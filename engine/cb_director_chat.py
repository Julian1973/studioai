#!/usr/bin/env python3
"""Small-context conversational Director for the Studio decision surface.

This is a text-reasoning assistant only. It cannot call a media provider, approve work,
reject work, or fire a retake. The browser may explicitly pass an accepted correction to
the existing production decision route after Julian chooses "Use correction".
"""
from __future__ import annotations

import json
import os
import re
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

import cb_llm
import cb_audio_authority
import cb_render


ROOT = Path(__file__).resolve().parent.parent
CHAT_DIR = ROOT / "cb-output" / "director-chat"
CHAT_MODEL = os.environ.get("OPENAI_STUDIO_AGENT_MODEL", cb_llm.VALIDATOR_MODEL)
VALID_STAGES = {
    "script", "storyboard", "scenelook", "keyframe", "voice", "animation",
    "animation-edit", "animation-refire", "continuity", "final",
}


class DirectorChatReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    response: str = Field(min_length=1, max_length=1800)
    changeSummary: str = Field(default="", max_length=500)
    correction: str = Field(default="", max_length=900)
    protectedElements: list[str] = Field(default_factory=list, max_length=8)
    readyToApply: bool
    editStartSec: float | None = None
    editEndSec: float | None = None


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _token(value):
    text = str(value or "").strip()
    if not text or not re.fullmatch(r"[A-Za-z0-9_.-]+", text):
        raise ValueError("episode, scene, shot and stage must be plain tokens")
    return text


def _path(episode, scene, shot_id, stage):
    episode, scene, stage = _token(episode), _token(scene), _token(stage)
    if stage not in VALID_STAGES:
        raise ValueError("unsupported Director chat stage")
    shot = _token(shot_id) if shot_id else "scene"
    return CHAT_DIR / f"{episode}_scene{scene}_{shot}_{stage}.json"


def history(episode, scene, shot_id, stage):
    path = _path(episode, scene, shot_id, stage)
    if not path.exists():
        return {"messages": [], "model": CHAT_MODEL, "zeroMediaSpend": True}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {"messages": []}
    return {
        "messages": list(data.get("messages") or [])[-20:],
        "model": data.get("model") or CHAT_MODEL,
        "zeroMediaSpend": True,
    }


def _scope_context(episode, scene, shot_id, stage, issue):
    pkg, _ = cb_render.load_pkg(scene, episode)
    shot = next((x for x in (pkg.get("shots") or []) if x.get("shotId") == shot_id), {})
    ledger = next((x for x in (pkg.get("continuityLedger") or [])
                   if x.get("shotId") == shot_id), {})
    department = (ledger.get("departmentWork") or {}).get(
        {"keyframe": "cinematography", "voice": "voice", "animation": "animation",
         "animation-edit": "animation", "animation-refire": "animation"}.get(stage, stage), {})
    continuity_out = shot.get("continuityOut") or {}
    closing_characters = [
        {
            "character": item.get("character"), "screenZone": item.get("screenZone"),
            "pose": item.get("pose"), "expression": item.get("expression"),
        }
        for item in (continuity_out.get("characters") or [])
    ]
    routed_audio = cb_audio_authority.route_lines(shot.get("dialogueLines") or [])
    return {
        "episode": episode,
        "scene": scene,
        "shotId": shot_id,
        "stage": stage,
        "issueOnScreen": str(issue or "")[:1400],
        "purpose": str(shot.get("purpose") or "")[:700],
        "orderedShotStates": {
            "opening": str(shot.get("openingPose") or "")[:900],
            "action": str(shot.get("purpose") or "")[:700],
            "landing": {
                "cameraSide": continuity_out.get("cameraSide"),
                "lighting": continuity_out.get("lighting"),
                "characters": closing_characters,
            },
        },
        "singleCameraTreatment": shot.get("camera"),
        "referenceRoles": shot.get("referenceSlots") or shot.get("keyframeReferenceSlots"),
        "exactDialogue": [
            {"speaker": x.get("speaker"), "exactText": x.get("exactText"),
             "delivery": x.get("delivery")}
            for x in routed_audio["spokenDialogue"]
        ],
        "seedanceSfxCues": routed_audio["seedanceSfxCues"],
        "currentStatus": ledger.get("status"),
        "durationSec": shot.get("durationSec"),
        "approvedTake": ledger.get("approvedTake"),
        "keyframeScreening": ledger.get("keyframeScreening"),
        "latestRejections": (
            list(ledger.get("keyframeRejections") or [])[-1:] +
            list(ledger.get("voiceRejections") or [])[-1:] +
            list(ledger.get("rejections") or [])[-1:]
        ),
        "audioAuthority": (
            "ElevenLabs v3 @Audio1 owns genuine spoken dialogue, voice identity, cadence, "
            "breath, pauses, mouth timing and silence. Snoring, snorting, sneezing, laughter "
            "and other non-verbal vocal events are timed Seedance 2.5 SFX and never enter @Audio1."
        ),
        "specialistDirection": department.get("approved") or department.get("candidate"),
    }


