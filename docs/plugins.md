---
title: Plugins
---
# Plugins

A plugin adds tools to the app and radios to the wireless layer without changing pokeldn. Code:
`pokeldn/plugins.py` (the loader and the API), `pokeldn/ldn/radios.py` (the radio lookup). The
project does not distribute, review or support third-party plugins.

A plugin runs as Python inside pokeldn, with the same access to files, keys and the network.
Plugins are off until enabled.

## Where plugins are found

| source | loaded when |
|---|---|
| a folder in `plugins/` in the app's data folder (`~/Library/Application Support/pokeldn/plugins` on macOS) | Settings, Show advanced settings, Plugins, turns it on |
| a folder named in `POKELDN_PLUGINS` (folders separated by `:`, `;` on Windows) | always, in that process and its runs |
| an installed Python package with an entry point in the `pokeldn.plugins` group | Settings turns it on |

Settings applies a change at the next app start. `python -m pokeldn --plugins` lists every plugin
found and whether it loaded or why it failed.

## A folder plugin

    my-plugin/
        plugin.toml
        plugin.py
        echo.py

`plugin.toml`:

```toml
id = "my-plugin"            # unique; Settings stores it
name = "My plugin"
description = "One line shown in Settings."
version = "0.1"
api = 1                     # the plugin API this was written for
module = "plugin"           # plugin.py; optional
```

`plugin.py` defines `register(api)`. A packaged plugin's entry point names a module with the same
function. The plugin's folder is on `sys.path`, so modules it ships next to `plugin.py` import. The
packaged app has no `pip`, so a folder plugin ships any dependency that is not already in pokeldn.

```python
from pokeldn.plugins import Field, Game, Tool


def register(api):
    api.add_tool("frlg", Tool("my-echo", "Echo", "echo.py", "Prints a word.", ("Nothing to press.",),
                              fields=(Field("--word", "Word", default="hello"),)))
```

A plugin that raises in `register`, targets another API version or takes a name already in use
adds nothing; Settings shows the error and the other plugins still load.

## The API, version 1

| call | effect |
|---|---|
| `api.add_tool(game, tool)` | adds a `Tool` under the game whose key is `game`: `frlg`, `lgpe`, `swsh`, `bdsp`, `pla`, `sv`, `za`, or one the plugin added |
| `api.add_game(game, icon="")` | adds a new game section with its tools; `icon` is an image file in the plugin |
| `api.add_radio(scheme, install, label="")` | makes `POKELDN_RADIO=scheme:ARG` call `install(ARG, log)` before the first LDN call, and adds the radio to Settings |
| `api.folder` | the plugin's folder, or None for a package |
| `api.version` | the API version, `1` |

`Tool`, `Field` and `Game` are the app's own catalog types (`pokeldn/app/catalog.py`); a field's
`flag` is the argument the app passes to the tool's script. A tool key or game key may not repeat
one that exists.

## A tool's script

A tool runs as the app's own child process, in the session folder, with the radio settings in its
environment. A relative `script` path is relative to the plugin's folder. The app imports the script
to read its arguments for the Advanced tab, so the script follows the same rule as `bin/`: a
`build_parser()` that returns its `argparse` parser, and the work under `if __name__ == "__main__"`.

```python
import argparse


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--word")
    return parser


if __name__ == "__main__":
    print("echo:", build_parser().parse_args().word)
```

A line the script prints shows in the session's output. `[done] trade N complete` ticks a queued
trade off, as `pokeldn.ldn.show_done` prints it.

## A radio

The LDN layer reaches the air through `ldn.wlan.create_factory`. A radio's `install` calls
`ldn.wlan.set_factory(factory)`, where `factory()` is an async context manager yielding an object
with the interface of `ldn.wlan.Factory`; `pokeldn/ldn/esp32_wlan.py` is the board's implementation
and the reference for one that has no kernel interface. With any `POKELDN_RADIO` set, launchers skip
the Linux `iw` and interface steps.

In the app, Settings, Plugins, Radio picks the board or a plugin's radio. A plugin radio runs with
`POKELDN_RADIO=scheme:` and an empty argument; the plugin keeps its own configuration. From the
command line:

```bash
POKELDN_PLUGINS=~/my-plugin POKELDN_RADIO=myradio:ARG ./.venv/bin/python -m pokeldn sv-host
```

## Compatibility

`pokeldn.plugins` with the names in the API table is the supported surface; anything else a plugin
imports from pokeldn can change in any release. A change to the API table raises `API_VERSION`, and
a plugin written for another version is refused with a message.
