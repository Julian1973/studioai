#!/usr/bin/env python3
"""test_cb_render_department_gate.py — THE ZERO-SPEND PROOF (item 8 of Julian's 2026-07-19
department-gate hardening directive): exercises the REAL cb_render routes — the exact
functions cb-studio/serve.py's HTTP handlers call — against a disposable production
package, with only the network-facing choke points mocked (cb_llm.structured for every
department consult, cb_gen's actual provider calls for keyframe/voice/animation/scenelook
generation). No approval JSON is ever hand-edited directly — every approved/candidate
record in this file is produced by calling the real prepare_department/decide_department
functions, exactly as a real Studio click would.

Confirmed forensic root cause this whole directive exists to close: _resolve_seedance_
prompt() silently fell back to shot["seedancePrompt"] whenever no approved Animation
Direction existed — five real Seedance candidates fired ($15.47) with the Animation
Director never having run. Every test below proves a specific piece of THE CORE LAW
("no current approved department direction = no disclosure authorisation = no provider
call") is now structurally impossible to bypass.

    pytest test_cb_render_department_gate.py -q
"""
import json
import pathlib
import re
import shutil
import sys
import time

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cb_render as R
import cb_departments
import cb_gen


CFG = {"Fuzzby": {"sizeRank": 2, "avoid": "bee", "voiceId": "voice-fuzzby",
                   "anchor": "media/refs/CB_Fuzzby.jpeg"},
       "Zenny": {"sizeRank": 3, "avoid": "bee", "voiceId": "voice-zenny",
                  "anchor": "media/refs/CB_Zenny.jpeg"}}


def _formula_prompt(action, line="Nailed it.", speaker="FUZZBY"):
    """A minimal, valid Gold-Build FORMULA prompt (2026-07-24 — the shape
    cb_render.check_formula_structure now hard-requires at prepare/save/fire): header when
    dialogue exists (@Audio1 declared the sole source — the spoken WORDS never appear,
    THE SH1 KEEPER STANDARD, 2026-07-25), a labelled 'Shot 1:' segment carrying the action
    and a performance note naming @Audio1, a closing HOLD tail, no duration text. Every seeded/mocked animation
    prompt in this suite must be this shape or the real gates refuse it — which is exactly
    the production contract these tests exercise."""
    header = ("ENGLISH DIALOGUE ONLY, spoken in English. Use @Audio1 as the sole source of "
              "dialogue, wording, voice, performance and timing.\n\n") if line else ""
    dlg = f" {speaker.title()} performs their vocal beat from @Audio1." if line else ""
    return (header
            + f"Shot 1: Close-up, 85mm, handheld drift. {action}{dlg} His pride "
            + "drives the speed of the move; his grin is held one beat too long — "
            + "the comedy hinge. He nearly grazes the leaf on the way past.\n\n"
            # delivers the fixture's declared feltIntent AND its visualPayoff — both
            # are gated fields, so a canned GOOD prompt has to honour both.
            + "They hold the look, about 2 seconds of silence, no more dialogue.")


# the redesign-recovery tests change the shot's own locked line first, then re-approve a
# genuinely different Animation Direction — the formula gate requires that NEW line inline
# verbatim in the re-approved card, so the redesign prompt carries it.
_REDESIGN_LINE = "A completely different line now."
_REDESIGN_PROMPT = _formula_prompt(
    "genuinely different approved redesign action, slowed into a held closing beat, "
    "near-still", line=_REDESIGN_LINE)


def _char_state(marks=()):
    return {"character": "Fuzzby", "screenZone": "frame-left", "facing": "right",
            "pose": "hover", "expression": "bright", "visibleMarks": list(marks),
            "heldProps": []}


def _build_shot(shot_id, source_type, source_shot_id, dialogue):
    # THE REAL cb_engine.Shot SCHEMA, IN FULL (2026-07-19 fix — found while running this
    # exact test): fire_shot's own PROTECTION 4 (_fresh_validation) re-loads and re-
    # validates the package against cb_engine.Shot at every disclosure, so a test package
    # must satisfy that real schema end to end, not just cb_render's own looser reads.
    return {
        "shotId": shot_id, "beatCode": "1.B1", "sourceType": source_type,
        "sourceShotId": source_shot_id, "durationSec": 6.0, "purpose": "the gag",
        "performanceAssignment": "Fuzzby rockets past, clips the leaf, rebounds proudly.",
        "camera": "Wide tracking, bee height",
        "openingPose": "Fuzzby outside the flower, wound up",
        "seedancePrompt": "the storyboard's OWN compiled prose — must never reach the "
                          "provider directly on the animation route, per THE CORE LAW",
        "promptWords": 20, "referenceSlots": {"@图1": "Fuzzby", "@图2": "Zenny"},
        "keyframeReferenceSlots": {"@图1": "Fuzzby", "@图2": "Zenny"},
        "keyframePrompt": "the storyboard's own compiled keyframe prose",
        "keyframePromptWords": 12,
        "visualPayoff": "He nearly grazes the leaf", "prohibited": [],
        # THE INTENT ENGINE PIN (2026-07-25): a stated purpose on the shot must reach the
        # Director's own animation charge. The first wiring read the context's top level,
        # found nothing (the shot nests under "shot"), and a broad except swallowed the
        # miss — the suite stayed green while the whole point of the engine silently never
        # shipped. This field + the assertion below make that miss a test failure forever.
        "feltIntent": "His pride drives the speed; the grin held too long is the comedy hinge.",
        "dialogueLines": dialogue, "charactersInFrame": ["Fuzzby", "Zenny"],
        "continuityIn": {"lighting": "warm", "cameraSide": "left",
                         "characters": [_char_state()]},
        "continuityOut": {"lighting": "warm", "cameraSide": "left",
                          "characters": [_char_state(marks=["pollen dust"])]},
        # cutPace is a REQUIRED field (2026-07-21 fix) — the Director/Producer's
        # mandatory pace decision must fire on every shot, no default.
        "cutPace": "single_continuous_take", "cutPaceReason": "test fixture — a single "
                   "unbroken take is sufficient for this synthetic gate-mechanics check.",
        "internalCuts": [],
    }


