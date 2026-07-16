#!/usr/bin/env python3
"""Regression coverage for cb_director_eye.py — first test file for this module (closes a standing gap).

THE FIX BEING PROTECTED (2026-07-15, Julian, live — "the job of the rules is to deliver the scene then the
beats within the scene... the guard rails are there to protect the beat the director has created"): confirmed
live that Director's Eye flagged 1.B5's HIGH-severity storm-grey lighting as a break of the locked EP3
"S1-3 stay warm-golden" doctrine — but `_slim()` (the function deciding what the Eye is even shown) never
included `director_mode` or `carryMarks`, the two fields where 1.B5's own declared creative intent lives
("Exit on a comic button while planting the larger weather turn faithfully"). The Eye was judging a beat's
content against an episode-wide rule with zero visibility into the storyboard's own stated justification.

Fixed: both fields now reach the Eye, and the SYSTEM prompt states explicitly that a beat's OWN declared
director_mode/carryMarks is the storyboard's authority to deviate from a scene-level default — the Eye's job
becomes judging whether the beat delivers ITS OWN stated intent, not overruling that intent blind.

Run: python3 test_cb_director_eye.py  (mocked cb_llm.structured throughout — zero real API cost)
"""
import json

PASS = FAIL = 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"PASS  {name}")
    else:
        FAIL += 1; print(f"FAIL  {name}  {detail}")

import cb_director_eye as DE


print("=== _slim() includes directorMode and carryMarks (the actual fields the fix threads through) ===")
beat = {
    "beatCode": "1.B5", "sceneNumber": 1, "characters": ["Fuzzby", "Zenny"],
    "storyBeat": "Zenny names the storm; Fuzzby gets stuck in a flower.",
    "director_mode": "Exit on a comic button while planting the larger weather turn faithfully.",
    "carryMarks": "pollen still drifting off Fuzzby as he hovers; the named storm and cooling sky",
    "light": "Warm gold drains slightly from the meadow edges as cool grey-blue sky tint touches the upper petals.",
}
slim = DE._slim(beat)
check("directorMode is present and verbatim", slim.get("directorMode") == beat["director_mode"], slim.get("directorMode"))
check("carryMarks is present and verbatim", slim.get("carryMarks") == beat["carryMarks"], slim.get("carryMarks"))
check("light still present (existing field, untouched)", slim.get("light") == beat["light"])
check("a beat with no director_mode/carryMarks authored yet degrades to None, never raises",
      DE._slim({"beatCode": "9.B9"}).get("directorMode") is None)


print("=== the SYSTEM prompt actually states the storyboard-authority rule (not just data plumbing) ===")
check("SYSTEM prompt tells the Eye a beat's own directorMode/carryMarks can justify a scene-level deviation",
      "directorMode" in DE.SYSTEM and "carryMarks" in DE.SYSTEM and "does not override" in DE.SYSTEM)
check("SYSTEM prompt still states the exception has limits (never a blanket excuse)",
      "un-declared drift" in DE.SYSTEM or "genuinely absolute rule" in DE.SYSTEM)


print("=== run() actually threads the new fields into the real LLM call's user payload ===")
_captured = {}
def _mock_structured(system, user, schema, label=None):
    _captured["system"] = system
    _captured["user"] = user
    class _R:
        def model_dump(self):
            return {"findings": [], "summary": {"flagged": 0, "beatsReviewed": 1, "verdict": "CLEAN"}}
    return _R()

orig_structured = DE.cb_llm.structured
DE.cb_llm.structured = _mock_structured
orig_project = DE._project
DE._project = lambda: {"name": "Test Show", "primary": True}
orig_bible = DE._show_bible
DE._show_bible = lambda: ("canon text", {})

import tempfile, os
scratch_pkg = {
    "title": "Test Ep", "theme": "test theme",
    "beats": [beat],
}
tmpdir = tempfile.mkdtemp(prefix="director_eye_test_")
pkg_path = os.path.join(tmpdir, "scratch.json")
json.dump(scratch_pkg, open(pkg_path, "w"))
orig_here = DE.HERE
import pathlib
DE.HERE = pathlib.Path(tmpdir)
(DE.HERE / "media").mkdir(exist_ok=True)

try:
    rep = DE.run(pkg_path, episode="EpTest")
    user_obj = json.loads(_captured["user"])
    beat_in_payload = user_obj["episode"]["beats"][0]
    check("run() reaches the LLM at all (mock was actually called)", "system" in _captured)
    check("the real LLM payload for this beat carries directorMode",
          beat_in_payload.get("directorMode") == beat["director_mode"], beat_in_payload)
    check("the real LLM payload for this beat carries carryMarks",
          beat_in_payload.get("carryMarks") == beat["carryMarks"], beat_in_payload)
    check("run() returns the mocked clean report without raising", rep.get("summary", {}).get("verdict") == "CLEAN")
finally:
    DE.cb_llm.structured = orig_structured
    DE._project = orig_project
    DE._show_bible = orig_bible
    DE.HERE = orig_here
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


print(f"\n{PASS}/{PASS+FAIL} passed.")
if FAIL:
    raise SystemExit(f"{FAIL} FAILURE(S)")
print("ALL PASS")
