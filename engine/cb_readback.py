#!/usr/bin/env python3
"""cb_readback.py — READ THE PROMPT BACK BEFORE YOU PAY FOR IT.

Julian, 2026-07-27, after I diagnosed a bad keyframe by reading its own prompt aloud to him:

    "i cant nor do i have the technical ability to read the prompt, but you just did and
     you conveyed it to me in a manner that makes sense and was right — my question is why
     cant what you just done now looking at the prompt and understanding the shot be done
     at the point of writing the prompt so we get the right shot... prevention is the best
     form of cure."

He is right, and the honest answer is that this studio has been building the wrong kind of
check for five weeks. Every existing guard is a LINT: it matches words. Does the text contain
"specular"? Does it contain a banned adjective? Is it over N words? That is not reading.

BOTH of the day's real failures were CONTRADICTIONS, and a contradiction is invisible to word
matching because NEITHER CLAUSE IS WRONG:

    "wide shot, 24mm"            +  "a specular ping on a spectacle lens"
    "match the reference 100%,      +  "roughly one-sixth of frame height"
     every feature exactly"

Each phrase passes every lint this codebase owns. Together they cannot both be obeyed in one
frame, and the model resolves them the same way every time — toward the detail, because
detail is concrete and scale is hedged. The result is a portrait where a corridor was asked
for, twice in one morning, at $0.14 and a real amount of Julian's patience each time.

WHAT THIS IS NOT
----------------
It is NOT A GATE, and that is not a technicality. CLAUDE.md rule 87 is unambiguous:

    "CREATIVE OVER CONSTRAINTS. DELIVERY OF THE DIRECTOR'S GUIDANCE OVER CONTROL... A new
     gate, a new negative, a new law, a new refusal, a new word cap, a new lint is NOT the
     answer here — that direction was tried for weeks and the footage got worse."

So this refuses nothing, blocks nothing, scores nothing and edits nothing. It reads the
prompt and says, in plain English, which two instructions are fighting and which one the
render will obey. Julian decides. A reading is not a rail.

It is also NOT the retired intent judge (rule 87, e0e6bd9). That asked "is this prompt
FAITHFUL to the director's stated intent" and measured INVERTED against the real corpus —
it scored the two rejected prompts 10/10 and the approved keeper lowest, because echoing the
director's words back is high textual fidelity and is exactly what makes a prompt laboured.
This asks a different question with no such failure mode: CAN ONE FRAME SATISFY ALL OF THIS
AT ONCE? That is a question about physics and optics, not taste. Restating the intent more
loudly does not make a prompt more internally consistent, so the inversion that killed the
judge cannot arise here.

    python3 cb_readback.py <scene> <shotId> [episode]      # read the live approved direction
"""
import json
import os
import sys
from typing import List, Literal

from pydantic import BaseModel, Field

import cb_llm

HERE = os.path.dirname(os.path.abspath(__file__))


class Clash(BaseModel):
    """One pair of instructions that cannot both be obeyed."""
    first: str = Field(description="The first instruction, quoted from the prompt, short.")
    second: str = Field(description="The second instruction, quoted from the prompt, short.")
    why: str = Field(description="One plain sentence: why one frame cannot do both. No jargon.")
    wins: str = Field(description="Which one the render will actually obey, and why.")
    cost: str = Field(description="What the director will see on screen as a result. Concrete.")


class Mismatch(BaseModel):
    """One thing the brief says that the APPROVED PICTURE does not show. This is the class of
    failure that produced the corridor take: the brief was written from the shot's paperwork
    while the approved frame showed something else entirely, and the render got fragments of
    both. It is a question of FACT — the picture is attached, look at it."""
    prompt_says: str = Field(description="What the brief says, quoted, short.")
    frame_shows: str = Field(description="What you can actually SEE in the attached approved "
                                         "picture instead. Describe it plainly.")
    why_it_matters: str = Field(description="One plain sentence on what breaks. No jargon.")
    cost: str = Field(description="What the director will see on screen. Concrete.")


