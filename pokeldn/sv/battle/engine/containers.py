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


def _lookup(base, size, value, load):
    def fn(m, owner, key, *_):
        node = find(m, owner + base, key & ((1 << 8 * size) - 1), size)
        if not node:
            return 0
        return m.u64(node + value) if load else node + value
    return fn


# Lookups of the same libc++ map shape: (map offset in the owner, key size, value offset, load).
for _addr, _spec in {0x10E2DD4: (8, 4, 0x14, False)}.items():
    lifted(_addr)(_lookup(*_spec))


@lifted(0x119B478)
def find_handler(m, owner, kind, ident, *_):
    """Walk the entry chain from the u16 key at owner+0x70: each node (map at its owner+8) names
    the next key (+0x2c) and owner (+0x20). The first live node (+0x5c set, +0x59 clear) whose kind
    byte (+0x40) and id (+0x4c) match is returned as node+0x18; 0 at the end of the chain."""
    kind &= 0xFF; ident &= 0xFFFFFFFF
    key, table = m.u16(owner + 0x70), owner + 8
    while key != 0xEE:
        node = find(m, table, key, 2)
        if not node:
            return 0
        if m.u8(node + 0x5C) and m.u8(node + 0x40) == kind and m.u32(node + 0x4C) == ident \
                and m.u8(node + 0x59) == 0:
            return node + 0x18
        key, table = m.u16(node + 0x2C), m.u64(node + 0x20) + 8
    return 0
