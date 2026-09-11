---
title: Production Recovery Coordinator
version: 1.0.0
decision: accepted-by-Julian
decision_date: 2026-09-11
implementation: pending
qualification: pending-route-and-live-evidence
---

# Production Recovery Coordinator

## Locked decision

One producer instruction starts one durable production operation. Studio owns preparation, recovery and delivery through completion or a specific decision requiring the producer. Individual technical steps must not abandon the operation and send the producer back through unchanged approvals.

AI diagnoses and repairs production state using bounded, validated tools. It does not rewrite running application code to force a generation through. Shared code improvements are developed and tested separately, then released between active production operations.

This is a Studio-wide requirement for every project and SEE, HEAR, WATCH, assembly and post route. It is not an S2.SH1 exception. Acceptance of this specification is not implementation or Studio-wide readiness.

## Durable ownership

Persist operation ID, project/episode/scene/shot/version, requested correction, approved source hashes, exact payload hash, reference bindings, spending authority, current checkpoint, recovery attempts, provider task IDs and outcome. Resume from durable state after process restart. A lease and idempotency key prevent competing workers or duplicate submissions.

States: queued, preparing, diagnosing, repairing, validating, awaiting-spend-approval, submitting, reconciling-submission, rendering, reviewing, awaiting-creative-decision, completed, needs-attention, cancelled. Preserve each transition and its evidence. Completed means the requested artifact/outcome is persisted and accessible, not merely that a subprocess exited successfully.

## Recovery contract

1. Capture the actual failed stage and exact evidence before diagnosis.
2. Classify into a supported recovery action. AI may propose a tool plan; typed scope and invariant validation must authorize its execution.
3. Recover stale derived direction, source-role bindings, compiler output and temporary transport failures through existing production tools. Refresh only affected inputs and downstream products.
4. Retain human approvals when their actual dependencies are unchanged. Never renew hashes to conceal a changed source. Preserve original evidence and record any justified carry-forward separately.
5. Revalidate the resulting current payload through the same first-fire checks. No missing reference, story conflict, failed identity check or uncertain submission becomes a pass merely to finish.
6. Reconcile an uncertain provider submission before retrying. Query by provider task ID/idempotency evidence; never resubmit blindly. Waiting on a busy scene does not start another provider job.
7. Use bounded retries, backoff, an overall deadline and authorized spending limits. Repeated identical failures stop automatic repetition and become a saved, resumable needs-attention outcome with an exact explanation. Do not hide an exhausted recovery loop behind perpetual progress.
8. Do not change approved words, audio bytes, duration, story beats, cast, opening image, or scene plate unless the producer's correction authorizes that change. A genuine creative choice returns to the producer as that choice, not technical debugging.
9. Preparation never implies approval to spend. Existing explicit spending authority can carry within its declared scope; otherwise present the sealed cost decision. Human approval of returned media remains separate.

## Producer experience

Reject → explain correction → Retake is one operation. The correction stays saved and visible. Show useful progress such as “Updating the vision reference”, “Checking the animation request”, and “Rendering”. Technical logs belong in expandable evidence.

Successful preparation presents the cost/Fire decision, or continues to submission when already authorized. Successful submission presents provider progress; returned media presents Approve / Reject. Keep SEE and HEAR current during WATCH-only recovery. Never display “Ready to fire” while checks are incomplete or another operation owns the scene.

A temporary failure is handled automatically with a progress update. An unrecoverable fault is not hidden: retain the operation, name the specific remaining issue and provide a direct resume or decision action. Never claim a render was submitted or returned without corresponding evidence.

## Learning after production

Every recovery writes an incident linked to the original request, failure, diagnosis, tool actions, changed fields, validation, retries, cost and final outcome. Once the scene is complete, review these incidents together, distinguish provider limitations from integration defects, and prioritize shared fixes by root cause.

Add regression coverage reproducing each confirmed failure, verify unaffected routes and approval preservation, and release shared fixes between active jobs. A lesson is proposed until tested; a fixture pass is not proof of live semantic/image understanding. Version the fix and link its tests and release to the incident.

## Required acceptance evidence

- A WATCH-only rejection preserves unchanged SEE/HEAR approvals and reaches a current cost review without another approval cycle.
- A stale derived handoff and cached geography/reference mismatch are repaired before the sealed request is accepted.
- Two simultaneous actions serialize; only one authorized media submission occurs.
- Restart during preparation resumes the same operation and correction.
- Restart or timeout during submission reconciles the existing provider task without duplicate spend.
- A transient Prompt Director timeout retries automatically; repeated timeouts terminate bounded recovery with an actionable saved state.
- Genuine changes to opening, plate, words, timing or reference authority invalidate the correct affected stages.
- Unauthorized creative changes and spending are rejected before tool execution.
- Successful returned media appears in Studio with correct lineage and human review controls.
- Every failure and recovery has durable evidence, including proof of no media submission where applicable.
- Scene completion produces an incident review and links shared fixes to meaningful regression tests.
- Route-level tests cover actual UI/API entry points; a controlled live run separately qualifies user-visible behavior. No broad readiness claim before that evidence exists.

## Existing partial foundations

The current checkout contains bounded scene-lease waiting, one automatic retry for a specifically identified pre-submission Prompt Director timeout, preservation of SEE across derived WATCH handoff, retake recompilation against approved geography/reference bindings, and retake progress UI. These are components, not the complete persistent coordinator. Restart ownership, unified recovery planning, submission reconciliation and the full acceptance matrix still require implementation and qualification.

## Changelog

### 1.0.0

- Recorded the accepted recovery ownership, producer experience, learning loop and evidence boundaries.
