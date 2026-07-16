#!/usr/bin/env python3
"""test_cb_address.py — regression coverage for cb_address.scene_captions/write_captions (2026-07-14).

Real, deliverable dialogue captions timed to the scene's actual rendered timeline — built from the beat's own
cuts[].dialogue field ("SPEAKER: line") plus _scene_shot_walk's already-proven scene-cumulative shot timing
(the same walk the retake sheet and review overlay already use). This locks in: only spoken shots produce a
caption line; a chorus/"ALL:" line is captioned without an invented speaker label; a malformed/blank dialogue
string is skipped, never crashes; both SRT and VTT files write valid, correctly-ordered timecodes.

ZERO API/ffmpeg/LLM calls: _scene_shot_walk (already independently exercised by cb_address's own existing
retake-sheet functionality) is monkeypatched to yield controlled (bm, sh, scene_in, scene_out) tuples — this
tests scene_captions/write_captions' OWN new logic (which cut it reads, how it formats a speaker label, how
it writes timecodes), not the shared walk's pre-existing timing math.

Convention matches test_cb_post.py / test_cb_beats.py: plain Python, a fails-list-of-strings pattern, a
main() that prints PASS/FAIL per case and sys.exit(1) on any failure.

    python3 test_cb_address.py
"""
import os, sys, json, tempfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cb_address


def _scratch(fn):
    tmp = tempfile.mkdtemp(prefix="cb_address_test_")
    cwd = os.getcwd()
    os.makedirs(os.path.join(tmp, "media"), exist_ok=True)
    os.chdir(tmp)
    try:
        return fn()
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp, ignore_errors=True)


_PKG = {
    "beats": [
        {"beatCode": "1.B1", "sceneNumber": "1", "cuts": [
            {"dialogue": "FUZZBY: Nailed it.", "action": "he strikes a pose"},
            {"dialogue": None, "action": "Zenny watches, deadpan"},
        ]},
        {"beatCode": "1.B2", "sceneNumber": "1", "cuts": [
            {"dialogue": "ALL: Surprise!", "action": "the whole group jumps out"},
        ]},
        {"beatCode": "1.B3", "sceneNumber": "1", "cuts": [
            {"dialogue": "  ", "action": "a blank/whitespace-only dialogue string — must be skipped, not crash"},
            {"dialogue": "malformed no colon here", "action": "no ':' at all — must be skipped, not crash"},
        ]},
    ]
}


def _fake_walk_for(pkg_path, scene_num, episode="Ep1"):
    """A fixed, ordered sequence of (bm, sh, scene_in, scene_out) — mirrors the shape _scene_shot_walk really
    yields (bm carries 'code'; sh carries 'index'), covering: a normal spoken shot, a silent shot (skipped by
    scene_captions since it has no dialogue), a chorus/ALL line, and two malformed-dialogue shots. Signature
    matches _scene_shot_walk's own real call shape (pkg_path, scene_num, episode) exactly."""
    yield {"code": "1.B1"}, {"index": 1}, 0.0, 5.0
    yield {"code": "1.B1"}, {"index": 2}, 5.0, 8.0
    yield {"code": "1.B2"}, {"index": 1}, 8.0, 12.5
    yield {"code": "1.B3"}, {"index": 1}, 12.5, 14.0
    yield {"code": "1.B3"}, {"index": 2}, 14.0, 16.0


def test_scene_captions_extracts_real_dialogue_with_correct_timing():
    def _run():
        json.dump(_PKG, open("pkg.json", "w"))
        orig = cb_address._scene_shot_walk
        cb_address._scene_shot_walk = _fake_walk_for
        try:
            return cb_address.scene_captions("pkg.json", "1", "Ep1")
        finally:
            cb_address._scene_shot_walk = orig
    caps = _scratch(_run)
    fails = []
    ok_count = len(caps) == 2   # only 1.B1 cut1 (dialogue) and 1.B2 cut1 (ALL) produce a caption
    print(f"  {'PASS' if ok_count else 'FAIL'}  exactly 2 real captions (silent + blank + malformed shots skipped) — got {len(caps)}: {caps}")
    if not ok_count:
        fails.append(f"scene_captions: expected 2 captions, got {len(caps)}: {caps}")
    if caps:
        c0 = caps[0]
        ok0 = c0["start"] == 0.0 and c0["end"] == 5.0 and c0["text"] == "Fuzzby: Nailed it."
        print(f"  {'PASS' if ok0 else 'FAIL'}  caption 1: correct timing + speaker-labelled words — got {c0}")
        if not ok0:
            fails.append(f"caption 1 wrong: {c0}")
    if len(caps) > 1:
        c1 = caps[1]
        ok1 = c1["start"] == 8.0 and c1["end"] == 12.5 and c1["text"] == "Surprise!"
        print(f"  {'PASS' if ok1 else 'FAIL'}  caption 2: an 'ALL:' chorus line has NO invented speaker label — got {c1}")
        if not ok1:
            fails.append(f"caption 2 (ALL: chorus line) wrong — expected no speaker label: {c1}")
    return fails


