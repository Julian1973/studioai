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
import os
import pathlib
import re
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

import cb_formulas
import cb_llm

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

RUNTIME_START = "<!-- RUNTIME_WORKER_START -->"
RUNTIME_END = "<!-- RUNTIME_WORKER_END -->"

SKILLS = {
    "director": ROOT / "skills/crystal-bears-director/SKILL.md",
    "cinematography": ROOT / "skills/crystal-bears-cinematographer/SKILL.md",
    "dp": ROOT / "skills/crystal-bears-dp/SKILL.md",
    "voice": ROOT / "skills/crystal-bears-voice-director/SKILL.md",
    # THE DIRECTOR HOLDS THE ANIMATION CHAIR (2026-07-25). Two independent chair
    # tables existed — cb_render._DEPARTMENT_WORKERS and this one — and only this
    # one actually decides which skill loads. Re-pointing the other alone changed
    # nothing, which a test caught. Same two-sources-of-truth defect as the rest of
    # tonight. The camera skill also carried five stale markers (10-12s beats, the
    # retired FRAME CHAIN doctrine); the director skill is clean.
    "animation": ROOT / "skills/crystal-bears-director/SKILL.md",
    "review": ROOT / "skills/crystal-bears-continuity/SKILL.md",
    "post": ROOT / "skills/crystal-bears-post/SKILL.md",
    "producer": ROOT / "skills/crystal-bears-producer/SKILL.md",
    # THE SHOWRUNNER TAKES HER CHAIR (2026-07-26). This file is the only table that decides
    # which contract loads (cb_render._DEPARTMENT_WORKERS is the render-stage table and has
    # no showrunner row, correctly — she authors no provider prompt). Before this key,
    # cb_creative._mind emitted the literal fallback string 'Showrunner taste canon owns
    # this pass.' at gates 0, 2 AND 6 — measured: _mind('SHOWRUNNER', ['showrunnerTaste'])
    # = 16,488 chars with 'Crystal Bears Showrunner' NOT in it. The one chair asked to
    # guarantee bible fidelity was the one chair with no contract, at any gate.
    "showrunner": ROOT / "skills/crystal-bears-showrunner/SKILL.md",
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
     "worker": "Director", "influences": "Pete Docter \u00b7 Glen Keane",
     "skill": "crystal-bears-director", "output": "exact Seedance prompt"},
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
        if rec["id"] == "cinematography":
            item["loaded"] = item["loaded"] and bool(load_runtime_skill("dp"))
        out.append(item)
    return out


def load_runtime_skill(worker):
    """Read the marked runtime contract from the real SKILL.md on every worker call.

    The repository's historical skill documents contain useful research plus superseded
    pipeline notes.  Only the concise marked contract is executable; the source document
    remains available to humans without letting stale instructions silently enter a call.
    """
    path = SKILLS[worker]
    text = path.read_text(encoding="utf-8")
    if RUNTIME_START not in text or RUNTIME_END not in text:
        raise RuntimeError(f"{path} has no executable runtime worker contract")
    return text.split(RUNTIME_START, 1)[1].split(RUNTIME_END, 1)[0].strip()


# SIMPLIFIED 2026-07-21 (Julian's own words: "I don't want rigid flags and structures, and
# the prompts need to be really simple. We've overengineered everything on this."). These
# three schemas used to carry 5-7 structured breakdown fields each (composition, lensAnd-
# CameraRelationship, performanceArc, ...) — confirmed, before this change, that NONE of
# them were ever read anywhere downstream (cb_render.py, cb-studio/serve.py, app.html all
# only ever touch .providerPrompt). They existed purely to make the LLM call feel more
# structured; in practice they were dead weight the model had to fill in and a reviewer
# never saw. Down to the one thing that ships (providerPrompt) plus one plain-language
# verdict (doesItLand) — Julian's own framing: "each one of these phases, they have to
# make sure that it lands."
class LookDirection(BaseModel):
    providerPrompt: str = Field(min_length=40)
    doesItLand: str = Field(min_length=1)


class CinematographyDirection(BaseModel):
    shotId: str
    providerPrompt: str = Field(min_length=40)
    doesItLand: str = Field(min_length=1)


# SIMPLIFIED 2026-07-21 (the same pass as LookDirection/CinematographyDirection/
# AnimationDirection, above): dramaticIntention/subtext/cadenceAndBreath/timingAndBody
# duplicated ground the storyboard's own Voice Performance role (cb_creative.VoicePerformance,
# gate5_voice) already covers — that authoring already happened, following VOICE_PERFORMANCE_
# CANON.md, and its result lands on the shot's own dialogueLines[].delivery (cb_handover._
# dialogue_lines maps voicePerformances[].elevenLabsV3Direction straight onto it). Asking THIS
# stage to re-derive intention/subtext/cadence from scratch, in its own separate fields nobody
# read (sceneIntention had zero call sites either), was the exact same "rigid structure,
# nothing downstream reads it" pattern already fixed for the other three departments.
class VoiceLineDirection(BaseModel):
    speaker: str
    exactDialogue: str
    performedText: str


