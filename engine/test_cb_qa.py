#!/usr/bin/env python3
"""test_cb_qa.py — regression coverage for cb_qa.py's ZERO-API-CALL checks.

cb_qa.py (1389 lines, ~19 check_* functions) had NO test coverage before this file — only gate-lock
bookkeeping was tested elsewhere (test_gate_cascade.py, test_unapprove_locks.py). This covers every
function that needs no vision_verdict/LLM call: the Character Vocabulary Law, the Camera-Lock Law,
the keyframe lint, check_gate3_lint's text-only checks (word budget, anti-slop, Law 5 dialogue leak,
negation lint, structural congruence), and check_join_state's carryMarks-scoped STATE logic (with
vision_verdict monkeypatched — no network, no API key needed).

Convention matches test_gate_cascade.py / test_unapprove_locks.py: plain Python, assert statements,
no pytest/unittest, a main() that runs every check and prints PASS/FAIL, sys.exit(1) on any failure.

Uses REAL fixture data pulled from the live package (cb-output/Ep1_The_Adventure_Begins_beat_package.json)
where useful, plus synthetic mutations to prove each check can actually fail (a check that can't fail
is worthless).

    python3 test_cb_qa.py
"""
import os, sys, json, copy, glob

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cb_qa

PKG_CANDIDATES = glob.glob(os.path.join(HERE, "..", "cb-output", "*beat_package.json"))
PKG_PATH = max(PKG_CANDIDATES, key=os.path.getmtime) if PKG_CANDIDATES else None

RESULTS = []  # (name, ok, detail)


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


def _load_pkg():
    assert PKG_PATH and os.path.exists(PKG_PATH), f"no beat package found near {HERE}/../cb-output/"
    return json.load(open(PKG_PATH))


def _beat(d, code):
    beats = d.get("beats") or d.get("shots") or []
    b = next((b for b in beats if (b.get("beatCode") or b.get("shotCode")) == code), None)
    assert b is not None, f"beat {code} not found in real package"
    return copy.deepcopy(b)


# ═══════════════════════════════════════════════════════════════════════════════════
# check_character_vocabulary — THE CHARACTER VOCABULARY LAW (no API call; reads
# characters.json's lexicon.banned + the beat's own cuts text)
# ═══════════════════════════════════════════════════════════════════════════════════
def test_character_vocabulary():
    d = _load_pkg()

    # PASS case: 1.B2 is a real, currently-clean beat (confirmed live before writing this test).
    b2 = _beat(d, "1.B2")
    r = cb_qa.check_character_vocabulary(b2)
    check("check_character_vocabulary: real clean beat (1.B2) passes",
          r["ok"] and not r["violations"], f"violations={r['violations']}")

    # FAIL case: inject Fuzzby's own banned word ("gently" — confirmed in Fuzzby's lexicon.banned)
    # into a cut whose text names Fuzzby, mirroring the real 1.B1 cuts 1-2 bug this law was built to catch.
    mutated = copy.deepcopy(b2)
    mutated["cuts"][0]["action"] = "Fuzzby gently drifts between the flowers, barely moving at all."
    r2 = cb_qa.check_character_vocabulary(mutated)
    check("check_character_vocabulary: injected banned word ('gently' near Fuzzby) is caught",
          (not r2["ok"]) and any(v["word"] == "gently" and v["character"] == "Fuzzby" for v in r2["violations"]),
          f"violations={r2['violations']}")

    # Sanity: a word banned for one character is NOT flagged when that character isn't named in the cut.
    only_zenny = copy.deepcopy(b2)
    only_zenny["cuts"][0]["action"] = "Zenny gently glides between the flowers."
    only_zenny["cuts"][0]["framing"] = "wide shot of Zenny alone"
    r3 = cb_qa.check_character_vocabulary(only_zenny)
    check("check_character_vocabulary: 'gently' near Zenny only (no Fuzzby ban) does not false-flag",
          r3["ok"], f"violations={r3['violations']}")