class ReadBack(BaseModel):
    # ORDER IS REASONING ORDER — the same law that fixed both authoring chairs. The eyes
    # must LOOK at the picture and find the internal fights BEFORE they are allowed to say
    # whether it delivers; a verdict written first becomes a thing the evidence is bent to fit.
    shot_says: str = Field(description="In one plain sentence, what this brief will actually "
                                       "produce — as a person would describe what they see.")
    frame_mismatches: List[Mismatch] = Field(
        default_factory=list,
        description="Things the brief states that the ATTACHED APPROVED PICTURE contradicts. "
                    "Empty list when the brief genuinely starts from the picture — that is a "
                    "good and common answer. Only report what you can actually SEE.")
    clashes: List[Clash] = Field(
        default_factory=list,
        description="Pairs INSIDE the brief that cannot both be obeyed. Empty list if there "
                    "are none. Never invent one.")
    craft_notes: List[str] = Field(
        default_factory=list,
        description="At most three short plain-English notes on whether this brief is built "
                    "the way this studio's proven prompts are built — one physical cause "
                    "relayed into consequences, no stop/park commands, a task rather than a "
                    "state for anyone holding still. Empty when it reads clean. NEVER a note "
                    "about length.")
    delivers: Literal["delivers", "partly", "will-not"] = Field(
        description="Your recommendation to the director, and the ONLY place you give one. "
                    "'delivers' — this starts from the approved picture and will land the "
                    "beat. 'partly' — it will produce something usable but a named thing will "
                    "be missing or wrong. 'will-not' — a mismatch or clash above is fatal and "
                    "he will not get the shot he asked for. Base it ONLY on the evidence you "
                    "listed above; never on taste, never on how the writing reads, and never "
                    "on how long it is.")
    verdict: str = Field(description="One or two plain sentences to the director, in his own "
                                     "language, saying whether to fire this and why. He does "
                                     "not read prompts and should not have to — this sentence "
                                     "is what he acts on. No jargon, no prompt vocabulary.")


_SYSTEM = """You are a cinematographer reading a still-image brief back to a director who
cannot read prompts and does not want to. Your whole job is to catch, BEFORE the render is
paid for, the one failure that keeps happening: two instructions in the same brief that
cannot both be obeyed in a single frame.

THIS IS THE FAILURE, TWICE, FROM ONE REAL MORNING:

  1. "WIDE SHOT, 24mm" together with "spectacles catching a hard specular ping in
     three-quarter profile" and "the fur between his wings". At 24mm from that distance
     none of that detail exists. The render abandoned the wide and came in close to deliver
     it. The director asked for a corridor and got a portrait.

  2. "match the reference 100%, every feature and accessory exactly as shown" together with
     "a small dark silhouette-and-attitude read, roughly one-sixth of frame height". At a
     sixth of frame height a character is a silhouette; you cannot also show every feature.
     The render made him three times the stated size to satisfy the identity clause.

Notice what BOTH have in common: each clause is perfectly reasonable alone. Nothing is
misspelled, banned or badly written. They are only impossible TOGETHER. That is the only
thing you are looking for.

HOW TO READ:
- Find the stated shot size and focal length first. Everything else is judged against it.
- Ask of every descriptive detail: at that distance, is this physically resolvable?
- Ask of every absolute ("100%", "exactly", "every"): does it fight a stated scale, distance
  or framing?
- Ask: is the space the action needs actually left empty, or has it been filled?
- When two clauses fight, say which one the render will obey. The concrete and absolute
  beats the hedged and abstract, every time. "exactly" beats "roughly".

RULES:
- Report ONLY genuine impossibilities. A brief with no clash gets an empty list, and that is
  a good and common answer. Inventing a clash to look useful is the worst thing you can do —
  it teaches the director to ignore you.
- Never rewrite the prompt. You are not a gate; the director fires whatever he wants, and a
  bad recommendation from you costs him a shot he should have taken.
- Write for someone who has never read a prompt. No jargon, no lists of terms. Say what they
  will SEE.
"""

