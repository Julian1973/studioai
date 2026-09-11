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

VERSION = "tracked-production-objects-1.0.2"

_NEGATIVE_CONTEXT = re.compile(
    r"\b(?:no|not|never|without|exclude|excluding|avoid|forbid|forbidden|prohibit|prohibited|must not|do not)\b",
    re.IGNORECASE,
)


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


def _normalise_object(raw: Mapping[str, Any], fallback_id: str) -> Dict[str, Any]:
    object_id = _text(raw.get("id") or raw.get("objectId") or fallback_id)
    name = _text(raw.get("name") or raw.get("description") or object_id)
    aliases = _list(raw.get("aliases"))
    prohibited = _list(raw.get("prohibitedSubstitutions") or raw.get("prohibited") or raw.get("forbidden"))
    return {
        "id": object_id,
        "name": name,
        "description": _text(raw.get("description") or name),
        "aliases": aliases,
        "legacyIds": _list(raw.get("legacyIds")),
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
    Names and aliases never create an object or infer its lifecycle. Legacy IDs
    must be explicitly declared by project data before deduplication.
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
            declared_legacy_ids = {alias for item in items for alias in item.get("legacyIds", [])}
            if normalised["id"] not in existing_ids | declared_legacy_ids:
                items.append(normalised)
    return items


def _near_negative(text: str, start: int) -> bool:
    sentence_start = max(text.rfind('\n', 0, start), text.rfind('.', 0, start)) + 1
    sentence_prefix = text[sentence_start:start]
    window = text[max(0, start - 160):start]
    return bool(_NEGATIVE_CONTEXT.search(sentence_prefix) or _NEGATIVE_CONTEXT.search(window))


def _positive_matches(regex: re.Pattern[str], prompt: str) -> List[str]:
    out = []
    for match in regex.finditer(prompt):
        if not _near_negative(prompt, match.start()):
            out.append(match.group(0))
    return out


def provider_clauses(shot: Mapping[str, Any]) -> List[str]:
    clauses = []
    for obj in registry_for_shot(shot):
        text = (f"{obj['id']} {obj['name']}: preserve the declared total count "
                f"of {obj['count']} across the whole sequence, including across cuts.")
        if obj['count'] == 1:
            text += " Transfers move this same object; they do not leave a copy with its former holder or at its former location."
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
    # This section is compiler-owned. Reusing a prior prompt must not retain a
    # stale lifecycle just because it already mentions the same object ID.
    prompt = re.sub(
        r"(?ms)^\[Tracked production objects\][ \t]*\n.*?(?=^\[[^\n]+\][ \t]*(?:\n|$)|\Z)",
        "", prompt,
    ).strip()
    clauses = provider_clauses(shot)
    if not clauses:
        return prompt
    addition = "\n\n[Tracked production objects]\n" + "\n".join(f"- {clause}" for clause in clauses)
    return prompt + addition


def audit_prompt(prompt: str, shot: Mapping[str, Any], references: Optional[Iterable[Mapping[str, Any]]] = None) -> Dict[str, Any]:
    prompt = _text(prompt)
    objects = registry_for_shot(shot)
    errors: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []
    for obj in objects:
        if not isinstance(obj.get('count'), int) or isinstance(obj['count'], bool) or obj['count'] < 1:
            errors.append({'objectId': obj['id'], 'reason': 'invalid declared object count'})
        # Prose matching cannot prove an ownership transfer or substitution.
        # The semantic Prompt Director receives these declared object records;
        # structured lifecycle contradictions are checked by dynamic-state review.
        warnings.append({'objectId': obj['id'], 'reason': 'Visual identity and prose compliance require semantic/output review; unverified here'})
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
