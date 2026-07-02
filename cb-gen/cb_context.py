#!/usr/bin/env python3
"""cb_context.py — the COMPLETENESS AUDIT. Before a shot is prompted, prove that EVERYTHING that
should feed it is present and locked: the scene, the previous scene, the references, the show bible,
the storyline, the script. If the script mentions a hero item that isn't reference-locked, flag it
BEFORE rendering — so gaps (a wrong cuff, a missing satchel) are caught by the process, not the eye.

    python3 cb_context.py [package.json] [scene]      # audit a scene (or whole episode)
"""
import json, os, sys
import cb_prompts as P

# hero things that, if named in the script, MUST be reference-locked for that shot
HERO = {
    "wristband": ["wristband", "cuff", "band", "bezel", "amulet"],
    "satchel":   ["satchel", "bag", "pack", "strap"],
    "boat":      ["boat", "sailboat", "sail", "dock", "pier"],
    "bowl":      ["bowl"],
    "wand":      ["wand", "mallet"],
    "parcel":    ["parcel", "box", "supplies", "package"],
}

def _locked_text(episode, shot):
    """All the lock text the builder will inject for this shot — what's actually pinned."""
    refs, item_locks = P.items_for(episode, shot)
    parts = [P.recurring_line(episode, shot), P.worn_line(episode, shot), P.props_block(shot),
             P._band_line(shot), " ".join(item_locks)]
    return " ".join(parts).lower()

def check(pkg, episode="Ep1", scene=None):
    d = json.load(open(pkg))
    shots = [s for s in (d.get("beats") or d.get("shots") or []) if scene is None or str(s.get("sceneNumber")) == str(scene)]
    F = []
    def add(code, level, msg): F.append({"shot": code, "level": level, "msg": msg})
    for s in shots:
        code = s.get("shotCode") or s.get("beatCode"); sc = P.scene_cfg(episode, str(s.get("sceneNumber")))
        # 1. the scene is fully specified
        if not sc.get("master"): add(code, "NOTE", "scene has no master yet (will build an establishing master)")
        if not sc.get("time") or not sc.get("weather"): add(code, "BLOCK", "scene missing time/weather")
        # 2. every character has a reference anchor (the show bible/reference)
        for c in s.get("characters", []):
            if c not in P.CHARACTERS: add(code, "BLOCK", f"character '{c}' has no reference anchor in characters.json")
        # 3. the script's hero items are reference-locked
        text = ((s.get("action") or s.get("storyBeat") or "") + " "
                + (s.get("dialogue") or " ".join((c.get("dialogue") or "") for c in (s.get("cuts") or [])))).lower()
        locked = _locked_text(episode, s)
        for key, kws in HERO.items():
            if any(k in text for k in kws) and not any(k in locked for k in kws):
                # boat/pier are set elements handled by master-derive — only a note
                lvl = "NOTE" if key == "boat" else "BLOCK"
                add(code, lvl, f"script mentions '{key}' but it is NOT reference-locked for this shot "
                               f"— declare it (items / props / recurring / carried)")
    return F

def run(pkg=None, scene=None, episode="Ep1"):
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    pkg = pkg or "../cb-output/Ep1_The_Adventure_Begins_shot_package.json"
    F = check(pkg, episode, scene)
    blk = [f for f in F if f["level"] == "BLOCK"]
    where = f"scene {scene}" if scene else episode
    print(f"CONTEXT AUDIT — {where}: {len(blk)} BLOCK, {len(F)-len(blk)} note", flush=True)
    for f in F: print(f"  [{f['level']}] {f['shot']}: {f['msg']}", flush=True)
    return F

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None,
        sys.argv[2] if len(sys.argv) > 2 else None)
