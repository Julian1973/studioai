# StudioAI Target Architecture

## One production state

The existing canonical episode package and shot ledgers remain the source of truth. SQLite
coordinates concurrency and immutable render-rating records. The T34 orchestrator is an
adapter over this state, not a second state machine or JSON database.

## One episode flow

`Script -> Story and Direction -> Production Package -> Control Room -> Fire -> Render QA -> Human Dailies Decision -> Editor`

The Production Package is generated automatically after script approval and contains story
interpretation, screenplay/beat validation, shot direction, keyframe handoff, ElevenLabs v3
audio handoff, Seedance 2.5 prompt, references, continuity, timing, cost and preflight data.

## Provider boundary

All paid animation calls must resolve through the verified Seedance 2.5 contract in
`cb_render.py` / `cb_providers.py`. The explicit 2.0 comparison path is transitional and is
not part of the target production route; it remains until the migration and golden tests
prove it can be archived without breaking historical evidence.

## Review boundary

`cb_dailies.py` records the minimal human call and creates an advisory diagnosis. It never
fires, approves, changes canon, or promotes a learning rule. `cb_learning.py` remains the
only door to active creative memory, and promotion remains explicitly human-controlled.

## Remaining reduction work

- Complete runtime reachability map for versioned skills and route aliases.
- Add parity tests for the single 2.5 adapter and 30-second beat budget.
- Consolidate duplicate state projections in the server after parity.
- Archive obsolete skill/specification copies after reachability is proven.
- Keep approved Episode 1 output readable throughout the migration.
