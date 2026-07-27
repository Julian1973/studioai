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


# THE SHOT PANEL — JULIAN'S OWN NUMBERS AND NAMES, AND WHICH SECTION AUTHORISES WHAT
# (2026-07-26, the UI/engine reconciliation; UI_MUST_MATCH_THE_PROCESS.md).
#
# THE DEFECT THIS CLOSES. The engine was restructured over weeks and cb-studio/app.html was
# patched at its edges instead of reconciled with it. Section "02 · OPENING FRAME" offered a
# Generate (fire) button and NO prepare/approve path for the direction the engine demands
# behind it — so the only button that section showed could only ever refuse. Julian hit that
# wall twice ("im lost", "i cant go back") and was unblocked from the command line, which is
# a workaround, not a fix. Sections 04 and 05 had grown their own inline authorisation rows;
# 02 never did. Three sections, three different shapes.
#
# WHY THIS TABLE IS IN THE ENGINE AND NOT IN app.html. The last time this project shipped two
# tables for one truth (the chair tables) they drifted apart within a day and a test had to be
# written to bind them — test_studio_chair_table.py exists because of it. A hardcoded stage
# list in app.html is exactly that mistake again. This is the one table; the panel reads it,
# the refusal messages read it, and the test binds both to it.
#
# THE NAMES ARE JULIAN'S, NOT THE ENGINE'S (his own correction: "please refer to the numbers
# and the real stage names, stage three is opening frame"). `stage` here is an implementation
# detail — an engine key — and it must never reach a human. Everything a person reads comes
# from `number` and `name`.
#
#   stage      — the engine department key this section is gated by (None = no gate).
#   authorises — this is THE section where that stage's direction is prepared and approved.
#                A section may be gated by a stage it does not authorise (07 · FIRE spends on
#                the animation direction that 05 · DIRECTION authorises); such a section must
#                send the human to the authorising one by NAME, never leave them guessing.
SHOT_PANEL = [
    {"number": "01", "name": "STORYBOARD", "rowId": "storyboard",
     "stage": None, "authorises": False},
    {"number": "02", "name": "OPENING FRAME", "rowId": "frame",
     "stage": "cinematography", "authorises": True},
    {"number": "03", "name": "SPECIAL REFERENCES", "rowId": "refs",
     "stage": None, "authorises": False},
    {"number": "04", "name": "VOICE", "rowId": "voice",
     "stage": "voice", "authorises": True},
    {"number": "05", "name": "DIRECTION", "rowId": "direction",
     "stage": "animation", "authorises": True},
    {"number": "06", "name": "PROMPT", "rowId": "prompt",
     "stage": None, "authorises": False},
    {"number": "07", "name": "FIRE", "rowId": "fire",
     "stage": "animation", "authorises": False},
    {"number": "08", "name": "REVIEW", "rowId": "review",
     "stage": None, "authorises": False},
]


def panel_section(stage):
    """The ONE section a human prepares and approves `stage` in, or None."""
    for sec in SHOT_PANEL:
        if sec["stage"] == stage and sec["authorises"]:
            return sec
    return None


def panel_label(stage):
    """What a human calls this stage on their own screen — '02 · OPENING FRAME'.

    Falls back to the engine key only when a stage has no section at all, which is itself a
    reconciliation failure the studio-chair test refuses to let ship."""
    sec = panel_section(stage)
    return f'{sec["number"]} · {sec["name"]}' if sec else str(stage)


