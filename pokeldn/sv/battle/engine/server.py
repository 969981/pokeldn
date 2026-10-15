"""The battle server's sends: a step's message (0x113bad8: header, body from the builder, a 0x50-byte
message object) queued in the link of every station it goes to, in the per-slot store entries and in the
server's own log (docs/sv_raid.md, The server's messages)."""

import struct

from pokeldn.sv.battle.engine import requests
from pokeldn.sv.battle.engine.calls import _tail
from pokeldn.sv.battle.engine.containers import _hash_find_u32
from pokeldn.sv.battle.engine.references import _construct_counted_base
from pokeldn.sv.battle.engine.requests import _add_ref, _release
from pokeldn.sv.battle.engine.session import _map_push_back, _map_push_front
from pokeldn.sv.battle.engine.steps import _create, _pop, _push, _tls_stack
from pokeldn.sv.battle.machine import UnliftedCall, lifted

MESSAGE = 0x44ED338             # vtable of the message object 0x1227714 makes (+0x78, +0xc8 at +0x20, +0x28)
HEADER = 0x20                   # u32 type, u32 pad, u64 step, u64 round, u8 destination, u8 5, 6 pad bytes
ALL = 5                         # the destination byte of a message for every station


def _counted_copy(m, at, o):
    """A strong reference copied into the slot `at` (AddReference when o is set)."""
    m.put(at, 8, o)
    if o:
        _add_ref(m, o)


# --- deque<message*> of a link or a store entry: map {first, begin, end, cap} at +0x40, map allocator
# +0x60, start +0x80, size +0x88, block allocator +0x90, bound byte +0xb0; 0x200 pointers a block -------

def _scoped_store(m, alloc, dst, value):
    stack = _tls_stack(m)
    if stack:
        _push(m, stack, alloc)
    m.put(dst, 8, value)
    if stack:
        _pop(m, stack)


@lifted(0x113D698)
def construct_ref(m, holder, dst, src, *_):
    """*dst = a strong reference to *src, with the allocator [holder] on the thread's object stack."""
    alloc = m.u64(holder)
    stack = _tls_stack(m)
    if stack:
        _push(m, stack, alloc)
    o = m.u64(src)
    m.put(dst, 8, o)
    if o:
        _add_ref(m, o)
    if stack:
        _pop(m, stack)
    return stack


@lifted(0x113D810)
def add_back_capacity(m, d, *_):
    """libc++ deque<T*>::__add_back_capacity at d (map +0..+0x18, its allocator +0x20, start +0x40, block
    allocator +0x50): a spare front block rotated to the back; else a new 0x1000-byte block (align 8)
    pushed onto the map, at the back when there is room, else at the front and rotated; else a new map of
    max(2 * capacity, 1) pointers holding the new block and the old pointers, the old map freed."""
    blocks = m.u64(d + 0x50)
    if m.u64(d + 0x40) >= 0x200:
        m.put(d + 0x40, 8, m.u64(d + 0x40) - 0x200)
        begin = m.u64(d + 8)
        pt = m.u64(begin)
        m.put(d + 8, 8, begin + 8)
        _map_push_back(m, d, pt, m.u64(d + 0x20))
        return
    first, begin, end, cap = (m.u64(d + i) for i in (0, 8, 0x10, 0x18))
    size = (end - begin) >> 3
    if size < (cap - first) >> 3:
        blk = m.vcall(blocks, 0x10, 0x1000, 8)
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
    span = cap - first
    count = (span >> 2) if span else 1
    if count == size:
        raise UnliftedCall("0x113da3c: a full new map")
    alloc = m.u64(d + 0x20)
    new = m.vcall(alloc, 0x10, count * 8, 8)
    if not new:
        raise UnliftedCall("allocator out of memory: vf 0xe8")
    with m.frame(0x30) as sb:
        mid = new + size * 8
        m.put(sb, 8, new); m.put(sb + 8, 8, mid); m.put(sb + 0x10, 8, mid)
        m.put(sb + 0x18, 8, new + count * 8); m.put(sb + 0x20, 8, d + 0x20)
        blk = m.vcall(blocks, 0x10, 0x1000, 8)
        if not blk:
            raise UnliftedCall("allocator out of memory: vf 0xe8")
        _scoped_store(m, alloc, mid, blk)
        m.put(sb + 0x10, 8, mid + 8)
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
            m.call_void(m.main + 0xB48FE8, a, old, old_cap - old, 8)
        else:
            m.vcall_void(a, 0x18, old, old_cap - old, 8)


