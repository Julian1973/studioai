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

from pydantic import BaseModel, Field, field_validator, model_validator

import cb_llm
import cb_emission_conformance as emission
import cb_engine_rules
import cb_voice_director
import cb_audio_authority

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

RUNTIME_START = "<!-- RUNTIME_WORKER_START -->"
RUNTIME_END = "<!-- RUNTIME_WORKER_END -->"
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


SKILLS = {
    # One owner per production responsibility.  Compatibility names resolve here so
    # versioned skill families cannot silently become alternate runtime authorities.
    "story-architect": ROOT / "skills/crystal-bears-director/SKILL.md",
    "director": ROOT / "skills/crystal-bears-director/SKILL.md",
    "cinematography": ROOT / "skills/crystal-bears-cinematographer/SKILL.md",
    "dp": ROOT / "skills/crystal-bears-cinematographer/SKILL.md",
    "voice": ROOT / "skills/crystal-bears-voice-director/SKILL.md",
    "animation": ROOT / "skills/seedance-production-director/SKILL.md",
    "review": ROOT / "skills/crystal-bears-continuity/SKILL.md",
    "post": ROOT / "skills/crystal-bears-post/SKILL.md",
}

SKILL_ALIASES = {
    "heart-director": "director",
    "story-director": "director",
    "screenwriter": "writer",
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
        out.append(item)
    return out


def load_runtime_skill(worker, standard_version=0):
    """Read the marked runtime contract from the real SKILL.md on every worker call.

    The repository's historical skill documents contain useful research plus superseded
    pipeline notes.  Only the concise marked contract is executable; the source document
    remains available to humans without letting stale instructions silently enter a call.
    """
    del standard_version  # retained as a read-compatible API argument
    worker = SKILL_ALIASES.get(worker, worker)
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
    placements: List[CharacterFramePlacement] = Field(min_length=1, max_length=12)

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


class VoiceTagPurpose(BaseModel):
    tag: str = Field(min_length=1)
    purpose: str = Field(min_length=1)


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
    tagPurposes: List[VoiceTagPurpose] = Field(default_factory=list, max_length=8)
    takeRecipes: List["VoiceTakeRecipe"] = Field(min_length=1, max_length=3)

    @field_validator("tagPurposes", mode="before")
    @classmethod
    def accept_legacy_tag_purpose_map(cls, value):
        """Read existing canon records while emitting a strict provider-safe schema."""
        if isinstance(value, dict):
            return [{"tag": tag, "purpose": purpose}
                    for tag, purpose in value.items()]
        return value


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
    dialogueLineIndexes: List[int] = Field(
        default_factory=list, max_length=8,
        description="One-based locked-script lines spoken inside this internal shot.")
    dialogueDirections: List[str] = Field(
        default_factory=list, max_length=8,
        description="Written performance direction aligned with dialogueLineIndexes; "
                    "never raw ElevenLabs tags.")
    holdAfterDialogue: bool = Field(
        default=True,
        description="False when launch, impact or other action follows the line immediately.")
    gagBeatIds: List[str] = Field(
        default_factory=list, max_length=8,
        description="Gag clocks whose explicit hold is owned by this internal shot.")


class TimingBeatDirection(BaseModel):
    type: Literal[
        "travel", "dodge", "impact", "load_release", "tumble", "settle",
        "reaction", "turn", "aerial", "self_check", "environment_turn",
        "reveal", "business",
    ]
    count: int = Field(default=1, ge=1, le=8)
    source: str = Field(min_length=1)


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
    retroactive: bool = Field(
        default=False,
        description="True when the character must verify the outcome before claiming intent.")
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

    @model_validator(mode="before")
    @classmethod
    def derive_gag_count_from_clocks(cls, value):
        """Derive the reporting count from its authored gag-clock source."""
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        design = dict(normalized.get("generationDesign") or {})
        design["completeGagArcCount"] = len(normalized.get("gagClocks") or [])
        normalized["generationDesign"] = design
        return normalized

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
    shotPlan: List[InternalShotDirection] = Field(min_length=1, max_length=4)
    timingBeats: List[TimingBeatDirection] = Field(default_factory=list, max_length=20)
    witnessStagingSides: List[str] = Field(
        default_factory=list, max_length=4,
        description="Canon/director staging sides copied verbatim into two-character gag prompts.")
    stagePlan: List[SeedanceStageDirection] = Field(min_length=1, max_length=5)
    geography: List[str] = Field(
        min_length=1, max_length=8,
        description="Scene geography ledger copied verbatim into every shot in the scene.")
    attributeOwnership: List[str] = Field(
        default_factory=list, max_length=6,
        description="Salient feature ownership and explicit non-owner exclusions.")
    environmentContract: List[str] = Field(
        default_factory=list, max_length=6,
        description="Ordered environment-state changes that preserve scene geometry.")
    motionVocabulary: List[MotionVocabularyDirection] = Field(
        default_factory=canonical_motion_vocabulary,
        description="Canonical belongs/banned motion verbs injected from versioned data.")
    referenceContract: List[ReferenceDirection] = Field(default_factory=list, max_length=50)
    openingCarriedState: str = Field(
        default="",
        description="Visible state carried by a relay opening frame, stated explicitly.")
    openingMotionBridge: str = Field(
        default="",
        description="The first causal movement that resolves an inherited opening pose "
                    "before the new shot action begins.")
    actionOwnership: List[str] = Field(
        default_factory=list, max_length=6,
        description="Explicit actor, object and non-owner locks for actions whose "
                    "authorship must remain visually unambiguous.")
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
        for internal_shot in self.shotPlan:
            if (internal_shot.dialogueDirections and
                    len(internal_shot.dialogueDirections) !=
                    len(internal_shot.dialogueLineIndexes)):
                raise ValueError(
                    "dialogueDirections must align one-to-one with dialogueLineIndexes")
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


def _system(worker, job, standard_version=0):
    return (load_runtime_skill(worker, standard_version) + "\n\nTHIS RUN:\n" + job +
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
    charactersInFrame: List[str]
    offscreenCharacters: List[str]


class StoryTruthDirection(BaseModel):
    protagonist: str
    falseBelief: str
    practicalWant: str
    keyRelationship: str
    emotionalFearOrWound: str
    transformedAction: str
    themeProvenThroughAction: str


class TransformationMovementDirection(BaseModel):
    movement: Literal[
        "opening", "inciting-pressure", "first-adaptation", "midpoint-truth",
        "low-point", "climax-choice", "new-normal"]
    believes: str
    feels: str
    does: str
    relationshipCondition: str
    audienceFeeling: str


class EpisodeTapestryDirection(BaseModel):
    physicalMotifArc: str
    visualMotifArc: str
    colourAndLightJourney: str
    sourceSoundArc: str
    musicMotifArc: str
    environmentalMetaphor: str
    openingImage: str
    finalImage: str
    transformedMeaning: str


class SequenceBlueprintDirection(BaseModel):
    sequenceId: str
    sceneIds: List[str] = Field(min_length=1)
    runtimeTarget: str
    externalObjective: str
    emotionalStart: str
    pressureOrComplication: str
    emotionalTurn: str
    endCondition: str
    dominantAudienceFeeling: str
    nextQuestion: str


class EpisodeStoryArchitectureDirection(BaseModel):
    storyTruth: StoryTruthDirection
    transformationMap: List[TransformationMovementDirection] = Field(min_length=7, max_length=7)
    tapestryMap: EpisodeTapestryDirection
    sequenceBlueprint: List[SequenceBlueprintDirection] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def transformation_movements_are_complete_and_ordered(self):
        expected = ["opening", "inciting-pressure", "first-adaptation", "midpoint-truth",
                    "low-point", "climax-choice", "new-normal"]
        if [item.movement for item in self.transformationMap] != expected:
            raise ValueError("transformationMap movements are incomplete or out of order")
        return self


class EpisodeVisionDirection(BaseModel):
    """The complete cb_creative.EpisodeVision schema used by approved story intake."""
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
    storyArchitecture: EpisodeStoryArchitectureDirection


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
                load_runtime_skill("story-architect") + "\n\n"
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
                "logline and lead bear. episodeVision.storyArchitecture must contain one "
                "action-based story truth; exactly seven ordered transformation movements; "
                "a restrained physical, visual, colour/light, source-sound, music and "
                "environment tapestry; and a sequence blueprint covering the supplied scenes "
                "in story order. For every beat, list the exact canon character names physically "
                "visible during that beat in charactersInFrame, including a character seen inside "
                "a vision, and list speaking characters who remain outside the image in "
                "offscreenCharacters. A character merely named in dialogue is not present. "
                "Bo's Mum is locked offscreen-only and can never appear in charactersInFrame. "
                "Do not invent events or dialogue to complete it. Every scene "
                "needs at least one beat, and its first "
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
    standard_version = int(context.get("creativeDirectingStandardVersion") or 0)
    return cb_llm.structured(
        _system("cinematography",
                "Own the scene-wide environment, palette, material, light and atmosphere. "
                "Do not compose a shot or place a character.", standard_version),
        "APPROVED SCENE CONTEXT:\n" + _j(context) +
        "\n\nReturn the exact image-provider prompt for one environment-only Scene Look plate.",
        LookDirection, label="department_look", log=log)


def prepare_cinematography(context, images, *, log=print):
    standard_version = int(context.get("creativeDirectingStandardVersion") or 0)
    result = cb_llm.structured(
        _system("cinematography",
                "Own this shot's performance-ready opening stage. Establish the world, "
                "camera, light, cast identity, canon relative scale, loose starting "
                "relationship and clear action space. Do not pre-perform or freeze the "
                "acting that belongs to Animation. The attached images are in the exact "
                "labelled provider-reference order in the context.", standard_version) + "\n\n" +
                load_runtime_skill("dp", standard_version),
        "APPROVED SHOT CONTRACT AND ORDERED IMAGE LABELS:\n" + _j(context) +
        "\n\nReturn one keyframe-provider direction and one machine-readable "
        "openingFrameLayout staging envelope. Return geography as one to eight concise, "
        "literal screen-direction, travel-axis and spatial-relation statements. It becomes "
        "the approved geography ledger used verbatim by both image and video compilers. "
        "Include every openingCharactersInFrame entry exactly when that field is present; "
        "otherwise include every charactersInFrame entry exactly "
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
        str(name).strip() for name in (
            shot.get("openingCharactersInFrame")
            if shot.get("openingCharactersInFrame") is not None
            else shot.get("charactersInFrame") or [])
        if str(name).strip()))
    placements = list(result.openingFrameLayout.placements)
    placed_cast = [item.character for item in placements]
    if (len(placed_cast) != len(expected_cast) or
            set(placed_cast) != set(expected_cast)):
        raise RuntimeError(
            "Cinematography changed charactersInFrame: "
            f"expected {expected_cast}, got {placed_cast}")
    placement_by_character = {item.character: item for item in placements}
    result.openingFrameLayout.placements = [
        placement_by_character[name] for name in expected_cast]
    style_version, style_text = canonical_style_paragraph()
    result.charactersInFrame = expected_cast
    result.canonicalStyleVersion = style_version
    result.canonicalStyleParagraph = style_text
    return result


_TAG = re.compile(r"\[[^\]]+\]")
_WORD = re.compile(r"[A-Za-z0-9']+")


def _spoken_words(text):
    return [w.lower() for w in _WORD.findall(_TAG.sub("", text or ""))]


def _locked_line_text(line):
    return str(line.get("exactText") if line.get("exactText") is not None else line.get("text") or "")


def _locked_spoken_text(line):
    """Remove script numbering and parenthetical stage notes before word comparison."""
    text = _locked_line_text(line).strip()
    text = re.sub(r"^\s*\d+\s*\t", "", text)
    return re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()


def _voice_word_sequence(text):
    """Compare spoken payload only; script numbers and trailing action notes are not audio."""
    text = re.sub(r"^\s*\d+\s*\t", "", str(text or "")).strip()
    text = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
    return _spoken_words(text)


def validate_voice_direction(result, locked_lines):
    got = result.lines
    if len(got) != len(locked_lines):
        raise RuntimeError(f"Voice Director returned {len(got)} line(s); {len(locked_lines)} are locked")
    registers = (cb_voice_director.archetype_registers().get("registers") or {})
    for idx, (out, locked) in enumerate(zip(got, locked_lines), start=1):
        is_chorus = (
            str(locked.get("voiceTreatment") or "").casefold() == "group_chorus" and
            bool(locked.get("chorusMembers")))
        # A collective label is a locked script role, not a fabricated character. LLMs
        # often try to nominate one cast member for ALL; restore the typed collective
        # authority only when the line carries an explicit, non-empty chorus roster.
        if is_chorus:
            out.speaker = str(locked["speaker"])
            out.character = str(locked["speaker"])
        if locked.get("dialogueOccurrenceId"):
            if out.dialogueOccurrenceId != locked["dialogueOccurrenceId"]:
                raise RuntimeError(f"Voice Director changed occurrence ID on line {idx}")
            if out.sourceEventId != locked.get("sourceEventId"):
                raise RuntimeError(f"Voice Director changed source event ID on line {idx}")
        if out.speaker.strip().lower() != str(locked["speaker"]).strip().lower():
            raise RuntimeError(f"Voice Director changed speaker on line {idx}")
        if out.character.strip().lower() != str(locked["speaker"]).strip().lower():
            raise RuntimeError(f"Voice Director changed character on line {idx}")
        locked_text = _locked_spoken_text(locked)
        if _voice_word_sequence(out.exactDialogue) != _voice_word_sequence(locked_text):
            raise RuntimeError(f"Voice Director changed locked dialogue on line {idx}")
        if _voice_word_sequence(out.performedText) != _voice_word_sequence(locked_text):
            raise RuntimeError(f"Voice Director added, dropped or changed words on line {idx}")
        performance_override = str(locked.get("performanceOverride") or "").strip()
        if performance_override and out.performedText.strip() != performance_override:
            raise RuntimeError(
                f"Voice Director ignored the human performance override on line {idx}")
        if out.archetypeId not in registers:
            raise RuntimeError(
                f"Voice Director selected unregistered archetype {out.archetypeId!r} "
                f"on line {idx}; choose one of: {', '.join(sorted(registers))}")
        purposes = {
            item.tag.strip().casefold(): item.purpose.strip()
            for item in out.tagPurposes
            if item.tag.strip()
        }
        recipe_tags = {
            tag.strip().casefold()
            for recipe in out.takeRecipes
            for tag in re.findall(r"\[([^\]]+)\]", recipe.performedText)
            if tag.strip()
        }
        missing_purposes = sorted(tag for tag in recipe_tags if not purposes.get(tag))
        if missing_purposes:
            locked_delivery = str(locked.get("delivery") or "").strip()
            fallback = (
                f"Carry the locked delivery direction: {locked_delivery}"
                if locked_delivery else
                "Mark a deliberate performance beat while preserving the locked words."
            )
            for tag in missing_purposes:
                out.tagPurposes.append(VoiceTagPurpose(tag=tag, purpose=fallback))
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


def animation_story_lock_report(shot, provider_prompt, stage_plan=None, shot_plan=None):
    """Prove that every approved visual event survives into the provider request."""
    locked = animation_locked_visual_events(shot)
    prompt = " ".join(str(provider_prompt or "").split()).casefold()
    actual_stages = list(stage_plan or [])
    internal_shots = list(shot_plan or [])
    shot_actions = []
    for item in internal_shots:
        get = (lambda key, row=item: getattr(row, key, "")) if not isinstance(item, dict) else item.get
        value = " ".join(str(get("causalAction") or "").split()).casefold()
        if value:
            shot_actions.append(value)
    decomposed_story_is_emitted = bool(shot_actions) and all(
        action in prompt for action in shot_actions)
    errors = []
    for index, event in enumerate(locked):
        primary = event["primaryEvent"]
        ending = event["observableEndState"]
        if (primary and " ".join(primary.split()).casefold() not in prompt
                and not decomposed_story_is_emitted):
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

    shot_plan_supersedes = bool(data.get("shotPlan"))
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
        compiled_action = provider_action
        for line in shot.get("dialogueLines") or []:
            spoken = _locked_spoken_text(line)
            if spoken:
                compiled_action = re.sub(
                    re.escape(spoken), "the assigned dialogue placement",
                    compiled_action, flags=re.I)
        if (not shot_plan_supersedes and compiled_action and
                " ".join(compiled_action.split()).casefold() not in prompt):
            errors.append(
                f"{actual_clock.get('beatCode') or '?'} providerAction is absent from providerPrompt")
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
        if (not shot_plan_supersedes and contact_and_weight and
                " ".join(contact_and_weight.split()).casefold() not in prompt):
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


def carry_approved_gag_clock_text(shot, direction):
    """Restore storyboard-locked gag wording before provider prompt compilation.

    Animation owns staging and performance translation, while the approved setup,
    disruption, recovery hold and button remain immutable story facts. Structured model
    output may paraphrase those fields despite being instructed to copy them. Normalize
    that harmless drift here and let the existing report continue to reject missing,
    reordered or otherwise weakened gag contracts.
    """
    approved_by_code = {
        str(item.get("beatCode") or ""): item
        for item in (shot.get("comedyContractsApproved") or [])
        if item.get("mode") in {"SMALL", "BIG"}
    }
    translation = getattr(direction, "creativeTranslation", None)
    clocks = list(getattr(translation, "gagClocks", None) or [])
    if approved_by_code:
        event_by_beat = {}
        for event in animation_locked_visual_events(shot):
            for beat_id in event.get("beatIds") or []:
                event_by_beat[str(beat_id)] = str(event.get("primaryEvent") or "").strip()
        authored_by_code = {str(clock.beatCode or ""): clock for clock in clocks}
        clocks = []
        for code, approved in approved_by_code.items():
            clock = authored_by_code.get(code)
            if clock is None:
                clock = GagClockDirection(
                    beatCode=code,
                    mode=approved["mode"],
                    setup=approved["setup"],
                    anticipation=(approved.get("expectation") or approved["setup"]),
                    impact=approved["disruption"],
                    reaction=(approved.get("hold") or approved["button"]),
                    recoveryHold=approved["hold"],
                    recoveryHoldSec=float(approved.get("recoveryHoldSec") or 1.0),
                    button=approved["button"],
                    retroactive=False,
                    providerAction=(event_by_beat.get(code) or approved["disruption"]),
                )
            clocks.append(clock)
        translation.gagClocks = clocks
        design = getattr(translation, "generationDesign", None)
        if design is not None:
            design.completeGagArcCount = len(clocks)
        internal_shots = list(getattr(direction, "shotPlan", None) or [])
        approved_stages = list(shot.get("storyboardStagePlanApproved") or [])
        if internal_shots and len(internal_shots) == len(approved_stages):
            for internal_shot, stage in zip(internal_shots, approved_stages):
                internal_shot.gagBeatIds = [
                    beat_id for beat_id in (stage.get("beatIds") or [])
                    if str(beat_id) in approved_by_code
                ]
        else:
            for internal_shot in internal_shots:
                internal_shot.gagBeatIds = [
                    beat_id for beat_id in (internal_shot.gagBeatIds or [])
                    if str(beat_id) in approved_by_code
                ]

    # Dialogue ownership is occurrence-based, not text-based: repeated lines are
    # separate approved audio events. Rebind them deterministically to the signed
    # internal-shot story actions so a model cannot collapse identical wording.
    internal_shots = list(getattr(direction, "shotPlan", None) or [])
    dialogue = provider_dialogue_lines(shot)
    approved_internal = list(shot.get("storyboardInternalShotPlanApproved") or [])
    if internal_shots and dialogue:
        owner_by_line = {}
        for shot_index, internal_shot in enumerate(internal_shots):
            for line_index in list(internal_shot.dialogueLineIndexes or []):
                if 1 <= int(line_index) <= len(shot.get("dialogueLines") or []):
                    owner_by_line.setdefault(int(line_index), shot_index)
        if len(approved_internal) == len(internal_shots):
            approved_words = [
                " ".join(emission.dialogue_words(item.get("storyAction") or ""))
                for item in approved_internal
            ]
            for fallback, line in enumerate(dialogue, start=1):
                line_index = int(line.get("_sourceDialogueIndex") or fallback)
                exact_words = " ".join(emission.dialogue_words(
                    line.get("exactText") or line.get("text") or ""))
                matches = [index for index, words in enumerate(approved_words)
                           if exact_words and exact_words in words]
                if matches:
                    owner_by_line[line_index] = matches[0]
        for fallback, line in enumerate(dialogue, start=1):
            line_index = int(line.get("_sourceDialogueIndex") or fallback)
            if line_index in owner_by_line:
                continue
            previous = next((owner_by_line[index] for index in range(line_index - 1, 0, -1)
                             if index in owner_by_line), None)
            following = next((owner_by_line[index] for index in range(
                line_index + 1, len(shot.get("dialogueLines") or []) + 1)
                              if index in owner_by_line), None)
            owner_by_line[line_index] = following if following is not None else (
                previous if previous is not None else 0)
        source_lines = shot.get("dialogueLines") or []
        for shot_index, internal_shot in enumerate(internal_shots):
            indexes = sorted(index for index, owner in owner_by_line.items()
                             if owner == shot_index)
            internal_shot.dialogueLineIndexes = indexes
            internal_shot.dialogueDirections = [
                str((source_lines[index - 1].get("delivery") or
                     "Perform exactly as approved in @Audio1.")).strip()
                for index in indexes
            ]
    for clock in clocks:
        approved = approved_by_code.get(str(clock.beatCode or ""))
        if not approved:
            continue
        clock.mode = approved["mode"]
        clock.setup = approved["setup"]
        clock.impact = approved["disruption"]
        clock.recoveryHold = approved["hold"]
        clock.button = approved["button"]
    return direction


def prepare_voice(context, locked_lines, *, log=print):
    locked_lines = cb_audio_authority.route_lines(locked_lines)["spokenDialogue"]
    if not locked_lines:
        return {"lines": [], "audioAuthority": "seedance-2.5-sfx-only"}
    registers = cb_voice_director.archetype_registers().get("registers") or {}
    register_contract = {
        key: {
            "intent": value.get("intent"),
            "cadence": value.get("cadence"),
            "allowedTags": value.get("allowedTags") or [],
        }
        for key, value in registers.items()
    }
    result = cb_llm.structured(
        _system("voice",
                "Direct the locked words as an ElevenLabs v3 performance reconciled with "
                "the approved body action. Never add an ad-lib or rewrite a word."),
        "APPROVED SHOT CONTEXT:\n" + _j(context) +
        "\n\nREGISTERED VOICE ARCHETYPES (archetypeId must be one exact key; "
        "use only its allowedTags):\n" + _j(register_contract) +
        "\n\nTAG PURPOSE LAW: every bracketed audio tag used in performedText or in any "
        "takeRecipes.performedText must have one matching tagPurposes row. The tag value "
        "must omit brackets and its purpose must explain the dramatic job of that tag.\n" +
        "\n\nHUMAN PERFORMANCE OVERRIDE LAW: when a locked line contains "
        "performanceOverride, copy it verbatim into performedText and the primary take "
        "recipe. Reconcile intention, cadence and body direction to that performance; "
        "never restore an older delivery description.\n" +
        "\n\nLOCKED LINES (same count/order/speaker/words must be returned):\n" + _j(locked_lines),
        VoiceDirection, label="department_voice", log=log)
    return validate_voice_direction(result, locked_lines)


SEEDANCE_AUDIO_EXCLUSIONS_SECTION = (
    "[AUDIO AND EXCLUSIONS]\n"
    "No narration. No improvised or extra words. No extra voices. No subtitles, "
    "captions, text overlays, or watermark. No character redesign, no wardrobe "
    "changes, no duplicated cast members, and no mouth movement from silent listeners. "
    "Seedance 2.5 must provide instrumental music, ambience and non-verbal SFX that support the scene; "
    "do not add sung lyrics, vocal music, narration, or any additional spoken words."
)


def _seedance_audio_exclusions_section():
    return SEEDANCE_AUDIO_EXCLUSIONS_SECTION


def _seedance_nonverbal_audio_policy():
    return (
        "Seedance 2.5 must provide instrumental music, ambience and non-verbal SFX that support the "
        "scene; do not add sung lyrics, vocal music, narration, or any additional "
        "spoken words."
    )


_SEEDANCE25_RENDER_ARTIFACTS = re.compile(
    r"\b(?:4k(?:\s+ultra\s+hd)?|8k|60\s*fps|120\s*fps|hdr)\b|"
    r"\{\s*(?:0?\.\d+|1(?:\.\d+)?)\s*\}", re.I)
_SEEDANCE25_PROVIDER_UI = re.compile(
    r"(?:consistency\s*/\s*creativity\s*:\s*[^.\n]+|"
    r"high\s+quality\s*\+\s*cloth\s+simulation\s+optimization)", re.I)


def adapt_seedance25_prompt(text):
    """Remove legacy 2.0 prompt syntax without changing story direction.

    Resolution, frame rate, HDR, numeric weighting and provider UI sliders belong to
    the request/provider contract. Keeping them in the emitted prose creates stale
    instructions and makes prompt comparison unreliable. This function deliberately
    does not rewrite creative action or the small, evidence-backed exclusion shell.
    """
    value = str(text or "")
    value = _SEEDANCE25_PROVIDER_UI.sub("", value)
    value = _SEEDANCE25_RENDER_ARTIFACTS.sub("", value)
    value = re.sub(r"[ \t]{2,}", " ", value)
    value = re.sub(r"[ \t]+([,.])", r"\1", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _apply_animation_provider_shell(prompt, shot, references=None):
    """Apply the non-creative house contract around generated Seedance direction."""
    text = str(prompt or "").strip()
    routed_audio = cb_audio_authority.route_lines(shot.get("dialogueLines") or [])
    dialogue = routed_audio["spokenDialogue"]
    sfx_cues = routed_audio["seedanceSfxCues"]
    text = "\n".join(
        line for line in text.splitlines()
        if not line.strip().lower().startswith("audio-lock:")
    ).strip()

    for item in dialogue:
        exact = str(item.get("exactText") or "").strip()
        if exact:
            text = re.sub(
                re.escape(exact), "the assigned dialogue placement", text,
                flags=re.IGNORECASE)

    if dialogue:
        speakers = list(dict.fromkeys(
            str(item.get("speaker") or "").strip()
            for item in dialogue if str(item.get("speaker") or "").strip()))
        speaker_copy = " and ".join(speakers) or "Assigned speakers"
        speaker_verb = "performs" if len(speakers) == 1 else "perform"
        text = (
            "AUDIO-AUTHORITY: @Audio1 is the sole authority for voice identity, "
            "cadence, delivery, mouth timing and silence. The exact braced dialogue markers "
            "place approved words only; no alternative performance is permitted. " +
            speaker_copy + " " + speaker_verb + " only the assigned markers; listeners "
            "remain silent and closed-mouth. No narration, no improvised or extra words, "
            "no extra voices, and no subtitles or captions. Do not synthesize an alternate spoken "
            "performance: use the supplied @Audio1 for dialogue timing, mouth timing and voice; "
            "Seedance 2.5 must provide the directed non-verbal SFX, ambience and instrumental music. "
            + emission.SINGLE_INSTANCE_DIALOGUE_LOCK + "\n\n" + text
        )
        placements = "[Dialogue Placement]\n" + "\n".join(
            emission.dialogue_placement_line(item, hold_after=False)
            for item in dialogue)
        audio_heading = re.search(r"(?im)^\s*\[Audio\]\s*$", text)
        if audio_heading:
            start = audio_heading.start()
            text = (text[:start].rstrip() + "\n\n" + placements + "\n\n" +
                    text[start:].lstrip())
        else:
            text = text.rstrip() + "\n\n" + placements

    if sfx_cues:
        cue_lines = []
        for cue in sfx_cues:
            timing = (f"{float(cue['startSec']):.1f}-{float(cue['endSec']):.1f}s"
                      if cue.get("startSec") is not None and cue.get("endSec") is not None
                      else "at the authored action beat")
            cue_lines.append(
                f"- {timing}: {cue.get('character') or 'Character'} — "
                f"{', '.join(cue.get('kinds') or [])}. {cue['instruction']}")
        text = text.rstrip() + "\n\n[SEEDANCE 2.5 NON-VERBAL SFX]\n" + "\n".join(cue_lines)

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
        if role == "character_identity":
            subject = re.match(
                r"^(.+?)(?:'s|’s)?\s+(?:controls|defines|owns)?\s*.*?"
                r"\b(?:identity|turnaround)\b",
                controls, re.I)
            label = subject.group(1).strip() if subject else "character"
            reference_lines.append(_character_reference_authority_line(
                tag, label, controls))
        elif role == "location":
            reference_lines.append(
                f"{tag} defines scene/layout/light only. Do not use characters or action "
                "from it.")
        else:
            reference_lines.append(
                f"{tag} defines only {controls}. "
                f"{exclusions.get(role, 'Do not use unrelated background or content from it.')}")
    if reference_lines:
        opening = next((item for item in references
                        if str((item.model_dump() if hasattr(item, "model_dump") else item)
                               .get("role") or "").strip() in
                        {"opening_frame", "opening keyframe", "previous shot final frame"}), None)
        opening_line = (
            "OPENING-FRAME AUTHORITY: the first attached image is the approved opening frame. "
            "The video must begin on that image's composition and physical state before any "
            "motion, reframing or internal cut. Do not replace it with a prop close-up or a "
            "later action state.\n"
            if opening else ""
        )
        reference_section = "[Multimodal Reference Layer]\n" + opening_line + "\n".join(reference_lines)
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
        + ("@Audio1 remains the sole English dialogue and performance authority."
           if dialogue else "Preserve the approved audio and ambience relationship.")
    )
    supplement_pattern = re.compile(
        r"(?ims)^\s*\[(?:Global Supplement|Overall Supplement|Maintain Consistency)\]"
        r"\s*.*?(?=^\s*\[[^\]\n]+\]\s*$|\Z)")
    if supplement_pattern.search(text):
        replacement = (
            (_seedance_audio_exclusions_section() + "\n\n")
            if "[AUDIO AND EXCLUSIONS]" not in text else ""
        ) + consistency
        return supplement_pattern.sub(replacement + "\n\n", text, count=1).strip()

    audio_heading = re.search(r"(?im)^\s*\[Audio\]\s*$", text)
    prefix = (_seedance_audio_exclusions_section() + "\n\n"
              if "[AUDIO AND EXCLUSIONS]" not in text else "")
    if audio_heading:
        start = audio_heading.start()
        text = (text[:start].rstrip() + "\n\n" + prefix + consistency + "\n\n" +
                text[start:].lstrip())
    else:
        text = text.rstrip() + "\n\n" + prefix + consistency
    return text


def _image_tag_number(tag):
    match = re.match(r"^@(?:图|Image)\s*(\d+)$", str(tag or "").strip(), re.I)
    return int(match.group(1)) if match else 10_000


def _character_reference_label(controls):
    """Read a character name from either subject-first or authority-first prose."""
    text = str(controls or "").strip()
    patterns = (
        r"^(?:controls|defines|owns)\s+(.+?)(?:'s|’s)?\s+"
        r"(?:(?:character|exact|complete|uncropped|360)\s+)*(?:identity|turnaround)\b",
        r"^(.+?)(?:'s|’s)?\s+(?:character\s+)?"
        r"(?:(?:exact|complete|uncropped|360)\s+)*(?:identity|turnaround)\b",
        r"^(.+?)(?:'s|’s)?\s+(?:controls|defines|owns)\s+.*?\bidentity\b",
    )
    for pattern in patterns:
        match = re.match(pattern, text, re.I)
        if match:
            return match.group(1).strip()
    return "character identity"


_WEARABLE_STATE_RE = re.compile(
    r"\b(wearables?|clothing|costumes?|accessor(?:y|ies)|wristbands?|bracelets?|"
    r"cuffs?|bands?|necklaces?|collars?|pendants?|headdresses?|glasses|spectacles|"
    r"satchels?)\b", re.I)


def _character_reference_authority_line(tag, label, controls, ownership=()):
    """Keep approved character-state wearables under the character reference's authority."""
    state_locks = []
    controls_text = str(controls or "").strip().rstrip(".")
    if _WEARABLE_STATE_RE.search(controls_text):
        state_locks.append(controls_text)
    owner_name = re.sub(
        r"(?:'s|’s)\s+dolphin$", "", str(label or "").strip(), flags=re.I)
    owner_prefix = re.compile(rf"^{re.escape(owner_name)}(?:\b|'s\b|’s\b)", re.I)
    for value in ownership or []:
        lock = str(value or "").strip().rstrip(".")
        if (lock and _WEARABLE_STATE_RE.search(lock)
                and owner_prefix.search(lock)):
            state_locks.append(lock)
    state_locks = list(dict.fromkeys(state_locks))
    if state_locks:
        return (
            f"{tag} defines exactly one {label} identity, proportions, scale and approved "
            f"wearable state: {'; '.join(state_locks)}. Refer to that wearable state "
            "strictly; exclude background, pose, unrelated props and scene."
        )
    return (
        f"{tag} defines exactly one {label} identity/scale only; "
        "exclude background, pose, props and scene."
    )


def _render_reference_order(references):
    """Mirror provider upload semantics for provider-facing prompt tags.

    Stored shot records can use stable project slots such as @图4 for the approved
    opening frame. The provider sees a compact upload list, so the prompt must be
    rewritten against that upload order. Otherwise the prompt can say @图4 is the
    first frame while the actual first uploaded image is @图1.
    """
    references = list(references or [])
    image_items = []
    for item in references:
        data = item.model_dump() if hasattr(item, "model_dump") else dict(item or {})
        match = re.match(r"^@(?:图|Image)\s*(\d+)$", str(data.get("assetTag") or ""), re.I)
        if match:
            image_items.append((int(match.group(1)), item))

    # A contiguous slot map has already been rebound to the provider's sealed upload
    # order. Re-sorting it by semantic role would make the prompt describe different
    # files from the ones actually uploaded (for example, calling a boat a location).
    numbers = [number for number, _ in image_items]
    if (numbers and len(numbers) == len(set(numbers))
            and sorted(numbers) == list(range(1, len(numbers) + 1))):
        image_by_number = {number: item for number, item in image_items}
        non_images = [
            item for item in references
            if not re.match(
                r"^@(?:图|Image)\s*\d+$",
                str((item.model_dump() if hasattr(item, "model_dump")
                     else dict(item or {})).get("assetTag") or ""), re.I)
        ]
        return [image_by_number[number] for number in sorted(image_by_number)] + non_images

    role_rank = {
        "opening_frame": 0,
        "previous shot final frame": 0,
        "opening keyframe": 0,
        "location": 3,
        "scene plate": 3,
        "character_identity": 2,
        "prop": 4,
        "style": 5,
        "closing_frame": 6,
        "audio": 99,
    }

    def key(item):
        data = item.model_dump() if hasattr(item, "model_dump") else dict(item or {})
        role = str(data.get("role") or "").strip()
        if role == "character_identity":
            rank = role_rank[role]
        else:
            rank = role_rank.get(role, 50)
        return (rank, _image_tag_number(data.get("assetTag")))

    return sorted(references, key=key)


def enforce_aerial_camera_contract(direction):
    """Emit the R11 camera contract from typed aerial ownership, not model wording."""
    data = direction.model_dump() if hasattr(direction, "model_dump") else dict(direction or {})
    has_aerial = any(
        str(item.get("type") or "").casefold() == "aerial"
        for item in (data.get("timingBeats") or []))
    if not has_aerial:
        return direction
    aerial_pattern = re.compile(
        r"\b(aerial|leap|dive|breach|half[- ]roll|double back|double backward|"
        r"triple twist|multi-rotation|biles)\b",
        re.I)
    owned = [
        item for item in direction.shotPlan
        if aerial_pattern.search(" ".join((item.purpose, item.causalAction)))
    ]
    if len(owned) == 1 and not re.search(
            r"track(?:s|ing)? (?:the )?(?:full|complete) (?:arc|aerial|rotation)",
            owned[0].framingLensAndCamera, re.I):
        owned[0].framingLensAndCamera = (
            owned[0].framingLensAndCamera.rstrip(" .") +
            ". Camera tracks the full arc."
        )
    return direction


def _approved_attribute_ownership(data, character_state_locks=None):
    ownership = [
        str(item).strip() for item in data.get("attributeOwnership") or []
        if (str(item).strip()
            and not re.match(r"^@(?:图|Image)\s*\d+\b", str(item).strip(), re.I))
    ]
    ownership.extend(
        str(lock).strip() for lock in (character_state_locks or {}).values()
        if str(lock).strip()
    )
    return list(dict.fromkeys(ownership))


def provider_audio_routing(shot):
    """Route provider-safe script lines to dialogue and non-verbal audio lanes."""
    names = {
        str(name).strip() for name in (shot.get("charactersInFrame") or [])
        if len(str(name).strip()) > 1
    }
    lines = []
    for source_index, source in enumerate(shot.get("dialogueLines") or [], start=1):
        line = dict(source)
        line["_sourceDialogueIndex"] = source_index
        text = str(line.get("exactText") or line.get("text") or "")
        for name in sorted(names, key=len, reverse=True):
            text = re.sub(rf"\b{re.escape(name.upper())}\b", name, text)
        if line.get("exactText") is not None:
            line["exactText"] = text
        else:
            line["text"] = text
        lines.append(line)
    return cb_audio_authority.route_lines(lines)


def provider_dialogue_lines(shot):
    """Return only spoken dialogue with provider-safe character-name casing."""
    return provider_audio_routing(shot)["spokenDialogue"]


def compile_animation_provider_prompt(shot, direction):
    """Compile the provider prompt from typed, approved Animation direction.

    The structured direction is the creative source of truth.  The prose returned in
    ``providerPrompt`` by the specialist is deliberately ignored here: allowing the model
    to describe the beat once in fields and then author it again as free prose was the
    golden-link failure.  This compiler emits each approved stage, gag action, reference
    role and handoff once, in the shape expected by the Seedance prompt preflight.
    """
    data = direction.model_dump() if hasattr(direction, "model_dump") else dict(direction or {})
    character_state_locks = dict(shot.get("characterStateLocks") or {})
    approved_ownership = _approved_attribute_ownership(data, character_state_locks)
    routed_audio = provider_audio_routing(shot)
    dialogue = routed_audio["spokenDialogue"]
    seedance_sfx_cues = routed_audio["seedanceSfxCues"]
    references = _render_reference_order(data.get("referenceContract") or [])
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

    def complete(value, *, context="render direction"):
        """Preserve the complete approved direction without length-based rewriting."""
        return emission.ensure_complete_sentence(value, context=context)

    def consistency_clause(value):
        text = " ".join(str(value or "").split()).strip().rstrip(".")
        text = re.sub(r"^(?:use|keep|maintain|preserve|protect)\s+", "", text,
                      flags=re.I)
        return text

    def strip_request_parameters(value):
        text = " ".join(str(value or "").split()).strip()
        text = re.sub(r"\b(?:generate|create)\s+a\s+(\d+\s*[- ]\s*second\s+)",
                      lambda match: match.group(0).replace(match.group(1), ""),
                      text, flags=re.I)
        text = re.sub(r"\b\d+\s*[- ]\s*second\s+(?=(?:reference-to-video|video|unit|shot)\b)",
                      "", text, flags=re.I)
        text = re.sub(r"\b(?:in\s+)?(?:16:9|9:16|1:1)\s+(?:frame|composition|format)\b",
                      "frame", text, flags=re.I)
        text = re.sub(r"\b(?:16:9|9:16|1:1)\b", "frame", text, flags=re.I)
        text = re.sub(r"\b(?:480p|720p|1080p|2160p)\b", "", text, flags=re.I)
        return text

    def strip_prompt_request_parameters(value):
        text = str(value or "")
        text = re.sub(r"\b(?:aspect ratio|resolution)\b", "composition", text, flags=re.I)
        text = re.sub(r"\bmodel(?: id| version)?\b", "render engine", text, flags=re.I)
        text = re.sub(r"\b(?:480p|720p|1080p|2160p)\b", "", text, flags=re.I)
        text = re.sub(r"(?<!\d)(?:16:9|9:16|1:1)(?!\d)", "wide frame", text, flags=re.I)
        text = re.sub(r"\bduration\s*:", "timing:", text, flags=re.I)
        text = re.sub(r"\bno cuts?\b", "motivated transitions only", text, flags=re.I)
        text = re.sub(r"\bno handheld\b", "stable motivated camera", text, flags=re.I)
        return text

    def camera_clause(value, number):
        text = " ".join(str(value or "").split()).strip()
        text = re.sub(rf"^(?:cut\s+to\.?\s*)?shot\s+{number}\s*[:\-—]\s*",
                      "", text, flags=re.I)
        text = re.sub(r"^cut\s+to\.?\s*", "", text, flags=re.I)
        return text.strip()

    def normalize_reference_grammar(text):
        lines = []
        for line in str(text or "").splitlines():
            stripped = line.strip()
            if re.match(r"^@(?:图|Image)\s*\d+\s+owns\b", stripped, re.I) and re.search(
                    r"\b(?:opening composition|carried state|first frame)\b",
                    stripped, re.I):
                line = re.sub(
                    r"^(@(?:图|Image)\s*\d+)\s+owns\b.*$",
                    r"\1 is the first frame. It defines opening composition and carried "
                    r"state only. Do not use it to redesign identity, proportions, "
                    r"materials or later action.",
                    stripped,
                    flags=re.I)
            elif re.match(r"^@(?:图|Image)\s*\d+\s+(?:controls|owns)\b", stripped, re.I):
                line = re.sub(
                    r"^(@(?:图|Image)\s*\d+)\s+(?:controls|owns)\s+(.+?)\s+only\b.*$",
                    r"\1 defines \2 only. Do not use unrelated background, pose, "
                    r"composition, props or scene from \1.",
                    stripped,
                    flags=re.I)
                if line == stripped:
                    line = re.sub(
                        r"^(@(?:图|Image)\s*\d+)\s+(?:controls|owns)\s+(.+?)\.?$",
                        r"\1 defines \2 only. Do not use unrelated background, characters, "
                        r"action, props or scene.",
                        stripped,
                        flags=re.I)
            lines.append(line)
        return "\n".join(lines)

    sections = []
    if dialogue:
        sections.append(
            "AUDIO-AUTHORITY: @Audio1 is the sole authority and sole performance authority "
            "for every English dialogue line, voice identity, cadence, delivery, mouth "
            "timing and silence. Each exact dialogue line appears once in braces in the "
            "Shot Sequence and is bound to its named speaker and @Audio1. The exact braced "
            "dialogue markers place approved words only; no alternative performance is "
            "permitted. Listeners remain silent and closed-mouth unless they are the named "
            "speaker for that exact line. No narration, no extra words, and no subtitles or "
            "captions. Dialogue language: English. No music comes from @Audio1; Seedance "
            "generates separate synchronized non-dialogue SFX, ambience and instrumental "
            "musical underscore beneath the approved dialogue rhythm. "
            + emission.SINGLE_INSTANCE_DIALOGUE_LOCK)

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
    slot_bindings = []
    collapse_bindings = []
    location_tag = next((
        f"@图{index}"
        for index, reference in enumerate(references, start=1)
        if str((reference.model_dump() if hasattr(reference, "model_dump")
                else dict(reference)).get("role") or "").strip() == "location"
    ), "the location reference")
    for index, reference in enumerate(references, start=1):
        item = reference.model_dump() if hasattr(reference, "model_dump") else dict(reference)
        original_tag = str(item.get("assetTag") or "").strip()
        tag = f"@图{index}" if re.match(r"^@(?:图|Image)\s*\d+$", original_tag, re.I) else original_tag
        role = str(item.get("role") or "").strip()
        raw_controls = str(item.get("controls") or "").strip()
        controls = complete(raw_controls,
                            context=f"{tag or 'reference'} role").rstrip(".")
        if not tag or not controls:
            continue
        role_label = role
        if role == "character_identity":
            role_label = _character_reference_label(raw_controls)
            collapse_bindings.append((tag, role_label))
        slot_bindings.append((tag, role_label))
        if role != "audio":
            exclusion = exclusions.get(
                role, "Do not use unrelated background or content from it.")
            if re.search(r"\b(?:exclude|does not define|do not use)\b", controls, re.I):
                exclusion = ""
            if role == "opening_frame":
                is_relay_opening = bool(
                    re.search(r"previous (?:unit|shot)|final frame", controls, re.I)
                    or shot.get("sourceType") == "relay"
                    or shot.get("sourceShotId"))
                if is_relay_opening:
                    carried_state = str(data.get("openingCarriedState") or "").strip()
                    if not carried_state:
                        first_stage = next(iter(data.get("stagePlan") or []), {})
                        first_stage = (first_stage.model_dump() if hasattr(first_stage, "model_dump")
                                       else dict(first_stage))
                        carried_state = str(
                            first_stage.get("initialOrCarriedState") or "").strip()
                    if not carried_state:
                        raise ValueError(
                            "relay opening frame requires openingCarriedState (R20)")
                    reference_lines.append(
                        f"{tag} is the first frame and the previous shot's approved final "
                        "frame. Use it only for carried character state: it controls the "
                        "exact opening pose, emotion, light and carried prop state only: "
                        f"{carried_state.rstrip('.')}. "
                        "Do not use it as the scene geography, camera framing or environment "
                        f"layout authority; {location_tag} and Geography control the "
                        "wider scene. If an Opening Motion Bridge is present, it alone "
                        "controls how this inherited pose resolves into the new action.")
                else:
                    reference_lines.append(
                        f"{tag} is the first frame. It defines opening composition and "
                        "state; exclude later action and redesign.")
            elif role == "character_identity":
                reference_lines.append(_character_reference_authority_line(
                    tag, role_label, raw_controls, approved_ownership))
            elif role == "location":
                reference_lines.append(
                    f"{tag} defines scene/layout/light only; exclude characters/action.")
            else:
                reference_lines.append(
                    f"{tag} defines {controls}."
                    + (f" {exclusion}" if exclusion else ""))
    if reference_lines:
        stability = emission.reference_slot_stability_line(slot_bindings).replace(
            "Project-stable slots:", "Slots:").replace(
            ". Never swap roles.", "; never swap.")
        collapse = emission.multi_angle_collapse_summary(collapse_bindings).replace(
            "Multi-angle collapse:", "Angles:").replace(
            "; views are angles, not extra characters.", "; views are not extra characters.")
        reference_lines = [
            line.replace("This first frame defines ", "Defines ")
            for line in reference_lines
        ]
        lines = [stability, collapse, *reference_lines]
        sections.append("[Multimodal Reference Layer]\n" + "\n".join(
            line for line in lines if line))

    opening_motion_bridge = str(data.get("openingMotionBridge") or "").strip()
    if opening_motion_bridge:
        sections.append(
            "[Opening Motion Bridge]\n" +
            complete(opening_motion_bridge, context="opening motion bridge"))

    action_ownership = [
        complete(item, context="action ownership")
        for item in data.get("actionOwnership") or [] if str(item).strip()
    ]
    if action_ownership:
        sections.append("[ACTION OWNERSHIP]\n" + "\n".join(action_ownership))

    ownership = approved_ownership
    if ownership:
        sections.append("[ATTRIBUTE OWNERSHIP]\n" + "\n".join(ownership))

    environment_contract = [
        strip_request_parameters(item).strip() for item in data.get("environmentContract") or []
        if str(item).strip()
    ]
    if environment_contract:
        sections.append("[ENVIRONMENT CONTRACT]\n" + "\n".join(environment_contract))

    scene_state_lines = []
    action_has_departed = bool(re.search(
        r"\b(?:already (?:moving|underway)|moving away|has departed|underway)\b",
        str(shot.get("action") or ""), re.I))
    for lock in shot.get("sceneContinuityLocks") or []:
        if hasattr(lock, "model_dump"):
            item = lock.model_dump()
        elif isinstance(lock, dict):
            item = dict(lock)
        else:
            item = {"label": "Scene continuity", "value": str(lock)}
        label = str(item.get("label") or "Scene continuity").strip()
        lock_text = " ".join(str(item.get(key) or "") for key in ("value", "forbidden"))
        if action_has_departed and re.search(
                r"\b(?:moored|alongside the pier|before departure|move the sailboat away)\b",
                lock_text, re.I):
            continue
        value = complete(item.get("value"),
                         context=f"{label} scene continuity").rstrip(".")
        if not value:
            continue
        line = f"{label}: {value}."
        raw_forbidden = item.get("forbidden")
        forbidden = (
            complete(raw_forbidden,
                     context=f"{label} forbidden continuity").rstrip(".")
            if str(raw_forbidden or "").strip() else ""
        )
        if forbidden:
            line += f" Forbidden: {forbidden}."
        scene_state_lines.append(line)
    if scene_state_lines:
        sections.append("[Scene Continuity State]\n" + "\n".join(scene_state_lines))

    goal = strip_request_parameters(
        data.get("generationGoal") or data.get("dramaticBeat") or "")
    sections.append("[One-Sentence Summary]\n" + goal)

    global_lines = []
    style_version, style_text = canonical_style_paragraph()
    global_lines.append(f"Style ({style_version}): {style_text}")
    geography = [
        strip_request_parameters(item).strip()
        for item in data.get("geography") or []
        if str(item).strip()]
    if geography:
        global_lines.append("Geography: " + " ".join(geography))
    mechanism = str(interpretation.get("mechanism") or "").strip()
    heart = str(interpretation.get("emotionalHeart") or "").strip()
    short_unit = float(data.get("durationSec") or shot.get("durationSec") or 0) <= 15
    # Short units already carry their mechanism and heart in the summary, playable
    # action, performance hold and end state. Repeating them here spends the words
    # that should carry an executable camera/shot plan.
    global_values = []
    if not short_unit and not data.get("shotPlan"):
        global_values.extend([
            ("Comic or emotional mechanism", mechanism),
            ("Performance", complete(data.get("performanceArc"),
                                     context="performance arc")),
            ("Physical causality", complete(data.get("physicalCauseAndEffect"),
                                            context="physical causality")),
            ("Emotional heart", heart),
        ])
    for label, value in global_values:
        if value:
            global_lines.append(f"{label}: {value}")
    sections.append("[Global Settings]\n" + "\n".join(global_lines))

    # Keep every generated take physically alive at the held beat: the provider needs
    # an executable eyeline, active thought and non-vacant landing, not just plot verbs.
    sections.append("[Living Performance]\n" +
                    cb_engine_rules.living_performance_boilerplate(shot, data))

    audio_cues = emission.dialogue_cues(
        dialogue, duration_sec=data.get("durationSec") or shot.get("durationSec"))
    audio_cues_by_source = {
        int(line.get("_sourceDialogueIndex") or index): cue
        for index, (line, cue) in enumerate(zip(dialogue, audio_cues), start=1)
    }
    sfx_cues_by_source = {
        int(cue["sourceDialogueIndex"]): cue
        for cue in seedance_sfx_cues
        if cue.get("sourceDialogueIndex") is not None
    }
    internal_shots = list(data.get("shotPlan") or [])
    multi_shot = len(internal_shots) > 1
    explicit_cut_sequence = any(
        re.search(
            r"\b(?:cut to|hard cut|smash cut|match cut|intercut)\b",
            " ".join(str(value or "") for value in (
                (item.model_dump() if hasattr(item, "model_dump") else dict(item)).get("framingLensAndCamera"),
                (item.model_dump() if hasattr(item, "model_dump") else dict(item)).get("causalAction"),
            )),
            re.I)
        for item in internal_shots)
    emitted_holds = set()
    emitted_dialogue = []
    sailing_causality_injected = False
    if internal_shots:
        shot_lines = []
        for index, internal_shot in enumerate(internal_shots):
            item = (internal_shot.model_dump() if hasattr(internal_shot, "model_dump")
                    else dict(internal_shot))
            number = int(item.get("shotNumber") or index + 1)
            camera = complete(
                item.get("framingLensAndCamera"),
                context=f"Internal shot {number} camera")
            camera = strip_request_parameters(camera_clause(camera, number))
            authored_action = emission.drop_superseded_action_prefix(
                item.get("causalAction"), environment_contract)
            sailing_action = cb_engine_rules.sailing_departure_action(
                authored_action, shot, data)
            sailing_causality_injected = (
                sailing_causality_injected or sailing_action != authored_action)
            action = complete(
                strip_request_parameters(sailing_action),
                context=f"Internal shot {number} action")
            performance_value = str(item.get("observablePerformance") or "").strip()
            performance = (
                complete(strip_request_parameters(performance_value),
                         context=f"Internal shot {number} performance")
                if performance_value else "")
            landing_value = str(item.get("landingImage") or "").strip()
            landing = (
                emission.ensure_complete_sentence(
                    strip_request_parameters(landing_value),
                    context=f"Internal shot {number} end state")
                if landing_value else "")
            unit_label = "Shot" if explicit_cut_sequence else "Phase"
            parts = [f"{unit_label} {number}: Camera: {camera}", f"Action: {action}"]
            if performance:
                parts.append(f"Performance: {performance}")
            if landing:
                parts.append(f"End state: {landing}")
            directions = list(item.get("dialogueDirections") or [])
            for dialogue_position, line_index in enumerate(
                    item.get("dialogueLineIndexes") or []):
                source_index = int(line_index)
                cue = audio_cues_by_source.get(source_index)
                sfx_cue = sfx_cues_by_source.get(source_index)
                if cue is None and sfx_cue is None:
                    raise ValueError(
                        f"Internal shot {number} references invalid dialogue line {line_index}")
                if sfx_cue is not None:
                    start, end = sfx_cue.get("startSec"), sfx_cue.get("endSec")
                    timing = (
                        f"{float(start):g}-{float(end):g}s: "
                        if start is not None and end is not None else ""
                    )
                    parts.append(
                        "Non-verbal SFX: " + timing
                        + str(sfx_cue.get("instruction") or "").strip())
                if cue is None:
                    continue
                direction_text = (directions[dialogue_position]
                                  if dialogue_position < len(directions) else "")
                parts.append(emission.dialogue_placement_line(
                    cue,
                    direction=direction_text,
                    hold_after=bool(item.get("holdAfterDialogue", True))))
                emitted_dialogue.append(source_index)
            for beat_id in item.get("gagBeatIds") or []:
                clock = gag_clocks.get(str(beat_id))
                if not clock:
                    # A specialist may inherit a legacy gag marker even when the
                    # approved shot defines no gag clocks. It contributes no timing
                    # contract in that case, regardless of whether the shot has
                    # dialogue, so it must not block an otherwise valid prompt.
                    if not gag_clocks:
                        continue
                    raise ValueError(
                        f"Internal shot {number} references unknown gag beat {beat_id}")
                hold_sec = clock.get("recoveryHoldSec")
                if hold_sec is None:
                    raise ValueError(f"{beat_id} gag button has no numeric recoveryHoldSec")
                hold_direction = str(clock.get("recoveryHold") or "").strip()
                if (item.get("holdAfterDialogue", True) and
                        re.search(r"\bbefore (?:the )?(?:line|dialogue)\b",
                                  hold_direction, re.I)):
                    hold_direction = (
                        "Hold after the spoken line so the body truth lands before the next "
                        "action or cut.")
                parts.append(
                    f"Hold: {float(hold_sec):.1f}s — "
                    f"{hold_direction}")
                emitted_holds.add(str(beat_id))
            shot_lines.append(" ".join(parts))
        sides = [str(item).strip() for item in data.get("witnessStagingSides") or []
                 if str(item).strip()]
        if sides:
            witness_payoff = (
                "carry the joke" if gag_clocks else "carry the emotional truth")
            shot_lines.append(
                "Witness staging: " + " ".join(sides) +
                " Hold on the non-acting witness; their stillness and the hold length " +
                witness_payoff + ".")
        # The shot plan already owns story, gag action and physics. Re-emitting the
        # source fields here makes the provider parse competing versions of the same
        # action and violates the emission standard's state-each-action-once rule.
        if multi_shot and dialogue:
            seen = set()
            duplicates = sorted(
                index for index in emitted_dialogue
                if index in seen or seen.add(index))
            if duplicates:
                raise ValueError(
                    "multi-shot dialogue duplicates locked line(s): "
                    + ", ".join(str(index) for index in duplicates))
            missing_dialogue = [
                index for index in audio_cues_by_source
                if index not in seen]
            if missing_dialogue and not shot_lines:
                raise ValueError(
                    "multi-shot dialogue has no internal shot to carry missing locked lines")
            if missing_dialogue:
                fallback_lines = [
                    emission.dialogue_placement_line(
                        audio_cues_by_source[index],
                        direction=str(audio_cues_by_source[index].get("delivery") or "").strip(),
                        hold_after=False)
                    for index in missing_dialogue]
                shot_lines[-1] = shot_lines[-1].rstrip() + " " + " ".join(fallback_lines)
        section_title = (
            "[Shot Sequence]" if explicit_cut_sequence else
            "[Timed Action Phases — One Continuous Render]" if multi_shot else
            "[Camera and Shot Plan]")
        if multi_shot and not explicit_cut_sequence:
            shot_lines.insert(
                0,
                "One continuous Seedance render: these are timed action phases, not "
                "coverage cuts, not separate setups, and not permission to invent a new "
                "final tableau.")
        sections.append(section_title + "\n" + "\n".join(shot_lines))

    stage_sections = []
    approved_physics = {
        str(item.get("beatCode") or ""): str(
            (item.get("physicalStaging") or {}).get("contactAndWeight") or "").strip()
        for item in shot.get("comedyContractsApproved") or []
        if str((item.get("physicalStaging") or {}).get("contactAndWeight") or "").strip()
    }
    for item in shot.get("physicalStagings") or []:
        if isinstance(item, str):
            text = item.strip()
            if text:
                approved_physics[f"physical-staging-{len(approved_physics) + 1}"] = text
            continue
        item_dict = item.model_dump() if hasattr(item, "model_dump") else (
            dict(item) if isinstance(item, dict) else {})
        beat_code = str(item_dict.get("beatCode") or "").strip()
        contact = str(item_dict.get("contactAndWeight") or "").strip()
        if beat_code and contact:
            approved_physics[beat_code] = contact
    audio_cues = emission.dialogue_cues(
        dialogue, duration_sec=data.get("durationSec") or shot.get("durationSec"))
    for index, stage in enumerate(stages):
        if multi_shot:
            break
        if internal_shots:
            break
        item = stage.model_dump() if hasattr(stage, "model_dump") else dict(stage)
        stage_number = int(item.get("stageNumber") or index + 1)
        beat_label = ", ".join(str(value) for value in item.get("beatIds") or [])
        purpose = beat_label or " ".join(str(item.get("purpose") or "Story event").split())
        start, end = item.get("startSec"), item.get("endSec")
        performance_led = short_unit
        if not performance_led and start is not None and end is not None:
            heading = f"[Stage {stage_number}: {start:g}-{end:g}s [{purpose}]]"
        else:
            heading = f"[Stage {stage_number}: [{purpose}]]"
        prefix = "Initial state" if index == 0 else "Continue from the previous stage"
        event = str(item.get("primaryEvent") or "").strip()
        additions = []
        for beat_id in item.get("beatIds") or []:
            action = gag_actions.get(str(beat_id))
            if action and " ".join(action.split()).casefold() not in " ".join(event.split()).casefold():
                additions.append(action)
        action = " ".join([event, *additions]).strip()
        for line in dialogue:
            exact = str(line.get("exactText") or "").strip()
            if exact:
                action = re.sub(
                    re.escape(exact), "the assigned dialogue placement", action,
                    flags=re.I)
        # Quantified action requirements in the approved shot contract are load-bearing.
        # They must survive the Director-to-provider compile even when the structured
        # primaryEvent summarizes the route more tersely.
        purpose_text = " ".join(str(shot.get("purpose") or "").split())
        near_miss = re.search(
            r"\b(one|two|three|four|five|\d+)\s+(?:readable\s+)?near[- ]miss(?:es)?\b",
            purpose_text, re.I)
        if near_miss and not re.search(
                r"\b" + re.escape(near_miss.group(1)) +
                r"\s+(?:readable\s+)?near[- ]miss(?:es)?\b", action, re.I):
            count = near_miss.group(1)
            action = (
                f"Include {count} readable near-misses before the first impact. " + action)
        physics_lines = []
        for beat_id in item.get("beatIds") or []:
            physics = approved_physics.get(str(beat_id))
            if physics:
                physics_lines.append(f"Physics: {emission.require_complete_sentence(physics, context=f'{beat_id} physical staging')}")
        stage_audio = [] if internal_shots else [
            cue for cue in audio_cues
            if cue["startSec"] < float(end) and cue["endSec"] > float(start)]
        dialogue_markers = [
            emission.dialogue_placement_line(
                cue,
                direction=str(cue.get("delivery") or "").strip())
            for cue in stage_audio]
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
            f"{prefix}: {complete(item.get('initialOrCarriedState'), context=f'Stage {stage_number} initial state')}",
            f"Cause: {emission.require_complete_sentence(item.get('cause'), context=f'Stage {stage_number} cause')}",
            f"Action/Expression: {action}",
            *physics_lines,
            *hold_lines,
            *([] if internal_shots else [
                "Emotion/Camera Analysis: "
                + complete(item.get("emotionOrCameraAnalysis"),
                           context=f"Stage {stage_number} emotion/camera analysis")
            ]),
            *dialogue_markers,
            f"End state: {str(item.get('observableEndState') or '').strip()}",
        ]
        stage_sections.append("\n".join(lines))
    missing_holds = set(gag_clocks) - emitted_holds
    if missing_holds:
        raise ValueError(
            "gag button(s) are not owned by a compiled stage: "
            + ", ".join(sorted(missing_holds)))
    if stage_sections:
        sequence_header = (
            "[Performance Sequence]" if short_unit else "[Timestamp Script Storyboard]")
        sections.append(sequence_header + "\n" + "\n\n".join(stage_sections))
    human_review = str(shot.get("watchDirectorFeedbackApproved") or "").strip()
    if human_review:
        sections.append(
            "[Human Review Correction]\n"
            "This bounded correction is approved Director intent. Integrate it into the "
            "staged action and camera while preserving canon, the opening frame, exact "
            "@Audio1 dialogue and the signed landing state:\n"
            + complete(human_review, context="human review correction")
        )
    consistency = [consistency_clause(item) for item in
                   data.get("consistencyContract") or [] if str(item).strip()]
    safeguards = [consistency_clause(item) for item in
                  data.get("surgicalSafeguards") or [] if str(item).strip()]
    finish = str(data.get("continuityFinish") or "").strip().rstrip(".")
    instance_lock = emission.character_instance_lock(shot.get("charactersInFrame") or [])
    if instance_lock:
        consistency = [item for item in consistency if not
                       emission.is_instance_lock_equivalent(
                           item, shot.get("charactersInFrame") or [])]
    supplement = [*(item for item in [instance_lock] if item),
                  *(f"Maintain {item}." for item in consistency[:1]),
                  *(f"Safeguard: {item}." for item in safeguards[:2])]
    traversal = cb_engine_rules.travel_traversal_boilerplate(shot, data)
    if traversal:
        supplement.append(traversal)
    repeated_contacts = cb_engine_rules.repeated_contact_boilerplate(shot, data)
    if repeated_contacts:
        supplement.append(repeated_contacts)
    sailing = cb_engine_rules.sailing_departure_boilerplate(shot, data)
    if sailing and not sailing_causality_injected:
        supplement.append(sailing)
    supplement.append(cb_engine_rules.living_performance_boilerplate(shot, data))
    # A short unit's last stage already carries its complete observable handoff. Repeating
    # it in compiler boilerplate spends words without adding creative direction.
    if finish and not short_unit:
        supplement.append(f"Final handoff: {finish}.")

    audio_contract = str(data.get("audioContract") or "").strip()
    shot_id = str(shot.get("shotId") or "")
    split_unit = bool(
        (shot.get("sourceShotId") and str(shot.get("sourceShotId")) != shot_id)
        or re.search(r"\.SH\d+[A-Z]$", shot_id))
    if dialogue:
        foley = re.search(
            r"(?:only|retain|add)\s+[^.;]*foley[^.;]*", audio_contract, re.I)
        audio = (
            "@Audio1 is the sole authority and sole performance authority for every "
            "English dialogue line, voice identity, cadence, delivery, mouth timing and "
            "silence. Each exact dialogue line appears once in braces in the Shot Sequence "
            "and is bound to its named speaker and @Audio1. No alternative performance is "
            "permitted; listeners remain silent and closed-mouth unless they are the named "
            "speaker for that line. No narration or extra words. Use Seedance-generated "
            "non-dialogue SFX, ambience and instrumental musical underscore only underneath "
            "the approved dialogue rhythm."
        )
        # Speaker ownership and occurrence counts are compiled from the immutable
        # dialogue lines above. Specialist prose may describe performance, but must not
        # restate or renumber dialogue authority in the provider payload.
        if foley:
            audio += " " + foley.group(0).strip().capitalize() + "."
        if not re.search(
                r"Seedance may generate non-verbal music, ambience and SFX|"
                r"\bno\b[^.;]{0,120}\b(?:music|bgm|musical underscore)\b",
                audio, re.I):
            audio += " " + _seedance_nonverbal_audio_policy()
    else:
        audio = audio_contract
        if not re.search(
                r"Seedance may generate non-verbal music, ambience and SFX|"
                r"\bno\b[^.;]{0,120}\b(?:music|bgm|musical underscore)\b",
                audio, re.I):
            audio = audio.rstrip(" .") + ". " + _seedance_nonverbal_audio_policy()
    if seedance_sfx_cues:
        authored_sfx = []
        for cue in seedance_sfx_cues:
            start, end = cue.get("startSec"), cue.get("endSec")
            timing = (
                f"{float(start):g}-{float(end):g}s: "
                if start is not None and end is not None else ""
            )
            authored_sfx.append(timing + str(cue.get("instruction") or "").strip())
        audio = audio.rstrip(" .") + ". Authored non-verbal SFX cues: " + " ".join(authored_sfx)
    if not re.search(r"\bno watermark\b", audio, re.I):
        audio = audio.rstrip(" .") + ". No watermark."
    sections.append("[Audio]\n" + audio)
    sections.append(_seedance_audio_exclusions_section())
    sections.append("[Global Supplement]\n" + " ".join(supplement))
    prompt = strip_prompt_request_parameters(normalize_reference_grammar(
        "\n\n".join(section for section in sections if section.strip())))
    prompt = adapt_seedance25_prompt(prompt)
    prompt_sections(prompt)
    for line in prompt.splitlines():
        if re.match(r"^(?:Initial state|Continue from the previous stage|Cause|Physics|Emotion/Camera Analysis|Audio cues|Dialogue performance|End state):", line):
            emission.require_complete_sentence(line.split(":", 1)[1], context=line.split(":", 1)[0])
    dialogue_check = emission.validate_dialogue_synthesis(prompt, dialogue)
    if not dialogue_check["ready"]:
        raise ValueError("dialogue synthesis contract failed: " +
                         "; ".join(dialogue_check["errors"]))
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
    standard_version = int(context.get("creativeDirectingStandardVersion") or 0)
    result = cb_llm.structured(
        _system("animation",
                "Turn the approved dramatic beat into one playable Seedance generation unit. "
                "The first attached image is the approved opening frame; remaining attachments "
                "follow the exact reference order in the context. Continuous relay may use one "
                "shot; action units use two to four internal shots, each with one clean motion "
                "idea and a real story, performance or reaction purpose.", standard_version),
        "APPROVED SHOT, VOICE DIRECTION AND ORDERED ATTACHMENTS:\n" + _j(context) +
        "\n\nDIRECTORIAL FREEDOM CONTRACT:\n"
        "When humanWorkingAnimationPrompt or watchDirectorFeedback is present, treat it as "
        "approved bounded review feedback: preserve its requested emotional, physical, "
        "continuity and sound corrections "
        "while translating them into this typed direction and the deterministic provider prompt. "
        "Every explicitly counted action, action order, camera response, performance quality "
        "and audio ownership rule in watchDirectorFeedback must appear in the matching "
        "shotPlan causalAction/observablePerformance and stagePlan primaryEvent; do not leave "
        "the correction only in provider prose or a safeguard. "
        "Do not copy its prose wholesale and do not let it override locked canon, SEE or HEAR. "
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
        "providerAction sentence. Mark retroactive=true when the character must verify the "
        "outcome before performing pride or another emotion. Copy "
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
        "numbered one-to-four-shot directing plan, typed timingBeats, canonical witnessStagingSides "
        "for two-character gags, and a consecutive stagePlan in which every "
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
        "Emit every scripted line exactly once inside the stage that owns it, attributed to the "
        "named speaker with the approved delivery. Protect a full-beat pose hold after a line when "
        "the story needs its recognition, reaction or comic button to register. Suppress that hold "
        "when the approved action begins immediately with or after the line, such as a launch, impact "
        "or interruption; name that immediate action in the same stage instead. In a dialogue-rich "
        "shot, at least one non-immediate recognition or reaction line must retain readable air. "
        "R8 is mandatory: when timingBeats contains travel, dodge, impact, load_release, tumble "
        "or aerial action, return two to four motivated internal shots, one clean motion or "
        "story idea per shot. Place any cut deliberately at a change of story job or maximum "
        "stored energy; a continuous camera intention may connect those phases but may not "
        "collapse them into one undifferentiated internal shot. "
        "Classify ordinary locomotion by a character whose normal movement is flight as travel, "
        "not aerial. Use timing beat type aerial only for an explicitly approved compound, "
        "multi-rotation or multi-stage airborne manoeuvre that needs its own tracked arc. "
        "@Audio1 remains sole authority for voice identity, cadence, "
        "delivery, mouth timing and silence. Use the exact attached asset tags and bind each one separately in the prompt "
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
        "established light/material behaviour. Preserve all direction required to deliver "
        "the approved beat and emotional outcome; never shorten it to meet a word count. The "
        "compiler adds the canonical audio and continuity shell before validation: "
        "each instruction appears once, reference bindings stay one concise line each, and stage "
        "direction states only the action, visible performance, camera purpose and end state. "
        "It should feel like confident direction to an "
        "exceptional actor and camera crew, not an animation checklist.",
        AnimationDirection, label="department_animation", log=log, images=images)

    result = enforce_aerial_camera_contract(result)
    result = carry_approved_gag_clock_text(shot, result)

    if result.durationSec != duration:
        raise RuntimeError(
            f"Animation Director changed approved duration from {duration}s to "
            f"{result.durationSec}s")
    approved_geography = (
        context.get("sceneGeographyLedger") or shot.get("geographyLedgerApproved") or [])
    if approved_geography:
        result.geography = list(approved_geography)
    if (not result.witnessStagingSides and
            len(shot.get("charactersInFrame") or []) >= 2 and
            result.creativeTranslation.gagClocks):
        continuity_characters = list(
            ((shot.get("continuityOut") or {}).get("characters") or []))
        result.witnessStagingSides = [
            f"{item.get('character')} holds {item.get('screenZone')}; "
            f"{item.get('pose')}; facing {item.get('facing')}."
            for item in continuity_characters
            if item.get("character") and item.get("screenZone") and
            item.get("pose") and item.get("facing")
        ]
    result.providerPrompt = compile_animation_provider_prompt(shot, result)
    approved_stages = shot.get("storyboardStagePlanApproved") or []
    if approved_stages:
        expected = [list(stage.get("beatIds") or []) for stage in approved_stages]
        actual = [list(stage.beatIds) for stage in result.stagePlan]
        if actual != expected:
            raise RuntimeError(
                "Animation Director added, dropped, merged, reordered or reassigned approved "
                f"story stages: expected {expected}, got {actual}")
        lock_report = animation_story_lock_report(
            shot, result.providerPrompt, result.stagePlan, result.shotPlan)
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
                "whether the intended dramatic or comic beat is actually felt. Compare the "
                "approved emotional entry, pressure, visible turn, exit and held-after-beat "
                "against what is observable. Test whether the child-clear want, hidden "
                "inner action, relationship pressure and change in thought remain direct "
                "without explanatory dialogue. Judge whether environment, physical motif, "
                "colour/light and sound deepen the same emotional argument rather than "
                "decorate it or order a feeling; identify whether the beat remains legible "
                "muted and in silhouette/staging. Check that must-understand information is "
                "clear, protected information is not revealed early, relationship distance, "
                "power, touch and eyelines carry the intended change, and score respects the "
                "approved silence rule. For comedy, identify setup, expectation, "
                "disruption, reaction, button and hold separately; presence is not a landing. "
                "Then judge acting, prop contact, weight, anticipation, follow-through, "
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
