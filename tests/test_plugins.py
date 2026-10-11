"""Plugins (pokeldn.plugins): a folder plugin's tool runs through the app's own child-process path,
its radio carries the LDN calls, and a broken or unwanted plugin adds nothing."""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import trio

from pokeldn import plugins
from pokeldn.app import paths

ROOT = Path(__file__).resolve().parents[1]

TOOL_PLUGIN = '''
from pokeldn.plugins import Field, Tool

def register(api):
    api.add_tool("frlg", Tool("example-echo", "Echo", "echo.py", "Writes its arguments.", ("Nothing to press.",),
                              fields=(Field("--word", "Word", default="hello"),), fixed=("--out", "echo.json")))
'''
ECHO = '''
import argparse, json, sys

def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out")
    parser.add_argument("--word")
    parser.add_argument("--extra")
    return parser

if __name__ == "__main__":
    args = build_parser().parse_args()
    json.dump(sys.argv[1:], open(args.out, "w"))
'''
RADIO_PLUGIN = '''
import contextlib
from ldn import wlan

SEEN = []

class FakeFactory:
    pass

def install(arg, log):
    SEEN.append(arg)
    @contextlib.asynccontextmanager
    async def factory():
        yield FakeFactory()
    wlan.set_factory(factory)

def register(api):
    api.add_radio("fake", install, "Fake radio")
'''


def make(base: Path, name: str, source: str, api: int = 1, **files) -> Path:
    folder = base / name
    folder.mkdir(parents=True)
    (folder / "plugin.toml").write_text(f'id = "{name}"\nname = "{name.title()}"\napi = {api}\n')
    (folder / "plugin.py").write_text(textwrap.dedent(source))
    for filename, text in files.items():
        (folder / filename.replace("_", ".")).write_text(textwrap.dedent(text))
    return folder


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setattr(paths, "DATA", data)
    monkeypatch.delenv("POKELDN_PLUGINS", raising=False)
    monkeypatch.delenv("POKELDN_RADIO", raising=False)
    plugins._reset()
    from ldn import wlan
    yield data
    plugins._reset()
    wlan.set_factory(None)


def test_a_folder_plugin_tool_runs_through_the_cli_child_path(tmp_path):
    folder = make(tmp_path / "elsewhere", "echo", TOOL_PLUGIN, echo_py=ECHO)
    env = dict(os.environ, POKELDN_PLUGINS=str(folder), POKELDN_DATA=str(tmp_path / "data"), PYTHONPATH=str(ROOT))
    run = lambda *a: subprocess.run([sys.executable, "-m", "pokeldn", *a], cwd=tmp_path, env=env,  # noqa: E731
                                    capture_output=True, text=True, timeout=60)
    listed = run("--list")
    assert "example-echo" in listed.stdout and "FireRed & LeafGreen: Echo" in listed.stdout
    assert "echo                 Echo: loaded" in run("--plugins").stdout
    done = run("example-echo", "--", "--extra", "1")
    assert done.returncode == 0, done.stderr
    assert json.loads((tmp_path / "echo.json").read_text()) == ["--out", "echo.json", "--word", "hello",
                                                                "--extra", "1"]


def test_a_plugin_radio_carries_the_ldn_calls(isolated, tmp_path, monkeypatch):
    folder = make(tmp_path, "fakeradio", RADIO_PLUGIN)
    monkeypatch.setenv("POKELDN_PLUGINS", str(folder))
    monkeypatch.setenv("POKELDN_RADIO", "fake:port-7")
    from ldn import wlan
    from pokeldn.ldn import transport

    async def factory_type():
        async with wlan.create_factory() as factory:
            return type(factory).__name__

    assert trio.run(factory_type) == "FakeFactory"
    assert sys.modules["pokeldn_plugin_fakeradio"].SEEN == ["port-7"]
    assert transport.board_radio()                       # no iw, no vif cleanup
    assert transport.find_ap_phy(log=lambda _: None) == "fake"


def test_an_unknown_radio_is_refused_before_any_ldn_call(isolated, monkeypatch):
    monkeypatch.setenv("POKELDN_RADIO", "nothing:x")
    from ldn import wlan

    async def open_factory():
        async with wlan.create_factory():
            pass

    with pytest.raises(RuntimeError, match="names no radio"):
        trio.run(open_factory)


def test_a_plugin_toml_that_does_not_parse_runs_no_code(isolated, tmp_path, monkeypatch):
    folder = make(tmp_path, "badtoml", "raise SystemExit('imported')")
    (folder / "plugin.toml").write_text('id = "badtoml"\napi = \n')
    monkeypatch.setenv("POKELDN_PLUGINS", str(folder))
    [plugin] = plugins.load()
    assert plugin.error.startswith("plugin.toml:") and not plugin.loaded


def test_a_plugin_in_the_data_folder_loads_only_once_enabled(isolated):
    make(isolated / "plugins", "echo", TOOL_PLUGIN, echo_py=ECHO)
    assert [p.id for p in plugins.discover()] == ["echo"]
    assert plugins.load() == []
    assert "example-echo" not in {t.key for g in plugins.games() for t in g.tools}
    (isolated / "settings.json").write_text(json.dumps({"plugins": ["echo"]}))
    plugins._reset()
    tool = next(t for g in plugins.games() if g.key == "frlg" for t in g.tools if t.key == "example-echo")
    assert tool.script == str(isolated / "plugins" / "echo" / "echo.py")


@pytest.mark.parametrize("source, api, error", [
    (TOOL_PLUGIN, 2, "written for plugin API 2"),
    (TOOL_PLUGIN.replace('"example-echo"', '"frlg-trade-host"'), 1, "already taken"),
    (TOOL_PLUGIN.replace('add_tool("frlg"', 'add_tool("snes"'), 1, "no game 'snes'"),
    (RADIO_PLUGIN.replace('"fake"', '"esp32"'), 1, "already taken"),
    (RADIO_PLUGIN + "\n    raise ValueError('half done')\n", 1, "half done"),
], ids=["api-version", "tool-key-taken", "unknown-game", "radio-taken", "raises-after-a-radio"])
def test_a_broken_plugin_keeps_its_error_and_adds_nothing(isolated, tmp_path, monkeypatch, source, api, error):
    broken = make(tmp_path, "broken", source, api=api)
    good = make(tmp_path, "good", TOOL_PLUGIN.replace("example-echo", "good-echo"))
    monkeypatch.setenv("POKELDN_PLUGINS", os.pathsep.join(map(str, (broken, good))))
    state = {p.id: p for p in plugins.load()}
    assert error in state["broken"].error and not state["broken"].loaded
    assert state["good"].loaded
    keys = {t.key for g in plugins.games() for t in g.tools}
    assert "good-echo" in keys and "example-echo" not in keys
    assert plugins.radios() == []
