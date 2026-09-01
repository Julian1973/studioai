#!/usr/bin/env python3
"""test_cb_render_generation_safety.py — Julian's 2026-07-18 production-safety directive,
issued after a failed Scene Look Plate regeneration archived the approved, already-reviewed
plate before its replacement had actually been produced, and separately after an unrelated
S1.SH6 storyboard correction invalidated the whole production package (and, by the old
design, would have invalidated S1.SH1's own candidate too, even though nothing about S1.SH1
itself changed).

Proves, in order, the directive's own numbered points:
  1. Every UI/no-op action (approve/save/continue/navigation) causes zero generation calls.
  2. Generating S1.SH1 produces one S1.SH1 candidate and touches no plate or other shot.
  3. Generating a plate touches no keyframes.
  4. A failed plate regeneration leaves the approved plate live and approved.
  5. Changing an unrelated shot (S1.SH6) does not invalidate an unchanged S1.SH1 or the
     approved Scene Look.
  6. Changing S1.SH1's own opening composition DOES invalidate its own candidate/approval.
  7. Changing the approved plate invalidates dependent keyframes (their own recorded
     sceneLookHash no longer matches).

Everything runs against a scratch package/storyboard/media tree in a temp directory
(cb_render.HERE/MEDIA and cb_engine.canonical_package_path monkeypatched) — zero real data
touched. cb_gen.generate_image is stubbed to write a real small file (proving the two-phase
candidate lifecycle end to end) OR to raise (proving the failure-safety case) — never a real
network/provider call either way.

Direct-script harness, matching this codebase's own test_gate_cascade.py convention:
python3 test_cb_render_generation_safety.py; prints PASS/FAIL per case, exits 1 on any fail.
"""
import os, sys, json, shutil, tempfile, hashlib, pathlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cb_render as R
import cb_engine as E

FAILS = []
GEN_CALLS = []   # every cb_gen.generate_image call this run, for proof #2/#3's isolation check


def check(name, cond, detail=""):
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
        FAILS.append(name)


def _scratch():
    d = pathlib.Path(tempfile.mkdtemp(prefix="cb_render_gensafety_"))
    (d / "cb-output" / "creative").mkdir(parents=True)
    (d / "engine" / "media" / "shots").mkdir(parents=True)
    (d / "projects" / "crystal-bears" / "canon").mkdir(parents=True)
    (d / "projects" / "crystal-bears" / "laws").mkdir(parents=True)
    return d


def _write_locations(root, scene="1", episode="Ep1", look="a warm meadow"):
    p = root / "projects" / "crystal-bears" / "canon" / "locations.json"
    p.write_text(json.dumps({episode: {scene: {"look": look, "lighting": "golden",
                                                "weather": "clear", "colorTemperature": "warm",
                                                "definingFeature": "flowers"}}}))


def _write_style(root, text="Pixar-caliber 3D CGI."):
    (root / "projects" / "crystal-bears" / "laws" / "style.txt").write_text(text)


def _write_storyboard(root, scene, episode, sh1_marker="v1", sh6_marker="v1"):
    p = root / "cb-output" / "creative" / f"{episode}_scene{scene}_storyboard.json"
    sb = {"marker": "scene", "shots": [
        {"shotId": "S1.SH1", "openingImage": sh1_marker},
        {"shotId": "S1.SH6", "cameraRelationship": sh6_marker},
    ]}
    p.write_text(json.dumps(sb, sort_keys=True))
    return p


def _write_package(root, scene, episode, shot_ids=("S1.SH1", "S1.SH6"), revision=1, extra_ledgers=None):
    card_hashes = {sid: R._live_card_hash(sid, scene, episode) for sid in shot_ids}
    shots = [{"shotId": sid, "sourceType": "opener", "beatCode": "1.B1",
              "keyframePrompt": f"prompt for {sid}", "keyframeReferenceSlots": {},
              "referenceSlots": {}, "durationSec": 5} for sid in shot_ids]
    ledger = []
    extra_ledgers = extra_ledgers or {}
    for sid in shot_ids:
        ledger.append(dict({"shotId": sid, "status": "designed"}, **extra_ledgers.get(sid, {})))
    pkg = {"episode": episode, "sceneNumber": str(scene), "revision": revision,
           "validation": {"passed": True},
           "sourceStoryboard": {"path": "n/a", "md5": "irrelevant-now",
                                "creativeCardHashes": card_hashes},
           "shots": shots, "continuityLedger": ledger}
    p = root / "cb-output" / f"{episode}_scene{scene}_production_package.json"
    p.write_text(json.dumps(pkg, indent=1))
    return pkg, p


