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


class CharacterFramePlacement(BaseModel):
    character: str = Field(min_length=1)
    centerX: float = Field(ge=0.08, le=0.92)
    centerY: float = Field(ge=0.08, le=0.92)
    apparentScale: float = Field(default=1.0, ge=0.55, le=1.8)
    depthPlane: int = Field(default=0, ge=-2, le=2)
    bodyAngleDegrees: float = Field(default=0.0, ge=-80.0, le=80.0)
    facing: str = Field(min_length=1)
    pose: str = Field(min_length=1)


class OpeningFrameLayout(BaseModel):
    """Machine-readable staging envelope for the literal opening frame.

    Physical character height comes from canon. The DP chooses the reference subject's
    approximate frame coverage, starting zone, depth and apparent perspective scale. This
    is local advisory evidence, never a provider pose template or animation choreography.
    """
    aspectRatio: Literal["16:9"] = "16:9"
    referenceCharacter: str = Field(min_length=1)
    referenceHeightFraction: float = Field(ge=0.18, le=0.55)
    sameDepth: bool
    placements: List[CharacterFramePlacement] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_layout(self):
        names = [item.character for item in self.placements]
        if len(names) != len(set(names)):
            raise ValueError("opening-frame layout contains a duplicate character")
        if self.referenceCharacter not in names:
            raise ValueError("referenceCharacter must be present in placements")
        if self.sameDepth:
            planes = {item.depthPlane for item in self.placements}
            if len(planes) != 1 or any(item.apparentScale != 1.0 for item in self.placements):
                raise ValueError(
                    "sameDepth layouts require one depth plane and apparentScale=1.0")
        return self


class CinematographyDirection(BaseModel):
    shotId: str
    audienceRead: str
    composition: str
    lensAndCameraRelationship: str
    lightingAndDepth: str
    openingFrameLayout: OpeningFrameLayout
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
    shotNumber: int = Field(ge=1, le=6)
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


class SeedanceStageDirection(BaseModel):
    stageNumber: int = Field(ge=1, le=5)
    beatIds: List[str] = Field(min_length=1)
    purpose: str = Field(min_length=1)
    startSec: Optional[float] = Field(
        default=None, ge=0,
        description="Start time when pacingMode is timestamp; omitted for storyline pacing.")
    endSec: Optional[float] = Field(
        default=None, gt=0,
        description="End time when pacingMode is timestamp; omitted for storyline pacing.")
    initialOrCarriedState: str = Field(
        min_length=1,
        description="The visible state inherited at the start of this stage.")
    primaryEvent: str = Field(
        min_length=1,
        description="One primary state change, written as playable cause and effect.")
    observableEndState: str = Field(
        min_length=1,
        description="The directly visible state that proves this stage completed.")
    emotionOrCameraAnalysis: str = Field(
        min_length=1,
        description="Why the observable action lands emotionally, comedically or through camera scheduling.")


