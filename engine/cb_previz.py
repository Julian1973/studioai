#!/usr/bin/env python3
"""cb_previz.py — GATE 1.6, THE PREVIZ REEL (2026-07-08, Story/Editorial + Pipeline TD panel finding).

Something fluid was getting locked as final too early: Gate 1 signs a schema-valid storyboard with no
audio and no visuals, and the very next real generation call (Gate 2a's plate) already costs money. This
stage sits between the two — near-zero cost, built entirely from cheap-tier calls and stills — so Julian
can HEAR the dialogue's timing and comedic rhythm before a single expensive render fires, and revise a
line through the EXISTING beat editor if it doesn't land.

This is NOT a final take of anything: the voice here is scratch (Flash tier, not the acted V3 performance
Gate 3 fires), and the picture is either a placeholder card or whatever keyframe happens to already exist
(normally none — Gate 1.6 runs BEFORE Gate 2b). Nothing this module produces is ever treated as an
approved artifact for a later gate; `assemble_scene_previz`'s own output only ever feeds the Gate-1.6
review screen.

NOTE ON NUMBERING: this is "Gate 1.6", not "Gate 1.5" — "Gate 1.5" is already the established name for
Director's Eye (cb_director_eye.py), an unrelated, automatic, flag-only bible/craft review that fires at
the END of every Gate-1 authoring pass and carries no lock state of its own (it is not in GATE_SEQ). This
stage is chronologically NEXT: Director's Eye (1.5) runs automatically during authoring, before Julian
ever signs Gate 1; this stage is a human sign-off that fires AFTER Gate 1 is signed and BEFORE Gate 2a.

    python3 cb_previz.py <package.json> <sceneNumber> [episode=Ep1]
"""
import json, os, subprocess, textwrap
import cb_gen, cb_voice, cb_scene, cb_post, cb_preflight, cb_beats
from cb_segprompt import HANDLE_TOTAL

PREVIZ_VOICE_MODEL = "eleven_flash_v2_5"   # cheap scratch tier, roughly half V3's per-character cost — this
                                            # is disposable timing/rhythm audio, never a final acted take


def _beats_for_scene(pkg_path, scene_num):
    # FIXED 2026-07-12 (full-codebase audit continued): this used to reimplement the load-package-and-filter-
    # by-sceneNumber pattern independently (its own json.load + str(sceneNumber)-equality list comprehension)
    # instead of calling cb_beats._load_scene_beats — the shared helper built the same 2026-07-08 session
    # specifically to deduplicate this exact pattern (its own docstring: "never change this matching logic
    # without re-checking every caller"). A future correction to that shared matching logic would have
    # silently never reached this independent copy. Now delegates the load+filter step to it and applies only
    # this function's own natural-sort on top.
    _, beats = cb_beats._load_scene_beats(pkg_path, scene_num)
    # Natural sort on the trailing beat number (cb_preflight._beat_sort_key) — a lexicographic sort on the raw
    # code string would misorder any scene with 10+ beats ('1.B10' < '1.B2'); the same bug class found and
    # fixed in cb_beats.py/cb_director.py this session (rule 11 sweep).
    beats.sort(key=lambda b: cb_preflight._beat_sort_key(b.get("beatCode") or b.get("shotCode") or ""))
    return beats


