#!/usr/bin/env python3
"""test_cb_readback.py — prevention, and the two rules that keep it from becoming a rail.

Zero provider calls: cb_llm.structured is stubbed throughout. What is tested is the CONTRACT
(never blocks, never scores, never edits, degrades to silence) and the PROMPT (it must carry
the two real failures as worked examples, or it is guessing).
"""
import cb_llm
import cb_readback as R


def test_it_never_becomes_a_gate():
    """CLAUDE.md rule 87: "A new gate, a new negative, a new law, a new refusal, a new word
    cap, a new lint is NOT the answer here — that direction was tried for weeks and the
    footage got worse." A reading is not a rail. This one reports and hands over."""
    src = open(R.__file__).read()
    # Scoped to the reader itself. The __main__ CLI legitimately sys.exit(1)s when a shot
    # has no direction on record — that is a command-line tool reporting nothing to read,
    # not the reader refusing a director anything.
    body = src[src.index("def read_back("):src.index('if __name__')]
    for banned in ("raise Refused", "sys.exit(", "raise RuntimeError"):
        assert banned not in body, f"cb_readback learned to refuse something ({banned})"
    assert "score" not in R.ReadBack.model_fields, "a NUMERIC score would make it a judge"
    assert "passes" not in R.ReadBack.model_fields, "pass/fail is a gate's vocabulary"
    # THE INVARIANT, RESTATED — NOT LOOSENED (2026-07-27). This used to assert `verdict` was
    # absent, treating "has no opinion" as the way to prove "is not a gate". Julian then asked
    # for exactly the opposite: "i dont want to be the guy reading the direction, i really
    # need a strong pair of eyes that... ensures it delivers." A reading he must interpret
    # himself is the chair he asked to leave.
    #
    # An opinion was only ever a PROXY for the real rule. The real rule is that nothing this
    # returns can stop him doing anything — and that is now asserted directly, which is
    # stronger than the proxy ever was, because the proxy would have passed happily on a
    # field named something else that DID gate.
    assert "delivers" in R.ReadBack.model_fields, (
        "the eyes lost their recommendation — he is back to reading prompts himself")


def test_no_code_anywhere_acts_on_the_recommendation():
    """THE TEETH. An advisory becomes a gate the moment one branch reads it. The verdict may
    be shown to Julian and may be logged; it may never be tested by anything that decides."""
    import pathlib, re
    root = pathlib.Path(__file__).resolve().parent.parent
    # Only real FIELD ACCESS counts — .delivers, ["delivers"], .get("delivers"). The bare
    # English word appears all over this codebase's prose ("what AnyFilm delivers", "a prompt
    # delivers that through the staging"); a first draft of this test matched those and
    # reported six comments as gates.
    access = re.compile(r"""(\.delivers\b|\[\s*['"]delivers['"]\s*\]|get\(\s*['"]delivers['"])""")
    offenders = []

    # THE ENGINE: no control flow on the verdict AT ALL. This is where a gate would actually
    # bite — refusing a prepare, refusing a fire, withholding a spend token — so the rule here
    # is absolute, not a judgement call.
    decides = re.compile(r"\b(if|elif|while|assert|raise|return)\b|[=!]=")
    for f in root.glob("engine/*.py"):
        if f.name in ("cb_readback.py", "test_cb_readback.py"):
            continue          # the reader defines the field; its own test asserts on it
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if access.search(line) and decides.search(line):
                offenders.append(f"ENGINE {f.name}:{i}: {line.strip()[:100]}")

    # THE STUDIO: the verdict is SHOWN, so it necessarily picks a label, a glyph and a border
    # colour — that is the whole point of showing it, not a gate, and an earlier draft of this
    # test wrongly reported exactly those two lines. What it may never do is take an action
    # away. This scopes to that: never near `disabled`, never deciding what goes in an
    # actions array.
    takes_away = re.compile(r"\bdisabled\b|\bactions\s*[:=]|\bacts\s*=")
    for f in list(root.glob("cb-studio/*.html")) + list(root.glob("cb-studio/*.py")):
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if access.search(line) and takes_away.search(line):
                offenders.append(f"STUDIO {f.name}:{i}: {line.strip()[:100]}")

    assert not offenders, (
        "the eyes' recommendation now decides something — that makes it a gate, and rule 87 "
        "is unambiguous that a gate is not the answer here:\n  " + "\n  ".join(offenders))


