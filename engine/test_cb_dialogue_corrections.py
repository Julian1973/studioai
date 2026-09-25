"""T34 - the voice/dialogue contract, clauses 1 and 3, acceptance check 2.

"Save corrected words" explicitly updates the script line with history, never silently;
the occurrence keeps its dialogueOccurrenceId; ruling (Julian, 2026-09-25): only that
line's voice re-locks - its current take becomes historical, nothing else changes.
"""
import copy
import json

import pytest

import cb_engine
import cb_intake
import cb_lineage
import cb_render as render
import cb_scripts

SCRIPT = "\n".join([
    "EXT. BUZZING NOOK - MORNING  1",
    "",
    "Keen fires the catapult.",
    "",
    "ZENNY",
    "OK, Fuzzby, calm down.",
    "It's not that funny.",
    "",
    "KEEN",
    "Uh-oh—",
    "",
    "FUZZBY",
    "Nice machine.",
    "",
])

CANON_POLICY = {"scriptChecks": {
    "forbiddenPatterns": [{"id": "no-bees-sting", "pattern": r"\bstings?\b",
                           "message": "Crystal Bears bees never sting."}],
}}
LOCKED_CALL = {"id": "fuzzby-call", "speaker": "FUZZBY", "triggerPattern": r"\bmachine\b",
               "exactText": "Nice machine.", "message": "Fuzzby's call is locked."}


@pytest.fixture
def store(tmp_path, monkeypatch):
    script_store = cb_scripts.ScriptStore(
        tmp_path, show_id="crystal-bears", script_root=tmp_path / "scripts")
    current = script_store.store("Ep9", SCRIPT, "Test Episode", activated_by="test")
    monkeypatch.setattr(cb_intake, "SCRIPT_STORE", script_store)
    monkeypatch.setattr(cb_intake, "script_record_for", lambda episode: script_store.current(episode))
    monkeypatch.setattr(cb_intake, "ROOT", tmp_path)
    monkeypatch.setattr(cb_intake.cb_canon, "load_policy", lambda root=None: CANON_POLICY)
    return script_store, current


def _identity_events(script_store):
    current = script_store.current("Ep9")
    parsed = cb_intake.parse_script(
        (script_store.root / current["contentPath"]).read_text(), log=lambda *_: None)
    return cb_intake._annotate_source_events(parsed["events"], current["scriptVersionId"])


def _occurrence(script_store, speaker):
    return next(e for e in _identity_events(script_store)
                if e["type"] == "dialogue" and e["speaker"] == speaker)


# ── the script: new version with history, identity untouched ────────────────────────

def test_save_corrected_words_keeps_identity_and_writes_history(store):
    script_store, before = store
    zenny = _occurrence(script_store, "Zenny")
    entry = cb_intake.correct_dialogue_line(
        "Ep9", zenny["dialogueOccurrenceId"], "OK, Fuzzby, calm DOWN. It is not that funny.",
        "Julian's rewrite for rhythm", corrected_by="Julian", log=lambda *_: None)

    after = script_store.current("Ep9")
    assert after["scriptVersionId"] == before["scriptVersionId"]      # approvals stay bound
    assert entry["fromText"] == "OK, Fuzzby, calm down. It's not that funny."
    assert entry["toText"] == "OK, Fuzzby, calm DOWN. It is not that funny."
    assert entry["reason"] == "Julian's rewrite for rhythm"
    # the corrected full script is its own immutable history version
    assert entry["effectiveScriptVersionId"] != before["scriptVersionId"]
    effective = script_store.effective_script_text("Ep9")
    assert "It is not that funny." in effective and "Uh-oh—" in effective
    # every occurrence keeps its ID, including the corrected one
    assert [e.get("dialogueOccurrenceId") for e in _identity_events(script_store)] == [
        e.get("dialogueOccurrenceId") for e in _identity_events(script_store)]
    assert script_store.corrected_words("Ep9")[zenny["dialogueOccurrenceId"]]["toText"] == \
        entry["toText"]
    events = list((script_store.script_root / "_events" / "Ep9").glob("*.json"))
    assert any(json.loads(p.read_text())["kind"] == "dialogue-line-corrected" for p in events)


