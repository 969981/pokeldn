---
title: Simulated Mystery Gifts
---
# Simulated Mystery Gifts

Let's Go Pikachu/Eevee, Brilliant Diamond/Shining Pearl, Legends Arceus, Scarlet/Violet and Legends
Z-A take no Mystery Gift card over local wireless. Each has a Mystery Gift - Simulated tool that
brings a console an official gift Pokemon another way: the game's trade host offers a fresh legal
copy, as a trainer who received the gift and trades it on. The console's player offers a Pokemon in
return, which goes to Received like any trade's.

| game | tool | the host it is | offer flag |
|---|---|---|---|
| Let's Go | `lgpe-gift-host` | Trade (Host), `bin/lgpe_host.py` | `--offer` |
| Brilliant Diamond/Shining Pearl | `bdsp-gift-host` | Trade (Host), `bin/bdsp_host.py` | `--offer` |
| Legends Arceus | `pla-gift-host` | Trade (Host), `bin/pla_host.py` | `--trade-box-record` |
| Scarlet/Violet | `sv-gift-host` | Trade (Host), `bin/sv_host.py` ([Hosting for a console](sv.md#hosting-for-a-console)) | `--trade-offer` |
| Legends Z-A | `za-gift-host` | Trade (Host), `bin/za_host.py` | `--trade-offer` |

Each tool is its game's Trade (Host) with its one offer picked from the game's gifts: the same entry
point and fixed arguments, the host's code (Brilliant Diamond/Shining Pearl's room password) and New
PID each run. It sits after the game's trades (`catalog.simulated_gift`). The steps are the host's,
with the event Pokemon chosen first.

## The gifts

PKHeX.Core embeds every distribution its legality check knows, one table per game, read from the
package's own resources: nothing is downloaded. The PKHeX service's `gift_events` lists a table's
Pokemon cards, eggs and item cards left out, newest first by the day the distribution opened
(`EncounterServerDate.GetDistributionWindow`); a card PKHeX holds no day for lists after the dated
ones. PKHeX.Core 26.8.26 holds:

| game | table | gift Pokemon | opened | HOME's | Your OT |
|---|---|---:|---|---|---:|
| Let's Go | `MGDB_G7GG` | 15 | undated, but for HOME's Meltan (11 Feb 2025) | Meltan (9028) | 3 |
| Brilliant Diamond/Shining Pearl | `MGDB_G8B` | 9 | 18 May 2022 to 27 Jan 2025, 5 undated | Turtwig, Chimchar, Piplup (9015 to 9017), Manaphy (9026) | 3 |
| Legends Arceus | `MGDB_G8A` | 11 | 27 Jan 2022 to 27 Jan 2025 | Rowlet, Cyndaquil, Oshawott (9018 to 9020), Enamorus (9027) | 3 |
| Scarlet/Violet | `MGDB_G9` | 106 | 17 Nov 2022 to 5 Jun 2026 | Sprigatito, Fuecoco, Quaxly (9021 to 9023), Meloetta (9024), Garchomp (9035) | 29 |
| Legends Z-A | `MGDB_G9A` | 8 | 14 Oct 2025 to 26 Apr 2026 | Chikorita, Tepig, Totodile (9031 to 9033), Volcanion (9034) | 5 |

Each gift has a key, `card-species-form`, with the Tera type after it on Scarlet/Violet
(`0503-964-0-10` is Gavin's Palafin). Scarlet/Violet's card 1521 holds eighteen Mew, one per Tera
type: its 106 gifts come from 77 cards, and the 29 that give the receiver's own trainer from 12. Two
records under one key differ only in what the Pokemon does not carry, such as the card's revision.

The tool's card lists the gifts ([Mystery Gift - Simulated](gui.md#mystery-gift---simulated)), each as
the trainer in Settings would receive it (PKHeX's `ConvertToPKM` with that trainer): the card's own OT
and language where the card fixes them, otherwise Your OT. A tile also shows the level, Tera type,
shininess (may be or always), held item and the day the distribution opened; a hover shows the moves.
The search matches any word of these, the ball, the moves and the card number.

### HOME's gifts

HOME delivers Pokemon, not cards: PKHeX's HOME cards rebuild what it hands out. The EventsGallery
names each "Simulated" and the trainer it gives:

| OT | gallery | cards |
|---|---|---|
| HOME | "Simulated HOME" | Let's Go's Meltan (9028), Manaphy (9026), Enamorus (9027), Meloetta (9024), Volcanion (9034) |
| the receiving trainer's | "Simulated (Trainer)" | Turtwig, Chimchar, Piplup (9015 to 9017); Rowlet, Cyndaquil, Oshawott (9018 to 9020); Sprigatito, Fuecoco, Quaxly (9021 to 9023); Chikorita, Tepig, Totodile (9031 to 9033) |
| PJCS26, in Japanese | "Simulated PJCS26" | Scarlet/Violet's Garchomp (9035) |

A gift HOME gave carries the tracker HOME sets as it delivers it. Let's Go has no HOME tracker, so its
Meltan needs none. On the other games, a copy of one gets the tracker the HOME tracker setting gives
it ([The HOME tracker setting](gui.md#the-home-tracker-setting)): none under `empty`, which PKHeX
flags and the app accepts as the only problem, and a made one under `made`, which Pokemon HOME
refuses. Each reply says which (`home_tracker`). No other gift needs a tracker.

- **The list:** each such gift is outlined in amber with the setting's warning, which the search
  finds.
- **The chosen copy:** Legal, with the same warning.
- **The trade:** the host checks its offer under the same setting, which it inherits from the app
  (`POKELDN_HOME_TRACKER`).

Two of HOME's gifts need more than PKHeX's `ConvertToPKM` gives (`services/pkhex/Program.cs`):

- **Let's Go's Meltan (card 9028)** keeps the height and weight HOME gave it
  (`WB7.IsHeightWeightFixed`), which PKHeX's check expects in place of the computed ones
  [MiscVerifierPB7]. The service computes every other Let's Go Pokemon's as the console does, and
  restores this card's (`ResetSizes`).
- **Legends Z-A's Chikorita, Tepig and Totodile (cards 9031 to 9033)** are Alphas with three perfect
  IVs and 20 in the rest (`WA9.HomeBaseIV`). PKHeX.Core 26.8.26 makes them with one perfect IV and
  five at 0, which its own check refuses, so the service sets HOME's spread (`SetHomeIVs`).

## The copy a trade offers

Picking a gift runs `gift_event`: a fresh copy for the trainer in Settings, made on each of the game's
versions in turn until one gives a legal copy. Scarlet/Violet's card 1540 gave Scarlet a shiny
Miraidon and Violet a shiny Koraidon, each to that version alone. A copy illegal as made gets a
handler (POKELDN), as the receiving save sets one on a card that arrives already handled. The card's
moves are never refitted. A PID roll its own check rejects is rolled again, up to eight times on each
version.

The copy is kept with the built Pokemon and offered like one, under the trainer it was made with. The
host checks it again as it prepares the offer. With New PID each run on, the copy gets a new PID and
encryption constant where the card rolls them, and a fixed PID stays ("kept its own PID"). Every gift
of the five games passes that check under either HOME tracker setting (`tests/test_pokemon_service.py`).

The console receives a traded event Pokemon:

- the card's own trainer and language, where the card fixes them (Gavin's Palafin keeps OT Gavin and
  English);
- otherwise, the app's trainer from Settings, as a gift to the receiver names;
- with the card's trainer, or the app's, the console's player becomes its handler.

## Other games

FireRed and LeafGreen receive event Pokemon through their own Mystery Gift:
[Event Pokemon](frlg_gift.md#event-pokemon) sends a fresh Gen 3 distribution through the Mystery
Event `givepokemon`. Sword and Shield take real cards over local wireless
([Official event cards](swsh_gift.md#official-event-cards)).
