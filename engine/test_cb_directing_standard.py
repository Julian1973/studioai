import hashlib
import json
import pathlib

import pytest

import cb_creative as C
import cb_departments as D
import cb_render as R


def _cinematography():
    return {
        "storyPointOfView": "Stay with Bo's private hesitation.",
        "emotionalDistanceStart": "Observe his ritual from a protected distance.",
        "emotionalDistanceEnd": "Arrive close enough to share the failed brave thought.",
        "revealStrategy": "Let the doorway become pressure only when Bo looks toward it.",
        "shotScale": "interior medium-wide to intimate medium",
        "lensIntent": "Preserve room geography without emotionally abandoning Bo.",
        "cameraHeight": "Bo's seated eye level",
        "composition": "Bo and conker share the foreground decision space.",
        "depthStrategy": "Doorway pressure remains readable behind him.",
        "cameraBehavior": "Patient approach, then stillness for the reversal.",
        "focusStrategy": "Hold Bo and the conker readable through each contact.",
        "lightingFunction": "Warm home light makes leaving feel genuinely difficult.",
        "paletteFunction": "Warm interior against cooler doorway separation.",
        "performanceVisibility": "Paws, conker contact, eyeline and reaction remain visible.",
        "editorialPurpose": "Carry one complete hesitation and its reaction without coverage.",
        "memorableLandingImage": "Bo holds the conker at the satchel mouth, caught between choices.",
        "providerInstruction": "Stay at Bo's eye level; preserve the doorway and visible prop contact.",
    }


def _card(budget):
    return C.StoryboardCard(
        shotId="3.B1.S1", beatIds=["3.B1"], targetDurationSec=30,
        stagePlan=[
            {"stageNumber": 1, "beatIds": ["3.B1"], "purpose": "hesitation",
             "primaryEvent": "Bo tests leaving and stops.",
             "emotionalOrComicTurn": "stalling becomes visible fear",
             "cameraAndTransition": "camera approaches and then waits",
             "observableEndState": "Bo remains inside"},
            {"stageNumber": 2, "beatIds": ["3.B1"], "purpose": "return",
             "primaryEvent": "Bo returns to the conker.",
             "emotionalOrComicTurn": "bravery collapses",
             "cameraAndTransition": "camera follows the retreat",
             "observableEndState": "conker reaches the satchel mouth"},
        ],
        purpose="Make avoidance funny before its vulnerability becomes clear.",
        audienceExperience="Protective amusement becomes recognition.",
        openingImage="Bo waits beside the open satchel and conker.",
        principalPerformance="Bo rehearses leaving, then returns.",
        cameraRelationship="The camera approaches, waits and follows his retreat.",
        physicalOrEmotionalChange="Casual delay becomes visible fear.",
        closingImage="Bo holds the conker half-packed.",
        transitionType="PLANNED_CUT", transitionReason="The next entrance changes the power.",
        providerBoundaryReason="dramatic_editorial_break",
        providerBoundaryExplanation="Keen's arrival begins a new relationship beat.",
        cinematographyContract=_cinematography(), performanceBudget=budget)


def test_storyboard_card_refuses_a_budget_that_cannot_breathe():
    with pytest.raises(ValueError, match="performance budget exceeds"):
        _card({
            "emotionalTurnCount": 2, "propStateChangeCount": 3, "dialogueHeavy": True,
            "silentActingReserveSec": 6, "landingHoldSec": 2,
            "minimumHonestDurationSec": 34, "decision": "single-unit",
            "rationale": "The complete performance needs more room."})


