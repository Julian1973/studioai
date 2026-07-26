#!/usr/bin/env python3
"""test_story_room.py — GUARDS ON THE ROOM ITSELF, NOT ON A PRODUCTION ARTEFACT.

These tests assert who is in the room and what context they hold. They need NO episode, NO
beat package and NO production data — which is exactly why they live here rather than in
test_cb_creative.py, whose module-level require_live_beat_package mark would silence them at
clean zero. That is the second time a blanket module mark has hidden tests that matter most
when the project is empty (the first was test_no_legacy_fingerprints.py, corrected the same
day). A guard that switches itself off when the pipeline is about to run for real is not a
guard.

    pytest test_story_room.py -q
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def test_step_one_convenes_the_whole_room():
    """THE MOST CONSEQUENTIAL PASS GETS THE MOST CONTEXT (2026-07-26).

    Julian: "step 1 has to be done properly... I knew when we were working further down the
    line the beats weren't landing and now we know why."

    cb_departments.prepare_story decides where EVERY beat begins and ends and authors
    want/need/kidRead/adultRead/emotionalIntent for the whole episode — the emotional
    architecture every later chair can only refine INSIDE. It used to run on the Director's
    runtime contract and the job text alone: no show bible, no taste canons, no exemplars, no
    Showrunner. Then the ten-gate creative room convened to design shots inside a shape it had
    no voice in choosing. The room got stronger as the decisions got smaller.

    It now routes through cb_creative._mind — the same room builder the creative gates use —
    so there is ONE room for the whole pipeline rather than two that drift. This test is the
    guard: it asserts the CONTEXT arrives, not the wording, so the charge can be rewritten
    freely without breaking it.

    Deliberately NOT guarded by require_live_beat_package: this needs no production data, and
    it matters most when the project is at clean zero and about to run a script for real."""
    import cb_departments as D
    import cb_llm

    captured = {}

    def _capture(system, user, schema, **kw):
        captured["system"] = system
        raise SystemExit("captured — no provider call")

    real = cb_llm.structured
    D.cb_llm.structured = _capture
    try:
        D.prepare_story([{"index": 0, "scene": 1, "type": "action", "text": "x"}],
                        {1: ["Fuzzby"]}, log=lambda *a, **k: None)
    except SystemExit:
        pass
    finally:
        D.cb_llm.structured = real

    m = captured.get("system", "")
    assert m, "prepare_story never reached the LLM boundary"
    for needed, what in (
            ("Crystal Bears Director", "the Director's runtime SKILL contract"),
            ("Crystal Bears Showrunner", "the Showrunner's contract — series truth in the room"),
            ("SHOW CANON", "the show bible"),
            ("TASTE CANON", "the taste canons"),
            ("APPROVED CANONICAL EXEMPLAR", "the approved exemplars"),
            ("verbatim-locked", "the dialogue lock"),
            ("Cinematographer", "the DP — a beat with no visual event cannot be staged"),
            ("why the story turns HERE", "the demand that the boundary justify itself")):
        assert needed in m, (
            f"step 1 lost {what}. This pass sets the episode's emotional architecture; a beat "
            f"boundary or an adultRead authored without it cannot be recovered downstream.")
    # and the one structural decision this pass makes must still be forced to justify itself
    import cb_departments as _D
    assert "boundaryReason" in _D.BeatSplit.model_fields, (
        "BeatSplit lost boundaryReason — the beat boundary is the single most consequential "
        "structural decision in the pipeline and it would once again be unreviewable")
    assert _D.BeatSplit.model_fields["boundaryReason"].is_required(), (
        "boundaryReason became optional — an unjustified boundary is an invisible one")

    assert len(m) > 20000, (
        f"step 1's charge collapsed to {len(m)} chars — it was ~2,000 when it ran on the "
        f"Director alone and ~36,000 with the room. Something stopped assembling.")


def test_the_character_canon_reaches_every_authoring_room_whole():
    """THE THIRD TRUNCATION (2026-07-26).

    Three times in one file the same bug: craft written, approved, and eaten by a cap.
    The taste canons lost their REJECTION QUESTIONS to a 7,000-char slice. The show
    bible lost 81% of itself — the cut landing mid-table in the locked Crystal Power
    System — to a 6,000-char one. And the character canon lost `bibles` (21,043 of its
    33,595 chars for a two-character cast, 63%) to caps of 12,000 / 9,000 / 8,000, so
    no character's own locked canon ever reached a single gate in this studio.

    Six of eleven rooms had no character canon AT ALL, including the three that need it
    most: step 1 (which authors want and need for every beat in the episode, with the
    Showrunner charged to run the substitution test against a register she wasn't
    given), the shot conference (staging is acting), and the voice room (the read IS
    the character).

    A cap is invisible. It never errors, never warns, and produces a confident answer
    from a fraction of the canon — which is exactly why this needs a test and not a
    comment.
    """
    import inspect
    import cb_creative as C
    import cb_departments as D

    rooms = {"prepare_story": D.prepare_story}
    for fn in ("gate0_readiness", "gate1_treatments", "gate2_select", "gate3_beats",
               "gate4_shot_conference", "gate5_performance", "gate5_voice",
               "gate6_adversarial_review", "production_detail"):
        f = getattr(C, fn, None)
        if f:
            rooms[fn] = f
    for name, f in rooms.items():
        assert "_characters_for" in inspect.getsource(f), (
            f"{name} authors without the character canon — it is deciding who these "
            f"people are from their names alone")

    # gate6b is deliberately absent: it judges whether a scene can be PRODUCED (reference
    # coverage, cast count, duration), never who anyone is. Naming it here so a future
    # reader knows it was considered, not missed.
    assert "_characters_for" not in inspect.getsource(C.gate6b_producer_feasibility)

    # No call site may re-introduce a slice. This is the assertion that would have caught
    # all three truncations on the day each was written.
    for path in ("cb_creative.py", "cb_departments.py"):
        for i, line in enumerate(open(path, encoding="utf-8"), 1):
            if "_characters_for(" in line and "[:" in line:
                raise AssertionError(f"{path}:{i} truncates the character canon: "
                                     f"{line.strip()[:90]}")

    # The bibles block — the whole point — must actually survive to the text.
    assert "bibles" in C._characters_for(["Fuzzby", "Zenny"])


def test_the_show_bible_is_not_truncated():
    """31,829 chars of locked canon, handed to every room as 6,000 until 2026-07-26.

    The cut landed mid-table in section 3, so every gate authored knowing roughly two
    bears' crystal, feeling, archetype, colour and note — and none of the other seven.
    A room told 'SHOW CANON (authoritative, never contradicted)' and then handed a fifth
    of it cannot keep the show on brand; it can only keep the part it was shown.
    """
    import cb_creative as C

    src = C._CANON_SOURCES["showBible"]
    assert src.exists()
    full = src.read_text(encoding="utf-8")
    got = C._mind("SHOWRUNNER", ["showrunnerTaste"], "x")
    got = got["system"] if isinstance(got, dict) else str(got)
    for probe in ("Crystal Power System", "Rose Quartz", "Citrine", "The Ripple"):
        assert probe in got, f"the show bible reaches the room without {probe!r}"
    assert len(full) < 40000, (
        "the bible has outgrown the 40,000 backstop in _mind — raise it, and do not let "
        "canon be cut to fit a number again")


def test_every_beatsplit_field_the_room_authors_actually_survives_to_disk():
    """AUTHORED, THEN DISCARDED (2026-07-26, found on the first real fire).

    cb_intake builds each beat as a hand-enumerated dict. A new BeatSplit field is
    therefore authored by the room, enforced by the schema (boundaryReason is required
    with min_length=1 — the model literally cannot omit it), and then silently dropped
    on the way to disk unless someone remembers to add one line.

    The first real run proved it: 43/43 beats came back rich on storyBeat, want, need,
    kidRead, adultRead and emotionalIntent — and 0/43 on boundaryReason. The Studio's
    intake review already rendered the field, so it showed blank for every beat, and
    nothing anywhere said why. The room did its job; the serializer ate it.

    This asserts the two sides agree, so the next field added to BeatSplit cannot be
    lost the same way.
    """
    import inspect
    import cb_departments as D
    import cb_intake

    src = inspect.getsource(cb_intake)
    start = src.find("beats_out.append({")
    assert start != -1, "cb_intake no longer builds beats this way — re-point this test"
    block = src[start:src.find("})", start)]

    # firstEventIndex is deliberately absent: it is consumed to compute each beat's own
    # event range and is meaningless once that range exists. Everything else must survive.
    structural = {"firstEventIndex"}
    for field in D.BeatSplit.model_fields:
        if field in structural:
            continue
        assert f'"{field}"' in block, (
            f"BeatSplit authors {field!r} and cb_intake never writes it to disk — the "
            f"room's work is being discarded at serialization")


def test_the_intake_log_reaches_the_studio_live():
    """The Studio streams this subprocess's stdout to show the live step. Python block-
    buffers a pipe, so without flush the whole 200s run displayed 'Starting…' and the
    log arrived only at exit — a progress indicator that is wrong for the entire job.
    """
    import re
    src = open("cb_intake.py", encoding="utf-8").read()
    bad = [l.strip() for l in src.splitlines()
           if re.match(r"\s*print\(", l) and "flush" not in l]
    assert not bad, f"unflushed print() in the streamed intake path: {bad[:3]}"
