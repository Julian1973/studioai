#!/usr/bin/env python3
"""Pure Seedance production-unit packing checks shared by authoring and handover."""
import hashlib
import json


MAX_UNIT_SECONDS = 30
NEAR_FULL_SECONDS = 24
MAX_STAGES_PER_UNIT = 3
MAX_INTERNAL_SHOTS_PER_UNIT = 3
HANDOFF_HOLD_SECONDS = 1.0

COMPLEXITY_KEYWORDS = (
    "chase", "tumble", "crash", "collision", "reveal", "moustache", "mustache",
    "flower", "stamen", "gymnastic", "physical comedy", "fast", "drone",
)

BOUNDARY_REASONS = {
    "scene_end",
    "duration_limit",
    "location_or_time_change",
    "reference_regime_change",
    "continuity_reset",
    "dramatic_editorial_break",
    "complexity_protection",
}

HARD_SPLIT_REASONS = {
    "location_or_time_change",
    "reference_regime_change",
    "continuity_reset",
}

JUDGEMENT_SPLIT_REASONS = {
    "dramatic_editorial_break",
    "complexity_protection",
}


def _value(unit, key, default=None):
    if isinstance(unit, dict):
        return unit.get(key, default)
    return getattr(unit, key, default)


def _seconds(unit):
    value = _value(unit, "targetDurationSec")
    try:
        seconds = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"production unit has invalid targetDurationSec {value!r}") from exc
    if value != seconds or not 4 <= seconds <= MAX_UNIT_SECONDS:
        raise ValueError(
            f"production unit duration must be a whole 4-{MAX_UNIT_SECONDS}s value; got {value!r}")
    return seconds


def _unit_row(unit):
    stages = list(_value(unit, "stagePlan", []) or [])
    internal_shots = list(_value(unit, "internalShotPlan", []) or [])
    text = " ".join(str(_value(unit, key) or "") for key in (
        "purpose", "visualPayoff", "providerBoundaryExplanation",
        "packingJudgement", "transitionReason"))
    text += " " + " ".join(str(_value(stage, key) or "") for stage in stages
                            for key in ("purpose", "primaryEvent", "observableEndState"))
    complexity_hits = sorted({word for word in COMPLEXITY_KEYWORDS
                              if word in text.casefold()})
    return {
        "shotId": str(_value(unit, "shotId") or "").strip(),
        "beatIds": list(_value(unit, "beatIds", []) or []),
        "targetDurationSec": _seconds(unit),
        "stageCount": len(stages),
        "internalShotCount": len(internal_shots),
        "complexitySignals": complexity_hits,
        "providerBoundaryReason": str(
            _value(unit, "providerBoundaryReason") or "").strip(),
        "providerBoundaryExplanation": str(
            _value(unit, "providerBoundaryExplanation") or "").strip(),
    }


