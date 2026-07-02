# THE CRYSTAL BEARS — THE ENGINE (front to back)

*The complete production engine: every module, the data structure, and the **actual live prompts** the code generates. Companion to `CRYSTAL_BEARS_PIPELINE.md` (the soul, the cast, the influences). All prompts below are pulled straight from the running code (Ep1 Scene 1 · beat 1.B1).*

---

## THE FLOW — modules, gates, artifacts

```
 SCRIPT (final, dialogue locked)
   │
   ▼  GATE 1 ─ cb_director.py  (Gemini)
 BEAT PACKAGE  +  locations.json  +  continuity.json  +  episode_arc.json
   │
   ▼  GATE 2a ─ cb_pipeline.anchors → cb_scene.build_plate → build_plate_prompt → cb_gen.generate_image (Nano Banana)
 SCENE PLATE  ── cb_qa.check_plate ──► ✓ sign off ──► FROZEN MASTER
   │
   ▼  GATE 2b ─ cb_pipeline.coverage → cb_scene.run → build_keyframe_prompt → cb_gen.generate_image (Nano Banana)
 ONE OPENING KEYFRAME / BEAT  ── cb_qa.check_scene (21-check Definition of Done) ──► ✓ sign off
   │
   ▼  GATE 3 ─ cb_pipeline.gate3 → cb_beats.run
 per beat:  cb_voice.build_dialogue_track (V3)  +  seedance_json  →  cb_gen.generate_video_seedance_ref (Seedance 2.0)
 10–12s TAKE / BEAT  → stitch → SCENE  ──► ✓ sign off
   │
   ▼  GATE 4 ─ cb_pipeline.gate4 → cb_post.run
 ASSEMBLE (crossfade + held tail) → MASTER (−14 LUFS) → STEMS  (+ optional bed: music_brief → cb_gen.eleven_music)
   │
   ▼  EXPORT  (CapCut — final bed + by-ear mix → the finished episode)

 ── all fired / reviewed / signed off / stopped from cb-studio ──
```

---

## GATE 1 · THE DIRECTOR — `cb_director.py` (Gemini)

**The mind** (read at runtime: the director skill + cinematography skill + locked canon + cast lock). The system prompt opens:

```
You are the Crystal Bears DIRECTOR — an Oscar-calibre animation director doing world-class SCRIPT BREAKDOWN.
FOUR PIXAR MASTERS SHAPE EVERY DECISION YOU MAKE — internalise them as your METHOD, not a flavour:
• PETE DOCTER — lead with the FEELING; the emotion is the architecture… track the hidden inner NEED beneath the
  outward want… hold the BITTERSWEET… carry the most important feelings WORDLESSLY.
• JOHN LASSETER — STORY & CHARACTER first; believably ALIVE… SINCERITY over cynicism ALWAYS… performance (the 12
  principles), alive through acting, not bigness.
• PATRICK LIN (DP — CAMERA) — SEE every shot as a composed film frame; lens/height/distance chosen for the FEELING.
• JEAN-CLAUDE KALACHE (DP — LIGHT) — light is STORY; a deliberate colour script per beat.
… plus the NORTH STAR operate-it-every-beat block (want/need/crystalTruth, the surrender, the wordless held beat,
  the same-second co-watch, no villain).
```

**Six staged passes:** `theme_lock` → `beat_map` → `scene_coverage` *(per scene)* → `braintrust` *(per scene)* → `derive_plate` *(per scene)* → assemble.

**The BEAT — the data structure** (each beat in the package):

```
slug · scene · characters[] · speakers[] · keenWristbands · durationSec · pillar · intensity
storyBeat · emotionalIntent · physicalFeeling
want · need · crystalTruth · kidRead · adultRead · theGame · wordlessHeld     ← North-Star fields
light · atmosphere · motionTempo · grade
cuts[] { n, framing, action, dialogue ("NAME: line"), delivery }            ← the internal cut-list (verbatim lines)
cameraArc · pacingVerbs · pauseHold · performance{surface,underneath,innerThought}
crystalGlow · beautyMoment · startState · keyframePrompt · i2vPrompt · soundIntent
continuity{opensFrom,carryToNext,screenDirection} · check{focalSubject,emotionalRead,heartCheck}
```

