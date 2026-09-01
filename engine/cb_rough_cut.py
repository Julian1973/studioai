#!/usr/bin/env python3
"""Persistent, zero-spend rough-cut edit decisions.

The episode sequence remains available to the legacy Director surface. Scene cuts
power the production Director's Seat: every approved WATCH take is placed on the
timeline by default, while reorder and trim decisions are saved independently of
the immutable production package. Every entry is pinned to the approved take hash.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import pathlib
import re
import tempfile
import threading
import paths as P  # the project profile is the only path authority (T44/T45)


ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / P.OUTPUT_REL
_TOKEN = re.compile(r"^[A-Za-z0-9._-]+$")
_LOCK = threading.Lock()


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_token(value, label):
    value = str(value or "").strip()
    if not value or not _TOKEN.fullmatch(value):
        raise ValueError(f"valid {label} required")
    return value


def _output_root(out=None):
    return pathlib.Path(out) if out is not None else OUT


def _draft_path(episode, out=None):
    return _output_root(out) / f"{episode}_rough_cut_draft.json"


def _read_draft(episode, out=None):
    path = _draft_path(episode, out)
    if not path.exists():
        return {"schemaVersion": 2, "episode": episode, "updatedAt": None,
                "sequence": [], "sceneCuts": {}}
    data = json.loads(path.read_text())
    if data.get("episode") != episode or not isinstance(data.get("sequence"), list):
        raise ValueError("rough-cut draft is malformed")
    if not isinstance(data.get("sceneCuts", {}), dict):
        raise ValueError("rough-cut scene cuts are malformed")
    data.setdefault("sceneCuts", {})
    return data


def _write_draft(episode, draft, out=None):
    output = _output_root(out)
    output.mkdir(parents=True, exist_ok=True)
    draft["schemaVersion"] = 2
    draft["episode"] = episode
    draft["updatedAt"] = _now()
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{episode}_rough_cut_", suffix=".json", dir=output)
    try:
        with os.fdopen(fd, "w") as target:
            json.dump(draft, target, indent=2, ensure_ascii=False)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temp_name, _draft_path(episode, output))
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _approved_shots(episode, out=None):
    approved = {}
    for path in _output_root(out).glob(f"{episode}_scene*_production_package.json"):
        try:
            package = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if str(package.get("episode") or episode) != episode:
            continue
        ledgers = {entry.get("shotId"): entry for entry in package.get("continuityLedger") or []}
        scene = str(package.get("sceneNumber") or "")
        for order, shot in enumerate(package.get("shots") or [], start=1):
            shot_id = str(shot.get("shotId") or "")
            ledger = ledgers.get(shot_id) or {}
            take = ledger.get("approvedTake")
            if ledger.get("status") != "approved" or not take or not os.path.isfile(take):
                continue
            approved[shot_id] = {
                "shotId": shot_id,
                "scene": scene,
                "durationSec": shot.get("durationSec"),
                "purpose": shot.get("purpose") or "",
                "approvedTake": str(pathlib.Path(take).resolve()),
                "sourceHash": _sha256(take),
                "dialogueLines": list(shot.get("dialogueLines") or []),
                "storyOrder": order,
            }
    return approved


def _scene_shot_ids(episode, scene, out=None):
    """Return the live production units for one scene in story order."""
    retired = {"superseded", "archived", "inactive"}
    for path in _output_root(out).glob(f"{episode}_scene*_production_package.json"):
        try:
            package = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if (str(package.get("episode") or episode) != episode or
                str(package.get("sceneNumber") or "") != scene):
            continue
        return [
            str(shot.get("shotId"))
            for shot in package.get("shots") or []
            if shot.get("shotId") and
            str(shot.get("status") or "").strip().lower() not in retired and
            not str(shot.get("status") or "").strip().lower().startswith("skipped-") and
            not shot.get("superseded")
        ]
    return []


def _source_duration(source):
    try:
        duration = float(source.get("durationSec") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if duration <= 0:
        raise ValueError(f"{source.get('shotId')} has no readable approved duration")
    return duration


def _default_scene_sequence(approved, scene):
    rows = [item for item in approved.values() if str(item.get("scene")) == scene]
    rows.sort(key=lambda item: (int(item.get("storyOrder") or 0), item.get("shotId") or ""))
    return [{
        "shotId": item["shotId"], "scene": scene,
        "durationSec": _source_duration(item), "inSec": 0.0,
        "outSec": _source_duration(item), "manualTrim": False,
        "sourceHash": item["sourceHash"], "addedAt": _now(),
    } for item in rows]


def _project_scene_entry(entry, approved, scene, order):
    shot_id = str(entry.get("shotId") or "")
    source = approved.get(shot_id)
    is_current = bool(
        source and str(source.get("scene")) == scene and
        source.get("sourceHash") == entry.get("sourceHash"))
    try:
        in_sec = round(float(entry.get("inSec") or 0), 3)
        out_sec = round(float(entry.get("outSec") or entry.get("durationSec") or 0), 3)
    except (TypeError, ValueError):
        in_sec, out_sec = 0.0, 0.0
        is_current = False
    return {
        **entry, "order": order, "inSec": in_sec, "outSec": out_sec,
        "editDurationSec": round(max(0.0, out_sec - in_sec), 3),
        "current": is_current,
        "reason": None if is_current else (
            "approved take changed" if source else "approved take is no longer available"),
        "approvedTake": source["approvedTake"] if is_current else None,
        "purpose": (source or {}).get("purpose") or "",
        "dialogueLines": list((source or {}).get("dialogueLines") or []),
    }


def scene_status(episode="Ep1", scene="1", out=None):
    """Return one scene's current cut, auto-seeded from approved WATCH takes."""
    episode = _validate_token(episode, "episode")
    scene = _validate_token(scene, "scene")
    with _LOCK:
        draft = _read_draft(episode, out)
        approved = _approved_shots(episode, out)
        saved = (draft.get("sceneCuts") or {}).get(scene)
        raw_sequence = list((saved or {}).get("sequence") or [])
        if not saved:
            raw_sequence = _default_scene_sequence(approved, scene)
        sequence = [
            _project_scene_entry(entry, approved, scene, index)
            for index, entry in enumerate(raw_sequence, start=1)
        ]
        selected = {entry.get("shotId") for entry in sequence}
        available = [
            {**item, "inCut": shot_id in selected}
            for shot_id, item in approved.items() if str(item.get("scene")) == scene
        ]
        expected_ids = _scene_shot_ids(episode, scene, out)
        approved_ids = {
            shot_id for shot_id, item in approved.items()
            if str(item.get("scene")) == scene
        }
        missing_ids = [shot_id for shot_id in expected_ids if shot_id not in approved_ids]
        all_shots_approved = bool(expected_ids) and not missing_ids
        all_current = bool(sequence) and all(entry["current"] for entry in sequence)
        confirmed = bool((saved or {}).get("confirmed"))
        return {
            "schemaVersion": 2, "episode": episode, "scene": scene,
            "updatedAt": (saved or {}).get("updatedAt") or draft.get("updatedAt"),
            "saved": bool(saved), "confirmed": confirmed,
            "confirmedCurrent": bool(confirmed and all_current and all_shots_approved),
            "sequence": sequence, "available": available,
            "expectedCount": len(expected_ids), "approvedCount": len(approved_ids),
            "missingShotIds": missing_ids, "allShotsApproved": all_shots_approved,
            "readyCount": sum(1 for entry in sequence if entry["current"]),
            "staleCount": sum(1 for entry in sequence if not entry["current"]),
            "totalDurationSec": round(sum(entry["editDurationSec"] for entry in sequence), 3),
        }


