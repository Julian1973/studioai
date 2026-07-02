# CLIP_DONE — the Definition of Done for a Gate-3 clip

The temporal sibling of `KEYFRAME_DONE.md`. A keyframe is one image; a CLIP is that image **in motion**.
Gate 3 runs this QA **automatically** as each clip renders (`cb_qa.check_clip`, hooked in `cb_beats.py`):
the machine is the QA, not Julian's eye. It is **advisory** — it prints a verdict, writes a sidecar, and
**never** auto-overwrites or blocks a render (a false flag must never destroy a good take).

## THE FOUNDATION
One signed-off OPENING keyframe per beat is the single image the clip is built from. Seedance
reference-to-video animates ONE 8–15s take forward from that keyframe (it runs its own internal cuts).
A clip is DONE only when it holds the keyframe's truth IN MOTION — identity, story-state, world and
weight — for the whole take. Bar = world-class feature 3D-CGI (Pixar / DreamWorks), warm, ages 4–8.

## BLOCK vs NOTE (severity — the anti-alert-fatigue split)
- **BLOCK** (re-render-worthy, fails the take): `CLIP_MISSING`, `CLIP_WONT_DECODE`, `CLIP_FROZEN`,
  `CLIP_MORPH`, `CLIP_IDENTITY_DRIFT` (corroborated), `CLIP_POP_CHARACTER`, `EXTRA_CHARACTER`,
  `BEE_WITH_CRYSTAL`, `UNSAFE_FACE`.
- **NOTE** (advisory, surfaced for the human, does NOT fail the take): `CLIP_FLOATY`, `CLIP_STATE_*`,
  `ANATOMY_DEFECT` (too noisy on a cartoon bee's small/tucked limbs to auto-fail), `CLIP_BAD_DURATION`,
  `LOW_RESOLUTION_CLIP`, `BAD_ASPECT`, and any single-frame (uncorroborated) identity/cast hit.

## WHAT IT CHECKS
**Technical (deterministic — ffprobe/ffmpeg, run first):**
1. FILE exists, non-zero, decodes, has a video stream. (`CLIP_MISSING`, `CLIP_WONT_DECODE`)
2. DURATION 7.5–15.5s. (`CLIP_BAD_DURATION`, note)
3. RESOLUTION ≥ 1280 wide (the Seedance 720p floor — NOT the 2K keyframe floor), 16:9. (`LOW_RESOLUTION_CLIP`/`BAD_ASPECT`, note)
4. MOTION present — a near-zero consecutive-frame luma diff = a frozen near-still. (`CLIP_FROZEN`, block; gated to beats that should move)

**Per-frame identity (vision — the SETTLED frames: first + last, a MOTION-safe checklist):**
5. Reuses the keyframe gate with `clip_frame=True`, which DROPS the held-keyframe-only checks
   (pose / sharpness / bar / crop / lighting / style / added-prop) that false-fire on a motion frame,
   keeping only identity / anatomy / cast / size / crystal / transient-substance.
6. Noisy codes (`ANATOMY_DEFECT`, `CLIP_IDENTITY_DRIFT`, `EXTRA_CHARACTER`) only escalate when seen on
   **≥2 settled frames**; a lone hit is a NOTE.

**Across the take (vision — ONE multi-frame call, the keyframe = IMAGE 1 truth):**
7. IDENTITY stability first→last, no `CLIP_MORPH`; no `CLIP_POP_CHARACTER`; no `CLIP_FLICKER` within a shot
   (internal cuts are told to the model so a cut isn't mistaken for a flicker).
8. STORY-STATE: a substance the beat NAMES at start (pollen moustache, dirt, wet fur) is present at the start
   AND still present at the end **when it must carry** — carry is decided by the NEXT beat's `startState`
   (if B4 opens "covered in pollen", B3 must NOT end clean), overriding any "clean/wipe" resolve-verb. (`CLIP_STATE_DROPPED`, note)
9. WEIGHT: grounded motion, no float/skate/glide. (`CLIP_FLOATY`, advisory — weight is a motion property a
   still cannot prove; this is best-effort.)

## COMEDY LICENCE
On `comedyMode == BIG` beats the doctrine INTENTIONALLY exaggerates — squash/stretch, smear/streak frames,
extreme poses. Both the per-frame and multi-frame passes are told this is CORRECT and must PASS; identity is
judged only where motion settles, never on the gag peak. The QA must never punish the comedy.

## ROBUSTNESS
- Vision calls retry (back-off) on transient 429/500/503; a true infra failure returns `QA_UNAVAILABLE`
  (grey "QA skipped"), NEVER a red content fail.
- ffmpeg/ffprobe missing → `QA_UNAVAILABLE`, not a clip fault.
- Frames extract to a `tempfile.mkdtemp` that is always cleaned in `finally`.
- The whole check is wrapped at the call-site so a QA hiccup never crashes the render loop or the stitch.

## OUTPUT (mirrors `check_done_frame`)
`{ok, reasons:[BLOCK codes], notes:[NOTE codes], fix_hint, verdict}` → printed to the live Gate-3 log AND
written to a `media/{ep}_{beatCode}_{slug}.qa.json` sidecar the studio reads. `ok=False` only on a BLOCK;
`ok=None` = QA unavailable; `ok=True` passes even with advisory notes.

## HONEST LIMITS
- ANATOMY and STORY-STATE are **advisory** — vision miscounts stylised limbs and can miss a subtle state drop;
  trust the note as a prompt to LOOK, not a verdict.
- WEIGHT/float is best-effort (no per-still proof of motion).
- Re-run standalone any time: `python3 cb_qa.py clips <package.json> <scene>`.
