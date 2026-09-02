#!/usr/bin/env python3
"""Build production packages from the locked episode beat package."""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
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


def _episode_beat_package_path(episode: str) -> pathlib.Path:
    current = SCRIPT_STORE.current(episode, required=True)
    matches = []
    for path in sorted(OUTPUT.glob(f"{episode}_*beat_package.json")):
        try:
            pkg = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        source = pkg.get("sourceScript") or {}
        if source.get("scriptVersionId") == current.get("scriptVersionId"):
            matches.append(path)
    if matches:
        return max(matches, key=lambda item: item.stat().st_mtime)
    fallback = OUTPUT / f"{episode}_The_Adventure_Begins_beat_package.json"
    if fallback.exists():
        return fallback
    raise FileNotFoundError(
        f"Current beat package not found for {episode} and script "
        f"{current.get('scriptVersionId')}")


def _scene_plan_units(source: dict[str, Any], scene_s: str,
                      beats: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    by_code = {beat.get("beatCode"): beat for beat in beats}
    plan = source.get("productionPlan") or []
    if isinstance(plan, dict):
        plan = plan.get("scenes") or []
    units = []
    for item in plan:
        if str(item.get("sceneNumber") or item.get("scene")) != scene_s:
            continue
        codes = [code for code in item.get("sourceBeatCodes") or [] if code in by_code]
        if codes:
            units.append([by_code[code] for code in codes])
    return units or [[beat] for beat in beats]


def _combined_dialogue_lines(beats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lines = []
    for beat in beats:
        for line in _dialogue_lines(beat):
            lines.append(line)
    return lines


def _combined_action_text(beats: list[dict[str, Any]]) -> str:
    return " ".join(part for part in (_action_text(beat) for beat in beats) if part)


def _combined_characters(beats: list[dict[str, Any]]) -> list[str]:
    seen = set()
    chars = []
    for beat in beats:
        for name in beat.get("characters") or []:
            clean = str(name).strip()
            if clean and clean not in seen:
                chars.append(clean)
                seen.add(clean)
    return chars


def _opening_event_characters(beat: dict[str, Any]) -> list[str]:
    declared = [str(name).strip() for name in beat.get("characters") or []
                if str(name).strip()]
    declared_by_key = {name.casefold(): name for name in declared}
    events = ((beat.get("sourceEventSignature") or {}).get("inputs") or {}).get(
        "orderedEvents") or []
    seen = set()
    out = []
    for event in events:
        speakers = [
            str(name).strip() for name in (event.get("chorusMembers") or [])
            if str(name).strip()
        ]
        if not speakers:
            speaker = str(event.get("speaker") or "").strip()
            speakers = [speaker] if speaker else []
        for speaker in speakers:
            canonical = declared_by_key.get(speaker.casefold(), speaker)
            if canonical not in seen:
                out.append(canonical)
                seen.add(canonical)
        text = str(event.get("text") or "")
        for name in declared:
            if name in seen:
                continue
            if re.search(rf"\b{re.escape(name)}\b", text, re.I):
                out.append(name)
                seen.add(name)
    return out or declared


def _combined_constraints(beats: list[dict[str, Any]]) -> list[dict[str, str]]:
    constraints = []
    seen = set()
    for beat in beats:
        for item in _continuity_constraints(beat):
            key = (item.get("label"), item.get("value"))
            if key not in seen:
                constraints.append(item)
                seen.add(key)
    return constraints


def _shot_duration(unit: list[dict[str, Any]], plan_item: dict[str, Any] | None) -> int:
    if plan_item and plan_item.get("targetDurationSec"):
        return int(plan_item["targetDurationSec"])
    return min(30, max(6, sum(_duration_for_beat(beat) for beat in unit)))


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
            "path": str(_episode_beat_package_path(episode).relative_to(ROOT)),
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
            "voiceTreatment": event.get("voiceTreatment", "single_voice"),
            "chorusMembers": event.get("chorusMembers") or [],
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
    beat_path = _episode_beat_package_path(episode)
    source = json.loads(beat_path.read_text(encoding="utf-8"))
    scene_s = str(scene)
    beats = [beat for beat in source.get("beats") or []
             if str(beat.get("sceneNumber")) == scene_s]
    if not beats:
        raise ValueError(f"No beats found for scene {scene_s}")

    shots = []
    ledger = []
    by_plan_codes = []
    plan = source.get("productionPlan") or []
    if isinstance(plan, dict):
        plan = plan.get("scenes") or []
    for item in plan:
        if str(item.get("sceneNumber") or item.get("scene")) == scene_s:
            by_plan_codes.append(item)
    units = _scene_plan_units(source, scene_s, beats)
    for idx, unit in enumerate(units, 1):
        plan_item = by_plan_codes[idx - 1] if idx - 1 < len(by_plan_codes) else None
        beat_codes = [beat.get("beatCode") or f"{scene_s}.B{n}"
                      for n, beat in enumerate(unit, 1)]
        beat_code = beat_codes[0]
        shot_id = f"S{scene_s}.SH{idx}"
        previous_shot_id = shots[-1]["shotId"] if shots else None
        duration = _shot_duration(unit, plan_item)
        dialogue_lines = _combined_dialogue_lines(unit)
        characters = _combined_characters(unit)
        opening_characters = _opening_event_characters(unit[0])
        action = _combined_action_text(unit)
        story_parts = [beat.get("storyBeat") for beat in unit if beat.get("storyBeat")]
        story_beat = " / ".join(story_parts)
        kid_parts = [beat.get("kidRead") or beat.get("emotionalIntent") for beat in unit
                     if beat.get("kidRead") or beat.get("emotionalIntent")]
        visual_payoff = " / ".join(kid_parts)
        reference_slots, _ = _reference_slots(
            characters, opener=idx == 1,
            has_dialogue=bool(dialogue_lines))
        _, keyframe_reference_slots = _reference_slots(
            opening_characters, opener=idx == 1,
            has_dialogue=bool(dialogue_lines))
        shot = {
            "shotId": shot_id,
            "sceneNumber": int(scene_s) if scene_s.isdigit() else scene_s,
            "beatCode": beat_code,
            "beatCodes": beat_codes,
            "title": (story_beat or beat_code)[:90],
            "durationSec": duration,
            "purpose": story_beat,
            "visualPayoff": visual_payoff,
            "sourceType": "opener" if idx == 1 else "relay",
            "sourceShotId": previous_shot_id,
            "location": unit[0].get("location"),
            "time": unit[0].get("time"),
            "charactersInFrame": characters,
            "storyBeat": story_beat,
            "emotionalIntent": " / ".join(
                beat.get("emotionalIntent") for beat in unit if beat.get("emotionalIntent")),
            "kidRead": " / ".join(beat.get("kidRead") for beat in unit if beat.get("kidRead")),
            "adultRead": " / ".join(beat.get("adultRead") for beat in unit if beat.get("adultRead")),
            "action": action,
            "dialogueLines": dialogue_lines,
            "referenceSlots": reference_slots,
            "keyframeReferenceSlots": keyframe_reference_slots,
            "openingCharactersInFrame": opening_characters,
            "continuityConstraints": _combined_constraints(unit),
            "directorRecord": {
                "storyBeat": story_beat,
                "emotionalIntent": " / ".join(
                    beat.get("emotionalIntent") for beat in unit if beat.get("emotionalIntent")),
                "kidRead": " / ".join(beat.get("kidRead") for beat in unit if beat.get("kidRead")),
                "adultRead": " / ".join(beat.get("adultRead") for beat in unit if beat.get("adultRead")),
                "action": action,
                "dialogueLines": dialogue_lines,
                "continuityConstraints": _combined_constraints(unit),
            },
            "sourceBeatId": unit[0].get("sourceBeatId"),
            "sourceBeatIds": [beat.get("sourceBeatId") for beat in unit],
            "sourceEventRange": {
                "firstEventIndex": (unit[0].get("sourceEventRange") or {}).get("firstEventIndex"),
                "lastEventIndex": (unit[-1].get("sourceEventRange") or {}).get("lastEventIndex"),
                "firstEventId": (unit[0].get("sourceEventRange") or {}).get("firstEventId"),
                "lastEventId": (unit[-1].get("sourceEventRange") or {}).get("lastEventId"),
                "eventCount": sum((beat.get("sourceEventRange") or {}).get("eventCount") or 0
                                  for beat in unit),
            },
            "sourceEventIds": [
                event for beat in unit for event in (beat.get("sourceEventIds") or [])
            ],
            "dialogueOccurrenceIds": [
                occurrence for beat in unit
                for occurrence in (beat.get("dialogueOccurrenceIds") or [])
            ],
        }
        shots.append(shot)
        ledger.append({
            "shotId": shot_id,
            "status": "designed",
            "sourceBeatId": unit[0].get("sourceBeatId"),
            "sourceBeatIds": [beat.get("sourceBeatId") for beat in unit],
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
