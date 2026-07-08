#!/usr/bin/env python3
"""test_gate_cascade.py — the cascade assertion (BUG fix, 2026-07-02, Julian).

A Gate-1 deliverable change must automatically relock every downstream sign-off — the studio was caught showing a
scene's Gate 2 as "signed off" after a Scene-1 restructure (4 beats -> 5) that happened entirely outside any gate
UI action. Fixed with a lazy content-hash check (cb_pipeline._scene_beats_fingerprint / _relock_if_stale, mirrored
in cb-studio/serve.py's locked_state() since it is a separate process with no engine import). This script proves
BOTH copies actually cascade-clear on a Gate-1 change, using SCRATCH files only — it never touches the real
locked.json or any real beat package, so it is safe to run any time, including in CI.

    python3 test_gate_cascade.py     # exit 0 = both implementations pass; exit 1 = a regression was caught
"""
import os, sys, json, ast, tempfile, shutil, hashlib, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
SERVE_PY = os.path.join(os.path.dirname(HERE), "cb-studio", "serve.py")


def _scratch_scenes(scene_num=9):
    """THE MANIFEST (CLAUDE.md rule 37, 2026-07-06; sceneLook added rule 53, 2026-07-08): a manifest-compliant
    scratch scene entry — cb_pipeline.approve now gates on manifest_ok, so every scratch package this test
    fires approve() against needs one of these. pillar='heart' is a scratch shortcut, not a real story call —
    it trivially exempts this scene from the "laugh beat per non-Heart pillar" check, which has nothing to do
    with what THIS test actually verifies (cascade-relock mechanics), so there's no reason to also give the
    scratch beats a comedyMode."""
    return [{"sceneNumber": scene_num, "ambientBed": "scratch test ambient bed — not real content",
             "parentLine": "scratch test parent-layer line — not real content",
             "sceneLook": "scratch test scene-look line — not real content", "pillar": "heart"}]


def _scratch_package(path, beats, scenes=None):
    json.dump({"beats": beats, "scenes": scenes if scenes is not None else _scratch_scenes()}, open(path, "w"))


def _sync_scratch_scene_cache(episode, scene_num, scene_dict):
    """FIXED 2026-07-06 (found live during THE DEFINITIVE BUILD's own dry-walk sweep): cb_preflight's scene-
    cache-sync check used to shell out to a wrongly-pathed script and silently never fire (rule 39's sibling
    fix in cb_preflight.py) — this test's approve() calls passed for months without ever actually exercising
    a real scene-cache check. Now that the check is wired correctly (cb_prompts.scene_cache_stale), a scratch
    episode/scene with no config/locations.json entry at all correctly BLOCKs — exactly as it should for a
    real, never-synced scene. This helper keeps the scratch scene in sync the same way tools/sync_scenes.py
    keeps a real one in sync, so this test still isolates CASCADE-RELOCK mechanics (its actual subject),
    never re-testing scene-cache sync (a different, already-covered concern)."""
    import cb_prompts
    cb_prompts.LOCATIONS.setdefault(episode, {})[str(scene_num)] = {
        "_sourceHash": cb_prompts._scene_source_hash(scene_dict)
    }


def _manifest_compliant_beat(code, scene_num, story_beat, is_opener=True):
    """THE MANIFEST (rule 37): fills every field cb_preflight's TECHNICAL/CREATIVE contracts require, so a
    scratch beat used ONLY to exercise the cascade-relock logic doesn't ALSO fail the (unrelated) content gate
    cb_pipeline.approve now enforces. Values are deliberately synthetic/scratch, never real creative content —
    this test's own assertions are about relock behaviour, not about these values meaning anything."""
    b = {
        "beatCode": code, "sceneNumber": scene_num, "storyBeat": story_beat,
        "endState": "scratch endState — not real content", "endStateStill": "scratch endStateStill",
        "carryMarks": "scratch carry marks", "pauseHold": "one hold only: under 1 second",
        "actingContrast": "scratch acting contrast", "humourLayer": 1, "kidRead": "scratch kid read",
        "adultRead": "scratch adult read", "want": "scratch want", "need": "scratch need",
        "emotionMechanic": "scratch emotion-as-mechanic statement",
        # THE FIDELITY-ALLOCATION LAW (rule 46/49, 2026-07-07) — required by check_beat_creative; added
        # 2026-07-08 (rule 53's contradiction sweep) after this fixture was found still missing it,
        # independently crashing the same approve() calls sceneLook's own gap did.
        "fidelityAllocation": {"primary": "Scratch", "secondary": "none", "economized": "none"},
    }
    if not is_opener:
        b["junctionType"] = "intentional_next_shot"
        b["opensOn"] = {"who": "Scratch", "action": "doing a scratch thing"}
    return b


