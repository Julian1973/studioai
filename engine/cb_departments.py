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

from pydantic import BaseModel, Field, model_validator

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
    "animation": ROOT / "skills/seedance-production-director/SKILL.md",
    "review": ROOT / "skills/crystal-bears-continuity/SKILL.md",
    "post": ROOT / "skills/crystal-bears-post/SKILL.md",
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
     "worker": "Seedance Production Director",
     "influences": "feature-animation direction · cinematography · editorial rhythm",
     "skill": "seedance-production-director", "output": "exact cinematic Seedance shooting script"},
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


class LookDirection(BaseModel):
    creativeIntent: str
    storyOfPlace: str
    paletteAndLighting: str
    materialsAndAtmosphere: str
    continuityRules: List[str] = Field(default_factory=list, max_length=5)
    providerPrompt: str = Field(min_length=40)


class CinematographyDirection(BaseModel):
    shotId: str
    audienceRead: str
    composition: str
    lensAndCameraRelationship: str
    lightingAndDepth: str
    referenceUse: List[str] = Field(default_factory=list, max_length=6)
    continuityProtections: List[str] = Field(default_factory=list, max_length=4)
    providerPrompt: str = Field(min_length=40)


class VoiceLineDirection(BaseModel):
    dialogueOccurrenceId: str = ""
    sourceEventId: str = ""
    speaker: str
    exactDialogue: str
    performedText: str
    dramaticIntention: str
    subtext: str
    cadenceAndBreath: str
    timingAndBody: str


class VoiceDirection(BaseModel):
    shotId: str
    sceneIntention: str
    lines: List[VoiceLineDirection]


class InternalShotDirection(BaseModel):
    shotNumber: int = Field(ge=1, le=3)
    purpose: str = Field(min_length=1)
    framingLensAndCamera: str = Field(min_length=1)
    causalAction: str = Field(min_length=1)
    observablePerformance: str = Field(min_length=1)
    compositionLightAndMaterials: str = Field(min_length=1)
    landingImage: str = Field(min_length=1)


class ReferenceDirection(BaseModel):
    assetTag: str = Field(min_length=1)
    role: Literal["opening_frame", "character_identity", "location", "prop",
                  "style", "audio", "video", "closing_frame"]
    controls: str = Field(min_length=1)
    scope: Literal["canon", "episode", "continuity"]


class AnimationDirection(BaseModel):
    shotId: str
    dramaticBeat: str
    audienceBefore: str = Field(min_length=1)
    audienceAfter: str = Field(min_length=1)
    beatOwner: str = Field(min_length=1)
    performanceFreedom: str = Field(
        min_length=1,
        description="The acting latitude deliberately left to Seedance: intention, cadence, "
                    "micro-reactions and secondary motion it may interpret rather than obey "
                    "as frame-by-frame choreography.")
    performanceArc: str
    physicalCauseAndEffect: str
    cameraBehaviour: str
    timingAndRhythm: str
    landingBreath: str = Field(
        min_length=1,
        description="How the payoff/reaction is allowed to register; descriptive rhythm, "
                    "not compulsory timestamps.")
    directionDensity: Literal["open", "guided", "precise"]
    precisionReasons: List[str] = Field(
        default_factory=list, max_length=4,
        description="Only the continuity, dialogue, safety or essential story facts that "
                    "justify precise control. Empty is valid for an open performance.")
    shotPlan: List[InternalShotDirection] = Field(min_length=1, max_length=3)
    referenceContract: List[ReferenceDirection] = Field(default_factory=list, max_length=9)
    continuityFinish: str
    surgicalSafeguards: List[str] = Field(default_factory=list, max_length=3)
    providerPrompt: str = Field(min_length=40)

    @model_validator(mode="after")
    def precision_must_be_earned(self):
        if self.directionDensity == "precise" and not self.precisionReasons:
            raise ValueError("precise direction requires an explicit continuity, dialogue, "
                             "safety or essential-story reason")
        return self


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
    beatLands: bool
    strongestEvidence: str
    weakestDimension: str


