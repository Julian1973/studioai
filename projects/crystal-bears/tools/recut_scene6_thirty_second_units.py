#!/usr/bin/env python3
"""Repack Scene 6 into three story-led Seedance production units."""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import pathlib
import shutil
import sys


ROOT = pathlib.Path(__file__).resolve().parents[3]   # projects/<id>/tools/ → repo root
ENGINE = ROOT / "engine"
sys.path.insert(0, str(ENGINE))

import cb_lineage  # noqa: E402
import paths as P  # noqa: E402 — the project profile is the only path authority (T45)


PACKAGE = ROOT / P.OUTPUT_REL / "Ep1_scene6_production_package.json"
STORYBOARD = ROOT / P.OUTPUT_REL / "creative" / "Ep1_scene6_storyboard.json"


def _shot(records: list[dict], shot_id: str) -> dict:
    return next(record for record in records if record["shotId"] == shot_id)


def _unique(*groups: list) -> list:
    values = []
    for group in groups:
        for value in group or []:
            if value not in values:
                values.append(copy.deepcopy(value))
    return values


def _merged_record(first: dict, second: dict, *, story_beat: str,
                   emotional_intent: str, kid_read: str, adult_read: str,
                   action: str) -> dict:
    return {
        "storyBeat": story_beat,
        "emotionalIntent": emotional_intent,
        "kidRead": kid_read,
        "adultRead": adult_read,
        "action": action,
        "dialogueLines": _unique(first.get("dialogueLines"), second.get("dialogueLines")),
        "continuityConstraints": _unique(
            first.get("continuityConstraints"), second.get("continuityConstraints")),
    }


def _merge(first: dict, second: dict, *, duration: int, purpose: str,
           visual_payoff: str, emotional_intent: str, kid_read: str,
           adult_read: str, action: str, camera: str) -> dict:
    unit = copy.deepcopy(first)
    unit.update({
        "beatCode": f"{first['beatCode']}+{second['beatCode']}",
        "sourceBeatIds": [first.get("sourceBeatId"), second.get("sourceBeatId")],
        "sourceEventIds": _unique(first.get("sourceEventIds"), second.get("sourceEventIds")),
        "dialogueOccurrenceIds": _unique(
            first.get("dialogueOccurrenceIds"), second.get("dialogueOccurrenceIds")),
        "durationSec": duration,
        "title": purpose[:90],
        "purpose": purpose,
        "storyBeat": purpose,
        "emotionalIntent": emotional_intent,
        "kidRead": kid_read,
        "adultRead": adult_read,
        "action": action,
        "camera": camera,
        "visualPayoff": visual_payoff,
        "dialogueLines": _unique(first.get("dialogueLines"), second.get("dialogueLines")),
        "continuityConstraints": _unique(
            first.get("continuityConstraints"), second.get("continuityConstraints")),
        "directorRecord": _merged_record(
            first, second, story_beat=purpose, emotional_intent=emotional_intent,
            kid_read=kid_read, adult_read=adult_read, action=action),
    })
    return unit


def _storyboard_record(shot: dict) -> dict:
    return {
        key: copy.deepcopy(shot.get(key))
        for key in (
            "shotId", "sourceType", "sourceShotId", "durationSec", "purpose",
            "storyBeat", "action", "camera", "visualPayoff", "dialogueLines",
            "continuityConstraints", "sourceBeatIds",
        )
    }


