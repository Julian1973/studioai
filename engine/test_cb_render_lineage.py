#!/usr/bin/env python3
"""test_cb_render_lineage.py — proves the state-integrity checkpoint (Julian, 2026-07-17)
AND its 2026-07-18 correction: lineage_status() itself is unchanged and still a truthful,
whole-package provenance READ — but it is no longer a keyframe-firing GATE. Keyframe
validity is now direct-input-signature-based (cb_render._keyframe_input_signature), so an
unrelated shot's edit (which bumps the package revision / storyboard md5) can never
invalidate a DIFFERENT shot's own candidate or approval. See test_cb_render_generation_
safety.py for the full 2026-07-18 production-safety + direct-input-lineage proof set.

Everything runs against a scratch package in a temp directory (cb_render.HERE/MEDIA
monkeypatched) — zero real data touched, zero cb_gen calls (any accidental call is made to
raise, proving zero spend).

Direct-script harness, matching this codebase's own test_gate_cascade.py/test_cb_preflight.py
convention: python3 test_cb_render_lineage.py; prints PASS/FAIL per case, exits 1 on any fail.
"""
import os, sys, json, shutil, tempfile, hashlib, pathlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cb_render as R
import cb_engine as E

FAILS = []


def check(name, cond, detail=""):
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
        FAILS.append(name)


def _scratch():
    d = pathlib.Path(tempfile.mkdtemp(prefix="cb_render_lineage_"))
    (d / "cb-output" / "creative").mkdir(parents=True)
    (d / "engine" / "media" / "shots").mkdir(parents=True)
    return d


def _write_storyboard(root, scene, episode, shot_id="S1.SH1", marker="v1"):
    p = root / "cb-output" / "creative" / f"{episode}_scene{scene}_storyboard.json"
    sb = {"marker": marker, "shots": [{"shotId": shot_id, "marker": marker}]}
    p.write_text(json.dumps(sb, sort_keys=True))
    return hashlib.md5(p.read_bytes()).hexdigest()


def _card_hash(root, scene, episode, shot_id="S1.SH1"):
    return R._live_card_hash(shot_id, scene, episode)


def _write_package(root, scene, episode, storyboard_md5, revision=1, extra_ledger=None,
                    shot_id="S1.SH1", card_hash=None):
    pkg = {
        "episode": episode, "sceneNumber": str(scene), "revision": revision,
        "validation": {"passed": True},
        "sourceStoryboard": {"path": "n/a", "md5": storyboard_md5,
                             "creativeCardHashes": {shot_id: card_hash} if card_hash else {}},
        "shots": [{"shotId": shot_id, "sourceType": "opener", "beatCode": "1.B1",
                   "keyframePrompt": "a prompt", "keyframeReferenceSlots": {},
                   "referenceSlots": {}, "durationSec": 5}],
        "continuityLedger": [dict({"shotId": shot_id, "status": "designed"},
                                   **(extra_ledger or {}))],
    }
    p = root / "cb-output" / f"{episode}_scene{scene}_production_package.json"
    p.write_text(json.dumps(pkg, indent=1))
    return pkg, p