class EvaluationDimension(BaseModel):
    score: int = Field(ge=0, le=2)
    intended: str
    observed: str
    diagnosis: str
    confidence: Literal["low", "medium", "high"]


class CheapestNextAction(BaseModel):
    action: Literal["approve", "select-existing-candidate", "recover-in-edit",
                    "free-upstream-revision", "paid-rerender", "human-redesign"]
    rerenderRequired: bool
    reason: str
    changeOneLever: str
    preserveExactly: List[str] = Field(max_length=6)
    proofOfImprovement: str
    zeroCostChecksFirst: List[str] = Field(max_length=6)


class MediaReview(BaseModel):
    artifactType: Literal["keyframe", "animation", "final"]
    verdict: Literal["recommend-approve", "revise", "block"]
    summary: str
    intendedRead: str
    actualRead: str
    finalFrameUsable: bool = False
    recommendedCandidate: Optional[str] = None
    candidateAssessments: List[CandidateAssessment] = Field(default_factory=list)
    beatDelivery: EvaluationDimension
    actingAndPerformance: EvaluationDimension
    physicalCausality: EvaluationDimension
    timingAndReaction: EvaluationDimension
    cameraAndEdit: EvaluationDimension
    compositionAndContinuity: EvaluationDimension
    identityAndReferenceUse: EvaluationDimension
    finishAndProductionValue: EvaluationDimension
    likelyRootCause: Literal["prompt-direction", "opening-frame", "reference-binding",
                             "voice-timing", "action-overload", "camera-plan",
                             "continuity-input", "provider-variance", "post-only",
                             "no-material-failure"]
    rootCauseReasoning: str
    cheapestNextAction: CheapestNextAction
    learningTags: List[str] = Field(default_factory=list, max_length=8)
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


def prepare_story(script_events, cast_by_scene, canon_context, *, log=print):
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
        "SIGNED STORY CANON — these are the exact human-locked inputs for this run. "
        "Obey them; never fill a missing fact invisibly:\n"
        + json.dumps(canon_context, ensure_ascii=False, indent=1) +
        "\n\nSCRIPT EVENTS, IN ORDER — index : scene : type : [speaker :] text (dialogue text "
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
                "Own the scene-wide environment, palette, material, light and atmosphere. "
                "Do not compose a shot or place a character."),
        "APPROVED SCENE CONTEXT:\n" + _j(context) +
        "\n\nReturn the exact image-provider prompt for one environment-only Scene Look plate.",
        LookDirection, label="department_look", log=log)


