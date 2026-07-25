#!/usr/bin/env python3
"""test_cb_formulas.py — THE FORMULA LIBRARY + THE VERDICT CORPUS (2026-07-25).

These pin down the two disciplines the product depends on:

  1. A formula proven on one kind of material NEVER reaches a different kind. The whole
     value of the library is that SH1's physical-comedy spend does not teach a quiet
     interior beat to fill stillness with impacts.
  2. Every real fire and every human verdict lands in an append-only corpus, because the
     pairing is the asset a new formula is derived from.

Zero provider calls: the corpus is a file, and formula resolution is pure string work.
"""
import json
import os
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cb_corpus
import cb_formulas as F


# ── THE LIBRARY ────────────────────────────────────────────────────────────────────────
def test_the_proven_formula_reaches_only_its_own_material():
    """The load-bearing guarantee. SH1 is a physical-comedy/action-chain formula."""
    body, meta = F.formula_block("physical comedy, escalating")
    assert meta["formKey"] == "physical_comedy" and meta["exemplar"]
    exemplar = (F.CRAFT_DIR / meta["exemplar"]).read_text(encoding="utf-8")
    probe = [l.strip() for l in exemplar.splitlines() if len(l.strip()) > 60][3]
    assert probe in body, "the proven formula did not reach the form it was proven on"

    for other in ("a quiet held realisation", "two-hander dialogue exchange",
                  "a transition that carries us onward", "wonder, the world at scale"):
        body, meta = F.formula_block(other)
        assert meta["exemplar"] is None, f"an exemplar leaked to {other!r}"
        assert probe not in body, f"SH1's body leaked into {other!r} — the wrong lesson"


def test_an_unmatched_or_ambiguous_form_gets_no_exemplar_rather_than_a_guess():
    """The conservative direction: a missing exemplar costs one exploratory take; a wrong
    one silently teaches the wrong shape on every future beat of that form."""
    _, meta = F.formula_block("something the director invented")
    assert (meta["formKey"], meta["confidence"]) == (None, "none")

    # a near-tie must refuse, not pick the higher raw hit count (caught live: two generic
    # words out-voting one specific two-word phrase)
    _, meta = F.formula_block("physical comedy dialogue exchange")
    assert meta["formKey"] is None and meta["confidence"] == "weak"
    assert "refusing to guess" in meta["why"]


def test_a_form_with_no_formula_is_told_it_is_discovering_one():
    body, meta = F.formula_block("a quiet interior realisation, held")
    assert meta["status"] == "missing"
    assert "DISCOVERY" in body and "NO PROVEN FORMULA" in body
    assert "becomes this form's formula" in body, \
        "the writer is not told its take can become the formula — the loop never closes"


def test_registry_never_claims_proven_without_evidence():
    for key, e in F.load_registry()["forms"].items():
        if e.get("status") == "proven":
            assert e.get("exemplar") and e.get("provenTake") and e.get("provenBy"), \
                f"{key} claims proven with no exemplar/take/evidence named"
            assert (F.CRAFT_DIR / e["exemplar"]).exists(), \
                f"{key}'s exemplar file is missing from disk"
        else:
            assert not e.get("exemplar"), f"{key} is unproven but carries an exemplar"


def test_a_proven_entry_whose_file_vanished_degrades_loudly_not_silently(monkeypatch):
    monkeypatch.setattr(F, "load_registry", lambda: {"forms": {"physical_comedy": {
        "status": "proven", "label": "x", "exemplar": "NOT_ON_DISK.txt",
        "provenTake": "S1.SH1", "provenBy": "test"}}})
    body, meta = F.formula_block("physical comedy")
    assert meta["status"] == "proven-but-missing-file" and meta["exemplar"] is None
    assert "NO EXEMPLAR SUPPLIED" in body


def test_the_writer_only_receives_the_matching_formula():
    """End to end through the REAL curriculum loader the animation writer actually uses."""
    import cb_departments as D
    exemplar = (F.CRAFT_DIR / "SH1_KEEPER_EXEMPLAR.txt").read_text(encoding="utf-8")
    probe = [l.strip() for l in exemplar.splitlines() if len(l.strip()) > 60][3]
    hit, _ = D._craft_curriculum("physical comedy, escalating")
    miss, _ = D._craft_curriculum("a quiet held realisation")
    assert probe in hit and probe not in miss
    for text in (hit, miss):                    # the LAWS reach both, always
        assert "PROMPT_CRAFT_STANDARD.md" in text


