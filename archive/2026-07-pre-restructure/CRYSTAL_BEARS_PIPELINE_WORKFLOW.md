> **SUPERSEDED (2026-07-02)** — this document predates the Studio Bible and describes an earlier era of the pipeline. The Studio Bible (CRYSTAL_BEARS_STUDIO_BIBLE.md) is the current source of truth; anything here still true has been folded into it. Kept for historical record only — do not build against this file.

---

# The Crystal Bears Pipeline — Gated Workflow (the Producer's run-sheet)

## THE VISION — how the feeling travels from script to screen (read this first)

We take a script that is **meaningful, beautiful, funny and emotive**, and we deliver an **award-winning** animation that looks like a multi-billion-pound Pixar production — and lands *exactly* from the Show Bible: who these characters are, the emotive beat, the heart, the funny.

The chain is one feeling, carried down the line:

1. **The Director understands it as a human FIRST** — the why, what we're trying to achieve, the **social-emotional learning** of *this* episode, which characters carry it, and how the heart and the laughter live through them, the beats, and the funny. (See canon **§0 NORTH STAR** + the Director's §1.5 emotional lens.)
2. **He directs it into scenes and shots** — each scene knows what it's *for*, delivered through shots and beats that are **simple, not complicated, but beautifully emotional and beautifully funny when needed.** Less, held, felt.
3. **We prompt it → build the keyframes → check them at the gate.** The stills already carry the feeling.
4. **The Camera brings it to life** in magical Pixar 3D CGI quality — motion that serves the beat, restrained and alive.
5. **Post binds it together** — sound, music, the mix — into the finished, broadcast-grade film.

**The director is the soul; everyone downstream executes a vision that was *understood* before it was built.** Every gate below exists to protect that feeling on its way to the screen. The test never changes: *will they laugh out loud? will they breathe in? does it reach both the kid and the parent?*

---

**The rule:** the work moves down the line **one department at a time**, and every hand-off is a **sign-off gate**. A department only runs on **approved, locked** input from the department before it. Nothing downstream is generated until the current stage is signed off — that protects both **quality** (catch drift before it multiplies) and **cost** (never spend on video/voice off un-approved frames).

Owned by the **Producer / 1st AD** (the orchestrator — `crystal-bears-master` now; the app's pipeline controller later). Each crew skill is **gate-aware**: it runs its stage, produces its artifact, then **STOPS at its gate and waits for sign-off.**

---

## The line

```
UPLOAD SCRIPT
   │  (Screenwriter — or write with crystal-bears-writer)
   ▼
╔═ GATE 0 — SCRIPT APPROVED ═╗
   │
   ▼
SHOT LIST            (Director → the shot package)
   │
   ▼
╔═ GATE 1 — SHOT LIST SIGNED OFF ═╗   ← review coverage, beats, intent BEFORE any spend
   │
   ▼
KEYFRAMES            (DP — approved shots → keyframe prompts → key images)
   │
   ▼
╔═ GATE 2 — KEYFRAMES SIGNED OFF ═╗   ← the consistency checkpoint; regen any shot; lock the look
   │
   ▼
MOTION / CLIPS       (Camera — locked keyframes → i2v prompts → video clips)
   │
   ▼
╔═ GATE 3 — CLIPS SIGNED OFF ═╗
   │
   ▼
POST                 (Sound + Edit + Mix → final cut)
   │
   ▼
╔═ GATE 4 — FINAL CUT SIGNED OFF ═╗ → EXPORT
```

**Runs in parallel once GATE 1 is locked** (they only need the approved shot list, not the visuals):
- **Voice** (Voice Director → ElevenLabs V3 dialogue) → its own sign-off
- **Music** (Composer → Suno brief → track) → its own sign-off

Both feed into **Post**, so they must be signed off before GATE 4.

---

## What flows down the line

One artifact — **the shot package** — enriched at every stage, never re-created:

| After… | The shot package gains |
|--------|------------------------|
| Director (Gate 1) | shots: coverage, framing, prompts, dialogue+speaker→voiceId, intent block |
| DP (Gate 2) | each shot's **key image** (+ approved/locked flag, regen history) |
| Camera (Gate 3) | each shot's **video clip** |
| Voice / Music | the **dialogue tracks** + the **music track** |
| Post (Gate 4) | the **final stitched film** |

---

## Each shot/stage has a state

`draft → in-review → approved → locked` (or `→ regenerate` back a step).
- A stage can only start when its inputs are **locked**.
- **Per-shot granularity at Gate 2 & 3:** approve good keyframes/clips individually, send only the failures back for regen — the rest stay locked. (No re-running the whole batch.)
- The **Continuity Supervisor** runs an automatic check *before* each gate (against canon + the locked reference images) and flags drift for the human reviewer.

---

## How we operate it

- **In this environment (now):** I run a department, then **pause and present the artifact for your sign-off**, then run the next only when you approve. (When I directed Ep5 just now I ran straight through to *prove the Director skill* — but in real operation it stops at GATE 1.)
- **In the app (built):** the gates are per-shot **approve / lock** buttons + an **async job queue** for the slow stages (image and especially video generation take minutes — they queue and notify, they don't block). This is exactly why the merged build needs the jobs table + per-shot lock states.

---

## Build implication

Every crew skill is written to be **gate-aware**: produce → stop → wait. The **DP / keyframe skill** (next to build) must:
1. take only the **approved** shots from the shot package,
2. generate one **keyframe per shot** (reference-anchored to the locked anchor images),
3. present them **per shot for sign-off**, supporting **regenerate** on any single shot,
4. write the locked key image back into the shot package and **stop at GATE 2.**

---

## Scene-by-scene execution — the prudent order (2026-06-19, Julian)

Production runs **scene by scene, with a gate per scene** — never 45 shots across the board (or they're all wrong at once). For each scene, at the keyframe stage (Gate 2) and again at the clip stage (Gate 3):

1. **Calibration shot.** Render the scene's **FIRST shot alone** (e.g. 1.1). Confirm the look, lighting, character consistency, and — for a new location — the environment are right.
2. **Sign it off.** If it's wrong, regenerate just that one shot before spending on the rest.
3. **Batch the scene.** Render the remaining shots of the scene, **feeding the approved first keyframe back in as an extra intra-scene consistency reference** (alongside the character + scene anchors).
4. **Per-scene gate.** Sign off the whole scene, then move to the next.

Rationale: catch a wrong look on shot 1 of a scene cheaply, before it multiplies. File naming uses the shotCode (e.g. `Ep3_1.1_*`).
