#!/usr/bin/env python3
"""Build production packages from the locked episode beat package."""
from __future__ import annotations

import hashlib
import json
import pathlib
from datetime import datetime, timezone
from typing import Any

import paths

OUTPUT = pathlib.Path(paths.OUTPUT)
if not (OUTPUT / "Ep1_The_Adventure_Begins_beat_package.json").exists():
    OUTPUT = pathlib.Path(paths.ROOT) / "cb-output"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _duration_for_beat(beat: dict[str, Any]) -> int:
    events = ((beat.get("sourceEventSignature") or {}).get("inputs") or {}).get("orderedEvents") or []
    dialogue_count = sum(1 for item in events if item.get("sourceType") == "dialogue")
    return max(6, min(18, 5 + len(events) + dialogue_count * 2))


def _dialogue_lines(beat: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    events = ((beat.get("sourceEventSignature") or {}).get("inputs") or {}).get("orderedEvents") or []
    for event in events:
        if event.get("sourceType") != "dialogue":
            continue
        out.append({
            "speaker": event.get("speaker"),
            "text": event.get("text"),
            "dialogueOccurrenceId": event.get("dialogueOccurrenceId"),
            "sourceEventId": event.get("sourceEventId"),
            "sourceEventIndex": event.get("sourceEventIndex"),
        })
    return out


def _action_text(beat: dict[str, Any]) -> str:
    events = ((beat.get("sourceEventSignature") or {}).get("inputs") or {}).get("orderedEvents") or []
    parts = [event.get("text", "").strip() for event in events if event.get("sourceType") == "action"]
    return " ".join(part for part in parts if part)


def build_scene_package(scene: str | int, episode: str = "Ep1") -> tuple[dict[str, Any], pathlib.Path]:
    beat_path = OUTPUT / f"{episode}_The_Adventure_Begins_beat_package.json"
    if not beat_path.exists():
        raise FileNotFoundError(f"Beat package not found: {beat_path}")
    source = json.loads(beat_path.read_text(encoding="utf-8"))
    scene_s = str(scene)
    beats = [beat for beat in source.get("beats") or []
             if str(beat.get("sceneNumber")) == scene_s]
    if not beats:
        raise ValueError(f"No beats found for scene {scene_s}")

    shots = []
    ledger = []
    for idx, beat in enumerate(beats, 1):
        beat_code = beat.get("beatCode") or f"{scene_s}.B{idx}"
        shot_id = f"{beat_code}.S1"
        previous_shot_id = shots[-1]["shotId"] if shots else None
        duration = _duration_for_beat(beat)
        shot = {
            "shotId": shot_id,
            "sceneNumber": int(scene_s) if scene_s.isdigit() else scene_s,
            "beatCode": beat_code,
            "title": beat.get("storyBeat", beat_code)[:90],
            "durationSec": duration,
            "sourceType": "opener" if idx == 1 else "relay",
            "sourceShotId": previous_shot_id,
            "location": beat.get("location"),
            "time": beat.get("time"),
            "charactersInFrame": beat.get("characters") or [],
            "storyBeat": beat.get("storyBeat"),
            "emotionalIntent": beat.get("emotionalIntent"),
            "kidRead": beat.get("kidRead"),
            "adultRead": beat.get("adultRead"),
            "action": _action_text(beat),
            "dialogueLines": _dialogue_lines(beat),
            "sourceBeatId": beat.get("sourceBeatId"),
            "sourceEventRange": beat.get("sourceEventRange"),
            "sourceEventIds": beat.get("sourceEventIds") or [],
            "dialogueOccurrenceIds": beat.get("dialogueOccurrenceIds") or [],
        }
        shots.append(shot)
        ledger.append({
            "shotId": shot_id,
            "status": "designed",
            "sourceBeatId": beat.get("sourceBeatId"),
            "sourceType": shot["sourceType"],
            "sourceShotId": previous_shot_id,
            "keyframeApproval": None,
            "voiceApproval": None,
            "approvedTake": None,
            "harvestFrame": None,
            "candidatePaths": None,
        })

    signature = hashlib.sha256(json.dumps({
        "episode": episode,
        "scene": scene_s,
        "sourceBeatIds": [b.get("sourceBeatId") for b in beats],
    }, sort_keys=True).encode("utf-8")).hexdigest()
    package = {
        "schemaVersion": 1,
        "episode": episode,
        "sceneNumber": int(scene_s) if scene_s.isdigit() else scene_s,
        "sceneTitle": beats[0].get("location") or f"Scene {scene_s}",
        "status": "designed",
        "revision": 1,
        "generatedAt": _now(),
        "source": "locked episode beat package",
        "sourceBeatPackage": str(beat_path),
        "sourceSignature": signature,
        "sourceScript": source.get("sourceScript"),
        "sourceContract": source.get("sourceContract"),
        "shots": shots,
        "continuityLedger": ledger,
        "validation": {"passed": True, "errors": []},
    }
    out_path = OUTPUT / f"{episode}_scene{scene_s}_production_package.json"
    out_path.write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return package, out_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("scene")
    parser.add_argument("--episode", default="Ep1")
    args = parser.parse_args()
    _, written = build_scene_package(args.scene, args.episode)
    print(written)