def main() -> None:
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    storyboard = json.loads(STORYBOARD.read_text(encoding="utf-8"))
    original = package["shots"]
    if [shot["shotId"] for shot in original] == ["6.B1.S1", "6.B3.S1", "6.B5.S1"]:
        print("Scene 6 is already packed into three production units.")
        return

    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    archive = ROOT / P.OUTPUT_REL / "archive" / "scene_recuts"
    archive.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PACKAGE, archive / f"Ep1_scene6_before_three_unit_recut_{stamp}.json")
    shutil.copy2(STORYBOARD, archive / f"Ep1_scene6_storyboard_before_three_unit_recut_{stamp}.json")

    b1, b2 = _shot(original, "6.B1.S1"), _shot(original, "6.B2.S1")
    b3, b4 = _shot(original, "6.B3.S1"), _shot(original, "6.B4.S1")
    b5 = copy.deepcopy(_shot(original, "6.B5.S1"))

    unit1 = _merge(
        b1, b2, duration=26,
        purpose=(
            "Fuzzby's spectacularly failed arrival briefly releases the tension, then the same "
            "breathless momentum becomes an urgent warning that Zenny alone can complete."),
        emotional_intent=(
            "Let the audience laugh once, then feel the joke turn into care without resetting "
            "the group or losing the storm's pressure."),
        kid_read=(
            "Fuzzby crashes onto the beach, cannot say what is wrong, and Zenny helps him tell "
            "the bears that someone is in trouble."),
        adult_read=(
            "Their comic rhythm becomes functional intimacy: Zenny understands the message "
            "inside Fuzzby's failed delivery."),
        action=(
            f"Shot 1 — comic arrival. {b1['action']} "
            f"Shot 2 — the warning, without resetting the beach geography. {b2['action']}"),
        camera=(
            "Open in the established storm-cove wide with Aida and the gathered bears anchored "
            "on shore. Track Fuzzby's escalating ricochets in one readable lateral action idea. "
            "Cut only after his soggy-heap button to a grounded group composition for the warning; "
            "hold Zenny's stillness against his breathless movement."),
        visual_payoff=(
            "Fuzzby points at Zenny with grateful recognition after she quietly supplies 'In "
            "trouble,' and the whole group finally understands the emergency."),
    )
    # The bears' quiet storm watch is the opening state. Fuzzby bursts into that stillness
    # as the first animated event and Zenny arrives during the warning beat. Keeping both
    # bees out of frame one protects their entrances and distinct identities, while WATCH
    # still receives both turnarounds through the complete animation reference contract.
    unit1["openingCharactersInFrame"] = [
        "Aida", "Amie", "Howey", "Luna", "Misty", "Sunny",
    ]
    unit1["keyframeReferenceSlots"] = {
        "@图1": "Aida",
        "@图2": "Amie",
        "@图3": "Howey",
        "@图4": "Luna",
        "@图5": "Misty",
        "@图6": "Sunny",
        "@图7": "scene plate",
    }

    unit2 = _merge(
        b3, b4, duration=28,
        purpose=(
            "Aida locates Keen's tiny boat through the rain, contains the group's fear, and turns "
            "that shared concern into the disciplined communal Crystal Call."),
        emotional_intent=(
            "Move continuously from frightening distance to grounded certainty and then collective "
            "hope; the magic is an act of care, not spectacle for its own sake."),
        kid_read=(
            "Aida spots Keen's boat in the storm and the Crystal Bears join their powers to help him."),
        adult_read=(
            "Aida gives communal fear a focus, then turns helpless witnessing into coordinated action."),
        action=(
            f"Shot 1 — locate the danger. {b3['action']} "
            f"Shot 2 — answer together, continuing from Aida's turn. {b4['action']}"),
        camera=(
            "Begin behind and beside Aida at the waterline so her eyeline leads to the same tiny "
            "boat beyond the breakers. Let the lens find the boat through rain, then return with "
            "her turn to the gathered bears. Move into a calm, inclusive arc as each crystal joins; "
            "do not fragment the call into disconnected portraits."),
        visual_payoff=(
            "Every distinct crystal contributes one readable pulse until the gathered bears hold "
            "a single combined light, ready to release across the sea."),
    )
    unit2["sourceType"] = "relay"
    unit2["sourceShotId"] = unit1["shotId"]

    b5["sourceType"] = "relay"
    b5["sourceShotId"] = unit2["shotId"]
    b5["durationSec"] = 6
    b5["camera"] = (
        "Hold the gathered bears and the origin of the combined light long enough to read its "
        "cause, then travel with the beacon across the storm-dark sea toward the tiny boat. End "
        "on hope reaching into distance, not on rescue completed.")

    active = [unit1, unit2, b5]
    package["shots"] = active
    package["continuityLedger"] = [{
        "shotId": shot["shotId"],
        "status": "designed",
        "sourceBeatId": shot.get("sourceBeatId"),
        "sourceBeatIds": shot.get("sourceBeatIds") or [shot.get("sourceBeatId")],
        "sourceType": shot["sourceType"],
        "sourceShotId": shot.get("sourceShotId"),
        "keyframeApproval": None,
        "voiceApproval": None,
        "approvedTake": None,
        "harvestFrame": None,
        "candidatePaths": None,
    } for shot in active]
    package["revision"] = int(package.get("revision") or 1) + 1
    package.setdefault("revisionNotes", []).append({
        "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "reviewedBy": "Julian and Codex",
        "change": (
            "Repacked Scene 6 into three story-led Seedance units: B1+B2 (26s), "
            "B3+B4 (28s), and the protected B5 beacon payoff (6s)."),
    })

    storyboard["shots"] = [_storyboard_record(shot) for shot in active]
    storyboard["approvalState"] = "generated-pending-human-review"
    storyboard["humanNote"] = ""
    storyboard_inputs = {
        "scriptVersionId": storyboard["sourceScript"]["scriptVersionId"],
        "beatPackageDigest": (package.get("inputSignature") or {}).get("inputs", {}).get(
            "beatPackageDigest"),
        "sceneNumber": "6",
        "sourceBeatIds": [beat.get("sourceBeatId") for beat in storyboard.get("beats") or []],
        "shotIds": [shot["shotId"] for shot in active],
    }
    storyboard["inputSignature"] = cb_lineage.dependency_signature(
        "scene-storyboard-snapshot", storyboard_inputs)
    STORYBOARD.write_text(
        json.dumps(storyboard, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    source_storyboard = package.setdefault("sourceStoryboard", {})
    storyboard_bytes = STORYBOARD.read_bytes()
    source_storyboard["md5"] = hashlib.md5(storyboard_bytes).hexdigest()
    source_storyboard["sha256"] = hashlib.sha256(storyboard_bytes).hexdigest()
    source_storyboard["approvalState"] = storyboard["approvalState"]
    source_storyboard["inputSignature"] = copy.deepcopy(storyboard["inputSignature"])
    production_inputs = dict((package.get("inputSignature") or {}).get("inputs") or {})
    production_inputs["storyboardSha256"] = source_storyboard["sha256"]
    package["inputSignature"] = cb_lineage.dependency_signature(
        "production-package", production_inputs)
    PACKAGE.write_text(
        json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Scene 6 repacked: 6.B1.S1=26s, 6.B3.S1=28s, 6.B5.S1=6s")


if __name__ == "__main__":
    main()