**Example — beat 1.B1 (the cuts, verbatim):**

```json
"cuts": [
 { "n":1, "framing":"wide establishing, slow organic push-in (24mm)",
   "action":"Tall glowing flowers sway in the dawn-lit canopy; Fuzzby weaves erratically through the air, humming…",
   "dialogue":"FUZZBY: \"BIZZY-BIZZY-BIZZY, BIZZY-BIZZY-BIZZY…\"", "delivery":"fun sing-song rhythm, manic energy" },
 { "n":2, "framing":"insert, quick whip-pan",
   "action":"Fuzzby scoops pollen, over-rotates, bumps a leaf, and instantly snaps upright, chest out.",
   "dialogue":"FUZZBY: \"Nailed it.\"", "delivery":"confident, completely ignoring the fumble" },
 { "n":3, "framing":"context mid (50mm)",
   "action":"Zenny glides in smoothly frame-right. Fuzzby freezes mid-air frame-left, caught.",
   "dialogue":"ZENNY: \"Fuzzby… why are you humming?\"", "delivery":"calm, smooth, precise" } ]
```
> **Dialogue is locked verbatim** — the Director breaks the final script *down*, never rewords a line.

---

## GATE 2a · FOUNDATION — the plate · `build_plate_prompt` → Nano Banana

**Refs:** the location's signed-off library scene shot (layout lock). **Influences in the prompt:** Eggleston + Jessup. **THE ACTUAL PROMPT (Scene 1):**

```
A cinematic ESTABLISHING ENVIRONMENT PLATE — Rainforest — giant sunlit pollen flowers, bee's-eye wide. Scene
direction (the Director's intent for this empty stage): A bee's-eye-level wide shot of a lush rainforest canopy…
massive bell-shaped flowers bursting with glowing yellow pollen… warm golden-amber morning sun in god-rays…
Empty of characters. Match the LAYOUT, perspective and screen direction of the reference image EXACTLY … but with
EVERY character REMOVED — an empty set. Time & weather: Morning, Clear, warm breeze, distant rumble of thunder at
the end. Composition & camera: wide-to-medium lens, eye-level — real layered depth (soft FG / sharp MG /
atmospheric BG bokeh). Colour & light: ONE dominant motivated colour temperature; warm god-rays + soft teal fill…
STYLE: Premium feature-film 3D-CGI … painterly-but-real, never flat. PRODUCTION DESIGN (Ralph Eggleston — the
colour script; Harley Jessup — warm, hand-crafted worlds): build the WORLD as the FIRST CHARACTER… The landscape
is the first actor. CINEMATOGRAPHY (Patrick Lin — camera; Jean-Claude Kalache — lighting): a deliberate MOTIVATED
establishing FRAME… LIGHT IS STORY… THE CRYSTAL BEARS WORLD: weave just 2-3 SUBTLE ambient crystals… This is an
EMPTY stage: absolutely no characters… No text, captions, logos or watermarks; 16:9.
```
**QA:** `cb_qa.check_plate` → ✓ sign off → the plate becomes the **frozen master**.

---

## GATE 2b · KEYFRAMES — the still · `build_keyframe_prompt` → Nano Banana

**Refs:** the frozen plate + each character's turnaround. **Reference-first** (points, never describes). **Influence:** Glen Keane. **THE ACTUAL PROMPT (1.B1):**

