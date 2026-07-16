#!/usr/bin/env python3
"""Regression test: cb_retake.read_retakes' "file EXISTS, not merely non-empty" fix (2026-07-08 audit finding).

    python3 engine/test_cb_retake.py

The bug: read_retakes used to treat an empty in-app run-list the same as "no JSON at all" (a truthiness `or`
fallback), silently falling through to whatever stale rows were still sitting in the Excel CSV from a previous
session. The fix checks os.path.exists(json_path) — an explicit, deliberately-empty [] must be respected as
"nothing selected this fire," never silently overridden by a stale leftover CSV.

ISOLATED: runs entirely inside a scratch tmp dir (chdir'd there, media/ created fresh) so it never touches the
real engine/media/ or any real beat package. Both test refs are canonical Refs ("1.B4#shot7"-style) — parse_ref's
own regex matches them directly in _resolve_locator without ever touching `pkg`, so a nonexistent/dummy pkg path
is safe to pass; no real beat-package data is needed for this test's subject (read_retakes' file-selection logic,
not shot resolution).

Exit 0 = both cases pass.
"""
import os, sys, csv, json, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cb_retake

EP, SCENE = "Ep1", 1
DUMMY_PKG = "no-such-package.json"   # never read for a canonical Ref — see module docstring


def _write_csv(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Ref", "Issue / What's Wrong", "Change To (How You Want It)"])
        w.writerow(["1.B4#shot7", "moustache doesn't wipe off", "wipe the moustache clean by shot's end"])


def _scratch(fn):
    """Run `fn()` inside a fresh scratch tmp dir (chdir'd there, media/ created), always restoring cwd/cleanup."""
    tmp = tempfile.mkdtemp(prefix="cb_retake_test_")
    cwd = os.getcwd()
    os.makedirs(os.path.join(tmp, "media"), exist_ok=True)
    os.chdir(tmp)
    try:
        return fn()
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp, ignore_errors=True)


def test_empty_json_beats_stale_csv():
    """A deliberately-empty in-app run-list ([]) must be respected — the stale, populated CSV must NOT be consulted."""
    def _run():
        json.dump([], open(f"media/{EP}_Scene{SCENE}_retakes.json", "w"))
        _write_csv(f"media/{EP}_Scene{SCENE}_RETAKES.csv")
        return cb_retake.read_retakes(DUMMY_PKG, EP, SCENE)
    result = _scratch(_run)
    ok = result == []
    print(f"  {'PASS' if ok else 'FAIL'}  empty JSON run-list respected (stale CSV ignored) — got {result!r}")
    return [] if ok else [f"read_retakes: expected [] with an empty in-app JSON present, got {result!r}"]


def test_no_json_falls_back_to_csv():
    """With no JSON file at all, read_retakes must fall back to the CSV-derived rows."""
    def _run():
        _write_csv(f"media/{EP}_Scene{SCENE}_RETAKES.csv")
        return cb_retake.read_retakes(DUMMY_PKG, EP, SCENE)
    result = _scratch(_run)
    fails = []
    ok_len = len(result) == 1
    fails += [] if ok_len else [f"read_retakes: expected 1 CSV-derived row, got {len(result)}: {result!r}"]
    print(f"  {'PASS' if ok_len else 'FAIL'}  CSV fallback produced exactly 1 row — got {result!r}")
    if result:
        row = result[0]
        checks = {
            "ref": row.get("ref") == "1.B4#shot7",
            "change": row.get("change") == "wipe the moustache clean by shot's end",
            "issue": row.get("issue") == "moustache doesn't wipe off",
        }
        for k, ok in checks.items():
            print(f"  {'PASS' if ok else 'FAIL'}  CSV row {k!r} correct — got {row.get(k)!r}")
            if not ok:
                fails.append(f"read_retakes: CSV-derived row {k!r} wrong: {row!r}")
    return fails