def _cut_dialogue_pairs(beat):
    """[(speaker, text, is_chorus)] for each cut carrying dialogue.

    A normal cut is parsed from the existing "SPEAKER: text" convention cuts[].dialogue already uses
    everywhere else in this pipeline (cb_voice, cb_segprompt). A group_chorus cut is special-cased FIRST,
    before that generic split: its label ("ALL:", "CHORUS:", ...) never resolves to a real character
    (cb_voice._char("All").get("voiceId") is None), which used to make the whole line silently vanish from
    the previz reel (the "if not vid: continue" skip in scratch_vo_for_beat) instead of just being scratched
    — defeating the entire point of previz, hearing a line's timing/rhythm before a paid render (2026-07-08
    audit finding, real: production beat 8.B3's "ALL: Welcome to Crystal Cove! We're the Crystal Bears!").
    Here the label is stripped (via cb_voice._cut_segments, the same parser cb_voice's own group_chorus
    branch uses) and ONE real, voiceId-bearing character is picked from the cut's own chorusMembers (or the
    beat's speakers — the same two fields cb_voice._resolve_turns/_chorus already read for the real render
    path) so the line's timing survives in the reel, scratched in that single character's cheap voice. This
    is NEVER a substitute for the real multi-voice chorus mix cb_voice._chorus builds at Gate 3 — it exists
    solely so the line isn't silently missing from a disposable timing artifact."""
    pairs = []
    for c in (beat.get("cuts") or []):
        dlg = str(c.get("dialogue") or "").strip()
        if not dlg:
            continue
        if (c.get("voiceTreatment") or "").strip() == "group_chorus":
            line = " ".join(t for _, t in cb_voice._cut_segments(dlg) if t)
            if not line:
                continue
            members = c.get("chorusMembers") or beat.get("speakers") or []
            chosen = next((m for m in members if cb_voice._char(m).get("voiceId")), None)
            if not chosen:
                print(f"  (previz VO skipped — no voiceId chorus member for group_chorus cut in "
                      f"{beat.get('beatCode')}; chorusMembers={members!r})", flush=True)
                continue
            print(f"  (chorus line — scratched in {chosen}'s voice for timing only)", flush=True)
            pairs.append((chosen, line, True))
            continue
        # FIXED 2026-07-12 (full-codebase audit continued): this branch used to parse dialogue with a naive
        # dlg.split(":", 1) — a single split, so a cut authored with TWO speakers packed into one dialogue
        # field (a real, supported shape elsewhere in this pipeline — cb_voice._resolve_turns's own BEAT
        # branch already handles it via cb_voice._cut_segments) would silently drop every speaker after the
        # first and voice their text in the first speaker's voice, literal "ZENNY:" label and all — the exact
        # general-case version of the bug the group_chorus branch above was already special-cased against.
        # Now uses the same shared parser, one (label, text, False) tuple per parsed segment.
        for label, text in cb_voice._cut_segments(dlg):
            if label and text:
                pairs.append((label, text, False))
    return pairs


def scratch_vo_for_beat(beat, episode, tmp_dir):
    """One cheap Flash-tier TTS call PER DIALOGUE-BEARING CUT (never one merged call for the whole beat) so a
    back-and-forth exchange (e.g. 1.B2's Fuzzby/Zenny volley) keeps each line in its own speaker's voice —
    the whole point of previz is judging comedic TIMING, which a single flattened voice would hide. Returns
    the merged mp3 path, or None for a wordless beat (never a fallback voice — silence is the correct read
    for a beat with nothing to say)."""
    pairs = _cut_dialogue_pairs(beat)
    if not pairs:
        return None
    code = (beat.get("beatCode") or beat.get("shotCode") or "beat").replace(".", "_")
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "media", "_previz"), exist_ok=True)
    abs_clips = []
    for i, (speaker, text, is_chorus) in enumerate(pairs):
        # A chorus pair's "speaker" is already a resolved, voiceId-bearing canonical character (chosen in
        # _cut_dialogue_pairs from chorusMembers/beat.speakers) — running it back through _resolve_speaker
        # is unnecessary and, for a name resolvable but ambiguous, could re-fuzzy-match it away from the
        # exact member that was already validated to have a voiceId.
        canon_name = speaker if is_chorus else cb_voice._resolve_speaker(speaker, beat)
                                                                  # "FUZZBY" -> "Fuzzby", same resolver cb_voice
                                                                  # itself uses everywhere else — a raw ALL-CAPS
                                                                  # cut label never matches characters.json directly
        cc = cb_voice._char(canon_name)
        vid = cc.get("voiceId")
        if not vid:
            print(f"  (previz VO skipped — no voiceId for '{speaker}' in {beat.get('beatCode')})", flush=True)
            continue
        rel_name = f"_previz/{episode}_{code}_vo{i}.mp3"   # relative to cb_gen.MEDIA (engine/media/)
        try:
            full_path = cb_gen.eleven_tts(text, vid, model_id=PREVIZ_VOICE_MODEL, out=rel_name, stability=0.40)
        except Exception as e:
            print(f"  (previz VO call failed for {beat.get('beatCode')} cut {i}: {str(e)[:160]})", flush=True)
            continue
        if os.path.exists(full_path):
            abs_clips.append(full_path)
    if not abs_clips:
        return None
    if len(abs_clips) == 1:
        return abs_clips[0]
    concat_list = os.path.join(tmp_dir, f"{code}_vo_concat.txt")
    with open(concat_list, "w") as f:
        for c in abs_clips:
            f.write(f"file '{c}'\n")
    merged = os.path.join(tmp_dir, f"{code}_vo_merged.mp3")
    r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", merged],
                        capture_output=True, text=True)
    # FIXED 2026-07-12 (full-codebase audit continued): this call used to run without capturing or checking
    # its result at all — a failed concat merge (a malformed mp3 from a flaky TTS response, a codec mismatch,
    # an ffmpeg env issue) silently fell through to "abs_clips[0]" with zero printed diagnostic, dropping every
    # dialogue line after the first with no signal anything went wrong. assemble_beat_clip a few lines below
    # already got this exact hardening (returncode + existence check, a beat-identified error print) for the
    # same class of "trust ffmpeg blindly" risk — this sibling VO-merge step was never swept for the same fix.
    if r.returncode or not os.path.exists(merged):
        print(f"  previz VO merge ERROR ({code}) — falling back to the first line only:",
              (r.stderr or "")[-400:], flush=True)
        return abs_clips[0]
    return merged


