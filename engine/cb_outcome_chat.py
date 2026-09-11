"""Explicit chat decisions bound to the exact reviewed artifact or WATCH request."""
import hashlib
import json
import re
from pathlib import Path

import cb_db
import cb_render as R
import cb_episode_budget as budget


def intent(message):
    text = re.sub(r"[.!]+$", "", str(message).strip().lower())
    if text in {"apply and refire", "apply & refire", "apply and refire keyframe"}:
        return {"kind": "retake-keyframe"}
    match = re.fullmatch(r"approve (?:the )?episode budget (?:of )?\$([0-9]+(?:\.[0-9]{1,2})?)", text)
    if match:
        return {"kind": "budget", "amount": match.group(1)}
    if text in {"approve", "approved", "approve it", "yes approve", "yes approve it"}:
        return {"kind": "approve"}
    if text in {"approve a", "approve b"}:
        return {"kind": "approve", "targetKind": "keyframe", "candidateId": text[-1].upper()}
    named = {"approve keyframe": "keyframe", "approve voice": "voice",
             "approve render request": "request", "approve watch request": "request",
             "fire": "request", "render it": "request", "approve render": "render"}
    if text in named:
        return {"kind": "approve", "targetKind": named[text]}
    if text in {"continue", "prepare next", "retry preparation"}:
        return {"kind": "continue"}
    commands = {"show prompt": "prepare-request", "show watch request": "prepare-request",
                "prepare watch": "prepare-request", "generate keyframe": "build-keyframe",
                "show me the keyframe": "build-keyframe", "generate voice": "build-voice",
                "let me hear it": "build-voice", "next shot": "next-shot"}
    return {"kind": commands[text]} if text in commands else None


def _file(path):
    p = Path(path) if path else None
    if not p or not p.is_file():
        return None
    with p.open("rb") as handle:
        return {"path": str(p), "hash": hashlib.file_digest(handle, "sha256").hexdigest()}


def target(episode, scene, shot_id, stage):
    if not shot_id:
        return None
    pkg, _ = R.load_pkg(scene, episode)
    shot = R._shot(pkg, shot_id)
    led = R._ledger(pkg, shot_id)
    kind, artifact = None, None
    if stage == "keyframe" and led.get("keyframeCandidate"):
        kind = "keyframe"
        record = led["keyframeCandidate"]
        artifact = {"record": record, "file": _file(record.get("path")),
                    "candidates": [{"record": c, "file": _file(c.get("path"))} for c in led.get("keyframeCandidates", [])],
                    "selected": led.get("selectedKeyframeCandidateId")}
    elif stage == "voice" and led.get("voPath") and not (led.get("voiceApproval") or {}).get("approved"):
        kind = "voice"
        artifact = {"file": _file(led["voPath"]), "generatedFrom": led.get("voGeneratedFrom"),
                    "timing": _file(led.get("voTimingPath"))}
    elif stage == "animation":
        if led.get("pendingSpendAuth"):
            kind, artifact = "request", led["pendingSpendAuth"]
        elif led.get("candidatePaths") and led.get("status") != "approved":
            kind = "render"
            artifact = {"files": [_file(p) for p in led["candidatePaths"]], "batch": led.get("batch")}
    if not kind:
        return None
    record = {"episode": episode, "scene": str(scene), "shotId": shot_id,
              "kind": kind, "artifact": artifact, "shot": shot}
    digest = hashlib.sha256(json.dumps(record, sort_keys=True, default=str).encode()).hexdigest()
    return {"kind": kind, "hash": digest, "shotId": shot_id,
            "batchId": led.get("batchId") if kind == "render" else None,
            "label": {"keyframe": "keyframe", "voice": "voice performance",
                      "request": "WATCH prompt, references and script", "render": "finished render"}[kind]}


def execute(episode, scene, shot_id, stage, reviewed_hash, reviewer="Julian", candidate_id=None):
    with cb_db.scene_lease(R.ROOT, episode, scene, "chat-reviewed-decision"):
        current = target(episode, scene, shot_id, stage)
        if not current or current["hash"] != reviewed_hash:
            raise R.Refused("The reviewed item changed. Review its current version before approving.")
        pkg, _ = R.load_pkg(scene, episode)
        led = R._ledger(pkg, shot_id)
        kind = current["kind"]
        if kind == "keyframe":
            if candidate_id:
                R.select_keyframe_candidate(scene, shot_id, candidate_id, episode)
            return R.approve_keyframe(scene, shot_id, episode, reviewed_by=reviewer)
        if kind == "voice":
            return R.approve_voice(scene, shot_id, episode, reviewed_by=reviewer)
        if kind == "request":
            auth = led["pendingSpendAuth"]
            disclosure = auth.get("disclosure") or {}
            count = int(disclosure.get("candidateCount") or disclosure.get("candidates") or 1)
            return R.fire_shot(scene, shot_id, episode, candidates=count,
                               spend_token=auth["token"])
        count = len(led.get("candidatePaths") or [])
        if candidate_id is None and count != 1:
            raise R.Refused("Select the render candidate in WATCH before approving this batch.")
        try:
            selected = int(candidate_id) if candidate_id is not None else 1
        except (ValueError, TypeError):
            raise R.Refused("Choose a numbered render candidate from this reviewed batch.")
        if not 1 <= selected <= count:
            raise R.Refused("That render candidate is not in the reviewed batch.")
        return R.approve_shot(scene, shot_id, selected, episode, reviewed_by=reviewer)