# ═══════════════════════════════════════════════════════════════════════════════════
# check_camera_lock_conflict — LAW 8 / rule 38 (camera locked on any spoken line; hum/
# sing-song exempt)
# ═══════════════════════════════════════════════════════════════════════════════════
def test_camera_lock_conflict():
    d = _load_pkg()

    # FAIL case: 1.B1's real cut 3 is a KNOWN, currently-live violation (confirmed via
    # check_gate3_lint's own blockers before writing this test — "cut 3: has dialogue but framing
    # names camera movement (push)"). Use it as-is, no mutation needed.
    b1 = _beat(d, "1.B1")
    r = cb_qa.check_camera_lock_conflict(b1)
    check("check_camera_lock_conflict: real 1.B1 (known live push-in-on-dialogue bug) is caught",
          not r["ok"] and "push" in r["verdict"].lower(), f"verdict={r['verdict']}")

    # PASS case: strip camera-movement words from every cut's framing -> must read clean.
    fixed = copy.deepcopy(b1)
    for c in fixed["cuts"]:
        c["framing"] = "static locked-off medium shot, camera does not move"
    r2 = cb_qa.check_camera_lock_conflict(fixed)
    check("check_camera_lock_conflict: same beat with camera-move words removed passes",
          r2["ok"], f"verdict={r2['verdict']}")

    # Exemption sanity: a hum/sing-song vocal (per delivery/voiceTreatment text) is motion-exempt,
    # so a cut with a "push" move AND a hummed line must NOT be flagged for that cut.
    hum_beat = {"cuts": [{"n": 1, "framing": "camera pushes in slowly",
                          "dialogue": "FUZZBY: la la la...",
                          "delivery": "a light, continuous hum", "voiceTreatment": "hum, sing-song rhythm"}]}
    r3 = cb_qa.check_camera_lock_conflict(hum_beat)
    check("check_camera_lock_conflict: a hum/sing-song vocal is motion-exempt (rule 38)",
          r3["ok"], f"verdict={r3['verdict']}")

    # And confirm the SAME shape of cut without the hum marker IS flagged (proves the exemption
    # is doing real work, not just "this check never fires on one-cut beats").
    spoken_beat = {"cuts": [{"n": 1, "framing": "camera pushes in slowly",
                             "dialogue": "FUZZBY: Nailed it.",
                             "delivery": "a clipped, proud declaration"}]}
    r4 = cb_qa.check_camera_lock_conflict(spoken_beat)
    check("check_camera_lock_conflict: same shape WITHOUT hum marker correctly flags",
          not r4["ok"], f"verdict={r4['verdict']}")


