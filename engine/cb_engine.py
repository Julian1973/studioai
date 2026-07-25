#!/usr/bin/env python3
"""cb_engine.py — THE DIRECTOR ENGINE, HYBRID v2 (Julian's rulings, 2026-07-16 —
THE_DEFINITIVE_PIPELINE.md at repo root is the governing document; read it first).

⚠ FROZEN 2026-07-17 (Julian's system-freeze checkpoint, PIPELINE_CUTOVER_LEDGER.md §8):
compile_keyframe_prompt, compile_shot_contract and the reference-ownership doctrine are
LOCKED as of that day's corrections. No further compiler changes without a fresh, dated
ruling — see the ledger for the full record.

THE HYBRID (Julian: "the ultimate clean workflow... light, clean and effective"): the
production CONTRACT and design-time VALIDATOR adopted from the Enaid Animation Studio
reference architecture he supplied, merged with this studio's own locked laws —
ElevenLabs-only voice (@Audio1; spoken words NEVER appear in any render prompt, Law 6),
reference-only identity (no character description in any prompt, ever, rule 5), and the
platform-length shot contract carrying his dictated @图1 anchor texts verbatim.

What the hybrid adds over v1 (each closed a named gap in PIPELINE_CUTOVER_LEDGER.md):
  - DIALOGUE LIVES ON THE SHOT: typed lines (speaker, exact verbatim text, delivery,
    timing) feed the ElevenLabs audio brief and the verbatim validator — and are
    mechanically guarded out of every render prompt.
  - TYPED CONTINUITY IN/OUT per shot (zone/facing/pose/expression/marks/props) — the
    §6 continuity ledger as data; drift is caught at design time, before any money.
  - THE PHYSICAL-STAGING CONTRACT: a BIG-comedy beat cannot ship without one shot
    carrying the full gag physics (visibility, contact/weight, payoff shape, prohibited).
  - THE DETERMINISTIC VALIDATOR: zero-LLM checks (verbatim dialogue, dropped/duplicated
    lines, speaker visibility, timing, relay sources, mark/prop drift) + one repair pass.
  - A reference-first keyframe prompt per opener shot (anticipation, room to breathe,
    zero appearance text).

A SCENE is a dramatic unit, a BEAT is a change in story/emotion/comedy, a SHOT is the
camera's view of that beat. The render unit is the 4-8s shot, ONE performance assignment
each; the shipped prompt stays platform-length. Zero renders are fired by this module.

    python3 cb_engine.py <scene> [episode]     # design + validate + compile one scene
"""
import os, sys, json, re, pathlib
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cb_llm
import paths as P


def canonical_package_path(scene, episode="Ep1"):
    """THE canonical production package's path (2026-07-17, Julian's layer-boundary
    directive, item 2) — cb_engine.py already owns the canonical package CONTRACT
    (compile_scene_package below is what shapes it); this is the one place its filename
    convention lives. cb_render.py's own _pkg_path delegates to this pure helper (never
    duplicates it); cb_handover.py calls it directly — a pure path computation, not a
    render or provider entry point, so it does not violate cb_handover's own
    never-imports-cb_render/cb_gen invariant. No new module, no new convention: this is
    the SAME path both modules already computed independently before this correction."""
    return HERE.parent / "cb-output" / f"{episode}_scene{scene}_production_package.json"


# CORRECTED 2026-07-22 (low-priority cleanup pass): both constants below used to be described here
# as a live "hard assertion... guards against bloat" — stale the moment Julian's 2026-07-21 ruling
# ("take all the straightjackets off") removed the actual enforcement from both compile functions
# (see compile_shot_contract's and compile_keyframe_prompt's own dated comments, further down this
# file, for the real history). Neither is asserted against anywhere anymore; both stay purely as a
# measurement/sanity threshold the test suite compares a clean fixture's word count against, and as
# a stated point of reference for "what used to be the ceiling" in the surrounding doctrine comments.
MAX_SHOT_PROMPT_WORDS = 210   # was: hard assertion on every compiled shot contract, raised 170->210
                              # on 2026-07-16 for the dictated @图1 anchor contracts' fixed
                              # continuity-scaffolding overhead (~34/~62 words per shot). Removed as
                              # a real cap 2026-07-21; kept as the test suite's own lean-fixture bound.
MAX_KEYFRAME_PROMPT_WORDS = 160   # was: hard assertion on every compiled keyframe brief. Removed as
                                  # a real cap the same 2026-07-21 pass; kept for the identical reason.
# 2026-07-21 (Julian's cut-pace mandate — every shot's own pace is a real director decision,
# "short, sharp and snappy" or "a longer one," made every single time): the old 4-8s ceiling
# was sized for a single continuous take only. Seedance 2.0's own real multi-shot grammar
# (verified: [ref:multishot-grammar]) wants a budget of roughly four to five seconds PER
# internal cut — two-to-three cuts genuinely need up to fifteen seconds total — so the
# ceiling is raised to match, not because every shot needs the max, but so a shot the
# Director genuinely calls rapid_cuts on isn't structurally starved of the seconds its own
# cuts need to land clean.
MIN_SHOT_SEC, MAX_SHOT_SEC = 4, 15


# ─────────────────────────────────────────────────────────────────────────────────────────
# THE PRODUCTION CONTRACT — the hybrid schema (Enaid's data model under this studio's laws)
# ─────────────────────────────────────────────────────────────────────────────────────────
class DirectorStatement(BaseModel):
    """Julian's six questions, per scene (THE_DEFINITIVE_PIPELINE.md §1)."""
    audienceFeeling: str = Field(min_length=1)
    whoseScene: str = Field(min_length=1)
    emotionalChange: str = Field(min_length=1)
    theLaugh: str = Field(min_length=1)
    visualSurprise: str = Field(min_length=1)
    carryForward: str = Field(min_length=1)


class DialogueLine(BaseModel):
    """One verbatim script line assigned to one shot. exactText feeds ONLY the ElevenLabs
    audio brief and the verbatim validator — it is mechanically guarded out of every render
    prompt (Law 6, un-reopenable)."""
    speaker: str = Field(min_length=1)            # canonical character name from the cast
    exactText: str = Field(min_length=1)          # VERBATIM from the locked beats — validated, never edited
    delivery: str = Field(min_length=1)           # acting direction: tone + physical behaviour, never words
    startSec: float                               # approximate window inside the shot
    endSec: float
    # 2026-07-22 (Julian's directive, real-footage diagnosis — S1.SH1's "Nailed it." never
    # landed because the shot's picture-side climax (bounce-chain/backflip/landing/
    # confusion) takes several real seconds regardless of how long ElevenLabs happens to
    # render the PRECEDING line): an OPTIONAL, director-authored floor (seconds INTO the
    # shot) for when this line's own onset may begin, anchored to the FIXED picture
    # duration — never "N seconds after wherever the previous line ends," which floats
    # with ElevenLabs' own take-to-take variance in how long a chant/ad-lib actually runs
    # (confirmed live: the same two-line take rendered its opening chant at 2.4s in one
    # generation and 3.9s in another). None/0.0 for every line today except one (fully
    # backward compatible — omitting it reproduces the exact prior behaviour).
    # cb_render.voice_shot stretches the take's own largest pre-existing pause so this
    # line's onset lands at or after minOnsetSec; it never touches a single word of the
    # actual vocal performance.
    minOnsetSec: Optional[float] = None


class CharacterState(BaseModel):
    """One character's continuity truth at a shot boundary — typed, machine-comparable."""
    character: str = Field(min_length=1)
    screenZone: str = Field(min_length=1)         # frame-left / centre / frame-right etc.
    facing: str = Field(min_length=1)
    pose: str = Field(min_length=1)
    expression: str = Field(min_length=1)
    visibleMarks: List[str]                       # pollen moustache, dirt — what the join must carry
    heldProps: List[str]


class ContinuityState(BaseModel):
    """The world at a shot boundary (§6's ledger as data). The scene plate carries the
    constant look (Scene Bubble Law) — only what can CHANGE shot to shot is tracked."""
    lighting: str = Field(min_length=1)
    cameraSide: str = Field(min_length=1)         # which side of the action line the camera holds
    characters: List[CharacterState]


class PhysicalStaging(BaseModel):
    """The gag-physics contract (the 1.B4 vanish-into-the-flower lesson, as a type).
    Required on at least one shot of every BIG-comedy beat — validator-enforced."""
    staysVisible: str = Field(min_length=1)       # what must remain readable in silhouette throughout
    contactAndWeight: str = Field(min_length=1)   # what touches what; where weight compresses/rebounds
    payoffShape: str = Field(min_length=1)        # the exact visual shape of the gag's payoff
    prohibitedStaging: List[str]                  # this gag's own specific failure modes


# ─────────────────────────────────────────────────────────────────────────────────────
# THE PRODUCTION-DIRECTION UPGRADE (Julian's directive, 2026-07-25)
#
# Three additions, all OPTIONAL so every existing canonical package still validates
# unchanged (backward compatibility is a hard requirement of the directive):
#
#   DramaticForm    — the scene's dramatic mode. The directive's central creative ask:
#                     "Different dramatic forms must produce genuinely different direction,
#                     shot structure, camera behaviour, editing, tempo and performance...
#                     There must be no universal continuous take, camera move, focal
#                     length, shot count, prompt length or closing hold."
#   FirstFramePlan  — the SOURCE OF TRUTH for keyframe generation, replacing the two
#                     free-text strings (openingImage/openingPose) that carried it before.
#   MotionPlan      — the SOURCE OF TRUTH for animation prompt translation.
#
# Neither plan REPLACES the existing prose fields; they sit alongside them so a package
# authored before this upgrade still compiles through the identical path.
# ─────────────────────────────────────────────────────────────────────────────────────

DramaticForm = Literal[
    "physical_comedy", "character_comedy", "intimate_emotion", "relationship_dialogue",
    "action", "tension", "wonder", "exposition", "reveal", "transition",
]

# ── ENDING BEHAVIOUR — the real vocabulary, not a binary ────────────────────────────
# (Julian's directive item 2, 2026-07-25.) A first pass modelled this as settle-vs-motion;
# that is too coarse for the endings real production needs. Five kinds, of which only the
# two genuine HOLDS require a hold tail — the others legitimately end while still moving.
#
#   reaction_hold     — the camera holds on a reaction/emotional beat. HOLD required.
#   living_hold       — held frame, performance continues (breath, idle life). HOLD required.
#   continue_in_motion— action carries on past the cut point.               no HOLD.
#   cut_on_action     — the edit lands mid-movement, deliberately.          no HOLD.
#   visual_transition — the image itself becomes the way into the next shot.no HOLD.
EndingBehaviour = Literal[
    "reaction_hold", "living_hold", "continue_in_motion", "cut_on_action", "visual_transition",
]

# The two endings that genuinely need the clean-frame harvest window. Everything else is
# allowed — and expected — to finish in movement.
HOLD_REQUIRING_ENDINGS = ("reaction_hold", "living_hold")


class DramaticIntent(BaseModel):
    """WHAT THIS BEAT IS, DRAMATICALLY — and explicitly NOT a template selector.

    Julian's directive item 3 (2026-07-25) is emphatic: "DramaticForm should inform the
    Director's judgement, not prescribe the result... Do not implement rules such as:
    comedy always uses whip-pans; emotion always uses close-ups; action always uses
    handheld movement; wonder always uses wide lenses."

    So nothing downstream may map a form to a camera, lens, shot count or edit. This
    model exists to make the beat's dramatic identity EXPLICIT and reviewable — the
    Director still chooses the camera, editing, staging and performance that serve this
    particular story beat. A beat can be physical comedy AND affection at once, or
    tension AND wonder: hence primary + optional secondary, never one exclusive bucket."""
    primaryForm: DramaticForm
    secondaryColour: Optional[DramaticForm] = None
    audienceExperience: str = Field(min_length=1, description=
        "What the audience should FEEL/understand — not what the camera does.")
    emotionalOrPhysicalTurn: str = Field(min_length=1, description=
        "The change this beat delivers. If nothing turns, the beat has no dramatic function.")
    performanceLeader: str = Field(min_length=1, description=
        "Which character carries this beat. Not necessarily the speaker.")
    tempoShape: str = Field(min_length=1, description=
        "How the beat's pace MOVES — e.g. 'fast then a held stop', 'slow build, no release'. "
        "A shape, never a single speed.")


class FirstFramePlan(BaseModel):
    """The approved opening instant — the source of truth for keyframe generation.
    Cinematography may enrich composition/depth/focus/light/atmosphere/material; it may
    NOT change the story instant, identity, scale, costume, position, prop state or
    continuity recorded here."""
    storyInstant: str = Field(min_length=1)      # the exact moment, not a range
    shotSize: str = Field(min_length=1)
    cameraPosition: str = Field(min_length=1)    # height + angle + distance relationship
    characterPositions: str = Field(min_length=1)
    scaleRelationship: Optional[str] = None      # relative size, when two+ characters share frame
    pose: str = Field(min_length=1)
    gaze: str = Field(min_length=1)
    expression: str = Field(min_length=1)
    actionPhase: str = Field(min_length=1)       # anticipation / mid-action / recovery / at rest
    foreground: Optional[str] = None
    midground: Optional[str] = None
    background: Optional[str] = None
    propState: Optional[str] = None
    environmentState: Optional[str] = None
    lightState: Optional[str] = None
    referenceRoles: Optional[str] = None
    incomingContinuity: Optional[str] = None


class MotionPlan(BaseModel):
    """The approved motion design — the source of truth for animation prompt translation.
    prepare_animation may enrich the EXECUTION (precise physical wording, micro-performance,
    secondary motion, depth, environmental reaction, light and material response); it may
    NOT change dramatic function, performance leader, objectives, shot count, editing
    strategy, tempo, camera strategy, physical outcome, payoff or continuity."""
    entryState: str = Field(min_length=1)
    cameraBehaviour: str = Field(min_length=1)
    orderedActions: List[str] = Field(default_factory=list, description=
        "The character actions IN ORDER. Each is a physical cause with its visible consequence.")
    characterObjectives: Optional[str] = None
    performanceProgression: Optional[str] = None
    environmentalResponse: Optional[str] = None
    tempoChanges: Optional[str] = None           # where the shot speeds up / slows / holds
    dialogueSections: Optional[str] = None       # which audio section carries which performance
    listenerBehaviour: Optional[str] = None
    payoff: str = Field(min_length=1)
    exitState: str = Field(min_length=1)
    nextShotHandoff: Optional[str] = None


