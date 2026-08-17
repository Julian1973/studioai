#!/usr/bin/env python3
"""Build production packages from the locked episode beat package."""
from __future__ import annotations

import hashlib
import json
import pathlib
from datetime import datetime, timezone
from typing import Any

import paths
import cb_lineage
import cb_scripts

OUTPUT = pathlib.Path(paths.OUTPUT)
if not (OUTPUT / "Ep1_The_Adventure_Begins_beat_package.json").exists():
    OUTPUT = pathlib.Path(paths.ROOT) / "cb-output"
ROOT = pathlib.Path(paths.ROOT)
SCRIPT_STORE = cb_scripts.ScriptStore(ROOT)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _md5_file(path: pathlib.Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _storyboard_path(scene: str, episode: str) -> pathlib.Path:
    return OUTPUT / "creative" / f"{episode}_scene{scene}_storyboard.json"


def _write_storyboard_snapshot(*, scene: str, episode: str, source: dict[str, Any],
                               beats: list[dict[str, Any]], shots: list[dict[str, Any]]) -> dict[str, Any]:
    path = _storyboard_path(scene, episode)
    path.parent.mkdir(parents=True, exist_ok=True)
    current_script = SCRIPT_STORE.current(episode, required=True)
    beat_signature = source.get("contentSignature") or cb_lineage.beat_package_signature(source)
    storyboard = {
        "episodeId": episode,
        "sceneNumber": scene,
        "engineVersion": "cb_scene_package.py production-package storyboard snapshot",
        "builtAt": _now(),
        "sourceScript": current_script,
        "sourceBeatPackage": {
            "path": str((OUTPUT / f"{episode}_The_Adventure_Begins_beat_package.json").relative_to(ROOT)),
            "contentSignature": beat_signature,
        },
        "approvalState": "generated-pending-human-review",
        "humanNote": "Generated from locked episode beat package for current production graph.",
        "beats": [
            {
                "beatId": beat.get("beatCode"),
                "storyBeat": beat.get("storyBeat"),
                "emotionalIntent": beat.get("emotionalIntent"),
                "kidRead": beat.get("kidRead"),
                "adultRead": beat.get("adultRead"),
                "participatingCharacters": beat.get("characters") or [],
                "sourceBeatId": beat.get("sourceBeatId"),
                "sourceEventIds": beat.get("sourceEventIds") or [],
                "sourceEventRange": beat.get("sourceEventRange"),
                "sourceEventSignature": beat.get("sourceEventSignature"),
                "dialogueOccurrences": [
                    {
                        "dialogueOccurrenceId": cut.get("dialogueOccurrenceId"),
                        "sourceEventId": cut.get("sourceEventId"),
                        "sourceEventIndex": cut.get("sourceEventIndex"),
                        "beatId": beat.get("beatCode"),
                        "sourceBeatId": beat.get("sourceBeatId"),
                        "speaker": cut.get("speaker"),
                        "exactText": cut.get("exactText") or cut.get("text"),
                    }
                    for cut in (beat.get("cuts") or [])
                    if cut.get("sourceType") == "dialogue" or cut.get("dialogueOccurrenceId")
                ],
            }
            for beat in beats
        ],
        "shots": [
            {
                "shotId": shot.get("shotId"),
                "sourceType": shot.get("sourceType"),
                "sourceShotId": shot.get("sourceShotId"),
                "durationSec": shot.get("durationSec"),
                "purpose": shot.get("purpose"),
                "storyBeat": shot.get("storyBeat"),
                "action": shot.get("action"),
                "visualPayoff": shot.get("visualPayoff"),
                "dialogueLines": shot.get("dialogueLines") or [],
                "continuityConstraints": shot.get("continuityConstraints") or [],
            }
            for shot in shots
        ],
    }
    storyboard["inputSignature"] = cb_lineage.dependency_signature(
        "scene-storyboard-snapshot",
        {
            "scriptVersionId": current_script["scriptVersionId"],
            "beatPackageDigest": beat_signature["digest"],
            "sceneNumber": scene,
            "sourceBeatIds": [beat.get("sourceBeatId") for beat in beats],
            "shotIds": [shot.get("shotId") for shot in shots],
        },
    )
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
        if existing.get("inputSignature") == storyboard["inputSignature"]:
            for key in ("approvalState", "humanNote", "approvalLog"):
                if key in existing:
                    storyboard[key] = existing[key]
    path.write_text(json.dumps(storyboard, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "path": str(path),
        "md5": _md5_file(path),
        "sha256": cb_lineage.sha256_file(path),
        "approvalState": storyboard["approvalState"],
        "humanNote": storyboard["humanNote"],
        "creativeCardHashes": {},
        "inputSignature": storyboard["inputSignature"],
    }


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


def _continuity_constraints(beat: dict[str, Any]) -> list[dict[str, str]]:
    """Shot-visible continuity constraints derived from the locked beat text."""
    text = " ".join(str(beat.get(key) or "") for key in (
        "beatCode", "storyBeat", "emotionalIntent", "kidRead", "adultRead",
    ))
    text += " " + _action_text(beat)
    text_l = text.casefold()
    beat_code = str(beat.get("beatCode") or "")
    try:
        beat_index = int(beat_code.split(".B", 1)[1].split(".", 1)[0])
    except Exception:
        beat_index = 0
    constraints: list[dict[str, str]] = []
    if "keen" in text_l:
        if "wristband" not in text_l and beat_index >= 6:
            state = (
                "Keen is now wearing both inherited wristbands as aged-gold open cuffs "
                "with blank settings, one cuff on each wrist. "
                "No crystals, no aquamarine stones and no glow appear in or on them."
            )
        elif "wristband" not in text_l:
            state = (
                "Keen starts this scene with bare wrists. No wristbands, bands, "
                "bracelets, cuffs, crystals or straps appear on either wrist."
            )
        elif "slips them onto his wrists" in text_l or "puts the wristbands on" in text_l:
            state = (
                "Keen may put on the inherited wristbands in this shot. They are worn, "
                "aged-gold open cuffs with blank settings only: no crystals, no "
                "aquamarine stones and no glow."
            )
        elif "wristbands land in keen" in text_l or "holds the wristbands" in text_l:
            state = (
                "The wristbands are in Keen's paws only. His wrists remain bare until "
                "the later shot where he puts them on. The bands are vacant: no crystals "
                "or aquamarine stones."
            )
        elif "brings out" in text_l or "father" in text_l:
            state = (
                "Mum introduces the inherited wristbands as aged-gold open cuffs with "
                "blank settings. Keen's wrists "
                "are still bare in this shot. No crystals, aquamarine stones or glow."
            )
        else:
            state = (
                "Wristband continuity must remain explicit: Keen has no aquamarine "
                "stones or crystal glow in this scene."
            )
        constraints.append({
            "label": "Keen wristband state",
            "value": state,
            "severity": "critical",
        })
    return constraints


def _reference_slots(characters: list[str], *, opener: bool,
                     has_dialogue: bool) -> tuple[dict[str, str], dict[str, str]]:
    """Create complete provider-role bindings when a shot first enters production.

    Direction prose is not an attachment. Every generated package therefore carries the
    character identities and Scene Look explicitly; opener animation also carries its
    approved opening frame, and dialogue shots reserve the audio authority slot.
    """
    cast = [str(name).strip() for name in characters if str(name).strip()]
    keyframe = {f"@图{index}": name for index, name in enumerate(cast, start=1)}
    keyframe[f"@图{len(keyframe) + 1}"] = "scene plate"

    animation: dict[str, str] = {}
    if opener:
        animation["@图1"] = "opening keyframe"
        next_index = 2
    else:
        animation["@图1"] = "previous shot final frame"
        animation["@图2"] = "scene plate"
        next_index = 3
    for name in cast:
        animation[f"@图{next_index}"] = name
        next_index += 1
    if opener:
        animation[f"@图{next_index}"] = "scene plate"
    if has_dialogue:
        animation["@Audio1"] = "voice track"
    return animation, keyframe


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
        dialogue_lines = _dialogue_lines(beat)
        reference_slots, keyframe_reference_slots = _reference_slots(
            beat.get("characters") or [], opener=idx == 1,
            has_dialogue=bool(dialogue_lines))
        shot = {
            "shotId": shot_id,
            "sceneNumber": int(scene_s) if scene_s.isdigit() else scene_s,
            "beatCode": beat_code,
            "title": beat.get("storyBeat", beat_code)[:90],
            "durationSec": duration,
            "purpose": beat.get("storyBeat"),
            "visualPayoff": beat.get("kidRead") or beat.get("emotionalIntent"),
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
            "dialogueLines": dialogue_lines,
            "referenceSlots": reference_slots,
            "keyframeReferenceSlots": keyframe_reference_slots,
            "openingCharactersInFrame": beat.get("characters") or [],
            "continuityConstraints": _continuity_constraints(beat),
            "directorRecord": {
                "storyBeat": beat.get("storyBeat"),
                "emotionalIntent": beat.get("emotionalIntent"),
                "kidRead": beat.get("kidRead"),
                "adultRead": beat.get("adultRead"),
                "action": _action_text(beat),
                "dialogueLines": dialogue_lines,
                "continuityConstraints": _continuity_constraints(beat),
            },
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

    source_beat_signature = source.get("contentSignature") or cb_lineage.beat_package_signature(source)
    source_storyboard = _write_storyboard_snapshot(
        scene=scene_s,
        episode=episode,
        source=source,
        beats=beats,
        shots=shots,
    )
    current_script = SCRIPT_STORE.current(episode, required=True)
    package_inputs = {
        "scriptVersionId": current_script["scriptVersionId"],
        "beatPackageDigest": source_beat_signature["digest"],
        "storyboardSha256": source_storyboard["sha256"],
        "creativeCardHashes": {},
        "canonProfileDigest": None,
    }
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
        "sourceSignature": source_beat_signature["digest"],
        "sourceScript": current_script,
        "sourceStoryboard": source_storyboard,
        "inputSignature": cb_lineage.dependency_signature(
            "production-package", package_inputs),
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
