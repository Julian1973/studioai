"""Actual Studio HTTP entrypoints and CLI coordinator, with all providers replaced."""
import copy
import http.client
import importlib.util
import json
import os
from pathlib import Path
import threading
import time
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

import cb_db
import cb_recovery as C
import cb_render as R
import cb_studio_director as D


@pytest.fixture
def world(tmp_path, monkeypatch):
    root = tmp_path
    path = root / "cb-output/Ep3_scene1_production_package.json"
    path.parent.mkdir()
    voice = root / "approved.wav"
    image = root / "approved.png"
    voice.write_bytes(b"unchanged-audio")
    image.write_bytes(b"unchanged-image")
    ledger = {"shotId": "S1.SH2", "status": "candidates-pending", "batchId": "batch1",
              "candidatePaths": ["returned-take"], "pendingSpendAuth": None,
              "voPath": str(voice), "voiceApproval": {"hash": "audio", "path": str(voice)},
              "keyframeApproval": {"hash": "image", "path": str(image)}}
    pkg = {"revision": 1, "shots": [{"shotId": "S1.SH2", "durationSec": 6,
            "dialogueLines": [{"exactText": "Keep these words."}], "charactersInFrame": ["Bo"]}],
           "continuityLedger": [ledger]}
    calls = []
    def save(*args):
        path.write_text(json.dumps(pkg))
    save()
    monkeypatch.setattr(R, "HERE", root / "engine")
    monkeypatch.setattr(R, "load_pkg", lambda *a: (pkg, path))
    monkeypatch.setattr(R, "_ledger", lambda *a: ledger)
    monkeypatch.setattr(R, "_save", save)
    monkeypatch.setattr(R, "save_watch_director_feedback", lambda *a, **k: calls.append("feedback"))
    def reject(*args, **kwargs):
        calls.append("archive")
        ledger.update(status="designed", candidatePaths=None, batchId=None)
        save()
    monkeypatch.setattr(R, "reject_shot", reject)
    monkeypatch.setattr(R, "restore_seedance_working", lambda *a: calls.append("clear"))
    monkeypatch.setattr(R, "prepare_department", lambda scene, stage, *a: calls.append(stage))
    monkeypatch.setattr(R, "recompile_animation_candidate", lambda *a: calls.append("compile"))
    def prepare(*a):
        calls.append("seal")
        ledger["pendingSpendAuth"] = {"token": "sealed", "envelopeHash": "payload-digest"}
        save()
    monkeypatch.setattr(D, "prepare_render", prepare)
    return root, pkg, ledger, calls, save


def load_server(root, monkeypatch, name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name("serve.py"))
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)
    monkeypatch.setattr(server, "ROOT", root)
    monkeypatch.setattr(server, "_is_stale", lambda: False)
    monkeypatch.setattr(server, "_clear_director_session_cache", lambda **k: None)
    # Exercise real routing and JSON validation without involving browser credentials.
    monkeypatch.setattr(server.H, "_authorize", lambda self, **kwargs: True)
    monkeypatch.setattr(server.H, "_valid_post_origin", lambda self: True)
    return server


