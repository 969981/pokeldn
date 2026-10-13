"""The C library and Horizon calls the server reaches."""

from pokeldn.sv.battle.machine import UnliftedCall, lifted

FAKE_THREAD = 0x7F0001000      # what GetCurrentThread returns in the engine's address space


@lifted(0x343C220)
def memset(m, dst, value, n, *_):
    m.write(dst, bytes([value & 0xFF]) * n)
    return dst


@lifted(0x343C210)
def memcpy(m, dst, src, n, *_):
    m.write(dst, m.read(src, n))
    return dst


@lifted(0x343C6F0)
def memcmp(m, a, b, n, *_):
    x, y = m.read(a, n), m.read(b, n)
    for i in range(n):
        if x[i] != y[i]:
            return (x[i] - y[i]) & 0xFFFFFFFF
    return 0


@lifted(0x343C290)
def get_current_thread(m, *_):
    return FAKE_THREAD


@lifted(0x343E5E0)
def signal_light_event(m, event, *_):
    """The server signals events that are already signalled: nothing changes."""
    if m.u8(event) != 1:
        raise UnliftedCall("signal of an unsignalled event")
    return event