```
REFERENCE IMAGES:
[Image 1: Ep1_S1_plate.png] — SCENE: copy environment, camera and composition exactly.
[Image 2: CB_Fuzzby_turn4.png] — FUZZBY: build 100% accurate to this reference — IMMUTABLE, written in stone: add
   NOTHING to Fuzzby and remove nothing (no extra props on the body, accessories, items, markings or attributes
   the reference does not show). One Fuzzby only — do not reproduce the reference's row of views.
[Image 3: CB_Zenny_turn4.png] — ZENNY: … (immutable, one Zenny only) …

TASK: Single production-quality 3D-CGI film still from "The Crystal Bears".
SHOT: S1_1.B1 · Type: wide establishing · Camera: eye-level · Placement: Fuzzby frame-left, Zenny frame-right
OPENING FRAME — the START of this beat, before the action resolves:
   Fuzzby frame-left mid-air zig-zagging between giant glowing flowers, pollen sacks on legs. Zenny not yet in frame

DIRECTION (Glen Keane — the pose must FEEL, not just look):
   Find the ONE opening pose that already ACTS — a clear line of action and irresistible appeal, reading in
   silhouette so the emotion lands off the still before any motion. Truthful acting… one crisp still, no motion
   blur. Do NOT show the payoff.
CINEMATOGRAPHY: motivated camera, real depth, soft key + gentle rim; match the lighting mood of Image 1.
STYLE: Premium Pixar / DreamWorks feature quality — soft GI, plush fur, big expressive eyes, golden pollen, motes,
   aquamarine crystals, shallow DoF. Never flat.
CONSTRAINTS:
   Copy scene and camera from Image 1 exactly.
   Build each character EXACTLY and ONLY as its reference shows — IMMUTABLE… if the staging names something on a
   character its reference lacks, do NOT add it — the character reference never changes.
   SCALE — keep every character at its EXACT canonical size… Largest → smallest: Fuzzby > Zenny. Fuzzby = the
   BIGGER of the two bees; Zenny = the SMALLER bee.
   One of each named character. One coherent frame — not a collage. Sharp 2K 16:9. No text/UI.
```
**QA — the Definition of Done** (`cb_qa.check_scene`, 21 report-only checks): resolution/aspect · anatomy · wrong-character · extra-character · bee-with-crystal · wrong-location · soft-focus-face · face-collage · bad-crop · lighting · transient-prop · crystal-state · style · unsafe-face · text · **ADDED_PROP** · **SIZE_MISMATCH** · **WEAK_POSE** · **BELOW_BAR** (world-class bar) · **PLATE_DRIFT**. → review the flagged → regen → ✓ sign off.

---

## GATE 3 · CLIPS — `cb_beats.run` → V3 voice + Seedance 2.0 ref2vid

**Per beat:** build the cut-ordered V3 voice track, then one 10–12s ref2vid take (keyframe = TRUTH + turnarounds + voice + the multi-shot prompt). **Influences:** animation = Lasseter/Dohrn/Docter/Brumm; voice = Romano/Docter/Brumm.

**THE VOICE — `cb_voice.direct_line`** (never rewords; tag = colour, text = acts; play the need):

```
Input : Fuzzby, "Nailed it.", with a need leaking under a proud surface
Output: [proudly] Nailed it. [gulps]        ← the bravado, with the fear leaking under it
```
*Rules: model=eleven_v3 · stability ≤0.40 (surrender drops to the floor) · 1–2 tags at the shift · signature leads (Fuzzby `[proudly]`, Zenny `[deadpan]`) · phonetic name lock · the wordless beat = silence.*

**THE SEEDANCE PROMPT (1.B1) — the actual JSON:**