def test_approve_is_built_without_ever_consulting_the_eyes():
    """The positive form of the rule above, and the one that actually protects Julian: the
    Approve/Reject controls must be constructed from the department record alone. If the
    verdict cannot reach them, it cannot withhold them, whatever anyone adds later."""
    import pathlib
    app = (pathlib.Path(__file__).resolve().parent.parent
           / "cb-studio" / "app.html").read_text(encoding="utf-8")
    block = app[app.index("function authBlockHTML("):app.index("\n// THE VISIBLE REFERENCE")]
    approve = [l for l in block.splitlines() if "shApproveStageAll" in l or "deptDecide" in l]
    assert approve, "the approve/reject controls moved — this test no longer guards anything"
    for line in approve:
        assert "readback" not in line.lower() and "delivers" not in line, (
            f"an approval control is now built from the reading: {line.strip()[:110]}")


def test_an_unreachable_model_blocks_nothing(monkeypatch):
    """It must never be the reason Julian cannot get on with his morning."""
    monkeypatch.setattr(cb_llm, "structured",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("provider down")))
    assert R.read_back("anything", log=lambda *a: None) is None
    assert "blocked" in R.as_plain_text(None).lower()


def test_a_clean_brief_is_allowed_to_be_clean():
    """The worst failure mode of an advisory is inventing findings to look useful — it
    teaches the director to ignore it. An empty list must read as good news."""
    rb = R.ReadBack(shot_says="A wide corridor with a small bee climbing away.", clashes=[],
                    delivers="delivers", verdict="Fire it — it starts where your frame does.")
    out = R.as_plain_text(rb)
    assert "fights itself" in out
    assert "cannot both happen" not in out


def test_the_prompt_carries_both_real_failures_as_examples():
    """This is the load-bearing part. The reader is only reliable because it has been shown
    the two ACTUAL contradictions from 2026-07-27 — the 24mm-versus-specular-ping one, and
    the match-100%-versus-one-sixth-of-frame-height one. Strip the worked examples and it is
    a generic 'look for problems' prompt, which finds imaginary ones."""
    s = R._SYSTEM
    assert "24mm" in s and "specular" in s, "the lens-versus-detail failure is no longer shown"
    assert "100%" in s and "one-sixth" in s, "the identity-versus-scale failure is no longer shown"
    assert "each clause is perfectly reasonable alone" in s.lower(), (
        "the reader is no longer told WHY a lint cannot catch this — it will drift back into "
        "matching words")
    assert "empty list" in s.lower(), "nothing tells it that finding nothing is a good answer"


def test_it_names_which_instruction_wins(monkeypatch):
    """A contradiction the director cannot act on is just anxiety. Every finding has to say
    which clause the render will actually obey, and what he will see because of it."""
    for f in ("first", "second", "why", "wins", "cost"):
        assert f in R.Clash.model_fields, f"a finding no longer says {f!r}"
    rb = R.ReadBack(shot_says="x", delivers="will-not",
                    verdict="Don't fire this — you will get a portrait, not the corridor.",
                    clashes=[R.Clash(
        first="match 100%", second="one-sixth of frame height",
        why="A sixth-height figure has no room for features.",
        wins="The identity clause — absolute beats hedged.",
        cost="A big front-on bee instead of a corridor.")])
    out = R.as_plain_text(rb)
    assert "will obey" in out and "you will see" in out
