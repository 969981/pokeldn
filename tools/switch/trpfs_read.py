#!/usr/bin/env python3
"""List and extract files from a Trinity packed file system (Scarlet and Violet).

    ./.venv/bin/python tools/switch/trpfs_read.py --romfs-dir DIR --list [--grep personal]
    ./.venv/bin/python tools/switch/trpfs_read.py --update UPDATE.nsp --base BASE.xci --keys KEYS \\
        --nca 7e5b9bbf --base-nca d8c3a585 --extract avalon/data/personal_array.bin --out-dir OUT

`arc/data.trpfd` names the files (FNV-1a 64 path hashes) and the packs; `arc/data.trpfs` holds the
packs. An entry of compression type 3 is Oodle: it runs the title's own OodleLZ_Decompress from its
main image under unicorn (`--image`, `--oodle`; Scarlet 4.0.0 `0xcc8750`). docs/za.md "The personal table".
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FNV_BASIS = 0xCBF29CE484222645
FNV_PRIME = 0x100000001B3
OODLE = 3


def fnv1a64(text):
    h = FNV_BASIS
    for c in text.encode() if isinstance(text, str) else text:
        h = ((h ^ c) * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return h


class Fb:
    """Just enough FlatBuffers to walk an untyped buffer."""

    def __init__(self, buf):
        self.b = buf

    def u32(self, at):
        return struct.unpack_from("<I", self.b, at)[0]

    def u64(self, at):
        return struct.unpack_from("<Q", self.b, at)[0]

    def root(self):
        return self.u32(0)

    def field(self, table, i):
        """Absolute position of field i of the table at `table`, or 0 when absent."""
        vt = table - struct.unpack_from("<i", self.b, table)[0]
        vsize = struct.unpack_from("<H", self.b, vt)[0]
        if 4 + 2 * i >= vsize:
            return 0
        off = struct.unpack_from("<H", self.b, vt + 4 + 2 * i)[0]
        return table + off if off else 0

    def vec(self, table, i):
        """-> (data start, count) of the vector in field i."""
        at = self.field(table, i)
        if not at:
            return 0, 0
        v = at + self.u32(at)
        return v + 4, self.u32(v)

    def u64s(self, table, i):
        start, n = self.vec(table, i)
        return struct.unpack_from(f"<{n}Q", self.b, start) if n else ()

    def tables(self, table, i):
        start, n = self.vec(table, i)
        return [start + 4 * k + self.u32(start + 4 * k) for k in range(n)]

    def string(self, at):
        v = at + self.u32(at)
        return self.b[v + 4:v + 4 + self.u32(v)].decode()


class Oodle:
    """OodleLZ_Decompress from a title's main image, under unicorn; only PLT imports are hooked."""

    BUF = 0x60000000

    def __init__(self, image, entry):
        from nso_run import load, _plt_stubs
        from nso_imports import imports
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
        img = load(image)
        self.entry = entry
        self.uc = uc = Uc(UC_ARCH_ARM64, UC_MODE_LITTLE_ENDIAN)
        uc.ctl_set_tcg_buffer_size(64 << 20)
        uc.mem_map(0, (len(img) + 0xFFFFF) & ~0xFFFFF)
        uc.mem_write(0, bytes(img))
        self.stubs = _plt_stubs(img, dict(imports(bytes(img))))
        self.cap = 0
        if self.stubs:
            uc.hook_add(UC_HOOK_CODE, self._stub, begin=min(self.stubs), end=max(self.stubs) + 16)

    def _stub(self, uc, addr, _size, _):
        from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, \
            UC_ARM64_REG_LR, UC_ARM64_REG_PC
        name = self.stubs.get(addr)
        if name is None:
            return
        x0, x1, x2 = (uc.reg_read(r) for r in (UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2))
        if name in ("memcpy", "memmove"):
            uc.mem_write(x0, bytes(uc.mem_read(x1, x2)))
        elif name == "memset":
            uc.mem_write(x0, bytes([x1 & 0xFF]) * x2)
        else:
            raise RuntimeError(f"OodleLZ_Decompress called import {name}")
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_LR))

    def _room(self, need):
        if need > self.cap:
            if self.cap:
                self.uc.mem_unmap(self.BUF, self.cap)
            self.cap = (need + 0xFFFFF) & ~0xFFFFF
            self.uc.mem_map(self.BUF, self.cap)

    def decompress(self, comp, rawlen):
        """The game's call (0x27ad6b0): fuzz-safe 1, no CRC, no window, 0x80000 bytes of decoder
        memory, thread phase 3."""
        from unicorn.arm64_const import UC_ARM64_REG_SP, UC_ARM64_REG_LR, UC_ARM64_REG_X0
        clen = (len(comp) + 0xFFF) & ~0xFFF
        rlen = (rawlen + 0xFFF) & ~0xFFF
        mem_size, stack = 0x80000, 0x100000
        self._room(clen + rlen + mem_size + stack + 0x1000)
        cin, raw = self.BUF, self.BUF + clen
        mem = raw + rlen
        sp = mem + mem_size + stack - 0x100
        ret = sp + 0x80
        uc = self.uc
        uc.mem_write(cin, bytes(comp))
        uc.mem_write(sp, struct.pack("<6Q", 0, 0, 0, mem, mem_size, 3))
        uc.mem_write(ret, b"\x00\x00\x20\xd4")              # brk: never reached, emu stops first
        uc.reg_write(UC_ARM64_REG_SP, sp)
        uc.reg_write(UC_ARM64_REG_LR, ret)
        for i, v in enumerate((cin, len(comp), raw, rawlen, 1, 0, 0, 0)):
            uc.reg_write(UC_ARM64_REG_X0 + i, v)
        uc.emu_start(self.entry, ret)
        n = uc.reg_read(UC_ARM64_REG_X0)
        if n != rawlen:
            raise RuntimeError(f"OodleLZ_Decompress returned {n}, expected {rawlen}")
        return bytes(uc.mem_read(raw, rawlen))


