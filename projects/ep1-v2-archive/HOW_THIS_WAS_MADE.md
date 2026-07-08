# Episode 1 — v2 Archive: how it was actually made

Scene 1 (Rainforest — Fuzzby & Zenny), as produced by the **2026-06-22/23 "cleanslate" pipeline** — the run Julian named as by far the best take produced so far. This document, plus the "Episode 1 — v2 Archive" project now in the Studio, is the full record: every prompt, every reference image, exactly as it was.

Source of everything below: `_archive_cleanslate_20260622/cbgen/render_scene1.py` (the script that actually fired) and its companion Gate-1 storyboard, `_archive_cleanslate_20260622/cb-output/Ep1_The_Adventure_Begins_shot_package.json`. Quoted verbatim, nothing invented.

## The method — and how it differs from today's pipeline

This is a genuinely different, older system. None of the current `GATE3_ANIMATION_DOCTRINE.md` rules existed yet.

- **Single-image i2v**, via `cb_gen.generate_video_seedance()` — not the current ref2vid / multi-reference system. Each beat was seeded from **one** start-frame image. No character-turnaround images, no scene-plate reference, nothing — the render call carried no reference images at all.
- **Chaining**: beat 1 opened from a hand-built start frame (`media/Ep1_S1_b1_start.png`). Beats 2–4 each opened from `cb_gen.last_frame()` of the *previous* beat's own rendered clip — literally the last extracted frame of the .mp4, no clean-up or re-generation pass.
- **Voice**: `generate_audio=True` — Seedance's own native audio generation produced voice, music and SFX together in one pass. No separate ElevenLabs V3 track, no lip-sync step. **Today this is forbidden** (CLAUDE.md rule 4 / Law 5 — voice must come from one combined @Audio1 V3 track, no native-voice fallback).
- **Dialogue written into the prompt**: every line is spelled out verbatim inside the prompt text (e.g. `Fuzzby, cheerful sing-song: "Bizzy bizzy bizzy... Nailed it!"`). **Today this is forbidden** (Law 6 — dialogue words must never appear in the prompt).
- **Identity carried by description**: a short repeated line (`CONSIST`, below) tells the model Fuzzby is "the BIGGER bumblebee (male, chaotic)" and Zenny is "the SMALLER bumblebee (female, calm)". **Today this is forbidden** (Law 5 / CLAUDE.md rule 5 — identity comes only from reference images, never appearance text).
- **Resolution**: 720p, vs. today's standard tier default.
- **Output**: 4 separate clips (`Ep1_S1_beat1.mp4` .. `beat4.mp4`), never stitched into one file by this script.

**What's missing from the archive**: the actual rendered .mp4 outputs and the very first start-frame image (`Ep1_S1_b1_start.png`) do not survive on disk — only the generation script, the scene plate, the character sheet, and the Gate-1 storyboard survive. Nothing below fills those gaps; they're named as genuinely absent.

## The constant identity line (repeated in every beat's prompt)

> Keep the two bees on-model and the Rainforest consistent throughout: Fuzzby = the BIGGER bumblebee (male, chaotic); Zenny = the SMALLER bumblebee (female, calm).

## The four fired prompts, verbatim

### Beat 1 — "Bizzy... Nailed it" (12s, `media/Ep1_S1_b1_start.png` → `Ep1_S1_beat1.mp4`)

> Multi-shot sequence with clean cuts between shots. Keep the two bees on-model and the Rainforest consistent throughout: Fuzzby = the BIGGER bumblebee (male, chaotic); Zenny = the SMALLER bumblebee (female, calm). Shot 1 (wide establishing, slow push-in): the sun-dappled rainforest of tall pollen-flowers, pollen motes drifting and crystals glinting, as Fuzzby and Zenny weave between the blooms collecting pollen. Shot 2 (cut to a medium shot of FUZZBY): he dips into a flower, scoops a big puff of pollen, overdoes it and spins once, then bounces back upright beaming and proud, full of personality. Fuzzby, cheerful sing-song: "Bizzy bizzy bizzy... Nailed it!" Shot 3 (cut to a wide two-shot): Fuzzby frame-left hovers proud while Zenny frame-right watches him, calm and unimpressed. Lively expressive character animation, snappy comic timing; avoid jitter, avoid identity drift.

### Beat 2 — "I am not a normal bee" (14s, last frame of beat 1 → `Ep1_S1_beat2.mp4`)

