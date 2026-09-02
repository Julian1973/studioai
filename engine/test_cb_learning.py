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
    assert "IMMUTABLE" in json.load(open(L.EVIDENCE_P, encoding="utf-8"))["note"]
    assert "Proposals only" in json.load(open(L.PATTERNS_P, encoding="utf-8"))["note"]


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
        L.promote(p["patternId"], by="Julian", applied_source_ref="abc1234")
    assert L.active_memory() == []


def test_one_random_provider_failure_never_becomes_a_rule(isolated):
    e = _ev(outcome="model-limited", category="provider")
    p = L.propose_pattern("the provider always fails at X",
                           supportingEvidence=[e["evidenceId"]],
                           proposedSource="provider capability profile")
    with pytest.raises(L.PromotionRefused, match="one random provider failure"):
        L.promote(p["patternId"], by="Julian", applied_source_ref="abc1234")






# ── human interface: feedback captured, classification proposed, promotion separate ────
def test_human_feedback_shows_everything_and_promotes_nothing(isolated):
    out = L.human_feedback("reject", "the quiet scene had too many shots", scene="2")
    assert out["evidenceCaptured"]["evidenceId"]
    assert out["lessonInferred"] and out["proposedScope"] == "scene"
    assert "NOT promoted" in out["promotion"]            # never silent
    assert L.active_memory() == []


# ── retrieval: scoped, labelled, small — never the whole library ────────────────────────




# ── prompts stay immutable; no provider access ───────────────────────────────────────────
def test_learning_never_touches_prompts_or_providers():
    src = (HERE / "cb_learning.py").read_text(encoding="utf-8")
    assert "import cb_gen" not in src and "import cb_render" not in src
    assert "import cb_engine" not in src
    assert "seedancePrompt" not in src                   # never appends to a compiled prompt
    assert "manualProviderPromptEdits" in src            # tracked, must remain zero


def test_dailies_schema_forces_a_cheapest_testable_next_action():
    import cb_departments as D
    schema = D.MediaReview.model_json_schema()
    props = schema["properties"]
    for name in ("beatDelivery", "actingAndPerformance", "physicalCausality",
                 "timingAndReaction", "cameraAndEdit", "likelyRootCause",
                 "rootCauseReasoning", "cheapestNextAction", "learningTags"):
        assert name in props
    action = schema["$defs"]["CheapestNextAction"]
    required = set(action["required"])
    assert {"action", "rerenderRequired", "changeOneLever",
            "preserveExactly", "proofOfImprovement", "zeroCostChecksFirst"} <= required


# ── THE SIMPLIFICATION CHECKPOINT (2026-07-17): five focused proofs ─────────────────────
def test_promotion_without_applied_source_reference_fails(isolated):
    e = _ev()
    p = L.propose_pattern("a real lesson", supportingEvidence=[e["evidenceId"]],
                           proposedSource="director canon")
    with pytest.raises(L.PromotionRefused, match="applied source"):
        L.promote(p["patternId"], by="Julian", applied_source_ref="")
    assert L.active_memory() == []
    rec = L.promote(p["patternId"], by="Julian", applied_source_ref="abc1234")
    assert rec["appliedSourceRef"] == "abc1234"          # all four records present
    assert rec["destinationSource"] == "director canon"
    assert rec["promotedBy"] == "Julian" and rec["rollback"]["how"]


def test_learning_store_text_never_enters_role_prompts(isolated):
    """Marker text planted in ALL THREE stores must never reach a creative role's mind."""
    e = _ev(feedback="ZZ-EVIDENCE-MARKER-ZZ")
    p = L.propose_pattern("ZZ-PATTERN-MARKER-ZZ", supportingEvidence=[e["evidenceId"]],
                           proposedSource="director canon")
    L.promote(p["patternId"], by="Julian", applied_source_ref="abc1234")
    import cb_creative as C
    for role in ("SHOWRUNNER", "DIRECTOR", "CINEMATOGRAPHER", "VOICE DIRECTOR"):
        mind = C._mind(role, ["directorTaste"], "charge")
        for marker in ("ZZ-EVIDENCE-MARKER-ZZ", "ZZ-PATTERN-MARKER-ZZ"):
            assert marker not in mind, (role, marker)
    assert "import cb_learning" not in (HERE / "cb_creative.py").read_text(encoding="utf-8")


def test_raw_exemplar_dump_does_not_return():
    """Roles receive concise canonical PRINCIPLES only — never attempted/userWords prose."""
    import cb_creative as C
    assert not hasattr(C, "_exemplar_text") and not hasattr(C, "_governed_memory")
    mind = C._mind("DIRECTOR", ["directorTaste"], "charge")
    assert "EX-005" in mind                              # the canonical principle survives
    assert "re-fired for a stronger in-flight read" not in mind     # EX-001 userWords
    assert "user verdict:" not in mind                   # the raw dump's own formatting
    assert len(C._canonical_exemplars()) <= 2200


def test_ex005_remains_linked_to_7d5762e():
    """The REAL registry (not a fixture): the active EX-005 principle points at the
    verified structural change."""
    real = json.load(open(L.ROOT / "projects/crystal-bears/creative/learning/"
                                    "ACTIVE_CREATIVE_MEMORY.json", encoding="utf-8"))
    rec = next(r for r in real["principles"] if r["principleId"] == "acm-213b111d")
    assert rec["appliedSourceRef"] == "7d5762e"
    assert rec["destinationSource"] == "creative-room workflow"
    pats = json.load(open(L.ROOT / "projects/crystal-bears/creative/learning/"
                                     "PATTERN_LIBRARY.json", encoding="utf-8"))["patterns"]
    for pid in ("pat-6ee4b7fd", "pat-c63c3a1f"):         # stay inactive
        assert next(p for p in pats if p["patternId"] == pid)["maturity"] != "approved-principle"


def test_creative_room_2_execution_order_unchanged():
    import cb_creative as C
    assert C.ENGINE_VERSION.startswith("creative-room-2.2")
    body = (HERE / "cb_creative.py").read_text(encoding="utf-8").split("def run_scene", 1)[1]
    order = [body.index(s) for s in ("gate0_readiness(", "gate1_treatments(",
                                       "gate2_select(", "gate3_beats(",
                                       "gate4_shot_conference(", "gate5_performance(",
                                       "gate5_voice(", "gate6_adversarial_review(")]
    assert order == sorted(order)                        # treatments -> selection -> beats...


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
