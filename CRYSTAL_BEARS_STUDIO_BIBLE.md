# CRYSTAL BEARS — THE STUDIO BIBLE
*The production pipeline, the chairs, the minds, and the locked craft rules. This is the source of truth. Everything the software does must serve this document.*

Brand DNA (every chair answers to this): **Pixar-quality 3D CGI comedy · the heart of *Inside Out* · the everyday truth of *Bluey* · the vibrant energy of *Trolls*.** Made for ages 4–8, co-watchable by a parent.

---

## PART 0 — THE FIVE GOVERNING LAWS

1. **One studio, one director, one mind per chair — never a committee.** A Pixar film is not twelve voices arguing into one prompt. It is a *director* with a vision and department heads who serve it. Our failure mode was stacking layers (director-pass + modes + staging + comedy + crystal rules) that each appended to the prompt until the signal drowned. **Every chair is one coherent auteur. The Director makes the calls; everyone else executes his vision in their craft.**

2. **References are law; text does the motion; Seedance does the heavy lifting.** Identity and look come *entirely* from the reference images. The prompt text controls only **motion, performance beats, camera freedom and audio rules**. Describing a character in text competes with the refs and causes redesign — so we never do it.

3. **Fix the structure, not the output.** A bad clip is a bad *keyframe, prompt, or reference* — never something to hand-patch. We fix the thing that produced it and re-run through the system. No one-off test files.

4. **Gate discipline.** Each gate is signed off before the next unlocks. Stop at the image gate. Cheap fixes upstream beat expensive fixes downstream.

5. **The voice lives in the render — never in post.** The ElevenLabs V3 track goes *in* as `@AudioN` and Seedance outputs it. Post is a mix, not a rescue.

---

## PART 1 — THE PIPELINE AT A GLANCE

```
GATE 0 Write → GATE 1 Direct → GATE 2 Keyframe → GATE 3 Animate → GATE 4 Retake/Edit → GATE 5 Post
                                                    (Continuity / Script Supervisor checks EVERY gate)
```

Into Seedance at Gate 3 go only three things: **the keyframe (`@图1`), the character turnarounds (`@图2`/`@图3`), and the V3 voice (`@AudioN`).** Seedance directs everything else — motion, camera, cuts, music, SFX.

---

## PART 2 — THE CHAIRS
*For each: the role, the mind, why them, why they're on board, and what they own.*

### GATE 0 — WRITERS' ROOM · **Showrunner: Joe Brumm** (creator of *Bluey*)
- **Why him:** *Bluey* is our co-watch North Star — stories that are genuinely funny for a 5-year-old and quietly move a parent, built from everyday truth, never preachy. Brumm writes emotion through play.
- **On board for:** heart, kid-real dialogue, comedy that comes from character, the SEL lesson carried invisibly.
- **Owns:** SEED → a **locked, dialogue-final SEL screenplay**. Self-scored; won't ship below 8/10. (Supported by the room: Docter · Stanton · Nee · Woolverton.)
- **Hands down:** one locked screenplay → the Director.

### GATE 1 — DIRECTOR · **Pete Docter** (*Monsters, Inc.*, *Up*, *Inside Out*, *Soul*)
- **Why him:** *Inside Out* is our literal North Star — *"the feeling outside; the crystal you see."* Docter directs **emotional truth through comedy** better than anyone alive. He is the single call-maker.
- **On board for:** the vision. He decides what each moment *means* and *how it plays*.
- **Owns:** breaks the locked script into **segments** (dramatic-beat integrity — never cut mid-joke); writes each segment's **SCENE** and **ACTION / PERFORMANCE** — the craft half of the Seedance prompt (the beats, the weight, the comic timing). He sets emotional + comedic intent. **Every other chair serves this brief.**
- **Hands down:** the segment breakdown + per-segment briefs → DP and Animator.

