#!/usr/bin/env python3
"""test_cb_director.py — regression coverage for cb_director.direct()'s Gate-0 provenance hard
block (2026-07-14, Julian: "hard block if the input script has no record of having passed
through Gate 0's own Writer process — no belowBar field, no lock").

Before this fix, direct() (the real Gate 1 entry point) would break down ANY script text handed
to it with zero check that the script actually came from cb_writer.write() (Gate 0, the Writers'
Room) — a script uploaded straight into the Studio (cb-studio/serve.py's own /api/episode handler
explicitly deletes any old .score.json sidecar on upload, since "an uploaded script carries no
Writers'-Room scorecard") sailed into Gate 1 with no record it was ever reviewed against the Show
Bible/North Star. Now direct() refuses outright — a plain RuntimeError, before spending a single
token — unless a matching {stem}.score.json sidecar exists next to the script and carries a
'belowBar' key (cb_writer.write()'s own always-present marker).

Convention matches test_cb_voice.py / test_cb_prompts.py / test_gate_cascade.py: plain Python,
assert-style checks recorded via check(), no pytest/unittest, a main() that prints PASS/FAIL per
case and sys.exit(1) on any failure. Zero real API calls — the provenance check runs and raises
BEFORE _mind()/any LLM call, proven here by monkeypatching _mind() to a sentinel that would only
ever fire if the check let a valid case through.

    python3 test_cb_director.py
"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cb_director

RESULTS = []  # (name, ok, detail)


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


class _ReachedMind(Exception):
    """Sentinel — proves direct() got PAST the provenance check and reached the real work."""


def _scratch_script(tmp, name="Ep9_Test_Script.txt"):
    p = os.path.join(tmp, name)
    with open(p, "w") as f:
        f.write("SCENE 1 -- SOMEWHERE\n\nFUZZBY: Hi.\n")
    return p


def _run_gated(script_path):
    """Calls direct() with _mind() monkeypatched to raise _ReachedMind — so this NEVER spends a
    real API call regardless of which branch the provenance check takes."""
    orig_mind = cb_director._mind
    cb_director._mind = lambda: (_ for _ in ()).throw(_ReachedMind("reached _mind()"))
    try:
        cb_director.direct(script_path, "Ep9", "Test Script")
        return None  # unreachable — direct() always raises via _mind() or the provenance check
    except _ReachedMind:
        return "reached_mind"
    except RuntimeError as e:
        return str(e)
    finally:
        cb_director._mind = orig_mind


# ═══════════════════════════════════════════════════════════════════════════════════
# THE GATE-0 PROVENANCE HARD BLOCK — all four branches
# ═══════════════════════════════════════════════════════════════════════════════════
def test_gate0_provenance_hard_block():
    tmp = tempfile.mkdtemp(prefix="cb_director_gate0_test_")
    try:
        script_path = _scratch_script(tmp)
        sidecar_path = os.path.join(tmp, "Ep9_Test_Script.score.json")

        # Case 1 — no sidecar at all.
        result = _run_gated(script_path)
        check("direct(): a script with NO sidecar at all is refused before any LLM work",
              isinstance(result, str) and "no Gate-0 record found" in result, result)

        # Case 2 — sidecar exists but is invalid JSON.
        with open(sidecar_path, "w") as f:
            f.write("{not valid json")
        result = _run_gated(script_path)
        check("direct(): an invalid-JSON sidecar is refused before any LLM work",
              isinstance(result, str) and "not valid JSON" in result, result)

        # Case 3 — sidecar is valid JSON but missing the belowBar key.
        with open(sidecar_path, "w") as f:
            json.dump({"title": "Test Script"}, f)
        result = _run_gated(script_path)
        check("direct(): a sidecar missing the 'belowBar' key is refused before any LLM work",
              isinstance(result, str) and "no 'belowBar' field" in result, result)

        # Case 4 — a real, valid Gate-0 sidecar (matching cb_writer.write()'s own shape) lets
        # direct() proceed PAST the provenance check and reach the real work.
        with open(sidecar_path, "w") as f:
            json.dump({"title": "Test Script", "belowBar": False, "scorecard": {}}, f)
        result = _run_gated(script_path)
        check("direct(): a valid belowBar sidecar lets direct() proceed past the provenance check",
              result == "reached_mind", result)

        # Case 5 — a belowBar=True sidecar is a QUALITY flag, not a PROVENANCE one — must still
        # proceed (matching cb_writer's own "written anyway so Gate 1 isn't blocked" design).
        with open(sidecar_path, "w") as f:
            json.dump({"title": "Test Script", "belowBar": True, "scorecard": {}}, f)
        result = _run_gated(script_path)
        check("direct(): belowBar=True (below-quality-bar) is NOT a provenance block — still proceeds",
              result == "reached_mind", result)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════════════
# THE REAL PRODUCTION SCRIPT'S GRANDFATHER SIDECAR — a regression pin. Ep1's own founding
# script predates cb_writer.py's automated Writers' Room; it was grandfathered with a
# hand-authored sidecar (rules 310/CLAUDE.md, 2026-07-14) recording its real, already-
# established provenance rather than a fabricated LLM score. If that sidecar is ever
# accidentally deleted, this test catches it — Gate 1 would otherwise refuse to re-fire
# for the show's own founding episode.
# ═══════════════════════════════════════════════════════════════════════════════════
def test_real_ep1_script_has_grandfather_sidecar():
    sidecar_path = os.path.join(HERE, "..", "shows", "crystal-bears", "episodes", "scripts",
                                 "Ep1_The_Adventure_Begins.score.json")
    check("the real Ep1 script's grandfather sidecar exists on disk",
          os.path.exists(sidecar_path), sidecar_path)
    if os.path.exists(sidecar_path):
        d = json.loads(open(sidecar_path).read())
        check("the real Ep1 grandfather sidecar carries a 'belowBar' key (the shape direct() checks for)",
              "belowBar" in d, d)
        check("the real Ep1 grandfather sidecar honestly marks itself hand-authored, not an invented LLM score",
              d.get("handAuthored") is True, d)


def main():
    test_gate0_provenance_hard_block()
    test_real_ep1_script_has_grandfather_sidecar()

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
