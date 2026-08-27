#!/usr/bin/env python3
"""cb_creative.py — THE CRYSTAL BEARS CREATIVE ROOM (process v2, 2026-07-17).

The 2026-07-17 freeze was superseded by Julian's 2026-07-30 architecture rebuild: Gate 3
now owns typed emotion, comedy and optional crystal-power intent; Gate 4 owns typed
cinematography; Gate 5 emits typed character-specific performance and physical-comedy
contracts; and ProductionDetail owns typed continuity boundaries plus numeric
per-occurrence dialogue windows. Historical prose remains review context but is no longer
executable.

Process v1 was rejected by Julian as a PROCESS-LEVEL failure (EX-005 in the exemplar
library): the Cinematographer entered after the dramatic approach was already selected;
no governing audience-experience/visual-grammar decision existed; fixed lanes and
action->consequence->reaction coverage returned; the camera watched from safety; and a
mandatory 28-field shot card encouraged over-direction. v2 replaces the process, not the
artifact — the rejected Scene 1 package is archived unchanged and feeds the room as a
rejected exemplar; no desired replacement shot was added to canon.

THE v2 GATES
  Gate 0 — Canon and creative readiness: confirm canon/script/exemplars; if performance
           fields essential to the participating characters are unresolved, produce a
           PROPOSED canon completion for human approval (the run itself directs on
           established canon only — psychology is never invented invisibly).
  Gate 1 — Whole-scene creative treatments: Director + Cinematographer JOINTLY author
           three materially different complete directing concepts; the Cinematographer
           is a co-author who challenges safe, static or conventional imagery.
  Gate 2 — Showrunner treatment selection (before any beat exists), rejecting anything
           that depends on fixed lanes, habitual coverage, safe cameras, mechanical shot
           counts or mere illustration.
  Gate 3 — Beat architecture inside the selected treatment.
  Gate 4 — Director/Cinematographer shot conference: a shot exists only for a meaningful
           change; every transition carries its cut-vs-continuous justification; no
           camera behaviour is automatically preferred; no permanent screen sides;
           reaction shots only when the reaction changes meaning.
  Gate 5 — Performance and voice synthesis (body first, then voice, reconciled).
  Gate 6 — ADVERSARIAL Showrunner review: actively attempts to reject; compares against
           the SELECTED TREATMENT (internal consistency alone is not enough); on failure
           returns to Gate 3 or 4 — never patches shot wording; ≤2 complete creative
           revisions, then human escalation.

THE SPLIT CONTRACT: a lean Creative Storyboard Card carries the idea; Production Detail
(continuity, dialogue timing, reference roles, keyframe need, ≤3 protections) is added
ONLY after the creative sequence passes. Detail exists because it serves the idea, never
because a schema contains a box.

This module NEVER calls a media provider, never compiles a Seedance prompt and never
touches a spend token. Its only external calls are OpenAI text calls via cb_llm.

    python3 cb_creative.py envelope  [episode]
    python3 cb_creative.py vision    [episode]
    python3 cb_creative.py scene <n> [episode] [--brief "audience-experience ambition"]
    python3 cb_creative.py migrate   [episode]
"""
import datetime
import hashlib
import json
import os
import pathlib
import re
import sys
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.json_schema import SkipJsonSchema

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import cb_llm
import cb_canon
import cb_departments
import cb_engine
import cb_lineage
import cb_scripts
import cb_unit_packing

CREATIVE = ROOT / "shows" / "crystal-bears" / "creative"
OUT = ROOT / "cb-output" / "creative"
CANON_VERSION = "1.0"
ENGINE_VERSION = "creative-room-2.2 (2026-08-01, story-to-screen supervision contracts)"
CREATIVE_DIRECTING_STANDARD_VERSION = 4
UNIT_PACKING_CONTRACT_VERSION = 1
MAX_INTERNAL_REVISIONS = 2
SCRIPT_STORE = cb_scripts.ScriptStore(ROOT)


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _md5(path):
    return hashlib.md5(pathlib.Path(path).read_bytes()).hexdigest()


def _norm(s):
    return re.sub(r"[^a-z0-9']+", " ", (s or "").lower().replace("’", "'")).strip()


# ─────────────────────────────────────────────────────────────────────────────────────────
# THE v2 STORYBOARD DATA CONTRACT — creative layer lean, production detail separate
# ─────────────────────────────────────────────────────────────────────────────────────────
class Provenance(BaseModel):
    role: str
    model: str = ""
    promptVersion: str = ENGINE_VERSION
    canonVersion: str = CANON_VERSION
    at: str = ""
    humanRevision: Optional[str] = None


class SceneTreatment(BaseModel):
    """One COMPLETE whole-scene directing concept (Gate 1) — never a coverage variation."""
    name: str
    audienceExperience: str
    emotionalPointOfView: str
    comicOrDramaticMechanism: str
    characterPerformanceStrategy: str
    visualGrammar: str
    cameraCharacterRelationship: str
    movementVersusStillness: str
    depthAndEnvironment: str
    rhythmAndEscalation: str
    cutPhilosophy: str
    openingImage: str
    closingImage: str
    cinematographerChallenge: str      # where the camera thinking pushed/dared the dramatic idea


class TreatmentSet(BaseModel):
    treatments: List[SceneTreatment] = Field(min_length=3, max_length=3)


class TreatmentSelection(BaseModel):
    """Gate 2 — the Showrunner's decision BEFORE any beat exists."""
    selectedTreatment: str                       # a treatment name, or a combined statement
    combinedFrom: List[str] = Field(default_factory=list)
    governingAudienceExperience: str             # the ONE experience the scene now serves
    rationale: str
    rejectionChecks: str                         # how each candidate fared against the
    #                                              forbidden dependencies (fixed lanes, habitual
    #                                              coverage, safe cameras, mechanical counts...)


class SceneEmotionalNorthStar(BaseModel):
    """The direct human truth every department must express through this scene."""
    model_config = ConfigDict(extra="forbid")

    surfaceStory: str = Field(min_length=1)
    universalTruth: str = Field(min_length=1)
    childClearWant: str = Field(min_length=1)
    emotionalNeed: str = Field(min_length=1)
    falseBeliefUnderPressure: str = Field(min_length=1)
    relationshipEngine: str = Field(min_length=1)
    ordinaryLifeTruth: str = Field(min_length=1)
    sceneTurn: str = Field(min_length=1)
    audienceJourney: List[str] = Field(min_length=3, max_length=8)
    finalAfterFeeling: str = Field(min_length=1)
    dialogueSubtractionOpportunity: str = Field(min_length=1)
    environmentPressure: str = Field(min_length=1)


class CharacterSceneTransformation(BaseModel):
    """A playable belief-to-action change, not invented psychology or a stated lesson."""
    model_config = ConfigDict(extra="forbid")

    emotionalOwner: str = Field(min_length=1)
    entryBelief: str = Field(min_length=1)
    entryFeeling: str = Field(min_length=1)
    pressureBehaviour: str = Field(min_length=1)
    costlyChoice: str = Field(min_length=1)
    exitBelief: str = Field(min_length=1)
    exitAction: str = Field(min_length=1)


class TapestryContract(BaseModel):
    """How image, environment and sound echo one emotional argument without ornament."""
    model_config = ConfigDict(extra="forbid")

    physicalMotif: str = Field(min_length=1)
    sonicMotif: str = Field(min_length=1)
    colourAndLightProgression: str = Field(min_length=1)
    thematicVisualContrast: str = Field(min_length=1)
    openingClosingRhyme: str = Field(min_length=1)


class EmotionalStoryToScreenContract(BaseModel):
    """Upstream Heart Director contract consumed by the existing Gate 1-6 room."""
    model_config = ConfigDict(extra="forbid")

    northStar: SceneEmotionalNorthStar
    transformation: CharacterSceneTransformation
    tapestry: TapestryContract


class DialogueOccurrence(BaseModel):
    """One immutable spoken occurrence, distinct even when its words repeat exactly."""
    dialogueOccurrenceId: str = Field(min_length=1)
    sourceEventId: str = Field(min_length=1)
    sourceEventIndex: int = Field(ge=0)
    beatId: str = Field(min_length=1)
    sourceBeatId: str = Field(min_length=1)
    speaker: str = Field(min_length=1)
    exactText: str = Field(min_length=1)


class BeatEmotionContract(BaseModel):
    """The emotional event the audience experiences, expressed without invented psychology."""
    model_config = ConfigDict(extra="forbid")

    owner: str = Field(min_length=1)
    entryState: str = Field(min_length=1)
    pressure: str = Field(min_length=1)
    choiceOrRealisation: str = Field(min_length=1)
    exitState: str = Field(min_length=1)
    observableEvidence: str = Field(min_length=1)
    audienceAlignment: Literal["ahead", "with", "behind"]
    heldAfterBeat: str = Field(min_length=1)


class PhysicalComedyStaging(BaseModel):
    """Readable physics for the one shot that carries a BIG physical gag."""
    model_config = ConfigDict(extra="forbid")

    staysVisible: str = Field(min_length=1)
    contactAndWeight: str = Field(min_length=1)
    payoffShape: str = Field(min_length=1)
    prohibitedStaging: List[str] = Field(default_factory=list, max_length=3)


class BeatComedyContract(BaseModel):
    """Character-led comic structure. NONE is an explicit rhythm decision, not an omission."""
    model_config = ConfigDict(extra="forbid")

    mode: Literal["NONE", "SMALL", "BIG"]
    mechanism: str = Field(min_length=1)
    comicOwner: Optional[str] = None
    straightCharacter: Optional[str] = None
    setup: str = ""
    expectation: str = ""
    disruption: str = ""
    button: str = ""
    hold: str = ""
    physicalStaging: Optional[PhysicalComedyStaging] = None

    @model_validator(mode="after")
    def active_comedy_has_a_playable_shape(self):
        if self.mode != "NONE":
            required = (self.comicOwner, self.setup, self.expectation,
                        self.disruption, self.button, self.hold)
            if any(not str(value or "").strip() for value in required):
                raise ValueError(
                    "SMALL/BIG comedy needs an owner, setup, expectation, disruption, "
                    "button and hold")
        if self.mode == "BIG" and self.physicalStaging is None:
            raise ValueError("BIG comedy needs a physicalStaging contract")
        if self.mode == "NONE" and self.physicalStaging is not None:
            raise ValueError("NONE comedy cannot carry physicalStaging")
        return self


class CrystalPowerMoment(BaseModel):
    """A story-level power event. Exact spoken words remain owned by dialogue occurrences."""
    model_config = ConfigDict(extra="forbid")

    bearer: str = Field(min_length=1)
    canonRule: str = Field(min_length=1)
    trigger: str = Field(min_length=1)
    exactCallOccurrenceId: Optional[str] = None
    emotionalMeaning: str = Field(min_length=1)
    visibleManifestation: str = Field(min_length=1)
    costOrConsequence: str = Field(min_length=1)
    continuityResult: str = Field(min_length=1)
    prohibitedInventions: List[str] = Field(default_factory=list, max_length=3)


class Beat(BaseModel):
    """Gate 3 — beat architecture INSIDE the selected treatment. Beats do not
    automatically become separate shots."""
    beatId: str
    sceneId: str
    sourceScript: str
    exactDialogue: List[str]
    sourceBeatId: str = ""
    sourceEventIds: List[str] = Field(default_factory=list)
    # Source lineage is restored mechanically from the immutable beat package after the
    # creative pass. Keeping these free-form dictionaries out of the provider response
    # schema prevents OpenAI strict structured outputs from treating provenance as an
    # authorable object while preserving it on the runtime model.
    sourceEventRange: SkipJsonSchema[Dict] = Field(default_factory=dict)
    sourceEventSignature: SkipJsonSchema[Dict] = Field(default_factory=dict)
    dialogueOccurrences: List[DialogueOccurrence] = Field(default_factory=list)
    participatingCharacters: List[str]
    whatChanges: str
    whoDrives: str
    audienceAnticipation: str
    actionOrChoice: str
    consequence: str
    emotionalOrComicHandover: str
    emotionContract: Optional[BeatEmotionContract] = None
    comedyContract: Optional[BeatComedyContract] = None
    powerMoment: Optional[CrystalPowerMoment] = None
    approvalState: str = "draft"


class PerformancePhase(BaseModel):
    """One observable phase of a shot's performance, in causal screen order."""
    model_config = ConfigDict(extra="forbid")

    phase: Literal["anticipation", "action", "reaction", "settle"]
    performer: str = Field(min_length=1)
    observableAction: str = Field(min_length=1)


class CharacterPerformanceTruth(BaseModel):
    """Why this performance can belong only to this locked character."""
    model_config = ConfigDict(extra="forbid")

    character: str = Field(min_length=1)
    canonTrait: str = Field(min_length=1)
    playableWant: str = Field(min_length=1)
    pressureResponse: str = Field(min_length=1)
    observableSignature: str = Field(min_length=1)
    substitutionTest: str = Field(min_length=1)


class ShotPerformanceContract(BaseModel):
    """Gate-5 performance truth. It gives animation a playable shape without turning
    acting into frame-by-frame choreography. playableIntention remains review context;
    the observable fields are the only parts compiled for a visual provider."""
    model_config = ConfigDict(extra="forbid")

    beatOwner: str = Field(min_length=1)
    playableIntention: str = Field(min_length=1)
    phases: List[PerformancePhase] = Field(min_length=1, max_length=4)
    physicalCauseAndEffect: str = Field(min_length=1)
    visibleEmotionalTurn: str = Field(min_length=1)
    requiredLanding: str = Field(min_length=1)
    performanceFreedom: str = Field(min_length=1)
    characterTruths: List[CharacterPerformanceTruth] = Field(
        default_factory=list, max_length=4)
    # Gate 3 owns the canonical physical-comedy contract. This singular value is only a
    # compatibility mirror for Gate 5's beatOwner; handover compiles every BIG beat's exact
    # staging directly from the beat contract into its packed production unit.
    comedyStaging: SkipJsonSchema[Optional[PhysicalComedyStaging]] = None

    @model_validator(mode="after")
    def phases_are_unique_and_ordered(self):
        order = {"anticipation": 0, "action": 1, "reaction": 2, "settle": 3}
        names = [phase.phase for phase in self.phases]
        if len(names) != len(set(names)):
            raise ValueError("performance phases must be unique")
        if names != sorted(names, key=order.__getitem__):
            raise ValueError("performance phases must follow anticipation/action/reaction/settle order")
        return self


