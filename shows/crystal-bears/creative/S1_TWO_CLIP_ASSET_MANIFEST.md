# Scene 1 as two 30-second clips — asset manifest

All paths relative to `/Users/julianjenkins/Desktop/8Th Hour/`. Every file below was
verified present on disk 2026-08-01.

## Reference images

| Slot | File | Job |
|---|---|---|
| `@图1` **Clip A** | `engine/media/shots/Ep1_S1.SH1_keyframe_candidate_588a0d29.jpeg` | The exact opening frame — composition, camera side, both positions, scale, light |
| `@图1` **Clip B** | *harvested from Clip A's approved take* | Same job. See "The relay" below — this does not exist until Clip A is fired and approved |
| `@图2` | `cb-seed/assets/final_turnarounds/CB_Fuzzby.jpeg` | Fuzzby identity only |
| `@图3` | `cb-seed/assets/final_turnarounds/CB_Zenny.jpeg` | Zenny identity only |
| `@图4` | `cb-seed/assets/locations/deep_rainforest_flower_meadow.png` | The world only — light, palette, plant texture. Never framing or pose |

`@图4` is the locked plate (locations.json, locked 2026-07-24). The prompts state
explicitly that where it and `@图1` disagree on light, the plate wins.

## Audio

**Clip A's dialogue already exists as approved takes.** Both files are real V3
performances already fired and kept:

| File | Length | Contains |
|---|---|---|
| `engine/media/shots/Ep1_S1.SH1_vo.mp3` | 4.08s | the BIZZY hum, then "Nailed it." |
| `engine/media/shots/Ep1_S1.SH2_vo.mp3` | 6.64s | "Do I look official?", then "Officially nuts!" |

They cannot be used as-is. Both were cut for 12-second shots, so the lines sit
seconds apart; Clip A needs them ~15s apart. The four lines have to be split at
their own silence and placed at the beat times the prompt calls:

    hum                  0.0s
    "Nailed it."        15.5s
    "Do I look official?"  26.0s
    "Officially nuts!"     28.2s

`cb_render.build_timed_master` does exactly this — cuts an approved take at its own
silence and places the parts, same performance, no re-voice.

**Clip B needs four new lines.** None exist yet:

| Speaker | Line | Lands |
|---|---|---|
| Fuzzby | Buzz Crash!! | ~12.5s |
| Fuzzby | …okay that sounded dramatic. | ~20.0s |
| Zenny | A Storm's coming. | ~24.5s |
| Fuzzby | Good thing I work well under pressure. | ~27.5s |

All four verbatim from the script. Delivery notes, following the same register as
the approved takes: Fuzzby's first is a triumphant pop straight out of the blossom;
his second drops right down, genuinely caught off guard; Zenny's is quiet and flat,
no drama in it; his last is chest-out bravado that the flower immediately punishes.

## The relay

Clip B opens on Clip A's own final frame. That frame does not exist until Clip A is
fired and you have approved it — so the order is fixed:

1. Fire Clip A.
2. Approve it.
3. Harvest its final frame (the sharpest frame in the closing beat, not just the
   literal last one).
4. That harvested frame becomes Clip B's `@图1`.

`engine/media/shots/Ep1_S1.SH1_final_frame.png` already exists, but it is the end of
the OLD 12-second SH1 take — it ends on the superhero pose, not on the "Officially
nuts!" exchange Clip A now closes on. It is the wrong frame for this structure. Do
not use it as Clip B's opener.

## The one thing I could not verify

The pipeline has only ever run 15-second generations. I have no confirmed knowledge
that a 30-second single generation is available on the surface you are firing
through, or what it costs there. Both prompts are written to 30s as asked, timed
across their whole length, and both split cleanly at their own midpoint if the
surface turns out to cap shorter — Clip A at 14s (the pose) and Clip B at 14s (the
blossom pop) are real beat boundaries, not arbitrary cuts.

Worth checking the surface's own current limit before firing, since a refused 30s
call and a silently truncated one look different and only one of them wastes money.
