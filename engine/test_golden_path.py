#!/usr/bin/env python3
"""test_golden_path.py — THE GOLDEN PATH, outcome-based, zero cost.

WHAT THESE TESTS PROVE — AND WHAT THEY NEVER PROVE (Julian's probabilistic-model
correction, 2026-07-16): this suite proves ORCHESTRATION, VALIDATION, SPENDING CONTROL and
STATE TRANSITIONS. Seedance is a probabilistic generator; nothing here is, or can be,
evidence of creative render quality — the product is an approved shot selected from a
controlled candidate set by a human, never a "perfect prompt".

Runs the entire hybrid pipeline end to end against a synthetic 3-shot scene with every
provider mocked: design-package -> voice -> timing slate -> keyframe -> candidate batch ->
select -> relay batch (off the harvested frame) -> stitch. Asserts:

  1. every locked dialogue line reaches the voice provider exactly once, word for word,
     in the right character's voice — and never reaches any render prompt (Law 6)
  2. a candidate batch REFUSES without explicit spend approval, and with it generates N
     candidates from the IDENTICAL prompt/references/audio, anchor first, in slot order
  3. approval selects ONE candidate, archives the rest, harvests its final frame; a relay
     batch fires from that frame — and refuses when the source is not approved
  4. a failed-validation package cannot fire anything
  5. a pending batch cannot be re-fired past
  6. batch rejection archives everything, the reroll uses the UNCHANGED package, and two
     failed batches hard-stop the shot as model-limited
  7. the stitched scene picture contains every approved shot, in order

    pytest test_golden_path.py -q
"""
import json, os, pathlib, shutil
import pytest

import cb_engine as E
import cb_render as R


# ── the synthetic scene: opener w/ dialogue, relay w/ dialogue, silent relay ────────────
CFG = {"Fuzzby": {"sizeRank": 2, "avoid": "bee", "voiceId": "voice-fuzzby",
                   "anchor": "media/refs/CB_Fuzzby.jpeg"},
       "Zenny": {"sizeRank": 3, "avoid": "bee", "voiceId": "voice-zenny",
                  "anchor": "media/refs/CB_Zenny.jpeg"}}

BEATS = [
    {"beatCode": "1.B1", "comedyMode": "BIG", "storyBeat": "The crash gag.",
     "cuts": [{"framing": "wide", "action": "Fuzzby rockets.",
               "dialogue": "FUZZBY: Nailed it.", "delivery": "proud"},
              {"framing": "two", "action": "Zenny deadpans.",
               "dialogue": "ZENNY: Fuzzby… why are you humming?", "delivery": "dry"}]},
]


def _state(chars, marks=()):
    return E.ContinuityState(lighting="warm", cameraSide="left", characters=[
        E.CharacterState(character=c, screenZone="frame-left", facing="right",
                          pose="hover", expression="bright",
                          visibleMarks=list(marks), heldProps=[]) for c in chars])


def _mkshot(shot_id, source, src_id, lines, binding, staging=None):
    return E.Shot(shotId=shot_id, beatCode="1.B1", durationSec=6.0, purpose="the gag",
                  performanceAssignment="Fuzzby rockets past, clips the leaf, rebounds proudly.",
                  camera="Wide tracking, bee height", openingPose="Fuzzby outside the flower, wound up",
                  sourceType=source, sourceShotId=src_id,
                  cutInMotivation=None if src_id is None and source == "opener" and shot_id.endswith("S1") else "matched action",
                  dialogueBinding=binding, dialogueLines=lines,
                  visualPayoff="He nearly grazes the leaf", physicalStaging=staging,
                  prohibited=[], charactersInFrame=["Fuzzby", "Zenny"],
                  continuityIn=_state(["Fuzzby", "Zenny"]),
                  continuityOut=_state(["Fuzzby", "Zenny"], marks=["pollen dust"])
                  if shot_id.endswith("S1") else
                  E.ContinuityState(lighting="warm", cameraSide="left", characters=[
                      E.CharacterState(character=c, screenZone="frame-left", facing="right",
                                        pose="hover", expression="bright",
                                        visibleMarks=["pollen dust"], heldProps=[])
                      for c in ["Fuzzby", "Zenny"]]))


