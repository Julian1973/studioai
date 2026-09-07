#!/usr/bin/env python3
"""Build a local Episode 2 post review master from the approved-input manifest."""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import os
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

import cb_post  # noqa: E402


def _load_shots(input_root, episode):
    manifest_path = input_root / "episode.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return manifest, manifest.get("shots") or []
    legacy = sorted(input_root.glob(f"{episode}_assembly_review*_manifest.json"))
    if not legacy:
        raise RuntimeError(f"post input manifest is missing: {manifest_path}")
    source = legacy[-1]
    legacy_manifest = json.loads(source.read_text(encoding="utf-8"))
    shots = [
        {"id": item["shotId"], "scene": item["scene"], "render": item["sourcePath"]}
        for item in legacy_manifest.get("timeline", [])
    ]
    return {"episode": episode, "shots": shots}, shots


def _clip_path(input_root, render):
    path = pathlib.Path(render)
    if path.is_absolute() and path.is_file():
        return path
    if path.is_absolute():
        for root in (ROOT / "engine" / "media" / "shots", ROOT / "engine" / "media"):
            candidate = root / path.name
            if candidate.is_file():
                return candidate
    return input_root / path


def _assemble_scene_full(clips, out, micro_transition_after=None):
    """Assemble full scene renders, with optional tiny transitions at audited bad joins."""
    inputs = []
    filters = []
    for index, clip in enumerate(clips):
        inputs += ["-i", clip]
        filters.append(
            f"[{index}:v]fps=24,setsar=1,settb=AVTB,format=yuv420p[v{index}]"
        )
        filters.append(
            f"[{index}:a]aformat=sample_rates=48000:channel_layouts=stereo[a{index}]"
        )
    micro_transition_after = set(micro_transition_after or ())
    current_v, current_a = "v0", "a0"
    elapsed = cb_post._dur(clips[0])
    for index in range(1, len(clips)):
        if index - 1 in micro_transition_after:
            next_v, next_a = f"vx{index}", f"ax{index}"
            duration = 0.18
            filters.append(
                f"[{current_v}]setpts=PTS-STARTPTS,settb=AVTB[vxcur{index}]"
            )
            filters.append(
                f"[{current_a}]asetpts=PTS-STARTPTS[axcur{index}]"
            )
            filters.append(
                f"[vxcur{index}][v{index}]xfade=transition=fade:duration={duration:.3f}:"
                f"offset={max(0.0, elapsed - duration):.3f}[{next_v}]"
            )
            filters.append(
                f"[axcur{index}][a{index}]acrossfade=d={duration:.3f}:c1=tri:c2=tri[{next_a}]"
            )
            elapsed += cb_post._dur(clips[index]) - duration
        else:
            next_v, next_a = f"vc{index}", f"ac{index}"
            filters.append(
                f"[{current_v}][{current_a}][v{index}][a{index}]concat=n=2:v=1:a=1"
                f"[{next_v}][{next_a}]"
            )
            elapsed += cb_post._dur(clips[index])
        current_v, current_a = next_v, next_a
    filters.append(f"[{current_v}]null[v]")
    filters.append(f"[{current_a}]anull[a]")
    result = subprocess.run(
        ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filters),
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
         "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000",
         "-ac", "2", "-b:a", "256k", "-movflags", "+faststart", str(out)],
        capture_output=True, text=True,
    )
    if result.returncode or not out.is_file():
        raise RuntimeError(f"scene assembly failed: {result.stderr[-800:]}")
    return cb_post._dur(str(out))


def _assemble_episode_with_scene_transitions(scene_files, scene_durations, out):
    """Cross-dissolve only between scenes; preserve hard cuts inside each scene."""
    transition = 0.45
    inputs = []
    filters = []
    for index, scene_file in enumerate(scene_files):
        inputs += ["-i", str(scene_file)]
        filters.append(f"[{index}:v]setpts=PTS-STARTPTS[v{index}]")
        filters.append(f"[{index}:a]asetpts=PTS-STARTPTS[a{index}]")

    current_v = "v0"
    current_a = "a0"
    elapsed = scene_durations[0]
    for index in range(1, len(scene_files)):
        next_v = f"v{index}"
        next_a = f"a{index}"
        joined_v = f"vx{index}"
        joined_a = f"ax{index}"
        offset = max(0.0, elapsed - transition)
        filters.append(
            f"[{current_v}][{next_v}]xfade=transition=fade:duration={transition:.3f}:"
            f"offset={offset:.3f},format=yuv420p[{joined_v}]"
        )
        filters.append(
            f"[{current_a}][{next_a}]acrossfade=d={transition:.3f}:c1=tri:c2=tri[{joined_a}]"
        )
        current_v, current_a = joined_v, joined_a
        elapsed += scene_durations[index] - transition

    filters.append(f"[{current_v}]tpad=stop_mode=clone:stop_duration=0.40[vout]")
    filters.append(f"[{current_a}]apad=pad_dur=0.40[aout]")
    result = subprocess.run(
        ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filters),
         "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "medium",
         "-crf", "18", "-r", "24", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000",
         "-ac", "2", "-b:a", "256k", "-movflags", "+faststart", str(out)],
        capture_output=True, text=True,
    )
    if result.returncode or not out.is_file():
        raise RuntimeError(f"scene transition assembly failed: {result.stderr[-1000:]}")
    return cb_post._dur(str(out))


