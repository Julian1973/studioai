"""Local timing utilities for an approved ElevenLabs dialogue performance.

The paid voice provider returns one acted conversation plus the source range for each
dialogue input. Authored start times remain exact performance anchors. The natural take
may extend beyond an estimated end time when it still fits before the next start anchor;
the software never clips or time-compresses an actor to satisfy an estimate.
"""
from __future__ import annotations

import hashlib
import json
import math
import pathlib
import subprocess


class AudioTimingError(RuntimeError):
    """The approved performance cannot be mapped to the approved timing contract."""


SAMPLE_RATE = 48000
CHANNELS = 2
# ElevenLabs delivery naturally breathes around the written estimate. For Studio work,
# small overruns should be logged as natural extension, not treated as a dead-end.
WINDOW_TOLERANCE_SEC = 0.75
EDGE_FADE_SEC = 0.012
# ElevenLabs dialogue-with-timestamps returns one continuous acted conversation. Its
# segment ranges already contain the actor's pauses, so adding another gap at every
# boundary duplicates silence and can push an otherwise valid performance over budget.
MIN_DIALOGUE_GAP_SEC = 0.0
MIN_LANDING_ROOM_SEC = 0.35
TIMING_COVERAGE_TOLERANCE_SEC = 0.20


def file_sha256(path):
    path = pathlib.Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def minimum_master_duration(raw_audio_path, timing_path, dialogue_lines):
    """Return the shortest shot duration that preserves every natural line take.

    Extending the shot can only solve an overrun at the final dialogue boundary. Any
    earlier overlap still requires a performance or authored-cue decision, so refuse it
    here rather than hiding the conflict by moving or compressing dialogue.
    """
    raw_audio_path = pathlib.Path(raw_audio_path)
    timing = json.loads(pathlib.Path(timing_path).read_text(encoding="utf-8"))
    if timing.get("audioSha256") != file_sha256(raw_audio_path):
        raise AudioTimingError("dialogue timing metadata does not match the raw audio bytes")
    ranges = _source_ranges(timing, len(dialogue_lines))
    if _needs_continuous_assembly(raw_audio_path, timing, ranges):
        if not dialogue_lines:
            return 0.0
        first = dialogue_lines[0]
        try:
            first_start = float(
                first.get("startSec")
                if first.get("startSec") is not None else first.get("startsAtSec"))
        except (TypeError, ValueError) as exc:
            raise AudioTimingError("dialogue line 1 has no approved start anchor") from exc
        return first_start + _probe_duration(raw_audio_path)
    authored = []
    for index, (line, source_range) in enumerate(zip(dialogue_lines, ranges)):
        try:
            target_start = float(
                line.get("startSec")
                if line.get("startSec") is not None else line.get("startsAtSec"))
        except (TypeError, ValueError) as exc:
            raise AudioTimingError(
                f"dialogue line {index + 1} has no approved start anchor") from exc
        authored.append((index, target_start, source_range[1] - source_range[0]))
    for position, (index, target_start, source_duration) in enumerate(authored[:-1]):
        next_start = authored[position + 1][1]
        if source_duration > next_start - target_start + WINDOW_TOLERANCE_SEC:
            raise AudioTimingError(
                f"dialogue line {index + 1} overlaps the next approved start; "
                "shot extension cannot resolve an internal timing conflict")
    if not authored:
        return 0.0
    _, final_start, final_duration = authored[-1]
    return final_start + final_duration


