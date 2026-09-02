#!/usr/bin/env python3
"""test_cb_post.py — regression coverage for cb_post.run()'s picture-assembly wiring (2026-07-14).

THE BUG THIS GUARDS: assemble_conformed (JOIN ON LIVE MOTION, Julian's own 2026-07-03 doctrine) was fully
built and documented as Gate 5's real assembler but had ZERO live callers — run() called assemble_picture
(the raw butt-join) exclusively, confirmed stale by two separate audits (CLAUDE.md rules 46/49) and never
closed until this fix. This file locks in: (1) a multi-clip scene's real Gate-5 picture is built via
assemble_conformed, with assemble_picture's own output saved alongside as a named raw comparison copy;
(2) a single-clip scene (no join to conform) falls back to assemble_picture directly, with no redundant
raw-copy file; (3) assemble_conformed's own failure contract (None on a real ffmpeg failure, matching its
siblings assemble_picture/mix) actually stops run() before mix/review/CapCut-stems, the same guarantee
those two already had.

ZERO API/ffmpeg calls: every ffmpeg-touching function (_clips/_norm/assemble_picture/assemble_conformed/mix/
cb_address) is monkeypatched to a fake that records what it was called with — this tests run()'s OWN control
flow (which function it calls, in what order, with what fallback), not ffmpeg's actual trim/concat math
(assemble_conformed's trim arithmetic is pre-existing, unchanged by this fix).

Convention matches test_cb_beats.py / test_cb_scene.py: plain Python, a fails-list-of-strings pattern, a
main() that prints PASS/FAIL per case and sys.exit(1) on any failure.

    python3 test_cb_post.py
"""
import os, sys, json, pathlib, tempfile, shutil

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cb_post


def test_replace_guide_dialogue_discards_provider_audio(monkeypatch, tmp_path):
    video = tmp_path / "provider.mp4"
    voice = tmp_path / "approved.wav"
    out = tmp_path / "review.mp4"
    video.write_bytes(b"provider")
    voice.write_bytes(b"approved")
    monkeypatch.setattr(cb_post, "_dur", lambda path: 12.0)
    captured = {}

    def fake_run(cmd, capture_output, text):
        captured["cmd"] = cmd
        pathlib.Path(cmd[-1]).write_bytes(b"review")
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(cb_post.subprocess, "run", fake_run)

    assert cb_post.replace_guide_dialogue(video, voice, out) == str(out)
    command = " ".join(captured["cmd"])
    assert "[0:a]" not in command
    assert "amix=" not in command
    assert "[1:a]" in command
    assert "[dialogue]" in command


def _scratch(fn):
    """REAL, PRE-EXISTING BUG FOUND AND FIXED HERE (2026-07-14, while adversarially verifying the SFX-
    sweetening build): cb_post.run()'s own FIRST LINE is `os.chdir(os.path.dirname(os.path.abspath(__file__)))`
    — deliberate, correct PRODUCTION behaviour ("resets cwd so relative media/ paths resolve regardless of
    caller's cwd") but it silently DEFEATS this function's own isolation strategy, since __file__ always
    resolves to the REAL cb_post.py in engine/, not this scratch tmpdir — every test that calls cb_post.run()
    was writing its fake output (and, via run()'s own un-mocked glob.glob for CapCut voice stems, REAL copies
    of production voice .mp3s) straight into the REAL engine/media/ directory, confirmed live (a routine test
    run left 1-byte fake .mp4 stubs at media/Ep1_Scene1_{complete,picture,picture_RAW}.mp4 and a fake stems_
    Ep1_Scene1/ folder). Confirmed NO real production data was ever destroyed (Gate 5 has never fired for real
    against this scene — still gate-blocked at the time this was found — and the real source vo_Ep1_*.mp3
    files were only ever read/copied, never mutated), but the risk is real for the day Gate 5 DOES fire for
    real. Fixed at the source of the isolation break: cb_post.__file__ is a real, patchable module attribute,
    not a filesystem read — pointing it at a (non-existent, string-only) path INSIDE the scratch tmpdir makes
    run()'s own chdir target the scratch dir instead of the real engine/ directory, restoring true isolation
    without touching cb_post.py's own correct production behaviour at all."""
    tmp = tempfile.mkdtemp(prefix="cb_post_test_")
    cwd = os.getcwd()
    os.makedirs(os.path.join(tmp, "media"), exist_ok=True)
    orig_file = cb_post.__file__
    cb_post.__file__ = os.path.join(tmp, "cb_post.py")
    os.chdir(tmp)
    try:
        return fn()
    finally:
        os.chdir(cwd)
        cb_post.__file__ = orig_file
        shutil.rmtree(tmp, ignore_errors=True)


