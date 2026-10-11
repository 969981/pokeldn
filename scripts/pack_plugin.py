"""Packs a plugin folder into a .pokeplugin the app installs, and checks it as the app would.

    python scripts/pack_plugin.py my-plugin [-o my-plugin-1.0.0.pokeplugin]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pokeldn.app import plugin_store  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", help="the folder holding plugin.toml")
    parser.add_argument("-o", "--output", help="the package to write; default <id>-<version>.pokeplugin")
    args = parser.parse_args(argv)
    if not os.path.isfile(os.path.join(args.folder, "plugin.toml")):
        parser.exit(1, f"{args.folder} has no plugin.toml\n")
    out = args.output or os.path.join(os.getcwd(), "plugin.pokeplugin")
    try:
        package = plugin_store.pack(args.folder, out)
    except plugin_store.PackageError as error:
        os.remove(out)
        parser.exit(1, f"Not installable: {error}\n")
    if not args.output:
        named = f"{package.id}-{package.version or '0'}.{plugin_store.EXTENSION}"
        os.replace(out, named)
        out = named
    print(f"{out}: {package.name} {package.version}, {package.files} files, {plugin_store.size_text(package.size)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
