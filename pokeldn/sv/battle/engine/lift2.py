"""Lifted battle server functions, batch 2 (moved to their topic module once reviewed)."""

from pokeldn.sv.battle.machine import FUNCTIONS, Pair, UnliftedCall, lifted
from pokeldn.sv.battle.engine.containers import battler


def _tail(m, address, *args):
    """A tail call: the callee's result, or None when the callee is void."""
    fn = FUNCTIONS.get(address - m.main)
    if fn is None:
        raise UnliftedCall(f"main+0x{address - m.main:x}")
    return fn(m, *args)


def _need(m, address):
    """Refuse the round before any write when a callee reached later is not lifted."""
    if address - m.main not in FUNCTIONS:
        raise UnliftedCall(f"main+0x{address - m.main:x}")


def _vtail(m, obj, slot, *args):
    return _tail(m, m.u64(m.u64(obj) + slot), obj, *args)


def _main_battler(m, o, ident):
    return battler(m, m.u64(m.u64(o + 0x10) + 0x30), ident)


@lifted(0x14C7890)
def is_1_or_6(m, v, *_): return int(v & 0xFF in (1, 6))


@lifted(0x114B1D4)
def u16_at_0(m, p, *_): return m.u16(p)


@lifted(0x17CE3AC)
def low7_of_2(m, p, *_): return int(m.u8(p + 2) & 0x7F != 0)


@lifted(0x1149380)
def entry_of_five(m, o, i, *_):
    i &= 0xFF
    return m.u64(o + 8 + 8 * i) if i < 5 else 0


@lifted(0x11494E8)
def set_entry_of_five(m, o, i, v, *_):
    i &= 0xFF
    if i < 5:
        m.put(m.u64(m.u64(o + 0x10) + 0x210) + 8 + 8 * i, 8, v & 0xFFFFFFFF)


def _kind(kind, address):
    def fn(m, out, *_):
        m.put(out, 4, kind)
        return m.main + address
    return fn


# Type descriptors: store a kind, return a rodata address. (function, kind, address)
for _addr, _kind_v, _ret in ((0x2D18260, 1, 0x44FAC10), (0x2D187A0, 1, 0x44FAF00), (0x2D17240, 3, 0x44FA8A0),
                             (0x2D17840, 1, 0x44F9750), (0x2D180E0, 1, 0x44FAA40)):
    lifted(_addr)(_kind(_kind_v, _ret))


@lifted(0x139B698)
def current_c4_entry(m, o, *_):
    base = m.u64(m.u64(o + 0x40) + 8)
    return base + m.u8(base + 0x938) * 0xC4 + 8


@lifted(0x1143AB8)
def battler_set_5a0(m, o, ident, i, v, *_):
    b = _main_battler(m, o, ident)
    return _vtail(m, b, 0x530, i & 0xFFFFFFFF, v & 0xFFFFFFFF)


@lifted(0x183F194)
def battler_4f8(m, o, ident, a, b2, *_):
    b = _main_battler(m, o, ident)
    return _vtail(m, b, 0x4F8, a & 0xFFFFFFFF, b2)


@lifted(0x288CE48)
def battler_398(m, o, ident, *_):
    return _vtail(m, _main_battler(m, o, ident), 0x398)


@lifted(0x14375B4)
def battler_4a0(m, o, ident, *_):
    b = _main_battler(m, o, ident)
    if b == 0:
        return
    return _vtail(m, b, 0x4A0)


@lifted(0x2D3BAE0)
def species_402_406(m, b, *_):
    p = m.u64(b + 0x700)
    return m.u16(b + 0x402) if p and m.u32(p + 0xB8) else m.u16(b + 0x406)


@lifted(0x1381400)
def has_id(m, o, ident, *_): return int(m.call(m.main + 0x1381420, o, ident) & 0xFF != 10)


@lifted(0x114A934)
def first_byte_of_2a0(m, o, *_):
    with m.frame(0x10) as p:
        m.call_void(m.main + 0x113FA64, m.call(m.main + 0x114A964, m.u64(o + 0x78)), p, p + 8)
        return m.u8(p)


@lifted(0x1820E4C)
def next_serial(m, o, out, *_):
    v = m.u32(o + 8)
    if v == 0:
        v = 1
        m.put(o + 8, 4, 1)
    m.put(out, 4, v)
    m.put(o + 8, 4, m.u32(o + 8) + 1)


@lifted(0x114E498)
def entry_38(m, o, i, *_):
    i &= 0xFF
    return 0 if i > 4 else m.u64(m.u64(o + 0x10) + 0x30) + i * 0x38 + 0x28


@lifted(0x2D14150)
def clear_core_48(m, b, *_): m.put(m.u64(b + 0x48) + 0x48, 4, 0)


@lifted(0x10E2474)
def copy_5(m, dst, src, *_):
    m.put(dst, 4, m.u32(src)); m.put(dst + 4, 1, m.u8(src + 4))


@lifted(0x15808D0)
def init_0x19(m, p, *_):
    m.write(p, bytes(0x18)); m.put(p + 0x18, 1, 1)


@lifted(0x2880944)
def clear_0x24b(m, p, *_): m.write(p, bytes(0x24))


@lifted(0xF53840)
def static_4765a30(m, *_):
    """A function-local static, built on first use; the engine only reads one already built."""
    if m.u8(m.main + 0x4765A38) & 1 == 0:
        raise UnliftedCall("static 0x4765a30 not built")
    return m.main + 0x4765A30


@lifted(0x2D1FF04)
def static_46dcd58(m, *_):
    """A function-local static (guard and storage reached through the GOT); read only once built."""
    if m.u8(m.u64(m.main + 0x46DCD50)) & 1 == 0:
        raise UnliftedCall("static 0x46dcd58 not built")
    return m.u64(m.main + 0x46DCD58)


@lifted(0x284DB90)
def handler_with_key(m, o, ident, key, *_):
    """The first kind-2 handler of `ident` whose u16 (0xf7bb74) is `key`, or 0."""
    owner = m.call(m.main + 0x114C158, o)
    h = m.call(m.main + 0x119B478, owner, 2, ident & 0xFF)
    while h and m.call(m.main + 0xF7BB74, h) & 0xFFFF != key & 0xFFFFFFFF:
        h = m.call(m.main + 0x1155BDC, owner, h, 0)
    return h


@lifted(0x13DC030)
def release_matching(m, o, pokemon, key, *_):
    """Walk the kind-0 handlers of the Pokemon's id (0x119b478 over [[o+8]+0xd0]) and, for each one
    whose u16 +0x30 is `key`, +0x68 clear and +0x44 set, release it (+0x3f clear) or retire it."""
    table = m.u64(m.u64(o + 8) + 0xD0)
    cur = m.call(m.main + 0x119B478, table, 0, m.vcall(pokemon, 0x98) & 0xFFFFFFFF)
    while cur:
        kind, ident = m.u8(cur + 0x28), m.u32(cur + 0x34)
        nxt = cur
        while True:
            nxt = m.call(m.main + 0xF7BA54, m.u64(nxt + 8), m.u16(nxt + 0x14))
            if nxt == 0 or (m.u8(nxt + 0x28) == kind and m.u32(nxt + 0x34) == ident
                            and m.u8(nxt + 0x41) == 0):
                break
        if m.u16(cur + 0x30) == key & 0xFFFF and m.u32(cur + 0x68) == 0 and m.u8(cur + 0x44):
            if m.u8(cur + 0x3F) == 0:
                m.call_void(m.main + 0x13608E0, m.u64(m.u64(o + 8) + 0xD0), cur)
            else:
                m.call_void(m.main + 0x1360CDC, cur, 1)
        cur = nxt




