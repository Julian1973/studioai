#!/usr/bin/env python3
"""The live specialist workers behind Crystal Bears Studio departments.

This is deliberately not a second production pipeline.  It contains the people: each
worker reads the existing approved shot contract and the relevant repository skill,
prepares one visible candidate brief, then stops.  cb_render persists the candidate,
Julian edits/approves it, and the existing image/voice/video functions consume the exact
approved provider text.  No function in this module calls cb_gen or spends media money.
"""
from __future__ import annotations

import json
import pathlib
import re
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

import cb_llm

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

RUNTIME_START = "<!-- RUNTIME_WORKER_START -->"
RUNTIME_END = "<!-- RUNTIME_WORKER_END -->"

SKILLS = {
    "director": ROOT / "skills/crystal-bears-director/SKILL.md",
    "cinematography": ROOT / "skills/crystal-bears-cinematographer/SKILL.md",
    "dp": ROOT / "skills/crystal-bears-dp/SKILL.md",
    "voice": ROOT / "skills/crystal-bears-voice-director/SKILL.md",
    "animation": ROOT / "skills/crystal-bears-camera/SKILL.md",
    "review": ROOT / "skills/crystal-bears-continuity/SKILL.md",
    "post": ROOT / "skills/crystal-bears-post/SKILL.md",
    "producer": ROOT / "skills/crystal-bears-producer/SKILL.md",
}

DEPARTMENTS = [
    {"id": "story", "stage": "storyboard", "department": "Story & Direction",
     "worker": "Director", "influences": "Pete Docter · Andrew Stanton",
     "skill": "crystal-bears-director", "output": "approved storyboard and shot purpose"},
    {"id": "look", "stage": "scenelook", "department": "Look Development",
     "worker": "Cinematographer / DP", "influences": "Patrick Lin · Jean-Claude Kalache",
     "skill": "crystal-bears-cinematographer", "output": "exact Scene Look plate brief"},
    {"id": "cinematography", "stage": "keyframe", "department": "Cinematography",
     "worker": "Cinematographer / DP", "influences": "Patrick Lin · Jean-Claude Kalache",
     "skill": "crystal-bears-cinematographer", "output": "exact opening-frame prompt"},
    {"id": "voice", "stage": "voice", "department": "Voice",
     "worker": "Voice Director", "influences": "character-specific ElevenLabs v3 acting craft",
     "skill": "crystal-bears-voice-director", "output": "exact performed text sent to ElevenLabs"},
    {"id": "animation", "stage": "animation", "department": "Animation",
     "worker": "Animation Director / Camera", "influences": "feature-animation performance and camera craft",
     "skill": "crystal-bears-camera", "output": "exact Seedance prompt"},
    {"id": "review", "stage": "continuity", "department": "Director Review & Continuity",
     "worker": "Director Review / Continuity Supervisor", "influences": "evidence-led dailies review",
     "skill": "crystal-bears-continuity", "output": "review of the actual rendered media"},
    {"id": "post", "stage": "final", "department": "Final & Post",
     "worker": "Post Supervisor", "influences": "picture editing · sound design · re-recording mix",
     "skill": "crystal-bears-post", "output": "review of the actual assembled scene"},
]


def roster():
    """The people shown in Studio.  `loaded` proves the running source can open the skill."""
    out = []
    for rec in DEPARTMENTS:
        item = dict(rec)
        key = {"story": "director", "look": "cinematography",
               "cinematography": "cinematography", "voice": "voice",
               "animation": "animation", "review": "review", "post": "post"}[rec["id"]]
        item["loaded"] = bool(load_runtime_skill(key))
        if rec["id"] == "cinematography":
            item["loaded"] = item["loaded"] and bool(load_runtime_skill("dp"))
        out.append(item)
    return out


def load_runtime_skill(worker):
    """Read the marked runtime contract from the real SKILL.md on every worker call.

    The repository's historical skill documents contain useful research plus superseded
    pipeline notes.  Only the concise marked contract is executable; the source document
    remains available to humans without letting stale instructions silently enter a call.
    """
    path = SKILLS[worker]
    text = path.read_text(encoding="utf-8")
    if RUNTIME_START not in text or RUNTIME_END not in text:
        raise RuntimeError(f"{path} has no executable runtime worker contract")
    return text.split(RUNTIME_START, 1)[1].split(RUNTIME_END, 1)[0].strip()