### GATE 2 — CINEMATOGRAPHY + PRODUCTION DESIGN (Keyframes) · **Sharon Calahan** (DP) + **Ralph Eggleston** (Production Designer)
- **Why them:** Calahan lit *Toy Story*, *A Bug's Life*, *Finding Nemo* — Pixar's foundational DP; warm, painterly, naturalistic light that feels both real and magical. Eggleston designed *Inside Out* and authored its colour script — the emotional use of colour.
- **On board for:** the *look* — composition, lighting, the crystal-world palette.
- **Owns:** from the Director's brief + the **locked turnarounds** + the scene plate, they compose and light each **keyframe** (opening, and closing where the beat needs it). **Reference-anchored** (identity from the turnarounds, never prose), **crisp** (sharp still, wings defined, *no motion blur* — the still is the frame Seedance animates *from*), 2K, QA'd.
- **Status:** ✅ **Working — the keyframes are good.** This chair is not where we drifted.
- **Hands down:** the signed-off keyframe(s) → Gate 3.

### GATE 3 — SUPERVISING ANIMATOR + VOICE DIRECTOR (Animation) · **Glen Keane** (animation) + the **Voice Director** (V3)
- **Why them:** Keane is the greatest character animator — *appeal, weight, the illusion of life.* He is the cure for the floaty. The Voice Director gets the ElevenLabs V3 performance to *act* — proud here, a whisper there, real cadence — not one flat accent.
- **On board for:** making it **move with real weight and comic timing**, and making it **sound alive**.
- **Owns:** Keane's craft is written into the Director's **ACTION / PERFORMANCE** beats (anticipation → impact → follow-through) and protected by the **negatives** (no floaty, no morphing). The render runs through Seedance guided by the **definitive prompt** (Part 3). The Voice Director acts the V3 lines that go in as `@AudioN`.
- **Where we drifted:** *the prompt* — over-choreographed, contradictory, and it didn't speak Seedance. **Fixed** by the definitive structure below.
- **Hands down:** the signed-off clips → Editor.

### GATE 4 — EDITOR (Retakes / Cut) · **Kevin Nolting** (*Up*, *Inside Out*, *Soul*)
- **Why him:** Pixar's editor — impeccable comic *and* emotional timing; he knows to the frame when a beat lands or drags.
- **On board for:** the cut, the pace, and calling the **surgical retakes** (fix one shot inside a beat, never re-render the whole thing).
- **Owns:** watches the assembled scene, flags shots for retake with the change, conforms the cut, signs off pacing.
- **Hands down:** the locked cut → Post.

### GATE 5 — SCORE + SOUND + MIX (Post) · **Michael Giacchino** (Composer) + **Gary Rydstrom** (Sound Designer / Re-recording Mixer)
- **Why them:** Giacchino scored *Up*, *Ratatouille*, *Inside Out*, *Coco* — the Pixar emotional composer. Rydstrom is a seven-time-Oscar sound legend (*Toy Story*, *Finding Nemo*).
- **On board for:** the final polish — balance, master, warmth.
- **Owns:** because the **voice is already in the render** and Seedance scores the music/SFX, Post = **curate, mix, master, stitch**. Their taste replaces any weak Seedance music, ducks the score under dialogue, and masters to broadcast loudness. **No voice swap.**
- **Hands down:** the finished film.

### CROSS-CUTTING — CONTINUITY / SCRIPT SUPERVISOR · **the bible-keeper**
- **Why:** at scale, drift is the enemy of IP. One meticulous eye keeps every frame on-canon.
- **On board for:** consistency — catches off-model characters, wrong crystal colours, broken screen direction, canon errors.
- **Owns:** runs at **every gate**, returns BLOCK / NOTE findings *before* the human signs off.

---

## PART 2.5 — THE GATE CONTRACTS
*Every gate is a HARD LOCK. You cannot advance until the chair has **produced its deliverable** and it is **signed off**. The lock is enforced three ways — the pipeline refuses to fire, the server refuses the request, the UI shows 🔒. Continuity checks **before** every sign-off.*

**The contract shape:** `LOCKED UNTIL (entry) → THE WORKFLOW (the chair's actions) → DELIVERABLE / DEFINITION OF DONE → SIGN-OFF → UNLOCKS next`. A gate that hasn't created its deliverable to the DoD **cannot be signed off**, so the next gate stays locked.

