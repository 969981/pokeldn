"""What a battle session holds before the build steps run, made on an arena (`arena.new`): the data
tables in their function-local statics, the weak-handle table, the battle network object N (vtable
0x44ff468) and what hangs off it (docs/sv_raid.md, Reproducing a round).

The table creators are the game's (personal 0x164498c, id-hash 0x1730f6c); the files they load come
from the romfs as bytes (`files`), laid into the maps as the loaders leave them: each map reserved to
its record count, then filled in file order, the default record the one for key 0. The weak-handle
table is the game's (0x165dd08) with its growth paths (0xc1adec, 0xc1aa80, 0xb44724). N's own objects
come from a template (units of constants, links, handles) the caller supplies; the battle bootstrap
gives the party records, the seed, the time limits and the boss's action profile (`build_network`).
The named-parameter table at [N+0x48]+0x148 is laid out from (name hash, value) pairs
(`build_parameters`).
"""

import struct

from pokeldn.sv.battle.engine.steps import _create, _insert, _pop, _push, _rehash, _tls_stack, _tls_top
from pokeldn.sv.battle.machine import MASK, UnliftedCall, lifted

M64 = MASK[8]
ONE_F = 0x3F800000
MAX_NODES = 0x0FFFFFFFFFFFFFFF          # the map allocators' max_size

APPLICATION_NAME = 0x3B78D3D            # "Application"
APPLICATION_LIMIT = 0xA0000000

# name, static slot, GOT word of the slot, guard GOT word, file, key rule
TABLES = (
    ("personal", 0x47420B8, 0x46D7438, 0x46D7430, "avalon/data/personal_array.bin", "pair"),
    ("growth", 0x47420D8, 0x46DA7C8, 0x46DA7C0, "avalon/data/growTable.bin", None),
    ("moves", 0x4742568, 0x46D7948, 0x46D7940, "avalon/data/waza_array.bin", "u16"),
    ("abilities", 0x4742548, 0x46DDAB0, 0x46DDAA8, "avalon/data/tokusei_array.bin", "u16"),
)
IDHASH = ("idhash", 0x4734E50, 0x46D8908, 0x46D8900,
          "world/data/battle/battle_item_conversion/battle_item_conversion_array.bin")
IDHASH_HASHES = 0x3C61260               # 282 u64 name hashes, main .rodata [0x1821674]
IDHASH_ENTRIES = 282

# Objects the loaders make, as a snapshot holds them: vtable, the second vtable at +0x20, the word at
# +0x28, object size.
LAYOUT = {
    "growth": (0x44A8FA0, 0x44A8FD0, 0x4440090, 0x68),
    "moves": (0x44A9678, 0x44A96A8, 0x44A9658, 0xE0),
    "abilities": (0x44A9598, 0x44A95C8, 0x44A9578, 0xE0),
}
RESOURCE_VT = 0x4440368                 # the file resource [T+0x30]; vf 0x70 (0x92e438) returns +0x1f0
RESOURCE_SIZE = 0x210
FILES = 0x3000000000                    # where the loaded files sit: outside the game heap, never freed


def _fnv1a64(data):
    """FNV-1a 64 as the romfs names files."""
    h = 0xCBF29CE484222645           # the basis the game uses (tools/switch/trpfs_read.py)
    for c in data:
        h = ((h ^ c) * 0x100000001B3) & M64
    return h


# --- allocators -----------------------------------------------------------------------------------

@lifted(0x2A64D40)
def counted_type_node(m, *_):
    """The counted allocator's type node (its parent: 0x11e29ac's), built on first use."""
    from pokeldn.sv.battle.engine.arena import _node, type_node_allocator
    return _node(m, 0x46DD938, 0x46DD940, lambda: type_node_allocator(m))


@lifted(0x2A6487C)
def counted_sizes_kept(m, o, *_):
    """Whether a counted allocator keeps counts by size class: u8 +0x50."""
    return m.u8(o + 0x50)


def application_allocator(m):
    """The counted allocator "Application" (limit 0xa0000000) over the GlobalHeap counted allocator
    main+0x4763918: the allocator at N+8, of every data table and of the main modules."""
    inner = m.main + 0x4763918
    a = m.vcall(inner, 0x10, 0x58, 8)
    with m.frame(0x10) as f:
        m.put(f, 8, APPLICATION_LIMIT); m.put(f + 8, 8, inner)
        m.call_void(m.main + 0x13ECA54, a, f, f + 8)
    m.vcall_void(a, 0xE0, m.main + APPLICATION_NAME)
    return a


# --- the personal table's creator ---------------------------------------------------------------