@lifted(0x157B674)
def move_blocked(m, o, attacker, target, move, *_):
    def cond(c): return m.vcall(target, 0x300, c) & 1
    if cond(0xB) and m.call(m.main + 0x157B7A0, m.u16(move)) & 1:
        return 1
    if cond(7) and m.u16(move) in (0x14F, 0xD4):
        return 1
    if cond(0xE) and m.u16(move) == 0x149:
        return 1
    a = m.vcall(attacker, 0x98) & 0xFFFFFFFF
    t = m.vcall(target, 0x98) & 0xFFFFFFFF
    if cond(0x10) and m.u8(move + 0x12) and m.call(m.main + 0x15C04A4, o, a, t) & 1 == 0:
        return 1
    return 0


@lifted(0x15F9F38)
def check_kind_4(m, o, flag, a, b, kind, result, *_):
    m.put(flag, 1, 0)
    kind &= 0xFF
    result &= 0xFFFFFFFF
    with m.frame(0x30) as p:
        if result & 0xFF == 0:
            if kind == 4:
                m.put(p, 8, b); m.put(p + 8, 1, 1)
                q = m.call(m.main + 0x15FA02C, m.call(m.main + 0x1361214, o))
                m.call_void(m.main + 0x15FA034, q, p + 0x20, p)
                if m.u8(p + 0x20) == 0:
                    return 7
            return 0
        if kind == 4:
            m.put(p, 8, b); m.put(p + 8, 1, 0)
            q = m.call(m.main + 0x15FA02C, m.call(m.main + 0x1361214, o))
            m.call_void(m.main + 0x15FA034, q, p + 0x20, p)
            if m.u8(p + 0x20) and m.call(m.main + 0x15FA528, m.u64(o + 0x38), a, b) & 1 == 0:
                m.put(flag, 1, 1)
                return 0
        return result


@lifted(0x113F4F8)
def settle_state(m, o, *_):
    r = m.call(m.main + 0x113F5B8, m.call(m.main + 0x114E480, o))
    if r & 1:
        return r
    if m.call(m.main + 0x113F630, m.call(m.main + 0x113F5B0, m.call(m.main + 0x1482534, o))) & 1 == 0:
        e = m.call(m.main + 0x113F5B0, m.call(m.main + 0x1482534, o))
        r = m.call(m.main + 0x113F5C8, e, 0)
        if r & 0xFF == 0:
            return r
    a = m.call(m.main + 0x114E480, o)
    flag = m.call(m.main + 0x114E550, a, m.call(m.main + 0x1482534, o)) & 1
    x = m.call(m.main + 0x1143584, o)
    m.call_void(m.main + (0x1148C58 if flag else 0x114C994), x)
    m.call_void(m.main + 0x113F5F0, o)
    p = m.call(m.main + 0x113DE70, m.call(m.main + 0x113DE68, o))
    m.put(p, 1, 2)   # tail call to 0x113fa5c, a byte store returning its pointer
    return p


@lifted(0x28858AC)
def push_pair(m, o, a, b, *_):
    with m.frame(0x20) as p:
        m.put(p, 1, 0)
        m.put(p + 8, 4, a); m.put(p + 0xC, 4, b)
        m.put(p + 0x10, 2, 0); m.put(p + 0x12, 1, 0); m.put(p + 0x14, 2, 0)
        return _tail(m, m.main + 0x121BDB0, m.call(m.main + 0x114E520, m.u64(o + 0x78)), p, p + 8)


@lifted(0xF70010)
def remaining_90(m, o, *_):
    if m.u32(o + 0x70) != 1:
        return 0
    n = m.u32(o + 0x90)
    v = m.vcall(m.call(m.main + 0xF6FC68, o), 0x108) & 0xFFFF
    if n <= v:
        return 0
    n = m.u32(o + 0x90)
    return (n - (m.vcall(m.call(m.main + 0xF6FC68, o), 0x108) & 0xFFFF)) & 0xFFFFFFFF


def _static_46d3f08(m):
    """The address of the static built by 0x1a07aa4; the engine only reads one already built."""
    if m.u8(m.u64(m.main + 0x46D3F00)) & 1 == 0:
        raise UnliftedCall("static 0x46d3f08 not built")
    return m.u64(m.main + 0x46D3F08)


def _has_static(m, obj):
    """Whether the list returned by the first virtual of the subobject at +0x28 holds that static."""
    node = m.vcall(obj + 0x28, 0)
    target = _static_46d3f08(m)
    while node:
        if node == target:
            return True
        node = m.u64(node)
    return False


@lifted(0x11502BC)
def mark_flagged(m, o, *_):
    if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49A) >> 1 & 1 == 0:
        return
    with m.frame(0xC0) as p:
        it = p + 0x10
        m.call_void(m.main + 0x1143D84, it)
        m.put(p + 8, 8, it)
        m.call_void(m.main + 0x1143DF0, m.call(m.main + 0x1143DE8, m.u64(o + 0x78)), p, p + 8)
        m.call_void(m.main + 0x1143D7C, it)
        pk = m.call(m.main + 0x158003C, it)
        while pk:
            if m.call(m.main + 0x1142E68, m.u64(o + 8), m.u64(o + 0x10), pk) & 1 == 0 and _has_static(m, pk):
                if m.call(m.main + 0x1680124, pk) & 1 and m.vcall(pk, 0x510, 0x19) & 1:
                    t = m.u64(o + 0x20)
                    m.call_void(m.main + 0x115044C, t, m.vcall(pk, 0x98) & 0xFFFFFFFF)
                    t = m.u64(o + 0x20)
                    m.call_void(m.main + 0x115043C, t, m.vcall(pk, 0x98) & 0xFFFFFFFF)
            pk = m.call(m.main + 0x158003C, it)


@lifted(0x1533284)
def flag_type_match(m, o, pk, move, *_):
    if not _has_static(m, pk):
        return
    f714 = m.u8(pk + 0x714)
    if f714 == 0 and m.vcall(pk, 0x4D0, 0x1C) & 1 == 0:
        return
    b = m.u8(pk + 0x715)
    t = m.u8(move + 8)
    expect = b if b < 0x13 else 0x12     # the table at 0x3c630a1 (step 2) maps 0..0x12 to itself
    if t == 0x12 or t != expect:
        if b != 0x63:
            return
        r = m.call(m.main + 0x2D2219C, pk, t, m.u16(move))
        if r & 0xFF == 0x12:
            return
        shift = 0x1F if r & 0xFF == 0x63 else r & 0x1F
        if m.u32(pk + 0x71C) >> shift & 1:
            return
    base = m.u64(m.u64(o + 0x40) + 8)
    m.put(base + m.u8(base + 0x938) * 0xC4 + 0x1F, 1, 1)


@lifted(0x2D1F784)
def has_type(m, b, t, *_):
    t &= 0xFF
    if t == 0x12:
        return 0
    r = m.vcall(b, 0x220, 0x19) & 1
    c1, c2 = m.u8(b + 0x40A), m.u8(b + 0x40B)
    a = c1 == 0x12 or (r and c1 == 2)
    z = c2 == 0x12 or (r and c2 == 2)
    if m.vcall(b, 0x4D0, 0x17) & 1:
        if not a:
            if z:
                c2 = c1
        elif not z:
            c1 = c2
        else:
            c1 = c2 = 0x12
    elif a:
        c1 = c2 = 0 if z else c2
    elif z:
        c2 = c1
    return int(c1 == t or c2 == t)


@lifted(0x1148948)
def find_after(m, o, after, ident, *_):
    """The first entry (0x8c bytes from +8, count at +0x2420) past `after` whose u32 is `ident`, or 0."""
    n = m.u8(o + 0x2420)
    d = (after - o + 0x84) & 0xFFFFFFFFFFFFFFFF
    i = 0
    while True:
        if n == i:
            k = n
            break
        i += 1
        d = (d - 0x8C) & 0xFFFFFFFFFFFFFFFF
        if d == 0:
            k = i
            break
    ident &= 0xFFFFFFFF
    for j in range(k & 0xFF, n):
        e = o + 8 + 0x8C * j
        if m.u32(e) == ident:
            return e
    return 0


