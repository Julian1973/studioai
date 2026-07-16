#!/usr/bin/env python3
"""test_cb_scene.py — real, standalone regression tests for cb_scene.py.

This module had ZERO test coverage before this file. Matches the existing convention (test_gate_cascade.py,
test_cb_beats.py, test_cb_preflight.py): plain Python, assert-driven, no pytest/unittest, a main() that runs
every check and prints PASS/FAIL, sys.exit(1) on any failure. Uses purely SCRATCH/synthetic fixtures and
monkeypatched dependencies — never the real production package or a real API call.

Covers the fix made 2026-07-09 (Julian, watching Gate 2b spend five real Seedream calls on Scene 1 — "why
would we create b2 keyframe, surely is that not the last frame of g3 s1b1"): cb_scene._run_beats used to fall
back to chain_source_for's keyframe-chained fallback for ANY continuation beat whose predecessor's own
keyframe existed on disk, spending a real generation call on an image Gate 3 never actually reads
(cb_beats.run/relay_source_for are Gate 3's only source for a continuation beat's opening reference). Fixed
to skip a "chained" status beat entirely, matching PRODUCTION_DOCTRINE.md's own Stage 4 ("a relay beat never
gets its own [keyframe]") and the Studio's own keyframesFor display, which already assumed this.

    python3 test_cb_scene.py
"""
import os, sys, json, tempfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cb_scene


PASS = []
FAIL = []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name); print(f"  PASS  {name}")
    else:
        FAIL.append(name); print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# _run_beats only ever generates for the scene opener and a vision beat; a "chained" or "pending" continuation