@lifted(0x1644B38)
def table_base_1644b38(m, o, *_):
    """Base constructor of the personal table: vtable 0x44a8df0 (+0x20 its +0x30), +8 the top of the
    thread's object stack, +0x10 / u32 +0x18 zero; the class static [0x46d7438] gets byte +8 = 1."""
    m.put(o, 8, m.u64(m.main + 0x46D66F8) + 0x10)
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 4, 0)
    top = _tls_top(m)
    m.put(o, 8, m.main + 0x44A8DF0); m.put(o + 8, 8, top)
    m.put(o + 0x20, 8, m.main + 0x44A8E20)
    _static_guard(m, 0x46D7430)
    m.put(m.u64(m.main + 0x46D7438) + 8, 1, 1)


@lifted(0x1644AB4)
def construct_personal(m, o, *_):
    """The personal table: vtables [0x46dda68] + 0x10 / + 0x40, +0x28 0x44a8e40, an empty map at +0x68
    over the allocator +8 (max load 1.0), no default record, +0xd8 not loaded."""
    m.call_void(m.main + 0x1644B38, o)
    vt = m.u64(m.main + 0x46DDA68)
    _empty_table(m, o, vt + 0x10, vt + 0x40, m.main + 0x44A8E40)


@lifted(0x164498C)
def create_personal(m, alloc, *_):
    """Create the 0xe0-byte personal table from alloc (0x1644ab4)."""
    return _create(m, alloc, 0xE0, lambda o: m.call_void(m.main + 0x1644AB4, o))


def _static_guard(m, guard_got):
    """A function-local static's guard (its address in the GOT word): acquired and released when unset;
    the __cxa_atexit registration between them is not reproduced."""
    g = m.u64(m.main + guard_got)
    if m.u8(g) & 1 == 0 and m.call(m.main + 0x343CF10, g) & 1:
        m.call_void(m.main + 0x343CF20, g)


def _empty_table(m, o, vt, vt20, w28):
    for off in (0x30, 0x38, 0x40, 0x48, 0x50, 0x58, 0x60, 0x68, 0x70, 0x88, 0x98, 0xB0, 0xC0, 0xD0):
        m.put(o + off, 8, 0)
    m.put(o + 0x90, 4, 0); m.put(o + 0xB8, 4, 0); m.put(o + 0xD8, 1, 0)
    m.put(o, 8, vt); m.put(o + 0x20, 8, vt20); m.put(o + 0x28, 8, w28)
    alloc = m.u64(o + 8)
    m.put(o + 0x78, 8, alloc); m.put(o + 0x80, 8, MAX_NODES)
    m.put(o + 0xA0, 8, alloc); m.put(o + 0xA8, 8, MAX_NODES)
    m.put(o + 0xC8, 4, ONE_F)


# --- the id-hash table's creator -----------------------------------------------------------------

@lifted(0x1731190)
def idhash_base_1731190(m, o, *_):
    """Base constructor of the id-hash table: vtable 0x4492008 (+0x20 its +0x30), +8 the top of the
    thread's object stack; the class static [0x46d8908] gets byte +8 = 1."""
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 4, 0)
    m.put(o, 8, m.u64(m.main + 0x46D66F8) + 0x10)
    top = _tls_top(m)
    m.put(o, 8, m.main + 0x4492008); m.put(o + 8, 8, top)
    m.put(o + 0x20, 8, m.main + 0x4492038)
    _static_guard(m, 0x46D8900)
    m.put(m.u64(m.main + 0x46D8908) + 8, 1, 1)


@lifted(0x1731094)
def construct_idhash(m, o, *_):
    """The id-hash table: vtable 0x4491fb8 (+0x20 its +0x30), 282 zeroed 0x18-byte entries from +0x28
    (u32 index, u64 hash +8, u16 id +0x10), four resource handles at +0x1a98, +0x1ad8, +0x1b30 and
    +0x1b70 (each [0x46d8e88] + 0x10 and seven zero words)."""
    m.call_void(m.main + 0x1731190, o)
    m.put(o, 8, m.main + 0x4491FB8); m.put(o + 0x20, 8, m.main + 0x4491FE8)
    e = o + 0x28
    while e != o + 0x1A98:
        m.put(e, 4, 0); m.put(e + 8, 8, 0); m.put(e + 0x10, 2, 0)
        e += 0x18
    for off in range(0x1AA0, 0x1AD8, 8):
        m.put(o + off, 8, 0)
    vt = m.u64(m.main + 0x46D8E88) + 0x10
    for off in range(0x1AE0, 0x1B18, 8):
        m.put(o + off, 8, 0)
    m.put(o + 0x1AD8, 8, vt); m.put(o + 0x1A98, 8, vt)
    for off in range(0x1B38, 0x1B70, 8):
        m.put(o + off, 8, 0)
    m.put(o + 0x1B30, 8, vt)
    for off in range(0x1B78, 0x1BB0, 8):
        m.put(o + off, 8, 0)
    m.put(o + 0x1B70, 8, vt)


