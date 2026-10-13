"""The server's round-level checks."""

from pokeldn.sv.battle.engine.slots import slot_matches
from pokeldn.sv.battle.machine import lifted


def party(m, parties, client):
    """(count, member list address) of a client's party in the party container."""
    base = parties + 0x38 * client
    return m.u8(base + 0x58), base + 0x28


def able_count(m, parties, client):
    n, members = party(m, parties, client)
    return sum(m.vcall(m.u64(members + 8 * i), 0x208) & 1 for i in range(n)) & 0xFF


@lifted(0x114A808)
def battle_continues(m, o, *_):
    """1 while every side still has a Pokemon able to fight (vf 0x208 of the party members)."""
    flags = m.u64(m.u64(m.u64(o + 8) + 0x38) + 0x498)
    pokecon = m.u64(o + 0x10)
    if flags >> 10 & 1 == 0:
        if flags >> 33 & 1:
            n, _ = party(m, m.u64(pokecon + 0x30), 0)
            if n == 0 or able_count(m, m.u64(pokecon + 0x30), 0) == 0:
                return 1
        if m.call(m.main + 0x10D3D7C, pokecon) & 1:
            return 1
        p = m.call(m.main + 0x10D3F10, m.u64(pokecon + 0x290))
        return 0 if p == 0 else (m.vcall(p, 0x208) ^ 1) & 1
    setup = m.u64(m.u64(pokecon + 0x290) + 8)
    mode, rule = m.u32(setup + 0x36C), m.u8(setup + 0x370)
    ours = 2 if mode > 2 else 1
    sides = (2 if mode > 2 else 0,
             2 if mode > 2 else 1,
             0 if mode in (1, 2) else 2,
             0 if mode == 2 else (1 if mode == 1 else 2),
             0 if mode == 2 else 2)
    parties = m.u64(pokecon + 0x30)
    for client in range(5):
        if slot_matches(m, mode, rule, client) & 1 and sides[client] == ours:
            n, _ = party(m, parties, client)
            if n and able_count(m, parties, client):
                return 0
    return 1


@lifted(0x1147774)
def first_standing(m, it, *_):
    """Point the iterator at the first party member of the first client (0..4) that is not out of
    the battle (vf 0x200): client at +0x18, index at +0x19; +0x1a stays 1 when there is none."""
    from pokeldn.sv.battle.engine.slots import positions_of_slot
    m.put(it + 0x1A, 1, 1); m.put(it + 0x18, 2, 0)
    pokecon = m.u64(it + 0x10)
    setup = m.u64(m.u64(pokecon + 0x290) + 8)
    for client in range(5):
        mode, rule = m.u32(setup + 0x36C), m.u8(setup + 0x370)
        if slot_matches(m, mode, rule, client) & 1 == 0:
            continue
        parties = m.u64(pokecon + 0x30)
        n = positions_of_slot(m, mode, rule, client)
        count, members = party(m, parties, client)
        for i in range(n):
            if i >= 0x100:
                break
            if i < count:
                b = m.u64(members + 8 * i)
                if b and m.vcall(b, 0x200) & 1 == 0:
                    m.put(it + 0x18, 1, client); m.put(it + 0x19, 1, i); m.put(it + 0x1A, 1, 0)
                    return
