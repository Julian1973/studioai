# CRYSTAL BEARS STUDIO — TICKET PACK 001
*Everything from the 2 July 2026 audit session, one pack. Each ticket: the files, the change, the definition of done. Priorities: P0 = the floor (nothing else ships first) · P1 = this month · P2 = next. Source of truth order: Locked Canon > Studio Bible > this pack.*

*Status legend: ✅ DONE (2026-07-02, applied + verified this session) · ⏳ OPEN.*

---

## THE FLOOR (P0)

**T1 · Voice failure refuses the render** ✅ DONE
cb_beats.py. A failed ElevenLabs track now refuses and skips the beat when it has dialogue — no silent fallback to Seedance's native voice. Law 5.
DoD: no clip can exist whose voice is not the acted V3 track; the refusal prints its reason. Verified.

**T2 · Continuity tail: decided — resolves within each take** ✅ DONE (Julian's ruling)
cb_beats.py + cb_seedance.py + Studio Bible Part 4. Ruling: a temporary state resolves WITHIN the take it started in — it never carries across a take boundary. The dead continuity-tail chaining machinery (`_prev_clip_path`, the CONTINUITY TAIL image/text injection in `cb_beats.run`, `cb_seedance.continuity_video_ref`/`NEEDS_PREVIOUS_TAIL`/`CB_ALLOW_UNAPPROVED_TAIL`) is removed entirely, not merely un-gated.
DoD: one doctrine in the Bible; the code path no longer exists. Verified (compiles, live smoke test, `continuity_video` field confirmed gone from every prompt-building path).

**T3 · The second master: declared KEPT** ✅ DONE (Julian's ruling)
cb_seedance.py, cb_beats.py, Studio Bible Part 4. Ruling: the 15 minds / archetypes / compact validators are an intentional, declared second validation layer underneath the Director's chair — not leftover. The Bible now states this explicitly.
DoD: the Bible and the code tell one story about who may refuse a render and why. Done.

**T4 · Docstrings match the wiring** ✅ DONE
cb_beats.py, cb_seedance.py. `gate3_prepare` and `get_seedance_prompt` now state the truth: `cb_segprompt.for_beat` prose is the shipped prompt for every beat; the compact builder is validation/readiness + fallback only.
DoD: a fresh Claude Code session reading only docstrings would build the current truth. Done.

**T5 · Bible amendments from the audit** ✅ DONE
CRYSTAL_BEARS_STUDIO_BIBLE.md, cb_post.py. WING LAW usage recorded; the duration rule stated once (8–15s clamp, ~10–12s target — §3.5); the Ep1 hand-authored SEGMENTS dict was already fully retired this session (deleted, not merely marked); "replace the voice" removed from the CapCut readme.
DoD: no two documents disagree. Done.

**T6 · Ruling on Bo** ✅ DONE (Julian's ruling — stub only)
CRYSTAL_BEARS_LOCKED_CANON.md, config/characters.json, crystal-bears-continuity/SKILL.md. Ruling: confirmed as recurring-guest tier. A `characters.json` stub exists (species/appearance/voice/bible all still TBD — Julian's to supply) so canon/cast-lock lookups aren't blocked. Reference art is still outside-the-code work.
DoD: Ep2 is producible under the cast lock once Julian supplies reference art + bible content; canon/pipeline side is unblocked today. Partially done — code/canon side complete, creative content still pending Julian.

**T16 · One gate numbering, everywhere** ✅ DONE
cb_retake.py (now says GATE 4 throughout), cb_post.py (now says GATE 5 throughout), serve.py (`GATE_NAME` dict corrected + completed), app.html (gate rail + scene-spine comment fixed), Studio Bible, crystal-bears-continuity skill. Canonical map: 0 Write · 1 Direct · 2 Keyframe (2a anchors, 2b coverage) · 3 Animate · 4 Retake/Edit · 5 Post.
DoD: grep for gate numbers returns one vocabulary across code, UI and Bible. Done.

---

## THE PROMPT (P1)

**T7 · for_beat_v2 added, UNROUTED** ✅ DONE (additive only — NOT switched on)
cb_segprompt.py. The faithful translator: the Director's light, atmosphere, motionTempo, cuts, pauseHold, physicalFeeling and soundIntent ship inside the baked law; names delabeled (first mention full, short label after); spoken words stripped from prose (they live only in @Audio1); frame sides restored to REFERENCE LAW; the empty plate text never ships as SCENE. Verified against a real Ep1 beat — richer output, zero callers (unrouted, exactly as intended).
DoD (routing, still open): preview and fire both call for_beat_v2; all 44 Ep1 prompts regenerate and read at the You Mind standard; the mechanical checks (no names, no spoken words, tokens ordered) pass on every one. ⏳ Needs Julian's eyes on the regenerated prompts before switching the routing point.

**T8 · The Director authors the prose (the next level)** ⏳ OPEN
chairs skill + cb_director.py output schema. Add sceneProse and actionProse to the Director's contract.

**T9 · Physics as a clause, plus the prompt budget law** ⏳ OPEN
cb_segprompt.py, cb_continuity checks, Studio Bible.

**T10 · The golden set harness** ✅ DONE (2026-07-02)
engine/cb_golden.py + engine/goldens/. Stores the 3 Seedance baseline prompts (1.B1-1.B3) + the 4 Scene-1 keyframe prompts (1.B1-1.B4, anchor + chained) as of the T33 fix pass; `python3 cb_golden.py diff` compares current output against them, `capture` deliberately overwrites (only after a diff has been shown).
DoD: one command diffs current output vs the stored golden set; no prompt-touching commit merges without that diff shown (CLAUDE.md hard rule). Verified: captured clean, `diff` reports ZERO DIFFS against itself.

**T33 · Field-to-frame audit (Director-field consumption sweep)** ✅ DONE (2026-07-02)
tools/field_audit.py (mechanical, re-runnable: Pydantic-introspects the schema, greps engine/*.py, flags zero-hit fields) + FIELD_TO_FRAME_AUDIT.md (the full judged report — 74 fields, 18 LEAK, 18 PARTIAL, fixed vs deferred, with why). Same bug class as the startState/shotSize find (2026-07-02).
DoD: one report of all leaks — done (FIELD_TO_FRAME_AUDIT.md). Every LEAK/PARTIAL confirmed in the keyframe, voice or QA paths fixed in this pass (18 fixes across cb_prompts.py, cb_qa.py, cb_director_eye.py, cb_voice.py) with baseline proof (cb_segprompt.py byte-identical). Leaks outside those three paths (the Seedance-clip path, and items needing a design decision — director_mode, cameraArc/staging-verification QA, performance_notes, writerNote) logged in the report, not silently fixed or dropped.
Follow-up (same day, found reviewing the regenerated Gate 2b keyframes): a chained beat's environment was competing against a text re-description of the scene's location and losing — 1.B2-1.B4 drifted to a different world than the approved plate. Fixed in build_keyframe_prompt (the chain image is now the sole environment source for a continuation beat); locked as CLAUDE.md hard rule 12 + Studio Bible §3.1. Verified: QA 4/4 PASS (was 1/4, PLATE_DRIFT on the other 3), confirmed visually, golden set diffed and recaptured.

Three further rulings (same day, Julian, after reviewing the regenerated keyframes):
1. Scene 1's location/look/definingFeature/cameraHeight/sceneShotName/lighting rewritten at the TRUE source — discovered scene_cfg() reads config/locations.json (a separate cache), not the beat package directly, so the earlier fix hadn't actually reached the pipeline until this. Fixed in both places; swept every consumer (segprompt/seedance/QA/pipeline). Golden set re-blessed.
2. for_beat_v2's dangling-possessive bug fixed (delabel now runs before the quote-stripper, with proper apostrophe boundaries) — FOR_BEAT_V2_REVIEW_EP1_SCENE1.md regenerated clean. The kept validator's gag-carryover check (wrong direction — fixed to check the NEXT beat, demoted to a NOTE) and gag-lock content check (hardcoded "moustache"/"goatee" moved to canon/gag_locks.json, passing silently when empty) were ruled drift, not protection, and fixed; swept for other hardcoded story words in cb_seedance.py's validators (found and reported, not all fixed — see the commit for the full list).
3. tools/sync_scenes.py — a sync/hash check for config/locations.json vs the beat package (mirrors tools/sync_canon.py), wired into cb_beats.render_readiness() as a hard BLOCK on drift, not a silent divergence.

Result: render_readiness() reports READY_TO_RENDER on all of Ep1 1.B1-1.B4. Voice tracks built for real (V3 Text-to-Dialogue, attribution clean). Nothing fired, nothing signed — held at staged per Julian's explicit instruction, pending his read of the regenerated v2 doc.

---

## THE RETAKE ROOM (P1)

**T11 · The layer question, wired in front** ⏳ OPEN
**T12 · The retake prompt obeys the law** ⏳ OPEN
**T13 · The failure class ledger** ⏳ OPEN
**T14 · failed_correction_rule wired** ⏳ OPEN
**T15 · Sample and select arrives in the retake room first** ⏳ OPEN

---

## POST (P1 and P2)

**T17 · Dual loudness masters (P1)** ⏳ OPEN
**T18 · Giacchino becomes a decision maker (P2)** ⏳ OPEN
**T19 · The episode master and the handoff pack (P2)** ⏳ OPEN

**T20 · Crossfade doctrine reconciled** ✅ DONE
cb_post.py. Docstring and behaviour now agree: hard cuts within a scene, cross-dissolves reserved for between scenes only.
DoD: one sentence of doctrine, code matching it. Done.

**T21 · Readme language** ✅ DONE
cb_post.py CAPCUT_README. "Replace the voice" removed; voice stems are documented as balance/duck only.
DoD: no document in the repo offers a voice swap. Done for cb_post.py's own readme; see T5.

---

## RESTRUCTURE (T30)

Full 5-phase repo restructure — see RESTRUCTURE_SPEC_T30.md. Status tracked there, not duplicated here.

---

## NEW FROM COMPETITIVE RESEARCH (Addendum A, 2 July 2026)

**T31 · The provenance pack (P1)** ⏳ OPEN
cb_gen forensic logs + the Gate 5 handoff pack. Per-episode auto-generated CHAIN_OF_TITLE.md recording every asset's source (turnarounds, voices, music, models, scripts). Ships inside the broadcaster handoff pack.
DoD: every episode signed at Gate 5 emits its chain of title with zero hand assembly; the pitch materials reference it.

**T32 · The cross-episode world ledger (P2, queued behind the Bo ruling — Bo is now confirmed, so this can proceed)** ⏳ OPEN
New: shows/crystal-bears/canon/world_state.json + a Continuity read at Gate 0 and write at Gate 5 sign-off. Carries Keen's wristband state, relationships, objects gained/lost, promises made, episode to episode.
DoD: Gate 0 receives the ledger as context; Gate 5 sign-off appends the episode's canonical changes; Continuity BLOCKS a script contradicting the ledger.

**Fold-in (no new ticket, from Addendum A):** T8 gains one line: the Director's Eye pass runs as an explicit Critique, Correct, Verify cycle on the breakdown before Gate 1 sign-off. One loop, one author, measured by the golden set like everything else. ⏳ Folds into T8 when T8 is worked.

**Ruling requested (Addendum A) — the two universes boundary:** proposed wording added to the Studio Bible (see Part 6) — Julian to accept, amend or reject.

---

## THE ORDER OF PLAY

Week one: T1 to T6 and T16 (the floor) — ✅ done 2026-07-02. T21 and T20 — ✅ done.
Week two: T7 (added, unrouted) — ✅ done. T9, then T10 so every later change is measured — ⏳ open.
Week three: T11 to T15 (the retake room), T17 — ⏳ open.
Then: T8 (the Director's prose), T18, T19, T31, T32 — ⏳ open.

*Rule for the pack: a ticket is done when its DoD is true and the Bible agrees, not when the code compiles.*
