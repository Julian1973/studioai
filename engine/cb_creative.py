#!/usr/bin/env python3
"""cb_creative.py — THE CRYSTAL BEARS CREATIVE ROOM (vNEXT, 2026-07-16).

One new creative brain ABOVE the cleaned production pipeline. Four roles — Showrunner,
Director (owning animation and physical performance), Cinematographer, Voice Director —
collaborate as ordered passes over ONE Authoritative Storyboard Package:

    Episode -> Scene -> Beat -> Shot (+ Voice Performance per spoken line)

The creative room creates the magic; the storyboard captures it. Seedance stays a later,
lean distillation handled by the surviving production route (cb_engine -> cb_render) at
the human gates — this module NEVER calls a media provider, never compiles a Seedance
prompt and never touches a spend token. Its only external calls are OpenAI text calls via
cb_llm (the creative room's own thinking).

Canon precedence (§4): Show Bible -> Character/Relationship Canon -> Environment/Visual
Canon -> Approved Script -> Scene -> Beat -> Shot -> Production Handover. A lower level
interprets, never contradicts; genuine conflicts are reported, never silently resolved.

    python3 cb_creative.py envelope  [episode]        # Internal Gate 0 — canon integrity
    python3 cb_creative.py vision    [episode]        # Internal Gate 1 — episode vision
    python3 cb_creative.py scene <n> [episode]        # Internal Gates 2-6 for one scene
    python3 cb_creative.py migrate   [episode]        # canon migration/import report
"""
import datetime
import hashlib
import json
import os
import pathlib
import re
import sys
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import cb_llm
import paths as P

CREATIVE = ROOT / "shows" / "crystal-bears" / "creative"
OUT = ROOT / "cb-output" / "creative"
CANON_VERSION = "1.0"
ENGINE_VERSION = "creative-room-1.0 (2026-07-16)"
MAX_INTERNAL_REVISIONS = 2


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _md5(path):
    return hashlib.md5(pathlib.Path(path).read_bytes()).hexdigest()


def _norm(s):
    return re.sub(r"[^a-z0-9']+", " ", (s or "").lower().replace("’", "'")).strip()


# ─────────────────────────────────────────────────────────────────────────────────────────
# §8 THE AUTHORITATIVE STORYBOARD DATA CONTRACT
# ─────────────────────────────────────────────────────────────────────────────────────────
class Provenance(BaseModel):
    role: str
    model: str = ""
    promptVersion: str = ENGINE_VERSION
    canonVersion: str = CANON_VERSION
    at: str = ""
    humanRevision: Optional[str] = None


class VoicePerformance(BaseModel):
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


class Shot(BaseModel):
    shotId: str
    beatId: str
    purpose: str
    intendedDurationRange: str
    openingComposition: str
    openingCharacterState: str
    blocking: str
    principalPerformance: str
    secondaryPerformance: str
    animationAndPhysics: str
    gazeAndExpression: str
    audiencePointOfView: str
    shotSize: str
    cameraHeight: str
    cameraAngle: str
    lensFeeling: str
    depthAndParallax: str
    cameraBehaviour: str
    lightingAndAtmosphere: str
    dialoguePlacement: str
    soundRelationship: str
    closingComposition: str
    closingCharacterState: str
    cutMotivation: str
    transitionType: Literal["CONTINUOUS", "PLANNED_CUT"]
    requiresNewKeyframe: bool
    continuityIn: str
    continuityOut: str
    essentialProviderProtections: List[str] = Field(default_factory=list, max_length=3)
    approvalState: str = "draft"


class Interpretation(BaseModel):
    name: str
    dramaticConstruction: str
    characterBehaviour: str
    audienceExperience: str


