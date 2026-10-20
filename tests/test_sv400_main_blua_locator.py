"""Tests for the read-only Violet 4.0.0 main.blua locator."""

import importlib.util
from pathlib import Path
import struct
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sv400_main_blua_locator",
    ROOT / "scripts" / "research" / "sv400_main_blua_locator.py",
)
locator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = locator
SPEC.loader.exec_module(locator)


def _vu(value):
    groups = []
    while True:
        groups.append(value & 0x7F)
        value >>= 7
        if not value:
            break
    out = bytearray()
    for index, group in enumerate(reversed(groups)):
        if index == len(groups) - 1:
            group |= 0x80
        out.append(group)
    return bytes(out)


def _lua_string(value):
    if value is None:
        return _vu(0)
    raw = value.encode("utf-8")
    return _vu(len(raw) + 1) + raw


def _constant(value):
    if isinstance(value, str):
        return bytes([locator.TAG_SHORT_STRING]) + _lua_string(value)
    if isinstance(value, int):
        return bytes([locator.TAG_INTEGER]) + struct.pack("<q", value)
    raise TypeError(value)


def _prototype(*, constants=(), code=(0x12345678,), children=(), source=None):
    out = bytearray()
    out += _lua_string(source)
    out += _vu(1)
    out += _vu(2)
    out += bytes([0, 0, 8])
    out += _vu(len(code))
    for word in code:
        out += struct.pack("<I", word)
    out += _vu(len(constants))
    for value in constants:
        out += _constant(value)
    out += _vu(0)  # upvalues
    out += _vu(len(children))
    for child in children:
        out += child
    out += _vu(0)  # line info
    out += _vu(0)  # absolute line info
    out += _vu(0)  # locals
    out += _vu(0)  # upvalue names
    return bytes(out)


def _chunk(root):
    return (
        bytes.fromhex("1b4c75615400")
        + locator.LUA_CHECK
        + bytes([4, 8, 8])
        + struct.pack("<q", 0x5678)
        + struct.pack("<d", 370.5)
        + bytes([0])
        + root
    )


def _synthetic_chunk():
    lottery = _prototype(
        constants=(
            "reward_item_00",
            "difficulty_1",
            "subject_type",
            "slot_num",
            "itemID",
            "category",
            "num",
        ),
        code=(0x01020304, 0x11121314),
    )
    reward_filter = _prototype(
        constants=("ItemNo", "ItemNum", "rareType", "subjectType", 2481),
        code=(0xAABBCCDD,),
    )
    settlement = _prototype(
        constants=("ItemNo", "ItemNum", "WSYS_COIN_OVERFLOW_NUM", 2137),
        code=(0x0BADF00D,),
    )
    return _chunk(_prototype(children=(lottery, reward_filter, settlement)))


def test_parser_enumerates_prototypes_and_code_offsets():
    data = _synthetic_chunk()
    root = locator.parse_chunk(data)
    protos = list(locator.walk(root))
    assert len(protos) == 4
    lottery = protos[1]
    assert lottery.code == (0x01020304, 0x11121314)
    assert struct.unpack_from("<I", data, lottery.code_offset)[0] == 0x01020304


def test_fingerprints_find_expected_synthetic_bodies():
    report = locator.analyze_bytes(data=_synthetic_chunk(), require_violet_400_sha=False)
    assert report["status"] == "STRUCTURAL_ONLY_UNVERIFIED_BUILD"

    lottery = report["candidates"]["lottery_reward_item"]
    assert lottery["complete_candidate_count"] == 1

    reward_filter = report["candidates"]["battle_reward_filter"]
    assert reward_filter["complete_candidate_count"] == 1
    assert reward_filter["candidates"][0]["matched_integers"] == [2481]

    settlement = report["candidates"]["raid_result_add_item"]
    assert settlement["complete_candidate_count"] == 1
    assert settlement["candidates"][0]["matched_integers"] == [2137]


def test_instruction_dump_reports_file_offsets_and_fields():
    report = locator.analyze_bytes(
        _synthetic_chunk(),
        require_violet_400_sha=False,
        include_instructions_for={"battle_reward_filter"},
    )
    row = report["candidates"]["battle_reward_filter"]["candidates"][0]
    insn = row["instructions"][0]
    assert insn["word"] == "AABBCCDD"
    assert insn["file_offset"] == row["code_offset"]
    assert insn["opcode"] == (0xAABBCCDD & 0x7F)


def test_exact_build_is_required_by_default():
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        locator.analyze_bytes(_synthetic_chunk())


def test_trailing_bytes_are_rejected():
    with pytest.raises(ValueError, match="trailing bytes"):
        locator.parse_chunk(_synthetic_chunk() + b"X")
