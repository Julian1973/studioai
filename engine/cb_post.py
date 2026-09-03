#!/usr/bin/env python3
"""cb_post.py — GENERALIZED post (replaces the ad-hoc build_scene*_post.py).

POST = CURATION (the quality filter — NOT composition). Production clips carry approved ElevenLabs dialogue
and usable foley/ambience from the animation render. For split Seedance units, music is NOT baked into each
clip because it drifts from render to render. Scene-level score is generated or selected once after the
approved clips are stitched, then ducked under the dialogue across the whole scene. Gate 5 LISTENS and decides
what works — keeps what works, trims or replaces what doesn't. For a scene Post:
  1) ASSEMBLES the picture via assemble_conformed — JOIN ON LIVE MOTION (Julian, 2026-07-03: "the last frame
     needs to be the start of the next frame... we need to get it to flow across") — the settle is trimmed off
     every clip but the last so cuts land mid-motion, not hold-into-hold; still HARD CUTS shot-to-shot (no
     in-scene cross-dissolves — those are reserved for BETWEEN scenes only), still keeps the clip audio (voice
     + SFX/ambience). WIRED IN 2026-07-14 (Julian's front-to-back wiring pass) — this function
     was fully built (2026-07-03) and documented as Gate 5's own doctrine but had zero live callers until now
     (confirmed by rules 46/49's own audits); assemble_picture (the raw butt-join) still runs too, saved
     alongside as `_picture_RAW.mp4`, the named "deliberate comparison baseline" it always was.
  2) MASTERS to broadcast loudness -> a preview "complete" mix, defaulting to YouTube's own target (unchanged
     behaviour). A hand-supplied MUSIC.mp3 always wins; otherwise CB_AUTO_MUSIC_BED=1 can create an ElevenLabs
     scene-level underscore and duck it under the voice. This is the score-continuity route for split units.
     REAL PER-PLATFORM MASTERS (2026-07-14, Julian's front-to-back wiring pass — "script to post to YouTube, to
     Amazon, Netflix"): LOUDNESS_TARGETS names each platform's own published loudness spec; mix()'s previously-
     hardcoded -14 LUFS is now an explicit, chosen default (still YouTube, still -14, nothing regresses), and
     build_platform_masters() delivers a separately-mastered file per platform from the picture already built
     above (`python3 cb_post.py masters <pkg> <scene> [ep] [platforms]`, or `cb_pipeline.py masters <scene>`).
     SFX SWEETENING (2026-07-14, rule 82): before mastering, sweeten_cues_for_scene() layers the show's own
     signature one-shots (FWIP/THUP/POLLEN_PUFF/POP) onto a matching beat's own resolved archetype, additively,
     into the SAME mix() call, threaded through every platform master — see mix()'s own sfx_layers param. Best-
     effort and asset-gated: a cue with no file yet on disk (the project's canon/sfx/ is currently empty)
     is silently skipped, never blocks Gate 5.
  3) Exports a 24-bit combined programme WAV. Generated clips do not carry separable
     dialogue, music and effects sources, so true stems remain an upstream production task.
  4) BUILDS THE SECOND MASTER — a 9:16 centre-safe vertical derivative (build_vertical_derivative, 2026-07-14 —
     CLAUDE.md rule 28's own doctrine has always named "two masters delivered," only the 16:9 one ever actually
     got built) — a static, centre-anchored crop scaled to 1080x1920, alongside real dialogue captions
     (scene_captions/write_captions, .srt + .vtt) — both delivery-required, both non-fatal to the primary master.

The clip audio is never stripped. Post is the quality filter, seamless stitch and delivery
mastering stage; it never pretends a combined mix is a set of isolated stems.

    python3 cb_post.py <package.json> <sceneNumber> [episode=Ep1]
"""
import datetime
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import uuid

import cb_audio_authority
import paths as P  # the project profile is the only path authority (T44)

HELD = 1.6   # held last frame (tension beat)
DELIVERY_FPS = 24.0
DELIVERY_AUDIO_HZ = 48000
DELIVERY_VIDEO_CODEC = "h264"
DELIVERY_PIXEL_FORMAT = "yuv420p"
DELIVERY_COLOR = "bt709"
LOUDNESS_TOLERANCE_LU = 1.0
TRUE_PEAK_TOLERANCE_DB = 0.2
DELIVERY_VIDEO_TAG_ARGS = [
    "-color_primaries", DELIVERY_COLOR,
    "-color_trc", DELIVERY_COLOR,
    "-colorspace", DELIVERY_COLOR,
]
DELIVERY_X264_COLOR_ARGS = DELIVERY_VIDEO_TAG_ARGS + [
    "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",
]
# FIXED 2026-07-12 (full-codebase audit continued): removed the unused `XF = 0.4` cross-dissolve-duration constant
# — grepped clean across the whole repo, zero references anywhere outside its own definition. It was reserved for
# a between-scenes cross-dissolve transition (per assemble_picture's/assemble_conformed's own docstrings), but no
# such episode-level assembly function exists anywhere yet; re-add it the day that feature is actually built.
AUTO_MUSIC_BED = os.environ.get("CB_AUTO_MUSIC_BED", "") == "1"   # OFF by default; enable for an ElevenLabs
                                                                 # scene-level post cue after stitch.

