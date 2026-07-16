#!/usr/bin/env python3
"""test_cb_beats.py — real, standalone regression tests for cb_beats.py.

This module had ZERO test coverage before this file. Matches the existing convention (test_gate_cascade.py,
test_cb_preflight.py, test_unapprove_locks.py): plain Python, assert-driven, no pytest/unittest, a main() that
runs every check and prints PASS/FAIL, sys.exit(1) on any failure. Uses purely SCRATCH/synthetic beat-package
fixtures constructed here — never the real production package — so this never depends on live-state drift.

Covers cb_beats._load_scene_beats(pkg_path, scene_num, d=None) — the shared load-and-filter helper (2026-07-08
dedup pass) that used to be copy-pasted across gate3_dryrun/render_readiness/run/fire_next_beat.

    python3 test_cb_beats.py
"""
import os, sys, json, tempfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cb_beats
import cb_voice


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# Scratch fixture — a beat package spanning multiple scenes, some with an int sceneNumber, some a string, so
# a filter bug that only matches one type would slip past a single-shape fixture.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _multi_scene_package(tmp):
    beats = [
        {"beatCode": "8.B1", "sceneNumber": 8, "slug": "eight_one"},
        {"beatCode": "9.B1", "sceneNumber": 9, "slug": "nine_one"},          # int sceneNumber
        {"beatCode": "9.B2", "sceneNumber": "9", "slug": "nine_two"},        # string sceneNumber, same scene
        {"beatCode": "10.B1", "sceneNumber": 10, "slug": "ten_one"},
    ]
    path = os.path.join(tmp, "Ep9_Scratch_beat_package.json")
    json.dump({"beats": beats, "scenes": []}, open(path, "w"))
    return path, beats


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# 1. _load_scene_beats(pkg_path, "9") returns ONLY beats matching sceneNumber "9" — both when the source
#    field is an int (9.B1's sceneNumber=9) and when it's a string (9.B2's sceneNumber="9"). Beats from
#    other scenes (8.B1, 10.B1) must be excluded.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_filters_to_one_scene_int_and_string(tmp):
    fails = []
    pkg, beats = _multi_scene_package(tmp)

    d, scene_beats = cb_beats._load_scene_beats(pkg, "9")
    codes = sorted(b.get("beatCode") for b in scene_beats)

    if codes != ["9.B1", "9.B2"]:
        fails.append(f"expected exactly ['9.B1', '9.B2'] for scene '9', got {codes}")

    if not any(b.get("beatCode") == "9.B1" for b in scene_beats):
        fails.append("9.B1 (int sceneNumber=9) should match scene_num='9' but was excluded")
    if not any(b.get("beatCode") == "9.B2" for b in scene_beats):
        fails.append("9.B2 (string sceneNumber='9') should match scene_num='9' but was excluded")
    if any(b.get("beatCode") in ("8.B1", "10.B1") for b in scene_beats):
        fails.append(f"beats from other scenes leaked into the scene-9 filter: {codes}")

    # d is the full parsed package dict, handed back regardless of the filter — confirm it still has all 4.
    if len(d.get("beats") or []) != 4:
        fails.append(f"the returned full package dict `d` should still contain all 4 beats, got {len(d.get('beats') or [])}")

    return fails


