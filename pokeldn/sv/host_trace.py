"""Read-only Scarlet/Violet host RaidPoint / bootstrap trace correlation.

No runtime Hook, memory writes, packet transmission, or inventory edits.
The fields match pokeldn.sv.raid, NOT the historical donor-era descriptions.
"""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import struct

from pokeldn.sv import lz4

POINT_SIZE = 0x3E8
RAW_SIZE = 0xAA0
POINT_START = 0x6B8
REWARD_START = 0xE4
REWARD_END = 0x3B4
ROW_SIZE = 16
ROW_COUNT = (REWARD_END - REWARD_START) // ROW_SIZE  # 45
FORMAT = "pokeldn.host.reward-trace.v1"
STAGES = ("P0", "P1", "P2", "P3")
KINDS = ("rows", "point", "bootstrap", "application")
ROW = struct.Struct("<4I")


def digest(raw):
    return sha256(raw).hexdigest()


def active_rows_from_point(point):
    """(ordered nonempty rows, warnings); never alters or normalizes the original bytes."""
    if len(point) != POINT_SIZE:
        raise ValueError(f"RaidPoint must be 0x{POINT_SIZE:X} bytes; got {len(point)}")
    name = point[:24].split(b"\x00", 1)[0]
    if not name.startswith(b"RaidPoint_") or not name.isascii():
        raise ValueError("RaidPoint identifier invalid")
    all_rows = [ROW.unpack_from(point, REWARD_START + i * ROW_SIZE)
                for i in range(ROW_COUNT)]
    populated = []
    warnings = []
    empty_seen = False
    for i, row in enumerate(all_rows):
        if row == (0, 0, 0, 0):
            empty_seen = True
            continue
        if empty_seen:
            warnings.append(f"nonempty row after empty slot: index={i}")
        if row[0] == 0 or row[1] == 0:
            warnings.append(f"incomplete reward row: index={i}")
        if row[3] > 5:
            warnings.append(f"unrecognized subject: index={i}, value={row[3]}")
        populated.append(row)
    return populated, warnings


def point_from_blob(data, kind):
    """Unwrap an already reassembled application (outer Pia zlib handled separately)."""
    if kind == "point":
        point = bytes(data)
    elif kind in ("bootstrap", "application"):
        if kind == "application":
            if len(data) < 19 or data[:4] != b"\x80\x33\x2f\x01":
                raise ValueError("expected complete 0x3380/0x2F application (0x012F)")
            flags, uncompressed_size = struct.unpack_from("<II", data, 6)
            if flags != 2 or uncompressed_size != RAW_SIZE:
                raise ValueError("unexpected application compression/length")
            data = lz4.decompress(data[0x12:], RAW_SIZE)
        if len(data) != RAW_SIZE:
            raise ValueError(f"bootstrap must be 0x{RAW_SIZE:X} bytes; got {len(data)}")
        point = bytes(data[POINT_START:POINT_START + POINT_SIZE])
    else:
        raise ValueError(f"unsupported binary snapshot kind: {kind}")
    if len(point) != POINT_SIZE:
        raise ValueError("truncated RaidPoint")
    return point


def parse_rows(data):
    """P0 export: a UTF-8 JSON array of [item, quantity, rare, subject] rows."""
    payload = json.loads(data)
    if not isinstance(payload, list) or len(payload) > ROW_COUNT:
        raise ValueError("P0 rows must be a JSON array containing at most 45 rows")
    rows = []
    for row in payload:
        if (not isinstance(row, list) or len(row) != 4 or
                any(type(x) is not int or x < 0 or x > 0xFFFFFFFF for x in row)):
            raise ValueError("row must contain four unsigned 32-bit integers")
        rows.append(tuple(row))
    return rows


