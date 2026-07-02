#!/usr/bin/env python3
"""cb_golden.py — T10, the golden-set harness.

Stores a known-good snapshot of BOTH prompt paths and diffs current output against it:
  • the Seedance clip-prompt baseline (cb_segprompt.shipped_prompt — for_beat_v2, the SAME call
    gate3_dryrun/cb_beats.run/get_seedance_prompt make; a raw cb_segprompt.for_beat() call would
    silently measure the retired v1 fallback instead of what the studio actually ships) on all 5
    Ep1 Scene-1 beats (1.B1-1.B5, since Julian's Director's Cut restructure — was 1.B1-1.B3).
  • the keyframe prompt (cb_scene.keyframe_for) on all 5 Ep1 Scene-1 beats (1.B1-1.B5) — anchor + 4
    chained beats, so a chain-vs-anchor formatting regression shows up too.

CLAUDE.md hard rule: no prompt-touching commit merges without this diff shown. A diff is not automatically
wrong — a ticket can deliberately change a prompt — but it must be SHOWN to Julian before the golden is
recaptured, never silently overwritten.

Content assertions (spec freeze, 2026-07-02, Julian): diffing only proves "unchanged since last time" — it never
proves anything is actually THERE, so a snapshot itself could be lean and every later diff would still pass.
`assertions()` checks every shipped segprompt beat against v3's OWN spec (updated from the v2-era checks, which
tested for motionTempo/physicalFeeling language and a literal "SPEAKER MAP:" string — v3 deliberately drops both:
the trials found them token tax, and the JSON emitter binds a speaker per SHOT, not a beat-level line map):
  1. a real fragment of the beat's own cuts[].action content survives into the prompt (checked as the longest
     name-free chunk, so it holds regardless of which delabeled role-label form a character name became) —
     proves the shots carry the Director's actual action, not generic filler.
  2. if the beat has dialogue: the PROSE emitter must carry a "SPEAKER MAP:" line; the JSON emitter must have at
     least one shot with a dialogue object whose line is the fixed "the line in @Audio1 during this shot" string
     (never the actual words).
  3. the PROSE emitter's NEGATIVES line has exactly six comma-separated items (the worked example's own spec).
  4. the JSON emitter parses as valid JSON with the required top-level keys and a non-empty shots[] array.
  5. both emitters' per-shot seconds sum to exactly the beat's total duration (the mechanical assembler's own
     invariant — durations become PER-SHOT seconds, they must never drift from the beat total).
Wired into both commands: `diff` fails (exit 1) on a failed assertion even with zero text diffs; `capture`
refuses to bless a snapshot that fails one — a lean or malformed prompt can never silently become the new normal.

    python3 cb_golden.py diff       # compare current output vs the stored golden set (exit 1 on any diff or failed assertion)
    python3 cb_golden.py capture    # OVERWRITE the golden set with current output (only after Julian has seen the diff)
"""
import os, sys, re, json, difflib

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN_DIR = os.path.join(HERE, "goldens")
PKG = os.path.join(HERE, "..", "cb-output", "Ep1_Episode_1_beat_package.json")
SEGPROMPT_BEATS = ["1.B1", "1.B2", "1.B3", "1.B4", "1.B5"]
KEYFRAME_BEATS = ["1.B1", "1.B2", "1.B3", "1.B4", "1.B5"]


def _pkg():
    return json.load(open(PKG))


def current_snapshot():
    """{key: prompt text} for every golden-set entry, built the SAME way the live paths build them
    (cb_segprompt.shipped_prompt — the shared decision gate3_dryrun/cb_beats.run/get_seedance_prompt all call,
    v2 first with v1 as a loud logged fallback; cb_scene.keyframe_for for the keyframe) — never a bespoke
    re-implementation, and never a raw for_beat()/for_beat_v2() call that could measure a path nothing ships."""
    import cb_segprompt, cb_scene
    d = _pkg()
    beats = d["beats"]
    by_code = {(b.get("beatCode") or b.get("shotCode")): b for b in beats}
    scenes = {str(s.get("sceneNumber")): s for s in (d.get("scenes") or [])}
    out = {}
    for code in SEGPROMPT_BEATS:
        b = by_code.get(code)
        if not b:
            continue
        sc = scenes.get(str(b.get("sceneNumber")))
        prompt, _builder, _is_v2 = cb_segprompt.shipped_prompt(b, sc)
        out[f"segprompt__{code}"] = prompt or ""
    for code in KEYFRAME_BEATS:
        if code not in by_code:
            continue
        prompt, _refs, _info = cb_scene.keyframe_for(beats, code, "Ep1")
        out[f"keyframe__{code}"] = prompt
    return out


def _golden_path(key):
    return os.path.join(GOLDEN_DIR, key + ".txt")


def _has_dialogue(beat):
    return bool(beat.get("speakers")) or any((c.get("dialogue") or "").strip() for c in (beat.get("cuts") or []))


def _name_free_chunks(text, cast):
    """Split `text` on any cast-name mention (with an optional possessive 's, matching the exact span
    cb_segprompt._delabel rewrites) — the surviving fragments are words delabeling never touches, so they must
    appear verbatim in the shipped prompt no matter which role-label form (full first-mention, or short) a name
    became. Returns the fragments in order, stripped, empties dropped."""
    if not cast:
        return [text.strip()] if text.strip() else []
    pat = r"\b(?:" + "|".join(re.escape(n) for n in cast) + r")(?:'s)?\b"
    return [seg.strip() for seg in re.split(pat, text) if seg.strip()]