def audit_units(units):
    """Return a deterministic audit of 30-second utilization and every provider join.

    An internal camera cut is not a provider boundary. Two adjacent units whose combined
    natural duration fits in 30 seconds therefore need either a hard production boundary or
    an explicit Director/Showrunner judgement that merging would damage the scene. Duration
    capacity is not complexity capacity: a standard unit carries at most three causal stages
    and three motivated camera views.
    """
    rows = [_unit_row(unit) for unit in units]
    blocking = []
    merge_reviews = []
    protected = []

    for index, row in enumerate(rows):
        shot_id = row["shotId"] or f"unit-{index + 1}"
        reason = row["providerBoundaryReason"]
        explanation = row["providerBoundaryExplanation"]
        if (row["stageCount"] > MAX_STAGES_PER_UNIT or
                row["internalShotCount"] > MAX_INTERNAL_SHOTS_PER_UNIT):
            blocking.append({
                "code": "UNIT_COMPLEXITY_EXCEEDED",
                "shotId": shot_id,
                "message": (
                    f"{shot_id} asks one generation to carry {row['stageCount']} causal "
                    f"stages and {row['internalShotCount']} camera views. Keep one unit to "
                    f"at most {MAX_STAGES_PER_UNIT} stages and "
                    f"{MAX_INTERNAL_SHOTS_PER_UNIT} motivated views, or split at a "
                    "story-led complexity-protection boundary."),
            })
        if reason not in BOUNDARY_REASONS:
            blocking.append({
                "code": "BOUNDARY_REASON_MISSING",
                "shotId": shot_id,
                "message": "Every provider-unit boundary needs one supported reason.",
            })
        if not explanation:
            blocking.append({
                "code": "BOUNDARY_EXPLANATION_MISSING",
                "shotId": shot_id,
                "message": "Every provider-unit boundary needs an observable explanation.",
            })

        is_last = index == len(rows) - 1
        if (row["complexitySignals"] and row["targetDurationSec"] > 15 and
                reason == "scene_end" and row["stageCount"] >= MAX_STAGES_PER_UNIT):
            merge_reviews.append({
                "fromUnit": shot_id,
                "toUnit": None,
                "combinedDurationSec": row["targetDurationSec"],
                "reason": "complexity_review",
                "explanation": (
                    f"{shot_id} is a long single unit with complexity signals "
                    f"{', '.join(row['complexitySignals'])}; keep it single only if one "
                    "clear job, one camera grammar and a usable handoff frame are proven."),
                "status": "showrunner-review",
            })
        if is_last:
            if reason != "scene_end":
                blocking.append({
                    "code": "FINAL_BOUNDARY_NOT_SCENE_END",
                    "shotId": shot_id,
                    "message": "The final production unit must close with scene_end.",
                })
            continue

        next_row = rows[index + 1]
        combined = row["targetDurationSec"] + next_row["targetDurationSec"]
        boundary = {
            "fromUnit": shot_id,
            "toUnit": next_row["shotId"] or f"unit-{index + 2}",
            "combinedDurationSec": combined,
            "reason": reason,
            "explanation": explanation,
        }
        if reason == "scene_end":
            blocking.append({
                "code": "EARLY_SCENE_END",
                "shotId": shot_id,
                "message": "scene_end may appear only on the scene's final production unit.",
            })
        elif reason == "duration_limit":
            if combined <= MAX_UNIT_SECONDS:
                blocking.append({
                    "code": "FALSE_DURATION_SPLIT",
                    "shotId": shot_id,
                    "message": (
                        f"{shot_id} and {boundary['toUnit']} total {combined}s and fit inside "
                        f"one {MAX_UNIT_SECONDS}s Seedance request."),
                })
            else:
                protected.append({**boundary, "status": "protected"})
        elif reason in HARD_SPLIT_REASONS:
            protected.append({**boundary, "status": "protected"})
        elif reason in JUDGEMENT_SPLIT_REASONS:
            if combined <= MAX_UNIT_SECONDS:
                merge_reviews.append({**boundary, "status": "showrunner-review"})
            else:
                protected.append({**boundary, "status": "protected"})

    total = sum(row["targetDurationSec"] for row in rows)
    unique_beats = []
    for row in rows:
        for beat_id in row["beatIds"]:
            if beat_id not in unique_beats:
                unique_beats.append(beat_id)
    full = [row["shotId"] for row in rows if row["targetDurationSec"] == MAX_UNIT_SECONDS]
    near_full = [row["shotId"] for row in rows
                 if NEAR_FULL_SECONDS <= row["targetDurationSec"] < MAX_UNIT_SECONDS]
    short = [row["shotId"] for row in rows if row["targetDurationSec"] < NEAR_FULL_SECONDS]
    signature_rows = [{key: row[key] for key in (
        "shotId", "beatIds", "targetDurationSec", "stageCount", "internalShotCount",
        "providerBoundaryReason", "providerBoundaryExplanation")} for row in rows]
    digest = hashlib.sha256(json.dumps(
        signature_rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    return {
        "schemaVersion": 2,
        "inputDigest": digest,
        "maxUnitSec": MAX_UNIT_SECONDS,
        "nearFullThresholdSec": NEAR_FULL_SECONDS,
        "maxStagesPerUnit": MAX_STAGES_PER_UNIT,
        "maxInternalShotsPerUnit": MAX_INTERNAL_SHOTS_PER_UNIT,
        "unitCount": len(rows),
        "sourceBeatCount": len(unique_beats),
        "beatReduction": len(unique_beats) - len(rows),
        "multiBeatUnitCount": sum(1 for row in rows if len(row["beatIds"]) > 1),
        "totalPlannedSec": total,
        "windowUtilizationPct": (
            round((total / (len(rows) * MAX_UNIT_SECONDS)) * 100, 1) if rows else 0.0),
        "fullThirtySecondUnitIds": full,
        "nearFullUnitIds": near_full,
        "shortUnitIds": short,
        "unitComplexity": [{
            "shotId": row["shotId"],
            "stageCount": row["stageCount"],
            "internalShotCount": row["internalShotCount"],
            "complexitySignals": row["complexitySignals"],
            "withinStandard": (
                row["stageCount"] <= MAX_STAGES_PER_UNIT and
                row["internalShotCount"] <= MAX_INTERNAL_SHOTS_PER_UNIT),
        } for row in rows],
        "executionPolicy": {
            "default": "Use one 4-30s Seedance unit when it has one clear job and compact stage grammar.",
            "splitWhen": (
                "Split protected units for dense physical comedy, exact reveals, route-sensitive "
                "causality, major geography changes, or more than one competing camera job."),
            "continuity": (
                f"Every unit must end on a usable held handoff frame of about "
                f"{HANDOFF_HOLD_SECONDS:g}s; the next unit starts from that approved frame."),
            "music": (
                "For split production units, render Seedance with dialogue/foley only and generate "
                "one ElevenLabs scene-level music cue after stitch so score continuity does not drift."),
        },
        "protectedSplits": protected,
        "mergeReviewRequired": merge_reviews,
        "blockingIssues": blocking,
        "ready": not blocking,
        "needsHumanMergeReview": bool(merge_reviews),
    }
