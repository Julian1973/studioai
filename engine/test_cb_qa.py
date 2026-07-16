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

    # FIX REGRESSION (2026-07-08/09, HIGH-severity, confirmed and fixed): a shorter cast name that is
    # ALSO a literal substring of a longer, co-present cast name (e.g. "Keen" inside "Keen's Mum") used
    # to get its own spurious name_positions entry at the SAME text offset as the real longer-name match.
    # A tied-distance min() then resolved to whichever was appended FIRST — the shorter name, since it
    # iterated earlier in the cast list — silently misattributing a violation that really belonged to
    # the longer name's own character (here: Keen's Mum's own "anxious"/"calm down" bans, both of which
    # happen to overlap Keen's own banned list in the real characters.json data, making this a real,
    # not hypothetical, collision). The fix processes cast names longest-first and skips any match whose
    # span falls entirely inside a span already claimed by a longer name.
    keen_mum_cut = {
        "openingCast": ["Keen", "Keen's Mum", "Zenny"],
        "cuts": [
            {"framing": "medium on Mum", "action": "Keen's Mum grows anxious, calm down, near the ropes."}
        ],
    }
    r4 = cb_qa.check_character_vocabulary(keen_mum_cut)
    check("check_character_vocabulary: 'Keen' substring inside 'Keen's Mum' attributes correctly to Keen's Mum, not Keen",
          (not r4["ok"])
          and all(v["character"] == "Keen's Mum" for v in r4["violations"])
          and any(v["word"] == "anxious" for v in r4["violations"])
          and any(v["word"] == "calm down" for v in r4["violations"]),
          f"violations={r4['violations']}")

    # GAP CLOSED (2026-07-09): every case above has AT MOST ONE named character in the cut's text, so
    # the OLD whole-cut/"named anywhere" attribution logic and the NEW nearest-name-by-position logic
    # (see the docstring's "ATTRIBUTION — NEAREST-NAME, NOT WHOLE-CUT" paragraph) produce IDENTICAL
    # results on all of them — this suite could not actually distinguish the pre-fix and post-fix
    # implementations, and a regression back to whole-cut attribution would have passed cleanly. These
    # two cases both name BOTH Fuzzby and Zenny in the same cut (Zenny's own lexicon.banned is empty —
    # she owns no banned words, only Fuzzby does), so the two implementations diverge: whole-cut logic
    # flags Fuzzby's banned "gently" any time his name is anywhere in the cut; nearest-name logic only
    # flags it when Fuzzby's own mention is the textually closest name to the word. Both sentences were
    # confirmed empirically against the live implementation before being committed as permanent asserts
    # (word choice/spacing determines which name reads "nearest" — never assumed).

    # Both named, "gently" sits textually NEAREST to Zenny (who owns no banned words) -> not Fuzzby's
    # violation; nearest-name logic passes clean where whole-cut logic would have wrongly flagged Fuzzby.
    near_zenny = copy.deepcopy(b2)
    near_zenny["cuts"][0]["framing"] = "wide two-shot, both bees in frame"
    near_zenny["cuts"][0]["action"] = "Fuzzby rockets toward the next flower as Zenny gently glides in beside him."
    r5 = cb_qa.check_character_vocabulary(near_zenny)
    check("check_character_vocabulary: both named, 'gently' nearest Zenny -> no Fuzzby violation (nearest-name, not whole-cut)",
          r5["ok"] and not r5["violations"], f"violations={r5['violations']}")

    # Both named, "gently" sits textually NEAREST to Fuzzby despite Zenny also being present in the same
    # cut -> still correctly Fuzzby's violation (proves the fix doesn't over-correct into never flagging
    # a genuine same-character hit just because another name co-occurs in the cut).
    near_fuzzby = copy.deepcopy(b2)
    near_fuzzby["cuts"][0]["framing"] = "wide two-shot, both bees in frame"
    near_fuzzby["cuts"][0]["action"] = "Zenny glides steadily nearby as Fuzzby gently drifts toward the next flower."
    r6 = cb_qa.check_character_vocabulary(near_fuzzby)
    check("check_character_vocabulary: both named, 'gently' nearest Fuzzby -> Fuzzby violation still caught",
          (not r6["ok"]) and any(v["word"] == "gently" and v["character"] == "Fuzzby" for v in r6["violations"]),
          f"violations={r6['violations']}")


