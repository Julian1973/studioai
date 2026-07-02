#!/usr/bin/env python3
"""cb_director_schemas.py — the Director's STRICT output contract (Pydantic v2).

These models are the JSON Schema / Structured Outputs the OpenAI Director (cb_llm) is constrained to, AND the
Pydantic validation every Director response is checked against. They mirror the exact field names the rest of the
pipeline already consumes (cb_prompts, cb_beats, cb_scene, cb_continuity, cb_director_eye) — so switching the
Director's PROVIDER from Gemini to OpenAI does not change the package shape downstream.

OpenAI strict structured outputs forbid extra properties and require every field; Optional[...] = None becomes a
nullable-but-present field. Keep these models flat; nest only where the package is genuinely nested.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


# ── STAGE 0 — theme lock ─────────────────────────────────────────────────────
class Theme(BaseModel):
    declaration: str
    theme: str
    leadArc: str
    storySpine: str
    promise: str
    throughline: str
    selCompetency: str
    haidt: str
    pressureTest: str


# ── STAGE A — episode_to_scenes (beat map: scenes + arc + continuity) ─────────
class Scene(BaseModel):
    sceneNumber: int
    name: str
    locationId: str
    location: str
    time: str
    weather: str
    lighting: str
    look: str
    cast: List[str]
    pillar: str
    intensity: float
    emotionalCore: str


class ArcDay(BaseModel):
    scenes: List[int]
    pillar: str
    light: str


class Arc(BaseModel):
    episode: str
    title: str
    lead: str
    engine: str
    the_day_unfolds: List[ArcDay]
    wristbands: List[str]


class Vision(BaseModel):
    shot: str
    ofScene: str
    wristbands: str
    style: str
    materialize: str


class Recurring(BaseModel):
    name: str
    appearance: str
    orientation: str
    anchorScene: str


class Persistent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    item: str
    in_: str = Field(alias="in")   # downstream cb_prompts reads persistent[].in — preserve the key exactly
    fromShot: str


class Lost(BaseModel):
    name: str
    atShot: str
    reason: str


class Item(BaseModel):
    name: str
    appearance: str
    shots: List[str]


class WorldState(BaseModel):
    locationId: str
    atScene: str
    change: str
    persists: bool


class Continuity(BaseModel):
    visions: List[Vision]
    recurring: List[Recurring]
    persistent: List[Persistent]
    lost: List[Lost]
    items: List[Item]
    worldState: List[WorldState]


class EpisodeBreakdown(BaseModel):
    title: str
    logline: str
    leadBear: str
    engine: str
    format: str
    scenes: List[Scene]
    arc: Arc
    continuity: Continuity


# ── DERIVE PLATE (scene establishing plate, derived from the scene's beats) ───
class Plate(BaseModel):
    sceneShotName: str
    location: str
    look: str
    definingFeature: str
    colorTemperature: str
    lens: str
    cameraHeight: str


# ── STAGE B — scene_to_beats (the rich beat schema) ──────────────────────────
class Cut(BaseModel):
    n: int
    framing: str
    action: str
    dialogue: Optional[str] = None        # "NAME: line" or null (a wordless cut)
    delivery: Optional[str] = None        # acting/cadence note for the line
    voiceTreatment: Optional[str] = None  # production voice treatment: "group_chorus" | "underwater_vo" | null
    chorusMembers: Optional[List[str]] = None  # group_chorus only: canon characters whose voices form the unison


class Performance(BaseModel):
    surface: str
    underneath: str
    innerThought: str


class BeatCheck(BaseModel):
    focalSubject: str
    emotionalRead: str
    heartCheck: str


class BeatContinuity(BaseModel):
    opensFrom: str
    carryToNext: str
    screenDirection: str                  # "LEFT" | "RIGHT"


class Beat(BaseModel):
    slug: str
    scene: str
    characters: List[str]
    openingCast: List[str]                # subset of characters visible in the OPENING frame
    speakers: List[str]
    keenWristbands: Optional[str] = None  # "none"|"vacant"|"crystal"|null
    durationSec: int                      # 8..15
    pillar: str
    intensity: float
    storyBeat: str
    emotionalIntent: str
    want: str
    need: str
    crystalTruth: str
    kidRead: str
    adultRead: str
    theGame: Optional[str] = None
    wordlessHeld: bool
    comedyMode: Optional[str] = None      # "BIG" | "TRUE" | null
    physicalFeeling: str
    light: str
    atmosphere: str
    motionTempo: str
    grade: str
    cuts: List[Cut]                       # 2-4 internal cuts, in order; cut 1 is the opening
    cameraArc: str
    pacingVerbs: List[str]
    pauseHold: str
    performance: Performance
    crystalGlow: str
    beautyMoment: bool
    startState: str                       # the static held OPENING frame (the keyframe is drawn from it)
    keyframePrompt: str
    i2vPrompt: str                        # the Seedance beat take prompt
    soundIntent: str
    continuity: BeatContinuity
    check: BeatCheck
    writerNote: Optional[str] = None      # Braintrust/Three-Strikes flag for Julian; the line STAYS verbatim
    shot_style: Optional[str] = None      # SINGLE_TAKE|CINEMATIC_CUTS|COMEDY_CUTS|HEART_COVERAGE|ACTION_COVERAGE|MAGIC_COVERAGE (inferred if null)
    script_gag_lock_id: Optional[str] = None  # a LOCKED scripted gag (config/gag_locks.json) — the Director may split, never mutate
    gag_carry: Optional[str] = None       # a gag state the beat must carry IN from a prior gag beat (e.g. "pollen moustache")
    # ── Episode Director layer (all optional / back-compatible; inferred by cb_seedance when null) ──
    director_mode: Optional[str] = None         # one of the 15 universal emotional modes (DIRECTOR_MODE_GUIDANCE)
    audience_feeling_target: Optional[str] = None  # what the audience should FEEL (laughter, tenderness, panic, awe …)
    emotional_function: Optional[str] = None    # the beat's emotional job in the arc
    script_truth_lock: Optional[str] = None     # a non-gag scripted truth the beat must preserve
    music_emotion: Optional[str] = None         # the emotional intent of the score/SFX for this beat
    performance_notes: Optional[str] = None     # acting truth for the performers in this beat
    # ── Physical staging layer (optional; cb_seedance derives the intent from these + the gag lock when null) ──
    physical_staging_intent: Optional[str] = None   # explicit full staging intent (overrides the derived one)
    visibility_rule: Optional[str] = None       # what stays visible (body/silhouette/hands/object)
    contact_rule: Optional[str] = None          # what touches what (and what must NOT enter/hide)
    physics_rule: Optional[str] = None          # what compresses / rebounds / what force acts on the body
    visual_payoff_rule: Optional[str] = None    # the exact gag shape / payoff / what changes physically
    failed_correction_rule: Optional[str] = None  # the physical action that makes it worse / the failed attempt
    continuity_physical_rule: Optional[str] = None  # the physical state that must carry into the next beat
    prohibited_staging: Optional[str] = None    # staging that is forbidden (e.g. disappearing into the flower)


class SceneBeats(BaseModel):
    beats: List[Beat]


# ── GATE 1.5 — DIRECTOR'S EYE (bible + Pixar-craft review, cb_director_eye.py) ─
class EyeFlag(BaseModel):
    issue: str
    rule: str            # the EXACT bible rule OR Pixar-craft principle this beat breaks
    ruleType: str         # "bible" (canon/character/North-Star/comedy-doctrine) | "craft" (Docter/Lasseter/Lin/Kalache)
    severity: str         # high | medium | low
    fix: str              # a concrete, minimal fix

class EyeFinding(BaseModel):
    beatCode: str
    verdict: str          # "on-bible" | "FLAG"
    flags: List[EyeFlag]

class EyeSummary(BaseModel):
    beatsReviewed: int
    flagged: int
    topThemes: List[str]
    verdict: str          # one honest line

class EyeReport(BaseModel):
    findings: List[EyeFinding]
    summary: EyeSummary


# ── validation helpers (business rules layered on top of the strict schema) ───
VALID_COMEDY = {"BIG", "TRUE", None, ""}


def beat_problems(beats, scene):
    """Business-rule validation on top of the strict Pydantic schema. Returns a list of human-readable problems
    (empty = clean) for validate_scene_beats to drive a single repair call. Conservative: only flags things a
    repair call can actually fix without touching the LOCKED dialogue."""
    problems = []
    if not beats:
        return [f"scene {scene.get('sceneNumber')} produced ZERO beats"]
    cast = set(scene.get("cast") or [])
    for b in beats:
        code = b.get("beatCode") or b.get("slug") or "?"
        chars = set(b.get("characters") or [])
        oc = set(b.get("openingCast") or [])
        sp = set(b.get("speakers") or [])
        if not (oc <= chars):
            problems.append(f"{code}: openingCast {sorted(oc - chars)} not in characters {sorted(chars)}")
        if not (sp <= chars):
            problems.append(f"{code}: speakers {sorted(sp - chars)} not in characters {sorted(chars)}")
        if cast and not (chars <= cast):
            problems.append(f"{code}: characters {sorted(chars - cast)} are not in the scene cast {sorted(cast)}")
        if not (b.get("cuts")):
            problems.append(f"{code}: has no cuts (need 2-4 internal cuts)")
        d = b.get("durationSec")
        if not isinstance(d, int) or not (8 <= d <= 15):
            problems.append(f"{code}: durationSec {d!r} out of range 8..15")
        if (b.get("comedyMode") or None) not in VALID_COMEDY:
            problems.append(f"{code}: comedyMode {b.get('comedyMode')!r} must be BIG, TRUE or null")
    return problems


def pacing_warnings(beats):
    """SOFT warnings (reported, never a repair trigger — dialogue is LOCKED, so the fix is a SPLIT, not a trim):
    a beat whose total spoken words exceed ~20 (~10s at 2 words/s) is running hot."""
    warns = []
    for b in beats:
        words = 0
        for c in (b.get("cuts") or []):
            line = (c.get("dialogue") or "")
            if ":" in line:
                line = line.split(":", 1)[1]
            words += len(line.split())
        if words > 20:
            warns.append(f"{b.get('beatCode') or b.get('slug')}: ~{words} spoken words (>20 ≈ >10s) — consider a SPLIT")
    return warns
