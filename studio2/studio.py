#!/usr/bin/env python3
"""
CRYSTAL BEARS STUDIO 2 — the whole engine in one file.
Script -> NB2 keyframe -> Seedance 2 -> Julian's eye. Nothing else.

STATUS (added 2026-07-08, software-wide fix batch — see CLAUDE.md's studio2 note): this is a SEPARATE,
STANDALONE PROTOTYPE — its own canon.yaml/studio.py/scene.html, never imported by engine/ or cb-studio/,
and not part of the live production path. The live pipeline is engine/cb_*.py fired through cb-studio/
serve.py, governed by CLAUDE.md/PRODUCTION_DOCTRINE.md/GATE3_ANIMATION_DOCTRINE.md/MANIFEST.md — those
documents, not this file's own docstring, are the source of truth for word budgets, prompt shape and every
other rule. This module's own WORD_CAP/TARGET/STORY_CAP (280/250/80, below) is this prototype's OWN
regime — it does not reflect and is not overridden by engine/cb_preflight.py's WORD_BUDGET_BLOCK/TARGET
(650/400). Nothing here is deleted or altered in behavior; this header only prevents a future session from
mistaking this for the live path.

THE SCARS, AS LAW (each line below exists because something specific went wrong):
  1. One canon file. The UI, the engine, everyone reads canon.yaml. Never two stores.
  2. The engine is the only prompt author. No prompt is ever hand-written or patched.
  3. Prompts are SHORT. Hard cap 250 words, story <=80. The first two renders ever
     made were the best because they were short. Long prompts render obedience.
  4. Character = one movement line from canon. No poses, no negations, no appearance,
     no retake notes. The reference image is the identity; the words are the energy.
  5. Dialogue words NEVER appear in a prompt. The voice is a performed V3 track fired
     in as @Audio1. It drives generation. It is never added in post.
  6. A scene opener fires with exactly: keyframe + turnarounds + plate (+ audio).
     Nothing inherited. A relay beat opens from the APPROVED predecessor's settle
     frame + its trimmed tail as motion reference. Cuts, not freezes.
  7. Rejected takes are dead. Approval is recorded data; harvest and resume read
     approval status, never file existence.
  8. One render per fire. One retry on hard failure. Then stop and think.
  9. A blank is an error, never a fallback.
 10. Julian's eye is the final gate on every take. The machine never advances past it.
"""
import hashlib, json, os, re, shutil, subprocess, sys, time, urllib.request
from datetime import datetime
from pathlib import Path

import yaml  # pip install pyyaml

ROOT = Path(__file__).parent
CANON = yaml.safe_load((ROOT / "canon.yaml").read_text())
TAKES = ROOT / "takes"

# ---- render endpoints (fal queue API). Swap = edit two strings. -------------
FAL_KEY = os.environ.get("FAL_KEY", "")
SEEDANCE = "fal-ai/bytedance/seedance-2.0/reference-to-video"  # Julian's Loop: anchor + turnarounds + @Audio1
HANDLE = 1  # extra second on every render, trimmed at stitch for clean cuts
NB2 = "fal-ai/nano-banana-2"

WORD_CAP, TARGET, STORY_CAP = 280, 250, 80
SPEED_WORDS = re.compile(r"\b(fast|quickly|rapidly|swiftly|speedily)\b", re.I)


# ---------------------------------------------------------------- helpers ---
def die(msg):  sys.exit(f"BLOCK: {msg}")

def words(s):  return len(s.split())

def load_scene(ep_file):
    ep = yaml.safe_load((ROOT / ep_file).read_text())
    scene = CANON["scenes"][ep["scene"]]
    cast = {c: CANON["characters"][c] for c in ep["cast"]}
    return ep, scene, cast

def beat_by_id(ep, beat_id):
    for b in ep["beats"]:
        if b["id"] == beat_id:
            return b
    die(f"beat {beat_id} not found")

def take_dir(beat_id, n=None):
    base = TAKES / beat_id.replace(".", "_")
    if n is None:  # next take number
        base.mkdir(parents=True, exist_ok=True)
        n = 1 + max([int(p.name.split("_")[1]) for p in base.glob("take_*")] or [0])
    return base / f"take_{n:03d}"

def latest_take(beat_id):
    base = TAKES / beat_id.replace(".", "_")
    takes = sorted(base.glob("take_*")) if base.exists() else []
    return takes[-1] if takes else None

def status_of(take):
    f = take / "approval.json"
    return json.loads(f.read_text())["status"] if f.exists() else "pending"

def approved_take(beat_id):
    base = TAKES / beat_id.replace(".", "_")
    if not base.exists():
        return None
    for t in sorted(base.glob("take_*"), reverse=True):
        if status_of(t) == "approved":
            return t
    return None


