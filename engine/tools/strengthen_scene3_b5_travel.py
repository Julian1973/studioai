#!/usr/bin/env python3
"""Add the approved R9 traversal direction to Scene 3's combined departure unit."""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import shutil


ROOT = pathlib.Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "cb-output" / "Ep1_scene3_production_package.json"
ANCHOR = "Mum lifts one paw; Keen waves back. "
TRAVERSAL = (
    "As the boat starts travelling, preserve the emotional medium-wide while showing three "
    "parallax speeds: foreground rope, post and near water pass fastest; Keen and the boat move "
    "at a middle speed; Mum, the pier and island recede slowest. The mooring post passes the "
    "camera and vanishes behind, with occasional foreground rope or rigging wipes across the "
    "lens. Let the boat pull slightly smaller as it moves away, then let the camera gently surge "
    "to recover Keen. Allow the boat to drift off-centre toward open water before the camera "
    "restores the shared composition with Mum still readable behind him. "
)


def main() -> None:
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    shot = next(item for item in package["shots"] if item["shotId"] == "3.B5.S1")
    if TRAVERSAL in shot.get("action", ""):
        return
    if ANCHOR not in shot.get("action", ""):
        raise RuntimeError("Scene 3 B5 travel anchor is missing")

    archive = ROOT / "cb-output" / "archive" / "scene_recuts"
    archive.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    shutil.copy2(PACKAGE, archive / f"Ep1_scene3_before_b5_r9_{stamp}.json")

    shot["action"] = shot["action"].replace(ANCHOR, ANCHOR + TRAVERSAL, 1)
    shot.setdefault("directorRecord", {})["action"] = shot["action"]
    package.setdefault("revisionNotes", []).append({
        "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "reviewedBy": "Julian",
        "change": (
            "Added R9 traversal evidence to 3.B5.S1: three parallax speeds, a passing landmark, "
            "subject scale change, off-centre recovery and foreground lens wipes."
        ),
    })
    PACKAGE.write_text(json.dumps(package, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