def _line(speaker, text, start, end):
    return E.DialogueLine(speaker=speaker, exactText=text, delivery="in character",
                          startSec=start, endSec=end)


STAGING = E.PhysicalStaging(staysVisible="full silhouette", contactAndWeight="chest to leaf",
                             payoffShape="upward pop", prohibitedStaging=["vanishing"])


def _build_package(tmp, valid=True):
    """Design + compile a real package through cb_engine's own compilers (no LLM — the
    design object is constructed directly), then place it where cb_render loads it."""
    s1 = _mkshot("1.B1.S1", "opener", None,
                 [_line("Fuzzby", "Nailed it.", 1.0, 2.5)],
                 "FUZZBY speaks with breathless pride", staging=STAGING)
    # s2's continuityIn must carry s1's marks (pollen dust) for the validator
    s2 = _mkshot("1.B1.S2", "relay", "1.B1.S1",
                 [_line("Zenny", "Fuzzby… why are you humming?", 1.0, 3.5)],
                 "ZENNY speaks with dry deadpan")
    s2.continuityIn = E.ContinuityState(lighting="warm", cameraSide="left", characters=[
        E.CharacterState(character=c, screenZone="frame-left", facing="right", pose="hover",
                          expression="bright", visibleMarks=["pollen dust"], heldProps=[])
        for c in ["Fuzzby", "Zenny"]])
    s3 = _mkshot("1.B1.S3", "relay", "1.B1.S2", [], None)
    s3.continuityIn = s2.continuityOut.model_copy(deep=True)
    design = E.SceneShotList(
        statement=E.DirectorStatement(audienceFeeling="joy", whoseScene="Fuzzby",
                                       emotionalChange="pride", theLaugh="the crash",
                                       visualSurprise="the leaf", carryForward="the hum"),
        shots=[s1, s2, s3])
    report = E.validate_scene_design(design, BEATS, CFG)
    assert report["passed"], report["issues"]

    shots_out = []
    for sh in design.shots:
        prompt, wc, slots = E.compile_shot_contract(sh, {}, CFG)
        rec = sh.model_dump()
        rec.update(seedancePrompt=prompt, promptWords=wc, referenceSlots=slots,
                   audioBrief=E.compile_audio_brief(sh))
        if sh.sourceType == "opener":
            kf, kwc, kslots = E.compile_keyframe_prompt(sh, {}, CFG)
            rec.update(keyframePrompt=kf, keyframePromptWords=kwc,
                       keyframeReferenceSlots=kslots)
        shots_out.append(rec)
    pkg = {"episode": "EpT", "sceneNumber": "9", "shots": shots_out,
           "continuityLedger": [E._ledger_entry(s) for s in design.shots],
           "validation": report if valid else {"passed": False, "issues": [
               {"severity": "ERROR", "code": "SYNTH", "path": "x", "message": "forced"}]}}
    out = tmp / "cb-output" / "EpT_scene9_production_package.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(pkg, open(out, "w"), indent=1)
    return out