class Shot(BaseModel):
    """ONE camera view of one beat — ONE controlled performance assignment (§5)."""
    shotId: str                                   # e.g. "1.B1.S1"
    beatCode: str                                 # the beat this shot photographs
    durationSec: float = Field(ge=MIN_SHOT_SEC, le=MAX_SHOT_SEC)
    purpose: str = Field(min_length=1)            # this shot's ONE job, one line
    performanceAssignment: str = Field(min_length=1)  # one cause with its visible consequences —
    #                                               plain flowing prose; the heart of the prompt
    camera: str = Field(min_length=1)             # lens/height/move in one line
    openingPose: str = Field(min_length=1)        # the ANTICIPATION instant (§4) — the keyframe truth
    sourceType: Literal["opener", "relay"]        # opener = generated keyframe; relay = harvested frame
    sourceShotId: Optional[str] = None            # relay: the EARLIER shot whose final frame anchors this one
    cutInMotivation: Optional[str] = None         # §7 — matched action / reaction / eyeline / sound bridge
    # 2026-07-21 CORRECTION (Julian's own audit — "you have to do what you think is right...
    # it has to fire every single time, it's not optional"): transitionType used to be
    # authored at Gate 4, then silently DISCARDED here — distil_shot kept only transitionReason's
    # prose (cutInMotivation above), never the categorical CONTINUOUS/PLANNED_CUT value itself,
    # so compile_shot_contract had nothing to branch on and every shot compiled identically
    # regardless of the Director's own real decision. Restored as a real, typed field the
    # compiler actually reads (see compile_shot_contract). None only for a scene's own true
    # first shot, which has no predecessor to be continuous with or cut from.
    transitionType: Optional[Literal["CONTINUOUS", "PLANNED_CUT"]] = None
    # cutPace: REQUIRED, no default — the Director's own pace decision (single_continuous_
    # take / paced_cuts / rapid_cuts), mandatory on every shot per Julian's own ruling.
    # internalCuts: the ordered, self-contained cuts authored at Gate 5 when cutPace calls
    # for them (empty for single_continuous_take — performanceAssignment carries that case).
    cutPace: Literal["single_continuous_take", "paced_cuts", "rapid_cuts"]
    internalCuts: List[str] = Field(default_factory=list)
    # ── THE CLIP/CARD SEPARATION (Julian's directive, 2026-07-25) ───────────────────
    # Until this field existed, a Seedance generation clip and a cinematic camera shot
    # were the SAME object: fire_shot() renders exactly one Shot, so the only way to put
    # several ordered camera shots inside one generation was internalCuts — free prose,
    # which REDEFINES those camera shots instead of referencing them (no shotId, no
    # openingPose, no endingBehaviour, no continuity, no approval of their own).
    # composedOf is the reference form: an ordered list of OTHER Shot Cards in this same
    # scene that this one generation renders in sequence. The compiler reads each member
    # card's own authored fields — nothing is re-typed. Empty (the default, and every
    # existing package) means exactly what it always meant: this clip is this one card.
    composedOf: List[str] = Field(default_factory=list)
    # ── THE PRODUCTION-DIRECTION UPGRADE (2026-07-25) ───────────────────────────────
    # packageVersion is the V1/V2 discriminator the precedence rule turns on. A shot
    # WITHOUT it is a legacy V1 shot: the compatibility adapter fills its plans and a
    # missing ending decision stays valid. A shot declaring "v2" is held to the full
    # contract — plans present, ending behaviour explicitly chosen — or it is REFUSED.
    packageVersion: Optional[Literal["v2"]] = None
    dramaticIntent: Optional[DramaticIntent] = None
    # endingBehaviour retires the universal closing hold. REQUIRED on a v2 shot (the
    # Director/Editor must choose); absent is valid ONLY for a legacy package.
    endingBehaviour: Optional[EndingBehaviour] = None
    firstFramePlan: Optional[FirstFramePlan] = None
    motionPlan: Optional[MotionPlan] = None
    dialogueBinding: Optional[str] = None         # the prompt-facing sentence: WHO speaks + the emotional
    #                                               read — NEVER the words (the audio carries them)
    dialogueLines: List[DialogueLine]             # the typed voice data (empty when nobody speaks)
    visualPayoff: str = Field(min_length=1)       # the exact image this shot must end having delivered
    physicalStaging: Optional[PhysicalStaging] = None  # required somewhere in every BIG-comedy beat
    prohibited: List[str]                         # 0-3 shot-specific failure modes ONLY — never a wall
    charactersInFrame: List[str]                  # who is visible (reference bindings derive from this)
    # 2026-07-17 (Julian's system-freeze checkpoint, THE SIMPLIFICATION): typed absence,
    # replacing the old NO_INHERITED_STATE sentinel string — None means "nothing genuinely
    # carries in," true ONLY for the scene's own first shot (mechanically cleared in
    # design_scene, never LLM-authored; see validate_scene_design's OPENER_CONTINUITY_IN_
    # NOT_CLEARED / CONTINUITY_IN_MISSING checks). No new field, state or helper layer —
    # Optional on the field that already existed.
    continuityIn: Optional[ContinuityState] = None  # the world as this shot opens (None: scene opener)
    continuityOut: ContinuityState                # the world as this shot ends — the next relay's truth
    # THE HEART-PACE-AND-FEELING FIX (Julian's ruling, 2026-07-23, watching S1.SH2 v3 —
    # "this is better but lacks the heart pace and feeling"): two authored creative fields
    # that existed in the storyboard all along but never reached the shipped prompt.
    # tempoDesign: the Director's own Gate-5 animationTiming — the fast/slow/pause contrast
    # map ("quick and clumsy, then slow right down for the reveal") — previously DROPPED
    # entirely at handover because the raw field quotes locked dialogue (a Law 6 risk);
    # now shipped with the quoted words mechanically stripped, never the whole design.
    # feltIntent: the shot's own audienceExperience — what the moment should FEEL like —
    # the seedance doctrine's own first rule ("name one intention and make camera, light
    # and performance serve it") applied at last. Both optional: a shot authored before
    # this fix simply compiles without them, never a crash.
    tempoDesign: Optional[str] = None             # Law-6-safe pace design (dialogue stripped at handover)
    feltIntent: Optional[str] = None              # the one intention the whole shot serves
    # THE SHOT-MODE VOCABULARY (Julian's Option B + Anti-Guardrail Principle, 2026-07-23):
    # a SELECTABLE CREATIVE VOCABULARY the Director chooses at storyboard time — never
    # compulsory boilerplate, never an LLM classification at delivery time. 1-2 entries,
    # order = primary then secondary. Compilation SELECTS and REMOVES language by mode
    # (a dialogue shot drops physics-chain and motion-blur vocabulary; a kinetic shot
    # drops speaker vocabulary) — it never adds mode boilerplate on top.
    # THE SHOT-DENSITY RULE (Julian, verbatim intent): when one generation contains more
    # than two substantially different performance modes, the Director must explicitly
    # approve either a hybrid take or split-generation staging — recorded here as
    # modeDensityDecision, surfaced at handover (a decision point, not a new lint layer).
    performanceModes: List[Literal["KINETIC_ACTION", "PHYSICAL_COMEDY",
        "DIALOGUE_PERFORMANCE", "COMEDY_REACTION", "EMOTIONAL_ACTING",
        "WORLD_ESTABLISHING"]] = Field(default_factory=list)
    modeDensityDecision: Optional[Literal["hybrid_approved", "split_staged"]] = None


class SceneShotList(BaseModel):
    statement: DirectorStatement
    shots: List[Shot]


# ─────────────────────────────────────────────────────────────────────────────────────────
# Role mind — one integrated design pass (Animation Director + Cinematographer + Continuity)
# ─────────────────────────────────────────────────────────────────────────────────────────
def _design_mind():
    return (
        "You are an integrated directing unit for a Pixar-calibre 3D CGI children's show (ages 4-8): "
        "the ANIMATION DIRECTOR (Glen Keane's chair — performance, humour, weight, appeal), the "
        "CINEMATOGRAPHER (Patrick Lin's chair — shots, lenses, movement, visual progression) and the "
        "CONTINUITY SUPERVISOR (every persistent visual and spatial state). You photograph an "
        "already-directed, LOCKED storyboard. The render model must never be asked to decide comedy, "
        "staging, camera, geography or continuity: you decide all of it here.\n\n"
        "NON-NEGOTIABLE LAWS:\n"
        "1. SCRIPT TRUTH: dialogue is locked. Copy each line into dialogueLines EXACTLY as given in "
        "the beats — same words, same order, every line assigned to exactly one shot, none dropped, "
        "none invented. delivery is acting direction, never a rewrite.\n"
        "2. ONE performance assignment per shot: one physical/emotional cause with its visible "
        "consequences — never a mini-film of competing actions. A dive AND a crash AND a recovery is "
        "usually 2 shots, sometimes 3, never 1.\n"
        "3. The opening pose is ANTICIPATION, never the payoff: the character begins OUTSIDE the "
        "flower with the flower positioned for contact — never already buried in the result.\n"
        "4. Every cut is DESIGNED (matched action, reaction cut, eyeline, sound bridge, foreground "
        "wipe) — state cutInMotivation for every shot after the first. No arbitrary cuts.\n"
        "5. Screen direction and geography stay consistent; state who is frame-left/right in every "
        "continuity state, and keep marks/props identical across each relay join (what leaves a shot "
        "enters the next unchanged).\n"
        "6. NEVER describe a character's appearance anywhere — identity comes only from reference "
        "images. Poses, positions and expressions yes; looks, colours, species features no.\n"
        "7. Comedy physics: weight, compression, rebound, follow-through — chained cause and "
        "consequence, never a checklist of verbs. For a BIG-comedy beat, put the full physicalStaging "
        "contract on the shot that carries the gag's physical event; leave it null everywhere else.\n"
        "8. Only the named speaker's mouth moves; listeners react silently. Dialogue timing must fit "
        "inside the shot with breathing room.\n"
        "9. OBSERVABLE DIRECTION LAW (Julian's ruling, 2026-07-16): performanceAssignment, "
        "physicalStaging and visualPayoff are RENDER-FACING — they may contain ONLY what a camera "
        "sees or a microphone hears: movement, pose, expression, timing, camera-visible cause and "
        "effect, and sound. Abstract intent, judgments, metaphors and inner states ('the pose "
        "becomes the joke', 'sells it as status', 'mistakes attention for permission') are valid "
        "creative planning but belong ONLY in purpose — never in the three render-facing fields. "
        "Translate every intention into visible behaviour: lean, not micro-choreographed.\n"
        "WORD DISCIPLINE (hard limits): performanceAssignment 25-50 words; camera <= 15; "
        "openingPose <= 30; visualPayoff <= 15; purpose <= 12. Precision over volume.\n"
        "10. NEVER restate the audio/lip-sync assignment inside performanceAssignment or "
        "visualPayoff (e.g. 'Lip-sync the approved audio; no additional speech') — that "
        "instruction is generated mechanically from dialogueLines and shipped separately, "
        "every time. Repeating it here only burns your own word budget on something already "
        "said; spend it on the physical action instead.\n"
        "11. For a BIG-comedy beat, physicalStaging.contactAndWeight is the shot's REAL "
        "cause-and-effect chain — what hits what, where it bends, where it rebounds, what "
        "flies loose — and reaches the provider on its own, alongside performanceAssignment, "
        "not folded into it. Keep it a concrete, staged sequence of physical events, never a "
        "summary of the same beat performanceAssignment already covers.\n"
        "Output STRICT JSON matching the schema you are given."
    )


def _load_pkg(episode):
    cands = sorted((HERE.parent / "cb-output").glob(f"{episode}_*beat_package.json"),
                   key=lambda p: p.stat().st_mtime)
    if not cands:
        raise FileNotFoundError(f"no beat package for {episode} in cb-output/")
    return json.load(open(cands[-1])), cands[-1]


def _beat_sort_key(code):
    """Natural sort on the trailing beat number ('3.B10' -> 10) — inlined from the deleted
    legacy cb_preflight at the 2026-07-16 cutover; the one thing cb_engine used from it."""
    m = re.search(r"[Bb](\d+)\s*$", str(code or ""))
    return int(m.group(1)) if m else 0


def _scene_beats(d, scene_num):
    beats = [b for b in d.get("beats") or [] if str(b.get("sceneNumber")) == str(scene_num)]
    beats.sort(key=lambda b: _beat_sort_key(b.get("beatCode") or ""))
    return beats


def _beat_digest(beats):
    """What the design pass reads: the director's own locked creative content. Full dialogue
    text IS included here — the design must copy it verbatim into dialogueLines; this is
    authoring context, never render-prompt text (the Law-6 guard sits at compile time)."""
    out = []
    for b in beats:
        out.append({
            "beatCode": b.get("beatCode"),
            "storyBeat": b.get("storyBeat"),
            "comedyMode": b.get("comedyMode"),
            "cuts": [{"framing": c.get("framing"), "action": c.get("action"),
                       "dialogue": c.get("dialogue") or None,
                       "delivery": c.get("delivery")} for c in (b.get("cuts") or [])],
            "startState": b.get("startState"),
            "endState": b.get("endState"),
            "carryMarks": b.get("carryMarks"),
            "characters": b.get("characters"),
        })
    return out


