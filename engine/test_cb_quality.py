import cb_quality


def _state(**stage_overrides):
    stages = {
        "script": {"state": "approved"},
        "storyboard": {"state": "approved"},
        "scenelook": {"state": "approved"},
        "voice": {"state": "approved"},
        "keyframe": {"state": "approved"},
        "animation": {"state": "approved"},
        "continuity": {"state": "approved"},
        "final": {"state": "approved"},
    }
    stages.update({key: {"state": value} for key, value in stage_overrides.items()})
    return {
        "packageCurrent": True,
        "canonLock": {"current": True, "episodeReady": True, "blockers": []},
        "stages": stages,
        "shots": [{"shotId": "S1.SH1"}],
        "postProduction": {
            "approved": {"current": True, "manifestDigest": "abc123"},
        },
    }


def _package():
    return {
        "directorStatement": {
            "audienceFeeling": "The audience spots the wobble before Zenny does.",
            "whoseScene": "Zenny",
            "emotionalChange": "control to honest connection",
            "theLaugh": "patient expectation, Fuzzby disruption, held reaction",
            "visualSurprise": "ordered wide to intimate held close-up",
            "carryForward": "one loose ribbon remains",
        },
        "creativeIntent": {
            "beatExperienceContracts": [{
                "beatId": "B1",
                "emotion": {"owner": "Zenny", "entryState": "contained"},
                "comedy": {"mode": "BIG", "mechanism": "status reversal"},
                "power": None,
            }],
        },
        "shots": [{
            "shotId": "S1.SH1",
            "performanceContractApproved": {"phases": [{"phaseId": "P1"}]},
            "characterTruthsApproved": [{"character": "Zenny"}],
            "cinematographyContractApproved": {"storyPov": "Zenny"},
        }],
    }


def _dimensions(compass):
    return {item["id"]: item for item in compass["dimensions"]}


def test_canon_conflict_is_attention_not_automatically_resolved():
    state = _state(storyboard="blocked", scenelook="locked", voice="locked",
                   keyframe="locked", animation="locked", continuity="locked",
                   final="locked")
    state["packageCurrent"] = False
    state["canonLock"]["blockers"] = [{"message": "Zenny crystal conflict"}]

    compass = cb_quality.quality_compass(state)

    story = _dimensions(compass)["story"]
    assert story["state"] == "attention"
    assert story["directorQuestion"] == "Which signed source should govern this conflict?"
    assert compass["zeroSpend"] is True


def test_legacy_handover_cannot_masquerade_as_current_creative_intent():
    package = _package()
    package["directorStatement"]["audienceFeeling"] = "n/a (legacy storyboard)"
    package["creativeIntent"] = {}

    compass = cb_quality.quality_compass(_state(), package)

    assert _dimensions(compass)["story"]["state"] == "attention"
    assert compass["overall"] == "attention"


def test_typed_plan_remains_unassessed_until_rendered_media_is_reviewed():
    state = _state(voice="ready", animation="ready", continuity="ready", final="locked")

    compass = cb_quality.quality_compass(state, _package())
    dimensions = _dimensions(compass)

    assert dimensions["story"]["state"] == "clear"
    assert dimensions["performance"]["state"] == "unassessed"
    assert dimensions["picture"]["state"] == "unassessed"
    assert dimensions["sound"]["state"] == "unassessed"
    assert dimensions["finish"]["state"] == "waiting"
    assert "artistic quality remains a human verdict" in compass["claim"]


def test_fully_reviewed_current_master_clears_structural_quality_compass():
    compass = cb_quality.quality_compass(_state(), _package())

    assert compass["overall"] == "clear"
    assert all(item["state"] == "clear" for item in compass["dimensions"])