def build(episode: str = "Ep2") -> pathlib.Path:
    input_root = ROOT / "engine" / "media" / "post95" / f"{episode}_episode"
    manifest, shots = _load_shots(input_root, episode)
    if not shots:
        raise RuntimeError("post input manifest contains no approved shots")
    clips = [str(_clip_path(input_root, shot["render"])) for shot in shots]
    missing = [clip for clip in clips if not pathlib.Path(clip).is_file()]
    if missing:
        raise RuntimeError(f"approved render is missing: {missing[0]}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = ROOT / "engine" / "media" / "post95" / f"{episode}_episode" / f"review_{stamp}"
    output_root.mkdir(parents=True, exist_ok=False)
    picture = output_root / f"{episode}_picture_conformed.mp4"
    master = output_root / f"{episode}_post_review_youtube.mp4"
    vertical = output_root / f"{episode}_post_review_youtube_9x16.mp4"
    audio = output_root / f"{episode}_program_audio_24bit.wav"

    # Use the latest audit to identify same-scene joins that need a micro dissolve.
    audit_files = sorted(input_root.glob("boundary_audit_*/boundary_audit.json"))
    audited_pairs = set()
    if audit_files:
        audit = json.loads(audit_files[-1].read_text(encoding="utf-8"))
        audited_pairs = {
            (row["from"], row["to"])
            for row in audit.get("boundaries", [])
            if row.get("recommendation") == "REVIEW / RE-ANCHOR"
        }

    # Build each scene from complete approved renders. This deliberately bypasses
    # the legacy handle trim: the approved render is the authority for its full
    # dialogue and landing beat. Only scene boundaries receive dissolves.
    scene_numbers = []
    for shot in shots:
        if shot["scene"] not in scene_numbers:
            scene_numbers.append(shot["scene"])
    scene_files = []
    scene_durations = []
    for scene in scene_numbers:
        scene_indexes = [index for index, shot in enumerate(shots) if shot["scene"] == scene]
        scene_clips = [clips[index] for index in scene_indexes]
        scene_file = output_root / f"scene_{scene:02d}_full.mp4"
        # These are the exact in-scene joins identified by the boundary audit.
        micro_after = []
        for local_index in range(len(scene_clips) - 1):
            previous_id = shots[scene_indexes[local_index]]["id"]
            current_id = shots[scene_indexes[local_index + 1]]["id"]
            fallback_pairs = {
                ("S1.SH1", "S1.SH2"),
                ("S1.SH2", "S1.SH3"),
                ("S3.SH3", "S3.SH4"),
            }
            if (previous_id, current_id) in (audited_pairs or fallback_pairs):
                micro_after.append(local_index)
        scene_durations.append(_assemble_scene_full(scene_clips, scene_file, micro_after))
        scene_files.append(scene_file)
    duration = _assemble_episode_with_scene_transitions(
        scene_files, scene_durations, picture
    )
    # Studio review renders are often 854x480.  The post contract is 1080p, so make
    # the delivery-frame conversion explicit rather than reporting a false format.
    probe = cb_post._probe_media(picture)
    if not probe or probe.get("width") != 1920 or probe.get("height") != 1080:
        scaled = picture.with_name("picture_scaled.mp4")
        result = subprocess.run([
            "ffmpeg", "-y", "-i", str(picture),
            "-vf", "scale=1920:1080:flags=lanczos,fps=24,setsar=1,format=yuv420p",
            "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-preset", "medium",
            "-crf", "18", "-r", "24", "-pix_fmt", "yuv420p",
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
            "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "256k",
            "-movflags", "+faststart", str(scaled),
        ], capture_output=True, text=True)
        if result.returncode or not scaled.is_file():
            raise RuntimeError(f"1080p conform failed: {result.stderr[-600:]}")
        os.replace(scaled, picture)
    if not cb_post.mix(str(picture), None, None, str(master), platform="youtube"):
        raise RuntimeError("post mix/master failed; no review master was produced")
    if not cb_post.build_vertical_derivative(str(master), str(vertical)):
        raise RuntimeError("vertical review derivative failed")
    if not cb_post.extract_program_audio(str(master), str(audio)):
        raise RuntimeError("programme audio export failed")

    master_probe = cb_post._probe_media(master)
    loudness = cb_post._measure_loudness(master, cb_post.LOUDNESS_TARGETS["youtube"])
    report = {
        "status": "review-only-human-approval-required",
        "episode": episode,
        "sourceManifest": str(manifest_path),
        "approvedShotCount": len(shots),
        "durationSec": cb_post._dur(str(master)),
        "master": str(master),
        "vertical": str(vertical),
        "programAudio": str(audio),
        "masterProbe": master_probe,
        "measuredLoudness": loudness,
        "notes": [
            "Native approved Seedance audio was preserved and mastered; no voice replacement was performed.",
            "No music or ambience bed was supplied, so this is a picture-and-native-audio review master.",
            "Complete approved shot tails were preserved; audited in-scene joins use 0.18s micro-transitions, and scene boundaries use 0.45s video and audio dissolves.",
            "Human creative review is still required before delivery sign-off.",
        ],
        "editingPolicy": {
            "shotTailPolicy": "preserve-complete-approved-render",
            "withinSceneTransition": "hard-cut-except-audited-0.18s-micro-transition",
            "betweenSceneTransition": "0.45s-cross-dissolve-and-audio-crossfade",
        },
        "shots": [shot["id"] for shot in shots],
    }
    report_path = output_root / "post_review_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return master


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", default="Ep2")
    args = parser.parse_args()
    try:
        print(f"MASTER {build(args.episode)}")
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
