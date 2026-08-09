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
import cb_emission_conformance as emission

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

RUNTIME_START = "<!-- RUNTIME_WORKER_START -->"
RUNTIME_END = "<!-- RUNTIME_WORKER_END -->"
MAX_ANIMATION_PROVIDER_PROMPT_WORDS = 700
DIRECTOR_GRAMMAR_PACK = HERE / "grammar_pack.json"


def director_grammar_pack():
    """Load versioned Director law as data; never let a worker improvise it."""
    return json.loads(DIRECTOR_GRAMMAR_PACK.read_text(encoding="utf-8"))


def canonical_style_paragraph():
    style = director_grammar_pack().get("style_paragraph") or {}
    version = str(style.get("version") or "").strip()
    text = str(style.get("text") or "").strip()
    if not version or not text:
        raise RuntimeError("Director grammar pack has no versioned canonical style paragraph")
    return version, text


_PROMPT_SECTION_RE = re.compile(
    r"(?ms)^\[([^\]\n]+)\]\s*\n(.*?)(?=^\[[^\]\n]+\]\s*$|\Z)")


def prompt_sections(prompt):
    """Return named prompt sections and reject headers that have no body."""
    sections = {}
    for name, body in _PROMPT_SECTION_RE.findall(str(prompt or "")):
        clean_name = name.strip()
        clean_body = body.strip()
        if not clean_body:
            raise ValueError(f"prompt section [{clean_name}] has no body")
        if clean_name in sections:
            raise ValueError(f"prompt section [{clean_name}] is duplicated")
        sections[clean_name] = clean_body
    return sections


def animation_provider_prompt_word_limit(duration_sec):
    """Leave room for compiler-owned style, geography, causality and numeric holds."""
    return 620 if float(duration_sec or 0) <= 15 else MAX_ANIMATION_PROVIDER_PROMPT_WORDS

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
    geography: List[str] = Field(
        min_length=1, max_length=8,
        description="Shot geography statements consumed verbatim by image and video compilers.")
    charactersInFrame: List[str] = Field(
        default_factory=list,
        description="Mechanically injected exact approved cast; never authored separately.")
    canonicalStyleVersion: str = ""
    canonicalStyleParagraph: str = ""
    openingFrameLayout: OpeningFrameLayout
    negativeSpace: List[str] = Field(
        min_length=1, max_length=4,
        description="Visible empty-space reservations for later entrances, travel or reveals.")
    referenceUse: List[str] = Field(default_factory=list, max_length=6)
    continuityProtections: List[str] = Field(default_factory=list, max_length=4)
    providerPrompt: str = Field(min_length=40)


class VoiceLineDirection(BaseModel):
    dialogueOccurrenceId: str = ""
    sourceEventId: str = ""
    speaker: str
    character: str = Field(min_length=1)
    exactDialogue: str
    performedText: str
    dramaticIntention: str
    subtext: str
    cadenceAndBreath: str
    timingAndBody: str
    archetypeId: str = Field(min_length=1)
    performanceQuestions: "VoicePerformanceQuestions"
    physicalState: str = Field(min_length=1)
    emotionalState: "VoiceEmotionalState"
    listener: str = Field(min_length=1)
    bodyVoiceRelationship: str = Field(min_length=1)
    previousText: str = Field(min_length=1)
    startsAtSec: float = Field(gt=0)
    estimatedDurationSec: float = Field(gt=0, le=15)
    pauseReasons: List[str] = Field(default_factory=list, max_length=6)
    tagPurposes: dict[str, str]
    takeRecipes: List["VoiceTakeRecipe"] = Field(min_length=1, max_length=3)


class VoicePerformanceQuestions(BaseModel):
    intention: str = Field(min_length=1)
    subtext: str = Field(min_length=1)
    thoughtBefore: str = Field(min_length=1)
    changeDuring: str = Field(min_length=1)
    operativeWords: List[str] = Field(min_length=1, max_length=6)


class VoiceEmotionalState(BaseModel):
    entry: str = Field(min_length=1)
    exit: str = Field(min_length=1)


class VoiceTakeRecipe(BaseModel):
    recipeId: str = Field(min_length=1)
    label: str = Field(min_length=1)
    performedText: str = Field(min_length=1)
    primary: bool = False
    takesCount: int = Field(default=1, ge=1, le=5)


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
    cause: str = Field(
        min_length=1,
        description="The visible cause inherited from the preceding state or stage.")
    primaryEvent: str = Field(
        min_length=1,
        description="One primary state change, written as playable cause and effect.")
    observableEndState: str = Field(
        min_length=1,
        description="The directly visible state that proves this stage completed.")
    emotionOrCameraAnalysis: str = Field(
        min_length=1,
        description="Why the observable action lands emotionally, comedically or through camera scheduling.")


class DirectorInterpretationDirection(BaseModel):
    """The creative reason for the unit, before provider choreography begins."""
    jokeOrAche: str = Field(min_length=1)
    mechanism: str = Field(min_length=1)
    statusBefore: str = Field(min_length=1)
    statusAfter: str = Field(min_length=1)
    audienceProgression: List[str] = Field(min_length=3, max_length=3)
    emotionalHeart: str = Field(min_length=1)


