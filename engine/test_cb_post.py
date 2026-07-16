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
import os, sys, json, tempfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cb_post


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


def test_multiclip_uses_conformed_and_saves_raw_comparison():
    """2+ clips: assemble_conformed builds the real `picture`; assemble_picture ALSO runs, saved as
    `_picture_RAW.mp4` — the named raw-vs-conformed comparison copy, per the fix's own docstring."""
    calls = []
    def fake_clips(pkg, episode, scene_num): return ["media/a.mp4", "media/b.mp4"]
    def fake_norm(clips): return clips
    def fake_assemble_picture(clips, out):
        calls.append(("assemble_picture", tuple(clips), out)); open(out, "w").write("x"); return 5.0
    def fake_assemble_conformed(clips, out):
        calls.append(("assemble_conformed", tuple(clips), out)); open(out, "w").write("x"); return 4.2
    def fake_mix(picture, music, amb, out, sfx_layers=None):
        calls.append(("mix", picture)); open(out, "w").write("x"); return out
    def fake_address_windows(pkg, scene_num, episode): return []
    def fake_write_retake_csv(pkg, scene_num, episode): return ("scratch.csv", 0)

    def _run():
        json.dump({"beats": []}, open("pkg.json", "w"))
        import cb_address
        restore_addr = _patch_module(cb_address, {"scene_shot_windows": fake_address_windows,
                                                    "write_retake_csv": fake_write_retake_csv})
        restore = _patch({"_clips": fake_clips, "_norm": fake_norm, "assemble_picture": fake_assemble_picture,
                           "assemble_conformed": fake_assemble_conformed, "mix": fake_mix})
        try:
            cb_post.run("pkg.json", "1", "Ep1")
        finally:
            restore(); restore_addr()
        return calls

    result = _scratch(_run)
    fails = []
    fns_called = [c[0] for c in result]
    ok_conform = "assemble_conformed" in fns_called
    ok_raw = fns_called.count("assemble_picture") == 1   # the raw comparison copy, exactly once
    conform_call = next((c for c in result if c[0] == "assemble_conformed"), None)
    ok_picture_target = conform_call and conform_call[2] == "media/Ep1_Scene1_picture.mp4"
    raw_call = next((c for c in result if c[0] == "assemble_picture"), None)
    ok_raw_target = raw_call and raw_call[2] == "media/Ep1_Scene1_picture_RAW.mp4"
    print(f"  {'PASS' if ok_conform else 'FAIL'}  multi-clip run() calls assemble_conformed at all — got {fns_called}")
    print(f"  {'PASS' if ok_raw else 'FAIL'}  assemble_picture called exactly once (the raw comparison copy) — got {fns_called.count('assemble_picture')}x")
    print(f"  {'PASS' if ok_picture_target else 'FAIL'}  assemble_conformed writes the REAL picture path — got {conform_call}")
    print(f"  {'PASS' if ok_raw_target else 'FAIL'}  assemble_picture writes the _RAW comparison path — got {raw_call}")
    for ok, msg in [(ok_conform, "assemble_conformed not called for a multi-clip scene"),
                     (ok_raw, f"assemble_picture called {fns_called.count('assemble_picture')}x, expected exactly 1"),
                     (ok_picture_target, f"assemble_conformed target wrong: {conform_call}"),
                     (ok_raw_target, f"assemble_picture (raw) target wrong: {raw_call}")]:
        if not ok:
            fails.append(msg)
    return fails


