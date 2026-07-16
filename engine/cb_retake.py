#!/usr/bin/env python3
"""GATE 4 — RETAKES / EDIT (surgical). Regenerate ONE shot inside a beat (continuity-matched) and splice it back at its
frame boundaries, instead of re-rendering the whole beat. Never lose the good bits; never pay for a full re-render.

    splice_shot(beat_clip, fs, fe, replacement, fps, out)   # frame-accurate: beat[:fs] + replacement(slot) + beat[fe:]
    regen_shot(pkg, "1.B4#shot7", "how you want it", episode)  # seed → fix prompt → render the shot → splice → new beat
"""
import os, re, json, subprocess, math
import cb_gen, cb_address
import cb_prompts as P
# FIXED 2026-07-11 (full-codebase audit — dead code): the module-level HERE constant was defined but never
# referenced anywhere in this file; removed rather than left as an orphaned path helper nobody uses.

def _load_beat(pkg, code):
    """FIXED 2026-07-11 (full-codebase audit — duplication): the 'load the package JSON and find the beat by
    beatCode/shotCode' snippet used to be copy-pasted verbatim across beat_retake_brief/preview_brief/
    regen_shot in this same file. One shared helper now; returns the beat dict or None."""
    d = json.load(open(pkg))
    return next((b for b in (d.get("beats") or d.get("shots") or [])
                 if (b.get("beatCode") or b.get("shotCode")) == code), None)

def _load_scene(pkg, scene_num):
    """FIXED 2026-07-12 (full-codebase audit continued — duplication): the scene dict for `scene_num`, needed
    so `_shot_fix_prompt` can resolve the beat's own physical-archetype `prohibited_staging` the same way the
    real v5 emitter does (`cb_segprompt._v5_archetype_prohibited`, which takes a beat AND a scene). Fail-open,
    matching this file's own convention elsewhere: an unresolved scene degrades to {} rather than raising."""
    try:
        d = json.load(open(pkg))
        sn = str(scene_num)
        return next((s for s in (d.get("scenes") or []) if str(s.get("sceneNumber")) == sn), None) or {}
    except Exception:
        return {}

def parse_ref(ref):
    """'1.B4#shot7' -> ('1.B4', 7)."""
    m = re.match(r"\s*([0-9]+\.B[0-9a-zA-Z]+)\s*#\s*shot\s*([0-9]+)", str(ref))
    if not m:
        raise ValueError(f"bad shot ref {ref!r} (expected like '1.B4#shot7')")
    return m.group(1), int(m.group(2))

def _extract_frame(clip, frame, out):
    """Frame-accurate single-frame grab (the continuity SEED — the exact frame the shot begins from)."""
    try:
        os.remove(out)
    except OSError:
        pass
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", clip,
                        "-vf", f"select=eq(n\\,{max(0, frame)})", "-frames:v", "1", out],
                       capture_output=True, text=True)
    if r.returncode or not os.path.exists(out) or os.path.getsize(out) == 0:
        return None
    return out

def splice_shot(beat_clip, fs, fe, replacement, fps, out, preserve_length=True):
    """Replace frames [fs, fe) of beat_clip with `replacement`, as ONE concat — hard cuts at the shot boundaries,
    frame-accurate via the trim filter. preserve_length=True trims the replacement to the SLOT length (beat length
    unchanged — addressing stays valid); False flexes the beat to the replacement's own length (for a fix that needs
    more screen time — then re-conform the scene to refresh the timecodes)."""
    slot = max(1, fe - fs)
    mv = f"trim=end_frame={slot}," if preserve_length else ""
    ma = f"atrim=end={slot/fps:.3f}," if preserve_length else ""
    fc = (
        f"[0:v]trim=end_frame={fs},setpts=PTS-STARTPTS,setsar=1,format=yuv420p[v1];"
        f"[0:a]atrim=end={fs/fps:.3f},asetpts=PTS-STARTPTS[a1];"
        f"[1:v]{mv}setpts=PTS-STARTPTS,setsar=1,fps={fps},format=yuv420p[vm];"
        f"[1:a]{ma}asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo[am];"
        f"[0:v]trim=start_frame={fe},setpts=PTS-STARTPTS,setsar=1,format=yuv420p[v3];"
        f"[0:a]atrim=start={fe/fps:.3f},asetpts=PTS-STARTPTS[a3];"
        f"[v1][a1][vm][am][v3][a3]concat=n=3:v=1:a=1[v][a]"
    )
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", beat_clip, "-i", replacement, "-filter_complex", fc,
           "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print("splice ERROR:", r.stderr[-700:]); return None
    return out

def _extract_clip(src, fs, fe, out, fps):
    """Trim frames [fs, fe) of `src` into a standalone short mp4 — ONE shot, for before/after review. Falls back to
    video-only if the source has no audio. Returns out or None."""
    fc = (f"[0:v]trim=start_frame={fs}:end_frame={fe},setpts=PTS-STARTPTS,setsar=1,format=yuv420p[v];"
          f"[0:a]atrim=start={fs/fps:.3f}:end={fe/fps:.3f},asetpts=PTS-STARTPTS[a]")
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-filter_complex", fc,
                        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out],
                       capture_output=True, text=True)
    if r.returncode:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vf",
                        f"trim=start_frame={fs}:end_frame={fe},setpts=PTS-STARTPTS,setsar=1,format=yuv420p",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", out], capture_output=True, text=True)
    return out if os.path.exists(out) else None