@lifted(0x1730F6C)
def create_idhash(m, alloc, *_):
    """Create the 0x1bb0-byte id-hash table from alloc (0x1731094)."""
    return _create(m, alloc, 0x1BB0, lambda o: m.call_void(m.main + 0x1731094, o))


# --- loading the files ---------------------------------------------------------------------------

def _fb_records(data):
    """Offsets of the tables in field 0 (a vector of tables) of a FlatBuffers file's root."""
    def field(t, i):
        vt = t - struct.unpack_from("<i", data, t)[0]
        if struct.unpack_from("<H", data, vt)[0] < 4 + 2 * i + 2:
            return 0
        return struct.unpack_from("<H", data, vt + 4 + 2 * i)[0]
    root = struct.unpack_from("<I", data, 0)[0]
    f = field(root, 0)
    v = root + f + struct.unpack_from("<I", data, root + f)[0]
    n = struct.unpack_from("<I", data, v)[0]
    out = []
    for i in range(n):
        s = v + 4 + 4 * i
        out.append(s + struct.unpack_from("<I", data, s)[0])
    return out, field


def _load(m, alloc, path, data):
    """The file in memory (page-aligned from FILES; the resource system's own heap is not reproduced)
    with its resource object (vtable 0x4440368, 0x210 bytes): +0x48 the path's FNV-1a 64, +0x50 / +0x58
    the path and its length, +0x1d8 the size, +0x1f0 the bytes."""
    buf = getattr(m, "files_end", FILES)
    m.files_end = (buf + len(data) + 0xFFF) & ~0xFFF
    m.write(buf, data)
    name = m.vcall(alloc, 0x10, len(path) + 1, 1)
    m.write(name, path.encode() + b"\0")

    def build(r):
        m.write(r, bytes(RESOURCE_SIZE))
        m.put(r, 8, m.main + RESOURCE_VT)
        m.put(r + 0x20, 8, m.main + RESOURCE_VT + 0x98); m.put(r + 0x28, 8, m.main + RESOURCE_VT + 0xE8)
        m.put(r + 0x48, 8, _fnv1a64(path.encode()))
        m.put(r + 0x50, 8, name); m.put(r + 0x58, 8, len(path))
        m.put(r + 0x1D8, 8, len(data)); m.put(r + 0x1E8, 8, 0x10001)
        m.put(r + 0x1F0, 8, buf); m.put(r + 0x1F8, 8, alloc)
    return _create(m, alloc, RESOURCE_SIZE, build), buf


def _fill_map(m, t, buf, data, rule):
    """The u16 (or species * 10000 + form) map at +0x68: reserved to the record count, one 0x20-byte
    node {next, hash = key, key, record} per record in file order, the default (+0xd0) key 0's record,
    +0xd8 loaded."""
    recs, field = _fb_records(data)
    keyed = {}
    for r in recs:
        f0 = field(r, 0)
        a, b = struct.unpack_from("<HH", data, r + f0) if f0 else (0, 0)
        keyed.setdefault(a * 10000 + b if rule == "pair" else a, r)
    table = t + 0x68
    width = 4 if rule == "pair" else 2
    do = 0xF7BB84 if width == 4 else 0x127D27C        # __do_rehash with bucket arrays aligned 4 / 8
    _rehash(m, table, len(keyed), do)
    for key, r in keyed.items():
        node = m.vcall(m.u64(table + 0x38), 0x10, 0x20, 8)
        m.put(node, 8, 0); m.put(node + 8, 8, key)
        m.put(node + 0x10, 8, 0); m.put(node + 0x10, width, key)
        m.put(node + 0x18, 8, buf + r)
        _insert(m, table, node, key, do)
    m.put(t + 0xD0, 8, buf + keyed[0] if 0 in keyed else 0)
    m.put(t + 0xD8, 1, 1)


def _set_slot(m, slot_got, guard_got, obj):
    """The function-local static [slot_got] holds obj (its guard set, the slot empty before)."""
    _static_guard(m, guard_got)
    slot = m.u64(m.main + slot_got)
    if m.u64(slot):
        raise UnliftedCall("table static already holds an object")
    m.put(slot, 8, obj)


