# Studio Loop Spec

This local copy records the implemented Studio loop contract when the upstream PR artifact
is not available to the checkout.

## Emission Firing Floor

Render emissions must score at least 9.5 in `cb_emission_standard.preflight`.
Anything below the floor is blocked before spend.

## Prompt Bank Record

Every approved or rejected animation prompt is written append-only to
`cb-output/prompt-bank/prompt_bank.jsonl`.

Required record fields:

- `schemaVersion`
- `recordId`
- `bankedAt`
- `episode`
- `scene`
- `shotId`
- `artifactType`
- `outcome`
- `approved`
- `diagnosis`
- `category`
- `candidate`
- `candidatePath`
- `promptHash`
- `promptText`
- `parsed`
- `archetype`
- `conformance`
- `metadata`

The `parsed` object is created at bank time and includes section order, section sizes,
total character and word count, shot count, dialogue presence and audio policy signals.

The v1 query surface is:

```bash
python3 engine/cb_prompt_bank.py report
python3 engine/cb_render.py prompt-bank
```

It reports section-order frequency, character-count distribution and archetype win rate.

## Render Continuity Modes

Each non-opening shot defaults to `keyframe-handoff`: the previous approved shot's harvested
final frame is the first image reference.

A non-opening shot may opt into `video-extension`: the previous approved clip is attached as
`@Video1`, the prompt receives a continue-forward directive, and the still-image reference
pack remains attached for identity, scene and style control.

CLI selector:

```bash
python3 engine/cb_render.py continuity-mode <scene> <shotId> keyframe-handoff [episode]
python3 engine/cb_render.py continuity-mode <scene> <shotId> video-extension [episode]
```
