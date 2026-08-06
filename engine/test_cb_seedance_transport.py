import copy
import subprocess

import pytest

import cb_seedance_transport as transport


def _stages():
    windows = [(0, 7), (7, 15), (15, 22), (22, 28)]
    return [{
        "stageNumber": index,
        "beatIds": [f"1.B{min(index, 3)}"],
        "purpose": f"Approved purpose {index}",
        "startSec": start,
        "endSec": end,
        "initialOrCarriedState": f"Approved opening state {index}",
        "primaryEvent": f"One visible causal event {index}",
        "observableEndState": f"Approved visible end state {index}",
        "emotionOrCameraAnalysis": f"Observable performance and camera reason {index}",
    } for index, (start, end) in enumerate(windows, start=1)]


def _base_task():
    return {
        "type": "thirty_second_video",
        "goal": "Deliver the approved comedy escalation in the meadow.",
        "duration_seconds": 28,
        "aspect_ratio": "16:9",
        "resolution": "720p",
        "assets": {
            "images": [
                {"tag": "@Image1", "subject": "opening frame"},
                {"tag": "@Image2", "subject": "Fuzzby"},
                {"tag": "@Image3", "subject": "Zenny"},
            ],
            "videos": [],
            "audio": [{"tag": "@Audio1", "subject": "approved dialogue",
                       "duration_seconds": 28}],
        },
        "references": [
            {"tag": "@Image1", "subject": "Opening Frame",
             "defines": "opening composition and pose", "exclude": "nothing"},
            {"tag": "@Image2", "subject": "Fuzzby",
             "defines": "identity and materials", "exclude": "the background"},
            {"tag": "@Image3", "subject": "Zenny",
             "defines": "identity and materials", "exclude": "the background"},
            {"tag": "@Audio1", "subject": "Approved Dialogue",
             "defines": "voice, performance, and timing", "exclude": "music"},
        ],
        "stages": [{
            "time": f"{stage['startSec']}-{stage['endSec']} seconds",
            "purpose": stage["purpose"],
            "initial_state": stage["initialOrCarriedState"],
            "event": stage["primaryEvent"],
            "end_state": stage["observableEndState"],
            "emotion_or_camera": stage["emotionOrCameraAnalysis"],
        } for stage in _stages()],
        "scene_style": "Premium stylized 3D CGI with natural fur and meadow materials.",
        "camera": "Keep causal action readable and motivated through approved internal cuts.",
        "audio": "@Audio1 is the sole dialogue source. Natural foley only; no music.",
        "consistency": [
            "Keep identity, scale, scene geography, prop state, lighting, and camera axis stable."
        ],
        "no_music": True,
    }


def _shot():
    return {
        "shotId": "S1.SH1", "durationSec": 28,
        "dialogueLines": [
            {"speaker": "Fuzzby", "exactText": "First locked line.",
             "startSec": 1, "endSec": 3},
            {"speaker": "Zenny", "exactText": "Second locked line.",
             "startSec": 10, "endSec": 12},
            {"speaker": "Fuzzby", "exactText": "Final locked line.",
             "startSec": 20, "endSec": 22},
        ],
    }


def test_28_second_unit_uses_approved_15_plus_13_stage_boundary():
    plan = transport.plan_stage_segments(_stages(), 28)
    assert [item["durationSec"] for item in plan] == [15, 13]
    assert [item["stageNumbers"] for item in plan] == [[1, 2], [3, 4]]


def test_comparison_plan_keeps_one_studio_unit_and_derives_two_prompts():
    direction = {"durationSec": 28, "stagePlan": _stages()}
    plan = transport.build_comparison_plan(
        shot=_shot(), approved_direction=direction, base_task=_base_task(),
        parent_prompt="The exact approved parent Animation Director prompt.",
        comparison_run_id="same-process-test")

    assert plan["studioShotId"] == "S1.SH1"
    assert plan["studioCandidateCountMeaning"].startswith("one review candidate")
    assert [item["durationSec"] for item in plan["segments"]] == [15, 13]
    assert plan["segments"][0]["dialogueLineIndexes"] == [0, 1]
    assert plan["segments"][1]["dialogueLineIndexes"] == [2]
    assert plan["segments"][1]["dynamicOpeningRelay"] is True
    assert plan["segments"][0]["prompt"].startswith(
        "@Audio1 is the sole source of English dialogue")
    assert "0-7 seconds" in plan["segments"][0]["prompt"]
    assert "0-7 seconds" in plan["segments"][1]["prompt"]
    for segment in plan["segments"]:
        assert "First locked line" not in segment["prompt"]
        assert "Final locked line" not in segment["prompt"]


def test_comparison_translates_studio_slots_to_provider_upload_tags():
    task = _base_task()
    task["assets"]["images"][0]["tag"] = "@图1"
    task["assets"]["images"][1]["tag"] = "@图2"
    task["assets"]["images"][2]["tag"] = "@图3"
    task["references"][0]["tag"] = "@图1"
    task["references"][1]["tag"] = "@图2"
    task["references"][2]["tag"] = "@图3"
    task["camera"] += " Preserve the camera axis defined beside @图 1."

    plan = transport.build_comparison_plan(
        shot=_shot(), approved_direction={"durationSec": 28, "stagePlan": _stages()},
        base_task=task, parent_prompt="approved", comparison_run_id="same-process-test")

    for segment in plan["segments"]:
        assert "@图" not in segment["prompt"]
        assert "@Image1" in segment["prompt"]
        assert [item["tag"] for item in segment["referenceContract"][:3]] == [
            "@Image1", "@Image2", "@Image3"]


def test_comparison_refuses_a_boundary_that_crosses_dialogue():
    shot = copy.deepcopy(_shot())
    shot["dialogueLines"][1].update({"startSec": 14, "endSec": 16})
    with pytest.raises(transport.TransportPlanError, match="crosses dialogue"):
        transport.build_comparison_plan(
            shot=shot, approved_direction={"durationSec": 28, "stagePlan": _stages()},
            base_task=_base_task(), parent_prompt="approved",
            comparison_run_id="same-process-test")


def test_comparison_uses_other_approved_boundaries_when_best_split_is_fractional():
    stages = _stages()
    stages[1]["endSec"] = 14.5
    stages[2]["startSec"] = 14.5
    plan = transport.plan_stage_segments(stages, 28)
    assert [item["durationSec"] for item in plan] == [7, 15, 6]
    assert [item["stageNumbers"] for item in plan] == [[1], [2, 3], [4]]


def test_comparison_refuses_when_no_approved_integer_windows_exist():
    stages = _stages()
    stages[0]["endSec"] = 14.5
    stages[1]["startSec"] = 14.5
    stages[1]["endSec"] = 28
    stages = stages[:2]
    with pytest.raises(transport.TransportPlanError, match="cannot form legal"):
        transport.plan_stage_segments(stages, 28)


def test_internal_segments_join_locally_with_an_audio_track(tmp_path):
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    out = tmp_path / "joined.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:s=64x64:r=24:d=0.5",
        "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(first),
    ], check=True, capture_output=True)
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=64x64:r=24:d=0.5",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(second),
    ], check=True, capture_output=True)

    assert transport.join_segments([first, second], out) == str(out.resolve())
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nk=1:nw=1", str(out),
    ], check=True, capture_output=True, text=True)
    assert 0.9 <= float(probe.stdout.strip()) <= 1.2
    assert transport._has_audio(out) is True