def authorising_stages():
    """Every engine stage a shot panel section actually authorises, in panel order.

    The one list any caller may iterate — serve.py's endpoints and the Studio's own rows all
    read this rather than re-typing ('cinematography', 'voice', 'animation') for the fourth
    time, which is how the two sides drifted apart in the first place."""
    return [s["stage"] for s in SHOT_PANEL if s["authorises"] and s["stage"]]


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
    """WORK THE SHOT OUT BEFORE YOU WRITE IT (2026-07-27).

    Julian, after I diagnosed two bad keyframes by reading their own prompts back to him:
    "surely the prompt needs to take into it the context and outcomes with common sense and
    creative reasoning — you just broke that prompt down as an expert and understanding the
    demands of the shot, surely that is what fires when you take the shot direction."

    He is right, and the schema was the reason it didn't. The field order WAS
    shotId -> providerPrompt -> doesItLand: the model went straight to writing prose, and
    `doesItLand` sat AFTER it, so whatever reflection happened arrived once the prose was
    already committed and could not change a word of it. A real DP does not open their mouth
    first; they work out the frame, then describe it.

    Structured output is generated IN FIELD ORDER, so `frameLogic` sitting above
    `providerPrompt` is not decoration — it forces the reasoning to happen first and then
    constrains the prose that follows it. Both of the day's real failures were contradictions
    this working-out cannot survive: you cannot write "at 24mm a spectacle ping is not
    resolvable" and then ask for one four lines later.

    This is not a gate (rule 87). Nothing is refused, scored or capped. The room got a
    thinking step it never had."""

    shotId: str
    frameLogic: str = Field(min_length=1, description=(
        "THE STAGING DECISION — THE DIRECTOR AND THE DP, IN THE ROOM, BEFORE ANY PROMPT "
        "EXISTS. This is not notes about a prompt you have already written; it is the "
        "creative decision the prompt will then merely DELIVER. Nothing you write in "
        "providerPrompt may contradict what you settle here.\n\n"
        "THE DIRECTOR SPEAKS FIRST, and in plain human words — no prompt language, no "
        "camera jargon yet:\n"
        "(1) WHAT IS THIS FRAME FOR? What does the audience feel in the first half-second "
        "they see it — the laugh being set up, the heart being reached for, the trouble "
        "being promised? Say it as you would to a person, not a machine.\n"
        "(2) WHAT MUST THIS FRAME AFFORD? The performance lands ON this stage and has "
        "fifteen seconds to do its job. Name the room it needs: the air the action travels "
        "into, the object it arrives at, the space the joke needs to be legible in. That "
        "space is the point of the frame, not the background to it.\n\n"
        "THE DP ANSWERS, and only now does craft enter:\n"
        "(3) The shot size and focal length that SERVES (1) and (2) — chosen for them, never "
        "chosen first and justified after.\n"
        "(4) At that size, what is genuinely resolvable on the characters, and what is NOT. "
        "If the honest answer is 'silhouette, posture and colour, not features', say so "
        "plainly — that is then the whole of your job on them, and every line you write "
        "afterwards must respect it.\n\n"
        "Then write providerPrompt as pure DELIVERY of this decision — no new choices, "
        "nothing invented that is not settled above. If while writing you find yourself "
        "reaching for something you named unresolvable, do not write it and do not quietly "
        "drop the shot size to accommodate it: the decision above is the one that stands. "
        "A frame that is beautiful and leaves the performance nowhere to go is a failed "
        "frame, however well it is written."))
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