@lifted(0x147ACC4)
def clear_id(m, o, ident, *_):
    """Clear the first of ten (u32 id, flag byte) entries from +8 that is flagged and holds `ident`."""
    ident &= 0xFFFFFFFF
    for i in range(10):
        if m.u8(o + 0xC + 8 * i) and m.u32(o + 8 + 8 * i) == ident:
            m.put(o + 8 + 8 * i, 4, 0)
            return


@lifted(0x13607C0)
def release_battler(m, o, ident, *_):
    b = _main_battler(m, o, ident)
    return _tail(m, m.main + 0x1360B30, m.u64(o + 0x18), b)


@lifted(0x1380DB8)
def count_sign(m, o, e, n, *_):
    """Signal the sign of `n` (0x15 positive, 0x16 negative) to [e+8] through slot 0x508, unless the
    byte at e+0x10 is 8."""
    if m.u8(e + 0x10) == 8:
        return
    n &= 0xFFFFFFFF
    if n == 0:
        return
    return _vtail(m, m.u64(e + 8), 0x508, 0x16 if n & 0x80000000 else 0x15)


@lifted(0x13616F0)
def remove_id(m, o, i, ident, *_):
    """Drop `ident` from list i (0..13): flag at +0xa8+4i, count at +0x70+4i, ten u32 slots at
    +0xe0+0x2c*i. Returns 1 when the list became empty and was cleared."""
    i &= 0xFFFFFFFF
    if (i ^ 0x80000000) - 0x80000000 > 0xD:
        return 0
    flag, count = o + 0xA8 + 4 * i, o + 0x70 + 4 * i
    if m.u32(flag) == 0:
        return 0
    n = m.u32(count)
    arr = o + 0x2C * i + 0xE0
    ident &= 0xFFFFFFFF
    for j in range(n):
        if m.u32(arr + 4 * j) == ident:
            break
    else:
        return 0
    if j <= 9:
        k = j
        if j & 1:
            m.put(arr + 4 * j, 4, m.u32(arr + 4 * j + 4))
            k = j + 1
        if j != 9:
            for off in range(4 * k, 0x28, 8):
                a, b = m.u32(arr + off + 4), m.u32(arr + off + 8)
                m.put(arr + off, 4, a); m.put(arr + off + 4, 4, b)
        j = 10
    n = (n - 1) & 0xFFFFFFFF
    m.put(arr + 4 * j, 4, 0)
    m.put(count, 4, n)
    pair = o + 8 + 0x10 * i + 0x340
    if n == 0:
        m.write(pair, bytes(0x10))
        m.put(o + 4 * i + 0x38, 4, 0)
        m.put(count, 4, 0); m.put(flag, 4, 0)
        m.put(arr + 0x28, 4, 0)
        m.write(arr, bytes(0x28))
        return 1
    if m.call(m.main + 0x184A110, pair) & 0xFFFFFFFF == ident:
        m.call_void(m.main + 0x28787A0, pair, m.u32(arr))
    return 0


def _standing(m, o):
    """Each party member still in the battle, as the server's inlined iterator (0x1147774 then the
    0x1360dbc step) hands them out."""
    from pokeldn.sv.battle.engine.flow import first_standing, next_standing
    with m.frame(0x28) as it:
        m.put(it, 8, m.u64(m.main + 0x46E2580) + 0x10)
        m.put(it + 8, 8, m.u64(o + 8)); m.put(it + 0x10, 8, m.u64(o + 0x10))
        m.put(it + 0x18, 2, 0); m.put(it + 0x1A, 1, 1)
        first_standing(m, it)
        while next_standing(m, it, it + 0x20):
            yield m.u64(it + 0x20)


def _rule_499_bit2(m, o):
    return m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x499) >> 2 & 1


@lifted(0x1141160)
def standing_condition_c(m, o, *_):
    if _rule_499_bit2(m, o):
        return
    for b in _standing(m, o):
        if m.vcall(b, 0x4D0, 0xC) & 1:
            m.call_void(m.main + 0x1140198, m.u64(o + 0x20), b, 0xC)
            m.call_void(m.main + 0x1148470, m.u64(o + 0x20), b, 0x13)


@lifted(0x114140C)
def note_standing_ids(m, o, *_):
    """Add each standing member's id to the byte list at [[o+0x40]+0x68] (30 bytes from +8, count +0x28)."""
    if _rule_499_bit2(m, o):
        return
    for b in _standing(m, o):
        v = m.vcall(b, 0x98) & 0xFFFFFFFF
        t = m.u64(m.u64(o + 0x40) + 0x68)
        if m.call(m.main + 0x114E624, t, v) & 1 == 0:
            n = m.s(t + 0x28, 4)
            if n <= 0x1D:
                m.put(t + 8 + n, 1, v)
                m.put(t + 0x28, 4, m.u32(t + 0x28) + 1)


@lifted(0x2D3B780)
def bump_490(m, b, *_):
    """Raise the byte counter behind slots 0x490 (get) and 0x498 (set) by one, unless it is 0xff."""
    v = m.vcall(b, 0x490)
    if ~v & 0xFF == 0:
        return
    return _vtail(m, b, 0x498, (v + 1) & 0xFFFFFFFF)