# ═══════════════════════════════════════════════════════════════════════════════════
# check_camera_lock_conflict — LAW 8 / rule 38 (camera locked on any spoken line; hum/
# sing-song exempt)
# ═══════════════════════════════════════════════════════════════════════════════════
def test_camera_lock_conflict():
    d = _load_pkg()

    # REGRESSION GUARD (2026-07-14): 1.B1's cut 3 used to be a real, live violation ("push-in" on
    # its own dialogue cut, "Nailed it.") — found and fixed the same night check_gate3_lint's own
    # blockers were, for the first time, actually wired into cb_beats.run() itself (previously only
    # cb_replicator.walk_scene enforced this check; a beat fired via cb_beats.run() directly — a
    # scratch script, a Studio button — never saw it). Fixing that gap surfaced this real violation
    # across 9 beats package-wide; all were fixed the same session. This assertion now guards the
    # fix stays fixed, rather than asserting the historical bug (the synthetic FAIL case below
    # already proves detection works, independent of this beat's own current data).
    b1 = _beat(d, "1.B1")
    r = cb_qa.check_camera_lock_conflict(b1)
    check("check_camera_lock_conflict: real 1.B1's own camera-lock violation stays fixed (regression guard)",
          r["ok"], f"verdict={r['verdict']}")

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

    # FAIL case 3 (2026-07-15, Julian, live — "guardrails... to bring that beat to life... not guardrails
    # for anything else"): the `_pose()` fallback ("{Name} is in frame, mid-action") is cb_prompts.py's own
    # unattributed-character marker — confirmed live to fire on 47% of character blocks in real ensemble
    # scene-openers (9.B1, 10.B1). A named character shipping this generic fallback is a hard BLOCK.
    fallback_prompt = clean_prompt.replace(
        "CHARACTER 3 (Zenny): holds a steady working line, glides between blossoms with neat precision.",
        "CHARACTER 3 (Zenny): Zenny is in frame, mid-action.")
    r5 = cb_qa.check_keyframe_lint(fallback_prompt, chars=["Fuzzby", "Zenny"])
    check("check_keyframe_lint: the unattributed-character fallback is a hard BLOCK, naming the character",
          not r5["ok"] and any("Zenny" in b and "Unattributed" in b for b in r5["blockers"]),
          f"blockers={r5['blockers']}")

    # Sanity: real, specific staging text that merely CONTAINS the words "in frame" must never false-positive
    # — only the EXACT fallback phrase ("{Name} is in frame, mid-action") trips this check.
    real_staging_prompt = clean_prompt.replace(
        "CHARACTER 3 (Zenny): holds a steady working line, glides between blossoms with neat precision.",
        "CHARACTER 3 (Zenny): Zenny is in frame, sharply focused on the flower ahead of her.")
    r6 = cb_qa.check_keyframe_lint(real_staging_prompt, chars=["Fuzzby", "Zenny"])
    check("check_keyframe_lint: real staging text containing 'in frame' never false-positives on the fallback check",
          r6["ok"], f"blockers={r6['blockers']}")


