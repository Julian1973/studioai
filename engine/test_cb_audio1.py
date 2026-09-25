"""T37 - the voice/dialogue contract, clause 5, acceptance check 4.

Approval creates @Audio1: the approved take's hash, bound to the exact dialogue version,
with its measured duration and every line's measured speech interval and speaker. A saved
prompt or a generated take is never approval.
"""
import json
import pathlib
import subprocess

import pytest

import cb_audio_timing
import cb_render as R
from test_current_production_path import (  # noqa: F401  (isolated_canon is autouse)
    isolated_canon, world, _approve_scene_look, _approve_specialist_inputs,
    _sign_specialist_inputs)

QUIET = {"log": lambda *a, **k: None}


# ── measurement: from the master's own bytes ─────────────────────────────────────

def _placed_master(tmp_path, pieces, lines, duration):
    """Build raw audio from (kind, seconds) pieces, place it with the real builder."""
    raw = tmp_path / "raw.wav"
    parts, labels = [], []
    for index, (kind, seconds) in enumerate(pieces):
        source = (f"sine=f=220:d={seconds}" if kind == "tone" else
                  f"anullsrc=r=44100:cl=mono,atrim=duration={seconds}")
        parts.append(f"{source}[p{index}]")
        labels.append(f"[p{index}]")
    graph = ";".join(parts) + ";" + "".join(labels) + \
        f"concat=n={len(pieces)}:v=0:a=1[out]"
    subprocess.run(["ffmpeg", "-y", "-filter_complex", graph, "-map", "[out]",
                    "-ar", "44100", str(raw)], check=True, capture_output=True)
    timing = cb_audio_timing.dialogue_timing_path(raw)
    cursor, segments = 0.0, []
    for index, line in enumerate(lines):
        segments.append({"dialogueInputIndex": index, "startTimeSec": cursor,
                         "endTimeSec": cursor + line["sourceSec"]})
        cursor += line["sourceSec"]
    timing.write_text(json.dumps({"audioSha256": cb_audio_timing.file_sha256(raw),
                                  "voiceSegments": segments}))
    return cb_audio_timing.render_timed_dialogue_master(
        raw, timing, lines, duration, tmp_path / "master.wav")


def test_measured_intervals_come_from_the_audio_including_pauses(tmp_path):
    contract = _placed_master(
        tmp_path, [("tone", 0.8), ("tone", 0.4), ("silence", 0.4), ("tone", 0.4)],
        [{"dialogueOccurrenceId": "a", "startSec": 1.0, "endSec": 2.0, "sourceSec": 0.8},
         {"dialogueOccurrenceId": "b", "startSec": 4.0, "endSec": 5.5, "sourceSec": 1.2}],
        8)
    measured = cb_audio_timing.measure_speech_intervals(
        contract["outputPath"], contract["placements"])
    assert measured["durationSec"] == pytest.approx(8.0, abs=0.01)   # the whole shot
    first, second = measured["lines"]
    assert first["measuredStartSec"] == pytest.approx(1.0, abs=0.02)
    assert first["measuredEndSec"] == pytest.approx(1.8, abs=0.02)
    assert [[pytest.approx(v, abs=0.02) for v in span] for span in second["voicedIntervals"]] \
        == [[4.0, 4.4], [4.8, 5.2]]                                     # the pause is measured
    assert measured["method"]["tool"] == "ffmpeg silencedetect"


def test_a_line_the_take_does_not_speak_is_refused(tmp_path):
    contract = _placed_master(
        tmp_path, [("tone", 0.6), ("silence", 0.6)],
        [{"dialogueOccurrenceId": "a", "startSec": 0.5, "endSec": 1.5, "sourceSec": 0.6},
         {"dialogueOccurrenceId": "b", "startSec": 3.0, "endSec": 4.0, "sourceSec": 0.6}],
        5)
    with pytest.raises(cb_audio_timing.AudioTimingError, match="no speech measured for "
                                                                "dialogue line 2"):
        cb_audio_timing.measure_speech_intervals(
            contract["outputPath"], contract["placements"])


# ── approval creates @Audio1; nothing else does ────────────────────────────────

@pytest.fixture
def voiced(world, monkeypatch):
    _, tmp, pkg_path = world
    pkg = json.loads(pkg_path.read_text())
    _approve_specialist_inputs(pkg)
    pkg_path.write_text(json.dumps(pkg, indent=1))
    _approve_scene_look(tmp, pkg)
    _sign_specialist_inputs(pkg)
    pkg_path.write_text(json.dumps(pkg, indent=1))
    shot = next(s for s in pkg["shots"] if s.get("dialogueLines"))
    R.regen_voice_shot("9", shot["shotId"], "EpT", **QUIET)
    return shot["shotId"]