# SIMPLIFIED 2026-07-21 (Julian's own words: "I don't want rigid flags and structures, and
# the prompts need to be really simple. We've overengineered everything on this."). These
# three schemas used to carry 5-7 structured breakdown fields each (composition, lensAnd-
# CameraRelationship, performanceArc, ...) — confirmed, before this change, that NONE of
# them were ever read anywhere downstream (cb_render.py, cb-studio/serve.py, app.html all
# only ever touch .providerPrompt). They existed purely to make the LLM call feel more
# structured; in practice they were dead weight the model had to fill in and a reviewer
# never saw. Down to the one thing that ships (providerPrompt) plus one plain-language
# verdict (doesItLand) — Julian's own framing: "each one of these phases, they have to
# make sure that it lands."
class LookDirection(BaseModel):
    providerPrompt: str = Field(min_length=40)
    doesItLand: str = Field(min_length=1)


class CinematographyDirection(BaseModel):
    shotId: str
    providerPrompt: str = Field(min_length=40)
    doesItLand: str = Field(min_length=1)


# SIMPLIFIED 2026-07-21 (the same pass as LookDirection/CinematographyDirection/
# AnimationDirection, above): dramaticIntention/subtext/cadenceAndBreath/timingAndBody
# duplicated ground the storyboard's own Voice Performance role (cb_creative.VoicePerformance,
# gate5_voice) already covers — that authoring already happened, following VOICE_PERFORMANCE_
# CANON.md, and its result lands on the shot's own dialogueLines[].delivery (cb_handover._
# dialogue_lines maps voicePerformances[].elevenLabsV3Direction straight onto it). Asking THIS
# stage to re-derive intention/subtext/cadence from scratch, in its own separate fields nobody
# read (sceneIntention had zero call sites either), was the exact same "rigid structure,
# nothing downstream reads it" pattern already fixed for the other three departments.
class VoiceLineDirection(BaseModel):
    speaker: str
    exactDialogue: str
    performedText: str


class VoiceDirection(BaseModel):
    shotId: str
    lines: List[VoiceLineDirection]
    doesItLand: str = Field(min_length=1)


class AnimationDirection(BaseModel):
    shotId: str
    providerPrompt: str = Field(min_length=40)
    doesItLand: str = Field(min_length=1)


class ReviewFinding(BaseModel):
    severity: Literal["BLOCK", "NOTE"]
    criterion: str
    visibleEvidence: str
    owner: Literal["director", "cinematography", "voice", "animation", "continuity", "post"]
    suggestedAction: str


class CandidateAssessment(BaseModel):
    candidateId: str
    verdict: Literal["recommend-approve", "revise", "block"]
    summary: str


class MediaReview(BaseModel):
    artifactType: Literal["keyframe", "animation", "final"]
    verdict: Literal["recommend-approve", "revise", "block"]
    summary: str
    intendedRead: str
    actualRead: str
    finalFrameUsable: bool = False
    recommendedCandidate: Optional[str] = None
    candidateAssessments: List[CandidateAssessment] = Field(default_factory=list)
    findings: List[ReviewFinding] = Field(default_factory=list)


def _system(worker, job):
    return (load_runtime_skill(worker) + "\n\nTHIS RUN:\n" + job +
            "\n\nYou are preparing a candidate for human approval. Do not claim it is "
            "approved. Do not call or simulate a media provider. Return only the requested "
            "structured result.")


def _j(value, limit=22000):
    return json.dumps(value, ensure_ascii=False, indent=1)[:limit]


class BeatSplit(BaseModel):
    """One beat's own creative content, inside a scene the mechanical parser already
    divided. firstEventIndex is the ONLY structural decision the Director makes here —
    the index (from the supplied, locked script-event list) of the event that OPENS this
    beat; the beat covers every event up to the next beat's own firstEventIndex, or the
    scene's last event. Dialogue text is never authored here — see cb_intake.py."""
    sceneNumber: int
    firstEventIndex: int = Field(ge=0)
    beatCode: str = Field(min_length=1)
    storyBeat: str = Field(min_length=1)
    want: str = Field(min_length=1)
    need: str = Field(min_length=1)
    kidRead: str = Field(min_length=1)
    adultRead: str = Field(min_length=1)
    emotionalIntent: str = Field(min_length=1)


