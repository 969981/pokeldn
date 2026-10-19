#!/usr/bin/env python3
"""Read-only SV itemdata_array.bin SlotMaxNum inventory. Requires no external packages.

Input must be a legally dumped, *unmodified* RomFS FlatBuffer:
    world/data/item/itemdata/itemdata_array.bin
Never distribute copyrighted game resource bytes; export only item ID/max metadata.

Structure cross-checked against KM-Editor generated ItemDataArray.cs / ItemData.cs:
  ItemDataArray.Values is field index 0, a vector of table offsets;
  ItemData.Id is field index 0; ItemData.SlotMaxNum is field index 24.
"""
import argparse
import csv
import hashlib
import struct
import sys
from pathlib import Path


class BadFlatbuffer(ValueError):
    pass


def scalar(blob: bytes, pos: int, fmt: str) -> int:
    length = struct.calcsize(fmt)
    if pos < 0 or pos + length > len(blob):
        raise BadFlatbuffer(f"out of bounds: {pos:#x} + {length:#x}")
    return struct.unpack_from("<" + fmt, blob, pos)[0]


def field(blob: bytes, obj: int, index: int) -> int | None:
    """Absolute address of a table's field, or None when omitted (default 0)."""
    vt = obj - scalar(blob, obj, "i")
    size = scalar(blob, vt, "H")
    object_size = scalar(blob, vt + 2, "H")
    if size < 4 or object_size < 4:
        raise BadFlatbuffer(f"invalid vtable at {vt:#x}")
    slot = vt + 4 + 2 * index
    if slot + 2 > vt + size:
        return None
    delta = scalar(blob, slot, "H")
    if delta == 0:
        return None
    if delta >= object_size:
        raise BadFlatbuffer(f"field {index} outside object {obj:#x}")
    address = obj + delta
    scalar(blob, address, "B")
    return address


def parse_items(blob: bytes) -> dict[int, int]:
    root = scalar(blob, 0, "I")
    values = field(blob, root, 0)
    if values is None:
        raise BadFlatbuffer("ItemDataArray.Values is absent")
    vector = values + scalar(blob, values, "I")
    count = scalar(blob, vector, "I")
    if count > 100_000:
        raise BadFlatbuffer(f"unexpected item count {count}")
    result = {}
    for n in range(count):
        ptr = vector + 4 + 4 * n
        obj = ptr + scalar(blob, ptr, "I")
        id_addr = field(blob, obj, 0)
        max_addr = field(blob, obj, 24)
        item_id = scalar(blob, id_addr, "i") if id_addr is not None else 0
        max_num = scalar(blob, max_addr, "i") if max_addr is not None else 0
        if item_id in result:
            raise BadFlatbuffer(f"duplicate item ID {item_id}")
        if not 0 <= item_id <= 100_000 or max_num < 0:
            raise BadFlatbuffer(f"unreasonable item record ID {item_id} / max {max_num}")
        result[item_id] = max_num
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("file", type=Path, help="owned RomFS itemdata_array.bin")
    ap.add_argument("--ids", default="1,15,50,795,796,1606,2481",
                    help="comma-separated target IDs; use 'all' for the full table")
    ap.add_argument("--csv", type=Path, help="save only id/slot_max_num as CSV")
    args = ap.parse_args()
    data = args.file.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    try:
        found = parse_items(data)
    except BadFlatbuffer as exc:
        ap.error(f"invalid/nonmatching FlatBuffer: {exc}")
    ids = sorted(found) if args.ids == "all" else [int(v.strip(), 0) for v in args.ids.split(",")]
    rows = [{"item_id": i, "slot_max_num": found[i]} for i in ids if i in found]
    print(f"input={args.file} size={len(data)} sha256={sha} total_items={len(found)}")
    print(f"requested={len(ids)} found={len(rows)} missing={sorted(set(ids) - found.keys())}")
    for row in rows:
        print(f"{row['item_id']},{row['slot_max_num']}")
    if args.csv:
        with args.csv.open("w", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=["item_id", "slot_max_num"])
            writer.writeheader()
            writer.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