> Multi-shot sequence with clean cuts between shots. Keep the two bees on-model and the Rainforest consistent throughout: Fuzzby = the BIGGER bumblebee (male, chaotic); Zenny = the SMALLER bumblebee (female, calm). Shot 1 (wide two-shot): Zenny (frame-right) turns to Fuzzby (frame-left), tilting her head. Shot 2 (cut to a medium close-up of ZENNY): calm and dry, one eyebrow raised. Zenny: "Fuzz-bee, why are you humming?" Shot 3 (cut to a medium close-up of FUZZBY): he puffs up his chest, utterly self-important, wings flaring with pride. Fuzzby, proud: "I am not a normal bee!" Shot 4 (cut to a medium close-up of ZENNY): one slow, flat, deadpan blink. Zenny, dry: "I can agree with that." Shot 5 (cut to a brief wide two-shot): Fuzzby deflates a touch; Zenny gives the tiniest shrug. Big personality, snappy comic timing; pollen motes drift, crystals twinkle. avoid jitter, avoid identity drift.

### Beat 3 — "Do I look official?" (13s, last frame of beat 2 → `Ep1_S1_beat3.mp4`)

> Multi-shot sequence with clean cuts between shots. Keep the two bees on-model and the Rainforest consistent throughout: Fuzzby = the BIGGER bumblebee (male, chaotic); Zenny = the SMALLER bumblebee (female, calm). Shot 1 (wide two-shot): Fuzzby (frame-left) spots a big open pollen-flower and zips toward it eagerly; Zenny (frame-right) watches. Shot 2 (cut to a medium shot of FUZZBY): he plunges his whole face into the flower and pulls back out, his face comically dusted in pollen like a fuzzy moustache, beaming and tilting his head proudly. Fuzzby: "Do I look official?" Shot 3 (cut to a medium close-up of ZENNY): she looks him over, flat and unimpressed, one slow blink. Zenny, dry: "You look dusty." Shot 4 (cut to a brief wide two-shot): Fuzzby wipes a bit of pollen off, sheepish; Zenny stays calm. Big personality, snappy comic timing; pollen motes drift, crystals twinkle. avoid jitter, avoid identity drift.

### Beat 4 — "Storm's coming" (15s, last frame of beat 3 → `Ep1_S1_beat4.mp4`)

> Multi-shot sequence with clean cuts between shots. Keep the two bees on-model and the Rainforest consistent throughout: Fuzzby = the BIGGER bumblebee (male, chaotic); Zenny = the SMALLER bumblebee (female, calm). Shot 1 (wide two-shot): a low thunder RUMBLES; the sky begins to darken and the warm light cools; both bees freeze and glance up. Shot 2 (cut to a medium close-up of FUZZBY): he flinches, then plays it cool with a breezy little wave and a smug grin that cracks into a nervous gulp. Fuzzby, breezy then a comic gulp: "Okay... that sounded dramatic." Shot 3 (cut to a medium close-up of ZENNY): she calmly tilts her head up at the blackening sky, utterly unimpressed, one slow blink. Zenny, flat and dry: "Storm's coming." Shot 4 (cut to a wide two-shot, HELD LONG): the wind gusts hard, petals and leaves whip past, the light goes cold and grey, both bees brace as the first fat raindrops fall — HOLD on this darkening wide for several seconds of rising tension. Big personality, cinematic timing; avoid jitter, avoid identity drift.

## The imagery

| File | What it is |
|---|---|
| `scene1_opening_plate.png` | The scene's locked plate — the closest surviving artifact to beat 1's true start frame (the actual start-frame file no longer exists) |
| `scene1_charsheet_reference.png` | The character sheet available at the time — not itself fed to the render (this pipeline used no reference images at all) |
| `scene1_final_output.mp4` | The referenced WhatsApp video — the finished result these four prompts produced |

All three are copied to `~/Downloads/CB_Ep1_v2_Archive/` for direct viewing, and are also wired into the Studio project below.

## Where to browse this live

Studio → **Projects → Episode 1 — v2 Archive → Episode 999**. All 4 beats are there with their story beat, per-cut breakdown and dialogue. Beat 1 also shows the plate image and the full output video playable inline.

One known display quirk: beats 2–4 don't show their reference image inline in the Studio's per-beat viewer — the viewer's image slot for any non-opening beat expects a *relay-harvested* frame from the current production pipeline's continuation mechanism, which doesn't exist for this older, non-relay-chained archive. The data itself (this document, and the raw package JSON) is unaffected — nothing is hidden, it just doesn't auto-render in that one widget.
