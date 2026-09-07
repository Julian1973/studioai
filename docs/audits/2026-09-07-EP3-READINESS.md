# Episode 3 production readiness

The operating requirement is a clear next action from story to scene cut. The director
reviews story, image, performance, cost and film. Technical preparation belongs to the Studio.

## Targeted verification

On 7 September, after consolidation:

- Current production path and shared production contracts: 15 passed in 6.78 seconds.
  The isolated three-shot fixture generated and approved voice, accepted an opening image,
  rendered and accepted each shot, carried continuity and reached an approved scene master.
  It verified three provider calls and the exact approved prompts.
- Browser outcome, intake lineage and new continuation tests: 106 passed in 0.99 seconds.
  Five new tests execute the actual `prepareDirectionThen` JavaScript with fake transport.
  Current direction continues immediately; reused and newly prepared direction refresh state
  before continuing once; failure does not continue; navigation to another scene does not
  continue the original action there.
- `git diff --check` passed. No production packages or media were changed and no provider
  was contacted. This work adds regression coverage, not another runtime policy.

## What this establishes

The tested production sequence and automatic preparation continuation work with controlled
inputs. The tests do not constitute a complete live Episode 3 browser rehearsal: specialist
creative inputs, scene look and provider responses are fixtures. They cannot prove that a new
script will produce excellent direction or that an external provider will remain available.
The first real Episode 3 shot remains the live acceptance check of that complete chain.

## Live acceptance standard

1. Import and approve the Episode 3 story; show its scenes in order with an obvious next action.
2. Establish the scene look, review the opening image and hear required performances.
3. Fire prepares current direction automatically and continues to the exact cost review.
4. Generate one authorized candidate; show its progress and then the playable result.
5. Accept the watched result; carry the approved continuity into the next active shot.
6. Assemble the accepted shots for scene-cut review and final approval.

A changed technical revision alone must not undo a creative acceptance. An unchanged approved
take remains available. A real missing or contradictory input must name the affected shot,
explain the issue and present a direct recovery action. An uncertain paid submission must
retain its record and avoid duplicate submission. A reproducible failure to meet these
conditions is a software defect to repair, not an extra production rule for the director.

Broader evidence and remaining recovery limitations are recorded in
[the consolidation result](2026-09-07-CONSOLIDATION-RESULT.md).
