"""Project-scoped production commands shared by the agent and the visible controls.

One durable state/command/job ledger; model output is creative data, never executable
instructions. Only user commands can approve outcomes, budgets or a WATCH request.
"""
from __future__ import annotations

from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading
import time
import uuid

from studio_workspace import Workspace, StudioError, digest, token
from studio_transport import ProviderTransport, EpisodePlan, Shot, AgentReply


STANDARD_PATH = Path(__file__).resolve().parent.parent / "skills/project-production-standard.md"

_RUNNING = set()
_RUNNING_LOCK = threading.Lock()
STAGES = ("see", "hear", "request", "watch")
ROLE = {"plan": "direction", "chat": "direction", "revise": "direction", "see": "keyframes", "hear": "voices", "watch": "animation"}


def money(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number <= 0 or number > 100000:
            raise ValueError()
        return int(number * 1000000)
    except Exception:
        raise StudioError("Enter a positive budget in USD.") from None


def initial():
    return {"revision": 0, "sourceHash": None, "shots": [], "history": [], "messages": [],
            "budget": {"allowance": 0, "reserved": 0, "committed": 0}, "reviews": []}


def copy_json(value):
    return json.loads(json.dumps(value))


def file_hash(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


class Production:
    def __init__(self, workspace, *, transport=None, background=True):
        self.ws = workspace
        self.transport = transport or ProviderTransport()
        self.background = background

    def _load(self, db, pid, ep):
        row = db.execute("SELECT data FROM production WHERE project=? AND episode=?", (pid, ep)).fetchone()
        return json.loads(row[0]) if row else initial()

    def _save(self, db, pid, ep, state):
        state["revision"] += 1
        db.execute("INSERT OR REPLACE INTO production VALUES(?,?,?,?)", (pid, ep, state["revision"], json.dumps(state)))

    def _job(self, db, job):
        db.execute("INSERT OR REPLACE INTO jobs VALUES(?,?,?,?,?)", (job["id"], job["projectId"], job["episode"], job["status"], json.dumps(job)))

    def snapshot(self, pid, ep=None):
        context = self.ws.context(pid, ep)
        if context.get("legacy"):
            return {"project": context["project"], "legacy": True, "services": self.ws.services(pid),
                    "message": "This project uses the existing production desk. Its approved work remains in that ledger."}
        with self.ws.db() as db:
            state = self._load(db, pid, str(ep)) if ep is not None else initial()
            jobs = [json.loads(r[0]) for r in db.execute("SELECT data FROM jobs WHERE project=? AND episode=? ORDER BY rowid DESC LIMIT 30", (pid, str(ep)))]
        # Job inputs contain source context, but no keys. Expose only useful status.
        public_jobs = [{k: j.get(k) for k in ("id", "kind", "shotId", "status", "taskId", "message", "code", "binding", "createdAt")} for j in jobs]
        for item, job in zip(public_jobs, jobs):
            if job["status"] in {"queued", "running"} and job.get("pid") != os.getpid():
                item.update(status="interrupted", message="Studio restarted. Resume this job to recover its recorded progress.")
        return {"project": context["project"], "episodes": context["episodes"], "episode": ep,
                "services": self.ws.services(pid), "state": state, "jobs": public_jobs,
                "sourceChanged": bool(state["sourceHash"] and state["sourceHash"] != context["sourceHash"] and self.source_impact(state, context)),
                "sourceHash": context["sourceHash"]}

    def selected(self, state, shot_id):
        shot = next((s for s in state["shots"] if s["id"] == shot_id), None)
        if not shot:
            raise StudioError("Select a shot in this episode.", "scope_mismatch")
        return shot

    def source_signature(self, context, shot):
        assets = context["assets"]
        selected = [assets["characters"].get(name) for name in shot["characters"]]
        selected += [a for a in assets["locations"] if a["name"] == shot["location"]]
        selected += [a for a in assets["props"] if a["name"] in shot["props"]]
        paths = [a.get("anchor") or a.get("image") for a in selected if a]
        return digest({"bible": context["bible"], "project": {k: context["project"].get(k) for k in ("style", "aspectRatio", "audience", "premise")}, "assets": selected,
                       "images": {p: context["assetDigests"].get(p) for p in paths if p}})

    def source_impact(self, state, context):
        return (state.get("scriptHash") != digest(context["script"]) or
                any(s.get("sourceSignature") != self.source_signature(context, s) for s in state["shots"]))

    def artifact(self, shot, stage):
        return (shot.get("outcomes") or {}).get(stage)

    def assert_artifact(self, pid, artifact):
        if not artifact:
            raise StudioError("Prepare this outcome before reviewing it.")
        for item in artifact.get("files", []):
            path = self.ws.project_path(pid, item["path"])
            if not path.is_file() or file_hash(path) != item["hash"]:
                raise StudioError("The reviewed file has changed or is missing. Restore it or create a new candidate.", "stale")

    def assets(self, context, shot):
        assets = context["assets"]
        refs = []
        for name in shot["characters"]:
            value = assets["characters"].get(name)
            if not value or not value.get("anchor"):
                raise StudioError(f"Add a character reference for {name} in this project.", "missing_reference")
            refs.append({"name": name, "path": value["anchor"]})
        for group, names in (("locations", [shot["location"]] if shot["location"] else []), ("props", shot["props"])):
            for name in names:
                value = next((a for a in assets[group] if a["name"] == name), None)
                if not value or not value.get("image"):
                    raise StudioError(f"Add a {group} reference for {name} in this project.", "missing_reference")
                refs.append({"name": name, "path": value["image"]})
        if len(refs) > 10:
            raise StudioError("This shot needs a consolidated reference plate; the keyframe adapter supports ten references.", "reference_limit")
        for ref in refs:
            path = self.ws.project_path(context["project"]["id"], ref["path"])
            if not path.is_file():
                raise StudioError("A selected project reference is missing.", "missing_reference")
            ref["hash"] = file_hash(path)
        return refs

    def validate_shot(self, context, shot):
        shot = Shot.model_validate(shot).model_dump()
        token(shot["id"])
        lines = context["script"].splitlines()
        if not 1 <= shot["startLine"] <= shot["endLine"] <= len(lines) or not 4 <= shot["duration"] <= 30 or shot["scene"] < 1:
            raise StudioError("The director returned invalid source coverage or timing. Existing work is preserved.", "invalid_plan")
        if shot["transition"] not in {"cut", "continuation"}:
            raise StudioError("Each shot must identify a cut or continuation.", "invalid_plan")
        if not set(shot["characters"]).issubset(context["assets"]["characters"]):
            raise StudioError("The director named a character outside this project's library.", "invalid_plan")
        for group, names in (("locations", [shot["location"]] if shot["location"] else []), ("props", shot["props"])):
            if not set(names).issubset({a["name"] for a in context["assets"][group]}):
                raise StudioError("The director named an asset outside this project's library.", "invalid_plan")
        source = "\n".join(lines[shot["startLine"] - 1:shot["endLine"]])
        cursor = 0
        for line in shot["dialogue"]:
            position = source.find(line["text"], cursor)
            if not line["text"].strip() or position < 0 or line["speaker"] not in context["assets"]["characters"]:
                raise StudioError("The proposed dialogue does not match its script occurrence and cast.", "invalid_plan")
            cursor = position + len(line["text"])
        for field in ("emotion", "performance", "camera", "geography", "seePrompt", "watchPrompt"):
            if not shot[field].strip() or len(shot[field]) > 12000:
                raise StudioError("The director returned incomplete shot direction.", "invalid_plan")
        return shot

    def validate_plan(self, context, plan):
        plan = EpisodePlan.model_validate(plan).model_dump()
        shots = [self.validate_shot(context, s) for s in plan["shots"]]
        cursor = 1
        ids = set()
        scene = 0
        for shot in shots:
            if shot["startLine"] != cursor or shot["id"] in ids or shot["scene"] < scene:
                raise StudioError("The proposed shots omit, repeat or reorder script coverage.", "invalid_plan")
            cursor = shot["endLine"] + 1
            ids.add(shot["id"])
            scene = shot["scene"]
        if cursor != len(context["script"].splitlines()) + 1:
            raise StudioError("The director did not cover the whole script. Existing work is preserved.", "invalid_plan")
        return shots

    def _prompt(self, context, shot, stage, refs):
        direction = {k: shot[k] for k in ("emotion", "performance", "camera", "geography", "transition")}
        labels = "\n".join(f"@Image{i + 1}: {r['name']}" for i, r in enumerate(refs))
        return (f"Project: {context['project']['name']}\nFrame aspect: {context['project'].get('aspectRatio', '16:9')}\nVisual style: {context['project'].get('style', '')}\n"
                f"Project bible:\n{context['bible']}\nShot direction:\n{json.dumps(direction, ensure_ascii=False)}\n"
                f"References:\n{labels}\n{shot['seePrompt' if stage == 'see' else 'watchPrompt']}\n"
                "Preserve referenced identities, scale, prop ownership and screen geography. Use the stated camera view; do not mirror the scene.")

    def _stage(self, shot):
        for stage in STAGES:
            if stage == "hear" and not shot["dialogue"]:
                continue
            item = self.artifact(shot, stage)
            if not item or item.get("status") != "approved":
                return stage
        return "done"

    def _message(self, state, role, message, **extra):
        state["messages"].append({"role": role, "text": str(message)[:12000], "at": time.time(), **extra})
        state["messages"] = state["messages"][-80:]

    def command(self, payload):
        pid, ep = token(payload.get("projectId")), token(payload.get("episode"))
        context = self.ws.context(pid, ep)
        if context.get("legacy"):
            raise StudioError("Open this project's existing production desk to direct its current shots.", "legacy_project")
        if context["project"].get("archived"):
            raise StudioError("This project is archived.")
        command_id = token(payload.get("commandId"))
        action = str(payload.get("action") or "")
        launch = None
        advance = None
        with self.ws.db() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT result FROM commands WHERE project=? AND episode=? AND id=?", (pid, ep, command_id)).fetchone()
            if previous:
                return json.loads(previous[0])
            state = self._load(db, pid, ep)
            # Polling a pinned job does not approve or edit an outcome. A provider
            # completion racing a poll must not create a false stale-review error.
            if action not in {"resume", "status"} and payload.get("expectedRevision") != state["revision"]:
                raise StudioError("This shot changed in another window. The studio will reload the current outcome for review.", "stale")
            if state["sourceHash"] and state["sourceHash"] != context["sourceHash"]:
                if not self.source_impact(state, context):
                    state["sourceHash"] = context["sourceHash"]
                elif action not in {"status", "resume", "refresh_sources", "reconcile", "budget"}:
                    raise StudioError("The project source changed. Review the source update notice before continuing.", "source_changed")
            shot_id = str(payload.get("shotId") or "")
            shot = self.selected(state, shot_id) if shot_id else None
            message = str(payload.get("message") or "").strip()
            if len(message) > 12000:
                raise StudioError("Keep this direction under 12,000 characters.")
            # Credentials belong in the password input, never in the persisted chat.
            if re.search(r"\b(?:sk-[A-Za-z0-9_-]{12,}|ark-[A-Za-z0-9_-]{16,})", message):
                raise StudioError("Put API keys in Workspace connections, then remove the key from this message.", "secret_in_chat")
            if action == "chat":
                self._message(state, "user", message, shotId=shot_id)
                normalized = message.lower().strip(" .!")
                action = {"approve": "approve", "reject": "reject", "continue": "continue", "next": "continue",
                          "status": "status", "help": "status", "prepare": "prepare",
                          "fire": "watch", "render": "watch", "resume": "resume"}.get(normalized, "chat")
                match = re.fullmatch(r"approve (?:episode )?budget \$?([0-9]+(?:\.[0-9]{1,2})?)", normalized)
                if match:
                    action = "budget"
                    payload = {**payload, "amountUsd": match[1]}
                elif normalized in {"approve see", "approve hear", "approve watch", "approve request"}:
                    action = "approve"
                    if not shot or self._stage(shot) != normalized.split()[1]:
                        raise StudioError("Open the outcome named in your approval first.", "stale")
            if action == "refresh_sources":
                if payload.get("sourceHash") != context["sourceHash"]:
                    raise StudioError("The sources changed again. Review their current version.", "stale")
                if state.get("scriptHash") != digest(context["script"]):
                    raise StudioError("The screenplay changed. Save it as a new episode or sequence version so approved dialogue and shot coverage stay traceable.", "script_changed")
                active = db.execute("SELECT id FROM jobs WHERE project=? AND episode=? AND state IN ('queued','running','pending','unknown')", (pid, ep)).fetchone()
                if active:
                    raise StudioError("Finish or recover the current job before refreshing source dependencies.", "job_active")
                state["history"].append({"reason": "Project sources updated", "sourceHash": state["sourceHash"], "shots": copy_json(state["shots"])})
                for item in state["shots"]:
                    self.validate_shot(context, {k: item[k] for k in Shot.model_fields})
                    signature = self.source_signature(context, item)
                    if item.get("sourceSignature") == signature:
                        continue
                    if self._stage(item) != "done":
                        for s in ("see", "request", "watch"):
                            if s in item["outcomes"]:
                                item["versions"].append({"stage": s, **item["outcomes"].pop(s)})
                    else:
                        item["continuityReview"] = "Approved against earlier project sources. Review the join with newly generated work."
                    item["sourceSignature"] = signature
                state["sourceHash"] = context["sourceHash"]
                self._message(state, "agent", "Updated project sources are now active. Finished shots and approved voices are preserved; unfinished pictures can be prepared from the new references.")
            elif action == "budget":
                amount = money(payload.get("amountUsd"))
                if amount < state["budget"]["committed"] + state["budget"]["reserved"]:
                    raise StudioError("The allowance cannot be below work already committed or reserved.")
                state["budget"]["allowance"] = amount
                state["budget"]["approvedAt"] = time.time()
                self._message(state, "agent", "Episode allowance recorded. I can prepare its shots within the configured estimates; you approve each outcome.")
                if not state["shots"]:
                    advance = ""
            elif action == "status":
                self._message(state, "agent", self.status_message(state, shot))
            elif action in {"approve", "reject"}:
                if not shot:
                    raise StudioError("Choose the shot you are reviewing.")
                stage = self._stage(shot)
                item = self.artifact(shot, stage)
                self.assert_artifact(pid, item)
                if item["id"] != payload.get("reviewId") or item["status"] != "candidate":
                    raise StudioError("Review the current candidate before deciding.", "stale")
                item["status"] = "approved" if action == "approve" else "rejected"
                item["reviewedAt"] = time.time()
                item["note"] = str(payload.get("note") or message)[:3000]
                state["reviews"].append({"shotId": shot_id, "stage": stage, "candidateId": item["id"], "decision": item["status"], "note": item["note"]})
                self._message(state, "agent", f"{stage.upper()} {item['status']}. " + self.status_message(state, shot))
                if action == "approve":
                    advance = shot_id
            elif action == "reconcile":
                row = db.execute("SELECT data FROM jobs WHERE id=? AND project=? AND episode=?", (token(payload.get("jobId")), pid, ep)).fetchone()
                if not row:
                    raise StudioError("That job is not in this episode.", "scope_mismatch")
                job = json.loads(row[0])
                if job["status"] != "unknown" or payload.get("providerChecked") is not True:
                    raise StudioError("Check the uncertain request in your provider account before closing it.")
                if payload.get("taskId") and job["kind"] == "watch":
                    job.update(taskId=token(payload["taskId"]), status="pending")
                    self._job(db, job)
                    launch = job
                else:
                    state["budget"]["reserved"] -= job["estimate"]
                    state["budget"]["committed"] += job["estimate"]
                    job.update(status="failed", message="Closed after user checked the provider. Its estimated cost is retained.")
                    self._job(db, job)
                    self._message(state, "agent", job["message"])
            elif action == "resume":
                job_id = payload.get("jobId")
                if not job_id:
                    latest = db.execute("SELECT id FROM jobs WHERE project=? AND episode=? AND state IN ('queued','running','pending','unknown') ORDER BY rowid DESC LIMIT 1", (pid, ep)).fetchone()
                    job_id = latest[0] if latest else None
                row = db.execute("SELECT data FROM jobs WHERE id=? AND project=? AND episode=?", (token(job_id), pid, ep)).fetchone()
                if not row:
                    raise StudioError("That job is not in the selected episode.", "scope_mismatch")
                job = json.loads(row[0])
                if job["status"] == "completed":
                    self._message(state, "agent", "This job is already complete. Review its outcome below.")
                elif job.get("taskId") or job.get("imageUrl"):
                    launch = job
                elif job["status"] == "queued":
                    launch = job
                else:
                    raise StudioError("No provider task ID was confirmed. Check the provider account before creating another request.", "submission_unknown")
            else:
                if action == "continue":
                    if not state["shots"]:
                        action = "prepare"
                    else:
                        shot = shot or next((s for s in state["shots"] if self._stage(s) != "done"), None)
                        if not shot:
                            action = "status"
                        else:
                            shot_id = shot["id"]
                            stage = self._stage(shot)
                            candidate = self.artifact(shot, stage)
                            if candidate and candidate["status"] == "candidate":
                                action = "status"
                            else:
                                action = "watch" if stage == "watch" else stage
                if action == "status":
                    self._message(state, "agent", self.status_message(state, shot))
                elif action == "request":
                    if not shot:
                        raise StudioError("Choose a shot first.")
                    item = self.watch_request(context, state, shot)
                    self._replace(shot, "request", item)
                    self._message(state, "agent", "WATCH request ready. Review the prompt, script, references, duration and estimate before approving.")
                else:
                    kind = "plan" if action == "prepare" else action
                    if kind not in ROLE:
                        raise StudioError("Choose a production action or send the agent a direction.")
                    if kind == "plan" and state["shots"]:
                        raise StudioError("This episode already has shots. Select a shot and direct a revision.")
                    if kind in {"see", "hear", "watch", "revise"} and not shot:
                        raise StudioError("Select the shot you want to work on.")
                    if kind == "revise" and payload.get("stage") not in {"see", "hear", "watch"}:
                        raise StudioError("Choose picture, voice or animation for this revision. Exact dialogue remains bound to the script.")
                    launch = self.reserve(db, context, state, pid, ep, kind, shot, message, payload)
                    self._message(state, "agent", "Preparing the episode's shot direction." if kind == "plan" else
                                  "Working on your direction." if kind in {"chat", "revise"} else f"Preparing {kind.upper()}. I will bring back the outcome for review.", jobId=launch["id"])
            self._save(db, pid, ep, state)
            result = {"ok": True, "projectId": pid, "episode": ep, "revision": state["revision"], "jobId": launch["id"] if launch else None}
            db.execute("INSERT INTO commands VALUES(?,?,?,?)", (pid, ep, command_id, json.dumps(result)))
        if launch:
            self.launch(launch)
        elif advance is not None:
            self.advance(pid, ep, advance)
        return result

    def advance(self, pid, ep, shot_id):
        """Prepare only the next outcome; approval remains an explicit human command."""
        snapshot = self.snapshot(pid, ep)
        state = snapshot["state"]
        shot = self.selected(state, shot_id) if shot_id else None
        if shot and self._stage(shot) == "done":
            index = state["shots"].index(shot) + 1
            if index >= len(state["shots"]):
                return
            shot = state["shots"][index]
        payload = {"projectId": pid, "episode": ep, "action": "continue", "commandId": uuid.uuid4().hex,
                   "expectedRevision": state["revision"], "shotId": shot["id"] if shot else ""}
        if shot and self._stage(shot) == "watch":
            payload["reviewId"] = shot["outcomes"]["request"]["id"]
        try:
            self.command(payload)
        except StudioError as exc:
            with self.ws.db() as db:
                db.execute("BEGIN IMMEDIATE")
                state = self._load(db, pid, ep)
                self._message(state, "agent", str(exc))
                self._save(db, pid, ep, state)

    def status_message(self, state, shot):
        if not state["budget"]["allowance"]:
            return "Approve one episode allowance and choose its project services. You can explore the project before connecting generation accounts."
        if not state["shots"]:
            return "Ready to prepare this script into directed shots, then show you its first keyframe."
        if not shot:
            return "Choose a shot. I can help with its picture, performance, camera and continuity."
        stage = self._stage(shot)
        if stage == "done":
            return "This shot's render is approved. Select the next shot when ready."
        item = self.artifact(shot, stage)
        if item and item["status"] == "candidate":
            return f"Review {stage.upper()} for {shot['id']}, then approve, reject or describe a change."
        return f"Ready to prepare {stage.upper()} for {shot['id']}."

    def _replace(self, shot, stage, item):
        outcomes = shot.setdefault("outcomes", {})
        if outcomes.get(stage):
            shot.setdefault("versions", []).append({"stage": stage, **outcomes[stage]})
        outcomes[stage] = item

    def watch_request(self, context, state, shot):
        pid = context["project"]["id"]
        for stage in ("see", "hear"):
            if stage == "hear" and not shot["dialogue"]:
                continue
            item = self.artifact(shot, stage)
            self.assert_artifact(pid, item)
            if item["status"] != "approved":
                raise StudioError(f"Approve {stage.upper()} before preparing the WATCH request.")
        binding = self.ws.binding(pid, "animation")
        if binding["model"] != "dreamina-seedance-2-5-260628":
            raise StudioError("The animation adapter is qualified for dreamina-seedance-2-5-260628. Choose that model or qualify another adapter first.", "model_unavailable")
        refs = [{"name": "Approved opening frame — begin from this composition", **shot["outcomes"]["see"]["files"][0]}]
        refs += self.assets(context, shot)
        files = [dict(r) for r in refs]
        audio = []
        duration = shot["duration"]
        if shot["dialogue"]:
            audio = shot["outcomes"]["hear"]["files"]
            files += audio
            length = self.transport.verify_media(self.ws.project_path(pid, audio[0]["path"]), "audio")
            duration = max(duration, math.ceil(length))
            if duration > 30:
                raise StudioError("This voice performance exceeds 30 seconds. Split the source into shorter shots before rendering.", "timing_limit")
        source = "\n".join(context["script"].splitlines()[shot["startLine"] - 1:shot["endLine"]])
        prompt = self._prompt(context, shot, "watch", refs)
        if audio:
            prompt += "\n@Audio1 is the approved voice performance. Match its exact words, speaker timing and lip sync. No extra dialogue."
        else:
            prompt += "\nNo spoken dialogue."
        prompt += "\nExact source:\n" + source
        ratio = context["project"].get("aspectRatio") or "16:9"
        if ratio not in {"16:9", "9:16", "1:1", "4:3", "3:4", "21:9"}:
            raise StudioError("Choose a supported project aspect ratio before animation.", "unsupported_format")
        return {"id": uuid.uuid4().hex, "status": "candidate", "files": files, "prompt": prompt,
                "images": refs, "audio": audio, "duration": duration, "ratio": ratio, "resolution": "480p", "binding": binding,
                "source": source, "shotHash": digest(Shot.model_validate({k: shot[k] for k in Shot.model_fields}).model_dump()),
                "dependencies": {s: (self.artifact(shot, s) or {}).get("id") for s in ("see", "hear")}}

    def reserve(self, db, context, state, pid, ep, kind, shot, message, payload):
        active = db.execute("SELECT id FROM jobs WHERE project=? AND episode=? AND state IN ('queued','running','pending','unknown')", (pid, ep)).fetchone()
        if active:
            raise StudioError("This episode already has work in progress. Resume or review that job before starting another.", "job_active")
        if kind in {"see", "hear"}:
            required = self._stage(shot)
            if required != kind:
                raise StudioError(f"Review the current {required.upper()} outcome or direct a revision first.")
        binding = self.ws.binding(pid, ROLE[kind])
        refs = self.assets(context, shot) if kind == "see" else []
        inputs = {}
        if kind == "hear":
            if not shot["dialogue"]:
                raise StudioError("This shot has no dialogue; continue to the WATCH request.")
            dialogue = []
            for line in shot["dialogue"]:
                voice_id = (self.ws.services(pid).get("voices", {}).get("casting", {}).get(line["speaker"]) or
                            context["assets"]["characters"][line["speaker"]].get("voiceId", ""))
                if not re.fullmatch(r"[A-Za-z0-9]{12,64}", voice_id):
                    raise StudioError(f"Set a valid ElevenLabs voice ID for {line['speaker']} in the project library.", "missing_voice")
                delivery = line.get("delivery", "neutral")
                spoken = line["text"] if delivery == "neutral" else f"[{delivery}] " + line["text"]
                dialogue.append({"text": spoken, "voice_id": voice_id})
            inputs["dialogue"] = dialogue
        if kind == "watch":
            request = self.artifact(shot, "request")
            self.assert_artifact(pid, request)
            if request["status"] != "approved" or request["id"] != payload.get("reviewId"):
                raise StudioError("Approve the current WATCH request before firing its render.", "approval_required")
            if binding != request["binding"]:
                raise StudioError("The service or key changed. Prepare and review an updated WATCH request.", "stale")
            if any((self.artifact(shot, s) or {}).get("id") != request["dependencies"][s] for s in ("see", "hear")):
                raise StudioError("The WATCH inputs changed. Review an updated request.", "stale")
            inputs["request"] = request
        cost = money(binding["estimateUsd"])
        budget = state["budget"]
        if budget["allowance"] - budget["committed"] - budget["reserved"] < cost:
            raise StudioError("The episode allowance does not cover this request. Increase it or adjust the project service estimate.", "budget_required")
        budget["reserved"] += cost
        job = {"id": uuid.uuid4().hex, "projectId": pid, "episode": ep, "kind": kind,
               "shotId": shot["id"] if shot else None, "shot": shot, "context": context, "sourceHash": context["sourceHash"],
               "binding": binding, "estimate": cost, "references": refs, "inputs": inputs,
               "direction": message, "stage": payload.get("stage", "see"), "reviews": self.review_learning(db, pid, state),
               "messages": state["messages"][-12:], "standard": STANDARD_PATH.read_text(), "standardHash": file_hash(STANDARD_PATH), "status": "queued", "createdAt": time.time(), "pid": os.getpid()}
        if kind == "see":
            index = next(i for i, s in enumerate(state["shots"]) if s["id"] == shot["id"])
            if index and state["shots"][index - 1]["scene"] == shot["scene"]:
                previous = state["shots"][index - 1]
                job["previousState"] = {k: previous[k] for k in ("id", "geography", "camera", "performance")}
                ending = (self.artifact(previous, "watch") or {}).get("ending")
                if ending and self.artifact(previous, "watch")["status"] == "approved":
                    self.assert_artifact(pid, {"files": [ending]})
                    job["references"].append({"name": "Previous approved ending — continuity state; use the NEW camera view for a cut", **ending})
                elif shot["transition"] == "continuation":
                    raise StudioError("A continuation needs the previous approved render's ending frame. Approve that shot or direct this opening as a cut.", "handoff_required")
        self._job(db, job)
        return job

    def review_learning(self, db, pid, state):
        records = []
        for row in db.execute("SELECT episode,data FROM production WHERE project=? ORDER BY rowid DESC LIMIT 12", (pid,)):
            records += [{**review, "episode": row["episode"]} for review in json.loads(row["data"])["reviews"][-10:]]
        return (records + state["reviews"][-10:])[-60:]

    def launch(self, job):
        with _RUNNING_LOCK:
            if job["id"] in _RUNNING:
                return
            _RUNNING.add(job["id"])
        if self.background:
            threading.Thread(target=self.run, args=(job["id"],), daemon=True, name="studio-project-job").start()
        else:
            self.run(job["id"])

    def run(self, job_id):
        try:
            with self.ws.db() as db:
                db.execute("BEGIN IMMEDIATE")
                job = json.loads(db.execute("SELECT data FROM jobs WHERE id=?", (job_id,)).fetchone()[0])
                if job["status"] == "completed":
                    return
                if job["status"] != "queued" and not (job.get("taskId") or job.get("imageUrl")):
                    raise StudioError("No provider task ID was confirmed. Check the provider account before resubmitting.", "submission_unknown")
                job.update(status="running", pid=os.getpid())
                self._job(db, job)
            binding, pid = job["binding"], job["projectId"]
            connection, key = self.ws.credential(binding["connectionId"], binding["revision"])
            context, kind = job["context"], job["kind"]
            if not job.get("taskId") and not job.get("imageUrl"):
                if self.ws.context(pid, job["episode"])["sourceHash"] != job["sourceHash"]:
                    raise StudioError("The project source changed before submission. Prepare from its current version.", "source_changed")
                self.assert_artifact(pid, {"files": job["references"]})
                if kind == "watch":
                    self.assert_artifact(pid, job["inputs"]["request"])
            out_dir = self.ws.project_path(pid, f"projects/{pid}/media")
            out_dir.mkdir(exist_ok=True)
            if kind in {"plan", "chat", "revise"}:
                data = {"project": context["project"], "bible": context["bible"], "assets": context["assets"],
                        "scriptLines": list(enumerate(context["script"].splitlines(), 1)),
                        "selectedShot": job["shot"], "direction": job["direction"], "stage": job["stage"],
                        "reviewLearning": job["reviews"], "conversation": job["messages"]}
                if len(json.dumps(data)) > 200000:
                    raise StudioError("This script exceeds the current director context limit. Split it into production sequences.", "context_limit")
                visual = [{"name": name, "path": item["anchor"]} for name, item in context["assets"]["characters"].items()
                          if item.get("anchor") and (not job["shot"] or name in job["shot"]["characters"])]
                visual += [{"name": item["name"], "path": item["image"]} for item in context["assets"]["locations"]
                           if item.get("image") and (not job["shot"] or item["name"] == job["shot"]["location"])]
                visual = [item for item in visual if self.ws.project_path(pid, item["path"]).is_file()][:8]
                data["attachedReferenceNames"] = [item["name"] for item in visual]
                result = self.transport.direct(connection, key, binding["model"], job["standard"], data, planning=kind == "plan",
                                               images=[self.ws.project_path(pid, item["path"]) for item in visual])
                if kind == "plan":
                    result["shots"] = self.validate_plan(context, result)
                else:
                    result = AgentReply.model_validate(result).model_dump()
                    if result["revisedShot"]:
                        result["revisedShot"] = self.validate_shot(context, result["revisedShot"])
                        old, new = job["shot"], result["revisedShot"]
                        if not old or any(old[k] != new[k] for k in ("id", "scene", "startLine", "endLine")) or [(d["speaker"], d["text"]) for d in old["dialogue"]] != [(d["speaker"], d["text"]) for d in new["dialogue"]]:
                            raise StudioError("The director changed protected script or shot identity. The proposal was not applied.", "invalid_revision")
                        if old["dialogue"] != new["dialogue"] and job["stage"] != "hear":
                            raise StudioError("The proposed visual revision changed the protected voice performance. Select voice to direct that change.", "invalid_revision")
            elif kind == "see":
                output = out_dir / f"{job_id}.png"
                prompt = self._prompt(context, job["shot"], "see", job["references"])
                if job.get("previousState"):
                    prompt += "\nIncoming continuity state:\n" + json.dumps(job["previousState"])
                if job.get("imageUrl"):
                    self.transport.download(job["imageUrl"], output)
                    self.transport.verify_media(output, "image")
                else:
                    def received(url):
                        job["imageUrl"] = url
                        with self.ws.db() as db:
                            self._job(db, job)
                    self.transport.image(connection, key, binding["model"], prompt,
                                         [self.ws.project_path(pid, r["path"]) for r in job["references"]], output, received=received)
                result = self.media_result(pid, output, prompt)
                result["references"] = job["references"]
            elif kind == "hear":
                output = out_dir / f"{job_id}.mp3"
                self.transport.voice(connection, key, binding["model"], job["inputs"]["dialogue"], output)
                result = self.media_result(pid, output, json.dumps(job["inputs"]["dialogue"], ensure_ascii=False))
            else:
                output = out_dir / f"{job_id}.mp4"
                request = job["inputs"]["request"]
                if not job.get("taskId"):
                    job["taskId"] = self.transport.video_submit(connection, key, binding["model"], request["prompt"],
                        [self.ws.project_path(pid, r["path"]) for r in request["images"]],
                        [self.ws.project_path(pid, r["path"]) for r in request["audio"]], request["duration"], ratio=request["ratio"])
                    with self.ws.db() as db:
                        job["status"] = "pending"
                        self._job(db, job)
                ready = self.transport.video_poll(connection, key, job["taskId"], output)
                if not ready:
                    # A persisted task can be polled by the UI or after a restart.
                    with self.ws.db() as db:
                        job.update(status="pending", message="The provider is rendering. Resume checks this same task without a new generation.")
                        self._job(db, job)
                    return
                result = self.media_result(pid, output, request["prompt"])
                result["requestId"] = request["id"]
                if request["audio"]:
                    # HEAR is the speech authority. Preserve the generated source,
                    # then replace its speech track with the exact approved audio.
                    import subprocess
                    conformed = out_dir / f"{job_id}-approved-voice.mp4"
                    voice_path = self.ws.project_path(pid, request["audio"][0]["path"])
                    try:
                        subprocess.run(["ffmpeg", "-v", "error", "-i", str(output), "-i", str(voice_path),
                                        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-af", "apad",
                                        "-c:a", "aac", "-shortest", "-y", str(conformed)], capture_output=True, timeout=90, check=True)
                        self.transport.verify_media(conformed, "video")
                    except Exception:
                        raise StudioError("The render returned but its approved voice could not be conformed. Resume this task to recover it.", "download_failed") from None
                    result["files"].insert(0, self.file_record(pid, conformed))
                    result["audioAuthority"] = {"source": request["audio"][0], "note": "Approved HEAR track conformed; review lip sync. Native music and effects are retained only in the original provider render."}
                ending = out_dir / f"{job_id}-ending.png"
                import subprocess
                try:
                    subprocess.run(["ffmpeg", "-v", "error", "-sseof", "-1", "-i", str(output), "-update", "1", "-y", str(ending)],
                                   capture_output=True, timeout=40, check=True)
                    self.transport.verify_media(ending, "image")
                    result["ending"] = self.file_record(pid, ending)
                    result["files"].append(result["ending"])
                except Exception:
                    result["continuityNote"] = "Ending frame extraction needs recovery before a continuation shot."
            self.complete(job, result)
        except Exception as exc:
            if "job" in locals():
                self.fail(job, exc)
        finally:
            with _RUNNING_LOCK:
                _RUNNING.discard(job_id)

    def file_record(self, pid, output):
        return {"path": str(Path(output).relative_to(self.ws.root)), "hash": file_hash(output)}

    def media_result(self, pid, output, prompt):
        return {"id": uuid.uuid4().hex, "status": "candidate", "files": [self.file_record(pid, output)], "prompt": prompt}

    def complete(self, job, result):
        pid, ep, kind = job["projectId"], job["episode"], job["kind"]
        with self.ws.db() as db:
            db.execute("BEGIN IMMEDIATE")
            current = json.loads(db.execute("SELECT data FROM jobs WHERE id=?", (job["id"],)).fetchone()[0])
            if current["status"] == "completed":
                return
            state = self._load(db, pid, ep)
            if self.ws.context(pid, ep)["sourceHash"] != job["sourceHash"]:
                state["history"].append({"jobId": job["id"], "reason": "Source changed while generating", "result": result})
                self._message(state, "agent", "The source changed during generation. I kept the result in history without replacing current work.")
            elif kind == "plan":
                state["shots"] = [{**shot, "outcomes": {}, "versions": [], "sourceSignature": self.source_signature(job["context"], shot)} for shot in result["shots"]]
                state["sourceHash"] = job["sourceHash"]
                state["scriptHash"] = digest(job["context"]["script"])
                self._message(state, "agent", result["message"] + " Your shot plan is in the pipeline. The next outcome is SEE.")
            elif kind in {"chat", "revise"}:
                new = result.get("revisedShot")
                if new:
                    shot = self.selected(state, job["shotId"])
                    if digest(shot) != digest(job["shot"]):
                        raise StudioError("The shot changed while the director was working. Send the direction against its current version.", "stale")
                    state["history"].append({"shot": json.loads(json.dumps(shot)), "jobId": job["id"]})
                    # Voice is script-bound and preserved for a visual revision.
                    # Other shots, including approved downstream work, stay intact.
                    changed = {k for k in Shot.model_fields if new[k] != shot[k]}
                    if changed:
                        reset = {"request", "watch"}
                        if "dialogue" in changed:
                            reset.add("hear")
                        if changed - {"watchPrompt", "duration", "dialogue"}:
                            reset.add("see")
                        for stage in reset:
                            if stage in shot["outcomes"]:
                                shot["versions"].append({"stage": stage, **shot["outcomes"].pop(stage)})
                        shot.update(new)
                        shot["sourceSignature"] = self.source_signature(job["context"], new)
                        for downstream in state["shots"][state["shots"].index(shot) + 1:]:
                            if downstream["scene"] == shot["scene"]:
                                downstream["continuityReview"] = f"Review the join after the revision to {shot['id']}. Accepted files have been preserved."
                    self._message(state, "agent", result["message"] + " The direction is now in this shot's prompts. Its next outcome will use these changes.")
                else:
                    self._message(state, "agent", result["message"])
            else:
                shot = self.selected(state, job["shotId"])
                result.update(binding=job["binding"], sourceHash=job["sourceHash"], standardHash=job["standardHash"], jobId=job["id"])
                self._replace(shot, kind, result)
                self._message(state, "agent", f"{kind.upper()} is ready for {shot['id']}. Review it below before approving.")
            state["budget"]["reserved"] -= job["estimate"]
            state["budget"]["committed"] += job["estimate"]
            job.update(status="completed", completedAt=time.time(), message="Outcome ready for review.")
            self._job(db, job)
            self._save(db, pid, ep, state)
        if kind == "plan":
            self.advance(pid, ep, result["shots"][0]["id"])
        elif kind in {"chat", "revise"} and result.get("revisedShot"):
            self.advance(pid, ep, job["shotId"])

    def fail(self, job, exc):
        error = exc if isinstance(exc, StudioError) else StudioError("The operation could not finish. Your current outcomes are preserved; check the job before retrying.", "operation_failed")
        with self.ws.db() as db:
            db.execute("BEGIN IMMEDIATE")
            current = json.loads(db.execute("SELECT data FROM jobs WHERE id=?", (job["id"],)).fetchone()[0])
            if current["status"] in {"completed", "failed"}:
                return
            # A known task remains recoverable with its original connection revision.
            unknown = (error.code in {"submission_unknown", "download_failed", "provider_offline"} or bool(job.get("taskId") or job.get("imageUrl"))) and error.code != "generation_failed"
            job.update(status=("pending" if job.get("taskId") or job.get("imageUrl") else "unknown") if unknown else "failed", code=error.code, message=str(error))
            state = self._load(db, job["projectId"], job["episode"])
            if not unknown:
                state["budget"]["reserved"] -= job["estimate"]
                if error.code not in {"authentication_failed", "permission_required", "model_unavailable", "missing_key", "vault_unavailable"}:
                    state["budget"]["committed"] += job["estimate"]
            self._message(state, "agent", str(error), jobId=job["id"])
            self._job(db, job)
            self._save(db, job["projectId"], job["episode"], state)