class EpisodeVisionDirection(BaseModel):
    """Same 14 fields cb_creative.EpisodeVision already defines — reused verbatim (never
    a second vision schema) so an approved candidate here drops straight into
    cb_creative.py's own {episode}_episode_vision.json shape without translation."""
    premise: str
    dramaticQuestion: str
    theme: str
    externalJourney: str
    internalJourney: str
    relationshipChanges: str
    emotionalCurve: str
    comedyCurve: str
    setupPayoffMap: str
    visualMotifs: str
    sonicMotifs: str
    climax: str
    resolution: str
    intendedFinalFeeling: str


class StoryIntakeDirection(BaseModel):
    title: str = Field(min_length=1)
    logline: str = Field(min_length=1)
    leadBear: str = ""
    episodeVision: EpisodeVisionDirection
    beats: List[BeatSplit] = Field(min_length=1)


def prepare_story(script_events, cast_by_scene, *, log=print):
    """The Director's FIRST task on a newly uploaded script (2026-07-19): decide where
    each scene's own beats begin, and author the creative content around them. Scene
    order, characters and every spoken line are LOCKED SOURCE EVIDENCE, supplied here
    only as read-only context for the Director's own understanding — the caller
    (cb_intake.py) re-inserts the exact source text mechanically afterward and never
    trusts this call's own reproduction of it. Deliberately does NOT use the shared _j()
    truncation helper for the script content: cutting the script short here would mean
    the Director never even sees, let alone preserves, everything past the cut."""
    return cb_llm.structured(
        _system("director",
                "You are breaking a LOCKED, already-approved script into its scenes and "
                "beats for this studio's storyboard pipeline. The script's scene order, "
                "its characters and every spoken line are LOCKED SOURCE EVIDENCE — you "
                "never rewrite, drop or invent a line; the dialogue text below is supplied "
                "for your own understanding only and is reinserted mechanically afterward "
                "exactly as given, so nothing you write for it is ever used. Your job is "
                "entirely: (1) decide, per scene, where each real dramatic or comedic beat "
                "begins — one firstEventIndex per beat, naming the index of the event that "
                "OPENS that beat; a beat covers every event up to the next beat's own "
                "firstEventIndex, or the scene's last event — a real change in what the "
                "beat is about, never an arbitrary paragraph split; and (2) author the "
                "whole-episode vision plus, for every beat, storyBeat (what happens and "
                "why, in your own words), want (the surface goal), need (the underlying "
                "emotional need), kidRead and adultRead (the two co-viewing layers this "
                "show is built on), and emotionalIntent. Also suggest the episode's title, "
                "logline and lead bear. Every scene needs at least one beat, and its first "
                "beat's own firstEventIndex must equal that scene's own first event "
                "index."),
        "SCRIPT EVENTS, IN ORDER — index : scene : type : [speaker :] text (dialogue text "
        "is LOCKED, shown for context only, never to be altered):\n"
        + json.dumps(script_events, ensure_ascii=False, indent=1) +
        "\n\nCAST PRESENT PER SCENE (mechanically detected from the script text):\n"
        + json.dumps(cast_by_scene, ensure_ascii=False, indent=1) +
        "\n\nReturn the episode vision, a suggested title/logline/leadBear, and the "
        "ordered beat split with creative content for every beat, across every scene.",
        StoryIntakeDirection, label="department_story", log=log)


def prepare_look(context, *, log=print):
    return cb_llm.structured(
        _system("cinematography",
                "Write the exact image-provider prompt for this scene's environment-only "
                "Scene Look plate: the place itself — light, palette, material, atmosphere. "
                "No character, no shot composition. Keep it plain and concrete."),
        "APPROVED SCENE CONTEXT:\n" + _j(context) +
        "\n\nReturn the provider prompt, and one plain sentence on whether this place "
        "reads true to the scene.",
        LookDirection, label="department_look", log=log)


