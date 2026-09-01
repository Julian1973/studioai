# StudioAI — 8th Hour Animation Studio

A human-directed, approval-gated AI animation pipeline from script to finished scene — ONE studio
for ANY show. Every show is a project under `projects/<id>/` that owns its bible, canon, laws, chairs'
taste, assets, scripts and episodes; the engine and the studio contain no show. `projects/crystal-bears/`
is the first production, `projects/the-box-monsters/` the second. Read [STUDIO_BIBLE.md](STUDIO_BIBLE.md)
for how the studio works and [RESTRUCTURE_SPEC_PROJECTS.md](RESTRUCTURE_SPEC_PROJECTS.md) for why it is
shaped this way.

It is designed around one principle: the models execute a resolved production plan. They
do not silently decide story, performance, camera, canon, continuity or spend.

## Start the Studio

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 cb-studio/serve.py
```

Open `http://localhost:8765/cb-studio/app.html`. The Productions screen lists every project;
entering one switches the studio to it (`STUDIO_PROJECT=<id>` also selects the project at start).
Create a new show with **New production** (the wizard builds it from `studio/templates/project/`).

Run the zero-spend verification suite:

```bash
python3 -m pytest -q
```

Expected result: everything passes except the pre-existing, documented failures (key-art media fixtures,
two audio-timing cases); the skips name unavailable historical media fixtures. After a run, revert the
two project data files the suite still writes into (`git checkout -- projects/crystal-bears/episodes/output/prompt-bank/prompt_bank.jsonl projects/crystal-bears/episodes/output/asset-registry/assets.json`, T64).
After any structural change: `python3 tools/t40_baseline.py --check` must print IDENTICAL.

## The production path

1. Lock canon and the script.
2. Approve episode and scene direction.
3. Separate scenes, beats, generation units and cinematic shots.
4. Approve the Scene Look.
5. Direct, generate, hear and approve voice performances.
6. Build the current scene timing slate.
7. Direct and approve the exact opening frame.
8. Prepare and approve a Seedance shooting script and ordered reference contract.
9. Run the free structure, safety and 20-point craft checks.
10. Review the exact provider request and maximum cost, then explicitly authorise one
    controlled candidate batch.
11. Select a take, harvest its final frame and relay it into the next generation unit.
12. Review continuity, assemble the scene and finish picture and sound.

The detailed contract is in [WORLD_CLASS_PIPELINE.md](WORLD_CLASS_PIPELINE.md). The recovered
branch history and this release's changes are in
[CANONICAL_RELEASE_NOTES.md](CANONICAL_RELEASE_NOTES.md).

The researched Seedance 2.5 scene-generation, provider-migration and delivery plan is in
[SEEDANCE_2_5_PRODUCTION_BLUEPRINT.md](SEEDANCE_2_5_PRODUCTION_BLUEPRINT.md).

## Hard guarantees

- Spoken dialogue words are locked to the script and never enter the visual Seedance
  prompt. `@Audio1` is the sole voice/performance source.
- The first frame is an approved keyframe or the approved previous take's harvested final
  frame.
- Prompt, opening frame, Scene Look, ordered references and voice are lineage-bound. A
  changed direct input makes Animation direction stale.
- No image, voice or video provider is called without the required human approval and
  confirmed billing configuration.
- Every paid batch is disclosed, single-use, resumable and recorded.
- Candidates, approvals, rejections, evidence and costs are preserved.
- Craft scores advise the director; they never pretend to prove that a performance is
  funny, moving or artistically successful.

## Repository map

- `engine/` — the pipeline: planning, validation, generation, safety, approvals, cost controls, post. No show in it;
  `engine/paths.py` reads the active project's `profile.json` (the only path authority) and `engine/project_laws.py`
  reads the project's own laws.
- `cb-studio/` — the studio UI and local API (`serve.py`). No show in it.
- `studio/chairs/<role>/` — the eight generic chairs (writer, director, cinematographer, voice-director, composer,
  animation, continuity, post): craft + runtime contract, `{project}`/`{showrunner}` filled from the profile.
- `studio/templates/project/` — the project template; `engine/project_scaffold.py` / the wizard create a project from it.
- `projects/<id>/` — ONE FOLDER PER SHOW: `profile.json`, `SHOW_BIBLE.md`, `canon/` (facts + the canon lock), `laws/`
  (the show's rules the engine enforces), `chairs/` (the show's taste), `creative/`, `assets/`, `episodes/`
  (scripts, output, media, episodes.json). `docs/` for the show's own documents.
- `tools/` — `t40_baseline.py` (byte-identity proof), `sync_canon.py --project <id>`, `check_links.py`, media backup.
- `dailies/` — evidence review helpers.
- Compatibility links, for one release (T61 removes them): `shows/`→`projects/`, `cb-output/`→the first project's
  output, `engine/config`→its canon, `cb-studio/data/scripts`→its scripts, `skills/*/SKILL.md`→the moved chair
  documents, the root `CRYSTAL_BEARS_*.md`. `tools/check_links.py` verifies them; the studio refuses to start on a
  broken one (a Windows clone without symlink support — enable Developer Mode, `git config core.symlinks true`).

The root Node/Replit files are an older, unrelated interactive project retained from the
original 8th Hour folder. They are not part of this animation production path.

## Local configuration

Provider credentials and real media are intentionally not included in a source handover.
Preserve the production `.env`, approved media and billing profile when installing this
build. Never paste credentials into source files.
