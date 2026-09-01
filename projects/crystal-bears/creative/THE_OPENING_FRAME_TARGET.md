# THE OPENING FRAME — THE TARGET, FROM JULIAN'S OWN EXAMPLE

**2026-07-27.** After four failed keyframes and a morning of prompt rewrites, Julian produced
a frame and said: *"Here is a perfect example of the shot."* This file records what makes it
right, so nobody has to rediscover it.

## THE FRAME

Both bees hovering in an open sunlit wildflower field — lavender spikes, white daisies, red
clover, crystals in the grass, low warm sun behind them, soft bokeh. Fuzzby frame-left and
visibly larger; Zenny frame-right, smaller, at the SAME distance from camera. Each about a
third of frame height. No ceiling, no tunnel, no foreground obstruction.

## WHY IT WORKS — FIVE THINGS, ALL OF THEM DELETIONS

1. **THE WORLD COMES FROM THE PLATE, NOT FROM WORDS.** Same flowers, same light, same
   crystals as `Ep1_S1_plate`. Nobody described an environment; the plate supplied it.

   The four failures did the opposite. Their reference line read *"@图4 only for the world —
   corridor palette, flower and leaf materials, sky and sun state"* — the plate demoted to a
   COLOUR SWATCH, allowed to tint but not to define space. The words then built a dark
   enclosed rainforest corridor, and architecture beat tint every time. The plate is the
   world: the space, the light and the openness come from it.

2. **BOTH CHARACTERS AT COMPARABLE DEPTH, SO SIZE READS.** Canon says Fuzzby is bigger and
   Zenny smaller. That fact is only VISIBLE when they are the same distance from the lens.
   Every failed frame put Fuzzby a body-length away and Zenny ten metres back, where
   perspective decides everything and the size relationship is unreadable — the frame was
   trying to establish something its own staging made impossible.

3. **THEY ARE IN THE WORLD, NOT FILLING IT.** About a third of frame height. Wide enough to
   be a stage, close enough to read as characters. The failures asked for one-sixth in words
   and rendered at ~45%, because an absolute identity clause ("match 100%, every feature
   exactly") outranks a hedged scale clause ("roughly one-sixth") in every render.

4. **NO ARCHITECTURE.** No leaf ceiling, no corridor, no foreground stem swinging past the
   lens. "Corridor" appears ZERO times in the script and 48 times in the storyboard; it
   entered through `locations.json`'s own `definingFeature`, and it built a tunnel every
   time. A near-miss is MOTION and belongs to Seedance, which has fifteen seconds. A still
   cannot show a near-miss; it can only show clutter.

5. **IT IS FORGIVING.** Both bees hover with air all around them. The performance can begin
   in any direction without contradicting the frame. A frame pinned to one hyper-specific
   instant — an exact roll angle, a precise mid-upstroke — is a sculpture, and every frame of
   motion after it reads as a departure from something the model was told to honour.

## THE CANON CONTRADICTION THIS EXPOSED — NOT YET FIXED

`shows/crystal-bears/canon/locations.json`, Ep1 scene 1, describes two different worlds:

| field | says |
|---|---|
| `look` | "An open sunlit wildflower meadow read at bee scale — purple lavender spikes, white daisies" |
| `name` | "Deep Within the Rainforest" |
| `definingFeature` | "Towering pollen-heavy rainforest flowers forming natural **corridors**…" |
| `locationId` | `deep_rainforest_flower_meadow` — both, at once |

`look` is right and matches the plate. `name` and `definingFeature` are the rainforest the
renders kept obeying. Julian, 2026-07-27: *"rainforest i dont want that is my fault"* — the
slugline is his and he does not want it.

The script's own SLUGLINE says `EXT. DEEP WITHIN THE RAINFOREST – DAY`, but its very next
sentence describes the field: *"Tall flowers sway gently in the warm breeze. Some stretch
high above the grass."* The prose was always right; the heading was always wrong.

**Not changed yet, deliberately:** editing the script changes its hash and invalidates the
storyboard lineage, which forces a Scene 1 rebuild. That is Julian's call to time, not a
cleanup to slip into a commit. Dialogue is untouched either way — a slugline is not dialogue.

## WHAT TO CHANGE FIRST

The reference-role line in `cb_departments.prepare_cinematography`. The plate must govern the
WORLD — space, light, openness, the kind of place this is — not merely the palette. That is
one line, it is the same shape as the two fixes that did work today (scope a reference
correctly and the render stops fighting itself), and it is upstream of most of the rainforest
cleanup: with the plate governing space, "corridor" has far less to grab onto.

## THE HONEST LIMIT

This is one frame Julian liked, made outside the pipeline. It is a TARGET, not a proof. The
five observations above are drawn from a single example against four failures — strong
evidence for a direction, not a demonstrated law. Nothing here has been reproduced through
our own fire path yet.
