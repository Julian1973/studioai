#!/usr/bin/env python3
"""T58 — the second project is a full citizen and never sees the first one.

Every check here runs the engine in a SUBPROCESS with STUDIO_PROJECT=the-box-monsters (the profile is
read once at import time, so an in-process monkeypatch cannot prove this). Three claims:
  1. every `paths.*` value the active project declares resolves inside projects/the-box-monsters/;
  2. every engine module imports, every project-data loader returns Box Monsters data (or empty),
     and the canon lock / intake / capability report work for its Ep1;
  3. no Crystal Bears path, name or Phase-3 word is reachable from the second project.
"""
import json
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENGINE = ROOT / "engine"
SECOND = "the-box-monsters"
FIRST_WORDS = ("crystal-bears", "Crystal Bears", "Fuzzby", "Zenny", "Aida", "Keen", "Squeaky", "Howey",
               "cb-seed", "cb-output")


def _run(code: str, project: str = SECOND, timeout: int = 240) -> dict:
    env = {**os.environ, "STUDIO_PROJECT": project, "PYTHONPATH": str(ENGINE)}
    env.pop("STUDIO_SHOW", None)
    proc = subprocess.run([sys.executable, "-c", code], cwd=str(ENGINE), env=env,
                          capture_output=True, text=True, timeout=timeout)
    assert proc.returncode == 0, f"subprocess failed:\n{proc.stdout[-2000:]}\n{proc.stderr[-4000:]}"
    marker = proc.stdout.rfind("\n@@JSON@@")
    assert marker >= 0, proc.stdout[-2000:]
    return json.loads(proc.stdout[marker + len("\n@@JSON@@"):])


@pytest.fixture(scope="module")
def second_project_exists():
    if not (ROOT / "projects" / SECOND / "profile.json").exists():
        pytest.skip(f"projects/{SECOND} is not scaffolded on this checkout")


def test_every_declared_path_lives_inside_the_second_project(second_project_exists):
    out = _run("""
import json, paths as P
vals = {k: getattr(P, k) for k in dir(P) if k.isupper() and isinstance(getattr(P, k), str)}
print("\\n@@JSON@@" + json.dumps({"id": P.PROJECT_ID, "name": P.PROJECT_NAME, "paths": vals}))
""")
    assert out["id"] == SECOND and out["name"] == "The Box Monsters"
    home = str(ROOT / "projects" / SECOND)
    for key, value in out["paths"].items():
        if key in ("PROJECT_ID", "PROJECT_NAME", "SHOW_ID", "ENGINE_ADAPTER", "SHOWRUNNER",
                   "ENGINE", "ROOT", "MEDIA_URL") or key.endswith("_REL"):
            continue
        if key in ("LOCKED", "NOTES"):        # legacy engine-level names, unused by any live module
            continue
        if os.sep in value or "/" in value:
            assert value.startswith(home) or value.startswith(str(ROOT / "studio")), f"paths.{key} = {value}"
        for word in FIRST_WORDS:
            assert word not in value, f"paths.{key} = {value} names the first project"


def test_every_engine_module_imports_under_the_second_project(second_project_exists):
    modules = sorted(p.stem for p in ENGINE.glob("*.py")
                     if not p.stem.startswith("test_") and p.stem not in ("conftest",))
    out = _run(f"""
import importlib, json, traceback
failed = {{}}
for name in {modules!r}:
    try:
        importlib.import_module(name)
    except Exception as exc:
        failed[name] = traceback.format_exc().splitlines()[-1]
print("\\n@@JSON@@" + json.dumps(failed))
""", timeout=600)
    assert out == {}, "modules that cannot import for the second project:\n" + "\n".join(f"{k}: {v}" for k, v in out.items())


