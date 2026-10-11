"""The Pokemon the app keeps between games: each record in the bank folder with a `.json` beside it
[docs/gui.md, The bank]. A trade's received Pokemon is deposited on its own; one queued for a trade
carries {"bank": id} in the offer queue and leaves the bank when that trade completes."""
import base64
import hashlib
import json
import os
import random
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from pokeldn.app.paths import BANK, IMPORT
from pokeldn.pokemon import EXTENSIONS

FILES = re.compile(r"\.(pk3|pb7|pk8|pb8|pa8|pk9|pa9)$", re.IGNORECASE)
IMPORT_EXTENSIONS = frozenset({
    "pk1", "pk2", "pk3", "pk4", "pk5", "pk6", "pk7", "pk8", "pk9",
    "sk2", "ck3", "xk3", "bk4", "rk4", "pb7", "pb8", "pa8", "pa9",
})
GAME_OF = {extension: game for game, extension in EXTENSIONS.items()}
_deposit_lock = threading.Lock()


@dataclass(frozen=True)
class Entry:
    id: str               # the record's file name without its extension
    path: str
    game: str             # the catalog key of the game it is in now
    species_id: int
    shiny: bool
    summary: str          # pokeldn.pokemon.summary
    legal: bool
    tracker: int          # the HOME tracker a move to another game gives it, never 0
    created: float
    origin: str           # the Received file it came from, "" when unknown

    @property
    def when(self) -> str:
        return time.strftime("%d %b %Y, %H:%M", time.localtime(self.created))


def library() -> Path:
    """The folder; created by the first deposit, never by a listing."""
    return BANK


def inbox() -> Path:
    """The folder scanned for external Pokemon records and game saves."""
    return IMPORT


def _meta_path(path) -> Path:
    return Path(path).with_suffix(".json")


