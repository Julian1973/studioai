import pathlib

import cb_providers
import cb_studio_director
import cb_render


SHOT_ID = "S1.SH1"


def test_prepare_render_refreshes_stale_cinematography_before_sealing(monkeypatch):
    calls = []

    monkeypatch.setattr(
        cb_providers, "video_model",
        lambda require_enabled=True: type("Model", (), {"provider": "fal"})())
    monkeypatch.setattr(
        cb_render, "_require_confirmed_billing",
        lambda provider: calls.append(("billing", provider)))
    monkeypatch.setattr(
        cb_studio_director, "_direction_current",
        lambda scene, shot_id, stage, episode: stage == "animation")
    monkeypatch.setattr(
        cb_render, "prepare_department",
        lambda scene, stage, shot_id, episode, log: calls.append(("prepare", stage)))

    def fire(*_args, **_kwargs):
        calls.append(("fire", _kwargs["candidates"], _kwargs["spend_token"]))
        raise cb_render.Refused("SPEND NOT APPROVED")

    package = {
        "shots": [{"shotId": SHOT_ID, "sourceType": "opener"}],
        "continuityLedger": [{
            "shotId": SHOT_ID,
            "pendingSpendAuth": {"token": "sealed"},
        }],
    }
    monkeypatch.setattr(cb_render, "fire_shot", fire)
    monkeypatch.setattr(
        cb_render, "load_pkg", lambda scene, episode: (package, pathlib.Path("pkg.json")))
    monkeypatch.setattr(
        cb_render, "_ledger",
        lambda loaded, shot_id: loaded["continuityLedger"][0])

    cb_studio_director.prepare_render("1", SHOT_ID, log=lambda *_: None)

    assert calls == [
        ("billing", "fal"),
        ("prepare", "cinematography"),
        ("fire", 2, None),
    ]


def test_relay_shot_projects_source_harvest_as_its_opening_frame():
    media = {
        "shots": {
            "S1.A": {"finalFrame": "/engine/media/shots/S1.A_final.png"},
            "S1.B": {"vo": "/engine/media/shots/S1.B_voice.wav"},
        }
    }
    shot = {"shotId": "S1.B", "sourceType": "relay", "sourceShotId": "S1.A"}

    projected = cb_studio_director._opening_frame_media(shot, media)

    assert projected["keyframeApproved"] == "/engine/media/shots/S1.A_final.png"
    assert projected["keyframe"] == "/engine/media/shots/S1.A_final.png"
    assert projected["relayAnchor"] == "/engine/media/shots/S1.A_final.png"
    assert projected["vo"] == "/engine/media/shots/S1.B_voice.wav"
    assert "keyframeApproved" not in media["shots"]["S1.B"]


def test_failure_is_hidden_after_workflow_moves_to_another_phase():
    failure = {"operation": "director:refire-keyframe:S1.B cb_studio_director.py refire-keyframe"}

    assert cb_studio_director._failure_matches_phase(failure, "keyframe") is True
    assert cb_studio_director._failure_matches_phase(failure, "voice") is False


def _state(**current):
    return {
        "policyVersion": "test-policy",
        "episode": "Ep1",
        "scene": "1",
        "packageExists": True,
        "packageCurrent": True,
        "packageRevision": 3,
        "lineage": {"current": True},
        "stages": {"storyboard": {"state": "approved"}},
        "shots": [{
            "shotId": SHOT_ID,
            "talky": True,
            "badgeState": "ready",
            "current": {
                "keyframe": False,
                "voice": False,
                "animation": False,
                **current,
            },
            "pending": {"keyframe": False, "voice": False, "animation": False},
        }],
    }


def _package(pending_spend=None):
    return {
        "episode": "Ep1",
        "sceneNumber": "1",
        "sceneName": "DEEP WITHIN THE RAINFOREST",
        "shots": [{
            "shotId": SHOT_ID,
            "durationSec": 29,
            "purpose": "Fuzzby's comedy climb.",
            "charactersInFrame": ["Fuzzby", "Zenny"],
            "keyframePrompt": "STALE PACKAGE PROMPT MUST NEVER BE SHOWN",
        }],
        "continuityLedger": [{
            "shotId": SHOT_ID,
            "pendingSpendAuth": pending_spend,
        }],
    }


