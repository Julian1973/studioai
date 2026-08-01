import copy

import cb_lineage
import cb_studio_agent as agent


def _intake():
    return {
        "episode": "Ep1",
        "hasScript": True,
        "scriptName": "Ep1_Test.txt",
        "scriptVersionId": "sha256:" + "1" * 64,
        "hasCandidate": True,
        "candidateCurrent": True,
        "canonicalCurrent": False,
        "canonicalBeatPackageDigest": None,
        "candidate": {
            "inputSignature": {"digest": "2" * 64},
        },
    }


def _state():
    return {
        "policyVersion": "test-policy-v1",
        "episode": "Ep1",
        "scene": "1",
        "canonLock": {
            "current": True,
            "episodeReady": False,
            "manifestDigest": "3" * 64,
            "profileDigests": {"story": "4" * 64},
            "blockers": [
                {
                    "code": "SCRIPT_CANON_CONFLICT",
                    "message": "The script and locked canon disagree.",
                    "action": "Choose the authority and create a new immutable version.",
                    "evidence": "conflicting script line",
                },
            ],
            "warnings": [],
        },
        "packageExists": False,
        "packageCurrent": False,
        "lineage": {"current": False, "reasonCodes": ["canon-lock-required"]},
        "stages": {
            "script": {"state": "approved"},
            "storyboard": {"state": "blocked", "sub": "canon conflict"},
            "scenelook": {"state": "locked"},
            "voice": {"state": "locked"},
            "keyframe": {"state": "locked"},
            "animation": {"state": "locked"},
            "continuity": {"state": "locked"},
            "final": {"state": "locked"},
        },
        "shots": [],
        "blockers": [],
    }


def _preflight():
    return {
        "ok": False,
        "zeroSpend": True,
        "blockers": [{
            "code": "CANON_LOCK_REQUIRED",
            "stage": "storyboard",
            "message": "The script and locked canon disagree.",
            "action": "Choose the authority and create a new immutable version.",
        }],
        "warnings": [],
        "nextAction": "Choose the authority and create a new immutable version.",
    }


def _install(monkeypatch, intake=None, state=None, preflight=None):
    intake = intake if intake is not None else _intake()
    state = state if state is not None else _state()
    preflight = preflight if preflight is not None else _preflight()
    monkeypatch.setattr(agent.cb_intake, "intake_status", lambda episode: intake)
    monkeypatch.setattr(
        agent.cb_state,
        "production_state",
        lambda scene, episode, intake=None: state,
    )
    monkeypatch.setattr(
        agent.cb_production_preflight,
        "production_preflight",
        lambda scene, episode, state=None: preflight,
    )
    return intake, state, preflight


def test_help_brief_is_deterministic_signed_and_read_only(monkeypatch):
    intake, state, preflight = _install(monkeypatch)
    before = copy.deepcopy((intake, state, preflight))

    first = agent.studio_agent_brief("1", "Ep1")
    second = agent.studio_agent_brief("1", "Ep1")

    assert first == second
    assert (intake, state, preflight) == before
    assert first["mode"] == "HELP"
    assert first["readOnly"] is True
    assert first["zeroSpend"] is True
    assert first["nextAction"]["execution"] == {
        "available": False,
        "mode": "HELP",
        "changesData": False,
        "canSpend": False,
        "reason": "HELP mode can navigate and explain, but cannot execute work.",
    }
    assert "call-media-providers" in first["authority"]["mayNot"]
    assert first["briefId"].endswith(first["contextSignature"]["digest"])
    assert cb_lineage.signature_matches(
        first["contextSignature"],
        "studio-agent-context",
        first["contextSignature"]["inputs"],
    )


def test_one_intake_and_readiness_snapshot_flows_through_the_brief(monkeypatch):
    intake, state, preflight = _intake(), _state(), _preflight()
    observed = {}
    monkeypatch.setattr(agent.cb_intake, "intake_status", lambda episode: intake)

    def production_state(scene, episode, intake=None):
        observed["intake"] = intake
        return state

    def production_preflight(scene, episode, state=None):
        observed["state"] = state
        return preflight

    monkeypatch.setattr(agent.cb_state, "production_state", production_state)
    monkeypatch.setattr(
        agent.cb_production_preflight,
        "production_preflight",
        production_preflight,
    )

    agent.studio_agent_brief("1", "Ep1")

    assert observed["intake"] is intake
    assert observed["state"] is state


