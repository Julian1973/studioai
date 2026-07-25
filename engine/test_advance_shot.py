#!/usr/bin/env python3
"""test_advance_shot.py — the three-stop loop (Julian's direct ruling, 2026-07-21): proves
advance_shot() actually resolves every mechanical gate (lineage, department freshness,
redesign eligibility) automatically and silently, and only ever stops for the three real
creative moments — storyboard read, keyframe look, clip watch — never spending real money
or auto-approving a keyframe/clip on its own. Reuses test_cb_render_department_gate.py's
own `world`/`_mock_llm` fixtures (same disposable, zero-provider-call isolation) rather
than re-deriving a second copy of that setup.

    pytest test_advance_shot.py -q
"""
import json
import pathlib
import sys
import time

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cb_render as R
import cb_llm
from test_cb_render_department_gate import (
    world, _mock_llm, _build_shot, CFG, _reach_model_limited, _approve_animation,
)


@pytest.fixture(autouse=True)
def _no_real_llm_by_default(monkeypatch):
    """HARD TRIPWIRE (added 2026-07-21 after a real live OpenAI call was accidentally fired
    from an earlier, incompletely-mocked version of this file's own department-resolution
    test): every test in this file refuses any real cb_llm.structured call by default,
    matching test_cb_engine.py's own established _no_llm autouse pattern. A test that
    genuinely needs a department to prepare successfully still calls _mock_llm(monkeypatch)
    itself, same as this whole suite already does — that call simply re-patches structured
    a second time, which cleanly overrides this fixture's own default for the rest of that
    one test. No test may ever again reach a real provider through a gap in its own setup."""
    def _boom(*a, **k):
        raise AssertionError("TRIPWIRE: a real cb_llm.structured call was attempted — "
                              "this test is missing its own _mock_llm(monkeypatch) call")
    monkeypatch.setattr(cb_llm, "structured", _boom)


def _skip_lineage(monkeypatch):
    """Isolates the department/redesign/keyframe logic from the (separately, already
    tested) lineage auto-recompile step — advance_shot's own lineage branch is proven on
    its own in test_advance_shot_auto_recompiles_a_stale_lineage_from_an_approved_storyboard
    below, against a real storyboard fixture; every other test here targets what happens
    ONCE lineage is already current."""
    monkeypatch.setattr(R, "lineage_status", lambda pkg, scene, episode="Ep1":
                        {"current": True, "packageStoryboardMd5": "x",
                         "liveStoryboardMd5": "x", "packageRevision": pkg.get("revision")})


def test_advance_shot_from_scratch_reaches_the_keyframe_stop(world, monkeypatch):
    """Nothing is prepared or approved yet. advance_shot must, entirely on its own: prepare
    and approve Cinematography, generate the keyframe, and stop there — never auto-approving
    the keyframe, and never touching Voice/Animation yet, since Animation's own real
    prerequisite (_anchor_for) hard-requires an APPROVED keyframe for an opener shot, which
    only a human can grant. Once the keyframe is approved, a second call must then resolve
    Voice (direction + the real take) and Animation on its own and land at ready-to-render."""
    calls, tmp, path = world
    _skip_lineage(monkeypatch)
    _mock_llm(monkeypatch)
    result = R.advance_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    assert result["status"] == "keyframe-ready-for-your-eye"
    assert result["path"]
    assert len(calls["image"]) == 1                     # exactly one keyframe generated
    pkg = json.load(open(path))
    led = R._ledger(pkg, "1.B1.S1")
    appr = led["departmentWork"]["cinematography"]["approved"]
    assert appr and appr["outcome"] == "approved"
    # voice/animation are genuinely untouched — the keyframe blocks them, not a bug
    assert "voice" not in led.get("departmentWork", {})
    assert "animation" not in led.get("departmentWork", {})
    assert led["keyframeCandidate"]["path"] == result["path"]
    # the keyframe itself is NOT approved — that stays the human's own call
    assert not (led.get("keyframeApproval") or {}).get("approved")

    # once Julian approves the keyframe, the SAME call must resolve voice + animation and
    # land at the final mechanical gate, all on its own, with zero further human input.
    R.approve_keyframe("9", "1.B1.S1", "EpT", reviewed_by="Julian", log=lambda *a, **k: None)
    second = R.advance_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    assert second["status"] == "ready-to-render"
    pkg = json.load(open(path))
    led = R._ledger(pkg, "1.B1.S1")
    for stage in ("voice", "animation"):
        appr = led["departmentWork"][stage]["approved"]
        assert appr and appr["outcome"] == "approved"
    assert (led.get("voiceApproval") or {}).get("approved")
    assert len(calls["voice"]) == 1                      # exactly one real voice take fired


