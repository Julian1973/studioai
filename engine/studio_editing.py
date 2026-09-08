"""Versioned direction edits and episode review commands on the production ledger."""
from __future__ import annotations

import json
import math
import time
import uuid
from xml.etree import ElementTree as ET

from studio_workspace import StudioError, digest
from studio_transport import Shot


COMMANDS = {"register_finish", "approve_finish", "reject_finish","apply_revision", "discard_revision", "undo_revision", "bind_states", "choose_reference", "review_join",
            "timeline_note", "resolve_note", "trim_clip", "reset_trim", "review_cut", "export_cut"}


def fields(shot):
    return Shot.model_validate({k: shot[k] for k in Shot.model_fields if k in shot}).model_dump()


def impact(old, new):
    before = fields(old)
    changed = [k for k in Shot.model_fields if before[k] != new[k]]
    reset = set()
    if changed:
        reset = {"request", "watch"}
        if "dialogue" in changed:
            reset.add("hear")
        if set(changed) - {"watchPrompt", "duration", "dialogue", "beatPlan", "endingState"}:
            reset.add("see")
    return {"changed": changed, "reset": sorted(reset),
            "preserved": [s for s in old.get("outcomes", {}) if s not in reset],
            "replacesApproved": [s for s in sorted(reset) if old.get("outcomes", {}).get(s, {}).get("status") == "approved"],
            "diff": [{"field": k, "before": before[k], "after": new[k]} for k in changed]}


def apply_edit(production, context, state, shot, new, reason):
    change = impact(shot, new)
    if not change["changed"]:
        return change
    original = json.loads(json.dumps(shot))
    original.pop("proposal", None)
    original.pop("editHistory", None)
    shot.setdefault("editHistory", []).append({"id": uuid.uuid4().hex, "before": original, "at": time.time(), "reason": reason})
    shot["editHistory"] = shot["editHistory"][-20:]
    for name in change["reset"]:
        if name in shot["outcomes"]:
            shot.setdefault("versions", []).append({"stage": name, **shot["outcomes"].pop(name)})
    shot.update(new)
    shot["sourceSignature"] = production.source_signature(context, shot)
    shot.pop("proposal", None)
    mark_joins(state, shot)
    return change


def mark_joins(state, shot):
    index = state["shots"].index(shot)
    # Only the incoming and immediately outgoing joins changed. Other shots keep their files.
    for neighbour in state["shots"][max(0, index):index + 2]:
        if state["shots"].index(neighbour) > 0:
            neighbour["continuityReview"] = f"Review the join around the change to {shot['id']}."