def _dims(clip):
    try:
        o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height", "-of", "csv=p=0:s=x", clip], capture_output=True, text=True).stdout.strip()
        w, h = o.split("x"); return int(w), int(h)
    except Exception:
        return 1280, 720

def _stamp_shot_clip(clip, ref, scene_in, scene_out, tag, out, fps):
    """Burn the SAME timecode + shot-code stamp the review video uses onto a short clip (scene timecode + frame top-left,
    Ref + scene in–out + BEFORE/AFTER bottom-left) — so a retake before/after never loses the time/shot reference. PIL
    per-second PNGs + the `overlay` filter (this ffmpeg has no drawtext). Returns `out` on success, else the input clip."""
    try:
        import tempfile, math, shutil
        from PIL import Image, ImageDraw
        import cb_post
        dur = cb_post._dur(clip)
        if not dur:
            return clip
        W, H = _dims(clip)
        big, small = cb_post._pil_font(30), cb_post._pil_font(26)
        label = f"{ref}    [{cb_post._mss(scene_in)}-{cb_post._mss(scene_out)}]    {tag}"
        tmp = tempfile.mkdtemp(prefix="retake_stamp_")
        for sec in range(max(1, int(math.ceil(dur)))):
            img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(img)
            t = scene_in + sec
            cb_post._boxed(dr, big, f"{cb_post._mss(t)}   f{int(t * fps)}", 18, 14, (255, 255, 255, 255))
            cb_post._boxed(dr, small, label, 18, H - 54, (255, 230, 0, 255))
            img.save(os.path.join(tmp, f"ov_{sec:04d}.png"))
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", clip, "-framerate", "1",
                            "-i", os.path.join(tmp, "ov_%04d.png"), "-filter_complex",
                            "[0:v][1:v]overlay=0:0[v]", "-map", "[v]", "-map", "0:a?",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                            "-c:a", "copy", "-movflags", "+faststart", out], capture_output=True, text=True)
        shutil.rmtree(tmp, ignore_errors=True)
        return out if (not r.returncode and os.path.exists(out)) else clip
    except Exception as e:
        print(f"  stamp skipped ({str(e)[:80]})"); return clip

def _make_review_clip(src, fs, fe, ref, scene_in, scene_out, tag, out, fps):
    """Extract shot [fs, fe) from src and burn the timecode + shot-code stamp on it (before/after for the retake log).
    Guarantees `out` exists (stamped if PIL/ffmpeg allow, else the plain extract). Returns out or None."""
    raw = out + ".raw.mp4"
    if not _extract_clip(src, fs, fe, raw, fps):
        return None
    res = _stamp_shot_clip(raw, ref, scene_in, scene_out, tag, out, fps)
    if res == out:
        try: os.remove(raw)
        except OSError: pass
    else:
        os.replace(raw, out)   # stamp unavailable → keep the unstamped extract under the stable name
    return out

def _frame_mean(png):
    from PIL import Image
    im = Image.open(png).convert("RGB").resize((48, 27))
    px = list(im.getdata()); n = max(1, len(px))
    return [sum(p[c] for p in px) / n for c in range(3)]

def _match_grade(clip, ref_frame, out):
    """Match clip's overall grade (per-channel mean) to ref_frame (the beat's EXACT prior frame) via a CLAMPED
    per-channel gain — so the regenerated shot's lighting/palette match the beat across the cut. Returns the (possibly
    graded) clip; falls back to the original on any error or if it already matches."""
    try:
        f0 = clip + ".f0.png"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", clip, "-frames:v", "1", f0], capture_output=True)
        rm, cm = _frame_mean(ref_frame), _frame_mean(f0)
        try: os.remove(f0)
        except OSError: pass
        g = [max(0.75, min(1.35, (rm[c] / cm[c]) if cm[c] else 1.0)) for c in range(3)]
        if all(abs(x - 1.0) < 0.02 for x in g):
            return clip
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", clip, "-vf",
                            f"colorchannelmixer=rr={g[0]:.4f}:gg={g[1]:.4f}:bb={g[2]:.4f}",
                            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-c:a", "copy", "-movflags", "+faststart", out], capture_output=True, text=True)
        return out if (not r.returncode and os.path.exists(out)) else clip
    except Exception as e:
        print(f"  grade-match skipped ({str(e)[:80]})"); return clip

def _seam_delta(ref_frame, clip):
    """Mean per-channel colour distance (0–255) between the beat's prior frame and the new shot's first frame.
    ~0 = the lighting lines up across the cut; a big number = a mismatch to eyeball."""
    try:
        f0 = clip + ".s0.png"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", clip, "-frames:v", "1", f0], capture_output=True)
        rm, cm = _frame_mean(ref_frame), _frame_mean(f0)
        try: os.remove(f0)
        except OSError: pass
        return round(sum(abs(rm[c] - cm[c]) for c in range(3)) / 3, 1)
    except Exception:
        return None

