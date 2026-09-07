---
name: seedance-scene-wrapper
description: Design optional Seedance scene establishes, geography entries and exit buttons when those functions strengthen story, continuity or transition.
---

# Seedance Scene Wrapper

Establishes and buttons are available story functions, not compulsory bookends.
Choose them only when the scene needs a distinct opening geography/emotional image
or a separate consequence/transition image. A scene may open or close directly on
coverage when inherited geography, character point of view or uninterrupted emotion
is stronger.

## Wrapper

| Role | Job | Length |
| --- | --- | --- |
| `establish` | Place, scale, threat or emotional temperature | 3-10 seconds |
| `coverage` | Perform the scripted action and dialogue | 4-30 seconds |
| `button` | Show the consequence and provide the scene exit | 3-5 seconds |

## Rules

1. An establishing shot has exactly one job: `location`, `scale`, `threat`, or `emotion`.
2. Do not add an establish when the preceding scene already supplies geography and the
   stronger opening is a character action, discovery or reaction.
3. Do not add a button unless its consequence or transition changes the audience's reading.
4. Establishing shots and buttons carry no dialogue. Ambience only; dialogue is laid in the edit.
5. Each wrapper shot has one dominant camera action.
6. The final frame is held completely stable for one full second.
7. A held frame becomes the next shot's continuity authority only when the declared
   `frameSource` calls for `chain_cut` or `chain_continue`.
8. Scene plates define location, character turnarounds define identity, approved keyframes
   define explicit opening composition, and previous final frames define inherited continuity.
9. Exclude character references from a deliberately character-free wrapper frame.
10. Leave 6-12 frames of breathing room around a wrapper in the edit when useful.
11. Before fire, present and seal the complete score record: creative gate score, Seedance
   authoring score out of 10, firing floor, pass/fail, prompt version/hash, reference set,
   duration, candidate count and provider. The same score record must travel with the spend
   disclosure and fire audit; never report only one score.

## Scene plan

Before writing a prompt, record the scene purpose, location/time, continuity in,
continuity out and coverage list. Then state whether an establish and button are
`required` or `omitted`, with one story reason for each decision.

## Prompt shape

Use one dominant camera action, explicit foreground/midground/background staging,
an explicit end state, and a stable final-second hold. Establish and button
prompts must say `no dialogue`, `ambient sound only`, and must not invent extra
characters or geography.

## Studio fields

The canonical engine stores these fields on each shot:

- `shotRole`: `establish`, `coverage`, or `button`
- `establishJob`: `location`, `scale`, `threat`, or `emotion` for establishes
- `buttonChange`: the consequence shown by a button
- `frameSource`: `scene_plate`, `keyframe`, `chain_cut`, or `chain_continue`

The compiler validates these fields before a prompt can reach a provider.
