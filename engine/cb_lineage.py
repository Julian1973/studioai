#!/usr/bin/env python3
"""Stable content hashes and dependency signatures for production artifacts.

Signatures deliberately contain their normalized inputs as well as a digest. The inputs
make a stale decision explainable in Studio; the digest makes equality and persistence
cheap. Timestamps and mutable approval metadata never belong in a dependency signature.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any, Mapping


SIGNATURE_SCHEMA_VERSION = 1
SCRIPT_VERSION_PREFIX = "sha256:"
SCRIPT_EVENT_CONTRACT_VERSION = 1


class LineageError(RuntimeError):
    """Raised when persisted lineage evidence is malformed or does not match its content."""


def canonical_bytes(value: Any) -> bytes:
    """Return the one UTF-8 JSON representation used by every dependency signature."""
    try:
        text = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise LineageError(f"dependency inputs are not canonical JSON: {exc}") from exc
    return text.encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: str | pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def script_version_id(data: bytes | str) -> str:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return SCRIPT_VERSION_PREFIX + sha256_bytes(raw)


def parse_script_version_id(version_id: str) -> str:
    value = str(version_id or "")
    if not value.startswith(SCRIPT_VERSION_PREFIX):
        raise LineageError("script version ID must use the sha256:<digest> form")
    digest = value[len(SCRIPT_VERSION_PREFIX):]
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise LineageError("script version ID contains an invalid SHA-256 digest")
    return digest


def dependency_signature(kind: str, inputs: Mapping[str, Any], *, schema_version: int = 1) -> dict:
    """Build a typed signature over direct inputs only."""
    kind = str(kind or "").strip()
    if not kind:
        raise LineageError("dependency signature kind is required")
    normalized_inputs = dict(inputs)
    envelope = {
        "kind": kind,
        "schemaVersion": int(schema_version),
        "inputs": normalized_inputs,
    }
    return {
        **envelope,
        "algorithm": "sha256",
        "digest": sha256_bytes(canonical_bytes(envelope)),
    }


def signature_matches(record: Mapping[str, Any] | None, kind: str,
                      inputs: Mapping[str, Any], *, schema_version: int = 1) -> bool:
    if not isinstance(record, Mapping):
        return False
    try:
        expected = dependency_signature(kind, inputs, schema_version=schema_version)
    except LineageError:
        return False
    return all(record.get(key) == expected[key]
               for key in ("kind", "schemaVersion", "algorithm", "digest", "inputs"))


def beat_package_signature(pkg: Mapping[str, Any]) -> dict:
    """Content identity for the human-approved script adaptation package."""
    content = {key: pkg.get(key) for key in (
        "title", "episode", "logline", "leadBear", "format", "unit", "beats",
        "sourceContract",
    )}
    return dependency_signature("beat-package-content", content)


def _script_event_payload(event: Mapping[str, Any]) -> dict:
    """The exact mechanically parsed payload that owns a source-event identity."""
    index = event.get("i")
    if index is None:
        index = event.get("sourceEventIndex", event.get("index"))
    scene_number = event.get("scene")
    if scene_number is None:
        scene_number = event.get("sourceSceneNumber", event.get("sceneNumber"))
    return {
        "index": int(index),
        "sceneNumber": int(scene_number),
        "type": str(event.get("type", event.get("sourceType")) or ""),
        "speaker": event.get("speaker"),
        "text": str(event.get("text") if event.get("text") is not None else
                    event.get("exactText") if event.get("exactText") is not None else
                    event.get("action") or ""),
    }


def script_event_id(script_version_id_value: str, event: Mapping[str, Any]) -> str:
    """Return a stable ID for one exact event occurrence in one immutable script."""
    parse_script_version_id(script_version_id_value)
    digest = sha256_bytes(canonical_bytes({
        "scriptVersionId": script_version_id_value,
        "event": _script_event_payload(event),
    }))
    return f"script-event:sha256:{digest}"


def dialogue_occurrence_id(script_version_id_value: str,
                           event: Mapping[str, Any]) -> str:
    """Return a unique identity even when speaker and words repeat byte-for-byte."""
    payload = _script_event_payload(event)
    if payload["type"] != "dialogue":
        raise LineageError("only dialogue events can own a dialogue occurrence ID")
    digest = sha256_bytes(canonical_bytes({
        "scriptVersionId": script_version_id_value,
        "sourceEventId": script_event_id(script_version_id_value, event),
        "kind": "dialogue-occurrence",
    }))
    return f"dialogue-occurrence:sha256:{digest}"


def source_event_record(script_version_id_value: str,
                        event: Mapping[str, Any]) -> dict:
    """Normalize one parsed event or persisted cut into its signed source record."""
    payload = _script_event_payload(event)
    record = {
        "sourceEventId": script_event_id(script_version_id_value, payload),
        "sourceEventIndex": payload["index"],
        "sourceSceneNumber": payload["sceneNumber"],
        "sourceType": payload["type"],
        "speaker": payload["speaker"],
        "text": payload["text"],
    }
    if payload["type"] == "dialogue":
        record["dialogueOccurrenceId"] = dialogue_occurrence_id(
            script_version_id_value, payload)
        record["voiceTreatment"] = str(
            event.get("voiceTreatment") or "single_voice")
        record["chorusMembers"] = list(event.get("chorusMembers") or [])
    return record


def source_beat_event_signature(script_version_id_value: str,
                                events: list[Mapping[str, Any]]) -> dict:
    """Sign one beat's exact, ordered source-event partition."""
    records = [source_event_record(script_version_id_value, event) for event in events]
    return dependency_signature("source-beat-events", {
        "scriptVersionId": script_version_id_value,
        "orderedEvents": records,
    })