def _patch(monkeypatches):
    """monkeypatches: {name: fake_fn} — patches cb_post.<name>, returns a restore() callback."""
    originals = {name: getattr(cb_post, name) for name in monkeypatches}
    for name, fn in monkeypatches.items():
        setattr(cb_post, name, fn)
    def restore():
        for name, fn in originals.items():
            setattr(cb_post, name, fn)
    return restore


# (test_multiclip_uses_conformed_and_saves_raw_comparison deleted at the 2026-07-16 cutover — it preserved legacy run()/sweetening behaviour)
# (test_singleclip_falls_back_to_assemble_picture_no_redundant_raw deleted at the 2026-07-16 cutover — it preserved legacy run()/sweetening behaviour)
# (test_conformed_failure_stops_run_before_mix deleted at the 2026-07-16 cutover — it preserved legacy run()/sweetening behaviour)
class _FakeCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode; self.stdout = stdout; self.stderr = stderr


def _fake_ffmpeg_ffprobe_run(cmd, capture_output=True, text=True):
    """A single fake standing in for subprocess.run across BOTH ffprobe (used by _dur) and ffmpeg (used by
    mix/assemble_*) calls — distinguished by cmd[0]. ffmpeg calls 'succeed' by writing their own -y output
    path (always cmd[-1] for every ffmpeg invocation in this module) so os.path.exists(out) checks pass."""
    if cmd and cmd[0] == "ffprobe":
        return _FakeCompleted(stdout="5.0")
    if cmd and cmd[-1] == "-" and "loudnorm" in " ".join(cmd):
        return _FakeCompleted(stderr=json.dumps({
            "input_i": "-20.0", "input_tp": "-4.0", "input_lra": "3.0",
            "input_thresh": "-30.0", "target_offset": "0.0",
        }))
    open(cmd[-1], "w", encoding="utf-8").write("x")
    return _FakeCompleted(returncode=0)


def test_mix_uses_correct_loudness_target_per_platform():
    """LOUDNESS_TARGETS (2026-07-14): each named platform must actually reach the ffmpeg loudnorm filter with
    ITS OWN I/TP/LRA values — not a single hardcoded number regardless of what platform was asked for."""
    def _run():
        open("picture.mp4", "w", encoding="utf-8").write("x")
        orig = cb_post.subprocess.run
        cmds = {}
        try:
            for plat in cb_post.LOUDNESS_TARGETS:
                # capture the LAST subprocess.run call (the ffmpeg mix call) per platform — always delegates
                # to the ORIGINAL fixed fake (_fake_ffmpeg_ffprobe_run), never the previous iteration's own
                # capturing wrapper (which would recurse into itself once reassigned to cb_post.subprocess.run).
                captured = []
                def capturing(cmd, capture_output=True, text=True, _captured=captured):
                    _captured.append(cmd)
                    return _fake_ffmpeg_ffprobe_run(cmd, capture_output, text)
                cb_post.subprocess.run = capturing
                cb_post.mix("picture.mp4", "nomusic.mp3", "noamb.mp3", f"out_{plat}.mp4", platform=plat)
                cmds[plat] = next((c for c in captured if c[0] == "ffmpeg"), None)
        finally:
            cb_post.subprocess.run = orig
        return cmds

    cmds = _scratch(_run)
    fails = []
    for plat, tgt in cb_post.LOUDNESS_TARGETS.items():
        cmd = cmds.get(plat)
        fc = next((a for a in (cmd or []) if isinstance(a, str) and "loudnorm" in a), None)
        expect = f"loudnorm=I={tgt['I']}:TP={tgt['TP']}:LRA={tgt['LRA']}"
        ok = bool(fc) and expect in fc
        print(f"  {'PASS' if ok else 'FAIL'}  {plat}: ffmpeg filter carries its own target ({expect}) — got {fc}")
        if not ok:
            fails.append(f"mix(platform={plat!r}) did not build the expected loudnorm clause {expect!r}: {fc}")
    assert not fails, "\n".join(fails)


