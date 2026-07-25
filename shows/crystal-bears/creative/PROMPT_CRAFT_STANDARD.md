# THE PROMPT CRAFT STANDARD — the house writing level (Julian's ruling, 2026-07-24)

Julian, reviewing AnyFilm's complete Scene 1-10 clip prompts against ours: *"this is the
level of direction craft and production we need. You need to write to this level. We have
to be more creative, we have to be better, we have to be AAA Pixar. These prompts deliver."*

This document is that ruling made permanent. It is derived from the 48 captured, delivered
AnyFilm clip prompts (the footage Julian rated AAA) and applies to EVERY prompt written in
this studio from now on — hand-written tonight, compiled by Brick 1 tomorrow, authored by
the Creative Room's shot gate forever. A prompt that doesn't meet this standard is not
finished.

## The ten components — every shot carries all of them

1. **The camera line, with intent.** Size, focal length, movement — and the movement means
   something: "slow push-in" = revelation, "crane up" = scale shift, "handheld with subtle
   drift" = nervous energy. Never a bare "static" without the stillness doing a job.
2. **Physical, cause-and-effect action prose.** One cause with visible consequences —
   "clips a broad leaf — FWIP — bounces off it, tumbles, then catches himself." Sound
   design written INTO the picture in caps (FWIP, THUP, RUMBLE) at the exact story moment.
3. **Depth staging, named.** Foreground / midground / background each given content:
   "Foreground: massive dewy petals frame the shot in soft bokeh. Midground: two tiny
   buzzing shapes... Background: deep jungle layers recede into misty green-blue haze."
4. **Light as the narrative clock.** Every shot states the light AND its movement — colour
   temperature is story state: "Cool blue-grey begins to creep into the edges of the
   frame's colour temperature." The storm turn is told by light, shot by shot.
   **OUR ONE AMENDMENT (the surviving law):** the light states are written in our proven
   vocabulary — concrete sky/sun/shadow states, never time-of-day words. The drift-vocab
   gate stands; everything else in this standard is unrestricted.