def _direction(episode, scene, shot_id, stage):
    R.prepare_department(scene, stage, shot_id, episode)
    pkg, _ = R.load_pkg(scene, episode)
    work, _ = R._department_container(pkg, scene, shot_id, stage, episode)
    if work.get("candidate"):
        R.decide_department(scene, stage, "approved", shot_id,
                            "Automatic technical preparation for outcome review.", episode,
                            "Studio Director")


def prepare(episode, scene, shot_id, stage):
    if not budget.status(episode)["approved"]:
        raise budget.BudgetRefused("Approve the episode allowance in chat first")
    with cb_db.scene_lease(R.ROOT, episode, scene, "chat-outcome-preparation"):
        pkg, _ = R.load_pkg(scene, episode)
        shots = R.production_contracts.active_shots(pkg)
        shot_id = shot_id or (shots[0]["shotId"] if shots else None)
        if not shot_id:
            raise R.Refused("This scene has no active shots")
        shot = R._shot(pkg, shot_id)
        led = R._ledger(pkg, shot_id)
        if stage == "keyframe":
            if not R._shot_uses_own_keyframe(shot, led):
                return prepare(episode, scene, shot_id, "voice")
            if led.get("keyframeCandidate") or (led.get("keyframeApproval") or {}).get("approved"):
                return {"existing": True}
            if not R.scenelook_status(scene, episode).get("current"):
                _direction(episode, scene, None, "look")
                rec = R._load_scenelook_rec(scene, episode)
                if not rec.get("candidate"):
                    R.generate_scenelook_plate(scene, episode)
                # Scene world is an internal reference. The user reviews the composed SEE
                # outcome; this stamp must never claim a human reviewed the reference.
                R.approve_scenelook(scene, episode, reviewed_by="Studio Director — internal scene reference")
            _direction(episode, scene, shot_id, "cinematography")
            return R.keyframe_shot(scene, shot_id, episode)
        if stage == "voice":
            if not R.cb_audio_authority.spoken_dialogue_lines(shot):
                return prepare(episode, scene, shot_id, "animation")
            if led.get("voPath"):
                return {"existing": True}
            _direction(episode, scene, shot_id, "voice")
            return R.regen_voice_shot(scene, shot_id, episode)
        if stage == "animation":
            if led.get("pendingSpendAuth"):
                return {"existing": True}
            _direction(episode, scene, shot_id, "animation")
            try:
                return R.fire_shot(scene, shot_id, episode, candidates=1)
            except R.Refused:
                pkg, _ = R.load_pkg(scene, episode)
                if R._ledger(pkg, shot_id).get("pendingSpendAuth"):
                    return {"requestReady": True}
                raise
        raise ValueError("Unsupported outcome")


def retake_keyframe(episode, scene, shot_id, reviewed_hash, correction, reviewer="Julian"):
    """One explicitly requested SEE retake, bound to the reviewed candidate."""
    if not str(correction).strip():
        raise R.Refused("A precise correction is required")
    if not budget.status(episode)["approved"]:
        raise budget.BudgetRefused("Approve the episode allowance first")
    with cb_db.scene_lease(R.ROOT, episode, scene, "chat-keyframe-retake"):
        current = target(episode, scene, shot_id, "keyframe")
        if not current or current["hash"] != reviewed_hash:
            raise R.Refused("The SEE candidate changed. Review the current image before refiring.")
        R.reject_keyframe(scene, shot_id, correction, episode, reviewed_by=reviewer)
        # Shared build refreshes affected direction and validates the final prompt.
        # Keep the approved plate and media approvals; return exactly one candidate.
        return R.build_keyframe(scene, shot_id, episode, compare=False)


if __name__ == "__main__":
    import sys
    if sys.argv[1] == "retake-keyframe":
        retake_keyframe(*sys.argv[2:])
    elif sys.argv[1] == "prepare":
        episode, scene, shot_id, stage = sys.argv[2:]
        prepare(episode, scene, None if shot_id == "scene" else shot_id, stage)
    else:
        episode, scene, shot_id, stage, reviewed_hash, reviewer, *choice = sys.argv[1:]
        execute(episode, scene, shot_id, stage, reviewed_hash, reviewer, choice[0] if choice else None)