def test_mix_unrecognized_platform_falls_back_to_default():
    """An unrecognized/typo'd platform name must degrade to DEFAULT_PLATFORM's target, never raise — this is
    a mastering CHOICE, not a hard gate."""
    def _run():
        open("picture.mp4", "w", encoding="utf-8").write("x")
        orig = cb_post.subprocess.run
        captured = []
        def capturing(cmd, capture_output=True, text=True):
            captured.append(cmd)
            return _fake_ffmpeg_ffprobe_run(cmd, capture_output, text)
        cb_post.subprocess.run = capturing
        try:
            r = cb_post.mix("picture.mp4", "nomusic.mp3", "noamb.mp3", "out.mp4", platform="not_a_real_platform")
        finally:
            cb_post.subprocess.run = orig
        return r, captured
    result, captured = _scratch(_run)
    fails = []
    ok_no_crash = result == "out.mp4"
    print(f"  {'PASS' if ok_no_crash else 'FAIL'}  an unrecognized platform name does not raise, mix() completes — got {result!r}")
    if not ok_no_crash:
        fails.append(f"mix() with an unrecognized platform did not complete cleanly: {result!r}")
    tgt = cb_post.LOUDNESS_TARGETS[cb_post.DEFAULT_PLATFORM]
    cmd = next((c for c in captured if c[0] == "ffmpeg"), None)
    fc = next((a for a in (cmd or []) if isinstance(a, str) and "loudnorm" in a), None)
    expect = f"loudnorm=I={tgt['I']}:TP={tgt['TP']}:LRA={tgt['LRA']}"
    ok_default = bool(fc) and expect in fc
    print(f"  {'PASS' if ok_default else 'FAIL'}  falls back to DEFAULT_PLATFORM's own target ({expect}) — got {fc}")
    if not ok_default:
        fails.append(f"unrecognized-platform fallback did not use DEFAULT_PLATFORM's target: {fc}")
    assert not fails, "\n".join(fails)


def test_build_platform_masters_refuses_cleanly_with_no_picture():
    """No picture.mp4 for the scene (Gate 5 hasn't fired yet) -> a clear refusal, empty result, never a crash."""
    def _run():
        return cb_post.build_platform_masters("pkg.json", "1", "Ep1")
    result = _scratch(_run)
    ok = result == {}
    print(f"  {'PASS' if ok else 'FAIL'}  no picture on disk -> refuses cleanly with an empty dict — got {result!r}")
    assert ok, f"build_platform_masters with no picture should return {{}}, got {result!r}"


def test_build_platform_masters_calls_mix_once_per_platform():
    """With a real picture present, one master file per requested platform, each via mix() with the RIGHT
    platform kwarg and the RIGHT output filename."""
    calls = []
    def fake_mix(picture, music, amb, out, platform=cb_post.DEFAULT_PLATFORM, sfx_layers=None):
        calls.append((platform, out)); open(out, "w", encoding="utf-8").write("x"); return out
    def _run():
        os.makedirs("media", exist_ok=True)
        open("media/Ep1_Scene1_picture.mp4", "w", encoding="utf-8").write("x")
        restore = _patch({"mix": fake_mix})
        try:
            return cb_post.build_platform_masters("pkg.json", "1", "Ep1", platforms=("youtube", "netflix"))
        finally:
            restore()
    result = _scratch(_run)
    fails = []
    ok_keys = set(result.keys()) == {"youtube", "netflix"}
    print(f"  {'PASS' if ok_keys else 'FAIL'}  exactly the 2 requested platforms in the result — got {result!r}")
    if not ok_keys:
        fails.append(f"build_platform_masters returned wrong keys: {result!r}")
    ok_calls = ("youtube", "media/Ep1_Scene1_master_youtube.mp4") in calls and \
               ("netflix", "media/Ep1_Scene1_master_netflix.mp4") in calls
    print(f"  {'PASS' if ok_calls else 'FAIL'}  mix() called once per platform with the correctly-named output — got {calls}")
    if not ok_calls:
        fails.append(f"build_platform_masters called mix() with wrong platform/output pairing: {calls}")
    assert not fails, "\n".join(fails)