def _char_refs(beat):
    """The character identity refs for the beat (slot + path), so the regen holds identity."""
    refs, anchors = [], []
    cast = [c for c in (beat.get("openingCast") or beat.get("characters") or []) if c]
    for i, c in enumerate(cast):
        try:
            r = P.char_identity_ref(c)
        except Exception:
            r = ""
        if r:
            slot = f"@Image{2 + len(refs)}"   # @Image1 is the continuity seed; characters start at @Image2
            refs.append({"name": c, "slot": slot}); anchors.append(r)
    return refs, anchors

def _shot_fix_prompt(beat, shot, change, char_refs, lock="", keep="", scene=None):
    names = ", ".join(c["name"] for c in char_refs) or "the established character(s)"
    refs = {"continue_from": "@Image1"}
    for c in char_refs:
        refs[c["name"]] = c["slot"]
    continuity = ("CONTINUATION SHOT. @Image1 is the EXACT frame this shot begins from. Match its character pose, "
                  "position, facing, scale, lighting, palette, identity and ANY carried props PRECISELY, holding "
                  "the established Crystal Cove look — then perform the action below as one continuous motion.")
    if lock:
        continuity += f" LOCK (must stay identical across the cut): {lock}"
    # FIXED 2026-07-12 (full-codebase audit continued — duplication): style/negative used to be a small,
    # independently hand-typed duplicate of content centrally maintained elsewhere — cb_segprompt._style()/
    # _standing_negatives() and the beat's own resolved physical-archetype prohibited_staging (rule 62's
    # automatic safety net against reproducing the exact defect a retake was fired to fix). The old hand-typed
    # style text still said "abundant colourful cut crystals" — the faceted/cut-crystal phrasing CLAUDE.md
    # rule 25 flags as a Crystal World Rule violation — proof this copy had already silently drifted from
    # doctrine. Now pulled from the same shared functions the real v5 emitter uses, so a future canon/negatives
    # change and the archetype safety net both propagate to a retake automatically instead of living only in
    # the normal Gate-3 render path. Fail-open to the prior hand-typed text if cb_segprompt is ever
    # unavailable — a retake must never hard-crash over an import, only lose this one extra layer of
    # protection (matching this file's own director_retake_brief fail-open convention).
    try:
        import cb_segprompt
        style = cb_segprompt._style()
        scene_look = cb_segprompt._v5_scene_look(scene or {})
        if scene_look:
            style = style + " " + scene_look
        negative = cb_segprompt._v5_negative_line(beat, scene or {})
        negative = negative.split("Negative: ", 1)[-1].rstrip(".")
    except Exception:
        style = ("Pixar-quality stylised 3D animation, Crystal Cove: warm volumetric morning light, abundant colourful "
                  "cut crystals in the world, weighty cartoon physics, shallow depth of field.")
        negative = ("style change, identity drift, off-model, extra or missing limbs/wings, a hard scene cut, a new "
                     "character entering, on-screen text, a different location or palette.")
    p = {
        "references": refs,
        "subject": f"Crystal Cove — {names}",
        "continuity": continuity,
        "action": change,
        "camera": shot.get("camera") or "hold the established framing of @Image1",
        "style": style,
        "negative": negative,
    }
    if keep:
        p["keep_unchanged"] = keep
    return p

# ── DIRECTOR CHECK on the retake wording ──────────────────────────────────────────────────────────────────────────
# Julian's plain-English note ("the moustache should wipe off") is NOT fed raw to the renderer. The show's Director
# reads it against the shot's context + the character bibles + canon, and rewrites it into ONE precise, continuity-
# locked retake instruction — changing only what was asked, naming exactly what must stay identical across the cut.
# Fail-open: if the director is off / errors, the raw change is used (the retake still runs). Cached per note so a
# preview and the fire reuse the SAME brief (no drift, no double LLM call).
RETAKE_DIRECTOR_VERSION = "v1-retake-2026-07-01"

def _retake_director_on():
    return os.environ.get("CB_RETAKE_DIRECTOR", "1").strip().lower() not in ("0", "false", "off", "no")

def _retake_brief_schema():
    from pydantic import BaseModel, Field
    from typing import List
    class RetakeBrief(BaseModel):
        action: str = Field(description="the rewritten retake instruction — ONE precise, concrete, imperative sentence the renderer performs as this shot's action; changes ONLY what the showrunner asked, continuity-aware")
        continuity_lock: str = Field(description="one line naming exactly what must stay identical across the cut: identity/pose-into, lighting, palette, carried props, framing")
        keep_unchanged: str = Field(description="what in this shot must NOT change, so the renderer does not over-correct beyond the note")
        rationale: str = Field(description="one line — how you read the showrunner's note into this instruction")
        confidence: str = Field(description="high | medium | low — how unambiguous the note was")
        flags: List[str] = Field(default_factory=list, description="concerns: ambiguity, continuity risk, physically tricky, canon conflict — empty if none")
    return RetakeBrief

