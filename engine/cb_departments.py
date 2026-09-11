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

from pydantic import BaseModel, Field, create_model, field_validator, model_validator

import cb_llm
import cb_emission_conformance as emission
import cb_engine_rules
import cb_voice_director
import cb_audio_authority
from cb_production_contracts import visual_event_text, validate_timeline, shot_handoff_instruction
from studio_scene_handoff import SoundHandoff, sound_instruction
import studio_prompt_aliases

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

RUNTIME_START = "<!-- RUNTIME_WORKER_START -->"
RUNTIME_END = "<!-- RUNTIME_WORKER_END -->"
DIRECTOR_GRAMMAR_PACK = HERE / "grammar_pack.json"
CRYSTAL_ENERGY_LAW = ROOT / "shows/crystal-bears/laws/crystal_energy_law.txt"


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


def crystal_energy_law():
    """Return the show-wide visual law injected into every animation prompt."""
    text = CRYSTAL_ENERGY_LAW.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError("Crystal energy law is blank")
    return text


_PROMPT_SECTION_RE = re.compile(
    r"(?ms)^\[([^\]\n]+)\]\s*\n(.*?)(?=^\[[^\]\n]+\]\s*$|\Z)")


def _coerce_text_list(value):
    if value is None:
        return value
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    return value


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
    "seedream-keyframe": ROOT / "skills/crystal-bears-seedream-keyframes/SKILL.md",
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
     "worker": "Director", "influences": "Joe Brumm · Pete Docter · Chris Sanders",
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
    role = text.split(RUNTIME_START, 1)[1].split(RUNTIME_END, 1)[0].strip()
    standard = (ROOT / "skills/production-standard.md").read_text(encoding="utf-8").strip()
    if worker == 'animation':
        from studio_prompt_structure import WRITING_BRIEF
        role += '\n\n' + WRITING_BRIEF
    return standard + "\n\n" + role


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


class CameraConsciousness(BaseModel):
    """Positive camera choices carried from DP through WATCH.

    Optional fields preserve historical approved direction; current DP work is asked
    to author them so camera craft reaches the provider instead of becoming a note.
    """
    dramaticOwner: str = ""
    emotionalAction: str = ""
    cameraState: Literal["controlled", "observational", "flowing"] | None = None
    viewpoint: str = ""
    lensFamily: str = ""
    movementTrigger: str = ""
    movementFinish: str = ""
    focusPlan: str = ""
    exitCondition: str = ""


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
    cameraConsciousness: CameraConsciousness = Field(default_factory=CameraConsciousness)
    providerPrompt: str = Field(min_length=40)

    @field_validator(
        "geography", "charactersInFrame", "negativeSpace", "referenceUse",
        "continuityProtections",
        mode="before",
    )
    @classmethod
    def coerce_provider_text_lists(cls, value):
        return _coerce_text_list(value)


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
    """A playable view, not a second copy of the Studio control records.

    Keep visual fields concise (aim for about 100 words total per view). Name only
    visible performers or an explicitly required offscreen cause. Preserve every
    causal transition and exact dialogue cue; identity bibles and state ledgers
    belong in the shared source records, not repeated inside each visual field.
    """
    sourceViewId: Optional[str] = Field(default=None, description='Exact approved coverage viewId enacted by this view. Never substitute a story stage ID or add a placeholder view.')
    sourceStageNumbers: List[int] = Field(default_factory=list, description="Approved story stages visibly enacted by this view; multiple views may cover one stage.")
    shotNumber: int = Field(ge=1, le=6)
    transitionType: Literal['opening', 'cut', 'move', 'hold', 'auto'] = 'auto'
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
                  "style", "audio", "video", "closing_frame", "continuity_state"]
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
        gt=0, le=30.0,
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


class TimelineEvent(BaseModel):
    performer: str | None = Field(default=None, description="Exact character owning a nonverbal performance; never the dialogue speaker by default.")
    visibility: Literal['visible', 'offscreen'] | None = Field(default=None, description="Whether this character performance must be readable on camera or is deliberately offscreen.")
    channel: Literal["action", "camera", "music", "dialogue", "sfx"]
    startSec: float = Field(ge=0)
    endSec: float = Field(gt=0)
    event: str = Field(min_length=1)


from studio_director_card import CharacterRoleEvent


class AnimationDirection(BaseModel):
    soundHandoff: SoundHandoff | None = None
    cinematographyHandoff: CameraConsciousness = Field(
        default_factory=CameraConsciousness,
        description="The approved Director of Photography decisions carried verbatim into "
                    "the animation request. This is a handoff, not a second camera plan.")
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
    timeline: List[TimelineEvent] = Field(default_factory=list,
        description="Optional exact timing by independent action, camera, music, dialogue and sfx channels. Parallel channels may overlap.")
    characterRoleEvents: List[CharacterRoleEvent] = Field(default_factory=list,
        description="Copy authored directorCard.characterRoleEvents exactly, retaining event ID, view, character and action. Do not transfer event ownership.")
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

    @field_validator(
        "precisionReasons", "witnessStagingSides", "geography",
        "attributeOwnership", "environmentContract", "actionOwnership",
        "consistencyContract", "surgicalSafeguards", "contentToPreserve",
        "blockoutMappings",
        mode="before",
    )
    @classmethod
    def coerce_provider_text_lists(cls, value):
        return _coerce_text_list(value)

    @model_validator(mode="before")
    @classmethod
    def inject_versioned_motion_vocabulary(cls, value):
        """Keep versioned grammar under compiler control, not model control."""
        if isinstance(value, dict):
            value = dict(value)
            value["motionVocabulary"] = [
                item.model_dump() for item in canonical_motion_vocabulary()
            ]
            # Preserve supplied stage clocks and validate them as timestamp pacing.
            # A mislabeled short unit is a format mismatch, not a reason to discard
            # its authored timing or ask the provider to invent the direction again.
            stages = value.get('stagePlan') or []
            if value.get('pacingMode', 'storyline') == 'storyline' and stages and all(
                    isinstance(stage, dict) and stage.get('startSec') is not None
                    and stage.get('endSec') is not None for stage in stages):
                value['pacingMode'] = 'timestamp'
        return value

    @model_validator(mode="after")
    def precision_must_be_earned(self):
        timeline = validate_timeline([event.model_dump() for event in self.timeline], self.durationSec)
        if not timeline["ready"]:
            raise ValueError("; ".join(timeline["errors"]))
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
    failureClass: Literal["source", "planning", "compilation", "submission", "model-output",
                          "no-material-failure", "unverified"] = Field(default="unverified",
        description="Classify using the originating sealed source/plan/payload and observed media. A visible defect alone does not prove its origin. Use unverified when the needed evidence was not supplied.")
    failureClassEvidence: str = Field(default="Not classified against originating request",
        description="Cite the exact source/payload and observed range supporting the classification. Proposed repairs are advisory until cause is established; never infer submission correctness from a prompt score.")
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
    from studio_director_card import CONTRACT
    return (CONTRACT + "\n\n" + load_runtime_skill(worker, standard_version) + "\n\nTHIS RUN:\n" + job +
            "\n\nYou are preparing a candidate for human approval. Do not claim it is "
            "approved. Do not call or simulate a media provider. Return only the requested "
            "structured result.")


def _j(value, limit=22000):
    return json.dumps(value, ensure_ascii=False, indent=1)[:limit]


def _creative_context(context):
    # Preserve the whole creative handoff; never cut JSON or tail decisions silently.
    clean = dict(context)
    from studio_director_card import REVIEW_CRITERIA
    clean["creativeReviewCriteria"] = REVIEW_CRITERIA
    observations = clean.pop("reviewObservations", "")
    return observations + "\n\n" + json.dumps(clean, ensure_ascii=False, indent=1)


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
    movement: str = Field(min_length=1, description="An event or movement actually present in the approved screenplay, in screenplay order.")
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
    transformationMap: List[TransformationMovementDirection] = Field(default_factory=list)
    tapestryMap: EpisodeTapestryDirection
    sequenceBlueprint: List[SequenceBlueprintDirection] = Field(min_length=1, max_length=12)



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
                "action-based story truth; only the movements present in the approved screenplay, in screenplay order; "
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
        StoryIntakeDirection, tier="premium", label="department_story", log=log)