@lifted(0x113D5E0)
def push_message(m, q, src, *_):
    """push_back of a strong reference to *src on q's deque; a bound at +0xb0 (pop the front when full)
    is not lifted."""
    if m.u8(q + 0xB0):
        raise UnliftedCall("0x2801764: a bounded deque")
    begin, end = m.u64(q + 0x48), m.u64(q + 0x50)
    cap = (((end - begin) << 6) - 1) & 0xFFFFFFFFFFFFFFFF if end != begin else 0
    if cap == m.u64(q + 0x80) + m.u64(q + 0x88):
        m.call_void(m.main + 0x113D810, q + 0x40)
    begin, end = m.u64(q + 0x48), m.u64(q + 0x50)
    i = m.u64(q + 0x80) + m.u64(q + 0x88)
    slot = m.u64(begin + ((i >> 6) & 0x3FFFFFFFFFFFFF8)) + 8 * (i & 0x1FF) if end != begin else 0
    r = m.call(m.main + 0x113D698, q + 0x90, slot, src)
    m.put(q + 0x88, 8, m.u64(q + 0x88) + 1)
    return r


def _push_copy(m, q, o):
    """A reference to o copied to the stack, pushed on q (0x113d5e0), the copy released."""
    with m.frame(0x10) as c:
        _counted_copy(m, c, o)
        m.call_void(m.main + 0x113D5E0, q, c)
        _release(m, c)


@lifted(0x113D4A0)
def link_push(m, link, src, *_):
    """The message *src onto the link's outgoing deque [link+0x48]."""
    _push_copy(m, m.u64(link + 0x48), m.u64(src))


@lifted(0x113D184)
def find_link(m, server, slot, *_):
    """Writes to x8 a strong reference to the link the server keeps for `slot` (u32-keyed map at
    server+0x1a0), or 0."""
    out = m.x8
    node = _hash_find_u32(m, server + 0x1A0, slot & 0xFFFFFFFF)
    if not node:
        m.put(out, 8, 0)
        return out
    o = m.u64(node + 0x18)
    _counted_copy(m, out, o)
    return out


@lifted(0x113D33C)
def link_send(m, server, link, src, *_):
    """When the server's links are live (u8 server+0x490): *src onto the link *link (0x113d4a0)."""
    if not m.u8(server + 0x490):
        return
    o = m.u64(link)
    with m.frame(0x10) as c:
        _counted_copy(m, c, m.u64(src))
        m.call_void(m.main + 0x113D4A0, o, c)
        _release(m, c)


def _send_on(m, server, link_ref, msg):
    """link_send through copies of the link and message references, both released after."""
    with m.frame(0x20) as c:
        _counted_copy(m, c, m.u64(link_ref))
        _counted_copy(m, c + 8, msg)
        m.call_void(m.main + 0x113D33C, server, c, c + 8)
        _release(m, c + 8)
        _release(m, c)


@lifted(0x113E17C)
def send_to_slot(m, server, src, slot, *_):
    """*src onto the link of `slot` (u8), when the server has one."""
    with m.frame(0x10) as ln:
        m.call_sret(m.main + 0x113D184, ln, server, slot & 0xFF)
        if not m.u64(ln):
            return
        _send_on(m, server, ln, m.u64(src))
        _release(m, ln)


@lifted(0x113CD5C)
def send_to_all(m, server, src, *_):
    """*src onto the link of every slot 0..4 the server has one for, then of slot 0xff."""
    for slot in (0, 1, 2, 3, 4, 0xFF):
        with m.frame(0x10) as ln:
            m.call_sret(m.main + 0x113D184, ln, server, slot)
            if m.u64(ln):
                _send_on(m, server, ln, m.u64(src))
                _release(m, ln)


@lifted(0xF6F324)
def store_entry(m, store, slot, *_):
    """Writes to x8 a strong reference to the store's entry for the u8 `slot` (u32-keyed map at
    store+0xc8), or 0."""
    out = m.x8
    node = _hash_find_u32(m, store + 0xC8, slot & 0xFF)
    o = m.u64(node + 0x18) if node else 0
    _counted_copy(m, out, o)
    return out


def _step_of(m, msg):
    return m.u64(m.u64(msg + 0x40) + 8)


@lifted(0x113C718)
def log_message(m, server, src, *_):
    """The message *src onto the server's log [server+0x50], unless the log holds its step already."""
    msg = m.u64(src)
    step = _step_of(m, msg)
    if not step:
        return
    with m.frame(0x10) as f:
        m.call_sret(m.main + 0xE63734, f, m.u64(server + 0x50), step)
        if m.u64(f):
            _release(m, f)
            return
        _push_copy(m, m.u64(server + 0x50), msg)