def _ledger(shot_id):
    pkg, _ = R.load_pkg("9", "EpT")
    return pkg, R._shot(pkg, shot_id), R._ledger(pkg, shot_id)


def test_a_generated_take_is_not_audio1(voiced):
    pkg, _, ledger = _ledger(voiced)
    assert ledger.get("voPath") and not ledger.get("audio1")
    assert R.current_audio1(pkg, voiced) is None
    assert R.voice_performance_status("9", voiced, "EpT")["audio1"] is None


def test_approval_creates_the_measured_audio1_record(voiced):
    R.approve_voice("9", voiced, "EpT", reviewed_by="Julian", **QUIET)
    pkg, shot, ledger = _ledger(voiced)
    record = R.current_audio1(pkg, voiced)
    assert record is not None and record["name"] == "@Audio1"
    assert record["sha256"] == cb_audio_timing.file_sha256(ledger["voPath"])
    assert record["audio1Id"] == "audio1:" + record["sha256"]
    assert ledger["voiceApproval"]["audio1Id"] == record["audio1Id"]
    assert record["approvedBy"] == "Julian"
    # bound to the exact dialogue version
    assert record["dialogueVersion"]["dialogueHash"] == \
        ledger["voiceApproval"]["inputSignature"]["dialogueHash"]
    assert record["dialogueVersion"]["scriptVersionId"] == \
        (pkg.get("sourceScript") or {}).get("scriptVersionId")
    # measured duration is the whole shot; every line measured with its speaker and words
    assert record["measuredDurationSec"] == pytest.approx(shot["durationSec"], abs=0.05)
    assert [(l["dialogueOccurrenceId"], l["speaker"], l["exactText"]) for l in record["lines"]] \
        == [(l["dialogueOccurrenceId"], l["speaker"], l["exactText"])
            for l in shot["dialogueLines"]]
    for line in record["lines"]:
        assert line["placedStartSec"] <= line["measuredStartSec"] < line["measuredEndSec"] \
            <= line["placedEndSec"] + 0.001
        assert line["voicedIntervals"]
    # the record is also written beside the master, hash-bound
    path = pathlib.Path(ledger["voiceApproval"]["audio1RecordPath"])
    assert cb_audio_timing.file_sha256(path) == ledger["voiceApproval"]["audio1RecordSha256"]
    assert json.loads(path.read_text())["audio1Id"] == record["audio1Id"]
    assert R.voice_performance_status("9", voiced, "EpT")["audio1"]["audio1Id"] == \
        record["audio1Id"]


def test_audio1_stops_being_current_when_its_bytes_or_dialogue_change(voiced):
    R.approve_voice("9", voiced, "EpT", reviewed_by="Julian", **QUIET)
    pkg, shot, ledger = _ledger(voiced)
    shot["dialogueLines"][0]["exactText"] += " Extra."
    assert R.current_audio1(pkg, voiced) is None          # a new dialogue version
    pkg, _, ledger = _ledger(voiced)
    with open(ledger["voPath"], "ab") as handle:
        handle.write(b"\0")
    assert R.current_audio1(pkg, voiced) is None          # not the approved bytes


def test_a_take_that_misses_a_line_is_never_approved(voiced, monkeypatch):
    def silent(master, placements):
        raise cb_audio_timing.AudioTimingError("no speech measured for dialogue line 1")
    monkeypatch.setattr(cb_audio_timing, "measure_speech_intervals", silent)
    with pytest.raises(R.Refused, match="cannot become @Audio1"):
        R.approve_voice("9", voiced, "EpT", reviewed_by="Julian", **QUIET)
    pkg, _, ledger = _ledger(voiced)
    assert not ledger.get("voiceApproval") and not ledger.get("audio1")


def test_rejection_keeps_audio1_only_as_history(voiced):
    R.approve_voice("9", voiced, "EpT", reviewed_by="Julian", **QUIET)
    _, _, before = _ledger(voiced)
    audio1_id = before["audio1"]["audio1Id"]
    R.reject_voice("9", voiced, "Keen's line lands flat", "EpT", reviewed_by="Julian", **QUIET)
    pkg, _, ledger = _ledger(voiced)
    assert ledger["audio1"] is None and R.current_audio1(pkg, voiced) is None
    assert ledger["voiceRejections"][-1]["timingBundle"]["audio1"]["audio1Id"] == audio1_id