def test_singleclip_falls_back_to_assemble_picture_no_redundant_raw():
    """Exactly 1 clip: no join exists to conform, so run() must use assemble_picture directly for the real
    `picture` AND must NOT also render a redundant, identical _RAW copy (nothing to compare against)."""
    calls = []
    def fake_clips(pkg, episode, scene_num): return ["media/a.mp4"]
    def fake_norm(clips): return clips
    def fake_assemble_picture(clips, out):
        calls.append(("assemble_picture", out)); open(out, "w").write("x"); return 5.0
    def fake_assemble_conformed(clips, out):
        calls.append(("assemble_conformed", out)); open(out, "w").write("x"); return 5.0
    def fake_mix(picture, music, amb, out, sfx_layers=None):
        calls.append(("mix", picture)); open(out, "w").write("x"); return out

    def _run():
        json.dump({"beats": []}, open("pkg.json", "w"))
        import cb_address
        restore_addr = _patch_module(cb_address, {"scene_shot_windows": lambda *a: [],
                                                    "write_retake_csv": lambda *a: ("scratch.csv", 0)})
        restore = _patch({"_clips": fake_clips, "_norm": fake_norm, "assemble_picture": fake_assemble_picture,
                           "assemble_conformed": fake_assemble_conformed, "mix": fake_mix})
        try:
            cb_post.run("pkg.json", "1", "Ep1")
        finally:
            restore(); restore_addr()
        return calls

    result = _scratch(_run)
    fails = []
    fns_called = [c[0] for c in result]
    ok_no_conform = "assemble_conformed" not in fns_called
    ok_one_picture_call = fns_called.count("assemble_picture") == 1
    print(f"  {'PASS' if ok_no_conform else 'FAIL'}  single-clip run() never calls assemble_conformed (no join to conform) — got {fns_called}")
    print(f"  {'PASS' if ok_one_picture_call else 'FAIL'}  assemble_picture called exactly once, no redundant _RAW copy — got {fns_called.count('assemble_picture')}x")
    if not ok_no_conform:
        fails.append(f"single-clip scene wrongly called assemble_conformed: {fns_called}")
    if not ok_one_picture_call:
        fails.append(f"single-clip scene called assemble_picture {fns_called.count('assemble_picture')}x, expected exactly 1 (no redundant raw copy)")
    return fails


def test_conformed_failure_stops_run_before_mix():
    """THE FIX'S OWN FAILURE CONTRACT: assemble_conformed must return None on a real ffmpeg failure (matching
    assemble_picture/mix's own pre-existing contract) — and run() must actually STOP there, never calling
    mix() against a picture that was never written (the exact 'silent success on failure' bug class rule 59
    already fixed for this file's other two assemblers, now proven for this one too)."""
    calls = []
    def fake_clips(pkg, episode, scene_num): return ["media/a.mp4", "media/b.mp4"]
    def fake_norm(clips): return clips
    def fake_assemble_picture(clips, out):
        calls.append("assemble_picture"); open(out, "w").write("x"); return 5.0
    def fake_assemble_conformed_fails(clips, out):
        calls.append("assemble_conformed"); return None   # simulates a real ffmpeg failure
    def fake_mix(picture, music, amb, out, sfx_layers=None):
        calls.append("mix"); return out   # must NEVER be reached

    def _run():
        json.dump({"beats": []}, open("pkg.json", "w"))
        restore = _patch({"_clips": fake_clips, "_norm": fake_norm, "assemble_picture": fake_assemble_picture,
                           "assemble_conformed": fake_assemble_conformed_fails, "mix": fake_mix})
        try:
            cb_post.run("pkg.json", "1", "Ep1")
        finally:
            restore()
        return calls

    result = _scratch(_run)
    fails = []
    ok_no_mix = "mix" not in result
    print(f"  {'PASS' if ok_no_mix else 'FAIL'}  a failed assemble_conformed stops run() before mix() is ever called — got {result}")
    if not ok_no_mix:
        fails.append(f"run() called mix() after assemble_conformed failed — the exact 'silent success on failure' bug: {result}")
    return fails


class _FakeCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode; self.stdout = stdout; self.stderr = stderr


