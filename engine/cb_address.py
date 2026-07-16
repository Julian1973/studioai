#!/usr/bin/env python3
"""Beat ADDRESSING — the foundation for SURGICAL edits.

Every beat gets an addressable map: its SCENE number + BEAT number, the rendered clip's FRAME RATE, and each internal
SHOT's time + FRAME range — derived from the beat's own cuts[] via cb_segprompt._v5_shot_time_ranges for a beat
shipping the v5 DEFINITIVE_PROSE builder (the current, standard path), or from the Director's legacy
action_timeline for a beat still on the older compact cb_seedance builder. This lets the pipeline target a PORTION
of a beat — a single shot / frame range — and regenerate just that, instead of re-rendering the whole beat.

    map = beat_address_map(pkg, "1.B4")            # one beat
    scene = scene_address_map(pkg, 1)              # every beat in a scene
    python3 cb_address.py <package.json> [scene|beatCode] [episode]   # CLI dump to stdout (JSON)

FIXED 2026-07-12 (full-codebase audit continued): this usage line used to claim the CLI dump "+ writes
media/<ep>_<code>.map.json" — __main__ only ever prints the JSON to stdout, no file has ever been written.
Corrected the doc to describe what the CLI actually does; __main__ itself is unchanged.
"""
import os, re, json, subprocess
import cb_seedance

def parse_scene_beat(code):
    """'1.B4' -> ('1','4'); '1.B3a' -> ('1','3a'); '12.B7' -> ('12','7')."""
    m = re.match(r"\s*(\d+)\.B?([0-9]+[A-Za-z]*)", str(code or ""))
    if m:
        return m.group(1), m.group(2)
    parts = str(code or "").split(".")
    return (parts[0] if parts else str(code)), (parts[1].lstrip("Bb") if len(parts) > 1 else "")

def clip_fps(clip):
    """Real frame rate of a rendered clip (r_frame_rate), default 24.0 if absent."""
    if not clip or not os.path.exists(clip):
        return 24.0
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=r_frame_rate", "-of", "default=nk=1:nw=1", clip], capture_output=True, text=True)
        s = r.stdout.strip()
        if "/" in s:
            n, d = s.split("/"); return round(float(n) / float(d), 3) if float(d) else 24.0
        return float(s) if s else 24.0
    except Exception:
        return 24.0

def _clip_duration(clip):
    if not clip or not os.path.exists(clip):
        return 0.0
    # FIXED 2026-07-12 (loose-ends pass): was a hand-rolled ffprobe subprocess call, duplicated across 6
    # files — cb_post._dur() is the canonical probe. Lazy import to avoid a new module-level dependency.
    import cb_post
    return cb_post._dur(clip)

def parse_time_range(s):
    """'2-4s' -> (2.0,4.0); '9.7-10.8s' -> (9.7,10.8); '5s' -> (5.0,5.0). None if unparseable."""
    s = str(s or "").strip().lower().replace("seconds", "").replace("sec", "").replace("s", "")
    m = re.match(r"^\s*([\d.]+)\s*(?:-|–|—|to)\s*([\d.]+)\s*$", s)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.match(r"^\s*([\d.]+)\s*$", s)
    if m:
        return float(m.group(1)), float(m.group(1))
    return None

