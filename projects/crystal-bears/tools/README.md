# Crystal Bears — one-off production tools

Scripts that only ever made sense for THIS show's episodes (a Scene-3 recut, the Scene-1 director-record
import, a golden-emission comparison). T51 (RESTRUCTURE_SPEC_PROJECTS.md, 2026-09-01) moved them here
from `engine/` and `engine/tools/` — the engine is project-agnostic; a project keeps its own tooling.
Run from the repo root, e.g. `python3 projects/crystal-bears/tools/recut_scene6_thirty_second_units.py`.

`build_episode_to_date_preview.py` (moved from `tools/` in T48–T51) builds this show's Ep1 episode-to-date
post preview from its own named shots and review cuts.
