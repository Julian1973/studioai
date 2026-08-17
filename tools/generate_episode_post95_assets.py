#!/usr/bin/env python3
"""Generate the scene-level score and ambience assets for the 95% review pass.

Assets are generated once and then reused. This script never edits approved picture,
dialogue, render candidates, or approval state.
"""

from __future__ import annotations

import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
ENGINE = ROOT / "engine"
sys.path.insert(0, str(ENGINE))

import cb_gen  # noqa: E402


ROUTE = "cb_render"
MEDIA_SUBDIR = pathlib.Path("post95")
OUTPUT_DIR = ENGINE / "media" / MEDIA_SUBDIR

MUSIC = {
    "scene1": {
        "duration_ms": 44288,
        "file": "Ep1_Scene1_score_post95.mp3",
        "prompt": (
            "Instrumental cinematic score for a premium warm family animation. Start with nimble, "
            "playful pizzicato strings, soft marimba and tiny woodwind gestures supporting a chaotic "
            "bee chase and proud comic mishaps. Keep the rhythm buoyant and quick but never frantic "
            "or harsh. Around two-thirds through, drain the brightness, introduce low soft strings and "
            "distant restrained percussion as storm clouds arrive. Leave clear space for dialogue and "
            "comic effects throughout. End unresolved but gentle, with a small thread of courage. No "
            "vocals, no choir, no melody that competes with speech, no trailer impacts."
        ),
    },
    "scene2": {
        "duration_ms": 23792,
        "file": "Ep1_Scene2_score_post95.mp3",
        "prompt": (
            "Instrumental cinematic underscore for a tender mystical family-animation scene at a "
            "crystal cove. Begin nearly weightless with warm glassy harmonics, soft felt piano and one "
            "slow breathing string line. Bloom gently as rose-pink light reveals a distant vision of a "
            "child and mother, then fall almost to silence for the quiet line of recognition. Resolve "
            "with calm purpose rather than triumph. Intimate, emotionally sincere, spacious and warm. "
            "No vocals, no choir, no percussion hits, no sentimental excess, no melody over dialogue."
        ),
    },
    "scene3": {
        "duration_ms": 102333,
        "file": "Ep1_Scene3_score_post95.mp3",
        "prompt": (
            "Long-form instrumental cinematic score for an emotionally warm family-animation farewell "
            "at a sunlit wooden pier. Begin with gentle acoustic plucks, felt piano and soft strings as "
            "a young bear checks supplies with his mother. Let affection and unspoken worry deepen; thin "
            "to near-silence around the mother's keepsake gift and their most important promises. Return "
            "with a warmer open harmony for the embrace and preparation to sail. Add a tiny touch of "
            "playful woodwind when a small sea companion appears, then broaden into hopeful wind-filled "
            "strings as the boat moves toward the sun. Keep dialogue completely clear, avoid constant "
            "melody, and finish with quiet forward motion rather than a huge ending. No vocals, no choir, "
            "no trailer drums, no abrupt changes."
        ),
    },
}

AMBIENCE = {
    "scene1": {
        "file": "Ep1_Scene1_ambience_post95.mp3",
        "prompt": (
            "Seamless lush flower-corridor rainforest ambience at bee height: gentle leaf movement, "
            "soft distant insects, light petal rustle and airy natural space. No speech, no music, no "
            "close buzz, no discrete impacts, no thunder. Stable loop with no obvious beginning or end."
        ),
    },
    "scene2": {
        "file": "Ep1_Scene2_ambience_post95.mp3",
        "prompt": (
            "Seamless quiet crystal-cove shoreline ambience: very gentle small waves, soft distant wind "
            "and subtle open coastal air. No voices, no birds, no music, no singing bowl, no magical "
            "chimes. Calm stable loop with no obvious beginning or end."
        ),
    },
    "scene3": {
        "file": "Ep1_Scene3_ambience_post95.mp3",
        "prompt": (
            "Seamless warm tropical pier and calm open-water ambience: soft water against timber and a "
            "moored wooden boat, light sea breeze, distant gentle shore wash. No voices, no music, no "
            "gulls, no rope squeaks, no discrete splashes. Stable loop with no obvious beginning or end."
        ),
    },
}


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, spec in MUSIC.items():
        target = OUTPUT_DIR / spec["file"]
        if target.exists() and target.stat().st_size:
            print(f"reuse music {name}: {target}")
            continue
        print(f"generate music {name}...")
        cb_gen.eleven_music(
            spec["prompt"],
            length_ms=spec["duration_ms"],
            out=str(MEDIA_SUBDIR / spec["file"]),
            production_route=ROUTE,
        )
        print(f"generated: {target}")

    for name, spec in AMBIENCE.items():
        target = OUTPUT_DIR / spec["file"]
        if target.exists() and target.stat().st_size:
            print(f"reuse ambience {name}: {target}")
            continue
        print(f"generate ambience {name}...")
        cb_gen.eleven_sfx(
            spec["prompt"],
            duration=20,
            out=str(MEDIA_SUBDIR / spec["file"]),
            loop=True,
            production_route=ROUTE,
        )
        print(f"generated: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