def test_canon_conflict_is_a_human_decision_not_a_proven_fact(monkeypatch):
    _install(monkeypatch)

    brief = agent.studio_agent_brief("1", "Ep1")

    assert brief["headline"] == "Scene 1 needs attention in Story & Direction."
    assert brief["nextAction"]["type"] == "resolve-blocker"
    assert brief["nextAction"]["blockerCode"] == "CANON_LOCK_REQUIRED"
    assert len(brief["decisions"]) == 1
    assert brief["decisions"][0]["code"] == "SCRIPT_CANON_CONFLICT"
    proven_ids = {item["id"] for item in brief["facts"]["proven"]}
    assert "canon-manifest-current" in proven_ids
    assert "episode-canon-ready" not in proven_ids


def test_shot_selection_cannot_bypass_an_upstream_scene_blocker(monkeypatch):
    state = _state()
    state["canonLock"]["episodeReady"] = True
    state["canonLock"]["blockers"] = []
    state["packageExists"] = True
    state["packageCurrent"] = True
    state["packageRevision"] = 7
    state["stages"]["storyboard"] = {"state": "approved"}
    state["stages"]["scenelook"] = {"state": "blocked", "sub": "plate stale"}
    state["shots"] = [{
        "shotId": "1.B1.S1",
        "label": "Waiting for current Scene Look approval",
        "badgeState": "locked",
        "current": {"keyframe": True, "animation": False},
    }]
    preflight = _preflight()
    preflight["blockers"] = [{
        "code": "SCENE_LOOK_NOT_CURRENT",
        "stage": "look",
        "message": "No current approved Scene Look plate is available.",
        "action": "Approve a current Scene Look plate.",
    }]
    intake = _intake()
    intake["canonicalCurrent"] = True
    _install(monkeypatch, intake, state, preflight)

    brief = agent.studio_agent_brief("1", "Ep1", "1.B1.S1")

    assert brief["selection"] == {
        "type": "shot", "shotId": "1.B1.S1", "resolved": True,
    }
    assert brief["context"]["shot"]["shotId"] == "1.B1.S1"
    assert brief["nextAction"]["stage"] == "scenelook"
    assert brief["nextAction"]["shotId"] is None


def test_missing_script_is_always_the_first_action(monkeypatch):
    intake = _intake()
    intake.update({"hasScript": False, "scriptName": None, "scriptVersionId": None})
    _install(monkeypatch, intake=intake)

    brief = agent.studio_agent_brief("1", "Ep1")

    assert brief["nextAction"]["stage"] == "script"
    assert brief["nextAction"]["label"] == (
        "Upload and register the script as an immutable version."
    )
    assert brief["nextAction"]["execution"]["canSpend"] is False


def test_plan_mode_prepares_work_without_resolving_canon_or_spending(monkeypatch):
    _, state, _ = _install(monkeypatch)
    state["qualityCompass"] = {
        "overall": "attention",
        "dimensions": [{
            "id": "story",
            "state": "attention",
            "directorQuestion": "Which signed source should govern this conflict?",
        }],
    }

    brief = agent.studio_agent_brief("1", "Ep1", mode="PLAN")

    assert brief["mode"] == "PLAN"
    assert brief["plan"]["objective"].startswith(
        "Reconcile the named canon/script conflict")
    assert brief["plan"]["humanDecisions"] == brief["decisions"]
    assert brief["plan"]["qualityQuestions"] == [
        "Which signed source should govern this conflict?",
    ]
    assert brief["plan"]["execution"] == {
        "available": False,
        "mode": "PLAN",
        "changesData": False,
        "canSpend": False,
        "reason": "PLAN mode can prepare a creative plan, but cannot execute work.",
    }
    assert "draft-zero-spend-plan" in brief["authority"]["may"]
    assert "change-canon" in brief["authority"]["mayNot"]


def test_agent_rejects_unknown_mode_before_any_provider_path(monkeypatch):
    _install(monkeypatch)

    try:
        agent.studio_agent_brief("1", "Ep1", mode="EXECUTE")
    except ValueError as exc:
        assert "HELP, PLAN" in str(exc)
    else:
        raise AssertionError("unknown agent mode should be rejected")
