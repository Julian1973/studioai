"""Shared, side-effect-free production contracts for UI, workers and editorial.

Accepted bytes are historical evidence. Draft readiness is a separate calculation.
No function here grants approval, calls a provider, or changes production state.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re

POLICY_VERSION = "production-contracts-1"
AUDIT_FIELDS = frozenset({
    "revision", "packageRevision", "createdAt", "updatedAt", "savedAt",
    "reviewedAt", "reviewedBy", "reviewed_by", "auditNotes", "internalNotes",
})


def content(value):
    """Strip only declared bookkeeping fields; unknown fields remain significant."""
    if isinstance(value, dict):
        return {k: content(v) for k, v in value.items() if k not in AUDIT_FIELDS}
    if isinstance(value, list):
        return [content(v) for v in value]
    return value


def content_hash(value):
    return hashlib.sha256(json.dumps(content(value), sort_keys=True,
                                     ensure_ascii=False).encode()).hexdigest()


def working_signature_matches(recorded, expected):
    # Existing saved signatures can be carried forward without rewriting their history.
    def project(sig):
        return {k: v for k, v in (sig or {}).items() if k != "packageRevision"}
    return bool(recorded) and project(recorded) == project(expected)


def active_shots(pkg):
    def retired(shot):
        status = str(shot.get("status") or "").strip().lower()
        return (status in {"superseded", "archived", "inactive"} or
                status.startswith("skipped-") or bool(shot.get("superseded")))
    return [shot for shot in pkg.get("shots", []) if not retired(shot)]


def file_hash(path):
    if not path:
        return None
    try:
        with pathlib.Path(path).open("rb") as handle:
            return hashlib.file_digest(handle, "sha256").hexdigest()
    except (OSError, ValueError):
        return None


def accepted_asset(ledger):
    approval = ledger.get("approval") or {}
    take, frame = ledger.get("approvedTake"), ledger.get("harvestFrame")
    declared = bool(approval.get("approved") and take)
    intact = bool(declared and approval.get("contentHash") and
                  approval.get("harvestHash") and
                  file_hash(take) == approval["contentHash"] and
                  file_hash(frame) == approval["harvestHash"])
    return {"accepted": declared, "intact": intact,
            "path": take, "framePath": frame,
            "assetId": approval.get("contentHash"),
            "approvedAt": approval.get("at"),
            "reviewer": approval.get("reviewed_by") or approval.get("reviewedBy"),
            "reason": None if intact else
            "accepted-asset-missing-or-changed" if declared else "no-accepted-asset"}


def shot_next_action(row):
    """One read-only next step for the desk, chat and navigation. Never authorizes spend."""
    current, pending = row.get("current") or {}, row.get("pending") or {}
    allowed = row.get("allowedActions") or {}
    accepted = row.get("acceptedAsset") or {}
    def step(code, stage, label, state="ready", reason=None):
        return {"code": code, "stage": stage, "shotId": row["shotId"],
                "label": label, "state": state, "reason": reason}
    if accepted.get("accepted") and not accepted.get("intact"):
        return step("recover-media", "animation", "Restore the accepted media", "blocked", row.get("sub"))
    if accepted.get("intact") and not (row.get("amendment") or {}).get("active"):
        return step("review-cut", "continuity", "Review the accepted take in the scene cut", "accepted")
    if row.get("needsKeyframe", not row.get("keyframeSatisfied")) and not current.get("keyframe", row.get("keyframeSatisfied")):
        if pending.get("keyframe"):
            return step("review-keyframe", "keyframe", "Review your keyframe", "review" if allowed.get("approveKeyframe") else "needs-attention", row.get("sub"))
        return step("prepare-keyframe", "keyframe", "Prepare your keyframe")
    if row.get("talky") and not current.get("voice"):
        return step("review-voice" if pending.get("voice") else "prepare-voice", "voice",
                    "Listen to your voice performance" if pending.get("voice") else "Prepare your voice performance",
                    "review" if pending.get("voice") else "ready")
    if pending.get("animation") or row.get("animState") == "candidates-pending":
        return step("review-candidate", "animation", "Watch and review your render",
                    "review" if allowed.get("approveAnimation") else "needs-attention", row.get("sub"))
    if pending.get("request"):
        return step("review-request", "animation", "Review prompt, references and script", "review")
    return step("prepare-request", "animation", "Prepare your animation request")


def revision_impact(stage, shot_id):
    """Conservative impact disclosure, not permission to mutate another shot."""
    affected = {"keyframe": ["keyframe", "animation request", "new render"],
                "voice": ["voice performance", "animation request", "new render"],
                "animation": ["animation request", "new render"],
                "animation-edit": ["selected render interval"],
                "animation-refire": ["animation request", "new render"]}.get(stage, ["shot direction", "dependent production inputs"])
    return {"shotId": shot_id, "rebuild": affected,
            "preserve": "Accepted versions stay in history. Unaffected shots keep their approvals.",
            "continuity": "If the landing pose, props, location or dialogue changes, review the next shot's continuity before generating it. Existing downstream media is not rewritten."}


def command_outcome(returncode, gate, lines):
    for line in reversed(lines):
        if line.startswith("STUDIO_OUTCOME "):
            try:
                outcome = json.loads(line[len("STUDIO_OUTCOME "):])["outcome"]
            except (ValueError, KeyError, TypeError):
                continue
            if outcome in {"completed", "needs_spend_approval", "submission_unknown", "failed"}:
                return outcome
    if returncode == 0:
        return "completed"
    if any("SPEND NOT APPROVED" in line for line in lines):
        return "needs_spend_approval"
    if any("submission outcome is unknown" in line.lower() for line in lines):
        return "submission_unknown"
    return "failed"


def visual_event_text(text):
    """Canonicalize notation, never paraphrase action or dialogue words."""
    text = str(text or "")
    text = re.sub(r"(\d+(?:\.\d+)?)\s*(?:seconds?|s)?\s*(?:[–—-]|until|to)\s*"
                  r"(\d+(?:\.\d+)?)\s*(?:seconds?|s)\b",
                  lambda m: f"{m[1]} seconds until {m[2]} seconds", text, flags=re.I)
    return " ".join(text.split()).casefold()


def validate_timeline(events, duration):
    """Concurrent channels are valid; one channel cannot contain conflicting intervals."""
    errors, channels = [], {}
    for event in events:
        try:
            start, end = float(event["startSec"]), float(event["endSec"])
            channel = str(event["channel"])
            if not channel or not 0 <= start < end <= float(duration):
                raise ValueError()
            channels.setdefault(channel, []).append((start, end))
        except (KeyError, TypeError, ValueError):
            errors.append("Timeline event needs a channel and an increasing interval inside the shot.")
    for channel, intervals in channels.items():
        ordered = sorted(set(intervals))
        if any(b[0] < a[1] for a, b in zip(ordered, ordered[1:])):
            errors.append(f"Conflicting intervals on timeline channel {channel}.")
    return {"ready": not errors, "errors": errors}


def shot_handoff_instruction(shot, *, still=False):
    """Emit the declared editorial join without changing legacy approved shot records."""
    transition = shot.get("shotTransition") or {}
    kind = transition.get("type")
    if kind not in {"cut", "continuation"}:
        return ""
    source = transition.get("stateSourceShotId") or "the preceding shot"
    if kind == "cut":
        instruction = (
            f"EDITORIAL HANDOFF — planned cut from {source}. "
            + ("Compose this shot's new opening keyframe in its authored camera view. "
               if still else "Begin on this shot's own approved opening keyframe and authored camera view. ")
            + "Inherit world positions, "
            "prop ownership, action phase and emotional state from the incoming continuity "
            "record; do not inherit the previous camera composition. For reverse coverage, "
            "reproject the same geography from the new viewpoint, preserve matched eyelines "
            "and the interaction axis, and never mirror the set or reverse playback. "
            "Do not interpolate, morph or travel from the preceding frame to create this cut. "
            "The edit joins the separate shots."
        )
    else:
        instruction = (
            f"EDITORIAL HANDOFF — continuous action from {source}. Use its approved "
            "landing frame as the opening anchor and carry positions, facing, movement "
            "direction, action phase, props, eyelines, camera height and movement, light direction "
            "and emotion forward without replaying the action. Use the actual approved "
            "landing state; a matching pose alone does not establish matching motion."
        )
    reason = str(transition.get("reason") or "").strip()
    return instruction + (" Editorial purpose: " + reason if reason else "")
