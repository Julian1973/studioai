"""Provider transport planning for one approved Studio animation unit.

Studio shots remain the creative and review unit. When an explicitly selected comparison
provider has a shorter request limit, this module groups consecutive approved Animation
Director stages into legal calls and deterministically compiles those calls from the same
approved typed direction. It never contacts a provider or changes an approval.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import pathlib
import re
import subprocess

import cb_emission_conformance as emission
import cb_post
import cb_seedance_pipeline


COMPARISON_MODEL_ID = "fal-seedance-2.0"
MIN_SEGMENT_SEC = 4.0
MAX_SEGMENT_SEC = 15.0


class TransportPlanError(RuntimeError):
    """Approved direction cannot be transported without changing its stage structure."""


def _digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode()).hexdigest()


def _timed_stages(stage_plan, duration_sec):
    rows = []
    for index, stage in enumerate(stage_plan or [], start=1):
        try:
            number = int(stage.get("stageNumber", index))
            start = float(stage["startSec"])
            end = float(stage["endSec"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TransportPlanError(
                "comparison transport requires approved timestamps on every animation stage"
            ) from exc
        if number != index or start < 0 or end <= start:
            raise TransportPlanError("approved animation stages are not consecutive and valid")
        if rows and abs(start - rows[-1]["endSec"]) > 0.001:
            raise TransportPlanError("approved animation stages have a gap or overlap")
        rows.append({"stage": stage, "stageNumber": number,
                     "startSec": start, "endSec": end})
    if not rows:
        raise TransportPlanError("approved Animation direction has no stage plan")
    if abs(rows[0]["startSec"]) > 0.001 or abs(rows[-1]["endSec"] - duration_sec) > 0.001:
        raise TransportPlanError("approved animation stages do not cover the shot duration")
    return rows


def plan_stage_segments(stage_plan, duration_sec, *, min_sec=MIN_SEGMENT_SEC,
                        max_sec=MAX_SEGMENT_SEC):
    """Find the fewest legal calls, with every boundary on an approved stage end."""
    duration_sec = float(duration_sec)
    if not (min_sec <= duration_sec <= 30):
        raise TransportPlanError("comparison transport supports 4-30 second Studio units")
    if duration_sec <= max_sec:
        numbers = [int(stage.get("stageNumber", index))
                   for index, stage in enumerate(stage_plan or [], start=1)]
        if not numbers:
            raise TransportPlanError("approved Animation direction has no stage plan")
        return [{
            "segmentIndex": 1, "globalStartSec": 0.0,
            "globalEndSec": duration_sec, "durationSec": duration_sec,
            "stageNumbers": numbers,
        }]

    rows = _timed_stages(stage_plan, duration_sec)
    memo = {}

    def solve(start_index):
        if start_index == len(rows):
            return []
        if start_index in memo:
            return memo[start_index]
        choices = []
        global_start = rows[start_index]["startSec"]
        for end_index in range(start_index, len(rows)):
            global_end = rows[end_index]["endSec"]
            segment_duration = global_end - global_start
            if segment_duration > max_sec + 0.001:
                break
            if segment_duration < min_sec - 0.001:
                continue
            if abs(segment_duration - round(segment_duration)) > 0.001:
                continue
            rest = solve(end_index + 1)
            if rest is None:
                continue
            current = [{
                "globalStartSec": global_start,
                "globalEndSec": global_end,
                "durationSec": segment_duration,
                "stageNumbers": [
                    row["stageNumber"] for row in rows[start_index:end_index + 1]
                ],
            }, *rest]
            choices.append(current)
        if not choices:
            memo[start_index] = None
            return None
        memo[start_index] = min(
            choices,
            key=lambda choice: (
                len(choice),
                tuple(-round(item["durationSec"], 3) for item in choice),
            ),
        )
        return memo[start_index]

    result = solve(0)
    if not result:
        raise TransportPlanError(
            "the approved stage boundaries cannot form legal 4-15 second comparison calls"
        )
    return [{"segmentIndex": index, **item}
            for index, item in enumerate(result, start=1)]


def _line_indexes_for_segment(dialogue_lines, segment):
    selected = []
    start, end = segment["globalStartSec"], segment["globalEndSec"]
    for index, line in enumerate(dialogue_lines or []):
        try:
            line_start, line_end = float(line["startSec"]), float(line["endSec"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TransportPlanError(
                f"dialogue line {index + 1} has no approved timing window"
            ) from exc
        intersects = line_start < end - 0.001 and line_end > start + 0.001
        contained = line_start >= start - 0.001 and line_end <= end + 0.001
        if intersects and not contained:
            raise TransportPlanError(
                f"approved stage boundary at {end:g}s crosses dialogue line {index + 1}"
            )
        if contained:
            selected.append(index)
    return selected


def _rebase_stages(base_stages, stage_numbers, global_start):
    selected = []
    wanted = set(stage_numbers)
    for index, stage in enumerate(base_stages or [], start=1):
        if index not in wanted:
            continue
        item = copy.deepcopy(stage)
        time_value = str(item.get("time") or "")
        parsed = cb_seedance_pipeline._parse_time_range(time_value) if time_value else None
        if parsed:
            item["time"] = (
                f"{parsed[0] - global_start:g}-{parsed[1] - global_start:g} seconds"
            )
        selected.append(item)
    if len(selected) != len(stage_numbers):
        raise TransportPlanError("compiled task stages do not match approved stage numbers")
    return selected


def _reference_tag(reference):
    return str(reference.get("tag") or "").lower().replace(" ", "")


def _provider_reference_tags(task):
    """Translate Studio slot labels to the provider's upload-order reference syntax."""
    mapping = {}
    prefixes = {"images": "@Image", "videos": "@Video", "audio": "@Audio"}
    for kind, prefix in prefixes.items():
        for index, asset in enumerate((task.get("assets") or {}).get(kind) or [], start=1):
            old = _reference_tag(asset)
            new = f"{prefix}{index}"
            if old:
                mapping[old] = new
            asset["tag"] = new
    for reference in task.get("references") or []:
        replacement = mapping.get(_reference_tag(reference))
        if replacement:
            reference["tag"] = replacement

    token = re.compile(r"@(image|audio|video|图)\s*(\d+)", re.IGNORECASE)

    def replace(value):
        if isinstance(value, str):
            return token.sub(
                lambda match: mapping.get(
                    f"@{match.group(1)}{match.group(2)}".lower(), match.group(0)),
                value,
            )
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        return value

    return replace(task)