# ═══════════════════════════════════════════════════════════════════════════════════
# check_retake_prompt — THE GATE-4 SIBLING (2026-07-14, CLAUDE.md rule 84/85): closes the confirmed gap
# where cb_retake.regen_shot's own _shot_fix_prompt dict shipped with zero anti-slop/Character Vocabulary
# Law enforcement — neither check_gate3_lint nor check_keyframe_lint is directly reusable on this shape.
# ═══════════════════════════════════════════════════════════════════════════════════
def test_check_retake_prompt():
    clean = {"subject": "Crystal Cove — Fuzzby, Zenny", "continuity": "Match the exact frame.",
             "action": "Fuzzby rockets forward and slams into the leaf.", "camera": "wide tracking shot",
             "style": "Warm saturated light, bold legible staging.", "negative": "no crystals on the bees"}
    r = cb_qa.check_retake_prompt(clean, characters=["Fuzzby", "Zenny"])
    check("check_retake_prompt: a clean retake prompt passes", r["ok"], f"blockers={r['blockers']}")

    # anti-slop word in the freely-authored action text -> hard BLOCK
    slop = dict(clean, action="Fuzzby rockets forward in a cinematic, epic dive into the leaf.")
    r2 = cb_qa.check_retake_prompt(slop, characters=["Fuzzby", "Zenny"])
    check("check_retake_prompt: anti-slop word in the retake's own action text is a hard BLOCK",
          not r2["ok"] and any("cinematic" in b for b in r2["blockers"]), f"blockers={r2['blockers']}")

    # Fuzzby's own banned lexicon word ("gently") in HIS retake action -> hard BLOCK
    vocab = dict(clean, action="Fuzzby gently lands on the branch.")
    r3 = cb_qa.check_retake_prompt(vocab, characters=["Fuzzby"])
    check("check_retake_prompt: Fuzzby's own banned word in his retake action is a hard BLOCK",
          not r3["ok"] and any("Fuzzby" in b and "Vocabulary" in b for b in r3["blockers"]),
          f"blockers={r3['blockers']}")

    # anti-slop word inside the LOCKED style field (cb_segprompt._style()'s own text) -> FLAG only
    style_slop = dict(clean, style="A cinematic, stylised look.")
    r4 = cb_qa.check_retake_prompt(style_slop, characters=["Fuzzby", "Zenny"])
    check("check_retake_prompt: anti-slop word in the locked style field is flag-only, not a blocker",
          r4["ok"] and any("locked style" in f for f in r4["flags"]), f"ok={r4['ok']} flags={r4['flags']}")

    # a genuinely empty/malformed prompt dict never raises
    try:
        r5 = cb_qa.check_retake_prompt({}, characters=None)
        check("check_retake_prompt: an empty/malformed prompt dict never raises", r5["ok"] is True)
    except Exception as e:
        check("check_retake_prompt: an empty/malformed prompt dict never raises", False, f"raised {e!r}")


# ═══════════════════════════════════════════════════════════════════════════════════
# check_gate3_lint — the unified Step-4 lint (compiles the real v5 prompt via
# cb_segprompt.shipped_prompt, no vision call). Uses REAL package data.
# ═══════════════════════════════════════════════════════════════════════════════════
def test_gate3_lint_word_budget_and_congruence():
    import cb_preflight as PF

    # PASS-ish case: 1.B2 is real, currently clean (confirmed live above) and under the hard cap
    # (PF.WORD_BUDGET_BLOCK, 700 as of 2026-07-14 rule 84/85 — read live below, never a hand-typed number).
    r = cb_qa.check_gate3_lint(PKG_PATH, "1.B2", "Ep1")
    check("check_gate3_lint: real 1.B2 compiles under the word-budget hard cap",
          r["word_count"] <= PF.WORD_BUDGET_BLOCK and not any("word budget" in b for b in r["blockers"]),
          f"word_count={r['word_count']} blockers={r['blockers']}")
    check("check_gate3_lint: real 1.B2 has no @Video1 (retired 2026-07-07)",
          "@Video1" not in r["prompt"], "found @Video1 in shipped prompt")
    check("check_gate3_lint: real 1.B2's references block matches the relay wording (§4b)",
          not any("doctrine's exact relay wording" in b for b in r["blockers"]), f"blockers={r['blockers']}")

    # REGRESSION GUARD (2026-07-14): 1.B1's camera-lock violation (see test_camera_lock_conflict's
    # own note) is fixed; check_gate3_lint must report it clean via the SAME re-wired
    # check_camera_lock_conflict call, matching that other test's own regression-guard shape.
    r2 = cb_qa.check_gate3_lint(PKG_PATH, "1.B1", "Ep1")
    check("check_gate3_lint: real 1.B1's camera-lock violation stays fixed (regression guard)",
          not any("Camera-Lock Law" in b for b in r2["blockers"]), f"blockers={r2['blockers']}")


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


