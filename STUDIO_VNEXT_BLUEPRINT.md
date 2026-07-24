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
   that"). CONFIRMED BY THEIR OWN AI DIRECTOR (2026-07-24, Julian's oracle session): each
   clip starts from its first shot's STORYBOARD STILL, never the previous clip's last
   frame — "if a video clip deviates significantly from its prompt in the final seconds,
   the next clip (starting fresh from its storyboard) may have a visual discontinuity. The
   system relies on prompt discipline… rather than direct frame-to-frame generation."
   Our harvest chain is the structural fix they don't have — proven live the same day it
   was confirmed: S1.SH3 fired FROM S1.SH2's harvested final frame and held continuity on
   the first roll. THE FUSED CONTINUITY MODEL (our junction-type doctrine, kept): within a
   scene, default = harvest-anchored (previous approved clip's final frame as the start
   frame — the HOLD tail exists to make that frame clean); a deliberate fresh camera setup
   or scene opener = composed start frame instead, with state carried by references and
   prompt (their "continuity bridge" prose — carried positions, lighting keys, marks —
   kept as the SECONDARY layer on top of the frame anchor, not the only defense).
3. **The light law** — banned drift vocabulary enforced on every clip prompt
   (their cards carry warm-amber/golden freely; ours compile through _DRIFT_VOCAB_RE).