class Http:
    def __init__(self, server):
        self.httpd = server.http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.H)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
    def __enter__(self):
        self.thread.start()
        return self
    def __exit__(self, *args):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(3)
    def request(self, method, path, body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=10)
        connection.request(method, path, body=json.dumps(body) if body is not None else None,
                           headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result


RETAKE = {"cmd": "retake", "scene": "1", "episode": "Ep3", "shotId": "S1.SH2",
          "correction": "Keep SEE and HEAR; fix object motion", "expectedBatchId": "batch1"}
ARGS = ["cb_studio_director.py", "retake-render", "1", "S1.SH2",
        RETAKE["correction"], "Ep3", "batch1"]
PREPARE_ARGS = ["cb_studio_director.py", "prepare-render", "1", "S1.SH2", "Ep3"]


def sealed_operation(world, args=PREPARE_ARGS):
    root, pkg, ledger, calls, save = world
    operation = C.register(root, args, "original-preparation")
    auth = {"token": "a"*32, "bindingHash": "binding", "envelopeHash": "envelope",
            "envelope": {"candidateCount": 1}, "disclosure": {"candidateCount": 1}}
    cb_db.issue_spend_authorization(root, "Ep3", "1", "S1.SH2", auth)
    ledger["pendingSpendAuth"] = auth
    save()
    operation = C.change(root, operation["operationId"], "awaiting-spend-approval", "Review cost & fire",
        spendDecisionHash=C.digest(auth), inputsCaptured=True,
        resumeInputFingerprint=C.request_fingerprint(root, operation, pkg))
    return operation, auth


@pytest.mark.parametrize("change_input", ["director-card", "feedback", "specialist-reference", "additional-role"])
def test_authored_watch_change_starts_one_new_bounded_preparation(world, change_input):
    root, pkg, ledger, calls, save = world
    previous, auth = sealed_operation(world)
    assert C.register(root, PREPARE_ARGS)["operationId"] == previous["operationId"]
    if change_input == "director-card":
        pkg["shots"][0]["directorCard"] = {"views": [{"viewId": "revised", "action": "New intended action"}]}
    elif change_input == "feedback":
        ledger["watchDirectorFeedback"] = {"text": "Keep the cup on the table", "savedAt": "now"}
        pkg["shots"][0]["watchDirectorFeedbackApproved"] = "Keep the cup on the table"
    elif change_input == "specialist-reference":
        ledger["departmentWork"] = {"animation": {"candidate": {"output": {
            "referenceContract": [{"role": "geography-only", "path": "new-approved-angle.png"}]}}}}
    else:
        ledger["additionalAnimationReferenceRoles"] = ["location:reverse"]
    ledger["pendingSpendAuth"] = None
    save()
    def request(_):
        op = C.register(root, PREPARE_ARGS, "replacement-job")
        return C.reserve(root, op["operationId"], "replacement-job", resume=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(request, range(4)))
    ids = {op["operationId"] for op, launched in results}
    assert len(ids) == 1 and previous["operationId"] not in ids
    assert sum(launched for op, launched in results) == 1
    assert results[0][0]["predecessorOperationId"] == previous["operationId"]
    assert results[0][0]["requestFingerprint"] != previous["requestFingerprint"]


@pytest.mark.parametrize("decision_change", ["missing", "consumed", "replaced"])
def test_retired_cost_decision_gets_new_lifecycle_without_resetting_same_failure(world, decision_change):
    root, pkg, ledger, calls, save = world
    previous, auth = sealed_operation(world)
    if decision_change == "missing":
        ledger["pendingSpendAuth"] = None
    elif decision_change == "consumed":
        cb_db.claim_spend_authorization(root, auth["token"], "Ep3", "1", "S1.SH2",
                                        auth["bindingHash"], auth["envelopeHash"], "submitted-batch")
    else:
        replacement = {**auth, "token": "b"*32}
        cb_db.issue_spend_authorization(root, "Ep3", "1", "S1.SH2", replacement)
        ledger["pendingSpendAuth"] = replacement
    save()
    current = C.register(root, PREPARE_ARGS, previous["jobId"])
    assert current["operationId"] != previous["operationId"]
    assert current["jobId"] != previous["jobId"]
    assert C.reserve(root, current["operationId"], current["jobId"], resume=True)[1]
    C.change(root, current["operationId"], "needs-attention", "Same final review timeout",
             owner=None, leaseUntil=0, attempts={"prepare": 2},
             resumeInputFingerprint=C.request_fingerprint(root, current, pkg))
    same = C.register(root, PREPARE_ARGS)
    assert same["operationId"] == current["operationId"]
    assert same["attempts"] == {"prepare": 2}


def test_retake_new_approved_source_can_start_new_operation_without_rewriting_prior_evidence(world):
    root, pkg, ledger, calls, save = world
    previous = C.register(root, ARGS)
    C.change(root, previous["operationId"], "needs-attention", "Missing direction", inputsCaptured=True)
    ledger["voiceApproval"] = {"hash": "explicit-new-audio-approval", "path": ledger["voPath"]}
    save()
    current = C.register(root, ARGS)
    assert current["operationId"] != previous["operationId"]
    assert C.get(root, previous["operationId"])["approvedSources"] == previous["approvedSources"]
    assert current["approvedSources"]["voiceApproval"]["hash"] == "explicit-new-audio-approval"


def test_derived_prompt_and_record_timestamps_do_not_reset_a_failed_request(world):
    root, pkg, ledger, calls, save = world
    ledger["watchDirectorFeedback"] = {"text": "Keep intention", "savedAt": "before"}
    ledger["departmentWork"] = {"animation": {"candidate": {"generatedAt": "before",
        "output": {"referenceContract": [], "providerPrompt": "old compiled prompt"}}}}
    save()
    previous = C.register(root, PREPARE_ARGS)
    C.change(root, previous["operationId"], "needs-attention", "Timed out", attempts={"prepare": 2})
    ledger["watchDirectorFeedback"]["savedAt"] = "later"
    ledger["departmentWork"]["animation"]["candidate"]["generatedAt"] = "later"
    ledger["departmentWork"]["animation"]["candidate"]["output"]["providerPrompt"] = "rebuilt compiled prompt"
    save()
    current = C.register(root, PREPARE_ARGS)
    assert current["operationId"] == previous["operationId"]
    assert current["attempts"] == {"prepare": 2}


def test_bound_reference_bytes_change_reopens_preparation(world):
    root, pkg, ledger, calls, save = world
    ledger["additionalAnimationReferenceRoles"] = ["location:reverse"]
    reference = root / "reverse.png"
    reference.write_bytes(b"original geography reference")
    registry = root / "cb-output/asset-registry/assets.json"
    registry.parent.mkdir()
    registry.write_text(json.dumps({"assets": [{"assetId": "reference1", "episode": "Ep3",
        "scene": "1", "shotId": "S1.SH2", "role": "location:reverse", "path": str(reference), "status": "approved"}]}))
    save()
    previous, auth = sealed_operation(world)
    reference.write_bytes(b"changed geography reference")
    ledger["pendingSpendAuth"] = None
    save()
    current = C.register(root, PREPARE_ARGS)
    assert current["operationId"] != previous["operationId"]
    assert current["predecessorOperationId"] == previous["operationId"]


def test_issued_unclaimed_token_never_inherits_old_task_or_returned_media(world):
    root, pkg, ledger, calls, save = world
    previous, auth = sealed_operation(world)
    old = root / "old-take.mp4"
    old.write_bytes(b"old returned artifact")
    ledger.update(status="candidates-pending", batchId="old-batch", candidatePaths=[str(old)],
                  batch={"transports": [{"providerTaskId": "old-task", "status": "completed"}]})
    save()
    op = C.register(root, ["cb_render.py", "fire", "1", "S1.SH2", "Ep3", "--spend-token", auth["token"]])
    result = C.reconcile(root, op["operationId"])
    assert result["state"] == "reconciling-submission"
    assert result["providerTaskIds"] == [] and result["returnedPaths"] == []
    assert result["mediaSubmitted"] is None


def test_current_task_cannot_claim_previous_batch_candidate_paths(world):
    root, pkg, ledger, calls, save = world
    previous, auth = sealed_operation(world)
    cb_db.claim_spend_authorization(root, auth["token"], "Ep3", "1", "S1.SH2",
                                    auth["bindingHash"], auth["envelopeHash"], "new-batch")
    output = root / "take.mp4"
    output.write_bytes(b"returned artifact")
    ledger.update(status="candidates-pending", batchId="old-batch", candidatePaths=[str(output)],
        batch={"token": auth["token"], "batchId": "new-batch", "status": "generating",
               "transports": [{"providerTaskId": "new-task", "status": "running"}]})
    save()
    op = C.register(root, ["cb_render.py", "fire", "1", "S1.SH2", "Ep3", "--spend-token", auth["token"]])
    observed = C.reconcile(root, op["operationId"])
    assert observed["providerTaskIds"] == ["new-task"]
    assert observed["returnedPaths"] == [] and observed["state"] == "reconciling-submission"
    ledger["batchId"] = "new-batch"
    ledger["batch"]["status"] = "complete"
    save()
    observed = C.reconcile(root, op["operationId"])
    assert observed["state"] == "reviewing" and observed["returnedPaths"] == [str(output)]


def test_duplicate_http_requests_and_server_restart_keep_one_operation(world, monkeypatch):
    root, pkg, ledger, calls, save = world
    server = load_server(root, monkeypatch, "recovery_duplicate_server")
    launches = []
    monkeypatch.setattr(server, "_stream", lambda job, args: launches.append((job, args)))
    with Http(server) as http:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: http.request("POST", "/api/shot-run", RETAKE), range(2)))
        assert [r[0] for r in results] == [200, 200], results
        assert results[0][1]["jobId"] == results[1][1]["jobId"]
        assert len(launches) == 1
        status, payload = http.request("GET", "/api/production-operations?episode=Ep3&scene=1")
        assert status == 200 and len(payload["operations"]) == 1
    op = C.all_operations(root)[0]
    assert op["correction"] == RETAKE["correction"]
    # A lost dispatch reservation is durable and resumable with exactly the same ID.
    C.change(root, op["operationId"], "preparing", "Worker lost", owner="dead", workerPid=99999999, leaseUntil=time.time()+30)
    second = load_server(root, monkeypatch, "recovery_restarted_server")
    second.JOBS.update(cb_db.load_jobs(root))
    restarted = []
    monkeypatch.setattr(second, "_stream", lambda job, args: restarted.append((job, args)))
    second._recover_production_operations()
    assert restarted == [(op["jobId"], ARGS)]
    assert len(C.all_operations(root)) == 1
    assert C.get(root, op["operationId"])["correction"] == RETAKE["correction"]
    assert not calls