@lifted(0x113C4CC)
def queue_for_slot(m, server, src, slot, *_):
    """For a slot the battle mode seats (0xe7e2a0 on [[server+0x38]+0x290]+8's +0x36c, +0x370), the
    message *src onto the slot's store entry (0xf6f324), unless the entry holds its step already."""
    msg = m.u64(src)
    step = _step_of(m, msg)
    if not step:
        return
    o = m.u64(m.u64(m.u64(server + 0x38) + 0x290) + 8)
    if not m.call(m.main + 0xE7E2A0, m.u32(o + 0x36C), m.u8(o + 0x370), slot & 0xFF) & 1:
        return
    with m.frame(0x20) as f:
        m.call_sret(m.main + 0xF6F324, f, server, slot & 0xFFFFFFFF)
        e = m.u64(f)
        if not e:
            return
        m.call_sret(m.main + 0xE63734, f + 8, e, step)
        if m.u64(f + 8):
            _release(m, f + 8)
        else:
            _push_copy(m, e, msg)
        _release(m, f)


@lifted(0x1227714)
def make_message(m, o, header, body, size, *_):
    """The message object: the counted base, vtable 0x44ed338, a buffer of size + 0x20 bytes from [o+8]
    at +0x40 (its length at +0x48) holding the 32-byte header then the body."""
    _construct_counted_base(m, o)
    m.put(o, 8, m.main + MESSAGE)
    m.put(o + 0x20, 8, m.main + MESSAGE + 0x78)
    m.put(o + 0x28, 8, m.main + MESSAGE + 0xC8)
    m.put(o + 0x40, 8, 0)
    n = (size + HEADER) & 0xFFFFFFFF
    m.put(o + 0x48, 4, 0)
    data = m.vcall(m.u64(o + 8), 0x10, n, 8)
    m.put(o + 0x40, 8, data)
    m.put(o + 0x48, 4, n)
    m.write(data, m.read(header, HEADER))
    m.write(m.u64(o + 0x40) + HEADER, m.read(body, size & 0xFFFFFFFF))
    return m.u64(o + 0x40) + HEADER


@lifted(0x28015B4)
def destroy_message(m, o, *_):
    """The message object's destructor: its buffer back to [o+8] (0xb48fe8 while frees are deferred, else
    vf 0x18), the base vtables, the weak handle at +0x30 released."""
    from pokeldn.sv.battle.engine.references import _release_weak
    alloc = m.u64(o + 8)
    m.put(o, 8, m.main + MESSAGE)
    m.put(o + 0x20, 8, m.main + MESSAGE + 0x78); m.put(o + 0x28, 8, m.main + MESSAGE + 0xC8)
    data, n = m.u64(o + 0x40), m.u32(o + 0x48)
    if m.vcall(alloc, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) >= 1:
        m.call_void(m.main + 0xB48FE8, alloc, data, n, 8)
    else:
        m.vcall_void(alloc, 0x18, data, n, 8)
    v = m.u64(m.main + 0x46D8C78)
    m.put(o, 8, v + 0x10); m.put(o + 0x20, 8, v + 0x88); m.put(o + 0x28, 8, v + 0xD8)
    p = m.u64(o + 0x30)
    return _release_weak(m, p, o) if p else o


@lifted(0x113BAD8)
def send_step(m, server, kind, dest, *_):
    """One server step: the step counter server+0x198 raised; the body already received for that step in
    [[server+0x448]+0x38] (0xe63734), or else the builder 0x113c8a0 (kind, round server+0x488); the
    header {kind, step, round, dest, 5}; the message (0x1227714, 0x50 bytes from [server+8]) onto every
    link (dest 5, 0x113cd5c) or dest's (0x113e17c), the server's log (0x113c718) and the store entry of
    every slot (dest 5) or dest's (0x113c4cc). Writes to x8 {u8 [[server+0x448]+0xc4a5], u64 step, u8
    +0xc4a4}. The header's pad bytes +0x1a..+0x1f are stack the game never writes; they are zero here."""
    out = m.x8
    kind &= 0xFFFFFFFF
    m.put(out, 1, 0); m.put(out + 8, 8, 0); m.put(out + 0x10, 1, 0)
    with m.frame(0x60) as sp:
        hdr, got, body, size = sp, sp + 0x20, sp + 0x30, sp + 0x38
        m.write(sp, bytes(0x60))
        step = (m.u64(server + 0x198) + 1) & 0xFFFFFFFFFFFFFFFF
        m.put(server + 0x198, 8, step)
        b = m.u64(server + 0x448)
        received = 0
        if m.u64(b + 0x38):
            m.call_sret(m.main + 0xE63734, hdr, m.u64(b + 0x38), step)
            received = m.u64(hdr)
        if received:
            m.put(body, 8, m.u64(received + 0x40) + HEADER)
            m.put(size, 4, m.u32(received + 0x48) - HEADER)
            _release(m, hdr)
        else:
            m.call_void(m.main + 0x113C8A0, b, body, size, server + 0x488, kind)
        m.put(hdr + 0x19, 1, 5)
        m.put(hdr, 4, kind)
        m.put(hdr + 0x18, 1, dest)
        m.put(hdr + 8, 8, m.u64(server + 0x198)); m.put(hdr + 0x10, 8, m.u64(server + 0x488))
        alloc = m.u64(server + 8)
        msg = _create(m, alloc, 0x50, lambda o: m.call_void(m.main + 0x1227714, o, hdr, m.u64(body), m.u32(size)))
        m.put(got, 8, msg)
        _add_ref(m, msg)
        if dest & 0xFF == ALL:
            with m.frame(0x10) as c:
                _counted_copy(m, c, msg)
                m.call_void(m.main + 0x113CD5C, server, c)
                _release(m, c)
        else:
            with m.frame(0x10) as c:
                _counted_copy(m, c, msg)
                m.call_void(m.main + 0x113E17C, server, c, dest)
                _release(m, c)
        with m.frame(0x10) as c:
            _counted_copy(m, c, msg)
            m.call_void(m.main + 0x113C718, server, c)
            _release(m, c)
        if dest & 0xFF == ALL:
            _add_ref(m, msg)
        for slot in (range(5) if dest & 0xFF == ALL else (dest,)):
            with m.frame(0x10) as c:
                _counted_copy(m, c, msg)
                m.call_void(m.main + 0x113C4CC, server, c, slot & 0xFFFFFFFF)
                _release(m, c)
        if dest & 0xFF == ALL:
            m.put(got + 8, 8, msg)
            _release(m, got + 8)
        m.put(out + 8, 8, m.u64(server + 0x198))
        r = m.u64(server + 0x448) + 0xC4A4
        m.put(out, 1, m.u8(r + 1))
        m.put(out + 0x10, 1, m.u8(r))
        _release(m, got)
    return out