# ─────────────────────────────────────────────────────────────────────────────────────────
# STAGE: the scene's shot design — one structured call, then validate, then ONE repair pass
# ─────────────────────────────────────────────────────────────────────────────────────────
def _design_user_prompt(scene_num, scene, beats):
    return (
        f"SCENE {scene_num} — '{scene.get('name', '')}'\n"
        f"Location: {scene.get('location', '')}\nLook: {scene.get('sceneLook', scene.get('lighting', ''))}\n"
        f"Emotional core: {scene.get('emotionalCore', '')}\n\n"
        f"THE DIRECTOR'S LOCKED BEATS (the story truth — photograph these, never rewrite them):\n"
        f"{json.dumps(_beat_digest(beats), ensure_ascii=False, indent=1)}\n\n"
        "TASK 1 — the DIRECTOR'S STATEMENT for this scene (the six questions).\n"
        "TASK 2 — the SHOT LIST: convert each beat into 1-3 shots of 4-8 seconds. shotId = "
        "'{beatCode}.S{n}' (e.g. '1.B1.S1'). The FIRST shot of the scene is sourceType='opener' with "
        "sourceShotId=null. EVERY LATER SHOT DEFAULTS TO 'relay' (sourceShotId = the earlier shot "
        "whose final frame it continues from, usually the previous one) — this applies whether the "
        "camera holds on the same coverage OR cuts to something new; a relay shot's own camera and "
        "action are completely free to describe a new setup, relay only means this shot's opening "
        "frame anchors identity/position/lighting off the previous shot's real final frame instead "
        "of inventing a disconnected one. Use 'opener' (sourceShotId=null) ONLY for a genuine scene "
        "or location reset — never merely because the shot is a cut. "
        "Every shot: ONE performance assignment, an anticipation openingPose, an exact visualPayoff, "
        "typed continuityIn/continuityOut (zone, facing, pose, expression, marks, props for every "
        "character in frame), dialogueLines copied VERBATIM with timing, at most 3 prohibited items, "
        "and physicalStaging on the gag-carrying shot of each BIG-comedy beat."
    )


def _clear_opener_continuity_in(design):
    """THE SIMPLIFICATION (2026-07-17, Julian's system-freeze checkpoint): the scene's own
    first shot has no predecessor to inherit continuity from — cleared MECHANICALLY, never
    trusted from the LLM (the identical structural-fact treatment
    cb_creative.production_detail already applies to its own opener shot's continuityIn).
    Typed absence (None), not a sentinel string. A no-op on an empty shot list."""
    if design.shots:
        design.shots[0].continuityIn = None


def design_scene(episode, scene_num, log=print):
    d, pkg_path = _load_pkg(episode)
    beats = _scene_beats(d, scene_num)
    if not beats:
        raise ValueError(f"no beats for scene {scene_num}")
    scene = next((s for s in d.get("scenes") or [] if str(s.get("sceneNumber")) == str(scene_num)), {})
    try:
        characters_cfg = json.load(open(P.CHARS))
    except Exception:
        characters_cfg = {}

    user = _design_user_prompt(scene_num, scene, beats)
    log(f"ENGINE — designing scene {scene_num}: statement + shot list (one structured call)...", flush=True)
    result = cb_llm.structured(_design_mind(), user, SceneShotList,
                                label=f"engine_design_s{scene_num}")
    _clear_opener_continuity_in(result)

    # the deterministic validator, then at most ONE repair pass (same discipline as Gate 1's
    # beat_problems loop): errors go back to the same mind, verbatim, fix-only
    report = validate_scene_design(result, beats, characters_cfg)
    if not report["passed"]:
        issues = [f"[{i['severity']}] {i['code']} at {i['path']}: {i['message']}"
                  for i in report["issues"] if i["severity"] == "ERROR"]
        log(f"ENGINE — design has {len(issues)} validation error(s); one repair pass...", flush=True)
        repair_user = (user + "\n\nYOUR PREVIOUS DESIGN FAILED VALIDATION. Return the FULL corrected "
                       "design, changing ONLY what these errors require:\n" + "\n".join(issues))
        result = cb_llm.structured(_design_mind(), repair_user, SceneShotList,
                                    label=f"engine_design_s{scene_num}_repair")
        _clear_opener_continuity_in(result)
        report = validate_scene_design(result, beats, characters_cfg)
    # THE OBSERVABLE-DIRECTION TRANSLATOR (Julian's directive, 2026-07-16): abstract direction is
    # never the user's problem to fix by hand — the Episode Director repairs it automatically,
    # field-scoped, before compilation. Runs only when the deterministic validator found any.
    if any(i["code"] in REPAIRABLE_CODES for i in report["issues"]):
        _, _, report = auto_repair_abstract_directions(result, beats, characters_cfg, log=log)
    return result, report, beats, scene, d, pkg_path


# ─────────────────────────────────────────────────────────────────────────────────────────
# THE OBSERVABLE-DIRECTION REPAIR LOOP (Julian's 10-point directive, 2026-07-16): when the
# deterministic validator rejects a render-facing field as abstract, ONLY that field goes back
# to the Episode Director for automatic translation into observable direction — with the
# creative purpose, duration, continuity, behaviour, camera, dialogue timing, authored
# constraints and model-feasibility limits supplied read-only. At most TWO attempts, each
# deterministically revalidated; both failing escalates to the user. Every repair is recorded
# in full — never silent. The original abstract text is preserved as PLANNING METADATA
# (creativeIntent) and never enters a Seedance prompt.
# ─────────────────────────────────────────────────────────────────────────────────────────
REPAIR_MAX_ATTEMPTS = 2
REPAIR_PROMPT_VERSION = "2026-07-16.2"
REPAIRABLE_CODES = ("ABSTRACT_DIRECTION", "FIELD_OVERBUDGET")
REPAIR_PROTECTED_FIELDS = ("purpose", "durationSec", "camera", "dialogueLines", "dialogueBinding",
                            "continuityIn", "continuityOut", "prohibited", "physicalStaging",
                            "sourceType", "sourceShotId", "openingPose", "charactersInFrame",
                            "shotId", "beatCode", "cutInMotivation")
FEASIBILITY_LIMITS = ("One continuous 4-8 second shot, no camera cuts. Only what a camera can see "
                      "or a microphone can hear: movement, pose, expression, timing, physical "
                      "cause and effect, and sound. At most one or two clear actions per second. "
                      "No inner states, judgments, metaphors or narrative commentary.")


class _FieldRepair(BaseModel):
    text: str = Field(min_length=1)


def _field_abstract_hits(text):
    return [m.group(0) for m in (p.search(text or "") for p in _ABSTRACT_DIRECTION) if m]


def _field_rejections(field_name, text):
    """The deterministic field-level verdict the repair loop revalidates against — the SAME
    two checks validate_scene_design applies: abstraction and the field's own word budget."""
    problems = [f"still abstract: \"{h}\"" for h in _field_abstract_hits(text)]
    budget = FIELD_WORD_BUDGETS.get(field_name)
    if budget and len((text or "").split()) > budget:
        problems.append(f"{len(text.split())} words against the field's {budget}-word budget")
    return problems


def _repair_context(shot):
    """Point 3: everything the translator needs, read-only. Dialogue travels as speaker+timing
    only — the exact words never need to leave the audio path even internally."""
    return {
        "creativePurpose": shot.purpose,
        "shotDurationSec": shot.durationSec,
        # continuityIn is None for the scene's own first shot (typed absence) — nothing to
        # report, never an AttributeError.
        "openingContinuity": shot.continuityIn.model_dump() if shot.continuityIn else None,
        "closingContinuity": shot.continuityOut.model_dump(),
        "characterBehaviour": {c.character: {"pose": c.pose, "expression": c.expression,
                                              "screenZone": c.screenZone}
                                for c in (shot.continuityIn.characters if shot.continuityIn else [])},
        "camera": shot.camera,
        "dialogue": [{"speaker": l.speaker, "startSec": l.startSec, "endSec": l.endSec}
                      for l in shot.dialogueLines],
        "authoredConstraints": (list(shot.prohibited)
                                 + (list(shot.physicalStaging.prohibitedStaging)
                                    if shot.physicalStaging else [])),
        "modelFeasibilityLimits": FEASIBILITY_LIMITS,
    }


def repair_abstract_field(shot, field_name, current_text, offending, prev_failure=None):
    """One repair attempt: the Episode Director translates ONE rejected field into observable
    direction. It receives only that field plus the protected context; it can change nothing else
    by construction. Lean, not micro-choreographed."""
    system = ("You are the Episode Director's observable-action translator for a 3D CGI "
              "children's show. Rewrite ONE rejected direction field as purely filmable "
              "direction: visible movement, pose, expression, timing, camera-visible cause and "
              "effect, and sound. You are translating creative intent into behaviour — keep the "
              "creative purpose EXACTLY; never change the story, screen geography, camera, "
              "duration, opening state, continuity destination or authored constraints; never "
              "add new events, props or characters; never quote spoken words. LEAN, not "
              "micro-choreographed — the field's own hard word budget is in the payload and is "
              "a deterministic rejection if exceeded.")
    payload = {"fieldToRewrite": field_name, "currentText": current_text,
               "rejectedFor": offending,
               "hardWordBudget": FIELD_WORD_BUDGETS.get(field_name),
               "protectedContext": _repair_context(shot)}
    if prev_failure:
        payload["previousAttemptRejected"] = prev_failure
    r = cb_llm.structured(system, json.dumps(payload, ensure_ascii=False, indent=1),
                           _FieldRepair, label=f"repair_{shot.shotId}_{field_name}")
    return r.text.strip()


def auto_repair_abstract_directions(design, beats, characters_cfg, log=print):
    """Points 3-6: field-scoped automatic repair with deterministic revalidation after every
    attempt, a two-attempt cap, loud escalation, and a full record. Returns
    (repair_log, escalations, final_validation_report). Mutates only the rejected fields;
    every protected field is asserted byte-identical afterwards."""
    repair_log, escalations = [], []
    report = validate_scene_design(design, beats, characters_cfg)
    targets = {}
    for i in report["issues"]:
        if i["code"] not in REPAIRABLE_CODES:
            continue
        sid = i["path"].split("(")[1].split(")")[0]
        targets.setdefault((sid, i["path"].split(".")[-1]), []).append(i["message"])
    for (sid, fld) in targets:
        shot = next(s for s in design.shots if s.shotId == sid)
        protected_before = {f: json.dumps(getattr(shot, f), default=lambda o: o.model_dump(),
                                           sort_keys=True) for f in REPAIR_PROTECTED_FIELDS}
        original = getattr(shot, fld)
        offending = _field_rejections(fld, original)
        repaired, prev_failure = False, None
        for attempt in range(1, REPAIR_MAX_ATTEMPTS + 1):
            replacement = repair_abstract_field(shot, fld, original, offending, prev_failure)
            problems = _field_rejections(fld, replacement)
            entry = {"shotId": sid, "field": fld, "attempt": attempt, "original": original,
                     "replacement": replacement,
                     "reason": "; ".join(offending),
                     "model": cb_llm.DIRECTOR_MODEL, "promptVersion": REPAIR_PROMPT_VERSION,
                     "protectedFields": list(REPAIR_PROTECTED_FIELDS),
                     "validationResult": (f"REJECTED — {'; '.join(problems)}" if problems
                                           else "PASSED deterministic revalidation")}
            repair_log.append(entry)
            log(f"REPAIR — {sid}.{fld} attempt {attempt}: {entry['validationResult']}", flush=True)
            if problems:
                prev_failure = {"text": replacement, "rejectedFor": problems}
                continue
            setattr(shot, fld, replacement)
            repaired = True
            break
        if not repaired:
            escalations.append({"shotId": sid, "field": fld, "original": original,
                                 "reason": f"both automated repair attempts still abstract — "
                                           f"a creative decision is needed"})
        # the repair can never touch a protected field — asserted, not assumed
        for f in REPAIR_PROTECTED_FIELDS:
            now = json.dumps(getattr(shot, f), default=lambda o: o.model_dump(), sort_keys=True)
            assert now == protected_before[f], (
                f"REPAIR VIOLATION: {sid}.{f} changed during a field-scoped repair of {fld}")
    final = validate_scene_design(design, beats, characters_cfg)
    return repair_log, escalations, final


# ─────────────────────────────────────────────────────────────────────────────────────────
# THE VALIDATOR — deterministic, zero-LLM, runs before any money (adopted from the Enaid
# reference architecture; extended with this studio's verbatim-dialogue lock)
# ─────────────────────────────────────────────────────────────────────────────────────────
def _norm(s):
    return re.sub(r"[^a-z0-9']+", " ", (s or "").lower().replace("’", "'")).strip()


def _canon_speaker(label, characters_cfg):
    """Resolve a script speaker label ('FUZZBY', "KEEN'S MUM") to its canonical cast name.
    Exact case-insensitive match only — never substring (the Keen/Keen's-Mum lesson)."""
    want = _norm(label)
    for name in characters_cfg:
        if _norm(name) == want:
            return name
    return label.strip()


def _expected_lines(beats):
    """(speaker_label, exact_text) for every dialogue line the locked beats carry, in order."""
    out = []
    for b in beats:
        for c in (b.get("cuts") or []):
            dlg = (c.get("dialogue") or "").strip()
            if dlg and ":" in dlg:
                spk, txt = dlg.split(":", 1)
                if txt.strip():
                    out.append((spk.strip(), txt.strip().strip('"“”').strip()))
    return out


# The design mind's own per-field word discipline, enforced deterministically.
# 2026-07-17 correction (Julian's consolidation-checkpoint directive, item 4): visualPayoff's
# own 15-word cap was REMOVED — an arbitrary per-field budget that rejected S1.SH1's real,
# already-approved 18-word closingImage for no reason tied to the actual constraint that
# matters (whether the COMPILED provider brief fits its own hard cap). performanceAssignment
# kept its own 50-word budget at that time (deliberately not named in that correction).
#
# 2026-07-17 SECOND CORRECTION, SAME DAY (Julian's explicit decision, PIPELINE_CUTOVER_
# LEDGER.md §10): performanceAssignment's own 50-word cap is now ALSO removed, for the
# identical reason — it rejected Gate 5's real, approved physicalPerformance (72-92 words on
# every real Scene 1 dialogue-bearing shot; Gate 5's own authoring instruction was never
# written under a 50-word discipline) purely on field-isolated length, while the ACTUAL
# provider-facing brief it feeds compiles comfortably inside the real ceiling. This dict is
# now EMPTY — no per-field word cap remains anywhere, and none is to be reintroduced (Julian:
# "do not introduce a replacement field limit"). The governing constraint is, and stays, the
# COMPILED brief's own hard cap: MAX_SHOT_PROMPT_WORDS/MAX_KEYFRAME_PROMPT_WORDS plus the
# COMPILABILITY check below (a real compile_shot_contract call) — both fully unconditional,
# on the real shipped text, exactly as before. Law 6 (_assert_no_spoken_words, inside that
# same compile call) and the ABSTRACT_DIRECTION safety/renderability scan just below are
# ALSO unweakened — this correction touches only the isolated per-field length budget, no
# other check.
FIELD_WORD_BUDGETS = {}