def prepare_cinematography(context, images, compiled_brief, *, log=print):
    """THE DELIVERY-IS-COMPILATION FIX (2026-07-21), simplified the same day per Julian's
    own framing ("the cinematographer and the director need to work on that to be able to
    create the exact prompt that they need to do to make that key frame come to life,
    based on the magic they've done"): compiled_brief is what the Director and
    Cinematographer already decided together at storyboard time — cb_engine.
    compile_keyframe_prompt's own deterministic output. This call turns that decision into
    the exact keyframe prompt, grounded in it, never inventing a composition it doesn't
    already contain."""
    return cb_llm.structured(
        _system("cinematography",
                "The Director and Cinematographer already decided this shot together — "
                "the brief below IS that decision, the magic already done. Your job is to "
                "turn it into the exact keyframe prompt: real photographic language (lens, "
                "height, light) for what's already there, nothing new invented. The "
                "attached images are in the labelled order given in the context.") +
                "\n\n" + load_runtime_skill("dp"),
        "THE APPROVED BRIEF — what was already decided:\n" + compiled_brief +
        "\n\nSHOT AND ORDERED IMAGE LABELS:\n" + _j(context) +
        "\n\nReturn the exact keyframe prompt, bound to the labelled references, and one "
        "plain sentence on whether this frame will land the shot.",
        CinematographyDirection, label="department_cinematography", log=log,
        images=images)


_TAG = re.compile(r"\[[^\]]+\]")
_WORD = re.compile(r"[A-Za-z0-9']+")


def _spoken_words(text):
    return [w.lower() for w in _WORD.findall(_TAG.sub("", text or ""))]


def validate_voice_direction(result, locked_lines):
    got = result.lines
    if len(got) != len(locked_lines):
        raise RuntimeError(f"Voice Director returned {len(got)} line(s); {len(locked_lines)} are locked")
    for idx, (out, locked) in enumerate(zip(got, locked_lines), start=1):
        if out.speaker.strip().lower() != str(locked["speaker"]).strip().lower():
            raise RuntimeError(f"Voice Director changed speaker on line {idx}")
        if _spoken_words(out.exactDialogue) != _spoken_words(locked["exactText"]):
            raise RuntimeError(f"Voice Director changed locked dialogue on line {idx}")
        if _spoken_words(out.performedText) != _spoken_words(locked["exactText"]):
            raise RuntimeError(f"Voice Director added, dropped or changed words on line {idx}")
    return result


def _voice_line_briefs(locked_lines):
    """Each line's own already-approved direction, pulled OUT of the generic shot JSON and
    labelled so it can't be missed. `delivery` is the storyboard's Voice Performance role's
    own V3-tagged performance (cb_creative.gate5_voice, following VOICE_PERFORMANCE_CANON.md
    — intention, subtext, the thought before the line, operative words, tag discipline, all
    already decided there), mapped onto the shot's dialogueLines at promotion time
    (cb_handover._dialogue_lines: elevenLabsV3Direction -> delivery). Before this fix this
    sat unread inside context's buried shot JSON and the LLM re-invented a performance from
    the bare locked words every time — the exact bug this function closes."""
    out = []
    for ln in locked_lines:
        out.append(f'{ln.get("speaker")}: "{ln.get("exactText")}"\n'
                    f'  APPROVED DIRECTION: {ln.get("delivery") or "(none authored yet)"}')
    return "\n".join(out)


