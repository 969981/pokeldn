#!/usr/bin/env python3
"""Fail-closed identity and Prototype-location gate for Violet 4.0.0 main.blua.

Read-only. Requires the exact retail SHA, then checks the independently
recorded four method paths, code offsets and instruction counts. It does not
patch bytecode, install a runtime Hook, or claim items reach the player's bag.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from sv400_main_blua_locator import parse_chunk, raw_instruction


DEFAULT_ANCHORS = (
    Path(__file__).resolve().parents[2]
    / "docs/research/sv/references/violet400-reward-prototype-anchors.json"
)


def require_exact_build(data: bytes, anchors: dict) -> str:
    digest = hashlib.sha256(data).hexdigest()
    expected = anchors["main_blua_sha256"].lower()
    if digest != expected:
        raise ValueError(f"SHA-256 mismatch: actual {digest}, expected {expected}")
    if len(data) != anchors["main_blua_bytes"]:
        raise ValueError("exact-build size does not match anchor manifest")
    return digest


def locate(root, path: str):
    parts = path.split("/")
    if not parts or parts[0] != "root":
        raise ValueError(f"invalid Prototype path: {path}")
    current = root
    for part in parts[1:]:
        if not part.isdigit() or int(part) >= len(current.children):
            raise ValueError(f"missing Prototype path: {path}")
        current = current.children[int(part)]
    return current


def verify_anchor_prototypes(root, anchors: dict) -> dict:
    if len(root.code) != anchors["root_code_count"]:
        raise ValueError("root instruction count differs from exact-build manifest")
    if len(root.children) != anchors["root_children"]:
        raise ValueError("root child count differs from exact-build manifest")
    found = {}
    for name, spec in anchors["methods"].items():
        proto = locate(root, spec["prototype_path"])
        expected_offset = int(spec["code_file_offset_hex"], 16)
        if proto.code_offset != expected_offset:
            raise ValueError(f"{name}: code offset mismatch")
        if len(proto.code) != spec["instruction_count"]:
            raise ValueError(f"{name}: instruction count mismatch")
        record = {
            "path": spec["prototype_path"],
            "code_file_offset_hex": f"0x{proto.code_offset:X}",
            "instruction_count": len(proto.code),
        }
        if name == "LotteryRewardItem":
            pcs = [*spec["early_return_pcs"], spec["candidate_post_construction_pc"]]
            if len(set(pcs)) != len(pcs) or any(pc < 0 or pc >= len(proto.code) for pc in pcs):
                raise ValueError("LotteryRewardItem: candidate PCs out of bounds")
            if (expected_offset + spec["candidate_post_construction_pc"] * 4
                != int(spec["candidate_return_file_offset_hex"], 16)):
                raise ValueError("LotteryRewardItem: PC/file-offset inconsistency")
            record["candidate_instructions_not_execution_proof"] = [
                raw_instruction(proto.code[pc], pc, proto.code_offset) for pc in pcs
            ]
        found[name] = record
    return found


def analyze(main_blua: bytes, anchors: dict) -> dict:
    digest = require_exact_build(main_blua, anchors)
    root = parse_chunk(main_blua)
    matches = verify_anchor_prototypes(root, anchors)
    return {
        "status": "EXACT_VIOLET_400_STATIC_ANCHORS_RECHECKED",
        "sha256": digest,
        "methods": matches,
        "candidate_pc475_is_proven_safe_injection_site": False,
        "bytecode_rewrite_completed": False,
        "runtime_hook_installed": False,
        "retail_reward_prefix_retained_on_hardware": "NOT_TESTED",
        "subject5_item_received_on_hardware": "NOT_TESTED",
        "save_reload_verified": "NOT_TESTED",
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("main_blua", type=Path, help="original Violet 4.0.0 main.blua")
    p.add_argument("--anchors", type=Path, default=DEFAULT_ANCHORS)
    p.add_argument("--output", type=Path)
    a = p.parse_args(argv)
    try:
        anchors = json.loads(a.anchors.read_text(encoding="utf-8"))
        data = a.main_blua.read_bytes()
        report = analyze(data, anchors)
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        print(f"Violet 4.0.0 anchor gate refused: {exc}", file=sys.stderr)
        return 2
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if a.output:
        a.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