# Also confirm passing an int scene_num (not just a string) behaves identically — matches every real call
# site's own str(sceneNumber)-equality convention.
def test_filters_to_one_scene_when_scene_num_is_int(tmp):
    fails = []
    pkg, beats = _multi_scene_package(tmp)

    d, scene_beats = cb_beats._load_scene_beats(pkg, 9)
    codes = sorted(b.get("beatCode") for b in scene_beats)
    if codes != ["9.B1", "9.B2"]:
        fails.append(f"expected exactly ['9.B1', '9.B2'] for scene_num=9 (int), got {codes}")
    return fails


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# 2. Calling _load_scene_beats with an already-parsed d= dict does NOT re-read the file — proven by deleting
#    the on-disk package after the first load, then confirming a second call passing the same d= still works
#    (several real call sites, e.g. gate3_dryrun/render_readiness, already have `d` on hand and must not
#    re-parse the file a second time for the same fire).
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_reuses_already_parsed_dict_without_rereading_file(tmp):
    fails = []
    pkg, beats = _multi_scene_package(tmp)

    d, scene_beats_first = cb_beats._load_scene_beats(pkg, "9")
    if sorted(b.get("beatCode") for b in scene_beats_first) != ["9.B1", "9.B2"]:
        fails.append("first load (from disk) did not return the expected scene-9 beats — test setup broken")

    # Now delete the on-disk package entirely — if the second call re-reads the file, it will crash.
    os.remove(pkg)
    if os.path.exists(pkg):
        fails.append("test setup error: package file still exists after os.remove")

    try:
        d2, scene_beats_second = cb_beats._load_scene_beats(pkg, "9", d=d)
    except Exception as e:
        fails.append(f"passing d= should avoid re-reading the (now-deleted) file, but raised: "
                      f"{type(e).__name__}: {e}")
        return fails

    codes2 = sorted(b.get("beatCode") for b in scene_beats_second)
    if codes2 != ["9.B1", "9.B2"]:
        fails.append(f"second call (with d=) should return the same scene-9 beats, got {codes2}")
    if d2 is not d:
        fails.append("second call should hand back the SAME d dict it was passed, not a re-parsed copy")

    return fails


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# 3. _build_voice_track_with_retry (2026-07-09) — ONE-RENDER ECONOMY extended to the voice sub-step. A live
#    scene walk skipped beat 1.B2 when build_dialogue_track returned falsy with no exception raised and no
#    diagnostic printed; the identical call succeeded on manual retry moments later (transient ElevenLabs
#    contention, most likely a concurrent job on the same account). Every other stage already gets one
#    automatic retry before a hard stop (rule 28) — this closes the same gap for voice specifically.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _with_patched_build_dialogue_track(fake, body):
    original = cb_voice.build_dialogue_track
    cb_voice.build_dialogue_track = fake
    try:
        return body()
    finally:
        cb_voice.build_dialogue_track = original


def test_voice_retry_falsy_then_success(tmp):
    fails = []
    calls = []
    def fake(b, out=None, voice_direction=None):
        calls.append(out)
        return None if len(calls) == 1 else {"track": "x.mp3", "lines": [], "speakers": []}
    result = _with_patched_build_dialogue_track(fake, lambda: cb_beats._build_voice_track_with_retry(
        "1.B2", {}, "vo_Ep1_1.B2.mp3", []))
    if result != {"track": "x.mp3", "lines": [], "speakers": []}:
        fails.append(f"expected the 2nd attempt's success dict, got {result}")
    if len(calls) != 2:
        fails.append(f"expected exactly 2 attempts (1 falsy + 1 retry), got {len(calls)}")
    return fails


def test_voice_retry_exhausts_at_two_attempts(tmp):
    fails = []
    calls = []
    def fake(b, out=None, voice_direction=None):
        calls.append(out)
        return None
    result = _with_patched_build_dialogue_track(fake, lambda: cb_beats._build_voice_track_with_retry(
        "1.B2", {}, "vo_Ep1_1.B2.mp3", []))
    if result:
        fails.append(f"expected a falsy result after both attempts fail, got {result}")
    if len(calls) != 2:
        fails.append(f"expected the retry to stop at exactly 2 attempts (never a 3rd), got {len(calls)}")
    return fails


def test_voice_retry_survives_a_raised_exception(tmp):
    fails = []
    calls = []
    def fake(b, out=None, voice_direction=None):
        calls.append(out)
        if len(calls) == 1:
            raise RuntimeError("transient boom")
        return {"track": "y.mp3"}
    result = _with_patched_build_dialogue_track(fake, lambda: cb_beats._build_voice_track_with_retry(
        "1.B2", {}, "vo_Ep1_1.B2.mp3", []))
    if result != {"track": "y.mp3"}:
        fails.append(f"expected the 2nd attempt's success dict after a raised exception on attempt 1, got {result}")
    if len(calls) != 2:
        fails.append(f"expected exactly 2 attempts, got {len(calls)}")
    return fails


