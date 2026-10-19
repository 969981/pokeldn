#!/usr/bin/env python3
"""Read-only ELF opcode verification, RaidPoint layout, and offline plaintext reward editing.

Never attaches to a process; never edits executable or compressed network packets.
"""
import argparse
import hashlib
from pathlib import Path
import struct

POINT_SIZE = 0x3E8
BOOTSTRAP_SIZE = 0xAA0
RAIDPOINT_OFFSET = 0x6B8
ROW_OFFSET = 0xE4
ROW_END = 0x3B4  # +0x3B4..+0x3B7 are NOT another reward row
ROW_SIZE = 16
ROW_COUNT = 45
ELF_SHA256 = "d17403eaa9d844db82f647fd2f1518806b10c0518d53602fc0ac1766298fdba0"
ELF_TEXT_FILE_BIAS = 0x8D8
OPCODES = {
    0xE32814: 0xAA0003F4,  # mov x20,x0
    0xE3283C: 0xAA0003F7,  # mov x23,x0
    0xE3295C: 0xA946A688,  # ldp x8,x9,[x20,#0x68]
    0xE32960: 0x911B62E0,  # add x0,x23,#0x6D8
    0xE32964: 0xA945AA8B,  # ldp x11,x10,[x20,#0x58]
    0xE32968: 0x9101E281,  # add x1,x20,#0x78
    0xE3296C: 0x52807902,  # mov w2,#0x3C8
    0xE32970: 0xF9035EEB,  # str x11,[x23,#0x6B8]
    0xE32974: 0xF9036AE9,  # str x9,[x23,#0x6D0]
    0xE32978: 0xF90366E8,  # str x8,[x23,#0x6C8]
    0xE3297C: 0xF90362EA,  # str x10,[x23,#0x6C0]
    0xE32980: 0x94982624,  # bl memcpy@plt
    0xE329B0: 0x141D8073,  # b 0x1592B7C
}

def base_of(data):
    if len(data) == POINT_SIZE:
        base = 0
    elif len(data) == BOOTSTRAP_SIZE:
        base = RAIDPOINT_OFFSET
    else:
        raise ValueError("expected uncompressed 0x3E8 RaidPoint or 0xAA0 bootstrap")
    if data[base:base + 10] != b"RaidPoint_":
        raise ValueError("missing RaidPoint_ prefix: not a recognized plain RaidPoint")
    return base

def parse_reward(value):
    parts = value.split(":")
    if len(parts) not in (2, 3):
        raise ValueError("reward must be ITEM:QUANTITY[:SUBJECT]")
    item, quantity = (int(x, 0) for x in parts[:2])
    subject = int(parts[2], 0) if len(parts) == 3 else 0
    if not 1 <= item <= 65535 or not 1 <= quantity <= 999 or subject not in (0, 5):
        raise ValueError("require 1<=item<=65535, 1<=quantity<=999, subject in {0,5}")
    return item, quantity, 0, subject

def edit_plain(data, rows):
    if not 1 <= len(rows) <= ROW_COUNT:
        raise ValueError("require 1..45 replacement rows")
    base = base_of(data)
    out = bytearray(data)
    out[base + ROW_OFFSET:base + ROW_END] = bytes(ROW_END - ROW_OFFSET)
    for i, row in enumerate(rows):
        struct.pack_into("<4I", out, base + ROW_OFFSET + ROW_SIZE * i, *row)
    assert len(out) == len(data)
    assert out[:base + ROW_OFFSET] == data[:base + ROW_OFFSET]
    assert out[base + ROW_END:] == data[base + ROW_END:]
    return bytes(out)

def verify_elf(path):
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != ELF_SHA256:
        raise ValueError(f"ELF SHA mismatch: {digest}; offsets are specific to Violet 4.0.0")
    for rva, expected in OPCODES.items():
        found = struct.unpack_from("<I", data, ELF_TEXT_FILE_BIAS + rva)[0]
        if found != expected:
            raise ValueError(f"opcode mismatch at main+0x{rva:X}: {found:08X} vs {expected:08X}")
    return len(OPCODES)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    e = sub.add_parser("verify-elf", help="verify unmodified Violet 4.0.0 ELF SHA + 13 opcodes")
    e.add_argument("file", type=Path)
    layout = sub.add_parser("layout", help="print 0-based row input and output offsets")
    layout.add_argument("row", type=int)
    inspect = sub.add_parser("inspect", help="read up to 45 rows from an uncompressed RaidPoint/bootstrap")
    inspect.add_argument("file", type=Path)
    patch = sub.add_parser("patch", help="write a NEW plaintext blob; original remains unchanged")
    patch.add_argument("file", type=Path)
    patch.add_argument("--reward", action="append", required=True)
    patch.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.action == "verify-elf":
        n = verify_elf(a.file)
        print(f"PASS: SHA256 and {n}/{n} AArch64 opcodes")
    elif a.action == "layout":
        if not 0 <= a.row < ROW_COUNT:
            p.error("row index must be 0..44")
        shift = ROW_OFFSET + ROW_SIZE * a.row
        print(f"row={a.row} RaidPoint+0x{shift:X} "
              f"bootstrap+0x{RAIDPOINT_OFFSET + shift:X} "
              f"serializer_x20+0x{0x58 + shift:X} "
              f"serializer_x23+0x{RAIDPOINT_OFFSET + shift:X}; "
              "fields at +0/+4/+8/+0xC")
    elif a.action == "inspect":
        data = a.file.read_bytes()
        base = base_of(data)
        for i in range(ROW_COUNT):
            row = struct.unpack_from("<4I", data, base + ROW_OFFSET + ROW_SIZE * i)
            if any(row):
                print(f"[{i:02}] item={row[0]} quantity={row[1]} rare={row[2]} subject={row[3]}")
    else:
        if a.file.resolve() == a.output.resolve():
            p.error("input and output paths must differ")
        rows = [parse_reward(v) for v in a.reward]
        out = edit_plain(a.file.read_bytes(), rows)
        if a.output.exists():
            p.error("output exists; refusing overwrite")
        a.output.write_bytes(out)
        print(f"wrote {len(out)} plaintext bytes with {len(rows)} rewards to {a.output}")

if __name__ == "__main__":
    main()
