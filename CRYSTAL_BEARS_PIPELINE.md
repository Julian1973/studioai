# THE CRYSTAL BEARS — Complete Production Pipeline

*The front-to-back workflow we hang our hat on. Status: DRAFT for sign-off (2026-06-24). Once signed off, this document is the single source the **studio (cb-studio)** is built to act on — every gate fired, reviewed and signed off in the software, not by hand.*

---

## 0 · NORTH STAR — the soul every gate is measured against

**We are taking _Inside Out_ to the next level — through the bear's heart and soul.** _Inside Out_ put the feeling on the **inside**; the Crystal Bears puts it on the **outside** — a crystal you *see* glow, a note you *hear* ring, a colour that floods the clearing — so a four‑to‑eight‑year‑old with no word for the feeling **sees** it, **hears** it, **feels** it in their own tummy.

- The crystal is the **Need, not the mood** — it *contradicts* the brave face.
- **No villain, ever** — the antagonist is the feeling; the child is never braced, free to feel.
- Bears **sit with** each other; the turn comes from being *witnessed*, never solved.
- The Crystal Call is a **surrender played, not a power‑up**.
- Land it the **Bluey** way — never discussed, always *played*; the kid laughs while the parent breathes in, the same beat.

**The eight craft laws:** ① crystal = the Need ② want vs need on every beat ③ the surrender beat (not the power‑up) ④ the one wordless held beat ⑤ play is the vehicle ⑥ the catch and the release ⑦ hold the ache (never reset to zero) ⑧ the note carries the feeling.

**The test for any beat:** will they laugh out loud? will they breathe in? does the crystal tell the truth the bear can't yet say? does it reach the kid *and* the parent at once? *If not, it isn't there yet.*

> Audience is **ages 4–8** — dazzling AND dead‑centre for a five‑year‑old. Touchstones: **Toy Story, Trolls, Inside Out, Bluey.**

---

## The shape — five phases, each signed off

```
Script → Gate 1 Director → Gate 2 Foundation+Keyframes → Gate 3 Clips → Gate 4 Post → Export
                ✓ sign off        ✓ 2a   ✓ 2b                ✓                ✓            (CapCut)
```
A gate stays **locked** until the one before it is signed off. Everything is fired, watched live and stopped from the **studio**. *Procedure drives the prompts — never hand‑edit a prompt/pose/frame; fix the structure and re‑run.*

---

## The cast (the characters within it)

**The 7 bears — the Five Pillars made into people** (`config/characters.json`, canon §3):

| Bear | Crystal | Feeling | Note | Role |
|------|---------|---------|------|------|
| **Aida** | Rose Quartz | Confidence | G | wise elder / leader |
| **Sunny** | Citrine | Joy | C | youngest, most playful |
| **Luna** | Lepidolite | Calm | F | calm, nature‑connected |
| **Misty** | Moonstone | Trust / Intuition | A | oldest, most intuitive |
| **Amie** | Amethyst | Understanding | D | curious, expressive |
| **Howey** | Howlite | Kindness (Tide) | E | thoughtful, protective |
| **Keen** | Aquamarine | Courage | B | adventurous (Ep1 origin) |

Plus the **bees** (Fuzzby — bigger, proud; Zenny — smaller, deadpan), **Keen's Mum**, **Squeaky** (a small dolphin). Each character has: a structured **bible** (essence, voice, arc, do/don't), a **Crystal Call** (a declaration of inner truth — the crystal responds to *sincerity, not volume*), a canonical **ElevenLabs voiceId**, a locked **turnaround**, and a canonical **sizeRank**.

**Two laws bind every character everywhere:**
- **WRITTEN IN STONE** — a character *is* its turnaround reference. Never add or remove anything (no props on the body, accessories or attributes the reference lacks); staging describes position/action/camera/environment only.
- **SIZE CONTINUITY** — each character at its exact canonical size; a smaller character never renders larger (Fuzzby > Zenny).

---

## GATE 1 · THE DIRECTOR

