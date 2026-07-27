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
from typing import List

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


class ReadBack(BaseModel):
    shot_says: str = Field(description="In one plain sentence, what this prompt will actually "
                                       "produce — as a person would describe the picture.")
    clashes: List[Clash] = Field(description="Pairs that cannot both be true in one frame. "
                                             "Empty list if there are none. Never invent one.")


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
- Never rewrite the prompt. Never score it. Never say whether it is good. You are not a
  judge and you are not a gate; the director decides everything.
- Write for someone who has never read a prompt. No jargon, no lists of terms. Say what they
  will SEE.
"""

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


def read_back(prompt_text, *, shot_id="", form="still", log=print, model=None):
    """One read. Returns a ReadBack, or None if the model is unreachable — this must never
    be the reason a director cannot get on with their day.

    form="still" is the keyframe lens (shot size vs resolvable detail, the two real failures
    quoted in _SYSTEM). form="take" swaps in the motion lens above. A form this doesn't
    recognise falls back to the still lens rather than refusing — a reading is advisory, and
    an unknown stage is a reason to read differently, never a reason not to read at all."""
    if not (prompt_text or "").strip():
        return None
    take = (form or "").strip().lower() == "take"
    system = _SYSTEM + _TAKE_LENS if take else _SYSTEM
    unit = "one continuous take" if take else "one frame"
    user = (f"The brief below is for shot {shot_id}. It has not been rendered yet — nothing "
            f"has been spent.\n\nRead it and tell me what I will actually get, and whether "
            f"any two instructions in it cannot both be obeyed in {unit}.\n\n"
            f"--- THE BRIEF ---\n{prompt_text}\n--- END ---")
    try:
        return cb_llm.structured(system, user, ReadBack,
                                 model=model or getattr(cb_llm, "VALIDATOR_MODEL", None),
                                 label="readback", log=log)
    except Exception as e:                      # noqa: BLE001 — advisory, never load-bearing
        log(f"[readback] could not read this brief back ({e}) — this blocks nothing")
        return None


def as_plain_text(rb):
    """The director's own view. Written to be read out loud, not parsed."""
    if rb is None:
        return "Could not read this brief back — nothing is blocked by that."
    out = ["WHAT YOU WILL GET", "  " + rb.shot_says, ""]
    if not rb.clashes:
        out += ["Nothing in this brief fights itself.", ""]
        return "\n".join(out)
    n = len(rb.clashes)
    out += [f"{n} thing{'s' if n > 1 else ''} in here cannot both happen:", ""]
    for i, c in enumerate(rb.clashes, 1):
        out += [f"  {i}. “{c.first}”",
                f"     versus “{c.second}”",
                f"     {c.why}",
                f"     The render will obey: {c.wins}",
                f"     So you will see: {c.cost}", ""]
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
