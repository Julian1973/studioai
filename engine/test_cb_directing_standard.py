import hashlib
import json
import pathlib

import pytest

import cb_creative as C
import cb_departments as D
import cb_render as R


def test_scene_director_uses_a_cross_process_serialisation_lock():
    source = pathlib.Path(C.__file__).read_text()
    assert "episode-scene-director.lock" in source
    assert "fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)" in source
    assert "@_serial_scene_director\ndef run_scene(" in source


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
        cinematographyContract=_cinematography(), performanceBudget=budget,
        storyIntent={
            "narrativeFunction": "Make avoidance funny before vulnerability becomes clear.",
            "primaryAudienceFeeling": "protective amusement",
            "secondaryAudienceFeeling": "recognition",
            "outerAction": "Bo rehearses leaving and returns to the conker.",
            "innerAction": "He tries to make fear look like practical preparation.",
            "performanceDirection": "Play the attempt to conceal fear, not generic fear.",
            "mutedRead": "Repeated doorway glances and retreat make avoidance visible.",
            "environmentPressure": "The open doorway turns the safe room into a decision.",
            "soundStory": "Packing sounds stop whenever the outside world intrudes.",
            "motifUse": "The conker changes from comfort object to delayed choice.",
            "thoughtChangeAndCut": "Hold when Bo admits the retreat through action.",
            "mustUnderstand": "Bo is delaying because leaving frightens him.",
            "mustNotKnowYet": "How Keen will respond when he arrives.",
            "reactionBeat": "Bo checks the doorway, then returns to the conker.",
            "relationshipDistance": "Mum remains close in sound but outside Bo's frame.",
            "relationshipPowerDynamic": "Mum's confidence increases the pressure on Bo.",
            "touchOrAvoidance": "Bo grips the conker instead of crossing the doorway.",
            "eyelineRule": "Doorway glances lead every retreat to the table.",
            "silhouetteRead": "Bo's forward lean repeatedly folds back toward safety.",
            "silenceRule": "Protect the pause after Mum's last reassurance.",
            "scoreInstruction": "Withhold melodic reassurance until Bo makes a real choice."})


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
    pkg = {"creativeDirectingStandardVersion": 4,
           "timingSlateReview": {"candidate": candidate, "approved": None, "history": []}}
    monkeypatch.setattr(R, "HERE", here)
    monkeypatch.setattr(R, "load_pkg", lambda scene, episode: (pkg, tmp_path / "pkg.json"))
    monkeypatch.setattr(R, "_timing_slate_input_signature", lambda value: signature)
    monkeypatch.setattr(R, "_save", lambda value, path: None)

    assert R.timing_slate_status("3", "EpT")["approved"] is False
    R.decide_timing_slate("3", "approved", episode="EpT", log=lambda *_: None)
    assert R.timing_slate_status("3", "EpT")["approved"] is True


def test_watch_uses_hear_approval_without_a_duplicate_rhythm_gate():
    source = pathlib.Path(R.__file__).read_text()
    fire_source = source[source.index("def fire_shot("):source.index("def next_shot(")]
    assert "_performance_budget_report(" in fire_source
    assert "voice-timed performance budget is overloaded" in fire_source
    assert "needs Julian's rhythm approval" not in fire_source


def test_fresh_validation_keeps_full_script_occurrences_for_mixed_sfx_dialogue():
    source = pathlib.Path(R.__file__).read_text()
    validation = source[source.index("def _fresh_validation("):source.index("def _prompt_version(")]
    assert 'target_lines = list(target_rec.get("dialogueLines") or [])' in validation
    assert "target_lines = cb_audio_authority.spoken_dialogue_lines(target_rec)" not in validation


def test_voice_direction_save_is_scoped_to_spoken_dialogue():
    source = pathlib.Path(R.__file__).read_text()
    scoped_validation = (
        'cb_departments.validate_voice_direction(\n'
        '            model, cb_audio_authority.spoken_dialogue_lines(shot))'
    )
    assert scoped_validation in source


def test_prompt_score_is_named_contract_completeness_not_artistic_quality():
    report = R._prompt_contract_completeness(
        {"dialogueLines": []},
        "Opening frame. Camera holds a wide composition with foreground depth and warm "
        "wood light. Bo hesitates, then reaches because the conker stops near him. End state.",
        {})
    assert report["maximum"] == 20
    assert "quality" not in report


def test_forward_department_work_requires_signed_v3_director_card(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "ROOT", tmp_path)
    card = {"shotId": "3.B1.S1", "storyIntent": {"narrativeFunction": "hesitation"},
            "performanceBudget": {"decision": "single-unit"},
            "cinematographyContract": _cinematography(),
            "performanceContract": {"beatOwner": "3.B1"}}
    storyboard = {"approvalState": "approved", "creativeDirectingStandardVersion": 4,
                  "emotionalStoryToScreenContract": {"northStar": {"x": "y"},
                      "transformation": {"x": "y"}, "tapestry": {"x": "y"}},
                  "shots": [card]}
    path = tmp_path / "storyboard.json"
    path.write_text(json.dumps(storyboard))
    card_hash = hashlib.sha256(json.dumps(
        card, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    pkg = {"creativeDirectingStandardVersion": 4,
           "sourceStoryboard": {"path": str(path), "approvalState": "approved",
                                  "creativeCardHashes": {"3.B1.S1": card_hash}}}
    assert R._require_forward_directing_source(
        pkg, {"shotId": "3.B1.S1"}, "3", "Ep2") == card
    pkg["sourceStoryboard"]["approvalState"] = "generated-pending-human-review"
    with pytest.raises(R.Refused, match="human-approved Director storyboard"):
        R._require_forward_directing_source(pkg, {"shotId": "3.B1.S1"}, "3", "Ep2")


def test_runtime_roles_have_one_current_owner_and_compatibility_aliases():
    current = D.load_runtime_skill("director")
    assert "Crystal Bears Director" in current
    assert D.load_runtime_skill("director", 3) == current
    assert D.load_runtime_skill("director", 4) == current
    assert D.load_runtime_skill("heart-director", 4) == current
    assert D.load_runtime_skill("story-director") == current
    # T53: chairs resolve by role — the studio craft plus the active project's taste overlay.
    for version in (0, 3, 4):
        assert R._department_skill_ref("animation", "seedance-production-director", version).startswith(
            "studio/chairs/animation/SKILL.md")
    assert R._department_skill_ref("cinematography", "dp", 4).startswith(
        "studio/chairs/cinematographer/SKILL.md")
    assert "crystal-bears-" not in R._department_skill_ref("cinematography", "dp", 4)


def test_v3_source_contract_remains_valid_without_v4_heart_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "ROOT", tmp_path)
    card = {"shotId": "S1.SH1", "performanceBudget": {"decision": "single-unit"},
            "cinematographyContract": {"storyPointOfView": "with Bo"},
            "performanceContract": {"beatOwner": "1.B1"}}
    storyboard = {"approvalState": "approved", "creativeDirectingStandardVersion": 3,
                  "shots": [card]}
    path = tmp_path / "v3-storyboard.json"
    path.write_text(json.dumps(storyboard))
    card_hash = hashlib.sha256(json.dumps(
        card, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    pkg = {"creativeDirectingStandardVersion": 3,
           "sourceStoryboard": {"path": str(path), "approvalState": "approved",
                                  "creativeCardHashes": {"S1.SH1": card_hash}}}
    assert R._require_forward_directing_source(
        pkg, {"shotId": "S1.SH1"}, "1", "Ep1") == card