def main():
    scratch = _scratch()
    scene, episode = "TESTLINEAGE", "EpX"
    orig_here, orig_media = R.HERE, R.MEDIA
    orig_pkg_path = E.canonical_package_path
    try:
        R.HERE = scratch / "engine"
        R.MEDIA = R.HERE / "media" / "shots"
        E.canonical_package_path = lambda sc, ep="Ep1": scratch / "cb-output" / f"{ep}_scene{sc}_production_package.json"
        # cb_gen.generate_image must NEVER be called by any test below — any accidental
        # invocation proves an unauthorized spend, so make it raise loudly instead of a
        # silent no-op that would hide the bug.
        R.cb_gen.generate_image = lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("cb_gen.generate_image was called — this would have spent real money"))
        R._require_confirmed_billing = lambda provider: None   # isolate lineage/lifecycle tests
        # A scene look must read as APPROVED+current for keyframe_shot's own gate to be
        # reached at all in these tests — stub it, since Scene Look's own lifecycle has its
        # own dedicated proofs in test_cb_render_generation_safety.py.
        R._require_current_scenelook = lambda sc, ep="Ep1": None
        R._keyframe_input_signature = lambda pkg, shot, sc, ep="Ep1": {"cardHash": "stub-sig"}

        print("== lineage_status() is unchanged — still a truthful provenance READ ==")
        live_md5 = _write_storyboard(scratch, scene, episode, marker="current-content")
        pkg, path = _write_package(scratch, scene, episode, storyboard_md5=live_md5, revision=7)
        lin = R.lineage_status(pkg, scene, episode)
        check("current lineage reports current=True", lin["current"] is True, lin)

        stale_pkg, _ = _write_package(scratch, scene, episode, storyboard_md5="deadbeef" * 4, revision=6)
        lin2 = R.lineage_status(stale_pkg, scene, episode)
        check("mismatched md5 reports current=False", lin2["current"] is False, lin2)

        no_hash_pkg = dict(pkg); no_hash_pkg["sourceStoryboard"] = {}
        lin3 = R.lineage_status(no_hash_pkg, scene, episode)
        check("missing package md5 is never silently current", lin3["current"] is False, lin3)

        print("== keyframe_shot() NO LONGER refuses on a stale whole-package/storyboard md5 ==")
        # (2026-07-18 correction): a package built from a superseded storyboard version used
        # to hard-refuse EVERY keyframe fire, even for a shot whose OWN content never changed
        # — the exact blanket-invalidation bug this correction removes. lineage_status still
        # truthfully reports "stale" above; it is simply no longer a firing gate. Proven here
        # by confirming the call reaches cb_gen.generate_image (which is stubbed to raise,
        # proving zero real spend across this whole file) rather than being refused earlier
        # for "superseded storyboard" — the exact refusal this correction removes.
        pkg, path = _write_package(scratch, scene, episode, storyboard_md5="deadbeef" * 4, revision=6)
        try:
            R.keyframe_shot(scene, "S1.SH1", episode)
            check("keyframe_shot reaches generation despite a stale package/storyboard md5",
                  False, "should have hit the generate_image stub")
        except AssertionError as e:
            check("keyframe_shot reaches generation despite a stale package/storyboard md5",
                  "would have spent real money" in str(e), str(e))
        except R.Refused as e:
            check("keyframe_shot reaches generation despite a stale package/storyboard md5",
                  False, f"refused before reaching generation: {e}")

        print("== keyframe_shot() still refuses to regenerate over an undecided candidate ==")
        pkg, path = _write_package(scratch, scene, episode, storyboard_md5=live_md5, revision=7,
                                    extra_ledger={"keyframeCandidate": {"path": "x", "generatedAt": "t",
                                                                          "inputSignature": {"a": 1}}})
        try:
            R.keyframe_shot(scene, "S1.SH1", episode)
            check("keyframe_shot refuses over a pending decision", False, "did not raise")
        except R.Refused as e:
            check("keyframe_shot refuses over a pending decision", "awaiting a decision" in str(e), str(e))

        print("== _anchor_for(): a file's existence alone can never anchor a fire (proof #1) ==")
        cand_file = R.MEDIA / f"{episode}_S1.SH1_keyframe_candidate_test.png"
        cand_file.write_bytes(b"fake-png-bytes")
        pkg, path = _write_package(scratch, scene, episode, storyboard_md5=live_md5, revision=7,
                                    extra_ledger={"keyframeCandidate": {"path": str(cand_file), "generatedAt": "t",
                                                                          "inputSignature": {"cardHash": "stub-sig"}}})
        shot = pkg["shots"][0]
        try:
            R._anchor_for(pkg, shot)
            check("an unapproved-but-existing file cannot anchor", False, "did not raise")
        except R.Refused as e:
            check("an unapproved-but-existing file cannot anchor", "no APPROVED keyframe" in str(e), str(e))

        print("== approve_keyframe() (direct-input signature, not storyboard md5) ==")
        try:
            path_out = R.approve_keyframe(scene, "S1.SH1", episode, reviewed_by="TestReviewer")
            pkg2 = json.load(open(path))
            led2 = pkg2["continuityLedger"][0]
            check("approve records approved=True", led2["keyframeApproval"]["approved"] is True)
            check("approve records reviewedBy", led2["keyframeApproval"]["reviewedBy"] == "TestReviewer")
            check("approve records the inputSignature, no packageRevision tie",
                  "inputSignature" in led2["keyframeApproval"] and
                  "packageRevision" not in led2["keyframeApproval"], led2["keyframeApproval"])
            # NOW the anchor must succeed — the immediate, valid successor unlocks (proof #5)
            R._anchor_for(pkg2, shot)
            check("an approved candidate DOES anchor a fire", True)
        except Exception as e:
            check("approve_keyframe succeeds and anchors", False, repr(e))

        print("== _anchor_for() NO LONGER refuses an approval merely because the package "
              "revision moved on (2026-07-18 correction — this is the whole point) ==")
        pkg3, path3 = _write_package(scratch, scene, episode, storyboard_md5=live_md5, revision=8,
                                      extra_ledger={"keyframeApproval": {"approved": True, "path": str(cand_file),
                                                                           "inputSignature": {"a": 1}}})
        try:
            anchor = R._anchor_for(pkg3, pkg3["shots"][0])
            check("a revision-8 package can still anchor off an older approval",
                  anchor == str(cand_file), anchor)
        except R.Refused as e:
            check("a revision-8 package can still anchor off an older approval", False, str(e))

        print("== reject_keyframe() is atomic (proof #2) and never touches an existing approval ==")
        cand_file2 = R.MEDIA / f"{episode}_S1.SH1_keyframe_candidate_test2.png"
        cand_file2.write_bytes(b"the-rejected-image-bytes")
        original_bytes = cand_file2.read_bytes()
        approved_file = R.MEDIA / f"{episode}_S1.SH1_keyframe_approved_test.png"
        approved_file.write_bytes(b"the-still-approved-image")
        pkg, path = _write_package(scratch, scene, episode, storyboard_md5=live_md5, revision=9,
                                    extra_ledger={
                                        "keyframeCandidate": {"path": str(cand_file2), "generatedAt": "t",
                                                              "inputSignature": {"a": 2}},
                                        "keyframeApproval": {"approved": True, "path": str(approved_file),
                                                              "inputSignature": {"a": 1}},
                                        "keyframePath": str(approved_file)})
        archived_rel = R.reject_keyframe(scene, "S1.SH1", "the geometry drifted to a wide vista", episode,
                                          reviewed_by="TestReviewer")
        pkg4 = json.load(open(path))
        led4 = pkg4["continuityLedger"][0]
        archived_abs = R.HERE / archived_rel
        check("rejection clears the live-path duplicate", not cand_file2.exists())
        check("rejection preserves the exact bytes in history", archived_abs.exists() and
              archived_abs.read_bytes() == original_bytes)
        check("rejection preserves the reason", led4["keyframeRejected"]["reason"] == "the geometry drifted to a wide vista")
        check("rejection clears the current candidate position", led4.get("keyframeCandidate") is None)
        check("rejection NEVER touches a pre-existing approval (item 2's own principle)",
              led4.get("keyframeApproval", {}).get("path") == str(approved_file) and
              approved_file.exists(), led4.get("keyframeApproval"))

        print("== reject_keyframe() requires a real reason ==")
        pkg, path = _write_package(scratch, scene, episode, storyboard_md5=live_md5, revision=10,
                                    extra_ledger={"keyframeCandidate": {"path": str(cand_file2), "generatedAt": "t",
                                                                          "inputSignature": {"a": 1}}})
        try:
            R.reject_keyframe(scene, "S1.SH1", "   ", episode)
            check("reject_keyframe refuses a blank reason", False, "did not raise")
        except R.Refused:
            check("reject_keyframe refuses a blank reason", True)

        print("== approve_keyframe() refuses a candidate whose OWN direct inputs have since "
              "changed (not the whole storyboard) ==")
        R._keyframe_input_signature = lambda pkg, shot, sc, ep="Ep1": {"cardHash": "a-different-value-now"}
        pkg, path = _write_package(scratch, scene, episode, storyboard_md5=live_md5, revision=11,
                                    extra_ledger={"keyframeCandidate": {"path": str(cand_file2), "generatedAt": "t",
                                                                          "inputSignature": {"cardHash": "old-value"}}})
        try:
            R.approve_keyframe(scene, "S1.SH1", episode)
            check("approve refuses a candidate whose own inputs changed", False, "did not raise")
        except R.Refused as e:
            check("approve refuses a candidate whose own inputs changed", "cardHash" in str(e), str(e))

    finally:
        R.HERE, R.MEDIA = orig_here, orig_media
        E.canonical_package_path = orig_pkg_path
        shutil.rmtree(scratch, ignore_errors=True)

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} case(s) — {FAILS}")
        sys.exit(1)
    print("ALL PASS ✓ — lineage stays a truthful provenance read; keyframe validity is now "
          "direct-input-signature-based, never a package-revision/storyboard-md5 gate")


if __name__ == "__main__":
    main()