def test_gate3_lint_checklist_verb_flag():
    """THE MOTION CONTRACT check (2026-07-13, the CapCut-formula deep-dive) — a cut whose action reads as
    4+ comma-separated, independently-clocked verbs (a checklist of poses) should surface as an advisory
    FLAG, never a hard block (it's a computed proxy for a real risk, not a semantic judge of true causation
    — the same "report, never block a proxy" convention this codebase already uses elsewhere). A genuine
    one-cause/chained-consequences sentence, even a long one, should NOT trip it — the check counts comma
    fragments, not sentence length, so this also guards against a false-positive regression."""
    d = _load_pkg()
    scene1 = next(s for s in d.get("scenes", []) if str(s.get("sceneNumber")) == "1")
    b2_real = _beat(d, "1.B2")

    # --- FLAG case: 5 independently-clocked, comma-separated actions (the confirmed real-world shape) ---
    checklist_beat = copy.deepcopy(b2_real)
    checklist_beat["beatCode"] = "1.B2_CHECKLIST_TEST"
    checklist_beat["cuts"][0]["action"] = (
        "He bounces off, spins once in mid-air, stabilizes himself, puffs out his chest proudly, and lands."
    )
    tmp_path = _write_scratch_pkg(d, scene1, checklist_beat)
    r = cb_qa.check_gate3_lint(tmp_path, "1.B2_CHECKLIST_TEST", "Ep1")
    os.remove(tmp_path)
    check("check_gate3_lint: a 5-fragment checklist action surfaces an advisory flag, never a block",
          any("separately-clocked actions" in f for f in r["flags"]),
          f"flags={r['flags']}")
    check("check_gate3_lint: the checklist flag never adds to blockers (it's a proxy, not a semantic judge)",
          not any("separately-clocked" in b for b in r["blockers"]), f"blockers={r['blockers']}")

    # --- CLEAN case: one cause with chained consequences in a single sentence, no comma-listed verbs ---
    chained_beat = copy.deepcopy(b2_real)
    chained_beat["beatCode"] = "1.B2_CHAINED_TEST"
    chained_beat["cuts"][0]["action"] = (
        "His own momentum shoots him sideways into the broad leaf; the leaf snaps under the hit and the "
        "impact spins him a full turn before he catches himself on the rebound."
    )
    tmp_path2 = _write_scratch_pkg(d, scene1, chained_beat)
    r2 = cb_qa.check_gate3_lint(tmp_path2, "1.B2_CHAINED_TEST", "Ep1")
    os.remove(tmp_path2)
    # scoped to cut 1 specifically (the mutated one) — 1.B2's OTHER real, untouched cuts may legitimately
    # carry their own checklist-shaped text and correctly flag on their own merits; that's not this test's
    # concern, only whether a genuinely chained sentence in cut 1 avoids a false positive.
    check("check_gate3_lint: a chained cause-and-consequence sentence in cut 1 does not trip the checklist flag on cut 1",
          not any("cut 1:" in f and "separately-clocked actions" in f for f in r2["flags"]), f"flags={r2['flags']}")