# ── SFX SWEETENING (2026-07-14, CLAUDE.md rule 82 — Julian: "go with those two things you flagged") ──────────
# THE MECHANISM, NOT THE ASSETS: this closes the gap CAPCUT_README.txt itself once named as "confirmed, not
# attempted here... needs real recorded/licensed audio assets this code-only pass has no way to source." That
# is still true — no audio files exist yet (the project's canon/sfx/ is empty, see its own README) — but
# the SOFTWARE that will layer a real one-shot onto a weak comedy hit the moment a file is dropped in can be,
# and now is, built and tested against zero-asset degradation. Scoped to EXACTLY the four signature one-shots
# this show's own doctrine already names (CRYSTAL_BEARS_STUDIO_BIBLE.md, CLAUDE.md rule 57) — never expanded
# to every archetype's own plausible sound on my own initiative; a research pass found several other archetypes
# with a nameable sound (WHOOMP, THUMP, RUMBLE, SPLASH...) but adding those would be inventing new doctrine, not
# building what's already named — left for Julian's own call, not decided here.
SFX_LIBRARY_PATH = P.SFX_LIBRARY                    # T44: from the project profile
# ARCHETYPE -> CUE, grounded directly in each archetype's own physics_rule/visual_payoff_rule text (cb_seedance.
# PHYSICAL_ARCHETYPES) — never a guess. POLLEN_SMEAR_TUMBLE maps to POP, not THUP, because that archetype's own
# visual_payoff_rule is explicit: "The pop-up line is the finisher; the THUPs are mid-flight bounces, not the
# end" — matching this function's own last-shot placement heuristic below. Archetypes with no comedy one-shot
# implied (dramatic/serious beats, pure-stillness beats) are deliberately absent, not force-mapped.
def _load_sfx_library():
    """Graceful-degrade load (matching mix()'s own have_mus/have_amb convention, never gag_locks.json's hard-
    fail-on-missing-key convention — an asset-availability question, not a content-correctness one). Missing
    manifest or malformed JSON both degrade to an empty library, never raise."""
    try:
        d = json.load(open(SFX_LIBRARY_PATH, encoding="utf-8"))
        return {k: v for k, v in d.items() if not k.startswith("_")}
    except Exception:
        return {}

def _dur(p):
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=nk=1:nw=1",p],
                       capture_output=True, text=True)
    try: return float(r.stdout.strip())
    except: return 0.0

def _clips(pkg, episode, scene_num):
    d = json.load(open(pkg, encoding="utf-8")); out = []
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
    r = subprocess.run([
        "ffmpeg", "-y", "-i", clip, "-f", "lavfi", "-i",
        f"anullsrc=channel_layout=stereo:sample_rate={DELIVERY_AUDIO_HZ}",
        "-shortest", "-c:v", "copy", "-c:a", "aac", "-ar",
        str(DELIVERY_AUDIO_HZ), "-ac", "2", "-b:a", "128k", tmp,
    ], capture_output=True)
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
        fc.append(
            f"[0:v]fps={DELIVERY_FPS:g},setsar=1,format={DELIVERY_PIXEL_FORMAT},"
            f"tpad=stop_mode=clone:stop_duration={HELD}[v]")
        fc.append(
            f"[0:a]aformat=sample_rates={DELIVERY_AUDIO_HZ}:channel_layouts=stereo,"
            f"apad=pad_dur={HELD}[a]")
    else:
        # HARD CUTS within a scene — instant, shot-to-shot. NO cross-dissolves between beats; a cross-dissolve is
        # reserved ONLY for a passage-of-time transition BETWEEN scenes (a separate, episode-level assembly). We just
        # concatenate the clips end-to-end (concat filter), then hold the final frame briefly for the scene's end.
        for i in range(len(clips)):
            fc.append(
                f"[{i}:v]fps={DELIVERY_FPS:g},setsar=1,"
                f"format={DELIVERY_PIXEL_FORMAT}[v{i}]")
            fc.append(
                f"[{i}:a]aformat=sample_rates={DELIVERY_AUDIO_HZ}:"
                f"channel_layouts=stereo[a{i}]")
        joins = "".join(f"[v{i}][a{i}]" for i in range(len(clips)))
        fc.append(f"{joins}concat=n={len(clips)}:v=1:a=1[cv][ca]")
        fc.append(f"[cv]tpad=stop_mode=clone:stop_duration={HELD}[v]")
        fc.append(f"[ca]apad=pad_dur={HELD}[a]")
    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r",
        f"{DELIVERY_FPS:g}", "-pix_fmt", DELIVERY_PIXEL_FORMAT,
    ] + DELIVERY_X264_COLOR_ARGS + [
        "-c:a", "aac", "-ar", str(DELIVERY_AUDIO_HZ), "-ac", "2",
        "-b:a", "256k", "-movflags", "+faststart", out,
    ]   # +faststart: moov up front so browsers stream it (no stall)
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
DEFAULT_FPS = DELIVERY_FPS  # fallback only if a clip's own fps can't be read.
POST_SCHEMA_VERSION = 2
POST_POLICY_VERSION = "scene-post-v3-director-cut"