class GagClockDirection(BaseModel):
    """One complete comic arc plus the exact visual sentence compiled for Seedance."""
    beatCode: str = Field(min_length=1)
    mode: Literal["SMALL", "BIG"]
    setup: str = Field(min_length=1)
    anticipation: str = Field(min_length=1)
    impact: str = Field(min_length=1)
    reaction: str = Field(min_length=1)
    recoveryHold: str = Field(min_length=1)
    recoveryHoldSec: float = Field(
        gt=0, le=3.0,
        description="Numeric landing hold. BIG arcs and any arc that ends the unit need "
                    ">= 2.0s for the pose to read; SMALL mid-chain arcs may run 0.6-1.5s.")
    button: str = Field(min_length=1)
    providerAction: str = Field(
        min_length=1,
        description="A dialogue-free, directly photographable action sentence copied "
                    "verbatim into providerPrompt.")

    @model_validator(mode="after")
    def big_buttons_must_land(self):
        if self.mode == "BIG" and self.recoveryHoldSec < 2.0:
            raise ValueError(
                "BIG gag hold < 2.0s truncates the landing — the button cannot read "
                "('briefly' is not a duration; AAA Prompt Standard gag-clock law)")
        return self


class MotionVocabularyDirection(BaseModel):
    """Versioned canon verbs. These are injected from grammar_pack.json."""
    character: str = Field(min_length=1)
    belongs: List[str] = Field(default_factory=list, max_length=20)
    banned: List[str] = Field(default_factory=list, max_length=20)


def canonical_motion_vocabulary():
    characters = director_grammar_pack().get("characters") or {}
    return [
        MotionVocabularyDirection(
            character=name,
            belongs=list((rules or {}).get("belongs") or []),
            banned=list((rules or {}).get("banned") or []))
        for name, rules in characters.items()
        if (rules or {}).get("belongs") or (rules or {}).get("banned")
    ]


class GenerationDesignDirection(BaseModel):
    """The approved packaging decision, made before the provider receives a prompt."""
    packagingDecision: Literal["single-unit", "continuation-unit"]
    completeGagArcCount: int = Field(ge=0, le=8)
    densityJudgement: str = Field(min_length=1)
    splitOrNonSplitRationale: str = Field(min_length=1)
    handoffState: str = Field(min_length=1)


class CreativeTranslationDirection(BaseModel):
    interpretation: DirectorInterpretationDirection
    gagClocks: List[GagClockDirection] = Field(default_factory=list, max_length=8)
    generationDesign: GenerationDesignDirection

    @model_validator(mode="after")
    def gag_count_matches_design(self):
        if self.generationDesign.completeGagArcCount != len(self.gagClocks):
            raise ValueError("generationDesign.completeGagArcCount must match gagClocks")
        return self


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
    creativeTranslation: CreativeTranslationDirection
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
    geography: List[str] = Field(
        min_length=1, max_length=8,
        description="Scene geography ledger copied verbatim into every shot in the scene.")
    motionVocabulary: List[MotionVocabularyDirection] = Field(
        default_factory=canonical_motion_vocabulary,
        description="Canonical belongs/banned motion verbs injected from versioned data.")
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

    @model_validator(mode="before")
    @classmethod
    def inject_versioned_motion_vocabulary(cls, value):
        """Keep versioned grammar under compiler control, not model control."""
        if isinstance(value, dict):
            value = dict(value)
            value["motionVocabulary"] = [
                item.model_dump() for item in canonical_motion_vocabulary()
            ]
        return value

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
        canonical_vocab = {
            item.character: item.model_dump() for item in canonical_motion_vocabulary()
        }
        supplied_vocab = {}
        for item in self.motionVocabulary:
            value = item.model_dump() if hasattr(item, "model_dump") else dict(item)
            supplied_vocab[str(value.get("character") or "")] = value
        if supplied_vocab != canonical_vocab:
            raise ValueError("motionVocabulary must match the versioned Director grammar pack")
        directed_text = "\n".join([
            *(stage.primaryEvent for stage in self.stagePlan),
            *(clock.providerAction for clock in self.creativeTranslation.gagClocks),
        ])
        for character, rules in canonical_vocab.items():
            for verb in rules.get("banned") or []:
                pattern = rf"\b{re.escape(character)}\b[^.\n]{{0,100}}\b{re.escape(verb)}\b"
                if re.search(pattern, directed_text, re.I):
                    raise ValueError(
                        f"motion vocabulary violation: {character} cannot '{verb}'")
        prompt_words = len(self.providerPrompt.split())
        prompt_limit = animation_provider_prompt_word_limit(self.durationSec)
        if prompt_words > prompt_limit:
            raise ValueError(
                f"providerPrompt is {prompt_words} words; the production ceiling is "
                f"{prompt_limit}")
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
    result = cb_llm.structured(
        _system("cinematography",
                "Own this shot's performance-ready opening stage. Establish the world, "
                "camera, light, cast identity, canon relative scale, loose starting "
                "relationship and clear action space. Do not pre-perform or freeze the "
                "acting that belongs to Animation. The attached images are in the exact "
                "labelled provider-reference order in the context.") + "\n\n" +
                load_runtime_skill("dp"),
        "APPROVED SHOT CONTRACT AND ORDERED IMAGE LABELS:\n" + _j(context) +
        "\n\nReturn one keyframe-provider direction and one machine-readable "
        "openingFrameLayout staging envelope. Return geography as one to eight concise, "
        "literal screen-direction, travel-axis and spatial-relation statements. It becomes "
        "the approved geography ledger used verbatim by both image and video compilers. "
        "Include every charactersInFrame entry exactly "
        "once. Normalized centres indicate loose starting zones, not pixel locks. Facing and "
        "pose describe only a playable frame-one anticipation state; do not prescribe exact "
        "limb, wing, facial or later action choreography. Canonical physical height is "
        "applied from the character registry: choose the reference character's approximate "
        "frame-height fraction and use apparentScale solely for an authored depth difference. "
        "Set sameDepth=true, one depthPlane and apparentScale=1.0 when perspective must not "
        "alter relative size. Keep every character readable inside the 16:9 frame with lead "
        "room and an unobstructed performance corridor. Return negativeSpace as one to four "
        "explicit empty-space reservations, such as 'Hold empty space frame-right for Zenny "
        "entering later'; never fill planned reveal space merely to balance the frame. The "
        "final image call receives the "
        "locked turnarounds and Scene Look in providerReferencePlan order. Never assign an "
        "opening composition, sizing board or generated pose plate to an @图 label: those "
        "remain local advisory evidence. Bind references by the labels stated in context; "
        "do not describe character identity from memory.",
        CinematographyDirection, label="department_cinematography", log=log,
        images=images)
    shot = context.get("shot") or {}
    expected_cast = list(dict.fromkeys(
        str(name).strip() for name in shot.get("charactersInFrame") or []
        if str(name).strip()))
    placed_cast = [item.character for item in result.openingFrameLayout.placements]
    if placed_cast != expected_cast:
        raise RuntimeError(
            "Cinematography changed or reordered charactersInFrame: "
            f"expected {expected_cast}, got {placed_cast}")
    style_version, style_text = canonical_style_paragraph()
    result.charactersInFrame = expected_cast
    result.canonicalStyleVersion = style_version
    result.canonicalStyleParagraph = style_text
    return result


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
        if out.character.strip().lower() != str(locked["speaker"]).strip().lower():
            raise RuntimeError(f"Voice Director changed character on line {idx}")
        if _spoken_words(out.exactDialogue) != _spoken_words(locked["exactText"]):
            raise RuntimeError(f"Voice Director changed locked dialogue on line {idx}")
        if _spoken_words(out.performedText) != _spoken_words(locked["exactText"]):
            raise RuntimeError(f"Voice Director added, dropped or changed words on line {idx}")
    return result