# Known unrenderable-abstraction constructs (Julian's correction, 2026-07-16, point 3). A tight,
# documented heuristic — high-confidence psychological-intent shapes only, so a real staging verb
# never false-fails. Extended only with evidence, never speculatively.
_ABSTRACT_DIRECTION = [re.compile(p, re.IGNORECASE) for p in (
    r"measures?\s+the\s+difference",
    r"\bmistakes?\b[\w\s'’]{0,40}?\bas\b",
    r"\bas\s+(?:status|permission)\b",
    r"\bas\s+(?:his|her|their)\s+specialty\b",
    r"\bsell(?:s|ing)?\b[\w\s'’]{0,30}?\bas\b",
    r"\bfeel\s+(?:larger|bigger|smaller)\b",
    r"refus\w*\s+to\s+decorate",
    r"offers?\s+the\s+accident",
    r"becomes?\s+the\s+joke\b",
)]


def validate_scene_design(design, beats, characters_cfg):
    """The design-time gate: every check deterministic, every issue named with a path.
    ERRORs block compilation; WARNINGs report."""
    issues = []
    add = lambda sev, code, path, msg: issues.append(
        {"severity": sev, "code": code, "path": path, "message": msg})

    known_ids, seen_norm_lines = [], []
    shots_by_id = {}
    for i, sh in enumerate(design.shots):
        path = f"shots[{i}]({sh.shotId})"
        if sh.shotId in shots_by_id:
            add("ERROR", "DUPLICATE_SHOT_ID", path, sh.shotId)
        shots_by_id[sh.shotId] = sh

        for c in sh.charactersInFrame:
            if characters_cfg and _canon_speaker(c, characters_cfg) not in characters_cfg:
                add("ERROR", "UNKNOWN_CHARACTER", f"{path}.charactersInFrame", c)

        # opener/relay integrity — a relay must anchor on an EARLIER shot
        if i == 0 and sh.sourceType != "opener":
            add("ERROR", "FIRST_SHOT_NOT_OPENER", path, "the scene's first shot must be an opener")
        if sh.sourceType == "relay":
            if not sh.sourceShotId:
                add("ERROR", "RELAY_WITHOUT_SOURCE", f"{path}.sourceShotId",
                    "a relay shot must name the earlier shot whose final frame anchors it")
            elif sh.sourceShotId not in known_ids:
                add("ERROR", "INVALID_RELAY_SOURCE", f"{path}.sourceShotId",
                    f"{sh.sourceShotId} is not an earlier shot in this scene")
        elif sh.sourceShotId:
            add("WARNING", "OPENER_WITH_SOURCE", f"{path}.sourceShotId",
                "an opener starts from its own generated keyframe, not a harvested frame")

        # THE CUT-PACE CONSISTENCY CHECK (2026-07-21, Julian's mandate — "it has to fire
        # every single time, it's not optional"): cutPace itself is already required at the
        # schema level (no default), so a shot missing it entirely fails at construction, not
        # here. This catches the SECOND way "not optional" could still be silently violated —
        # a cutPace that claims cuts but names none, or a single-take shot carrying stray
        # internalCuts left over from an edit, either of which would compile a real, visible
        # mismatch between the Director's stated decision and what actually ships.
        if sh.cutPace == "single_continuous_take" and sh.internalCuts:
            add("ERROR", "CUTPACE_MISMATCH", f"{path}.internalCuts",
                "single_continuous_take must carry no internalCuts — performanceAssignment "
                "alone carries that case; leftover internalCuts suggest a stale edit")
        if sh.cutPace in ("paced_cuts", "rapid_cuts") and len(sh.internalCuts) < 2 \
                and not sh.composedOf:
            add("ERROR", "CUTPACE_MISMATCH", f"{path}.internalCuts",
                f"cutPace={sh.cutPace!r} requires at least 2 authored internalCuts, got "
                f"{len(sh.internalCuts)} — the Director's own pace decision has nothing to "
                f"deliver it")

        # THE CLIP/CARD SEPARATION CHECK (2026-07-25). composedOf is the reference form
        # of internal cutting: this generation renders these other Shot Cards in order,
        # reading their own authored fields. The two forms are mutually exclusive — a
        # clip that both references cards AND retypes prose cuts has two competing
        # authorities for the same segments, which is exactly what this field exists to
        # end. Membership itself is resolved (and its own errors raised) below.
        if sh.composedOf:
            if sh.internalCuts:
                add("ERROR", "CLIP_MEMBER_CONFLICT", f"{path}.composedOf",
                    "a clip may reference member Shot Cards OR author prose internalCuts, "
                    "never both — two authorities for the same segments")
            if sh.cutPace == "single_continuous_take":
                add("ERROR", "CUTPACE_MISMATCH", f"{path}.composedOf",
                    "single_continuous_take renders one camera shot — it cannot compose "
                    "several member cards")
            if len(set(sh.composedOf)) != len(sh.composedOf):
                add("ERROR", "CLIP_MEMBER_CONFLICT", f"{path}.composedOf",
                    "the same member card is listed twice in one clip")
            try:
                resolve_clip_members(sh, design.shots)
            except ClipMemberError as e:
                add("ERROR", "CLIP_MEMBER_UNRESOLVED", f"{path}.composedOf", str(e))
        owner = clip_owner_of(sh.shotId, design.shots)
        if owner and sh.composedOf:
            add("ERROR", "CLIP_MEMBER_CONFLICT", f"{path}.composedOf",
                f"{sh.shotId} is already a member of clip {owner} — a member card is a "
                f"camera shot, never itself a clip")
        owners = [s.shotId for s in design.shots
                  if s.shotId != sh.shotId and sh.shotId in (getattr(s, "composedOf", None) or [])]
        if len(owners) > 1:
            add("ERROR", "CLIP_MEMBER_CONFLICT", f"{path}.shotId",
                f"{sh.shotId} is claimed as a member by more than one clip "
                f"({', '.join(owners)}) — it would render twice")

        # dialogue: speaker visible, timing sane, binding consistent
        in_frame = {_norm(c) for c in sh.charactersInFrame}
        for j, ln in enumerate(sh.dialogueLines):
            lp = f"{path}.dialogueLines[{j}]"
            if _norm(ln.speaker) not in in_frame and _norm(ln.speaker) != "all":
                add("ERROR", "SPEAKER_NOT_VISIBLE", lp, f"{ln.speaker} is not in charactersInFrame")
            if ln.endSec > sh.durationSec:
                add("ERROR", "DIALOGUE_OVERRUN", lp,
                    f"line ends at {ln.endSec}s in a {sh.durationSec}s shot")
            if ln.startSec >= ln.endSec:
                add("ERROR", "INVALID_DIALOGUE_TIMING", lp, "start must precede end")
            seen_norm_lines.append((_norm(ln.speaker), _norm(ln.exactText), lp))
        if sh.dialogueLines and not sh.dialogueBinding:
            add("ERROR", "BINDING_MISSING", f"{path}.dialogueBinding",
                "shot carries dialogue lines but no prompt-facing binding sentence")
        if sh.dialogueBinding and not sh.dialogueLines:
            add("ERROR", "LINES_MISSING", f"{path}.dialogueLines",
                "shot has a dialogue binding but no typed lines for the voice pass")

        # TYPED ABSENCE (2026-07-17, THE SIMPLIFICATION): continuityIn=None is valid ONLY
        # for the scene's own first shot — every other shot must state what it inherits.
        # Mechanically enforced in design_scene (_clear_opener_continuity_in); these two
        # checks are defense-in-depth, catching a stale/hand-edited/reloaded design
        # (repair_package reconstructs Shot objects straight from a stored package) rather
        # than trusting the mechanical clear blindly.
        if i == 0 and sh.continuityIn is not None:
            add("ERROR", "OPENER_CONTINUITY_IN_NOT_CLEARED", f"{path}.continuityIn",
                "the scene's first shot must have continuityIn=null (no predecessor) — "
                "the mechanical clear did not run or was overwritten")
        if i > 0 and sh.continuityIn is None:
            add("ERROR", "CONTINUITY_IN_MISSING", f"{path}.continuityIn",
                "only the scene's first shot may have continuityIn=null; this shot must "
                "state what it genuinely inherits from the one before it")

        # continuity states must cover everyone in frame (continuityIn skipped when None —
        # the scene's own first shot, nothing to cover)
        for state_name, state in (("continuityIn", sh.continuityIn),
                                    ("continuityOut", sh.continuityOut)):
            if state is None:
                continue
            covered = {_norm(cs.character) for cs in state.characters}
            for c in sh.charactersInFrame:
                if _norm(c) not in covered:
                    add("ERROR", "CONTINUITY_CAST_INCOMPLETE", f"{path}.{state_name}",
                        f"{c} is in frame but missing from {state_name}")

        # relay join: marks and props must carry across the cut unchanged. sh.continuityIn
        # is None only for a validly-cleared scene opener — never sourceType=="relay" (a
        # relay shot with continuityIn=None already carries CONTINUITY_IN_MISSING above;
        # skip this join check rather than crash on it, the same graceful-degrade the rest
        # of this validator uses for every other already-reported malformed state).
        if (sh.sourceType == "relay" and sh.sourceShotId in shots_by_id
                and sh.sourceShotId != sh.shotId and sh.continuityIn is not None):
            src = shots_by_id[sh.sourceShotId]
            prior = {_norm(cs.character): cs for cs in src.continuityOut.characters}
            for cs in sh.continuityIn.characters:
                p = prior.get(_norm(cs.character))
                if not p:
                    continue
                if _normset(p.visibleMarks) != _normset(cs.visibleMarks):
                    add("ERROR", "MARK_DRIFT", f"{path}.continuityIn",
                        f"{cs.character}'s visible marks do not match {sh.sourceShotId}'s continuityOut")
                if _normset(p.heldProps) != _normset(cs.heldProps):
                    add("ERROR", "PROP_DRIFT", f"{path}.continuityIn",
                        f"{cs.character}'s held props do not match {sh.sourceShotId}'s continuityOut")
        known_ids.append(sh.shotId)

    # THE VERBATIM LOCK: every locked dialogue line assigned exactly once, word for word.
    # THE MULTISET FIX (2026-07-22, Julian's full-audit directive — a real, confirmed bug):
    # the original check counted matches by GLOBAL value equality, not by consuming one
    # matched instance per expected line — so a scene where the same speaker legitimately
    # says the exact same locked words twice (a catchphrase, an exclamation) had BOTH
    # correctly-assigned occurrences double-count each other's match and get wrongly flagged
    # DIALOGUE_LINE_DUPLICATED, even though the assignment was a valid 1:1 mapping. Counting
    # by multiset (how many times this exact (speaker, text) pair is EXPECTED vs. how many
    # times it actually GOT assigned) is the correct generalization — it agrees with the old
    # check whenever no locked line is a value-duplicate of another (the common case) and
    # only differs in the case the old check got wrong.
    from collections import Counter
    expected = _expected_lines(beats)
    exp_norm = [(_norm(_canon_speaker(s, characters_cfg)), _norm(t)) for s, t in expected]
    got_norm = [(_norm(_canon_speaker(s, characters_cfg)), t) for s, t, _ in seen_norm_lines]
    exp_counts = Counter(exp_norm)
    got_counts = Counter(got_norm)
    reported = set()
    for (es, et), (raw_s, raw_t) in zip(exp_norm, expected):
        if (es, et) in reported:
            continue
        reported.add((es, et))
        exp_n, got_n = exp_counts[(es, et)], got_counts.get((es, et), 0)
        if got_n < exp_n:
            short = exp_n - got_n
            add("ERROR", "DIALOGUE_LINE_DROPPED", "shots",
                f"locked line not assigned to any shot"
                f"{f' ({short} of {exp_n} occurrences missing)' if exp_n > 1 else ''} — "
                f"{raw_s}: \"{raw_t}\"")
        elif got_n > exp_n:
            add("ERROR", "DIALOGUE_LINE_DUPLICATED", "shots",
                f"locked line assigned to {got_n} shots"
                f"{f' (expected {exp_n})' if exp_n > 1 else ''} — {raw_s}: \"{raw_t}\"")
    for gs, gt, lp in seen_norm_lines:
        if not any(gs == es and gt == et for es, et in exp_norm):
            add("ERROR", "DIALOGUE_NOT_VERBATIM", lp,
                "line does not match any locked script line word for word")

    # RE-HOMED KEEPERS (architecture recovery, 2026-07-16 — the camera-lock law, rule 38,
    # and the checklist-verb Motion Contract flag, rule 78, re-pointed at shot contracts;
    # WARNING-only, per the house rule that computed proxies advise, never hard-block):
    _CAM_MOVE = re.compile(r"\b(pan|push|track(?:ing)?|doll(?:y|ies)|whip|zoom|orbit|crane|"
                            r"tilt|sweep|chase|barrel)\b", re.IGNORECASE)
    for i, sh in enumerate(design.shots):
        path = f"shots[{i}]({sh.shotId})"
        if sh.dialogueLines and _CAM_MOVE.search(sh.camera or ""):
            add("WARNING", "CAMERA_MOVE_DURING_DIALOGUE", f"{path}.camera",
                "the camera law prefers a locked camera while a line lands "
                "(a hum/sing-song is exempt) — check the move is deliberate")
        frags = [f for f in re.split(r"[,;]", sh.performanceAssignment or "") if f.strip()]
        if len(frags) >= 5:
            add("WARNING", "CHECKLIST_ASSIGNMENT", f"{path}.performanceAssignment",
                f"{len(frags)} comma-separated fragments — the Motion Contract wants one "
                "cause with chained consequences, not a checklist of verbs")
        # ABSTRACT DIRECTION (Julian's correction, 2026-07-16, point 3): a video model cannot
        # render psychological intent. Never stripped, never auto-rewritten in place — the field
        # FAILS with the offending phrase named, and the repair loop (or a human) corrects the
        # source. Deterministic heuristic (known unrenderable constructs), per the
        # concrete-criteria doctrine. FIELD OVERBUDGET is the same class: a deterministic
        # field-level rejection the repair loop translates, respecting the design mind's own
        # word discipline.
        for field_name, field_text in (("performanceAssignment", sh.performanceAssignment),
                                         ("visualPayoff", sh.visualPayoff)):
            for pat in _ABSTRACT_DIRECTION:
                m = pat.search(field_text or "")
                if m:
                    add("ERROR", "ABSTRACT_DIRECTION", f"{path}.{field_name}",
                        f"unrenderable psychological intent — \"{m.group(0)}\" — replace with "
                        f"observable movement in the source contract (never auto-rewritten)")
            budget = FIELD_WORD_BUDGETS.get(field_name)
            if budget is not None:
                n = len((field_text or "").split())
                if n > budget:
                    add("ERROR", "FIELD_OVERBUDGET", f"{path}.{field_name}",
                        f"{n} words against the field's own {budget}-word discipline — "
                        f"lean direction, never micro-choreography")

    # COMPILABILITY (2026-07-21 correction — the word-ceiling ERROR this check used to
    # raise, SHOT_OVERBUDGET, is retired: Julian's own direct ruling removed the hard word
    # ceiling from compile_shot_contract entirely, so length can no longer make a shot
    # uncompilable. The one real failure mode left here is a genuine COMPILE_GUARD — e.g.
    # Law 6's spoken-words assertion — never a length count. Compilation is fully
    # deterministic (no LLM), so this stays cheap to run on every shot regardless.
    for i, sh in enumerate(design.shots):
        try:
            compile_shot_contract(sh, {}, characters_cfg, siblings=design.shots)
        except (ValueError, AssertionError) as e:
            add("ERROR", "COMPILE_GUARD", f"shots[{i}]({sh.shotId})", str(e))

    # the physical-staging contract: every BIG-comedy beat carries the gag physics somewhere
    big_beats = {b.get("beatCode") for b in beats
                 if str(b.get("comedyMode") or "").upper() == "BIG"}
    staged = {sh.beatCode for sh in design.shots if sh.physicalStaging}
    for bc in sorted(big_beats - staged):
        add("ERROR", "MISSING_PHYSICAL_STAGING", f"beat {bc}",
            "a BIG-comedy beat needs the full physicalStaging contract on its gag-carrying shot")

    return {"passed": all(i["severity"] != "ERROR" for i in issues), "issues": issues}


