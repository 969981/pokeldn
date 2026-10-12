"""pokeldn.popup and pokeldn.app.popups: the pop-ups a program shows in the app (docs/gui.md, Pop-ups)."""
import os
import threading

import pytest

from pokeldn import popup
from pokeldn.app import popups, runner


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    """Each test is one program: no pop-up open, no app attached, no dispatcher."""
    monkeypatch.setattr(popup, "_live", {})
    monkeypatch.setattr(popup, "_sink", None)
    monkeypatch.setattr(popup, "_dispatch", None)


@pytest.fixture
def sent(monkeypatch):
    """The messages the program sends the app, as an app-run child does."""
    messages = []
    monkeypatch.setattr(popup, "_sink", messages.append)
    return messages


def reply(message, answer):
    return popup.receive(popup.line({"id": message["id"], "n": message["n"], "answer": answer}) + "\n")


# The program's side.

def test_a_run_sends_each_pop_up_as_one_line_and_its_answer_fires_the_callback(monkeypatch, capsys):
    monkeypatch.setenv("POKELDN_POPUPS", "1")
    acked = []
    id = popup.acknowledge("Saved", "The backup is in the session folder.", on_ack=lambda: acked.append(1),
                           tone="warning")
    out = capsys.readouterr().out
    assert out.count("\n") == 1 and out.startswith(popup.PREFIX) and popup.available()
    message = popup.read(out.rstrip("\n"))[1]
    assert message == {"op": "open", "id": id, "n": message["n"], "kind": "ack", "title": "Saved",
                       "text": "The backup is in the session folder.", "label": "OK", "stack": True,
                       "urgent": False, "tone": "warning"}
    assert reply(message, "agree") and acked == []      # not one of an acknowledgement's answers
    assert reply(message, "ack") and acked == [1]
    assert reply(message, "ack") and acked == [1]       # answered once
    assert not popup.receive("an unrelated line\n")


def test_a_confirmation_fires_the_one_callback_of_the_button_pressed(sent):
    fired = []
    for answer in ("agree", "disagree", "dismiss"):
        popup.confirm("Trade?", "A shiny.", "Trade", "Skip", on_agree=lambda: fired.append("agree"),
                      on_disagree=lambda: fired.append("disagree"), on_dismiss=lambda: fired.append("dismiss"))
        assert sent[-1]["kind"] == "confirm" and (sent[-1]["agree"], sent[-1]["disagree"]) == ("Trade", "Skip")
        reply(sent[-1], answer)
    assert fired == ["agree", "disagree", "dismiss"]
    with pytest.raises(ValueError):
        popup.confirm("Trade?", "", "Trade", "")


def test_opening_again_under_an_id_replaces_the_pop_up_and_drops_its_callbacks(sent):
    fired = []
    first = popup.acknowledge("One", id="gift", on_ack=lambda: fired.append("one"))
    second = popup.acknowledge("Two", id="gift", on_ack=lambda: fired.append("two"))
    assert first == second == "gift" and sent[1]["n"] > sent[0]["n"]
    reply(sent[0], "ack")                               # the app answered the first before it was replaced
    assert fired == []
    reply(sent[1], "ack")
    assert fired == ["two"]


def test_a_cancelled_pop_up_fires_nothing_and_an_unknown_id_is_nothing_to_cancel(sent):
    fired = []
    id = popup.confirm("Trade?", "", "Trade", "Skip", on_agree=lambda: fired.append(1),
                       on_dismiss=lambda: fired.append(2))
    popup.cancel(id)
    assert sent[-1] == {"op": "cancel", "id": id}
    reply(sent[0], "agree")
    popup.cancel(id)
    popup.cancel("never-opened")
    assert fired == [] and len(sent) == 2


def test_a_timeout_dismisses_a_confirmation_and_closes_an_acknowledgement_silently(sent):
    dismissed, acked = threading.Event(), []
    popup.confirm("Trade?", "", "Trade", "Skip", id="ask", timeout=0.05, on_dismiss=dismissed.set)
    popup.acknowledge("Note", id="note", timeout=0.05, on_ack=lambda: acked.append(1))
    assert dismissed.wait(5)
    for _ in range(100):
        if {"op": "cancel", "id": "note"} in sent:
            break
        threading.Event().wait(0.02)
    assert {"op": "cancel", "id": "ask"} in sent and {"op": "cancel", "id": "note"} in sent and acked == []
    with pytest.raises(ValueError):
        popup.acknowledge("Note", timeout=0)


def test_an_answer_ends_the_timer(sent):
    dismissed = []
    popup.confirm("Trade?", "", "Trade", "Skip", timeout=0.1, on_dismiss=lambda: dismissed.append(1))
    reply(sent[0], "agree")
    threading.Event().wait(0.3)
    assert dismissed == [] and len(sent) == 1


def test_a_dispatcher_runs_the_callbacks_and_one_that_raises_prints_its_traceback(sent, capsys):
    handed = []
    popup.set_dispatcher(handed.append)

    def broken():
        raise KeyError("oops")
    popup.acknowledge("Note", on_ack=broken)
    reply(sent[0], "ack")
    assert len(handed) == 1
    handed[0]()                                         # the program's loop runs it
    assert "KeyError: 'oops'" in capsys.readouterr().err


