"""Cached, game-scoped competitive sets for the shared Pokemon offer picker.

The data is fetched from pkmn's processed Smogon set API. Set text remains attributed to its
source and is never treated as proof that the corresponding in-game Pokemon is legal: callers must
run every candidate through the PKHeX paste and make services.
"""
from __future__ import annotations

import itertools
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

import certifi

from pokeldn import __version__
from pokeldn.app.paths import DATA

SOURCE = "Smogon sets via pkmn.cc"
SOURCE_URL = "https://pkmn.github.io/smogon/data/sets/"
CACHE = DATA / "cache" / "meta"
CACHE_SECONDS = 24 * 60 * 60
MAX_BYTES = 2 * 1024 * 1024
MAX_VARIANTS = 256

# Only formats present in the provider's public /sets/index.json are listed. In particular, there
# is no Legends Z-A format there; keeping the key with no formats gives the GUI a precise message.
FORMATS = {
    "frlg": (("gen3ou", "Gen 3 OU"), ("gen3uu", "Gen 3 UU"), ("gen3ubers", "Gen 3 Ubers")),
    "bdsp": (("gen8bdspou", "BDSP OU"),),
    "za": (),
}


class MetaError(Exception):
    pass


def formats(game: str) -> tuple[tuple[str, str], ...]:
    return FORMATS.get(game, ())


def unavailable(game: str) -> str:
    if game == "za":
        return ("No verified public Smogon/Showdown set source currently lists a Legends Z-A format. "
                "Sets from another game are not offered as Z-A meta.")
    return "Browse Meta is not available for this game."


