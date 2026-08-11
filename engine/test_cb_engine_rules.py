import cb_engine_rules as rules
import cb_render as render


def _shot(duration=9):
    return {"shotId": "UNIT", "durationSec": duration,
            "purpose": "A chase with two readable near-misses, impact, leaf recoil and held pose."}


def _direction(duration=9):
    return {
        "durationSec": duration,
        "geography": ["Travel runs toward frame-right."],
        "cameraBehaviour": "A small drone follows slightly late behind the subject.",
        "physicalCauseAndEffect": "Impact loads the springy leaf; recoil starts one rotation and recovery.",
        "stagePlan": [{"primaryEvent": "The subject travels, tumbles, then settles into a held pose."}],
        "creativeTranslation": {"gagClocks": [{"beatCode": "B1", "recoveryHoldSec": 2.1}]},
    }


def test_beat_cost_blocks_overstuffed_units_and_uses_margin():
    report = rules.beat_cost_report(_shot(), _direction())
    assert report["recommendedDurationSec"] == 13
    assert report["ready"] is False
    assert rules.beat_cost_report(_shot(13), _direction(13))["ready"] is True


def test_only_compression_verdicts_raise_versioned_costs():
    data = rules.load_beat_costs()
    unchanged, applied = rules.apply_compression_verdict(
        data, {"category": "identity", "diagnosis": "the face drifted"})
    assert applied is False and unchanged == data
    updated, applied = rules.apply_compression_verdict(data, {
        "category": "action-timing", "diagnosis": "the impact was rushed",
        "beatType": "impact", "increaseSec": 0.2, "verdictId": "V1"})
    assert applied is True
    assert updated["costsSec"]["impact"] == data["costsSec"]["impact"] + 0.2


def test_geometry_must_agree_between_keyframe_and_render():
    cine = {
        "geography": ["Travel runs toward frame-right."],
        "lensAndCameraRelationship": "Drone follow from behind.",
        "negativeSpace": ["Lead room stays open frame-right."],
        "openingFrameLayout": {"placements": [{
            "character": "Subject", "facing": "away from camera toward frame-right"}]},
    }
    assert rules.geometry_agreement(cine, _direction())["ready"] is True
    bad = {**cine, "openingFrameLayout": {"placements": [{
        "character": "Subject", "facing": "toward camera"}]}}
    assert rules.geometry_agreement(bad, _direction())["ready"] is False


def test_relay_units_use_the_approved_carried_frame_not_a_second_keyframe_contract(
        monkeypatch):
    monkeypatch.setattr(
        rules, "beat_cost_report",
        lambda *_args, **_kwargs: {"ready": True})
    monkeypatch.setattr(
        rules, "action_unit_report",
        lambda *_args, **_kwargs: {"ready": True, "errors": []})
    monkeypatch.setattr(
        rules, "geometry_agreement",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("relay must not compare against a separately authored keyframe")))

    report = render._engine_rule_report(
        {}, {"shotId": "UNIT", "sourceType": "relay"},
        {"geography": ["The carried frame is the opening truth."]},
        cinematography={"geography": ["A stale parallel brief."]})

    assert report["ready"] is True
    assert report["geometry"]["basis"] == "approved-relay-opening-frame"


def test_assets_before_cost_provenance_are_inputs_not_duration_constraints():
    provenance = rules.duration_provenance(_shot(13), _direction(13),
                                           costed_at="2026-08-10T10:00:00+00:00")
    assert not rules.asset_may_constrain_duration(
        {"generatedAt": "2026-08-09T10:00:00+00:00"}, provenance)
    assert rules.asset_may_constrain_duration(
        {"generatedAt": "2026-08-10T11:00:00+00:00"}, provenance)
    assert not rules.asset_may_constrain_duration(
        {"generatedAt": "2026-08-10T11:00:00+00:00"},
        {**provenance, "authoritative": False})


def test_duration_change_carries_only_existing_human_approvals_as_inputs():
    ledger = {
        "keyframeApproval": {"approved": True, "at": "2026-08-09T10:00:00+00:00"},
        "voiceApproval": {"approved": True, "at": "2026-08-09T10:01:00+00:00"},
    }
    provenance = rules.duration_provenance(
        _shot(16), _direction(16), costed_at="2026-08-10T10:00:00+00:00")
    carried = render._carry_approved_inputs_across_duration_change(ledger, provenance)
    assert carried == ["keyframeApproval", "voiceApproval"]
    for key in carried:
        record = ledger[key]["durationCarryForward"]
        assert record["newDurationSec"] == 16
        assert record["costSignature"] == provenance["costSignature"]


