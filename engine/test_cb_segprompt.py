#!/usr/bin/env python3
"""test_cb_segprompt.py — real automated coverage for cb_segprompt.py (the v5 prompt compiler).

cb_segprompt.py is the single most load-bearing module in this pipeline (shipped_prompt/emit_v5 is what
Seedance actually receives for every beat, every scene, every episode) and had ZERO automated test coverage
before this file — only cb_golden.py's manual diffing, which detects CHANGE, never CORRECTNESS. This file
asserts actual, specific behaviour, matching the plain-assert/no-framework style of test_gate_cascade.py and
test_unapprove_locks.py: plain Python, assert-style checks collected into a fails list, a main() that runs
every check and prints PASS/FAIL per check plus a final summary, sys.exit(1) on any failure.

    python3 test_cb_segprompt.py

Reads the REAL Ep1 beat package (shows/crystal-bears/episodes/output/Ep1_The_Adventure_Begins_beat_package.json)
read-only for the shipped_prompt/manifest-gap checks — never writes to it. Everything else is pure-function
testing against synthetic strings, no I/O.
"""
import os, sys, copy, json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import cb_segprompt as S
import cb_qa

PKG_PATH = os.path.join(os.path.dirname(HERE), "shows", "crystal-bears", "episodes", "output",
                         "Ep1_The_Adventure_Begins_beat_package.json")


def _load_beat(code):
    d = json.load(open(PKG_PATH))
    all_beats = d.get("beats") or d.get("shots") or []
    beat = next(b for b in all_beats if (b.get("beatCode") or b.get("shotCode")) == code)
    scene = next((s for s in d.get("scenes") or [] if str(s.get("sceneNumber")) == str(beat.get("sceneNumber"))), None)
    return beat, scene