# THE TAKE STARTS FROM THE PICTURE, NOT FROM THE PAPERWORK (Julian, 2026-07-27, finding the
# thing four days of fixes had walked past): "If the direction is written before the keyframe,
# then it's going to contradict everything it's done, and this is a perfect example. The
# keyframe is Fuzzby and Zenny quite high up in the meadow, but obviously the direction is
# completely different. The direction really needs to be able to look at the keyframe to be
# able to start the direction from that moment."
#
# The ordering was never the bug — _anchor_for already refuses to prepare a take without an
# APPROVED keyframe, and on the failing shot the keyframe was approved at 07:47:33 and the
# direction at 07:51:25, four minutes later, with that exact picture attached as @图1. The
# writer HAD it. It just had nowhere to look at it. It went straight to providerPrompt and
# wrote from the shot's paperwork, which says rainforest and corridor, and "corridor" landed
# in the fired prompt five times over an open sunlit meadow.
#
# CinematographyDirection got frameLogic on 2026-07-26 for exactly this reason — a required
# field ABOVE the prose, because in a structured output FIELD ORDER IS REASONING ORDER: what
# sits above providerPrompt must be resolved before a word of prose exists. The take chair
# never got its equivalent. This is it, and it is deliberately a READ, not a plan: the writer
# is not asked what it INTENDS, it is asked what is ACTUALLY THERE.
class AnimationDirection(BaseModel):
    shotId: str
    openingFrameRead: str = Field(min_length=1, description=(
        "LOOK AT @图1 BEFORE YOU WRITE ANYTHING. This is the APPROVED opening frame — the "
        "literal first frame of the take you are about to write, already signed off. It is "
        "not a mood reference and not one input among several: it is where the fifteen "
        "seconds BEGIN, and every word you write after this must be able to start from it. "
        "Describe what you can SEE in it, in four parts, in this order:\n"
        "(1) WHAT KIND OF PLACE IS THIS? Open or enclosed, how far you can see, what is "
        "overhead, what is underfoot, what the light is doing. Take it from the PICTURE. If "
        "the shot's own paperwork calls the place something the picture plainly is not — a "
        "corridor, a rainforest, a tunnel, a canopy — say so here in plain words, and then "
        "write the picture, never the paperwork. This is the single most common way a take "
        "fails: the frame shows a meadow and the words build a tunnel.\n"
        "(2) WHERE IS EACH CHARACTER IN IT? Position in frame, how high, how far from the "
        "lens, and CRUCIALLY their size relative to each other as the frame actually shows "
        "it. If they are at the same distance, say so — that is what makes the size "
        "relationship readable, and it is fragile. A take that pushes one of them far into "
        "the distance destroys it.\n"
        "(3) WHAT DOES THIS FRAME AFFORD? The stage has to be flexible enough for the "
        "performance to take place. Name the room that is actually there — where there is "
        "air to move into, what is close enough to be hit or landed on, which directions are "
        "open. You are not free to invent room the picture does not have.\n"
        "(4) WHERE DOES IT GO? Name where the take ENDS UP — a place, a state, a position "
        "this opening frame could not have shown you. If you cannot name one, the take has "
        "not moved and you have written a held pose.\n"
        "Then write providerPrompt as the fifteen seconds that begin in THIS frame and "
        "travel to THAT ending. Nothing in the prose may contradict what you just described "
        "seeing."))
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
                "chair has to design inside, so it is the one that must justify itself. "
                # CITE THE EVENT, DON'T JUST ARGUE (2026-07-26). Found by measurement, not
                # preference: in a blind A/B of this pass, one author habitually named the
                # numbered event it was ruling against ("starting at event 12 would miss
                # the instant Fuzzby pauses") and the other argued the same point in prose
                # alone. Checked all 13 citations against the real parse — 13/13 landed on
                # a real event, in the right scene, saying what was claimed. That is the
                # difference between a boundary you can AUDIT and one you can only admire,
                # and it is a technique, not a property of any one model — so it belongs in
                # the charge where every author has to do it.
                "CITE THE EVENT INDEX YOU ARE RULING AGAINST. A boundary reason that names "
                "the specific alternative — 'starting at event 12 would miss the instant he "
                "pauses' — can be checked against the script by anyone. One that only "
                "argues well cannot. Name the index; be falsifiable.\n\n"
                # THE THREE THINGS FIVE BLIND JUDGES FOUND (2026-07-26). Two real
                # breakdowns of this same script were read blind by five independent
                # reviewers. The verdict mattered less than the defects: each author had a
                # different one, and both are avoidable at authoring time, which is where
                # compliance is PRODUCED rather than policed. Measured on the real pair:
                # 18 instructional NEEDs in one, 4 audience-effect claims and 2 off-screen
                # images in the other. lint_breakdown.py is the advisory backstop; this is
                # the fix.
                "THREE THINGS THAT WEAKEN A BEAT, AND HOW TO WRITE INSTEAD.\n"
                "(1) NEED IS A LACK THE CHARACTER IS CARRYING, NEVER A LESSON THEY OUGHT TO "
                "LEARN. A need a character does not yet know they have cannot be phrased as "
                "an obligation they should meet. 'He needs to accept that a plan can fail' "
                "is a curriculum objective wearing his name — it would work unchanged in any "
                "preschool show, and a beat sheet written that way pushes every chair "
                "downstream toward lesson delivery. 'He needs her to keep watching' is a "
                "lack. Test it: could this exact sentence sit in a different series with a "
                "different cast? Then it is not authored yet.\n"
                # CORRECTED SAME DAY (2026-07-26), on the first real run under this rule.
                # The first wording said "point at the frame and say what is IN it" and the
                # room did precisely that — and stopped saying what the visible thing MEANS.
                # Measured on the same moment: "Nothing glows. She hands over grief
                # disguised as equipment" became "The bezels are empty, and she holds her
                # paws closed around his." The second is true, checkable, and something a
                # four-year-old already sees — the adult door had closed. The ban was always
                # on claiming the ROOM'S REACTION, never on meaning. CREATIVE OVER
                # CONSTRAINTS: a rule that produces a flatter beat is the wrong rule, and
                # this one was mine.
                "(2) adultRead IS THE SECOND DOOR ONTO THE SAME MOMENT — anchor it to "
                "something visible, then SAY WHAT THAT VISIBLE THING MEANS. Both halves are "
                "required. The anchor is what stops it floating free of the beat; the "
                "meaning is the entire reason the field exists. 'Nothing glows — she is "
                "handing over grief disguised as equipment' does both. 'The bezels are "
                "empty' is only the anchor, and it tells an adult nothing the child has not "
                "already seen. What you must NOT do is claim how the room will react: "
                "'every parent watching has stood on that pier' is unfalsifiable and it is "
                "marking your own homework. Say what the moment MEANS; let the room have its "
                "own reaction to it.\n"
                "(3) NEVER NAME WHAT THE CAMERA CANNOT SEE. 'A mother standing on a dock "
                "just outside the frame' is a lovely line and a real production hazard — "
                "somebody downstream will try to board it. If it matters, it is on screen; "
                "if it is not on screen, it is not in the beat.\n\n"
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
                "them.\n"
                # THE PLATE GOVERNS THE WORLD (2026-07-27, Julian: "it has to be the scene
                # plate reference" / "ensure this is now the workflow for the keyframes —
                # taking the director's view, looking at the context of the scene plate and
                # the flexibility of the shot").
                #
                # Earned the hard way. Four keyframes in one morning came back as a dark
                # enclosed rainforest tunnel while the real plate is an open sunlit
                # wildflower field. Cause: the plate had been scoped to PALETTE ONLY — the
                # DP's own reference line read "@图4 only for the world — corridor palette,
                # flower and leaf materials, sky and sun state" — so the picture that defines
                # the world got a vote on tint, and invented prose ("corridor", 0 uses in the
                # script, 48 in the storyboard) got the vote on architecture. Architecture
                # won every time. The plate is not a swatch; it IS the place.
                "THE PLATE IS THE WORLD — READ IT BEFORE YOU WRITE A WORD. The scene anchor "
                "is not a colour swatch and not a mood board. It decides WHAT KIND OF PLACE "
                "THIS IS: the space, the light, how open or closed it is, how far you can "
                "see, what is underfoot and overhead. Take those from the picture, not from "
                "your own vocabulary. If the plate is an open sunlit field, you may not "
                "build a corridor, a tunnel, a canopy or a ceiling in words — and if a word "
                "from the scene's own paperwork describes a different kind of place than the "
                "plate shows, THE PLATE WINS and you say nothing about the place at all "
                "beyond what it already shows. Your words are for what the plate cannot "
                "know: where the characters are in it, at what scale, at what instant.\n"
                "THE DIRECTOR'S VIEW COMES FIRST, THE CRAFT SERVES IT. Settle what the "
                "audience should FEEL in the first half-second and what the frame must "
                "AFFORD the performance landing on it (frameLogic), and only then choose "
                "shot size and lens to serve that. Never choose the lens first and justify "
                "it after.\n"
                "LEAVE THE SHOT FLEXIBLE. This frame is where fifteen seconds of performance "
                "BEGINS, so it must survive being moved: characters readable with real air "
                "around them, at a depth where their scale relationship to each other can "
                "actually be seen, and nothing pinned so precisely that the first second of "
                "motion contradicts it. Two characters at wildly different distances cannot "
                "show the audience which of them is bigger — if that relationship matters "
                "here, stage them where it reads; if it does not, this frame is not the place "
                "to establish it.\n"
                "Below is the house craft curriculum; it is your mind. Write "
                "providerPrompt as one complete opening-frame prompt: shot size + focal "
                "length first, the subjects frozen at the exact story instant (scale "
                "relationship explicit), foreground/midground/background depth staging, "
                "then light, then the emotional read of the frame.\n"
                "THE IDENTITY LAW (Julian's ruling, 2026-07-25 — the proven reference-first "
                "style that produced our best keyframes; reinstated after a described-identity "
                "prompt drifted both characters off-model): NEVER describe a character's "
                "appearance — no body shape, colours, stripes, glasses, cheeks, wings, "
                "features, ever. A name is a label welded to its reference slot, nothing "
                "more. For each character write exactly one identity clause, and SIZE THE "
                "FIDELITY CLAIM TO YOUR OWN SHOT, because an absolute one fights your lens:\n"
                "  · where the character is large enough in frame for features to resolve — "
                "'{Name} is the character from @图N — match the reference 100%, every "
                "feature and accessory exactly as shown'\n"
                "  · where they are NOT — a wide, a deep background, anything you have just "
                "worked out reads as silhouette — '{Name} is the character from @图N — match "
                "the reference; at this size that is silhouette, proportion and colour, not "
                "features'\n"
                # WHY THIS IS SIZED NOW (2026-07-27). The absolute form was mandated at EVERY
                # shot size, and it is the root of the second contradiction of the day: the DP
                # correctly worked out in frameLogic that "what is NOT resolvable is
                # expression, eye direction, mouth shape, fur detail, or any facial read at
                # all — so I do not write one", and then this template obliged it to demand
                # "every feature and accessory exactly as shown" four lines later. The render
                # obeyed the absolute over the hedge, every time, and put Fuzzby at ~45% of
                # frame height where the brief asked for one-sixth. The model never had a
                # choice; our own charge took it away.
                # RULE 5 IS UNTOUCHED AND UN-REOPENABLE: identity still comes ONLY from the
                # reference image, a name is still a label welded to its @图N slot, and
                # describing a character's appearance is still forbidden in both branches.
                # What changed is a claim about RESOLUTION, not about identity — and at a
                # wide, "silhouette, proportion and colour" is not a weaker instruction, it
                # is the true one.
                " — then spend your words ONLY on "
                "pose, position, action-instant, staging, depth and light. The reference "
                # THE LAST NUMERIC CAP ON THE STAGE, DELETED (2026-07-26, Julian: "now we
                # have the level of directing that gets delivered without the guardrails").
                # The performance chair retired its own ceiling on evidence — the approved
                # SH1 keeper runs 722 words and a rejected take runs 716, six words apart
                # with opposite verdicts, so length never separated them; stop-command
                # density did. This chair kept "~170 words" and was the only numeric cap
                # left on the direction -> image -> video path, which is the exact stage
                # Julian names as the weak one. Honest limit, stated rather than papered
                # over: that measurement came from MOTION prompts, so it does not by itself
                # prove a still-image cap wrong. What decides it is his own standing ruling
                # — the stage exists to AFFORD the performance, and a frame that is correct
                # and leaves the performance nowhere to go is a failed frame. A number
                # cannot tell you which words those were. The DISCIPLINE is kept verbatim;
                # only the number is gone.
                "images carry identity; your text carries the moment. LEANNESS IS ZERO "
                "WASTED WORDS, NOT A NUMBER — there is no word ceiling here. Every word "
                "describing what a reference already shows is a word pulling the render "
                "away from that reference, so cut those without mercy; but never cut a word "
                "that is doing real work on pose, position, action-instant, staging, depth "
                "or light to hit a length.\n\n"
                # WRITE ONLY WHAT YOUR OWN LENS CAN SEE (2026-07-27). Julian, on the first
                # keyframe fired after the ~170-word cap came off: "the image is awful...
                # surely this shot is to narrow." Root-caused, not guessed. The cap was
                # deleted on real evidence — but every word of that evidence came from
                # MOTION prompts (the approved 722-word keeper is a Seedance brief with
                # fifteen seconds to execute it), and rule 87 flagged in the same breath
                # that it "does not by itself prove a still-image cap wrong." It didn't.
                # A still and a take have OPPOSITE relationships with length: more words in
                # a take buy more performance delivered over time; more words in a still buy
                # more detail crammed into one image, and the lens collapses inward to fit
                # them. The cap had been quietly doing a second job — with 170 words there
                # was no ROOM to describe an eyelash, so the stage got the words by default.
                # Removing it did not free the stage; it let the performance move in.
                # The replacement is a rule of KIND, not COUNT, and it is self-enforcing:
                # you cannot overspend on detail without contradicting your own lens.
                "WRITE ONLY WHAT YOUR OWN LENS CAN ACTUALLY SEE. Name the shot size and "
                "focal length first, then describe nothing the audience could not resolve "
                "at that distance. A 24mm wide from bee-height CANNOT show a specular ping "
                "on a spectacle lens, an open mouth mid-word, or the fur between a "
                "character's wings — write those and the render will quietly abandon your "
                "wide and come in close to deliver them, and you will get a portrait where "
                "you asked for a corridor. If the moment genuinely needs that detail, you "
                "chose the wrong lens; change the lens on purpose. At a wide, a character "
                "is a SILHOUETTE, an ATTITUDE and a POSITION IN SPACE — that is the whole "
                "of your job on them, and it is enough.\n\n"
                "EXPRESSION, EYELINE, MOUTH SHAPE, ANTENNA CARRIAGE AND WING-BEAT ARE THE "
                "PERFORMANCE, AND THE PERFORMANCE IS NOT YOURS. It has fifteen seconds to "
                "arrive; you have one frame. Hand it the stage and get out of its way.\n\n"
                # THE FORGIVING START FRAME (Julian, 2026-07-27, in his own words: "the
                # keyframe is the stage the canvas for the animation to build on — it has to
                # be the forgiving start frame"). This is a rule about COMMITMENT, not
                # detail, and it is the other half of the lens rule above. A frame pinned to
                # one hyper-specific instant — an exact roll angle, a precise mid-upstroke,
                # antennae streaming at a stated attitude — is not a canvas, it is a
                # sculpture, and every frame of motion after it reads as a DEPARTURE from
                # something the model was told to honour. That is the documented anti-hold
                # failure (rules 26/31) arriving through the still instead of the text.
                "BUILD A FORGIVING START FRAME — A CANVAS, NOT A SCULPTURE. The animation "
                "builds ON this frame, so it must survive being moved. Do not freeze a "
                "once-only instant the performance then has to escape: give a READABLE "
                "ATTITUDE the motion can continue out of, not a pinned pose it must first "
                "undo. Leave the lane the action travels into genuinely EMPTY — if the beat "
                "climbs frame-left, that air is not yours to decorate. Keep the character "
                "off the very edge and out of the exact centre so there is somewhere to go "
                "in both directions. The test is simple: could the first second of movement "
                "start from this frame without contradicting it? If the honest answer is "
                "no, you have composed a poster, and the performance will have to break "
                "your frame before it can begin. "
                "The frame has to AFFORD the performance that "
                "lands on it: room to travel where the action travels, the object the beat "
                "needs actually present, both characters placed so the moment can play. A "
                "frame that is beautiful, correct and leaves the performance nowhere to go "
                "is a failed frame, however few words built it.\n"
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
                # THE SAME LAW THE KEYFRAME GOT, ARRIVING HERE ELEVEN HOURS LATE
                # (2026-07-27, Julian, watching the first take off the fixed keyframe: "the
                # scene doesnt deliver"). prepare_cinematography was given THE PLATE IS THE
                # WORLD that morning; this chair — the one that writes the fifteen seconds —
                # was not, and nothing here ever said the pictures outrank the paperwork. The
                # take fired at 07:56 says "corridor" FIVE times and "ceiling" TWICE, off an
                # opening frame that is an open sunlit field, and the words won: the first
                # second of footage is a dirt path between walls of flowers. A rule that
                # governs the still and not the motion is not a rule, it is a coin toss over
                # which chair happens to write the sentence that survives.
                "THE PICTURES ARE THE WORLD — READ THEM BEFORE YOU WRITE A WORD. @图1 and "
                "the world reference are not colour swatches and not mood boards. Between "
                "them they decide WHAT KIND OF PLACE THIS IS: the space, the light, how "
                "open or closed it is, how far you can see, what is underfoot and overhead. "
                "Take all of that from the pictures, never from your own vocabulary. If they "
                "show an open sunlit field, you may not build a corridor, a tunnel, a canopy "
                "or a ceiling in words — not once, and not as scene-setting before the "
                "action starts. If a word from the shot's own paperwork describes a "
                "different kind of place than the pictures show, THE PICTURES WIN and you "
                "say nothing about the place beyond what they already show. Your words are "
                "for what a still cannot hold: what MOVES, what it moves against, and what "
                "that movement does to everything it touches.\n"
                "AND THE SHOT MUST TRAVEL. @图1 is where the fifteen seconds BEGIN, never "
                "where they live. If the frame at the end could be mistaken for the frame at "
                "the start, nothing happened — the take has to end somewhere the opening "
                "frame could not have shown you.\n"
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