def build_tables(m, alloc, files):
    """The five data tables from `files` (romfs path -> bytes) into their statics. Returns name -> table."""
    out = {}
    for name, _slot, slot_got, guard_got, path, rule in TABLES:
        data = files[path]
        if name == "personal":
            t = m.call(m.main + 0x164498C, alloc)
        else:
            vt, vt20, w28, size = LAYOUT[name]

            def build(o, vt=vt, vt20=vt20, w28=w28, size=size):
                m.write(o, bytes(size))
                m.put(o + 8, 8, _tls_top(m))
                if size > 0x68:
                    _empty_table(m, o, m.main + vt, m.main + vt20, m.main + w28)
                else:
                    m.put(o, 8, m.main + vt); m.put(o + 0x20, 8, m.main + vt20)
                    m.put(o + 0x28, 8, m.main + w28)
            t = _create(m, alloc, size, build)
        res, buf = _load(m, alloc, path, data)
        m.put(t + 0x30, 8, res)
        if rule:
            _fill_map(m, t, buf, data, rule)
        _set_slot(m, slot_got, guard_got, t)
        out[name] = t
    name, _slot, slot_got, guard_got, path = IDHASH
    data = files[path]
    t = m.call(m.main + 0x1730F6C, alloc)
    recs, field = _fb_records(data)
    for i, r in enumerate(recs[:IDHASH_ENTRIES]):
        g = (lambda j: struct.unpack_from("<I", data, r + field(r, j))[0] if field(r, j) else 0)
        item, index = g(0), g(1)
        e = t + 0x28 + 0x18 * i
        m.put(e, 4, index); m.put(e + 4, 4, 0)
        m.put(e + 8, 8, m.u64(m.main + IDHASH_HASHES + 8 * index))
        m.put(e + 0x10, 2, item)
    for i in range(len(recs), IDHASH_ENTRIES):
        m.put(t + 0x28 + 0x18 * i, 4, 0xFFFFFFFF)
    _set_slot(m, slot_got, guard_got, t)
    out[name] = t
    return out


# --- the weak-handle table: static 0x4700930 (GOT 0x46d3910, guard GOT 0x46d3908) ------------------

@lifted(0x165E1C4)
def handles_base_165e1c4(m, o, *_):
    """Base constructor of the weak-handle table: vtable 0x44e8b00 (+0x20 its +0x30), +8 the top of the
    thread's object stack; the class static [0x46d3910] gets byte +8 = 1."""
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 4, 0)
    m.put(o, 8, m.u64(m.main + 0x46D66F8) + 0x10)
    top = _tls_top(m)
    m.put(o, 8, m.main + 0x44E8B00); m.put(o + 8, 8, top)
    m.put(o + 0x20, 8, m.main + 0x44E8B30)
    _static_guard(m, 0x46D3908)
    m.put(m.u64(m.main + 0x46D3910) + 8, 1, 1)


@lifted(0xC1ADEC)
def handles_new_block(m, o, *_):
    """Append a block of 0x400 handle entries (0x8008 bytes, the count at +0x8000 zeroed with the
    allocator on the thread's object stack) from the allocator [o] to the block table at o+8 (entries
    {block, allocator, 0x8008, 8}; count at o+0x8008, at most 0x400); a failed allocation appends
    {0, 0, 0, 0}."""
    alloc = m.u64(o)
    blk = m.vcall(alloc, 0x10, 0x8008, 8)
    if blk:
        stack = _tls_stack(m)
        _push(m, stack, alloc)
        m.put(blk + 0x8000, 8, 0)
        _pop(m, stack)
        size, align = 0x8008, 8
    else:
        alloc = size = align = 0
    count = m.u64(o + 0x8008)
    if count >= 0x400:
        raise UnliftedCall("abort: handle block table full")
    e = o + (count << 5)
    m.put(e + 8, 8, blk); m.put(e + 0x10, 8, alloc)
    m.put(e + 0x18, 8, size); m.put(e + 0x20, 8, align)
    m.put(o + 0x8008, 8, m.u64(o + 0x8008) + 1)


