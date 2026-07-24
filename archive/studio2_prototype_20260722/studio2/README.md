# CRYSTAL BEARS — STUDIO 2
Three files. That's the studio.

**Status:** a standalone prototype, not the live production path. The live pipeline is `engine/cb_*.py`
fired through `cb-studio/serve.py`, governed by the root `CLAUDE.md` / `PRODUCTION_DOCTRINE.md` /
`GATE3_ANIMATION_DOCTRINE.md`. This directory's own word budgets and rules below are this prototype's own
regime and do not reflect the live system's.

- **canon.yaml** — the show's truth: style, negatives, one movement line per character, scenes.
- **ep1_s1.yaml** — the beats: the script's own action, under 80 words each, voice moments placed, words never written.
- **studio.py** — the engine: keyframe → fire → your eye → approve → harvest → next beat → stitch.

## The loop
    python3 studio.py keyframe ep1_s1.yaml     # once per scene — Julian signs the image
    python3 studio.py walk ep1_s1.yaml         # fires the next beat, then STOPS for your eye
    python3 studio.py approve 1.B1             # or: reject 1.B1 "one sentence why"
    python3 studio.py walk ep1_s1.yaml         # next beat — repeat to 1.B5
    python3 studio.py stitch ep1_s1.yaml       # settle-trimmed joins → scene.mp4

## The laws (the scars)
One canon file. Engine is the only prompt author. Prompt target 250 words, hard safety cap 280, story ≤80.
One movement line per character — no poses, no negations, no appearance.
Dialogue words never in prompts — the V3 track fires IN as @Audio1, never post.
Openers inherit nothing; relay beats open from the APPROVED predecessor only.
Rejected takes are dead. One render per fire. Julian's eye gates every take.
