# StudioAI Controlled Reduction Pass 1

Branch: `codex/studioai-reduction-pass-1`

Starting lineage: `integration/reconciled-studioai` at
`81ff42182d8772891191a33e2f00a5a0e17bdc69`

## Result

This pass reduces the visible Director journey without deleting uncertain production code.
The application now presents four phases:

`Script -> Production Package -> Render -> Review`

The existing internal stage state, lineage checks, reference locks, spend controls and
approval actions remain in place underneath the presentation layer. No paid provider is
called by this pass.

## Measured changes

| Measure | Before | After | Change |
| --- | ---: | ---: | ---: |
| Tracked files | 506 | 506 | 0 |
| Runtime Python lines (`engine/`, `cb-studio/`, excluding tests) | 44,429 | 44,429 | 0 |
| Director visible pipeline controls | 10 | 4 | -6 |
| Director pipeline labels | 10 internal labels | 4 phase labels | consolidated |
| Visible scene phases | Stage, Take, Master + separate Render Review | Script, Production Package, Render, Review | 4 |
| Prompt compiler implementations | retained | retained | no unsafe deletion |
| Canon reference copies | 9 | 9 | retained pending parity proof |

## Changed files

Changed files are limited to:

- `cb-studio/app.html`: consolidated the Director-facing scene rail into four phases and
  retained legacy phase aliases for old URLs.
- `cb-studio/director.html`: replaced the ten-button visible rail with four phase controls.
- `cb-studio/director.js`: reports four-phase progress while mapping internally to existing
  production steps.
- `cb-studio/test_director_ui.py` and `cb-studio/test_outcome_ui.py`: updated obsolete UI
  expectations to the current four-phase contract.
- existing Director UI tests: prove the visible reduction and retained protections without
  inflating the baseline suite.
- `REDUCTION_PASS_1_RESULT.md`: this result record.

No production engine module, provider adapter, canon file, approved Episode 1 asset, ledger,
historical document or archive reference was deleted or rewritten.

## Retained protections

The existing suite continues to cover Seedance 2.5 production enforcement, ElevenLabs v3
dialogue authority, exact dialogue and speaker attribution, closed-mouth listeners, timing
budgets, explicit Fire spending approval, single-use spend protection, concurrency,
upstream invalidation, reference locking, STOP handling, QA, retakes, dailies and final
assembly. The reduction tests also assert that internal stage checks remain behind the
four-phase surface and that the UI continues to use the authoritative Director action route.

## Verification

Command:

```text
pytest -q
```

Expected clean-checkout result for the canonical starting suite was `743 passed, 4 skipped`.
The focused reduction/UI suite passed during this pass with `105 passed`. The complete suite
must be rerun from a clean checkout after this branch is pushed; no paid provider calls are
permitted.

## Remaining candidates

These are deliberately not removed in Pass 1:

- duplicate cinematography/DP skill copies, pending runtime reachability and prompt-parity
  evidence;
- legacy prompt and Seedance 2.0 comparison modules, pending explicit quarantine proof;
- duplicated canon reference files, pending one-source resolution tests across every role;
- legacy UI routes and internal stage action names, pending compatibility and rollback proof;
- superseded documentation, pending a complete active-document inventory.

Pass 1 is not a request to delete these items. They remain candidates for a separately reviewed
reduction pass.