def _base_beats():
    return [
        _manifest_compliant_beat("9.B1", 9, "original content", is_opener=True),
        _manifest_compliant_beat("9.B2", 9, "original content 2", is_opener=False),
    ]


def test_cb_pipeline(tmp):
    """Exercise the REAL cb_pipeline.py functions (imported directly — this is production code, not a copy)."""
    fails = []
    spec = importlib.util.spec_from_file_location("cb_pipeline_test", os.path.join(HERE, "cb_pipeline.py"))
    P = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(P)

    pkg = os.path.join(tmp, "Ep9_Test_beat_package.json")
    _scratch_package(pkg, _base_beats())
    P.PKG, P.LOCK, P.EP = pkg, os.path.join(tmp, "locked.json"), "Ep9"
    _sync_scratch_scene_cache("Ep9", 9, _scratch_scenes()[0])

    P.approve("1", "9"); P.approve("2a", "9"); P.approve("2b", "9"); P.approve("3", "9")
    d = P._lock()
    d["Ep9"]["9"]["beats"] = {"9.B1": {"audio": True, "keyframe": True, "clip": True}}
    P._save(d)

    if not P._approved("9", "3"):
        fails.append("cb_pipeline: gate 3 should read approved before any beat-package change")

    # the Gate-1 deliverable changes — a beat is added, exactly like the Scene-1 restructure
    beats = _base_beats(); beats.append(_manifest_compliant_beat("9.B3", 9, "added by a restructure", is_opener=False))
    _scratch_package(pkg, beats)

    if P._approved("9", "3"):
        fails.append("cb_pipeline: gate 3 should auto-relock (read False) after the Gate-1 deliverable changed")
    sd = P._lock().get("Ep9", {}).get("9", {})
    for g in ("1", "2a", "2b", "3"):
        if sd.get(g):
            fails.append(f"cb_pipeline: gate {g!r} should have been cascade-cleared, still {sd.get(g)!r}")
    if sd.get("beats"):
        fails.append(f"cb_pipeline: per-beat locks should have been cleared, still {sd.get('beats')!r}")
    if sd.get("1_fp"):
        fails.append("cb_pipeline: the stale fingerprint baseline should have been dropped too")

    # re-approving stamps a FRESH baseline that matches the NEW content, and gate 3 reads clean again once re-approved
    P.approve("1", "9"); P.approve("2a", "9"); P.approve("2b", "9"); P.approve("3", "9")
    if not P._approved("9", "3"):
        fails.append("cb_pipeline: re-approving after the change should read approved again")
    return fails


def test_frame_chain_cascade(tmp):
    """FRAME CHAIN doctrine (2026-07-02, Julian; frame source updated 2026-07-03 — THE HARVEST, "ending frames
    are harvested, never composed"): a retake upstream (a new HARVESTED SETTLE FRAME) must mark every downstream
    beat's keyframe/clip dirty. Exercises the real cb_pipeline functions with a scratch package + scratch media/
    settle-frame files (arbitrary bytes — _beat_end_frame_hash only hashes bytes, it never decodes the PNG)."""
    fails = []
    spec = importlib.util.spec_from_file_location("cb_pipeline_test2", os.path.join(HERE, "cb_pipeline.py"))
    P = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(P)

    pkg = os.path.join(tmp, "Ep9_Chain_beat_package.json")
    beats = [
        _manifest_compliant_beat("9.B1", 9, "anchor", is_opener=True),
        _manifest_compliant_beat("9.B2", 9, "continuation one", is_opener=False),
        _manifest_compliant_beat("9.B3", 9, "continuation two", is_opener=False),
    ]
    for b, slug in zip(beats, ("b1", "b2", "b3")):
        b["slug"] = slug
    _scratch_package(pkg, beats)
    P.PKG, P.LOCK, P.EP = pkg, os.path.join(tmp, "locked_chain.json"), "Ep9"
    _sync_scratch_scene_cache("Ep9", 9, _scratch_scenes()[0])

    cwd = os.getcwd()
    media = os.path.join(tmp, "media"); os.makedirs(media, exist_ok=True)
    os.chdir(tmp)
    try:
        # 9.B1's harvested settle frame (what 9.B2 chained off) + 9.B2's (what 9.B3 chained off)
        open("media/Ep9_9.B1_b1_settle.png", "wb").write(b"settle-frame-v1")
        open("media/Ep9_9.B2_b2_settle.png", "wb").write(b"settle-frame-v1")

        P.approve("1", "9"); P.approve("2a", "9")
        for code in ("9.B1", "9.B2", "9.B3"):
            P._set_beat_lock("9", code, "keyframe", True)
            P._set_beat_lock("9", code, "clip", True)
        P.record_chain_source("9", "9.B2")   # stamps against 9.B1's CURRENT settle-frame hash
        P.record_chain_source("9", "9.B3")   # stamps against 9.B2's CURRENT settle-frame hash

        if P._relock_chain_if_dirty("9"):
            fails.append("frame chain: should NOT be dirty yet — nothing has changed")
        lk = P._lock().get("Ep9", {}).get("9", {}).get("beats", {})
        for code in ("9.B2", "9.B3"):
            if not lk.get(code, {}).get("keyframe"):
                fails.append(f"frame chain: {code} keyframe should still read locked before any retake")

        # a retake on 9.B1 harvests a NEW settle frame — everything chained through it is now stale
        open("media/Ep9_9.B1_b1_settle.png", "wb").write(b"settle-frame-v2-AFTER-A-RETAKE")

        if not P._relock_chain_if_dirty("9"):
            fails.append("frame chain: should detect 9.B1's changed ending frame and cascade-clear downstream")
        lk = P._lock().get("Ep9", {}).get("9", {}).get("beats", {})
        for code in ("9.B2", "9.B3"):
            bl = lk.get(code, {})
            if bl.get("keyframe") or bl.get("clip"):
                fails.append(f"frame chain: {code} keyframe/clip should have been cleared (built from the stale chain), still {bl!r}")
        if not lk.get("9.B1", {}).get("keyframe"):
            fails.append("frame chain: 9.B1 itself is upstream of the change, not downstream — its own lock must NOT be touched")
    finally:
        os.chdir(cwd)
    return fails