def _normset(values):
    return "|".join(sorted(_norm(v) for v in values if _norm(v)))


# ─────────────────────────────────────────────────────────────────────────────────────────
# COMPILERS — mechanical, short, platform-length. Spoken words and appearance text can
# never enter these outputs: guarded by construction AND by assertion.
# ─────────────────────────────────────────────────────────────────────────────────────────
_STYLE_LAW_PATH = HERE.parent / "shows/crystal-bears/laws/style.txt"


def _style_law_text():
    """The show's own single locked style line (rule 75, Julian's feature-caliber craft
    rewrite) — read fresh every call. Every OTHER consumer of this file (cb_render._scene_
    context, the department LLM prompts) already had it; this compiler's own _style_line
    never did, shipping a thinner, disconnected hardcoded string instead (2026-07-21 audit,
    Julian's own techhalla-example comparison — the actual gap wasn't a missing gate, it was
    this compiler simply not quoting a law that already existed).

    NEVER CACHED (2026-07-22, Julian's full-audit directive — the same bug class as the
    long-running-server-serves-stale-logic bug fixed elsewhere tonight, reproduced here for
    a data file instead of a .py file): a module-level cache populated once and never
    invalidated meant an edit to style.txt mid-session was invisible for the rest of that
    process's life — no error, no staleness flag, nothing in serve.py's freshness fingerprint
    watches non-.py files under shows/. A single small text-file read costs nothing worth
    caching; reading it fresh every call closes the gap outright rather than adding another
    invalidation path to keep in sync."""
    return _STYLE_LAW_PATH.read_text().strip() if _STYLE_LAW_PATH.exists() else ""


# THE QUALITY LINE (2026-07-21, Julian, comparing our compiled prompts against a real
# AAA-grade example he'd watched delivered): the example's own closing "STYLE & QUALITY
# BOOSTERS" block — a dense, POSITIVE technical/craft line, distinct from this compiler's
# existing "Hard constraints" (which is negative-only, prohibitions never affirmations) —
# was the one structural piece with no equivalent here at all. Translated into THIS show's
# own register (stylised 3D CGI, never the source example's photoreal/anamorphic-lens
# language, which belongs to a different visual world entirely) rather than copied.
# Deliberately does not restate anything UNIVERSAL_CONSTRAINTS/_render_critical already
# says (no redesign/no artifacts-as-negation) — this is the positive craft bar, not a sixth
# negatives list.
QUALITY_LINE = ("Craft: richly detailed 3D textures, natural motion blur on fast movement, "
                 "coherent physics throughout, feature-film-level polish and stability.")


def _style_line(scene, shot=None):
    # ONE consistent anchor-matching style rule (Julian, 2026-07-16, point 9 + Option D +
    # the destructive cutover, which removed the last legacy style-scaffolding phrases
    # scaffolding from executable source): a SHOT's style anchor IS its own @图1; a KEYFRAME
    # (shot=None) makes the first frame, so its style anchors to the references it is given.
    # The signed 1.B1.S1 keyframe predates this wording and stands unchanged as a file.
    law = _style_law_text()
    if shot is None:
        base = ("Stylised feature-quality 3D CGI with natural weight. Preserve the exact "
                 "character designs, proportions, materials, lighting and environment from "
                 "the references.")
        return f"{base} {law}".strip() if law else base
    base = "Stylised feature-quality 3D CGI matching @图1."
    return f"{base} {law}".strip() if law else base


# THE @图1 ANCHORS — Julian's Option D ruling (2026-07-16), CORRECTED 2026-07-19 (Julian,
# watching S1.SH1-SH3 land as three disconnected vignettes instead of one escalating gag:
# "I want each beat to land with laughter or emotion... do what you know works").
#
# Option D's original design treated "opener" as the correct choice for ANY planned editorial
# cut, reserving "relay" (a real harvested-frame anchor) for literal seamless continuation
# only. In practice this meant every cut inside a beat generated its own disconnected fresh
# keyframe, with continuity carried in text only (continuityIn/continuityOut) and never in
# actual pixels — exactly the shape that read as unconnected on real rendered footage.
#
# This project already solved this once, on the old beat-level pipeline (rules 15/21/26/31/
# 51/52 of this show's CLAUDE.md): a CUT and a CONTINUITY-ANCHOR are not the same choice.
# Every shot after the scene's true first one should relay off the previous shot's actual
# harvested final frame for STATE (identity, position, marks, lighting) — regardless of
# whether the camera holds or cuts to new coverage. "Opener" (a fresh, unanchored keyframe)
# is now reserved for a genuine scene/location reset (the Scene Bubble Law), never for "this
# is an editorial cut" alone. The mechanism itself needed no new code: a relay shot has always
# harvested its source shot's real approved final frame (cb_render._anchor_for) — only the
# ANCHOR WORDING and the AUTHORING GUIDANCE (_design_user_prompt below) needed correcting so
# the Director actually chooses relay for these cuts, and so relay's own wording doesn't
# accidentally re-introduce the old anti-hold bug (a literal "continue immediately" phrasing
# that made sense for true seamless continuation but would ask the model to freeze/repeat a
# pose for a beat that's supposed to travel to new coverage).
# 2026-07-20 (Julian, watching real S1.SH1 footage: "no movement no fast paced... no big
# tumble and correction"): the bare anchor gave the model nothing telling it @图1 is a
# LAUNCH point rather than a pose to hold — the exact anti-hold failure mode this show's
# earlier beat-level pipeline already found and fixed multiple times (rules 26/51/76 of
# CLAUDE.md's history). Adding the explicit instruction here, once, mechanically, covers
# every opener shot forever rather than relying on each shot's own free-authored camera/
# performance text to fight the model's own default read of a reference frame.
OPENER_ANCHOR = ("Begin exactly on @图1, the approved opening frame — motion begins "
                  "immediately, never a resting hold.")

RELAY_ANCHOR = ("Begin exactly on @图1, the approved final frame of the previous shot, matched "
                 "for identity, position and lighting.")
# 2026-07-19, tightened same day it was first written: a first draft here also said "then move
# into this shot's own new action, never hold/repeat that pose" — but the compiled sentence
# already concatenates this anchor directly with the shot's OWN camera/action text right after
# it (compile_shot_contract: f"{anchor} — {camera text}."), so stating "move into new action"
# a second time was pure duplication, the exact camera-language-in-the-anchor mistake this
# project's own older doctrine already found and removed once (rule 51's third pass, 2026-07-07:
# "camera direction never appears inside the continuation-state clause... stating 'fresh camera
# setup' a second time is pure duplication... an identity/state instruction only, camera left
# entirely to the shot's own direction"). Dropping "continue... immediately" (which implied a
# held/seamless pose) for a state-only "matched for identity, position and lighting" removes the
# anti-hold risk without needing an explicit negative — and costs zero extra words over the
# original Option D wording (both 18 words), which matters under this module's own tight 210-
# word hard ceiling (confirmed live: the anti-hold-negative first draft pushed S1.SH5 to 219).


def _name_pattern(name, cast):
    """Word-boundary match for a cast name that never fires inside a LONGER cast member's name
    containing it ("Keen" inside "Keen's Mum") — the substring-collision bug class this codebase
    has already fixed twice (cb_voice._resolve_speaker, cb_segprompt._v5_active_cast)."""
    lookaheads = ""
    for other in cast:
        if other != name and other.startswith(name):
            suffix = re.escape(other[len(name):]).replace("'", "['’]")
            lookaheads += f"(?!{suffix})"
    return re.compile(rf"\b{re.escape(name)}\b{lookaheads}")


def _inline_bindings(text, shot, characters_cfg, start=2):
    """Bind each character's reference slot INLINE at their first mention — "Fuzzby (@图2, larger
    bee)" — identity, size and slot in one gesture, exactly where the model reads the name.
    Returns (text, next_slot) — next_slot is the first free @图N after the cast (the plate's slot)."""
    order = sorted(shot.charactersInFrame,
                   key=lambda c: (characters_cfg.get(c, {}).get("sizeRank") or 99))
    epithets = {}
    if len(order) == 2:   # size epithets only when the comparison is meaningful in frame
        kind = lambda c: ("bee" if "bee" in str(characters_cfg.get(c, {}).get("avoid", "")).lower()
                           else "bear")
        epithets[order[0]] = f"smaller {kind(order[0])}"
        epithets[order[1]] = f"larger {kind(order[1])}"
    n = start
    for c in order:
        tag = f"@图{n}" + (f", {epithets[c]}" if c in epithets else "")
        pat = _name_pattern(c, order)
        if pat.search(text):
            text = pat.sub(f"{c} ({tag})", text, count=1)
        else:
            text = f"{c} ({tag}) is in frame. " + text
        n += 1
    return text, n


def reference_slots(shot, characters_cfg, for_keyframe=False):
    """The persisted @图N/@Audio1 slot map — the upload order the fire function must honour.
    Deterministic (same sizeRank sort as _inline_bindings) and persisted in the package so a
    later characters.json edit can never silently reorder an already-compiled shot's uploads.
    A keyframe generation has no @图1 anchor (it MAKES the first frame): cast starts at @图1."""
    order = sorted(shot.charactersInFrame,
                   key=lambda c: (characters_cfg.get(c, {}).get("sizeRank") or 99))
    slots, n = {}, 1
    if not for_keyframe:
        slots["@图1"] = ("opening keyframe" if shot.sourceType == "opener"
                          else "previous shot final frame")
        n = 2
    for c in order:
        slots[f"@图{n}"] = c
        n += 1
    slots[f"@图{n}"] = "scene plate"
    if not for_keyframe and shot.dialogueLines:
        slots["@Audio1"] = "voice track"
    return slots


def _assert_no_spoken_words(prompt, shot, artifact):
    """LAW 6, mechanically enforced at the last possible moment: no dialogue line's words may
    appear in any render prompt. Loud failure, never a silent strip."""
    p = _norm(prompt)
    for ln in shot.dialogueLines:
        t = _norm(ln.exactText)
        if len(t.split()) >= 2 and t in p:
            raise AssertionError(
                f"LAW 6 VIOLATION: spoken words leaked into the {artifact} for {shot.shotId}: \"{ln.exactText}\"")