def test_gate3_lint_archetype_completeness_contract():
    """THE ARCHETYPE COMPLETENESS CONTRACT (2026-07-14, Julian: "we have a structure and template and we
    must ensure it meets that through the storyboard... what I don't understand is you see it after the
    event but not before"). The exact regression this check exists to catch: a real, live bug earlier THIS
    SESSION silently dropped the archetype's own protective negative phrases from the shipped Negative line
    whenever a physics anchor also existed — nothing caught it until Fuzzby actually vanished into a flower
    on real, billed footage (1.B2). This proves the check catches that EXACT regression class before any
    prompt fires, by monkeypatching the compiler functions to reproduce the broken wiring directly (data-
    level mutation alone can't simulate a wiring break — the bug lived in the compiler, not the beat data)."""
    import cb_segprompt as CS

    # both halves clean on the real, currently-fixed 1.B1/1.B2 (regression guard: the fix stays fixed)
    r_b1 = cb_qa.check_gate3_lint(PKG_PATH, "1.B1", "Ep1")
    check("check_gate3_lint: real 1.B1 passes the Archetype Completeness Contract clean",
          not any("Archetype Completeness Contract" in b for b in r_b1["blockers"]), f"blockers={r_b1['blockers']}")
    r_b2 = cb_qa.check_gate3_lint(PKG_PATH, "1.B2", "Ep1")
    check("check_gate3_lint: real 1.B2 passes the Archetype Completeness Contract clean",
          not any("Archetype Completeness Contract" in b for b in r_b2["blockers"]), f"blockers={r_b2['blockers']}")

    # --- FAIL case: reproduce tonight's exact regression — the negative-line compiler silently drops the
    # archetype's own prohibited phrases (the resolver itself still works fine; only the WIRING breaks) ---
    _orig_neg = CS._v5_negative_line
    def _broken_negative_line(beat, scene):
        staging = [str(x).strip() for x in (beat.get("stagingProhibited") or []) if str(x).strip()]
        staging = [s if CS._NEGATION_LEAD_RE.match(s) else f"no {CS._LEADING_ARTICLE_RE.sub('', s)}" for s in staging]
        return "Negative: " + "; ".join(staging + CS._standing_negatives()) + "."
    CS._v5_negative_line = _broken_negative_line
    try:
        r = cb_qa.check_gate3_lint(PKG_PATH, "1.B2", "Ep1")
    finally:
        CS._v5_negative_line = _orig_neg
    check("check_gate3_lint: a silently-broken negative-line wiring is a hard BLOCK (the exact 1.B2 regression)",
          not r["ok"] and any("Archetype Completeness Contract" in b and "prohibited staging" in b for b in r["blockers"]),
          f"ok={r['ok']} blockers={r['blockers']}")

    # --- FAIL case: the positive half — the physics anchor silently drops out of the shot-list compiler ---
    _orig_story = CS._v5_beat_story
    def _broken_beat_story(beat, cast, scene=None, episode="Ep1"):
        out = _orig_story(beat, cast, scene, episode)
        return "\n".join(l for l in out.split("\n") if not l.startswith("PHYSICS:"))
    CS._v5_beat_story = _broken_beat_story
    try:
        r2 = cb_qa.check_gate3_lint(PKG_PATH, "1.B1", "Ep1")
    finally:
        CS._v5_beat_story = _orig_story
    check("check_gate3_lint: a silently-dropped PHYSICS anchor is a hard BLOCK",
          not r2["ok"] and any("Archetype Completeness Contract" in b and "PHYSICS anchor" in b for b in r2["blockers"]),
          f"ok={r2['ok']} blockers={r2['blockers']}")

    # --- NO FALSE POSITIVE: a beat-authored stagingProhibited item that already covers an archetype phrase
    # (case-insensitive substring, mirroring _v5_negative_line's own dedup) must not be reported as missing,
    # even though it never appears verbatim in the shipped Negative line under the archetype's own phrasing ---
    d = _load_pkg()
    scene1 = next(s for s in d.get("scenes", []) if str(s.get("sceneNumber")) == "1")
    b1_real = _beat(d, "1.B1")
    archetype_phrases = CS._v5_archetype_prohibited(b1_real, scene1)
    if archetype_phrases:
        covered_beat = copy.deepcopy(b1_real)
        covered_beat["beatCode"] = "1.B1_COVERED_TEST"
        covered_beat["stagingProhibited"] = [archetype_phrases[0]]
        tmp_path = _write_scratch_pkg(d, scene1, covered_beat)
        r3 = cb_qa.check_gate3_lint(tmp_path, "1.B1_COVERED_TEST", "Ep1")
        os.remove(tmp_path)
        check("check_gate3_lint: a beat-authored phrase already covering the archetype's own is never a false-positive BLOCK",
              not any("Archetype Completeness Contract" in b and "prohibited staging" in b for b in r3["blockers"]),
              f"blockers={r3['blockers']}")