@lifted(0x113BAB8)
def send_all(m, server, kind, *_):
    return _tail(m, m.main + 0x113BAD8, server, kind, ALL)


# --- the server's per-slot message stores: what it sent each slot (server+0xc8, 0xf6f324) and what each
# slot sent it (server+0x130, 0xe634c8); each entry a message deque as above -------------------------------

@lifted(0xE634C8)
def receive_entry(m, server, slot, *_):
    """Writes to x8 a strong reference to the entry of what `slot` (u8) sent (u32-keyed map at
    server+0x130), or 0."""
    out = m.x8
    node = _hash_find_u32(m, server + 0x130, slot & 0xFF)
    _counted_copy(m, out, m.u64(node + 0x18) if node else 0)
    return out


def _deque_at(m, q, i):
    """The element slot of index i (map +0x48, 0x200 a block)."""
    return m.u64(m.u64(q + 0x48) + 8 * (i >> 9)) + 8 * (i & 0x1FF)


def _find_type(m, q, key):
    """The index of the first message whose header type (u32 [msg+0x40]) is `key`, each looked at taken
    and dropped around the read (as 0xf6f0a8 and 0xf6fd7c walk), or None."""
    if m.u64(q + 0x50) == m.u64(q + 0x48):
        return None
    start, size = m.u64(q + 0x80), m.u64(q + 0x88)
    for i in range(start, start + size):
        e = m.u64(_deque_at(m, q, i))
        if not e:
            continue
        _add_ref(m, e)
        t = m.u32(m.u64(e + 0x40))
        with m.frame(0x10) as h:
            m.put(h, 8, e)
            _release(m, h)
        if t == key:
            return i
    return None


@lifted(0xF6F0A8)
def find_type(m, q, key, *_):
    """Writes to x8 a strong reference to the first message of type `key` (u32) in q's deque, or 0."""
    out = m.x8
    i = _find_type(m, q, key & 0xFFFFFFFF)
    _counted_copy(m, out, 0 if i is None else m.u64(_deque_at(m, q, i)))
    return out


def _free_block(m, alloc, block):
    if m.vcall(alloc, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) >= 1:
        m.call_void(m.main + 0xB48FE8, alloc, block, 0x1000, 8)
    else:
        m.vcall_void(alloc, 0x18, block, 0x1000, 8)


