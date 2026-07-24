#!/usr/bin/env python3
"""test_cb_render_legacy_revalidation.py — Julian's 2026-07-20 bounded legacy-approval
revalidation directive, completed the same day by his own FINAL COMPLETION DIRECTIVE
("The claim that a 'genuinely consumed input changed' is not proven: the legacy record has
no field-level tracking and therefore cannot distinguish an actual upstream-input change
from a signature-formula or dependency-scope change"). Proves an EXISTING, human-approved,
content-unchanged Cinematography Direction can be re-bound to the corrected dependency-graph
formula (_DEPT_SIGNATURE_VERSION 3) using SEALED KEYFRAME EVIDENCE — never a reconstructed
legacy-formula hash — with ZERO LLM/provider/media calls, while genuine drift (a real
consumed-input change, or direct output tampering) is correctly refused with the EXACT
mismatching file/prompt/field named. Also proves the five dependency-boundary conditions the
same directive names.

Reuses test_cb_render_department_gate.py's own `world` fixture and real-route seed helpers
(_mock_llm/_seed_voice/_seed_keyframe_anchor/_seed_animation_prereqs) — no hand-edited
ledger JSON stands in for a real approval; only the disposable test package's OWN file
content is ever mutated directly, and only to simulate (a) a pre-2026-07-20 approval record
that predates signatureVersion/sourceFields/outputHash entirely, or (b) a genuine external
change to a real input file — never anything cb_render.py's own real routes wouldn't
otherwise produce.

    pytest test_cb_render_legacy_revalidation.py -q
"""
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cb_render as R
from test_cb_render_department_gate import (
    world, _mock_llm, _seed_voice, _seed_keyframe_anchor, _seed_animation_prereqs,
)


def _load_approved(path, shot_id, stage):
    pkg = json.load(open(path))
    led = next(l for l in pkg["continuityLedger"] if l["shotId"] == shot_id)
    return led["departmentWork"][stage]["approved"], pkg


def _strip_signature_version(path, shot_id="1.B1.S1", stage="cinematography",
                             also_strip_output_tracking=True):
    """Simulates a pre-2026-07-20 approval. Every approval this session's OWN fix creates
    already carries signatureVersion/sourceFields/outputHash; every approval that predates
    it — including the real, live production package's own current Cinematography approval
    at the moment this directive was given — has none of these fields at all. Stripping
    them here reproduces that exact real-world starting state on disposable test data.
    also_strip_output_tracking=False keeps outputHash (simulating a record whose version
    field is missing but which still has a real output baseline to check tampering
    against — see test_prompt_tampering_cannot_be_revalidated's own reasoning)."""
    pkg = json.load(open(path))
    led = next(l for l in pkg["continuityLedger"] if l["shotId"] == shot_id)
    approved = led["departmentWork"][stage]["approved"]
    approved.pop("signatureVersion", None)
    if also_strip_output_tracking:
        approved.pop("sourceFields", None)
        approved.pop("outputHash", None)
    json.dump(pkg, open(path, "w"))