def test_advance_shot_never_regenerates_a_keyframe_already_pending(world, monkeypatch):
    """A second call while a keyframe candidate is already awaiting a decision must return
    the SAME pending candidate, never fire a second real generation call."""
    calls, tmp, path = world
    _skip_lineage(monkeypatch)
    _mock_llm(monkeypatch)
    first = R.advance_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    second = R.advance_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    assert second["status"] == "keyframe-ready-for-your-eye"
    assert second["path"] == first["path"]
    assert len(calls["image"]) == 1                      # still exactly one


def test_advance_shot_stops_at_a_pending_clip_batch_without_touching_it(world, monkeypatch):
    """A shot already sitting at candidates-pending (a real batch fired earlier) must be
    reported as stop three and left completely untouched — advance_shot never fires or
    resolves it on its own."""
    calls, tmp, path = world
    _skip_lineage(monkeypatch)
    _mock_llm(monkeypatch)
    pkg = json.load(open(path))
    led = R._ledger(pkg, "1.B1.S1")
    led["status"] = "candidates-pending"
    led["candidatePaths"] = ["/fake/c1.mp4", "/fake/c2.mp4"]
    before = json.dumps(led, sort_keys=True)
    json.dump(pkg, open(path, "w"))
    result = R.advance_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    assert result["status"] == "clip-ready-for-your-eye"
    assert result["candidatePaths"] == ["/fake/c1.mp4", "/fake/c2.mp4"]
    after = json.dumps(R._ledger(json.load(open(path)), "1.B1.S1"), sort_keys=True)
    assert after == before                                # byte-for-byte untouched
    assert calls["image"] == [] and calls["video"] == [] and calls["voice"] == []


def test_advance_shot_reports_needs_new_direction_when_genuinely_ineligible(world, monkeypatch):
    """A shot that's model-limited on the SAME direction as its last rejected batch must
    never auto-clear — that would silently retry an attempt already proven not to work.
    advance_shot must report it honestly and leave the ledger untouched."""
    calls, tmp, path = world
    _skip_lineage(monkeypatch)
    _reach_model_limited(monkeypatch, path)                # real two-batch rejection cycle
    _mock_llm(monkeypatch)
    before = json.dumps(R._ledger(json.load(open(path)), "1.B1.S1"), sort_keys=True)
    result = R.advance_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    assert result["status"] == "needs-new-direction"
    assert result["blockers"]
    after = json.dumps(R._ledger(json.load(open(path)), "1.B1.S1"), sort_keys=True)
    assert after == before


