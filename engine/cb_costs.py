#!/usr/bin/env python3
"""cb_costs.py — THE COST LEDGER (2026-07-08, business-loose-end fix: WORLD_CLASS_ROADMAP.md's own named
metric, "cost per signed minute," was tracked nowhere in the codebase before this).

Every generation call in cb_gen.py logs its estimated cost here, appended to a plain JSONL ledger
(engine/cost_ledger.jsonl — gitignored, runtime state, not source, same category as locked.json). Attribution
is FREE, not a new plumbing requirement: every generation call's own `out=` filename already follows this
codebase's own `{episode}_{code}_{slug}.ext` convention (confirmed against cb_beats.py/cb_scene.py's real call
sites) — parsed here rather than threading a new parameter through every caller.

RATES — researched 2026-07-08 against fal.ai's and ElevenLabs' current pricing pages, confidence labeled per
figure. THESE ARE ESTIMATES, NOT A BILLING RECORD. Verify against your own fal/ElevenLabs account before
trusting this for a real budget decision — provider pricing changes, and this file is not automatically kept
in sync with it. Update the numbers here (and bump RATES_UPDATED) the day you confirm real rates differ.
"""
import os, re, json, time

RATES_UPDATED = "2026-07-08"
LEDGER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cost_ledger.jsonl")