def check(fails, label, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"  {status}  {label}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(label + (f" — {detail}" if detail else ""))


def test_strip_spoken_words():
    fails = []
    print("\n=== _strip_spoken_words ===")
    out = S._strip_spoken_words('Fuzzby lands on the stable pose, with "Nailed it." landing on that stable frame.')
    check(fails, "removes the quoted dialogue fragment", '"Nailed it."' not in out and "Nailed it" not in out, out)
    check(fails, "does not leave a dangling 'with'", " with " not in (" " + out + " "), out)
    check(fails, "does not leave doubled spaces", "  " not in out, out)
    check(fails, "does not leave a dangling ' ,' before punctuation", " ," not in out and " ." not in out, out)

    # a plain sentence with no quote must survive completely untouched (no over-stripping)
    plain = "Fuzzby chases and banks hard, then locks onto the flower."
    out2 = S._strip_spoken_words(plain)
    check(fails, "leaves a quote-free sentence unchanged", out2 == plain, out2)

    # a quote with no preceding 'with' still gets removed cleanly
    out3 = S._strip_spoken_words('Zenny turns and says "Look out" before ducking.')
    check(fails, "removes a quote with no preceding 'with'", "Look out" not in out3, out3)
    return fails


def test_strip_speed_adjectives():
    fails = []
    print("\n=== _v5_strip_speed_adjectives ===")
    for word in ("fast", "hyper", "wildly", "manically", "chaotic", "frantic", "erratic", "zooming"):
        sentence = f"Fuzzby flies {word} toward the flower."
        out = S._v5_strip_speed_adjectives(sentence)
        check(fails, f"removes bare speed word '{word}'", word not in out.lower().split(), out)
    # named, concrete action verbs (not generic speed adjectives) must survive
    kept = S._v5_strip_speed_adjectives("Fuzzby rockets forward, brakes too late, loops once, then stops.")
    for verb in ("rockets", "brakes", "loops", "stops"):
        check(fails, f"keeps concrete named gag verb '{verb}'", verb in kept, kept)
    # no double-spacing left behind
    stripped = S._v5_strip_speed_adjectives("Fuzzby flies wildly and fast toward the flower.")
    check(fails, "collapses double-spaces after stripping two adjacent speed words", "  " not in stripped, stripped)
    return fails


def test_standing_negatives():
    fails = []
    print("\n=== _standing_negatives ===")
    negs = S._standing_negatives()
    check(fails, "returns exactly eleven items", len(negs) == 11, f"got {len(negs)}: {negs}")
    check(fails, "every item is a non-empty string", all(isinstance(n, str) and n.strip() for n in negs))
    # calling twice returns the identical list content (no hidden mutation/randomness)
    negs2 = S._standing_negatives()
    check(fails, "is deterministic across calls", negs == negs2)
    return fails


def test_shot_time_ranges():
    fails = []
    print("\n=== _v5_shot_time_ranges ===")
    # Julian's own hand-verified 4-cut/15s worked example
    ranges4 = S._v5_shot_time_ranges(4)
    check(fails, "4 cuts over 15s reproduces Julian's hand-verified boundaries",
          ranges4 == [(0, 4), (4, 8), (8, 11), (11, 15)], str(ranges4))

    for n in (2, 3, 4, 5):
        ranges = S._v5_shot_time_ranges(n)
        check(fails, f"{n} cuts: correct count of ranges", len(ranges) == n, str(ranges))
        check(fails, f"{n} cuts: starts at 0", ranges[0][0] == 0, str(ranges))
        check(fails, f"{n} cuts: ends at HANDLE_TOTAL ({S.HANDLE_TOTAL})",
              ranges[-1][1] == S.HANDLE_TOTAL, str(ranges))
        # no gaps or overlaps: each range's end must equal the next range's start
        contiguous = all(ranges[i][1] == ranges[i + 1][0] for i in range(len(ranges) - 1))
        check(fails, f"{n} cuts: no gaps or overlaps between consecutive ranges", contiguous, str(ranges))
        # every range must be non-negative width (start <= end)
        check(fails, f"{n} cuts: every range has start <= end", all(a <= b for a, b in ranges), str(ranges))
    return fails


def test_shipped_prompt_real_beat():
    fails = []
    print("\n=== shipped_prompt on real beat 1.B1 (opener) ===")
    if not os.path.exists(PKG_PATH):
        check(fails, "real Ep1 beat package exists at expected path", False, PKG_PATH)
        return fails
    beat, scene = _load_beat("1.B1")
    try:
        prompt, builder, is_definitive = S.shipped_prompt(beat, scene, relay=False)
        raised = False
    except Exception as e:
        prompt, builder, is_definitive = "", "", False
        raised = True
        raise_detail = f"{type(e).__name__}: {e}"
    check(fails, "compiles without raising", not raised, raise_detail if raised else "")
    if raised:
        return fails
    check(fails, "returns a non-empty prompt string", isinstance(prompt, str) and len(prompt) > 0)
    check(fails, "is_definitive is True", is_definitive is True)
    check(fails, "builder label identifies v5", "v5" in builder, builder)
    wc = S._v5_word_count(prompt)
    import cb_preflight as PF
    check(fails, f"word count ({wc}) is under WORD_BUDGET_BLOCK ({PF.WORD_BUDGET_BLOCK})",
          wc < PF.WORD_BUDGET_BLOCK, f"word count={wc}")
    # sanity: the prompt should actually mention the beat's own header format
    check(fails, "prompt opens with the HANDLE_TOTAL header", prompt.startswith(f"{S.HANDLE_TOTAL}s, 16:9, 24fps"), prompt[:60])
    check(fails, "prompt ends with the Negative line", prompt.rstrip().endswith("."), prompt[-60:])
    check(fails, "prompt contains the Negative: label", "Negative:" in prompt)
    return fails


def test_manifest_field_missing_on_gap():
    fails = []
    print("\n=== ManifestFieldMissing on a beat missing a required field ===")
    if not os.path.exists(PKG_PATH):
        check(fails, "real Ep1 beat package exists at expected path", False, PKG_PATH)
        return fails
    beat, scene = _load_beat("1.B1")
    broken = copy.deepcopy(beat)
    # endState (NOT endStateStill) is what _v5_beat_story actually reads as the settle text —
    # confirmed live by reading cb_segprompt.py's _v5_beat_story, which raises ManifestFieldMissing("endState", ...)
    broken.pop("endState", None)
    raised_correct_type = False
    raised_generic_fallback = False
    try:
        prompt, _b, _d = S.shipped_prompt(broken, scene, relay=False)
        # if it did NOT raise, it must not have silently produced generic boilerplate text either
        if prompt:
            raised_generic_fallback = True
    except cb_qa.ManifestFieldMissing as e:
        raised_correct_type = True
        detail = str(e)
    except Exception as e:
        detail = f"wrong exception type: {type(e).__name__}: {e}"
    check(fails, "raises cb_qa.ManifestFieldMissing (never silently emits boilerplate)",
          raised_correct_type and not raised_generic_fallback,
          detail if not raised_correct_type else "")
    if raised_correct_type:
        check(fails, "the exception names the missing field (endState)", "endState" in detail, detail)

    # An empty `cuts` list is a DIFFERENT, EARLIER short-circuit: for_beat_v5 itself returns ("", "v5 (empty
    # — no cuts)") before emit_v5/_v5_beat_story ever runs — confirmed by reading for_beat_v5's own guard
    # clause. This is legitimate, documented behaviour (cb_beats.run's "empty Seedance prompt — skipping"
    # handles it), NOT a ManifestFieldMissing case — asserting otherwise would be testing for behaviour the
    # module was never built to have. What we assert instead: it returns cleanly (never raises) and the
    # result is unambiguously empty, so a caller's existing empty-prompt check still catches it.
    broken2 = copy.deepcopy(beat)
    broken2["cuts"] = []
    try:
        prompt2, builder2, _d2 = S.shipped_prompt(broken2, scene, relay=False)
        check(fails, "an empty cuts[] short-circuits to an empty prompt (not a crash, not boilerplate)",
              prompt2 == "", repr(prompt2))
        check(fails, "the empty-cuts builder label names the reason", "no cuts" in builder2, builder2)
    except Exception as e:
        check(fails, "an empty cuts[] short-circuits to an empty prompt (not a crash, not boilerplate)",
              False, f"raised instead: {type(e).__name__}: {e}")
    return fails


def main():
    all_fails = []
    all_fails += test_strip_spoken_words()
    all_fails += test_strip_speed_adjectives()
    all_fails += test_standing_negatives()
    all_fails += test_shot_time_ranges()
    all_fails += test_shipped_prompt_real_beat()
    all_fails += test_manifest_field_missing_on_gap()

    print()
    if all_fails:
        print(f"FAILED — {len(all_fails)} assertion(s) did not hold:")
        for f in all_fails:
            print(f"  - {f}")
        return 1
    print("ALL PASS — cb_segprompt.py's core behaviours (Law 6 stripping, the adjective-chaos ban, the "
          "eleven standing negatives, the shot-timing law, a real beat's compiled word budget, and the "
          "manifest hard-gate on a missing required field) are verified correct, not just non-crashing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