def prepare_look(context, *, log=print):
    context = dict(context)
    from cb_learning_context import brief
    context.setdefault("reviewObservations", brief(context))
    standard_version = int(context.get("creativeDirectingStandardVersion") or 0)
    return cb_llm.structured(
        _system("cinematography",
                "Own the scene-wide environment, palette, material, light and atmosphere. "
                "Do not compose a shot or place a character.", standard_version),
        "APPROVED SCENE CONTEXT:\n" + _creative_context(context) +
        "\n\nReturn the exact image-provider prompt for one environment-only Scene Look plate.",
        LookDirection, label="department_look", log=log)


def prepare_cinematography(context, images, *, log=print):
    context = dict(context)
    from studio_director_card import stage_decisions
    context['directorDecisions'] = stage_decisions(context.get('shot') or context, 'see')
    from cb_learning_context import brief
    context.setdefault("reviewObservations", brief(context))
    standard_version = int(context.get("creativeDirectingStandardVersion") or 0)
    result = cb_llm.structured_with_repair(
        _system("cinematography",
                "Own this shot's performance-ready opening stage. Establish the world, "
                "camera, light, cast identity, canon relative scale, loose starting "
                "relationship and clear action space. Do not pre-perform or freeze the "
                "acting that belongs to Animation. The attached images are in the exact "
                "labelled provider-reference order in the context.", standard_version) + "\n\n" +
                load_runtime_skill("dp", standard_version) + "\n\n" +
                load_runtime_skill("seedream-keyframe", standard_version),
        "APPROVED SHOT CONTRACT AND ORDERED IMAGE LABELS:\n" + _creative_context(context) +
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
        "do not describe character identity from memory. Author cameraConsciousness as the "
        "positive creative authority for this shot: dramaticOwner, emotionalAction, cameraState "
        "(controlled, observational or flowing), viewpoint, lensFamily, movementTrigger, "
        "movementFinish, focusPlan and exitCondition. A deliberate hold is a complete "
        "cinematic choice: set cameraState=controlled and state that it holds by design; "
        "never add decorative movement.",
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
    if not set(expected_cast).issubset(set(placed_cast)):
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
        bound = cb_voice_director.bind_primary_performance(out.model_dump(), locked)
        for recipe, compiled_recipe in zip(out.takeRecipes, bound.get("takeRecipes") or []):
            recipe.performedText = compiled_recipe["performedText"]
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


def _coerce_storyboard_stage_plan(shot):
    """Normalize approved stage plans from legacy text or current structured rows."""
    raw = shot.get("storyboardStagePlanApproved") or []
    if isinstance(raw, str):
        chunks = [
            item.strip()
            for item in re.split(r"(?=\bStage\s+\d+\b)", raw)
            if item.strip()
        ] or [raw.strip()]
        stages = []
        for index, text in enumerate(chunks):
            number_match = re.search(r"\bStage\s+(\d+)\b", text, flags=re.I)
            stage_number = int(number_match.group(1)) if number_match else index + 1
            body = re.sub(
                r"^\s*Stage\s+\d+\s*(?:\([^)]*\))?\s*:?\s*",
                "",
                text,
                flags=re.I,
            ).strip()
            stages.append({
                "stageNumber": stage_number,
                "beatIds": [],
                "primaryEvent": body,
                "observableEndState": "",
            })
        return stages
    stages = []
    for index, stage in enumerate(raw):
        if isinstance(stage, dict):
            stages.append(stage)
        elif stage:
            stages.append({
                "stageNumber": index + 1,
                "beatIds": [],
                "primaryEvent": str(stage).strip(),
                "observableEndState": "",
            })
    return stages


def animation_locked_visual_events(shot):
    """Return the provider-facing story facts inherited from the approved storyboard."""
    locked = []
    for stage in _coerce_storyboard_stage_plan(shot):
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
    prompt = visual_event_text(provider_prompt)
    bound_stages = {number for view in (shot_plan or [])
                    for number in ((view.model_dump() if hasattr(view, 'model_dump') else view)
                                   .get('sourceStageNumbers') or [])}
    actual_stages = list(stage_plan or [])
    errors = []
    for index, event in enumerate(locked):
        primary = event["primaryEvent"]
        ending = event["observableEndState"]
        if primary and visual_event_text(primary) not in prompt and event['stageNumber'] not in bound_stages:
            errors.append(
                f"stage {event['stageNumber']} approved visual event is absent from providerPrompt")
        if actual_stages:
            if index >= len(actual_stages):
                errors.append(f"stage {event['stageNumber']} is absent from stagePlan")
                continue
            actual = actual_stages[index]
            get = (lambda key: getattr(actual, key, "")) if not isinstance(actual, dict) else actual.get
            if visual_event_text(get("primaryEvent")) != visual_event_text(primary):
                errors.append(f"stage {event['stageNumber']} primaryEvent changed")
            if ending and str(get("observableEndState") or "").strip() != ending:
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
                ((_coerce_storyboard_stage_plan(shot) or [{}])[-1]
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
            duration = float(data.get('durationSec') or shot.get('durationSec') or 30)
            if float(hold_sec) > duration:
                errors.append(f"{actual_clock.get('beatCode') or '?'} landing hold exceeds the shot duration")
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
        ((_coerce_storyboard_stage_plan(shot) or [{}])[-1].get("observableEndState"))
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
            approved_hold_sec = float(
                approved.get("recoveryHoldSec") or
                (shot.get("performanceBudgetApproved") or {}).get("landingHoldSec") or
                2.0)
            if approved.get("mode") == "BIG":
                approved_hold_sec = max(2.0, approved_hold_sec)
            if clock is None:
                clock = GagClockDirection(
                    beatCode=code,
                    mode=approved["mode"],
                    setup=approved["setup"],
                    anticipation=(approved.get("expectation") or approved["setup"]),
                    impact=approved["disruption"],
                    reaction=(approved.get("hold") or approved["button"]),
                    recoveryHold=approved["hold"],
                    recoveryHoldSec=approved_hold_sec,
                    button=approved["button"],
                    retroactive=False,
                    providerAction=(event_by_beat.get(code) or approved["disruption"]),
                )
            else:
                clock.recoveryHoldSec = approved_hold_sec
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
            stage_by_number = {int(stage.get("stageNumber") or i + 1): stage
                               for i, stage in enumerate(approved_stages)}
            for internal_shot in internal_shots:
                linked = [beat for number in internal_shot.sourceStageNumbers
                          for beat in stage_by_number.get(number, {}).get("beatIds", [])]
                internal_shot.gagBeatIds = list(dict.fromkeys(
                    beat_id for beat_id in (linked or internal_shot.gagBeatIds or [])
                    if str(beat_id) in approved_by_code))

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
                           if exact_words and (" " + exact_words + " ") in (" " + words + " ")]
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
                _animation_dialogue_direction(shot, source_lines[index - 1])
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


def _animation_dialogue_direction(shot, line):
    """HEAR owns performance; revised WATCH owns current visual blocking."""
    if shot.get('watchDirectorFeedbackApproved'):
        return ('Perform exactly as approved in @Audio1; body blocking follows '
                'the current WATCH view and its measured dialogue interval.')
    occurrence = line.get('dialogueOccurrenceId')
    brief = next((item for item in shot.get('voiceDirectorBrief', [])
                  if occurrence and item.get('dialogueOccurrenceId') == occurrence), {})
    return str(brief.get('physicalActionRelationship') or line.get('delivery') or
               'Perform exactly as approved in @Audio1.').strip()


def carry_approved_dialogue_ownership(shot, direction):
    """Bind every approved spoken line to an internal shot before prompt compile.

    Director output can preserve the visible action while dropping stale
    ``dialogueLineIndexes`` after a script/split amendment. The compiler and R15
    rules need typed ownership, so repair that layer from the current approved
    shot dialogue instead of asking for another creative rewrite.
    """
    internal_shots = list(getattr(direction, "shotPlan", None) or [])
    dialogue = provider_dialogue_lines(shot)
    if not internal_shots or not dialogue:
        return direction

    expected = [
        int(line.get("_sourceDialogueIndex") or fallback)
        for fallback, line in enumerate(dialogue, start=1)
    ]
    seen = []
    valid_expected = set(expected)
    for internal_shot in internal_shots:
        for line_index in list(getattr(internal_shot, "dialogueLineIndexes", []) or []):
            try:
                number = int(line_index)
            except (TypeError, ValueError):
                continue
            if number in valid_expected:
                seen.append(number)

    if seen == expected and len(seen) == len(set(seen)):
        for internal_shot in internal_shots:
            indexes = list(getattr(internal_shot, "dialogueLineIndexes", []) or [])
            directions = list(getattr(internal_shot, "dialogueDirections", []) or [])
            if len(directions) < len(indexes):
                internal_shot.dialogueDirections = directions + [
                    "Perform exactly as approved in @Audio1, in beat with the visible "
                    "action and reaction."
                    for _ in range(len(indexes) - len(directions))
                ]
        return direction

    for internal_shot in internal_shots:
        internal_shot.dialogueLineIndexes = []
        internal_shot.dialogueDirections = []

    source_lines = shot.get("dialogueLines") or []
    shot_count = max(1, len(internal_shots))
    for position, line_index in enumerate(expected):
        owner_index = min(shot_count - 1, int(position * shot_count / max(1, len(expected))))
        # Keep Pydantic max_length=8 valid even for long dialogue units.
        if len(internal_shots[owner_index].dialogueLineIndexes) >= 8:
            owner_index = next(
                (index for index, item in enumerate(internal_shots)
                 if len(item.dialogueLineIndexes) < 8),
                owner_index,
            )
        if len(internal_shots[owner_index].dialogueLineIndexes) >= 8:
            continue
        line = source_lines[line_index - 1] if 0 < line_index <= len(source_lines) else {}
        delivery = _animation_dialogue_direction(shot, line)
        if not delivery:
            speaker = str(line.get("speaker") or "").strip()
            exact = str(line.get("exactText") or line.get("text") or "").strip()
            delivery = (
                f"{speaker} delivers {{{exact}}} exactly as approved in @Audio1, "
                "timed to the in-beat action and held reaction."
            )
        internal_shots[owner_index].dialogueLineIndexes.append(line_index)
        internal_shots[owner_index].dialogueDirections.append(delivery)
        internal_shots[owner_index].holdAfterDialogue = True
    return direction


def prepare_voice(context, locked_lines, *, log=print):
    context = dict(context)
    from studio_director_card import stage_decisions
    context['directorDecisions'] = stage_decisions(context.get('shot') or context, 'hear')
    from cb_learning_context import brief
    context.setdefault("reviewObservations", brief(context))
    locked_lines = cb_audio_authority.route_lines(locked_lines)["spokenDialogue"]
    if not locked_lines:
        return {
            "shotId": str(context.get("shotId") or ""),
            "sceneIntention": str(
                context.get("sceneIntention") or
                context.get("purpose") or
                context.get("storyBeat") or
                "Seedance owns non-dialogue vocal SFX for this shot."
            ),
            "lines": [],
            "audioAuthority": "seedance-2.5-sfx-only",
        }
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
        "APPROVED SHOT CONTEXT:\n" + _creative_context(context) +
        "\n\nREGISTERED VOICE ARCHETYPES (archetypeId must be one exact key; "
        "use only its allowedTags):\n" + _j(register_contract) +
        "\n\nPROVIDER HANDOFF: ElevenLabs receives takeRecipes.performedText and voice settings, "
        "not cadenceAndBreath, subtext, or other prose notes. Express the selected acting "
        "and cadence in each recipe using purposeful allowed v3 tags and faithful punctuation. "
        "Do not leave a direction solely in prose metadata. Plain delivery is valid when "
        "intentional; do not add arbitrary tags or speak action notes.\n" +
        "\n\nTAG PURPOSE LAW: every bracketed audio tag used in performedText or in any "
        "takeRecipes.performedText must have one matching tagPurposes row. The tag value "
        "must omit brackets and its purpose must explain the dramatic job of that tag.\n" +
        "\n\nHUMAN PERFORMANCE OVERRIDE LAW: when a locked line contains "
        "performanceOverride, copy it verbatim into performedText and the primary take "
        "recipe. Reconcile intention, cadence and body direction to that performance; "
        "never restore an older delivery description.\n" +
        "\n\nLOCKED LINES (same count/order/speaker/words must be returned):\n" + _j(locked_lines),
        VoiceDirection, label="department_voice", log=log)
    cards = cb_voice_director.voice_cards().get("characters") or {}
    cards_casefold = {str(name).casefold(): card for name, card in cards.items()}
    for directed, locked in zip(result.lines, locked_lines):
        # Keep explicit human performance markup literal. Generated markup is a
        # suggestion and can be reduced deterministically to the registered palette.
        if str(locked.get("performanceOverride") or "").strip():
            continue
        register = registers.get(directed.archetypeId) or {}
        chorus = list(locked.get("chorusMembers") or [])
        member_cards = [cards_casefold[str(name).casefold()] for name in chorus
                        if str(name).casefold() in cards_casefold]
        if member_cards:
            default_tags = {
                tag for card in member_cards for tag in card.get("defaultTags", [])
            }
            banned_sets = [
                {str(tag).casefold() for tag in card.get("bannedTags", [])}
                for card in member_cards
            ]
            banned = set.intersection(*banned_sets) if banned_sets else set()
        else:
            card = cards_casefold.get(
                str(locked.get("speaker") or directed.character).casefold()) or {}
            default_tags = set(card.get("defaultTags", []))
            banned = {str(tag).casefold() for tag in card.get("bannedTags", [])}
        allowed = {
            str(tag).casefold()
            for tag in default_tags.union(register.get("allowedTags") or [])
        } - banned
        removed = cb_voice_director.normalize_generated_performance_tags(directed, allowed)
        if removed:
            log(
                f"VOICE DIRECTOR - {context.get('shotId') or result.shotId}: removed "
                f"unsupported generated tag(s) on {directed.dialogueOccurrenceId}: "
                + ", ".join(removed)
            )
    return validate_voice_direction(result, locked_lines)