class ShotCinematographyContract(BaseModel):
    """The story reason and observable camera grammar of one production unit."""
    model_config = ConfigDict(extra="forbid")

    storyPointOfView: str = Field(min_length=1)
    emotionalDistanceStart: str = ""
    emotionalDistanceEnd: str = ""
    revealStrategy: str = ""
    shotScale: str = Field(min_length=1)
    lensIntent: str = Field(min_length=1)
    cameraHeight: str = Field(min_length=1)
    composition: str = Field(min_length=1)
    depthStrategy: str = Field(min_length=1)
    cameraBehavior: str = Field(min_length=1)
    focusStrategy: str = Field(min_length=1)
    lightingFunction: str = Field(min_length=1)
    paletteFunction: str = Field(min_length=1)
    performanceVisibility: str = ""
    editorialPurpose: str = ""
    memorableLandingImage: str = ""
    providerInstruction: str = Field(min_length=1, max_length=240)


class ShotPerformanceBudget(BaseModel):
    """Director's honest capacity decision before a provider unit is approved."""
    model_config = ConfigDict(extra="forbid")

    emotionalTurnCount: int = Field(ge=0, le=2)
    propStateChangeCount: int = Field(ge=0, le=3)
    dialogueHeavy: bool
    silentActingReserveSec: float = Field(ge=1.0, le=12.0)
    landingHoldSec: float = Field(ge=0.8, le=4.0)
    minimumHonestDurationSec: float = Field(ge=4.0, le=45.0)
    decision: Literal["single-unit", "split-before-generation"]
    rationale: str = Field(min_length=1)


class ShotStoryIntent(BaseModel):
    """The meaning carried by one shot before camera and provider instructions are authored."""
    model_config = ConfigDict(extra="forbid")

    narrativeFunction: str = Field(min_length=1)
    primaryAudienceFeeling: str = Field(min_length=1)
    secondaryAudienceFeeling: str = Field(min_length=1)
    outerAction: str = Field(min_length=1)
    innerAction: str = Field(min_length=1)
    performanceDirection: str = Field(min_length=1)
    mutedRead: str = Field(min_length=1)
    environmentPressure: str = Field(min_length=1)
    soundStory: str = Field(min_length=1)
    motifUse: str = Field(min_length=1)
    thoughtChangeAndCut: str = Field(min_length=1)


class StoryboardStage(BaseModel):
    """One causal story step inside a Seedance production unit."""
    model_config = ConfigDict(extra="forbid")

    stageNumber: int = Field(ge=1, le=5)
    beatIds: List[str] = Field(min_length=1)
    purpose: str = Field(min_length=1)
    primaryEvent: str = Field(
        min_length=1,
        description="One primary visible state change, expressed as cause and effect.")
    emotionalOrComicTurn: str = Field(min_length=1)
    cameraAndTransition: str = Field(
        min_length=1,
        description="The motivated camera behaviour or cut that lets this stage land.")
    observableEndState: str = Field(
        min_length=1,
        description="The directly visible state that proves this stage has completed.")


class StoryboardInternalShot(BaseModel):
    """One motivated camera view inside a single Seedance generation request."""
    model_config = ConfigDict(extra="forbid")

    shotNumber: int = Field(ge=1, le=6)
    purpose: str = Field(min_length=1)
    framingAndCamera: str = Field(min_length=1)
    storyAction: str = Field(min_length=1)
    performanceFocus: str = Field(min_length=1)
    landingImage: str = Field(min_length=1)
    cutReason: str = Field(
        min_length=1,
        description="Why this view or internal cut is stronger than remaining on the prior view.")


class StoryboardCard(BaseModel):
    """Gate 4's owned storyboard fields. Performance is intentionally absent so the
    shot conference cannot author or invalidate the later Director performance pass."""
    shotId: str
    beatIds: List[str]                           # a continuous chain may span beats
    targetDurationSec: Optional[int] = Field(
        default=None, ge=4, le=30,
        description="The natural approved story duration for this Seedance production unit. "
                    "It is never padded to 30 seconds or compressed merely to fit a model limit.")
    stagePlan: List[StoryboardStage] = Field(default_factory=list, max_length=5)
    internalShotPlan: List[StoryboardInternalShot] = Field(default_factory=list, max_length=6)
    purpose: str
    audienceExperience: str
    openingImage: str = Field(description=(
        "2026-07-17 correction (Julian's Gate-B source-contract ruling, simplified same day "
        "after the first version read as a mandatory camera checklist): a RENDERABLE "
        "DESCRIPTION OF THE LITERAL FIRST FRAME that makes the selected treatment visually "
        "legible. Include only the viewpoint, spatial relationships, depth or action "
        "direction that MATERIALLY DEFINES that image — never all four as a required list, "
        "never a checklist. This field alone controls the compiled keyframe's composition; "
        "no compiler-level framing instruction and no reference image may override it."))
    principalPerformance: str
    cameraRelationship: str                      # lead/pursue/lag/lose/rediscover/anticipate/
    #                                              arrive-late/still/abandon-for-another — whatever
    #                                              the idea needs; nothing automatically preferred
    physicalOrEmotionalChange: str
    closingImage: str
    transitionType: Literal["CONTINUOUS", "PLANNED_CUT"]
    transitionReason: str                        # cut: why continuous would be weaker;
    #                                              continuous: why a cut would weaken it
    providerBoundaryReason: Literal[
        "scene_end", "duration_limit", "location_or_time_change",
        "reference_regime_change", "continuity_reset", "dramatic_editorial_break",
        "complexity_protection"]
    providerBoundaryExplanation: str = Field(
        min_length=1,
        description="Why the next material must start a new Seedance request instead of "
                    "remaining inside this unit as a motivated internal cut.")
    cinematographyContract: Optional[ShotCinematographyContract] = None
    performanceBudget: Optional[ShotPerformanceBudget] = None
    storyIntent: Optional[ShotStoryIntent] = None
    approvalState: str = "draft"

    @model_validator(mode="after")
    def production_unit_structure_is_ordered(self):
        stage_numbers = [stage.stageNumber for stage in self.stagePlan]
        if stage_numbers and stage_numbers != list(range(1, len(stage_numbers) + 1)):
            raise ValueError("storyboard stages must be consecutive and begin at 1")
        internal_numbers = [shot.shotNumber for shot in self.internalShotPlan]
        if internal_numbers and internal_numbers != list(range(1, len(internal_numbers) + 1)):
            raise ValueError("internal shots must be consecutive and begin at 1")
        owned = set(self.beatIds)
        for stage in self.stagePlan:
            if not set(stage.beatIds).issubset(owned):
                raise ValueError(
                    f"stage {stage.stageNumber} names a beat outside this production unit")
        if self.targetDurationSec and self.targetDurationSec > 15 and len(self.stagePlan) < 2:
            raise ValueError("production units over 15 seconds require at least two story stages")
        if self.performanceBudget:
            if self.performanceBudget.decision != "single-unit":
                raise ValueError("split-before-generation is not an approvable production unit")
            if (self.targetDurationSec and
                    self.performanceBudget.minimumHonestDurationSec > self.targetDurationSec):
                raise ValueError(
                    "performance budget exceeds the production-unit duration; split the unit")
        return self


class CreativeShotCard(StoryboardCard):
    """The runtime card after Gate 5 enriches the locked storyboard plan."""
    physicalPerformance: Optional[str] = None
    animationTiming: Optional[str] = None
    performanceContract: Optional[ShotPerformanceContract] = None


class BoundaryCharacterState(BaseModel):
    """One character's complete, machine-comparable state at a shot boundary."""
    model_config = ConfigDict(extra="forbid")

    characterId: str = Field(min_length=1)
    screenZone: str = Field(min_length=1)
    facing: str = Field(min_length=1)
    pose: str = Field(min_length=1)
    expression: str = Field(min_length=1)
    visibleMarks: List[str]
    heldProps: List[str]


class ContinuityBoundary(BaseModel):
    """The exact world state that opens or closes a shot."""
    model_config = ConfigDict(extra="forbid")

    lighting: str = Field(min_length=1)
    cameraSide: str = Field(min_length=1)
    characters: List[BoundaryCharacterState]

    @model_validator(mode="after")
    def character_ids_are_unique(self):
        ids = [character.characterId for character in self.characters]
        if len(ids) != len(set(ids)):
            raise ValueError("continuity boundary contains duplicate character IDs")
        return self


class DialogueTimingWindow(BaseModel):
    """An exact spoken occurrence's numeric window inside its owning shot."""
    model_config = ConfigDict(extra="forbid")

    dialogueOccurrenceId: str = Field(min_length=1)
    startSec: float = Field(ge=0)
    endSec: float = Field(gt=0)

    @model_validator(mode="after")
    def window_has_positive_length(self):
        if self.startSec >= self.endSec:
            raise ValueError("dialogue timing startSec must precede endSec")
        return self


class ProductionDetailDraft(BaseModel):
    """Production-pass fields that the Director/Cinematographer may author."""
    model_config = ConfigDict(extra="forbid")

    shotId: str
    continuityIn: str
    continuityOut: str
    dialogueTiming: str
    continuityInState: Optional[ContinuityBoundary]
    continuityOutState: ContinuityBoundary
    dialogueTimings: List[DialogueTimingWindow]
    referenceRoles: str
    dialogueOccurrenceIds: List[str] = Field(default_factory=list)
    essentialProviderProtections: List[str] = Field(default_factory=list, max_length=3)


class ProductionDetail(ProductionDetailDraft):
    """Canonical execution truth after mechanical keyframe and duration derivation."""
    requiresNewKeyframe: bool
    intendedDurationRange: str


class VoicePerformance(BaseModel):
    dialogueOccurrenceId: str = ""
    sourceEventId: str = ""
    sourceEventIndex: int = -1
    beatId: str = ""
    sourceBeatId: str = ""
    speaker: str
    exactDialogue: str
    voiceIdentity: str = ""
    dramaticIntention: str
    subtext: str
    relationshipTarget: str
    emotionalEntry: str
    emotionalExit: str
    operativeWords: List[str]
    pace: str
    rhythm: str
    pauses: str
    breaths: str
    nonVerbalActions: str
    elevenLabsV3Direction: str
    physicalActionRelationship: str
    expectedTiming: str
    generatedAsset: Optional[str] = None
    approvalState: str = "draft"


class Scene(BaseModel):
    """sourceApprovalState (renamed from approvalState, 2026-07-17 schema checkpoint):
    this represents Gate 3's own draft marker on the SOURCE scene material — it is NEVER
    production authorization. The storyboard package's own top-level `approvalState` is
    the SOLE Gate A authority (enforced by cb_handover.promote(), which reads only that
    field); no nested field, this one included, may ever be read as authorizing
    production. Renamed specifically so a future reader cannot confuse the two."""
    sceneId: str
    sourceScriptRange: str
    location: str
    time: str
    participatingCharacters: List[str]
    purpose: str
    dramaticQuestion: str
    emotionalOwner: str
    connectionFromPreviousScene: str
    handoverToNextScene: str
    sourceApprovalState: str = "draft"


class EpisodeVision(BaseModel):
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


class SceneDirection(BaseModel):
    scene: Scene
    beats: List[Beat]


class ShotConference(BaseModel):
    shots: List[StoryboardCard]


class PerformanceCard(BaseModel):
    """Only the fields Gate 5 may author for an existing storyboard card."""
    model_config = ConfigDict(extra="forbid")

    shotId: str = Field(min_length=1)
    physicalPerformance: str = Field(min_length=1)
    animationTiming: str = Field(min_length=1)
    performanceContract: ShotPerformanceContract


class PerformancePass(BaseModel):
    shots: List[PerformanceCard]


class VoiceScript(BaseModel):
    performances: List[VoicePerformance]


class ProductionPass(BaseModel):
    details: List[ProductionDetailDraft]


class FieldProposal(BaseModel):
    field: str
    proposedText: str
    groundedIn: str                              # the existing canon text this derives from


class CharacterCompletion(BaseModel):
    character: str
    proposals: List[FieldProposal]


class CanonCompletionProposal(BaseModel):
    """Gate 0 — proposed completions for unresolved performance fields, FOR HUMAN
    APPROVAL. The run itself never uses these: psychology is never invented invisibly."""
    completions: List[CharacterCompletion]


class ReviewIssue(BaseModel):
    role: Literal["director", "cinematographer", "voice"]
    target: str
    issue: str


class ShowrunnerReview(BaseModel):
    judgement: str                               # a WRITTEN judgement — never a numerical score
    treatmentComparison: str                     # explicitly: does the result still deliver the
    #                                              SELECTED treatment's central experience?
    packingJudgement: str                        # explicitly: are all avoidable provider joins gone?
    packingPasses: bool
    passes: bool
    returnTo: Optional[Literal["gate3", "gate4"]] = None
    issues: List[ReviewIssue] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────────────────
# CANON SOURCES + GATE 0 READINESS
# ─────────────────────────────────────────────────────────────────────────────────────────
_CANON_SOURCES = {
    "showBible": ROOT / "shows/crystal-bears/canon/LOCKED_CANON.md",
    "studioBible": ROOT / "CRYSTAL_BEARS_STUDIO_BIBLE.md",
    "characters": ROOT / "shows/crystal-bears/canon/characters.json",
    "locations": ROOT / "shows/crystal-bears/canon/locations.json",
    "continuity": ROOT / "shows/crystal-bears/canon/continuity.json",
    "styleLaw": ROOT / "shows/crystal-bears/laws/style.txt",
    "showrunnerTaste": CREATIVE / "SHOWRUNNER_TASTE_CANON.md",
    "directorTaste": CREATIVE / "DIRECTOR_TASTE_CANON.md",
    "cinematographyTaste": CREATIVE / "CINEMATOGRAPHY_TASTE_CANON.md",
    "voiceTaste": CREATIVE / "VOICE_PERFORMANCE_CANON.md",
    "characterPerformance": CREATIVE / "CHARACTER_PERFORMANCE_CANON.json",
    "relationships": CREATIVE / "RELATIONSHIP_CANON.json",
    "exemplars": CREATIVE / "EXEMPLAR_LIBRARY.json",
}


