#!/usr/bin/env python3
"""Outcome-first Director facade for the canonical production engine.

The existing engine remains authoritative for canon, lineage, approvals, provider routing,
spend and media.  This module only projects that state into one creative decision at a time
and provides three narrowly scoped orchestration commands used by the Studio server.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys
from typing import Any

import cb_asset_registry


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


def _scene_continuity_rules(episode: str, scene: str) -> list[dict[str, str]]:
    """Project the canonical character-state rules relevant to this scene."""
    path = pathlib.Path(__file__).resolve().parent / "config" / "continuity.json"
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    try:
        scene_number = int(scene)
    except (TypeError, ValueError):
        return []
    rows = []
    for character, states in (((config.get(episode) or {}).get("characterStates") or {}).items()):
        for state in states or []:
            scope = str(state.get("scenes") or "")
            match = re.fullmatch(r"(\d+)(?:-(\d+))?", scope)
            if not match:
                continue
            first = int(match.group(1)); last = int(match.group(2) or first)
            rule = str(state.get("rule") or "").strip()
            if first <= scene_number <= last and rule:
                rows.append({
                    "label": f"{character} — {state.get('wristbandState') or 'continuity'}",
                    "value": rule,
                    "severity": "critical",
                })
    return rows


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


def _opening_frame_media(shot: dict[str, Any], media: dict[str, Any] | None) -> dict[str, Any]:
    """Project the visible opening frame used by authored and relay shots."""
    shots_media = (media or {}).get("shots") or {}
    own_media = dict(shots_media.get(shot.get("shotId")) or {})
    if own_media.get("keyframeApproved") or shot.get("sourceType") != "relay":
        return own_media
    source_id = shot.get("sourceShotId")
    relay_anchor = (shots_media.get(source_id) or {}).get("finalFrame")
    if relay_anchor:
        own_media["keyframeApproved"] = relay_anchor
        own_media["keyframe"] = relay_anchor
        own_media["relayAnchor"] = relay_anchor
    return own_media


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
    elif "ai-review" in operation_text or "review-keyframe" in operation_text or "review-animation" in operation_text:
        activity_label = "AI Director review in progress"
        fallback_step = "Reviewing the actual artifact against story, performance and continuity..."
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
        "operation": " ".join([str(job.get("gate") or ""), *(
            str(value) for value in (job.get("args") or []))]).lower(),
    }


def _failure_matches_phase(failure: dict[str, Any] | None, phase: str) -> bool:
    """Keep a failure visible only while it still explains the active decision."""
    if not failure:
        return False
    operation = str(failure.get("operation") or "")
    if "keyframe" in operation:
        return phase == "keyframe"
    if "voice" in operation:
        return phase == "voice"
    if any(token in operation for token in (" prepare-render", " fire ", " approve ", " reject ")):
        return phase == "animation"
    return True


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
        seedance = dict(contract_checks.get("seedancePromptContract") or {})
        if seedance:
            raw_score = seedance.get("score")
            raw_maximum = seedance.get("maximum")
            normalized = seedance.get("normalizedScore")
            if normalized is None and raw_maximum:
                normalized = round((float(raw_score or 0) / float(raw_maximum)) * 10, 2)
            seedance["rawScore"] = raw_score
            seedance["rawMaximum"] = raw_maximum
            seedance["score"] = normalized
            seedance["maximum"] = 10
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
            "seedancePromptContract": seedance,
            "qualityGate": contract_checks.get("qualityGate"),
            "creativeTranslation": contract_checks.get("creativeTranslation"),
        }
    return None


def _prepared_animation_contract(ledger: dict[str, Any]) -> dict[str, Any] | None:
    """Expose compiled creative direction before WATCH without implying render readiness."""
    candidate = (((ledger.get("departmentWork") or {}).get("animation") or {})
                 .get("candidate") or {})
    output = candidate.get("output") or {}
    prompt = str(output.get("providerPrompt") or "").strip()
    if not prompt:
        return None
    preflight = candidate.get("preflight") or {}
    verdict = "PASS" if preflight.get("verdict") == "PASS" else "BLOCK"
    voice_approved = bool((ledger.get("voiceApproval") or {}).get("approved"))
    return {
        "kind": "animation",
        "authoritative": True,
        "renderReady": False,
        "gate": ("Compile current provider request" if voice_approved else
                 "HEAR approval required before WATCH"),
        "source": candidate.get("preparedBy") or "current-direction",
        "prompt": prompt,
        "promptHash": hashlib.sha256(prompt.encode()).hexdigest(),
        "durationSec": output.get("durationSec"),
        "conformance": {
            "score": preflight.get("score"),
            "maximum": 10,
            "verdict": verdict,
            "checkerVerdict": preflight.get("verdict") or "BLOCK",
            "findings": list(preflight.get("findings") or [])[:3],
        },
        "seedancePromptContract": {
            **(preflight.get("seedanceAuthoring") or {}),
            "score": (preflight.get("seedanceAuthoring") or {}).get("normalizedScore"),
            "maximum": 10,
            "repairActions": [],
        },
        "qualityGate": preflight.get("qualityGate"),
        "creativeTranslation": {"ready": True, "errors": []},
    }


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


def _voice_audition_candidates(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    auditions = ledger.get("voiceAuditions") or {}
    if auditions.get("status") != "ready_for_hear_verdict":
        return []
    out = []
    for index, candidate in enumerate(auditions.get("candidates") or [], start=1):
        path = str(candidate.get("path") or "").strip()
        if not path:
            continue
        out.append({
            "n": index,
            "candidateId": candidate.get("candidateId"),
            "url": path,
            "label": candidate.get("label") or f"Voice take {index}",
            "recipeId": candidate.get("recipeId"),
            "takeNumber": candidate.get("takeNumber"),
            "performedText": candidate.get("performedText"),
            "primary": bool(candidate.get("primary")),
            "selected": (
                (auditions.get("selected") or {}).get("candidateId") ==
                candidate.get("candidateId")
            ),
        })
    return out


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


def _line_state(active: bool, complete: bool, blocked: bool, waiting: bool = False) -> str:
    if active:
        return "active"
    if complete:
        return "complete"
    if blocked:
        return "blocked"
    if waiting:
        return "waiting"
    return "pending"


def _production_line(*, phase: str, status: str, state: dict[str, Any],
                     selected_state: dict[str, Any] | None,
                     selected_shot_id: str | None, all_animations_current: bool,
                     all_shots: list[dict[str, Any]]) -> dict[str, Any]:
    """Collapse overlapping gates into one visible production sequence."""
    current = (selected_state or {}).get("current") or {}
    talky = bool((selected_state or {}).get("talky"))
    keyframe_complete = bool(current.get("keyframe"))
    voice_complete = bool((not talky) or current.get("voice"))
    animation_complete = bool(current.get("animation"))
    blocked = status == "blocked"
    story_complete = bool(state.get("packageCurrent"))
    complete_count = sum(1 for item in all_shots if _shot_complete(item))
    total_count = len(all_shots)
    steps = [
        {
            "id": "story",
            "label": "Story",
            "state": _line_state(phase == "story", story_complete,
                                 blocked and phase == "story"),
            "summary": "Script and Director storyboard package",
        },
        {
            "id": "see",
            "label": "SEE",
            "state": _line_state(phase == "keyframe", keyframe_complete,
                                 blocked and phase == "keyframe", not story_complete),
            "summary": "Approved opening frame",
        },
        {
            "id": "hear",
            "label": "HEAR",
            "state": _line_state(phase == "voice", voice_complete,
                                 blocked and phase == "voice", not keyframe_complete),
            "summary": "Approved voice performance",
        },
        {
            "id": "watch",
            "label": "WATCH",
            "state": _line_state(phase == "animation", animation_complete,
                                 blocked and phase == "animation", not voice_complete),
            "summary": "Seedance prompt, spend, render and take",
        },
        {
            "id": "review",
            "label": "Review",
            "state": _line_state(phase in ("review", "final"),
                                 bool(all_animations_current and status == "complete"),
                                 blocked and phase in ("review", "final"),
                                 not all_animations_current),
            "summary": "Quality check, scene master and final approval",
        },
    ]
    active = next((step for step in steps if step["state"] == "active"), None)
    return {
        "mode": "production-line",
        "activeStep": (active or {}).get("id") or phase,
        "selectedShotId": selected_shot_id,
        "shotProgress": {"complete": complete_count, "total": total_count},
        "steps": steps,
    }


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
                "artifactVisible": bool((artifact or {}).get("url") or
                                        (artifact or {}).get("items")),
            }
        return {
            "severity": "info",
            "title": "Keyframe ready for your review",
            "message": "The generated keyframe is visible. Your decision controls whether it moves forward.",
            "nextAction": "Choose Approve if it works, or Refire with a correction if it does not.",
            "artifactVisible": bool((artifact or {}).get("url") or
                                    (artifact or {}).get("items")),
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


def _ai_creative_review(ledger: dict[str, Any], phase: str) -> dict[str, Any]:
    """Expose the specialist's actual-artifact review without granting it authority."""
    stage = {
        "keyframe": "review-keyframe",
        "animation": "review-animation",
    }.get(phase)
    if not stage:
        return {
            "available": False,
            "stage": None,
            "verdict": "human-review",
            "summary": (
                "This stage still requires Julian's direct judgement; no visual AI review "
                "is applicable to the current artifact."
            ),
            "advisoryOnly": True,
            "mayApprove": False,
        }
    work = ((ledger.get("departmentWork") or {}).get(stage) or {})
    event = work.get("candidate") or work.get("approved") or {}
    output = event.get("output") or {}
    reviewed_paths = sorted(str(path) for path in (event.get("reviewedMediaPaths") or []) if path)
    if phase == "keyframe":
        record = ledger.get("keyframeCandidate") or ledger.get("keyframeApproval") or {}
        current_paths = [str(record.get("path"))] if record.get("path") else []
    else:
        current_paths = (
            [str(ledger.get("approvedTake"))]
            if ledger.get("status") == "approved" and ledger.get("approvedTake")
            else [str(path) for path in (ledger.get("candidatePaths") or []) if path]
        )
    review_current = bool(reviewed_paths) and reviewed_paths == sorted(current_paths)
    if output and not review_current:
        return {
            "available": False,
            "stage": stage,
            "verdict": "stale",
            "summary": "The saved recommendation belongs to an older artifact. Review this result again.",
            "advisoryOnly": True,
            "mayApprove": False,
        }
    if not output:
        return {
            "available": False,
            "stage": stage,
            "verdict": "not-run",
            "summary": "The AI Director has not reviewed the actual artifact yet.",
            "advisoryOnly": True,
            "mayApprove": False,
        }
    dimensions = []
    for key, label in (
        ("beatDelivery", "Beat delivery"),
        ("actingAndPerformance", "Acting and performance"),
        ("physicalCausality", "Physical causality"),
        ("timingAndReaction", "Timing and reaction"),
        ("cameraAndEdit", "Camera and edit"),
        ("compositionAndContinuity", "Composition and continuity"),
        ("identityAndReferenceUse", "Identity and references"),
        ("finishAndProductionValue", "Finish and production value"),
    ):
        item = output.get(key) or {}
        if item:
            dimensions.append({
                "id": key,
                "label": label,
                "score": item.get("score"),
                "observed": item.get("observed"),
                "diagnosis": item.get("diagnosis"),
                "confidence": item.get("confidence"),
            })
    return {
        "available": True,
        "stage": stage,
        "verdict": output.get("verdict") or "reviewed",
        "summary": output.get("summary") or "The actual artifact has been reviewed.",
        "intendedRead": output.get("intendedRead"),
        "actualRead": output.get("actualRead"),
        "beatLands": (output.get("beatDelivery") or {}).get("score") == 2,
        "recommendedCandidate": output.get("recommendedCandidate"),
        "dimensions": dimensions,
        "likelyRootCause": output.get("likelyRootCause"),
        "rootCauseReasoning": output.get("rootCauseReasoning"),
        "cheapestNextAction": output.get("cheapestNextAction"),
        "preparedAt": event.get("preparedAt"),
        "advisoryOnly": True,
        "mayApprove": False,
    }


