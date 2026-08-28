# StudioAI Lineage Reconciliation

Date: 2026-08-28

## Cause

`origin/main` (`558a75e9b4046c02f33c7700574e2d86e711e6c2`) and
`origin/codex/reduce-studioai` (`0ebb2e695dd1ca931f03160f6b20adc949a12761`)
have no merge base. Their roots are different (`3685349...` and `1bc6439...`),
so this is separate repository lineage, not a normal branch divergence. The
cleanup lineage has 71 commits and about 504 files; remote main has 43 commits
and about 114 files. Only 73 paths overlap.

## Authority

The cleanup lineage is the authoritative current StudioAI production system. It
contains the functioning StudioAI surface, the full engine (`cb_render.py`,
`cb_providers.py`, `cb_intake.py`, `cb_creative.py`), dailies, current Seedance
2.5 contract, ElevenLabs v3 voice authority, approved output records and the
architecture audit documents. Remote main is the older July shell and lacks
those production modules. No commit was found missing from the cleanup
lineage that should be replayed from main.

## Protection references

Before integration, the exact heads were fetched and verified. These permanent
remote safety references were created:

- `origin/archive/main-before-reconciliation-20260828` -> `558a75e9...`
- annotated tag `studioai-main-before-reconciliation-20260828` -> `558a75e9...`

Local exact-head refs also exist under `refs/archives/lineage/`. The integration
branch starts directly from `0ebb2e695dd1ca931f03160f6b20adc949a12761`.

## Reconciliation

The smallest safe correction is a controlled integration branch from the
cleanup head. Do not merge unrelated histories or cherry-pick only `0ebb2e6`:
its parent chain contains the production system. The branch adds deterministic
test fixtures, reconciles the current typed directing contract, keeps the
dialogue/audio and approval gates intact, and fixes target-shot validation to
walk the full relay ancestry.

## Verification

Exact command: `pytest -q`

Result on `integration/reconciled-studioai`: **743 passed, 4 skipped in 31.91s**.
No paid provider was called. The complete failure-by-failure evidence is in
`TEST_RECONCILIATION.md`.

## Rollback

Delete only the unmerged integration branch if required. Restore the prior main
reference from `studioai-main-before-reconciliation-20260828` or
`archive/main-before-reconciliation-20260828`. No main ref was changed by this
task.

## Decision boundary

The integration branch is ready for final review as the candidate production
lineage. It has not replaced remote main, changed the default branch, deleted
legacy files, or altered approved Episode 1 outputs. Main replacement requires
Julian's separate explicit approval.