@lifted(0x13B1F10)
def move_field_6(m, key_holder, *_):
    """Field 6 (a byte) of the record for the u16 id at key_holder+8; 0x65 reads as 0x64."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.containers import data_record
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    v = fb.u8(m, data_record(m, table, m.u16(key_holder + 8)), 6)
    return 0x64 if v == 0x65 else v


@lifted(0x1365E90)
def clients_off_side(m, mode, rule, pos, *_):
    """How many of the clients 0..4 present in this mode (0xe7e2a0) map to a class other than the one
    of `pos` (tables 0x3c6a450 / 455 / 45a, 2 outside them)."""
    from pokeldn.sv.battle.engine.getters import _MODE_TABLES
    raw = (mode, rule)
    mode &= 0xFFFFFFFF; rule &= 0xFFFFFFFF; pos &= 0xFFFFFFFF
    n = 0
    for c in range(5):
        if m.call(m.main + 0xE7E2A0, *(raw if c == 0 else (mode, rule)), c) & 1 == 0:
            continue
        if mode not in _MODE_TABLES or 4 < (pos ^ 0x80000000) - 0x80000000:
            side = 2
        elif pos < 5:
            side = _MODE_TABLES[mode][pos]
        else:
            side = m.u8(m.main + 0x3C6A450 + 5 * mode + pos)
        n += side != (_MODE_TABLES[mode][c] if mode in _MODE_TABLES else 2)
    return n & 0xFF


def _keyed(m, address, key):
    """Call `address` with a stack object (vtable [0x46ddad8]+0x10, u16 key at +8)."""
    with m.frame(0x10) as p:
        m.put(p, 8, m.u64(m.main + 0x46DDAD8) + 0x10)
        m.put(p + 8, 2, key)
        return m.call(m.main + address, p)


@lifted(0x1382AB0)
def keyed_flag(m, key, *_): return _keyed(m, 0x1382AE8, key) & 1


@lifted(0x20FB1A8)
def keyed_byte(m, key, *_):
    return (((_keyed(m, 0x20FB1E0, key) & 0xFF) ^ 0x80) - 0x80) & 0xFFFFFFFF


@lifted(0x2D3C9E0)
def spend_pp(m, b, i, n, *_):
    """Take n PP from move slot i (current +0x432, floored at 0); a slot flagged at +0x43a also sets
    +0x428 and tells the Pokemon object (slot 0x118)."""
    s = b + 0x16 * (i & 0xFF)
    n &= 0xFF
    if m.u8(s + 0x43A):
        _need(m, m.u64(m.u64(m.u64(b + 0x48)) + 0x118))
    left = (max(m.u8(s + 0x432), n) - n) & 0xFFFFFFFF
    m.put(s + 0x432, 1, left)
    if m.u8(s + 0x43A) == 0:
        return
    m.put(s + 0x428, 1, left)
    return _vtail(m, m.u64(b + 0x48), 0x118, i, left)


@lifted(0x174AE20)
def queue_0x13(m, o, a, b, src, *_):
    with m.frame(0x10) as p:
        m.put(p, 4, 0); m.put(p + 8, 8, 0)
        m.call_void(m.main + 0x174AE90, src, p + 0xC, p + 8, p)
        return _tail(m, m.main + 0x119AFF0, o, 0x13, a & 0xFFFFFFFF, b & 0xFF, m.u32(p + 0xC), m.u32(p + 8),
                     m.u32(p))


@lifted(0x171A850)
def battler_1c0(m, o, ident, a, b, *_):
    bt = _main_battler(m, o, ident)
    if bt == 0:
        return
    return _vtail(m, bt, 0x1C0, a & 0xFFFFFFFF, b & 0xFFFFFFFF)


@lifted(0x1820EB8)
def append_entry(m, o, src, *_):
    """Copy an entry into the next free 0x8c-byte slot (from +8, count at +0x2420, at most 0x42)."""
    n = m.u8(o + 0x2420)
    if n > 0x41:
        return 0
    e = o + 0x8C * n
    m.write(e + 8, m.read(src, 0x54))
    m.put(e + 0x5C, 8, m.u64(src + 0x54))
    m.put(e + 0x64, 1, m.u8(src + 0x5C))
    m.write(e + 0x68, m.read(src + 0x60, 0x24))     # 0x1820f40: a 0x24-byte memcpy
    m.put(e + 0x8C, 8, m.u64(src + 0x84))
    m.put(o + 0x2420, 1, m.u8(o + 0x2420) + 1)
    return 1


@lifted(0x1872CE0)
def check_1640(m, o, b, *_):
    with m.frame(0x18) as p:
        m.put(p + 8, 8, b); m.put(p + 0x10, 1, 0)
        q = m.call(m.main + 0x1872D18, m.call(m.main + 0x1361214, o))
        m.call_void(m.main + 0x1872D20, q, p, p + 8)
        return m.u8(p)


@lifted(0x1148894)
def mark_id_entries(m, o, ident, *_):
    """For the first entry (0x8c bytes from +8) holding `ident`: set its +0x89, then +0x81 of every
    later entry holding it."""
    ident &= 0xFFFFFFFF
    for i in range(m.u8(o + 0x2420)):
        e = o + 8 + 0x8C * i
        if m.u32(e) == ident:
            m.put(e + 0x89, 1, 1)
            e = find_after(m, o, e, ident)
            while e:
                m.put(e + 0x81, 1, 1)
                e = find_after(m, o, e, ident)
            return


@lifted(0x2D19610)
def advance_2d0(m, o, ident, *_):
    s = m.u64(m.u64(o + 0x38) + 0x78)
    p = m.u64(s + 0x20)
    if (m.u32(p + 0xC) if p else 0) != ident & 0xFFFFFFFF:
        return
    q = m.u64(s + 0x2D0)
    if q == 0 or m.u8(q + 0xA) > 1:
        return
    m.put(q + 0xC, 4, 1)
    if m.u8(q + 0xA) == 1:
        m.put(q + 0xA, 1, 2)


@lifted(0x288818C)
def mark_bits(m, o, out, row, bits, *_):
    """For each of 19 indexes set in the bit field `bits` (byte count, then the bytes) that 0x28883a0
    accepts, set out[row*0x13 + i]; 1 if any was set."""
    row &= 0xFFFFFFFF
    base = out + 0x13 * (row & 0xFF)
    hit = 0
    for i in range(0x13):
        k = (i >> 3) + 1
        if k < m.u8(bits) and m.u8(bits + k) >> (i & 7) & 1 \
                and m.call(m.main + 0x28883A0, o, row, i) & 1:
            hit = 1
            m.put(base + i, 1, 1)
    return hit


@lifted(0x157BF08)
def remove_member(m, lst, b, *_):
    """Take a battler out of a member list (pointers from +0, count +0xa6), closing the gap; the byte
    at +0xa8 drops by one too."""
    n = m.u8(lst + 0xA6)
    for i in range(n):
        if m.u64(lst + 8 * i) != b:
            continue
        cur = n
        if i + 1 < n:
            m.put(lst + 8 * i, 8, m.u64(lst + 8 * i + 8))
            cur = m.u8(lst + 0xA6)
            j = i
            while j + 2 < cur:
                m.put(lst + 8 * j + 8, 8, m.u64(lst + 8 * j + 0x10))
                cur = m.u8(lst + 0xA6)
                j += 1
        m.put(lst + 0xA6, 1, cur - 1)
        m.put(lst + 0xA8, 1, m.u8(lst + 0xA8) - 1)
        return


@lifted(0x2D2219C)
def effective_type(m, b, t, move, *_):
    """The type a move takes: 0x1f for moves 0x353 and 0x38a (the latter when vf 0x88(0x3fd)) on a
    battler holding the static, flagged at +0x714 and with 0x63 at +0x715; else `t`."""
    t &= 0xFFFFFFFF
    if not _has_static(m, b) or m.u8(b + 0x714) == 0 or m.u8(b + 0x715) != 0x63:
        return t
    move &= 0xFFFF
    if move == 0x353:
        return 0x1F
    if move == 0x38A:
        return 0x1F if m.vcall(b, 0x88, 0x3FD) & 1 else t
    return t


@lifted(0x115043C)
def queue_bd(m, o, arg, *_):
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xBD, arg & 0xFFFFFFFF)


@lifted(0x1360CDC)
def set_41(m, e, v, *_): m.put(e + 0x41, 1, v & 1)


@lifted(0x157B7A0)
def move_check_157fc44(m, move, *rest):
    return _tail(m, m.main + 0x157FC44, move, *rest[:6])


@lifted(0x15FA034)
def check_b0(m, o, out, arg, *_):
    if m.u32(m.u64(m.u64(o + 0x10) + 0x70) + 0xB0):
        m.put(out, 1, 0)
        return
    r = m.call(m.main + 0x15FA084, m.u64(o + 0x38), m.u64(arg), m.u8(arg + 8))
    m.put(out, 1, r & 1)     # the game clears `out` before the call; the callee never sees it


@lifted(0xFECB7C)
def rule_allows_move(m, b, *_):
    """0 when the battler has no rule object (+0x700), its move (+0x47e) has field 6 set, or the
    shared object at [+0x708]+0x190 answers the 0x50fc5612cd4b7875 query; else whether [+0x700]+0xcc
    is set."""
    if m.u64(b + 0x700) == 0:
        return 0
    with m.frame(0x10) as p:
        m.put(p, 8, m.u64(m.main + 0x46DDAC0) + 0x10)
        m.put(p + 8, 2, m.u16(b + 0x47E))
        if m.call(m.main + 0xFECCD8, p) & 1:
            return 0
    holder = m.u64(b + 0x708)
    v = m.vcall(b, 0x2B8, m.u64(b + 0x700)) & 0xFFFFFFFF
    obj = m.u64(holder + 0x190)
    if obj:
        _need(m, m.u64(m.u64(obj) + 0x28))
        count = m.u32(obj + 0x28)
        if count == 0xFFFFFFFF:
            raise UnliftedCall("reference counter overflow abort")
        m.put(obj + 0x28, 4, count + 1)
    r = m.vcall(obj, 0x28, 0x50FC5612CD4B7875, v)
    if obj:
        count = m.u32(obj + 0x28)
        if count == 0:
            raise UnliftedCall("reference counter underflow abort")
        m.put(obj + 0x28, 4, count - 1)
        if count == 1:
            m.vcall_void(obj, 0x10)
    if r & 1:
        return 0
    return int(m.u32(m.u64(b + 0x700) + 0xCC) != 0)


@lifted(0x11521A0)
def shared_148(m, o, *_):
    """The object at [[o+8]+0x48]+0x148, after taking and dropping a reference on its control block
    (+0x30: object +0x10, u16 count +0x1a); the first reference builds +8, the last releases (vf 0x50)."""
    obj = m.u64(m.u64(m.u64(o + 8) + 0x48) + 0x148)
    if obj == 0:
        return 0
    ctl = m.u64(obj + 0x30)
    inner = m.u64(ctl + 0x10)
    if inner == 0:
        raise UnliftedCall("AddReference abort: m_object is null")
    count = m.u16(ctl + 0x1A)
    if count == 0xFFFF:
        raise UnliftedCall("AddReference abort: counter overflow")
    if count == 0:
        _need(m, m.u64(m.u64(inner)))
    m.put(ctl + 0x1A, 2, count + 1)
    if count == 0:
        m.put(ctl + 8, 8, m.vcall(inner, 0))
        m.put(ctl + 0x1C, 4, 0xFFFFFFFE)
    ctl = m.u64(obj + 0x30)
    count = m.u16(ctl + 0x1A)
    if count == 0:
        raise UnliftedCall("ReleaseReference abort: counter underflow")
    m.put(ctl + 0x1A, 2, count - 1)
    if count == 1:
        m.put(ctl + 0x10, 8, 0)
        m.vcall_void(obj, 0x50)
    return obj


# Stat stage multipliers (numerator, denominator) for stages 0..12, the table at 0x3c69d73.
_STAGE = ((2, 8), (2, 7), (2, 6), (2, 5), (2, 4), (2, 3), (2, 2), (3, 2), (4, 2), (5, 2), (6, 2), (7, 2), (8, 2))
# Stat id -> (getter slot, stage byte) for the staged stats (jump tables 0x3c6b49f / 0x3c6b4ae).
_STAGED = {8: (0xC0, 0x414), 9: (0xC8, 0x415), 10: (0xD0, 0x416), 11: (0xD8, 0x417), 12: (0xE0, 0x418)}


@lifted(0x2D3B894)
def stat_value(m, b, which, *_):
    """Stat `which`: 1..7 the signed stage bytes +0x414..+0x41a, 8..12 a stat (vf 0xc0..0xe0) times
    its stage, 13 / 14 the u16 at +0x5a / +0x58, 15 the byte at +0x62. With a rule object (+0x700)
    whose +0xb8 is set, 9 and 11 trade places."""
    which &= 0xFFFFFFFF
    if not 1 <= which <= 15:
        return 0
    if which <= 7:
        return (((m.u8(b + 0x413 + which) ^ 0x80) - 0x80) & 0xFFFFFFFF)
    if which == 13:
        return m.u16(b + 0x5A)
    if which == 14:
        return m.u16(b + 0x58)
    if which == 15:
        return m.u8(b + 0x62)
    rule = m.u64(b + 0x700)
    if rule and which in (9, 11) and m.u32(rule + 0xB8):
        which = 20 - which
    slot, stage = _STAGED[which]
    v = m.vcall(b, slot) & 0xFFFFFFFF
    s = m.u8(b + stage)
    if s <= 12:
        num, den = _STAGE[s]
        v = ((v * num) & 0xFFFF) // den
    return v & 0xFFFF


def _s32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


def _class_of(m, mode, i):
    """Entry i of the mode's five-entry class table (0x3c6a450 + 5 * mode), indexed as a u32."""
    from pokeldn.sv.battle.engine.getters import _MODE_TABLES
    i &= 0xFFFFFFFF
    return _MODE_TABLES[mode][i] if i < 5 else m.u8(m.main + 0x3C6A450 + 5 * mode + i)


