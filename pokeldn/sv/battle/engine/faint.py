"""Fainting: marking a battler fainted, the faint pass after an action and the raid's case of it."""

from pokeldn.sv.battle.engine.actions import _standing_by_speed
from pokeldn.sv.battle.engine.calls import M32, _need, _tail
from pokeldn.sv.battle.engine.damage import _HIT_KEY, _per_hit
from pokeldn.sv.battle.engine.statics import _raid_class
from pokeldn.sv.battle.machine import lifted


@lifted(0x2D3C2E8)
def hits_to_faint(m, b, kind, table, *_):
    """How many hits of fixed damage kind `kind` the battler takes before fainting: its HP (vf 0x140)
    divided by vf 0x68 of `table` for the kind's key, at least 1; 0 when vf 0x220 rejects the kind."""
    if m.vcall(b, 0x220, kind, table) & 1 == 0:   # x1, x2 pass through to the virtual call
        return 0
    kind &= 0xFFFF
    if kind in (6, 7, 8):
        return 0
    if kind == 5:
        n = m.vcall(table, 0x68, m.u64(m.main + 0x46E2700)) & 0xFFFFFFFF
        w = m.u64(b + 0xD8)
        if w & 7 == 1 and (w >> 3 & 0x3F) == (n - 1) & 0xFFFFFFFF:
            d = m.vcall(table, 0x68, m.u64(m.main + 0x46E2700)) & 0xFFFFFFFF
            return (_per_hit(m, b, d) * m.u8(b + 0x395)) & 0xFFFFFFFF
        key = _HIT_KEY[5]
    elif kind == 9:
        if m.vcall(b, 0x228, 1) & 1 == 0:
            return 0
        key = _HIT_KEY[9]
    elif kind in _HIT_KEY:
        key = _HIT_KEY[kind]
    elif kind == 0x2E:
        if m.vcall(b, 0x300, 10) & 1 or m.vcall(b, 0x300, 8) & 1:
            key = 0x3C6B548
        else:
            key = 0x3C6B550
    else:
        return 0
    d = m.vcall(table, 0x68, m.main + key) & 0xFFFFFFFF
    return _per_hit(m, b, d)


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


@lifted(0x136038C)
def end_check_after_faint(m, o, b, flag, *_):
    """When the battle is over (0x114a808 false) and `flag`: 0x1361bb0 with b."""
    if m.call(m.main + 0x114A808, o) & 1:
        if m.call(m.main + 0x13603FC, o) & 1:
            return
    if not flag & 1:
        return
    with m.frame(0x20) as sp:
        m.put(sp + 0x18, 8, b)
        x = m.call(m.main + 0x1360F04, m.call(m.main + 0x1361214, o))
        m.call_void(m.main + 0x1361BB0, x, sp + 8, sp + 0x18)


@lifted(0x1589A7C)
def note_fainted(m, p, ident, *_):
    """Append ident to the u32 list at p+8 (count byte +0x9e, at most 0x1e, flag byte p+0x80+i cleared),
    set its byte in the u32 -> u8 map at p+0x2f0, and count it (capped at 100) in the u16 at
    p+0x2e0 + 2 * 0x10e2da8([p+0x358] setup, ident)."""
    ident &= M32
    n = m.u8(p + 0x9E)
    if n <= 0x1D:
        m.put(p + 8 + 4 * n, 4, ident)
        m.put(p + 8 + n + 0x78, 1, 0)
        m.put(p + 0x9E, 1, m.u8(p + 0x9E) + 1)
    side = m.call(m.main + 0x10E2DA8, m.call(m.main + 0xE7E27C, m.u64(p + 0x358)), ident) & 0xFF
    with m.frame(0x10) as f:
        m.put(f, 4, ident)
        m.put(m.call(m.main + 0x1589BC0, p + 0x2F0, f), 1, 1)
    c = p + 0x2E0 + 2 * side
    v = m.u16(c)
    if v <= 0x63:
        m.put(c, 2, v + 1)


