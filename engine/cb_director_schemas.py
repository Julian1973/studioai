#!/usr/bin/env python3
"""cb_director_schemas.py — the Director's STRICT output contract (Pydantic v2).

These models are the JSON Schema / Structured Outputs the OpenAI Director (cb_llm) is constrained to, AND the
Pydantic validation every Director response is checked against. They mirror the exact field names the rest of the
pipeline already consumes (cb_prompts, cb_beats, cb_scene, cb_continuity, cb_director_eye) — so switching the
Director's PROVIDER from Gemini to OpenAI does not change the package shape downstream.

OpenAI strict structured outputs forbid extra properties and require every field; Optional[...] = None becomes a
nullable-but-present field. Keep these models flat; nest only where the package is genuinely nested.
"""
import re
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
    # ── THE MANIFEST LAYER, scene-scoped (CLAUDE.md rules 37/46, added 2026-07-07 — "the stuff that you've
    # done needs to be written into some form of script or code for it to be used in every single project
    # going forward"): Gate 1 now AUTHORS these itself, so a fresh fire on any project produces a
    # manifest-clean package end to end, instead of needing a separate manual authoring pass whose work a
    # re-fire would silently wipe (the schema-drift finding, rule 46). cb_preflight BLOCKs on both. ──
    ambientBed: str = Field(min_length=1)   # ONE locked ambient-sound-bed line for the WHOLE scene (rule 35 —
    #   word-for-word identical across every beat in it; the scene's constant environment only, never
    #   anything beat-specific, never a future story event — the thunder-leak lesson). min_length=1 is
    #   deliberate (2026-07-07): a plain `str` field lets OpenAI's strict mode satisfy "required" with an
    #   EMPTY string, which Pydantic accepts as valid — no ValidationError, so `structured_with_repair`'s
    #   existing repair loop never fires and a genuinely blank field would ship silently. This scene-level
    #   Stage has no custom business-rule validator (unlike scene_to_beats' beat_problems/repair_call), so
    #   the constraint itself has to be the thing that makes "blank" a real, catchable error.
    parentLine: str = Field(min_length=1)   # the adult-layer read of the WHOLE scene — what a watching parent
    #   understands/feels here that a 4-year-old doesn't yet (the co-watch contract, rule 37). Same
    #   min_length=1 reasoning as ambientBed above.
    sceneLook: str = Field(min_length=1)    # THE SCENE-LOOK LAW (rule 53, 2026-07-08): ONE short, already-
    #   punctuated atmosphere line for the WHOLE scene — light source/direction/behaviour, texture, mood —
    #   read verbatim into every beat's shipped prompt (cb_segprompt._v5_scene_look, appended as a second
    #   sentence onto the style law, Block 1). Added the same day the universal style law was leaned to a
    #   fixed constant (rule 52, decision 4) and scene-specific atmosphere ("warm golden hour sunlight,"
    #   pollen, storm light) moved OUT of it — every scene needs its own sceneLook or its beats ship with NO
    #   atmosphere language at all. Distinct from `look` (the verbose empty-plate composition text) and from
    #   `lighting` (the scene's own longer lighting description, which may legitimately describe change ACROSS
    #   the scene, e.g. "drains into storm light by the end") — sceneLook is the CONSTANT held word-for-word
    #   across every beat (the Scene Bubble Law, rule 35), so it should read as the scene's dominant, opening
    #   atmosphere, not a beat-by-beat progression. Same min_length=1 reasoning as ambientBed/parentLine above.


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
    delivery: Optional[str] = None        # THE DELIVERY LAW (rule 53, 2026-07-08 — Julian: "any performs a
    #   reply was a dry affection, a counterpunch holding back the laugh until the end of the delivery... how
    #   you're going to talk around the audio. That's fantastic"). ACTING DIRECTION for this line's
    #   performance — tone, intent, physical behaviour while speaking — NEVER the words themselves (Law 6
    #   stays fully intact). Required whenever `dialogue` is non-blank; null/blank only for a wordless cut.
    #   This is now LOAD-BEARING, not flavour text: cb_segprompt._v5_cut_speaker_note reads it directly into
    #   the shipped prompt as "{Name} performs {his/her} vocal beat from @Audio1 {delivery}." — write it as a
    #   clause that completes that sentence naturally (starting with a preposition like "with"/"as", never a
    #   capital letter or a full independent sentence). WORKED EXAMPLES (Julian's own praised standard):
    #   "with earnest, hopeful pomp, presenting the pollen moustache as though it were an official uniform"
    #   (Fuzzby, 1.B2) / "as a dry, affectionate counterpunch, holding back the laugh until the end of the
    #   delivery" (Zenny, 1.B2). A generic tag ("happy", "sad", "excited") fails this bar — name the SPECIFIC
    #   tone, the physical behaviour that carries it, and (where it sharpens the moment) what's held back or
    #   revealed. Before this rule this field existed but was silently discarded by the emitter (every cut
    #   shipped as a bare "{Name} speaks.") — it is now what actually reaches Seedance.
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


