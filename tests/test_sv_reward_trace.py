"""Read-only reward trace tests: host byte integrity and imported receiver evidence boundaries."""
import hashlib
import importlib.util
import json
import struct
from pathlib import Path

import pytest

from pokeldn.sv import raid, raid_encounter
from pokeldn.sv import raid_reward_trace as trace

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sv_reward_trace_check", ROOT / "scripts" / "research" / "sv_reward_trace_check.py")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def events_from(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def make_trace(path, rewards):
    found = raid_encounter.generate(0xFDAE7B7D)
    observer = trace.HostRewardTrace(path, run_id="isolated-raid-01")
    plain = raid.bootstrap(found, [None] * 4, rewards, on_point=observer.capture_source)
    packed = raid.bootstrap_message(plain)
    observer.capture_host(plain, packed, 1, raid.payload_of)
    return plain, events_from(path)


def test_reward_trace_is_off_unless_opted_in(monkeypatch):
    monkeypatch.delenv(trace.ENV_PATH, raising=False)
    assert trace.HostRewardTrace.from_environment() is None


def test_final_source_and_wire_roundtrip_same_720_bytes(tmp_path):
    path = tmp_path / "rewards.jsonl"
    plain, events = make_trace(path, [(15, 2, 0), (50, 3, 5)])
    assert len(plain) == 0xAA0
    assert [e["event"] for e in events] == [
        "S1_SOURCE", "S2_HOST_BOOTSTRAP", "S2_WIRE_LOOPBACK"]
    assert {e["run_id"] for e in events} == {"isolated-raid-01"}
    assert [e["row_entries"] for e in events] == [
        [[0, 15, 2, 0, 0], [1, 50, 3, 0, 5]]] * 3
    assert len({e["rows_sha256"] for e in events}) == 1
    assert events[1]["stage_result"] == "MATCH_S1"
    assert events[2]["stage_result"] == "MATCH_S2_HOST"
    assert checker.compare_session(events)["status"] == "PENDING_RECEIVER"
    assert hashlib.sha256(plain[0x79C:0xA6C]).hexdigest() == events[0]["rows_sha256"]


@pytest.mark.parametrize("number", [1, 45])
def test_boundary_last_reward_row_is_preserved(tmp_path, number):
    rows = [(15, 1, 0)] * number
    plain, events = make_trace(tmp_path / "rows.jsonl", rows)
    assert events[0]["row_count"] == number
    assert events[1]["row_entries"][-1] == [number - 1, 15, 1, 0, 0]
    assert plain[0xA6C:0xA70] == bytes(4)  # Padding is not a 46th reward.
    assert plain[0xA70:0xA8C] != bytes(28)  # Boss summary remained.
    assert checker.compare_session(events)["status"] == "PENDING_RECEIVER"


def test_duplicate_items_keep_order_and_quantity_without_merging(tmp_path):
    _, events = make_trace(tmp_path / "duplicates.jsonl", [(15, 1, 0), (15, 2, 5), (15, 3, 0)])
    assert events[0]["row_entries"] == [
        [0, 15, 1, 0, 0], [1, 15, 2, 0, 5], [2, 15, 3, 0, 0]]
    assert checker.expected_filter(
        checker.rows_from_snapshot(events[0]),
        {"is_host": False, "once_eligible": False, "has_glimmering_charm": False,
         "raid_power_level": 0, "matching_raid_power": False}
    ) == [[15, 1, 0, 0], [15, 3, 0, 0]]


def test_malformed_snapshot_hash_cannot_pass(tmp_path):
    _, events = make_trace(tmp_path / "bad.jsonl", [(15, 2)])
    events[1]["row_entries"][0][2] = 999
    assert checker.compare_session(events)["status"] == "COPY_MISMATCH"


def test_corrupt_compressed_message_is_not_a_pass(tmp_path):
    path = tmp_path / "corrupt.jsonl"
    found = raid_encounter.generate(0xFDAE7B7D)
    observer = trace.HostRewardTrace(path, run_id="failed-wire")
    plain = raid.bootstrap(found, [None] * 4, [(15, 2)], on_point=observer.capture_source)
    observer.capture_host(plain, b"invalid", 1, raid.payload_of)
    result = checker.compare_session(events_from(path))
    assert result["status"] == "TRANSPORT_OR_PARSE_MISMATCH"


