"""Synthetic FlatBuffer regression for the read-only SV SlotMaxNum extractor.

No game binaries are committed or needed. Fields mimic the published
ItemDataArray.Values and ItemData.Id/SlotMaxNum vtable indices.
"""
import runpy
import struct
from pathlib import Path

import pytest

MODULE = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                            "docs/research/sv/scripts/slot_max_num.py"))
parse_items = MODULE["parse_items"]
BadFlatbuffer = MODULE["BadFlatbuffer"]


def make_one_item(item_id=15, maximum=999):
    buf = bytearray(240)
    struct.pack_into("<I", buf, 0, 32)  # root table address
    struct.pack_into("<HHH", buf, 16, 6, 8, 4)  # root vtable: field 0 at +4
    struct.pack_into("<iI", buf, 32, 16, 28)  # root table + vector at 64
    struct.pack_into("<II", buf, 64, 1, 132)  # count 1, offset entry 68 -> item table at 200
    struct.pack_into("<HH", buf, 100, 54, 12)  # item vtable / object sizes
    struct.pack_into("<H", buf, 104, 4)       # field 0 Id -> table +4
    struct.pack_into("<H", buf, 152, 8)       # field 24 SlotMaxNum -> table +8
    struct.pack_into("<iii", buf, 200, 100, item_id, maximum)
    return bytes(buf)


def test_itemdata_flatbuffer_reads_actual_id_and_slot_max_without_guessing():
    assert parse_items(make_one_item(15, 999)) == {15: 999}
    assert parse_items(make_one_item(796, 500)) == {796: 500}
    assert parse_items(make_one_item(50, 20)) == {50: 20}


def test_missing_slot_max_uses_flatbuffers_default_zero():
    buf = bytearray(make_one_item())
    struct.pack_into("<H", buf, 152, 0)
    assert parse_items(bytes(buf)) == {15: 0}


def test_corrupt_and_truncated_flatbuffers_fail_closed():
    with pytest.raises(BadFlatbuffer):
        parse_items(make_one_item()[:150])
    buf = bytearray(make_one_item())
    struct.pack_into("<I", buf, 64, 100_001)
    with pytest.raises(BadFlatbuffer):
        parse_items(bytes(buf))
