#!/usr/bin/env python3
"""cb_continuity.py — the cross-scene continuity CHECK (fires every gate, surfaces in the studio).

Catches the things a single-scene build can't see:
  - Keen's wristbands must progress none -> vacant -> crystal across the whole episode (no regressions).
  - A VISION/flashback (config/continuity.json) must match the real scene it foreshadows — and is flagged
    STALE if that real scene's master was updated AFTER the vision was made (regenerate the vision).
  - Recurring assets (the red-sail sailboat, the pier) must trace back to their anchor scene's master.

    python3 cb_continuity.py [package.json] [episode]
"""
import json, os, sys
import cb_prompts as P

ORDER = {"none": 0, "vacant": 1, "crystal": 2}
TIME_ORDER = {"early morning": 1, "morning": 2, "mid-morning": 3, "late morning": 4, "midday": 5,
              "early afternoon": 6, "afternoon": 7, "late afternoon": 8, "dusk": 9, "evening": 10, "night": 11}
WEATHER_SEV = {"clear": 0, "fair": 0, "clouds gathering": 1, "overcast": 1, "clearing": 1, "storm": 2}
def _exists(p): return bool(p) and os.path.exists(p)
def _mtime(p): return os.path.getmtime(p) if _exists(p) else 0
def _codekey(c):
    out = []
    for x in str(c).split("."):
        d = "".join(ch for ch in x if ch.isdigit())   # "B2" -> 2, "3" -> 3 (beat codes are 1.B2, shots are 1.3)
        out.append(int(d) if d else 0)
    return out

def _canon_sync_findings():
    """T30 Phase 1 — the skills/*/references canon copies must match root CRYSTAL_BEARS_LOCKED_CANON.md byte-for-byte
    (via tools/sync_canon.py's hash). A drifted copy means someone edited a generated file directly instead of the
    source — BLOCK it here so it's caught at every gate, not just when someone remembers to run --check by hand."""
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        root = os.path.dirname(here)
        sys.path.insert(0, os.path.join(root, "tools"))
        import sync_canon
        src = open(sync_canon.SRC, encoding="utf-8").read()
        import hashlib
        h = hashlib.sha256(src.encode()).hexdigest()[:12]
        skill_dirs = sorted(d for d in __import__("glob").glob(os.path.join(root, "skills", "crystal-bears-*"))
                            if os.path.isdir(d))
        out = []
        for d in skill_dirs:
            c = os.path.join(d, "references", "CRYSTAL_BEARS_LOCKED_CANON.md")
            if not os.path.exists(c) or hashlib.sha256(sync_canon.body(c).encode()).hexdigest()[:12] != h:
                out.append({"level": "BLOCK", "scene": "-", "shot": "-",
                            "msg": f"CANON DRIFT: {os.path.relpath(c, root)} does not match root CRYSTAL_BEARS_LOCKED_CANON.md "
                                   f"— run `python3 tools/sync_canon.py` to regenerate it (never edit a copy directly)."})
        return out
    except Exception as e:
        return [{"level": "NOTE", "scene": "-", "shot": "-", "msg": f"canon sync check unavailable ({str(e)[:120]})"}]