def test_duration_change_never_invents_missing_approvals():
    ledger = {"keyframeApproval": None, "voiceApproval": {"approved": False}}
    provenance = rules.duration_provenance(_shot(16), _direction(16))
    assert render._carry_approved_inputs_across_duration_change(ledger, provenance) == []
    assert ledger["keyframeApproval"] is None
    assert "durationCarryForward" not in ledger["voiceApproval"]


def test_meta_rule_separates_engine_fixes_from_director_instances():
    assert rules.generic_fix_review("Every dialogue marker has one named speaker.")["ready"]
    assert not rules.generic_fix_review("Patch S1.SH1A so its dialogue works.")["ready"]


def _action_direction():
    return {
        "durationSec": 16,
        "timingBeats": [
            {"type": "travel", "count": 1, "source": "approved travel"},
            {"type": "impact", "count": 3, "source": "approved contacts"},
            {"type": "load_release", "count": 1, "source": "approved load"},
            {"type": "aerial", "count": 1, "source": "approved aerial"},
            {"type": "self_check", "count": 1, "source": "retroactive button"},
            {"type": "reaction", "count": 1, "source": "witness payoff"},
        ],
        "creativeTranslation": {"gagClocks": [{
            "beatCode": "B", "retroactive": True, "recoveryHoldSec": 2.1}]},
        "witnessStagingSides": ["Actor frame-left; witness frame-right."],
        "shotPlan": [
            {"purpose": "Travel", "framingLensAndCamera": "Pursuit camera.",
             "causalAction": "Three parallax speeds: foreground, midground and distant. Named landmarks pass the camera and vanish behind it. The subject pulls ahead and shrinks; the camera surges and it swells. It drifts to the frame edge and the camera swings to recover it. Foreground stems wipe across the lens."},
            {"purpose": "Escalation", "framingLensAndCamera": "Hold each contact.",
             "causalAction": "The first contact starts a spin; the second hits harder and the spin doubles; the third is worse than the last and loads the leaf."},
            {"purpose": "Aerial", "framingLensAndCamera": "Camera tracks the full arc.",
             "causalAction": "The release creates a double backward tuck with triple twist."},
            {"purpose": "Button", "framingLensAndCamera": "Hold actor and witness.",
             "causalAction": "The actor looks left, right and down, checks their body is intact, then poses. The non-acting witness stays motionless and holds the joke."},
        ],
    }


def test_r8_to_r14_action_grammar_accepts_proven_flova_structure():
    shot = {"charactersInFrame": ["Actor", "Witness"], "dialogueLines": []}
    report = rules.action_unit_report(shot, _action_direction())
    assert report["ready"] is True, report["errors"]
    assert report["internalShotCount"] == 4


def test_action_grammar_blocks_flat_single_shot_travel_and_repeated_contacts():
    direction = _action_direction()
    direction["shotPlan"] = [direction["shotPlan"][0]]
    direction["timingBeats"] = [
        {"type": "travel", "count": 1, "source": "approved travel"},
        {"type": "impact", "count": 3, "source": "approved contacts"},
    ]
    direction["creativeTranslation"] = {"gagClocks": []}
    report = rules.action_unit_report(
        {"charactersInFrame": ["Actor"], "dialogueLines": []}, direction)
    assert report["ready"] is False
    assert any("R8" in error for error in report["errors"])
    assert any("R10" in error for error in report["errors"])


def test_r15_requires_attributed_delivery_and_post_line_hold():
    direction = {"shotPlan": [{
        "shotNumber": 1,
        "dialogueLineIndexes": [1],
        "dialogueDirections": ["calm and resolved"],
        "holdAfterDialogue": True,
    }], "creativeTranslation": {"gagClocks": []}}
    shot = {"charactersInFrame": ["Actor"], "dialogueLines": [
        {"speaker": "Actor", "exactText": "Done."}]}
    assert not rules.action_unit_report(shot, direction, "Actor says {Done.}")["ready"]
    prompt = ("Shot 1: Dialogue placement: Actor, calm and resolved: {Done.} "
              "The pose holds a full beat after the line ends.\n[Audio]\nNatural sound.")
    assert rules.action_unit_report(shot, direction, prompt)["ready"]


def test_r15_suppresses_hold_when_immediate_action_is_typed():
    direction = {"shotPlan": [{
        "shotNumber": 1,
        "dialogueLineIndexes": [1],
        "dialogueDirections": ["at full volume, before the launch"],
        "holdAfterDialogue": False,
    }], "creativeTranslation": {"gagClocks": []}}
    shot = {"charactersInFrame": ["Actor"], "dialogueLines": [
        {"speaker": "Actor", "exactText": "Go!"}]}
    prompt = ("Shot 1: Dialogue placement: Actor, at full volume, before the launch: "
              "{Go!} The actor launches immediately.\n[Audio]\nNatural sound.")
    assert rules.action_unit_report(shot, direction, prompt)["ready"]