class AnimationDirection(BaseModel):
    shotId: str
    durationSec: int = Field(
        ge=4, le=30,
        description="The exact approved story duration for this production unit.")
    taskMode: Literal[
        "text-to-video", "reference-to-video", "thirty-second-video",
        "ultra-long-video", "video-edit", "extend-forward", "extend-backward",
        "transition", "first-last-frame", "storyboard-grid", "blockout-render",
    ] = "reference-to-video"
    pacingMode: Literal["storyline", "timestamp"] = "storyline"
    generationGoal: str = Field(
        min_length=1,
        description="A one-sentence statement of the video and central story event.")
    deliveryPlan: str = Field(
        min_length=1,
        description="A concise explanation of how the prompt is built to deliver the "
                    "director's intended audience turn.")
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
    shotPlan: List[InternalShotDirection] = Field(min_length=1, max_length=6)
    stagePlan: List[SeedanceStageDirection] = Field(min_length=1, max_length=5)
    referenceContract: List[ReferenceDirection] = Field(default_factory=list, max_length=50)
    consistencyContract: List[str] = Field(min_length=1, max_length=6)
    audioContract: str = Field(
        min_length=1,
        description="The speaker, language, track authority and silence relationships. "
                    "Use 'No dialogue' when the shot has no spoken line.")
    continuityFinish: str
    surgicalSafeguards: List[str] = Field(default_factory=list, max_length=3)
    editScope: str = ""
    contentToPreserve: List[str] = Field(default_factory=list, max_length=8)
    extensionDirection: Literal["forward", "backward"] = "forward"
    transitionTrigger: str = ""
    transitionTransformation: str = ""
    transitionArrivalState: str = ""
    audioTransition: str = ""
    firstFrameTag: str = "@Image 1"
    lastFrameTag: str = "@Image 2"
    storyboardTag: str = "@Image 1"
    storyboardReadingOrder: str = "left to right, top to bottom"
    blockoutKind: Literal["coarse", "fine"] = "coarse"
    blockoutMappings: List[str] = Field(default_factory=list, max_length=20)
    providerPrompt: str = Field(min_length=40)

    @model_validator(mode="after")
    def precision_must_be_earned(self):
        if self.directionDensity == "precise" and not self.precisionReasons:
            raise ValueError("precise direction requires an explicit continuity, dialogue, "
                             "safety or essential-story reason")
        numbers = [stage.stageNumber for stage in self.stagePlan]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError("Seedance stages must be consecutive and begin at 1")
        timed = [(stage.startSec, stage.endSec) for stage in self.stagePlan]
        shot_numbers = [shot.shotNumber for shot in self.shotPlan]
        if shot_numbers != list(range(1, len(shot_numbers) + 1)):
            raise ValueError("internal shots must be consecutive and begin at 1")
        if self.durationSec > 15 and self.pacingMode != "timestamp":
            raise ValueError("production units over 15 seconds require timestamp pacing")
        if self.pacingMode == "timestamp":
            if any(start is None or end is None for start, end in timed):
                raise ValueError("timestamp pacing requires startSec and endSec for every stage")
            if any(start >= end for start, end in timed):
                raise ValueError("every timestamp stage must end after it begins")
            if abs(timed[0][0]) > 0.001:
                raise ValueError("timestamp stages must begin at 0 seconds")
            if any(abs(timed[index][0] - timed[index - 1][1]) > 0.001
                   for index in range(1, len(timed))):
                raise ValueError("timestamp stages must be consecutive without gaps or overlaps")
            if abs(timed[-1][1] - self.durationSec) > 0.001:
                raise ValueError("timestamp stages must end at the approved duration")
        elif any(start is not None or end is not None for start, end in timed):
            raise ValueError("storyline pacing must omit startSec and endSec")
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


class PoseConformanceDimension(BaseModel):
    """One visible, objective check on an isolated acting-pose candidate."""
    score: int = Field(ge=0, le=2)
    visibleEvidence: str = Field(min_length=1)
    correction: str = ""


class PoseConformanceReview(BaseModel):
    """Machine qualification for a reusable pose plate, never a human approval."""
    verdict: Literal["pass", "revise", "block"]
    character: str = Field(min_length=1)
    subjectCount: int = Field(ge=0, le=8)
    summary: str = Field(min_length=1)
    identityAndProportions: PoseConformanceDimension
    requestedPoseAndPerformance: PoseConformanceDimension
    anatomyAndSilhouette: PoseConformanceDimension
    isolationAndFraming: PoseConformanceDimension
    forbiddenContent: PoseConformanceDimension
    recommendedCorrection: str = ""

    @model_validator(mode="after")
    def pass_requires_objective_evidence(self):
        dimensions = (
            self.identityAndProportions,
            self.requestedPoseAndPerformance,
            self.anatomyAndSilhouette,
            self.isolationAndFraming,
            self.forbiddenContent,
        )
        if self.verdict == "pass" and (
                self.subjectCount != 1 or any(item.score != 2 for item in dimensions)):
            raise ValueError(
                "a passing pose must contain exactly one subject and score 2 on every "
                "objective dimension")
        if self.verdict != "pass" and not self.recommendedCorrection.strip():
            raise ValueError("a failed pose review must provide one corrective instruction")
        return self