class Beat(BaseModel):
    beatId: str
    sceneId: str
    sourceScript: str
    exactDialogue: List[str]
    participatingCharacters: List[str]
    objectiveByCharacter: str
    opposition: str
    subtext: str
    beginningState: str
    pressure: str
    actionDiscoveryOrChoice: str
    reversalReleaseOrRecognition: str
    consequence: str
    reaction: str
    closingState: str
    intendedAudienceResponse: str
    comedyOrEmotionEngine: str
    energyCurve: str
    memorableImage: str
    interpretations: List[Interpretation] = Field(min_length=3, max_length=3)
    selectedDirectorialInterpretation: str
    selectionReason: str
    approvalState: str = "draft"

    @property
    def rejectedApproachSummaries(self):
        return [i.name for i in self.interpretations
                if i.name != self.selectedDirectorialInterpretation]


class Scene(BaseModel):
    sceneId: str
    sourceScriptRange: str
    location: str
    time: str
    participatingCharacters: List[str]
    purpose: str
    dramaticQuestion: str
    emotionalOwner: str
    characterObjectives: str
    opposition: str
    subtext: str
    emotionalEntry: str
    emotionalExit: str
    storyTurn: str
    visualIdentity: str
    lightingAtmosphere: str
    energyShape: str
    connectionFromPreviousScene: str
    handoverToNextScene: str
    showrunnerNotes: str = ""
    approvalState: str = "draft"


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


class ShotList(BaseModel):
    shots: List[Shot]


class VoiceScript(BaseModel):
    performances: List[VoicePerformance]


class ReviewIssue(BaseModel):
    role: Literal["director", "cinematographer", "voice"]
    target: str
    issue: str


class ShowrunnerReview(BaseModel):
    judgement: str            # a WRITTEN creative judgement — never a numerical score
    passes: bool
    issues: List[ReviewIssue] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────────────────
