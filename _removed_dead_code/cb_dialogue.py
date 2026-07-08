#!/usr/bin/env python3
"""⚠ DEPRECATED (2026-06-29) — NOT on the live render path. Do NOT wire this back into regen or Gate 3.

Clip rendering — Gate 3 AND clip regen — now runs through ONE unified path: cb_beats.run →
cb_prompts.seedance_json → cb_gen.generate_video_seedance_ref (honours seedancePromptOverride, the @Audio1
ElevenLabs V3 lip-sync track, and Seedance-scored SFX + MUSIC). This module's per-shot build_ref2vid_prompt
path is SFX-only (NO music) and is no longer called by the pipeline — cb_pipeline.regen switched to cb_beats.run
(2026-06-29). Kept for reference and the __main__ CLI only. Gate 3 and clip regen MUST stay on the same path.
────────────────────────────────────────────────────────────────────────────────────────────────────────────
Scene DIALOGUE driver — the talking-clip pipeline THROUGH THE SYSTEM, per shot, zero hand-prompts.

Per shot in a scene: ensure the signed-off keyframe exists, build the directed V3 dialogue track (cb_voice),
build the Seedance ref2vid @-prompt (cb_prompts.build_ref2vid_prompt — SFX, NO music), render the talking clip
(cb_gen.generate_video_seedance_ref), then stitch the scene. Every string is generated from the shot package +
config + canon — nothing is hand-typed.

    python3 cb_dialogue.py <package.json> <sceneNumber> [episode=Ep1] [codes=1.4,1.5] [--dry]

--dry prints the directed lines + image bindings + the ref2vid prompt for every shot and renders NOTHING
(the proof that the system generates it all from the package).
"""
import os, sys, json, subprocess
import cb_gen, cb_prompts as P, cb_voice

ANCHORS = {"Fuzzby": "../cb-seed/assets/CB_Fuzzby_turn4.png",
           "Zenny":  "../cb-seed/assets/CB_Zenny_turn4.png"}

def _anchor(c):
    a = ANCHORS.get(c) or f"../cb-seed/assets/CB_{c.replace(chr(39), '').replace(' ', '')}_turn4.png"
    return a if os.path.exists(a) else None

def run(pkg_path, scene_num, episode="Ep1", codes=None, dry=False, note=""):
    d = json.load(open(pkg_path)); scene_num = str(scene_num)
    shots = [s for s in (d.get("beats") or d.get("shots") or []) if str(s.get("sceneNumber")) == scene_num]
    for _s in shots:
        _s.setdefault("shotCode", _s.get("beatCode"))
    print(f"DIALOGUE driver: {episode} scene {scene_num} — {len(shots)} shots"
          + (f" (codes={codes})" if codes else "") + (" [DRY]" if dry else ""), flush=True)
    # Gate 3 FAIL-EARLY: every shot in scope must have its keyframe (Gate 2b) — never silently skip into a partial scene.
    targets = [s for s in shots if not codes or s["shotCode"] in codes]
    missing = [s["shotCode"] for s in targets
               if not os.path.exists(f"media/{episode}_{s['shotCode']}_{s.get('slug', s['shotCode'].replace('.', '_'))}.png")]
    if missing and not dry:
        raise SystemExit(f"GATE 3: {len(missing)} keyframe(s) missing ({', '.join(missing)}) — "
                         f"fire Gate 2b (keyframes) first. Nothing rendered.")
    clips = []
    for s in shots:
        code = s["shotCode"]; slug = s.get("slug", code.replace(".", "_"))
        if codes and code not in codes:
            continue
        kf = f"media/{episode}_{code}_{slug}.png"
        chars = s.get("characters", [])
        prev_frame = None
        if clips and not dry:   # continuity handshake — the PREVIOUS clip's last frame flows into this shot
            prev_frame = str(cb_gen.MEDIA / f"_cont_{code}.png")
            try:
                cb_gen.last_frame(clips[-1], out=prev_frame)
            except Exception as e:
                print(f"  {code}: continuity last-frame failed ({str(e)[:80]}) — rendering without handshake", flush=True)
                prev_frame = None
        prompt = P.build_ref2vid_prompt(s, episode=episode, note=note, prev_frame=prev_frame)
        if dry:
            print(f"\n===== {code}  {slug} =====", flush=True)
            for c in P._speakers(s):
                print(f"  VOICE {c} (stab {cb_voice.settings(c)['stability']}): {cb_voice.direct_line(c, shot=s)}", flush=True)
            imgs = [os.path.basename(kf)] + [os.path.basename(_anchor(c)) for c in chars if _anchor(c)]
            print(f"  IMAGES: {imgs}", flush=True)
            print(f"  REF2VID PROMPT:\n  {prompt}", flush=True)
            continue
        if not os.path.exists(kf):
            print(f"  {code}: SKIP — keyframe missing at {kf} (run the keyframe gate first)", flush=True)
            continue
        track = cb_voice.build_dialogue_track(s, out=f"vo_{episode}_{code}.mp3")
        imgs = ([prev_frame] if prev_frame and os.path.exists(prev_frame) else []) + [kf] + [_anchor(c) for c in chars if _anchor(c)]
        audio = [track["track"]] if track else None
        out = f"{episode}_{code}_{slug}.mp4"   # POST (cb_post._clips) + regen expect this exact name — no _clip suffix
        say = " | ".join(f"{l['character']}: {l['text']}" for l in track["lines"]) if track else "(silent)"
        _dur = int(s.get("durationSec") or s.get("duration") or 11); _dur = max(8, min(15, _dur))  # match cb_beats (was a stale 'duration' key → 6s default)
        print(f"  {code}: ref2vid | imgs={len(imgs)} | audio={'yes' if audio else 'silent'} | {_dur}s"
              f"\n         {say}", flush=True)
        try:
            cb_gen.generate_video_seedance_ref(prompt, imgs, audio_urls=audio,
                                               duration=_dur, out=out)
            clips.append(f"media/{out}")
            print(f"         -> {out}", flush=True)
        except Exception as e:
            print(f"  {code}: FAILED — {str(e)[:200]} (continuing with the rest)", flush=True)
    if clips and not dry:
        stitch(clips, f"media/{episode}_S{scene_num}_dialogue.mp4")
    print("=== DIALOGUE DRIVER DONE ===", flush=True)
    return clips

def stitch(clips, out):
    lst = cb_gen.MEDIA / "_concat.txt"
    lst.write_text("".join(f"file '{os.path.abspath(c)}'\n" for c in clips))
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", out],
                   check=True, capture_output=True)
    print(f"  stitched {len(clips)} clips -> {out}", flush=True)
    return out

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    pkg = sys.argv[1]; scene = sys.argv[2]
    ep = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("-") else "Ep1"
    codes = None
    for a in sys.argv[4:]:
        if a and not a.startswith("-"):
            codes = a.split(",")
    run(pkg, scene, ep, codes, dry=("--dry" in sys.argv))