def _segment_task(base_task, shot_id, segment, segment_count, dialogue_lines):
    task = _provider_reference_tags(copy.deepcopy(base_task))
    task["type"] = "reference_based_generation"
    task["duration_seconds"] = segment["durationSec"]
    task["goal"] = (
        f"Execute only approved stages {', '.join(map(str, segment['stageNumbers']))} of "
        f"production unit {shot_id}. Continue from the supplied opening frame, preserve "
        "everything already established, and reach the final selected stage's approved "
        "observable end state."
    )
    task["stages"] = _rebase_stages(
        task.get("stages") or [], segment["stageNumbers"], segment["globalStartSec"])
    task["forbidden"] = list(task.get("forbidden") or []) + [
        "do not replay stages outside this segment",
        "no new story event or unapproved action",
    ]
    if segment["segmentIndex"] > 1:
        task["forbidden"].extend((
            "no hard cut at the opening relay boundary",
            "nothing appears out of thin air",
        ))
        image_refs = [item for item in (task.get("references") or [])
                      if not _reference_tag(item).startswith("@audio")]
        if not image_refs:
            raise TransportPlanError("comparison continuation has no opening-image reference")
        first = image_refs[0]
        first.update({
            "subject": "Literal Opening Relay Frame",
            "defines": (
                "the exact opening composition, poses, prop state, scene state, lighting, "
                "camera direction, and motion trend inherited from the preceding segment"
            ),
            "exclude": "nothing; this image has opening-frame authority",
        })
    dialogue_speakers = list(dict.fromkeys(
        str((line or {}).get("speaker") or "").strip()
        for line in dialogue_lines
        if str((line or {}).get("speaker") or "").strip()
    ))
    if dialogue_lines:
        speaker_names = ", ".join(dialogue_speakers)
        task["audio"] = (
            "@Audio1 is the sole authority for English voice identity, cadence, delivery, "
            f"mouth timing and silence for {speaker_names}. The exact braced dialogue "
            "markers below place approved words only; no alternative performance is "
            "permitted. Listeners remain silent and closed-mouth. No narration, no extra "
            "words, and no subtitles or captions. The rendered dialogue is a guide track; "
            "approved @Audio1 remains the film dialogue in post.\n" + "\n".join(
                emission.dialogue_placement_line(line) for line in dialogue_lines
            ) + "\nSeedance may generate only non-dialogue ambience, foley, comedy "
            "impacts, wing buzzes, plant movement, and low supportive underscore."
        )
        task["assets"]["audio"] = [{
            "tag": "@Audio1", "subject": "approved timed dialogue",
            "duration_seconds": segment["durationSec"],
        }]
    else:
        task["references"] = [item for item in (task.get("references") or [])
                              if not _reference_tag(item).startswith("@audio")]
        task["assets"]["audio"] = []
        task["audio"] = (
            "No dialogue occurs in this segment. Seedance may generate ambience, foley, "
            "designed non-dialogue sound effects, and low supportive underscore. Do not "
            "invent or repeat dialogue from another stage."
        )
    task["transportContext"] = None
    task.pop("transportContext", None)
    return task