def _read_meta(path) -> dict:
    try:
        meta = json.loads(_meta_path(path).read_text(encoding="utf-8"))
        return meta if isinstance(meta, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_meta(path, meta: dict) -> None:
    target = _meta_path(path)
    tmp = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    try:
        tmp.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _digests(folder=None) -> set[str]:
    """Hashes whose metadata still has its matching Bank record."""
    folder = Path(folder or BANK)
    if not folder.is_dir():
        return set()
    found = set()
    for meta_path in folder.glob("*.json"):
        meta = _read_meta(meta_path)
        extension = EXTENSIONS.get(str(meta.get("game", "")))
        if meta.get("sha256") and extension and meta_path.with_suffix(f".{extension}").is_file():
            found.add(str(meta["sha256"]))
    return found


def _source_digests(folder=None) -> set[str]:
    """Imported file hashes, including sources changed by conversion or cleanup."""
    folder = Path(folder or BANK)
    if not folder.is_dir():
        return set()
    return {str(meta["source_sha256"]) for path in folder.glob("*.json")
            if (meta := _read_meta(path)).get("source_sha256")}


def _save_source_locations(folder=None) -> set[tuple[str, str]]:
    """Save hash and stable slot pairs already imported."""
    folder = Path(folder or BANK)
    if not folder.is_dir():
        return set()
    return {
        (str(meta["source_save_sha256"]), str(meta["source_slot"]))
        for path in folder.glob("*.json")
        if (meta := _read_meta(path)).get("source_save_sha256") and meta.get("source_slot")
    }


def _entry(path: Path) -> Entry | None:
    game = GAME_OF.get(path.suffix[1:].lower())
    meta = _read_meta(path)
    if game is None or not meta:
        return None
    try:
        tracker = int(meta.get("tracker", "0"))
    except ValueError:
        tracker = 0
    return Entry(path.stem, str(path), game, int(meta.get("species_id") or 0), bool(meta.get("shiny")),
                 str(meta.get("summary", "")), meta.get("legal") is not False, tracker,
                 float(meta.get("created") or 0), str(meta.get("origin", "")))


def entries(folder=None) -> list[Entry]:
    """Every banked Pokemon, newest first."""
    folder = Path(folder or BANK)
    if not folder.is_dir():
        return []
    found = [e for path in folder.iterdir() if FILES.search(path.name) and (e := _entry(path))]
    return sorted(found, key=lambda e: (e.created, e.id), reverse=True)


def find(entry_id: str, folder=None) -> Entry | None:
    return next((e for e in entries(folder) if e.id == entry_id), None)


def data(entry: Entry) -> bytes:
    return Path(entry.path).read_bytes()


def deposit(game: str, source: str, info: dict, folder=None) -> Entry | None:
    """Keep a copy of the record at `source`, which PKHeX read as `info`. None when the bank already holds
    these bytes: a received file is read again while it grows, and on every later scan."""
    content = Path(source).read_bytes()
    return deposit_bytes(game, content, info, folder=folder, origin=str(source))


def deposit_bytes(game: str, content: bytes, info: dict, *, folder=None, origin: str = "",
                  metadata: dict | None = None, allow_duplicate: bool = False) -> Entry | None:
    """Atomically add one native record and its metadata; return None for an exact duplicate."""
    if game not in EXTENSIONS:
        raise ValueError(f"unknown game {game}")
    folder = Path(folder or BANK)
    content = bytes(content)
    digest = _digest(content)
    from pokeldn.pokemon import summary
    reserved = {"game", "species", "species_id", "shiny", "summary", "legal", "tracker", "created",
                "origin", "sha256"}
    extra = {key: value for key, value in (metadata or {}).items() if key not in reserved}
    with _deposit_lock:
        if not allow_duplicate and digest in _digests(folder):
            return None
        folder.mkdir(parents=True, exist_ok=True)
        name = re.sub(r"[^A-Za-z0-9]+", "", str(info.get("species", ""))) or "pokemon"
        while True:
            stem = f"{name}-{time.strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:12]}"
            path = folder / f"{stem}.{EXTENSIONS[game]}"
            if not path.exists() and not _meta_path(path).exists():
                break
        meta = {
            "game": game, "species": info.get("species", ""), "species_id": int(info.get("species_id") or 0),
            "shiny": bool(info.get("shiny")), "summary": summary(info), "legal": bool(info.get("legal")),
            # HOME gives each Pokemon a tracker when it enters; a string, since JSON readers lose 64-bit precision.
            "tracker": str(random.randrange(1, 1 << 63)), "created": time.time(),
            "origin": str(origin), "sha256": digest, **extra,
        }
        data_tmp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        meta_target = _meta_path(path)
        meta_tmp = meta_target.with_name(f".{meta_target.name}.{uuid4().hex}.tmp")
        committed_data = False
        try:
            data_tmp.write_bytes(content)
            meta_tmp.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            os.replace(data_tmp, path)
            committed_data = True
            os.replace(meta_tmp, meta_target)
        except Exception:
            if committed_data:
                path.unlink(missing_ok=True)
            raise
        finally:
            data_tmp.unlink(missing_ok=True)
            meta_tmp.unlink(missing_ok=True)
        return _entry(path)


def _imported_record(info: dict) -> tuple[str, bytes]:
    if not info.get("legal"):
        from pokeldn.pokemon import BuilderError
        raise BuilderError(str(info.get("problems") or info.get("report") or
                               "PKHeX finds this Pokemon not legal."))
    return str(info["game"]), base64.b64decode(info["data"], validate=True)


def scan_import_folder(trainers: dict[str, dict], *, service=None, progress=None) -> dict:
    """Import Pokemon files and every occupied slot in game saves below the Import folder."""
    from pokeldn import pokemon

    IMPORT.mkdir(parents=True, exist_ok=True)
    all_files = sorted((path for path in IMPORT.rglob("*") if path.is_file()), key=lambda path: str(path).lower())

    def candidate(path: Path) -> bool:
        if path.suffix[1:].lower() in IMPORT_EXTENSIONS:
            return True
        try:
            return 32 * 1024 <= path.stat().st_size <= 64 * 1024 * 1024
        except OSError:
            return False

    files = [path for path in all_files if candidate(path)]
    result = {"found": len(files), "imported": 0, "duplicates": 0, "skipped": 0, "failed": 0,
              "cleaned": 0, "ignored": len(all_files) - len(files), "issues": []}
    known_sources = _source_digests()
    known_save_slots = _save_source_locations()
    helper = service or pokemon.SERVICE
    for done, path in enumerate(files, 1):
        relative = str(path.relative_to(IMPORT))
        try:
            source = path.read_bytes()
            source_digest = _digest(source)
            extension = path.suffix[1:].lower()
            if extension in IMPORT_EXTENSIONS:
                if source_digest in known_sources:
                    result["duplicates"] += 1
                else:
                    info = helper.import_bytes(source, path.suffix, trainers)
                    game, content = _imported_record(info)
                    added = deposit_bytes(
                        game, content, info, origin=str(path),
                        metadata={"source_kind": "import-file", "source_file": relative,
                                  "source_extension": extension, "source_sha256": source_digest,
                                  "source_format": str(info.get("source_format", "")),
                                  "source_legal": bool(info.get("source_legal", True)),
                                  "converted": bool(info.get("converted")),
                                  "automatic_cleanup": list(info.get("cleanup") or [])},
                    )
                    if added is None:
                        result["duplicates"] += 1
                    else:
                        result["imported"] += 1
                        result["cleaned"] += int(bool(info.get("cleaned")))
                        known_sources.add(source_digest)
            else:
                save = helper.import_save(source, path.name, trainers)
                for mon in save.get("pokemon", []):
                    location = str(mon.get("location", "Unknown save slot"))
                    slot = f"{mon.get('container', '')}:{mon.get('box', -1)}:{mon.get('slot', -1)}"
                    source_slot = source_digest, slot
                    if source_slot in known_save_slots:
                        result["duplicates"] += 1
                        continue
                    if not mon.get("readable", True) or mon.get("error") or not mon.get("legal"):
                        result["skipped"] += 1
                        reason = str(mon.get("error") or mon.get("problems") or mon.get("report") or
                                     "PKHeX finds this Pokemon not legal.").splitlines()[0]
                        result["issues"].append({"file": relative, "location": location, "reason": reason})
                        continue
                    game, content = _imported_record(mon)
                    deposit_bytes(
                        game, content, mon, origin=str(path), allow_duplicate=True,
                        metadata={"source_kind": "save-file", "source_file": relative,
                                  "source_save_sha256": source_digest, "source_location": location,
                                  "source_slot": slot, "source_format": str(mon.get("source_format", "")),
                                  "source_legal": bool(mon.get("source_legal", True)),
                                  "save_format": str(save.get("format", "")),
                                  "save_version": str(save.get("version", "")),
                                  "save_trainer": str(save.get("name", "")),
                                  "converted": bool(mon.get("converted")),
                                  "automatic_cleanup": list(mon.get("cleanup") or []),
                                  "egg": bool(mon.get("egg"))},
                    )
                    result["imported"] += 1
                    result["cleaned"] += int(bool(mon.get("cleaned")))
                    known_save_slots.add(source_slot)
        except (OSError, ValueError, KeyError, pokemon.BuilderError) as error:
            if "does not recognize this as a supported game save" in str(error):
                result["found"] -= 1
                result["ignored"] += 1
            else:
                result["skipped"] += 1
                result["issues"].append({"file": relative, "reason": str(error).splitlines()[0]})
        except Exception as error:
            result["failed"] += 1
            result["issues"].append({"file": relative, "reason": str(error)})
        if progress:
            progress(done, len(files))
    return result


def edit(entry: Entry, fields: dict) -> Entry:
    """Change what a player could change in the game (nickname, level, moves, held item) and keep the result,
    or BuilderError with the reason. A legal Pokemon stays legal: an edit PKHeX rejects is refused."""
    from pokeldn.pokemon import SERVICE, BuilderError, summary
    reply = SERVICE.check_bytes(entry.game, data(entry), fields=fields)
    if entry.legal and not reply["legal"]:
        raise BuilderError(reply["problems"])
    content = base64.b64decode(reply["data"])
    path = Path(entry.path)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(content)
    os.replace(tmp, path)
    meta = _read_meta(path)
    meta.update({"species": reply["species"], "species_id": int(reply["species_id"]), "shiny": bool(reply["shiny"]),
                 "summary": summary(reply), "legal": bool(reply["legal"]), "sha256": _digest(content),
                 "edited": time.time()})
    _write_meta(path, meta)
    return _entry(path)


def remove(entry_id: str, folder=None) -> None:
    folder = Path(folder or BANK)
    for path in folder.glob(f"{entry_id}.*") if folder.is_dir() else ():
        if FILES.search(path.name) or path.suffix == ".json":
            path.unlink(missing_ok=True)


# The offer queues

def offer(entry: Entry, game: str, trainer: dict) -> dict:
    """The queue item that trades this banked Pokemon into `game`: moved there by PKHeX's HOME conversion
    and legal there, or BuilderError with the reason. `trainer` is the bank's owner, who handles it."""
    from pokeldn.pokemon import SERVICE, summary
    reply = SERVICE.move(entry.game, game, data(entry), entry.tracker, trainer)
    return {"file": SERVICE.keep(game, reply), "summary": summary(reply), "species": reply["species_id"],
            "shiny": reply["shiny"], "legal": reply["legal"], "encounter": reply["encounter"],
            "moves": reply["moves"], "report": "", "bank": entry.id}


def queued(settings, entry_id: str) -> list[str]:
    """The tool keys whose offer queue holds this banked Pokemon."""
    return [tool for tool, stored in settings.tool_values.items()
            for value in stored.get("values", {}).values() if isinstance(value, list)
            if any(isinstance(v, dict) and v.get("bank") == entry_id for v in value)]


def enqueue(settings, tool, field, item: dict) -> str:
    """Append a moved Pokemon to a tool's queue; why it cannot be, or ""."""
    from pokeldn.app.command import offers
    stored = settings.tool_values.setdefault(tool.key, {"values": {}, "extra": {}})
    queue = [v for v in offers(stored["values"].get(field.key, field.default)) if v.get("file")]
    if len(queue) >= field.queue:
        return f"{tool.name} already has {field.queue} Pokemon queued."
    stored["values"][field.key] = queue + [item]
    settings.save()
    return ""


def dequeue(settings, entry_id: str) -> None:
    """Take a banked Pokemon out of every queue; it stays in the bank."""
    _drop(settings, lambda v: v.get("bank") == entry_id)


def prune(settings) -> None:
    """Drop queued Pokemon whose bank record is gone: traded away, or removed from the folder."""
    if not BANK.is_dir():     # an unplugged or unreadable folder says nothing about what was traded
        return
    held = {e.id for e in entries()}
    _drop(settings, lambda v: bool(v.get("bank")) and v["bank"] not in held)


def _drop(settings, gone) -> None:
    changed = False
    for stored in settings.tool_values.values():
        for key, value in stored.get("values", {}).items():
            if isinstance(value, list) and any(isinstance(v, dict) and gone(v) for v in value):
                stored["values"][key] = [v for v in value if not (isinstance(v, dict) and gone(v))]
                changed = True
    if changed:
        settings.save()
