"""Durable, bounded WATCH preparation and submission reconciliation.

Only declared local preparation tools are replayable. Provider submission is never
replayed by this coordinator; its saved transport evidence must be reconciled first.
The existing render engine remains the authority for approvals and spend tokens.
"""
from __future__ import annotations

import contextlib
import contextvars
import functools
import hashlib
import inspect
import json
import os
import pathlib
import threading
import time
import uuid

import cb_db

ACTIVE = contextvars.ContextVar("production_operation", default=None)
PREPARATION = {"prepare-render", "retake-render"}
ACTIVE_STATES = {"queued", "preparing", "diagnosing", "repairing", "validating"}
TERMINAL = {"awaiting-spend-approval", "reviewing", "completed", "cancelled"}
MAX_ATTEMPTS = 2
DEADLINE_SECONDS = 1800
LEASE_SECONDS = 60


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS production_operations (
        operation_id TEXT PRIMARY KEY, operation_key TEXT UNIQUE NOT NULL,
        data_json TEXT NOT NULL, updated_at REAL NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS production_operation_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT, operation_id TEXT NOT NULL,
        at REAL NOT NULL, data_json TEXT NOT NULL)""")


@contextlib.contextmanager
def transaction(root):
    with cb_db.transaction(root) as conn:
        _schema(conn)
        yield conn


def _read(conn, operation_id):
    row = conn.execute("SELECT data_json FROM production_operations WHERE operation_id=?",
                       (operation_id,)).fetchone()
    if not row:
        raise ValueError("Production operation was not found")
    return json.loads(row[0])


def _write(conn, operation, event=None):
    operation["updatedAt"] = time.time()
    conn.execute("UPDATE production_operations SET data_json=?, updated_at=? WHERE operation_id=?",
                 (json.dumps(operation), operation["updatedAt"], operation["operationId"]))
    if event:
        conn.execute("INSERT INTO production_operation_events(operation_id,at,data_json) VALUES(?,?,?)",
                     (operation["operationId"], time.time(), json.dumps(event, default=str)))


def get(root, operation_id):
    with transaction(root) as conn:
        return _read(conn, operation_id)


def all_operations(root):
    with transaction(root) as conn:
        return [json.loads(row[0]) for row in conn.execute(
            "SELECT data_json FROM production_operations ORDER BY updated_at DESC LIMIT 500")]


def events(root, operation_id):
    with transaction(root) as conn:
        return [{"at": row[0], **json.loads(row[1])} for row in conn.execute(
            "SELECT at,data_json FROM production_operation_events WHERE operation_id=? ORDER BY event_id",
            (operation_id,))]


def change(root, operation_id, state, message, **fields):
    with transaction(root) as conn:
        op = _read(conn, operation_id)
        updates = {**fields, "state": state, "message": message}
        if all(op.get(key) == value for key, value in updates.items()):
            return op
        op.update(fields, state=state, message=message)
        _write(conn, op, {"state": state, "message": message, **fields})
        return op


def describe(args):
    """Allowlist concrete WATCH commands; arbitrary CLI arguments are never resumed."""
    args = list(args)
    if len(args) >= 4 and args[0] == "cb_studio_director.py" and args[1] in PREPARATION:
        retake = args[1] == "retake-render"
        if (retake and len(args) != 7) or (not retake and len(args) not in {4, 5}):
            return None
        return {"kind": args[1], "scene": args[2], "shotId": args[3],
                "episode": args[5] if retake else args[4] if len(args) == 5 else "Ep1",
                "correction": args[4] if retake else "",
                "sourceBatchId": args[6] if retake else None, "args": args,
                "spendingAuthority": {"media": False}}
    if len(args) >= 5 and args[:2] == ["cb_render.py", "fire"] and "--spend-token" in args:
        token_index = args.index("--spend-token") + 1
        if token_index >= len(args):
            return None
        return {"kind": "submit-watch", "scene": args[2], "shotId": args[3],
                "episode": args[4], "correction": "", "args": args,
                "spendingAuthority": {"media": True, "tokenHash": digest(args[token_index])}}
    return None


def package_snapshot(root, descriptor):
    path = pathlib.Path(root) / "cb-output" / (
        f"{descriptor['episode']}_scene{descriptor['scene']}_production_package.json")
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def protected_inputs(package, shot_id):
    """Actual approved dependencies, including current file bytes, never renewed hashes."""
    shot = next((s for s in package.get("shots", []) if s.get("shotId") == shot_id), {})
    ledger = next((s for s in package.get("continuityLedger", []) if s.get("shotId") == shot_id),
                  package.get("ledger", {}))
    fields = {key: ledger.get(key) for key in ("keyframeApproval", "voiceApproval", "voPath", "voTimingPath")}
    fields["story"] = {key: shot.get(key) for key in
                       ("durationSec", "dialogueLines", "charactersInFrame", "beatIds", "beatCode")}
    file_hashes = {}
    for item in (ledger.get("keyframeApproval") or {}, ledger.get("voiceApproval") or {},
                 {"path": ledger.get("voPath")}, {"path": ledger.get("voTimingPath")}):
        path = item.get("path")
        if path:
            try:
                file_hashes[str(path)] = hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
            except OSError:
                file_hashes[str(path)] = "unavailable"
    fields["fileHashes"] = file_hashes
    # Copy mutable package values so an in-process writer cannot alter the evidence.
    return json.loads(json.dumps(fields, default=str))


def source_snapshot(root, descriptor, package):
    inputs = protected_inputs(package, descriptor["shotId"])
    plate_path = pathlib.Path(root) / "cb-output" / (
        f"{descriptor['episode']}_scenelook_scene{descriptor['scene']}.json")
    try:
        record = json.loads(plate_path.read_text())
    except (OSError, ValueError):
        record = {}
    approved = record.get("approved") or {}
    inputs["scenePlate"] = approved
    if approved.get("path"):
        try:
            inputs["scenePlateBytes"] = hashlib.sha256(pathlib.Path(approved["path"]).read_bytes()).hexdigest()
        except OSError:
            inputs["scenePlateBytes"] = "unavailable"
    return inputs


def _ledger(package, shot_id):
    return next((row for row in package.get("continuityLedger", []) if row.get("shotId") == shot_id),
                package.get("ledger", {}))


def authored_snapshot(root, descriptor, package):
    """Current semantic inputs, excluding histories, timestamps and compiled prose."""
    shot = next((row for row in package.get("shots", []) if row.get("shotId") == descriptor["shotId"]), {})
    ledger = _ledger(package, descriptor["shotId"])
    direction = {}
    for stage in ("cinematography", "animation"):
        work = (ledger.get("departmentWork") or {}).get(stage) or {}
        record = work.get("candidate") or work.get("approved") or {}
        # Capture typed semantic and reference changes; never use record generation
        # time or compiled provider prose as a new producer instruction.
        direction[stage] = {key: value for key, value in (record.get("output") or {}).items()
                            if key not in {"providerPrompt", "compiledPrompt", "promptDirectorEvidence"}}
    roles = ledger.get("additionalAnimationReferenceRoles") or []
    registry_path = pathlib.Path(root) / "cb-output/asset-registry/assets.json"
    try:
        assets = json.loads(registry_path.read_text()).get("assets", [])
    except (OSError, ValueError):
        assets = []
    references = [{key: item.get(key) for key in ("assetId", "id", "path", "sha256", "hash", "role", "status")}
        for item in assets if item.get("episode") == descriptor["episode"] and
        str(item.get("scene")) == str(descriptor["scene"]) and
        item.get("shotId") in (None, descriptor["shotId"]) and item.get("role") in roles]
    for reference in references:
        try:
            reference["currentBytesHash"] = hashlib.sha256(pathlib.Path(reference["path"]).read_bytes()).hexdigest()
        except (OSError, TypeError):
            reference["currentBytesHash"] = "unavailable"
    return {"shot": {key: value for key, value in shot.items()
                      if key not in {"seedancePrompt", "keyframePrompt", "compiledPrompt", "promptDirectorEvidence"}},
            "source": {key: package.get(key) for key in ("revision", "sourceLineage", "sourceStoryboard",
                "sourceScript", "sceneCoverage", "creativeDirectingStandardVersion")},
            "feedback": (ledger.get("watchDirectorFeedback") or {}).get("text"),
            "workingPrompt": (ledger.get("workingSeedancePrompt") or {}).get("text"),
            "workingVoice": (ledger.get("workingVoice") or {}).get("lines"),
            "referenceRoles": roles, "resolvedReferences": sorted(references, key=lambda item: digest(item)),
            "specialistDirection": direction}


def request_fingerprint(root, descriptor, package):
    return digest({"sources": source_snapshot(root, descriptor, package),
                   "authored": authored_snapshot(root, descriptor, package)})


def _changed_bytes_without_new_approval(previous, current):
    old = dict(previous or {})
    new = dict(current or {})
    old_bytes = (old.pop("fileHashes", None), old.pop("scenePlateBytes", None))
    new_bytes = (new.pop("fileHashes", None), new.pop("scenePlateBytes", None))
    return old == new and old_bytes != new_bytes


def _current_cost_decision(conn, op, package):
    pending = _ledger(package, op["shotId"]).get("pendingSpendAuth") or {}
    if not pending.get("token") or digest(pending) != op.get("spendDecisionHash"):
        return False
    auth = conn.execute("SELECT status FROM spend_authorizations WHERE token=?", (pending["token"],)).fetchone()
    return bool(auth and auth["status"] == "issued")


def register(root, args, job_id=None):
    descriptor = describe(args)
    if not descriptor:
        return None
    package = package_snapshot(root, descriptor)
    request_key = digest(descriptor)
    fingerprint = request_fingerprint(root, descriptor, package)
    with transaction(root) as conn:
        matching = [json.loads(row[0]) for row in conn.execute("SELECT data_json FROM production_operations")]
        matching = [op for op in matching if (op.get("requestKey") or digest(describe(op["args"]))) == request_key]
        previous = max(matching, key=lambda op: op["createdAt"], default=None)
        if previous:
            if (descriptor["kind"] not in PREPARATION or worker_alive(previous) or
                    previous["state"] in ACTIVE_STATES | {"reconciling-submission", "submitting", "rendering"}):
                return previous
            if previous.get("inputsCaptured") and _changed_bytes_without_new_approval(
                    previous.get("approvedSources"), source_snapshot(root, descriptor, package)):
                previous.update(state="needs-attention", message="Approved asset bytes changed without a new approval. Review the changed input before resuming.")
                _write(conn, previous, {"state": "needs-attention", "message": previous["message"]})
                return previous
            unchanged = fingerprint == previous.get("resumeInputFingerprint", previous.get("requestFingerprint"))
            if unchanged and previous["state"] != "awaiting-spend-approval":
                return previous  # In particular: no new budget for the same failed request.
            if unchanged and _current_cost_decision(conn, previous, package):
                return previous
        # A changed authored input or retired cost decision starts one linked,
        # bounded preparation lifecycle. The transaction collapses simultaneous
        # callers onto its queued row without replenishing the predecessor's budget.
        key = digest([request_key, fingerprint, previous["operationId"] if previous else None])
        now = time.time()
        operation_id = uuid.uuid4().hex
        op = {**descriptor, "operationId": operation_id, "operationKey": key,
              "requestKey": request_key, "requestFingerprint": fingerprint,
              "resumeInputFingerprint": fingerprint,
              "predecessorOperationId": previous["operationId"] if previous else None,
              "jobId": (job_id if job_id and (not previous or job_id != previous.get("jobId")) else "production_" + operation_id),
              "state": "queued", "message": "Preparation queued" if descriptor["kind"] in PREPARATION else "Authorized submission queued",
              "createdAt": now, "deadlineAt": now + DEADLINE_SECONDS,
              "checkpoints": [], "attempts": {}, "owner": None,
              "approvedSources": source_snapshot(root, descriptor, package),
              "providerTaskIds": [], "mediaSubmitted": False}
        conn.execute("INSERT INTO production_operations VALUES(?,?,?,?)", (op["operationId"], key, json.dumps(op), now))
        _write(conn, op, {"state": "queued", "request": descriptor,
                          "approvedSources": op["approvedSources"], "requestFingerprint": fingerprint,
                          "predecessorOperationId": op["predecessorOperationId"]})
        return op


def authorize_text_retry(root, operation_id):
    """One explicit producer retry cycle; duplicate starts never reset this budget."""
    with transaction(root) as conn:
        op = _read(conn, operation_id)
        failure = op.get("failure") or {}
        name = failure.get("checkpoint")
        if (op["kind"] not in PREPARATION or op["state"] != "needs-attention" or
                failure.get("recovery") != "retry-prompt-director" or
                int(op.get("manualTextRetries") or 0) >= 1 or time.time() >= op["deadlineAt"]):
            raise RuntimeError("This saved issue needs an input or service repair before another retry cycle.")
        previous = dict(op["attempts"])
        op["attempts"][name] = 0
        op["manualTextRetries"] = 1
        _write(conn, op, {"action": "producer-authorized-text-retry", "previousAttempts": previous,
                         "checkpoint": name, "mediaAuthority": False})
        return op


def worker_alive(op):
    if not op.get("owner"):
        return False
    pid = op.get("workerPid")
    if not pid:
        return float(op.get("leaseUntil") or 0) >= time.time()
    # A missed heartbeat is not proof a local worker died. Keep its ownership
    # while the PID exists; the preparation runner enforces the overall deadline.
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def reserve(root, operation_id, job_id, *, resume=False):
    """One process gets the launch reservation, even with two Studio servers."""
    with transaction(root) as conn:
        op = _read(conn, operation_id)
        if worker_alive(op) or (op["state"] in TERMINAL and not (resume and op["state"] == "cancelled")):
            return op, False
        if op["state"] in {"reconciling-submission", "submitting", "rendering"}:
            return op, False
        if op["state"] == "needs-attention" and not resume:
            return op, False
        if time.time() >= op["deadlineAt"]:
            op.update(state="needs-attention", message="Preparation deadline reached. Review the saved evidence before starting a new request.")
            _write(conn, op, {"state": op["state"], "message": op["message"]})
            return op, False
        op.update(owner="dispatch:" + uuid.uuid4().hex, workerPid=None,
                  leaseUntil=time.time() + LEASE_SECONDS, jobId=op.get("jobId") or job_id,
                  state="queued", message="Resuming saved preparation" if resume else op["message"])
        _write(conn, op, {"state": "queued", "jobId": op["jobId"], "resume": resume})
        return op, True


@contextlib.contextmanager
def claim(root, operation_id):
    owner = uuid.uuid4().hex
    with transaction(root) as conn:
        op = _read(conn, operation_id)
        if worker_alive(op) and not str(op.get("owner")).startswith("dispatch:"):
            raise RuntimeError("This production operation is already running")
        if op["state"] in TERMINAL or op["state"] in {"reconciling-submission", "rendering", "submitting"}:
            raise RuntimeError("This operation requires its saved decision or submission reconciliation")
        op.update(owner=owner, workerPid=os.getpid(), leaseUntil=time.time() + LEASE_SECONDS)
        _write(conn, op, {"workerClaimed": owner, "pid": os.getpid()})
    stop = threading.Event()
    def heartbeat():
        while not stop.wait(LEASE_SECONDS / 3):
            with transaction(root) as conn:
                current = _read(conn, operation_id)
                if current.get("owner") != owner:
                    return
                current["leaseUntil"] = time.time() + LEASE_SECONDS
                _write(conn, current)
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    token = ACTIVE.set((root, operation_id))
    try:
        yield op
    finally:
        ACTIVE.reset(token)
        stop.set()
        thread.join(timeout=2)
        with transaction(root) as conn:
            current = _read(conn, operation_id)
            if current.get("owner") == owner:
                current.update(owner=None, workerPid=None, leaseUntil=0)
                _write(conn, current)


def checkpoint(name, message, action, *, retry_timeout=False, repeat=False):
    active = ACTIVE.get()
    if not active:
        return action()
    root, operation_id = active
    op = get(root, operation_id)
    if name in op["checkpoints"] and not repeat:
        return
    while True:
        op = get(root, operation_id)
        count = int(op["attempts"].get(name, 0))
        if time.time() >= op["deadlineAt"] or (retry_timeout and count >= MAX_ATTEMPTS):
            raise RuntimeError(f"{message}: recovery limit reached. Saved correction retained; inspect the failed checkpoint before resuming.")
        counts = {**op["attempts"], name: count + 1}
        change(root, operation_id, "validating" if retry_timeout else "preparing",
               message, checkpoint=name, attempts=counts)
        try:
            result = action()
        except Exception as exc:
            detail = str(exc)
            transient = retry_timeout and "prompt_director" in detail.lower() and (
                "timed out" in detail.lower() or "apitimeouterror" in detail.lower())
            failure = {
                "checkpoint": name, "type": type(exc).__name__, "detail": detail,
                "fingerprint": digest([name, type(exc).__name__, detail]),
                "recovery": "retry-prompt-director" if transient else "requires-input-repair"}
            inner_failure = get(root, operation_id).get("failure") or {}
            if (name == "prepare" and inner_failure.get("checkpoint") != name and
                    (inner_failure.get("detail") == detail or "recovery limit reached" in detail)):
                failure = inner_failure  # Keep the actual failed stage, not its caller.
            change(root, operation_id, "diagnosing", detail, failure=failure)
            if not transient or count + 1 >= MAX_ATTEMPTS:
                raise
            change(root, operation_id, "repairing", "Retrying final direction review; approved media retained")
            time.sleep(min(2 ** count, 4))
        else:
            op = get(root, operation_id)
            done = list(dict.fromkeys(op["checkpoints"] + [name]))
            change(root, operation_id, "preparing", message + " — checked", checkpoints=done)
            return result


def protect_preparation(fn):
    signature = inspect.signature(fn)
    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        if ACTIVE.get():
            return fn(*args, **kwargs)
        import cb_render
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        values = bound.arguments
        scene, shot, episode = values["scene"], values["shot_id"], values["episode"]
        command = fn.__name__.replace("_", "-")
        argv = ["cb_studio_director.py", command, str(scene), shot]
        if command == "retake-render":
            argv += [values["correction"], episode, values.get("expected_batch_id")]
        else:
            argv += [episode]
        root = cb_render.HERE.parent
        operation_id = os.environ.get("CB_PRODUCTION_OPERATION_ID")
        op = get(root, operation_id) if operation_id else register(root, argv)
        if op["args"] != argv:
            raise RuntimeError("Operation arguments changed; refusing an unrelated recovery")
        if op["state"] == "awaiting-spend-approval":
            package, _ = cb_render.load_pkg(scene, episode)
            if cb_render._ledger(package, shot).get("pendingSpendAuth"):
                return
            raise RuntimeError("The saved cost decision changed. Prepare a current request before firing.")
        with claim(root, op["operationId"]):
            failure_scope = "input-validation"
            try:
                with cb_db.scene_lease(root, episode, scene, "recovery:" + op["operationId"],
                                       wait_seconds=240, on_wait=values.get("log", print)):
                    package, _ = cb_render.load_pkg(scene, episode)
                    before = source_snapshot(root, op, package)
                    if op.get("inputsCaptured") and before != op["approvedSources"]:
                        raise RuntimeError("Approved inputs changed since this operation began. Prepare a new request against the current SEE and HEAR decisions.")
                    change(root, op["operationId"], "preparing", "Checking saved production inputs",
                           approvedSources=before, inputsCaptured=True,
                           resumeInputFingerprint=request_fingerprint(root, op, package))
                    failure_scope = "preparation"
                    result = checkpoint("prepare", "Checking animation request", lambda: fn(*args, **kwargs),
                                        retry_timeout=command == "prepare-render", repeat=True)
                    failure_scope = "outcome-validation"
                    package, _ = cb_render.load_pkg(scene, episode)
                    if source_snapshot(root, op, package) != before:
                        raise RuntimeError("Protected SEE, HEAR or story inputs changed during WATCH recovery. Review the changed input before continuing.")
                    pending = cb_render._ledger(package, shot).get("pendingSpendAuth") or {}
                    if not pending:
                        raise RuntimeError("Preparation ended without a persisted cost decision")
                    change(root, op["operationId"], "awaiting-spend-approval", "Review cost & fire",
                           payloadHash=pending.get("envelopeHash"),
                           referenceBindings=(pending.get("envelope") or {}).get("referenceBindings"),
                           spendDecisionHash=digest(pending), mediaSubmitted=False,
                           resumeInputFingerprint=request_fingerprint(root, op, package))
                    return result
            except Exception as exc:
                uncertain = any(word in str(exc).lower() for word in ("submission outcome is unknown", "unresolved provider"))
                fields = {} if failure_scope == "preparation" else {"failure": {
                    "checkpoint": failure_scope, "detail": str(exc), "type": type(exc).__name__,
                    "recovery": "requires-input-repair"}}
                try:
                    current_package, _ = cb_render.load_pkg(scene, episode)
                    fields["resumeInputFingerprint"] = request_fingerprint(root, op, current_package)
                except Exception:
                    pass  # Preserve the last captured fingerprint if package reading failed.
                change(root, op["operationId"], "reconciling-submission" if uncertain else "needs-attention",
                       str(exc), failureDetail=str(exc), mediaSubmitted=None if uncertain else False, **fields)
                raise
    return wrapped


def reconcile(root, operation_id, *, worker_running=False):
    """Read only the engine's durable provider transport; never call a submit route."""
    op = get(root, operation_id)
    package = package_snapshot(root, op)
    ledger = next((s for s in package.get("continuityLedger", []) if s.get("shotId") == op["shotId"]), {})
    tasks, transports = [], []
    def visit(value):
        if isinstance(value, dict):
            if value.get("providerTaskId"):
                tasks.append(str(value["providerTaskId"]))
                transports.append({k: value.get(k) for k in ("providerTaskId", "status", "lastProviderEvent")})
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    # Evidence is restricted to the token's batch, never an older accepted take.
    batch = ledger.get("batch") or {}
    token_hash = (op.get("spendingAuthority") or {}).get("tokenHash")
    batch_token = batch.get("spendToken") or batch.get("spendAuthToken") or batch.get("token")
    with transaction(root) as conn:
        authorizations = [dict(row) for row in conn.execute(
            "SELECT token,batch_id,status FROM spend_authorizations WHERE episode=? AND scene=? AND shot_id=?",
            (op["episode"], op["scene"], op["shotId"]))]
    matching = next((row for row in authorizations if digest(row["token"]) == token_hash), None)
    batch_id = batch.get("batchId") or batch.get("id")
    claimed_batch_id = matching.get("batch_id") if matching else None
    batch_matches = bool(claimed_batch_id and batch_id and claimed_batch_id == batch_id and
                         matching.get("status") in {"claimed", "completed"})
    if batch_id and batch_token and digest(batch_token) == token_hash:
        batch_matches = True
    if batch_matches:
        visit(batch)
    returned_batch_matches = bool(batch_matches and batch.get("status") == "complete" and
                                  ledger.get("batchId") == batch_id)
    outputs = [str(p) for p in (ledger.get("candidatePaths") or []) if p and pathlib.Path(p).is_file()
               and pathlib.Path(p).stat().st_size > 0] if returned_batch_matches else []
    state = "reviewing" if outputs and ledger.get("status") == "candidates-pending" else (
        "rendering" if worker_running and tasks else "submitting" if worker_running else "reconciling-submission")
    message = "Returned media is saved and awaiting your review" if state == "reviewing" else (
        "Provider task accepted; awaiting returned media" if state == "rendering" else
        "Checking the authorized request and provider submission" if state == "submitting" else
        "Provider task recorded; reconcile its current outcome before any further submission" if tasks else
        "Submission outcome is unconfirmed. Inspect provider submission evidence before retrying; automatic resubmission is blocked.")
    ownership = {} if worker_running else {"owner": None, "workerPid": None, "leaseUntil": 0}
    return change(root, operation_id, state, message, providerTaskIds=sorted(set(tasks)),
                  transportEvidence=transports, returnedPaths=outputs,
                  mediaSubmitted=True if tasks or outputs else None, **ownership)


def public(op):
    data = {key: op.get(key) for key in ("operationId", "jobId", "kind", "episode", "scene", "shotId",
            "state", "message", "correction", "checkpoint", "attempts", "createdAt", "updatedAt",
            "deadlineAt", "providerTaskIds", "mediaSubmitted", "failureDetail")}
    failure = op.get("failure") or {}
    data["canRetryTextReview"] = (op["state"] == "needs-attention" and
        failure.get("recovery") == "retry-prompt-director" and
        not op.get("manualTextRetries") and time.time() < op["deadlineAt"])
    return data


def recoverable(root):
    """Recover lost ownership without taking over a live child after server restart."""
    ready = []
    for op in all_operations(root):
        if worker_alive(op) or op["state"] in TERMINAL or op["state"] == "needs-attention":
            continue
        if op["kind"] == "submit-watch" or op["state"] == "reconciling-submission":
            reconcile(root, op["operationId"])
        elif op["state"] in ACTIVE_STATES:
            change(root, op["operationId"], "queued", "Recovering saved preparation after worker interruption",
                   owner=None, workerPid=None, leaseUntil=0)
            ready.append(get(root, op["operationId"]))
    return ready
