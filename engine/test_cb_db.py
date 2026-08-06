import json
import threading
import time

import pytest

import cb_db


def _auth(token="a" * 32):
    envelope = {
        "candidateCount": 2,
        "prompt": "locked prompt",
        "durationSec": 4,
    }
    return {
        "token": token,
        "bindingHash": "b" * 32,
        "envelopeHash": "e" * 64,
        "envelope": envelope,
        "disclosure": {"candidateCount": 2},
        "issuedAt": cb_db.utc_now(),
    }


def test_atomic_json_compare_and_swap_blocks_lost_update(tmp_path):
    path = tmp_path / "cb-output" / "EpT_scene1_production_package.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"value": 0}))

    first, first_digest = cb_db.read_json_document(tmp_path, path)
    second, second_digest = cb_db.read_json_document(tmp_path, path)
    first["value"] = 1
    cb_db.atomic_write_json(tmp_path, path, first, first_digest)

    second["value"] = 2
    with pytest.raises(cb_db.StateConflict, match="CONCURRENT STATE CHANGE"):
        cb_db.atomic_write_json(tmp_path, path, second, second_digest)
    assert json.loads(path.read_text()) == {"value": 1}


def test_atomic_remove_refuses_a_changed_document(tmp_path):
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps({"version": 1}))
    _, digest = cb_db.read_json_document(tmp_path, path)
    path.write_text(json.dumps({"version": 2}))

    with pytest.raises(cb_db.StateConflict, match="changed before removal"):
        cb_db.atomic_remove(tmp_path, path, expected_digest=digest)
    assert path.exists()


def test_studio_jobs_survive_restart_and_orphans_become_interrupted(tmp_path):
    job = {
        "jobId": "storyintake_Ep1_test",
        "serverKey": "127.0.0.1:8770|public",
        "gate": "storyintake",
        "scene": "-",
        "args": ["cb_intake.py", "run", "Ep1"],
        "status": "running",
        "step": "Director - reading the script",
        "log": "MECHANICAL PARSE",
        "started": 100.0,
        "ended": None,
        "pid": 123,
    }
    cb_db.persist_job(tmp_path, job)
    other = dict(job, jobId="storyintake_Ep1_other",
                 serverKey="127.0.0.1:8765|loopback", started=101.0)
    cb_db.persist_job(tmp_path, other)

    restored = cb_db.load_jobs(tmp_path, server_key=job["serverKey"])
    assert list(restored) == [job["jobId"]]
    assert restored[job["jobId"]]["status"] == "running"
    assert restored[job["jobId"]]["args"] == job["args"]
    assert restored[job["jobId"]]["operationKey"] == cb_db.job_operation_key(
        job["gate"], job["scene"], job["args"])

    assert cb_db.interrupt_running_jobs(
        tmp_path, "Restarted safely.", server_key=job["serverKey"]
    ) == 1
    interrupted = cb_db.load_jobs(tmp_path)[job["jobId"]]
    assert interrupted["status"] == "interrupted"
    assert interrupted["step"] == "Restarted safely."
    assert interrupted["ended"] is not None
    assert interrupted["log"].endswith("Restarted safely.")
    assert cb_db.load_jobs(tmp_path)[other["jobId"]]["status"] == "running"


def test_scene_lease_refuses_parallel_owner_and_is_reentrant(tmp_path):
    results = []
    with cb_db.scene_lease(tmp_path, "EpT", "1", "outer"):
        with cb_db.scene_lease(tmp_path, "EpT", "1", "nested"):
            pass

        def contend():
            try:
                with cb_db.scene_lease(tmp_path, "EpT", "1", "parallel"):
                    results.append("acquired")
            except Exception as exc:
                results.append(exc)

        thread = threading.Thread(target=contend)
        thread.start()
        thread.join(timeout=2)

    assert len(results) == 1
    assert isinstance(results[0], cb_db.SceneBusy)
    assert "SCENE BUSY" in str(results[0])


def test_expired_scene_lease_can_be_recovered(tmp_path):
    now = time.time()
    with cb_db.transaction(tmp_path) as conn:
        conn.execute(
            """
            INSERT INTO scene_leases(
                episode, scene, owner, operation, acquired_at, heartbeat_at, expires_at
            ) VALUES('EpT', '1', 'dead-owner', 'crashed-job', ?, ?, ?)
            """,
            (now - 10, now - 10, now - 1),
        )
    with cb_db.scene_lease(tmp_path, "EpT", "1", "recovery"):
        pass


