# Engine Rules

These rules apply to every project, scene and shot. Shot-specific creative choices remain
Director data. Provider prompts are deterministic compiler outputs, never manually authored
production truth.

## R1 - Dialogue Synthesis

For every scripted line, emit the exact locked text once as an attributed English dialogue
placement marker inside the stage where it is spoken. Declare `@Audio1` the sole authority
for voice identity, cadence, delivery, mouth timing and silence. Permit no alternative
performance. Named listeners remain silent and closed-mouth. Ban narration, extra words,
subtitles and captions.

Provider audio is a performance and lip-sync guide, not the final dialogue master. Prompt
text never contains file-internal voice timecodes.

## R2 - Dialogue Post Lane

Every dialogue render records an audio-provenance ledger. The approved voice master is
restored in post; provider dialogue is removed. Foley, ambience and score remain separate
mix layers. A dialogue shot cannot ship without proof that this post lane ran.

## R3 - Beat-Cost Timing

Timing beats use versioned minimum costs. Unit duration is the sum of typed beat costs and
button holds, plus the versioned margin. Duration is a request parameter, not prompt prose.
An over-stuffed unit is blocked before spend.

Only an explicit `action-timing` verdict diagnosing compression may raise a beat cost.
Successful shots and unrelated verdicts never lower or raise costs automatically.

## R4 - Cross-Compiler Geometry

SEE and WATCH read the same approved geography and camera policy. Contradictory direction
blocks both emissions and names the conflicting fields. A follow camera cannot be paired
with an opening pose that faces the travelling subject toward the lens.

## R5 - Playable Opening Stage

For travelling action, the opening frame must show visible depth ahead, lead room in the
ruled direction and every route object needed by the action. Subjects travel away from or
across the camera as directed. A beautiful but unplayable frame fails SEE mechanically;
creative approval remains Julian's decision after the defect is corrected.

## R6 - Duration Provenance

An asset can constrain duration only when it was produced after that unit's beats were
costed. Older keyframes, audio and reference images remain valid inputs but never silently
become timing authority.

## R7 - Generalisation

An engineering defect is closed only by a project-agnostic rule and an executable test.
Compiler rules cannot name a production shot, scene or character. Director data may name
all of them because specificity is its purpose. A one-off creative correction is not an
engine fix and does not close a defect class.

## R8 - Multi-Shot Emission

Continuous relay may remain one shot. Action units use two to four motivated internal shots.
Every shot has one clean motion idea. A cut that releases stored physical energy belongs at the
maximum-load image, never at an incidental midpoint.

## R9 - Traversal

Travel must show three parallax speeds, landmarks passing the camera and vanishing behind it,
subject scale change, recoverable off-centre drift and occasional foreground lens wipes. Blur
alone cannot prove travel.

## R10 - Escalating Contacts

Repeated contacts are individually separated and readable, with each visibly larger than the
last. Equal contacts are blocked as repetition without escalation.

## R11 - Compound Moves

Any multi-rotation or multi-stage aerial owns a dedicated internal shot whose camera tracks the
complete arc. `aerial` is a versioned timing beat with a 1.8-second minimum.

## R12 - Self-Check

Retroactive-intention comedy requires a visible self-check before the character performs pride
or another claimed emotion. `self_check` is a versioned 1.2-second timing beat. A gag marked
retroactive without that typed beat is blocked.

## R13 - Witness

The payoff of a two-character gag holds on the non-acting witness. Their stillness and the hold
length carry the joke. Canonical staging sides are Director data copied verbatim by the compiler.

## R14 - Action Exclusions

`No cuts` and `no handheld` are continuous-relay protections only. They are invalid in action
units because they suppress motivated edits and energy.

## R15 - Dialogue In Its Beat

Every scripted line is emitted once inside its owning beat with a named speaker, approved
delivery and a full-beat pose hold after the line. Detached dialogue-placement blocks fail
preflight. The provider performance remains guide audio; the approved master is restored in post.