class Source:
    """Byte ranges of arc/data.trpfd and arc/data.trpfs, from a directory or the containers."""

    def __init__(self, args):
        if args.romfs_dir:
            self.fd = open(os.path.join(args.romfs_dir, "arc", "data.trpfd"), "rb").read()
            path = os.path.join(args.romfs_dir, "arc", "data.trpfs")
            self._fs = open(path, "rb")
            self.fs_size = os.path.getsize(path)
            self.read_fs = self._read_file
            return
        from xci_read import load_keys
        from bktr_read import open_update_romfs
        _virt, romfs = open_update_romfs(args.update, args.base, load_keys(args.keys),
                                         args.nca, args.base_nca)
        files = {p: (o, s) for p, o, s in romfs.walk()}
        self.fd = romfs.read_file(*files["/arc/data.trpfd"])
        fs_off, self.fs_size = files["/arc/data.trpfs"]
        self.read_fs = lambda off, size: romfs.read_file(fs_off + off, size)

    def _read_file(self, off, size):
        self._fs.seek(off)
        return self._fs.read(size)


class Trpfs:
    def __init__(self, src):
        self.src = src
        fd = self.fd = Fb(src.fd)
        root = fd.root()
        self.file_hashes = fd.u64s(root, 0)
        self.index = {h: i for i, h in enumerate(self.file_hashes)}
        self.pack_names = [fd.string(at) for at in
                           (lambda s, n: [s + 4 * k for k in range(n)])(*fd.vec(root, 1))]
        self.file_pack = [fd.u64(fd.field(t, 0)) if fd.field(t, 0) else 0
                          for t in fd.tables(root, 2)]
        self.pack_size = [fd.u64(fd.field(t, 0)) for t in fd.tables(root, 3)]
        head = src.read_fs(0, 16)
        if head[:7] != b"ONEPACK":
            raise ValueError("data.trpfs: no ONEPACK magic")
        table_at = struct.unpack_from("<Q", head, 8)[0]
        tail = Fb(src.read_fs(table_at, src.fs_size - table_at))
        troot = tail.root()
        self.pack_at = dict(zip(tail.u64s(troot, 0), tail.u64s(troot, 1)))
        self.packs = {}

    def pack(self, i):
        if i not in self.packs:
            name = self.pack_names[i]
            off = self.pack_at[fnv1a64(name)]
            self.packs[i] = Fb(self.src.read_fs(off, self.pack_size[i]))
        return self.packs[i]

    def entry(self, file_hash):
        """-> (pack index, compression type, decompressed size, stored bytes)."""
        i = self.index[file_hash]
        p = self.file_pack[i]
        pk = self.pack(p)
        root = pk.root()
        k = pk.u64s(root, 0).index(file_hash)
        t = pk.tables(root, 1)[k]
        ctype = struct.unpack_from("<b", pk.b, pk.field(t, 1))[0] if pk.field(t, 1) else -1
        dsize = pk.u64(pk.field(t, 3)) if pk.field(t, 3) else 0
        start, n = pk.vec(t, 4)
        return p, ctype, dsize, pk.b[start:start + n]

    def read(self, file_hash, oodle):
        _p, ctype, dsize, data = self.entry(file_hash)
        if ctype == OODLE:
            return oodle.decompress(data, dsize)
        if ctype not in (-1, 0):
            raise ValueError(f"{file_hash:016x}: compression type {ctype}")
        return bytes(data)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--romfs-dir", help="a directory holding arc/data.trpfd and arc/data.trpfs")
    ap.add_argument("--update", help="the update NSP, read in place with bktr_read.py")
    ap.add_argument("--base", help="the base game's XCI/NSP")
    ap.add_argument("--keys", default=os.path.expanduser("~/.switch/prod.keys"))
    ap.add_argument("--nca", help="update Program NCA name prefix")
    ap.add_argument("--base-nca", help="base Program NCA name prefix")
    ap.add_argument("--image", default="scratchpad/sv/main.bin", help="main image for Oodle")
    ap.add_argument("--oodle", type=lambda s: int(s, 0), default=0xCC8750,
                    help="OodleLZ_Decompress in --image (Scarlet 4.0.0 0xcc8750, Z-A 2.0.2 0x1a9c9e0)")
    ap.add_argument("--list", action="store_true", help="print the packs and file counts")
    ap.add_argument("--grep", help="with --list: only pack names containing this")
    ap.add_argument("--extract", nargs="*", default=[], help="paths or 0x hashes to extract")
    ap.add_argument("--out-dir", default=".", help="where --extract writes, under the file's path")
    args = ap.parse_args(argv)
    if not args.romfs_dir and not (args.update and args.base):
        ap.error("give --romfs-dir, or --update and --base")

    fs = Trpfs(Source(args))
    print(f"{len(fs.file_hashes)} files, {len(fs.pack_names)} packs", file=sys.stderr)
    if args.list:
        counts = {}
        for p in fs.file_pack:
            counts[p] = counts.get(p, 0) + 1
        for i, name in enumerate(fs.pack_names):
            if args.grep and args.grep.lower() not in name.lower():
                continue
            print(f"{i:6d}  {fs.pack_size[i]:12d}  {counts.get(i, 0):6d}  {name}")
    oodle = Oodle(args.image, args.oodle) if args.extract else None
    for want in args.extract:
        h = int(want, 16) if want.startswith("0x") else fnv1a64(want)
        if h not in fs.index:
            sys.exit(f"{want}: hash {h:016x} not in data.trpfd")
        p, ctype, dsize, data = fs.entry(h)
        out = fs.read(h, oodle)
        dest = os.path.join(args.out_dir, want if not want.startswith("0x") else f"{h:016x}.bin")
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        with open(dest, "wb") as fh:
            fh.write(out)
        print(f"{want}  hash {h:016x}  pack {p} {fs.pack_names[p]}  type {ctype}  "
              f"{len(data)} -> {len(out)} bytes -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