def test_a_program_holding_the_limit_unanswered_is_refused_until_one_is_answered(sent):
    for n in range(popup.LIMIT):
        popup.acknowledge(f"Note {n}", id=str(n))
    popup.acknowledge("Again", id="0")                  # a replacement takes no new place
    with pytest.raises(RuntimeError):
        popup.acknowledge("One too many")
    reply(sent[0 + popup.LIMIT], "ack")                 # the replaced "0", answered
    popup.acknowledge("Room again")


def test_with_no_app_a_pop_up_is_a_log_line_and_never_answered(capsys):
    assert not popup.available()
    popup.confirm("Trade?", "A shiny.", "Trade", "Skip")
    popup.acknowledge("Saved", "In the session folder.")
    assert capsys.readouterr().out == ("[pop-up] Trade?: A shiny. [Trade / Skip / Dismiss]\n"
                                       "[pop-up] Saved: In the session folder. [OK]\n")
    with pytest.raises(ValueError):
        popup.acknowledge("Loud", tone="alarm")


def test_with_no_app_only_a_pop_up_with_a_timeout_waits(capsys):
    """A terminal run never answers: a host that warns each round never reaches LIMIT, and a timeout still
    dismisses its pop-up."""
    for n in range(popup.LIMIT + 8):
        popup.acknowledge(f"Round {n}", id=f"gift-{n}")
    dismissed = threading.Event()
    popup.confirm("Trade?", "", "Trade", "Skip", timeout=0.05, on_dismiss=dismissed.set)
    assert dismissed.wait(5) and popup._live == {}
    assert capsys.readouterr().out.count("[pop-up] ") == popup.LIMIT + 9


def test_a_message_is_found_wherever_another_threads_print_left_it():
    line = popup.line({"op": "cancel", "id": "x"})
    assert popup.read("[sv] partner" + line) == ("[sv] partner", {"op": "cancel", "id": "x"})
    assert popup.read("[sv] partner offers 992") == ("[sv] partner offers 992", None)
    assert popup.read(popup.PREFIX + "not json")[1] is None
    assert popup.read(popup.PREFIX + "[1, 2]")[1] is None


# The app's side.

class View:
    def __init__(self):
        self.shown, self.events = [], []

    def show(self, entry):
        self.shown.append(entry)
        self.events.append(("show", entry.title))

    def refresh(self, old, entry):
        self.shown[self.shown.index(old)] = entry
        self.events.append(("refresh", entry.title))

    def hide(self, entry):
        self.shown.remove(entry)
        self.events.append(("hide", entry.title))


def opened(title, id=None, kind="ack", n=1, **fields):
    message = {"op": "open", "id": id or title, "n": n, "kind": kind, "title": title, "text": "", "label": "OK",
               "stack": True, "urgent": False, "tone": "info"}
    if kind == "confirm":
        message.update(agree="Yes", disagree="No")
    return {**message, **fields}


def manager():
    view = View()
    answers = []
    app = popups.Manager(view)
    return app, view, app.program("Trade host", answers.append), answers


def titles(view):
    return [e.title for e in view.shown]


def test_pop_ups_stack_until_one_that_refuses_it_shows_then_wait_their_turn():
    app, view, run, _ = manager()
    run.take(opened("A"))
    run.take(opened("Blocker", stack=False))
    run.take(opened("B"))
    run.take(opened("C", stack=False))
    run.take(opened("D"))
    assert titles(view) == ["A", "Blocker"] and [e.title for e in app.queue] == ["B", "C", "D"]
    run.take(opened("Now", urgent=True))
    assert titles(view) == ["A", "Blocker", "Now"]
    app.answer(view.shown[1], "ack")
    assert titles(view) == ["A", "Now", "B", "C"] and [e.title for e in app.queue] == ["D"]
    app.answer(view.shown[3], "ack")
    assert titles(view) == ["A", "Now", "B", "D"] and app.queue == []


def test_a_pop_up_opened_again_under_its_id_keeps_its_place():
    app, view, run, answers = manager()
    run.take(opened("Old", id="gift"))
    run.take(opened("Top"))
    run.take(opened("New", id="gift", n=2))
    assert titles(view) == ["New", "Top"] and ("refresh", "New") in view.events
    app.answer(view.shown[0], "ack")
    assert answers == [{"id": "gift", "n": 2, "answer": "ack"}]
    run.take(opened("Blocker", stack=False))
    run.take(opened("Queued", id="q"))
    run.take(opened("Later"))
    run.take(opened("Queued again", id="q", n=3))
    assert [e.title for e in app.queue] == ["Queued again", "Later"]
    run.take(opened("Queued, urgent", id="q", n=4, urgent=True))
    assert titles(view)[-1] == "Queued, urgent" and [e.title for e in app.queue] == ["Later"]