# THE APPROVED PICTURE IS ATTACHED — LOOK AT IT (2026-07-27, Julian: "i really need a strong
# pair of eyes that understands the beat, the prompting lean structure, and ensures it
# delivers based on the stage, the keyframe and the desired directors outcomes").
#
# Until this, these eyes read only TEXT. That is why they could not have caught the failure
# they were built for: the brief and the approved frame were each internally coherent and
# described two different shots. Nothing in words alone reveals that. The picture does.
_LOOK_AT_IT = """
AN APPROVED PICTURE IS ATTACHED TO THIS MESSAGE. LOOK AT IT FIRST, BEFORE YOU READ A WORD OF
THE BRIEF. It is not a mood reference and not one input among several — it is the SIGNED,
LOCKED visual truth of this shot, and the brief's whole job is to start from it and move.

THIS IS THE REAL FAILURE IT EXISTS TO CATCH, FROM ONE REAL MORNING:
  The approved frame showed two characters hovering side by side, facing camera, at the same
  distance, in an open sunlit meadow with sky above them.
  The brief described a chase from behind one of them, low, inside a narrow corridor of
  towering flowers, with the second character a speck far away at the limit of focus.
  Both were perfectly reasonable on their own. The render received two different shots and
  produced fragments of each: it opened in a corridor with a photoreal insect, then snapped
  to the right character halfway through. The director's beat did not land at all.

WHAT TO CHECK AGAINST THE PICTURE, EVERY TIME:
- THE PLACE. Open or enclosed? What is overhead? How far can you see? If the picture is an
  open field and the brief says corridor, tunnel, canopy or ceiling, that is a mismatch — and
  it is the single most common one.
- WHO IS IN IT. Every character you can see in the picture should be accounted for in the
  brief. A character visible in the approved frame and absent from the brief's opening is a
  mismatch.
- WHERE THEY ARE. Left/right, high/low, near/far. A brief that reverses the picture's own
  screen positions, or that starts BEHIND a character the picture shows facing camera, is a
  mismatch. Camera side is not a detail; it is the whole shot.
- THEIR SIZE RELATIVE TO EACH OTHER. If the picture shows them at the same distance so their
  real size difference reads, a brief that pushes one far into the distance destroys the one
  thing that frame was built to establish.
- THE LIGHT. Direction, time of day, quality. A brief that contradicts it is a mismatch.

DO NOT accept "begin exactly on the reference" as resolving any of this. A brief can say that
sentence and then describe a different shot for the next four hundred words; the render obeys
the description, not the promise. Judge what the brief actually DESCRIBES.

DO NOT report a mismatch for something the picture simply cannot show — what happens next,
motion, sound, or anything outside the frame. The picture is frame zero only.
"""

# THE BEAT, AND THE WAY THIS STUDIO'S GOOD PROMPTS ARE ACTUALLY BUILT. Both measured, both
# from the real corpus (CLAUDE.md rule 87) — and the length finding is stated as a PROHIBITION
# on remarking, because every automated measure this studio ever built that keyed on length
# scored its own approved keeper worst.
_CRAFT = """
YOU ALSO KNOW HOW THIS STUDIO'S PROVEN PROMPTS ARE BUILT. Its own approved take and its
rejected ones were measured against each other, and these are the findings that held:

- LENGTH IS NOT THE VARIABLE, AND YOU MUST NEVER REMARK ON IT. The approved keeper ran 722
  words; a rejected one ran 716. Six words apart, opposite outcomes. Every measure this studio
  built that keyed on length rated its own best work worst. Do not mention word count, do not
  say a brief is long or short, do not suggest trimming. It is not evidence of anything.
- STOP-COMMAND DENSITY IS THE VARIABLE. The approved keeper contained ONE phrase telling
  something to stop, hold, freeze, park or stay still. The rejections contained nine and ten.
  A character who is not travelling needs a continuous named TASK plus small corrections —
  never a state word like "flat", "motionless" or "barely moves", which the model obeys
  literally and renders as a freeze.
- ONE PHYSICAL CAUSE, RELAYED. The strongest briefs name one cause and let every later event
  be its consequence, the object of one sentence becoming the subject of the next. Needing
  "then" or "meanwhile" to join two events is the proof the chain is broken — that is two
  shots, not one.
- THE BIGGEST MOVEMENT BELONGS INSIDE THE DIALOGUE, never finish-the-action-then-park-to-talk.

Report at most three of these, only when you actually see them, in plain words. They are
craft observations, not faults — a brief can be worth firing with all three present.

TWO MORE KINDS OF CLASH, BOTH FOUND IN REAL FIRED PROMPTS — treat these as clashes, not
craft notes, because each one has a wrong answer the render will actually pick:

- SOUND AGAINST SOUND. A brief that says one sound "runs unbroken" and later says "Silence"
  is asking for both across the same seconds. This exact pair shipped. Read every sound
  instruction against every other one and against the hold at the end.
- TOO MANY EVENTS FOR THE SECONDS. This is the one that matters most and it is easy to miss,
  because no single sentence is wrong — the fault only exists in the total. COUNT the
  distinct physical events the brief asks for: every named contact, every change of
  direction, every camera move, every state change of a body or an object. Then divide the
  stated duration by that count. Under half a second per event, the model cannot stage them
  and will keep the two or three it can hold and silently drop the rest — usually the
  middle of the chain, which is usually the joke. When you find this, say so plainly, give
  the count and the seconds, and NAME THE EVENTS YOU WOULD CUT FIRST: always decoration
  (lens swipes, camera flourishes, light description, a glance) before story (a contact, a
  consequence, a physical cause). Never propose cutting WORDS — this studio measured that
  and its own approved keeper was one of its longest briefs. Events, not length.
"""