SEEDANCE_AUDIO_EXCLUSIONS_SECTION = (
    "[AUDIO AND EXCLUSIONS]\n"
    "No narration. No improvised or extra words. No extra voices. No subtitles, "
    "captions, text overlays, or watermark. No character redesign, no wardrobe "
    "changes, no duplicated cast members, and no mouth movement from silent listeners. "
    "Seedance 2.5 must provide instrumental music, ambience and non-verbal SFX that support the scene; "
    "do not add sung lyrics, vocal music, narration, or any additional spoken words."
)

SEEDANCE_EXACT_AUDIO_EXCLUSIONS_SECTION = (
    "[AUDIO AND EXCLUSIONS]\n"
    "Preserve the supplied @Audio1 bed unchanged. During dialogue, only the active "
    "speaker articulates; all listeners remain silent and non-articulating. During "
    "approved laughter or giggling already present in @Audio1, animate only the "
    "characters audibly participating in that exact interval. Do not generate "
    "additional dialogue, laughter, vocalisations or narration. No music. No ambience. "
    "No SFX. "
    "No subtitles, captions, text overlays or watermark. No character redesign, "
    "wardrobe changes or duplicated cast members."
)

SEEDANCE_EXACT_AUDIO_DIALOGUE_LOCK = (
    "Use @Audio1 as the only voice authority. Only the character currently speaking "
    "in @Audio1 may move their mouth. No music. No ambience. No SFX. "
    "VERBATIM DIALOGUE LOCK - TRANSCRIPT ONLY. Every approved line below already exists "
    "once in @Audio1. Use the written transcript only to assign the correct speaker and "
    "mouth timing. Do not synthesize, repeat, dub, echo, layer or replace any spoken line. "
    "The final render must contain exactly one audible dialogue performance: the supplied "
    "@Audio1, unchanged."
)