def _retake_brief_fp(issue, change, shot_action):
    import hashlib
    return hashlib.sha1("|".join([RETAKE_DIRECTOR_VERSION, issue or "", change or "", shot_action or ""]).encode()).hexdigest()[:16]

def director_retake_brief(pkg, code, sh, beat, char_refs, issue, change, episode="Ep1"):
    """Rewrite a plain-English retake note into a precise, continuity-locked Director instruction. `sh=None` means a
    WHOLE-BEAT brief (the beat is being re-fired from scratch, not spliced) — e.g. a full creative redirect applied
    before Gate 3 re-fires; `sh` given means the usual single-spliced-shot brief. Returns a dict {action,
    continuity_lock, keep_unchanged, rationale, confidence, flags, _raw_change} or None (fail-open / off)."""
    if not _retake_director_on() or not str(change or "").strip():
        return None
    if sh is not None:
        shot_action = sh.get("action", "")
        cache = f"media/_retake_brief_{episode}_{code}_s{sh.get('index')}.json"
    else:
        bits = [str(beat.get("storyBeat") or "").strip()]
        bits += [str(c.get("action") or "").strip() for c in (beat.get("cuts") or [])]
        shot_action = " ".join(b for b in bits if b)
        cache = f"media/_retake_brief_{episode}_{code}_beat.json"
    fp = _retake_brief_fp(issue, change, shot_action)
    try:
        c = json.load(open(cache))
        if c.get("_fp") == fp:
            return c.get("result")
    except Exception:
        pass
    try:
        import cb_llm
        try:
            import cb_director_pass as DP
            bibles = "\n".join(DP._bible_brief(c["name"]) for c in char_refs) or "(no named characters)"
        except Exception:
            bibles = "(bibles unavailable — direct from the reference frame)"
        # FIXED 2026-07-11 (full-codebase audit): "summary"/"action" are not real top-level beat fields (the
        # actual synopsis field is storyBeat; "action" only exists per-cut) — this silently never carried the
        # beat's own story synopsis for the common single-shot retake case.
        beat_ctx = " · ".join(f"{k}: {str(beat.get(k))[:160]}" for k in ("beatCode", "storyBeat", "want", "need")
                              if beat.get(k))
        scope = "ONE shot inside a finished beat" if sh is not None else "an ENTIRE beat, about to be re-rendered from scratch (not a single spliced shot)"
        system = (
            # GATE 4'S NAMED CHAIR (2026-07-14, restoring the named-auteur-per-chair doctrine,
            # CRYSTAL_BEARS_STUDIO_BIBLE.md Law 1): this pass is EDITORIAL work, not a second directing pass — the
            # Director already made his creative call at Gate 1; a retake note is a showrunner's precise correction
            # to ONE thing, and turning that plain-English note into the single most precise instruction that fixes
            # exactly what he flagged, while leaving everything else exactly as cut, is Kevin Nolting's own job
            # (editor — Up, Inside Out, Soul, Toy Story 3): reading a note for its real intent, choosing the minimal
            # change that actually serves it, and never touching a frame beyond what was asked.
            "You are KEVIN NOLTING, editing the animated kids' show Crystal Bears — doing a RETAKE NOTE pass. This is "
            "an editor's judgment call, not a fresh directing pass: the showrunner already knows what he wants "
            "fixed and has flagged "
            f"{scope}, writing in plain English what is wrong (ISSUE) and how "
            "he wants it (CHANGE TO). Your job is exactly Nolting's own craft — translate his note into ONE precise, "
            "continuity-locked retake instruction the renderer will perform as this shot's action, touching nothing "
            "he didn't ask for.\n"
            "HARD RULES:\n"
            "• Change ONLY what he asked. Everything else must match the surrounding frames EXACTLY — identity, the "
            "pose the shot begins from, lighting, palette, carried props, framing.\n"
            "• Honour weight and real cartoon physics, and the character bibles + canon you are given.\n"
            "• If the shot contains a gag, preserve its mechanism; only fix what he flagged.\n"
            "• NEVER add a new character, prop, on-screen text, location, or restyle. NEVER drift the character.\n"
            "• NEVER write or alter dialogue — the spoken lines are locked verbatim elsewhere; direct only the "
            "physical action, camera and timing around them.\n"
            "• If his note is ambiguous, read it the way an editor reads an ambiguous note in the room — choose "
            "the interpretation that best serves the cut's own established timing, continuity and intent, never the "
            "one that invents new content or a bigger change than he described — and say so in flags. Keep "
            "'action' to one concrete imperative sentence a renderer can execute.")
        user = (
            f"BEAT: {beat_ctx or code}\n"
            + (f"SHOT: {code}#shot{sh.get('index')} — current action: {shot_action or '(unknown)'}\n"
               if sh is not None else
               f"WHOLE BEAT {code} — current combined action across all cuts: {shot_action or '(unknown)'}\n")
            + f"CHARACTER(S) IN FRAME (direct THEM, on-model):\n{bibles}\n\n"
            f"SHOWRUNNER'S ISSUE (what's wrong): {issue or '(not stated — infer from the change)'}\n"
            f"SHOWRUNNER'S CHANGE TO (how he wants it): {change}\n\n"
            "Rewrite this into the retake brief.")
        label = f"retake_director_{code}_s{sh.get('index')}" if sh is not None else f"retake_director_{code}_beat"
        out = cb_llm.structured(system, user, _retake_brief_schema(), label=label).model_dump()
        out["_raw_change"] = change
        try:
            os.makedirs("media", exist_ok=True)
            json.dump({"_fp": fp, "_version": RETAKE_DIRECTOR_VERSION, "result": out}, open(cache, "w"), indent=2)
        except Exception:
            pass
        return out
    except SystemExit as e:
        print(f"  retake director unavailable ({str(e)[:120]}) — using the note verbatim.", flush=True)
        return None
    except Exception as e:
        print(f"  retake director error ({type(e).__name__}: {str(e)[:120]}) — using the note verbatim.", flush=True)
        return None