def _script_package(episode, cast_scope=None, validate_canon=True):
    cands = sorted((ROOT / "cb-output").glob(f"{episode}_*beat_package.json"),
                   key=lambda p: p.stat().st_mtime)
    if not cands:
        raise RuntimeError(f"no approved script/beat package for {episode} in cb-output/")
    path = cands[-1]
    pkg = json.loads(path.read_text())
    try:
        current = SCRIPT_STORE.current(episode, required=True)
    except cb_scripts.ScriptStoreError as exc:
        raise RuntimeError(str(exc)) from exc
    source = pkg.get("sourceScript") or {}
    if source.get("scriptVersionId") != current["scriptVersionId"]:
        raise RuntimeError(
            f"STALE SCRIPT PACKAGE — {path.name} belongs to "
            f"{source.get('scriptVersionId') or 'an unversioned legacy script'}, while "
            f"{current['scriptVersionId']} is active. Approve Story & Direction for the active script first.")
    if source.get("sha256") != current["sha256"]:
        raise RuntimeError(f"SCRIPT LINEAGE CORRUPT — {path.name}'s script hash does not match its version ID")
    cast = sorted(cast_scope) if cast_scope is not None else sorted({
        name for beat in pkg.get("beats") or []
        for name in beat.get("characters") or [] if name})
    lock = cb_canon.status(episode, cast, root=ROOT)
    if validate_canon:
        try:
            lock = cb_canon.require_locked(episode, cast, root=ROOT)
        except cb_canon.CanonLockError as exc:
            raise RuntimeError(str(exc)) from exc
    expected_input = cb_lineage.dependency_signature(
        "beat-package-input", {
            "scriptVersionId": current["scriptVersionId"],
            "canonProfileDigest": lock["profileDigests"]["story"],
        })
    if pkg.get("inputSignature") != expected_input:
        raise RuntimeError(f"SCRIPT LINEAGE MISSING — {path.name} has no valid beat-package input signature")
    expected_content = cb_lineage.beat_package_signature(pkg)
    if pkg.get("contentSignature") != expected_content:
        raise RuntimeError(f"BEAT PACKAGE CHANGED — {path.name}'s signed canonical content no longer matches")
    return path