**Engine:** Gemini, reading its *mind* at runtime — the director skill, the cinematography skill, the locked canon, the cast lock.
**Influences:** **Pete Docter** (lead with the feeling) · **John Lasseter** (story/character/heart) · **Patrick Lin** (camera) · **Jean‑Claude Kalache** (light).

**Structure — six staged passes** (`cb_director.py`):
1. **Theme lock** — the one theme, the SEL competency, the pressure‑test (the trap).
2. **Beat map** — scenes (cast, Pillar, look, light, emotional core) + episode arc + continuity scaffold.
3. **Beats** *(per scene)* — the 2–4 beats; each = one 10–12s Seedance take with its own internal cut‑list.
4. **Braintrust** *(per scene)* — critique vs the masters + theme, then **remake**.
5. **Derive plate** *(per scene)* — spec the single empty stage all the beats play on.
6. **Assemble** — write the **beat package** + `locations.json` + `continuity.json` + `episode_arc.json`.

**Output — the beat package**, every beat carrying the North‑Star fields: `want`, `need`, `crystalTruth`, `kidRead`, `adultRead`, `theGame`, `wordlessHeld`, plus `startState`, cuts, lighting, the take prompt. **Dialogue is locked verbatim** — the Director breaks the final script *down*, never rewords a line.

---

## GATE 2 · FOUNDATION + KEYFRAMES

Two signed‑off halves. **Engine:** Nano Banana (Gemini image), 2K.

### 2a · Foundation — *build the world*
**Influences:** **Ralph Eggleston** (the colour script) · **Harley Jessup** (warm, hand‑crafted worlds). *The world is the first character.*
**Structure** (`cb_pipeline.anchors` → `cb_scene.build_plate` → `cb_qa.check_plate`):
1. **Character locks** — each character's own locked turnaround (from the library; never generated).
2. **Build the empty plate** — the world, no characters; continuity‑aware (returning locations derive from their last‑seen state).
3. **Plate QA** — verify the world matches the location.
4. **Sign off → the plate becomes the frozen master.**

### 2b · Keyframes — *place the characters in*
**Influences:** **Glen Keane** (the pose must *feel*, not just look — the opening pose that already acts).
**Structure** (`cb_pipeline.coverage` → `cb_scene.run` → `cb_qa.check_scene`):
1. **One opening keyframe per beat** — `build_keyframe_prompt`: the frozen plate + the turnarounds + `startState` + the scale lock — **reference‑first** (points at the refs, describes nothing).
2. **The Definition‑of‑Done QA** *(21 checks, report‑only)* — identity, anatomy, scale, immutability (no added props), the **world‑class bar** (no flat/dull/AI‑mushy), pose‑reads‑in‑silhouette, plate fidelity, 2K, lighting…
3. **Review the flagged → regen → sign off** a spot‑on set.

> **This is the foundation.** The keyframe is the single image the whole clip is built from — *if it's wrong, everything downstream is wrong.* The machine catches the floor; your eye sets the ceiling (the *stunning*).

---

## GATE 3 · CLIPS

**Engine:** Seedance 2.0 reference‑to‑video + ElevenLabs V3 + ffmpeg. The still becomes **performance**.
**Influences — animation:** **John Lasseter** *(Toy Story — appeal + weight; the anti‑floaty‑AI cure)* · **Walt Dohrn** *(Trolls — joy, music‑on‑the‑beat, hugs)* · **Pete Docter** *(the wordless beat, the surrender)* · **Joe Brumm** *(Bluey — micro‑acting, the co‑watch)*.
**Influences — voice:** **Andrea Romano** *(cast to the cadence, direct the want — the firewall against the flat‑AI read)* · **Pete Docter** *(the feeling under the line)* · **Joe Brumm** *(the same‑second co‑watch)*.

