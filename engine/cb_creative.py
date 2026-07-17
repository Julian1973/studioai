#!/usr/bin/env python3
"""cb_creative.py — THE CRYSTAL BEARS CREATIVE ROOM (process v2, 2026-07-17).

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

from pydantic import BaseModel, Field

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import cb_llm

CREATIVE = ROOT / "shows" / "crystal-bears" / "creative"
OUT = ROOT / "cb-output" / "creative"
CANON_VERSION = "1.0"
ENGINE_VERSION = "creative-room-2.0 (2026-07-17, whole-scene-treatment process)"
MAX_INTERNAL_REVISIONS = 2


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


class Beat(BaseModel):
    """Gate 3 — beat architecture INSIDE the selected treatment. Beats do not
    automatically become separate shots."""
    beatId: str
    sceneId: str
    sourceScript: str
    exactDialogue: List[str]
    participatingCharacters: List[str]
    whatChanges: str
    whoDrives: str
    audienceAnticipation: str
    actionOrChoice: str
    consequence: str
    emotionalOrComicHandover: str
    approvalState: str = "draft"


class CreativeShotCard(BaseModel):
    """Gate 4 — the lean creative card. Detail exists because it contributes to the idea,
    not because the schema contains a box; production data lives in ProductionDetail,
    added only after the creative sequence passes Gate 6."""
    shotId: str
    beatIds: List[str]                           # a continuous chain may span beats
    purpose: str
    audienceExperience: str
    openingImage: str
    principalPerformance: str
    cameraRelationship: str                      # lead/pursue/lag/lose/rediscover/anticipate/
    #                                              arrive-late/still/abandon-for-another — whatever
    #                                              the idea needs; nothing automatically preferred
    physicalOrEmotionalChange: str
    closingImage: str
    transitionType: Literal["CONTINUOUS", "PLANNED_CUT"]
    transitionReason: str                        # cut: why continuous would be weaker;
    #                                              continuous: why a cut would weaken it
    physicalPerformance: Optional[str] = None    # Gate 5 (Director): body + animation intent
    animationTiming: Optional[str] = None        # Gate 5 (Director): timing/weight of the move
    approvalState: str = "draft"


class ProductionDetail(BaseModel):
    """Added ONLY after Gate 6 passes — the production layer, separate from the idea."""
    shotId: str
    continuityIn: str
    continuityOut: str
    dialogueTiming: str
    referenceRoles: str
    requiresNewKeyframe: bool
    essentialProviderProtections: List[str] = Field(default_factory=list, max_length=3)


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


class Scene(BaseModel):
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


class ShotConference(BaseModel):
    shots: List[CreativeShotCard]


class PerformancePass(BaseModel):
    shots: List[CreativeShotCard]


class VoiceScript(BaseModel):
    performances: List[VoicePerformance]


class ProductionPass(BaseModel):
    details: List[ProductionDetail]


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
    passes: bool
    returnTo: Optional[Literal["gate3", "gate4"]] = None
    issues: List[ReviewIssue] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────────────────
# CANON SOURCES + GATE 0 READINESS
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
    cands = sorted((ROOT / "cb-output").glob(f"{episode}_*beat_package.json"),
                   key=lambda p: p.stat().st_mtime)
    if not cands:
        raise RuntimeError(f"no approved script/beat package for {episode} in cb-output/")
    return cands[-1]


def load_canon_envelope(episode="Ep1", log=print):
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


def _exemplar_text():
    """Approved AND rejected exemplars — explicit human verdicts only. The rejected
    process-v1 exemplar (EX-005) is the room's own most important anti-pattern."""
    p = _CANON_SOURCES["exemplars"]
    if not p.exists():
        return ""
    lib = json.load(open(p))
    lines = []
    for e in lib.get("exemplars", []):
        lines.append(f"[{e['id']} · {e['outcome'].upper()}] {e.get('attempted','')} — "
                     f"user verdict: {e.get('userWords','')} — principle: {e.get('principle','')}")
    return "\n".join(lines)[:7000]


def _script_beats(episode, scene_num=None):
    d = json.load(open(_script_package(episode)))
    beats = d.get("beats") or []
    if scene_num is not None:
        beats = [b for b in beats if str(b.get("sceneNumber")) == str(scene_num)]
    beats.sort(key=lambda b: int(re.search(r"[Bb](\d+)", b.get("beatCode") or "B0").group(1)))
    return beats, d


