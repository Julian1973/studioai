#!/usr/bin/env python3
"""cb_engine.py — THE DIRECTOR ENGINE, HYBRID v2 (Julian's rulings, 2026-07-16 —
THE_DEFINITIVE_PIPELINE.md at repo root is the governing document; read it first).

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

MAX_SHOT_PROMPT_WORDS = 210   # hard assertion on every compiled shot contract. Raised 170->210 on
                              # 2026-07-16: Julian's dictated @图1 anchor contracts (OPENER_ANCHOR /
                              # RELAY_ANCHOR below) are fixed continuity scaffolding of ~34/~62 words
                              # per shot, on top of the platform-length ACTION content — which stays
                              # capped by the mind's own 25-50-word assignment discipline. The cap
                              # still guards against action-content bloat; it is not licence for it.
MAX_KEYFRAME_PROMPT_WORDS = 160
MIN_SHOT_SEC, MAX_SHOT_SEC = 4, 8


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
    dialogueBinding: Optional[str] = None         # the prompt-facing sentence: WHO speaks + the emotional
    #                                               read — NEVER the words (the audio carries them)
    dialogueLines: List[DialogueLine]             # the typed voice data (empty when nobody speaks)
    visualPayoff: str = Field(min_length=1)       # the exact image this shot must end having delivered
    physicalStaging: Optional[PhysicalStaging] = None  # required somewhere in every BIG-comedy beat
    prohibited: List[str]                         # 0-3 shot-specific failure modes ONLY — never a wall
    charactersInFrame: List[str]                  # who is visible (reference bindings derive from this)
    continuityIn: ContinuityState                 # the world as this shot opens
    continuityOut: ContinuityState                # the world as this shot ends — the next relay's truth


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
        "sourceShotId=null; every later shot is 'relay' (sourceShotId = the earlier shot whose final "
        "frame it continues from, usually the previous one) when the action flows on directly, or "
        "'opener' (sourceShotId=null) when it is a designed editorial cut to genuinely new coverage. "
        "Every shot: ONE performance assignment, an anticipation openingPose, an exact visualPayoff, "
        "typed continuityIn/continuityOut (zone, facing, pose, expression, marks, props for every "
        "character in frame), dialogueLines copied VERBATIM with timing, at most 3 prohibited items, "
        "and physicalStaging on the gag-carrying shot of each BIG-comedy beat."
    )


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
        "openingContinuity": shot.continuityIn.model_dump(),
        "closingContinuity": shot.continuityOut.model_dump(),
        "characterBehaviour": {c.character: {"pose": c.pose, "expression": c.expression,
                                              "screenZone": c.screenZone}
                                for c in shot.continuityIn.characters},
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


# The design mind's own per-field word discipline, enforced deterministically on the two
# render-facing prose fields (the repair loop translates a violation, never truncates it).
FIELD_WORD_BUDGETS = {"performanceAssignment": 50, "visualPayoff": 15}

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

        # continuity states must cover everyone in frame
        for state_name, state in (("continuityIn", sh.continuityIn),
                                    ("continuityOut", sh.continuityOut)):
            covered = {_norm(cs.character) for cs in state.characters}
            for c in sh.charactersInFrame:
                if _norm(c) not in covered:
                    add("ERROR", "CONTINUITY_CAST_INCOMPLETE", f"{path}.{state_name}",
                        f"{c} is in frame but missing from {state_name}")

        # relay join: marks and props must carry across the cut unchanged
        if sh.sourceType == "relay" and sh.sourceShotId in shots_by_id and sh.sourceShotId != sh.shotId:
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

    # THE VERBATIM LOCK: every locked dialogue line assigned exactly once, word for word
    expected = _expected_lines(beats)
    exp_norm = [(_norm(_canon_speaker(s, characters_cfg)), _norm(t)) for s, t in expected]
    got_norm = [(_norm(_canon_speaker(s, characters_cfg)), t) for s, t, _ in seen_norm_lines]
    for (es, et), (raw_s, raw_t) in zip(exp_norm, expected):
        n = sum(1 for gs, gt in got_norm if gs == es and gt == et)
        if n == 0:
            add("ERROR", "DIALOGUE_LINE_DROPPED", "shots",
                f"locked line not assigned to any shot — {raw_s}: \"{raw_t}\"")
        elif n > 1:
            add("ERROR", "DIALOGUE_LINE_DUPLICATED", "shots",
                f"locked line assigned to {n} shots — {raw_s}: \"{raw_t}\"")
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
            budget = FIELD_WORD_BUDGETS[field_name]
            n = len((field_text or "").split())
            if n > budget:
                add("ERROR", "FIELD_OVERBUDGET", f"{path}.{field_name}",
                    f"{n} words against the field's own {budget}-word discipline — "
                    f"lean direction, never micro-choreography")

    # COMPILABILITY (Julian's directive, 2026-07-16, point 4's designed outcome): a shot whose
    # contract can no longer fit the word cap — authored constraints are never dropped and
    # direction is never auto-rewritten — FAILS validation here, named, so a stale stored prompt
    # can never fire past it. Compilation is fully deterministic now (no LLM), so this is cheap.
    for i, sh in enumerate(design.shots):
        try:
            compile_shot_contract(sh, {}, characters_cfg)
        except (ValueError, AssertionError) as e:
            add("ERROR", "SHOT_OVERBUDGET" if "cap" in str(e) else "COMPILE_GUARD",
                f"shots[{i}]({sh.shotId})", str(e))

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
def _style_line(scene, shot=None):
    # ONE consistent anchor-matching style rule (Julian, 2026-07-16, point 9 + Option D +
    # the destructive cutover, which removed the last legacy style-scaffolding phrases
    # scaffolding from executable source): a SHOT's style anchor IS its own @图1; a KEYFRAME
    # (shot=None) makes the first frame, so its style anchors to the references it is given.
    # The signed 1.B1.S1 keyframe predates this wording and stands unchanged as a file.
    if shot is None:
        return ("Stylised feature-quality 3D CGI with natural weight. Preserve the exact "
                "character designs, proportions, materials, lighting and environment from "
                "the references.")
    return "Stylised feature-quality 3D CGI matching @图1."


# THE @图1 ANCHORS — Julian's Option D ruling (2026-07-16, superseding his own same-day dictated
# long scaffold): the provider brief carries a CONCISE anchor; the full continuity contract lives
# internally and is enforced by validation/review, never by boilerplate. No anti-hold text is
# compiled — the shot's observable direction determines whether a pose continues. A planned cut
# uses a storyboard-approved NEW keyframe named as the new shot's opening composition (that shot
# is an opener by construction — the same OPENER_ANCHOR applies to it).
OPENER_ANCHOR = "Begin exactly on @图1, the approved opening frame."

RELAY_ANCHOR = ("Begin exactly on @图1, the approved final frame of the previous shot, and "
                "continue the new action immediately.")


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
UNIVERSAL_CONSTRAINTS = [                                        # the lean five — every shot, always
    ("no_character_redesign", "no character redesign"),
    ("no_extra_characters", "no extra characters"),
    ("no_onscreen_text", "no on-screen text"),
    ("no_invented_voices", "no invented voices"),
    ("no_camera_cut", "no camera cut"),
]
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
    negation is added, never stripped, and the authored words are never altered."""
    s = str(item).strip().rstrip(".")
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
        [m for cs in shot.continuityIn.characters for m in cs.visibleMarks]
        + [m for cs in shot.continuityOut.characters for m in cs.visibleMarks]))
    if marks:
        out.append("Keep " + ", ".join(marks) + " visible.")
    return out[:2]   # + the standing identity/scale/sides line = never more than three