class KeyframeConformanceDimension(BaseModel):
    """One objective, visible opening-frame requirement."""
    score: int = Field(ge=0, le=2)
    visibleEvidence: str = Field(min_length=1)
    correction: str = ""


class KeyframeConformanceReview(BaseModel):
    """Fail-closed qualification before a keyframe is exposed for human approval."""
    verdict: Literal["pass", "revise", "block"]
    expectedCharacters: List[str] = Field(min_length=1, max_length=8)
    detectedCharacters: List[str] = Field(default_factory=list, max_length=8)
    expectedSubjectCount: int = Field(ge=1, le=8)
    subjectCount: int = Field(ge=0, le=12)
    summary: str = Field(min_length=1)
    identityAndDistinguishability: KeyframeConformanceDimension
    relativeScaleAndGeography: KeyframeConformanceDimension
    anatomyAndSilhouette: KeyframeConformanceDimension
    actionReadyComposition: KeyframeConformanceDimension
    forbiddenContent: KeyframeConformanceDimension
    recommendedCorrection: str = ""

    @model_validator(mode="after")
    def pass_requires_every_objective_contract(self):
        dimensions = (
            self.identityAndDistinguishability,
            self.relativeScaleAndGeography,
            self.anatomyAndSilhouette,
            self.actionReadyComposition,
            self.forbiddenContent,
        )
        expected = sorted(name.casefold() for name in self.expectedCharacters)
        detected = sorted(name.casefold() for name in self.detectedCharacters)
        if self.verdict == "pass" and (
                self.subjectCount != self.expectedSubjectCount or
                expected != detected or any(item.score != 2 for item in dimensions)):
            raise ValueError(
                "a passing keyframe must contain the exact cast and score 2 on every "
                "objective dimension")
        if self.verdict != "pass" and not self.recommendedCorrection.strip():
            raise ValueError("a failed keyframe review must provide one corrective instruction")
        return self


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
                "Own this shot's performance-ready opening stage. Establish the world, "
                "camera, light, cast identity, canon relative scale, loose starting "
                "relationship and clear action space. Do not pre-perform or freeze the "
                "acting that belongs to Animation. The attached images are in the exact "
                "labelled provider-reference order in the context.") + "\n\n" +
                load_runtime_skill("dp"),
        "APPROVED SHOT CONTRACT AND ORDERED IMAGE LABELS:\n" + _j(context) +
        "\n\nReturn one keyframe-provider direction and one machine-readable "
        "openingFrameLayout staging envelope. Include every charactersInFrame entry exactly "
        "once. Normalized centres indicate loose starting zones, not pixel locks. Facing and "
        "pose describe only a playable frame-one anticipation state; do not prescribe exact "
        "limb, wing, facial or later action choreography. Canonical physical height is "
        "applied from the character registry: choose the reference character's approximate "
        "frame-height fraction and use apparentScale solely for an authored depth difference. "
        "Set sameDepth=true, one depthPlane and apparentScale=1.0 when perspective must not "
        "alter relative size. Keep every character readable inside the 16:9 frame with lead "
        "room and an unobstructed performance corridor. The final image call receives the "
        "locked turnarounds and Scene Look in providerReferencePlan order. Never assign an "
        "opening composition, sizing board or generated pose plate to an @图 label: those "
        "remain local advisory evidence. Bind references by the labels stated in context; "
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
    shot = context.get("shot") or {}
    raw_duration = shot.get("durationSec", shot.get("targetDurationSecApproved"))
    try:
        duration = int(raw_duration)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Animation Director requires an approved integer duration") from exc
    if float(raw_duration) != duration or not 4 <= duration <= 30:
        raise RuntimeError(
            f"Animation Director requires an approved 4-30s integer duration; got {raw_duration!r}")

    result = cb_llm.structured(
        _system("animation",
                "Turn the approved dramatic beat into one playable Seedance generation unit. "
                "The first attached image is the approved opening frame; remaining attachments "
                "follow the exact reference order in the context. Use one to six internal "
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
        f"The approved production-unit duration is exactly {duration} seconds. Preserve it; "
        "never pad toward 30 seconds or compress the approved story timing. Preserve the "
        "storyboardStagePlanApproved and storyboardInternalShotPlanApproved from the shot when "
        "present: do not add, drop, merge or reorder their stages, beat ownership or motivated "
        "camera views. Add executable timing and detail without changing their story.\n\n"
        "Return taskMode='reference-to-video', the exact durationSec, pacingMode, generationGoal, deliveryPlan, audienceBefore, "
        "audienceAfter, beatOwner, performanceFreedom, landingBreath, directionDensity, a "
        "numbered one-to-six-shot directing plan, a consecutive stagePlan in which every "
        "stage keeps its approved beatIds, has one primary event, an emotionOrCameraAnalysis "
        "and an observable end state, "
        "the separate reference "
        "contract, consistencyContract, audioContract, the exact continuity landing, no more "
        "than three surgical safeguards, and one paste-ready Seedance shooting script in "
        "providerPrompt. Use pacingMode='storyline' for units up to 15 seconds and "
        "pacingMode='timestamp' for 16-30 seconds; timestamp mode requires ordered startSec "
        "and endSec values on every stage, while storyline mode omits both. "
        "Keep every spoken word out of providerPrompt; refer to the approved track only as "
        "@Audio1. Use the exact attached asset tags and bind each one separately in the prompt "
        "to what it defines and what it must not contribute. For dialogue shots, preserve the "
        "house audio-lock header as line one. Adapt the official ByteDance Seedance 2.5 "
        "structure as: [Multimodal Reference Layer], [One-Sentence Summary], [Global Settings], "
        "[Timestamp Script Storyboard], consecutive Stage N headings, [Global Supplement], "
        "then [Audio]. In [Global Settings], cover environment and texture, visual style, "
        "camera language, character styling, performance core and only necessary prohibited "
        "items. Each stage must contain Initial state or Continue from the previous stage, "
        "Action/Expression, Emotion/Camera Analysis, and End state. In timestamp mode write the "
        "heading as 'Stage N: 0-4s [Purpose]'; in storyline mode write 'Stage N: [Purpose]'. "
        "Keep duration, aspect ratio, resolution and model "
        "selection out of providerPrompt because the API contract owns them. Prefer stages to "
        "one-second micromanagement; use exact time points only for a critical handoff or "
        "dialogue cue. Explicitly prohibit extra dialogue, subtitles and default BGM. The prompt "
        "must begin from the approved opening state and end on a usable handoff, with causal "
        "physical action, observable performance, motivated camera, readable composition, and "
        "established light/material behaviour. It should feel like confident direction to an "
        "exceptional actor and camera crew, not an animation checklist.",
        AnimationDirection, label="department_animation", log=log, images=images)

    if result.durationSec != duration:
        raise RuntimeError(
            f"Animation Director changed approved duration from {duration}s to "
            f"{result.durationSec}s")
    approved_stages = shot.get("storyboardStagePlanApproved") or []
    if approved_stages:
        expected = [list(stage.get("beatIds") or []) for stage in approved_stages]
        actual = [list(stage.beatIds) for stage in result.stagePlan]
        if actual != expected:
            raise RuntimeError(
                "Animation Director added, dropped, merged, reordered or reassigned approved "
                f"story stages: expected {expected}, got {actual}")
    approved_shots = shot.get("storyboardInternalShotPlanApproved") or []
    if approved_shots and len(result.shotPlan) != len(approved_shots):
        raise RuntimeError(
            "Animation Director changed the approved number of motivated internal shots")
    return result


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


def review_pose_conformance(context, images, *, log=print):
    """Compare one pose candidate with its locked identity source.

    Image order is contractual: the candidate is first and the identity turnaround is
    second. This worker qualifies an internal production input; it cannot approve media,
    regenerate anything or silently relax a failed dimension.
    """
    if len(images) != 2:
        raise ValueError("pose conformance requires candidate and identity images")
    return cb_llm.structured_with_repair(
        _system(
            "review",
            "Run an objective production check on one isolated character acting pose. "
            "Image 1 is the ACTUAL POSE CANDIDATE. Image 2 is the LOCKED IDENTITY "
            "TURNAROUND and is the sole authority for face, silhouette, body proportions, "
            "limbs, wings, antennae, glasses and approved design. Judge only visible "
            "evidence. Score each dimension 2 only when it clearly passes, 1 when "
            "ambiguous or materially weak, and 0 when wrong. A pass requires exactly one "
            "character, every dimension at 2, the requested pose visibly readable, the "
            "complete silhouette uncropped, usable isolation, sound anatomy, and none of "
            "the forbidden content. When it does not pass, return one concise, prompt-ready "
            "correction that changes only the failed features and preserves what worked. "
            "This is machine qualification, never human approval."),
        "POSE CONTRACT AND ORDERED IMAGE ROLES:\n" + _j(context) +
        "\n\nInspect Image 1 against Image 2. Do not infer missing details and do not "
        "reward polish when identity, proportions, anatomy, acting or forbidden-content "
        "requirements fail.",
        PoseConformanceReview,
        model=cb_llm.VALIDATOR_MODEL,
        label="department_pose_conformance",
        log=log,
        images=images,
    )


def review_keyframe_conformance(context, images, *, log=print):
    """Compare a rendered opener with its exact identity, world and staging contracts.

    Image order is contractual and described in ``context['orderedImages']``.  This is a
    narrow production safety check, not a taste score and never a creative approval.
    """
    if len(images) < 2:
        raise ValueError("keyframe conformance requires a candidate and its references")
    return cb_llm.structured_with_repair(
        _system(
            "review",
            "Run an objective pre-approval check on one rendered opening keyframe. Image 1 "
            "is the ACTUAL KEYFRAME CANDIDATE. The remaining images are the locked identity "
            "views and Scene Look listed in orderedImages. Each identity image contains one "
            "canonical character and is authoritative for that character only. Judge visible "
            "evidence, not polish or personal taste. A pass requires exactly the expected cast; "
            "each named character visibly matching its own reference without blending, swapping "
            "or borrowed features; canonical relative size and authored screen geography; sound "
            "anatomy and readable silhouettes; a loose performance-ready opening composition; "
            "and no forbidden props, duplicate subjects, text, logo or watermark. Score 2 only "
            "when the requirement clearly passes, 1 when ambiguous or materially weak, and 0 "
            "when wrong. Any non-2 dimension makes the verdict revise or block. Return one concise "
            "prompt-ready correction that changes only failed features and preserves what worked. "
            "This qualification can block Accept but can never approve creative quality."),
        "KEYFRAME CONTRACT AND ORDERED IMAGE ROLES:\n" + _j(context) +
        "\n\nInspect Image 1 against every named reference. Do not infer hidden detail, "
        "do not confuse two reference views with extra cast, and do not reward cinematic "
        "finish when identity, scale, anatomy, geography or forbidden-content checks fail.",
        KeyframeConformanceReview,
        model=cb_llm.VALIDATOR_MODEL,
        label="department_keyframe_conformance",
        log=log,
        images=images,
    )