def beat_retake_brief(pkg, code, issue, change, episode="Ep1"):
    """WHOLE-BEAT variant of director_retake_brief — for a full creative redirect applied to a beat's own Gate-1
    direction fields (storyBeat/cameraArc/pauseHold/motionTempo) before Gate 3 re-fires it from scratch, never a
    hand-patched prompt. Returns the same brief dict as director_retake_brief, or None (fail-open)."""
    beat = _load_beat(pkg, code)
    if not beat:
        return None
    char_refs, _ = _char_refs(beat)
    return director_retake_brief(pkg, code, None, beat, char_refs, issue, change, episode)

def preview_brief(pkg, locator, issue, change, episode="Ep1", scene=None):
    """Resolve a locator (Ref or timecode) and return the Director's reworded retake brief WITHOUT rendering — so the
    studio can show 'here's how the director read your note' before you fire. {ok, ref, brief} or {ok:False, error}."""
    try:
        if scene is None:
            m = re.match(r"^(\d+)\.", str(locator) or "")
            scene = int(m.group(1)) if m else 1
        ref = _resolve_locator(pkg, locator, episode, scene)
        code, shotnum = parse_ref(ref)
        mp = cb_address.beat_address_map(pkg, code, episode)
        sh = next((s for s in mp.get("shots", []) if s.get("index") == shotnum), None)
        if not sh:
            return {"ok": False, "error": f"{ref}: shot {shotnum} not found"}
        beat = _load_beat(pkg, code) or {}
        char_refs, _ = _char_refs(beat)
        brief = director_retake_brief(pkg, code, sh, beat, char_refs, issue, change, episode)
        return {"ok": True, "ref": ref, "shot_action": sh.get("action", ""), "brief": brief}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:160]}"}