def test_restart_does_not_take_over_live_worker(world, monkeypatch):
    root, *_ = world
    op = C.register(root, ARGS, "live-job")
    C.change(root, op["operationId"], "preparing", "Working", owner="live",
             workerPid=os.getpid(), leaseUntil=time.time()+30)
    assert C.recoverable(root) == []
    assert C.get(root, op["operationId"])["owner"] == "live"
    C.change(root, op["operationId"], "preparing", "Heartbeat was delayed", leaseUntil=time.time()-1)
    assert C.recoverable(root) == []


def test_normal_browser_cost_review_uses_preparation_and_never_supplies_spend(world, monkeypatch):
    root, pkg, ledger, calls, save = world
    previous, auth = sealed_operation(world)
    pkg["shots"][0]["directorCard"] = {"action": "The revised intended action"}
    ledger["pendingSpendAuth"] = None
    save()
    server = load_server(root, monkeypatch, "recovery_normal_prepare")
    launches = []
    monkeypatch.setattr(server, "_stream", lambda job, args: launches.append(args))
    with Http(server) as http:
        status, payload = http.request("POST", "/api/shot-run", {
            "cmd": "fire", "scene": "1", "episode": "Ep3", "shotId": "S1.SH2", "candidates": 1})
        assert status == 200
    assert launches == [["cb_studio_director.py", "prepare-render", "1", "S1.SH2", "Ep3"]]
    operation = C.all_operations(root)[0]
    assert operation["spendingAuthority"] == {"media": False}
    assert operation["jobId"] == payload["jobId"]
    assert operation["predecessorOperationId"] == previous["operationId"]