def test_voice_retry_no_wasted_retry_on_first_success(tmp):
    fails = []
    calls = []
    def fake(b, out=None, voice_direction=None):
        calls.append(out)
        return {"track": "z.mp3"}
    result = _with_patched_build_dialogue_track(fake, lambda: cb_beats._build_voice_track_with_retry(
        "1.B2", {}, "vo_Ep1_1.B2.mp3", []))
    if result != {"track": "z.mp3"}:
        fails.append(f"expected the 1st attempt's success dict, got {result}")
    if len(calls) != 1:
        fails.append(f"a first-attempt success should never trigger a 2nd call, got {len(calls)} calls")
    return fails


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
CASES = [
    ("filters to one scene (int + string sceneNumber both match)", test_filters_to_one_scene_int_and_string),
    ("filters to one scene when scene_num itself is passed as an int", test_filters_to_one_scene_when_scene_num_is_int),
    ("reuses an already-parsed d= dict without re-reading the file", test_reuses_already_parsed_dict_without_rereading_file),
    ("voice retry: falsy 1st attempt -> succeeds on the automatic retry", test_voice_retry_falsy_then_success),
    ("voice retry: exhausts at exactly 2 attempts, never a 3rd", test_voice_retry_exhausts_at_two_attempts),
    ("voice retry: survives a raised exception on attempt 1 too", test_voice_retry_survives_a_raised_exception),
    ("voice retry: a first-attempt success never wastes a 2nd call", test_voice_retry_no_wasted_retry_on_first_success),
]


def test_run_halts_on_gate3_lint_block_before_any_cost(tmp):
    """THE GAP THAT LET 1.B3'S REAL FAILURE HAPPEN (2026-07-14): cb_replicator.walk_scene already called
    cb_qa.check_gate3_lint before firing — but cb_beats.run() itself, the lower-level function a scratch
    script (or any other direct caller) can call without going through walk_scene, never did. Proves the
    fix: (1) a lint BLOCK stops run() before it reaches any paid step (voice synthesis is the first one —
    tripwired here to raise if ever called, proving zero cost was spent), (2) no exception escapes, (3) no
    clip file is produced. render_readiness and cb_scene are monkeypatched to isolate this one new check
    from the rest of run()'s own heavy pipeline (voice/keyframe/Seedance), matching this file's own
    scratch-fixture-only convention."""
    fails = []
    import cb_qa, cb_scene

    beats = [{"beatCode": "1.B1", "sceneNumber": 1, "slug": "test_beat", "cuts": []}]
    pkg = os.path.join(tmp, "Ep_Lint_Scratch_beat_package.json")
    json.dump({"beats": beats, "scenes": []}, open(pkg, "w"))

    orig_ready = cb_beats.render_readiness
    orig_relay = cb_scene.relay_source_for
    orig_lint = cb_qa.check_gate3_lint
    orig_voice_retry = cb_beats._build_voice_track_with_retry
    try:
        cb_beats.render_readiness = lambda pkg_path, code, episode="Ep1": {"status": "READY_TO_RENDER", "blockers": [], "flags": []}
        cb_scene.relay_source_for = lambda beats, code, episode: (None, "first", None)

        def _tripwire(*a, **k):
            raise AssertionError("voice synthesis was reached — the lint block did NOT stop run() before cost")
        cb_beats._build_voice_track_with_retry = _tripwire

        cb_qa.check_gate3_lint = lambda pkg_path, code, episode: {
            "ok": False, "blockers": ["SIMULATED BLOCK for this test"], "flags": [], "prompt": "", "word_count": 0}

        # keyframe path check happens earlier (missing keyframe -> skip before reaching render_readiness at
        # all) — write a fake keyframe file so execution actually reaches the lint check being tested.
        os.makedirs(os.path.join(tmp, "media"), exist_ok=True)
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            open("media/Ep1_1.B1_test_beat.png", "wb").write(b"\x89PNG\r\n\x1a\nfake")
            clips = cb_beats.run(pkg, 1, "Ep1", codes=["1.B1"])
        finally:
            os.chdir(old_cwd)

        fails += [] if clips == [] else [f"expected no clips produced, got {clips!r}"]
        fails += [] if not os.path.exists(os.path.join(tmp, "media", "Ep1_1.B1_test_beat.mp4")) else ["a clip file was produced despite the lint block"]
    finally:
        cb_beats.render_readiness = orig_ready
        cb_scene.relay_source_for = orig_relay
        cb_qa.check_gate3_lint = orig_lint
        cb_beats._build_voice_track_with_retry = orig_voice_retry

    return fails


CASES.append(("run() halts on a check_gate3_lint BLOCK before any paid step is reached",
               test_run_halts_on_gate3_lint_block_before_any_cost))