def test_prompt_before_fire_wiring():
    """THE PRE-FIRE READ (2026-07-14, Julian: "if you read the prompts before they go for render we
    wouldn't have these issues... we need to fix software wide not prompt specific"). The check itself
    calls a real LLM (cb_llm.structured) — these tests prove the WIRING (caching, blocker formatting,
    fail-open on infra failure) with cb_llm.structured monkeypatched, zero API cost. The check's actual
    JUDGMENT QUALITY (does it correctly tell a deliberate settle resolution from an accidental
    contradiction) was proven separately against real production data — see CLAUDE.md's own dated record
    of the live 1.B2 finding and fix; that class of proof needs a real model call and isn't something a
    mock can meaningfully verify (a mock only ever returns what the test tells it to)."""
    import cb_llm, shutil

    if os.path.exists(cb_qa._PROMPT_READ_CACHE_DIR):
        shutil.rmtree(cb_qa._PROMPT_READ_CACHE_DIR)
    orig = cb_llm.structured

    class _FakeVerdict:
        def __init__(self, **kw): self.__dict__.update(kw)
        def model_dump(self): return dict(self.__dict__)

    try:
        # clean verdict -> ok=True, no blockers
        cb_llm.structured = lambda system, user, schema, **kw: _FakeVerdict(
            continuity_honored=True, continuity_reason="opens on the carried state",
            staging_honors_negatives=True, staging_reason="no contradiction",
            settle_honors_negatives=True, settle_reason="no contradiction")
        r1 = cb_qa.check_prompt_before_fire("PROMPT ONE", "TEST.WIRE1", "Ep1")
        check("check_prompt_before_fire: a clean verdict passes with no blockers",
              r1["ok"] and not r1["blockers"] and not r1["skipped"], r1)

        # a real contradiction -> ok=False, a specific, quotable blocker
        cb_llm.structured = lambda system, user, schema, **kw: _FakeVerdict(
            continuity_honored=False, continuity_reason="opening ignores the anchor, jumps to a wide shot",
            staging_honors_negatives=True, staging_reason="fine",
            settle_honors_negatives=True, settle_reason="fine")
        r2 = cb_qa.check_prompt_before_fire("PROMPT TWO", "TEST.WIRE2", "Ep1")
        check("check_prompt_before_fire: a real contradiction is a hard block with the specific reason quoted",
              not r2["ok"] and any("ignores the anchor" in b for b in r2["blockers"]), r2)

        # identical (prompt, beat) pair -> cached, LLM called exactly once for two calls
        called = {"n": 0}
        def _counting(system, user, schema, **kw):
            called["n"] += 1
            return _FakeVerdict(continuity_honored=True, continuity_reason="x", staging_honors_negatives=True,
                                 staging_reason="x", settle_honors_negatives=True, settle_reason="x")
        cb_llm.structured = _counting
        cb_qa.check_prompt_before_fire("CACHE TEST PROMPT", "TEST.WIRE3", "Ep1")
        cb_qa.check_prompt_before_fire("CACHE TEST PROMPT", "TEST.WIRE3", "Ep1")
        check("check_prompt_before_fire: identical prompt+beat is cached, not re-billed",
              called["n"] == 1, f"called {called['n']} times, expected 1")

        # a genuine infra outage (both providers down) fails OPEN, never silently a pass or a block
        def _outage(system, user, schema, **kw):
            raise SystemExit("both providers down")
        cb_llm.structured = _outage
        r4 = cb_qa.check_prompt_before_fire("OUTAGE TEST PROMPT", "TEST.WIRE4", "Ep1")
        check("check_prompt_before_fire: an infra outage fails open, marked skipped with a reason",
              r4["ok"] and r4["skipped"] and r4.get("skipped_reason"), r4)
    finally:
        cb_llm.structured = orig
        if os.path.exists(cb_qa._PROMPT_READ_CACHE_DIR):
            shutil.rmtree(cb_qa._PROMPT_READ_CACHE_DIR)