def _extract_functions(src_path, names):
    """Pull just the named top-level function defs out of a source file via ast (not a full import) — serve.py
    binds a live socket at module level with no __main__ guard, so it can't be imported directly in a test."""
    src = open(src_path, encoding="utf-8").read()
    tree = ast.parse(src, filename=src_path)
    wanted = {n: None for n in names}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            wanted[node.name] = ast.get_source_segment(src, node)
    missing = [n for n, v in wanted.items() if v is None]
    if missing:
        raise RuntimeError(f"{src_path}: could not find function(s) {missing} — has the cascade fix been moved/renamed?")
    return wanted


def test_serve_py(tmp):
    """Exercise serve.py's MIRRORED copy — extracted via ast (not imported: serve.py binds a live socket at module
    level). If this ever fails while test_cb_pipeline passes, the two duplicated implementations have drifted."""
    fails = []
    if not os.path.exists(SERVE_PY):
        return [f"serve.py not found at {SERVE_PY} — skipped"]
    fns = _extract_functions(SERVE_PY, ["_scene_beats_fingerprint", "_relock_stale_scenes", "locked_state"])
    ns = {"json": json, "pathlib": __import__("pathlib"), "hashlib": hashlib}
    for name in ("_scene_beats_fingerprint", "_relock_stale_scenes", "locked_state"):
        exec(compile(fns[name], SERVE_PY, "exec"), ns)
    ns["OUT"] = ns["pathlib"].Path(tmp)
    ns["CBGEN"] = ns["pathlib"].Path(tmp)

    pkg = os.path.join(tmp, "Ep9_Test_beat_package.json")
    _scratch_package(pkg, _base_beats())
    cur = ns["_scene_beats_fingerprint"]("Ep9", "9")
    json.dump({"Ep9": {"9": {"1": True, "1_fp": cur}}}, open(os.path.join(tmp, "locked.json"), "w"))

    d = ns["locked_state"]()
    if not d.get("Ep9", {}).get("9", {}).get("1"):
        fails.append("serve.py: gate 1 should still read approved before any beat-package change")

    beats = _base_beats(); beats.append({"beatCode": "9.B3", "sceneNumber": 9, "storyBeat": "added by a restructure"})
    _scratch_package(pkg, beats)

    d2 = ns["locked_state"]()
    sd = d2.get("Ep9", {}).get("9", {})
    if sd.get("1") or sd.get("1_fp"):
        fails.append(f"serve.py: gate 1 + its fingerprint should have been cascade-cleared, still {sd!r}")
    return fails


def main():
    tmp = tempfile.mkdtemp(prefix="cb_gate_cascade_test_")
    try:
        fails = test_cb_pipeline(tmp) + test_serve_py(tmp) + test_frame_chain_cascade(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if fails:
        print("CASCADE ASSERTION FAILED:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("CASCADE ASSERTION PASSED — a Gate-1 deliverable change correctly cascade-relocks every downstream "
          "sign-off (cb_pipeline.py + its serve.py mirror), and an upstream ending-frame retake correctly marks "
          "every downstream beat's keyframe/clip dirty (the FRAME CHAIN doctrine).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