def test_run_halts_on_prompt_before_fire_block(tmp):
    """THE PRE-FIRE READ (2026-07-14, Julian: "if you read the prompts before they go for render we wouldn't
    have these issues... we need to fix software wide not prompt specific") — cb_qa.check_prompt_before_fire
    catches contradictions the mechanical lint structurally cannot (a continuity/negative-line contradiction
    only visible on an actual read). Same shape as the lint-block test above: the mechanical lint passes
    clean this time (ok=True), so execution reaches the NEW check; that check is monkeypatched to simulate a
    real contradiction; proves run() halts before voice synthesis (the tripwire) with zero clips produced —
    exactly the "before the event, not after" behaviour this check exists to deliver."""
    fails = []
    import cb_qa, cb_scene

    beats = [{"beatCode": "1.B1", "sceneNumber": 1, "slug": "test_beat", "cuts": []}]
    pkg = os.path.join(tmp, "Ep_PreFireRead_Scratch_beat_package.json")
    json.dump({"beats": beats, "scenes": []}, open(pkg, "w"))

    orig_ready = cb_beats.render_readiness
    orig_relay = cb_scene.relay_source_for
    orig_lint = cb_qa.check_gate3_lint
    orig_read = cb_qa.check_prompt_before_fire
    orig_voice_retry = cb_beats._build_voice_track_with_retry
    try:
        cb_beats.render_readiness = lambda pkg_path, code, episode="Ep1": {"status": "READY_TO_RENDER", "blockers": [], "flags": []}
        cb_scene.relay_source_for = lambda beats, code, episode: (None, "first", None)

        def _tripwire(*a, **k):
            raise AssertionError("voice synthesis was reached — the pre-fire-read block did NOT stop run() before cost")
        cb_beats._build_voice_track_with_retry = _tripwire

        cb_qa.check_gate3_lint = lambda pkg_path, code, episode: {
            "ok": True, "blockers": [], "flags": [], "prompt": "SOME COMPILED PROMPT TEXT", "word_count": 10}
        _calls = []
        def _fake_read(prompt, beat_code, episode="Ep1"):
            _calls.append((prompt, beat_code, episode))
            return {"ok": False, "blockers": ["SIMULATED continuity contradiction"], "skipped": False, "verdict": {}}
        cb_qa.check_prompt_before_fire = _fake_read

        os.makedirs(os.path.join(tmp, "media"), exist_ok=True)
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            open("media/Ep1_1.B1_test_beat.png", "wb").write(b"\x89PNG\r\n\x1a\nfake")
            clips = cb_beats.run(pkg, 1, "Ep1", codes=["1.B1"])
        finally:
            os.chdir(old_cwd)

        fails += [] if clips == [] else [f"expected no clips produced, got {clips!r}"]
        fails += [] if not os.path.exists(os.path.join(tmp, "media", "Ep1_1.B1_test_beat.mp4")) else ["a clip file was produced despite the pre-fire-read block"]
        fails += [] if _calls and _calls[0][0] == "SOME COMPILED PROMPT TEXT" and _calls[0][1] == "1.B1" else [f"check_prompt_before_fire wasn't called with the lint's own compiled prompt: {_calls!r}"]
    finally:
        cb_beats.render_readiness = orig_ready
        cb_scene.relay_source_for = orig_relay
        cb_qa.check_gate3_lint = orig_lint
        cb_qa.check_prompt_before_fire = orig_read
        cb_beats._build_voice_track_with_retry = orig_voice_retry

    return fails


CASES.append(("run() halts on a check_prompt_before_fire BLOCK before any paid step is reached",
               test_run_halts_on_prompt_before_fire_block))