# ── THE CORPUS ─────────────────────────────────────────────────────────────────────────
def _isolated(monkeypatch, tmp):
    """Point the corpus at a scratch dir via the SAME env override conftest.py uses — the
    real mechanism, not a monkeypatched constant, so these tests also prove the override
    actually works."""
    monkeypatch.setenv("CB_CORPUS_DIR", str(tmp))


def test_a_fire_and_its_verdict_pair_up(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        _isolated(monkeypatch, tmp)
        ref = pathlib.Path(tmp) / "ref.png"
        ref.write_bytes(b"pixels")
        fid = cb_corpus.record_fire(
            episode="Ep1", scene=1, shot_id="S1.SH1", prompt="a real prompt",
            refs=[{"role": "@图1", "path": str(ref)}], provider="byteplus",
            model="dreamina-seedance-2-0", resolution="480p", candidates=2,
            formula={"formKey": "physical_comedy", "exemplar": "SH1_KEEPER_EXEMPLAR.txt"})
        assert fid
        cb_corpus.record_verdict(shot_id="S1.SH1", kept=False,
                                 verdict="the crash feels rushed and the pace is slow")

        [rec] = cb_corpus.judged()
        assert rec["promptSha"] and rec["refs"][0]["sha"], "content was not hashed"
        assert rec["verdict"]["kept"] is False
        assert "crash feels rushed" in rec["verdict"]["verdict"]
        assert rec["verdict"]["fireId"] == fid, "the verdict did not attach to its fire"


def test_for_form_returns_the_evidence_a_new_formula_is_derived_from(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        _isolated(monkeypatch, tmp)
        for i, (form, kept, words) in enumerate([
                ("quiet_emotion", False, "too busy, she never settles"),
                ("quiet_emotion", True, "that's the one — the pause carries it"),
                ("physical_comedy", True, "lands")], 1):
            cb_corpus.record_fire(episode="Ep1", scene=1, shot_id=f"S1.SH{i}",
                                  prompt=f"prompt {i}", formula={"formKey": form})
            cb_corpus.record_verdict(shot_id=f"S1.SH{i}", kept=kept, verdict=words)
        quiet = cb_corpus.for_form("quiet_emotion")
        assert len(quiet) == 2
        assert [q["verdict"]["kept"] for q in quiet] == [False, True]
        assert "pause carries it" in quiet[1]["verdict"]["verdict"]


def test_the_corpus_is_append_only(monkeypatch):
    """A corpus you can edit is a corpus you can flatter. A re-review appends; the
    original fire and the original verdict both survive on disk."""
    with tempfile.TemporaryDirectory() as tmp:
        _isolated(monkeypatch, tmp)
        cb_corpus.record_fire(episode="Ep1", scene=1, shot_id="S1.SH1", prompt="p")
        cb_corpus.record_verdict(shot_id="S1.SH1", kept=False, verdict="not great")
        cb_corpus.record_verdict(shot_id="S1.SH1", kept=True, verdict="actually, keep it")
        raw = cb_corpus.read_all()
        assert len(raw) == 3, "a record was overwritten instead of appended"
        assert [r["kind"] for r in raw] == ["fire", "verdict", "verdict"]
        assert cb_corpus.judged()[0]["verdict"]["kept"] is True   # latest wins for reading


def test_recording_never_breaks_the_thing_it_observes(monkeypatch):
    """Evidence-keeping must not be able to fail a real, paid fire."""
    monkeypatch.setattr(cb_corpus, "_append",
                        lambda rec: (_ for _ in ()).throw(OSError("disk full")))
    assert cb_corpus.record_fire(episode="Ep1", scene=1, shot_id="X", prompt="p") is None
    assert cb_corpus.record_verdict(shot_id="X", kept=True, verdict="fine") is None


def test_a_corrupt_line_never_hides_the_rest(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        _isolated(monkeypatch, tmp)
        cb_corpus.record_fire(episode="Ep1", scene=1, shot_id="S1.SH1", prompt="p")
        with (pathlib.Path(tmp) / "fires.jsonl").open("a") as fh:
            fh.write("{not json at all\n")
        cb_corpus.record_fire(episode="Ep1", scene=1, shot_id="S1.SH2", prompt="q")
        assert len(cb_corpus.read_all()) == 2