def _clip_fps(clip):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=r_frame_rate", "-of", "default=nk=1:nw=1", clip], capture_output=True, text=True)
    try:
        num, den = r.stdout.strip().split("/")
        return float(num) / float(den)
    except Exception:
        return DEFAULT_FPS


def conform_plan(clips, protected_windows=None, settle_trim=None, edge_frames=EDGE_FRAMES,
                 edit_decisions=None):
    """Calculate the one authoritative trim and scene-time map used by picture and captions.
    Dialogue windows are protected from the generic edge/settle trim; a clip shorter than an
    approved line refuses instead of clipping words off the final film."""
    if settle_trim is None:
        settle_trim = _settle_trim()
    protected_windows = protected_windows or [[] for _ in clips]
    if len(protected_windows) != len(clips):
        raise ValueError("protected dialogue windows must align one-for-one with clips")
    if edit_decisions is not None and len(edit_decisions) != len(clips):
        raise ValueError("edit decisions must align one-for-one with clips")
    durs = [_dur(clip) for clip in clips]
    fpss = [_clip_fps(clip) for clip in clips]
    if any(duration <= 0 for duration in durs):
        raise ValueError("every approved clip must have a positive readable duration")
    out, cursor = [], 0.0
    for index, (clip, duration, fps, windows) in enumerate(
            zip(clips, durs, fpss, protected_windows)):
        edge = edge_frames / fps
        decision = (edit_decisions or [{} for _ in clips])[index] or {}
        if decision.get("manualTrim"):
            try:
                start = float(decision["inSec"])
                end = float(decision["outSec"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"malformed edit decision for {clip}") from exc
            if start < 0 or end <= start or end > duration + 0.01:
                raise ValueError(f"edit decision falls outside {clip}'s {duration:.3f}s duration")
        else:
            start = edge
            end = duration if index == len(clips) - 1 else max(
                start + 0.5, duration - settle_trim - edge)
        if windows:
            starts, ends = [], []
            for window in windows:
                try:
                    line_start = float(window["startSec"])
                    line_end = float(window["endSec"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError(f"malformed dialogue window in {clip}") from exc
                if line_start < 0 or line_start >= line_end or line_end > duration:
                    raise ValueError(
                        f"dialogue window {line_start}-{line_end}s falls outside {clip}'s "
                        f"{duration:.3f}s duration")
                starts.append(line_start); ends.append(line_end)
            start = min(start, min(starts))
            end = max(end, max(ends))
        segment_duration = end - start
        if segment_duration <= 0:
            raise ValueError(f"conform would remove the whole clip: {clip}")
        out.append({"clip": str(clip), "sourceStartSec": round(start, 6),
                    "sourceEndSec": round(end, 6),
                    "sceneStartSec": round(cursor, 6),
                    "sceneEndSec": round(cursor + segment_duration, 6),
                    "fps": fps})
        cursor += segment_duration
    return out

def assemble_conformed(clips, out, settle_trim=None, edge_frames=EDGE_FRAMES, plan=None):
    """JOIN ON LIVE MOTION (Julian, 2026-07-03) — Gate 4's conform doctrine, superseding the earlier fixed-
    fraction settle trim. Still HARD CUTS (no cross-dissolve — that rule is unchanged); the flow comes from WHERE
    each cut lands. Per clip: the full settle (settle_trim seconds) is removed from the tail of every clip but the
    scene's last, PLUS a small edge_frames trim off the closing deceleration of what's left (every clip but the
    last) and off the opening ease-in (every clip, including the first). Never re-renders — trims/concats
    already-rendered clips only. This is the "conformed cut"; assemble_picture (unchanged) remains the raw
    butt-join for comparison. `settle_trim` defaults to cb_segprompt.HANDLE_SETTLE (see _settle_trim) when not
    given explicitly."""
    if plan is None:
        plan = conform_plan(clips, settle_trim=settle_trim, edge_frames=edge_frames)
    if len(plan) != len(clips):
        raise ValueError("conform plan must align one-for-one with clips")
    inputs = []
    for c in clips: inputs += ["-i", c]
    n = len(clips)
    fc = []
    for i in range(n):
        start = float(plan[i]["sourceStartSec"])
        end = float(plan[i]["sourceEndSec"])
        fc.append(
            f"[{i}:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS,"
            f"fps={DELIVERY_FPS:g},setsar=1,format={DELIVERY_PIXEL_FORMAT}[v{i}]")
        fc.append(f"[{i}:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS,"
                  f"aformat=sample_rates={DELIVERY_AUDIO_HZ}:channel_layouts=stereo[a{i}]")
    joins = "".join(f"[v{i}][a{i}]" for i in range(n))
    fc.append(f"{joins}concat=n={n}:v=1:a=1[cv][ca]")
    fc.append(f"[cv]tpad=stop_mode=clone:stop_duration={HELD}[v]")
    fc.append(f"[ca]apad=pad_dur={HELD}[a]")
    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r",
        f"{DELIVERY_FPS:g}", "-pix_fmt", DELIVERY_PIXEL_FORMAT,
    ] + DELIVERY_X264_COLOR_ARGS + [
        "-c:a", "aac", "-ar", str(DELIVERY_AUDIO_HZ), "-ac", "2",
        "-b:a", "256k", "-movflags", "+faststart", out,
    ]
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
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", f"{DELIVERY_FPS:g}",
           "-pix_fmt", DELIVERY_PIXEL_FORMAT] + DELIVERY_X264_COLOR_ARGS + [
           "-c:a", "copy", "-movflags", "+faststart", out]
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
    fc = ([f"[0:a]aformat=sample_rates={DELIVERY_AUDIO_HZ}:channel_layouts=stereo,"
           "asplit=2[vmix][vsc]"] if have_mus
          else [f"[0:a]aformat=sample_rates={DELIVERY_AUDIO_HZ}:"
                "channel_layouts=stereo[vmix]"])
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
        fc.append(f"[{idx}]aformat=sample_rates={DELIVERY_AUDIO_HZ}:channel_layouts=stereo,"
                   f"adelay={delay_ms}|{delay_ms},atrim=0:{T}[{tag}]")
        mix_in.append(f"[{tag}]"); idx += 1
    n = len(mix_in)
    fc.append("".join(mix_in) + f"amix=inputs={n}:normalize=0,highpass=f=35,"
              "equalizer=f=3000:t=q:w=2:g=1.2,highshelf=f=9000:g=1.5,"
              "acompressor=threshold=-16dB:ratio=2:attack=25:release=250:makeup=2[apre]")
    measure_fc = list(fc) + [
        f"[apre]loudnorm=I={tgt['I']}:TP={tgt['TP']}:LRA={tgt['LRA']}:"
        "print_format=json[measure]"
    ]
    measure = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats"] + inputs + [
            "-filter_complex", ";".join(measure_fc), "-map", "[measure]",
            "-f", "null", "-",
        ], capture_output=True, text=True)
    stats = _parse_loudnorm_stats(measure.stderr) if not measure.returncode else None
    if not stats or any(stats.get(key) is None for key in (
            "integratedLufs", "truePeakDbtp", "loudnessRangeLu", "thresholdLufs",
            "targetOffsetLu")):
        print("mix ERROR: loudness analysis failed:", (measure.stderr or "")[-400:])
        return None
    normalize = (
        f"[apre]loudnorm=I={tgt['I']}:TP={tgt['TP']}:LRA={tgt['LRA']}:"
        f"measured_I={stats['integratedLufs']}:measured_TP={stats['truePeakDbtp']}:"
        f"measured_LRA={stats['loudnessRangeLu']}:measured_thresh={stats['thresholdLufs']}:"
        f"offset={stats['targetOffsetLu']}:linear=true,"
        "alimiter=limit=0.89:level=false[aout]"
    )
    fc.append(normalize)
    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", ";".join(fc), "-map", "0:v:0", "-map", "[aout]",
        "-c:v", "copy",
    ] + DELIVERY_VIDEO_TAG_ARGS + [
        "-c:a", "aac", "-ar", str(DELIVERY_AUDIO_HZ), "-ac", "2",
        "-b:a", "256k", "-movflags", "+faststart", out,
    ]
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
    vf = (f"crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale={target_w}:{target_h},"
          f"fps={DELIVERY_FPS:g},setsar=1")
    cmd = ["ffmpeg", "-y", "-i", src, "-vf", vf,
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r",
           f"{DELIVERY_FPS:g}", "-pix_fmt", DELIVERY_PIXEL_FORMAT] + DELIVERY_X264_COLOR_ARGS + [
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
    # SFX sweetening was removed at the 2026-07-16 destructive cutover (it resolved cues via
    # the deleted beat-archetype system); a shot-pipeline sweetening pass is a future build.
    sfx_layers = []
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


def _vtt_tc(sec):
    return _srt_tc(sec).replace(",", ".")


def write_delivery_captions(shots, plan, srt_path, vtt_path):
    """Write exact locked dialogue against the conformed scene timeline."""
    if len(shots) != len(plan):
        raise ValueError("caption shots and conform plan must align")
    windows = []
    for shot, segment in zip(shots, plan):
        source_start = float(segment["sourceStartSec"])
        source_end = float(segment["sourceEndSec"])
        scene_start = float(segment["sceneStartSec"])
        for line in shot.get("dialogueLines") or []:
            start, end = float(line["startSec"]), float(line["endSec"])
            if start < source_start or end > source_end:
                raise ValueError(
                    f"conform trims approved dialogue {line.get('dialogueOccurrenceId')} "
                    f"in {shot.get('shotId')}")
            windows.append({
                "dialogueOccurrenceId": line.get("dialogueOccurrenceId"),
                "sourceEventId": line.get("sourceEventId"),
                "shotId": shot.get("shotId"), "speaker": line["speaker"],
                "exactText": line["exactText"],
                "startSec": round(scene_start + start - source_start, 3),
                "endSec": round(scene_start + end - source_start, 3),
            })
    srt_lines, vtt_lines = [], ["WEBVTT", ""]
    for index, window in enumerate(windows, start=1):
        srt_lines.extend([
            str(index),
            f"{_srt_tc(window['startSec'])} --> {_srt_tc(window['endSec'])}",
            window["exactText"], "",
        ])
        vtt_lines.extend([
            f"{_vtt_tc(window['startSec'])} --> {_vtt_tc(window['endSec'])}",
            window["exactText"], "",
        ])
    pathlib.Path(srt_path).write_text("\n".join(srt_lines), encoding="utf-8")
    pathlib.Path(vtt_path).write_text("\n".join(vtt_lines), encoding="utf-8")
    return windows


def extract_program_audio(master, out):
    """Export the mastered combined programme audio honestly; generated clips do not carry
    separable dialogue/music/SFX stems, so this is never labelled as isolated stems."""
    cmd = ["ffmpeg", "-y", "-i", str(master), "-map", "0:a:0", "-vn",
           "-c:a", "pcm_s24le", "-ar", str(DELIVERY_AUDIO_HZ), "-ac", "2", str(out)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode or not os.path.exists(out):
        print("extract_program_audio ERROR:", result.stderr[-400:])
        return None
    return str(out)


def _probe_media(path):
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format",
        "-of", "json", str(path)], capture_output=True, text=True)
    if result.returncode:
        return None
    try:
        data = json.loads(result.stdout)
    except (TypeError, ValueError):
        return None
    streams = data.get("streams") or []
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})
    duration = ((data.get("format") or {}).get("duration") or video.get("duration") or
                audio.get("duration"))
    try:
        duration = float(duration)
    except (TypeError, ValueError):
        duration = 0.0

    def rate(value):
        try:
            if "/" in str(value):
                numerator, denominator = str(value).split("/", 1)
                return float(numerator) / float(denominator)
            return float(value)
        except (TypeError, ValueError, ZeroDivisionError):
            return 0.0

    try:
        sample_rate = int(audio.get("sample_rate") or 0)
    except (TypeError, ValueError):
        sample_rate = 0
    return {
        "durationSec": duration,
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "hasVideo": bool(video),
        "hasAudio": bool(audio),
        "videoCodec": video.get("codec_name"),
        "pixelFormat": video.get("pix_fmt"),
        "fps": rate(video.get("avg_frame_rate") or video.get("r_frame_rate")),
        "colorPrimaries": video.get("color_primaries"),
        "colorTransfer": video.get("color_transfer"),
        "colorSpace": video.get("color_space"),
        "audioCodec": audio.get("codec_name"),
        "audioSampleRate": sample_rate,
        "audioChannels": int(audio.get("channels") or 0),
        "audioChannelLayout": audio.get("channel_layout"),
        "audioSampleFormat": audio.get("sample_fmt"),
        "audioBitsPerRawSample": int(audio.get("bits_per_raw_sample") or 0),
    }


