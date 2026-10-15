import json
import os
import time
from pathlib import Path

import pytest

from pokeldn import meta
from tests.test_pokemon_service import TRAINER, service  # noqa: F401 - shared PKHeX fixture


SOURCE = {"Charizard": {"Mixed": {
    "item": ["Leftovers", "Lum Berry"],
    "nature": ["Timid", "Modest"],
    "evs": {"spa": 252, "spe": 252, "hp": 4},
    "moves": ["Flamethrower", ["Dragon Claw", "Fly"], "Brick Break"],
}}}


def test_meta_cache_refreshes_then_survives_an_offline_refresh(tmp_path):
    payload = json.dumps(SOURCE).encode()
    calls = []

    def fetch(url, timeout):
        calls.append((url, timeout))
        return payload

    data, stale = meta.load_format("gen3ou", cache=tmp_path, fetch=fetch)
    assert data == SOURCE and not stale and len(calls) == 1
    data, stale = meta.load_format("gen3ou", cache=tmp_path,
                                   fetch=lambda *_: pytest.fail("downloaded again"))
    assert data == SOURCE and not stale
    old = time.time() - meta.CACHE_SECONDS - 1
    os.utime(tmp_path / "gen3ou.json", (old, old))
    data, stale = meta.load_format(
        "gen3ou", cache=tmp_path,
        fetch=lambda *_: (_ for _ in ()).throw(OSError("offline")))
    assert data == SOURCE and stale


def test_source_alternatives_remain_visible_and_become_explicit_candidates():
    build = {"species": "Charizard", "role": "Mixed", "format": "Gen 3 OU",
             "set": SOURCE["Charizard"]["Mixed"]}
    variants = list(meta.alternatives(build))
    assert len(variants) == 8
    resolved, notes = variants[0]
    text = meta.showdown(build, resolved)
    assert "Charizard @ Leftovers" in text and "Timid Nature" in text and "- Dragon Claw" in text
    assert notes == ["item: Leftovers", "nature: Timid", "move 2: Dragon Claw"]
    assert ("Moves", "Flamethrower / Dragon Claw / Fly / Brick Break") in meta.preview(build)


def test_only_verified_formats_are_exposed_for_each_requested_game():
    assert {key for key, _ in meta.formats("frlg")} == {"gen3ou", "gen3uu", "gen3ubers"}
    assert meta.formats("bdsp") == (("gen8bdspou", "BDSP OU"),)
    assert meta.formats("za") == () and "No verified" in meta.unavailable("za")


@pytest.mark.parametrize("game,build", [
    ("frlg", {"species": "Charizard", "role": "Mixed", "format": "Gen 3 OU", "set": {
        "item": "Leftovers", "nature": "Timid", "moves": ["Flamethrower", "Fly", "Dragon Claw"]}}),
    ("bdsp", {"species": "Garchomp", "role": "Attacker", "format": "BDSP OU", "set": {
        "item": "Choice Scarf", "ability": "Rough Skin", "nature": "Jolly",
        "evs": {"atk": 252, "spd": 4, "spe": 252},
        "moves": ["Earthquake", "Outrage", "Stone Edge"]}}),
])
def test_a_meta_build_uses_the_existing_parser_and_legal_builder(service, game, build):
    found, built, choices = meta.build_legal(service, game, build, TRAINER)
    assert found["species"] == build["species"] and built["legal"] and not choices
    assert Path(built["file"]).is_file()


def test_a_meta_build_absent_from_the_target_game_is_refused(service):
    build = {"species": "Garchomp", "role": "Wrong generation", "format": "Gen 3 OU",
             "set": {"moves": ["Earthquake"]}}
    with pytest.raises(meta.MetaError, match="not legal for FRLG.*not in this game"):
        meta.build_legal(service, "frlg", build, TRAINER)