def regen_shot(pkg, ref, change, episode="Ep1", render_dur=5, out=None, preserve_length=True, issue=""):
    """Regenerate ONE shot (continuity-seeded) and splice it into its beat. Returns {ok, ref, new_beat, replacement, ...}."""
    code, shotnum = parse_ref(ref)
    m = cb_address.beat_address_map(pkg, code, episode)
    shots = [s for s in m.get("shots", []) if "frame_start" in s]
    sh = next((s for s in shots if s["index"] == shotnum), None)
    if not sh:
        return {"ok": False, "error": f"{ref}: shot {shotnum} not found ({len(shots)} shots)"}
    fps = m["fps"]; fs, fe = sh["frame_start"], sh["frame_end"]
    # FIXED 2026-07-11 (full-codebase audit): render_dur used to be a hardcoded default (5s) never derived
    # from or validated against the shot's own slot length — with preserve_length=True (the default),
    # splice_shot pads/holds a too-short replacement rather than refusing, so a slot longer than 5s could
    # silently produce a beat clip whose retaken shot reads as a held/frozen pad instead of new motion.
    slot_secs = (fe - fs) / fps
    min_dur = math.ceil(slot_secs)
    if render_dur < min_dur:
        print(f"  GATE 4 retake {ref}: requested render_dur={render_dur}s is shorter than this shot's own "
              f"slot ({slot_secs:.1f}s) — raising to {min_dur}s so the replacement actually covers it.", flush=True)
        render_dur = min_dur
    if not preserve_length and shotnum != max(s["index"] for s in shots):
        return {"ok": False, "error": (
            f"{ref}: preserve_length=False is only safe on the LAST shot of a beat. cb_address.beat_address_map "
            "derives every shot's frame range from the beat's action_timeline, which is never re-conformed after a "
            "splice — flexing a MIDDLE shot's length would silently shift every later shot's addressing off the "
            "real clip. Use preserve_length=True, or retake this beat's shots from the end backward.")}
    beat_clip = f"media/{episode}_{code}_{m['slug']}.mp4"
    if not os.path.exists(beat_clip):
        return {"ok": False, "error": f"beat clip missing: {beat_clip}"}
    # BEFORE — snapshot the original slot (just this shot), STAMPED, before we splice over it. The stamp = the same
    # scene timecode + shot-code the review video shows, so a before/after comparison never loses the reference.
    cref = f"{code}#shot{shotnum}"
    try:
        _wins = cb_address.scene_shot_windows(pkg, m.get("scene"), episode)
        _w = next((w for w in _wins if w.get("ref") == cref), None)
    except Exception:
        _w = None
    sin = _w["scene_in"] if _w else fs / fps
    sout = _w["scene_out"] if _w else fe / fps
    before = _make_review_clip(beat_clip, fs, fe, cref, sin, sout, "BEFORE",
                               f"media/_retake_{episode}_{code}_s{shotnum}_before.mp4", fps)
    beat = _load_beat(pkg, code) or {}
    # FIXED 2026-07-11 (full-codebase audit — Law 5): this path never checked whether the shot being retaken
    # has dialogue before firing generate_video_seedance_ref with no audio_urls — the exact "no native-voice
    # fallback" violation Law 5 exists to prevent (cb_beats.run guards this elsewhere for a whole-beat Gate-3
    # render, but a single-shot splice never went through that gate at all). Building a partial-beat V3 track
    # correctly time-aligned to just this shot's slot is real, separate work this fix does not attempt —
    # refusing loudly here (matching Law 5's own refusal convention) is safer than a silently wrong render.
    _cut_dlg = ((beat.get("cuts") or [{}])[shotnum - 1].get("dialogue") or "").strip() if beat.get("cuts") else ""
    if _cut_dlg:
        return {"ok": False, "error": (
            f"{ref}: this shot has dialogue (\"{_cut_dlg[:60]}\") — a single-shot retake has no way to fire "
            "a canonical V3 @Audio1 track for it yet (Law 5: no native-voice fallback, ever). Re-render the "
            "WHOLE beat through Gate 3 instead, which already builds and lip-syncs the real voice track.")}
    # 1) continuity SEED — the exact frame the shot begins from
    seed = f"media/_retake_seed_{episode}_{code}_s{shotnum}.png"
    if not _extract_frame(beat_clip, fs, seed):
        return {"ok": False, "error": "could not extract the continuity seed frame"}
    # 2) DIRECTOR CHECK — translate the plain-English note into precise, continuity-locked retake wording (fail-open)
    char_refs, anchors = _char_refs(beat)
    brief = director_retake_brief(pkg, code, sh, beat, char_refs, issue, change, episode)
    if brief and brief.get("action"):
        action = brief["action"]
        print(f"  director read {ref}: “{change[:60]}” → “{action[:90]}”"
              + (f"  ⚑ {'; '.join(brief.get('flags') or [])}" if brief.get("flags") else ""), flush=True)
    else:
        action = change
    # 3) fix prompt + identity refs
    scene = _load_scene(pkg, m.get("scene"))
    prompt = _shot_fix_prompt(beat, sh, action, char_refs,
                              lock=(brief or {}).get("continuity_lock", ""), keep=(brief or {}).get("keep_unchanged", ""),
                              scene=scene)
    # 3c) THE GATE-4 LINT (2026-07-14, closing the confirmed Gate-3-bypass gap, CLAUDE.md rule 84/85): this
    # path never ran the anti-slop/Character Vocabulary Law checks that gate every OTHER route to Seedance —
    # cb_qa.check_retake_prompt is the Gate-4-shaped sibling of check_gate3_lint/check_keyframe_lint, scoped
    # to _shot_fix_prompt's own dict shape (see that function's own docstring for why the other two lints
    # aren't directly reusable here).
    import cb_qa
    _lint = cb_qa.check_retake_prompt(prompt, characters=[c["name"] for c in char_refs])
    if not _lint["ok"]:
        return {"ok": False, "error": f"{ref}: retake lint failed — {'; '.join(_lint['blockers'])}"}
    for _f in _lint["flags"]:
        print(f"  GATE 4 retake {ref}: (lint flag) {_f}", flush=True)
    # 4) render the replacement shot (seeded from @Image1)
    repl = f"_retake_{episode}_{code}_s{shotnum}.mp4"
    print(f"  GATE 4 retake {ref}: rendering replacement shot ({render_dur}s, seeded) — action: {action[:80]}…", flush=True)
    try:
        cb_gen.generate_video_seedance_ref(prompt, [seed] + anchors, duration=render_dur, out=repl)
    except Exception as e:
        return {"ok": False, "error": f"render failed: {str(e)[:200]}"}
    replacement = f"media/{repl}"
    # 3b) GRADE-MATCH the new shot to the beat's EXACT prior frame so lighting/palette match across the cut
    graded = _match_grade(replacement, seed, f"media/_retake_{episode}_{code}_s{shotnum}_graded.mp4")
    seam = _seam_delta(seed, graded)
    print(f"  GATE 4 retake {ref}: grade-matched={graded != replacement} · seam Δ={seam} (≈0 = lighting lines up at the cut)", flush=True)
    # 4) splice into the beat (replace the slot, preserve beat length)
    out = out or f"media/{episode}_{code}_{m['slug']}.mp4"   # default: overwrite the beat in place
    spliced = splice_shot(beat_clip, fs, fe, graded, fps, out + ".tmp.mp4", preserve_length=preserve_length)
    if not spliced:
        return {"ok": False, "error": "splice failed"}
    os.replace(out + ".tmp.mp4", out)
    # AFTER — snapshot the new slot (just this shot, as it now lands in the beat), STAMPED the same way
    after = _make_review_clip(out, fs, fe, cref, sin, sout, "AFTER · retaken",
                              f"media/_retake_{episode}_{code}_s{shotnum}_after.mp4", fps)
    return {"ok": True, "ref": ref, "code": code, "shot": shotnum, "frames": [fs, fe], "fps": fps,
            "replacement": replacement, "graded": graded != replacement, "seam_delta": seam, "new_beat": out,
            "director_brief": brief, "action": action,
            "before": before if (before and os.path.exists(before)) else None,
            "after": after if (after and os.path.exists(after)) else None}