def test_cli_resumes_saved_checkpoints_without_rejecting_or_preparing_twice(world, monkeypatch):
    root, pkg, ledger, calls, save = world
    original = copy.deepcopy(ledger)
    def fail(*args):
        raise RuntimeError("Missing current reference")
    monkeypatch.setattr(D, "prepare_render", fail)
    assert D.main(ARGS[1:]) == 1
    op = C.all_operations(root)[0]
    assert op["state"] == "needs-attention"
    server = load_server(root, monkeypatch, "recovery_cli_projection")
    visible = server._jobs_snapshot()[op["jobId"]]
    assert visible["status"] == "failed"
    assert visible["operation"]["operationId"] == op["operationId"]
    assert {"archive-take", "cinematography", "animation"}.issubset(op["checkpoints"])
    def succeed(*args):
        ledger["pendingSpendAuth"] = {"token": "current", "envelopeHash": "exact-payload"}
        save()
    monkeypatch.setattr(D, "prepare_render", succeed)
    assert D.main(ARGS[1:]) == 0
    final = C.get(root, op["operationId"])
    assert final["state"] == "awaiting-spend-approval" and final["mediaSubmitted"] is False
    assert final["payloadHash"] == "exact-payload"
    assert calls.count("archive") == calls.count("cinematography") == calls.count("animation") == 1
    assert ledger["keyframeApproval"] == original["keyframeApproval"]
    assert ledger["voiceApproval"] == original["voiceApproval"]
    assert C.events(root, op["operationId"])[-1]["state"] == "awaiting-spend-approval"


