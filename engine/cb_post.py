#!/usr/bin/env python3
"""cb_post.py — GENERALIZED post (replaces the ad-hoc build_scene*_post.py).

POST = CURATION (the quality filter — NOT composition). The hardest creative work happens at GATE 3: Seedance
scores each take — the acted ElevenLabs V3 voice + Seedance's own synchronised SFX and TIMED comedy/emotional
music (its timing is the point) are ALREADY in the clip audio. Gate 5 LISTENS and decides what Seedance got
right — keeps what works, trims or replaces what doesn't. For a scene Post:
  1) ASSEMBLES the picture via assemble_conformed — JOIN ON LIVE MOTION (Julian, 2026-07-03: "the last frame
     needs to be the start of the next frame... we need to get it to flow across") — the settle is trimmed off
     every clip but the last so cuts land mid-motion, not hold-into-hold; still HARD CUTS shot-to-shot (no
     in-scene cross-dissolves — those are reserved for BETWEEN scenes only), still keeps the clip audio (voice
     + SFX + Seedance's timed music). WIRED IN 2026-07-14 (Julian's front-to-back wiring pass) — this function
     was fully built (2026-07-03) and documented as Gate 5's own doctrine but had zero live callers until now
     (confirmed by rules 46/49's own audits); assemble_picture (the raw butt-join) still runs too, saved
     alongside as `_picture_RAW.mp4`, the named "deliberate comparison baseline" it always was.
  2) MASTERS to broadcast loudness -> a preview "complete" mix, defaulting to YouTube's own target (unchanged
     behaviour). The ElevenLabs Music bed is the FALLBACK, not the default — fired ONLY if Seedance's own music
     isn't right for a scene: a hand-supplied MUSIC.mp3 (always wins) or CB_AUTO_MUSIC_BED=1 (scratch underscore)
     gets ducked under the voice; otherwise Post keeps the clip's score.
     REAL PER-PLATFORM MASTERS (2026-07-14, Julian's front-to-back wiring pass — "script to post to YouTube, to
     Amazon, Netflix"): LOUDNESS_TARGETS names each platform's own published loudness spec; mix()'s previously-
     hardcoded -14 LUFS is now an explicit, chosen default (still YouTube, still -14, nothing regresses), and
     build_platform_masters() delivers a separately-mastered file per platform from the picture already built
     above (`python3 cb_post.py masters <pkg> <scene> [ep] [platforms]`, or `cb_pipeline.py masters <scene>`).
     SFX SWEETENING (2026-07-14, rule 82): before mastering, sweeten_cues_for_scene() layers the show's own
     signature one-shots (FWIP/THUP/POLLEN_PUFF/POP) onto a matching beat's own resolved archetype, additively,
     into the SAME mix() call, threaded through every platform master — see mix()'s own sfx_layers param. Best-
     effort and asset-gated: a cue with no file yet on disk (shows/crystal-bears/canon/sfx/ is currently empty)
     is silently skipped, never blocks Gate 5.
  3) Exports STEMS (picture+voice, music, ambience) so Julian curates the final keep/trim/replace + mix in CapCut by ear.
  4) BUILDS THE SECOND MASTER — a 9:16 centre-safe vertical derivative (build_vertical_derivative, 2026-07-14 —
     CLAUDE.md rule 28's own doctrine has always named "two masters delivered," only the 16:9 one ever actually
     got built) — a static, centre-anchored crop scaled to 1080x1920, alongside real dialogue captions
     (scene_captions/write_captions, .srt + .vtt) — both delivery-required, both non-fatal to the primary master.

The clip audio is never stripped. Post is the quality filter + the seamless stitch + the stems — never the creative layer.

    python3 cb_post.py <package.json> <sceneNumber> [episode=Ep1]
"""
import json, sys, os, subprocess, shutil

HELD = 1.6   # held last frame (tension beat)
# FIXED 2026-07-12 (full-codebase audit continued): removed the unused `XF = 0.4` cross-dissolve-duration constant
# — grepped clean across the whole repo, zero references anywhere outside its own definition. It was reserved for
# a between-scenes cross-dissolve transition (per assemble_picture's/assemble_conformed's own docstrings), but no
# such episode-level assembly function exists anywhere yet; re-add it the day that feature is actually built.
AUTO_MUSIC_BED = os.environ.get("CB_AUTO_MUSIC_BED", "") == "1"   # OFF by default — Seedance scores the clip; a bed
                                                                 # on top is a deliberate, opt-in/CapCut decision

# ── SFX SWEETENING (2026-07-14, CLAUDE.md rule 82 — Julian: "go with those two things you flagged") ──────────
# THE MECHANISM, NOT THE ASSETS: this closes the gap CAPCUT_README.txt itself once named as "confirmed, not
# attempted here... needs real recorded/licensed audio assets this code-only pass has no way to source." That
# is still true — no audio files exist yet (shows/crystal-bears/canon/sfx/ is empty, see its own README) — but
# the SOFTWARE that will layer a real one-shot onto a weak comedy hit the moment a file is dropped in can be,
# and now is, built and tested against zero-asset degradation. Scoped to EXACTLY the four signature one-shots
# this show's own doctrine already names (CRYSTAL_BEARS_STUDIO_BIBLE.md, CLAUDE.md rule 57) — never expanded
# to every archetype's own plausible sound on my own initiative; a research pass found several other archetypes
# with a nameable sound (WHOOMP, THUMP, RUMBLE, SPLASH...) but adding those would be inventing new doctrine, not
# building what's already named — left for Julian's own call, not decided here.
SFX_LIBRARY_PATH = "config/sfx_library.json"   # -> shows/crystal-bears/canon/sfx_library.json, the usual symlink
# ARCHETYPE -> CUE, grounded directly in each archetype's own physics_rule/visual_payoff_rule text (cb_seedance.
# PHYSICAL_ARCHETYPES) — never a guess. POLLEN_SMEAR_TUMBLE maps to POP, not THUP, because that archetype's own
# visual_payoff_rule is explicit: "The pop-up line is the finisher; the THUPs are mid-flight bounces, not the
# end" — matching this function's own last-shot placement heuristic below. Archetypes with no comedy one-shot
# implied (dramatic/serious beats, pure-stillness beats) are deliberately absent, not force-mapped.
ARCHETYPE_TO_SFX_CUE = {
    "LEAF_CRASH_REBOUND": "FWIP",
    "POLLEN_FACE_PRESS_REVEAL": "POLLEN_PUFF",
    "POLLEN_SMEAR_TUMBLE": "POP",
    "FLOWER_STUCK_BUTTON": "POLLEN_PUFF",
    "CRASH_ARRIVAL_HEAP": "THUP",
}