def _visual_event_without_dialogue(text):
    """Remove quoted speech while preserving the approved visible action order."""
    value = re.sub(r"“[^”]*”|\"[^\"]*\"", "", str(text or ""))
    value = re.sub(
        r"\b(?:says?|calls?|hums?|humming|asks?|answers?)\s*(?=,|;|\.|\bthen\b|\band\b|$)",
        "", value, flags=re.I)
    value = re.sub(r"\bwith\s*(?=,|;|\.|$)", "", value, flags=re.I)
    value = re.sub(r",\s*,", ",", value)
    value = re.sub(r"\s+([,.;:!?])", r"\1", value)
    value = re.sub(r",\s*(then|and)\b", r", \1", value, flags=re.I)
    value = re.sub(r"\s{2,}", " ", value).strip(" ,")
    return value


def animation_locked_visual_events(shot):
    """Return the provider-facing story facts inherited from the approved storyboard."""
    locked = []
    for stage in shot.get("storyboardStagePlanApproved") or []:
        locked.append({
            "stageNumber": stage.get("stageNumber"),
            "beatIds": list(stage.get("beatIds") or []),
            "primaryEvent": _visual_event_without_dialogue(stage.get("primaryEvent")),
            "observableEndState": str(stage.get("observableEndState") or "").strip(),
        })
    return locked


def animation_story_lock_report(shot, provider_prompt, stage_plan=None):
    """Prove that every approved visual event survives into the provider request."""
    locked = animation_locked_visual_events(shot)
    prompt = " ".join(str(provider_prompt or "").split()).casefold()
    actual_stages = list(stage_plan or [])
    errors = []
    for index, event in enumerate(locked):
        primary = event["primaryEvent"]
        ending = event["observableEndState"]
        if primary and " ".join(primary.split()).casefold() not in prompt:
            errors.append(
                f"stage {event['stageNumber']} approved visual event is absent from providerPrompt")
        if actual_stages:
            if index >= len(actual_stages):
                errors.append(f"stage {event['stageNumber']} is absent from stagePlan")
                continue
            actual = actual_stages[index]
            get = (lambda key: getattr(actual, key, "")) if not isinstance(actual, dict) else actual.get
            if str(get("primaryEvent") or "").strip() != primary:
                errors.append(f"stage {event['stageNumber']} primaryEvent changed")
            if str(get("observableEndState") or "").strip() != ending:
                errors.append(f"stage {event['stageNumber']} observableEndState changed")
    return {"ready": not errors, "errors": errors, "lockedVisualEvents": locked}