def test_run_refuses_when_scene_plate_missing(tmp):
    """LAW 3, EXTENDED TO THE PLATE SLOT (2026-07-15, seam audit — Gate 1->2->3 handoff review):
    cb_segprompt.emit_v5 computes `plate_n = len(cast) + 2` UNCONDITIONALLY and always emits the "@图{plate_n}
    scene plate..." sentence — the compiled prompt always claims a plate reference exists — but run() only
    ever appended the plate file to the upload list `if os.path.exists(_plate)`, with no refusal, unlike the
    Law 3 character-anchor check right above it (which DOES refuse on a missing anchor). Proves the fix: a
    beat with everything else green but no scene-plate file on disk is REFUSED before any generation call,
    with zero clip produced — matching the existing character-anchor refusal's own behaviour exactly. Every
    heavy dependency between the lint checks and the plate check (voice synthesis, gate3_prepare, the v5
    prompt compile) is monkeypatched to a harmless stub so only the new plate-existence check is under test."""
    fails = []
    import cb_qa, cb_scene, cb_seedance, cb_segprompt, cb_gen

    beats = [{"beatCode": "1.B1", "sceneNumber": 1, "slug": "test_beat", "cuts": [],
              "openingCast": [], "characters": []}]
    pkg = os.path.join(tmp, "Ep_PlateRefuse_Scratch_beat_package.json")
    json.dump({"beats": beats, "scenes": []}, open(pkg, "w"))

    orig_ready = cb_beats.render_readiness
    orig_relay = cb_scene.relay_source_for
    orig_lint = cb_qa.check_gate3_lint
    orig_read = cb_qa.check_prompt_before_fire
    orig_vd = cb_seedance.director_voice_direction
    orig_voice_retry = cb_beats._build_voice_track_with_retry
    orig_prepare = cb_beats.gate3_prepare
    orig_shipped = cb_segprompt.shipped_prompt
    orig_gen = cb_gen.generate_video_seedance_ref
    try:
        cb_beats.render_readiness = lambda pkg_path, code, episode="Ep1": {"status": "READY_TO_RENDER", "blockers": [], "flags": []}
        cb_scene.relay_source_for = lambda beats, code, episode: (None, "first", None)
        cb_qa.check_gate3_lint = lambda pkg_path, code, episode: {
            "ok": True, "blockers": [], "flags": [], "prompt": "A COMPILED TEST PROMPT", "word_count": 4}
        cb_qa.check_prompt_before_fire = lambda prompt, beat_code, episode="Ep1": {
            "ok": True, "blockers": [], "skipped": False, "verdict": {}}
        cb_seedance.director_voice_direction = lambda pkg_path, code, episode: {}
        cb_beats._build_voice_track_with_retry = lambda code, b, out, vd: None   # wordless — no dialogue on this beat
        cb_beats.gate3_prepare = lambda pkg_path, beat, episode="Ep1": {"refuse": False, "prompt": {}, "builder": "test"}
        cb_segprompt.shipped_prompt = lambda beat, scene=None, relay=False, prev_end_state_still=None, prev_carry_marks=None, episode="Ep1": (
            "A COMPILED TEST PROMPT", "test_v5", True)

        def _tripwire(*a, **k):
            raise AssertionError("generate_video_seedance_ref was reached — the missing-plate refusal did NOT stop run()")
        cb_gen.generate_video_seedance_ref = _tripwire

        os.makedirs(os.path.join(tmp, "media"), exist_ok=True)
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            open("media/Ep1_1.B1_test_beat.png", "wb").write(b"\x89PNG\r\n\x1a\nfake")
            # NOTE: deliberately NO media/Ep1_S1_plate.png written — this is the exact gap being tested.
            clips = cb_beats.run(pkg, 1, "Ep1", codes=["1.B1"])
        finally:
            os.chdir(old_cwd)

        fails += [] if clips == [] else [f"expected no clips produced, got {clips!r}"]
        fails += [] if not os.path.exists(os.path.join(tmp, "media", "Ep1_1.B1_test_beat.mp4")) else ["a clip file was produced despite the missing scene plate"]
    finally:
        cb_beats.render_readiness = orig_ready
        cb_scene.relay_source_for = orig_relay
        cb_qa.check_gate3_lint = orig_lint
        cb_qa.check_prompt_before_fire = orig_read
        cb_seedance.director_voice_direction = orig_vd
        cb_beats._build_voice_track_with_retry = orig_voice_retry
        cb_beats.gate3_prepare = orig_prepare
        cb_segprompt.shipped_prompt = orig_shipped
        cb_gen.generate_video_seedance_ref = orig_gen

    return fails


CASES.append(("run() refuses to fire when the scene plate is missing, even though the compiled prompt "
               "unconditionally claims one (Law 3 extended to the plate slot)",
               test_run_refuses_when_scene_plate_missing))


