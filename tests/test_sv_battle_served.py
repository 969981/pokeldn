"""A raid battle served by the engine (pokeldn.sv.battle.engine.server.Server) from a Scarlet 4.0.0 host's
own bootstrap and the stations' messages its server received, against the frames that server sent the guest
between two emulated consoles (docs/sv_raid.md, The server's flow). The session needs the game's image and
romfs tables in scratchpad/."""
import base64
import json
import os
import re
import sys
import zlib
from pathlib import Path

import pytest

from pokeldn import gen9

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((Path(__file__).parent / "data" / "sv_raid_served.json").read_text())
BATTLE = ROOT / "scratchpad" / "battle"
ROMFS = ROOT / "scratchpad" / "sv" / "romfs"
EMULATOR_NAMES = {"Player", "POKELDN", "VMJOINER"}
HEADER = 18 + 0x20                 # the frame's address and length, then the message header
PADDING = set(range(4, 8)) | set(range(0x1A, 0x20))       # header bytes the game copies from its stack


def events():
    blob = zlib.decompress(base64.b64decode(DATA["blob"]))
    return [(kind, t, slot, blob[at:at + n]) for kind, t, slot, at, n in DATA["events"]]


def test_the_recorded_battle_names_only_an_emulated_player():
    boot = bytes.fromhex(DATA["bootstrap"])
    data = boot + b"".join(e[3] for e in events())
    assert {m.decode("utf-16-le") for m in re.findall(rb"(?:[\x20-\x7e]\x00){4,}", data)} <= EMULATOR_NAMES
    assert not re.search(rb"u-[0-9a-z]{20}", data)
    owners = {gen9.read(gen9.decrypt(boot[o:o + 0x158]))["ot_name"] for o in (0, 0x158, 0x560)}
    assert owners <= EMULATOR_NAMES | {""}


@pytest.fixture(scope="module")
def session():
    if not (BATTLE / "arena" / "image.pkl").exists() or not ROMFS.exists():
        pytest.skip("needs Scarlet 4.0.0's image and romfs tables in scratchpad/")
    for sub in ("standalone", "arena"):
        if str(BATTLE / sub) not in sys.path:
            sys.path.insert(0, str(BATTLE / sub))
    import standalone
    from pokeldn.sv.battle.engine import arena, session as build
    boot = bytes.fromhex(DATA["bootstrap"])
    m = standalone.Standalone(standalone.static_page)
    arena.build(m)
    app = build.application_allocator(m)
    build.build_handles(m, app)
    names = [t[4] for t in build.TABLES] + [build.IDHASH[4]]
    build.build_tables(m, app, {p: (ROMFS / p).read_bytes() for p in names})
    saved = build.RAID_SETUP
    build.RAID_SETUP = tuple((o, s, 0 if o == 0x90 else v, n) for o, s, v, n in saved)   # the host's slot 0
    try:
        n = build.build_session(m, app, boot, standalone.generated_partners(boot))
    finally:
        build.RAID_SETUP = saved
    build.start_states(m, n)
    return m, n


def serve(m, n):
    from pokeldn.sv.battle.engine import server
    srv = server.Server(m, n)
    ev = events()
    srv.clock(ev[0][1])
    srv.setup()
    srv.run()
    ours = []
    for kind, t, slot, data in ev:
        ours += srv.handle([(slot, data)] if kind == "in" else [], t)[2]
    return ours, [e[3] for e in ev if e[0] == "out"]


def unwritten(frame):
    """The offsets the game never writes: header padding, and a round's or capture's request block bytes."""
    from pokeldn.sv.battle.engine import requests
    out = {HEADER - 0x20 + i for i in PADDING}
    if frame[HEADER - 0x20] in (0x15, 0x25):
        out |= {HEADER + i for i in requests.UNWRITTEN}
    return out


def test_the_served_battle_sends_the_guest_the_servers_frames(session):
    m, n = session
    ours, wire = serve(m, n)
    assert len(ours) == len(wire) == 24
    for i, (a, b) in enumerate(zip(ours, wire)):
        skip = unwritten(b)
        assert len(a) == len(b) and [o for o in range(len(a)) if a[o] != b[o] and o not in skip] == [], i
    assert [f[HEADER - 0x20] for f in wire[-3:]] == [0x25, 0x29, 0x49]