def source_beat_id(signature: Mapping[str, Any]) -> str:
    digest = str(signature.get("digest") or "")
    if len(digest) != 64:
        raise LineageError("source beat signature has no valid digest")
    return f"source-beat:sha256:{digest}"


def _cut_as_event(cut: Mapping[str, Any], scene_number: Any) -> dict:
    source_type = str(cut.get("sourceType") or
                      ("dialogue" if cut.get("dialogue") else "action"))
    return {
        "i": cut.get("sourceEventIndex"),
        "scene": cut.get("sourceSceneNumber", scene_number),
        "type": source_type,
        "speaker": cut.get("speaker") if source_type == "dialogue" else None,
        "text": (cut.get("exactText") if source_type == "dialogue"
                 else cut.get("action")),
        "voiceTreatment": cut.get("voiceTreatment", "single_voice"),
        "chorusMembers": cut.get("chorusMembers") or [],
    }


def beat_package_source_contract(script_version_id_value: str,
                                 beats: list[Mapping[str, Any]]) -> dict:
    """Build the episode-wide exact event/beat/occurrence contract from persisted cuts."""
    ordered_event_ids = []
    ordered_dialogue_ids = []
    ordered_beat_ids = []
    beat_signature_digests = []
    for beat in beats:
        events = [_cut_as_event(cut, beat.get("sceneNumber"))
                  for cut in (beat.get("cuts") or [])]
        signature = source_beat_event_signature(script_version_id_value, events)
        beat_id = source_beat_id(signature)
        records = signature["inputs"]["orderedEvents"]
        ordered_beat_ids.append(beat_id)
        beat_signature_digests.append(signature["digest"])
        ordered_event_ids.extend(record["sourceEventId"] for record in records)
        ordered_dialogue_ids.extend(
            record["dialogueOccurrenceId"] for record in records
            if record["sourceType"] == "dialogue")
    inputs = {
        "scriptVersionId": script_version_id_value,
        "orderedSourceBeatIds": ordered_beat_ids,
        "sourceBeatSignatureDigests": beat_signature_digests,
        "orderedSourceEventIds": ordered_event_ids,
        "orderedDialogueOccurrenceIds": ordered_dialogue_ids,
    }
    return {
        "schemaVersion": SCRIPT_EVENT_CONTRACT_VERSION,
        "eventCount": len(ordered_event_ids),
        "dialogueOccurrenceCount": len(ordered_dialogue_ids),
        **inputs,
        "inputSignature": dependency_signature("script-event-contract", inputs),
    }


