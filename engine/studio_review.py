"""Read models for the director's board and review timeline.

Readiness is derived from current approvals and verified media, never navigation.
This module does not submit generation, modify source files or invent approvals.
"""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import subprocess

from studio_workspace import StudioError, asset_digest, digest


STAGES = ("see", "hear", "request", "watch")
ROLES = {"see": "keyframes", "hear": "voices", "watch": "animation"}


def stage(shot):
    if shot.get("importedArchive"):
        return "archive"
    return next((s for s in STAGES if (s != "hear" or shot.get("dialogue")) and
                 shot.get("outcomes", {}).get(s, {}).get("status") != "approved"), "done")


@lru_cache(maxsize=512)
def media_duration(path, modified, size):
    try:
        result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "json", path], capture_output=True, timeout=15, check=True)
        return round(float(json.loads(result.stdout)["format"]["duration"]), 3)
    except Exception:
        return None


def verified_file(ws, pid, record):
    if not record or not record.get("hash"):
        return None
    try:
        path = ws.project_path(pid, record["path"])
        stat = path.stat()
        if not path.is_file() or asset_digest(str(path), stat.st_mtime_ns, stat.st_size) != record["hash"]:
            return None
        return path, stat
    except (StudioError, OSError, KeyError):
        return None


def issue(code, message, severity="warning", **extra):
    return {"code": code, "message": message, "severity": severity, **extra}


def inspect(production, context, state, shot):
    pid = context["project"]["id"]
    problems, references = [], []
    if not shot.get("importedArchive"):
        try:
            references = production.assets(context, shot)
        except StudioError as exc:
            problems.append(issue(exc.code, str(exc), "blocker"))
        for ref in references:
            if ref.get("approvalStatus") != "approved":
                problems.append(issue("reference_review", f"Check {ref['name']} against the SEE outcome; library approval is not recorded."))
        for claim in shot.get("identityClaims", []):
            canonical = context["assets"]["characters"].get(claim["character"], {}).get("identityTraits", {})
            expected = canonical.get(claim["trait"])
            if expected is not None and str(expected).casefold() != claim["value"].casefold():
                problems.append(issue("identity_conflict", f"{claim['character']}: {claim['trait']} is {expected} in the project library; the direction says {claim['value']}.", "blocker"))
        for field in ("camera", "geography"):
            if not shot.get(field):
                problems.append(issue("missing_direction", f"The shot needs {field} direction.", "blocker"))
    if shot.get("continuityReview"):
        problems.append(issue("join_review", shot["continuityReview"]))
    for name, outcome in shot.get("outcomes", {}).items():
        if outcome.get("status") in {"approved", "candidate"}:
            for item in outcome.get("files", []):
                if not verified_file(production.ws, pid, item):
                    problems.append(issue("media_changed", f"The {name.upper()} file is missing or differs from its recorded version.", "blocker", stage=name))
                    break
    index = state["shots"].index(shot)
    previous = state["shots"][index - 1] if index else None
    if previous and previous["scene"] == shot["scene"]:
        watch = previous.get("outcomes", {}).get("watch", {})
        ending = watch.get("ending")
        if watch.get("status") == "approved" and verified_file(production.ws, pid, ending):
            references.append({**ending, "name": f"{previous['id']} approved ending", "role": "previous state",
                               "approvalStatus": "approved", "version": watch["id"]})
        elif shot.get("transition") == "continuation" and not shot.get("importedArchive"):
            problems.append(issue("handoff_required", "This continuation needs the preceding approved ending frame.", "blocker"))
    actual = []
    for name in ("see", "request"):
        outcome = shot.get("outcomes", {}).get(name, {})
        for ref in outcome.get("references", outcome.get("images", [])):
            actual.append({**ref, "usedFor": name, "candidateId": outcome.get("id")})
    from studio_references import suggestions, resolve
    from studio_media_review import current_reports
    choices = suggestions(production, context, state, shot) if not shot.get('importedArchive') else []
    try:
        selected = resolve(production, context, state, shot)
        if selected:
            references.append(selected)
    except StudioError as exc:
        # Once SEE was approved, its recorded image is the downstream authority.
        # A newer source reference requires review before a new SEE, not destruction
        # of the already reviewed picture/voice/render or an assembly dead end.
        locked_opening = shot.get('outcomes', {}).get('see', {}).get('status') == 'approved'
        problems.append(issue(exc.code, str(exc) + (' The approved opening and its downstream outcomes are retained.' if locked_opening else ''),
                              'warning' if locked_opening else 'blocker'))
    return {"issues": problems, "references": references, "actualReferences": actual, "suggestions": choices,
            "mediaReviews": current_reports(production, context, state, shot) if shot.get('mediaReviews') else [],
            "claim": "Checks cover recorded identity traits, reference versions and handoffs. Visual likeness and performance require viewing."}


