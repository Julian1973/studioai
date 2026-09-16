# Studio Loop Spec

## Current loop

The current Studio loop is:

`SCRIPT → DIRECT → SEE → HEAR → WATCH → FIRE → REVIEW`

DIRECT is the only creative authority. SEE visualizes approved direction as a Scene Plate,
one Opening Keyframe owned by the current generation unit, and an optional Illustrated
Storyboard. HEAR creates ElevenLabs v3 Audio1 from exact dialogue and DIRECT performance.
WATCH mechanically emits the provider prompt, references and audio without creative
substitution. FIRE submits the sealed request to BytePlus. REVIEW is human Approve or
Retake.

## Readiness and prompt integrity

The producer preview and the actual Fire route call the same zero-spend WATCH readiness
implementation. It verifies:

- current DIRECT
- current approved SEE
- current approved Audio1 when dialogue exists
- current reference files and hashes
- no unresolved provider operation
- `authoredActionHash == emittedActionHash`
- valid BytePlus model, duration, settings and cost contract

A failure returns one current blocker. It does not call a specialist or rewrite direction.

## Continuity

New generation units use editorial cuts. Each unit owns an Opening Keyframe. The next unit
preserves story state and visual identity while choosing its own composition. Normal current
production does not require a previous final frame, a previous video, `@Video1`, an extension
source or pixel-for-pixel continuation.

Historical keyframe-handoff, video-extension and specialist records remain readable for
provenance. They cannot supply current production authority.

## Submission, recovery and approval

The sealed request binds exact DIRECT action, SEE assets, references, Audio1 and provider
settings. A known provider task is polled or recovered by its task ID. An unknown submission
outcome blocks retry until reconciled.

Returned-media approval validates the sealed request, provider task, returned media hash,
reference hashes and Audio1 hash. It does not compare against unrelated mutable working
metadata.

## Prompt Bank

Approved and rejected animation prompts remain append-only in
`cb-output/prompt-bank/prompt_bank.jsonl`. They are evidence and learning material, not a
fallback authority for current WATCH compilation.