def _seedance_audio_exclusions_section(*, exact_audio_only=False):
    return (SEEDANCE_EXACT_AUDIO_EXCLUSIONS_SECTION
            if exact_audio_only else SEEDANCE_AUDIO_EXCLUSIONS_SECTION)


def _preserves_exact_audio_bed(audio_contract):
    """Return true only for an explicit shot-level opt-out of provider audio."""
    text = " ".join(str(audio_contract or "").split())
    preserves_track = bool(re.search(
        r"\b(?:preserve|use)\s+@Audio1\s+unchanged\b", text, re.I))
    rejects_provider_audio = bool(re.search(
        r"\bno\s+provider-generated\b[^.;]*(?:audio|dialogue|laughter|"
        r"vocalisations?|music|ambience|sfx|sound)", text, re.I))
    return preserves_track and rejects_provider_audio


def _seedance_nonverbal_audio_policy():
    return (
        "Seedance 2.5 must provide instrumental music, ambience and non-verbal SFX that support the "
        "scene; do not add sung lyrics, vocal music, narration, or any additional "
        "spoken words."
    )


def _directed_nonverbal_performance(prompt, timeline, *, exact_audio_only=False, audio_contract=''):
    """A timed, authorised character SFX must not conflict with a speech-only mouth lock."""
    explicit_sfx = bool(re.search(r'authori[sz]ed[^.]*\bSFX\b|\bSFX\b[^.]*authori[sz]ed', audio_contract, re.I))
    cues = [item for item in timeline if (item.get('channel') == 'sfx' or
                                        explicit_sfx and item.get('channel') == 'action') and
            re.search(r'\b(?:laugh\w*|giggl\w*|chuckl\w*|gasp\w*|sigh\w*|sob\w*|cry\w*|breath\w*|effort)\b', str(item.get('event', '')), re.I)]
    if exact_audio_only or not cues:
        return prompt
    prompt = re.sub(r'Only the character currently speaking in @Audio1 may move their mouth\.',
                    'Only the active @Audio1 speaker articulates dialogue.', prompt)
    prompt = re.sub(r'[Ll]isteners remain silent and closed-mouth(?: unless[^.]+)?',
                    'Listeners remain silent and closed-mouth except during their explicitly timed '
                    'nonverbal SFX; only the active @Audio1 speaker articulates dialogue', prompt)
    prompt = prompt.replace('no mouth movement from silent listeners',
                            'no dialogue articulation from nonspeakers')
    ownership = []
    for cue in cues:
        if cue.get('performer'):
            owner = str(cue['performer']).strip()
            visibility = cue.get('visibility')
            ownership.append(
                f"{owner} alone performs this nonverbal cue from {float(cue['startSec']):g} "
                f"to {float(cue['endSec']):g} seconds: {cue['event']}. " +
                (f"Keep {owner}'s face and body readable in the planned view. " if visibility == 'visible' else
                 f"{owner} is intentionally offscreen; do not transfer the sound or mouth movement to a visible listener. " if visibility == 'offscreen' else '') +
                "No other character performs or lip-syncs this cue.")
    has_audio1 = '@Audio1' in prompt or '@Audio1' in str(audio_contract or '')
    no_dialogue_unit = bool(re.search(r'no\s+(?:elevenlabs\s+)?(?:spoken\s+)?dialogue|no\s+approved\s+speech', str(audio_contract or ''), re.I))
    authority_tail = ('Preserve @Audio1 and its speaker timing unchanged.'
                      if has_audio1 and not no_dialogue_unit else
                      'No approved speech exists in this unit; do not create dialogue, extra words or lip-sync.')
    return prompt + ('\n\n[DIRECTED NONVERBAL PERFORMANCE]\n' +
                     ('\n'.join(ownership) + '\n' if ownership else '') +
                     'During the named nonverbal SFX cues, animate the assigned character’s natural '
                     'sound-specific mouth and body performance, including overlap with another character’s dialogue when approved dialogue exists. '
                     'This permits no extra words or vocal events outside the directed cue. ' +
                     authority_tail)


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
        reference_heading = "REFERENCE AUTHORITY" if "[REFERENCE AUTHORITY]" in text else "Multimodal Reference Layer"
        reference_section = f"[{reference_heading}]\n" + opening_line + "\n".join(reference_lines)
        reference_pattern = re.compile(
            r"(?ims)^\s*\[(?:Multimodal Reference Layer|REFERENCE AUTHORITY)\]\s*.*?"
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
    from studio_dynamic_state import review_plan
    plan_review = review_plan(shot)
    if plan_review['errors']:
        raise ValueError('Direction plan needs correction: ' + '; '.join(plan_review['errors']))
    data = direction.model_dump() if hasattr(direction, "model_dump") else dict(direction or {})
    camera_handoff = dict(data.get("cinematographyHandoff") or {})

    def camera_consciousness_lines():
        """Emit one compact, positive camera brief from the approved DP handoff.

        This belongs in the deterministic compiler, so a specialist cannot leave the
        camera craft stranded in its own department output or replace it with generic
        prose in ``providerPrompt``.
        """
        labels = (
            ("Dramatic owner", "dramaticOwner"),
            ("Emotional action", "emotionalAction"),
            ("Camera state", "cameraState"),
            ("Viewpoint", "viewpoint"),
            ("Lens family", "lensFamily"),
            ("Movement trigger", "movementTrigger"),
            ("Movement finish", "movementFinish"),
            ("Focus plan", "focusPlan"),
            ("Exit condition", "exitCondition"),
        )
        return [f"{label}: {complete(camera_handoff.get(key), context=label.casefold())}"
                for label, key in labels if str(camera_handoff.get(key) or "").strip()]

    audio_contract = str(data.get("audioContract") or "").strip()
    exact_audio_only = _preserves_exact_audio_bed(audio_contract)
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

    camera_handoff_lines = camera_consciousness_lines()

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
        text = re.sub(r"\baspect ratio\b", "composition", text, flags=re.I)
        text = re.sub(r"\bmodel(?: id| version)?\b", "render engine", text, flags=re.I)
        text = re.sub(r"\b(?:480p|720p|1080p|2160p)\b", "", text, flags=re.I)
        text = re.sub(r"(?<!\d)(?:16:9|9:16|1:1)(?!\d)", "wide frame", text, flags=re.I)
        text = re.sub(r"\bduration\s*:", "timing:", text, flags=re.I)
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
    task_mode = str(data.get("taskMode") or "").strip()
    if task_mode in {"extend-forward", "extend-backward"}:
        direction_label = "forward" if task_mode == "extend-forward" else "backward"
        carried_state = complete(
            data.get("openingCarriedState")
            or ((data.get("stagePlan") or [{}])[0].get("initialOrCarriedState")
                if isinstance((data.get("stagePlan") or [{}])[0], dict) else ""),
            context="video extension boundary state",
        )
        continuity_lines = [
            f"@Video1 is the source video to extend {direction_label}.",
            "The first frame of this generated unit must continue directly from @Video1 with no hard cut, no black frame, no reset and no replay.",
            "Preserve pose, props, layout, camera, light and motion at the connecting frame: " + carried_state,
            "Each subject remains the same continuous instance throughout; do not duplicate, split, replace or swap any character or prop.",
        ]
        sections.append("[Video Extension Continuity]\n" + "\n".join(continuity_lines))
    authority = ""
    if dialogue:
        if exact_audio_only:
            authority = (
                "AUDIO-AUTHORITY: @Audio1 is the sole authority and sole performance "
                "authority for every English dialogue line, voice identity, cadence, "
                "delivery, breath, pause, mouth timing, approved laughter interval and "
                "silence. Each exact dialogue line appears once in braces in the Shot "
                "Sequence and is bound to its named speaker and @Audio1. During dialogue, "
                "only the active speaker articulates; listeners remain silent and closed-mouth "
                "and non-articulating during that dialogue interval. During approved laughter "
                "or giggling in @Audio1, animate "
                "only the characters audibly participating in that exact interval. Preserve "
                "the complete @Audio1 bed unchanged. No alternative performance, additional "
                "vocalisation, music, ambience or SFX is permitted. No narration. No extra "
                "words. No subtitles or captions. Dialogue language: English. "
                + SEEDANCE_EXACT_AUDIO_DIALOGUE_LOCK)
        else:
            authority = (
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
        sections.append(authority)

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
    reference_summary_lines = []
    team_reference_lines = []
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
        if role == "opening_frame":
            team_reference_lines.append(
                f"{tag} controls only the inherited opening composition and visible "
                "carried state.")
        elif role == "character_identity":
            team_reference_lines.append(
                f"{tag} controls only {role_label}'s identity, proportions, scale and "
                "approved wearable state.")
        elif role == "location":
            team_reference_lines.append(
                f"{tag} controls only the approved scene geography, light, materials "
                "and atmosphere.")
        elif role == "prop":
            team_reference_lines.append(f"{tag} controls only {controls.rstrip('.')}.")
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
            elif role == "continuity_state":
                reference_lines.append(
                    f"{tag} is the preceding approved ending: use visible character, prop and action state only. "
                    "It is not the opening frame or a location plate. Preserve the new opening composition; "
                    "do not morph from this reference or copy its camera framing.")
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
        reference_summary_lines = [line for line in lines if line]
        sections.append("[Multimodal Reference Layer]\n" + "\n".join(
            reference_summary_lines))

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
    goal_header = "[Extension Goal]" if task_mode in {"extend-forward", "extend-backward"} else "[One-Sentence Summary]"
    sections.append(goal_header + "\n" + goal)

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
    if camera_handoff_lines:
        sections.append("[Camera Consciousness]\n" + "\n".join(camera_handoff_lines))
    sections.append("[Crystal Energy Law]\n" + crystal_energy_law())

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
    planned_views = list(shot.get('storyboardInternalShotPlanApproved') or [])
    for index, item in enumerate(internal_shots):
        if index < len(planned_views) and planned_views[index].get('transitionType') in {'opening', 'cut', 'move', 'hold'}:
            item['transitionType'] = planned_views[index]['transitionType']
    if internal_shots and task_mode == 'reference-to-video':
        # A cut from the previous production clip is this clip's opening,
        # not an instruction to cut away from its approved first image.
        internal_shots[0]['transitionType'] = 'opening'
    multi_shot = len(internal_shots) > 1
    # Prefer the approved structured edit scope. Falling back to camera prose made a
    # valid plan such as "three internal shots and two intentional cuts" collapse into
    # continuous phases unless the specialist happened to repeat the words "cut to".
    edit_scope = str(data.get("editScope") or "")
    structured_cut_scope = bool(re.search(
        r"\b(?:\d+\s+)?(?:intentional|motivated|planned)?\s*cuts?\b",
        edit_scope, re.I))
    declared_entries = [item.get('transitionType', 'auto') for item in internal_shots]
    explicit_cut_sequence = structured_cut_scope or any(entry == 'cut' for entry in declared_entries) or any(
        re.search(
            r"\b(?:cut to|hard cut|smash cut|match cut|intercut)\b",
            " ".join(str(value or "") for value in (
                (item.model_dump() if hasattr(item, "model_dump") else dict(item)).get("framingLensAndCamera"),
                (item.model_dump() if hasattr(item, "model_dump") else dict(item)).get("causalAction"),
            )),
            re.I)
        for item in internal_shots)
    if declared_entries and all(entry != 'auto' for entry in declared_entries):
        explicit_cut_sequence = 'cut' in declared_entries
    emitted_holds = set()
    emitted_dialogue = []
    sailing_causality_injected = False
    camera_movement_lines = []
    if internal_shots:
        from studio_storyboard_prompt import view_timings, subjects_for_view, labelled_view, validate_view_bindings
        validate_view_bindings(shot, internal_shots)
        coverage_times = view_timings(shot, len(internal_shots))
        shot_lines = []
        last_gag_view = {str(beat): index for index, view in enumerate(internal_shots)
                         for beat in ((view.model_dump() if hasattr(view, 'model_dump') else view)
                                      .get('gagBeatIds') or [])}
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
            named_speakers = [audio_cues_by_source[int(i)]['speaker']
                              for i in item.get('dialogueLineIndexes') or []
                              if int(i) in audio_cues_by_source]
            coverage_view = next((view for view in (shot.get('directorCard') or {}).get('views', [])
                                  if view.get('viewId') == item.get('sourceViewId')), {})
            subjects = subjects_for_view(collapse_bindings, item, named_speakers,
                                        visible_entities=coverage_view.get('visibleEntities'))
            parts = [f"Camera: {camera}", subjects, f"Action: {action}"]
            entry = item.get('transitionType', 'auto')
            if entry == 'cut':
                parts.insert(1, 'Cut to the planned view. Preserve world positions, eyelines, action phase and story time across this edit.')
            elif entry in {'move', 'hold'}:
                parts.insert(1, 'Continue within the current camera shot; ' + ('hold this motivated view.' if entry == 'hold' else 'make the directed camera move.'))
            if performance:
                parts.append(f"Performance: {performance}")
            setting = str(item.get('compositionLightAndMaterials') or '').strip()
            if setting:
                parts.append('Setting / light / materials: ' + complete(
                    strip_request_parameters(setting), context=f'Internal shot {number} setting'))
            if landing:
                parts.append(f"End state: {landing}")
            directions = list(item.get("dialogueDirections") or [])
            for dialogue_position, line_index in enumerate(
                    item.get("dialogueLineIndexes") or []):
                source_index = int(line_index)
                cue = audio_cues_by_source.get(source_index)
                sfx_cue = sfx_cues_by_source.get(source_index)
                if cue is None and sfx_cue is None:
                    parts.append(
                        "Compiler repair: ignored an invalid dialogue reference "
                        f"to line {line_index}; the approved shot has no such "
                        "dialogue/SFX cue.")
                    continue
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
                if last_gag_view.get(str(beat_id)) != index:
                    continue  # One recovery hold, after the gag's final authored view.
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
            shot_lines.append(labelled_view(number, unit_label, coverage_times[index], parts))
        sides = [str(item).strip() for item in data.get("witnessStagingSides") or []
                 if str(item).strip()]
        if sides:
            shot_lines.append(
                "Witness staging: " + " ".join(sides) +
                " Preserve each witness’s authored attention and reaction. Use stillness only "
                "where directed; do not freeze an active reaction or laughter cue.")
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
        sections.append(section_title + "\n" + "\n\n".join(shot_lines))
        camera_movement_lines = shot_lines

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
        no_dialogue_review = not (shot.get("dialogueLines") or []) and re.search(
            r"no\s+(?:elevenlabs\s+)?(?:spoken\s+)?dialogue|no\s+@Audio1",
            human_review, re.I)
        review_guard = (
            "staged action and camera while preserving canon, the opening frame, no-dialogue audio state and the signed landing state:\n"
            if no_dialogue_review else
            "staged action and camera while preserving canon, the opening frame, exact @Audio1 dialogue and the signed landing state:\n")
        sections.append(
            "[Human Review Correction]\n"
            "This bounded correction is approved Director intent. Integrate it into the "
            + review_guard
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
    # Authored camera choices define the creative coverage, but travel shots still
    # need Seedance-readable traversal grammar. Keep the R9 evidence unless the
    # authored handoff already contains every required travel cue; otherwise long
    # route-sensitive beats can pass creative review while failing the provider
    # prompt audit or drifting in depth/geography.
    if traversal:
        supplement.append(traversal)
    repeated_contacts = cb_engine_rules.repeated_contact_boilerplate(shot, data)
    if repeated_contacts:
        supplement.append(repeated_contacts)
    sailing = cb_engine_rules.sailing_departure_boilerplate(shot, data)
    if sailing and not sailing_causality_injected:
        supplement.append(sailing)
    # Already emitted in Living Performance. A second copy competes with the
    # authored per-view performance without adding any instruction.
    # A short unit's last stage already carries its complete observable handoff. Repeating
    # it in compiler boilerplate spends words without adding creative direction.
    if finish and not short_unit:
        supplement.append(f"Final handoff: {finish}.")

    shot_id = str(shot.get("shotId") or "")
    split_unit = bool(
        (shot.get("sourceShotId") and str(shot.get("sourceShotId")) != shot_id)
        or re.search(r"\.SH\d+[A-Z]$", shot_id))
    if dialogue and exact_audio_only:
        audio = (
            "Preserve @Audio1 unchanged as the complete approved audio bed. During dialogue, "
            "only the active speaker articulates; listeners remain silent and "
            "non-articulating. During approved laughter or giggling in @Audio1, animate only "
            "the characters audibly participating in that exact interval. Do not generate "
            "additional dialogue, laughter, vocalisations, narration, music, ambience or SFX."
        )
    elif dialogue:
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
    if seedance_sfx_cues and not exact_audio_only:
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
    sections.append(_seedance_audio_exclusions_section(
        exact_audio_only=exact_audio_only))
    if any(supplement):
        sections.append("[Global Supplement]\n" + " ".join(supplement))
    prompt = strip_prompt_request_parameters(normalize_reference_grammar(
        "\n\n".join(section for section in sections if section.strip())))
    prompt = adapt_seedance25_prompt(prompt)

    # Seedance's production team expects long exact-audio coverage prompts in a
    # stable review envelope. Keep the typed direction as source of truth, but do
    # not send the legacy stack of overlapping house sections to the provider.
    # The reference contract below is compiled from actual upload order, never
    # copied from an example whose slot numbers may describe a different request.
    if exact_audio_only and explicit_cut_sequence and camera_movement_lines:
        team_authority = (
            "AUDIO-AUTHORITY: @Audio1 is the sole authority for exact words, speaker "
            "identity, voice identity, cadence, emotional delivery, breath, pauses, "
            "dialogue timing, mouth timing, approved laughter and silence. Preserve it "
            "unchanged. No alternative performance is permitted. Only the active speaker "
            "articulates speech; listeners remain silent and closed-mouth and "
            "non-articulating. During approved laughter, animate only the "
            "characters audibly participating in that interval. No narration or improvised "
            "dialogue. No extra words. No extra voices. No additional vocalisations, music, "
            "ambience or SFX. No subtitles or captions. Dialogue language: English. "
            + SEEDANCE_EXACT_AUDIO_DIALOGUE_LOCK
        )
        scenario = [
            goal,
            complete(data.get("dramaticBeat"), context="dramatic beat"),
        ]
        if opening_motion_bridge:
            scenario.append(complete(
                opening_motion_bridge, context="opening motion bridge"))

        core_action = [
            "Performance arc: " + complete(
                data.get("performanceArc"), context="performance arc"),
            "Physical cause and effect: " + complete(
                data.get("physicalCauseAndEffect"),
                context="physical cause and effect"),
        ]
        core_action.extend(action_ownership)
        if traversal:
            core_action.append(traversal)
        if repeated_contacts:
            repeated_context = " ".join(str(value or "") for value in (
                shot.get("purpose"), data.get("physicalCauseAndEffect"), goal))
            if re.search(r"\bpoofs?\b", repeated_context, re.I):
                core_action.append(
                    "Tail-poof escalation: separate the first, second and third poofs "
                    "clearly with a readable reaction between each event. The first poof "
                    "is large, the second is larger than the first, and the third is "
                    "larger than the second and completes the escalation.")
            else:
                core_action.append(repeated_contacts)
        if sailing and not sailing_causality_injected:
            core_action.append(sailing)
        core_action.append(cb_engine_rules.living_performance_boilerplate(shot, data))

        audio_hierarchy = [
            "@Audio1 is the master clock for dialogue, pauses, reactions, approved "
            "laughter and the final landing.",
            "Each approved spoken line appears once in the camera plan below. Bind "
            "that line to its named speaker and its exact interval in @Audio1.",
            audio,
        ]

        landing = []
        if finish:
            landing.append(complete(finish, context="landing state"))
        final_internal_shot = (
            internal_shots[-1].model_dump()
            if hasattr(internal_shots[-1], "model_dump")
            else dict(internal_shots[-1]))
        final_landing = str(final_internal_shot.get("landingImage") or "").strip()
        if final_landing and final_landing.casefold() not in " ".join(landing).casefold():
            landing.append(complete(final_landing, context="final landing image"))
        landing.extend(
            f"Maintain {item}." for item in consistency[:1] if item)

        negative_items = [
            "No replay of completed opening action",
            "no identity blending, duplication or position swapping",
            "no incorrect speaker mouth movement",
            "no extra dialogue, laughter, vocalisations, music, ambience or SFX",
            "no subtitles, captions, text or watermarks",
        ]
        negative_items.extend(
            item.rstrip(".") for item in safeguards[:2] if item)

        style_lines = [f"Style ({style_version}): {style_text}"]
        if geography:
            style_lines.append("Geography: " + " ".join(geography))
        crystal_context = " ".join(str(value or "") for value in (
            shot.get("purpose"), shot.get("action"), goal,
            data.get("physicalCauseAndEffect")))
        if re.search(r"\b(?:crystal|quartz|aquamarine|pendant|crystal energy)\b",
                     crystal_context, re.I):
            style_lines.append(crystal_energy_law())

        compact_references = [
            reference_summary_lines[0] if reference_summary_lines else "",
            reference_summary_lines[1] if len(reference_summary_lines) > 1 else "",
            *team_reference_lines,
            "Keep one instance of each established character. Do not blend identities, "
            "transfer traits or invent entrances; off-crop established characters may "
            "only be revealed by the planned camera move.",
        ]

        team_camera_lines = [*camera_handoff_lines, *camera_movement_lines]
        team_sections = [
            "[GENERATED VIDEO PROMPT]",
            team_authority,
            "Scenario Description:\n" + "\n".join(scenario),
            "Reference Contract:\n" + "\n".join(
                line for line in compact_references if line),
            "Continuity Priority:\n"
            "Prioritise character, prop, scale and spatial consistency over visual "
            "reinterpretation.",
            "Rendering Intent:\nPrioritise stable identity, "
            "readable performance, coherent physical transformation and continuity.",
            "Style Description:\n" + "\n".join(style_lines),
            "Character Description and Core Action:\n" + "\n".join(core_action),
            "Character Reference Authority:\nBind each "
            "character exclusively to the identity reference assigned above.",
            "Audio Hierarchy and Music Policy:\n" + "\n".join(audio_hierarchy),
            "Camera Movement Description:\n" + "\n".join(team_camera_lines),
            "Landing State:\n" + "\n".join(landing),
            "Negative Prompt (Negative):\n" + ". ".join(negative_items) + ".",
        ]
        prompt = adapt_seedance25_prompt("\n\n".join(
            section for section in team_sections if section.strip()))

    # Fully timed shared coverage has one provider-facing shooting script. Keep
    # source feedback, broad scene prose and duplicate coverage text in the review
    # snapshot; do not ask the video model to reconcile a second telling of events.
    structured_storyboard = bool(internal_shots and all(coverage_times))
    if structured_storyboard:
        storyboard_sections = [
            goal_header + '\n' + goal,
            '[Camera Consciousness]\n' + '\n'.join(camera_handoff_lines)
                if camera_handoff_lines else '',
            '[Multimodal Reference Layer]\n' + '\n'.join(reference_summary_lines)
                if reference_summary_lines else '',
            '[Global Settings]\n' + '\n'.join(global_lines),
            '[Opening Motion Bridge]\n' + complete(opening_motion_bridge)
                if opening_motion_bridge else '',
            section_title + '\n' + '\n\n'.join(shot_lines),
            '[ACTION OWNERSHIP]\n' + '\n'.join(action_ownership)
                if action_ownership else '',
            '[ATTRIBUTE OWNERSHIP]\n' + '\n'.join(ownership) if ownership else '',
            '[ENVIRONMENT CONTRACT]\n' + '\n'.join(environment_contract)
                if environment_contract else '',
            '[Scene Continuity State]\n' + '\n'.join(scene_state_lines)
                if scene_state_lines else '',
            '[Dialogue Authority]\n' + authority if authority else '',
            '[Audio]\n' + audio,
            _seedance_audio_exclusions_section(exact_audio_only=exact_audio_only),
            '[Global Supplement]\n' + ' '.join(dict.fromkeys(supplement))
                if any(supplement) else '',
        ]
        # Energy effects are not implied merely by an IP name or a crystal in the
        # environment. Emit the law when the authored action actually uses one.
        effect_context = ' '.join(str(data.get(k) or '') for k in (
            'physicalCauseAndEffect', 'generationGoal', 'actionOwnership'))
        if re.search(r'\b(?:crystal energy|energy pulse|crystal glow|crystal activates)\b',
                     effect_context, re.I):
            storyboard_sections.append('[Crystal Energy Law]\n' + crystal_energy_law())
        prompt = adapt_seedance25_prompt(strip_prompt_request_parameters(
            normalize_reference_grammar('\n\n'.join(x for x in storyboard_sections if x))))

    timeline = data.get("timeline") or []
    if timeline:
        report = validate_timeline(timeline, data.get("durationSec") or shot.get("durationSec"))
        if not report["ready"]:
            raise ValueError("; ".join(report["errors"]))
        prompt += "\n\n[CHANNEL TIMING]\n" + "\n".join(
            f"{item['channel']}: {float(item['startSec']):g} seconds until "
            f"{float(item['endSec']):g} seconds: {item['event']}" for item in timeline)
    handoff = shot_handoff_instruction(shot)
    if handoff:
        prompt += "\n\n[EDITORIAL HANDOFF]\n" + handoff
    prompt += "\n\n[SOUND HANDOFF]\n" + sound_instruction(
        data.get("soundHandoff"), continuation=split_unit or (shot.get("shotTransition") or {}).get("type") == "continuation",
        exact_audio=exact_audio_only)
    # Missing action must be repaired in the typed sequence, never appended as a
    # competing instruction after the actual camera/performance plan.
    missing_events = [event for event in animation_locked_visual_events(shot)
                      if event['primaryEvent'] and
                      visual_event_text(event['primaryEvent']) not in visual_event_text(prompt)]
    bound_stages = {number for view in (data.get('shotPlan') or [])
                    for number in view.get('sourceStageNumbers', [])}
    expected_stages = {event['stageNumber'] for event in animation_locked_visual_events(shot)}
    if bound_stages - expected_stages:
        raise ValueError("Animation view references an unknown approved stage")
    missing_events = [event for event in missing_events if event['stageNumber'] not in bound_stages]
    if missing_events:
        raise ValueError("Animation direction needs reconciliation in its main sequence; "
                         "missing approved stages: " + ", ".join(
                             str(event['stageNumber']) for event in missing_events))
    from studio_coverage import staging_instruction
    staging = staging_instruction(shot)
    if staging and not structured_storyboard:
        prompt += '\n\n[COVERAGE STAGING]\n' + staging
    prompt = _directed_nonverbal_performance(prompt, timeline, exact_audio_only=exact_audio_only,
                                           audio_contract=str(data.get('audioContract') or ''))
    from studio_creative_authority import compile_instructions, listener_scope
    prompt = compile_instructions(listener_scope(prompt), shot, "watch")
    prompt_sections(prompt)
    for line in prompt.splitlines():
        if re.match(r"^(?:Initial state|Continue from the previous stage|Cause|Physics|Emotion/Camera Analysis|Audio cues|Dialogue performance|End state):", line):
            emission.require_complete_sentence(line.split(":", 1)[1], context=line.split(":", 1)[0])
    dialogue_check = emission.validate_dialogue_synthesis(prompt, dialogue)
    if not dialogue_check["ready"]:
        raise ValueError("dialogue synthesis contract failed: " +
                         "; ".join(dialogue_check["errors"]))
    prompt = studio_prompt_aliases.protect_honeycomb_aliases(prompt, shot)
    from studio_prompt_order import compile_order
    from studio_watch_structure import apply as structure_watch
    return compile_order(structure_watch(compile_order(prompt, data), shot, data), data)


def _animation_response_schema(shot):
    """Constrain the worker to the coverage it must preserve before generation.

    A broad 1-6 array permits a valid JSON response that silently merges approved
    views. Bind both schema limits to the source count; semantic validators still
    check the resulting acting, events and timings as usual.
    """
    views = shot.get('storyboardInternalShotPlanApproved') or []
    if not views:
        return AnimationDirection
    count = len(views)
    if not 1 <= count <= 6:
        raise ValueError('Approved coverage exceeds the animation unit capacity of six views')
    ids = tuple(v.get('viewId') for v in views)
    bound_view = InternalShotDirection
    if all(ids) and len(set(ids)) == len(ids):
        bound_view = create_model('SourceBoundAnimationView', __base__=InternalShotDirection,
            sourceViewId=(Literal[ids], Field(description='Copy this exact approved viewId. Preserve view order and enact its camera and action; no placeholder entries.')))
    return create_model(
        'AnimationDirectionWithApprovedCoverage', __base__=AnimationDirection,
        shotPlan=(List[bound_view], Field(
            min_length=count, max_length=count,
            description='Exactly one entry per approved view, in the same order, '
                        'including the final landing. Do not merge or add views.')))


def prepare_animation(context, images, *, log=print):
    """One bounded repair for source-contract failures, never a media retry."""
    try:
        return _prepare_animation_once(context, images, log=log)
    except (RuntimeError, ValueError) as exc:
        if not str(exc).startswith(('Animation Director changed', 'Animation Director added',
                                     'Animation Director weakened', 'Animation coverage must',
                                     'Animation view ')):
            raise
        repaired_context = dict(context)
        views = (context.get('shot') or {}).get('storyboardInternalShotPlanApproved') or []
        repaired_context['animationContractRepair'] = {
            'failure': str(exc), 'requiredShotPlanCount': len(views),
            'orderedViewIds': [v.get('viewId') for v in views],
            'instruction': 'Repair this failed source contract. Return one shotPlan entry per approved view, '
                           'in order, including the final landing. Preserve every approved stage, event, '
                           'audio line and measured timing. The current Director Card supplies executable '
                           'view timing where legacy ranges say approximate. Do not merge views.'}
        log('ANIMATION DIRECTION — repairing the named source-contract mismatch once; no render submitted')
        return _prepare_animation_once(repaired_context, images, log=log)


def _animation_current_context(context):
    """Keep old HEAR visual blocking out of a newly directed WATCH revision.

    Work on a copy: approved audio, exact words, timing and vocal direction remain
    untouched. Old body staging cannot overrule the current visual correction.
    """
    from copy import deepcopy
    current = deepcopy(context)
    shot = current.get('shot') or {}
    if shot.get('watchDirectorFeedbackApproved'):
        for brief in shot.get('voiceDirectorBrief') or []:
            brief.pop('physicalActionRelationship', None)
        current['visualBlockingAuthority'] = (
            'Use current WATCH coverage and review feedback for body action. The '
            'approved audio asset, exact dialogue and measured timing remain unchanged; '
            'historical HEAR physical blocking is not a current movement instruction.')
    return current


def _prepare_animation_once(context, images, *, log=print):
    context = _animation_current_context(context)
    from studio_director_card import stage_decisions
    context['directorDecisions'] = stage_decisions(context.get('shot') or context, 'watch')
    from studio_coverage import unit_board
    context['coverageBoard'] = unit_board(context.get('shot') or context)
    from cb_learning_context import brief
    context.setdefault("reviewObservations", brief(context))
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
    result = cb_llm.structured_with_repair(
        _system("animation",
                "Turn the approved dramatic beat into one playable Seedance generation unit. "
                "The first attached image is the approved opening frame; remaining attachments "
                "follow the exact reference order in the context. Continuous relay may use one "
                "shot; use the authored scene coverage, with each view serving a clean action, "
                "thought, relationship or reaction. There is no compulsory cut count. "
                "Scope means the current production unit, not a single camera view. "
                "Render its included coverage views in authored order, with explicit view boundaries. "
                "A next-view action belongs here only when that view is included in this unit. "
                "Match opening posture and eye state to the actual approved opening; do not invent "
                "an eyes-opening action or weather escalation from a generic reaction. "
                "Keep the last included view's landing, and place every approved dialogue occurrence "
                "at its measured Audio1 timing; a silent earlier view does not make the whole unit silent. "
                "Write complete semantic sentences; never truncate camera or performance clauses.", standard_version),
        "APPROVED SHOT, VOICE DIRECTION AND ORDERED ATTACHMENTS:\n" + _creative_context(context) +
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
        "primaryEvent verbatim into the matching stagePlan.primaryEvent AND the appropriate "
        "shotPlan.causalAction (concatenate events in story order when a view carries several). "
        "Set sourceStageNumbers on every view to the approved stage numbers it enacts. "
        "These links provide traceability, not permission to omit or contradict the actions. "
        "For each character nonverbal SFX timeline cue, set performer to its exact character "
        "and visibility to visible or deliberately offscreen. A visible physical gag needs "
        "a shotPlan view showing its face/body at readable scale. Never transfer a laugh "
        "to the character speaking Audio1. Distinguish waking sounds from laughter and "
        "give each its actual interval, not a blanket full-shot laugh. "
        "The compiler ignores providerPrompt; do not place essential action only there. Into that stage's "
        "Action/Expression line in providerPrompt. Copy each observableEndState verbatim into "
        "the matching stagePlan.observableEndState. Never move an event to another stage.\n\n"
        "LOCKED VISUAL EVENT CONTRACT (spoken words already removed):\n" +
        _j(locked_visual_events) + "\n\n"
        "CINEMATOGRAPHY HANDOFF CONTRACT:\n"
        "When currentCinematographyDirection contains cameraConsciousness, copy those "
        "decisions into cinematographyHandoff without weakening or replacing them. Make "
        "shotPlan, stagePlan and the compiled provider direction enact the same dramatic "
        "owner, emotional action, camera state, movement trigger/finish, focus plan and "
        "exit condition. A controlled hold is a valid camera decision; never add movement "
        "for decoration.\n\n"
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
        "Return taskMode='reference-to-video', the exact durationSec, pacingMode, generationGoal, deliveryPlan, creativeTranslation, cinematographyHandoff, audienceBefore, "
        "audienceAfter, beatOwner, performanceFreedom, landingBreath, directionDensity, a "
        "numbered directing plan preserving every approved sourceViewId in the same order; "
        "each view must enact that source view's purpose, action and camera, never fill a "
        "required view with a placeholder or merge its action into another view. Without "
        "approved coverage, choose the views needed for the story. Return typed timingBeats, canonical witnessStagingSides "
        "for two-character gags, and a consecutive stagePlan in which every "
        "stage keeps its approved beatIds, has one primary event, an emotionOrCameraAnalysis, "
        "a visible cause inherited from the prior state, and an observable end state, "
        "plus geography copied from the approved scene geography ledger, "
        "the separate reference "
        "contract, consistencyContract, audioContract, the exact continuity landing, no more "
        "than three surgical safeguards, and one paste-ready Seedance shooting script in "
        "providerPrompt. Use pacingMode='timestamp' whenever stage clocks are supplied "
        "and for all 16-30 second units. Short units without stage clocks may use "
        "pacingMode='storyline'; timestamp mode requires ordered startSec "
        "and endSec values on every stage as broad budgets, not frame-accurate commands; "
        "storyline mode omits both. "
        "Emit every scripted line exactly once inside the stage that owns it, attributed to the "
        "named speaker with the approved delivery. Protect a full-beat pose hold after a line when "
        "the story needs its recognition, reaction or comic button to register. Suppress that hold "
        "when the approved action begins immediately with or after the line, such as a launch, impact "
        "or interruption; name that immediate action in the same stage instead. In a dialogue-rich "
        "shot, at least one non-immediate recognition or reaction line must retain readable air. "
        "When timingBeats contains travel, dodge, impact, load_release, tumble "
        "or aerial action, preserve the approved coverage: choose views for one clean motion or "
        "story idea per shot. Place any cut deliberately at a change of story job or maximum "
        "stored energy; a continuous camera intention may connect those phases but may not "
        "lose their readable cause and consequence. An intentional continuous view is valid. "
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
        "dialogue cue. Populate soundHandoff with a scene-aware entrance, exit and carried sound, "
        "respecting the selected audio contract. Preserve Seedance's permitted timed score and "
        "effects; splitting a unit must not reset its music or imply replacement in post. "
        "The prompt must begin from the approved opening state and end on a usable "
        "held handoff frame, with causal "
        "physical action, observable performance, motivated camera, readable composition, and "
        "established light/material behaviour. Preserve all direction required to deliver "
        "the approved beat and emotional outcome; never shorten it to meet a word count. The "
        "compiler adds the canonical audio and continuity shell before validation: "
        "each instruction appears once, reference bindings stay one concise line each, and stage "
        "direction states only the action, visible performance, camera purpose and end state. "
        "It should feel like confident direction to an "
        "exceptional actor and camera crew, not an animation checklist.",
        _animation_response_schema(shot), label="department_animation", log=log, images=images)

    # Cinematography is an approved upstream decision. Preserve it as typed data so
    # the deterministic Seedance compiler carries the same camera owner, movement and
    # exit condition even when the Animation specialist phrases its own plan differently.
    approved_cinematography = context.get("currentCinematographyDirection") or {}
    if isinstance(approved_cinematography, dict):
        approved_cinematography = approved_cinematography.get("output") or approved_cinematography
    if isinstance(approved_cinematography, dict):
        authored_camera = approved_cinematography.get("cameraConsciousness") or {}
        if any(str(value or "").strip() for value in authored_camera.values()):
            result.cinematographyHandoff = CameraConsciousness.model_validate(authored_camera)

    result = enforce_aerial_camera_contract(result)
    result = carry_approved_gag_clock_text(shot, result)
    result = carry_approved_dialogue_ownership(shot, result)

    # The closing handoff is approved upstream and has no creative latitude.
    # Restore it deterministically instead of rejecting a harmless model paraphrase.
    approved_handoff = str(
        shot.get("visualPayoff") or
        ((shot.get("storyboardStagePlanApproved") or [{}])[-1].get("observableEndState"))
        or "").strip()
    if approved_handoff:
        result.creativeTranslation.generationDesign.handoffState = approved_handoff

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
    approved_stages = _coerce_storyboard_stage_plan(shot)
    if approved_stages and len(result.stagePlan) == len(approved_stages):
        for actual_stage, approved_stage in zip(result.stagePlan, approved_stages):
            approved_beat_ids = list(approved_stage.get("beatIds") or [])
            if approved_beat_ids:
                actual_stage.beatIds = approved_beat_ids
    result.providerPrompt = compile_animation_provider_prompt(shot, result)
    approved_stages = _coerce_storyboard_stage_plan(shot)
    if approved_stages:
        expected = [list(stage.get("beatIds") or []) for stage in approved_stages]
        actual = [list(stage.beatIds) for stage in result.stagePlan]
        if any(expected) and actual != expected:
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
    from studio_director_card import REVIEW_CRITERIA
    context = {**context, 'creativeReviewCriteria': REVIEW_CRITERIA,
               'reviewEvidenceScope': {'method': 'sampled still images', 'imageCount': len(images),
                                      'audio': 'not supplied to this reviewer', 'continuousMotion': 'unverified',
                                      'adjoiningPictureAndSound': 'unverified'}}
    return cb_llm.structured(
        _system("post" if artifact_type == "final" else "review",
                "Run dailies review on visible evidence. This call receives still images, not video or audio. "
                "Do not claim to have listened, verified lip sync, assessed continuous movement or auditioned an edit. "
                "Leave those dimensions unverified and keep inference separate from observations. Findings are advice for Julian, "
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
            "and no forbidden props, duplicate subjects, duplicate tracked story objects, text, logo or watermark. Score 2 only "
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