def read_retake_csv(path):
    """Read the FILLED/AMENDED retake sheet — every row that has a locator AND a change. Robust to an AMENDED sheet
    where you DELETE the fine rows and keep only the shots + changes, to a locator given as a Ref OR a timecode (the
    Scene-In column), and to a few CHANGE-TO header spellings. Headers are matched case-insensitively. Returns
    [{ref, change, issue}]."""
    import csv
    out = []
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                low = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
                loc = low.get("ref") or low.get("locator") or low.get("timecode") or low.get("scene in")
                change = next((low[k] for k in ("change to (how you want it)", "change to", "change", "retake") if low.get(k)), "")
                issue = low.get("issue / what's wrong") or low.get("issue") or ""
                if loc and change:
                    out.append({"ref": loc, "change": change, "issue": issue})
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"  retake-sheet read error: {e}")
    return out

def _parse_tc(s):
    """A locator TIMECODE → seconds. '0:50'→50.0, '0:50.5'→50.5, '50'/'50.5s'→50.5. None if not a timecode."""
    s = str(s or "").strip().lower().rstrip("s")
    m = re.match(r"^(\d+):([0-5]?\d(?:\.\d+)?)$", s)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    m = re.match(r"^(\d+(?:\.\d+)?)$", s)
    return float(m.group(1)) if m else None

def _resolve_locator(pkg, loc, episode, scene):
    """A retake locator = a canonical Ref (1.B4#shot7, used as-is) OR a review-video TIMECODE → the shot at that scene time."""
    loc = str(loc or "").strip()
    if re.match(r"^\d+\.B[0-9a-zA-Z]+#shot\d+$", loc):
        return loc
    t = _parse_tc(loc)
    if t is None:
        return loc
    w = cb_address.shot_at_time(pkg, scene, episode, t)
    return w["ref"] if w else loc

def read_retakes_json(path):
    """In-app TYPED retakes — [{ref, change, issue}] from the studio Gate-5 form (media/<ep>_Scene<n>_retakes.json)."""
    try:
        d = json.load(open(path))
        return [{"ref": (r.get("ref") or "").strip(), "change": (r.get("change") or "").strip(),
                 "issue": (r.get("issue") or "").strip()} for r in d if (r.get("ref") and r.get("change"))]
    except Exception:
        return []

def read_retakes(pkg, episode, scene):
    """The retakes to run THIS fire: the in-app run-list (JSON — exactly the one OR all you fired) if present, else the
    Excel sheet (CSV). Each locator (a TIMECODE like 0:50 OR a canonical Ref) is resolved to a shot Ref; dedup by Ref."""
    # "if present" means the JSON file EXISTS, not "the JSON list happens to be non-empty" — the old `or` fallback
    # treated an explicit, deliberately-empty in-app run-list (nothing selected this fire) the same as "no JSON at
    # all," silently falling through to whatever stale entries were still sitting in the Excel CSV from a previous
    # session (2026-07-08 audit finding).
    json_path = f"media/{episode}_Scene{scene}_retakes.json"
    if os.path.exists(json_path):
        src = read_retakes_json(json_path)
    else:
        src = read_retake_csv(f"media/{episode}_Scene{scene}_RETAKES.csv")
    seen, out = set(), []
    for r in src:
        ref = _resolve_locator(pkg, r["ref"], episode, scene)
        if ref and ref not in seen:
            seen.add(ref); out.append({"ref": ref, "change": r["change"], "issue": r.get("issue", ""), "locator": r["ref"]})
    return out

def _retake_log_path(episode, scene):
    return f"media/{episode}_Scene{scene}_retake_log.json"

def _base(p):
    return os.path.basename(p) if p else None