# ── the mocked provider estate — records every call, spends nothing ─────────────────────
class Providers:
    def __init__(self):
        self.voice_calls, self.image_calls, self.fire_calls = [], [], []

    def install(self, monkeypatch, tmp):
        def eleven_dialogue(inputs, out="vo.mp3", **k):
            self.voice_calls.append({"inputs": inputs, "out": out})
            # a REAL (silent) mp3 — the animatic runs genuine ffmpeg over this file, so the
            # mock must produce decodable audio, not a byte stub
            import subprocess as sp
            sp.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                    "-t", "1.5", "-q:a", "9", out], check=True, capture_output=True)
            return out
        def generate_image(prompt, refs=None, out="kf.png", **k):
            self.image_calls.append({"prompt": prompt, "refs": refs, "out": out})
            pathlib.Path(out).write_bytes(b"PNG")
            return out
        def _fal_upload(path):
            return f"url://{path}"
        def generate_video_seedance_ref(prompt, image_urls, audio_urls=None, out="c.mp4", **k):
            self.fire_calls.append({"prompt": prompt, "image_urls": image_urls,
                                     "audio_urls": audio_urls, "out": out, **k})
            pathlib.Path(out).write_bytes(b"MP4:" + os.path.basename(out).encode())
            return out
        def last_frame(clip, out="last.png"):
            pathlib.Path(out).write_bytes(b"FRAME:" + os.path.basename(clip).encode())
            return out
        monkeypatch.setattr(R.cb_gen, "eleven_dialogue", eleven_dialogue)
        monkeypatch.setattr(R.cb_gen, "generate_image", generate_image)
        monkeypatch.setattr(R.cb_gen, "_fal_upload", _fal_upload)
        monkeypatch.setattr(R.cb_gen, "generate_video_seedance_ref", generate_video_seedance_ref)
        monkeypatch.setattr(R.cb_gen, "last_frame", last_frame)
        def assemble_picture(clips, out):
            pathlib.Path(out).write_bytes(b"".join(pathlib.Path(c).read_bytes() for c in clips))
            return out
        monkeypatch.setattr(R.cb_post, "assemble_picture", assemble_picture)
        monkeypatch.setattr(R.cb_post, "_dur", lambda p: 6.0)


@pytest.fixture()
def world(monkeypatch, tmp_path):
    """A fully-isolated world mirroring the real repo layout (root/cb-output + root/engine/
    media): package, refs, plate, characters config, mocked providers."""
    prov = Providers()
    prov.install(monkeypatch, tmp_path)
    engine = tmp_path / "engine"
    monkeypatch.setattr(R, "HERE", engine)
    monkeypatch.setattr(R, "MEDIA", engine / "media" / "shots")
    (engine / "media" / "refs").mkdir(parents=True)
    for c in CFG.values():
        (engine / c["anchor"]).write_bytes(b"REF")
    (engine / "media" / "EpT_S9_plate.png").write_bytes(b"PLATE")
    monkeypatch.setattr(R, "_characters_cfg", lambda: CFG)
    # confirmed billing profiles — the unconfirmed hard-block has its own dedicated test
    import cb_costs
    monkeypatch.setattr(cb_costs, "load_billing_profile", lambda provider=None: {
        "planConfirmed": True, "cadenceConfirmed": True, "plan": "test",
        "billingCadence": "monthly", "cyclePriceUsdExTax": 99.0, "creditsPerCycle": 600000,
        "creditsPerCharacter": {"eleven_v3": 1.0}, "pricingSource": "test",
        "effectiveDate": "2026-07-16"})
    # a real beat package in the tmp world so _fresh_validation re-validates for real
    beatpkg = {"beats": [dict(b, sceneNumber="9") for b in BEATS],
               "scenes": [{"sceneNumber": "9", "name": "test"}]}
    (tmp_path / "cb-output" / "EpT_test_beat_package.json").parent.mkdir(
        parents=True, exist_ok=True)
    json.dump(beatpkg, open(tmp_path / "cb-output" / "EpT_test_beat_package.json", "w"))
    import cb_engine as E2
    monkeypatch.setattr(E2, "HERE", tmp_path / "engine")
    pkg_path = _build_package(tmp_path)
    return prov, tmp_path, pkg_path


def _token(shot_id, scene="9", ep="EpT", candidates=3):
    """Run the disclosure step (refuses by design) and return the server-issued token."""
    with pytest.raises(R.Refused, match="SPEND NOT APPROVED"):
        R.fire_shot(scene, shot_id, ep, candidates=candidates, log=lambda *a, **k: None)
    return _led(scene, ep)[shot_id]["pendingSpendAuth"]["token"]


def _led(scene="9", ep="EpT"):
    pkg, _ = R.load_pkg(scene, ep)
    return {e["shotId"]: e for e in pkg["continuityLedger"]}


