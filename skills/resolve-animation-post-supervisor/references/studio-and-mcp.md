# AI Studio and Resolve operations

Canonical workspace: `/Users/julianjenkins/Desktop/Ai Studio`. Use its existing records rather than a second database or parallel approval pipeline. The local app is served at `http://127.0.0.1:8899/cb-studio/app.html`; a file:// page is disconnected.

Locate the selected Studio project and episode first. Approved screenplay, shot direction, SEE, HEAR and WATCH retain their respective authority. Missing original stems remain missing; a flattened soundtrack cannot be relabelled as approved HEAR. Retrieve the actual project's character IDs and references.

## Project production workflow

- `skills/project-production-standard.md`: project-agnostic creative direction.
- `engine/studio_production.py`, `studio_editing.py`, `studio_review.py`: shared project command ledger, outcome approvals, scoped revisions, review notes and assembly fingerprints.
- `engine/studio_post_contract.py`: source-bound Post Supervisor brief carried in `source-manifest.json` by the existing **Create finishing handoff** action. It includes this project's context, approved outcome IDs and media hashes, exact direction and voice references, with the assembly approval state stated separately.
- The accompanying FCPXML references original approved media. Inspect its declared timebase and actual source rates before conforming; it is interchange data, not a verified Resolve edit.
- Return findings against the recorded project/episode/shot and assembly version. Missing action or voice changes return to the selected shot's existing proposal/review path. Preserve other approved shots and inspect affected joins. Do not write generic project results into the legacy episode-only ledger.

This is a manual, source-bound handoff. The Studio does not yet dispatch durable Resolve editing jobs or import their returned candidates into the project ledger. Use available Codex Resolve tools for explicitly requested work and report this boundary; do not invent completed jobs or additional approval records.

## Legacy Crystal Bears finishing desk

The legacy companion is `skills/seedance-production-director/SKILL.md`. Existing episode records and their explicit review route remain authoritative. These endpoints are episode-only; they are not storage for other projects.

Integration points (inspect implementation before writing):
- `engine/cb_finishing.py`: candidate-bound brief, live Resolve snapshot, enhancement job lifecycle.
- `engine/cb_post_workspace.py`: candidate discovery and version-bound verdicts.
- `engine/cb_vcube.py`: secure VOD adapter and readiness.
- `cb-studio/finishing.html` and `finishing.js`: review player, findings, brief and human decisions.
- `tools/register_resolve_review.py`: legacy candidate registration, live timeline/frame-count check; no automatic Drive verification or approval. It currently qualifies only 30 fps review exports. This is not a universal post-production frame rate.
- `docs/finishing/davinci-vcube.md`: actual transport and review contract.

Read the actual runtime contract and relevant references before execution. Preparing a brief does not dispatch an editing agent or run QC. The UI must describe those states accurately.

## Capability preflight
Locate the configured MCP repository and inspect its instructions. Current local path: `/Users/julianjenkins/Documents/ChatGPT/Divinvi/davinci-resolve-mcp`. Establish Resolve version/edition, bridge response, current project/timeline and required operation support with a read-only call. Registration alone is not connectivity. Prefer native API/MCP, then supported UI for missing controls; don't invent API names or claim every native feature is exposed.

The working bridge has used `src.utils.resolve_bridge_client.connect(timeout=8, require_enabled=False)` from the repo's `venv/bin/python`. Recheck current support; edition or runtime may change. Do not make a purchase or swap providers to recover connectivity. On timeout, read live state before repeating mutations.

Before edits record project, timeline ID/name, fps, start frame, track topology and active source version. Duplicate the timeline for a repair candidate and verify edits/track muting apply to that duplicate. Save, read back starts/durations/source bounds and preserve the original. Avoid uncontrolled large batch operations; prove one representative change first when the route is untested.

Scope existing user authorization to the task. Reversible repairs and review exports may proceed when requested. Ask only for genuinely missing inputs or a new action outside authority, explaining why. Keep approvals for changed approved story/voice, destructive replacement, spending and publication as applicable; do not repeatedly ask for the same granted permission.
