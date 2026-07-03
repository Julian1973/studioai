#!/usr/bin/env python3
"""cb_post.py — GENERALIZED post (replaces the ad-hoc build_scene*_post.py).

POST = CURATION (the quality filter — NOT composition). The hardest creative work happens at GATE 3: Seedance
scores each take — the acted ElevenLabs V3 voice + Seedance's own synchronised SFX and TIMED comedy/emotional
music (its timing is the point) are ALREADY in the clip audio. Gate 5 LISTENS and decides what Seedance got
right — keeps what works, trims or replaces what doesn't. For a scene Post:
  1) ASSEMBLES the picture from the scene's clips — HARD CUTS shot-to-shot (no in-scene cross-dissolves; those are
     reserved for BETWEEN scenes only) + a held last frame — KEEPING the clip audio (voice + SFX + Seedance's timed
     music) so the sound flows continuously while the picture cuts.
  2) MASTERS to broadcast loudness -> a preview "complete" mix. The ElevenLabs Music bed is the FALLBACK, not the
     default — fired ONLY if Seedance's own music isn't right for a scene: a hand-supplied MUSIC.mp3 (always wins)
     or CB_AUTO_MUSIC_BED=1 (scratch underscore) gets ducked under the voice; otherwise Post keeps the clip's score.
  3) Exports STEMS (picture+voice, music, ambience) so Julian curates the final keep/trim/replace + mix in CapCut by ear.

The clip audio is never stripped. Post is the quality filter + the seamless stitch + the stems — never the creative layer.

    python3 cb_post.py <package.json> <sceneNumber> [episode=Ep1]
"""
import json, sys, os, subprocess, shutil

HELD = 1.6   # held last frame (tension beat)
XF = 0.4     # cross-dissolve duration — RESERVED for passage-of-time transitions BETWEEN scenes ONLY (never within a scene)
AUTO_MUSIC_BED = os.environ.get("CB_AUTO_MUSIC_BED", "") == "1"   # OFF by default — Seedance scores the clip; a bed
                                                                 # on top is a deliberate, opt-in/CapCut decision

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
        slug = s.get("slug", s["shotCode"].replace(".", "_"))
        p = f"media/{episode}_{s['shotCode']}_{slug}.mp4"
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
    subprocess.run(["ffmpeg","-y","-i",clip,"-f","lavfi","-i","anullsrc=channel_layout=stereo:sample_rate=44100",
                    "-shortest","-c:v","copy","-c:a","aac","-b:a","128k", tmp], capture_output=True)
    return tmp

def _norm(clips): return [_ensure_audio(c) for c in clips]

def stitch(pkg, scene_num, episode="Ep1"):
    """The COMPLETED ANIMATION cut — join the clips (hard cuts + held tail), keeping their native audio.
    No music/mix (that's Post). Appears in the studio's Animation tab as 'completed animation'."""
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    clips = _clips(pkg, episode, scene_num)
    if not clips:
        print(f"STITCH: no clips for {episode} scene {scene_num}"); return
    out = f"media/{episode}_Scene{scene_num}_animation.mp4"
    assemble_picture(_norm(clips), out)
    print(f"STITCH -> {out} (completed animation cut, {len(clips)} clips)", flush=True)
    return out

def assemble_picture(clips, out):
    """HARD-CUT concat of the scene's clips (instant shot-to-shot, NO in-scene cross-dissolves) + a brief held last
    frame for the scene end, keeping native voice. Cross-dissolves belong only between scenes (passage of time)."""
    inputs = []
    for c in clips: inputs += ["-i", c]
    durs = [_dur(c) for c in clips]
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
    if r.returncode: print("assemble_picture ERROR:", r.stderr[-400:])
    return _dur(out)

SETTLE_TRIM = 2.0   # matches cb_segprompt.HANDLE_SETTLE (mirrored locally, no cross-module import — same house
                    # convention as elsewhere). JOIN ON LIVE MOTION (Julian, 2026-07-03, superseding the earlier
                    # fixed-fraction trim below): the settle exists in the footage for the relay's harvest and for
                    # these trim handles — it is trimmed OUT of the visible cut ENTIRELY, off every clip but the
                    # scene's last (whose settle IS the scene's real landing and stays in full).
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

def assemble_conformed(clips, out, settle_trim=SETTLE_TRIM, edge_frames=EDGE_FRAMES):
    """JOIN ON LIVE MOTION (Julian, 2026-07-03) — Gate 4's conform doctrine, superseding the earlier fixed-
    fraction settle trim. Still HARD CUTS (no cross-dissolve — that rule is unchanged); the flow comes from WHERE
    each cut lands. Per clip: the full settle (settle_trim seconds) is removed from the tail of every clip but the
    scene's last, PLUS a small edge_frames trim off the closing deceleration of what's left (every clip but the
    last) and off the opening ease-in (every clip, including the first). Never re-renders — trims/concats
    already-rendered clips only. This is the "conformed cut"; assemble_picture (unchanged) remains the raw
    butt-join for comparison."""
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
    if r.returncode: print("assemble_conformed ERROR:", r.stderr[-400:])
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

def mix(picture, music, ambience, out):
    """Lay continuous music + ambience UNDER the picture's native voice (ducked), hold to end, master."""
    T = _dur(picture); fo = round(T - 1.0, 2)
    inputs = ["-i", picture]
    have_mus = music and os.path.exists(music)
    have_amb = ambience and os.path.exists(ambience)
    if have_mus: inputs += ["-i", music]
    if have_amb: inputs += ["-i", ambience]
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
    n = len(mix_in)
    fc.append("".join(mix_in) + f"amix=inputs={n}:normalize=0,highpass=f=35,"
              "equalizer=f=3000:t=q:w=2:g=1.2,highshelf=f=9000:g=1.5,"
              "acompressor=threshold=-16dB:ratio=2:attack=25:release=250:makeup=2,"
              "loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.89:level=false[aout]")
    cmd = ["ffmpeg","-y"] + inputs + ["-filter_complex", ";".join(fc),
           "-map","0:v:0","-map","[aout]","-c:v","copy","-c:a","aac","-b:a","256k","-movflags","+faststart", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: print("mix ERROR:", r.stderr[-400:])
    return out

def run(pkg, scene_num, episode="Ep1"):
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    clips = _clips(pkg, episode, scene_num)
    if not clips:
        print(f"GATE 5: no clips for {episode} scene {scene_num} (fire gate 3 first)."); return
    print(f"GATE 5 — Post: {episode} scene {scene_num}, {len(clips)} clips", flush=True)
    picture = f"media/{episode}_Scene{scene_num}_picture.mp4"
    assemble_picture(_norm(clips), picture)
    print(f"  picture (clips hard-cut + held tail, native voice) -> {picture}", flush=True)
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
    mix(picture, music, amb, complete)
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
    # CapCut handoff: the picture (V3 voice + SFX already in it) + the CLEAN per-shot V3 voice stems (for
    # re-balancing / swaps) + the auto-generated scratch music bed + a readme. Julian refines the mix by ear.
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
                 "The picture + voice + SFX + Seedance's timed score are delivered; the bed-on-top is your last, optional call.\n")
    print(f"  CapCut handoff -> {stems}/ (picture + {len(voices)} clean voice stems + readme)", flush=True)
    print("=== POST DONE ===", flush=True)

if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "Ep1")
