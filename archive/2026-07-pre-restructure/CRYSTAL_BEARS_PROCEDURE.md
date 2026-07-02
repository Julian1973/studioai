> **SUPERSEDED (2026-07-02)** — this document predates the Studio Bible and describes an earlier era of the pipeline. The Studio Bible (CRYSTAL_BEARS_STUDIO_BIBLE.md) is the current source of truth; anything here still true has been folded into it. Kept for historical record only — do not build against this file.

---

# THE CRYSTAL BEARS PROCEDURE — script → finished shot

**Governing principle: the PROCEDURE drives the prompts. We never hand-prompt.**
To change what comes out, you change the *procedure* — the structured data and the config — and re-run.
You never edit a prompt for a single shot. A fix made in the procedure is permanent: it applies to
that shot, every other shot, and every future episode. A fix made in a prompt is drift waiting to happen.

The prompts are *generated* by `cb_prompts.py` from data. Nobody writes them by hand. If a prompt is
wrong, the data behind it is wrong — fix the data.

---

## 1. Sources of truth (set once, reused everywhere)

| Source | Holds | File |
|--------|-------|------|
| Show Bible | canon — bears, crystals, pillars, world rules | `CRYSTAL_BEARS_LOCKED_CANON.md` |
| Characters | anchor image, voiceId, **sizeRank**, cadence; Keen's wristband-state anchors | `cb-gen/config/characters.json` |
| Locations | per scene: **master** frame, **space/geography**, **time**, **weather**, lighting | `cb-gen/config/locations.json` |
| Episode arc | the day's lighting + Five-Pillars progression | `cb-gen/config/episode_arc.json` |
| Continuity | **visions** (→ real scene + materialisation), **recurring assets** (colour + scale + look) | `cb-gen/config/continuity.json` |

These are the only place facts live. The drivers read them; they are never duplicated into prompts.

**Before any shot is prompted, a CONTEXT COMPLETENESS AUDIT runs** (`cb_context.py`, a pre-flight on gates 2 & 3): it confirms the full context is present and locked — the scene + the previous scene, every reference, the show bible, the storyline and the script — and FLAGS anything the script mentions that isn't reference-locked (a cuff, a satchel, a prop) BEFORE it renders. Gaps are caught by the process, not the eye.

---

## 2. The stages (gated — STOP and sign off at each)

```
SCRIPT → [1 Director plan] → [2 DP keyframes] → [3 Camera clips] → [4 Post] → finished scene
                 sign off          sign off           sign off         sign off
         (continuity check runs at every gate; a gate won't fire until the one before is signed off)
```

**Stage 1 — Script → SHOT PACKAGE (the Director).**
The script is broken into shots, and *all directing is encoded as DATA on each shot* — never prose to be
prompted later. Each shot carries:

- `shotCode`, `scene`, `sceneNumber`
- `characters`, `speaker`
- `keenWristbands` (none / vacant / crystal)
- `shotSize`, `angle`, `movement`, `lens`, `duration`
- `action`, `dialogue`
- `intent` {pillar, beat, emotion, intensity, musicMood, sfxTags, humour}
- `performance` {surface, underneath, innerThought}
- `beats` [{t, do, emotion}] — timed, one action per beat, holds count
- `props` [{name, state}] — exact position/state of every prop in this shot
- `keyframePrompt` / `i2vPrompt` seeds (optional nudges, not the whole prompt)

Vision/flashback shots are declared in `continuity.json`. → **Gate 1 sign-off.**

**Stage 2 — KEYFRAMES (the DP).** FIRST the establishing **MASTER is built with the full references + identity lock and VISUALLY VERIFIED** (`cb_pipeline.py master <scene>`) — the foundation must be right before anything derives from it. Then the software derives every shot from that verified master + config + the
shot's data. Each shot gets a **START and an END** frame. → **Gate 2 sign-off (the images).**

**Stage 3 — CLIPS (the Camera).** Image→video (Seedance) from the *locked* keyframes; native voice kept as
the lip-sync guide (final via ADR). When the clips finish they are **auto-stitched** into the scene's
**completed-animation cut** (crossfades + held tail, guide audio, `_animation.mp4`) — it appears in the studio's
**Animation** tab immediately, no Post required. → **Gate 3 sign-off.**

**Stage 4 — POST.** Takes the cut to the finished scene: continuous music/ambience (ducked) + SFX, mastered,
exported as `_complete.mp4` + stems — shown in the **Post** tab. → **Gate 4 sign-off.**

