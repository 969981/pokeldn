"""Synthetic regressions for the fail-closed 4.0.0 reward anchor gate.

No retail game binary is distributed or claimed to have been run here.
"""
import hashlib
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "research"))
import sv400_exact_reward_gate as gate
from sv400_main_blua_locator import Prototype
from sv_lua_reward_append_prototype import RewardRow, append_after_lottery, filter_like_f316


def _proto(path, code_offset, code, children=()):
    return Prototype(path=path, source=None, line_defined=0,
                     last_line_defined=0, num_params=0, is_vararg=0,
                     max_stack_size=4, code_offset=code_offset, code=tuple(code),
                     constants=(), upvalue_count=0, children=list(children))


def _fixture():
    first = _proto("root/0", 0x64, [0, 1, 2, 3, 4, 5])
    second = _proto("root/1", 0xC8, [7])
    root = _proto("root", 0x20, [1, 2], [first, second])
    anchors = {
        "root_code_count": 2,
        "root_children": 2,
        "methods": {
            "LotteryRewardItem": {
                "prototype_path": "root/0", "code_file_offset_hex": "0x64",
                "instruction_count": 6, "early_return_pcs": [0, 1],
                "candidate_post_construction_pc": 4,
                "candidate_return_file_offset_hex": "0x74",
            },
            "FilterSubject5": {
                "prototype_path": "root/1", "code_file_offset_hex": "0xC8",
                "instruction_count": 1,
            },
        },
    }
    return root, anchors


def test_all_exact_synthetic_anchors_pass_without_claiming_hook():
    root, anchors = _fixture()
    found = gate.verify_anchor_prototypes(root, anchors)
    assert found["LotteryRewardItem"]["candidate_instructions_not_execution_proof"][-1]["file_offset"] == 0x74
    assert found["FilterSubject5"]["instruction_count"] == 1


@pytest.mark.parametrize("field,value,match", [
    ("code_file_offset_hex", "0x65", "code offset"),
    ("instruction_count", 7, "instruction count"),
    ("candidate_return_file_offset_hex", "0x75", "PC/file-offset"),
    ("candidate_post_construction_pc", 6, "out of bounds"),
])
def test_mismatched_anchor_is_rejected(field, value, match):
    root, anchors = _fixture()
    anchors["methods"]["LotteryRewardItem"][field] = value
    with pytest.raises(ValueError, match=match):
        gate.verify_anchor_prototypes(root, anchors)


def test_wrong_prototype_path_is_rejected():
    root, anchors = _fixture()
    anchors["methods"]["FilterSubject5"]["prototype_path"] = "root/3"
    with pytest.raises(ValueError, match="missing Prototype"):
        gate.verify_anchor_prototypes(root, anchors)


def test_exact_hash_check_rejects_unexpected_input():
    data = b"synthetic only"
    anchors = {"main_blua_sha256": hashlib.sha256(data).hexdigest(),
               "main_blua_bytes": len(data)}
    assert gate.require_exact_build(data, anchors) == anchors["main_blua_sha256"]
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        gate.require_exact_build(data + b"!", anchors)


@pytest.mark.parametrize("has_charm,expected_extra", [(False, False), (True, True)])
def test_single_subject5_append_preserves_retail_prefix_offline(has_charm, expected_extra):
    original = [RewardRow(i + 1, 1, 0, 0) for i in range(20)]
    extra = RewardRow(492, 1, 0, 5)
    combined = append_after_lottery(original, [extra])
    assert combined[:20] == tuple(original)
    assert combined[20] == extra
    filtered = filter_like_f316(combined, is_host=False, has_glimmering_charm=has_charm)
    assert all(r in filtered for r in original)
    assert (extra in filtered) is expected_extra


def test_no_truncation_when_45_rows_are_full():
    original = [RewardRow(i + 1, 1, 0, 0) for i in range(45)]
    with pytest.raises(ValueError, match="refusing to overwrite"):
        append_after_lottery(original, [RewardRow(492, 1, 0, 5)])
    assert len(original) == 45
