import base64
import importlib.util
import io
import pathlib

import pytest
from PIL import Image


SERVER_PATH = pathlib.Path(__file__).resolve().parents[1] / "cb-studio" / "serve.py"
SPEC = importlib.util.spec_from_file_location("cb_studio_security_test_server", SERVER_PATH)
SERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SERVER)


def test_request_length_is_bounded_and_chunked_bodies_are_rejected():
    assert SERVER._validated_content_length({"Content-Length": "128"}) == 128
    with pytest.raises(SERVER.RequestTooLarge):
        SERVER._validated_content_length({
            "Content-Length": str(SERVER.MAX_REQUEST_BYTES + 1),
        })
    with pytest.raises(ValueError, match="chunked"):
        SERVER._validated_content_length({"Transfer-Encoding": "chunked"})
    with pytest.raises(ValueError, match="non-negative"):
        SERVER._validated_content_length({"Content-Length": "-1"})


def test_image_upload_uses_detected_type_and_rejects_invalid_bytes(monkeypatch):
    stream = io.BytesIO()
    Image.new("RGB", (2, 2), "red").save(stream, format="PNG")
    encoded = base64.b64encode(stream.getvalue()).decode()

    blob, extension = SERVER.decode_image_upload(encoded)
    assert blob.startswith(b"\x89PNG") and extension == ".png"

    with pytest.raises(ValueError, match="readable"):
        SERVER.decode_image_upload(base64.b64encode(b"not-an-image").decode())

    monkeypatch.setattr(SERVER, "MAX_IMAGE_PIXELS", 1)
    with pytest.raises(ValueError, match="dimensions"):
        SERVER.decode_image_upload(encoded)


def test_static_allowlist_hides_secrets_source_and_traversal():
    assert not SERVER._static_blocked("/cb-studio/app.html")
    assert not SERVER._static_blocked("/engine/media/review.mp4")
    assert SERVER._static_blocked("/engine/.env")
    assert SERVER._static_blocked("/engine/cb_gen.py")
    assert SERVER._static_blocked("/engine/media/../../engine/.env")


def test_duplicate_live_job_start_reuses_the_existing_job():
    args = ["cb_intake.py", "run", "Ep1"]
    operation_key = SERVER.cb_db.job_operation_key("storyintake", "-", args)
    saved = SERVER._jobs_snapshot()
    try:
        with SERVER._JOB_LOCK:
            SERVER.JOBS.clear()
            SERVER.JOBS["existing"] = {
                "jobId": "existing",
                "gate": "storyintake",
                "scene": "-",
                "args": args,
                "operationKey": operation_key,
                "status": "running",
                "step": "Working",
                "log": "",
                "started": 1.0,
                "ended": None,
            }
        assert SERVER._start("duplicate", "storyintake", "-", args) == "existing"
        assert list(SERVER.JOBS) == ["existing"]
    finally:
        with SERVER._JOB_LOCK:
            SERVER.JOBS.clear()
            SERVER.JOBS.update(saved)


def test_new_job_refuses_to_run_without_durable_ledger(monkeypatch):
    saved = SERVER._jobs_snapshot()
    try:
        with SERVER._JOB_LOCK:
            SERVER.JOBS.clear()
        monkeypatch.setattr(SERVER, "_is_stale", lambda: False)

        def fail_persistence(_job, required=False):
            assert required is True
            raise RuntimeError("ledger unavailable")

        monkeypatch.setattr(SERVER, "_persist_job", fail_persistence)
        with pytest.raises(RuntimeError, match="ledger unavailable"):
            SERVER._start("new-job", "storyintake", "-",
                          ["cb_intake.py", "run", "Ep1"])
        assert "new-job" not in SERVER.JOBS
        assert "new-job" not in SERVER.PROCS
    finally:
        with SERVER._JOB_LOCK:
            SERVER.JOBS.clear()
            SERVER.JOBS.update(saved)