def handle(production, db, context, state, shot, payload):
    action, pid = payload["action"], context["project"]["id"]
    if action in {"register_finish", "approve_finish", "reject_finish", "apply_revision", "undo_revision", "bind_states", "choose_reference", "trim_clip", "reset_trim", "export_cut"}:
        active = db.execute("SELECT id FROM jobs WHERE project=? AND episode=? AND state IN ('queued','running','pending','unknown')", (pid, str(payload["episode"]))).fetchone()
        if active:
            raise StudioError("Finish or recover the current job before changing its inputs.", "job_active")
    if action in {"apply_revision", "discard_revision", "undo_revision", "bind_states", "choose_reference", "review_join", "trim_clip", "reset_trim"} and not shot:
        raise StudioError("Select the shot for this change.")
    if action in {"apply_revision", "discard_revision"}:
        proposal = shot.get("proposal")
        if not proposal or proposal["id"] != payload.get("proposalId"):
            raise StudioError("Review the current proposed change first.", "stale")
        if action == "discard_revision":
            shot.pop("proposal")
            return "Proposed change discarded. Current outcomes are retained."
        if proposal["beforeHash"] != digest(fields(shot)) or proposal.get("outcomeHash") != digest(shot.get("outcomes", {})) or proposal["sourceSignature"] != production.source_signature(context, shot):
            raise StudioError("The direction or references changed. Prepare a new proposal.", "stale")
        new = production.validate_shot(context, proposal["shot"])
        from studio_references import resolve
        resolve(production, context, {**state, 'shots': [new if s['id'] == shot['id'] else s for s in state['shots']]}, new)
        apply_edit(production, context, state, shot, new, proposal["message"])
        return "Direction applied. Prepare the updated outcome when ready; earlier versions remain available."
    if action == "undo_revision":
        history = shot.get("editHistory", [])
        if not history:
            raise StudioError("There is no direction edit to undo.")
        before = history[-1]["before"]
        if before.get("sourceSignature") != production.source_signature(context, before):
            raise StudioError("Project references changed since this edit. Prepare a new revision against current references.", "source_changed")
        for artifact in before.get("outcomes", {}).values():
            production.assert_artifact(pid, artifact)
        retained = [{"stage": k, **v} for k, v in shot["outcomes"].items()]
        versions = shot.get("versions", []) + retained
        media_reviews = {r['id']: r for r in before.get('mediaReviews', []) + shot.get('mediaReviews', [])}
        undo_log = state.setdefault("editAudit", [])
        undo_log.append({"shotId": shot["id"], "action": "undo", "editId": history[-1]["id"], "at": time.time()})
        shot.clear()
        shot.update(before)
        shot["versions"] = versions
        shot["editHistory"] = history[:-1]
        if media_reviews:
            shot['mediaReviews'] = list(media_reviews.values())
        mark_joins(state, shot)
        return "Previous direction and its recorded outcomes restored. Spending and job history are retained."
    if action in {"bind_states", "choose_reference"}:
        new = fields(shot)
        if action == 'bind_states':
            new["characterStates"] = payload.get("characterStates", [])
        else:
            new['compositionReference'] = payload.get('reference')
            new['cameraSetupId'] = str(payload.get('cameraSetupId', new['cameraSetupId'])).strip()[:100]
        new = production.validate_shot(context, new)
        production.assets(context, new)
        from studio_references import resolve
        resolve(production, context, {**state, 'shots': [new if s['id'] == shot['id'] else s for s in state['shots']]}, new)
        change = impact(shot, new)
        shot["proposal"] = {"id": uuid.uuid4().hex, "shot": new, "beforeHash": digest(fields(shot)), "outcomeHash": digest(shot.get("outcomes", {})),
                            "sourceSignature": production.source_signature(context, shot), "impact": change,
                            "message": "Use the selected approved character states." if action == 'bind_states' else "Use the selected camera setup and approved composition reference.", "createdAt": time.time()}
        return "Reference change ready to review."
    from studio_review import projection
    view = projection(production, context, state, [])
    timeline = view["timeline"]
    if payload.get("timelineFingerprint") != timeline["fingerprint"]:
        raise StudioError("The episode assembly changed. Review its current version before saving.", "stale")
    if action in {'register_finish','approve_finish','reject_finish'}:
        from studio_finish_return import handle as finish_return
        return finish_return(production, context, state, timeline, payload)
    assembly = state.setdefault("assembly", {})
    if action == "review_join":
        index = state["shots"].index(shot)
        if not index or any(timeline["clips"][i]["gap"] for i in (index - 1, index)):
            raise StudioError("Both shots need approved footage before reviewing their join.")
        shot.pop("continuityReview", None)
        assembly.setdefault("joinReviews", []).append({"shotId": shot["id"], "fingerprint": timeline["fingerprint"], "at": time.time()})
        return "Join reviewed against the current approved clips."
    if action == "timeline_note":
        note = str(payload.get("note") or "").strip()
        seconds = float(payload.get("seconds", 0))
        if not note or len(note) > 3000 or not math.isfinite(seconds) or not 0 <= seconds <= timeline["duration"]:
            raise StudioError("Add a short note at a valid episode time.")
        clip = next((c for c in timeline["clips"] if c["start"] <= seconds < c["start"] + c["duration"]), None)
        if clip is None and timeline["clips"] and seconds == timeline["duration"]:
            clip = timeline["clips"][-1]
        if not clip:
            raise StudioError("Prepare the episode shots before adding a timed note.")
        assembly.setdefault("notes", []).append({"id": uuid.uuid4().hex, "shotId": clip["shotId"], "seconds": seconds,
                                                "sourceSeconds": clip["in"] + seconds - clip["start"], "candidateId": clip["candidateId"],
                                                "note": note, "fingerprint": timeline["fingerprint"], "resolved": False})
        assembly.pop("review", None)
        return "Review note saved to this moment and shot."
    if action == "resolve_note":
        note = next((n for n in assembly.get("notes", []) if n["id"] == payload.get("noteId")), None)
        if not note:
            raise StudioError("This review note is unavailable.")
        note.update(resolved=True, resolvedAt=time.time())
        return "Review note marked addressed."
    if action in {"trim_clip", "reset_trim"}:
        clip = next(c for c in timeline["clips"] if c["shotId"] == shot["id"])
        if clip["gap"]:
            raise StudioError("Approve the shot before adjusting its assembly timing.")
        trims = assembly.setdefault("trims", {})
        if action == "reset_trim":
            trims.pop(shot["id"], None)
        else:
            start, end = float(payload.get("in", 0)), float(payload.get("out", clip["sourceDuration"]))
            if not all(math.isfinite(n) for n in (start, end)) or not 0 <= start < end <= clip["sourceDuration"]:
                raise StudioError("Keep the trim inside the approved clip's duration.")
            trims[shot["id"]] = {"candidateId": clip["candidateId"], "in": start, "out": end}
        mark_joins(state, shot)
        assembly.pop("review", None)
        return "Assembly timing updated. The original render and audio are retained; review the new cut."
    if action in {"review_cut", "export_cut"}:
        if not view["summary"]["assemblyReady"]:
            raise StudioError("The episode still has gaps. Approve the missing footage before signing off or exporting.")
        if action == "review_cut":
            if not timeline.get("preview"):
                raise StudioError("Prepare the continuous preview and watch the episode before approving its assembly.")
            if view["summary"]["blockers"] or view["summary"]["joinReviews"] or any(not n.get("resolved") for n in assembly.get("notes", [])):
                raise StudioError("Resolve the flagged media, joins and review notes before approving this assembly.")
            assembly["review"] = {"decision": "approved", "fingerprint": timeline["fingerprint"], "at": time.time()}
            return "Episode assembly approved against these exact clips and timings."
        assembly["export"] = export_cut(production, pid, str(payload["episode"]), timeline, context=context, state=state)
        return "Finishing handoff created from verified approved clips. Open its timeline and source manifest."
    raise StudioError("Choose a supported review action.")


