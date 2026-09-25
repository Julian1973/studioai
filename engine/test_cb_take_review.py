"""T36 - the voice/dialogue contract, clause 4, acceptance check 3: the take review desk.

Every take has a player plus approve/reject. "Approve & continue to WATCH" is the forward
action; "Reject / add a note" is always available and the note reaches the Voice Director;
"Regenerate" is optional; "Approve this take as heard" needs a recorded reason and keeps the
identity/voice/timing safeguards. Rejected and superseded takes stay in history.
"""
import json
import os

import pytest

import cb_render as R
import cb_studio_director
from test_cb_audio1 import QUIET, voiced  # noqa: F401  (fixtures)
from test_current_production_path import isolated_canon, world  # noqa: F401
from test_golden_path import _voice_direction_output


def _ledger(shot_id):
    pkg, _ = R.load_pkg("9", "EpT")
    return pkg, R._shot(pkg, shot_id), R._ledger(pkg, shot_id)


def _edit_take(shot_id, **changes):
    """Simulate a take generated from an earlier direction."""
    pkg, path = R.load_pkg("9", "EpT")
    ledger = R._ledger(pkg, shot_id)
    signature = dict(ledger["voInputSignature"])
    signature.update(changes.pop("signature", {}))
    ledger["voInputSignature"] = signature
    for key, value in changes.items():
        ledger[key] = value
    R._save(pkg, path)


# ── approve as heard ────────────────────────────────────────────────────────────

def test_a_take_from_an_earlier_direction_needs_the_as_heard_reason(voiced):
    _edit_take(voiced, signature={"performanceHash": "an-earlier-performance"},
               voGeneratedFrom=[{**line, "recipeId": "an-earlier-recipe"}
                                for line in _ledger(voiced)[2]["voGeneratedFrom"]])
    with pytest.raises(R.Refused, match="approve this take as heard with a reason"):
        R.approve_voice("9", voiced, "EpT", reviewed_by="Julian", **QUIET)
    R.approve_voice("9", voiced, "EpT", reviewed_by="Julian",
                    as_heard_reason="The earlier read lands the joke better", **QUIET)
    pkg, shot, ledger = _ledger(voiced)
    as_heard = ledger["voiceApproval"]["asHeard"]
    assert as_heard["reason"] == "The earlier read lands the joke better"
    assert as_heard["differences"] == ["performanceHash"]
    assert as_heard["safeguards"] == ["identity", "voice", "timing"]
    record = R.current_audio1(pkg, voiced)
    assert record["approvedAsHeard"]["reason"] == as_heard["reason"]
    # still a current approval downstream
    assert R._voice_approval_status(pkg, shot)["current"] is True
    assert R.voice_performance_status("9", voiced, "EpT")["approvedAsHeard"]["reason"] == \
        as_heard["reason"]


@pytest.mark.parametrize("change,match", [
    ({"signature": {"performanceHash": "x", "dialogueHash": "another-version"}},
     "identity: the take was made for a different dialogue version"),
    ({"signature": {"performanceHash": "x", "voiceIds": ["someone-else"]}},
     "voice: a line was voiced by a different registered voice"),
    ({"signature": {"performanceHash": "x", "canonProfileDigest": "older-canon"}},
     "voice: the voice canon changed after this take"),
])
def test_as_heard_never_bends_identity_or_voice(voiced, change, match):
    _edit_take(voiced, **change)
    with pytest.raises(R.Refused, match=match):
        R.approve_voice("9", voiced, "EpT", reviewed_by="Julian",
                        as_heard_reason="I like it", **QUIET)
    assert not _ledger(voiced)[2].get("voiceApproval")


def test_as_heard_refuses_a_take_that_speaks_other_words(voiced):
    generated = _ledger(voiced)[2]["voGeneratedFrom"]
    _edit_take(voiced, signature={"performanceHash": "x"},
               voGeneratedFrom=[{**generated[0], "text": generated[0]["text"] + " Extra"},
                                *generated[1:]])
    with pytest.raises(R.Refused, match="does not speak .* approved words"):
        R.approve_voice("9", voiced, "EpT", reviewed_by="Julian",
                        as_heard_reason="I like it", **QUIET)


# ── history: nothing is a single slot ─────────────────────────────────────────────

def test_regenerated_and_rejected_takes_stay_in_history(voiced):
    _, _, first = _ledger(voiced)
    first_take = first["voPath"]
    R.regen_voice_shot("9", voiced, "EpT", **QUIET)
    _, _, second = _ledger(voiced)
    second_take = second["voPath"]
    assert second_take != first_take
    R.reject_voice("9", voiced, "Too fast into the button", "EpT", reviewed_by="Julian",
                   **QUIET)
    pkg, _, ledger = _ledger(voiced)
    superseded, rejected = ledger["voiceTakeHistory"]
    assert superseded["status"] == "superseded" and superseded["take"]["voPath"] == first_take
    assert rejected["status"] == "rejected" and rejected["reason"] == "Too fast into the button"
    assert os.path.exists(superseded["take"]["voPath"])
    assert os.path.exists(rejected["take"]["voPath"])            # archived, never deleted
    assert rejected["take"]["voPlacementPath"]                     # the full bundle travels
    history = R.voice_performance_status("9", voiced, "EpT")["takeHistory"]
    assert [entry["status"] for entry in history] == ["rejected", "superseded"]  # newest first
    assert history[0]["reason"] == "Too fast into the button"


# ── the note reaches the Voice Director ───────────────────────────────────────────

def test_a_rejection_note_reaches_the_voice_director_before_the_next_take(voiced, monkeypatch):
    R.reject_voice("9", voiced, "Warmer, less sarcastic", "EpT", reviewed_by="Julian", **QUIET)
    pkg, shot, ledger = _ledger(voiced)
    pending = R.hear_note_unanswered(pkg, voiced, "9", "EpT")
    assert pending["note"] == "Warmer, less sarcastic"
    context = R._shot_context(pkg, shot, ledger, "9", "EpT")
    assert context["hearTakeNotes"][-1]["note"] == "Warmer, less sarcastic"
    assert R.voice_performance_status("9", voiced, "EpT")["hearNotePending"]["note"] == \
        "Warmer, less sarcastic"

    seen = {}

    def director(context, locked_lines, log=print):
        seen["notes"] = context.get("hearTakeNotes")
        return R.cb_departments.validate_voice_direction(
            R.cb_departments.VoiceDirection.model_validate(_voice_direction_output(shot)),
            locked_lines)
    monkeypatch.setattr(R.cb_departments, "prepare_voice", director)
    calls = []
    monkeypatch.setattr(R, "voice_shot", lambda *a, **k: calls.append("voice_shot"))

    cb_studio_director.build_voice("9", voiced, "EpT", log=lambda *a, **k: None)

    assert seen["notes"][-1]["note"] == "Warmer, less sarcastic"
    assert calls == ["voice_shot"]                                   # then the take
    pkg, _, _ = _ledger(voiced)
    assert R.hear_note_unanswered(pkg, voiced, "9", "EpT") is None   # answered


def test_an_answered_note_does_not_redirect_again(voiced, monkeypatch):
    prepared = []
    monkeypatch.setattr(R, "prepare_department", lambda *a, **k: prepared.append(a))
    monkeypatch.setattr(R, "voice_shot", lambda *a, **k: None)
    cb_studio_director.build_voice("9", voiced, "EpT", log=lambda *a, **k: None)
    assert prepared == []                         # no note, current direction: no re-direct
