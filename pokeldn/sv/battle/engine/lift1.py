"""Lifted battle server functions, batch 1 (moved to their topic module once reviewed)."""

from pokeldn.sv.battle.engine import flatbuffer as fb  # noqa: F401
from pokeldn.sv.battle.engine.containers import data_record
from pokeldn.sv.battle.engine.data import static_table
from pokeldn.sv.battle.machine import Pair, UnliftedCall, lifted  # noqa: F401


@lifted(0x10E244C)
def set_id_byte(m, p, ident, b, *_):
    m.put(p, 4, ident); m.put(p + 4, 1, b)


@lifted(0x10E2464)
def clear_id_byte(m, p, *_):
    m.put(p, 4, 0); m.put(p + 4, 1, 10)


@lifted(0x11438A4)
def byte_equals(m, p, v, *_):
    return int(m.u8(p) == v & 0xFF)


@lifted(0x1149604)
def init_0x4b(m, p, *_):
    m.put(p, 8, 0xE00000000); m.put(p + 8, 2, 0); m.put(p + 0x18, 8, 0); m.put(p + 0x10, 4, 0)
    m.put(p + 0x20, 2, 0x9C)
    for o in (0x24, 0x2C, 0x34, 0x3C, 0x43):
        m.put(p + o, 8, 0)


@lifted(0x114B1DC)
def plus_4(m, p, *_):
    return (p + 4) & 0xFFFFFFFFFFFFFFFF


# Index permutation at 0x3c69ef0 (s64 x 14) into the 16-byte entries at 0x44f11c8.
_ORDER_3C69EF0 = (0, 1, 2, 3, 4, 5, 7, 6, 8, 9, 10, 11, 12, 13)


@lifted(0x114C070)
def entry_44f11d0(m, i, *_):
    i &= 0xFFFFFFFF
    if i > 0xD:
        return 0
    return m.u64(m.main + 0x44F11D0 + _ORDER_3C69EF0[i] * 0x10)


@lifted(0x1150ED0)
def state_is_1(m, o, *_):
    return int(m.u32(o + 0x70) == 1)


@lifted(0x11531D4)
def grid_entry(m, o, row, col, *_):
    """Tail call into 0x1723914 on [[o+0x10]+0x210]: entry (row < 4, signed col <= 4) of a 4x5 grid at +0x30."""
    base = m.u64(m.u64(o + 0x10) + 0x210)
    row &= 0xFF; col &= 0xFFFFFFFF
    if row > 3 or (col if col < 0x80000000 else col - (1 << 32)) > 4:
        return 0
    return m.u64((base + row * 0x28 + col * 8 + 0x30) & 0xFFFFFFFFFFFFFFFF)


@lifted(0x1380C4C)
def clear_0x19(m, p, *_):
    m.put(p + 0x18, 1, 0); m.put(p, 8, 0); m.put(p + 8, 8, 0); m.put(p + 0x10, 8, 0)


@lifted(0x13DF9D4)
def side_slot(m, o, side, i, *_):
    side &= 0xFF; i &= 0xFFFFFFFF
    si = i if i < 0x80000000 else i - (1 << 32)
    if si > 0x12 or side > 1:
        return 0
    return (m.u64(o + 0x90) + side * 0x2F8 + i * 0x28 + 8) & 0xFFFFFFFFFFFFFFFF


@lifted(0x1533CA0)
def percent_round(m, a, b, *_):
    """a * b / 100 (32-bit), rounded half up."""
    v = (a * b) & 0xFFFFFFFF
    q, r = divmod(v, 100)
    return q + 1 if r > 0x31 else q


# Battle mode 0, 1, 2 -> five-entry tables (0x3c6a450, 0x3c6a455, 0x3c6a45a).
_MODE_TABLES = {0: (0, 1, 2, 2, 2), 1: (0, 1, 0, 1, 2), 2: (0, 1, 0, 0, 0)}


@lifted(0x1142ECC)
def same_mode_class(m, o, a, b, *_):
    """Whether keys a and b fall in the same class under the setup's battle mode (+0x36c)."""
    a &= 0xFF; b &= 0xFF
    t = _MODE_TABLES.get(m.u32(m.u64(o + 8) + 0x36C))
    ca = t[a] if t and a < 5 else 2
    cb = t[b] if t and b < 5 else 2
    return int(ca == cb)


@lifted(0x1380EA4)
def record_field18_byte(m, o, i, *_):
    """Byte i of the 3-byte entry in field 18 of the data record for the u16 id at o+8; 0 when i > 2."""
    i &= 0xFF
    if i > 2:
        return 0
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    rec = data_record(m, table, m.u16(o + 8))
    off = m.u16(rec - m.s(rec, 4) + 0x28)   # read without the vtable size check, as the game does
    return m.u8(rec + off + 3 * i)


@lifted(0x1794040)
def pack_kind_1(m, a, b, c, *_):
    return Pair(a & 0xFFFFFFFF, ((c & 0xFFFF) << 9) | ((b << 3) & 0x1F8) | 1)


@lifted(0x1794970)
def pack_kind_4(m, a, b, c, *_):
    return Pair(a & 0xFFFFFFFF, ((b & 0xFFFFFFFF) << 26) | ((c & 0x3F) << 3) | 4)


@lifted(0x28616B0)
def pack_kind_2(m, a, b, *_):
    return Pair(a & 0xFFFFFFFF, ((b << 3) & 0x1F8) | 2)


@lifted(0x171A7EC)
def tenth(m, v, *_):
    return (v & 0xFFFF) // 10


@lifted(0x2A10D80)
def nothing(m, *_):
    return


@lifted(0x2D174A0)
def kind_1_44fa3c0(m, out, *_):
    m.put(out, 4, 1)
    return m.main + 0x44FA3C0


@lifted(0x2D10C60)
def kind_1_44f40d0(m, out, *_):
    m.put(out, 4, 1)
    return m.main + 0x44F40D0


@lifted(0x2888AB8)
def count_reached(m, o, *_):
    return int((m.u32(o + 0x10) >> 3 & 0x3F) <= m.u32(o + 0x1C))


@lifted(0x284D154)
def set_word_48(m, o, i, v, *_):
    m.put(o + (i & 0xFF) * 4 + 0x48, 4, v)


def _copy_0x24(m, dst, src, *_):
    m.write(dst, m.read(src, 0x24))
    return dst


lifted(0x287ECA8)(_copy_0x24)
lifted(0x28800B8)(_copy_0x24)


@lifted(0x2888170)
def set_word_4(m, o, i, v, *_):
    """Word i from +4 when i is below the count in bits 7..13 of the u16 at +2."""
    i &= 0xFF
    if i < (m.u16(o + 2) >> 7 & 0x7F):
        m.put(o + i * 4 + 4, 4, v)


@lifted(0x284DCD0)
def entry_44f3f98(m, i, *_):
    i &= 0xFFFFFFFF
    return m.u64(m.main + 0x44F3F98 + i * 0x10) if i < 0x13 else 0


@lifted(0x1769890)
def max_s32(m, a, b, *_):
    sa = m_s32(a); sb = m_s32(b)
    return (b if sa < sb else a) & 0xFFFFFFFF


def m_s32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


@lifted(0xE7E3C8)
def entry_0x38(m, o, i, *_):
    i &= 0xFFFFFFFF
    return (o + i * 0x38 + 0x28) & 0xFFFFFFFFFFFFFFFF if i < 5 else 0


def _owner_id(m, o, slot):
    """The u32 id (+0xc) of the object at [[o+0x38]+0x78]+slot, 0 when there is none."""
    p = m.u64(m.u64(m.u64(o + 0x38) + 0x78) + slot)
    return m.u32(p + 0xC) if p else 0


def _mark_pending(m, rec):
    """A record whose state byte (+0xa) is 0 or 1 gets +0xc = 1, and state 1 moves to 2."""
    if not rec or m.u8(rec + 0xA) > 1:
        return 0
    m.put(rec + 0xC, 4, 1)
    if m.u8(rec + 0xA) == 1:
        m.put(rec + 0xA, 1, 2)
    return 1


@lifted(0x2844C10)
def mark_pending_248(m, o, ident, key, *_):
    root = m.u64(m.u64(o + 0x38) + 0x78)
    if _owner_id(m, o, 0x28) != ident & 0xFFFFFFFF:
        return 0
    p = m.u64(root + 0xF8)
    if (m.u32(p + 0xC) if p else 0) & 0xFFFF != key & 0xFFFF:
        return 0
    return _mark_pending(m, m.u64(root + 0x248))


@lifted(0x2D1A5F0)
def mark_pending_298(m, o, ident, *_):
    if _owner_id(m, o, 0x18) == ident & 0xFFFFFFFF:
        _mark_pending(m, m.u64(m.u64(m.u64(o + 0x38) + 0x78) + 0x298))


@lifted(0x17286D0)
def div_or_1(m, a, b, *_):
    a &= 0xFFFFFFFF; b &= 0xFFFFFFFF
    return a // (b or 1)