def export_cut(production, pid, episode, timeline, *, context, state):
    """FCPXML plus a hash manifest. Originals are referenced without re-encoding."""
    from studio_post_contract import project_brief
    post_brief = project_brief(production, context, state, timeline)
    folder = production.ws.project_path(pid, f"projects/{pid}/exports/{uuid.uuid4().hex}")
    folder.mkdir(parents=True)
    root = ET.Element("fcpxml", version="1.8")
    resources = ET.SubElement(root, "resources")
    ET.SubElement(resources, "format", id="sequence-format", frameDuration="1/24s", width="1920", height="1080", colorSpace="1-1-1 (Rec. 709)")
    library = ET.SubElement(root, "library")
    event = ET.SubElement(library, "event", name=f"{pid} episode {episode}")
    project = ET.SubElement(event, "project", name=f"Episode {episode} approved-shot assembly")
    sequence = ET.SubElement(project, "sequence", format="sequence-format", tcStart="0s", tcFormat="NDF", audioLayout="stereo", audioRate="48k")
    spine = ET.SubElement(sequence, "spine")
    offset = 0
    manifest = {"projectId": pid, "episode": episode, "fingerprint": timeline["fingerprint"], "clips": [],
                "meaning": "Approved-shot assembly, 24 fps interchange timeline. Finish colour, sound and delivery checks in the finishing application.", "notes": timeline["notes"],
                "postSupervisor": post_brief}
    for index, clip in enumerate(timeline["clips"]):
        production.assert_artifact(pid, {"files": [clip["file"]]})
        path = production.ws.project_path(pid, clip["file"]["path"])
        ref = f"clip{index + 1}"
        # Review WATCH files contain the approved speech when the shot has HEAR.
        import subprocess
        probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)], check=True, capture_output=True, timeout=15).stdout)
        video = next(s for s in probe["streams"] if s["codec_type"] == "video")
        if index == 0:
            sequence_format = resources.find("format[@id='sequence-format']")
            sequence_format.set("width", str(video["width"]))
            sequence_format.set("height", str(video["height"]))
        fps_num, fps_den = (int(n) for n in video["r_frame_rate"].split("/"))
        format_id = f"format{index + 1}"
        ET.SubElement(resources, "format", id=format_id, frameDuration=f"{fps_den}/{fps_num}s", width=str(video["width"]), height=str(video["height"]))
        attributes = {"id": ref, "name": clip["shotId"], "start": "0s", "duration": f"{round(clip['sourceDuration'] * 1000)}/1000s", "hasVideo": "1", "format": format_id}
        audio = next((s for s in probe["streams"] if s["codec_type"] == "audio"), None)
        if audio:
            attributes.update(hasAudio="1", audioSources="1", audioChannels=str(audio.get("channels", 2)), audioRate=str(audio.get("sample_rate", 48000)))
        attributes["src"] = path.as_uri()  # FCPXML 1.8 uses asset.src; media-rep starts at 1.9.
        ET.SubElement(resources, "asset", attributes)
        frames = max(1, round(clip["duration"] * 24))
        ET.SubElement(spine, "asset-clip", name=clip["shotId"], ref=ref, offset=f"{offset}/24s", start=f"{round(clip['in'] * 24)}/24s", duration=f"{frames}/24s")
        manifest["clips"].append({**clip, "sourcePath": str(path), "timelineFrame": offset, "frames": frames})
        offset += frames
    sequence.set("duration", f"{offset}/24s")
    xml = folder / "episode.fcpxml"
    xml.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n' + ET.tostring(root, encoding="unicode"))
    target = folder / "source-manifest.json"
    target.write_text(json.dumps(manifest, indent=2))
    return {"fingerprint": timeline["fingerprint"], "files": [production.file_record(pid, xml), production.file_record(pid, target)], "createdAt": time.time()}