def test_advance_shot_auto_clears_model_limited_once_genuinely_eligible(world, monkeypatch):
    """Once the real Animation Direction has genuinely changed since the last rejected
    batch, advance_shot must clear the block itself — no separate manual "acknowledge
    redesign" click — and continue toward the next real stop. Deliberately does NOT mutate
    dialogueLines the way the sibling redesign-eligibility tests in
    test_cb_render_department_gate.py do — the redesign signature already changes purely
    from _approve_animation's own different prompt text (proven there via
    animationPromptSha256), and mutating dialogueLines here would also stale Voice's own
    direction, which advance_shot now correctly tries to re-prepare — something this
    shared _mock_llm fixture's hardcoded VoiceDirection response can't satisfy for changed
    dialogue (it always returns "Nailed it." regardless of the locked text). Voice/keyframe/
    cinematography all stay untouched and current from _seed_animation_prereqs."""
    calls, tmp, path = world
    _skip_lineage(monkeypatch)
    _reach_model_limited(monkeypatch, path)
    # GOLD BUILD (2026-07-24): the re-approved direction must BE the formula, carrying the
    # shot's own (unchanged) locked line inline verbatim — different ACTION text is what
    # genuinely changes the redesign signature here, never the dialogue.
    from test_cb_render_department_gate import _formula_prompt
    _approve_animation(monkeypatch, _formula_prompt(
        "genuinely different approved action, slowed into a held redesign closing beat, "
        "near-still"), shot_id="1.B1.S1")
    _mock_llm(monkeypatch)
    result = R.advance_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    assert result["status"] != "needs-new-direction"
    led = R._ledger(json.load(open(path)), "1.B1.S1")
    assert led["status"] != "model-limited"
    assert len(led["redesignAcknowledgements"]) == 1
    # the previous rejection history is untouched — nothing here erases it
    assert len(led["rejections"]) == R.MAX_BATCH_ATTEMPTS


def test_advance_shot_never_clears_model_limited_off_a_same_call_direction_refresh(
        world, monkeypatch):
    """THE SAME-CALL SIGNATURE BYPASS (2026-07-22, Julian's full-audit directive): a real bug
    found live — redesign_eligibility compares the last rejected batch's signature against a
    freshly-computed "current" one, but if _auto_direction refreshes+auto-approves Animation
    Direction EARLIER IN THE SAME advance_shot() CALL (steps 2/4/5, before step 6 checks
    eligibility), that "current" signature is partly a byproduct of this very call, not
    independent evidence anything genuinely changed since the rejection. Unlike the sibling
    test above (which pre-approves the new direction OUTSIDE the call via _approve_animation),
    this test invalidates the shot's OWN currently-approved Animation Direction's stored
    sourceHash directly — forcing _auto_direction("animation") to discover staleness and
    refresh it FOR THE FIRST TIME from inside advance_shot's own call, exactly the race the
    fix closes. Proves: (1) the recursion path actually fires (the log names it explicitly),
    (2) it terminates in exactly one recursion, never a loop, (3) the shot still resolves
    correctly once evaluated against settled, post-refresh state."""
    calls, tmp, path = world
    _skip_lineage(monkeypatch)
    _reach_model_limited(monkeypatch, path)          # animation direction is approved+current
    # Invalidate ONLY animation's stored freshness signature — simulates "this direction was
    # never actually stale until the instant advance_shot itself looks at it," the same-call
    # scenario _approve_animation's own external pre-call in the sibling test bypasses.
    pkg = json.load(open(path))
    led = R._ledger(pkg, "1.B1.S1")
    led["departmentWork"]["animation"]["approved"]["sourceHash"] = "deliberately-stale-hash"
    json.dump(pkg, open(path, "w"))
    from test_cb_render_department_gate import _formula_prompt
    _mock_llm(monkeypatch, animation_prompt=_formula_prompt(
        "genuinely different freshly recompiled action, slowed into a held closing beat, "
        "near-still, reflecting real change"))
    logs = []
    result = R.advance_shot("9", "1.B1.S1", "EpT", log=logs.append)
    recheck_lines = [m for m in logs if "re-checking the model-limited block" in m]
    assert len(recheck_lines) == 1, (
        "the same-call refresh must trigger exactly one settled-state recheck, never zero "
        "(the bypass) and never more than one (a loop)")
    refresh_lines = [m for m in logs if "animation direction refreshed automatically" in m]
    assert len(refresh_lines) == 1, (
        "the direction must refresh exactly once — the recursive second pass must find it "
        "already current and refresh nothing further")
    assert result["status"] != "needs-new-direction"
    led = R._ledger(json.load(open(path)), "1.B1.S1")
    assert led["status"] != "model-limited"
    assert len(led["redesignAcknowledgements"]) == 1