@lifted(0x184A110)
def packed_index(m, o, *_):
    """The index packed in the u64 at +8: bits 3..8 for kind 3, bits 26..57 (low 32) for kind 4, else 0."""
    v = m.u64(o + 8)
    kind = v & 7
    if kind == 3:
        return v >> 3 & 0x3F
    if kind == 4:
        return v >> 26 & 0xFFFFFFFF
    return 0


@lifted(0x2823478)
def side_flags(m, o, flags, count, code, *_):
    """Falls into 0x2823490 (the mode word [[o+8]+0x36c] is passed and unused): codes 0/1 set
    flags[0] = code, 4 sets 1, 5 sets 0, 3 also sets flags[count+1]; count ends as the entries set."""
    code &= 0xFF
    m.put(count, 1, 0)
    if code <= 1:
        m.put(flags, 1, code); n = 1
    elif code == 5:
        m.put(flags, 1, 0); n = m.u8(count) + 1
    elif code == 4:
        m.put(flags, 1, 1); n = m.u8(count) + 1
    elif code == 3:
        m.put(flags, 1, 0)
        k = (m.u8(count) + 1) & 0xFF
        m.put(count, 1, k)
        m.put(flags + k, 1, 1)
        n = m.u8(count) + 1
    else:
        n = 0
    m.put(count, 1, n)


@lifted(0x2D0E080)
def kind_of_index(m, out, i, *_):
    """(kind, descriptor) for i in 1..4 from 0x3baa850 and the pointers at 0x44f14b0; else (1, 0x44f1448)."""
    j = (i - 1) & 0xFF
    if j > 3:
        m.put(out, 4, 1)
        return m.main + 0x44F1448
    m.put(out, 4, (2, 3, 3, 2)[j])   # 0x3baa850
    return m.u64(m.main + 0x44F14B0 + 8 * j)


@lifted(0x288D990)
def start_or_count(m, o, src, *_):
    n = m.u32(o + 0x20)
    if n == 0:
        m.put(o + 0x1C, 8, 0x100000000)
        m.write(o + 8, m.read(src, 0x10))
        return 1
    limit = m.call(m.main + 0x288FCD8, m.u32(o + 0x18)) & 0xFFFFFFFF
    if n >= limit:
        return 0
    m.put(o + 0x20, 4, m.u32(o + 0x20) + 1)
    return 1


@lifted(0x2888224)
def all_clear_then_25(m, p, *_):
    """1 if any of the 37 bytes from p is set, else the byte at +0x25."""
    if any(m.read(p, 0x25)):
        return 1
    return m.u8(p + 0x25)


@lifted(0x288C730)
def clear_slot(m, o, i, *_):
    """Falls into 0x288c73c on [[o+0x10]+0x70]: clears slot i (signed i <= 13, flag at +0xa8 + 4i)."""
    base = m.u64(m.u64(o + 0x10) + 0x70)
    i &= 0xFFFFFFFF
    if m_s32(i) > 0xD:
        return 0
    flag = (base + i * 4 + 0xA8) & 0xFFFFFFFFFFFFFFFF
    if m.u32(flag) == 0:
        return 0
    a = base + 8 + i * 0x10; b = base + 8 + i * 4; c = base + i * 0x2C
    m.put(a + 0x348, 8, 0); m.put(a + 0x340, 8, 0)
    m.put(b + 0x30, 4, 0); m.put(b + 0x68, 4, 0); m.put(flag, 4, 0)
    m.put(c + 0x108, 4, 0)
    m.put(c + 0xF8, 8, 0); m.put(c + 0x100, 8, 0)
    m.put(c + 0xE8, 8, 0); m.put(c + 0xF0, 8, 0)
    m.put(c + 0xE0, 8, 0)
    return 1


# Stage kinds 1..7 -> the stage bytes at +0x414..+0x41a.
def _stage_byte(kind):
    kind &= 0xFFFFFFFF
    return 0x413 + kind if 1 <= kind <= 7 else None


@lifted(0x2D3D2D0)
def stage_can_move(m, o, kind, up, *_):
    """Whether the signed stage byte can still rise (up > 0: below 12) or fall (above 0)."""
    off = _stage_byte(kind)
    v = m.s(o + off, 1) if off else 0
    return int(v < 0xC) if m_s32(up) > 0 else int(v > 0)


@lifted(0x2D3D48C)
def stage_raise(m, o, kind, n, *_):
    """Raise a stage byte by n (u8), capped at 12; returns the amount added."""
    off = _stage_byte(kind)
    if not off:
        return 0
    v = m.s(o + off, 1)
    if v > 0xB:
        return 0
    r = (0xC - v) if v + (n & 0xFF) > 0xC else n
    r &= 0xFFFFFFFF
    m.put(o + off, 1, r + v)
    return r


def _boost_if_kind(m, o, ident, kind):
    """0x2853510: when the owner id matches and the action kind (0x16962f0) is `kind` with a nonzero
    [[o+0x48]+0x48], tail-calls 0x1353738([o+0x38], 0x34, 0x1333)."""
    if _owner_id(m, o, 0x20) != ident & 0xFFFFFFFF:
        return
    if m.call(m.main + 0x16962F0, o) & 0xFF != kind & 0xFF:
        return
    if m.u32(m.u64(o + 0x48) + 0x48) == 0:
        return
    m.call_void(m.main + 0x1353738, m.u64(o + 0x38), 0x34, 0x1333)


@lifted(0x285A750)
def boost_if_kind_11(m, o, ident, *_):
    _boost_if_kind(m, o, ident, 0x11)


def _tail(m, address, *args):
    """A tail call: the callee's result as it is (None from a void callee)."""
    from pokeldn.sv.battle.machine import FUNCTIONS
    fn = FUNCTIONS.get(address - m.main)
    if fn is None:
        raise UnliftedCall(f"main+0x{address - m.main:x}")
    return fn(m, *args)


def _vtail(m, obj, slot, *args):
    return _tail(m, m.u64(m.u64(obj) + slot), obj, *args)


@lifted(0x15808E4)
def any_1_or_3(m, p, *_):
    """0 if one of the first n (+0x14) words is 1, else 1 if one is 3, else 2; 2 when the flag at
    +0x18 is clear or n is 0."""
    n = m.u32(p + 0x14)
    if m.u8(p + 0x18) == 0 or n == 0:
        return 2
    words = [m.u32(p + 4 * i) for i in range(n)]
    if 1 in words:
        return 0
    return 1 if 3 in words else 2


@lifted(0x1589B18)
def rank_after_others(m, o, i, *_):
    """A byte at +8+i still at 5 (unset) becomes one more than the highest set byte of +8..+0xc."""
    i &= 0xFF
    if i > 4 or m.u8(o + 8 + i) != 5:
        return
    first = m.u8(o + 8)
    cur = 0xFF if first == 5 else first
    for k in range(1, 5):
        b = m.u8(o + 8 + k)
        sc = cur - 0x100 if cur & 0x80 else cur
        if b != 5 and not (sc > b):
            cur = b
    m.put(o + 8 + i, 1, cur + 1)


@lifted(0x1589A40)
def rule_value_290(m, o, key, *_):
    """The setup map's value for `key` ([[o+0x10]+0x290] owner), 0 when absent or above 4."""
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50), key)
    if p == 0:
        return 0
    v = m.s(p, 4)
    return v & 0xFFFFFFFF if v < 5 else 0


@lifted(0x1579420)
def fill_entry(m, o, a, entry, src, *_):
    v = m.u16(src + 2)
    if v == 0xFFFF:
        v = m.call(m.main + 0x1579490, m.u64(o + 8))
    m.put(entry + 0xA, 2, v)
    m.call_void(m.main + 0x1579498, m.u64(o + 0x10), a, entry, src)
    m.put(entry + 4, 1, 0); m.put(entry + 9, 1, 1)


@lifted(0xF74860)
def data_record_f74860(m, table, key, *_):
    return data_record(m, table, key)


@lifted(0x1382AE8)
def record_flag_34(m, o, *_):
    """Field 34 of the data record for the u16 id at o+8, as a bool."""
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    return int(fb.u8(m, data_record(m, table, m.u16(o + 8)), 34) != 0)


@lifted(0x20FB1E0)
def record_field16_pos(m, o, *_):
    """Field 16 (s8) of the data record for the u16 id at o+8, negatives as 0."""
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    rec = data_record(m, table, m.u16(o + 8))
    off = fb.field(m, rec, 16)
    return max(m.s(rec + off, 1), 0) if off else 0


