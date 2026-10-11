"""Installing, updating and removing `.pokeplugin` packages in the data folder's plugins/.

A package is a zip holding plugin.toml at its root or inside one top folder, beside the plugin's
module and files (docs/plugins.md, Packages). Nothing in a package runs before it is installed and
turned on.
"""
import json
import os
import re
import shutil
import stat
import time
import tomllib
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from pokeldn import plugins

EXTENSION = "pokeplugin"
MAX_FILES = 2000
MAX_BYTES = 64 << 20
ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
CONSENT = ".installed.json"     # written when the user accepted the risks for this plugin
SKIP = ("__pycache__", ".DS_Store", CONSENT)


class PackageError(Exception):
    """A file that is not an installable plugin; the message is shown to the user as it is."""


@dataclass
class Package:
    id: str
    name: str
    version: str
    api: tuple | None
    author: str = ""
    description: str = ""
    homepage: str = ""
    files: int = 0
    size: int = 0
    icon: bytes = b""
    source: str = ""
    prefix: str = ""                 # the top folder the files sit in, or ""
    members: list = field(default_factory=list)


def _version(text: str) -> tuple:
    return tuple(int(n) for n in re.findall(r"\d+", text)[:4])


def compare(package: Package, installed: plugins.Plugin | None) -> str:
    """install, update, reinstall or downgrade."""
    if installed is None:
        return "install"
    new, old = _version(package.version), _version(installed.version)
    return "update" if new > old else "downgrade" if new < old else "reinstall"


def read(path: str) -> Package:
    """Reads and checks a package without extracting it."""
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as error:
        raise PackageError(f"{os.path.basename(path)} is not a plugin package ({error}).") from None
    with archive:
        infos = [i for i in archive.infolist() if not i.is_dir()]
        if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_BYTES:
            raise PackageError("The package is too large to be a plugin.")
        names = [i.filename for i in infos]
        for info in infos:
            parts = PurePosixPath(info.filename).parts
            if info.filename.startswith(("/", "\\")) or ".." in parts or ":" in info.filename \
                    or stat.S_ISLNK(info.external_attr >> 16):
                raise PackageError(f"The package holds an unsafe path: {info.filename}")
        tomls = [n for n in names if PurePosixPath(n).name == "plugin.toml" and len(PurePosixPath(n).parts) <= 2]
        if len(tomls) != 1:
            raise PackageError("The package has no plugin.toml at its top." if not tomls else
                               "The package holds several plugins; install them one by one.")
        prefix = str(PurePosixPath(tomls[0]).parent)
        prefix = "" if prefix == "." else prefix + "/"
        if any(not n.startswith(prefix) for n in names):
            raise PackageError("plugin.toml must sit at the top of the package, beside the plugin's files.")
        try:
            meta = tomllib.loads(archive.read(tomls[0]).decode("utf-8"))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
            raise PackageError(f"plugin.toml does not parse: {error}") from None
        plugin_id = str(meta.get("id", ""))
        if not ID.fullmatch(plugin_id):
            raise PackageError("plugin.toml needs an id of lowercase letters, digits, dots, dashes or underscores.")
        api = plugins.parse_api(meta.get("api"))
        state, message = plugins.compatibility(api)
        if state in ("newer", "older"):
            raise PackageError(message)
        module = str(meta.get("module", "plugin"))
        if f"{prefix}{module}.py" not in names:
            raise PackageError(f"The package has no {module}.py next to plugin.toml.")
        icon_name = f"{prefix}{meta.get('icon', 'icon.png')}"
        icon = archive.read(icon_name) if icon_name in names else b""
        return Package(plugin_id, str(meta.get("name", plugin_id)), str(meta.get("version", "")), api,
                       str(meta.get("author", "")), str(meta.get("description", "")),
                       str(meta.get("homepage", "")), len(infos), sum(i.file_size for i in infos), icon,
                       os.path.abspath(path), prefix, names)


def installed(plugin_id: str) -> plugins.Plugin | None:
    folder = plugins.folder() / plugin_id
    return plugins._read_folder(folder) if (folder / "plugin.toml").is_file() else None


def consented(plugin: plugins.Plugin) -> bool:
    """True once the user accepted the risks for this plugin in the app."""
    return plugin.folder is not None and (plugin.folder / CONSENT).is_file()


def accept(plugin: plugins.Plugin) -> None:
    """Records the user's acceptance for a plugin that came in by hand, not through install."""
    (plugin.folder / CONSENT).write_text(json.dumps({"accepted": time.strftime("%Y-%m-%d %H:%M"),
                                                     "source": "folder"}), encoding="utf-8")


def install(package: Package) -> Path:
    """Extracts the package as plugins/<id>, replacing an installed copy only once the new one is
    whole. The caller has shown the risks and the user accepted them."""
    root = plugins.folder()
    root.mkdir(parents=True, exist_ok=True)
    target = root / package.id
    staging = root / f".staging-{package.id}"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir()
    try:
        with zipfile.ZipFile(package.source) as archive:
            for name in package.members:
                relative = name[len(package.prefix):]
                if not relative or any(part in SKIP for part in PurePosixPath(relative).parts):
                    continue
                out = staging / relative
                out.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as src, open(out, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        (staging / CONSENT).write_text(json.dumps({"accepted": time.strftime("%Y-%m-%d %H:%M"),
                                                   "source": os.path.basename(package.source),
                                                   "version": package.version}), encoding="utf-8")
        old = root / f".old-{package.id}"
        shutil.rmtree(old, ignore_errors=True)
        if target.exists():
            os.replace(target, old)
        os.replace(staging, target)
        shutil.rmtree(old, ignore_errors=True)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return target


def remove(plugin_id: str, data: bool = False) -> None:
    """Deletes plugins/<id>, and with `data` what it kept; a plugin elsewhere (POKELDN_PLUGINS, a
    package) is not the app's to delete."""
    root = plugins.folder().resolve()
    target = (root / plugin_id).resolve()
    if target.parent != root or not (target / "plugin.toml").is_file():
        raise PackageError("Only a plugin installed in the app can be removed here.")
    shutil.rmtree(target)
    if data and ID.fullmatch(plugin_id):
        shutil.rmtree(plugins.data_folder(plugin_id), ignore_errors=True)


def kept_data(plugin_id: str) -> int:
    """The bytes a plugin keeps in its data folder."""
    folder = plugins.data_folder(plugin_id)
    return sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()) if folder.is_dir() else 0


def pack(folder: str, out: str) -> Package:
    """Writes a folder holding plugin.toml as a package, then reads it back as the app would."""
    source = Path(folder)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source)
            if path.is_file() and not any(part in SKIP for part in relative.parts):
                archive.write(path, relative.as_posix())
    return read(out)


def size_text(size: int) -> str:
    return f"{size} B" if size < 1024 else f"{size / 1024:.0f} KB" if size < 1 << 20 else f"{size / (1 << 20):.1f} MB"