def test_timeout_budget_survives_http_resume_and_has_actionable_status(world, monkeypatch):
    root, pkg, ledger, calls, save = world
    attempts = []
    def fail(*args):
        attempts.append(1)
        raise RuntimeError("prompt_director APITimeoutError: request timed out")
    monkeypatch.setattr(D, "prepare_render", fail)
    assert D.main(ARGS[1:]) == 1
    op = C.all_operations(root)[0]
    assert len(attempts) == 2 and op["state"] == "needs-attention"
    server = load_server(root, monkeypatch, "recovery_timeout_server")
    finished = threading.Event()
    def stream(job_id, args):
        D.main(args[1:])
        finished.set()
    monkeypatch.setattr(server, "_stream", stream)
    with Http(server) as http:
        status, payload = http.request("POST", "/api/production-operation-resume", {"operationId": op["operationId"]})
        assert status == 200
        assert finished.wait(4)
        status, jobs = http.request("GET", "/api/jobs")
        job = jobs["jobs"][payload["jobId"]]
        assert job["status"] == "failed"
        assert "recovery limit reached" in job["step"]
    assert len(attempts) == 2  # Resume cannot silently replenish the text retry budget.
    assert ledger["pendingSpendAuth"] is None


def test_changed_approved_bytes_are_not_renewed_on_resume(world, monkeypatch):
    root, pkg, ledger, calls, save = world
    monkeypatch.setattr(D, "prepare_render", lambda *a: (_ for _ in ()).throw(RuntimeError("Missing reference")))
    assert D.main(ARGS[1:]) == 1
    op = C.all_operations(root)[0]
    old = op["approvedSources"]
    Path(ledger["voPath"]).write_bytes(b"different voice bytes")
    assert D.main(ARGS[1:]) == 1
    final = C.get(root, op["operationId"])
    assert final["approvedSources"] == old
    assert "Approved inputs changed" in final["message"]
    assert calls.count("archive") == 1


def test_only_explicit_producer_text_retry_reopens_one_bounded_cycle(world, monkeypatch):
    root, pkg, ledger, calls, save = world
    attempts = []
    def fail(*args):
        attempts.append(1)
        raise RuntimeError("prompt_director APITimeoutError: timed out")
    monkeypatch.setattr(D, "prepare_render", fail)
    assert D.main(ARGS[1:]) == 1
    operation = C.all_operations(root)[0]
    assert C.public(operation)["canRetryTextReview"] is True
    C.authorize_text_retry(root, operation["operationId"])
    assert D.main(ARGS[1:]) == 1
    assert len(attempts) == 4
    with pytest.raises(RuntimeError, match="repair"):
        C.authorize_text_retry(root, operation["operationId"])
    assert any(event.get("action") == "producer-authorized-text-retry"
               for event in C.events(root, operation["operationId"]))
    assert ledger["pendingSpendAuth"] is None


