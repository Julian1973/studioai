import json
import pathlib
import subprocess

import pytest

import cb_audio_timing


def _silent_audio(path, duration):
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
        "-t", str(duration), "-c:a", "libmp3lame", str(path),
    ], check=True, capture_output=True)


def test_approved_dialogue_is_placed_once_then_sliced_without_regeneration(tmp_path):
    raw = tmp_path / "raw.mp3"
    _silent_audio(raw, 3)
    timing = cb_audio_timing.dialogue_timing_path(raw)
    timing.write_text(json.dumps({
        "audioSha256": cb_audio_timing.file_sha256(raw),
        "voiceSegments": [
            {"dialogueInputIndex": 0, "startTimeSec": 0, "endTimeSec": 1},
            {"dialogueInputIndex": 1, "startTimeSec": 1, "endTimeSec": 2},
            {"dialogueInputIndex": 2, "startTimeSec": 2, "endTimeSec": 3},
        ],
    }), encoding="utf-8")
    lines = [
        {"dialogueOccurrenceId": "d1", "startSec": 1, "endSec": 2.5},
        {"dialogueOccurrenceId": "d2", "startSec": 5, "endSec": 6.5},
        {"dialogueOccurrenceId": "d3", "startSec": 8, "endSec": 9.5},
    ]
    master = tmp_path / "approved.wav"
    contract = cb_audio_timing.render_timed_dialogue_master(
        raw, timing, lines, 10, master)

    assert pathlib.Path(contract["contractPath"]).is_file()
    assert contract["outputSha256"] == cb_audio_timing.file_sha256(master)
    assert [item["targetStartSec"] for item in contract["placements"]] == [1, 5, 8]

    first = cb_audio_timing.slice_timed_master(master, 0, 6, tmp_path / "first.wav")
    second = cb_audio_timing.slice_timed_master(master, 6, 10, tmp_path / "second.wav")
    assert first["durationSec"] == 6
    assert second["durationSec"] == 4
    assert first["sourceSha256"] == second["sourceSha256"] == contract["outputSha256"]


def test_voice_take_can_extend_past_estimated_end_without_clipping(tmp_path):
    raw = tmp_path / "raw.mp3"
    _silent_audio(raw, 2)
    timing = cb_audio_timing.dialogue_timing_path(raw)
    timing.write_text(json.dumps({
        "audioSha256": cb_audio_timing.file_sha256(raw),
        "voiceSegments": [
            {"dialogueInputIndex": 0, "startTimeSec": 0, "endTimeSec": 2},
        ],
    }), encoding="utf-8")
    contract = cb_audio_timing.render_timed_dialogue_master(
        raw, timing, [{"startSec": 1, "endSec": 2}], 5, tmp_path / "out.wav")
    assert contract["placements"][0]["targetStartSec"] == 1
    assert contract["placements"][0]["targetEndSec"] == 3
    assert contract["placements"][0]["naturalExtensionSec"] == 1
    assert contract["placements"][0]["edgeFadeSec"] == cb_audio_timing.EDGE_FADE_SEC


def test_incomplete_provider_timestamps_preserve_the_whole_conversation(tmp_path):
    raw = tmp_path / "raw.mp3"
    _silent_audio(raw, 4)
    timing = cb_audio_timing.dialogue_timing_path(raw)
    timing.write_text(json.dumps({
        "audioSha256": cb_audio_timing.file_sha256(raw),
        "voiceSegments": [
            {"dialogueInputIndex": 0, "startTimeSec": 0, "endTimeSec": 1},
            {"dialogueInputIndex": 1, "startTimeSec": 1, "endTimeSec": 2.5},
        ],
    }), encoding="utf-8")
    lines = [
        {"dialogueOccurrenceId": "d1", "startSec": 0.5, "endSec": 1.5},
        {"dialogueOccurrenceId": "d2", "startSec": 3, "endSec": 4},
    ]

    contract = cb_audio_timing.render_timed_dialogue_master(
        raw, timing, lines, 5, tmp_path / "out.wav")

    assert contract["assemblyMode"] == "continuous-dialogue-performance"
    assert contract["performanceTargetStartSec"] == 0.5
    assert contract["performanceTargetEndSec"] == pytest.approx(4.5, abs=.05)
    assert len(contract["placements"]) == 2
    assert all(item["continuousPerformance"] for item in contract["placements"])
    assert cb_audio_timing.minimum_master_duration(raw, timing, lines) == pytest.approx(
        4.5, abs=.05)


def test_character_alignment_overrides_inaccurate_voice_segment_envelopes():
    timing = {
        "voiceSegments": [
            {"dialogueInputIndex": 0, "startTimeSec": 0, "endTimeSec": 0.4,
             "characterStartIndex": 0, "characterEndIndex": 2},
            {"dialogueInputIndex": 1, "startTimeSec": 0.4, "endTimeSec": 0.8,
             "characterStartIndex": 2, "characterEndIndex": 4},
        ],
        "alignment": {
            "characters": list("ABCD"),
            "character_start_times_seconds": [0.0, 0.3, 0.8, 1.1],
            "character_end_times_seconds": [0.3, 0.8, 1.1, 1.6],
        },
    }

    assert cb_audio_timing._source_ranges(timing, 2) == [(0.0, 0.8), (0.8, 1.6)]


