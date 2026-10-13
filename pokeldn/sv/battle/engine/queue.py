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
