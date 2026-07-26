#!/usr/bin/env python3
"""cb_creative.py — THE CRYSTAL BEARS CREATIVE ROOM (process v2, 2026-07-17).

⚠ FROZEN 2026-07-17 (Julian's system-freeze checkpoint, PIPELINE_CUTOVER_LEDGER.md §8):
this module's Gates 0-6, ProductionDetail and CreativeShotCard are LOCKED as of the
openingImage/reference-role/continuityIn corrections that day. No further creative or
compiler changes without a fresh, dated ruling — see the ledger for the full record.

2026-07-19 exception, Julian's own fresh ruling ("we can be flexible if it secures the
beat again... this is a straight jacket, that's a guide not a rule"): production_detail's
requiresNewKeyframe was a mechanical straightjacket (forced True for every PLANNED_CUT,
discarding whatever continuity the mind had already authored for that same shot) — fixed
to a genuine, defaulting-to-relay creative judgment. See correction #4 in that function's
own docstring for the full record.

2026-07-21 exception, Julian's own direct ruling ("all of the producer, the director, the
showrunner... need to fire so that when we create the storyboard, the storyboard is
already being populated... the script-to-storyboard is actually where the magic
happens"): a NEW gate, 6b — the Producer's own feasibility & scope review — is added
after Gate 6 passes and Production Detail is authored. This is purely ADDITIVE, never a
modification of any frozen Gate 0-6/ProductionDetail/CreativeShotCard content — no frozen
field, prompt or schema above is touched. See gate6b_producer_feasibility's own docstring.

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
import cb_departments

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
    # ── THE DIFFERENTIATION DECISIONS (Julian's directive item 4, 2026-07-25) ────────
    # Decided by the DIRECTOR at Gate 3, upstream, not inferred later by a prompt writer.
    # Deliberately only THREE new fields: whatChanges already owns the turn, whoDrives
    # already owns the performance leader, audienceAnticipation already owns the audience
    # experience — restating those here would create the competing authorities item 1
    # forbids. Optional so every existing beat still validates.
    primaryForm: Optional[str] = Field(default=None, description=(
        "The beat's dramatic mode: physical_comedy | character_comedy | intimate_emotion | "
        "relationship_dialogue | action | tension | wonder | exposition | reveal | "
        "transition. This INFORMS your judgement; it NEVER selects a camera, lens, shot "
        "count or edit. There is no 'comedy always whip-pans' or 'emotion always "
        "close-ups' rule — choose what THIS beat needs."))
    secondaryColour: Optional[str] = Field(default=None, description=(
        "An optional second form running underneath. A beat can be physical comedy AND "
        "affection, or tension AND wonder. Null if the beat is single-toned."))
    tempoShape: Optional[str] = Field(default=None, description=(
        "How this beat's pace MOVES — e.g. 'fast, one hard stop, then a held deadpan', "
        "'slow build with no release'. A SHAPE across the beat, never one flat speed."))
    approvalState: str = "draft"


class CreativeShotCard(BaseModel):
    """Gate 4 — the lean creative card. Detail exists because it contributes to the idea,
    not because the schema contains a box; production data lives in ProductionDetail,
    added only after the creative sequence passes Gate 6."""
    shotId: str
    beatIds: List[str]                           # a continuous chain may span beats
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
    # THE CUT-PACE DECISION (2026-07-21, Julian — "you have to do what you think is right
    # to deliver the beat, whether that's short, sharp and snappy or a longer one... that's
    # down to you, the director, the producer... it has to fire every single time, it's not
    # optional"): REQUIRED on every shot, no default, no exception — the pace this shot's
    # own generation call actually cuts at is a real directorial decision, made HERE, at the
    # same shot conference that already decides transitionType, grounded in the scene's own
    # already-authored rhythmAndEscalation/comicOrDramaticMechanism (Gate 1) — never
    # inherited from an unrelated reference example's own genre. A held emotional beat earns
    # single_continuous_take; a five-hit collision earns rapid_cuts; most shots sit between.
    cutPace: Literal["single_continuous_take", "paced_cuts", "rapid_cuts"]
    cutPaceReason: str = Field(min_length=1, description=(
        "Why THIS pace serves THIS beat — grounded in the scene's own rhythmAndEscalation/"
        "comicOrDramaticMechanism, never a generic justification."))
    physicalPerformance: Optional[str] = None    # Gate 5 (Director): body + animation intent
    animationTiming: Optional[str] = None        # Gate 5 (Director): timing/weight of the move
    # THE INTERNAL CUTS (Gate 5, authored ONLY when cutPace calls for them): each entry is
    # ONE self-contained cut in Seedance's own real multi-shot grammar — one action + one
    # camera move, ordered, ending on its own completed beat (never a mid-action cut). Left
    # empty for single_continuous_take, where performanceAssignment already carries the one
    # flowing take. Never a mechanical split of performanceAssignment's own prose — the
    # Director authors each cut directly, the same discipline as the gag-physics fields
    # below, because deriving cuts by slicing prose invents boundaries nobody actually chose.
    internalCuts: List[str] = Field(default_factory=list)
    # THE CLIP/CARD SEPARATION (Julian's directive, 2026-07-25). internalCuts REDEFINE
    # their camera shots as prose; composedOf REFERENCES other Shot Cards in this scene
    # that this one generation renders in order, each compiled from its own card. The two
    # are mutually exclusive. Empty (the default) = this card is its own generation clip.
    composedOf: List[str] = Field(default_factory=list)
    # THE GAG-PHYSICS CONTRACT (2026-07-21, Julian — "how do we get the prompt to deliver
    # the feel, the laughter, the pain"): cb_engine.compile_shot_contract has always known
    # how to render cb_engine.PhysicalStaging into the shipped prompt (it's the exact fix
    # for the old beat-pipeline's "Fuzzby vanished into the flower" lesson) — but nothing in
    # this storyboard schema could ever populate it, so cb_handover.distil_shot hardcoded it
    # to None for every shot promoted through the live pipeline. These four, authored
    # alongside physicalPerformance/animationTiming at the SAME Gate 5 pass (never a new
    # gate), are that missing source. Optional and all-or-nothing by design: only a shot
    # that carries a big physical/comedic beat needs them; an ordinary shot leaves them
    # null, exactly as it does today.
    gagStaysVisible: Optional[str] = Field(default=None, description=(
        "Only for a shot carrying a big physical/comedic beat: what must remain readable in "
        "silhouette THROUGHOUT the gag (e.g. 'his wings and legs stay visible above the "
        "petal line the whole time'). This is the specific guard against a gag reading as "
        "the character simply vanishing — leave null for an ordinary shot."))
    gagContactAndWeight: Optional[str] = Field(default=None, description=(
        "Only for a shot carrying a big physical/comedic beat: the real cause-and-effect "
        "chain — what touches what, where weight compresses, where it rebounds, what flies "
        "loose. Leave null for an ordinary shot; never a restatement of physicalPerformance."))
    gagPayoffShape: Optional[str] = Field(default=None, description=(
        "Only for a shot carrying a big physical/comedic beat: the exact visual shape of "
        "the gag's payoff — the one image this beat must land having delivered. Leave null "
        "for an ordinary shot."))
    gagProhibitedStaging: List[str] = Field(default_factory=list, description=(
        "Only for a shot carrying a big physical/comedic beat: this gag's own specific "
        "failure modes (e.g. 'never fully disappearing into the flower'). Empty for an "
        "ordinary shot."))
    # ── THE ENDING DECISION (Julian's directive item 2, 2026-07-25) ─────────────────
    # Chosen deliberately at Gate 4, before approval. Retires the previously-universal
    # closing hold: only reaction_hold / living_hold require a hold tail downstream.
    endingBehaviour: Optional[str] = Field(default=None, description=(
        "How this shot ENDS: reaction_hold (hold on a reaction) | living_hold (held frame, "
        "performance continues) | continue_in_motion (action carries past the cut) | "
        "cut_on_action (edit lands mid-movement) | visual_transition (the image becomes "
        "the way into the next shot). Do NOT default to a hold — an action beat or a "
        "transition that stops dead is wrong."))
    approvalState: str = "draft"


class CharacterContinuity(BaseModel):
    """ONE character's typed continuity at a shot's boundary (2026-07-17, Julian's
    consolidation-checkpoint directive, item 3) — authored during Gate 5/6 production
    detailing, alongside continuityIn/Out's whole-shot prose, never inferred downstream by
    a promotion boundary (cb_handover.py must never invent this; it only maps it).
    Deliberately lean (id + two states, not cb_engine.CharacterState's full seven-field
    screenZone/facing/pose/expression/visibleMarks/heldProps shape) — that richer typed
    contract is a render-facing production-compiler concern; this is the production-detail
    layer's own honest, single-string-per-direction account of what changed for THIS
    character, per Julian's own literal spec (character ID; opening state; closing
    state)."""
    characterId: str = Field(min_length=1)
    openingState: str = Field(min_length=1)
    closingState: str = Field(min_length=1)


class ProductionDetail(BaseModel):
    """Added ONLY after Gate 6 passes — the production layer, separate from the idea.
    intendedDurationRange (2026-07-17 schema checkpoint): a credible per-shot range,
    e.g. '5-8s', authored from the FROZEN Creative Shot Card's own physicalPerformance +
    animationTiming (Gate 5) and the locked dialogue timing — never invented independent
    of the approved creative content, never a re-authoring of it.
    characterContinuity (2026-07-17, item 3): OPTIONAL — populated only for a shot whose
    Production Detail has been authored/regenerated under this field's existence; an empty
    list is the honest, legacy state for a shot not yet touched, never an invented one."""
    shotId: str
    continuityIn: str
    continuityOut: str
    dialogueTiming: str
    referenceRoles: str
    requiresNewKeyframe: bool
    intendedDurationRange: str
    essentialProviderProtections: List[str] = Field(default_factory=list, max_length=3)
    characterContinuity: List[CharacterContinuity] = Field(default_factory=list)


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
    # THE LINE'S PLACE AGAINST THE PICTURE (2026-07-26, GAP 6). cb_engine.DialogueLine
    # .minOnsetSec and cb_render._stretch_natural_pause are fully built for exactly the
    # "'Nailed it.' came through as an almost-inaudible ~0.4s blip" failure, and
    # cb_handover._dialogue_lines already reads vp.get("minOnsetSec") — but this schema
    # had no such field, so the storyboard could never author one and the whole mechanism
    # has never been able to fire from the live script-to-storyboard path. This is that
    # missing source. OPTIONAL and null for almost every line: only a line the picture's
    # own physical climax must CLEAR before it lands needs a floor.
    minOnsetSec: Optional[float] = Field(default=None, description=(
        "Seconds INTO the shot before this line's onset may begin — an absolute floor "
        "against the shot's fixed picture duration, never 'N seconds after the previous "
        "line' (ElevenLabs renders the same chant at 2.4s in one take and 3.9s in the "
        "next). Author it ONLY when the picture has to finish something before the line "
        "can be heard — a crash chain landing, a reveal completing. Null otherwise."))
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


class FeasibilityIssue(BaseModel):
    """One Gate 6b finding — never a creative note, always a producibility one (a missing
    asset, an unrealistic ask, a scope problem the storyboard's own words create)."""
    shotId: str
    severity: Literal["BLOCK", "NOTE"]
    issue: str


class ProducerFeasibilityReview(BaseModel):
    """Gate 6b (2026-07-21) — the Producer's OWN pass, after Gate 6 passes and Production
    Detail exists. Feasibility and scope only — never a creative opinion; the Producer
    does not judge whether a shot is good, only whether it can actually be delivered.
    judgement/issues are the LLM's own holistic scope read; missingCharacterReferences and
    durationValidation (merged in by gate6b_producer_feasibility, never authored by the
    LLM itself) are computed mechanically from what's already on disk — the LLM is shown
    both and asked to reason from them, never to re-derive or contradict them."""
    judgement: str
    passes: bool
    issues: List[FeasibilityIssue] = Field(default_factory=list)


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
    "producerTaste": CREATIVE / "PRODUCER_TASTE_CANON.md",
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


def _canonical_exemplars(limit=12):
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


def _scene_cast(sd):
    """Every named character the scene's own approved beats actually carry.

    The three rooms downstream of Gate 3 (shot conference, voice, adversarial review) all
    receive `sd` and none of them received a cast, so none of them received the character
    canon — this is the one derivation they were each missing, in one place instead of
    three copies that can drift."""
    return sorted({c for b in getattr(sd, "beats", []) or []
                   for c in (getattr(b, "participatingCharacters", None) or [])})


def _characters_for(names):
    try:
        chars = json.load(open(_CANON_SOURCES["characters"]))
    except Exception:
        return "{}"
    # THE ACTING CANON IS EMITTED FIRST AND IS NEVER TRUNCATED (2026-07-26).
    #
    # Julian: "pixar level DIRECTION, ACTING, sound and imagery." Measured on the real Scene 1
    # pair, the acting canon was not reaching the room at all. Every caller slices this
    # payload by raw character count (12,000 / 9,000 / 8,000 at gates 0/1/3) and the prose
    # `bible` is emitted first at 13,232 chars for Fuzzby and 7,788 for Zenny — 21,020 of a
    # 33,577-char payload. So the Director's 8,000-char slice ended INSIDE Fuzzby's own list
    # of prohibitions, and `actingNote`, `lexicon` and `cameraRegister` arrived at NO gate for
    # EITHER character. The room was authoring performance with the structural canon and none
    # of the performance canon.
    #
    # The whole acting canon for both characters is 1,443 characters. It costs ~4% of the
    # Director's budget to have it complete. So it leads, and the long prose bible — which is
    # reference, and which the taste canons and show bible already restate — is what gives way
    # when a cap bites. Ordering, not a cap change: no budget is raised, nothing is refused.
    ACTING_FIRST = ("cadence", "actingNote", "lexicon", "cameraRegister",
                    "gender", "sizeRank", "size")
    picked = {}
    for n in names:
        for k, v in chars.items():
            if _norm(k) == _norm(n) and isinstance(v, dict):
                rec = {kk: v.get(kk) for kk in ACTING_FIRST if v.get(kk)}
                if v.get("bible"):
                    rec["bible"] = v["bible"]      # last: the long reference prose
                picked[k] = rec
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
    # TWO BLOCKS, NOT ONE (2026-07-26). Per-record ordering alone was not enough: with the
    # acting fields first INSIDE each record, Fuzzby's 13,232-char bible still sat between his
    # acting canon and Zenny's, so the second character's performance canon was still cut at
    # every cap. Emitting EVERY character's acting canon before ANY character's prose bible is
    # what actually guarantees the whole cast's performance arrives — measured: 4/4 acting
    # fields for BOTH characters inside the Director's 8,000-char slice, where before it was
    # 0/4 for either.
    acting = {k: {kk: vv for kk, vv in rec.items() if kk != "bible"}
              for k, rec in picked.items()}
    bibles = {k: rec["bible"] for k, rec in picked.items() if rec.get("bible")}
    return json.dumps({"actingCanon": acting,          # every character, always survives
                       "performanceCanon": perf,
                       "relationships": rel,
                       "bibles": bibles},              # long reference prose, trimmed first
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
def _mind(role, taste_keys, charge):
    # THE TASTE CANONS ARRIVE WHOLE (2026-07-26). Measured, not assumed: FOUR of the five
    # canons are longer than the 7,000-char slice this line used to take, and in every one of
    # them what the slice cut was the operative half.
    #   DIRECTOR_TASTE_CANON.md        9,900 chars — ANTI-PATTERNS begins at char 7,340, so
    #     "Checklist choreography" ("six comma-separated verbs in one sentence, each
    #     independently clocked, none causing the next"), "Adjective chaos", "Simultaneous
    #     everything" and ALL NINE REJECTION QUESTIONS reached NO Director gate — including
    #     #4, "What is the one cause, and what are its visible consequences? (A verb list —
    #     rewrite as physics.)", which is the cause-chain law this room most needed.
    #     gate3_beats, gate4_shot_conference and gate5_performance all authored without it.
    #   CINEMATOGRAPHY_TASTE_CANON.md  9,140 — REJECTION QUESTIONS lost.
    #   SHOWRUNNER_TASTE_CANON.md     10,264 — "REJECTION QUESTIONS (ask every one, every
    #     review)" has never once reached the Showrunner at gate 0, 2 or 6.
    #   VOICE_PERFORMANCE_CANON.md    10,253 — the three WORKED EXAMPLES on real, verbatim-
    #     locked Ep1 lines lost.
    # This is the acting-canon finding again in a different file: the craft was written,
    # approved, and eaten by a cap. 14,000 clears the largest canon by 3,736 chars. Cost
    # measured on the real files: the joint Director/DP system prompt goes 26,048 -> 31,088
    # chars. Nothing is refused and no budget is introduced — a truncation is deleted.
    taste = "\n\n".join(_canon_text(k, 14000) for k in taste_keys)
    # The Creative Room now genuinely hires the repository's specialist people.  Only the
    # concise marked runtime contracts are loaded (not historical/superseded pipeline notes
    # elsewhere in the long skill documents).  This remains the ONE existing Gate 0-6
    # creative path; no parallel storyboard pipeline is introduced.
    worker_keys = []
    if "DIRECTOR" in role:
        worker_keys.append("director")
    if "CINEMATOGRAPHER" in role:
        worker_keys.append("cinematography")
    if "VOICE" in role:
        worker_keys.append("voice")
    if "PRODUCER" in role:
        worker_keys.append("producer")
    # THE SHOWRUNNER'S BRANCH (2026-07-26). Without this the chair is inert: the SKILLS key
    # exists and load_runtime_skill('showrunner') returns her 1,605-char contract, but _mind
    # never asks for it, so every SHOWRUNNER pass still emitted the fallback string
    # "Showrunner taste canon owns this pass." Checked AFTER the substring tests above,
    # deliberately — "DIRECTOR, WITH THE SHOWRUNNER IN THE ROOM" must load BOTH contracts,
    # and the existing joint pattern ("DIRECTOR AND CINEMATOGRAPHER") already relies on this
    # same additive matching rather than an elif chain.
    if "SHOWRUNNER" in role:
        worker_keys.append("showrunner")
    worker_contracts = "\n\n".join(cb_departments.load_runtime_skill(k)
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
            # THE SHOW BIBLE ARRIVES WHOLE (2026-07-26). The taste-canon fix above swept the
            # line it was written on and stopped there; this line, four lines down, kept a
            # 6,000-char slice of a 31,829-char canon — 81% of the show's own locked bible
            # cut from every room, every gate, since the room was built. Measured, not
            # assumed: the cut lands MID-TABLE in "3. The Crystal Power System — LOCKED",
            # so every gate has been authoring with roughly two bears' crystal/feeling/
            # archetype/colour/note rows and none of the other seven, none of the Five
            # Pillars' own timing clock, and nothing below. A room told "SHOW CANON
            # (authoritative, never contradicted)" and then handed a fifth of it cannot
            # keep the show on brand — it can only keep the part it was shown. 40,000
            # clears the real file by 8,171 chars. A truncation is deleted; no cap, no
            # budget and no refusal is introduced.
            + _canon_text("showBible", 40000)
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
            + f"\n\nESTABLISHED CANON FOR THIS CAST:\n{_characters_for(cast)}",
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
        f"CHARACTER + RELATIONSHIP CANON:\n{_characters_for(ready['cast'])}"
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
        f"CHARACTER + RELATIONSHIP CANON (a treatment that does not fit these people is not the right treatment, however well it reads):\n"
        f"{_characters_for(ready['cast'])}\n\n"
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
        _mind("DIRECTOR, WITH THE SHOWRUNNER IN THE ROOM",
              ["directorTaste", "showrunnerTaste"],
              "Structure the beats INSIDE the selected whole-scene treatment. Every beat "
              "defines: what changes; who drives the change; audience anticipation; the "
              "action or choice; the consequence; and the emotional or comic handover. "
              "Beats do NOT automatically become separate shots — a physical, emotional or "
              "comic chain remains continuous when continuity strengthens it. "
              "THE DRAMATIC FORM DECISION (mandatory, every beat, 2026-07-25): name this "
              "beat's primaryForm — what KIND of dramatic material it actually is (physical "
              "comedy, quiet emotion, dialogue exchange, tension or reveal, fast action, "
              "wonder, transition, and so on: describe what it IS, you are not picking from "
              "a fixed menu) — its secondaryColour if a second register genuinely runs "
              "under it, and its tempoShape: how the beat's energy actually moves across "
              "its own length (builds, drops, holds then breaks, stutters, runs flat and "
              "fast). These are DESCRIPTIONS OF THIS BEAT, never labels that select a "
              "template: two beats sharing a primaryForm must still be directed "
              "differently, because their tempo, their turn and their leader differ. A "
              "quiet emotional beat and a crash are not the same material and must not "
              "inherit the same shape — say plainly which this is."),
        f"THE SELECTED TREATMENT (this governs everything):\n{treatment.model_dump_json()}\n\n"
        f"THE SHOWRUNNER'S SELECTION:\n{selection.model_dump_json()}\n\n"
        f"EPISODE VISION:\n{json.dumps(vision, ensure_ascii=False)[:4000]}\n\n"
        f"THE SCENE'S APPROVED SCRIPT (dialogue verbatim-locked):\n{script}\n\n"
        f"CHARACTER CANON:\n{_characters_for(ready['cast'])}{notes}\n\n"
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
        _mind("DIRECTOR AND CINEMATOGRAPHER, IN SHOT CONFERENCE, "
              "WITH THE SHOWRUNNER IN THE ROOM",
              ["directorTaste", "cinematographyTaste", "showrunnerTaste"],
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
              "only if the sequence passes. "
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
              "hard-refuses the whole scene's production handover (LAW 6). "
              "WHAT YOU WRITE HERE IS EXECUTED, NOT INTERPRETED (2026-07-26). Every word "
              "of cameraRelationship, openingImage and closingImage travels — through the "
              "shot contract, into the Seedance prompt — and is read LITERALLY by a video "
              "model. It has no ear for craft shorthand. A framing decision you write as a "
              "LOCK becomes a freeze command it obeys for the whole span you name, and the "
              "span is usually the dialogue, which is most of the clip. This is not "
              "theoretical: a previous card here authored \u2018settles into a steady medium "
              "two-shot with both characters in frame and holds that two-shot, unbroken, "
              "from the crash recovery through both spoken lines to the final frame\u2019 \u2014 "
              "every chair downstream did its job faithfully and the result was a dead back "
              "half that got the shot pulled. SO: author the INTENT, never the MECHANISM. "
              "\u2018Both must stay readable through the exchange\u2019 is intent \u2014 it leaves the "
              "performance somewhere to live. \u2018Holds the two-shot unbroken\u2019 is a mechanism, "
              "and it is a stop order. \u2018Locked\u2019, \u2018unbroken\u2019, \u2018static\u2019, \u2018held "
              "throughout\u2019 and \u2018motionless\u2019 are the words that kill a beat. Where "
              "stillness genuinely IS the idea \u2014 and in this show it often is \u2014 name the "
              "live thing inside it: what the character is still DOING, and the small "
              "corrections that prove they are alive while holding. Your own "
              "CINEMATOGRAPHY canon already calls the habitual two-shot \u2018the laziest "
              "possible answer to whose moment is this\u2019; this is that anti-pattern arriving "
              "at the moment you write the field, instead of sitting in a document nobody "
              "reads twice.\n\n"
              "THE SHOWRUNNER IS IN THIS CONFERENCE AND SHE TALKS WHILE THE SEQUENCE IS "
              "DESIGNED (2026-07-26). She holds NO verdict here and no shot waits on her; "
              "she never overrules your staging, lens, cut or comic construction. She is "
              "accountable for one thing at this table: that the SEQUENCE is this show \u2014 "
              "that the cuts serve the Five Pillars beat this scene sits on, that the "
              "point-of-view choices honour who this moment belongs to, that geography and "
              "continuity carry from the scene before and set up the one after, and that "
              "no shot could be lifted into a different children\u2019s show unchanged. When "
              "the sequence is already this show she says so and gets out of the way. "
              "When it is not, she names the show-true version of the SAME ambition \u2014 "
              "never the smaller one.\n\n"
              "THE CUT-PACE DECISION (mandatory, every shot, no exceptions): decide "
              "cutPace — single_continuous_take, paced_cuts (2-3 internal cuts), or "
              "rapid_cuts (4+ tight, fast cuts) — from what THIS shot's own beat actually "
              "needs, grounded in the treatment's own rhythmAndEscalation and "
              "comicOrDramaticMechanism, never a fixed default and never copied from an "
              "unrelated reference. A held emotional beat earns single_continuous_take; a "
              "frantic collision earns rapid_cuts; state why in cutPaceReason. Most shots "
              "sit at paced_cuts or single_continuous_take — rapid_cuts is for the shot "
              "that genuinely IS the scene's own bang-bang-bang moment, not a default. "
              "THE CLIP UNIT (locked 2026-07-25, from AnyFilm's own measured grouping "
              "rule): a generation clip is A COMPLETE CONVERSATIONAL OR ACTION UNIT — it "
              "exists because it contains one finished exchange, not because a duration "
              "ran out. Group camera setups until the dialogue exchange COMPLETES, "
              "including the reaction that closes it. An establishing or transition shot "
              "with no dialogue STANDS ALONE as its own clip. One to three camera setups "
              "per clip; four is rare and needs a reason. If a clip is carrying more than "
              "three distinct story beats, it is too dense — split it. "
              "THE ENDING DECISION (mandatory, every shot, 2026-07-25): decide "
              "endingBehaviour — how this shot actually STOPS. reaction_hold (settle and "
              "hold on a reaction), living_hold (the frame holds while the performance "
              "keeps breathing), continue_in_motion (the action carries straight past the "
              "cut), cut_on_action (the edit lands mid-movement), or visual_transition (the "
              "image itself becomes the way into the next shot). THERE IS NO DEFAULT AND NO "
              "PREFERRED ENDING. A held closing beat is one legitimate ending among five, "
              "not the house style: an action chain that stops dead to hold is wrong, and a "
              "transition that settles instead of carrying is wrong. Decide from what THIS "
              "shot's own dramatic form and tempo demand — the beat's primaryForm and "
              "tempoShape are stated for you; read them. If consecutive shots keep choosing "
              "the same ending, that is a symptom to fix, not a sequence. "
              "cameraRelationship IS READ LITERALLY BY A VIDEO MODEL (2026-07-26). "
              "cb_handover.distil_shot copies this field verbatim into Shot.camera and it "
              "reaches the provider as you wrote it — so a framing MECHANISM authored here "
              "becomes a freeze command downstream, obeyed for the whole span it governs, "
              "and that span is usually the dialogue, which is most of the clip. This is "
              "not hypothetical: S1.SH2's own card read 'holds that two-shot, unbroken, "
              "from the crash recovery through the discovery, both spoken lines and the "
              "button to the final frame', and the take did exactly that, faithfully, and "
              "was rejected for it. Author the INTENT — what must stay true and why ('both "
              "of them have to stay readable through the exchange; her reaction is the "
              "second half of his joke') — and leave the mechanism to the camera. Stillness "
              "remains fully available and is often the right call: when you choose it, say "
              "what it is FOR and what keeps moving inside it, never how long a frame is "
              "held."),
        f"CHARACTER CANON FOR THIS SCENE’S CAST (you are staging THESE people — whose moment a shot belongs to, who the camera can afford to lose, and what a character is still DOING inside a held frame are all answered here):\n"
        f"{_characters_for(_scene_cast(sd))}\n\n"
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
        _mind("DIRECTOR, WITH THE SHOWRUNNER IN THE ROOM",
              ["directorTaste", "showrunnerTaste"],
              "The visual sequence now exists. Author each shot's PHYSICAL PERFORMANCE and "
              "ANIMATION TIMING (physicalPerformance, animationTiming): performance arises "
              "from thought; physical cause and effect stays readable; weight, anticipation "
              "and follow-through are timed to the treatment's rhythm. physicalPerformance "
              "must NEVER quote or paraphrase a character's spoken line, even a fragment - "
              "describe only the body: what the character does before, during and after "
              "the line lands, never the words themselves (the audio track alone carries "
              "dialogue; a shot's own dialogue words appearing here hard-refuses the whole "
              "scene's production handover, LAW 6).\n\n"
              "THE GAG-PHYSICS CONTRACT: for a shot that carries a BIG physical or comedic "
              "beat — the moment where the whole gag lands, not every shot in a comedic "
              "scene — also author gagStaysVisible / gagContactAndWeight / gagPayoffShape / "
              "gagProhibitedStaging. gagStaysVisible is a SHORT NOUN PHRASE, never a full "
              "sentence (e.g. 'his wings and legs above the petal line', NOT 'From the "
              "moment he enters, his wings must remain visible') — it is spliced directly "
              "after the word 'Keep' downstream, so a full sentence there reads broken. "
              "gagContactAndWeight and gagPayoffShape are the real contact-and-weight chain "
              "(what hits what, where it compresses, where it rebounds) and the exact shape "
              "of the payoff — full sentences, same register as physicalPerformance. "
              "gagProhibitedStaging names this gag's own failure modes (e.g. a character "
              "disappearing entirely into a flower/prop instead of staying visible). Leave "
              "all four null for an ordinary shot — never author them as a restatement of "
              "physicalPerformance, and never invent a big beat that isn't already there.\n\n"
              "If cutPace/cutPaceReason are not already set on a shot, decide them now, "
              "here, using the SAME standard as Gate 4: grounded in the treatment's own "
              "rhythmAndEscalation and comicOrDramaticMechanism, never a fixed default.\n\n"
              "INTERNAL CUTS (mandatory whenever this shot's own cutPace is paced_cuts or "
              "rapid_cuts — leave empty for single_continuous_take): author internalCuts as "
              "an ordered list of self-contained cuts in Seedance's own real multi-shot "
              "grammar — each entry ONE action plus ONE camera move, ending on its own "
              "completed beat, never a mid-action cut. 2-3 entries for paced_cuts, 4 or more "
              "for rapid_cuts, matching the count cutPace itself already commits to. Never a "
              "restatement of physicalPerformance chopped into pieces — each cut is its own "
              "sentence, in order, building toward visualPayoff. The SAME LAW 6 rule that "
              "governs physicalPerformance governs every internalCuts entry too: NEVER quote "
              "or paraphrase a character's spoken line, even a fragment, even inside quotation "
              "marks — describe only the body and camera around the moment the line lands "
              "(e.g. 'as he delivers his line', never the words themselves). Change NOTHING "
              "else on the cards — the sequence design is settled.\n\n"
              "THE SHOWRUNNER IS IN THIS PASS AND SHE TALKS WHILE THE PERFORMANCE IS WRITTEN "
              "(2026-07-26). She holds NO verdict here, no shot waits on her, and she never "
              "rewrites your body-language, timing or gag construction. She is accountable, "
              "on every shot, for two things. (1) THIS CAST, NOT ANY CAST: run the "
              "substitution test on the physical performance itself — if the same body could "
              "belong to a different character it is not authored yet, and she names what "
              "THIS character's own register does with this exact moment, working from the "
              "acting canon supplied below rather than a generic adjective. (2) THE CHARGED "
              "STILL: she refuses, as written, any performance that instructs stillness as a "
              "STATE. 'Motionless', 'flat', 'locked', 'barely moves' and 'stays still' are "
              "freeze commands — a model obeys them literally and the performance dies on "
              "screen. Stillness is often exactly right in this show; when it is, the "
              "performance must name the continuous thing the character is DOING while "
              "holding, and the small corrections that prove they are alive inside it. Where "
              "the performance is already this cast's own she says so and gets out of the "
              "way."),
        f"THE SELECTED TREATMENT:\n{treatment.model_dump_json()[:3000]}\n\n"
        f"THE SHOT SEQUENCE:\n" + "\n".join(s.model_dump_json() for s in shots)
        # THE ACTING CANON REACHES THE PERFORMANCE PASS (2026-07-26). Commit ca80b59 got the
        # acting canon into gates 0/1/3. This pass — the one that actually AUTHORS physical
        # performance — was never in that list because it was handed NO character canon of
        # any kind: its user message was treatment + shots, and `sd` was an unused parameter.
        # Seating the Showrunner here to hold character truth without the register would be
        # an empty chair, and the substitution test she is charged with is unrunnable
        # without it. Cast comes from the beats Gate 3 already authored; same 8,000-char
        # slice Gate 3 uses, and _characters_for emits the acting canon for the whole cast
        # first, so it survives the slice.
        + "\n\nCHARACTER CANON FOR THIS SCENE'S CAST (acting canon first — this is the "
          "register the substitution test runs against):\n"
        + _characters_for(_scene_cast(sd)),
        PerformancePass, label=f"gate5_perf_s{scene_num}")
    by_id = {s.shotId: s for s in shots}
    for s in pp.shots:
        d0 = by_id.get(s.shotId)
        if d0:                                    # only the Gate-5 fields may change
            d0.physicalPerformance = s.physicalPerformance
            d0.animationTiming = s.animationTiming
            d0.gagStaysVisible = s.gagStaysVisible
            d0.gagContactAndWeight = s.gagContactAndWeight
            d0.gagPayoffShape = s.gagPayoffShape
            d0.gagProhibitedStaging = s.gagProhibitedStaging
            d0.cutPace = s.cutPace
            d0.cutPaceReason = s.cutPaceReason
            d0.internalCuts = s.internalCuts
    return shots


def gate5_voice(episode, scene_num, sd, shots, log=print):
    beats, _ = _script_beats(episode, scene_num)
    lines = _locked_dialogue(beats)
    if not lines:
        return []
    vs = cb_llm.structured(
        _mind("VOICE DIRECTOR, WITH THE DIRECTOR AND THE SHOWRUNNER IN THE ROOM",
              ["voiceTaste", "directorTaste", "showrunnerTaste"],
              "Transform each locked line into truthful, character-specific vocal acting "
              "for ElevenLabs v3, RECONCILED with the body: the physical performance below "
              "is what the character is doing while speaking. What does the character want "
              "FROM THE LISTENER; what changes during the line; which words carry "
              "intention; where do they breathe or hesitate. Every v3 tag has a dramatic "
              "purpose. Dialogue never automatically starts at frame one — its timing may "
              "shape editorial rhythm, but never replaces the selected treatment."),
        f"CHARACTER CANON FOR THIS SCENE’S CAST (the voice IS the character — this is the register, the lexicon and the relationship the read has to be true to):\n"
        f"{_characters_for(_scene_cast(sd))}\n\n"
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
              "a WRITTEN judgement — never a score. "
              "THE UNIVERSALS TEST (2026-07-25, run it explicitly before you judge): read "
              "DOWN the whole sequence and look for anything that is true of EVERY shot — "
              "one continuous-take habit, one camera move, one focal length, one shot "
              "count, one prompt shape, one closing hold. A value that never varies across "
              "materially different dramatic material is a template asserting itself, not a "
              "decision, and it is grounds to fail. Check endingBehaviour first, then "
              "cutPace: if beats of genuinely different form (a crash and a held emotional "
              "moment) resolved to the same ending or the same pace, say so by name and "
              "return to gate4."),
        f"CHARACTER CANON FOR THIS SCENE’S CAST (‘could this belong to another show’ is unanswerable without it — run the substitution test against THIS):\n"
        f"{_characters_for(_scene_cast(sd))}\n\n"
        f"THE SELECTED TREATMENT (the contract this scene must deliver):\n"
        f"{treatment.model_dump_json()}\n\n"
        f"GOVERNING EXPERIENCE: {selection.governingAudienceExperience}\n\n"
        f"EPISODE VISION:\n{json.dumps(vision, ensure_ascii=False)[:3500]}\n\n"
        f"BEATS:\n" + "\n".join(b.model_dump_json()[:1600] for b in sd.beats)
        + "\n\nSHOTS:\n" + "\n".join(s.model_dump_json()[:1800] for s in shots)
        + "\n\nVOICE:\n" + "\n".join(v.model_dump_json()[:1100] for v in voices),
        # THE CRITIC SHOULD NOT BE THE AUTHOR (2026-07-26). This gate is asked to ACTIVELY
        # ATTEMPT to fail work that, until now, the very same model wrote — nine gates of
        # it. A model reviewing its own output is a weak critic: it shares the blind spots
        # that produced the work, and the pattern it is least able to see is its own.
        # CB_REVIEW_PROVIDER points this one gate at a different provider from the
        # authoring gates. Unset (the default) means same-as-author — the behaviour that
        # shipped until today — so nothing changes for anyone who does not opt in. This is
        # true whichever provider authors; it is not an argument about which model is
        # better.
        ShowrunnerReview, label="gate6_review",
        provider=cb_llm.REVIEW_PROVIDER or None)


# ─────────────────────────────────────────────────────────────────────────────────────────
# GATE 6b — PRODUCER FEASIBILITY & SCOPE REVIEW (2026-07-21, purely additive — see the
# module docstring's dated exception)
# ─────────────────────────────────────────────────────────────────────────────────────────
def _missing_character_references(cast):
    """Deterministic, zero-LLM — the SAME check load_canon_envelope already runs
    episode-wide (cb_creative.py's own conflicts list), scoped here to exactly this
    scene's own cast, so the Producer reasons from a computed fact rather than
    re-deriving it. Returns a sorted list of character names with no locked anchor."""
    try:
        chars = json.load(open(_CANON_SOURCES["characters"]))
    except Exception:
        return sorted(cast)
    missing = []
    for name in cast:
        rec = next((v for k, v in chars.items() if _norm(k) == _norm(name)), None)
        anchor = rec.get("anchor") if isinstance(rec, dict) else None
        if not anchor or not (HERE / anchor).exists():
            missing.append(name)
    return sorted(missing)


def gate6b_producer_feasibility(episode, scene_num, shots, details, cast, log=print):
    """Gate 6b — feasibility and scope ONLY, never a creative opinion. Runs after Gate 6
    passes and Production Detail is authored (intendedDurationRange only exists once
    Production Detail has run, so this cannot fire any earlier in the sequence).

    Two facts are computed MECHANICALLY, never authored by the LLM, and handed to it as
    ground truth to reason from: missingCharacterReferences (_missing_character_
    references, above) and durationValidation (validate_duration_ranges, already used
    elsewhere in this module — reused verbatim, not reimplemented). The LLM's own job is
    the holistic scope read neither of those mechanical checks can make (an oversized
    cast crowding one frame, a physically impossible simultaneous performance) — grounded
    in the same shots/details it's shown, never re-deriving or contradicting the two
    mechanical facts.

    Unlike Gate 6, a BLOCK here never returns the scene to an earlier creative gate for
    automatic re-authoring — a missing reference or an unrealistic duration is not fixed
    by different prose; it needs a real production decision, surfaced plainly in Julian's
    own review screen before he approves the storyboard, exactly like any other BLOCK
    finding in this studio."""
    missing_refs = _missing_character_references(cast)
    duration = validate_duration_ranges(details, log=log)
    review = cb_llm.structured(
        _mind("PRODUCER", ["producerTaste"],
              "Gate 6b: the creative sequence has already passed Gate 6 and Production "
              "Detail is already authored. Judge ONLY whether this scene can actually be "
              "produced as written — never whether it's good. Two facts below are already "
              "computed for you; reason from them, never re-derive or contradict them. "
              "Add your own holistic scope judgement on top: does any shot ask for more "
              "simultaneous named characters, or a scale of action, than a reference-"
              "anchored single composition can credibly hold together. Name the specific "
              "shot and the specific practical reason for every issue you raise."),
        f"SHOTS:\n" + "\n".join(s.model_dump_json()[:1400] for s in shots)
        + f"\n\nPRODUCTION DETAIL:\n" + "\n".join(d.model_dump_json()[:900] for d in details)
        + f"\n\nMECHANICALLY COMPUTED — MISSING CHARACTER REFERENCES (each one is a real "
          f"BLOCK on its own, already true, do not re-check): "
        + (", ".join(missing_refs) if missing_refs else "none")
        + f"\n\nMECHANICALLY COMPUTED — DURATION VALIDATION (already true, do not "
          f"re-check): " + json.dumps(duration, ensure_ascii=False),
        ProducerFeasibilityReview, label=f"gate6b_producer_s{scene_num}")
    # Every missing reference is a real, standing BLOCK regardless of what the LLM itself
    # returned — a mechanical fact is never something a generous specialist gets to waive.
    issues = list(review.issues)
    for name in missing_refs:
        if not any(name.lower() in i.issue.lower() for i in issues):
            issues.append(FeasibilityIssue(
                shotId="scene", severity="BLOCK",
                issue=f"{name} appears in this scene with no locked reference image on disk."))
    passes = review.passes and not missing_refs and not duration.get("invalidShotIds")
    return {"judgement": review.judgement, "passes": passes,
            "issues": [i.model_dump() for i in issues],
            "missingCharacterReferences": missing_refs,
            "durationValidation": duration}


# ─────────────────────────────────────────────────────────────────────────────────────────
# PRODUCTION DETAIL — added ONLY after the creative sequence passes
# ─────────────────────────────────────────────────────────────────────────────────────────
def production_detail(episode, scene_num, sd, shots, voices, log=print, shot_cast=None,
                       opener_shot_id=None):
    """opener_shot_id (2026-07-17, added alongside the continuityIn correction below):
    identifies the scene's TRUE first shot by shotId, not by list position. Defaults to
    shots[0].shotId — correct for the normal, whole-scene call this function has always
    had (run_scene passes every shot, in order, so position 0 genuinely IS the opener).
    A SCOPED call (regenerate_production_detail's only_shot_id path) must pass the real
    scene-opener's shotId explicitly instead of relying on position-in-a-subset, or a
    later, non-opener shot regenerated alone would be mistaken for the opener and both
    requiresNewKeyframe and continuityIn (below) would be set wrongly for it.

    shot_cast (2026-07-17, item 3, optional): {shotId: [characterName, ...]} — when
    given, the mind is told EXACTLY which characters are in each shot and asked to author
    typed per-character continuity (character ID; opening state; closing state) for
    precisely that named cast, never inventing or omitting one. Omitted (None) preserves
    the pre-existing behaviour exactly — characterContinuity is simply not requested and
    every ProductionDetail keeps its schema-default empty list.

    2026-07-17 correction #2 (Julian's ruling, same day as the openingImage simplification):
    closes THE DUPLICATION — continuityIn was being authored as a second description of the
    shot's own opening image, competing with openingImage inside the compiled keyframe
    brief. Fixed at the source, not with a text-similarity/dedup engine: continuityIn now
    means ONLY visual state genuinely INHERITED from the immediately preceding shot or
    scene — never a restatement of this shot's own opening action.

    2026-07-17 correction #3 (Julian's system-freeze checkpoint, same day — THE
    SIMPLIFICATION): correction #2's own fix used a literal sentinel PHRASE
    ("N/A — scene opener; no predecessor shot to inherit from.") stamped into continuityIn
    for the scene's true first shot, duplicated byte-for-byte in cb_engine.py so its
    compiler could recognise it. Julian's ruling: replace that duplicated string with TYPED
    ABSENCE in the existing schema — no new field, state, helper layer or protocol.
    continuityIn/continuityOut are already plain, unconstrained `str` fields (no
    Field(min_length=1)) — the schema ALREADY has a natural absence value, the empty
    string, used elsewhere in this same function as the fallback default for a shot the
    LLM's own response omitted entirely (see the ProductionDetail(...) fallback below,
    unchanged, always "" for both fields). For the scene's true first shot (i==0), there is
    no predecessor to inherit from, so continuityIn is now set MECHANICALLY to "" (never
    LLM-authored — the same structural-fact treatment requiresNewKeyframe's own i==0 case
    already gets, one line below). cb_handover._continuity_state maps an empty
    continuityIn to cb_engine's own typed None (Shot.continuityIn: Optional[ContinuityState]
    = None) — the compiler (cb_engine.compile_keyframe_prompt) omits the 'Continuity in:'
    paragraph on that None, a literal is-None check, never a string comparison.

    2026-07-19 correction #4 (Julian, exercising his own explicit exception to this
    module's freeze — "we can be flexible if it secures the beat again... this is a
    straight jacket, that's a guide not a rule"): requiresNewKeyframe used to be forced
    True for EVERY shot whose transitionType is PLANNED_CUT, regardless of what the mind
    actually authored for it (see the mechanical override below, pre-fix: `is_opener or
    (transitionType == "PLANNED_CUT")`) — a real, live bug, not a hypothetical: the current
    Scene 1 storyboard has all five shots marked PLANNED_CUT, so every one of them was
    forced to a disconnected fresh keyframe even though four of them already carry rich,
    genuinely-inherited continuityIn/continuityOut/characterContinuity text (pollen dust,
    an unsettled hover, a held pose) that a relay is exactly built to preserve. transition
    Type answers a CAMERA/EDIT question (does the shot cut or hold); requiresNewKeyframe
    answers a DIFFERENT question (does this shot's visible world reset), and conflating them
    is the same "any editorial cut treated as a full reset" bug independently found and
    fixed the same day in cb_engine.py's own design_scene authoring prompt (see that
    module's 2026-07-19 note above OPENER_ANCHOR/RELAY_ANCHOR).
    FIXED: the mind is now asked to author requiresNewKeyframe itself as a genuine creative
    judgment — default FALSE (this shot's opening frame anchors off the ACTUAL previous
    shot, exactly as its own continuityIn already describes, even though the cut itself
    changes camera/character/framing) — reserving TRUE for a genuine scene/location reset,
    or a deliberate choice that a disconnected fresh image is what actually LANDS this
    beat (a hard button, a hidden reveal, a scene-defining wide). This is a guide with a
    strong default, never an absolute rule — the model's own authored value is now
    TRUSTED, not silently overwritten by transitionType. The ONE thing that stays
    mechanical (unchanged, still structural fact, not a stylistic choice) is the scene's
    true first shot (is_opener): it always requires a keyframe, since there is no
    predecessor to relay off, whatever transitionType or the mind's own answer says."""
    cast_block = ""
    if shot_cast:
        cast_block = ("\n\nSHOT CAST (author characterContinuity for EXACTLY these named "
                       "characters, per shot — never invent a character not listed here, "
                       "never omit one that is):\n"
                       + "\n".join(f"{sid}: {', '.join(names)}" for sid, names in shot_cast.items()))
    pd = cb_llm.structured(
        _mind("DIRECTOR AND CINEMATOGRAPHER, PRODUCTION PASS, "
              "WITH THE SHOWRUNNER IN THE ROOM",
              ["directorTaste", "cinematographyTaste", "showrunnerTaste"],
              "The creative sequence has PASSED. Add the production layer only: "
              "continuityIn/Out; dialogue timing within the shot; reference roles (which "
              "references anchor identity/environment); whether the shot requires a NEW, "
              "DISCONNECTED keyframe (requiresNewKeyframe) — DEFAULT FALSE for every shot "
              "except the scene's true opener, even when the shot is a PLANNED_CUT: a cut "
              "is a camera/edit choice, not a claim that the visible world resets, and the "
              "continuityIn you are about to author for this same shot is exactly the kind "
              "of carried-forward state a relay (opening off the actual previous shot) "
              "preserves. Set it TRUE only for a genuine scene/location reset, or when a "
              "disconnected fresh image is the deliberate choice that makes THIS beat land "
              "(a hard button, a hidden reveal, a scene-defining wide) — a real judgment "
              "call you are making, never a mechanical consequence of the cut itself; a "
              "credible intendedDurationRange per shot (e.g. '5-8s') authored FROM the shot's own "
              "already-approved physicalPerformance and animationTiming (the weight and "
              "timing of the move already decided at Gate 5) and the locked dialogue's own "
              "timing where the shot carries a line — never invented independent of that "
              "already-approved content, and never a re-authoring of the performance "
              "itself; and AT MOST three genuinely provider-essential protections — only "
              "what would invalidate the shot if violated, never a constraint wall. "
              "continuityIn is ONLY what genuinely carries in from the shot immediately "
              "before this one — a mark, a position, an environmental state left over from "
              "what just happened. It is NEVER a second description of THIS shot's own "
              "opening image or action; openingImage already owns that, on the creative "
              "card, and this field must not compete with it. If nothing meaningfully "
              "carries in (this shot opens a new beat of action clean), say so briefly "
              "rather than inventing continuity that doesn't exist. When a SHOT CAST is "
              "given, also author characterContinuity: for each named character, one short "
              "opening state (their state at the shot's own first frame) and one short "
              "closing state (their state at the shot's own last frame) — concrete, "
              "observable, never psychological; this typed field is unaffected by the "
              "continuityIn correction above. Add nothing creative; change nothing "
              "creative."),
        f"CHARACTER CANON FOR THIS SCENE’S CAST (characterContinuity’s opening and closing states are THESE people’s states — read them from here, never generically):\n"
        f"{_characters_for(_scene_cast(sd))}\n\n"
        f"THE SHOTS (physicalPerformance/animationTiming are ALREADY APPROVED — ground the "
        f"duration in them, never rewrite them):\n"
        + "\n".join(s.model_dump_json() for s in shots)
        + "\n\nVOICE TIMINGS (locked dialogue — ground dialogue-bearing shots' duration in "
          "these):\n"
        + "\n".join(f"{v.speaker}: {v.expectedTiming}" for v in voices)
        + cast_block,
        ProductionPass, label=f"production_detail_s{scene_num}")
    real_opener = opener_shot_id or (shots[0].shotId if shots else None)
    by_id = {d.shotId: d for d in pd.details}
    out = []
    for s in shots:                    # ONLY the true opener is structural; everything
        is_opener = (s.shotId == real_opener)  # else is the mind's own authored judgment
        d = by_id.get(s.shotId) or ProductionDetail(
            shotId=s.shotId, continuityIn="", continuityOut="", dialogueTiming="",
            referenceRoles="", requiresNewKeyframe=False,
            intendedDurationRange="")
        # 2026-07-19 correction #4 (see docstring): a scene's FIRST shot has no predecessor
        # frame to continue from — it always requires a keyframe, whatever its creative
        # transitionType or the mind's own answer says. Every OTHER shot keeps whatever the
        # mind actually authored (defaulting False above if its response omitted the shot
        # entirely) — transitionType no longer forces True regardless of that judgment.
        d.requiresNewKeyframe = is_opener or d.requiresNewKeyframe
        if is_opener:              # mechanical, never LLM-authored — see docstring above.
            d.continuityIn = ""    # typed absence (correction #3) — the schema's own
                                    # existing empty-string convention, not a sentinel phrase
        if shot_cast and s.shotId in shot_cast:
            # mechanical guard, not authoring: drop anything the model named that isn't in
            # the given cast, never invent a missing one — a deterministic revalidation of
            # what the LLM returned, the same discipline _field_rejections applies elsewhere
            allowed = set(shot_cast[s.shotId])
            d.characterContinuity = [c for c in d.characterContinuity
                                      if c.characterId in allowed]
        out.append(d)
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

    escalation, details, producer = None, [], None
    if review and not review.passes:
        escalation = ("UNRESOLVED after the permitted complete creative revisions — "
                      "escalated for human direction, not endlessly rewritten: "
                      + (("; ".join(i.issue for i in review.issues[:3])) or
                          review.judgement[:400]))
        log("ESCALATION — " + escalation)
    else:
        details = production_detail(episode, scene_num, sd, shots, voices, log=log)
        producer = gate6b_producer_feasibility(episode, scene_num, shots, details,
                                               ready["cast"], log=log)
        log(f"GATE 6b — Producer {'clears' if producer['passes'] else 'BLOCKS'}: "
            f"{producer['judgement'][:140]}")

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
           "producerFeasibility": producer,
           "provenance": {"showrunner": PROV("showrunner"), "director": PROV("director"),
                           "cinematographer": PROV("cinematographer"),
                           "voice": PROV("voice-director"),
                           **({"producer": PROV("producer")} if producer else {})},
           "approvalState": "awaiting-human-storyboard-approval"}
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{episode}_scene{scene_num}_storyboard.json"
    json.dump(pkg, open(out, "w"), indent=1, ensure_ascii=False)
    log(f"STORYBOARD v2 — scene {scene_num}: {len(sd.beats)} beat(s), {len(shots)} shot(s), "
        # 2026-07-19: counts the mind's own requiresNewKeyframe verdict, not transitionType —
        # a PLANNED_CUT no longer implies a fresh keyframe (correction #4 above).
        f"{sum(1 for d in details if d.requiresNewKeyframe)} keyframe shot(s), "
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