def test_run_proceeds_past_prompt_before_fire_when_skipped(tmp):
    """A genuine infra outage (both LLM providers down) must NEVER block a render on its own — that would
    let an unrelated API hiccup brick the whole pipeline. Proves the SKIPPED case is treated as a pass-
    through: execution reaches past the check (the tripwire below fires, proving it got that far), never
    silently confused with either a real pass or a real block."""
    fails = []
    import cb_qa, cb_scene

    beats = [{"beatCode": "1.B1", "sceneNumber": 1, "slug": "test_beat", "cuts": []}]
    pkg = os.path.join(tmp, "Ep_PreFireReadSkip_Scratch_beat_package.json")
    json.dump({"beats": beats, "scenes": []}, open(pkg, "w"))

    orig_ready = cb_beats.render_readiness
    orig_relay = cb_scene.relay_source_for
    orig_lint = cb_qa.check_gate3_lint
    orig_read = cb_qa.check_prompt_before_fire
    orig_voice_retry = cb_beats._build_voice_track_with_retry
    try:
        cb_beats.render_readiness = lambda pkg_path, code, episode="Ep1": {"status": "READY_TO_RENDER", "blockers": [], "flags": []}
        cb_scene.relay_source_for = lambda beats, code, episode: (None, "first", None)
        cb_qa.check_gate3_lint = lambda pkg_path, code, episode: {
            "ok": True, "blockers": [], "flags": [], "prompt": "SOME COMPILED PROMPT TEXT", "word_count": 10}
        cb_qa.check_prompt_before_fire = lambda prompt, beat_code, episode="Ep1": {
            "ok": True, "blockers": [], "skipped": True, "verdict": None, "skipped_reason": "both providers down (simulated)"}

        _reached = {"v": False}
        def _proof_of_progress(*a, **k):
            _reached["v"] = True
            raise AssertionError("stopping here on purpose — proves execution reached past the skipped pre-fire read")
        cb_beats._build_voice_track_with_retry = _proof_of_progress

        os.makedirs(os.path.join(tmp, "media"), exist_ok=True)
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            open("media/Ep1_1.B1_test_beat.png", "wb").write(b"\x89PNG\r\n\x1a\nfake")
            try:
                cb_beats.run(pkg, 1, "Ep1", codes=["1.B1"])
            except AssertionError as e:
                if "proves execution reached past" not in str(e):
                    fails.append(f"unexpected assertion: {e}")
        finally:
            os.chdir(old_cwd)

        fails += [] if _reached["v"] else ["execution never reached past the skipped pre-fire read — a skip incorrectly halted the beat"]
    finally:
        cb_beats.render_readiness = orig_ready
        cb_scene.relay_source_for = orig_relay
        cb_qa.check_gate3_lint = orig_lint
        cb_qa.check_prompt_before_fire = orig_read
        cb_beats._build_voice_track_with_retry = orig_voice_retry

    return fails


CASES.append(("run() proceeds past a SKIPPED pre-fire read (infra failure never silently blocks)",
               test_run_proceeds_past_prompt_before_fire_when_skipped))