def test_project_data_loaders_serve_the_second_project_only(second_project_exists):
    out = _run("""
import json, paths as P, project_laws as L, cb_departments as D, project_profile, cb_canon
report = project_profile.capability_report(P.PROFILE)
status = cb_canon.status("Ep1", root="..")
print("\\n@@JSON@@" + json.dumps({
  "names": L.cast_names(), "species": {n: L.species_of(n, {}) for n in L.cast_names()},
  "pron": L.pronunciation_overrides(), "bans": L.proximity_bans(), "forbidden": L.keyframe_forbidden(True),
  "room": L.room_voice(), "chairs": {w: D.chair_ref(w) for w in ("director","dp","voice","animation","review","post")},
  "contract": D.load_runtime_skill("director"),
  "ready": report["productionReady"], "missing": report["missingRequiredPaths"],
  "lockCurrent": status["current"], "episodeReady": status.get("episodeReady"),
  "blockers": [b.get("code") for b in (status.get("blockers") or []) + (status.get("episodeBlockers") or [])],
}))
""")
    assert out["names"] == ["Patch", "Rumble", "Tilly", "Nib", "Jenny", "Teacher", "Classmate"]
    assert out["species"]["Rumble"] == "box monster" and out["species"]["Jenny"] == "human"
    assert out["pron"] == {} and out["bans"] == [] and out["forbidden"] == []
    assert "wonky" in out["room"]
    for ref in out["chairs"].values():
        assert ref.startswith("studio/chairs/") and "crystal" not in ref
    assert "You are the Box Monsters Director" in out["contract"]
    assert out["ready"] is True and out["missing"] == []
    assert out["lockCurrent"] is True and out["episodeReady"] is True, out["blockers"]
    blob = json.dumps(out)
    for word in FIRST_WORDS:
        assert word not in blob, f"{word!r} reachable from the second project: {blob[:400]}"


def test_intake_and_studio_registry_work_for_the_second_project(second_project_exists):
    out = _run("""
import json, sys, cb_intake
s = cb_intake.intake_status("Ep1")
sys.path.insert(0, "../cb-studio")
import serve
reg = serve._project_registry()
roster = serve._project_design_roster()
print("\\n@@JSON@@" + json.dumps({
  "hasScript": s.get("hasScript"), "scriptVersionId": s.get("scriptVersionId"),
  "canonLockCurrent": s.get("canonLockCurrent"), "canonEpisodeReady": s.get("canonEpisodeReady"),
  "canonBlockers": s.get("canonBlockers"), "active": serve.ACTIVE_PROJECT_ID,
  "registry": [r["id"] for r in reg], "activeRow": next(r for r in reg if r["id"] == serve.ACTIVE_PROJECT_ID),
  "rosterNames": [c["name"] for c in roster["characters"]], "titles": roster["episodeTitles"],
}))
""", timeout=300)
    assert out["hasScript"] is True and str(out["scriptVersionId"]).startswith("sha256:624e0080")
    assert out["canonLockCurrent"] is True and out["canonEpisodeReady"] is True, out["canonBlockers"]
    assert out["active"] == SECOND and SECOND in out["registry"]
    assert out["activeRow"]["configBase"].startswith(f"projects/{SECOND}/")
    assert out["rosterNames"] == ["Patch", "Rumble", "Tilly", "Nib", "Jenny"]
    assert out["titles"] == {"Ep1": "Episode 1: The Box That Felt Small"}


def test_a_project_without_its_own_voice_craft_still_runs_the_voice_stage(second_project_exists):
    """The Voice Director's craft is the studio's; a project only overrides it.

    cb_voice_director loads its registers and rulebook with a raise, never a degrade, and the
    project template ships neither — so the second project's first HEAR pass died on "Voice
    Director data is unavailable: VOICE_ARCHETYPE_REGISTERS.json" with nothing wrong with the
    project at all (2026-09-02). paths now falls back to studio/chairs/voice-director/ for both.
    """
    out = _run("""
import json, pathlib
import paths as P
import cb_voice_director as V
registers = V.archetype_registers()
rulebook = V.rulebook()
print("\\n@@JSON@@" + json.dumps({
    "registersPath": str(P.VOICE_REGISTERS),
    "rulebookPath": str(P.VOICE_RULEBOOK),
    "registerIds": sorted((registers.get("registers") or {}).keys()),
    "mechanicalRules": sorted((rulebook.get("mechanicalRules") or {}).keys()),
}))
""")
    studio = str(ROOT / "studio" / "chairs" / "voice-director")
    assert out["registersPath"].startswith(studio)
    assert out["rulebookPath"].startswith(studio)
    assert out["registerIds"], "the studio's own register vocabulary must be readable"
    assert "lockedScriptWords" in out["mechanicalRules"]
    for word in FIRST_WORDS:
        assert word not in json.dumps(out), f"{word} reached the second project's voice craft"


def test_the_first_project_keeps_its_own_voice_craft(second_project_exists):
    """The fallback is a floor, never an override: a project's own files still win."""
    out = _run("""
import json
import paths as P
print("\\n@@JSON@@" + json.dumps({"registers": str(P.VOICE_REGISTERS),
                                  "rulebook": str(P.VOICE_RULEBOOK)}))
""", project="crystal-bears")
    own = str(ROOT / "projects" / "crystal-bears" / "creative")
    assert out["registers"].startswith(own)
    assert out["rulebook"].startswith(own)
