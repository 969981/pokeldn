"""Pointer and field getters of the server's objects, named by offset until their meaning is known."""

from pokeldn.sv.battle.machine import lifted


def _q(off):
    def get(m, o, *_): return m.u64(o + off)
    return get


for _addr, _off in ((0x1482534, 0x10), (0x1143584, 0x20), (0x1146E90, 0x38), (0x11409B4, 0x310),
                    (0x1361214, 0x78), (0x13813EC, 0x290), (0x11427FC, 0x68), (0x148253C, 0x70),
                    (0x114E480, 0x08), (0x11440E8, 0x10)):
    lifted(_addr)(_q(_off))


@lifted(0x1149348)
def get_2420(m, o, *_): return m.u8(o + 0x2420)


@lifted(0x1482544)
def slot_a8_nonzero(m, o, i, *_):
    i &= 0xFFFFFFFF
    if i >= 0x80000000 or i >= 0xE:   # signed compare: negative indices are below 0xe
        if i >= 0x80000000:
            return int(m.u32(o + (i & 0xFFFFFFFF) * 4 + 0xA8) != 0)
        return 0
    return int(m.u32(o + i * 4 + 0xA8) != 0)


@lifted(0x179372C)
def clear_pair(m, p, *_):
    m.put(p + 8, 8, 0); m.put(p, 4, 0)


@lifted(0x1381420)
def slot_of_id(m, o, ident, *_):
    """Index 0..9 of the active entry (u32 id at +8 + 8i, flag byte at +0xc + 8i) holding `ident`; 10 if none."""
    ident &= 0xFFFFFFFF
    for i in range(10):
        if m.u8(o + 0xC + 8 * i) and m.u32(o + 8 + 8 * i) == ident:
            return i
    return 10


@lifted(0x2D1FD38)
def static_46d3f08(m, *_):
    """A function-local static, built on first use; the engine only reads one already built."""
    if m.u8(m.u64(m.main + 0x46D3F00)) & 1 == 0:
        raise UnliftedCall("static 0x46d3f08 not built")
    return m.u64(m.main + 0x46D3F08)


@lifted(0x1149340)
def get_48(m, o, *_): return m.u64(o + 0x48)


@lifted(0x1146154)
def clear_0x24(m, p, *_):
    m.put(p + 0x20, 4, 0); m.put(p + 0x10, 8, 0); m.put(p + 0x18, 8, 0); m.put(p, 8, 0); m.put(p + 8, 8, 0)


@lifted(0x10E2DA8)
def rule_value(m, o, key, *_):
    """The u32 value for `key` in the setup's map ([[o+8]+0x50]); 0 when absent or above 4."""
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(o + 8) + 0x50), key)
    if p == 0:
        return 0
    v = m.s(p, 4)
    return v & 0xFFFFFFFF if v < 5 else 0


# Battle mode 0, 1, 2 -> five-entry tables (0x3c6a450, 0x3c6a455, 0x3c6a45a).
_MODE_TABLES = {0: (0, 1, 2, 2, 2), 1: (0, 1, 0, 1, 2), 2: (0, 1, 0, 0, 0)}


@lifted(0x144E790)
def mode_class(m, o, key, *_):
    setup = m.u64(o + 8)
    mode = m.u32(setup + 0x36C)
    p = m.call(m.main + 0x10E2DD4, m.u64(setup + 0x50), key)
    v = 0 if p == 0 or m.s(p, 4) > 4 else m.u32(p) & 0xFF
    if mode not in _MODE_TABLES or v > 4:
        return 2
    return _MODE_TABLES[mode][v]