def prepare_voice(context, locked_lines, *, log=print):
    """THE DELIVERY-IS-COMPILATION FIX (2026-07-21), same pattern and same day as
    Cinematography/Animation, per Julian's own instruction ("they need to deliver the beat
    through the v3 prompting [emotion] and cadence best practice of which you have the
    documents"): each line's own APPROVED DIRECTION already IS that V3/cadence best
    practice, decided once at storyboard time by the Voice Performance role reading the
    show's own Voice Performance Canon. This stage's job is finalising that direction into
    the literal ElevenLabs V3 string — never re-deciding the performance from scratch."""
    result = cb_llm.structured(
        _system("voice",
                "Each line below already carries its APPROVED DIRECTION — the Voice "
                "Performance role's own V3 tags, cadence and intention, decided once at "
                "storyboard time following the show's Voice Performance Canon. Your job is "
                "to finalise that direction into the exact text ElevenLabs will receive: "
                "real V3 tags, punctuation as cadence, every locked word present and in "
                "order. Do not re-direct the performance — the acting choice is already "
                "made; you are writing it down correctly."),
        "THE SHOT'S LINES, EACH WITH ITS ALREADY-APPROVED DIRECTION:\n" +
        _voice_line_briefs(locked_lines) +
        "\n\nSHOT CONTEXT:\n" + _j(context) +
        "\n\nReturn each line's exact performedText (same order/speaker/words as above), "
        "and one plain sentence on whether this performance will land the beat.",
        VoiceDirection, label="department_voice", log=log)
    return validate_voice_direction(result, locked_lines)


def prepare_animation(context, images, compiled_brief, *, log=print):
    """THE DELIVERY-IS-COMPILATION FIX (2026-07-21), simplified the same day per Julian's
    own framing ("once we've built the key frame, they need to think of how, when they see
    the key frame, they are then going to bring that to life through animation to ensure
    that the beat lands"): compiled_brief is what the Director, Producer and
    Cinematographer already decided together at storyboard time — cb_engine.
    compile_shot_contract's own deterministic output. This call's real job is looking at
    the actual approved keyframe (the first attached image) and animating it so the beat's
    payoff actually lands — the joke hits, the feeling reads."""
    return cb_llm.structured(
        _system("animation",
                "The first image is the approved keyframe — look at it. Everything below "
                "is what the Director, Producer and Cinematographer already decided at "
                "storyboard time. Your job: bring that exact frame to life so the beat "
                "lands — ground every choice in the brief and the frame, never invent new "
                "staging or performance. Remaining attachments follow the reference order "
                "in the context.\n\n"
                # THE TEMPO-MAP LAW (2026-07-23, Julian, watching a real take play at one
                # even middle pace — "lacks the heart pace and feeling"): compared directly
                # against the one approved take this show has, whose prompt carried
                # explicit timestamped segments; the takes without them all rendered flat.
                "STRUCTURE LAW — THE TEMPO MAP: the performance body of providerPrompt "
                "MUST be broken into chronological TIMESTAMPED segments covering the full "
                "shot duration (e.g. '0.0-4.5s:', '4.5-7.0s:', ... to the final second — "
                "use the real fireDurationSec from the context). Each segment states its "
                "own TEMPO explicitly — fast/brisk/accelerating vs slowed/held/near-still "
                "— because the CONTRAST between quick chaos and a slowed-down beat IS the "
                "comedy. Honor the brief's own 'Tempo:' design and each dialogue line's "
                "startSec/endSec when placing segments. A prompt where every moment moves "
                "at the same pace is a structural failure, not a style choice. Serve the "
                "brief's 'Felt intent:' line — every camera, timing and performance choice "
                "exists to make that one feeling land."),
        "THE APPROVED BRIEF — what was already decided:\n" + compiled_brief +
        "\n\nSHOT, VOICE DIRECTION AND ORDERED ATTACHMENTS:\n" + _j(context) +
        "\n\nReturn the exact Seedance reference-to-video prompt. Keep all spoken words out "
        "of providerPrompt; refer to the approved track only as @Audio1. Then one plain "
        "sentence on whether this animation will land the beat.",
        AnimationDirection, label="department_animation", log=log, images=images)


def review_media(artifact_type, context, images, *, log=print):
    if artifact_type not in ("keyframe", "animation", "final"):
        raise ValueError("artifact_type must be keyframe|animation|final")
    return cb_llm.structured(
        _system("post" if artifact_type == "final" else "review",
                "Run dailies review on visible evidence. Findings are advice for Julian, "
                "never an automatic approval, rewrite or generation instruction."),
        "REVIEW TARGET AND APPROVED INTENT:\n" + _j({**context, "artifactType": artifact_type}) +
        "\n\nUse orderedReviewImages in the context to distinguish the actual rendered "
        "evidence (chronological where there are several frames) from its identity and "
        "Scene Look references.",
        MediaReview, label=f"department_review_{artifact_type}", log=log, images=images)
