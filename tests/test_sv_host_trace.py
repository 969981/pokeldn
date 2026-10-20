"""N0/N1 read-only evidence parser tests; no Switch, network or memory writes."""

from hashlib import sha256
import json
import struct

import pytest

from pokeldn.sv import host_trace, lz4


def make_point(rows):
    point = bytearray(host_trace.POINT_SIZE)
    point[:len(b"RaidPoint_HOST_TEST")] = b"RaidPoint_HOST_TEST"
    for index, row in enumerate(rows):
        struct.pack_into("<4I", point, 0xE4 + index * 16, *row)
    return bytes(point)


def as_application(point):
    plain = bytes(host_trace.POINT_START) + point
    assert len(plain) == 0xAA0
    envelope = b"\x80\x33\x2f\x01" + struct.pack("<HII", 0x13, 2, 0xAA0) + bytes(4)
    return plain, envelope + lz4.compress(plain)


def test_all_three_binary_shapes_decode_same_point():
    rows = [(1127, 1, 0, 0), (1867, 2, 0, 4), (1867, 3, 0, 5)]
    point = make_point(rows)
    plain, app = as_application(point)
    for kind, data in (("point", point), ("bootstrap", plain), ("application", app)):
        report = host_trace.inspect(data, kind)
        assert report["rows"] == [list(row) for row in rows]
        assert report["point_sha256"] == sha256(point).hexdigest()
        assert report["active_count"] == 3
        assert report["free_slots"] == 42
        assert report["subject_counts"] == {"0": 1, "4": 1, "5": 1}
        assert report["warnings"] == []


def test_holes_and_bad_selector_are_flagged_not_silently_removed():
    point = bytearray(make_point([(1127, 1, 0, 0)]))
    struct.pack_into("<4I", point, 0xE4 + 2 * 16, 1128, 3, 0, 7)
    report = host_trace.inspect(bytes(point), "point")
    assert len(report["warnings"]) == 2
    assert report["active_count"] == 2


def test_reject_wrong_length_type_and_compression():
    point = make_point([(1127, 1, 0, 0)])
    _, app = as_application(point)
    with pytest.raises(ValueError):
        host_trace.inspect(point[:-1], "point")
    with pytest.raises(ValueError):
        host_trace.inspect(b"\x80\x33\x2e\x01" + app[4:], "application")
    with pytest.raises(ValueError):
        host_trace.inspect(app[:6] + struct.pack("<I", 0) + app[10:], "application")


def manifest_for(tmp_path, rows):
    point = make_point(rows)
    plain, app = as_application(point)
    paths = {"P0": ("rows", "p0.json", json.dumps([list(x) for x in rows]).encode()),
             "P1": ("point", "p1.bin", point),
             "P2": ("bootstrap", "p2.bin", plain),
             "P3": ("application", "p3.bin", app)}
    specs = []
    for stage, (kind, file, data) in paths.items():
        (tmp_path / file).write_bytes(data)
        specs.append({"stage": stage, "kind": kind, "file": file, "sha256": sha256(data).hexdigest()})
    return {"format": host_trace.FORMAT, "session_id": "controlled-example-only",
            "title_id": "01008F6008C5E000", "build_id": "TEST-NO-HARDWARE",
            "game_version": "4.0.0", "checkpoints": specs}


def test_four_stages_match_and_do_not_claim_real_hardware(tmp_path):
    rows = [(1127, 1, 0, 0), (1867, 2, 0, 5)]
    report = host_trace.correlate(manifest_for(tmp_path, rows), tmp_path)
    assert report["status"] == "SNAPSHOTS_MATCH_NOT_HARDWARE_PROVEN"
    assert report["comparisons"] == {"P0_to_P1": True, "P1_to_P2": True, "P2_to_P3": True}
    assert not report["missing_stages"]


def test_catches_changed_sent_reward_even_with_updated_checksum(tmp_path):
    manifest = manifest_for(tmp_path, [(1127, 1, 0, 0)])
    changed = make_point([(1127, 1, 0, 0), (15, 1, 0, 5)])
    _, app = as_application(changed)
    (tmp_path / "p3.bin").write_bytes(app)
    manifest["checkpoints"][-1]["sha256"] = sha256(app).hexdigest()
    report = host_trace.correlate(manifest, tmp_path)
    assert report["status"] == "MISMATCH_OR_LAYOUT_WARNING"
    assert report["comparisons"]["P2_to_P3"] is False


def test_incomplete_traces_are_not_called_complete(tmp_path):
    manifest = manifest_for(tmp_path, [(1127, 1, 0, 0)])
    manifest["checkpoints"] = manifest["checkpoints"][0:2]
    report = host_trace.correlate(manifest, tmp_path)
    assert report["status"] == "PENDING_CAPTURE"
    assert report["missing_stages"] == ["P2", "P3"]


def test_rejects_invalid_identity_and_checksum(tmp_path):
    manifest = manifest_for(tmp_path, [(1127, 1, 0, 0)])
    manifest["build_id"] = ""
    with pytest.raises(ValueError, match="build_id"):
        host_trace.correlate(manifest, tmp_path)
    manifest["build_id"] = "TEST"
    manifest["checkpoints"][0]["sha256"] = "f" * 64
    with pytest.raises(ValueError, match="checksum"):
        host_trace.correlate(manifest, tmp_path)


def test_rows_json_schema_validation():
    for bad in (b"{}", b"[[1,2,3]]", b"[[true,2,0,5]]", b"[[1,-1,0,5]]"):
        with pytest.raises(ValueError):
            host_trace.inspect(bad, "rows")