def _locked_dialogue(beats):
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


def _unresolved_fields_for(names):
    """Which performance-canon fields are unresolved (null) for these characters."""
    p = _CANON_SOURCES["characterPerformance"]
    if not p.exists():
        return {}
    allp = json.load(open(p)).get("characters", {})
    out = {}
    for n in names:
        for k, v in allp.items():
            if _norm(k) == _norm(n) and isinstance(v, dict):
                missing = [f for f, val in v.items()
                           if f not in ("provenance", "cadence", "actingNote") and not val]
                if missing:
                    out[k] = sorted(missing)
    return out


# ─────────────────────────────────────────────────────────────────────────────────────────
# ROLE MINDS — taste canons + the exemplar library's explicit human verdicts
# ─────────────────────────────────────────────────────────────────────────────────────────
def _governed_memory(role):
    """THE CREATIVE LEARNING SYSTEM's scoped retrieval (cb_learning) — each role receives
    only the memory relevant to its task, in labelled categories (approved preference /
    contextual exemplar / provider limitation / unresolved observation), never the whole
    library and never an instruction wall. Falls back to the raw exemplar verdicts when
    the learning stores don't exist yet."""
    try:
        import cb_learning
        text = cb_learning.retrieve_for_role(role)
        if text and "EXEMPLAR" in text or "PREFERENCE" in text:
            return text
    except Exception:
        pass
    return _exemplar_text()


def _mind(role, taste_keys, charge):
    taste = "\n\n".join(_canon_text(k, 7000) for k in taste_keys)
    return (f"You are the {role} of the Crystal Bears creative room — a world-class family-"
            f"animation voice for ages 4-8 with adult-rewarding wit. You never imitate or "
            f"name real filmmakers or studios; you apply the enduring principles below as "
            f"the show's OWN identity.\n\n{charge}\n\n"
            f"YOUR TASTE CANON:\n{taste}\n\n"
            f"GOVERNED CREATIVE MEMORY (scoped to your role; the REJECTED verdicts are "
            f"failures you must not repeat; do not treat any rejected artifact as a "
            f"model, and do not reverse-engineer a 'desired shot' from them):\n"
            + _governed_memory(role)
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


# ─────────────────────────────────────────────────────────────────────────────────────────
# GATE 0 — CANON AND CREATIVE READINESS
# ─────────────────────────────────────────────────────────────────────────────────────────
def gate0_readiness(episode, scene_num, brief, log=print):
    """Confirms canon/script/exemplars; where the participating characters carry
    unresolved performance fields, authors a PROPOSED canon completion for human
    approval. The run proceeds on ESTABLISHED canon only — proposals are saved for
    Julian's decision, never fed into directing."""
    env = load_canon_envelope(episode, log=log)
    beats, _ = _script_beats(episode, scene_num)
    if not beats:
        raise RuntimeError(f"no script material for scene {scene_num}")
    cast = sorted({c for b in beats for c in (b.get("characters") or [])})
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
            "unresolvedFields": unresolved,
            "canonCompletionProposal": str(proposal_path.name) if proposal_path else None,
            "brief": brief or None}


# ─────────────────────────────────────────────────────────────────────────────────────────
# GATE 1 — WHOLE-SCENE CREATIVE TREATMENTS (Director + Cinematographer, jointly)
# ─────────────────────────────────────────────────────────────────────────────────────────
def gate1_treatments(episode, scene_num, vision, ready, log=print):
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
        f"THE SCENE'S APPROVED SCRIPT (dialogue verbatim-locked):\n{script}\n\n"
        f"CHARACTER + RELATIONSHIP CANON:\n{_characters_for(ready['cast'])[:9000]}"
        + brief_line,
        TreatmentSet, label=f"gate1_treatments_s{scene_num}")
    log(f"GATE 1 — three whole-scene treatments: "
        + " | ".join(t.name for t in ts.treatments))
    return ts.treatments