@lifted(0x131BE1C)
def erase_at(m, d, _block, it, *_):
    """libc++ deque<T*>::erase at the element slot `it` (d: map +0..+0x18, start +0x40, size +0x48, block
    allocator +0x50): the elements on the shorter side shifted over it by move-assignment (the erased one
    released by the first move), the vacated end destroyed, start/size updated, and a block freed when two
    spare blocks gather at that end. The returned iterator is not reproduced."""
    first = m.u64(d + 8)
    if m.u64(d + 0x10) == first:
        raise UnliftedCall("0x131be1c on an empty map")
    start, size = m.u64(d + 0x40), m.u64(d + 0x48)
    at = lambda i: m.u64(first + 8 * (i >> 9)) + 8 * (i & 0x1FF)
    pos = next(i for i in range(start, start + size) if at(i) == it)
    n = pos - start
    if n <= (size - 1) >> 1:
        for i in range(pos, start, -1):            # move_backward: [start, pos) onto [start+1, pos+1)
            old = m.u64(at(i))
            m.put(at(i), 8, 0)
            if old:
                with m.frame(0x10) as h:
                    m.put(h, 8, old)
                    _release(m, h)
            v = m.u64(at(i - 1))
            m.put(at(i - 1), 8, 0)
            m.put(at(i), 8, v)
        old = m.u64(at(start))
        if old:
            with m.frame(0x10) as h:
                m.put(h, 8, old)
                _release(m, h)
        m.put(d + 0x40, 8, start + 1); m.put(d + 0x48, 8, size - 1)
        if start + 1 >= 0x400:
            blk = m.u64(m.u64(d + 8))
            _free_block(m, m.u64(d + 0x50), blk)
            m.put(d + 8, 8, m.u64(d + 8) + 8)
            m.put(d + 0x40, 8, m.u64(d + 0x40) - 0x200)
        return
    end = start + size
    for i in range(pos, end - 1):                  # move: [pos+1, end) onto [pos, end-1)
        old = m.u64(at(i))
        m.put(at(i), 8, 0)
        if old:
            with m.frame(0x10) as h:
                m.put(h, 8, old)
                _release(m, h)
        v = m.u64(at(i + 1))
        m.put(at(i + 1), 8, 0)
        m.put(at(i), 8, v)
    old = m.u64(at(end - 1))
    if old:
        with m.frame(0x10) as h:
            m.put(h, 8, old)
            _release(m, h)
    m.put(d + 0x48, 8, size - 1)
    b, e = m.u64(d + 8), m.u64(d + 0x10)
    cap = ((e - b) << 6) - 1 if e != b else 0
    if cap - (start + size - 1) >= 0x400:
        _free_block(m, m.u64(d + 0x50), m.u64(e - 8))
        m.put(d + 0x10, 8, m.u64(d + 0x10) - 8)


@lifted(0xF6FD7C)
def erase_type(m, q, key, *_):
    """The first message of type `key` (u32) erased from q's deque (0x131be1c)."""
    i = _find_type(m, q, key & 0xFFFFFFFF)
    if i is None:
        return
    it = _deque_at(m, q, i)
    return _tail(m, m.main + 0x131BE1C, q + 0x40, m.u64(q + 0x48) + 8 * (i >> 9), it)


def _seated(m, server, slot):
    o = m.u64(m.u64(m.u64(server + 0x38) + 0x290) + 8)
    return m.call(m.main + 0xE7E2A0, m.u32(o + 0x36C), m.u8(o + 0x370), slot & 0xFF) & 1


def _entry_has(m, server, getter, key, slot):
    """Whether the entry `getter` gives for slot holds a message of type key: None when there is no entry."""
    with m.frame(0x10) as f:
        m.call_sret(m.main + getter, f, server, slot & 0xFFFFFFFF)
        if not m.u64(f):
            return None
        m.call_sret(m.main + 0xF6F0A8, f + 8, m.u64(f), key & 0xFFFFFFFF)
        found = m.u64(f + 8) != 0
        if found:
            _release(m, f + 8)
        _release(m, f)
        return found


@lifted(0xF6EF64)
def sent_to(m, server, key, slot, *_):
    """Whether the server's entry for a seated slot still holds a message of type `key` it sent."""
    if not _seated(m, server, slot):
        return 0
    return int(bool(_entry_has(m, server, 0xF6F324, key, slot)))


@lifted(0xF6F590)
def received_from(m, server, key, slot, *_):
    """Whether a slot sent a message of type `key`: 1 also for a slot the mode does not seat or one with
    no entry."""
    if not _seated(m, server, slot):
        return 1
    r = _entry_has(m, server, 0xE634C8, key, slot)
    return 1 if r is None else int(r)


@lifted(0xE63380)
def answered(m, server, step, slot, *_):
    """Whether what a seated slot sent holds a message of header step `step` (0xe63734); 1 for a slot the
    mode does not seat or one with no entry."""
    if not _seated(m, server, slot):
        return 1
    with m.frame(0x10) as f:
        m.call_sret(m.main + 0xE634C8, f, server, slot & 0xFFFFFFFF)
        if not m.u64(f):
            return 1
        m.call_sret(m.main + 0xE63734, f + 8, m.u64(f), step)
        found = m.u64(f + 8) != 0
        if found:
            _release(m, f + 8)
        _release(m, f)
        return int(found)


@lifted(0xF6EDF4)
def take_answered(m, reader, key, answer, *_):
    """When the server sent the reader's slot a message of type `key` and the slot sent one of type
    `answer`: the first of each erased (0xf6fd7c) from the two entries; 1 then."""
    server, slot = m.u64(reader + 0x30), m.u32(reader + 0x38)
    if not m.call(m.main + 0xF6EF64, server, key, slot) & 1:
        return 0
    if not m.call(m.main + 0xF6F590, server, answer, slot) & 1:
        return 0
    for getter, k in ((0xF6F324, key), (0xE634C8, answer)):
        with m.frame(0x10) as f:
            m.call_sret(m.main + getter, f, server, slot)
            if m.u64(f):
                m.call_void(m.main + 0xF6FD7C, m.u64(f), k & 0xFFFFFFFF)
                _release(m, f)
    return 1