# ── THE CONSTRAINT REGISTRY (Julian's bounded correction, 2026-07-16) ──────────────────────
# Every machine-injected constraint has a canonical ID and ships with its negation intact (or a
# positive, filmable formulation). Deduplication is by ID + SUBSUMES — never fuzzy text matching.
# Authored shot constraints have no IDs: they ship VERBATIM and are never deduplicated or dropped.
UNIVERSAL_CONSTRAINTS = [                                        # the lean four — every shot, always
    ("no_character_redesign", "no character redesign"),
    ("no_extra_characters", "no extra characters"),
    ("no_onscreen_text", "no on-screen text"),
    ("no_invented_voices", "no invented voices"),
]
# "no_camera_cut" REMOVED (2026-07-22, Julian, live, watching S1.SH1's real render — "no
# freedom to it... no flying, zooming in and out, zigzagging... we have so many rules in
# place that stop the creativity of Seedance"): this was one of the original "lean five"
# (Julian's own 2026-07-16 correction) but forcing it onto EVERY shot in the show, always,
# unconditionally, is itself the over-constraint he's naming — confirmed live in S1.SH1's
# own real, submitted prompt ("One continuous camera relationship with no cuts... Hard
# constraints: ...no camera cut..."), which described exactly one camera vector for the
# full 15s and explicitly forbade anything else. A genuinely continuous, uncut chase shot
# is still a legitimate choice — it's just not a system-wide mandate the Director can never
# override per beat. Whether a shot cuts internally is now the Director's own authored
# choice (camera/cutInMotivation fields), never a machine-injected universal.
SUBSUMES = {  # subsuming ID -> IDs it makes redundant ("no invented voices" covers background too)
    "no_invented_voices": {"no_invented_background_voices"},
}
CONDITIONAL_CAP = 3   # Julian's correction, point 4: the cap applies ONLY to auto-injected
                      # conditional items — never to authored constraints, never to the universal five.


def _conditional_constraints(shot, characters_cfg):
    """THE CONDITIONAL CONSTRAINTS (Julian's rulings, 2026-07-16): proven items ship ONLY when
    their explicit trigger fires, as (canonical_id, text) pairs, in deterministic priority order
    (audio, winged cast, gag physics, ground contact). '2D/flat animation' is carried by the
    style line's own positive statement rather than injected."""
    out = []
    if shot.dialogueLines:                                       # trigger: audio-bearing shot
        out += [("no_foreign_language_speech", "no foreign-language speech"),
                ("no_invented_background_voices", "no invented background voices")]
    if any("bee" in str(characters_cfg.get(c, {}).get("avoid", "")).lower()
           for c in shot.charactersInFrame):                     # trigger: winged cast in frame
        out += [("no_crystals_on_bees", "no crystals on the bees"),
                ("wings_keep_moving", "wings continue moving while airborne")]
    if shot.physicalStaging:                                     # trigger: gag physics contract
        out += [("no_body_inflation", "no body inflation"),
                ("no_full_body_deflation", "no full-body deflation")]
    text = " ".join([shot.performanceAssignment or "", shot.openingPose or "",
                      shot.visualPayoff or ""])
    if re.search(r"\b(land(?:s|ing)?|ground|floor|stands?|sits?|perch(?:es)?|crash(?:es)?|"
                  r"impacts?|drops?|falls?|bounc\w+|rebounds?|slams?)\b", text, re.IGNORECASE):
        out += [("no_floating_sinking", "no floating or sinking through ground")]
    return out


_NEG_LEAD = re.compile(r"^(?:no\b|never\b|do\s+not\b|don['’]t\b|avoid\b)", re.IGNORECASE)
_POS_LEAD = re.compile(r"^(?:preserve|keep|end|hold|maintain|stay|remain|match|continue)\b",
                        re.IGNORECASE)


def _explicit_constraint(item):
    """Point 1: never output a bare phrase. An authored item already carrying negation, or a
    positive filmable imperative, ships VERBATIM; anything else gets an explicit 'no ' prefix —
    negation is added, never stripped, and the authored words are never altered.

    THE FULL-SENTENCE FIX (2026-07-22, found reviewing real compiled Scene-1 output —
    Julian: "we're just going to be now iterating the prompt... see if we can get that
    right"): a real authored essentialProviderProtections item is often a genuine, multi-
    clause director's NOTE — e.g. "Camera must stay still with Zenny; do not grant Fuzzby a
    clean heroic showcase." — which already states its own polarity (positive requirement,
    embedded negation, or both) in its own words. The old check only ever looked at the
    string's FIRST word, so a positive sentence that didn't happen to open on one of
    _POS_LEAD's specific verbs (this one opens on "Camera", a noun) got a mechanical "no "
    jammed in front of a whole sentence — "no Camera must stay still with Zenny", which
    doesn't parse as English and inverts the actual instruction. A bare, unpunctuated PHRASE
    ("extra characters", "on-screen text") still needs the synthetic "no " to read as a
    constraint at all — the fix only exempts a genuine SENTENCE (its own terminal
    punctuation, or an internal semicolon joining more than one clause), which always ships
    exactly as authored, its own polarity intact, never touched."""
    raw = str(item).strip()
    if re.search(r"[.!?]$", raw) or ";" in raw:
        return raw.rstrip(".")
    s = raw.rstrip(".")
    return s if (_NEG_LEAD.match(s) or _POS_LEAD.match(s)) else "no " + s


def hard_constraints(shot, characters_cfg):
    """The 'Hard constraints:' line + full provenance (Julian's correction, 2026-07-16, points
    1/2/4). Authored constraints (the shot's own prohibited list + its physicalStaging
    prohibitions) ship VERBATIM — negation never stripped, never dropped, never capped. Machine
    items dedup by canonical ID (SUBSUMES), conditionals cap at CONDITIONAL_CAP with the
    overflow DISCLOSED, the universal five always ship. Order: authored, universal, conditional."""
    authored = list(dict.fromkeys(               # exact-duplicate guard only — never fuzzy
        (list(shot.physicalStaging.prohibitedStaging) if shot.physicalStaging else [])
        + list(shot.prohibited)))
    universal_ids = {cid for cid, _ in UNIVERSAL_CONSTRAINTS}
    conditional = _conditional_constraints(shot, characters_cfg)
    live_ids = universal_ids | {cid for cid, _ in conditional}
    subsumed = {cid for cid, _ in conditional
                if any(cid in SUBSUMES.get(winner, set()) for winner in live_ids if winner != cid)}
    conditional = [(cid, t) for cid, t in conditional if cid not in subsumed]
    capped_out = conditional[CONDITIONAL_CAP:]
    conditional = conditional[:CONDITIONAL_CAP]
    items = ([_explicit_constraint(a) for a in authored]
             + [t for _, t in UNIVERSAL_CONSTRAINTS]
             + [t for _, t in conditional])
    line = "Hard constraints: " + "; ".join(items) + "."
    return line, {"authored": authored,
                   "universal": [cid for cid, _ in UNIVERSAL_CONSTRAINTS],
                   "conditional": [cid for cid, _ in conditional],
                   "deduplicated": sorted(subsumed),
                   "capped_out": [cid for cid, _ in capped_out]}


def _reference_role_sentence(shot, scene, characters_cfg):
    """Concise reference-role mapping (Julian's Option D worked example): one short job per
    reference, built from the SAME slot map the fire function uploads against — the text can
    never disagree with the upload order. @图1's job is the anchor sentence's; @Audio1's the
    audio sentence's."""
    set_word = (str(scene.get("sceneName", "")).split() or ["set"])[-1].lower() if scene else "set"
    set_name = f"the {set_word} set" if set_word != "set" else "the set"
    parts = []
    for tag, who in reference_slots(shot, characters_cfg).items():
        if tag in ("@图1", "@Audio1"):
            continue
        parts.append(f"{tag} only for {set_name}" if who == "scene plate"
                     else f"{tag} only for {who}")
    if len(parts) > 1:
        return "Use " + ", ".join(parts[:-1]) + " and " + parts[-1] + "."
    return f"Use {parts[0]}." if parts else ""


def _lip_sync_sentence(shot, characters_cfg):
    """Audio and mouth assignment, derived mechanically from the typed dialogue lines — never a
    free-form splice. The exact words live only in the audio."""
    if not shot.dialogueLines:
        return ""
    speakers, seen = [], set()
    for ln in shot.dialogueLines:
        name = _canon_speaker(ln.speaker, characters_cfg)
        if _norm(name) not in seen:
            seen.add(_norm(name))
            speakers.append(name)
    silent = [c for c in shot.charactersInFrame if _norm(c) not in seen]
    s = f"Use @Audio1 as the only voice. Lip-sync {' and '.join(speakers)}"
    if len(silent) == 1:
        s += f"; {silent[0]}'s mouth remains closed"
    elif silent:
        s += f"; {' and '.join(silent)} keep their mouths closed"
    return s + "."


def _strip_redundant_audio_sentence(text):
    """2026-07-20 (Julian, real S1.SH1 footage: "no movement... no fast paced"): found while
    diagnosing — the design LLM sometimes restates the audio/lip-sync assignment INSIDE
    performanceAssignment/visualPayoff's own free prose ("Lip-sync the approved @Audio1
    performance exactly; no additional speech."), even though _lip_sync_sentence already
    generates this mechanically and authoritatively from dialogueLines every time. The result
    was the SAME instruction shipping twice in one compiled prompt — real, wasted budget under
    this module's own tight 210-word hard ceiling, crowding out room for the actual physical
    action a bee-chase gag needs to read as fast and committed. Drops any WHOLE sentence
    (split on '. ') that mentions lip-sync/lip syncing — a defense-in-depth mechanical guard;
    the matching Law 9 addendum in _design_mind() is the permanent fix at the source."""
    if not text or "lip" not in text.lower() or "sync" not in text.lower():
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    kept = [s for s in sentences if "lip" not in s.lower() or "sync" not in s.lower()]
    return " ".join(kept).strip()


_DIALOGUE_MODES = {"DIALOGUE_PERFORMANCE", "EMOTIONAL_ACTING"}
_KINETIC_MODES = {"KINETIC_ACTION", "PHYSICAL_COMEDY"}


def _modes_dialogue_only(shot):
    """True when the shot's Director-selected performance modes are purely dialogue/
    emotional acting — the register where physics-chain and fast-motion vocabulary is
    COMPETING language to remove (Anti-Guardrail Principle rule 3), not direction.
    False when modes are absent (unmigrated shots keep today's exact behaviour) or when
    any kinetic mode is present (a hybrid keeps its physics language)."""
    modes = set(getattr(shot, "performanceModes", None) or [])
    return bool(modes) and modes <= _DIALOGUE_MODES


def _quality_line(shot):
    """The closing craft line, mode-scoped (Anti-Guardrail rule 3 — remove competing
    language): 'natural motion blur on fast movement' is real direction for a kinetic
    shot and competing noise for a near-still dialogue/emotional shot, where it quietly
    argues for the camera and body energy the register is trying to avoid."""
    if _modes_dialogue_only(shot):
        return ("Craft: richly detailed 3D textures, coherent physics throughout, "
                "feature-film-level polish and stability.")
    return QUALITY_LINE


def _render_critical(shot):
    """The ≤3 genuinely render-critical protections that reach Seedance (Julian's Option D
    criteria: failure invalidates THIS shot; not already carried by keyframe/references/action;
    visually expressible). Derived deterministically from the typed contract: the gag's
    visibility guarantee and the continuity marks that must stay visible. Everything else stays
    INTERNAL — preserved, enforced by validation and review, never repeated at the provider."""
    out = []
    if shot.physicalStaging and shot.physicalStaging.staysVisible:
        sv = shot.physicalStaging.staysVisible.strip().rstrip(".")
        # authored either as a noun phrase ("Fuzzby's whole silhouette above the petals") — needs
        # "Keep" — or as a full sentence ("Fuzzby begins outside the flower; ...") — ships verbatim
        if re.search(r"\b(is|are|begins?|stays?|remains?|keeps?|snaps?|holds?)\b",
                      " ".join(sv.split()[:4])):
            out.append(sv + ".")
        else:
            out.append("Keep " + sv + ".")
    marks = list(dict.fromkeys(
        [m for cs in (shot.continuityIn.characters if shot.continuityIn else [])
         for m in cs.visibleMarks]
        + [m for cs in shot.continuityOut.characters for m in cs.visibleMarks]))
    if marks:
        out.append("Keep " + ", ".join(marks) + " visible.")
    return out[:2]   # + the standing identity/scale/sides line = never more than three