def _download(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": f"pokeldn/{__version__} Browse Meta"})
    context = __import__("ssl").create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        length = response.headers.get("Content-Length")
        if length and int(length) > MAX_BYTES:
            raise MetaError("The set source is larger than expected.")
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise MetaError("The set source is larger than expected.")
    return data


def _read(data: bytes, format_id: str) -> dict:
    try:
        parsed = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MetaError(f"{format_id} returned invalid set data.") from exc
    if not isinstance(parsed, dict) or any(not isinstance(v, dict) for v in parsed.values()):
        raise MetaError(f"{format_id} returned an unexpected set format.")
    return parsed


def load_format(format_id: str, *, cache: Path = CACHE, timeout: float = 12,
                now: float | None = None, fetch=None) -> tuple[dict, bool]:
    """Return (sets, used_stale_cache).

    A fresh cache avoids the network; a stale valid cache is used only when refresh fails.
    """
    allowed = {key for rows in FORMATS.values() for key, _ in rows}
    if format_id not in allowed:
        raise MetaError("Unknown or unsupported meta format.")
    now = time.time() if now is None else now
    path = cache / f"{format_id}.json"
    try:
        if now - path.stat().st_mtime < CACHE_SECONDS:
            return _read(path.read_bytes(), format_id), False
    except OSError:
        pass
    try:
        data = (fetch or _download)(f"{SOURCE_URL}{format_id}.json", timeout)
        parsed = _read(data, format_id)
        cache.mkdir(parents=True, exist_ok=True)
        temporary = cache / f".{format_id}-{os.getpid()}-{uuid4().hex}.tmp"
        temporary.write_bytes(data)
        temporary.replace(path)
        return parsed, False
    except Exception as exc:
        try:
            return _read(path.read_bytes(), format_id), True
        except OSError:
            if isinstance(exc, MetaError):
                raise
            if isinstance(exc, urllib.error.HTTPError):
                detail = f"HTTP {exc.code}"
            elif isinstance(exc, urllib.error.URLError):
                detail = str(exc.reason)
            else:
                detail = str(exc)
            raise MetaError(
                f"Could not load {format_id}: {detail or 'network error'}. No cached copy is available."
            ) from exc


def load(game: str, **kwargs) -> tuple[list[dict], bool]:
    """Return all configured builds for a game and whether any stale cache was used."""
    configured = formats(game)
    if not configured:
        raise MetaError(unavailable(game))
    builds, stale = [], False
    for format_id, label in configured:
        data, old = load_format(format_id, **kwargs)
        stale |= old
        for species, sets in data.items():
            if not isinstance(species, str) or not isinstance(sets, dict):
                continue
            for role, values in sets.items():
                if isinstance(role, str) and isinstance(values, dict):
                    builds.append({"species": species, "role": role, "format_id": format_id,
                                   "format": label, "source": SOURCE, "source_url": SOURCE_URL,
                                   "set": values})
    builds.sort(key=lambda build: (build["species"].casefold(), build["format"],
                                   build["role"].casefold()))
    return builds, stale


def _choices(value):
    return value if isinstance(value, list) else [value]


def alternatives(build: dict, limit: int = MAX_VARIANTS):
    """Yield resolved variants in source order.

    Slash choices become explicit candidates so PKHeX can select the first legal one without
    silently discarding source fields.
    """
    raw = build["set"]
    fields = ("item", "ability", "nature", "evs", "ivs", "gender", "level", "shiny", "happiness")
    fixed = [(key, _choices(raw[key])) for key in fields if key in raw]
    move_slots = [_choices(move) for move in raw.get("moves", [])]
    keys = [key for key, _ in fixed]
    pools = [values for _, values in fixed] + move_slots
    if not pools:
        yield {}, []
        return
    for n, picked in enumerate(itertools.product(*pools)):
        if n >= limit:
            return
        resolved = dict(zip(keys, picked[:len(keys)]))
        resolved["moves"] = list(picked[len(keys):])
        notes = []
        for key, values in fixed:
            if len(values) > 1:
                notes.append(f"{key}: {resolved[key]}")
        for slot, values in enumerate(move_slots):
            if len(values) > 1:
                notes.append(f"move {slot + 1}: {resolved['moves'][slot]}")
        yield resolved, notes


STAT_NAMES = (("hp", "HP"), ("atk", "Atk"), ("def", "Def"),
              ("spa", "SpA"), ("spd", "SpD"), ("spe", "Spe"))


def _stats(label: str, values: dict) -> str:
    return f"{label}: " + " / ".join(f"{values[key]} {name}" for key, name in STAT_NAMES if key in values)


def showdown(build: dict, resolved: dict) -> str:
    """Return a resolved provider set in the existing PKHeX parser's Showdown format."""
    first = build["species"] + (f" @ {resolved['item']}" if resolved.get("item") else "")
    lines = [first]
    if resolved.get("ability"):
        lines.append(f"Ability: {resolved['ability']}")
    if resolved.get("level"):
        lines.append(f"Level: {resolved['level']}")
    if resolved.get("gender"):
        lines.append(f"Gender: {resolved['gender']}")
    if resolved.get("shiny"):
        lines.append("Shiny: Yes")
    if "happiness" in resolved:
        lines.append(f"Happiness: {resolved['happiness']}")
    if isinstance(resolved.get("evs"), dict) and resolved["evs"]:
        lines.append(_stats("EVs", resolved["evs"]))
    if resolved.get("nature"):
        lines.append(f"{resolved['nature']} Nature")
    if isinstance(resolved.get("ivs"), dict) and resolved["ivs"]:
        lines.append(_stats("IVs", resolved["ivs"]))
    lines += [f"- {move}" for move in resolved.get("moves", []) if isinstance(move, str)]
    return "\n".join(lines) + "\n"


def preview(build: dict) -> list[tuple[str, str]]:
    """Return human-readable source values while keeping alternatives visible with slashes."""
    raw = build["set"]

    def shown(value):
        if isinstance(value, list):
            return " / ".join(shown(item) for item in value)
        if isinstance(value, dict):
            return ", ".join(f"{key.upper()} {item}" for key, item in value.items())
        return str(value)

    rows = []
    for key, label in (("nature", "Nature"), ("ability", "Ability"), ("item", "Item"),
                       ("moves", "Moves"), ("evs", "EVs"), ("ivs", "IVs")):
        if key in raw:
            rows.append((label, shown(raw[key])))
    return rows


def build_legal(service, game: str, build: dict, trainer: dict,
                version: str = "") -> tuple[dict, dict, list[str]]:
    """Resolve alternatives through the paste and make path; return the first legal build."""
    problems = []
    for resolved, choices in alternatives(build):
        try:
            found, = service.paste(game, showdown(build, resolved), trainer, version)
            if found["errors"]:
                raise MetaError(" ".join(found["errors"]))
            info = service.make(game, found["species_id"], trainer, found["level"], found["shiny"],
                                found["nickname"], version, found["options"])
            if not info.get("legal"):
                raise MetaError(info.get("report", "PKHeX did not mark the build legal."))
            return found, info, choices
        except Exception as exc:
            message = str(exc)
            if message and message not in problems:
                problems.append(message)
    detail = " ".join(problems[:3]) or "No source alternative could be built legally."
    raise MetaError(f"This meta build is not legal for {game.upper()}: {detail}")
