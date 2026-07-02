#!/usr/bin/env python3
"""Beat ADDRESSING — the foundation for SURGICAL edits.

Every beat gets an addressable map: its SCENE number + BEAT number, the rendered clip's FRAME RATE, and each internal
SHOT's time + FRAME range (from the Director's authoritative action_timeline). This lets the pipeline target a PORTION
of a beat — a single shot / frame range — and regenerate just that, instead of re-rendering the whole 10-12s take.

    map = beat_address_map(pkg, "1.B4")            # one beat
    scene = scene_address_map(pkg, 1)              # every beat in a scene
    python3 cb_address.py <package.json> [scene|beatCode] [episode]   # CLI dump (+ writes media/<ep>_<code>.map.json)
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
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nk=1:nw=1", clip], capture_output=True, text=True)
        return float(r.stdout.strip() or 0)
    except Exception:
        return 0.0

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
    # SHOTS — the Director's authoritative breakdown (compact action_timeline), each mapped to a FRAME range.
    shots = []
    try:
        g = cb_seedance.get_seedance_prompt(pkg_path, beat_code, mode="render", episode=episode)
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

def write_sidecar(pkg_path, beat_code, episode="Ep1"):
    """Persist a beat's map next to its clip (media/<ep>_<code>.map.json) so the studio + regen can read it."""
    here = os.path.dirname(os.path.abspath(__file__))
    m = beat_address_map(pkg_path, beat_code, episode)
    out = os.path.join(here, "media", f"{episode}_{beat_code}.map.json")
    json.dump(m, open(out, "w"), indent=2, ensure_ascii=False)
    return out

def _tc(sec):
    """seconds -> M:SS.s timecode (maps to the stitched-scene scrubber)."""
    m = int(sec // 60); return f"{m}:{(sec - m*60):04.1f}"

def scene_retake_rows(pkg_path, scene_num, episode="Ep1"):
    """RETAKE-SHEET rows for a scene: every shot with its SCENE-cumulative timecode (so a reviewer watching the
    stitched scene maps a playback moment → the exact beat + shot), the current action, and BLANK columns to fill in
    the requested change. Scene offsets are plain sums of beat durations (hard cuts = no overlap)."""
    sm = scene_address_map(pkg_path, scene_num, episode)
    rows, offset = [], 0.0
    for bm in sm["beats"]:
        for sh in bm.get("shots", []):
            if "start_sec" not in sh:
                continue
            rows.append({
                "Scene": bm["scene"], "Beat": bm["beat"], "Shot": sh["index"],
                "Ref": f"{bm['code']}#shot{sh['index']}",
                "Scene In": _tc(offset + sh["start_sec"]), "Scene Out": _tc(offset + sh["end_sec"]),
                "Beat In": f"{sh['start_sec']:.1f}s", "Beat Out": f"{sh['end_sec']:.1f}s",
                "Frames (in beat)": f"{sh.get('frame_start')}-{sh.get('frame_end')}",
                "Current action": sh.get("action", ""),
                "ISSUE / what's wrong": "", "CHANGE TO (how you want it)": "", "Priority": "",
            })
        offset += bm.get("duration") or 0.0
    return rows

def scene_shot_windows(pkg_path, scene_num, episode="Ep1"):
    """Per-shot SCENE-time windows (float seconds) for the burned-in review overlay:
    [{ref, beat, shot, scene_in, scene_out}]. Offsets are plain sums of beat durations (hard cuts = no overlap)."""
    sm = scene_address_map(pkg_path, scene_num, episode)
    wins, offset = [], 0.0
    for bm in sm["beats"]:
        for sh in bm.get("shots", []):
            if "start_sec" not in sh:
                continue
            wins.append({"ref": f"{bm['code']}#shot{sh['index']}", "beat": bm["beat"], "shot": sh["index"],
                         "scene_in": round(offset + sh["start_sec"], 3), "scene_out": round(offset + sh["end_sec"], 3)})
        offset += bm.get("duration") or 0.0
    return wins

def shot_at_time(pkg_path, scene_num, episode, t):
    """The shot whose SCENE-time window contains t seconds (maps a review-video timecode → the shot to retake)."""
    for w in scene_shot_windows(pkg_path, scene_num, episode):
        if w["scene_in"] <= t < w["scene_out"]:
            return w
    ws = scene_shot_windows(pkg_path, scene_num, episode)
    return ws[-1] if (ws and t >= ws[-1]["scene_out"]) else None   # past the end → the last shot

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
