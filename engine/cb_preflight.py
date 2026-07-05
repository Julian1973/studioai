#!/usr/bin/env python3
"""cb_preflight.py — THE MANIFEST enforcement tool (CLAUDE.md rule 37, MANIFEST.md, 2026-07-06, Julian's
ruling — "blanks BLOCK on both contracts... a missing field halts with the field named").

ONE command: checks the CURRENT beat package against BOTH contracts (TECHNICAL, CREATIVE) — per beat, per
scene, per character, per package — and prints a PASS/FAIL gap table, every gap named. This tool only
REPORTS — it never fires, retakes, signs, or edits anything. `manifest_ok(pkg_path, scene, episode)` is the
importable choke-point every gate-arming call site (cb_pipeline.approve, cb_beats.fire_next_beat,
cb_replicator.walk_scene, cb-studio/serve.py's fire/approve endpoints) calls before proceeding — see
MANIFEST.md's "Gate ordering in code" section.

    python3 cb_preflight.py [package.json] [--episode=EpN] [--scene=N]

Deliberately CHEAP and LOCAL: no vision/LLM calls (this runs on every gate-arming check, potentially many
times per session) — structural/text checks only. Deeper vision-based QA (cb_qa.check_plate's crystal-shape
verdict, cb_qa.check_clip's identity/anatomy checks) already runs at its own natural build/render points
elsewhere in the pipeline; this tool does not re-trigger them.
"""
import os, sys, json, re, glob

HERE = os.path.dirname(os.path.abspath(__file__))
CHARACTERS_PATH = os.path.join(HERE, "config", "characters.json")

# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# Package resolution — same glob convention as cb_pipeline._resolve_pkg / cb_golden._resolve_pkg_path, never
# a hardcoded filename or episode.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _resolve_pkg(episode=None):
    pattern = f"{episode}_*beat_package.json" if episode else "*beat_package.json"
    cands = glob.glob(os.path.join(HERE, "..", "cb-output", pattern))
    if not cands and episode:
        cands = glob.glob(os.path.join(HERE, "..", "cb-output", f"{episode}_*shot_package.json"))
    if not cands:
        cands = glob.glob(os.path.join(HERE, "..", "cb-output", "*shot_package.json"))
    return max(cands, key=os.path.getmtime) if cands else None


class Gap:
    """One named finding. kind: 'BLOCK' (a required field is blank/missing) | 'FLAG' (advisory — a computed
    check with no fixed bar, or a best-effort heuristic) | 'STRUCTURAL' (already impossible to violate by
    construction, reported so 'every gap named' doesn't quietly skip it)."""
    __slots__ = ("scope", "code", "field", "kind", "detail")
    def __init__(self, scope, code, field, kind, detail=""):
        self.scope = scope      # "beat" | "scene" | "character" | "package"
        self.code = code        # beat code, scene number, character name, or "package"
        self.field = field
        self.kind = kind
        self.detail = detail
    def line(self):
        tag = {"BLOCK": "BLOCK", "FLAG": "FLAG ", "STRUCTURAL": "OK   "}[self.kind]
        d = f" — {self.detail}" if self.detail else ""
        return f"  [{tag}] {self.scope} {self.code}: {self.field}{d}"


def _blank(v):
    return v is None or (isinstance(v, str) and not v.strip())


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# TECHNICAL CONTRACT — per beat
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
_HOLD_RE = re.compile(r"(\d+(?:\.\d+)?)[\s-]*second")

