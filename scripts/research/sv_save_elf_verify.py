#!/usr/bin/env python3
"""Verify original Violet 4.0.0 ELF save Lua-native registration and Commit path.
Read-only. This is build-specific; rejects a mismatched ELF hash.
"""
import argparse
import hashlib
import struct
from pathlib import Path

SHA256 = "d17403eaa9d844db82f647fd2f1518806b10c0518d53602fc0ac1766298fdba0"
TEXT_OFF = 0x8D8
REG_PTRS = {
    0x35186A8: 0x3AE1EE1,    # fAA5A90DA name pointer
    0x35186C0: 0x16D16D0,    # fAA5A90DA native wrapper
    0x35186D8: 0x3B704F6,    # f6F7C8191 name pointer
    0x35186F0: 0x147F530,    # f6F7C8191 native wrapper
}
OPCODES = {
    0x16D16FC: 0x94000015,  # BL 0x16D1750
    0x147F578: 0x9400001F,  # BL 0x147F5F4
    0x147F6A8: 0x7100081F,  # CMP W0,#2
    0x147F6AC: 0x54000081,  # B.NE 0x147F6BC
    0x147F6B8: 0x94000041,  # BL 0x147F7BC
    0x147F6C4: 0x94000059,  # BL cleanup 0x147F828
    0x147F6C8: 0x52800020,  # MOV W0,#1
    0x147F7A0: 0xB943DA73,  # LDR W19,[X19,#0x3D8]
    0x147F9A0: 0x947EFFF8,  # BL nn::fs::Commit@plt
    0x147F9C0: 0xB9000A95,  # STR W21,[X20,#8] (Result)
}

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("elf", type=Path)
    args = ap.parse_args()
    data = args.elf.read_bytes()
    actual_sha = hashlib.sha256(data).hexdigest()
    if actual_sha != SHA256:
        raise SystemExit(f"Unexpected ELF SHA256: {actual_sha} (expected {SHA256})")
    for off, expected in REG_PTRS.items():
        actual = struct.unpack_from("<Q", data, off)[0]
        assert actual == expected, f"registration {off:#x}: {actual:#x} != {expected:#x}"
    for rva, expected in OPCODES.items():
        actual = struct.unpack_from("<I", data, TEXT_OFF + rva)[0]
        assert actual == expected, f"RVA {rva:#x}: {actual:#x} != {expected:#x}"
    print(f"PASS SHA256; {len(REG_PTRS)} registration pointers; {len(OPCODES)} ARM64 opcodes")

if __name__ == "__main__":
    main()
