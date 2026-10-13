"""A battler's stored Pokemon: the 0x148-byte core record (encryption constant at +0, flags at +4,
checksum at +6, four 0x50-byte blocks from +8 shuffled by (EC >> 13) & 31, the whole tail XORed by
an LCG seeded with the EC) and the 16-byte party record, behind an accessor object:

    +0x08  party record      +0x10  core record     +0x18  u8 encrypted     +0x19  u8 keep plain
    +0x20  lock owner        +0x28  light event
"""

from pokeldn.sv.battle.engine.libc import FAKE_THREAD, signal_light_event
from pokeldn.sv.battle.machine import UnliftedCall, lifted

# Where logical block k sits for each shuffle value (0x3c62e18).
BLOCK_POSITION = (
    (0, 1, 2, 3), (0, 1, 3, 2), (0, 2, 1, 3), (0, 3, 1, 2), (0, 2, 3, 1), (0, 3, 2, 1),
    (1, 0, 2, 3), (1, 0, 3, 2), (2, 0, 1, 3), (3, 0, 1, 2), (2, 0, 3, 1), (3, 0, 2, 1),
    (1, 2, 0, 3), (1, 3, 0, 2), (2, 1, 0, 3), (3, 1, 0, 2), (2, 3, 0, 1), (3, 2, 0, 1),
    (1, 2, 3, 0), (1, 3, 2, 0), (2, 1, 3, 0), (3, 1, 2, 0), (2, 3, 1, 0), (3, 2, 1, 0),
    (0, 1, 2, 3), (0, 1, 3, 2), (0, 2, 1, 3), (0, 3, 1, 2), (0, 2, 3, 1), (0, 3, 2, 1),
    (1, 0, 2, 3), (1, 0, 3, 2))
BAD_RECORD_BLOCK = 0x47422E0          # a zero block in main's .bss, read for a record flagged bad
CORE, BLOCKS = 0x148, 8


def _lcg(seed):
    return (seed * 0x41C64E6D + 0x6073) & 0xFFFFFFFF


def _xor_words(m, address, count, seed):
    data = bytearray(m.read(address, 2 * count))
    for i in range(count):
        seed = _lcg(seed)
        v = (data[2 * i] | data[2 * i + 1] << 8) ^ (seed >> 16)
        data[2 * i], data[2 * i + 1] = v & 0xFF, v >> 8
    m.write(address, bytes(data))


def _checksum(m, core):
    data = m.read(core + BLOCKS, CORE - BLOCKS)
    return sum(data[i] | data[i + 1] << 8 for i in range(0, len(data), 2)) & 0xFFFF


def _crypt(m, acc):
    core, party = m.u64(acc + 0x10), m.u64(acc + 8)
    ec = m.u32(core)
    _xor_words(m, core + BLOCKS, (CORE - BLOCKS) // 2, ec)
    if party:
        _xor_words(m, party, 8, ec)


def block(m, core, logical):
    """Address of logical block `logical` of a plain core record."""
    if m.u8(core + 4) >> 2 & 1:
        return m.main + BAD_RECORD_BLOCK
    return core + BLOCKS + 0x50 * BLOCK_POSITION[(m.u32(core) >> 13) & 0x1F][logical]


def access(m, acc, read):
    """Lock the record, decrypt it, call read(core), encrypt it again as the game does, unlock."""
    if m.u64(acc + 0x20) != 0:
        raise UnliftedCall("pokemon record already locked")
    m.put(acc + 0x20, 8, FAKE_THREAD)
    if m.u8(acc + 0x18):
        _crypt(m, acc)
        m.put(acc + 0x18, 1, 0)
        core = m.u64(acc + 0x10)
        if m.u16(core + 6) != _checksum(m, core):
            m.put(core + 4, 2, m.u16(core + 4) | 4)
    value = read(m.u64(acc + 0x10))
    if m.u8(acc + 0x18) == 0 and m.u8(acc + 0x19) == 0:
        core = m.u64(acc + 0x10)
        if core:
            m.put(core + 6, 2, _checksum(m, core))
            ec = m.u32(core)
            _xor_words(m, core + BLOCKS, (CORE - BLOCKS) // 2, ec)
        party = m.u64(acc + 8)
        if party and m.u64(acc + 0x10):
            _xor_words(m, party, 8, m.u32(m.u64(acc + 0x10)))
        m.put(acc + 0x18, 1, 1)
    m.put(acc + 0x20, 8, 0)
    signal_light_event(m, acc + 0x28)
    return value


@lifted(0xBF4CFC)
def is_egg(m, acc, *_):
    """Bit 30 of the IV word (block B +0x34)."""
    return access(m, acc, lambda core: m.u32(block(m, core, 1) + 0x34) >> 30 & 1)