def _requested_edit_window(message, duration):
    """Return an explicit bounded time range; never invent one from vague language."""
    text = str(message or "").lower().replace("seconds", "s").replace("second", "s")
    patterns = (
        r"(?:from\s*)?(\d+(?:\.\d+)?)\s*s?\s*(?:-|to|through|until)\s*(\d+(?:\.\d+)?)\s*s?",
        r"between\s+(\d+(?:\.\d+)?)\s*s?\s+and\s+(\d+(?:\.\d+)?)\s*s?",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        start, end = float(match.group(1)), float(match.group(2))
        if 0 <= start < end <= float(duration or 0) + 0.05:
            return start, end
    return None


def _edit_review_frames(video_path, start, end):
    """Extract three local evidence frames for Director inspection without provider spend."""
    source = Path(str(video_path or ""))
    if not source.is_file():
        return []
    digest = hashlib.sha256(f"{source}:{start:.3f}:{end:.3f}".encode()).hexdigest()[:16]
    target = CHAT_DIR / "review-frames" / digest
    target.mkdir(parents=True, exist_ok=True)
    frames = []
    for index, timestamp in enumerate((start, (start + end) / 2, end), 1):
        output = target / f"frame-{index}.jpg"
        if not output.exists():
            subprocess.run(
                ["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{timestamp:.3f}",
                 "-i", str(source), "-frames:v", "1", "-q:v", "3", str(output)],
                check=True, capture_output=True,
            )
        frames.append(str(output))
    return frames


def chat(episode, scene, shot_id, stage, message, issue="", reviewer="Julian"):
    message = str(message or "").strip()
    if not message:
        raise ValueError("Director message cannot be blank")
    if len(message) > 3000:
        raise ValueError("Director message is too long")
    path = _path(episode, scene, shot_id, stage)
    saved = history(episode, scene, shot_id, stage)
    prior = list(saved.get("messages") or [])[-8:]
    context = _scope_context(episode, scene, shot_id, stage, issue)
    edit_window = None
    review_frames = []
    if stage == "animation-edit":
        edit_window = _requested_edit_window(message, context.get("durationSec"))
        if edit_window:
            review_frames = _edit_review_frames(
                context.get("approvedTake"), edit_window[0], edit_window[1])
            context["requestedEditWindow"] = {
                "startSec": edit_window[0], "endSec": edit_window[1],
                "inspectionFrames": len(review_frames),
            }
    system = (
        "You are Direct, the Crystal Bears conversational shot Director inside a professional "
        "animation review desk. Follow the FilmAgent directing discipline: accept ONE plain "
        "creative note, reshape only the affected shot instructions, and never redesign the "
        "shot. Discuss the visible creative result plainly and specifically. Protect "
        "the immutable script, canon, character identity, geography, approved continuity and "
        "existing approvals. Preserve the ordered opening, action and landing states unless the "
        "note explicitly targets one of them. Keep one coherent camera treatment. Diagnose the "
        "first failed production layer and propose the smallest bounded correction. Fill "
        "changeSummary with what will visibly change and protectedElements with the successful "
        "things that must remain unchanged. Never claim to approve, reject, generate, refire or "
        "spend. Never rewrite exact dialogue. Keep the response under 220 words. Set readyToApply "
        "true only when the correction is precise enough to become a rejection/iteration brief."
    )
    if stage == "animation-edit":
        system += (
            " This is a bounded edit of an approved take. If the reviewer has not supplied an "
            "exact start and end time, ask which seconds need editing and set readyToApply false. "
            "When a valid range and precise correction exist, inspect the supplied start, middle "
            "and end frames, recommend the smallest correction, preserve everything outside the "
            "range, set editStartSec and editEndSec exactly, and set readyToApply true."
        )
    elif stage == "animation-refire":
        system += (
            " This is a complete-take refire. Review the whole-shot problem and produce one precise "
            "full-shot correction while preserving every successful element."
        )
    user = json.dumps({
        "productionContext": context,
        "recentConversation": prior,
        "reviewer": reviewer,
        "message": message,
    }, ensure_ascii=False, separators=(",", ":"))
    reply = cb_llm.structured(
        system, user, DirectorChatReply, model=CHAT_MODEL,
        label=f"studio-director-chat-{stage}", log=lambda *args, **kwargs: None,
        images=review_frames or None)
    messages = prior + [
        {"role": "user", "text": message, "at": _now()},
        {"role": "director", "text": reply.response,
         "changeSummary": reply.changeSummary, "correction": reply.correction,
         "protectedElements": reply.protectedElements,
         "readyToApply": reply.readyToApply,
         "editStartSec": reply.editStartSec, "editEndSec": reply.editEndSec,
         "at": _now()},
    ]
    CHAT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"episode": episode, "scene": scene, "shotId": shot_id, "stage": stage,
               "model": CHAT_MODEL, "messages": messages[-20:]}
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    os.replace(temporary, path)
    return {"reply": reply.model_dump(), "messages": messages[-20:], "model": CHAT_MODEL,
            "zeroMediaSpend": True}
