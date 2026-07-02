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

Content assertions (T33 Ruling, 2026-07-02, Julian): diffing only proves "unchanged since last time" — it
never proves anything is actually THERE, so a snapshot itself could be lean and every later diff would still
pass. `assertions()` checks every shipped segprompt beat directly: (1) if the beat authored a motionTempo, a
real fragment of it must survive into the prompt (checked as the longest name-free chunk of the raw field, so
it holds regardless of which delabeled form — full first-mention or short — a character name became); (2) if
the beat has dialogue, the prompt must carry a SPEAKER MAP. Wired into both commands: `diff` fails (exit 1) on
a failed assertion even with zero text diffs; `capture` refuses to bless a snapshot that fails one — a lean
prompt can never silently become the new normal.

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
        mt = str(b.get("motionTempo") or "").strip()
        if mt:
            chunks = _name_free_chunks(mt, cast)
            check = (max(chunks, key=len) if chunks else "")[:60].strip()
            if check and check not in prompt:
                fails.append(f"{code}: motionTempo language not found in the shipped prompt (looked for: {check!r})")
        if _has_dialogue(b) and "SPEAKER MAP:" not in prompt:
            fails.append(f"{code}: beat has dialogue but the shipped prompt has no SPEAKER MAP")
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
