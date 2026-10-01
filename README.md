# Studio Ai

Studio AI is a human-directed, approval-gated production platform. Its current
qualified animation workflow takes Crystal Bears from script to finished scene.
Additional productions can be onboarded into isolated show profiles and immutable
script stores; their shot-production adapters must be qualified before generation.

It is designed around one principle: the models execute a resolved production plan. They
do not silently decide story, performance, camera, canon, continuity or spend.

## Start the Studio

For a repeatable workstation installation, use the
[workstation guide](docs/STUDIO_WORKSTATIONS.md):

```bash
python3 scripts/studio.py install --verify
python3 scripts/studio.py doctor
python3 scripts/studio.py run
```

This release candidate targets Linux and Python 3.12. Studio macOS/Windows machines
and shared multi-user deployment still need separate qualification.

The original developer setup remains:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 cb-studio/serve.py
```

Open `http://localhost:8765/cb-studio/app.html`.

Run the zero-spend verification suite:

```bash
python3 -m pytest -q
```

Latest verified baseline: **755 passed, 4 skipped**. The skips name unavailable historical
revision-6 media fixtures; the current production route is covered and passes.

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

- `cb-studio/` — production command centre and local API.
- `engine/` — planning, validation, generation, safety, approvals, cost controls and post.
- `shows/crystal-bears/` — show-specific canon, scripts, laws and production state.
- `skills/` — runtime production-department contracts, including the Seedance Production
  Director.
- `cb-output/` — production packages and evidence.
- `tools/` — canon, media and field-audit utilities.

## Additional productions

The New Project wizard creates a canonical `shows/<show-id>/profile.json`,
project identity, character references, bible, visual style and episode directories.
Projects are discovered from published manifests; legacy archives remain visible.
Script uploads name their project explicitly and preserve immutable script versions
inside that project's tenant. Reopening a development project shows its own screenplay
without entering the active show's production workflow.

New projects start in development. `studio-generic-v1` is a declared future adapter,
not an installed production capability. Live action and arbitrary animation are not
yet qualified for shot generation. See [delivery gates](docs/STUDIO_PLATFORM_DELIVERY.md).

The root Node/Replit files are an older, unrelated interactive project retained from the
original 8th Hour folder. They are not part of this animation production path.

## Local configuration

Provider credentials and real media are intentionally not included in a source handover.
Preserve the production `.env`, approved media and billing profile when installing this
build. Never paste credentials into source files.