| Gate · Chair | Locked until | The workflow (creates what we need) | Deliverable / Definition of Done |
|---|---|---|---|
| **0 · Write** (Brumm) | a SEED exists | 8-pass room: heart → lesson → game → outline → draft → punch-up → braintrust → lock | **Locked, dialogue-final SEL screenplay**, self-scored ≥ 8/10 |
| **1 · Direct** (Docter) | Gate 0 signed | reads the locked script + world; cuts it into **segments** (beat-integrity); writes each segment's **SCENE + ACTION/PERFORMANCE** | **Full segment breakdown + per-segment briefs**, each a complete beat, on-brand; Director's-Eye passes |
| **2 · Keyframe** (Calahan + Eggleston) | Gate 1 signed | compose + light each keyframe (opening + closing) from brief + turnarounds + plate; reference-anchored, crisp; QA each | **Every keyframe signed off** — 2K, on-model, crisp (no motion-blur), continuity-chained; `cb_qa.check_done_frame` passes |
| **3 · Animate** (Keane + Voice Dir.) | Gate 2 signed | Voice Dir. acts V3 lines → `@AudioN`; the **definitive prompt** renders each segment from keyframe + turnarounds + voice; clip QA | **Every clip signed off** — on-model through motion, weighty physics, **11Labs voice IN the render**, lip-synced; `cb_qa.check_clip` passes |
| **4 · Retake/Edit** (Nolting) | Gate 3 signed | watch the assembled scene; call **surgical retakes** per shot; regen + splice; conform the cut | **Locked cut** — flagged shots fixed (before/after reviewed), pacing signed off |
| **5 · Post** (Giacchino + Rydstrom) | Gate 4 signed | curate/replace weak music, balance, duck score under dialogue, master to loudness, stitch | **Finished, mastered film** |

**The rule in one line:** *a gate only opens when the one before it has actually built its thing and you've signed it. No skipping, no "we'll fix it later," no half-baked hand-off.*

## PART 3 — THE LOCKED CRAFT RULES

### 3.1 — Keyframe discipline (Gate 2)
- **Reference-first:** identity comes *only* from the locked turnarounds (`@图2`/`@图3`); the prompt describes staging, light and mood — **never** the character's design.
- **CLEAN base identity — render exactly per the reference, add nothing beyond it. Baked software-wide in `build_keyframe_prompt` (not per-beat).** The keyframe renders each character *exactly as its turnaround shows it* — **including canonical accessories the reference itself carries** (glasses, Aida's pendant, Keen's worn wristbands). It does **not** apply a **temporary transformation** the story puts the character through — a pollen moustache, being caked/dusted/covered in pollen, dirt, wet or muddy fur, a smear, a loose held prop. Those are **applied *and* removed by Seedance inside the take**. Baking a transient state in locks the whole beat to "with it" and creates a jarring *with-it / without-it* cut at the boundary — and it's exactly the heavy lifting Seedance is for. *The distinction that matters:* canonical accessory (in the reference → render) vs temporary transformation (not in the reference → Seedance adds it). The rule is enforced for **every keyframe in every scene**, so a beat whose start-state names a state (audited: 1.B4 moustache, 5.B wet, etc.) is cleaned automatically — no hand-edit.
- **Crisp / frozen instant:** describe the pose *positively* — "a single frozen instant at high shutter speed, wings held sharp and fully defined." Front-end pose, not a back-end "no blur" constraint. A blurred keyframe reads as "already moving" and *dampens* the motion Seedance adds.
- **No overrides that shadow the engine:** a saved `keyframePromptOverride` fires verbatim and silently pins that beat, so later engine improvements never reach it. Prefer editing the start-state; clear stale overrides.
- **Cascade:** each keyframe chains off the previous approved one for lighting/world continuity (not body states — those live in Seedance).

### 3.2 — The definitive Seedance prompt (Gate 3) — *3-model consensus (GPT-5.5 · Claude Opus 4.8 · Gemini 3.1 Pro)*
Prose-first (Seedance follows natural language). Six sections, always in order. **The Director writes only SCENE + ACTION/PERFORMANCE (+ an optional camera hint); REFERENCE LAW, AUDIO and NEGATIVES are baked law he cannot break.**