def test_build_vertical_derivative_refuses_cleanly_with_no_source():
    """No source file on disk -> a clear refusal (None), never a crash."""
    def _run():
        return cb_post.build_vertical_derivative("media/does_not_exist.mp4", "media/out_vertical.mp4")
    result = _scratch(_run)
    ok = result is None
    print(f"  {'PASS' if ok else 'FAIL'}  no source on disk -> refuses cleanly (None) — got {result!r}")
    assert ok, f"build_vertical_derivative with no source should return None, got {result!r}"


def test_build_vertical_derivative_builds_centre_crop_and_scale():
    """A real source -> the ffmpeg call carries the centre-anchored crop filter (ih*9/16 width, full height,
    centred x-offset) followed by a scale to the target resolution — the actual 'centre-safe 9:16' math."""
    def _run():
        os.makedirs("media", exist_ok=True)
        open("media/complete.mp4", "w", encoding="utf-8").write("x")
        orig = cb_post.subprocess.run
        captured = []
        def capturing(cmd, capture_output=True, text=True):
            captured.append(cmd)
            return _fake_ffmpeg_ffprobe_run(cmd, capture_output, text)
        cb_post.subprocess.run = capturing
        try:
            r = cb_post.build_vertical_derivative("media/complete.mp4", "media/out_vertical.mp4",
                                                    target_w=1080, target_h=1920)
        finally:
            cb_post.subprocess.run = orig
        return r, captured
    result, captured = _scratch(_run)
    fails = []
    ok_result = result == "media/out_vertical.mp4"
    print(f"  {'PASS' if ok_result else 'FAIL'}  build_vertical_derivative returns the output path on success — got {result!r}")
    if not ok_result:
        fails.append(f"build_vertical_derivative did not return the expected output path: {result!r}")
    cmd = next((c for c in captured if c[0] == "ffmpeg"), None)
    vf = None
    if cmd and "-vf" in cmd:
        vf = cmd[cmd.index("-vf") + 1]
    ok_crop = bool(vf) and "crop=ih*9/16:ih:(iw-ih*9/16)/2:0" in vf
    ok_scale = bool(vf) and "scale=1080:1920" in vf
    print(f"  {'PASS' if ok_crop else 'FAIL'}  ffmpeg filter carries the centre-anchored crop — got {vf}")
    print(f"  {'PASS' if ok_scale else 'FAIL'}  ffmpeg filter scales to the requested 1080x1920 target — got {vf}")
    for ok, msg in [(ok_crop, f"vertical derivative crop filter missing/wrong: {vf}"),
                     (ok_scale, f"vertical derivative scale filter missing/wrong: {vf}")]:
        if not ok:
            fails.append(msg)
    assert not fails, "\n".join(fails)


def test_load_sfx_library_gracefully_degrades_on_missing_manifest():
    """No config/sfx_library.json on disk -> an empty dict, never a crash (matching mix()'s own have_mus/
    have_amb file-exists convention, never gag_locks.json's hard-fail-on-missing-key one)."""
    def _run():
        # T44: the manifest path comes from the project profile (absolute), not the cwd — point the
        # module at a path that does not exist inside the scratch dir to exercise "no manifest".
        saved = cb_post.SFX_LIBRARY_PATH
        cb_post.SFX_LIBRARY_PATH = os.path.join(os.getcwd(), "config", "sfx_library.json")
        try:
            return cb_post._load_sfx_library()
        finally:
            cb_post.SFX_LIBRARY_PATH = saved
    result = _scratch(_run)
    ok = result == {}
    print(f"  {'PASS' if ok else 'FAIL'}  missing manifest -> empty dict, no crash — got {result!r}")
    assert ok, f"_load_sfx_library() with no manifest should return {{}}, got {result!r}"


