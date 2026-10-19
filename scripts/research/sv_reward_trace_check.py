"""Compare host SV raid reward trace JSONL with separately collected receiver observations.

Without real receiver events the result is always PENDING_RECEIVER; a matching
fixture is not proof that a retail Switch actually ran the corresponding code.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pokeldn.sv.raid_reward_trace import REWARD_SIZE, ROW


def read_jsonl(path):
    events = []
    with open(path, encoding="utf-8") as inp:
        for number, line in enumerate(inp, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict) or not isinstance(record.get("run_id"), str):
                raise ValueError(f"{path}:{number}: expected JSON object with run_id")
            if not isinstance(record.get("event"), str):
                raise ValueError(f"{path}:{number}: missing event")
            events.append(record)
    return events


def rows_from_snapshot(record):
    """Independently re-encode sparse rows and verify the reported 720 B SHA."""
    if record.get("data_len") not in (1000, 2720):
        raise ValueError("snapshot must represent a 1000-byte RaidPoint or 2720-byte Bootstrap")
    result = [(0, 0, 0, 0) for _ in range(45)]
    seen = set()
    entries = record.get("row_entries")
    if not isinstance(entries, list):
        raise ValueError("missing row_entries")
    for entry in entries:
        if not isinstance(entry, list) or len(entry) != 5:
            raise ValueError("row_entries must contain [index,item,quantity,rare,subject]")
        index, *values = entry
        if type(index) is not int or not 0 <= index < 45 or index in seen:
            raise ValueError(f"duplicate or invalid reward row index: {index}")
        if any(type(v) is not int or not 0 <= v <= 0xFFFFFFFF for v in values):
            raise ValueError(f"invalid u32 reward fields at row {index}")
        seen.add(index)
        if values == [0, 0, 0, 0]:
            raise ValueError("zero row must be omitted from sparse row_entries")
        result[index] = tuple(values)
    if record.get("row_count") != len(entries):
        raise ValueError("row_count does not match row_entries")
    raw = b"".join(ROW.pack(*row) for row in result)
    assert len(raw) == REWARD_SIZE
    digest = hashlib.sha256(raw).hexdigest()
    if record.get("rows_sha256") != digest:
        raise ValueError("rows_sha256 does not agree with encoded row_entries")
    return result


def expected_filter(rows, eligibility):
    """Model supported by documented older Lua and existing 4.0.0 research, not live capture."""
    if not isinstance(eligibility, dict):
        raise ValueError("missing eligibility inputs")
    def flag(name):
        value = eligibility.get(name)
        if type(value) is not bool:
            raise ValueError(f"eligibility.{name} must be a boolean")
        return value

    is_host = flag("is_host")
    once = flag("once_eligible")
    charm = flag("has_glimmering_charm")
    power = eligibility.get("raid_power_level")
    if type(power) is not int or not 0 <= power <= 3:
        raise ValueError("eligibility.raid_power_level must be 0..3")
    match = flag("matching_raid_power")
    selected = []
    subject4_index = 0
    for item, count, rare, subject in rows:
        if (item, count, rare, subject) == (0, 0, 0, 0):
            continue
        keep = (
            subject == 0 or
            (subject == 1 and is_host) or
            (subject == 2 and not is_host) or
            (subject == 3 and once) or
            (subject == 4 and match and subject4_index < power) or
            (subject == 5 and charm)
        )
        if subject == 4:
            subject4_index += 1
        if keep:
            selected.append([item, count, rare, subject])
    return selected


def compare_session(events):
    """Return a status; actual hardware provenance still requires manual corroboration."""
    out = {"run_id": events[0]["run_id"], "status": "PENDING_RECEIVER", "details": []}
    sources = [e for e in events if e["event"] == "S1_SOURCE"]
    if len(sources) != 1 or sources[0].get("capture_origin") != "pokeldn_host":
        out.update(status="HOST_TRACE_INCOMPLETE", details=["expected exactly one host S1_SOURCE"])
        return out
    try:
        source_rows = rows_from_snapshot(sources[0])
    except ValueError as exc:
        out.update(status="SOURCE_WRONG", details=[str(exc)])
        return out
    hosts = [e for e in events if e["event"] == "S2_HOST_BOOTSTRAP"]
    if not hosts:
        out.update(status="HOST_TRACE_INCOMPLETE", details=["no S2_HOST_BOOTSTRAP"])
        return out
    for host in hosts:
        station = host.get("station_index")
        if host.get("capture_origin") != "pokeldn_host":
            out.update(status="HOST_TRACE_INCOMPLETE", details=["wrong origin for host event"])
            return out
        try:
            rows = rows_from_snapshot(host)
        except ValueError as exc:
            out.update(status="COPY_MISMATCH", details=[str(exc)])
            return out
        if rows != source_rows or host.get("stage_result") != "MATCH_S1":
            out.update(status="COPY_MISMATCH", details=[f"host stage mismatch station={station}"])
            return out
        loopback = [e for e in events if e["event"] == "S2_WIRE_LOOPBACK"
                    and e.get("station_index") == station]
        if len(loopback) != 1 or loopback[0].get("stage_result") != "MATCH_S2_HOST":
            out.update(status="TRANSPORT_OR_PARSE_MISMATCH",
                       details=[f"missing/failed loopback station={station}"])
            return out
        try:
            wire_rows = rows_from_snapshot(loopback[0])
        except ValueError as exc:
            out.update(status="TRANSPORT_OR_PARSE_MISMATCH", details=[str(exc)])
            return out
        if wire_rows != rows:
            out.update(status="TRANSPORT_OR_PARSE_MISMATCH",
                       details=[f"loopback differs station={station}"])
            return out
        receiver = [e for e in events if e["event"] == "S2_RECEIVER_PRE_FILTER"
                    and e.get("station_index") == station]
        s3 = [e for e in events if e["event"] == "S3_FILTERED"
              and e.get("station_index") == station]
        if not receiver or not s3:
            out["details"].append(f"station={station}: real receiver/filter logs missing")
            continue
        if len(receiver) != 1 or len(s3) != 1:
            out.update(status="MISSING_OBSERVATION",
                       details=[f"duplicate receiver/filter events station={station}"])
            return out
        if receiver[0].get("capture_origin") != "receiver_runtime" or s3[0].get("capture_origin") != "receiver_runtime":
            out.update(status="MISSING_OBSERVATION",
                       details=[f"unattributed receiver events station={station}"])
            return out
        try:
            receiver_rows = rows_from_snapshot(receiver[0])
            expected = expected_filter(receiver_rows, s3[0].get("eligibility"))
        except ValueError as exc:
            out.update(status="MISSING_OBSERVATION", details=[f"station={station}: {exc}"])
            return out
        if receiver_rows != wire_rows:
            out.update(status="TRANSPORT_OR_PARSE_MISMATCH",
                       details=[f"receiver rows differ station={station}"])
            return out
        if s3[0].get("actual_rows") != expected:
            out.update(status="FILTER_MISMATCH",
                       details=[f"station={station}: expected={expected!r} actual={s3[0].get('actual_rows')!r}"])
            return out
        out["details"].append(f"station={station}: reported receiver rows and filtered rows match")
    if len(out["details"]) == len(hosts) and all("reported receiver" in d for d in out["details"]):
        # JSONL imports cannot cryptographically prove that a console produced the records.
        out["status"] = "REPORTED_RECEIVER_MATCH_UNVERIFIED"
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="JSONL emitted by POKELDN_SV_REWARD_TRACE")
    parser.add_argument("--receiver", help="separately captured real-console JSONL (optional)")
    parser.add_argument("--json", action="store_true", help="machine-readable summary")
    args = parser.parse_args(argv)
    try:
        events = read_jsonl(args.host)
        if args.receiver:
            events.extend(read_jsonl(args.receiver))
        sessions = {}
        for e in events:
            sessions.setdefault(e["run_id"], []).append(e)
        if not sessions:
            raise ValueError("no session records found")
        reports = [compare_session(batch) for batch in sessions.values()]
        if args.json:
            print(json.dumps(reports, ensure_ascii=False, indent=2))
        else:
            for report in reports:
                print(f"{report['run_id']}: {report['status']}")
                for detail in report["details"]:
                    print(f"  {detail}")
            print("Receiver file provenance is not cryptographically attested by this tool.")
        return 1 if any(r["status"] not in ("PENDING_RECEIVER", "REPORTED_RECEIVER_MATCH_UNVERIFIED")
                        for r in reports) else 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"trace validation error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
