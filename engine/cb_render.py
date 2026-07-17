#!/usr/bin/env python3
"""cb_render.py — THE SHOT RENDER LOOP (THE_DEFINITIVE_PIPELINE.md Gates 4-8, hybrid v2).

Consumes ONE artifact: the scene production package cb_engine.py compiles and validates.
Everything the render model must never decide was decided upstream; this module only
executes, checks, and stops for Julian.

The loop, per the spec's own gate order (voice BEFORE images — timing drives pictures):
  Gate 4  voice_scene()     one ElevenLabs text-to-dialogue call per dialogue shot, the
                            exact verbatim words from the shot's own typed dialogueLines
  Gate 5  animatic_scene()  every shot held for its real duration with its real voice —
                            the rhythm test before any expensive image or video
  Gate 6  keyframe_shot()   the opener's anticipation frame, reference-first
  Gate 7  fire_shot()       a CONTROLLED CANDIDATE BATCH per shot (default 3, range 1-4)
                            behind a spend disclosure + explicit human approval — Seedance
                            is a PROBABILISTIC generator; upstream planning controls the
                            inputs, it never guarantees the performance. Identical
                            keyframe/references/audio/prompt/settings across the batch.
  Gate 8  approve/reject    Julian selects ONE candidate (others archived) — approval
                            harvests its literal final frame as the next relay's anchor;
                            batch rejection follows THE FAILURE DECISION LADDER, hard-
                            stopping at 2 failed batches (model-limited: human redesign)
  stitch_scene()            approved clips hard-cut in order (cuts were DESIGNED upstream)

HARD REFUSALS (never a silent degrade): a package whose validation failed cannot fire;
a relay cannot fire before its source shot is approved and harvested; a missing character
reference, plate or keyframe refuses with the artifact named; a shot pending review cannot
be re-fired. Law 6 is re-asserted at fire time as defense in depth.

All paid calls live in cb_gen (cost ledger + .gen.json sidecars fire there); this module
adds a .review.json human checklist per candidate. The unit tests over this module prove
ORCHESTRATION, VALIDATION, SPENDING CONTROL and STATE TRANSITIONS only — they are never
evidence of creative render quality, which no test can prove (rule 28: no check
approximates "is it funny").

    python3 cb_render.py voice    <scene> [episode]
    python3 cb_render.py animatic <scene> [episode]
    python3 cb_render.py keyframe <scene> <shotId> [episode]
    python3 cb_render.py next     <scene> [episode] [--candidates N] [--spend-token T]
    python3 cb_render.py fire     <scene> <shotId> [episode] [--candidates N] [--spend-token T]
    python3 cb_render.py approve  <scene> <shotId> <candidateN> [episode]
    python3 cb_render.py reject   <scene> <shotId> "<correction>" [--category identity|geography|action-timing|instruction-ignored|other] [episode]
    python3 cb_render.py metrics  <scene> [episode]
    python3 cb_render.py stitch   <scene> [episode]
    python3 cb_render.py status   <scene> [episode]
"""
import os, sys, json, re, glob, pathlib, datetime, shutil, hashlib, uuid
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cb_engine
import cb_gen
import cb_post
import paths as P

MEDIA = HERE / "media" / "shots"
DUR_TOLERANCE_SEC = 1.5          # rendered clip may differ from designed duration by this much


class Refused(RuntimeError):
    """A named, deliberate refusal — never a crash, never a silent skip."""


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _norm(s):
    return re.sub(r"[^a-z0-9']+", " ", (s or "").lower().replace("’", "'")).strip()


# ── package + ledger ────────────────────────────────────────────────────────────────────
def _pkg_path(scene, episode="Ep1"):
    """2026-07-17 (Julian's layer-boundary directive, item 2): delegates to cb_engine's
    canonical_package_path — the one place the canonical package's filename convention
    lives (cb_engine.py already owns the package CONTRACT). Name and signature unchanged
    so every existing internal caller of _pkg_path needs no changes."""
    return cb_engine.canonical_package_path(scene, episode)


def load_pkg(scene, episode="Ep1"):
    p = _pkg_path(scene, episode)
    if not p.exists():
        raise Refused(f"no production package at {p.name} — run cb_engine.py {scene} {episode} first")
    return json.load(open(p)), p


def _save(pkg, path):
    json.dump(pkg, open(path, "w"), indent=1, ensure_ascii=False)


def _shot(pkg, shot_id):
    for s in pkg["shots"]:
        if s["shotId"] == shot_id:
            return s
    raise Refused(f"no shot {shot_id} in the package")


def _ledger(pkg, shot_id):
    for e in pkg["continuityLedger"]:
        if e["shotId"] == shot_id:
            return e
    raise Refused(f"no ledger entry for {shot_id}")


def _require_valid(pkg):
    if not (pkg.get("validation") or {}).get("passed"):
        raise Refused("REFUSED — the production package failed design validation; "
                      "fix the design, never fire past a red validator")


# ── reference resolution — identity/plate refusals are keeper law (never fire blind) ────
def _characters_cfg():
    try:
        return json.load(open(P.CHARS))
    except Exception:
        return {}


def _resolve_char(name, characters_cfg):
    """Exact key first, then exact case-insensitive/apostrophe-normalized match ("FUZZBY" ->
    "Fuzzby") — never substring (the Keen/Keen's-Mum lesson). The design LLM authors
    dialogue speakers in script caps; canon keys are canonical case. Found by the first
    real-provider validation run (2026-07-16), invisible to the mocked golden path."""
    if name in characters_cfg:
        return name
    want = _norm(name)
    for k in characters_cfg:
        if _norm(k) == want:
            return k
    return name


def _char_ref(name, characters_cfg):
    rel = (characters_cfg.get(_resolve_char(name, characters_cfg)) or {}).get("anchor")
    path = (HERE / rel) if rel else None
    if not path or not path.exists():
        raise Refused(f"REFUSED — no resolvable identity reference for {name} "
                      f"(characters.json anchor: {rel}) — identity comes only from references")
    return str(path)


def _plate_path(scene, episode="Ep1"):
    hits = sorted(glob.glob(str(HERE / "media" / f"{episode}_S{scene}*plate*.png")))
    if not hits:
        raise Refused(f"REFUSED — no scene plate found for {episode} scene {scene} "
                      f"(media/{episode}_S{scene}*plate*.png) — the world anchor must exist first")
    return hits[-1]