# {op: (usd_per_unit, unit_label, confidence)} — confidence: high / medium / low-derived / low-unresolved
RATES = {
    "seedance_standard_per_sec":       (0.3034, "second", "confirmed — Julian, 2026-07-16"),  # ref2vid standard, 720p, no video input; the higher of fal's two printed figures ($0.3024 token-derived / $0.3034 prose) per Julian's ruling — the spending bound; billing_profile.json v2026-07-16.2 is the confirmation record
    "seedance_fast_per_sec":           (0.24,  "second", "medium"),      # ref2vid, no video input, fast tier
    "seedance_i2v_per_sec":            (0.30,  "second", "medium"),      # image-to-video (generate_video_seedance), same base rate assumed
    # CORRECTED 2026-07-09 (the "low-provider-mismatch" $0.04 guess below was checked against Google's own
    # pricing page, ai.google.dev/gemini-api/docs/pricing, gemini-3.1-flash-image row): NB2 is billed by output
    # token ($60/1M output tokens, standard tier), which resolves to a real per-image price of $0.067 at 1K,
    # $0.101 at 2K (cb_gen.py's own default image_size), $0.151 at 4K. Every NB2 spend this ledger has ever
    # logged at the old $0.04 rate under-counted real cost by roughly 2.5x. Kept, not deleted, for rollback
    # (CB_IMAGE_PROVIDER=nanobanana) alongside the new default, seedream5pro_image, below.
    "nanobanana2_image":               (0.101, "image",  "high"),
    # Seedream 5 Pro (bytedance/seedream/v5/pro/edit, fal.ai) — THE NEW DEFAULT keyframe model (Julian's ruling,
    # 2026-07-09, "we go Seedream 5 pro" — see cb_gen.py's IMAGE_PROVIDER doctrine comment for the evidence).
    # Sourced directly from fal.ai's own model page the same day: $0.135/image for the 1536-2048px output tier
    # (our real 1.B1 test rendered at 2752x1536, in this tier) + $0.0045 per reference image beyond the first
    # free one — a real keyframe beat sends 2-4 references (identity refs + plate/chain), so 0.135 + (n-1)*0.0045
    # for n>=1 refs is the true per-call cost; 0.144 below assumes the common 3-ref case (2 characters + plate)
    # as a flat estimate, matching this ledger's existing single-flat-rate convention (see nanobanana2_image
    # above) rather than threading ref-count through every caller.
    "seedream5pro_image":              (0.144, "image",  "high"),
    # BytePlus ModelArk video path (2026-07-22, Julian: "i want to go via byteplus model ark") — the NEW
    # default video provider (cb_gen.VIDEO_PROVIDER). UNCONFIRMED PRICING: BytePlus's own pricing page was
    # not reachable during this integration (docs.byteplus.com is a JS-rendered SPA that blocked scraping);
    # this figure is a placeholder carried over from seedance_standard_per_sec (the fal.ai rate for the
    # SAME underlying model) as the best available estimate, explicitly NOT a confirmed BytePlus rate.
    # Update the moment a real invoice/pricing page is seen — do not treat spend logged under this key as
    # accurate until then.
    "seedance_byteplus_ark_per_sec":   (0.3034, "second", "low-unresolved — placeholder, carried from fal's seedance_standard_per_sec rate; BytePlus's own price unconfirmed"),
    # 480p test-iteration tier (2026-07-23, Julian: "lets run the tests at the lesser amount"): Seedance
    # bills roughly by pixel-area x seconds; 480p (864x480) is ~45% of 720p's (1280x720) pixel area, so
    # this is the 720p placeholder rate scaled by 0.45. Same caveat as its parent — estimated, not a
    # confirmed BytePlus figure; update both together when a real invoice is seen.
    "seedance_byteplus_ark_480p_per_sec": (0.1365, "second", "estimated — area-proportional (480p ≈ 45% of 720p pixel area) from seedance_byteplus_ark_per_sec, itself unconfirmed"),
    # Seedream 5 Pro via BytePlus ModelArk (2026-07-22, alongside the video-provider switch above) —
    # a real, specific figure from a third-party pricing breakdown (atlascloud.ai, "Seedream 5.0 Pro
    # Price: What You Really Pay Per Image in 2026"), NOT BytePlus's own official pricing page directly
    # (docs.byteplus.com blocked scraping, same limitation as the video integration). Their own stated
    # tiers: images at/above 2.36MP (our real 2K renders, e.g. the confirmed 2752x1536 fal-path output)
    # bill as "2K" at $0.09; the first reference image is free, each additional is $0.003. This flat
    # estimate assumes the common case (2K output, ~2 total references — 1 free + 1 paid), matching this
    # ledger's own established flat-rate convention for nanobanana2_image/seedream5pro_image above,
    # rather than threading exact ref-count through every caller. NOTABLY CHEAPER than either existing
    # image rate (fal Seedream $0.144, NB2 $0.101) if this figure holds — worth flagging to Julian, not
    # yet independently confirmed against a real invoice.
    "seedream5pro_byteplus_image":     (0.096, "image",  "medium — single well-sourced third-party breakdown, not BytePlus's own pricing page directly"),
    "elevenlabs_tts_v3_per_1k_chars":  (0.165, "1000 chars", "published Pro-derived — plan unconfirmed"),  # FALLBACK ONLY: billing_profile.json is the pricing source (Julian's directive, 2026-07-16). Derived from the OFFICIAL published Pro plan ($99/600k credits, 1 credit/char on v3, elevenlabs.io/pricing) — NOT the verified account cost until Julian confirms plan + billing cadence.
    "elevenlabs_dialogue_v3_per_1k_chars": (0.165, "1000 chars", "published Pro-derived — plan unconfirmed"),  # FALLBACK ONLY — see billing_profile.json, the configured source
    "elevenlabs_voice_change_per_min": (0.12,  "minute", "medium"),      # speech-to-speech (RETIRED code path, rule 56 — kept for completeness, should never fire)
    "elevenlabs_music_per_min":        (0.15,  "minute", "medium"),      # Eleven Music, Pro-plan credit ratio — genuinely plan-dependent
    "elevenlabs_sfx_flat":             (0.02,  "sfx call", "low-derived"),  # no published standalone rate found; rough placeholder
}

_OUT_RE = re.compile(r"^([A-Za-z0-9]+)_(\d+(?:\.[A-Za-z0-9]+)?)_")

# THE VO-PREFIX FIX (2026-07-08, HIGH-severity bug): cb_beats.py's build_dialogue_track call and
# cb_pipeline.py's gen_audio() both name every dialogue-track render out=f"vo_{episode}_{code}.mp3" — a
# "vo_" PREFIX before the episode token, which _OUT_RE (below) never matches, since it anchors the episode
# to the very first token. That silently dropped EVERY ElevenLabs voice-generation cost (the highest-frequency
# cost item in the whole pipeline) into episode=None/code=None, invisible to every per-beat/per-scene
# breakdown in report(). Checked FIRST, before the generic fallback.
_VO_RE = re.compile(r"^vo_([A-Za-z0-9]+)_(\d+(?:\.[A-Za-z0-9]+)?)")