def test_load_sfx_library_loads_real_manifest_excluding_underscore_keys():
    """A real manifest loads its real cue entries and excludes the '_note' documentation key."""
    def _run():
        os.makedirs("config", exist_ok=True)
        json.dump({"_note": "docs, not a cue", "FWIP": {"file": "sfx/fwip.mp3"}},
                   open("config/sfx_library.json", "w", encoding="utf-8"))
        return cb_post._load_sfx_library()
    result = _scratch(_run)
    fails = []
    ok_has_cue = "FWIP" in result and result["FWIP"]["file"] == "sfx/fwip.mp3"
    ok_no_note = "_note" not in result
    print(f"  {'PASS' if ok_has_cue else 'FAIL'}  real cue entry loads correctly — got {result!r}")
    print(f"  {'PASS' if ok_no_note else 'FAIL'}  '_note' documentation key excluded — got keys {list(result.keys())}")
    if not ok_has_cue:
        fails.append(f"_load_sfx_library() did not load the real FWIP entry: {result!r}")
    if not ok_no_note:
        fails.append(f"_load_sfx_library() did not exclude the '_note' key: {list(result.keys())}")
    assert not fails, "\n".join(fails)


# (test_sweeten_cues_for_scene_only_returns_cues_with_assets_on_disk deleted at the 2026-07-16 cutover — it preserved legacy run()/sweetening behaviour)
def test_mix_sfx_layers_reaches_ffmpeg_filter_with_adelay_and_atrim():
    """A real sfx_layers entry must produce an adelay clause at the RIGHT millisecond offset and an atrim
    clause bounding it to the picture's own duration — the actual overshoot guard, not just 'it ran'."""
    def _run():
        os.makedirs("media", exist_ok=True)
        open("picture.mp4", "w", encoding="utf-8").write("x")
        sfx = "media/fwip.mp3"; open(sfx, "w", encoding="utf-8").write("x")
        orig = cb_post.subprocess.run
        captured = []
        def capturing(cmd, capture_output=True, text=True):
            captured.append(cmd)
            return _fake_ffmpeg_ffprobe_run(cmd, capture_output, text)
        cb_post.subprocess.run = capturing
        try:
            r = cb_post.mix("picture.mp4", "nomusic.mp3", "noamb.mp3", "out.mp4",
                             sfx_layers=[{"file": sfx, "at_sec": 2.5}])
        finally:
            cb_post.subprocess.run = orig
        return r, captured
    result, captured = _scratch(_run)
    fails = []
    ok_success = result == "out.mp4"
    print(f"  {'PASS' if ok_success else 'FAIL'}  mix() with a real sfx_layers entry succeeds — got {result!r}")
    if not ok_success:
        fails.append(f"mix() with a real sfx layer did not succeed: {result!r}")
    cmd = next((c for c in captured if c[0] == "ffmpeg"), None)
    fc = next((a for a in (cmd or []) if isinstance(a, str) and "adelay" in a), None)
    ok_delay = bool(fc) and "adelay=2500|2500" in fc   # 2.5s -> 2500ms, paired stereo L/R per ffmpeg's own requirement
    ok_atrim = bool(fc) and "atrim=0:" in fc            # the overshoot guard on the sfx branch itself
    ok_sfx_input = bool(cmd) and "media/fwip.mp3" in cmd   # the file actually reached ffmpeg's -i list
    print(f"  {'PASS' if ok_delay else 'FAIL'}  adelay carries the correct paired-stereo millisecond offset — got {fc}")
    print(f"  {'PASS' if ok_atrim else 'FAIL'}  the sfx branch is atrim'd to the picture's own duration — got {fc}")
    print(f"  {'PASS' if ok_sfx_input else 'FAIL'}  the sfx file reached ffmpeg's own -i input list — got {cmd}")
    for ok, msg in [(ok_delay, f"adelay clause missing/wrong: {fc}"),
                     (ok_atrim, f"atrim overshoot guard missing on the sfx branch: {fc}"),
                     (ok_sfx_input, f"sfx file never reached ffmpeg's inputs: {cmd}")]:
        if not ok:
            fails.append(msg)
    assert not fails, "\n".join(fails)


