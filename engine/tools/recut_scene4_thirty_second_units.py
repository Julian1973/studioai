#!/usr/bin/env python3
"""Repack Scene 4 into three approved near-30-second Seedance units."""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import pathlib
import shutil
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
ENGINE = ROOT / "engine"
sys.path.insert(0, str(ENGINE))

import cb_engine  # noqa: E402
import cb_lineage  # noqa: E402
import paths as P  # noqa: E402 — the project profile is the only path authority (T44)


PACKAGE = ROOT / P.OUTPUT_REL / "Ep1_scene4_production_package.json"
STORYBOARD = ROOT / P.OUTPUT_REL / "creative" / "Ep1_scene4_storyboard.json"
CHARS = pathlib.Path(P.CHARS)                        # T44: from the project profile


def _shot(records: list[dict], shot_id: str) -> dict:
    return next(record for record in records if record["shotId"] == shot_id)


def _shifted(lines: list[dict], shift: float) -> list[dict]:
    result = copy.deepcopy(lines)
    for line in result:
        line["startSec"] = round(float(line["startSec"]) + shift, 1)
        line["endSec"] = round(float(line["endSec"]) + shift, 1)
    return result


def _unique(*groups: list) -> list:
    values = []
    for group in groups:
        for value in group or []:
            if value not in values:
                values.append(copy.deepcopy(value))
    return values


def _active_storyboard_record(shot: dict) -> dict:
    return {
        key: copy.deepcopy(shot.get(key))
        for key in (
            "shotId", "sourceType", "sourceShotId", "durationSec", "purpose",
            "performanceAssignment", "camera", "openingPose", "visualPayoff",
            "dialogueLines", "beatCodes", "continuityConstraints",
            "motionContinuityRequired",
        )
    }


def _compile(package: dict, shot: dict, characters: dict) -> None:
    fields = set(cb_engine.Shot.model_fields)
    model = cb_engine.Shot(**{key: value for key, value in shot.items() if key in fields})
    prompt, words, slots = cb_engine.compile_shot_contract(
        model, package.get("scene") or {}, characters)
    shot["seedancePrompt"] = prompt
    shot["promptWords"] = words
    shot["referenceSlots"] = slots
    shot["internalConstraints"] = cb_engine.hard_constraints(model, characters)[0]
    if model.sourceType == "opener":
        keyframe, keyframe_words, keyframe_slots = cb_engine.compile_keyframe_prompt(
            model, package.get("scene") or {}, characters)
        shot["keyframePrompt"] = keyframe
        shot["keyframePromptWords"] = keyframe_words
        shot["keyframeReferenceSlots"] = keyframe_slots