@lifted(0x1589990)
def battler_fainted(m, o, rec, ident, *_):
    """Record a faint: 0x1589a7c(rec, ident); when no party member of 0x114e498(o, rule value) is able,
    rank the side (0x1589b18); then the battler's vf 0x550(1, 1) and command 0x37 (ident, 1, 1)."""
    ident &= M32
    v = m.call(m.main + 0x1589A40, o, ident) & M32
    m.call_void(m.main + 0x1589A7C, rec, ident)
    lst = m.call(m.main + 0x114E498, o, v)
    if not m.call(m.main + 0xE7E454, lst) & 0xFF:
        m.call_void(m.main + 0x1589B18, m.call(m.main + 0x1589A74, m.call(m.main + 0x113DE68, o)), v)
    x = m.u64(o + 0x20)
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(x + 0x20) + 0x10) + 0x30), ident)
    m.vcall_void(b, 0x550, 1, 1)
    return _tail(m, m.main + 0x119AFF0, m.u64(x + 0x18), 0x37, ident, 1, 1)


@lifted(0x1144DF8)
def battler_faints(m, o, out, rec, *_):
    """rec = {battler, byte announce, x}: when the battler is not yet marked fainted in [[o+0x10]+0x110]
    (0x287b7a4) and vf 0x200 says it is down, run the faint: 0x288dbd0, 0x14a07e0, 0x287f270, 0x1589990,
    the rule 0x49c bit 1 follow-up 0x11519ac, 0x1536f5c when announced, the raid boss steps (class
    0x46d3f08 with +0x714 set), command 0x94, the rule 0x499 bit 2 flag 8 (vf 0x550 + command 0x37), then
    0x1360214 .. 0x2836f48; out = 1 when it ran."""
    b = m.u64(rec)
    tbl = m.u64(m.u64(o + 0x10) + 0x110)
    ident = m.vcall(b, 0x98) & M32
    down = not m.call(m.main + 0x287B7A4, tbl, ident) & 1 and m.vcall(b, 0x200) & 1
    if down:
        if _raid_class(m, b) and m.u8(b + 0x714):
            for a in (0x28426A8, 0x115044C, 0x187FE48):
                _need(m, m.main + a)
        if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49C) >> 1 & 1:
            _need(m, m.main + 0x11519AC)
    m.put(out, 1, 0)
    if not down:
        return
    x = m.u64(rec + 0x10)
    m.call_void(m.main + 0x288DBD0, m.u64(o + 0x20), b, x)
    m.call_void(m.main + 0x14A07E0, o, m.u64(rec + 0x10))
    m.call_void(m.main + 0x287F270, o, m.u64(rec + 0x10), b)
    m.call_void(m.main + 0x1589990, o, tbl, ident)
    if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49C) >> 1 & 1:
        x24 = m.u64(o + 0x10)
        i2 = m.vcall(b, 0x98) & M32
        p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(x24 + 0x290) + 8) + 0x50), i2)
        if p and m.u32(p) == 1 and m.vcall(b, 0x200) & 1:
            m.call_void(m.main + 0x11519AC, m.u64(m.u64(o + 0x78) + 0x1F80))
    if m.u8(rec + 8):
        q = m.u64(o + 0x20)
        m.call_void(m.main + 0x1536F5C, q, m.vcall(b, 0x98) & M32, b, 0)
    if _raid_class(m, b) and m.u8(b + 0x714) and m.vcall(b, 0x588) & 1:
        with m.frame(0x20) as f:
            m.put(f + 0x10, 8, b); m.put(f + 0x18, 1, 0)
            m.call_void(m.main + 0x28426A8, m.u64(m.u64(o + 0x78) + 0x1480), f + 8, f + 0x10)
    w24 = m.vcall(b, 0x478) & M32
    m.vcall_void(b, 0x470)
    w25 = m.call(m.main + 0x15C0434, o, ident, w24) & 1
    m.call_void(m.main + 0x119AFF0, m.u64(m.u64(o + 0x20) + 0x18), 0x94, ident, 0)
    if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x499) >> 2 & 1:
        x26 = m.u64(o + 0x20)
        bb = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(x26 + 0x20) + 0x10) + 0x30), ident)
        m.vcall_void(bb, 0x550, 8, 1)
        m.call_void(m.main + 0x119AFF0, m.u64(x26 + 0x18), 0x37, ident, 8, 1)
    m.call_void(m.main + 0x1360214, o, b)
    m.call_void(m.main + 0x2836D2C, m.u64(o + 0x38), ident)
    if _raid_class(m, b) and m.u8(b + 0x714):
        m.call_void(m.main + 0x115044C, m.u64(o + 0x20), m.vcall(b, 0x98) & M32)
        h = m.u16(b + 0x710)
        skip = False
        if h == 0x3F3:
            if m.u16(b + 0x718) == m.u16(b + 0x712):
                skip = True
            else:
                m.call_void(m.main + 0x187FE48, m.u64(o + 0x20), m.vcall(b, 0x98) & M32, m.u16(b + 0x712), 0)
                h = m.u16(b + 0x710)
        if not skip and h == 0x3FD and m.u16(b + 0x718) != m.u16(b + 0x712):
            m.call_void(m.main + 0x187FE48, m.u64(o + 0x20), m.vcall(b, 0x98) & M32, m.u16(b + 0x712), 0)
    m.call_void(m.main + 0x147AC20, m.u64(o + 0x20), ident)
    m.call_void(m.main + 0x1148894, m.u64(o + 0x48), ident)
    m.call_void(m.main + 0x149FDF4, o, b)
    m.call_void(m.main + 0x287F3D4, o, b)
    if w25:
        m.call_void(m.main + 0x1437580, m.u64(o + 0x20), w24)
    m.call_void(m.main + 0x287F878, o, ident)
    m.call_void(m.main + 0x162B7F0, o, ident, w24)
    m.call_void(m.main + 0x2836F48, m.u64(o + 0x38), ident)
    m.put(out, 1, 1)


