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


def _scratch_package(path, beats):
    json.dump({"beats": beats}, open(path, "w"))


def _base_beats():
    return [
        {"beatCode": "9.B1", "sceneNumber": 9, "storyBeat": "original content"},
        {"beatCode": "9.B2", "sceneNumber": 9, "storyBeat": "original content 2"},
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

    P.approve("1", "9"); P.approve("2a", "9"); P.approve("2b", "9"); P.approve("3", "9")
    d = P._lock()
    d["Ep9"]["9"]["beats"] = {"9.B1": {"audio": True, "keyframe": True, "clip": True}}
    P._save(d)

    if not P._approved("9", "3"):
        fails.append("cb_pipeline: gate 3 should read approved before any beat-package change")

    # the Gate-1 deliverable changes — a beat is added, exactly like the Scene-1 restructure
    beats = _base_beats(); beats.append({"beatCode": "9.B3", "sceneNumber": 9, "storyBeat": "added by a restructure"})
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
        fails = test_cb_pipeline(tmp) + test_serve_py(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if fails:
        print("CASCADE ASSERTION FAILED:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("CASCADE ASSERTION PASSED — a Gate-1 deliverable change correctly cascade-relocks every downstream "
          "sign-off, in both cb_pipeline.py and its serve.py mirror.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