def _preflight(provider_ready=False):
    blocker = {
        "code": "VIDEO_PROVIDER_NOT_QUALIFIED",
        "stage": "configuration",
        "message": "Seedance 2.5 is not active for this account.",
        "action": "Activate and qualify the selected route.",
    }
    return {
        "episode": "Ep1",
        "scene": "1",
        "blockers": [] if provider_ready else [blocker],
        "productionInputs": {"shots": {SHOT_ID: {
            "keyframePrompt": "CURRENT EXACT KEYFRAME REQUEST",
            "keyframePromptHash": "abc123",
            "keyframePromptSource": "prepared",
            "keyframePromptHeadline": "Fuzzby enters too hot while Zenny stays calm.",
            "voiceLines": [{"speaker": "Fuzzby", "performedText": "[excited] Bizzy!"}],
            "voiceDirectionSource": "prepared",
        }}},
        "providerCapabilities": {
            "selectionReady": provider_ready,
            "selectedVideoModelId": "dreamina-seedance-2-5-260628",
        },
    }


def _media(**shot_media):
    return {"shots": {SHOT_ID: shot_media}}


def _session(state=None, preflight=None, package=None, media=None, jobs=None,
             animation_contract=None):
    return cb_studio_director.build_session(
        state=state or _state(),
        preflight=preflight or _preflight(),
        package=package or _package(),
        media=media or _media(),
        scene_look={"plateUrl": "/engine/media/world.png"},
        jobs=jobs or {},
        animation_contract=animation_contract,
    )


def test_direct_scene_is_an_explicit_provider_call():
    state = _state()
    state["packageCurrent"] = False
    state["stages"]["storyboard"] = {
        "state": "ready",
        "sub": "direct the scene from the current script",
    }
    session = _session(state=state, package={})
    assert session["phase"] == "story"
    assert session["primaryAction"] == {
        "id": "direct-scene",
        "label": "Direct scene",
        "paid": True,
        "destructive": False,
    }


def test_provider_route_does_not_block_keyframe_work():
    session = _session()
    assert session["status"] == "ready_to_fire"
    assert session["phase"] == "keyframe"
    assert session["primaryAction"]["id"] == "build-keyframe"
    assert session["artifact"]["url"] == "/engine/media/world.png"
    assert not session["providerReady"]


def test_shot_summaries_expose_stable_id_aliases():
    session = _session()
    selected = next(shot for shot in session["shots"] if shot["selected"])
    assert selected["id"] == SHOT_ID
    assert selected["shotId"] == SHOT_ID


def test_keyframe_review_uses_current_exact_request_not_stale_package_copy():
    state = _state()
    state["shots"][0]["pending"]["keyframe"] = True
    session = _session(
        state=state,
        media=_media(keyframeCandidate="/engine/media/candidate.png"),
    )
    assert session["status"] == "ready_to_review"
    assert {item["id"] for item in session["decisionActions"]} == {
        "accept-keyframe", "iterate-keyframe"
    }
    request = session["inspector"]["providerRequest"]
    assert request["authoritative"] is True
    assert request["prompt"] == "CURRENT EXACT KEYFRAME REQUEST"
    assert "STALE PACKAGE PROMPT" not in request["prompt"]


def test_approved_keyframe_suppresses_retained_rejection_history():
    ledger = {
        "keyframeApproval": {"approved": True, "path": "/approved.png"},
        "keyframeRejected": {"reason": "An older candidate was wrong."},
    }
    comms = cb_studio_director._keyframe_stage_comms(
        ledger, "ready_to_fire", {"url": "/approved.png"})
    assert comms["title"] == "Keyframe accepted"
    assert "HEAR" in comms["nextAction"]
    assert "rejected" not in comms["message"].lower()


def test_voice_is_the_next_visible_outcome_after_keyframe_acceptance():
    session = _session(
        state=_state(keyframe=True),
        media=_media(keyframeApproved="/engine/media/accepted.png"),
    )
    assert session["phase"] == "voice"
    assert session["primaryAction"]["id"] == "build-voice"
    assert session["artifact"]["url"] == "/engine/media/accepted.png"
    assert session["inspector"]["providerRequest"]["lines"][0]["speaker"] == "Fuzzby"