# ── THE GOLDEN PATH ─────────────────────────────────────────────────────────────────────
def test_golden_path_script_to_scene_picture(world):
    prov, tmp, _ = world

    # Gate 4 — voice: exactly the locked words, exactly once, right voices
    R.voice_scene("9", "EpT", log=lambda *a, **k: None)
    assert len(prov.voice_calls) == 2
    texts = [(t["voice_id"], t["text"]) for c in prov.voice_calls for t in c["inputs"]]
    assert ("voice-fuzzby", "Nailed it.") in texts
    assert ("voice-zenny", "Fuzzby… why are you humming?") in texts

    # Gate 5 — the TIMING SLATE assembles from real durations + real voice, before any
    # image money (it approves timing/dialogue only — never staging or rhythm)
    out = R.animatic_scene("9", "EpT", log=lambda *a, **k: None)
    assert pathlib.Path(out).exists() and out.endswith("_timing_slate.mp4")
    assert len(prov.image_calls) == 0          # no paid image call yet — slates only

    # Gate 6 — the opener keyframe, reference-first, refs in the persisted slot order
    R.keyframe_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    kf_call = prov.image_calls[-1]
    assert [os.path.basename(r) for r in kf_call["refs"]] == \
           ["CB_Fuzzby.jpeg", "CB_Zenny.jpeg", "EpT_S9_plate.png"]
    assert "nailed it" not in kf_call["prompt"].lower()          # Law 6

    # Gate 7 — SPEND CONTROL: no batch without a server-issued single-use token; the
    # disclosure is real, stored server-side, and bound to the exact package
    with pytest.raises(R.Refused, match="SPEND NOT APPROVED"):
        R.next_shot("9", "EpT", log=lambda *a, **k: None)
    assert len(prov.fire_calls) == 0                              # refusal spent NOTHING
    auth = _led()["1.B1.S1"]["pendingSpendAuth"]
    disc = auth["disclosure"]
    for k in ("candidateCount", "costPerCandidateUsd", "maxBatchCostUsd", "promptVersion",
               "bindingHash", "packageHash", "referenceSlots", "openingAnchor",
               "audioAsset", "shotDurationSec"):
        assert k in disc
    assert abs(disc["maxBatchCostUsd"] - 3 * disc["costPerCandidateUsd"]) < 1e-9

    # a fabricated token is refused — approval is server-side, never a client boolean
    with pytest.raises(R.Refused, match="unknown or already-used"):
        R.fire_shot("9", "1.B1.S1", "EpT", spend_token="deadbeef" * 4,
                     log=lambda *a, **k: None)

    # approved batch: 3 candidates, IDENTICAL prompt/refs/audio, anchor first, slot order
    R.next_shot("9", "EpT", spend_token=auth["token"], log=lambda *a, **k: None)  # 1.B1.S1
    batch1 = prov.fire_calls[-3:]
    assert len(batch1) == 3
    assert len({c["prompt"] for c in batch1}) == 1                # identical prompt
    assert len({tuple(c["image_urls"]) for c in batch1}) == 1     # identical references
    f1 = batch1[0]
    assert f1["image_urls"][0].endswith("_keyframe.png")          # anchor first
    assert [os.path.basename(u) for u in f1["image_urls"][1:]] == \
           ["CB_Fuzzby.jpeg", "CB_Zenny.jpeg", "EpT_S9_plate.png"]
    assert f1["audio_urls"] and f1["audio_urls"][0].endswith("_vo.mp3")
    assert "nailed it" not in f1["prompt"].lower()                # Law 6 at fire time
    assert f1["duration"] == "6"      # deferred re-home item 8: always the shot's explicit
    #                                   seconds, never 'auto' (the old 15s literals can't bite)
    # per-candidate review sheets: human criteria all null — machine never approves quality
    led1 = _led()["1.B1.S1"]
    assert len(led1["candidatePaths"]) == 3
    rev = json.loads(pathlib.Path(led1["candidatePaths"][1] + ".review.json").read_text())
    assert set(rev["criteria"]) == set(R.REVIEW_CRITERIA)
    assert all(v is None for v in rev["criteria"].values())

    # the token is SINGLE-USE (consumed) and nothing advances past a pending batch
    assert _led()["1.B1.S1"]["pendingSpendAuth"] is None
    with pytest.raises(R.Refused, match="pending"):
        R.next_shot("9", "EpT", log=lambda *a, **k: None)
    with pytest.raises(R.Refused, match="pending"):
        R.fire_shot("9", "1.B1.S1", "EpT", spend_token=auth["token"],
                     log=lambda *a, **k: None)

    # Gate 8 — select candidate 2; the others are archived, its final frame harvested
    R.approve_shot("9", "1.B1.S1", 2, "EpT", log=lambda *a, **k: None)
    led1 = _led()["1.B1.S1"]
    assert led1["approvedTake"].endswith("_c2.mp4")
    assert led1["harvestFrame"].endswith("_final_frame.png")
    arch = tmp / "engine" / "media" / "archive" / "shots_candidates"
    archived = [p.name for d in arch.iterdir() for p in d.iterdir()]
    assert "EpT_1.B1.S1_c1.mp4" in archived and "EpT_1.B1.S1_c3.mp4" in archived

    # relay batch fires from the SELECTED candidate's harvested final frame
    t2 = _token("1.B1.S2")
    R.next_shot("9", "EpT", spend_token=t2, log=lambda *a, **k: None)   # 1.B1.S2 batch
    f2 = prov.fire_calls[-1]
    assert f2["image_urls"][0].endswith("EpT_1.B1.S1_final_frame.png")   # THE relay contract
    R.approve_shot("9", "1.B1.S2", 1, "EpT", log=lambda *a, **k: None)

    t3 = _token("1.B1.S3")
    R.next_shot("9", "EpT", spend_token=t3, log=lambda *a, **k: None)   # silent 1.B1.S3
    f3 = prov.fire_calls[-1]
    assert f3["audio_urls"] is None                               # silent shot: no @Audio1
    assert f3["image_urls"][0].endswith("EpT_1.B1.S2_final_frame.png")
    R.approve_shot("9", "1.B1.S3", 1, "EpT", log=lambda *a, **k: None)

    # stitch — every approved shot, in order
    pic = R.stitch_scene("9", "EpT", log=lambda *a, **k: None)
    data = pathlib.Path(pic).read_bytes()
    i1 = data.find(b"1.B1.S1_c2.mp4"); i2 = data.find(b"1.B1.S2_c1.mp4")
    i3 = data.find(b"1.B1.S3_c1.mp4")
    assert -1 < i1 < i2 < i3

    # the evidence pack records the whole run: every shot approved, every asset present,
    # the stitched output named — nothing invented, nothing silently missing
    out = R.evidence_pack("9", "EpT", log=lambda *a, **k: None)
    pack = json.loads((pathlib.Path(out) / "evidence.json").read_text())
    assert len(pack["shots"]) == 3 and pack["stitchedOutput"]["exists"]
    for c in pack["shots"]:
        assert c["state"]["status"] == "approved"
        assert c["assets"]["take"]["exists"] and c["assets"]["harvestFrame"]["exists"]
        assert c["state"]["disclosure"]["promptVersion"]          # the spend record persists
        if c["input"]["dialogueLines"]:
            assert c["assets"]["voice"]["exists"]
    idx = (pathlib.Path(out) / "index.md").read_text()
    for sid in ("1.B1.S1", "1.B1.S2", "1.B1.S3"):
        assert sid in idx
    assert idx.count("status: **approved**") == 3
    # a silent shot's "voice: MISSING" is the truthful record, not a gap — but the
    # stitched output must never be missing after a full run
    assert "Stitched output: `EpT_Scene9_shots_picture.mp4`" in idx


