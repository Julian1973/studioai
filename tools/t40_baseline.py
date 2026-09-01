#!/usr/bin/env python3
"""T40 BASELINE — RESTRUCTURE_SPEC_PROJECTS.md safety rule, made runnable.

Zero-spend, read-only. Walks every real production package of the active project and
records, per shot, exactly what the engine would emit right now:

    scenelook   the Scene Look plate prompt (cb_render._compile_scenelook_prompt)
    keyframe    the opener keyframe prompt (cb_render._resolve_keyframe_prompt), or "<relay>"
    seedance    the animation prompt fire_shot would submit (cb_render._resolve_seedance_prompt)
    conformance the emission-conformance report for that prompt (cb_render._emission_conformance_report)

plus the two LLM system prompts (creative room, Direct) and the resolved profile paths.
Every value lands as a text file under engine/goldens/T40_BASELINE/. A failure is recorded
as `REFUSED: <reason>` so the baseline stays deterministic even where a package is not yet
fireable — an unchanged refusal is as much a proof as an unchanged prompt.

    python3 tools/t40_baseline.py            # write engine/goldens/T40_BASELINE/
    python3 tools/t40_baseline.py --check    # re-emit to a temp dir and diff against it

A non-empty diff is a FAILED restructure phase, whatever it improved.
"""
from __future__ import annotations

import argparse
import filecmp
import json
import os
import pathlib
import re
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
os.chdir(ROOT)

BASELINE = ROOT / "engine" / "goldens" / "T40_BASELINE"
ABS_ROOT_RE = re.compile(re.escape(str(ROOT)))


def _norm(text: str) -> str:
    # Absolute paths differ per machine; the repo-relative form is the stable truth.
    return ABS_ROOT_RE.sub("<ROOT>", str(text)).rstrip() + "\n"


def _write(out: pathlib.Path, name: str, value) -> None:
    if not isinstance(value, str):
        value = json.dumps(value, indent=1, sort_keys=True, ensure_ascii=False, default=str)
    (out / name).write_text(_norm(value), encoding="utf-8")


def _try(fn, *a, **k):
    try:
        v = fn(*a, **k)
        return "<None>" if v is None else v
    except Exception as exc:  # noqa: BLE001 — the refusal text IS the recorded behaviour
        return f"REFUSED: {type(exc).__name__}: {exc}"