def test_reference_position():
    """THE SEAM AUDIT'S HIGH-severity finding (2026-07-15, Gate 1->2->3 handoff review): check_prompt_before_
    fire (above) reads the compiled TEXT only — nothing ever checked the references block's own hand-authored
    position claims (spatialAxis/relayOpeningNote, CLAUDE.md rule 53) or the size clause
    (cb_segprompt._v5_size_clause) against the actual anchor image cb_beats.run uploads as @图1. Needs
    vision_verdict, so monkeypatched here — zero network/API cost, same convention as check_join_state's own
    tests above."""
    import tempfile
    orig_vision_verdict = cb_qa.vision_verdict
    fd, tmp = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        # no anchor path at all -> skip (ok=None), no vision call possible
        r0 = cb_qa.check_reference_position({}, [], None)
        check("check_reference_position: no anchor path -> ok=None (skip)", r0["ok"] is None, r0)

        # anchor exists but no spatialAxis/relayOpeningNote and a single-character cast (no size claim
        # either, since a size clause needs 2+ distinct sizeRanks) -> nothing to check, zero vision calls
        called = {"n": 0}
        def _counting(prompt, images):
            called["n"] += 1
            return "MATCH", None
        cb_qa.vision_verdict = _counting
        r1 = cb_qa.check_reference_position({}, ["Fuzzby"], tmp)
        check("check_reference_position: no claim authored -> ok=None, zero vision calls spent",
              r1["ok"] is None and called["n"] == 0, r1)

        # a real position claim + a MATCH verdict -> ok=True
        cb_qa.vision_verdict = lambda prompt, images: ("MATCH", None)
        r2 = cb_qa.check_reference_position({"spatialAxis": "Fuzzby frame-left, Zenny frame-right"},
                                             ["Fuzzby", "Zenny"], tmp)
        check("check_reference_position: a MATCH verdict -> ok=True", r2["ok"] is True, r2)

        # a real position claim + a MISMATCH verdict -> ok=False, the contradiction is surfaced
        cb_qa.vision_verdict = lambda prompt, images: (
            "MISMATCH\nspatialAxis: Fuzzby frame-left, Zenny frame-right — the image shows them swapped", None)
        r3 = cb_qa.check_reference_position({"spatialAxis": "Fuzzby frame-left, Zenny frame-right"},
                                             ["Fuzzby", "Zenny"], tmp)
        check("check_reference_position: a MISMATCH verdict -> ok=False, the contradiction is quoted",
              r3["ok"] is False and "swapped" in r3["verdict"], r3)

        # a vision-infra error skips (ok=None) — never a false pass or a false block
        cb_qa.vision_verdict = lambda prompt, images: (None, "(QA model error 503)")
        r4 = cb_qa.check_reference_position({"spatialAxis": "x"}, ["Fuzzby", "Zenny"], tmp)
        check("check_reference_position: a vision-infra error skips (ok=None)", r4["ok"] is None, r4)
    finally:
        cb_qa.vision_verdict = orig_vision_verdict
        if os.path.exists(tmp):
            os.remove(tmp)