def _load_sfx_library():
    """Graceful-degrade load (matching mix()'s own have_mus/have_amb convention, never gag_locks.json's hard-
    fail-on-missing-key convention — an asset-availability question, not a content-correctness one). Missing
    manifest or malformed JSON both degrade to an empty library, never raise."""
    try:
        d = json.load(open(SFX_LIBRARY_PATH))
        return {k: v for k, v in d.items() if not k.startswith("_")}
    except Exception:
        return {}

def sweeten_cues_for_scene(pkg, scene_num, episode="Ep1"):
    """Best-effort candidate list of (cue_id, file, at_sec, beatCode) for THIS scene's own rendered beats —
    never a required input, never blocks Gate 5. For each rendered beat (a real clip must already exist on
    disk, matching _clips' own definition of "rendered"), resolves its physical archetype the IDENTICAL way
    the shipped v5 prompt already does (cb_segprompt.resolve_physical_archetype — so a sweetened cue never
    disagrees with what the beat's own prompt already asked for), maps it to a cue via ARCHETYPE_TO_SFX_CUE,
    and places it at the LAST rendered shot's scene-cumulative start time (cb_address.scene_shot_windows) —
    a best-effort placement heuristic, not frame-exact: this codebase has no per-shot "this is the payoff
    instant" field to place against, and the archetype system's own convention (e.g. POLLEN_SMEAR_TUMBLE's own
    stated "the pop-up... is the finisher... not the end") is that a beat's own payoff lands in its later
    shots, so its last shot is the most defensible simple anchor. NAMED LIMITATION, not silently glossed over:
    a sweetening cue is NOT currently sidechain-ducked against dialogue the way music already is — if the
    placed timecode overlaps a spoken line, this could mask it; real asset population should account for that
    by ear (CapCut is where Julian ultimately curates this, same as every other stem). Only cues whose file
    actually exists on disk are ever returned — a manifest entry with no asset present is silently omitted,
    never an error."""
    lib = _load_sfx_library()
    if not lib:
        return []
    try:
        import cb_address, cb_segprompt
        d = json.load(open(pkg))
        beats = [b for b in (d.get("beats") or d.get("shots") or []) if str(b.get("sceneNumber")) == str(scene_num)]
        scenes = d.get("scenes") or []
        scene = next((s for s in scenes if str(s.get("sceneNumber")) == str(scene_num)), {})
        rendered_codes = {os.path.basename(p).split("_", 2)[1] for p in _clips(pkg, episode, str(scene_num))}
        windows = cb_address.scene_shot_windows(pkg, scene_num, episode)
        # windows[i]["beat"] is the BARE BEAT NUMBER (int, from cb_address.beat_address_map's own "beatno"),
        # never the beat-CODE string ("1.B1") — confirmed by reading beat_address_map directly before trusting
        # this. The real per-window beat-code lives in "ref" (f"{code}#shot{n}"), the same field
        # write_retake_csv's own "Ref" column is built from — split on the SAME "#shot" separator every other
        # consumer of this field already uses, not a guess at a new one.
        def _window_beat_code(w): return str(w.get("ref", "")).split("#shot")[0]
    except Exception as e:
        print(f"  SFX sweetening candidates skipped ({str(e)[:140]})", flush=True)
        return []
    out = []
    for beat in beats:
        code = beat.get("beatCode") or beat.get("shotCode")
        if code not in rendered_codes:
            continue
        archetype = cb_segprompt.resolve_physical_archetype(beat, scene)
        cue_id = ARCHETYPE_TO_SFX_CUE.get(archetype)
        if not cue_id or cue_id not in lib:
            continue
        beat_windows = [w for w in windows if _window_beat_code(w) == code]
        if not beat_windows:
            continue
        at_sec = max(w["scene_in"] for w in beat_windows)   # last rendered shot's own start = the payoff anchor
        rel = lib[cue_id].get("file", "")
        sfx_path = os.path.normpath(os.path.join(os.path.dirname(SFX_LIBRARY_PATH), rel)) if rel else ""
        if not sfx_path or not os.path.exists(sfx_path):
            continue
        out.append({"cue_id": cue_id, "file": sfx_path, "at_sec": at_sec, "beatCode": code})
    return out

def _dur(p):
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=nk=1:nw=1",p],
                       capture_output=True, text=True)
    try: return float(r.stdout.strip())
    except: return 0.0

def _clips(pkg, episode, scene_num):
    d = json.load(open(pkg)); out = []
    for s in (d.get("beats") or d.get("shots") or []):
        if str(s.get("sceneNumber")) != scene_num: continue
        s.setdefault("shotCode", s.get("beatCode"))
        # dict.get(key, default) evaluates `default` EAGERLY, even when `key` is already present — so the old
        # s.get("slug", s["shotCode"].replace(...)) called .replace() on s["shotCode"] unconditionally, crashing
        # with a raw AttributeError the moment a beat had neither beatCode nor shotCode (shotCode ends up None,
        # setdefault does not fix that). 2026-07-08 audit finding.
        code = s.get("shotCode") or ""
        slug = s.get("slug") or code.replace(".", "_")
        # FIXED 2026-07-12 (full-codebase audit continued): this still read s['shotCode'] directly instead of the
        # safely-computed `code` right above — the 2026-07-08 crash fix (comment above) only covered `slug`'s eager-
        # default crash and left this path construction pointing at the same unsafe field. For a beat missing both
        # beatCode and shotCode, s['shotCode'] is None, so the f-string embedded the literal substring "None" into
        # the path instead of the already-computed empty string — half-applied, now consistent.
        p = f"media/{episode}_{code}_{slug}.mp4"
        if os.path.exists(p): out.append(p)
    return out

def _has_audio(p):
    r = subprocess.run(["ffprobe","-v","error","-select_streams","a","-show_entries","stream=codec_type",
                        "-of","csv=p=0", p], capture_output=True, text=True)
    return "audio" in r.stdout