def check_beat_technical(beat, is_scene_opener):
    code = beat.get("beatCode") or beat.get("shotCode") or "?"
    gaps = []

    if _blank(beat.get("endState")):
        gaps.append(Gap("beat", code, "endState", "BLOCK", "this beat's own settle text — required on every beat"))
    if _blank(beat.get("endStateStill")):
        gaps.append(Gap("beat", code, "endStateStill", "BLOCK", "static-photograph counterpart to endState — required on every beat"))
    if _blank(beat.get("carryMarks")):
        gaps.append(Gap("beat", code, "carryMarks", "BLOCK", "short phrase naming what persists — required on every beat"))

    jt = beat.get("junctionType")
    if is_scene_opener:
        pass   # the scene's first beat has no predecessor to join from — junctionType doesn't apply
    elif _blank(jt):
        gaps.append(Gap("beat", code, "junctionType", "BLOCK",
                         "not authored (code safely defaults to intentional_next_shot per rule 31, but the "
                         "Manifest wants it declared, not relied on as a silent default)"))

    ph = beat.get("pauseHold")
    if _blank(ph):
        gaps.append(Gap("beat", code, "pauseHold", "BLOCK", "must state a concrete hold duration"))
    else:
        m = _HOLD_RE.search(str(ph))
        if not m:
            gaps.append(Gap("beat", code, "pauseHold", "BLOCK", f"no concrete duration stated in {ph!r}"))
        elif float(m.group(1)) > 1.5:
            gaps.append(Gap("beat", code, "pauseHold", "BLOCK", f"states {m.group(1)}s — staging law caps holds at <=1.5s"))

    if not is_scene_opener and jt != "seamless_continuation":
        oo = beat.get("opensOn") or {}
        if not (isinstance(oo, dict) and oo.get("who") and oo.get("action")):
            gaps.append(Gap("beat", code, "opensOn", "BLOCK", "required for an intentional_next_shot beat (the default) — {who, action}"))

    if _blank(beat.get("actingContrast")):
        gaps.append(Gap("beat", code, "actingContrast", "BLOCK", "required on every beat"))

    speakers = [s for s in (beat.get("speakers") or []) if s]
    dlg_all = []
    for c in (beat.get("cuts") or []):
        d = (c.get("dialogue") or "").strip()
        if d:
            sp = d.split(":", 1)[0].strip().title()
            if sp and sp.lower() != "all":   # a group_chorus line ("ALL: ...") isn't tied to one speaker's order
                dlg_all.append(sp)
    first_order = []   # distinct speakers, in FIRST-APPEARANCE order — alternating dialogue (A, B, A) is normal
    for sp in dlg_all:
        if sp not in first_order:
            first_order.append(sp)
    if speakers and first_order:
        # speakers[] may legitimately list more names than get an individual line (a chorus participant covered
        # only by an "ALL:" line, say) — only the RELATIVE ORDER of names that DO speak individually is checked,
        # never the full list length, so a chorus-only participant listed alongside them is not a false mismatch.
        norm_speakers = [s.strip().title() for s in speakers]
        speakers_subset = [s for s in norm_speakers if s in first_order]
        missing_names = [s for s in first_order if s not in norm_speakers]
        if missing_names:
            gaps.append(Gap("beat", code, "speaker order", "BLOCK",
                            f"{missing_names} speak(s) individually in cuts[] but is not listed in speakers[]={speakers}"))
        elif speakers_subset != first_order:
            gaps.append(Gap("beat", code, "speaker order", "BLOCK",
                            f"speakers={speakers} orders its individual speakers as {speakers_subset}, but cuts[] "
                            f"has them speak in this order: {first_order}"))
    elif first_order and not speakers:
        gaps.append(Gap("beat", code, "speaker order", "BLOCK", f"cuts[] has dialogue ({first_order}) but speakers[] is empty"))

    # single gag arc — best-effort structural heuristic only (cb_qa.py's own comments admit this cannot be
    # a real semantic guarantee: "Law 1's other half... this lint cannot cover at all").
    holds_stated = len(re.findall(r"\bone hold\b", str(ph or "").lower()))
    gag_locks = 1 if beat.get("script_gag_lock_id") else 0
    if _blank(ph) or gag_locks == 0:
        gaps.append(Gap("beat", code, "single gag arc", "FLAG",
                        "heuristic only (no pauseHold and/or no script_gag_lock_id to anchor on) — cannot confirm a single arc"))

    return gaps


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# TECHNICAL CONTRACT — per scene
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def check_scene_technical(scene, episode, gate="1"):
    """The plate is NEVER a manifest BLOCK, in any gate scope (Julian's ruling, 2026-07-06 — "NO plates yet —
    plates are Stage 2, after Gate 1 carries my signature"): its own crystal-shape/no-characters QA already
    runs automatically at Gate-2a build time (cb_qa.check_plate) — a SEPARATE, already-enforced mechanism —
    so the manifest only ever reports whether it exists yet, informationally, never gating a sign-off on it.
    The `gate` param is kept for forward compatibility (a future Gate-2+-only check could use it) but does not
    currently change this function's behaviour."""
    sn = str(scene.get("sceneNumber"))
    gaps = []

    plate_path = os.path.join(HERE, "media", f"{episode}_S{sn}_plate.png")
    if not os.path.exists(plate_path):
        gaps.append(Gap("scene", sn, "plate", "STRUCTURAL",
                        "not built yet — expected at this stage (plates are Stage 2, after Gate 1 is signed); "
                        "its own QA (cb_qa.check_plate) runs automatically once it exists, never gated here"))
    else:
        gaps.append(Gap("scene", sn, "plate", "STRUCTURAL",
                        "plate file exists — its own crystal-shape/no-characters QA already runs at Gate-2a build time (cb_qa.check_plate), not re-triggered here"))

    if _blank(scene.get("ambientBed")):
        gaps.append(Gap("scene", sn, "ambientBed", "BLOCK", "required on every scene"))
    else:
        gaps.append(Gap("scene", sn, "ambientBed", "STRUCTURAL",
                        "present — word-for-word identity across every beat in the scene is already guaranteed by construction (rule 35), not re-checked"))

    try:
        import subprocess
        r = subprocess.run([sys.executable, "sync_scenes.py", "--check"], cwd=HERE,
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0 and f"scene {sn}:" in (r.stdout or ""):
            line = next((l for l in r.stdout.splitlines() if f"scene {sn}:" in l), "").strip()
            gaps.append(Gap("scene", sn, "locations cache sync", "BLOCK", line or "out of sync — run tools/sync_scenes.py"))
    except Exception as e:
        gaps.append(Gap("scene", sn, "locations cache sync", "FLAG", f"could not run tools/sync_scenes.py --check ({str(e)[:80]})"))

    try:
        import cb_qa
        pkg_path = _resolve_pkg(episode)
        vocab = cb_qa.check_scene_vocabulary(pkg_path, sn, episode)
        if not vocab["ok"]:
            gaps.append(Gap("scene", sn, "banned vocabulary", "BLOCK", vocab["verdict"]))
    except Exception as e:
        gaps.append(Gap("scene", sn, "banned vocabulary", "FLAG", f"vocab check failed to run ({str(e)[:80]})"))

    return gaps


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# TECHNICAL CONTRACT — per character
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def check_characters_technical(all_beats):
    gaps = []
    cast = set()
    for b in all_beats:
        cast.update(b.get("characters") or [])
        cast.update(b.get("openingCast") or [])
    try:
        chars = json.load(open(CHARACTERS_PATH))
    except Exception:
        chars = {}
    for name in sorted(cast):
        bible = (chars.get(name) or {}).get("bible") or {}
        if _blank(bible.get("actingRule")):
            gaps.append(Gap("character", name, "actingRule", "BLOCK",
                            "one-line acting essence in characters.json's bible — required for every character who appears"))
    return gaps


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# CREATIVE CONTRACT — per beat / per scene / per package
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def check_beat_creative(beat):
    code = beat.get("beatCode") or beat.get("shotCode") or "?"
    gaps = []
    hl = beat.get("humourLayer")
    if hl is None:
        gaps.append(Gap("beat", code, "humourLayer", "BLOCK",
                        "NEW field (1-4), not yet authored anywhere — presence-only check, never a quality judgment "
                        "(whether the humour actually lands at that layer stays Julian's reserved verdict, rule 28)"))
    elif not (isinstance(hl, int) and 1 <= hl <= 4):
        gaps.append(Gap("beat", code, "humourLayer", "BLOCK", f"present but not an integer 1-4 ({hl!r})"))
    for f, label in (("kidRead", "kidRead"), ("adultRead", "adultRead"), ("want", "want"), ("need", "need")):
        if _blank(beat.get(f)):
            gaps.append(Gap("beat", code, label, "BLOCK", "required on every beat"))
    if _blank(beat.get("emotionMechanic")):
        gaps.append(Gap("beat", code, "emotionMechanic", "BLOCK",
                        "NEW field, not yet authored anywhere — presence-only check, same reserved-verdict caveat as humourLayer"))
    return gaps


def check_scene_creative(scene, scene_beats):
    sn = str(scene.get("sceneNumber"))
    gaps = []

    fz = {"fuzzby": 0, "zenny": 0}
    for b in scene_beats:
        cast = [c.lower() for c in ((b.get("characters") or []) + (b.get("openingCast") or []))]
        if "fuzzby" in cast:
            fz["fuzzby"] += 1
        if "zenny" in cast:
            fz["zenny"] += 1
    if fz["fuzzby"] or fz["zenny"]:
        gaps.append(Gap("scene", sn, "Fuzzby/Zenny ratio", "FLAG",
                        f"computed {fz['fuzzby']}:{fz['zenny']} beats — no stated target ratio exists yet to pass/fail against"))

    pillar = str(scene.get("pillar") or (scene_beats[0].get("pillar") if scene_beats else "") or "").strip().lower()
    is_heart = "heart" in pillar
    if not is_heart:
        has_laugh_beat = any(str(b.get("comedyMode") or "").upper() == "BIG" for b in scene_beats)
        if not has_laugh_beat:
            gaps.append(Gap("scene", sn, "laugh beat per non-Heart pillar", "BLOCK",
                            f"pillar={pillar!r} (not Heart) but no beat in this scene has comedyMode=BIG"))

    if _blank(scene.get("parentLine")):
        gaps.append(Gap("scene", sn, "parentLine", "BLOCK", "NEW field, not yet authored anywhere"))

    return gaps


def check_package_creative(pkg):
    gaps = []
    if _blank(pkg.get("northStarAnswers")):
        gaps.append(Gap("package", "package", "northStarAnswers", "BLOCK",
                        "the North Star 'six questions' do not exist as a literal six anywhere in canon "
                        "(CRYSTAL_BEARS_LOCKED_CANON.md states 4 test questions + 8 craft laws) — field missing "
                        "AND the exact six questions need Julian's own definition before this check can mean "
                        "more than 'a field exists'"))
    return gaps


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# THE FULL RUN
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def run(pkg_path, episode="Ep1", scene_filter=None, gate="1"):
    """gate='1' (default): Gate 1's own manifest scope — everything except the scene plate (Stage 2, per
    Julian's 2026-07-06 ruling). gate='2' or later: the full manifest, plate included."""
    d = json.load(open(pkg_path))
    all_beats = d.get("beats") or d.get("shots") or []
    scenes = d.get("scenes") or []
    if scene_filter:
        all_beats = [b for b in all_beats if str(b.get("sceneNumber")) == str(scene_filter)]
        scenes = [s for s in scenes if str(s.get("sceneNumber")) == str(scene_filter)]

    gaps = []
    by_scene = {}
    for b in all_beats:
        by_scene.setdefault(str(b.get("sceneNumber")), []).append(b)
    for sn, beats in by_scene.items():
        beats.sort(key=lambda b: str(b.get("beatCode") or b.get("shotCode") or ""))
        opener_code = beats[0].get("beatCode") or beats[0].get("shotCode")
        for b in beats:
            code = b.get("beatCode") or b.get("shotCode")
            gaps.extend(check_beat_technical(b, is_scene_opener=(code == opener_code)))
            gaps.extend(check_beat_creative(b))

    for s in scenes:
        sn = str(s.get("sceneNumber"))
        gaps.extend(check_scene_technical(s, episode, gate=gate))
        gaps.extend(check_scene_creative(s, by_scene.get(sn, [])))

    gaps.extend(check_characters_technical(all_beats))
    if not scene_filter:
        gaps.extend(check_package_creative(d))

    return gaps, all_beats, scenes


def _beat_pass(code, gaps):
    return not any(g.kind == "BLOCK" and g.scope == "beat" and g.code == code for g in gaps)


def print_report(gaps, all_beats, scenes):
    blocks = [g for g in gaps if g.kind == "BLOCK"]
    flags = [g for g in gaps if g.kind == "FLAG"]
    structural = [g for g in gaps if g.kind == "STRUCTURAL"]

    print("=" * 100)
    print("THE MANIFEST — cb_preflight gap table (CLAUDE.md rule 37 / MANIFEST.md)")
    print("=" * 100)

    print(f"\n--- PER-BEAT PASS/FAIL ({len(all_beats)} beats) ---")
    codes = [b.get("beatCode") or b.get("shotCode") for b in all_beats]
    for code in codes:
        beat_gaps = [g for g in gaps if g.scope == "beat" and g.code == code]
        beat_blocks = [g for g in beat_gaps if g.kind == "BLOCK"]
        status = "PASS" if not beat_blocks else f"FAIL ({len(beat_blocks)} block{'s' if len(beat_blocks) != 1 else ''})"
        print(f"  {code}: {status}")
        for g in beat_gaps:
            if g.kind != "STRUCTURAL":
                print(f"      {g.line().strip()}")

    print(f"\n--- PER-SCENE ({len(scenes)} scenes) ---")
    for s in scenes:
        sn = str(s.get("sceneNumber"))
        scene_gaps = [g for g in gaps if g.scope == "scene" and g.code == sn]
        scene_blocks = [g for g in scene_gaps if g.kind == "BLOCK"]
        status = "PASS" if not scene_blocks else f"FAIL ({len(scene_blocks)} block{'s' if len(scene_blocks) != 1 else ''})"
        print(f"  scene {sn}: {status}")
        for g in scene_gaps:
            print(f"      {g.line().strip()}")

    char_gaps = [g for g in gaps if g.scope == "character"]
    if char_gaps:
        print(f"\n--- PER-CHARACTER ---")
        for g in char_gaps:
            print(f"  {g.line().strip()}")

    pkg_gaps = [g for g in gaps if g.scope == "package"]
    if pkg_gaps:
        print(f"\n--- PER-PACKAGE ---")
        for g in pkg_gaps:
            print(f"  {g.line().strip()}")

    print(f"\n--- SUMMARY BY FIELD (every gap named, rolled up) ---")
    by_field = {}
    for g in blocks + flags:
        by_field.setdefault((g.field, g.kind), []).append(f"{g.scope} {g.code}")
    for (field, kind), where in sorted(by_field.items(), key=lambda kv: (-len(kv[1]), kv[0][0])):
        print(f"  [{kind}] {field}: {len(where)} — {', '.join(where[:12])}{' ...' if len(where) > 12 else ''}")

    beats_pass = sum(1 for code in codes if _beat_pass(code, gaps))
    print(f"\n{'=' * 100}")
    print(f"TOTALS: {beats_pass}/{len(all_beats)} beats clean on both contracts. "
          f"{len(blocks)} BLOCK, {len(flags)} FLAG, {len(structural)} STRUCTURAL (already code-enforced, not re-checked).")
    print("No retakes, no fires until the package passes both manifests whole (Julian's ruling, 2026-07-06).")
    print("=" * 100)


def manifest_ok(pkg_path, scene=None, episode="Ep1", gate="1"):
    """THE CHOKE-POINT every gate-arming call site imports and calls before proceeding (MANIFEST.md's "Gate
    ordering in code"). Returns (ok: bool, block_count: int, gaps: list[Gap]) scoped to ONE scene if given,
    else the whole package. ok=True only when zero BLOCK-kind gaps exist in scope. gate='1' (default) is
    Gate 1's own scope (excludes the plate, Stage 2); pass gate='2' or later once a plate is expected to exist."""
    gaps, _, _ = run(pkg_path, episode=episode, scene_filter=scene, gate=gate)
    blocks = [g for g in gaps if g.kind == "BLOCK"]
    return (not blocks), len(blocks), gaps


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    episode = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--episode=")), "Ep1")
    scene_filter = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--scene=")), None)
    gate = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--gate=")), "1")
    pkg_path = args[0] if args else _resolve_pkg(episode)
    if not pkg_path or not os.path.exists(pkg_path):
        print("no production loaded — no beat package found in cb-output/")
        sys.exit(0)
    os.chdir(HERE)
    gaps, all_beats, scenes = run(pkg_path, episode=episode, scene_filter=scene_filter, gate=gate)
    print_report(gaps, all_beats, scenes)
    sys.exit(1 if any(g.kind == "BLOCK" for g in gaps) else 0)
