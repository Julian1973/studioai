# DISPATCH 001 — 2 July 2026, applied 2026-07-02 by Claude Code (reconciled against a same-day audit pass already in progress)

The patch handed off from the other Claude project (`studio_dispatch_001.patch` + `PACK_ADDENDUM_A.md`) could not be applied with a raw `git apply` — several of its target files (`cb_beats.py`, `cb_post.py`, `cb_segprompt.py`, `cb_retake.py`) had already been edited earlier the same session by a separate, independent 44-finding code audit. Every change below was reconciled by hand against the CURRENT file state, not blind-applied.

## Applied this session, in order:

1. **Rulings taken from Julian** (AskUserQuestion, before any code touched):
   - T2 — a temporary state resolves WITHIN the take it started in; no cross-take continuity-tail chaining.
   - T3 — the "second master" (15 minds / archetypes / compact validators in cb_seedance.py) is KEPT, declared in the Bible as an intentional layer.
   - T6 — Bo confirmed as recurring-guest tier; a canon/characters.json STUB added (no creative content — species, art, voice, bible still needed from Julian).
   - T30 — full 5-phase restructure approved.

2. **T1** — cb_beats.py: a beat WITH dialogue whose V3 track failed now REFUSES to render (Law 5). Wordless beats unaffected. Verified.
3. **T2 (ruling executed)** — cb_beats.py + cb_seedance.py: `_prev_clip_path`, the CONTINUITY TAIL image/text injection, `continuity_video_ref`, `NEEDS_PREVIOUS_TAIL`, `CB_ALLOW_UNAPPROVED_TAIL`, and the `continuity_video` compact-JSON field removed entirely (not merely un-gated). Verified compiles + live smoke test + baseline byte-identical.
4. **T3 (ruling executed)** — Studio Bible Part 4 gains a declared section naming the second master as intentional.
5. **T4** — cb_beats.py + cb_seedance.py: docstrings now state the truth — cb_segprompt prose is the shipped prompt; compact is validation.
6. **T5** — Studio Bible §3.5 states the duration rule once (8–15s clamp, ~10–12s target); the Ep1 SEGMENTS dict was already fully deleted earlier this session (not merely marked for retirement); CapCut readme "replace the voice" language removed.
7. **T6 (ruling executed)** — CRYSTAL_BEARS_LOCKED_CANON.md + config/characters.json + crystal-bears-continuity/SKILL.md: Bo added as a clearly-flagged stub (recurring-guest tier, the one known fact "a cub" included, everything else marked TBD).
8. **T16** — cb_retake.py (now GATE 4 throughout), cb_post.py (now GATE 5 throughout), serve.py (`GATE_NAME` dict corrected + completed for 2a/2b/4/5), app.html (gate rail + a stale scene-spine comment), crystal-bears-continuity/SKILL.md (two stray Gate 4→5 mislabels) — one vocabulary now, verified via grep sweep + live browser check.
9. **T20 / T21** — cb_post.py: crossfade docstring language already corrected earlier this session; CapCut readme voice-swap language removed (T5/T21 overlap, one fix).
10. **T7 — for_beat_v2** — cb_segprompt.py: added, reconciled against the file's already-cleaned state (the old SEGMENTS/build/definitive cluster this patch's context originally anchored against no longer exists — it was deleted earlier this session as dead code). Verified end-to-end against a real Ep1 beat: correct delabeling, correct quote-stripping (including a smart-quote regex bug in the original patch text, fixed), zero callers (genuinely unrouted). Routing decision (switching preview/fire to v2) is still open — needs Julian reading the regenerated prompts first.
11. **Restructure T30, Phase 1 (One Canon)** — root CRYSTAL_BEARS_LOCKED_CANON.md's own stale doctrine fixed FIRST (the "Start+END keyframe per shot" and "native voice + Voice-Changer swap" sections, both superseded earlier this session in the skill docs but not yet in the deeper canon copy) — then all 9 `skills/crystal-bears-*/references/CRYSTAL_BEARS_LOCKED_CANON.md` copies (7 originally known + 2 more discovered: cinematographer, writer) regenerated via a new `tools/sync_canon.py`, stamped and hash-verified. `cb_continuity.py` gained a BLOCK-level drift check (`_canon_sync_findings`). Verified: `--check` passes, drift-injection test caught correctly, baseline prompts byte-identical before/after.
12. **The "two universes" ruling paragraph** (Addendum A) — added to Studio Bible Part 6, clearly marked ADDED AS PROPOSED pending Julian's accept/amend/reject.
13. **T31 / T32** (Addendum A) — logged as open tickets in TICKET_PACK_001.md, not built (T31 needs Gate 5 handoff-pack infrastructure that doesn't exist yet; T32 was queued behind the Bo ruling, which is now resolved, so it can be picked up next).
14. **Docs** — TICKET_PACK_001.md, WORLD_CLASS_ROADMAP.md, RESTRUCTURE_SPEC_T30.md, CLAUDE.md, this file — all rewritten to reflect what was ACTUALLY decided and done this session, not the other Claude's draft dispatch verbatim.

## Verification performed (and re-run after each phase):
- import proof: `cb_pipeline, cb_beats, cb_segprompt, cb_post, cb_retake, cb_qa, cb_continuity, cb_voice, cb_gen` all import clean.
- baseline: `for_beat` on Ep1 beats 1.B1/1.B2/1.B3 byte-identical before and after every change in this dispatch.
- canon: `tools/sync_canon.py --check` passes.
- live: app.html gate-rail change verified in the running studio preview (fresh, non-stale server, zero console errors).

## NOT done in this dispatch:
- Restructure Phases 2–5 (paths.py + physical file moves to engine/shows/studio-ui, the show-profile abstraction, document consolidation, code hygiene). Phase 1 is the highest-value, lowest-risk phase and is complete and verified; Phases 2–5 touch import paths across ~30 files and carry materially higher risk to the live pipeline. Ready to continue on request.
- T8–T15, T17–T19 (Director's prose, physics/budget law, golden set, retake room upgrades, dual loudness masters, Giacchino decision layer, episode master/handoff pack) — all still open, tracked in TICKET_PACK_001.md.
- T31 build (provenance pack) — logged, not built.
- T32 build (cross-episode world ledger) — logged, not built; now unblocked by the Bo ruling.
- Reference art / full character bible for Bo — outside-the-code work, Julian's.