def _slot_paths(shot, slots_key, anchor_path, scene, episode, characters_cfg):
    """The image upload list, in the package's own persisted slot order — the order is the
    contract; a fire that reorders references invalidates every inline @图N binding."""
    out = []
    for slot in sorted((k for k in shot[slots_key] if k.startswith("@图")),
                       key=lambda k: int(k[2:])):
        role = shot[slots_key][slot]
        if role in ("opening keyframe", "previous shot final frame"):
            out.append(anchor_path)
        elif role == "scene plate":
            out.append(_plate_path(scene, episode))
        else:
            out.append(_char_ref(role, characters_cfg))
    return out


# ── Gate 4 — voice, the exact words, one in-context call per dialogue shot ──────────────
def _vo_path(shot_id, episode):
    return MEDIA / f"{episode}_{shot_id}_vo.mp3"


def voice_shot(pkg, path, shot_id, episode="Ep1", log=print):
    shot = _shot(pkg, shot_id)
    if not shot.get("dialogueLines"):
        return None
    _require_confirmed_billing("elevenlabs")               # protection 5 — block, not warn
    characters_cfg = _characters_cfg()
    turns = []
    for ln in shot["dialogueLines"]:
        vid = (characters_cfg.get(_resolve_char(ln["speaker"], characters_cfg)) or {}).get("voiceId")
        if not vid:
            raise Refused(f"REFUSED — no ElevenLabs voiceId for {ln['speaker']} "
                          f"(Law 5: the voice lives in the render; no fallback)")
        turns.append({"text": ln["exactText"], "voice_id": vid})
    MEDIA.mkdir(parents=True, exist_ok=True)
    out = _vo_path(shot_id, episode)
    led = _ledger(pkg, shot_id)
    kind = "regeneration" if led.get("voPath") else "generation"
    cb_gen.eleven_dialogue(turns, out=str(out), generation_kind=kind,
                            production_route="cb_render")
    led["voPath"] = str(out)
    _save(pkg, path)
    log(f"VOICE — {shot_id}: {len(turns)} line(s) -> {out.name}")
    return str(out)


def voice_scene(scene, episode="Ep1", log=print):
    pkg, path = load_pkg(scene, episode)
    _require_valid(pkg)
    done = []
    for s in pkg["shots"]:
        if s.get("dialogueLines") and not _ledger(pkg, s["shotId"]).get("voPath"):
            done.append(voice_shot(pkg, path, s["shotId"], episode, log=log))
    log(f"VOICE — scene {scene}: {len(done)} shot track(s) built")
    return done


# ── Gate 5 — THE TIMING SLATE (reclassified, Julian's probabilistic-model correction,
# 2026-07-16): a dialogue and shot-duration timing slate, NOT a creative animatic. It
# supports approval of exactly five things — dialogue accuracy, character voice assignment,
# broad shot duration, overall scene length, intended dialogue position — and must never be
# presented as proof of physical comedy, staging, animation, geography or final rhythm.
def animatic_scene(scene, episode="Ep1", log=print):
    """Builds the TIMING SLATE (function name kept for CLI/Studio compatibility)."""
    pkg, path = load_pkg(scene, episode)
    _require_valid(pkg)
    MEDIA.mkdir(parents=True, exist_ok=True)
    clips = []
    for s in pkg["shots"]:
        led = _ledger(pkg, s["shotId"])
        img = led.get("keyframePath") or _slate(s, episode)
        vo = led.get("voPath")
        dur = max(float(s["durationSec"]), (_audio_dur(vo) + 0.5) if vo else 0.0)
        clip = MEDIA / f"{episode}_{s['shotId']}_timing_slate.mp4"
        _hold(img, dur, vo, str(clip))
        clips.append(str(clip))
    out = HERE / "media" / f"{episode}_Scene{scene}_timing_slate.mp4"
    result = cb_post.assemble_picture(clips, str(out))
    if not result:
        raise Refused("timing-slate assembly failed — see ffmpeg output above")
    log(f"TIMING SLATE — scene {scene}: {len(clips)} shots -> {out.name} · approves dialogue "
        f"accuracy, voice assignment, shot durations, scene length and line position ONLY — "
        f"it does not prove staging, physical comedy or final rhythm")
    return str(out)


def _slate(shot, episode):
    """A plain title card for a shot with no keyframe yet — PIL, reusing cb_post's proven
    font fallback (never ffmpeg drawtext; that availability bug was already fixed once)."""
    from PIL import Image, ImageDraw
    out = MEDIA / f"{episode}_{shot['shotId']}_slate.png"
    img = Image.new("RGB", (1280, 720), (24, 26, 32))
    d = ImageDraw.Draw(img)
    font = cb_post._pil_font(44)
    d.text((60, 280), shot["shotId"], fill=(240, 240, 240), font=font)
    d.text((60, 350), (shot.get("purpose") or "")[:70], fill=(170, 180, 200),
           font=cb_post._pil_font(28))
    img.save(out)
    return str(out)


def _audio_dur(p):
    return cb_post._dur(p) or 0.0