def load_canon_envelope(episode="Ep1", cast_scope=None, log=print):
    env = {"episode": episode, "canonVersion": CANON_VERSION, "builtAt": _now(),
           "sources": {}, "gaps": [], "conflicts": []}
    for key, path in _CANON_SOURCES.items():
        if path.exists():
            env["sources"][key] = {"path": str(path.relative_to(ROOT)),
                                     "sha256": cb_lineage.sha256_file(path)}
        else:
            env["gaps"].append(f"{key}: {path.name} not present (optional context)")
    spath = _script_package(episode, cast_scope=cast_scope)
    pkg = json.loads(spath.read_text())
    cast = sorted(cast_scope) if cast_scope is not None else sorted({
        name for beat in pkg.get("beats") or []
        for name in beat.get("characters") or [] if name})
    try:
        lock = cb_canon.require_locked(episode, cast, root=ROOT)
    except cb_canon.CanonLockError as exc:
        raise RuntimeError(str(exc)) from exc
    env["sources"]["scriptPackage"] = {
        "path": str(spath.relative_to(ROOT)), "sha256": cb_lineage.sha256_file(spath)}
    env["canonLock"] = {
        "manifestDigest": lock["manifestDigest"],
        "profile": "storyboard",
        "profileDigest": lock["profileDigests"]["storyboard"],
        "sourceHashes": cb_canon.source_hashes("storyboard", ROOT),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{episode}_canon_envelope.json"
    json.dump(env, open(out, "w"), indent=1, ensure_ascii=False)
    log(f"CANON ENVELOPE — {len(env['sources'])} sources versioned, "
        f"{len(env['gaps'])} gap(s), {len(env['conflicts'])} genuine conflict(s) -> {out.name}")
    if env["conflicts"]:
        raise RuntimeError("CANON CONFLICT — human resolution required:\n  "
                           + "\n  ".join(env["conflicts"]))
    return env


def _canon_text(key, limit=9000):
    p = _CANON_SOURCES.get(key)
    return p.read_text()[:limit] if p and p.exists() else ""


def _canonical_exemplars(limit=6):
    """THE SIMPLIFICATION CHECKPOINT (2026-07-17): role prompts receive ONLY the concise
    approved canonical exemplar PRINCIPLES (EXEMPLAR_LIBRARY, reusable entries) — never
    the raw exemplar dump (attempted/userWords prose), and never Evidence Library, Pattern
    Library or Active Creative Memory content. Active Memory is an audit registry pointing
    at approved source changes; its prose is never injected into a creative role."""
    p = _CANON_SOURCES["exemplars"]
    if not p.exists():
        return ""
    lib = json.load(open(p))
    lines = [f"• [{e['id']} · {e['outcome'].upper()}] {e['principle']}"
             for e in lib.get("exemplars", [])
             if e.get("reusable") and e.get("principle")][:limit]
    return "\n".join(lines)[:2200]


def _script_beats(episode, scene_num=None):
    d = json.load(open(_script_package(episode, validate_canon=False)))
    # Readers may order or scope their own view, but must never mutate the loaded canonical
    # package: its signed content identity cannot depend on which helper happened to read it.
    beats = list(d.get("beats") or [])
    if scene_num is not None:
        beats = [b for b in beats if str(b.get("sceneNumber")) == str(scene_num)]
    beats.sort(key=lambda b: int(re.search(r"[Bb](\d+)", b.get("beatCode") or "B0").group(1)))
    return beats, d


def _locked_dialogue(beats):
    """Return typed source occurrences, never lossy speaker/text tuples."""
    out = []
    for b in beats:
        for c in (b.get("cuts") or []):
            dlg = (c.get("dialogue") or "").strip()
            if dlg and ":" in dlg:
                required = ("dialogueOccurrenceId", "sourceEventId", "sourceEventIndex",
                            "speaker", "exactText")
                missing = [key for key in required if c.get(key) in (None, "")]
                if missing:
                    raise RuntimeError(
                        f"SOURCE CONTRACT MISSING — {b.get('beatCode')} dialogue cut lacks "
                        + ", ".join(missing) + "; rebuild Story Intake")
                out.append({
                    "dialogueOccurrenceId": c["dialogueOccurrenceId"],
                    "sourceEventId": c["sourceEventId"],
                    "sourceEventIndex": c["sourceEventIndex"],
                    "beatId": b["beatCode"],
                    "sourceBeatId": b["sourceBeatId"],
                    "speaker": c["speaker"],
                    "exactText": c["exactText"],
                })
    return out


def _beat_dialogue_occurrences(source_beat):
    return [DialogueOccurrence(
        dialogueOccurrenceId=cut["dialogueOccurrenceId"],
        sourceEventId=cut["sourceEventId"],
        sourceEventIndex=cut["sourceEventIndex"],
        beatId=source_beat["beatCode"],
        sourceBeatId=source_beat["sourceBeatId"],
        speaker=cut["speaker"],
        exactText=cut["exactText"],
    ) for cut in (source_beat.get("cuts") or []) if cut.get("sourceType") == "dialogue"]


def _scene_dialogue_contract(beats, voices, details):
    occurrences = [occ for beat in beats for occ in beat.dialogueOccurrences]
    inputs = {
        "orderedSourceBeatIds": [beat.sourceBeatId for beat in beats],
        "orderedDialogueOccurrenceIds": [occ.dialogueOccurrenceId for occ in occurrences],
        "voiceOccurrenceIds": [voice.dialogueOccurrenceId for voice in voices],
        "shotAssignments": {
            detail.shotId: list(detail.dialogueOccurrenceIds) for detail in details},
        "shotTimingWindows": {
            detail.shotId: [window.model_dump() for window in detail.dialogueTimings]
            for detail in details},
    }
    return {"schemaVersion": 2, **inputs,
            "inputSignature": cb_lineage.dependency_signature(
                "scene-dialogue-occurrences", inputs)}


def _characters_for(names):
    try:
        chars = json.load(open(_CANON_SOURCES["characters"]))
    except Exception:
        return "{}"
    picked = {}
    for n in names:
        for k, v in chars.items():
            if _norm(k) == _norm(n) and isinstance(v, dict):
                picked[k] = {kk: v.get(kk) for kk in
                             ("bible", "cadence", "actingNote", "gender", "sizeRank", "size",
                              "lexicon", "cameraRegister") if v.get(kk)}
    perf = {}
    p = _CANON_SOURCES["characterPerformance"]
    if p.exists():
        allp = json.load(open(p)).get("characters", {})
        perf = {k: v for k, v in allp.items() if any(_norm(k) == _norm(n) for n in names)}
    rel = {}
    r = _CANON_SOURCES["relationships"]
    if r.exists():
        for pair in json.load(open(r)).get("pairs", []):
            if all(any(_norm(x) == _norm(n) for n in names) for x in pair.get("pair", [])):
                rel[" & ".join(pair["pair"])] = pair
    return json.dumps({"bibles": picked, "performanceCanon": perf, "relationships": rel},
                      ensure_ascii=False)


def _unresolved_fields_for(names):
    """Return only essential primary-bible gaps, never optional overlay blanks.

    The immutable canon lock already refuses a participating character without these
    fields. Null fields in CHARACTER_PERFORMANCE_CANON are advisory expansion space and
    must not cause the system to invent psychology or claim a locked character is absent.
    """
    p = _CANON_SOURCES["characters"]
    if not p.exists():
        return {}
    allp = json.load(open(p))
    out = {}
    for n in names:
        for k, v in allp.items():
            if _norm(k) == _norm(n) and isinstance(v, dict):
                missing = [field for field in ("bible", "cadence", "key_features", "anchor")
                           if not v.get(field)]
                if missing:
                    out[k] = sorted(missing)
    return out


# ─────────────────────────────────────────────────────────────────────────────────────────
# ROLE MINDS — taste canons + the exemplar library's explicit human verdicts
# ─────────────────────────────────────────────────────────────────────────────────────────
def _mind(role, taste_keys, charge):
    taste = "\n\n".join(_canon_text(k, 7000) for k in taste_keys)
    # The Creative Room now genuinely hires the repository's specialist people.  Only the
    # concise marked runtime contracts are loaded (not historical/superseded pipeline notes
    # elsewhere in the long skill documents).  This remains the ONE existing Gate 0-6
    # creative path; no parallel storyboard pipeline is introduced.
    worker_keys = []
    if "EMOTIONAL STORY-TO-SCREEN" in role:
        worker_keys.append("heart-director")
    if "DIRECTOR" in role:
        worker_keys.append("director")
    if "CINEMATOGRAPHER" in role:
        worker_keys.append("cinematography")
    if "VOICE" in role:
        worker_keys.append("voice")
    worker_contracts = "\n\n".join(cb_departments.load_runtime_skill(
        k, CREATIVE_DIRECTING_STANDARD_VERSION)
                                      for k in worker_keys)
    return (f"You are the {role} of the Crystal Bears creative room — a world-class family-"
            f"animation voice for ages 4-8 with adult-rewarding wit. The show's OWN world "
            f"never names or imitates a real filmmaker or studio — no character, line, "
            f"on-screen reference or plot point may cite one. Separately, and only as your "
            f"OWN private craft direction never surfaced in the show itself, your department "
            f"contract below may cite real professional influences by name; those are "
            f"guidance for your judgement, never content to ship.\n\n{charge}\n\n"
            f"LIVE DEPARTMENT WORKER CONTRACT(S) LOADED FROM SKILL.md:\n"
            f"{worker_contracts or 'Showrunner taste canon owns this pass.'}\n\n"
            f"YOUR TASTE CANON:\n{taste}\n\n"
            f"APPROVED CANONICAL EXEMPLAR PRINCIPLES (concise, directly relevant; the "
            f"REJECTED verdicts are failures you must not repeat — do not treat any "
            f"rejected artifact as a model, and do not reverse-engineer a 'desired shot' "
            f"from them):\n"
            + _canonical_exemplars()
            + "\n\nSHOW CANON (authoritative, never contradicted):\n"
            + _canon_text("showBible", 6000)
            + "\n\nHARD RULES: approved dialogue is verbatim-locked — never reword, drop or "
              "invent a line. Character identity comes only from references; never describe "
              "physical appearance. Use ONLY established character canon — where a "
              "performance field is unresolved, work from what exists rather than inventing "
              "deep psychology. Concrete, observable craft language only — 'cinematic', "
              "'beautiful' and 'award-winning' are ambitions, not directions. Same event -> "
              "different behaviour per character (the character-substitution test). "
              "Characters are NEVER assigned permanent screen sides.")


PROV = lambda role: Provenance(role=role, model=cb_llm.DIRECTOR_MODEL, at=_now()).model_dump()


# ── EPISODE VISION (Showrunner — unchanged from v1; not part of the rejected process) ────
def episode_vision(episode="Ep1", log=print):
    beats, d = _script_beats(episode)
    script = "\n".join(
        f"[Scene {b.get('sceneNumber')} · {b.get('beatCode')}] {b.get('storyBeat','')}\n"
        + "\n".join(f"  {c.get('dialogue')}" for c in (b.get('cuts') or []) if c.get('dialogue'))
        for b in beats)
    v = cb_llm.structured(
        _mind("SHOWRUNNER", ["showrunnerTaste"],
              "Read the COMPLETE episode before anything is directed. Establish what this "
              "episode is really about beneath the plot, what changes, which relationship "
              "carries its heart, where the audience laughs, leans forward, becomes still, "
              "and what remains after it ends."),
        f"THE COMPLETE APPROVED SCRIPT (dialogue verbatim-locked):\n{script[:24000]}",
        EpisodeVision, label="creative_vision")
    beat_signature = cb_lineage.beat_package_signature(d)
    script_version = (d.get("sourceScript") or {}).get("scriptVersionId")
    canon_digest = cb_canon.profile_digest(
        "story", episode=episode,
        cast={name for beat in beats for name in beat.get("characters") or []},
        root=ROOT)
    vision_inputs = cb_lineage.episode_vision_inputs(
        script_version, beat_signature, canon_digest)
    pkg = {"episodeId": episode, "title": d.get("title", episode),
           "sourceScriptVersion": _md5(_script_package(episode)),
           "sourceScript": d.get("sourceScript"),
           "sourceBeatPackageSignature": beat_signature,
           "inputSignature": cb_lineage.dependency_signature("episode-vision", vision_inputs),
           "canonLock": {"profile": "story", "profileDigest": canon_digest},
           "canonVersion": CANON_VERSION, **v.model_dump(),
           "showrunnerJudgement": "", "approvalState": "draft",
           "provenance": PROV("showrunner")}
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(pkg, open(OUT / f"{episode}_episode_vision.json", "w"), indent=1,
              ensure_ascii=False)
    log(f"EPISODE VISION — theme: {v.theme[:90]}")
    return pkg


# ─────────────────────────────────────────────────────────────────────────────────────────
# GATE 0 — CANON AND CREATIVE READINESS
# ─────────────────────────────────────────────────────────────────────────────────────────
def gate0_readiness(episode, scene_num, brief, log=print):
    """Confirms canon/script/exemplars; where the participating characters carry
    unresolved performance fields, authors a PROPOSED canon completion for human
    approval. The run proceeds on ESTABLISHED canon only — proposals are saved for
    Julian's decision, never fed into directing."""
    beats, script_pkg = _script_beats(episode, scene_num)
    if not beats:
        raise RuntimeError(f"no script material for scene {scene_num}")
    cast = sorted({c for b in beats for c in (b.get("characters") or [])})
    env = load_canon_envelope(episode, cast_scope=cast, log=log)
    source_report = cb_lineage.validate_beat_package_source_contract(script_pkg)
    if not source_report["ok"]:
        raise RuntimeError(
            "STALE STORY INTAKE — the canonical beat package has no valid exact-event "
            "contract (" + ", ".join(source_report["issues"][:5]) + "). Rebuild or "
            "mechanically migrate Story Intake before directing this scene.")
    unresolved = _unresolved_fields_for(cast)
    proposal_path = None
    if unresolved:
        prop = cb_llm.structured(
            _mind("SHOWRUNNER", ["showrunnerTaste"],
                  "Gate 0 readiness: performance-canon fields for this scene's cast are "
                  "unresolved. Propose completions FOR HUMAN APPROVAL — each proposal must "
                  "be grounded in a quoted piece of the character's EXISTING canon (bible, "
                  "cadence, actingNote, lexicon), extending it honestly, never inventing an "
                  "unrelated psychology. These are proposals only; nothing here is canon "
                  "until the user approves it."),
            f"CAST: {', '.join(cast)}\n\nUNRESOLVED FIELDS:\n"
            + json.dumps(unresolved, ensure_ascii=False)
            + f"\n\nESTABLISHED CANON FOR THIS CAST:\n{_characters_for(cast)[:12000]}",
            CanonCompletionProposal, label=f"gate0_canon_completion_s{scene_num}")
        doc = {"episodeId": episode, "sceneNumber": str(scene_num), "builtAt": _now(),
               "approvalState": "proposed-awaiting-human-approval",
               "note": ("Gate 0 canon-completion PROPOSAL — not canon, not used by this "
                         "run's directing. The scene was directed on established canon only."),
               "unresolvedFields": unresolved,
               "completions": [c.model_dump() for c in prop.completions]}
        proposal_path = OUT / f"{episode}_scene{scene_num}_canon_completion_PROPOSED.json"
        json.dump(doc, open(proposal_path, "w"), indent=1, ensure_ascii=False)
        log(f"GATE 0 — canon-completion PROPOSAL for {', '.join(unresolved)} -> "
            f"{proposal_path.name} (awaiting human approval; run uses established canon only)")
    return {"envelope": env, "cast": cast, "beats": beats,
            "scriptPackage": script_pkg,
            "unresolvedFields": unresolved,
            "canonCompletionProposal": str(proposal_path.name) if proposal_path else None,
            "brief": brief or None}


# ─────────────────────────────────────────────────────────────────────────────────────────
# HEART CONTRACT — emotional meaning before treatments, boards or prompts
# ─────────────────────────────────────────────────────────────────────────────────────────
def emotional_story_contract(episode, scene_num, vision, ready, log=print):
    script = json.dumps([{
        "beatCode": beat.get("beatCode"), "storyBeat": beat.get("storyBeat"),
        "dialogue": [cut.get("dialogue") for cut in (beat.get("cuts") or [])
                     if cut.get("dialogue")],
        "location": beat.get("location"), "time": beat.get("time")}
        for beat in ready["beats"]], ensure_ascii=False)
    brief_line = (f"\n\nUSER AMBITION — audience experience only, never permission to "
                  f"rewrite canon or dialogue:\n{ready['brief']}" if ready["brief"] else "")
    contract = cb_llm.structured(
        _mind("EMOTIONAL STORY-TO-SCREEN DIRECTOR", ["directorTaste"],
              "Define the scene's simple, direct emotional operating system before any "
              "treatment or shot exists. A four-to-eight-year-old must understand the "
              "immediate want through action; an adult should recognise the deeper ordinary-"
              "life truth without the theme being spoken. Make the relationship cause the "
              "change. Identify the emotional owner's entry belief, pressure behaviour, "
              "costly choice and visible exit action. Then define a restrained tapestry of "
              "physical motif, sonic motif, colour/light progression, thematic visual "
              "contrast and an opening/closing image rhyme whose meaning changes. Name what "
              "can be removed from dialogue because behaviour, image or silence carries it. "
              "The environment must apply emotional or physical pressure, not act as wallpaper."),
        f"EPISODE VISION:\n{json.dumps(vision, ensure_ascii=False)[:6000]}\n\n"
        f"LOCKED SCENE SCRIPT:\n{script}\n\n"
        f"CHARACTER + RELATIONSHIP CANON:\n{_characters_for(ready['cast'])[:9000]}"
        + brief_line,
        EmotionalStoryToScreenContract, label=f"heart_contract_s{scene_num}")
    log(f"HEART CONTRACT — {contract.northStar.childClearWant[:90]} -> "
        f"{contract.northStar.finalAfterFeeling[:90]}")
    return contract


# ─────────────────────────────────────────────────────────────────────────────────────────
# GATE 1 — WHOLE-SCENE CREATIVE TREATMENTS (Director + Cinematographer, jointly)
# ─────────────────────────────────────────────────────────────────────────────────────────
def gate1_treatments(episode, scene_num, vision, ready, heart=None, log=print):
    script = json.dumps([{"beatCode": b.get("beatCode"), "storyBeat": b.get("storyBeat"),
                           "dialogue": [c.get("dialogue") for c in (b.get("cuts") or [])
                                         if c.get("dialogue")],
                           "location": b.get("location"), "time": b.get("time")}
                          for b in ready["beats"]], ensure_ascii=False)
    brief_line = (f"\n\nTHE USER'S AMBITION (the desired AUDIENCE EXPERIENCE — never a shot "
                  f"solution; you own the solution): {ready['brief']}" if ready["brief"] else "")
    ts = cb_llm.structured(
        _mind("DIRECTOR AND CINEMATOGRAPHER, IN JOINT CONFERENCE",
              ["directorTaste", "cinematographyTaste"],
              "BEFORE any beat or shot exists, jointly author THREE materially different "
              "WHOLE-SCENE TREATMENTS — three complete directing concepts, never three "
              "variations of the same coverage. Each defines its own audience experience, "
              "emotional point of view, comic/dramatic mechanism, character-performance "
              "strategy, visual grammar, camera-character relationship, movement-versus-"
              "stillness strategy, use of depth and environment, rhythm and escalation, cut "
              "philosophy, and a memorable opening and closing image. The CINEMATOGRAPHER is "
              "a CO-AUTHOR here, not a decorator of a finished idea: challenge any "
              "interpretation that would produce safe, static or conventional imagery, and "
              "record that challenge per treatment. The camera may discover action "
              "experientially — it does not have to wait anywhere safe. No fixed screen "
              "sides; no automatic action/consequence/reaction coverage; no mechanical shot "
              "thinking at this stage at all."),
        f"EPISODE VISION:\n{json.dumps(vision, ensure_ascii=False)[:6000]}\n\n"
        + (f"SIGNED EMOTIONAL STORY-TO-SCREEN CONTRACT:\n"
           f"{heart.model_dump_json()}\n\n" if heart else "")
        + f"THE SCENE'S APPROVED SCRIPT (dialogue verbatim-locked):\n{script}\n\n"
        f"CHARACTER + RELATIONSHIP CANON:\n{_characters_for(ready['cast'])[:9000]}"
        + brief_line,
        TreatmentSet, label=f"gate1_treatments_s{scene_num}")
    log(f"GATE 1 — three whole-scene treatments: "
        + " | ".join(t.name for t in ts.treatments))
    return ts.treatments


# ─────────────────────────────────────────────────────────────────────────────────────────
# GATE 2 — SHOWRUNNER TREATMENT SELECTION (before any beat breakdown)
# ─────────────────────────────────────────────────────────────────────────────────────────
def gate2_select(vision, treatments, ready, heart=None, log=print):
    sel = cb_llm.structured(
        _mind("SHOWRUNNER", ["showrunnerTaste"],
              "Evaluate the three COMPLETE scene treatments before any beat breakdown. "
              "Select one — or combine — on story truth, character specificity, emotional "
              "clarity, visual originality, audience experience, cinematic opportunity, "
              "rhythm, contrast with surrounding scenes, feasibility and memorability. You "
              "MUST reject any treatment that depends on: fixed character lanes; keeping "
              "all characters visible; habitual action/reaction coverage; safe camera "
              "placement; repeated close-up punctuation; mechanical shot counts; generic "
              "'cinematic' terminology; or merely illustrating the script — and say so in "
              "rejectionChecks. State the ONE governing audience experience the selected "
              "treatment commits the scene to."),
        f"EPISODE VISION:\n{json.dumps(vision, ensure_ascii=False)[:5000]}\n\n"
        + (f"SIGNED EMOTIONAL STORY-TO-SCREEN CONTRACT:\n"
           f"{heart.model_dump_json()}\n\n" if heart else "")
        + ("USER AMBITION: " + ready["brief"] + "\n\n" if ready["brief"] else "")
        + "THE THREE TREATMENTS:\n"
        + "\n\n".join(t.model_dump_json() for t in treatments),
        TreatmentSelection, label="gate2_selection")
    log(f"GATE 2 — selected: {sel.selectedTreatment[:100]} · governing experience: "
        f"{sel.governingAudienceExperience[:90]}")
    return sel


def _selected_treatment(treatments, selection):
    for t in treatments:
        if _norm(t.name) == _norm(selection.selectedTreatment) or \
           _norm(t.name) in _norm(selection.selectedTreatment):
            return t
    return treatments[0]


# ─────────────────────────────────────────────────────────────────────────────────────────
# GATE 3 — BEAT ARCHITECTURE (Director, inside the selected treatment)
# ─────────────────────────────────────────────────────────────────────────────────────────
def gate3_beats(episode, scene_num, vision, selection, treatment, ready,
                heart=None, review_notes="", log=print):
    script = json.dumps([{"beatCode": b.get("beatCode"),
                           "sourceBeatId": b.get("sourceBeatId"),
                           "sourceEventIds": b.get("sourceEventIds"),
                           "storyBeat": b.get("storyBeat"),
                           "dialogueOccurrences": [{
                               "dialogueOccurrenceId": c.get("dialogueOccurrenceId"),
                               "sourceEventId": c.get("sourceEventId"),
                               "speaker": c.get("speaker"),
                               "exactText": c.get("exactText")}
                               for c in (b.get("cuts") or [])
                               if c.get("sourceType") == "dialogue"],
                           "location": b.get("location"), "time": b.get("time")}
                          for b in ready["beats"]], ensure_ascii=False)
    notes = (f"\n\nSHOWRUNNER'S RETURN NOTES (a COMPLETE re-architecture is required — "
             f"never a wording patch): {review_notes}" if review_notes else "")
    sd = cb_llm.structured(
        _mind("DIRECTOR", ["directorTaste"],
              "Structure the beats INSIDE the selected whole-scene treatment. Every beat "
              "defines: what changes; who drives the change; audience anticipation; the "
              "action or choice; the consequence; and the emotional or comic handover. "
              "Beats do NOT automatically become separate shots — a physical, emotional or "
              "comic chain remains continuous when continuity strengthens it. Every beat "
              "also needs an emotionContract and a comedyContract. emotionContract names "
              "the participating character who owns the beat, entry state, pressure, "
              "choice or realisation, exit state, observable evidence, whether the audience "
              "is ahead/with/behind them, and what remains held after the beat. Never invent "
              "hidden psychology: use the selected treatment, established character canon "
              "and visible script event. comedyContract explicitly says NONE, SMALL or BIG. "
              "For comedy, preserve setup, expectation, disruption, button and the hold that "
              "lets the audience catch up. BIG comedy must include one readable physical "
              "staging contract: what stays visible, contact and weight, payoff shape and no "
              "more than three specific staging failures. powerMoment is null unless the "
              "approved script and canon genuinely contain a Crystal power event; when it "
              "exists, bind any spoken call by dialogueOccurrenceId rather than copying or "
              "rewriting its words."),
        f"THE SELECTED TREATMENT (this governs everything):\n{treatment.model_dump_json()}\n\n"
        + (f"SIGNED EMOTIONAL STORY-TO-SCREEN CONTRACT:\n"
           f"{heart.model_dump_json()}\n\n" if heart else "")
        + f"THE SHOWRUNNER'S SELECTION:\n{selection.model_dump_json()}\n\n"
        f"EPISODE VISION:\n{json.dumps(vision, ensure_ascii=False)[:4000]}\n\n"
        f"THE SCENE'S APPROVED SCRIPT (dialogue verbatim-locked):\n{script}\n\n"
        f"CHARACTER CANON:\n{_characters_for(ready['cast'])[:8000]}{notes}\n\n"
        f"Return the Scene record and EXACTLY one Beat per script beat, in the same order "
        f"(beatId = the script's own beatCode; sceneId = 'S{scene_num}'; sourceScript = "
        f"the storyBeat verbatim; exactDialogue = every locked display line, verbatim, in "
        f"order). Source IDs are immutable facts and will be mechanically restored after "
        f"your creative pass; never merge, drop, duplicate or reorder a source beat.",
        SceneDirection, label=f"gate3_beats_s{scene_num}")
    missing_supervision = [
        beat.beatId for beat in sd.beats
        if not beat.emotionContract or not beat.comedyContract
    ]
    if missing_supervision and not review_notes:
        repair_note = (
            "Validation repair: every beat must include both a complete typed "
            "emotionContract and a complete typed comedyContract, including NONE comedy. "
            "Missing on: " + ", ".join(missing_supervision)
        )
        log(f"  [director] gate3_beats_s{scene_num}: {repair_note} - rerunning once", flush=True)
        return gate3_beats(
            episode, scene_num, vision, selection, treatment, ready,
            heart=heart, review_notes=repair_note, log=log)
    # The Director owns meaning inside each beat, never source identity.
    expected_codes = [str(beat.get("beatCode")) for beat in ready["beats"]]
    returned_codes = [str(beat.beatId) for beat in sd.beats]
    if returned_codes != expected_codes:
        raise RuntimeError(
            "BEAT PASS DROPPED/DUPLICATED/REORDERED source beats — expected "
            f"{expected_codes}, got {returned_codes}")
    for beat, src in zip(sd.beats, ready["beats"]):
        required = ("sourceBeatId", "sourceEventIds", "sourceEventRange",
                    "sourceEventSignature")
        missing = [key for key in required if not src.get(key)]
        if missing:
            raise RuntimeError(
                f"SOURCE CONTRACT MISSING — {src.get('beatCode')} lacks "
                + ", ".join(missing))
        beat.beatId = str(src["beatCode"])
        beat.sceneId = f"S{scene_num}"
        beat.sourceScript = str(src.get("storyBeat") or "")
        beat.sourceBeatId = src["sourceBeatId"]
        beat.sourceEventIds = list(src["sourceEventIds"])
        beat.sourceEventRange = dict(src["sourceEventRange"])
        beat.sourceEventSignature = dict(src["sourceEventSignature"])
        beat.dialogueOccurrences = _beat_dialogue_occurrences(src)
        beat.exactDialogue = [
            f"{occ.speaker}: {occ.exactText}" for occ in beat.dialogueOccurrences]
        if not beat.emotionContract or not beat.comedyContract:
            raise RuntimeError(
                f"SUPERVISION CONTRACT MISSING - {beat.beatId} needs typed emotion and "
                "comedy intent")
        participant_names = {_norm(name) for name in beat.participatingCharacters}
        if _norm(beat.emotionContract.owner) not in participant_names:
            raise RuntimeError(
                f"EMOTION CONTRACT UNKNOWN OWNER - {beat.beatId} names "
                f"{beat.emotionContract.owner}")
        for field, name in (("comicOwner", beat.comedyContract.comicOwner),
                            ("straightCharacter", beat.comedyContract.straightCharacter)):
            if name and _norm(name) not in participant_names:
                raise RuntimeError(
                    f"COMEDY CONTRACT UNKNOWN {field} - {beat.beatId} names {name}")
        if beat.powerMoment:
            if _norm(beat.powerMoment.bearer) not in participant_names:
                raise RuntimeError(
                    f"POWER CONTRACT UNKNOWN BEARER - {beat.beatId} names "
                    f"{beat.powerMoment.bearer}")
            occurrence_ids = {
                occurrence.dialogueOccurrenceId for occurrence in beat.dialogueOccurrences}
            call_id = beat.powerMoment.exactCallOccurrenceId
            if call_id and call_id not in occurrence_ids:
                raise RuntimeError(
                    f"POWER CONTRACT UNKNOWN CALL - {beat.beatId} names {call_id}")
    return sd


# ─────────────────────────────────────────────────────────────────────────────────────────
# GATE 4 — DIRECTOR/CINEMATOGRAPHER SHOT CONFERENCE
# ─────────────────────────────────────────────────────────────────────────────────────────
def _validate_gate4_production_units(shots, beats):
    """Refuse a storyboard that cannot become ordered 4-30s Seedance units."""
    expected = [beat.beatId for beat in beats]
    beat_index = {beat_id: index for index, beat_id in enumerate(expected)}
    flattened = []
    for shot in shots:
        if shot.targetDurationSec is None:
            raise RuntimeError(
                f"PRODUCTION UNIT DURATION MISSING - {shot.shotId} needs a natural 4-30s "
                "targetDurationSec")
        if not shot.stagePlan:
            raise RuntimeError(
                f"PRODUCTION UNIT STAGES MISSING - {shot.shotId} needs 1-3 causal stages")
        if not shot.internalShotPlan:
            raise RuntimeError(
                f"PRODUCTION UNIT CAMERA PLAN MISSING - {shot.shotId} needs at least one "
                "motivated internal shot")
        unknown = [beat_id for beat_id in shot.beatIds if beat_id not in beat_index]
        if unknown:
            raise RuntimeError(
                f"PRODUCTION UNIT UNKNOWN BEAT - {shot.shotId} names {unknown[0]}")
        stage_beats = []
        for stage in shot.stagePlan:
            for beat_id in stage.beatIds:
                if beat_id not in stage_beats:
                    stage_beats.append(beat_id)
        if stage_beats != shot.beatIds:
            raise RuntimeError(
                f"PRODUCTION UNIT STAGE COVERAGE MISMATCH - {shot.shotId} carries "
                f"{shot.beatIds}, but its stages carry {stage_beats}")
        flattened.extend(shot.beatIds)

    if not flattened and expected:
        raise RuntimeError("PRODUCTION UNIT COVERAGE MISSING - the scene has no units")
    indices = [beat_index[beat_id] for beat_id in flattened]
    if indices != sorted(indices):
        raise RuntimeError(
            "PRODUCTION UNIT BEAT ORDER CHANGED - source beats must remain chronological")
    covered = []
    for beat_id in flattened:
        if beat_id not in covered:
            covered.append(beat_id)
    if covered != expected:
        raise RuntimeError(
            "PRODUCTION UNIT BEAT COVERAGE MISMATCH - expected "
            f"{expected}, got {covered}")
    packing = cb_unit_packing.audit_units(shots)
    if packing["blockingIssues"]:
        issue = packing["blockingIssues"][0]
        raise RuntimeError(
            f"PRODUCTION UNIT PACKING INVALID - {issue['code']}: {issue['message']}")
    return packing


def gate4_shot_conference(episode, scene_num, selection, treatment, sd,
                          heart=None, review_notes="", log=print):
    notes = (f"\n\nSHOWRUNNER'S RETURN NOTES (redesign the SEQUENCE — never patch "
             f"wording): {review_notes}" if review_notes else "")
    sc = cb_llm.structured_with_repair(
        _mind("DIRECTOR AND CINEMATOGRAPHER, IN SHOT CONFERENCE",
              ["directorTaste", "cinematographyTaste"],
              "Design the sequence TOGETHER as Seedance 2.5 PRODUCTION UNITS, not routine "
              "coverage shots. Each CreativeShotCard is one continuous provider request with "
              "one opening anchor, one continuity landing and a natural targetDurationSec from "
              "4 through 30 seconds. Thirty seconds is available continuity capacity, never a "
              "target. Pack a complete causal arc only for the time its faithful setup, "
              "development, escalation and payoff naturally require under one reference regime. Internal "
              "camera cuts stay INSIDE that provider request. Never add empty action merely to "
              "fill time and never compress an honest performance to hit the ceiling. Before "
              "creating another provider unit, explicitly test whether its stages can fit in "
              "the prior unit without exceeding 30 seconds. Split only where the story "
              "needs a deliberate editorial boundary, a location/time/reference regime changes, "
              "continuity needs a fresh anchor, or the honest performance would exceed 30 "
              "seconds. A unit may span consecutive beats; do not create one unit per source "
              "beat by default. Preserve every source beat and dialogue occurrence in exact "
              "order. Inside each unit, author stagePlan with one to three consecutive causal "
              "stages. Every stage names its beatIds, contains ONE primary visible state change, "
              "states the emotional or comic turn, gives the motivated camera/transition "
              "treatment and ends on an observable state. Author internalShotPlan with one to "
              "three views. Each view exists ONLY when it introduces a meaningful change in point "
              "of view, information, scale, emotion, power, energy, spatial experience, comic "
              "timing or visual idea - never to complete coverage. Every internal view gives "
              "its purpose, framing and camera, story action, performance focus, landing image "
              "and cutReason. At production-unit boundaries, for EVERY cut state why remaining "
              "continuous would be weaker; for EVERY continuous handoff state why a cut would "
              "weaken the experience (transitionReason). Every card also owns the provider "
              "boundary AFTER it. Set providerBoundaryReason to scene_end on the final card; "
              "otherwise choose duration_limit, location_or_time_change, "
              "reference_regime_change, continuity_reset, dramatic_editorial_break or "
              "complexity_protection, and state the concrete providerBoundaryExplanation. "
              "Thirty seconds is continuity capacity, not complexity capacity: never put more "
              "than three causal stages or three motivated camera views into one provider unit. "
              "If the faithful scene needs more, split at the strongest story-led boundary rather "
              "than shrinking, rushing or omitting its performance. "
              "duration_limit is truthful only when this unit plus the next unit's natural "
              "duration exceeds 30 seconds. A dramatic or complexity split whose pair totals "
              "30 seconds or less is exceptional and will be challenged by the Showrunner. "
              "The camera may lead, "
              "pursue, lag, lose a character, rediscover a character, anticipate, arrive "
              "late, remain still, or abandon one character for another — NO behaviour is "
              "automatically preferred; choose what the treatment's experience demands. "
              "Geography stays understandable, but characters get no permanent screen "
              "sides. A reaction character receives a separate shot ONLY when that reaction "
              "changes the meaning — never as automatic punctuation. A chain may span "
              "beats (beatIds lists every beat a production unit carries). Duration, causal "
              "stages and motivated views define the approved edit; executable continuity, "
              "reference attachment and provider protections come later. "
              "openingImage IS THE LITERAL FIRST FRAME (2026-07-17 correction, simplified "
              "same day) — a renderable description of the actual opening composition that "
              "makes THIS shot's experience visually legible, not a mood note and never a "
              "fixed checklist. Say only what materially defines this particular frame — "
              "viewpoint, a spatial relationship, depth, or an action direction, whichever "
              "of those actually matters here, never all of them by default and never "
              "reduced to character pose alone. A wide establishing view is wrong when "
              "cameraRelationship calls for an embedded, in-the-world vantage — but the "
              "fix is judgment about THIS shot, not a mandatory formula repeated on every "
              "shot. closingImage, like openingImage, is a purely VISUAL, PHYSICAL "
              "description of the final frame - describe only what is SEEN (pose, "
              "environment, the physical residue of what just happened), never a "
              "character's spoken line, quoted or paraphrased: the audio track alone "
              "carries dialogue, and any of a shot's own dialogue words appearing here "
              "hard-refuses the whole scene's production handover (LAW 6). Every card also "
              "needs a cinematographyContract. It records the production unit's governing "
              "story point of view, scale, "
              "lens intent, camera height, composition, depth, camera behaviour, focus, "
              "lighting function and palette function before reducing them to one concise, "
              "observable providerInstruction. These are choices for this story beat, never "
              "a lens checklist. Every card requires performanceBudget. Count emotional turns "
              "and prop-state changes, reserve explicit silent acting and landing time, estimate "
              "the minimum honest duration, and set decision=split-before-generation when the "
              "performance cannot breathe. Such a card is a redesign signal, not an approvable "
              "unit. Every cinematographyContract must also state emotionalDistanceStart, "
              "emotionalDistanceEnd, revealStrategy, performanceVisibility, editorialPurpose "
              "and memorableLandingImage. These express visual arc and performance need, not "
              "decorative coverage. Every card also requires storyIntent: narrative function, "
              "primary and secondary audience feeling, outer action, inner action, playable "
              "performance direction, what remains legible with sound muted, how the environment "
              "applies pressure, how sound deepens rather than rescues the beat, how the signed "
              "motif is used, and the exact change in thought that motivates the cut or hold. "
              "providerInstruction must not contain empty quality labels "
              "such as cinematic, beautiful, award-winning or Pixar."),
        f"THE SELECTED TREATMENT (the sequence must deliver ITS experience):\n"
        f"{treatment.model_dump_json()}\n\n"
        + (f"SIGNED EMOTIONAL STORY-TO-SCREEN CONTRACT:\n"
           f"{heart.model_dump_json()}\n\n" if heart else "")
        + f"GOVERNING AUDIENCE EXPERIENCE: {selection.governingAudienceExperience}\n\n"
        f"THE BEATS:\n" + "\n".join(b.model_dump_json() for b in sd.beats)
        + f"{notes}\n\nshotId = 'S{scene_num}.SH<n>' in sequence order.",
        ShotConference, label=f"gate4_shots_s{scene_num}")
    shots = [CreativeShotCard(**shot.model_dump()) for shot in sc.shots]
    packing = _validate_gate4_production_units(shots, sd.beats)
    for shot in shots:
        if not shot.cinematographyContract:
            raise RuntimeError(
                f"CINEMATOGRAPHY CONTRACT MISSING for {shot.shotId}")
        missing_visual_intent = [
            name for name in (
                "emotionalDistanceStart", "emotionalDistanceEnd", "revealStrategy",
                "performanceVisibility", "editorialPurpose", "memorableLandingImage")
            if not str(getattr(shot.cinematographyContract, name, "") or "").strip()
        ]
        if missing_visual_intent:
            raise RuntimeError(
                f"CINEMATOGRAPHY VISUAL INTENT MISSING for {shot.shotId}: "
                + ", ".join(missing_visual_intent))
        if not shot.performanceBudget:
            raise RuntimeError(f"PERFORMANCE BUDGET MISSING for {shot.shotId}")
        if not shot.storyIntent:
            raise RuntimeError(f"STORY INTENT MISSING for {shot.shotId}")
        provider_line = _norm(shot.cinematographyContract.providerInstruction)
        empty_labels = ("cinematic", "beautiful", "award winning", "pixar")
        if any(label in provider_line for label in empty_labels):
            raise RuntimeError(
                f"CINEMATOGRAPHY CONTRACT USES AN EMPTY QUALITY LABEL in {shot.shotId}")
    log(f"GATE 4 - {len(shots)} Seedance production unit(s): "
        + " ".join(f"{s.shotId}:{s.targetDurationSec}s/"
                    f"{len(s.stagePlan)}st[{'C' if s.transitionType=='CONTINUOUS' else 'K'}]"
                    for s in shots)
        + f"; {len(packing['fullThirtySecondUnitIds'])} full 30s, "
          f"{len(packing['mergeReviewRequired'])} merge review(s)")
    return shots


# ─────────────────────────────────────────────────────────────────────────────────────────
# GATE 5 — PERFORMANCE AND VOICE SYNTHESIS
# ─────────────────────────────────────────────────────────────────────────────────────────
def gate5_performance(episode, scene_num, treatment, sd, shots,
                      review_notes="", log=print):
    pp = cb_llm.structured_with_repair(
        _mind("DIRECTOR", ["directorTaste"],
              "The visual sequence now exists. Author each shot's PHYSICAL PERFORMANCE, "
              "ANIMATION TIMING and typed performanceContract. performanceContract.beatOwner "
              "must be one of that card's beatIds. Its phases are one to four UNIQUE, "
              "observable phases in anticipation/action/reaction/settle order; each performer "
              "is exactly one named participating character or ENVIRONMENT. Use only the "
              "phases genuinely present in this shot. physicalCauseAndEffect states the "
              "readable mechanics, visibleEmotionalTurn states what visibly changes, "
              "requiredLanding defines the final readable result, performanceFreedom leaves "
              "room for cadence, micro-reactions and secondary motion, and playableIntention "
              "records the acting thought for review. characterTruths records, for every "
              "named character who performs a phase, the locked canon trait under pressure, "
              "their playable want, pressure response, observable signature and why another "
              "character could not be substituted. Ground it in supplied canon and never "
              "invent backstory. Never use frame-by-frame timestamps. "
              "Performance arises from thought; physical cause and effect stays readable; "
              "weight, anticipation and follow-through are timed to the treatment's rhythm. "
              "physicalPerformance and animationTiming remain concise human review context. "
              "Every provider-executable performanceContract field must be concrete screen "
              "evidence, not psychology. physicalPerformance "
              "must NEVER quote or paraphrase a character's spoken line, even a fragment - "
              "describe only the body: what the character does before, during and after "
              "the line lands, never the words themselves. The same dialogue ban applies to "
              "every provider-executable performanceContract field (the audio track alone "
              "carries dialogue; a shot's own dialogue words appearing here hard-refuses the "
              "whole scene's production handover, LAW 6). Change NOTHING else on the cards - "
              "the sequence design is settled. Never rewrite or copy physicalStaging. Handover "
              "compiles every Gate 3 BIG-comedy staging mechanically into its packed unit. If "
              "a BIG beat legitimately crosses a unit boundary, performanceContract.beatOwner "
              "identifies the one unit carrying its physical payoff."),
        f"THE SELECTED TREATMENT:\n{treatment.model_dump_json()[:3000]}\n\n"
        f"THE BEAT EMOTION, COMEDY AND POWER CONTRACTS:\n"
        + "\n".join(b.model_dump_json() for b in sd.beats)
        + f"\n\nCHARACTER CANON:\n"
        + _characters_for(sorted({name for beat in sd.beats
                                  for name in beat.participatingCharacters}))[:10000]
        + f"\n\nTHE SHOT SEQUENCE:\n"
        + "\n".join(s.model_dump_json() for s in shots)
        + (f"\n\nVALIDATION REPAIR - return the complete performance pass again. "
           f"Do not change the shot sequence: {review_notes}" if review_notes else ""),
        PerformancePass, label=f"gate5_perf_s{scene_num}")
    expected_ids = [shot.shotId for shot in shots]
    returned_ids = [shot.shotId for shot in pp.shots]
    if returned_ids != expected_ids:
        raise RuntimeError(
            "PERFORMANCE PASS DROPPED/DUPLICATED/REORDERED shots - expected "
            f"{expected_ids}, got {returned_ids}")

    beats_by_id = {beat.beatId: beat for beat in sd.beats}
    big_beats = {
        beat.beatId: beat.comedyContract.physicalStaging
        for beat in sd.beats
        if beat.comedyContract and beat.comedyContract.mode == "BIG"
    }
    by_id = {s.shotId: s for s in shots}
    for s in pp.shots:
        d0 = by_id.get(s.shotId)
        if not d0 or not s.performanceContract:
            raise RuntimeError(f"PERFORMANCE CONTRACT MISSING for {s.shotId}")
        if not (s.physicalPerformance or "").strip() or not (s.animationTiming or "").strip():
            raise RuntimeError(f"PERFORMANCE REVIEW CONTEXT MISSING for {s.shotId}")
        contract = s.performanceContract
        if contract.beatOwner not in d0.beatIds:
            raise RuntimeError(
                f"PERFORMANCE CONTRACT CROSSED BEATS - {s.shotId} names "
                f"{contract.beatOwner}, expected one of {d0.beatIds}")
        allowed = []
        for beat_id in d0.beatIds:
            beat = beats_by_id.get(beat_id)
            if beat is None:
                raise RuntimeError(
                    f"PERFORMANCE CONTRACT UNKNOWN BEAT - {s.shotId} names {beat_id}")
            for character in beat.participatingCharacters:
                if character not in allowed:
                    allowed.append(character)
        allowed_norm = {_norm(character) for character in allowed}
        truth_names = [truth.character for truth in contract.characterTruths]
        if len(truth_names) != len({_norm(name) for name in truth_names}):
            raise RuntimeError(
                f"PERFORMANCE CONTRACT DUPLICATED CHARACTER TRUTH in {s.shotId}")
        for truth in contract.characterTruths:
            if _norm(truth.character) not in allowed_norm:
                message = (
                    f"PERFORMANCE CONTRACT UNKNOWN CHARACTER TRUTH - {s.shotId} names "
                    f"{truth.character}; every characterTruth and phase performer must be "
                    f"one of {allowed} or ENVIRONMENT for this shot"
                )
                if not review_notes:
                    log(f"  [director] gate5_perf_s{scene_num}: {message} - rerunning once",
                        flush=True)
                    return gate5_performance(
                        episode, scene_num, treatment, sd, shots,
                        review_notes=message, log=log)
                raise RuntimeError(message)
        performing_characters = {
            _norm(phase.performer) for phase in contract.phases
            if _norm(phase.performer) != "environment"
        }
        if performing_characters - {_norm(name) for name in truth_names}:
            raise RuntimeError(
                f"PERFORMANCE CONTRACT MISSING CHARACTER TRUTH for {s.shotId}")
        for phase in contract.phases:
            if (_norm(phase.performer) not in allowed_norm and
                    _norm(phase.performer) != "environment"):
                raise RuntimeError(
                    f"PERFORMANCE CONTRACT UNKNOWN PERFORMER - {s.shotId} names "
                    f"{phase.performer}; allowed: {allowed} or ENVIRONMENT")
        execution = cb_engine.compile_performance_contract(contract.model_dump())
        locked_dialogue = [occ.exactText for beat_id in d0.beatIds
                           for occ in beats_by_id[beat_id].dialogueOccurrences]
        leaked = [line for line in locked_dialogue
                  if line.strip() and line.casefold() in execution.casefold()]
        if leaked:
            raise RuntimeError(
                f"PERFORMANCE CONTRACT QUOTED LOCKED DIALOGUE in {s.shotId}: {leaked[0]!r}")
        # Only Gate-5-owned fields may change; every Gate-4 field remains on d0 untouched.
        d0.physicalPerformance = s.physicalPerformance
        d0.animationTiming = s.animationTiming
        d0.performanceContract = contract

    carriers_by_beat = {}
    for beat_id, staging in big_beats.items():
        eligible = [shot for shot in shots if beat_id in shot.beatIds]
        if not eligible:
            raise RuntimeError(
                f"BIG COMEDY STAGING HAS NO PACKED UNIT - {beat_id}")
        if len(eligible) == 1:
            carrier = eligible[0]
        else:
            owned = [shot for shot in eligible if shot.performanceContract and
                     shot.performanceContract.beatOwner == beat_id]
            if len(owned) != 1:
                raise RuntimeError(
                    f"BIG COMEDY STAGING CARRIER AMBIGUOUS - {beat_id} crosses "
                    f"{len(eligible)} units and has {len(owned)} performance owners")
            carrier = owned[0]
        carriers_by_beat[beat_id] = carrier.shotId

    # Keep the legacy singular mirror honest without pretending it can represent every BIG
    # beat in a multi-beat unit. The authoritative contracts remain on the beats above.
    for shot in shots:
        contract = shot.performanceContract
        if not contract:
            continue
        contract.comedyStaging = None
        owner = contract.beatOwner
        if owner in big_beats and carriers_by_beat.get(owner) == shot.shotId:
            contract.comedyStaging = big_beats[owner].model_copy(deep=True)
    return shots


def gate5_voice(episode, scene_num, sd, shots, log=print):
    beats, _ = _script_beats(episode, scene_num)
    lines = _locked_dialogue(beats)
    if not lines:
        return []
    vs = cb_llm.structured(
        _mind("VOICE DIRECTOR", ["voiceTaste"],
              "Transform each locked line into truthful, character-specific vocal acting "
              "for ElevenLabs v3, RECONCILED with the body: the physical performance below "
              "is what the character is doing while speaking. What does the character want "
              "FROM THE LISTENER; what changes during the line; which words carry "
              "intention; where do they breathe or hesitate. Every v3 tag has a dramatic "
              "purpose. Dialogue never automatically starts at frame one — its timing may "
              "shape editorial rhythm, but never replaces the selected treatment."),
        f"THE SHOTS (body + timing to reconcile with):\n"
        + "\n".join(f"{s.shotId}: {s.principalPerformance} | body: {s.physicalPerformance} "
                     f"| timing: {s.animationTiming}" for s in shots)
        + "\n\nTHE LOCKED OCCURRENCES (return exactly this order and copy every ID, "
          "speaker and exactDialogue VERBATIM):\n"
        + "\n".join(
            (f"{line['dialogueOccurrenceId']} | {line['sourceEventId']} | "
             f"{line['speaker']}: {line['exactText']}")
            if isinstance(line, dict) else f"{line[0]}: {line[1]}"
            for line in lines),
        VoiceScript, label=f"gate5_voice_s{scene_num}")
    if len(vs.performances) != len(lines):
        raise RuntimeError(
            f"VOICE PASS DROPPED/DUPLICATED a locked occurrence: expected {len(lines)}, "
            f"got {len(vs.performances)}")
    for index, (voice, locked) in enumerate(zip(vs.performances, lines), start=1):
        if isinstance(locked, dict):
            speaker, exact_text = locked["speaker"], locked["exactText"]
            occurrence_id = locked["dialogueOccurrenceId"]
            # Provider output may preserve the immutable digest while dropping this
            # repository-owned namespace. Restore the namespace mechanically; never ask
            # a creative model to author source identity.
            if (voice.dialogueOccurrenceId and
                    occurrence_id.endswith(voice.dialogueOccurrenceId) and
                    occurrence_id.rsplit(voice.dialogueOccurrenceId, 1)[0] ==
                    "dialogue-occurrence:"):
                voice.dialogueOccurrenceId = occurrence_id
            if voice.dialogueOccurrenceId != occurrence_id:
                raise RuntimeError(
                    f"VOICE PASS CHANGED/REORDERED occurrence {index}: expected "
                    f"{occurrence_id}, got {voice.dialogueOccurrenceId or 'missing ID'}")
            voice.sourceEventId = locked["sourceEventId"]
            voice.sourceEventIndex = locked["sourceEventIndex"]
            voice.beatId = locked["beatId"]
            voice.sourceBeatId = locked["sourceBeatId"]
        else:  # Legacy unit-fixture compatibility; canonical packages never use this path.
            speaker, exact_text = locked
        if (voice.speaker.strip() != str(speaker).strip() or
                voice.exactDialogue.strip() != str(exact_text).strip()):
            raise RuntimeError(
                f"VOICE PASS DROPPED/REWORDED locked occurrence {index}: expected "
                f"{speaker}: {exact_text!r}, got {voice.speaker}: {voice.exactDialogue!r}")
    return vs.performances


# ─────────────────────────────────────────────────────────────────────────────────────────
# GATE 6 — ADVERSARIAL SHOWRUNNER REVIEW
# ─────────────────────────────────────────────────────────────────────────────────────────
def gate6_adversarial_review(vision, selection, treatment, sd, shots, voices,
                             heart=None, log=print):
    packing = cb_unit_packing.audit_units(shots)
    review = cb_llm.structured(
        _mind("SHOWRUNNER", ["showrunnerTaste"],
              "ACTIVELY ATTEMPT TO REJECT this storyboard. Judge the COMPLETE scene, not "
              "isolated shot quality, for: repeated coverage patterns; repeated reaction-"
              "shot grammar; fixed staging; safe camera behaviour; unnecessary keyframes; "
              "excessive cutting; excessive continuity; overfilled shot cards; decorative "
              "micro-expression; loss of the selected audience experience; and generic "
              "solutions that could belong to another show. COMPARE the result against the "
              "SELECTED WHOLE-SCENE TREATMENT (treatmentComparison) — internal consistency "
              "alone is NOT enough; if the storyboard has lost the treatment's central "
              "experience, fail it and set returnTo to 'gate3' (beat architecture is wrong) "
              "or 'gate4' (the shot sequence is wrong). Audit provider packing as a separate "
              "decision. Reject emotional posturing: the child-clear want, relationship engine, "
              "ordinary-life truth, costly choice and final after-feeling must be visible in "
              "accumulated behaviour. Reject motifs, music, colour or environment that decorate "
              "without carrying the signed emotional argument. At least one important beat must "
              "remain legible muted, and cuts must follow changes in thought rather than line ends. "
              "decision. Seedance 2.5 can carry a complete 30-second arc with internal cuts, "
              "so reject avoidable joins: if two adjacent units total 30 seconds or less, "
              "accept the split only when its named boundary protects a real location/time, "
              "reference, continuity, dramatic or complexity requirement. Prefer one full "
              "30-second request when it safely carries setup, development, escalation and "
              "payoff; never approve empty padding. State packingJudgement and packingPasses. "
              "If packingPasses is false, passes must be false and returnTo must be gate4. "
              "Never request wording patches. Give a WRITTEN judgement — never a score."),
        f"THE SELECTED TREATMENT (the contract this scene must deliver):\n"
        f"{treatment.model_dump_json()}\n\n"
        + (f"SIGNED EMOTIONAL STORY-TO-SCREEN CONTRACT:\n"
           f"{heart.model_dump_json()}\n\n" if heart else "")
        + f"GOVERNING EXPERIENCE: {selection.governingAudienceExperience}\n\n"
        f"EPISODE VISION:\n{json.dumps(vision, ensure_ascii=False)[:3500]}\n\n"
        f"BEATS:\n" + "\n".join(b.model_dump_json()[:1600] for b in sd.beats)
        + "\n\nSHOTS:\n" + "\n".join(s.model_dump_json()[:1800] for s in shots)
        + "\n\nDETERMINISTIC 30-SECOND PACKING AUDIT:\n"
        + json.dumps(packing, ensure_ascii=False, indent=1)
        + "\n\nVOICE:\n" + "\n".join(v.model_dump_json()[:1100] for v in voices),
        ShowrunnerReview, label="gate6_review")
    if not review.packingPasses:
        review.passes = False
        review.returnTo = "gate4"
        if not any(issue.target == "unit-packing" for issue in review.issues):
            review.issues.append(ReviewIssue(
                role="director", target="unit-packing", issue=review.packingJudgement))
    return review


def _assign_dialogue_occurrences(shots, voices, details):
    """Validate the typed occurrence-to-shot partition; infer only a unique placement."""
    detail_by_id = {detail.shotId: detail for detail in details}
    shot_by_id = {shot.shotId: shot for shot in shots}
    expected = [voice.dialogueOccurrenceId for voice in voices]
    if any(not occurrence_id for occurrence_id in expected):
        raise RuntimeError(
            "DIALOGUE CONTRACT MISSING — every VoicePerformance must carry its immutable "
            "dialogueOccurrenceId before Production Detail")
    if len(expected) != len(set(expected)):
        raise RuntimeError("DIALOGUE CONTRACT DUPLICATED a VoicePerformance occurrence ID")

    # A model omission may be repaired only where structure proves one destination. Text
    # matching is a secondary unique signal, never an identity and never an ambiguity tie-break.
    assigned = [oid for detail in details for oid in detail.dialogueOccurrenceIds]
    if expected and not assigned:
        for voice in voices:
            eligible = [shot for shot in shots if voice.beatId in shot.beatIds]
            quoted = [shot for shot in eligible
                      if voice.exactDialogue and voice.exactDialogue in
                      (detail_by_id.get(shot.shotId).dialogueTiming
                       if detail_by_id.get(shot.shotId) else "")]
            targets = quoted if len(quoted) == 1 else eligible
            if len(targets) != 1:
                raise RuntimeError(
                    f"DIALOGUE ASSIGNMENT AMBIGUOUS — {voice.dialogueOccurrenceId} can land "
                    f"on {[shot.shotId for shot in eligible]}; Production Detail must name "
                    "the occurrence ID explicitly")
            detail_by_id[targets[0].shotId].dialogueOccurrenceIds.append(
                voice.dialogueOccurrenceId)

    assigned_in_shot_order = []
    owner_by_id = {voice.dialogueOccurrenceId: voice.beatId for voice in voices}
    for shot in shots:
        detail = detail_by_id.get(shot.shotId)
        if detail is None:
            continue
        normalized_ids = []
        for occurrence_id in detail.dialogueOccurrenceIds:
            matches = [expected_id for expected_id in expected
                       if expected_id.endswith(occurrence_id)]
            if occurrence_id not in owner_by_id and len(matches) == 1:
                occurrence_id = matches[0]
            normalized_ids.append(occurrence_id)
        detail.dialogueOccurrenceIds = normalized_ids
        for occurrence_id in normalized_ids:
            if occurrence_id not in owner_by_id:
                raise RuntimeError(
                    f"DIALOGUE ASSIGNMENT UNKNOWN — {shot.shotId} names {occurrence_id}")
            if owner_by_id[occurrence_id] not in shot_by_id[shot.shotId].beatIds:
                raise RuntimeError(
                    f"DIALOGUE ASSIGNMENT CROSSED BEATS — {occurrence_id} belongs to "
                    f"{owner_by_id[occurrence_id]}, not {shot.shotId}")
            assigned_in_shot_order.append(occurrence_id)
    if assigned_in_shot_order != expected:
        raise RuntimeError(
            "DIALOGUE ASSIGNMENT DROPPED/DUPLICATED/REORDERED occurrences — expected "
            f"{expected}, got {assigned_in_shot_order}")
    return details


# ─────────────────────────────────────────────────────────────────────────────────────────
# PRODUCTION DETAIL — added ONLY after the creative sequence passes
# ─────────────────────────────────────────────────────────────────────────────────────────
def production_detail(episode, scene_num, sd, shots, voices, log=print, shot_cast=None,
                       opener_shot_id=None):
    """Author the executable production layer without changing an approved creative card.
    The true opener is identified by ID so a scoped regeneration cannot accidentally erase
    a later shot's inherited state. Missing details, boundary fields, cast members or timing
    windows refuse; no fallback content is invented."""
    if shot_cast is None:
        if sd is None:
            raise RuntimeError("SHOT CAST REQUIRED - Production Detail cannot infer visible "
                               "characters without SceneDirection")
        beats_by_id = {beat.beatId: beat for beat in sd.beats}
        shot_cast = {}
        for shot in shots:
            cast = []
            for beat_id in shot.beatIds:
                beat = beats_by_id.get(beat_id)
                if beat is None:
                    raise RuntimeError(
                        f"SHOT CAST UNKNOWN BEAT - {shot.shotId} names {beat_id}")
                for character in beat.participatingCharacters:
                    if character not in cast:
                        cast.append(character)
            shot_cast[shot.shotId] = cast

    expected_shot_ids = [shot.shotId for shot in shots]
    if set(shot_cast) != set(expected_shot_ids):
        raise RuntimeError(
            "SHOT CAST CONTRACT MISMATCH - expected entries for "
            f"{expected_shot_ids}, got {list(shot_cast)}")
    real_opener = opener_shot_id or (shots[0].shotId if shots else None)
    cast_block = (
        "\n\nTRUE SCENE OPENER (continuityInState must be null only here):\n"
        f"{real_opener}\n\nSHOT CAST (every non-null boundary must contain EXACTLY these "
        "character IDs, with explicit empty lists when there are no marks or props):\n"
        + "\n".join(f"{sid}: {', '.join(names) or '(none)'}"
                    for sid, names in shot_cast.items()))
    pd = cb_llm.structured(
        _mind("DIRECTOR AND CINEMATOGRAPHER, PRODUCTION PASS",
              ["directorTaste", "cinematographyTaste"],
              "The creative sequence has PASSED. Add the production layer only: "
              "human-readable continuityIn/Out and dialogueTiming review prose; typed "
              "continuityInState/continuityOutState; numeric dialogueTimings; reference "
              "roles (which references anchor identity/environment); and AT MOST three "
              "genuinely provider-essential "
              "protections - only "
              "what would invalidate the shot if violated, never a constraint wall. "
              "The system derives requiresNewKeyframe from the approved transition and "
              "intendedDurationRange from the locked targetDurationSec; never author either. "
              "Keep every numeric dialogue window inside that card's locked duration and "
              "never re-author the performance itself. "
              "continuityIn and continuityInState are ONLY what genuinely carry in from the shot immediately "
              "before this one — a mark, a position, an environmental state left over from "
              "what just happened. It is NEVER a second description of THIS shot's own "
              "opening image or action; openingImage already owns that, on the creative "
              "card, and this field must not compete with it. If nothing meaningfully "
              "carries in (this shot opens a new beat of action clean), say so briefly "
              "rather than inventing continuity that doesn't exist. The TRUE SCENE OPENER "
              "alone uses continuityInState=null. Every other incoming boundary and every "
              "outgoing boundary names lighting, cameraSide and EXACTLY the supplied cast; "
              "each character has separate screenZone, facing, pose, expression, "
              "visibleMarks and heldProps values. Never duplicate one sentence across those "
              "fields. Add nothing creative; change nothing creative. For every "
              "VoicePerformance, assign its dialogueOccurrenceId to exactly one owning "
              "shot's dialogueOccurrenceIds list and author one matching numeric "
              "dialogueTimings window inside that shot. The two ID lists must be identical "
              "and in the same order. Preserve occurrence order; repeated identical words "
              "remain separate IDs."),
        f"THE SHOTS (physicalPerformance/animationTiming are ALREADY APPROVED — ground the "
        f"duration in them, never rewrite them):\n"
        + "\n".join(s.model_dump_json() for s in shots)
        + "\n\nVOICE TIMINGS (locked dialogue — ground dialogue-bearing shots' duration in "
          "these):\n"
        + "\n".join(f"{v.dialogueOccurrenceId} | beat {v.beatId} | {v.speaker}: "
                    f"{v.exactDialogue} | {v.expectedTiming}" for v in voices)
        + cast_block,
        ProductionPass, label=f"production_detail_s{scene_num}")
    returned_ids = [detail.shotId for detail in pd.details]
    if returned_ids != expected_shot_ids:
        raise RuntimeError(
            "PRODUCTION DETAIL DROPPED/DUPLICATED/REORDERED shots - expected "
            f"{expected_shot_ids}, got {returned_ids}")
    by_id = {detail.shotId: detail for detail in pd.details}
    out = []
    for s in shots:
        is_opener = (s.shotId == real_opener)
        if s.targetDurationSec is None:
            raise RuntimeError(
                f"PRODUCTION UNIT DURATION MISSING - {s.shotId}")
        draft = by_id[s.shotId]
        authored = {
            field: getattr(draft, field)
            for field in ProductionDetailDraft.model_fields
        }
        d = ProductionDetail(
            **authored,
            requiresNewKeyframe=is_opener or (s.transitionType == "PLANNED_CUT"),
            intendedDurationRange=f"{s.targetDurationSec}-{s.targetDurationSec}s",
        )
        if is_opener:
            d.continuityIn = ""
            d.continuityInState = None
        elif d.continuityInState is None:
            raise RuntimeError(
                f"CONTINUITY CONTRACT MISSING - only {real_opener} may have null "
                f"continuityInState; {s.shotId} must carry its inherited boundary")
        out.append(d)
    out = _assign_dialogue_occurrences(shots, voices, out)
    _validate_typed_production_contract(
        shots, out, shot_cast, real_opener)
    return out


# ─────────────────────────────────────────────────────────────────────────────────────────
# DURATION CREDIBILITY (2026-07-17 schema checkpoint) — every shot's range validated,
# never silently accepted; the scene total is a SUM, never invented
# ─────────────────────────────────────────────────────────────────────────────────────────
_DURATION_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*s\s*$")


def _duration_bounds(rng):
    m = _DURATION_RE.match(rng or "")
    if not m:
        return None
    lo, hi = float(m.group(1)), float(m.group(2))
    return (lo, hi) if 0 < lo <= hi else None


def _validate_typed_production_contract(shots, details, shot_cast, real_opener):
    """Validate the typed execution contract before it can be approved or signed."""
    detail_by_id = {detail.shotId: detail for detail in details}
    previous_shot = None
    previous_detail = None
    for shot in shots:
        detail = detail_by_id[shot.shotId]
        expected_cast = list(shot_cast[shot.shotId])
        states = [("continuityOutState", detail.continuityOutState)]
        if detail.continuityInState is not None:
            states.insert(0, ("continuityInState", detail.continuityInState))
        elif shot.shotId != real_opener:
            raise RuntimeError(
                f"CONTINUITY CONTRACT MISSING - {shot.shotId}.continuityInState")
        for field_name, state in states:
            actual = [character.characterId for character in state.characters]
            if set(actual) != set(expected_cast) or len(actual) != len(expected_cast):
                raise RuntimeError(
                    f"CONTINUITY CAST MISMATCH - {shot.shotId}.{field_name} expected "
                    f"exactly {expected_cast}, got {actual}")

        occurrence_ids = list(detail.dialogueOccurrenceIds)
        timing_ids = [window.dialogueOccurrenceId for window in detail.dialogueTimings]
        if timing_ids != occurrence_ids:
            raise RuntimeError(
                f"DIALOGUE TIMING CONTRACT MISMATCH - {shot.shotId} assignments are "
                f"{occurrence_ids}, timing windows are {timing_ids}")
        try:
            duration = cb_engine.normalize_duration_range(detail.intendedDurationRange)
        except ValueError as exc:
            raise RuntimeError(f"DURATION CONTRACT INVALID - {shot.shotId}: {exc}") from exc
        if (shot.targetDurationSec is not None and
                duration != float(shot.targetDurationSec)):
            raise RuntimeError(
                f"DURATION CONTRACT CHANGED STORY TIMING - {shot.shotId} targets "
                f"{shot.targetDurationSec}s but {detail.intendedDurationRange!r} normalizes "
                f"to {duration:g}s")
        for window in detail.dialogueTimings:
            if window.endSec > duration:
                raise RuntimeError(
                    f"DIALOGUE TIMING OVERRUN - {window.dialogueOccurrenceId} ends at "
                    f"{window.endSec}s in {shot.shotId}'s {duration}s provider duration")

        if previous_detail is not None and detail.continuityInState is not None:
            if shot.transitionType == "CONTINUOUS":
                if (detail.continuityInState.model_dump() !=
                        previous_detail.continuityOutState.model_dump()):
                    raise RuntimeError(
                        f"CONTINUOUS JOIN DRIFT - {shot.shotId}.continuityInState must "
                        f"exactly equal {previous_shot.shotId}.continuityOutState")
            else:
                prior_characters = {
                    character.characterId: character
                    for character in previous_detail.continuityOutState.characters}
                for character in detail.continuityInState.characters:
                    prior = prior_characters.get(character.characterId)
                    if prior is None:
                        continue
                    if (prior.visibleMarks != character.visibleMarks or
                            prior.heldProps != character.heldProps):
                        raise RuntimeError(
                            f"CUT CONTINUITY DRIFT - {character.characterId}'s marks/props "
                            f"change between {previous_shot.shotId} and {shot.shotId}")
        previous_shot = shot
        previous_detail = detail


def validate_duration_ranges(details, log=print):
    """Every ProductionDetail's intendedDurationRange must parse as 'N-Ms' with a
    credible, positive, non-inverted bound. Reports each shot plus the summed scene
    range — never invents a total when a shot fails, and never silently accepts a
    malformed value."""
    rows, invalid, lo_sum, hi_sum = [], [], 0.0, 0.0
    for d in details:
        b = _duration_bounds(d.intendedDurationRange)
        if b is None:
            invalid.append(d.shotId)
            rows.append({"shotId": d.shotId, "range": d.intendedDurationRange,
                         "valid": False})
            continue
        lo, hi = b
        lo_sum += lo
        hi_sum += hi
        rows.append({"shotId": d.shotId, "range": d.intendedDurationRange, "valid": True,
                     "loSec": lo, "hiSec": hi})
    total = {"loSec": round(lo_sum, 1), "hiSec": round(hi_sum, 1),
             "formatted": f"{lo_sum:.0f}-{hi_sum:.0f}s", "allValid": not invalid}
    if invalid:
        log(f"DURATION VALIDATION — {len(invalid)} shot(s) FAILED credibility: {invalid}")
    else:
        log(f"DURATION VALIDATION — all {len(rows)} shot(s) credible; scene total "
            f"{total['formatted']}")
    return {"perShot": rows, "invalidShotIds": invalid, "sceneTotal": total}


def _shots_hash(pkg):
    """The Creative Shot Cards' own content hash — proves a production-detail-only
    regeneration touched nothing creative."""
    return hashlib.sha256(json.dumps(pkg.get("shots", []), sort_keys=True,
                                      ensure_ascii=False).encode()).hexdigest()


def regenerate_production_detail(storyboard_path, out_path, log=print, only_shot_id=None):
    """Regenerates ONLY ProductionDetail (now including intendedDurationRange) from a
    FROZEN, already Gate-6-passed, already Gate-A-approved storyboard's Creative Shot
    Cards — never reruns Gates 0-4, never revises a shot, never generates a new
    treatment. Proves the creative cards are byte-for-byte unchanged via _shots_hash
    before/after, and refuses (raises) if they ever differ.

    only_shot_id (2026-07-17, item 3): when given, regenerates a SINGLE shot's own
    Production Detail only — every sibling shot's stored ProductionDetail is carried
    forward completely UNCHANGED (not re-authored, not re-validated in isolation; the
    combined durationValidation still covers the whole scene's own already-stored ranges).
    Used for a scoped, single-shot correction (Julian's directive: "Regenerate only
    S1.SH1's Production Detail from its unchanged approved Creative Card") without
    re-authoring the rest of the scene's production layer as a side effect."""
    src = json.load(open(storyboard_path))
    before_hash = _shots_hash(src)
    episode, scene_num = src["episodeId"], src["sceneNumber"]
    all_shots = [CreativeShotCard(**s) for s in src["shots"]]
    voices = [VoicePerformance(**v) for v in src.get("voicePerformances", [])]
    beats_all = {b["beatId"]: b for b in src.get("beats", [])}

    if only_shot_id:
        shots = [s for s in all_shots if s.shotId == only_shot_id]
        if not shots:
            raise ValueError(f"{only_shot_id} not found in the approved storyboard.")
    else:
        shots = all_shots

    shot_cast = {}
    for s in shots:
        cast = []
        for bid in s.beatIds:
            for c in beats_all.get(bid, {}).get("participatingCharacters", []):
                if c not in cast:
                    cast.append(c)
        shot_cast[s.shotId] = cast

    # the REAL scene-opener's shotId, from the FULL shot list — never assumed from
    # position within a possibly-scoped-down `shots` subset (only_shot_id may name a
    # later, non-opener shot; see production_detail's own opener_shot_id docstring)
    details = production_detail(episode, scene_num, None, shots, voices, log=log,
                                 shot_cast=shot_cast, opener_shot_id=all_shots[0].shotId)
    new_by_id = {d.shotId: d for d in details}

    existing = [ProductionDetail(**p) for p in src.get("productionDetail", [])]
    if only_shot_id:
        # every sibling's own ProductionDetail passes through byte-identical; ONLY the
        # named shot's entry is replaced by the freshly regenerated one
        merged = [new_by_id.get(d.shotId, d) for d in existing]
        if not any(d.shotId == only_shot_id for d in existing):
            merged.append(new_by_id[only_shot_id])
    else:
        merged = details
    validation = validate_duration_ranges(merged, log=log)

    out = json.loads(json.dumps(src))              # deep copy — the frozen source untouched
    out["productionDetail"] = [d.model_dump() for d in merged]
    out["durationValidation"] = validation
    if "approvalState" in out.get("scene", {}):     # travels the Gate-A ambiguity fix
        out["scene"]["sourceApprovalState"] = out["scene"].pop("approvalState")

    after_hash = _shots_hash(out)
    if before_hash != after_hash:
        raise RuntimeError(
            "REFUSED — creative shot cards changed during a production-detail-only "
            "regeneration; this must never happen. No file written.")
    out["creativeCardHashCheck"] = {"before": before_hash, "after": after_hash,
                                     "unchanged": True}
    if only_shot_id:
        out["singleShotRegeneration"] = {"shotId": only_shot_id,
                                          "siblingsUnchanged": [d.shotId for d in existing
                                                                 if d.shotId != only_shot_id]}
    pathlib.Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(out_path, "w"), indent=1, ensure_ascii=False)
    log(f"PRODUCTION DETAIL REGENERATED — {out_path}"
        + (f" (single shot: {only_shot_id})" if only_shot_id else "")
        + f"; creative-card hash unchanged ({before_hash[:12]}…); "
        f"scene total {validation['sceneTotal']['formatted']}")
    return out


