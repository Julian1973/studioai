#!/usr/bin/env python3
"""DAILIES — the learning lane. fire → watch → verdict → diagnose → refire.

Thin by design: the engine does the work; this loop adds the pre-flight brain, the
playbook memory, and the ledger. Run from the repo root. Commands:

  status                             where the scene stands + retake rate
  preflight <beat> [ep]              free brain-check (engine dryrun, no spend)
  fire <beat> [ep]                   preflight → REAL render (refuses on BLOCK)
  verdict <beat> good "<note>"       accept: bank the recipe as a proven path
  verdict <beat> retake --layer L --class C "<note>"   diagnose + log + retake cmd
  log                                the learning ledger
"""
import json, os, pathlib, subprocess, sys, time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
ENGINE = ROOT / "engine"
LOGF = HERE / "dailies_log.jsonl"
PLAYBOOK = HERE / "playbook.json"
sys.path.insert(0, str(ENGINE))
import paths as _P  # noqa: E402 — the project profile is the only path authority (T45)
# Relative to engine/ (the engine commands below run with cwd=ENGINE).
DEFAULT_PKG = os.path.relpath(os.path.join(_P.OUTPUT, "Ep1_Episode_1_beat_package.json"), str(ENGINE))

LAYERS = ("take", "keyframe", "brief", "reference")


def _now(): return time.strftime("%Y-%m-%d %H:%M")


def _pb():
    return json.loads(PLAYBOOK.read_text())


def _pb_save(pb):
    PLAYBOOK.write_text(json.dumps(pb, indent=2, ensure_ascii=False))