def creative_translation_report(shot, direction, provider_prompt=None):
    """Prove approved comedy and handoff truth survived the Animation Director.

    This complements the stage story lock. The stage lock protects what happens; this
    report protects why the gag works and the visible action sentence actually sent to the
    provider. It is deterministic and makes no provider call.
    """
    data = direction.model_dump() if hasattr(direction, "model_dump") else dict(direction or {})
    translation = data.get("creativeTranslation") or {}
    clocks = list(translation.get("gagClocks") or [])
    design = translation.get("generationDesign") or {}
    prompt = " ".join(str(provider_prompt or data.get("providerPrompt") or "").split()).casefold()
    approved = [
        item for item in (shot.get("comedyContractsApproved") or [])
        if item.get("mode") in {"SMALL", "BIG"}
    ]
    derived = False
    if approved and not clocks and data.get("deriveCreativeTranslationFromApproved") is True:
        event_by_beat = {}
        for event in animation_locked_visual_events(shot):
            for beat_id in event.get("beatIds") or []:
                event_by_beat[str(beat_id)] = str(event.get("primaryEvent") or "").strip()
        clocks = [{
            "beatCode": str(item.get("beatCode") or ""),
            "mode": item.get("mode"),
            "setup": item.get("setup"),
            "impact": item.get("disruption"),
            "recoveryHold": item.get("hold"),
            "recoveryHoldSec": item.get("recoveryHoldSec"),
            "button": item.get("button"),
            "providerAction": event_by_beat.get(str(item.get("beatCode") or ""), ""),
        } for item in approved]
        design = {
            "completeGagArcCount": len(clocks),
            "handoffState": str(
                shot.get("visualPayoff") or
                ((shot.get("storyboardStagePlanApproved") or [{}])[-1]
                 .get("observableEndState")) or "").strip(),
        }
        derived = True
    errors = []

    expected_codes = [str(item.get("beatCode") or "") for item in approved]
    actual_codes = [str(item.get("beatCode") or "") for item in clocks]
    if approved and actual_codes != expected_codes:
        errors.append(
            "gag clocks added, dropped or reordered approved comedy beats: "
            f"expected {expected_codes}, got {actual_codes}")

    for approved_clock, actual_clock in zip(approved, clocks):
        comparisons = (
            ("mode", "mode"),
            ("setup", "setup"),
            ("disruption", "impact"),
            ("hold", "recoveryHold"),
            ("button", "button"),
        )
        for approved_key, actual_key in comparisons:
            if str(actual_clock.get(actual_key) or "").strip() != str(
                    approved_clock.get(approved_key) or "").strip():
                errors.append(
                    f"{actual_clock.get('beatCode') or '?'} {actual_key} changed approved "
                    f"{approved_key}")
        provider_action = str(actual_clock.get("providerAction") or "").strip()
        if provider_action and " ".join(provider_action.split()).casefold() not in prompt:
            errors.append(
                f"{actual_clock.get('beatCode') or '?'} providerAction is absent from providerPrompt")
        normalized_action = " ".join(provider_action.split()).casefold()
        for line in shot.get("dialogueLines") or []:
            spoken = " ".join(str(line.get("exactText") or "").split()).casefold()
            if spoken and len(spoken.split()) >= 2 and spoken in normalized_action:
                errors.append(
                    f"{actual_clock.get('beatCode') or '?'} providerAction contains spoken words")
        hold_sec = actual_clock.get("recoveryHoldSec")
        if hold_sec is None:
            errors.append(
                f"{actual_clock.get('beatCode') or '?'} gag button has no numeric hold")
        else:
            hold_line = f"Hold: {float(hold_sec):.1f}s"
            if hold_line.casefold() not in prompt:
                errors.append(
                    f"{actual_clock.get('beatCode') or '?'} explicit Hold line is absent "
                    "from providerPrompt")

        physical_staging = approved_clock.get("physicalStaging") or {}
        contact_and_weight = str(physical_staging.get("contactAndWeight") or "").strip()
        if contact_and_weight and " ".join(contact_and_weight.split()).casefold() not in prompt:
            errors.append(
                f"{actual_clock.get('beatCode') or '?'} approved contact-and-weight staging "
                "is absent from providerPrompt")

    if int(design.get("completeGagArcCount") or 0) != len(clocks):
        errors.append("generation design gag count does not match its gag clocks")
    required_handoff = str(
        shot.get("visualPayoff") or
        ((shot.get("storyboardStagePlanApproved") or [{}])[-1].get("observableEndState"))
        or "").strip()
    if required_handoff and str(design.get("handoffState") or "").strip() != required_handoff:
        errors.append("generation design changed the approved handoff state")

    return {
        "ready": not errors,
        "errors": errors,
        "approvedGagBeatCodes": expected_codes,
        "compiledGagBeatCodes": actual_codes,
        "derivedFromApprovedContracts": derived,
    }