```json
{
 "physical_feeling": "Joyful wonder at the magical world, giving way to comedic affection for Fuzzby's energy.",
 "lands_in": "the first ~2 seconds — the feeling must ARRIVE immediately",
 "identity_lock": "The opening keyframe is TRUTH — copy every character EXACTLY… Each character is IMMUTABLE: add
   NOTHING and remove nothing… Add ONLY motion and performance. No morphing, no appearing/disappearing items.",
 "scale": "SCALE — keep every character at its EXACT canonical size… Largest → smallest: Fuzzby > Zenny…",
 "animation_direction": "ANIMATION DIRECTION (Lasseter/Toy Story — appeal + weight + the 12 principles; Dohrn/
   Trolls — joy, music-on-the-beat, hugs; Docter — the wordless held beat; Brumm/Bluey — micro-acting + the
   co-watch): animate FORWARD… WEIGHT IS NON-NEGOTIABLE… NO sliding/floating/rubber-limbs (the anti-floaty cure).
   Performance over bigness… comedy is catch-and-release… HOLD THE ACHE… the Crystal Call is a SURRENDER.",
 "take": "ONE continuous take. Perform the internal cuts below in order — Seedance directs the cuts, camera, timing.",
 "duration_seconds": 12,
 "opening_frame": "Fuzzby frame-left mid-air zig-zagging between giant glowing flowers…",
 "camera": "Starts wide (24mm) to show the scale of the safe world, then snaps to mid-shots as the comedy begins.",
 "cuts": [ {n:1 … "FUZZBY: \"BIZZY-BIZZY-BIZZY…\""}, {n:2 … "FUZZBY: \"Nailed it.\""}, {n:3 … "ZENNY: \"Fuzzby… why are you humming?\""} ],
 "performance": { "surface":"Fuzzby manic and proud; Zenny composed", "underneath":"Fuzzby wants to be seen as a
   professional; Zenny finds him endearing but exhausting", "innerThought":"…" },
 "audio": "Seedance SCORES the take: synchronised in-world SFX (the bonk, slide-whistle, splash) AND timed comedy +
   emotional MUSIC that lands ON the action (the sting the instant he hits the tree, the button on the deflate) —
   its timing is the point. The lip-synced acted voice stays FORWARD on top. (Post reviews / keeps / trims / replaces.)",
 "negative": "no on-screen text, no morphing, no extra/missing limbs, no flicker, no style drift"
}
```
> The keyframe is `@Image1` (the take animates *forward* from it); the V3 voice is `@Audio1` (lip-synced); Seedance directs the internal cuts + scores the SFX & timed music. → stitch the beats → the scene → ✓ sign off.

---

## GATE 4 · POST — `cb_post.run` (CURATION — the quality filter, not composition)

**The hardest creative work is Gate 3; Gate 4 is the quality filter.** Post **listens and decides what Seedance got right — keeps what works, trims or replaces what doesn't.** **Assemble** (crossfade, NO jumps, held tail — keeping the clip's voice + SFX + Seedance music) → **master** (−14 LUFS) → **export stems** (picture+voice · music · ambience + CapCut readme). **Influences:** Murch + Nolting (edit), Tom Myers (mix), Bush + Giacchino (the *fallback* bed). **The ElevenLabs Music bed is the FALLBACK, not the default — fired ONLY if Seedance's own music isn't right for a scene.** Julian does the final keep/trim/replace + mix in CapCut.

**THE MUSIC BRIEF — `music_brief`** (only fired for an opt-in bed; ElevenLabs Music). **Actual (Scene 1):**

```
Instrumental orchestral underscore for a warm, gentle children's animated scene set in Rainforest. Theme: spark.
Emotional arc: Joyful wonder… giving way to comedic affection for Fuzzby's exhausting energy; pure character
comedy… escalating physical comedy… Morning Clear, warm breeze, distant rumble of thunder at the end. Soft strings,
light woodwinds, harp and warm pads; tender, hopeful, cinematic but understated. NO vocals, no lyrics, no heavy
drums — a calm bed that sits UNDER spoken dialogue, even dynamics, never overpowering the voices.
```

---

## EXPORT — the final phase

Signed-off scenes assemble into the **finished episode**; the stems hand to **CapCut** for the final bed (if any) and the by-ear mix; **export** the deliverable.

---

## THE CONTROL SURFACE — cb-studio

Every module above is fired, watched, signed off and **stopped** from the studio: Projects → Episodes; per-gate Fire / Sign-off / Stop with live progress; the storyboard + per-beat editors (cuts · Seedance · extra references); the keyframe Foundation (plate + locked identity sheets); character profiles / bibles / Crystal Calls; the QA verdicts per beat. **Run through the system — nothing by hand.**