def save_scene_cut(episode, scene, sequence, confirm=False, out=None):
    """Validate and atomically save one scene edit decision list.

    Manual trims may not clip approved dialogue. Dialogue edits remain a HEAR/WATCH
    decision; this editor only changes picture order and safe handles.
    """
    episode = _validate_token(episode, "episode")
    scene = _validate_token(scene, "scene")
    if not isinstance(sequence, list) or not sequence:
        raise ValueError("a scene cut needs at least one approved shot")
    with _LOCK:
        draft = _read_draft(episode, out)
        approved = _approved_shots(episode, out)
        if confirm:
            expected_ids = _scene_shot_ids(episode, scene, out)
            approved_ids = {
                shot_id for shot_id, item in approved.items()
                if str(item.get("scene")) == scene
            }
            missing_ids = [shot_id for shot_id in expected_ids if shot_id not in approved_ids]
            if missing_ids:
                raise ValueError(
                    "finish WATCH approval before locking the scene cut: " +
                    ", ".join(missing_ids))
        normalized, seen = [], set()
        for item in sequence:
            if not isinstance(item, dict):
                raise ValueError("every scene-cut entry must be an object")
            shot_id = _validate_token(item.get("shotId"), "shotId")
            source = approved.get(shot_id)
            if not source or str(source.get("scene")) != scene:
                raise ValueError(f"{shot_id} is not a current approved take in scene {scene}")
            if shot_id in seen:
                raise ValueError(f"{shot_id} appears more than once in the scene cut")
            seen.add(shot_id)
            duration = _source_duration(source)
            try:
                in_sec = round(float(item.get("inSec") or 0), 3)
                out_sec = round(float(item.get("outSec") or duration), 3)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{shot_id} has invalid trim times") from exc
            if in_sec < 0 or out_sec <= in_sec or out_sec > duration + 0.01:
                raise ValueError(f"{shot_id} trim must stay inside 0-{duration:g}s")
            manual = bool(item.get("manualTrim"))
            if manual:
                for line in source.get("dialogueLines") or []:
                    try:
                        start, end = float(line["startSec"]), float(line["endSec"])
                    except (KeyError, TypeError, ValueError) as exc:
                        raise ValueError(f"{shot_id} has malformed approved dialogue timing") from exc
                    if start < in_sec or end > out_sec:
                        occurrence = line.get("dialogueOccurrenceId") or "approved dialogue"
                        raise ValueError(f"{shot_id} trim would cut {occurrence}; edit HEAR first")
            normalized.append({
                "shotId": shot_id, "scene": scene, "durationSec": duration,
                "inSec": in_sec, "outSec": out_sec, "manualTrim": manual,
                "sourceHash": source["sourceHash"], "addedAt": item.get("addedAt") or _now(),
            })
        draft.setdefault("sceneCuts", {})[scene] = {
            "updatedAt": _now(), "confirmed": bool(confirm), "sequence": normalized,
        }
        _write_draft(episode, draft, out)
    return scene_status(episode, scene, out)


