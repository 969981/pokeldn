"""The shared Browse Meta dialog used by every supported Pokemon offer picker."""
import threading

import flet as ft

from pokeldn import meta
from gui import theme as t
from gui.views.widgets import PixelActivity

ALL = "*"


class MetaBrowser:
    def __init__(self, app, game: str, on_use):
        self.app, self.game, self.on_use = app, game, on_use
        self.builds: list[dict] = []
        self.filtered: list[dict] = []
        self.selected: dict | None = None
        self.search = t.field(hint="Search Pokemon or role", on_change=lambda e: self._filter())
        choices = [(ALL, "All formats"), *meta.formats(game)]
        self.format = t.dropdown(choices, ALL, on_select=lambda e: self._filter(), width=180)
        self.results = ft.ListView(spacing=4, height=300)
        self.preview = ft.Container()
        self.status = ft.Container()
        self.use = t.button("Use Build", self._use, disabled=True)
        self.dialog = t.dialog(
            title=t.text("Browse Meta", 17, weight=ft.FontWeight.W_600),
            content=ft.Container(ft.Column([
                t.text("Competitive source sets are imported through PKHeX. Meta suitability does not imply "
                       "legality in the selected game.", 12, t.MUTED),
                ft.Row([self.search, self.format], spacing=8),
                ft.Row([ft.Container(self.results, expand=True),
                        ft.Container(self.preview, width=290, padding=ft.Padding(12, 4, 0, 4))],
                       spacing=8, vertical_alignment=ft.CrossAxisAlignment.START),
                self.status,
            ], spacing=10, tight=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH), width=760),
            actions=[t.secondary_button("Cancel", lambda e: self.app.page.pop_dialog()), self.use],
        )

    def open(self) -> None:
        self.app.page.show_dialog(self.dialog)
        if not meta.formats(self.game):
            self.status.content = t.text(meta.unavailable(self.game), 12, t.AMBER, selectable=True)
            self.search.disabled = self.format.disabled = True
            self.dialog.update()
            return
        self.status.content = ft.Row([PixelActivity("Loading meta builds"),
                                      t.text("Loading source sets...", 12, t.MUTED)], spacing=8)
        self.dialog.update()
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self) -> None:
        try:
            builds, stale = meta.load(self.game)
            error = ""
        except Exception as exc:
            builds, stale, error = [], False, str(exc)

        def show():
            self.builds = builds
            if error:
                self.status.content = t.text(error, 12, t.RED, selectable=True)
            else:
                suffix = " A cached copy is shown because refresh failed." if stale else ""
                self.status.content = t.text(
                    f"{len(builds)} builds · {meta.SOURCE}.{suffix}", 12, t.AMBER if stale else t.FAINT)
                self._filter(update=False)
            self.dialog.update()
        self.app.ui(show)

    def _filter(self, update: bool = True) -> None:
        query = (self.search.value or "").strip().casefold()
        format_id = self.format.value
        self.filtered = [build for build in self.builds
                         if (format_id == ALL or build["format_id"] == format_id)
                         and (not query or query in build["species"].casefold()
                              or query in build["role"].casefold())]
        self.results.controls = [self._row(build) for build in self.filtered]
        if not self.filtered:
            self.results.controls = [t.text("No builds match this search.", 12, t.MUTED)]
        if self.selected not in self.filtered:
            self.selected = None
            self.preview.content = t.text("Select a build to preview it.", 12, t.MUTED)
            self.use.disabled = True
        if update:
            self.dialog.update()

    def _row(self, build: dict) -> ft.Control:
        selected = build is self.selected
        return ft.Container(ft.Column([
            t.text(build["species"], 13, weight=ft.FontWeight.W_600),
            t.text(f"{build['role']} · {build['format']}", 11, t.MUTED),
        ], spacing=1, tight=True), padding=ft.Padding(10, 7, 10, 7), border_radius=9,
            bgcolor=t.SELECTED if selected else None, ink=True,
            on_click=lambda e, chosen=build: self._select(chosen))

    def _select(self, build: dict) -> None:
        self.selected = build
        self.results.controls = [self._row(item) for item in self.filtered]
        rows = [
            t.text(build["species"], 16, weight=ft.FontWeight.W_600),
            t.text(build["role"], 13, t.TEXT),
            t.badge(build["format"], t.BLUE, "label"),
        ]
        rows += [ft.Column([t.text(label, 11, t.FAINT), t.text(value, 12, t.MUTED, selectable=True)],
                           spacing=0, tight=True)
                 for label, value in meta.preview(build)]
        rows.append(t.text(f"Source: {build['source']} · {build['source_url']}", 11, t.FAINT,
                           selectable=True))
        self.preview.content = ft.Column(rows, spacing=7, tight=True)
        self.use.disabled = False
        self.dialog.update()

    def _use(self, e) -> None:
        if self.selected is None:
            return
        self.use.disabled = True
        self.status.content = ft.Row([PixelActivity("Checking meta build"),
                                      t.text("Resolving alternatives and checking game legality...", 12, t.MUTED)],
                                     spacing=8)
        self.dialog.update()

        def finished(error: str = ""):
            if error:
                self.status.content = t.text(error, 12, t.RED, selectable=True)
                self.use.disabled = False
                self.dialog.update()
            else:
                self.app.page.pop_dialog()
        self.on_use(self.selected, finished)
