"""A raid battle served from the host's station (pokeldn.sv.raid_battle) against a scripted console at slot 2,
from the rme10 host's bootstrap: its first frames against the six battle-start messages a retail host sent,
and the battle run to its end. Needs Scarlet 4.0.0's image and tables (test_sv_battle_served.game_files)."""
import pytest

from pokeldn.sv import raid, raid_battle as rb
from test_sv_battle_served import DATA, game_files

PADDING = set(range(18 + 4, 18 + 8)) | set(range(18 + 0x1A, 18 + 0x20))
BOOT = bytes.fromhex(DATA["bootstrap"])


def scripted(battle, until=900.0, delay=0.3, answer_end=True):
    """The console at slot 2: each odd server step answered `delay` later, a request with its Pokemon's
    first move on the boss and the boss's first move on it. -> [(x, message)] it received."""
    moves = (rb.first_move(BOOT[0x158:0x2B0]), rb.first_move(BOOT[4 * 0x158:5 * 0x158]))
    now, pending, got = 0.0, [], []
    battle.start(now)
    while not battle.over and now < until:
        now += 0.1
        for item in [p for p in pending if p[0] <= now]:
            pending.remove(item)
            battle.receive(2, item[1], now)
        for slot, raw in battle.poll(now):
            assert slot == 2
            x, y, msg = rb.unframe(raw)
            assert (x, y) in ((rb.SERVER, 2), (rb.RELAY, rb.EVERY))
            got.append((x, msg))
            if x == rb.SERVER and msg[0] == rb.REQUEST:
                pending.append((now + delay, rb.command(msg, 2, *moves)))
            elif x == rb.SERVER and msg[0] & 1 and (answer_end or msg[0] != rb.FADE_END):
                pending.append((now + delay, rb.answer(msg, 2)))
    return got


@pytest.fixture(scope="module")
def served():
    return scripted(rb.RaidBattle(game_files(), BOOT))


def test_the_first_frames_are_a_retail_hosts_battle_start(served):
    """Message 1, the notice 0x46 and the four local stations' answers, as a retail host sent them
    (raid.HANDOFF), outside the header bytes its stack filled."""
    ours = [rb.frame(rb.SERVER if x == rb.SERVER else rb.RELAY, 2 if x == rb.SERVER else rb.EVERY, m)
            for x, m in served[:len(raid.HANDOFF)]]
    for a, b in zip(ours, raid.HANDOFF):
        assert len(a) == len(b) and [i for i in range(len(a)) if a[i] != b[i] and i not in PADDING] == []


def test_the_battle_runs_to_its_end_against_a_scripted_console(served):
    kinds = [m[0] for x, m in served if x == rb.SERVER]
    assert kinds[:3] == [0x01, 0x11, 0x05] and kinds[-5:] == [0x25, 0x29, 0x49, 0x35, 0x37]
    relayed = {(m[0], m[0x19]) for x, m in served if x == rb.RELAY}
    assert {(0x06, 0), (0x06, 2), (0x06, 3), (0x06, 4)} <= relayed


def test_a_console_that_never_answers_the_end_is_let_go():
    """0x37 answered by no one: the battle is over END_WAIT after it."""
    battle = rb.RaidBattle(game_files(), BOOT)
    got = scripted(battle, answer_end=False)
    assert battle.over and [m[0] for x, m in got if x == rb.SERVER][-1] == 0x37
