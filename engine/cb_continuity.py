#!/usr/bin/env python3
"""cb_continuity.py — the cross-scene continuity CHECK.

CORRECTED 2026-07-14 (full-pipeline verification audit): this docstring used to say "fires every gate" —
overclaimed. The code-enforced scope is 3 of 7 gates (2a/2b/3, via cb_pipeline.fire()'s own _GENERATIVE
tuple, which just prints the findings) plus approve() itself (2026-07-14 fix, CLAUDE.md rule 85 — a real
BLOCK-level finding for THIS scene, or a genuinely global finding, now actually refuses that gate's
sign-off, closing the "computed but discarded" gap the old wording implied was already closed). Gates
1/1.6/4/5 do not run this check automatically at all.

Catches the things a single-scene build can't see:
  - Keen's wristbands must progress none -> vacant -> crystal across the whole episode (no regressions).
  - A VISION/flashback (config/continuity.json) must match the real scene it foreshadows — and is flagged
    STALE if that real scene's master was updated AFTER the vision was made (regenerate the vision).
  - Recurring assets (the red-sail sailboat, the pier) must trace back to their anchor scene's master.

    python3 cb_continuity.py [package.json] [episode]
"""
import json, os, sys
import cb_prompts as P

def _resolve_pkg(episode="Ep1"):
    """The current episode's beat package — resolved by glob, mirroring cb_pipeline._resolve_pkg() exactly,
    so this module never carries its own second, independently-hardcoded guess at the filename.
    FIXED 2026-07-12 (full-codebase audit continued): run() and __main__'s --json branch both used to
    hardcode a single stale literal ("..._shot_package.json", a filename that no longer exists anywhere
    outside old archive folders — the live package is "..._beat_package.json"). This is exactly the
    invocation cb-studio/serve.py's continuity_state() fires on every /api/continuity poll (`python3
    cb_continuity.py --json`, no path arg) — so the check was silently crashing (FileNotFoundError -> empty
    stdout -> serve.py's `json.loads(p.stdout or "[]")` swallowing it into an always-empty [] with no
    returncode check anywhere), and the Studio's continuity panel always showed 0 findings regardless of
    real Keen-wristband regressions, stale visions, or canon drift. Callers still may pass an explicit pkg
    path (unchanged); this only replaces the stale default."""
    import glob
    cands = (glob.glob(f"../cb-output/{episode}_*beat_package.json")
             or glob.glob(f"../cb-output/{episode}_*shot_package.json"))
    return max(cands, key=os.path.getmtime) if cands else f"../cb-output/{episode}_The_Adventure_Begins_beat_package.json"

ORDER = {"none": 0, "vacant": 1, "crystal": 2}
TIME_ORDER = {"early morning": 1, "morning": 2, "mid-morning": 3, "late morning": 4, "midday": 5,
              "early afternoon": 6, "afternoon": 7, "late afternoon": 8, "dusk": 9, "evening": 10, "night": 11}
WEATHER_SEV = {"clear": 0, "fair": 0, "clouds gathering": 1, "overcast": 1, "clearing": 1, "storm": 2}

def _rank(text, table):
    """Resolve a TIME_ORDER/WEATHER_SEV rank from free-form authored prose (e.g. 'Morning, early in the
    same warm day.') by finding the longest matching vocabulary keyword as a case-insensitive substring,
    rather than requiring an exact full-string match. ADDED 2026-07-15 (guardrail-fidelity audit): Scene.
    time/weather (cb_director_schemas.py) carry no enum — the Director authors full descriptive sentences —
    so the old TIME_ORDER.get(t,0)/WEATHER_SEV.get(w,0) exact lookups silently fell back to 0 for every real
    scene (confirmed: none of the real Ep1 scenes' time/weather text matches a bare dict key), meaning this
    check was 100% silent on real data regardless of whether the day actually moved forward or backward.
    'Longest match wins' resolves overlapping keys correctly (e.g. 'late morning' over the shorter 'morning'
    substring it contains). Returns 0 when no keyword is found, matching the previous fallback."""
    if not text:
        return 0
    t = str(text).lower()
    best, best_len = 0, 0
    for k, v in table.items():
        if k in t and len(k) > best_len:
            best, best_len = v, len(k)
    return best

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
    prev_t = prev_w = None; prev_n = None; prev_wn = None
    for n in sorted([k for k in scenes if k.isdigit()], key=int):
        sc = scenes[n]; t = sc.get("time"); w = sc.get("weather")
        if t and prev_t and _rank(t, TIME_ORDER) < _rank(prev_t, TIME_ORDER):
            add("BLOCK", n, "-", f"time goes BACKWARDS: scene {prev_n} ({prev_t}) -> scene {n} ({t}) (the day must move forward)")
        if w and prev_w is not None and abs(_rank(w, WEATHER_SEV) - _rank(prev_w, WEATHER_SEV)) >= 2:
            # FIXED 2026-07-12 (full-codebase audit continued): this used to cite prev_n — the scene where
            # prev_t (time) last advanced, tracked by the SEPARATE `if t:` branch below — not the scene
            # where prev_w (weather) actually last advanced. A scene with weather but no time (or vice
            # versa) could name the wrong previous scene as the source of the cited weather state.
            # prev_wn now tracks that scoped to the `if w:` branch only, same pattern as prev_t/prev_n.
            add("NOTE", n, "-", f"weather jumps {prev_w} -> {w} (scene {prev_wn}->{n}) with no intermediate — intend a hard change?")
        if t: prev_t, prev_n = t, n
        if w: prev_w, prev_wn = w, n

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
            # GUARD — added 2026-07-15 alongside restoring `on` above: a naive fix would immediately false-
            # flag Keen's own real "vacant cuffs" entry (fromShot 3.3) against 3.B1, where he correctly has
            # no wristbands yet — that's the story's own deliberate staging (his Mum gives them to him),
            # already declared in the beat's own keenWristbands field, which is more authoritative than this
            # hand-maintained config claim. Skip when the earliest beat's own declared state already says
            # the item is explicitly absent — never override a beat's own more specific declared intent.
            first = appin[0]
            item_l = str(p.get("item", "")).lower()
            if ("cuff" in item_l or "wristband" in item_l) and first.get("keenWristbands", "none") == "none":
                continue
            add("NOTE", fscene, first["shotCode"],
                f"CARRY-BACK? {who} {p.get('verb','has')} {p['item']} from {fs}, but first appears at "
                f"{first['shotCode']} — should it be present from there? Check the script for its true entry point.")

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
    pkg = pkg or _resolve_pkg(episode)
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
        print(json.dumps(check(pkg or _resolve_pkg(ep), ep)))
    else:
        run(pkg, ep)
