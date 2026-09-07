# Crystal Bears Studio Agent Architecture

Status: foundational direction, HELP mode implemented

## Decision

Keep the existing Crystal Bears production pipeline as the authoritative engine. Put one
Studio Agent control surface above it.

The useful lesson from InVideo Agent 2 is the experience: one conversational production
companion, one visible plan, and one place to understand what happens next. The supplied
prototype implementation must not be imported. It treats file existence as approval,
contains placeholder quality checks, can accept a failed render after a retry cap, and can
assemble incomplete material. Those behaviours conflict with the protections already in
the canonical v2.2 engine.

The Studio Agent is therefore a control plane over the pipeline, never a second pipeline.

## Product Definition

The Studio Agent understands the active canon, immutable script, approved assets, typed
production graph, current selections, approval lineage, quality evidence, and spend policy.
It turns that context into one clear recommendation and coordinates existing specialists.

It must always separate:

- **Built:** an artefact exists.
- **Proven:** the artefact is approved, current, and supported by matching evidence.
- **Proposed:** a plan, candidate, edit, or recommendation still needs a decision.

No conversational language may blur those states.

## Authority Boundary

The pipeline owns:

- immutable scripts and exact source-event coverage;
- the locked canon manifest and stage-specific canon profiles;
- storyboard and production-package lineage;
- typed shot, performance, reference, continuity, and delivery contracts;
- approval freshness and readiness;
- database transactions, scene locks, spend reservations, and provider jobs;
- post-production manifests, QC, and final-master approval.

The Studio Agent owns:

- context compilation;
- explanation and blocker diagnosis;
- one recommended next action;
- structured proposals and impact previews;
- navigation and coordination of existing production commands;
- presentation of evidence and history.

The Studio Agent never owns canon truth, approval truth, spend truth, or provider truth.

## Context Brief

Every interaction is scoped into a signed `StudioContextBrief` with five layers:

1. **Show:** canon manifest digest and stage profile digests.
2. **Episode:** immutable script version and approved Beat package digest.
3. **Scene:** production-package revision, stage states, lineage, and blockers.
4. **Shot:** the selected typed Shot contract and current direct-input evidence.
5. **Task:** Agent mode, requested outcome, target stage, and proposed action.

The brief is content-addressed. A changed script, canon lock, package, selected Shot, stage
state, or blocker creates a different brief ID. An old recommendation therefore cannot be
presented as current without detection.

The Agent receives references and digests by default, not an undifferentiated dump of the
whole show bible. Exact provider packages are compiled only by the existing stage owner.

## Operating Modes

### HELP

Read-only and zero-spend. Explain current state, distinguish built/proven/proposed facts,
identify blockers, recommend one next action, and navigate to an existing workspace.

Implemented in `engine/cb_studio_agent.py` and `/api/studio-agent`.

### PLAN

Create a typed `ChangeProposal` containing target, desired audience effect, exact patch,
affected dependencies, protected elements, reversibility, risk, cost class, and required
human approval. A plan cannot mutate production data.

### EDIT

Apply only an approved, reversible patch through the owning engine command. The patch must
have a before signature, after signature, decision owner, and supersession record. Script,
canon, dialogue, timing, Shot Card, and timeline edits use their own typed patch contracts.

### PREPARE

Compile the exact existing provider envelope, ordered references, protected audio, model and
settings, dependency signature, and cost estimate. Preparation performs no paid call.

### GENERATE

Delegate one sealed, approved request to the existing transaction and spend-protection path.
The Agent cannot create its own provider adapter, retry loop, model fallback, or spend path.

### REVIEW

Compare generated evidence with the approved intent and return a typed diagnosis across
story, performance, identity, picture, dialogue/lip sync, continuity, audio, and technical
delivery. It can propose one evidenced correction but cannot approve its own review.

### DELIVER

Delegate conform, mix, captions, delivery masters, and QC to the existing post-production
gate. "Final" means a current QC-passed master with a human-approved review record.

## Controlled Loop

Every material instruction follows the same loop:

`Understand -> compile signed context -> check locks -> scope selection -> propose -> show
impact/risk/cost -> obtain required approval -> delegate -> review evidence -> record`

The loop stops closed whenever its context signature becomes stale.

## Better Than A Generic Agent

| Generic Agent Pattern | Crystal Bears Studio Agent |
| --- | --- |
| Large prompt containing all context | Signed, task-scoped context layers |
| LLM decides what is ready | Authoritative deterministic readiness policy |
| Agent edits state directly | Typed proposal, then owning command applies approved patch |
| Provider chosen from prose | Versioned capability registry plus human cost policy |
| A file means a stage passed | Approval, content hash, dependency signature, and evidence |
| Automatic fallback and retry | One sealed paid job; explicit redesign or provider decision |
| Batch review after generation | Preflight before spend plus post-generation evidence review |
| Chat history is memory | Append-only decisions, artefact lineage, and promoted learning |
| "Final video" is concatenated clips | Conform, mix, captions, QC manifest, and master approval |

## Model Use

Deterministic code must own state, policy, signatures, money, and command eligibility. A
language model may interpret creative intent, draft a plan, explain evidence, or prepare a
specialist candidate. It cannot be the authority for any approval or spend decision.

Provider routing starts as a deterministic capability registry. Model names, API features,
limits, reference counts, duration, audio support, and prices are versioned evidence that
must be verified before they enter the registry. The Agent may recommend a route and explain
the trade-off; it may not switch silently.

## Implementation Sequence

1. **HELP foundation:** signed brief, current-state explanation, one next action, scene and
   Shot selection, built/proven/proposed evidence. Implemented.
2. **PLAN contract:** persisted proposals with impact analysis and no execution authority.
3. **Command adapters:** allowlisted navigation and reversible free edits through existing
   engine owners.
4. **PREPARE:** sealed request preview using the current production compiler and live rates.
5. **GENERATE:** hand the approved envelope to existing transactions, scene locks, and spend
   reservations.
6. **REVIEW:** structured media evidence and one-variable retake proposals.
7. **DELIVER:** sequence-level review, post-production orchestration, and final master gate.
8. **Conversation:** natural-language command parsing over these typed contracts, never in
   place of them.

## Acceptance Tests

The Studio Agent is production-ready only when tests prove that:

- identical context produces the same brief ID;
- changed direct inputs invalidate the affected brief and no unrelated approved work;
- HELP and PLAN cannot write, approve, run a provider, or reserve spend;
- a stale proposal cannot execute;
- every execution references the exact approved proposal and context signature;
- paid work cannot bypass transaction, scene-lock, billing, and cap checks;
- provider failure cannot trigger an automatic retry or silent fallback;
- review evidence cannot approve itself;
- the golden path preserves every script event and dialogue occurrence through the final
  current, QC-passed master.

## Supplied Documents

The useful Context/Brief split has been retained but strengthened. "Context" is now a signed,
layered projection of authoritative data, and a "Brief" is stage-specific rather than one
table containing episode intent, Shot execution, provider inputs, review, and delivery state.

The one-stop-shop product direction in `THE CRYSTAL BEARS - AI Animation Pipeline.md` is
sound. Its pasted code is treated only as an experience sketch. The canonical engine remains
the implementation authority.
