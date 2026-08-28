"""Lightweight post-render dailies loop.

This is deliberately separate from approval ledgers and prompt learning.  It records the
complete review envelope, proposes a diagnosis, and never fires a retake or changes canon.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import pathlib
import uuid
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
PATH = ROOT / "shows" / "crystal-bears" / "creative" / "learning" / "DAILIES_LIBRARY.jsonl"


def _now():
    return _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read():
    if not PATH.exists():
        return []
    return [json.loads(line) for line in PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write(record):
    PATH.parent.mkdir(parents=True, exist_ok=True)
    with PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _first_failure(snapshot, note, rating):
    text = str(note or "").lower()
    scores = snapshot.get("scores") or {}
    hints = [
        ("audio/lip-sync", ("voice", "audio", "lip", "sync", "dialogue", "mouth"), "Check the approved @Audio1 bed, timing ledger and listener mouth lock."),
        ("continuity/reference", ("continuity", "strap", "bag", "conker", "reference", "identity", "scale", "house"), "Check the approved opening/landing frames and ordered character, location and prop references."),
        ("acting/emotion", ("emotion", "anxious", "nervous", "boring", "acting", "performance", "funny", "comedy"), "Check the director's performance beat, reaction holds and physical business."),
        ("physics/action", ("physics", "walk", "move", "fall", "clip", "weight", "action"), "Check the shot-direction physical cause-and-effect and contact timing."),
        ("camera/composition", ("camera", "frame", "angle", "shot", "composition", "entrance"), "Check the camera contract and opening/landing composition."),
    ]
    for category, words, correction in hints:
        if any(word in text for word in words):
            return {"category": category, "reason": correction, "confidence": "medium"}
    weakest = min(((float(v), k) for k, v in scores.items() if isinstance(v, (int, float))), default=None)
    if weakest and weakest[0] <= 1:
        return {"category": weakest[1], "reason": "The lowest automated craft dimension is the first layer to inspect; compare it with the signed direction and render evidence.", "confidence": "low"}
    if rating < 4:
        return {"category": "unclassified", "reason": "The take needs a human note before a targeted correction can be trusted.", "confidence": "low"}
    return None


def analyze(snapshot, *, rating, decision, note=""):
    """Return an advisory diagnosis and evidence summary; never mutate production state."""
    rating = int(rating)
    diagnosis = _first_failure(snapshot, note, rating) if rating < 4 or decision == "retake" else None
    return {
        "schemaVersion": 1,
        "analysedAt": _now(),
        "beatLanded": rating >= 4,
        "likelyFailedLayer": diagnosis,
        "checks": {
            "storyBeat": bool(snapshot.get("storyBeat")),
            "promptAndProvenance": bool(snapshot.get("promptHash")),
            "openingAndLanding": bool(snapshot.get("openingFrame") or snapshot.get("landingFrame")),
            "audioBed": bool(snapshot.get("audioAsset")),
            "automatedQa": snapshot.get("automatedQa") or "not available",
        },
        "nextAction": "Ask whether this diagnosis is right; do not fire automatically." if diagnosis else "Await the selected approval decision.",
    }


def record(snapshot, *, rating, decision, note="", reviewer="Julian", cost=None, retake_of=None):
    if int(rating) not in range(1, 6):
        raise ValueError("rating must be 1-5")
    decision = str(decision).strip().lower()
    if decision not in {"approve", "retake", "reject"}:
        raise ValueError("decision must be approve, retake or reject")
    analysis = analyze(snapshot, rating=int(rating), decision=decision, note=note)
    record_id = "daily-" + uuid.uuid4().hex[:12]
    record = {
        "schemaVersion": 1, "recordId": record_id, "recordedAt": _now(),
        "episode": snapshot.get("episode"), "scene": snapshot.get("scene"),
        "beat": snapshot.get("beat"), "shotId": snapshot.get("shotId"),
        "take": snapshot.get("take") or snapshot.get("candidateId"),
        "candidateId": snapshot.get("candidateId"), "assetPath": snapshot.get("assetPath"),
        "assetHash": snapshot.get("assetHash"), "promptHash": snapshot.get("promptHash"),
        "promptVersion": snapshot.get("promptVersion"), "keyframeVersion": snapshot.get("keyframeVersion"),
        "audioVersion": snapshot.get("audioVersion"), "provider": snapshot.get("provider"),
        "providerModelId": snapshot.get("providerModelId"), "operationId": snapshot.get("operationId"),
        "timing": snapshot.get("timing") or {}, "automatedScores": snapshot.get("automatedScores") or {},
        "rating": int(rating), "decision": decision, "note": str(note or "").strip(),
        "reviewer": str(reviewer or "Julian").strip(), "cost": cost,
        "retakeOf": retake_of, "analysis": analysis,
        "diagnosisState": "awaiting-confirmation" if analysis["likelyFailedLayer"] else None,
    }
    if retake_of:
        # Compare against the prior immutable row before appending the new row.
        prior = next((row for row in _read() if row.get("recordId") == retake_of), None)
        if prior:
            record["analysis"]["comparison"] = {
                "ratingDelta": int(rating) - int(prior.get("rating", 0)),
                "ratingImproved": int(rating) > int(prior.get("rating", 0)),
                "changed": {
                    "prompt": snapshot.get("promptHash") != prior.get("promptHash"),
                    "asset": snapshot.get("assetHash") != prior.get("assetHash"),
                    "audio": snapshot.get("audioVersion") != prior.get("audioVersion"),
                },
            }
    _write(record)
    return record


def compare(record_id):
    rows = _read()
    current = next((row for row in rows if row.get("recordId") == record_id), None)
    if not current or not current.get("retakeOf"):
        return None
    prior = next((row for row in rows if row.get("recordId") == current["retakeOf"]), None)
    if not prior:
        return {"status": "source-not-found", "retakeOf": current["retakeOf"]}
    return {
        "status": "compared", "retakeOf": prior["recordId"],
        "ratingImproved": current.get("rating", 0) > prior.get("rating", 0),
        "ratingDelta": current.get("rating", 0) - prior.get("rating", 0),
        "diagnosisFixed": bool(prior.get("analysis", {}).get("likelyFailedLayer")) and
            not current.get("analysis", {}).get("likelyFailedLayer"),
        "changed": {"prompt": current.get("promptHash") != prior.get("promptHash"), "asset": current.get("assetHash") != prior.get("assetHash"), "audio": current.get("audioVersion") != prior.get("audioVersion")},
        "additionalCost": current.get("cost"),
    }


def report():
    rows = _read()
    approved = [r for r in rows if r.get("decision") == "approve"]
    retakes = [r for r in rows if r.get("decision") == "retake"]
    improvements = [r.get("analysis", {}).get("comparison", {}).get("ratingDelta") for r in rows]
    improvements = [int(v) for v in improvements if isinstance(v, (int, float))]
    cats = Counter((r.get("analysis", {}).get("likelyFailedLayer") or {}).get("category") for r in rows)
    return {"count": len(rows), "averageRating": round(sum(r.get("rating", 0) for r in rows) / len(rows), 2) if rows else 0,
            "firstPassApprovalRate": round(sum(1 for r in approved if not r.get("retakeOf")) / max(1, len(rows)), 3),
            "retakesPerApprovedShot": round(len(retakes) / max(1, len(approved)), 2),
            "mostCommonFailure": cats.most_common(1)[0][0] if cats else None,
            "averageImprovementAfterRetake": round(sum(improvements) / len(improvements), 2) if improvements else None,
            "learningRecommendations": []}


def rows():
    return _read()