def cascade_retime_for_natural_performance(raw_audio_path, timing_path, dialogue_lines,
                                           minimum_gap_sec=MIN_DIALOGUE_GAP_SEC):
    """Move only later starts to preserve a returned take without clipping or compression.

    The first authored anchor remains fixed. Each later line keeps its authored start unless
    the preceding natural performance requires it to move. Returns copied lines, required
    duration and an audit list; it never edits script text or calls a provider.
    """
    raw_audio_path = pathlib.Path(raw_audio_path)
    timing = _read_json(timing_path)
    if timing.get("audioSha256") != file_sha256(raw_audio_path):
        raise AudioTimingError("dialogue timing metadata does not match the raw audio bytes")
    ranges = _source_ranges(timing, len(dialogue_lines))
    if _needs_continuous_assembly(raw_audio_path, timing, ranges):
        if not dialogue_lines:
            return {"lines": [], "requiredDurationSec": 0.0,
                    "changes": [], "providerCalled": False}
        first = dialogue_lines[0]
        key = "startSec" if first.get("startSec") is not None else "startsAtSec"
        try:
            first_start = float(first[key])
        except (KeyError, TypeError, ValueError) as exc:
            raise AudioTimingError("dialogue line 1 has no approved start anchor") from exc
        return {"lines": [dict(line) for line in dialogue_lines],
                "requiredDurationSec": first_start + _probe_duration(raw_audio_path),
                "changes": [], "providerCalled": False}
    retimed, changes, previous_end = [], [], None
    for index, (original, source_range) in enumerate(zip(dialogue_lines, ranges)):
        line = dict(original)
        key = "startSec" if line.get("startSec") is not None else "startsAtSec"
        try:
            authored_start = float(line[key])
        except (KeyError, TypeError, ValueError) as exc:
            raise AudioTimingError(
                f"dialogue line {index + 1} has no approved start anchor") from exc
        start = authored_start if previous_end is None else max(
            authored_start, previous_end + float(minimum_gap_sec))
        duration = source_range[1] - source_range[0]
        if start > authored_start + 0.001:
            changes.append({"dialogueIndex": index, "fromSec": authored_start,
                            "toSec": start, "shiftSec": start - authored_start})
        line[key] = start
        if line.get("endSec") is not None:
            authored_window = max(0.01, float(line["endSec"]) - authored_start)
            line["endSec"] = start + max(authored_window, duration)
        elif line.get("estimatedDurationSec") is not None:
            line["estimatedDurationSec"] = max(float(line["estimatedDurationSec"]), duration)
        retimed.append(line)
        previous_end = start + duration
    return {"lines": retimed, "requiredDurationSec": float(previous_end or 0),
            "changes": changes, "providerCalled": False}


def natural_master_duration(required_duration_sec, maximum_duration_sec=30.0,
                            landing_room_sec=MIN_LANDING_ROOM_SEC):
    """Choose a whole-second slate that preserves the take and landing room."""
    required = float(required_duration_sec)
    maximum = float(maximum_duration_sec)
    target = float(math.ceil(required + float(landing_room_sec)))
    if target > maximum + 0.001:
        raise AudioTimingError(
            f"natural performance requires {required:.2f}s plus "
            f"{landing_room_sec:.2f}s landing room in a {maximum:g}s maximum")
    return target


def dialogue_timing_path(audio_path):
    return pathlib.Path(str(pathlib.Path(audio_path)) + ".dialogue.json")


def timed_master_contract_path(audio_path):
    return pathlib.Path(str(pathlib.Path(audio_path)) + ".timing.json")


def _read_json(path):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as exc:
        raise AudioTimingError(f"dialogue timing metadata is unreadable: {path}") from exc


def _probe_duration(path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nk=1:nw=1", str(path),
        ],
        capture_output=True, text=True,
    )
    try:
        duration = float(result.stdout.strip())
    except (TypeError, ValueError) as exc:
        raise AudioTimingError(f"audio duration is unreadable: {path}") from exc
    if result.returncode or duration <= 0:
        raise AudioTimingError(f"audio duration is unreadable: {path}")
    return duration


def _source_ranges(timing, expected_count):
    raw = timing.get("voiceSegments") or timing.get("voice_segments") or []
    grouped = {}
    for item in raw:
        try:
            index = int(item.get("dialogueInputIndex", item.get("dialogue_input_index")))
            start = float(item.get("startTimeSec", item.get("start_time_seconds")))
            end = float(item.get("endTimeSec", item.get("end_time_seconds")))
        except (TypeError, ValueError) as exc:
            raise AudioTimingError("ElevenLabs returned a malformed dialogue segment") from exc
        if index < 0 or start < 0 or end <= start:
            raise AudioTimingError("ElevenLabs returned an invalid dialogue segment range")
        current = grouped.setdefault(index, [start, end])
        current[0] = min(current[0], start)
        current[1] = max(current[1], end)
    expected = set(range(expected_count))
    if set(grouped) != expected:
        raise AudioTimingError(
            "ElevenLabs timing metadata does not map one source range to every approved line"
        )
    aligned = _character_aligned_ranges(timing, raw, expected_count)
    if aligned is not None:
        return aligned
    return [tuple(grouped[index]) for index in range(expected_count)]