def check(pkg, episode="Ep1"):
    _pkg = json.load(open(pkg))
    shots = _pkg.get("beats") or _pkg.get("shots") or []
    for _s in shots:
        _s.setdefault("shotCode", _s.get("beatCode"))
    F = []
    def add(level, scene, shot, msg): F.append({"level": level, "scene": str(scene), "shot": shot, "msg": msg})

    # 0. CANON SYNC (T30 Phase 1) — every skill's canon copy must match the root source exactly
    F.extend(_canon_sync_findings())

    # 1. Keen wristbands progress monotonically (visions excluded — they legitimately show an earlier state)
    keen = sorted([s for s in shots if "Keen" in s.get("characters", []) and not P.vision_for(episode, s["shotCode"])],
                  key=lambda s: (int(s["sceneNumber"]), _codekey(s["shotCode"])))
    seen = "none"
    for s in keen:
        st = s.get("keenWristbands", "none")
        if ORDER.get(st, 0) < ORDER.get(seen, 0):
            add("BLOCK", s["sceneNumber"], s["shotCode"],
                f"Keen wristbands regress {seen} -> {st} (must progress none -> vacant -> crystal)")
        if ORDER.get(st, 0) > ORDER.get(seen, 0): seen = st

    # 1b. Time of day must move FORWARD; weather must transition logically
    scenes = P.LOCATIONS.get(episode, {})
    prev_t = prev_w = None; prev_n = None
    for n in sorted([k for k in scenes if k.isdigit()], key=int):
        sc = scenes[n]; t = sc.get("time"); w = sc.get("weather")
        if t and prev_t and TIME_ORDER.get(t, 0) < TIME_ORDER.get(prev_t, 0):
            add("BLOCK", n, "-", f"time goes BACKWARDS: scene {prev_n} ({prev_t}) -> scene {n} ({t}) (the day must move forward)")
        if w and prev_w is not None and abs(WEATHER_SEV.get(w, 0) - WEATHER_SEV.get(prev_w, 0)) >= 2:
            add("NOTE", n, "-", f"weather jumps {prev_w} -> {w} (scene {prev_n}->{n}) with no intermediate — intend a hard change?")
        if t: prev_t, prev_n = t, n
        if w: prev_w = w

    # 2. Visions must match — and must not be stale vs the real scene's master
    for v in P.CONTINUITY.get(episode, {}).get("visions", []):
        sc = P.scene_cfg(episode, v["ofScene"]); m = sc.get("master")
        vs = next((s for s in shots if s["shotCode"] == v["shot"]), None)
        vscene = vs["sceneNumber"] if vs else "?"
        slug = (vs.get("slug", v["shot"].replace(".", "_")) if vs else v["shot"].replace(".", "_"))
        vkf = f"media/{episode}_{v['shot']}_{slug}.png"
        if not _exists(m):
            add("BLOCK", vscene, v["shot"],
                f"vision of scene {v['ofScene']}, but scene {v['ofScene']} has no master yet — build it first")
        elif _exists(vkf) and _mtime(vkf) < _mtime(m):
            add("BLOCK", vscene, v["shot"],
                f"VISION OUT OF DATE — scene {v['ofScene']} was rebuilt after this vision; regenerate the vision so it matches")
        else:
            add("NOTE", vscene, v["shot"],
                f"vision derives from scene {v['ofScene']} (wristbands={v.get('wristbands')}) — re-check if scene {v['ofScene']} changes")

    # 3. Recurring assets trace to their anchor scene
    for r in P.CONTINUITY.get(episode, {}).get("recurring", []):
        sc = P.scene_cfg(episode, r["anchorScene"])
        where = ", ".join(str(x) for x in (r.get("scenes") or r.get("shots") or []))
        scope = "scenes" if r.get("scenes") else "shots"
        extra = f" [look: {r['appearance']}]" if r.get("appearance") else ""
        if not _exists(sc.get("master")):
            add("NOTE", r["anchorScene"], "-",
                f"recurring '{r['name']}': anchor scene {r['anchorScene']} master not built yet — build it so {scope} {where} can match{extra}")
        else:
            add("NOTE", r["anchorScene"], "-", f"recurring '{r['name']}' must match scene {r['anchorScene']} across {scope} {where}{extra}")

    # 4. CARRY-BACK continuity — a WORN/persistent item (e.g. Keen's satchel) should usually be present from
    #    the character's FIRST appearance in the scene, not just where the script first NAMES it. Flag (NOTE)
    #    when its fromShot is later than the character's first shot in that scene, so the true entry point is
    #    confirmed against the script. (Caught the satchel popping in at 3.2 instead of being there from 3.1.)
    real = [s for s in shots if not P.vision_for(episode, s["shotCode"])]
    for p in P.CONTINUITY.get(episode, {}).get("persistent", []):
        who = p.get("on"); fs = str(p.get("fromShot", ""))
        if not who or not fs:
            continue
        fscene = fs.split(".")[0]
        appin = sorted([s for s in real if who in s.get("characters", []) and str(s.get("sceneNumber")) == fscene],
                       key=lambda s: _codekey(s["shotCode"]))
        if appin and _codekey(appin[0]["shotCode"]) < _codekey(fs):
            add("NOTE", fscene, appin[0]["shotCode"],
                f"CARRY-BACK? {who} {p.get('verb','has')} {p['item']} from {fs}, but first appears at "
                f"{appin[0]['shotCode']} — should it be present from there? Check the script for its true entry point.")

    # 5. STATEFUL LOCATIONS — a place REMEMBERS. A returning location (same `locationId`) must derive from its
    #    LAST-seen state (not be older than the previous visit) and carry the accumulated worldState changes.
    by_lid = {}
    for k in sorted([k for k in scenes if k.isdigit()], key=int):
        lid = scenes[k].get("locationId")
        if lid: by_lid.setdefault(lid, []).append(int(k))
    ws = P.CONTINUITY.get(episode, {}).get("worldState", [])
    for lid, visits in by_lid.items():
        for i in range(1, len(visits)):
            n, prev = visits[i], visits[i - 1]
            cur_p = f"media/{episode}_S{n}_plate.png"; prev_p = f"media/{episode}_S{prev}_plate.png"
            chg = [w["change"] for w in ws if w.get("locationId") == lid
                   and str(w.get("atScene", "")).isdigit() and int(w["atScene"]) <= n]
            chg_txt = f"; carries {len(chg)} world change(s)" if chg else ""
            if _exists(cur_p) and _exists(prev_p) and _mtime(cur_p) < _mtime(prev_p):
                add("NOTE", n, "-", f"STATEFUL LOCATION '{lid}': scene {n} plate is OLDER than its last state "
                    f"(scene {prev}) — rebuild so it inherits the latest world state{chg_txt}")
            else:
                add("NOTE", n, "-", f"returning location '{lid}': scene {n} derives from scene {prev}'s state{chg_txt}")
    return F

def run(pkg=None, episode="Ep1"):
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    pkg = pkg or "../cb-output/Ep1_The_Adventure_Begins_shot_package.json"
    F = check(pkg, episode)
    blocks = [f for f in F if f["level"] == "BLOCK"]
    print(f"CONTINUITY — {episode}: {len(blocks)} BLOCK, {len(F)-len(blocks)} note", flush=True)
    for f in F:
        print(f"  [{f['level']}] scene {f['scene']} shot {f['shot']}: {f['msg']}", flush=True)
    return F

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--json"]
    pkg = args[0] if len(args) > 0 else None
    ep = args[1] if len(args) > 1 else "Ep1"
    if "--json" in sys.argv:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        print(json.dumps(check(pkg or "../cb-output/Ep1_The_Adventure_Begins_shot_package.json", ep)))
    else:
        run(pkg, ep)
