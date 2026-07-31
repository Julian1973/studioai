# Seedance 2.5 Manual Test - Episode 1, Scene 1

This is a manual, no-API test pack for the 30-second rainforest pollen scene with Fuzzby
and Zenny. It does not restore the archived episode or alter Crystal Bears Studio state.

## Run this first

Use `PROMPT_01_VISUAL_30S.txt`. It isolates the central Seedance 2.5 question: can one
30-second generation preserve both characters, five clear editorial beats, physical comedy,
camera rhythm and the warm-to-storm lighting turn?

Settings:

- Model: Seedance 2.5 only if that exact model is selectable.
- Mode: Omni reference / reference-to-video.
- Aspect ratio: 16:9.
- Duration: 30 seconds.
- Resolution: 720p or 1080p for the first test; do not pay for 4K until the scene works.
- Audio generation: off, if the interface provides that control.
- Candidate count: one.

Upload these four files in this order:

1. `assets/01_opening_frame.png` - opening composition and starting state.
2. `assets/02_Fuzzby_turnaround.jpeg` - Fuzzby identity only.
3. `assets/03_Zenny_turnaround.jpeg` - Zenny identity only.
4. `assets/04_scene_look.png` - environment, materials, palette and lighting only.

The prompt uses `@Image1` through `@Image4`. After uploading, use the platform's `@`
selector to bind each reference. If BytePlus gives the files different tag names, replace
the tokens in the prompt with the names shown by the interface.

## Lip-sync test

Only after the visual test is worth pursuing, use `PROMPT_02_AUDIO_15S.txt`.

Upload the same four images, then upload:

5. `assets/07_dialogue_guide_first_15s.wav` - the available approved Scene 1 dialogue
   performances placed on a 15-second, 48 kHz, 24-bit stereo timeline.

Use 15 seconds, 16:9 and one candidate. Bind the WAV as `@Audio1` or replace that token with
the tag assigned by the interface.

The source dialogue files are also included separately:

- `assets/05_Fuzzby_SH1_approved_voice.mp3`
- `assets/06_Fuzzby_Zenny_SH2_approved_voice.mp3`

The guide contains only dialogue that was actually approved before the episode reset. The
Scene 1 voices for the crash, storm reaction and final exchange were never present as
approved source files, so this pack does not fabricate them.

## Full 30-second dialogue capability test

Use `PROMPT_03_FULL_DIALOGUE_30S.txt` for the requested end-to-end Scene 1 test. Upload only
the same four ordered images, bind `@Image1` through `@Image4`, set 16:9 and 30 seconds, turn
native audio generation on, and generate one candidate. Do not upload the dialogue guide or
the two MP3 files for this version: it deliberately tests the model's own two-character voice
assignment, English dialogue, sound design and lip sync. The generated voices are temporary
and cannot become approved production dialogue.

## Reference provenance

- The opening frame was human-approved in the archived production history, then superseded
  and archived during later work. It is suitable for this manual comparison but is not a
  current production approval after the fresh-project reset.
- The Fuzzby and Zenny files are the locked final turnaround references.
- The Scene Look is byte-identical to the historically approved flower-meadow plate.
- The two source voice files were approved in the archived production history.
- Rejected video generations, rejected Scene Looks and unverified keyframes are excluded.

Exact hashes and source classifications are in `UPLOAD_MANIFEST.json`.

## What to inspect before another generation

Record one verdict for each item:

- Fuzzby identity remains stable for all 30 seconds.
- Zenny remains smaller, distinct and never changes into Fuzzby.
- Both characters retain the reference glasses, stripes, wings and proportions.
- The five timeline beats occur in order and are not compressed into chaos.
- Every collision has readable contact, weight, recoil and consequence.
- Zenny's quiet precision remains the comic contrast.
- The camera uses motivated cuts and does not wander randomly.
- The environment remains the same place as light changes toward the storm.
- No extra characters, crystals, hearts, captions, logos or random text appear.
- The final flower impact reads clearly and the scene ends on a usable held image.

Put the downloaded result and a short review note in `results/`. Inspect that file before
authorising any reroll or higher-resolution generation.