@pytest.fixture()
def world(monkeypatch, tmp_path):
    """A fully-isolated, disposable production package + media tree — mirrors test_golden_
    path.py's own established fixture shape. Only cb_gen's provider-facing functions and
    cb_llm.structured (the ONE choke point every department consult in cb_departments.py
    calls through) are mocked; cb_departments.py's own system-prompt construction (which
    genuinely calls load_runtime_skill against the real repo SKILL.md files) runs for real,
    proving item 8's "the correct runtime skill was genuinely loaded"."""
    provider_calls = {"image": [], "video": [], "voice": []}

    def fake_generate_image(prompt, refs=None, out="kf.png", **k):
        provider_calls["image"].append({"prompt": prompt, "refs": refs})
        pathlib.Path(out).write_bytes(b"PNG")
        return out
    def fake_video(prompt, image_urls, audio_urls=None, out="c.mp4", **k):
        provider_calls["video"].append({"prompt": prompt, "image_urls": image_urls,
                                          "audio_urls": audio_urls})
        pathlib.Path(out).write_bytes(b"MP4")
        return out
    def fake_voice(inputs, out="vo.mp3", **k):
        provider_calls["voice"].append({"inputs": inputs})
        pathlib.Path(out).write_bytes(b"ID3fake")
        return out
    monkeypatch.setattr(cb_gen, "generate_image", fake_generate_image)
    monkeypatch.setattr(cb_gen, "generate_video_seedance_ref", fake_video)
    monkeypatch.setattr(cb_gen, "eleven_dialogue", fake_voice)
    monkeypatch.setattr(cb_gen, "_fal_upload", lambda p: f"file://{p}")
    monkeypatch.setattr(cb_gen, "last_frame", lambda clip, out="last.png": (
        pathlib.Path(out).write_bytes(b"FRAME"), out)[1])

    engine = tmp_path / "engine"
    monkeypatch.setattr(R, "HERE", engine)
    monkeypatch.setattr(R, "MEDIA", engine / "media" / "shots")
    (engine / "media" / "refs").mkdir(parents=True)
    for c in CFG.values():
        (engine / c["anchor"]).write_bytes(b"REF")
    monkeypatch.setattr(R, "_characters_cfg", lambda: CFG)
    monkeypatch.setattr(R, "_require_current_scenelook", lambda scene, episode="EpT": None)
    monkeypatch.setattr(R, "_require_confirmed_billing", lambda provider: None)

    canon_dir = tmp_path / "shows" / "crystal-bears" / "canon"
    canon_dir.mkdir(parents=True, exist_ok=True)
    json.dump({"EpT": {"9": {"look": "A synthetic test meadow.", "lighting": "Warm test daylight.",
                              "weather": "Clear.", "colorTemperature": "Warm.",
                              "definingFeature": "A single test flower."}}},
              open(canon_dir / "locations.json", "w"))

    plate_path = engine / "media" / "Ep1_S9_scenelook.png"
    plate_path.write_bytes(b"SCENELOOK_PLATE")
    R._save_scenelook_rec({
        "approved": {"path": str(plate_path), "hash": R._sha256_file(plate_path),
                     "inputSignature": R._scenelook_input_signature("9", "EpT"),
                     "approvedAt": "2026-01-01T00:00:00", "reviewedBy": "test"},
        "candidate": None, "history": [],
    }, "9", "EpT")

    s1 = _build_shot("1.B1.S1", "opener", None,
                      [{"speaker": "Fuzzby", "exactText": "Nailed it.", "delivery": "proud",
                        "startSec": 1.0, "endSec": 2.5}])
    s2 = _build_shot("1.B1.S2", "relay", "1.B1.S1", [])
    pkg = {"episode": "EpT", "sceneNumber": "9", "shots": [s1, s2],
           "continuityLedger": [{"shotId": "1.B1.S1"}, {"shotId": "1.B1.S2"}],
           "validation": {"passed": True}, "revision": 1}
    path = tmp_path / "cb-output" / "EpT_scene9_production_package.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(pkg, open(path, "w"))
    monkeypatch.setattr(R, "load_pkg", lambda scene, episode="EpT": (json.load(open(path)), path))
    monkeypatch.setattr(R, "_require_current_lineage", lambda pkg, scene, episode: None)
    # OUT OF SCOPE HERE ON PURPOSE (2026-07-19, found while running this exact test —
    # matching test_golden_path.py's own identical, already-established precedent for
    # _require_current_lineage above): _fresh_validation re-loads a SEPARATE artifact,
    # cb_engine's own Gate-1 beat package (glob-matched by episode label against the real
    # cb-output/ directory), and re-validates this shot package's full content against
    # cb_engine.Shot's real schema + cb_engine.validate_scene_design's real business rules.
    # That full-schema/business-rule proof is test_golden_path.py's own job (its fixture
    # builds a real, schema-complete beat package + shots precisely to exercise this path);
    # this file's own stated job is the department-gate mechanism (THE CORE LAW), never a
    # second proof of cb_engine's compiler/validator correctness. Scoped out the same way,
    # for the same reason, rather than duplicating that other suite's fixture machinery.
    monkeypatch.setattr(R, "_fresh_validation", lambda pkg, episode: None)
    return provider_calls, tmp_path, path


# ── mocking cb_llm.structured: the ONE network choke point in cb_departments.py ─────────
def _mock_llm(monkeypatch, animation_prompt=None, cinematography_prompt=None,
              voice_performed=None, look_prompt=None, media_review=None):
    """Patches cb_llm.structured so cb_departments.py's own real system-prompt construction
    (a genuine call to load_runtime_skill against the real repo SKILL.md files) runs
    unmocked — only the actual OpenAI network call is intercepted, and the response is a
    REAL instance of the REAL Pydantic schema, so schema validation genuinely runs too."""
    def fake_structured(system, user, schema, *, model=None, label="director", log=print,
                        images=None):
        name = schema.__name__
        if name == "AnimationDirection":
            # THE FORMULA GATE fixture (Gold Build, 2026-07-24): check_formula_structure
            # refuses any animation candidate that is not the house formula — header when
            # dialogue exists (THE SH1 KEEPER STANDARD, 2026-07-25: @Audio1 declared the
            # sole source of dialogue/wording/voice/performance/timing, the spoken WORDS
            # never present), labelled 'Shot N:' segments, 'Cut to.' transitions, a closing
            # HOLD tail, no duration text. The default stub must satisfy that real
            # save-time contract.
            # openingFrameRead (2026-07-27) is what the writer SEES in the approved keyframe,
            # settled before a word of prose exists — Julian's own find: "the direction really
            # needs to be able to look at the keyframe to be able to start the direction from
            # that moment." Required on the real model, so the stub carries a real-shaped one
            # rather than "x", for the same reason frameLogic's does below: a fixture that
            # cannot be built the way production builds it proves nothing.
            return schema(shotId="1.B1.S1", doesItLand="t",
                          openingFrameRead="(1) Open sunlit meadow, sky visible, nothing "
                                           "overhead — the paperwork's 'corridor' is not what "
                                           "this picture shows, so I write the picture. "
                                           "(2) Both bees mid-frame at the same distance, "
                                           "Fuzzby left and visibly larger, Zenny right and "
                                           "smaller — that reads only because they share a "
                                           "depth. (3) Open air above and to both sides; the "
                                           "leaf is within reach frame-right. (4) It ends with "
                                           "him grounded on the leaf, pollen settling — a "
                                           "place this frame could not have shown.",
                          providerPrompt=animation_prompt or
                          "ENGLISH DIALOGUE ONLY, spoken in English. Use @Audio1 as the "
                          "sole source of dialogue, wording, voice, performance and "
                          "timing.\n\n"
                          "Shot 1: Close-up, 85mm, handheld drift. Fuzzby bursts up out of "
                          "the flower, pollen haloing him in the high-key daylight, and "
                          # THE INTENT PIN (2026-07-25): the fixture shot declares a
                          # feltIntent, and THE DIRECTOR'S STOP now refuses a prompt
                          # that doesn't deliver it — so the canned GOOD candidate
                          # delivers it: his pride drives the speed, the grin held
                          # too long as the comedy hinge.
                          "puffs his chest with oblivious pride — his pride drives "
                          "the speed of every move. Fuzzby performs his vocal "
                          "beat from @Audio1. His grin is held one beat too long — "
                          "the comedy hinge. He nearly grazes the leaf on the way "
                          "past.\n\n"
                          "They hold the look, about 2 seconds of silence, no more dialogue.")
        if name == "CinematographyDirection":
            # frameLogic (2026-07-27) is the STAGING DECISION the Director and DP settle
            # before any prompt language exists — the prompt is delivery of it. Required on
            # the real model, so the stub carries a real-shaped one rather than "x": these
            # fixtures exist to prove the gate, and a fixture that cannot be constructed the
            # way production constructs it proves nothing.
            return schema(shotId="1.B1.S1", doesItLand="t",
                          frameLogic="(1) The frame promises trouble by crowding. (2) It must "
                                     "afford a climb up-frame-left, so that lane stays empty. "
                                     "(3) Wide, 24mm, bee-height. (4) At this size he reads as "
                                     "silhouette and attitude, not features.",
                          providerPrompt=cinematography_prompt or
                          "a real cinematography direction prompt with plenty of words yes")
        if name == "VoiceDirection":
            return schema(shotId="1.B1.S1", doesItLand="t", lines=[
                {"speaker": "Fuzzby", "exactDialogue": "Nailed it.",
                 "performedText": voice_performed or "Nailed it."}])
        if name == "LookDirection":
            return schema(doesItLand="t",
                          providerPrompt=look_prompt or
                          "a real look development prompt with plenty of words in it yes")
        if name == "MediaReview":
            base = {"artifactType": "keyframe", "verdict": "recommend-approve",
                    "summary": "t", "intendedRead": "t", "actualRead": "t",
                    "finalFrameUsable": True, "findings": []}
            base.update(media_review or {})
            return schema(**base)
        raise AssertionError(f"unexpected schema in this test: {name}")
    monkeypatch.setattr(cb_departments.cb_llm, "structured", fake_structured)


# ── 1/2/3: refuses, no disclosure, zero provider calls ──────────────────────────────────
def test_animation_refuses_with_no_direction_zero_provider_calls(world):
    calls, tmp, path = world
    with pytest.raises(R.DepartmentNotApproved, match="requires an APPROVED"):
        R.fire_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    assert calls["video"] == [] and calls["image"] == [] and calls["voice"] == []
    led = R._ledger(json.load(open(path)), "1.B1.S1")
    assert led.get("pendingSpendAuth") is None, "no disclosure authorisation may exist"


