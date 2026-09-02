# 8th Hour Animation Studio

The canonical Crystal Bears production build: a human-directed, approval-gated AI
animation pipeline from script to finished scene.

It is designed around one principle: the models execute a resolved production plan. They
do not silently decide story, performance, camera, canon, continuity or spend.

## Start the Studio

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

Expected canonical result: **969 passed, 4 skipped**. The skips name unavailable historical
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

The root Node/Replit files are an older, unrelated interactive project retained from the
original 8th Hour folder. They are not part of this animation production path.

## Local configuration

Provider credentials and real media are intentionally not included in a source handover.
Preserve the production `.env`, approved media and billing profile when installing this
build. Never paste credentials into source files.

OpenAI text direction is cost-routed and guarded by default:

- `gpt-5.5` is used only for episode Story & Direction.
- `gpt-5.4-mini` is used for scene, shot, keyframe, voice, animation and review direction.
- Identical signed inputs reuse the local structured response instead of calling the API again.
- One provider attempt is made; exhausted credit and other non-retryable errors stop immediately.
- `OPENAI_MAX_CALL_USD=1.00` and `OPENAI_DAILY_BUDGET_USD=5.00` refuse work before an API call.
- Actual input, cached-input and output token usage is recorded in the gitignored cost ledger.
