#!/usr/bin/env python3
"""Read-only Violet 4.0.0 main.blua prototype locator.

The tool parses the standard little-endian Lua 5.4 binary chunk used by
Scarlet/Violet, records each Prototype's instruction-array file offset, and
ranks prototypes using constant fingerprints from the publicly decompiled raid
reward chain.

By default it rejects any input whose SHA-256 is not the known retail Violet
4.0.0 main.blua hash. It never rewrites the input.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import struct
from typing import Iterable

EXPECTED_VIOLET_400_SHA256 = (
    "c1a4f4e2625912cf0b739a642a79ba3357df0557a544b92da22a6cb139de2815"
)
EXPECTED_VIOLET_400_ROOT_CHILD_COUNT = 30_829
EXPECTED_VIOLET_400_ROOT_CODE_COUNT = 429_034
MAX_INPUT = 64 * 1024 * 1024
MAX_DEPTH = 512
MAX_PROTOTYPES = 1_000_000

LUA_SIGNATURE = bytes((0x1B, 0x4C, 0x75, 0x61))
LUA_CHECK = bytes((0x19, 0x93, 0x0D, 0x0A, 0x1A, 0x0A))

TAG_NIL = 0
TAG_FALSE = 1
TAG_NUMBER = 3
TAG_SHORT_STRING = 4
TAG_TRUE = 17
TAG_INTEGER = 19
TAG_LONG_STRING = 20


@dataclass(frozen=True)
class Constant:
    tag: int
    value: object | None


@dataclass
class Prototype:
    path: str
    source: str | None
    line_defined: int
    last_line_defined: int
    num_params: int
    is_vararg: int
    max_stack_size: int
    code_offset: int
    code: tuple[int, ...]
    constants: tuple[Constant, ...]
    upvalue_count: int
    children: list["Prototype"] = field(default_factory=list)

    @property
    def strings(self) -> frozenset[str]:
        return frozenset(
            c.value for c in self.constants
            if c.tag in (TAG_SHORT_STRING, TAG_LONG_STRING)
            and isinstance(c.value, str)
        )

    @property
    def integers(self) -> frozenset[int]:
        return frozenset(
            c.value for c in self.constants
            if c.tag == TAG_INTEGER and isinstance(c.value, int)
        )


class Reader:
    def __init__(self, data: bytes):
        if not 0 < len(data) <= MAX_INPUT:
            raise ValueError(f"Lua chunk must be 1..{MAX_INPUT} bytes")
        self.data = data
        self.off = 0
        self.prototype_count = 0

    def need(self, n: int) -> None:
        if n < 0 or self.off > len(self.data) - n:
            raise ValueError(f"truncated Lua chunk at file offset 0x{self.off:X}")

    def read(self, n: int) -> bytes:
        self.need(n)
        out = self.data[self.off:self.off + n]
        self.off += n
        return out

    def u8(self) -> int:
        return self.read(1)[0]

    def u32(self) -> int:
        return struct.unpack("<I", self.read(4))[0]

    def i64(self) -> int:
        return struct.unpack("<q", self.read(8))[0]

    def u64(self) -> int:
        return struct.unpack("<Q", self.read(8))[0]

    def varuint(self) -> int:
        value = 0
        for _ in range(10):
            b = self.u8()
            if value > (0xFFFFFFFFFFFFFFFF >> 7):
                raise ValueError("Lua variable-length integer overflow")
            value = (value << 7) | (b & 0x7F)
            if b & 0x80:
                return value
        raise ValueError("unterminated Lua variable-length integer")

    def count(self, label: str) -> int:
        value = self.varuint()
        if value > 0x7FFFFFFF:
            raise ValueError(f"Lua {label} count is too large")
        return int(value)

    def lua_bytes(self) -> bytes | None:
        encoded = self.varuint()
        if encoded == 0:
            return None
        length = encoded - 1
        if length > 0x7FFFFFFF:
            raise ValueError("Lua string is too large")
        return self.read(int(length))

    def lua_string(self) -> str | None:
        raw = self.lua_bytes()
        if raw is None:
            return None
        return raw.decode("utf-8", errors="backslashreplace")

    def constant(self) -> Constant:
        tag = self.u8()
        if tag in (TAG_NIL, TAG_FALSE, TAG_TRUE):
            value = None if tag == TAG_NIL else tag == TAG_TRUE
        elif tag == TAG_NUMBER:
            value = struct.unpack("<d", self.read(8))[0]
        elif tag == TAG_INTEGER:
            value = self.i64()
        elif tag in (TAG_SHORT_STRING, TAG_LONG_STRING):
            raw = self.lua_bytes()
            if raw is None:
                raise ValueError("string constant used null-string encoding")
            value = raw.decode("utf-8", errors="backslashreplace")
        else:
            raise ValueError(
                f"unsupported Lua 5.4 constant tag 0x{tag:02X} "
                f"at file offset 0x{self.off - 1:X}"
            )
        return Constant(tag, value)

    def prototype(self, path: str, depth: int) -> Prototype:
        if depth > MAX_DEPTH:
            raise ValueError("prototype depth exceeds safety limit")
        self.prototype_count += 1
        if self.prototype_count > MAX_PROTOTYPES:
            raise ValueError("prototype count exceeds safety limit")

        source = self.lua_string()
        line_defined = self.count("line")
        last_line_defined = self.count("line")
        num_params = self.u8()
        is_vararg = self.u8()
        max_stack_size = self.u8()

        code_count = self.count("instruction")
        if code_count > (len(self.data) - self.off) // 4:
            raise ValueError("instruction array is truncated")
        code_offset = self.off
        code = tuple(self.u32() for _ in range(code_count))

        constants = tuple(self.constant() for _ in range(self.count("constant")))

        upvalue_count = self.count("upvalue")
        self.read(upvalue_count * 3)

        child_count = self.count("child prototype")
        proto = Prototype(
            path=path,
            source=source,
            line_defined=line_defined,
            last_line_defined=last_line_defined,
            num_params=num_params,
            is_vararg=is_vararg,
            max_stack_size=max_stack_size,
            code_offset=code_offset,
            code=code,
            constants=constants,
            upvalue_count=upvalue_count,
        )
        for index in range(child_count):
            proto.children.append(self.prototype(f"{path}/{index}", depth + 1))

        self.read(self.count("line-info entry"))

        for _ in range(self.count("absolute-line entry")):
            self.count("instruction index")
            self.count("line")

        for _ in range(self.count("local variable")):
            self.lua_bytes()
            self.count("instruction index")
            self.count("instruction index")

        for _ in range(self.count("upvalue name")):
            self.lua_bytes()

        return proto


def parse_chunk(data: bytes) -> Prototype:
    r = Reader(data)
    if r.read(4) != LUA_SIGNATURE:
        raise ValueError("not a Lua binary chunk")
    if r.u8() != 0x54 or r.u8() != 0:
        raise ValueError("expected standard Lua 5.4 format")
    if r.read(6) != LUA_CHECK:
        raise ValueError("bad Lua conversion-data marker")
    if (r.u8(), r.u8(), r.u8()) != (4, 8, 8):
        raise ValueError("unsupported Lua scalar sizes")
    if r.i64() != 0x5678:
        raise ValueError("unsupported Lua integer byte order")
    if struct.unpack("<d", r.read(8))[0] != 370.5:
        raise ValueError("unsupported Lua number representation")
    r.u8()  # root upvalue count
    root = r.prototype("root", 0)
    if r.off != len(data):
        raise ValueError(
            f"Lua chunk has {len(data) - r.off} trailing bytes at 0x{r.off:X}"
        )
    return root


def walk(root: Prototype) -> Iterable[Prototype]:
    yield root
    for child in root.children:
        yield from walk(child)


FINGERPRINTS = {
    "lottery_reward_item": {
        "strings": {
            "reward_item_00",
            "difficulty_1",
            "subject_type",
            "slot_num",
            "itemID",
            "category",
            "num",
        },
        "integers": set(),
        "description": "FieldRaidJewelry.LotteryRewardItem semantic body",
    },
    "raidpoint_reward_serializer": {
        "strings": {"ItemNo", "ItemNum", "rareType", "subjectType"},
        "integers": set(),
        "description": "RaidMatchingView reward-row writer candidate",
    },
    "battle_reward_filter": {
        "strings": {"ItemNo", "ItemNum", "rareType", "subjectType"},
        "integers": {2481},
        "description": "BattleRewardData.F316... eligibility filter candidate",
    },
    "raid_result_add_item": {
        "strings": {"ItemNo", "ItemNum", "WSYS_COIN_OVERFLOW_NUM"},
        "integers": {2137},
        "description": "GameEventBattleResult.RaidResultAddItem candidate",
    },
}


def candidate_score(proto: Prototype, spec: dict) -> tuple[int, int, list[str], list[int]]:
    wanted_strings = spec["strings"]
    wanted_ints = spec["integers"]
    hit_strings = sorted(wanted_strings & proto.strings)
    hit_ints = sorted(wanted_ints & proto.integers)
    hits = len(hit_strings) + len(hit_ints)
    total = len(wanted_strings) + len(wanted_ints)
    return hits, total, hit_strings, hit_ints


def raw_instruction(word: int, pc: int, base: int) -> dict:
    return {
        "pc": pc,
        "file_offset": base + pc * 4,
        "word": f"{word:08X}",
        "opcode": word & 0x7F,
        "A": (word >> 7) & 0xFF,
        "k": (word >> 15) & 1,
        "B": (word >> 16) & 0xFF,
        "C": (word >> 24) & 0xFF,
        "Bx": (word >> 15) & 0x1FFFF,
        "Ax": (word >> 7) & 0x1FFFFFF,
    }


def analyze_bytes(
    data: bytes,
    *,
    require_violet_400_sha: bool = True,
    include_instructions_for: set[str] | None = None,
) -> dict:
    sha = hashlib.sha256(data).hexdigest()
    if require_violet_400_sha and sha != EXPECTED_VIOLET_400_SHA256:
        raise ValueError(
            "main.blua SHA-256 mismatch: "
            f"{sha}; expected Violet 4.0.0 {EXPECTED_VIOLET_400_SHA256}"
        )

    root = parse_chunk(data)
    is_verified_build = sha == EXPECTED_VIOLET_400_SHA256
    if is_verified_build and (
        len(root.children) != EXPECTED_VIOLET_400_ROOT_CHILD_COUNT
        or len(root.code) != EXPECTED_VIOLET_400_ROOT_CODE_COUNT
    ):
        raise ValueError(
            "verified-hash chunk has unexpected 4.0.0 root shape: "
            f"code={len(root.code)} children={len(root.children)}"
        )

    protos = list(walk(root))
    include_instructions_for = include_instructions_for or set()
    candidate_groups = {}

    for name, spec in FINGERPRINTS.items():
        ranked = []
        for proto in protos:
            hits, total, hit_strings, hit_ints = candidate_score(proto, spec)
            if hits == 0:
                continue
            row = {
                "path": proto.path,
                "source": proto.source,
                "line_defined": proto.line_defined,
                "last_line_defined": proto.last_line_defined,
                "code_offset": proto.code_offset,
                "code_count": len(proto.code),
                "constant_count": len(proto.constants),
                "child_count": len(proto.children),
                "max_stack_size": proto.max_stack_size,
                "fingerprint_hits": hits,
                "fingerprint_total": total,
                "complete_fingerprint": hits == total,
                "matched_strings": hit_strings,
                "matched_integers": hit_ints,
            }
            if name in include_instructions_for:
                row["instructions"] = [
                    raw_instruction(word, pc, proto.code_offset)
                    for pc, word in enumerate(proto.code)
                ]
            ranked.append(row)
        ranked.sort(
            key=lambda x: (
                not x["complete_fingerprint"],
                -x["fingerprint_hits"],
                x["code_count"],
                x["path"],
            )
        )
        candidate_groups[name] = {
            "description": spec["description"],
            "candidates": ranked[:50],
            "complete_candidate_count": sum(
                1 for row in ranked if row["complete_fingerprint"]
            ),
        }

    return {
        "status": (
            "VERIFIED_VIOLET_400"
            if is_verified_build
            else "STRUCTURAL_ONLY_UNVERIFIED_BUILD"
        ),
        "sha256": sha,
        "expected_violet_400_sha256": EXPECTED_VIOLET_400_SHA256,
        "bytes": len(data),
        "root_code_count": len(root.code),
        "root_child_count": len(root.children),
        "expected_violet_400_root_code_count": EXPECTED_VIOLET_400_ROOT_CODE_COUNT,
        "expected_violet_400_root_child_count": EXPECTED_VIOLET_400_ROOT_CHILD_COUNT,
        "prototype_count": len(protos),
        "candidates": candidate_groups,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("main_blua", type=Path)
    parser.add_argument(
        "--allow-unknown-sha",
        action="store_true",
        help="parse a non-4.0.0 chunk for research, but label it unverified",
    )
    parser.add_argument(
        "--dump-candidate",
        action="append",
        choices=sorted(FINGERPRINTS),
        default=[],
        help="include raw decoded instruction fields for that candidate group",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    try:
        data = args.main_blua.read_bytes()
        report = analyze_bytes(
            data,
            require_violet_400_sha=not args.allow_unknown_sha,
            include_instructions_for=set(args.dump_candidate),
        )
    except (OSError, ValueError, struct.error) as exc:
        print(f"locator error: {exc}")
        return 2

    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
