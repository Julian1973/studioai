# StudioAI Before Architecture Audit

Audit date: 2026-08-28
Repository root: `/Users/julianjenkins/Desktop/Ai Studio`

## Current runtime path

`cb-studio/serve.py` is the authenticated HTTP entry point. It dispatches specialist work
to the engine, while `engine/cb_render.py` owns the shot ledger, spend authorization,
provider handoff, candidate media, approvals and continuity invalidation. JSON production
packages remain the creative artifacts; SQLite owns leases, spend claims and render ratings.

The current path is therefore functional, but not yet minimal: `serve.py` mirrors some
state projection logic, `cb_render.py` remains a very large owner, and older specialist
skills and provider comparison code are still present.

## Verified owners to preserve

| Responsibility | Current owner | Decision |
| --- | --- | --- |
| Script intake and episode vision | `engine/cb_intake.py` | KEEP |
| Scene/beat package creation | `engine/cb_creative.py` | KEEP |
| Shot/keyframe/voice/video ledger | `engine/cb_render.py` | KEEP |
| Concurrent leases and spend claims | `engine/cb_db.py` | KEEP |
| Canonical provider checks | `engine/cb_providers.py` and `cb_production_preflight.py` | KEEP, consolidate later |
| Human approvals | `cb_render.py` ledger methods | KEEP |
| Final assembly | `engine/cb_post.py` and `cb_post_workspace.py` | KEEP, inspect overlap |
| Dailies learning | `engine/cb_learning.py` + `engine/cb_dailies.py` | MERGE boundary only after parity tests |

## Known conflicts requiring controlled reduction

- Seedance 2.5 is the intended production route, but an explicit Seedance 2.0 comparison
  adapter remains in `cb_providers.py` and `cb_seedance_transport.py`.
- Multiple versioned director/cinematography/DP skill directories remain. Runtime mapping
  must be proved before archival.
- The new `cb_dailies.py` is an additive lightweight review record, while Prompt Lab has a
  separate detailed rating model. These must not become competing approval sources.
- Historical output and generated episode files are mixed under `cb-output`; they must not
  be treated as source configuration.

No deletion is authorized by this audit alone. Existing approved media and their ledgers are
protected until replacement tests and migration checks pass.
