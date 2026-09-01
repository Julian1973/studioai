# STUDIO RESTRUCTURE SPEC — PROJECTS (T40)
*Finishes what T30 started. THE SOFTWARE IS THE PIPELINE. A show is a PROJECT: a folder that owns its show bible, canon, assets, laws, chairs' taste and episodes. Crystal Bears is the first project; Box Monsters is the second. The engine, the gates, the providers, the cost controls and the generic craft chairs never again say a character's name. Executed by Codex / Claude Code, phase by phase, one commit per phase, with the safety rule governing every move. Julian approves at the front.*

**Status: approved by Julian 2026-09-01 — executing on branch `t40/projects`, one commit per ticket (TICKET_PACK_002.md is the order of play). Written against `codex/studioai-reduction-pass-3` @ 0b0a6b7.**

- ✅ **Phase 0 (Baseline)** — T41/T42 done. Real pytest line: 932 passed, 3 failed (pre-existing), 4 skipped. Baseline = 286 files under engine/goldens/T40_BASELINE/, byte-identical on re-run.
- ✅ **Phase 1 (One home per project)** — T43 done. NOT done: `cb-studio` → `studio-ui` (step 7, Julian's call, deferred).
- ✅ **Phase 2 (Every path through the profile)** — T44 done for engine/tools/dailies and the studio server; the studio UI's project-from-request work is T45. Deviation from the tree above: `cb-seed/assets` stays the real directory and `projects/crystal-bears/assets` is the link (identity digests hash the resolved path — see T44's note).

**Why now.** T30 (2026-07-02) made the *paths* show-agnostic and wrote `shows/crystal-bears/profile.json` as the tenant manifest — and recorded its own unmet acceptance criterion: *"`STUDIO_SHOW=<other>` with an empty stub profile starts the engine and fails ONLY on missing content, never on Crystal Bears assumptions baked in code."* The 2026-09-01 audit shows how far that still is from true:

- `SUPPORTED_ENGINE_ADAPTERS = {"crystal-bears-v1"}` is a whitelist of one; `cb_render.py:150` hard-refuses anything else. A second project is refused, or inherits everything.
- 64 literal `shows/crystal-bears/...` paths in non-test engine / UI / tools code bypass `paths.py` (only 4 of ~44 engine modules import it).
- Character and world names live in logic, not data: `cb_scene_package.py:168-204` branches on `"keen"`; `cb_emission_standard.py` greps prompts for `Zenny`, `pollen`, `moustache`; `dailies/preflight.py` carries the cast list as a regex; `cb_gen.py:67` holds `{"Aida": "Ada"}`; `cb_engine.py:1000` knows the species list `("squirrel","dolphin","bee","bear")`; `cb_render.py:5752` forbids "crystals on either bee"; both live LLM system prompts open *"You are … of the Crystal Bears creative room"*.
- 7 of 8 department skills are `skills/crystal-bears-*` with canon copies inside; `cb_render.py:2989` builds the skill path as `f"skills/crystal-bears-{skill}/SKILL.md"`.
- `profile.json` says episode output lives at `shows/crystal-bears/episodes/output/` — that directory does not exist; the packages are in root `cb-output/`. `engine/config/` is a real directory of copies, not the symlinks `paths.py`'s docstring claims. `cb-studio/data/scripts/` has drifted from `shows/crystal-bears/episodes/scripts/` (Ep1 differs by 37 bytes; Ep2 V2 exists in only one of them).
- The UI already has Productions / project selection, `p=<id>` routing, `projects.json`, and a `POST /api/project` scaffold that writes to `projects/<id>/` — a directory the repo has never created. The UI's word is **project**; the engine's word is **show**. One word from now on: **project**.

