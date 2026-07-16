#!/usr/bin/env python3
"""test_e2e_fire_route.py — Julian's cutover order (2026-07-16, §6): prove the REAL production
route end to end, from the actual Studio endpoint to a mocked fal adapter, after the legacy
Gate-3 button fired a 634-word 15-second mega-prompt around every spend protection.

Three proofs, zero spend:

1. THE STUDIO ENDPOINT: cb-studio/serve.py's shot_run_job — the exact function the Shots tab's
   'Approve spend & fire' click reaches via POST /api/shot-run — builds precisely the argv that
   invokes cb_render's fire path with the token. (The subprocess boundary is bridged by proving
   both of its sides: this argv, and the fire function below that argv dispatches to.)

2. THE SEALED ROUTE: fire_shot against the REAL revision-6 production package (writes redirected
   to a scratch copy; provider adapter mocked) — disclosure seals the envelope, the token binds
   to its hash, and the OUTGOING PROVIDER REQUEST contains the exact accepted 105-word brief,
   duration 6.0, package revision 6, the approved keyframe/references/audio — and NO legacy
   prompt string.

3. THE SINGLE ROUTE: every legacy caller of a paid provider function is blocked at the cb_gen
   chokepoint at runtime.

    pytest test_e2e_fire_route.py -q
"""
import hashlib
import json
import pathlib
import shutil
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "cb-studio"))

import cb_gen
import cb_render

LEGACY_STRINGS = [
    "Pixar-caliber", "squash-and-stretch", "0–5s", "5–10s", "10–15s", "Negative:",
    "camera already waiting at the leaf", "no leaf hit as the final image",
    "crash-lands into pride", "frame-left lane", "15s, 16:9, 24fps",
]


def test_studio_endpoint_builds_the_exact_fire_argv():
    """§6 step 1: the Shots tab's approve-spend click -> POST /api/shot-run ->
    serve.shot_run_job -> the exact cb_render argv (token travels as its own argv element).
    serve.py binds its port at import (the live Studio holds it), so the REAL shot_run_job
    function is extracted from the real source via ast and executed with a captured _start —
    identical code under test, no socket."""
    import ast
    src = (HERE.parent / "cb-studio" / "serve.py").read_text()
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "shot_run_job")
    captured = {}
    ns = {"_start": lambda jid, label, scene, argv: captured.update(argv=argv, label=label),
          "_jid": lambda s: s, "str": str}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "serve.py", "exec"), ns)
    ns["shot_run_job"]("fire", "1", episode="Ep1", shot_id="1.B1.S1",
                        candidates=3, spend_token="feedfacefeedface")
    assert captured["argv"] == ["cb_render.py", "fire", "1", "1.B1.S1", "Ep1",
                                 "--candidates", "3", "--spend-token", "feedfacefeedface"]


@pytest.fixture()
def scratch_pkg(monkeypatch, tmp_path):
    """The REAL revision-6 package, loaded read-only and SAVED to a scratch copy — the real
    file can never be mutated by this test. Reference/audio files are the real, approved,
    hash-verified assets (read-only)."""
    real = HERE.parent / "cb-output" / "Ep1_scene1_production_package.json"
    scratch = tmp_path / real.name
    shutil.copy(real, scratch)
    real_load = cb_render.load_pkg
    monkeypatch.setattr(cb_render, "load_pkg",
                        lambda scene, episode="Ep1": (json.load(open(scratch)), scratch))
    monkeypatch.setattr(cb_render, "MEDIA", tmp_path / "shots")
    return scratch