@lifted(0xF91070)
def time_left(m, timer, limit, offset, *_):
    """Seconds left of a `limit`-second timer (start ns +0, accumulated ns +8, paused bytes +0x19/+0x1a):
    paused, limit - accumulated; running, limit + offset - (now - start) - accumulated (whole seconds,
    truncated toward zero); 1 for a zero limit."""
    if not limit:
        return 1
    s = lambda v: v - (1 << 64) if v >> 63 else v
    sec = lambda ns: ns // 1000000000 if ns >= 0 else -(-ns // 1000000000)
    acc = s(m.u64(timer + 8))
    if m.u8(timer + 0x19) or m.u8(timer + 0x1A):
        return (limit - sec(acc)) & 0xFFFFFFFFFFFFFFFF
    now = m.call(m.main + 0x343D5B0, m.call(m.main + 0x343C280))
    return (limit + offset - sec(s((now - m.u64(timer)) & 0xFFFFFFFFFFFFFFFF)) - sec(acc)) & 0xFFFFFFFFFFFFFFFF


# --- the server's request flow ----------------------------------------------------------------------
# The console runs it as jobs of a scheduler and a per-frame state machine (0xf6d538) over five per-slot
# readers (0xf6df44); neither exists in a session built without the battle scene. Server reproduces their
# decisions over the engine's state with the lifted pieces above (docs/sv_raid.md, The server's flow).

WAIT = (5, 0xD, 0xB, 0xF, 9, 7, 0x21, 3, 0x23, 0x15, 0x17, 0x19, 0x13, 0x47, 0x1F, 0x1D)   # 0xf6e22c..0xf6e368
PAIRS = ((0x15, 0x16), (0x23, 0x24), (0x11, 0x12), (0x13, 0x14), (0x17, 0x18), (0x19, 0x1A), (0x1B, 0x1C),
         (0x1D, 0x1E), (0x25, 0x26), (0x1F, 0x20))                                              # 0xf6e410..
SIDE = (0, 1, 0, 0, 0)                  # the raid's side of each slot, 0x3c6a45a