def compile_shot_contract(shot, scene, characters_cfg):
    """THE SEEDANCE PERFORMANCE BRIEF (Julian's Option D, 2026-07-16): the provider reads a LEAN
    creative brief — reference roles, the exact opening anchor, the observable action and its
    performance beat, camera, audio/mouth assignment, the closing state, and at most three
    render-critical protections. The FULL production contract (creative intent, authored
    constraints, canon/continuity rules, repair history, provenance, review requirements) lives
    in the package — preserved and enforced by validation and review, never repeated at the
    provider. 'Not sent to Seedance' is not 'dropped from the production contract'.
    Target 90-160 words; 210 is the hard failure ceiling. Duration/AR travel as API params.

    2026-07-17 correction (Julian's audit, source-defect protection lifted for this one
    line only): the closing preservation sentence no longer unconditionally locks 'screen
    sides' on every shot — that was a false universal, since most shots have no approved
    reason to hold a fixed lane. No separate screen-side detector was added; a genuinely
    required lock is expected to reach the shot via shot.prohibited (an authored constraint),
    the one existing door for this. NOTE, flagged rather than silently assumed: under this
    module's own Option D design, shot.prohibited/hard_constraints' authored items feed
    `internalConstraints` in the package (see compile_scene_package) — deliberately NOT
    concatenated into THIS function's own returned prompt string. So today a genuinely
    required screen-side lock does not yet reach the shipped Seedance brief through either
    path; it is visible in the package for review, not in the fired prompt. Whether that
    gap should be closed (and how) is a separate, undecided question — not addressed by
    this fix, which only removes the false default."""
    anchor = OPENER_ANCHOR if shot.sourceType == "opener" else RELAY_ANCHOR
    camera = shot.camera.strip().rstrip(".")
    action = [f"{anchor[:-1]} — {camera[0].lower()}{camera[1:]}.",
              shot.performanceAssignment.strip().rstrip(".") + "."]
    payoff = shot.visualPayoff.strip().rstrip(".").lstrip(". ")
    action.append(payoff[:1].upper() + payoff[1:] + ".")

    closing = [_lip_sync_sentence(shot, characters_cfg),
               "Preserve character identity and relative scale."]
    closing += _render_critical(shot)

    prompt = "\n\n".join([
        f"{_style_line(scene, shot)} {_reference_role_sentence(shot, scene, characters_cfg)}".strip(),
        " ".join(action),
        " ".join(s for s in closing if s),
    ])
    wc = len(prompt.split())
    if wc > MAX_SHOT_PROMPT_WORDS:
        raise ValueError(
            f"shot {shot.shotId} brief is {wc} words (hard ceiling {MAX_SHOT_PROMPT_WORDS}, "
            f"target 90-160) — tighten {shot.shotId}'s source direction; the internal contract "
            f"is never auto-trimmed.")
    _assert_no_spoken_words(prompt, shot, "Seedance brief")
    return prompt, wc, reference_slots(shot, characters_cfg)