def _hold(img, dur, audio, out):
    # every hold carries a real audio stream (silent when no voice) — the scene assembler's
    # concat maps [i:a] on EVERY clip; and -t bounds the output (never -shortest, which would
    # truncate a 6s hold to its 2s voice track). Found by the first real animatic assembly.
    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", img]
    if audio:
        cmd += ["-i", audio]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    cmd += ["-t", f"{dur:.2f}", "-r", "24", "-pix_fmt", "yuv420p",
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,"
                   "pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            "-af", "apad", "-c:a", "aac", out]
    import subprocess as sp
    r = sp.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise Refused(f"timing-slate hold failed for {out}: {r.stderr.decode()[-300:]}")
    return out


# ── Gate 6 — the opener keyframe (anticipation, reference-first) ────────────────────────
def keyframe_shot(scene, shot_id, episode="Ep1", log=print):
    pkg, path = load_pkg(scene, episode)
    _require_valid(pkg)
    _require_confirmed_billing("fal")                       # protection 5 — block, not warn
    shot = _shot(pkg, shot_id)
    if shot["sourceType"] != "opener":
        raise Refused(f"REFUSED — {shot_id} is a relay shot; it anchors on its source shot's "
                      f"harvested final frame, never its own keyframe")
    characters_cfg = _characters_cfg()
    refs = _slot_paths(shot, "keyframeReferenceSlots", None, scene, episode, characters_cfg)
    MEDIA.mkdir(parents=True, exist_ok=True)
    out = MEDIA / f"{episode}_{shot_id}_keyframe.png"
    cb_gen.generate_image(shot["keyframePrompt"], refs=refs, out=str(out), production_route="cb_render")
    led = _ledger(pkg, shot_id)
    led["keyframePath"] = str(out)
    _save(pkg, path)
    log(f"KEYFRAME — {shot_id} -> {out.name} (review before firing)")
    return str(out)


# ── Gate 7 — THE CANDIDATE GENERATOR (Julian's probabilistic-model correction,
# 2026-07-16): Seedance is a probabilistic generator, not a deterministic renderer. One
# approved shot contract produces a CONTROLLED CANDIDATE SET (default 3, range 1-4) behind
# an explicit spend disclosure + human approval. Upstream planning and validation control
# the INPUTS; they never guarantee the performance — the product is an approved shot chosen
# from candidates, not a "perfect prompt".
DEFAULT_CANDIDATES = 3
MAX_CANDIDATES = 4
MAX_BATCH_ATTEMPTS = 2      # the failure ladder's hard stop — never an endless patch loop

# the per-candidate evaluation sheet (§6 of the correction) — HUMAN review criteria; the
# machine fills mechanical notes only and never auto-approves creative quality
REVIEW_CRITERIA = ["characterIdentity", "relativeScale", "startingGeography",
                    "actionReadability", "physicalCauseAndEffect",
                    "comicOrEmotionalPerformance", "cameraBehaviour",
                    "dialogueAndMouthPerformance", "continuity", "finalFrameUsability"]

FAILURE_CATEGORIES = ["identity", "geography", "action-timing", "instruction-ignored", "other"]

DECISION_LADDER = """THE FAILURE DECISION LADDER (after reviewing a candidate set):
  1. One candidate succeeds            -> approve it (approve <scene> <shotId> <N>)
  2. Failures vary randomly            -> ONE controlled reroll, UNCHANGED package
  3. Identity/opening geography fails consistently -> correct the keyframe or references
  4. Action/physical timing fails consistently     -> simplify or divide the shot (redesign)
  5. Model repeatedly ignores an instruction       -> remove conflicts, shorten the prompt
  6. Two failed batches                -> STOP: shot is model-limited; human redesign or an
                                          alternative production method. No prompt-patching."""


def _anchor_for(pkg, shot):
    led = _ledger(pkg, shot["shotId"])
    if shot["sourceType"] == "opener":
        kf = led.get("keyframePath")
        if not kf or not os.path.exists(kf):
            raise Refused(f"REFUSED — {shot['shotId']} has no generated keyframe yet "
                          f"(cb_render.py keyframe {shot['beatCode'].split('.')[0]} {shot['shotId']})")
        return kf
    src = _ledger(pkg, shot["sourceShotId"])
    if src.get("status") != "approved" or not src.get("harvestFrame"):
        raise Refused(f"REFUSED — {shot['shotId']} relays off {shot['sourceShotId']}, which is "
                      f"not approved+harvested yet (status: {src.get('status')}) — "
                      f"Julian's eye comes first, always")
    return src["harvestFrame"]


def _require_confirmed_billing(provider):
    """PROTECTION 5 (Julian, 2026-07-16): an unconfirmed billing profile HARD-BLOCKS paid
    generation — a refusal, never a warning. One-line confirmation in billing_profile.json
    (planConfirmed + cadenceConfirmed) unblocks the provider."""
    import cb_costs
    prof = cb_costs.load_billing_profile(provider)
    if not prof or not (prof.get("planConfirmed") and prof.get("cadenceConfirmed")):
        raise Refused(f"REFUSED — billing profile for '{provider}' is UNCONFIRMED "
                      f"(engine/billing_profile.json: planConfirmed/cadenceConfirmed). Paid "
                      f"generation is hard-blocked until Julian confirms the plan and cadence.")


def _file_md5(path):
    try:
        return hashlib.md5(pathlib.Path(path).read_bytes()).hexdigest()
    except Exception:
        return "missing"


def _shots_hash(pkg):
    """The exact package hash (protection 1/4): every shot's full authored+compiled content."""
    return hashlib.sha256(json.dumps(pkg["shots"], sort_keys=True,
                                      ensure_ascii=False).encode()).hexdigest()[:16]


def _binding_hash(pkg, shot, led, imgs, anchor, candidates, fast):
    """Everything the spend approval is bound to (protection 1): the exact package hash,
    provider, model/tier, candidate count, cost rate, max batch cost — plus the CONTENT
    hashes of the anchor, every reference file and the audio, the slot order, duration and
    settings. Any change between disclosure and generation produces a different hash and
    invalidates the token."""
    import cb_costs
    key = "seedance_fast_per_sec" if fast else "seedance_standard_per_sec"
    rate, _, _ = cb_costs.RATES[key]
    per = round(cb_costs.estimate_video_cost(key, int(round(shot["durationSec"]))), 4)
    payload = {"packageHash": _shots_hash(pkg),
               "shotId": shot["shotId"],
               "provider": "fal", "model": f"seedance-ref2vid-{'fast' if fast else 'standard'}",
               "candidates": candidates, "ratePerSecUsd": rate,
               "maxBatchCostUsd": round(per * candidates, 4),
               "prompt": shot["seedancePrompt"],
               "slotOrder": shot["referenceSlots"],
               "anchorMd5": _file_md5(anchor),
               "refMd5s": [_file_md5(p) for p in imgs],
               "audioMd5": _file_md5(led["voPath"]) if led.get("voPath") else None,
               "durationSec": shot["durationSec"]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:32], per


def _fresh_validation(pkg, episode):
    """PROTECTION 4: validation is re-run against the CURRENT package content at every
    disclosure — a hand-edited or revised package can never fire on a stale green stamp.
    Zero-LLM (cb_engine's deterministic validator, imported, never modified)."""
    import cb_engine as E
    d, _ = E._load_pkg(episode)
    beats = E._scene_beats(d, pkg["sceneNumber"])
    fields = set(E.Shot.model_fields)
    shots = [E.Shot(**{k: v for k, v in rec.items() if k in fields}) for rec in pkg["shots"]]
    design = E.SceneShotList(statement=E.DirectorStatement(**pkg.get("directorStatement", {
        k: "n/a" for k in ("audienceFeeling", "whoseScene", "emotionalChange", "theLaugh",
                            "visualSurprise", "carryForward")})), shots=shots)
    report = E.validate_scene_design(design, beats, _characters_cfg())
    if not report["passed"]:
        errs = [i for i in report["issues"] if i["severity"] == "ERROR"]
        raise Refused(f"REFUSED — fresh validation of the CURRENT package failed with "
                      f"{len(errs)} error(s) (first: {errs[0]['code']} at {errs[0]['path']}). "
                      f"A revised package requires fresh validation before any spend.")
    return report


def _prompt_version(shot):
    import hashlib
    return hashlib.md5(shot["seedancePrompt"].encode()).hexdigest()[:8]


def _spend_disclosure(shot, led, candidates, fast, anchor):
    """Everything a human must see BEFORE approving a candidate batch (§3): counts, costs,
    prompt version, references in slot order, keyframe/anchor, audio, duration."""
    import cb_costs
    key = "seedance_fast_per_sec" if fast else "seedance_standard_per_sec"
    per = round(cb_costs.estimate_video_cost(key, int(round(shot["durationSec"]))), 4)
    return {"shotId": shot["shotId"], "candidateCount": candidates,
            "costPerCandidateUsd": per, "maxBatchCostUsd": round(per * candidates, 4),
            "promptVersion": _prompt_version(shot),
            "referenceSlots": shot["referenceSlots"],
            "openingAnchor": anchor,
            "audioAsset": led.get("voPath"),
            "shotDurationSec": shot["durationSec"],
            "tier": "fast" if fast else "standard"}


def _sealed_envelope(pkg, shot, led, imgs, anchor, candidates, fast, per):
    """THE IMMUTABLE PROVIDER-REQUEST ENVELOPE (Julian's cutover order, 2026-07-16, §5):
    everything the provider will receive, sealed AT DISCLOSURE — exact prompt, duration, model,
    resolution, candidate count, reference order with per-file hashes, audio hash, max cost.
    The spend token binds to this envelope's hash; firing sends THIS, never a recompile."""
    img_slots = [t for t in shot["referenceSlots"] if t != "@Audio1"]
    refs = [{"slot": t, "role": shot["referenceSlots"][t], "path": p, "md5": _file_md5(p)}
            for t, p in zip(img_slots, imgs)]
    env = {"shotId": shot["shotId"], "prompt": shot["seedancePrompt"],
           "durationSec": shot["durationSec"], "provider": "fal",
           "model": "bytedance/seedance-2.0",
           "endpoint": ("bytedance/seedance-2.0/fast/reference-to-video" if fast
                         else "bytedance/seedance-2.0/reference-to-video"),
           "resolution": "720p", "tier": "fast" if fast else "standard",
           "candidateCount": candidates, "costPerCandidateUsd": per,
           "maxBatchCostUsd": round(per * candidates, 4),
           "packageRevision": pkg.get("revision"),
           "promptVersion": _prompt_version(shot), "references": refs,
           "audio": {"path": led.get("voPath"),
                      "md5": _file_md5(led["voPath"]) if led.get("voPath") else None}}
    import hashlib
    h = hashlib.sha256(json.dumps(env, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return env, h


def _verify_envelope(auth):
    """The fire-time seal check: the stored envelope re-hashes to the bound hash and every
    referenced file is byte-identical to what was disclosed. Returns the envelope."""
    import hashlib
    env = auth.get("envelope")
    if not env:
        raise Refused("REFUSED — the presented token predates the sealed-envelope protocol "
                      "and is VOID; request a new disclosure.")
    h = hashlib.sha256(json.dumps(env, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if h != auth.get("envelopeHash"):
        raise Refused("REFUSED — sealed-envelope integrity check failed; request a new "
                      "disclosure.")
    for r in env["references"]:
        if _file_md5(r["path"]) != r["md5"]:
            raise Refused(f"REFUSED — {r['slot']} ({r['role']}) changed on disk after the "
                          f"disclosure; the token is STALE. Request a new disclosure.")
    if env["audio"]["path"] and _file_md5(env["audio"]["path"]) != env["audio"]["md5"]:
        raise Refused("REFUSED — the audio asset changed after the disclosure; the token is "
                      "STALE. Request a new disclosure.")
    return env


def fire_shot(scene, shot_id, episode="Ep1", candidates=DEFAULT_CANDIDATES, fast=False,
              spend_token=None, dry_run=False, log=print):
    """Generate one CONTROLLED CANDIDATE BATCH behind Julian's six spend protections
    (2026-07-16): (1) approval is SERVER-SIDE, SINGLE-USE and bound to the exact package
    hash + provider + model + candidate count + cost rate + max batch cost — anything that
    changes between disclosure and generation invalidates the token; (2) the batch is
    RESUMABLE and IDEMPOTENT — a resume generates only missing candidates, never repaying
    completed ones; (4) an unchanged reroll is verified against the identical binding, and
    any revision re-validates from scratch; (5) an unconfirmed billing profile hard-blocks;
    (6) every candidate and every failure is persisted, nothing deleted."""
    pkg, path = load_pkg(scene, episode)
    _require_valid(pkg)                                     # the stored gate, cheapest first
    _require_confirmed_billing("fal")                       # protection 5 — block, not warn
    shot = _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
    candidates = max(1, min(MAX_CANDIDATES, int(candidates)))
    if led.get("status") == "model-limited":
        raise Refused(f"REFUSED — {shot_id} is MODEL-LIMITED after {MAX_BATCH_ATTEMPTS} failed "
                      f"candidate batches; the ladder requires human redesign or an alternative "
                      f"production method, never more prompt-patching.\n{DECISION_LADDER}")
    if led.get("status") == "approved":
        raise Refused(f"REFUSED — {shot_id} is already approved; reject it first to re-fire")
    if shot.get("dialogueLines") and not led.get("voPath"):
        raise Refused(f"REFUSED — {shot_id} has dialogue but no voice track "
                      f"(Law 5: voice first, no native-voice fallback)")

    # LAW 6, re-asserted at the last moment before money
    p = _norm(shot["seedancePrompt"])
    for ln in shot.get("dialogueLines") or []:
        if len(_norm(ln["exactText"]).split()) >= 2 and _norm(ln["exactText"]) in p:
            raise Refused(f"REFUSED — LAW 6: spoken words found in {shot_id}'s compiled prompt")

    # THE UNCHANGED-PACKAGE RULE: nothing is auto-appended after a failure — a reroll ships
    # the byte-identical contract; a targeted correction is a NEW versioned package that
    # re-validates and re-discloses below (the binding hash makes this mechanical).
    prompt = shot["seedancePrompt"]
    anchor = _anchor_for(pkg, shot)
    characters_cfg = _characters_cfg()
    imgs = _slot_paths(shot, "referenceSlots", anchor, scene, episode, characters_cfg)

    # ── RESUME PATH (protection 2): an in-flight batch completes its MISSING candidates
    # only, under its ORIGINAL token — completed candidates are never regenerated or repaid
    batch = led.get("batch")
    if batch and batch.get("status") == "generating":
        if spend_token != batch["token"]:
            raise Refused(f"REFUSED — {shot_id} has an in-flight batch; resuming requires its "
                          f"original spend token (nothing new is authorized)")
        binding, _per = _binding_hash(pkg, shot, led, imgs, anchor, batch["expected"], fast)
        if binding != batch["bindingHash"]:
            raise Refused(f"REFUSED — the package changed mid-batch (binding mismatch); the "
                          f"in-flight authorization is void. Request a new disclosure.")
        # a resume ships the SAME sealed envelope the original approval bound (§5)
        envelope = _verify_envelope(batch)
        prompt = envelope["prompt"]
        fast = (envelope["tier"] == "fast")
        candidates = batch["expected"]
    else:
        if led.get("status") == "candidates-pending":
            raise Refused(f"REFUSED — {shot_id} has a candidate batch pending Julian's review "
                          f"(approve one candidate or reject the batch first)")
        # PROTECTION 4: fresh validation of the CURRENT package, every disclosure
        _fresh_validation(pkg, episode)
        binding, per = _binding_hash(pkg, shot, led, imgs, anchor, candidates, fast)
        envelope, env_hash = _sealed_envelope(pkg, shot, led, imgs, anchor, candidates,
                                                fast, per)
        reroll = (led.get("lastBatchBinding") == binding)
        disclosure = {"shotId": shot_id, "candidateCount": candidates,
                       "costPerCandidateUsd": per,
                       "maxBatchCostUsd": round(per * candidates, 4),
                       "promptVersion": _prompt_version(shot),
                       "bindingHash": binding,
                       "envelopeHash": env_hash,
                       "packageHash": _shots_hash(pkg),
                       "rerollOfUnchangedPackage": reroll,
                       "packageRevision": pkg.get("revision"),
                       "referenceSlots": shot["referenceSlots"],
                       "openingAnchor": anchor, "audioAsset": led.get("voPath"),
                       "shotDurationSec": shot["durationSec"],
                       "tier": "fast" if fast else "standard"}
        log("SPEND DISCLOSURE — review before approving:")
        for k in ("shotId", "candidateCount", "costPerCandidateUsd", "maxBatchCostUsd",
                   "promptVersion", "bindingHash", "envelopeHash", "packageRevision",
                   "rerollOfUnchangedPackage", "openingAnchor", "audioAsset",
                   "shotDurationSec", "tier"):
            log(f"  {k}: {disclosure[k]}")
        log(f"  referenceSlots (upload order): {json.dumps(disclosure['referenceSlots'])}")

        auth = led.get("pendingSpendAuth")
        if dry_run:
            log("SEALED PROVIDER-REQUEST ENVELOPE (dry run — no token issued, nothing stored):")
            log(json.dumps(envelope, indent=1, ensure_ascii=False))
            log(f"ENVELOPE SHA-256: {env_hash}")
            raise Refused("REFUSED — DRY RUN. No spend token was issued and no state changed.")
        if spend_token is None:
            # issue (or re-issue) the server-side single-use token, bound to the SEALED envelope
            led["pendingSpendAuth"] = {"token": uuid.uuid4().hex,
                                        "bindingHash": binding,
                                        "envelope": envelope, "envelopeHash": env_hash,
                                        "disclosure": disclosure, "issuedAt": _now()}
            _save(pkg, path)
            raise Refused("REFUSED — SPEND NOT APPROVED. A single-use spend token has been "
                          "issued, bound to the sealed envelope above; re-run with "
                          f"--spend-token {led['pendingSpendAuth']['token']} "
                          "(Studio: 'Approve spend & fire').")
        # validate the presented token: server-issued, single-use, envelope-exact
        if not auth or spend_token != auth["token"]:
            raise Refused("REFUSED — unknown or already-used spend token; request a new "
                          "disclosure")
        if auth["bindingHash"] != binding:
            raise Refused("REFUSED — the spend token is STALE: the package, references, "
                          "audio, cost or settings changed after the disclosure. Request a "
                          "new disclosure and approval.")
        # THE SEAL (§5): firing sends the DISCLOSED envelope verbatim — never a recompile,
        # never another prompt, never another duration. Verified file-by-file.
        envelope = _verify_envelope(auth)
        prompt = envelope["prompt"]
        fast = (envelope["tier"] == "fast")
        candidates = envelope["candidateCount"]
        led["pendingSpendAuth"] = None                     # single-use: consumed NOW
        pv = auth["disclosure"]["promptVersion"]
        if led.get("lastPromptVersion") and led["lastPromptVersion"] != pv:
            led["promptRevisions"] = led.get("promptRevisions", 0) + 1
        led["lastPromptVersion"] = pv
        batch = {"token": spend_token, "bindingHash": binding,
                 "envelope": envelope, "envelopeHash": auth["envelopeHash"],
                 "batchId": f"{shot_id}-b{led.get('batchAttempts', 0) + 1}-"
                             f"{datetime.datetime.now().strftime('%Y%m%dT%H%M%S')}",
                 "expected": candidates, "done": [], "failed": [],
                 "disclosure": auth["disclosure"], "status": "generating"}
        led["batch"] = batch
        _save(pkg, path)

    image_urls = [cb_gen._fal_upload(x) for x in imgs]     # uploaded once per invocation
    audio_urls = [cb_gen._fal_upload(led["voPath"])] if led.get("voPath") else None

    MEDIA.mkdir(parents=True, exist_ok=True)
    for i in range(1, batch["expected"] + 1):
        if i in batch["done"]:
            continue                                       # idempotent: never regenerated
        out = MEDIA / f"{episode}_{shot_id}_c{i}.mp4"
        log(f"FIRE — {shot_id} candidate {i}/{batch['expected']} ({shot['sourceType']}, "
            f"{shot['durationSec']}s{', @Audio1' if audio_urls else ''}) ...")
        try:
            cb_gen.generate_video_seedance_ref(prompt, image_urls,
                                                audio_urls=audio_urls,
                                                resolution=envelope["resolution"],
                                                duration=str(int(round(envelope["durationSec"]))),
                                                out=str(out), fast=fast, raw_prompt=True, production_route="cb_render")
        except Exception as e:
            # protection 6: the failure is PERSISTED, the batch stays resumable
            batch["failed"].append({"candidate": i, "error": str(e)[:400], "at": _now()})
            _save(pkg, path)
            raise Refused(f"REFUSED — candidate {i} failed at the provider "
                          f"({str(e)[:160]}). The batch is saved and resumable: re-run with "
                          f"the SAME spend token to generate only the missing candidates — "
                          f"completed candidates are never repaid.")
        _candidate_review(shot, str(out), batch["batchId"], i)
        batch["done"].append(i)
        _save(pkg, path)                                   # persisted per candidate

    batch["status"] = "complete"
    paths = [str(MEDIA / f"{episode}_{shot_id}_c{i}.mp4") for i in sorted(batch["done"])]
    led.update({"status": "candidates-pending", "candidatePaths": paths,
                "batchId": batch["batchId"],
                "candidatesGenerated": led.get("candidatesGenerated", 0) + len(batch["done"]),
                "disclosure": batch["disclosure"],
                "lastBatchBinding": batch["bindingHash"], "firedAt": _now()})
    _save(pkg, path)
    log(f"FIRE — {shot_id}: {len(paths)} candidate(s) rendered · STOPPED for Julian's "
        f"review. Approve ONE (approve {scene} {shot_id} <n>) or reject the batch. "
        f"No candidate is ever auto-approved.")
    return paths


def _candidate_review(shot, clip, batch_id, index):
    """The per-candidate review sheet (§6): the ten human criteria, all null — supporting
    human review only; the machine NEVER auto-approves creative quality. Machine notes hold
    only what is mechanically checkable (duration)."""
    real = cb_post._dur(clip) or 0.0
    notes = []
    if abs(real - float(shot["durationSec"])) > DUR_TOLERANCE_SEC:
        notes.append(f"duration {real:.1f}s vs designed {shot['durationSec']}s")
    review = {"shotId": shot["shotId"], "batchId": batch_id, "candidate": index,
              "at": _now(),
              "criteria": {c: None for c in REVIEW_CRITERIA},
              "note": "human review only — the machine never approves creative quality",
              "machineNotes": notes}
    with open(clip + ".review.json", "w") as f:
        json.dump(review, f, indent=1)
    return review


def next_shot(scene, episode="Ep1", candidates=DEFAULT_CANDIDATES, fast=False,
              spend_token=None, dry_run=False, log=print):
    """Fire a candidate batch for the next fireable shot in order, then STOP."""
    pkg, path = load_pkg(scene, episode)
    _require_valid(pkg)
    for s in pkg["shots"]:
        led = _ledger(pkg, s["shotId"])
        if led.get("status") == "candidates-pending":
            raise Refused(f"REFUSED — {s['shotId']} has a candidate batch pending Julian's "
                          f"review; nothing advances past it")
        if led.get("status") == "model-limited":
            raise Refused(f"REFUSED — {s['shotId']} is model-limited and blocks the walk; "
                          f"it needs human redesign before the scene can continue")
        if led.get("status") != "approved" or (led.get("batch") or {}).get("status") == "generating":
            return fire_shot(scene, s["shotId"], episode, candidates=candidates,
                              fast=fast, spend_token=spend_token, log=log, dry_run=dry_run)
    log(f"SCENE {scene} — every shot approved; ready to stitch")
    return None


# ── Gate 8 — Julian selects ONE candidate; approval harvests the relay anchor ───────────
def approve_shot(scene, shot_id, candidate=1, episode="Ep1", reviewed_by="Julian", log=print):
    """Select ONE candidate from the pending batch. The unselected candidates are archived
    (never deleted); the selected take's literal final frame is harvested as the next
    relay's anchor."""
    pkg, path = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)
    if led.get("status") != "candidates-pending" or not led.get("candidatePaths"):
        raise Refused(f"REFUSED — {shot_id} has no candidate batch pending review")
    cands = led["candidatePaths"]
    candidate = int(candidate)
    if not 1 <= candidate <= len(cands):
        raise Refused(f"REFUSED — candidate must be 1..{len(cands)} for {shot_id}")
    selected = cands[candidate - 1]

    # archive the unselected candidates + their review sheets (never deleted)
    arch = HERE / "media" / "archive" / "shots_candidates" / led["batchId"]
    arch.mkdir(parents=True, exist_ok=True)
    for i, c in enumerate(cands, 1):
        if i == candidate:
            continue
        for ext in ("", ".review.json"):
            if os.path.exists(c + ext):
                shutil.move(c + ext, arch / os.path.basename(c + ext))

    harvest = MEDIA / f"{episode}_{shot_id}_final_frame.png"
    cb_gen.last_frame(selected, out=str(harvest))
    led.update({"status": "approved", "approvedTake": selected,
                "approvedCandidate": candidate, "harvestFrame": str(harvest),
                "approval": {"approved": True, "candidate": candidate,
                              "reviewed_by": reviewed_by, "at": _now()}})
    _save(pkg, path)
    # off-machine backup of the approved take — ported from cb_beats (the 2026-07-08
    # operational-risk fix); fail-soft, never blocks an approval
    try:
        root = str(HERE.parent)
        if root not in sys.path:
            sys.path.insert(0, root)   # tools/ lives at repo root (same resolution cb_beats uses)
        import tools.backup_media as _backup
        _backup.backup_one(os.path.abspath(selected))
        _backup.backup_one(os.path.abspath(str(harvest)))
    except Exception as e:
        log(f"  (backup skipped: {e})")
    log(f"APPROVED — {shot_id} candidate {candidate} by {reviewed_by}; "
        f"final frame harvested -> {harvest.name}; unselected candidates archived")
    return str(harvest)


def reject_shot(scene, shot_id, correction, category="other", episode="Ep1",
                reviewed_by="Julian", log=print):
    """Reject the WHOLE candidate batch: every candidate archived (never deleted) with the
    one-sentence correction and its failure category on record. The next fire is a
    controlled reroll of the UNCHANGED package; after MAX_BATCH_ATTEMPTS failed batches the
    shot is MODEL-LIMITED and requires human redesign (the decision ladder's hard stop)."""
    pkg, path = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)
    if led.get("status") != "candidates-pending" or not led.get("candidatePaths"):
        raise Refused(f"REFUSED — {shot_id} has no candidate batch pending review")
    if category not in FAILURE_CATEGORIES:
        raise Refused(f"REFUSED — category must be one of {FAILURE_CATEGORIES}")
    ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    arch = HERE / "media" / "archive" / "shots_rejected" / f"{episode}_{shot_id}_{ts}"
    arch.mkdir(parents=True, exist_ok=True)
    for c in led["candidatePaths"]:
        for ext in ("", ".review.json"):
            if os.path.exists(c + ext):
                shutil.move(c + ext, arch / os.path.basename(c + ext))
    rejection = {"shotId": shot_id, "batchId": led.get("batchId"),
                 "correction": correction, "category": category,
                 "reviewed_by": reviewed_by, "at": _now()}
    with open(arch / "REJECTED.json", "w") as f:
        json.dump(rejection, f, indent=1)
    attempts = led.get("batchAttempts", 0) + 1
    led.setdefault("rejections", []).append(rejection)
    led.update({"batchAttempts": attempts, "candidatePaths": None, "batchId": None})
    if attempts >= MAX_BATCH_ATTEMPTS:
        led["status"] = "model-limited"
        _save(pkg, path)
        log(f"REJECTED — {shot_id} batch archived. {attempts} failed batches: shot is now "
            f"MODEL-LIMITED. Human redesign or an alternative production method required.\n"
            f"{DECISION_LADDER}")
    else:
        led["status"] = "designed"
        _save(pkg, path)
        log(f"REJECTED — {shot_id} batch archived ({attempts}/{MAX_BATCH_ATTEMPTS} attempts). "
            f"Correction on record: {correction} [{category}]\n{DECISION_LADDER}")
    return str(arch)


def metrics(scene, episode="Ep1", log=print):
    """§7 — does the pipeline actually work? Per-scene production metrics from the ledger
    and cost ledger. The architecture is successful only if these improve over real
    production; a metric that cannot be computed is null, never invented."""
    pkg, _ = load_pkg(scene, episode)
    costs = {}
    lf = HERE / "cost_ledger.jsonl"
    if lf.exists():
        for line in open(lf):
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("out"):
                costs.setdefault(os.path.basename(str(rec["out"])), 0.0)
                costs[os.path.basename(str(rec["out"]))] += rec.get("cost_usd") or 0.0
    approved, cand_total, batches, revisions, cats = 0, 0, 0, 0, {}
    approved_secs, approved_cost = 0.0, 0.0
    times = []
    for s in pkg["shots"]:
        led = _ledger(pkg, s["shotId"])
        cand_total += led.get("candidatesGenerated", 0)
        batches += led.get("batchAttempts", 0) + (1 if led.get("status") in
                    ("candidates-pending", "approved") else 0)
        revisions += led.get("promptRevisions", 0)
        for r in led.get("rejections", []):
            cats[r.get("category", "other")] = cats.get(r.get("category", "other"), 0) + 1
        if led.get("status") == "approved":
            approved += 1
            approved_secs += float(s["durationSec"])
            base = f"{episode}_{s['shotId']}_c"
            approved_cost += sum(v for k, v in costs.items() if k.startswith(base))
            if led.get("firedAt") and (led.get("approval") or {}).get("at"):
                try:
                    t0 = datetime.datetime.fromisoformat(led["firedAt"])
                    t1 = datetime.datetime.fromisoformat(led["approval"]["at"])
                    times.append((t1 - t0).total_seconds())
                except Exception:
                    pass
    out = {"scene": str(scene), "at": _now(),
           "approvedShots": approved, "totalShots": len(pkg["shots"]),
           "candidatesGenerated": cand_total,
           "candidatesPerApprovedShot": round(cand_total / approved, 2) if approved else None,
           "costPerApprovedSecondUsd": round(approved_cost / approved_secs, 4)
               if approved_secs and approved_cost else None,
           "meanSecondsToApproval": round(sum(times) / len(times), 1) if times else None,
           "failureCategories": cats,
           "promptRevisions": revisions,
           "shotRedesigns": sum(1 for s in pkg["shots"]
                                 if _ledger(pkg, s["shotId"]).get("status") == "model-limited"),
           "identityFailures": cats.get("identity", 0),
           "continuityFailures": cats.get("geography", 0)}
    dest = HERE.parent / "cb-output" / f"{episode}_scene{scene}_metrics.json"
    json.dump(out, open(dest, "w"), indent=1)
    log(json.dumps(out, indent=1))
    return out


# ── Gate 9 handoff — the scene picture (cuts were designed; the join is a hard cut) ─────
def stitch_scene(scene, episode="Ep1", log=print):
    pkg, path = load_pkg(scene, episode)
    clips, missing = [], []
    for s in pkg["shots"]:
        led = _ledger(pkg, s["shotId"])
        if led.get("status") == "approved" and led.get("approvedTake"):
            clips.append(led["approvedTake"])
        else:
            missing.append(s["shotId"])
    if missing:
        raise Refused(f"REFUSED — cannot stitch scene {scene}: unapproved shots {missing}")
    out = HERE / "media" / f"{episode}_Scene{scene}_shots_picture.mp4"
    result = cb_post.assemble_picture(clips, str(out))
    if not result:
        raise Refused("stitch failed — see ffmpeg output above")
    log(f"STITCH — scene {scene}: {len(clips)} approved shots -> {out.name} "
        f"(cb_post mix/captions/masters take it from here)")
    return str(out)


def evidence_pack(scene, episode="Ep1", log=print):
    """THE EVIDENCE PACK (Julian's cutover directive, 2026-07-16): for every shot, one
    record of input → compiled instruction → provider request → returned assets → state
    transitions → costs → approvals → harvested frame — plus the stitched output. Written
    to cb-output/{episode}_scene{scene}_evidence/ as JSON + a readable index.md. Collects
    only what exists; missing pieces are named MISSING, never invented."""
    pkg, _ = load_pkg(scene, episode)
    out_dir = HERE.parent / "cb-output" / f"{episode}_scene{scene}_evidence"
    out_dir.mkdir(parents=True, exist_ok=True)

    # cost entries, keyed by output filename (cb_gen logs every paid call with out=)
    costs = {}
    ledger_file = HERE / "cost_ledger.jsonl"
    if ledger_file.exists():
        for line in open(ledger_file):
            try:
                rec = json.loads(line)
            except Exception:
                continue
            key = os.path.basename(str(rec.get("out") or ""))
            if key:
                costs.setdefault(key, []).append(rec)

    def _asset(p):
        if not p:
            return None
        exists = os.path.exists(p)
        entry = {"path": p, "exists": exists,
                 "bytes": os.path.getsize(p) if exists else None}
        side = p + ".gen.json"
        if os.path.exists(side):
            try:
                entry["providerRequest"] = json.load(open(side))
            except Exception:
                entry["providerRequest"] = "unreadable sidecar"
        entry["costEntries"] = costs.get(os.path.basename(p), [])
        return entry

    cases = []
    for s in pkg["shots"]:
        led = _ledger(pkg, s["shotId"])
        take = led.get("approvedTake") or (led.get("candidatePaths") or [None])[0]
        review = None
        if take and os.path.exists(str(take) + ".review.json"):
            review = json.load(open(str(take) + ".review.json"))
        cases.append({
            "shotId": s["shotId"], "sourceType": s["sourceType"],
            "sourceShotId": s.get("sourceShotId"),
            "input": {"beatCode": s["beatCode"], "purpose": s["purpose"],
                       "dialogueLines": s.get("dialogueLines") or [],
                       "openingPose": s["openingPose"]},
            "compiledInstruction": {"seedancePrompt": s["seedancePrompt"],
                                     "promptWords": s["promptWords"],
                                     "referenceSlots": s["referenceSlots"],
                                     "keyframePrompt": s.get("keyframePrompt"),
                                     "audioBrief": s.get("audioBrief")},
            "assets": {"voice": _asset(led.get("voPath")),
                        "keyframe": _asset(led.get("keyframePath")),
                        "candidates": [_asset(c) for c in (led.get("candidatePaths") or [])],
                        "take": _asset(led.get("approvedTake")),
                        "harvestFrame": _asset(led.get("harvestFrame"))},
            "state": {"status": led.get("status"),
                       "batchAttempts": led.get("batchAttempts", 0),
                       "candidatesGenerated": led.get("candidatesGenerated", 0),
                       "disclosure": led.get("disclosure"),
                       "approval": led.get("approval"),
                       "rejections": led.get("rejections") or [],
                       "machineReview": review},
        })

    stitched = HERE / "media" / f"{episode}_Scene{scene}_shots_picture.mp4"
    animatic = HERE / "media" / f"{episode}_Scene{scene}_timing_slate.mp4"
    if not animatic.exists():   # the pre-reclassification name (the frozen 2026-07-16 slate)
        animatic = HERE / "media" / f"{episode}_Scene{scene}_animatic.mp4"
    pack = {"episode": episode, "scene": str(scene), "generatedAt": _now(),
            "validation": pkg.get("validation"),
            "shots": cases,
            "timingSlate": _asset(str(animatic)) if animatic.exists() else None,
            "stitchedOutput": _asset(str(stitched)) if stitched.exists() else None}
    json.dump(pack, open(out_dir / "evidence.json", "w"), indent=1, ensure_ascii=False)

    md = [f"# Evidence pack — {episode} scene {scene} ({_now()})",
          f"Design validation: {'PASSED' if (pkg.get('validation') or {}).get('passed') else 'FAILED'}\n"]
    for c in cases:
        st = c["state"]
        md.append(f"## {c['shotId']} · {c['sourceType']}"
                  + (f" ← {c['sourceShotId']}" if c["sourceShotId"] else ""))
        md.append(f"- status: **{st['status'] or 'designed'}**"
                  + (f" · approved by {st['approval']['reviewed_by']} at {st['approval']['at']}"
                     if st.get("approval") else "")
                  + (f" · rejected: “{st['rejection']['correction']}”" if st.get("rejection") else ""))
        for k, a in c["assets"].items():
            if k == "candidates":
                present = [x for x in (a or []) if x and x.get("exists")]
                md.append(f"- candidates: {len(present)} pending" if present
                          else "- candidates: none pending (selected/archived or not fired)")
                continue
            md.append(f"- {k}: " + ("MISSING" if not a else
                      f"`{os.path.basename(a['path'])}` ({a['bytes']} bytes)"
                      + (f" · £-logged {len(a['costEntries'])} cost entr(y/ies)" if a["costEntries"] else "")
                      + (" · provider request recorded" if a.get("providerRequest") else "")))
        notes = (st.get("machineReview") or {}).get("machineNotes")
        if notes:
            md.append(f"- machine notes: {'; '.join(notes)}")
        md.append("")
    md.append(f"Stitched output: "
              + (f"`{os.path.basename(str(stitched))}`" if stitched.exists() else "MISSING"))
    (out_dir / "index.md").write_text("\n".join(md))
    log(f"EVIDENCE — {out_dir.name}/evidence.json + index.md ({len(cases)} shots)")
    return str(out_dir)


def status(scene, episode="Ep1", log=print):
    pkg, _ = load_pkg(scene, episode)
    rows = []
    for s in pkg["shots"]:
        led = _ledger(pkg, s["shotId"])
        rows.append(f"{s['shotId']:<10} {s['sourceType']:<7} {led.get('status','designed'):<18} "
                    f"vo={'y' if led.get('voPath') else '-'} "
                    f"kf={'y' if led.get('keyframePath') else '-'} "
                    f"cands={len(led.get('candidatePaths') or [])} "
                    f"batches={led.get('batchAttempts', 0)} "
                    f"harvest={'y' if led.get('harvestFrame') else '-'}")
    log("\n".join(rows))
    return rows


if __name__ == "__main__":
    os.chdir(HERE)
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    cmd = args[0]
    try:
        # shared flags: --candidates N (1-4), --approve-spend, --category X
        flags = {"candidates": DEFAULT_CANDIDATES, "spend_token": None, "category": "other",
                 "dry_run": False}
        pos = []
        i = 1
        while i < len(args):
            a = args[i]
            if a == "--candidates":
                flags["candidates"] = int(args[i + 1]); i += 2
            elif a == "--spend-token":
                flags["spend_token"] = args[i + 1]; i += 2
            elif a == "--category":
                flags["category"] = args[i + 1]; i += 2
            elif a == "--dry-run":
                flags["dry_run"] = True; i += 1
            else:
                pos.append(a); i += 1
        ep = lambda n: pos[n] if len(pos) > n else "Ep1"
        if cmd == "voice":
            voice_scene(pos[0], ep(1))
        elif cmd in ("animatic", "slate"):
            animatic_scene(pos[0], ep(1))
        elif cmd == "keyframe":
            keyframe_shot(pos[0], pos[1], ep(2))
        elif cmd == "next":
            next_shot(pos[0], ep(1), candidates=flags["candidates"],
                       spend_token=flags["spend_token"], dry_run=flags["dry_run"])
        elif cmd == "fire":
            fire_shot(pos[0], pos[1], ep(2), candidates=flags["candidates"],
                       spend_token=flags["spend_token"], dry_run=flags["dry_run"])
        elif cmd == "approve":
            approve_shot(pos[0], pos[1], int(pos[2]) if len(pos) > 2 else 1, ep(3))
        elif cmd == "reject":
            reject_shot(pos[0], pos[1], pos[2], category=flags["category"], episode=ep(3))
        elif cmd == "stitch":
            stitch_scene(pos[0], ep(1))
        elif cmd == "status":
            status(pos[0], ep(1))
        elif cmd == "metrics":
            metrics(pos[0], ep(1))
        elif cmd == "evidence":
            evidence_pack(pos[0], ep(1))
        else:
            print(f"unknown command {cmd}"); sys.exit(1)
    except Refused as e:
        print(str(e)); sys.exit(1)
