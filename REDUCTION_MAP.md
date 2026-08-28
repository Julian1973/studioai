# StudioAI Reduction Map

Audit date: 2026-08-28

This is the controlled reduction plan. “Archive” means move only after reachability and
golden-output tests pass. “Delete” is intentionally empty in the first pass.

| Area | Decision | Reason / exit test |
| --- | --- | --- |
| `cb-studio/serve.py` | KEEP, then MERGE projections | Live authenticated entry point; remove only duplicated projection code after API parity tests |
| `engine/cb_render.py` | KEEP | Current owner of spend, media, approvals and continuity; split only by clear ownership |
| `engine/cb_orchestrator.py` | MERGE carefully | T34 contract is useful, but it must not become a second state store; adapt around existing ledger |
| `engine/cb_learning.py` | KEEP | Human-approved active memory and promotion safety are established |
| `engine/cb_dailies.py` | KEEP as review adapter | Lightweight rating/decision/diagnosis records; no approval or provider authority |
| `engine/cb_providers.py` | KEEP, then consolidate | One 2.5 production adapter is required; 2.0 comparison must be quarantined or removed after migration tests |
| `engine/cb_seedance_transport.py` | ARCHIVE comparison branch | Retain only as an explicit migration fixture once no active caller remains |
| `skills/*-v3`, `skills/*-v4` | ARCHIVE candidates | Prove runtime reachability and prompt parity before moving |
| `skills/crystal-bears-camera` | MERGE into Cinematic Shot Director | The supplied shot-director skill is the intended owner of camera/shot design |
| `skills/crystal-bears-dp` and cinematographer skills | ARCHIVE candidates | Avoid duplicate creative authority after shot-director parity tests |
| `cb-output` generated packages | KEEP as artifacts | Never import them as application configuration |
| old specifications and dispatch notes | ARCHIVE by date | Keep audit history without leaving competing current doctrine |
| destructive deletion | DELETE: none yet | Safety requirement: no deletion before map, tests and approved-output checks |

## Target human decisions

1. Approve script.
2. Fire a verified render.
3. Approve, retake or reject the render, optionally rating 1–5 and adding a note.

All other work is automatic preparation, validation, or evidence collection and must remain
non-spending unless the Fire decision is explicit.
