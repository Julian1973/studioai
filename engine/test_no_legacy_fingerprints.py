#!/usr/bin/env python3
"""test_no_legacy_fingerprints.py — Julian's destructive-cutover order (2026-07-16, §6):
the build FAILS if executable source or active prompt data ever again contains a legacy
prompt fingerprint, and the old Studio routes stay GONE.

Scope: executable source (engine/*.py, cb-studio/*.py, cb-studio/app.html) and the ACTIVE
production package's compiled prompts. Immutable historic evidence is excluded by design:
archives, backups, the validation freeze, media sidecars, the beat package (canon dialogue
ground truth — data, not a prompt template) and cost/usage records.

    pytest test_no_legacy_fingerprints.py -q
"""
import json
import pathlib
import re

import pytest



HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

# Legacy prompt fingerprints (§6): the three forensic strings, the timeline mega-prompt
# headings, and the former long "Negative:" builder's construction.
#
# "Pixar-caliber" RETIRED 2026-07-21: it was banned here because a hardcoded DUPLICATE of
# the show's style law used to live directly in prompt-building source — real duplication,
# the destructive cutover's own target. cb_engine._style_law_text() (built the same night
# this line was retired, Julian's own techhalla-example comparison) now reads that law from
# its ONE canonical file (shows/crystal-bears/laws/style.txt) at compile time, every time,
# never a hardcoded copy — so this phrase legitimately, deliberately reaches both executable
# source (this file's own comments, unavoidably, since they have to name what they test) and
# every real compiled prompt now. A blunt string match can't tell "hardcoded duplicate" from
# "the one true file, read correctly" apart — the fix is a real source-of-truth change, not
# a regression this fingerprint should keep flagging.
FINGERPRINTS = [
    "camera already waiting at the leaf",
    "no leaf hit as the final image",
    "crash-lands into pride",
    re.compile(r"\b0[–-]5s\b"), re.compile(r"\b5[–-]10s\b"), re.compile(r"\b10[–-]15s\b"),
    '"Negative: "',
]
THIS_FILE = pathlib.Path(__file__).name


# DORMANT-SAFE WHEN THE SCENE IS RESET (2026-07-26) — see _live_package.py. These
# assertions need real production data; when Scene 1 has been archived for a clean
# run they skip honestly rather than erroring as if the engine were broken.
from _live_package import require_live_package
# NOT a module-level skip (corrected 2026-07-26). Blanketing this file silenced FOUR pure
# source scans that need no production data at all — including the ONLY assertion that
# cb_director.py and 21 other legacy modules stay absent and unimportable, and the ONLY
# proof that exactly one Seedance caller exists. They matter MOST at clean zero, which is
# exactly when the blanket switched them off. Only the one test that reads a live package
# is guarded, at its own def below.
_needs_live_package = require_live_package()

def _executable_sources():
    """Production executable source. test_*.py files are the fingerprint POLICE — they must
    name the fingerprints to assert their absence — so they are guards, not generators, and
    are excluded from the scan (this test itself proves the guards exist)."""
    files = sorted(f for f in HERE.glob("*.py") if not f.name.startswith("test_"))
    files += [ROOT / "cb-studio" / "serve.py", ROOT / "cb-studio" / "app.html"]
    return [f for f in files if f.exists()]


def test_no_legacy_fingerprint_in_executable_source():
    hits = []
    for f in _executable_sources():
        text = f.read_text(errors="replace")
        for fp in FINGERPRINTS:
            found = (fp.search(text) if hasattr(fp, "search") else (fp in text))
            if found:
                hits.append(f"{f.name}: {getattr(fp, 'pattern', fp)}")
    assert not hits, "legacy prompt fingerprints in executable source:\n" + "\n".join(hits)