# ---------------------------------------------------------------- compile ---
def _refs_line(names, prev_approved):
    """Declare what every uploaded reference image actually IS, in the prompt text itself —
    the model is never handed images with no acknowledgement of their job (Julian's ruling,
    2026-07-06: 'there's nothing in there about the reference images'). Kept terse — every
    word here is word-budget spent on plumbing, not story."""
    point = ("@图1 previous approved settle — carry forward, new angle."
             if prev_approved else "@图1 signed scene keyframe — begin here.")
    chars = " ".join(f"@图{i+2} {n.title()} match exactly." for i, n in enumerate(names))
    return point + " " + chars

def compile_prompt(ep, scene, cast, beat, prev_approved):
    """ARCHIVE RECIPE (2026-06-22, the best takes ever made): one identity line,
    shot-listed cuts with dialogue written in, one closer. ~140 words. Nothing else.

    EXTENDED per Julian's ruling (2026-07-06 — character truth must be cross-referenced,
    not thin): the per-character `dna` line is pulled from canon.yaml — itself sourced
    verbatim/condensed from engine/config/characters.json's real bible fields (see canon.yaml's
    own `# dna sourced from...` comments) — never invented here. The reference images are also
    named explicitly in the prompt text; a model is never handed anchors with no acknowledgement."""
    if "shots" in beat:
        text = " ".join(beat["shots"].split())
        for w in CANON["banned_words"]:
            if re.search(rf"\b{w}\b", text, re.I): die(f"banned word '{w}' in {beat['id']}")
        if re.search(r'["\u201c\u201d]', text):
            die(f"quoted dialogue in {beat['id']} — @Audio1 carries the words; place the moment, never write it")
        names = list(cast)
        size_handle = "; ".join(f"{n.title()} = {'BIGGER' if i == 0 else 'SMALLER'} bumblebee "
                                 f"({'male' if n == 'fuzzby' else 'female'})" for i, n in enumerate(names)) + "."
        dna_line = "  ".join(f"{n.title()}: {cast[n]['dna']}." for n in names)
        p = ("Multi-shot sequence with clean cuts between shots. " + size_handle + " "
             + " ".join(ep["identity"].split()) + " "
             + _refs_line(names, prev_approved) + " "
             + dna_line + " "
             + "@Audio1 is the only source of all vocal sound; animate mouths and performance to it. "
             + text + " " + " ".join(ep["closer"].split()))
        if words(p) > WORD_CAP: die(f"{beat['id']}: {words(p)} words (cap {WORD_CAP})")
        return p
    return _compile_v5(ep, scene, cast, beat, prev_approved)

def _compile_v5(ep, scene, cast, beat, prev_approved):
    """Canon in, prompt out. Short, sourced, checked. The only prompt author."""
    story = " ".join(beat["story"].split())
    if "physical" in beat:
        story += " " + " ".join(f"{v.strip()}" for v in beat["physical"].values())
    if words(story) > STORY_CAP:
        die(f"{beat['id']} story is {words(story)} words (cap {STORY_CAP}) — cut adjectives, keep actions")
    for w in CANON["banned_words"]:
        if re.search(rf"\b{w}\b", story, re.I):
            die(f"banned word '{w}' in {beat['id']} — it is the crystal cove meadow")
    if re.search(r'["\u201c\u201d]', story):
        die(f"quoted dialogue in {beat['id']} story — words live only in the V3 track (Law 5)")
    if SPEED_WORDS.search(story):
        die(f"speed adverb in {beat['id']} — write named actions, not speed")

    names = list(cast)  # e.g. ["fuzzby", "zenny"]
    refs = [f"@图1 opening keyframe — begin on this exact composition."] if not prev_approved else [
        "@图1 previous approved settle — carry the characters, their marks and the light; open on a fresh angle nearby.",
        "@Video1 — previous tail, motion energy only, never its framing.",
    ]
    for i, n in enumerate(names):
        refs.append(f"@图{i+2} {n.title()} — match exactly.")
    refs.append(f"@图{len(names)+2} scene plate — lighting, palette, texture throughout.")
    refs.append("@Audio1 — sole source of all vocal sound; animate mouths and full performance to it.")

    dna = "  ".join(f"{n.title()}: {cast[n]['dna']}." for n in names)

    prompt = "\n".join([
        "15s, 16:9, 3D CGI beat.",
        CANON["style"] + ".",
        "\n".join(refs),
        dna,
        story,
        f"Ambience: {scene['ambience']}.",
        "16:9, 24fps, smooth cinematic motion, shallow depth of field.",
        f"Negative: {CANON['negatives']}.",
    ])
    if words(prompt) > WORD_CAP:
        die(f"{beat['id']} compiles to {words(prompt)} words (cap {WORD_CAP})")
    return prompt