@lifted(0x11416C0)
def mark_all_standing(m, o, *_):
    """Unless the setup flag bit 0x4d2 is set: for every party member still in the battle, vf 0x4b0(1)
    on its battler and command 0x51 (id, 1) on the queue."""
    from pokeldn.sv.battle.engine.containers import battler
    from pokeldn.sv.battle.engine.flow import first_standing, next_standing
    if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x499) >> 2 & 1:
        return
    with m.frame(0x20) as it:
        m.put(it, 8, m.u64(m.main + 0x46E2580) + 0x10)
        m.put(it + 8, 8, m.u64(o + 8)); m.put(it + 0x10, 8, m.u64(o + 0x10))
        m.put(it + 0x18, 2, 0); m.put(it + 0x1A, 1, 1)
        first_standing(m, it)
        with m.frame(8) as out:
            while next_standing(m, it, out):
                b = m.u64(out)
                owner = m.u64(o + 0x20)
                b2 = battler(m, m.u64(m.u64(m.u64(owner + 0x20) + 0x10) + 0x30), m.vcall(b, 0x98))
                m.vcall_void(b2, 0x4B0, 1)
                q = m.u64(owner + 0x18)
                m.call_void(m.main + 0x119AFF0, q, 0x51, m.vcall(b, 0x98) & 0xFFFFFFFF, 1)


@lifted(0x113AF40)
def position_of_side_index(m, mode, rule, side, index, *_):
    """The battle position (0..9) of the index-th position whose client is of side class `side`; 10 if none."""
    from pokeldn.sv.battle.engine.slots import SIDE_CLASS, slot_of_position
    mode &= 0xFFFFFFFF; rule &= 0xFF; side &= 0xFF; index &= 0xFF
    if side > 1 or index > 5:
        return 10
    n = 0
    for pos in range(10):
        slot = slot_of_position(mode, rule, pos)
        cls = SIDE_CLASS[mode][slot] if mode in SIDE_CLASS and slot < 5 else 2
        if cls == side:
            if n == index:
                return pos
            n += 1
    return 10


@lifted(0x1143D84)
def clear_member_list(m, lst, *_):
    m.write(lst, bytes(0x8F))
    m.put(lst + 0x90, 8, 0); m.put(lst + 0x98, 8, 0); m.put(lst + 0xA0, 8, 0); m.put(lst + 0xA8, 2, 0)


@lifted(0x288D228)
def add_u16_8(m, o, n, *_):
    p = m.call(m.main + 0xFA01F0, m.u64(o + 0x10))
    m.put(p + 8, 2, m.u16(p + 8) + n)


@lifted(0x2853340)
def is_last_kind_1(m, o, obj, *_):
    """Whether the u64 at o+8 is kind 1 with index (bits 3..8) one below vf 0x68(obj, [0x46e2700])."""
    n = m.vcall(obj, 0x68, m.u64(m.main + 0x46E2700))
    v = m.u64(o + 8)
    return int(v & 7 == 1 and (v >> 3 & 0x3F) == (n - 1) & 0xFFFFFFFF)


@lifted(0x114D360)
def check_114da8c(m, o, a, *_):
    return m.call(m.main + 0x114DA8C, m.call(m.main + 0x11440E8, m.u64(o + 0x10)), a) & 1


@lifted(0x14A08A4)
def bump_counter(m, o, ident, key, *_):
    """vf 0x780(key, vf 0x778(key) + 1) on the battler `ident`; a count of 0xff wraps to -1."""
    from pokeldn.sv.battle.engine.containers import battler
    b = battler(m, m.u64(m.u64(o + 0x10) + 0x30), ident)
    v = m.vcall(b, 0x778, key & 0xFFFFFFFF) & 0xFF
    return _vtail(m, b, 0x780, key & 0xFFFFFFFF, 0xFFFFFFFF if v == 0xFF else v + 1)


@lifted(0x1360318)
def apply_kind_4(m, o, _a, p, *_):
    """When vf 0x540(4) of the battler at [p] names an entry (0x13813f4), run 0x1361d0c on it, then
    tail-call 0x1361b20(o, [p], byte p+8)."""
    v = m.vcall(m.u64(p), 0x540, 4) & 0xFF
    if v == 0:
        return
    e = m.call(m.main + 0x13813F4, o, v)
    if e == 0:
        return
    m.call_void(m.main + 0x1361D0C, o, e, m.u8(p + 9))
    return _tail(m, m.main + 0x1361B20, o, m.u64(p), m.u8(p + 8))


@lifted(0x12708F4)
def init_action_list(m, o, *_):
    """Constructor of the action list (vtable 0x44ee488): bytes +0x60..+0x84 of each of the 66 entries
    (0x8c bytes from +8) and the count at +0x2420 are zeroed."""
    m.put(o, 8, m.main + 0x44EE488)
    for k in range(0x42):
        m.write(o + 0x68 + 0x8C * k, bytes(0x24))
    m.put(o + 0x2420, 1, 0)


@lifted(0x114358C)
def count_turn_limit(m, o, i, *_):
    """For a live slot i (signed i <= 13, flag at +0xa8 + 4i of [[[o+0x20]+0x10]+0x70]) with a limit
    (0x19375b0 on its +0x348 + 16i entry): count +0x38 + 4i up, 1 when it reaches the limit. Always
    queues command 0x44 (i)."""
    i &= 0xFFFFFFFF
    r = 0
    if m_s32(i) <= 0xD:
        base = m.u64(m.u64(m.u64(o + 0x20) + 0x10) + 0x70)
        if m.u32(base + i * 4 + 0xA8):
            limit = m.call(m.main + 0x19375B0, base + i * 0x10 + 0x348) & 0xFF
            if limit:
                n = (m.u32(base + i * 4 + 0x38) + 1) & 0xFFFFFFFF
                m.put(base + i * 4 + 0x38, 4, n)
                if n >= limit:
                    r = 1
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x44, i)
    return r


@lifted(0x15323D4)
def note_targets(m, o, p, *_):
    """For each of the p[0] + p[1] entries (12 bytes from p+8: id, then byte +4, flags +6): mark the
    id's slot (0x1381420) in row [[[o+0x40]+8]+0x938] of the 0xc4-byte table: +0x25 = 1, +0x26 = 2
    (flag bit 1) or 1 (bit 0) from the first entry of that id with either, +0x27 = the first entry's
    byte (7 when none)."""
    def count():
        return m.u8(p) + m.u8(p + 1)
    if count() == 0:
        return
    t = m.u64(m.u64(o + 0x40) + 8)
    row = t + m.u8(t + 0x938) * 0xC4
    k = 0
    while True:
        ident = m.u32(p + 8 + 0xC * k)
        s = m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), ident) & 0xFF
        m.put(row + 3 * s + 0x25, 1, 1)
        v = 0
        for j in range(max(count(), 1) if count() else 0):
            if m.u32(p + 8 + 0xC * j) == ident:
                f = m.u8(p + 0xE + 0xC * j)
                if f & 2:
                    v = 2; break
                if f & 1:
                    v = 1; break
        m.put(row + 3 * s + 0x26, 1, v)
        v = 7
        for j in range(max(count(), 1) if count() else 0):
            if m.u32(p + 8 + 0xC * j) == ident:
                v = m.u8(p + 0xC + 0xC * j); break
        m.put(row + 3 * s + 0x27, 1, v)
        k += 1
        if k >= count():
            return


@lifted(0x1794478)
def record_field11_byte3(m, o, *_):
    """Byte 3 of field 11 of the data record for the u16 id at o+8 (read without the vtable size check)."""
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    rec = data_record(m, table, m.u16(o + 8))
    return m.u8(rec + m.u16(rec - m.s(rec, 4) + 0x1A) + 3)


@lifted(0x157BD30)
def drop_unmarked_members(m, o, _a, ctx, *_):
    """Walk the member list [ctx+0x18] with its cursor at +0xa8. A member whose id (vf 0x98) is in the
    ten (id, flag) pairs at [ctx+0x10] with the flag clear is removed (0x157bf08) and handed to
    0x287ef48 (when one member was listed or [ctx+8]+0x13 is clear) and 0x158137c. When [ctx+0x20] is
    set and the list was emptied with +0xa7 or +0xa9 set, tail-calls 0x157bf90(0x1143584(o), id, 3)."""
    lst = m.u64(ctx + 0x18)
    if m.u8(lst + 0xA6) == 0:
        return
    m.put(lst + 0xA8, 1, 0)
    while True:
        lst = m.u64(ctx + 0x18)
        i = m.u8(lst + 0xA8)
        if i >= m.u8(lst + 0xA6):
            break
        m.put(lst + 0xA8, 1, i + 1)
        b = m.u64(lst + 8 * i)
        if b == 0:
            break
        ident = m.vcall(b, 0x98) & 0xFFFFFFFF
        pairs = m.u64(ctx + 0x10)
        hit = next((pairs + 8 * k for k in range(10) if m.u32(pairs + 8 * k) == ident), None)
        if hit is None or m.u8(hit + 4):
            continue
        lst = m.u64(ctx + 0x18)
        n = m.u8(lst + 0xA6)
        flag = m.u8(m.u64(ctx + 8) + 0x13)
        m.call_void(m.main + 0x157BF08, lst, b)
        if n < 2 or flag == 0:
            m.call_void(m.main + 0x287EF48, o, m.u64(ctx), b, m.u64(ctx + 0x10))
        m.call_void(m.main + 0x158137C, o, m.u64(ctx), b)
    if m.u64(ctx + 0x20) == 0:
        return
    lst = m.u64(ctx + 0x18)
    if m.u8(lst + 0xA7) == 0 and m.u8(lst + 0xA9) == 0:
        return
    if m.u8(lst + 0xA6):
        return
    x = m.call(m.main + 0x1143584, o)
    return _tail(m, m.main + 0x157BF90, x, m.vcall(m.u64(ctx), 0x98) & 0xFFFFFFFF, 3)