**The safety rule: behaviour must not change.** Before Phase 1, capture the baseline and commit it as `engine/goldens/T40_BASELINE/`: (a) the current `engine/goldens/` prompt fixtures re-emitted via the dry-run path for Ep1 1.B1–1.B5 (keyframe + segprompt + relay variants); (b) the Ep2 Scene-4 WATCH prompt as currently emitted; (c) `python3 -m pytest -q` result line (re-counted on the working branch: **932 passed, 3 failed, 4 skipped** — the 3 failures pre-date T40: 2 need local key-art media, 1 is an audio-timing tolerance; the README's "153 passed" was stale); (d) `python3 tools/sync_canon.py --check` green; (e) the import proof `python3 -c "import cb_engine, cb_render, cb_gen, cb_post, cb_canon, cb_creative, cb_voice_director, cb_intake, cb_departments, cb_scene_package, cb_emission_standard"`. After EVERY phase all five must reproduce byte-identically (prompts) or green (checks). A restructure that changes an emitted prompt has failed, whatever it improved. Crystal Bears output on the last day of this spec must equal Crystal Bears output on the first.

**Julian's rulings this spec relies on (2026-09-01):** the software is the pipeline; shows are projects with episodes; each project owns its own assets and show bible; Box Monsters is the second project; Julian stays at the front with approve / retake / reject.

---

## THE TARGET TREE

```
studioai/
  CLAUDE.md                          operating instructions (rule 6 rewritten: canon edited at projects/<id>/canon/)
  STUDIO_BIBLE.md                    how the STUDIO makes things — engine doctrine only, no show content
                                     (from CRYSTAL_BEARS_STUDIO_BIBLE.md; the show parts move to the project)
  README.md
  engine/                            the permanent, project-agnostic spine
    paths.py                         every path from the ACTIVE PROJECT's profile — the only path authority
    project_profile.py               (was studio_profile.py) validated project manifest, capability flags
    cb_*.py                          craft + law; zero character names, zero project ids
    goldens/                         frozen prompt baselines incl. T40_BASELINE/
  studio/                            generic, project-agnostic craft the engine loads by ROLE
    chairs/                          writer/ director/ cinematographer/ voice-director/ composer/
                                     continuity/ post/ — SKILL.md each: craft, no canon, no cast
    skills/ standards/               (exists today: seedance wrapper/extension + Seedance standards)
    templates/project/               the blank project a new show is scaffolded from (profile.json,
                                     canon/*.json stubs, laws/, chairs/, episodes/, assets/, docs/)
  studio-ui/                         (was cb-studio) app.html, director.*, serve.py, data/
                                     data/projects.json = the registry; NO per-project content here
  projects/                          ONE FOLDER PER SHOW — everything the show owns
    crystal-bears/
      profile.json                   the project manifest (extended — see Phase 2)
      SHOW_BIBLE.md                  (from root CRYSTAL_BEARS_STUDIO_BIBLE.md, show parts only)
      canon/                         LOCKED_CANON.md characters.json locations.json continuity.json
                                     episode_arc.json gag_locks.json banned_vocabulary.json
                                     identity_packs.json voice_cards.json sfx_library.json sfx/
                                     lock_policy.json reference_slot_policy.json CANON_LOCK.json
      laws/                          style.txt wing_law.txt forbidden_elements.json
                                     emission_checks.json (the Scene-1 pollen-gag checks, as data)
                                     cast_vocabulary.json (names, species, pronunciation, appearance terms)
      chairs/                        the show's TASTE overlays per role (director.md, writer.md, …) —
                                     read on top of studio/chairs/<role>/SKILL.md at runtime
      creative/                      (exists) taste canons, exemplars, corpus, learning/
      assets/                        (was cb-seed; git-ignored, backed up to 5t) plates, turnarounds, refs
      docs/                          (exists) character sheets, comedy doctrine, EP1_GATE1_STORYBOARD.md
      episodes/
        scripts/                     the single script store (cb-studio/data/scripts merged in)
        output/                      (was cb-output) packages, evidence, prompt-bank, asset-registry
        episodes.json                the derived episode index (was studio-ui/data/episodes.json)
    box-monsters/
      profile.json  SHOW_BIBLE.md  canon/  laws/  chairs/  assets/  episodes/     ← scaffolded from the template
  tools/
    sync_canon.py --project <id>     generates + verifies any canon copies for ONE project
    migrate_t40.py                   the one-time mover, kept for the record
  shows -> projects                  compatibility symlink, one release, then deleted
  cb-output -> projects/crystal-bears/episodes/output      compatibility symlink, one release
  cb-seed   -> projects/crystal-bears/assets               compatibility symlink, one release
  CRYSTAL_BEARS_LOCKED_CANON.md -> projects/crystal-bears/canon/LOCKED_CANON.md   (exists today; retargeted)
```

**The three-layer rule (CLAUDE.md rule 2), now with a fourth word.** Taste lives in prose (chairs) · law lives in code (engine) · canon lives in data (the project's canon/) · and **the project is the only place a name may live.** If a character, place, species, prop, gag or pronunciation appears in `engine/`, `studio/` or `studio-ui/` it is in the wrong layer and moves the day it is found.

---

## PHASE 0 — BASELINE (no code change)

1. Re-count the suite on the working branch; write the real line into this file's safety rule.
2. Emit and commit `engine/goldens/T40_BASELINE/` per the safety rule.
3. Reconcile the drifted script stores BEFORE moving anything: diff `cb-studio/data/scripts/` against `shows/crystal-bears/episodes/scripts/`; Julian rules which Ep1 text is canonical; `Ep2_Bos_Big_Day_V2.txt` is copied into the tenant store. Record the ruling in the commit.
DoD: `git status` clean, baseline directory committed, both script stores byte-identical.

## PHASE 1 — ONE HOME PER PROJECT (moves only, no logic)

1. `git mv shows projects`; create symlink `shows -> projects`.
2. `git mv cb-output projects/crystal-bears/episodes/output`; symlink `cb-output -> …`. Delete the phantom `episodes.output` claim mismatch — the profile is now true.
3. `git mv cb-studio/data/scripts/* projects/crystal-bears/episodes/scripts/` (after Phase 0's reconcile); remove the `if showId == DEFAULT_SHOW_ID` special case in `serve.py:70-77` so every project's scripts resolve the same way.
4. `cb-seed/` (untracked, ~790 MB): move on disk to `projects/crystal-bears/assets/`; symlink `cb-seed -> …`; update `.gitignore` (`/projects/*/assets/`) and `tools/backup_media.py`.
5. `engine/config/`: delete the seven duplicated JSON copies and `LOCKED_CANON.md`; leave a symlink `engine/config -> ../projects/crystal-bears/canon` for one release. `beat_costs.json` and `sfx/` move into the project's canon/ (they are show data) — `cb_post.py:87` and `cb_costs.py` read them via the profile in Phase 2.
6. `git mv CRYSTAL_BEARS_STUDIO_BIBLE.md projects/crystal-bears/SHOW_BIBLE.md`; `git mv EP1_GATE1_STORYBOARD.md projects/crystal-bears/docs/`; root symlinks for both. Retarget the existing root `CRYSTAL_BEARS_LOCKED_CANON.md` symlink and the seven skill `references/` symlinks to the new path.
7. `git mv cb-studio studio-ui` and fix every literal (T30 Phase 2 did exactly this for `cb-gen` → `engine`; same sweep: serve.py, app.html, director.js, projects.json, `.gitignore`, `start-studio.*`, README, EPISODE_2_START_HERE.md). *Optional — Julian may defer this step; it is cosmetic and touches 23 files.*
DoD: safety rule green; `find . -type l` lists exactly the compatibility symlinks named above; `python3 tools/sync_canon.py --check` green.

## PHASE 2 — EVERY PATH THROUGH THE PROFILE

1. Rename `engine/studio_profile.py` → `engine/project_profile.py` (keep `studio_profile` as a one-line re-export for one release). Env var becomes `STUDIO_PROJECT` (`STUDIO_SHOW` honoured as alias). `DEFAULT_SHOW_ID` is deleted — the default project comes from `studio-ui/data/projects.json`'s `primary: true` entry, never a code constant.
2. Extend the profile schema so every file the engine reads is DECLARED: `canon.{voiceCards, sfxLibrary, sfxDir, beatCosts, lockPolicy, canonLock, referenceSlotPolicy}`, `laws.{style, forbiddenElements, emissionChecks, castVocabulary, wingLaw?}`, `creative.{root, learning, exemplars, dailiesLibrary, voiceRegisters, voiceRulebook, voicePlaybook}`, `assets.root`, `chairs` (project taste overlays dir), `episodes.{scripts, output, index}`. Unknown keys still `extra="forbid"`.
3. Kill the 64 literals. Every `ROOT / "shows" / "crystal-bears" / …` in `cb_canon.py`, `cb_creative.py` (L78, L810-815, L2718), `cb_dailies.py`, `cb_learning.py` (L42/46/76), `cb_voice_director.py` (L19-22), `cb_intake.py` (L51/57), `cb_post.py` (L87), `cb_render.py` (L940/2621/3039), `cb_handover.py`, `cb_departments.py`, `tools/sync_canon.py`, `tools/sync_scenes.py`, `tools/backup_media.py`, `dailies/preflight.py`, `dailies/playbook.json` becomes an import from `paths`. `cb_canon.py:659`'s emitted `"showId": "crystal-bears"` becomes `P.PROJECT_ID`.
4. UI: `serve.py` workbench key / API defaults (`L635-636, 2868, 3624`) take the project from the request (`p=`) and fall back to the registry's primary — never the string. `director.js:1549/1565/3164/3216`, `app.html:2806/3681/5834`, `board.html:112` read `CURRENT_PROJECT`. `_APPROVED_FILES` (`serve.py:2396-2405`) is generated from every registered project's profile, not hand-listed.
5. `episodes.json` moves to `projects/<id>/episodes/episodes.json`; `reindex_episodes()` writes the ACTIVE project's index; `projects.json.episodesFile` is derived, not authored.
DoD: `grep -rn "crystal-bears\|crystal_bears\|Crystal Bears" engine/ studio-ui/ tools/ dailies/ --include=*.py --include=*.js --include=*.html --include=*.json | grep -v test_ | grep -v goldens | grep -v FULL_AUDIT` returns ZERO lines. Safety rule green. Every module imports `paths`; a test asserts no module builds a path with the literal `"projects"`.

## PHASE 3 — CANON OUT OF CODE

Each item: the logic stays; the NAMES become project data the logic reads. Nothing is deleted from Crystal Bears — it is relocated into `projects/crystal-bears/`.

1. **Cast vocabulary** → `laws/cast_vocabulary.json`: `{names:[…], speciesTerms:{bee:[…], bear:[…]}, appearanceTerms:[…], pronunciation:{"Aida":"Ada"}}`. Consumers: `dailies/preflight.py` NAMES/APPEARANCE/BEES (L20-22, 100-102), `cb_gen.py:67` `ELEVEN_PRONUNCIATION_OVERRIDES`, `app.html:5964` toast, `cb_engine.py:1000-1027` `_character_species()` candidate list, `cb_prompt_lab.py:226-300` matchTerms, `cb_quality.py:129`.
2. **Species and physiology** → `characters.json` gains `species` and `physiology` (e.g. `{"wings": true}`); `isBee` is kept as a derived alias for one release. `laws.wingLaw.appliesWhen` becomes `"any cast member has physiology.wings"`. The forbidden-elements sentence in `cb_render.py:5752` becomes `laws/forbidden_elements.json`, rendered per project.
3. **Continuity rules** → `continuity.json`: the Keen wristband branch in `cb_scene_package.py:168-204` becomes a data rule `{"whenCast":["Keen"], "carry":"…aged-gold open cuffs…"}` applied by generic code.
4. **Emission checks** → `laws/emission_checks.json`: every regex in `cb_emission_standard.py:67, 174-209` (moustache / pollen / cut-to-Zenny / clean-fur) becomes a named check with its pattern and its BLOCK/WARN level; the module runs whatever the project declares. A project with no checks file runs the structural checks only.
5. **LLM system prompts**: `cb_creative.py:1067` and `cb_director_chat.py:198` open `"You are the {role} of the {project.name} creative room"`; the show's taste paragraph is appended from `projects/<id>/chairs/<role>.md`.
6. **Gap strings** (`cb_canon.py:498` "Crystal Call…") → `canon/episode_arc.json` or the project's `creative/` as declared gaps.
7. **Docstrings and comments** that say "Crystal Bears" in `cb_gen.py`, `cb_layout.py`, `cb_safety.py`, `cb_state.py`, `cb_departments.py`, `cb_post.py:28/80` are rewritten to say "the active project" (rule 7).
DoD: `grep -rniE "fuzzby|zenny|aida|keen|squeaky|howey|sunny|luna|misty|amie|\bbo\b|pollen|moustache|crystal call|wing law|isbee|meadow" engine/ studio/ studio-ui/ dailies/ tools/ --include=*.py --include=*.js --include=*.html | grep -v test_ | grep -v goldens` returns ZERO lines. Safety rule green — the Crystal Bears prompts are byte-identical because the same words now arrive from data.

## PHASE 4 — GENERIC CHAIRS, PROJECT TASTE

1. Split each `skills/crystal-bears-<role>/SKILL.md` into two files: the CRAFT (how a director/DP/writer works, gate contracts, output shapes) → `studio/chairs/<role>/SKILL.md`; the TASTE and any canon citations (Fuzzby's motion doctrine, the fourteen staging laws' show-specific examples, the bee wing rules) → `projects/crystal-bears/chairs/<role>.md`. The `references/CRYSTAL_BEARS_LOCKED_CANON.md` copies are deleted; the engine hands the chair the project canon at runtime (`paths.load_show_bible()` already exists).
2. `cb_departments.py:68-106` and `cb_render.py:2989/3021` resolve a chair as `studio/chairs/<role>/SKILL.md` + `projects/<id>/chairs/<role>.md` (optional). No project id in the path.
3. `tools/sync_canon.py --project <id>`: `SRC`, `POLICY` and the glob come from the profile; `compatibilityCopies` in `lock_policy.json` lists project-relative paths only.
4. **Engine adapters become capabilities.** Delete `SUPPORTED_ENGINE_ADAPTERS` and the refusal in `cb_render.py:150-153` / `cb_production_preflight.py:426`. Replace with `profile.capabilities` flags the engine checks per feature (`hasWingLaw`, `hasGagLocks`, `hasIdentityPacks`, `hasEmissionChecks`, …). Production is blocked by MISSING REQUIRED CONTENT (no characters, no locked canon, no scripts) with a message naming the missing file — never by the project's name.
5. `studio/templates/project/` is written: a blank profile, empty canon JSONs with schemas, `laws/` stubs, `chairs/` stubs, `SHOW_BIBLE.md` outline, `episodes/scripts/`. `POST /api/project` (`serve.py:3826-3888`) scaffolds from it.
DoD: `ls skills/` shows only generic dirs (or `skills/` is gone and `studio/chairs/` holds them); `grep -rn "crystal" studio/chairs` zero; `sync_canon.py --project crystal-bears --check` green; safety rule green.

## PHASE 5 — THE SECOND PROJECT

1. Scaffold `projects/box-monsters/` from the template via the UI's own "New production" wizard (proves the wizard, not just the script). Julian supplies the name, premise, audience, animation type, aspect ratio, episode length; content stays empty.
2. `STUDIO_PROJECT=box-monsters python3 -m pytest -q engine/test_project_profile.py` passes; the engine boots; every gate reports "blocked: missing <file>" naming a Box Monsters file — T30's acceptance criterion, finally true.
3. A new test `engine/test_second_project_isolation.py`: with Box Monsters active, no Crystal Bears path, name, asset or prompt fragment is reachable (walk `paths.*`, run the dry-run emitter on a stub beat, assert none of the Phase-3 terms appear).
4. UI: Productions screen lists both projects; switching projects switches scripts, episodes, canon, assets and chairs with no restart.
5. CLAUDE.md: rule 6 rewritten ("canon is edited ONLY at `projects/<id>/canon/LOCKED_CANON.md`, then `sync_canon.py --project <id>`"); rule 2 gains the fourth word; a new numbered rule records this spec's ruling and date. `STUDIO_BIBLE.md` at root holds engine doctrine only. README's repository map updated. EPISODE_2_START_HERE.md path updated.
DoD: both projects visible and switchable; isolation test green; safety rule green; compatibility symlinks (`shows`, `cb-output`, `cb-seed`, `engine/config`) still present and scheduled for deletion in the NEXT release's first ticket.

---

## THE ORDER AND THE RULE

Phases run 0 → 5, **one phase per commit** (Phase 3 may be two commits: data files first, code second — both baseline-green). Safety rule green after every phase, stated in the commit message with the pytest line and the goldens diff (`diff -r engine/goldens/T40_BASELINE <fresh emission>` = empty). Any phase that cannot keep Crystal Bears byte-identical STOPS and comes back to Julian with the exact prompt diff — it does not "improve" the prompt on the way through.

If time is short: Phases 0–2 alone are worth shipping (one true tree, every path through the profile). Phase 3 is the one that makes the second project honest. Phases 4–5 are the proof.

**What Julian decides, in order:** (1) approve this spec; (2) Phase 0's Ep1 script ruling; (3) whether Phase 1 step 7 (`cb-studio` → `studio-ui`) runs now or later; (4) Box Monsters' profile facts when Phase 5 asks. Everything else is the agent's to execute and prove.