def _fake_ffmpeg_ffprobe_run(cmd, capture_output=True, text=True):
    """A single fake standing in for subprocess.run across BOTH ffprobe (used by _dur) and ffmpeg (used by
    mix/assemble_*) calls — distinguished by cmd[0]. ffmpeg calls 'succeed' by writing their own -y output
    path (always cmd[-1] for every ffmpeg invocation in this module) so os.path.exists(out) checks pass."""
    if cmd and cmd[0] == "ffprobe":
        return _FakeCompleted(stdout="5.0")
    open(cmd[-1], "w").write("x")
    return _FakeCompleted(returncode=0)


def test_mix_uses_correct_loudness_target_per_platform():
    """LOUDNESS_TARGETS (2026-07-14): each named platform must actually reach the ffmpeg loudnorm filter with
    ITS OWN I/TP/LRA values — not a single hardcoded number regardless of what platform was asked for."""
    def _run():
        open("picture.mp4", "w").write("x")
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
    return fails


def test_mix_unrecognized_platform_falls_back_to_default():
    """An unrecognized/typo'd platform name must degrade to DEFAULT_PLATFORM's target, never raise — this is
    a mastering CHOICE, not a hard gate."""
    def _run():
        open("picture.mp4", "w").write("x")
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
    return fails


def test_build_platform_masters_refuses_cleanly_with_no_picture():
    """No picture.mp4 for the scene (Gate 5 hasn't fired yet) -> a clear refusal, empty result, never a crash."""
    def _run():
        return cb_post.build_platform_masters("pkg.json", "1", "Ep1")
    result = _scratch(_run)
    ok = result == {}
    print(f"  {'PASS' if ok else 'FAIL'}  no picture on disk -> refuses cleanly with an empty dict — got {result!r}")
    return [] if ok else [f"build_platform_masters with no picture should return {{}}, got {result!r}"]


def test_build_platform_masters_calls_mix_once_per_platform():
    """With a real picture present, one master file per requested platform, each via mix() with the RIGHT
    platform kwarg and the RIGHT output filename."""
    calls = []
    def fake_mix(picture, music, amb, out, platform=cb_post.DEFAULT_PLATFORM, sfx_layers=None):
        calls.append((platform, out)); open(out, "w").write("x"); return out
    def _run():
        os.makedirs("media", exist_ok=True)
        open("media/Ep1_Scene1_picture.mp4", "w").write("x")
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
    return fails


def test_build_vertical_derivative_refuses_cleanly_with_no_source():
    """No source file on disk -> a clear refusal (None), never a crash."""
    def _run():
        return cb_post.build_vertical_derivative("media/does_not_exist.mp4", "media/out_vertical.mp4")
    result = _scratch(_run)
    ok = result is None
    print(f"  {'PASS' if ok else 'FAIL'}  no source on disk -> refuses cleanly (None) — got {result!r}")
    return [] if ok else [f"build_vertical_derivative with no source should return None, got {result!r}"]


def test_build_vertical_derivative_builds_centre_crop_and_scale():
    """A real source -> the ffmpeg call carries the centre-anchored crop filter (ih*9/16 width, full height,
    centred x-offset) followed by a scale to the target resolution — the actual 'centre-safe 9:16' math."""
    def _run():
        os.makedirs("media", exist_ok=True)
        open("media/complete.mp4", "w").write("x")
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
    return fails


def test_load_sfx_library_gracefully_degrades_on_missing_manifest():
    """No config/sfx_library.json on disk -> an empty dict, never a crash (matching mix()'s own have_mus/
    have_amb file-exists convention, never gag_locks.json's hard-fail-on-missing-key one)."""
    def _run():
        return cb_post._load_sfx_library()
    result = _scratch(_run)
    ok = result == {}
    print(f"  {'PASS' if ok else 'FAIL'}  missing manifest -> empty dict, no crash — got {result!r}")
    return [] if ok else [f"_load_sfx_library() with no manifest should return {{}}, got {result!r}"]