def build_comparison_plan(*, shot, approved_direction, base_task, parent_prompt,
                          comparison_run_id, model_id=COMPARISON_MODEL_ID):
    """Compile provider prompts from the current approved Animation direction."""
    if model_id != COMPARISON_MODEL_ID:
        raise TransportPlanError("only fal-seedance-2.0 is allowed for this comparison")
    comparison_run_id = str(comparison_run_id or "").strip()
    if not comparison_run_id or len(comparison_run_id) > 120:
        raise TransportPlanError("a bounded comparison run ID is required")
    shot_id = str(shot.get("shotId") or "").strip()
    duration = float(shot.get("durationSec") or 0)
    if float(approved_direction.get("durationSec") or 0) != duration:
        raise TransportPlanError("approved Animation duration differs from the Studio shot")
    stage_plan = approved_direction.get("stagePlan") or []
    segments = plan_stage_segments(stage_plan, duration)
    output = []
    for segment in segments:
        line_indexes = _line_indexes_for_segment(shot.get("dialogueLines") or [], segment)
        dialogue_speakers = list(dict.fromkeys(
            str((shot.get("dialogueLines") or [])[index].get("speaker") or "").strip()
            for index in line_indexes
            if str((shot.get("dialogueLines") or [])[index].get("speaker") or "").strip()
        ))
        segment_dialogue = [
            (shot.get("dialogueLines") or [])[index] for index in line_indexes
        ]
        task = _segment_task(
            base_task, shot_id, segment, len(segments), segment_dialogue)
        try:
            prompt = cb_seedance_pipeline.SeedancePromptBuilder(task).build()
        except ValueError as exc:
            raise TransportPlanError(
                f"could not compile provider segment {segment['segmentIndex']}: {exc}"
            ) from exc
        if dialogue_speakers:
            prompt = (
                "AUDIO-AUTHORITY: @Audio1 is the sole authority for English voice identity, "
                "cadence, delivery, mouth timing and silence; no alternative performance "
                "is permitted. Listeners remain silent and closed-mouth. No narration, no "
                "extra words, and no subtitles or captions.\n" + prompt
            )
            synthesis = emission.validate_dialogue_synthesis(
                prompt, segment_dialogue)
            if not synthesis["ready"]:
                raise TransportPlanError(
                    "comparison dialogue synthesis contract failed: "
                    + "; ".join(synthesis["errors"]))
        output.append({
            **segment,
            "prompt": prompt,
            "promptHash": hashlib.sha256(prompt.encode()).hexdigest(),
            "dialogueLineIndexes": line_indexes,
            "dialogueSpeakers": dialogue_speakers,
            "referenceContract": task.get("references") or [],
            "compiledStages": task.get("stages") or [],
            "dynamicOpeningRelay": segment["segmentIndex"] > 1,
        })
    return {
        "schemaVersion": 1,
        "mode": "approved-stage-relay-comparison",
        "comparisonRunId": comparison_run_id,
        "providerModelId": model_id,
        "studioShotId": shot_id,
        "studioDurationSec": duration,
        "studioCandidateCountMeaning": "one review candidate after internal calls are joined",
        "parentPromptHash": hashlib.sha256(str(parent_prompt).encode()).hexdigest(),
        "approvedDirectionHash": _digest(approved_direction),
        "stageBoundaryLaw": "every internal boundary is an approved Animation stage end",
        "segments": output,
    }


