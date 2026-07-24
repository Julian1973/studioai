# STUDIO vNEXT — The Brick-by-Brick Build Plan
**Julian's directive (2026-07-24):** *"strip the pipeline out, look and feel, and that's what
we need to create brick by brick… can we go better with our knowledge and experience. The AI
that sits in there is very good as well… the agent is always in the studio to help. We need
that."*

This is the definitive plan: AnyFilm's pipeline anatomy (captured live from Julian's own
project — 126 storyboard shots + 48 footage prompts in `shows/crystal-bears/creative/
anyfilm_reference/`), rebuilt as OUR studio, upgraded with everything this project has
proven the hard way. The Aida sanctuary clip is the quality bar; nothing we ship goes below it.

---

## PART 1 — The pipeline anatomy (what we are rebuilding)

**Ten linear steps, one rail, always visible, each gated on the last:**

```
PRE-PROD   1 Upload   2 Style   3 Analysis
DESIGN     4 Characters   5 Props   6 Locations
PRODUCTION 7 Storyboard   8 Footage   9 Audio   10 Rough Cut
```

The structural genius is the ASSET-FIRST DESIGN PHASE: before a single storyboard frame,
the system builds a complete, visual asset library — and every downstream generation PINS
its references from that library. Nothing is ever described twice; everything points at an
approved image.

### Step 3 — Analysis (script → full production breakdown, one pass)
Reads the screenplay → characters (with per-scene counts), scenes, shots, props, locations —
each with generation-ready prompts. Theirs did 18 pages → 11 chars / 10 scenes / 126 shots /
10 props / 10 locations in 7m18s. **We already have this** (cb_script + cb_creative + the
Episode Director) — ours is more faithful (verbatim dialogue lock, canon gates). What we
lack is the OUTPUT SHAPE: one visual, reviewable breakdown screen with live counts.

### Step 4 — Characters (the asset audit begins)
Per character: role line · FACE IDENTITY text · WARDROBES (per-scene-range variants, e.g.
Keen: pier-dry / at-sea-soaked / post-storm) · REFERENCE SHEET (multi-angle turnaround +
face closeups) · per-character image model choice · Regen/Upload per artifact.
**Our upgrade:** face identity and wardrobe text are COMPILED FROM LOCKED CANON
(characters.json), never LLM-freewritten (theirs drifted Zenny into a lavender bear).
Upload slots take our real turnarounds. Wardrobe-per-scene-range is genuinely new for us —
adopt it (it IS our Keen-two-states doctrine, generalized).

