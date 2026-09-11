"""Historical native provenance checks; synthetic files and no network calls."""
import copy
import hashlib
import json
import socket

import pytest

import cb_render as R
from studio_shot_request import native_envelope
from test_current_production_path import world, isolated_canon


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", lambda *args, **kwargs: pytest.fail("Network forbidden"))


def sealed_batch():
    ref = {"path": "/tmp/original.png", "md5": "original-content", "slot": "Image 1",
           "role": "opening keyframe"}
    env = {"shotId": "S1.SH1", "directorCardRevision": {"revision": 3},
           "references": [dict(ref)], "executionPlan": {"segments": [
               {"segmentIndex": 0, "prompt": "The character turns, then settles.",
                "references": [dict(ref)], "promptDirectorSnapshot": {
                    "authorities": {"shot": {"dialogueLines": []}, "revision": 3}},
                "promptDirector": {"lifecycle": ["original expectation"]}}]}}
    env["productionRequest"] = native_envelope(env).record()
    return {"batchId": "original-batch", "envelope": env, "envelopeHash": seal(env)}


def seal(envelope):
    # The native fire serializer has spaces; compact canonical request JSON differs.
    return hashlib.sha256(json.dumps(envelope, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def test_matching_outer_and_request_seals_preserve_exact_historical_plan():
    batch = sealed_batch()
    batch["envelope"]["executionPlan"]["segments"][0]["prompt"] += " Café."
    batch["envelope"]["productionRequest"] = native_envelope(batch["envelope"]).record()
    batch["envelopeHash"] = seal(batch["envelope"])
    result = R._returned_origin({"batch": batch, "currentDirection": "changed"})
    assert result["status"] == "origin-verified"
    assert result["originIntegrity"]["verified"] is True
    assert result["segments"][0]["sourceSnapshot"]["authorities"]["revision"] == 3
    assert result["segments"][0]["references"][0]["md5"] == "original-content"
    assert result["originatingProduction"]["approved"] is False
    assert result["reviewScope"]["deliveryEligible"] is False


@pytest.mark.parametrize("field", ["references", "promptDirectorSnapshot", "request"])
def test_changed_sealed_history_is_an_incident_without_trusted_segments(field):
    batch = sealed_batch()
    env = batch["envelope"]
    segment = env["executionPlan"]["segments"][0]
    if field == "references":
        segment["references"][0].update(path="/tmp/replacement.png", md5="replacement-content")
    elif field == "promptDirectorSnapshot":
        segment[field]["authorities"]["revision"] = 99
    else:
        env["productionRequest"]["snapshot"]["truth"]["direction"] = {"changed": True}
        # A matching outer seal cannot cure a corrupt nested immutable request.
        batch["envelopeHash"] = seal(env)
    ledger = {"batch": batch, "candidatePaths": ["/tmp/existing.mp4"]}
    before = copy.deepcopy(ledger)
    result = R._returned_origin(ledger)
    assert result["status"] == "origin-integrity-failed"
    assert result["requestLineage"]["status"] == "origin-integrity-failed"
    assert result["originatingProduction"]["status"] == "origin-integrity-failed"
    assert result["originIntegrity"]["verified"] is False
    assert result["segments"] == [] and result["directorCardRevision"] is None
    assert "truth" not in result["originatingProduction"]
    assert ledger == before  # Playback paths and historical incident are left intact.


def test_missing_outer_seal_never_promotes_nested_request_to_verified_origin():
    batch = sealed_batch()
    del batch["envelopeHash"]
    result = R._returned_origin({"batch": batch})
    assert result["status"] == "legacy-unverified"
    assert result["requestLineage"]["status"] == "legacy-unverified"
    assert result["originatingProduction"]["status"] == "legacy-unverified"
    assert result["segments"][0]["references"][0]["md5"] == "original-content"
    assert "unverified" in result["reviewScope"]["planned"]
    assert result["originIntegrity"]["verified"] is False


@pytest.mark.parametrize("envelope", [["broken envelope"], {"executionPlan": "broken plan"},
                                     {"executionPlan": {"segments": ["broken segment"]}}])
def test_malformed_historical_record_is_readable_as_an_incident(envelope):
    result = R._returned_origin({"batch": {"envelope": envelope, "envelopeHash": seal(envelope)}})
    assert result["status"] == "origin-integrity-failed"
    assert result["segments"] == []


def test_corrupt_origin_blocks_review_before_frames_or_model_and_stays_readable(world, monkeypatch):
    _, root, path = world
    pkg = json.loads(path.read_text())
    shot = pkg["shots"][0]
    led = R._ledger(pkg, shot["shotId"])
    media = root / "existing.mp4"
    media.write_bytes(b"synthetic-existing-media")
    batch = sealed_batch()
    batch["envelope"]["executionPlan"]["segments"][0]["references"][0]["md5"] = "replaced"
    led.update(status="candidates-pending", candidatePaths=[str(media)], batch=batch)
    path.write_text(json.dumps(pkg))
    monkeypatch.setattr(R, "_review_frames", lambda *args, **kwargs: pytest.fail("Frame extraction forbidden"))
    monkeypatch.setattr(R.cb_departments, "review_media", lambda *args, **kwargs: pytest.fail("Reviewer forbidden"))
    before = path.read_bytes()
    with pytest.raises(R.Refused, match="originating production integrity failed"):
        R.prepare_department("9", "review-animation", shot["shotId"], "EpT", log=lambda *args: None)
    assert path.read_bytes() == before and media.read_bytes() == b"synthetic-existing-media"
    signature = R._department_input_signature(pkg, "review-animation", shot["shotId"], "9", "EpT")
    assert signature["generationSignature"] is None
    shot.update(seedancePrompt="Today's unrelated revised action.", camera="New close-up.")
    assert R._department_input_signature(pkg, "review-animation", shot["shotId"], "9", "EpT") == signature
    assert R._returned_origin(led)["status"] == "origin-integrity-failed"