def _has_audio(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
         "stream=codec_type", "-of", "default=nk=1:nw=1", str(path)],
        capture_output=True, text=True,
    )
    return result.returncode == 0 and "audio" in result.stdout


def _with_audio(path, work_dir):
    path = pathlib.Path(path).resolve()
    if _has_audio(path):
        return path
    out = pathlib.Path(work_dir) / f"{path.stem}_with_silence.mp4"
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(path), "-f", "lavfi", "-i",
            f"anullsrc=channel_layout=stereo:sample_rate={cb_post.DELIVERY_AUDIO_HZ}",
            "-shortest", "-c:v", "copy", "-c:a", "aac", "-ar",
            str(cb_post.DELIVERY_AUDIO_HZ), "-ac", "2", "-b:a", "192k", str(out),
        ],
        capture_output=True, text=True,
    )
    if result.returncode or not out.is_file():
        raise TransportPlanError("could not add silence to an internal provider segment")
    return out


def join_segments(segment_paths, out):
    """Join internal transport calls exactly, with no editorial trim, fade, or final hold."""
    if not segment_paths:
        raise TransportPlanError("no provider segments exist to join")
    out = pathlib.Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    work_dir = out.parent / f".{out.stem}_transport"
    work_dir.mkdir(parents=True, exist_ok=True)
    paths = [_with_audio(path, work_dir) for path in segment_paths]
    inputs = []
    for path in paths:
        inputs.extend(("-i", str(path)))
    filters = []
    for index in range(len(paths)):
        filters.append(
            f"[{index}:v]fps={cb_post.DELIVERY_FPS:g},setsar=1,"
            f"format={cb_post.DELIVERY_PIXEL_FORMAT}[v{index}]"
        )
        filters.append(
            f"[{index}:a]aformat=sample_rates={cb_post.DELIVERY_AUDIO_HZ}:"
            f"channel_layouts=stereo[a{index}]"
        )
    joins = "".join(f"[v{index}][a{index}]" for index in range(len(paths)))
    filters.append(f"{joins}concat=n={len(paths)}:v=1:a=1[v][a]")
    command = [
        "ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filters),
        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
        "-crf", "18", "-r", f"{cb_post.DELIVERY_FPS:g}", "-pix_fmt",
        cb_post.DELIVERY_PIXEL_FORMAT, *cb_post.DELIVERY_X264_COLOR_ARGS,
        "-c:a", "aac", "-ar", str(cb_post.DELIVERY_AUDIO_HZ), "-ac", "2",
        "-b:a", "256k", "-movflags", "+faststart", str(out),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode or not out.is_file():
        raise TransportPlanError("could not join provider segments: " + result.stderr[-400:])
    return str(out)