def test_process_retakes_survives_one_bad_regen_shot():
    """THE FIX (2026-07-14, Julian's front-to-back wiring pass): process_retakes' per-retake loop used to
    call regen_shot() with no guard — a single bad/stale package path (regen_shot -> cb_address.beat_address_map
    -> a bare json.load) crashed the WHOLE batch, losing results for every retake, including ones already
    processed successfully before the crash. Proves: a retake whose regen_shot call raises is isolated (turned
    into an {ok:False, error} entry) and the REST of the batch still runs and is recorded."""
    def _run():
        json.dump([
            {"ref": "1.B1#shot1", "issue": "bad take", "change": "this one will explode"},
            {"ref": "1.B2#shot1", "issue": "bad take", "change": "this one is fine"},
        ], open(f"media/{EP}_Scene{SCENE}_retakes.json", "w"))

        orig_regen = cb_retake.regen_shot
        def fake_regen_shot(pkg, ref, change, episode="Ep1", **kw):
            if ref == "1.B1#shot1":
                raise RuntimeError("simulated bad/stale package path (the real 2026-07-14 bug)")
            return {"ok": True, "ref": ref, "new_beat": "fake"}
        cb_retake.regen_shot = fake_regen_shot
        try:
            # process_retakes' own re-conform step (cb_post._clips/assemble_picture) will fail against this
            # scratch package too — that's fine, it's already wrapped in its own try/except (prints "re-conform
            # skipped") and isn't what this test is proving.
            return cb_retake.process_retakes(DUMMY_PKG, SCENE, EP)
        finally:
            cb_retake.regen_shot = orig_regen
    fails = []
    try:
        result = _scratch(_run)
    except Exception as e:
        print(f"  FAIL  process_retakes raised instead of isolating the bad retake -> {e!r}")
        return [f"process_retakes crashed on a single bad regen_shot call: {e!r}"]
    ok_ran = result.get("ok") is True and result.get("retakes") == 2
    print(f"  {'PASS' if ok_ran else 'FAIL'}  process_retakes completed normally (ok=True, retakes=2) — got {result!r}")
    if not ok_ran:
        fails.append(f"process_retakes: expected ok=True/retakes=2, got {result!r}")
    results = result.get("results") or []
    ok_len = len(results) == 2
    print(f"  {'PASS' if ok_len else 'FAIL'}  both retakes are present in results (the crashed one was NOT lost) — got {len(results)} entries")
    if not ok_len:
        fails.append(f"process_retakes: expected 2 result entries, got {len(results)}: {results!r}")
    else:
        r1 = next((r for r in results if r.get("ref") == "1.B1#shot1"), None)
        r2 = next((r for r in results if r.get("ref") == "1.B2#shot1"), None)
        ok_r1 = bool(r1) and r1.get("ok") is False and "error" in r1
        ok_r2 = bool(r2) and r2.get("ok") is True
        print(f"  {'PASS' if ok_r1 else 'FAIL'}  the exploding retake is recorded as ok=False with an error, not lost — got {r1!r}")
        print(f"  {'PASS' if ok_r2 else 'FAIL'}  the OTHER retake still succeeded despite its sibling's crash — got {r2!r}")
        if not ok_r1:
            fails.append(f"process_retakes: exploding retake not correctly recorded: {r1!r}")
        if not ok_r2:
            fails.append(f"process_retakes: sibling retake did not survive the batch: {r2!r}")
    return fails