def compile_keyframe_prompt(shot, scene, characters_cfg):
    """The opening-keyframe prompt for an OPENER shot — reference-first (zero appearance
    text), room to breathe (Julian's Gate-2b law), compiled from: the approved opening
    image, continuity in, identity/scale/reference bindings, and environment/lighting/
    opening composition.

    2026-07-17 correction (Julian's audit, source-defect protection lifted for this one
    function only): this used to hardcode a universal 'the anticipation instant before the
    action, never the payoff' framing and ban 'the action already happening' as a negative —
    both false universals. THE APPROVED OPENING STATE DECIDES whether movement is already
    underway (e.g. a character already pitched into travel) or the shot opens on deliberate
    stillness (e.g. a character already still, before a quiet line) — this function states
    only what shot.openingPose actually says, never a default posture.

    shot.camera (the whole-shot camera RELATIONSHIP, which can describe movement across the
    entire shot) is deliberately never read here — a single-frame brief has no legitimate use
    for a whole-shot movement description, opener or not. 'Opening composition' instead comes
    from continuityIn's own lighting/cameraSide (which side of the action line the camera
    holds at the opening instant, plus lighting) — the world/light/framing truth for this one
    frame. When a caller's own mapping has (degenerately) duplicated one prose sentence into
    both continuityIn.lighting and continuityIn.cameraSide, it is stated once, not twice."""
    pose, next_slot = _inline_bindings(shot.openingPose.strip().rstrip("."), shot,
                                        characters_cfg, start=1)
    lighting = shot.continuityIn.lighting.strip().rstrip(".")
    camera_side = shot.continuityIn.cameraSide.strip().rstrip(".")
    continuity = lighting if _norm(lighting) == _norm(camera_side) else f"{lighting}; {camera_side}"
    prompt = "\n\n".join([
        _style_line(scene),
        f"The literal OPENING FRAME of the shot, exactly as approved: {pose}.",
        f"Continuity in: {continuity}. Frame a touch wider than the shot size alone implies — "
        f"real headroom and side-room for whatever the shot needs. "
        f"@图{next_slot} scene plate holds the world, palette and light exactly.",
        ("Negative: character redesign, appearance drift from the references, extra "
         "characters, on-screen text."),
    ])
    wc = len(prompt.split())
    assert wc <= MAX_KEYFRAME_PROMPT_WORDS, (
        f"keyframe prompt for {shot.shotId} is {wc} words (cap {MAX_KEYFRAME_PROMPT_WORDS})")
    _assert_no_spoken_words(prompt, shot, "keyframe prompt")
    return prompt, wc, reference_slots(shot, characters_cfg, for_keyframe=True)


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


def _continuity_summary(state):
    chars = "; ".join(
        f"{cs.character} {cs.screenZone}, facing {cs.facing}, {cs.pose}, {cs.expression}"
        + (f", marks [{', '.join(cs.visibleMarks)}]" if cs.visibleMarks else "")
        + (f", props [{', '.join(cs.heldProps)}]" if cs.heldProps else "")
        for cs in state.characters)
    return f"light {state.lighting}; camera side {state.cameraSide}; {chars}"


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
        prompt, wc, slots = compile_shot_contract(sh, scene, characters_cfg)
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
    out_json = HERE.parent / "cb-output" / f"{episode}_scene{scene_num}_production_package.json"
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
    pkg_file = HERE.parent / "cb-output" / f"{episode}_scene{scene_num}_production_package.json"
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
        # refresh the STORED prompt — the fire path ships this, never a fresh compile. An
        # over-budget shot is REPORTED (validation carries SHOT_OVERBUDGET, blocking any fire on
        # the stale stored prompt) — never dropped constraints, never a crashed run.
        try:
            prompt, wc, slots = compile_shot_contract(sh, pkg.get("scene", {}), characters_cfg)
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