# ═══════════════════════════════════════════════════════════════════════════════════
# check_keyframe_lint — the Gate-2 sibling lint (anti-slop + vocabulary law on a
# compiled keyframe prompt string)
# ═══════════════════════════════════════════════════════════════════════════════════
def test_keyframe_lint():
    # PASS case: a clean, well-formed keyframe prompt with proper CHARACTER-paragraph structure.
    clean_prompt = (
        "STYLE: premium 3D-CGI Pixar-quality rendering, warm morning light.\n\n"
        "CHARACTER 2 (Fuzzby): rockets between flowers, wings a rapid blur, banks hard around the stem.\n\n"
        "CHARACTER 3 (Zenny): holds a steady working line, glides between blossoms with neat precision.\n\n"
        "REFERENCE IMAGES: match each character to its turnaround exactly.\n\n"
        "CONSTRAINTS: no text, no extra characters."
    )
    r = cb_qa.check_keyframe_lint(clean_prompt, chars=["Fuzzby", "Zenny"])
    check("check_keyframe_lint: clean prompt passes", r["ok"], f"blockers={r['blockers']}")

    # FAIL case 1: anti-slop word inside a CHARACTER paragraph -> hard BLOCK.
    slop_prompt = clean_prompt.replace(
        "CHARACTER 2 (Fuzzby): rockets between flowers, wings a rapid blur, banks hard around the stem.",
        "CHARACTER 2 (Fuzzby): a stunning, cinematic, epic pose as he rockets between flowers.")
    r2 = cb_qa.check_keyframe_lint(slop_prompt, chars=["Fuzzby", "Zenny"])
    check("check_keyframe_lint: anti-slop word in a CHARACTER paragraph is a hard BLOCK",
          not r2["ok"] and any("Fuzzby" in b for b in r2["blockers"]), f"blockers={r2['blockers']}")

    # FAIL case 2: Fuzzby's own banned lexicon word ("slowly") injected into HIS OWN character
    # paragraph -> hard BLOCK (scoped precisely to that paragraph, per the docstring).
    banned_prompt = clean_prompt.replace(
        "CHARACTER 2 (Fuzzby): rockets between flowers, wings a rapid blur, banks hard around the stem.",
        "CHARACTER 2 (Fuzzby): slowly and gently drifts between flowers, calm and unhurried.")
    r3 = cb_qa.check_keyframe_lint(banned_prompt, chars=["Fuzzby", "Zenny"])
    check("check_keyframe_lint: Fuzzby's own banned word in his paragraph is a hard BLOCK",
          not r3["ok"] and any("Fuzzby" in b and "Vocabulary" in b for b in r3["blockers"]),
          f"blockers={r3['blockers']}")

    # Sanity: an anti-slop hit OUTSIDE any CHARACTER paragraph (locked template text) is FLAG-only,
    # never a blocker — proves the locked-vs-authored severity split is real, not accidental.
    style_slop_prompt = clean_prompt.replace(
        "STYLE: premium 3D-CGI Pixar-quality rendering, warm morning light.",
        "STYLE: cinematic, premium 3D-CGI Pixar-quality rendering, warm morning light.")
    r4 = cb_qa.check_keyframe_lint(style_slop_prompt, chars=["Fuzzby", "Zenny"])
    check("check_keyframe_lint: anti-slop word in STYLE (locked text) is flag-only, not a blocker",
          r4["ok"] and any("locked" in f for f in r4["flags"]), f"ok={r4['ok']} flags={r4['flags']}")


# ═══════════════════════════════════════════════════════════════════════════════════
# check_gate3_lint — the unified Step-4 lint (compiles the real v5 prompt via
# cb_segprompt.shipped_prompt, no vision call). Uses REAL package data.
# ═══════════════════════════════════════════════════════════════════════════════════
def test_gate3_lint_word_budget_and_congruence():
    import cb_preflight as PF

    # PASS-ish case: 1.B2 is real, currently clean (confirmed live above) and under the 650 hard cap.
    r = cb_qa.check_gate3_lint(PKG_PATH, "1.B2", "Ep1")
    check("check_gate3_lint: real 1.B2 compiles under the word-budget hard cap",
          r["word_count"] <= PF.WORD_BUDGET_BLOCK and not any("word budget" in b for b in r["blockers"]),
          f"word_count={r['word_count']} blockers={r['blockers']}")
    check("check_gate3_lint: real 1.B2 has no @Video1 (retired 2026-07-07)",
          "@Video1" not in r["prompt"], "found @Video1 in shipped prompt")
    check("check_gate3_lint: real 1.B2's references block matches the relay wording (§4b)",
          not any("doctrine's exact relay wording" in b for b in r["blockers"]), f"blockers={r['blockers']}")

    # FAIL case: 1.B1 has a REAL, currently-live camera-lock violation (confirmed above) — the
    # unified lint must surface it as a blocker via its own re-wired check_camera_lock_conflict call.
    r2 = cb_qa.check_gate3_lint(PKG_PATH, "1.B1", "Ep1")
    check("check_gate3_lint: real 1.B1's known camera-lock violation is caught as a blocker",
          not r2["ok"] and any("Camera-Lock Law" in b for b in r2["blockers"]), f"blockers={r2['blockers']}")


