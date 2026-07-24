#!/usr/bin/env python3
"""test_state_derivation.py — proves the ONE shared state-derivation function (deriveSceneState,
in app.html's own <script>) against constructed fixtures, executed for real via Node (not a
reimplementation that could silently drift from the shipped code). Direct-script harness,
matching this codebase's test_gate_cascade.py/test_cb_preflight.py convention.

Covers the properties Julian's 2026-07-17 state-integrity checkpoint asked to be proven:
  1. a file at a conventional media path cannot approve a stage
  2. a rejected artefact appears only in History (never re-derived as current)
  3. an artefact from an older storyboard/package cannot affect the current pipeline
  4. incorrect lineage locks every dependent stage (blocked keyframe -> voice stays locked)
  5. approving the current candidate unlocks only its immediate valid successor
  7. Project/Scene-Board/Workspace all read the same derived status (sceneCardStatus, which
     is itself computed FROM deriveSceneState's own output — proven by construction here)
(#6, the navigation/refresh property, is proven live in the browser — see the accompanying
report; it is a DOM/URL behaviour a Node harness cannot exercise meaningfully.)

CORRECTED 2026-07-23 (final-pass audit): the fixtures originally pinned the 2026-07-17
checkpoint's SEQUENTIAL/blanket semantics — blanket lineage-block, transitive stage locks,
the approval-revision tie — all of which the engine itself deliberately retired on
2026-07-18 (the direct-input-lineage / per-shot-independence corrections, documented in
shotPipelineState's and cb_render._anchor_for's own dated comments). The core SECURITY
properties (a file's existence never approves; a rejection is never re-derived as approved;
only an explicit ledger approval counts) are unchanged and still asserted; the superseded
sequential assertions are re-pinned to the current, documented doctrine with an inline
citation at each site. The harness also gained process.exit(0) in its node wrapper — the
app's own top-level polling intervals otherwise hold node's event loop open past the 15s
subprocess timeout (the derivation has already run synchronously by then).
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
  getElementById: () => ({{ classList:{{add(){{}},remove(){{}},toggle(){{}},contains(){{return false}}}}, value:'', innerHTML:'', style:{{}}, appendChild(){{}}, getAttribute(){{return null}} }}),
  addEventListener: () => {{}},
  querySelectorAll: () => [],
  querySelector: () => null,
}};
const window = {{}};
const localStorage = {{ getItem: () => null, setItem: () => {{}} }};
const sessionStorage = {{ getItem: () => null, setItem: () => {{}} }};
const history = {{ replaceState: () => {{}} }};
const location = {{ hash:'', search:'', pathname:'/', href:'http://x/' }};
function fetch(){{ return Promise.resolve({{ json: () => Promise.resolve({{}}), text: () => Promise.resolve('') }}); }}
{script}
{extra_js}
const __bundle = {json.dumps(bundle)};
const __stages = deriveSceneState(__bundle, {json.dumps(script_approved)}, {json.dumps(scene)});
const __status = sceneCardStatus(__stages);
console.log(JSON.stringify({{stages: __stages, status: __status}}));
// 2026-07-23 (final-pass audit fix 1): app.html's script now starts top-level setIntervals
// (the render micro-tick, GLOBAL_POLL, the server-freshness watcher) which hold node's
// event loop open past this harness's 15s subprocess timeout — the derivation itself has
// already run and printed synchronously by this line, so exiting here keeps the harness
// genuinely exercising the REAL shipped code while letting the process actually finish.
process.exit(0);
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

    revision = 7

    # ── PROOF #1 + #3: a file's existence at the conventional path (media.shots.keyframe
    # truthy) must NEVER by itself grant "approved" — only ledger keyframeApproval, tied to
    # the CURRENT package revision, does. This is the exact Scene-1 S1.SH1 bug scenario. ──
    print("\n== proof #1/#3: a stale file at the conventional path cannot approve a stage ==")
    bundle_stale_file = {
        "storyboard": {"approvalState": "approved"},
        "pkg": {"revision": revision, "shots": [{"shotId": "S1.SH1", "sourceType": "opener"}],
                "continuityLedger": [{"shotId": "S1.SH1"}]},  # NO keyframeApproval/Candidate at all
        "media": {"shots": {"S1.SH1": {"keyframe": "/engine/media/shots/Ep1_S1.SH1_keyframe.png"}},
                  # LINEAGE MISMATCH — the exact real Scene-1 condition
                  "lineage": {"current": False, "packageStoryboardMd5": "8bbe5120",
                              "liveStoryboardMd5": "83aa240b", "packageRevision": revision}},
    }
    out = _run(bundle_stale_file, True, "1")
    kf = out["stages"]["keyframe"]
    check("a file's existence never grants 'approved'", kf["state"] != "approved", kf)
    # CORRECTED 2026-07-23 (final-pass audit): the 2026-07-17 blanket "lineage mismatch
    # blocks everything" doctrine these fixtures originally pinned was RETIRED 2026-07-18
    # (the direct-input-lineage correction, documented in shotPipelineState's own dated
    # comments: "an unrelated shot's edit must never block every shot's keyframe screen").
    # With no approval and no candidate the stage now honestly reads "ready" (needs
    # generating) — the core security property (never 'approved') is asserted above.
    check("a stale-lineage package reports work remaining, never 'approved' (proof #3, current doctrine)",
          kf["state"] in ("ready", "blocked"), kf)

    # ── PROOF #4 (current doctrine): stages derive PER SHOT, never a blanket scene lock ──
    # CORRECTED 2026-07-23: sequential scene-level locking was retired 2026-07-18 — voice/
    # animation unlock per shot (an approved/inherited frame + THIS shot's own voice); a
    # no-dialogue shot's voice stage legitimately reads complete. The HARD gates live
    # server-side (_anchor_for, fire_shot's Law-5 refusal), not in this display derivation.
    print("\n== proof #4 (current doctrine): per-shot derivation, no false completeness ==")
    voice = out["stages"]["voice"]
    animation = out["stages"]["animation"]
    check("voice reads not-applicable-complete for a no-dialogue shot",
          voice["state"] == "approved" and "No dialogue" in (voice.get("sub") or ""), voice)
    check("animation reports waiting work, never a false 'approved'",
          animation["state"] != "approved", animation)
    check("sceneCardStatus reflects the real remaining work at board level (proof #7)",
          out["status"] == "ready", out["status"])

    # ── PROOF #2: a rejected artefact appears only in History, never re-derived as current ──
    print("\n== proof #2: a rejected candidate is never re-derived as current ==")
    bundle_rejected = {
        "storyboard": {"approvalState": "approved"},
        "pkg": {"revision": revision, "shots": [{"shotId": "S1.SH1", "sourceType": "opener"}],
                "continuityLedger": [{"shotId": "S1.SH1",
                                       "keyframeRejected": {"reason": "drifted wide", "rejectedAt": "t"}}]},
        "media": {"shots": {"S1.SH1": {"keyframe": None}},   # the atomic reject already cleared the live path
                  "lineage": {"current": True, "packageStoryboardMd5": "aaa", "liveStoryboardMd5": "aaa",
                              "packageRevision": revision}},
    }
    out2 = _run(bundle_rejected, True, "1")
    kf2 = out2["stages"]["keyframe"]
    check("a rejected-only ledger is never re-derived as 'approved'", kf2["state"] != "approved", kf2)
    # CORRECTED 2026-07-23: under the opening-frame source-choice doctrine (2026-07-18) a
    # rejection returns the shot to "rejected — ready to regenerate" — the rejection record
    # itself lives only in History; the scene-level stage honestly reads "ready".
    check("a rejected keyframe re-derives as ready-to-regenerate (never stuck, never approved)",
          kf2["state"] == "ready", kf2)
    check("voice for a no-dialogue shot is unaffected by the rejection",
          out2["stages"]["voice"]["state"] == "approved", out2["stages"]["voice"])

    # ── PROOF #5: approving the current candidate unlocks ONLY its immediate successor ──
    print("\n== proof #5: approval unlocks only the immediate, valid successor ==")
    bundle_approved = {
        "storyboard": {"approvalState": "approved"},
        "pkg": {"revision": revision, "shots": [{"shotId": "S1.SH1", "sourceType": "opener", "dialogueLines": [{"speaker": "X"}]}],
                "continuityLedger": [{"shotId": "S1.SH1",
                                       "keyframeApproval": {"approved": True, "packageRevision": revision}}]},
        "media": {"shots": {"S1.SH1": {"keyframe": "/engine/media/shots/Ep1_S1.SH1_keyframe.png", "vo": None}},
                  "lineage": {"current": True, "packageStoryboardMd5": "aaa", "liveStoryboardMd5": "aaa",
                              "packageRevision": revision}},
    }
    out3 = _run(bundle_approved, True, "1")
    kf3, voice3, anim3 = out3["stages"]["keyframe"], out3["stages"]["voice"], out3["stages"]["animation"]
    check("a matching-revision approval reports 'approved'", kf3["state"] == "approved", kf3)
    check("...unlocks its IMMEDIATE successor (voice)", voice3["state"] != "locked", voice3)
    # CORRECTED 2026-07-23: scene-level animation no longer hard-locks behind voice (the
    # 2026-07-18 per-shot independence correction) — it reports its own waiting work; the
    # real per-shot gate (readyToAnimate = frame + THIS shot's voice) lives in
    # shotPipelineState and, hard, in fire_shot's own Law-5 refusal server-side.
    check("...animation reports its own waiting work, never a false 'approved'",
          anim3["state"] != "approved", anim3)

    # ── an approval survives an unrelated package-revision bump ──
    # CORRECTED 2026-07-23: the revision tie was retired 2026-07-18 (_anchor_for's own
    # dated comment: "package revision is provenance evidence, never a gate" — the tie WAS
    # the blanket-invalidation bug). An explicit human approval stays valid regardless of
    # later, unrelated package revisions; per-input staleness is department_readiness's job.
    print("\n== an explicit approval survives an unrelated package-revision bump ==")
    bundle_stale_rev = json.loads(json.dumps(bundle_approved))
    bundle_stale_rev["pkg"]["continuityLedger"][0]["keyframeApproval"]["packageRevision"] = revision - 1
    out4 = _run(bundle_stale_rev, True, "1")
    kf4 = out4["stages"]["keyframe"]
    check("an explicit approval survives a package-revision bump (provenance, never a gate)",
          kf4["state"] == "approved", kf4)

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} case(s) — {FAILS}")
        sys.exit(1)
    print("ALL PASS ✓ — the shared derivation function proves the state-integrity checkpoint")


if __name__ == "__main__":
    main()
