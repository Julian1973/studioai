import cb_studio_director
import cb_render


SHOT_ID = "S1.SH1"


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


def test_voice_is_the_next_visible_outcome_after_keyframe_acceptance():
    session = _session(
        state=_state(keyframe=True),
        media=_media(keyframeApproved="/engine/media/accepted.png"),
    )
    assert session["phase"] == "voice"
    assert session["primaryAction"]["id"] == "build-voice"
    assert session["artifact"]["url"] == "/engine/media/accepted.png"
    assert session["inspector"]["providerRequest"]["lines"][0]["speaker"] == "Fuzzby"


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
            "checks": {"promptSource": "animation-director-current"},
        },
    )
    assert session["status"] == "ready_to_review"
    assert session["decisionActions"][0]["id"] == "approve-spend"
    assert session["spendDisclosure"]["maxBatchCostUsd"] == 1.25
    assert "secret-single-use-token" not in str(session)
    assert session["inspector"]["providerRequest"]["prompt"] == (
        "CURRENT EXACT ANIMATION REQUEST")


def test_running_job_replaces_actions_with_one_progress_state():
    jobs = {"job-1": {
        "jobId": "job-1",
        "scene": "1",
        "gate": f"director:build-keyframe:{SHOT_ID}",
        "status": "running",
        "step": "Rendering opening frame...",
        "started": 100,
        "args": ["cb_studio_director.py", "build-keyframe", "1", SHOT_ID, "Ep1"],
    }}
    session = _session(jobs=jobs)
    assert session["status"] == "rendering"
    assert session["primaryAction"] is None
    assert session["decisionActions"] == []
    assert session["runningJob"]["step"] == "Rendering opening frame..."


def test_allowed_actions_are_derived_from_the_current_session_only():
    session = _session()
    assert cb_studio_director.allowed_action_ids(session) == {"build-keyframe"}


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