5. **Render craft language.** Catchlights in every close-up ("specular catchlights dance
   in his pupils"), rim light, subsurface scattering through petals/wings, bokeh quality,
   bounce light with a named source ("soft bounce light from a nearby yellow petal warms
   her face from below").
6. **Micro-performance — tells, not labels.** Feelings shown as physical behaviour: "She
   tries to keep a straight face. Fails slightly at the corner of her mouth." / "his wings
   beat just a little faster than normal." / "One eye twitches slightly."
7. **The emotional-intent sentence.** Each shot closes by naming what the shot MEANS:
   "The contrast between their two flight styles tells the entire relationship." /
   "The scale shift — from intimate comedy to vast approaching danger — is breathtaking."
8. **Editorial rhyming.** When a framing repeats, say so: "Same framing as shot 9." A
   returned setup with changed emotion is a cut that edits itself.
9. **Beats written as beats.** "Beat. She studies him." / "One beat. Two beats." Comic
   and dramatic timing lives in the prose, not in luck.
10. **Structure — what is LAW and what is merely usual.**

    LAW (a prompt that breaks these does not fire, and there is no override): when the
    shot has dialogue, the prompt opens with the `ENGLISH DIALOGUE ONLY` header, declares
    `@Audio1` the sole source of dialogue, wording, voice, performance and timing — and
    the spoken words THEMSELVES NEVER APPEAR. See THE SH1 KEEPER STANDARD below.

    ⚠ SUPERSEDED 2026-07-25: this component previously read "dialogue inline,
    verbatim-locked, AFTER the action that earns it." That was the pre-keeper form. It is
    now the exact opposite of the law and is corrected here rather than only further down
    the page, because you are reading this document as your mind and a reader who stops
    at this line would be told the reverse of the truth.

    USUAL, NOT LAW (2026-07-25, Julian: "remove a lot of the guardrails that suffocate
    the creative prompting"): `Shot N: ...` labelling · `Cut to.` transitions · the HOLD
    tail · duration kept out of the text. These are how most shots come out and they are
    reported as advisories if absent — but a single unbroken take with no labels, or a
    shot that ends in motion because that is what the moment wants, is a legitimate
    answer and will fire.

## Reference points — NOT budgets, and NOT a ceiling
~90-120 words per shot, ~250-350 per clip (AnyFilm's delivered average: 244; the best of
theirs run long — richness beats brevity at this altitude). The proven keeper here is 722
words and every one buys physics.

There is NO word ceiling in the engine (2026-07-25). Every numeric cap this studio set was
later found cutting the wrong thing — the last one truncated a physics description to its
flatter half to fit a budget. These numbers are here so you know what good work has
weighed, never so you can be refused for missing them. Write what the shot needs.

## Enforcement path
- Tonight: hand-written prompts are checked against the ten components before save.
- Brick 4 / Creative Room: this document's ten components go verbatim into the shot-
  authoring gate's system prompt so every future card is BORN at this level.
- The only word-level guard that survives on top: `_DRIFT_VOCAB_RE` (component 4's
  amendment). Nothing else in this standard is ever enforced by truncation or strip —
  richness is the product (the No-Straitjacket Law).

---

# THE SH1 KEEPER STANDARD (Julian's ruling, 2026-07-25 — "use this as the standard for all our prompts... anyfilm is the formula in terms of lean prompting")

Proven the hard way: eleven live A/B fires on S1.SH1 in one session (Julian authoring,
each fired verbatim, each judged on real footage). The winner — the FINAL HYBRID below —
beat every heavier, more prescriptive variant, and the variant that replaced its physics
with geometry (v4: "180-degree U-turn", "screen direction reverses") lost the pace, the
turnaround AND the crash in one take. These laws supersede the corresponding parts of the
ten components above; everything not amended stands.

## The laws the winner proved

1. **THE AUDIO-ONLY DIALOGUE LAW** (supersedes component 10's "dialogue inline, verbatim").
   Dialogue words NEVER appear in the prompt. The header declares `@Audio1` as *the sole
   source of dialogue, wording, voice, performance and timing*, names who speaks and who
   stays silent ("mouth closed"), and bans additional vocalisations. Performance is timed
   by naming the audio's own sections: "During the opening spoken section of @Audio1..." /
   "As the final spoken section of @Audio1 begins...".
2. **THE REFERENCE-ROLE LINE.** One sentence scoping every reference to a single job with
   "only": @图1 *only* for the exact opening composition and positions; one @图N *only*
   for each character's identity, proportions, features and accessories; one *only* for
   the world. (THE IDENTITY LAW stands: never describe appearance — the reference carries
   what they look like, the words carry what they DO.)
3. **THE ANCHOR LAW** (kills the Zenny-teleport). A stationary character is welded to a
   named physical object, never a position: "Whenever her flower bends or moves, Zenny
   travels physically with it." The model cannot re-invent what is physically attached.
4. **THE PHYSICS-SPEND LAW** (the core finding — it is not word *count*, it is word
   *spend*). Every sentence is a physical cause with visible consequences: named contacts
   ("his shoulder glances from one stem, knocking him sideways"), objects acting on
   characters ("the final leaf bends beneath him and redirects him through one broad
   horseshoe curve"), never abstract geometry (degrees, screen direction, spatial
   bookkeeping) and never scaffolding that restates the world. Speed is proven by its
   consequences (contacts, wakes, bending stems), never asserted.
5. **THE CONNECTED-SPRING LAW.** Any structure that must flex is declared one connected
   physical unit before it acts: "The petal, flower head and stem remain visibly connected
   as one flexible physical structure" — then it can load, rebound and launch believably.
6. **PASSENGER, NOT PERFORMER.** Involuntary motion is stated as involuntary: "his limbs
   loose and his wings helpless — he is a passenger, not a performer." Emotion is written
   as observable physical events (the honest blink, the closed-mouth sigh, the smallest
   wry smile), never labels.
7. **THE HOLD TAIL, WIDENED.** The clip still ends on a held clean-frame harvest window,
   in the winner's own wording: "Hold on ... for two seconds after the audio finishes ...
   Silence." (The older "about 2 seconds of silence" form remains valid.)
8. **THE SIZE LAW, RESTATED AS SPEND.** The AnyFilm band (~250-350, delivered average 244)
   remains the target for a single-gag shot. A multi-beat physical-chain shot with
   dialogue-sync sections may legitimately run longer — the winner is 722 words and every
   one of them buys physics — but a word spent on geometry, scaffolding, appearance or
   restated world is wrong at ANY length. Leanness = zero wasted words, not a number.

## The worked exemplar — S1.SH1's keeper prompt, verbatim

(The full text lives at `shows/crystal-bears/creative/SH1_KEEPER_EXEMPLAR.txt` and is the
approved recipe for S1.SH1. Study its shape: header → reference roles → shot line →
anchor law → physical chain out → object-driven turnaround → connected-spring crash →
involuntary somersaults → lucky landing → astonishment-to-pose → deadpan close → hold.)

---

# WHAT ANYFILM ACTUALLY TOLD US (2026-07-25 — from their own answers to our 10 questions)

Their full verbatim answers are at `anyfilm_reference/ANYFILM_ANSWERS_10Q_20260725.md`.
They were received on 2026-07-25 and — honestly — sat unread in a chat log while this
studio kept building. These are the four findings that bear on every prompt written here.

## 1. THEY HAVE NO CONTINUITY STATE MACHINE. WE BUILT ONE, AND IT IS WHERE OUR
##    PROMPTS GET HEAVY.

In their own words, what is **NOT** present in their pipeline:

> ❌ No `previousClipEndState` field · ❌ No `carryOverProps` · ❌ No explicit state machine

Continuity instead comes from **explicit callback language inside the action prose** —
their examples: *"still dusted in pollen"*, *"same close-up setup"*, *"wristbands now set
with"*. One short phrase, carried in the sentence that is already describing the action.

We generate structured continuity and expand it into dedicated safeguard sentences —
anchors, held two-shots, position locks. That is a real part of why our prompts run 722-810
words against their delivered 244, and it is exactly the material an external craft review
identified as making a shot read "dramatically immobilised".

**THE RULE:** carry state in ONE short callback phrase inside the action sentence. Never a
paragraph of continuity insurance. If a state matters, name it once, in passing, while
something is happening.

## 2. THEY DO NOT KNOW WHICH TECHNICAL VOCABULARY WORKS — AND SAID SO.

Their own confidence tiers:

- **HIGH (likely work):** focal lengths (18/50/85/100mm) · camera movements (crane, dolly,
  pan, orbit) · lighting direction (rim, back, key, fill) · shot sizes (wide → ECU)
- **MEDIUM:** god rays / volumetric light · bokeh · subsurface scattering · specular highlights
- **LOW (might be ignored):** ambient occlusion · water caustics · lens bloom · telephoto
  compression

Spend words on the HIGH tier. A LOW-tier term is a word that probably did nothing.

## 3. THEY SUSPECT PLAIN DESCRIPTION BEATS JARGON — AND NEVER TESTED IT.

Their own worked pair:

> **A (jargon):** "Volumetric god rays pierce the canopy, subsurface scattering through
> petals, ambient occlusion in shadows."
> **B (plain):** "Thick shafts of sunlight cut through the leaves, glowing through flower
> petals like stained glass, shadows deepening between roots."

They believe both may land the same, and admit their own stacking of techniques is because
the writer *"isn't sure which terms work → uses multiple approaches"*. Redundancy is a
symptom of uncertainty, not craft. Write B.

## 4. THEIR OWN NAMED WEAK POINT IS THE ONE WE KEEP HITTING.

> "Clip 2→3 transitions rely on the human writer knowing Fuzzby is STILL covered in pollen."

They have no mechanism for it either. The difference is that they solve it with a phrase and
we solve it with scaffolding. Solve it with the phrase.

## 5. THEIR REFERENCE STACK COVERS THE BEAT'S CONTENT. OURS COVERS IDENTITY ONLY.

AnyFilm select reference images by what the shot *does*:

- **RULE 1 — keyframe coverage:** first shot's opening frame · mid-clip emotional peak
  (dialogue: the reaction) · final shot's closing frame (action: the payoff beat)
- **RULE 2 — character coverage:** shot-reverse-shot → both setups · group → widest + key
  CU · **physical comedy → setup + impact + recovery**
- **RULE 3 — continuity anchors:** wardrobe state · prop presence · lighting reference

Ours is @图1 (previous shot's final frame) + one turnaround per character + the plate. That
is identity and world — and **nothing showing the impact or the payoff**. On a physical
comedy beat we are asking the model to invent the exact moment the shot exists for, with no
visual reference for it, while giving it three references for things that barely change.

This is the largest remaining structural difference between their pipeline and ours. It is
recorded here as the standing finding; changing the stack is a gate/cost decision, not a
prompt-writing one.

**UNTIL IT CHANGES:** the words must carry the impact and the payoff alone, because no
image does. Spend there first. That is where a physical-comedy prompt earns its length —
not on restating identity the turnarounds already lock.