# ── 1: a legacy approval can be revalidated without rerunning a specialist ──────────────
def test_legacy_approval_can_be_revalidated_without_rerunning_specialist(world, monkeypatch):
    calls, tmp, path = world
    _seed_keyframe_anchor(monkeypatch, path)
    _strip_signature_version(path)
    # _seed_keyframe_anchor itself fires the mocked provider once (a real keyframe to
    # approve) — snapshot AFTER seeding so the assertions below prove revalidation adds
    # zero NEW calls, not that no call was ever made in this test at all.
    calls_before = {k: len(v) for k, v in calls.items()}

    pkg = json.load(open(path))
    status = R.department_legacy_status(pkg, "9", "cinematography", "1.B1.S1", "EpT")
    assert status["eligible"] is True, status["reason"]
    assert status["approvedSignatureVersion"] is None, "a legacy record has no version stamp at all"
    assert status["currentSignatureVersion"] == R._DEPT_SIGNATURE_VERSION
    assert "Sealed keyframe evidence confirms" in status["reason"]
    assert "reviewed by Julian" in status["reason"]

    orig_approved, _ = _load_approved(path, "1.B1.S1", "cinematography")
    orig_decision_at = orig_approved["decisionAt"]
    orig_reviewed_by = orig_approved["reviewedBy"]
    orig_output = json.loads(json.dumps(orig_approved["output"]))  # deep copy for comparison

    event = R.revalidate_department("9", "cinematography", "1.B1.S1", "EpT",
                                    reviewed_by="Julian", log=lambda *a, **k: None)
    assert event["newSignatureVersion"] == R._DEPT_SIGNATURE_VERSION
    assert event["oldSignatureVersion"] is None

    approved, updated_pkg = _load_approved(path, "1.B1.S1", "cinematography")
    assert approved["signatureVersion"] == R._DEPT_SIGNATURE_VERSION
    assert approved["decisionAt"] == orig_decision_at, "the original approval timestamp must survive"
    assert approved["reviewedBy"] == orig_reviewed_by, "the original reviewer must survive"
    assert approved["output"] == orig_output, "revalidation must never touch the approved content"

    fresh = R.department_freshness(updated_pkg, "9", "cinematography", "1.B1.S1", "EpT")
    assert fresh["current"] is True, "a revalidated approval must now read as fully current"
    assert {k: len(v) for k, v in calls.items()} == calls_before, \
        "revalidation must add zero NEW provider calls"

    led = next(l for l in updated_pkg["continuityLedger"] if l["shotId"] == "1.B1.S1")
    revals = led["departmentWork"]["cinematography"].get("revalidations") or []
    assert len(revals) == 1
    assert revals[0]["reviewedBy"] == "Julian"
    assert revals[0]["newSignatureVersion"] == R._DEPT_SIGNATURE_VERSION


# ── 2: prompt tampering cannot be revalidated ───────────────────────────────────────────
def test_prompt_tampering_cannot_be_revalidated(world, monkeypatch):
    calls, tmp, path = world
    _seed_keyframe_anchor(monkeypatch, path)
    # Keep outputHash (a real baseline to check against) — only the version field is
    # missing, simulating a record from partway through this feature's own rollout.
    _strip_signature_version(path, also_strip_output_tracking=False)
    calls_before = {k: len(v) for k, v in calls.items()}

    approved, pkg = _load_approved(path, "1.B1.S1", "cinematography")
    approved["output"]["providerPrompt"] = "a tampered prompt that was never actually approved"
    json.dump(pkg, open(path, "w"))

    pkg2 = json.load(open(path))
    status = R.department_legacy_status(pkg2, "9", "cinematography", "1.B1.S1", "EpT")
    assert status["eligible"] is False
    assert "output content itself has changed" in status["reason"]
    with pytest.raises(R.Refused, match="revalidation refused"):
        R.revalidate_department("9", "cinematography", "1.B1.S1", "EpT",
                                log=lambda *a, **k: None)
    assert {k: len(v) for k, v in calls.items()} == calls_before, \
        "a refused revalidation must add zero NEW provider calls"


# ── 3: a real consumed-input change cannot be revalidated, and IS named exactly — sealed
# keyframe evidence names the exact mismatching file, even on a TRUE legacy record (no
# sourceFields/outputHash at all) — the whole point of Julian's FINAL COMPLETION DIRECTIVE
# correction: a reconstructed legacy-formula hash could never prove or name this for a
# record that predates field-level tracking; sealed evidence is an INDEPENDENT source (the
# keyframe's own generation-time signature) and needs no sourceFields to name the field.
def test_real_consumed_input_change_cannot_be_revalidated(world, monkeypatch):
    calls, tmp, path = world
    _seed_keyframe_anchor(monkeypatch, path)
    _strip_signature_version(path)  # true legacy: no sourceFields/outputHash either
    calls_before = {k: len(v) for k, v in calls.items()}

    # A REAL input Cinematography actually consumes: the underlying reference image's own
    # bytes (content-hash based — same path, genuinely different content).
    ref_path = tmp / "engine" / "media" / "refs" / "CB_Fuzzby.jpeg"
    ref_path.write_bytes(b"COMPLETELY DIFFERENT REFERENCE IMAGE CONTENT")

    pkg = json.load(open(path))
    status = R.department_legacy_status(pkg, "9", "cinematography", "1.B1.S1", "EpT")
    assert status["eligible"] is False
    assert "sealed evidence shows a genuine change" in status["reason"]
    assert status["changedField"], (
        "sealed keyframe evidence names the exact mismatching field even on a true legacy "
        "record — it never needs the record's own sourceFields breakdown to do so")
    assert "referenceFiles" in status["changedField"]
    assert "CB_Fuzzby.jpeg" in status["reason"] or "referenceFiles" in status["reason"]
    with pytest.raises(R.Refused, match="revalidation refused"):
        R.revalidate_department("9", "cinematography", "1.B1.S1", "EpT",
                                log=lambda *a, **k: None)
    assert {k: len(v) for k, v in calls.items()} == calls_before, \
        "a refused revalidation must add zero NEW provider calls"


