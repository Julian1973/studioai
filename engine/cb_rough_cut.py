#!/usr/bin/env python3
"""Persistent, zero-spend episode rough-cut shot selection.

This is an edit decision list, not a final master. Only approved animation takes
may enter it, and every entry is pinned to the take's content hash so a replaced
or changed source can never masquerade as the shot the editor selected.
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


ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "cb-output"
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


def _draft_path(episode):
    return OUT / f"{episode}_rough_cut_draft.json"


def _read_draft(episode):
    path = _draft_path(episode)
    if not path.exists():
        return {"schemaVersion": 1, "episode": episode, "updatedAt": None, "sequence": []}
    data = json.loads(path.read_text())
    if data.get("episode") != episode or not isinstance(data.get("sequence"), list):
        raise ValueError("rough-cut draft is malformed")
    return data


def _write_draft(episode, draft):
    OUT.mkdir(parents=True, exist_ok=True)
    draft["schemaVersion"] = 1
    draft["episode"] = episode
    draft["updatedAt"] = _now()
    fd, temp_name = tempfile.mkstemp(prefix=f".{episode}_rough_cut_", suffix=".json", dir=OUT)
    try:
        with os.fdopen(fd, "w") as target:
            json.dump(draft, target, indent=2, ensure_ascii=False)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temp_name, _draft_path(episode))
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _approved_shots(episode):
    approved = {}
    for path in OUT.glob(f"{episode}_scene*_production_package.json"):
        try:
            package = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if str(package.get("episode") or episode) != episode:
            continue
        ledgers = {entry.get("shotId"): entry for entry in package.get("continuityLedger") or []}
        scene = str(package.get("sceneNumber") or "")
        for shot in package.get("shots") or []:
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
            }
    return approved


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