# beat is skipped — no cb_gen.generate_image call, no matter what keyframe_for/chain_source_for resolves.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_run_beats_skips_chained_and_pending_continuation():
    """FIXED 2026-07-14 (found while adversarially verifying the SFX-sweetening build in cb_post.py): this
    function and its sibling below os.chdir(tmp) but never restore the original cwd before their own outer
    finally deletes tmp via shutil.rmtree — leaving the PROCESS itself sitting in a directory that no longer
    exists on disk. Harmless in isolation (this file's own remaining code never touches a relative path
    again), but it corrupts every OTHER test file's own os.getcwd()-based scratch-dir isolation (e.g.
    test_cb_post.py's _scratch()) for the rest of the same pytest session — confirmed live: `pytest
    test_cb_scene.py test_cb_post.py` failed 14/16 of test_cb_post.py's own cases with a raw
    FileNotFoundError at their very first os.getcwd() call, purely from running AFTER this file."""
    tmp = tempfile.mkdtemp()
    cwd = os.getcwd()
    try:
        beats = [
            {"beatCode": "1.B1", "sceneNumber": "1", "slug": "one"},
            {"beatCode": "1.B2", "sceneNumber": "1", "slug": "two"},
            {"beatCode": "1.B3", "sceneNumber": "1", "slug": "three"},
        ]
        d = {"beats": beats}

        # Fabricate keyframe_for's return per beat code — the exact three statuses _run_beats branches on.
        fake_info = {
            "1.B1": (None, "first", {"kind": "opening keyframe", "chain": {"status": "first", "prev": None}}),
            "1.B2": (None, "chained", {"kind": "opening keyframe", "chain": {"status": "chained", "prev": "1.B1"}}),
            "1.B3": (None, "pending", {"kind": "opening keyframe", "chain": {"status": "pending", "prev": "1.B2"}}),
        }

        def fake_keyframe_for(all_beats, code, episode="Ep1", note=""):
            _, _, info = fake_info[code]
            return f"prompt for {code}", ["ref1"], info

        calls = []

        def fake_generate_image(prompt, refs, aspect, out):
            calls.append(out)

        orig_kf, orig_gen = cb_scene.keyframe_for, cb_scene.cb_gen.generate_image
        orig_scene_cfg = cb_scene.P.scene_cfg
        try:
            cb_scene.keyframe_for = fake_keyframe_for
            cb_scene.cb_gen.generate_image = fake_generate_image
            cb_scene.P.scene_cfg = lambda episode, scene: {"name": "Test Scene", "master": None}
            os.chdir(tmp)
            os.makedirs("media", exist_ok=True)
            cb_scene._run_beats(d, "1", "Ep1")
        finally:
            cb_scene.keyframe_for = orig_kf
            cb_scene.cb_gen.generate_image = orig_gen
            cb_scene.P.scene_cfg = orig_scene_cfg

        check("the opener (1.B1, status=first) IS generated", "Ep1_1.B1_one.png" in calls, f"calls={calls}")
        check("a chained continuation (1.B2) is NEVER generated — no Gate-2b keyframe for a relay beat",
              "Ep1_1.B2_two.png" not in calls, f"calls={calls}")
        check("a pending continuation (1.B3) is NEVER generated (pre-existing behaviour, unchanged)",
              "Ep1_1.B3_three.png" not in calls, f"calls={calls}")
        check("exactly one keyframe generated total (only the opener)", calls == ["Ep1_1.B1_one.png"], f"calls={calls}")
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# A vision beat (its own POV, never chains) still gets its own keyframe — the fix must not touch this path.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_run_beats_still_generates_vision_beats():
    tmp = tempfile.mkdtemp()
    cwd = os.getcwd()
    try:
        beats = [
            {"beatCode": "2.B1", "sceneNumber": "2", "slug": "vision_one"},
        ]
        d = {"beats": beats}

        def fake_keyframe_for(all_beats, code, episode="Ep1", note=""):
            return "vision prompt", ["ref1"], {"kind": "vision keyframe", "chain": {"status": "vision", "prev": None}}

        calls = []

        def fake_generate_image(prompt, refs, aspect, out):
            calls.append(out)

        orig_kf, orig_gen = cb_scene.keyframe_for, cb_scene.cb_gen.generate_image
        orig_scene_cfg = cb_scene.P.scene_cfg
        try:
            cb_scene.keyframe_for = fake_keyframe_for
            cb_scene.cb_gen.generate_image = fake_generate_image
            cb_scene.P.scene_cfg = lambda episode, scene: {"name": "Test Scene", "master": None}
            os.chdir(tmp)
            os.makedirs("media", exist_ok=True)
            cb_scene._run_beats(d, "2", "Ep1")
        finally:
            cb_scene.keyframe_for = orig_kf
            cb_scene.cb_gen.generate_image = orig_gen
            cb_scene.P.scene_cfg = orig_scene_cfg

        check("a vision beat still gets its own keyframe generated", calls == ["Ep1_2.B1_vision_one.png"], f"calls={calls}")
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# THE GATE-2 LINT, NOW ENFORCED IN _run_beats TOO (2026-07-14, CLAUDE.md rule 84/85 — a full gate-by-gate
# audit found _run_beats (the body of coverage(), GATE_SEQ's own canonical Gate-2b firing function) computed
# keyframe_for()'s info["lint"] but never read it, so the OFFICIAL way a scene's keyframes get built had zero
# content enforcement — a beat with a real, confirmed BLOCK-worthy prompt would still fire a real generation
# call. build_one_beat/regen_shot already hard-blocked on the identical lint; this closes the gap.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_run_beats_blocks_on_lint_failure():
    tmp = tempfile.mkdtemp()
    cwd = os.getcwd()
    try:
        beats = [
            {"beatCode": "3.B1", "sceneNumber": "3", "slug": "blocked"},
            {"beatCode": "3.B2", "sceneNumber": "3", "slug": "clean"},
        ]
        d = {"beats": beats}

        def fake_keyframe_for(all_beats, code, episode="Ep1", note=""):
            if code == "3.B1":
                info = {"kind": "opening keyframe", "chain": {"status": "first", "prev": None},
                        "lint": {"ok": False, "blockers": ["anti-slop word in a character paragraph"], "flags": []}}
            else:
                info = {"kind": "opening keyframe", "chain": {"status": "first", "prev": None},
                        "lint": {"ok": True, "blockers": [], "flags": ["a harmless advisory flag"]}}
            return f"prompt for {code}", ["ref1"], info

        calls = []

        def fake_generate_image(prompt, refs, aspect, out):
            calls.append(out)

        orig_kf, orig_gen = cb_scene.keyframe_for, cb_scene.cb_gen.generate_image
        orig_scene_cfg = cb_scene.P.scene_cfg
        try:
            cb_scene.keyframe_for = fake_keyframe_for
            cb_scene.cb_gen.generate_image = fake_generate_image
            cb_scene.P.scene_cfg = lambda episode, scene: {"name": "Test Scene", "master": None}
            os.chdir(tmp)
            os.makedirs("media", exist_ok=True)
            cb_scene._run_beats(d, "3", "Ep1")
        finally:
            cb_scene.keyframe_for = orig_kf
            cb_scene.cb_gen.generate_image = orig_gen
            cb_scene.P.scene_cfg = orig_scene_cfg

        check("a beat with lint.ok=False is NEVER generated — the block actually stops the fire",
              "Ep1_3.B1_blocked.png" not in calls, f"calls={calls}")
        check("a beat with lint.ok=True (even carrying an advisory flag) IS generated — flags never block",
              "Ep1_3.B2_clean.png" in calls, f"calls={calls}")
        check("exactly one keyframe generated total (only the clean beat)", calls == ["Ep1_3.B2_clean.png"], f"calls={calls}")
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp, ignore_errors=True)