def _filter_members(m, src, pokecon, b, dst, n, ident, keep):
    from pokeldn.sv.battle.engine.flow import add_member
    for i in range(n):
        x = m.u64(src + 8 * i)
        r = m.call(m.main + 0x118AB58, m.u64(pokecon + 0x290), ident, m.vcall(x, 0x98) & 0xFF)
        if x and r & 1 == keep:
            add_member(m, dst, x)


@lifted(0x1532554)
def members_related(m, src, pokecon, b, dst, *_):
    """Fill member list `dst` with the members of `src` that 0x118ab58 relates to battler b; their count."""
    n = m.u8(src + 0xA6)
    ident = m.vcall(b, 0x98) & 0xFF
    clear_member_list(m, dst)
    if n == 0:
        return 0
    _filter_members(m, src, pokecon, b, dst, n, ident, 1)
    return m.u8(dst + 0xA6)


@lifted(0x153268C)
def members_unrelated(m, src, pokecon, b, dst, *_):
    """Fill member list `dst` with the members of `src` that 0x118ab58 does not relate to battler b."""
    clear_member_list(m, dst)
    ident = m.vcall(b, 0x98) & 0xFF
    _filter_members(m, src, pokecon, b, dst, m.u8(src + 0xA6), ident, 0)
    return m.u8(dst + 0xA6)


def _rule_or_0(m, o, key):
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50), key)
    if p == 0:
        return None
    v = m.s(p, 4)
    return v & 0xFFFFFFFF if v < 5 else 0


@lifted(0x114D390)
def drop_raid_actions(m, o, lst, *_):
    """For each kind-1 action of the raid battler (0xf6fc68) in the action list, look up its class
    (setup map, key +0xc; class 5 redirects through 0x1138c38(o, byte +8)); when 0x114d824 gives a
    negative count for it, the battler's actions are removed (0x1148894) and 0x156616c(6, class) runs."""
    raid = m.call(m.main + 0xF6FC68, m.u64(m.u64(o + 0x10) + 0x310))
    if raid == 0 or m.u8(lst + 0x2420) == 0:
        return
    k = 0
    while True:
        e = lst + 8 + 0x8C * k
        if k & 0xFF < m.u8(lst + 0x2420):
            ident = m.u32(e)
            if ident == m.vcall(raid, 0x98) & 0xFFFFFFFF and m.u32(e + 4) == 1:
                v = _rule_or_0(m, o, m.u32(e + 0xC))
                if v is None:
                    cls = 0; v = 0
                else:
                    if v & 0xFF == 5:
                        b = m.call(m.main + 0x1138C38, o, m.u8(e + 8))
                        if b:
                            v = _rule_or_0(m, o, m.vcall(b, 0x98) & 0xFFFFFFFF) or 0
                    cls = v & 0xFF
                if cls != 5:
                    n = m.call(m.main + 0x114D824, m.u64(m.u64(o + 0x10) + 0x310), v)
                    if n & 0x8000:
                        m.call_void(m.main + 0x1148894, lst, m.vcall(raid, 0x98) & 0xFFFFFFFF)
                        m.call_void(m.main + 0x156616C, m.call(m.main + 0x1143584, o), 6, cls)
        k += 1
        if k >= m.u8(lst + 0x2420):
            return


@lifted(0x1143A30)
def set_and_queue_35(m, o, b, a, c, *_):
    """0x1143ab8([o+0x20], id, a, c), then command 0x35 (id, a & 0xff, c & 0xff)."""
    m.call_void(m.main + 0x1143AB8, m.u64(o + 0x20), m.vcall(b, 0x98) & 0xFFFFFFFF, a & 0xFFFFFFFF, c & 0xFFFFFFFF)
    q = m.u64(o + 0x18)
    return _tail(m, m.main + 0x119AFF0, q, 0x35, m.vcall(b, 0x98) & 0xFFFFFFFF, a & 0xFF, c & 0xFF)


@lifted(0x1360480)
def set_and_queue_41(m, o, a, b, *_):
    """0x1360524([o+0x20], id a, id b), then command 0x41 (id a, id b)."""
    x = m.u64(o + 0x20)
    ia = m.vcall(a, 0x98) & 0xFFFFFFFF
    m.call_void(m.main + 0x1360524, x, ia, m.vcall(b, 0x98) & 0xFFFFFFFF)
    q = m.u64(o + 0x18)
    ia = m.vcall(a, 0x98) & 0xFFFFFFFF
    return _tail(m, m.main + 0x119AFF0, q, 0x41, ia, m.vcall(b, 0x98) & 0xFFFFFFFF)


@lifted(0x1148470)
def set_and_queue_20(m, o, b, c, *_):
    """0x11484e4([o+0x20], id, c), then command 0x20 (id, c)."""
    m.call_void(m.main + 0x11484E4, m.u64(o + 0x20), m.vcall(b, 0x98) & 0xFFFFFFFF, c & 0xFFFFFFFF)
    q = m.u64(o + 0x18)
    return _tail(m, m.main + 0x119AFF0, q, 0x20, m.vcall(b, 0x98) & 0xFFFFFFFF, c & 0xFFFFFFFF)


@lifted(0x136078C)
def set_and_queue_6c(m, o, ident, *_):
    m.call_void(m.main + 0x13607C0, m.u64(o + 0x20), ident & 0xFFFFFFFF)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x6C, ident & 0xFFFFFFFF)


@lifted(0x136075C)
def battler_to_1360c00(m, o, ident, *_):
    from pokeldn.sv.battle.engine.containers import battler
    b = battler(m, m.u64(m.u64(o + 0x10) + 0x30), ident)
    return _tail(m, m.main + 0x1360C00, m.u64(o + 0x18), b)


@lifted(0x1360F0C)
def drop_handlers_of(m, o, ident, *_):
    """Remove every kind-0 handler of battler `ident` from the handler table [[[o+0x18]+8]+0xd0]: live
    ones (+0x44) through 0x13608e0, or 0x1360cdc(1) when +0x3f is set; repeats until none is found."""
    from pokeldn.sv.battle.engine.containers import battler, find_handler
    b = battler(m, m.u64(m.u64(o + 0x10) + 0x30), ident)
    owner = m.u64(o + 0x18)
    bid = m.vcall(b, 0x98) & 0xFFFFFFFF
    table = m.u64(m.u64(owner + 8) + 0xD0)
    h = find_handler(m, table, 0, bid)
    while h:
        if m.u8(h + 0x44):
            if m.u8(h + 0x3F) == 0:
                m.call_void(m.main + 0x13608E0, m.u64(m.u64(owner + 8) + 0xD0), h)
            else:
                m.call_void(m.main + 0x1360CDC, h, 1)
        h = find_handler(m, table, 0, bid)


@lifted(0x1381540)
def has_10d3f10(m, a, b=0, *_):
    return int(m.call(m.main + 0x10D3F10, a, b) != 0)


@lifted(0x1793E60)
def run_17942d0_with(m, v, *rest):
    """0x17942d0's result for a stack object (vtable [0x46ddad8] + 0x10, u16 v at +8)."""
    with m.frame(0x10) as f:
        m.put(f, 8, m.u64(m.main + 0x46DDAD8) + 0x10)
        m.put(f + 8, 2, v)
        return m.call(m.main + 0x17942D0, f, *rest[:6])


@lifted(0x288D9F0)
def queue_4a(m, q, a, b, src, *_):
    """Command 0x4a (a & 0xff, b, then the three values 0x174ae90 reads out of `src`)."""
    with m.frame(0x10) as f:
        m.put(f, 8, 0); m.put(f + 8, 4, 0)
        m.call_void(m.main + 0x174AE90, src, f + 4, f, f + 8)
        m.call_void(m.main + 0x119AFF0, q, 0x4A, a & 0xFF, b & 0xFFFFFFFF, m.u32(f + 4), m.u32(f), m.u32(f + 8))


@lifted(0x162B830)
def class_matches_95(m, o, ident, *_):
    """Whether battler `ident`'s class in the setup map equals the byte at [o+8]+0x95."""
    from pokeldn.sv.battle.engine.containers import battler
    b = battler(m, m.u64(m.u64(o + 0x10) + 0x30), ident)
    want = m.u64(o + 8)
    v = _rule_or_0(m, o, m.vcall(b, 0x98) & 0xFFFFFFFF)
    return int((v or 0) == m.u8(want + 0x95))