```
12 seconds, 16:9.

REFERENCE LAW: @图1 (keyframe) is TRUTH — copy the characters EXACTLY (no redesign/morph/rescale/new accessories) and
  copy the environment + lighting from it. @图2 = the LARGER bee (frame-LEFT); @图3 = the SMALLER bee (frame-RIGHT) —
  turnarounds lock proportions, markings, glasses. Add ONLY motion and performance. No extra characters.
SCENE:  <the world / light — no character description>
ACTION / PERFORMANCE:  <the beats + real cartoon physics: anticipation → impact → follow-through; readable comedy>
CAMERA:  Seedance directs cinematically; keep both characters readable + on-model; no chaotic camera.
AUDIO:  use ONLY @Audio1 for ALL dialogue — the characters speak the words in @Audio1, each lip-syncing to its own lines
  in order; generate no other/duplicate voice. Seedance scores the rest: ambience, SFX, a light underscore (no sung lyrics).
NEGATIVES:  no morphing/redesign/rescale, no extra limbs, no flicker/artifacts, no on-screen text/subtitles, no logos,
  no foreign-language speech, no crystals on the bees.
```

**Why this shape (the consensus):**
- **No identity description in text** — the single highest-ROI change; kills the "copy exactly" vs "Pixar-quality" contradiction that makes the model redesign faces. *(Claude's strongest point; matches our reference-first doctrine.)*
- **Role labels, not names** — "the larger bee" / "the smaller bee" avoids the *name-trap* (latent associations). Names still live in the audio. *(Gemini; the one A/B-testable variable — 2 of 3 models say names are fine if reference-locked.)*
- **Keep the action/performance prose** — that's where text genuinely improves motion. *(All three.)*
- **Prose in, JSON only as internal spec.** *(GPT-5.5; Seedance follows natural-language logic.)*

### 3.3 — Voice in the render (Gate 3)
**Use ONLY `@Audio1` for all dialogue** (one supplied V3 track, both speakers in temporal order) — the fal-documented pattern that makes Seedance *output the supplied 11Labs voice* instead of inventing one; each character lip-syncs to its own lines. `generate_audio: True` so Seedance *also* scores music/SFX. The prose is sent **plain** (`raw_prompt=True`) so nothing wraps or contradicts it. **No post swap** — `cb_post` keeps the render's native voice and only masters.

### 3.4 — The reference model
`@图N` is Seedance's native image token (not `@ImageN`). Order: `@图1` keyframe, `@图2` larger-bee turnaround, `@图3` smaller-bee turnaround. Audio: `@Audio1..` per speaker.

### 3.5 — Density
12s is action-dense. If a beat drifts past ~7s, **split into a 2-clip fallback** — never keep rewriting.

---

## PART 4 — HOW THIS IS BAKED INTO THE SOFTWARE

- **Each chair = one LLM pass with one auteur system-prompt** (its mind's taste + craft + the rules above). No stacked layers.
- **Gate 1 (Docter):** system prompt carries the brand DNA + the Seedance craft + this bible; writes SCENE + ACTION per segment. The old Director's Pass / 15 modes / staging / comedy / crystal layers **collapse into his head as taste**, not separate passes.
- **Gate 3 form:** `cb_segprompt.py` is the definitive builder — REFERENCE LAW / SCENE / ACTION / CAMERA / AUDIO / NEGATIVES. The Director fills SCENE + ACTION; the rest is baked law.
- **`cb_voice`:** emits per-speaker tracks. **`cb_gen`:** sends prose + `@图N` + per-speaker `audio_urls` + `generate_audio`. **`cb_post`:** mix/master only, no voice swap.
- **Continuity:** a check that runs at every gate against the turnarounds + canon.

---

## PART 5 — STATUS

- ✅ **Gate 2 keyframes — good** (reference-anchored, on-model). Not the problem.
- ✅ **Gate 3 prompt — fixed** to the definitive structure (`cb_segprompt`), verified.
- ⏳ **Remaining wiring:** per-speaker voice (`cb_voice`) · `@图N` + audio pass (`cb_gen`) · point Gate 3 at `cb_segprompt` (`cb_beats`) · crisp-keyframe rule (`cb_prompts`) · strip post voice-swap (`cb_post`).
- ⏳ **Then:** render Segments 1–4 the proper way, voice in the render, and judge.