def _intent_block(intent):
    """The Director's own stated outcome for this beat, when the shot carries one. Silence is
    correct when it does not — an invented purpose is worse than none, and the eyes must never
    grade a brief against an outcome nobody actually asked for."""
    intent = (intent or "").strip()
    if not intent:
        return ""
    return ("\n\nWHAT THE DIRECTOR ASKED THIS BEAT TO DO — HIS OWN WORDS. This is the outcome "
            "the brief exists to deliver. Judge delivery against THIS, never against your own "
            "idea of a good shot:\n" + intent + "\n")

# THE TAKE'S OWN LENS (2026-07-27, Julian: "when you ask me to approve direction im not the
# techy guy — you have the context and the rational to ensure the prompt is right and will
# deliver the performance on the stage"). The still lens above asks "can ONE FRAME hold all
# of this at once", and for a keyframe that is the whole question. A take is fifteen seconds
# of MOTION, and its impossibilities are different in kind — not "does this detail resolve at
# this distance" but "can the body be in two places", "does the camera have to be still and
# moving in the same second", "is there time for all of this".
#
# A still and a take have OPPOSITE relationships with length: more words in a take buy
# performance over time; more words in a still crowd one image until the lens collapses. So
# this lens must never inherit the still lens's suspicion of detail — it is looking for
# CONTRADICTION, never for abundance.
_TAKE_LENS = """
THIS BRIEF IS FOR A MOVING TAKE OF ABOUT FIFTEEN SECONDS, NOT A STILL. Judge it as motion.

The impossibilities you are looking for are different in kind:
- One body asked to be in two places, or to do two things, in the same moment.
- A camera asked to hold locked and to move at the same time.
- More events named than can physically happen in the seconds available — not "this is a lot
  of writing", but "these specific actions cannot fit end to end in the time given".
- An instruction to hold a pose or stay still sitting next to an instruction to travel.
- A physical chain whose links don't connect — an effect named before its own cause.

WHAT IS NOT A CLASH, AND YOU MUST NOT REPORT IT AS ONE:
- Length. A long brief is not a fault. More words buy performance over fifteen seconds; this
  studio's own approved takes are among its longest briefs. Never remark on the word count.
- Detail. Naming a small physical beat is direction, not contradiction.
- Repetition of a character's name, or a reference tag appearing more than once.
Report a pair only when obeying BOTH is physically impossible in one continuous take.
"""


