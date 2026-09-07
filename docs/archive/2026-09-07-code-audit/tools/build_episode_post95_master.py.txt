#!/usr/bin/env python3
"""Build the current full-episode, native-audio assembly review candidate."""

from __future__ import annotations

import argparse
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from cb_episode_post import build_episode_assembly  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", default="Ep1")
    args = parser.parse_args()
    print(build_episode_assembly(args.episode))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