@_needs_live_package
def test_no_legacy_fingerprint_in_active_shot_prompts():
    pkg = json.load(open(ROOT / "cb-output" / "Ep1_scene1_production_package.json"))
    hits = []
    for s in pkg["shots"]:
        for field in ("seedancePrompt", "keyframePrompt"):
            text = s.get(field) or ""
            for fp in FINGERPRINTS:
                found = (fp.search(text) if hasattr(fp, "search") else (fp in text))
                if found:
                    hits.append(f"{s['shotId']}.{field}: {getattr(fp, 'pattern', fp)}")
    assert not hits, "legacy fingerprints in ACTIVE prompts:\n" + "\n".join(hits)


def test_legacy_modules_cannot_execute():
    """§3/§7: the old prompt generator and render loop are GONE from the active tree —
    importing any of them fails. Recoverable only through the pre-legacy-pipeline-removal tag."""
    for mod in ("cb_segprompt", "cb_beats", "cb_replicator", "cb_seedance", "cb_director_pass",
                 "cb_previz", "cb_scene", "cb_prompts", "cb_qa", "cb_pipeline", "cb_retake",
                 "cb_voice", "cb_address", "cb_golden", "cb_craft", "cb_preflight",
                 "cb_continuity", "cb_context", "cb_director", "cb_director_eye",
                 "cb_director_schemas", "cb_writer", "cb_script", "beat_preview", "kf_preview"):
        assert not (HERE / f"{mod}.py").exists(), f"legacy module still present: {mod}.py"
        with pytest.raises(ImportError):
            __import__(mod)


def test_legacy_studio_routes_are_gone_never_redirected():
    """§6: every old route returns 410 GONE via the single gate — serve.py contains no
    legacy handler and no redirect to another generator."""
    src = (ROOT / "cb-studio" / "serve.py").read_text()
    assert "LEGACY_GONE_ROUTES" in src and '"error": "GONE' in src
    for route in ("/api/fire", "/api/regen", "/api/render-beat", "/api/gen-keyframe",
                   "/api/beat-prompt", "/api/relay-approve", "/api/director-eye"):
        assert route in src.split("LEGACY_GONE_ROUTES")[1].split("]")[0], route
        # no handler block remains — only the gate list and the removal comment mention it
        handlers = [l for l in src.splitlines()
                    if f'self.path == "{route}"' in l or f'self.path.startswith("{route}' in l]
        assert not handlers, f"legacy handler still present for {route}"
    assert "Location:" not in src or "redirect" not in src.lower().split("legacy_gone")[0][-500:]


def test_single_seedance_call_graph():
    """§5/§7: every call site of the Seedance provider adapter lives in cb_render, and only ONE
    of them can produce an approvable take.

    THE INVARIANT, RESTATED — NOT LOOSENED (2026-07-27). This asserted a COUNT of one caller.
    A count was only ever a proxy for the thing that matters: that nothing can spend and hand
    back something approvable without disclosure -> sealed envelope -> single-use token.

    Julian asked for five authors' prompts for the same shot to be rendered so he could judge
    the footage. That needs a real call with the shot's own references, and it is not a take.
    A test harness could have passed cb_gen's route sentinel itself and rendered immediately —
    and the guard would have had a permanent hole in it, reusable by anything. The call was put
    in cb_render instead, where the rule already points.

    So the count is replaced by the two guarantees underneath it, both asserted directly:
      1. EVERY caller is in cb_render.py — no module outside it may reach the adapter.
      2. The comparison caller CANNOT PRODUCE A TAKE. It never writes the ledger, the batch,
         the candidate paths or any approval, so nothing it renders can be approved, harvested
         or shipped. Only fire_shot's path does that, and it is unchanged.
    That is strictly stronger than counting: a second production path named something else
    would have passed the old count check by being the only one, and fails this one."""
    callers = []
    for f in _executable_sources():
        if f.suffix != ".py" or f.name == "cb_gen.py":
            continue
        for i, line in enumerate(f.read_text().splitlines(), 1):
            code = line.split("#")[0]
            if "cb_gen.generate_video_seedance" in code:      # a real adapter CALL, not prose
                callers.append(f"{f.name}:{i}")
    assert callers, "the Seedance adapter has no caller at all — the render path is broken"
    assert all(c.startswith("cb_render.py") for c in callers), (
        f"the Seedance adapter may only be called from cb_render: {callers}")
    assert len(callers) <= 2, (
        f"more call sites than the production fire plus the one comparison route: {callers}")

    src = (HERE / "cb_render.py").read_text()
    if len(callers) == 2:
        # The second caller is only tolerable while it provably cannot make a take.
        i = src.index("def fire_comparison_clip(")
        body = src[i:src.index("\ndef ", i + 10)]
        assert "cb_gen.generate_video_seedance_ref" in body, (
            "the second adapter call is somewhere other than the comparison route")
        # WRITES are the risk, not reads. The route legitimately READS the shot's own approved
        # references and voice path — that is the whole point, so the comparison uses the same
        # inputs as a real fire. What it must never do is WRITE production state back.
        import re as _re
        code = "\n".join(l.split("#")[0] for l in body.splitlines())
        writes = _re.findall(
            r"""(_save\s*\(|led\s*\[[^\]]+\]\s*=|led\.update\s*\(|led\.setdefault\s*\(|"""
            r"""\bcandidatePaths\b\s*=|\bbatchId\b\s*=|approve\w*\s*\()""", code)
        assert not writes, (
            f"the comparison route WRITES production state {sorted(set(writes))} — it could "
            f"produce something approvable, which is exactly what this test exists to stop")
        assert "isTake" in body and "False" in body, (
            "the comparison route no longer records that its output is not a take")

    gen = (HERE / "cb_gen.py").read_text()
    assert "_require_production_route" in gen and '_AUTHORIZED_PRODUCTION_ROUTE = "cb_render"' in gen


