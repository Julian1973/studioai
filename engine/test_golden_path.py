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


def fire_keyframe(scene, shot_id, episode, log=None):
    """Drives cb_render.keyframe_shot's real two-phase disclose-then-confirm spend-token seal
    (2026-07-22, Julian's directive — "ensure the prompts I see in the studio are the exact
    prompts that go to the API... your mistakes have cost me money"; see keyframe_shot's own
    docstring and _keyframe_binding_hash's for the full forensic reasoning) in one call, for
    fixture code that isn't itself testing the disclosure step — mirrors this project's own
    established convention for fire_shot's identical two-phase contract. Never used by
    cb_render.py itself or any real Studio route; the real split stays the only path a
    human exercises."""
    log = log or (lambda *a, **k: None)
    try:
        R.keyframe_shot(scene, shot_id, episode, log=log)
    except R.Refused:
        pass
    pkg, _ = R.load_pkg(scene, episode)
    led = R._ledger(pkg, shot_id)
    auth = led.get("pendingKeyframeSpendAuth")
    if not auth:
        raise AssertionError(f"keyframe_shot({shot_id!r}) did not issue a spend token — "
                              f"it likely refused for an unrelated reason before reaching "
                              f"the seal")
    return R.keyframe_shot(scene, shot_id, episode, spend_token=auth["token"], log=log)


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
                  # cutPace is REQUIRED (2026-07-21) — the mandatory Director/Producer pace
                  # decision must fire on every shot; a single unbroken take is right for
                  # this fixture's own short gag.
                  cutPace="single_continuous_take", internalCuts=[],
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
    # THE SIMPLIFICATION (2026-07-17): the scene's true first shot has nothing to
    # inherit — typed absence (None), the same mechanical clear design_scene now applies.
    s1.continuityIn = None
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
    # THE STORYBOARD-SOURCED BEATS FIX (2026-07-22): _fresh_validation now reads its beats
    # from pkg["sourceStoryboard"]["path"] — the real storyboard that produced the package
    # — never a same-named-episode file discovered by an unrelated glob (see cb_render.
    # _beats_for_fresh_validation's own docstring for the real production bug this closes).
    # This fixture's own BEATS constant is reshaped into the storyboard's real field names
    # (beatId/exactDialogue) and written to a real scratch storyboard file so re-validation
    # still exercises real content, matching this suite's own stated job.
    sb_path = tmp / "cb-output" / "creative" / "EpT_scene9_storyboard.json"
    sb_path.parent.mkdir(parents=True, exist_ok=True)
    sb_beats = [{"beatId": b["beatCode"], "comedyMode": b.get("comedyMode"),
                 "exactDialogue": [c["dialogue"] for c in b.get("cuts", []) if c.get("dialogue")]}
                for b in BEATS]
    json.dump({"beats": sb_beats}, open(sb_path, "w"))
    pkg = {"episode": "EpT", "sceneNumber": "9", "shots": shots_out,
           "continuityLedger": [E._ledger_entry(s) for s in design.shots],
           "sourceStoryboard": {"path": str(sb_path)},
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
        self.conform_calls = []

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
        # stitch_scene (2026-07-21, JOIN ON LIVE MOTION scoped to this pipeline's own shot
        # grammar) now calls assemble_conformed for its real multi-clip output, alongside
        # assemble_picture for the RAW comparison baseline — same fake-concat contract as
        # assemble_picture above; this suite's own assertions only check clip order, never
        # real ffmpeg trim behaviour (that's cb_post's own test file's job).
        def assemble_conformed(clips, out, settle_trim=None, edge_frames=None):
            self.conform_calls.append({"clips": list(clips), "out": out, "settle_trim": settle_trim})
            pathlib.Path(out).write_bytes(b"".join(pathlib.Path(c).read_bytes() for c in clips))
            return out
        monkeypatch.setattr(R.cb_post, "assemble_conformed", assemble_conformed)
        monkeypatch.setattr(R.cb_post, "_dur", lambda p: 6.0)


def _seed_department_approval(scene, ep, shot_id, stage, output):
    """TEST-ONLY (2026-07-19, the department-gate hardening directive): seeds a CURRENT,
    approved department direction directly into the ledger — via the same
    _department_container/_department_candidate/_department_signature machinery
    decide_department itself uses, just without a real LLM call. This suite's own docstring
    already states its job (orchestration, validation, spending control, state transitions),
    never department preparation itself — that is test_cb_render_department_gate.py's job,
    exercising the real prepare_department/decide_department routes end to end with a
    mocked LLM. Every shot's approval is seeded once, up front, exactly the same way the
    Scene Look plate approval above is seeded directly via _save_scenelook_rec rather than
    through a real LLM call — matching this fixture's own already-established precedent."""
    pkg, path = R.load_pkg(scene, ep)
    context = R._department_context_for_freshness(pkg, scene, stage, shot_id, ep)
    work, save_fn = R._department_container(pkg, scene, shot_id, stage, ep)
    work["approved"] = R._department_candidate(stage, output, context, scene=scene,
                                                 shot_id=shot_id, pkg=pkg)
    save_fn()
    R._save(pkg, path)


def _seed_voice_and_cinematography(scene, ep):
    """Seeds voice + cinematography (opener shots only) approvals for every shot in the
    package, reusing each shot's OWN already-compiled legacy fields (keyframePrompt/
    dialogueLines) as the seeded department output — so every existing assertion in this
    file that checks the exact prompt/reference/audio text fired to a mocked provider still
    holds unchanged; only WHERE that text now has to come from (an approved department
    record, never a bare storyboard fallback) has changed, per THE CORE LAW. Animation is
    deliberately NOT seeded here — _department_context_for_freshness's own animation branch
    calls _anchor_for, which for an opener requires an ALREADY-APPROVED keyframe and for a
    relay requires its source shot ALREADY approved+harvested; neither exists this early in
    any test's own flow. See _seed_animation_for_shot below, called once that real
    dependency is actually satisfied — matching real production order exactly."""
    pkg, _ = R.load_pkg(scene, ep)
    for s in pkg["shots"]:
        shot_id = s["shotId"]
        if s.get("dialogueLines"):
            lines = [{"speaker": ln["speaker"], "exactDialogue": ln["exactText"],
                      "performedText": ln["exactText"]} for ln in s["dialogueLines"]]
            _seed_department_approval(scene, ep, shot_id, "voice",
                                       {"shotId": shot_id, "lines": lines,
                                        "doesItLand": "test"})
        if s["sourceType"] == "opener":
            _seed_department_approval(scene, ep, shot_id, "cinematography",
                                       {"shotId": shot_id, "providerPrompt": s["keyframePrompt"],
                                        "doesItLand": "test"})


def _seed_animation_for_shot(scene, ep, shot_id):
    """Seeds ONE shot's animation approval, reusing its own already-compiled seedancePrompt
    — called only once its real anchor dependency (an approved keyframe for an opener, or
    an approved+harvested source for a relay) is already satisfied, matching real
    production order. Kept as its own function (not folded into _seed_voice_and_
    cinematography) for exactly that reason."""
    pkg, _ = R.load_pkg(scene, ep)
    s = next(x for x in pkg["shots"] if x["shotId"] == shot_id)
    _seed_department_approval(scene, ep, shot_id, "animation",
                               {"shotId": shot_id, "providerPrompt": s["seedancePrompt"],
                                "doesItLand": "test"})


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
    # NOTE (2026-07-19): a fixed-filename "EpT_S9_plate.png" used to be written here — dead
    # since the 2026-07-18 production-safety directive moved _plate_path to read the Scene
    # Look sidecar's own APPROVED record instead of globbing a conventional filename (never
    # actually exercised by any test before tonight, since every test refused earlier at
    # _require_current_scenelook before reaching _plate_path at all). The real plate file is
    # created below, alongside the scenelook approval record it's read from.
    # THE SCENE LOOK CANON FALLBACK (2026-07-19): _compile_scenelook_prompt reads
    # {root}/shows/crystal-bears/canon/locations.json for episode "EpT" scene "9" — this
    # world has no such file by default, so every path through keyframe_shot (which always
    # calls _require_current_scenelook first) refused with "no canon environment data
    # found," unrelated to whatever each test actually exercises downstream. A minimal,
    # synthetic (not real-show) entry closes that gate the same way the real production
    # shows/crystal-bears/canon/locations.json now does for Ep1.
    canon_dir = tmp_path / "shows" / "crystal-bears" / "canon"
    canon_dir.mkdir(parents=True, exist_ok=True)
    json.dump({"EpT": {"9": {
        "look": "A synthetic test meadow with oversized flowers.",
        "lighting": "Warm test daylight.",
        "weather": "Clear.",
        "colorTemperature": "Warm.",
        "definingFeature": "A single tall test flower.",
    }}}, open(canon_dir / "locations.json", "w"))
    # keyframe_shot also hard-refuses without a CURRENT APPROVED Scene Look Plate
    # (_require_current_scenelook) — a separate gate from the canon-data one above. Approve
    # a synthetic plate via the real functions (never a hand-typed signature) so it can never
    # silently drift from what the compiler actually considers "current."
    plate_path = engine / "media" / "EpT_S9_scenelook.png"
    plate_path.write_bytes(b"SCENELOOK_PLATE")
    R._save_scenelook_rec({
        "approved": {"path": str(plate_path), "hash": R._sha256_file(plate_path),
                     "inputSignature": R._scenelook_input_signature("9", "EpT"),
                     "approvedAt": "2026-07-19T00:00:00", "reviewedBy": "test"},
        "candidate": None, "history": [],
    }, "9", "EpT")
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
    # THE LINEAGE CHECK, OUT OF SCOPE HERE ON PURPOSE (2026-07-17 state-integrity
    # checkpoint): _build_package hand-constructs a package directly through cb_engine's own
    # compilers — no creative-room storyboard file, no sourceStoryboard.md5, no revision at
    # all. This suite's own docstring already states its job: orchestration, validation,
    # spending control and state transitions, never storyboard-promotion lineage — real
    # lineage coverage lives in test_cb_render_lineage.py against a real storyboard/package
    # pair. Bypassing here is the same, already-established call as legacy_scratch_pkg's own
    # identical bypass in test_e2e_fire_route.py.
    monkeypatch.setattr(R, "_require_current_lineage", lambda pkg, scene, episode: None)
    _seed_voice_and_cinematography("9", "EpT")
    return prov, tmp_path, pkg_path


def _token(shot_id, scene="9", ep="EpT", candidates=3):
    """Run the disclosure step (refuses by design) and return the server-issued token."""
    with pytest.raises(R.Refused, match="SPEND NOT APPROVED"):
        R.fire_shot(scene, shot_id, ep, candidates=candidates, log=lambda *a, **k: None)
    return _led(scene, ep)[shot_id]["pendingSpendAuth"]["token"]


def _led(scene="9", ep="EpT"):
    pkg, _ = R.load_pkg(scene, ep)
    return {e["shotId"]: e for e in pkg["continuityLedger"]}


def _voice_and_approve(scene="9", ep="EpT", log=lambda *a, **k: None):
    """THE VOICE APPROVAL STEP (2026-07-19): fire_shot now hard-refuses a dialogue shot
    whose voice track exists but hasn't been explicitly approved (mirrors the pre-existing
    keyframe-approval gate) — voice_scene() alone (generate) is no longer enough to clear
    a dialogue shot for animation. Approves every dialogue shot's track in package order,
    matching how a real Studio session would review-then-approve each one."""
    R.voice_scene(scene, ep, log=log)
    pkg, _ = R.load_pkg(scene, ep)
    for s in pkg["shots"]:
        if s.get("dialogueLines"):
            R.approve_voice(scene, s["shotId"], ep, log=log)


# ── THE GOLDEN PATH ─────────────────────────────────────────────────────────────────────
def test_golden_path_script_to_scene_picture(world):
    prov, tmp, _ = world

    # Gate 4 — voice: exactly the locked words, exactly once, right voices
    R.voice_scene("9", "EpT", log=lambda *a, **k: None)
    assert len(prov.voice_calls) == 2
    texts = [(t["voice_id"], t["text"]) for c in prov.voice_calls for t in c["inputs"]]
    assert ("voice-fuzzby", "Nailed it.") in texts
    assert ("voice-zenny", "Fuzzby… why are you humming?") in texts
    R.approve_voice("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    R.approve_voice("9", "1.B1.S2", "EpT", log=lambda *a, **k: None)

    # Gate 5 — the TIMING SLATE assembles from real durations + real voice, before any
    # image money (it approves timing/dialogue only — never staging or rhythm)
    out = R.animatic_scene("9", "EpT", log=lambda *a, **k: None)
    assert pathlib.Path(out).exists() and out.endswith("_timing_slate.mp4")
    assert len(prov.image_calls) == 0          # no paid image call yet — slates only

    # Gate 6 — the opener keyframe, reference-first, refs in the persisted slot order
    fire_keyframe("9", "1.B1.S1", "EpT")
    kf_call = prov.image_calls[-1]
    assert [os.path.basename(r) for r in kf_call["refs"]] == \
           ["CB_Fuzzby.jpeg", "CB_Zenny.jpeg", "EpT_S9_scenelook.png"]
    assert "nailed it" not in kf_call["prompt"].lower()          # Law 6

    # Gate 6b (2026-07-17 state-integrity checkpoint) — a generated-but-unapproved
    # keyframe candidate can never anchor a fire; Julian's own review approves it first,
    # exactly the lifecycle a real Studio session goes through before any spend.
    R.approve_keyframe("9", "1.B1.S1", "EpT", reviewed_by="TestReviewer", log=lambda *a, **k: None)
    # THE CORE LAW (2026-07-19): fire_shot's own paid route now hard-requires a CURRENT,
    # approved Animation Direction for this exact shot — seeded here, now that its real
    # anchor dependency (the just-approved keyframe) actually exists, matching real
    # production order exactly.
    _seed_animation_for_shot("9", "EpT", "1.B1.S1")

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
    # anchor first: the APPROVED keyframe's own stored path (never renamed to a fixed
    # "_keyframe.png" — approve_keyframe keeps the candidate's own unique-hash filename,
    # matching this codebase's own "never rename an artefact, only what's approved of it
    # changes" convention; a literal ".endswith('_keyframe.png')" was stale against that)
    assert f1["image_urls"][0].endswith(_led()["1.B1.S1"]["keyframeApproval"]["path"])
    assert [os.path.basename(u) for u in f1["image_urls"][1:]] == \
           ["CB_Fuzzby.jpeg", "CB_Zenny.jpeg", "EpT_S9_scenelook.png"]
    assert f1["audio_urls"] and f1["audio_urls"][0].endswith("_vo.mp3")
    assert "nailed it" not in f1["prompt"].lower()                # Law 6 at fire time
    # 2026-07-19 (THE HANDLE DOCTRINE, Julian: "we want 15 second clips with 2 seconds at
    # the end to have for editing" — raised after a real take overran its own shorter
    # designed clip with zero warning): cb_render._handle_duration now overrides the
    # design-time durationSec with max(HANDLE_TOTAL=15, real_vo_duration+HANDLE_SETTLE=2)
    # before the fire ever reaches the provider — this fixture's own mocked VO is a real
    # 1.5s silent take, so 15.0 (the floor) is what should ship. This is NOT a regression of
    # the old "never a blind 'auto' literal" guarantee this assertion used to pin — 15 here
    # is a genuinely computed, audio-aware value (it would stretch past 15 for a longer real
    # take, per test_cb_render.py), never a hardcoded literal ignoring the shot's content.
    assert f1["duration"] == "15"
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

    # relay batch fires from the SELECTED candidate's harvested final frame — 1.B1.S2's own
    # animation direction can only be seeded now that its source (S1) is approved+harvested,
    # matching _anchor_for's own real relay dependency exactly.
    _seed_animation_for_shot("9", "EpT", "1.B1.S2")
    t2 = _token("1.B1.S2")
    R.next_shot("9", "EpT", spend_token=t2, log=lambda *a, **k: None)   # 1.B1.S2 batch
    f2 = prov.fire_calls[-1]
    assert f2["image_urls"][0].endswith("EpT_1.B1.S1_final_frame.png")   # THE relay contract
    R.approve_shot("9", "1.B1.S2", 1, "EpT", log=lambda *a, **k: None)

    _seed_animation_for_shot("9", "EpT", "1.B1.S3")
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

    # JOIN ON LIVE MOTION, scoped to THIS pipeline's own 4-8s shot grammar (2026-07-21):
    # the real, final picture goes through assemble_conformed with settle_trim PINNED to
    # 0.0 — never the old beat-pipeline's ~2s default, which would eat a large fraction of
    # a short shot's own content. A raw, untrimmed comparison baseline is written alongside.
    assert len(prov.conform_calls) == 1
    assert prov.conform_calls[0]["settle_trim"] == 0.0
    assert len(prov.conform_calls[0]["clips"]) == 3
    raw = pathlib.Path(pic).with_name(pathlib.Path(pic).name.replace(
        "_shots_picture.mp4", "_shots_picture_RAW.mp4"))
    assert raw.exists()

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
    _voice_and_approve()
    # THE CORE LAW (2026-07-19): under the department-gate hardening, this refusal now
    # surfaces one step EARLIER than it used to — no Animation Direction could ever have
    # been legitimately prepared for a relay shot whose source isn't approved+harvested yet
    # (_anchor_for's own real relay dependency, which _seed_animation_for_shot/prepare_
    # department both hit identically), so fire_shot refuses on THE CORE LAW's own message
    # rather than reaching the older, deeper "source not approved" check inside _anchor_for
    # — the underlying guarantee (a relay can never fire before its source is approved) is
    # unchanged and, if anything, enforced earlier and more strongly than before.
    with pytest.raises(R.Refused, match="requires an APPROVED"):
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
    fire_keyframe("9", "1.B1.S1", "EpT")
    R.approve_keyframe("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    # THE CORE LAW (2026-07-19): to isolate testing Law 5's OWN refusal (dialogue with no
    # approved voice), the shot must otherwise be fully department-ready — an Animation
    # Direction seeded here, matching real production order (its anchor, the keyframe, is
    # now approved). Without this, fire_shot's own animation-direction gate would refuse
    # first, for an unrelated reason, and this test would no longer prove what it says it
    # proves.
    _seed_animation_for_shot("9", "EpT", "1.B1.S1")
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
    _voice_and_approve()
    fire_keyframe("9", "1.B1.S1", "EpT")
    R.approve_keyframe("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    _seed_animation_for_shot("9", "EpT", "1.B1.S1")
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
    _voice_and_approve()
    fire_keyframe("9", "1.B1.S1", "EpT")
    R.approve_keyframe("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    _seed_animation_for_shot("9", "EpT", "1.B1.S1")
    tok = _token("1.B1.S1")
    # a targeted correction: the prompt text changes after the disclosure
    pkg = json.loads(pathlib.Path(pkg_path).read_text())
    pkg["shots"][0]["seedancePrompt"] += " Revised."
    pathlib.Path(pkg_path).write_text(json.dumps(pkg, indent=1))
    with pytest.raises(R.Refused, match="STALE"):
        R.fire_shot("9", "1.B1.S1", "EpT", spend_token=tok, log=lambda *a, **k: None)
    assert len(prov.fire_calls) == 0
    # THE CORE LAW (2026-07-19): under the department-gate hardening, the revised storyboard
    # prompt ALSO makes the seeded Animation Direction itself go stale (its own sourceHash
    # was computed against the pre-revision shot dict) — a genuinely correct, stricter
    # consequence: the Animation Director must re-review a beat whose underlying prompt
    # changed, not just re-disclose against it. Re-seeding here (standing in for a real
    # re-prepare + re-approve through the Studio) is what actually unblocks the next
    # disclosure — without this, a fresh SPEND-NOT-APPROVED disclosure could never surface,
    # since fire_shot's own animation-direction gate would keep refusing first.
    _seed_animation_for_shot("9", "EpT", "1.B1.S1")
    # the next disclosure records the revision and re-validates from scratch
    _token("1.B1.S1")
    d = _led()["1.B1.S1"]["pendingSpendAuth"]["disclosure"]
    assert d["rerollOfUnchangedPackage"] is False


def test_batch_resume_is_idempotent_never_repays(world):
    """Protection 2: two of three complete, the third fails -> resume generates ONLY the
    missing candidate under the ORIGINAL token; completed candidates never regenerate."""
    prov, tmp, _ = world
    _voice_and_approve()
    fire_keyframe("9", "1.B1.S1", "EpT")
    R.approve_keyframe("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    _seed_animation_for_shot("9", "EpT", "1.B1.S1")
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