@lifted(0x1793EFC)
def build_target(m, x0, code, b, out, ctx, *_):
    """Pack a target descriptor for battler b from `code` (kind in bits 0..3, fields at bits 4 and 10)
    into the 16 bytes at `out`."""
    code &= 0xFFFFFFFF
    kind = code & 0xF
    f4, f10 = (code & 0xFFFF) >> 4 & 0x3F, code >> 10 & 0x3F

    def ident():
        return m.vcall(b, 0x98) & 0xFFFFFFFF
    if kind == 2:
        v = m.call(m.main + 0x179405C, ctx, f4, f10)
        r = (ident(), (v & 0x3F) << 3 | 2)
    elif kind == 1:
        r = m.call(m.main + 0x1794040, ident(), f10, f4)
    elif kind == 4:
        a = ident(); c = ident()
        r = m.call(m.main + 0x1794970, a, c, m.call(m.main + 0x179405C, ctx, f4, f10))
    elif kind == 3:
        a = ident()
        r = (a, (ident() & 0x3F) << 3 | 3)
    else:
        r = m.call(m.main + 0x1794120, x0, code, b, out, ctx)
    m.put(out, 8, r[0]); m.put(out + 8, 8, r[1])


@lifted(0x28680A0)
def boost_if_flag_4(m, o, ident, *_):
    """When the owner id matches and the battler named at +0x28 has vf 0x4d0(4), tail-calls
    0x1353738([o+0x38], 0x38, 0x2000)."""
    from pokeldn.sv.battle.engine.containers import battler
    if _owner_id(m, o, 0x20) != ident & 0xFFFFFFFF:
        return
    b = battler(m, m.u64(m.u64(o + 8) + 0x30), _owner_id(m, o, 0x28))
    if m.vcall(b, 0x4D0, 4) & 1:
        return _tail(m, m.main + 0x1353738, m.u64(o + 0x38), 0x38, 0x2000)


@lifted(0x17CE294)
def take_pending_code(m, _o, b, p, *_):
    """Consume the code at p (set to 0, or 6 for code 0x32 while vf 0x230 is nonzero); the result
    depends on the code: 0x31 gives vf 0x230, 0x32 vf 0x230 or 6 when vf 0x220(6), 0x33 0x17ce3c0
    (p kept when nonzero), anything else the code itself when vf 0x220(code)."""
    v = m.vcall(b, 0x230)
    code = m.u32(p)
    if code == 0x32:
        if v & 0xFFFF:
            m.put(p, 4, 6)
            return v
        r = 6 if m.vcall(b, 0x220, 6) & 1 else 0
    elif code == 0x31:
        r = v
    elif code == 0x33:
        r = m.call(m.main + 0x17CE3C0, b)
        if r & 0xFFFF:
            return r
        r = 0
    else:
        r = m.u32(p) if m.vcall(b, 0x220, code) & 1 else 0
    m.put(p, 4, 0)
    return r


_CODES_3C69DC4 = (0x7, 0xC, 0xD, 0xF, 0x17, 0xB)   # u16 x 6 at 0x3c69dc4


@lifted(0x2823BE0)
def code_at(m, i, *_):
    i &= 0xFFFFFFFF
    return _CODES_3C69DC4[i] if i <= 5 else 0


@lifted(0x17CE3C0)
def first_code_held(m, b, *_):
    """The first code of 0x2823be0's list for which vf 0x220 holds; 0 at the end of the list."""
    i = 0
    while True:
        v = m.call(m.main + 0x2823BE0, i) & 0xFFFFFFFF
        i += 1
        if v & 0xFFFF == 0 or m.vcall(b, 0x220, v) & 1:
            return v


@lifted(0x17CE354)
def maybe_114b0ac(m, o, a, p, *_):
    """When 0x17ce3ac(p) holds (bits 0..6 of the byte at p+2), tail-calls 0x114b0ac(0x1143584(o), a, p)."""
    if m.call(m.main + 0x17CE3AC, p) & 1 == 0:
        return
    return _tail(m, m.main + 0x114B0AC, m.call(m.main + 0x1143584, o), a & 0xFFFFFFFF, p)


@lifted(0x2872E70)
def kind_3_2872d60(m, o, a, *_):
    return _tail(m, m.main + 0x2872D60, o, a, 3)


@lifted(0x288DBD0)
def queue_49(m, o, b, src, *_):
    """Command 0x49 (id of b, then id of [src] and the u16 at src+8, or 0, 0 without src)."""
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    other = val = 0
    if src:
        other = m.vcall(m.u64(src), 0x98) & 0xFFFFFFFF
        val = m.u16(src + 8)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x49, ident, other, val)


@lifted(0x1437580)
def set_and_queue_38(m, o, a, *_):
    m.call_void(m.main + 0x14375B4, m.u64(o + 0x20), a & 0xFFFFFFFF)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x38, a & 0xFFFFFFFF)


# Event parameter frames, as the handlers inline them: a pool of 0x60 parameter records (pointers at
# pool + 8 + 32i, u16 kind at +8, used count at pool+0xc08) and a stack of 31 frames (stack+0x408).

def ev_push(m, ctx):
    """Open a frame: claim the next free record as a frame marker (kind 1), make the next frame current."""
    pool = m.u64(ctx + 0x38)
    c = m.u32(pool + 0xC08)
    while c <= 0x5F:
        e = m.u64(pool + 32 * c + 8)
        if m.u16(e + 8) == 0:
            if c <= 0x5E:
                m.put(e + 8, 2, 1)
                m.put(pool + 0xC08, 4, m.u32(pool + 0xC08) + 1)
            break
        c += 1
        m.put(pool + 0xC08, 4, c)
    stk = m.u64(ctx + 0x58)
    n = m.u32(stk + 0x408)
    if n <= 0x1E:
        m.put(stk + 0x408, 4, n + 1)
        stk = m.u64(ctx + 0x58)
        n = m.u32(stk + 0x408)
    m.put(ctx + 0x78, 8, m.u64(stk + 32 * n + 8))


def ev_param(m, ctx, kind, value, typ, slot):
    """Set parameter `kind` of the current frame (reusing a record of that kind above the used count,
    else the first free one) and note it in the frame at `slot`."""
    pool = m.u64(ctx + 0x38)
    i = m.u32(pool + 0xC08)
    while i < 0x60:
        k = m.u16(m.u64(pool + 32 * i + 8) + 8)
        if k == 0 or k == kind:
            break
        i += 1
    else:
        return
    e = m.u64(pool + 32 * i + 8)
    if e == 0:
        return
    m.put(e + 8, 2, kind); m.put(e + 0xC, 4, value); m.put(e + 0xA, 1, typ)
    m.put(e + 0x10, 8, 0); m.put(e + 0x18, 8, 0)
    m.put(m.u64(ctx + 0x78) + slot, 8, e)


def ev_pop(m, ctx):
    """Close the current frame: clear it, release its records back to the frame marker below."""
    stk = m.u64(ctx + 0x58)
    n = m.u32(stk + 0x408)
    if n:
        m.write(m.u64(stk + 32 * n + 8) + 8, bytes(0x430))
        m.put(stk + 0x408, 4, m.u32(stk + 0x408) - 1)
        stk = m.u64(ctx + 0x58)
        n = m.u32(stk + 0x408)
    m.put(ctx + 0x78, 8, m.u64(stk + 32 * n + 8))
    pool = m.u64(ctx + 0x38)
    c = m.u32(pool + 0xC08)
    if c == 0:
        return
    if c & 0xFFFF <= 0x5F:
        j = c & 0xFFFF
        while True:
            e = m.u64(pool + 32 * j + 8)
            if m.u16(e + 8) == 0:
                break
            m.put(e + 8, 2, 0)
            j += 1
            if j & 0xFFFF == 0x60:
                break
        c = m.u32(pool + 0xC08)
    c = (c - 1) & 0xFFFFFFFF
    m.put(pool + 0xC08, 4, c)
    m.put(m.u64(pool + 32 * c + 8) + 8, 2, 0)
    c = m.u32(pool + 0xC08)
    while c:
        c -= 1
        m.put(pool + 0xC08, 4, c)
        if m.u16(m.u64(pool + 32 * c + 8) + 8) == 1:
            m.put(pool + 0xC08, 4, c + 1)
            return


@lifted(0x157E064)
def event_c5(m, o, a, b, _x3, out, *_):
    """Unless vf 0x4e8 of b is 0x20: event 0xc5 with parameters 3 (id a), 4 (id b), 0x24 (that value),
    0x49 (1) and 0x56 ([out]); returns whether parameter 0x49 came back nonzero, [out] gets 0x56's."""
    m.put(out, 1, 1)
    v = m.vcall(b, 0x4E8) & 0xFFFFFFFF
    if v == 0x20:
        return 0
    ev_push(m, m.u64(o + 0x10))
    ctx = m.u64(o + 0x10)
    ev_param(m, ctx, 3, m.vcall(a, 0x98), 4, 0x20)
    ctx = m.u64(o + 0x10)
    ev_param(m, ctx, 4, m.vcall(b, 0x98), 4, 0x28)
    ev_param(m, m.u64(o + 0x10), 0x24, v, 4, 0x128)
    ev_param(m, m.u64(o + 0x10), 0x49, 1, 1, 0x250)
    ev_param(m, m.u64(o + 0x10), 0x56, m.u8(out), 1, 0x2B8)
    m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), 0xC5, 8, 1)
    frame = m.u64(m.u64(o + 0x10) + 0x78)
    p = m.u64(frame + 0x250)
    r = int(p != 0 and m.u32(p + 0xC) != 0)
    p = m.u64(frame + 0x2B8)
    m.put(out, 1, int(p != 0 and m.u32(p + 0xC) != 0))
    ev_pop(m, m.u64(o + 0x10))
    return r


