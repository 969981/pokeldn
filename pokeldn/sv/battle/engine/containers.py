"""libc++ unordered_map lookups as the server compiles them: buckets at +0, bucket count at +8; a
node is (next, hash, key, value). A u16 key hashes to itself."""

from pokeldn.sv.battle.machine import UnliftedCall, lifted


def _bucket(h, n):
    return h & (n - 1) if n & (n - 1) == 0 else h % n


def find_u16(m, table, key):
    """The node holding the u16 `key`, or 0."""
    return find(m, table, key & 0xFFFF, 2)


def find(m, table, key, size):
    """The node holding `key` (a u16 or u32 at node+0x10), or 0."""
    n = m.u64(table + 8)
    if n == 0:
        return 0
    b = _bucket(key, n)
    node = m.u64(m.u64(table) + b * 8)
    if node == 0:
        return 0
    node = m.u64(node)
    while node:
        h = m.u64(node + 8)
        if h == key:
            if m.u(node + 0x10, size) == key:
                return node
        elif _bucket(h, n) != b:
            return 0
        node = m.u64(node)
    return 0


@lifted(0xF7BA54)
def find_value(m, owner, key, *_):
    """The value slot (+0x18) of the u16-keyed map at owner+8, or 0; key 0xee is never present."""
    key &= 0xFFFF
    if key == 0xEE:
        return 0
    node = find_u16(m, owner + 8, key)
    return node + 0x18 if node else 0


@lifted(0xFAF09C)
def format_slot(m, table, key_ptr, *_):
    """operator[] of the queue's command-format map: the value byte (+0x12) of the key's node. The
    engine never inserts: a missing key refuses the round."""
    node = find_u16(m, table, m.u16(key_ptr))
    if not node:
        raise UnliftedCall("command-format map insert")
    return node + 0x12


@lifted(0xF21C94)
def battler(m, owner, ident, *_):
    """The battler with id `ident` from the u32-keyed map at owner+0x140, or 0."""
    node = find(m, owner + 0x140, ident & 0xFFFFFFFF, 4)
    return m.u64(node + 0x18) if node else 0