def test_mix_sfx_layers_missing_file_silently_skipped():
    """An sfx_layers entry pointing at a file that doesn't exist on disk is silently dropped — mix() still
    succeeds, and the missing file never reaches ffmpeg's own -i input list."""
    def _run():
        os.makedirs("media", exist_ok=True)
        open("picture.mp4", "w", encoding="utf-8").write("x")
        orig = cb_post.subprocess.run
        captured = []
        def capturing(cmd, capture_output=True, text=True):
            captured.append(cmd)
            return _fake_ffmpeg_ffprobe_run(cmd, capture_output, text)
        cb_post.subprocess.run = capturing
        try:
            r = cb_post.mix("picture.mp4", "nomusic.mp3", "noamb.mp3", "out.mp4",
                             sfx_layers=[{"file": "media/does_not_exist.mp3", "at_sec": 1.0}])
        finally:
            cb_post.subprocess.run = orig
        return r, captured
    result, captured = _scratch(_run)
    fails = []
    ok_success = result == "out.mp4"
    print(f"  {'PASS' if ok_success else 'FAIL'}  mix() still succeeds with a missing sfx file — got {result!r}")
    if not ok_success:
        fails.append(f"mix() should still succeed when the sfx file is missing: {result!r}")
    cmd = next((c for c in captured if c[0] == "ffmpeg"), None)
    ok_not_input = bool(cmd) and "media/does_not_exist.mp3" not in cmd
    print(f"  {'PASS' if ok_not_input else 'FAIL'}  the missing file never reached ffmpeg's -i input list — got {cmd}")
    if not ok_not_input:
        fails.append(f"a missing sfx file leaked into ffmpeg's inputs: {cmd}")
    assert not fails, "\n".join(fails)


def _patch_module(mod, monkeypatches):
    originals = {name: getattr(mod, name) for name in monkeypatches}
    for name, fn in monkeypatches.items():
        setattr(mod, name, fn)
    def restore():
        for name, fn in originals.items():
            setattr(mod, name, fn)
    return restore


def test_conform_plan_protects_dialogue_from_edge_and_settle_trim(monkeypatch):
    monkeypatch.setattr(cb_post, "_dur", lambda path: 6.0)
    monkeypatch.setattr(cb_post, "_clip_fps", lambda path: 24.0)
    plan = cb_post.conform_plan(
        ["first.mp4", "second.mp4"],
        protected_windows=[[{"startSec": 0.0, "endSec": 5.5}], []],
        settle_trim=2.0, edge_frames=4)
    assert plan[0]["sourceStartSec"] == 0.0
    assert plan[0]["sourceEndSec"] == 5.5
    assert plan[1]["sceneStartSec"] == 5.5


def test_conform_plan_applies_manual_director_trim(monkeypatch):
    monkeypatch.setattr(cb_post, "_dur", lambda path: 10.0)
    monkeypatch.setattr(cb_post, "_clip_fps", lambda path: 24.0)
    plan = cb_post.conform_plan(
        ["approved.mp4"], protected_windows=[[]],
        edit_decisions=[{"inSec": 1.25, "outSec": 8.5, "manualTrim": True}])
    assert plan[0]["sourceStartSec"] == 1.25
    assert plan[0]["sourceEndSec"] == 8.5
    assert plan[0]["sceneStartSec"] == 0.0
    assert plan[0]["sceneEndSec"] == 7.25