def projection(production, context, state, jobs):
    ws, pid = production.ws, context["project"]["id"]
    services = ws.services(pid)
    rows, scenes, clips = [], {}, []
    total = approved_duration = approved_voice = 0.0
    voice_total = approved_count = generated_count = 0
    inspections = {}
    for shot in state["shots"]:
        sid, outcomes = shot["id"], shot.get("outcomes", {})
        current = stage(shot)
        inspection = inspect(production, context, state, shot)
        inspections[sid] = inspection
        watch = outcomes.get("watch", {})
        file = (watch.get("files") or [None])[0]
        verified = verified_file(ws, pid, file)
        measured = media_duration(str(verified[0]), verified[1].st_mtime_ns, verified[1].st_size) if verified else None
        accepted = watch.get("status") == "approved" and measured is not None
        generated_count += int(bool(verified))
        approved_count += int(accepted)
        approved_duration += measured if accepted else 0
        hear = outcomes.get("hear", {})
        voice_total += int(bool(shot.get("dialogue")))
        approved_voice += int(bool(shot.get("dialogue")) and hear.get("status") == "approved" and
                              bool(verified_file(ws, pid, (hear.get("files") or [None])[0])))
        duration = measured if accepted else float(shot.get("duration") or 0)
        trim = state.get("assembly", {}).get("trims", {}).get(sid, {})
        trim_valid = accepted and trim.get("candidateId") == watch.get("id")
        start = float(trim.get("in", 0)) if trim_valid else 0
        end = float(trim.get("out", duration)) if trim_valid else duration
        if start < 0 or end > duration + .01 or end <= start:
            start, end = 0, duration
        clip = {"shotId": sid, "scene": shot["scene"], "title": shot["title"], "start": round(total, 3),
                "duration": round(end - start, 3), "in": start, "out": end, "sourceDuration": duration,
                "gap": not accepted, "file": file if accepted else None,
                "candidateId": watch.get("id") if accepted else None, "joinReview": bool(shot.get("continuityReview"))}
        clips.append(clip)
        total += end - start
        job = next((j for j in jobs if j.get("shotId") == sid and j["status"] in {"queued", "running", "pending", "unknown", "interrupted"}), None)
        blocked = any(i["severity"] == "blocker" for i in inspection["issues"])
        candidate = outcomes.get(current, {})
        status = "preparing" if job else "needs_attention" if blocked or shot.get("continuityReview") or candidate.get("status") == "rejected" else "approved" if accepted else "ready_for_review" if candidate.get("status") == "candidate" else "missing"
        estimate = 0.0
        known = True
        for outcome_stage, role in ROLES.items():
            if outcome_stage == "hear" and not shot.get("dialogue"):
                continue
            if outcomes.get(outcome_stage, {}).get("status") in {"approved", "candidate"}:
                continue
            value = services.get(role, {}).get("estimateUsd")
            if value is None:
                known = False
            else:
                estimate += value
        see = outcomes.get("see", {})
        thumbnail = (see.get("files") or [None])[0]
        if not verified_file(ws, pid, thumbnail):
            thumbnail = watch.get("ending") if verified_file(ws, pid, watch.get("ending")) else None
        row = {"id": sid, "scene": shot["scene"], "title": shot["title"], "stage": current, "status": status,
               "thumbnail": thumbnail, "approved": accepted, "plannedSeconds": shot.get("duration", 0),
               "approvedSeconds": measured if accepted else 0, "remainingEstimateUsd": round(estimate, 4) if known else None,
               "issueCount": len(inspection["issues"]), "job": job,
               "nextEstimateUsd": services.get(ROLES.get(current), {}).get("estimateUsd")}
        rows.append(row)
        scene = scenes.setdefault(shot["scene"], {"number": shot["scene"], "shots": [], "approved": 0, "approvedSeconds": 0, "remainingEstimateUsd": 0})
        scene["shots"].append(row)
        scene["approved"] += int(accepted)
        scene["approvedSeconds"] += measured if accepted else 0
        scene["remainingEstimateUsd"] = scene["remainingEstimateUsd"] + estimate if known and scene["remainingEstimateUsd"] is not None else None
    fingerprint = digest([{k:v for k,v in clip.items() if k not in {"joinReview", "title"}} for clip in clips])
    notes = state.get("assembly", {}).get("notes", [])
    timeline = {"clips": clips, "duration": round(total, 3), "fingerprint": fingerprint,
                "notes": notes, "gaps": sum(c["gap"] for c in clips), "export": state.get("assembly", {}).get("export"),
                "review": state.get("assembly", {}).get("review")}
    preview = state.get("assembly", {}).get("preview")
    timeline["preview"] = preview if preview and preview.get("fingerprint") == fingerprint and verified_file(ws, pid, (preview.get("files") or [None])[0]) else None
    issues = [i for v in inspections.values() for i in v["issues"]]
    return {"scenes": list(scenes.values()), "shots": rows, "inspections": inspections, "timeline": timeline,
            "summary": {"shots": len(rows), "generatedShots": generated_count, "approvedShots": approved_count,
                        "approvedSeconds": round(approved_duration, 3), "approvedVoices": int(approved_voice), "voiceShots": voice_total,
                        "joinReviews": sum(s.get("continuityReview") is not None for s in state["shots"]),
                        "blockers": sum(i["severity"] == "blocker" for i in issues),
                        "assemblyReady": bool(rows) and all(not c["gap"] for c in clips),
                        "reviewCurrent": bool(timeline["review"] and timeline["review"].get("fingerprint") == fingerprint and timeline["review"].get("decision") == "approved")}}