def gather(scene, cast, beat, prev_approved):
    """Assemble the reference files for this fire. A blank is an error.
    Julian's ruling: the scene (keyframe or re-mint) goes in FIRST, then the two character
    turnarounds, every beat — opener included, not just relays."""
    imgs, vid = [], None
    if prev_approved:
        rm = prev_approved / "remint.png"
        if not rm.exists(): die("previous approved take has no re-mint — approve runs it; check NB2")
        imgs.append(rm)
    else:
        kf = ROOT / scene["keyframe"]
        if not kf.exists():
            die(f"scene keyframe missing ({kf}) — run `keyframe` and get Julian's sign-off first")
        imgs.append(kf)
    for n in cast: imgs.append(ROOT / cast[n]["ref"])   # turnarounds ride every beat, opener and relay alike
    audio = ROOT / beat["audio"]
    if not audio.exists(): die(f"V3 track missing for {beat['id']}: {audio} — the voice fires IN")
    return imgs, vid, audio


# ------------------------------------------------------------------- fire ---
def fal_call(model, payload):
    if not FAL_KEY: die("FAL_KEY not set")
    req = urllib.request.Request(
        f"https://queue.fal.run/{model}",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"})
    sub = json.loads(urllib.request.urlopen(req).read())
    status_url = sub["status_url"]; resp_url = sub["response_url"]
    while True:
        time.sleep(8)
        st = json.loads(urllib.request.urlopen(urllib.request.Request(
            status_url, headers={"Authorization": f"Key {FAL_KEY}"})).read())
        if st["status"] == "COMPLETED":
            return json.loads(urllib.request.urlopen(urllib.request.Request(
                resp_url, headers={"Authorization": f"Key {FAL_KEY}"})).read())
        if st["status"] in ("FAILED", "ERROR"):
            die(f"render failed: {st}")

def upload(path):
    """fal file upload; returns a URL. (Uses fal storage endpoint.)"""
    import mimetypes
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    req = urllib.request.Request(
        "https://rest.fal.ai/storage/upload", data=path.read_bytes(),
        headers={"Authorization": f"Key {FAL_KEY}", "Content-Type": mime})
    return json.loads(urllib.request.urlopen(req).read())["url"]

def fire(ep_file, beat_id):
    ep, scene, cast = load_scene(ep_file)
    beat = beat_by_id(ep, beat_id)
    idx = ep["beats"].index(beat)
    prev = approved_take(ep["beats"][idx-1]["id"]) if idx else None
    if idx and not prev:
        die(f"predecessor {ep['beats'][idx-1]['id']} has no APPROVED take — rejected footage never anchors")
    prompt = compile_prompt(ep, scene, cast, beat, prev)
    imgs, vid, audio = gather(scene, cast, beat, prev)

    t = take_dir(beat_id); t.mkdir(parents=True)
    (t / "prompt.txt").write_text(prompt)          # the prompt AS FIRED, forever
    print(f"— {beat_id} · {words(prompt)} words · {'relay' if prev else 'opener'} —\n{prompt}\n")

    payload = {"prompt": prompt, "image_urls": [upload(p) for p in imgs],
               "audio_urls": [upload(audio)],
               "duration": beat.get("duration", 15) + HANDLE, "aspect_ratio": "16:9",
               "resolution": "720p", "generate_audio": False}
    out = fal_call(SEEDANCE, payload)
    url = out["video"]["url"] if "video" in out else out["videos"][0]["url"]
    urllib.request.urlretrieve(url, t / "clip.mp4")
    (t / "meta.json").write_text(json.dumps({
        "fired": datetime.now().isoformat(), "beat": beat_id,
        "prompt_sha": hashlib.sha256(prompt.encode()).hexdigest()[:16],
        "audio_sha": hashlib.sha256(audio.read_bytes()).hexdigest()[:16],
        "refs": [p.name for p in imgs]}))
    dur = float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0", t/"clip.mp4"]).strip())
    if not 13 <= dur <= 17: print(f"WARN: duration {dur:.1f}s — check before reviewing")
    print(f"LANDED -> {t/'clip.mp4'}\nWatch it. Then: approve {beat_id}  |  reject {beat_id} \"one sentence\"")

def keyframe(ep_file):
    """Generate the scene's single opening keyframe with NB2. Julian signs it."""
    _, scene, cast = load_scene(ep_file)
    prompt = (CANON["style"] + ". " + scene["keyframe_prompt"] +
              " Characters exactly as their reference images. 16:9, centre-safe. No text.")
    payload = {"prompt": prompt,
               "image_urls": [upload(ROOT / c["ref"]) for c in cast.values()] +
                             [upload(ROOT / scene["plate"])]}
    out = fal_call(NB2, payload)
    url = out["images"][0]["url"] if "images" in out else out["image"]["url"]
    dest = ROOT / scene["keyframe"]; dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    print(f"Keyframe -> {dest}. Julian looks at it before anything fires.")


# ---------------------------------------------------- approve / harvest -----
def approve(beat_id, ep_file="ep1_s1.yaml"):
    t = latest_take(beat_id) or die(f"no take for {beat_id}")
    (t / "approval.json").write_text(json.dumps(
        {"status": "approved", "by": "julian", "at": datetime.now().isoformat()}))
    _, _, cast = load_scene(ep_file)
    harvest(t, cast)
    page(ep_file)
    print(f"{beat_id} APPROVED and harvested. Next beat may fire.")

def reject(beat_id, reason, ep_file="ep1_s1.yaml"):
    t = latest_take(beat_id) or die(f"no take for {beat_id}")
    (t / "approval.json").write_text(json.dumps(
        {"status": "rejected", "by": "julian", "reason": reason, "at": datetime.now().isoformat()}))
    page(ep_file)
    print(f"{beat_id} REJECTED ({reason}). This take is dead — fix the beat's story line, fire again.")

def harvest(t, cast=None):
    """Julian's Loop: last frame -> NB2 re-mint (turnarounds as identity anchors) -> next keyframe."""
    clip = t / "clip.mp4"
    dur = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", clip]).strip())
    subprocess.run(["ffmpeg", "-v", "error", "-ss", str(dur-0.05), "-i", clip,
                    "-frames:v", "1", str(t / "last_frame.png")], check=True)
    refs = [upload(t / "last_frame.png")] + [upload(ROOT / c["ref"]) for c in (cast or {}).values()]
    out = fal_call(NB2, {"prompt": "Restore this exact frame to pristine, crisp quality. "
        "Characters exactly as their reference images. Change nothing about pose, framing, "
        "composition or lighting.", "image_urls": refs})
    url = out["images"][0]["url"] if "images" in out else out["image"]["url"]
    urllib.request.urlretrieve(url, t / "remint.png")


# ---------------------------------------------------------------- walk ------
def walk(ep_file):
    """Fire the next unapproved beat, then stop for Julian. Run again after approval."""
    ep, _, _ = load_scene(ep_file)
    for b in ep["beats"]:
        if not approved_take(b["id"]):
            t = latest_take(b["id"])
            if t and status_of(t) == "pending":
                die(f"{b['id']} is waiting for your eye: {t/'clip.mp4'}")
            fire(ep_file, b["id"]); return
    print("Scene complete — every beat approved. Stitch when ready.")

def stitch(ep_file, out="scene.mp4"):
    """Join approved clips, trimming each settle (last 2s) so cuts land on motion."""
    ep, _, _ = load_scene(ep_file)
    parts = []
    for i, b in enumerate(ep["beats"]):
        t = approved_take(b["id"]) or die(f"{b['id']} not approved")
        clip = t / "clip.mp4"
        dur = float(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", clip]).strip())
        end = dur if i == len(ep["beats"]) - 1 else dur - HANDLE  # trim the cut handle
        cut = t / "cut.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", clip, "-t", str(end),
                        "-c:v", "libx264", "-c:a", "aac", cut], check=True)
        parts.append(cut)
    lst = ROOT / "concat.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", lst, "-c", "copy", ROOT / out], check=True)
    print(f"Scene -> {ROOT/out}")