def test_expired_preparation_worker_is_stopped_and_not_left_running(world, monkeypatch):
    root, *_ = world
    server = load_server(root, monkeypatch, "recovery_worker_deadline")
    worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                              stdout=subprocess.PIPE, text=True, start_new_session=True)
    try:
        with pytest.raises(TimeoutError, match="deadline"):
            list(server._process_lines_until_exit(worker, timeout=0.01, deadline=time.time()-1))
        assert worker.poll() is not None
    finally:
        if worker.poll() is None:
            worker.kill()
        worker.wait()
        worker.stdout.close()


@pytest.mark.parametrize("state", ["preparing", "needs-attention", "reconciling-submission"])
def test_browser_durable_operation_hides_stale_cost_and_shows_real_recovery(state):
    app = Path(__file__).with_name("app.html").read_text()
    js = app[app.index("function watchProductionOperation("):app.index("async function directorContinue(")]
    harness = r'''
const assert=require('node:assert/strict');
const SH_EP='Ep3',SH_SC='1',PSHOT_I=0;
const pShots=()=>[{shotId:'S1.SH2'}],pFocusedStage=()=> 'animation';
const shLedger=()=>({pendingSpendAuth:{token:'stale'},watchRetake:{status:'preparing'}});
const _esc=x=>String(x||''),_attr=_esc,durableWatchJob=()=>null;
const PJOBS={current:{scene:'1',args:['S1.SH2'],status:state==='preparing'?'running':'failed',
 operation:{operationId:'op1',shotId:'S1.SH2',episode:'Ep3',scene:'1',state,
 message:'Exact saved recovery status',createdAt:1}}};
const html=directorNextStepHTML();
assert.ok(html.includes('Exact saved recovery status'));
assert.ok(!html.includes('Review cost &amp; fire'));
if(state==='needs-attention')assert.ok(html.includes('Resume saved preparation'));
if(state==='reconciling-submission')assert.ok(!html.includes('resumeProductionOperation'));
'''
    subprocess.run(["node", "-e", "const state="+json.dumps(state)+";\n"+js+harness],
                   check=True, capture_output=True, text=True)


@pytest.mark.parametrize("task_id", [None, "provider-existing-task"])
def test_uncertain_submission_reconciles_exact_batch_without_replay(world, monkeypatch, task_id):
    root, pkg, ledger, calls, save = world
    token = "a" * 32
    args = ["cb_render.py", "fire", "1", "S1.SH2", "Ep3", "--spend-token", token]
    op = C.register(root, args, "submitted-job")
    C.change(root, op["operationId"], "submitting", "Worker interrupted", owner="lost", workerPid=99999999)
    ledger["batch"] = {"token": token, "batchId": "new-batch", "transports": [
        {"providerTaskId": task_id, "status": "submitted" if task_id else "submitting"}]}
    # An old unrelated batch ID must never qualify as this operation's returned media.
    ledger["candidatePaths"] = []
    save()
    if task_id:
        observed = C.reconcile(root, op["operationId"], worker_running=True)
        assert observed["state"] == "rendering"
        assert observed["providerTaskIds"] == [task_id]
    assert C.recoverable(root) == []
    result = C.get(root, op["operationId"])
    assert result["state"] == "reconciling-submission"
    assert result["providerTaskIds"] == ([task_id] if task_id else [])
    event_count = len(C.events(root, op["operationId"]))
    assert C.recoverable(root) == []
    assert len(C.events(root, op["operationId"])) == event_count
    server = load_server(root, monkeypatch, "recovery_submission_server")
    launches = []
    monkeypatch.setattr(server, "_stream", lambda *a: launches.append(a))
    with Http(server) as http:
        status, payload = http.request("POST", "/api/production-operation-resume", {"operationId": op["operationId"]})
        assert status == 409 and payload["zeroSpend"] is True
    assert launches == [] and calls == []


def test_successful_process_exit_without_cost_or_media_is_not_completed(world, monkeypatch):
    root, pkg, ledger, calls, save = world
    monkeypatch.setattr(D, "prepare_render", lambda *a: None)
    assert D.main(ARGS[1:]) == 1
    op = C.all_operations(root)[0]
    assert op["state"] == "needs-attention" and "cost review" in op["message"]
    assert op["mediaSubmitted"] is False