# ─────────────────────────────────────────────────────────────────────────────────────────
# THE SCENE RUN — Gates 0-6 + production detail
# ─────────────────────────────────────────────────────────────────────────────────────────
def run_scene(scene_num, episode="Ep1", brief=None, log=print):
    ready = gate0_readiness(episode, scene_num, brief, log=log)
    source_pkg = ready["scriptPackage"]
    vpath = OUT / f"{episode}_episode_vision.json"
    vision = (json.load(open(vpath)) if vpath.exists() else episode_vision(episode, log=log))
    beat_signature = cb_lineage.beat_package_signature(source_pkg)
    script_version = (source_pkg.get("sourceScript") or {}).get("scriptVersionId")
    story_canon_digest = cb_canon.profile_digest(
        "story", episode=episode, cast=ready["cast"], root=ROOT)
    vision_inputs = cb_lineage.episode_vision_inputs(
        script_version, beat_signature, story_canon_digest)
    if not cb_lineage.signature_matches(vision.get("inputSignature"),
                                        "episode-vision", vision_inputs):
        raise RuntimeError(
            "STALE EPISODE VISION — it was not authored from the active immutable script and "
            "canonical beat package. Rebuild Story & Direction before directing this scene.")

    heart = emotional_story_contract(episode, scene_num, vision, ready, log=log)
    treatments = gate1_treatments(episode, scene_num, vision, ready, heart=heart, log=log)
    selection = gate2_select(vision, treatments, ready, heart=heart, log=log)
    treatment = _selected_treatment(treatments, selection)

    sd = gate3_beats(episode, scene_num, vision, selection, treatment, ready,
                     heart=heart, log=log)
    shots = gate4_shot_conference(episode, scene_num, selection, treatment, sd,
                                  heart=heart, log=log)
    shots = gate5_performance(episode, scene_num, treatment, sd, shots, log=log)
    voices = gate5_voice(episode, scene_num, sd, shots, log=log)

    review, revisions = None, []
    for attempt in range(MAX_INTERNAL_REVISIONS + 1):
        review = gate6_adversarial_review(vision, selection, treatment, sd, shots, voices,
                                           heart=heart, log=log)
        log(f"GATE 6 — {'accepts' if review.passes else 'REJECTS'}: {review.judgement[:140]}")
        if review.passes or attempt == MAX_INTERNAL_REVISIONS:
            break
        notes = "; ".join(f"[{i.role}->{i.target}] {i.issue}" for i in review.issues[:4]) \
                or review.judgement[:400]
        revisions.append({"returnTo": review.returnTo or "gate4", "notes": notes,
                           "at": _now()})
        if (review.returnTo or "gate4") == "gate3":     # complete re-architecture
            sd = gate3_beats(episode, scene_num, vision, selection, treatment, ready,
                              heart=heart, review_notes=notes, log=log)
        shots = gate4_shot_conference(episode, scene_num, selection, treatment, sd,
                                        heart=heart, review_notes=notes, log=log)
        shots = gate5_performance(episode, scene_num, treatment, sd, shots, log=log)
        voices = gate5_voice(episode, scene_num, sd, shots, log=log)

    escalation, details = None, []
    if review and not review.passes:
        escalation = ("UNRESOLVED after the permitted complete creative revisions — "
                      "escalated for human direction, not endlessly rewritten: "
                      + (("; ".join(i.issue for i in review.issues[:3])) or
                          review.judgement[:400]))
        log("ESCALATION — " + escalation)
    else:
        details = production_detail(episode, scene_num, sd, shots, voices, log=log)

    storyboard_inputs = {
        "scriptVersionId": script_version,
        "beatPackageDigest": beat_signature["digest"],
        "episodeVisionDigest": vision["inputSignature"]["digest"],
        "sceneNumber": str(scene_num),
        "ambitionBrief": ready["brief"],
        "canonProfileDigest": ready["envelope"]["canonLock"]["profileDigest"],
        "canonSources": (ready.get("envelope") or {}).get("sources", {}),
    }
    packing_audit = cb_unit_packing.audit_units(shots)
    pkg = {"episodeId": episode, "sceneNumber": str(scene_num),
           "engineVersion": ENGINE_VERSION, "canonVersion": CANON_VERSION,
           "unitPackingContractVersion": UNIT_PACKING_CONTRACT_VERSION,
           "creativeDirectingStandardVersion": CREATIVE_DIRECTING_STANDARD_VERSION,
           "builtAt": _now(), "vision": vision,
           "emotionalStoryToScreenContract": heart.model_dump(),
           "sourceScript": source_pkg.get("sourceScript"),
           "sourceBeatPackage": {"path": str(_script_package(episode).relative_to(ROOT)),
                                 "contentSignature": beat_signature},
           "canonLock": ready["envelope"]["canonLock"],
           "inputSignature": cb_lineage.dependency_signature(
               "scene-storyboard", storyboard_inputs),
           "ambitionBrief": ready["brief"],
           "canonCompletionProposal": ready["canonCompletionProposal"],
           "directedOnEstablishedCanonOnly": True,
           "treatments": [t.model_dump() for t in treatments],
           "treatmentSelection": selection.model_dump(),
           "scene": sd.scene.model_dump(),
           "beats": [b.model_dump() for b in sd.beats],
           "shots": [s.model_dump() for s in shots],
           "unitPackingAudit": packing_audit,
           "productionDetail": [d.model_dump() for d in details],
           "voicePerformances": [v.model_dump() for v in voices],
           "dialogueContract": _scene_dialogue_contract(sd.beats, voices, details),
           "showrunnerJudgement": review.judgement if review else "",
           "treatmentComparison": review.treatmentComparison if review else "",
           "packingJudgement": review.packingJudgement if review else "",
           "packingPasses": bool(review and review.packingPasses),
           "internalRevisions": revisions, "escalation": escalation,
           "provenance": {"showrunner": PROV("showrunner"), "director": PROV("director"),
                           "cinematographer": PROV("cinematographer"),
                           "voice": PROV("voice-director")},
           "approvalState": "awaiting-human-storyboard-approval"}
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{episode}_scene{scene_num}_storyboard.json"
    json.dump(pkg, open(out, "w"), indent=1, ensure_ascii=False)
    log(f"STORYBOARD v2 — scene {scene_num}: {len(sd.beats)} beat(s), "
        f"{len(shots)} Seedance unit(s), "
        f"{len(packing_audit['fullThirtySecondUnitIds'])} full 30s, "
        f"{sum(1 for s in shots if s.transitionType == 'PLANNED_CUT')} keyframe shot(s), "
        f"{len(voices)} voice performance(s) -> {out.name}")
    return pkg