def test_relay_refuses_before_source_is_approved(world):
    _, _, _ = world
    R.voice_scene("9", "EpT", log=lambda *a, **k: None)
    with pytest.raises(R.Refused, match="not approved"):
        R.fire_shot("9", "1.B1.S2", "EpT", log=lambda *a, **k: None)


def test_failed_validation_package_cannot_fire(world, monkeypatch, tmp_path):
    _build_package(tmp_path, valid=False)
    for fn in (lambda: R.voice_scene("9", "EpT"),
               lambda: R.next_shot("9", "EpT"),
               lambda: R.fire_shot("9", "1.B1.S1", "EpT")):
        with pytest.raises(R.Refused, match="validation"):
            fn()


def test_dialogue_shot_refuses_to_fire_without_voice(world):
    prov, _, _ = world
    R.keyframe_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    with pytest.raises(R.Refused, match="Law 5"):
        R.fire_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)


def test_missing_identity_reference_refuses_by_name(world, monkeypatch):
    bad = {k: dict(v) for k, v in CFG.items()}
    bad["Zenny"]["anchor"] = "media/refs/DOES_NOT_EXIST.jpeg"
    monkeypatch.setattr(R, "_characters_cfg", lambda: bad)
    R.voice_scene("9", "EpT", log=lambda *a, **k: None)
    with pytest.raises(R.Refused, match="Zenny"):
        R.keyframe_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)


