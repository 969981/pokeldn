"""Battler methods reached through its vtable (main+0x44fbcb0): small getters, setters and the calls
it hands to the Pokemon object it holds at +0x48."""

from pokeldn.sv.battle.machine import lifted

MOVE_SLOT, MOVE_COUNT = 0x16, 0x482


def _core(m, b):
    return m.u64(b + 0x48)


def _forward(slot, *fixed):
    """A method that calls `slot` of the object at +0x48 with the given leading arguments, then the
    caller's remaining ones, and returns its result."""
    def fn(m, b, *args):
        return m.vcall(_core(m, b), slot, *(fixed + args[:4 - len(fixed)]))
    return fn


for _addr, _slot, _fixed in ((0x2D3BC88, 0x70, (0,)), (0x2D3BCAC, 0x70, (1,)), (0x2D3BCD0, 0x70, (2,)),
                             (0x2D3BCF4, 0x70, (3,)), (0x2D3BD18, 0x70, (4,)), (0x2D3BD3C, 0x70, (5,)),
                             (0x2D3EE3C, 0x1B0, (9,)), (0x2D3CD80, 0x170, ()), (0x2D3CD90, 0x178, ()),
                             (0x2D3E6E4, 0xC8, ()), (0x2D3EE60, 0x1C0, ())):
    lifted(_addr)(_forward(_slot, *_fixed))


def _own(slot):
    def fn(m, b, *args):
        return m.vcall(b, slot, *args[:4])
    return fn


lifted(0x2A10910)(_own(0x78))
lifted(0x2A1091C)(_own(0x98))


@lifted(0x2A10930)
def own_730(m, b, *_): return m.vcall(b, 0x730) & 0xFFFF


@lifted(0x2A10950)
def own_740(m, b, *_): return m.vcall(b, 0x740) & 0xFFFF


@lifted(0x2D3BF0C)
def is_41c_1fe(m, b, *_): return int(m.u16(b + 0x41C) == 0x1FE)


@lifted(0x2D3C250)
def condition_entry(m, b, cond, *_):
    """The 16-byte entry of condition `cond` (+0x80), returned in x0 and x1."""
    from pokeldn.sv.battle.machine import Pair
    e = b + 0x80 + 0x10 * (cond & 0xFFFF)
    return Pair(m.u64(e), m.u64(e + 8))


@lifted(0x2D3C25C)
def condition_turns(m, b, cond, *_): return m.u8(b + 0x390 + (cond & 0xFFFF))


@lifted(0x2D3B708)
def field_3e0(m, b, *_): return b + 0x3E0


@lifted(0x2D3D8B0)
def slot_4a0(m, b, i, *_): return b + 0x4A0 + 8 * (i & 0xFFFFFFFF)


@lifted(0x2D3D8BC)
def set_slot_4a0(m, b, i, src, *_): m.put(b + 0x4A0 + 8 * (i & 0xFFFFFFFF), 8, m.u64(src))


@lifted(0x2D3ECEC)
def has_6f8(m, b, *_): return int(m.u32(b + 0x6F8) != 0)


def _move_byte(off):
    def fn(m, b, i, *_): return m.u8(b + off + MOVE_SLOT * (i & 0xFF))
    return fn


lifted(0x2D3C94C)(_move_byte(0x428))
lifted(0x2D3C988)(_move_byte(0x429))


@lifted(0x2D3CB40)
def move_43a_clear(m, b, i, *_): return int(m.u8(b + 0x43A + MOVE_SLOT * (i & 0xFF)) == 0)


@lifted(0x2D1F674)
def is_710(m, b, v, *_): return int(m.u16(b + 0x710) == v & 0xFFFF)


@lifted(0x2D1F684)
def is_710_718(m, b, v, w, *_):
    return int(m.u16(b + 0x710) == v & 0xFFFF and m.u16(b + 0x718) == w & 0xFFFF)


@lifted(0x2D3E338)
def copy_6f2(m, b, other, *_): m.put(b + 0x6F2, 2, m.u16(other + 0x6F2))