def test_framing_mismatch():
    """FRAMING_MISMATCH (2026-07-15, seam audit — Gate 1->2->3 handoff review): check_done_frame's PLATE_
    DRIFT item checks the WORLD matches the plate; nothing checked the actual shot SCALE the Director called
    for in cuts[0].framing (the same field cb_prompts.build_keyframe_prompt reads to build the COMPOSITION
    line) — a keyframe could pass every other item while still being the wrong shot scale. Uses the same
    unparseable-fake-PNG convention test_cb_beats.py already uses for a resolution-check-free fixture (the
    deterministic LOW_RESOLUTION/BAD_ASPECT checks degrade to skipped on a file _img_size can't parse, never
    crash), and monkeypatches vision_verdict — zero network/API cost."""
    import tempfile
    orig_vision_verdict = cb_qa.vision_verdict
    fd, kf = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    open(kf, "wb").write(b"\x89PNG\r\n\x1a\nfake")
    try:
        # a beat with a real cuts[0].framing -> the checklist offers FRAMING_MISMATCH, naming the exact term
        captured = {}
        def _capture(prompt, images):
            captured["prompt"] = prompt
            return "PASS", None
        cb_qa.vision_verdict = _capture
        shot = {"characters": [], "cuts": [{"framing": "wide shot"}]}
        r1 = cb_qa.check_done_frame(shot, kf, {}, "Ep1", is_end=False)
        check("check_done_frame: FRAMING_MISMATCH is offered on the START frame when cuts[0].framing is authored",
              "FRAMING_MISMATCH" in captured.get("prompt", ""), captured.get("prompt", "")[:200])
        check("check_done_frame: the checklist item states the actual authored framing text",
              "wide shot" in captured.get("prompt", ""), captured.get("prompt", "")[:200])
        check("check_done_frame: a clean PASS verdict passes (ok=True)", r1["ok"] is True, r1)

        # the model actually flags FRAMING_MISMATCH -> surfaces as a real failed reason
        cb_qa.vision_verdict = lambda prompt, images: (
            "FAIL\nFRAMING_MISMATCH: this is a close-up, not the stated wide shot", None)
        r2 = cb_qa.check_done_frame(shot, kf, {}, "Ep1", is_end=False)
        check("check_done_frame: a real FRAMING_MISMATCH flag from the model surfaces as a failed reason",
              r2["ok"] is False and "FRAMING_MISMATCH" in r2["reasons"], r2)

        # no framing authored at all -> the item is never offered (nothing to check against a fallback default)
        captured2 = {}
        def _capture2(prompt, images):
            captured2["prompt"] = prompt
            return "PASS", None
        cb_qa.vision_verdict = _capture2
        shot_no_framing = {"characters": [], "cuts": [{}]}
        cb_qa.check_done_frame(shot_no_framing, kf, {}, "Ep1", is_end=False)
        check("check_done_frame: FRAMING_MISMATCH is skipped when no framing was authored",
              "FRAMING_MISMATCH" not in captured2.get("prompt", ""), captured2.get("prompt", "")[:200])

        # scoped to the START frame only — cuts[0] is the OPENING cut; the END frame check never asks it
        captured3 = {}
        def _capture3(prompt, images):
            captured3["prompt"] = prompt
            return "PASS", None
        cb_qa.vision_verdict = _capture3
        cb_qa.check_done_frame(shot, kf, {}, "Ep1", is_end=True)
        check("check_done_frame: FRAMING_MISMATCH is scoped to the START frame only, never the END frame",
              "FRAMING_MISMATCH" not in captured3.get("prompt", ""), captured3.get("prompt", "")[:200])
    finally:
        cb_qa.vision_verdict = orig_vision_verdict
        if os.path.exists(kf):
            os.remove(kf)


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
def test_clip_composition_loop_advisory_only():
    # CLIP_COMPOSITION_LOOP (2026-07-14, diagnosing 1.B3's real rendered failure — the take opened and
    # closed on nearly the identical branch composition, undetected until watched). Two guarantees to
    # prove: (1) the design promise that this code can NEVER block a take, checked against the actual
    # set membership, not just trusted from reading the code; (2) _passB's own vision-call parsing
    # correctly recognizes the code when the model reports it.
    check("CLIP_COMPOSITION_LOOP is never in CLIP_BLOCK_CODES (design guarantee: advisory-only, never blocks)",
          "CLIP_COMPOSITION_LOOP" not in cb_qa.CLIP_BLOCK_CODES, cb_qa.CLIP_BLOCK_CODES)
    check("CLIP_COMPOSITION_LOOP is not in CLIP_CORROBORATE (single signal is enough to surface, since it never blocks)",
          "CLIP_COMPOSITION_LOOP" not in cb_qa.CLIP_CORROBORATE, cb_qa.CLIP_CORROBORATE)
    check("CLIP_COMPOSITION_LOOP has a DONE_CODES fix-hint entry",
          "CLIP_COMPOSITION_LOOP" in cb_qa.DONE_CODES, list(cb_qa.DONE_CODES.keys()))

    tmp = [os.path.join(HERE, f"_test_cb_qa_fake_passb_{i}.png") for i in range(4)]
    for p in tmp:
        open(p, "wb").write(b"\x89PNG\r\n\x1a\nfake")
    orig_vision_verdict = cb_qa.vision_verdict
    try:
        shot = {"characters": ["Fuzzby", "Zenny"], "startState": "", "storyBeat": "", "cuts": []}

        def fake_fail(prompt, images):
            check("_passB's checklist states the composition-loop criterion concretely (position/framing/background)",
                  "CLIP_COMPOSITION_LOOP" in prompt and "background elements" in prompt, prompt[:2000])
            return ("FAIL\nCLIP_COMPOSITION_LOOP: last frame matches the opening branch composition exactly", None)
        cb_qa.vision_verdict = fake_fail
        codes = cb_qa._passB(shot, tmp, comedy_big=False)
        check("_passB correctly parses CLIP_COMPOSITION_LOOP out of a FAIL response",
              codes == ["CLIP_COMPOSITION_LOOP"], codes)

        def fake_pass(prompt, images):
            return ("PASS", None)
        cb_qa.vision_verdict = fake_pass
        codes2 = cb_qa._passB(shot, tmp, comedy_big=False)
        check("_passB returns empty on a clean PASS (no false positive)", codes2 == [], codes2)
    finally:
        cb_qa.vision_verdict = orig_vision_verdict
        for p in tmp:
            if os.path.exists(p):
                os.remove(p)


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
    test_check_retake_prompt()
    test_gate3_lint_word_budget_and_congruence()
    test_gate3_lint_dialogue_leak_and_anti_slop()
    test_gate3_lint_checklist_verb_flag()
    test_gate3_lint_archetype_completeness_contract()
    test_prompt_before_fire_wiring()
    test_reference_position()
    test_framing_mismatch()
    test_clip_composition_loop_advisory_only()
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