def test_failure_ladder_unchanged_reroll_then_model_limited(world):
    """§5: rejection archives the whole batch; the reroll uses the UNCHANGED package (no
    auto-appended retake note, no new negatives); two failed batches hard-stop the shot."""
    prov, tmp, _ = world
    R.voice_scene("9", "EpT", log=lambda *a, **k: None)
    R.keyframe_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    t1 = _token("1.B1.S1", candidates=2)
    R.fire_shot("9", "1.B1.S1", "EpT", candidates=2, spend_token=t1,
                log=lambda *a, **k: None)
    first_prompt = prov.fire_calls[-1]["prompt"]
    first_binding = _led()["1.B1.S1"]["lastBatchBinding"]
    take = _led()["1.B1.S1"]["candidatePaths"][0]
    R.reject_shot("9", "1.B1.S1", "camera too loose on the crash",
                  category="action-timing", episode="EpT", log=lambda *a, **k: None)
    led = _led()["1.B1.S1"]
    assert led["status"] == "designed" and led["batchAttempts"] == 1
    assert led["rejections"][0]["category"] == "action-timing"
    arch_root = tmp / "engine" / "media" / "archive" / "shots_rejected"
    arch = [p for p in arch_root.iterdir() if p.is_dir()]
    assert arch and any(p.name == os.path.basename(take) for p in arch[0].iterdir())
    # the controlled reroll: IDENTICAL binding — the disclosure itself confirms the
    # package is unchanged (rerollOfUnchangedPackage), and the shipped prompt is identical
    t1b = _token("1.B1.S1", candidates=2)
    auth = _led()["1.B1.S1"]["pendingSpendAuth"]
    assert auth["disclosure"]["rerollOfUnchangedPackage"] is True
    assert auth["bindingHash"] == first_binding
    R.fire_shot("9", "1.B1.S1", "EpT", candidates=2, spend_token=t1b,
                log=lambda *a, **k: None)
    assert prov.fire_calls[-1]["prompt"] == first_prompt
    # second failed batch -> MODEL-LIMITED; a third fire refuses by name
    R.reject_shot("9", "1.B1.S1", "still no readable impact",
                  category="action-timing", episode="EpT", log=lambda *a, **k: None)
    assert _led()["1.B1.S1"]["status"] == "model-limited"
    with pytest.raises(R.Refused, match="MODEL-LIMITED"):
        R.fire_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    # and the walk refuses at it too — a model-limited shot blocks, never silently skipped
    with pytest.raises(R.Refused, match="model-limited"):
        R.next_shot("9", "EpT", log=lambda *a, **k: None)


def test_stitch_refuses_with_unapproved_shots(world):
    with pytest.raises(R.Refused, match="unapproved"):
        R.stitch_scene("9", "EpT", log=lambda *a, **k: None)