@lifted(0x17776D8)
def event_bc_if_2a8(m, o, _a, p, *_):
    """When vf 0x2a8 of battler [p] is nonzero, tail-calls 0x1777748(0x1146e90(o), battler, byte p+4)."""
    from pokeldn.sv.battle.engine.containers import battler
    b = battler(m, m.u64(m.u64(o + 0x10) + 0x30), m.u32(p))
    if m.vcall(b, 0x2A8) & 0xFFFF == 0:
        return
    return _tail(m, m.main + 0x1777748, m.call(m.main + 0x1146E90, o), b, m.u8(p + 4))


@lifted(0x156616C)
def add_and_queue_85(m, o, kind, n, *_):
    m.call_void(m.main + 0x15661B0, m.u64(o + 0x20), kind & 0xFFFFFFFF, n & 0xFFFFFFFF)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x85, kind & 0xFF, n & 0xFFFFFFFF)


@lifted(0x15660D0)
def first_member_11493a0(m, o, lst, n, *_):
    """Walk the member list; at the first member 0x11493a0 accepts, tail-calls 0x156616c([o+0x20], 7, n)."""
    m.put(lst + 0xA8, 1, 0)
    if m.u8(lst + 0xA6) == 0:
        return
    i = 0
    while True:
        m.put(lst + 0xA8, 1, i + 1)
        b = m.u64(lst + 8 * i)
        if b == 0:
            return
        if m.call(m.main + 0x11493A0, m.u64(o + 0x10), m.vcall(b, 0x98) & 0xFFFFFFFF) & 1:
            return _tail(m, m.main + 0x156616C, m.u64(o + 0x20), 7, n & 0xFFFFFFFF)
        i = m.u8(lst + 0xA8)
        if i >= m.u8(lst + 0xA6):
            return


_CLASS_TABLES = {0: 0x3C6A450, 1: 0x3C6A455, 2: 0x3C6A45A}


@lifted(0x142A758)
def allies_present(m, mode, rule, slot, *_):
    """How many other client slots (0..4) are present (0xe7e2a0) and of the same side class as `slot`."""
    from pokeldn.sv.battle.engine.slots import SIDE_CLASS
    mode &= 0xFFFFFFFF; slot &= 0xFFFFFFFF
    if mode in SIDE_CLASS:
        if slot < 5:
            mine = SIDE_CLASS[mode][slot]
        elif slot >= 0x80000000:   # signed compare: a negative slot indexes the table
            mine = m.u8(m.main + _CLASS_TABLES[mode] + slot)
        else:
            mine = 2
    else:
        mine = 2
    n = 0
    for s in range(5):
        if s == slot:
            continue
        if m.call(m.main + 0xE7E2A0, mode, rule, s) & 1:
            theirs = SIDE_CLASS[mode][s] if mode in SIDE_CLASS else 2
            if theirs == mine:
                n += 1
    return n & 0xFF


def _pokemon_getters():
    from pokeldn.sv.battle.engine.pokemon import _getter
    lifted(0xBF41A8)(_getter(0, 0x1C, 2, 0, 0x4742290, False))     # block A +0x1c (u16)


_pokemon_getters()


@lifted(0x114DC24)
def queue_c1(m, o, a, b, *_):
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xC1, a & 0xFF, b & 0xFFFFFFFF)


@lifted(0x1149478)
def allies_plus_1(m, setup, *_):
    return (m.call(m.main + 0x142A758, m.u32(setup + 0x36C), m.u8(setup + 0x370), 0) & 0xFF) + 1


@lifted(0x171A804)
def set_and_queue_73(m, o, ident, a, b, *_):
    m.call_void(m.main + 0x171A850, m.u64(o + 0x20), ident & 0xFFFFFFFF, a & 0xFFFFFFFF, b & 0xFFFFFFFF)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x73, ident & 0xFFFFFFFF, a & 0xFF, b & 0xFFFF)


@lifted(0x2887F9C)
def count_and_queue_4a(m, o, side, i, src, *_):
    """When 0x288d980(side) holds and slot (side, i) of [o+0x10] accepts the count (0x288d990), queue
    command 0x4a for it; 1 when queued."""
    if m.call(m.main + 0x288D980, side & 0xFFFFFFFF) & 1 == 0:
        return 0
    e = m.call(m.main + 0x13DF9D4, m.u64(o + 0x10), side & 0xFFFFFFFF, i & 0xFFFFFFFF)
    if e == 0:
        return 0
    if m.call(m.main + 0x288D990, e, src) & 1 == 0:
        return 0
    m.call_void(m.main + 0x288D9F0, m.u64(o + 0x18), side & 0xFFFFFFFF, i & 0xFFFFFFFF, src)
    return 1


def _raid_id(m, rec):
    """The raid battler id the record caches at +0x18, looked up once while setup flag 0x4d2 is set."""
    if m.u8(m.u64(m.u64(rec + 8) + 0x38) + 0x499) >> 2 & 1 and m.u32(rec + 0x18) == 0:
        lst = m.call(m.main + 0x14B5634, m.u64(m.u64(rec + 0x10) + 0x30), 1)
        b = m.call(m.main + 0x114C614, lst, 0)
        if b:
            m.put(rec + 0x18, 4, m.vcall(b, 0x98))
    return m.u32(rec + 0x18)


def _class_of(m, o, ident):
    v = _rule_or_0(m, o, ident)
    return 0 if v is None else v


def _next_action_serial(m, o):
    c = m.u64(m.u64(o + 0x10) + 0x190)
    v = m.u32(c + 8)
    if v == 0:
        v = 1
        m.put(c + 8, 4, 1)
    m.put(c + 8, 4, m.u32(c + 8) + 1)
    return v


@lifted(0x114D528)
def raid_extra_actions(m, o, lst, *_):
    """For each side class (0..4) holding a non-raid battler with an action in the list, when 0x114d824
    gives the raid record a positive count for it, append a raid action (kind 0xc, that count as move)
    aimed at that battler and run 0x156616c(6, class)."""
    with m.frame(0x20 + 0x90) as f:
        ids, act = f, f + 0x20
        m.write(ids, bytes(0x14))
        n = m.u8(lst + 0x2420)
        k = 0
        while k < n:
            if k & 0xFF < n:
                e = lst + 8 + 0x8C * k
                ident = m.u32(e)
                rec = m.u64(m.u64(o + 0x10) + 0x310)
                if _raid_id(m, rec) != ident:
                    cls = _class_of(m, o, m.u32(e))
                    m.put(ids + 4 * cls, 4, m.u32(e))
            n = m.u8(lst + 0x2420)
            k += 1
        for cls in range(5):
            target = m.u32(ids + 4 * cls)
            if target == 0:
                continue
            cnt = m.call(m.main + 0x114D824, m.u64(m.u64(o + 0x10) + 0x310), cls) & 0xFFFF
            cnt = cnt - 0x10000 if cnt & 0x8000 else cnt
            if cnt < 1:
                continue
            m.write(act, bytes(0x8C))
            m.put(act + 0x88, 1, 5); m.put(act + 0x84, 4, 0x5400000); m.put(act + 4, 4, 0xC)
            m.put(act + 0x10, 2, cnt)
            m.put(act + 8, 1, m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), target))
            m.put(act + 0xC, 4, target)
            m.put(act + 0x28, 1, 8); m.put(act + 0x2C, 4, 0)
            m.put(act, 4, _raid_id(m, m.u64(m.u64(o + 0x10) + 0x310)))
            raid = _raid_id(m, m.u64(m.u64(o + 0x10) + 0x310))
            m.put(act + 0x88, 1, _class_of(m, o, raid)); m.put(act + 0x89, 2, 0)
            m.put(act + 0x84, 4, m.call(m.main + 0x11514B8, o, act, lst))
            m.put(act + 0x54, 4, _next_action_serial(m, o))
            m.call_void(m.main + 0x1820EB8, lst, act)
            m.call_void(m.main + 0x156616C, m.call(m.main + 0x1143584, o), 6, cls)