def test_voice_timing_blocks_prompt_complete_but_overloaded_action():
    shot = _card({
        "emotionalTurnCount": 2, "propStateChangeCount": 3, "dialogueHeavy": True,
        "silentActingReserveSec": 4.5, "landingHoldSec": 1.5,
        "minimumHonestDurationSec": 30, "decision": "single-unit",
        "rationale": "Only viable if the voice leaves six seconds of physical air."}).model_dump()
    shot["durationSec"] = 30
    shot["performanceBudgetApproved"] = shot.pop("performanceBudget")
    shot["dialogueLines"] = [
        {"startSec": 0.5, "endSec": 5.45}, {"startSec": 5.6, "endSec": 7.3},
        {"startSec": 8.2, "endSec": 11.2}, {"startSec": 13.0, "endSec": 23.5},
        {"startSec": 24.0, "endSec": 26.35}, {"startSec": 26.65, "endSec": 29.8},
    ]
    report = R._performance_budget_report(shot, {})
    assert report["ready"] is False
    assert report["dialogueOccupancyRatio"] > 0.8
    assert report["recommendedAction"] == "split-at-strongest-story-boundary"


def test_timing_slate_requires_and_records_human_rhythm_approval(tmp_path, monkeypatch):
    here = tmp_path / "engine"
    media = here / "media"
    media.mkdir(parents=True)
    slate = media / "EpT_Scene3_timing_slate.mp4"
    slate.write_bytes(b"voice-timed-slate")
    signature = {"shots": [{"shotId": "3.B1.S1", "durationSec": 30}]}
    pathlib.Path(str(slate) + ".contract.json").write_text(json.dumps({
        "generatedAt": "now", "inputSignature": signature}))
    candidate = {"path": str(slate), "contentHash": hashlib.sha256(slate.read_bytes()).hexdigest(),
                 "inputSignature": signature, "preparedAt": "now"}
    pkg = {"creativeDirectingStandardVersion": 3,
           "timingSlateReview": {"candidate": candidate, "approved": None, "history": []}}
    monkeypatch.setattr(R, "HERE", here)
    monkeypatch.setattr(R, "load_pkg", lambda scene, episode: (pkg, tmp_path / "pkg.json"))
    monkeypatch.setattr(R, "_timing_slate_input_signature", lambda value: signature)
    monkeypatch.setattr(R, "_save", lambda value, path: None)

    assert R.timing_slate_status("3", "EpT")["approved"] is False
    R.decide_timing_slate("3", "approved", episode="EpT", log=lambda *_: None)
    assert R.timing_slate_status("3", "EpT")["approved"] is True


def test_prompt_score_is_named_contract_completeness_not_artistic_quality():
    report = R._prompt_contract_completeness(
        {"dialogueLines": []},
        "Opening frame. Camera holds a wide composition with foreground depth and warm "
        "wood light. Bo hesitates, then reaches because the conker stops near him. End state.",
        {})
    assert report["maximum"] == 20
    assert "quality" not in report


def test_forward_department_work_requires_signed_v3_director_card(tmp_path):
    card = {"shotId": "3.B1.S1", "performanceBudget": {"decision": "single-unit"},
            "cinematographyContract": _cinematography(),
            "performanceContract": {"beatOwner": "3.B1"}}
    storyboard = {"approvalState": "approved", "creativeDirectingStandardVersion": 3,
                  "shots": [card]}
    path = tmp_path / "storyboard.json"
    path.write_text(json.dumps(storyboard))
    card_hash = hashlib.sha256(json.dumps(
        card, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    pkg = {"creativeDirectingStandardVersion": 3,
           "sourceStoryboard": {"path": str(path), "approvalState": "approved",
                                  "creativeCardHashes": {"3.B1.S1": card_hash}}}
    assert R._require_forward_directing_source(
        pkg, {"shotId": "3.B1.S1"}, "3", "Ep2") == card
    pkg["sourceStoryboard"]["approvalState"] = "generated-pending-human-review"
    with pytest.raises(R.Refused, match="human-approved Director storyboard"):
        R._require_forward_directing_source(pkg, {"shotId": "3.B1.S1"}, "3", "Ep2")


def test_v3_runtime_is_versioned_without_changing_legacy_canon_skill():
    legacy = D.load_runtime_skill("director")
    forward = D.load_runtime_skill("director", 3)
    assert "Director v3" not in legacy
    assert "Director v3" in forward
    assert R._department_skill_ref("animation", "seedance-production-director", 0) == (
        "skills/seedance-production-director/SKILL.md")
    assert R._department_skill_ref("animation", "seedance-production-director", 3) == (
        "skills/seedance-production-director-v3/SKILL.md")
