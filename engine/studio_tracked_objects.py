"""Tracked production-object registry and prompt guard for StudioAI.

This module is deliberately deterministic and provider-free. It does not claim
image understanding. It verifies that current shot state, reference authority and
sealed provider prose describe the same physical story objects before spending.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional

VERSION = "tracked-production-objects-1.0.0"

_NEGATIVE_CONTEXT = re.compile(
    r"\b(?:no|not|never|without|exclude|excluding|avoid|forbid|forbidden|prohibit|prohibited|must not|do not)\b",
    re.IGNORECASE,
)
_STANDALONE_COMB = re.compile(r"(?<!honey)\bcomb\b", re.IGNORECASE)
_DUPLICATE_POSITIVE = re.compile(
    r"\b(?:another|second|extra|duplicate|new|separate|replacement|substitute)\s+(?:whole\s+)?(?:golden\s+)?honeycomb\b",
    re.IGNORECASE,
)
_HONEYCOMB_HOUSE_POSITIVE = re.compile(
    r"\bhoneycomb[-\s]+(?:house|home|hut|cottage|door|building|background\s+motif|motif|structure)\b",
    re.IGNORECASE,
)
_GENERIC_COMB_POSITIVE = re.compile(r"\b(?:hair|generic|brush)\s+comb\b|\bbrush\b", re.IGNORECASE)
_PARTIAL_POSITIVE = re.compile(r"\b(?:piece|chunk|slice|fragment|part)\s+of\s+(?:the\s+)?honeycomb\b", re.IGNORECASE)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, Mapping)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _stable(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(obj: Any) -> str:
    return hashlib.sha256(_stable(obj).encode("utf-8")).hexdigest()


def _contains_honeycomb_lock(shot: Mapping[str, Any]) -> bool:
    fields = [shot.get("shotId"), shot.get("seedancePrompt"), shot.get("keyframePrompt")]
    legacy_locks = shot.get("objectLifecycleLocks") or []
    if isinstance(legacy_locks, Mapping):
        iterable = [{"objectId": key, **value} if isinstance(value, Mapping) else {"objectId": key, "description": value}
                    for key, value in legacy_locks.items()]
    else:
        iterable = legacy_locks
    for lock in iterable:
        if isinstance(lock, Mapping):
            fields.extend([lock.get("objectId"), lock.get("description"), lock.get("stateIn"), lock.get("stateDuring"), lock.get("stateOut")])
    for obj in shot.get("trackedProductionObjects") or []:
        fields.extend([obj.get("id"), obj.get("name"), obj.get("description")])
    return any("honeycomb" in str(item or "").lower() for item in fields)


def _default_honeycomb_object(shot: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    if not _contains_honeycomb_lock(shot):
        return None
    return {
        "id": "H01",
        "name": "original single whole golden honeycomb",
        "description": (
            "The original removable whole golden honeycomb story object. It is round, "
            "golden, glistening and honey-cell textured. It is not a hair comb, brush, "
            "hive-house, duplicate, new substitute or partial piece."
        ),
        "aliases": ["honeycomb", "comb", "whole comb", "golden comb", "whole honeycomb"],
        "sourceReferences": ["approved scene/prop references and current shot state"],
        "stateIn": _text(shot.get("openingState") or "current shot opening state"),
        "stateDuring": _text(shot.get("action") or shot.get("shotAction") or "current shot action"),
        "stateOut": _text(shot.get("endingState") or "current shot ending state"),
        "count": 1,
        "owner": "scripted action owner only",
        "location": "current scripted world location",
        "support": "must follow visible cause and effect",
        "timing": "must change only at the planned beat",
        "visibility": "must remain readable when story-critical",
        "authorityExpiresOnChange": ["SEE", "HEAR", "WATCH", "references", "script", "duration"],
        "prohibitedSubstitutions": [
            "hair comb", "generic comb", "brush", "honeycomb-shaped house",
            "hive-house", "background honeycomb motif", "duplicate honeycomb",
            "second golden honey-cell object", "partial piece", "new substitute honeycomb",
        ],
    }


def _normalise_object(raw: Mapping[str, Any], fallback_id: str) -> Dict[str, Any]:
    object_id = _text(raw.get("id") or raw.get("objectId") or fallback_id)
    name = _text(raw.get("name") or raw.get("description") or object_id)
    aliases = _list(raw.get("aliases"))
    if not aliases and "honeycomb" in (name + " " + _text(raw.get("description"))).lower():
        aliases = ["honeycomb", "comb", "whole comb", "golden comb"]
    prohibited = _list(raw.get("prohibitedSubstitutions") or raw.get("prohibited") or raw.get("forbidden"))
    return {
        "id": object_id,
        "name": name,
        "description": _text(raw.get("description") or name),
        "aliases": aliases,
        "sourceReferences": _list(raw.get("sourceReferences") or raw.get("sourceRefs") or raw.get("references")),
        "stateIn": _text(raw.get("stateIn") or raw.get("openingState")),
        "stateDuring": _text(raw.get("stateDuring") or raw.get("during")),
        "stateOut": _text(raw.get("stateOut") or raw.get("endingState")),
        "count": raw.get("count", raw.get("expectedCount", 1)),
        "owner": _text(raw.get("owner") or raw.get("ownership")),
        "location": _text(raw.get("location")),
        "support": _text(raw.get("support")),
        "timing": _text(raw.get("timing")),
        "visibility": _text(raw.get("visibility")),
        "authorityExpiresOnChange": _list(raw.get("authorityExpiresOnChange")),
        "prohibitedSubstitutions": prohibited,
    }


def registry_for_shot(shot: Mapping[str, Any], *, project: Optional[Mapping[str, Any]] = None) -> List[Dict[str, Any]]:
    """Return normalised tracked objects for the shot.

    Explicit `trackedProductionObjects` wins. Legacy `objectLifecycleLocks` are converted.
    A conservative honeycomb default is created only when the shot already refers to a
    honeycomb lifecycle, so this stays software-wide without hard-coding one scene.
    """
    items: List[Dict[str, Any]] = []
    for idx, raw in enumerate(shot.get("trackedProductionObjects") or [], start=1):
        if isinstance(raw, Mapping):
            items.append(_normalise_object(raw, f"OBJ{idx:02d}"))
    legacy_locks = shot.get("objectLifecycleLocks") or []
    if isinstance(legacy_locks, Mapping):
        legacy_items = []
        for key, value in legacy_locks.items():
            if isinstance(value, Mapping):
                legacy_items.append({"objectId": key, **dict(value)})
            else:
                legacy_items.append({"objectId": key, "description": value})
    else:
        legacy_items = legacy_locks
    for idx, raw in enumerate(legacy_items, start=1):
        if isinstance(raw, Mapping):
            normalised = _normalise_object(raw, f"OBJ{len(items)+idx:02d}")
            existing_ids = {item["id"] for item in items}
            has_explicit_honeycomb = any(
                item.get("id") == "H01" and "honeycomb" in (item.get("name", "") + " " + item.get("description", "")).lower()
                for item in items)
            is_legacy_honeycomb = (
                normalised["id"] in {"object:honeycomb.whole", "honeycomb.whole"}
                or "honeycomb" in (normalised.get("name", "") + " " + normalised.get("description", "")).lower())
            if normalised["id"] not in existing_ids and not (has_explicit_honeycomb and is_legacy_honeycomb):
                items.append(normalised)
    default = _default_honeycomb_object(shot)
    if default and not any("honeycomb" in (item["name"] + " " + item["description"]).lower() for item in items):
        items.append(default)
    return items


def _near_negative(text: str, start: int) -> bool:
    window = text[max(0, start - 72):start]
    return bool(_NEGATIVE_CONTEXT.search(window))


def _positive_matches(regex: re.Pattern[str], prompt: str) -> List[str]:
    out = []
    for match in regex.finditer(prompt):
        if not _near_negative(prompt, match.start()):
            out.append(match.group(0))
    return out


def provider_clauses(shot: Mapping[str, Any]) -> List[str]:
    clauses = []
    for obj in registry_for_shot(shot):
        text = f"{obj['id']} {obj['name']}: preserve as one tracked story object."
        if obj.get("stateIn"):
            text += f" State in: {obj['stateIn']}."
        if obj.get("stateDuring"):
            text += f" During: {obj['stateDuring']}."
        if obj.get("stateOut"):
            text += f" State out: {obj['stateOut']}."
        if obj.get("prohibitedSubstitutions"):
            text += " No substitution: " + "; ".join(obj["prohibitedSubstitutions"][:8]) + "."
        clauses.append(text)
    return clauses


def apply_provider_clauses(prompt: str, shot: Mapping[str, Any]) -> str:
    prompt = _text(prompt)
    clauses = provider_clauses(shot)
    if not clauses:
        return prompt
    existing = prompt.lower()
    missing = [clause for clause in clauses if clause.split(":", 1)[0].lower() not in existing]
    if not missing:
        return prompt
    addition = "\n\n[Tracked production objects]\n" + "\n".join(f"- {clause}" for clause in missing)
    return prompt + addition


def audit_prompt(prompt: str, shot: Mapping[str, Any], references: Optional[Iterable[Mapping[str, Any]]] = None) -> Dict[str, Any]:
    prompt = _text(prompt)
    objects = registry_for_shot(shot)
    errors: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []
    for obj in objects:
        blob = (obj["name"] + " " + obj["description"] + " " + " ".join(obj.get("aliases") or [])).lower()
        if "honeycomb" in blob:
            if "honeycomb" in prompt.lower() and "original" not in prompt.lower():
                errors.append({"objectId": obj["id"], "reason": "tracked original honeycomb is mentioned without original-object authority"})
            for match in _STANDALONE_COMB.finditer(prompt):
                if not _near_negative(prompt, match.start()):
                    errors.append({"objectId": obj["id"], "reason": "standalone comb alias can substitute the honeycomb", "text": match.group(0)})
                    break
            if _positive_matches(_DUPLICATE_POSITIVE, prompt):
                errors.append({"objectId": obj["id"], "reason": "prompt implies a duplicate or substitute honeycomb"})
            if _positive_matches(_HONEYCOMB_HOUSE_POSITIVE, prompt):
                errors.append({"objectId": obj["id"], "reason": "prompt allows honeycomb-house or background motif substitution"})
            if _positive_matches(_GENERIC_COMB_POSITIVE, prompt):
                errors.append({"objectId": obj["id"], "reason": "prompt allows generic comb/brush substitution"})
            if _positive_matches(_PARTIAL_POSITIVE, prompt):
                errors.append({"objectId": obj["id"], "reason": "prompt changes the whole object into a partial piece"})
            exclusions = prompt.lower()
            required_negative_markers = ["duplicate", "hair comb", "honeycomb-shaped house"]
            missing = [term for term in required_negative_markers if term not in exclusions]
            if missing:
                errors.append({"objectId": obj["id"], "reason": "missing substitution exclusions", "missing": ", ".join(missing)})
        if not obj.get("sourceReferences"):
            warnings.append({"objectId": obj["id"], "reason": "object has no explicit source reference binding"})
    summary = {
        "version": VERSION,
        "status": "BLOCKED" if errors else "READY",
        "errors": errors,
        "warnings": warnings,
        "objects": objects,
        "referenceCount": len(list(references or [])),
    }
    summary["objectResolutionHash"] = digest({k: v for k, v in summary.items() if k != "objectResolutionHash"})[:32]
    return summary


def ensure_ready(prompt: str, shot: Mapping[str, Any], references: Optional[Iterable[Mapping[str, Any]]] = None) -> Dict[str, Any]:
    report = audit_prompt(prompt, shot, references)
    if report["status"] != "READY":
        reasons = "; ".join(item.get("reason", "tracked object failure") for item in report["errors"])
        raise ValueError("BLOCKED: TRACKED PRODUCTION OBJECTS — " + reasons)
    return report


def compact_report(report: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "version": report.get("version"),
        "status": report.get("status"),
        "objectResolutionHash": report.get("objectResolutionHash"),
        "objects": [{"id": item.get("id"), "name": item.get("name"), "count": item.get("count")} for item in report.get("objects") or []],
        "errors": copy.deepcopy(report.get("errors") or []),
        "warnings": copy.deepcopy(report.get("warnings") or []),
    }
