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
    "seedance_standard_per_sec":       (0.30,  "second", "medium"),      # ref2vid, no video input, standard tier
    "seedance_fast_per_sec":           (0.24,  "second", "medium"),      # ref2vid, no video input, fast tier
    "seedance_i2v_per_sec":            (0.30,  "second", "medium"),      # image-to-video (generate_video_seedance), same base rate assumed
    # PROVIDER MISMATCH, FLAGGED: cb_gen.generate_image calls Google's Gemini API directly
    # (generativelanguage.googleapis.com, model gemini-3.1-flash-image) — NOT fal.ai's hosted "nano-banana-2"
    # endpoint the pricing research covered. $0.04 is the closest available figure (fal's OLDER, non-"2"
    # Nano Banana listing, which is believed to be the same Gemini Flash Image family) — this is a low-
    # confidence stand-in, not Google's own direct-API billing rate, which was never independently checked.
    # Verify against actual Gemini API billing before trusting this one specifically.
    "nanobanana2_image":               (0.04,  "image",  "low-provider-mismatch"),
    "elevenlabs_tts_v3_per_1k_chars":  (0.10,  "1000 chars", "high"),    # eleven_v3 TTS / text-to-dialogue (same meter, unconfirmed for dialogue specifically)
    "elevenlabs_voice_change_per_min": (0.12,  "minute", "medium"),      # speech-to-speech (RETIRED code path, rule 56 — kept for completeness, should never fire)
    "elevenlabs_music_per_min":        (0.15,  "minute", "medium"),      # Eleven Music, Pro-plan credit ratio — genuinely plan-dependent
    "elevenlabs_sfx_flat":             (0.02,  "sfx call", "low-derived"),  # no published standalone rate found; rough placeholder
}

_OUT_RE = re.compile(r"^([A-Za-z0-9]+)_(\d+(?:\.[A-Za-z0-9]+)?)_")


def _attribution(out_path):
    """Parse {episode}_{code}_{slug}.ext out of an `out=` filename, per this codebase's own universal naming
    convention (cb_beats.py/cb_scene.py). Returns (episode, code) or (None, None) if it doesn't match — a
    scratch/test filename should never crash cost logging, just log unattributed."""
    base = os.path.basename(str(out_path or ""))
    m = _OUT_RE.match(base)
    if not m:
        return None, None
    return m.group(1), m.group(2)


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


def estimate_video_cost(op_key, seconds):
    rate, _, _ = RATES[op_key]
    return rate * float(seconds or 15)  # HANDLE_TOTAL default when duration is "auto"


def estimate_image_cost(op_key=None):
    rate, _, _ = RATES["nanobanana2_image"]
    return rate


def estimate_tts_cost(text):
    rate, _, _ = RATES["elevenlabs_tts_v3_per_1k_chars"]
    return rate * (len(text or "") / 1000.0)


def estimate_music_cost(length_ms):
    rate, _, _ = RATES["elevenlabs_music_per_min"]
    return rate * ((length_ms or 30000) / 60000.0)


def estimate_voice_change_cost(audio_path):
    """Duration-based, but voice_change is RETIRED (cb_gen.voice_change raises before this could ever run) —
    kept only so the rate table stays complete; falls back to a flat 10s estimate since it can never fire."""
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
        if r.get("code"):
            by_beat.setdefault((r["episode"], r["code"]), []).append(r["cost_usd"])
    if by_beat:
        print("\nBy beat:")
        for (ep, code), costs in sorted(by_beat.items(), key=lambda kv: -sum(kv[1])):
            print(f"  {ep} {code}: ${sum(costs):.2f} ({len(costs)} calls)")

    by_scene = {}
    for r in rows:
        if r.get("code") and "." in r["code"]:
            scene = r["code"].split(".")[0]
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