def _ensure_audio(clip):
    """Stitching concatenates audio across the hard cuts, which needs every clip to HAVE an audio stream. Silent clips
    (no dialogue) have none — give them a silent track so the cut assembles cleanly."""
    if _has_audio(clip): return clip
    os.makedirs("media/_tmp", exist_ok=True)
    tmp = f"media/_tmp/{os.path.basename(clip).rsplit('.',1)[0]}_aud.mp4"
    r = subprocess.run(["ffmpeg","-y","-i",clip,"-f","lavfi","-i","anullsrc=channel_layout=stereo:sample_rate=44100",
                    "-shortest","-c:v","copy","-c:a","aac","-b:a","128k", tmp], capture_output=True)
    if r.returncode or not os.path.exists(tmp):
        print("_ensure_audio ERROR:", (r.stderr or b"").decode(errors="replace")[-400:])
        return clip   # fall back to the original (silent) clip — surfaces immediately and clearly inside
                       # assemble_picture's own existing returncode check, rather than a confusing downstream error
    return tmp

def _norm(clips): return [_ensure_audio(c) for c in clips]

def assemble_picture(clips, out):
    """HARD-CUT concat of the scene's clips (instant shot-to-shot, NO in-scene cross-dissolves) + a brief held last
    frame for the scene end, keeping native voice. Cross-dissolves belong only between scenes (passage of time)."""
    inputs = []
    for c in clips: inputs += ["-i", c]
    fc = []
    if len(clips) == 1:
        fc.append(f"[0:v]tpad=stop_mode=clone:stop_duration={HELD}[v]")
        fc.append(f"[0:a]apad=pad_dur={HELD}[a]")
    else:
        # HARD CUTS within a scene — instant, shot-to-shot. NO cross-dissolves between beats; a cross-dissolve is
        # reserved ONLY for a passage-of-time transition BETWEEN scenes (a separate, episode-level assembly). We just
        # concatenate the clips end-to-end (concat filter), then hold the final frame briefly for the scene's end.
        for i in range(len(clips)):
            fc.append(f"[{i}:v]setsar=1,format=yuv420p[v{i}]")
            fc.append(f"[{i}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{i}]")
        joins = "".join(f"[v{i}][a{i}]" for i in range(len(clips)))
        fc.append(f"{joins}concat=n={len(clips)}:v=1:a=1[cv][ca]")
        fc.append(f"[cv]tpad=stop_mode=clone:stop_duration={HELD}[v]")
        fc.append(f"[ca]apad=pad_dur={HELD}[a]")
    cmd = ["ffmpeg","-y"] + inputs + ["-filter_complex", ";".join(fc),
           "-map","[v]","-map","[a]","-c:v","libx264","-preset","medium","-crf","18","-pix_fmt","yuv420p",
           "-c:a","aac","-b:a","256k","-movflags","+faststart", out]   # +faststart: moov up front so browsers stream it (no stall)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode or not os.path.exists(out):
        # FIXED 2026-07-12 (full-codebase audit continued): this used to only print an error and then return
        # _dur(out) unconditionally — 0.0 on a failed/missing file, a signal run() never actually checked (it
        # discarded the return value entirely and unconditionally printed a success line right after calling this).
        # A real ffmpeg failure (mismatched resolution/pixel format, a truncated or codec-surprising clip) would
        # print "assemble_picture ERROR: ..." here and then have run() print the picture-success line anyway, feed
        # the never-written `out` into mix(), and eventually crash several steps later at the CapCut stems copy —
        # far from the real diagnosis. Return None on failure so the caller can check it and stop immediately
        # (matching the fix already applied to cb_previz.assemble_beat_clip per the 2026-07-08 audit note).
        print("assemble_picture ERROR:", r.stderr[-400:])
        return None
    return _dur(out)

def _settle_trim():
    """The settle-trim length in seconds — read LIVE from cb_segprompt.HANDLE_SETTLE via a function-scoped
    import, matching this codebase's established deferred-import convention for this module pair (e.g.
    cb_scene.py's own relay_source_for / _settle_window). 2026-07-08 audit fix: this used to be a plain
    hardcoded local literal (SETTLE_TRIM = 2.0) that merely "matched" HANDLE_SETTLE by comment, with no actual
    import tying the two together — a future change to HANDLE_SETTLE would have silently stopped propagating
    here. Same fix applied to cb_scene.py's SETTLE_WINDOW."""
    # RE-HOMED (architecture recovery, 2026-07-16, THE_DEFINITIVE_PIPELINE.md re-home item 1):
    # cb_segprompt is a cutover demolition target and this module is KEEP — the live read stays
    # while cb_segprompt exists (identical behaviour today), with the value itself (2.0s) as the
    # guarded fallback so this KEEP module survives the old path's archive. The settle-trim
    # concept is itself beat-era (shots carry no settle window) and retires with the legacy path.
    try:
        import cb_segprompt
        return float(cb_segprompt.HANDLE_SETTLE)
    except Exception:
        return 2.0

# JOIN ON LIVE MOTION (Julian, 2026-07-03, superseding the earlier fixed-fraction trim below): the settle
# exists in the footage for the relay's harvest and for these trim handles — it is trimmed OUT of the visible
# cut ENTIRELY, off every clip but the scene's last (whose settle IS the scene's real landing and stays in
# full).
EDGE_FRAMES = 4     # "3 to 5 frames" — trimmed off EVERY clip's own opening ease-in, and off the closing
                    # deceleration of what remains after the settle is removed (every clip but the last) — cutting
                    # where the motion is alive, not where it's still ramping up or ramping down.
DEFAULT_FPS = 24.0  # fallback only if a clip's own fps can't be read; confirmed 24fps on real rendered clips.

def _clip_fps(clip):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=r_frame_rate", "-of", "default=nk=1:nw=1", clip], capture_output=True, text=True)
    try:
        num, den = r.stdout.strip().split("/")
        return float(num) / float(den)
    except Exception:
        return DEFAULT_FPS