def test_spend_and_candidate_claims_are_single_owner_and_idempotent(tmp_path):
    auth = _auth()
    cb_db.issue_spend_authorization(tmp_path, "EpT", "1", "1.B1.S1", auth)
    cb_db.claim_spend_authorization(
        tmp_path, auth["token"], "EpT", "1", "1.B1.S1",
        auth["bindingHash"], auth["envelopeHash"], "batch-1")

    assert cb_db.claim_candidate(tmp_path, auth["token"], 1, "worker-a")["action"] == "generate"
    with pytest.raises(cb_db.SpendConflict, match="unresolved provider attempt"):
        cb_db.claim_candidate(tmp_path, auth["token"], 1, "worker-b")

    out1 = tmp_path / "candidate-1.mp4"
    out1.write_bytes(b"one")
    cb_db.complete_candidate(tmp_path, auth["token"], 1, out1)
    completed = cb_db.claim_candidate(tmp_path, auth["token"], 1, "worker-b")
    assert completed["action"] == "completed"

    assert cb_db.claim_candidate(tmp_path, auth["token"], 2, "worker-a")["action"] == "generate"
    cb_db.fail_candidate(tmp_path, auth["token"], 2, "provider unavailable")
    assert cb_db.claim_candidate(tmp_path, auth["token"], 2, "worker-a")["action"] == "generate"
    out2 = tmp_path / "candidate-2.mp4"
    out2.write_bytes(b"two")
    cb_db.complete_candidate(tmp_path, auth["token"], 2, out2)

    cb_db.complete_spend_authorization(tmp_path, auth["token"])
    assert cb_db.spend_authorization(tmp_path, auth["token"])["status"] == "completed"
    with pytest.raises(cb_db.SpendConflict, match="already-used"):
        cb_db.claim_spend_authorization(
            tmp_path, auth["token"], "EpT", "1", "1.B1.S1",
            auth["bindingHash"], auth["envelopeHash"], "batch-1")


def test_internal_provider_segments_are_individually_idempotent(tmp_path):
    auth = _auth()
    auth["envelope"]["candidateCount"] = 1
    auth["disclosure"]["candidateCount"] = 1
    cb_db.issue_spend_authorization(tmp_path, "EpT", "1", "S1.SH1", auth)
    cb_db.claim_spend_authorization(
        tmp_path, auth["token"], "EpT", "1", "S1.SH1",
        auth["bindingHash"], auth["envelopeHash"], "batch-segmented")
    cb_db.claim_candidate(tmp_path, auth["token"], 1, "worker")

    first = cb_db.claim_candidate_segment(
        tmp_path, auth["token"], 1, 1, 2, "worker")
    assert first["action"] == "generate"
    segment_one = tmp_path / "segment-1.mp4"
    segment_one.write_bytes(b"segment-one")
    cb_db.complete_candidate_segment(tmp_path, auth["token"], 1, 1, segment_one)
    completed = cb_db.claim_candidate_segment(
        tmp_path, auth["token"], 1, 1, 2, "worker")
    assert completed["action"] == "completed"

    cb_db.claim_candidate_segment(tmp_path, auth["token"], 1, 2, 2, "worker")
    with pytest.raises(cb_db.SpendConflict, match="until every sealed segment"):
        candidate = tmp_path / "candidate.mp4"
        candidate.write_bytes(b"joined")
        cb_db.complete_candidate(tmp_path, auth["token"], 1, candidate)
    cb_db.fail_candidate_segment(
        tmp_path, auth["token"], 1, 2, "provider unavailable")
    retry = cb_db.claim_candidate_segment(
        tmp_path, auth["token"], 1, 2, 2, "worker")
    assert retry["action"] == "generate"
    segment_two = tmp_path / "segment-2.mp4"
    segment_two.write_bytes(b"segment-two")
    cb_db.complete_candidate_segment(tmp_path, auth["token"], 1, 2, segment_two)
    candidate = tmp_path / "candidate.mp4"
    candidate.write_bytes(b"joined")
    cb_db.complete_candidate(tmp_path, auth["token"], 1, candidate)
