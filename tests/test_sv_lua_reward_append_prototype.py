"""Regression tests for the post-LotteryRewardItem append research model."""

import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sv_lua_reward_append_prototype",
    ROOT / "scripts" / "research" / "sv_lua_reward_append_prototype.py",
)
prototype = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = prototype
SPEC.loader.exec_module(prototype)

RewardRow = prototype.RewardRow


def test_append_preserves_every_original_row_byte_semantically():
    original = (
        RewardRow(1127, 1, 0, 0),
        RewardRow(2064, 3, 0, 2),
        RewardRow(567, 2, 0, 4),
        RewardRow(1862, 10, 0, 5),
    )
    extra = (RewardRow(1, 7, 0, 5),)
    augmented = prototype.append_after_lottery(original, extra)
    assert augmented[: len(original)] == original
    assert augmented[len(original):] == extra


@pytest.mark.parametrize(
    "has_charm,extra_visible",
    [(False, False), (True, True)],
)
def test_subject5_extra_uses_original_filter(has_charm, extra_visible):
    original = (
        RewardRow(1127, 1, 0, 0),
        RewardRow(2064, 3, 0, 2),
    )
    extra = RewardRow(1, 7, 0, 5)
    rows = prototype.append_after_lottery(original, (extra,))
    filtered = prototype.filter_like_f316(
        rows,
        is_host=False,
        has_glimmering_charm=has_charm,
    )
    assert original[0] in filtered
    assert original[1] in filtered
    assert (extra in filtered) is extra_visible


def test_full_45_row_retail_result_fails_closed_instead_of_overwriting():
    original = tuple(RewardRow(i + 1, 1, 0, 0) for i in range(45))
    snapshot = tuple(original)
    with pytest.raises(ValueError, match="refusing to overwrite retail rewards"):
        prototype.append_after_lottery(original, (RewardRow(999, 1, 0, 5),))
    assert original == snapshot


def test_subject4_ordinal_is_unchanged_by_appended_subject5():
    original = (
        RewardRow(100, 1, 0, 4),
        RewardRow(101, 1, 0, 4),
        RewardRow(102, 1, 0, 0),
    )
    extra = RewardRow(1, 7, 0, 5)
    filtered = prototype.filter_like_f316(
        prototype.append_after_lottery(original, (extra,)),
        is_host=False,
        has_glimmering_charm=True,
        raid_power_level=1,
    )
    assert filtered == (original[0], original[2], extra)


def test_model_report_never_claims_hardware_or_persistence_pass():
    report = prototype.analyze(
        {
            "original_rows": [[1127, 1, 0, 0], [2064, 3, 0, 2]],
            "extra_rows": [[1, 7, 0, 5]],
            "eligibility": {
                "is_host": False,
                "once_eligible": False,
                "has_glimmering_charm": True,
                "raid_power_level": 0,
            },
        }
    )
    assert report["original_prefix_unchanged"] is True
    assert report["filtered_rows"][-1] == [1, 7, 0, 5]
    assert report["hardware_bag_delta"] == "PENDING"
    assert report["reload_persistence"] == "PENDING"
