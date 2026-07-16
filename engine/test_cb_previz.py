#!/usr/bin/env python3
"""test_cb_previz.py — regression coverage for cb_previz.craft_score_for_scene (2026-07-14).

cb_previz.py had zero test coverage before this file. This covers only the NEW craft-scoring
integration (wiring cb_craft.score_scene_craft into Gate 1.6) — zero API calls, zero ffmpeg calls,
cb_craft.score_scene_craft fully monkeypatched. The pre-existing scratch-VO/placeholder-frame/ffmpeg
assembly logic is exercised in real production use, not re-tested here.

    python3 test_cb_previz.py
"""
import os, sys, json, tempfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cb_previz
import cb_craft
import cb_pipeline

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


FAKE_CRAFT_RESULT = {
    "sceneNumber": 1,
    "criteria": {
        "characterVoice": {"score": 4, "verdict": "distinct", "evidence": ["Fuzzby: ..."], "agreement_gap": 0},
        "comedyCraft": {"score": 3, "verdict": "escalates", "evidence": ["..."], "agreement_gap": 1},
        "emotionalNorthStar": {"score": 4, "verdict": "lands", "evidence": ["..."], "agreement_gap": 0},
        "fidelityTraceability": {"score": 5, "verdict": "traces", "evidence": ["..."], "agreement_gap": 0},
        "overallPixarBenchmark": {"score": 3, "verdict": "competent, not yet Pixar", "evidence": ["..."], "agreement_gap": 2},
    },
    "review": {"oneLineToFixFirst": "Give Zenny's reaction its own beat instead of a group shrug."},
    "skeptic": {"oneLineToFixFirst": "same"},
}


def _make_scratch_package(tmpdir):
    pkg = {
        "scenes": [{"sceneNumber": 1, "name": "Test Scene"}],
        "beats": [
            {"beatCode": "1.B1", "sceneNumber": 1, "slug": "test-beat",
             "storyBeat": "Fuzzby preens.", "want": "to be seen", "need": "to be enough",
             "crystalTruth": "no crystal in this beat", "kidRead": "he's silly", "adultRead": "he's insecure",
             "comedyMode": "BIG", "endState": "he holds the pose",
             "cuts": [{"n": 1, "action": "Fuzzby preens on the branch.", "dialogue": None}]},
        ],
    }
    path = os.path.join(tmpdir, "scratch_beat_package.json")
    with open(path, "w") as f:
        json.dump(pkg, f)
    return path