@lifted(0x1365B00)
def nth_client_off_side(m, mode, rule, pos, nth, *_):
    """Walking the clients after `pos` ((pos + k) % 5), the (nth % count)-th present one whose class
    differs from pos's, counting with 0x1365e90; 5 when there is none."""
    n = m.call(m.main + 0x1365E90, mode, rule, pos, nth) & 0xFF
    nth &= 0xFF
    target = nth % n if n else nth
    mode &= 0xFFFFFFFF; rule &= 0xFFFFFFFF
    p = _s32(pos)
    count = 0
    for k in range(5):
        s = _s32(p + k)
        c = (s - int(s / 5) * 5) & 0xFFFFFFFF
        if c == pos & 0xFFFFFFFF or m.call(m.main + 0xE7E2A0, mode, rule, c) & 1 == 0 or mode > 2:
            continue
        mine = _class_of(m, mode, p) if p <= 4 else 2
        if mine == _class_of(m, mode, c):
            continue
        if count == target:
            return c
        count = (count + 1) & 0xFFFFFFFF
    return 5


def _negative_field(index):
    """The record's signed byte field `index`, negated when below zero, else 0."""
    def fn(m, key_holder, *_):
        from pokeldn.sv.battle.engine import flatbuffer as fb
        from pokeldn.sv.battle.engine.containers import data_record
        from pokeldn.sv.battle.engine.data import static_table
        table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
        v = fb.u8(m, data_record(m, table, m.u16(key_holder + 8)), index)
        return (0x100 - v) if v & 0x80 else 0
    return fn


lifted(0x1419734)(_negative_field(15))
lifted(0x141A340)(_negative_field(16))


@lifted(0x287B2D4)
def count_outcome(m, counters, pokecon, attacker, target, kind, *_):
    """Count one outcome in the u16 counters (at most 9999): +8 / +0xc / +0xa by `kind` (0, below 8,
    8 and up; 7 is not counted) on one side, +0xe / +0x12 / +0x10 on the other, picked by the two
    battlers' classes in the setup's map; nothing when 0x118ab58 holds or both classes are set."""
    a = m.vcall(attacker, 0x98) & 0xFFFFFFFF
    t = m.vcall(target, 0x98) & 0xFFFFFFFF

    def cls(ident):
        p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(pokecon + 0x290) + 8) + 0x50), ident)
        return 0 if p == 0 or m.s(p, 4) >= 5 else m.u32(p) & 0xFF
    ca, ct = cls(a), cls(t)
    r = m.call(m.main + 0x118AB58, m.u64(pokecon + 0x290), a, t)
    kind &= 0xFF
    if r & 1 or (ca and ct):
        return
    offs = (8, 0xC, 0xA) if ca == 0 else (0xE, 0x12, 0x10)
    if kind == 7:
        return
    at = counters + (offs[0] if kind == 0 else offs[1] if kind < 8 else offs[2])
    v = m.u16(at)
    if v <= 0x270E:
        m.put(at, 2, v + 1)


@lifted(0xF6DD84)
def queue_low_hp(m, o, b, *_):
    """With fewer than four entries queued (+0x7c), queue a kind-3 entry (+0x5c + 8n) for a battler
    whose share (0xf91070, in percent of [[o+8]+0x290]+0x10 +0x8a) is at most 10, then OR in the
    0xf6f87c, 0xf6fa5c and 0xf6de7c checks."""
    if m.u32(o + 0x7C) > 3:
        return 0
    f = m.call(m.main + 0xF6F87C, o, b) & 1
    if b and m.u8(m.u64(m.u64(o + 8) + 0x310) + 0x8D) == 0:
        pc = m.u64(m.u64(o + 8) + 0x290)
        s = m.u16(m.u64(pc + 0x10) + 0x8A)
        low = True
        if s:
            r = m.call(m.main + 0xF91070, b, s, m.s(m.u64(m.u64(pc + 8) + 0x1B0) + 8, 2) & 0xFFFFFFFFFFFFFFFF)
            d = m.u16(m.u64(pc + 0x10) + 0x8A)
            q = ((r * 100) & 0xFFFFFFFFFFFFFFFF) // d if d else 0
            low = q & 0xFFFFFFFF <= 10
        if low:
            f = 1
            n = m.u32(o + 0x7C)
            if n <= 3:
                m.put(o + 8 * n + 0x5C, 1, 3)
                m.put(o + 8 * n + 0x60, 4, 1)
                m.put(o + 0x7C, 4, m.u32(o + 0x7C) + 1)
    a = m.call(m.main + 0xF6FA5C, o, b)
    c = m.call(m.main + 0xF6DE7C, o, b)
    return (c | a | f) & 1