def compile_shot_contract(shot, scene, characters_cfg, siblings=None):
    """THE GOLD SOURCE BRIEF (Julian's Gold Build ruling, 2026-07-24 — "we are going to be
    brave... build it out properly... ensure all the old code is taken out and that only
    the new way is being created and presented to the API"): this function's OLD job —
    composing the lean Seedance prose brief that used to feed the fire path — is RETIRED.
    The prompt that fires is now WRITTEN, never compiled: the Animation gate's register
    writer (cb_departments.prepare_animation, armed verbatim with PROMPT_CRAFT_STANDARD.md
    + PROMPT_CRAFT_SKILL.md — the AnyFilm-derived house curriculum) authors the full
    formula cinematic prompt. What THIS function emits is the SOURCE MATERIAL that writer
    works from: every storyboard-approved fact, labelled plainly, nothing pre-written — so
    the magic lives in the prompting (Julian, same day: "the magic is in the prompting,
    that has to be that way") and the FACTS live here, storyboard-faithful. This text is
    never fireable: cb_render's formula-structure gate refuses anything shaped like it.
    Signature and return contract unchanged (text, word_count, reference_slots) so every
    consumer — compile_scene_package, repair_package, cb_handover._compile_one,
    cb_render._canonical_compiled_brief — keeps working untouched."""
    shot = as_shot(shot)   # boundary normalisation (dicts OR typed)
    lines = ["SOURCE MATERIAL — storyboard-approved facts for the cinematic card. This is "
             "NOT a prompt and must never fire; the register card is written from it at "
             "the Animation gate."]

    def add(label, val):
        v = ("" if val is None else str(val)).strip()
        if v:
            lines.append(f"{label}: {v}")

    add("SET & LIGHT LAW (light is written in THIS vocabulary — concrete sky/sun/shadow "
        "states, never time-of-day words)", _style_line(scene, shot))
    add("REFERENCES", _reference_role_sentence(shot, scene, characters_cfg))
    add("FELT INTENT (the one feeling every camera, light and performance choice serves)",
        shot.feltIntent)
    add("OPENING ANCHOR", OPENER_ANCHOR if shot.sourceType == "opener" else RELAY_ANCHOR)
    add("CAMERA (storyboard-approved)", shot.camera)
    add("OPENING POSE / FIRST FRAME", shot.openingPose)
    if shot.transitionType == "CONTINUOUS":
        add("TRANSITION", "continuing directly from the previous shot's own motion, no cut")
    elif shot.transitionType == "PLANNED_CUT" and shot.cutInMotivation:
        add("TRANSITION", f"planned cut, motivated by {shot.cutInMotivation.strip()}")
    add("PERFORMANCE (approved physical performance)",
        _strip_redundant_audio_sentence(shot.performanceAssignment))
    if shot.cutPace == "single_continuous_take":
        add("CUT PACE", "single continuous take — the card is one Shot 1 only, no internal cuts")
    elif shot.composedOf:
        # THE REFERENCE FORM (2026-07-25): this generation renders other Shot Cards in
        # order. Each segment is compiled FROM THE MEMBER CARD'S OWN authored fields —
        # nothing here is re-typed, so a member's camera, first frame, performance and
        # ending remain the single authority for that segment.
        members, _prov = resolve_clip_members(shot, siblings)
        lines.append("MEMBER SHOT CARDS (each becomes its own 'Shot N:' segment of this "
                     "clip, in this order — compiled from that card, not restated here):")
        for i, m in enumerate(members, 1):
            lines.append(f"  {i}. [{m.shotId}] camera: {str(m.camera).strip()}")
            lines.append(f"      first frame: {str(m.openingPose).strip()}")
            lines.append(f"      performance: "
                         f"{_strip_redundant_audio_sentence(m.performanceAssignment).strip()}")
            if m.visualPayoff:
                lines.append(f"      closes on: "
                             f"{_strip_redundant_audio_sentence(m.visualPayoff).strip()}")
            if m.endingBehaviour:
                lines.append(f"      ends by: {str(m.endingBehaviour).strip()}")
    elif shot.internalCuts:
        lines.append("INTERNAL CUTS (each becomes its own 'Shot N:' segment of the card, "
                     "in this order):")
        for i, cut in enumerate(shot.internalCuts, 1):
            lines.append(f"  {i}. {str(cut).strip()}")
    add("TEMPO DESIGN (the pace-contrast map — written INTO the motion of each segment, "
        "never as a separate metadata line)", shot.tempoDesign)
    if shot.physicalStaging:
        ps = shot.physicalStaging
        add("GAG PHYSICS — stays visible", getattr(ps, "staysVisible", None))
        add("GAG PHYSICS — contact and weight", getattr(ps, "contactAndWeight", None))
        add("GAG PHYSICS — payoff shape", getattr(ps, "payoffShape", None))
        add("GAG PHYSICS — prohibited staging", getattr(ps, "prohibitedStaging", None))
    add("VISUAL PAYOFF (the closing image)",
        _strip_redundant_audio_sentence(shot.visualPayoff))
    if shot.continuityIn is not None:
        try:
            add("CONTINUITY IN", _continuity_line(shot.continuityIn))
        except Exception:
            add("CONTINUITY IN", shot.continuityIn)
    if shot.continuityOut is not None:
        try:
            add("CONTINUITY OUT", _continuity_line(shot.continuityOut))
        except Exception:
            add("CONTINUITY OUT", shot.continuityOut)
    dl = shot.dialogueLines or []
    if dl:
        lines.append("DIALOGUE — THE AUDIO LAW (THE SH1 KEEPER STANDARD, Julian's ruling "
                     "2026-07-25, superseding the earlier inline-verbatim formula): the "
                     "spoken WORDS below are context for staging and timing ONLY and must "
                     "NEVER be written into the card. @Audio1 is the sole source of "
                     "dialogue, wording, voice, performance and timing; the card names who "
                     "speaks, who stays silent, and times the performance by the audio's "
                     "own spoken sections. Nothing invented beyond this list:")
        for d in dl:
            spk = str(getattr(d, "speaker", "") or "").upper()
            txt = str(getattr(d, "exactText", "") or "")
            dlv = str(getattr(d, "delivery", "") or "as written")
            s0 = getattr(d, "startSec", None)
            s1 = getattr(d, "endSec", None)
            lines.append(f"  {spk}: {txt}  (delivery: {dlv}; ~{s0}-{s1}s)")
    hc_line, _ = hard_constraints(shot, characters_cfg)
    add("HARD CONSTRAINTS (honoured in the writing itself — nothing here is mechanically "
        "re-appended)", hc_line)
    if shot.prohibited:
        add("PROHIBITED (authored)", "; ".join(str(p) for p in shot.prohibited))
    lines.append("DURATION: carried by the API parameter — NEVER write any duration into "
                 "the card; the only sanctioned time phrase is the closing hold's own "
                 "'about 2 seconds of silence'.")
    text = "\n".join(lines)
    return text, len(text.split()), reference_slots(shot, characters_cfg)


class PlanIncomplete(ValueError):
    """A v2 shot that fails the plan contract. Never raised for a legacy package."""


def _legacy_first_frame_plan(shot):
    """THE ONE COMPATIBILITY ADAPTER (v1 → FirstFramePlan). Julian's directive item 1:
    "create ONE explicit compatibility adapter that maps the old fields into the new
    plans. Do not scatter fallback precedence across multiple compilers." This is that
    one place; no compiler may implement its own fallback."""
    return FirstFramePlan(
        storyInstant=shot.openingPose,
        shotSize=(shot.camera.split(",")[0].strip() or "as directed"),
        cameraPosition=shot.camera,
        characterPositions=(shot.continuityIn.cameraSide if shot.continuityIn
                            else "as established by the opening frame"),
        pose=shot.openingPose,
        gaze="as the opening pose implies",           # v1 never recorded gaze separately
        expression="as the opening pose implies",     # v1 never recorded expression separately
        actionPhase="anticipation",                   # v1's openingPose IS the anticipation instant
        lightState=(shot.continuityIn.lighting if shot.continuityIn else None),
        incomingContinuity=(shot.cutInMotivation or None),
        referenceRoles=None,
    )


def _legacy_motion_plan(shot):
    """THE ONE COMPATIBILITY ADAPTER (v1 → MotionPlan). Same single-location rule."""
    actions = list(shot.internalCuts) if shot.internalCuts else [shot.performanceAssignment]
    return MotionPlan(
        entryState=shot.openingPose,
        cameraBehaviour=shot.camera,
        orderedActions=actions,
        performanceProgression=shot.performanceAssignment,
        tempoChanges=shot.tempoDesign,
        dialogueSections=shot.dialogueBinding,
        payoff=shot.visualPayoff,
        exitState=(shot.continuityOut.cameraSide if shot.continuityOut else shot.visualPayoff),
        nextShotHandoff=None,
    )


def resolve_plans(shot):
    """THE PRECEDENCE RULE, in exactly one function (directive item 1):

        approved typed plan  →  legacy adapter for an old package  →  REFUSAL if a
        declared-v2 package is incomplete.

    Returns (FirstFramePlan, MotionPlan, provenance) where provenance is "approved" or
    "legacy_adapted", so every consumer can report WHICH authority it used. The same
    creative decision therefore never exists in two conflicting authoritative places:
    when an approved plan exists it wins outright and the legacy prose is not consulted."""
    shot = as_shot(shot)
    is_v2 = shot.packageVersion == "v2"
    missing = []
    if is_v2:
        if not shot.firstFramePlan:  missing.append("firstFramePlan")
        if not shot.motionPlan:      missing.append("motionPlan")
        if not shot.endingBehaviour: missing.append("endingBehaviour")
        if not shot.dramaticIntent:  missing.append("dramaticIntent")
        if missing:
            raise PlanIncomplete(
                f"REFUSED — {shot.shotId} declares packageVersion='v2' but is missing "
                f"{', '.join(missing)}. A v2 shot must carry its approved plans and an "
                f"explicit ending decision; the legacy adapter is NOT applied to a v2 "
                f"package (that would silently invent direction nobody approved).")
        return shot.firstFramePlan, shot.motionPlan, "approved"
    # legacy package: an approved plan still wins per-field if one happens to be present
    ffp = shot.firstFramePlan or _legacy_first_frame_plan(shot)
    mp = shot.motionPlan or _legacy_motion_plan(shot)
    prov = "approved" if (shot.firstFramePlan and shot.motionPlan) else "legacy_adapted"
    return ffp, mp, prov


def ending_requires_hold(shot):
    """Does this shot's own approved ending need the clean-frame harvest window?
    Legacy (no decision) keeps the historical hold requirement — nothing loosens by
    accident. Only reaction_hold / living_hold require it.

    Reads the ONE field directly rather than validating an entire Shot: a caller may
    legitimately hold a partial record (the render gate does), and a validation error
    on some unrelated field must never be able to flip a hold decision. An unrecognised
    value is treated as hold-required — unknown input is never a silent bypass."""
    if shot is None:
        return True
    if isinstance(shot, Shot):
        eb = shot.endingBehaviour
    elif isinstance(shot, dict):
        eb = shot.get("endingBehaviour")
    else:
        eb = getattr(shot, "endingBehaviour", None)
    if eb is None:
        return True                      # legacy default: unchanged behaviour
    return eb in HOLD_REQUIRING_ENDINGS


def _continuity_line(cs):
    """DE-DUPLICATED continuity rendering (Julian's directive item 9, 2026-07-25 —
    "inspect it for duplicated or conflicting representations of the same direction...
    The final writer should receive complete production truth ONCE, with clear authority,
    rather than several slightly different versions").

    MEASURED on the real S1.SH2 record: every per-character field (screenZone / facing /
    pose / expression) held the IDENTICAL string, and lighting == cameraSide — ~13% of the
    compiled brief was literal repetition of the same decision. Dumping the raw JSON told
    the writer the same thing up to four times per character, which dilutes authority
    rather than adding truth.

    Emits each distinct value ONCE, naming which aspects it covers. Nothing is dropped:
    when the values genuinely differ they are all still stated, separately."""
    if cs is None:
        return None
    get = cs.get if isinstance(cs, dict) else (lambda k, d=None: getattr(cs, k, d))
    parts = []
    light, side = get("lighting"), get("cameraSide")
    if light and side and light.strip() == side.strip():
        parts.append(f"world (lighting + camera side): {light.strip()}")
    else:
        if light: parts.append(f"lighting: {light.strip()}")
        if side:  parts.append(f"camera side: {side.strip()}")
    for ch in (get("characters") or []):
        cg = ch.get if isinstance(ch, dict) else (lambda k, d=None: getattr(ch, k, d))
        name = cg("character") or "character"
        fields = {k: (cg(k) or "").strip() for k in ("screenZone", "facing", "pose", "expression")}
        distinct = {}
        for k, v in fields.items():
            if v: distinct.setdefault(v, []).append(k)
        for value, aspects in distinct.items():
            parts.append(f"{name} ({'/'.join(aspects)}): {value}")
        for extra in ("visibleMarks", "heldProps"):
            v = cg(extra)
            if v: parts.append(f"{name} {extra}: {', '.join(str(x) for x in v)}")
    return " | ".join(parts) if parts else None


def as_shot(shot):
    """THE PACKAGE BOUNDARY NORMALISER (Julian's directive, 2026-07-25 — "Fix the current
    fragility where canonical package dictionaries can reach a compiler expecting typed
    Pydantic objects. Normalise data into the canonical typed models at the package
    boundary").

    The canonical package on disk holds plain dicts; the compilers were written against
    typed Shot objects and reach for attributes (shot.openingPose). Calling a compiler
    with real package data therefore raised AttributeError — confirmed live, and only
    invisible in production because prepare_cinematography happens to pass typed objects.

    Accepts either shape and always returns a typed Shot. Unknown/legacy keys are dropped
    rather than raising, so a package authored before any schema addition still normalises
    cleanly (backward compatibility is a hard requirement of the directive)."""
    if isinstance(shot, Shot):
        return shot
    if not isinstance(shot, dict):
        raise TypeError(f"as_shot: expected Shot or dict, got {type(shot).__name__}")
    known = {k: v for k, v in shot.items() if k in Shot.model_fields}
    return Shot.model_validate(known)


# ── THE FOUR-LEVEL MODEL (Julian's directive, 2026-07-25) ──────────────────────────
# 1 DRAMATIC BEAT      cb_creative.Beat / Shot.beatCode — what changes in the story.
# 2 CINEMATIC SHOT     a Shot Card (this module's Shot) — one camera/performance idea.
# 3 GENERATION CLIP    what ONE provider call renders. Addressed by the shotId that
#                      fire_shot() is given; its members are resolved below.
# 4 EDITORIAL OUTPUT   cb_post assembles rendered clips into picture/conformed/masters.
#
# Levels 1, 3 and 4 were already separate. Levels 2 and 3 were CONFLATED: one Shot was
# always exactly one generation, so several ordered camera shots inside one generation
# could only be expressed as internalCuts — prose, which redefines those camera shots
# instead of referencing them. composedOf is the reference form; this resolver is the
# one place the distinction is read. A clip with no composedOf resolves to itself,
# byte-identically to the behaviour every existing package already has.

class ClipMemberError(ValueError):
    """Raised when a clip's composedOf cannot be resolved to real Shot Cards."""


def resolve_clip_members(shot, siblings=None):
    """Return (members, provenance) for a generation clip.

    members    — ordered list of typed Shot Cards this ONE generation renders.
    provenance — "self" (the 1:1 default) or "composed" (references resolved).

    siblings may be the package dict, its shots list, or None. Passing None with a
    composedOf present is an error rather than a silent fallback: quietly rendering
    only the parent would drop authored camera shots without a word."""
    shot = as_shot(shot)
    refs = list(shot.composedOf or [])
    if not refs:
        return [shot], "self"
    if siblings is None:
        raise ClipMemberError(
            f"{shot.shotId}: composedOf names {len(refs)} member card(s) but no sibling "
            f"shots were supplied to resolve them against")
    if isinstance(siblings, dict):
        siblings = siblings.get("shots") or []
    by_id = {}
    for s in siblings:
        s = as_shot(s)
        by_id[s.shotId] = s
    members = []
    for ref in refs:
        if ref == shot.shotId:
            raise ClipMemberError(f"{shot.shotId}: composedOf may not reference itself")
        if ref not in by_id:
            raise ClipMemberError(
                f"{shot.shotId}: composedOf references {ref!r}, which is not a shot in "
                f"this scene")
        member = by_id[ref]
        if member.composedOf:
            raise ClipMemberError(
                f"{shot.shotId}: member {ref} itself declares composedOf — a clip's "
                f"members are camera shots, never nested clips")
        members.append(member)
    return members, "composed"


