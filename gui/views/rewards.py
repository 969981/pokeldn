import flet as ft

from gui import theme as t
from gui.views.pokemon import NamePicker
from pokeldn.sv.raid import REWARD_ROWS


TEMPLATES = (
    ("training", "Training bundle", (1128, 50, 53, 795, 796, 1606)),
    ("shards", "Tera shard bundle", tuple(range(1862, 1880)) + (2549,)),
    ("herba", "Herba Mystica bundle", (1904, 1905, 1906, 1907, 1908)),
    ("treasure", "Treasure bundle", (92, 581, 91, 583)),
    ("balls", "Ball bundle", (2, 3, 6, 7, 9, 10, 11, 12, 13, 15)),
)
TEMPLATE_ITEMS = {key: items for key, _, items in TEMPLATES}


class RewardPicker:
    """A raid's reward rows in order, each an item from the game's bag list and a quantity. The value
    is [{"item_id", "quantity"}]; an empty list keeps the raid's own rewards."""

    def __init__(self, app, game: str, value, on_change):
        self.app, self.game, self.on_change = app, game, on_change
        self.value = [dict(row) for row in value] if isinstance(value, (list, tuple)) else []
        self.template = self._template_of()
        self.template_quantity = self._template_quantity()
        self.rows = ft.Column(spacing=8)
        self.templates = t.dropdown([("seed", "Raid's own rewards"), ("custom", "Custom rewards")]
                                    + [(key, label) for key, label, _ in TEMPLATES], self.template,
                                    on_select=self._choose_template)
        self.quantity = t.field(value=self.template_quantity, mono=True, width=110,
                                keyboard_type=ft.KeyboardType.NUMBER,
                                on_change=self._set_template_quantity)
        self.template_quantity_control = ft.Column([
            t.text("Quantity each", 11, t.MUTED), self.quantity], spacing=4)
        self.template_controls = ft.Row([
            ft.Column([t.text("Template", 11, t.MUTED), self.templates], spacing=4, expand=True),
            self.template_quantity_control,
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.END)
        self.add = t.secondary_button("Add reward", self._add, "plus")
        self.control = ft.Column([self.template_controls, self.rows, self.add], spacing=10, tight=True)
        self._render(update=False)

    def _template_of(self) -> str:
        items = tuple(int(row.get("item_id", 0) or 0) for row in self.value)
        if not items:
            return "seed"
        return next((key for key, expected in TEMPLATE_ITEMS.items() if items == expected), "custom")

    def _template_quantity(self) -> str:
        quantities = {str(row.get("quantity", "")) for row in self.value}
        if len(quantities) == 1:
            quantity = quantities.pop()
            if quantity.isdigit():
                return quantity
        return "50"

    def _set(self, index: int, key: str, value: str) -> None:
        self.value[index][key] = value
        self.template = "custom"
        self.templates.value = self.template
        self.templates.update()
        self.on_change([dict(row) for row in self.value])

    def _choose_template(self, event) -> None:
        self.template = event.control.value
        if self.template == "seed":
            self.value = []
            self.on_change([])
        elif self.template != "custom":
            self._apply_template()
        self._render()

    def _set_template_quantity(self, event) -> None:
        text = event.control.value
        event.control.error = None if text.isdigit() and 1 <= int(text) <= 999 else "1 to 999"
        event.control.update()
        if event.control.error is None:
            self.template_quantity = text
            if self.template in TEMPLATE_ITEMS:
                self._apply_template()
                self._render()

    def _apply_template(self) -> None:
        self.value = [{"item_id": str(item), "quantity": self.template_quantity}
                      for item in TEMPLATE_ITEMS[self.template]]
        self.on_change([dict(row) for row in self.value])

    def _quantity(self, event, index: int) -> None:
        text = event.control.value
        event.control.error = None if text.isdigit() and 1 <= int(text) <= 999 else "1 to 999"
        event.control.update()
        self._set(index, "quantity", text)

    def _add(self, _event) -> None:
        if len(self.value) < REWARD_ROWS:
            self.value.append({"item_id": "", "quantity": "1"})
            self.template = "custom"
            self.templates.value = self.template
            self.on_change([dict(row) for row in self.value])
            self._render()

    def _remove(self, index: int) -> None:
        self.value.pop(index)
        self.template = self._template_of()
        self.templates.value = self.template
        self.on_change([dict(row) for row in self.value])
        self._render()

    def _render(self, update: bool = True) -> None:
        rows = []
        for index, row in enumerate(self.value):
            item = NamePicker(self.app, self.game, "bag", str(row.get("item_id", "")),
                              lambda value, n=index: self._set(n, "item_id", value),
                              optional=False).control
            quantity = t.field(value=str(row.get("quantity", "1")), mono=True, width=110,
                               keyboard_type=ft.KeyboardType.NUMBER,
                               on_change=lambda event, n=index: self._quantity(event, n))
            rows.append(ft.Row([
                ft.Container(t.text(str(index + 1), 11, t.BLUE, weight=ft.FontWeight.W_700), width=24, height=24,
                             margin=ft.Margin(0, 0, 0, 5), alignment=ft.Alignment.CENTER, border_radius=12,
                             bgcolor=ft.Colors.with_opacity(0.12, t.BLUE)),
                ft.Column([t.text("Item", 11, t.MUTED), item], spacing=4, expand=True),
                ft.Column([t.text("Quantity", 11, t.MUTED), quantity], spacing=4),
                t.icon_button("close", lambda _e, n=index: self._remove(n), "Remove reward"),
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.END))
        if not rows:
            rows.append(ft.Row([t.pixel_icon("gift", color=t.FAINT),
                                t.text("The raid's own rewards, shown with the raid above.", 12, t.MUTED)],
                               spacing=8))
        self.rows.controls = rows
        self.template_quantity_control.visible = self.template in TEMPLATE_ITEMS
        self.add.disabled = len(self.value) >= REWARD_ROWS
        if update:
            self.control.update()