def _queue_id_kind(kind):
    """Hand (battler id, kind) to 0x17776d8 on the object at [o+0x78]+0x2e0."""
    def fn(m, o, b, *_):
        ident = m.vcall(b, 0x98)
        with m.frame(0x10) as p:
            m.put(p + 8, 4, ident); m.put(p + 0xC, 1, kind)
            m.call_void(m.main + 0x17776D8, m.call(m.main + 0x17776D0, m.u64(o + 0x78)), p, p + 8)
    return fn


lifted(0x177767C)(_queue_id_kind(4))
lifted(0x114B5DC)(_queue_id_kind(1))


@lifted(0x288C710)
def forward_28787e0(m, o, v, pair, *_):
    return _tail(m, m.main + 0x28787E0, m.u64(m.u64(o + 0x10) + 0x70), v, m.u64(pair), m.u64(pair + 8))


@lifted(0x1480A6C)
def make_entry(m, o, kind, value, src, b, *_):
    """A 16-byte entry returned in x0 and x1: x0 = value (its upper half as 0x179372c leaves it), x1 = 1
    for kinds 1 and 3..5, for kind 2: 2 with 0x179405c of the battler's two 0x68 reads in bits 3..8."""
    with m.frame(0x10) as p:
        m.call_void(m.main + 0x179372C, p)
        k = kind & 0xFFFF
        m.put(p + 8, 8, 0)
        if 3 <= k <= 5 or k == 1:
            hi = 1
        elif k == 2:
            x = m.vcall(b, 0x68, m.u64(m.main + 0x46E25C8)) & 0xFFFFFFFF
            y = m.vcall(b, 0x68, m.u64(m.main + 0x46E25D0)) & 0xFFFFFFFF
            m.put(p, 4, value)
            m.put(p + 8, 8, 2)
            r = m.call(m.main + 0x179405C, src, x, y)
            hi = (2 & ~0x1F8) | ((r & 0x3F) << 3)
        else:
            hi = 0
        m.put(p + 8, 8, hi)
        m.put(p, 4, value)
        return Pair(m.u64(p), hi)


@lifted(0x17CE148)
def flag_battler_entry(m, o, ident, *_):
    return _tail(m, m.main + 0x17CE178, o, _main_battler(m, o, ident))


@lifted(0x17CE178)
def flag_entry_of(m, o, b, *_):
    """Flag the battler's entry in its class's row of the table at [o+0x10]+0x250."""
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    pokecon = m.u64(o + 0x10)
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(pokecon + 0x290) + 8) + 0x50), ident)
    cls = 0 if p == 0 or m.s(p, 4) >= 5 else m.u32(p)
    return _tail(m, m.main + 0x17CE1E4, m.u64(m.u64(o + 0x10) + 0x250), cls, ident)


@lifted(0x17CE1E4)
def flag_entry(m, table, row, ident, *_):
    """In row `row` (0..4, 0x60 bytes) set the flag byte (+0xc) of the first of six 16-byte entries
    from +0x10 whose u32 is `ident`."""
    row &= 0xFF
    if row > 4:
        return
    ident &= 0xFFFFFFFF
    for k in range(1, 7):
        e = table + 0x60 * row + 0x10 * k
        if m.u32(e) == ident:
            m.put(e + 0xC, 1, 1)
            return


@lifted(0x286FE20)
def double_on_condition(m, o, ident, *_):
    s = m.u64(m.u64(o + 0x38) + 0x78)
    p = m.u64(s + 0x20)
    if (m.u32(p + 0xC) if p else 0) != ident & 0xFFFFFFFF:
        return
    q = m.u64(s + 0x28)
    b = battler(m, m.u64(m.u64(o + 8) + 0x30), m.u32(q + 0xC) if q else 0)
    if m.vcall(b, 0x230) & 0xFFFF == 0 and m.vcall(b, 0x228, 1) & 1 == 0:
        return
    return _tail(m, m.main + 0x181D0D0, o, 2)


@lifted(0x283D690)
def mode_class_of(m, o, key, *_):
    return _tail(m, m.main + 0x144E790, m.u64(m.u64(o + 8) + 0x290), key)


# Index -> (value, value with a second argument; -1 means none), from the tables at 0x3c6afa0 and
# 0x3c6af36 (rows of three s16) for the indexes the mask 0x140465cff admits.
_COMMAND_VALUES = {0: (94, 297), 1: (105, 298), 2: (99, 299), 3: (89, 300), 4: (83, 296), 5: (118, 301),
                   6: (114, 302), 7: (126, 126), 10: (191, -1), 11: (194, -1), 12: (199, -1), 14: (284, -1),
                   17: (126, 126), 18: (239, -1), 22: (187, -1), 30: (216, -1), 32: (362, -1)}


@lifted(0x114A970)
def build_command(m, kind, src, arg, extra, out, *_):
    """Fill a message header at `out` for kind 1..33: u16 id, u16 flags with the argument count in
    bits 7..13, then u32 arguments; kind 0x12 adds 0x49, kind 8 adds 0xf7ffe0 of `src`."""
    w8 = (kind - 1) & 0xFFFFFFFF
    i = w8 & 0xFFFF
    if i > 0x20 or not (0x140465CFF >> (w8 & 63)) & 1:
        return 0
    a, b = _COMMAND_VALUES[i]
    extra &= 0xFFFF
    v = b if extra else a
    if v < 0:
        v = a
    hi = m.u16(out + 2) & 0xC000
    m.put(out, 2, v)
    flags = hi | 0x82
    m.put(out + 2, 2, flags)
    m.put(out + 4, 4, arg)
    if extra:
        flags = hi | 0x102
        m.put(out + 2, 2, flags)
        m.put(out + 8, 4, extra)
    k = kind & 0xFFFF
    n = flags >> 7 & 0x7F
    if k == 0x12 and n <= 7:
        m.put(out + 2, 2, ((flags + 0x80) & 0x3F80) | (flags & 0xC07F))
        m.put(out + 4 * n + 4, 4, 0x49)
    elif k == 8 and n <= 7:
        r = m.call(m.main + 0xF7FFE0, src)
        m.put(out + 2, 2, ((flags + 0x80) & 0x3F80) | (flags & 0xC07F))
        m.put(out + 4 * n + 4, 4, r & 0xFFFF)
    return 1


@lifted(0x287B8E0)
def map_at_u32(m, table, key_ptr, *_):
    """unordered_map<u32, ...>::at: the value (node+0x14) for the u32 at key_ptr; a missing key throws."""
    from pokeldn.sv.battle.engine.containers import find
    node = find(m, table, m.u32(key_ptr), 4)
    if not node:
        raise UnliftedCall("unordered_map::at of a missing key (throws)")
    return node + 0x14


@lifted(0x1794620)
def record_byte_11(m, key_holder, *_):
    """The byte 4 past field 11 of the record for the u16 id at key_holder+8; the field is read without
    a vtable size check."""
    from pokeldn.sv.battle.engine.containers import data_record
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    rec = data_record(m, table, m.u16(key_holder + 8))
    return m.u8(rec + m.u16(rec - m.s(rec, 4) + 0x1A) + 4)


def _triple_byte(k):
    """Byte k of the i-th (0..2) three-byte entry at field 18 of the record for the u16 id at
    key_holder+8; the field is read without a vtable size check."""
    def fn(m, key_holder, i, *_):
        from pokeldn.sv.battle.engine.containers import data_record
        from pokeldn.sv.battle.engine.data import static_table
        i &= 0xFF
        if i > 2:
            return 0
        table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
        rec = data_record(m, table, m.u16(key_holder + 8))
        return m.u8(rec + m.u16(rec - m.s(rec, 4) + 0x28) + 3 * i + k)
    return fn


lifted(0x1771130)(_triple_byte(1))
lifted(0x1384070)(_triple_byte(2))