if __name__ == "__main__":
    import subprocess, sys
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))


def test_exactly_one_storyboard_author():
    """ONE DIRECTOR (2026-07-26, Julian: "do gap 5 now").

    cb_engine used to carry a second, complete storyboard author — design_scene /
    compile_scene_package / repair_package — that wrote the SAME canonical production package
    cb_handover writes, from ONE hardcoded LLM prompt, with no show bible, no taste canon, no
    exemplars, no SKILL contract, no Showrunner and no review. It had zero real callers and ran
    from the CLI anyway.

    Two engines that can both author a storyboard is the defect class that has cost this
    project the most: the v1/v2 assemblers, the retired beat pipeline. This test is the guard.
    cb_creative is the only director; cb_engine is the contract, compiler and validator."""
    import cb_engine
    for name in ("design_scene", "compile_scene_package", "repair_package",
                 "_design_mind", "_design_user_prompt", "auto_repair_abstract_directions"):
        assert not hasattr(cb_engine, name), (
            f"cb_engine.{name} is back — a second storyboard author has been reintroduced. "
            f"cb_creative is the only director.")

    # ...and the live consumers must still have everything they import from it.
    for name in ("Shot", "SceneShotList", "DirectorStatement", "ContinuityState",
                 "CharacterState", "DialogueLine", "PhysicalStaging",
                 "MIN_SHOT_SEC", "MAX_SHOT_SEC", "canonical_package_path",
                 "compile_shot_contract", "compile_keyframe_prompt", "compile_audio_brief",
                 "validate_scene_design", "hard_constraints", "ending_requires_hold",
                 "clip_owner_of"):
        assert hasattr(cb_engine, name), (
            f"cb_engine.{name} is missing — the deletion took a live consumer's symbol with it")

    # nobody may call the deleted entry points, in any file, ever again
    import pathlib, re
    root = pathlib.Path(__file__).resolve().parent.parent
    for py in list((root / "engine").glob("*.py")) + list((root / "cb-studio").glob("*.py")):
        if py.name in ("test_no_legacy_fingerprints.py",):
            continue
        txt = py.read_text(encoding="utf-8", errors="ignore")
        for call in re.finditer(r"cb_engine\.(design_scene|compile_scene_package|"
                                r"repair_package)\s*\(", txt):
            raise AssertionError(f"{py.name} calls cb_engine.{call.group(1)}() — deleted path")
