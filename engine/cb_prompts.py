#!/usr/bin/env python3
"""cb_prompts.py — GATE 2, THE DP + PRODUCTION DESIGNER. THE BEST prompting recipe per engine, encoded once.

ROLE: turns a signed-off beat's own staging data into the production-grade, paste-ready KEYFRAME image
prompt (build_keyframe_prompt) and the once-per-scene establishing PLATE prompt (build_plate_prompt) — the
actual image-generation instructions Gate 2 fires. RESPONSIBILITY: every keyframe is on-model, reference-
anchored (character identity comes ONLY from the reference images, never from prose — Law 5, un-reopenable)
and lit/composed to a real cinematographer's standard, not a generic "nice picture." WORKFLOW: build_
keyframe_prompt reads the beat's own authored staging (framing, light, atmosphere) and assembles it against
the locked reference stack (turnarounds + scene plate) — deterministic, data-driven, ZERO LLM call in this
step (matching Gate 5's own "mechanical, not a guess" design; the CREATIVE call already happened at Gate 1).
INFLUENCE (2026-07-14, the named-auteur-per-chair doctrine, CRYSTAL_BEARS_STUDIO_BIBLE.md Law 1): every
keyframe's COMPOSITION carries Ralph Eggleston's eye ("the world as the first character"), its STYLE carries
Patrick Lin (camera) and Jean-Claude Kalache (lighting) — see build_keyframe_prompt's own comp/style
construction, below, for the real, live text. build_plate_prompt (the once-per-scene establishing plate, a
separate function) has always independently carried the same three names via PLATE_CINEMATOGRAPHY/PLATE_
PRODUCTION_DESIGN.

CORRECTED 2026-07-14 (this docstring was itself stale — confirmed via a skill-file staleness audit that
found it still described mechanisms Law 4/29 forbid): the OLD text here said "native voice kept (Julian
swaps in CapCut); start->end frames" — the retired post-voice-swap pipeline and the retired two-keyframe-
per-shot model, neither true of the LIVE code below. The real, current recipe:
- Seedream 5 Pro / Nano Banana keyframe: character REFERENCE-ONLY (never described) + the SCENE directed
  richly & cinematically + derive from the scene MASTER for continuity.
- Seedance i2v (built elsewhere, cb_segprompt.py/Gate 3): reference-only (the keyframe carries identity);
  the acted ElevenLabs V3 track drives the render directly as @Audio1 — no native Seedance voice, no post
  swap, ever (Law 5). ONE keyframe per BEAT (its opening frame), chained off the previous beat's own settle
  — never a separate END frame per shot (rule 15/21, LOCKED 2026-07-02).

Reads the SSOT config (config/characters.json, config/locations.json) so references are
strong, complete (all characters) and never hardcoded.
"""
import json, os, re, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
def _load(name): return json.load(open(os.path.join(HERE, "config", name)))
def _load_opt(name):
    try: return _load(name)
    except Exception: return {}
CHARACTERS = _load("characters.json")
LOCATIONS  = _load("locations.json")
CONTINUITY = _load_opt("continuity.json")

# FIXED 2026-07-12 (full-codebase audit, duplication finding): this exact "who is a bee" derivation used to be
# independently recomputed in three places — a local `_bees` inside this module's own build_keyframe_prompt,
# cb_seedance.py's own module-level BEES, and cb_qa.py's own module-level BEES (all three byte-identical
# formulas) — a real risk that a future edit to one copy silently drifts from the others. This module already
# loads CHARACTERS at import time, so it's the natural single home; cb_seedance.py and cb_qa.py (both already
# `import cb_prompts as P`) now reference P.BEES instead of recomputing their own copy.
BEES = {c for c, v in CHARACTERS.items() if isinstance(v, dict) and "bee" in str(v.get("avoid", "")).lower()}

# ── THE LOCATIONS LIBRARY — signed-off scene shots, stored & reusable (the world's reference set) ──
# Parallel to the character library: when a scene shot (plate) is SIGNED OFF it is stored here keyed by
# locationId, so the same place returning later (or a new scene/episode in that world) references the
# APPROVED look — reuse + consistency, never a re-roll from scratch.
LOCLIB_DIR = os.path.join(HERE, "..", "cb-seed", "assets", "locations")        # persistent asset store (never cleared)
LOCLIB_MANIFEST = os.path.join(LOCLIB_DIR, "_manifest.json")                   # the library lives WITH the assets, not in episode config

def _loclib():
    try: return json.load(open(LOCLIB_MANIFEST)) if os.path.exists(LOCLIB_MANIFEST) else {}
    except Exception: return {}

def loclib_ref(location_id):
    """The persistent SIGNED-OFF scene shot for this locationId (a reusable reference image), or None."""
    if not location_id: return None
    e = _loclib().get(location_id)
    if e:
        p = os.path.join(LOCLIB_DIR, e["file"])
        if os.path.exists(p): return p
    return None

def register_location(location_id, name, plate_path, location="", look="", source="", episode="", scene=""):
    """Store a SIGNED-OFF scene shot into the reusable LOCATIONS LIBRARY (keyed by locationId). The manifest value
    carries the labelling fields the studio's Scenes view needs (locationId/episode/scene/updatedAt)."""
    if not location_id or not plate_path or not os.path.exists(plate_path): return None
    os.makedirs(LOCLIB_DIR, exist_ok=True)
    fname = (re.sub(r"[^A-Za-z0-9_]+", "_", location_id).strip("_") or "location") + ".png"
    shutil.copy(plate_path, os.path.join(LOCLIB_DIR, fname))
    import datetime
    lib = _loclib()
    lib[location_id] = {"file": fname, "locationId": location_id, "name": name, "location": location, "look": look,
                        "source": source, "episode": episode, "scene": scene,
                        "updatedAt": datetime.datetime.now().isoformat(timespec="seconds")}
    json.dump(lib, open(LOCLIB_MANIFEST, "w"), indent=1, ensure_ascii=False)
    return os.path.join(LOCLIB_DIR, fname)

# ── THE CHARACTER MASTER LIBRARY — the "Flow master" per character × location (the Google Flow steal) ──
# Beside the locations library: a character's BEST signed-off SOLO keyframe in a place — the one you never let drift —
# becomes that character's SUBJECT ANCHOR for every later keyframe in that location. It REPLACES the grey-bg box
# (richer: already lit, scaled and materialised here), so identity locks AND the ref count DROPS. Keyed per-location,
# so the same place returning later (a new scene/episode in that world) reuses the master automatically. Fail-open:
# no master (or a stale/retired/missing one) -> fall back to the grey-bg Character Box (today's behaviour), never error.
MASTERLIB_DIR = os.path.join(HERE, "..", "cb-seed", "assets", "masters")
MASTERLIB_MANIFEST = os.path.join(MASTERLIB_DIR, "_manifest.json")

def _masterlib():
    try: return json.load(open(MASTERLIB_MANIFEST)) if os.path.exists(MASTERLIB_MANIFEST) else {}
    except Exception: return {}

def master_ref(character, location_id, episode=""):
    """THE CHARACTER MASTER for `character` in this location (Flow's 'use this image as subject'): the signed-off SOLO
    keyframe that locks how they look HERE. Returns its path, or None -> the caller falls back to the Character Box.
    Tries the episode-specific key first, then the durable per-location key. Fail-open: None on miss / missing file /
    retired / STALE (manifest designRev != the character's current identityRev)."""
    if not (character and location_id): return None
    lib = _masterlib()
    keys = ([f"{character}@{location_id}#{episode}"] if episode else []) + [f"{character}@{location_id}"]
    rev = (CHARACTERS.get(character) or {}).get("identityRev")
    for k in keys:
        e = lib.get(k)
        if not e or e.get("status") == "retired": continue
        if rev and e.get("designRev") and e.get("designRev") != rev: continue   # design moved on -> master stale -> box
        p = os.path.join(MASTERLIB_DIR, e["file"])
        if os.path.exists(p): return p
    return None

def register_master(character, location_id, keyframe_path, episode="", scene="", beat="", scope="location", approved_by=""):
    """Snapshot a SIGNED-OFF solo keyframe into the CHARACTER MASTER library (Flow 'set as subject'), keyed
    {character}@{locationId} (+ '#{episode}' when scope='episode'). Copies the frame in (frozen), writes the manifest.
    Returns the stored path, or None if the source frame is missing."""
    if not (character and location_id and keyframe_path and os.path.exists(keyframe_path)): return None
    os.makedirs(MASTERLIB_DIR, exist_ok=True)
    ep_tag = f"_{episode}" if (episode and scope == "episode") else ""
    fname = (re.sub(r"[^A-Za-z0-9_]+", "_", f"{character}_{location_id}{ep_tag}").strip("_") or "master") + ".png"
    shutil.copy(keyframe_path, os.path.join(MASTERLIB_DIR, fname))
    import datetime
    key = f"{character}@{location_id}" + (f"#{episode}" if (episode and scope == "episode") else "")
    lib = _masterlib()
    lib[key] = {"key": key, "character": character, "locationId": location_id, "file": fname,
                "scope": scope or "location", "episode": episode, "scene": scene, "sourceBeat": beat,
                "designRev": (CHARACTERS.get(character) or {}).get("identityRev", ""),
                "approvedBy": approved_by, "status": "active",
                "updatedAt": datetime.datetime.now().isoformat(timespec="seconds")}
    json.dump(lib, open(MASTERLIB_MANIFEST, "w"), indent=1, ensure_ascii=False)
    return os.path.join(MASTERLIB_DIR, fname)

def clear_master(character, location_id, episode=""):
    """Retire a character's master for this location (-> falls back to the Character Box). Removes the episode-specific
    and durable keys + their files. Returns the count cleared."""
    lib = _masterlib(); n = 0
    for k in ([f"{character}@{location_id}#{episode}"] if episode else []) + [f"{character}@{location_id}"]:
        e = lib.pop(k, None)
        if e:
            n += 1
            try: os.remove(os.path.join(MASTERLIB_DIR, e["file"]))
            except Exception: pass
    if n: json.dump(lib, open(MASTERLIB_MANIFEST, "w"), indent=1, ensure_ascii=False)
    return n

def masters_index():
    """The whole character-master library (for the studio to display + audit)."""
    return _masterlib()

def vision_for(episode, shot_code):
    """If this shot is a declared vision/flashback of a later real scene, return its link (else None)."""
    for v in CONTINUITY.get(episode, {}).get("visions", []):
        if v["shot"] == shot_code:
            return v
    return None

# The world-class look (rich cinematic) — applied to the SCENE, never the character.
STYLE = ("Premium 3D CGI, Pixar/DreamWorks FEATURE quality — soft global illumination, subsurface scattering on plush "
         "fur, large expressive stylized eyes (NOT photoreal), volumetric god-rays, warm rim-light, cinematic shallow "
         "depth of field, rich layered depth, floating light motes, the aquamarine crystal-magic glow; soft, magical, "
         "cinematic — never flat or harsh.")

# CANON — how an Aida vision is FRAMED (locked, every episode). The vision FILLS the frame; we never see
# the real scene around it. It is her POV INTO the vision, not a bubble sitting inside a shot.
VISION_FRAME = ("THE VISION FILLS THE ENTIRE FRAME — this is Aida's point of view looking INTO the vision, NOT a "
                "small bubble sitting inside a wider scene. The dreamlike vision content occupies the WHOLE image. The "
                "glowing curved edge of the vision-orb and its soft rose-pink haze sit only at the very MARGINS of the "
                "frame and dissolve into soft darkness and mist on every side — mysterious. We do NOT see the real world, "
                "the sanctuary, Aida, or ANY surroundings around the orb; nothing is visible on either side of the bubble. "
                "The frame IS the inside of the bubble.")

def scene_cfg(episode, scene_num):
    return LOCATIONS[episode][str(scene_num)]

# ── SCENE-CACHE FRESHNESS (T33 Ruling 3, 2026-07-02, Julian) ──────────────────────────────────────────────────────
# config/locations.json (LOCATIONS above) is a SNAPSHOT of each scene's descriptive fields, cached for fast lookup —
# but the beat package's own scenes[] array is the actual single source of truth (the Director's Gate-1 output). The
# 2026-07-02 find: a beat-package scene edit silently never reached scene_cfg()'s callers (keyframe/plate/Seedance
# prompts) because nothing ever re-synced this cache — a stale snapshot diverged from its source with no signal at
# all. Same discipline as tools/sync_canon.py (source hash vs copy hash), extended to scene data: a mismatch is now
# a detectable, blockable condition, not a silent divergence.
SCENE_SYNC_FIELDS = ("name", "locationId", "sceneShotName", "time", "weather", "location", "look",
                     "lighting", "definingFeature", "colorTemperature", "lens", "cameraHeight")