def test_eligibility_model_all_supported_subjects_without_reordering():
    rows = [(15, 1, 0, 0), (16, 1, 0, 1), (17, 1, 0, 2),
            (18, 1, 0, 3), (19, 1, 0, 4), (20, 1, 0, 4),
            (21, 1, 0, 5)]
    host = {"is_host": True, "once_eligible": True, "has_glimmering_charm": True,
            "matching_raid_power": True, "raid_power_level": 1}
    assert checker.expected_filter(rows, host) == [
        [15, 1, 0, 0], [16, 1, 0, 1], [18, 1, 0, 3],
        [19, 1, 0, 4], [21, 1, 0, 5]]
    guest = {**host, "is_host": False, "once_eligible": False,
             "has_glimmering_charm": False, "raid_power_level": 0}
    assert checker.expected_filter(rows, guest) == [[15, 1, 0, 0], [17, 1, 0, 2]]


@pytest.mark.parametrize("charm,expected", [
    (False, [[15, 2, 0, 0]]),
    (True, [[15, 2, 0, 0], [50, 3, 0, 5]]),
])
def test_receiver_import_matching_is_reported_but_not_attested(tmp_path, charm, expected):
    _, events = make_trace(tmp_path / "host.jsonl", [(15, 2, 0), (50, 3, 5)])
    src = events[0]
    receiver = {**src, "event": "S2_RECEIVER_PRE_FILTER",
                "station_index": 1, "capture_origin": "receiver_runtime"}
    filtered = {
        "schema_version": 1, "run_id": src["run_id"], "event": "S3_FILTERED",
        "station_index": 1, "capture_origin": "receiver_runtime",
        "eligibility": {
            "is_host": False, "once_eligible": False,
            "has_glimmering_charm": charm, "raid_power_level": 0,
            "matching_raid_power": False},
        "actual_rows": expected,
    }
    assert checker.compare_session(events + [receiver, filtered])["status"] == \
           "REPORTED_RECEIVER_MATCH_UNVERIFIED"
    filtered["actual_rows"] = []
    assert checker.compare_session(events + [receiver, filtered])["status"] == "FILTER_MISMATCH"


def test_inconsistent_receiver_is_not_accepted(tmp_path):
    _, events = make_trace(tmp_path / "host.jsonl", [(15, 2)])
    changed = bytearray(raid.POINT_SIZE)
    struct.pack_into("<IIII", changed, raid.POINT_REWARDS, 15, 3, 0, 0)
    receiver = {"event": "S2_RECEIVER_PRE_FILTER", "run_id": "isolated-raid-01",
                "capture_origin": "receiver_runtime", "station_index": 1,
                **trace.describe(changed)}
    s3 = {"event": "S3_FILTERED", "run_id": "isolated-raid-01",
          "capture_origin": "receiver_runtime", "station_index": 1,
          "eligibility": {"is_host": False, "once_eligible": False,
                          "has_glimmering_charm": False, "raid_power_level": 0,
                          "matching_raid_power": False},
          "actual_rows": [[15, 3, 0, 0]]}
    assert checker.compare_session(events + [receiver, s3])["status"] == \
           "TRANSPORT_OR_PARSE_MISMATCH"


def test_research_group_integrates_opt_in_capture(tmp_path, monkeypatch):
    path = tmp_path / "group.jsonl"
    monkeypatch.setenv(trace.ENV_PATH, str(path))
    found = raid_encounter.generate(0xFDAE7B7D)
    group = raid.RaidGroup(found, raid.empty_participant(), rewards=[(15, 2, 0), (50, 3, 5)])
    a = group.bootstrap()
    b = group.bootstrap()
    assert a is b
    assert [e["event"] for e in events_from(path)] == ["S1_SOURCE"]
    group.reward_trace.capture_host(a, raid.bootstrap_message(a), 1, raid.payload_of)
    assert checker.compare_session(events_from(path))["status"] == "PENDING_RECEIVER"