def test_voice_phase_exposes_prepared_watch_prompt_without_unlocking_render():
    package = _package()
    package["continuityLedger"][0]["departmentWork"] = {
        "animation": {"candidate": {
            "preparedBy": "deterministic compiler",
            "output": {
                "durationSec": 15,
                "providerPrompt": "CURRENT PREPARED WATCH PROMPT WITH ENOUGH CREATIVE DIRECTION",
            },
            "preflight": {
                "score": 9.75,
                "verdict": "PASS",
                "findings": [{"rule": "length", "message": "Long but valid."}],
            },
        }},
    }
    session = _session(
        state=_state(keyframe=True),
        package=package,
        media=_media(keyframeApproved="/engine/media/accepted.png"),
    )

    assert session["phase"] == "voice"
    assert session["primaryAction"]["id"] == "build-voice"
    assert session["inspector"]["providerRequest"]["kind"] == "voice"
    preview = session["inspector"]["preparedAnimationRequest"]
    assert preview["prompt"].startswith("CURRENT PREPARED WATCH PROMPT")
    assert preview["conformance"]["score"] == 9.75
    assert preview["conformance"]["verdict"] == "PASS"
    assert preview["renderReady"] is False
    assert all(action["id"] != "approve-spend" for action in session["decisionActions"])


def test_seedance_qualification_blocks_only_the_animation_phase_with_an_outcome():
    session = _session(state=_state(keyframe=True, voice=True))
    assert session["phase"] == "animation"
    assert session["status"] == "blocked"
    assert session["primaryAction"]["id"] == "open-provider-setup"
    assert session["blocker"]["code"] == "VIDEO_PROVIDER_NOT_QUALIFIED"


def test_spend_token_never_leaves_the_server_projection():
    pending = {
        "token": "secret-single-use-token",
        "disclosure": {
            "shotId": SHOT_ID,
            "candidateCount": 1,
            "maxBatchCostUsd": 1.25,
            "bindingHash": "binding",
            "providerModelId": "seedance-2.5",
        },
    }
    session = _session(
        state=_state(keyframe=True, voice=True, animationDirection=True),
        preflight=_preflight(provider_ready=True),
        package=_package(pending),
        animation_contract={
            "verdict": "passed",
            "finalPrompt": "CURRENT EXACT ANIMATION REQUEST",
            "checks": {
                "promptSource": "animation-director-current",
                "durationSec": 29,
                "resolution": "480p",
                "model": "fal-seedance-2.5",
                "emissionConformance": {
                    "score": 9.75,
                    "verdict": "PASS",
                    "findings": [{
                        "severity": "POLISH",
                        "rule": "length",
                        "message": "Emission is long.",
                        "fix": "Compact plumbing only.",
                        "deduction": 0.25,
                    }],
                },
            },
        },
    )
    assert session["status"] == "ready_to_review"
    assert session["decisionActions"][0]["id"] == "approve-spend"
    assert session["spendDisclosure"]["maxBatchCostUsd"] == 1.25
    assert "secret-single-use-token" not in str(session)
    assert session["inspector"]["providerRequest"]["prompt"] == (
        "CURRENT EXACT ANIMATION REQUEST")
    assert session["inspector"]["providerRequest"]["resolution"] == "480p"
    assert session["inspector"]["providerRequest"]["durationSec"] == 29
    assert session["inspector"]["providerRequest"]["conformance"] == {
        "score": 9.75,
        "maximum": 10,
        "verdict": "PASS",
        "checkerVerdict": "PASS",
        "findings": [{
            "severity": "POLISH",
            "rule": "length",
            "message": "Emission is long.",
            "fix": "Compact plumbing only.",
            "deduction": 0.25,
        }],
    }


def test_animation_request_without_checker_report_fails_visible_conformance_closed():
    session = _session(
        state=_state(keyframe=True, voice=True, animationDirection=True),
        preflight=_preflight(provider_ready=True),
        animation_contract={
            "verdict": "passed",
            "finalPrompt": "UNCHECKED ANIMATION REQUEST",
            "checks": {"durationSec": 29, "resolution": "480p", "model": "seedance"},
        },
    )
    report = session["inspector"]["providerRequest"]["conformance"]
    assert report["score"] == 0.0
    assert report["verdict"] == "BLOCK"
    assert report["findings"][0]["rule"] == "checker-report"