def test_outgoing_provider_request_is_the_sealed_brief(monkeypatch, scratch_pkg, tmp_path):
    """§6 step 2: disclosure -> sealed envelope -> token -> fire -> MOCKED adapter captures the
    outgoing request. The request is the accepted brief, 6.0s, revision 6, approved assets —
    with zero legacy strings."""
    sent = {}

    def fake_adapter(prompt, image_urls, audio_urls=None, video_urls=None, resolution="720p",
                      duration=None, out=None, fast=False, raw_prompt=False,
                      production_route=None):
        cb_gen._require_production_route(production_route, "test")   # route sentinel enforced
        sent.update(prompt=prompt, image_urls=image_urls, audio_urls=audio_urls,
                     resolution=resolution, duration=duration, fast=fast)
        pathlib.Path(out).write_bytes(b"fake")
        return out

    monkeypatch.setattr(cb_gen, "generate_video_seedance_ref", fake_adapter)
    monkeypatch.setattr(cb_gen, "_fal_upload", lambda p: f"file://{p}")   # no network
    monkeypatch.setattr(cb_render, "_candidate_review", lambda *a, **k: None)
    monkeypatch.setattr(cb_render, "_require_confirmed_billing", lambda prov: None)

    # 1) disclosure: no token -> REFUSED (designed), sealed envelope stored on the scratch ledger
    with pytest.raises(cb_render.Refused, match="SPEND NOT APPROVED"):
        cb_render.fire_shot("1", "1.B1.S1", "Ep1", candidates=3, log=lambda *a, **k: None)
    pkg = json.load(open(scratch_pkg))
    led = [x for x in pkg["continuityLedger"] if x["shotId"] == "1.B1.S1"][0]
    auth = led["pendingSpendAuth"]
    env = auth["envelope"]
    canon = hashlib.sha256(json.dumps(env, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    assert canon == auth["envelopeHash"]                     # token binds to the sealed envelope
    assert env["durationSec"] == 6.0 and env["candidateCount"] == 3
    assert env["packageRevision"] == 6
    assert env["maxBatchCostUsd"] == 5.4612 and env["costPerCandidateUsd"] == 1.8204

    # 2) fire with the token -> the adapter receives the ENVELOPE, verbatim
    cb_render.fire_shot("1", "1.B1.S1", "Ep1", candidates=3,
                         spend_token=auth["token"], log=lambda *a, **k: None)
    shot = [s for s in pkg["shots"] if s["shotId"] == "1.B1.S1"][0]
    assert sent["prompt"] == shot["seedancePrompt"] == env["prompt"]   # the accepted brief, exact
    assert 90 <= len(sent["prompt"].split()) <= 160                    # the lean Option-D band
    assert sent["duration"] == "6" and sent["resolution"] == "720p"
    for legacy in LEGACY_STRINGS:
        assert legacy not in sent["prompt"], f"legacy string leaked: {legacy}"
    # the approved keyframe + reference order + audio travelled exactly as sealed
    assert sent["image_urls"] == [f"file://{r['path']}" for r in env["references"]]
    assert env["references"][0]["role"] == "opening keyframe"
    assert env["references"][0]["md5"] == "c02dc92cbb300cc25898b4231ad04d6e"   # signed keyframe
    assert sent["audio_urls"] == [f"file://{env['audio']['path']}"]
    # single-use: consumed
    pkg2 = json.load(open(scratch_pkg))
    led2 = [x for x in pkg2["continuityLedger"] if x["shotId"] == "1.B1.S1"][0]
    assert led2["pendingSpendAuth"] is None and led2["status"] == "candidates-pending"


def test_pre_envelope_token_is_void(monkeypatch, scratch_pkg):
    """A token issued before the sealed-envelope protocol (e.g. db660b33...) can never fire."""
    monkeypatch.setattr(cb_render, "_require_confirmed_billing", lambda prov: None)
    pkg = json.load(open(scratch_pkg))
    led = [x for x in pkg["continuityLedger"] if x["shotId"] == "1.B1.S1"][0]
    led["pendingSpendAuth"] = {"token": "oldtokenoldtoken",
                                "bindingHash": "x" * 32}     # no envelope — pre-protocol shape
    json.dump(pkg, open(scratch_pkg, "w"), indent=1, ensure_ascii=False)
    with pytest.raises(cb_render.Refused):
        cb_render.fire_shot("1", "1.B1.S1", "Ep1", spend_token="oldtokenoldtoken",
                             log=lambda *a, **k: None)


def test_dry_run_issues_no_token_and_stores_nothing(monkeypatch, scratch_pkg):
    monkeypatch.setattr(cb_render, "_require_confirmed_billing", lambda prov: None)
    with pytest.raises(cb_render.Refused, match="DRY RUN"):
        cb_render.fire_shot("1", "1.B1.S1", "Ep1", candidates=3, dry_run=True,
                             log=lambda *a, **k: None)
    pkg = json.load(open(scratch_pkg))
    led = [x for x in pkg["continuityLedger"] if x["shotId"] == "1.B1.S1"][0]
    assert not led.get("pendingSpendAuth")


def test_every_legacy_route_is_blocked_at_the_adapter():
    """§4: the single-production-route sentinel — a paid call without the cb_render route is
    refused at the chokepoint, so cb_beats/cb_retake/cb_pipeline/the old Studio buttons/this
    module's own CLI are all runtime-disabled without touching their code."""
    for fn, args in [(cb_gen.generate_video_seedance_ref, ("p", [])),
                      (cb_gen.generate_video_seedance, ("p", "kf.png")),
                      (cb_gen.generate_image, ("p",)),
                      (cb_gen.eleven_tts, ("t", "v")),
                      (cb_gen.eleven_dialogue, ([],)),
                      (cb_gen.eleven_music, ("m",)),
                      (cb_gen.eleven_sfx, ("s",)),
                      (cb_gen.lipsync, ("v.mp4", "a.mp3"))]:
        with pytest.raises(RuntimeError, match="legacy fire route disabled"):
            fn(*args)


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