class Server:
    """A battle server over a session the engine built (N): stations' messages in (receive), the
    messages it queues for each station out (sent), its flow run between them (run)."""

    def __init__(self, m, n):
        self.m, self.n = m, n
        self.c = m.u64(n + 0xB0)
        self.round_boss = m.u64(m.u64(self.c + 0x468) + 0x1B0)   # the round's list (0x16e5c90)
        self.state = [0] * 5            # reader +8: 0 idle, 1 requested, 2 command posted
        self.jobs = []
        self.ended = False
        self.timed = True               # sm +0x118: the timed check armed
        self.timer = None
        self.seen = {s: 0 for s in range(5)}
        self.log = []
        alloc = m.u64(self.c + 8)
        self.boss = m.vcall(alloc, 0x10, 0x80, 8)           # sm +0xf8: the boss's action list
        m.write(self.boss, m.read(self.round_boss, 0x80))
        m.call_void(m.main + 0xFAF024, self.boss)
        self.reader = m.vcall(alloc, 0x10, 0x40 * 5, 8)     # stand-ins: +0x30 the server, +0x38 the slot
        for s in range(5):
            r = self.reader + 0x40 * s
            m.write(r, bytes(0x40))
            m.put(r + 0x30, 8, self.c)
            m.put(r + 0x38, 4, s)

    # --- in and out --------------------------------------------------------------------------------

    def receive(self, slot, raw):
        """A station's message (32-byte header and body) into what `slot` sent (0xe634c8's entry), as
        the frame reader's 0xe106a4 stores it (0x113d5e0)."""
        m = self.m
        with m.frame(0x40) as h:
            m.write(h, raw[:HEADER])
            with m.frame((len(raw) + 0x20) & ~0xF) as body:
                m.write(body, raw[HEADER:])
                msg = _create(m, m.u64(self.c + 8), 0x50,
                              lambda o: m.call_void(m.main + 0x1227714, o, h, body, len(raw) - HEADER))
        with m.frame(0x20) as f:
            m.put(f + 8, 8, msg)
            _add_ref(m, msg)
            m.call_sret(m.main + 0xE634C8, f, self.c, slot)
            if m.u64(f):
                m.call_void(m.main + 0x113D5E0, m.u64(f), f + 8)
                _release(m, f)
            _release(m, f + 8)

    def sent(self, slot):
        """The messages queued for `slot`'s link since the last call."""
        m, out = self.m, []
        node = _hash_find_u32(m, self.c + 0x1A0, slot)
        if node:
            q = m.u64(m.u64(node + 0x18) + 0x48)
            start, size = m.u64(q + 0x80), m.u64(q + 0x88)
            for i in range(start + self.seen[slot], start + size):
                msg = m.u64(_deque_at(m, q, i))
                out.append(m.read(m.u64(msg + 0x40), m.u32(msg + 0x48)))
            self.seen[slot] = size
        return out

    def frame(self, slot, msg):
        """A message on the wire: key 0x7b, the address (setup u32 +0x2c, 1, slot), the length."""
        m = self.m
        return struct.pack("<HIIII", 0x7B, m.u32(m.u64(self.n + 0x38) + 0x2C), 1, slot, len(msg)) + msg

    def clock(self, left):
        """The battle timer at `left` seconds (a paused stand-in timer, 0xf91070)."""
        m = self.m
        if self.timer is None:
            self.timer = m.vcall(m.u64(self.c + 8), 0x10, 0x20, 8)
            m.write(self.timer, bytes(0x20))
            m.put(self.timer + 0x18, 1, 1)
            m.put(self.timer + 0x19, 1, 1)
        limit = m.u16(self.n + 0x8A)
        m.put(self.timer + 8, 8, (limit - left) * 1000000000)

    def handle(self, messages, left=None, stations=(2,)):
        """Serve: the battle timer at `left` seconds (when given), each (slot, message) received in turn
        with the flow run after it; returns the frames queued for each slot in `stations`."""
        if left is not None:
            self.clock(left)
        self.run()
        for slot, raw in messages:
            self.receive(slot, raw)
            self.run()
        return {s: [self.frame(s, msg) for msg in self.sent(s)] for s in stations}

    # --- the flow ----------------------------------------------------------------------------------

    def run(self, limit=10000):
        """The flow until nothing more happens: the job at the head runs while it can; with no job, one
        pass of the per-frame machine."""
        for _ in range(limit):
            if self.ended:
                return
            if self.jobs:
                if self.jobs[0]() == "wait":
                    return
                self.jobs.pop(0)
                continue
            if not self._frame():
                return
        raise UnliftedCall("the server flow does not settle")

    def _send(self, kind, dest=ALL):
        m = self.m
        with m.frame(0x20) as r:
            m.call_sret(m.main + 0x113BAD8, r, self.c, kind, dest)
            res = (m.u8(r), m.u64(r + 8), m.u8(r + 0x10))
        self.log.append((kind, dest, res[1]))
        return res

    def _sent(self, key, slot):
        return self.m.call(self.m.main + 0xF6EF64, self.c, key, slot) & 1

    def _received(self, key, slot):
        return self.m.call(self.m.main + 0xF6F590, self.c, key, slot) & 1

    def _frame(self):
        """0xf6d538 with no job running: the boss's queued actions first (a raid action), else the timed
        check, else each slot's reader. Whether anything was posted or erased."""
        m = self.m
        if m.u8(self.boss + 0x5C):
            self._post_raid_action(self.boss)
            self.timed = True
            return True
        if self.timed and self.timer is not None and m.u32(self.boss + 0x7C) == 0 and self._timed_check():
            return True
        moved = False
        for s in range(5):
            moved |= self._read(s)
        return moved

    def _timed_check(self):
        """0xf6d62c: the boss's triggers checked on a copy of the list against the timer (0xf6dd84); when
        one fires, the copy's actions reach the list (the console sends them as message 0x51)."""
        m = self.m
        with m.frame(0x80) as t:
            m.write(t, bytes(0x80))
            m.put(t, 8, m.u64(self.round_boss)); m.put(t + 8, 8, m.u64(self.round_boss + 8))
            m.write(t + 0x10, m.read(m.u64(m.u64(self.round_boss + 8) + 0x310) + 0x1C, 0x4A))
            if not m.call(m.main + 0xF6DD84, t, self.timer) & 1:
                return False
            m.write(self.boss + 0x5C, m.read(t + 0x5C, 0x24))
        self.timed = False
        return True

    def _read(self, s):
        """0xf6df44 for a seated slot: a player slot requests a command once nothing it was sent waits for
        an answer (0xf70078), posts the round once it answered the request (0xf6e6a8), and returns idle
        once it answered the round; every slot's answered pairs are erased (0xf6e3ac)."""
        m = self.m
        if not _seated(m, self.c, s):
            return False
        if SIDE[s] != SIDE[m.u8(self.n + 0x95)]:
            return self._erase_pairs(s)
        st = self.state[s]
        if st == 0:
            if any(self._sent(k, s) for k in WAIT):
                return self._erase_pairs(s)
            self.state[s] = 1
            self.jobs.append(lambda s=s: self._request(s))
            return True
        if st == 1:
            if self._sent(5, s) and self._received(6, s):
                self._post_command(s)
                self.state[s] = 2
                return True
            return False
        if m.call(m.main + 0xF6EDF4, self.reader + 0x40 * s, 0x15, 0x16) & 1:
            self.state[s] = 0
            return True
        return False

    def _erase_pairs(self, s):
        m = self.m
        hit = False
        for k, a in PAIRS:
            hit |= bool(m.call(m.main + 0xF6EDF4, self.reader + 0x40 * s, k, a) & 1)
        return hit

    def _request(self, s):
        """ServerRequest (0x138d178): message 5 to the slot."""
        self._send(5, s)

    def _post_command(self, s):
        """0xf6e6a8: a zeroed block, kind 0x15 at +0x238, the slot's command gathered in (0xf702ec, done key
        5, key 6), posted as a ServerCommand."""
        m = self.m
        with m.frame(0x240) as b:
            m.write(b, requests.posted(0x15))
            m.call_void(m.main + 0xF702EC, self.reader + 0x40 * s, b, 5, 6)
            block = m.read(b, 0x240)
        self.jobs.append(lambda block=block: self._command(block))

    def _command(self, block):
        """ServerCommand (0x16e4f10): the block into the server (0x113bac0), the round sent to every
        station, then its result's case (0x16e4ff0)."""
        m = self.m
        with m.frame(0x240) as f:
            m.write(f, block)
            m.call(m.main + 0x113BAC0, self.c, f)
        r = self._send(int.from_bytes(block[0x238:0x23C], "little"))
        self._case(8 if r[2] else r[0])

    def _case(self, k):
        """0x16e4ff0 (jump table 0x3c61c38): 0 nothing, 4 an empty round (0x16e5cac), 6 the round's boss
        actions as a raid action when one is the shield (0x16e5ad0)."""
        m = self.m
        if k == 0:
            return
        if k == 4:
            self.jobs.append(lambda: self._command(requests.posted(0x15)))
            return
        if k == 6:
            obj = self.round_boss
            if m.call(m.main + 0x1142804, obj) & 1 and m.u8(obj + 0x5C) == 1:
                self._post_raid_action(obj)
            return
        if k == 7:                              # the battle's end: capture and results (0x16e56a0)
            self.ended = True
            return
        raise UnliftedCall(f"0x16e4ff0 case {k}")

    def _post_raid_action(self, obj):
        """0x16e5ad0 / 0xf6d8d4: a RaidAction of the list's actions (0x114fb2c), from its state 0 (message
        0x47 first) when the first is the shield, else from state 2."""
        m = self.m
        with m.frame(0x40) as w:
            m.write(w, bytes(0x40))
            n = m.call(m.main + 0x114FB2C, obj, w)
            actions = m.read(w, 0x40)
        first = 0 if m.u8(obj + 0x5C) == 1 else 2
        job = {"state": first, "first": first, "count": n, "actions": actions, "obj": obj}
        self.jobs.append(lambda job=job: self._raid_action(job))

    def _raid_action(self, job):
        """RaidAction (0x18c92a8): 0 message 0x47 to every station; 1 wait until every seated slot sent a
        message of that step (0xe63380); 2 the slot-1 block of the actions (0xf6fc54, count +0x231), the
        round to every station; 3 its result's case, the list cleared (0xfaf024), and after a 0x47 every
        seated slot's 0x47 and 0x48 erased."""
        m = self.m
        while True:
            st = job["state"]
            if st == 0:
                job["step"] = self._send(0x47)[1]
            elif st == 1:
                if not all(m.call(m.main + 0xE63380, self.c, job["step"], s) & 1 for s in range(5)):
                    return "wait"
            elif st == 2:
                with m.frame(0x250) as b:
                    m.write(b, requests.posted(0x15))
                    with m.frame(0x40) as a:
                        m.write(a, job["actions"])
                        for i in range(job["count"]):
                            m.call(m.main + 0xF6FC54, b + 0x70 + 0x10 * i, a + 0x10 * i)
                    m.put(b + 0x231, 1, job["count"])
                    m.call(m.main + 0x113BAC0, self.c, b)
                r = self._send(0x15)
                job["result"] = 8 if r[2] else r[0]
            else:
                self._case(job["result"])
                m.call_void(m.main + 0xFAF024, job["obj"])
                if job["first"] != 2:
                    for s in range(5):
                        if _seated(m, self.c, s) and self._sent(0x47, s) and self._received(0x48, s):
                            with m.frame(0x10) as f:
                                m.call_sret(m.main + 0xF6F324, f, self.c, s)
                                if m.u64(f):
                                    m.call_void(m.main + 0xF6FD7C, m.u64(f), 0x47)
                                    _release(m, f)
                                m.call_sret(m.main + 0xE634C8, f, self.c, s)
                                if m.u64(f):
                                    m.call_void(m.main + 0xF6FD7C, m.u64(f), 0x48)
                                    _release(m, f)
                return
            job["state"] += 1
