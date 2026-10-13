"""The server command queue object: u32 length at +0x68, bytes from +0x70 (docs/sv_raid.md, The server
command queue)."""

from pokeldn.sv.battle import queue as codec
from pokeldn.sv.battle.machine import lifted

LENGTH, DATA = 0x68, 0x70


def format_of(command):
    return codec.COMMAND_FORMAT[command] if command < len(codec.COMMAND_FORMAT) else 0


def argument_count(fmt):
    return 10 if fmt in (0x10, 0x20) else fmt & 0xF


@lifted(0x119BF58)
def write(m, que, command, fmt, args_ptr, *_):
    """Append one command whose u32 arguments sit at `args_ptr`."""
    fmt &= 0xFF
    args = [m.u32(args_ptr + 4 * k) for k in range(len(codec.FORMATS[fmt]))]
    append(m, que, command, fmt, args)


def append(m, que, command, fmt, args):
    widths = codec.FORMATS[fmt]
    acc = nbits = 0
    for w, v in zip(widths, args):
        acc = acc << w | (v & ((1 << w) - 1)); nbits += w
    body = (command & 0xFFFF).to_bytes(2, "big") + acc.to_bytes((nbits + 7) // 8, "big")
    n = m.u32(que + LENGTH)
    m.write(que + DATA + n, body)
    m.put(que + LENGTH, 4, n + len(body))


@lifted(0x119AFF0)
def push(m, que, command, *varargs):
    """The variadic push: the id's format from the queue's map, then that many u32 arguments."""
    command &= 0xFFFF
    fmt = format_of(command)
    args = [v & 0xFFFFFFFF for v in varargs[:argument_count(fmt)]]
    args += [0] * (len(codec.FORMATS[fmt]) - len(args))
    append(m, que, command, fmt, args)


@lifted(0x10AFCB8)
def reserve_group(m, que, placeholder, group, size, *_):
    """Reserve a group at the queue's end and return where it starts. With no size, the room is a
    zero-argument `placeholder` command; its first three bytes become the group id and length."""
    start = m.u32(que + LENGTH)
    size &= 0xFFFFFFFF
    if size & 0xFF:
        size = (size + 3) & 0xFFFFFFFF
    else:
        fmt = format_of(placeholder & 0xFFFF)
        append(m, que, placeholder, fmt, [0] * len(codec.FORMATS[fmt]))
        size = (m.u32(que + LENGTH) - start) & 0xFFFFFFFF
    at = start & 0xFFFF
    m.put(que + DATA + at, 1, (group >> 8) & 0xFF)
    m.put(que + DATA + ((at + 1) & 0xFFFFFFFF), 1, group & 0xFF)
    m.put(que + DATA + ((at + 2) & 0xFFFFFFFF), 1, (size - 3) & 0xFF)
    m.put(que + LENGTH, 4, at + (size & 0xFF))
    return start