def test_load_sfx_library_loads_real_manifest_excluding_underscore_keys():
    """A real manifest loads its real cue entries and excludes the '_note' documentation key."""
    def _run():
        os.makedirs("config", exist_ok=True)
        json.dump({"_note": "docs, not a cue", "FWIP": {"file": "sfx/fwip.mp3"}},
                   open("config/sfx_library.json", "w"))
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
    return fails


def test_sweeten_cues_for_scene_only_returns_cues_with_assets_on_disk():
    """A beat resolving to a mapped archetype (LEAF_CRASH_REBOUND -> FWIP) with a REAL asset on disk becomes a
    candidate at a real timecode; a second beat mapping to a cue with NO asset on disk is silently omitted —
    never an error, never a phantom candidate pointing at a file that doesn't exist."""
    def _run():
        os.makedirs("config", exist_ok=True)
        os.makedirs("media", exist_ok=True)
        real_asset = os.path.join("config", "fwip.mp3")
        open(real_asset, "w").write("fake mp3 bytes, file-exists check only")
        json.dump({
            "FWIP": {"file": "fwip.mp3"},
            "POP": {"file": "does_not_exist.mp3"},   # no real asset -> must be silently excluded
        }, open("config/sfx_library.json", "w"))
        pkg = {
            "beats": [
                {"beatCode": "1.B1", "sceneNumber": "1", "physical_action_archetype": "LEAF_CRASH_REBOUND"},
                {"beatCode": "1.B2", "sceneNumber": "1", "physical_action_archetype": "POLLEN_SMEAR_TUMBLE"},
            ],
            "scenes": [{"sceneNumber": "1"}],
        }
        json.dump(pkg, open("pkg.json", "w"))
        # _clips reads media/{episode}_{code}_{slug}.mp4 off disk — give both beats a real (fake-content) clip
        # so both are treated as "rendered" (sweeten_cues_for_scene's own definition, matching _clips itself).
        open("media/Ep1_1.B1_a.mp4", "w").write("x")
        open("media/1.B1_slug", "w")  # not read; just proving the dir is otherwise inert
        import cb_address, cb_segprompt
        fake_windows = [
            {"ref": "1.B1#shot1", "beat": 1, "shot": 1, "scene_in": 0.0, "scene_out": 5.0},
            {"ref": "1.B1#shot2", "beat": 1, "shot": 2, "scene_in": 5.0, "scene_out": 10.0},
            {"ref": "1.B2#shot1", "beat": 1, "shot": 1, "scene_in": 10.0, "scene_out": 15.0},
        ]
        restore_addr = _patch_module(cb_address, {"scene_shot_windows": lambda *a, **k: fake_windows})
        restore_clips = _patch({"_clips": lambda pkg, episode, scene_num: [
            f"media/{episode}_1.B1_a.mp4", f"media/{episode}_1.B2_a.mp4"]})
        try:
            return cb_post.sweeten_cues_for_scene("pkg.json", "1", "Ep1")
        finally:
            restore_addr(); restore_clips()

    result = _scratch(_run)
    fails = []
    ok_one_candidate = len(result) == 1
    print(f"  {'PASS' if ok_one_candidate else 'FAIL'}  exactly 1 candidate (the cue WITH a real asset) — got {result}")
    if not ok_one_candidate:
        fails.append(f"expected exactly 1 candidate, got {len(result)}: {result}")
    else:
        c = result[0]
        ok_fwip = c["cue_id"] == "FWIP" and c["beatCode"] == "1.B1"
        ok_timecode = c["at_sec"] == 5.0   # the LAST shot of 1.B1's own two windows, not the first
        print(f"  {'PASS' if ok_fwip else 'FAIL'}  the surviving candidate is 1.B1's FWIP (POP correctly excluded, no asset) — got {c}")
        print(f"  {'PASS' if ok_timecode else 'FAIL'}  placed at the beat's LAST shot start (5.0s, not 0.0s) — got {c['at_sec']}")
        if not ok_fwip:
            fails.append(f"wrong candidate survived: {c}")
        if not ok_timecode:
            fails.append(f"wrong timecode — expected the last-shot heuristic (5.0s), got {c['at_sec']}")
    return fails