# ─────────────────────────────────────────────────────────────────────────────────────────
# GATE 2 — SHOWRUNNER TREATMENT SELECTION (before any beat breakdown)
# ─────────────────────────────────────────────────────────────────────────────────────────
def gate2_select(vision, treatments, ready, log=print):
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
                review_notes="", log=print):
    script = json.dumps([{"beatCode": b.get("beatCode"), "storyBeat": b.get("storyBeat"),
                           "dialogue": [c.get("dialogue") for c in (b.get("cuts") or [])
                                         if c.get("dialogue")],
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
              "comic chain remains continuous when continuity strengthens it."),
        f"THE SELECTED TREATMENT (this governs everything):\n{treatment.model_dump_json()}\n\n"
        f"THE SHOWRUNNER'S SELECTION:\n{selection.model_dump_json()}\n\n"
        f"EPISODE VISION:\n{json.dumps(vision, ensure_ascii=False)[:4000]}\n\n"
        f"THE SCENE'S APPROVED SCRIPT (dialogue verbatim-locked):\n{script}\n\n"
        f"CHARACTER CANON:\n{_characters_for(ready['cast'])[:8000]}{notes}\n\n"
        f"Return the Scene record and one Beat per script beat (beatId = the script's own "
        f"beatCode; sceneId = 'S{scene_num}'; sourceScript = the storyBeat verbatim; "
        f"exactDialogue = every locked line, verbatim, in order).",
        SceneDirection, label=f"gate3_beats_s{scene_num}")
    # THE VERBATIM SNAP (deterministic, kept from v1): the locked script lines replace
    # whatever the Director wrote, beat for beat.
    by_code = {str(b.get("beatCode")): b for b in ready["beats"]}
    for beat in sd.beats:
        src = by_code.get(beat.beatId)
        if src is not None:
            beat.exactDialogue = [c.get("dialogue").strip() for c in (src.get("cuts") or [])
                                    if (c.get("dialogue") or "").strip()]
    return sd


# ─────────────────────────────────────────────────────────────────────────────────────────
# GATE 4 — DIRECTOR/CINEMATOGRAPHER SHOT CONFERENCE
# ─────────────────────────────────────────────────────────────────────────────────────────
def gate4_shot_conference(episode, scene_num, selection, treatment, sd,
                          review_notes="", log=print):
    notes = (f"\n\nSHOWRUNNER'S RETURN NOTES (redesign the SEQUENCE — never patch "
             f"wording): {review_notes}" if review_notes else "")
    sc = cb_llm.structured(
        _mind("DIRECTOR AND CINEMATOGRAPHER, IN SHOT CONFERENCE",
              ["directorTaste", "cinematographyTaste"],
              "Design the shot sequence TOGETHER, inside the selected treatment. A shot "
              "exists ONLY when it introduces a meaningful change in point of view, "
              "information, scale, emotion, power, energy, spatial experience, comic timing "
              "or visual idea — never to complete coverage. For EVERY cut, state why "
              "remaining continuous would be weaker; for EVERY continuous shot, state why a "
              "cut would weaken the experience (transitionReason). The camera may lead, "
              "pursue, lag, lose a character, rediscover a character, anticipate, arrive "
              "late, remain still, or abandon one character for another — NO behaviour is "
              "automatically preferred; choose what the treatment's experience demands. "
              "Geography stays understandable, but characters get no permanent screen "
              "sides. A reaction character receives a separate shot ONLY when that reaction "
              "changes the meaning — never as automatic punctuation. A chain may span "
              "beats (beatIds lists every beat a shot carries). Keep each card LEAN: the "
              "eight creative fields carry the idea; production detail comes later and "
              "only if the sequence passes."),
        f"THE SELECTED TREATMENT (the sequence must deliver ITS experience):\n"
        f"{treatment.model_dump_json()}\n\n"
        f"GOVERNING AUDIENCE EXPERIENCE: {selection.governingAudienceExperience}\n\n"
        f"THE BEATS:\n" + "\n".join(b.model_dump_json() for b in sd.beats)
        + f"{notes}\n\nshotId = 'S{scene_num}.SH<n>' in sequence order.",
        ShotConference, label=f"gate4_shots_s{scene_num}")
    log(f"GATE 4 — {len(sc.shots)} shot(s): "
        + " ".join(f"{s.shotId}[{'C' if s.transitionType=='CONTINUOUS' else 'K'}]"
                    for s in sc.shots))
    return sc.shots


# ─────────────────────────────────────────────────────────────────────────────────────────
# GATE 5 — PERFORMANCE AND VOICE SYNTHESIS
# ─────────────────────────────────────────────────────────────────────────────────────────
def gate5_performance(episode, scene_num, treatment, sd, shots, log=print):
    pp = cb_llm.structured(
        _mind("DIRECTOR", ["directorTaste"],
              "The visual sequence now exists. Author each shot's PHYSICAL PERFORMANCE and "
              "ANIMATION TIMING (physicalPerformance, animationTiming): performance arises "
              "from thought; physical cause and effect stays readable; weight, anticipation "
              "and follow-through are timed to the treatment's rhythm. Change NOTHING else "
              "on the cards — the sequence design is settled."),
        f"THE SELECTED TREATMENT:\n{treatment.model_dump_json()[:3000]}\n\n"
        f"THE SHOT SEQUENCE:\n" + "\n".join(s.model_dump_json() for s in shots),
        PerformancePass, label=f"gate5_perf_s{scene_num}")
    by_id = {s.shotId: s for s in shots}
    for s in pp.shots:
        d0 = by_id.get(s.shotId)
        if d0:                                    # only the two Gate-5 fields may change
            d0.physicalPerformance = s.physicalPerformance
            d0.animationTiming = s.animationTiming
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
        + "\n\nTHE LOCKED LINES (exactDialogue must be copied VERBATIM):\n"
        + "\n".join(f"{spk}: {txt}" for spk, txt in lines),
        VoiceScript, label=f"gate5_voice_s{scene_num}")
    want = [(_norm(s), _norm(t)) for s, t in lines]
    got = [(_norm(v.speaker), _norm(v.exactDialogue)) for v in vs.performances]
    for w in want:
        if w not in got:
            raise RuntimeError(f"VOICE PASS DROPPED/REWORDED a locked line: {w}")
    return vs.performances