def beat_address_map(pkg_path, beat_code, episode="Ep1"):
    """The addressable map of ONE beat: {episode, scene, beat, code, slug, fps, duration, total_frames, shots[]}.
    Each shot carries its time AND frame range (frame_start/frame_end) so a portion can be targeted for surgical regen."""
    d = json.load(open(pkg_path)); here = os.path.dirname(os.path.abspath(__file__))
    beat = next((b for b in (d.get("beats") or d.get("shots") or [])
                 if (b.get("beatCode") or b.get("shotCode")) == beat_code), None)
    if not beat:
        return {"error": f"beat {beat_code} not found", "code": beat_code}
    scene = str(beat.get("sceneNumber") or parse_scene_beat(beat_code)[0])
    beatno = parse_scene_beat(beat_code)[1]
    slug = beat.get("slug") or (beat_code or "").replace(".", "_")
    clip = os.path.join(here, "media", f"{episode}_{beat_code}_{slug}.mp4")
    rendered = os.path.exists(clip)
    fps = clip_fps(clip)
    dur = _clip_duration(clip)
    total_frames = int(round(dur * fps)) if dur else 0
    # SHOTS — the Director's authoritative breakdown, mapped to a FRAME range.
    # FIXED 2026-07-08 (confirmed bug): for a beat firing the v5 DEFINITIVE_PROSE builder (get_seedance_prompt's
    # own "raw": True flag), g["prompt"] is a plain compiled-text STRING, not a dict — the old
    # (g.get("prompt") or {}).get("action_timeline") call raised AttributeError on every such beat (silently
    # swallowed by this function's own try/except), leaving shots empty for almost every real beat in production
    # today (only the legacy/compact cb_seedance builder ever populated "action_timeline"). When "raw" is set,
    # derive shots from the beat's OWN cuts[] instead, using cb_segprompt._v5_shot_time_ranges (THE SHOT-TIMING
    # LAW, rule 54) — the same deterministic per-shot time budget the shipped prompt itself is built from, so the
    # address map always matches what actually rendered. The legacy action_timeline path is kept, unchanged, as
    # the fallback for a beat still on the older compact builder.
    shots = []
    try:
        g = cb_seedance.get_seedance_prompt(pkg_path, beat_code, mode="render", episode=episode)
        if g.get("raw"):
            import cb_segprompt
            cuts = beat.get("cuts") or []
            ranges = cb_segprompt._v5_shot_time_ranges(len(cuts)) if cuts else []
            for i, (c, (t0, t1)) in enumerate(zip(cuts, ranges)):
                sh = {"index": i + 1, "time": f"{t0}-{t1}s", "action": (c.get("action") or "")[:180]}
                if c.get("framing"):
                    sh["camera"] = c["framing"]
                sh["start_sec"], sh["end_sec"] = float(t0), float(t1)
                sh["frame_start"] = int(round(t0 * fps))
                sh["frame_end"] = int(round(t1 * fps))
                # CLAMP (2026-07-09 confirmed bug): the v5 shot ranges are divided from the NOMINAL
                # HANDLE_TOTAL, not measured against this clip's own rendered length — a generative
                # render is never guaranteed to pace exactly to that nominal split, so frame_end could
                # point past the real file's last frame otherwise, a real risk for cb_retake.splice_shot().
                # Only clamp when total_frames is truthy (the clip actually exists and was measured) —
                # never clamp to 0 for an unrendered beat.
                if total_frames:
                    sh["frame_start"] = min(sh["frame_start"], total_frames)
                    sh["frame_end"] = min(sh["frame_end"], total_frames)
                shots.append(sh)
        else:
            tl = (g.get("prompt") or {}).get("action_timeline") or []
            for i, st in enumerate(tl):
                sh = {"index": i + 1, "time": st.get("time"), "action": (st.get("action") or "")[:180]}
                if st.get("camera"):
                    sh["camera"] = st["camera"]
                tr = parse_time_range(st.get("time"))
                if tr:
                    sh["start_sec"], sh["end_sec"] = round(tr[0], 3), round(tr[1], 3)
                    sh["frame_start"] = int(round(tr[0] * fps))
                    sh["frame_end"] = int(round(tr[1] * fps))
                    # FIXED 2026-07-11 (full-codebase audit, medium finding): the same out-of-range
                    # frame_end risk the v5/raw branch above was clamped against (2026-07-09) applied
                    # equally here — this legacy action_timeline branch computes frame_start/frame_end
                    # from the same nominal (never rendered-length-measured) time split and had no clamp.
                    if total_frames:
                        sh["frame_start"] = min(sh["frame_start"], total_frames)
                        sh["frame_end"] = min(sh["frame_end"], total_frames)
                shots.append(sh)
    except Exception as e:
        shots = [{"error": str(e)[:140]}]
    return {"episode": episode, "scene": scene, "beat": beatno, "code": beat_code, "slug": slug,
            "rendered": rendered, "fps": fps, "duration": round(dur, 3), "total_frames": total_frames,
            "shot_count": len([s for s in shots if "index" in s]), "shots": shots}

def scene_address_map(pkg_path, scene_num, episode="Ep1"):
    """Every beat in a scene, addressed."""
    d = json.load(open(pkg_path)); scene_num = str(scene_num)
    codes = [b.get("beatCode") or b.get("shotCode") for b in (d.get("beats") or d.get("shots") or [])
             if str(b.get("sceneNumber")) == scene_num]
    return {"episode": episode, "scene": scene_num, "beats": [beat_address_map(pkg_path, c, episode) for c in codes]}

