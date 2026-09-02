#!/usr/bin/env python3
"""Prove the browser displays backend production state without re-deriving approvals.

The real app.html script is executed via Node. Fixtures deliberately contradict raw media and
ledger fields; the backend policy document must always win.
"""
import os, re, sys, json, shutil, subprocess, tempfile, pathlib

HERE = pathlib.Path(__file__).resolve().parent
APP_HTML = HERE / "app.html"
FAILS = []


def check(name, cond, detail=""):
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
        FAILS.append(name)


def _extract_script():
    html = APP_HTML.read_text()
    m = re.search(r"<script>(.*)</script>", html, re.S)
    if not m:
        raise RuntimeError("could not find <script> block in app.html")
    return m.group(1)


def _run(bundle, script_approved, scene, extra_js=""):
    """Executes the REAL deriveSceneState (and sceneCardStatus) from app.html against one
    fixture, inside a minimal browser-global stub (document/localStorage/fetch/window), via a
    real Node process — never a hand-copied reimplementation of the derivation logic."""
    script = _extract_script()
    wrapper = f"""
const document = {{
  documentElement: {{ style:{{setProperty(){{}}}} }},
  body: {{ classList:{{add(){{}},remove(){{}},toggle(){{}},contains(){{return false}}}} }},
  getElementById: () => ({{ classList:{{add(){{}},remove(){{}},toggle(){{}},contains(){{return false}}}}, value:'', innerHTML:'', style:{{}}, appendChild(){{}}, addEventListener(){{}}, setAttribute(){{}}, getAttribute(){{return null}} }}),
  addEventListener: () => {{}},
  querySelectorAll: () => [],
  querySelector: () => null,
}};
const window = {{ location: {{ origin:'http://x' }}, innerWidth:1024, addEventListener(){{}} }};
const localStorage = {{ getItem: () => null, setItem: () => {{}} }};
const sessionStorage = {{ getItem: () => null, setItem: () => {{}} }};
const history = {{ replaceState: () => {{}} }};
const location = {{ hash:'', search:'', pathname:'/', href:'http://x/' }};
function fetch(){{ return new Promise(() => {{}}); }}
{script}
{extra_js}
const __bundle = {json.dumps(bundle)};
const __stages = deriveSceneState(__bundle, {json.dumps(script_approved)}, {json.dumps(scene)});
const __status = sceneCardStatus(__stages);
console.log(JSON.stringify({{stages: __stages, status: __status}}));
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(wrapper)
        path = f.name
    try:
        r = subprocess.run(["node", path], capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            raise RuntimeError(f"node exited {r.returncode}: {r.stderr[-2000:]}")
        return json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        os.unlink(path)


def main():
    print("== confirming app.html's script block extracts + loads cleanly ==")
    try:
        script = _extract_script()
        check("script block extracted", len(script) > 1000)
        subprocess.run(["node", "--check", "-"], input=script, text=True, check=True,
                        capture_output=True)
        check("script block is valid JS", True)
    except Exception as e:
        check("script block is valid JS", False, repr(e))
        print("ABORTING — cannot proceed without a loadable script")
        sys.exit(1)

    def policy(**overrides):
        stages = {name: {"state": "locked"} for name in
                  ("script", "storyboard", "scenelook", "voice", "keyframe",
                   "animation", "continuity", "final")}
        stages.update(overrides)
        return {"policyVersion": "direct-input-readiness-v1",
                "stages": stages, "shots": []}

    print("\n== raw files and ledgers cannot override backend state ==")
    stale = {
        "pkg": {"revision": 7, "continuityLedger": [{
            "shotId": "S1.SH1", "keyframeApproval": {"approved": True}}]},
        "media": {"shots": {"S1.SH1": {"keyframe": "/a/file.png"}}},
        "productionState": policy(
            script={"state": "approved"}, storyboard={"state": "approved"},
            keyframe={"state": "blocked", "sub": "direct inputs changed"},
            voice={"state": "locked"}, animation={"state": "locked"}),
    }
    out = _run(stale, True, "1")
    check("a present file and raw approval cannot grant approval",
          out["stages"]["keyframe"]["state"] == "blocked", out["stages"]["keyframe"])
    check("dependent states come from the same policy document",
          out["stages"]["voice"]["state"] == "locked" and
          out["stages"]["animation"]["state"] == "locked")
    check("board status consumes the same state", out["status"] == "blocked", out["status"])

    print("\n== rejection and pending decisions are displayed verbatim ==")
    rejected = {"productionState": policy(
        script={"state": "approved"}, storyboard={"state": "approved"},
        scenelook={"state": "rejected", "sub": "candidate rejected"})}
    out2 = _run(rejected, True, "1")
    check("backend rejection remains rejected",
          out2["stages"]["scenelook"]["state"] == "rejected")
    check("board surfaces the decision", out2["status"] == "rejected", out2["status"])

    print("\n== package revision metadata cannot invalidate a carried approval ==")
    carried = {
        "pkg": {"revision": 9, "continuityLedger": [{
            "shotId": "S1.SH1",
            "keyframeApproval": {"approved": True, "packageRevision": 2}}]},
        "productionState": {
            **policy(
                script={"state": "approved"}, storyboard={"state": "approved"},
                scenelook={"state": "approved"}, keyframe={"state": "approved"},
                voice={"state": "ready"}, animation={"state": "locked"}),
            "shots": [{"shotId": "S1.SH1", "needsKeyframe": True, "kf": "approved",
                       "current": {"keyframe": True}}],
        },
    }
    out3 = _run(carried, True, "1")
    check("direct-input-current approval carries across package revisions",
          out3["stages"]["keyframe"]["state"] == "approved", out3["stages"]["keyframe"])
    check("the backend unlocks only the stage it declared ready",
          out3["stages"]["voice"]["state"] == "ready" and
          out3["stages"]["animation"]["state"] == "locked")

    print("\n== missing authoritative state fails closed ==")
    out4 = _run({"pkg": {"revision": 1}, "media": {"picture": "/old.mp4"}}, True, "1")
    check("legacy fields are never used as a fallback approval policy",
          out4["stages"]["final"]["state"] in {"blocked", "locked"},
          out4["stages"]["final"])

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} case(s) — {FAILS}")
        sys.exit(1)
    print("ALL PASS ✓ — the browser displays one backend approval/readiness policy")


if __name__ == "__main__":
    main()