def emit(out: pathlib.Path) -> int:
    import cb_render as R
    import paths as P
    out.mkdir(parents=True, exist_ok=True)

    _write(out, "profile_paths.json", {
        k: getattr(P, k) for k in
        ("SHOW_ID", "ENGINE_ADAPTER", "SHOW", "CANON", "CHARS", "LOCATIONS",
         "IDENTITY_PACKS", "CONFIG", "OUTPUT", "SCRIPTS")})

    try:
        import cb_creative
        for role in ("SHOWRUNNER", "DIRECTOR", "CINEMATOGRAPHER", "VOICE DIRECTOR"):
            _write(out, f"system_prompt__creative_room__{role.replace(' ', '_')}.txt",
                   _try(cb_creative._system_prompt, role)
                   if hasattr(cb_creative, "_system_prompt") else "<no _system_prompt>")
    except Exception as exc:  # noqa: BLE001
        _write(out, "system_prompt__creative_room.txt", f"REFUSED: {exc}")

    count = 0
    pkgs = sorted(pathlib.Path(P.OUTPUT).glob("Ep*_scene*_production_package.json"))
    for pkg_path in pkgs:
        m = re.match(r"(Ep\d+)_scene(\d+)_production_package\.json", pkg_path.name)
        if not m:
            continue
        episode, scene = m.group(1), m.group(2)
        tag = f"{episode}_S{scene}"
        _write(out, f"{tag}__scenelook.txt", _try(R._compile_scenelook_prompt, scene, episode))
        try:
            pkg, _ = R.load_pkg(scene, episode)
        except Exception as exc:  # noqa: BLE001
            _write(out, f"{tag}__package.txt", f"REFUSED: {exc}")
            continue
        for shot in pkg.get("shots") or []:
            sid = shot.get("shotId") or "?"
            base = f"{tag}__{sid}"
            _write(out, f"{base}__keyframe.txt",
                   _try(R._resolve_keyframe_prompt, pkg, shot))
            sd = _try(R._resolve_seedance_prompt, pkg, shot, scene, episode)
            prompt = sd[0] if isinstance(sd, tuple) else sd
            _write(out, f"{base}__seedance.txt", prompt)
            if isinstance(sd, tuple) and prompt and hasattr(R, "_emission_conformance_report"):
                specialist = _try(R._approved_department_output, pkg, sid, "animation")
                _write(out, f"{base}__conformance.json",
                       _try(R._emission_conformance_report, shot,
                            specialist if isinstance(specialist, dict) else {}, prompt))
            # STORED-DIRECTION EMISSION — the lineage gates above legitimately refuse a shot
            # whose direct inputs are stale or whose plate is unsigned on this machine. The
            # prompt-building code is still exercised here on the stored (approved or
            # candidate) department output, so a restructure that changes how canon data
            # reaches the prompt is caught even for a shot the gates refuse today.
            led = ((pkg.get("shotLedger") or pkg.get("ledger") or {}).get(sid)
                   if isinstance(pkg.get("shotLedger") or pkg.get("ledger"), dict) else None)
            if led is None:
                led = _try(R._ledger, pkg, sid)
            work = (led.get("departmentWork") or {}) if isinstance(led, dict) else {}
            def _stored(stage):
                w = work.get(stage) or {}
                rec = w.get("approved") or w.get("candidate") or {}
                return rec.get("output") or {}
            anim = _stored("animation")
            raw = anim.get("providerPrompt") or shot.get("seedancePrompt") or ""
            _write(out, f"{base}__stored_seedance_raw.txt", raw or "<empty>")
            if raw:
                _write(out, f"{base}__stored_seedance_scaled.txt",
                       _try(R._with_character_scale_control, raw, shot, "referenceSlots",
                            scene, episode))
                _write(out, f"{base}__stored_conformance.json",
                       _try(R._emission_conformance_report, shot, anim, raw))
            cine = _stored("cinematography")
            if shot.get("sourceType") == "opener":
                plan = _try(R._expanded_reference_blueprint, shot, "keyframeReferenceSlots",
                            R._characters_cfg(), scene, episode)
                _write(out, f"{base}__stored_keyframe_refs.json", plan)
                _write(out, f"{base}__stored_keyframe.txt",
                       _try(R._compile_keyframe_integration_prompt, cine, shot,
                            plan if isinstance(plan, list) else None))
            _write(out, f"{base}__stored_animation_refs.json",
                   _try(R._expanded_reference_blueprint, shot, "referenceSlots",
                        R._characters_cfg(), scene, episode))
            count += 1
    _write(out, "MANIFEST.txt", "\n".join(sorted(p.name for p in out.iterdir() if p.name != "MANIFEST.txt")))
    return count


def check() -> int:
    if not BASELINE.exists():
        print(f"no baseline at {BASELINE} — run without --check first")
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        fresh = pathlib.Path(tmp) / "fresh"
        emit(fresh)
        cmp = filecmp.dircmp(str(BASELINE), str(fresh))
        bad = sorted(set(cmp.diff_files) | set(cmp.left_only) | set(cmp.right_only))
        if not bad:
            print(f"T40 baseline: IDENTICAL ({len(list(BASELINE.iterdir()))} files)")
            return 0
        print("T40 baseline: DIFFERS —")
        for name in bad:
            kind = ("changed" if name in cmp.diff_files else
                    "missing now" if name in cmp.left_only else "new")
            print(f"  {kind:12} {name}")
        return 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        sys.exit(check())
    n = emit(BASELINE)
    print(f"T40 baseline written: {n} shots → {BASELINE.relative_to(ROOT)}")
