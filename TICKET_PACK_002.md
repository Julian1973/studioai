# STUDIOAI — TICKET PACK 002 · PROJECTS
*The work that turns the software into the pipeline and the shows into projects. Companion to RESTRUCTURE_SPEC_PROJECTS.md (T40) — the spec says why and in what shape; this pack is the order of play. Each ticket: the files, the change, the definition of done. Priorities: P0 = the floor (nothing else ships first) · P1 = this phase of work · P2 = when P1 is green. Source of truth order: the active project's Locked Canon > STUDIO_BIBLE > the spec > this pack. One commit per ticket, the commit message naming the ticket and stating the safety-rule result.*

*Status legend: ✅ DONE · ⏳ OPEN · ⛔ BLOCKED (on Julian). Work lives on branch `t40/projects`. Numbering continues from TICKET_PACK_001 (last used T33) and T30/T40 (spec tickets).*

*Written 2026-09-01 against `codex/studioai-reduction-pass-3` @ 0b0a6b7. Julian's rulings: the software is the pipeline; shows are projects with episodes; each project owns its assets and show bible; Box Monsters is project two.*

---

## THE FLOOR (P0)

**T41 · Baseline capture** ✅ DONE (2026-09-01, c9db460)
engine/goldens/T40_BASELINE/, RESTRUCTURE_SPEC_PROJECTS.md. Re-emit the Ep1 1.B1–1.B5 keyframe/segprompt/relay prompts and the Ep2 S4 WATCH prompt through the dry-run path; record the real pytest line for the working branch (the README's "153 passed, 4 skipped" is to be re-counted, not trusted); record `sync_canon.py --check` and the import proof. Commit them.
DoD: `diff -r engine/goldens/T40_BASELINE <fresh emission>` is empty on a second run; the spec's safety rule quotes the real pytest line. Verified.

**T42 · Script store reconcile** ✅ DONE (2026-09-01, b8f54b3 — Julian ruled: the studio copy is canonical)
cb-studio/data/scripts/ vs shows/crystal-bears/episodes/scripts/. Ep1_The_Adventure_Begins.txt differs (17,863 B vs 17,826 B); Ep2_Bos_Big_Day_V2.txt exists only in cb-studio/data/scripts. Present the Ep1 diff to Julian; he rules which is canonical; copy Ep2 V2 into the tenant store.
DoD: both stores byte-identical; the ruling and the diff are in the commit message. Julian's decision recorded.

**T43 · One home per project (moves)** ✅ DONE (2026-09-01, 1c960f9)
Phase 1 of the spec. `git mv shows projects` (+ `shows` symlink); `cb-output` → `projects/crystal-bears/episodes/output` (+ symlink); scripts merged; `cb-seed` → `projects/crystal-bears/assets` on disk (+ symlink, .gitignore `/projects/*/assets/`, backup_media.py); `engine/config` copies deleted → symlink to the project canon (beat_costs.json + sfx/ move into canon/); `CRYSTAL_BEARS_STUDIO_BIBLE.md` → `projects/crystal-bears/SHOW_BIBLE.md`; `EP1_GATE1_STORYBOARD.md` → `projects/crystal-bears/docs/`; root and skill symlinks retargeted; serve.py:70-77 special case for the default show removed.
DoD: `find . -type l` lists only the spec's compatibility symlinks; safety rule green; sync_canon --check green. Verified.

**T44 · Profile is the only path authority** ✅ DONE (2026-09-01)
engine/project_profile.py (from studio_profile.py; re-export shim kept; engine/test_studio_profile.py → test_project_profile.py), engine/paths.py, every module in the spec's Phase 2 list. Schema extended (canon.voiceCards/sfxLibrary/sfxDir/beatCosts/lockPolicy/canonLock/referenceSlotPolicy; laws.forbiddenElements/emissionChecks/castVocabulary; creative.*; assets.root; chairs; episodes.index). `STUDIO_PROJECT` env (STUDIO_SHOW alias). `DEFAULT_SHOW_ID` deleted — the default is `projects.json`'s primary. All 64 literal paths replaced; `cb_canon.py:659` showId from the profile.
DoD: the spec's Phase-2 grep returns zero lines; a new test asserts no engine module builds a path from the literal "projects"; safety rule green. Verified — engine/test_t44_profile_authority.py pins it (its allowlist names the sites T53/T54/T55 still own). NOTE: cb-seed/assets stays the REAL directory for one release with projects/crystal-bears/assets as the link — cb_identity digests hash the resolved absolute path, so moving the bytes would mark every approved direction stale on a working machine; T61 decides (content digests or a one-time relock).

**T45 · UI takes the project from the request** ✅ DONE (2026-09-01)
cb-studio/serve.py (L635-636, 2396-2405, 2868, 3624), director.js (L1549, 1565, 3164, 3216), app.html (L2806, 3681, 5834), board.html:112, data/projects.json. Workbench key, API defaults, deep links and `_APPROVED_FILES` derive from `CURRENT_PROJECT` / the registry — never the string. `episodes.json` becomes `projects/<id>/episodes/episodes.json` written by `reindex_episodes()` for the active project.
DoD: the UI runs with `crystal-bears` removed from every .js/.html/.py under cb-studio (grep zero outside tests); Episode 2 opens exactly as EPISODE_2_START_HERE.md describes. Verified in code and tests (engine/test_t44_profile_authority.py guards both the project-id and the output-path literals); the live-studio walk-through of EPISODE_2_START_HERE.md is owed on Julian's machine — no server was started here.

---

## CANON OUT OF CODE (P1) — Phase 3

**T46 · Cast vocabulary as data** ✅ DONE (2026-09-01)
projects/crystal-bears/laws/cast_vocabulary.json (new); dailies/preflight.py L20-22/100-102; engine/cb_gen.py:67 + app.html:5964 (pronunciation); engine/cb_engine.py:1000-1027 (species candidates); engine/cb_prompt_lab.py:226-300 (matchTerms); engine/cb_quality.py:129.
DoD: the six consumers read the file; the Crystal Bears file reproduces today's behaviour byte-for-byte (goldens + preflight fixtures). Verified.

**T47 · Species and physiology — as project law, not in characters.json** ✅ DONE (2026-09-01)
projects/crystal-bears/canon/characters.json (`species`, `physiology.wings`), engine/project_profile.py (`laws.wingLaw.appliesWhen` → physiology), engine/cb_render.py:5752 → `laws/forbidden_elements.json`. `isBee` kept as a derived alias for one release with a deprecation note in the Show Bible.
DoD: no code path tests `isBee` or the word "bee"; forbidden elements render per project; safety rule green. Verified — with one deviation: species/physiology live in laws/cast_vocabulary.json, NOT in characters.json, because characters.json is under the canon lock (lock_policy.json) and editing it would mark canon as drifted; the species map was derived from each character's own canon prose (Bo is a squirrel, Squeaky a dolphin). `isBee` and "bee in avoid" remain as LEGACY fallbacks inside project_laws.has_wings so shipped negatives stay byte-identical (Bo still counts as winged via his `avoid` text — recorded in the vocabulary file for Julian's ruling at T61). Also moved this pass, found by the new guard test: the Scene-10 single-subject-anchor override (→ reference_slot_policy.json identityOverrides), Zenny's mantra-chant performance note (→ vocalCues), the comedy-contract default wording (→ comedyDefaults), a prompt example naming Zenny.

