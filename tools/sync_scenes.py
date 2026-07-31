#!/usr/bin/env python3
"""ONE SCENE SOURCE (T33 Ruling 3, 2026-07-02). The single source of truth for a scene's descriptive fields
(location/look/definingFeature/lighting/etc.) is the beat package's own scenes[] array — the Director's Gate-1
output. shows/crystal-bears/canon/locations.json (config/locations.json) is a CACHED SNAPSHOT of it, read by
cb_prompts.scene_cfg() on every keyframe/plate/Seedance prompt build. Nothing previously kept that snapshot in
sync: a beat-package scene edit could silently never reach any prompt at all, with no signal that it hadn't. Same
discipline as sync_canon.py (source hash vs copy hash), extended to scene data.

    python3 tools/sync_scenes.py            # regenerate every episode's locations.json entries from their beat packages
    python3 tools/sync_scenes.py --check     # verify only — exit 1 on any drift (wired into cb_beats.render_readiness)
"""
import sys, os, json, glob, importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(ROOT, "engine")
LOCATIONS_PATH = os.path.join(ROOT, "shows", "crystal-bears", "canon", "locations.json")


def _load_cb_prompts():
    """Import engine/cb_prompts.py by path (not a package import — engine/ isn't installed) so this tool can reuse
    the SAME hash function the runtime freshness check uses; two independent implementations could themselves drift."""
    spec = importlib.util.spec_from_file_location("cb_prompts", os.path.join(ENGINE, "cb_prompts.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _episodes():
    """Every episode that has both a beat package and a canon/locations.json entry to sync."""
    pattern = os.path.join(ROOT, "cb-output", "*_beat_package.json")
    for p in sorted(glob.glob(pattern)):
        base = os.path.basename(p)
        ep = base.split("_", 1)[0]
        yield ep, p


def main():
    check = "--check" in sys.argv
    P = _load_cb_prompts()
    locations = json.load(open(LOCATIONS_PATH)) if os.path.exists(LOCATIONS_PATH) else {}
    drift = []
    synced = 0
    for ep, pkg_path in _episodes():
        d = json.load(open(pkg_path))
        scenes = d.get("scenes") or []
        if not scenes:
            continue
        cache = locations.setdefault(ep, {})
        for src in scenes:
            sn = str(src.get("sceneNumber"))
            if not sn or sn == "None":
                continue
            want = P._scene_source_hash(src)
            entry = cache.get(sn)
            got = entry.get("_sourceHash") if entry else None
            if got == want:
                continue
            drift.append(f"{ep} scene {sn}: " + ("never synced" if got is None else f"stale (had {got}, source is now {want})"))
            if not check:
                new_entry = {k: src.get(k) for k in P.SCENE_SYNC_FIELDS}
                if entry and entry.get("master"):
                    new_entry["master"] = entry["master"]   # keep the signed-off plate reference already on file
                new_entry["_sourceHash"] = want
                cache[sn] = new_entry
                synced += 1
    if check:
        if drift:
            print("SCENE CACHE DRIFT (BLOCK):")
            for d_ in drift:
                print("  " + d_)
            sys.exit(1)
        print(f"scene cache in sync — every scene's canon/locations.json entry matches its beat package")
        return
    if drift:
        json.dump(locations, open(LOCATIONS_PATH, "w"), indent=1, ensure_ascii=False)
        print(f"scene cache resynced: {synced} scene(s) updated — " + "; ".join(drift))
    else:
        print("scene cache already in sync — nothing to do")


if __name__ == "__main__":
    main()