class OpensOn(BaseModel):
    who: str        # the character the camera opens on
    action: str     # their immediate mid-motion state (a short phrase, not a full sentence)


class FidelityAllocation(BaseModel):
    """THE FIDELITY-ALLOCATION LAW (2026-07-07, mined from "Seedance Prompt Engine," a reference tool built on
    the same seedance-20 doctrine — its own allocation model: "identity fidelity, motion boldness, and scene
    density compete for one budget... never demand a perfect face + a backflip + a crowd + a spoken line in
    one call"). An explicit, AUTHORED per-beat decision — never inferred — about who this beat's craft budget
    actually spends on, closing the exact gap the craft audit found (rule 48): an ensemble beat naming 5-9
    characters with nobody designated to actually carry it reads as wallpaper, because nothing ever forced the
    choice of who does."""
    primary: str      # the ONE named character this beat's fidelity budget spends on — who genuinely needs
    #                   precise expression/performance here; ALWAYS a real name, even for a solo beat (that
    #                   one character IS the primary) — never blank, never "none"
    secondary: str    # the ONE supporting character playing off primary, or "none" for a genuinely solo beat
    economized: str   # who/what is DELIBERATELY kept generic/background this beat (comma-separated names, or
    #                   "none" if every named character is primary/secondary) — never a silent omission


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
    # ── THE MANIFEST LAYER, beat-scoped (CLAUDE.md rules 37/46, added 2026-07-07 — Gate 1 now authors these
    # itself; see cb_director_schemas.py's module note and cb_director.scene_to_beats' prompt for the exact
    # definitions the Director is given). cb_preflight BLOCKs on all of these except junctionType/opensOn,
    # which are exempt for a scene's own first beat (no predecessor to join from) — nullable here for that
    # reason, defaulted/derived in code (cb_director._finalize_beat_manifest_fields) for every other beat, so
    # a missing value is never silently invented as prose, only mechanically defaulted where rule 31 already
    # names the default ("intentional_next_shot... never seamless_continuation by omission"). ──
    endState: str                          # directing prose for THIS beat's own distinct ending — a living
    #                                         settle, in character, NEVER a restatement of the previous beat's
    #                                         pose (it becomes the next beat's own anchor)
    endStateStill: str                     # the SAME instant as endState, described as a static photograph:
    #                                         no temporal verbs ("settles into", "turns to"), no imperatives,
    #                                         no camera/ambience — only subjects, poses, positions, expressions
    carryMarks: str                        # a SHORT phrase (not a sentence) naming what specifically, visibly
    #                                         persists into the next beat (a held object, wet fur, a costume
    #                                         state) — or an explicit "no persisting marks" if genuinely none
    junctionType: Optional[str] = None     # "intentional_next_shot" (THE DEFAULT — a new gag arc, a fresh
    #                                         camera setup) | "seamless_continuation" (ONLY when the shot
    #                                         genuinely doesn't cut — ONE unbroken take spanning the boundary);
    #                                         null ONLY for a scene's own first beat (no predecessor to join)
    opensOn: Optional[OpensOn] = None       # WHO the camera opens on and their immediate mid-motion state;
    #                                         null ONLY for a scene's own first beat
    relayOpeningNote: Optional[str] = None  # OPTIONAL (rule 53, 2026-07-08) — one extra sentence for a relay
    #                                         beat's @图1 clause naming what breaks IMMEDIATELY after the
    #                                         opening frame (e.g. who moves first, what pose is broken) —
    #                                         only when opensOn/carryMarks alone leave real ambiguity about
    #                                         the instant after the anchor frame; most beats leave this null
    spatialAxis: Optional[str] = None       # OPTIONAL (rule 53, 2026-07-08) — a fixed one-sentence blocking
    #                                         law for this beat (who occupies which lane/side, "never swap
    #                                         sides") — only when the scene's own blocking benefits from an
    #                                         explicit standing rule beyond what startState already states;
    #                                         most beats leave this null, NOT a required field every beat
    stagingProhibited: Optional[List[str]] = None  # OPTIONAL (found MISSING from this schema entirely in the
    #                                         2026-07-08 software-wide sign-off audit — the field was real and
    #                                         load-bearing, cb_segprompt._v5_negative_line already merges it
    #                                         into the beat's shipped Negative line, cb_preflight already
    #                                         checked its well-formedness, but nothing in the Director's own
    #                                         schema let Gate 1 natively author it, the exact class of gap
    #                                         rule 47 closed for junctionType/opensOn/carryMarks/etc — this
    #                                         closes the same gap for this one field). A short list of THIS
    #                                         beat's own specific gag-failure modes to forbid (e.g. "Fuzzby
    #                                         disappearing into the flower"), each phrase written WITHOUT its
    #                                         own leading "no" (the emitter adds that mechanically) — most
    #                                         beats leave this null; the eleven standing negatives already
    #                                         cover every beat regardless
    actingContrast: str                    # which characters in this beat play off each other and how (for a
    #                                         solo-character beat: the INTERNAL contrast within that one
    #                                         character's own performance — surface vs. interior)
    humourLayer: int                       # 1-4, the show's Layered-Humour scale (see the prompt for the
    #                                         exact definition of each layer — judged honestly per beat, a
    #                                         quiet Heart beat can legitimately be layer 1)
    emotionMechanic: str                   # ONE sentence: the concrete visual/physical MECHANISM that makes
    #                                         this beat's emotion legible on screen (a glow, a gesture, a held
    #                                         breath, a physical gag) — never a restatement of emotionalIntent
    fidelityAllocation: FidelityAllocation  # THE FIDELITY-ALLOCATION LAW (2026-07-07) — who this beat's craft
    #                                         budget actually spends on; see FidelityAllocation's own docstring
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
VALID_JUNCTION = {"intentional_next_shot", "seamless_continuation", None, ""}
_PAUSEHOLD_RE = re.compile(r"(\d+(?:\.\d+)?)[\s-]*second")