def assertions(snap=None):
    """Content assertions on every shipped segprompt beat — see the module docstring. Returns a list of failure
    strings (empty means everything passed)."""
    d = _pkg()
    beats = d["beats"]
    by_code = {(b.get("beatCode") or b.get("shotCode")): b for b in beats}
    snap = snap if snap is not None else current_snapshot()
    fails = []
    for code in SEGPROMPT_BEATS:
        b = by_code.get(code)
        if not b:
            continue
        prompt = snap.get(f"segprompt__{code}", "")
        cast = b.get("openingCast") or b.get("characters") or []
        is_json = prompt.strip().startswith("{")

        # (1) a real fragment of the beat's OWN cuts[].action survives — proves real content, not generic filler
        action = " ".join(str(c.get("action") or "").strip() for c in (b.get("cuts") or []))
        if action.strip():
            chunks = _name_free_chunks(action, cast)
            check = (max(chunks, key=len) if chunks else "")[:60].strip()
            if check and check not in prompt:
                fails.append(f"{code}: none of the beat's own cuts[].action content survived into the shipped prompt (looked for: {check!r})")

        # (2) dialogue binding — SPEAKER MAP for prose, a per-shot dialogue object for JSON
        has_dlg = _has_dialogue(b)
        if has_dlg and not is_json and "SPEAKER MAP:" not in prompt:
            fails.append(f"{code}: beat has dialogue but the PROSE prompt has no SPEAKER MAP")
        if has_dlg and is_json:
            try:
                doc = json.loads(prompt)
                shots = doc.get("shots") or []
                dlg_shots = [s for s in shots if isinstance(s.get("dialogue"), dict)]
                if not dlg_shots:
                    fails.append(f"{code}: beat has dialogue but no JSON shot carries a dialogue object")
                bad_line = [s for s in dlg_shots if s["dialogue"].get("line") != "the line in @Audio1 during this shot"]
                if bad_line:
                    fails.append(f"{code}: a JSON dialogue shot's line is not the fixed @Audio1 reference — "
                                 f"actual words may have leaked: {bad_line[0]['dialogue'].get('line')!r}")
            except Exception as e:
                fails.append(f"{code}: JSON prompt failed to parse ({e})")

        # (3) NEGATIVES trimmed to six (prose only — the JSON emitter has no NEGATIVES section). Split on ", no "
        # (the clause boundary — every item starts with "no"), NOT every comma: an item like "no on-screen text,
        # subtitles, logos or watermarks" is ONE clause with commas inside its own internal list.
        if not is_json:
            m = re.search(r"NEGATIVES:\s*(.+)$", prompt, re.S)
            if m:
                n = len([x for x in re.split(r",\s*(?=no )", m.group(1).strip()) if x.strip()])
                if n != 6:
                    fails.append(f"{code}: NEGATIVES should have exactly 6 items, has {n}")
            else:
                fails.append(f"{code}: no NEGATIVES section found in the prose prompt")

        # (4)+(5) structural invariants — durations become PER-SHOT seconds, must sum to the beat total
        dur = int(b.get("durationSec") or 12); dur = max(8, min(15, dur))
        if is_json:
            try:
                doc = json.loads(prompt)
                for key in ("duration", "aspect", "style", "references", "shots"):
                    if key not in doc:
                        fails.append(f"{code}: JSON prompt missing required top-level key {key!r}")
                if not doc.get("shots"):
                    fails.append(f"{code}: JSON prompt has an empty shots[] array")
                total = sum(s.get("seconds", 0) for s in (doc.get("shots") or []))
                if total != dur:
                    fails.append(f"{code}: JSON shots[].seconds sum to {total}, expected the beat total {dur}")
            except Exception:
                pass   # already reported above
        else:
            secs = [int(x) for x in re.findall(r"SHOT \d+ \((\d+)s\)", prompt)]
            if secs and sum(secs) != dur:
                fails.append(f"{code}: prose SHOT seconds sum to {sum(secs)}, expected the beat total {dur}")
    return fails


def diff():
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    snap = current_snapshot()
    any_diff = False
    for key, text in snap.items():
        gp = _golden_path(key)
        if not os.path.exists(gp):
            print(f"[{key}] NO GOLDEN STORED YET — run 'python3 cb_golden.py capture' once Julian has reviewed this output.")
            any_diff = True
            continue
        golden = open(gp, encoding="utf-8").read()
        if golden == text:
            print(f"[{key}] OK — identical to golden")
        else:
            any_diff = True
            print(f"[{key}] DIFF —")
            for line in difflib.unified_diff(golden.splitlines(), text.splitlines(),
                                              fromfile="golden", tofile="current", lineterm=""):
                print("  " + line)
    fails = assertions(snap)
    for f in fails:
        any_diff = True
        print(f"[ASSERTION FAILED] {f}")
    print()
    print("ZERO DIFFS — safe to merge" if not any_diff
          else "DIFFS FOUND — show Julian before merging (CLAUDE.md hard rule); recapture only after he has seen this")
    return 1 if any_diff else 0


def capture():
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    snap = current_snapshot()
    fails = assertions(snap)
    if fails:
        print("REFUSING TO CAPTURE — the current output fails its own content assertions (a lean prompt must not"
              " become the new golden):")
        for f in fails:
            print(f"  {f}")
        return 1
    for key, text in snap.items():
        open(_golden_path(key), "w", encoding="utf-8").write(text)
        print(f"captured [{key}] ({len(text)} chars)")
    return 0


if __name__ == "__main__":
    os.chdir(HERE)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "diff"
    sys.exit(capture() if cmd == "capture" else diff())