@lifted(0x114CE2C)
def raid_actions(m, o, _a, p, *_):
    """The raid battler's turn additions to the action list [p]: drop what 0x114d390 drops; when the raid
    record (+0x8c set, move +0x64 accepted by 0x114d360) has a pending kind-1 action (+0x89 clear) of its
    own, add one more action with one of its moves (vf 0x730) aimed at a battler of the second action
    list [o+0x48]; then the per-class extras (0x114d528)."""
    from pokeldn.sv.battle.engine.containers import battler
    if m.call(m.main + 0x114D34C, m.u64(m.u64(o + 0x10) + 0x310)) & 1 == 0:
        return
    lst = m.u64(p)
    m.call_void(m.main + 0x114D390, o, lst)
    rec = m.u64(m.u64(o + 0x10) + 0x310)
    if m.u8(rec + 0x8C):
        raid = m.call(m.main + 0xF6FC68, rec)
        move = m.u16(m.u64(m.u64(o + 0x10) + 0x310) + 0x64) if raid else 0
        if raid and move and m.call(m.main + 0x114D360, o, move) & 0xFFFFFFFF and m.u8(lst + 0x2420):
            k = 0
            while True:
                e = lst + 8 + 0x8C * k
                if k & 0xFF < m.u8(lst + 0x2420):
                    ident = m.u32(e)
                    if ident == m.vcall(raid, 0x98) & 0xFFFFFFFF and m.u32(e + 4) == 1 \
                            and m.u8(e + 0x89) == 0:
                        _raid_extra_move(m, o, lst, e)
                        break
                k += 1
                if k >= m.u8(lst + 0x2420):
                    break
    return _tail(m, m.main + 0x114D528, o, lst)


def _raid_extra_move(m, o, lst, entry):
    from pokeldn.sv.battle.engine.containers import battler
    with m.frame(0xC0) as f:
        moves, out, req, act = f, f + 0x10, f + 0x18, f + 0x20
        m.write(f + 0x20, bytes(0x24))
        raid = m.call(m.main + 0xF6FC68, m.u64(m.u64(o + 0x10) + 0x310))
        if raid == 0:
            return
        m.put(moves, 2, 0)
        n = 0
        for i in range(4):
            if i:
                m.put(moves + 2 * i, 2, 0)
            if m.vcall(raid, 0x730, i) & 0xFFFF:
                m.put(moves + 2 * n, 2, m.vcall(raid, 0x730, i))
                n += 1
        other = m.u64(o + 0x48)
        if m.u8(other + 0x2420) == 0:
            return
        j = 0
        while True:
            if j & 0xFF < m.u8(other + 0x2420):
                ident = m.u32(other + 8 + 0x8C * j)
                if ident:
                    rec = m.u64(m.u64(o + 0x10) + 0x310)
                    if _raid_id(m, rec) != ident:
                        break
                    other = m.u64(o + 0x48)
            j += 1
            if j >= m.u8(other + 0x2420):
                return
        b = battler(m, m.u64(m.u64(o + 0x10) + 0x30), m.u32(other + 8 + 0x8C * j))
        if b == 0 or m.vcall(b, 0x200) & 1:
            return
        idx = m.call(m.main + 0x11440F0, m.call(m.main + 0x11440E8, m.u64(o + 0x10)), n) & 0xFFFFFFFF
        idx = idx - (1 << 32) if idx & 0x80000000 else idx
        move = m.u16(moves + 2 * idx)
        m.put(req, 4, m.vcall(raid, 0x98)); m.put(req + 4, 2, move)
        m.call_void(m.main + 0x2842270, m.u64(m.u64(o + 0x78) + 0xB40), out, req)
        slot = m.u8(out)
        table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
        flag = fb.u8(m, data_record(m, table, move), 17)
        if flag not in (0, 3):
            target = 0
        else:
            target = m.vcall(b, 0x98) & 0xFFFFFFFF
            slot = m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), m.vcall(b, 0x98) & 0xFFFFFFFF)
        a = f + 0x48
        m.write(a, bytes(0x8C))
        m.put(a + 0x88, 1, 5); m.put(a + 0x84, 4, 0x5400000); m.put(a + 4, 4, 0xC)
        m.put(a + 0x10, 2, move); m.put(a + 8, 1, slot); m.put(a + 0xC, 4, target)
        m.put(a, 4, m.vcall(raid, 0x98))
        m.put(a + 0x88, 1, _class_of(m, o, m.vcall(raid, 0x98) & 0xFFFFFFFF)); m.put(a + 0x89, 2, 0)
        m.put(a + 0x54, 4, _next_action_serial(m, o))
        m.put(a + 0x84, 4, m.u32(entry + 0x84))
        m.call_void(m.main + 0x1820EB8, lst, a)


@lifted(0x113E9E4)
def raid_actions_of_turn(m, o, *_):
    with m.frame(0x10) as f:
        m.put(f + 8, 8, m.u64(o + 0x48))
        x = m.call(m.main + 0x113EA18, m.u64(o + 0x78))
        return _tail(m, m.main + 0x114CE2C, x, f, f + 8)



@lifted(0x287EAD4)
def queue_b2(m, o, *_):
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xB2, 0)


@lifted(0x17521D8)
def queue_c8(m, o, b, *_):
    """Command 0xc8 (id of b), unless b is null or its id is 0."""
    if b == 0:
        return
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    if ident == 0:
        return
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xC8, ident)


@lifted(0x11501BC)
def queue_ca(m, o, a, b, n, ids, *_):
    """Variadic command 0xca (a, b & 0xffff, then n (1..4) u32 ids from `ids`, ended by 0xffff0000)
    through 0x157ebc0; any other n sends no ids."""
    k = (n - 1) & 0xFFFFFFFF
    vals = [m.u32(ids + 4 * i) for i in range(k + 1)] if k <= 3 else []
    return _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), 0xCA, a & 0xFFFFFFFF, b & 0xFFFF, *vals, 0xFFFF0000)


def _raid_id_inline(m, rec):
    """_raid_id with 0x14b5634 / 0x114c614 inlined: the parties' list 1 (flag +0x90, first member +0x60)."""
    v = m.u32(rec + 0x18)
    if m.u8(m.u64(m.u64(rec + 8) + 0x38) + 0x499) >> 2 & 1 and v == 0:
        parties = m.u64(m.u64(rec + 0x10) + 0x30)
        if m.u8(parties + 0x90):
            b = m.u64(parties + 0x60)
            if b:
                v = m.vcall(b, 0x98) & 0xFFFFFFFF
                m.put(rec + 0x18, 4, v)
        else:
            v = 0
    return v


@lifted(0x2886D48)
def first_non_raid_actor(m, o, *_):
    """The entry (0x13813f4) of the first battler with an action in the list that is not the raid battler; 0."""
    if m.call(m.main + 0x1149348, m.call(m.main + 0x1149340, o)) & 0xFF == 0:
        return 0
    i = 0
    while True:
        e = m.call(m.main + 0x1149354, m.call(m.main + 0x1149340, o), i)
        if e and m.u32(e):
            ident = m.u32(e)
            if _raid_id_inline(m, m.u64(m.u64(o + 0x10) + 0x310)) != ident:
                return _tail(m, m.main + 0x13813F4, o, m.u32(e))
        i += 1
        if i >= m.call(m.main + 0x1149348, m.call(m.main + 0x1149340, o)) & 0xFF:
            return 0


@lifted(0x1140958)
def raid_turn_if_standing(m, o, *_):
    """Tail-calls 0x11425b0(o) while the raid battler exists and is still in the battle (vf 0x200 false)."""
    def raid():
        return m.call(m.main + 0xF6FC68, m.call(m.main + 0x11409B4, m.call(m.main + 0x1482534, o)))
    if raid() == 0:
        return 0
    r = m.vcall(raid(), 0x200)
    if r & 1:
        return r
    return _tail(m, m.main + 0x11425B0, o)


# 0x1482e80's message per kind 1..35 (jump table 0x3c6a6b4): (form, group, message). Form "F" sends
# (id, message, id), "H" (id, message, id, extra), "G" (id, message); kinds not listed send
# ("F", 0xca, 0x237).
_KIND_MESSAGES = {
    1: ("F", 0xCA, 0x242), 3: ("F", 0xCB, 0x5D), 4: ("F", 0xCB, 0x62), 6: ("F", 0xCB, 0x7A),
    7: ("F", 0xCB, 0x7B), 8: ("F", 0xCB, 0x71), 9: ("H", 0xCB, 0xC6), 10: ("H", 0xCB, 0xBE),
    11: ("H", 0xCB, 0xC1), 12: ("H", 0xCB, 0xC4), 13: ("H", 0xCB, 0x11E), 14: ("F", 0xCB, 0x11F),
    18: ("F", 0xCB, 0x94), 20: ("H", 0xCB, 0x15B), 23: ("F", 0xCA, 0x2BA), 26: ("G", 0xCA, 0x2F2),
    27: ("G", 0xCA, 0x305), 28: ("G", 0xCA, 0x306), 29: ("F", 0xCA, 0x30B), 30: ("F", 0xCA, 0x30C),
    31: ("F", 0xCA, 0x30C), 32: ("F", 0xCA, 0x30C), 33: ("F", 0xCB, 0x1B4), 34: ("F", 0xCB, 0x1BB),
}
_END = 0xFFFF0000