@lifted(0x165E080)
def construct_handles(m, o, *_):
    """The weak-handle table (vtable 0x44e8ab0): +0x28 its allocator (+8), the block table at +0x30 with
    one block (0xc1adec), current block +0x8038 0; at +0x8040 the id pool (base 0, next 0, live 0, two
    empty deques over the allocator, the live bitset +0x88..+0xc0, lock +0xd0, light event +0xe0);
    u32 +0x8144 1 and the light event +0x8138."""
    p = o + 0x8040
    m.call_void(m.main + 0x165E1C4, o)
    alloc = m.u64(o + 8)
    m.put(o, 8, m.main + 0x44E8AB0); m.put(o + 0x20, 8, m.main + 0x44E8AE0)
    m.put(o + 0x28, 8, alloc)
    m.put(o + 0x8030, 8, 0); m.put(o + 0x8038, 8, 0)
    m.call_void(m.main + 0xC1ADEC, o + 0x28)
    alloc = m.u64(o + 8)
    m.put(p, 8, 0); m.put(p + 8, 4, 0)
    m.put(p + 0x10, 8, 0); m.put(p + 0x18, 8, 0); m.put(p + 0x20, 8, 0)
    # two 0x28-byte deque headers copied from a stack temporary: {0, allocator, max, 0, u32 0} (the
    # temporary's last four bytes are never written; zero here)
    for at in (p + 0x28, p + 0x58):
        m.write(at, struct.pack("<QQQQQ", 0, alloc, 0x3FFFFFFFFFFFFFFF, 0, 0))
    m.put(p + 0x50, 8, 0)
    m.put(p + 0xB8, 4, 0); m.put(p + 0xC0, 8, 0)
    m.put(p + 0x88, 8, 0); m.put(p + 0x90, 8, 0)
    m.put(p + 0xEC, 4, 1)
    m.put(p + 0x98, 8, 0); m.put(p + 0xA0, 8, alloc)
    m.put(p + 0xA8, 8, 0x1FFFFFFFFFFFFFFF); m.put(p + 0xB0, 8, 0)
    m.put(p + 0xD0, 8, 0); m.put(p + 0xD8, 8, 0)
    m.call_void(m.main + 0x343E6D0, p + 0xE0, 0, 1)
    m.put(p + 0xF0, 8, 0)
    m.put(o + 0x8144, 4, 1)
    m.call_void(m.main + 0x343E6D0, o + 0x8138, 0, 1)


@lifted(0x165DD08)
def create_handles(m, alloc, *_):
    """Create the 0x8150-byte weak-handle table from alloc (align 0x10, 0x165e080)."""
    stack = _tls_stack(m)
    _push(m, stack, alloc)
    o = m.vcall(alloc, 0x10, 0x8150, 0x10)
    if not o:
        raise UnliftedCall("abort: allocation failed in Create")
    m.call_void(m.main + 0x165E080, o)
    m.put(o + 0x18, 4, 0x108150)
    m.put(o + 8, 8, alloc); m.put(o + 0x10, 8, o)
    _pop(m, stack)
    return o


def build_handles(m, alloc):
    """The weak-handle table into its static 0x4700930."""
    t = m.call(m.main + 0x165DD08, alloc)
    _set_slot(m, 0x46D3910, 0x46D3908, t)
    return t


def _scoped_copy(m, alloc, dst, src):
    """*dst = *src (u64) with alloc on the thread's object stack, when the thread has one."""
    stack = _tls_stack(m)
    if stack:
        _push(m, stack, alloc)
    m.put(dst, 8, m.u64(src))
    if stack:
        _pop(m, stack)


@lifted(0xC1AF5C)
def construct_backward_c1af5c(m, alloc_ref, begin, end, out, *_):
    """Copy the u64 range [begin, end) backward to end at *out (lowered as it goes), each element with
    the allocator [alloc_ref] on the thread's object stack."""
    while end != begin:
        _scoped_copy(m, m.u64(alloc_ref), m.u64(out) - 8, end - 8)
        end -= 8
        m.put(out, 8, m.u64(out) - 8)


@lifted(0xC1AA80)
def vector_append_c1aa80(m, v, n, value, *_):
    """vector<u64>::__append(n, value) of {begin, end, capacity, allocator*, max_size}: in place when
    it fits, else a new buffer of max(2 * capacity, size + n) elements (max_size when capacity is past
    half of it) from the allocator, the old elements moved behind the new ones (0xc1af5c) and the old
    buffer freed (0xb48fe8 when the allocator defers frees)."""
    begin, end, cap = m.u64(v), m.u64(v + 8), m.u64(v + 0x10)
    if n <= (cap - end) >> 3:
        for i in range(n):
            _scoped_copy(m, m.u64(v + 0x18), end + 8 * i, value)
        m.put(v + 8, 8, end + 8 * n)
        return
    size = (end - begin) >> 3
    want = n + size
    top = min(m.u64(v + 0x20), 0x7FFFFFFFFFFFFFFF)
    if top < want:
        raise UnliftedCall("vector length_error")
    have = (cap - begin) >> 3
    grow = max(2 * have, want)
    count = grow if have < top >> 1 else top
    alloc_ref = v + 0x18
    new = 0
    if count:
        new = m.vcall(m.u64(alloc_ref), 0x10, count * 8, 8)
        if not new:
            raise UnliftedCall("allocator out of memory: vf 0xe8")
    with m.frame(0x30) as sb:
        mid = new + size * 8
        m.put(sb + 8, 8, new); m.put(sb + 0x10, 8, mid)
        m.put(sb + 0x18, 8, mid); m.put(sb + 0x20, 8, new + count * 8); m.put(sb + 0x28, 8, alloc_ref)
        for i in range(n):
            _scoped_copy(m, m.u64(alloc_ref), mid + 8 * i, value)
        m.put(sb + 0x18, 8, mid + 8 * n)
        m.call_void(m.main + 0xC1AF5C, alloc_ref, m.u64(v), m.u64(v + 8), sb + 0x10)
        old = m.u64(v)
        old_cap = m.u64(v + 0x10)
        m.put(v, 8, m.u64(sb + 0x10)); m.put(v + 8, 8, m.u64(sb + 0x18))
        m.put(v + 0x10, 8, m.u64(sb + 0x20))
    if old:
        alloc = m.u64(alloc_ref)
        size = old_cap - old
        if m.vcall(alloc, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) >= 1:
            m.call_void(m.main + 0xB48FE8, alloc, old, size, 8)
        else:
            m.vcall_void(alloc, 0x18, old, size, 8)