def main():
    scratch = _scratch()
    scene, episode = "1", "EpXSafety"
    orig_here, orig_media = R.HERE, R.MEDIA
    orig_pkg_path = E.canonical_package_path
    orig_gen = R.cb_gen.generate_image
    try:
        R.HERE = scratch / "engine"
        R.MEDIA = R.HERE / "media" / "shots"
        E.canonical_package_path = lambda sc, ep="Ep1": scratch / "cb-output" / f"{ep}_scene{sc}_production_package.json"
        R._require_confirmed_billing = lambda provider: None
        _write_locations(scratch, scene, episode)
        _write_style(scratch)
        _write_storyboard(scratch, scene, episode)

        def _record_and_write(prompt, refs=None, out=None, **kw):
            GEN_CALLS.append({"prompt": prompt, "refs": refs, "out": out})
            pathlib.Path(out).write_bytes(f"real-bytes-{len(GEN_CALLS)}".encode())
            return out
        R.cb_gen.generate_image = _record_and_write

        print("== 1. Approve/save/continue/navigation cause ZERO generation calls ==")
        GEN_CALLS.clear()
        pkg, path = _write_package(scratch, scene, episode)
        # a plate must be approved first for these read/approve-style calls to exercise real
        # code paths without hitting an earlier, unrelated refusal
        cand = R.MEDIA.parent / f"{episode}_S{scene}_plate_seed.png"
        cand.write_bytes(b"seed-plate")
        rec = {"approved": {"path": str(cand), "hash": R._sha256_file(cand),
                            "inputSignature": R._scenelook_input_signature(scene, episode),
                            "approvedAt": "t", "reviewedBy": "Julian"},
               "candidate": None, "history": []}
        R._save_scenelook_rec(rec, scene, episode)
        # "navigation"/"continue"/"save" have no cb_render entry points at all (there is no
        # generic status/list call that reaches cb_gen) — proven by calling every read-only
        # entry point this module actually exposes and confirming none of them touch cb_gen.
        R.scenelook_status(scene, episode)
        R.lineage_status(pkg, scene, episode)
        R.reassess_keyframe(scene, "S1.SH1", episode)
        R.status(scene, episode, log=lambda *a, **k: None)
        check("scenelook_status/lineage_status/reassess_keyframe/status() never call generate_image",
              len(GEN_CALLS) == 0, GEN_CALLS)
        # "approve" with nothing pending refuses cleanly — still zero generation calls
        try:
            R.approve_scenelook(scene, episode)
        except R.Refused:
            pass
        check("approve_scenelook with no pending candidate never calls generate_image",
              len(GEN_CALLS) == 0, GEN_CALLS)

        print("== 2. Generating S1.SH1 produces ONE S1.SH1 candidate and touches no plate or "
              "other shot ==")
        GEN_CALLS.clear()
        pkg, path = _write_package(scratch, scene, episode)
        plate_before = R._sha256_file(cand)
        R.keyframe_shot(scene, "S1.SH1", episode)
        pkg2 = json.load(open(path))
        led_sh1 = next(e for e in pkg2["continuityLedger"] if e["shotId"] == "S1.SH1")
        led_sh6 = next(e for e in pkg2["continuityLedger"] if e["shotId"] == "S1.SH6")
        check("exactly one generation call fired", len(GEN_CALLS) == 1, GEN_CALLS)
        check("S1.SH1 has a candidate", bool(led_sh1.get("keyframeCandidate")))
        check("S1.SH6's ledger entry is completely untouched", led_sh6 == {"shotId": "S1.SH6", "status": "designed"})
        check("the approved plate file is byte-identical (untouched)",
              R._sha256_file(cand) == plate_before)
        check("the plate's own sidecar record is untouched",
              R.scenelook_status(scene, episode)["approved"]["path"] == str(cand))

        print("== 3. Generating a plate touches NO keyframes ==")
        GEN_CALLS.clear()
        # start clean: reject the SH1 candidate from step 2 so this step's own plate
        # generation is the only thing under test
        R.reject_keyframe(scene, "S1.SH1", "clearing for the next test", episode)
        led_before = json.load(open(path))["continuityLedger"]
        R.generate_scenelook_plate(scene, episode)
        led_after = json.load(open(path))["continuityLedger"]
        check("exactly one generation call fired for the plate", len(GEN_CALLS) == 1, GEN_CALLS)
        check("the production package's ledger is completely untouched by a plate generation",
              led_before == led_after)
        st = R.scenelook_status(scene, episode)
        check("the plate's own new file is a CANDIDATE, not yet approved", st["status"] == "awaiting")
        check("the OLD approved plate is still separately present and untouched",
              st["approved"]["path"] == str(cand) and os.path.exists(cand), st["approved"])
        # clean up: reject this test's own plate candidate so later sections start from the
        # same one approved plate
        R.reject_scenelook(scene, "clearing for the next test", episode)

        print("== 4. A FAILED plate regeneration leaves the approved plate live and approved ==")
        st_before = R.scenelook_status(scene, episode)
        def _boom(*a, **k):
            raise RuntimeError("simulated provider failure — no file produced, no cost incurred")
        R.cb_gen.generate_image = _boom
        try:
            R.generate_scenelook_plate(scene, episode)
            check("a failed generate_scenelook_plate call raises", False, "did not raise")
        except RuntimeError:
            check("a failed generate_scenelook_plate call raises", True)
        R.cb_gen.generate_image = _record_and_write
        st_after = R.scenelook_status(scene, episode)
        check("the approved plate is UNCHANGED after a failed regeneration",
              st_after == st_before, (st_before, st_after))
        check("the approved plate file itself still exists on disk", os.path.exists(cand))
        check("no orphaned candidate was left behind by the failed attempt",
              st_after["candidate"] is None, st_after["candidate"])

        print("== 5. Changing S1.SH6 does NOT invalidate an unchanged S1.SH1 candidate or the "
              "approved Scene Look ==")
        GEN_CALLS.clear()
        pkg, path = _write_package(scratch, scene, episode)
        R.keyframe_shot(scene, "S1.SH1", episode)                 # a fresh, valid SH1 candidate
        R.approve_keyframe(scene, "S1.SH1", episode)
        before = R.reassess_keyframe(scene, "S1.SH1", episode)
        check("SH1's own approval is carry-forward-valid before the SH6 edit",
              before["verdict"] == "carry_forward", before)
        sl_before = R.scenelook_status(scene, episode)
        # THE UNRELATED EDIT: S1.SH6's own storyboard content changes; S1.SH1's does not.
        _write_storyboard(scratch, scene, episode, sh1_marker="v1", sh6_marker="v2-CHANGED")
        after = R.reassess_keyframe(scene, "S1.SH1", episode)
        check("SH1's own approval is STILL carry-forward-valid after an unrelated SH6 edit",
              after["verdict"] == "carry_forward", after)
        sl_after = R.scenelook_status(scene, episode)
        check("the approved Scene Look is unaffected by the SH6 edit",
              sl_after["status"] == "approved" and sl_after["current"] is True, sl_after)
        # and the positive control: SH6's OWN card hash really did change, proving the edit
        # was real and the test isn't passing by accident
        sh6_hash_v1 = hashlib.sha256(json.dumps({"shotId": "S1.SH6", "cameraRelationship": "v1"},
                                                 sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        sh6_hash_v2 = R._live_card_hash("S1.SH6", scene, episode)
        check("SH6's own card hash genuinely changed (the edit was real)", sh6_hash_v1 != sh6_hash_v2)

        print("== 6. Changing S1.SH1's OWN opening composition DOES invalidate its own "
              "candidate/approval ==")
        _write_storyboard(scratch, scene, episode, sh1_marker="v2-SH1-CHANGED", sh6_marker="v2-CHANGED")
        after_own_edit = R.reassess_keyframe(scene, "S1.SH1", episode)
        check("SH1's own edit correctly marks it for regeneration",
              after_own_edit["verdict"] == "regenerate" and "cardHash" in after_own_edit["changed"],
              after_own_edit)
        try:
            R.approve_keyframe(scene, "S1.SH1", episode)
            check("approve_keyframe refuses re-approval after SH1's own edit (no pending "
                  "candidate to approve)", False, "should have refused")
        except R.Refused as e:
            check("approve_keyframe refuses (no candidate pending — the approval already "
                  "on record is simply flagged stale by reassess_keyframe, not silently kept)",
                  "no keyframe candidate" in str(e), str(e))

        print("== 7. Changing the approved plate invalidates DEPENDENT keyframes ==")
        # re-approve a fresh SH1 candidate against the CURRENT (post step-6) storyboard first
        # (no candidate is pending — step 6 only reassessed and confirmed the refusal, it
        # never generated one — so keyframe_shot fires cleanly here)
        R.keyframe_shot(scene, "S1.SH1", episode)
        R.approve_keyframe(scene, "S1.SH1", episode)
        before_plate_change = R.reassess_keyframe(scene, "S1.SH1", episode)
        check("SH1 is carry-forward-valid before the plate changes",
              before_plate_change["verdict"] == "carry_forward", before_plate_change)
        # approve a NEW plate candidate — this changes the approved plate's own hash
        R.generate_scenelook_plate(scene, episode)
        R.approve_scenelook(scene, episode)
        after_plate_change = R.reassess_keyframe(scene, "S1.SH1", episode)
        check("SH1 is now flagged for regeneration once the approved plate itself changed",
              after_plate_change["verdict"] == "regenerate" and
              "sceneLookHash" in after_plate_change["changed"], after_plate_change)

    finally:
        R.HERE, R.MEDIA = orig_here, orig_media
        E.canonical_package_path = orig_pkg_path
        R.cb_gen.generate_image = orig_gen
        shutil.rmtree(scratch, ignore_errors=True)

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} case(s) — {FAILS}")
        sys.exit(1)
    print("ALL PASS ✓ — separated generation actions, non-destructive two-phase lifecycle, "
          "and direct-input lineage all proven against real (scratch) code paths")


if __name__ == "__main__":
    main()