@lifted(0x2D3E610)
def set_5a0(m, b, i, v, *_): m.put(b + 0x5A0 + (i & 0xFFFFFFFF), 1, v)


@lifted(0x2D3C7D8)
def move_433_minus_432(m, b, i, *_):
    s = b + MOVE_SLOT * (i & 0xFF)
    return (m.u8(s + 0x433) - m.u8(s + 0x432)) & 0xFFFFFFFF


@lifted(0x2D3C7F4)
def move_429_minus_428(m, b, i, *_):
    s = b + MOVE_SLOT * (i & 0xFF)
    return (m.u8(s + 0x429) - m.u8(s + 0x428)) & 0xFFFFFFFF


@lifted(0x2D3B7F0)
def set_6d_74(m, b, v, *_): m.put(b + 0x6D, 1, 1); m.put(b + 0x74, 4, v)


@lifted(0x2D3E6FC)
def clear_6d_74(m, b, *_): m.put(b + 0x6D, 1, 0); m.put(b + 0x74, 4, 0)


@lifted(0x2D3D240)
def not_4e8_20(m, b, *_): return int(m.vcall(b, 0x4E8) & 0xFFFFFFFF != 0x20)


@lifted(0x2D3D264)
def has_540_4(m, b, *_): return int(m.vcall(b, 0x540, 4) & 0xFF != 0)


@lifted(0x2D3E3D0)
def has_338(m, b, *_): return int(m.vcall(b, 0x338) & 0xFF != 0x12)


@lifted(0x2D3B764)
def clear_7c_78(m, b, *_): m.put(b + 0x7C, 1, 0); m.put(b + 0x78, 4, 0)


@lifted(0x2D3D168)
def set_flag_49e(m, b, i, *_):
    i &= 0xFFFFFFFF
    a = b + ((i >> 3) & 0xFF) + 0x49E
    m.put(a, 1, m.u8(a) | (1 << (i & 7)))


@lifted(0x2D3DC34)
def clear_flag_496(m, b, i, *_):
    i &= 0xFFFFFFFF
    a = b + ((i >> 3) & 0xFF) + 0x496
    m.put(a, 1, m.u8(a) & ~(1 << (i & 7)))


@lifted(0x2D3D884)
def clear_flag_49a(m, b, i, *_):
    i &= 0xFFFFFFFF
    a = b + ((i >> 3) & 0xFF) + 0x49A
    m.put(a, 1, m.u8(a) & ~(1 << (i & 7)))
    return m.vcall(b, 0x500, i)


@lifted(0x2D3ECBC)
def set_6f8(m, b, v, w, *_): m.put(b + 0x6F8, 4, v); m.put(b + 0x6F4, 2, w)


@lifted(0x2D3E418)
def set_5e(m, b, v, *_): m.put(b + 0x5E, 2, v); m.put(b + 0x5C, 2, 0)


@lifted(0x80120C)
def first_of_30(m, o, *_):
    p = m.u64(o + 0x30)
    return m.u64(p) if p else 0


def _byte_3c2(m, b, i, *_):
    i &= 0xFF
    return m.u8(b + 0x3C2 + i) if i < m.u8(b + 0x3C1) else 0


lifted(0x2D3EBA0)(_byte_3c2)
lifted(0x2D3B874)(_byte_3c2)


@lifted(0x2D3E648)
def set_counter_5a8(m, b, i, v, *_):
    i &= 0xFF
    if i < 9:
        m.put(b + 0x5A8 + 4 * i, 4, v)


@lifted(0x2D3D798)
def set_484(m, b, v, *_):
    if v & 0xFF < 4:
        m.put(b + 0x484, 1, v)


def _slot_getter(off, size, default):
    def fn(m, b, i, *_):
        i &= 0xFF
        return m.u(b + off + MOVE_SLOT * i, size) if i < m.u8(b + MOVE_COUNT) else default
    return fn


lifted(0x2D3C960)(_slot_getter(0x433, 1, 0))
lifted(0x2D3C5FC)(_slot_getter(0x430, 2, 0xA5))
lifted(0x2D3C77C)(_slot_getter(0x438, 1, 0))