def _human_review_contract(*, phase: str, status: str, state: dict[str, Any],
                           selected_state: dict[str, Any] | None,
                           artifact: dict[str, Any] | None,
                           shot: dict[str, Any], ledger: dict[str, Any],
                           quality_review: dict[str, Any] | None,
                           blocker: dict[str, Any] | None,
                           primary: dict[str, Any] | None,
                           decisions: list[dict[str, Any]]) -> dict[str, Any]:
    """Project the existing human gates without creating a second approval path."""
    current = (selected_state or {}).get("current") or {}
    pending = (selected_state or {}).get("pending") or {}
    stages = state.get("stages") or {}
    current_id = {
        "story": "direction", "keyframe": "see", "voice": "hear",
        "animation": "watch", "review": "qc", "final": "post",
    }.get(phase, "direction")
    talky = bool((selected_state or {}).get("talky"))
    signed = {
        "direction": bool(state.get("packageCurrent")),
        "see": bool(current.get("keyframe")),
        "hear": not talky or bool(current.get("voice")),
        "watch": bool(current.get("animation")),
        "qc": bool(current.get("directorReview")),
        "post": (stages.get("final") or {}).get("state") == "approved",
    }
    pending_by_stage = {
        "direction": not signed["direction"] and phase == "story" and status == "ready_to_review",
        "see": bool(pending.get("keyframe")),
        "hear": bool(pending.get("voice")),
        "watch": bool(pending.get("animation")),
        "qc": phase == "review" and status == "ready_to_review",
        "post": phase == "final" and status == "ready_to_review",
    }
    definitions = [
        ("direction", "DIRECTION", "The script beat, emotional outcome and playable staging are clear."),
        ("see", "SEE", "The opening image protects identity, geography, props and room for the action."),
        ("hear", "HEAR", "The performance carries the exact line, acting intention and pace."),
        ("watch", "WATCH", "The action, acting, continuity and ending beat land on screen."),
        ("qc", "QC", "A fresh viewing confirms the accepted take still works in sequence."),
        ("post", "POST", "Picture, dialogue, effects, music, rhythm and delivery work together."),
    ]
    review_stages = []
    reached_current = False
    upstream_current = True
    for stage_id, label, intent in definitions:
        is_current = stage_id == current_id
        reached_current = reached_current or is_current
        stage_not_required = stage_id == "hear" and not talky
        if signed[stage_id] and not upstream_current and not stage_not_required:
            stage_status = "recheck"
        elif signed[stage_id]:
            stage_status = "signed"
        elif pending_by_stage[stage_id] or (is_current and status == "ready_to_review"):
            stage_status = "decision"
        elif is_current:
            stage_status = "working" if status == "rendering" else "current"
        elif reached_current:
            stage_status = "locked"
        else:
            stage_status = "complete"
        if stage_not_required:
            stage_status = "not_required"
        review_stages.append({
            "id": stage_id, "label": label, "status": stage_status,
            "intent": intent, "current": is_current,
            "humanRequired": stage_status not in ("locked", "not_required"),
        })
        if not stage_not_required:
            upstream_current = upstream_current and stage_status == "signed"

    intended_outcome = str(
        shot.get("visualPayoff") or shot.get("emotionalIntent") or
        shot.get("purpose") or shot.get("storyBeat") or ""
    ).strip()
    evidence = []
    artifact_visible = bool(artifact and (artifact.get("url") or artifact.get("items")))
    evidence.append(
        f"Visible artifact: {artifact.get('label') or artifact.get('type') or 'current result'}"
        if artifact_visible else "No review artifact is visible yet."
    )
    if blocker:
        evidence.append(str(blocker.get("message") or blocker.get("action") or "A blocker is open."))
    if quality_review:
        finding = (quality_review.get("actualRead") or quality_review.get("verdict") or
                   quality_review.get("cheapestNextAction"))
        if finding:
            evidence.append(str(finding))
    ai_review = _ai_creative_review(ledger, phase)
    actions = [item.get("id") for item in [primary, *decisions] if item and item.get("id")]
    return {
        "schemaVersion": 1,
        "authority": "Julian",
        "rule": (
            "The AI Director reviews and recommends. It cannot approve or reject. "
            "Only Julian's decision is final."
        ),
        "currentStage": current_id,
        "stages": review_stages,
        "currentDecision": {
            "required": status == "ready_to_review",
            "canApprove": status == "ready_to_review" and artifact_visible and bool(decisions),
            "artifactVisible": artifact_visible,
            "intendedOutcome": intended_outcome,
            "evidence": evidence,
            "actions": actions,
            "aiReview": ai_review,
            "advisoryOnly": True,
        },
    }


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
    shot_media = _opening_frame_media(shot, media)
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
        if state.get("preservedPackageView") and selected_state is not None and package:
            status = "blocked"
            blocker = next(iter(state.get("blockers") or []), None)
            summary = ((blocker or {}).get("message") or
                       "The preserved shot is visible, but its production graph needs refresh.")
            primary = _action("open-inspector", "Resolve in Inspector")
            preserved_see_candidates = list(package_ledger.get("keyframeCandidates") or [])
            if len(preserved_see_candidates) > 1:
                phase = "keyframe"
                headline = "Preserved SEE A/B comparison"
                artifact = {
                    "type": "image-set",
                    "label": "SEE A/B comparison",
                    "selectedCandidateId": package_ledger.get("selectedKeyframeCandidateId"),
                    "items": [{
                        "candidateId": item.get("candidateId"),
                        "label": item.get("label"),
                        "provider": item.get("provider"),
                        "model": item.get("model"),
                        "url": cb_asset_registry.url_for_path(item.get("path")),
                    } for item in preserved_see_candidates
                        if cb_asset_registry.url_for_path(item.get("path"))],
                }
            elif shot_media.get("clip"):
                phase = "animation"
                headline = "Preserved animation take"
                artifact = {"type": "video", "url": shot_media.get("clip"),
                            "label": "Preserved accepted animation"}
            elif shot_media.get("vo"):
                phase = "voice"
                headline = "Preserved voice track"
                artifact = {"type": "audio", "url": shot_media.get("vo"),
                            "label": "Preserved approved voice"}
            elif shot_media.get("keyframeApproved") or shot_media.get("keyframe"):
                phase = "keyframe"
                headline = "Preserved opening frame"
                artifact = {
                    "type": "image",
                    "url": shot_media.get("keyframeApproved") or shot_media.get("keyframe"),
                    "label": "Preserved approved opening frame",
                }
        elif story_state == "ready":
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
        keyframe_ready = bool(current.get("keyframe") or shot_media.get("keyframeApproved"))
        voice_ready = bool(not selected_state.get("talky") or current.get("voice"))
        purpose = str(shot.get("purpose") or shot.get("storyBeat") or "").strip()
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
            keyframe_candidates = list(package_ledger.get("keyframeCandidates") or [])
            if len(keyframe_candidates) > 1:
                selected_keyframe_candidate_id = package_ledger.get("selectedKeyframeCandidateId")
                artifact = {
                    "type": "image-set",
                    "label": "SEE A/B comparison",
                    "selectedCandidateId": selected_keyframe_candidate_id,
                    "items": [{
                        "candidateId": item.get("candidateId"),
                        "label": item.get("label"),
                        "provider": item.get("provider"),
                        "model": item.get("model"),
                        "url": cb_asset_registry.url_for_path(item.get("path")),
                    } for item in keyframe_candidates
                        if cb_asset_registry.url_for_path(item.get("path"))],
                }
            else:
                artifact = {"type": "image", "url": shot_media.get("keyframeCandidate")
                            or shot_media.get("keyframe"), "label": "Opening-frame candidate"}
            if len(keyframe_candidates) > 1 and not selected_keyframe_candidate_id:
                headline = "Choose the SEE stage to review"
                summary = ("Compare A from Seedream 5.0 Pro with B from Nano Banana 2. "
                           "Selecting a candidate does not approve it.")
                primary = None
                decisions = []
            elif _ai_creative_review(package_ledger, phase)["available"]:
                decisions = [
                    _action("accept-keyframe", "Accept"),
                    _action("iterate-keyframe", "Iterate", destructive=True),
                ]
            else:
                primary = _action("run-ai-review", "Run AI Director review")
        elif not keyframe_ready:
            phase = "keyframe"
            status = "ready_to_fire"
            headline = "Build the opening stage"
            summary = keyframe_headline or purpose
            primary = _action("build-keyframe", "Build opening frame", paid=True)
            if (scene_look or {}).get("plateUrl"):
                artifact = {"type": "image", "url": scene_look.get("plateUrl"),
                            "label": "Current Scene Look"}
        voice_auditions = _voice_audition_candidates(package_ledger)
        if (not all_animations_current and keyframe_ready and pending.get("voice")
                and shot_media.get("vo")):
            phase = "voice"
            status = "ready_to_review"
            headline = "Do the performances sound true?"
            summary = purpose
            artifact = {"type": "audio", "url": shot_media.get("vo"),
                        "label": "Complete voice performance"}
            decisions = [
                _action("accept-voice", "Accept"),
                _action("iterate-voice", "Iterate", destructive=True),
            ]
        elif (not all_animations_current and keyframe_ready and voice_auditions
              and not current.get("voice")):
            phase = "voice"
            status = "ready_to_review"
            headline = "Choose the voice performance"
            summary = purpose
            artifact = {"type": "audio-set", "items": voice_auditions,
                        "label": "Voice performance auditions"}
            decisions = [
                _action("accept-voice", "Accept"),
                _action("iterate-voice", "Iterate", destructive=True),
            ]
        elif not all_animations_current and keyframe_ready and pending.get("voice"):
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
        elif (not all_animations_current and keyframe_ready and selected_state.get("talky")
              and not current.get("voice")):
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
        elif (not all_animations_current and keyframe_ready and voice_ready
              and pending.get("animation")):
            phase = "animation"
            status = "ready_to_review"
            headline = "Watch the result"
            summary = purpose
            candidates = shot_media.get("candidates") or []
            artifact = {"type": "video-set", "items": candidates,
                        "label": "Animation candidates"}
            if _ai_creative_review(package_ledger, phase)["available"]:
                decisions = [
                    _action("accept-animation", "Accept", candidate=(candidates[0].get("n")
                                                                      if len(candidates) == 1 else None)),
                    _action("iterate-animation", "Iterate", destructive=True),
                ]
            else:
                primary = _action("run-ai-review", "Run AI Director review")
        elif (not all_animations_current and keyframe_ready and voice_ready
              and not current.get("animation")):
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
        elif not all_animations_current and keyframe_ready and voice_ready:
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
    if (status in ("ready_to_review", "complete") and (artifact or spend)) or not _failure_matches_phase(
            recent_failure, phase):
        recent_failure = None

    all_shots = state.get("shots") or []
    completed = sum(1 for item in all_shots if _shot_complete(item))
    shot_summaries = []
    for index, item in enumerate(all_shots, start=1):
        item_shot_id = item.get("shotId")
        source = package_shots.get(item.get("shotId")) or {}
        item_media = _opening_frame_media(source, media)
        shot_purpose = source.get("purpose") or source.get("storyBeat")
        shot_summaries.append({
            "id": item_shot_id,
            "shotId": item_shot_id,
            "number": index,
            "durationSec": source.get("durationSec"),
            "purpose": shot_purpose,
            "storyBeat": source.get("storyBeat"),
            "acceptedUrl": item_media.get("clip"),
            "keyframeUrl": item_media.get("keyframeApproved"),
            "voiceUrl": item_media.get("vo"),
            "state": "complete" if _shot_complete(item) else item.get("badgeState") or "waiting",
            "selected": item_shot_id == shot_id,
        })

    session = {
        "schemaVersion": SCHEMA_VERSION,
        "readOnlyProjection": True,
        "episode": episode,
        "scene": scene,
        "sceneName": (package or {}).get("sceneName") or "Scene " + scene,
        "preservedPackageView": bool(state.get("preservedPackageView")),
        "sceneContinuityRules": _scene_continuity_rules(episode, scene),
        "status": status,
        "phase": phase,
        "headline": headline,
        "summary": summary,
        "selectedShotId": shot_id,
        "shot": ({
            "shotId": shot_id,
            "durationSec": shot.get("durationSec"),
            "purpose": shot.get("purpose") or shot.get("storyBeat"),
            "storyBeat": shot.get("storyBeat"),
            "visualPayoff": shot.get("visualPayoff") or shot.get("kidRead") or shot.get("emotionalIntent"),
            "emotionalIntent": shot.get("emotionalIntent"),
            "kidRead": shot.get("kidRead"),
            "adultRead": shot.get("adultRead"),
            "action": shot.get("action"),
            "dialogueLines": shot.get("dialogueLines") or [],
            "continuityConstraints": shot.get("continuityConstraints") or [],
            "directorRecord": shot.get("directorRecord") or {},
            "characters": shot.get("charactersInFrame") or [],
            "sourceType": shot.get("sourceType"),
            "sourceShotId": shot.get("sourceShotId"),
            "relayAnchorUrl": shot_media.get("relayAnchor"),
        } if shot_id else None),
        "progress": {"complete": completed, "total": len(all_shots)},
        "productionLine": _production_line(
            phase=phase, status=status, state=state, selected_state=selected_state,
            selected_shot_id=shot_id, all_animations_current=all_animations_current,
            all_shots=all_shots),
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
        "humanReview": _human_review_contract(
            phase=phase, status=status, state=state, selected_state=selected_state,
            artifact=artifact, shot=shot, ledger=package_ledger,
            quality_review=quality_review,
            blocker=blocker, primary=primary, decisions=decisions,
        ),
        "stages": stages,
        "lineageCurrent": bool((state.get("lineage") or {}).get("current")),
        "providerReady": bool((preflight.get("providerCapabilities") or {}).get("selectionReady")),
        "providerModel": (preflight.get("providerCapabilities") or {}).get("selectedVideoModelId"),
        "inspector": {
            "providerRequest": _prompt_contract(
                preflight, shot_id, phase, animation_contract),
            "preparedAnimationRequest": _prepared_animation_contract(package_ledger),
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
    if ((session.get("artifact") or {}).get("type") == "image-set"):
        out.add("select-keyframe-candidate")
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
    package, _ = cb_render.load_pkg(scene, episode)
    cb_render._shot(package, shot_id)
    if not _direction_current(scene, shot_id, "cinematography", episode):
        log("DIRECTOR — refreshing current cinematography direction before render sealing")
        cb_render.prepare_department(scene, "cinematography", shot_id, episode, log)
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