if __name__ == "__main__":
    import subprocess
    sys_exit = subprocess.call(["python3", "-m", "pytest", __file__, "-q"])
    raise SystemExit(sys_exit)


def test_stale_token_refused_when_package_changes(world):
    """Protection 1/4: anything changing between disclosure and generation voids the token
    — a revised package needs fresh validation and a fresh approval."""
    prov, tmp, pkg_path = world
    R.voice_scene("9", "EpT", log=lambda *a, **k: None)
    R.keyframe_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    tok = _token("1.B1.S1")
    # a targeted correction: the prompt text changes after the disclosure
    pkg = json.loads(pathlib.Path(pkg_path).read_text())
    pkg["shots"][0]["seedancePrompt"] += " Revised."
    pathlib.Path(pkg_path).write_text(json.dumps(pkg, indent=1))
    with pytest.raises(R.Refused, match="STALE"):
        R.fire_shot("9", "1.B1.S1", "EpT", spend_token=tok, log=lambda *a, **k: None)
    assert len(prov.fire_calls) == 0
    # the next disclosure records the revision and re-validates from scratch
    _token("1.B1.S1")
    d = _led()["1.B1.S1"]["pendingSpendAuth"]["disclosure"]
    assert d["rerollOfUnchangedPackage"] is False


def test_batch_resume_is_idempotent_never_repays(world):
    """Protection 2: two of three complete, the third fails -> resume generates ONLY the
    missing candidate under the ORIGINAL token; completed candidates never regenerate."""
    prov, tmp, _ = world
    R.voice_scene("9", "EpT", log=lambda *a, **k: None)
    R.keyframe_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    tok = _token("1.B1.S1")
    real = R.cb_gen.generate_video_seedance_ref
    calls = {"n": 0}
    def flaky(prompt, image_urls, out="c.mp4", **k):
        calls["n"] += 1
        if out.endswith("_c3.mp4") and calls["n"] <= 3:
            raise RuntimeError("provider 500")
        return real(prompt, image_urls, out=out, **k)
    import pytest as _pt
    orig = R.cb_gen.generate_video_seedance_ref
    R.cb_gen.generate_video_seedance_ref = flaky
    try:
        with _pt.raises(R.Refused, match="resumable"):
            R.fire_shot("9", "1.B1.S1", "EpT", spend_token=tok, log=lambda *a, **k: None)
        led = _led()["1.B1.S1"]
        assert led["batch"]["status"] == "generating"
        assert led["batch"]["done"] == [1, 2]
        assert led["batch"]["failed"][0]["candidate"] == 3          # failure persisted
        # a resume WITHOUT the original token is refused
        with _pt.raises(R.Refused, match="original spend token"):
            R.fire_shot("9", "1.B1.S1", "EpT", spend_token="deadbeef" * 4,
                         log=lambda *a, **k: None)
        # resume with the original token: ONLY candidate 3 generates
        before = calls["n"]
        R.fire_shot("9", "1.B1.S1", "EpT", spend_token=tok, log=lambda *a, **k: None)
        assert calls["n"] == before + 1                             # one call, no repays
        assert _led()["1.B1.S1"]["status"] == "candidates-pending"
        assert len(_led()["1.B1.S1"]["candidatePaths"]) == 3
    finally:
        R.cb_gen.generate_video_seedance_ref = orig


def test_unconfirmed_billing_profile_hard_blocks_all_paid_generation(world, monkeypatch):
    """Protection 5: an unconfirmed billing profile is a REFUSAL, never a warning."""
    import cb_costs
    monkeypatch.setattr(cb_costs, "load_billing_profile",
                         lambda provider=None: {"planConfirmed": False,
                                                 "cadenceConfirmed": True})
    with pytest.raises(R.Refused, match="UNCONFIRMED"):
        R.voice_scene("9", "EpT", log=lambda *a, **k: None)
    with pytest.raises(R.Refused, match="UNCONFIRMED"):
        R.keyframe_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    with pytest.raises(R.Refused, match="UNCONFIRMED"):
        R.fire_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