**Structure** (`cb_pipeline.gate3` → `cb_beats.run`), per beat:
1. **Build the V3 voice track** — the locked lines, cut‑ordered, each in its speaker's canonical voice; *play the need* (a leak under a performed want), surrender = low‑energy, the wordless beat = silence, the stability law (≤0.40).
2. **One 10–12s Seedance ref2vid take** — animates *forward* from the keyframe (TRUTH), with the turnarounds + the voice + the multi‑shot prompt; Seedance directs its own internal cuts, camera, motion, **and scores the take** (synchronised SFX + timed comedy/emotional music — its timing is the point); the voice stays forward.
3. **Stitch** the beats into the scene → sign off.

**Animation laws baked in:** act it then size it (one clean arc) · **weight is non‑negotiable** (no sliding/floating/rubber‑limbs) · performance over bigness · comedy = catch‑and‑release · hold the ache (the wordless beat in stillness; the Crystal Call a surrender).

---

## GATE 4 · POST — *curation, not composition (the quality filter)*

**Engine:** ffmpeg (+ *fallback* ElevenLabs Music). **The hardest creative work is Gate 3; Gate 4 is the quality filter.** Seedance delivers the clip with voice + SFX + music already baked in; Post **listens and decides what Seedance got right — keeps what works, trims or replaces what doesn't**, masters and exports stems. **The ElevenLabs Music bed is the FALLBACK, not the default — fired only if Seedance's music isn't right for a scene.**
**Influences (finishing team, panel 2026-06-24):** **Walter Murch** *(emotion is the first criterion for every cut; silence as material; voice forward)* + **Kevin Nolting** *(Pixar editor — how long to hold a beat for ages 4–8; the held tail; the wordless nadir)* = the **editorial** core; **Tom Myers** *(Skywalker re‑recording mixer, Inside Out / Soul — the sidechain duck that keeps dialogue the anchor, the held tail, the clean 4–8 master)* = the **mix** core; **Joff Bush** *(Bluey — the tiny chamber palette that scores the feeling then thins or DROPS so the voice and room carry it)* + **Michael Giacchino** *(the single hummable theme carrying two feelings at once; want → surrender → ache by harmonic re‑colouring)* = the **composer**, for the *optional bed*. The bear's **note** is timed here: unresolved at the contradiction → resolves on the surrender → lingers as the ache in the closing chord.

**Structure** (`cb_pipeline.gate4` → `cb_post.run`):
1. **Assemble the picture** — crossfades (NO jumps) + a held tail, **keeping the clip's own voice + SFX + Seedance music**.
2. **Master** to −14 LUFS → a preview "complete."
3. **Export stems** (picture+voice · music · ambience) + a CapCut readme.

**The music bed ON TOP is the last, optional call** — your own `MUSIC.mp3` (always wins), `CB_AUTO_MUSIC_BED=1` (scratch underscore), or just take the stems to CapCut. Post never strips the clip audio; its job is the *seamless stitch + the polish + the stems.*

---

## EXPORT — the final phase

The signed‑off scenes assemble into the **finished episode**; the stems hand off to **CapCut**, where the final bed (if any) and the by‑ear mix land, and the episode is **exported**. This is the deliverable.

---

## THE CONTROL SURFACE — cb‑studio

Everything above runs **through the studio**: Projects → Episodes; per‑gate **Fire / Sign‑off / Stop** with live progress; the storyboard + per‑beat editors (cuts, Seedance, the extra references); the keyframe **Foundation** (plate + locked identity sheets); character profiles, bibles, Crystal Calls; the QA verdicts surfaced per beat. *Run through the system — every action goes through the studio.*

---

## NEXT — activate it in the studio (post‑sign‑off)

Once this document is signed off, the work is to make the studio **truly reflect and act on it end‑to‑end**, so the whole pipeline runs in the software, not by prompting:
- Surface every new structural element in the studio (the per‑beat North‑Star fields; the keyframe QA verdicts + Definition‑of‑Done; the gate minds/influences shown per gate; the Seedance‑scores + Post‑polish audio policy; the export phase).
- Make all four gates fire, review, sign off and stop cleanly from the studio with the new structure.
- Tweak the UX/UI where needed so each gate's structure, influences and rules are visible and driveable.