def inspect(data, kind):
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    if kind == "rows":
        rows = parse_rows(data)
        point_hash = None
        warnings = []
        for i, row in enumerate(rows):
            if row[0] == 0 or row[1] == 0 or row[3] > 5:
                warnings.append(f"suspicious P0 row: index={i}")
    else:
        point = point_from_blob(data, kind)
        rows, warnings = active_rows_from_point(point)
        point_hash = digest(point)
    packed = b"".join(ROW.pack(*row) for row in rows)
    return {
        "kind": kind,
        "blob_sha256": digest(data),
        "point_sha256": point_hash,
        "rows_sha256": digest(packed),
        "active_count": len(rows),
        "free_slots": ROW_COUNT - len(rows),
        "subject_counts": dict(sorted(Counter(str(r[3]) for r in rows).items())),
        "rows": [list(r) for r in rows],
        "warnings": warnings,
    }


def correlate(manifest, base_dir):
    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
        raise ValueError("unknown trace manifest format")
    for key in ("session_id", "title_id", "build_id", "game_version"):
        if not isinstance(manifest.get(key), str) or not manifest[key].strip():
            raise ValueError(f"missing {key}; session and build identity are mandatory")
    specs = manifest.get("checkpoints")
    if not isinstance(specs, list):
        raise ValueError("checkpoints must be an array")
    snapshots = {}
    for spec in specs:
        if not isinstance(spec, dict):
            raise ValueError("checkpoint must be a mapping")
        stage, kind, file = (spec.get("stage"), spec.get("kind"), spec.get("file"))
        if stage not in STAGES or stage in snapshots:
            raise ValueError(f"invalid or duplicate stage: {stage!r}")
        if kind not in KINDS or not isinstance(file, str) or not file:
            raise ValueError("invalid checkpoint kind/file")
        if stage == "P0" and kind != "rows":
            raise ValueError("P0 must be a rows JSON export from producer")
        if stage == "P1" and kind != "point":
            raise ValueError("P1 must be a raw RaidPoint snapshot")
        if stage == "P2" and kind != "bootstrap":
            raise ValueError("P2 must be a complete 0xAA0 bootstrap plaintext")
        if stage == "P3" and kind != "application":
            raise ValueError("P3 must be a complete 0x012F application after reassembly")
        raw = (Path(base_dir) / file).read_bytes()
        snap = inspect(raw, kind)
        expected = spec.get("sha256")
        if expected is not None and (not isinstance(expected, str) or
                                     snap["blob_sha256"] != expected.lower()):
            raise ValueError(f"source checksum mismatch at {stage}")
        snapshots[stage] = snap
    comparisons = {}
    for left, right in zip(STAGES, STAGES[1:]):
        if left in snapshots and right in snapshots:
            a, b = snapshots[left], snapshots[right]
            matches = a["rows_sha256"] == b["rows_sha256"]
            if left != "P0":
                matches = matches and a["point_sha256"] == b["point_sha256"]
            comparisons[f"{left}_to_{right}"] = matches
    all_present = all(stage in snapshots for stage in STAGES)
    has_warnings = any(snap["warnings"] for snap in snapshots.values())
    if not all_present:
        status = "PENDING_CAPTURE"
    elif has_warnings or not all(comparisons.values()):
        status = "MISMATCH_OR_LAYOUT_WARNING"
    else:
        status = "SNAPSHOTS_MATCH_NOT_HARDWARE_PROVEN"
    return {
        "format": FORMAT,
        "session_id": manifest["session_id"],
        "identity": {k: manifest[k] for k in ("title_id", "build_id", "game_version")},
        "status": status,
        "missing_stages": [s for s in STAGES if s not in snapshots],
        "comparisons": comparisons,
        "snapshots": snapshots,
        "note": "Offline snapshot consistency only; source authenticity, live Hook and Bag persistence unproven",
    }


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="command", required=True)
    view = commands.add_parser("inspect", help="inspect a raw snapshot without changing it")
    view.add_argument("--kind", choices=KINDS, required=True)
    view.add_argument("--input", type=Path, required=True)
    comparison = commands.add_parser("correlate", help="compare P0 -> P3 evidence")
    comparison.add_argument("--manifest", type=Path, required=True)
    args = cli.parse_args(argv)
    try:
        if args.command == "inspect":
            report = inspect(args.input.read_bytes(), args.kind)
        else:
            report = correlate(json.loads(args.manifest.read_text(encoding="utf-8")), args.manifest.parent)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        cli.exit(2, f"trace error: {exc}\n")
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