def _write_retake_log(episode, scene, retakes, results):
    """Upsert one entry per retake (by Ref — a re-fire replaces its prior entry), newest first. Each entry carries the
    director's wording + the BEFORE/AFTER short clips so the studio can show old-vs-new per shot."""
    import time
    path = _retake_log_path(episode, scene)
    try:
        prev = (json.load(open(path)) or {}).get("entries", [])
    except Exception:
        prev = []
    by = {e.get("ref"): e for e in prev if e.get("ref")}
    for rt, res in zip(retakes, results):
        res = res or {}
        prior = by.get(rt["ref"])
        if not res.get("ok") and prior and prior.get("ok"):
            # a failed re-attempt must NOT clobber a previously successful retake's entry — regen_shot never reaches
            # os.replace() before returning ok:False, so the clip on disk (and the prior before/after pair) are still
            # the real, current state. Keep the good entry; just note the retry failed.
            prior["retry_error"] = res.get("error", ""); prior["retry_ts"] = time.time()
            continue
        b = res.get("director_brief") or {}
        by[rt["ref"]] = {
            "ref": rt["ref"], "locator": rt.get("locator", rt["ref"]),
            "change": rt.get("change", ""), "issue": rt.get("issue", ""),
            "action": b.get("action", ""), "continuity_lock": b.get("continuity_lock", ""),
            "keep_unchanged": b.get("keep_unchanged", ""), "flags": b.get("flags", []),
            "confidence": b.get("confidence", ""),
            "before": _base(res.get("before")), "after": _base(res.get("after")),
            "seam_delta": res.get("seam_delta"), "ok": bool(res.get("ok")),
            "error": res.get("error", ""), "ts": time.time(),
        }
    merged = sorted(by.values(), key=lambda e: e.get("ts", 0), reverse=True)
    try:
        os.makedirs("media", exist_ok=True)
        json.dump({"episode": episode, "scene": scene, "entries": merged}, open(path, "w"), indent=2)
    except Exception as ex:
        print(f"  retake-log write skipped ({ex})", flush=True)
    return merged

def process_retakes(pkg, scene, episode="Ep1", preserve_length=True):
    """GATE 4 — read the retakes (in-app run-list or the filled sheet), regenerate each flagged shot (continuity-
    matched) + splice it in, save a BEFORE/AFTER clip of each changed shot + a retake log (so you can review old-vs-new
    per shot, not the whole scene), then re-conform the scene (hard-cut stitch + fresh REVIEW.mp4 + refreshed sheet)
    for re-review. Firing is NOT a sign-off — iterate, then sign off Gate 4 → Gate 5 (Post)."""
    import cb_post, cb_address
    print(f"GATE 4 — RETAKES: {episode} scene {scene}  (typed run-list + Excel CSV)", flush=True)
    retakes = read_retakes(pkg, episode, scene)
    if not retakes:
        print("  no filled retakes (the CHANGE-TO column is empty) — nothing to do.", flush=True)
        return {"ok": True, "retakes": 0}
    print(f"  {len(retakes)} retake(s) to run.", flush=True)
    results = []
    for rt in retakes:
        print(f"  → {rt['ref']}: {rt['change'][:70]}", flush=True)
        # FIXED 2026-07-14 (Julian's front-to-back wiring pass — "whatever it takes, fix it now"): this loop
        # used to call regen_shot() with no guard, so a single bad/stale package path (regen_shot ->
        # cb_address.beat_address_map -> a bare json.load, no try/except) crashed the WHOLE batch — losing
        # `results` for every retake already processed before the crash (never reaches _write_retake_log or
        # the re-conform step below), not just the one that actually failed. Isolated per-item, matching
        # regen_shot's own {ok:False, ref, error} shape on its own controlled-failure paths (e.g. "shot not
        # found") so a caught exception here reads identically to a normal, expected failure downstream.
        try:
            results.append(regen_shot(pkg, rt["ref"], rt["change"], episode,
                                      preserve_length=preserve_length, issue=rt.get("issue", "")))
        except Exception as e:
            print(f"  → {rt['ref']}: FAILED — {e!r} (continuing with the remaining retakes in this batch)", flush=True)
            results.append({"ok": False, "ref": rt["ref"], "error": f"{type(e).__name__}: {e}"})
    succeeded = [r for r in results if r.get("ok")]
    _write_retake_log(episode, scene, retakes, results)   # before/after log for the studio (per-shot old-vs-new)
    try:   # re-conform: hard-cut stitch + fresh review overlay + refreshed sheet (timecodes follow any flexed beats)
        clips = cb_post._clips(pkg, episode, str(scene))
        stitched = f"media/{episode}_Scene{scene}_beats.mp4"
        cb_post.assemble_picture(cb_post._norm(clips), stitched)
        cb_post.burn_review_overlay(stitched, cb_address.scene_shot_windows(pkg, scene, episode),
                                    f"media/{episode}_Scene{scene}_REVIEW.mp4")
        cb_address.write_retake_csv(pkg, scene, episode)
        print(f"  re-conformed -> {stitched} (+ fresh REVIEW.mp4 + RETAKES.csv). Review the before/after, iterate, then sign off Gate 4 → Gate 5 (Post).", flush=True)
    except Exception as e:
        print(f"  re-conform skipped ({str(e)[:160]})", flush=True)
    return {"ok": True, "retakes": len(retakes), "succeeded": len(succeeded), "results": results}

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("usage: cb_retake.py <package.json> <ref like 1.B4#shot7> <change...> [episode]"); raise SystemExit(2)
    pkg, ref = sys.argv[1], sys.argv[2]
    change = sys.argv[3] if len(sys.argv) > 3 else "fix this shot"
    ep = sys.argv[4] if len(sys.argv) > 4 else "Ep1"
    print(json.dumps(regen_shot(pkg, ref, change, ep), indent=2))