def prepare_voice(context, locked_lines, *, log=print):
    result = cb_llm.structured(
        _system("voice",
                "Direct the locked words as an ElevenLabs v3 performance reconciled with "
                "the approved body action. Never add an ad-lib or rewrite a word."),
        "APPROVED SHOT CONTEXT:\n" + _j(context) +
        "\n\nLOCKED LINES (same count/order/speaker/words must be returned):\n" + _j(locked_lines),
        VoiceDirection, label="department_voice", log=log)
    return validate_voice_direction(result, locked_lines)


def _apply_animation_provider_shell(prompt, shot, references=None):
    """Apply the non-creative house contract around generated Seedance direction."""
    text = str(prompt or "").strip()
    dialogue = list(shot.get("dialogueLines") or [])
    text = "\n".join(
        line for line in text.splitlines()
        if not line.strip().lower().startswith("audio-lock:")
    ).strip()

    for item in dialogue:
        exact = str(item.get("exactText") or "").strip()
        if exact:
            text = re.sub(
                re.escape(exact), "the assigned @Audio1 performance", text,
                flags=re.IGNORECASE)

    if dialogue:
        speakers = list(dict.fromkeys(
            str(item.get("speaker") or "").strip()
            for item in dialogue if str(item.get("speaker") or "").strip()))
        speaker_copy = " and ".join(speakers) or "Assigned speakers"
        speaker_verb = "performs" if len(speakers) == 1 else "perform"
        text = (
            "AUDIO-LOCK: @Audio1 is the sole source of English dialogue, speaker "
            "performance, mouth timing and silence. " + speaker_copy +
            " " + speaker_verb + " only assigned @Audio1 regions; all listeners remain silent and "
            "closed-mouth. Add no dialogue, vocalisations, narration, translated speech, "
            "subtitles or captions.\n\n" + text
        )

    reference_lines = []
    exclusions = {
        "opening_frame": "Do not use it to redesign identity, proportions, materials or later action.",
        "closing_frame": "Do not use it to redesign identity, materials or the preceding action.",
        "character_identity": "Do not use its background, pose, composition or unrelated scene content.",
        "location": "Do not use people, characters or foreground action from it.",
        "prop": "Do not use its background, people or composition.",
        "style": "Do not use its subject identity, text or composition.",
        "video": "Do not use its subject identity, clothing or scene unless explicitly assigned.",
    }
    for reference in references or []:
        item = reference.model_dump() if hasattr(reference, "model_dump") else dict(reference)
        tag = str(item.get("assetTag") or "").strip()
        role = str(item.get("role") or "").strip()
        controls = str(item.get("controls") or "").strip().rstrip(".")
        if not tag or not controls or role == "audio":
            continue
        reference_lines.append(
            f"{tag} defines only {controls}. {exclusions.get(role, 'Do not use unrelated background or content from it.')}")
    if reference_lines:
        reference_section = "[Multimodal Reference Layer]\n" + "\n".join(reference_lines)
        reference_pattern = re.compile(
            r"(?ims)^\s*\[Multimodal Reference Layer\]\s*.*?"
            r"(?=^\s*\[[^\]\n]+\]\s*$|\Z)")
        if reference_pattern.search(text):
            text = reference_pattern.sub(reference_section + "\n\n", text, count=1).strip()
        else:
            first_section = re.search(r"(?im)^\s*\[[^\]\n]+\]\s*$", text)
            if first_section:
                start = first_section.start()
                text = (text[:start].rstrip() + "\n\n" + reference_section + "\n\n" +
                        text[start:].lstrip())
            else:
                text = reference_section + "\n\n" + text

    consistency = (
        "[Global Supplement]\nMaintain identity, character count, prop ownership, "
        "camera axis, lighting continuity and sound relationships throughout. Keep each "
        "referenced character as one continuous instance; add no extra props or cast. "
        + ("@Audio1 remains the sole English dialogue authority."
           if dialogue else "Preserve the approved audio and ambience relationship.")
    )
    supplement_pattern = re.compile(
        r"(?ims)^\s*\[(?:Global Supplement|Overall Supplement|Maintain Consistency)\]"
        r"\s*.*?(?=^\s*\[[^\]\n]+\]\s*$|\Z)")
    if supplement_pattern.search(text):
        return supplement_pattern.sub(consistency + "\n\n", text, count=1).strip()

    audio_heading = re.search(r"(?im)^\s*\[Audio\]\s*$", text)
    if audio_heading:
        start = audio_heading.start()
        return (text[:start].rstrip() + "\n\n" + consistency + "\n\n" +
                text[start:].lstrip())
    return text.rstrip() + "\n\n" + consistency