def scene_edit_decision(episode, scene, out=None):
    """Return the current hash-bound scene EDL for post assembly."""
    state = scene_status(episode, scene, out)
    if state["staleCount"]:
        raise ValueError("scene cut references changed or unavailable approved media")
    if not state["sequence"]:
        raise ValueError("scene cut has no approved media")
    return {
        "schemaVersion": state["schemaVersion"], "scene": state["scene"],
        "confirmed": state["confirmed"], "confirmedCurrent": state["confirmedCurrent"],
        "sequence": [{
            key: entry.get(key) for key in (
                "shotId", "sourceHash", "inSec", "outSec", "manualTrim")
        } for entry in state["sequence"]],
    }


def status(episode="Ep1"):
    episode = _validate_token(episode, "episode")
    with _LOCK:
        draft = _read_draft(episode)
        approved = _approved_shots(episode)
        sequence = []
        selected_ids = set()
        for index, entry in enumerate(draft.get("sequence") or [], 1):
            shot_id = str(entry.get("shotId") or "")
            current = approved.get(shot_id)
            is_current = bool(current and current["sourceHash"] == entry.get("sourceHash"))
            sequence.append({
                **entry,
                "order": index,
                "current": is_current,
                "reason": None if is_current else (
                    "approved take changed" if current else "approved take is no longer available"),
                "approvedTake": current["approvedTake"] if is_current else None,
            })
            selected_ids.add(shot_id)
        available = [
            {**item, "inCut": shot_id in selected_ids}
            for shot_id, item in sorted(
                approved.items(), key=lambda pair: (int(pair[1]["scene"] or 0), pair[0]))
        ]
        return {
            "schemaVersion": 1,
            "episode": episode,
            "updatedAt": draft.get("updatedAt"),
            "sequence": sequence,
            "available": available,
            "readyCount": sum(1 for entry in sequence if entry["current"]),
            "staleCount": sum(1 for entry in sequence if not entry["current"]),
        }


def add_shot(episode, shot_id):
    episode = _validate_token(episode, "episode")
    shot_id = _validate_token(shot_id, "shotId")
    with _LOCK:
        draft = _read_draft(episode)
        approved = _approved_shots(episode)
        source = approved.get(shot_id)
        if not source:
            raise ValueError("only a current approved animation take can be added to the rough cut")
        if any(entry.get("shotId") == shot_id for entry in draft["sequence"]):
            raise ValueError("shot is already in the rough cut")
        draft["sequence"].append({
            "shotId": shot_id,
            "scene": source["scene"],
            "durationSec": source["durationSec"],
            "sourceHash": source["sourceHash"],
            "addedAt": _now(),
        })
        _write_draft(episode, draft)
    return status(episode)


def remove_shot(episode, shot_id):
    episode = _validate_token(episode, "episode")
    shot_id = _validate_token(shot_id, "shotId")
    with _LOCK:
        draft = _read_draft(episode)
        before = len(draft["sequence"])
        draft["sequence"] = [entry for entry in draft["sequence"] if entry.get("shotId") != shot_id]
        if len(draft["sequence"]) == before:
            raise ValueError("shot is not in the rough cut")
        _write_draft(episode, draft)
    return status(episode)