def test_dense_animation_spend_projection_warns_before_one_shot_render():
    pending = {
        "token": "secret-single-use-token",
        "disclosure": {
            "shotId": SHOT_ID,
            "candidateCount": 1,
            "maxBatchCostUsd": 1.25,
            "providerModelId": "seedance-2.5",
        },
    }
    package = _package(pending)
    package["shots"][0].update({
        "purpose": "Fast chase, flower moustache reveal and crash recovery.",
        "visualPayoff": "Fuzzby pops out of the flower after the crash.",
        "storyboardStagePlanApproved": [{
            "primaryEvent": "Fuzzby barrels through a drone chase and crashes into a flower.",
            "observableEndState": "The flower moustache is readable.",
        }],
    })
    session = _session(
        state=_state(keyframe=True, voice=True, animationDirection=True),
        preflight=_preflight(provider_ready=True),
        package=package,
        animation_contract={
            "verdict": "passed",
            "finalPrompt": "CURRENT EXACT ANIMATION REQUEST",
            "checks": {"durationSec": 29, "resolution": "480p", "model": "fal-seedance-2.5"},
        },
    )
    assert session["status"] == "ready_to_review"
    assert session["advisories"][0]["code"] == "DENSE_UNIT_REVIEW"
    assert "protected split units" in session["advisories"][0]["nextAction"]
    assert {"chase", "crash", "flower", "moustache"}.issubset(
        set(session["advisories"][0]["signals"]))


def test_dense_animation_candidate_review_also_warns_against_blind_retry():
    package = _package()
    package["shots"][0].update({
        "purpose": "Fast chase, flower moustache reveal and crash recovery.",
        "visualPayoff": "Fuzzby pops out of the flower after the crash.",
    })
    state = _state(keyframe=True, voice=True, animationDirection=True)
    state["shots"][0]["pending"]["animation"] = True
    session = _session(
        state=state,
        preflight=_preflight(provider_ready=True),
        package=package,
        media=_media(candidates=[{"n": 1, "url": "/engine/media/c1.mp4"}]),
    )
    assert session["status"] == "ready_to_review"
    assert session["decisionActions"][1]["id"] == "iterate-animation"
    assert session["advisories"][0]["code"] == "DENSE_UNIT_REVIEW"
    assert "ready for review" in session["advisories"][0]["message"]


def test_superseded_render_candidates_remain_visible_but_not_approvable():
    package = _package()
    package["continuityLedger"][0]["batch"] = {
        "status": "complete",
        "approvalBlockedReason": "Director inputs were recompiled after these candidates were generated",
        "supersededByDirectionAt": "2026-08-10T12:58:44Z",
    }
    session = _session(
        state=_state(keyframe=True, voice=True, animationDirection=True),
        preflight=_preflight(provider_ready=True),
        package=package,
        media=_media(candidates=[
            {"n": 1, "url": "/engine/media/c1.mp4"},
            {"n": 2, "url": "/engine/media/c2.mp4"},
        ]),
    )
    assert session["status"] == "ready_to_fire"
    assert session["artifact"] == {
        "type": "video-set",
        "items": [
            {"n": 1, "url": "/engine/media/c1.mp4"},
            {"n": 2, "url": "/engine/media/c2.mp4"},
        ],
        "label": "Superseded animation candidates",
        "stale": True,
        "notice": "Director inputs were recompiled after these candidates were generated",
        "supersededAt": "2026-08-10T12:58:44Z",
    }
    assert session["primaryAction"]["id"] == "prepare-render"
    assert session["decisionActions"] == []


def test_running_job_replaces_actions_with_one_progress_state():
    jobs = {"job-1": {
        "jobId": "job-1",
        "scene": "1",
        "gate": f"director:build-keyframe:{SHOT_ID}",
        "status": "running",
        "step": "Rendering opening frame...",
        "started": 100,
        "log": "Submitting request...\nProvider is rendering candidate 1.",
        "args": ["cb_studio_director.py", "build-keyframe", "1", SHOT_ID, "Ep1"],
    }}
    session = _session(jobs=jobs)
    assert session["status"] == "rendering"
    assert session["primaryAction"] is None
    assert session["decisionActions"] == []
    assert session["runningJob"]["step"] == "Rendering opening frame..."
    assert session["runningJob"]["latestMessage"] == "Provider is rendering candidate 1."
    assert session["runningJob"]["durationSec"] == 29
    assert session["stageComms"]["title"] == "Work in progress"