def preflight(ep_file):
    ep, scene, cast = load_scene(ep_file)
    class _R: pass
    ok = True
    for i, b in enumerate(ep["beats"]):
        for label, prev in (("opener", None), ("relay", _R())):
            if i == 0 and label == "relay": continue
            if i > 0 and label == "opener": continue
            try:
                p = compile_prompt(ep, scene, cast, b, prev)
                n = words(p)
                note = "" if n <= TARGET else f" (over {TARGET} target)"
                print(f"PASS {b['id']} {label}: {n} words{note}")
            except SystemExit as e:
                print(f"FAIL {b['id']} {label}: {e}"); ok = False

    for n, c in cast.items():
        if not (ROOT / c["ref"]).exists(): print(f"MISS turnaround: {n}"); ok = False
    for k in ("plate", "keyframe"):
        if not (ROOT / scene[k]).exists(): print(f"MISS scene {k}: {scene[k]}"); ok = False
    print("PREFLIGHT " + ("GREEN — safe to walk" if ok else "RED — fix before any fire"))

# ------------------------------------------------------------- scene page ---
# Design system matched to the Episode 1 v2 Archive workflow page (same tokens, same layout
# language) per Julian's ruling: "I want the look and feel to be exactly the same." Live data,
# not a static snapshot — approval status, real audio, fired-vs-compiled prompts, all read fresh.
PAGE_CSS = """
@font-face {
  font-family: 'Display Slab';
  src: url(data:font/woff2;base64,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) format('woff2');
  font-weight: 900; font-display: swap;
}
@font-face {
  font-family: 'Body Sans';
  src: url(data:font/woff2;base64,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) format('woff2');
  font-weight: 400; font-display: swap;
}
@font-face {
  font-family: 'Label Sans';
  src: url(data:font/woff2;base64,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) format('woff2');
  font-weight: 700; font-display: swap;
}

:root {
  --ground: #14201a; --ground-2: #101a15; --surface: #1c2921; --surface-2: #223227;
  --line: #33473a; --crystal: #6fe0cf; --crystal-dim: #4a9c90; --pollen: #f0b542;
  --ink: #edf4ee; --ink-muted: #93a89b; --ink-faint: #6b8074; --flag: #e8785a;
}
* { box-sizing: border-box; }
html { background: var(--ground); }
body {
  margin: 0; background: var(--ground);
  background-image:
    radial-gradient(ellipse 900px 500px at 15% -5%, rgba(111,224,207,0.10), transparent 60%),
    radial-gradient(ellipse 700px 500px at 100% 10%, rgba(240,181,66,0.07), transparent 55%);
  color: var(--ink); font-family: 'Body Sans', -apple-system, sans-serif;
  font-size: 16px; line-height: 1.55; -webkit-font-smoothing: antialiased;
}
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
a { color: inherit; }
::selection { background: var(--crystal); color: #0c1512; }
.wrap { max-width: 920px; margin: 0 auto; padding: 0 24px 96px; }

.hero { padding: 56px 0 40px; border-bottom: 1px solid var(--line); }
.eyebrow {
  font-family: 'Label Sans', sans-serif; font-size: 11.5px; letter-spacing: 0.14em;
  text-transform: uppercase; color: var(--crystal); display: flex; align-items: center;
  gap: 10px; margin-bottom: 18px;
}
.eyebrow::before {
  content: ""; width: 7px; height: 7px; background: var(--crystal);
  box-shadow: 0 0 8px 1px rgba(111,224,207,0.7); transform: rotate(45deg); flex: none;
}
h1 {
  font-family: 'Display Slab', Georgia, serif; font-weight: 900; font-size: clamp(34px, 5.4vw, 54px);
  line-height: 1.04; letter-spacing: -0.01em; margin: 0 0 14px; text-wrap: balance;
}
h1 em { font-style: normal; color: var(--pollen); }
.hero-sub { max-width: 62ch; color: var(--ink-muted); font-size: 16.5px; margin: 0 0 28px; }
.hero-media { display: grid; grid-template-columns: 1.3fr 1fr; gap: 14px; }
.hero-shot {
  position: relative; border-radius: 10px; overflow: hidden; border: 1px solid var(--line);
  aspect-ratio: 16/9; background: var(--surface);
}
.hero-shot img, .hero-shot video { width: 100%; height: 100%; object-fit: cover; display: block; }
.hero-shot .tag {
  position: absolute; left: 10px; bottom: 10px; font-family: 'Label Sans', sans-serif;
  font-size: 10.5px; letter-spacing: 0.08em; text-transform: uppercase;
  background: rgba(16,26,21,0.82); border: 1px solid rgba(111,224,207,0.35); color: var(--crystal);
  padding: 4px 9px; border-radius: 100px;
}
.hero-shot.empty { display: flex; align-items: center; justify-content: center; color: var(--ink-faint); font-size: 13px; }

.section-label {
  font-family: 'Label Sans', sans-serif; font-size: 12px; letter-spacing: 0.13em; text-transform: uppercase;
  color: var(--ink-faint); margin: 56px 0 18px; display: flex; align-items: baseline; gap: 12px;
}
.section-label .n { color: var(--pollen); font-variant-numeric: tabular-nums; }
.section-label::after { content: ""; flex: 1; height: 1px; background: var(--line); }

.pipeline { display: flex; align-items: center; gap: 2px; overflow-x: auto; padding: 8px 4px 18px; margin: 0 -4px; }
.pipe-node {
  flex: none; width: 118px; text-decoration: none; border: 1px solid var(--line); background: var(--surface);
  border-radius: 10px; padding: 14px 10px; text-align: center; transition: border-color .15s, transform .15s, background .15s;
}
.pipe-node:hover { border-color: var(--crystal); background: var(--surface-2); transform: translateY(-2px); }
.pipe-node.approved { border-color: var(--crystal); }
.pipe-node.rejected { border-color: var(--flag); opacity: .6; }
.pipe-node.pending { border-color: var(--pollen); }
.pipe-node-n { font-family: 'Display Slab', serif; font-weight: 900; font-size: 22px; color: var(--crystal); line-height: 1; }
.pipe-node-code { font-family: 'Label Sans', sans-serif; font-size: 12px; font-weight: 700; margin-top: 6px; color: var(--ink); }
.pipe-node-dur { font-size: 11.5px; color: var(--ink-faint); margin-top: 2px; font-variant-numeric: tabular-nums; }
.pipe-node-st { font-size: 10px; letter-spacing: .06em; text-transform: uppercase; color: var(--ink-faint); margin-top: 3px; }
.pipe-arrow {
  flex: none; display: flex; flex-direction: column; align-items: center; justify-content: center;
  width: 92px; color: var(--ink-faint); font-size: 15px; gap: 3px;
}
.pipe-arrow span { font-family: ui-monospace, 'SF Mono', Menlo, monospace; font-size: 9.5px; color: var(--pollen); white-space: nowrap; }
.pipeline-note { color: var(--ink-muted); font-size: 14px; margin: 4px 0 0; }
.pipeline-total { font-variant-numeric: tabular-nums; color: var(--ink); }

.beat { border: 1px solid var(--line); background: var(--surface); border-radius: 14px; padding: 26px 26px 22px; margin-bottom: 22px; scroll-margin-top: 24px; }
.beat-head { display: flex; gap: 16px; align-items: flex-start; margin-bottom: 14px; }
.beat-num { font-family: 'Display Slab', serif; font-weight: 900; font-size: 30px; color: var(--crystal-dim); line-height: 1; flex: none; padding-top: 2px; }
.beat-head-text h3 { font-family: 'Display Slab', serif; font-weight: 900; font-size: 20px; margin: 0 0 4px; line-height: 1.2; }
.beat-slug { font-family: 'Body Sans', sans-serif; font-weight: 400; color: var(--ink-faint); font-size: 15px; }
.beat-meta { font-size: 12.5px; color: var(--ink-faint); font-variant-numeric: tabular-nums; }
.beat-meta .status { text-transform: uppercase; letter-spacing: .06em; }
.beat-meta .status.approved { color: var(--crystal); }
.beat-meta .status.rejected { color: var(--flag); }
.beat-meta .status.pending { color: var(--pollen); }

.cuts { display: flex; flex-direction: column; gap: 10px; margin-bottom: 18px; }
.cut { display: flex; gap: 12px; }
.cut-n { flex: none; width: 22px; padding-top: 2px; font-family: 'Label Sans', sans-serif; font-size: 11px; color: var(--ink-faint); font-variant-numeric: tabular-nums; }
.cut-framing { font-family: 'Label Sans', sans-serif; font-size: 11.5px; letter-spacing: .03em; text-transform: uppercase; color: var(--pollen); margin-bottom: 2px; }
.cut-action { font-size: 14.5px; color: var(--ink); }
.cut-voiced { display: inline-flex; align-items: center; gap: 5px; margin-top: 4px; font-size: 12px; color: var(--crystal); }

.vo-player { display: flex; align-items: center; gap: 12px; background: var(--ground-2); border: 1px solid var(--line); border-radius: 10px; padding: 12px 16px; margin-bottom: 16px; }
.vo-player .vl { font-family: 'Label Sans', sans-serif; font-size: 10.5px; letter-spacing: .1em; text-transform: uppercase; color: var(--crystal); flex: none; }
.vo-player audio { flex: 1; height: 32px; }

.prompt-block { background: var(--ground-2); border: 1px solid var(--line); border-radius: 10px; padding: 16px 18px 18px; margin-bottom: 16px; }
.prompt-label { font-family: 'Label Sans', sans-serif; font-size: 10.5px; letter-spacing: .1em; text-transform: uppercase; color: var(--pollen); margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
.prompt-label-sub { color: var(--ink-faint); text-transform: none; letter-spacing: 0; font-family: 'Body Sans', sans-serif; font-size: 12.5px; }
.prompt-copy { background: var(--pollen); color: var(--ground-2); border: 0; border-radius: 6px; padding: 4px 11px; font-size: 11px; font-weight: 700; cursor: pointer; font-family: 'Label Sans', sans-serif; }
.prompt-text { font-family: ui-monospace, 'SF Mono', Menlo, monospace; font-size: 12.8px; line-height: 1.65; color: #c9dcd2; white-space: pre-wrap; word-wrap: break-word; margin: 0; }

.render-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; background: var(--line); border-radius: 8px; overflow: hidden; }
.render-cell { background: var(--surface-2); padding: 10px 12px; }
.render-k { font-family: 'Label Sans', sans-serif; font-size: 9.5px; letter-spacing: .08em; text-transform: uppercase; color: var(--ink-faint); margin-bottom: 3px; }
.render-v { font-size: 12.5px; color: var(--ink); word-break: break-word; }

.missing-note { border: 1px dashed var(--line); border-radius: 10px; padding: 16px 18px; font-size: 13.5px; color: var(--ink-muted); margin-top: 16px; }
.missing-note b { color: var(--ink); }

.footer { margin-top: 56px; padding-top: 24px; border-top: 1px solid var(--line); font-size: 13px; color: var(--ink-faint); }

@media (max-width: 640px) {
  .hero-media { grid-template-columns: 1fr; }
  .render-row { grid-template-columns: repeat(2, 1fr); }
}
"""