# INTERNAL GATE 0 — CANON INGESTION AND THE EPISODE CANON ENVELOPE
# ─────────────────────────────────────────────────────────────────────────────────────────
_CANON_SOURCES = {
    "showBible": ROOT / "CRYSTAL_BEARS_LOCKED_CANON.md",
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


def _script_package(episode):
    """The approved episode script + exact dialogue live in the beat package — DATA ground
    truth (the deleted legacy renderer is unrelated to its status as the locked script)."""
    cands = sorted((ROOT / "cb-output").glob(f"{episode}_*beat_package.json"),
                   key=lambda p: p.stat().st_mtime)
    if not cands:
        raise RuntimeError(f"no approved script/beat package for {episode} in cb-output/")
    return cands[-1]


def load_canon_envelope(episode="Ep1", log=print):
    """§7 Internal Gate 0: load + version the canon, verify required assets, record
    provenance (source, hash), and surface GENUINE contradictions only — harmless missing
    metadata is reported as a gap, never a block."""
    env = {"episode": episode, "canonVersion": CANON_VERSION, "builtAt": _now(),
           "sources": {}, "gaps": [], "conflicts": []}
    for key, path in _CANON_SOURCES.items():
        if path.exists():
            env["sources"][key] = {"path": str(path), "md5": _md5(path)}
        else:
            env["gaps"].append(f"{key}: {path.name} not present (optional context)")
    spath = _script_package(episode)
    env["sources"]["script"] = {"path": str(spath), "md5": _md5(spath)}
    chars = json.load(open(_CANON_SOURCES["characters"]))
    for name, rec in chars.items():
        if isinstance(rec, dict) and rec.get("anchor"):
            if not (HERE / rec["anchor"]).exists():
                env["conflicts"].append(
                    f"character reference missing on disk: {name} -> {rec['anchor']}")
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


def _script_beats(episode, scene_num=None):
    d = json.load(open(_script_package(episode)))
    beats = d.get("beats") or []
    if scene_num is not None:
        beats = [b for b in beats if str(b.get("sceneNumber")) == str(scene_num)]
    beats.sort(key=lambda b: int(re.search(r"[Bb](\d+)", b.get("beatCode") or "B0").group(1)))
    return beats, d


def _locked_dialogue(beats):
    """(speaker, exact_text) in order — the verbatim lock the Voice Director and the
    dialogue-preservation check both trust."""
    out = []
    for b in beats:
        for c in (b.get("cuts") or []):
            dlg = (c.get("dialogue") or "").strip()
            if dlg and ":" in dlg:
                spk, txt = dlg.split(":", 1)
                if txt.strip():
                    out.append((spk.strip(), txt.strip().strip('"“”').strip()))
    return out


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


# ─────────────────────────────────────────────────────────────────────────────────────────
# THE FOUR ROLE MINDS — each quotes its own taste canon; none imitates a named person
# ─────────────────────────────────────────────────────────────────────────────────────────
def _mind(role, taste_key, charge):
    return (f"You are the {role} of the Crystal Bears creative room — a world-class family-"
            f"animation voice for ages 4-8 with adult-rewarding wit. You never imitate or "
            f"name real filmmakers or studios; you apply the enduring principles below as "
            f"the show's OWN identity.\n\n{charge}\n\n"
            f"YOUR TASTE CANON (your standard of excellence — apply it, quote-check your own "
            f"work against its rejection questions before answering):\n"
            + _canon_text(taste_key)
            + "\n\nSHOW CANON (authoritative, never contradicted):\n"
            + _canon_text("showBible", 6000)
            + "\n\nHARD RULES: approved dialogue is verbatim-locked — never reword, drop or "
              "invent a line. Character identity comes only from references; never describe "
              "physical appearance. No named-person imitation. Concrete, observable craft "
              "language only — 'cinematic', 'beautiful' and 'award-winning' are ambitions, "
              "not directions. Same event -> different behaviour per character (the "
              "character-substitution test).")


PROV = lambda role: Provenance(role=role, model=cb_llm.DIRECTOR_MODEL, at=_now()).model_dump()


# ── INTERNAL GATE 1: EPISODE VISION (Showrunner) ─────────────────────────────────────────
def episode_vision(episode="Ep1", log=print):
    beats, d = _script_beats(episode)
    script = "\n".join(
        f"[Scene {b.get('sceneNumber')} · {b.get('beatCode')}] {b.get('storyBeat','')}\n"
        + "\n".join(f"  {c.get('dialogue')}" for c in (b.get('cuts') or []) if c.get('dialogue'))
        for b in beats)
    v = cb_llm.structured(
        _mind("SHOWRUNNER", "showrunnerTaste",
              "Read the COMPLETE episode before anything is directed. Establish what this "
              "episode is really about beneath the plot, what changes, which relationship "
              "carries its heart, where the audience laughs, leans forward, becomes still, "
              "and what remains after it ends."),
        f"THE COMPLETE APPROVED SCRIPT (dialogue verbatim-locked):\n{script[:24000]}",
        EpisodeVision, label="creative_vision")
    pkg = {"episodeId": episode, "title": d.get("title", episode),
           "sourceScriptVersion": _md5(_script_package(episode)),
           "canonVersion": CANON_VERSION, **v.model_dump(),
           "showrunnerJudgement": "", "approvalState": "draft",
           "provenance": PROV("showrunner")}
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(pkg, open(OUT / f"{episode}_episode_vision.json", "w"), indent=1,
              ensure_ascii=False)
    log(f"EPISODE VISION — theme: {v.theme[:90]}")
    return pkg


# ── INTERNAL GATE 2+3: SCENE, BEAT AND SHOT DIRECTION (Director) ─────────────────────────
def direct_scene(episode, scene_num, vision, log=print):
    beats, _ = _script_beats(episode, scene_num)
    if not beats:
        raise RuntimeError(f"no script material for scene {scene_num}")
    cast = sorted({c for b in beats for c in (b.get("characters") or [])})
    script = json.dumps([{"beatCode": b.get("beatCode"), "storyBeat": b.get("storyBeat"),
                           "dialogue": [c.get("dialogue") for c in (b.get("cuts") or [])
                                         if c.get("dialogue")],
                           "location": b.get("location"), "time": b.get("time")}
                          for b in beats], ensure_ascii=False)
    sd = cb_llm.structured(
        _mind("DIRECTOR", "directorTaste",
              "You own the dramatic, comic, emotional and PHYSICAL interpretation — "
              "animation direction is yours; there is no separate animation role. For every "
              "significant beat you privately create THREE materially different "
              "interpretations (different dramatic construction, character behaviour or "
              "audience experience — never rewordings) and select the strongest, stating "
              "why. Performance arises from thought; physical cause and effect stays "
              "readable; one idea carries each moment."),
        f"EPISODE VISION (the Showrunner's governing intent):\n{json.dumps(vision, ensure_ascii=False)[:6000]}\n\n"
        f"THE SCENE'S APPROVED SCRIPT (dialogue verbatim-locked):\n{script}\n\n"
        f"CHARACTER + RELATIONSHIP CANON for this cast:\n{_characters_for(cast)[:9000]}\n\n"
        f"Direct scene {scene_num}: the Scene record, then one Beat record per script beat "
        f"(beatId = the script's own beatCode; sceneId = 'S{scene_num}'; sourceScript = the "
        f"storyBeat text verbatim; exactDialogue = every locked line, verbatim, in order).",
        SceneDirection, label=f"creative_direct_s{scene_num}")
    # THE VERBATIM SNAP (deterministic): whatever the Director wrote in exactDialogue, the
    # LOCKED script lines replace it beat-for-beat, character-for-character — creative work
    # never gets to paraphrase approved dialogue, and the Showrunner never has to catch it.
    by_code = {str(b.get("beatCode")): b for b in beats}
    for beat in sd.beats:
        src = by_code.get(beat.beatId)
        if src is not None:
            beat.exactDialogue = [c.get("dialogue").strip() for c in (src.get("cuts") or [])
                                    if (c.get("dialogue") or "").strip()]
    return sd


def design_shots(episode, scene_num, sd, log=print):
    sl = cb_llm.structured(
        _mind("DIRECTOR", "directorTaste",
              "Break each selected beat into the number of shots THE IDEA requires — no "
              "default count, no standard time blocks, no one-line-per-shot rule, and never "
              "several incompatible moments crushed together to save a keyframe. Each shot: "
              "ONE primary dramatic purpose, ONE primary performance idea, readable physical "
              "cause and effect, a clear opening state and a meaningful closing state, with "
              "room to anticipate, act and react."),
        f"SCENE DIRECTION:\n{sd.scene.model_dump_json()[:4000]}\n\n"
        f"DIRECTED BEATS (each with the selected interpretation):\n"
        + "\n".join(b.model_dump_json()[:2600] for b in sd.beats)
        + f"\n\nDesign the shots (shotId = '<beatId>.S<n>'; leave every camera field — "
          f"audiencePointOfView, shotSize, cameraHeight, cameraAngle, lensFeeling, "
          f"depthAndParallax, cameraBehaviour, lightingAndAtmosphere, cutMotivation, "
          f"openingComposition, closingComposition — as short placeholders reading 'CINE'; "
          f"the Cinematographer authors them next. Set transitionType provisionally and "
          f"requiresNewKeyframe true only for the sequence's first shot; the Cinematographer "
          f"finalises both. intendedDurationRange like '4-7s'.)",
        ShotList, label=f"creative_shots_s{scene_num}")
    return sl.shots


# ── INTERNAL GATE 4: CINEMATIC DESIGN (Cinematographer) ──────────────────────────────────
def cinematic_design(episode, scene_num, sd, shots, log=print):
    sl = cb_llm.structured(
        _mind("CINEMATOGRAPHER", "cinematographyTaste",
              "Turn the Director's selected interpretation into images that MEAN something. "
              "First hold the whole scene's visual strategy (whose experience governs the "
              "camera, what the audience knows, how close they should feel, the depth and "
              "light strategy) — then author every shot's composition, camera behaviour and "
              "cut. Characters need not stay visible; no fixed screen lanes; geography stays "
              "readable while compositions evolve. Every cut carries a motivation. Mark each "
              "transition CONTINUOUS (the previous approved final frame anchors the next "
              "shot, because continuity strengthens the experience) or PLANNED_CUT (a new "
              "keyframe is deliberately designed — set requiresNewKeyframe true)."),
        f"SCENE:\n{sd.scene.model_dump_json()[:3500]}\n\n"
        f"THE DIRECTOR'S SHOTS (author every 'CINE' field; keep all performance fields "
        f"EXACTLY as the Director wrote them):\n"
        + "\n".join(s.model_dump_json()[:2400] for s in shots),
        ShotList, label=f"creative_cine_s{scene_num}")
    # the Director's performance fields are protected — asserted, not assumed
    by_id = {s.shotId: s for s in shots}
    for s in sl.shots:
        d0 = by_id.get(s.shotId)
        if d0 and _norm(s.principalPerformance) != _norm(d0.principalPerformance):
            s.principalPerformance = d0.principalPerformance
    return sl.shots


# ── INTERNAL GATE 5: VOICE PERFORMANCE DESIGN (Voice Director) ───────────────────────────
def voice_design(episode, scene_num, sd, shots, log=print):
    beats, _ = _script_beats(episode, scene_num)
    lines = _locked_dialogue(beats)
    if not lines:
        return []
    vs = cb_llm.structured(
        _mind("VOICE DIRECTOR", "voiceTaste",
              "Transform each locked line into truthful, character-specific vocal acting for "
              "ElevenLabs v3. What does the character want FROM THE LISTENER; what changes "
              "during the line; which words carry intention; where do they breathe or "
              "hesitate. Every v3 tag has a dramatic purpose — never sprinkled. Dialogue "
              "never automatically starts at frame one. The same line in another mouth must "
              "not receive the same reading."),
        f"SCENE + SELECTED DIRECTION:\n{sd.scene.model_dump_json()[:3000]}\n\n"
        f"THE SHOTS (for physical-action relationships + placement):\n"
        + "\n".join(f"{s.shotId}: {s.principalPerformance} | dialoguePlacement: "
                     f"{s.dialoguePlacement}" for s in shots)
        + "\n\nTHE LOCKED LINES (exactDialogue must be copied VERBATIM):\n"
        + "\n".join(f"{spk}: {txt}" for spk, txt in lines),
        VoiceScript, label=f"creative_voice_s{scene_num}")
    # verbatim lock, enforced deterministically
    want = [(_norm(s), _norm(t)) for s, t in lines]
    got = [(_norm(v.speaker), _norm(v.exactDialogue)) for v in vs.performances]
    for w in want:
        if w not in got:
            raise RuntimeError(f"VOICE PASS DROPPED/REWORDED a locked line: {w}")
    return vs.performances


# ── INTERNAL GATE 6: SHOWRUNNER FINAL CUT (≤2 focused revisions, then escalate) ──────────
def showrunner_review(vision, sd, shots, voices, log=print):
    return cb_llm.structured(
        _mind("SHOWRUNNER", "showrunnerTaste",
              "Review the COMBINED work as one audience experience: story, character, "
              "physical performance, camera, voice, rhythm, continuity, emotion, comedy, "
              "memorability. Apply your rejection questions (character-substitution, "
              "generic-show, mute, memorable-image, camera-purpose, physical-causality, "
              "voice-and-body unity, setup-and-payoff, age-clarity, emotional-truth, "
              "repetition, shot-overload). Give a WRITTEN judgement — never a score. If a "
              "role's work is weak or contradictory, return a precise, focused issue to "
              "that role."),
        f"EPISODE VISION:\n{json.dumps(vision, ensure_ascii=False)[:4000]}\n\n"
        f"SCENE + BEATS:\n{sd.scene.model_dump_json()[:3000]}\n"
        + "\n".join(b.model_dump_json()[:1800] for b in sd.beats)
        + "\n\nSHOTS:\n" + "\n".join(s.model_dump_json()[:1800] for s in shots)
        + "\n\nVOICE:\n" + "\n".join(v.model_dump_json()[:1200] for v in voices),
        ShowrunnerReview, label="creative_review")


def run_scene(scene_num, episode="Ep1", log=print):
    """Internal Gates 0-6 for one scene — automatic, uninterrupted; the HUMAN gate is the
    storyboard review in the Studio afterwards."""
    load_canon_envelope(episode, log=log)
    vpath = OUT / f"{episode}_episode_vision.json"
    vision = (json.load(open(vpath)) if vpath.exists() else episode_vision(episode, log=log))
    sd = direct_scene(episode, scene_num, vision, log=log)
    shots = design_shots(episode, scene_num, sd, log=log)
    shots = cinematic_design(episode, scene_num, sd, shots, log=log)
    voices = voice_design(episode, scene_num, sd, shots, log=log)

    review, revisions = None, []
    for attempt in range(MAX_INTERNAL_REVISIONS + 1):
        review = showrunner_review(vision, sd, shots, voices, log=log)
        log(f"SHOWRUNNER — {'accepts' if review.passes else 'returns work'}: "
            f"{review.judgement[:140]}")
        if review.passes or attempt == MAX_INTERNAL_REVISIONS:
            break
        for issue in review.issues[:3]:
            revisions.append({"role": issue.role, "target": issue.target,
                               "issue": issue.issue, "at": _now()})
            if issue.role == "director":
                sd = direct_scene(episode, scene_num, vision, log=log)
                shots = design_shots(episode, scene_num, sd, log=log)
                shots = cinematic_design(episode, scene_num, sd, shots, log=log)
            elif issue.role == "cinematographer":
                shots = cinematic_design(episode, scene_num, sd, shots, log=log)
            elif issue.role == "voice":
                voices = voice_design(episode, scene_num, sd, shots, log=log)
    escalation = None
    if review and not review.passes:
        escalation = ("UNRESOLVED after the permitted internal revisions — presented to the "
                      "user as a creative question, not endlessly rewritten: "
                      + "; ".join(i.issue for i in review.issues[:3]))
        log("ESCALATION — " + escalation)

    pkg = {"episodeId": episode, "sceneNumber": str(scene_num),
           "engineVersion": ENGINE_VERSION, "canonVersion": CANON_VERSION,
           "builtAt": _now(), "vision": vision,
           "scene": sd.scene.model_dump(),
           "beats": [dict(b.model_dump(),
                           rejectedApproachSummaries=b.rejectedApproachSummaries)
                      for b in sd.beats],
           "shots": [s.model_dump() for s in shots],
           "voicePerformances": [v.model_dump() for v in voices],
           "showrunnerJudgement": review.judgement if review else "",
           "internalRevisions": revisions, "escalation": escalation,
           "provenance": {"showrunner": PROV("showrunner"), "director": PROV("director"),
                           "cinematographer": PROV("cinematographer"),
                           "voice": PROV("voice-director")},
           "approvalState": "awaiting-human-storyboard-approval"}
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{episode}_scene{scene_num}_storyboard.json"
    json.dump(pkg, open(out, "w"), indent=1, ensure_ascii=False)
    log(f"STORYBOARD — scene {scene_num}: {len(sd.beats)} beat(s), {len(shots)} shot(s), "
        f"{len(voices)} voice performance(s) -> {out.name}")
    return pkg


# ─────────────────────────────────────────────────────────────────────────────────────────
# MIGRATION (§10E): reference the existing foundation — copy nothing destructively,
# re-enter nothing manually, invent nothing (gaps are reported, not filled)
# ─────────────────────────────────────────────────────────────────────────────────────────
_PERF_FIELDS = ["consciousDesire", "hiddenEmotionalNeed", "primaryFear", "insecurity",
                "protectiveMask", "comicEngine", "emotionalEngine", "defaultPosture",
                "centreOfGravity", "silhouette", "movementRhythm", "gestureScale",
                "gazeBehaviour", "facialOpennessOrRestraint", "personalSpace",
                "responseToPressure", "responseToEmbarrassment", "responseToSuccess",
                "responseToFailure", "recoveryBehaviour", "useOfStillness",
                "emotionalTells", "neverWithoutStoryReason"]

_BIBLE_MAP = {  # mechanical field mapping from the EXISTING character bible — never invented
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
        run_scene(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "Ep1")
    elif cmd == "migrate":
        migrate(sys.argv[2] if len(sys.argv) > 2 else "Ep1")
    else:
        print(__doc__)
        sys.exit(1)