def test_invalidate_keyframe_qa_removes_stale_sidecar_only():
    """FIXED 2026-07-14 (live — Julian regenerating 1.B1, "there is no real status on the image"): regen_shot
    wrote a fresh .png but left the OLD .keyframe_qa.json sidecar sitting there describing the OLD image —
    the Studio's own qaBadge (app.html's kfCard) would then show a stale, wrong verdict as if it were current.
    Proves the fix (a) removes the exact sidecar for the beat that was just regenerated, (b) never touches a
    SIBLING beat's own sidecar, and (c) never raises when there's nothing to remove (the common case — most
    keyframes have never had Gate 2b's real vision QA run on them at all)."""
    tmp = tempfile.mkdtemp(prefix="cb_scene_test_")
    cwd = os.getcwd()
    try:
        os.chdir(tmp)
        os.makedirs("media", exist_ok=True)
        stale = "media/Ep1_1.B1_test-beat.keyframe_qa.json"
        sibling = "media/Ep1_1.B2_other-beat.keyframe_qa.json"
        open(stale, "w").write('{"shot": "1.B1", "ok": false}')
        open(sibling, "w").write('{"shot": "1.B2", "ok": true}')

        cb_scene._invalidate_keyframe_qa("Ep1", "1.B1", "test-beat")

        check("the regenerated beat's own stale sidecar is removed", not os.path.exists(stale))
        check("a sibling beat's sidecar is untouched", os.path.exists(sibling))

        raised = False
        try:
            cb_scene._invalidate_keyframe_qa("Ep1", "1.B1", "test-beat")  # nothing left to remove
        except Exception:
            raised = True
        check("calling it again when there's nothing to remove never raises", not raised)
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    print("test_run_beats_skips_chained_and_pending_continuation:")
    test_run_beats_skips_chained_and_pending_continuation()
    print("test_run_beats_still_generates_vision_beats:")
    test_run_beats_still_generates_vision_beats()
    print("test_run_beats_blocks_on_lint_failure:")
    test_run_beats_blocks_on_lint_failure()
    print("test_invalidate_keyframe_qa_removes_stale_sidecar_only:")
    test_invalidate_keyframe_qa_removes_stale_sidecar_only()
    print()
    if FAIL:
        print(f"{len(FAIL)} FAILED, {len(PASS)} passed")
        sys.exit(1)
    print(f"ALL PASS ({len(PASS)}/{len(PASS)}) — cb_scene._run_beats correctly skips Gate-2b keyframe "
          f"generation for every continuation beat (chained or pending), generating only for the scene's "
          f"own opener and any vision beat, and correctly hard-blocks on a real keyframe-lint failure "
          f"while a mere advisory flag never stops the fire.")


if __name__ == "__main__":
    main()