def test_an_answer_goes_back_once_and_esc_dismisses_or_acknowledges():
    app, view, run, answers = manager()
    run.take(opened("Ask", kind="confirm"))
    run.take(opened("Note"))
    ask, note = view.shown
    app.answer(ask, "maybe")
    assert answers == [] and titles(view) == ["Ask", "Note"]
    note.escaped()
    ask.escaped()
    ask.press("agree")                                  # closed already
    assert answers == [{"id": "Note", "n": 1, "answer": "ack"}, {"id": "Ask", "n": 1, "answer": "dismiss"}]
    run.take({"op": "cancel", "id": "Ask"})             # answered: nothing open to cancel
    assert view.shown == []


def test_cancel_closes_an_open_pop_up_or_takes_a_queued_one_out_and_the_app_reports_nothing():
    app, view, run, answers = manager()
    run.take(opened("Blocker", stack=False))
    run.take(opened("Queued"))
    run.take({"op": "cancel", "id": "Queued"})
    run.take({"op": "cancel", "id": "Blocker"})
    assert view.shown == [] and app.queue == [] and answers == []
    assert view.events == [("show", "Blocker"), ("hide", "Blocker")]


def test_a_program_that_exits_leaves_its_acknowledgements_without_an_answer():
    app, view, run, answers = manager()
    other = app.program("Other", answers.append)
    run.take(opened("Note"))
    run.take(opened("Ask", kind="confirm"))
    other.take(opened("Blocker", stack=False))
    run.take(opened("Queued"))
    run.ended()
    assert titles(view) == ["Note", "Blocker"] and app.queue == []
    run.take(opened("After"))
    view.shown[0].press("ack")
    assert answers == [] and titles(view) == ["Blocker"]


def test_each_program_has_its_own_ids_and_a_malformed_message_opens_nothing():
    app, view, run, answers = manager()
    other = app.program("Other", answers.append)
    run.take(opened("Mine", id="x"))
    other.take(opened("Theirs", id="x"))
    assert titles(view) == ["Mine", "Theirs"] and view.shown[1].source == "Other"
    for bad in (opened("No kind", kind="alert"), opened("No n", n="1"), opened("No labels", kind="confirm", agree=""),
                {"op": "open", "n": 1, "kind": "ack"}, ["not", "a", "dict"], {"op": "shout"}):
        run.take(bad)
    assert titles(view) == ["Mine", "Theirs"]
    run.take(opened("t" * 500, id="long", text="x" * 9000, tone="loud"))
    long = view.shown[-1]
    assert len(long.title) == popups.CLIP["title"] and len(long.text) == popups.CLIP["text"]
    assert long.tone == "info"


def test_the_app_shows_no_more_than_the_limit_of_one_program():
    app, view, run, _ = manager()
    for n in range(popup.LIMIT + 3):
        run.take(opened(f"Note {n}"))
    assert len(view.shown) == popup.LIMIT


def test_code_in_the_app_reaches_the_manager_directly(monkeypatch):
    app, view, _, _ = manager()
    acked = []
    program = app.program("", popup.answered)
    monkeypatch.setattr(popup, "_sink", program.take)
    popup.acknowledge("Update failed", on_ack=lambda: acked.append(1), label="Close")
    assert view.shown[0].label == "Close" and view.shown[0].source == ""
    view.shown[0].press("ack")
    assert acked == [1]


def test_a_run_shows_its_pop_ups_in_the_app_and_gets_the_answers(tmp_path):
    """End to end: the child's `[popup]` lines stay out of the log, the button's answer reaches its callback
    on the child's stdin, and Stop still interrupts it."""
    script = tmp_path / "ask.py"
    script.write_text(
        "import threading, time\n"
        "from pokeldn import popup\n"
        "answered = threading.Event()\n"
        "print('before')\n"
        "popup.confirm('Trade?', 'A shiny.', 'Trade', 'Skip', on_agree=lambda: (print('agreed'), answered.set()))\n"
        "popup.acknowledge('Note', 'stays')\n"
        "answered.wait(10)\n"
        "try:\n"
        "    while True: time.sleep(0.02)\n"
        "except KeyboardInterrupt:\n"
        "    print('stopped')\n", encoding="utf-8")
    view, lines, exits = View(), [], []
    shown, agreed, done = threading.Event(), threading.Event(), threading.Event()
    original = view.show

    def show(entry):
        original(entry)
        if len(view.shown) == 2:
            shown.set()
    view.show = show
    app = popups.Manager(view)

    def line(value):
        lines.append(value)
        if value == "agreed":
            agreed.set()

    def exit(code):
        exits.append(code)
        done.set()
    process = runner.Process(["--run", str(script)], str(tmp_path), dict(os.environ, POKELDN_MANAGED_RUN="1"),
                             line, exit, popups=app, label="Test")
    try:
        assert shown.wait(10)
        ask = view.shown[0]
        assert (ask.kind, ask.title, ask.agree, ask.source) == ("confirm", "Trade?", "Trade", "Test")
        ask.press("agree")
        assert agreed.wait(10)
    finally:
        process.stop()
        assert done.wait(20)
    assert exits == [0] and lines == ["before", "agreed", "stopped"]
    assert titles(view) == ["Note"]                     # the acknowledgement outlives its program
    view.shown[0].press("ack")                          # and its answer goes nowhere
