"""The Plugins page: add a .pokeplugin, turn plugins on and off, update and remove them, pick a radio.
Every install shows the risks and waits for the user's acceptance (docs/plugins.md)."""
import os
import shutil
import threading
from pathlib import Path

import flet as ft

from gui import drop
from gui import theme as t
from gui.views.widgets import open_folder
from pokeldn import plugins
from pokeldn.app import plugin_store as store
from pokeldn.app.paths import SESSION

ACTIONS = {"install": "Install", "update": "Update", "reinstall": "Reinstall", "downgrade": "Install older version"}
RISKS = (
    "It runs as a program on this computer, with your account's access to every file, your prod.keys included.",
    "It can use the network, your board and the sessions you start.",
    "pokeldn's guardrails stop a plugin deleting or overwriting your files and running erase commands, "
    "but a plugin written to get around them can.",
    "pokeldn does not review or support plugins, and cannot undo what one does.",
)


def plugin_icon(source: str | bytes = "", size: int = 48) -> ft.Control:
    """The plugin's own image, or the blocks mark on the brand gradient."""
    if isinstance(source, str) and source:
        try:
            source = Path(source).read_bytes()
        except OSError:
            source = b""
    if source:
        image = ft.Image(src=source, width=size, height=size, fit=ft.BoxFit.CONTAIN,
                         filter_quality=ft.FilterQuality.NONE)
        return ft.Container(image, width=size, height=size, border_radius=size * 0.22,
                            clip_behavior=ft.ClipBehavior.ANTI_ALIAS)
    return ft.Container(t.tinted(t.pixel_icon("blocks", size=24 if size < 48 else 48), t.BRAND_BLUE),
                        width=size, height=size, border_radius=size * 0.22, alignment=ft.Alignment.CENTER,
                        bgcolor=ft.Colors.with_opacity(0.08, "#FFFFFF"))


def checkbox(label: str, value: bool, on_change) -> ft.Container:
    """A whole-row tick box in the app's pixel style."""
    state = {"on": value}
    mark = t.pixel_icon("checkbox-on" if value else "checkbox", color=t.BLUE if value else t.MUTED)

    def toggle(e):
        state["on"] = not state["on"]
        mark.src = f"icons/{'checkbox-on' if state['on'] else 'checkbox'}.svg"
        mark.color = t.BLUE if state["on"] else t.MUTED
        mark.update()
        on_change(state["on"])

    return ft.Container(ft.Row([mark, t.text(label, 13, expand=True)], spacing=10,
                               vertical_alignment=ft.CrossAxisAlignment.START),
                        padding=ft.Padding(10, 10, 10, 10), border_radius=10, on_click=toggle,
                        bgcolor=ft.Colors.with_opacity(0.04, "#FFFFFF"))