def test_build_scene_post_is_atomic_hashed_and_caption_exact(monkeypatch, tmp_path):
    clip = tmp_path / "approved.mp4"
    clip.write_bytes(b"approved take")
    voice = tmp_path / "approved_voice.wav"
    voice.write_bytes(b"approved voice")

    def write_output(*args, **kwargs):
        out = pathlib.Path(args[1] if len(args) > 1 else kwargs["out"])
        out.write_bytes(b"media-output")
        return str(out)

    monkeypatch.setattr(cb_post, "_norm", lambda clips: clips)
    monkeypatch.setattr(cb_post, "replace_guide_dialogue", lambda video, approved_voice, out:
                        pathlib.Path(out).write_bytes(b"restored dialogue") or str(out))
    monkeypatch.setattr(cb_post, "_dur", lambda path: 6.0)
    monkeypatch.setattr(cb_post, "_clip_fps", lambda path: 24.0)
    monkeypatch.setattr(cb_post, "assemble_conformed", write_output)
    monkeypatch.setattr(cb_post, "mix", lambda picture, music, ambience, out, **kwargs:
                        pathlib.Path(out).write_bytes(b"master") or out)
    monkeypatch.setattr(cb_post, "build_vertical_derivative", lambda src, out:
                        pathlib.Path(out).write_bytes(b"vertical") or out)
    monkeypatch.setattr(cb_post, "extract_program_audio", lambda src, out:
                        pathlib.Path(out).write_bytes(b"audio") or str(out))

    def probe(path):
        common = {"videoCodec": "h264", "pixelFormat": "yuv420p", "fps": 24.0,
                  "colorPrimaries": "bt709", "colorTransfer": "bt709",
                  "colorSpace": "bt709", "audioCodec": "aac",
                  "audioSampleRate": 48000, "audioChannels": 2,
                  "audioChannelLayout": "stereo", "audioSampleFormat": "fltp",
                  "audioBitsPerRawSample": 0}
        if "program_audio" in str(path):
            return {**common, "durationSec": 7.6, "width": 0, "height": 0,
                    "hasVideo": False, "hasAudio": True, "videoCodec": None,
                    "pixelFormat": None, "fps": 0, "colorPrimaries": None,
                    "colorTransfer": None, "colorSpace": None,
                    "audioCodec": "pcm_s24le", "audioSampleFormat": "s32",
                    "audioBitsPerRawSample": 24}
        if "9x16" in str(path):
            return {**common, "durationSec": 7.6, "width": 1080, "height": 1920,
                    "hasVideo": True, "hasAudio": True}
        return {**common, "durationSec": 7.6, "width": 1280, "height": 720,
                "hasVideo": True, "hasAudio": True}

    monkeypatch.setattr(cb_post, "_probe_media", probe)
    monkeypatch.setattr(cb_post, "_measure_loudness", lambda path, target: {
        "integratedLufs": float(target["I"]), "truePeakDbtp": float(target["TP"]),
        "loudnessRangeLu": 3.0, "thresholdLufs": -24.0, "targetOffsetLu": 0.0,
    })
    shots = [{"shotId": "S1.SH1", "approvedTake": str(clip),
              "approvedVoice": str(voice),
              "audioProvenance": {"postLaneStatus": "required"},
              "dialogueLines": [{"dialogueOccurrenceId": "occ:first",
                                  "sourceEventId": "event:first", "speaker": "Fuzzby",
                                  "exactText": "Again.", "startSec": 0.5, "endSec": 1.2}]}]
    root = tmp_path / "post"
    manifest = cb_post.build_scene_post(
        shots, root, "EpT", "9", {"kind": "scene-post", "digest": "abc"},
        candidate_id="candidate1")
    final_dir = root / "EpT_Scene9_candidate1"
    assert final_dir.exists() and not list(root.glob(".tmp_*"))
    assert manifest["qc"]["passed"] is True
    assert manifest["qc"]["humanCreativeApprovalRequired"] is True
    assert manifest["deliveryProfile"]["programAudioSampleRateHz"] == 48000
    assert manifest["captionWindows"][0]["dialogueOccurrenceId"] == "occ:first"
    assert (final_dir / "captions.srt").read_text(encoding="utf-8").count("Again.") == 1
    assert json.loads((final_dir / "post_manifest.json").read_text(encoding="utf-8")) == manifest
    for asset in manifest["outputs"].values():
        assert pathlib.Path(asset["path"]).exists()
        assert asset["sha256"] == cb_post._sha256(asset["path"])


def test_build_scene_post_failure_exposes_no_candidate_directory(monkeypatch, tmp_path):
    clip = tmp_path / "approved.mp4"
    clip.write_bytes(b"approved take")
    monkeypatch.setattr(cb_post, "_norm", lambda clips: clips)
    monkeypatch.setattr(cb_post, "_dur", lambda path: 6.0)
    monkeypatch.setattr(cb_post, "_clip_fps", lambda path: 24.0)
    monkeypatch.setattr(cb_post, "assemble_conformed", lambda *args, **kwargs: None)
    with pytest.raises(RuntimeError, match="assembly failed"):
        cb_post.build_scene_post(
            [{"shotId": "S1.SH1", "approvedTake": str(clip), "dialogueLines": []}],
            tmp_path / "post", "EpT", "9", {"digest": "abc"},
            candidate_id="candidate1")
    assert not (tmp_path / "post" / "EpT_Scene9_candidate1").exists()
    assert not list((tmp_path / "post").glob(".tmp_*"))


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