def _faint_one(m, o, b, kind, rec, out):
    """0x1144bd8([o+0x38], b's id, kind), then 0x1144df8([[o+0x78]+0x400]) on {b, announce 1, 0}."""
    m.call_void(m.main + 0x1144BD8, m.u64(o + 0x38), m.vcall(b, 0x98) & M32, kind)
    m.put(rec, 8, b); m.put(rec + 8, 1, 1); m.put(rec + 0x10, 8, 0)
    m.call_void(m.main + 0x1144DF8, m.u64(m.u64(o + 0x78) + 0x400), out, rec)


@lifted(0x1145690)
def raid_faints(m, o, kind_ptr, *_):
    """The raid case of 0x11449f4: each standing member, fastest first, that is one of the raid
    record's entries ([o+0x48] +8, stride 0x8c, count byte +0x2420) faints through 0x1144df8."""
    with m.frame(0xE0) as f:
        lst, pl, rec, out = f, f + 0xB0, f + 0xB8, f + 0xD0
        _standing_by_speed(m, o, lst, pl, out)
        r = m.call(m.main + 0x1149340, o)
        n = m.u8(lst + 0xA6)
        m.put(lst + 0xA8, 1, 0)
        if n == 0:
            return
        b = m.u64(lst)
        m.put(lst + 0xA8, 1, 1)
        while b:
            ident = m.vcall(b, 0x98) & M32
            if any(m.u32(r + 8 + 0x8C * k) == ident for k in range(m.u8(r + 0x2420))):
                _faint_one(m, o, b, m.u16(kind_ptr), rec, out)
            i = m.u8(lst + 0xA8)
            if i >= m.u8(lst + 0xA6):
                return
            m.put(lst + 0xA8, 1, i + 1)
            b = m.u64(lst + 8 * i)