def test_a_second_correction_chains_from_the_first(store):
    script_store, _ = store
    keen = _occurrence(script_store, "Keen")
    first = cb_intake.correct_dialogue_line(
        "Ep9", keen["dialogueOccurrenceId"], "Uh-oh!", "sharper", log=lambda *_: None)
    second = cb_intake.correct_dialogue_line(
        "Ep9", keen["dialogueOccurrenceId"], "Uh-oh…", "softer after all", log=lambda *_: None)
    assert second["fromText"] == "Uh-oh!"
    assert second["previousCorrectionId"] == first["correctionId"]
    assert "Uh-oh…" in script_store.effective_script_text("Ep9")


@pytest.mark.parametrize("words,match", [
    ("", "cannot be empty"),
    ("[laughs] Nice machine.", "dialogue only"),
    ("Nice (beat) machine.", "dialogue only"),
    ("Nice machine.", "same as the approved words"),
])
def test_corrections_that_are_not_word_changes_are_refused(store, words, match):
    script_store, _ = store
    fuzzby = _occurrence(script_store, "Fuzzby")
    with pytest.raises(cb_intake.Refused, match=match):
        cb_intake.correct_dialogue_line(
            "Ep9", fuzzby["dialogueOccurrenceId"], words, "reason", log=lambda *_: None)


def test_a_correction_needs_a_stated_reason(store):
    script_store, _ = store
    fuzzby = _occurrence(script_store, "Fuzzby")
    with pytest.raises(cb_intake.Refused, match="stated reason"):
        cb_intake.correct_dialogue_line(
            "Ep9", fuzzby["dialogueOccurrenceId"], "Nice machine!", "  ", log=lambda *_: None)


def test_a_new_script_upload_is_a_new_identity_and_leaves_corrections_behind(store):
    script_store, _ = store
    fuzzby = _occurrence(script_store, "Fuzzby")
    cb_intake.correct_dialogue_line(
        "Ep9", fuzzby["dialogueOccurrenceId"], "Nice machine!", "punch", log=lambda *_: None)
    script_store.store("Ep9", SCRIPT.replace("Keen fires", "Keen launches"), "Test Episode")
    assert script_store.corrected_words("Ep9") == {}


# ── production: only that line's voice re-locks ───────────────────────────────────

def _production_pkg():
    line = lambda occ, speaker, text: {   # noqa: E731
        "dialogueOccurrenceId": occ, "sourceEventId": f"event-{occ}", "speaker": speaker,
        "exactText": text, "delivery": "d", "startSec": 1.0, "endSec": 2.0}
    take = {"voPath": "media/take.wav", "voRawPath": "media/raw.mp3",
            "voInputSignature": {"dialogueHash": "old"},
            "voiceApproval": {"approved": True, "contentHash": "abc"}}
    return {
        "revision": 7,
        "shots": [
            {"shotId": "S1.SH1", "dialogueLines": [line("occ-z", "Zenny", "It's not that funny.")]},
            {"shotId": "S1.SH2", "dialogueLines": [line("occ-f", "Fuzzby", "Nice machine.")]},
        ],
        "continuityLedger": [
            {"shotId": "S1.SH1", **copy.deepcopy(take),
             "workingVoice": {"lines": [{"dialogueOccurrenceId": "occ-z",
                                         "text": "[deadpan] It's not that funny."}]}},
            {"shotId": "S1.SH2", **copy.deepcopy(take)},
        ],
    }


def test_correction_makes_only_that_lines_take_historical(tmp_path, monkeypatch):
    pkg = _production_pkg()
    (tmp_path / "Ep9_scene1_production_package.json").write_text("{}")
    saved = []
    monkeypatch.setattr(render, "load_pkg", lambda scene, episode="Ep1": (pkg, tmp_path / "p.json"))
    monkeypatch.setattr(render, "_save", lambda p, path: saved.append(copy.deepcopy(p)))
    entry = {"correctionId": "c1", "dialogueOccurrenceId": "occ-z", "fromText": "It's not that funny.",
             "toText": "It is not that funny.", "reason": "rhythm", "correctedBy": "Julian",
             "correctedAt": "2026-09-25T12:00:00+00:00"}

    touched = render.apply_dialogue_correction("Ep9", entry, log=lambda *_: None,
                                               packages_dir=tmp_path)

    assert touched == [{"scene": "1", "shotId": "S1.SH1"}]
    corrected = pkg["shots"][0]["dialogueLines"][0]
    assert corrected["dialogueOccurrenceId"] == "occ-z"          # same identity
    assert corrected["exactText"] == "It is not that funny."
    assert corrected["identityText"] == "It's not that funny."
    assert corrected["wordRevisions"][0]["reason"] == "rhythm"
    sh1, sh2 = pkg["continuityLedger"]
    assert sh1["voPath"] is None and sh1["voiceApproval"] is None     # not current any more
    assert sh1["voiceTakeHistory"][0]["status"] == "historical"
    assert sh1["voiceTakeHistory"][0]["take"]["voPath"] == "media/take.wav"
    assert sh1["workingVoice"] is None and sh1["workingVoiceHistory"][0]["status"] == "historical"
    # the other line's take, and the package revision, are untouched
    assert sh2["voPath"] == "media/take.wav" and sh2["voiceApproval"]["approved"] is True
    assert pkg["revision"] == 7
    assert saved