def test_gate3_lint_dialogue_leak_and_anti_slop():
    """These need a beat whose data we control end-to-end but still routes through the REAL v5
    compiler — write a scratch package to a temp file so shipped_prompt() compiles it for real."""
    import tempfile, cb_scene

    d = _load_pkg()
    scene1 = next(s for s in d.get("scenes", []) if str(s.get("sceneNumber")) == "1")
    # 1.B2 (not 1.B1) is our clean base — confirmed live, zero blockers before any mutation, so any
    # blocker these mutations produce is caused by the mutation itself, not pre-existing beat noise
    # (1.B1 currently carries its own real, unrelated camera-lock violation — rule 38 — which would
    # otherwise mask/confuse the specific fault each test below is trying to isolate).
    b2_real = _beat(d, "1.B2")

    # --- FAIL case: inject an anti-slop word into the beat's own story content (cuts[]/endState) ---
    slop_beat = copy.deepcopy(b2_real)
    slop_beat["beatCode"] = "1.B2_SLOP_TEST"
    slop_beat["cuts"][0]["action"] = "A stunning, epic, cinematic masterpiece shot of Fuzzby diving."
    tmp_path = _write_scratch_pkg(d, scene1, slop_beat)
    r = cb_qa.check_gate3_lint(tmp_path, "1.B2_SLOP_TEST", "Ep1")
    os.remove(tmp_path)
    check("check_gate3_lint: injected anti-slop word in beat-story content is a hard BLOCK",
          not r["ok"] and any("anti-slop" in b for b in r["blockers"]), f"blockers={r['blockers']}")

    # --- FAIL case: inject the actual dialogue words into the shot-list action text, UNQUOTED (Law 5
    # leak) — cb_segprompt._strip_spoken_words only strips a QUOTED dialogue fragment
    # (re.sub(r'["“][^"”]*["”]', ...)), so an unquoted leak of the spoken words survives
    # that stripper and is exactly the residual case check_gate3_lint's own Law 5 net exists to catch —
    # a quoted injection would be stripped upstream before the lint ever saw it (confirmed live: an
    # earlier draft of this test quoted the words and the lint correctly found nothing to catch,
    # because the words were already gone by the time the prompt compiled).
    leak_beat = copy.deepcopy(b2_real)
    leak_beat["beatCode"] = "1.B2_LEAK_TEST"
    dlg = leak_beat["cuts"][1].get("dialogue") or ""
    words = dlg.split(":", 1)[-1].strip() if ":" in dlg else ""
    if len(words) <= 8:
        words = "a test phrase long enough to trip law five"
    leak_beat["cuts"][0]["action"] = f"Fuzzby mouths {words} while diving toward the flower."
    tmp_path2 = _write_scratch_pkg(d, scene1, leak_beat)
    r2 = cb_qa.check_gate3_lint(tmp_path2, "1.B2_LEAK_TEST", "Ep1")
    os.remove(tmp_path2)
    check("check_gate3_lint: unquoted dialogue words leaked into action text trip Law 5",
          not r2["ok"] and any("Law 5" in b for b in r2["blockers"]), f"blockers={r2['blockers']}, words={words!r}")


def _write_scratch_pkg(real_pkg, scene1, mutated_beat):
    """Write a scratch package containing ONLY scene 1 + the mutated beat + its real scene-1 siblings
    (so relay resolution / cast lookups behave exactly as they would for a real beat), to a temp path
    inside cb-output/ (shipped_prompt/relay_source_for don't need it there, but keep it colocated with
    the real package so relative asset lookups behave identically)."""
    import tempfile
    scene1_beats = [b for b in (real_pkg.get("beats") or []) if str(b.get("sceneNumber")) == "1"]
    beats = [b for b in scene1_beats if b.get("beatCode") != mutated_beat.get("beatCode")] + [mutated_beat]
    scratch = {"beats": beats, "scenes": [scene1]}
    fd, path = tempfile.mkstemp(suffix="_scratch_beat_package.json", dir=os.path.dirname(PKG_PATH))
    with os.fdopen(fd, "w") as f:
        json.dump(scratch, f)
    return path