def read_back(prompt_text, *, shot_id="", form="still", images=None, intent="",
              log=print, model=None):
    """One read. Returns a ReadBack, or None if the model is unreachable — this must never
    be the reason a director cannot get on with their day.

    form="still" is the keyframe lens (shot size vs resolvable detail, the two real failures
    quoted in _SYSTEM). form="take" swaps in the motion lens above. A form this doesn't
    recognise falls back to the still lens rather than refusing — a reading is advisory, and
    an unknown stage is a reason to read differently, never a reason not to read at all.

    images is the APPROVED PICTURE this brief must start from — the keyframe for a take, the
    plate for a still. When present the eyes can SEE; when absent they degrade to the old
    text-only read rather than refusing, and report no frame mismatches at all, because a
    mismatch they cannot see is one they must not claim.

    intent is the Director's own stated outcome for the beat, or "".

    ON THE VERDICT FIELD, HONESTLY (2026-07-27): this module's own header says it "scores
    nothing", and that clause is superseded here by Julian's direct instruction — "i dont
    want to be the guy reading the direction, i really need a strong pair of eyes that
    understands the beat, the prompting lean structure, and ensures it delivers based on the
    stage, the keyframe and the desired directors outcomes." A reading he still has to
    interpret puts him back in the chair he asked to leave.

    The risk is named rather than hidden. The retired intent judge (rule 87) was killed for
    scoring and it measured INVERTED — it rated the two REJECTED prompts 10/10 and the
    APPROVED keeper lowest, because restating the director's words back is high textual
    fidelity and is exactly what makes a prompt laboured. This verdict is grounded where that
    one was not: a PICTURE it can actually look at, plus contradictions that are questions of
    physics. That is a real difference in kind. It is also still unproven, and it stays
    advisory in the only way that matters — Approve is never disabled by it, and no code
    anywhere reads this field to decide anything."""
    if not (prompt_text or "").strip():
        return None
    take = (form or "").strip().lower() == "take"
    seen = [p for p in (images or []) if p and os.path.exists(p)]
    system = _SYSTEM + (_TAKE_LENS if take else "") + (_LOOK_AT_IT if seen else "") + _CRAFT
    unit = "one continuous take" if take else "one frame"
    user = (f"The brief below is for shot {shot_id}. It has not been rendered yet — nothing "
            f"has been spent.\n\n"
            + ("The APPROVED, SIGNED-OFF picture this brief must start from is attached. "
               "Look at it before you read a word of the brief.\n" if seen else
               "No approved picture is available for this shot, so leave frame_mismatches "
               "EMPTY — never guess at one you cannot see.\n")
            + _intent_block(intent)
            + f"\nTell me what I will actually get, whether the brief contradicts the "
              f"picture, whether any two instructions in it cannot both be obeyed in {unit}, "
              f"and whether to fire it.\n\n"
              f"--- THE BRIEF ---\n{prompt_text}\n--- END ---")
    try:
        return cb_llm.structured(system, user, ReadBack,
                                 model=model or getattr(cb_llm, "VALIDATOR_MODEL", None),
                                 label="readback", log=log, images=seen or None)
    # SystemExit IS THE ONE THIS HAD TO CATCH (2026-07-27, found the hard way). cb_llm raises
    # SystemExit on any provider failure — deliberately, so a real authoring run stops loudly
    # rather than degrading. SystemExit inherits from BaseException, NOT Exception, so the
    # original `except Exception` here read as total coverage and caught nothing that actually
    # happens. A provider overload during an ADVISORY reading then took down a writer call
    # that had already succeeded: 920 words, real money, discarded because the optional second
    # opinion could not be obtained. That is the exact inversion this module's whole design
    # forbids. KeyboardInterrupt is deliberately NOT caught — Ctrl-C must still stop the run.
    except (Exception, SystemExit) as e:        # noqa: BLE001 — advisory, never load-bearing
        log(f"[readback] could not read this brief back ({e}) — this blocks nothing")
        return None


_VERDICT_HEAD = {"delivers": "FIRE IT", "partly": "IT WILL PART-LAND",
                 "will-not": "DON'T FIRE THIS YET"}


def as_plain_text(rb):
    """The director's own view. Written to be read out loud, not parsed. The recommendation
    leads, because the whole point is that he should not have to work it out himself."""
    if rb is None:
        return "Could not read this brief back — nothing is blocked by that."
    out = [_VERDICT_HEAD.get(rb.delivers, rb.delivers.upper()),
           "  " + rb.verdict, "",
           "WHAT YOU WILL GET", "  " + rb.shot_says, ""]
    if rb.frame_mismatches:
        n = len(rb.frame_mismatches)
        out += [f"{n} thing{'' if n == 1 else 's'} the brief says that your approved frame "
                f"does NOT show:", ""]
        for i, m in enumerate(rb.frame_mismatches, 1):
            out += [f"  {i}. The brief says: {m.prompt_says}",
                    f"     Your frame shows: {m.frame_shows}",
                    f"     {m.why_it_matters}",
                    f"     So you will see: {m.cost}", ""]
    if rb.clashes:
        n = len(rb.clashes)
        out += [f"{n} thing{'' if n == 1 else 's'} in here cannot both happen:", ""]
        for i, c in enumerate(rb.clashes, 1):
            out += [f"  {i}. “{c.first}”",
                    f"     versus “{c.second}”",
                    f"     {c.why}",
                    f"     The render will obey: {c.wins}",
                    f"     So you will see: {c.cost}", ""]
    if not rb.frame_mismatches and not rb.clashes:
        out += ["It starts from your frame and nothing in it fights itself.", ""]
    if rb.craft_notes:
        out += ["On how it's built:"] + [f"  · {n}" for n in rb.craft_notes] + [""]
    return "\n".join(out)


if __name__ == "__main__":
    import cb_render
    scene, shot = sys.argv[1], sys.argv[2]
    ep = sys.argv[3] if len(sys.argv) > 3 else "Ep1"
    d = cb_render.department_status(scene, shot, ep, "cinematography")
    rec = (d.get("approved") or d.get("candidate") or {})
    text = ((rec.get("output") or {}).get("providerPrompt") or "")
    if not text:
        print("No cinematography direction on record for that shot.")
        sys.exit(1)
    print(as_plain_text(read_back(text, shot_id=shot)))