def test_running_keyframe_schema_refresh_is_explained_in_plain_english():
    jobs = {"job-1": {
        "jobId": "job-1", "scene": "1",
        "gate": f"director:refire-keyframe:{SHOT_ID}",
        "status": "running",
        "step": "DEPARTMENT REJECTED - cinematography by Studio contract migration",
        "started": 100,
        "log": "DEPARTMENT REJECTED - cinematography by Studio contract migration",
        "args": ["cb_studio_director.py", "refire-keyframe", "1", SHOT_ID],
    }}
    running = _session(jobs=jobs)["runningJob"]
    assert running["step"] == "Refreshing the shot direction before keyframe generation..."
    assert "opening-frame generation follows automatically" in running["latestMessage"]


def test_running_render_exposes_safe_batch_progress_details():
    package = _package()
    package["continuityLedger"][0]["batch"] = {
        "batchId": "batch-1",
        "status": "generating",
        "expected": 1,
        "disclosure": {
            "providerModelId": "fal-seedance-2.5",
            "shotDurationSec": 29,
            "candidateCount": 1,
            "maxBatchCostUsd": 13.72,
        },
    }
    jobs = {"job-1": {
        "jobId": "job-1", "scene": "1", "gate": f"director:render-animation:{SHOT_ID}",
        "status": "running", "step": "Rendering the clip...", "started": 100,
        "args": [SHOT_ID],
    }}
    running = _session(package=package, jobs=jobs)["runningJob"]
    assert running["batchId"] == "batch-1"
    assert running["providerModelId"] == "fal-seedance-2.5"
    assert running["candidateCount"] == 1
    assert running["maxBatchCostUsd"] == 13.72


def test_completed_candidate_is_visible_while_remaining_candidate_renders():
    package = _package()
    package["continuityLedger"][0]["batch"] = {
        "batchId": "batch-1",
        "status": "generating",
        "expected": 2,
        "done": [1],
        "disclosure": {"candidateCount": 2},
    }
    jobs = {"job-1": {
        "jobId": "job-1", "scene": "1",
        "gate": f"director:render-animation:{SHOT_ID}",
        "status": "running", "step": "Rendering candidate 2...", "started": 100,
        "args": [SHOT_ID],
    }}
    session = _session(
        state=_state(keyframe=True, voice=True, animationDirection=True),
        preflight=_preflight(provider_ready=True),
        package=package,
        media=_media(candidates=[{"n": 1, "url": "/engine/media/c1.mp4"}]),
        jobs=jobs,
    )
    assert session["status"] == "rendering"
    assert session["artifact"] == {
        "type": "video-set",
        "items": [{"n": 1, "url": "/engine/media/c1.mp4"}],
        "label": "Completed render candidates",
        "partial": True,
    }
    assert session["runningJob"]["completedCandidateCount"] == 1
    assert session["stageComms"]["artifactVisible"] is True
    assert "1 of 2" in session["stageComms"]["message"]
    assert session["decisionActions"] == []


def test_running_progress_does_not_expose_sensitive_log_lines():
    jobs = {"job-1": {
        "jobId": "job-1", "scene": "1", "gate": f"director:render-animation:{SHOT_ID}",
        "status": "running", "step": "Rendering", "started": 100,
        "args": [SHOT_ID], "log": "Provider accepted request\napi_key=do-not-expose",
    }}
    assert _session(jobs=jobs)["runningJob"]["latestMessage"] == "Provider accepted request"


def test_refire_keyframe_rejects_then_builds_replacement(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cb_render, "reject_keyframe",
        lambda scene, shot_id, correction, episode, log=print:
            calls.append(("reject", scene, shot_id, correction, episode)))
    monkeypatch.setattr(
        cb_studio_director, "build_keyframe",
        lambda scene, shot_id, episode, log=print:
            calls.append(("build", scene, shot_id, episode)))

    cb_studio_director.refire_keyframe(
        "1", SHOT_ID, "Give Fuzzby more lead room", "Ep1", log=lambda *_: None)

    assert calls == [
        ("reject", "1", SHOT_ID, "Give Fuzzby more lead room", "Ep1"),
        ("build", "1", SHOT_ID, "Ep1"),
    ]