def _scene_source_hash(scene):
    """Canonical hash of a scene dict's SYNCED fields only (excludes cache-only bookkeeping like `master`/
    `updatedAt`/`_sourceHash` itself, and beat-package-only story fields like `cast`/`pillar`/`intensity`/
    `emotionalCore` that config/locations.json was never meant to mirror) — so the beat package's raw scene dict and
    its locations.json snapshot hash identically when they genuinely agree, in either representation's native shape."""
    import hashlib
    projected = {k: scene.get(k) for k in SCENE_SYNC_FIELDS}
    return hashlib.sha256(json.dumps(projected, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]

def _resolve_beat_pkg(episode):
    """The episode's current beat package, resolved by glob (mirrors cb_pipeline._resolve_pkg, parameterised by
    episode so this works for the freshness check regardless of which episode is active)."""
    import glob
    cands = (glob.glob(os.path.join(HERE, "..", "cb-output", f"{episode}_*beat_package.json"))
             or glob.glob(os.path.join(HERE, "..", "cb-output", f"{episode}_*shot_package.json")))
    return max(cands, key=os.path.getmtime) if cands else None

def scene_cache_stale(episode, scene_num, pkg_path=None):
    """None if config/locations.json's cached scene matches its beat-package source; otherwise a short string
    describing the mismatch (missing hash = never synced; hash mismatch = the source has since changed underneath
    it). Fails LOUD by design — a stale/unsynced scene cache is exactly the bug this closes, so silence here would
    just reintroduce it. `pkg_path` can be supplied when the caller already resolved it (avoids a second glob)."""
    cached = (LOCATIONS.get(episode) or {}).get(str(scene_num))
    if cached is None:
        return f"no cached scene {scene_num} for {episode} in config/locations.json at all"
    pkg_path = pkg_path or _resolve_beat_pkg(episode)
    if not pkg_path or not os.path.exists(pkg_path):
        return None                                    # no beat package to compare against — nothing to detect drift from
    try:
        d = json.load(open(pkg_path))
    except Exception:
        return None                                    # an unreadable package can't be compared; not this check's job to fail on that
    src = next((s for s in (d.get("scenes") or []) if str(s.get("sceneNumber")) == str(scene_num)), None)
    if src is None:
        return None                                    # scene not in this package (e.g. a different episode's number) — not a mismatch
    want = _scene_source_hash(src)
    got = cached.get("_sourceHash")
    if got is None:
        return f"scene {scene_num} cache has never been synced (run tools/sync_scenes.py)"
    if got != want:
        return f"scene {scene_num} cache is STALE (hash {got} != source {want} — run tools/sync_scenes.py)"
    return None

def location_history(episode, scene_num):
    """STATEFUL LOCATIONS — a place remembers. For a RETURNING location (a scene whose `locationId`
    appeared in an EARLIER scene), return the location's LAST-SEEN state (the most recent earlier
    same-id plate that exists) + the accumulated `worldState` changes up to this scene. The returning
    scene's plate derives from that last state, not the original anchor. Returns (prior_plate|None, [change,...]).
    FIXED 2026-07-12 (Julian, live review — the plate reading as too tight, traced back to this function):
    the `changes` filter used to be `atScene/atShot <= scene_num` — so a world-state change authored to occur
    WITHIN this scene's own beats (e.g. Scene 1's own storm-pressure shift, tagged atScene:"1", meant to arrive
    only by 1.B4/1.B5) got folded into THIS SAME SCENE's own opening establishing plate, and separately made
    build_plate_prompt treat a scene's own FIRST-EVER plate as a "RETURNING location... reference image is its
    LAST-SEEN state" (wrong: there is no earlier occurrence to return to, and no earlier same-episode plate —
    prior_plate was None the whole time). A change only genuinely belongs to "what this location currently
    shows" once a scene STRICTLY AFTER the one it's tagged to has actually happened — never the tagged scene's
    own opening shot, which the change hasn't occurred in yet. `<=` -> `<` closes this; the returning/library-
    reference distinction this function's own docstring already describes now actually holds for a scene's own
    first appearance, matching build_plate's existing `if prior_plate: ... elif lib_ref: ...` design intent."""
    locs = LOCATIONS.get(episode, {})
    sc = locs.get(str(scene_num), {})
    lid = sc.get("locationId")
    if not lid:
        return None, []
    earlier = sorted([int(k) for k, v in locs.items()
                      if k.isdigit() and v.get("locationId") == lid and int(k) < int(scene_num)], reverse=True)
    prior_plate = None
    for e in earlier:
        p = f"media/{episode}_S{e}_plate.png"
        if os.path.exists(p):
            prior_plate = p; break
    changes = []
    for w in CONTINUITY.get(episode, {}).get("worldState", []):
        if w.get("locationId") != lid:
            continue
        at = str(w.get("atScene") or str(w.get("atShot", "0")).split(".")[0])
        if at.isdigit() and int(at) < int(scene_num):
            changes.append(w["change"])
    return prior_plate, changes

def char_refs(shot, anchors=True):
    """References for the shot's characters. anchors=True → include each character's main anchor image;
    anchors=False → SKIP the main anchors (used when the scene CHARACTER SHEET is the single identity+size
    authority, so we don't dilute with redundant per-character anchors) but KEEP item refs (wristbands)."""
    refs = []
    for c in shot.get("characters", []):
        cc = CHARACTERS.get(c)
        if not cc:
            raise KeyError(f"character '{c}' not in config/characters.json — add its anchor before building")
        if anchors and cc["anchor"] not in refs:
            refs.append(cc["anchor"])
        if c == "Keen":
            wb = shot.get("keenWristbands", "none")
            for r in cc.get("wristband_states", {}).get(wb, []):
                if r not in refs: refs.append(r)
    return refs

# Physics realism — mainly an i2v concern, but a still can clip too (the Scene-2 wand-through-bowl bug).
PHYSICS = ("Physics must be correct and believable: everything is SOLID — no object or limb passes through "
           "another; contact is real (a wand/mallet strikes and rests ON the rim of the bowl, never clipping "
           "through it; paws grip objects rather than intersect them; feet rest on the ground); respect gravity, "
           "weight and momentum; water, cloth and fur settle naturally.")

def size_line(shot):
    """SIZE continuity from the chart (characters.json sizeRank + size). Fires for EVERY shot:
    multi-character → relative order; SOLO → the character's absolute size anchored to true scale + known
    props, so a lone character is never rendered too small (the Aida-looks-small bug)."""
    chars = shot.get("characters", [])
    ranked = sorted([(c, CHARACTERS[c]) for c in chars if c in CHARACTERS and CHARACTERS[c].get("sizeRank")],
                    key=lambda x: -x[1]["sizeRank"])
    out = []
    if len(ranked) >= 2:
        perchar = []
        for c, cc in ranked:
            ref = cc.get("sizeRef")
            if ref and ref in CHARACTERS:
                perchar.append(f"{c} is EXACTLY the same size as {ref} on the chart (adult-female reference)")
            else:
                perchar.append(f"{c} is EXACTLY {c}'s own fixed size on the chart")
        out.append("SIZE — anchor EACH character to their OWN fixed canonical size on the SIZE CHART; do NOT invent "
                   "a size for anyone, and do NOT flatten or exaggerate any difference: " + "; ".join(perchar)
                   + ". The chart shows them to scale — match each one's absolute height and build to it exactly "
                   "(Keen stays Keen's size, the adult females stay Aida's size)")
        if "Fuzzby" in chars and "Zenny" in chars:
            out.append("Fuzzby is the BIGGER bee, Zenny the SMALLER")
    elif len(ranked) == 1:
        c, cc = ranked[0]
        ref = cc.get("sizeRef")
        anchor = (f"the SAME size as {ref} on the chart" if ref and ref in CHARACTERS else f"{c}'s own fixed size on the chart")
        out.append(f"SIZE — render {c} at {anchor} ({cc['size']}); give {c} real presence and correct "
                   f"proportions, do NOT shrink {c} (even in a wide shot); use any in-shot prop of known size to gauge scale")
    return (" " + "; ".join(out) + ".") if out else ""

def _shotord(scene, code):
    """Comparable (scene, [part,...]) ordinal for BOTH legacy shot codes ("3.1") and beat-native codes ("3.B1") —
    strips any letter prefix per dot-part (B1 -> 1) so continuity timing actually resolves. Before this fix, a plain
    `int(x)` on a beat-native part like "B1" ALWAYS raised (no letters allowed) and silently fell back to (0,[0]) for
    EVERY beat-native comparison — meaning worn_line/recurring_line/persistent_for's "has this item appeared yet by
    THIS shot" checks were structurally broken for every beat package, not just uncalled from one function."""
    try:
        parts = [int(re.sub(r"\D", "", x) or "0") for x in str(code).split(".")]
        return (int(scene), parts)
    except Exception:
        return (0, [0])

def persistent_for(episode, shot, asset_name):
    """CUMULATIVE state — items that entered the world earlier and PERSIST in/with an asset (e.g. the parcel
    Keen loads into the boat at 3.1 stays in the boat for every later shot, and accumulates). The state grows
    shot to shot and is never dropped."""
    cur = _shotord(shot.get("sceneNumber"), shot.get("shotCode"))
    out = []
    for p in CONTINUITY.get(episode, {}).get("persistent", []):
        if p.get("in") != asset_name: continue
        fs = str(p.get("fromShot", "")); fscene = fs.split(".")[0]
        if cur >= _shotord(fscene, fs): out.append(p["item"])
    return out

def _lost_at(episode, name):
    for l in CONTINUITY.get(episode, {}).get("lost", []):
        if l["name"] == name: return l
    return None

def worn_line(episode, shot):
    """Character-CARRIED continuity (satchel, etc.) — gain + loss attached to a character, not an asset.
    An item worn `on` a character stays consistent in EVERY shot with that character from fromShot to
    untilShot. Stops the satchel flickering on and off."""
    chars = shot.get("characters", [])
    cur = _shotord(shot.get("sceneNumber"), shot.get("shotCode"))
    out = []
    for p in CONTINUITY.get(episode, {}).get("persistent", []):
        who = p.get("on")
        if not who or who not in chars: continue
        fs = str(p.get("fromShot", ""))
        if fs and cur < _shotord(fs.split(".")[0], fs): continue
        ut = p.get("untilShot")
        if ut and cur > _shotord(str(ut).split(".")[0], ut): continue
        out.append(f"{who} {p.get('verb','carries')} {p['item']}")
    return (" CARRIED ITEMS (consistent in every shot — never add or drop): " + "; ".join(out) + ".") if out else ""

def items_for(episode, shot):
    """Hero ITEMS with a specific reference design (e.g. the vacant wristbands) — attach their REFERENCE
    image and lock to it whenever the item appears in a shot, regardless of who is holding/wearing it.
    Returns (ref_image_paths, lock_lines). This closes the gap where an item appears without its owner
    in frame (e.g. Mum holding Keen's wristbands) so it was never reference-checked."""
    code = shot.get("shotCode"); sn = str(shot.get("sceneNumber"))
    ref_imgs = []; locks = []
    for it in CONTINUITY.get(episode, {}).get("items", []):
        shots = it.get("shots"); scenes = [str(x) for x in it.get("scenes", [])]
        if (code in shots) if shots else (sn in scenes):
            if it.get("ref"): ref_imgs.append(it["ref"])
            locks.append(f"the {it['name']} — EXACTLY as its reference image: {it.get('appearance','')}".rstrip(": "))
    return ref_imgs, locks

def recurring_line(episode, shot):
    """Lock the look of recurring assets present in this shot, carry forward their persistent contents,
    and FORBID assets that were lost/destroyed earlier (e.g. the boat after Keen loses it in the storm)."""
    code = shot.get("shotCode"); sn = str(shot.get("sceneNumber")); cur = _shotord(sn, code)
    out = []
    for r in CONTINUITY.get(episode, {}).get("recurring", []):
        if not r.get("appearance"):
            continue
        shots = r.get("shots")
        match = (code in shots) if shots else (sn in [str(x) for x in r.get("scenes", [])])
        lost = _lost_at(episode, r["name"])
        if lost and cur > _shotord(str(lost["atShot"]).split(".")[0], lost["atShot"]):
            continue  # gone — the negative below forbids it
        if match:
            line = f"{r['name']} is {r['appearance']}"
            if r.get("scale"): line += f" — SIZE LOCK: {r['scale']}, identical to the master frame"
            if r.get("orientation"): line += f" — ORIENTATION: {r['orientation']}"
            if r.get("position"): line += f" — POSITION LOCK: {r['position']}"
            held = persistent_for(episode, shot, r["name"])
            if held: line += " — and it STILL contains (loaded in an earlier shot, must remain present): " + "; ".join(held)
            out.append(line)
    # negatives: anything lost earlier must NOT appear (regardless of the scenes list)
    for l in CONTINUITY.get(episode, {}).get("lost", []):
        if cur > _shotord(str(l["atShot"]).split(".")[0], l["atShot"]):
            out.append(f"NO {l['name']} anywhere in frame — {l.get('reason','it was lost')}; it is gone and must NOT appear")
    return (" " + "; ".join(out) + ".") if out else ""

def props_block(shot):
    """Per-shot PROP STATE — exact position/state of each prop, so it stays continuous shot-to-shot
    (never vanish, teleport, float or duplicate). e.g. the wand in Aida's paw (2.1) -> set down on the
    bowl's rim (2.3)."""
    pr = shot.get("props")
    if not pr: return ""
    parts = [f"{p['name']} — {p['state']}" for p in pr if p.get("name") and p.get("state")]
    if not parts: return ""
    return (" PROPS (exact state & position, continuous from the previous shot — never vanish, teleport, "
            "float or duplicate): " + "; ".join(parts) + ".")

def identity_line(shot):
    """Structural IDENTITY LOCK — each character's signature features (from characters.json key_features),
    reinforced on every shot so the reference-only anchor can't silently drop them (e.g. Keen's head tuft).
    This is config-driven, applied everywhere — not a per-prompt description."""
    chars = [c for c in shot.get("characters", []) if CHARACTERS.get(c)]
    if not chars:
        return ""
    return (" IDENTITY LOCK: each character is EXACTLY their reference image — copy " + ", ".join(chars)
            + " 100% from their references, every signature feature included; never simplify, drop, swap or re-interpret "
            "a feature, and never paint them from words.")

def _band_line(shot):
    if "Keen" not in shot.get("characters", []): return ""
    return {"none":   "Keen wears no cuffs (bare wrists)",
            "vacant": "Keen is wearing the cuffs shown in the cuffs reference — vacant, no crystal set",
            "crystal":"Keen is wearing the cuffs shown in the cuffs reference — crystal-set"
            }.get(shot.get("keenWristbands", "none"), "")

def _fix_line(note):
    note = (note or "").strip()
    return (f" CORRECTIONS — the previous render was WRONG. Fix exactly these and change nothing else: {note}" if note else "")

def size_chart_ref():
    """The optional bear SIZE-CHART image (all bears drawn to scale) — the reliable scale authority for
    relative sizes. Returns its path if present (drop it at cb-seed/assets/CB_size_chart.*), else None."""
    import glob
    for p in sorted(glob.glob(os.path.join(HERE, "..", "cb-seed", "assets", "CB_size_chart.*"))):
        return p
    return None

def _turn4_ref(cc):
    """PREFERRED character identity lock = the clean LoRA-built 4-way turnaround (front/side/back/side):
    the `turn4` field, else a turn4 file in refs, else the legacy turnaround grid. The old multi-view grid
    GENERICISED identity (Nano can't lock a face from a busy row of tiny views — it averages it into a
    plain bee/bear); the clean 4-way is the PROVEN reference that holds identity AND carries every angle."""
    rl = cc.get("refs") or []
    return (cc.get("turn4")
            or next((r for r in rl if "turn4" in r.lower()), None)
            or next((r for r in rl if "turnaround" in r.lower()), None))

def char_identity_ref(c):
    """STRICT production identity reference for character `c` = its clean 4-way turnaround (turn4).
    LOCK: the legacy multi-view turnaround GRID is FORBIDDEN here — feeding a busy row of tiny views makes
    Nano AVERAGE the face into a generic bee/bear (the "it's wrong" failure). A shot CANNOT render until
    every character has a turn4. Raises a clear, actionable error otherwise — the gate stays SHUT rather
    than silently shipping a wrong face."""
    cc = CHARACTERS.get(c)
    if not cc:
        raise KeyError(f"LOCK: character '{c}' not in config/characters.json")
    # PREFER a single clean render reference (render_ref) — Nano caps inputs at 3072px and tiles at 768px, so a
    # SINGLE front view fills the frame with readable detail, where a busy multi-view sheet collapses each view to
    # one fuzzy tile and the face drifts. Fall back to turn4 / a turn4 file if no render_ref is set.
    ref = (cc.get("render_ref") or cc.get("turn4")
           or next((r for r in (cc.get("refs") or []) if "turn4" in r.lower()), None)
           or cc.get("anchor"))   # LAST RESORT: the single clean front-view anchor. A single front view is exactly
                                  # what Nano reads best (the doctrine above), so it is FAR better than failing the
                                  # character pull — every character in the section that has an anchor now pulls.
    if not (ref and os.path.exists(ref)):
        raise FileNotFoundError(
            f"LOCK: '{c}' has NO usable identity reference on disk (render_ref / turn4 / anchor all missing or not "
            f"found). Add a clean front (or front+back) reference for {c} to config/characters.json.")
    return ref

def char_identity_refs(c):
    """THE CHARACTER BOX for `c` — the curated set of clean single-view references that get pulled BY NAME into every
    keyframe (Flow-style "add a character → it pulls the character's images"). On NANO the box is deliberately a
    CURATED FEW (front + back; 2–4 views max): Nano reads a handful of full-frame views well, but feeding it a big
    PILE of images makes it average the face into a generic blob — that averaging IS the drift. So the box is the BEST
    readable views, not every image. Precedence: explicit `box` list in config > frontRef + backRef > combined turnaround.
    To enrich a character's box, add a `box` array of clean single-view files in config/characters.json."""
    cc = CHARACTERS.get(c) or {}
    turn = cc.get("turnaround")                                          # LOCKED model sheet (Julian's directive) — wins
    if turn and os.path.exists(turn):
        return [turn]
    box = [r for r in (cc.get("box") or []) if r and os.path.exists(r)]   # explicit managed box
    if box:
        return box
    pair = [r for r in (cc.get("frontRef"), cc.get("backRef")) if r and os.path.exists(r)]
    return pair if pair else [char_identity_ref(c)]

def opening_cast(shot):
    """Who is ACTUALLY in the OPENING frame — so the keyframe only pulls the Character Box for who's on screen.
    The keyframe is the FIRST frame of the beat; a character the beat brings in LATER (startState: "Zenny is not yet
    in frame") must NOT have her box fed to Nano, or Nano will draw her into a frame she isn't in.
    Precedence: explicit `openingCast` (names exactly who's framed) > the full cast minus `notInFrame` minus anyone
    the startState explicitly says is absent. Conservative — a character is dropped ONLY on an explicit absence cue
    (never on mere omission), and the list is never returned empty."""
    allc = []
    for c in (list(shot.get("characters") or []) + list(shot.get("extraChars") or [])):
        if c and c not in allc:
            allc.append(c)
    oc = shot.get("openingCast")
    if oc:
        framed = [c for c in allc if c in oc]
        return framed or allc
    absent = set(shot.get("notInFrame") or [])
    ss = (shot.get("startState") or "")
    if ss:
        ABSENT = ("not yet in frame", "not in frame", "not yet in shot", "not in shot", "off-screen", "off screen",
                  "out of frame", "off-frame", "off frame", "out of shot", "off-camera", "off camera", "out of view",
                  "hasn't arrived", "has not arrived", "yet to enter", "not yet arrived", "not present", "hasn't entered")
        for clause in re.split(r"[.;]", ss):
            cl = clause.lower()
            if any(p in cl for p in ABSENT):
                for c in allc:
                    if c.lower() in cl:
                        absent.add(c)
    framed = [c for c in allc if c not in absent]
    return framed or allc

def _expression_mood(shot):
    """The EXPRESSION & MOOD line — weaves a beat's emotional read (feeling + performance surface/underneath) into its
    OPENING keyframe so each is DISTINCT. SHARED by build_keyframe_prompt AND build_vision_prompt (engine-wide, every
    beat; the action lives in the Seedance clip, so the keyframe's distinctiveness is the emotion). Empty when the beat
    carries no emotion data (so a thin beat just omits it rather than erroring).
    innerThought is deliberately NOT read here — it is the actor's monologue for the i2v/motion performance, not the
    still frame (see the comment at perf_block); folding it in here would blur that line."""
    perf = shot.get("performance") if isinstance(shot.get("performance"), dict) else {}
    feel = (shot.get("physicalFeeling") or shot.get("feelMoment") or shot.get("emotionalIntent") or "").strip().rstrip(".")
    surf = str(perf.get("surface") or "").strip().rstrip(".")
    under = str(perf.get("underneath") or "").strip().rstrip(".")
    truth = (shot.get("crystalTruth") or "").strip().rstrip(".")
    aft = (shot.get("audience_feeling_target") or "").strip().rstrip(".")
    segs = (([feel + "."] if feel else []) + (["Surface: " + surf + "."] if surf else [])
            + (["Underneath: " + under + "."] if under else []) + (["Crystal truth: " + truth + "."] if truth else [])
            + (["The audience should feel: " + aft + "."] if aft else [])
            + (["This is the held, wordless, stillness-carries-it moment — no dialogue; the silence and the body "
                "language do all the work."] if shot.get("wordlessHeld") else []))
    return ("EXPRESSION & MOOD (the opening read — show it in the faces and body language; this is the FIRST frame, before "
            "the action): " + " ".join(segs)) if segs else ""

_TEMP_STATE_RE = re.compile(r"\b(pollen|dust(?:ed|y)?|cak(?:ed|ing)|dirt(?:y)?|mud(?:dy)?|\bwet\b|smear(?:ed)?|moustache)\b", re.I)
def _strip_temp_state(t):
    """Drop any WHOLE SENTENCE naming a temporary body-state (pollen, dirt, wet fur, a moustache of dust, etc.) from
    text that will feed the per-character keyframe staging — CLEAN BASE IDENTITY forbids exactly these, so asserting
    one positively here would contradict that constraint inside the SAME prompt. Whole-sentence (not sub-clause)
    removal keeps the surviving text grammatically clean. Never returns empty (falls back to the original) — a
    startState that is ENTIRELY about a temporary state is rare, and dropping ALL staging would be worse than the
    contradiction this guards against."""
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", t or "") if s.strip()]
    kept = [s for s in sentences if not _TEMP_STATE_RE.search(s)]
    return " ".join(kept) if kept else t

def build_keyframe_prompt(shot, sc, master_path=None, note="", episode="Ep1", chain_ref=None, end_beat=False):
    """Nano Banana keyframe. Returns (prompt, refs).
    master_path None => establishing/master shot (compose from anchors + location).
    master_path set  => DERIVE this shot from the master (lock world; only framing/action change).
    end_beat set     => this is the shot's END frame — built the SAME clean way as the start (fresh from refs),
                        never composited against the start frame (see build_end_prompt's own docstring for why).
    note => a correction from the human review, appended as a high-priority fix."""
    # FIXED 2026-07-12 (full-codebase audit continued): dropped the `end_from` parameter — it was accepted
    # and documented ("PLUS the start frame as a labelled MOTION ANCHOR") but never once read in this
    # function's body (only the separate `end_beat` boolean actually gates anything below); no caller
    # anywhere in engine/ ever passed it either. The promised behaviour was also stale: build_end_prompt's
    # own inline comment explains that approach was deliberately abandoned after it caused motion-blur/
    # drift on real renders (fresh-from-refs holds identity better). A future maintainer reading the old
    # docstring in isolation would believe the start frame was being fed in as a visual reference when it
    # demonstrably wasn't — removed rather than wired up, since the abandoned behaviour is not wanted back.
    # ── REFERENCE IMAGES, by ROLE ("[Image N: filename] — ROLE"). ONE shot = TWO boundary frames:
    #    START frame refs = scene plate + each character's TURNAROUND (front/side/back).
    #    END   frame refs = the accepted START frame (PRIMARY anchor, Image 1) + scene plate + the same turnaround(s).
    # THE CHARACTER BOX is pulled only for who's actually in the OPENING frame (the keyframe is the first frame) — a
    # character the beat brings in later (startState: "Zenny is not yet in frame") must NOT have her box fed to Nano.
    chars = opening_cast(shot)
    refs = []
    def _img(path):
        refs.append(path); return len(refs)
    scene_ref = master_path or sc.get("master")
    loc_id = sc.get("locationId")
    # per-beat extra scene shot(s) — e.g. the PIER inside Aida's vision — OVERRIDE this beat's scene plate
    beat_scenes = []
    for xs in (shot.get("extraScenes") or []):
        if not xs: continue
        base = os.path.basename(xs)
        for cand in (xs, os.path.join("..", xs), os.path.join("media", base),
                     os.path.join("..", "cb-seed", "assets", base),
                     os.path.join("..", "cb-seed", "assets", "ep1", base)):
            if cand and os.path.exists(cand):
                if cand not in beat_scenes: beat_scenes.append(cand)
                break
    # ── REFERENCES, in the order Nano receives them: each in-frame CHARACTER FIRST (one identity image — its master if
    #    one is set, else the locked turnaround), then any PROP, then the ENVIRONMENT plate LAST.
    char_img = {}
    for c in chars:
        cm = master_ref(c, loc_id, episode)            # the character MASTER (an in-world frame), if one is set
        crefs = char_identity_refs(c)                  # else the locked turnaround (char_identity_refs prefers it)
        identity = cm or (crefs[0] if crefs else None)
        if not identity:
            continue
        char_img[c] = (refs.index(identity) + 1) if identity in refs else _img(identity)
        if c == "Keen":                                 # Keen's cuffs are a tracked STORY STATE (none/vacant/crystal,
            wb = shot.get("keenWristbands", "none")     # T ruling: one character, two states) — attach its own
            for r in CHARACTERS["Keen"].get("wristband_states", {}).get(wb, []):  # reference image so the state the
                if r not in refs: _img(r)                                          # Director picked actually renders
    for r in (items_for(episode, shot)[0] or []):      # props (rare) — after the characters
        if r and r not in refs:
            _img(r)
    for extra in (beat_scenes[1:] if beat_scenes else []):
        if extra not in refs:
            _img(extra)
    # CASCADE (Lock & Chain): a CONTINUATION beat (chain_ref set) locks to the PREVIOUS approved frame, which becomes a
    # separate "Continuity Reference" image (the LAST image) — NOT the plate. The format is continuation-format by POSITION
    # (whenever chain_ref is supplied), independent of whether that frame is rendered yet: the file attaches once it exists;
    # before then the preview shows the SAME structure with the Continuity Reference marked pending.
    chained = bool(chain_ref)                                  # a continuation beat (vs an anchor)
    chain_present = chained and os.path.exists(chain_ref)
    chain_img = (_img(chain_ref) if chain_present else (len(refs) + 1)) if chained else None
    # the plate/scene env image is used ONLY for an anchor beat — a continuation inherits the environment from the chain frame.
    env_ref = None if chained else (beat_scenes[0] if beat_scenes else (scene_ref if (scene_ref and os.path.exists(scene_ref)) else None))
    env_img = ((refs.index(env_ref) + 1) if env_ref in refs else _img(env_ref)) if env_ref else None
    # ── MANUAL OVERRIDE: a human-edited exact prompt ("Save & use this exact prompt") is sent VERBATIM (refs still
    # attach). GATED BEHIND EXPLICIT CONFIRMATION (2026-07-14, CLAUDE.md rule 82/83's own named-auteur-per-chair
    # doctrine — Julian: "keep them for genuine edge cases, but require an explicit confirmation... flag it
    # visibly so it's never silent"): this text used to ship unconditionally the moment it was non-empty,
    # completely bypassing Eggleston/Lin/Kalache's compiled voice (build_keyframe_prompt's own composition/
    # style text, below) with zero record that a bypass happened. An override left over from an earlier
    # experiment, or pasted in by accident, used to ship silently forever. Now requires the SAME beat to also
    # carry `keyframePromptOverrideConfirmed: true` — an override with no confirmation is treated as if it
    # were never set (falls through to the real DP compiler below), not as a partial/best-effort use.
    _ovr = str(shot.get("keyframePromptOverride") or "").strip()
    if _ovr:
        if shot.get("keyframePromptOverrideConfirmed"):
            print(f"  ⚠ GATE 2 BYPASSED for {shot.get('beatCode') or shot.get('shotCode') or '(beat)'} — "
                  f"a confirmed keyframePromptOverride is shipping VERBATIM, skipping the DP's own compiled "
                  f"composition/style (Eggleston/Lin/Kalache) entirely.", flush=True)
            return _ovr, refs
        print(f"  keyframePromptOverride present but NOT confirmed for "
              f"{shot.get('beatCode') or shot.get('shotCode') or '(beat)'} — ignoring it, compiling the real "
              f"DP prompt instead. Set keyframePromptOverrideConfirmed: true to intentionally ship it.", flush=True)
    # ── THE LOCKED GATE-2 KEYFRAME PROMPT — Julian's canonical Nano Banana 2 template (2026-06-28): a REFERENCE IMAGES
    #    header (one role line per image) then the PROMPT body. As many CHARACTER references as characters in the shot;
    #    the Director's beat supplies the action / environment / shot / lighting. Identity comes ENTIRELY from the images.
    idx_char = {v: k for k, v in char_img.items()}                     # image number -> character
    ref_lines = []
    for i in range(1, len(refs) + 1):
        if i in idx_char:
            # Hardened 2026-07-04 (Julian, after a real re-mint drift on this exact class of gap — an
            # accessory's colour hallucinated because the identity-lock text never named accessories at
            # all): identity means EVERY visible thing the reference shows, not just the face.
            ref_lines.append(f"[Image {i}] — {idx_char[i]} Reference: Maintain this character's exact identity as "
                              f"shown — facial features, proportions, AND every accessory exactly as the reference "
                              f"shows it (glasses frame colour and shape, clothing, held objects, or any other "
                              f"worn/carried item).")
        elif i == chain_img:
            ref_lines.append(f"[Image {i}] — Atmosphere Reference: Match the lighting, colors, and environmental textures of this image, but DO NOT copy the camera framing or character poses.")
        elif i == env_img:
            ref_lines.append(f"[Image {i}] — Scene Plate (the empty set): the EXACT location — composite the characters INTO it; reproduce its layout, set dressing, depth and lighting unchanged, adding only the characters.")
        else:
            ref_lines.append(f"[Image {i}] — Prop Reference: reproduce this object exactly as shown.")
    if chained and not chain_present:        # continuation whose previous frame isn't rendered yet (preview only — file attaches at generation)
        ref_lines.append(f"[Image {chain_img}] — Atmosphere Reference (the previous beat's approved frame — attaches once it is rendered): match its lighting, colors and textures; DO NOT copy its framing or poses.")
    header = "REFERENCE IMAGES:\n" + "\n".join(ref_lines)
    # cuts[0] is the Director's OWN first-shot direction for this beat — richer and more specific than startState
    # (which tends toward a generic "both hovering" template repeated beat to beat with only mood-adjectives
    # changed). The keyframe IS the beat's opening frame, and cuts[0] IS the beat's opening cut, so its action text
    # is the correct, more varied source; startState remains the fallback for a beat with no cuts authored yet.
    _cut0 = (shot.get("cuts") or [{}])[0] if not end_beat else {}
    text = ((shot.get("action") if end_beat else (_cut0.get("action") or shot.get("startState") or shot.get("action"))) or "").strip()
    text = _strip_temp_state(text)   # CLEAN BASE IDENTITY (below) FORBIDS a temporary body-state (pollen, dirt, wet
                                      # fur…); asserting it POSITIVELY in a per-character block a few lines below
                                      # would contradict that constraint in the SAME prompt call. Drop it here instead
                                      # — Seedance is what applies these states, within the take, not the keyframe.
    block_chars = [c for c in chars if c in char_img]
    def _named_in(s):
        return [c for c in block_chars if re.search(r"(?<!\w)" + re.escape(c) + r"(?!\w)", s, flags=re.I)]
    # Split the action into per-character UNITS: first by sentence, then — when ONE sentence names ≥2 in-frame
    # characters ("Fuzzby on the left…, Zenny on the right…") — by character-NAME boundary, so each character's
    # block carries ONLY its own staging. Without this, a two-character sentence was dumped wholesale into the
    # longest name's block (Fuzzby got Zenny's blocking; Zenny fell back to a generic "in frame" line).
    # Overlapping names (e.g. "Keen" ⊂ "Keen's Mum") resolve to the LONGEST name at that position.
    def _split_ok(s, pos):
        """A name starts a NEW staging clause only at the sentence start or after a clause boundary (,;:. or a
        joining conjunction) — NOT mid-phrase as an object ("…looking at Fuzzby"), which must stay in its clause."""
        pre = s[:pos].rstrip()
        if not pre:
            return True
        if pre[-1] in ",;:.":
            return True
        return bool(re.search(r"(?:^|\W)(?:and|but|then|while|as)$", pre, flags=re.I))
    def _units(t):
        """[(owner, clause)] — each clause owned by its SUBJECT (the name at the split point), so a clause that
        merely MENTIONS another character ("Zenny … looking at Fuzzby") stays Zenny's, not Fuzzby's."""
        out = []
        for s in [x.strip() for x in re.split(r"(?<=[.!?])\s+", t) if x.strip()]:
            raw = sorted((m.start(), m.end(), c) for c in block_chars
                         for m in re.finditer(r"(?<!\w)" + re.escape(c) + r"(?!\w)", s, flags=re.I))
            pts = []
            for pos, endp, c in raw:
                if pts and pos < pts[-1][1]:                    # overlap (Keen ⊂ Keen's Mum) → keep the longest name
                    if (endp - pos) > (pts[-1][1] - pts[-1][0]):
                        pts[-1] = (pos, endp, c)
                    continue
                if _split_ok(s, pos):
                    pts.append((pos, endp, c))
            if len(pts) <= 1:
                nm = _named_in(s)
                out.append((pts[0][2] if pts else (max(nm, key=len) if nm else None), s)); continue
            # LIST + SHARED action ("Aida, Howey, Misty and Luna stand in a circle") — names are consecutive (only
            # separators between them) → give EACH character the shared predicate, never a bare name.
            if all(re.fullmatch(r"[\s,;]*(?:and|&)?[\s,;]*", s[pts[i][1]:pts[i + 1][0]], flags=re.I)
                   for i in range(len(pts) - 1)):
                pred = re.sub(r"^[\s,;]*(?:and\b)?[\s,;]*", "", s[pts[-1][1]:]).strip(" ,;.")
                for pos, endp, c in pts:
                    out.append((c, (c + " " + pred).strip()))
                continue
            # MIXED case: a LEADING list run ("as Fuzzby and Zenny weave…") shares a predicate, but the SAME sentence
            # then splits into genuinely separate per-character clauses later ("…; Zenny's path is precise while
            # Fuzzby zig-zags…"). The whole-sentence check above only catches a PURE list; without this, the
            # PARALLEL loop below would split at each name in the list too, handing the shared predicate to only the
            # LAST name in the run and leaving the earlier name(s) a bare, contentless clause (the source of a
            # "Fuzzby Fuzzby zig-zags…" duplicate once _pose() joins it with that name's real clause).
            run = 0
            while (run + 1 < len(pts) and
                   re.fullmatch(r"[\s,;]*(?:and|&)?[\s,;]*", s[pts[run][1]:pts[run + 1][0]], flags=re.I)):
                run += 1
            if run > 0:
                pred_end = pts[run + 1][0] if run + 1 < len(pts) else len(s)
                pred = re.sub(r"[\s,;]*(?:\band\b|\bbut\b|\bthen\b|\bwhile\b|\bas\b)?[\s,;]*$", "",
                              s[pts[run][1]:pred_end]).strip(" ,;")
                for pos, endp, c in pts[:run + 1]:
                    out.append((c, (c + " " + pred).strip()))
                pts = pts[run + 1:]
                if not pts:
                    continue
            for i, (pos, endp, c) in enumerate(pts):            # PARALLEL ("A does X, B does Y") — one clause per SUBJECT
                seg = s[pos:(pts[i + 1][0] if i + 1 < len(pts) else len(s))]
                seg = re.sub(r"[\s,;]*(?:\band\b|\bbut\b|\bthen\b|\bwhile\b|\bas\b)?[\s,;]*$", "", seg).strip(" ,;")
                if seg:
                    out.append((c, seg))
        return out
    units = _units(text)
    def _pose(c):
        mine = [seg for own, seg in units if own == c]                 # ONLY the clause(s) this character is SUBJECT of
        # Join multiple clauses as separate sentences (". "), never a bare space — a bare join runs two independent
        # clauses together with no punctuation ("...pollen from flower to flower Zenny's path is smooth...").
        clause = ". ".join(seg.rstrip(" .,;") for seg in mine) if mine else (text if len(block_chars) == 1 else f"{c} is in frame, mid-action")
        clause = re.sub(r"\bframe[- ]left\b", "on the left of the frame", clause, flags=re.I)
        clause = re.sub(r"\bframe[- ]right\b", "on the right of the frame", clause, flags=re.I)
        return clause.strip().rstrip(".") or f"{c} in frame"
    # THE APPEARANCE-LEAK FIX (2026-07-08, software-wide sign-off audit): _markers() used to append "Keep
    # {c}'s signature {m}." (e.g. "round wire-frame glasses", "rosy blush cheeks") to every character block —
    # a direct violation of CLAUDE.md rule 5 ("no physical/appearance text anywhere, ever... what stays
    # absolutely forbidden is DESCRIBING the character"), contradicting this very module's own docstring
    # ("character REFERENCE-ONLY, never described"). cb_qa.check_gate3_lint's item (4) already guards the v5
    # VIDEO prompt against exactly this leak (a character's markers text appearing outside the Acting DNA
    # block) — this keyframe/still builder was the one sibling module the sweep never reached. Identity
    # anchoring for accessories is already carried, losslessly, by the reference image itself via the
    # "Maintain this character's exact identity from the reference... every accessory exactly as shown"
    # sentence below — that sentence needed no appearance prose added on top; deleted, not just unused.
    blocks = [f"CHARACTER {i} ({c}): Use Image {char_img[c]}. {_pose(c)}. "
              f"Maintain this character's exact identity from the reference — facial features, proportions, AND "
              f"every accessory exactly as shown (glasses frame colour and shape, clothing, held objects, or any "
              f"other worn/carried item)."
              for i, c in enumerate(block_chars, 1)]
    world = (sc.get("location") or sc.get("name") or "the scene").strip().rstrip(".")
    world = (world[0].lower() + world[1:]) if world else "the scene"
    # Keep "Place them …" grammatical for any location phrase: lead with a preposition if the location data doesn't.
    # Default "in"; author "on a weathered wooden pier" / "at the beach" into the location string to override.
    _PREP = {"in", "on", "at", "by", "near", "inside", "within", "atop", "amid", "among", "beside",
             "aboard", "outside", "behind", "beneath", "under", "over", "through", "across", "along"}
    if world.split() and not ({w.lower().strip(",.") for w in world.split()[:3]} & _PREP):
        world = "in " + world
    # For a CHAINED beat this line was firing UNCONDITIONALLY with no image to anchor to ("Place them {world}") — a
    # second, competing environment instruction alongside the chain-image anchor below, sourced from the scene's
    # broad `location` text rather than the actual approved frame. When that text is loose enough to admit more than
    # one reading (e.g. "towering blossoms... corridor... canopy" can read as a genuine forest OR as an ordinary
    # meadow at bee-scale), the model can drift to a DIFFERENT world than the one already established — confirmed on
    # real Ep1 beats: 1.B2-1.B4 rendered a denser, forest-like place than 1.B1/the plate. The chain image + the
    # CONTINUITY & CAMERA SHIFT instruction below are the correct, single source of environment truth for a
    # continuation; this text-only restatement is dropped for chained beats rather than left to compete with it.
    env_line = (f"ENVIRONMENT & CONTEXT: Place the characters INTO Image {env_img} (the empty set) — {world}. Keep its "
                f"set, dressing, depth and lighting exactly; add only the characters."
                if env_img else f"ENVIRONMENT & CONTEXT: Place them {world}.") if not chained else ""
    # shotSize/shotType are legacy pre-beat-native fields — always None on current data, silently collapsing every
    # keyframe to the "Medium shot" default. cuts[0].framing is the Director's own camera call for this beat's first
    # shot (lens, angle, move) and is the correct, beat-varying source; the old fields stay as a defensive fallback.
    framing = (_cut0.get("framing") or shot.get("shotSize") or shot.get("shotType") or "Medium shot").strip()
    # THE KEYFRAME GETS ITS NAMED CINEMATOGRAPHY VOICE (2026-07-14, restoring the named-auteur-per-chair doctrine
    # — CRYSTAL_BEARS_STUDIO_BIBLE.md's Gate 2 chair): CINEMATOGRAPHY (Lin/Kalache, defined below) and Eggleston's
    # production-design eye were already written into this file — CINEMATOGRAPHY carried its own comment saying
    # it was meant to be "carried into the render stages" — but neither ever actually reached this function's own
    # output; build_keyframe_prompt built its own generic, unattributed "STYLE:"/"COMPOSITION:" text instead. Wired
    # in here, concise (this is a per-beat keyframe, not the once-per-scene establishing plate that already used
    # the fuller PLATE_CINEMATOGRAPHY/PLATE_PRODUCTION_DESIGN text) — same two disciplines, same names, kept
    # consistent with Gate 1's own crew (cb_director.py), just scoped to compose and light ONE frame, not a world.
    # ROOM TO BREATHE (2026-07-14, Julian's own production note on Gate 2b — "with the opening keyframe we have
    # to be conscious of it being slightly wider to give the animation room to breathe"): a keyframe framed to
    # the LITERAL edge of its stated shot size leaves the video model nowhere to move the action into before it
    # exits frame — the still is a composed PICTURE, but the clip built from it needs headroom the picture alone
    # doesn't need. This is Eggleston's own standing composition law, applied on every beat, not a per-beat
    # authored override of the Director's `framing` call — the stated shot size is kept exactly as written.
    comp = (f"COMPOSITION (Ralph Eggleston's eye — the world as the first character): {framing}. Compose a natural "
            "film shot, the subject(s) clear and appropriately scaled within the frame, with real depth — a "
            "readable foreground/midground/background, never a flat cutout. Frame a touch WIDER than the shot "
            "size alone implies — keep the stated framing's intent, but leave real headroom and side space "
            "around the subject(s) so the animation has room to move before anything reaches the frame's edge; "
            "never crop the action to its literal boundary.")
    # "light" is the Director's own PER-BEAT lighting call (richer and beat-varying — e.g. differentiated per character);
    # "lighting" is a legacy/alternate key that is never actually populated on beat-native data. sc's scene-level
    # lighting stays the fallback for a beat that hasn't authored its own. Same bug class as the shotSize/cuts[0] find.
    light = (shot.get("light") or shot.get("lighting") or sc.get("lighting") or "").strip().rstrip(".")
    atmosphere = (shot.get("atmosphere") or "").strip().rstrip(".")
    style = ("STYLE (Patrick Lin, camera; Jean-Claude Kalache, lighting — the Pixar DPs): Premium 3D CGI, "
             "Disney/Pixar animation style, 8K resolution, Octane render, subsurface scattering (fur/skin), "
             "cinematic depth of field, hyper-realistic textures. A motivated, invisible, purposeful camera and "
             "a deliberate, soft key light with warm bounce and a gentle rim carving the characters off the "
             "background — never showy, never flat. "
             "Captured as a SINGLE FROZEN INSTANT at high shutter speed — the action is caught and held perfectly still, "
             "every part of it tack-sharp and fully in focus, as if the frame were paused. This is the frame the animation "
             "is built FROM."
             # beautyMoment: the Director's choice of the scene's ONE visual high point — push the render further here.
             + (" THIS IS THE SCENE'S BEAUTY MOMENT: push the lighting, colour and composition further than the "
                "surrounding beats — this is the single most visually beautiful frame in the scene." if shot.get("beautyMoment") else ""))
    one_each = " and ".join(f"one {c}" for c in chars) or "one of each character"
    ranked = sorted([c for c in chars if c in CHARACTERS and CHARACTERS[c].get("sizeRank") is not None],
                    key=lambda c: -(CHARACTERS[c].get("sizeRank") or 0))
    # A tied sizeRank (e.g. Keen/Squeaky both rank 4) must never assert an ordinal claim neither character's own
    # canon size prose supports — that's a pure artifact of this beat's own characters[] list order, not a real
    # size fact, and contradicts size_line()'s own "do NOT invent a size for anyone" text in the same prompt.
    if len(ranked) >= 2 and CHARACTERS[ranked[0]].get("sizeRank") != CHARACTERS[ranked[-1]].get("sizeRank"):
        size_clause = f" Ensure {ranked[0]} is visibly larger than {ranked[-1]}."
    elif len(ranked) >= 2:
        size_clause = f" {ranked[0]} and {ranked[-1]} are the SAME size — do not make one visibly larger."
    else:
        size_clause = ""
    # `keeps` (a positive "Fuzzby keeps round wire-frame glasses" restatement of characters.json's `markers`
    # field) is DELETED, same rule-5 fix as `_markers()` above — a positive appearance description, not a
    # prohibition. `avoids` is KEPT: "wears NO pendant/necklace/medallion/crystal" names something the
    # character must NOT be given, matching the standing "Negative:"-style prohibition pattern already used
    # everywhere else in this pipeline (v5's own standing negatives, the crystal-world rule below) — a
    # constraint on invention, not a description of the character's actual appearance.
    avoids = [f"{c} wears NO {CHARACTERS[c]['avoid'].rstrip('.')}"  for c in block_chars if CHARACTERS.get(c, {}).get("avoid")]
    sig = ""
    neg = (" " + "; ".join(avoids) + ".") if avoids else ""
    # Bee comedy scenes: Crystal Cove world-crystals ARE allowed, but only as SUBTLE BACKGROUND world-detail — never
    # active magic, never on/near the bees, never a dominant foreground/centre object pulling focus from the gag.
    _bees = BEES   # FIXED 2026-07-12 (full-codebase audit, duplication finding): now the module-level canonical set
    # FIXED 2026-07-12 (full-codebase audit continued): this clause used to hardcode the literal string
    # "Fuzzby or Zenny" regardless of which bee(s) are actually in block_chars — every OTHER per-character
    # clause in this function (avoids, wings, size_clause) derives its names dynamically from block_chars/
    # chars; this was the one exception. Currently masked because every authored bee beat so far includes
    # both bees together, but a future solo-Fuzzby or solo-Zenny beat (single-character beats are already
    # normal elsewhere in this package, e.g. 8.B1's Keen+Squeaky-only opening) would name a character who
    # isn't even in the shot. cb_segprompt._standing_negatives() states the equivalent v5 constraint
    # generically ("no crystals on the bees") for this exact reason — matched here instead of the hardcode.
    env_neg = (" Crystal rule for this bee scene: Crystal Cove is crystal-RICH — reproduce the plate's ABUNDANT COLOURFUL "
               "CUT crystals (jewel-toned — amethyst, rose, aqua, citrine, sapphire — faceted, catching the ambient "
               "light) clustered through the rocks, roots, bark, banks and flower bases at every depth. NO crystal on or "
               f"near {' or '.join(block_chars)}; NO crystal self-glow, aura, beams, particles, hum or magical activity (colour and "
               "sparkle come from reflected scene light only); crystals frame and fill the world but keep the immediate "
               "space around the bees, flowers, pollen and the gag readable — never crowd the performers or block the gag."
               if (block_chars and set(block_chars) <= _bees) else "")
    # CRISP WINGS — non-negotiable: even when a bee is hovering or in the air, its wings are rendered SHARP, SOLID and
    # FULLY DEFINED exactly as in the turnaround (four separate translucent wings, clean edges), NEVER a motion-blur,
    # translucent smear, haze, double-image or fan of blur. Blurred wings in the keyframe dampen the wing motion Seedance
    # then adds — so freeze them crisp.
    # LAUNCH-READY (Julian, 2026-07-03, from reviewing the first real fires): "frozen mid-beat" alone kept rendering
    # as both wings spread flat and symmetrical, body hanging vertical with legs dangling — a bee floating in place,
    # not a bee in flight. Seedance then has to invent a standstill-to-motion transition instead of continuing
    # existing motion. Fixed by making the freeze frame explicitly ASYMMETRIC (one wing up, one down, mid-downstroke)
    # and the body explicitly already accelerating (forward lean, legs tucked/trailing) — same crisp, non-blurred
    # wings, but a pose that reads as already airborne and launching, so the clip picks it up and just takes off.
    # THE TURNAROUND-CONFLICT FIX (Julian, 2026-07-07, diagnosing 1.B1's still-wrong wing on the actual rendered
    # keyframe): the LAUNCH-READY fix above never actually closed the gap — CB_Fuzzby.jpeg (the turnaround sheet
    # this text points at) shows all four wings in a static, evenly-spread, symmetrical REST pose in every one of
    # its four views; there is no asymmetric/mid-flight reference anywhere in the character's canon assets. The old
    # wording asked for wings "exactly as in the turnaround" in the SAME sentence as "ASYMMETRIC," and the separate
    # CLEAN BASE IDENTITY clause immediately after this one repeats "render each character EXACTLY as its turnaround
    # reference shows it... add NOTHING beyond the reference" with no bee/wing exception — two competing "match the
    # turnaround" signals (one a stronger reference IMAGE, one a text line placed right after this one) pulling
    # against the one asymmetry instruction. Same bug class as the rule-26 anti-hold fix and the rule-27 temporal-
    # contradiction bug: two opposing instructions in one prompt, and the render satisfied the wrong one. Fixed by
    # scoping "exactly as in the turnaround" to MATERIAL properties only (colour, translucency, vein pattern, edge
    # quality) and explicitly naming the turnaround's own resting pose as the thing NOT to copy, with an explicit
    # precedence statement over the later clean-base line.
    # SHARPENED 2026-07-12 (Julian, live footage review — the turnaround-conflict fix above held the prompt-text
    # override in place but the failure persisted identically across TWO different image models, Nano Banana 2
    # and Seedream 5 Pro, on the real Ep1 1.B1 keyframe: both still rendered the exact same silhouette this
    # clause already forbids). Diagnosis: the wording was already about as forceful as prose gets, so simply
    # re-asserting "asymmetric, not symmetrical" harder was unlikely to move a second model that failed the
    # identical instruction. Added: (1) a literal, concrete description of the RECURRING failure silhouette itself
    # (both wings out to the sides, mirrored, at matching height) — naming the specific pattern being observed,
    # not just the abstract "symmetrical" category, matching this project's own standing rule that a concrete,
    # checkable description outperforms an abstract one (CLAUDE.md rule 17, applied here to pose/motion, not
    # appearance — no character APPEARANCE is described, only a POSE to avoid, which this file's own FLIGHT
    # ENERGY clause already does routinely); (2) a positive physical-mechanics alternative (foreshortening/
    # overlap) so the model has a concrete correct target, not only a prohibition.
    wings = (" WINGS: capture the wings CAUGHT mid-downstroke, ASYMMETRIC — one wing raised, the other lowered, as if "
             "a fraction of a second into a beat cycle. THE SINGLE MOST COMMON FAILURE TO AVOID: do not render both "
             "wings (or all four) spread out flat to either side at matching height, mirrored, like a static "
             "reference-sheet display — that exact silhouette, however crisp and sharp, reads as parked and floating, "
             "never flying, and must not appear here. From this camera angle a wing mid-beat foreshortens and can "
             "partially overlap the body or another wing — it does not fan out flat and clear on both sides at once. "
             "Each of the four translucent wings keeps the turnaround's colour, translucency, vein pattern and clean "
             "edge quality — sharp and solid, as if caught by a fast camera shutter, crisp and readable, never a soft "
             "blur or fan — but the WING POSE itself must NOT match the turnaround: the turnaround shows its wings "
             "evenly spread and symmetrical because that is a reference-sheet convention for showing all four wings "
             "clearly, not a flight pose, and reproducing that resting spread here is the exact failure this "
             "instruction exists to prevent. This wing-pose instruction overrides any later 'match the turnaround "
             "exactly' line for wing pose specifically — every other feature (colour, glasses, body shape, markings) "
             "still matches the turnaround exactly. FLIGHT ENERGY: the body leans forward and down into the direction "
             "of travel, already accelerating, legs tucked or trailing back — never hanging straight down at rest "
             "like a puppet. This is a bee already IN FLIGHT and about to launch into the action, not hovering still "
             "in place."
             if (block_chars and set(block_chars) <= _bees) else "")
    # CLEAN BASE IDENTITY (baked principle, 2026-07-01): the keyframe is the CLEAN BASE the animation builds ON TOP OF.
    # Seedance does the heavy lifting — it applies AND removes every temporary state within the take. So the keyframe
    # renders each character as its plain turnaround self, and any temporary body-state named in the staging is IGNORED
    # here (put on later, in animation). This makes the rule software-wide: no hand-editing a beat to strip a moustache.
    clean_base = (" CLEAN BASE IDENTITY: render each character EXACTLY as its turnaround reference shows it — its canonical "
                  "look and any accessory the reference itself includes (glasses, a worn pendant, worn wristbands) — and "
                  "add NOTHING beyond the reference. Do NOT apply any TEMPORARY TRANSFORMATION the story puts a character "
                  "through: no pollen moustache, no being caked/dusted/covered in pollen, no dirt, no wet or muddy fur, no "
                  "smear, no loose prop the reference doesn't show. Those go ON later, in the animation — this keyframe is "
                  "the clean BASE the animation builds on top of.")
    # CONTINUITY GUARDS — worn_line (carried items, e.g. Keen's satchel), recurring_line (recurring-asset look-lock +
    # the NEGATIVE guard against a lost/not-yet-earned asset like the crystal-set cuffs appearing too early), and
    # props_block (per-shot prop state) were already used by build_vision_prompt/build_edit_prompt/build_i2v_prompt
    # but never by THIS function — every Gate-2 keyframe (the one every chained beat and Gate-3 take builds on top
    # of) was missing them entirely. size_line adds the solo-character absolute-size anchor scale_line/the inline
    # size_clause above doesn't cover (the "Aida looks small" bug, for exactly-one-character shots).
    # FIXED 2026-07-12 (full-codebase audit continued): worn_line/size_line both re-derive their own
    # `chars = shot.get("characters", [])` internally — the beat's FULL authored cast, bypassing this
    # function's own `chars = opening_cast(shot)` filtering (line 535) that exists specifically to exclude
    # a character not yet in frame. Confirmed live on 8.B1 (openingCast=[Keen, Squeaky], "the welcoming
    # group still off-frame") — this shipped a SIZE paragraph naming all 10 cast members with zero
    # reference images attached, a real instruction-inconsistency risk (the model can invent an
    # off-frame character into the shot). Pass the already-filtered `chars` in via a shallow dict
    # override (same `dict(shot, k=v)` pattern build_vision_prompt already uses two functions down) so
    # both helpers see only who's actually in this opening frame — no signature change, no other call
    # site (build_charsheet_prompt/build_vision_prompt, both intentionally scoped to their own full casts) affected.
    _shot_inframe = dict(shot, characters=chars)
    _worn = worn_line(episode, _shot_inframe)
    _recur = recurring_line(episode, shot)
    _props = props_block(shot)
    _size = size_line(_shot_inframe)
    # Keen's cuffs (none/vacant/crystal) — the story-state SENTENCE, alongside the reference image added above.
    _band = _band_line(shot)
    band_line = f" {_band}." if _band else ""
    # A bear's crystal-brightness state for THIS beat (crystalGlow) — bees never carry crystal, so this only ever
    # fires for bears in frame (mirrors cb_qa.check_done_frame's own `if bears and glow` gating for CRYSTAL_STATE_MISMATCH,
    # so the keyframe asserts exactly the state QA will later check the render against).
    _glow = (shot.get("crystalGlow") or "").strip().rstrip(".")
    _bears_present = [c for c in block_chars if c not in _bees]
    glow_line = f" CRYSTAL STATE: {_glow}." if (_glow and _bears_present) else ""
    constraints = ("CONSTRAINTS: Avoid multiple faces, distorted proportions, or duplicating the characters. "
                   f"Exactly {one_each}.{size_clause}{_size}{sig}{neg}{wings}{clean_base}{env_neg}{band_line}{glow_line}{_worn}{_recur}{_props}")
    lead = "Reason through this composition:"
    # ── EXPRESSION & MOOD — weave THIS beat's emotional read into the OPENING frame so each keyframe is DISTINCT;
    #    engine-wide via the shared _expression_mood (same helper the vision builder uses). Action stays in the clip.
    mood = _expression_mood(shot)
    # CONTINUATION beats open with a CONTINUITY & CAMERA SHIFT — an ATMOSPHERE-ONLY lock (take only the lighting/colours/
    # textures from the previous frame) that EXPLICITLY allows the camera to cut and the characters to move. This is the fix
    # for NB over-conditioning (the old "reproduce the environment with ZERO drift / use as the blueprint" lock made the model
    # copy the framing too → 4 near-identical frames). COMPOSITION is folded INTO the shift (the cut is acknowledged first),
    # so the standalone COMPOSITION + LIGHTING blocks are dropped for chained beats.
    continuity_lock = ([f"CONTINUITY & CAMERA SHIFT: Reason through this camera cut. Use Image {chain_img} ONLY for the "
                        f"lighting and background textures. The camera has now changed to a {framing}. Reason through how "
                        f"the characters and the environment from Image {chain_img} look from this new angle. "
                        # explicit negative: the observed failure mode was the model inventing a DIFFERENT place
                        # (denser, forest-like) rather than reframing the SAME one — say so directly, not just imply it.
                        "This is the SAME location, the SAME scale and the SAME world as Image "
                        f"{chain_img} — do not invent a different place, a different kind of plant, or a different scale."
                        # the chain image shows the PREVIOUS frame's light — it can't show a narrative shift THIS beat
                        # introduces (e.g. cooling before a thunder beat), so state this beat's own light/atmosphere too.
                        + (f" This beat's own light: {light}." if light else "")
                        + (f" Atmosphere: {atmosphere}." if atmosphere else "")] if chained else [])
    # LIGHTING carries Jean-Claude Kalache's own beat-specific call (2026-07-14, restoring the named-auteur-per-
    # chair doctrine, CRYSTAL_BEARS_STUDIO_BIBLE.md) — distinct from STYLE's general lighting philosophy above,
    # this is THIS beat's own key-light/mood instruction, in his voice.
    light_block = [] if chained else (([f"LIGHTING (Kalache's key light): {light}."] if light else []) + ([f"ATMOSPHERE: {atmosphere}."] if atmosphere else []))
    comp_block = [] if chained else [comp]   # chained: COMPOSITION is folded into the CONTINUITY & CAMERA SHIFT above
    body = [lead] + continuity_lock + blocks + ([mood] if mood else []) + ([env_line] if env_line else []) + comp_block + light_block + [style, constraints]
    prompt = re.sub(r"[ ]{2,}", " ", header + "\n\nPROMPT:\n" + "\n\n".join(body) + _fix_line(note))
    return prompt, refs

def build_remint_prompt():
    """THE RE-MINT prompt (Julian's ruling, 2026-07-03) — LOCKED and deliberately minimal: a restoration pass,
    never a re-generation. @图1 is the harvested settle frame to reproduce EXACTLY; the turnaround references
    that follow are attached SOLELY to hold each character's identity steady while cleaning — never to change
    pose, position or anything else about the frame being restored. This supersedes the earlier "NB2 chain
    refresh, rejected as routine" backlog note (LAB_BACKLOG.md) — re-mint is now standard for every relay link,
    per the director, not a QA-triggered exception.

    Hardened 2026-07-04 (Julian, after a real drift: Zenny's glasses hallucinated from black to pink during a
    re-mint) — the identity-lock list previously named only "face, markings, proportions", which left every
    ACCESSORY (glasses, clothing, held objects) undeclared and free for the model to reinterpret. Named
    explicitly now, with exact colour called out, since colour drift on an accessory is exactly what slipped
    through the old wording.

    Restructured same day (Julian): lead with the two-part instruction in his own words — "copy this exactly"
    then "for reference, here are the characters, to ensure 100% accuracy" — a plainer, more direct framing
    than the previous paragraph-first version, on the theory that a short, sequential instruction reads more
    reliably to the image model than a dense block of restrictions before the reference images' purpose is
    even stated."""
    return (
        "Copy @图1 exactly — same characters, same pose, same position, same environment, same lighting, "
        "everything unchanged. The ONLY permitted change is technical cleanup: remove compression artifacts, "
        "motion blur or softness so the frame is tack-sharp and clean. Do NOT redesign, restage, reframe, "
        "recolour, add, remove or reinterpret anything.\n\n"
        "For reference, here are the characters in this frame, to ensure 100% accuracy on their identity: "
        "face, markings, proportions, AND every accessory exactly as the reference shows it (glasses frame "
        "colour and shape, clothing, held objects, or any other worn/carried item). Use these references for "
        "identity accuracy ONLY — never to change a character's pose or position, or the exact colour of "
        "anything they wear or hold, from @图1. This is a restoration pass, not a new composition."
    )

def scene_characters(scene_shots):
    """Union of the characters appearing across a scene's shots, in order of first appearance."""
    seen = []
    for s in scene_shots:
        for c in s.get("characters", []):
            if c not in seen: seen.append(c)
    return seen

def build_charsheet_prompt(scene_shots, sc, episode="Ep1", note=""):
    """A2 — the per-scene CHARACTER-SHEET anchor. A clean, on-model GROUP line-up of the scene's
    characters in the scene's OPENING state (wardrobe + wristband state), neutral staging — the locked
    IDENTITY anchor that coverage derives from. Returns (prompt, refs). Identity-only: no environment,
    no scene props beyond worn items."""
    chars = scene_characters(scene_shots)
    opening_wb = scene_shots[0].get("keenWristbands", "none") if scene_shots else "none"
    sheet = {"characters": chars, "keenWristbands": opening_wb}  # for identity/size/band helpers
    refs = []
    for c in chars:
        cc = CHARACTERS.get(c)
        if not cc:
            raise KeyError(f"character '{c}' not in config/characters.json — add its anchor before building")
        # ANATOMY LOCK: condition on the FULL TURNAROUND (shows every limb/angle) so the sheet COPIES the correct
        # anatomy instead of inventing arms/legs from a single front crop. Fall back to the anchor if no turnaround.
        cref = _turn4_ref(cc) or cc["anchor"]
        if cref not in refs: refs.append(cref)
    if "Keen" in chars:
        for r in CHARACTERS["Keen"].get("wristband_states", {}).get(opening_wb, []):
            if r not in refs: refs.append(r)
    chart = size_chart_ref() if len(chars) >= 2 else None
    chart_clause = ""
    if chart and chart not in refs:
        refs.append(chart)
        chart_clause = (" Use the SIZE-CHART reference image to set the EXACT relative heights of the characters on "
                        "the sheet — match their proportions to the chart precisely.")
    names = ", ".join(chars)
    prompt = (
        f"A clean CHARACTER MODEL SHEET — a full-body group line-up of {names}, standing side by side facing "
        "camera in a relaxed neutral A-pose with a calm neutral expression, evenly spaced and clearly separated. "
        "Use the CHARACTER reference image(s) EXACTLY for each character — appearance, design, fur, face and "
        "proportions come entirely from those references; never change them. ANATOMY EXACTLY AS THE TURNAROUND: "
        "copy each character's COMPLETE body plan — the EXACT number of arms, legs, wings, paws, eyes and antennae "
        "shown in their reference; NEVER add, duplicate, merge, melt or drop a limb, digit or feature."
        + identity_line(sheet) + chart_clause +
        f" {_band_line(sheet)};{size_line(sheet)} "
        "Plain soft neutral studio background (pale even gradient), soft even three-point studio lighting, NO "
        "scenery, NO environment, NO ground detail, NO props except items a character wears, no text or logos. "
        f"Style: {STYLE} "
        "This is the scene's IDENTITY reference sheet — every character fully on-model, signature features clearly "
        "visible, relative sizes accurate to the references; 16:9."
        + _fix_line(note))
    return prompt, refs

def set_locks_for_scene(episode, scene_num):
    """Appearance + orientation locks for the recurring SET assets present in a scene (boat, pier, etc.) —
    WITHOUT persistent cargo. For the empty scene plate (the world, no characters, no per-shot props)."""
    sn = str(scene_num); out = []
    for r in CONTINUITY.get(episode, {}).get("recurring", []):
        if not r.get("appearance"): continue
        scenes = [str(x) for x in r.get("scenes", [])]; shots = r.get("shots")
        match = any(str(x).split(".")[0] == sn for x in shots) if shots else (sn in scenes)
        if match:
            line = f"{r['name']} is {r['appearance']}"
            if r.get("orientation"): line += f" — {r['orientation']}"
            out.append(line)
    return out

# PLATE-specific style (environment art — NOT the character STYLE; no fur/eyes language on an empty stage)
PLATE_STYLE = ("Premium feature-film 3D-CGI environment art in the established Crystal Bears look — physically-based "
               "rendering, soft global illumination, rich material detail and surface texture (grain, moss, wet stone, "
               "dappled bark, light scattering through translucent leaves), volumetric atmosphere and gentle god-rays, "
               "cinematic shallow depth of field with soft background bokeh; warm, magical, painterly-but-real — never "
               "flat, never harsh, never a clean empty studio render.")
# PLATE cinematography — the Lin/Kalache establishing-frame eye, applied to the EMPTY plate (no character/eyeline language)
PLATE_CINEMATOGRAPHY = ("CINEMATOGRAPHY (Patrick Lin — camera; Jean-Claude Kalache — lighting; the Pixar DPs): compose "
               "this as a deliberate, MOTIVATED establishing FRAME, not a snapshot — a clear focal anchor and staging "
               "that reads the place INSTANTLY. Build REAL LAYERED DEPTH: a soft, slightly out-of-focus FOREGROUND "
               "element framing the lower/edge of frame (foliage, a rock lip, a branch, drifting motes), a sharp "
               "MIDGROUND that holds the scene's defining feature and the space the action will play in, and an "
               "atmospheric BACKGROUND that recedes into haze and soft bokeh — foreground / midground / background "
               "distinct and readable. LIGHT IS STORY: one dominant, motivated key with a clear direction and source, "
               "warm bounce in the shadows and a gentle rim carving the silhouettes of the set pieces off the "
               "background; commit to ONE dominant colour temperature for the whole frame. Give a scale cue (a "
               "known-size element or layered overlap) so the world reads at true scale, never toy-like. Every plate a "
               "composed, lit Pixar establishing frame.")
# PLATE production design — the world as the first character (Ralph Eggleston colour script + Harley Jessup warm worlds)
PLATE_PRODUCTION_DESIGN = ("PRODUCTION DESIGN (Ralph Eggleston — the colour script; Harley Jessup — warm, hand-crafted "
               "worlds; the Pixar production designers): build the WORLD as the FIRST CHARACTER. Lead with the COLOUR "
               "SCRIPT — choose ONE governing palette and light temperature that already makes this empty stage FEEL the "
               "beat's emotion before any character arrives. Render it premium, warm and TACTILE — a lived-in, "
               "hand-crafted, generous, magical place a child wants to climb into; never slick, never flat, never a clean "
               "studio render. Compose and light for where the character WILL stand — leave the storytelling space, the "
               "eyeline and the contact light the keyframe will need. The landscape is the first actor.")

# ── THE LOCKED CRYSTAL COVE WORLD RULE ───────────────────────────────────────────────────────────────────────────
# Julian's standing law (2026-06-30): Crystal Cove is a world MADE of crystal — ABUNDANT, colourful CUT crystals on
# EVERY scene plate. This is the NAMED, LOCKED block: build_plate_prompt injects it into every plate, and a fail-loud
# guard there refuses to emit any plate prompt without it. Change the crystal look HERE (one place) → every scene updates.
CRYSTAL_COVE_WORLD_RULE = (
    "THE CRYSTAL BEARS WORLD (on-brand, ALWAYS): this is CRYSTAL COVE — a world MADE of crystal, so crystals are an "
    "ABUNDANT, SIGNATURE feature of EVERY scene, not a token detail. Fill the environment GENEROUSLY with COLOURFUL "
    "CUT crystals in natural jewel tones — amethyst purple, rose pink, aqua-teal, citrine gold, sapphire blue — "
    "clustered and studded through rock, bark, roots, banks, mossy ground and flower bases at EVERY depth: "
    "foreground crystal clusters framing the edges, midground formations among the set pieces, and crystal outcrops "
    "receding into the background. Give them clean facets that CATCH and refract the scene's own light like real "
    "gemstones, so the place reads UNMISTAKABLY as a jewel-bright crystal world. They are NOT light sources: their "
    "colour and sparkle come ONLY from the ambient scene light striking the cut facets — no inner glow, aura, halo, "
    "bloom, beams, hum, magical particles or emitted light of any kind. Abundant but COMPOSED, never a chaotic "
    "field: keep a clear, readable performance space and eyeline where the action will play, never bury the staging "
    "or block the main action path, and never place a crystal on or near a character. "
    "(A scene whose named defining FEATURE is itself a crystal leans in even further.)")

def build_plate_prompt(sc, episode, scene_num, layout_ref=None, location_ref=None, changes=None, note=""):
    """A1 — the EMPTY SCENE PLATE: a clean establishing environment for the scene with NO characters in it.
    The world authority — coverage places characters (from the turnarounds + sheet) into this locked plate.
    `changes` (set when this is a RETURNING location) = the accumulated world-state changes the plate must
    apply on top of its last-seen state. Returns (prompt, refs)."""
    refs = []
    if location_ref and os.path.exists(location_ref): refs.append(location_ref)
    if layout_ref and os.path.exists(layout_ref) and layout_ref not in refs: refs.append(layout_ref)
    locks = set_locks_for_scene(episode, scene_num)
    set_clause = (" Set elements (locked, identical every shot): " + "; ".join(locks) + ".") if locks else ""
    returning = bool(changes and layout_ref)
    change_clause = ""
    if returning:
        layout_clause = ("This is the SAME location returning later in the episode — the reference image is its "
                         "LAST-SEEN state, and the world REMEMBERS. Keep the geography, layout, structures, screen "
                         "direction and every fixed element IDENTICAL to it; remove any characters (empty set). Then "
                         "apply ONLY these accumulated changes that have happened since we were last here: "
                         + "; ".join(changes) + ". ")
    elif layout_ref:
        # SCOPED 2026-07-12 (Julian, live review — "the stage... too tight for the shot"): this used to say
        # "Match the LAYOUT... EXACTLY... every fixed element... in the same positions" with no carve-out — so a
        # re-fire meant to LOOSEN a scene's own composition (per its own updated `look`/`lens`/`cameraHeight`
        # fields above) was simultaneously told to reproduce the OLD reference image's density/framing exactly,
        # via a stronger image anchor fighting the very text this function just built. Same class of conflict as
        # the wing-turnaround fix in build_keyframe_prompt (a reference image outweighing a text override) —
        # same fix shape: split what "match exactly" covers (the functional, gag-load-bearing landmarks a beat's
        # own action depends on finding in a fixed place) from what it explicitly does NOT cover (how tightly the
        # space is framed/packed, which follows THIS beat's own scene-direction text above, not the old image).
        layout_clause = ("Match the reference image for its FUNCTIONAL landmarks only — the fixed structures, "
                         "terrain, water line, crystals, horizon and any named gag-load-bearing elements (a "
                         "specific leaf, branch or flower a beat's own action depends on finding in the same "
                         "place) — keep THOSE in the same relative positions. Do NOT match the reference for how "
                         "tightly-packed, crowded or open the framing is — that comes from the scene direction "
                         "above instead, even where it asks for something more open or spacious than the "
                         "reference shows. Remove every character — an empty set. ")
        change_clause = (" The location currently shows (world state): " + "; ".join(changes) + ".") if changes else ""
    else:
        layout_clause = ""
        change_clause = (" The location currently shows (world state): " + "; ".join(changes) + ".") if changes else ""
    # the world also FORGETS: assets lost earlier must NOT reappear in a later plate (e.g. the boat after the storm)
    lost_neg = []
    for l in CONTINUITY.get(episode, {}).get("lost", []):
        at = str(l.get("atShot", "")).split(".")[0]
        if at.isdigit() and str(scene_num).isdigit() and int(at) < int(scene_num):
            lost_neg.append(l["name"])
    lost_clause = (" GONE — lost earlier in the story, must NOT appear anywhere in frame: " + "; ".join(lost_neg) + ".") if lost_neg else ""
    # LEAD with the place + its defining feature (not a flat label) — the Director's sense-of-place fields
    lead = (sc.get('sceneShotName') or sc.get('location') or "the scene").strip().rstrip(". ")
    feature = (sc.get('definingFeature') or "").strip().rstrip(". ")
    look_clause = (f"Scene direction (the Director's intent for this empty stage): {sc['look']} " if sc.get('look') else "")
    lens = (sc.get('lens') or "a wide-to-medium cinematic lens").strip()
    cam_h = (sc.get('cameraHeight') or "eye-level").strip()
    colortemp = (sc.get('colorTemperature') or "").strip().rstrip(". ")
    comp_clause = (f" Composition & camera: frame the empty stage with {lens}, camera at {cam_h} — deliberate "
                   "establishing staging with a clear focal anchor and REAL layered depth: a soft out-of-focus "
                   "FOREGROUND element framing the edge, a sharp MIDGROUND holding the defining feature and the space "
                   "the action will play in, and an atmospheric BACKGROUND receding into haze and soft bokeh.")
    light_clause = ((f" Colour & light: unify the whole frame under ONE dominant colour temperature — {colortemp}; "
                     if colortemp else " Colour & light: commit to ONE dominant, motivated colour temperature for the whole frame; ")
                    + f"{sc.get('lighting','')} — a single motivated key with clear direction, warm bounce in the "
                      "shadows and a gentle rim carving the set pieces off the background; soft, never harsh, never flat.")
    prompt = (
        f"A cinematic ESTABLISHING ENVIRONMENT PLATE — {lead}. "
        + (f"The frame is built around its defining feature: {feature}. " if feature else "")
        + look_clause
        + layout_clause + change_clause + lost_clause + set_clause
        + f" Time & weather: {sc.get('time','')}, {sc.get('weather','')}."
        + comp_clause + light_clause
        + f" STYLE: {PLATE_STYLE} "
        + PLATE_PRODUCTION_DESIGN + " "
        + PLATE_CINEMATOGRAPHY + " "
        # THE LOCKED CRYSTAL COVE WORLD RULE — on EVERY scene plate by construction; a fail-loud guard below refuses any
        # plate prompt without it. Edit the crystal look in ONE place (the CRYSTAL_COVE_WORLD_RULE constant) to change every scene.
        + CRYSTAL_COVE_WORLD_RULE + " "
        + "This is an EMPTY stage: absolutely no characters, people, animals or creatures anywhere; show only the place "
          "and the set pieces the scene direction names — add no structures, vehicles or objects it does not name. "
          "Ready for characters to be placed in later. No text, captions, logos or watermarks; 16:9."
        + _fix_line(note))
    prompt = re.sub(r"[ ]{2,}", " ", prompt)
    # LOCK: every scene plate MUST carry the Crystal Cove world rule — fail loud if a future edit ever drops it.
    if "CRYSTAL COVE" not in prompt or "ABUNDANT" not in prompt:
        raise RuntimeError("LOCK VIOLATION: this scene plate prompt is missing the Crystal Cove world crystal rule "
                           "(CRYSTAL_COVE_WORLD_RULE) — it MUST appear in EVERY scene plate.")
    return prompt, refs

def build_vision_prompt(shot, vision, of_sc, note="", episode="Ep1"):
    """A vision/flashback that foreshadows a real scene — DERIVE from that scene's master so it
    matches exactly, then apply the dreamlike treatment. Returns (prompt, refs)."""
    shot2 = dict(shot); shot2["keenWristbands"] = vision.get("wristbands", shot.get("keenWristbands", "none"))
    refs = ([of_sc["master"]] if of_sc.get("master") else []) + char_refs(shot2)
    vmood = _expression_mood(shot)   # the SAME engine-wide emotional read as build_keyframe_prompt — visions are distinct too
    prompt = (
        f"Render this as a VISION. {VISION_FRAME} "
        f"Treatment: {vision.get('style', 'a dreamlike rose-pink vision treatment')}. "
        + (f"How it forms: {vision['materialize']}. " if vision.get("materialize") else "")
        + "INSIDE the bubble — filling the whole frame — is the foreseen moment. Use the MASTER frame (first reference "
        f"image) for ITS layout, composition and key elements, matched EXACTLY: show {vision.get('match', 'its layout, set and key elements')}; do NOT take the "
        "characters from the master; show NOTHING outside this foreseen moment (no surrounding sanctuary or real scene). "
        "Use the CHARACTER reference image(s) EXACTLY for the character(s) — design, fur, faces and proportions "
        "come entirely from those references; never change them." + identity_line(shot) + " "
        f"Subject/action inside the vision: {shot['action']} "
        + ((vmood + " ") if vmood else "")
        + f"Time & weather of the foreseen moment: {of_sc.get('time','')}, {of_sc.get('weather','')}. "
        f"Lighting & style: {STYLE} {of_sc.get('lighting','')}, all seen through the dreamlike vision treatment; the rose-pink "
        "orb haze and soft darkness frame only the outermost edges. "
        f"Constraints: characters identical to their references; {_band_line(shot2)};{size_line(shot)}{worn_line(episode, shot)}{recurring_line(episode, shot)} the sailboat "
        "and pier IDENTICAL to the master (same red sail, same shape, same layout); the vision FILLS the frame with NO "
        "surrounding real scene visible on any side; no objects clipping through each other; no text or logos; 16:9."
        + _fix_line(note))
    return prompt, refs

def build_edit_prompt(shot, sc, episode="Ep1"):
    """RETIRED (found dead — zero callers anywhere in engine/ — in the 2026-07-08 full-codebase audit; missed
    by the earlier 2026-07-08 contradiction sweep that guarded its three siblings build_i2v_prompt/
    build_ref2vid_prompt/build_beat_prompt the same way). The live builder is cb_segprompt.shipped_prompt
    (v5). Guarded rather than deleted outright — kept for the record; raises loud.
    Original design note: EDIT mode — modify the FROZEN master in place (the master is the FIRST ref = the
    canvas). Preserve every pixel of the set/boat/props/other characters; change ONLY the active character's
    pose. This is the frame-locked-compositing approach: the environment is a plate, the character is changed
    inside it."""
    raise RuntimeError("cb_prompts.build_edit_prompt is RETIRED and unused. Use cb_segprompt.shipped_prompt "
                        "(the v5 engine) instead.")
    refs = [sc["master"]] + char_refs(shot)
    item_refs, item_locks = items_for(episode, shot)
    for r in item_refs:
        if r not in refs: refs.append(r)
    chars = ", ".join(shot.get("characters", [])) or "the character"
    prompt = (
        "EDIT the FIRST image (the locked MASTER frame) in place — do NOT re-imagine or regenerate the scene. "
        "PRESERVE EXACTLY, pixel-for-pixel: the boat (same side and shape), the pier, the rocks, the crystals, the "
        "water line, the horizon, the whole background, the lighting direction, every OTHER character and all their "
        "accessories, and every prop in its exact position. "
        f"CHANGE ONLY the pose and action of {chars} to: {shot['action']}."
        + identity_line(shot) + worn_line(episode, shot)
        + ((" Hero items present, exactly as their reference: " + "; ".join(item_locks) + ".") if item_locks else "")
        + " Do NOT move the boat, do NOT remove any accessory, do NOT change any other character, do NOT alter the set "
        "or background, do NOT add anything new. Premium 3D CGI Pixar-style, same render quality as the source. 16:9.")
    return prompt, refs

def build_end_prompt(shot, sc=None, master_path=None, start_path=None, episode="Ep1", note=""):
    """End keyframe — built FRESH from refs (plate + character turnarounds), the SAME clean way as the start,
    with end_beat=True so build_keyframe_prompt sources its action text from the beat's own end state.
    Returns (prompt, refs). start_path is an EXISTENCE-GATE only — the LOCK below refuses to build an end
    frame before its own start frame exists — never a visual reference passed into the composition (see the
    inline comment just below for why that approach was tried and abandoned).
    FIXED 2026-07-12 (full-codebase audit continued): this docstring used to claim the end frame carries
    "the start frame as a labelled MOTION ANCHOR" — never true of this function's actual behaviour, and
    directly contradicted by its own inline comment three lines down explaining that passing the start
    frame as a reference caused motion-blur/drift on real renders. Corrected to describe what the code
    actually does.
    master_path defaults to the scene's locked master (the plate) so the character sheet is always included."""
    if not (start_path and os.path.exists(start_path)):
        raise FileNotFoundError(
            f"LOCK: the END frame for shot {shot.get('shotCode')} needs the START frame built first "
            f"(expected at '{start_path}').")
    if master_path is None and sc:
        master_path = sc.get("master")
    # Build the END the SAME clean way as the START (plate + clean turnarounds + magic recipe), framed as the
    # FINISHING beat. Do NOT pass the START frame as a reference: "recreate the START + apply the Action Delta"
    # made Nano re-render the characters with motion blur and DRIFT (the ENDs were always worst). Fresh-from-refs
    # holds identity exactly like the START.
    return build_keyframe_prompt(shot, sc, master_path=master_path, episode=episode, note=note, end_beat=True)

LOCKS = ("LOCKS — do NOT: redesign any character; swap identities, voices or dialogue; mis-sync lips; ADD anything "
         "not in the script (no extra characters, animals, people, objects or background elements) or remove anything "
         "it states; add random or exaggerated gestures; detach or float limbs; shake the camera; add unrequested "
         "cuts; or let anything clip or pass through anything else. Represent the script EXACTLY — nothing added, nothing omitted.")

# FIXED 2026-07-12 (full-codebase audit continued): MOTION_ECONOMY (a constant) plus acting_note/_BEAT_CAM/
# _PHON/_beat_phon/_beat_lines/_beat_delivery (below) were confirmed via repo-wide grep to have zero live
# callers anywhere — every reference to any of them sat inside build_beat_prompt's own body, AFTER that
# function's unconditional `raise RuntimeError(...)` (RETIRED, 2026-07-08), making that body statically
# unreachable Python. Deleted along with the dead body itself (see build_beat_prompt below) rather than
# left as orphaned helpers kept alive by nothing.

# DIRECTOR/CINEMATOGRAPHY — RETIRED 2026-07-14 (restoring the named-auteur-per-chair doctrine,
# CRYSTAL_BEARS_STUDIO_BIBLE.md Law 1): these two constants were written "to be carried into the render
# stages" but, per the 2026-07-08 audit, never actually had a live caller anywhere — the keyframe path
# shipped with no DP/director voice at all. Rather than wire the constants in as-is, their content is now
# woven DIRECTLY into build_keyframe_prompt's own comp/style/light_block construction above (Eggleston on
# composition, Lin on camera, Kalache on lighting) — the real, live path an image actually renders through.
# Deleted here rather than left as a second, unused copy of the same voices sitting dead beside the one
# that actually ships (this codebase's own "no orphaned duplicate of a now-live mechanism" discipline).

def _speakers(shot):
    """Speakers in order of appearance, read from the dialogue labels (NAME:), matched to the cast."""
    chars = shot.get("characters", [])
    labels = re.findall(r"([A-Z][A-Z'’ ]{1,22}?):", shot.get("dialogue") or "")
    def match(label):
        l = label.strip().lower()
        for c in chars:
            if c.lower() == l: return c
        cands = [c for c in chars if c.lower() in l or l in c.lower()]
        return max(cands, key=len) if cands else label.title()
    out = []
    for lab in labels:
        m = match(lab)
        if m not in out: out.append(m)
    if not out and shot.get("speaker"): out = [shot["speaker"]]
    return out

def _music_line(beat):
    """A named-genre, mood-led music cue (genre + mood + emotion read far better to a video model than technical terms).
    musicCue/scoreCue is an optional Director hook (not yet emitted) — until then the cue is comedyMode-generic."""
    cue = (beat.get("musicCue") or beat.get("scoreCue") or "").strip()
    if cue:
        return cue
    cm = str(beat.get("comedyMode") or "").upper()
    if cm == "BIG":
        genre = "Playful, bouncy comedy underscore — light pizzicato strings, ukulele, woodwinds, cartoon stings."
    elif cm == "TRUE":
        genre = "Tender, warm orchestral underscore — soft strings, light piano, gentle and emotional."
    else:
        genre = "Warm, gentle orchestral underscore — soft strings, light woodwinds, harp and warm pads."
    si = (beat.get("soundIntent") or "").strip()
    if si:
        genre += " Score it AROUND the beat's designed sound: " + si
        m = re.search(r"([A-G]#?\s*(?:note\s*)?\d{2,4}\s*Hz)", si)
        if m:
            genre += " Tune the underscore to this pitch and treat it as the crystal leitmotif: " + m.group(1) + "."
    return genre

def _sfx_line(beat):
    """The beat's OWN designed sound — first-class, specific, with its comic SILENCE preserved. Director hook:
    sfxIntent/soundDesign override; fall back to the beat's soundIntent. SFX are HEARD, never spoken (read-aloud guard)."""
    cue = (beat.get("sfxIntent") or beat.get("soundDesign") or beat.get("soundIntent") or "").strip()
    chars = [c for c in (beat.get("characters") or []) if c]
    sq = ("Squeaky's chirps, clicks, trills and squeaks ARE his voice — perform them as expressive, emotion-carrying "
          "vocalisations lip-synced to his mouth; never words, never gibberish, never silent. " if "Squeaky" in chars else "")
    base = ("DESIGNED, synchronised in-world sound effects, tightly timed to the on-screen action. These are SOUND "
            "EFFECTS to be HEARD — never spoken aloud, named, or shown as on-screen text. Soft, rounded, cartoon-warm "
            "— no harsh, loud or scary transients (gentle for ages 4-8). ")
    if cue:
        return (base + sq + "This beat's specific sound design: " + cue
                + " Where the design calls for silence or a held beat, cut ALL sound — SFX, music AND ambience — to a "
                  "clean vacuum at that exact moment, then let the next sound or line land into the silence.")
    return base + sq + "Light, specific diegetic SFX motivated by each action (impacts, footsteps, wing-flutter, fabric, foliage)."

def seedance_json(beat, style=None, episode="Ep1", audio_dur=None):
    """RETIRED (2026-07-01) — the OLD JSON Seedance builder. Do NOT use. The signed-off Gate-3 prompt is the cb_segprompt
    definitive prose (with cb_seedance COMPACT_TIMED_JSON as the fallback for beats without a segment). This function is
    kept only so old references fail LOUD instead of silently building a stale prompt; it raises unconditionally."""
    raise RuntimeError("cb_prompts.seedance_json is RETIRED — the old JSON builder must never render. Use the Gate-3 "
                       "source of truth: cb_segprompt (definitive prose) via cb_seedance.get_seedance_prompt / cb_beats.run.")

def music_brief(beats, sc, episode="Ep1"):
    """Instrumental underscore prompt for a scene's MUSIC BED (no vocals — it sits UNDER dialogue). Derived from
    the scene's pillar + the beats' feeling arc + time/weather, in the show's warm, gentle, hopeful palette.
    The bed is a SCRATCH/preview starting point — Julian refines or replaces it by ear in post."""
    pil = [str(b.get("pillar")) for b in (beats or []) if b.get("pillar")]
    pillar = max(set(pil), key=pil.count) if pil else "wonder"
    feels = [(b.get("physicalFeeling") or b.get("emotionalIntent") or "").strip() for b in (beats or [])]
    feels = [f for f in feels if f][:3]
    arc = "; ".join(feels) if feels else "gentle wonder building to warmth"
    when = " ".join(x for x in ((sc or {}).get("time", ""), (sc or {}).get("weather", "")) if x)
    name = (sc or {}).get("name", "")
    return (f"Instrumental orchestral underscore for a warm, gentle children's animated scene"
            f"{(' set in ' + name) if name else ''}. Theme: {pillar}. Emotional arc: {arc}. "
            f"{(when + '. ') if when else ''}"
            "Soft strings, light woodwinds, harp and warm pads; tender, hopeful, cinematic but understated. "
            "NO vocals, no lyrics, no heavy drums or drops — a calm bed that sits UNDER spoken dialogue, "
            "even dynamics, gently looping, never overpowering the voices.")

# ── MULTI-SHOT BEATS — THE FLOW METHOD (the first-ever way) ───────────────────────────────────────────────
# THE RULE: one Seedance take per BEAT, 10-12 seconds. Group the scene's shots into ~10-12s beats; each beat is ONE
# multi-shot Seedance generation that directs its OWN internal cuts + camera + timing (that's where the flow comes
# from). Chained last-frame -> next-beat start. NOT per-shot clips.
def group_beats(shots, lo=10, hi=12):
    """Split a scene's shots into BEATS whose durations sum to ~10-12s. A small leftover merges into the last beat."""
    beats, cur, tot = [], [], 0
    for s in shots:
        cur.append(s); tot += int(s.get("duration", 5) or 5)
        if tot >= lo:
            beats.append({"shots": cur, "duration": min(hi, max(lo, tot))}); cur, tot = [], 0
    if cur:
        if beats:
            beats[-1]["shots"] += cur; beats[-1]["duration"] = hi
        else:
            beats.append({"shots": cur, "duration": max(lo, min(hi, tot))})
    return beats

def build_beat_prompt(beat_shots, episode="Ep1", note=""):
    """RETIRED (found dead — zero callers anywhere in engine/ — in the 2026-07-08 contradiction sweep). Its
    _beat_lines dialogue-append quotes literal spoken words directly into the prompt, a Law 6 violation the
    instant this were ever called. The live builder is cb_segprompt.shipped_prompt (v5). Guarded rather than
    deleted outright — kept for the record; raises loud.
    Original design note: one continuous Seedance take directing its own cuts/camera across 2-3 shots.
    FIXED 2026-07-12 (full-codebase audit continued): the unreachable body below this raise (statically
    unreachable — AST-confirmed, the raise is unconditional) was stripped, and its private helpers
    (_BEAT_CAM, _PHON, _beat_phon, _beat_lines, _beat_delivery, MOTION_ECONOMY — none with a caller
    anywhere outside this dead body) were deleted along with it, rather than left as orphaned dead code
    kept alive by nothing. DIRECTOR/CINEMATOGRAPHY (also referenced only here) were deleted outright
    2026-07-14 once their content was woven into the live build_keyframe_prompt path instead (see that
    function). PHYSICS is left defined — not named in this finding, not touched."""
    raise RuntimeError("cb_prompts.build_beat_prompt is RETIRED and unused — its dialogue handling leaks "
                        "literal spoken words (Law 6). Use cb_segprompt.shipped_prompt (the v5 engine) instead.")