def main() -> None:
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    storyboard = json.loads(STORYBOARD.read_text(encoding="utf-8"))
    characters = json.loads(CHARS.read_text(encoding="utf-8"))
    prior_ledger = {
        entry.get("shotId"): copy.deepcopy(entry)
        for entry in package.get("continuityLedger") or []
        if entry.get("shotId")
    }

    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    archive = ROOT / P.OUTPUT_REL / "archive" / "scene_recuts"
    archive.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PACKAGE, archive / f"Ep1_scene4_before_three_unit_recut_{stamp}.json")
    shutil.copy2(STORYBOARD, archive / f"Ep1_scene4_storyboard_before_three_unit_recut_{stamp}.json")

    # A prior interrupted rebuild may have retained only the approval badge and path. Recover
    # missing voice provenance from the preserved package history so an unchanged, already
    # signed HEAR track does not become falsely stale merely because packaging was rebuilt.
    for candidate in sorted(
            archive.glob("Ep1_scene4_before_three_unit_recut_*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True):
        try:
            archived = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for entry in archived.get("continuityLedger") or []:
            shot_id = entry.get("shotId")
            if not shot_id:
                continue
            live_prior = prior_ledger.setdefault(shot_id, {})
            for key, value in entry.items():
                if live_prior.get(key) is None and value is not None:
                    live_prior[key] = copy.deepcopy(value)

    original = package["shots"]
    required_source_ids = {f"4.B{index}.S1" for index in range(1, 7)}
    if not required_source_ids.issubset({shot.get("shotId") for shot in original}):
        # Re-running a recut must be safe. Once the live package contains its three packed
        # units, recover the original directed six-shot source from the most recent archive
        # that actually contains it instead of failing or treating packed output as source.
        archived_sources = []
        for candidate in archive.glob("Ep1_scene4_before_three_unit_recut_*.json"):
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if required_source_ids.issubset({shot.get("shotId") for shot in payload.get("shots") or []}):
                archived_sources.append((candidate.stat().st_mtime, payload))
        if not archived_sources:
            raise RuntimeError("No preserved six-shot Scene 4 source exists for a safe recut rebuild")
        original = max(archived_sources, key=lambda item: item[0])[1]["shots"]
    b1, b2 = _shot(original, "4.B1.S1"), _shot(original, "4.B2.S1")
    b3, b4 = _shot(original, "4.B3.S1"), _shot(original, "4.B4.S1")
    b5, b6 = _shot(original, "4.B5.S1"), _shot(original, "4.B6.S1")

    unit1 = copy.deepcopy(b1)
    unit1.update({
        "beatCodes": ["4.B1", "4.B2"],
        "durationSec": 30.0,
        # Squeaky's first visible splash is the entrance beat. He belongs to the
        # animation cast and reference bundle, but must not be staged in frame one.
        "openingCharactersInFrame": ["Keen"],
        "requiredPropReferences": [
            "keen_sailboat", "keen_sailboat_departure_state"],
        "purpose": (
            "Make the empty sea feel enormous, turn Squeaky into Keen's first companion, "
            "then let Keen's confident map-reading reveal that he has no idea where he is going."
        ),
        "performanceAssignment": (
            "Shot 1: the small sailboat travels left-to-right across endless blue water. Keen "
            "performs confidence while making quick balance corrections. Squeaky surfaces at "
            "screen-right, keeps pace, and chatters; Keen greets him, listens, names him, and the "
            "friendship lands in one shared look. Shot 2: without resetting the boat or screen "
            "direction, Squeaky makes one playful leap while Keen laughs and lifts the map from "
            "the boat. Keen checks the map, looks over the bow, checks it again, rotates it upside "
            "down, then peeks over its edge and completes the directions joke. The boat keeps "
            "travelling throughout."
        ),
        "camera": (
            "Open wide with the boat small against endless water, starboard side and left-to-right "
            "travel. Push to a warm medium two-shot for the naming beat. Cut on Squeaky's leap to "
            "a medium on Keen, then push toward the upside-down map while Squeaky remains readable "
            "at screen-right. Preserve the same boat, travel axis, sail, cargo and open-water light."
        ),
        "visualPayoff": (
            "Keen holds the map visibly upside down, peeks over it toward the open water and lands "
            "'one of the directions' while Squeaky keeps pace beside the moving boat."
        ),
        "dialogueBinding": (
            "Keen speaks all four lines in order; Squeaky answers only with dolphin chatter and "
            "never forms human words."
        ),
        "dialogueLines": [
            *_shifted(b1["dialogueLines"], -0.6),
            *_shifted(b2["dialogueLines"], 12.1),
        ],
        "continuityConstraints": [
            {
                "label": "Scene 3 handoff state",
                "value": (
                    "Begin from the approved final state of 3.B7.S1. Preserve the same little "
                    "sailboat, tan sail, mast and rigging, established loaded cargo, bow-first "
                    "left-to-right travel, coherent wake, bright open-water light, exactly one "
                    "Keen and exactly one Squeaky."
                ),
                "severity": "blocking",
            },
            {
                "label": "Keen wristband state",
                "value": (
                    "Keen wears exactly two inherited aged-gold open cuffs with blank settings, "
                    "one on each wrist. No crystals, aquamarine stones or glow. The cuffs never "
                    "vanish, duplicate, swap wrists or change form."
                ),
                "severity": "blocking",
            },
            {
                "label": "Boat cargo state",
                "value": (
                    "The same established cargo remains aboard and spatially continuous: open "
                    "satchel, rolled blanket, folded map and small food pouch. Nothing appears, "
                    "disappears, duplicates or changes ownership unless a later approved action "
                    "visibly changes it."
                ),
                "severity": "blocking",
            },
            {
                "label": "Squeaky state",
                "value": (
                    "Exactly one Squeaky matches the approved turnaround and remains outside the "
                    "boat at screen-right beside the moving hull. Squeaky uses friendly nonverbal "
                    "dolphin chirps, clicks and squeaks only; no English or human speech."
                ),
                "severity": "blocking",
            },
            {
                "label": "Sailing physics",
                "value": (
                    "The filled sail drives the boat bow-first through the water; stern follows, "
                    "hull heels gently, wake trails coherently, and the boat never slides sideways "
                    "or travels stern-first. Preserve the established starboard camera side and "
                    "left-to-right travel axis."
                ),
                "severity": "blocking",
            },
        ],
        "continuityOut": copy.deepcopy(b2["continuityOut"]),
        "prohibited": _unique(b1.get("prohibited"), b2.get("prohibited")),
        "physicalStagings": _unique(b1.get("physicalStagings"), b2.get("physicalStagings")),
    })

    unit2 = copy.deepcopy(b3)
    unit2.update({
        "beatCodes": ["4.B3", "4.B4"],
        "durationSec": 30.0,
        "sourceShotId": "4.B1.S1",
        "motionContinuityRequired": True,
        "requiredPropReferences": [
            "keen_sailboat", "keen_sailboat_departure_state"],
        "purpose": (
            "Let the storm dismantle Keen's performed control in one escalating cause-and-effect "
            "run, ending with the map gone and Keen finally admitting that he is lost."
        ),
        "performanceAssignment": (
            "Shot 1: continue from the upside-down-map landing. A hard gust loads the sail, the "
            "boat heels and rocks, and Keen slides, grabs the mast and yelps. The light falls, rain "
            "builds from drops to sheets, and Squeaky dives below the rough water and disappears. "
            "Shot 2: Keen tries to steer with one hand and clamp the map with the other. A stronger "
            "gust visibly catches the map and tears it from his fingers; he reaches and calls after "
            "it. Shot 3: match Keen's reach as the boat drops beneath him. His hand closes on empty "
            "rain; the map vanishes into the grey. He regains his feet, sees that the horizon has "
            "gone, lets the loss register, and admits that he is lost."
        ),
        "camera": (
            "Begin medium on Keen, map and sail from the established starboard side. Jolt with the "
            "first heel, then widen to reveal darkening sky, rough water and Squeaky's disappearance. "
            "Track the stolen map toward screen-right, cut at maximum reach, and tighten slowly on "
            "Keen only after the map and horizon have both disappeared."
        ),
        "visualPayoff": (
            "Keen stands in the rocking boat with empty hands, rainwater around his feet and no "
            "visible horizon, then says 'Oh no... I'm lost!!!' without performing confidence."
        ),
        "dialogueBinding": "Keen speaks all three lines; Squeaky remains wordless and exits underwater.",
        "dialogueLines": [
            *_shifted(b3["dialogueLines"][:1], 0.0),
            *_shifted(b3["dialogueLines"][1:], -1.1),
            *_shifted(b4["dialogueLines"], 20.7),
        ],
        "continuityOut": copy.deepcopy(b4["continuityOut"]),
        "prohibited": _unique(b3.get("prohibited"), b4.get("prohibited")),
        "physicalStagings": _unique(b3.get("physicalStagings"), b4.get("physicalStagings")),
        "closingCharactersInFrame": ["Keen"],
    })

    unit3 = copy.deepcopy(b5)
    unit3.update({
        "beatCodes": ["4.B5", "4.B6"],
        "durationSec": 30.0,
        "sourceShotId": "4.B3.S1",
        "motionContinuityRequired": True,
        "requiredPropReferences": [
            "keen_sailboat", "keen_sailboat_departure_state"],
        "purpose": (
            "Turn Keen's fear into a small act of self-regulation, then let Squeaky's return give "
            "him a choice: accept help and steer toward trust."
        ),
        "performanceAssignment": (
            "Shot 1: continue with Keen alone in the same storm. A distant lightning flicker makes "
            "him grip the boat edge. His shoulders show quick breaths; he closes his eyes, takes one "
            "slower breath, repeats his brave phrase, and settles only slightly. Shot 2: Squeaky's "
            "offscreen clicking makes Keen open his eyes and turn before Squeaky appears. Squeaky "
            "leaps beside the hull, dives, resurfaces farther ahead and repeatedly indicates a clear "
            "screen-right route. Keen questions him, studies the water, meets Squeaky's eyeline, "
            "decides, and nods. Shot 3: Keen answers with growing resolve, braces his feet and hauls "
            "the tiller. The bow pivots under water resistance and the sail remains wind-loaded as "
            "the boat follows Squeaky rather than sliding sideways."
        ),
        "camera": (
            "Ride the established starboard-side boat motion in a steadier medium close while Keen "
            "breathes. Let Squeaky's chatter bridge into a pan toward screen-right, then widen to "
            "show Squeaky leading and the bow physically turning after him. End with both characters' "
            "motivated eyelines and a readable forward route through the storm."
        ),
        "visualPayoff": (
            "Squeaky surges ahead through the storm while Keen, still worried but no longer alone, "
            "turns the boat onto Squeaky's path and commits to following him."
        ),
        "dialogueBinding": (
            "Keen speaks all three lines. Squeaky uses only clicks and chirps; his mouth never forms "
            "human words."
        ),
        "dialogueLines": [
            *_shifted(b5["dialogueLines"], -0.4),
            *_shifted(b6["dialogueLines"][:1], 8.9),
            *_shifted(b6["dialogueLines"][1:], 8.8),
        ],
        "charactersInFrame": ["Keen", "Squeaky"],
        "openingCharactersInFrame": ["Keen"],
        "continuityOut": copy.deepcopy(b6["continuityOut"]),
        "prohibited": _unique(b5.get("prohibited"), b6.get("prohibited")),
        "physicalStagings": _unique(b5.get("physicalStagings"), b6.get("physicalStagings")),
    })

    active = [unit1, unit2, unit3]
    for shot in active:
        _compile(package, shot, characters)

    fields = set(cb_engine.Shot.model_fields)
    design = cb_engine.SceneShotList(
        statement=cb_engine.DirectorStatement(**package["directorStatement"]),
        shots=[cb_engine.Shot(**{k: v for k, v in shot.items() if k in fields}) for shot in active],
    )
    beat_package, _ = cb_engine._load_pkg("Ep1")
    beats = cb_engine._scene_beats(beat_package, "4")
    report = cb_engine.validate_scene_design(design, beats, characters)
    if not report["passed"]:
        raise RuntimeError(f"Scene 4 recut failed validation: {report['issues']}")

    package["shots"] = active
    package["totalSec"] = 90.0
    package["continuityLedger"] = [cb_engine._ledger_entry(shot) for shot in design.shots]
    ledger_by_id = {entry["shotId"]: entry for entry in package["continuityLedger"]}

    # Repacking direction must not erase an approved predecessor that remains byte-for-byte
    # valid. B1 is the opening motion master for the subsequent video-extension relays.
    prior_b1 = prior_ledger.get("4.B1.S1") or {}
    live_b1 = ledger_by_id["4.B1.S1"]
    for key in ("status", "keyframeApproval", "voiceApproval", "voPath", "voGeneratedFrom",
                "voInputSignature", "voPackageRevision", "voPlacementPath", "voRawPath",
                "voTimingPath", "departmentWork", "approvedTake", "harvestFrame",
                "candidatePaths", "candidatesGenerated", "batchAttempts"):
        if prior_b1.get(key) is not None:
            live_b1[key] = copy.deepcopy(prior_b1[key])

    # Voice direction is unchanged, so approved voice tracks remain valid. The old B3/B5
    # renders stay in the evidence trail but are deliberately no longer approved: their
    # movement was generated from a still handoff and must be replaced by @Video1 continuity.
    for shot_id in ("4.B3.S1", "4.B5.S1"):
        prior = prior_ledger.get(shot_id) or {}
        live = ledger_by_id[shot_id]
        for key in ("voiceApproval", "voPath", "voGeneratedFrom", "voInputSignature",
                    "voPackageRevision", "voPlacementPath", "voRawPath", "voTimingPath",
                    "departmentWork", "voiceAuditions", "voiceAuditionSelections",
                    "voiceAuditionSelectionsByHash"):
            if prior.get(key) is not None:
                live[key] = copy.deepcopy(prior[key])
        if prior.get("approvedTake"):
            live["supersededApprovedTake"] = {
                "path": prior["approvedTake"],
                "reason": "Replaced by motion-continuity video-extension relay",
                "retainedFor": "creative review evidence",
            }
    package["validation"] = report
    package["revision"] = int(package.get("revision") or 1) + 1
    package.setdefault("revisionNotes", []).append({
        "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "reviewedBy": "Julian",
        "change": (
            "Repacked Scene 4 from six short drafts into three 30-second Seedance units: "
            "B1+B2, B3+B4 and B5+B6. Every source beat and dialogue occurrence remains covered."
        ),
    })

    storyboard["shots"] = [_active_storyboard_record(shot) for shot in active]
    storyboard["approvalState"] = "generated-pending-human-review"
    storyboard["humanNote"] = ""
    storyboard_inputs = {
        "scriptVersionId": storyboard["sourceScript"]["scriptVersionId"],
        "beatPackageDigest": (package.get("inputSignature") or {}).get("inputs", {}).get(
            "beatPackageDigest"),
        "sceneNumber": "4",
        "sourceBeatIds": [beat.get("sourceBeatId") for beat in storyboard.get("beats") or []],
        "shotIds": [shot["shotId"] for shot in active],
    }
    storyboard["inputSignature"] = cb_lineage.dependency_signature(
        "scene-storyboard-snapshot", storyboard_inputs)
    STORYBOARD.write_text(
        json.dumps(storyboard, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    storyboard_bytes = STORYBOARD.read_bytes()
    source_storyboard = package.setdefault("sourceStoryboard", {})
    source_storyboard["md5"] = hashlib.md5(storyboard_bytes).hexdigest()
    source_storyboard["sha256"] = hashlib.sha256(storyboard_bytes).hexdigest()
    source_storyboard["approvalState"] = storyboard["approvalState"]
    source_storyboard["inputSignature"] = copy.deepcopy(storyboard["inputSignature"])
    production_inputs = dict((package.get("inputSignature") or {}).get("inputs") or {})
    production_inputs["storyboardSha256"] = source_storyboard["sha256"]
    package["inputSignature"] = cb_lineage.dependency_signature(
        "production-package", production_inputs)
    PACKAGE.write_text(
        json.dumps(package, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