def prepare_cinematography(context, images, *, log=print):
    return cb_llm.structured(
        _system("cinematography",
                "Own this shot's literal opening composition. The attached images are in "
                "the exact labelled reference order in the context.") + "\n\n" +
                load_runtime_skill("dp"),
        "APPROVED SHOT CONTRACT AND ORDERED IMAGE LABELS:\n" + _j(context) +
        "\n\nReturn one exact keyframe-provider prompt. Bind references by their labels; "
        "do not describe character identity from memory.",
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
        if locked.get("dialogueOccurrenceId"):
            if out.dialogueOccurrenceId != locked["dialogueOccurrenceId"]:
                raise RuntimeError(f"Voice Director changed occurrence ID on line {idx}")
            if out.sourceEventId != locked.get("sourceEventId"):
                raise RuntimeError(f"Voice Director changed source event ID on line {idx}")
        if out.speaker.strip().lower() != str(locked["speaker"]).strip().lower():
            raise RuntimeError(f"Voice Director changed speaker on line {idx}")
        if _spoken_words(out.exactDialogue) != _spoken_words(locked["exactText"]):
            raise RuntimeError(f"Voice Director changed locked dialogue on line {idx}")
        if _spoken_words(out.performedText) != _spoken_words(locked["exactText"]):
            raise RuntimeError(f"Voice Director added, dropped or changed words on line {idx}")
    return result


def prepare_voice(context, locked_lines, *, log=print):
    result = cb_llm.structured(
        _system("voice",
                "Direct the locked words as an ElevenLabs v3 performance reconciled with "
                "the approved body action. Never add an ad-lib or rewrite a word."),
        "APPROVED SHOT CONTEXT:\n" + _j(context) +
        "\n\nLOCKED LINES (same count/order/speaker/words must be returned):\n" + _j(locked_lines),
        VoiceDirection, label="department_voice", log=log)
    return validate_voice_direction(result, locked_lines)


def prepare_animation(context, images, *, log=print):
    return cb_llm.structured(
        _system("animation",
                "Turn the approved dramatic beat into one playable Seedance generation unit. "
                "The first attached image is the approved opening frame; remaining attachments "
                "follow the exact reference order in the context. Use one to three internal "
                "shots only when each edit has a real story, performance or reaction purpose."),
        "APPROVED SHOT, VOICE DIRECTION AND ORDERED ATTACHMENTS:\n" + _j(context) +
        "\n\nDIRECTORIAL FREEDOM CONTRACT:\n"
        "Lock only story truth, exact audio, canon, reference roles, opening state and the "
        "required landing. Direct intention, relationship, playable cause-and-effect and "
        "rhythmic contrast; leave Seedance genuine latitude to discover acting cadence, "
        "micro-reactions, overlap, recovery, secondary motion and organic camera response. "
        "Do not prescribe every blink, gesture, pose, camera coordinate or timestamp. Use "
        "directionDensity='open' by default, 'guided' when the beat needs clearer staging, "
        "and 'precise' only for a named continuity, dialogue, safety or essential story "
        "reason recorded in precisionReasons. A surprising interpretation is welcome when "
        "it preserves truth and makes the intended audience turn land more strongly.\n\n"
        "Return audienceBefore, audienceAfter, beatOwner, performanceFreedom, landingBreath, "
        "directionDensity, a numbered one-to-three-shot directing plan, the "
        "separate reference contract, the exact continuity landing, no more than three "
        "surgical safeguards, and one paste-ready Seedance shooting script in providerPrompt. "
        "Keep every spoken word out of providerPrompt; refer to the approved track only as "
        "@Audio1. The prompt must begin from the approved opening state and end on a usable "
        "handoff, with causal physical action, observable performance, motivated camera, "
        "readable composition, and established light/material behaviour. The prompt should "
        "feel like confident direction to an exceptional actor and camera crew, not an "
        "animation checklist.",
        AnimationDirection, label="department_animation", log=log, images=images)


def review_media(artifact_type, context, images, *, log=print):
    if artifact_type not in ("keyframe", "animation", "final"):
        raise ValueError("artifact_type must be keyframe|animation|final")
    return cb_llm.structured(
        _system("post" if artifact_type == "final" else "review",
                "Run dailies review on visible evidence. Findings are advice for Julian, "
                "never an automatic approval, rewrite or generation instruction. Judge "
                "whether the intended dramatic or comic beat is actually felt, then acting, "
                "physical causality, timing/reaction, motivated camera/edit, continuity, "
                "reference fidelity and finish. Separate visible evidence from inference. "
                "Diagnose the most likely root cause and confidence. Recommend the cheapest "
                "next action: prefer an existing candidate, edit recovery or a free upstream "
                "revision before a paid rerender. If a rerender is genuinely needed, change "
                "one lever only, state what must be preserved exactly, and define observable "
                "proof that the change worked. Do not convert one probable provider variation "
                "into a permanent creative rule."),
        "REVIEW TARGET AND APPROVED INTENT:\n" + _j({**context, "artifactType": artifact_type}) +
        "\n\nUse orderedReviewImages in the context to distinguish the actual rendered "
        "evidence (chronological where there are several frames) from its identity and "
        "Scene Look references.",
        MediaReview, label=f"department_review_{artifact_type}", log=log, images=images)