def test_render_readiness_surfaces_failed_keyframe_qa_as_a_flag(tmp):
    """THE KEYFRAME-QA-SILENTLY-SHIPS-ANYWAY GAP (2026-07-14, full-pipeline verification audit): confirmed
    live against real production data that 1.B1's real keyframe had a real, on-disk ok:false
    ACTION_STATE_MISMATCH verdict in its .keyframe_qa.json sidecar, and the real, billed video render fired
    anyway — render_readiness never read that sidecar at all. Proves the fix, isolated from render_readiness's
    other heavy dependencies (cb_seedance/cb_scene/cb_voice/cb_prompts/cb_qa are all monkeypatched to a clean,
    green baseline so only the new keyframe-QA-flag code path is under test): a failing sidecar surfaces as a
    FLAG (never a blocker — status stays READY_TO_RENDER, matching this project's vision-QA report-only
    doctrine), and a PASSING (or missing) sidecar produces no such flag at all."""
    fails = []
    import cb_qa, cb_scene, cb_seedance, cb_prompts as P

    beats = [{"beatCode": "1.B1", "sceneNumber": 1, "slug": "test_beat",
              "openingCast": [], "endStateStill": "he holds the pose", "atmosphere": "meadow hum",
              "endState": "he settles"}]
    pkg = os.path.join(tmp, "Ep_KFQA_Scratch_beat_package.json")
    json.dump({"beats": beats, "scenes": [{"sceneNumber": 1, "ambientBed": "meadow hum"}]}, open(pkg, "w"))

    orig_get_prompt = cb_seedance.get_seedance_prompt
    orig_relay = cb_scene.relay_source_for
    orig_audit = cb_voice.audit_attribution
    orig_stale = P.scene_cache_stale
    orig_vocab = cb_qa.check_scene_vocabulary
    try:
        cb_seedance.get_seedance_prompt = lambda pkg_path, code, mode="render", episode="Ep1": {
            "authoring": {"physical_action_archetype": "SOME_ARCHETYPE"}, "raw": True,
            "authoring_validator": {"ok": True, "rejects": []},
            "compact_validator": {"ok": True, "rejects": []},
            "readiness_status": "READY",
        }
        cb_scene.relay_source_for = lambda beats, code, episode: (None, "first", None)
        cb_voice.audit_attribution = lambda pkg_path: []
        P.scene_cache_stale = lambda episode, scene_num, pkg_path=None: None
        cb_qa.check_scene_vocabulary = lambda pkg_path, scene_num, episode: {"ok": True, "verdict": "clean"}

        os.makedirs(os.path.join(tmp, "media"), exist_ok=True)
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            open("media/Ep1_1.B1_test_beat.png", "wb").write(b"\x89PNG\r\n\x1a\nfake")

            # CASE 1 — a real, failing sidecar (the exact shape check_scene actually writes)
            open("media/Ep1_1.B1_test_beat.keyframe_qa.json", "w").write(json.dumps({
                "shot": "1.B1", "ok": False,
                "verdict": "FLAG\n  [START] FAIL: ACTION_STATE_MISMATCH — restage so the pose actively performs the action",
                "reasons": ["ACTION_STATE_MISMATCH"],
            }))
            r_fail = cb_beats.render_readiness(pkg, "1.B1", "Ep1")
            fails += [] if r_fail["status"] == "READY_TO_RENDER" else \
                [f"a FAILING keyframe QA sidecar must never turn into a hard blocker, got status={r_fail['status']!r}"]
            fails += [] if any("ACTION_STATE_MISMATCH" in fl for fl in r_fail["flags"]) else \
                [f"expected an ACTION_STATE_MISMATCH flag, got flags={r_fail['flags']!r}"]

            # CASE 2 — a passing sidecar produces no such flag
            open("media/Ep1_1.B1_test_beat.keyframe_qa.json", "w").write(json.dumps(
                {"shot": "1.B1", "ok": True, "verdict": "PASS", "reasons": []}))
            r_pass = cb_beats.render_readiness(pkg, "1.B1", "Ep1")
            fails += [] if not any("Definition-of-Done FAILED" in fl for fl in r_pass["flags"]) else \
                [f"a PASSING sidecar must never produce a Definition-of-Done flag, got flags={r_pass['flags']!r}"]

            # CASE 3 — no sidecar at all (e.g. Gate-2b keyframe QA never ran) degrades cleanly, no crash
            os.remove("media/Ep1_1.B1_test_beat.keyframe_qa.json")
            r_none = cb_beats.render_readiness(pkg, "1.B1", "Ep1")
            fails += [] if not any("Definition-of-Done FAILED" in fl for fl in r_none["flags"]) else \
                [f"a missing sidecar must never produce a Definition-of-Done flag, got flags={r_none['flags']!r}"]
        finally:
            os.chdir(old_cwd)
    finally:
        cb_seedance.get_seedance_prompt = orig_get_prompt
        cb_scene.relay_source_for = orig_relay
        cb_voice.audit_attribution = orig_audit
        P.scene_cache_stale = orig_stale
        cb_qa.check_scene_vocabulary = orig_vocab

    return fails


CASES.append(("render_readiness surfaces a failed keyframe Definition-of-Done check as a flag, never a blocker",
               test_render_readiness_surfaces_failed_keyframe_qa_as_a_flag))


def main():
    tmp = tempfile.mkdtemp(prefix="cb_beats_test_")
    bad = 0
    try:
        for label, fn in CASES:
            case_tmp = tempfile.mkdtemp(dir=tmp)
            try:
                fails = fn(case_tmp)
            except Exception as e:
                fails = [f"EXCEPTION: {type(e).__name__}: {e}"]
            if fails:
                bad += 1
                print(f"FAIL  {label}")
                for f in fails:
                    print(f"        - {f}")
            else:
                print(f"PASS  {label}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if bad:
        print(f"{bad}/{len(CASES)} CASE(S) FAILED")
        return 1
    print(f"ALL {len(CASES)} CASES PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