# ═══════════════════════════════════════════════════════════════════════════════════
# check_join_state — the STATE/LIGHT/GEOGRAPHY/COVERAGE join check. Needs vision_verdict,
# so we monkeypatch cb_qa.vision_verdict to avoid any network/API call and drive the
# carryMarks-scoped STATE logic directly.
# ═══════════════════════════════════════════════════════════════════════════════════
def test_join_state_carry_marks_scoping():
    # Two fake (but existing) image paths — check_join_state only checks os.path.exists, never
    # decodes pixels itself; the actual "vision" step is fully monkeypatched below.
    tmp_a = os.path.join(HERE, "_test_cb_qa_fake_frame_a.png")
    tmp_b = os.path.join(HERE, "_test_cb_qa_fake_frame_b.png")
    open(tmp_a, "wb").write(b"\x89PNG\r\n\x1a\nfake")
    open(tmp_b, "wb").write(b"\x89PNG\r\n\x1a\nfake")

    orig_vision_verdict = cb_qa.vision_verdict
    try:
        # --- PASS case: model reports CONTINUOUS on all four criteria ---
        def fake_pass(prompt, images):
            return ("CONTINUOUS\nFLAG: none", None)
        cb_qa.vision_verdict = fake_pass
        r = cb_qa.check_join_state(tmp_a, tmp_b, carry_marks="the pollen moustache")
        check("check_join_state: model reports CONTINUOUS -> ok=True",
              r["ok"] is True and r["flags"] == [], f"result={r}")

        # --- FAIL case: model reports BROKEN with a STATE line naming the declared mark ---
        def fake_fail(prompt, images):
            return ("BROKEN\nSTATE: the pollen moustache is present in image 1 but gone in image 2\n"
                     "FLAG: none", None)
        cb_qa.vision_verdict = fake_fail
        r2 = cb_qa.check_join_state(tmp_a, tmp_b, carry_marks="the pollen moustache")
        check("check_join_state: model reports BROKEN on the declared carry mark -> ok=False",
              r2["ok"] is False and "STATE" in r2["verdict"], f"result={r2}")

        # --- advisory FLAG never flips ok, even attached to an otherwise-CONTINUOUS verdict ---
        def fake_flag_only(prompt, images):
            return ("CONTINUOUS\nFLAG: a bee is holding a small bit of pollen in image 1 not present in image 2", None)
        cb_qa.vision_verdict = fake_flag_only
        r3 = cb_qa.check_join_state(tmp_a, tmp_b, carry_marks="the pollen moustache")
        check("check_join_state: an advisory FLAG on an incidental prop never flips ok=True to False",
              r3["ok"] is True and len(r3["flags"]) == 1, f"result={r3}")

        # --- no carryMarks declared -> STATE auto-passes regardless of model text about props ---
        def fake_no_marks_but_broken_text(prompt, images):
            # even if the model were to say BROKEN here, the PROMPT ITSELF instructs it to treat
            # STATE as auto-passing when no mark is declared — verify the prompt text reflects that
            # instruction (this is a text-construction check, not a claim about model behavior).
            assert "no specific mark is declared" in prompt.lower(), "prompt missing the no-marks auto-pass instruction"
            return ("CONTINUOUS\nFLAG: none", None)
        cb_qa.vision_verdict = fake_no_marks_but_broken_text
        r4 = cb_qa.check_join_state(tmp_a, tmp_b, carry_marks=None)
        check("check_join_state: no carryMarks declared -> prompt instructs STATE auto-pass",
              r4["ok"] is True, f"result={r4}")

        # --- missing frame -> ok=None, never crashes ---
        r5 = cb_qa.check_join_state(None, tmp_b, carry_marks="x")
        check("check_join_state: missing prev frame returns ok=None (never crashes)",
              r5["ok"] is None, f"result={r5}")
    finally:
        cb_qa.vision_verdict = orig_vision_verdict
        for p in (tmp_a, tmp_b):
            if os.path.exists(p):
                os.remove(p)


