---
name: seedance-shot-extension
description: Continue an approved Seedance shot from its actual source clip while preserving audiovisual state, advancing only the new dramatic delta, and engineering a usable landing frame.
---

# Seedance Shot Extension

Use this skill when new material must continue an approved source clip. The source
clip is ground truth for inherited motion, performance, composition, geography,
lighting and sound. Original approved references remain authority for identity,
scale, wardrobe, props and location design.

Read `skills/seedance-production-director/references/extension-workflow.md` and
`official-capabilities.md`. The production-director skill owns final prompt quality;
this skill owns the extension boundary and state contract.

## Refusal Gate

Do not prepare an executable extension unless:

- the exact source clip is named and human-approved;
- the provider operation is verified or accurately marked conditional;
- completed actions and current audiovisual state are recorded;
- the new beat differs from what has already happened;
- each continuity-critical subject has an original identity authority;
- dialogue uses approved audio and the correct speaker mapping;
- the intended landing state can open the following unit.

Never extend a drifting candidate or treat a provider task ID as returned media.

## Canonical Contract

Exchange extension data through `engine.cb_seedance_contract.ExtensionContract`.
The public record is snake_case and versioned as `seedance-extension/v1`.
Internal camelCase input is accepted only through the typed adapter. Unknown fields
are rejected rather than silently ignored.

Required principles:

1. `@Video1` is the approved continuity master.
2. State `already_true`, then direct only the new delta.
3. Pin the verified provider operation outside the creative prompt.
4. Keep one to three verifiable identity anchors per continuity-critical subject.
5. Carry lighting and sound state literally across the join.
6. A bridge declares one sole geography master.
7. The extracted final frame is QA evidence by default, not a competing authority.
8. Finish on an exact physical and audiovisual landing state with a brief living hold.

## Prompt Shape

```text
EXTENSION AUTHORITY
Extend @Video1 forward.
The first frame of the extension continues directly from the last frame of @Video1.
Preserve inherited motion, performance, composition, character state, screen
direction, lighting, geography, music, ambience and sound state. Do not reset.

ALREADY TRUE
[Observable completed facts.] Continue without replaying them.

REFERENCE CONTRACT
[One role and authority boundary per attached asset.]

AUDIO AUTHORITY
[@Audio1 mapping, active speaker, closed-mouth listeners, inherited ambience.]

OPENING SPATIAL STATE
[Positions, depth, axis, eyelines and action phase.]

NEW DRAMATIC DELTA
[Setup, development and payoff for the new beat only.]

LANDING STATE
[Camera, composition, positions, gaze, action phase, props, lighting and sound.]
Settle into a brief living hold without introducing a new action.
```

Use internal cuts only when they reveal consequence, change point of view, land
comedy, clarify geography or catch a meaning-changing reaction. Duration follows
the honest performance and reference complexity; 30 seconds is capacity, not a
target. Preserve successful instructions when repairing a failed continuation and
return to the last clean approved master when drift is already present.

## Human Authority

Return the contract, prompt, reference manifest, score record and unresolved risks
for review. Never call a provider, authorize spend, lock media or advance WATCH.