@lifted(0x1482E80)
def kind_message(m, o, b, extra, kind, *_):
    """Queue the message for battler b's state change `kind` through 0x157ebc0 (kind 2 also runs
    0x1366360, kind 15 adds commands 0xc7 and 0xc8, kind 22 picks one of a set of messages)."""
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    kind &= 0xFF
    q = m.u64(o + 0x18)
    send = lambda *a: _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), *a)
    if kind in (19, 25):
        return ident
    if kind == 2:
        m.call_void(m.main + 0x157EBC0, q, 0xCB, ident, 0x68, ident, _END)
        r = m.call(m.main + 0x1366360, m.u64(o + 8), m.u64(o + 0x10), b)
        if r & 0xFF == 0xFF:
            return send(0xCA, ident, 0x2EB, _END)
        return r
    if kind == 15:
        m.call_void(m.main + 0x119AFF0, q, 0xC7, ident, 0)
        m.call_void(m.main + 0x157EBC0, m.u64(o + 0x18), 0xCB, ident, 0x96, ident, _END)
        return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xC8, ident)
    if kind == 22:
        if m.vcall(b, 0x228, 0) & 1:
            return send(0xCA, ident, 0x2BB, ident, _END)
        i = m.call(m.main + 0x11440F0, m.call(m.main + 0x11440E8, m.u64(o + 0x10)), 4) & 0xFF
        return send(0xCA, ident, i + 0x2B5, ident, _END)
    form, group, msg = _KIND_MESSAGES.get(kind, ("F", 0xCA, 0x237))
    if form == "F":
        return send(group, ident, msg, ident, _END)
    if form == "H":
        return send(group, ident, msg, ident, extra & 0xFFFFFFFF, _END)
    return send(group, ident, msg, _END)


@lifted(0x284DF10)
def kind_2_284de20(m, o, a, *_):
    return _tail(m, m.main + 0x284DE20, o, a, 2)


@lifted(0x287EA80)
def set_and_queue_288d8c0(m, o, a, p, *_):
    """When 0x288c710([o+0x20], a, p) accepts, 0x288d8c0([o+0x18], a, p); 1 when it did."""
    if m.call(m.main + 0x288C710, m.u64(o + 0x20), a, p) & 1 == 0:
        return 0
    m.call_void(m.main + 0x288D8C0, m.u64(o + 0x18), a, p)
    return 1


@lifted(0x28533B8)
def target_of_code(m, _x0, code, b, out, ctx, obj, *_):
    """Write battler b's target descriptor for a script code into the 16 bytes at `out`: codes 0..5
    through 0x1480a6c, 6 a kind-2 descriptor from the object's two named values, 7 kind 3, else kind 1."""
    c = code & 0xFFFF
    if c <= 5:
        ident = m.vcall(b, 0x98)
        r = m.call(m.main + 0x1480A6C, ident, code, ident & 0xFFFFFFFF, ctx, obj)
        m.put(out, 8, r[0]); m.put(out + 8, 8, r[1])
        return
    m.put(out + 8, 8, 0)
    if c == 6:
        x = m.vcall(obj, 0x68, m.main + 0x3C69CC8)
        y = m.vcall(obj, 0x68, m.main + 0x3C69CD0)
        v = m.call(m.main + 0x179405C, ctx, x & 0xFFFFFFFF, y & 0xFFFFFFFF)
        lo, hi = m.vcall(b, 0x98) & 0xFFFFFFFF, (v & 0x3F) << 3 | 2
    elif c == 7:
        lo = m.vcall(b, 0x98) & 0xFFFFFFFF
        hi = (m.vcall(b, 0x98) & 0x3F) << 3 | 3
    else:
        lo, hi = m.vcall(b, 0x98) & 0xFFFFFFFF, 1
    m.put(out, 8, lo); m.put(out + 8, 8, hi)


@lifted(0x187495C)
def run_17ce0ec_for(m, o, b, *_):
    if b == 0:
        return
    return _tail(m, m.main + 0x17CE0EC, o, m.vcall(b, 0x98) & 0xFFFFFFFF, 0)


@lifted(0x287B7A4)
def flag_of_id(m, o, ident, *_):
    """Whether the u32-keyed map at o+0x2f0 holds `ident` with a nonzero value byte (through its at())."""
    from pokeldn.sv.battle.engine.containers import find
    ident &= 0xFFFFFFFF
    if not find(m, o + 0x2F0, ident, 4):
        return 0
    with m.frame(0x10) as f:
        m.put(f, 4, ident)
        return int(m.u8(m.call(m.main + 0x287B8E0, o + 0x2F0, f)) != 0)


@lifted(0x14B5634)
def party_list(m, parties, client, *_):
    """The member list (+0x28 + 0x38 * client) of a client's party; 0 past client 4."""
    client &= 0xFFFFFFFF
    return (parties + 0x38 * client + 0x28) & 0xFFFFFFFFFFFFFFFF if client <= 4 else 0


@lifted(0x2842270)
def target_slot(m, o, out, req, *_):
    """out = 0x10e21c0 for the entry of battler [req] (0x13813f4) and the move u16 at req+4."""
    e = m.call(m.main + 0x13813F4, o, m.u32(req))
    x = m.call(m.main + 0x11440E8, m.call(m.main + 0x1482534, o))
    y = m.call(m.main + 0x114E480, o)
    z = m.call(m.main + 0x1482534, o)
    m.put(out, 1, m.call(m.main + 0x10E21C0, y, z, e, m.u16(req + 4), x))


@lifted(0x11514B8)
def raid_action_order(m, o, act, lst, *_):
    """One past the order (+0x84) of the raid battler's action in the list; without one, what 0x113ecdc
    gives for `act` (request 0x102); 0 without a raid battler."""
    if m.call(m.main + 0xF6FC68, m.u64(m.u64(o + 0x10) + 0x310)) == 0:
        return 0
    k = 0
    while k < m.u8(lst + 0x2420):
        e = lst + 8 + 0x8C * k
        ident = m.u32(e)
        raid = m.call(m.main + 0xF6FC68, m.u64(m.u64(o + 0x10) + 0x310))
        if ident == m.vcall(raid, 0x98) & 0xFFFFFFFF:
            return (m.u32(e + 0x84) + 1) & 0xFFFFFFFF
        k += 1
    with m.frame(0x20) as f:
        m.put(f + 0x10, 8, act); m.put(f + 0x18, 2, 0x102)
        x = m.call(m.main + 0x28838F4, m.u64(o + 0x78))
        m.call_void(m.main + 0x113ECDC, x, f + 8, f + 0x10)
        return m.u32(f + 8)


@lifted(0x2844160)
def touch_shared_object(m, p, *_):
    """The object at [0xe7ecd0([p])+0x148], after taking and dropping one reference on its shared
    state (+0x30: u16 count +0x1a; the first reference builds the value at +8 through vf 0 of +0x10,
    the last one clears +0x10 and runs the object's vf 0x50). Abort paths are refused."""
    r = m.u64(m.call(m.main + 0xE7ECD0, m.u64(p)) + 0x148)
    if r == 0:
        return 0
    s = m.u64(r + 0x30)
    if m.u64(s + 0x10) == 0:
        raise UnliftedCall("AddReference abort: m_object is null")
    c = m.u16(s + 0x1A)
    m.put(s + 0x1A, 2, c + 1)
    if c == 0:
        m.put(s + 8, 8, m.vcall(m.u64(s + 0x10), 0))
        m.put(s + 0x1C, 4, 0xFFFFFFFE)
    elif c == 0xFFFF:
        raise UnliftedCall("AddReference abort: count overflow")
    s = m.u64(r + 0x30)
    c = m.u16(s + 0x1A)
    m.put(s + 0x1A, 2, c - 1)
    if c == 1:
        m.put(s + 0x10, 8, 0)
        m.vcall_void(r, 0x50)
    elif c == 0:
        raise UnliftedCall("Release abort: count underflow")
    return r



@lifted(0x284DE20)
def boost_once(m, o, a, k, *_):
    """When 0x283d6a0(o, 4) is `a`, the byte of [root+0xe0]'s id is k, and neither record +0x268 nor
    record 0x64 (k == 1) / 0x65 is set: 0x1353738([o+0x38], 0x38, 0x800, or 0xaac when 0x144b6d4 is
    nonzero), then mark that record pending."""
    k &= 0xFF
    if a & 0xFFFFFFFF != m.call(m.main + 0x283D6A0, o, 4) & 0xFF:
        return
    root = m.u64(m.u64(o + 0x38) + 0x78)
    if _owner_id(m, o, 0xE0) & 0xFF != k:
        return
    p = m.u64(root + 0x268)
    if p and m.u32(p + 0xC):
        return
    idx = 0x64 if k == 1 else 0x65
    p = m.u64(root + 8 * idx + 8)
    if p and m.u32(p + 0xC):
        return
    v = 0x800 if m.call(m.main + 0x144B6D4, m.u64(o + 8)) & 0xFFFFFFFF == 0 else 0xAAC
    m.call_void(m.main + 0x1353738, m.u64(o + 0x38), 0x38, v)
    _mark_pending(m, m.u64(m.u64(m.u64(o + 0x38) + 0x78) + 8 * idx + 8))
