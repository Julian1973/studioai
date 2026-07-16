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
    # FIXED 2026-07-15 (live during a real Gate-2a sign-off): "pack" was a bare substring, so ordinary physical-
    # comedy vocabulary describing DENSITY ("pollen-packed", "packed pollen") false-positived as a satchel-prop
    # mention — confirmed live on 1.B2/1.B4 (Scene 1, no satchel anywhere near that scene) blocking a real
    # sign-off. Every genuine satchel mention in the real package already also says "satchel"/"bag"/"strap" —
    # dropping "pack" loses zero real detection (checked directly against the whole package before removing it).
    "satchel":   ["satchel", "bag", "strap"],
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
    # FIXED 2026-07-12 (full-codebase audit continued): a beat-native beat only ever carries `beatCode`, never
    # `shotCode` — but items_for/worn_line/recurring_line (called below via _locked_text) all key their lookups
    # off shot.get("shotCode"), so it was always None and every hero-item lock check silently matched nothing.
    # cb_continuity.check() already carries this exact normalization for the same reason; mirror it here.
    for s in shots:
        s.setdefault("shotCode", s.get("beatCode"))
    F = []
    def add(code, level, msg): F.append({"shot": code, "level": level, "msg": msg})

    # 1. the scene is fully specified — a SCENE-level fact, checked once per distinct scene, never per beat.
    # FIXED 2026-07-12 (full-codebase audit continued): this used to run inside the per-beat loop below (same
    # `sc` object read fresh for every beat sharing a scene), so one real scene-level gap was reported as one
    # identical finding PER BEAT in that scene — demonstrated live: scene 3 (8 beats, no master yet) printed
    # "scene has no master yet" 8 times for a single underlying fact, inflating the BLOCK/NOTE count and
    # obscuring how many distinct problems actually exist.
    scene_nums = sorted({str(s.get("sceneNumber")) for s in shots}, key=lambda x: (0, int(x)) if x.isdigit() else (1, x))
    for sn in scene_nums:
        sc = P.scene_cfg(episode, sn)
        if not sc.get("master"): add(f"scene {sn}", "NOTE", "scene has no master yet (will build an establishing master)")
        if not sc.get("time") or not sc.get("weather"): add(f"scene {sn}", "BLOCK", "scene missing time/weather")

    for s in shots:
        code = s.get("shotCode") or s.get("beatCode")
        # 2. every character has a reference anchor (the show bible/reference)
        for c in s.get("characters", []):
            if c not in P.CHARACTERS: add(code, "BLOCK", f"character '{c}' has no reference anchor in characters.json")
        # 3. the script's hero items are reference-locked
        # FIXED 2026-07-12 (full-codebase audit continued): beat-native beats keep their real per-shot staging
        # prose exclusively inside cuts[].action — 0/43 real beats have ever populated a top-level "action" or
        # "dialogue" key. The old scan only ever saw storyBeat + the aggregated cuts[].dialogue, so the richest
        # source of hero-item mentions (the specific per-cut action text — "satchel", "wristband", "wand", etc.)
        # was never scanned at all, defeating this module's own stated purpose for most beats. Fold cuts[].action
        # in and drop the dead top-level action/dialogue branches (no beat-native beat has ever populated them).
        cuts_action = " ".join((c.get("action") or "") for c in (s.get("cuts") or []))
        dialogue_text = " ".join((c.get("dialogue") or "") for c in (s.get("cuts") or []))
        text = ((s.get("storyBeat") or "") + " " + cuts_action + " " + dialogue_text).lower()
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
    # FIXED 2026-07-12 (full-codebase audit continued): the hardcoded default pointed at
    # "Ep1_The_Adventure_Begins_shot_package.json" — a pre-beat-native-migration filename that no longer exists
    # in cb-output/, so the module's own documented no-argument usage (`python3 cb_context.py`) crashed with a
    # live FileNotFoundError. Resolve the real current package dynamically instead, the same way cb_pipeline's
    # own _resolve_pkg() does (glob for `{episode}_*beat_package.json` / fall back to `*shot_package.json`,
    # newest by mtime), with the same literal-fallback shape as a last resort if nothing globs at all.
    pkg = pkg or P._resolve_beat_pkg(episode) or f"../cb-output/{episode}_The_Adventure_Begins_beat_package.json"
    F = check(pkg, episode, scene)
    blk = [f for f in F if f["level"] == "BLOCK"]
    where = f"scene {scene}" if scene else episode
    print(f"CONTEXT AUDIT — {where}: {len(blk)} BLOCK, {len(F)-len(blk)} note", flush=True)
    for f in F: print(f"  [{f['level']}] {f['shot']}: {f['msg']}", flush=True)
    return F

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None,
        sys.argv[2] if len(sys.argv) > 2 else None)