def test_director_dialogue_timing_fields_are_accepted(tmp_path):
    raw = tmp_path / "raw.mp3"
    _silent_audio(raw, 1)
    timing = cb_audio_timing.dialogue_timing_path(raw)
    timing.write_text(json.dumps({
        "audioSha256": cb_audio_timing.file_sha256(raw),
        "voiceSegments": [
            {"dialogueInputIndex": 0, "startTimeSec": 0, "endTimeSec": 1},
        ],
    }), encoding="utf-8")
    contract = cb_audio_timing.render_timed_dialogue_master(
        raw, timing, [{"startsAtSec": 1.2, "estimatedDurationSec": 1.0}],
        5, tmp_path / "out.wav")
    assert contract["placements"][0]["targetStartSec"] == 1.2
    assert contract["placements"][0]["approvedWindowEndSec"] == 2.2


def test_voice_take_that_overlaps_next_start_anchor_refuses(tmp_path):
    raw = tmp_path / "raw.mp3"
    _silent_audio(raw, 3)
    timing = cb_audio_timing.dialogue_timing_path(raw)
    timing.write_text(json.dumps({
        "audioSha256": cb_audio_timing.file_sha256(raw),
        "voiceSegments": [
            {"dialogueInputIndex": 0, "startTimeSec": 0, "endTimeSec": 2},
            {"dialogueInputIndex": 1, "startTimeSec": 2, "endTimeSec": 3},
        ],
    }), encoding="utf-8")
    lines = [{"startSec": 1, "endSec": 1.5}, {"startSec": 2, "endSec": 3}]
    with pytest.raises(cb_audio_timing.AudioTimingError, match="next approved start"):
        cb_audio_timing.render_timed_dialogue_master(
            raw, timing, lines, 5, tmp_path / "out.wav")


def test_final_dialogue_overrun_reports_natural_required_duration(tmp_path):
    raw = tmp_path / "raw.mp3"
    _silent_audio(raw, 3.56)
    timing = cb_audio_timing.dialogue_timing_path(raw)
    timing.write_text(json.dumps({
        "audioSha256": cb_audio_timing.file_sha256(raw),
        "voiceSegments": [
            {"dialogueInputIndex": 0, "startTimeSec": 0, "endTimeSec": 1},
            {"dialogueInputIndex": 1, "startTimeSec": 1, "endTimeSec": 3.56},
        ],
    }), encoding="utf-8")
    lines = [{"startSec": 19.7}, {"startSec": 23.2}]

    required = cb_audio_timing.minimum_master_duration(raw, timing, lines)

    assert required == pytest.approx(25.76, abs=.02)


def test_internal_overlap_cannot_be_hidden_by_extending_shot(tmp_path):
    raw = tmp_path / "raw.mp3"
    _silent_audio(raw, 4)
    timing = cb_audio_timing.dialogue_timing_path(raw)
    timing.write_text(json.dumps({
        "audioSha256": cb_audio_timing.file_sha256(raw),
        "voiceSegments": [
            {"dialogueInputIndex": 0, "startTimeSec": 0, "endTimeSec": 3},
            {"dialogueInputIndex": 1, "startTimeSec": 3, "endTimeSec": 4},
        ],
    }), encoding="utf-8")

    with pytest.raises(cb_audio_timing.AudioTimingError, match="internal timing conflict"):
        cb_audio_timing.minimum_master_duration(
            raw, timing, [{"startSec": 1}, {"startSec": 2}],
        )

    cascade = cb_audio_timing.cascade_retime_for_natural_performance(
        raw, timing, [{"startSec": 1, "endSec": 2}, {"startSec": 2, "endSec": 3}],
    )
    assert cascade["lines"][0]["startSec"] == 1
    assert cascade["lines"][1]["startSec"] == pytest.approx(4.0)
    assert cascade["requiredDurationSec"] == pytest.approx(5.0)
    assert cascade["providerCalled"] is False


def test_natural_master_duration_uses_available_thirty_second_slate():
    assert cb_audio_timing.natural_master_duration(29.6) == 30
    with pytest.raises(cb_audio_timing.AudioTimingError, match="30s maximum"):
        cb_audio_timing.natural_master_duration(29.66)


def test_one_dialogue_segment_can_be_replaced_without_changing_master_duration(tmp_path):
    master = tmp_path / "master.mp3"
    replacement = tmp_path / "replacement.mp3"
    _silent_audio(master, 10)
    _silent_audio(replacement, 2)
    timing = cb_audio_timing.dialogue_timing_path(replacement)
    timing.write_text(json.dumps({
        "audioSha256": cb_audio_timing.file_sha256(replacement),
        "voiceSegments": [{
            "dialogueInputIndex": 0, "startTimeSec": 0, "endTimeSec": 2,
        }],
    }), encoding="utf-8")
    result = cb_audio_timing.replace_timed_dialogue_segment(
        master, replacement, timing, 4, 8, 6, tmp_path / "repaired.wav")
    assert result["targetStartSec"] == 4
    assert result["targetEndSec"] == 6
    assert result["durationSec"] == pytest.approx(10, abs=.05)
    assert pathlib.Path(result["contractPath"]).is_file()
