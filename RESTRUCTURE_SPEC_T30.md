# STUDIO RESTRUCTURE SPEC — TICKET T30
*Cleans the canons and the code into the efficient structure the studio's own doctrine demands: the ENGINE is show agnostic and permanent; the SHOW is a tenant profile. One canon, one home per document, one import path. Executed by Claude Code, phase by phase, with the safety rule below governing every move.*

**Status: approved by Julian 2026-07-02 — all 5 phases, executed in this session.**

- ✅ **Phase 1 (One Canon)** — done, verified (drift-injection test passed, baseline byte-identical).
- ✅ **Phase 2 (Paths before moves)** — done. `engine/paths.py` created; `cb-gen/` → `engine/` via `git mv`; every literal `"cb-gen"` reference fixed across serve.py, app.html, projects.json, .gitignore, and engine's own docstrings; live security-hardening test 34/35 (1 pre-existing unrelated gap — a media fixture wiped in an earlier reset).
- ✅ **Phase 3 (The show profile)** — the PHYSICAL move is done: canon markdown + all 5 config JSON files → `shows/crystal-bears/canon/`; `cb-output` → `shows/crystal-bears/episodes/output/`; `cb-studio/data/scripts` → `shows/crystal-bears/episodes/scripts/`; `WING_LAW`/`STYLE` extracted to `shows/crystal-bears/laws/*.txt`; `profile.json` written as the tenant manifest; backward-compat symlinks left at every old path (a real bug was caught and fixed here — an off-by-one relative symlink depth broke the live server on first restart; fixed and re-verified). **NOT done**: the deeper acceptance criterion (`STUDIO_SHOW=<other>` starting cleanly with zero Crystal-Bears assumptions baked into the engine's actual prompt-building logic) — that's creative-logic surgery across cb_director.py/cb_prompts.py/cb_qa.py, scoped as separate future work, documented in profile.json's own note.
- ✅ **Phase 4 (Document consolidation)** — done. 6 superseded pipeline docs archived to `archive/2026-07-pre-restructure/` with dated supersession notes; 4 character/comedy docs moved to `shows/crystal-bears/docs/`; `CLAUDE_CODE_BRIEF.md` correctly EXCLUDED (discovered mid-move it's an unrelated "8th Hour" game-build document, not a Crystal Bears pipeline doc). `STUDIO_GATE_FLOW_SPEC.md`/`STUDIO_WRITERS_ROOM_SPEC.md` correctly left live at root per spec. **NOT done**: renaming `CRYSTAL_BEARS_STUDIO_BIBLE.md` → `STUDIO_BIBLE.md` — deferred; that file is extensively cross-referenced and a rename this late in the session carried more risk than value today.
- ◐ **Phase 5 (Code hygiene)** — partial. Root `README.md` written. `previews/`/`tests/` subfolder reorganization skipped (low value, non-zero risk, diminishing returns at this point). Dead-code sweep is a no-op (T3 ruling was KEEP, not retire). Gate numbering already closed in the Phase-0 ticket pass.

**The safety rule: behaviour must not change.** Before Phase 1, capture the baseline: run the Gate 3 dry run on three Ep1 beats and save the emitted prompts, plus `python3 -c "import cb_pipeline, cb_beats, cb_segprompt, cb_post, cb_retake, cb_qa, cb_continuity, cb_voice, cb_gen"` as the import proof. After every phase, both must produce identical results. A restructure that changes an emitted prompt has failed, whatever it improved.

---

## THE TARGET TREE

```
studioai/
  CLAUDE.md                      operating instructions + session protocol
  STUDIO_BIBLE.md                how things are made (engine doctrine, renamed from CRYSTAL_BEARS_STUDIO_BIBLE.md
                                 with show specifics moved to the show profile)
  WORLD_CLASS_ROADMAP.md
  TICKET_PACK_001.md
  engine/                        the permanent, show agnostic spine (was cb-gen)
    cb_pipeline.py  cb_state helpers, gates, locks, cascade
    cb_beats.py     cb_gen.py    cb_seedance.py   cb_llm.py
    cb_segprompt.py cb_prompts.py cb_keyframe helpers
    cb_voice.py     cb_post.py   cb_retake.py     cb_address.py
    cb_qa.py        cb_continuity.py  cb_director.py  cb_director_*.py
    cb_writer.py    cb_script.py cb_scene.py      cb_context.py
    train_lora.py
    paths.py        every path constant in one file (Phase 2)
    previews/       kf_preview.py  voice_preview.py  beat_preview.py  retake_preview.py
    tests/          test_unapprove_locks.py  test_static_hardening.py (from cb-studio)
  shows/
    crystal-bears/               the tenant profile: everything Crystal Bears specific
      profile.json               the manifest the engine loads (Phase 3)
      canon/
        LOCKED_CANON.md          THE single source (the eight skill copies die)
        characters.json  locations.json  continuity.json  episode_arc.json  gag_locks.json
      laws/
        wing_law.txt             per show prompt law, loaded by profile
        style.txt                the visual DNA paragraph (out of cb_director.py's STYLE constant)
      docs/
        COMEDY_DOCTRINE.md  CHARACTER_SHEETS.md  CHARACTER_REFERENCE_DATA.md  CHARACTER_LORA_PROMPTS.md
      chairs/                    the skill prompts + worked examples (director, writer, dp, voice,
                                 composer, continuity, camera, post) — references/ subfolders deleted,
                                 canon read from ../canon at runtime
      episodes/
        scripts/                 the Ep1..Ep7 .txt files (from cb-studio/data/scripts)
        output/                  beat packages (from cb-output)
  studio-ui/                     was cb-studio: app.html, serve.py, data/ (minus scripts, moved above)
  tools/
    sync_canon.py                generates any needed canon copies + verifies hashes (Phase 1)
    migrate_paths.py             the one time mover, kept for the record
  archive/
    2026-07-pre-restructure/     the six superseded pipeline docs + anything replaced, untouched, dated
```

---

## PHASE 1 — ONE CANON (do this first; it is the disease the studio exists to cure)

1. `git mv CRYSTAL_BEARS_LOCKED_CANON.md shows/crystal-bears/canon/LOCKED_CANON.md` — the root copy becomes THE copy.
2. Delete all eight `skills/*/references/CRYSTAL_BEARS_LOCKED_CANON.md` duplicates. Any skill that read its local copy reads the canonical path instead (cb_director.py already reads a single CANON path constant; repoint it).
3. `tools/sync_canon.py`: if any consumer genuinely requires a local copy (a skill packaged for ~/.claude/skills), the copy is GENERATED from the canonical file and stamped `AUTO GENERATED — edit shows/crystal-bears/canon/LOCKED_CANON.md`, and the script verifies hashes match, exiting nonzero on drift.
4. Continuity gains a startup check: canonical hash matches every generated copy, BLOCK on mismatch.

DoD: `grep -r "LOCKED_CANON" --include="*.md" -l` returns one source file plus only stamped copies; editing a duplicate is impossible without the stamp shouting.

## PHASE 2 — PATHS BEFORE MOVES (the step that makes the rest safe)

1. Create `engine/paths.py`: ROOT, ENGINE, SHOW (resolved from profile), CANON, CHARS, LOCATIONS, MEDIA, OUTPUT, SCRIPTS, LOCKED, NOTES — every path constant currently scattered through the modules (the HERE/ROOT patterns in cb_director, cb_beats, cb_gen, cb_prompts, serve.py) imports from here.
2. Only when every module reads paths.py do the physical moves happen, all as `git mv` so history survives.
3. serve.py's CBGEN/ROOT constants repoint to paths.py values.

DoD: the import proof passes; the three baseline prompts are byte identical.

## PHASE 3 — THE SHOW PROFILE (the tenancy decision made physical)

1. `shows/crystal-bears/profile.json`: show name, canon paths, laws to inject (wing_law where any bee is cast), the style paragraph, chair prompt locations, character/location file paths, output conventions.
2. The engine loads ONE profile (env `STUDIO_SHOW=crystal-bears` default). Everything currently hardcoded moves behind it: the ROLE dict and bee logic in cb_segprompt read from characters.json (already mostly true), WING_LAW loads from laws/, STYLE from laws/style.txt, the characters/locations paths from the profile.
3. Acceptance: `STUDIO_SHOW=thistlewoods` with an empty stub profile starts the engine and fails ONLY on missing content, never on Crystal Bears assumptions baked in code.

DoD: grep the engine for "bee", "Fuzzby", "crystal" — zero hits outside comments; every hit lives in shows/crystal-bears/.

## PHASE 4 — THE DOCUMENT CONSOLIDATION (fourteen roots become four)

Stays at root: CLAUDE.md, STUDIO_BIBLE.md, WORLD_CLASS_ROADMAP.md, TICKET_PACK_001.md.

Moves to shows/crystal-bears/docs/: STUDIO_COMEDY_DOCTRINE.md, CHARACTER_SHEETS.md, CHARACTER_REFERENCE_DATA.md, CHARACTER_LORA_PROMPTS.md.

Archives (dated, untouched, with a one line supersession note prepended pointing at the Bible): CRYSTAL_BEARS_PIPELINE.md, CRYSTAL_BEARS_PIPELINE_WORKFLOW.md, CRYSTAL_BEARS_PIPELINE_CREW.md, CRYSTAL_BEARS_ENGINE.md, CRYSTAL_BEARS_PROCEDURE.md, CRYSTAL_BEARS_SCENE_WORKFLOW.md — six descriptions of the pipeline from different eras; the Bible is the survivor. Anything in them still true and absent from the Bible gets folded into the Bible FIRST, then the file archives. CLAUDE_CODE_BRIEF.md (discovered during execution, not in the original inventory) — same treatment: fold anything true into CLAUDE.md, then archive.

STUDIO_GATE_FLOW_SPEC.md and STUDIO_WRITERS_ROOM_SPEC.md stay live at root until their builds complete (the UI redesign, Gate 0), then archive.

DoD: root holds four living documents; every archived file carries its supersession note; nothing true was lost (the fold in is reviewed at sign off).

## PHASE 5 — CODE HYGIENE (last, least, still worth it)

1. previews/ and tests/ subfolders as per the tree; KEYFRAME_DONE.md and CLIP_DONE.md move into engine/docs or fold into the Bible's gate contracts.
2. Dead code sweep: anything the T3 ruling retires (none — T3 KEEPS the second master) deletes in the same commit as the Bible line that kills it. (T3's ruling was KEEP, not retire — this item is a no-op this pass.)
3. One `README.md` at root, ten lines: what this is, the tree, where the Bible is, how a session starts.
4. Gate numbering (T16) lands in the same sweep since every file is being touched anyway. (T16 already done in Phase 0 — no-op here.)

DoD: a stranger (or a fresh Claude Code session) finds any file's home in one guess.

---

## THE ORDER AND THE RULE

Phases run 1 → 2 → 3 → 4 → 5, one phase per commit, baseline checks green after each. Phase 3 is the one that pays forever: it is standing rule 6 finishing its thought — the model is a tenant, the show is a tenant, only the studio is permanent. If time is short, Phases 1 and 2 alone remove the two live dangers (canon drift, path spaghetti); 3 to 5 can follow next week.

*This spec supersedes nothing in the Ticket Pack; it IS ticket T30, and T16 (gate numbering) plus T28 (canon sync) close inside it.*