def test_build_keyframe_refreshes_legacy_direction_before_provider_call(monkeypatch):
    work = {
        "approved": None,
        "candidate": {"output": {"complete": False}},
        "history": [],
    }
    ledger = {"departmentWork": {"cinematography": work}}
    package = {"shots": [{"shotId": SHOT_ID}], "continuityLedger": [ledger]}
    calls = []

    monkeypatch.setattr(cb_render, "load_pkg", lambda *_: (package, None))
    monkeypatch.setattr(cb_render, "_shot", lambda *_: package["shots"][0])
    monkeypatch.setattr(cb_render, "_ledger", lambda *_: ledger)

    def check_contract(direction, _shot):
        if not direction.get("complete"):
            raise cb_render.Refused("legacy")

    def decide(_scene, _stage, verdict, **_kwargs):
        calls.append(verdict)
        if verdict == "rejected":
            work["candidate"] = None
        else:
            work["approved"] = work["candidate"]
            work["candidate"] = None

    def prepare(*_args, **_kwargs):
        calls.append("prepare")
        work["candidate"] = {"output": {"complete": True}}

    monkeypatch.setattr(cb_render, "_keyframe_direction_contract", check_contract)
    monkeypatch.setattr(cb_render, "decide_department", decide)
    monkeypatch.setattr(cb_render, "prepare_department", prepare)
    monkeypatch.setattr(
        cb_render, "keyframe_shot", lambda *_args, **_kwargs: calls.append("keyframe"))

    cb_studio_director.build_keyframe("1", SHOT_ID, "Ep1", log=lambda *_: None)

    assert calls == ["rejected", "prepare", "approved", "keyframe"]


def test_older_failure_is_hidden_after_newer_completed_action():
    jobs = {
        "old-failure": {
            "jobId": "old-failure", "scene": "1",
            "gate": f"director:prepare-render:{SHOT_ID}", "status": "failed",
            "started": 100, "ended": 120,
            "step": "providerPrompt is over the old ceiling",
            "log": "Value error, providerPrompt is over the old ceiling",
            "args": [SHOT_ID],
        },
        "new-keyframe": {
            "jobId": "new-keyframe", "scene": "1",
            "gate": f"director:build-keyframe:{SHOT_ID}", "status": "done",
            "started": 200, "ended": 240, "step": "Done.", "log": "Done.",
            "args": [SHOT_ID],
        },
    }
    session = _session(jobs=jobs)
    assert session["recentFailure"] is None


def test_latest_failed_action_is_still_reported():
    jobs = {
        "old-success": {
            "jobId": "old-success", "scene": "1",
            "gate": f"director:build-keyframe:{SHOT_ID}", "status": "done",
            "started": 100, "ended": 120, "step": "Done.", "log": "Done.",
            "args": [SHOT_ID],
        },
        "new-failure": {
            "jobId": "new-failure", "scene": "1",
            "gate": f"director:prepare-render:{SHOT_ID}", "status": "failed",
            "started": 200, "ended": 220, "step": "Failed.",
            "log": "REFUSED - current request could not be compiled",
            "args": [SHOT_ID],
        },
    }
    failure = _session(jobs=jobs)["recentFailure"]
    assert failure["jobId"] == "new-failure"
    assert "REFUSED" in failure["error"]


def test_allowed_actions_are_derived_from_the_current_session_only():
    session = _session()
    assert cb_studio_director.allowed_action_ids(session) == {
        "build-keyframe",
        "build-scene-plate",
        "select-scene-plate-library",
        "select-scene-plate-upload",
    }


def test_completed_animation_flows_to_quality_review_then_master():
    state = _state(keyframe=True, voice=True, animation=True, directorReview=False)
    session = _session(
        state=state,
        preflight=_preflight(provider_ready=True),
        media=_media(clip="/engine/media/accepted.mp4"),
    )
    assert session["phase"] == "review"
    assert session["primaryAction"]["id"] == "run-quality-review"
    assert session["artifact"]["url"] == "/engine/media/accepted.mp4"

    state["shots"][0]["current"]["directorReview"] = True
    state["stages"]["final"] = {"state": "ready"}
    state["postProduction"] = {
        "candidate": {"exists": False, "current": False},
        "approved": {"exists": False, "current": False},
    }
    session = _session(state=state, preflight=_preflight(provider_ready=True))
    assert session["phase"] == "final"
    assert session["primaryAction"]["id"] == "build-master"


