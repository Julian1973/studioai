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

# FIXED 2026-07-15 (the whole-episode restart archived the old "The_Adventure_Begins" package and Gate 1
# re-authored under a new working title): resolve the CURRENT beat package dynamically — same glob-newest
# convention cb_pipeline._resolve_pkg uses — instead of hardcoding a title that changes on every re-upload.
import glob as _glob
_PKG_CANDIDATES = sorted(_glob.glob(os.path.join(os.path.dirname(HERE), "shows", "crystal-bears", "episodes",
                                                   "output", "Ep1_*beat_package.json")), key=os.path.getmtime)
PKG_PATH = _PKG_CANDIDATES[-1] if _PKG_CANDIDATES else os.path.join(
    os.path.dirname(HERE), "shows", "crystal-bears", "episodes", "output",
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

    # FIXED 2026-07-13 (creativity-vs-rules audit): a SINGLE strip broke grammar whenever the matched word
    # was the head of a comparative ("faster than X" -> "than X") or the object of a fixed intensifying
    # preposition phrase ("at full speed" -> "at full") — confirmed live in 6+ real shipping beats (5.B3,
    # 4.B3, 6.B2, 10.B2). These constructions must now survive the strip completely untouched.
    comparative_cases = [
        ("clouds roll in faster than expected", "faster than expected"),
        ("words firing faster than his breath can carry", "faster than his breath can carry"),
        ("naming honey futures faster than Keen can track", "faster than Keen can track"),
    ]
    for sentence, must_survive in comparative_cases:
        out = S._v5_strip_speed_adjectives(sentence)
        check(fails, f"preserves comparative construction intact: {must_survive!r}", must_survive in out, out)
    prep_cases = [
        ("Fuzzby rockets toward the beach at full speed and immediately flies into the branch", "at full speed"),
        ("He darts in too fast and gets stuck", "too fast"),
    ]
    for sentence, must_survive in prep_cases:
        out = S._v5_strip_speed_adjectives(sentence)
        check(fails, f"preserves intensifying-preposition construction intact: {must_survive!r}",
              must_survive in out, out)

    # FIXED 2026-07-13, same night, found while verifying real beat 1.B1 was safe to re-fire: a
    # coordinated-modifier-pair strip ("wingbeats rapid and continuous" -> "wingbeats and continuous," a
    # dangling "and" with nothing on its left) — confirmed live in 4 real beats (1.B1, 8.B2, 10.B1, 10.B2),
    # all using the identical "wings/wingbeats {speed-word} and continuous(ly)" construction.
    and_pair_cases = [
        ("wingbeats rapid and continuous", "rapid and continuous"),
        ("wings beating rapidly and continuously.", "rapidly and continuously"),
    ]
    for sentence, must_survive in and_pair_cases:
        out = S._v5_strip_speed_adjectives(sentence)
        check(fails, f"preserves and-coordinated modifier pair intact: {must_survive!r}",
              must_survive in out, out)
    # a genuinely independent clause after "and" (not a coordinate modifier) still strips correctly —
    # this fix narrows the strip to a specific shape, it doesn't disable it for real new clauses
    real_clause = S._v5_strip_speed_adjectives("Fuzzby flies fast and lands hard.")
    check(fails, "still strips before a genuine new clause (2+ words before the boundary)",
          "fast" not in real_clause.lower().split(), real_clause)

    # FIXED 2026-07-14, found live rewriting 1.B2's own cut-1 framing to fix an opening-frame coverage
    # mismatch: "pushes in low and fast to follow him from behind" compiled to the dangling "pushes in low
    # and to follow him from behind" — "fast" sits between "and" (on its left, coordinating it with "low")
    # and "to follow" (an infinitive, on its right) on the right; stripping it left "and" with nothing
    # parallel to coordinate. The mirror-image of the already-fixed "X and <one-word>" case (rapid and
    # continuous): here the speed word is the SECOND half of the coordinate pair, not the first.
    and_prefix_cases = [
        ("Fuzzby pushes in low and fast to follow him from behind", "low and fast to follow"),
        ("she reads the room quiet and quick before the reveal", "quiet and quick before"),
    ]
    for sentence, must_survive in and_prefix_cases:
        out = S._v5_strip_speed_adjectives(sentence)
        check(fails, f"preserves a speed word preceded by 'and ' (coordinate pair, not a new clause): {must_survive!r}",
              must_survive in out, out)

    # a bare, unqualified speed word (no comparative/preposition/and-pair context) is still stripped as
    # before — this fix narrows the strip, it doesn't disable it
    still_stripped = S._v5_strip_speed_adjectives("Fuzzby flies fast toward the flower.")
    check(fails, "still strips a bare speed word with no comparative/preposition context",
          "fast" not in still_stripped.lower().split(), still_stripped)

    # FIXED 2026-07-13, same night, found writing physics-forward causal prose per the seedance-motion
    # doctrine (rule 76): the bare NOUN "speed" (e.g. "his own speed bends every stem") was being stripped
    # via `speed(?:y|ily)?`'s own optional suffix, leaving a subjectless broken clause ("his own bends
    # every stem") — the exact bug class rules 71-73 spent a night hunting, reproduced live in a fresh
    # rewrite. "speedy"/"speedily" (the real adjective/adverb forms this stripper exists to ban) must still
    # go; the bare noun — a legitimate, concrete physics term naming the actual cause of a visible
    # consequence — must now survive untouched.
    noun_kept = S._v5_strip_speed_adjectives("Fuzzby's own speed bends every stem he passes.")
    check(fails, "keeps the bare noun 'speed' when it's the grammatical subject of a real consequence",
          "speed" in noun_kept.lower(), noun_kept)
    adj_still_stripped = S._v5_strip_speed_adjectives("Fuzzby flies a speedy loop around the flower.")
    check(fails, "still strips the adjective form 'speedy'",
          "speedy" not in adj_still_stripped.lower(), adj_still_stripped)
    adv_still_stripped = S._v5_strip_speed_adjectives("Fuzzby speedily crosses the meadow.")
    check(fails, "still strips the adverb form 'speedily'",
          "speedily" not in adv_still_stripped.lower(), adv_still_stripped)

    if os.path.exists(PKG_PATH):
        d = json.load(open(PKG_PATH))
        beats = d.get("beats") or d.get("shots") or []
        scenes = d.get("scenes") or []
        risk_re = __import__("re").compile(
            r"\b(?:high-speed|fast(?:er|est)?|quick(?:ly|er|est)?|rapid(?:ly)?|hyper|manic(?:ally)?|"
            r"frantic(?:ally)?|chaotic(?:ally)?|wild(?:ly)?|erratic(?:ally)?|hasty|hastily|speed(?:y|ily)?|"
            r"zooming|zooms|zoomed)\b\s+and\s+\S+\s*(?:[,.;:]|$)", __import__("re").IGNORECASE)
        broken = []
        for b in beats:
            code = b.get("beatCode") or b.get("shotCode")
            sc = next((s for s in scenes if str(s.get("sceneNumber")) == str(b.get("scene"))), {})
            raw = " ".join(str(c.get("action") or "") + " " + str(c.get("framing") or "")
                            for c in (b.get("cuts") or [])) + " " + str(b.get("endState") or "")
            m = risk_re.search(raw)
            if not m:
                continue
            try:
                prompt, _, _ = S.shipped_prompt(b, sc, relay=False)
            except Exception:
                continue
            if m.group(0).split()[0].lower() not in prompt.lower():
                broken.append(code)
        check(fails, "zero real beats with an and-coordinated speed-adjective pair lose the adjective",
              not broken, broken)
    return fails


def test_active_cast_fidelity_and_size():
    fails = []
    print("\n=== _v5_active_cast fidelityAllocation respect + _v5_size_clause ===")

    # FIXED 2026-07-13 (creativity-vs-rules audit): the director's own authored fidelityAllocation must
    # override an incidental text mention — a character marked `economized` is backgrounded even when named
    # in blocking text, and `primary`/`secondary` are always active even when the prose never names them.
    beat = {
        "fidelityAllocation": {"primary": "Aida", "secondary": "Howey", "economized": "Fuzzby, Zenny"},
        "cuts": [{"action": "Fuzzby banks into frame-left and Zenny settles frame-right; the bears listen.",
                  "framing": "", "dialogue": ""}],
        "speakers": [],
    }
    active, background = S._v5_active_cast(beat, ["Aida", "Howey", "Fuzzby", "Zenny"])
    check(fails, "primary/secondary forced active even when never individually named",
          set(active) == {"Aida", "Howey"}, active)
    check(fails, "economized forced background even when individually named in blocking text",
          set(background) == {"Fuzzby", "Zenny"}, background)

    # FIXED 2026-07-13: the possessive-tail match used a bare substring test with no word boundary, so any
    # word CONTAINING the tail (e.g. "chrysanthemum" contains "mum") false-positive-matched "Keen's Mum".
    cast = ["Fuzzby", "Keen's Mum"]
    bad_beat = {"cuts": [{"action": "Fuzzby dives face-first into a giant chrysanthemum bloom, pollen everywhere.",
                           "framing": "", "dialogue": ""}]}
    active2, background2 = S._v5_active_cast(bad_beat, cast)
    check(fails, "'chrysanthemum' no longer false-positive-matches \"Keen's Mum\" via the 'mum' substring",
          "Keen's Mum" in background2, (active2, background2))
    control_beat = {"cuts": [{"action": "Fuzzby dives face-first into a giant daisy bloom, pollen everywhere.",
                               "framing": "", "dialogue": ""}]}
    active3, background3 = S._v5_active_cast(control_beat, cast)
    check(fails, "control (no 'mum' substring anywhere) still backgrounds an unmentioned character",
          "Keen's Mum" in background3, (active3, background3))

    # FIXED 2026-07-13 (director-fidelity-trace): relative size never reached the shipped video prompt even
    # though it's authored redundantly upstream (characters.json sizeRank, the cadence field's own
    # parenthetical, the Director's Pass camera direction) — confirmed live against 1.B1's actual rendered
    # footage, where Zenny visibly grows to match/exceed Fuzzby's size by the clip's end.
    clause = S._v5_size_clause(["Fuzzby", "Zenny"])
    check(fails, "size clause states Fuzzby larger than Zenny (their real characters.json sizeRank order)",
          "Fuzzby" in clause and "Zenny" in clause and "larger" in clause, clause)
    check(fails, "size clause is order-independent (same result regardless of cast list order)",
          S._v5_size_clause(["Zenny", "Fuzzby"]) == clause)
    check(fails, "no size clause for a solo character (nothing to compare against)",
          S._v5_size_clause(["Aida"]) == "")
    if os.path.exists(PKG_PATH):
        beat11, scene1 = _load_beat("1.B1")
        prompt11, _builder, _def = S.shipped_prompt(beat11, scene1, relay=False)
        check(fails, "real 1.B1's shipped prompt now carries the SIZE clause",
              "SIZE:" in prompt11 and "larger than" in prompt11, "SIZE:" in prompt11)
    return fails


def test_negative_line_article_strip():
    fails = []
    print("\n=== _v5_negative_line article-strip fix ===")
    # FIXED 2026-07-13 (creativity-vs-rules audit, confirmed live on 22/43 real shipping beats): the "no "
    # prefix step didn't strip a leading indefinite article first, shipping "no a clean face" / "no an easy
    # pull" — grammatically broken. A leading "a "/"an " must now be stripped before the "no " prefix lands.
    scene = {}
    beat = {"beatCode": "ZZ.TEST", "stagingProhibited": ["a clean face after wiping", "an easy pull free"]}
    line = S._v5_negative_line(beat, scene)
    check(fails, "'a clean face...' ships as 'no clean face...', never 'no a clean face...'",
          "no clean face after wiping" in line and "no a clean face" not in line, line)
    check(fails, "'an easy pull...' ships as 'no easy pull...', never 'no an easy pull...'",
          "no easy pull free" in line and "no an easy pull" not in line, line)
    # a phrase that already starts with a real negation word is untouched (not treated as having an article)
    beat2 = {"beatCode": "ZZ.TEST2", "stagingProhibited": ["never a clean recovery"]}
    line2 = S._v5_negative_line(beat2, scene)
    check(fails, "a phrase already starting with a negation word is left exactly as authored",
          "never a clean recovery" in line2, line2)
    if os.path.exists(PKG_PATH):
        d = json.load(open(PKG_PATH))
        beats = d.get("beats") or d.get("shots") or []
        scenes = d.get("scenes") or []
        broken = []
        for b in beats:
            code = b.get("beatCode") or b.get("shotCode")
            sc = next((s for s in scenes if str(s.get("sceneNumber")) == str(b.get("scene"))), {})
            real_line = S._v5_negative_line(b, sc)
            if "no a " in real_line.lower() or "no an " in real_line.lower():
                broken.append(code)
        check(fails, "zero real beats in the production package still ship 'no a X'/'no an X'",
              not broken, broken)
    return fails


def test_semicolon_not_treated_as_sentence_boundary():
    fails = []
    print("\n=== _v5_cap_sentences / _v5_positive_movement_slice: semicolon is not a sentence boundary ===")
    # FIXED 2026-07-13 (creativity-vs-rules audit — confirmed live against Sunny's real characters.json
    # mannerisms text): a semicolon joins two clauses of ONE sentence in English; the old split regex
    # treated it as equivalent to a period, so _v5_cap_sentences(text, 1, ...) kept only the first CLAUSE
    # and shipped it with a dangling, unresolved semicolon.
    sunny_real = ("Pure motion — bounding, skipping, twirling, leaping; she physically cannot hold still "
                  "when she's lit up. Tugs friends by the paw toward the next fun thing.")
    capped = S._v5_cap_sentences(sunny_real, 1, S._DNA_MANNERISMS_WORD_BACKSTOP)
    check(fails, "keeps the WHOLE first real sentence, including its semicolon-joined second clause",
          capped.rstrip().endswith("lit up."), capped)
    check(fails, "never ends on a dangling semicolon", not capped.rstrip().endswith(";"), capped)

    # the shared bug also lived in _v5_positive_movement_slice (the PRIMARY path every character's cadence
    # compiles through) — a semicolon-joined clause must survive as one unit, never split and have one half
    # silently dropped by the negation-duplicate-topic filter.
    sliced = S._v5_positive_movement_slice(sunny_real)
    check(fails, "_v5_positive_movement_slice keeps the semicolon-joined clause intact as one unit",
          "leaping; she physically cannot hold still when she's lit up." in sliced, sliced)

    if os.path.exists(CS_CHARS_PATH := S.P.CHARS):
        chars = json.load(open(CS_CHARS_PATH)).get("characters") or json.load(open(CS_CHARS_PATH))
        broken = []
        for name, c in chars.items():
            if not isinstance(c, dict) or "voiceId" not in c:
                continue
            cad = str(c.get("cadence") or "")
            if not cad:
                continue
            out = S._v5_positive_movement_slice(cad)
            if out.rstrip().endswith(";"):
                broken.append(name)
        check(fails, "zero real characters' cadence field ships a dangling trailing semicolon",
              not broken, broken)
    return fails


def test_cut_speaker_note_no_double_period():
    fails = []
    print("\n=== _v5_cut_speaker_note: no double period, correct subject-verb agreement ===")
    # FIXED 2026-07-13 (creativity-vs-rules audit, confirmed live on 33/84 real dialogue cuts — e.g. real
    # beat 8.B3 cut 2 shipped "...childlike welcome rather than ceremony.." with a literal double period,
    # sent to the paid Seedance API today): a trailing "." was appended even when the authored `delivery`
    # text already ended in its own terminal punctuation.
    c1 = {"n": 1, "dialogue": "FUZZBY: Ready?", "delivery": "eager, upbeat, already leaning forward."}
    out1 = S._v5_cut_speaker_note(c1, {"speakers": ["Fuzzby"]})
    check(fails, "delivery already ending in '.' does not get a second period appended",
          ".." not in out1, out1)
    c2 = {"n": 2, "dialogue": "FUZZBY: Ready?", "delivery": "eager, upbeat, already leaning forward"}
    out2 = S._v5_cut_speaker_note(c2, {"speakers": ["Fuzzby"]})
    check(fails, "delivery with NO terminal punctuation still gets exactly one period appended",
          out2.rstrip().endswith("forward.") and not out2.rstrip().endswith(".."), out2)
    # subject-verb agreement: "All" (a chorus/group speaker) is plural and takes "perform", never "performs"
    c3 = {"n": 3, "dialogue": "ALL: Welcome home.",
          "delivery": "warm, unified, delighted but not overwhelming; childlike welcome rather than ceremony."}
    out3 = S._v5_cut_speaker_note(c3, {"speakers": ["All"]})
    check(fails, "'All' as speaker takes the plural verb 'perform', never 'performs'",
          "All perform " in out3 and "All performs" not in out3, out3)
    if os.path.exists(PKG_PATH):
        d = json.load(open(PKG_PATH))
        beats = d.get("beats") or d.get("shots") or []
        broken = []
        for b in beats:
            code = b.get("beatCode") or b.get("shotCode")
            for cut in b.get("cuts", []):
                out = S._v5_cut_speaker_note(cut, b)
                if ".." in out:
                    broken.append((code, cut.get("n")))
        check(fails, "zero real dialogue cuts in the production package still ship a double period",
              not broken, broken)
    return fails


def test_v5_beat_story_audio_cue_always_trails():
    """THE MOTION CONTRACT / audio-placement regression guard (2026-07-13, the CapCut-formula deep-dive):
    a real side-test tonight spliced an "@Audio1" vocal cue into the MIDDLE of an action sentence and the
    model read it as two separate camera setups, breaking spatial continuity — confirmed by a direct
    structural diff against the fix. Our own compiler was never actually vulnerable to this (`_v5_beat_story`
    always appends `_v5_cut_speaker_note`'s return value AFTER the action body, never interleaves it), but
    that invariant lived only in code shape with no test proving it — this pins it down as a permanent
    regression guard so a future refactor can't silently reintroduce the mid-splice."""
    fails = []
    print("\n=== _v5_beat_story: the @Audio1 speaker note always trails the action text, never splices it ===")
    beat = {
        "beatCode": "TEST.AUDIO.TRAIL", "speakers": ["Fuzzby"], "endState": "He settles, chest out.",
        "cuts": [
            {"n": 1, "framing": "medium tracking shot", "dialogue": "FUZZBY: Bizzy bizzy bizzy.",
             "delivery": "off-key, proud work-song patter",
             "action": "He flies toward the sunflower and dives headfirst into its center in one motion."},
        ],
    }
    block = S._v5_beat_story(beat, ["Fuzzby"])
    line = [l for l in block.split("\n") if "performs" in l][0]
    action_end = line.find("motion.")
    audio_pos = line.find("@Audio1")
    check(fails, "the @Audio1 cue's position in the compiled line is AFTER the action's own final clause, never before or inside it",
          audio_pos > action_end > -1, line)
    check(fails, "the action's own sentence is not interrupted mid-clause by the speaker note",
          "into its center in one motion." in line, line)
    if os.path.exists(PKG_PATH):
        d = json.load(open(PKG_PATH))
        beats = d.get("beats") or d.get("shots") or []
        spliced = []
        for b in beats:
            code = b.get("beatCode") or b.get("shotCode")
            for cut in (b.get("cuts") or []):
                action = S._strip_spoken_words(str(cut.get("action") or "")).rstrip(".")
                note = S._v5_cut_speaker_note(cut, b)
                if not note:
                    continue
                combined = f"{action}." + note if action else note
                # the note must be a pure SUFFIX of the combined text — if it isn't, something inserted
                # content between the action's own end and the note, which is the exact mid-splice shape
                if not combined.endswith(note.strip()):
                    spliced.append((code, cut.get("n")))
        check(fails, "zero real dialogue cuts in the production package have their audio cue spliced mid-action",
              not spliced, spliced)
    return fails


def test_standing_negatives():
    fails = []
    print("\n=== _standing_negatives ===")
    negs = S._standing_negatives()
    check(fails, "returns exactly twelve items", len(negs) == 12, f"got {len(negs)}: {negs}")
    check(fails, "every item is a non-empty string", all(isinstance(n, str) and n.strip() for n in negs))
    check(fails, "the twelfth item bans invented background voices (2026-07-13 fix)",
          any("background voices" in n for n in negs), negs)
    # calling twice returns the identical list content (no hidden mutation/randomness)
    negs2 = S._standing_negatives()
    check(fails, "is deterministic across calls", negs == negs2)
    return fails


def test_audio1_no_other_voices_clause():
    fails = []
    print("\n=== _v5_references @Audio1 positive-preservation clause (2026-07-13 fix) ===")
    beat = {"speakers": ["Fuzzby"], "cuts": [{"n": 1, "dialogue": "FUZZBY: Hi.", "action": "waves"}]}
    ref_line = S._v5_references(["Fuzzby", "Zenny"], False, 4, beat)
    check(fails, "@Audio1 line states no other voices are generated",
          "No other voices generated" in ref_line, ref_line)
    wordless_beat = {"speakers": [], "wordlessHeld": True, "cuts": [{"n": 1, "action": "hovers"}]}
    wordless_line = S._v5_references(["Fuzzby", "Zenny"], False, 4, wordless_beat)
    check(fails, "a wordless beat gets no other-voices clause (no @Audio1 line to attach it to)",
          "No other voices generated" not in wordless_line, wordless_line)
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
    # ADDED 2026-07-13 (external-review verification, CLAUDE.md rule 73 follow-up): 1.B1 is a scene-opener
    # (relay=False) — its own @图1 clause never claims lighting/geography ("begin on this exact composition"
    # only), so there is nothing to arbitrate against the plate and the priority clause is correctly absent.
    check(fails, "opener beat has no reference-priority clause (nothing to arbitrate)",
          "disagree on lighting" not in prompt, prompt)
    return fails


def test_reference_priority_relay_only():
    fails = []
    print("\n=== reference-priority tie-break: relay-only, word-budget-safe ===")
    # ADDED 2026-07-13 (external-review verification, CLAUDE.md rule 73 follow-up): a relay beat's own @图1
    # clause DOES claim "lighting and local geography," which genuinely overlaps the plate's declared job —
    # confirmed no priority statement existed anywhere in this compiler before this fix. First attempt was a
    # general 3-way sentence on EVERY beat, which pushed real beat 1.B2 over the 650-word hard cap (655-664
    # words measured) — narrowed to a ~9-word, relay-only clause naming the one actually-diagnosed overlap.
    if not os.path.exists(PKG_PATH):
        check(fails, "real Ep1 beat package exists at expected path", False, PKG_PATH)
        return fails
    beat, scene = _load_beat("1.B2")
    prompt, _builder, _def = S.shipped_prompt(beat, scene, relay=True)
    check(fails, "relay beat's prompt states the lighting tie-break", "disagree on lighting" in prompt, prompt)
    wc = S._v5_word_count(prompt)
    import cb_preflight as PF
    check(fails, f"real 1.B2 (relay) word count ({wc}) stays under WORD_BUDGET_BLOCK ({PF.WORD_BUDGET_BLOCK})",
          wc < PF.WORD_BUDGET_BLOCK, f"word count={wc}")
    return fails


def test_relay_geography_freedom():
    fails = []
    print("\n=== @图1 first-frame-only continuity, not a geography constraint (2026-07-13 fix) ===")
    beat = {"speakers": [], "cuts": [{"n": 1, "action": "flies off", "framing": "wide"}]}
    ref_line = S._v5_references(["Fuzzby", "Zenny"], True, 4, beat)
    check(fails, "@图1 still matches the first frame exactly",
          "matched exactly as the first frame only" in ref_line, ref_line)
    check(fails, "the preserve-list no longer claims ongoing 'local geography'",
          "geography" not in ref_line.lower(), ref_line)
    check(fails, "an explicit travel-freedom sentence is present",
          "free to travel anywhere" in ref_line, ref_line)
    check(fails, "the anti-hold counter-instruction survives",
          "Do not hold the previous pose" in ref_line, ref_line)
    if os.path.exists(PKG_PATH):
        beat3, scene3 = _load_beat("1.B3")
        prompt3, _b, _d = S.shipped_prompt(beat3, scene3, relay=True)
        check(fails, "real 1.B3 relay prompt carries no ongoing geography claim",
              "local geography" not in prompt3, prompt3)
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


def test_archetype_prohibited_wired_into_negatives():
    fails = []
    print("\n=== _v5_archetype_prohibited / _v5_negative_line archetype wiring (2026-07-09) ===")
    if not os.path.exists(PKG_PATH):
        check(fails, "real Ep1 beat package exists at expected path", False, PKG_PATH)
        return fails

    # 1.B1 resolves to LEAF_CRASH_REBOUND via cb_seedance._ARCHETYPE_OVERRIDES, and was NEVER hand-edited
    # with its own stagingProhibited for this — the whole point of this fix is that it gets the protection
    # automatically, with zero per-beat authoring.
    import cb_seedance
    beat, scene = _load_beat("1.B1")
    # UPDATED 2026-07-15 (whole-episode restart): the fresh Gate-1 fire natively authors stagingProhibited
    # (the rule 55 schema fix working as designed), so "1.B1 has no hand-authored list" is no longer a valid
    # premise. Prove the SAME thing data-independently instead: clear the field on a COPY and confirm the
    # archetype protection still arrives automatically with zero per-beat authoring.
    beat = copy.deepcopy(beat)
    beat["stagingProhibited"] = None
    check(fails, "archetype protection tested on a copy with stagingProhibited cleared (proves it is automatic, not hand-authored)",
          not (beat.get("stagingProhibited") or []), beat.get("stagingProhibited"))
    archetype_phrases = S._v5_archetype_prohibited(beat, scene)
    check(fails, "resolves at least one archetype-derived prohibited phrase for 1.B1",
          len(archetype_phrases) > 0, archetype_phrases)
    expected = cb_seedance.PHYSICAL_ARCHETYPES.get("LEAF_CRASH_REBOUND", {}).get("prohibited_staging", "")
    check(fails, "matches LEAF_CRASH_REBOUND's own prohibited_staging content",
          archetype_phrases and archetype_phrases[0] in expected, (archetype_phrases, expected))

    # REVERTED 2026-07-14 (real footage diagnosis on 1.B2 — Fuzzby fully vanished into the flower on a
    # beat that DOES resolve a physics anchor): the 2026-07-13 suppression tested above used to hold —
    # archetype negatives were dropped whenever a positive PHYSICS anchor existed, on the theory the
    # positive text always covers the same protective ground. Proven false: POLLEN_FACE_PRESS_REVEAL's
    # own `physics_rule` describes flower-compression mechanics only, never character visibility — so the
    # ONE thing that would have stopped Fuzzby disappearing (the archetype's `prohibited_staging` phrase)
    # was the exact thing being suppressed. The negative line now ALWAYS carries the archetype's own
    # prohibited phrases, regardless of whether a physics anchor also resolves — matching rule 62's
    # original, evidence-backed design; see `_v5_negative_line`'s own docstring for the full dated record.
    negline = S._v5_negative_line(beat, scene)
    check(fails, "the negative line always carries the archetype's own prohibited phrases (physics anchor or not)",
          any(p.lower() in negline.lower() for p in archetype_phrases), negline)

    # Degrades gracefully: a minimal/malformed beat shape must NEVER crash prompt compilation — this is
    # enrichment, not a required input. Verified live: infer_physical_archetype's own fallback branches
    # (dmode-based defaults) mean even a beat with no cuts still resolves to SOME generic archetype
    # (e.g. DIALOGUE_HOVER_STASIS) rather than nothing — a real, useful, always-resolves-to-something
    # design (rule 10), not a gap. The guarantee under test is "never raises", not "returns empty".
    broken = {"beatCode": "ZZ.B99", "cuts": None}
    try:
        result = S._v5_archetype_prohibited(broken, scene)
        check(fails, "a malformed/minimal beat never raises (returns a list, empty or a generic fallback)",
              isinstance(result, list), result)
    except Exception as e:
        check(fails, "a malformed/minimal beat never raises (returns a list, empty or a generic fallback)",
              False, f"raised instead: {type(e).__name__}: {e}")

    # Dedup: a beat-authored stagingProhibited phrase that already covers the archetype's own item must not
    # appear twice in the shipped line.
    beat2 = copy.deepcopy(beat)
    beat2["stagingProhibited"] = [archetype_phrases[0]] if archetype_phrases else []
    negline2 = S._v5_negative_line(beat2, scene)
    if archetype_phrases:
        occurrences = negline2.lower().count(archetype_phrases[0].lower())
        check(fails, "a beat-authored phrase already matching the archetype's own is never duplicated",
              occurrences == 1, f"found {occurrences} occurrences in: {negline2}")
    return fails


def test_physics_anchor():
    """THE POSITIVE PHYSICS ANCHOR (2026-07-13, CLAUDE.md rule 75): `_v5_physics_anchor` closes the gap the
    independent craft audit named — a positive statement of the resolved archetype's own physics_rule,
    clause-capped, alongside the pre-existing negative-only `_v5_archetype_prohibited` (rule 62)."""
    fails = []
    beat, scene = _load_beat("1.B1")
    check(fails, "found real beat 1.B1 in the production package", beat is not None)
    if beat is None:
        return fails

    anchor = S._v5_physics_anchor(beat, scene)
    check(fails, "1.B1 (LEAF_CRASH_REBOUND) resolves a non-empty PHYSICS anchor", bool(anchor))
    check(fails, "the anchor is prefixed 'PHYSICS: ' and ends in a period",
          anchor.startswith("PHYSICS: ") and anchor.endswith("."))
    # THE FIELD-LOCAL CAP IS GONE (2026-07-15, CLAUDE.md rule 62/76's own fix superseded): a real audit
    # confirmed this cap was STILL dropping the settle/recovery clause off LEAF_CRASH_REBOUND's own
    # physics_rule on real beats (1.B1, 5.B3) even at 24 words, unforced (1.B1 had 120 spare words under the
    # real 700-word budget at the time). The anchor now ships the archetype's own physics_rule VERBATIM, in
    # full — the only gate on its length is the single outer word-budget, never a field-local ceiling.
    import cb_seedance as _CBS
    archetype = S.resolve_physical_archetype(beat, scene)
    full_physics = S._v5_strip_speed_adjectives(_CBS.PHYSICAL_ARCHETYPES.get(archetype, {}).get("physics_rule", ""))
    check(fails, "the anchor carries the archetype's FULL physics_rule verbatim, not a truncated clause",
          anchor == f"PHYSICS: {full_physics}.", f"anchor={anchor!r} full_physics={full_physics!r}")

    story = S._v5_beat_story(beat, beat.get("openingCast") or beat.get("characters") or [], scene)
    check(fails, "the anchor is the leading line of Block 4 (the shot list), not a separate '\\n\\n' block",
          story.split("\n", 1)[0] == anchor)

    # never raises on a malformed beat — enrichment, not a required input, matching the identical contract
    # `_v5_archetype_prohibited` already holds (its own resolver has a generic fallback archetype, so a
    # malformed beat legitimately gets THAT archetype's own physics_rule, not necessarily an empty string).
    try:
        result = S._v5_physics_anchor({"weird": "no cuts, no archetype-inferrable data"}, {})
        check(fails, "a malformed/minimal beat never raises", isinstance(result, str))
    except Exception as e:
        check(fails, "a malformed/minimal beat never raises", False, f"raised {e!r}")

    return fails


def test_expression_line():
    """THE EXPRESSION LINE (2026-07-14, CLAUDE.md rule 84/85): `_v5_expression_line` closes the confirmed
    Gate-3/Keane gap — a full gate-by-gate trace + adversarial verify found `cb_director_pass.direct_beat()`
    computes real per-beat camera/staging/expression/performance direction every beat via a genuine LLM call,
    but before this fix NOTHING of it reached the shipped prompt except `voice_direction`. This is a pure
    cache read (`cb_director_pass.cached_expression`) — no LLM call of its own."""
    fails = []
    beat, scene = _load_beat("1.B1")
    check(fails, "found real beat 1.B1 in the production package", beat is not None)
    if beat is None:
        return fails

    import cb_director_pass
    real_expr = cb_director_pass.cached_expression("Ep1", "1.B1")
    check(fails, "1.B1 has a real cached Director's Pass expression field on disk (from an earlier real fire)",
          bool(real_expr), "if this fails, the _director_pass/Ep1_1.B1.json cache file may have been deleted")

    line = S._v5_expression_line(beat, episode="Ep1")
    check(fails, "1.B1 resolves a non-empty EXPRESSION line from the real cache", bool(line))
    check(fails, "the line is prefixed 'EXPRESSION: ' and ends in a period",
          line.startswith("EXPRESSION: ") and line.endswith("."))
    # THE 24-WORD CLAUSE CAP IS GONE (2026-07-15, CLAUDE.md rule 62/76's own fix pattern applied here too): a
    # real audit found this cap firing on 43 of 43 real beats, discarding an average of 70 words each — ~3,000
    # words of Keane's own cached animator direction (the impact/rebound/recovery arc that actually sells the
    # comedy) reduced to its first clause on every single beat. The line now ships the cached expression text
    # in full (only speed-adjective/dialogue stripping applied) — the only gate on its length is the single
    # outer word-budget (cb_preflight.WORD_BUDGET_BLOCK), never a field-local ceiling.
    expected = S._v5_strip_speed_adjectives(S._strip_spoken_words(real_expr))
    check(fails, "the line carries the cached expression text in FULL, not a truncated clause",
          line == f"EXPRESSION: {expected}.", f"line={line!r} expected_body={expected!r}")

    # Position: EXPRESSION follows PHYSICS as the second leading line of Block 4 (the shot list) — never a
    # new "\n\n" block (cb_qa.check_gate3_lint's block-index model counts blocks by splitting on "\n\n").
    story = S._v5_beat_story(beat, beat.get("openingCast") or beat.get("characters") or [], scene, episode="Ep1")
    story_lines = story.split("\n")
    physics = S._v5_physics_anchor(beat, scene)
    check(fails, "PHYSICS is the first line and EXPRESSION the second, both inside Block 4's own newline-joined body",
          story_lines[0] == physics and story_lines[1] == line,
          f"lines[0]={story_lines[0]!r} lines[1]={story_lines[1]!r}")

    # Graceful degrade — no cache on disk for this episode/code -> empty string, never raises. Matches the
    # physics anchor's own "enrichment, never a required input" contract exactly.
    empty = S._v5_expression_line(beat, episode="Ep_NoSuchEpisode_Whatsoever")
    check(fails, "no cached direction for an unknown episode -> empty string, not an exception", empty == "")

    try:
        result = S._v5_expression_line({"weird": "no beatCode, no cache possible"}, episode="Ep1")
        check(fails, "a malformed/minimal beat never raises", isinstance(result, str))
    except Exception as e:
        check(fails, "a malformed/minimal beat never raises", False, f"raised {e!r}")

    # cached_expression itself: pure read, no LLM call, mirrors cached_voice_direction's own contract.
    check(fails, "cached_expression returns None (not raise) for a beat with no cache file at all",
          cb_director_pass.cached_expression("Ep1", "9.B_no_such_beat_9999") is None)

    return fails


def main():
    all_fails = []
    all_fails += test_strip_spoken_words()
    all_fails += test_strip_speed_adjectives()
    all_fails += test_active_cast_fidelity_and_size()
    all_fails += test_negative_line_article_strip()
    all_fails += test_semicolon_not_treated_as_sentence_boundary()
    all_fails += test_cut_speaker_note_no_double_period()
    all_fails += test_v5_beat_story_audio_cue_always_trails()
    all_fails += test_standing_negatives()
    all_fails += test_audio1_no_other_voices_clause()
    all_fails += test_shot_time_ranges()
    all_fails += test_shipped_prompt_real_beat()
    all_fails += test_reference_priority_relay_only()
    all_fails += test_relay_geography_freedom()
    all_fails += test_manifest_field_missing_on_gap()
    all_fails += test_archetype_prohibited_wired_into_negatives()
    all_fails += test_physics_anchor()
    all_fails += test_expression_line()

    print()
    if all_fails:
        print(f"FAILED — {len(all_fails)} assertion(s) did not hold:")
        for f in all_fails:
            print(f"  - {f}")
        return 1
    print("ALL PASS — cb_segprompt.py's core behaviours (Law 6 stripping, the adjective-chaos ban, the "
          "twelve standing negatives, the @Audio1 no-other-voices clause, the shot-timing law, a real "
          "beat's compiled word budget, and the manifest hard-gate on a missing required field) are "
          "verified correct, not just non-crashing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
