# Recurring-character and ensemble continuity

## Contents

1. Authority model
2. Cast manifest
3. Spatial continuity
4. Risk-point anchoring
5. Dialogue and reactions
6. Project production rules
7. Ensemble QA

## Authority model

Use original approved turnarounds or canon references for identity. Use the current approved master clip for inherited pose, movement, performance and scene state. Use the approved location reference for geography. Never allow a composite group frame or drifted generation to replace original identity authority.

Each prominent visible character receives:

- exact asset tag;
- unique name and role;
- canonical scale/proportion authority;
- current wardrobe, wearable and prop state;
- opening position and depth;
- dialogue/audio mapping if speaking;
- one-of-each status.

## Cast manifest

Before a group generation, write a compact manifest:

| Character | Identity tag | Scale authority | Opening position | State | Speaker? |
|---|---|---|---|---|---|

Count the cast explicitly. Require exactly one of each scripted character and no unscripted additions when duplication or substitution is a realistic risk.

Do not spend prompt space describing characters who are off-screen and irrelevant to the beat. If an off-screen character speaks, map the audio and state that the speaker remains off-screen.

## Spatial continuity

Record:

- left-to-right order and foreground/midground/background depth;
- screen direction and eyeline target;
- ground contact or hover height;
- relative height against the nearest known character;
- distance from landmarks and props;
- negative space reserved for an entrance, reveal or action;
- camera axis and any motivated crossing.

Use relationship language: beside, behind, shoulder height, half a body-length screen-right, deeper in the midground. Avoid vague “nearby” blocking.

## Risk-point anchoring

Reassert only decisive identity and spatial facts after:

- occlusion;
- exit or re-entry;
- fast motion, flight or transformation;
- a major angle or shot-size change;
- a group crossing paths;
- a character handling or exchanging a prop.

Two or three anchors often work for one character, but an ensemble may require more total facts. Prefer unique visual anchors and relative positions over full biographies.

## Dialogue and reactions

- Identify the active speaker next to every line.
- Keep every listener naturally closed-mouth.
- Stage a reaction after its audible or visual trigger.
- Prevent a group reaction from obscuring the main performance.
- When laughter or vocal reaction is approved, specify exactly who participates and when.
- Preserve eyelines so listeners look toward the actual speaker or action.

## Project production rules

The active project's own ensemble rules live in its chair overlay — `projects/<id>/chairs/animation.md`
(T52). The generic rules every project shares:

- Retrieve the latest approved project references rather than relying on remembered appearance.
- Preserve the project's height hierarchy and unstretched body proportions.
- Bind every recurring character to its own identity reference; never treat two similar characters as interchangeable.
- Track each character's wearable / physiology state (the project's continuity rules) as episode state.
- Track every character's colour accents, clothing and accessories from its own reference.
- Keep small characters genuinely small relative to larger ones; never enlarge them to fill a close shot.
- Distinguish identity truth from group-composition truth: a continuity frame may control placement while original turnarounds control appearance.
- Use exactly the scripted cast. Do not add background duplicates of established characters.
- If a character fails identity or scale QA, do not accept the shot as the next master even when the action is attractive.

## Ensemble QA

Approve only when:

- cast count and one-of-each status are correct;
- every face, body, wardrobe and wearable matches its original authority;
- heights and proportions remain correct without stretching or compression;
- no two characters exchange traits, colours, props or voices;
- spatial order, depth, screen direction and eyelines remain coherent;
- speaking and listening mouth states are correct;
- entrances, exits and occlusions preserve identity on reappearance;
- accumulated state carries through;
- the landing frame records every character needed next.