def test_quality_review_candidate_has_confirm_or_reopen_outcomes():
    state = _state(keyframe=True, voice=True, animation=True, directorReview=False)
    state["shots"][0]["pending"]["directorReview"] = True
    package = _package()
    package["continuityLedger"][0]["departmentWork"] = {
        "review-animation": {
            "candidate": {"output": {
                "verdict": "pass",
                "actualRead": "Fuzzby's chaos and Zenny's stillness both read clearly.",
            }}
        }
    }
    session = _session(
        state=state,
        package=package,
        preflight=_preflight(provider_ready=True),
        media=_media(clip="/engine/media/accepted.mp4"),
    )
    assert {action["id"] for action in session["decisionActions"]} == {
        "accept-quality", "reopen-shot"
    }
    assert session["qualityReview"]["verdict"] == "pass"


def test_reopen_accepted_take_archives_evidence_and_invalidates_post(tmp_path, monkeypatch):
    take = tmp_path / "accepted.mp4"
    harvest = tmp_path / "final.png"
    take.write_bytes(b"accepted-take")
    harvest.write_bytes(b"final-frame")
    (tmp_path / "accepted.mp4.review.json").write_text("{}")
    package = {
        "shots": [{"shotId": SHOT_ID}],
        "continuityLedger": [{
            "shotId": SHOT_ID,
            "status": "approved",
            "approvedTake": str(take),
            "approvedCandidate": 1,
            "harvestFrame": str(harvest),
            "approval": {"approved": True, "reviewed_by": "Julian"},
            "candidatePaths": [str(take)],
            "batchId": "batch-1",
            "batch": {"status": "complete"},
            "departmentWork": {
                "review-animation": {
                    "candidate": {"output": {"verdict": "needs-work"}},
                    "approved": None,
                    "history": [],
                }
            },
        }],
        "postProduction": {
            "candidate": {"manifest": {"manifestDigest": "old"}},
            "approved": None,
            "history": [],
        },
        "departmentWork": {
            "review-final": {
                "candidate": {"output": {"verdict": "pass"}},
                "approved": None,
                "history": [],
            }
        },
    }
    saved = []
    monkeypatch.setattr(cb_render, "HERE", tmp_path)
    monkeypatch.setattr(cb_render, "load_pkg", lambda scene, episode: (package, tmp_path / "pkg.json"))
    monkeypatch.setattr(cb_render, "_save", lambda pkg, path: saved.append((pkg, path)))
    archive = cb_render.reopen_approved_shot(
        "1", SHOT_ID, "The emotional turn does not read.", episode="Ep1")

    ledger = package["continuityLedger"][0]
    assert ledger["status"] == "designed"
    assert ledger["approvedTake"] is None and ledger["approval"] is None
    assert not take.exists() and not harvest.exists()
    assert (tmp_path / "accepted.mp4.review.json").exists() is False
    assert package["postProduction"]["candidate"] is None
    assert package["departmentWork"]["review-final"]["candidate"] is None
    assert ledger["renderHistory"][-1]["outcome"] == "accepted-take-reopened"
    assert archive.startswith(str(tmp_path / "media" / "archive" / "shots_reopened"))
    assert saved


def test_import_approved_take_copies_media_records_provenance_and_harvests(tmp_path, monkeypatch):
    source = tmp_path / "golden.mp4"
    source.write_bytes(b"golden-video")
    package = {
        "shots": [{"shotId": SHOT_ID}],
        "continuityLedger": [{
            "shotId": SHOT_ID,
            "status": "designed",
            "approvedTake": None,
            "renderHistory": [],
        }],
    }
    saved = []
    monkeypatch.setattr(cb_render, "HERE", tmp_path)
    monkeypatch.setattr(cb_render, "MEDIA", tmp_path / "media" / "shots")
    monkeypatch.setattr(cb_render, "load_pkg", lambda scene, episode: (package, tmp_path / "pkg.json"))
    monkeypatch.setattr(cb_render, "_save", lambda pkg, path: saved.append((pkg, path)))
    monkeypatch.setattr(cb_render, "_animation_generation_signature",
                        lambda *args, **kwargs: {"graph": "current", "tier": "standard"})
    monkeypatch.setattr(
        cb_render.cb_gen, "last_frame",
        lambda selected, out: pathlib.Path(out).write_bytes(b"harvest"))

    imported = cb_render.import_approved_take(
        "1", SHOT_ID, source, reviewed_by="Julian", source_label="Flova",
        provenance={"fixture": "beat_1_chase.txt"})

    ledger = package["continuityLedger"][0]
    assert pathlib.Path(imported).read_bytes() == b"golden-video"
    assert pathlib.Path(ledger["harvestFrame"]).read_bytes() == b"harvest"
    assert ledger["status"] == "approved"
    assert ledger["approval"]["source"] == "approved-external-import"
    assert ledger["approval"]["reviewed_by"] == "Julian"
    assert ledger["approval"]["inputSignature"]["graph"] == "current"
    assert ledger["renderHistory"][-1]["provenance"]["fixture"] == "beat_1_chase.txt"
    assert pathlib.Path(imported + ".import.json").is_file()
    assert saved