def _character_aligned_ranges(timing, segments, expected_count):
    """Resolve per-input ranges from the provider's precise character alignment."""
    alignment = (timing.get("alignment") or timing.get("normalizedAlignment") or
                 timing.get("normalized_alignment"))
    if not isinstance(alignment, dict):
        return None
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    characters = alignment.get("characters") or []
    if not starts or len(starts) != len(ends) or len(starts) != len(characters):
        return None
    bounds = {}
    for item in segments:
        try:
            index = int(item.get("dialogueInputIndex", item.get("dialogue_input_index")))
            start_index = int(item.get("characterStartIndex",
                                       item.get("character_start_index")))
            end_index = int(item.get("characterEndIndex", item.get("character_end_index")))
        except (TypeError, ValueError):
            return None
        if start_index < 0 or end_index <= start_index or end_index > len(starts):
            return None
        current = bounds.setdefault(index, [start_index, end_index])
        current[0] = min(current[0], start_index)
        current[1] = max(current[1], end_index)
    if set(bounds) != set(range(expected_count)):
        return None
    ranges = []
    for index in range(expected_count):
        start_index, end_index = bounds[index]
        try:
            start = float(starts[start_index])
            end = float(ends[end_index - 1])
        except (TypeError, ValueError):
            return None
        if start < 0 or end <= start:
            return None
        ranges.append((start, end))
    return ranges


def _needs_continuous_assembly(raw_audio_path, timing, ranges):
    """Detect provider segment timestamps that leave audible output unassigned.

    Text-to-Dialogue is one continuous acted performance. When its segment envelope does
    not cover the returned audio, slicing by those ranges can remove words. Character-level
    alignment is authoritative when present; older sidecars without it retain the complete
    conversation as one performance instead.
    """
    if not ranges:
        return False
    raw_duration = _probe_duration(raw_audio_path)
    covered_start = min(start for start, _ in ranges)
    covered_end = max(end for _, end in ranges)
    gaps = [next_start - end for (_, end), (next_start, _) in zip(ranges, ranges[1:])]
    return (covered_start > TIMING_COVERAGE_TOLERANCE_SEC or
            raw_duration - covered_end > TIMING_COVERAGE_TOLERANCE_SEC or
            any(gap > TIMING_COVERAGE_TOLERANCE_SEC for gap in gaps))


