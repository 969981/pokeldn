"""The battler object (one per Pokemon in battle): field getters and flag bits."""

from pokeldn.sv.battle.machine import UnliftedCall, lifted


@lifted(0x2D3B6F8)
def get_50(m, b, *_): return m.u32(b + 0x50)


@lifted(0x2D3BC58)
def get_5a(m, b, *_): return m.u16(b + 0x5A)


@lifted(0x2D3BC60)
def get_58(m, b, *_): return m.u16(b + 0x58)


@lifted(0x2D3BB04)
def get_408(m, b, *_): return m.u16(b + 0x408)


@lifted(0x2D3B7D0)
def get_487(m, b, *_): return m.u8(b + 0x487)


@lifted(0x2D3EADC)
def get_6c(m, b, *_): return m.u8(b + 0x6C)


@lifted(0x2D3E63C)
def get_5a0(m, b, i, *_): return m.u8(b + (i & 0xFFFFFFFF) + 0x5A0)


def _bit(m, b, base, i):
    i &= 0xFFFFFFFF
    return m.u8(b + ((i >> 3) & 0xFF) + base) >> (i & 7) & 1


@lifted(0x2D3D14C)
def flag_49e(m, b, i, *_): return _bit(m, b, 0x49E, i)


@lifted(0x2D3D130)
def flag_49a(m, b, i, *_): return _bit(m, b, 0x49A, i)


@lifted(0x2D3D114)
def flag_496(m, b, i, *_): return _bit(m, b, 0x496, i)


@lifted(0x2D3D7F4)
def set_flag_496(m, b, i, *_):
    i &= 0xFFFFFFFF
    a = b + ((i >> 3) & 0xFF) + 0x496
    m.put(a, 1, m.u8(a) | (1 << (i & 7)))


@lifted(0x2D3C0B8)
def slot_88_active(m, b, i, *_):
    return int(m.u8(b + (i & 0xFFFF) * 0x10 + 0x88) & 7 != 0)


@lifted(0x2D3ECFC)
def clear_6f8(m, b, *_):
    if m.u32(b + 0x6F8) != 0:
        m.put(b + 0x6F8, 4, 0); m.put(b + 0x6F4, 2, 0)


@lifted(0x2D3EE2C)
def call_520_3(m, b, *_):
    m.vcall(b, 0x520, 3)


# Stat stages -6..+6 as (numerator, denominator), 0x3c69d73.
STAGE_RATIO = ((2, 8), (2, 7), (2, 6), (2, 5), (2, 4), (2, 3), (2, 2),
               (3, 2), (4, 2), (5, 2), (6, 2), (7, 2), (8, 2))


@lifted(0x2D3BFC0)
def vf108_is_zero(m, b, *_):
    return int(m.vcall(b, 0x108) & 0xFFFF == 0)


@lifted(0x2D3C1B8)
def first_active_98(m, b, *_):
    for i, off in enumerate((0x98, 0xA8, 0xB8, 0xC8), 1):
        if m.u8(b + off) & 7:
            return i
    return 5 if m.u8(b + 0xD8) & 7 else 0


@lifted(0x2D3BEB0)
def staged_value(m, b, *_):
    """vf 0xe0 scaled by the stage in byte +0x418 (b[0x83] as u64 index)."""
    v = m.vcall(b, 0xE0)
    stage = m.u8(b + 0x418)
    if stage >= 13:
        return v
    num, den = STAGE_RATIO[stage]
    return ((v * num) & 0xFFFF) // den & 0xFFFFFFFF


def vf2a8_unless(m, b, other, *_):
    if m.u32(other + 0xBC) == 0 and m.vcall(b, 0x220, 0x13) & 1 == 0:
        return m.vcall(b, 0x2A8)
    return 0


@lifted(0x2D3DBE8)
def turn_start(m, b, *_):
    m.put(b + 0x496, 4, 0)
    if m.u16(b + 0x488) < 9999:
        m.put(b + 0x488, 2, m.u16(b + 0x488) + 1)
    n = (m.u8(b + 0x6EF) + 1) & 0xFF
    n = n if n < 3 else 0
    m.put(b + 0x6EF, 1, n)
    m.put(b + n + 0x6EC, 1, 0)
    m.put(b + 0x487, 1, 1)


@lifted(0x2D3CBF4)
def move_index(m, b, move, *_):
    """Which of the four move slots (u16 at +0x430 + 0x16 * i) holds `move`; 4 for none or move 0."""
    move &= 0xFFFF
    if move == 0:
        return 4
    for i in range(4):
        if m.u16(b + 0x430 + 0x16 * i) == move:
            return i
    return 4


@lifted(0x2D3E660)
def add_counter_5a8(m, b, i, n, *_):
    i &= 0xFF
    if i < 9:
        a = b + 0x5A8 + 4 * i
        v = (m.u32(a) + n) & 0xFFFFFFFF
        m.put(a, 4, 0xFFFF if v > 0xFFFE else v)


@lifted(0x2D3D938)
def step_condition(m, b, cond, out_pair, out_ended, *_):
    """Count one turn of condition `cond` (16-byte entries at +0x80, turns at +0x390); 1 when set."""
    cond &= 0xFFFF
    if cond & 0xFFFB == 2:
        return 0
    entry = b + 0x80 + 0x10 * cond
    word = m.u64(entry + 8)
    if word & 7 == 0:
        return 0
    kind = word & 7
    limit = (word >> 3) & 0x3F if kind in (2, 4) else 0
    first, second = m.u64(entry), m.u64(entry + 8)
    if out_pair:
        m.put(out_pair, 8, first); m.put(out_pair + 8, 8, second)
    if out_ended:
        m.put(out_ended, 1, 0)
    if cond == 0x1C:
        raise UnliftedCall("condition 0x1c (vf 0x668)")
    turns = b + 0x390 + cond
    if limit == 0:
        word = m.u64(entry + 8)
        if word & 7 == 1 and word & 0x1F8:
            if m.u8(turns) < (word >> 3) & 0x3F:
                m.put(turns, 1, m.u8(turns) + 1)
    else:
        t = (m.u8(turns) + 1) & 0xFF
        m.put(turns, 1, t)
        if limit <= t:
            m.put(entry, 8, 0); m.put(entry + 8, 8, 0); m.put(turns, 1, 0)
            if out_ended:
                m.put(out_ended, 1, 1)
    return 1