class PluginsView:
    def __init__(self, app):
        self.app = app
        self.notice = ft.Container()
        self.column = ft.Column(spacing=t.GAP, width=760)
        self.zone = ft.Container()
        self.scroll = ft.ListView([ft.Row([self.column], alignment=ft.MainAxisAlignment.CENTER)],
                                  padding=ft.Padding(4, 8, 4, 24), expand=True)
        self.control = drop.target(ft.Container(t.fade(self.scroll), expand=True), self._dropped,
                                   glow=lambda: self.zone)
        self.downloading = ""      # the plugin whose update is downloading
        app.plugin_update_listeners.append(lambda: self.render(update=self.column.page is not None))
        self.render()

    def enter(self, **_) -> None:
        self.render()

    def leave(self) -> None:
        self.notice.content = None

    # Rendering

    def render(self, update: bool = False) -> None:
        found = plugins.discover()
        loaded = {p.id: p for p in plugins.load()}
        rows = [self._row(p, loaded.get(p.id)) for p in found]
        header = ft.Container(ft.Row([
            t.pixel_icon("plug", size=24, color=t.RED),
            t.text("Plugins", 22, weight=ft.FontWeight.W_600, expand=True),
            t.secondary_button("How to make one", lambda e: self.app.navigate("docs", doc="plugins.md"),
                               "book-open"),
            t.button("Add a plugin", self._pick, "plus"),
        ], spacing=10), padding=ft.Padding(4, 12, 0, 0))
        self.zone = self._zone(compact=bool(rows))
        installed = t.section(
            f"Installed · {len(rows)}" if rows else "Installed",
            ft.Column([*rows, t.text(f"This pokeldn runs plugin API {plugins.API_VERSION}.{plugins.API_LEVEL}.",
                                     12, t.FAINT)], spacing=8) if rows else None,
            trailing=ft.Row([
                t.icon_button("refresh", self._refresh, "Look for changes and updates"),
                t.icon_button("folder", self._open_folder, "Open the plugins folder"),
            ], spacing=0))
        self.column.controls = [header, self.notice, self.zone, *([installed] if rows else []),
                                *self._radio_card()]
        if update:
            self.column.update()

    def _zone(self, compact: bool) -> ft.Container:
        title = ("Drop a .pokeplugin file here" if drop.AVAILABLE else "Add a .pokeplugin file")
        lead = t.tinted(t.pixel_icon("archive", size=24 if compact else 48), t.BRAND_BLUE)
        body = [t.text(title, 15 if not compact else 13, weight=ft.FontWeight.W_600),
                t.text("Plugins add tools and radios made by other people. You see what a plugin is and accept "
                       "its risks before anything is installed.", 12, t.MUTED,
                       text_align=None if compact else ft.TextAlign.CENTER)]
        choose = t.secondary_button("Choose a file", self._pick, "folder")
        if compact:
            content = ft.Row([lead, ft.Column(body, spacing=2, expand=True), choose], spacing=14)
            padding = ft.Padding(18, 14, 14, 14)
        else:
            content = ft.Column([lead, *body, ft.Container(height=4), choose], spacing=8,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            padding = ft.Padding(32, 36, 32, 32)
        return ft.Container(content, padding=padding, border_radius=16, bgcolor=t.CARD,
                            border=ft.Border.all(1.5, ft.Colors.with_opacity(0.12, "#FFFFFF")),
                            on_click=self._pick if not compact else None)

    def _row(self, plugin: plugins.Plugin, state: plugins.Plugin | None) -> ft.Control:
        s = self.app.settings
        local = plugin.folder is not None and plugin.folder.parent == plugins.folder()
        forced = plugins.named(plugin)
        on = state is not None
        meta = " · ".join(x for x in (f"Version {plugin.version}" if plugin.version else "",
                                      f"by {plugin.author}" if plugin.author else "",
                                      f"plugin API {plugins.api_text(plugin.api)}") if x)
        lines: list[ft.Control] = [
            ft.Row([t.text(plugin.name, 14, weight=ft.FontWeight.W_600), self._status(plugin, state)],
                   spacing=10, wrap=True),
        ]
        if meta:
            lines.append(t.text(meta, 12, t.FAINT))
        if plugin.description:
            lines.append(t.text(plugin.description, 12, t.MUTED))
        if state is not None and state.error:
            lines.append(ft.Container(t.text(state.error, 12, t.SOFT, selectable=True, font_family=t.MONO),
                                      padding=10, border_radius=8,
                                      bgcolor=ft.Colors.with_opacity(0.08, t.RED)))
        elif on:
            chips = self._adds(state)
            if chips:
                lines.append(ft.Row(chips, spacing=6, run_spacing=6, wrap=True))
        elif plugin.error:
            lines.append(t.badge(plugin.error, t.RED, "warning-diamond"))
        level, message = plugins.compatibility(plugin.api)
        if level == "deprecated":
            lines.append(t.badge(message, t.AMBER, "warning-diamond"))
        available = self.app.plugin_updates.get(plugin.id)
        if available is not None and local:
            busy = self.downloading == plugin.id
            lines.append(ft.Row([
                t.chip(f"Version {available.version} is out", "upload", t.GREEN),
                t.button("Downloading" if busy else f"Update to {available.version}",
                         lambda e, a=available, p=plugin: self._download(a, p), "download", color=t.GREEN,
                         disabled=bool(self.downloading)),
            ], spacing=8, wrap=True))
        if forced:
            lines.append(t.badge("Loaded from POKELDN_PLUGINS: it is on while that variable names it.", t.FAINT))
        elif plugin.entry_point is not None:
            lines.append(t.badge("Installed as a Python package.", t.FAINT))

        def item(label, icon, action, color=t.MUTED):
            return ft.PopupMenuItem(ft.Row([t.pixel_icon(icon, color=color), t.text(label, 13)], spacing=10),
                                    on_click=action, height=40)
        menu_items = []
        if on and state.loaded and (first := self._first_tool(state)):
            menu_items.append(item("Open its tools", "gamepad", lambda e, k=first: self._open_tool(*k)))
        if local:
            menu_items += [item("Update from a file", "upload", lambda e, p=plugin: self.app.page.run_task(
                self._pick_update, p)),
                           item("Show in folder", "folder", lambda e, p=plugin: open_folder(str(p.folder)))]
        if plugin.homepage:
            menu_items.append(item("Visit its page", "external-link",
                                   lambda e, u=plugin.homepage: self.app.page.run_task(self.app.open_url, u)))
        if local:
            menu_items.append(item("Remove", "trash", lambda e, p=plugin: self._confirm_remove(p), t.RED))
        menu = ft.PopupMenuButton(
            content=ft.Container(t.pixel_icon("more-vertical", color=t.MUTED), width=32, height=32,
                                 alignment=ft.Alignment.CENTER),
            tooltip="More", bgcolor=t.PANEL, menu_position=ft.PopupMenuPosition.UNDER,
            items=menu_items) if menu_items else ft.Container(width=32)
        toggle = t.switch(plugin.id in s.plugins or forced, lambda e, p=plugin: self._toggle(p, e.control.value))
        toggle.disabled = forced or bool(plugin.error) or \
            plugins.compatibility(plugin.api)[0] in ("newer", "older")
        toggle.tooltip = "Turn on" if not on else "Turn off"
        return t.surface(ft.Container(ft.Row([
            plugin_icon(plugin.icon),
            ft.Column(lines, spacing=4, expand=True),
            ft.Row([toggle, menu], spacing=2),
        ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.START), padding=ft.Padding(16, 14, 8, 14)))

    def _status(self, plugin: plugins.Plugin, state: plugins.Plugin | None) -> ft.Control:
        if plugins.compatibility(plugin.api)[0] in ("newer", "older"):
            return t.chip("Not compatible", "warning-diamond", t.RED)
        if plugin.error or (state is not None and state.error):
            return t.chip("Failed", "warning-diamond", t.RED)
        if state is not None:
            return t.chip("On", "check", t.GREEN)
        if plugin.folder is not None and plugin.folder.parent == plugins.folder() and not store.consented(plugin):
            return t.chip("Added by hand", "warning-diamond", t.AMBER)
        return t.chip("Off", None, t.FAINT)

    def _adds(self, state: plugins.Plugin) -> list[ft.Control]:
        names = {g.key: g.name for g in plugins.games()}
        chips = [t.chip(f"{g.name} · {len(g.tools)} tool{'s' * (len(g.tools) != 1)}", "gamepad", t.BLUE)
                 for g in state.games]
        chips += [t.chip(f"{tool.name} in {names.get(game, game)}", "arrows-horizontal", t.BLUE)
                  for game, tool in state.tools]
        chips += [t.chip(f"Radio: {plugins.radio(r).label}", "cpu", t.AMBER) for r in state.radios]
        return chips

    def _radio_card(self) -> list[ft.Control]:
        s = self.app.settings
        choices = [("", "The board (default)")] + [(r.scheme, r.label) for r in plugins.radios()]
        if s.radio and s.radio not in {c[0] for c in choices}:
            choices.append((s.radio, f"{s.radio} (its plugin is off)"))
        if len(choices) == 1:
            return []
        return [t.section("Radio", t.card(
            "What carries the wireless messages",
            t.dropdown(choices, s.radio, on_select=lambda e: self._set_radio(e.control.value or "")),
            "Keep the board unless a plugin's instructions say otherwise. The Games page shows the radio in "
            "use before you start."))]

    def _first_tool(self, state: plugins.Plugin):
        for game in state.games:
            if game.tools:
                return game.key, game.tools[0].key
        return (state.tools[0][0], state.tools[0][1].key) if state.tools else None

    # Actions

    def say(self, text: str, color: str = t.GREEN, icon: str = "check", action: tuple | None = None) -> None:
        row = [t.pixel_icon(icon, color=color), t.text(text, 13, expand=True)]
        if action:
            row.append(t.link_button(*action))
        row.append(t.icon_button("close", self._clear_notice, "Dismiss"))
        self.notice.content = ft.Container(ft.Row(row, spacing=10), padding=ft.Padding(14, 6, 6, 6),
                                           border_radius=12, bgcolor=ft.Colors.with_opacity(0.1, color))

    def _clear_notice(self, e=None) -> None:
        self.notice.content = None
        self.notice.update()

    def _reload(self, message: str = "") -> None:
        plugins.reload()
        s = self.app.settings
        if s.radio and plugins.radio(s.radio) is None:
            s.radio = ""
            s.save()
            message = (message + " " if message else "") + "The radio is back to the board."
        if message:
            self.say(message, t.MUTED, "refresh")
        self.render(update=True)

    def _refresh(self, e=None) -> None:
        self._reload("Plugins reloaded. Looking for updates.")
        self.app.check_plugin_updates()

    def _download(self, available, plugin: plugins.Plugin) -> None:
        from pokeldn.app import plugin_updates
        self.downloading = plugin.id
        self.render(update=True)

        def work():
            try:
                path, error = plugin_updates.download(available, SESSION / "plugin-download"), ""
            except OSError as failure:
                path, error = None, str(failure)
            self.app.ui(lambda: done(path, error))

        def done(path, error):
            self.downloading = ""
            self.render(update=True)
            if path is None:
                self.error_dialog(f"{plugin.name} {available.version} did not download", error)
            else:
                self.open_file(str(path), expected=plugin)

        threading.Thread(target=work, daemon=True).start()

    def _open_folder(self, e) -> None:
        plugins.folder().mkdir(parents=True, exist_ok=True)
        open_folder(str(plugins.folder()))

    def _open_tool(self, game: str, tool: str) -> None:
        self.app.navigate("games", game=game, tool=tool)

    def _set_radio(self, scheme: str) -> None:
        self.app.settings.radio = scheme
        self.app.settings.save()
        radio = plugins.radio(scheme)
        self.say(f"Sessions now use {radio.label}." if radio else "Sessions now use the board.", t.BLUE, "cpu")
        self.render(update=True)

    def _toggle(self, plugin: plugins.Plugin, value: bool) -> None:
        if value and plugin.folder is not None and not store.consented(plugin):
            try:
                package = store.describe(plugin)
            except (OSError, store.PackageError) as error:
                self.error_dialog(f"{plugin.name} cannot be turned on", str(error))
                self.render(update=True)
                return
            self.consent(package, "enable", plugin)
            self.render(update=True)     # the switch stays off until the user accepts
            return
        self._set_enabled(plugin.id, value)
        state = {p.id: p for p in plugins.load()}.get(plugin.id)
        if value and state is not None and state.error:
            self.say(f"{plugin.name} failed to load. Its error is on its card.", t.RED, "warning-diamond")
        elif value:
            self.say(f"{plugin.name} is on.", action=self._tools_action(plugin.id))
        else:
            self.say(f"{plugin.name} is off. Its tools are hidden until you turn it on again.", t.MUTED, "check")
        self.render(update=True)

    def _set_enabled(self, plugin_id: str, value: bool) -> None:
        s = self.app.settings
        s.plugins = [i for i in s.plugins if i != plugin_id] + ([plugin_id] if value else [])
        s.save()
        plugins.reload()
        if s.radio and plugins.radio(s.radio) is None:
            s.radio = ""
            s.save()

    def _tools_action(self, plugin_id: str):
        state = {p.id: p for p in plugins.load()}.get(plugin_id)
        first = self._first_tool(state) if state is not None and state.loaded else None
        return ("Open its tools", lambda e, k=first: self._open_tool(*k)) if first else None

    # Adding a package

    def _dropped(self, paths: list[str]) -> None:
        wanted = [p for p in paths if drop.suffix(p) == store.EXTENSION]
        if not wanted:
            self.error_dialog("Not a plugin", "Drop a file ending in .pokeplugin.")
            return
        self.open_file(wanted[0])

    async def _pick(self, e=None) -> None:
        files = await self.app.picker.pick_files(dialog_title="Choose a plugin", allowed_extensions=[store.EXTENSION],
                                                 file_type=ft.FilePickerFileType.CUSTOM)
        if files and files[0].path:
            self.open_file(files[0].path)

    async def _pick_update(self, plugin: plugins.Plugin) -> None:
        files = await self.app.picker.pick_files(dialog_title=f"Update {plugin.name}",
                                                 allowed_extensions=[store.EXTENSION],
                                                 file_type=ft.FilePickerFileType.CUSTOM)
        if files and files[0].path:
            self.open_file(files[0].path, expected=plugin)

    def open_file(self, path: str, expected: plugins.Plugin | None = None) -> None:
        """Reads a package and shows what it is with its risks; nothing is installed before the user accepts."""
        try:
            package = store.read(path)
        except store.PackageError as error:
            self.error_dialog(f"{os.path.basename(path)} cannot be installed", str(error))
            return
        if expected is not None and package.id != expected.id:
            self.error_dialog("A different plugin", f"{os.path.basename(path)} is {package.name}, not an update "
                                                    f"of {expected.name}.")
            return
        self.consent(package, store.compare(package, store.installed(package.id)), store.installed(package.id))

    def error_dialog(self, title: str, message: str) -> None:
        self.app.page.show_dialog(t.dialog(
            title=ft.Row([t.pixel_icon("warning-diamond", size=24, color=t.RED), t.text(title, 18, expand=True)],
                         spacing=10),
            content=t.text(message, 13, t.MUTED, width=420, selectable=True),
            actions=[t.button("OK", lambda e: self.app.page.pop_dialog())]))

    def consent(self, package: store.Package, action: str, current: plugins.Plugin | None) -> None:
        """The risk screen every install, update and first turn-on goes through."""
        trust = store.trust(package)
        stranger = trust in ("changed", "dropped")     # not the author of the copy seen before
        state = {"accepted": False, "enable": True, "stranger": not stranger}
        go = t.button("Turn on" if action == "enable" else ACTIONS[action], None,
                      "check", disabled=True, color=t.RED if stranger else t.BLUE)

        def ready() -> None:
            go.disabled = not (state["accepted"] and state["stranger"])
            go.update()

        def accepted(value: bool) -> None:
            state["accepted"] = value
            ready()

        def stranger_ok(value: bool) -> None:
            state["stranger"] = value
            ready()

        def enable(e) -> None:
            state["enable"] = bool(e.control.value)

        def close(e=None) -> None:
            self.app.page.pop_dialog()

        def confirm(e) -> None:
            if not (state["accepted"] and state["stranger"]):
                return
            close()
            self._accepted(package, action, current, state["enable"])

        go.on_click = confirm
        meta = " · ".join(x for x in (f"Version {package.version}" if package.version else "",
                                      f"by {package.author}" if package.author else "by an unnamed author") if x)
        lines: list[ft.Control] = [
            ft.Row([
                plugin_icon(package.icon or (current.icon if current else ""), 56),
                ft.Column([t.text(package.name, 20, weight=ft.FontWeight.W_600),
                           t.text(meta, 12, t.MUTED)], spacing=2, expand=True),
                t.icon_button("close", close, "Cancel"),
            ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.START),
        ]
        if package.description:
            lines.append(t.text(package.description, 13, t.SOFT))
        version_note = {
            "update": (f"Updates {current.name if current else ''} from {current.version if current else '?'} "
                       f"to {package.version}. What it saved is kept.", t.BLUE, "upload"),
            "reinstall": (f"Version {package.version} is already installed; this replaces its files.", t.MUTED,
                          "refresh"),
            "downgrade": (f"Installs {package.version} over the newer {current.version if current else '?'}.",
                          t.AMBER, "warning-diamond"),
            "enable": ("This plugin was copied into the plugins folder by hand and was never checked in the app.",
                       t.AMBER, "warning-diamond"),
        }.get(action)
        if version_note:
            lines.append(t.badge(*version_note))
        level, message = plugins.compatibility(package.api)
        if level == "deprecated":
            lines.append(t.badge(message, t.AMBER, "warning-diamond"))
        if package.source:
            lines.append(t.badge(f"{os.path.basename(package.source)} · {package.files} files · "
                                 f"{store.size_text(package.size)}", t.FAINT, "archive"))
        lines.append(self._signature(package, trust))
        lines.append(self._findings(package.findings))
        lines.append(ft.Container(ft.Row([
            t.pixel_icon("warning-diamond", size=24, color=t.RED),
            ft.Column([t.text("Plugins run with full access", 14, weight=ft.FontWeight.W_600),
                       *[ft.Row([t.text("·", 13, t.RED), t.text(r, 12, t.SOFT, expand=True)], spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.START) for r in RISKS]],
                      spacing=6, expand=True),
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
            padding=16, border_radius=14, bgcolor=ft.Colors.with_opacity(0.08, t.RED),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, t.RED))))
        if stranger:
            lines.append(checkbox("I know this file does not come from the author of the version I had, and "
                                  "I install it anyway.", False, stranger_ok))
        lines.append(checkbox("I understand these risks, and I trust the author of this plugin.", False, accepted))
        if action != "enable":
            lines.append(ft.Row([t.text("Turn it on after installing", 13, expand=True),
                                 t.switch(True, enable)]))
        self.app.page.show_dialog(t.dialog(
            modal=True, content_padding=0, actions_padding=0, inset_padding=32, scrollable=True,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS, semantics_label=f"Install {package.name}",
            content=ft.Container(ft.Column([
                ft.Container(ft.Column(lines, spacing=12, tight=True), padding=ft.Padding(26, 22, 18, 6)),
                ft.Container(ft.Row([ft.Container(expand=True), t.secondary_button("Cancel", close), go],
                                    spacing=8), padding=ft.Padding(26, 12, 22, 22)),
            ], spacing=0, tight=True), width=540, border_radius=20)))

    @staticmethod
    def _signature(package: store.Package, trust: str) -> ft.Control:
        """Who signed the file, against the author of the copy this app saw before."""
        key = f"key {store.fingerprint(package.key)}" if package.key else ""
        title, text, color, icon = {
            "same": ("Signed by the same author", f"The same {key} signed the version installed before.",
                     t.GREEN, "shield"),
            "new": ("Signed by its author", f"Signed with {key}. If the author publishes their key, compare it. "
                    "Every update must carry the same key.", t.BLUE, "key"),
            "unsigned": ("Not signed", "Nothing proves who made this file or that it was not changed since.",
                         t.AMBER, "warning-diamond"),
            "changed": ("Signed by someone else", f"Signed with {key}, not the key of the author of the version "
                        "installed before. Someone else may have made this file.", t.RED, "warning-diamond"),
            "dropped": ("No longer signed", "The version installed before was signed by its author; this file is "
                        "not. Someone else may have made it.", t.RED, "warning-diamond"),
        }[trust]
        return ft.Container(ft.Row([t.pixel_icon(icon, size=24, color=color), ft.Column([
            t.text(title, 14, weight=ft.FontWeight.W_600), t.text(text, 12, t.SOFT, selectable=True)],
            spacing=4, expand=True)], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
            padding=16, border_radius=14, bgcolor=ft.Colors.with_opacity(0.06, color),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, color)))

    @staticmethod
    def _findings(findings: list[str]) -> ft.Control:
        """What a reading of its code found; it informs, it cannot clear a plugin."""
        if findings:
            body = [t.text("What its code does", 14, weight=ft.FontWeight.W_600),
                    *[ft.Row([t.text("·", 13, t.AMBER), t.text(f, 12, t.SOFT, expand=True)], spacing=8,
                             vertical_alignment=ft.CrossAxisAlignment.START) for f in findings]]
            color, icon = t.AMBER, "search"
        else:
            body = [t.text("What its code does", 14, weight=ft.FontWeight.W_600),
                    t.text("No network, program, deletion or hidden code found in its files. A reading of "
                           "the code cannot prove a plugin safe.", 12, t.SOFT)]
            color, icon = t.BLUE, "search"
        return ft.Container(ft.Row([t.pixel_icon(icon, size=24, color=color), ft.Column(body, spacing=6, expand=True)],
                                   spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
                            padding=16, border_radius=14, bgcolor=ft.Colors.with_opacity(0.06, color),
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.25, color)))

    def _accepted(self, package: store.Package, action: str, current, enable: bool) -> None:
        if action == "enable":
            store.accept(current, package.key)
            self._toggle(current, True)
            return
        try:
            store.install(package)
        except (OSError, store.PackageError) as error:
            self.error_dialog(f"{package.name} was not installed", str(error))
            return
        if package.source.startswith(str(SESSION / "plugin-download")):
            shutil.rmtree(SESSION / "plugin-download", ignore_errors=True)
        if self.app.plugin_updates.pop(package.id, None) is not None:
            self.app._plugin_updates_done(self.app.plugin_updates)
        if enable:
            self._set_enabled(package.id, True)
        else:
            plugins.reload()
        state = {p.id: p for p in plugins.load()}.get(package.id)
        done = {"install": "installed", "update": f"updated to {package.version}",
                "reinstall": "reinstalled", "downgrade": f"now at {package.version}"}[action]
        if state is not None and state.error:
            self.say(f"{package.name} is {done} but failed to load. Its error is on its card.", t.RED,
                     "warning-diamond")
        elif enable:
            self.say(f"{package.name} is {done} and on.", action=self._tools_action(package.id))
        else:
            self.say(f"{package.name} is {done}. Turn it on when you want its tools.", t.MUTED)
        self.render(update=True)

    # Removing

    def _confirm_remove(self, plugin: plugins.Plugin) -> None:
        kept = plugins.data_folder(plugin.id).is_dir()
        state = {"data": False}

        def done(e):
            self.app.page.pop_dialog()
            try:
                store.remove(plugin.id, data=state["data"])
            except (OSError, store.PackageError) as error:
                self.error_dialog(f"{plugin.name} was not removed", str(error))
                return
            self._set_enabled(plugin.id, False)
            self.say(f"{plugin.name} is removed.", t.MUTED, "trash")
            self.render(update=True)

        self.app.page.show_dialog(t.dialog(
            title=ft.Row([plugin_icon(plugin.icon, 32), t.text(f"Remove {plugin.name}?", 18, expand=True)],
                         spacing=12),
            content=ft.Column([
                t.text("Its files are deleted from this computer and its tools leave the Games page. A session "
                       "it is running keeps going until it ends.", 13, t.MUTED),
                *([checkbox(f"Also delete what it saved ({store.size_text(store.kept_data(plugin.id))}); "
                            "otherwise installing it again finds it.", False,
                            lambda value: state.update(data=value))] if kept else []),
            ], spacing=12, tight=True, width=420),
            actions=[t.secondary_button("Cancel", lambda e: self.app.page.pop_dialog()),
                     t.button("Remove", done, "trash", color=t.RED)]))