@lifted(0x11449F4)
def faint_pass(m, o, out, kind_ptr, *_):
    """After an action of kind u16 [kind_ptr]: 0x1144bd8 with id 0, then (raid kind 0xf4: 0x1145690)
    every standing member, fastest first, goes through 0x1144df8 until the battle ends ([[o+0x40]+0x28]
    reads 8, or 0x114a808 and 0x13603fc both hold); out = 0x113fa64's answer."""
    m.call_void(m.main + 0x1144BD8, m.u64(o + 0x38), 0, m.u16(kind_ptr))
    if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x499) >> 2 & 1 and m.u16(kind_ptr) == 0xF4:
        return _tail(m, m.main + 0x1145690, o, kind_ptr)

    def over():
        return m.call(m.main + 0x114A808, o) & 1 and m.call(m.main + 0x13603FC, o) & 1

    with m.frame(0xE0) as f:
        lst, pl, rec, res = f, f + 0xB0, f + 0xB8, f + 0xD0
        if over():
            m.call_void(m.main + 0x113FA64, m.u64(m.u64(o + 0x78) + 0x2A0), pl, lst)
            m.put(out, 1, m.u8(pl))
            return
        _standing_by_speed(m, o, lst, pl, res)
        n = m.u8(lst + 0xA6)
        m.put(lst + 0xA8, 1, 0)
        b = m.u64(lst) if n else 0
        if b:
            m.put(lst + 0xA8, 1, 1)
        while b:
            _faint_one(m, o, b, m.u16(kind_ptr), rec, res)
            if m.u8(m.u64(m.u64(o + 0x40) + 0x28)) == 8 or over():
                break
            i = m.u8(lst + 0xA8)
            if i >= m.u8(lst + 0xA6):
                break
            m.put(lst + 0xA8, 1, i + 1)
            b = m.u64(lst + 8 * i)
        m.call_void(m.main + 0x113FA64, m.u64(m.u64(o + 0x78) + 0x2A0), res, rec)
        m.put(out, 1, m.u8(res))


@lifted(0x153379C)
def faint_after_move(m, o, _x, r, *_):
    """r = {targets, {_, u16 move at +2}, move record, user, u8 count}: after 0x153391c's check (true:
    0x1536f20 on the user), each target faints through 0x1144df8 with announce = record byte +5 and
    x = {user, move}, then the user with announce 1."""
    x22 = m.u64(m.u64(o + 0x78) + 0x260)
    user = m.u64(r + 0x18)
    if m.call(m.main + 0x153391C, m.u64(x22 + 0x38), user, m.u64(r + 8)) & 1:
        m.call_void(m.main + 0x1536F20, x22, user)
    with m.frame(0x40) as f:
        rec, s, out = f, f + 0x18, f + 0x28
        n = m.u8(r + 0x20)
        if n:
            announce = m.u8(m.u64(r + 0x10) + 5)
            i = 0
            while i < n:
                m.put(s, 8, m.u64(r + 0x18)); m.put(s + 8, 2, m.u16(m.u64(r + 8) + 2))
                m.put(rec, 8, m.u64(m.u64(r) + 8 * i)); m.put(rec + 8, 1, announce); m.put(rec + 0x10, 8, s)
                m.call_void(m.main + 0x1144DF8, m.u64(m.u64(o + 0x78) + 0x400), out, rec)
                i += 1
                n = m.u8(r + 0x20)
        m.put(rec, 8, m.u64(r + 0x18)); m.put(rec + 8, 1, 1); m.put(rec + 0x10, 8, 0)
        m.call_void(m.main + 0x1144DF8, m.u64(m.u64(o + 0x78) + 0x400), s, rec)


@lifted(0x2888690)
def faint_battler(m, o, b, *_):
    """0x1144df8(0x114389c([o+0x78])) on {b, announce 1, 0}."""
    with m.frame(0x20) as f:
        m.put(f + 8, 8, b); m.put(f + 0x10, 1, 1); m.put(f + 0x18, 8, 0)
        m.call_void(m.main + 0x1144DF8, m.call(m.main + 0x114389C, m.u64(o + 0x78)), f, f + 8)


@lifted(0x1536F20)
def faint_battler_of(m, o, b, *_):
    """0x1144df8(0x114389c(0x1361214(o))) on {b, announce 1, 0}."""
    with m.frame(0x20) as f:
        m.put(f + 8, 8, b); m.put(f + 0x10, 1, 1); m.put(f + 0x18, 8, 0)
        x = m.call(m.main + 0x114389C, m.call(m.main + 0x1361214, o))
        m.call_void(m.main + 0x1144DF8, x, f, f + 8)


@lifted(0x1532FE4)
def faint_user_if(m, o, user, x, *_):
    """When 0x153391c([[[o+0x78]+0x260]+0x38], user, x) holds: 0x1536f20 on the user."""
    t = m.u64(m.u64(o + 0x78) + 0x260)
    r = m.call(m.main + 0x153391C, m.u64(t + 0x38), user, x)
    if not r & 1:
        return r
    return _tail(m, m.main + 0x1536F20, t, user)