# The scene-level asset shape cb_post.py uses for a scene's music/ambience beds — "{episode}_S{scene}_...",
# e.g. "Ep1_S1_music.mp3" — has no beat code at all, just a scene number; _OUT_RE's `\d+` right after the
# first underscore never matches here either (the next token starts with the letter "S", not a digit).
# Checked second, before the generic fallback.
_SCENE_RE = re.compile(r"^([A-Za-z0-9]+)_S(\d+)_")


def _attribution(out_path):
    """Parse {episode}_{code} out of an `out=` filename. Tries, in priority order: the vo_-prefixed
    dialogue-track shape, the {episode}_S{scene}_ scene-asset shape, then the generic
    {episode}_{code}_{slug}.ext convention (cb_beats.py/cb_scene.py video+image renders) as the final
    fallback. Returns (episode, code) or (None, None) if none match — a scratch/test filename should never
    crash cost logging, just log unattributed."""
    base = os.path.basename(str(out_path or ""))

    m = _VO_RE.match(base)
    if m:
        return m.group(1), m.group(2)

    m = _SCENE_RE.match(base)
    if m:
        return m.group(1), m.group(2)

    m = _OUT_RE.match(base)
    if m:
        return m.group(1), m.group(2)

    return None, None


def log_spend(op, cost_usd, out=None, meta=None):
    """Append one ledger line. Never raises — a cost-logging failure must never break a real render that
    already succeeded (matches this codebase's own established pattern for backup_media.backup_one)."""
    try:
        episode, code = _attribution(out)
        row = {
            "ts": time.time(),
            "op": op,
            "cost_usd": round(cost_usd, 4),
            "episode": episode,
            "code": code,
            "out": os.path.basename(str(out)) if out else None,
            "meta": meta or {},
        }
        with open(LEDGER_PATH, "a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"  (cost_ledger: skipped logging {op} — {str(e)[:120]})", flush=True)


def write_gen_sidecar(out, **params):
    """THE REPRODUCIBILITY SIDECAR (2026-07-08, Pipeline TD panel finding): nothing anywhere recorded what
    actually produced a given render — no model name, resolution, duration or fal.ai tier. Writes
    `{out}.gen.json` next to the artifact itself (same directory, same base name, matching the existing
    `.qa.json`/`.join.json`/`.approval.json` sidecar convention in cb_beats.py). This does NOT buy bit-exact
    reproducibility — none of these APIs expose a seed — but it means a future "why does this differ from
    what shipped" question has a real, recorded answer instead of none. Never raises — a sidecar-write
    failure must never break a render that already succeeded."""
    try:
        path = str(out)
        base, ext = os.path.splitext(path)
        sidecar = base + ext + ".gen.json"  # e.g. media/Ep1_1.B1_slug.mp4.gen.json
        row = {"ts": time.time(), "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        row.update({k: v for k, v in params.items() if v is not None})
        with open(sidecar, "w") as f:
            json.dump(row, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  (gen_sidecar: skipped writing for {out} — {str(e)[:120]})", flush=True)


def estimate_video_cost(op_key, seconds):
    rate, _, _ = RATES[op_key]
    return rate * float(seconds or 15)  # HANDLE_TOTAL default when duration is "auto"


def estimate_image_cost(provider="seedream5pro"):
    """provider: "seedream5pro" (fal.ai host, default 2026-07-09 - 2026-07-22), "seedream5pro_byteplus"
    (BytePlus ModelArk host, default as of 2026-07-22 — see cb_gen.SEEDREAM_HOST), or "nanobanana2"
    (rollback model family) — picks the matching RATES key. Three values now, not two: the SEEDREAM_HOST
    switch added a genuine third dimension (which vendor hosts the SAME Seedream model), distinct from
    IMAGE_PROVIDER's own two-value model-family switch (seedream vs nanobanana)."""
    if provider == "nanobanana2":
        key = "nanobanana2_image"
    elif provider == "seedream5pro_byteplus":
        key = "seedream5pro_byteplus_image"
    else:
        key = "seedream5pro_image"
    rate, _, _ = RATES[key]
    return rate


BILLING_PROFILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "billing_profile.json")


def load_billing_profile(provider=None):
    """The configured pricing source (Julian's directive, 2026-07-16 — a billing profile,
    never a hardcoded universal rate). Official provider pricing pages only. Fail-soft:
    a missing/unreadable profile returns None and callers fall back to RATES, loudly
    labelled as the fallback."""
    try:
        prof = json.load(open(BILLING_PROFILE_PATH))
        return prof.get(provider) if provider else prof
    except Exception:
        return None


def dialogue_billing(inputs, model_id="eleven_v3", generation_kind="generation"):
    """The FULL billing record for one text-to-dialogue call — everything the ledger must
    carry per Julian's directive: provider+model, characters submitted, credits consumed,
    plan + cadence (with confirmation flags), pricing-table version + effective date,
    estimated allocated cost EX TAX, and whether this generation/regeneration consumed
    credits. Proven end to end by test_cb_gen."""
    chars = sum(len(str(i.get("text") or "")) for i in (inputs or []))
    full = load_billing_profile()
    prof = (full or {}).get("elevenlabs")
    if prof:
        cpc = (prof.get("creditsPerCharacter") or {}).get(model_id, 1.0)
        credits = chars * cpc
        est = prof["cyclePriceUsdExTax"] / prof["creditsPerCycle"] * credits
        return {"provider": "elevenlabs", "model": model_id,
                "charactersSubmitted": chars, "creditsConsumed": credits,
                "billingPlan": prof.get("plan"),
                "planConfirmed": bool(prof.get("planConfirmed")),
                "billingCadence": prof.get("billingCadence"),
                "cadenceConfirmed": bool(prof.get("cadenceConfirmed")),
                "pricingTableVersion": (full or {}).get("_version"),
                "pricingEffectiveDate": prof.get("effectiveDate"),
                "pricingSource": prof.get("pricingSource"),
                "estimatedCostUsdExTax": round(est, 6),   # 6dp: sub-cent precision matters per call
                "costBasis": ("estimated allocated cost ex tax — published "
                               f"{prof.get('plan')} plan, plan "
                               f"{'CONFIRMED' if prof.get('planConfirmed') else 'UNCONFIRMED'}"),
                "generationKind": generation_kind,
                "creditsWereConsumed": True}
    rate, _, conf = RATES["elevenlabs_dialogue_v3_per_1k_chars"]
    return {"provider": "elevenlabs", "model": model_id,
            "charactersSubmitted": chars, "creditsConsumed": chars,
            "billingPlan": None, "planConfirmed": False,
            "billingCadence": None, "cadenceConfirmed": False,
            "pricingTableVersion": None, "pricingEffectiveDate": None,
            "pricingSource": "RATES fallback — billing_profile.json missing",
            "estimatedCostUsdExTax": round(rate * chars / 1000.0, 6),
            "costBasis": f"RATES fallback ({conf})",
            "generationKind": generation_kind, "creditsWereConsumed": True}


def estimate_dialogue_cost(inputs):
    """Estimated allocated cost (ex tax) for one dialogue call — profile-derived, RATES
    fallback. NOT the verified account cost until the plan and cadence are confirmed."""
    return dialogue_billing(inputs)["estimatedCostUsdExTax"]


def estimate_tts_cost(text):
    rate, _, _ = RATES["elevenlabs_tts_v3_per_1k_chars"]
    return rate * (len(text or "") / 1000.0)


def estimate_music_cost(length_ms):
    rate, _, _ = RATES["elevenlabs_music_per_min"]
    return rate * ((length_ms or 30000) / 60000.0)


def estimate_voice_change_cost():
    """cb_gen.voice_change() is RETIRED (rule 56 — raises RuntimeError before any cb_costs call could ever
    happen), so this function has zero live callers and can never actually fire. Kept deliberately, not
    deleted, purely so RATES["elevenlabs_voice_change_per_min"] stays a documented, non-orphaned rate-table
    entry — mirroring rule 56's own explicit decision to leave cb_gen.voice_change()/lipsync() un-deleted
    pending Julian's word on whether either has a standalone use outside the render pipeline; deleting this
    estimator (and its RATES entry) would foreclose that same still-open call, one level removed.
    FIXED 2026-07-12 (full-codebase audit continued): used to accept an `audio_path` parameter it silently
    ignored, always returning a flat 10s estimate regardless of the real file — implying duration-based
    estimation this function never actually performed. Dropped the misleading parameter; the flat-10s
    estimate is now honest about being a placeholder, not a computation."""
    rate, _, _ = RATES["elevenlabs_voice_change_per_min"]
    return rate * (10 / 60.0)


def report(episode=None):
    """Read the ledger and print: total spend, spend by operation, spend per beat, spend per scene, and
    (WORLD_CLASS_ROADMAP.md's own named metric) cost per signed minute — using approval sidecars in
    engine/media/ to know which beats are actually signed, not just rendered."""
    if not os.path.exists(LEDGER_PATH):
        print("No spend logged yet (cost_ledger.jsonl doesn't exist).")
        return
    rows = []
    with open(LEDGER_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    if episode:
        rows = [r for r in rows if r.get("episode") == episode]
    if not rows:
        print(f"No spend logged{' for ' + episode if episode else ''}.")
        return

    total = sum(r["cost_usd"] for r in rows)
    print(f"=== COST LEDGER{' — ' + episode if episode else ''} ===")
    print(f"Total logged spend: ${total:.2f}  ({len(rows)} calls)")
    print(f"Rates last updated: {RATES_UPDATED} — VERIFY against your own account before trusting this.\n")

    by_op = {}
    for r in rows:
        by_op.setdefault(r["op"], []).append(r["cost_usd"])
    print("By operation:")
    for op, costs in sorted(by_op.items(), key=lambda kv: -sum(kv[1])):
        print(f"  {op}: ${sum(costs):.2f} ({len(costs)} calls, avg ${sum(costs)/len(costs):.3f})")

    by_beat = {}
    for r in rows:
        code = r.get("code")
        # FIXED 2026-07-12 (full-codebase audit continued): a bare scene-level code (e.g. "1", from a
        # scene-wide render like cb_post.py's music/ambience bed — "{episode}_S{scene}_...", matched by
        # _SCENE_RE above) used to be included here too, printing as a phantom beat indistinguishable from
        # a real "1.B1"-style entry — AND was simultaneously excluded from "By scene" below (which required
        # a "." in the code), so scene-level spend never surfaced where it actually belonged, only where it
        # shouldn't. "By beat" now only ever holds a real beat code (one with a "." in it); a bare scene
        # code is scene-only spend and belongs solely in "By scene".
        if code and "." in code:
            by_beat.setdefault((r["episode"], code), []).append(r["cost_usd"])
    if by_beat:
        print("\nBy beat:")
        for (ep, code), costs in sorted(by_beat.items(), key=lambda kv: -sum(kv[1])):
            print(f"  {ep} {code}: ${sum(costs):.2f} ({len(costs)} calls)")

    by_scene = {}
    for r in rows:
        code = r.get("code")
        if not code:
            continue
        # A real beat code ("1.B1") rolls up to its scene number ("1"); a bare scene-level code ("1", see
        # the by_beat comment above) IS already its own scene number — both correctly land in the same
        # (episode, scene) bucket now, instead of the scene-level row being dropped entirely.
        scene = code.split(".")[0]
        by_scene.setdefault((r["episode"], scene), []).append(r["cost_usd"])
    if by_scene:
        print("\nBy scene:")
        for (ep, scene), costs in sorted(by_scene.items(), key=lambda kv: -sum(kv[1])):
            print(f"  {ep} scene {scene}: ${sum(costs):.2f} ({len(costs)} calls)")

    # cost per signed minute — WORLD_CLASS_ROADMAP.md's own named metric
    signed_seconds = 0.0
    media_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media")
    if os.path.isdir(media_dir):
        seen_codes = set()
        for (ep, code) in by_beat:
            if episode and ep != episode:
                continue
            appr = [f for f in os.listdir(media_dir)
                    if f.startswith(f"{ep}_{code}_") and f.endswith(".approval.json")]
            for a in appr:
                try:
                    data = json.load(open(os.path.join(media_dir, a)))
                    if data.get("approved"):
                        seen_codes.add((ep, code))
                except Exception:
                    pass
        # HANDLE_TOTAL (15s) per signed beat — the actual runtime a signed clip contributes
        signed_seconds = len(seen_codes) * 15.0
    if signed_seconds > 0:
        cost_per_min = total / (signed_seconds / 60.0)
        print(f"\nCost per signed minute: ${cost_per_min:.2f}/min ({signed_seconds/60:.2f} signed minutes so far)")
    else:
        print("\nCost per signed minute: n/a (no approved beats yet)")


if __name__ == "__main__":
    import sys
    ep = sys.argv[1] if len(sys.argv) > 1 else None
    report(ep)