def test_write_captions_srt_and_vtt():
    def _run():
        json.dump(_PKG, open("pkg.json", "w"))
        orig = cb_address._scene_shot_walk
        cb_address._scene_shot_walk = _fake_walk_for
        try:
            srt_path, n1 = cb_address.write_captions("pkg.json", "1", "Ep1", fmt="srt")
            vtt_path, n2 = cb_address.write_captions("pkg.json", "1", "Ep1", fmt="vtt")
            return srt_path, n1, open(srt_path, encoding="utf-8").read(), vtt_path, n2, open(vtt_path, encoding="utf-8").read()
        finally:
            cb_address._scene_shot_walk = orig
    srt_path, n1, srt_text, vtt_path, n2, vtt_text = _scratch(_run)
    fails = []
    ok_counts = n1 == 2 and n2 == 2
    print(f"  {'PASS' if ok_counts else 'FAIL'}  both formats report 2 captions written — srt={n1}, vtt={n2}")
    if not ok_counts:
        fails.append(f"write_captions count mismatch: srt={n1}, vtt={n2}")

    ok_srt_ext = srt_path.endswith(".srt")
    ok_srt_tc = "00:00:00,000 --> 00:00:05,000" in srt_text   # SRT uses a comma before milliseconds
    ok_srt_text = "Fuzzby: Nailed it." in srt_text and "Surprise!" in srt_text
    print(f"  {'PASS' if ok_srt_ext else 'FAIL'}  srt path has .srt extension — got {srt_path}")
    print(f"  {'PASS' if ok_srt_tc else 'FAIL'}  srt timecode uses comma-milliseconds format — got:\n{srt_text[:200]}")
    print(f"  {'PASS' if ok_srt_text else 'FAIL'}  srt contains both real caption lines")
    for ok, msg in [(ok_srt_ext, f"srt path wrong extension: {srt_path}"),
                     (ok_srt_tc, "srt timecode format wrong (expected comma-ms)"),
                     (ok_srt_text, "srt missing expected caption text")]:
        if not ok:
            fails.append(msg)

    ok_vtt_ext = vtt_path.endswith(".vtt")
    ok_vtt_header = vtt_text.startswith("WEBVTT")
    ok_vtt_tc = "00:00:00.000 --> 00:00:05.000" in vtt_text   # VTT uses a period before milliseconds
    print(f"  {'PASS' if ok_vtt_ext else 'FAIL'}  vtt path has .vtt extension — got {vtt_path}")
    print(f"  {'PASS' if ok_vtt_header else 'FAIL'}  vtt file starts with the required 'WEBVTT' header")
    print(f"  {'PASS' if ok_vtt_tc else 'FAIL'}  vtt timecode uses period-milliseconds format — got:\n{vtt_text[:200]}")
    for ok, msg in [(ok_vtt_ext, f"vtt path wrong extension: {vtt_path}"),
                     (ok_vtt_header, "vtt file missing the required WEBVTT header"),
                     (ok_vtt_tc, "vtt timecode format wrong (expected period-ms)")]:
        if not ok:
            fails.append(msg)
    return fails


def main():
    fails = []
    print("=== scene_captions: real dialogue extraction + correct scene-cumulative timing ===")
    fails += test_scene_captions_extracts_real_dialogue_with_correct_timing()
    print("\n=== write_captions: valid SRT + VTT files, correct timecode formats ===")
    fails += test_write_captions_srt_and_vtt()
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