# ─────────────────────────────────────────────────────────────────────────────────────────
# GATE 6 — ADVERSARIAL SHOWRUNNER REVIEW
# ─────────────────────────────────────────────────────────────────────────────────────────
def gate6_adversarial_review(vision, selection, treatment, sd, shots, voices, log=print):
    return cb_llm.structured(
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
              "or 'gate4' (the shot sequence is wrong). Never request wording patches. Give "
              "a WRITTEN judgement — never a score."),
        f"THE SELECTED TREATMENT (the contract this scene must deliver):\n"
        f"{treatment.model_dump_json()}\n\n"
        f"GOVERNING EXPERIENCE: {selection.governingAudienceExperience}\n\n"
        f"EPISODE VISION:\n{json.dumps(vision, ensure_ascii=False)[:3500]}\n\n"
        f"BEATS:\n" + "\n".join(b.model_dump_json()[:1600] for b in sd.beats)
        + "\n\nSHOTS:\n" + "\n".join(s.model_dump_json()[:1800] for s in shots)
        + "\n\nVOICE:\n" + "\n".join(v.model_dump_json()[:1100] for v in voices),
        ShowrunnerReview, label="gate6_review")


# ─────────────────────────────────────────────────────────────────────────────────────────
# PRODUCTION DETAIL — added ONLY after the creative sequence passes
# ─────────────────────────────────────────────────────────────────────────────────────────
def production_detail(episode, scene_num, sd, shots, voices, log=print):
    pd = cb_llm.structured(
        _mind("DIRECTOR AND CINEMATOGRAPHER, PRODUCTION PASS",
              ["directorTaste", "cinematographyTaste"],
              "The creative sequence has PASSED. Add the production layer only: exact "
              "continuity state in/out per shot; dialogue timing within the shot; reference "
              "roles (which references anchor identity/environment); whether the shot "
              "requires a NEW keyframe (a PLANNED_CUT does; a CONTINUOUS chain does not); "
              "and AT MOST three genuinely provider-essential protections — only what would "
              "invalidate the shot if violated, never a constraint wall. Add nothing "
              "creative; change nothing creative."),
        f"THE SHOTS:\n" + "\n".join(s.model_dump_json() for s in shots)
        + "\n\nVOICE TIMINGS:\n"
        + "\n".join(f"{v.speaker}: {v.expectedTiming}" for v in voices),
        ProductionPass, label=f"production_detail_s{scene_num}")
    by_id = {d.shotId: d for d in pd.details}
    out = []
    for i, s in enumerate(shots):                 # keyframe truth is structural, not stylistic
        d = by_id.get(s.shotId) or ProductionDetail(
            shotId=s.shotId, continuityIn="", continuityOut="", dialogueTiming="",
            referenceRoles="", requiresNewKeyframe=(s.transitionType == "PLANNED_CUT"))
        # a scene's FIRST shot has no predecessor frame to continue from — it always
        # requires a keyframe, whatever its creative transitionType says about how it plays
        d.requiresNewKeyframe = (i == 0) or (s.transitionType == "PLANNED_CUT")
        out.append(d)
    return out