def _render_continuous_dialogue_master(raw_audio, dialogue_lines, duration_sec, out,
                                       ranges, timing_path):
    """Place a Text-to-Dialogue conversation once when per-turn timestamps are unsafe."""
    first = dialogue_lines[0]
    try:
        target_start = float(
            first.get("startSec")
            if first.get("startSec") is not None else first.get("startsAtSec"))
    except (TypeError, ValueError) as exc:
        raise AudioTimingError("dialogue line 1 has no approved start anchor") from exc
    raw_duration = _probe_duration(raw_audio)
    target_end = target_start + raw_duration
    if target_start < 0 or target_end > duration_sec + WINDOW_TOLERANCE_SEC:
        raise AudioTimingError(
            f"continuous dialogue performance needs {target_end:.2f}s but the shot is "
            f"{duration_sec:.2f}s")

    delay_ms = int(round(target_start * 1000))
    filters = (
        f"[0:a]aformat=sample_rates={SAMPLE_RATE}:channel_layouts=stereo,"
        f"adelay={delay_ms}|{delay_ms}[performance];"
        f"[1:a]atrim=duration={duration_sec:.6f},asetpts=PTS-STARTPTS[silence];"
        "[silence][performance]amix=inputs=2:duration=first:"
        f"dropout_transition=0:normalize=0,atrim=duration={duration_sec:.6f}[outa]"
    )
    command = [
        "ffmpeg", "-y", "-i", str(raw_audio), "-f", "lavfi", "-t",
        f"{duration_sec:.6f}", "-i",
        f"anullsrc=channel_layout=stereo:sample_rate={SAMPLE_RATE}",
        "-filter_complex", filters, "-map", "[outa]", "-ar", str(SAMPLE_RATE),
        "-ac", str(CHANNELS), "-c:a", "pcm_s16le", str(out),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode or not out.is_file():
        raise AudioTimingError(
            "could not preserve the continuous dialogue performance: " + result.stderr[-400:]
        )

    placements = []
    for index, (line, source_range) in enumerate(zip(dialogue_lines, ranges)):
        placements.append({
            "dialogueIndex": index,
            "dialogueOccurrenceId": line.get("dialogueOccurrenceId"),
            "sourceStartSec": source_range[0],
            "sourceEndSec": source_range[1],
            "targetStartSec": target_start + source_range[0],
            "targetEndSec": target_start + source_range[1],
            "continuousPerformance": True,
        })
    contract = {
        "schemaVersion": 1,
        "assemblyMode": "continuous-dialogue-performance",
        "rawAudioPath": str(raw_audio),
        "rawAudioSha256": file_sha256(raw_audio),
        "dialogueTimingPath": str(timing_path),
        "dialogueTimingSha256": file_sha256(timing_path),
        "durationSec": duration_sec,
        "performanceTargetStartSec": target_start,
        "performanceTargetEndSec": target_end,
        "placements": placements,
        "outputPath": str(out),
        "outputSha256": file_sha256(out),
    }
    contract_path = timed_master_contract_path(out)
    contract_path.write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    return {**contract, "contractPath": str(contract_path),
            "contractSha256": file_sha256(contract_path)}


def render_timed_dialogue_master(raw_audio, timing_path, dialogue_lines,
                                 duration_sec, out):
    """Place exact acted ranges at approved starts without clipping natural delivery."""
    raw_audio = pathlib.Path(raw_audio).resolve()
    timing_path = pathlib.Path(timing_path).resolve()
    out = pathlib.Path(out).resolve()
    duration_sec = float(duration_sec)
    if duration_sec <= 0 or not dialogue_lines:
        raise AudioTimingError("a timed dialogue master needs lines and a positive duration")
    if not raw_audio.is_file():
        raise AudioTimingError(f"raw dialogue audio is missing: {raw_audio}")
    timing = _read_json(timing_path)
    if timing.get("audioSha256") != file_sha256(raw_audio):
        raise AudioTimingError("dialogue timing metadata does not match the raw audio bytes")
    ranges = _source_ranges(timing, len(dialogue_lines))
    if _needs_continuous_assembly(raw_audio, timing, ranges):
        out.parent.mkdir(parents=True, exist_ok=True)
        return _render_continuous_dialogue_master(
            raw_audio, dialogue_lines, duration_sec, out, ranges, timing_path)

    authored = []
    for index, (line, source_range) in enumerate(zip(dialogue_lines, ranges)):
        try:
            target_start = float(
                line.get("startSec")
                if line.get("startSec") is not None else line.get("startsAtSec"))
            target_end = float((line.get("endSec") if line.get("endSec") is not None else (
                target_start + float(line["estimatedDurationSec"])
                if line.get("estimatedDurationSec") is not None else None
            )))
        except (KeyError, TypeError, ValueError) as exc:
            raise AudioTimingError(f"dialogue line {index + 1} has no approved timing window") from exc
        if target_start < 0 or target_end <= target_start or target_end > duration_sec + 0.001:
            raise AudioTimingError(f"dialogue line {index + 1} falls outside the shot duration")
        authored.append((index, line, source_range, target_start, target_end))

    placements = []
    for position, (index, line, source_range, target_start, target_end) in enumerate(authored):
        source_start, source_end = source_range
        source_duration = source_end - source_start
        next_start = authored[position + 1][3] if position + 1 < len(authored) else duration_sec
        available_duration = next_start - target_start
        if available_duration <= 0:
            raise AudioTimingError(
                f"dialogue line {index + 1}'s start anchor is not before the next line"
            )
        if source_duration > available_duration + WINDOW_TOLERANCE_SEC:
            raise AudioTimingError(
                f"dialogue line {index + 1}'s approved take is {source_duration:.2f}s but only "
                f"{available_duration:.2f}s remains before the next approved start; reject or "
                "retime the performance"
            )
        placements.append({
            "dialogueIndex": index,
            "dialogueOccurrenceId": line.get("dialogueOccurrenceId"),
            "sourceStartSec": source_start,
            "sourceEndSec": source_end,
            "targetStartSec": target_start,
            "targetEndSec": target_start + source_duration,
            "approvedWindowEndSec": target_end,
            "naturalExtensionSec": max(0.0, target_start + source_duration - target_end),
        })

    out.parent.mkdir(parents=True, exist_ok=True)
    split_labels = "".join(f"[src{index}]" for index in range(len(placements)))
    filters = [
        f"[0:a]asplit={len(placements)}{split_labels}",
        f"[1:a]atrim=duration={duration_sec:.6f},asetpts=PTS-STARTPTS[silence]",
    ]
    mixed_labels = ["[silence]"]
    for index, placement in enumerate(placements):
        delay_ms = int(round(placement["targetStartSec"] * 1000))
        line_duration = placement["sourceEndSec"] - placement["sourceStartSec"]
        fade = min(EDGE_FADE_SEC, line_duration / 4)
        fade_out_start = max(0.0, line_duration - fade)
        filters.append(
            f"[src{index}]atrim=start={placement['sourceStartSec']:.6f}:"
            f"end={placement['sourceEndSec']:.6f},asetpts=PTS-STARTPTS,"
            f"aformat=sample_rates={SAMPLE_RATE}:channel_layouts=stereo,"
            f"afade=t=in:st=0:d={fade:.6f},"
            f"afade=t=out:st={fade_out_start:.6f}:d={fade:.6f},"
            f"adelay={delay_ms}|{delay_ms}[line{index}]"
        )
        placement["edgeFadeSec"] = fade
        mixed_labels.append(f"[line{index}]")
    filters.append(
        "".join(mixed_labels) +
        f"amix=inputs={len(mixed_labels)}:duration=first:dropout_transition=0:normalize=0,"
        f"atrim=duration={duration_sec:.6f}[outa]"
    )
    command = [
        "ffmpeg", "-y", "-i", str(raw_audio), "-f", "lavfi", "-t",
        f"{duration_sec:.6f}", "-i",
        f"anullsrc=channel_layout=stereo:sample_rate={SAMPLE_RATE}",
        "-filter_complex", ";".join(filters), "-map", "[outa]", "-ar",
        str(SAMPLE_RATE), "-ac", str(CHANNELS), "-c:a", "pcm_s16le", str(out),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode or not out.is_file():
        raise AudioTimingError(
            "could not build the timed dialogue master: " + result.stderr[-400:]
        )
    actual_duration = _probe_duration(out)
    if abs(actual_duration - duration_sec) > WINDOW_TOLERANCE_SEC:
        raise AudioTimingError(
            f"timed dialogue master is {actual_duration:.3f}s, expected {duration_sec:.3f}s"
        )
    contract = {
        "schemaVersion": 1,
        "rawAudioPath": str(raw_audio),
        "rawAudioSha256": file_sha256(raw_audio),
        "dialogueTimingPath": str(timing_path),
        "dialogueTimingSha256": file_sha256(timing_path),
        "durationSec": duration_sec,
        "placements": placements,
        "outputPath": str(out),
        "outputSha256": file_sha256(out),
    }
    contract_path = timed_master_contract_path(out)
    contract_path.write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    return {**contract, "contractPath": str(contract_path),
            "contractSha256": file_sha256(contract_path)}


def slice_timed_master(master_audio, start_sec, end_sec, out):
    """Derive one byte-bound provider audio reference from an approved timed master."""
    master_audio = pathlib.Path(master_audio).resolve()
    out = pathlib.Path(out).resolve()
    start_sec, end_sec = float(start_sec), float(end_sec)
    if not master_audio.is_file() or start_sec < 0 or end_sec <= start_sec:
        raise AudioTimingError("invalid timed-master slice request")
    out.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(master_audio), "-af",
            f"atrim=start={start_sec:.6f}:end={end_sec:.6f},asetpts=PTS-STARTPTS",
            "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS), "-c:a", "pcm_s16le",
            str(out),
        ],
        capture_output=True, text=True,
    )
    if result.returncode or not out.is_file():
        raise AudioTimingError("could not derive provider audio slice: " + result.stderr[-400:])
    expected = end_sec - start_sec
    actual = _probe_duration(out)
    if abs(actual - expected) > WINDOW_TOLERANCE_SEC:
        raise AudioTimingError(
            f"provider audio slice is {actual:.3f}s, expected {expected:.3f}s"
        )
    return {
        "path": str(out), "sha256": file_sha256(out),
        "sourcePath": str(master_audio), "sourceSha256": file_sha256(master_audio),
        "sourceStartSec": start_sec, "sourceEndSec": end_sec,
        "durationSec": expected,
    }