def test_advance_shot_makes_zero_provider_calls_when_it_only_needs_a_human(world, monkeypatch):
    """Reaching a genuine stop must never itself cost anything — proven directly, not
    inferred, by patching every provider boundary to raise on any call."""
    calls, tmp, path = world
    _skip_lineage(monkeypatch)
    _mock_llm(monkeypatch)
    pkg = json.load(open(path))
    led = R._ledger(pkg, "1.B1.S1")
    led["status"] = "candidates-pending"
    led["candidatePaths"] = ["/fake/c1.mp4"]
    json.dump(pkg, open(path, "w"))
    result = R.advance_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    assert result["status"] == "clip-ready-for-your-eye"
    assert calls["image"] == [] and calls["video"] == [] and calls["voice"] == []


# ── the one real, un-isolated proof: lineage genuinely auto-recompiles ──────────────────
def test_advance_shot_auto_recompiles_a_stale_lineage_from_an_approved_storyboard(
        tmp_path, monkeypatch):
    """The exact real-world case this whole ruling exists to close: a package built from a
    superseded storyboard used to REFUSE outright (_require_current_lineage). advance_shot
    must instead recompile automatically, using the real cb_handover.promote_to_canonical
    route — never a hand-edited package — and continue past it without asking a human to
    do anything, since re-approving an already-approved storyboard is not a real decision."""
    import cb_handover as H
    import cb_engine
    from test_cb_handover import _canonical_env
    engine = tmp_path / "engine"
    (engine / "media" / "shots").mkdir(parents=True)
    (engine / "media" / "archive" / "shots_rejected").mkdir(parents=True)
    (engine / "media" / "refs").mkdir(parents=True)
    monkeypatch.setattr(R, "HERE", engine)
    monkeypatch.setattr(R, "MEDIA", engine / "media" / "shots")
    for c in CFG.values():
        (engine / c["anchor"]).write_bytes(b"REF")
    monkeypatch.setattr(R, "_characters_cfg", lambda: CFG)
    monkeypatch.setattr(R, "_require_current_scenelook", lambda scene, episode="Ep1": None)
    monkeypatch.setattr(R, "_require_confirmed_billing", lambda provider: None)
    monkeypatch.setattr(R, "_fresh_validation", lambda pkg, episode: None)

    sb_p, pkg_dir = _canonical_env(tmp_path, monkeypatch)
    monkeypatch.setattr(R, "_storyboard_path", lambda scene, episode="Ep1": sb_p)
    pkg_path = pkg_dir / "Ep1_scene1_production_package.json"

    # a genuinely STALE package: recorded storyboard md5 does not match the live file.
    stale = {"episode": "Ep1", "sceneNumber": "1", "revision": 6,
             "sourceStoryboard": {"path": str(sb_p), "md5": "0000000000stale0000000000"},
             "shots": [{"shotId": "S1.SH1", "performanceAssignment": "OLD"}],
             "continuityLedger": [{"shotId": "S1.SH1"}], "validation": {"passed": True}}
    json.dump(stale, open(pkg_path, "w"))
    monkeypatch.setattr(R, "load_pkg", lambda scene, episode="Ep1": (json.load(open(pkg_path)), pkg_path))
    monkeypatch.setattr(R, "_require_confirmed_billing", lambda provider: None)

    lin_before = R.lineage_status(json.load(open(pkg_path)), "1", "Ep1")
    assert lin_before["current"] is False                 # genuinely stale, confirmed

    result = R.advance_shot("1", "S1.SH1", "Ep1", log=lambda *a, **k: None)
    # it must have moved PAST the lineage refusal on its own — never "needs-story-review"
    # for an already-approved storyboard.
    assert result["status"] != "needs-story-review"
    after = json.load(open(pkg_path))
    assert after["revision"] == 7                          # a real promotion happened
    lin_after = R.lineage_status(after, "1", "Ep1")
    assert lin_after["current"] is True


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