def test_engine_expected_lines_speak_the_corrected_words(tmp_path, monkeypatch):
    script_store = cb_scripts.ScriptStore(
        tmp_path, show_id="crystal-bears", script_root=tmp_path / "scripts")
    monkeypatch.setattr(script_store, "all_corrected_words", lambda: {
        "occ-z": {"toText": "It is not that funny.", "correctionId": "c1"}})
    monkeypatch.setattr(cb_engine, "SCRIPT_STORE", script_store)
    beats = [{"cuts": [{"dialogue": "ZENNY: It's not that funny.", "dialogueOccurrenceId": "occ-z",
                        "sourceEventId": "e1", "speaker": "Zenny",
                        "exactText": "It's not that funny."}]}]
    [line] = cb_engine._expected_lines(beats)
    assert line["exactText"] == "It is not that funny."
    assert line["identityText"] == "It's not that funny."
    assert line["dialogueOccurrenceId"] == "occ-z"
    # idempotent: applying again keeps the recorded identity text
    [again] = script_store.apply_corrections([line])
    assert again == line


def test_a_title_rename_keeps_the_corrected_words_readable(store):
    script_store, before = store
    fuzzby = _occurrence(script_store, "Fuzzby")
    cb_intake.correct_dialogue_line(
        "Ep9", fuzzby["dialogueOccurrenceId"], "Nice machine!", "punch", log=lambda *_: None)
    renamed = script_store.rename_current("Ep9", "Renamed Episode")
    assert renamed["scriptVersionId"] == before["scriptVersionId"]      # same identity
    assert script_store.corrected_words("Ep9")[fuzzby["dialogueOccurrenceId"]]["toText"] == \
        "Nice machine!"
    for base in (script_store.script_root, script_store.studio_root):
        assert "Nice machine!" in (base / renamed["displayFile"]).read_text()


# ── the other lines carry forward ────────────────────────────────────────────────

def _two_line_pkg():
    line = lambda occ, speaker, text: {   # noqa: E731
        "dialogueOccurrenceId": occ, "sourceEventId": f"event-{occ}", "speaker": speaker,
        "exactText": text, "delivery": "d", "startSec": 1.0, "endSec": 2.0}
    return {
        "revision": 3,
        "shots": [{"shotId": "S1.SH1", "dialogueLines": [
            line("occ-z", "Zenny", "It's not that funny."),
            line("occ-k", "Keen", "Uh-oh—")]}],
        "continuityLedger": [{
            "shotId": "S1.SH1", "voPath": "media/take.wav",
            "workingVoice": {"savedBy": "Julian", "lines": [
                {"dialogueOccurrenceId": "occ-z", "speaker": "Zenny",
                 "text": "[deadpan] It's not that funny."},
                {"dialogueOccurrenceId": "occ-k", "speaker": "Keen",
                 "text": "[gasps] Uh-oh—"}]}}],
    }