**T48 · Continuity carry rules as data** ✅ DONE (2026-09-01 — `laws/continuity_rules.json`: keen-wristband cases + stateMarkers; cb_scene_package/cb_render read `project_laws.continuity_constraints` / `state_from_markers`)
projects/crystal-bears/canon/continuity.json, engine/cb_scene_package.py:168-204. The Keen wristband branch becomes `{"whenCast":["Keen"],"carry":"…"}` applied generically.
DoD: Scene packages for Ep1/Ep2 byte-identical to baseline; `grep -n keen engine/cb_scene_package.py` zero. Verified.

**T49 · Emission checks as data** ✅ DONE (2026-09-01 — `laws/emission_checks.json`: preflight triggers, archetype checks DSL, archetypeSignals; matrix doc notes the ids)
projects/crystal-bears/laws/emission_checks.json (new), engine/cb_emission_standard.py:67/174-209, docs/EMISSION_CONFORMANCE_MATRIX.md. Every regex becomes a named check `{id, pattern, level, rationale}`; the module runs the project's list; structural checks stay in code.
DoD: `test_cb_emission_standard.py` passes unchanged; the matrix doc lists the checks by id; the module contains no character or gag word. Verified.

**T50 · System prompts name the project, taste comes from the project** ✅ DONE (2026-09-01 — `chairs/room.json` voice + `P.PROJECT_NAME`; the studio Design tab's cast/locations/props/workbench/episode titles moved to `creative/design_roster.json` served by `/api/project-roster` — director.js names no character)
engine/cb_creative.py:1067, engine/cb_director_chat.py:198, projects/crystal-bears/chairs/ (new). "You are the {role} of the {project.name} creative room…" + the show's taste paragraph appended from `chairs/<role>.md`.
DoD: the assembled system prompt for Crystal Bears is byte-identical to today's; the module contains no show name. Verified.

**T51 · Gap strings, docstrings, comments** ✅ DONE (2026-09-01 — vision-plate role generic (`* vision plate`), chorus binding derived from chorusMembers, non-verbal sound palette + asset-group tokens + pronunciation message from cast_vocabulary.json, workbench default beat null, Ep1 preview tool → projects/crystal-bears/tools/; Phase-3 grep zero in live code)
engine/cb_canon.py:498; docstrings in cb_gen.py, cb_layout.py, cb_safety.py, cb_state.py, cb_departments.py, cb_post.py:28/80. "Crystal Bears" → "the active project" (rule 7); the Crystal Call gap moves to the project's creative/ as a declared gap.
DoD: the spec's Phase-3 grep returns ZERO lines across engine/ studio/ studio-ui/ dailies/ tools/. Verified.

---

## GENERIC CHAIRS (P1) — Phase 4

**T52 · Split the seven chairs into craft + taste** ✅ DONE (2026-09-01 — `studio/chairs/<role>/SKILL.md` ×8 generic craft (role · responsibility · workflow · influence + templated runtime contract); the show's documents moved verbatim to `projects/crystal-bears/chairs/<role>.md` (+ `animation.md`, `README.md`); `references/` copies deleted; `skills/…/SKILL.md` are symlinks to the moved files so `lock_policy.json`'s runtime hashes and every package's canon digest stay current until Julian's T61 re-lock. `grep -rin crystal studio/chairs` → zero (the lock-hashed animation SKILL.md keeps two 'Julian' mentions until re-lock))
skills/crystal-bears-{writer,director,cinematographer,voice-director,composer,continuity,post}/SKILL.md → studio/chairs/<role>/SKILL.md (craft) + projects/crystal-bears/chairs/<role>.md (taste, canon citations, the show's worked examples). (Older v3/v4 chair variants exist only on the `integration/reconciled-studioai` branch, not on the working branch — nothing to archive here.) `references/` copies deleted.
DoD: `grep -rn crystal studio/chairs` zero; every chair still loads (cb_departments smoke test); safety rule green. Verified.

**T53 · Chair resolution by role, not by project id** ✅ DONE (2026-09-01 — `cb_departments.SKILL_ROLES`/`chair_paths`/`chair_ref`/`project_chair_taste`; contracts fill `{project}`/`{showrunner}` from the profile (new optional `showrunner` field) and append the project's `RUNTIME_TASTE` block; proven byte-identical for all six chairs; a missing overlay is silent, never a refusal)
engine/cb_departments.py:68-106, engine/cb_render.py:2989/3021, engine/cb_intake.py:14/745. Resolve `studio/chairs/<role>/SKILL.md` + optional `projects/<id>/chairs/<role>.md`.
DoD: no f-string builds a skill path from a project id; a missing taste overlay is a WARN, not a refusal. Verified.

**T54 · sync_canon per project** ✅ DONE (2026-09-01 — `--project <id>` (sets STUDIO_PROJECT before paths loads); SRC/POLICY from the profile; stamped chair copies retired; a project with no locked canon yet reports 'nothing to sync' green. CLAUDE.md rule 6 rewrite lands with T60)
tools/sync_canon.py, projects/crystal-bears/canon/lock_policy.json. `--project <id>`; SRC/POLICY/glob from the profile; compatibilityCopies project-relative. CLAUDE.md rule 6 rewritten in the same commit.
DoD: `sync_canon.py --project crystal-bears --check` green; `--project box-monsters --check` green on an empty project. Verified.

**T55 · Adapters become capabilities** ✅ DONE (2026-09-01 — `SUPPORTED_ENGINE_ADAPTERS` deleted; `engineAdapter` optional label; `capabilities{}` + `DEFAULT_CAPABILITIES`; `capability_report.missingRequiredPaths`; `cb_render._require_show_adapter` refuses only on missing content, naming each file; preflight block `SHOW_PROFILE_CONTENT_MISSING` names paths)
engine/project_profile.py (`SUPPORTED_ENGINE_ADAPTERS` deleted; `capabilities{}` added), engine/cb_render.py:150-153, engine/cb_production_preflight.py:426, projects/crystal-bears/profile.json. Production is blocked only by missing required content, with the missing file named.
DoD: a profile with `engineAdapter` removed loads; preflight on an empty project reports every missing file by path and never a project name. Verified.

**T56 · The project template + wizard** ✅ DONE (2026-09-01 — `studio/templates/project/` (30 files, no show named); `engine/project_scaffold.py` (`scaffold_project`, CLI); `POST /api/project` scaffolds from it (cast → canon/characters.json + cast_vocabulary names + design roster + slot policy; key art into the project's assets); wizard gains the showrunner field; `test_project_scaffold.py`)
studio/templates/project/ (new), cb-studio/serve.py:3826-3888 `POST /api/project`, app.html openProjectWizard.
DoD: the wizard creates `projects/<id>/` from the template with a valid profile; `test_project_profile.py` passes for the fresh project. Verified.

---

## THE SECOND PROJECT (P1) — Phase 5

**T57 · The Box Monsters scaffolded** ✅ DONE (2026-09-01 — `projects/the-box-monsters/` created from the template (`project_scaffold`) and filled with Julian's own files from the PC (his Codex-built project of the same day: show bible → LOCKED_CANON, characters (Patch/Rumble/Tilly/Nib/Jenny + stubs), locations for the 5 scenes, continuity, style law, lock policy re-based to the projects/ layout, Jenny's voice card, the Ep1 script activated in the store with the identical sha256, design roster from his cast, key art). Canon locked (`lockedBy: Julian — 2026-09-01T16:29 lock, re-based …`); `cb_canon.status` current + episodeReady; preflight's next action for Ep1 is 'Approve and promote Story & Direction' — the first fire is Julian's)
projects/box-monsters/. Created through the wizard, not by hand. Name, premise, audience, animation type, aspect ratio, episode length from Julian; canon/laws/chairs/assets empty.
DoD: the project appears on the Productions screen; every gate reports "blocked: missing <file>" for a Box Monsters path. Verified.

**T58 · Isolation test** ✅ DONE (2026-09-01 — `engine/test_second_project_isolation.py` runs the engine in a subprocess with STUDIO_PROJECT=the-box-monsters: every paths.* inside the project, every engine module imports, loaders/chairs/canon/intake/registry serve Box Monsters only, no first-project word reachable. It found and closed: cb_canon's assumed characterPerformance source; None creative paths (now conventional defaults under creative/); cb_gen's import order; per-project MEDIA (profile `episodes.media`, `paths.MEDIA`/`MEDIA_URL`, cb_render/cb_gen/cb_post_workspace/cb_costs/serve.py re-pointed; the first project keeps engine/media for one release); the asset registry's `cb-seed/assets` label and URL prefix)
engine/test_second_project_isolation.py (new). With `STUDIO_PROJECT=box-monsters`: walk every `paths.*` value, run the dry-run emitter on a stub beat, assert no Crystal Bears path, name or Phase-3 term is reachable.
DoD: green with Box Monsters active; RED if any T46–T51 change is reverted (proved by reverting one locally). Verified.

**T59 · Switching projects in the UI** ✅ DONE (2026-09-01 — entering another engine-ready production POSTs `/api/project/activate`: the choice is recorded in `cb-studio/data/active-project.json` (honoured by `project_profile.default_project_id` after STUDIO_PROJECT, before the profile default), the studio re-execs itself and the page reloads on `?p=<id>`; refused while a job runs. `test_director_ui.py` gains the two-project switch case)
cb-studio/app.html, serve.py. Selecting a production switches scripts, episodes, canon, assets and chairs without restart; the `p=` deep link survives reload.
DoD: `test_director_ui.py` gains a two-project switch case; passes. Verified.

**T60 · Docs tell one story** ⏳ OPEN — blocked by T59
CLAUDE.md (rules 2, 6 rewritten; new dated rule for T40), STUDIO_BIBLE.md (from the engine parts of the old CRYSTAL_BEARS_STUDIO_BIBLE.md), README.md repository map, EPISODE_2_START_HERE.md, PRODUCTION_DOCTRINE.md stage map, engine/paths.py docstring (which today falsely says engine/config is symlinks).
DoD: a fresh Claude Code / Codex session reading only CLAUDE.md + README would build the project structure, not the Crystal Bears one. Done when Julian signs.

---

## LATER (P2)

**T61 · Delete the compatibility symlinks** ⏳ OPEN — first ticket of the release after T60
`shows`, `cb-output`, `cb-seed`, `engine/config`, root doc symlinks, the `studio_profile` shim, the `STUDIO_SHOW` alias, the `isBee` alias.
DoD: `find . -type l` empty (except the project canon symlink CLAUDE.md rule 6 permits, if kept); grep for each old name zero. Verified.

**T62 · `cb-studio` → `studio-ui`, `cb_` prefix review** ⏳ OPEN — Julian's call on timing
Cosmetic. 23 files reference `cb-studio`; 44 modules carry `cb_`. Rename only if Julian wants the naming to match the product; otherwise record that `cb_` is history, not meaning.
DoD: Julian's ruling recorded either way.

**T64 · The test suite writes into real project data** ⏳ OPEN (found by T43)
projects/crystal-bears/episodes/output/{prompt-bank/prompt_bank.jsonl, asset-registry/assets.json}. A full pytest run appends test prompts to the real prompt bank and re-registers real assets with test-machine paths — the committed prompt_bank.jsonl already carries pytest tmp paths from the Mac. Every writer in the suite must be pointed at a scratch project (the template from T56 is the natural fixture).
DoD: `python3 -m pytest -q` leaves `git status` clean. Verified.

**T63 · Windows PC copy brought to the working branch** ⏳ OPEN
C:\Users\julia\OneDrive\Desktop\Ai Studio. Add `update-studio.cmd` beside `start-studio.cmd` (fetch + fast-forward `codex/studioai-reduction-pass-3`, then re-create `.venv` if requirements changed). The PC copy was 19 commits behind on 2026-09-01 AND carries uncommitted local work (characters.json edited 16:01 BST, CB_Jenny_* assets added 16:06) — the update must stash or commit that first, never discard it.
DoD: double-click updates the PC to the branch tip and prints the commit it landed on. Verified on the PC.
