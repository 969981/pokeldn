"""Opt-in, host-side SV raid reward tracing; no packet or game-data modifications.

Set POKELDN_SV_REWARD_TRACE=/path/to/rewards.jsonl to capture independent
source RaidPoint, host Bootstrap and local compressed-message round-trip.
Receiver data MUST be collected separately on an authorized test console.
"""
import hashlib
import json
import logging
import os
import struct
import time
import uuid

POINT_SIZE = 0x3E8
BOOTSTRAP_SIZE = 0xAA0
RAIDPOINT_OFFSET = 0x6B8
REWARD_OFFSET = 0xE4
REWARD_SIZE = 45 * 16
ROW = struct.Struct("<IIII")
ENV_PATH = "POKELDN_SV_REWARD_TRACE"


def reward_region(data):
    """Return 720 raw reward bytes from a RaidPoint or a plain Bootstrap."""
    data = bytes(data)
    if len(data) == POINT_SIZE:
        offset = REWARD_OFFSET
    elif len(data) == BOOTSTRAP_SIZE:
        offset = RAIDPOINT_OFFSET + REWARD_OFFSET
    else:
        raise ValueError(f"expected 0x3E8 RaidPoint or 0xAA0 Bootstrap, got {len(data)} bytes")
    region = data[offset:offset + REWARD_SIZE]
    if len(region) != REWARD_SIZE:
        raise ValueError("incomplete raid reward region")
    return region


def describe(data):
    """Sparse indexed rows plus a digest computed over ALL 45 encoded rows."""
    raw = reward_region(data)
    rows = [ROW.unpack_from(raw, i * ROW.size) for i in range(45)]
    return {
        "data_len": len(data),
        "row_count": sum(row != (0, 0, 0, 0) for row in rows),
        "row_entries": [[i, *row] for i, row in enumerate(rows) if row != (0, 0, 0, 0)],
        "rows_sha256": hashlib.sha256(raw).hexdigest(),
    }


class HostRewardTrace:
    """Per-RaidGroup observational logger; disabled by default.

    Every snapshot is bound to an independent run_id. A failed trace write
    logs a warning but never prevents the raid from running.
    """

    def __init__(self, path, run_id=None):
        self.path = os.fspath(path)
        self.run_id = run_id or uuid.uuid4().hex
        self._source_point = None
        self._disabled = False

    @classmethod
    def from_environment(cls):
        path = os.environ.get(ENV_PATH)
        return cls(path) if path else None

    def _emit(self, event, **fields):
        if self._disabled:
            return
        record = {
            "schema_version": 1,
            "run_id": self.run_id,
            "event": event,
            "t_monotonic_ms": int(time.monotonic() * 1000),
            "capture_origin": "pokeldn_host",
            **fields,
        }
        try:
            with open(self.path, "a", encoding="utf-8") as out:
                out.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        except OSError as exc:
            self._disabled = True
            logging.warning("SV reward trace disabled; cannot write %s: %s", self.path, exc)

    def capture_source(self, point):
        """Called ONLY for the final raid_point() output, not for pre-validation."""
        if self._source_point is not None:
            raise ValueError("one RaidGroup must generate only one source RaidPoint")
        self._source_point = bytes(point)
        self._emit("S1_SOURCE", **describe(point), stage_result="RECORDED")

    def capture_host(self, plain, packed, station_index, decode_message):
        """Observe real pre-send bytes and independently decompress the framed message."""
        plain = bytes(plain)
        source = self._source_point
        matching = source is not None and plain[RAIDPOINT_OFFSET:] == source
        self._emit(
            "S2_HOST_BOOTSTRAP", station_index=station_index, message_kind="0x2f",
            **describe(plain),
            stage_result="MATCH_S1" if matching else "COPY_MISMATCH",
        )
        try:
            decoded = decode_message(packed)
            loopback = decoded == plain
            self._emit(
                "S2_WIRE_LOOPBACK", station_index=station_index, message_kind="0x2f",
                **describe(decoded),
                stage_result="MATCH_S2_HOST" if loopback else "TRANSPORT_OR_PARSE_MISMATCH",
            )
        except (ValueError, struct.error, IndexError) as exc:
            self._emit(
                "S2_WIRE_LOOPBACK", station_index=station_index, message_kind="0x2f",
                stage_result="TRANSPORT_OR_PARSE_MISMATCH", error=type(exc).__name__,
            )