def compile_animation_provider_prompt(shot, direction):
    """Compile the provider prompt from typed, approved Animation direction.

    The structured direction is the creative source of truth.  The prose returned in
    ``providerPrompt`` by the specialist is deliberately ignored here: allowing the model
    to describe the beat once in fields and then author it again as free prose was the
    golden-link failure.  This compiler emits each approved stage, gag action, reference
    role and handoff once, in the shape expected by the Seedance prompt preflight.
    """
    data = direction.model_dump() if hasattr(direction, "model_dump") else dict(direction or {})
    dialogue = list(shot.get("dialogueLines") or [])
    references = list(data.get("referenceContract") or [])
    stages = emission.time_tiles(
        list(data.get("stagePlan") or []),
        data.get("durationSec") or shot.get("durationSec"),
    )
    translation = data.get("creativeTranslation") or {}
    interpretation = translation.get("interpretation") or {}
    gag_actions = {
        str(item.get("beatCode") or ""): str(item.get("providerAction") or "").strip()
        for item in translation.get("gagClocks") or []
        if str(item.get("beatCode") or "").strip()
    }
    gag_clocks = {
        str(item.get("beatCode") or ""): item
        for item in translation.get("gagClocks") or []
        if str(item.get("beatCode") or "").strip()
    }

    def concise(value, *, words=28, context="render direction"):
        """Keep prose lean only at authored boundaries; never cut a sentence in half."""
        return emission.compact_complete_sentence(
            value, max_words=words, context=context)

    def consistency_clause(value):
        text = " ".join(str(value or "").split()).strip().rstrip(".")
        text = re.sub(r"^(?:use|keep|maintain|preserve|protect)\s+", "", text,
                      flags=re.I)
        return concise(text, words=22, context="render consistency").rstrip(".")

    sections = []
    if dialogue:
        speakers = list(dict.fromkeys(
            str(item.get("speaker") or "").strip()
            for item in dialogue if str(item.get("speaker") or "").strip()))
        owner = " and ".join(speakers) or "Assigned speakers"
        verb = "performs" if len(speakers) == 1 else "perform"
        sections.append(
            "AUDIO-LOCK: @Audio1 is the sole source of English dialogue, speaker "
            "performance, mouth timing and silence. " + owner + " " + verb +
            " assigned @Audio1 regions; listeners remain silent and closed-mouth. "
            "Add no dialogue, vocalisations, narration, translation, subtitles or captions.")

    exclusions = {
        "opening_frame": "Exclude redesign and later action.",
        "closing_frame": "Exclude identity redesign and preceding action.",
        "character_identity": "Exclude background, pose and composition.",
        "location": "Exclude characters and action.",
        "prop": "Exclude its background, people and composition.",
        "style": "Exclude its subject identity, text and composition.",
        "video": "Exclude identity, clothing and scene unless assigned.",
    }
    reference_lines = []
    for reference in references:
        item = reference.model_dump() if hasattr(reference, "model_dump") else dict(reference)
        tag = str(item.get("assetTag") or "").strip()
        role = str(item.get("role") or "").strip()
        controls = concise(item.get("controls"), words=15,
                           context=f"{tag or 'reference'} role").rstrip(".")
        if not tag or not controls:
            continue
        if role != "audio":
            reference_lines.append(
                f"{tag} defines {controls}. " + exclusions.get(
                    role, "Do not use unrelated background or content from it."))
    if reference_lines:
        sections.append("[Multimodal Reference Layer]\n" + "\n".join(reference_lines))

    goal = str(data.get("generationGoal") or data.get("dramaticBeat") or "").strip()
    sections.append("[One-Sentence Summary]\n" + goal)

    global_lines = []
    style_version, style_text = canonical_style_paragraph()
    global_lines.append(f"Style ({style_version}): {style_text}")
    geography = [str(item).strip() for item in data.get("geography") or [] if str(item).strip()]
    if geography:
        global_lines.append("Geography: " + " ".join(geography))
    mechanism = str(interpretation.get("mechanism") or "").strip()
    heart = str(interpretation.get("emotionalHeart") or "").strip()
    short_unit = float(data.get("durationSec") or shot.get("durationSec") or 0) <= 15
    global_values = [
        ("Comic or emotional mechanism", mechanism),
        ("Emotional heart", heart),
    ]
    if not short_unit:
        global_values.insert(1, (
            "Performance", concise(data.get("performanceArc"), words=28,
                                    context="performance arc")))
        global_values.insert(2, (
            "Physical causality", concise(data.get("physicalCauseAndEffect"), words=32,
                                           context="physical causality")))
    for label, value in global_values:
        if value:
            global_lines.append(f"{label}: {value}")
    sections.append("[Global Settings]\n" + "\n".join(global_lines))

    stage_sections = []
    emitted_holds = set()
    approved_physics = {
        str(item.get("beatCode") or ""): str(
            (item.get("physicalStaging") or {}).get("contactAndWeight") or "").strip()
        for item in shot.get("comedyContractsApproved") or []
        if str((item.get("physicalStaging") or {}).get("contactAndWeight") or "").strip()
    }
    approved_physics.update({
        str(item.get("beatCode") or ""): str(item.get("contactAndWeight") or "").strip()
        for item in shot.get("physicalStagings") or []
        if str(item.get("beatCode") or "").strip()
        and str(item.get("contactAndWeight") or "").strip()
    })
    audio_cues = emission.dialogue_cues(
        dialogue, duration_sec=data.get("durationSec") or shot.get("durationSec"))
    for index, stage in enumerate(stages):
        item = stage.model_dump() if hasattr(stage, "model_dump") else dict(stage)
        stage_number = int(item.get("stageNumber") or index + 1)
        beat_label = ", ".join(str(value) for value in item.get("beatIds") or [])
        purpose = beat_label or concise(item.get("purpose") or "Story event", words=9)
        start, end = item.get("startSec"), item.get("endSec")
        if start is not None and end is not None:
            heading = f"Stage {stage_number}: {start:g}-{end:g}s [{purpose}]"
        else:
            heading = f"Stage {stage_number}: [{purpose}]"
        prefix = "Initial state" if index == 0 else "Continue from the previous stage"
        event = str(item.get("primaryEvent") or "").strip()
        additions = []
        for beat_id in item.get("beatIds") or []:
            action = gag_actions.get(str(beat_id))
            if action and " ".join(action.split()).casefold() not in " ".join(event.split()).casefold():
                additions.append(action)
        action = " ".join([event, *additions]).strip()
        physics_lines = []
        for beat_id in item.get("beatIds") or []:
            physics = approved_physics.get(str(beat_id))
            if physics:
                physics_lines.append(f"Physics: {emission.require_complete_sentence(physics, context=f'{beat_id} physical staging')}")
        stage_audio = [cue for cue in audio_cues
                       if cue["startSec"] < float(end) and cue["endSec"] > float(start)]
        audio_line = "Audio cues: " + "; ".join(
            f"@Audio1 {emission.format_seconds(cue['startSec'])}-{emission.format_seconds(cue['endSec'])}s — {cue['speaker']}"
            for cue in stage_audio) + "." if stage_audio else "Audio cues: no dialogue in this stage."
        hold_lines = []
        for beat_id in item.get("beatIds") or []:
            clock = gag_clocks.get(str(beat_id))
            if not clock:
                continue
            hold_sec = clock.get("recoveryHoldSec")
            if hold_sec is None:
                raise ValueError(f"{beat_id} gag button has no numeric recoveryHoldSec")
            hold_lines.append(
                f"Hold: {float(hold_sec):.1f}s — "
                f"{str(clock.get('recoveryHold') or '').strip()}")
            emitted_holds.add(str(beat_id))
        lines = [
            heading,
            f"{prefix}: {concise(item.get('initialOrCarriedState'), words=28, context=f'Stage {stage_number} initial state')}",
            f"Cause: {emission.require_complete_sentence(item.get('cause'), context=f'Stage {stage_number} cause')}",
            f"Action/Expression: {action}",
            *physics_lines,
            *hold_lines,
            "Emotion/Camera Analysis: "
            + concise(item.get("emotionOrCameraAnalysis"), words=20,
                      context=f"Stage {stage_number} emotion/camera analysis"),
            audio_line,
            f"End state: {str(item.get('observableEndState') or '').strip()}",
        ]
        stage_sections.append("\n".join(lines))
    missing_holds = set(gag_clocks) - emitted_holds
    if missing_holds:
        raise ValueError(
            "gag button(s) are not owned by a compiled stage: "
            + ", ".join(sorted(missing_holds)))
    sections.append("[Timestamp Script Storyboard]\n" + "\n\n".join(stage_sections))

    consistency = [consistency_clause(item) for item in
                   data.get("consistencyContract") or [] if str(item).strip()]
    safeguards = [consistency_clause(item) for item in
                  data.get("surgicalSafeguards") or [] if str(item).strip()]
    finish = str(data.get("continuityFinish") or "").strip().rstrip(".")
    supplement = [*(f"Maintain {item}." for item in consistency[:1]),
                  *(f"Safeguard: {item}." for item in safeguards[:2])]
    if finish:
        supplement.append(f"Final handoff: {finish}.")
    sections.append("[Global Supplement]\n" + " ".join(supplement))

    audio_contract = str(data.get("audioContract") or "").strip()
    shot_id = str(shot.get("shotId") or "")
    split_unit = bool(
        (shot.get("sourceShotId") and str(shot.get("sourceShotId")) != shot_id)
        or re.search(r"\.SH\d+[A-Z]$", shot_id))
    if dialogue:
        foley = re.search(
            r"(?:only|retain|add)\s+[^.;]*foley[^.;]*", audio_contract, re.I)
        audio = "Use @Audio1 unchanged."
        if foley:
            audio += " " + foley.group(0).strip().capitalize() + "."
        if split_unit or re.search(
                r"\bno\b[^.;]{0,120}\b(?:musical underscore|music|bgm)\b",
                audio_contract, re.I):
            audio += " No music."
    else:
        audio = audio_contract
        if split_unit and not re.search(r"\bno\b[^.;]{0,120}\b(?:music|bgm|musical underscore)\b", audio, re.I):
            audio = audio.rstrip(" .") + ". No music."
    sections.append("[Audio]\n" + audio)
    prompt = "\n\n".join(section for section in sections if section.strip())
    prompt_sections(prompt)
    for line in prompt.splitlines():
        if re.match(r"^(?:Initial state|Continue from the previous stage|Cause|Physics|Emotion/Camera Analysis|Audio cues|End state):", line):
            emission.require_complete_sentence(line.split(":", 1)[1], context=line.split(":", 1)[0])
    return prompt


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

    locked_visual_events = animation_locked_visual_events(shot)
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
        "camera views. Add executable timing and detail without changing their story. The "
        "LOCKED VISUAL EVENT CONTRACT below is provider-facing story truth. Copy each "
        "primaryEvent verbatim into the matching stagePlan.primaryEvent and into that stage's "
        "Action/Expression line in providerPrompt. Copy each observableEndState verbatim into "
        "the matching stagePlan.observableEndState. Never move an event to another stage.\n\n"
        "LOCKED VISUAL EVENT CONTRACT (spoken words already removed):\n" +
        _j(locked_visual_events) + "\n\n"
        "CREATIVE TRANSLATION CONTRACT:\n"
        "Before compiling provider prose, return creativeTranslation.interpretation with "
        "the joke or ache, its mechanism, status before/after, exactly three audience "
        "progression reads and the emotional heart. For every SMALL or BIG item in the "
        "shot's comedyContractsApproved, return one gagClock in the same order. Copy its "
        "beatCode, mode, setup, disruption as impact, hold as recoveryHold, and button "
        "verbatim. Add directly visible anticipation and reaction, a readable recoveryHoldSec "
        "(minimum 2.0 seconds for BIG arcs and any arc that ends the unit — the landing must "
        "have air; 0.6-1.5 seconds for SMALL mid-chain arcs), and one dialogue-free "
        "providerAction sentence. Copy "
        "that providerAction verbatim into the matching Action/Expression section of "
        "providerPrompt. Do not copy spoken button words into providerAction. The generation "
        "design records whether this is the approved single unit or a continuation unit, "
        "counts the complete gag arcs, explains the density/split judgement, and copies the "
        "shot's approved visualPayoff verbatim as handoffState. These fields describe the "
        "already-approved packaging; Animation may not silently split or merge it. A 30-second "
        "unit is preferred only when it has one clear job, compact causality and one camera "
        "grammar. Dense physical comedy, exact reveal geography, route-sensitive causality or "
        "competing camera jobs require a protected split with a held handoff frame, even when "
        "the combined duration fits inside 30 seconds.\n\n"
        "Return taskMode='reference-to-video', the exact durationSec, pacingMode, generationGoal, deliveryPlan, creativeTranslation, audienceBefore, "
        "audienceAfter, beatOwner, performanceFreedom, landingBreath, directionDensity, a "
        "numbered one-to-six-shot directing plan, a consecutive stagePlan in which every "
        "stage keeps its approved beatIds, has one primary event, an emotionOrCameraAnalysis, "
        "a visible cause inherited from the prior state, and an observable end state, "
        "plus geography copied from the approved scene geography ledger, "
        "the separate reference "
        "contract, consistencyContract, audioContract, the exact continuity landing, no more "
        "than three surgical safeguards, and one paste-ready Seedance shooting script in "
        "providerPrompt. Use pacingMode='storyline' for units up to 15 seconds and "
        "pacingMode='timestamp' for 16-30 seconds; timestamp mode requires ordered startSec "
        "and endSec values on every stage as broad budgets, not frame-accurate commands; "
        "storyline mode omits both. "
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
        "dialogue cue. For split units, prohibit musical underscore in Seedance and keep only "
        "dialogue/foley/ambience; scene music is generated once in post after stitching through "
        "ElevenLabs. The prompt must begin from the approved opening state and end on a usable "
        "held handoff frame, with causal "
        "physical action, observable performance, motivated camera, readable composition, and "
        "established light/material behaviour. Keep providerPrompt between 280 and 405 words "
        "for 4-15 second units, or between 400 and 655 words for 16-30 second units; the "
        "compiler adds the canonical audio and continuity shell before validation: "
        "each instruction appears once, reference bindings stay one concise line each, and stage "
        "direction states only the action, visible performance, camera purpose and end state. "
        "It should feel like confident direction to an "
        "exceptional actor and camera crew, not an animation checklist.",
        AnimationDirection, label="department_animation", log=log, images=images)

    result.providerPrompt = compile_animation_provider_prompt(shot, result)

    if result.durationSec != duration:
        raise RuntimeError(
            f"Animation Director changed approved duration from {duration}s to "
            f"{result.durationSec}s")
    approved_geography = (
        context.get("sceneGeographyLedger") or shot.get("geographyLedgerApproved") or [])
    if approved_geography and list(result.geography) != list(approved_geography):
        raise RuntimeError("Animation Director changed the approved scene geography ledger")
    approved_stages = shot.get("storyboardStagePlanApproved") or []
    if approved_stages:
        expected = [list(stage.get("beatIds") or []) for stage in approved_stages]
        actual = [list(stage.beatIds) for stage in result.stagePlan]
        if actual != expected:
            raise RuntimeError(
                "Animation Director added, dropped, merged, reordered or reassigned approved "
                f"story stages: expected {expected}, got {actual}")
        lock_report = animation_story_lock_report(
            shot, result.providerPrompt, result.stagePlan)
        if not lock_report["ready"]:
            raise RuntimeError(
                "Animation Director weakened or reordered approved visual events: "
                + "; ".join(lock_report["errors"]))
    approved_shots = shot.get("storyboardInternalShotPlanApproved") or []
    if approved_shots and len(result.shotPlan) != len(approved_shots):
        raise RuntimeError(
            "Animation Director changed the approved number of motivated internal shots")
    translation_report = creative_translation_report(shot, result)
    if not translation_report["ready"]:
        raise RuntimeError(
            "Animation Director weakened the approved creative translation: "
            + "; ".join(translation_report["errors"]))
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