# ─────────────────────────────────────────────────────────────────────────────────────────
# MIGRATION (unchanged from v1 — gaps are reported, never filled)
# ─────────────────────────────────────────────────────────────────────────────────────────
_PERF_FIELDS = ["consciousDesire", "hiddenEmotionalNeed", "primaryFear", "insecurity",
                "protectiveMask", "comicEngine", "emotionalEngine", "defaultPosture",
                "centreOfGravity", "silhouette", "movementRhythm", "gestureScale",
                "gazeBehaviour", "facialOpennessOrRestraint", "personalSpace",
                "responseToPressure", "responseToEmbarrassment", "responseToSuccess",
                "responseToFailure", "recoveryBehaviour", "useOfStillness",
                "emotionalTells", "neverWithoutStoryReason"]

_BIBLE_MAP = {
    "consciousDesire": ("bible", "want"), "hiddenEmotionalNeed": ("bible", "need"),
    "comicEngine": ("bible", "comedyEngine"), "emotionalEngine": ("bible", "essence"),
    "movementRhythm": ("bible", "motionRule"), "defaultPosture": ("bible", "staging"),
    "responseToFailure": ("bible", "arc"), "emotionalTells": ("bible", "mannerisms"),
}


def migrate(episode="Ep1", log=print):
    chars = json.load(open(_CANON_SOURCES["characters"]))
    perf, gaps = {}, []
    for name, rec in chars.items():
        if not isinstance(rec, dict) or not rec.get("bible"):
            continue
        entry = {"provenance": {"source": "shows/crystal-bears/canon/characters.json",
                                  "method": "mechanical field mapping", "at": _now()}}
        for field in _PERF_FIELDS:
            src = _BIBLE_MAP.get(field)
            val = (rec.get(src[0], {}) or {}).get(src[1]) if src else None
            entry[field] = val
            if not val:
                gaps.append(f"{name}.{field}")
        entry["cadence"] = rec.get("cadence")
        entry["actingNote"] = rec.get("actingNote")
        perf[name] = entry
    CREATIVE.mkdir(parents=True, exist_ok=True)
    ppath = CREATIVE / "CHARACTER_PERFORMANCE_CANON.json"
    if not ppath.exists():
        json.dump({"version": CANON_VERSION, "note": "Migrated mechanically from the "
                    "character bibles; null fields are AUTHORING GAPS for the user or an "
                    "approved derivation pass — never silently invented.",
                    "characters": perf}, open(ppath, "w"), indent=1, ensure_ascii=False)
    report = {"builtAt": _now(), "assets": [], "gaps": sorted(gaps)[:400]}
    for key, path in {**_CANON_SOURCES, "script": _script_package(episode)}.items():
        p = pathlib.Path(path)
        report["assets"].append({"asset": key, "source": str(p),
                                   "status": "referenced" if p.exists() else "MISSING",
                                   "md5": _md5(p) if p.exists() else None})
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(report, open(OUT / "migration_report.json", "w"), indent=1, ensure_ascii=False)
    log(f"MIGRATION — {sum(1 for a in report['assets'] if a['status'] == 'referenced')} assets "
        f"referenced, {len(gaps)} character-performance authoring gap(s) recorded")
    return report


if __name__ == "__main__":
    os.chdir(HERE)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "envelope"
    if cmd == "envelope":
        load_canon_envelope(sys.argv[2] if len(sys.argv) > 2 else "Ep1")
    elif cmd == "vision":
        episode_vision(sys.argv[2] if len(sys.argv) > 2 else "Ep1")
    elif cmd == "scene":
        brief = None
        if "--brief" in sys.argv:
            brief = sys.argv[sys.argv.index("--brief") + 1]
        ep = next((a for a in sys.argv[3:] if not a.startswith("--")
                    and a != brief), "Ep1")
        run_scene(sys.argv[2], ep, brief=brief)
    elif cmd == "migrate":
        migrate(sys.argv[2] if len(sys.argv) > 2 else "Ep1")
    else:
        print(__doc__)
        sys.exit(1)
