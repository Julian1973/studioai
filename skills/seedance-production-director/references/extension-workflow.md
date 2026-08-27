# Video extension and long-form chaining

## Contents

1. Core rule
2. Preflight
3. Refusal gate
4. Extension prompt architecture
5. Join and handoff rules
6. Conditional backward-leading material and bridges
7. Failure recovery

## Core rule

Create a playable continuation of approved footage, not a fresh imitation. Use the actual approved preceding clip as the continuity master. Preserve its interface tag exactly.

Begin with:

    Extend the video forward from @Video1.
    Begin as a direct audiovisual continuation of its ending.

Describe only the new dramatic delta. Anything restated as action may be performed again.

### Final-frame policy

Extract the final frame for visual QA and the continuity ledger by default. Do not automatically attach it as a competing opening authority.

When a tested interface requires or benefits from it, scope it narrowly:

    @Image1 confirms only the inherited closing composition of @Video1.
    It does not replace @Video1 as motion, performance or audiovisual authority.

Never use a still that disagrees with the actual uploaded ending.

### Trim policy

If failed material follows the desired join, trim to the last clean point. Retain enough preceding footage and audio to establish motion, performance, camera direction, dialogue/music handle and sound state. There is no universal 15-second trimming rule.

## Preflight

### Confirm the master

Record the exact clip/take and mark whether it is approved. If identity, geography, state or sound already drifted, repair it or return to the last clean master.

### Build the beat

Define:

- dramatic purpose and leading experience;
- already-completed facts;
- new action only;
- setup, development and payoff;
- intended cuts versus continuous reframing;
- target duration;
- exact landing picture and sound.

### Contract the references

| Role | Authority |
|---|---|
| Master video | inherited motion, performance, composition, editing rhythm, light and sound state |
| Character | canonical design, proportions, scale, clothing and accessories—not pose/background |
| Location | geography, landmarks, materials and palette—not identity |
| Prop | exact design and current state |
| Audio | speaker, exact words, cadence, delivery, timing, mouth timing and silence |
| Style | rendering/material language only |
| Clay/blocking | camera path, pose, trajectory, spatial structure and blocking only |
| Closing target | landing composition only |

### Record already true

Capture:

- current positions, facing, depth and screen direction;
- pose, gaze, expression and action phase;
- relative scale;
- costume, wearable, prop and accumulated physical state;
- camera size, height, axis and motion;
- landmarks, light source and time;
- active speaker, listener state, music, ambience and sound;
- completed actions that must not repeat.

## Refusal gate

Do not produce an extension prompt until these are known or explicitly marked unresolved:

- source master is named;
- master is approved;
- operation is supported or accurately described for the selected route;
- at least one already-true fact is recorded when prior action matters;
- identity authority exists for every continuity-critical visible character;
- location/geography authority exists when spatial continuity matters;
- approved dialogue/audio is mapped when speech exists;
- new dramatic beat is distinct from completed action;
- landing state is usable by the next unit.

Two or three concise anchors are usually sufficient at a risk point, but do not impose an arbitrary number when more facts are genuinely required for an ensemble.

## Extension prompt architecture

Use only relevant sections.

    FORMAT
    [Duration, aspect ratio, locked visual treatment.]

    EXTENSION AUTHORITY
    Extend the video forward from @Video1.
    Begin as a direct audiovisual continuation of the ending of @Video1.
    Preserve inherited motion, performance, composition, character state,
    screen direction, lighting, geography, music, ambience and sound state.
    Do not reset the scene.

    ALREADY TRUE
    [Completed actions and observable opening state.]
    Continue without replaying these facts.

    REFERENCE CONTRACT
    [One exact role per tagged asset.]

    AUDIO AUTHORITY
    [Exact approved audio mapping, active speaker, closed-mouth listeners,
    inherited music/ambience and prohibited unapproved sound.]

    OPENING SPATIAL STATE
    [Positions, depth order, eyelines, axis and screen direction.]

    NEW DRAMATIC BEAT
    [The visible change and whose experience leads.]

    Shot 1: [size, useful lens if needed, camera behaviour].
    [Causal action, performance, blocking and motivated production detail.]
    [CHARACTER: Exact dialogue where spoken.]

    Cut to.

    Shot 2: [consequence, reaction or changed point of view.]

    Cut to.

    Shot 3: [payoff and transition into landing composition.]

    CONTINUITY SAFEGUARDS
    [Only likely material failures.]

    LANDING FRAME
    [Exact camera, composition, positions, gaze, expression, action phase,
    prop state, light, sound and next-beat negative space.]
    Settle into a brief living hold without freezing or new action.

Omit Cut to for a continuous take. Describe a motivated pan, track, orbit, occlusion, rack focus or reframing instead.

## Join and handoff rules

- Continue the inherited action phase; do not reset to a neutral pose.
- Carry travel direction, gaze, limb phase and energy across a cut.
- Preserve camera axis unless the shot visibly crosses or resets it.
- Carry literal light source, direction, quality and effect.
- State whether music and ambience continue, develop, resolve or stop.
- Place reactions after their trigger.
- Give each cut one purpose.
- Fund every action and reaction with duration; remove the least important beat before compressing all beats.
- Design the final picture and sound as the next unit's opening asset.
- Budget a finishing grade and sound-continuity pass across the assembled chain.

## Conditional backward-leading material and bridges

Read official-capabilities.md first. Do not call either native unless provider support is verified.

When constructing new material that must lead into an existing clip:

- declare the existing approved clip as the required destination state;
- work backwards from its opening pose, direction, camera and sound;
- avoid an action whose natural result contradicts that destination;
- end the new material one readable action phase before the destination;
- confirm editorial assembly can create the join.

When connecting two approved clips:

- choose one sole geography master;
- preserve identity from original canon references;
- define source closing state and destination opening state separately;
- make the bridge perform only the missing causal action;
- reject a smooth join that changes story logic, identity, scale or geography.

## Failure recovery

| Symptom | Repair |
|---|---|
| Opening resets/repeats | Shorten already-true facts; direct only the delta; verify the master and operation |
| Resembles but does not continue | Strengthen direct audiovisual-continuation language; remove competing opening authorities |
| Identity/proportions drift | Return to the last clean master and original character authority |
| Character swaps/duplicates | Separate each character's role, tag and spatial position; add one-of-each safeguard |
| Scale/depth changes | State relative size, depth, hover/ground height and nearest comparison character |
| Geography flips | Restate axis, screen direction, landmarks and depth; use a neutral re-establishing view if needed |
| Cut feels random | Make it reveal consequence, reaction or new information |
| Listener mouths dialogue | Put active-speaker and closed-mouth rules next to the affected line |
| Prop/wearable resets | Add it to already-true state, reference role and closing ledger |
| Light/sound jumps | Carry inherited source/state literally, then describe only the motivated change |
| Master already drifted | Stop; repair or return to the last clean approved clip |