def validate_beat_package_source_contract(pkg: Mapping[str, Any]) -> dict:
    """Verify a complete, gap-free source partition without trusting display strings."""
    issues = []
    source = pkg.get("sourceScript") or {}
    script_version = source.get("scriptVersionId")
    try:
        parse_script_version_id(script_version)
    except (LineageError, TypeError):
        issues.append("missing-or-invalid-script-version")
        return {"ok": False, "issues": issues, "eventCount": 0,
                "dialogueOccurrenceCount": 0}

    beats = list(pkg.get("beats") or [])
    all_indices = []
    all_event_ids = []
    all_dialogue_ids = []
    for beat_index, beat in enumerate(beats):
        cuts = list(beat.get("cuts") or [])
        events = []
        for cut_index, cut in enumerate(cuts):
            try:
                event = _cut_as_event(cut, beat.get("sceneNumber"))
                expected = source_event_record(script_version, event)
            except (LineageError, TypeError, ValueError):
                issues.append(f"beats[{beat_index}].cuts[{cut_index}]-malformed-source-event")
                continue
            for key in ("sourceEventId", "sourceEventIndex", "sourceSceneNumber",
                        "sourceType"):
                if cut.get(key) != expected[key]:
                    issues.append(f"beats[{beat_index}].cuts[{cut_index}]-{key}-mismatch")
            if expected["sourceType"] == "dialogue":
                for key in ("speaker", "dialogueOccurrenceId"):
                    if cut.get(key) != expected[key]:
                        issues.append(f"beats[{beat_index}].cuts[{cut_index}]-{key}-mismatch")
                if cut.get("exactText") != expected["text"]:
                    issues.append(f"beats[{beat_index}].cuts[{cut_index}]-exactText-mismatch")
                if cut.get("dialogue") != f"{expected['speaker']}: {expected['text']}":
                    issues.append(f"beats[{beat_index}].cuts[{cut_index}]-dialogue-display-mismatch")
                all_dialogue_ids.append(expected["dialogueOccurrenceId"])
            elif cut.get("action") != expected["text"]:
                issues.append(f"beats[{beat_index}].cuts[{cut_index}]-action-mismatch")
            events.append(event)
            all_indices.append(expected["sourceEventIndex"])
            all_event_ids.append(expected["sourceEventId"])

        try:
            expected_signature = source_beat_event_signature(script_version, events)
            expected_beat_id = source_beat_id(expected_signature)
        except (LineageError, TypeError, ValueError):
            issues.append(f"beats[{beat_index}]-source-signature-unbuildable")
            continue
        records = expected_signature["inputs"]["orderedEvents"]
        expected_dialogue_ids = [
            record["dialogueOccurrenceId"] for record in records
            if record["sourceType"] == "dialogue"]
        if beat.get("sourceBeatId") != expected_beat_id:
            issues.append(f"beats[{beat_index}]-sourceBeatId-mismatch")
        if beat.get("sourceEventIds") != [r["sourceEventId"] for r in records]:
            issues.append(f"beats[{beat_index}]-sourceEventIds-mismatch")
        if beat.get("dialogueOccurrenceIds") != expected_dialogue_ids:
            issues.append(f"beats[{beat_index}]-dialogueOccurrenceIds-mismatch")
        if beat.get("sourceEventSignature") != expected_signature:
            issues.append(f"beats[{beat_index}]-sourceEventSignature-mismatch")
        expected_range = {
            "firstEventIndex": records[0]["sourceEventIndex"] if records else None,
            "lastEventIndex": records[-1]["sourceEventIndex"] if records else None,
            "firstEventId": records[0]["sourceEventId"] if records else None,
            "lastEventId": records[-1]["sourceEventId"] if records else None,
            "eventCount": len(records),
        }
        if beat.get("sourceEventRange") != expected_range:
            issues.append(f"beats[{beat_index}]-sourceEventRange-mismatch")

    if len(all_event_ids) != len(set(all_event_ids)):
        issues.append("duplicate-source-event-id")
    if len(all_dialogue_ids) != len(set(all_dialogue_ids)):
        issues.append("duplicate-dialogue-occurrence-id")
    if all_indices != list(range(len(all_indices))):
        issues.append("source-events-not-a-complete-ordered-partition")

    try:
        expected_contract = beat_package_source_contract(script_version, beats)
    except (LineageError, TypeError, ValueError):
        expected_contract = None
        issues.append("source-contract-unbuildable")
    if pkg.get("sourceContract") != expected_contract:
        issues.append("source-contract-mismatch")
    return {
        "ok": not issues,
        "issues": issues,
        "eventCount": len(all_event_ids),
        "dialogueOccurrenceCount": len(all_dialogue_ids),
    }


def episode_vision_inputs(script_version_id_value: str,
                          beat_package_signature_value: Mapping[str, Any],
                          canon_profile_digest: str) -> dict:
    return {
        "scriptVersionId": script_version_id_value,
        "beatPackageDigest": beat_package_signature_value.get("digest"),
        "canonProfileDigest": canon_profile_digest,
    }