# --- deque<u32> of freed handle ids: map {first, begin, end, cap, allocator} at +0, start +0x40, size
# +0x48, block allocator +0x50; blocks of 0x400 ids (0x1000 bytes, align 4) --------------------------

def _scoped_store(m, alloc, dst, value):
    stack = _tls_stack(m)
    if stack:
        _push(m, stack, alloc)
    m.put(dst, 8, value)
    if stack:
        _pop(m, stack)


def _map_push_back(m, sb, value, alloc):
    """split_buffer<T*>::push_back (0xb44a40, 0xb451d8, 0xb44f54): room at the back, or the elements
    shifted to the front half of the spare room (memmove); a reallocation is refused."""
    first, begin, end, cap = (m.u64(sb + i) for i in (0, 8, 0x10, 0x18))
    if end == cap:
        if begin <= first:
            raise UnliftedCall("split_buffer push_back reallocates")
        d = (((begin - first) >> 3) + 1) >> 1
        nb = begin - 8 * d
        m.write(nb, m.read(begin, end - begin))
        end = nb + (end - begin)
        m.put(sb + 8, 8, nb); m.put(sb + 0x10, 8, end)
    _scoped_store(m, alloc, end, value)
    m.put(sb + 0x10, 8, m.u64(sb + 0x10) + 8)


def _map_push_front(m, sb, value, alloc):
    """split_buffer<T*>::push_front (0xb44cc0, 0xb45458): room at the front, or the elements shifted to
    the back half of the spare room; a reallocation is refused."""
    first, begin, end, cap = (m.u64(sb + i) for i in (0, 8, 0x10, 0x18))
    if begin == first:
        if end >= cap:
            raise UnliftedCall("split_buffer push_front reallocates")
        d = (((cap - end) >> 3) + 1) >> 1
        nb = end + 8 * d - (end - begin)
        m.write(nb, m.read(begin, end - begin))
        begin = nb
        m.put(sb + 8, 8, nb); m.put(sb + 0x10, 8, end + 8 * d)
    _scoped_store(m, alloc, begin - 8, value)
    m.put(sb + 8, 8, m.u64(sb + 8) - 8)


@lifted(0xB44724)
def deque_add_back_capacity(m, d, *_):
    """libc++ deque<u32>::__add_back_capacity: a spare front block rotated to the back; else a new
    block (0x1000, align 4, from [d+0x50]) pushed onto the map, at the back when it has room there,
    else at the front and rotated; else a new map of max(2 * capacity, 1) pointers (align 4, from
    [d+0x20]) holding the old ones and the new block, the old map freed."""
    blocks = m.u64(d + 0x50)
    if m.u64(d + 0x40) >= 0x400:
        m.put(d + 0x40, 8, m.u64(d + 0x40) - 0x400)
        begin = m.u64(d + 8)
        pt = m.u64(begin)
        m.put(d + 8, 8, begin + 8)
        _map_push_back(m, d, pt, m.u64(d + 0x20))
        return
    first, begin, end, cap = (m.u64(d + i) for i in (0, 8, 0x10, 0x18))
    size = (end - begin) >> 3
    if size < (cap - first) >> 3:
        blk = m.vcall(blocks, 0x10, 0x1000, 4)
        if not blk:
            raise UnliftedCall("allocator out of memory: vf 0xe8")
        if cap != end:
            _map_push_back(m, d, blk, m.u64(d + 0x20))
        else:
            _map_push_front(m, d, blk, m.u64(d + 0x20))
            begin = m.u64(d + 8)
            pt = m.u64(begin)
            m.put(d + 8, 8, begin + 8)
            _map_push_back(m, d, pt, m.u64(d + 0x20))
        return
    bytes_ = cap - first
    count = (bytes_ >> 2) if bytes_ else 1
    alloc = m.u64(d + 0x20)
    new = m.vcall(alloc, 0x10, count * 8, 4)
    if not new:
        raise UnliftedCall("allocator out of memory: vf 0xe8")
    with m.frame(0x30) as sb:
        mid = new + size * 8
        m.put(sb, 8, new); m.put(sb + 8, 8, mid); m.put(sb + 0x10, 8, mid)
        m.put(sb + 0x18, 8, new + count * 8); m.put(sb + 0x20, 8, d + 0x20)
        blk = m.vcall(blocks, 0x10, 0x1000, 4)
        if not blk:
            raise UnliftedCall("allocator out of memory: vf 0xe8")
        _map_push_back(m, sb, blk, alloc)
        p = m.u64(d + 0x10)
        while p != m.u64(d + 8):
            p -= 8
            _map_push_front(m, sb, m.u64(p), alloc)
        old = m.u64(d)
        old_cap = m.u64(d + 0x18)
        for i in (0, 8, 0x10, 0x18):
            m.put(d + i, 8, m.u64(sb + i))
    if old:
        a = m.u64(d + 0x20)
        if m.vcall(a, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) >= 1:
            m.call_void(m.main + 0xB48FE8, a, old, old_cap - old, 4)
        else:
            m.vcall_void(a, 0x18, old, old_cap - old, 4)