def _take_info(beat_id):
    t = latest_take(beat_id)
    if not t: return None
    meta = json.loads((t/"meta.json").read_text()) if (t/"meta.json").exists() else {}
    return {"take": t, "status": status_of(t),
            "prompt": (t/"prompt.txt").read_text() if (t/"prompt.txt").exists() else "",
            "meta": meta}

def _cuts_from_shots(shots_text):
    """Split the beat's `shots` prose into (framing, action) cuts for display — no dialogue
    words to show (Law 5: they live only in the V3 track), so a cut whose action mentions
    @Audio1 gets a small 'voiced' marker instead of literal text."""
    cuts = []
    for seg in [s.strip() for s in " ".join(shots_text.split()).split("Shot ") if s.strip()]:
        head, _, body = seg.partition(":")
        body = body.strip()
        voiced = "@Audio1" in body
        cuts.append((head.strip(), body, voiced))
    return cuts

def page(ep_file, out="scene.html"):
    """Render the canonical scene page — live truth, ep999-archive look. Read-only."""
    ep, scene, cast = load_scene(ep_file)
    name = scene.get("production_location", scene.get("name", "")).split("\u2014")[0].strip().title()
    beats = ep["beats"]
    total_dur = sum(b["duration"] for b in beats)

    nodes_html, beats_html, missing = [], [], []
    for i, b in enumerate(beats):
        info = _take_info(b["id"]); st = info["status"] if info else "unrendered"
        arrow = '<div class="pipe-arrow"><span>last_frame()</span>&#8594;</div>' if i > 0 else ""
        nodes_html.append(f"""{arrow}
        <a class="pipe-node {st}" href="#beat-{i+1}">
          <div class="pipe-node-n">{i+1:02d}</div>
          <div class="pipe-node-code">{b["id"]}</div>
          <div class="pipe-node-dur">{b["duration"]}s</div>
          <div class="pipe-node-st">{st}</div>
        </a>""")

        cuts = _cuts_from_shots(b["shots"])
        cuts_html = ""
        for j, (head, body, voiced) in enumerate(cuts):
            voiced_html = '<div class="cut-voiced">&#9834; voiced from @Audio1</div>' if voiced else ""
            cuts_html += f"""
        <div class="cut">
          <div class="cut-n">{j+1:02d}</div>
          <div class="cut-body">
            <div class="cut-framing">Shot {head}</div>
            <div class="cut-action">{body}</div>
            {voiced_html}
          </div>
        </div>"""

        prev_obj = object() if i and approved_take(beats[i-1]["id"]) else None
        prompt = info["prompt"] if info and info["prompt"] else compile_prompt(ep, scene, cast, b, prev_obj)
        label = "EXACT FIRED PROMPT" if info and info["prompt"] else "COMPILED PROMPT"
        label_sub = "— sent to Seedance, verbatim" if info and info["prompt"] else "— what will fire, verbatim, from canon"
        m = info["meta"] if info else {}
        if not info: missing.append(b["id"])

        vo_path = ROOT / b["audio"]
        vo_html = (f'<div class="vo-player"><span class="vl">@Audio1</span>'
                   f'<audio controls src="{b["audio"]}"></audio></div>') if vo_path.exists() else ""

        status_class = st if st in ("approved", "rejected", "pending") else ""
        beats_html.append(f"""
    <section class="beat" id="beat-{i+1}">
      <div class="beat-head">
        <div class="beat-num">{i+1:02d}</div>
        <div class="beat-head-text">
          <h3>{b["id"]} <span class="beat-slug">{b.get("title","")}</span></h3>
          <div class="beat-meta">{b["duration"]}s &nbsp;&middot;&nbsp; <span class="status {status_class}">{st}</span> &nbsp;&middot;&nbsp; Fuzzby &middot; Zenny</div>
        </div>
      </div>
      {vo_html}
      <div class="cuts">{cuts_html}
      </div>
      <div class="prompt-block">
        <div class="prompt-label"><span>{label} <span class="prompt-label-sub">{label_sub}</span></span>
          <button class="prompt-copy" onclick="navigator.clipboard.writeText(this.parentElement.nextElementSibling.innerText)">COPY</button></div>
        <pre class="prompt-text">{prompt}</pre>
      </div>
      <div class="render-row">
        <div class="render-cell"><div class="render-k">start frame</div><div class="render-v">{(m.get("refs") or ["keyframe / re-mint"])[0]}</div></div>
        <div class="render-cell"><div class="render-k">output</div><div class="render-v">{b["id"]}.mp4</div></div>
        <div class="render-cell"><div class="render-k">resolution</div><div class="render-v">720p</div></div>
        <div class="render-cell"><div class="render-k">audio</div><div class="render-v">@Audio1 (V3, fired in)</div></div>
      </div>
    </section>""")

    plate_or_kf = scene["keyframe"] if (ROOT / scene["keyframe"]).exists() else scene["plate"]
    plate_tag = "Signed keyframe" if (ROOT / scene["keyframe"]).exists() else "Scene plate (keyframe not yet signed)"
    b1_take = approved_take(beats[0]["id"])
    if b1_take and (b1_take / "clip.mp4").exists():
        hero_right = f'<div class="hero-shot"><video src="{b1_take.relative_to(ROOT)}/clip.mp4" controls></video><span class="tag">Beat 1, approved</span></div>'
    else:
        hero_right = '<div class="hero-shot empty">No approved clip yet</div>'

    missing_note = ("<b>What's missing right now:</b> " +
        (", ".join(missing) + " have not rendered yet &mdash; their prompt blocks show the exact text "
         "that will fire, compiled live from canon; nothing here has been invented to fill the gap."
         if missing else "nothing &mdash; every beat has a take on disk."))

    html = f"""<!doctype html><meta charset="utf-8"><title>Scene 1 &mdash; {name}</title><style>{PAGE_CSS}</style>
<div class="wrap">
  <header class="hero">
    <div class="eyebrow">Episode 1 &middot; Live production &middot; Julian's Loop</div>
    <h1>Scene 1 &mdash; {name},<br><em>beat by beat.</em></h1>
    <p class="hero-sub">Fuzzby and Zenny, pollen to storm. {len(beats)} beats, chained frame to frame &mdash;
    every prompt on this page is the machine's own truth, read live from the pipeline, never edited.</p>
    <div class="hero-media">
      <div class="hero-shot"><img src="{plate_or_kf}" alt="Scene 1"><span class="tag">{plate_tag}</span></div>
      {hero_right}
    </div>
  </header>
  <div class="section-label"><span class="n">01</span> The chain</div>
  <div class="pipeline">{"".join(nodes_html)}
  </div>
  <p class="pipeline-note">Every beat opens from the scene keyframe or the previous beat's
  <b class="pipeline-total">last_frame()</b> re-mint, plus both character turnarounds and its own @Audio1 track.
  Total run time: <b class="pipeline-total">{total_dur}s</b> across {len(beats)} beats.</p>
  <div class="section-label"><span class="n">02</span> Every beat, every prompt</div>
  {"".join(beats_html)}
  <div class="missing-note">{missing_note}</div>
  <div class="footer">Julian's Loop &middot; canon.yaml + {ep_file} + studio.py &middot; regenerate with <code>studio.py page {ep_file}</code></div>
</div>"""
    (ROOT / out).write_text(html)
    print(f"Scene page -> {ROOT/out}")

# ------------------------------------------------------------------- cli ----
if __name__ == "__main__":
    cmd, *args = sys.argv[1:] or ["help"]
    {"compile": lambda: print(compile_prompt(*load_scene(args[0]),
                              beat_by_id(yaml.safe_load((ROOT/args[0]).read_text()), args[1]),
                              None)),
     "keyframe": lambda: keyframe(args[0]),
     "fire":    lambda: fire(args[0], args[1]),
     "approve": lambda: approve(args[0]),
     "reject":  lambda: reject(args[0], args[1]),
     "walk":    lambda: walk(args[0]),
     "preflight": lambda: preflight(args[0]),
     "stitch":  lambda: stitch(args[0]),
     "page":    lambda: page(args[0]),
     "help":    lambda: print(__doc__ + "\nusage: studio.py "
                "keyframe|compile|fire|walk|approve|reject|stitch ep1_s1.yaml [beat] [reason]"),
    }.get(cmd, lambda: die(f"unknown command {cmd}"))()