def _tc(sec):
    """seconds -> M:SS.s timecode (maps to the stitched-scene scrubber)."""
    m = int(sec // 60); return f"{m}:{(sec - m*60):04.1f}"

def _scene_shot_walk(pkg_path, scene_num, episode="Ep1"):
    """Shared walk behind scene_retake_rows/scene_shot_windows.
    FIXED 2026-07-12 (full-codebase audit continued, low-severity duplication finding): the two callers used to
    each independently re-implement the identical 'walk sm["beats"], skip an unrendered beat or a shot missing
    start_sec, accumulate the cumulative scene offset' logic — a future fix to that shared rule (like the
    "rendered" skip below, added 2026-07-11) had to land in two near-identical copies, and it's easy for one to
    silently keep the old behaviour while the other gets patched. One generator now yields (bm, sh, scene_in,
    scene_out) for every real, addressable shot; each caller only maps that tuple into its own output shape.
    Offsets are plain sums of beat durations (hard cuts = no overlap)."""
    sm = scene_address_map(pkg_path, scene_num, episode)
    offset = 0.0
    for bm in sm["beats"]:
        # An UNRENDERED beat's shots are still populated from its planned cuts[] (beat_address_map computes them
        # regardless of "rendered"), but the stitched review video (cb_post.assemble_picture) only ever contains
        # RENDERED clips back to back — an unrendered beat contributes ZERO seconds of real footage, not a
        # nominal-duration gap. Including its shots gave them real-looking Scene-In/Out timecodes that collided
        # with whatever beat ACTUALLY occupies that stretch of the stitched video, and inflated `offset` by a
        # duration that was never really elapsed. Skip it entirely — both its shots and its offset contribution.
        if not bm.get("rendered"):
            continue
        for sh in bm.get("shots", []):
            if "start_sec" not in sh:
                continue
            yield bm, sh, offset + sh["start_sec"], offset + sh["end_sec"]
        offset += bm.get("duration") or 0.0

def scene_retake_rows(pkg_path, scene_num, episode="Ep1"):
    """RETAKE-SHEET rows for a scene: every shot with its SCENE-cumulative timecode (so a reviewer watching the
    stitched scene maps a playback moment → the exact beat + shot), the current action, and BLANK columns to fill in
    the requested change. Scene offsets are plain sums of beat durations (hard cuts = no overlap)."""
    rows = []
    for bm, sh, scene_in, scene_out in _scene_shot_walk(pkg_path, scene_num, episode):
        rows.append({
            "Scene": bm["scene"], "Beat": bm["beat"], "Shot": sh["index"],
            "Ref": f"{bm['code']}#shot{sh['index']}",
            "Scene In": _tc(scene_in), "Scene Out": _tc(scene_out),
            "Beat In": f"{sh['start_sec']:.1f}s", "Beat Out": f"{sh['end_sec']:.1f}s",
            "Frames (in beat)": f"{sh.get('frame_start')}-{sh.get('frame_end')}",
            "Current action": sh.get("action", ""),
            "ISSUE / what's wrong": "", "CHANGE TO (how you want it)": "", "Priority": "",
        })
    return rows

def scene_shot_windows(pkg_path, scene_num, episode="Ep1"):
    """Per-shot SCENE-time windows (float seconds) for the burned-in review overlay:
    [{ref, beat, shot, scene_in, scene_out}]. Offsets are plain sums of beat durations (hard cuts = no overlap)."""
    return [{"ref": f"{bm['code']}#shot{sh['index']}", "beat": bm["beat"], "shot": sh["index"],
             "scene_in": round(scene_in, 3), "scene_out": round(scene_out, 3)}
            for bm, sh, scene_in, scene_out in _scene_shot_walk(pkg_path, scene_num, episode)]

def shot_at_time(pkg_path, scene_num, episode, t):
    """The shot whose SCENE-time window contains t seconds (maps a review-video timecode → the shot to retake)."""
    # ONE call, not two — scene_shot_windows -> scene_address_map -> beat_address_map recompiles every beat's
    # prompt via cb_seedance.get_seedance_prompt, a real cost; the old code paid it twice per lookup for no
    # reason (2026-07-08 audit finding).
    ws = scene_shot_windows(pkg_path, scene_num, episode)
    for w in ws:
        if w["scene_in"] <= t < w["scene_out"]:
            return w
    return ws[-1] if (ws and t >= ws[-1]["scene_out"]) else None   # past the end → the last shot

# ── DIALOGUE CAPTIONS (2026-07-14, Julian's front-to-back wiring pass — "we can't just have them as files
# that sit there... whatever it takes to fix it, fix it now"): a delivery-ready video with no captions at all
# is not deliverable content for YouTube/Amazon/Netflix, all of which require them. Built here, not a new
# module, because the hard part — real, SCENE-cumulative timing per shot — is _scene_shot_walk, already proven
# correct for the retake sheet and review overlay above; captioning just needs the one thing those two don't
# carry: the shot's own SPOKEN WORDS.
def _vtt_tc(sec):
    """seconds -> HH:MM:SS.mmm (WebVTT's timecode format — same as SRT's but '.' not ',' before milliseconds)."""
    h = int(sec // 3600); m = int((sec % 3600) // 60); s = int(sec % 60); ms = int(round((sec - int(sec)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

def scene_captions(pkg_path, scene_num, episode="Ep1"):
    """Real dialogue captions for a scene: [{start, end, text}] in SCENE-cumulative seconds, one entry per
    SPOKEN cut. THE WORDS come from the beat's own cuts[].dialogue field ("SPEAKER: line") — the same ground-
    truth field cb_preflight.check_scene_dialogue_verbatim already treats as authoritative; never re-derived
    from the compiled Seedance prompt text, which deliberately never contains spoken words at all (Law 6). A
    shot with no dialogue (the common case — action/reaction beats) contributes no caption, matching normal
    captioning practice (captions cover what's SAID, not a narration of every action).

    KNOWN LIMITATION, STATED HONESTLY: a caption's on-screen window is its whole SHOT's time range (the same
    window scene_shot_windows already uses for the review overlay), not word-level forced alignment against
    the rendered clip's own audio — a real ASR/alignment pass is a materially bigger feature (a new STT
    dependency + cost) than "derive captions from the dialogue and shot timing we already have," which is what
    this function does. Good enough for a real, deliverable caption track; not frame-accurate lip-sync timing."""
    import cb_preflight
    d = json.load(open(pkg_path))
    beats_by_code = {(b.get("beatCode") or b.get("shotCode")): b
                      for b in (d.get("beats") or d.get("shots") or []) if str(b.get("sceneNumber")) == str(scene_num)}
    caps = []
    for bm, sh, scene_in, scene_out in _scene_shot_walk(pkg_path, scene_num, episode):
        beat = beats_by_code.get(bm["code"])
        if not beat:
            continue
        cuts = beat.get("cuts") or []
        idx = sh["index"] - 1
        if idx < 0 or idx >= len(cuts):
            continue
        raw = (cuts[idx].get("dialogue") or "").strip()
        if not raw or ":" not in raw:
            continue
        speaker = cb_preflight._dialogue_speaker(raw)
        words = raw.split(":", 1)[1].strip()
        if not words:
            continue
        # A group_chorus/"ALL:" line is a unison delivery, not one named speaker (cb_preflight's own speaker-
        # order check already excludes it the same way, line ~174) — captioned plain, no invented speaker label.
        label = f"{speaker.title()}: " if (speaker and speaker.upper() != "ALL") else ""
        caps.append({"start": round(scene_in, 3), "end": round(scene_out, 3), "text": f"{label}{words}"})
    return caps

def write_captions(pkg_path, scene_num, episode="Ep1", out=None, fmt="srt"):
    """Write scene_captions() to a real .srt or .vtt file. Returns (path, n_captions). fmt="vtt" for YouTube/
    web-native WebVTT; "srt" (default) for the universal SubRip format every other platform/NLE accepts."""
    caps = scene_captions(pkg_path, scene_num, episode)
    fmt = fmt.lower()
    out = out or os.path.join(os.path.dirname(os.path.abspath(__file__)), "media",
                               f"{episode}_Scene{scene_num}_captions.{fmt}")
    if fmt == "vtt":
        lines = ["WEBVTT", ""]
        for i, c in enumerate(caps, 1):
            lines += [str(i), f"{_vtt_tc(c['start'])} --> {_vtt_tc(c['end'])}", c["text"], ""]
    else:
        import cb_post
        lines = []
        for i, c in enumerate(caps, 1):
            lines += [str(i), f"{cb_post._srt_tc(c['start'])} --> {cb_post._srt_tc(c['end'])}", c["text"], ""]
    open(out, "w", encoding="utf-8").write("\n".join(lines))
    return out, len(caps)

RETAKE_COLS = ["Scene", "Beat", "Shot", "Ref", "Scene In", "Scene Out", "Beat In", "Beat Out",
               "Frames (in beat)", "Current action", "ISSUE / what's wrong", "CHANGE TO (how you want it)", "Priority"]

def write_retake_csv(pkg_path, scene_num, episode="Ep1", out=None):
    """Write the scene's retake sheet as a CSV (opens in Excel). Returns (path, n_rows)."""
    import csv
    rows = scene_retake_rows(pkg_path, scene_num, episode)
    out = out or os.path.join(os.path.dirname(os.path.abspath(__file__)), "media",
                              f"{episode}_Scene{scene_num}_RETAKES.csv")
    with open(out, "w", newline="", encoding="utf-8-sig") as f:   # utf-8-sig so Excel reads accents cleanly
        w = csv.DictWriter(f, fieldnames=RETAKE_COLS); w.writeheader(); w.writerows(rows)
    return out, len(rows)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: cb_address.py <package.json> [scene|beatCode] [episode]"); raise SystemExit(2)
    pkg = sys.argv[1]; target = sys.argv[2] if len(sys.argv) > 2 else None
    ep = sys.argv[3] if len(sys.argv) > 3 else "Ep1"
    if target and re.match(r"\d+\.B", target):
        print(json.dumps(beat_address_map(pkg, target, ep), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(scene_address_map(pkg, target or "1", ep), indent=2, ensure_ascii=False))
