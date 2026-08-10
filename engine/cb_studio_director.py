#!/usr/bin/env python3
"""Outcome-first Director facade for the canonical production engine.

The existing engine remains authoritative for canon, lineage, approvals, provider routing,
spend and media.  This module only projects that state into one creative decision at a time
and provides three narrowly scoped orchestration commands used by the Studio server.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from typing import Any


SCHEMA_VERSION = 1
SESSION_STATES = {
    "preparing", "ready_to_fire", "rendering", "ready_to_review", "blocked", "complete"
}
_SENSITIVE_PROGRESS = re.compile(
    r"(?:api[-_ ]?key|authorization|bearer|secret|spend[-_ ]?token|launch[-_ ]?token)\s*[:=]",
    re.IGNORECASE,
)
_COMPLEXITY_SIGNALS = (
    "chase", "tumble", "crash", "collision", "reveal", "moustache", "mustache",
    "flower", "stamen", "gymnastic", "physical comedy", "fast", "drone",
)


def _action(action_id: str, label: str, *, paid: bool = False,
            destructive: bool = False, candidate: int | None = None) -> dict[str, Any]:
    action = {
        "id": action_id,
        "label": label,
        "paid": paid,
        "destructive": destructive,
    }
    if candidate is not None:
        action["candidate"] = candidate
    return action


def _shot_map(package: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        shot.get("shotId"): shot
        for shot in ((package or {}).get("shots") or [])
        if shot.get("shotId")
    }


def _latest_running_job(jobs: dict[str, Any] | None, scene: str,
                        shot_id: str | None) -> dict[str, Any] | None:
    matches = []
    for job in (jobs or {}).values():
        if job.get("status") != "running" or str(job.get("scene")) != str(scene):
            continue
        gate = str(job.get("gate") or "")
        args = [str(value) for value in (job.get("args") or [])]
        if shot_id and shot_id not in gate and shot_id not in args:
            continue
        matches.append(job)
    if not matches:
        return None
    job = max(matches, key=lambda item: float(item.get("started") or 0))
    log_lines = [line.strip() for line in str(job.get("log") or "").splitlines()
                 if line.strip() and not _SENSITIVE_PROGRESS.search(line)]
    gate = str(job.get("gate") or "")
    args_text = " ".join(str(value) for value in (job.get("args") or []))
    operation_text = f"{gate} {args_text}".lower()
    if ("build-keyframe" in operation_text or "refire-keyframe" in operation_text or
            ":keyframe" in operation_text):
        activity_label = "Keyframe build in progress"
        fallback_step = "Building the opening keyframe..."
    elif "build-voice" in operation_text or "voice-shot" in operation_text:
        activity_label = "Voice generation in progress"
        fallback_step = "Creating the approved dialogue performance..."
    elif "prepare-render" in operation_text:
        activity_label = "Preparing animation request"
        fallback_step = "Preparing the animation request for approval..."
    elif "approve-spend" in operation_text or " cb_render.py fire " in f" {operation_text} ":
        activity_label = "Render in progress"
        fallback_step = "Submitting the approved Seedance render..."
    else:
        activity_label = "Production job in progress"
        fallback_step = "Building the next result..."
    raw_step = str(job.get("step") or "").strip()
    latest_message = log_lines[-1][:300] if log_lines else None
    if activity_label == "Keyframe build in progress" and raw_step.startswith("DEPARTMENT"):
        fallback_step = "Refreshing the shot direction before keyframe generation..."
        latest_message = (
            "The Studio is upgrading the older direction record to the current keyframe "
            "contract. The opening-frame generation follows automatically."
        )
    return {
        "jobId": job.get("jobId"),
        "status": job.get("status"),
        "activityLabel": activity_label,
        "step": fallback_step if raw_step.startswith("DEPARTMENT") else raw_step or fallback_step,
        "started": job.get("started"),
        "latestMessage": latest_message,
    }


def _latest_failed_job(jobs: dict[str, Any] | None, scene: str,
                       shot_id: str | None) -> dict[str, Any] | None:
    matches = []
    for job in (jobs or {}).values():
        if str(job.get("scene")) != str(scene):
            continue
        gate = str(job.get("gate") or "")
        args = [str(value) for value in (job.get("args") or [])]
        if shot_id and shot_id not in gate and shot_id not in args:
            continue
        matches.append(job)
    if not matches:
        return None
    job = max(matches, key=lambda item: float(item.get("ended") or item.get("started") or 0))
    # "Last action failed" must describe the latest action for this shot. Keeping an
    # older failure after a newer successful/refired action makes the Studio report a
    # false current state and sends the director back into an already-resolved problem.
    if job.get("status") != "failed":
        return None
    lines = [line.strip() for line in str(job.get("log") or "").splitlines()
             if line.strip() and not _SENSITIVE_PROGRESS.search(line)]
    detail = next((line for line in reversed(lines)
                   if "errors.pydantic.dev" not in line and
                   re.search(r"refused|error|failed|invalid|rejected", line, re.I)), None)
    return {
        "jobId": job.get("jobId"),
        "status": "failed",
        "error": job.get("error") or detail or job.get("step") or "The provider job failed.",
        "ended": job.get("ended"),
    }


def _shot_complete(shot_state: dict[str, Any]) -> bool:
    return bool((shot_state.get("current") or {}).get("animation"))


def _choose_shot(state: dict[str, Any], requested_shot_id: str | None) -> dict[str, Any] | None:
    shots = state.get("shots") or []
    if requested_shot_id:
        selected = next((shot for shot in shots if shot.get("shotId") == requested_shot_id), None)
        animations_complete = bool(shots) and all(_shot_complete(shot) for shot in shots)
        if selected and (not animations_complete or
                         not (selected.get("current") or {}).get("directorReview")):
            return selected
    animation_target = next((shot for shot in shots if not _shot_complete(shot)), None)
    if animation_target:
        return animation_target
    review_target = next((shot for shot in shots
                          if not (shot.get("current") or {}).get("directorReview")), None)
    return review_target or (shots[0] if shots else None)


def _provider_blocker(preflight: dict[str, Any]) -> dict[str, Any] | None:
    return next((blocker for blocker in (preflight.get("blockers") or [])
                 if blocker.get("code") == "VIDEO_PROVIDER_NOT_QUALIFIED"), None)


def _prompt_contract(preflight: dict[str, Any], shot_id: str | None,
                     phase: str, animation_contract: dict[str, Any] | None) -> dict[str, Any] | None:
    if not shot_id:
        return None
    production_inputs = preflight.get("productionInputs") or {}
    shot_inputs = (production_inputs.get("shots") or {}).get(shot_id) or {}
    if phase == "keyframe" and shot_inputs.get("keyframePrompt"):
        return {
            "kind": "keyframe",
            "authoritative": True,
            "source": shot_inputs.get("keyframePromptSource") or "current-direction",
            "prompt": shot_inputs["keyframePrompt"],
            "promptHash": shot_inputs.get("keyframePromptHash") or hashlib.sha256(
                shot_inputs["keyframePrompt"].encode()).hexdigest(),
        }
    if phase == "voice" and shot_inputs.get("voiceLines"):
        return {
            "kind": "voice",
            "authoritative": True,
            "source": shot_inputs.get("voiceDirectionSource") or "current-direction",
            "lines": shot_inputs["voiceLines"],
        }
    final_prompt = str((animation_contract or {}).get("finalPrompt") or "").strip()
    if phase in ("animation", "review", "final") and final_prompt:
        contract_checks = (animation_contract or {}).get("checks") or {}
        emission = contract_checks.get("emissionConformance") or {
            "score": 0.0,
            "verdict": "BLOCK",
            "findings": [{
                "severity": "FATAL",
                "rule": "checker-report",
                "message": "The authoritative emission checker did not supply a report.",
                "fix": "Recompile this shot before rendering.",
                "deduction": 10.0,
            }],
        }
        return {
            "kind": "animation",
            "authoritative": True,
            "source": ((animation_contract or {}).get("checks") or {}).get("promptSource")
                      or "current-direction",
            "prompt": final_prompt,
            "promptHash": hashlib.sha256(final_prompt.encode()).hexdigest(),
            "verdict": (animation_contract or {}).get("verdict"),
            "warnings": (animation_contract or {}).get("warnings") or [],
            "blockers": (animation_contract or {}).get("blockers") or [],
            "durationSec": contract_checks.get("durationSec"),
            "resolution": contract_checks.get("resolution"),
            "providerModelId": contract_checks.get("model"),
            "conformance": {
                "score": emission.get("score"),
                "maximum": 10,
                "verdict": "PASS" if emission.get("verdict") == "PASS" else "BLOCK",
                "checkerVerdict": emission.get("verdict"),
                "findings": list(emission.get("findings") or [])[:3],
            },
        }
    return None


def _spend_disclosure(package: dict[str, Any] | None, shot_id: str | None) -> dict[str, Any] | None:
    if not package or not shot_id:
        return None
    ledger = next((item for item in (package.get("continuityLedger") or [])
                   if item.get("shotId") == shot_id), {})
    disclosure = ((ledger.get("pendingSpendAuth") or {}).get("disclosure") or {})
    if not disclosure:
        return None
    allowed = (
        "shotId", "candidateCount", "costPerCandidateUsd", "maxBatchCostUsd",
        "promptVersion", "bindingHash", "envelopeHash", "packageRevision",
        "rerollOfUnchangedPackage", "shotDurationSec", "provider", "providerModelId",
        "modelVersion", "resolution", "tier", "internalProviderCalls",
    )
    return {key: disclosure.get(key) for key in allowed if key in disclosure}


def _production_advisories(shot: dict[str, Any], session_phase: str,
                           spend: dict[str, Any] | None) -> list[dict[str, Any]]:
    """User-facing guidance only. It never blocks an approved engine action by itself."""
    if not shot:
        return []
    text = " ".join(str(shot.get(key) or "") for key in (
        "shotId", "purpose", "visualPayoff", "providerBoundaryExplanation",
        "splitOrNonSplitRationale", "packingJudgement"))
    text += " " + " ".join(
        str(stage.get(key) or "")
        for stage in (shot.get("storyboardStagePlanApproved") or shot.get("stagePlan") or [])
        if isinstance(stage, dict)
        for key in ("purpose", "primaryEvent", "observableEndState"))
    signals = sorted({signal for signal in _COMPLEXITY_SIGNALS if signal in text.casefold()})
    duration = float(shot.get("durationSec") or 0)
    if (session_phase == "animation" and duration > 15 and len(signals) >= 2):
        context = (
            "This render is sealed and ready for provider approval."
            if spend else
            "This dense animation result is ready for review."
        )
        return [{
            "code": "DENSE_UNIT_REVIEW",
            "severity": "warning",
            "title": "Check the split before rendering",
            "message": (
                f"{context} This is a long dense comedy/action unit. It can continue, but the safer "
                "production path is split units with held handoff frames if the current "
                "prompt still carries chase, flower reveal and crash business in one pass."),
            "nextAction": (
                "If the candidate does not land every beat, Refire with protected split units "
                "instead of rerendering the old crowded 29-second Scene 1 request."),
            "signals": signals,
        }]
    return []


def _keyframe_stage_comms(ledger: dict[str, Any], status: str,
                          artifact: dict[str, Any] | None) -> dict[str, Any] | None:
    candidate = ledger.get("keyframeCandidate") or {}
    # Retained rejection history must not override a newer accepted shot truth.
    approved = ledger.get("keyframeApproval") or {}
    rejected = {} if approved else (ledger.get("keyframeRejected") or {})
    record = candidate or rejected
    screening = (record.get("conformanceScreening") or
                 record.get("geometryScreening") or {})
    reason = str(screening.get("reason") or rejected.get("reason") or "").strip()
    if candidate:
        if screening.get("status") == "fail":
            return {
                "severity": "warning",
                "title": "Keyframe generated with QC warnings",
                "message": reason or (
                    "The generated keyframe is available for your review, but the automated "
                    "checks found an issue."),
                "nextAction": "Review the visible image, then choose Approve or Refire.",
                "artifactVisible": bool((artifact or {}).get("url")),
            }
        return {
            "severity": "info",
            "title": "Keyframe ready for your review",
            "message": "The generated keyframe is visible. Your decision controls whether it moves forward.",
            "nextAction": "Choose Approve if it works, or Refire with a correction if it does not.",
            "artifactVisible": bool((artifact or {}).get("url")),
        }
    if rejected:
        return {
            "severity": "warning",
            "title": "Previous keyframe was rejected",
            "message": reason or "The last keyframe was rejected and archived.",
            "nextAction": "Build or select another keyframe before animation can continue.",
            "artifactVisible": False,
        }
    if approved:
        return {
            "severity": "success",
            "title": "Keyframe accepted",
            "message": "This frame is locked as the opening truth for the shot.",
            "nextAction": "Continue to HEAR and review the voice performance.",
            "artifactVisible": bool((artifact or {}).get("url")),
        }
    if status == "ready_to_fire":
        return {
            "severity": "info",
            "title": "No keyframe candidate yet",
            "message": "This shot needs a generated or selected opening frame before animation.",
            "nextAction": "Build the opening frame.",
            "artifactVisible": False,
        }
    return None


def _stage_comms(phase: str, status: str, ledger: dict[str, Any],
                 artifact: dict[str, Any] | None) -> dict[str, Any] | None:
    if status == "rendering":
        completed = len((artifact or {}).get("items") or [])
        expected = int(((ledger.get("batch") or {}).get("expected") or 0))
        return {
            "severity": "info",
            "title": "Work in progress",
            "message": (
                f"{completed} of {expected} render candidates completed. The finished "
                "clip is visible while the remaining candidate renders."
                if completed and expected else "The Studio is processing this stage."
            ),
            "nextAction": (
                "Review is unlocked after every requested candidate has completed."
                if completed else "Wait for the result panel to update."
            ),
            "artifactVisible": bool(completed),
        }
    if phase == "keyframe":
        return _keyframe_stage_comms(ledger, status, artifact)
    return None


def _scene_plate_actions(phase: str, status: str) -> list[dict[str, Any]]:
    if phase != "keyframe" or status == "rendering":
        return []
    return [
        _action("select-scene-plate-library", "Choose scene plate from library"),
        _action("build-scene-plate", "Fire scene plate"),
        _action("select-scene-plate-upload", "Upload scene plate"),
    ]


def build_session(*, state: dict[str, Any], preflight: dict[str, Any],
                  package: dict[str, Any] | None = None,
                  media: dict[str, Any] | None = None,
                  scene_look: dict[str, Any] | None = None,
                  jobs: dict[str, Any] | None = None,
                  requested_shot_id: str | None = None,
                  animation_contract: dict[str, Any] | None = None) -> dict[str, Any]:
    """Project authoritative engine documents into one outcome-oriented Director session."""
    episode = str(state.get("episode") or preflight.get("episode") or "Ep1")
    scene = str(state.get("scene") or preflight.get("scene") or "")
    package_shots = _shot_map(package)
    selected_state = _choose_shot(state, requested_shot_id)
    shot_id = (selected_state or {}).get("shotId")
    shot = package_shots.get(shot_id) or {}
    shot_media = ((media or {}).get("shots") or {}).get(shot_id) or {}
    running = _latest_running_job(jobs, scene, shot_id)
    recent_failure = _latest_failed_job(jobs, scene, shot_id)
    stages = state.get("stages") or {}
    provider_blocker = _provider_blocker(preflight)
    spend = _spend_disclosure(package, shot_id)
    package_ledger = next((item for item in ((package or {}).get("continuityLedger") or [])
                           if item.get("shotId") == shot_id), {})
    if running:
        batch = package_ledger.get("batch") or {}
        disclosure = batch.get("disclosure") or {}
        running.update({
            "batchId": batch.get("batchId") or package_ledger.get("batchId"),
            "providerModelId": disclosure.get("providerModelId"),
            "durationSec": disclosure.get("shotDurationSec") or shot.get("durationSec"),
            "candidateCount": disclosure.get("candidateCount") or batch.get("expected"),
            "maxBatchCostUsd": disclosure.get("maxBatchCostUsd"),
        })
    all_state_shots = state.get("shots") or []
    all_animations_current = bool(all_state_shots) and all(
        _shot_complete(item) for item in all_state_shots)
    quality_review = None

    status = "blocked"
    phase = "story"
    headline = "Direct this scene"
    summary = "The current script needs a production-ready scene package."
    primary = None
    decisions: list[dict[str, Any]] = []
    blocker = None
    artifact: dict[str, Any] | None = None

    if not state.get("packageCurrent"):
        story_state = (stages.get("storyboard") or {}).get("state")
        if story_state == "ready":
            status = "ready_to_fire"
            headline = "Direct this scene"
            summary = (stages.get("storyboard") or {}).get("sub") or summary
            primary = _action("direct-scene", "Direct scene", paid=True)
        elif story_state == "awaiting":
            status = "ready_to_review"
            headline = "Review story direction"
            summary = (stages.get("storyboard") or {}).get("sub") or summary
            primary = _action("open-inspector", "Review story")
        else:
            blocker = next(iter(state.get("blockers") or []), None)
            summary = (blocker or {}).get("message") or summary
            primary = _action("open-inspector", "Resolve in Inspector")
    elif selected_state is None:
        status = "blocked"
        summary = "The production package contains no shots."
        primary = _action("open-inspector", "Inspect package")
    else:
        current = selected_state.get("current") or {}
        pending = selected_state.get("pending") or {}
        purpose = str(shot.get("purpose") or "").strip()
        keyframe_headline = (((preflight.get("productionInputs") or {}).get("shots") or {})
                             .get(shot_id) or {}).get("keyframePromptHeadline")

        if all_animations_current and not all(
                (item.get("current") or {}).get("directorReview") for item in all_state_shots):
            phase = "review"
            artifact = {"type": "video", "url": shot_media.get("clip"),
                        "label": "Accepted animation"}
            review_work = ((package_ledger.get("departmentWork") or {})
                           .get("review-animation") or {})
            review_candidate = review_work.get("candidate") or {}
            if pending.get("directorReview") and review_candidate:
                status = "ready_to_review"
                headline = "Quality review ready"
                summary = "Confirm the accepted take still protects story, performance and continuity."
                quality_review = review_candidate.get("output") or {}
                decisions = [
                    _action("accept-quality", "Confirm shot"),
                    _action("reopen-shot", "Reopen", destructive=True),
                ]
            else:
                status = "ready_to_fire"
                headline = "Run the quality check"
                summary = purpose
                primary = _action("run-quality-review", "Run quality check")
        elif all_animations_current:
            phase = "final"
            final_stage = stages.get("final") or {}
            post = state.get("postProduction") or {}
            final_work = ((package or {}).get("departmentWork") or {}).get("review-final") or {}
            final_candidate = final_work.get("candidate") or {}
            artifact = {"type": "video", "url": (media or {}).get("picture"),
                        "label": "Scene master"}
            if final_stage.get("state") == "approved":
                status = "complete"
                headline = "Scene master accepted"
                summary = "The QC-passed 16:9 master is current and approved."
                quality_review = (final_work.get("approved") or {}).get("output") or {}
            elif final_stage.get("state") == "awaiting" and final_candidate:
                status = "ready_to_review"
                headline = "Review the scene master"
                summary = "Watch the finished scene, then accept it or send one clear correction."
                quality_review = final_candidate.get("output") or {}
                decisions = [
                    _action("accept-master", "Accept master"),
                    _action("iterate-master", "Iterate", destructive=True),
                ]
            elif final_stage.get("state") == "blocked":
                status = "blocked"
                headline = "Final master needs attention"
                summary = final_stage.get("sub") or "The post candidate is not current."
                primary = _action("open-inspector", "Inspect final master")
            elif (post.get("candidate") or {}).get("current") or (
                    post.get("approved") or {}).get("current"):
                status = "ready_to_fire"
                headline = "Run final review"
                summary = final_stage.get("sub") or "The mastered scene is ready for its final review."
                primary = _action("run-final-review", "Run final review")
            else:
                status = "ready_to_fire"
                headline = "Build the scene master"
                summary = "Conform the accepted shots, mix sound, build captions and run delivery QC."
                primary = _action("build-master", "Build scene master")
        elif pending.get("keyframe"):
            phase = "keyframe"
            status = "ready_to_review"
            headline = "Does this stage give the performance room to land?"
            summary = keyframe_headline or purpose
            artifact = {"type": "image", "url": shot_media.get("keyframeCandidate")
                        or shot_media.get("keyframe"), "label": "Opening-frame candidate"}
            decisions = [
                _action("accept-keyframe", "Accept"),
                _action("iterate-keyframe", "Iterate", destructive=True),
            ]
        elif not current.get("keyframe"):
            phase = "keyframe"
            status = "ready_to_fire"
            headline = "Build the opening stage"
            summary = keyframe_headline or purpose
            primary = _action("build-keyframe", "Build opening frame", paid=True)
            if (scene_look or {}).get("plateUrl"):
                artifact = {"type": "image", "url": scene_look.get("plateUrl"),
                            "label": "Current Scene Look"}
        elif pending.get("voice"):
            phase = "voice"
            status = "ready_to_review"
            headline = "Do the performances sound true?"
            summary = purpose
            artifact = {"type": "audio", "url": shot_media.get("vo"),
                        "label": "Voice performance"}
            decisions = [
                _action("accept-voice", "Accept"),
                _action("iterate-voice", "Iterate", destructive=True),
            ]
        elif selected_state.get("talky") and not current.get("voice"):
            phase = "voice"
            status = "ready_to_fire"
            headline = "Opening frame accepted. Create the performances."
            summary = (
                "The opening frame is locked and protected. Next, create the voice "
                "performances that will drive the animation."
            )
            primary = _action("build-voice", "Create performances", paid=True)
            artifact = {"type": "image", "url": shot_media.get("keyframeApproved")
                        or shot_media.get("keyframe"), "label": "Accepted opening frame"}
        elif pending.get("animation"):
            phase = "animation"
            status = "ready_to_review"
            headline = "Watch the result"
            summary = purpose
            candidates = shot_media.get("candidates") or []
            artifact = {"type": "video-set", "items": candidates,
                        "label": "Animation candidates"}
            decisions = [
                _action("accept-animation", "Accept", candidate=(candidates[0].get("n")
                                                                  if len(candidates) == 1 else None)),
                _action("iterate-animation", "Iterate", destructive=True),
            ]
        elif not current.get("animation"):
            phase = "animation"
            previous_candidates = shot_media.get("candidates") or []
            stale_batch = package_ledger.get("batch") or {}
            if previous_candidates and stale_batch.get("approvalBlockedReason"):
                # A direction recompile must block approval of old renders, but those
                # completed clips remain useful Director evidence and must stay visible.
                artifact = {
                    "type": "video-set",
                    "items": previous_candidates,
                    "label": "Superseded animation candidates",
                    "stale": True,
                    "notice": stale_batch.get("approvalBlockedReason"),
                    "supersededAt": stale_batch.get("supersededByDirectionAt"),
                }
            else:
                artifact = {"type": "image", "url": shot_media.get("keyframeApproved")
                            or shot_media.get("keyframe"), "label": "Accepted opening frame"}
            if provider_blocker:
                status = "blocked"
                headline = "Animation route needs activation"
                summary = provider_blocker.get("message") or "The selected video route is not qualified."
                blocker = provider_blocker
                primary = _action("open-provider-setup", "Open provider setup")
            elif spend:
                status = "ready_to_review"
                headline = "Ready to render"
                summary = purpose
                decisions = [
                    _action("approve-spend", "Approve spend and render", paid=True),
                    _action("cancel-spend", "Not yet"),
                ]
            else:
                status = "ready_to_fire"
                headline = "Compile the animation prompt"
                summary = (
                    "Compile the exact Seedance prompt, references and cost for review. "
                    "This does not submit a paid render."
                )
                primary = _action("prepare-render", "Compile prompt & show cost")
        else:
            phase = "final"
            status = "complete"
            headline = "Shot accepted"
            summary = purpose
            artifact = {"type": "video", "url": shot_media.get("clip"),
                        "label": "Accepted animation"}

    if running:
        status = "rendering"
        headline = running.get("step") or "Building the next result"
        primary = None
        decisions = []
        if phase == "animation":
            completed_candidates = shot_media.get("candidates") or []
            running["completedCandidateCount"] = len(completed_candidates)
            if completed_candidates:
                artifact = {
                    "type": "video-set",
                    "items": completed_candidates,
                    "label": "Completed render candidates",
                    "partial": True,
                }

    # A current reviewable result or sealed request supersedes an older failed attempt.
    # Keep failures visible only while they still explain why the selected shot cannot advance.
    if status in ("ready_to_review", "complete") and (artifact or spend):
        recent_failure = None

    all_shots = state.get("shots") or []
    completed = sum(1 for item in all_shots if _shot_complete(item))
    shot_summaries = []
    for index, item in enumerate(all_shots, start=1):
        item_shot_id = item.get("shotId")
        source = package_shots.get(item.get("shotId")) or {}
        shot_summaries.append({
            "id": item_shot_id,
            "shotId": item_shot_id,
            "number": index,
            "durationSec": source.get("durationSec"),
            "purpose": source.get("purpose"),
            "acceptedUrl": (((media or {}).get("shots") or {}).get(
                item_shot_id) or {}).get("clip"),
            "keyframeUrl": (((media or {}).get("shots") or {}).get(
                item_shot_id) or {}).get("keyframeApproved"),
            "voiceUrl": (((media or {}).get("shots") or {}).get(
                item_shot_id) or {}).get("vo"),
            "state": "complete" if _shot_complete(item) else item.get("badgeState") or "waiting",
            "selected": item_shot_id == shot_id,
        })

    session = {
        "schemaVersion": SCHEMA_VERSION,
        "readOnlyProjection": True,
        "episode": episode,
        "scene": scene,
        "sceneName": (package or {}).get("sceneName") or "Scene " + scene,
        "status": status,
        "phase": phase,
        "headline": headline,
        "summary": summary,
        "selectedShotId": shot_id,
        "shot": ({
            "shotId": shot_id,
            "durationSec": shot.get("durationSec"),
            "purpose": shot.get("purpose"),
            "visualPayoff": shot.get("visualPayoff"),
            "characters": shot.get("charactersInFrame") or [],
        } if shot_id else None),
        "progress": {"complete": completed, "total": len(all_shots)},
        "shots": shot_summaries,
        "artifact": artifact,
        "primaryAction": primary,
        "decisionActions": decisions,
        "blocker": blocker,
        "runningJob": running,
        "recentFailure": recent_failure,
        "spendDisclosure": spend,
        "sceneLook": scene_look or {},
        "stageComms": _stage_comms(phase, status, package_ledger, artifact),
        "scenePlateActions": _scene_plate_actions(phase, status),
        "advisories": _production_advisories(shot, phase, spend),
        "qualityReview": quality_review,
        "stages": stages,
        "lineageCurrent": bool((state.get("lineage") or {}).get("current")),
        "providerReady": bool((preflight.get("providerCapabilities") or {}).get("selectionReady")),
        "providerModel": (preflight.get("providerCapabilities") or {}).get("selectedVideoModelId"),
        "inspector": {
            "providerRequest": _prompt_contract(
                preflight, shot_id, phase, animation_contract),
            "policyVersion": state.get("policyVersion"),
            "packageRevision": state.get("packageRevision"),
            "structuralClaim": (
                "Code and lineage status only. Creative quality is proven by the rendered result."
            ),
        },
    }
    if session["status"] not in SESSION_STATES:
        raise ValueError(f"unknown Director session state: {session['status']}")
    return session


def allowed_action_ids(session: dict[str, Any]) -> set[str]:
    actions = []
    if session.get("primaryAction"):
        actions.append(session["primaryAction"])
    actions.extend(session.get("decisionActions") or [])
    actions.extend(session.get("scenePlateActions") or [])
    out = {str(action.get("id")) for action in actions if action.get("id")}
    if (session.get("phase") == "keyframe" and
            session.get("status") != "rendering" and
            not (session.get("artifact") or {}).get("url")):
        out.update({"select-keyframe-library", "select-keyframe-upload"})
    return out


def _direction_current(scene: str, shot_id: str, stage: str, episode: str) -> bool:
    import cb_render

    package, _ = cb_render.load_pkg(scene, episode)
    return bool(cb_render._department_record_status(
        package, shot_id, stage, scene, episode).get("current"))


def build_keyframe(scene: str, shot_id: str, episode: str = "Ep1", log=print) -> None:
    import cb_render

    package, _ = cb_render.load_pkg(scene, episode)
    shot = cb_render._shot(package, shot_id)
    ledger = cb_render._ledger(package, shot_id)
    work = ledger.setdefault("departmentWork", {}).setdefault(
        "cinematography", {"approved": None, "candidate": None, "history": []})

    def contract_is_complete(record: dict[str, Any] | None) -> bool:
        try:
            cb_render._keyframe_direction_contract(
                ((record or {}).get("output") or {}), shot)
            return True
        except (cb_render.Refused, KeyError, TypeError, ValueError):
            return False

    if not contract_is_complete(work.get("approved")):
        if work.get("candidate"):
            if contract_is_complete(work["candidate"]):
                log("DIRECTOR — promoting the current complete cinematography contract")
                cb_render.decide_department(
                    scene, "cinematography", "approved", shot_id=shot_id,
                    note="Current typed direction promoted for keyframe compilation.",
                    episode=episode, reviewed_by="Studio contract migration", log=log)
            else:
                log("DIRECTOR — refreshing legacy cinematography direction to the current contract")
                cb_render.decide_department(
                    scene, "cinematography", "rejected", shot_id=shot_id,
                    note="Legacy direction is missing required typed keyframe fields.",
                    episode=episode, reviewed_by="Studio contract migration", log=log)
        if not contract_is_complete(work.get("approved")):
            cb_render.prepare_department(
                scene, "cinematography", shot_id, episode, log)
            cb_render.decide_department(
                scene, "cinematography", "approved", shot_id=shot_id,
                note="Refreshed to the current typed keyframe contract.", episode=episode,
                reviewed_by="Studio contract migration", log=log)
    cb_render.keyframe_shot(scene, shot_id, episode, log)


def refire_keyframe(scene: str, shot_id: str, correction: str,
                    episode: str = "Ep1", log=print) -> None:
    """Apply the human retake note and return one replacement review candidate."""
    import cb_render

    log("REFIRE — recording the Director's keyframe note and retiring this candidate")
    cb_render.reject_keyframe(scene, shot_id, correction, episode, log=log)
    log("REFIRE — building the corrected keyframe now")
    build_keyframe(scene, shot_id, episode, log)


def build_voice(scene: str, shot_id: str, episode: str = "Ep1", log=print) -> None:
    import cb_render

    if not _direction_current(scene, shot_id, "voice", episode):
        log("DIRECTOR — preparing current voice direction")
        cb_render.prepare_department(scene, "voice", shot_id, episode, log)
    package, path = cb_render.load_pkg(scene, episode)
    cb_render.voice_shot(package, path, shot_id, episode, log)


def prepare_render(scene: str, shot_id: str, episode: str = "Ep1", log=print) -> None:
    """Prepare direction and seal the standard two-candidate 480p comedy request."""
    import cb_providers
    import cb_render

    model = cb_providers.video_model(require_enabled=True)
    cb_render._require_confirmed_billing(model.provider)
    if not _direction_current(scene, shot_id, "animation", episode):
        log("DIRECTOR — preparing current animation direction")
        cb_render.prepare_department(scene, "animation", shot_id, episode, log)
    try:
        cb_render.fire_shot(scene, shot_id, episode, candidates=2, spend_token=None, log=log)
    except cb_render.Refused as exc:
        package, _ = cb_render.load_pkg(scene, episode)
        pending = (cb_render._ledger(package, shot_id).get("pendingSpendAuth") or {})
        if pending and "SPEND NOT APPROVED" in str(exc):
            log("DIRECTOR — sealed request ready for spend approval; no media generated")
            return
        raise


def _usage() -> str:
    return (
        "usage: cb_studio_director.py <build-keyframe|build-voice|prepare-render> "
        "<scene> <shotId> [episode]\n"
        "       cb_studio_director.py refire-keyframe <scene> <shotId> "
        "<correction> [episode]"
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "refire-keyframe":
        if len(argv) not in (4, 5):
            print(_usage(), file=sys.stderr)
            return 2
        _, scene, shot_id, correction = argv[:4]
        episode = argv[4] if len(argv) == 5 else "Ep1"
        try:
            refire_keyframe(scene, shot_id, correction, episode)
            return 0
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if len(argv) not in (3, 4):
        print(_usage(), file=sys.stderr)
        return 2
    command, scene, shot_id = argv[:3]
    episode = argv[3] if len(argv) == 4 else "Ep1"
    commands = {
        "build-keyframe": build_keyframe,
        "build-voice": build_voice,
        "prepare-render": prepare_render,
    }
    fn = commands.get(command)
    if fn is None:
        print(_usage(), file=sys.stderr)
        return 2
    try:
        fn(scene, shot_id, episode)
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