class VoiceDirection(BaseModel):
    shotId: str
    lines: List[VoiceLineDirection]
    doesItLand: str = Field(min_length=1)


class AnimationDirection(BaseModel):
    shotId: str
    providerPrompt: str = Field(min_length=40)
    doesItLand: str = Field(min_length=1)


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


class MediaReview(BaseModel):
    artifactType: Literal["keyframe", "animation", "final"]
    verdict: Literal["recommend-approve", "revise", "block"]
    summary: str
    intendedRead: str
    actualRead: str
    finalFrameUsable: bool = False
    recommendedCandidate: Optional[str] = None
    candidateAssessments: List[CandidateAssessment] = Field(default_factory=list)
    findings: List[ReviewFinding] = Field(default_factory=list)


def _system(worker, job):
    return (load_runtime_skill(worker) + "\n\nTHIS RUN:\n" + job +
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
    # THE WHY, RECORDED (2026-07-26, Julian: "all agree how it breaks down AND WHY").
    # firstEventIndex is the single most consequential structural decision in the entire
    # pipeline — every later chair designs INSIDE the beats it creates — and it was the only
    # structural decision in this studio that never had to justify itself. The shot
    # conference has transitionReason and cutPaceReason for far smaller calls. An
    # unjustified boundary is also unreviewable: Julian could see WHAT each beat was and
    # never why it started there, so a wrong cut was invisible until the footage failed.
    boundaryReason: str = Field(min_length=1)
    beatCode: str = Field(min_length=1)
    storyBeat: str = Field(min_length=1)
    want: str = Field(min_length=1)
    need: str = Field(min_length=1)
    kidRead: str = Field(min_length=1)
    adultRead: str = Field(min_length=1)
    emotionalIntent: str = Field(min_length=1)


class EpisodeVisionDirection(BaseModel):
    """Same 14 fields cb_creative.EpisodeVision already defines — reused verbatim (never
    a second vision schema) so an approved candidate here drops straight into
    cb_creative.py's own {episode}_episode_vision.json shape without translation."""
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


class StoryIntakeDirection(BaseModel):
    title: str = Field(min_length=1)
    logline: str = Field(min_length=1)
    leadBear: str = ""
    episodeVision: EpisodeVisionDirection
    beats: List[BeatSplit] = Field(min_length=1)


def prepare_story(script_events, cast_by_scene, *, log=print):
    """The Director's FIRST task on a newly uploaded script (2026-07-19): decide where
    each scene's own beats begin, and author the creative content around them. Scene
    order, characters and every spoken line are LOCKED SOURCE EVIDENCE, supplied here
    only as read-only context for the Director's own understanding — the caller
    (cb_intake.py) re-inserts the exact source text mechanically afterward and never
    trusts this call's own reproduction of it. Deliberately does NOT use the shared _j()
    truncation helper for the script content: cutting the script short here would mean
    the Director never even sees, let alone preserves, everything past the cut."""
    # STEP 1 GETS THE WHOLE ROOM (2026-07-26, Julian: "step 1 has to be done properly...
    # I knew when we were working further down the line the beats weren't landing and now we
    # know why").
    #
    # THE ARCHITECTURAL MISTAKE THIS CORRECTS. This pass decides where EVERY beat begins and
    # ends, and authors want / need / kidRead / adultRead / emotionalIntent for the whole
    # episode — the emotional architecture the rest of the pipeline can only refine inside.
    # It was running on _system("director", ...): the Director's runtime contract and the job
    # text, and nothing else. No show bible. No taste canons. No exemplars. No Showrunner.
    # Then the ten-gate creative room — Showrunner at gates 3, 4 and 5, adversarial review,
    # Producer — convened to design shots INSIDE a shape it had no voice in choosing. The
    # room got stronger as the decisions got smaller, which is backwards: if a beat boundary
    # is wrong or an adultRead is thin, no amount of shot-conference craft recovers it.
    #
    # cb_creative._mind is already the correct room builder — it loads the runtime SKILL
    # contracts for every named chair, their taste canons, the show bible, and the approved
    # exemplars with rejected work marked as failures not to imitate. Reusing it here means
    # ONE room builder for the whole creative pipeline rather than two that drift apart.
    # Imported lazily inside the function: at module scope it would be a cycle.
    from cb_creative import _mind, _characters_for
    return cb_llm.structured(
        _mind("DIRECTOR AND CINEMATOGRAPHER, WITH THE SHOWRUNNER IN THE ROOM",
              ["directorTaste", "cinematographyTaste", "showrunnerTaste"],
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
                "logline and lead bear. Every scene needs at least one beat, and its first "
                "beat's own firstEventIndex must equal that scene's own first event "
                "index. For EVERY beat, state boundaryReason: why the story turns HERE and "
                "not one event earlier or later \u2014 what changes at this exact moment that "
                "makes the previous beat finished. \u2018It felt like a new section\u2019 is not a "
                "reason; \u2018his confidence breaks the instant she stops watching\u2019 is. This is "
                "the one structural decision this pass makes and it is the one every later "
                "chair has to design inside, so it is the one that must justify itself.\n\n"
                "THE CINEMATOGRAPHER IS AT THIS TABLE (2026-07-26). Where a beat begins "
                "decides what can be SEEN of it \u2014 a boundary drawn one event late buries "
                "the visual turn inside the previous beat, and a beat with no visual event "
                "in it cannot be staged, only narrated. He does not design shots here and "
                "there is no camera language in this output. He is accountable for one "
                "thing: that every beat contains something a camera could actually watch "
                "happen, and he says so plainly when a proposed boundary would leave a beat "
                "visually empty or hand the next one a turn that already occurred.\n\n"
                "THE SHOWRUNNER IS IN THIS PASS AND SHE TALKS WHILE THE EPISODE IS BROKEN "
                "DOWN (2026-07-26). This is the most consequential pass in the pipeline — "
                "every later chair designs INSIDE the beats decided here, and a beat "
                "boundary in the wrong place or a thin adultRead cannot be recovered by any "
                "amount of craft downstream. She holds no verdict; nothing waits on her. She "
                "is accountable for three things, on every beat. (1) THE ARC: each beat sits "
                "somewhere on the episode's Five Pillars curve, and the curve must actually "
                "climb, break and settle — two beats at the same energy in a row is a flat "
                "line, and she says so while the boundaries are still movable. (2) THE TWO "
                "DOORS: kidRead and adultRead must be the SAME moment seen twice, never two "
                "separate beats and never parallel tracks — one door open is a note, not a "
                "beat. (3) THIS SHOW, NOT ANY SHOW: run the substitution test on want and "
                "need — if this beat's emotional engine would work unchanged in a different "
                "children's series, it is not authored yet, and she names what THIS cast's "
                "own truth makes it instead. Where a beat already lands she says so and gets "
                "out of the way; where it does not she gives the show-true version of the "
                "same ambition, never the safer one."),
        "SCRIPT EVENTS, IN ORDER — index : scene : type : [speaker :] text (dialogue text "
        "is LOCKED, shown for context only, never to be altered):\n"
        + json.dumps(script_events, ensure_ascii=False, indent=1) +
        "\n\nCAST PRESENT PER SCENE (mechanically detected from the script text):\n"
        + json.dumps(cast_by_scene, ensure_ascii=False, indent=1) +
        # THE PEOPLE THEMSELVES (2026-07-26). Step 1 knew every character's NAME and nothing
        # else about them. It authors want and need for every beat in the episode, and the
        # Showrunner at this table is charged with running the substitution test on exactly
        # those two fields — "would this emotional engine work unchanged in a different
        # children's series" — which is unrunnable without the register it substitutes
        # against. Same empty chair as gate5_performance, one pass earlier and far more
        # consequential: a want authored generically here is inherited by every chair
        # downstream and no amount of craft recovers it.
        "\n\nCHARACTER CANON FOR THE EPISODE'S CAST (acting canon first — these are the "
        "people whose wants and needs you are authoring; the substitution test runs "
        "against THIS):\n"
        + _characters_for(sorted({c for v in (cast_by_scene or {}).values()
                                  for c in (v or [])})) +
        "\n\nReturn the episode vision, a suggested title/logline/leadBear, and the "
        "ordered beat split with creative content for every beat, across every scene.",
        StoryIntakeDirection, label="department_story", log=log)


def _intent_charge(context):
    """THE DIRECTOR'S OWN WORDS, for whichever chair is about to write.

    One reader, deliberately shared by the stage (prepare_cinematography) and the
    performance (prepare_animation) — Julian's ruling is that BOTH prompts are engineered
    from the direction, so both must read it from the same place or they will drift apart
    the first time one is edited. Returns "" when a shot states no intent: silence is
    correct, an invented purpose never is."""
    try:
        import cb_intent
        shot = context.get("shot") if isinstance(context, dict) else None
        return (cb_intent.charge(shot if isinstance(shot, dict) else {}) or "") and \
               (cb_intent.charge(shot) + "\n\n")
    except ImportError:
        return ""


def prepare_look(context, *, log=print):
    return cb_llm.structured(
        _system("cinematography",
                "Write the exact image-provider prompt for this scene's environment-only "
                "Scene Look plate: the place itself — light, palette, material, atmosphere. "
                "No character, no shot composition. Keep it plain and concrete. The plate "
                "must BE the scene canon's own stated environment (its look field), at the "
                "scale and vantage that field states — never a re-imagined alternative to it. "
                "When the scene has a LOCKED library plate (Julian's own lock), that image is "
                "the visual law and this prompt only ever describes THAT world.\n"
                "THE LIGHT LAW (drift-safe vocabulary, 2026-07-24): write light ONLY as concrete sky/sun/shadow states from the scene own authored lighting fields - never time-of-day mood words (sunset, sunrise, dawn, golden-hour, dusk, amber light, pink-orange, warm saturated are banned and refuse the save). The 9-take drift campaign proved time-of-day mood words drag generations away from the locked look; state the light EXACTLY as the scene's own authored lighting field words it (e.g. Scene 1's locked 'low sun just above the hills, long gold light raking the flower tops') and let the plate reference carry the rest — never restate a competing sun position or colour the plate does not show.\n"),
        "APPROVED SCENE CONTEXT:\n" + _j(context) +
        "\n\nReturn the provider prompt, and one plain sentence on whether this place "
        "reads true to the scene.",
        LookDirection, label="department_look", log=log)


def prepare_cinematography(context, images, compiled_brief, *, log=print):
    """THE REGISTER WRITER — STILLS (Gold Build, 2026-07-24, extended to the keyframe path
    the same day Julian caught the pre-Gold sunrise keyframe prompt still standing: "when
    you say you do something ensure that it is worked through front to back"). The
    Cinematographer writes the opening-frame prompt at the same house register as the
    Animation writer, from the same craft curriculum (loaded verbatim), using the still-
    image half of the transfer: [shot size, lens] + subject/action frozen at the story
    instant + depth staging + light + emotional intent. Light obeys THE LIGHT LAW — the
    scene's own drift-safe vocabulary only."""
    return cb_llm.structured(
        _system("cinematography",
                "YOU ARE BUILDING THE STAGE (Julian, 2026-07-25: \"the keyframe gives "
                "the stage which allows the performance to deliver and breathe — but BOTH "
                "those prompts are engineered FROM the director, not the other way "
                "around\"). This frame is not a pretty picture of the beat; it is the "
                "space the performance has to happen IN. Read what the beat is FOR, below, "
                "before you frame anything, then build a frame that AFFORDS it: room to "
                "travel in the direction the action travels, the object the gag needs "
                "actually present and reachable, the character NOT driving the action "
                "given a specific object in frame they are in contact with and working — "
                "an anchor that travels with them, not a spot on the canvas — both "
                "characters placed so the moment can "
                "play, air where the payoff has to land. A frame that is beautiful and "
                "leaves the performance nowhere to go is a failed frame.\n\n"
                "You are the studio's register writer for STILL opening frames. The "
                "attached images are the identity references and scene anchor — look at "
                "them. Below is the house craft curriculum; it is your mind. Write "
                "providerPrompt as one complete opening-frame prompt: shot size + focal "
                "length first, the subjects frozen at the exact story instant (scale "
                "relationship explicit), foreground/midground/background depth staging, "
                "then light, then the emotional read of the frame.\n"
                "THE IDENTITY LAW (Julian's ruling, 2026-07-25 — the proven reference-first "
                "style that produced our best keyframes; reinstated after a described-identity "
                "prompt drifted both characters off-model): NEVER describe a character's "
                "appearance — no body shape, colours, stripes, glasses, cheeks, wings, "
                "features, ever. A name is a label welded to its reference slot, nothing "
                "more. For each character write exactly one identity clause of this shape: "
                "'{Name} is the character from @图N — match the reference 100%, every "
                "feature and accessory exactly as shown' — then spend your words ONLY on "
                "pose, position, action-instant, staging, depth and light. The reference "
                "images carry identity; your text carries the moment. KEEP IT LEAN: the "
                "whole prompt under ~170 words — every word describing what a reference "
                "already shows is a word pulling the render away from that reference.\n"
                "THE LIGHT LAW (drift-safe vocabulary, 2026-07-24): write light ONLY as concrete sky/sun/shadow states from the scene own authored lighting fields - never time-of-day mood words (sunset, sunrise, dawn, golden-hour, dusk, amber light, pink-orange, warm saturated are banned and refuse the save). The 9-take drift campaign proved time-of-day mood words drag generations away from the locked look; state the light EXACTLY as the scene's own authored lighting field words it (e.g. Scene 1's locked 'low sun just above the hills, long gold light raking the flower tops') and let the plate reference carry the rest — never restate a competing sun position or colour the plate does not show.\n"
                "Never write any duration or motion-over-time; this is one frozen "
                "instant. Preserve exact character identity from the references.\n\n"
                "===== THE HOUSE CRAFT CURRICULUM (verbatim) =====\n" +
                _craft_curriculum(None)[0]),
        (_intent_charge(context) or "") +
        "SOURCE MATERIAL — the storyboard-approved facts for this opening frame:\n" +
        compiled_brief +
        "\n\nSHOT AND ORDERED ATTACHMENTS:\n" + _j(context) +
        "\n\nReturn the complete opening-frame prompt as providerPrompt, then one plain "
        "sentence on whether this frame will land the beat.",
        CinematographyDirection, label="department_cinematography", log=log, images=images)


_TAG = re.compile(r"\[[^\]]+\]")
_WORD = re.compile(r"[A-Za-z0-9']+")


def _spoken_words(text):
    return [w.lower() for w in _WORD.findall(_TAG.sub("", text or ""))]


def validate_voice_direction(result, locked_lines):
    got = result.lines
    if len(got) != len(locked_lines):
        raise RuntimeError(f"Voice Director returned {len(got)} line(s); {len(locked_lines)} are locked")
    for idx, (out, locked) in enumerate(zip(got, locked_lines), start=1):
        if out.speaker.strip().lower() != str(locked["speaker"]).strip().lower():
            raise RuntimeError(f"Voice Director changed speaker on line {idx}")
        if _spoken_words(out.exactDialogue) != _spoken_words(locked["exactText"]):
            raise RuntimeError(f"Voice Director changed locked dialogue on line {idx}")
        if _spoken_words(out.performedText) != _spoken_words(locked["exactText"]):
            raise RuntimeError(f"Voice Director added, dropped or changed words on line {idx}")
    return result


def _voice_line_briefs(locked_lines):
    """Each line's own already-approved direction, pulled OUT of the generic shot JSON and
    labelled so it can't be missed. `delivery` is the storyboard's Voice Performance role's
    own V3-tagged performance (cb_creative.gate5_voice, following VOICE_PERFORMANCE_CANON.md
    — intention, subtext, the thought before the line, operative words, tag discipline, all
    already decided there), mapped onto the shot's dialogueLines at promotion time
    (cb_handover._dialogue_lines: elevenLabsV3Direction -> delivery). Before this fix this
    sat unread inside context's buried shot JSON and the LLM re-invented a performance from
    the bare locked words every time — the exact bug this function closes."""
    out = []
    for ln in locked_lines:
        out.append(f'{ln.get("speaker")}: "{ln.get("exactText")}"\n'
                    f'  APPROVED DIRECTION: {ln.get("delivery") or "(none authored yet)"}')
    return "\n".join(out)


def prepare_voice(context, locked_lines, *, log=print):
    """THE DELIVERY-IS-COMPILATION FIX (2026-07-21), same pattern and same day as
    Cinematography/Animation, per Julian's own instruction ("they need to deliver the beat
    through the v3 prompting [emotion] and cadence best practice of which you have the
    documents"): each line's own APPROVED DIRECTION already IS that V3/cadence best
    practice, decided once at storyboard time by the Voice Performance role reading the
    show's own Voice Performance Canon. This stage's job is finalising that direction into
    the literal ElevenLabs V3 string — never re-deciding the performance from scratch."""
    result = cb_llm.structured(
        _system("voice",
                "Each line below already carries its APPROVED DIRECTION — the Voice "
                "Performance role's own V3 tags, cadence and intention, decided once at "
                "storyboard time following the show's Voice Performance Canon. Your job is "
                "to finalise that direction into the exact text ElevenLabs will receive: "
                "real V3 tags, punctuation as cadence, every locked word present and in "
                "order. Do not re-direct the performance — the acting choice is already "
                "made; you are writing it down correctly."),
        "THE SHOT'S LINES, EACH WITH ITS ALREADY-APPROVED DIRECTION:\n" +
        _voice_line_briefs(locked_lines) +
        "\n\nSHOT CONTEXT:\n" + _j(context) +
        "\n\nReturn each line's exact performedText (same order/speaker/words as above), "
        "and one plain sentence on whether this performance will land the beat.",
        VoiceDirection, label="department_voice", log=log)
    return validate_voice_direction(result, locked_lines)


_CRAFT_DIR = pathlib.Path(__file__).resolve().parent.parent / "shows" / "crystal-bears" / "creative"


def _craft_curriculum(primary_form=None, secondary_colour=None):
    """Loads the house craft curriculum VERBATIM (Julian's Gold Build ruling, 2026-07-24:
    everything gold from the AnyFilm transfer goes in whole — "dont kill them with
    straight jackets"; never summarized, never paraphrased). Read fresh on every call so
    an edit to any doc reaches the very next authored card.

    THE EXEMPLAR IS PART OF THE CURRICULUM (Julian's ruling, 2026-07-25 — "ensure that the
    direction and prompts are fired from the right place so we get the level of quality and
    consistency of the lean prompt we had"): SH1_KEEPER_EXEMPLAR.txt is the REAL, verbatim
    prompt that produced the show's first keeper take, proven over eleven live A/B fires.
    Until this ruling the writer was given the LAWS but never the WINNER — rules without a
    worked example, which is exactly how output drifts below the standard it complies with.
    A missing exemplar file degrades gracefully (laws still load) rather than breaking every
    authoring call — but it is loaded whenever present, and it is present."""
    parts = []
    for name in ("PROMPT_CRAFT_STANDARD.md", "PROMPT_CRAFT_SKILL.md"):
        p = _CRAFT_DIR / name
        parts.append(f"===== {name} =====\n" + p.read_text(encoding="utf-8"))
    # THE FORMULA LIBRARY (Julian's ruling, 2026-07-25, superseding the unconditional
    # SH1 attachment): the writer gets the proven formula FOR THE FORM IT IS WRITING, or
    # an honest "no formula exists yet, discover one" — never a shape proven on different
    # material. SH1 is a physical-comedy/action-chain formula; attaching it to a quiet
    # interior beat teaches the writer to fill stillness with impacts, which is precisely
    # the "clunky, scripted, fake" failure this library exists to end.
    block, meta = cb_formulas.formula_block(primary_form, secondary_colour)
    parts.append(block)
    return "\n\n".join(parts), meta


def prepare_animation(context, images, compiled_brief, *, primary_form=None,
                      secondary_colour=None, log=print):
    """THE REGISTER WRITER (Julian's Gold Build ruling, 2026-07-24 — "we are going to be
    brave... build it out properly... only the new way is being created and presented to
    the API", and same day: "the magic is in the prompting, that has to be that way"):
    supersedes both the 2026-07-21 delivery-is-compilation shape and the 2026-07-23
    tempo-map law. The specialist now WRITES the complete formula cinematic prompt at the
    house register — the craft curriculum (PROMPT_CRAFT_STANDARD.md +
    PROMPT_CRAFT_SKILL.md, the AnyFilm-derived transfer, loaded verbatim) is its mind.
    compiled_brief is cb_engine.compile_shot_contract's SOURCE MATERIAL (labelled
    storyboard facts, never pre-written prose). THE SH1 KEEPER STANDARD (Julian's ruling,
    2026-07-25, superseding the S1.SH3-era inline-verbatim-dialogue formula): dialogue
    words NEVER appear in the prompt — @Audio1 is declared the sole source of dialogue,
    wording, voice, performance and timing, and performance is timed by naming the
    audio's own spoken sections. The machine never rewrites or trims what this writes;
    cb_render's formula gate only verifies skeleton, drift vocabulary and the audio-law
    header afterward."""
    # THE FORMULA LIBRARY (2026-07-25): the writer gets the proven formula for THIS
    # beat's dramatic form, or an explicit "no formula yet — discover one". formula_meta
    # travels back to the caller so the fire record can say which formula produced the
    # prompt; that link is what lets the corpus answer "which formulas are working".
    # THE ENGINE SWITCH (Julian, 2026-07-25: "why am i wasting time on the old one if the
    # new one is better"). He was right that proving the OLD author's output is the wrong
    # test when we are replacing the author. The lean engine never needed its own fire
    # path — the gates, the sealed envelope and the spend token are the parts that were
    # already right and are kept. It only replaces WHO WRITES, then hands the prompt to
    # the same door. CB_ENGINE=lean routes the charge through THE LAW (255 words + one
    # worked exemplar) instead of the 6,711-word curriculum. Default stays the old author
    # until real footage says otherwise — smaller is not the same as better, and the lean
    # engine has not yet produced a single frame.
    if os.environ.get("CB_ENGINE", "").strip().lower() == "lean":
        import cb_lean
        curriculum = cb_lean.law()
        ex = cb_lean.exemplar(primary_form or "physical_comedy")
        if ex:
            curriculum += ("\n\n===== A REAL PROMPT THAT PRODUCED AN APPROVED TAKE ON "
                           "THIS KIND OF MATERIAL =====\nStudy its SHAPE and its SPEND, "
                           "then write THIS shot. Do not copy its content.\n\n" + ex)
        formula_meta = {"engine": "lean", "primaryForm": primary_form}
    else:
        curriculum, formula_meta = _craft_curriculum(primary_form, secondary_colour)
    # THE DIRECTOR'S OWN WORDS LEAD HER OWN BRIEF (2026-07-25). She stated what this beat
    # is FOR at the storyboard; under the old chair table that intent went to a different
    # department who never saw it. Same chair now, so it travels with her.
    # THE SAME READER THE STAGE USES (_intent_charge) — one source, so the keyframe and
    # the clip can never be engineered from different readings of the same direction.
    curriculum = (_intent_charge(context) or "") + curriculum
    result = cb_llm.structured(
        _system("animation",
                "YOU ARE THE DIRECTOR. Not a prompt technician, not a compliance "
                "checker — the person who staged this shot and is now directing the "
                "performance in it. Pete Docter's chair, with Glen Keane at your "
                "shoulder on weight, appeal and the illusion of life.\n\n"
                "THE FIRST IMAGE IS YOUR STAGE. You set that canvas knowing the "
                "performance you were about to direct — the space to travel, the "
                "object to hit, the room to bank. Now direct the performance it was "
                "built to hold. The keyframe is the stage; this prompt is the "
                "performance.\n\n"
                "WHAT YOU ARE ACTUALLY MAKING is a beat that lands — funny where it "
                "should be funny, felt where it should be felt. Physics, camera and "
                "continuity are how you deliver that. They are never the point. A "
                "shot that satisfies every law and does not land is a failed shot, "
                "and you are the one who would pull it.\n\n"
                "Below is the house craft curriculum — your training, not your "
                "brief. Write at its full level.\n\n"
                "THE FORMULA (structural law — the only fixed skeleton; THE SH1 KEEPER "
                "STANDARD, Julian's ruling 2026-07-25 — see the worked exemplar in the "
                "curriculum below):\n"
                "1. If any dialogue exists, the prompt OPENS with the audio law: "
                "'ENGLISH DIALOGUE ONLY, spoken in English. Use @Audio1 as the sole "
                "source of dialogue, wording, voice, performance and timing.' Name who "
                "speaks and who stays silent (mouth closed); ban additional SPEECH. "
                "NOT a ban on vocal sound (2026-07-26, GAP 6 — the deletion this audit "
                "names): 'vocalisations' banned the show's own voice. Fuzzby hums "
                "continuously through all of Scene 1 and the hum is not a dialogue line; "
                "Squeaky has no voiceId at all and her entire vocal identity is 'quick "
                "chirps and clicks', so that one word made her mute. A hum, chirp, gasp "
                "or breath the shot's own performance calls for is DIRECTED, not "
                "forbidden. DIALOGUE WORDS NEVER APPEAR IN THE PROMPT — time the "
                "performance by naming the audio's own sections ('During the opening "
                "spoken section of @Audio1...', 'As the final spoken section of @Audio1 "
                "begins...').\n"
                "2. Then THE REFERENCE-ROLE LINE — one sentence scoping every reference "
                "to a single job with 'only': @图1 only for the exact opening "
                "composition and positions; one @图N only for each character's identity, "
                "proportions, features and accessories; one only for the world.\n"
                "3. Then 'Shot 1:' — and 'Cut to. Shot N:' for each internal cut, in the "
                "source material's own order. Each shot: camera + lens + one continuous "
                "movement concept first ('Begin exactly on @图1.'), then action as "
                "PHYSICAL CAUSE AND VISIBLE CONSEQUENCE — named contacts, objects acting "
                "on characters, connected structures declared one flexible physical unit "
                "before they flex, involuntary motion stated as involuntary ('a "
                "passenger, not a performer'). NEVER abstract geometry (degrees, screen "
                "direction, spatial bookkeeping) and never scaffolding that restates the "
                "world — speed is proven by consequences, never asserted. THE ANCHOR "
                "LAW: a stationary character is welded to a named physical object "
                "('whenever her flower bends or moves, she travels physically with it'), "
                "never a position — BUT ONLY FOR A CHARACTER THE BEAT HAS DECIDED IS "
                "STAYING PUT. It was being applied as a default safety measure and "
                "pinned characters the story needed travelling (S1.SH2, 2026-07-25). When "
                "the beat moves a character, they MOVE. Never anchor anyone merely to "
                "keep them safely in frame.\n"
                "3b. ONE GEOGRAPHY PER CHARACTER. A character is either held to a named "
                "object or travelling — never written as both. 'Anchored to her flower' "
                "plus 'hovers beside him' is a contradiction, and a model resolves a "
                "contradiction by taking the safest reading, which is always less motion. "
                "Decide, then say it once.\n"
                "3d. THE CARD'S STASIS WORDS ARE NOT YOUR PROMPT'S STASIS WORDS. The "
                "SOURCE MATERIAL below describes the storyboard's intent in the "
                "storyboard's own vocabulary, and that vocabulary contains framing locks "
                "— 'holds a two-shot, unbroken', 'camera locked', 'stays near-motionless "
                "and flat through both lines'. Copying those into the prompt is how a "
                "beat dies: the model obeys them literally for the whole span they "
                "govern, and the span is usually the dialogue, which is most of the "
                "clip. Read them for what they MEAN — she must not be dropped from the "
                "beat, he must not go quiet, the two of them must both stay readable — "
                "and deliver that meaning through staging, eyeline and depth instead. "
                "You are the Director. Where the card's wording and the beat's landing "
                "pull apart, you resolve it toward motion, and you name what you chose "
                "in doesItLand so it is visible rather than silent.\n"
                "3c. STASIS VERBS ARE COMMANDS, NOT SAFETY. settle, hold, anchor, steady, "
                "still, motionless, remain, stay, locked, two-shot — the model obeys every "
                "one literally. Write them ONLY where stillness is the actual dramatic "
                "intent. Repeating a framing lock does not make a shot safer; it makes "
                "stillness its dominant instruction. The approved keeper runs about 2 such "
                "terms per 100 words; at 3+ you are directing a held pose no matter what "
                "your action sentences say.\n"
                "4. HOW THE SHOT STOPS IS THE CARD'S DECISION, NOT A DEFAULT "
                "(2026-07-25). Read the source material's own 'ends by:' line and "
                "obey it. reaction_hold / living_hold -> write the closing HOLD "
                "sentence: 'Hold on ... for two seconds after the audio finishes "
                "... Silence.' — the FINAL two seconds ONLY, the shot in motion "
                "right up to it. continue_in_motion / cut_on_action -> DO NOT write "
                "a hold at all; the clip ends mid-movement, energy unspent, and a "
                "beat that stops dead when the card asked it to carry is a WRONG "
                "ending. visual_transition -> the closing image becomes the way "
                "into the next shot, no stillness beat. NOTHING DECLARED (a legacy "
                "card) -> default to the two-second hold and nothing more.\n"
                "WHY THIS IS NOT FREE: our relay hands a shot's FINAL FRAME to the "
                "next shot as its opening, so a shot ending mid-motion hands over a "
                "motion-blurred anchor. continue_in_motion / cut_on_action suit a "
                "scene's LAST shot, or one whose successor opens on its own fresh "
                "setup — never a blanket preference. AnyFilm run a universal 2s "
                "hold on 84% of clips and name it their own weakness "
                "('artistically limiting — flattens emotional variety'); Pixar vary "
                "0s to 7s by emotional need. Vary it where the card says to and the "
                "chain allows. The hold, when written, is still the clean-frame "
                "harvest window.\n"
                "5. NEVER write any duration into the prompt (the API parameter carries "
                "it); the only sanctioned time phrase is the closing hold's own 'two "
                "seconds' (either wording in rule 4).\n"
                "6. Light is written ONLY in the source material's SET & LIGHT LAW "
                "vocabulary — concrete sky/sun/shadow states; time-of-day words "
                "(sunset, golden-hour, dusk, amber light) are banned and refuse the "
                "save.\n"
                "7. THE IDENTITY LAW (Julian's ruling, 2026-07-25 — the proven "
                "reference-first style; a described-identity prompt drifted both "
                "characters off-model): NEVER describe a character's appearance — no "
                "body shape, colours, fur, stripes, glasses, goggles, cheeks, wing "
                "look, features, ever. Declare identity ONCE per character as a "
                "reference lock — '{Name} is the character from @图N — match the "
                "reference 100%, every feature and accessory exactly as shown' — then "
                "write ONLY action, physicality-in-motion (squash, stretch, momentum, "
                "recovery), staging, depth, light and performance. The references carry "
                "what they look like; your words carry what they DO.\n"
                "8. THE SIZE LAW, AS SPEND (Julian's rulings, 2026-07-25 — 'look at the "
                "other prompts from AnyFilm', then the SH1 keeper): leanness is zero "
                "wasted words, not a number. The AnyFilm band (~250-350 per clip, "
                "delivered average 244; ~90-120 per shot) is the TARGET for a "
                "single-gag shot. A multi-beat physical-chain shot with dialogue-sync "
                "sections may run longer — but know the real numbers before you "
                "spend: AnyFilm DELIVERS 244 words per clip; this studio's own run "
                "722-810. Measured, that gap is not extra physics — it is "
                "continuity safeguards, restated framing locks and repeated "
                "stillness language, the exact material that made a shot read as "
                "immobilised. Past ~350 words the question is no longer 'does this "
                "buy physics' (anything passes that) but 'which of these sentences "
                "did I add because I was worried'. Cut those.\n"
                "THERE IS NO WORD CEILING (2026-07-25, Julian: \"remove a lot of the "
                "guardrails that suffocate the creative prompting\"). Every numeric cap "
                "this studio ever set was later found cutting the wrong thing — most "
                "recently a physics description truncated to its flatter half to fit a "
                "budget. The proven keeper is 722 words — the best take so far, not "
                "the ceiling of the craft, and still 3x what AnyFilm delivers. No "
                "cap; no prize for length either. "
                "Write what the shot needs.\n"
                "USE ANY CAMERA OR LIGHT VOCABULARY THE SHOT ACTUALLY CALLS FOR — focal "
                "length, lens character, rim light, backlight, depth, atmosphere. Nothing "
                "is banned. Reach for a technical term when it is the most precise way to "
                "say what you mean, and plain physical description when that is; the test "
                "is always whether the word makes the image more specific, never whether "
                "it appears on some approved list.\n\n"
                "NOW THE ONLY THING THAT ACTUALLY MATTERS. You are not filling in a "
                "template — you are the last filmmaker between a storyboard and a "
                "finished shot, and this is the only place the audience will ever meet "
                "this moment. Before you write a word, answer for yourself: what does "
                "this shot DO to someone watching it? What do they feel at the first "
                "frame, what changes in them by the last, and which single physical "
                "moment carries that change? Then write the shot that delivers exactly "
                "that — the performance with real weight and real timing, the camera "
                "behaving like someone who cares what happens, light that belongs to this "
                "moment and no other. The Showrunner, the Director and the DP have "
                "already decided WHAT this shot is. Your job is to make it ARRIVE — with "
                "the specificity and the nerve of someone who has watched it in their "
                "head and knows precisely why it lands.\n\n"
                "===== THE HOUSE CRAFT CURRICULUM (verbatim) =====\n" +
                curriculum),
        "SOURCE MATERIAL — the storyboard-approved facts. Write the card FROM these: "
        "invent cinematic craft freely, never new story facts:\n" + compiled_brief +
        "\n\nSHOT, VOICE DIRECTION AND ORDERED ATTACHMENTS:\n" + _j(context) +
        "\n\nReturn the complete formula prompt as providerPrompt, then one plain "
        "sentence on whether this clip will land the beat.",
        AnimationDirection, label="department_animation", log=log, images=images)
    # Attach the provenance without touching the schema: which formula (if any) was in the
    # writer's mind for this card. Read back by cb_render at fire time for the corpus.
    try:
        setattr(result, "_formula", formula_meta)
    except Exception:
        pass
    return result


def review_media(artifact_type, context, images, *, log=print):
    if artifact_type not in ("keyframe", "animation", "final"):
        raise ValueError("artifact_type must be keyframe|animation|final")
    return cb_llm.structured(
        _system("post" if artifact_type == "final" else "review",
                "Run dailies review on visible evidence. Findings are advice for Julian, "
                "never an automatic approval, rewrite or generation instruction."),
        "REVIEW TARGET AND APPROVED INTENT:\n" + _j({**context, "artifactType": artifact_type}) +
        "\n\nUse orderedReviewImages in the context to distinguish the actual rendered "
        "evidence (chronological where there are several frames) from its identity and "
        "Scene Look references.",
        MediaReview, label=f"department_review_{artifact_type}", log=log, images=images)