@lifted(0x115B968)
def form_record_u16(m, key_holder, *_):
    """The u16 at +0xa past field 0 of the record keyed by u16(+8) * 10000 + u16(+0xa) in the static
    table 0x46d7438 (its default at +0xd0); the field is read without a vtable size check."""
    from pokeldn.sv.battle.engine.containers import find
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7430, 0x46D7438, 0x46D7440)
    key = m.u16(key_holder + 8) * 10000 + m.u16(key_holder + 0xA)
    node = find(m, table + 0x68, key, 8)
    rec = m.u64(node + 0x18) if node else m.u64(table + 0xD0)
    return m.u16(rec + m.u16(rec - m.s(rec, 4) + 4) + 0xA)


def _ref_take(m, obj):
    count = m.u32(obj + 0x28)
    if count == 0xFFFFFFFF:
        raise UnliftedCall("reference counter overflow abort")
    m.put(obj + 0x28, 4, count + 1)


def _ref_drop(m, obj):
    count = m.u32(obj + 0x28)
    if count == 0:
        raise UnliftedCall("reference counter underflow abort")
    m.put(obj + 0x28, 4, count - 1)
    if count == 1:
        m.vcall_void(obj, 0x10)


@lifted(0x28764E0)
def base_damage(m, o, p, *_):
    """The damage formula over (power, level, attack, defense) at p: ((2 * level / 5 + 2) * power *
    attack / defense) / 50 + 2, unless the reference-counted object at +0x128 holds a replacement
    function (+0x30, called with its +0x50)."""
    obj = m.u64(o + 0x128)
    if obj:
        fn = m.u64(obj + 0x30)
        if m.u32(obj + 0x28) == 0:
            _need(m, m.u64(m.u64(obj) + 0x10))
        if fn:
            _need(m, fn)
        _ref_take(m, obj)
        fn = m.u64(obj + 0x30)
        _ref_drop(m, obj)
        if fn:
            obj = m.u64(o + 0x128)
            _ref_take(m, obj)
            r = m.call(m.u64(obj + 0x30), obj + 0x50, p) & 0xFFFFFFFF
            _ref_drop(m, obj)
            return r
    power, level, attack, defense = m.u32(p), m.u32(p + 4), m.u32(p + 8), m.u32(p + 0xC)
    v = (attack * power * ((((level << 1) & 0xFFFFFFFF) // 5 + 2) & 0xFFFFFFFF)) & 0xFFFFFFFF
    v = v // defense if defense else 0
    return (v // 50 + 2) & 0xFFFFFFFF


@lifted(0x1147754)
def standing_iterator(m, it, setup, pokecon, *_):
    """Build the standing-member iterator (vtable main+0x4500bb0) and point it at the first member."""
    m.put(it + 0x18, 2, 0)
    m.put(it, 8, m.main + 0x4500BB0)
    m.put(it + 0x1A, 1, 1)
    m.put(it + 8, 8, setup); m.put(it + 0x10, 8, pokecon)
    return _tail(m, m.main + 0x1147774, it)


@lifted(0x1148DF8)
def note_and_queue_74(m, o, a, b, c, *_):
    m.call_void(m.main + 0x288D134, m.u64(o + 0x20), a, b, c)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x74, a & 0xFFFFFFFF, b & 0xFF, c & 0xFFFF)


@lifted(0x11438E4)
def use_counter(m, o, b, i, a, c, d, *_):
    """Count down the battler's counter i (vf 0x540); when it reaches zero queue the two 0x74
    messages for `a` and `c` with 0x171a7ec(0x32) and hand `d` to 0x171a604."""
    i &= 0xFFFFFFFF
    if m.vcall(b, 0x540, i) & 0xFF == 0:
        return
    n = (m.vcall(b, 0x540, i) - 1) & 0xFFFFFFFF
    m.call_void(m.main + 0x1143A30, m.call(m.main + 0x1143584, o), b, i, n)
    if n & 0xFF:
        return
    v = m.call(m.main + 0x171A7EC, 0x32) & 0xFFFFFFFF
    for arg in (a, c):
        x = m.call(m.main + 0x1143584, o)
        m.call_void(m.main + 0x1148DF8, x, m.vcall(b, 0x98) & 0xFFFFFFFF, arg & 0xFFFFFFFF, v)
    x = m.call(m.main + 0x1143584, o)
    return _tail(m, m.main + 0x171A604, x, m.vcall(b, 0x98) & 0xFFFFFFFF, d & 0xFFFFFFFF, 0xFF)


@lifted(0x171A604)
def queue_bf(m, o, a, b, c, *_):
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xBF, a & 0xFFFFFFFF, b & 0xFF, c & 0xFF)


@lifted(0x171A6DC)
def queue_73_pair(m, o, b, kind, *_):
    """For kind 7 (stats 2 and 4) or 6 (stats 1 and 3), hand the battler's id with each stat and
    0x171a7ec(0x32) to 0x171a804."""
    v = m.call(m.main + 0x171A7EC, 0x32) & 0xFFFFFFFF
    kind &= 0xFFFFFFFF
    if kind == 7:
        stats = (2, 4)
    elif kind == 6:
        stats = (1, 3)
    else:
        return
    x = m.call(m.main + 0x1143584, o)
    m.call_void(m.main + 0x171A804, x, m.vcall(b, 0x98) & 0xFFFFFFFF, stats[0], v)
    x = m.call(m.main + 0x1143584, o)
    return _tail(m, m.main + 0x171A804, x, m.vcall(b, 0x98) & 0xFFFFFFFF, stats[1], v)


@lifted(0x287EE68)
def queue_ca(m, o, a, b, *_):
    return _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), 0xCA, a & 0xFFFFFFFF, b & 0xFFFF, 0xFFFF0000)


@lifted(0x287F270)
def raise_on_species_271(m, o, holder, pk, *_):
    """When the Pokemon holds the static, is species 0x271 (+0x710) and the 0x4690abda0b4ec6c4 query
    holds, raise the holder's battler's stat 3 by one (vf 0x550) and queue message 0x37."""
    if holder == 0 or pk == 0 or m.u64(holder) == 0:
        return
    if not _has_static(m, pk) or m.u16(pk + 0x710) != 0x271:
        return
    v = m.vcall(pk, 0x2A8) & 0xFFFFFFFF
    if m.call(m.main + 0x151BB5C, m.u64(o + 8), 0x4690ABDA0B4EC6C4, v) & 1 == 0:
        return
    ident = m.vcall(m.u64(holder), 0x98) & 0xFFFFFFFF
    q = m.u64(o + 0x20)
    b = battler(m, m.u64(m.u64(m.u64(q + 0x20) + 0x10) + 0x30), ident)
    m.vcall_void(b, 0x550, 3, 1)
    return _tail(m, m.main + 0x119AFF0, m.u64(q + 0x18), 0x37, ident, 3, 1)


@lifted(0x157EBC0)
def push_terminated(m, que, command, *varargs):
    """The variadic push whose u32 arguments end at 0xffff0000: the format byte (+0x12) of the
    command's node in the queue's map at +0 (0 when absent), then 0x119bf58 over the arguments."""
    from pokeldn.sv.battle.engine.containers import find_u16
    node = find_u16(m, que, command)
    fmt = m.u8(node + 0x12) if node else 0
    with m.frame(0x40) as arr:
        m.write(arr, bytes(0x40))
        for k, v in enumerate(varargs):
            v &= 0xFFFFFFFF
            m.put(arr + 4 * k, 4, v)
            if v == 0xFFFF0000:
                break
        return _tail(m, m.main + 0x119BF58, que, command, fmt, arr)


# The allocator's size classes between 0x221 and 0xaa0 (the constants compared in 0xee5860).
_SIZE_CLASSES = (0x240, 0x260, 0x270, 0x280, 0x2A0, 0x2D0, 0x2E0, 0x300, 0x330, 0x360, 0x380, 0x3B0, 0x400,
                 0x450, 0x490, 0x4C0, 0x550, 0x600, 0x660, 0x6D0, 0x800, 0x990, 0xAA0)