# ── 4: a storyboard seedancePrompt cannot bypass the gate ───────────────────────────────
def test_storyboard_prompt_field_cannot_bypass_the_gate(world):
    calls, tmp, path = world
    pkg = json.load(open(path))
    shot = pkg["shots"][0]
    assert "storyboard's OWN compiled prose" in shot["seedancePrompt"]
    with pytest.raises(R.DepartmentNotApproved):
        R.fire_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    assert calls["video"] == []


# ── 5: an unapproved working prompt cannot bypass the gate ──────────────────────────────
def test_unapproved_working_prompt_cannot_be_saved_at_all(world):
    calls, tmp, path = world
    with pytest.raises(R.Refused, match="Approve.*first|requires an APPROVED"):
        R.save_seedance_working("9", "1.B1.S1", "a hand-typed bypass prompt", "EpT")
    with pytest.raises(R.DepartmentNotApproved):
        R.fire_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    assert calls["video"] == []


# ── 6/11: running the real department route creates a candidate; the correct skill loads
def test_prepare_department_creates_a_real_candidate_and_loads_the_real_skill(world, monkeypatch):
    calls, tmp, path = world
    # 1.B1.S1 has dialogueLines — prepare_department's own animation branch hard-requires
    # an approved Voice Direction to exist first (production order), so seed it via the
    # real routes before testing animation's own candidate creation.
    _seed_animation_prereqs(monkeypatch, path)
    _mock_llm(monkeypatch)
    # THE CORRECT RUNTIME SKILL WAS GENUINELY LOADED (item 8): this is a real call against
    # the real repo file, not a stub — proves it BEFORE prepare_department ever runs.
    skill_text = cb_departments.load_runtime_skill("animation")
    assert skill_text and len(skill_text) > 20
    R.prepare_department("9", "animation", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    pkg = json.load(open(path))
    work = pkg["continuityLedger"][0]["departmentWork"]["animation"]
    assert work["candidate"] is not None and work["approved"] is None
    assert work["candidate"]["skillHash"], "the candidate must record which skill text it was hashed against"
    assert calls["video"] == [], "preparing a candidate must never spend"


# ── 7/8: approving through the real endpoint unlocks disclosure; the exact prompt reaches
#         the mocked provider unchanged
def test_approve_unlocks_disclosure_exact_prompt_reaches_provider_unchanged(world, monkeypatch):
    calls, tmp, path = world
    exact = _formula_prompt("THE EXACT APPROVED ANIMATION PROMPT — fast brisk action "
                            "slowing into a held closing beat, which must reach the "
                            "mocked provider byte for byte")

    # PRODUCTION ORDER: voice first (animation prep hard-requires it for a dialogue shot),
    # then cinematography → an approved keyframe anchor (fire_shot's own other pre-existing
    # requirement), THEN animation — never a hand-edited ledger, only the real routes.
    _seed_voice(monkeypatch, path)
    R.prepare_department("9", "cinematography", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    R.decide_department("9", "cinematography", "approved", "1.B1.S1", "EpT",
                        reviewed_by="Julian", log=lambda *a, **k: None)
    fire_keyframe("9", "1.B1.S1", "EpT")
    R.approve_keyframe("9", "1.B1.S1", "EpT", reviewed_by="Julian", log=lambda *a, **k: None)

    _mock_llm(monkeypatch, animation_prompt=exact)
    R.prepare_department("9", "animation", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    R.decide_department("9", "animation", "approved", "1.B1.S1", "EpT",
                        reviewed_by="Julian", log=lambda *a, **k: None)

    # NOW the real fire_shot route must resolve the exact approved Animation providerPrompt
    with pytest.raises(R.Refused, match="SPEND NOT APPROVED"):
        R.fire_shot("9", "1.B1.S1", "EpT", candidates=1, log=lambda *a, **k: None)
    led = R._ledger(json.load(open(path)), "1.B1.S1")
    auth = led["pendingSpendAuth"]
    assert auth is not None, "disclosure authorisation must now be available"
    assert auth["envelope"]["prompt"] == exact, \
        "the sealed provider-request envelope must carry the exact approved Animation prompt"
    R.fire_shot("9", "1.B1.S1", "EpT", candidates=1, spend_token=auth["token"],
                log=lambda *a, **k: None)
    assert len(calls["video"]) == 1
    assert calls["video"][0]["prompt"] == exact, "the mocked provider must receive the EXACT approved prompt"


def _mock_llm_voice_and_cinematography(monkeypatch):
    _mock_llm(monkeypatch)


def _seed_voice(monkeypatch, path, shot_id="1.B1.S1"):
    """Prepares, approves, generates and approves a real Voice Direction for a dialogue
    shot via the REAL routes (never a hand-edited ledger) — prepare_department's own
    animation branch hard-requires this exact chain before an Animation Direction may even
    be prepared for a shot with dialogueLines, matching production order."""
    _mock_llm(monkeypatch)
    R.prepare_department("9", "voice", shot_id, "EpT", log=lambda *a, **k: None)
    R.decide_department("9", "voice", "approved", shot_id, "EpT",
                        reviewed_by="Julian", log=lambda *a, **k: None)
    pkg, p = R.load_pkg("9", "EpT")
    R.voice_shot(pkg, p, shot_id, "EpT", log=lambda *a, **k: None)
    R.approve_voice("9", shot_id, "EpT", log=lambda *a, **k: None)


def fire_keyframe(scene, shot_id, episode, log=None):
    """Drives cb_render.keyframe_shot's real two-phase disclose-then-confirm spend-token seal
    (2026-07-22, Julian's directive — "ensure the prompts I see in the studio are the exact
    prompts that go to the API... your mistakes have cost me money"; see keyframe_shot's own
    docstring and _keyframe_binding_hash's for the full forensic reasoning) in one call, for
    fixture code that isn't itself testing the disclosure step — mirrors this file's own
    existing convention for fire_shot's identical two-phase contract (see e.g. the
    pendingSpendAuth-token round trips throughout this file). Never used by cb_render.py
    itself or any real Studio route; the real split stays the only path a human exercises."""
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


def _seed_keyframe_anchor(monkeypatch, path, shot_id="1.B1.S1"):
    """Prepares, approves, generates and approves a real Cinematography Direction and its
    keyframe for an OPENER shot via the REAL routes — prepare_department's own animation
    branch resolves _anchor_for(pkg, shot) even while only PREPARING (never firing) an
    Animation Direction, since the anchor image is one of the reference attachments the
    Animation Director itself is shown; a generated-but-unapproved keyframe is never a
    valid anchor (2026-07-17 state-integrity checkpoint), so this must run before any
    animation prep for an opener shot, not just before fire_shot."""
    _mock_llm(monkeypatch)
    R.prepare_department("9", "cinematography", shot_id, "EpT", log=lambda *a, **k: None)
    R.decide_department("9", "cinematography", "approved", shot_id, "EpT",
                        reviewed_by="Julian", log=lambda *a, **k: None)
    fire_keyframe("9", shot_id, "EpT")
    R.approve_keyframe("9", shot_id, "EpT", reviewed_by="Julian", log=lambda *a, **k: None)


def _seed_animation_prereqs(monkeypatch, path, shot_id="1.B1.S1"):
    """Everything prepare_department('animation', ...) requires before it will even run for
    a dialogue-bearing OPENER shot: an approved Voice Direction (+ generated + approved take)
    and an approved keyframe anchor (+ its own approved Cinematography Direction)."""
    _seed_voice(monkeypatch, path, shot_id)
    _seed_keyframe_anchor(monkeypatch, path, shot_id)


# ── 9: changing a relevant input makes the direction stale and blocks again ─────────────
def test_relevant_input_change_makes_direction_stale_and_blocks(world, monkeypatch):
    calls, tmp, path = world
    _seed_animation_prereqs(monkeypatch, path)
    _mock_llm(monkeypatch)
    R.prepare_department("9", "animation", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    R.decide_department("9", "animation", "approved", "1.B1.S1", "EpT",
                        reviewed_by="Julian", log=lambda *a, **k: None)
    pkg = json.load(open(path))
    fresh = R.department_freshness(pkg, "9", "animation", "1.B1.S1", "EpT")
    assert fresh["current"] is True, "a freshly-approved direction must be current"
    # a RELEVANT change: the shot's own dialogueLines (a real animation-context input)
    pkg["shots"][0]["dialogueLines"][0]["exactText"] = "A completely different line."
    json.dump(pkg, open(path, "w"))
    fresh2 = R.department_freshness(json.load(open(path)), "9", "animation", "1.B1.S1", "EpT")
    assert fresh2["current"] is False, "changing a real input must make the approval stale"
    with pytest.raises(R.DepartmentNotApproved, match="STALE"):
        R._require_approved_department(json.load(open(path)), "9", "animation", "1.B1.S1", "EpT")


# ── 10: changing an unrelated field does not make it stale ──────────────────────────────
def test_unrelated_field_change_does_not_stale_the_direction(world, monkeypatch):
    calls, tmp, path = world
    _seed_animation_prereqs(monkeypatch, path)
    _mock_llm(monkeypatch)
    R.prepare_department("9", "animation", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    R.decide_department("9", "animation", "approved", "1.B1.S1", "EpT",
                        reviewed_by="Julian", log=lambda *a, **k: None)
    pkg = json.load(open(path))
    # unrelated: a purely descriptive field _department_context_for_freshness never reads
    pkg["shots"][1]["purpose"] = "a totally unrelated edit on a DIFFERENT shot"
    json.dump(pkg, open(path, "w"))
    fresh = R.department_freshness(json.load(open(path)), "9", "animation", "1.B1.S1", "EpT")
    assert fresh["current"] is True, "an edit to an unrelated shot must never stale this one"


# ── 10b: approving Voice must never stale an already-approved Cinematography direction ──
# (2026-07-20, Julian, live in the Studio — "there is no way for me to approve and generate
# things"): the real, confirmed root cause was _shot_context folding Voice's own approved
# output into EVERY OTHER stage's freshness signature except voice's own — cinematography
# (a still-image keyframe composition) has zero legitimate dependency on Voice's performance
# direction, so approving Voice was flipping Cinematography's own sourceHash and reporting a
# false-positive STALE the very next time anyone checked it. This is the exact real-route
# sequence Julian hit: approve Cinematography, then approve Voice, then look at
# Cinematography again.
def test_approving_voice_does_not_stale_an_already_approved_cinematography(world, monkeypatch):
    calls, tmp, path = world
    _seed_keyframe_anchor(monkeypatch, path)
    pkg = json.load(open(path))
    fresh_before = R.department_freshness(pkg, "9", "cinematography", "1.B1.S1", "EpT")
    assert fresh_before["current"] is True, "a freshly-approved Cinematography direction must be current"

    _seed_voice(monkeypatch, path)

    pkg2 = json.load(open(path))
    fresh_after = R.department_freshness(pkg2, "9", "cinematography", "1.B1.S1", "EpT")
    assert fresh_after["current"] is True, (
        "approving an unrelated department (Voice) must never stale Cinematography's own "
        f"already-approved direction — got: {fresh_after['changed']}")
    # THE FULL GATE, NOT JUST THE FLAG (matches this file's own established pattern of
    # proving both the reported checklist state AND the actual hard gate agree): the real
    # keyframe route must still consider Cinematography ready to fire, not refuse STALE.
    approved, output = R._require_approved_department(
        pkg2, "9", "cinematography", "1.B1.S1", "EpT",
        action_label="keyframe readiness check")
    assert approved is not None and output.get("providerPrompt")


# ── 12: Look/keyframe/voice/review/post routes enforce their own departments ────────────
def test_scenelook_generation_refuses_without_its_own_approved_look_direction(world):
    calls, tmp, path = world
    with pytest.raises(R.Refused, match="Approve Look Development"):
        R.generate_scenelook_plate("9", "EpT", log=lambda *a, **k: None)
    assert calls["image"] == []


def test_keyframe_generation_refuses_without_its_own_approved_cinematography(world):
    calls, tmp, path = world
    # 2026-07-26 (UI/engine reconciliation): this used to match the DEPARTMENT name,
    # "Cinematography". The refusal now names the section a human actually has to open on his
    # own screen — "02 · OPENING FRAME" — because this same string is what department_readiness
    # returns as readiness.reasons.ready and the Studio prints straight onto the row, and
    # sending someone to a section that does not exist on their screen is what this whole
    # reconciliation was about. The gate itself is untouched: it still refuses, and still
    # spends nothing. Read from cb_departments so the assertion cannot drift from the table.
    with pytest.raises(R.DepartmentNotApproved,
                       match=re.escape(cb_departments.panel_label("cinematography"))):
        R.keyframe_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    assert calls["image"] == []


def test_the_readiness_reason_names_julians_section(world):
    """THE STRING JULIAN ACTUALLY READS (2026-07-26, the UI/engine reconciliation).

    department_readiness's reasons.ready is not developer text: the Studio prints it verbatim
    onto the shot row and into the disabled Generate button's tooltip. It used to be labelled
    "voice readiness check" / "cinematography readiness check" — the engine's own stage keys,
    on his screen, inside the very sentence telling him what to do about it, while his panel
    calls those sections 04 · VOICE and 02 · OPENING FRAME. Run against the real readiness
    path on the scratch world, not a hand-built message."""
    calls, tmp, path = world
    pkg, _p = R.load_pkg("9", "EpT")
    for stage in cb_departments.authorising_stages():
        rd = R.department_readiness(pkg, "9", stage, "1.B1.S1", "EpT")
        if rd.get("applicable") is False:
            continue
        reason = (rd.get("reasons") or {}).get("ready") or ""
        assert reason, f"{stage} is not ready but gives no reason"
        assert f"{stage} readiness check" not in reason, (
            f"the readiness reason for {stage} still names the engine's own stage key")
        assert cb_departments.panel_label(stage) in reason, (
            f"the readiness reason for {stage} never names the section "
            f"{cb_departments.panel_label(stage)!r} the human has to open")
    assert calls["image"] == [] and calls["voice"] == []


def test_voice_generation_refuses_without_its_own_approved_voice_direction(world):
    calls, tmp, path = world
    pkg, p = R.load_pkg("9", "EpT")
    with pytest.raises(R.DepartmentNotApproved,
                       match=re.escape(cb_departments.panel_label("voice"))):
        R.voice_shot(pkg, p, "1.B1.S1", "EpT", log=lambda *a, **k: None)
    assert calls["voice"] == []


def test_relay_shot_animation_refuses_before_its_source_is_approved(world, monkeypatch):
    calls, tmp, path = world
    _mock_llm(monkeypatch)
    with pytest.raises(R.Refused):
        R.fire_shot("9", "1.B1.S2", "EpT", log=lambda *a, **k: None)
    assert calls["video"] == []


# ── REGRESSION (found while producing the Scene-1 blocker report, 2026-07-19): a relay
#    shot has no Cinematography direction of its own — before this fix, department_status/
#    department_readiness's own freshness recompute crashed with a raw KeyError (not a
#    clean Refused) the instant anyone checked a relay shot's cinematography readiness,
#    since _department_context_for_freshness's cinematography branch unconditionally
#    indexed shot["keyframeReferenceSlots"], a field only an opener ever carries. ─────────
def test_relay_shot_cinematography_reports_not_applicable_never_crashes(world):
    calls, tmp, path = world
    status = R.department_status("9", "1.B1.S2", "EpT", stage="cinematography")
    readiness = status["readiness"]
    assert readiness["applicable"] is False
    assert readiness["readyForDisclosure"] is None
    # the deeper shared helper must raise a clean Refused, never propagate a bare KeyError
    pkg = json.load(open(path))
    with pytest.raises(R.Refused):
        R._department_context_for_freshness(pkg, "9", "cinematography", "1.B1.S2", "EpT")
    # and the real authoring entry point (prepare_department) must refuse the same way,
    # never crash, if ever invoked directly against a relay shot's cinematography stage
    with pytest.raises(R.Refused):
        R.prepare_department("9", "cinematography", "1.B1.S2", "EpT", log=lambda *a, **k: None)


# ── 13: Studio buttons call the protected backend routes (source-level proof, matching
#         test_e2e_fire_route.py's own AST-based technique for shot_run_job) ────────────
def test_studio_department_run_route_calls_the_real_protected_function():
    """/api/department-run in cb-studio/serve.py dispatches to a subprocess running
    'cb_render.py department-prepare' (the same subprocess-boundary shape already proven
    for the fire route by test_e2e_fire_route.py's own shot_run_job test) — confirm the
    route builds that exact subprocess command, and that the CLI's own department-prepare
    branch in cb_render.py calls the real prepare_department function this whole test file
    exercises, never a bypassed shortcut. /api/department-decide is a direct in-process call
    (no subprocess), so it's checked directly against decide_department."""
    src = (HERE.parent / "cb-studio" / "serve.py").read_text()
    assert "/api/department-run" in src
    idx = src.index("/api/department-run")
    window = src[idx:idx + 2000]
    assert "department-prepare" in window, \
        "the route must dispatch to cb_render.py's department-prepare subcommand"
    cbr_src = (HERE / "cb_render.py").read_text()
    idx_cli = cbr_src.index('cmd == "department-prepare"')
    window_cli = cbr_src[idx_cli:idx_cli + 200]
    assert "prepare_department(" in window_cli, \
        "the department-prepare CLI subcommand must call the real prepare_department"
    idx2 = src.index("/api/department-decide")
    window2 = src[idx2:idx2 + 2000]
    assert "decide_department" in window2


# ── 14: no real provider credentials or network calls are used ─────────────────────────
def test_no_real_network_or_credentials_touched(world, monkeypatch):
    """Every provider-facing function this whole file exercises is monkeypatched away by
    the world fixture — asserted directly (never just assumed) by confirming each one has
    genuinely been replaced by this file's own fake, never the real network-calling
    implementation."""
    _mock_llm(monkeypatch)
    assert cb_gen.generate_image.__name__ == "fake_generate_image"
    assert cb_gen.generate_video_seedance_ref.__name__ == "fake_video"
    assert cb_gen.eleven_dialogue.__name__ == "fake_voice"
    assert cb_departments.cb_llm.structured.__name__ == "fake_structured"
    # exercise one real, gated route end to end under these mocks and confirm it still
    # refuses cleanly with zero provider calls — the mocks are live, not just installed
    calls, tmp, path = world
    with pytest.raises(R.DepartmentNotApproved):
        R.fire_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    assert calls["video"] == [] and calls["image"] == [] and calls["voice"] == []


# ═════════════════════════════════════════════════════════════════════════════════════
# THE BOUNDED REDESIGN-RECOVERY ACTION (2026-07-20, Julian's directive) — "Acknowledge
# redesign and open new test cycle." Every test below uses ONLY the real, protected
# functions (redesign_eligibility, acknowledge_redesign, fire_shot, reject_shot) against a
# disposable package, exactly matching this file's own established discipline: no approval
# JSON is ever hand-edited to manufacture a passing test; every state transition happens
# through the real route a Studio click would also go through.
# ═════════════════════════════════════════════════════════════════════════════════════

def _fire_one_candidate(shot_id, path):
    """Fires the real disclosure-then-token dance down to ONE generated candidate,
    landing the shot in candidates-pending — never a hand-written ledger."""
    with pytest.raises(R.Refused, match="SPEND NOT APPROVED"):
        R.fire_shot("9", shot_id, "EpT", candidates=1, log=lambda *a, **k: None)
    led = R._ledger(json.load(open(path)), shot_id)
    token = led["pendingSpendAuth"]["token"]
    R.fire_shot("9", shot_id, "EpT", candidates=1, spend_token=token, log=lambda *a, **k: None)


def _approve_animation(monkeypatch, prompt_text, shot_id="1.B1.S1"):
    _mock_llm(monkeypatch, animation_prompt=prompt_text)
    R.prepare_department("9", "animation", shot_id, "EpT", log=lambda *a, **k: None)
    R.decide_department("9", "animation", "approved", shot_id, "EpT",
                        reviewed_by="Julian", log=lambda *a, **k: None)


def _reach_model_limited(monkeypatch, path, shot_id="1.B1.S1",
                         animation_prompt=_formula_prompt(
                             "fast brisk ORIGINAL rejected animation action, slowing into "
                             "a held ORIGINAL closing beat, near-still")):
    """Walks a real shot all the way to model-limited via two real rejected batches — the
    exact decision-ladder hard stop this whole recovery action exists to recover from.
    NOTE (found live via this test, out of scope for this bounded feature — see the final
    report): reject_shot's own archive path is second-resolution
    (media/archive/shots_rejected/{episode}_{shot_id}_{ts}); two rejections inside the same
    wall-clock second collide into the SAME directory, silently overwriting the first
    rejection's own REJECTED.json — the identical bug class CLAUDE.md rule 56 already
    documents and fixed for cb_beats.record_approval, just never for cb_render.reject_shot.
    Sleeping past the second boundary here avoids tripping over that pre-existing,
    out-of-scope bug rather than papering over it in production code."""
    _seed_animation_prereqs(monkeypatch, path, shot_id)
    _approve_animation(monkeypatch, animation_prompt, shot_id)
    # Drive to the ceiling by CONSTANT, never a hardcoded count — the iteration budget is
    # a policy number (raised 2 -> 7 on 2026-07-25) and a test that pins it breaks every
    # time the policy moves. What matters is that the ladder ENDS, not where.
    for i in range(R.MAX_BATCH_ATTEMPTS):
        _fire_one_candidate(shot_id, path)
        R.reject_shot("9", shot_id, f"failure {i + 1}", category="action-timing",
                      episode="EpT", log=lambda *a, **k: None)
    led = R._ledger(json.load(open(path)), shot_id)
    assert led["status"] == "model-limited", "setup must genuinely reach model-limited"
    return led["batch"]["batchId"]


def test_unchanged_inputs_cannot_clear_model_limited(world, monkeypatch):
    calls, tmp, path = world
    _reach_model_limited(monkeypatch, path)
    before = {k: len(v) for k, v in calls.items()}
    elig = R.redesign_eligibility("9", "1.B1.S1", "EpT")
    assert elig["eligible"] is False
    assert any("IDENTICAL" in b for b in elig["blockers"])
    assert elig["oldSignature"] and elig["oldSignature"] == elig["newSignature"]
    with pytest.raises(R.Refused, match="not available"):
        R.acknowledge_redesign("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    after = {k: len(v) for k, v in calls.items()}
    assert after == before, "checking/refusing eligibility must make zero new provider calls"


def test_changed_but_unapproved_inputs_cannot_clear_it(world, monkeypatch):
    """A REAL input changes (the shot's own dialogue line — the exact class of change
    test_relevant_input_change_makes_direction_stale_and_blocks already proves stales an
    Animation Direction) but NOTHING is re-approved yet. Eligibility must still refuse —
    "changed" alone is never enough, it must be CURRENT and APPROVED."""
    calls, tmp, path = world
    _reach_model_limited(monkeypatch, path)
    pkg = json.load(open(path))
    pkg["shots"][0]["dialogueLines"][0]["exactText"] = "A completely different line now."
    json.dump(pkg, open(path, "w"))
    before = {k: len(v) for k, v in calls.items()}
    elig = R.redesign_eligibility("9", "1.B1.S1", "EpT")
    assert elig["eligible"] is False
    assert any("not currently approved" in b or "STALE" in b for b in elig["blockers"])
    with pytest.raises(R.Refused, match="not available"):
        R.acknowledge_redesign("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    after = {k: len(v) for k, v in calls.items()}
    assert after == before, "checking/refusing eligibility must make zero new provider calls"


def test_current_approved_redesign_with_different_signature_enables_acknowledgement(world, monkeypatch):
    calls, tmp, path = world
    prev_batch_id = _reach_model_limited(monkeypatch, path)
    pkg = json.load(open(path))
    pkg["shots"][0]["dialogueLines"][0]["exactText"] = "A completely different line now."
    json.dump(pkg, open(path, "w"))
    # re-approve a GENUINELY different Animation Direction reflecting the changed line
    _approve_animation(monkeypatch, _REDESIGN_PROMPT, shot_id="1.B1.S1")
    before_calls = {k: list(v) for k, v in calls.items()}
    elig = R.redesign_eligibility("9", "1.B1.S1", "EpT")
    assert elig["eligible"] is True, elig["blockers"]
    assert elig["oldSignature"] and elig["newSignature"]
    assert elig["oldSignature"] != elig["newSignature"]
    assert "animationPromptSha256" in elig["changedInputs"]
    assert elig["previousCycleId"] == prev_batch_id
    assert len(elig["rejectedBatchIds"]) == R.MAX_BATCH_ATTEMPTS
    assert elig["nextCandidateLimit"] == R.REDESIGN_CANDIDATE_LIMIT == 1

    event = R.acknowledge_redesign("9", "1.B1.S1", "EpT", reviewed_by="Julian",
                                   log=lambda *a, **k: None)
    assert event["oldSignature"] == elig["oldSignature"]
    assert event["newSignature"] == elig["newSignature"]
    assert event["previousCycleId"] == prev_batch_id
    assert event["previousRejectedBatchIds"] == elig["rejectedBatchIds"]

    led = R._ledger(json.load(open(path)), "1.B1.S1")
    assert led["status"] == "designed"
    assert led["batchAttempts"] == 0
    assert led["redesignCycle"]["candidateLimit"] == 1
    # zero NEW provider calls from eligibility-checking/acknowledgement itself, zero spend
    assert calls["video"] == before_calls["video"] and calls["image"] == before_calls["image"] \
        and calls["voice"] == before_calls["voice"]
    assert led.get("pendingSpendAuth") is None


def test_old_signature_derived_from_last_rejected_batchs_sealed_envelope(world, monkeypatch):
    """Directly recomputes old_signature from led['batch']['envelope'] independently of
    redesign_eligibility's own internals, proving it is genuinely sourced from the
    historical sealed envelope, not guessed or reconstructed from mutable package state."""
    calls, tmp, path = world
    _reach_model_limited(monkeypatch, path)
    led = R._ledger(json.load(open(path)), "1.B1.S1")
    hist, missing = R._historical_redesign_components(led)
    assert not missing, missing
    expected = R._redesign_signature(hist)
    elig = R.redesign_eligibility("9", "1.B1.S1", "EpT")
    assert elig["oldSignature"] == expected
    # and it must come from the REJECTED batch's own envelope, not e.g. today's current
    # approved animation prompt (proven by construction: hist['animationPromptSha256'] is
    # the hash of the ORIGINAL rejected prompt text, recovered straight from the envelope)
    assert hist["animationPromptSha256"] == R._sha256_text(
        led["batch"]["envelope"]["prompt"])


def test_acknowledgement_event_does_not_invalidate_its_own_new_signature(world, monkeypatch):
    """Recomputing the CURRENT redesign components immediately after acknowledgement must
    still hash to the exact new_signature the acknowledgement event just recorded — proving
    cb_render.py's own _save() never bumps pkg['revision'] (only cb_engine.py's promotion
    step does), so the acknowledgement write cannot make its own redesign stale."""
    calls, tmp, path = world
    _reach_model_limited(monkeypatch, path)
    pkg = json.load(open(path))
    pkg["shots"][0]["dialogueLines"][0]["exactText"] = "A completely different line now."
    json.dump(pkg, open(path, "w"))
    _approve_animation(monkeypatch, _REDESIGN_PROMPT, shot_id="1.B1.S1")
    event = R.acknowledge_redesign("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    pkg2, _ = R.load_pkg("9", "EpT")
    shot2 = R._shot(pkg2, "1.B1.S1")
    recomputed, missing = R._current_redesign_components(pkg2, shot2, "9", "EpT")
    assert not missing, missing
    assert R._redesign_signature(recomputed) == event["newSignature"]


def test_all_historical_batches_and_rejections_remain_intact(world, monkeypatch):
    calls, tmp, path = world
    _reach_model_limited(monkeypatch, path)
    before = json.load(open(path))
    led_before = R._ledger(before, "1.B1.S1")
    rejections_before = json.loads(json.dumps(led_before["rejections"]))
    batch_before = json.loads(json.dumps(led_before["batch"]))
    pkg = json.load(open(path))
    pkg["shots"][0]["dialogueLines"][0]["exactText"] = "A completely different line now."
    json.dump(pkg, open(path, "w"))
    _approve_animation(monkeypatch, _REDESIGN_PROMPT, shot_id="1.B1.S1")
    R.acknowledge_redesign("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    after = json.load(open(path))
    led_after = R._ledger(after, "1.B1.S1")
    assert led_after["rejections"] == rejections_before, "no rejection may be lost or altered"
    assert led_after["batch"] == batch_before, "the previous batch's own record is untouched"
    assert len(led_after["redesignAcknowledgements"]) == 1


def test_cost_ledger_records_remain_intact(world, monkeypatch):
    calls, tmp, path = world
    _reach_model_limited(monkeypatch, path)
    lf = tmp / "engine" / "cost_ledger.jsonl"
    lf.parent.mkdir(parents=True, exist_ok=True)
    synthetic = json.dumps({"out": f"{tmp}/engine/media/shots/EpT_1.B1.S1_c1.mp4",
                            "cost_usd": 4.55, "at": "2026-01-01T00:00:00"})
    lf.write_text(synthetic + "\n")
    before = lf.read_text()
    pkg = json.load(open(path))
    pkg["shots"][0]["dialogueLines"][0]["exactText"] = "A completely different line now."
    json.dump(pkg, open(path, "w"))
    _approve_animation(monkeypatch, _REDESIGN_PROMPT, shot_id="1.B1.S1")
    elig = R.redesign_eligibility("9", "1.B1.S1", "EpT")
    assert elig["historicalSpendUsd"] == 4.55
    R.acknowledge_redesign("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    assert lf.read_text() == before, "the cost ledger file must be byte-for-byte untouched"


def test_acknowledgement_makes_zero_provider_calls_and_no_spend_authorisation(world, monkeypatch):
    """_reach_model_limited's own SETUP genuinely fires two real (mocked) video candidates
    — the two batches that get rejected. What must be proven here is that acknowledgement
    ITSELF adds no new calls on top of that setup, never that the counters are empty from
    the start of the test."""
    calls, tmp, path = world
    _reach_model_limited(monkeypatch, path)
    pkg = json.load(open(path))
    pkg["shots"][0]["dialogueLines"][0]["exactText"] = "A completely different line now."
    json.dump(pkg, open(path, "w"))
    _approve_animation(monkeypatch, _REDESIGN_PROMPT, shot_id="1.B1.S1")
    before = {k: len(v) for k, v in calls.items()}
    R.acknowledge_redesign("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    after = {k: len(v) for k, v in calls.items()}
    assert after == before, \
        "acknowledgement itself must make zero new LLM/image/voice/video calls"
    led = R._ledger(json.load(open(path)), "1.B1.S1")
    assert led.get("pendingSpendAuth") is None, \
        "acknowledgement must never create a spend authorisation"


def _acknowledged_shot(monkeypatch, path):
    _reach_model_limited(monkeypatch, path)
    pkg = json.load(open(path))
    pkg["shots"][0]["dialogueLines"][0]["exactText"] = "A completely different line now."
    json.dump(pkg, open(path, "w"))
    _approve_animation(monkeypatch, _REDESIGN_PROMPT, shot_id="1.B1.S1")
    R.acknowledge_redesign("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)


def test_only_one_candidate_permitted_in_new_cycle(world, monkeypatch):
    """The one-candidate cap is enforced in fire_shot ITSELF — the same function both the
    disclosure step and the real firing step run through — never only in the Studio UI.
    _acknowledged_shot's own setup already fired two real (mocked) candidates on the way to
    model-limited; what matters here is that requesting 2 in the NEW cycle adds no more."""
    calls, tmp, path = world
    _acknowledged_shot(monkeypatch, path)
    video_before = len(calls["video"])
    with pytest.raises(R.Refused, match="permits at most 1 candidate"):
        R.fire_shot("9", "1.B1.S1", "EpT", candidates=2, log=lambda *a, **k: None)
    # refused BEFORE any disclosure/spend-token/provider step — no pendingSpendAuth exists
    led = R._ledger(json.load(open(path)), "1.B1.S1")
    assert led.get("pendingSpendAuth") is None
    assert len(calls["video"]) == video_before


def test_two_or_more_candidates_refuses_before_provider_invocation(world, monkeypatch):
    calls, tmp, path = world
    _acknowledged_shot(monkeypatch, path)
    before = {k: len(v) for k, v in calls.items()}
    for n in (2, 3, 4):
        with pytest.raises(R.Refused, match="permits at most 1 candidate"):
            R.fire_shot("9", "1.B1.S1", "EpT", candidates=n, log=lambda *a, **k: None)
    after = {k: len(v) for k, v in calls.items()}
    assert after == before, "no candidate count above the cap may reach the provider at all"
    # exactly ONE candidate is genuinely allowed through to the normal disclosure step
    with pytest.raises(R.Refused, match="SPEND NOT APPROVED"):
        R.fire_shot("9", "1.B1.S1", "EpT", candidates=1, log=lambda *a, **k: None)


def test_control_unavailable_while_spend_authorisation_pending(world, monkeypatch):
    calls, tmp, path = world
    _reach_model_limited(monkeypatch, path)
    pkg = json.load(open(path))
    pkg["shots"][0]["dialogueLines"][0]["exactText"] = "A completely different line now."
    json.dump(pkg, open(path, "w"))
    _approve_animation(monkeypatch, _REDESIGN_PROMPT, shot_id="1.B1.S1")
    # simulate a pending disclosure — normally impossible while model-limited (fire_shot
    # refuses first), so this proves the eligibility check's own independent guard
    pkg2 = json.load(open(path))
    led2 = R._ledger(pkg2, "1.B1.S1")
    led2["pendingSpendAuth"] = {"token": "fake", "bindingHash": "x"}
    json.dump(pkg2, open(path, "w"))
    elig = R.redesign_eligibility("9", "1.B1.S1", "EpT")
    assert elig["eligible"] is False
    assert any("spend authorisation is currently pending" in b for b in elig["blockers"])


def test_control_unavailable_while_a_generation_job_is_in_flight(world, monkeypatch):
    calls, tmp, path = world
    _reach_model_limited(monkeypatch, path)
    pkg = json.load(open(path))
    pkg["shots"][0]["dialogueLines"][0]["exactText"] = "A completely different line now."
    json.dump(pkg, open(path, "w"))
    _approve_animation(monkeypatch, _REDESIGN_PROMPT, shot_id="1.B1.S1")
    pkg2 = json.load(open(path))
    led2 = R._ledger(pkg2, "1.B1.S1")
    led2["batch"] = dict(led2["batch"] or {}, status="generating")
    json.dump(pkg2, open(path, "w"))
    elig = R.redesign_eligibility("9", "1.B1.S1", "EpT")
    assert elig["eligible"] is False
    assert any("generation job is currently in flight" in b for b in elig["blockers"])


def test_no_direct_json_manipulation_required_through_the_real_route(world, monkeypatch):
    """The full, real, end-to-end recovery — model-limited to a real fire — using ONLY the
    protected route functions, no hand-edited ledger JSON for anything except simulating
    the changed creative input itself (the one thing a human/Director would actually edit
    through the Studio's own beat/shot editor, not the ledger machinery this feature
    protects)."""
    calls, tmp, path = world
    _acknowledged_shot(monkeypatch, path)
    video_before = len(calls["video"])   # 2 real (mocked) candidates already fired en route
                                         # to model-limited, in _acknowledged_shot's own setup
    with pytest.raises(R.Refused, match="SPEND NOT APPROVED"):
        R.fire_shot("9", "1.B1.S1", "EpT", candidates=1, log=lambda *a, **k: None)
    led = R._ledger(json.load(open(path)), "1.B1.S1")
    token = led["pendingSpendAuth"]["token"]
    R.fire_shot("9", "1.B1.S1", "EpT", candidates=1, spend_token=token,
               log=lambda *a, **k: None)
    assert len(calls["video"]) == video_before + 1, \
        "exactly one NEW candidate fires in the acknowledged cycle"
    led2 = R._ledger(json.load(open(path)), "1.B1.S1")
    assert led2["status"] == "candidates-pending"
    assert len(led2["candidatePaths"]) == 1


# ── the Studio route calls the protected backend functions, never a bypass ──────────────
def test_studio_redesign_routes_call_the_real_protected_functions():
    src = (HERE.parent / "cb-studio" / "serve.py").read_text()
    assert "/api/shot-redesign-eligibility" in src
    idx = src.index("/api/shot-redesign-eligibility")
    window = src[idx:idx + 2000]
    assert "_CBR.redesign_eligibility(" in window
    assert "/api/shot-acknowledge-redesign" in src
    idx2 = src.index("/api/shot-acknowledge-redesign")
    window2 = src[idx2:idx2 + 2000]
    assert "_CBR.acknowledge_redesign(" in window2


# ── AUTO-APPROVE A CLEAN DIRECTOR REVIEW PASS ONLY (2026-07-20, Julian — "i just want to
# see the good stuff thats passed"): the one department that grades itself gets to
# auto-approve on a genuinely clean verdict; every other department, and every non-clean
# review verdict, still stops for a real human decision. ─────────────────────────────────
def test_clean_director_review_auto_approves(world, monkeypatch):
    calls, tmp, path = world
    _seed_keyframe_anchor(monkeypatch, path)   # gives review-keyframe real media to review
    _mock_llm(monkeypatch, media_review={"verdict": "recommend-approve", "findings": []})
    cand = R.prepare_department("9", "review-keyframe", "1.B1.S1", "EpT",
                                log=lambda *a, **k: None)
    assert cand is not None, "prepare_department still returns the prepared candidate"
    status = R.department_status("9", "1.B1.S1", "EpT", "review-keyframe")
    assert status["candidate"] is None, "a clean pass leaves nothing pending"
    assert status["approved"] is not None, "a clean pass is approved automatically"
    assert "auto" in status["approved"]["reviewedBy"].lower()
    assert "clean pass" in status["approved"]["reviewedBy"].lower()
    # still fully visible/reversible history, exactly like a human decision would be
    assert status["approved"]["outcome"] == "approved"


def test_director_review_with_block_finding_still_stops_for_a_human(world, monkeypatch):
    calls, tmp, path = world
    _seed_keyframe_anchor(monkeypatch, path)
    _mock_llm(monkeypatch, media_review={
        "verdict": "recommend-approve",   # even a verdict that SOUNDS clean...
        "findings": [{"severity": "BLOCK", "criterion": "t", "visibleEvidence": "t",
                      "owner": "cinematography", "suggestedAction": "t"}]})
    R.prepare_department("9", "review-keyframe", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    status = R.department_status("9", "1.B1.S1", "EpT", "review-keyframe")
    assert status["approved"] is None, "one BLOCK finding must still stop for Julian"
    assert status["candidate"] is not None, "the candidate stays pending, awaiting a decision"


def test_director_review_revise_verdict_still_stops_for_a_human(world, monkeypatch):
    calls, tmp, path = world
    _seed_keyframe_anchor(monkeypatch, path)
    _mock_llm(monkeypatch, media_review={"verdict": "revise", "findings": []})
    R.prepare_department("9", "review-keyframe", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    status = R.department_status("9", "1.B1.S1", "EpT", "review-keyframe")
    assert status["approved"] is None, "a 'revise' verdict must still stop for Julian"
    assert status["candidate"] is not None


def test_clean_cinematography_pass_is_never_auto_approved(world, monkeypatch):
    """Cinematography/Voice/Animation/Look never self-grade a verdict, so none of them may
    be swept up by the review-only auto-approve path above — confirmed directly against
    the real function, not just inferred from the `stage.startswith("review-")` guard."""
    calls, tmp, path = world
    _mock_llm(monkeypatch)
    R.prepare_department("9", "cinematography", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    status = R.department_status("9", "1.B1.S1", "EpT", "cinematography")
    assert status["approved"] is None, "cinematography must never auto-approve itself"
    assert status["candidate"] is not None


# ── reconcile_shot_history — the state-integrity repair (Julian's directive, 2026-07-20) ─
def test_reconcile_shot_history_recovers_clobbered_rejection_state(world, monkeypatch):
    """The exact real-world drift this function exists to close: two genuinely rejected
    batches are on record, real, on disk, in the archive — but the live ledger has been
    reset (by the promotion race) to look as if neither ever happened, with a dangling
    candidatePaths pointer at a file that's actually already been archived away."""
    calls, tmp, path = world
    _reach_model_limited(monkeypatch, path)
    before = json.load(open(path))
    led_before = R._ledger(before, "1.B1.S1")
    real_rejections = json.loads(json.dumps(led_before["rejections"]))
    last_batch_id = led_before["batch"]["batchId"]
    assert (len(real_rejections) == R.MAX_BATCH_ATTEMPTS
            and led_before["status"] == "model-limited")

    # SIMULATE THE CLOBBER: exactly what the promotion race left behind live tonight —
    # candidatePaths pointing at a file reject_shot has already archived, zero rejections
    # on record, status reset to as if nothing happened.
    dangling = str(tmp / "engine" / "media" / "shots" / "EpT_1.B1.S1_c1.mp4")
    pkg = json.load(open(path))
    led = R._ledger(pkg, "1.B1.S1")
    led.update({"status": "candidates-pending", "candidatePaths": [dangling],
                "batchId": last_batch_id, "rejections": [], "batchAttempts": None})
    json.dump(pkg, open(path, "w"))

    audit = R.reconcile_shot_history("9", "1.B1.S1", episode="EpT", reviewed_by="Julian",
                                     log=lambda *a, **k: None)
    # EVERY rejection on record before the clobber is recovered — the invariant is
    # completeness, not a count. (batchAttempts counts DISTINCT rejected batchIds, which
    # is deliberately not the same as the raw number of reject_shot calls, so pinning
    # either to MAX_BATCH_ATTEMPTS would assert the wrong thing.)
    assert audit["recoveredRejections"]
    recovered_batches = {r["batchId"] for r in audit["recoveredRejections"]}
    assert recovered_batches == {r["batchId"] for r in real_rejections}

    after = json.load(open(path))
    led_after = R._ledger(after, "1.B1.S1")
    assert led_after["status"] == "model-limited"
    assert led_after["candidatePaths"] is None and led_after["batchId"] is None
    assert led_after["batchAttempts"] == len(recovered_batches)
    assert led_after["rejections"] == real_rejections            # recovered VERBATIM
    assert led_after["batch"] == led_before["batch"]              # untouched
    assert len(led_after["stateReconciliationLog"]) == 1


def test_reconcile_shot_history_is_idempotent(world, monkeypatch):
    """A second reconciliation after a successful one finds nothing new and refuses —
    never re-appends the same rejections a second time."""
    calls, tmp, path = world
    _reach_model_limited(monkeypatch, path)
    pkg = json.load(open(path))
    led = R._ledger(pkg, "1.B1.S1")
    last_batch_id = led["batch"]["batchId"]
    led.update({"status": "candidates-pending",
                "candidatePaths": [str(tmp / "engine" / "media" / "shots" / "EpT_1.B1.S1_c1.mp4")],
                "batchId": last_batch_id, "rejections": [], "batchAttempts": None})
    json.dump(pkg, open(path, "w"))
    R.reconcile_shot_history("9", "1.B1.S1", episode="EpT", log=lambda *a, **k: None)
    with pytest.raises(R.Refused, match="already reflects every"):
        R.reconcile_shot_history("9", "1.B1.S1", episode="EpT", log=lambda *a, **k: None)


def test_reconcile_shot_history_refuses_with_no_archive(world):
    """A shot with no rejection archive at all has nothing to reconcile — refuses rather
    than silently no-op'ing, so a caller can't mistake 'nothing to do' for a real repair."""
    calls, tmp, path = world
    with pytest.raises(R.Refused, match="no rejection archive records exist"):
        R.reconcile_shot_history("9", "1.B1.S1", episode="EpT", log=lambda *a, **k: None)


# ── delivery-is-compilation (2026-07-21, Julian's ruling) ───────────────────────────────
def test_cinematography_and_animation_receive_the_compiled_brief_not_raw_json(world, monkeypatch):
    """Proves the actual wiring, not just that nothing crashes: cb_engine.compile_keyframe_
    prompt's/compile_shot_contract's own deterministic output must genuinely reach the
    specialist's user prompt as its definitive source — the whole point of the fix."""
    calls, tmp, path = world
    captured = []

    def capturing_llm(system, user, schema, *, model=None, label="director", log=print,
                      images=None):
        captured.append((label, system, user))
        name = schema.__name__
        if name == "CinematographyDirection":
            return schema(shotId="1.B1.S1", doesItLand="t",
                          frameLogic="(1) Promise of trouble by crowding. (2) The climb lane "
                                     "up-frame-left stays empty. (3) Wide, 24mm, bee-height. "
                                     "(4) Silhouette and attitude, not features.",
                          providerPrompt="a real cinematography direction prompt yes yes")
        if name == "AnimationDirection":
            return schema(shotId="1.B1.S1", doesItLand="t",
                          openingFrameRead="(1) Open sunlit meadow, sky above. (2) Both bees "
                                           "at one depth, Fuzzby larger frame-left. (3) Open "
                                           "air both sides, leaf in reach. (4) Ends grounded "
                                           "on the leaf.",
                          providerPrompt=_formula_prompt(
                              "fast brisk real animation direction action, slowing into "
                              "a held closing beat, near-still"))
        if name == "VoiceDirection":
            return cb_departments.VoiceDirection(shotId="1.B1.S1", doesItLand="t", lines=[
                {"speaker": "Fuzzby", "exactDialogue": "Nailed it.",
                 "performedText": "Nailed it."}])
        raise AssertionError(name)
    monkeypatch.setattr(cb_departments.cb_llm, "structured", capturing_llm)

    R.prepare_department("9", "cinematography", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    label, system, user = next(c for c in captured if c[0] == "department_cinematography")
    # GOLD BUILD UPDATE (2026-07-24): the register writer's user prompt leads with the
    # compiled SOURCE-MATERIAL brief (cb_engine.compile_keyframe_prompt's own labelled
    # facts) as its definitive source — never a raw JSON dump standing in for it.
    assert "SOURCE MATERIAL — the storyboard-approved facts for this opening frame" in user
    assert "OPENING POSE / STORY INSTANT" in user   # real compile_keyframe_prompt output
    assert "register writer for STILL opening frames" in system
    assert "THE HOUSE CRAFT CURRICULUM (verbatim)" in system   # the craft docs, loaded verbatim

    R.decide_department("9", "cinematography", "approved", "1.B1.S1", "EpT",
                        reviewed_by="Julian", log=lambda *a, **k: None)
    fire_keyframe("9", "1.B1.S1", "EpT")
    R.approve_keyframe("9", "1.B1.S1", "EpT", reviewed_by="Julian", log=lambda *a, **k: None)
    R.prepare_department("9", "voice", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    label3, system3, user3 = next(c for c in captured if c[0] == "department_voice")
    # the shot's own already-approved acting direction ("proud", set in the scratch
    # fixture's dialogueLines[0].delivery) must reach the voice prompt labelled as the
    # definitive source — never buried, unread, inside a generic JSON dump of the shot.
    assert "APPROVED DIRECTION: proud" in user3
    assert "already made" in system3
    R.decide_department("9", "voice", "approved", "1.B1.S1", "EpT",
                        reviewed_by="Julian", log=lambda *a, **k: None)
    pkg, p = R.load_pkg("9", "EpT")
    R.voice_shot(pkg, p, "1.B1.S1", "EpT", log=lambda *a, **k: None)
    R.approve_voice("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)

    R.prepare_department("9", "animation", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    label2, system2, user2 = next(c for c in captured if c[0] == "department_animation")
    # GOLD BUILD UPDATE (2026-07-24): the animation register writer's user prompt leads
    # with compile_shot_contract's SOURCE-MATERIAL brief as its definitive source.
    assert "SOURCE MATERIAL — the storyboard-approved facts. Write the card FROM these" in user2
    assert "SOURCE MATERIAL — storyboard-approved facts" in user2   # the real compiled brief
    assert "Hard constraints:" in user2   # real cb_engine.compile_shot_contract output
    # THE DIRECTOR HOLDS THIS CHAIR (2026-07-25). This used to pin the phrase "look at
    # it" — incidental wording from when an "Animation Director / Camera" wrote the
    # prompt. The chair moved to the Director, so the assertion now pins the CONTRACT
    # (whose chair it is, and that the keyframe is the stage) rather than a sentence.
    assert "YOU ARE THE DIRECTOR" in system2
    assert "THE FIRST IMAGE IS YOUR STAGE" in system2
    assert "Pete Docter" in system2 and "Glen Keane" in system2
    # and the Cinematographer keeps her own chair — the Director took ANIMATION,
    # not the DP's job. A chair move that quietly collapsed two chairs into one
    # would pass every assertion above and still be wrong.
    assert "register writer for STILL opening frames" in system   # the DP's own contract, hers alone
    assert "THE FORMULA (structural law" in system2
    # the Director's stated intent leads her own charge (see the feltIntent pin above)
    assert "WHAT THIS BEAT IS FOR" in system2
    assert "the grin held too long is the comedy hinge" in system2
    assert "THE HOUSE CRAFT CURRICULUM (verbatim)" in system2