def beat_problems(beats, scene):
    """Business-rule validation on top of the strict Pydantic schema. Returns a list of human-readable problems
    (empty = clean) for validate_scene_beats to drive a single repair call. Conservative: only flags things a
    repair call can actually fix without touching the LOCKED dialogue.

    THE MANIFEST LAYER checks (added 2026-07-07, rule 46): mirrors cb_preflight.check_beat_technical's own
    business rules so a bad value is caught and repaired HERE, at authoring time, rather than surfacing only
    much later as a cb_preflight BLOCK with no repair loop of its own. Presence is already guaranteed by the
    strict Pydantic schema (every field is required unless Optional); this only checks VALUE VALIDITY."""
    problems = []
    if not beats:
        return [f"scene {scene.get('sceneNumber')} produced ZERO beats"]
    cast = set(scene.get("cast") or [])
    opener_slug = beats[0].get("slug")
    for i, b in enumerate(beats):
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
        hl = b.get("humourLayer")
        if not (isinstance(hl, int) and 1 <= hl <= 4):
            problems.append(f"{code}: humourLayer {hl!r} must be an integer 1-4")
        ph = str(b.get("pauseHold") or "")
        m = _PAUSEHOLD_RE.search(ph)
        if not m:
            problems.append(f"{code}: pauseHold {ph!r} must state a concrete duration as \"N second(s)\" (e.g. \"1.2 second hold on...\")")
        elif float(m.group(1)) > 1.5:
            problems.append(f"{code}: pauseHold states {m.group(1)}s — the staging law caps every hold at <=1.5s")
        jt = b.get("junctionType")
        if jt not in VALID_JUNCTION:
            problems.append(f"{code}: junctionType {jt!r} must be \"intentional_next_shot\", \"seamless_continuation\", or null (scene opener only)")
        if i > 0 and not (b.get("opensOn") or {}).get("who"):
            problems.append(f"{code}: opensOn is required (non-opener beat) — {{who, action}}, who the camera opens on")
        if not str(b.get("carryMarks") or "").strip():
            problems.append(f"{code}: carryMarks is required (a short phrase, or an explicit \"no persisting marks\")")
        fa = b.get("fidelityAllocation") or {}
        primary = str(fa.get("primary") or "").strip()
        if not primary or primary.lower() == "none":
            problems.append(f"{code}: fidelityAllocation.primary is required and must be an actual character name, never blank or \"none\"")
        elif chars and primary not in chars and primary.lower() != "none":
            problems.append(f"{code}: fidelityAllocation.primary {primary!r} is not in this beat's own characters {sorted(chars)}")
        if not str(fa.get("secondary") or "").strip():
            problems.append(f"{code}: fidelityAllocation.secondary is required (a character name, or an explicit \"none\")")
        if not str(fa.get("economized") or "").strip():
            problems.append(f"{code}: fidelityAllocation.economized is required (comma-separated names, or an explicit \"none\")")
        # THE DELIVERY LAW (rule 53, 2026-07-08): a cut WITH dialogue must have a non-blank delivery note —
        # cb_segprompt._v5_cut_speaker_note now quotes it directly into the shipped prompt as acting direction
        # ("{Name} performs {his/her} vocal beat from @Audio1 {delivery}."); a blank delivery on a spoken cut
        # silently degrades to a bare "{Name} speaks.", which is exactly the flat placeholder this rule exists
        # to replace. `dialogue` being non-nullable-in-practice-but-Optional means Pydantic alone won't catch
        # a "" delivery paired with real dialogue — checked here, same class of gap as the fields below.
        for c in (b.get("cuts") or []):
            if str(c.get("dialogue") or "").strip() and not str(c.get("delivery") or "").strip():
                problems.append(f"{code}: cut {c.get('n')} has dialogue but no delivery note — required (acting direction, never the words; see Cut.delivery's own docstring for the worked-example bar)")
        # A required `str` field in the Pydantic schema guarantees the KEY is present, never that its VALUE is
        # non-empty — an LLM can still return "" for a required field, which Pydantic accepts (a valid string)
        # but cb_preflight.check_beat_technical/check_beat_creative BLOCK on as blank. Check every one of them
        # here too, so a blank value drives the SAME repair call other business-rule violations already do,
        # instead of only surfacing much later as an unrepaired manifest BLOCK.
        for field in ("endState", "endStateStill", "actingContrast", "emotionMechanic", "want", "need",
                      "kidRead", "adultRead"):
            if not str(b.get(field) or "").strip():
                problems.append(f"{code}: {field} is required and must not be blank")
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