# ─────────────────────────────────────────────────────────────────────────────────────────
# THE SCENE RUN — Gates 0-6 + production detail
# ─────────────────────────────────────────────────────────────────────────────────────────
def run_scene(scene_num, episode="Ep1", brief=None, log=print):
    ready = gate0_readiness(episode, scene_num, brief, log=log)
    vpath = OUT / f"{episode}_episode_vision.json"
    vision = (json.load(open(vpath)) if vpath.exists() else episode_vision(episode, log=log))

    treatments = gate1_treatments(episode, scene_num, vision, ready, log=log)
    selection = gate2_select(vision, treatments, ready, log=log)
    treatment = _selected_treatment(treatments, selection)

    sd = gate3_beats(episode, scene_num, vision, selection, treatment, ready, log=log)
    shots = gate4_shot_conference(episode, scene_num, selection, treatment, sd, log=log)
    shots = gate5_performance(episode, scene_num, treatment, sd, shots, log=log)
    voices = gate5_voice(episode, scene_num, sd, shots, log=log)

    review, revisions = None, []
    for attempt in range(MAX_INTERNAL_REVISIONS + 1):
        review = gate6_adversarial_review(vision, selection, treatment, sd, shots, voices,
                                           log=log)
        log(f"GATE 6 — {'accepts' if review.passes else 'REJECTS'}: {review.judgement[:140]}")
        if review.passes or attempt == MAX_INTERNAL_REVISIONS:
            break
        notes = "; ".join(f"[{i.role}->{i.target}] {i.issue}" for i in review.issues[:4]) \
                or review.judgement[:400]
        revisions.append({"returnTo": review.returnTo or "gate4", "notes": notes,
                           "at": _now()})
        if (review.returnTo or "gate4") == "gate3":     # complete re-architecture
            sd = gate3_beats(episode, scene_num, vision, selection, treatment, ready,
                              review_notes=notes, log=log)
        shots = gate4_shot_conference(episode, scene_num, selection, treatment, sd,
                                        review_notes=notes, log=log)
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

    pkg = {"episodeId": episode, "sceneNumber": str(scene_num),
           "engineVersion": ENGINE_VERSION, "canonVersion": CANON_VERSION,
           "builtAt": _now(), "vision": vision,
           "ambitionBrief": ready["brief"],
           "canonCompletionProposal": ready["canonCompletionProposal"],
           "directedOnEstablishedCanonOnly": True,
           "treatments": [t.model_dump() for t in treatments],
           "treatmentSelection": selection.model_dump(),
           "scene": sd.scene.model_dump(),
           "beats": [b.model_dump() for b in sd.beats],
           "shots": [s.model_dump() for s in shots],
           "productionDetail": [d.model_dump() for d in details],
           "voicePerformances": [v.model_dump() for v in voices],
           "showrunnerJudgement": review.judgement if review else "",
           "treatmentComparison": review.treatmentComparison if review else "",
           "internalRevisions": revisions, "escalation": escalation,
           "provenance": {"showrunner": PROV("showrunner"), "director": PROV("director"),
                           "cinematographer": PROV("cinematographer"),
                           "voice": PROV("voice-director")},
           "approvalState": "awaiting-human-storyboard-approval"}
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{episode}_scene{scene_num}_storyboard.json"
    json.dump(pkg, open(out, "w"), indent=1, ensure_ascii=False)
    log(f"STORYBOARD v2 — scene {scene_num}: {len(sd.beats)} beat(s), {len(shots)} shot(s), "
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