def test_mix_sfx_layers_reaches_ffmpeg_filter_with_adelay_and_atrim():
    """A real sfx_layers entry must produce an adelay clause at the RIGHT millisecond offset and an atrim
    clause bounding it to the picture's own duration — the actual overshoot guard, not just 'it ran'."""
    def _run():
        os.makedirs("media", exist_ok=True)
        open("picture.mp4", "w").write("x")
        sfx = "media/fwip.mp3"; open(sfx, "w").write("x")
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
    return fails


def test_mix_sfx_layers_missing_file_silently_skipped():
    """An sfx_layers entry pointing at a file that doesn't exist on disk is silently dropped — mix() still
    succeeds, and the missing file never reaches ffmpeg's own -i input list."""
    def _run():
        os.makedirs("media", exist_ok=True)
        open("picture.mp4", "w").write("x")
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
    return fails


def _patch_module(mod, monkeypatches):
    originals = {name: getattr(mod, name) for name in monkeypatches}
    for name, fn in monkeypatches.items():
        setattr(mod, name, fn)
    def restore():
        for name, fn in originals.items():
            setattr(mod, name, fn)
    return restore


def main():
    fails = []
    print("=== run(): multi-clip scene uses assemble_conformed + saves a raw comparison copy ===")
    fails += test_multiclip_uses_conformed_and_saves_raw_comparison()
    print("\n=== run(): single-clip scene falls back to assemble_picture, no redundant raw copy ===")
    fails += test_singleclip_falls_back_to_assemble_picture_no_redundant_raw()
    print("\n=== run(): a failed assemble_conformed stops before mix() (no phantom deliverable) ===")
    fails += test_conformed_failure_stops_run_before_mix()
    print("\n=== mix(): each platform's own loudness target reaches the real ffmpeg filter ===")
    fails += test_mix_uses_correct_loudness_target_per_platform()
    print("\n=== mix(): an unrecognized platform falls back to DEFAULT_PLATFORM, never raises ===")
    fails += test_mix_unrecognized_platform_falls_back_to_default()
    print("\n=== build_platform_masters(): refuses cleanly with no picture on disk ===")
    fails += test_build_platform_masters_refuses_cleanly_with_no_picture()
    print("\n=== build_platform_masters(): one mix() call per requested platform, correctly named ===")
    fails += test_build_platform_masters_calls_mix_once_per_platform()
    print("\n=== build_vertical_derivative(): refuses cleanly with no source ===")
    fails += test_build_vertical_derivative_refuses_cleanly_with_no_source()
    print("\n=== build_vertical_derivative(): builds the centre-anchored 9:16 crop + scale ===")
    fails += test_build_vertical_derivative_builds_centre_crop_and_scale()
    print("\n=== _load_sfx_library(): gracefully degrades with no manifest on disk ===")
    fails += test_load_sfx_library_gracefully_degrades_on_missing_manifest()
    print("\n=== _load_sfx_library(): loads a real manifest, excludes the '_note' key ===")
    fails += test_load_sfx_library_loads_real_manifest_excluding_underscore_keys()
    print("\n=== sweeten_cues_for_scene(): only cues with a real asset on disk survive ===")
    fails += test_sweeten_cues_for_scene_only_returns_cues_with_assets_on_disk()
    print("\n=== mix(): a real sfx_layers entry reaches ffmpeg with adelay + atrim ===")
    fails += test_mix_sfx_layers_reaches_ffmpeg_filter_with_adelay_and_atrim()
    print("\n=== mix(): a missing sfx file is silently skipped, never breaks the mix ===")
    fails += test_mix_sfx_layers_missing_file_silently_skipped()
    print()
    if fails:
        print("FAILED:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