# --- the battle setup's party holders ------------------------------------------------------------

PARTY_RECORD = 0x158                    # the bootstrap's record: 0x148 sealed core, 0x10 party block


def build_party(m, alloc, record):
    """A setup party holder (0x68 bytes, 0xfa0d38) holding one Pokemon parameter object (0xeee5dc)
    made from a 0x158-byte sealed record: a Pokemon record (0xeee8fc) loads it into its accessor under
    the accessor's lock (0xe14ea8), recomputes its stats (0xe13b9c(r, 1)) and clamps its PP (0xe14018),
    as 0xeeea48 does; the parameter object copies it. Holder: u8 count +0x60 = 1, the parameter object
    at +0x30 with one weak reference, its own count +0x28 = 1."""
    from pokeldn.sv.battle.engine.pokemon import _locked
    from pokeldn.sv.battle.engine.steps import _acquire, _inc
    if len(record) != PARTY_RECORD:
        raise ValueError(f"a party record is {PARTY_RECORD:#x} bytes")
    with m.frame(0x10) as f:
        r = m.call(m.main + 0xEEE8FC, f, alloc)
    with m.frame(0x160) as buf:
        m.write(buf, record)
        _locked(m, m.u64(r + 0x70), 0xE14EA8, buf, buf + 0x148)
    m.call_void(m.main + 0xE13B9C, r, 1)
    m.call_void(m.main + 0xE14018, r)
    with m.frame(0x10) as f:
        p = m.call(m.main + 0xEEE5DC, f, alloc, r)
    _acquire(m, p)
    with m.frame(0x10) as f:
        h = m.call(m.main + 0xFA0D38, f, alloc)
    _inc(m, h)
    m.put(h + 0x30, 8, p)
    m.put(h + 0x60, 1, 1)
    return h


# --- the session plumbing from a template ---------------------------------------------------------

def build_from_template(m, alloc, template):
    """The objects of `template` (units {id: {size, header, fields}}; a field (offset, kind, data):
    "bytes" (data, mask), "alloc", "link" (unit, offset), "opaque" (an address the chain carries but
    never reads through: a zeroed 0x40-byte block), "handle_ptr" / "handle_id" (a weak handle to (unit,
    offset) in the weak-handle table, entry +8..+0x1f as given)) allocated from `alloc` and laid out;
    bytes no field names are zero. Returns {unit id: address}."""
    at = {}
    for uid, u in template["units"].items():
        o = m.vcall(alloc, 0x10, u["size"], 8)
        m.write(o, bytes(u["size"]))
        if u["header"]:                 # a Create'd object: +8 its allocator, +0x10 itself, +0x18 size
            m.put(o + 8, 8, alloc); m.put(o + 0x10, 8, o); m.put(o + 0x18, 4, 0x80000 | u["size"])
        at[uid] = o
    opaque, entries = {}, {}
    pool = m.u64(m.main + 0x4700930)
    for uid, u in template["units"].items():
        o = at[uid]
        for f in u["fields"]:
            off, kind, data = f[0], f[1], f[2]
            if kind == "bytes":
                mask = f[3]
                old = m.u64(o + off)
                new = int.from_bytes(data, "little")
                m.put(o + off, 8, (old & ~mask) | (new & mask))
            elif kind == "alloc":
                m.put(o + off, 8, alloc)
            elif kind == "link":
                m.put(o + off, 8, at[data[0]] + data[1])
            elif kind == "opaque":
                if data not in opaque:
                    opaque[data] = m.vcall(alloc, 0x10, 0x40, 8)
                    m.write(opaque[data], bytes(0x40))
                m.put(o + off, 8, opaque[data])
            elif kind in ("handle_ptr", "handle_id"):
                target, toff, tail = data
                key = (target, toff)
                if key not in entries:
                    with m.frame(0x10) as h:
                        m.x8 = h
                        m.call(m.main + 0xC1A58C, pool, at[target] + toff)
                        e = m.u64(h)
                    m.write(e + 8, tail)
                    m.put(e + 0x10, 8, at[target] + toff)
                    entries[key] = e
                e = entries[key]
                m.put(o + off, 8, e if kind == "handle_ptr" else m.u64(e))
    return at