def clip_owner_of(shot_id, siblings):
    """The shotId of the generation clip that renders this card, or None if it is its
    own clip. A member card is NOT independently fireable — firing it would render the
    same camera shot twice, once alone and once inside its owner."""
    if isinstance(siblings, dict):
        siblings = siblings.get("shots") or []

    # Read the TWO fields directly rather than validating a whole Shot. Same lesson as
    # ending_requires_hold's own 2026-07-25 correction: normalising an entire record to
    # read one field turns any unrelated schema gap into a raised error inside a guard —
    # and a guard that raises on a partial record refuses fires it has no business
    # refusing. Membership is a claim made BY the owner, so a malformed sibling can only
    # ever fail to claim; it can never wrongly capture this shot.
    def _get(s, key):
        return s.get(key) if isinstance(s, dict) else getattr(s, key, None)

    for s in siblings:
        sid = _get(s, "shotId")
        if sid and sid != shot_id and shot_id in (_get(s, "composedOf") or []):
            return sid
    return None


def compile_keyframe_prompt(shot, scene, characters_cfg):
    """THE GOLD SOURCE BRIEF — STILLS (2026-07-24, same ruling and same treatment as
    compile_shot_contract the same day; closed after Julian's front-to-back audit
    directive caught the keyframe path still carrying the old format): the old fireable
    keyframe-prompt composition is RETIRED. This now emits labelled SOURCE MATERIAL for
    the Cinematography register writer (cb_departments.prepare_cinematography, curriculum
    verbatim + THE LIGHT LAW), which WRITES the opening-frame prompt. Never fireable
    itself. Signature/return unchanged for every consumer."""
    shot = as_shot(shot)   # boundary normalisation (dicts OR typed)
    lines = ["SOURCE MATERIAL — storyboard-approved facts for the OPENING-FRAME card. This "
             "is NOT a prompt and must never fire; the register still-card is written from "
             "it at the Cinematography gate."]

    def add(label, val):
        v = ("" if val is None else str(val)).strip()
        if v:
            lines.append(f"{label}: {v}")

    add("SET & LIGHT LAW (light written ONLY as concrete sky/sun/shadow states — never "
        "time-of-day words)", _style_line(scene, shot))
    add("THIS IS THE LITERAL OPENING FRAME — one frozen instant, no motion-over-time",
        "yes")
    add("OPENING POSE / STORY INSTANT", shot.openingPose)
    add("CAMERA (storyboard-approved)", shot.camera)
    add("CHARACTERS IN FRAME (identity from references only; scale relationship explicit)",
        ", ".join(shot.charactersInFrame or []))
    if shot.continuityIn is not None:
        try:
            add("CONTINUITY IN", _continuity_line(shot.continuityIn))
        except Exception:
            add("CONTINUITY IN", shot.continuityIn)
    add("FELT INTENT (the frame's emotional read)", shot.feltIntent)
    hc_line, _ = hard_constraints(shot, characters_cfg)
    add("HARD CONSTRAINTS (honoured in the writing)", hc_line)
    lines.append("REFERENCE ROLES: " + _reference_role_sentence(shot, scene, characters_cfg))
    text = "\n".join(lines)
    return text, len(text.split()), reference_slots(shot, characters_cfg, for_keyframe=True)


def compile_audio_brief(shot):
    """The ElevenLabs job sheet for one shot — the ONE artifact where the exact words belong.
    Feeds the voice pass (Gate 4); never any render prompt."""
    if not shot.dialogueLines:
        return None
    lines = [f"{ln.speaker}: \"{ln.exactText}\" — {ln.delivery}. "
             f"Target {ln.startSec:.1f}-{ln.endSec:.1f}s."
             for ln in shot.dialogueLines]
    return "\n".join([f"SHOT {shot.shotId} — voice-only performance for @Audio1."] + lines + [
        "Preserve the exact words. No narration, ad-libs, sound effects or music in the voice track."])


def _ledger_entry(shot):
    return {"shotId": shot.shotId, "beatCode": shot.beatCode, "status": "designed",
            "sourceType": shot.sourceType, "sourceShotId": shot.sourceShotId,
            "cutInMotivation": shot.cutInMotivation,
            "continuityOut": shot.continuityOut.model_dump(),
            "approvedTake": None, "harvestFrame": None}


# ─────────────────────────────────────────────────────────────────────────────────────────
# THE PACKAGE
# ─────────────────────────────────────────────────────────────────────────────────────────
def compile_scene_package(scene_num, episode="Ep1", log=print):
    design, report, beats, scene, d, pkg_path = design_scene(episode, scene_num, log=log)
    try:
        characters_cfg = json.load(open(P.CHARS))
    except Exception:
        characters_cfg = {}

    if not report["passed"]:
        errs = [i for i in report["issues"] if i["severity"] == "ERROR"]
        log(f"ENGINE — ⛔ design still carries {len(errs)} validation ERROR(s) after the repair "
            f"pass — package written with validation.passed=false; it must not fire:", flush=True)
        for i in errs:
            log(f"   [{i['code']}] {i['path']}: {i['message']}", flush=True)

    shots_out, total_sec = [], 0.0
    for sh in design.shots:
        prompt, wc, slots = compile_shot_contract(sh, scene, characters_cfg,
                                                   siblings=design.shots)
        rec = sh.model_dump()
        rec["seedancePrompt"] = prompt
        rec["promptWords"] = wc
        rec["referenceSlots"] = slots
        rec["audioBrief"] = compile_audio_brief(sh)
        if sh.sourceType == "opener":
            kf, kwc, kslots = compile_keyframe_prompt(sh, scene, characters_cfg)
            rec["keyframePrompt"], rec["keyframePromptWords"] = kf, kwc
            rec["keyframeReferenceSlots"] = kslots
        shots_out.append(rec)
        total_sec += sh.durationSec

    pkg = {
        "episode": episode, "sceneNumber": str(scene_num), "sceneName": scene.get("name", ""),
        "doctrine": "THE_DEFINITIVE_PIPELINE.md (2026-07-16, hybrid contract)",
        "directorStatement": design.statement.model_dump(),
        "beatCodes": [b.get("beatCode") for b in beats],
        "shots": shots_out,
        "totalSec": round(total_sec, 1),
        "continuityLedger": [_ledger_entry(s) for s in design.shots],
        "validation": report,
        "reviewCriteria": {"canon": "characters and world accurate vs references",
                            "direction": "acting, humour and emotion land",
                            "physics": "weight, contact, follow-through",
                            "continuity": "connects naturally to surrounding shots"},
        "sourceBeatPackage": str(pkg_path.name),
    }
    out_json = canonical_package_path(scene_num, episode)
    json.dump(pkg, open(out_json, "w"), indent=1, ensure_ascii=False)

    # the human review document — the exact words ARE shown here (a human doc, not a render prompt)
    st = design.statement
    md = [f"# {episode} · Scene {scene_num} — Production Package (hybrid)",
          f"_{scene.get('name','')} · {len(design.shots)} shots · ~{round(total_sec)}s · "
          f"validation: {'PASSED' if report['passed'] else 'FAILED'} "
          f"({len(report['issues'])} issue(s)) · doctrine: THE_DEFINITIVE_PIPELINE.md_\n",
          "## Director's statement",
          f"- **Feel:** {st.audienceFeeling}",
          f"- **Whose scene:** {st.whoseScene}",
          f"- **Emotional change:** {st.emotionalChange}",
          f"- **The laugh:** {st.theLaugh}",
          f"- **Visual surprise:** {st.visualSurprise}",
          f"- **Carries forward:** {st.carryForward}\n"]
    if report["issues"]:
        md.append("## Validation report")
        for i in report["issues"]:
            md.append(f"- **{i['severity']}** `{i['code']}` at `{i['path']}` — {i['message']}")
        md.append("")
    for s in shots_out:
        md.append(f"## {s['shotId']}  ·  {s['durationSec']}s  ·  {s['sourceType']}"
                  + (f" ← {s['sourceShotId']}" if s.get('sourceShotId') else "")
                  + (f"  ·  cut in: {s['cutInMotivation']}" if s.get('cutInMotivation') else ""))
        md.append(f"**Purpose:** {s['purpose']}")
        md.append(f"**Opening pose (keyframe truth):** {s['openingPose']}")
        for ln in s.get("dialogueLines") or []:
            md.append(f"**{ln['speaker']}** ({ln['startSec']:.0f}-{ln['endSec']:.0f}s): "
                      f"“{ln['exactText']}” — _{ln['delivery']}_")
        md.append(f"**Payoff:** {s['visualPayoff']}")
        if s.get("physicalStaging"):
            ps = s["physicalStaging"]
            md.append(f"**Gag physics:** stays visible — {ps['staysVisible']}; contact/weight — "
                      f"{ps['contactAndWeight']}; payoff shape — {ps['payoffShape']}")
        md.append(f"**Prompt ({s['promptWords']} words):**\n```\n{s['seedancePrompt']}\n```")
        if s.get("keyframePrompt"):
            md.append(f"**Keyframe prompt ({s['keyframePromptWords']} words):**\n```\n{s['keyframePrompt']}\n```")
        md.append("")
    out_md = HERE.parent / "cb-output" / f"{episode}_scene{scene_num}_production_package.md"
    out_md.write_text("\n".join(md))
    log(f"ENGINE — wrote {out_json.name} + {out_md.name}: {len(design.shots)} shots, "
        f"~{round(total_sec)}s, prompts {min(s['promptWords'] for s in shots_out)}-"
        f"{max(s['promptWords'] for s in shots_out)} words, validation "
        f"{'PASSED' if report['passed'] else 'FAILED'}", flush=True)
    return pkg


def repair_package(scene_num, episode="Ep1", log=print):
    """Run the observable-direction repair loop against an EXISTING production package (Julian's
    directive, 2026-07-16, point 7): repairs every ABSTRACT_DIRECTION rejection field-by-field,
    preserves each original as creativeIntent planning metadata (never compiled), records the
    full repair log, refreshes every stored seedancePrompt (the fire path ships the STORED
    prompt), revalidates deterministically and bumps the package revision. Zero media spend."""
    pkg_file = canonical_package_path(scene_num, episode)
    pkg = json.loads(pkg_file.read_text())
    d, _ = _load_pkg(episode)
    beats = _scene_beats(d, scene_num)
    try:
        characters_cfg = json.load(open(P.CHARS))
    except Exception:
        characters_cfg = {}
    fields = set(Shot.model_fields)
    shots = [Shot(**{k: v for k, v in rec.items() if k in fields}) for rec in pkg["shots"]]
    design = SceneShotList(statement=DirectorStatement(**pkg["directorStatement"]), shots=shots)

    repair_log, escalations, final = auto_repair_abstract_directions(
        design, beats, characters_cfg, log=log)

    by_id = {s.shotId: s for s in design.shots}
    for rec in pkg["shots"]:
        sh = by_id[rec["shotId"]]
        for e in repair_log:
            if e["shotId"] == rec["shotId"] and "PASSED" in e["validationResult"]:
                # planning metadata: the FIRST original is the creative intent — a later repair
                # pass over an intermediate text must never overwrite the true source
                rec.setdefault("creativeIntent", {}).setdefault(e["field"], e["original"])
                rec[e["field"]] = getattr(sh, e["field"])
        # refresh the STORED prompt — the fire path ships this, never a fresh compile. Word
        # length can no longer block this (2026-07-21, the hard ceiling was removed); the
        # only remaining failure mode is a genuine compile guard (e.g. a Law 6 leak) —
        # reported, never a crashed run.
        try:
            prompt, wc, slots = compile_shot_contract(sh, pkg.get("scene", {}),
                                                     characters_cfg,
                                                     siblings=pkg.get("shots"))
            rec["seedancePrompt"], rec["promptWords"], rec["referenceSlots"] = prompt, wc, slots
            rec.pop("promptStale", None)
            # THE INTERNAL CONTRACT LINE (Option D): the full negation-safe constraints record,
            # kept in the package for validation/review — deliberately NOT in the provider brief.
            rec["internalConstraints"] = hard_constraints(sh, characters_cfg)[0]
        except (ValueError, AssertionError) as e:
            rec["promptStale"] = str(e)
            log(f"OVERBUDGET — {rec['shotId']}: stored prompt left stale and fire-blocked "
                f"via validation ({e})", flush=True)
    pkg["repairLog"] = pkg.get("repairLog", []) + repair_log
    errs = [i for i in final["issues"] if i["severity"] == "ERROR"]
    pkg["validation"] = {"passed": final["passed"], "errors": len(errs),
                          "warnings": len([i for i in final["issues"]
                                            if i["severity"] == "WARNING"]),
                          "issues": final["issues"], "validatedAt": "2026-07-16",
                          "revision": int(pkg.get("revision", 1)) + 1}
    pkg["revision"] = int(pkg.get("revision", 1)) + 1
    pkg_file.write_text(json.dumps(pkg, indent=1, ensure_ascii=False))
    log(f"REPAIR — {len([e for e in repair_log if 'PASSED' in e['validationResult']])} field(s) "
        f"repaired, {len(escalations)} escalated; validation passed={final['passed']}; "
        f"revision {pkg['revision']}", flush=True)
    for esc in escalations:
        log(f"ESCALATION — {esc['shotId']}.{esc['field']}: {esc['reason']}", flush=True)
    return repair_log, escalations, final


if __name__ == "__main__":
    os.chdir(HERE)
    if len(sys.argv) > 1 and sys.argv[1] == "repair":
        repair_package(sys.argv[2] if len(sys.argv) > 2 else "1",
                       sys.argv[3] if len(sys.argv) > 3 else "Ep1")
    else:
        scene = sys.argv[1] if len(sys.argv) > 1 else "1"
        ep = sys.argv[2] if len(sys.argv) > 2 else "Ep1"
        compile_scene_package(scene, ep)
