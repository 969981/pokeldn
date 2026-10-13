"""Game form numbers -> PokeAPI sprite filenames (without .png).

Source: https://github.com/PokeAPI/pokeapi/blob/master/data/v2/csv/pokemon.csv
Cosmetic forms: https://github.com/PokeAPI/sprites/tree/master/sprites/pokemon
These are game form indices, not PokeAPI's pokemon-form ids or form_order.
Unknown forms deliberately have no image instead of showing a different Pokemon.
"""

FORM_SPRITES = {
    # Pikachu's game index 8 is the Let's Go partner, not the World Cap (9).
    (25, 1): 10094, (25, 2): 10095, (25, 3): 10096, (25, 4): 10097,
    (25, 5): 10098, (25, 6): 10099, (25, 7): 10148, (25, 9): 10160,
    # Alolan forms.
    (19, 1): 10091, (20, 1): 10092, (26, 1): 10100, (27, 1): 10101,
    (28, 1): 10102, (37, 1): 10103, (38, 1): 10104, (50, 1): 10105,
    (51, 1): 10106, (52, 1): 10107, (53, 1): 10108, (74, 1): 10109,
    (75, 1): 10110, (76, 1): 10111, (88, 1): 10112, (89, 1): 10113,
    (103, 1): 10114, (105, 1): 10115,
    # Galarian forms; Meowth and Slowbro already have another form at index 1.
    (52, 2): 10161, (77, 1): 10162, (78, 1): 10163, (79, 1): 10164,
    (80, 2): 10165, (83, 1): 10166, (110, 1): 10167, (122, 1): 10168,
    (144, 1): 10169, (145, 1): 10170, (146, 1): 10171, (199, 1): 10172,
    (222, 1): 10173, (263, 1): 10174, (264, 1): 10175, (554, 1): 10176,
    (555, 2): 10177, (555, 3): 10178, (562, 1): 10179, (618, 1): 10180,
    # Other alternate forms in the bundled Sword/Shield event cards.
    (423, 1): "423-east", (801, 1): 10147, (854, 1): "854-antique", (893, 1): 10192,
    # Remaining Sword/Shield form choices from the app's PKHeX Options response.
    (421, 1): "421-sunshine", (422, 1): "422-east", (487, 1): 10007,
    (479, 1): 10008, (479, 2): 10009, (479, 3): 10010, (479, 4): 10011, (479, 5): 10012,
    (550, 1): 10016, (555, 1): 10017, (641, 1): 10019, (642, 1): 10020, (645, 1): 10021,
    (646, 1): 10023, (646, 2): 10022, (647, 1): 10024,
    (649, 1): "649-douse", (649, 2): "649-shock", (649, 3): "649-burn", (649, 4): "649-chill",
    (678, 1): 10025, (681, 1): 10026,
    (710, 1): 10027, (710, 2): 10028, (710, 3): 10029,
    (711, 1): 10030, (711, 2): 10031, (711, 3): 10032,
    (716, 0): "716-neutral", (716, 1): "716-active",
    (718, 1): 10181, (718, 2): 10118, (718, 3): 10119, (718, 4): 10120,
    (744, 1): 10151, (745, 1): 10126, (745, 2): 10152, (746, 1): 10127,
    (778, 1): 10143, (800, 1): 10155, (800, 2): 10156,
    (845, 1): 10182, (845, 2): 10183, (849, 1): 10184, (855, 1): "855-antique",
    (875, 1): 10185, (876, 1): 10186, (877, 1): 10187,
    (888, 1): 10188, (889, 1): 10189, (890, 1): 10190, (892, 1): 10191,
    (898, 1): 10193, (898, 2): 10194,
    **{(773, n): f"773-{name}" for n, name in enumerate((
        "fighting", "flying", "poison", "ground", "rock", "bug", "ghost", "steel", "fire",
        "water", "grass", "electric", "psychic", "ice", "dragon", "dark", "fairy"), start=1)},
    # The gift builder leaves Alcremie's decoration at its default Strawberry Sweet.
    **{(869, n): f"869-{name}-strawberry-sweet" for n, name in enumerate((
        "ruby-cream", "matcha-cream", "mint-cream", "lemon-cream", "salted-cream",
        "ruby-swirl", "caramel-swirl", "rainbow-swirl"), start=1)},
}


def sprite_key(species: int, form: int = 0) -> int | str | None:
    return FORM_SPRITES.get((species, form), None if form else species)
