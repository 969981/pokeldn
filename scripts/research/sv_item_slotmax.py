#!/usr/bin/env python3
"""Read Pokémon SV ItemDataArray FlatBuffers SlotMaxNum; no writes to source.
Source schema: pkNX FlatBuffers/SV/Item/Schemas/ItemDataArray.fbs
Field indexes: ItemData.Id = 0; ItemData.SlotMaxNum = 24.
"""
import argparse
import csv
import hashlib
import io
import struct
import sys
from pathlib import Path

RELATIVE = Path("world/data/item/itemdata/itemdata_array.bin")
NAMES = {
    1: "Master Ball", 50: "Rare Candy",
    492: "Fast Ball", 493: "Level Ball", 494: "Lure Ball",
    495: "Heavy Ball", 496: "Love Ball", 497: "Friend Ball",
    498: "Moon Ball", 499: "Sport Ball", 581: "Big Nugget",
    796: "Gold Bottle Cap", 851: "Beast Ball", 1128: "Exp. Candy XL",
    1606: "Ability Patch", 1904: "Sweet Herba Mystica",
    1905: "Salty Herba Mystica", 1906: "Sour Herba Mystica",
    1907: "Bitter Herba Mystica", 1908: "Spicy Herba Mystica",
}

def unpack(data: bytes, fmt: str, pos: int) -> int:
    size = struct.calcsize(fmt)
    if pos < 0 or pos + size > len(data):
        raise ValueError(f"invalid FlatBuffer offset {pos} for {fmt}")
    return struct.unpack_from(fmt, data, pos)[0]

def field(data: bytes, table: int, index: int):
    back = unpack(data, "<i", table)
    vt = table - back
    vt_size = unpack(data, "<H", vt)
    if vt_size < 4 or vt + vt_size > len(data):
        raise ValueError(f"invalid vtable size at {vt}")
    slot = vt + 4 + index * 2
    if slot + 2 > vt + vt_size:
        return None
    offset = unpack(data, "<H", slot)
    return table + offset if offset else None

def parse(data: bytes):
    root = unpack(data, "<I", 0)
    vec_slot = field(data, root, 0)
    if vec_slot is None:
        raise ValueError("ItemDataArray.Table field missing")
    vec = vec_slot + unpack(data, "<I", vec_slot)
    count = unpack(data, "<I", vec)
    if count > 20000 or vec + 4 + count * 4 > len(data):
        raise ValueError(f"invalid table count {count}")
    out = {}
    for i in range(count):
        element = vec + 4 + 4 * i
        table = element + unpack(data, "<I", element)
        id_at = field(data, table, 0)
        if id_at is None:
            raise ValueError(f"ItemData[{i}] missing Id")
        item_id = unpack(data, "<i", id_at)
        max_at = field(data, table, 24)
        slot_max = unpack(data, "<i", max_at) if max_at is not None else 0
        if not 0 <= item_id <= 100000 or not 0 <= slot_max <= 100000000:
            raise ValueError(f"unexpected item {item_id} / SlotMaxNum {slot_max}")
        if item_id in out:
            raise ValueError(f"duplicate ItemData.Id {item_id}")
        out[item_id] = slot_max
    return out

def self_test():
    # Synthetic two-table FlatBuffers: root table -> vector -> ItemData row
    d = bytearray(256)
    struct.pack_into("<I", d, 0, 16)          # root table
    struct.pack_into("<HHH", d, 8, 6, 8, 4)   # root vtable
    struct.pack_into("<iI", d, 16, 8, 12)     # vtable offset, vector relative
    struct.pack_into("<II", d, 32, 1, 92)     # one vector item at 128
    struct.pack_into("<HH", d, 70, 54, 12)    # ItemData vtable 25 fields
    struct.pack_into("<H", d, 74, 4)          # field 0 / Id
    struct.pack_into("<H", d, 122, 8)         # field 24 / SlotMaxNum
    struct.pack_into("<i", d, 128, 58)        # ItemData vtable back
    struct.pack_into("<ii", d, 132, 1, 999)   # Id=1, Max=999
    assert parse(bytes(d)) == {1: 999}
    print("PASS: 1/1 synthetic FlatBuffer SlotMaxNum tests", file=sys.stderr)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", nargs="?", type=Path, help="SV RomFS root or itemdata_array.bin")
    ap.add_argument("--all", action="store_true", help="print all items")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return
    if args.path is None:
        ap.error("path is required unless --self-test is supplied")
    p = args.path / RELATIVE if args.path.is_dir() else args.path
    data = p.read_bytes()
    items = parse(data)
    print(f"source={p} bytes={len(data)} sha256={hashlib.sha256(data).hexdigest()} items={len(items)}", file=sys.stderr)
    writer = csv.writer(sys.stdout)
    writer.writerow(["item_id", "name_en", "slot_max_num", "status"])
    selected = sorted(items) if args.all else sorted(NAMES)
    for item_id in selected:
        val = items.get(item_id)
        writer.writerow([item_id, NAMES.get(item_id, ""), "" if val is None else val, "missing" if val is None else "found"])

if __name__ == "__main__":
    main()