def _parse_loudnorm_stats(stderr):
    decoder = json.JSONDecoder()
    measured = None
    for position, character in enumerate(stderr or ""):
        if character != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(stderr[position:])
        except ValueError:
            continue
        if isinstance(candidate, dict) and "input_i" in candidate:
            measured = candidate
    if measured is None:
        return None

    def numeric(key):
        try:
            value = float(measured[key])
            return value if value not in (float("inf"), float("-inf")) else None
        except (KeyError, TypeError, ValueError):
            return None

    return {
        "integratedLufs": numeric("input_i"),
        "truePeakDbtp": numeric("input_tp"),
        "loudnessRangeLu": numeric("input_lra"),
        "thresholdLufs": numeric("input_thresh"),
        "targetOffsetLu": numeric("target_offset"),
    }


def _measure_loudness(path, target):
    """Measure the finished programme; mastering intent alone is not delivery evidence."""
    filter_spec = (
        f"loudnorm=I={target['I']}:TP={target['TP']}:LRA={target['LRA']}:"
        "print_format=json")
    result = subprocess.run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
        "-map", "0:a:0", "-af", filter_spec, "-f", "null", "-",
    ], capture_output=True, text=True)
    if result.returncode:
        return None
    return _parse_loudnorm_stats(result.stderr)