def test_only_the_corrected_lines_hear_edit_is_dropped(tmp_path, monkeypatch):
    pkg = _two_line_pkg()
    (tmp_path / "Ep9_scene1_production_package.json").write_text("{}")
    monkeypatch.setattr(render, "load_pkg", lambda scene, episode="Ep1": (pkg, tmp_path / "p.json"))
    monkeypatch.setattr(render, "_save", lambda p, path: None)
    entry = {"correctionId": "c1", "dialogueOccurrenceId": "occ-z", "fromText": "It's not that funny.",
             "toText": "It is not that funny.", "reason": "rhythm", "correctedBy": "Julian",
             "correctedAt": "2026-09-25T12:00:00+00:00"}
    render.apply_dialogue_correction("Ep9", entry, log=lambda *_: None, packages_dir=tmp_path)

    led = pkg["continuityLedger"][0]
    assert [l["dialogueOccurrenceId"] for l in led["workingVoice"]["lines"]] == ["occ-k"]
    assert len(led["workingVoiceHistory"][0]["lines"]) == 2          # full record kept
    lines, source = render._resolve_voice_lines(pkg, pkg["shots"][0])
    assert source == "human-working"
    assert [l["text"] for l in lines] == ["It is not that funny.", "[gasps] Uh-oh—"]


def test_stale_direction_for_a_corrected_line_falls_back_to_the_approved_words(monkeypatch):
    shot = {"shotId": "S1.SH1", "dialogueLines": [
        {"dialogueOccurrenceId": "occ-z", "sourceEventId": "e1", "speaker": "Zenny",
         "exactText": "It is not that funny.", "identityText": "It's not that funny.",
         "correctionId": "c1"},
        {"dialogueOccurrenceId": "occ-k", "sourceEventId": "e2", "speaker": "Keen",
         "exactText": "Uh-oh—"}]}
    pkg = {"shots": [shot], "continuityLedger": [{"shotId": "S1.SH1"}]}
    monkeypatch.setattr(render, "_approved_department_output", lambda *a, **k: {"lines": [
        {"dialogueOccurrenceId": "occ-z", "sourceEventId": "e1", "speaker": "Zenny",
         "performedText": "[deadpan] It's not that funny."},
        {"dialogueOccurrenceId": "occ-k", "sourceEventId": "e2", "speaker": "Keen",
         "performedText": "[gasps] Uh-oh—"}]})
    lines, source = render._resolve_voice_lines(pkg, shot)
    assert source == "voice-director-approved"
    assert [l["text"] for l in lines] == ["It is not that funny.", "[gasps] Uh-oh—"]


def test_uncorrected_lines_resolve_exactly_as_before(monkeypatch):
    shot = {"shotId": "S1.SH1", "dialogueLines": [
        {"dialogueOccurrenceId": "occ-k", "sourceEventId": "e2", "speaker": "Keen",
         "exactText": "Uh-oh—"}]}
    working = [{"dialogueOccurrenceId": "occ-k", "speaker": "Keen", "text": "[gasps] Uh-oh—"}]
    pkg = {"shots": [shot], "continuityLedger": [{"shotId": "S1.SH1",
                                                   "workingVoice": {"lines": working}}]}
    lines, _ = render._resolve_voice_lines(pkg, shot)
    assert lines is working


@pytest.mark.parametrize("speaker,words,check", [
    ("Zenny", "OK, Fuzzby, it stings. It's not that funny.", "no-bees-sting"),
    ("Fuzzby", "Nice machine, huh.", "fuzzby-call"),
])
def test_a_correction_may_not_bring_in_a_canon_conflict(store, monkeypatch, speaker, words, check):
    script_store, _ = store
    policy = {"scriptChecks": {**CANON_POLICY["scriptChecks"], "lockedDialogue": [LOCKED_CALL]}}
    monkeypatch.setattr(cb_intake.cb_canon, "load_policy", lambda root=None: policy)
    occurrence = _occurrence(script_store, speaker)
    with pytest.raises(cb_intake.Refused, match=f"show canon: .*{check}"):
        cb_intake.correct_dialogue_line(
            "Ep9", occurrence["dialogueOccurrenceId"], words, "reason", log=lambda *_: None)
    assert script_store.corrected_words("Ep9") == {}


def test_an_unreadable_canon_policy_refuses_the_correction(store, monkeypatch):
    script_store, _ = store
    def unreadable(root=None):
        raise cb_intake.cb_canon.CanonLockError("canon lock policy is unreadable")
    monkeypatch.setattr(cb_intake.cb_canon, "load_policy", unreadable)
    with pytest.raises(cb_intake.Refused, match="cannot be checked against canon"):
        cb_intake.correct_dialogue_line(
            "Ep9", _occurrence(script_store, "Keen")["dialogueOccurrenceId"], "Uh-oh!",
            "reason", log=lambda *_: None)