4. **Verbatim dialogue gate** — every in-prompt line checked against the locked script.
5. **Duration honesty** — clip duration fits content (their flat 15s wastes money and pace).
6. **One-variable retakes + the rejection ladder + scene-by-scene batching** — never a
   "Generate All · $316" button without per-scene review between batches.
   CONFIRMED BY THEIR AI (oracle session #2): their regeneration is a blind reroll — same
   prompt, same start frame, no seeds ("each regeneration is a fresh roll"), no record of
   what was rejected or why. Ours keeps the full retake ledger (rejection category +
   correction on file, one controlled reroll, then one variable changed, redesign after
   two failed batches, rejects archived as evidence). Their own workaround advice —
   "split shots into separate clips so you can regenerate smaller segments without losing
   good performances" — becomes our law: **PACK BY RISK, NOT JUST DURATION.** A high-risk
   gag beat gets its own clip so a retake never kills good neighbouring performances;
   low-risk connective coverage packs 2-3 shots. Also confirmed: no seed control exists on
   these models (matches our own provider findings) — the approved clip FILE is the only
   preservation; never regenerate an approved take.

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

## PART 1.5 — THE ORACLE SESSIONS (their own AI Director, interrogated by Julian, 2026-07-24)

Confirmed mechanics, straight from the machine — each one now a design input:

**CLIP PACKING (Brick 1's rules):** group by dialogue boundaries (complete exchanges),
action continuity (a crash never splits), emotional beats (held moments stay whole),
10-30s technical window. 1-3 shots; their real distribution 2×1 / 9×2 / 29×3. Three
shots = setup/action/reaction — "mirrors classical film editing." Never 4+: attention,
drift, compressed dialogue, and bigger retake blast radius. PLUS our addition: pack by
RISK (their own regen advice).

**THE DIRECTOR'S GRAMMAR (Brick 4's staging doctrine, verbatim from their rules):**
- Lens semantics: 18mm space > faces · 24-35mm relationships · 50mm workhorse/human eye ·
  65-85mm face/emotion · 100mm objects-that-must-be-SEEN.
- Shot count scales to narrative density, never duration: 8 (linear emotional arc) → 12
  (avg) → 16 (tonal shift in one location) → 18 (major turning point) → 20 (climax with
  intercutting).
- Sequencing: master→coverage · shot/reverse at MATCHING lens lengths · progression
  inward as emotion escalates · breathing room after intense close-ups.
- Framing reuse only within the same conversation / 3-5 shots; never across location or
  time shifts.
- Camera-move semantics: static = weight/ceremony · push-in = revelation · tracking =
  energy · handheld = chaos/comedy · crane = scale shift/closure.
- Composition: thirds, leading lines, FG/MG/BG depth layering, negative space = isolation.

**REFERENCE ATTACHMENT:** storyboard shot = characters in frame + location + props in
frame; video clip = every character appearing in ANY of its shots (so a mid-clip
entrance stays on-model). SURPRISE: their 4-angle location plates are decoration — "no
separate angle system exists; the cinematography language IN the shot prompt IS the
angle selector."

**THE TURNAROUND SHOCK:** their system does NOT use multi-angle reference sheets at all —
one single front-facing WARDROBE IMAGE per character state is the only image reference,
justified by "most video models accept only 1-2 reference images." OUR PROVIDER TAKES
FOUR IMAGES PLUS AUDIO — we ship turnarounds + plate + anchor frame + @Audio1 on every
clip. Structurally richer identity anchoring than the platform that set the quality bar;
keep it, never dilute to their single-image model.

**WARDROBE = STATE SYSTEM (validates and refines our prop-state doctrine):** each
wardrobe is image + reinforcing text + scene mapping, and it carries PROP STATES —
their Keen wristbands genuinely progress "plain leather" → "glowing faintly" → "set with
glowing aquamarine gems" across wardrobe entries. Adopt exactly this shape: wardrobe
variants per scene-range, auto-mapped, with state-carrying props inside the wardrobe.

**THE VOICE CONFESSION (vindicates Law 5 + @Audio1 completely):** the rough cut plays the
video model's embedded "temp voice" — "inconsistent tone, pacing, or vocal character
between clips… no character voice memory exists between generations." Their ElevenLabs
lines are generated but NOT overlaid; the Final Mix step to replace audio "is not yet"
built, and their own recommended fix is post-hoc replacement with lip-sync problems they
acknowledge ("synced to mouth movements"). OUR ARCHITECTURE BEATS BOTH: @Audio1 drives
the GENERATION — one canonical V3-acted voice per character, in the render itself,
native lip sync, deterministic timing. This is the single biggest structural advantage
we hold.

**STYLE SYSTEM:** a project-level style key ("pixar") injects model-specific keyword sets
per generation stage (wardrobes/stills/motion params/locations) and reinforces — never
rewrites — the authored prompt text. Set once at project start. Ours: the style law +
per-stage injection, same shape.

**FROM THE FULL WORKFLOW DOC (oracle session #3), five new nuggets:**
1. **PIPE = PAUSE dialogue syntax**: `KEEN'S MUM: Wherever you go… | KEEN'S MUM: You'll
   never be alone.` — splitting one speaker's line across pipe-separated repeats controls
   pacing inside the formula. Added to the clip-prompt grammar.
2. **3/4 VIEW is their primary character reference angle** (not front-on) — "generate 3/4
   view for primary reference." Worth an A/B in our wardrobe/reference generation.
3. **LOCATIONS ARE STATE VARIANTS, like wardrobes**: Crystal Cove exists three times
   (sanctuary / storm-building / beach-arrival) with a deliberate palette arc (warm gold →
   grey-blue → warm gold) tracking the emotional arc. Brick 2's location model: location ×
   narrative state, palette-arc-aware — the environmental twin of wardrobe states.
4. **THE STILL-PROMPT FORMULA**: [shot size, lens, movement] + [subject/action] +
   [composition] + [lighting] + [emotional intent], 150-300 words — Brick 4's card shape.
5. **THE FINAL MIX ORDER** (their unbuilt step; our cb_post already does most of it):
   strip embedded audio → sync dialogue → SFX at action cues → music at emotional beats →
   balance (dialogue fore, SFX mid, music back) → stereo master. Plus their per-scene
   music intent map (playful flute→ominous brass / tender piano / heroic rise / urgent
   percussion / warm strings) — seeds for our Giacchino-voiced Gate 5 brief.

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

## PART 3.4 — THE DASHBOARD (captured live, 2026-07-24)

Their dashboard is a RESUME MACHINE — every element answers "where was I, and what's one
click from here":

1. **Time-of-day greeting** — "GOOD MORNING / Action, Julian." The clapperboard hello.
2. **Four primary actions**: NEW PROJECT · CONTINUE (the hero) · PROJECTS · ASSETS.
3. **Studio-wide stat cards**: projects / characters / scenes / locations — the asset
   empire at a glance, across all projects.
4. **ACTIVE PRODUCTION card** (the centerpiece): project name · PIPELINE PROGRESS 09/10
   with bar · all 10 steps as chips with done-state lit · OPEN drops you at the current
   step. One glance = full production state; one click = back to work.
5. **QUICK GENERATE panel**: deep links straight to Characters / Locations / Storyboard /
   Footage / Voice-overs — skip the rail, jump to any generation surface.
6. **ENGINES panel with live latency**: Claude ~8s · EvoLink ~30s · ElevenLabs ~2s — "is
   my toolchain healthy" answered before you start.
7. **RECENT PRODUCTIONS**: resume cards with scene/char counts + relative time ("10m ago").
8. **CAPABILITIES strip**: each studio capability + the engine powering it (Script
   Analysis→Claude, Character Design→Nano Banana, Location Plates→4 angles, Storyboarding→
   auto-ref, Video Gen→Kling O3, Voice→ElevenLabs, Rough Cut→timeline) — orientation and
   honesty about what runs on what. (Note: their video engine is per-surface selectable —
   dashboard says Kling O3, the footage page fired Seedance. Multi-provider is native.)
9. **Header token balance**, always visible. Engine version in the footer.

**OUR DASHBOARD (Brick 3's front door) — same anatomy, three upgrades they don't have:**
- **DECISIONS WAITING** — the director's inbox, our unique advantage: "SH3 candidate
  awaiting your review", "Gate 2 sign-off pending", "1 retake brief open". Our engine
  already computes every one of these (approval ledger, gate states, candidate batches);
  their dashboard has no concept of it. This becomes the FIRST card — the studio tells
  Julian what needs his eye before anything else.
- **REAL SPEND, not tokens** — today / this episode / per-scene actual dollars from
  cost_ledger.jsonl, next to the estimate for the next planned batch.
- **ENGINES = our real health checks** — the API-health verification we already built
  (fal, ElevenLabs, OpenAI, Gemini) surfaced live with measured latency, not vibes.

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