def _log(entry):
    entry["at"] = _now()
    with open(LOGF, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _entries():
    if not LOGF.exists():
        return []
    return [json.loads(l) for l in LOGF.read_text().splitlines() if l.strip()]


def status():
    es = _entries()
    fires = [e for e in es if e["kind"] == "fire"]
    goods = [e for e in es if e["kind"] == "verdict" and e["verdict"] == "good"]
    retakes = [e for e in es if e["kind"] == "verdict" and e["verdict"] == "retake"]
    rate = (len(retakes) / len(goods)) if goods else None
    print(f"fires: {len(fires)}   accepted: {len(goods)}   retakes: {len(retakes)}")
    print(f"retake rate (retakes per accepted take): {rate:.2f}" if rate is not None else "retake rate: n/a — nothing accepted yet")
    pb = _pb()
    print(f"proven paths: {len(pb.get('proven_paths') or {})}   lessons: {len(pb.get('lessons') or [])}")
    media = ENGINE / "media"
    clips = sorted(media.glob("Ep*_*.mp4")) if media.exists() else []
    print(f"rendered clips on disk: {len(clips)}" + (f"   latest: {clips[-1].name}" if clips else ""))
    last_fire_day = fires[-1]["at"][:10] if fires else None
    today = time.strftime("%Y-%m-%d")
    if last_fire_day != today:
        print("⚠ LAW 1: nothing has rendered today.")


def preflight(beat, ep, pkg):
    return subprocess.run([sys.executable, str(HERE / "preflight.py"), pkg, beat, ep]).returncode


def fire(beat, ep, pkg):
    if preflight(beat, ep, pkg) != 0:
        print("FIRE REFUSED — clear the BLOCKs (or fix the beat upstream) and re-run.")
        return 1
    kc = subprocess.run([sys.executable, "cb_gen.py", "keycheck"], cwd=ENGINE, capture_output=True, text=True)
    if kc.returncode != 0:
        print("FIRE REFUSED — keycheck failed:\n" + (kc.stdout + kc.stderr).strip()[-500:])
        return 1
    print(f"firing {beat} ({ep}) …")
    r = subprocess.run([sys.executable, "cb_beats.py", pkg, beat, ep], cwd=ENGINE)
    _log({"kind": "fire", "beat": beat, "ep": ep, "ok": r.returncode == 0})
    if r.returncode == 0:
        print(f"\nrendered. WATCH IT (engine/media/), then:\n  dailies.py verdict {beat} good \"<why it lands>\"\n"
              f"  dailies.py verdict {beat} retake --layer <take|keyframe|brief|reference> --class <floaty|off_model|…> \"<what's wrong>\"")
    return r.returncode


def verdict(beat, verdict_word, note, layer=None, fclass=None, ep="Ep1", pkg=DEFAULT_PKG):
    pb = _pb()
    if verdict_word == "good":
        arch = input("archetype name for the playbook (e.g. two-bee-dialogue-meadow): ").strip() or f"beat-{beat}"
        pb.setdefault("proven_paths", {})
        entry = pb["proven_paths"].get(arch, {"renders_won": 0})
        entry.update({"proven_on": f"{_now()} {beat}", "recipe": f"the exact plan that fired for {beat} (see dryrun output / retake log)",
                      "renders_won": entry.get("renders_won", 0) + 1, "dethroned_by": None, "note": note})
        pb["proven_paths"][arch] = entry
        _pb_save(pb)
        _log({"kind": "verdict", "beat": beat, "verdict": "good", "note": note, "archetype": arch})
        print(f"banked. '{arch}' is now LAW for its archetype — reused verbatim until a render dethrones it.")
        return 0
    # retake
    if layer not in LAYERS:
        print(f"diagnosis required: --layer must be one of {LAYERS} (LAW 2 — 'try again' is not a diagnosis)"); return 2
    classes = list(_pb().get("failure_classes", {}))
    if fclass not in classes:
        print(f"diagnosis required: --class must be one of {classes}"); return 2
    fix_hint = pb["failure_classes"].get(fclass, "")
    pb.setdefault("lessons", []).append({"at": _now(), "beat": beat, "layer": layer, "class": fclass, "note": note})
    _pb_save(pb)
    _log({"kind": "verdict", "beat": beat, "verdict": "retake", "layer": layer, "class": fclass, "note": note})
    print(f"logged. known fixes for '{fclass}': {fix_hint}")
    if layer == "take":
        print(f"refire route (surgical): python3 engine/cb_retake.py {pkg} {beat}#shotN \"{note}\" {ep}")
    elif layer == "keyframe":
        print(f"route upstream: fix the anchor (Gate 2) then refire: python3 dailies/dailies.py fire {beat} {ep}")
    elif layer == "brief":
        print(f"route upstream: fix the beat's direction fields (Gate 1 / cb_pipeline redirect) then refire.")
    else:
        print(f"route upstream: fix the reference asset (turnaround/plate), then refire EVERYTHING that used it.")
    return 0


def show_log():
    for e in _entries()[-30:]:
        line = f"{e['at']}  {e['kind']:<7} {e.get('beat','')}"
        if e["kind"] == "verdict":
            line += f"  {e['verdict']}" + (f" [{e.get('layer')}/{e.get('class')}]" if e["verdict"] == "retake" else "")
            line += f"  — {e.get('note','')}"
        print(line)


def main(argv):
    if not argv:
        print(__doc__); return 2
    cmd, rest = argv[0], argv[1:]
    pkg = next((a.split("=", 1)[1] for a in rest if a.startswith("--pkg=")), DEFAULT_PKG)
    rest = [a for a in rest if not a.startswith("--pkg=")]
    if cmd == "status":
        status(); return 0
    if cmd == "preflight":
        return preflight(rest[0], rest[1] if len(rest) > 1 else "Ep1", pkg)
    if cmd == "fire":
        return fire(rest[0], rest[1] if len(rest) > 1 else "Ep1", pkg)
    if cmd == "verdict":
        beat, word = rest[0], rest[1]
        layer = next((rest[i + 1] for i, a in enumerate(rest) if a == "--layer"), None)
        fclass = next((rest[i + 1] for i, a in enumerate(rest) if a == "--class"), None)
        note = rest[-1] if rest[-1] not in (layer, fclass, word) else ""
        return verdict(beat, word, note, layer, fclass, pkg=pkg)
    if cmd == "log":
        show_log(); return 0
    print(__doc__); return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
