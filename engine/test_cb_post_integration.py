"""Real, zero-provider post-production golden path through local ffmpeg."""
import pathlib
import shutil
import subprocess

import pytest

import cb_post


def _make_approved_take(path):
    command = [
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        "color=c=0x3d6278:s=1280x720:r=24:d=2",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2",
        "-filter:a", "volume=-18dB", "-shortest",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-c:a", "aac", "-ar", "48000", "-ac", "2", str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-1000:])


def test_real_local_post_builds_and_probes_delivery_master(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg and ffprobe are required for the real post golden path")

    clip = tmp_path / "approved_take.mp4"
    _make_approved_take(clip)
    manifest = cb_post.build_scene_post(
        [{"shotId": "S1.SH1", "approvedTake": str(clip), "dialogueLines": []}],
        tmp_path / "post", "EpLocal", "1",
        {"kind": "scene-post", "source": "synthetic-approved-take"},
        platform="youtube", candidate_id="real-local",
    )

    assert manifest["qc"]["passed"] is True
    assert manifest["qc"]["humanCreativeApprovalRequired"] is True
    assert manifest["measuredLoudness"]["integratedLufs"] == pytest.approx(-14, abs=1)
    assert manifest["measuredLoudness"]["truePeakDbtp"] <= -0.8

    master = pathlib.Path(manifest["outputs"]["master16x9"]["path"])
    vertical = pathlib.Path(manifest["outputs"]["master9x16"]["path"])
    audio = pathlib.Path(manifest["outputs"]["programAudio"]["path"])
    assert master.exists() and vertical.exists() and audio.exists()

    master_probe = cb_post._probe_media(master)
    vertical_probe = cb_post._probe_media(vertical)
    audio_probe = cb_post._probe_media(audio)
    assert master_probe["videoCodec"] == "h264"
    assert master_probe["pixelFormat"] == "yuv420p"
    assert master_probe["fps"] == pytest.approx(24, abs=0.02)
    assert master_probe["colorPrimaries"] == "bt709"
    assert master_probe["audioSampleRate"] == 48000
    assert vertical_probe["width"] == 1080
    assert vertical_probe["height"] == 1920
    assert audio_probe["audioCodec"] == "pcm_s24le"
    assert audio_probe["audioBitsPerRawSample"] == 24
    assert audio_probe["audioSampleRate"] == 48000