def build_network(m, alloc, template, bootstrap, partners):
    """N and what hangs off it: the plumbing from `template`, then what the battle bootstrap (0xaa0
    plaintext) gives: the setup's five party holders (our Pokemon, the boss, the guest, then the two
    NPC partners' records from `partners`), the RaidPoint's randSeed at N+0x30 and setup+0x718, its
    raidTimeData limits at N+0x8a / +0x8c / +0x8e and its boss action profile as u16 at setup+0x514.
    N+0x150..+0x18f (the main-module holders 0x2891748 fills) start empty. Returns N."""
    at = build_from_template(m, alloc, template)
    n = at[template["root"]]
    setup = m.u64(n + 0x38)
    point = 5 * PARTY_RECORD
    seed = int.from_bytes(bootstrap[point + 0x3D8:point + 0x3E0], "little")
    m.put(n + 0x30, 8, seed); m.put(setup + 0x718, 8, seed)
    game, client, command = struct.unpack_from("<3I", bootstrap, point + 0x34)
    m.put(n + 0x8A, 2, game); m.put(n + 0x8C, 2, client); m.put(n + 0x8E, 2, command)
    for i, value in enumerate(struct.unpack_from("<37I", bootstrap, point + 0x4C)):
        m.put(setup + 0x514 + 2 * i, 2, value)
    records = [bootstrap[0:PARTY_RECORD], bootstrap[4 * PARTY_RECORD:5 * PARTY_RECORD],
               bootstrap[PARTY_RECORD:2 * PARTY_RECORD]] + list(partners)
    for i, rec in enumerate(records):
        m.put(setup + 0xA0 + 8 * i, 8, build_party(m, alloc, rec))
    for off in range(0x150, 0x190, 8):
        m.put(n + off, 8, 0)
    return n


# --- named battle parameters: N+0x48 +0x148 -------------------------------------------------------

PARAMETERS_VT = 0x4485568               # 0xa8 bytes; +0x20 0x44855e8, +0x28 the shared part 0x4485638


def build_parameters(m, alloc, pairs):
    """The named-parameter table [N+0x48]+0x148 the rounds read through 0x11521a0 and its vf 0x68
    (0x20049f4): an unordered_map<u64 name hash, u32> at +0x40 (buckets +0x40, count +0x48, first node
    +0x70, size +0x98, max load 1.0 +0xa0; nodes 0x20 bytes {next, hash, key, u32 value}) filled one by
    one from `pairs` (name hash, value), and a weak handle at +0x30 (its id at +0x38) to its +0x28 part
    holding one strong reference."""
    from pokeldn.sv.battle.engine.steps import _insert

    def build(o):
        m.write(o, bytes(0xA8))
        m.put(o, 8, m.main + PARAMETERS_VT); m.put(o + 0x20, 8, m.main + PARAMETERS_VT + 0x80)
        m.put(o + 0x28, 8, m.main + PARAMETERS_VT + 0xD0)
        m.put(o + 0x50, 8, alloc); m.put(o + 0x58, 8, MAX_NODES)
        m.put(o + 0x78, 8, alloc); m.put(o + 0x80, 8, MAX_NODES)
        m.put(o + 0xA0, 4, ONE_F)
    o = _create(m, alloc, 0xA8, build)
    pool = m.u64(m.main + 0x4700930)
    with m.frame(0x10) as h:
        m.x8 = h
        m.call(m.main + 0xC1A58C, pool, o + 0x28)
        e = m.u64(h)
    m.put(e + 8, 8, m.main + 0x4740BF0)         # the resolved value a live reference holds
    m.put(e + 0x1A, 2, 1); m.put(e + 0x1C, 4, 0xFFFFFFFE)
    m.put(o + 0x30, 8, e); m.put(o + 0x38, 8, m.u64(e))
    table = o + 0x40
    for key, value in pairs:
        node = m.vcall(m.u64(table + 0x38), 0x10, 0x20, 8)
        m.put(node, 8, 0); m.put(node + 8, 8, key); m.put(node + 0x10, 8, key); m.put(node + 0x18, 8, value)
        _insert(m, table, node, key, 0xFAE80C)
    return o