def assemble_conformed(clips, out, settle_trim=None, edge_frames=EDGE_FRAMES):
    """JOIN ON LIVE MOTION (Julian, 2026-07-03) — Gate 4's conform doctrine, superseding the earlier fixed-
    fraction settle trim. Still HARD CUTS (no cross-dissolve — that rule is unchanged); the flow comes from WHERE
    each cut lands. Per clip: the full settle (settle_trim seconds) is removed from the tail of every clip but the
    scene's last, PLUS a small edge_frames trim off the closing deceleration of what's left (every clip but the
    last) and off the opening ease-in (every clip, including the first). Never re-renders — trims/concats
    already-rendered clips only. This is the "conformed cut"; assemble_picture (unchanged) remains the raw
    butt-join for comparison. `settle_trim` defaults to cb_segprompt.HANDLE_SETTLE (see _settle_trim) when not
    given explicitly."""
    if settle_trim is None:
        settle_trim = _settle_trim()
    inputs = []
    for c in clips: inputs += ["-i", c]
    durs = [_dur(c) for c in clips]
    fpss = [_clip_fps(c) for c in clips]
    n = len(clips)
    fc = []
    for i in range(n):
        edge_in = edge_frames / fpss[i]
        edge_out = (edge_frames / fpss[i]) if i < n - 1 else 0.0
        settle_out = settle_trim if i < n - 1 else 0.0
        start = edge_in
        end = max(start + 0.5, durs[i] - settle_out - edge_out)   # floor: never trim a clip to nothing
        fc.append(f"[{i}:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS,setsar=1,format=yuv420p[v{i}]")
        fc.append(f"[{i}:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS,"
                  f"aformat=sample_rates=44100:channel_layouts=stereo[a{i}]")
    joins = "".join(f"[v{i}][a{i}]" for i in range(n))
    fc.append(f"{joins}concat=n={n}:v=1:a=1[cv][ca]")
    fc.append(f"[cv]tpad=stop_mode=clone:stop_duration={HELD}[v]")
    fc.append(f"[ca]apad=pad_dur={HELD}[a]")
    cmd = ["ffmpeg","-y"] + inputs + ["-filter_complex", ";".join(fc),
           "-map","[v]","-map","[a]","-c:v","libx264","-preset","medium","-crf","18","-pix_fmt","yuv420p",
           "-c:a","aac","-b:a","256k","-movflags","+faststart", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode or not os.path.exists(out):
        # FIXED 2026-07-14 (wiring this function into run() for the first time): this used to unconditionally
        # return _dur(out) even on a real ffmpeg failure — the exact "silent success on failure" bug class
        # already found and fixed in this file's own assemble_picture/mix (2026-07-12 audit). Never caught
        # before because nothing called this function outside its own test — now that run() does, a failure
        # here must be distinguishable from success (_dur of a missing file is 0.0, not None).
        print("assemble_conformed ERROR:", r.stderr[-400:])
        return None
    return _dur(out)

def _review_font():
    for p in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
              "/System/Library/Fonts/Supplemental/Verdana.ttf", "/System/Library/Fonts/Menlo.ttc"):
        if os.path.exists(p):
            return p
    return None