# ── 3b: the identical real input change, with sourceFields present too — same result, since
# sealed evidence (not sourceFields) is what actually names the field ───────────────────────
def test_real_consumed_input_change_names_the_changed_field_when_trackable(world, monkeypatch):
    calls, tmp, path = world
    _seed_keyframe_anchor(monkeypatch, path)
    # Keep sourceFields (this record was written by the fixed code, so it has one) — only
    # strip the version stamp.
    _strip_signature_version(path, also_strip_output_tracking=False)

    ref_path = tmp / "engine" / "media" / "refs" / "CB_Fuzzby.jpeg"
    ref_path.write_bytes(b"COMPLETELY DIFFERENT REFERENCE IMAGE CONTENT")

    pkg = json.load(open(path))
    status = R.department_legacy_status(pkg, "9", "cinematography", "1.B1.S1", "EpT")
    assert status["eligible"] is False
    assert status["changedField"], "sealed evidence must name the changed key"
    assert "referenceFiles" in status["changedField"], (
        f"expected the reference-image field to be named; got {status['changedField']!r}")


# ── 4: revalidation makes zero external calls (repeated explicitly, per the directive) ──
def test_revalidation_makes_zero_external_calls(world, monkeypatch):
    calls, tmp, path = world
    _seed_keyframe_anchor(monkeypatch, path)
    _strip_signature_version(path)
    calls_before = {k: len(v) for k, v in calls.items()}
    R.revalidate_department("9", "cinematography", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    assert {k: len(v) for k, v in calls.items()} == calls_before


# ── 5: history remains intact (repeated explicitly, per the directive) ─────────────────
def test_revalidation_history_remains_intact(world, monkeypatch):
    calls, tmp, path = world
    _seed_keyframe_anchor(monkeypatch, path)
    before, _ = _load_approved(path, "1.B1.S1", "cinematography")
    before_full = json.loads(json.dumps(before))
    _strip_signature_version(path)
    R.revalidate_department("9", "cinematography", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    after, pkg = _load_approved(path, "1.B1.S1", "cinematography")
    for key in ("decisionAt", "reviewedBy", "note", "outcome", "output", "preparedAt",
               "preparedBy", "shotId", "scene", "department", "worker"):
        assert after.get(key) == before_full.get(key), f"{key} must survive revalidation unchanged"
    led = next(l for l in pkg["continuityLedger"] if l["shotId"] == "1.B1.S1")
    assert led["departmentWork"]["cinematography"]["history"] == [], \
        "revalidation is not a supersession — the normal history list stays untouched"


# ── 6a: approving Voice does not stale Cinematography (dependency boundary) ─────────────
def test_boundary_approving_voice_does_not_stale_cinematography(world, monkeypatch):
    calls, tmp, path = world
    _seed_keyframe_anchor(monkeypatch, path)
    pkg = json.load(open(path))
    assert R.department_freshness(pkg, "9", "cinematography", "1.B1.S1", "EpT")["current"] is True
    _seed_voice(monkeypatch, path)
    pkg2 = json.load(open(path))
    assert R.department_freshness(pkg2, "9", "cinematography", "1.B1.S1", "EpT")["current"] is True


# ── 6b: editing Voice's own working prompt does not stale Cinematography (boundary) ─────
def test_boundary_editing_voice_working_prompt_does_not_stale_cinematography(world, monkeypatch):
    calls, tmp, path = world
    _seed_keyframe_anchor(monkeypatch, path)
    _seed_voice(monkeypatch, path)
    pkg = json.load(open(path))
    assert R.department_freshness(pkg, "9", "cinematography", "1.B1.S1", "EpT")["current"] is True
    R.save_voice_working("9", "1.B1.S1", [{"text": "A completely different acted line."}],
                         "EpT", log=lambda *a, **k: None)
    pkg2 = json.load(open(path))
    assert R.department_freshness(pkg2, "9", "cinematography", "1.B1.S1", "EpT")["current"] is True


# ── 7: preparing/approving Animation does not stale Cinematography (boundary) ──────────
def test_boundary_animation_does_not_stale_cinematography(world, monkeypatch):
    calls, tmp, path = world
    _seed_animation_prereqs(monkeypatch, path)  # seeds voice + keyframe anchor already
    pkg = json.load(open(path))
    assert R.department_freshness(pkg, "9", "cinematography", "1.B1.S1", "EpT")["current"] is True

    _mock_llm(monkeypatch)
    R.prepare_department("9", "animation", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    pkg2 = json.load(open(path))
    assert R.department_freshness(pkg2, "9", "cinematography", "1.B1.S1", "EpT")["current"] is True, \
        "merely PREPARING an Animation candidate must never stale Cinematography"

    R.decide_department("9", "animation", "approved", "1.B1.S1", "EpT",
                        reviewed_by="Julian", log=lambda *a, **k: None)
    pkg3 = json.load(open(path))
    assert R.department_freshness(pkg3, "9", "cinematography", "1.B1.S1", "EpT")["current"] is True, \
        "APPROVING an Animation Direction must never stale Cinematography either"


# ── 8: unrelated review/status/UI fields do not stale any creative department ──────────
def test_boundary_unrelated_field_does_not_stale_any_department(world, monkeypatch):
    calls, tmp, path = world
    _seed_animation_prereqs(monkeypatch, path)
    _mock_llm(monkeypatch)
    R.prepare_department("9", "animation", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    R.decide_department("9", "animation", "approved", "1.B1.S1", "EpT",
                        reviewed_by="Julian", log=lambda *a, **k: None)
    pkg = json.load(open(path))
    pkg["shots"][1]["purpose"] = "a totally unrelated edit on a different, relay shot"
    json.dump(pkg, open(path, "w"))
    pkg2 = json.load(open(path))
    for stage in ("cinematography", "voice", "animation"):
        assert R.department_freshness(pkg2, "9", stage, "1.B1.S1", "EpT")["current"] is True, \
            f"an unrelated field edit must never stale {stage}"


# ── 8b: changing a shot's cutPace/internalCuts/transitionType AFTER Animation Direction is
#        approved MUST stale it (2026-07-21, Julian — "it doesn't fire, or it dies silently,
#        or the compiler never reads it. That has to stop."): compile_shot_contract branches
#        its entire action structure on exactly these fields; _animation_dependency_context
#        (what department_freshness actually hashes) omitted them until this fix, meaning a
#        Director's real cut-pace decision, made AFTER a shot was already approved, would
#        silently never re-stale the approval — _resolve_seedance_prompt would keep firing
#        the OLD providerPrompt, compiled under the old pace, forever.
def test_boundary_cutpace_change_after_approval_stales_animation(world, monkeypatch):
    calls, tmp, path = world
    _seed_animation_prereqs(monkeypatch, path)
    _mock_llm(monkeypatch)
    R.prepare_department("9", "animation", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    R.decide_department("9", "animation", "approved", "1.B1.S1", "EpT",
                        reviewed_by="Julian", log=lambda *a, **k: None)
    pkg = json.load(open(path))
    assert R.department_freshness(pkg, "9", "animation", "1.B1.S1", "EpT")["current"] is True

    # The Director changes the shot's own pace decision — real content compile_shot_contract
    # genuinely branches on (single_continuous_take -> paced_cuts, with real internalCuts).
    pkg["shots"][0]["cutPace"] = "paced_cuts"
    pkg["shots"][0]["internalCuts"] = ["Fuzzby rockets past the leaf.",
                                       "He clips it and rebounds proudly."]
    json.dump(pkg, open(path, "w"))
    pkg2 = json.load(open(path))
    fresh = R.department_freshness(pkg2, "9", "animation", "1.B1.S1", "EpT")
    assert fresh["current"] is False, ("a real cutPace/internalCuts change must stale the "
                                       "already-approved Animation Direction")
    assert "changed" in fresh and fresh["changed"], "the reason must be named, never silent"

    # And the hard gate every paid route calls through must now refuse, not silently reuse
    # the stale providerPrompt compiled under the old pace.
    with pytest.raises(R.DepartmentNotApproved):
        R._require_approved_department(pkg2, "9", "animation", "1.B1.S1", "EpT",
                                        action_label="firing on a stale cut-pace decision")


# ── 8c: the SAME change on an OPENER's cutInMotivation/transitionType (the relay-only
#        fields) must never falsely stale a shot that never carries them (an opener has no
#        predecessor, so transitionType stays None and this must be a true, quiet no-op).
def test_boundary_transition_fields_stay_none_and_inert_for_an_opener(world, monkeypatch):
    calls, tmp, path = world
    _seed_animation_prereqs(monkeypatch, path)
    _mock_llm(monkeypatch)
    R.prepare_department("9", "animation", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    R.decide_department("9", "animation", "approved", "1.B1.S1", "EpT",
                        reviewed_by="Julian", log=lambda *a, **k: None)
    pkg = json.load(open(path))
    assert pkg["shots"][0]["sourceType"] == "opener"
    assert pkg["shots"][0].get("transitionType") is None
    fresh = R.department_freshness(pkg, "9", "animation", "1.B1.S1", "EpT")
    assert fresh["current"] is True


# ── 8d: THE NON-GENERATED-SOURCE REASSESSMENT FIX (2026-07-22, found live in the Studio —
#        Julian: "I know it's saying it's already approved... but then they're saying
#        waiting for approval. What's it waiting for approval for?"): an UPLOADED keyframe
#        approval (inputSignature=None by design, per approve_keyframe's own docstring) must
#        never be permanently flagged "regenerate" by reassess_keyframe just because there's
#        nothing recorded to diff against — pinned to the exact real S1.SH1 shape
#        ({"source": "uploaded", "inputSignature": None}).
def test_uploaded_source_keyframe_is_always_carry_forward_never_falsely_stale(world, monkeypatch):
    calls, tmp, path = world
    pkg = json.load(open(path))
    led = next(l for l in pkg["continuityLedger"] if l["shotId"] == "1.B1.S1")
    led["keyframeApproval"] = {
        "approved": True, "path": "media/some_uploaded_reference.png",
        "at": "2026-07-20T20:45:19", "reviewedBy": "Julian",
        "source": "uploaded", "inputSignature": None}
    json.dump(pkg, open(path, "w"))
    before = R.reassess_keyframe("9", "1.B1.S1", "EpT")
    assert before["verdict"] == "carry_forward", (
        "an uploaded-source approval has nothing to diff against — it must never be treated "
        "as stale purely because inputSignature is None by design")
    assert before["changed"] == []

    # A REAL change to a reference image — the exact kind of drift that WOULD stale a
    # generated keyframe — must still leave an uploaded one untouched, since it was never
    # signature-checked in the first place (matching approve_keyframe's own rule).
    ref_path = tmp / "engine" / "media" / "refs" / "CB_Fuzzby.jpeg"
    ref_path.write_bytes(b"A GENUINELY DIFFERENT REFERENCE IMAGE")
    after = R.reassess_keyframe("9", "1.B1.S1", "EpT")
    assert after["verdict"] == "carry_forward", (
        "an uploaded-source approval stays carry-forward regardless of downstream drift — "
        "it was approved on the strength of the human's own deliberate choice, never "
        "against a compiled brief it has no relationship to")


# ── 9: changing a keyframe/reference input Cinematography actually consumes DOES stale it
def test_boundary_real_reference_change_does_stale_cinematography(world, monkeypatch):
    calls, tmp, path = world
    _seed_keyframe_anchor(monkeypatch, path)
    pkg = json.load(open(path))
    assert R.department_freshness(pkg, "9", "cinematography", "1.B1.S1", "EpT")["current"] is True
    ref_path = tmp / "engine" / "media" / "refs" / "CB_Fuzzby.jpeg"
    ref_path.write_bytes(b"A GENUINELY DIFFERENT REFERENCE IMAGE")
    pkg2 = json.load(open(path))
    fresh = R.department_freshness(pkg2, "9", "cinematography", "1.B1.S1", "EpT")
    assert fresh["current"] is False, "a real reference-image content change must stale Cinematography"


# ── 10: changing Cinematography's own approved prompt/output content stales it ─────────
# (sourceHash is INPUT-only by design — see _department_signature's own docstring — so this
# specific class of drift is what the new outputHash/_output_tamper_check machinery exists
# to catch; it is the mechanism that makes an approved-prompt change count as "staling" it
# within this revalidation-focused deliverable, distinct from but complementary to the
# pre-existing input-context staleness check exercised in the boundary tests above.)
def test_boundary_changing_approved_output_content_is_detected_as_drift(world, monkeypatch):
    calls, tmp, path = world
    _seed_keyframe_anchor(monkeypatch, path)
    approved, pkg = _load_approved(path, "1.B1.S1", "cinematography")
    assert approved.get("outputHash"), "a freshly-approved record must carry an output baseline"
    ok_before, note_before = R._output_tamper_check(approved)
    assert ok_before is True and note_before is None, "an untouched approval must pass the tamper check"

    approved["output"]["providerPrompt"] = "a directly altered approved prompt"
    json.dump(pkg, open(path, "w"))

    tampered, _ = _load_approved(path, "1.B1.S1", "cinematography")
    ok_after, note_after = R._output_tamper_check(tampered)
    assert ok_after is False
    assert "output content itself has changed" in note_after


# ── 11: THE HISTORY-MATCH DISCOVERY — a later decision superseded the exact direction that
# generated/was-approved-against the live keyframe; sealed evidence proves it, and the
# restore action brings it back, real routes only, zero LLM/provider calls ─────────────────
# (found investigating the REAL S1.SH1 record against this same mechanism: its currently
# approved Cinematography Direction does not match the sealed keyframe evidence, but a
# SUPERSEDED history entry does — exactly this scenario, reproduced here on disposable data.)
def test_history_match_found_when_a_later_decision_superseded_the_true_source(world, monkeypatch):
    calls, tmp, path = world
    _seed_keyframe_anchor(monkeypatch, path)  # approves cinematography, generates+approves the keyframe
    original, _ = _load_approved(path, "1.B1.S1", "cinematography")
    original_prompt = original["output"]["providerPrompt"]

    # A LATER decision replaces Cinematography's own approval with DIFFERENT text — e.g. an
    # attempted repair of an unrelated staleness bug that (mistakenly) re-ran the specialist —
    # never touching the keyframe itself, which stays approved against the ORIGINAL text.
    _mock_llm(monkeypatch, cinematography_prompt="a totally different, later cinematography "
                                                 "direction that never generated the keyframe")
    R.prepare_department("9", "cinematography", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    R.decide_department("9", "cinematography", "approved", "1.B1.S1", "EpT",
                        reviewed_by="Julian", log=lambda *a, **k: None)
    # Matches the REAL S1.SH1 record's actual shape: BOTH approvals predate signatureVersion/
    # sourceFields/outputHash tracking entirely (the whole feature was added after they were
    # made) — strip it from the now-current (later) approval to reproduce that real state,
    # which is what makes department_legacy_status even look at sealed evidence at all.
    _strip_signature_version(path)
    calls_before = {k: len(v) for k, v in calls.items()}

    pkg = json.load(open(path))
    current, _ = _load_approved(path, "1.B1.S1", "cinematography")
    assert current["output"]["providerPrompt"] != original_prompt, \
        "the later decision must now be the live approval"

    # The GENERAL sealed-evidence eligibility check correctly refuses — the LIVE approval
    # genuinely does not match what generated the keyframe (this is not a formula-scope issue).
    status = R.department_legacy_status(pkg, "9", "cinematography", "1.B1.S1", "EpT")
    assert status["eligible"] is False
    assert "cinematographyDirection" in (status["changedField"] or "")

    # The HISTORY-MATCH mechanism finds the true source instead.
    match = R.cinematography_history_match(pkg, "9", "1.B1.S1", "EpT")
    assert match["found"] is True
    assert match["historyIndex"] == 0
    assert match["reviewedBy"] == "Julian"

    event = R.restore_cinematography_from_history("9", "1.B1.S1", "EpT", reviewed_by="Julian",
                                                   log=lambda *a, **k: None)
    assert event["restoredFromHistoryIndex"] == 0

    restored, updated_pkg = _load_approved(path, "1.B1.S1", "cinematography")
    assert restored["output"]["providerPrompt"] == original_prompt, \
        "the restored approval must be the exact original text, never invented"
    assert restored["signatureVersion"] == R._DEPT_SIGNATURE_VERSION

    fresh = R.department_freshness(updated_pkg, "9", "cinematography", "1.B1.S1", "EpT")
    assert fresh["current"] is True, "a restored, sealed-evidence-matched approval reads current"

    # The later (now-superseded-again) decision is preserved in history, never discarded.
    led = next(l for l in updated_pkg["continuityLedger"] if l["shotId"] == "1.B1.S1")
    hist = led["departmentWork"]["cinematography"]["history"]
    assert any(h["output"]["providerPrompt"].startswith("a totally different")
              for h in hist), "the superseded later decision must survive in history"

    assert {k: len(v) for k, v in calls.items()} == calls_before, \
        "restoring from history must add zero NEW provider calls"


def test_restore_from_history_refuses_when_no_match_exists(world, monkeypatch):
    calls, tmp, path = world
    _seed_keyframe_anchor(monkeypatch, path)  # current approval DOES match the keyframe already
    with pytest.raises(R.Refused, match="nothing proven to restore"):
        R.restore_cinematography_from_history("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)


# ── 13: Refire always just works, even with a candidate already pending (2026-07-20, Julian
# — "every stage should have an approve and reject and refire button") ─────────────────────
def test_prepare_department_supersedes_a_pending_candidate_instead_of_refusing(world, monkeypatch):
    calls, tmp, path = world
    _mock_llm(monkeypatch, cinematography_prompt="first candidate text, never approved — long enough for the schema")
    R.prepare_department("9", "cinematography", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    first_cand = R.department_status("9", "1.B1.S1", "EpT", stage="cinematography")["candidate"]
    assert first_cand["output"]["providerPrompt"] == "first candidate text, never approved — long enough for the schema"

    # Refire again WITHOUT rejecting first — must succeed, not raise "already has work
    # awaiting a decision".
    _mock_llm(monkeypatch, cinematography_prompt="second candidate text, supersedes the first — long enough for the schema")
    R.prepare_department("9", "cinematography", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    second = R.department_status("9", "1.B1.S1", "EpT", stage="cinematography")
    assert second["candidate"]["output"]["providerPrompt"] == "second candidate text, supersedes the first — long enough for the schema"

    # The discarded first candidate survives in history, never silently lost.
    hist = second["history"]
    assert any(h.get("outcome") == "superseded_by_refire" and
              h["output"]["providerPrompt"] == "first candidate text, never approved — long enough for the schema"
              for h in hist)


# ── 14: unapprove_department — the always-available "Reject" for an APPROVED direction ────
def test_unapprove_department_moves_approval_to_history_and_clears_it(world, monkeypatch):
    calls, tmp, path = world
    _seed_keyframe_anchor(monkeypatch, path)  # cinematography is approved
    before_approved = R.department_status("9", "1.B1.S1", "EpT", stage="cinematography")["approved"]
    assert before_approved

    event = R.unapprove_department("9", "cinematography", "1.B1.S1", "EpT",
                                   note="wrong direction, redoing it", log=lambda *a, **k: None)
    assert event["rejectedNote"] == "wrong direction, redoing it"

    after = R.department_status("9", "1.B1.S1", "EpT", stage="cinematography")
    assert after["approved"] is None, "the shot must return to 'nothing approved' state"
    assert any(h.get("outcome") == "rejected" and h.get("rejectedNote") == "wrong direction, redoing it"
              for h in after["history"]), "the un-approved record must survive in history"


def test_unapprove_department_requires_a_note(world, monkeypatch):
    calls, tmp, path = world
    _seed_keyframe_anchor(monkeypatch, path)
    with pytest.raises(R.Refused, match="requires a plain-language note"):
        R.unapprove_department("9", "cinematography", "1.B1.S1", "EpT", note="",
                               log=lambda *a, **k: None)


def test_unapprove_department_refuses_with_no_approval(world, monkeypatch):
    calls, tmp, path = world
    with pytest.raises(R.Refused, match="no approved direction to reject"):
        R.unapprove_department("9", "cinematography", "1.B1.S1", "EpT", note="anything",
                               log=lambda *a, **k: None)


def test_unapprove_department_refuses_while_candidate_pending(world, monkeypatch):
    calls, tmp, path = world
    _seed_keyframe_anchor(monkeypatch, path)
    _mock_llm(monkeypatch, cinematography_prompt="a fresh candidate now pending — long enough to satisfy the schema")
    R.prepare_department("9", "cinematography", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    with pytest.raises(R.Refused, match="candidate awaiting a decision"):
        R.unapprove_department("9", "cinematography", "1.B1.S1", "EpT", note="anything",
                               log=lambda *a, **k: None)