def test_craft_score_success_writes_sidecar():
    tmpdir = tempfile.mkdtemp(prefix="cb_previz_test_")
    old_cwd = os.getcwd()
    orig_score = cb_craft.score_scene_craft
    orig_load_chars = cb_craft._load_characters
    try:
        os.makedirs(os.path.join(tmpdir, "media"), exist_ok=True)
        os.chdir(tmpdir)
        pkg_path = _make_scratch_package(tmpdir)

        cb_craft._load_characters = lambda: {"Fuzzby": {"bible": {}}}
        cb_craft.score_scene_craft = lambda scene, beats, characters, script_scenes, log=print: dict(FAKE_CRAFT_RESULT)

        # cb_preflight._load_script_scenes hits real file resolution — no script file exists in this
        # scratch dir, so it should degrade to None gracefully (matching its own documented contract),
        # never raise. score_scene_craft itself is monkeypatched above regardless of what it gets passed.
        result = cb_previz.craft_score_for_scene(pkg_path, 1, episode="Ep1_TEST", log=lambda *a, **k: None)

        check("craft_score_for_scene returns the (monkeypatched) result dict on success",
              result is not None and result["sceneNumber"] == 1, result)
        sidecar = os.path.join(tmpdir, "media", "Ep1_TEST_Scene1_previz.craft.json")
        check("craft_score_for_scene writes the sidecar file", os.path.exists(sidecar), sidecar)
        if os.path.exists(sidecar):
            on_disk = json.load(open(sidecar))
            check("the sidecar's content matches what score_scene_craft returned",
                  on_disk["criteria"]["overallPixarBenchmark"]["score"] == 3, on_disk)
    finally:
        cb_craft.score_scene_craft = orig_score
        cb_craft._load_characters = orig_load_chars
        os.chdir(old_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_craft_score_fails_soft_never_raises():
    tmpdir = tempfile.mkdtemp(prefix="cb_previz_test_")
    old_cwd = os.getcwd()
    orig_score = cb_craft.score_scene_craft
    orig_load_chars = cb_craft._load_characters
    try:
        os.makedirs(os.path.join(tmpdir, "media"), exist_ok=True)
        os.chdir(tmpdir)
        pkg_path = _make_scratch_package(tmpdir)

        cb_craft._load_characters = lambda: {"Fuzzby": {"bible": {}}}
        def _boom(*a, **k):
            raise RuntimeError("simulated quota/network failure")
        cb_craft.score_scene_craft = _boom

        result = None
        raised = False
        try:
            result = cb_previz.craft_score_for_scene(pkg_path, 1, episode="Ep1_TEST", log=lambda *a, **k: None)
        except Exception:
            raised = True
        check("craft_score_for_scene NEVER raises even when score_scene_craft blows up",
              raised is False, "an exception propagated out — this would have broken the previz build")
        check("craft_score_for_scene returns None on failure (advisory-only contract)",
              result is None, result)
        sidecar = os.path.join(tmpdir, "media", "Ep1_TEST_Scene1_previz.craft.json")
        check("no sidecar is written on failure (nothing half-written)",
              not os.path.exists(sidecar), sidecar)
    finally:
        cb_craft.score_scene_craft = orig_score
        cb_craft._load_characters = orig_load_chars
        os.chdir(old_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_craft_score_no_beats_degrades_cleanly():
    tmpdir = tempfile.mkdtemp(prefix="cb_previz_test_")
    old_cwd = os.getcwd()
    try:
        os.makedirs(os.path.join(tmpdir, "media"), exist_ok=True)
        os.chdir(tmpdir)
        pkg_path = _make_scratch_package(tmpdir)
        # scene 99 has no beats in the scratch package
        result = cb_previz.craft_score_for_scene(pkg_path, 99, episode="Ep1_TEST", log=lambda *a, **k: None)
        check("a scene with no beats returns None, never crashes", result is None, result)
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_craft_score_resolves_real_scene_object_not_whole_package():
    """THE WRONG-OBJECT BUG (2026-07-14, full-pipeline verification audit): craft_score_for_scene used to bind
    `scene` to the WHOLE parsed package dict (cb_beats._load_scene_beats' first return value), never the real
    per-scene object living in pkg["scenes"] — so score_scene_craft's own scene.get('sceneNumber'/'name'/
    'pillar'/'emotionalCore') calls silently came back empty on every real fire. Proves the real per-scene
    dict (with its own name/pillar/emotionalCore) is what actually reaches score_scene_craft now, by
    capturing the exact `scene` argument passed in."""
    tmpdir = tempfile.mkdtemp(prefix="cb_previz_test_")
    old_cwd = os.getcwd()
    orig_score = cb_craft.score_scene_craft
    orig_load_chars = cb_craft._load_characters
    captured = {}
    try:
        os.makedirs(os.path.join(tmpdir, "media"), exist_ok=True)
        os.chdir(tmpdir)
        pkg_path = os.path.join(tmpdir, "scratch_beat_package.json")
        with open(pkg_path, "w") as f:
            json.dump({
                "scenes": [{"sceneNumber": 1, "name": "The Meadow", "pillar": "Spark",
                            "emotionalCore": "pride outrunning coordination"}],
                "beats": [{"beatCode": "1.B1", "sceneNumber": 1, "storyBeat": "Fuzzby preens.",
                           "cuts": [{"n": 1, "action": "Fuzzby preens.", "dialogue": None}]}],
            }, f)

        cb_craft._load_characters = lambda: {}
        def _capture(scene, beats, characters, script_scenes, log=print):
            captured["scene"] = scene
            return dict(FAKE_CRAFT_RESULT)
        cb_craft.score_scene_craft = _capture

        cb_previz.craft_score_for_scene(pkg_path, 1, episode="Ep1_TEST", log=lambda *a, **k: None)

        check("score_scene_craft received the REAL per-scene dict, not the whole package",
              captured.get("scene", {}).get("sceneNumber") == 1
              and captured.get("scene", {}).get("name") == "The Meadow"
              and captured.get("scene", {}).get("pillar") == "Spark",
              captured.get("scene"))
        check("the whole-package dict was NOT passed as `scene` (it has no top-level 'name'/'pillar')",
              "beats" not in (captured.get("scene") or {}), captured.get("scene"))
    finally:
        cb_craft.score_scene_craft = orig_score
        cb_craft._load_characters = orig_load_chars
        os.chdir(old_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_assemble_scene_previz_never_calls_craft_score_itself():
    """THE DOUBLE-FIRE BUG (2026-07-14, full-pipeline verification audit): assemble_scene_previz used to ALSO
    call craft_score_for_scene internally, right after cb_pipeline.previz_reel ALREADY calls it — every real
    Gate-1.6 fire ran the real-cost, two-LLM-call craft judge TWICE, with the second write silently
    clobbering the first. craft_score_for_scene now fires ONLY at the orchestration level
    (cb_pipeline.previz_reel, see test_previz_reel_fires_craft_score_after_successful_assemble below) — this
    proves assemble_scene_previz's OWN body never calls it, by monkeypatching craft_score_for_scene to a
    tripwire and confirming a real assemble_scene_previz() run never trips it."""
    tmpdir = tempfile.mkdtemp(prefix="cb_previz_test_")
    old_cwd = os.getcwd()
    orig_craft = cb_previz.craft_score_for_scene
    orig_assemble_beat_clip = cb_previz.assemble_beat_clip
    tripped = []
    try:
        os.makedirs(os.path.join(tmpdir, "media"), exist_ok=True)
        os.chdir(tmpdir)
        pkg_path = _make_scratch_package(tmpdir)

        cb_previz.craft_score_for_scene = lambda *a, **k: tripped.append(True)
        # stub the real (ffmpeg-calling) clip builder so this stays a zero-cost, zero-subprocess unit test —
        # only assemble_scene_previz's own internal control flow is under test here, not real clip assembly.
        cb_previz.assemble_beat_clip = lambda b, episode, tmp_dir: None

        result = cb_previz.assemble_scene_previz(pkg_path, 1, episode="Ep1_TEST")

        check("assemble_scene_previz's own body never calls craft_score_for_scene (no clips built -> None either way)",
              tripped == [], tripped)
        check("with every clip build stubbed to fail, assemble_scene_previz correctly returns None",
              result is None, result)
    finally:
        cb_previz.craft_score_for_scene = orig_craft
        cb_previz.assemble_beat_clip = orig_assemble_beat_clip
        os.chdir(old_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_previz_reel_fires_craft_score_after_successful_assemble():
    """THE WIRING (task #315, 2026-07-14): cb_craft.score_scene_craft existed, worked, and was fully proven
    (rule 48) but had ZERO live caller anywhere in the pipeline until cb_pipeline.previz_reel() was wired to
    fire cb_previz.craft_score_for_scene right after a successful assemble_scene_previz() — closing the same
    "built but orphaned" pattern this session found repeatedly elsewhere. Proves the ORDER (assemble, then
    craft-score) and the GATING (a failed/empty assemble must NEVER trigger a craft-score call — no reel
    means nothing to score, and previz_reel() must still return False in that case, unchanged)."""
    orig_assemble, orig_craft = cb_previz.assemble_scene_previz, cb_previz.craft_score_for_scene
    calls = []
    try:
        cb_previz.assemble_scene_previz = lambda pkg, scene, episode="Ep1": (
            calls.append(("assemble", scene, episode)) or f"media/{episode}_Scene{scene}_previz.mp4")
        cb_previz.craft_score_for_scene = lambda pkg, scene, episode="Ep1", log=print: (
            calls.append(("craft", scene, episode)) or {"sceneNumber": scene, "criteria": {}})
        result = cb_pipeline.previz_reel("1")
        check("previz_reel returns True on a successful build", result is True, result)
        check("assemble_scene_previz fired before craft_score_for_scene",
              calls == [("assemble", "1", cb_pipeline.EP), ("craft", "1", cb_pipeline.EP)], calls)
    finally:
        cb_previz.assemble_scene_previz, cb_previz.craft_score_for_scene = orig_assemble, orig_craft

    calls2 = []
    try:
        cb_previz.assemble_scene_previz = lambda pkg, scene, episode="Ep1": None   # "no beats found" case
        cb_previz.craft_score_for_scene = lambda pkg, scene, episode="Ep1", log=print: (
            calls2.append("craft") or None)
        result2 = cb_pipeline.previz_reel("99")
        check("previz_reel still returns False on a failed/empty build (unchanged by this wiring)",
              result2 is False, result2)
        check("craft_score_for_scene is NEVER called when the reel itself failed to build",
              calls2 == [], calls2)
    finally:
        cb_previz.assemble_scene_previz, cb_previz.craft_score_for_scene = orig_assemble, orig_craft


def main():
    test_craft_score_success_writes_sidecar()
    test_craft_score_fails_soft_never_raises()
    test_craft_score_no_beats_degrades_cleanly()
    test_craft_score_resolves_real_scene_object_not_whole_package()
    test_assemble_scene_previz_never_calls_craft_score_itself()
    test_previz_reel_fires_craft_score_after_successful_assemble()

    fails = [r for r in RESULTS if not r[1]]
    for name, ok, detail in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n        -> {detail}" if not ok and detail else ""))
    print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} passed.")
    if fails:
        print(f"{len(fails)} FAILURE(S)")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
