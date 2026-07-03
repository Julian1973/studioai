#!/usr/bin/env python3
"""Regression test: scene-gate <-> per-beat lock reconciliation in cb_pipeline.unapprove.

    python3 engine/test_unapprove_locks.py

ISOLATED: imports cb_pipeline (NOT __main__, so no chdir) and overrides cb_pipeline.LOCK to a TEMP file, so the
real engine/locked.json is never read or written. Exercises gates 2b/3/4 (they don't touch locations.json — the
1/2a master-reset is a separate concern). Verifies that un-signing a scene gate:
  • clears that gate + downstream gate flags, keeps upstream    (existing behaviour, unchanged)
  • clears ONLY the dependent per-beat stages for THAT scene    (the fix: 2b->keyframe+clip, 3->clip, 4->none)
  • leaves other scenes entirely untouched                     (no unrelated-scene wipe)
Exit 0 = all pass.
"""
import sys, os, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cb_pipeline

def sample():
    return {"Ep1": {
        "1": {"1": True, "2a": True, "2b": True, "3": True, "4": True,
              "beats": {"1.B1": {"audio": True, "keyframe": True, "clip": True},
                        "1.B2": {"audio": True, "keyframe": True, "clip": True}}},
        "2": {"1": True, "2a": True, "2b": True,
              "beats": {"2.B1": {"audio": True, "keyframe": True, "clip": False}}}}}

def run(gate, scene):
    tmp = tempfile.mktemp(suffix="_locked.json")
    json.dump(sample(), open(tmp, "w"))
    cb_pipeline.LOCK = tmp; cb_pipeline.EP = "Ep1"
    cb_pipeline.unapprove(gate, scene)
    r = json.load(open(tmp)); os.remove(tmp)
    return r

CASES = {
    "2b": dict(gone=["2b", "3", "4"], kept=["1", "2a"],            bclear=["keyframe", "clip"], bkeep=["audio"]),
    "3":  dict(gone=["3", "4"],       kept=["1", "2a", "2b"],      bclear=["clip"],             bkeep=["audio", "keyframe"]),
    "4":  dict(gone=["4"],            kept=["1", "2a", "2b", "3"], bclear=[],                   bkeep=["audio", "keyframe", "clip"]),
}
S2 = {"1": True, "2a": True, "2b": True, "beats": {"2.B1": {"audio": True, "keyframe": True, "clip": False}}}

def main():
    bad = 0
    for gate, e in CASES.items():
        after = run(gate, "1"); s1, s2 = after["Ep1"]["1"], after["Ep1"]["2"]
        print(f"\n=== unapprove {gate} 1 ===  scene1 -> {json.dumps(s1)}")
        for g in e["gone"]:
            ok = g not in s1; bad += not ok; print(f"  {'PASS' if ok else 'FAIL'}  gate {g} cleared")
        for g in e["kept"]:
            ok = s1.get(g) is True; bad += not ok; print(f"  {'PASS' if ok else 'FAIL'}  gate {g} kept")
        for code in ("1.B1", "1.B2"):
            for st in e["bclear"]:
                ok = s1["beats"][code][st] is False; bad += not ok; print(f"  {'PASS' if ok else 'FAIL'}  {code} {st} cleared")
            for st in e["bkeep"]:
                ok = s1["beats"][code][st] is True; bad += not ok; print(f"  {'PASS' if ok else 'FAIL'}  {code} {st} kept")
        ok = (s2 == S2); bad += not ok; print(f"  {'PASS' if ok else 'FAIL'}  scene 2 fully UNTOUCHED")
    print("\n" + ("ALL PASS" if not bad else f"{bad} FAILURE(S)"))
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