@lifted(0x2D3C654)
def move_435(m, b, i, *_):
    i &= 0xFF
    return int(i < m.u8(b + MOVE_COUNT) and m.u8(b + 0x435 + MOVE_SLOT * i) != 0)


@lifted(0x2D3C684)
def move_436(m, b, i, *_):
    i &= 0xFF
    return int(i < m.u8(b + MOVE_COUNT) and m.u8(b + 0x436 + MOVE_SLOT * i) != 0)


@lifted(0x2D3BF7C)
def hp_full(m, b, *_):
    return int(m.vcall(b, 0x108) & 0xFFFF == m.vcall(b, 0x110) & 0xFFFF)


@lifted(0x2D3E4A4)
def set_480(m, b, v, *_): m.put(b + 0x480, 2, v if v & 0xFFFF else 1)


@lifted(0x2D3E3A4)
def set_added_type(m, b, t, v, *_):
    t &= 0xFF
    if m.u8(b + 0x40A) != t and m.u8(b + 0x40B) != t:
        m.put(b + 0x40C, 1, t); m.put(b + 0x410, 4, v)


@lifted(0x2D3EAE4)
def set_6f2_and_610(m, b, v, *_):
    m.put(b + 0x6F2, 2, v)
    return m.vcall(b, 0x610, 8)


@lifted(0x2D3E710)
def both_6c_clear(m, b, other, *_):
    return int(m.u8(b + 0x6C) == 0 and m.u8(other + 0x6C) == 0 and m.u16(other + 0x6F2) == 0)


@lifted(0x2D3E408)
def shift_5c(m, b, *_):
    v = m.u16(b + 0x5C); m.put(b + 0x5C, 2, 0); m.put(b + 0x5E, 2, v)


@lifted(0x2D3CBB8)
def knows_move(m, b, move, *_):
    move &= 0xFFFF
    return int(any(m.u16(b + 0x430 + MOVE_SLOT * i) == move for i in range(4)))


@lifted(0x2D3E61C)
def bump_5a0(m, b, i, *_):
    a = b + 0x5A0 + (i & 0xFFFFFFFF)
    if m.u8(a) != 0xFF:
        m.put(a, 1, m.u8(a) + 1)


@lifted(0x2D3ECC8)
def get_6f8(m, b, out1, out2, *_):
    if m.u32(b + 0x6F8):
        m.put(out1, 4, m.u32(b + 0x6F8)); m.put(out2, 2, m.u16(b + 0x6F4))
        return 1
    return 0


@lifted(0x2D3D42C)
def any_stage_below_6(m, b, *_):
    """Whether any of the seven stat stages (+0x414..+0x41a, 6 = neutral) is below neutral."""
    return int(any(m.s(b + 0x414 + i, 1) <= 5 for i in range(7)))


@lifted(0x2D3DB54)
def clear_turn_conditions(m, b, *_):
    m.put(b + 0x399, 1, 0); m.write(b + 0x90, bytes(0x50)); m.put(b + 0x110, 8, 0); m.put(b + 0x118, 8, 0)
    m.put(b + 0x391, 4, 0); m.put(b + 0x395, 1, 0)


@lifted(0x2D3B3B0)
def set_480_from_core(m, b, *_):
    v = m.vcall(_core(m, b), 0x180) & 0xFFFF
    m.put(b + 0x480, 2, v or 1)


@lifted(0x2D3B800)
def shown_id(m, b, *_):
    return m.vcall(b, 0x98) if m.u8(b + 0x6D) == 0 else m.u32(b + 0x74)


@lifted(0x2D3CA6C)
def mark_42c(m, b, i, *_):
    s = b + MOVE_SLOT * (i & 0xFF)
    if m.u8(s + 0x43A) == 0 and m.u8(s + 0x42C) == 0:
        m.put(s + 0x42C, 1, 1); m.put(b + 0x485, 1, m.u8(b + 0x485) + 1)