@lifted(0xEE5860)
def size_class(m, size, align, *_):
    """The allocation size for `size` at alignment `align` (clamped to 0x10..0x1000): rounded up to the
    alignment, then above 0x1e0 to the first size class the alignment divides, else to a page."""
    M = 0xFFFFFFFFFFFFFFFF
    a = align if align < 0x1000 else 0x1000
    a = a if a > 0x10 else 0x10
    r = size % a
    n = ((a - r if r else 0) + size) & M
    if a == 0x1000 or n < 0x1E1:
        return n
    if n == 0x1F0:
        return 0x200
    if n < 0x221:
        return n
    for c in _SIZE_CLASSES:
        if n <= c and c % a == 0:
            return c
    return ((0x1000 - (n & 0xFFF) if n & 0xFFF else 0) + n) & M


@lifted(0xBF44F4)
def species(m, acc, *_):
    """The species: the u16 at the start of block A."""
    from pokeldn.sv.battle.engine.pokemon import access, block
    return access(m, acc, lambda core: m.u16(block(m, core, 0)))


@lifted(0x287A8C0)
def form_check_133b78c(m, b, *_):
    core = m.u64(b + 0x48)
    r = m.call(m.main + 0x103B8A0, m.u64(core + 0x70))
    if r & 0xFFFF < 0x137:
        return r
    s = m.call(m.main + 0xBF44F4, m.u64(core + 0x70))
    f = m.call(m.main + 0xBF41A8, m.u64(core + 0x70))
    g = m.call(m.main + 0xD99784, core)
    return _tail(m, m.main + 0x133B78C, s & 0xFFFFFFFF, f & 0xFFFFFFFF, g & 0xFFFFFFFF)


@lifted(0x1793E94)
def packed_move_info(m, key, *_):
    """Bits 0..3: 0x1794478 of the record for u16 `key`; when it is non-zero, bits 4..9 0x1794620 and
    bits 10..15 0x17947c8."""
    with m.frame(0x10) as p:
        m.put(p, 8, m.u64(m.main + 0x46DDAD8) + 0x10)
        m.put(p + 8, 2, key)
        r = m.call(m.main + 0x1794478, p)
        v = r & 0xF
        if r & 0xFF:
            a = m.call(m.main + 0x1794620, p)
            c = m.call(m.main + 0x17947C8, p)
            v = v | (a & 0x3F) << 4 | (c & 0x3FFFFF) << 10
        return v & 0xFFFF


@lifted(0x287A68C)
def core_b80208(m, b, *_):
    return _tail(m, m.main + 0xB80208, m.u64(m.u64(b + 0x48) + 0x70))


@lifted(0x1384028)
def keyed_triple_byte_2(m, key, i, *_):
    if i & 0xFFFFFFFF > 2:
        return 0
    with m.frame(0x10) as p:
        m.put(p, 8, m.u64(m.main + 0x46DDAD8) + 0x10)
        m.put(p + 8, 2, key)
        return m.call(m.main + 0x1384070, p, i) & 0xFF


@lifted(0x15C0434)
def other_side_target(m, o, a, t, *_):
    a &= 0xFFFFFFFF; t &= 0xFFFFFFFF
    if m.call(m.main + 0x15C04B0, m.u64(m.u64(o + 0x10) + 0x30), t) & 1 == 0:
        return 0
    if m.call(m.main + 0x15C04A4, o, a, t) & 1:
        return 0
    return int(t != 0 and t != a)


@lifted(0x1360CE8)
def release_condition_1a_of(m, o, pk, *_):
    """For each standing member under condition 0x1a whose condition value (vf 0x4f0) is the
    Pokemon's id, hand it to 0x287f998."""
    with m.frame(0x30) as p:
        it, out, holder = p, p + 0x20, p + 0x28
        m.put(holder, 8, o); m.put(out, 8, 0)
        a = m.call(m.main + 0x114E480, o)
        m.call_void(m.main + 0x1147754, it, a, m.call(m.main + 0x1482534, o))
        while m.call(m.main + 0x1360DBC, it, out) & 1:
            b = m.u64(out)
            if m.vcall(b, 0x4D0, 0x1A) & 1:
                v = m.u32(m.vcall(b, 0x4F0, 0x1A))
                if m.vcall(pk, 0x98) & 0xFFFFFFFF == v:
                    m.call_void(m.main + 0x287F998, holder, m.u64(out))


@lifted(0xD679F0)
def seal_record(m, acc, *_):
    """Under the record's lock clear keep-plain (+0x19) and, when the record is plain, store its
    checksum and encrypt the core and party records."""
    from pokeldn.sv.battle.engine.libc import FAKE_THREAD, signal_light_event
    from pokeldn.sv.battle.engine.pokemon import BLOCKS, CORE, _checksum, _xor_words
    if m.u64(acc + 0x20) != 0:
        raise UnliftedCall("pokemon record already locked")
    m.put(acc + 0x20, 8, FAKE_THREAD)
    m.put(acc + 0x19, 1, 0)
    if m.u8(acc + 0x18) == 0:
        core = m.u64(acc + 0x10)
        if core:
            m.put(core + 6, 2, _checksum(m, core))
            _xor_words(m, core + BLOCKS, (CORE - BLOCKS) // 2, m.u32(core))
        party = m.u64(acc + 8)
        if party and m.u64(acc + 0x10):
            _xor_words(m, party, 8, m.u32(m.u64(acc + 0x10)))
        m.put(acc + 0x18, 1, 1)
    m.put(acc + 0x20, 8, 0)
    return signal_light_event(m, acc + 0x28)


def _record_tail(target, deref=True):
    """A battler method that tail-calls `target` with its core (+0x48), or with the core's record
    accessor (+0x70) when `deref`, passing the caller's other arguments through."""
    def fn(m, b, *rest):
        core = m.u64(b + 0x48)
        return _tail(m, m.main + target, m.u64(core + 0x70) if deref else core, *rest[:6])
    return fn


for _addr, _target, _deref in ((0x287A8A8, 0xBEC030, True), (0x287A8B4, 0xD97B78, True),
                               (0x287A728, 0xE14B64, True), (0x287A734, 0xD97F14, False)):
    lifted(_addr)(_record_tail(_target, _deref))


@lifted(0x287A5B4)
def party_or_stored_c75438(m, b, *rest):
    """0xc75438 of the record accessor when it holds a party record, else 0xe13ef0 of the core."""
    core = m.u64(b + 0x48)
    acc = m.u64(core + 0x70)
    if m.u64(acc + 8):
        return _tail(m, m.main + 0xC75438, acc, *rest[:6])
    return m.call(m.main + 0xE13EF0, core, *rest[:6]) & 0xFFFF


@lifted(0x17D5D98)
def same_side_pair(m, o, a, b, *_):
    ia = m.vcall(a, 0x98) & 0xFFFFFFFF
    ib = m.vcall(b, 0x98) & 0xFFFFFFFF
    return _tail(m, m.main + 0x118AB58, m.u64(m.u64(o + 0x10) + 0x290), ia, ib)


@lifted(0x114B210)
def queue_cb(m, o, a, b, n, vals, *_):
    """Message 0xcb with `a`, `b` and the first n (1..4; otherwise none) u32 values at `vals`."""
    n &= 0xFFFFFFFF
    extra = [m.u32(vals + 4 * k) for k in range(n)] if 1 <= n <= 4 else []
    return _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), 0xCB, a & 0xFFFFFFFF, b & 0xFFFF, *extra,
                 0xFFFF0000)


@lifted(0x113AECC)
def side_of_c9c750(m, a, b, c, d, *_):
    """0x113a588 of (a, b, 0x113af40(a, b, k, 0), d), where k is 1, 0 or 2 for 0xc9c750's 0, 1 or
    anything else (table 0x3b72710)."""
    r = m.call(m.main + 0xC9C750, a, b, c, d) & 0xFF
    k = (1, 0)[r] if r <= 1 else 2
    s = m.call(m.main + 0x113AF40, a & 0xFFFFFFFF, b & 0xFFFFFFFF, k, 0)
    return _tail(m, m.main + 0x113A588, a & 0xFFFFFFFF, b & 0xFFFFFFFF, s & 0xFFFFFFFF, d & 0xFFFFFFFF)