def replace_timed_dialogue_segment(master_audio, replacement_audio,
                                   replacement_timing_path, target_start_sec,
                                   available_end_sec, old_end_sec, out):
    """Replace one contaminated dialogue region without touching other performances."""
    master_audio = pathlib.Path(master_audio).resolve()
    replacement_audio = pathlib.Path(replacement_audio).resolve()
    replacement_timing_path = pathlib.Path(replacement_timing_path).resolve()
    out = pathlib.Path(out).resolve()
    if not master_audio.is_file() or not replacement_audio.is_file():
        raise AudioTimingError("segment repair source audio is missing")
    timing = _read_json(replacement_timing_path)
    if timing.get("audioSha256") != file_sha256(replacement_audio):
        raise AudioTimingError("replacement timing metadata does not match its audio")
    source_start, source_end = _source_ranges(timing, 1)[0]
    source_duration = source_end - source_start
    target_start_sec = float(target_start_sec)
    available_end_sec = float(available_end_sec)
    old_end_sec = float(old_end_sec)
    if source_duration > available_end_sec - target_start_sec + WINDOW_TOLERANCE_SEC:
        raise AudioTimingError(
            f"replacement take is {source_duration:.2f}s but only "
            f"{available_end_sec - target_start_sec:.2f}s is available")
    master_duration = _probe_duration(master_audio)
    if target_start_sec < 0 or old_end_sec <= target_start_sec or available_end_sec > master_duration:
        raise AudioTimingError("invalid segment repair window")
    fade = min(EDGE_FADE_SEC, source_duration / 4)
    fade_out_start = max(0.0, source_duration - fade)
    delay_ms = int(round(target_start_sec * 1000))
    filters = (
        f"[0:a]volume=0:enable='between(t,{target_start_sec:.6f},{old_end_sec:.6f})'[base];"
        f"[1:a]atrim=start={source_start:.6f}:end={source_end:.6f},"
        "asetpts=PTS-STARTPTS,"
        f"aformat=sample_rates={SAMPLE_RATE}:channel_layouts=stereo,"
        f"afade=t=in:st=0:d={fade:.6f},"
        f"afade=t=out:st={fade_out_start:.6f}:d={fade:.6f},"
        f"adelay={delay_ms}|{delay_ms}[replacement];"
        "[base][replacement]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[outa]"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([
        "ffmpeg", "-y", "-i", str(master_audio), "-i", str(replacement_audio),
        "-filter_complex", filters, "-map", "[outa]", "-ar", str(SAMPLE_RATE),
        "-ac", str(CHANNELS), "-c:a", "pcm_s16le", str(out),
    ], capture_output=True, text=True)
    if result.returncode or not out.is_file():
        raise AudioTimingError("could not replace dialogue segment: " + result.stderr[-400:])
    actual_duration = _probe_duration(out)
    if abs(actual_duration - master_duration) > WINDOW_TOLERANCE_SEC:
        raise AudioTimingError("segment repair changed the master duration")
    contract = {
        "schemaVersion": 1,
        "operation": "replace-timed-dialogue-segment",
        "masterSourcePath": str(master_audio),
        "masterSourceSha256": file_sha256(master_audio),
        "replacementAudioPath": str(replacement_audio),
        "replacementAudioSha256": file_sha256(replacement_audio),
        "replacementTimingPath": str(replacement_timing_path),
        "replacementTimingSha256": file_sha256(replacement_timing_path),
        "targetStartSec": target_start_sec,
        "targetEndSec": target_start_sec + source_duration,
        "availableEndSec": available_end_sec,
        "replacedEndSec": old_end_sec,
        "edgeFadeSec": fade,
        "durationSec": master_duration,
        "outputPath": str(out),
        "outputSha256": file_sha256(out),
    }
    contract_path = timed_master_contract_path(out)
    contract_path.write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    return {**contract, "contractPath": str(contract_path),
            "contractSha256": file_sha256(contract_path)}
