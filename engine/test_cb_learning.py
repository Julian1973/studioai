#!/usr/bin/env python3
"""test_cb_learning.py — THE CREATIVE LEARNING SYSTEM's governance proofs (2026-07-17).
These prove the three-store separation, evidence immutability, source-first promotion,
never-silent activation and scoped retrieval — never that any lesson is creatively right.

    pytest test_cb_learning.py -q
"""
import json
import pathlib
import sys
import tempfile

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cb_learning as L


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    """Every test runs against its own tempdir stores — the REAL libraries are never
    touched by tests."""
    d = pathlib.Path(tempfile.mkdtemp())
    monkeypatch.setattr(L, "LEARNING", d)
    monkeypatch.setattr(L, "EVIDENCE_P", d / "EVIDENCE_LIBRARY.json")
    monkeypatch.setattr(L, "PATTERNS_P", d / "PATTERN_LIBRARY.json")
    monkeypatch.setattr(L, "ACTIVE_P", d / "ACTIVE_CREATIVE_MEMORY.json")
    yield d


def _ev(outcome="rejected", feedback="too safe", **kw):
    return L.capture_evidence(outcome, feedback, scene="1", category=kw.pop("category", "creative"),
                               classification=kw.pop("classification", "test"), **kw)


# ── the three stores are separate; evidence is immutable and complete ───────────────────
def test_three_stores_are_separate_files(isolated):
    _ev()
    L.propose_pattern("x", supportingEvidence=["ev-1"], proposedSource="director canon")
    assert L.EVIDENCE_P.exists() and L.PATTERNS_P.exists()
    assert not L.ACTIVE_P.exists()                       # nothing active until a human acts
    assert "IMMUTABLE" in json.load(open(L.EVIDENCE_P))["note"]
    assert "Proposals only" in json.load(open(L.PATTERNS_P))["note"]


def test_evidence_preserves_asset_decision_context_and_exact_words(isolated):
    r = _ev(feedback="the camera watched from safety", assetPointers=["media/x.mp4"],
            context="scene 1 take 2")
    got = L.evidence(r["evidenceId"])
    assert got["userFeedbackVerbatim"] == "the camera watched from safety"   # exact words
    assert got["assetPointers"] == ["media/x.mp4"]       # the asset, not only a lesson
    assert got["context"] == "scene 1 take 2"
    for field in ("evidenceId", "project", "show", "episode", "scene", "sourceVersion",
                   "creativeRole", "outcome", "systemClassification", "category", "scope"):
        assert field in got                              # the full classification contract


def test_evidence_api_is_append_only(isolated):
    _ev()
    assert not any(n.startswith(("edit", "update", "delete", "mutate"))
                    for n in dir(L) if callable(getattr(L, n)))
    with pytest.raises(ValueError):
        L.capture_evidence("liked-it")                   # outcomes are the closed set


# ── promotion: source-first, never silent, never one random provider failure ───────────
def test_promotion_refuses_without_named_source(isolated):
    e = _ev()
    p = L.propose_pattern("cameras should discover action",
                           supportingEvidence=[e["evidenceId"]], proposedSource=None)
    with pytest.raises(L.PromotionRefused, match="insufficiently understood"):
        L.promote(p["patternId"], by="Julian", explicit_user_decision="do it")
    assert L.active_memory() == []


def test_one_random_provider_failure_never_becomes_a_rule(isolated):
    e = _ev(outcome="model-limited", category="provider")
    p = L.propose_pattern("the provider always fails at X",
                           supportingEvidence=[e["evidenceId"]],
                           proposedSource="provider capability profile")
    with pytest.raises(L.PromotionRefused, match="one random provider failure"):
        L.promote(p["patternId"], by="Julian")


def test_promotion_requires_regression_or_explicit_user_decision(isolated):
    e1, e2 = _ev(), _ev(feedback="same again")
    p = L.propose_pattern("repeated safe coverage",
                           supportingEvidence=[e1["evidenceId"], e2["evidenceId"]],
                           proposedSource="cinematography canon")
    with pytest.raises(L.PromotionRefused, match="regression"):
        L.promote(p["patternId"], by="Julian")           # repetition alone is not enough
    L.record_regression(p["patternId"], comparison="anchor suite old-vs-new summary",
                         human_approved=True, by="Julian")
    rec = L.promote(p["patternId"], by="Julian")
    assert rec["activationVersion"] and rec["rollback"]["how"]      # reversible, versioned
    assert L.patterns(p["patternId"])["maturity"] == "approved-principle"


def test_explicit_user_decision_outranks_repetition_count(isolated):
    e = _ev(feedback="this is now how we work")
    p = L.propose_pattern("treatment before beats",
                           supportingEvidence=[e["evidenceId"]],
                           proposedSource="creative-room workflow")
    rec = L.promote(p["patternId"], by="Julian",
                     explicit_user_decision="Replace the creative-room process (directive)")
    assert rec["explicitUserDecision"].startswith("Replace")
    assert len(L.active_memory()) == 1                   # one explicit decision suffices


# ── human interface: feedback captured, classification proposed, promotion separate ────
def test_human_feedback_shows_everything_and_promotes_nothing(isolated):
    out = L.human_feedback("reject", "the quiet scene had too many shots", scene="2")
    assert out["evidenceCaptured"]["evidenceId"]
    assert out["lessonInferred"] and out["proposedScope"] == "scene"
    assert "NOT promoted" in out["promotion"]            # never silent
    assert L.active_memory() == []


# ── retrieval: scoped, labelled, small — never the whole library ────────────────────────
def test_retrieval_is_scoped_labelled_and_capped(isolated):
    for i in range(30):
        _ev(feedback=f"note {i}")
    e = _ev(outcome="approved", feedback="this one sang")
    p = L.propose_pattern("voice pauses carry meaning", supportingEvidence=[e["evidenceId"]],
                           proposedSource="voice director canon")
    L.promote(p["patternId"], by="Julian", explicit_user_decision="promote it")
    text = L.retrieve_for_role("VOICE DIRECTOR")
    assert len(text) <= 2600                             # never an instruction wall
    assert "APPROVED CREATIVE PREFERENCES" in text and "voice pauses carry meaning" in text
    assert "UNRESOLVED OBSERVATIONS" in text or "CONTEXTUAL EXEMPLARS" in text
    assert "CANON TRUTH" in text                         # the five categories distinguished
    director = L.retrieve_for_role("DIRECTOR")
    assert "voice pauses carry meaning" not in director  # role-scoped lanes


def test_provider_evidence_kept_separate_from_taste(isolated):
    _ev(outcome="model-limited", category="provider",
        classification="two motion signals confuse the model")
    text = L.retrieve_for_role("SHOWRUNNER")
    assert "PROVIDER LIMITATION" in text                 # capability, labelled apart


# ── prompts stay immutable; no provider access ───────────────────────────────────────────
def test_learning_never_touches_prompts_or_providers():
    src = (HERE / "cb_learning.py").read_text()
    assert "import cb_gen" not in src and "import cb_render" not in src
    assert "import cb_engine" not in src
    assert "seedancePrompt" not in src                   # never appends to a compiled prompt
    assert "manualProviderPromptEdits" in src            # tracked, must remain zero


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