> Animation tab = the stitched cut (picture + guide audio). Post tab = the whole thing (full mix). Two phases.

---

## 3. What the software bakes into every prompt — automatically, from data

The Director/DP/Camera never type these. `cb_prompts.py` assembles them from §1 + the shot data:

- **Identity** — character = reference-only (the anchor); never described. PLUS an **identity lock**: each character's signature features (`characters.json key_features`, e.g. Keen's head-tuft) are reinforced on every shot so the anchor can't silently drop them.
- **Size** — relative bear sizes from `sizeRank` (Amie < … < Howey).
- **Recurring assets** — colour + scale + look locked (rose-quartz bowl, red-sail boat, the wand).
- **Props + physics** — each prop's exact state/position, continuous shot-to-shot; nothing clips, floats,
  vanishes, teleports or duplicates.
- **Cumulative world state** — what's loaded/changed PERSISTS and grows (the parcel Keen loads into the boat in
  3.1 stays in the boat in every later shot + into Scene 4). `continuity.json persistent: [{item, in, fromShot}]`.
- **Removal/loss** — what's lost/destroyed is GONE and forbidden afterward (Keen loses the boat at 7.3 → no boat
  from 7.4 on). `continuity.json lost: [{name, atShot, reason}]`.
- **Wristbands** — Keen's state for the shot.
- **Vision** — derived from the real scene's master + its magical materialisation.
- **World** — time, weather, space, lighting (the day moves forward; weather transitions logically).
- **Acting** — performance intention (surface/underneath/inner thought) + timed beats.
- **Dialogue** — cast + active-speaker lock (only the speaker forms words), ~2 words/sec, native-voice guide.
- **LOCKS** — no redesign, identity/voice swap, floating limbs, camera shake, unrequested cuts.
- **Faithful to the script** — the frame IS the script: add NOTHING not in the action (no extra characters, animals, objects, background), omit nothing it states.

**THE SELF-CORRECT LOOP (gate 2):** produce → CHECK (3 checks: context audit, continuity, visual QA on the pixels) → if a shot is wrong, find it & change it (regenerate it using the QA's findings as the correction) → re-check → if right, it stays. Bounded rounds; the master is never auto-changed (it cascades — flagged for review). Nothing reaches sign-off with a continuity or faithfulness break. `cb_pipeline.py autofix <scene>`.

---

## 4. THE CORRECTION RULE — fix the procedure, not the prompt

When a shot is wrong, do **not** write a prompt. Find the layer that owns the problem, fix the DATA/CONFIG
there, and re-fire the gate. The output regenerates correctly — and stays correct everywhere.

| Symptom | Fix HERE (the procedure) | Not this |
|---------|--------------------------|----------|
| Character looks wrong / off-model | the **anchor** in `characters.json` | ~~describe them in the prompt~~ |
| A bear is the wrong size vs others | `sizeRank` in `characters.json` | ~~"make him smaller"~~ |
| A recurring prop's colour is wrong | `appearance` in `continuity.json` | ~~per-shot colour note~~ |
| A prop's size changes between shots | `scale` in `continuity.json` | ~~"same size as last shot"~~ |
| A prop is in the wrong place / vanished | the shot's `props` state | ~~"put the wand back"~~ |
| Wrong wristband state | the shot's `keenWristbands` | ~~prompt the wristbands~~ |
| A vision doesn't match its real scene | `continuity.json` vision (and rebuild the real scene first) | ~~redraw the vision freehand~~ |
| Wrong time of day / weather | `locations.json` | ~~"make it morning"~~ |
| Acting is flat | `performance` + `beats` on the shot | ~~"act better"~~ |
| Framing is wrong | `shotSize` / `angle` on the shot | ~~"zoom in"~~ |
| Wrong character speaks / mouths move | `speaker` / dialogue labels | ~~"only X talks"~~ |
| Continuity across scenes | `continuity.json` (visions, recurring) | ~~fix each shot by hand~~ |

The free-text **regenerate note** in the studio exists only for a genuine one-off render glitch (a stray
artefact on an otherwise-correct shot). It is **never** the fix for anything systemic. If you find yourself
writing the same note on more than one shot, that's a procedure fix, not a prompt.

---

## 5. Why this holds the quality bar

Every correction lives in the procedure, so it is **permanent, consistent, and inherited** by all shots and
all future episodes. There is no per-shot freelancing for the AI to drift from. Script in → world-class shots
out, scene after scene — because the procedure, not the prompt, is what we maintain.