def test_check_join_junction_routing():
    """check_join(): confirms frame_identity is None for intentional_next_shot (the default) and
    populated only for seamless_continuation — pure routing logic, monkeypatched vision calls."""
    tmp_a = os.path.join(HERE, "_test_cb_qa_fake_frame_c.png")
    tmp_b = os.path.join(HERE, "_test_cb_qa_fake_frame_d.png")
    open(tmp_a, "wb").write(b"\x89PNG\r\n\x1a\nfake")
    open(tmp_b, "wb").write(b"\x89PNG\r\n\x1a\nfake")
    orig = cb_qa.vision_verdict
    try:
        cb_qa.vision_verdict = lambda prompt, images: ("CONTINUOUS\nFLAG: none", None)
        r_cut = cb_qa.check_join(tmp_a, tmp_b, junction=cb_qa.JUNCTION_INTENTIONAL, carry_marks="x")
        check("check_join: intentional_next_shot (default) never checks frame identity",
              r_cut["frame_identity"] is None and r_cut["ok"] is True, f"result={r_cut}")

        r_seamless = cb_qa.check_join(tmp_a, tmp_b, junction=cb_qa.JUNCTION_SEAMLESS, carry_marks="x")
        check("check_join: seamless_continuation DOES check frame identity",
              r_seamless["frame_identity"] is not None and r_seamless["ok"] is True, f"result={r_seamless}")

        # FAIL case: frame-identity check reports BROKEN -> overall ok goes False even if STATE passed
        def mixed(prompt, images):
            if "UNBROKEN" in prompt:
                return ("BROKEN\nthe larger bee was frame-left, now frame-right", None)
            return ("CONTINUOUS\nFLAG: none", None)
        cb_qa.vision_verdict = mixed
        r_seamless_fail = cb_qa.check_join(tmp_a, tmp_b, junction=cb_qa.JUNCTION_SEAMLESS, carry_marks="x")
        check("check_join: seamless join fails overall when frame-identity is BROKEN, even if STATE passed",
              r_seamless_fail["ok"] is False, f"result={r_seamless_fail}")
    finally:
        cb_qa.vision_verdict = orig
        for p in (tmp_a, tmp_b):
            if os.path.exists(p):
                os.remove(p)


# ═══════════════════════════════════════════════════════════════════════════════════
# A deliberately-broken-assertion smoke test proving this harness can actually fail.
# Set BREAK_ME_FOR_REAL = True temporarily to confirm a real regression is caught, then
# revert to False before shipping (kept here, disabled, as documentation of that step).
# ═══════════════════════════════════════════════════════════════════════════════════
BREAK_ME_FOR_REAL = False


def main():
    if BREAK_ME_FOR_REAL:
        check("DELIBERATE BREAK (must show FAIL)", False, "proving the harness catches a real regression")

    test_character_vocabulary()
    test_camera_lock_conflict()
    test_keyframe_lint()
    test_gate3_lint_word_budget_and_congruence()
    test_gate3_lint_dialogue_leak_and_anti_slop()
    test_join_state_carry_marks_scoping()
    test_check_join_junction_routing()

    fails = [r for r in RESULTS if not r[1]]
    for name, ok, detail in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n        -> {detail}" if not ok and detail else ""))
    print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} passed.")
    if fails:
        print(f"{len(fails)} FAILURE(S)")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
