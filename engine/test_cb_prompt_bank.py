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
    assert approved["parsed"]["sectionOrder"] == ["References", "Shot Sequence", "Audio"]
    assert rejected["approved"] is False
    assert rejected["diagnosis"] == "moustache did not read"

    report = cb_prompt_bank.report(bank)
    assert report["records"] == 2
    assert report["sectionOrderFrequency"]["References > Shot Sequence > Audio"] == 2
    assert "false-triumph-chase" in report["archetypeWinRate"]