def _srt_tc(sec):
    h = int(sec // 3600); m = int((sec % 3600) // 60); s = int(sec % 60); ms = int(round((sec - int(sec)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def _mss(s):
    m = int(s // 60); return f"{m}:{(s - m*60):04.1f}"

def write_review_srt(windows, out):
    """Timed SRT of per-shot labels — BEAT/SHOT/Ref + the shot's scene in–out timecode. Robust timed text (vs 48 drawtexts)."""
    lines = []
    for i, w in enumerate(windows, 1):
        lines += [str(i), f"{_srt_tc(w['scene_in'])} --> {_srt_tc(w['scene_out'])}",
                  f"BEAT {w['beat']}   SHOT {w['shot']}   {w['ref']}   [{_mss(w['scene_in'])}-{_mss(w['scene_out'])}]", ""]
    open(out, "w", encoding="utf-8").write("\n".join(lines))
    return out

def _pil_font(size):
    from PIL import ImageFont
    f = _review_font()
    try:
        return ImageFont.truetype(f, size) if f else ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()

def _active_label(windows, t):
    for w in windows:
        if w["scene_in"] <= t < w["scene_out"]:
            return f"BEAT {w['beat']}    SHOT {w['shot']}    {w['ref']}    [{_mss(w['scene_in'])}-{_mss(w['scene_out'])}]"
    return ""

def _boxed(dr, font, text, x, y, color):
    bb = dr.textbbox((x, y), text, font=font)
    dr.rectangle([bb[0] - 9, bb[1] - 7, bb[2] + 9, bb[3] + 7], fill=(0, 0, 0, 165))
    dr.text((x, y), text, font=font, fill=color)

def burn_review_overlay(scene_video, windows, out, fps=24, W=1280, H=720):
    """RETAKE-REVIEW copy of the stitched scene — running scene timecode + frame (top-left) and the current
    BEAT/SHOT/Ref + in–out (bottom). This ffmpeg has NO text filters, so the overlay is rendered with PIL (one
    transparent PNG per second) and composited via the `overlay` filter. Also writes the .srt sidecar."""
    import tempfile, math, shutil
    from PIL import Image, ImageDraw
    write_review_srt(windows, os.path.splitext(out)[0] + ".srt")
    dur = _dur(scene_video)
    if not dur:
        print("review overlay: scene has no duration"); return None
    tmp = tempfile.mkdtemp(prefix="review_ov_")
    big, small = _pil_font(30), _pil_font(26)
    for sec in range(int(math.ceil(dur))):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(img)
        _boxed(dr, big, f"{_mss(sec)}   f{int(sec * fps)}", 18, 14, (255, 255, 255, 255))
        lab = _active_label(windows, sec + 0.05)
        if lab:
            _boxed(dr, small, lab, 18, H - 54, (255, 230, 0, 255))
        img.save(os.path.join(tmp, f"ov_{sec:04d}.png"))
    # overlay=0:0 (NOT shortest=1) — the main video drives the length; the 1fps label holds its last frame. shortest=1
    # truncated the video ~1s short of the (copied) audio, so it froze at the end. +faststart so browsers stream it.
    cmd = ["ffmpeg", "-y", "-i", scene_video, "-framerate", "1", "-i", os.path.join(tmp, "ov_%04d.png"),
           "-filter_complex", "[0:v][1:v]overlay=0:0[v]", "-map", "[v]", "-map", "0:a?",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy",
           "-movflags", "+faststart", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    shutil.rmtree(tmp, ignore_errors=True)
    if r.returncode:
        print("review overlay ERROR:", r.stderr[-700:]); return None
    return out

# LOUDNESS TARGETS, PER DELIVERY PLATFORM (2026-07-14, Julian's front-to-back wiring pass — "script to post to
# YouTube, to Amazon, Netflix, whatever it is"): the -14 LUFS mix() always mastered to was a single, silently
# hardcoded number with no way to select anything else — not wrong for YouTube (it happens to BE YouTube's own
# published target) but never actually a CHOICE, and every OTHER platform Julian named has a materially
# different real spec. Figures are the commonly-published targets for each platform as of this writing — always
# reconcile against that platform's own current delivery/loudness spec before a final broadcast delivery; these
# are a real, cited default, not a guarantee a spec hasn't moved. "I"/"TP"/"LRA" map directly onto ffmpeg's
# loudnorm filter (integrated loudness, true peak, loudness range); LRA is held at a consistent 11 across every
# target (none of these platforms mandate a specific LRA the way they mandate I/TP — 11 is a reasonable,
# consistent dynamic-range budget for a mixed voice+music+SFX kids' animation cut).
LOUDNESS_TARGETS = {
    "youtube":       {"I": -14, "TP": -1.0, "LRA": 11},   # YouTube's own published loudness recommendation
    "netflix":       {"I": -27, "TP": -2.0, "LRA": 11},   # Netflix Sound Mix Specifications (dialogue-gated LKFS)
    "amazon":        {"I": -24, "TP": -2.0, "LRA": 11},   # Prime Video / ATSC A/85 broadcast-style target
    "broadcast_ebu": {"I": -23, "TP": -1.0, "LRA": 11},   # EBU R128 (UK/EU broadcast delivery)
}
DEFAULT_PLATFORM = "youtube"   # unchanged default — matches this function's own pre-existing -14/-1.5/11 behaviour

def mix(picture, music, ambience, out, platform=DEFAULT_PLATFORM, sfx_layers=None):
    """Lay continuous music + ambience UNDER the picture's native voice (ducked), hold to end, master to
    `platform`'s own loudness target (LOUDNESS_TARGETS, above; defaults to YouTube, unchanged from before this
    was made an explicit choice). An unrecognized platform name falls back to DEFAULT_PLATFORM rather than
    raising — this is a mastering CHOICE, not a hard gate; a typo'd platform name should degrade to a sane
    default, never crash mid-render.

    `sfx_layers` (2026-07-14, THE SFX-SWEETENING MECHANISM, CLAUDE.md rule 82) — an optional list of
    {"file", "at_sec"} dicts, each a short one-shot mixed in ADDITIVELY at its own scene-cumulative timecode
    (see sweeten_cues_for_scene, above, for how these are computed). Each layer is stereo-formatted, delayed
    via adelay to its own at_sec (paired L/R delay values — ffmpeg requires matched per-channel delays for a
    stereo stream), then atrim'd to T so a layer starting late in a long picture can never push the mixed
    audio past the video's own length (amix defaults to the LONGEST input otherwise). Folded into the SAME
    amix call as music/ambience, BEFORE the mastering chain — so a sweetening cue is properly leveled by the
    same loudnorm/limiter pass everything else gets, never a second, un-normalized layer bolted on after.
    NAMED LIMITATION: unlike music, an sfx layer is NOT currently sidechain-ducked against the voice — see
    sweeten_cues_for_scene's own docstring for why, and why this is an acceptable scaffolding-stage trade
    given real assets don't exist yet either. A missing/unreadable sfx file is silently skipped (matching
    have_mus/have_amb's own convention), never an error — this is enrichment, never a required input."""
    tgt = LOUDNESS_TARGETS.get(platform, LOUDNESS_TARGETS[DEFAULT_PLATFORM])
    T = _dur(picture); fo = round(T - 1.0, 2)
    inputs = ["-i", picture]
    have_mus = music and os.path.exists(music)
    have_amb = ambience and os.path.exists(ambience)
    sfx_layers = [l for l in (sfx_layers or []) if l.get("file") and os.path.exists(l["file"])]
    if have_mus: inputs += ["-i", music]
    if have_amb: inputs += ["-i", ambience]
    for layer in sfx_layers: inputs += ["-i", layer["file"]]
    fc = (["[0:a]aformat=sample_rates=44100:channel_layouts=stereo,asplit=2[vmix][vsc]"] if have_mus
          else ["[0:a]aformat=sample_rates=44100:channel_layouts=stereo[vmix]"])
    mix_in = ["[vmix]"]; idx = 1
    if have_mus:
        fc.append(f"[{idx}]atrim=0:{T},afade=t=in:st=0:d=1.2,afade=t=out:st={fo}:d=1.0,volume=0.30[mus]")
        fc.append("[mus][vsc]sidechaincompress=threshold=0.04:ratio=12:attack=5:release=400[musd]")
        mix_in.append("[musd]"); idx += 1
    if have_amb:
        fc.append(f"[{idx}]aloop=loop=-1:size=2000000,atrim=0:{T},volume=0.10,afade=t=out:st={fo}:d=1.0[amb]")
        mix_in.append("[amb]"); idx += 1
    for si, layer in enumerate(sfx_layers):
        delay_ms = max(0, int(round(float(layer.get("at_sec") or 0) * 1000)))
        tag = f"sfx{si}"
        fc.append(f"[{idx}]aformat=sample_rates=44100:channel_layouts=stereo,"
                   f"adelay={delay_ms}|{delay_ms},atrim=0:{T}[{tag}]")
        mix_in.append(f"[{tag}]"); idx += 1
    n = len(mix_in)
    fc.append("".join(mix_in) + f"amix=inputs={n}:normalize=0,highpass=f=35,"
              "equalizer=f=3000:t=q:w=2:g=1.2,highshelf=f=9000:g=1.5,"
              "acompressor=threshold=-16dB:ratio=2:attack=25:release=250:makeup=2,"
              f"loudnorm=I={tgt['I']}:TP={tgt['TP']}:LRA={tgt['LRA']},alimiter=limit=0.89:level=false[aout]")
    cmd = ["ffmpeg","-y"] + inputs + ["-filter_complex", ";".join(fc),
           "-map","0:v:0","-map","[aout]","-c:v","copy","-c:a","aac","-b:a","256k","-movflags","+faststart", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode or not os.path.exists(out):
        # FIXED 2026-07-12 (full-codebase audit continued): this used to unconditionally return `out` even when
        # ffmpeg failed — an even weaker signal than assemble_picture's own pre-fix _dur(out), since it didn't even
        # correlate with success. run() discarded this return value entirely and unconditionally printed a
        # success line right after calling this, then proceeded into the retake-review/CapCut-stems steps against
        # a `complete` file that was never written (the CapCut copy several lines later would raise an uncaught
        # FileNotFoundError, far from the real diagnosis). Return None on failure so the caller can check it.
        print("mix ERROR:", r.stderr[-400:])
        return None
    return out

def build_vertical_derivative(src, out, target_w=1080, target_h=1920):
    """9:16 CENTRE-SAFE VERTICAL DERIVATIVE (2026-07-14, Julian's front-to-back wiring pass) — the second of
    the "two masters delivered" CLAUDE.md rule 28's own Production Line doctrine has always named ("the 16:9
    feature master and a centre-safe 9:16 derivative"), never actually built until now — a real, previously-
    named, never-built deliverable, not just an unwired one.

    A STATIC, centre-anchored crop — never subject-tracking/AI reframing, which "centre-safe" was never asking
    for: crops a vertical strip out of the horizontal centre of the 16:9 frame at full source height
    (`crop=ih*9/16:ih:(iw-ih*9/16)/2:0`), then scales to `target_w`x`target_h` (1080x1920, the standard
    vertical-delivery resolution for YouTube Shorts/Reels/TikTok-style 9:16 platforms). Re-encodes video (a
    crop+scale can't be a stream copy); audio is copied straight through, unchanged — whatever loudness master
    was fed in stays as mastered."""
    if not os.path.exists(src):
        print(f"build_vertical_derivative: source not found: {src}"); return None
    vf = f"crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale={target_w}:{target_h},setsar=1"
    cmd = ["ffmpeg", "-y", "-i", src, "-vf", vf,
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "copy", "-movflags", "+faststart", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode or not os.path.exists(out):
        print("build_vertical_derivative ERROR:", r.stderr[-400:])
        return None
    return out

def build_platform_masters(pkg, scene_num, episode="Ep1", platforms=("youtube", "netflix", "amazon")):
    """THE REAL DELIVERABLE: a separate, correctly-loudness-mastered file per named platform, built from the
    scene's ALREADY-ASSEMBLED picture (never re-runs assemble_conformed/assemble_picture — this is a re-mix/
    re-master pass over an existing, approved picture, same convention as a real audio-post delivery step).
    Requires run() to have already produced media/{episode}_Scene{N}_picture.mp4 for this scene (fire Gate 5
    first). Returns {platform: path_or_None}; a platform that fails to master is None, never silently skipped
    with no trace — every attempt is reported."""
    picture = f"media/{episode}_Scene{scene_num}_picture.mp4"
    if not os.path.exists(picture):
        print(f"build_platform_masters: no picture for {episode} scene {scene_num} yet — fire Gate 5 first "
              f"(run()) to build {picture}."); return {}
    music = f"media/{episode}_S{scene_num}_music.mp3"; amb = f"media/{episode}_S{scene_num}_ambience.mp3"
    # THREADED THROUGH (2026-07-14, SFX sweetening): mix()'s own sfx_layers param must reach EVERY platform's
    # mix() call here, not just run()'s own default-YouTube one — a research pass named this exact risk before
    # it could ship as a real gap (a sweetening cue present only in the YouTube complete.mp4, silently absent
    # from every Netflix/Amazon/broadcast master built by this function, since it calls mix() directly and
    # never routes through run()'s own complete.mp4).
    sfx_layers = sweeten_cues_for_scene(pkg, scene_num, episode)
    results = {}
    for plat in platforms:
        if plat not in LOUDNESS_TARGETS:
            print(f"  {plat}: SKIPPED — not in LOUDNESS_TARGETS ({', '.join(LOUDNESS_TARGETS)})")
            results[plat] = None
            continue
        out = f"media/{episode}_Scene{scene_num}_master_{plat}.mp4"
        tgt = LOUDNESS_TARGETS[plat]
        r = mix(picture, music, amb, out, platform=plat, sfx_layers=sfx_layers)
        results[plat] = r
        if r:
            print(f"  {plat}: I={tgt['I']} TP={tgt['TP']} LRA={tgt['LRA']} -> {r}", flush=True)
        else:
            print(f"  {plat}: FAILED — see the mix ERROR above", flush=True)
    return results

def run(pkg, scene_num, episode="Ep1"):
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    clips = _clips(pkg, episode, scene_num)
    if not clips:
        print(f"GATE 5: no clips for {episode} scene {scene_num} (fire gate 3 first)."); return
    print(f"GATE 5 — Post: {episode} scene {scene_num}, {len(clips)} clips", flush=True)
    picture = f"media/{episode}_Scene{scene_num}_picture.mp4"
    # WIRED IN 2026-07-14 (Julian's front-to-back wiring pass — "we can't just have them as files that sit
    # there that have zero firing"): assemble_conformed (JOIN ON LIVE MOTION, Julian's own 2026-07-03 ruling —
    # "the last frame needs to be the start of the next frame... we need to get it to flow across") was fully
    # built, tested, and documented as Gate 5's own doctrine (CLAUDE.md rule 19/PRODUCTION_DOCTRINE.md's Stage
    # 5) but had ZERO live callers — run() called assemble_picture (the raw butt-join) exclusively, confirmed
    # by rule 46/49's own audits and never closed. This is that close: the CONFORMED cut (settle-trimmed, cuts
    # land mid-motion) is now the real Gate-5 picture. assemble_picture is NOT deleted — it still runs, saved
    # alongside as the named "deliberate comparison baseline" its own docstring always called it (rule 19),
    # so nothing is lost and a raw-vs-conformed A/B is always available on disk, never fed into mix/stems.
    normed = _norm(clips)
    is_conformed = len(clips) >= 2
    if not is_conformed:
        # assemble_conformed's own settle-trim math assumes at least one join to trim; a single-clip scene has
        # no join to conform (and thus nothing for a raw-vs-conformed comparison to compare) — the raw butt-
        # join (a held-tail pass-through for one clip) is already the correct, complete picture.
        conform_ok = assemble_picture(normed, picture) is not None
    else:
        raw_picture = f"media/{episode}_Scene{scene_num}_picture_RAW.mp4"
        if assemble_picture(normed, raw_picture) is None:
            print(f"  (raw butt-join comparison copy failed — non-fatal, continuing with the conformed cut)", flush=True)
        else:
            print(f"  raw butt-join comparison (unconformed, for A/B) -> {raw_picture}", flush=True)
        conform_ok = assemble_conformed(normed, picture) is not None
    if not conform_ok:
        print(f"GATE 5: picture assembly FAILED for {episode} scene {scene_num} — see the ffmpeg error above. "
              f"Stopping (no phantom mix/review/CapCut-stems step on a picture that was never written).", flush=True)
        return
    # FIXED (full-pipeline verification workflow, 2026-07-14): this line used to unconditionally claim
    # "settle-trimmed conform, joins land mid-motion" even for a single-clip scene, where assemble_conformed
    # never ran (there was no join to conform) — a human reading Gate 5's log would be told a conform
    # happened when it didn't. Branches on which path actually ran.
    if is_conformed:
        print(f"  picture (settle-trimmed conform, joins land mid-motion, native voice) -> {picture}", flush=True)
    else:
        print(f"  picture (single clip, no join to conform, native voice) -> {picture}", flush=True)
    music = f"media/{episode}_S{scene_num}_music.mp3"; amb = f"media/{episode}_S{scene_num}_ambience.mp3"
    # MUSIC POLICY (changed 2026-06-24, Julian): SEEDANCE scores the take — its synchronised SFX + TIMED comedy/
    # emotional music are already IN the clip audio (its timing is the point). Post does NOT auto-compose a bed; it
    # POLISHES — assembles seamlessly, keeps the clip's voice+SFX+music, masters, and exports stems. A music bed ON
    # TOP is the LAST, OPTIONAL call: drop your own MUSIC.mp3 (always wins), or set CB_AUTO_MUSIC_BED=1 for a scratch
    # ElevenLabs underscore — otherwise we just deliver stems and you decide in CapCut.
    if AUTO_MUSIC_BED and not os.path.exists(music):
        try:
            import cb_gen, cb_prompts as P
            _d = json.load(open(pkg))
            _beats = [b for b in (_d.get("beats") or _d.get("shots") or []) if str(b.get("sceneNumber")) == str(scene_num)]
            _brief = P.music_brief(_beats, P.scene_cfg(episode, str(scene_num)), episode=episode)
            _len = int(max(10.0, _dur(picture)) * 1000)
            print(f"  (opt-in) generating a scratch music bed ON TOP ({_len // 1000}s) — {_brief[:70]}…", flush=True)
            cb_gen.eleven_music(_brief, length_ms=_len, out=os.path.basename(music))
            print(f"  music bed -> {music}", flush=True)
        except Exception as e:
            print(f"  music bed generation skipped ({str(e)[:140]}) — delivering the clip's own voice+SFX+music", flush=True)
    complete = f"media/{episode}_Scene{scene_num}_complete.mp4"
    # SFX SWEETENING (2026-07-14, CLAUDE.md rule 82) — best-effort, never blocks: candidates are computed
    # from this scene's own rendered beats + resolved archetypes, but only a cue whose actual audio file
    # exists on disk ever reaches mix() (see sweeten_cues_for_scene's own docstring). With no real assets
    # populated yet (shows/crystal-bears/canon/sfx/ is empty), this always reports 0 today — the honest,
    # correct state, not a silent no-op with no trace.
    try:
        sfx_layers = sweeten_cues_for_scene(pkg, scene_num, episode)
    except Exception as e:
        print(f"  SFX sweetening skipped ({str(e)[:140]})", flush=True)
        sfx_layers = []
    lib_size = len(_load_sfx_library())
    if lib_size:
        print(f"  SFX sweetening: {len(sfx_layers)} of {lib_size}-cue library have an asset on disk for this scene", flush=True)
    # FIXED 2026-07-12 (full-codebase audit continued): same gap as assemble_picture above — mix()'s return value
    # was discarded and the success line printed unconditionally, so a mix failure (picture succeeds, mix doesn't)
    # used to complete "=== POST DONE ===" with {episode}_Scene{N}_complete.mp4 — the actual Gate-5 deliverable —
    # never created or updated. Check it and stop before the retake-review/CapCut-stems steps.
    if mix(picture, music, amb, complete, sfx_layers=sfx_layers) is None:
        print(f"GATE 5: mix FAILED for {episode} scene {scene_num} — see the ffmpeg error above. "
              f"Stopping before the retake-review/CapCut-stems steps (no deliverable was produced).", flush=True)
        return
    print(f"  preview mix (music+ambience ducked, mastered -14 LUFS) -> {complete}", flush=True)
    # RETAKE REVIEW COPY — the same scene with the timecode + frame + beat/shot/Ref burned in, plus the matching Excel
    # retake sheet, so the cut can be marked up shot-by-shot for surgical retakes (see cb_address).
    try:
        import cb_address
        _wins = cb_address.scene_shot_windows(pkg, scene_num, episode)
        _review = f"media/{episode}_Scene{scene_num}_REVIEW.mp4"
        if burn_review_overlay(complete, _wins, _review):
            print(f"  retake review copy (timecode + beat/shot burned in) -> {_review}", flush=True)
        _csv, _n = cb_address.write_retake_csv(pkg, scene_num, episode)
        print(f"  retake sheet ({_n} shot rows) -> {_csv}", flush=True)
    except Exception as e:
        print(f"  retake review/sheet skipped ({str(e)[:140]})", flush=True)
    # DIALOGUE CAPTIONS — WIRED IN 2026-07-14 (Julian's front-to-back wiring pass): a delivery-ready video with
    # no captions is not deliverable content for YouTube/Amazon/Netflix, all of which require them. Real
    # dialogue text + real scene-cumulative shot timing (cb_address.scene_captions), never the compiled prompt
    # text (which deliberately never carries spoken words, Law 6). Non-fatal — a captions failure never blocks
    # the real Gate-5 deliverable (complete.mp4) that's already been written above.
    try:
        import cb_address
        _srt, _n_cap = cb_address.write_captions(pkg, scene_num, episode, fmt="srt")
        _vtt, _ = cb_address.write_captions(pkg, scene_num, episode, fmt="vtt")
        print(f"  captions ({_n_cap} line(s)) -> {_srt}, {_vtt}", flush=True)
    except Exception as e:
        print(f"  captions skipped ({str(e)[:140]})", flush=True)
    # THE SECOND MASTER — 9:16 CENTRE-SAFE VERTICAL DERIVATIVE, WIRED IN 2026-07-14 (Julian's front-to-back
    # wiring pass): CLAUDE.md rule 28's own doctrine has always named "two masters delivered" as Gate 5's real
    # output; only the 16:9 feature master (`complete`) ever actually got built. Non-fatal — a failure here
    # never blocks the primary 16:9 deliverable already written above.
    vertical = f"media/{episode}_Scene{scene_num}_vertical_9x16.mp4"
    if build_vertical_derivative(complete, vertical):
        print(f"  vertical derivative (9:16, centre-safe crop) -> {vertical}", flush=True)
    else:
        print(f"  vertical derivative skipped (see the build_vertical_derivative ERROR above, if any)", flush=True)
    # CapCut handoff: the picture (V3 voice + SFX already in it) + the CLEAN per-shot V3 voice stems (for
    # re-balancing / swaps) + the auto-generated scratch music bed + a readme. Julian refines the mix by ear.
    #
    # GATE 5'S NAMED CHAIR (2026-07-14, restoring the named-auteur-per-chair doctrine, CRYSTAL_BEARS_STUDIO_BIBLE.md
    # Law 1): this file is, and should stay, deliberately MECHANICAL — loudness normalization, hard-cut concat, a
    # fixed EQ/compressor/limiter recipe, zero content-awareness. There is no LLM call anywhere in cb_post.py, and
    # none belongs here: Julian himself IS the Gate-5 chair (Michael Giacchino/Gary Rydstrom's job, per the Studio
    # Bible), and he does that work by ear in CapCut, not through a machine's guess at what's funny or moving. What
    # this function CAN do — and, until this pass, wasn't doing — is hand him real, actionable craft guidance for
    # that pass instead of purely administrative file-naming instructions. The README below is that fix.
    #
    # SFX SWEETENING — THE MECHANISM IS NOW BUILT (2026-07-14, CLAUDE.md rule 82, Julian: "go with those two
    # things you flagged"): a small library of the show's own signature one-shots (FWIP/THUP/POLLEN_PUFF/POP —
    # "pollen puff", not the earlier doctrine text's "pollen poof"; every real occurrence in authored beat data
    # says "puff", corrected at the source) layered additively onto a matching beat's own resolved archetype —
    # see sweeten_cues_for_scene/ARCHETYPE_TO_SFX_CUE/_load_sfx_library, above, and mix()'s own sfx_layers param.
    # What's STILL genuinely missing is the AUDIO ITSELF: shows/crystal-bears/canon/sfx/ is empty (see its own
    # README) — this pass built the plumbing and confirmed it degrades gracefully to zero-cue, zero-cost no-ops
    # with no assets present (proven end to end with real ffmpeg, synthetic files, zero API spend), but it can't
    # record or license the four real one-shots. Drop a real file at each named path and the mechanism activates
    # with no further code change.
    import glob
    stems = f"media/stems_{episode}_Scene{scene_num}"; os.makedirs(stems, exist_ok=True)
    shutil.copy(picture, f"{stems}/PICTURE_voice+SFX.mp4")
    voices = sorted(glob.glob(f"media/vo_{episode}_{scene_num}.*.mp3"))
    for v in voices: shutil.copy(v, f"{stems}/VOICE_{os.path.basename(v)[len('vo_'):]}")
    for f, dst in [(music, "MUSIC.mp3"), (amb, "AMBIENCE.mp3")]:
        if os.path.exists(f): shutil.copy(f, f"{stems}/{dst}")
    with open(f"{stems}/CAPCUT_README.txt", "w") as fh:
        fh.write(f"CRYSTAL BEARS — CapCut handoff — {episode} Scene {scene_num}\n\n"
                 "PICTURE.mp4   = the polished, seamlessly-stitched cut, with the acted ElevenLabs V3 voice + Seedance's\n"
                 "                own synchronised SFX and TIMED comedy/emotional music already in it (timing locked to the action).\n"
                 "VOICE_<shot>.mp3 = clean per-shot V3 dialogue stems — to re-balance / duck the voice IN THE MIX.\n"
                 "                (Law 5: the render's voice is final — there is no voice swap.)\n"
                 "MUSIC.mp3 / AMBIENCE.mp3 = only if you supplied one or opted into the scratch bed (CB_AUTO_MUSIC_BED=1).\n\n"
                 "TO FINISH IN CAPCUT: drop PICTURE in (it already plays with score + SFX). If you want a music bed ON TOP,\n"
                 "lay it under the voice and balance by ear — or keep Seedance's own score. Pull a music moment if it's not working.\n"
                 "The picture + voice + SFX + Seedance's timed score are delivered; the bed-on-top is your last, optional call.\n\n"
                 "— THIS PASS IS YOURS: THE COMPOSER + SOUND DESIGNER'S CHAIR —\n"
                 "No machine judges comedy or feeling — that's this pass, by ear, same as it's always been. Two things\n"
                 "worth listening for specifically, in the voice of the people who actually do this at Pixar:\n\n"
                 "SCORE (Michael Giacchino's ear): the theme should serve the FEELING, not decorate the picture — if a\n"
                 "cue is merely 'nice' under a scene that needs to be funny or needs to break your heart, pull it back\n"
                 "or drop it rather than let pleasant music flatten a beat that should land harder. A comedy hit wants a\n"
                 "sting that lands EXACTLY on the visual gag, not near it — nudge the cue a frame or two until the hit\n"
                 "and the picture's own comic beat arrive together. An emotional beat often wants LESS — silence, or a\n"
                 "single sustained note, can carry more than a full cue. If this scene's own sound design named a pitch\n"
                 "for the crystal leitmotif, listen for whether the score is actually built around it or just sitting\n"
                 "near it — the leitmotif should feel inevitable, not incidental.\n\n"
                 "SOUND (Gary Rydstrom's ear): every SFX in the picture should have real, SPECIFIC weight — a crash, a\n"
                 "flap, a pop that sounds like THIS show's own world, not a generic stock hit. If a comedy beat's impact\n"
                 "sound reads thin or library-flat against the timing of the action, that's the first thing to sweeten\n"
                 "or replace before touching the music. Use silence as a tool, not an absence — a clean drop to near-\n"
                 "silence right before a big hit makes the hit land harder than piling more sound on top of it would.\n"
                 "Balance for CLARITY of the story beat, not loudness — the voice always wins over music and SFX when\n"
                 "they compete for the same moment; if you can't hear a line clearly, that's a mix problem here, not a\n"
                 "re-record (Law 5 — the render's voice is final).\n")
    print(f"  CapCut handoff -> {stems}/ (picture + {len(voices)} clean voice stems + readme)", flush=True)
    print("=== POST DONE ===", flush=True)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "masters":
        # masters <package.json> <sceneNumber> [episode=Ep1] [platforms=youtube,netflix,amazon]
        _pkg, _scene = sys.argv[2], sys.argv[3]
        _ep = sys.argv[4] if len(sys.argv) > 4 else "Ep1"
        _plats = tuple(sys.argv[5].split(",")) if len(sys.argv) > 5 else ("youtube", "netflix", "amazon")
        build_platform_masters(_pkg, _scene, _ep, _plats)
    else:
        run(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "Ep1")