def placeholder_frame(beat, episode, out_png):
    """A plain title card for a beat with no keyframe yet — via PIL, reusing cb_post's own already-solved
    font-fallback helpers verbatim (never ffmpeg drawtext, which this codebase already hit and fixed a real
    font-availability risk for once, in burn_review_overlay)."""
    from PIL import Image, ImageDraw
    big, small = cb_post._pil_font(54), cb_post._pil_font(30)
    img = Image.new("RGB", (1280, 720), (20, 18, 34))
    dr = ImageDraw.Draw(img)
    code = beat.get("beatCode") or beat.get("shotCode") or "?"
    story = str(beat.get("storyBeat") or "(no storyBeat authored yet)")
    dr.text((64, 280), f"BEAT {code}", font=big, fill=(232, 226, 248))
    for i, line in enumerate(textwrap.wrap(story, width=58)[:7]):
        dr.text((64, 366 + i * 36), line, font=small, fill=(182, 176, 204))
    img.save(out_png)
    return out_png


def assemble_beat_clip(beat, episode, tmp_dir):
    """One beat's previz clip: the real keyframe if Gate 2b somehow already ran, else a placeholder card —
    held for HANDLE_TOTAL or the scratch VO's own duration (whichever is longer), muxed with that VO (or
    silence for a wordless beat, so every clip has an audio stream cb_post.assemble_picture's concat needs)."""
    code = (beat.get("beatCode") or beat.get("shotCode") or "beat").replace(".", "_")
    kf = cb_scene.beat_frame_path(beat, episode)
    if os.path.exists(kf):
        frame = kf
    else:
        frame = os.path.join(tmp_dir, f"{code}_placeholder.png")
        placeholder_frame(beat, episode, frame)

    vo = scratch_vo_for_beat(beat, episode, tmp_dir)
    # FIXED 2026-07-12 (full-codebase audit, duplication finding): this used to hand-roll its own ffprobe
    # "format=duration" probe — cb_post._dur() already does exactly this, and this module already imports
    # cb_post at module level for a different function (assemble_scene_previz's own concat call).
    vo_dur = cb_post._dur(vo) if vo else 0.0
    duration = max(float(HANDLE_TOTAL), vo_dur + 1.0)

    out_clip = os.path.join(tmp_dir, f"{code}_previz.mp4")
    if vo:
        cmd = ["ffmpeg", "-y", "-loop", "1", "-i", frame, "-i", vo,
               "-t", str(duration), "-r", "24",
               "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:-1:-1,format=yuv420p",
               "-af", f"apad=whole_dur={duration}",
               "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "128k", out_clip]
    else:
        cmd = ["ffmpeg", "-y", "-loop", "1", "-i", frame,
               "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
               "-t", str(duration), "-r", "24",
               "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:-1:-1,format=yuv420p",
               "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "128k", out_clip]
    r = subprocess.run(cmd, capture_output=True, text=True)
    # A failed ffmpeg call used to still return out_clip's path regardless — assemble_scene_previz then fed that
    # nonexistent/broken file straight into cb_post.assemble_picture's concat, which either crashes on a missing
    # input or silently drops the beat from the middle of the reel with no clear signal which one (2026-07-08
    # audit finding). Return None on a real failure so the caller can skip it and say so.
    if r.returncode or not os.path.exists(out_clip):
        print(f"  previz clip ERROR ({code}):", r.stderr[-400:], flush=True)
        return None
    return out_clip


def craft_score_for_scene(pkg_path, scene_num, episode="Ep1", log=print):
    """THE PIXAR-CRAFT GATE, WIRED INTO GATE 1.6 (2026-07-14, Julian: "I want you... to ensure that we
    deliver a world-class, five-star Pixar animation that makes people laugh, makes people cry"). Runs the
    SAME dual-read craft judge (cb_craft.score_scene_craft) this project already built and proved (rule 48)
    — but that judge had ZERO live callers anywhere in the pipeline until now, confirmed by grep before this
    was written. Gate 1.6 is exactly the right choke point: it already exists as the cheap checkpoint before
    Gate 2a's first real, paid render, and a human is ALREADY about to watch the reel and judge it — this
    puts the same Pixar-caliber rubric (character voice, comedy craft, emotional/North-Star fidelity,
    fidelity-law traceability, the cold Pixar-benchmark verdict) right next to that moment instead of leaving
    it a manual-only CLI tool nobody remembers to run.

    ONE scene-level call (two LLM reads inside it — review + skeptic, per score_scene_craft's own anti-
    grade-inflation design), never per-beat — the previz reel already assembles once per scene, so this
    costs exactly one craft judgment per Gate-1.6 review, not one per beat fired.

    FAIL-SOFT BY DESIGN, matching this whole pipeline's own established convention for optional LLM
    enrichment (Director's Pass, keyframe QA, clip QA all degrade the same way): a scoring failure — quota,
    network, a malformed response — is caught, logged, and returns None. It NEVER blocks or breaks the
    previz build itself; the reel is the thing Julian must be able to watch regardless of whether the judge
    call succeeded. This is advisory information alongside the reel, never a gate of its own — rule 28's
    reserved verdict ("does it fly, is it funny") stays Julian's, exactly as cb_craft.py's own docstring
    already states; this function surfaces a second opinion, it does not replace his.

    Writes media/{episode}_Scene{N}_previz.craft.json (the same sidecar-per-artifact convention as every
    other QA check in this pipeline) and returns the result dict, or None on failure."""
    try:
        # FIXED (2026-07-14, full-pipeline verification audit): _load_scene_beats(pkg_path, scene_num)
        # returns (d, beats) where `d` is the WHOLE parsed package dict (title/episode/logline/.../scenes/
        # beats/northStarAnswers), never a single scene object — this line was silently binding `scene` to
        # the whole package, so every scene.get('sceneNumber'/'name'/'pillar'/'emotionalCore') call inside
        # _serialize_scene (cb_craft.py) came back empty, and the "compare against the original script"
        # section silently lost its scene to key against too. The real per-scene dict lives in d["scenes"],
        # keyed by sceneNumber — resolved explicitly here instead.
        pkg, beats = cb_beats._load_scene_beats(pkg_path, scene_num)
        scene = next((s for s in (pkg.get("scenes") or []) if str(s.get("sceneNumber")) == str(scene_num)), None)
        if not scene or not beats:
            log(f"  craft score: no scene/beats found for {episode} scene {scene_num} — skipped")
            return None
        import cb_craft
        characters = cb_craft._load_characters()
        script_scenes, _ = cb_preflight._load_script_scenes(episode, {"characters": characters}, log=log)
        result = cb_craft.score_scene_craft(scene, beats, characters, script_scenes or [], log=log)
        out_path = f"media/{episode}_Scene{scene_num}_previz.craft.json"
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2)
        log(f"  craft score -> {out_path}")
        for crit, c in result["criteria"].items():
            gap_note = f" (review/skeptic disagree by {c['agreement_gap']})" if c["agreement_gap"] >= 2 else ""
            log(f"    {crit}: {c['score']}/5{gap_note} — {c['verdict'][:140]}")
        log(f"    one line to fix first: {result['review'].get('oneLineToFixFirst', '')[:200]}")
        return result
    except Exception as e:
        log(f"  craft score: UNAVAILABLE ({e!r}) — advisory only, the previz reel itself is unaffected")
        return None


def assemble_scene_previz(pkg_path, scene_num, episode="Ep1"):
    """Builds every beat's previz clip in scene order, then hard-cuts them together with
    cb_post.assemble_picture (reused verbatim — same join style previz wants: instant cut, held tail).
    Output: media/{episode}_Scene{N}_previz.mp4 — the one file Julian watches at Gate 1.6.

    CORRECTED (2026-07-14, full-pipeline verification audit): this function used to ALSO call
    craft_score_for_scene right after assembling the reel — but cb_pipeline.previz_reel (the real GATE 1.6
    entry point every CLI/Studio-UI fire actually goes through) ALREADY calls craft_score_for_scene itself,
    right after calling this function. The result: every real Gate-1.6 fire ran the (real-cost, two-LLM-call)
    craft judge TWICE, with the second write silently clobbering the first — the "had ZERO live callers until
    now" comment on cb_pipeline.previz_reel's own call site was already false the moment it was written. This
    function now does assembly ONLY; craft_score_for_scene lives solely at the orchestration level
    (cb_pipeline.previz_reel), matching the module's own test (test_cb_previz.py's assemble-then-craft-score
    ordering test targets that call site, not this one). Direct standalone CLI use (this module's own
    __main__) now calls craft_score_for_scene explicitly itself, so that path still gets a score too."""
    beats = _beats_for_scene(pkg_path, scene_num)
    if not beats:
        print(f"PREVIZ: no beats for {episode} scene {scene_num}", flush=True)
        return None
    tmp_dir = f"media/_previz/{episode}_scene{scene_num}"
    os.makedirs(tmp_dir, exist_ok=True)
    os.makedirs("media/_previz", exist_ok=True)
    clips = []
    for b in beats:
        code = b.get("beatCode") or b.get("shotCode") or "?"
        print(f"  previz: {code}...", flush=True)
        clip = assemble_beat_clip(b, episode, tmp_dir)
        if clip:
            clips.append(clip)
        else:
            print(f"  previz: {code} SKIPPED — clip build failed (see error above); left out of the reel", flush=True)
    if not clips:
        print(f"PREVIZ: no clips built for {episode} scene {scene_num} — nothing to assemble", flush=True)
        return None
    out = f"media/{episode}_Scene{scene_num}_previz.mp4"
    cb_post.assemble_picture(clips, out)
    print(f"PREVIZ -> {out} ({len(clips)}/{len(beats)} beats — scratch VO + placeholder/keyframe cards, near-zero cost)",
          flush=True)
    return out


if __name__ == "__main__":
    import sys
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    pkg = sys.argv[1] if len(sys.argv) > 1 else None
    scene = sys.argv[2] if len(sys.argv) > 2 else None
    episode = sys.argv[3] if len(sys.argv) > 3 else "Ep1"
    if not pkg or not scene:
        print("usage: python3 cb_previz.py <package.json> <sceneNumber> [episode=Ep1]")
        sys.exit(1)
    if assemble_scene_previz(pkg, scene, episode=episode):
        print("  running the Pixar-craft judge (cb_craft.score_scene_craft) for this scene...", flush=True)
        craft_score_for_scene(pkg, scene, episode)
