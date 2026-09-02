"""The treatment script format (2026-09-02): "SCENE 01: TITLE" / "Shot 01: Title" / production
lines, as The Box Monsters' Episode 1 is written — parsed alongside the screenplay format, with
the screenplay path byte-for-byte unchanged."""
import cb_intake

ROSTER = ["Jenny", "Teacher", "Patch"]

TREATMENT = """THE BOX MONSTERS
Episode 1: The Box That Felt Small

Runtime: 7 minutes
Structure: 2 scenes / 3 shots / 30 seconds per shot

SCENE 01: CLASSROOM MISTAKE

Runtime: 1 minute
Shots: 01-02
Clean Plate: Empty classroom. Word BRIDGE on the board.
Character Keyframe: Jenny at the front of class. Wide frame.

Shot 01: Reading Goes Wrong

Jenny stands at the front of the classroom.

TEACHER
Take your time, Jenny.

JENNY
Briggle.

Final Frame: Jenny frozen, embarrassed.

Shot 02: The Feeling Stays

Jenny is back at her desk.

SCENE 02: JENNY'S BEDROOM

Runtime: 1 minute
Shots: 03
Clean Plate: Empty bedroom.
Character Keyframe: Jenny kneeling beside the shoebox.

Shot 03: The Shoebox

PATCH
We hear you.
"""

SCREENPLAY = """INT. CRYSTAL COVE - DAY 1

JENNY
Hello.

EXT. MEADOW - DUSK 2

TEACHER
Goodbye.
"""


def test_treatment_headings_and_production_lines():
    parsed = cb_intake.parse_script(TREATMENT, ROSTER, log=lambda *_: None)
    assert [s["sceneNumber"] for s in parsed["scenes"]] == [1, 2]
    assert parsed["scenes"][0]["location"] == "CLASSROOM MISTAKE"
    assert parsed["scenes"][0]["time"] == ""
    assert parsed["scenes"][0]["meta"]["clean plate"] == "Empty classroom. Word BRIDGE on the board."
    assert parsed["scenes"][0]["meta"]["shots"] == "01-02"
    assert parsed["scenes"][1]["location"] == "JENNY'S BEDROOM"
    # the production lines are scene metadata, never story events
    texts = [e["text"] for e in parsed["events"]]
    assert not any(t.startswith("Clean Plate:") or t.startswith("Runtime:") for t in texts)
    # the writer's shot structure reaches the Director verbatim and in order
    assert texts[0] == "Shot 01: Reading Goes Wrong"
    assert "Final Frame: Jenny frozen, embarrassed." in texts
    assert "Shot 02: The Feeling Stays" in texts
    assert parsed["dialogueCount"] == 3
    assert [e["speaker"] for e in parsed["events"] if e["type"] == "dialogue"] == ["Teacher", "Jenny", "Patch"]
    assert [e["scene"] for e in parsed["events"] if e["type"] == "dialogue"] == [1, 1, 2]
    # the title block before SCENE 01 is front matter, never Scene 0
    assert parsed["frontMatter"] and parsed["frontMatter"][0].startswith("THE BOX MONSTERS")
    assert all(e["scene"] >= 1 for e in parsed["events"])


def test_screenplay_headings_unchanged():
    parsed = cb_intake.parse_script(SCREENPLAY, ROSTER, log=lambda *_: None)
    assert [(s["sceneNumber"], s["location"], s["time"]) for s in parsed["scenes"]] == [
        (1, "CRYSTAL COVE", "DAY"), (2, "MEADOW", "DUSK")]
    assert "meta" not in parsed["scenes"][0]
    assert parsed["dialogueCount"] == 2


def test_no_headings_still_refuses():
    try:
        cb_intake.parse_script("JENNY\nHello.\n", ROSTER, log=lambda *_: None)
    except cb_intake.Refused as exc:
        assert "SCENE 01: TITLE" in str(exc)
    else:
        raise AssertionError("a script with no scene headings must be refused")
