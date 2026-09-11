# WATCH recovery implementation and evidence — 11 September 2026

This implements the current WATCH preparation/retake coordinator from the accepted
[recovery specification](production-recovery-coordinator-v1.0.0.md). It is a scoped
implementation, not qualification of every production route or a claim that live
provider behavior has been verified.

## Connected routes

- `cb_studio_director.py prepare-render` and `retake-render` use a durable operation
  identity and a scene lease. CLI and Studio workers share the same SQLite state.
- `/api/shot-run` retake and ordinary single-candidate Fire without a spend token
  enter that coordinator. The latter prepares a cost decision; it cannot submit
  media. The Director's prepare-render action uses the same path.
- The Studio runner records explicit-token WATCH Fire as a submission operation.
  An interrupted or inconclusive submission reads the matching token's batch
  transport evidence. It never replays the Fire command automatically.
- `/api/production-operations` exposes saved state and transition evidence.
  `/api/production-operation-resume` continues the saved preparation arguments.
  It refuses submission replay and returns reconciliation evidence instead.
- The startup/background recovery pass detects lost workers, preserves live
  worker ownership, and resumes eligible preparation with its existing ID.
  The job feed and WATCH progress strip use operation state, including saved
  failures and uncertain submissions, rather than trusting stale package text.

## Recovery and authority

The operation records correction, reviewed batch, approved SEE/HEAR/scene-plate
records and actual asset bytes, story timing/words/cast, checkpoint, attempt
counts, deadline, spend boundary, sealed payload digest, and resulting evidence.
Scene leases serialize mutations; SQLite launch reservations collapse duplicate
HTTP requests across server instances. Returned provider task IDs are read from
the matching batch only. Media must exist locally before reconciliation exposes
the human review state. A successful process exit alone is not completion.

Retake saves the correction, archives the returned take, refreshes derived
direction, recompiles against current opening/reference roles, and reruns the
normal sealed-request checks. Saved completed preparation checkpoints survive
worker loss. Compilation and final validation run again on resume. Unchanged
SEE/HEAR approvals are retained. Changed approved sources or bytes stop recovery;
the coordinator never renews their evidence to conceal a change.

A specific pre-submission Prompt Director timeout gets at most two attempts,
with backoff. Attempt counts survive restart. Duplicate requests do not replenish
them. The producer can explicitly request one further bounded text-review cycle;
that decision is recorded separately and supplies no media authority. The original
30-minute operation deadline remains in force. Studio stops a preparation child
that exceeds that deadline; CLI checks it at checkpoint boundaries. Other failures
stay saved as needs-attention with the actual failed checkpoint and evidence.

## Executed checks

The focused test command below passed **232 tests** on the staged checkout on
11 September 2026, including the independent-review regressions described below.
Providers were mocked; the repository fixture
prohibited external test networking. HTTP tests used disposable loopback ports
and all production/database writes were redirected to temporary test roots.

```text
python -m pytest \
  cb-studio/test_production_recovery.py engine/test_watch_retake.py \
  engine/test_cb_db.py engine/test_cb_server_security.py \
  cb-studio/test_production_continuation.py cb-studio/test_director_ui.py \
  cb-studio/test_outcome_ui.py engine/test_watch_feedback_see_scope.py \
  engine/test_handoff_preserves_see.py -q
```

Coverage includes simultaneous actual HTTP starts, lost dispatch/worker recovery,
live worker ownership across server restart, same-ID CLI checkpoint resume,
transient timeout exhaustion across resume, explicit bounded text retry, changed
approved bytes, process deadline, uncertain submission with and without a task
ID, ordinary browser cost preparation without media authority, and executed
browser status rendering that hides stale cost readiness during recovery.

The tests exposed a cold-database WAL initialization race; initialization now
retries that bounded local setup operation. Eight older UI assertions also failed
on the untouched baseline. Inspection showed retired templates/copy rather than
runtime failures: they are updated to the current player/words/performance order,
atomic keyframe source selection, dedicated retake form, and collapsed context.

Independent review found and reproduced two further defects before release:

- A prepared operation could retain its terminal cost state after typed WATCH
  direction changed. Preparation now fingerprints current authored shot/card,
  feedback, working text, specialist semantics/reference contracts, source
  authority, additive reference roles, resolved asset paths and current bytes.
  Missing, replaced or consumed cost decisions create one linked new preparation
  lifecycle. Concurrent callers share it. Saved failure/checkpoint fingerprints
  preserve retry counts across unchanged retries and ignore compiler prose and
  record timestamps. New explicit SEE/HEAR authority can start a new retake
  lifecycle; byte changes without a new approval remain blocked against the old
  evidence.
- A null claimed batch ID could accidentally match absent fields and attribute
  old returned media to a newly issued token. Reconciliation now requires a
  nonempty exact batch match. Returned paths additionally require a completed
  batch and matching current ledger batch ID; recorded provider tasks during
  generation remain separate from returned-media evidence.

## Remaining qualification boundaries

- No provider call, media generation, human media approval, Studio restart, or
  production-state mutation was performed as part of these checks.
- Submission reconciliation here is a read of durable local transport evidence.
  It does not query a provider or fetch an already-running task's result after its
  original worker has died. An uncertain task still needs the provider-specific
  reconciliation/retrieval step; this implementation prevents duplicate spend.
- SEE generation, HEAR generation, assembly, post, comparisons, multi-candidate
  preparation, and direct `cb_render.py fire` do not acquire this new operation
  coordinator. Their existing production/spend safeguards remain authoritative.
- Recovery events are durable incident evidence. Automated scene-completion
  incident synthesis and the general typed AI repair-plan executor are not
  implemented by this scoped change.
- A controlled live run must separately verify visible preparation, returned
  media lineage, and producer approval controls before a broader readiness claim.
