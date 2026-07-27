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
    assert "score" not in R.ReadBack.model_fields, "a score would make it a judge"
    assert "verdict" not in R.ReadBack.model_fields
    assert "passes" not in R.ReadBack.model_fields


def test_an_unreachable_model_blocks_nothing(monkeypatch):
    """It must never be the reason Julian cannot get on with his morning."""
    monkeypatch.setattr(cb_llm, "structured",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("provider down")))
    assert R.read_back("anything", log=lambda *a: None) is None
    assert "blocked" in R.as_plain_text(None).lower()


def test_a_clean_brief_is_allowed_to_be_clean():
    """The worst failure mode of an advisory is inventing findings to look useful — it
    teaches the director to ignore it. An empty list must read as good news."""
    rb = R.ReadBack(shot_says="A wide corridor with a small bee climbing away.", clashes=[])
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
    rb = R.ReadBack(shot_says="x", clashes=[R.Clash(
        first="match 100%", second="one-sixth of frame height",
        why="A sixth-height figure has no room for features.",
        wins="The identity clause — absolute beats hedged.",
        cost="A big front-on bee instead of a corridor.")])
    out = R.as_plain_text(rb)
    assert "will obey" in out and "you will see" in out
