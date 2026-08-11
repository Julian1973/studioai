import json

import cb_prompt_bank


def test_prompt_bank_records_parse_structure_and_report(tmp_path):
    bank = tmp_path / "prompt_bank.jsonl"
    prompt = """[References]
@Image1 defines Fuzzby's identity. Do not use the background.

[Shot Sequence]
Shot 1: Chase through flowers. End state: Fuzzby hovers.

[Audio]
No music.
"""

    approved = cb_prompt_bank.bank_prompt(
        prompt=prompt, episode="Ep1", scene="1", shot_id="S1.SH1A",
        outcome="approved", candidate=2, candidate_path="c2.mp4",
        bank_path=bank)
    rejected = cb_prompt_bank.bank_prompt(
        prompt=prompt, episode="Ep1", scene="1", shot_id="S1.SH1B",
        outcome="rejected", diagnosis="moustache did not read",
        category="action-timing", bank_path=bank)

    rows = [json.loads(line) for line in bank.read_text().splitlines()]
    assert [row["schemaVersion"] for row in rows] == [1, 1]
    assert approved["parsed"]["sectionOrder"] == [
        "References", "Reference", "Shot Sequence", "Shot", "Audio"]
    assert rejected["approved"] is False
    assert rejected["diagnosis"] == "moustache did not read"

    report = cb_prompt_bank.report(bank)
    assert report["records"] == 1
    assert report["rawRecords"] == 2
    assert report["sectionOrderFrequency"][
        "References > Reference > Shot Sequence > Shot > Audio"] == 1
    assert "false-triumph-chase" in report["archetypeWinRate"]


def test_prompt_bank_parses_proven_flova_grammar_and_dedupes_report(tmp_path):
    bank = tmp_path / "prompt_bank.jsonl"
    prompt = """image_1 defines exactly one performer. Refer to it strictly. Do not use its pose or background.
image_2 defines only the environment. Do not use or invent characters from it.
ATTRIBUTE OWNERSHIP: all new marks appear on the performer only.
Feature-quality stylized 3D CGI: tactile fur, glossy eyes and warm light.
Dialogue language: English. Only the named speaker speaks.

Shot 1 — the chase. The camera pursues through flowers at three speeds. End state: the performer is trapped at maximum load.
Shot 2 — the verdict. The witness holds still. End state: both characters are readable.

No music. No subtitles, captions or on-screen text. No watermark. No extra characters.
"""

    first = cb_prompt_bank.bank_prompt(
        prompt=prompt, episode="Ep1", scene="1", shot_id="S1.SH1A",
        outcome="approved", bank_path=bank)
    second = cb_prompt_bank.bank_prompt(
        prompt=prompt, episode="Ep1", scene="1", shot_id="S1.SH1A",
        outcome="approved", bank_path=bank)

    assert first["promptHash"] == second["promptHash"]
    parsed = cb_prompt_bank.parse_prompt_structure(prompt)
    assert parsed["sectionOrder"] == [
        "Reference", "Reference", "Attribute Ownership", "Style",
        "Dialogue Language", "Shot", "Shot", "Negatives"]
    references = [item for item in parsed["sections"] if item["name"] == "Reference"]
    assert all(item["hasRole"] and item["hasExclusion"] for item in references)
    assert parsed["markers"].get("End State", 0) == 0
    assert cb_prompt_bank.infer_archetype(prompt) == "false-triumph-chase"

    report = cb_prompt_bank.report(bank)
    assert report["rawRecords"] == 2
    assert report["records"] == 1
    assert report["duplicatePromptHashes"] == 1
    assert "Reference > Reference > Attribute Ownership" in next(
        iter(report["sectionOrderFrequency"]))