def test_regen_shot_refuses_on_lint_failure():
    """THE FIX (2026-07-14, CLAUDE.md rule 84/85 — a full gate-by-gate trace + adversarial verify found
    regen_shot calls cb_gen.generate_video_seedance_ref DIRECTLY, entirely bypassing render_readiness()
    and check_gate3_lint(), so a retake shipped with zero word-budget/Character Vocabulary Law/anti-slop
    enforcement). Proves the WIRING specifically (cb_qa.check_retake_prompt's own logic is unit-tested in
    test_cb_qa.py): with the check forced to fail, regen_shot must refuse cleanly, ok=False, and — most
    importantly — must NEVER reach the real (here: spied) generate_video_seedance_ref call, so no cost is
    spent on a prompt that was already known to be bad."""
    def _run():
        import cb_address, cb_gen, cb_qa

        code, shotnum = "1.B1", 1
        m = {"shots": [{"index": 1, "frame_start": 0, "frame_end": 90}], "fps": 30, "slug": "test_slug", "scene": "1"}
        beat_clip = f"media/{EP}_{code}_test_slug.mp4"
        open(beat_clip, "w").close()  # os.path.exists just needs the file to be present

        orig_map = cb_address.beat_address_map
        orig_windows = cb_address.scene_shot_windows
        orig_load_beat = cb_retake._load_beat
        orig_load_scene = cb_retake._load_scene
        orig_extract = cb_retake._extract_frame
        orig_char_refs = cb_retake._char_refs
        orig_brief = cb_retake.director_retake_brief
        orig_lint = cb_qa.check_retake_prompt
        orig_gen = cb_gen.generate_video_seedance_ref

        gen_calls = []

        def fake_gen(*a, **kw):
            gen_calls.append((a, kw))
            raise AssertionError("generate_video_seedance_ref must never be reached when the lint fails")

        try:
            cb_address.beat_address_map = lambda pkg, c, ep: m
            cb_address.scene_shot_windows = lambda pkg, sc, ep: []
            cb_retake._load_beat = lambda pkg, c: {"openingCast": ["Fuzzby"], "cuts": [{"framing": "", "action": "", "dialogue": ""}]}
            cb_retake._load_scene = lambda pkg, sc: {}
            cb_retake._extract_frame = lambda clip, frame, out: True
            cb_retake._char_refs = lambda beat: ([{"name": "Fuzzby", "slot": "@Image2"}], ["fake_ref.png"])
            cb_retake.director_retake_brief = lambda *a, **kw: None
            cb_qa.check_retake_prompt = lambda prompt, characters=None: {
                "ok": False, "blockers": ["forced test failure — anti-slop word 'cinematic'"], "flags": []}
            cb_gen.generate_video_seedance_ref = fake_gen

            result = cb_retake.regen_shot(DUMMY_PKG, "1.B1#shot1", "make it more cinematic", episode=EP)
        finally:
            cb_address.beat_address_map = orig_map
            cb_address.scene_shot_windows = orig_windows
            cb_retake._load_beat = orig_load_beat
            cb_retake._load_scene = orig_load_scene
            cb_retake._extract_frame = orig_extract
            cb_retake._char_refs = orig_char_refs
            cb_retake.director_retake_brief = orig_brief
            cb_qa.check_retake_prompt = orig_lint
            cb_gen.generate_video_seedance_ref = orig_gen
        return result, gen_calls

    fails = []
    result, gen_calls = _scratch(_run)
    ok_refused = result.get("ok") is False and "lint failed" in (result.get("error") or "")
    print(f"  {'PASS' if ok_refused else 'FAIL'}  regen_shot refuses cleanly on a lint failure (ok=False, named reason) — got {result!r}")
    if not ok_refused:
        fails.append(f"regen_shot: expected ok=False with 'lint failed' in the error, got {result!r}")
    ok_no_spend = gen_calls == []
    print(f"  {'PASS' if ok_no_spend else 'FAIL'}  the render call was NEVER reached — no cost spent on a known-bad prompt")
    if not ok_no_spend:
        fails.append(f"regen_shot: generate_video_seedance_ref was called despite the lint failure: {gen_calls!r}")
    return fails


def main():
    fails = []
    print("=== read_retakes: empty in-app JSON vs. stale CSV ===")
    fails += test_empty_json_beats_stale_csv()
    print("\n=== read_retakes: no JSON at all -> CSV fallback ===")
    fails += test_no_json_falls_back_to_csv()
    print("\n=== process_retakes: one bad regen_shot() does not crash the whole batch ===")
    fails += test_process_retakes_survives_one_bad_regen_shot()
    print("\n=== regen_shot: refuses cleanly on a Gate-4 lint failure, never spends the render call ===")
    fails += test_regen_shot_refuses_on_lint_failure()
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