def _video_delivery_checks(probe, width, height):
    probe = probe or {}
    return {
        "dimensions": probe.get("width") == width and probe.get("height") == height,
        "videoCodecH264": probe.get("videoCodec") == DELIVERY_VIDEO_CODEC,
        "pixelFormatYuv420p": probe.get("pixelFormat") == DELIVERY_PIXEL_FORMAT,
        "frameRate24": abs(float(probe.get("fps") or 0) - DELIVERY_FPS) <= 0.02,
        "colorPrimariesBt709": probe.get("colorPrimaries") == DELIVERY_COLOR,
        "colorTransferBt709": probe.get("colorTransfer") == DELIVERY_COLOR,
        "colorSpaceBt709": probe.get("colorSpace") == DELIVERY_COLOR,
        "audioCodecAac": probe.get("audioCodec") == "aac",
        "audioSampleRate48k": probe.get("audioSampleRate") == DELIVERY_AUDIO_HZ,
        "audioStereo": probe.get("audioChannels") == 2,
    }


def _sha256(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def _asset_record(actual_path, final_path, probe=False):
    actual = pathlib.Path(actual_path)
    record = {"path": str(final_path), "sha256": _sha256(actual),
              "bytes": actual.stat().st_size}
    if probe:
        record["media"] = _probe_media(actual)
    return record


def replace_guide_dialogue(video, approved_voice, out):
    """Replace a provider guide soundtrack with the approved HEAR master.

    Provider audio is audit evidence, not a safe production bed: a video model can embed
    synthesized speech in the same stream as its SFX and music. Mixing any percentage of
    that stream beneath @Audio1 can therefore create duplicate dialogue. Dialogue review
    media uses the approved master exclusively; non-dialogue stems must be added through a
    separately verified post lane.
    """
    duration = _dur(video)
    if duration <= 0 or not approved_voice or not os.path.exists(approved_voice):
        return None
    cmd = [
        "ffmpeg", "-y", "-i", str(video), "-i", str(approved_voice),
        "-filter_complex",
        (f"[1:a]aformat=sample_rates={DELIVERY_AUDIO_HZ}:channel_layouts=stereo,"
         f"apad,atrim=0:{duration:.6f}[dialogue]"),
        "-map", "0:v:0", "-map", "[dialogue]", "-c:v", "copy",
        "-c:a", "aac", "-ar", str(DELIVERY_AUDIO_HZ), "-ac", "2",
        "-b:a", "256k", "-movflags", "+faststart", str(out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode or not os.path.exists(out):
        return None
    return str(out)


def build_scene_post(shots, out_root, episode, scene_num, input_signature,
                     platform=DEFAULT_PLATFORM, candidate_id=None, music=None,
                     ambience=None, edit_decisions=None, settle_trim=None, edge_frames=None,
                     preserve_provider_mix=True):
    """Build one immutable post candidate transactionally.

    Nothing is exposed at its final path until conform, mix, vertical derivative, captions,
    programme audio, hashes and deterministic media QC all succeed. The returned manifest
    is the exact artefact later reviewed at the human final-master gate.
    """
    if not shots:
        raise ValueError("post requires at least one approved shot")
    if platform not in LOUDNESS_TARGETS:
        raise ValueError(f"unknown mastering platform {platform!r}")
    candidate_id = candidate_id or uuid.uuid4().hex[:12]
    root = pathlib.Path(out_root)
    root.mkdir(parents=True, exist_ok=True)
    final_dir = root / f"{episode}_Scene{scene_num}_{candidate_id}"
    if final_dir.exists():
        raise ValueError(f"post candidate already exists: {final_dir}")
    temp_dir = root / f".tmp_{episode}_Scene{scene_num}_{candidate_id}_{uuid.uuid4().hex[:8]}"
    temp_dir.mkdir()
    try:
        clips = [str(shot["approvedTake"]) for shot in shots]
        if any(not os.path.exists(clip) for clip in clips):
            missing = [clip for clip in clips if not os.path.exists(clip)]
            raise ValueError(f"approved post source is missing: {missing[0]}")
        post_sources = []
        audio_provenance = []
        for index, (shot, clip) in enumerate(zip(shots, clips), start=1):
            if cb_audio_authority.spoken_dialogue_lines(shot) and not preserve_provider_mix:
                # The retired "guide track" lane: replace the provider soundtrack with the HEAR
                # master over silence. Kept behind preserve_provider_mix=False for a future ruling.
                voice = shot.get("approvedVoice")
                if not voice or not os.path.exists(voice):
                    raise ValueError(
                        f"dialogue shot {shot.get('shotId')} has no approved voice master")
                restored = temp_dir / f"shot_{index:02d}_approved_dialogue.mp4"
                if not replace_guide_dialogue(clip, voice, restored):
                    raise RuntimeError(
                        f"approved dialogue restoration failed for {shot.get('shotId')}")
                post_sources.append(str(restored))
                audio_provenance.append({
                    "shotId": shot.get("shotId"),
                    "providerGuidePath": clip,
                    "providerGuideSha256": _sha256(clip),
                    "approvedVoicePath": voice,
                    "approvedVoiceSha256": _sha256(voice),
                    "postSourcePath": str(restored),
                    "postSourceSha256": _sha256(restored),
                    "guideDialogueRemoved": True,
                    "approvedDialogueRestored": True,
                })
            elif cb_audio_authority.spoken_dialogue_lines(shot):
                # THE PROVIDER MIX IS THE DELIVERABLE (2026-09-03): the take the human accepted
                # at WATCH carries the ElevenLabs performance lip-synced by Seedance plus the
                # music and sound design the MUSIC LAW asked the render for. Post keeps it
                # unchanged - no post voice swap (Law 5), no discarded score.
                voice = shot.get("approvedVoice")
                post_sources.append(clip)
                audio_provenance.append({
                    "shotId": shot.get("shotId"),
                    "providerFinalMixPath": clip,
                    "providerFinalMixSha256": _sha256(clip),
                    "approvedVoicePath": voice,
                    "approvedVoiceSha256": _sha256(voice) if voice and os.path.exists(voice) else None,
                    "postSourcePath": clip,
                    "postSourceSha256": _sha256(clip),
                    "guideDialogueRemoved": False,
                    "providerFinalMixPreserved": True,
                })
            else:
                post_sources.append(clip)
        normalized = _norm(post_sources)
        protected = [shot.get("dialogueLines") or [] for shot in shots]
        if edit_decisions is None:
            edit_decisions = [{
                "inSec": shot.get("editInSec", 0),
                "outSec": shot.get("editOutSec"),
                "manualTrim": bool(shot.get("manualTrim")),
            } for shot in shots]
        # A project with a fixed shot length (T71: the writer's shot IS the unit, ending on the
        # writer's Final Frame) passes settle_trim=0 / edge_frames=0: the beat-era settle trim
        # was silently cutting ~2 s off every accepted 30-second take (2026-09-03 audit).
        plan = conform_plan(
            normalized, protected_windows=protected, edit_decisions=edit_decisions,
            settle_trim=settle_trim,
            edge_frames=(EDGE_FRAMES if edge_frames is None else edge_frames))

        names = {
            "conformedPicture": "picture_conformed.mp4",
            "master16x9": f"master_16x9_{platform}.mp4",
            "master9x16": f"master_9x16_{platform}.mp4",
            "captionsSrt": "captions.srt",
            "captionsVtt": "captions.vtt",
            "programAudio": "program_audio_24bit.wav",
            "manifest": "post_manifest.json",
        }
        temp = {key: temp_dir / name for key, name in names.items()}
        final = {key: final_dir / name for key, name in names.items()}
        if not assemble_conformed(normalized, str(temp["conformedPicture"]), plan=plan):
            raise RuntimeError("conformed picture assembly failed")
        if not mix(str(temp["conformedPicture"]), music, ambience,
                   str(temp["master16x9"]), platform=platform):
            raise RuntimeError("programme mix/master failed")
        if not build_vertical_derivative(
                str(temp["master16x9"]), str(temp["master9x16"])):
            raise RuntimeError("9:16 derivative failed")
        caption_windows = write_delivery_captions(
            shots, plan, temp["captionsSrt"], temp["captionsVtt"])
        if not extract_program_audio(temp["master16x9"], temp["programAudio"]):
            raise RuntimeError("programme-audio export failed")

        picture_probe = _probe_media(temp["conformedPicture"])
        master_probe = _probe_media(temp["master16x9"])
        vertical_probe = _probe_media(temp["master9x16"])
        program_audio_probe = _probe_media(temp["programAudio"])
        loudness = _measure_loudness(temp["master16x9"], LOUDNESS_TARGETS[platform])
        expected_occurrences = [
            line.get("dialogueOccurrenceId") for shot in shots
            for line in (shot.get("dialogueLines") or [])]
        caption_occurrences = [window.get("dialogueOccurrenceId") for window in caption_windows]
        checks = {
            "conformedPictureReadable": bool(
                picture_probe and picture_probe["hasVideo"] and picture_probe["hasAudio"] and
                picture_probe["durationSec"] > 0),
            "master16x9Readable": bool(
                master_probe and master_probe["hasVideo"] and master_probe["hasAudio"] and
                master_probe["durationSec"] > 0 and master_probe["height"] and
                abs(master_probe["width"] / master_probe["height"] - 16 / 9) < 0.03),
            "master9x16Readable": bool(
                vertical_probe and vertical_probe["hasVideo"] and vertical_probe["hasAudio"] and
                vertical_probe["width"] == 1080 and vertical_probe["height"] == 1920),
            "masterDurationMatchesPicture": bool(
                picture_probe and master_probe and
                abs(picture_probe["durationSec"] - master_probe["durationSec"]) <= 0.25),
            "dialogueOccurrenceCoverage": caption_occurrences == expected_occurrences,
            "approvedDialoguePostLane": all(
                ((item.get("guideDialogueRemoved") and item.get("approvedDialogueRestored"))
                 or item.get("providerFinalMixPreserved"))
                for item in audio_provenance),
            "programAudioPresent": temp["programAudio"].exists() and
                temp["programAudio"].stat().st_size > 0,
            "programAudioPcm24": bool(
                program_audio_probe and program_audio_probe["audioCodec"] == "pcm_s24le" and
                program_audio_probe["audioBitsPerRawSample"] == 24),
            "programAudioSampleRate48k": bool(
                program_audio_probe and
                program_audio_probe["audioSampleRate"] == DELIVERY_AUDIO_HZ),
            "programAudioStereo": bool(
                program_audio_probe and program_audio_probe["audioChannels"] == 2),
            "loudnessMeasured": bool(
                loudness and loudness["integratedLufs"] is not None and
                loudness["truePeakDbtp"] is not None),
            "integratedLoudnessOnTarget": bool(
                loudness and loudness["integratedLufs"] is not None and
                abs(loudness["integratedLufs"] - LOUDNESS_TARGETS[platform]["I"])
                <= LOUDNESS_TOLERANCE_LU),
            "truePeakWithinLimit": bool(
                loudness and loudness["truePeakDbtp"] is not None and
                loudness["truePeakDbtp"] <=
                LOUDNESS_TARGETS[platform]["TP"] + TRUE_PEAK_TOLERANCE_DB),
        }
        picture_tech = _video_delivery_checks(
            picture_probe, picture_probe.get("width", 0) if picture_probe else 0,
            picture_probe.get("height", 0) if picture_probe else 0)
        master_tech = _video_delivery_checks(
            master_probe, picture_probe.get("width", 0) if picture_probe else 0,
            picture_probe.get("height", 0) if picture_probe else 0)
        vertical_tech = _video_delivery_checks(vertical_probe, 1080, 1920)
        for prefix, technical in (
                ("picture", picture_tech), ("master16x9", master_tech),
                ("master9x16", vertical_tech)):
            checks.update({
                f"{prefix}{name[0].upper()}{name[1:]}": bool(passed)
                for name, passed in technical.items()
            })
        if not all(checks.values()):
            failed = [name for name, passed in checks.items() if not passed]
            raise RuntimeError(f"post QC failed: {failed}")

        outputs = {
            "conformedPicture": _asset_record(
                temp["conformedPicture"], final["conformedPicture"], probe=True),
            "master16x9": _asset_record(temp["master16x9"], final["master16x9"], probe=True),
            "master9x16": _asset_record(temp["master9x16"], final["master9x16"], probe=True),
            "captionsSrt": _asset_record(temp["captionsSrt"], final["captionsSrt"]),
            "captionsVtt": _asset_record(temp["captionsVtt"], final["captionsVtt"]),
            "programAudio": _asset_record(
                temp["programAudio"], final["programAudio"], probe=True),
        }
        manifest = {
            "schemaVersion": POST_SCHEMA_VERSION,
            "policyVersion": POST_POLICY_VERSION,
            "candidateId": candidate_id, "episode": episode, "sceneNumber": str(scene_num),
            "builtAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "masteringPlatform": platform,
            "loudnessTarget": LOUDNESS_TARGETS[platform],
            "measuredLoudness": loudness,
            "deliveryProfile": {
                "videoCodec": "H.264", "pixelFormat": DELIVERY_PIXEL_FORMAT,
                "frameRate": DELIVERY_FPS, "color": "Rec.709",
                "programAudioCodec": "AAC", "programAudioSampleRateHz": DELIVERY_AUDIO_HZ,
                "programAudioChannels": 2,
                "archiveAudioCodec": "PCM 24-bit", "archiveAudioSampleRateHz": DELIVERY_AUDIO_HZ,
                "master16x9": {"aspectRatio": "16:9"},
                "master9x16": {"width": 1080, "height": 1920},
            },
            "manifestPath": str(final["manifest"]),
            "inputSignature": input_signature,
            "orderedShots": [{"shotId": shot["shotId"],
                               "approvedTake": str(shot["approvedTake"]),
                               "approvedTakeHash": _sha256(shot["approvedTake"]),
                               "editDecision": edit_decisions[index]}
                              for index, shot in enumerate(shots)],
            "audioProvenance": [
                {**item, "postSourcePath": str(
                    final_dir / pathlib.Path(item["postSourcePath"]).name)}
                for item in audio_provenance
            ],
            "conformPlan": plan, "captionWindows": caption_windows,
            "outputs": outputs,
            "qc": {
                "passed": True,
                "scope": "deterministic technical and lineage checks only",
                "humanCreativeApprovalRequired": True,
                "checks": checks,
            },
        }
        manifest["manifestDigest"] = hashlib.sha256(json.dumps(
            manifest, sort_keys=True, ensure_ascii=False,
            separators=(",", ":")).encode()).hexdigest()
        temp["manifest"].write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(temp_dir, final_dir)
        return manifest
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
