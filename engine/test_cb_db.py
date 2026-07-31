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
