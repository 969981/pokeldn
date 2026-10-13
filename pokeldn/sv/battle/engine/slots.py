"""Battle client slots: which slot a party position maps to in each battle mode."""

from pokeldn.sv.battle.machine import lifted

_MODE1_A = (2, 2, 2, 0, 2)      # 0x3c6a304
_MODE1_B = (3, 3, 3, 3, 5)      # 0x3c6a318


@lifted(0xE7E2A0)
def slot_matches(m, mode, rule, slot, *_):
    mode &= 0xFFFFFFFF; rule &= 0xFF; slot = slot & 0xFFFFFFFF
    slot = slot - (1 << 32) if slot & 0x80000000 else slot
    if slot > 4:
        return 0
    if (5 if mode > 2 else 0) == slot:
        return 1
    if mode == 2:
        v = 2 if rule else 5
    elif mode in (0, 1):
        v = 1
    else:
        v = 5
    if v == slot:
        return 1
    if mode == 2:
        v = 3 if rule > 1 else 5
    elif mode == 1:
        v = _MODE1_A[rule - 1] if 0 <= rule - 1 < 5 else 0
    else:
        v = 5
    if v == slot:
        return 1
    if mode == 2:
        w = 5 if rule < 3 else 4
    elif mode == 1:
        w = _MODE1_B[rule - 1] if 0 <= rule - 1 < 5 else 1
    else:
        w = 5
    if w == slot:
        return 1
    return int((1 if mode == 2 else 5) == slot)


def _slot_counts(mode, rule):
    if mode == 0:
        return (1, 1, 0, 0, 0, 9)
    if mode == 1:
        if 1 <= rule <= 3:
            return (1, 1, 1, 1, 0, 7)
        return {4: (2, 1, 0, 1, 0, 7), 5: (1, 1, 1, 0, 0, 8)}.get(rule, (2, 2, 0, 0, 0, 7))
    if mode == 2:
        return ((1, 6, 0, 0, 0, 4), (1, 6, 1, 0, 0, 3), (1, 6, 1, 1, 0, 2))[rule] if rule < 3 \
            else (1, 6, 1, 1, 1, 1)
    return (0, 0, 0, 0, 0, 11)


@lifted(0xFF9128)
def positions_of_slot(m, mode, rule, slot, *_):
    """How many of the battle's ten positions belong to client slot `slot` (5 = none)."""
    slot &= 0xFFFFFFFF
    return _slot_counts(mode & 0xFFFFFFFF, rule & 0xFF)[slot] if slot <= 5 else 0