### Step 5 — Props (new for us — build it)
Isolated object plates: "…on a plain neutral grey backdrop with soft studio lighting. No
environment, no context, just the object." Props carry scene tags. **Our upgrade:** props
with STORY STATES get one plate per state (wristbands VACANT vs CRYSTAL-LIT — the
inheritance is the episode's payoff; their single glowing plate spoils it). Prop plates
join the reference stack for any shot featuring the prop — this is how the wristband
close-ups hold.

### Step 6 — Locations (upgrade of our single scene plate)
FOUR angles per location: top-down / wide / close-up / low-angle, plus a generation prompt
per location. **Our upgrade:** our Crystal World Rule plate QA runs on all four; our light
law governs the prompts (no golden-hour vocabulary — that's baked into several of theirs).

### Step 7 — Storyboard (the Director's real output)
One card per shot: prompt prose (lens mm + camera move + action + light + micro-expression),
reference chips pinned from the asset library (LOC + CHARs), per-shot model + cost, per-shot
Gen/Regen/Upload, per-scene "Generate Scene" batch. 126 shots at ~$0.17.
**The twelve craft techniques** (full analysis in anyfilm_reference/ANYFILM_STORYBOARD_
ANALYSIS.md): expand-don't-compress · one-job-per-shot · reaction coverage · editorial
rhyming ("same framing as shot N") · lens ladder (18/28/35/50/65/85/100mm = emotional
distance) · light-as-narrative-clock · sound-in-cards · declared visual modes (VISION /
UNDERWATER / INTERCUT) · micro-expression cards · object-history macros · scale
storytelling · ceremony-as-sequence. These become OUR Director's staging laws.

### Step 8 — Footage (THE CLIP FORMULA — measured across all 48 captured prompts)
Storyboard shots pack 1–3 per 15s clip. The template (39/39 dialogue clips identical
skeleton, avg 244 words — lean):

```
ENGLISH DIALOGUE ONLY, spoken in English.
Shot 1: [framing], [lens]mm, [camera behaviour]. [Action prose — physical, sensory,
  cause-and-effect. Micro-detail: catchlights, water, light interaction.]
  [SPEAKER: Exact dialogue line.]
Cut to. Shot 2: [framing], [lens]mm, [camera]. [Action…]
Cut to. Shot 3: …
Characters look across the frame at each other, NOT at the camera. After the final
line they HOLD the look, about 2 seconds of silence, no more dialogue.
```

Start frame per clip (from storyboard frames) + pinned references + duration slider +
per-clip cost. Dialogue-free clips drop the header and behaviour laws.

**OUR UPGRADES (the fusion — where we beat them):**
1. **@Audio1 ElevenLabs V3 as the performance reference** (Julian: "the ElevenLabs V3
   acting level is key"). Their native voice = different voice per clip; our canonical cast
   voices + duration-matched masters = consistent characters AND deterministic timing. The
   dialogue text stays in-prompt (their formula) with @Audio1 driving the actual voice —
   the confirmed-bypass pattern we already run.
2. **Continuity chain** (Julian: "the continuity between shots isn't great — we can improve
   that"). Their clips generate independently — that's why their rough cut drifts. Our
   relay/harvest doctrine (previous clip's settle frame as next clip's start frame) is the
   fix they don't have. Start frame = harvested previous end, references = turnarounds +
   location plate + prop-state plates + face-state image when a mark persists.
3. **The light law** — banned drift vocabulary enforced on every clip prompt
   (their cards carry warm-amber/golden freely; ours compile through _DRIFT_VOCAB_RE).
4. **Verbatim dialogue gate** — every in-prompt line checked against the locked script.
5. **Duration honesty** — clip duration fits content (their flat 15s wastes money and pace).
6. **One-variable retakes + the rejection ladder + scene-by-scene batching** — never a
   "Generate All · $316" button without per-scene review between batches.

### Step 9 — Audio Studio
Every dialogue line as a row: character · line · voice settings (stability/style sliders) ·
per-line Generate · line-level regen. **Ours is already deeper**: V3 acting tags, the
Voice Director's cadence compiler, wordless-held doctrine, padded masters. Keep our engine,
adopt their LINE-TABLE UX — the whole episode's dialogue on one screen.

### Step 10 — Rough Cut
In-studio timeline: video track + text + VO + music lanes, split/edit tools, AI Edit,
Finish & Export. **Ours adds:** conform-trim joins (assemble_conformed), captions (.srt/
.vtt), platform loudness masters, 9:16 derivative — already built in cb_post, needs this UI.

---

## PART 2 — The agent layer (Julian: "the agent is always in the studio — we need that")

Two agents, always present, both already within our reach because the engine is ours:

**1. THE AI DIRECTOR (global, persistent right-side chat).** Theirs: Claude Sonnet 4.5,
takes plain English ("Make all night scenes more dramatic", "i need to add the character
fuzzby back in") and EDITS PROJECT DATA. Ours: Claude via cb_llm with function-calling over
our real engine operations (edit character/beat/scene fields, re-promote, prepare
departments, run audits) — every mutation logged to the ledger, gated exactly like a human
edit, never a silent write, never a paid fire without the disclosure flow. Our version is
STRONGER because our engine has real gates the agent must pass through; theirs writes
freely.

**2. THE SCENE AGENT (contextual, floating on every production screen).** Scoped to the
scene in view: "tighten this clip's pacing", "restage shot 12 without the crystal",
"why is this blocked?". Ours additionally surfaces gate/lint/QA state as answers — the
explain-the-block agent the Studio's own audit history kept asking for.

Both run on our existing cb_llm plumbing. The agent NEVER bypasses: spend tokens, canon
gates, drift vocabulary, verbatim dialogue — all apply to agent-initiated changes
identically.

---

## PART 3 — Look and feel

Adopt their structural language, keep our craft: single always-visible pipeline rail with
step states · one linear flow, each step a full-screen focused workspace · card grids for
assets/shots/clips with per-card action + cost + model · token/cost counter in the header ·
progress dots footer · "Continue → next step" as the only forward door · agent chat
docked right + floating scene agent. Our existing dark-neutral cinematic CSS system stays
(it's already premium); we adopt their DENSITY and card anatomy, not their purple.

---

## PART 3.5 — THE NO-STRAITJACKET LAW (Julian's ruling, 2026-07-24 — "their prompts have
produced top quality AAA pixar… don't kill them with straitjackets", said twice)

The footage formula's creative richness IS the product. This project's own history proves
the failure mode: stacked negatives, repeated scaffolding and armor paragraphs flattened
motion until the prompts read as contracts instead of direction. Therefore, hard law:

**What is ALLOWED to touch the clip prompt text:**
- The formula's own skeleton (header · shots · "Cut to." · behaviour tail) — as captured.
- The writer's free creative prose: action, physics, micro-detail, light, emotion. UNBOUNDED
  in vocabulary and style, subject only to the checks below.
- Verbatim locked dialogue on SPEAKER: lines.
- The scene's own light state written as CONCRETE weather/sky (the one proven word-level
  guard: no sunset/golden-hour time-of-day words in a day-bright scene — a ~7-word
  banned list, not a style cage).

**What is FORBIDDEN from entering the prompt text (our old armor stays retired):**
- No standing negatives pile. No eleven-item lists. Gag-specific negatives only when a
  specific documented failure demands one, and then at most a line.
- No injected acting-DNA blocks, camera-lock clauses, wing-law paragraphs, reference-role
  boilerplate, or repeated constraint scaffolding.
- No word-count ceiling enforcement inside the compiler. (The formula naturally lands
  ~100-310 words; if a prompt runs long, a human reads it, no machine truncates it.)

**Where our knowledge actually enters (outside the text):**
- REFERENCES: turnarounds, wardrobe variants, state-aware prop plates, location angles,
  face-state images, harvested start frames. Images carry identity and continuity — words
  never re-describe them.
- @Audio1: the V3 acted performance as the voice reference.
- CHECKS THAT REVIEW, NEVER INJECT: dialogue-verbatim, drift-vocabulary, canon (bees/
  crystals, prop states), continuity-chain presence — each returns a verdict a human sees;
  none appends a single word to the prompt.
- THE RETAKE PROTOCOL: quality is enforced by judging real footage and re-rolling with one
  variable changed — not by pre-armoring the prompt against imagined failures.

**THE SHOW BIBLE POPULATES THE ASSET LIBRARY** (same ruling): scenes, props, wardrobes and
location fields are seeded mechanically from locked canon — characters.json bibles,
locations.json, gag_locks, the script's own object list (wristbands, map, satchel, net,
crystals, pollen sacks) — the Fidelity Law applied to Bricks 2-4: canon populates, the
LLM enriches presentation, nothing contradicts the source.

## PART 4 — Build order (brick by brick)

- **Brick 1 — THE FOOTAGE FORMULA (immediate, engine-only).** New clip-prompt compiler
  emitting the measured template (header/shots/Cut to./behaviour laws) from our canonical
  package, with our six upgrades wired in. Provable on S1.SH3 vs the current prompt.
- **Brick 2 — THE ASSET LIBRARY.** Props module (state-aware plates) + 4-angle locations +
  wardrobe variants per character; reference-pinning into every downstream prompt.
- **Brick 3 — THE PIPELINE SHELL.** The 10-step rail UI over our existing serve.py engine;
  Analysis/Characters/Props/Locations/Storyboard screens reading our real data.
- **Brick 4 — STORYBOARD 2.0.** Card-grid with per-shot gen; the Director rebuilt on the
  twelve techniques (expansion, coverage, rhyming, lens ladder).
- **Brick 5 — FOOTAGE + AUDIO SCREENS.** Clip cards with start frames, reference chips,
  per-clip fire; the dialogue line-table over our V3 engine.
- **Brick 6 — THE AGENTS.** AI Director + Scene Agent over the whole thing.
- **Brick 7 — ROUGH CUT UI** over cb_post.

Each brick lands with tests, gates intact, and one real proof-fire before the next begins.
