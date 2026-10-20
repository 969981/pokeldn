"""Offline model for the SV raid reward post-generation append hook.

This intentionally models only the Lua-visible reward list semantics proven by
Martmists-GH/SV-Script-RE commit
1f843bd2517c707fbb47491dad58856eaa2c2cc7:

* FieldRaidJewelry.LotteryRewardItem returns BattleRewardData.
* BattleRewardData[3] is serialized as up to 45 reward rows.
* BattleRewardData.F316609DEA110601D filters rows by subjectType.

It does NOT patch a running game, claim a Violet 4.0.0 bytecode PC, add items to
a real Bag, or prove save persistence.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys

MAX_ROWS = 45
VALID_SUBJECTS = frozenset(range(6))


@dataclass(frozen=True)
class RewardRow:
    item: int
    quantity: int
    rare: int = 0
    subject: int = 0

    @classmethod
    def from_sequence(cls, value):
        if not isinstance(value, (list, tuple)) or len(value) != 4:
            raise ValueError("a reward row must be [item, quantity, rare, subject]")
        row = cls(*value)
        row.validate()
        return row

    def validate(self):
        for name, value in (
            ("item", self.item),
            ("quantity", self.quantity),
            ("rare", self.rare),
            ("subject", self.subject),
        ):
            if type(value) is not int:
                raise ValueError(f"{name} must be an integer")
        if not 1 <= self.item <= 0xFFFFFFFF:
            raise ValueError("item must be 1..0xffffffff")
        if not 1 <= self.quantity <= 0xFFFFFFFF:
            raise ValueError("quantity must be 1..0xffffffff")
        if not 0 <= self.rare <= 0xFFFFFFFF:
            raise ValueError("rare must be 0..0xffffffff")
        if self.subject not in VALID_SUBJECTS:
            raise ValueError("subject must be 0..5")
        return self

    def as_list(self):
        return [self.item, self.quantity, self.rare, self.subject]


def append_after_lottery(original_rows, extra_rows):
    """Append only after retail generation; never replace an original row.

    The 45-row serializer bound is treated as a hard fail-closed gate. This is
    deliberate: overwriting/truncating an original row would violate P1's
    primary invariant that retail rewards must not decrease.
    """
    original = tuple(row.validate() for row in original_rows)
    extra = tuple(row.validate() for row in extra_rows)
    if len(original) + len(extra) > MAX_ROWS:
        raise ValueError(
            f"append needs {len(original) + len(extra)} rows but serializer holds {MAX_ROWS}; "
            "refusing to overwrite retail rewards"
        )
    return original + extra


def filter_like_f316(
    rows,
    *,
    is_host,
    once_eligible=False,
    has_glimmering_charm=False,
    raid_power_level=0,
):
    """Model BattleRewardData.F316609DEA110601D from the pinned public decompile."""
    if type(is_host) is not bool:
        raise ValueError("is_host must be a boolean")
    if type(once_eligible) is not bool:
        raise ValueError("once_eligible must be a boolean")
    if type(has_glimmering_charm) is not bool:
        raise ValueError("has_glimmering_charm must be a boolean")
    if type(raid_power_level) is not int or not 0 <= raid_power_level <= 3:
        raise ValueError("raid_power_level must be 0..3")

    selected = []
    subject4_index = 0
    for row in rows:
        row.validate()
        keep = (
            row.subject == 0
            or (row.subject == 1 and is_host)
            or (row.subject == 2 and not is_host)
            or (row.subject == 3 and once_eligible)
            or (row.subject == 4 and subject4_index < raid_power_level)
            or (row.subject == 5 and has_glimmering_charm)
        )
        if row.subject == 4:
            subject4_index += 1
        if keep:
            selected.append(row)
    return tuple(selected)


def analyze(document):
    if not isinstance(document, dict):
        raise ValueError("input must be a JSON object")
    original = tuple(RewardRow.from_sequence(row) for row in document.get("original_rows", ()))
    extra = tuple(RewardRow.from_sequence(row) for row in document.get("extra_rows", ()))
    eligibility = document.get("eligibility", {})
    if not isinstance(eligibility, dict):
        raise ValueError("eligibility must be an object")

    augmented = append_after_lottery(original, extra)
    filtered = filter_like_f316(
        augmented,
        is_host=eligibility.get("is_host", False),
        once_eligible=eligibility.get("once_eligible", False),
        has_glimmering_charm=eligibility.get("has_glimmering_charm", False),
        raid_power_level=eligibility.get("raid_power_level", 0),
    )
    return {
        "status": "MODEL_ONLY",
        "original_count": len(original),
        "extra_count": len(extra),
        "augmented_count": len(augmented),
        "original_prefix_unchanged": augmented[: len(original)] == original,
        "original_rows": [row.as_list() for row in original],
        "augmented_rows": [row.as_list() for row in augmented],
        "filtered_rows": [row.as_list() for row in filtered],
        "hardware_bag_delta": "PENDING",
        "reload_persistence": "PENDING",
    }


def _read_json(path):
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSON model input, or - for stdin")
    parser.add_argument("--output", help="write JSON report here instead of stdout")
    args = parser.parse_args(argv)
    try:
        report = analyze(_read_json(args.input))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"append model error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