def test_import_director_accepted_external_take_marks_audio_as_post_lane(tmp_path, monkeypatch):
    source = tmp_path / "accepted-section.mp4"
    source.write_bytes(b"accepted-section")
    package = {
        "shots": [{"shotId": SHOT_ID}],
        "continuityLedger": [{"shotId": SHOT_ID, "status": "designed"}],
    }
    monkeypatch.setattr(cb_render, "HERE", tmp_path)
    monkeypatch.setattr(cb_render, "MEDIA", tmp_path / "media" / "shots")
    monkeypatch.setattr(cb_render, "load_pkg", lambda scene, episode: (package, tmp_path / "pkg.json"))
    monkeypatch.setattr(cb_render, "_save", lambda pkg, path: None)
    monkeypatch.setattr(cb_render, "_external_import_input_signature",
                        lambda *args, **kwargs: {"graph": "external-current"})
    monkeypatch.setattr(
        cb_render.cb_gen, "last_frame",
        lambda selected, out: pathlib.Path(out).write_bytes(b"harvest"))

    cb_render.import_approved_take(
        "1", SHOT_ID, source, reviewed_by="Julian", source_label="Flova section 2",
        provenance={"accepted": True}, approval_mode="external-director-accepted")

    ledger = package["continuityLedger"][0]
    assert ledger["approval"]["source"] == "external-director-accepted"
    assert ledger["approval"]["inputSignature"]["graph"] == "external-current"
    assert ledger["audioProvenance"]["postLaneStatus"] == "required"
    assert ledger["audioProvenance"]["dialogueAuthority"] == (
        "approved-voice-master-required-in-post")


def test_review_animation_signature_allows_external_director_accepted_take(tmp_path, monkeypatch):
    take = tmp_path / "accepted-section.mp4"
    take.write_bytes(b"accepted-section")
    package = {
        "revision": 4,
        "validation": {"passed": True},
        "shots": [{"shotId": SHOT_ID, "dialogueLines": [{"speaker": "Fuzzby"}]}],
        "continuityLedger": [{
            "shotId": SHOT_ID,
            "status": "approved",
            "approvedTake": str(take),
            "approval": {
                "source": "external-director-accepted",
                "inputSignature": {"graph": "external-current"},
                "contentHash": "accepted-hash",
            },
        }],
    }
    monkeypatch.setattr(cb_render, "load_pkg", lambda scene, episode: (package, tmp_path / "pkg.json"))
    monkeypatch.setattr(cb_render, "_save", lambda pkg, path: None)
    monkeypatch.setattr(cb_render, "_require_current_lineage", lambda pkg, scene, episode: None)

    def fail_generation_signature(*_args, **_kwargs):
        raise AssertionError("external accepted review must not require Seedance generation signature")

    monkeypatch.setattr(cb_render, "_animation_generation_signature", fail_generation_signature)

    work, _ = cb_render._department_container(package, "1", SHOT_ID, "review-animation", "Ep1")
    work["candidate"] = {
        "output": {"artifactType": "animation", "verdict": "pass"},
        "inputSignature": cb_render._department_input_signature(
            package, "review-animation", SHOT_ID, "1", "Ep1"),
    }

    cb_render.decide_department(
        "1", "review-animation", "approved", shot_id=SHOT_ID,
        episode="Ep1", reviewed_by="Julian")

    approved = package["continuityLedger"][0]["departmentWork"]["review-animation"]["approved"]
    assert approved["inputSignature"]["externalImportApprovalSignature"] == {
        "graph": "external-current"}
    assert approved["inputSignature"]["generationSignature"] is None
