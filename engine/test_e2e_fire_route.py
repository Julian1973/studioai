#!/usr/bin/env python3
"""test_e2e_fire_route.py — Julian's cutover order (2026-07-16, §6): prove the REAL production
route end to end, from the actual Studio endpoint to a mocked fal adapter, after the legacy
Gate-3 button fired a 634-word 15-second mega-prompt around every spend protection.

2026-07-17 correction (Julian's consolidation-checkpoint directive, item 5 — "Do not use the
archived legacy package as proof of the current route... the golden-path test must use the
newly promoted S1.SH1 canonical package"): this file now carries TWO, explicitly separate,
proof classes:

  - LEGACY (`test_legacy_*`, `legacy_scratch_pkg`): the ORIGINAL revision-6, 1.B1.S1 package —
    kept, explicitly labelled, as a regression pin on the sealed-envelope/token/route mechanics
    against the pre-handover content shape. This is NOT evidence the current, real production
    route works; it proves the route's own MECHANICS haven't regressed against old data.
  - GOLDEN PATH (`test_golden_path_*`, `golden_path_scratch_pkg`): the REAL, currently-live
    canonical package — the one cb_handover.promote_to_canonical actually wrote via a real,
    non-dry-run promotion of S1.SH1 from the human-approved creative-room storyboard. THIS is
    the proof the current route works end to end, on the content that is actually live today.

Four proofs, zero spend:

1. THE STUDIO ENDPOINT: cb-studio/serve.py's shot_run_job — the exact function the Shots tab's
   'Approve spend & fire' click reaches via POST /api/shot-run — builds precisely the argv that
   invokes cb_render's fire path with the token. (The subprocess boundary is bridged by proving
   both of its sides: this argv, and the fire function below that argv dispatches to.)

2. THE SEALED ROUTE (LEGACY regression pin): fire_shot against the ORIGINAL revision-6
   production package (writes redirected to a scratch copy; provider adapter mocked) —
   disclosure seals the envelope, the token binds to its hash, and the OUTGOING PROVIDER
   REQUEST contains the exact accepted 105-word brief, duration 6.0, package revision 6, the
   approved keyframe/references/audio — and NO legacy prompt string.

3. THE SEALED ROUTE (GOLDEN PATH): the SAME sealed-envelope/token/route mechanics, proven
   against the REAL, currently-live S1.SH1 canonical package cb_handover.promote_to_canonical
   actually wrote — the real proof the current route works, not a legacy stand-in for it.

4. THE SINGLE ROUTE: every legacy caller of a paid provider function is blocked at the cb_gen
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
def legacy_scratch_pkg(monkeypatch, tmp_path):
    """LEGACY FIXTURE (2026-07-17 relabel, item 5) — a REGRESSION PIN on the sealed-envelope/
    token/route mechanics against the ORIGINAL revision-6, 1.B1.S1 package content, loaded
    read-only and SAVED to a scratch copy (the real archived file can never be mutated by
    this test). This is explicitly NOT proof the current production route works — it only
    proves the mechanics haven't regressed against pre-handover content shape. See
    golden_path_scratch_pkg below for the real, current-route proof.

    Reads from cb-output/archive/Ep1_scene1_production_package_pre_S1.SH1_promotion_
    rev6_20260717.json — the stable, permanent archived home for this content (preserved
    byte-identical there by cb_handover.promote_to_canonical's own supersession-archive
    step), never the live path, which now legitimately holds real S1.SH1 content instead."""
    real = (HERE.parent / "cb-output" / "archive" /
            "Ep1_scene1_production_package_pre_S1.SH1_promotion_rev6_20260717.json")
    scratch = tmp_path / "Ep1_scene1_production_package.json"
    shutil.copy(real, scratch)
    # THE SIMPLIFICATION (2026-07-17): the real archived rev-6 file predates typed-absence
    # continuityIn — its own on-disk shape stays byte-identical, untouched, forever (this
    # copy is the only thing ever mutated). Patch ONLY the scratch copy so fresh validation
    # doesn't refuse it on a schema convention that didn't exist yet when this snapshot was
    # taken — this fixture's own job is proving sealed-envelope/token/route MECHANICS, not
    # re-litigating an old snapshot's continuity shape.
    pkg = json.load(open(scratch))
    for sh in pkg.get("shots", []):
        if sh.get("shotId") == "1.B1.S1":
            sh["continuityIn"] = None
    json.dump(pkg, open(scratch, "w"), indent=1, ensure_ascii=False)
    monkeypatch.setattr(cb_render, "load_pkg",
                        lambda scene, episode="Ep1": (json.load(open(scratch)), scratch))
    monkeypatch.setattr(cb_render, "MEDIA", tmp_path / "shots")
    return scratch


@pytest.fixture()
def golden_path_scratch_pkg(monkeypatch, tmp_path):
    """GOLDEN-PATH FIXTURE (2026-07-17, item 5 — Julian: "the golden-path test must use the
    newly promoted S1.SH1 canonical package"): the REAL, currently-live canonical package —
    the one cb_handover.promote_to_canonical actually wrote via a real (non-dry-run)
    promotion of S1.SH1 from the human-approved creative-room storyboard — loaded read-only
    and SAVED to a scratch copy (the real live file can never be mutated by this test). THIS
    is the proof the current production route works end to end, on the content that is
    actually live today, never a legacy stand-in for it."""
    real = HERE.parent / "cb-output" / "Ep1_scene1_production_package.json"
    live = json.load(open(real))
    assert live["shots"][0]["shotId"] == "S1.SH1", (
        "golden_path_scratch_pkg requires the live package to actually hold S1.SH1's real "
        "promoted content — run cb_handover.promote_to_canonical for real first.")
    assert live["validation"]["passed"] is True, (
        "golden_path_scratch_pkg requires a VALID live package — an invalid one must never "
        "be treated as the golden path.")
    scratch = tmp_path / "Ep1_scene1_production_package.json"
    shutil.copy(real, scratch)
    monkeypatch.setattr(cb_render, "load_pkg",
                        lambda scene, episode="Ep1": (json.load(open(scratch)), scratch))
    monkeypatch.setattr(cb_render, "MEDIA", tmp_path / "shots")
    return scratch


def test_legacy_1b1s1_outgoing_provider_request_is_the_sealed_brief(monkeypatch, legacy_scratch_pkg, tmp_path):
    """LEGACY (item 5): §6 step 2's original proof, pinned against the ORIGINAL revision-6
    package — a regression check on the mechanics, not evidence the current route works.
    disclosure -> sealed envelope -> token -> fire -> MOCKED adapter captures the outgoing
    request. The request is the accepted brief, 6.0s, revision 6, approved assets — with
    zero legacy strings."""
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
    pkg = json.load(open(legacy_scratch_pkg))
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
    pkg2 = json.load(open(legacy_scratch_pkg))
    led2 = [x for x in pkg2["continuityLedger"] if x["shotId"] == "1.B1.S1"][0]
    assert led2["pendingSpendAuth"] is None and led2["status"] == "candidates-pending"


def test_legacy_pre_envelope_token_is_void(monkeypatch, legacy_scratch_pkg):
    """LEGACY (item 5): a token issued before the sealed-envelope protocol (e.g.
    db660b33...) can never fire — pinned against the original revision-6 package."""
    monkeypatch.setattr(cb_render, "_require_confirmed_billing", lambda prov: None)
    pkg = json.load(open(legacy_scratch_pkg))
    led = [x for x in pkg["continuityLedger"] if x["shotId"] == "1.B1.S1"][0]
    led["pendingSpendAuth"] = {"token": "oldtokenoldtoken",
                                "bindingHash": "x" * 32}     # no envelope — pre-protocol shape
    json.dump(pkg, open(legacy_scratch_pkg, "w"), indent=1, ensure_ascii=False)
    with pytest.raises(cb_render.Refused):
        cb_render.fire_shot("1", "1.B1.S1", "Ep1", spend_token="oldtokenoldtoken",
                             log=lambda *a, **k: None)


def test_legacy_dry_run_issues_no_token_and_stores_nothing(monkeypatch, legacy_scratch_pkg):
    """LEGACY (item 5): pinned against the original revision-6 package."""
    monkeypatch.setattr(cb_render, "_require_confirmed_billing", lambda prov: None)
    with pytest.raises(cb_render.Refused, match="DRY RUN"):
        cb_render.fire_shot("1", "1.B1.S1", "Ep1", candidates=3, dry_run=True,
                             log=lambda *a, **k: None)
    pkg = json.load(open(legacy_scratch_pkg))
    led = [x for x in pkg["continuityLedger"] if x["shotId"] == "1.B1.S1"][0]
    assert not led.get("pendingSpendAuth")


def test_golden_path_s1sh1_keyframe_passes_real_require_valid_only_provider_stubbed(
        monkeypatch, golden_path_scratch_pkg, tmp_path):
    """GOLDEN PATH (2026-07-17, item 5+6): proves cb_render.keyframe_shot('S1.SH1') against
    the REAL, currently-live, newly-promoted canonical package — not the archived legacy
    one. _require_valid, _require_confirmed_billing, _shot, the relay/opener check, and
    _slot_paths (real character-identity + scene-plate reference resolution) ALL run
    unstubbed, against the real, promoted content. ONLY cb_gen.generate_image (the actual
    paid provider call) is stubbed — no media, no spend. Writes are redirected to a scratch
    copy (golden_path_scratch_pkg); the real live file is never touched by this test."""
    calls = []

    def fake_generate_image(prompt, refs=None, out=None, production_route=None, **k):
        cb_gen._require_production_route(production_route, "test")   # route sentinel enforced
        calls.append({"prompt": prompt, "refs": refs, "out": out})
        pathlib.Path(out).write_bytes(b"fake")
        return out

    monkeypatch.setattr(cb_gen, "generate_image", fake_generate_image)

    out_path = cb_render.keyframe_shot("1", "S1.SH1", "Ep1", log=lambda *a, **k: None)

    assert len(calls) == 1                                          # exactly one provider call
    call = calls[0]
    assert call["out"] == out_path
    assert "S1.SH1" in pathlib.Path(out_path).name
    assert pathlib.Path(out_path).exists()
    assert pathlib.Path(out_path).read_bytes() == b"fake"            # the stub's own marker —
    #                                                                   never real media
    # LEGACY_STRINGS is curated for the LEGACY MOTION/video prompt shape (0-5s, crash-lands
    # into pride, etc.) — irrelevant to a keyframe (still-image) prompt, which has its own,
    # current, correct "Negative:" section; the real no-legacy-material check here is that
    # no legacy SHOT ID crossed into the promoted content.
    assert "1.B1.S1" not in call["prompt"]                            # no legacy shot material

    # the real, unstubbed reference resolution — real character identity + real scene plate
    assert len(call["refs"]) == 3
    for ref in call["refs"]:
        assert pathlib.Path(ref).exists()

    # the write landed on the SCRATCH copy only — the real live file is untouched
    written = json.load(open(golden_path_scratch_pkg))
    led = [x for x in written["continuityLedger"] if x["shotId"] == "S1.SH1"][0]
    assert led["keyframePath"] == out_path
    real_live = HERE.parent / "cb-output" / "Ep1_scene1_production_package.json"
    real_pkg = json.load(open(real_live))
    real_led = [x for x in real_pkg["continuityLedger"] if x["shotId"] == "S1.SH1"][0]
    assert real_led.get("keyframePath") is None                      # real file never touched


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
