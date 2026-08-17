#!/usr/bin/env python3
"""Build a lip-sync-safe, episode-to-date post preview from approved media.

This is deliberately a review build. It never changes approved sources or writes
approval state. Picture and native audio remain paired throughout the conform.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "cb-output" / "review" / "episode_post_pass"
TMP = OUT / "_tmp"

SOURCES = {
    "s1a": (ROOT / "engine/media/shots/Ep1_S1.SH1A_import_20260811T075732_49a715c743.mp4", 4.0),
    "s1b": (ROOT / "engine/media/shots/Ep1_S1.SH1B_import_20260811T080746_3a4997c147.mp4", 4.0),
    "s1c": (ROOT / "engine/media/shots/Ep1_S1.SH1C_import_20260811T080824_bd67c41103.mp4", 2.0),
    "s1d": (ROOT / "engine/media/shots/Ep1_S1.SH2_c2.mp4", 3.0),
    "s2a": (ROOT / "engine/media/shots/Ep1_2.B1.S1_import_20260811T210039_ef0c243bc1.mp4", 14.0),
    "s2b": (ROOT / "engine/media/shots/Ep1_2.B2.S1_import_20260811T210127_73777ed51a.mp4", 14.0),
    "s2c": (ROOT / "engine/media/shots/Ep1_2.B3.S1_import_20260811T210127_9e0026f64f.mp4", 10.0),
    "s3": (ROOT / "cb-output/review/scene3_pace_pass/Ep1_scene3_sync_safe_cut_v6_no_nice_to_meet_you.mp4", 2.0),
}

TRIMS = {
    "s2a": (1.0, None),
    "s2c": (0.0, 8.0),
}


def run(args: list[str]) -> None:
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-2000:])


def duration(path: pathlib.Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nk=1:nw=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def conform(name: str, source: pathlib.Path, gain_db: float) -> pathlib.Path:
    target = TMP / f"{name}.mp4"
    start, end = TRIMS.get(name, (0.0, None))
    args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    if start:
        args.extend(["-ss", str(start)])
    args.extend(["-i", str(source)])
    if end is not None:
        args.extend(["-t", str(end - start)])
    args.extend([
        "-vf", "scale=854:480:flags=lanczos,fps=24,setsar=1,format=yuv420p",
        "-af", f"aresample=48000,aformat=channel_layouts=stereo,volume={gain_db}dB",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r", "24",
        "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-colorspace", "bt709", "-x264-params",
        "colorprim=bt709:transfer=bt709:colormatrix=bt709",
        "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "256k",
        "-movflags", "+faststart", str(target),
    ])
    run(args)
    return target


def concat_hard(inputs: list[pathlib.Path], target: pathlib.Path) -> None:
    args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for item in inputs:
        args.extend(["-i", str(item)])
    joins = "".join(f"[{i}:v][{i}:a]" for i in range(len(inputs)))
    args.extend([
        "-filter_complex", f"{joins}concat=n={len(inputs)}:v=1:a=1[v][a]",
        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
        "-crf", "18", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart",
        str(target),
    ])
    run(args)


def dissolve_three(inputs: list[pathlib.Path], target: pathlib.Path, fade: float) -> None:
    first, second, third = inputs
    d1, d2 = duration(first), duration(second)
    offset_1 = d1 - fade
    offset_2 = d1 + d2 - 2 * fade
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(first), "-i", str(second), "-i", str(third),
        "-filter_complex",
        (f"[0:v][1:v]xfade=transition=fade:duration={fade}:offset={offset_1}[v01];"
         f"[v01][2:v]xfade=transition=fade:duration={fade}:offset={offset_2}[v];"
         f"[0:a][1:a]acrossfade=d={fade}:c1=tri:c2=nofade[a01];"
         f"[a01][2:a]acrossfade=d={fade}:c1=tri:c2=nofade[a]"),
        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
        "-crf", "18", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart",
        str(target),
    ])


def assemble_episode(scenes: list[pathlib.Path], target: pathlib.Path, fade: float) -> None:
    first, second, third = scenes
    d1, d2 = duration(first), duration(second)
    offset_1 = d1 - fade
    offset_2 = d1 + d2 - 2 * fade
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(first), "-i", str(second), "-i", str(third),
        "-filter_complex",
        (f"[0:v][1:v]xfade=transition=fade:duration={fade}:offset={offset_1}[v01];"
         f"[v01][2:v]xfade=transition=fade:duration={fade}:offset={offset_2}[v];"
         f"[0:a][1:a]acrossfade=d={fade}:c1=tri:c2=nofade[a01];"
         f"[a01][2:a]acrossfade=d={fade}:c1=tri:c2=nofade[apre];"
         "[apre]highpass=f=30,loudnorm=I=-16:TP=-1.5:LRA=11:linear=true[a]"),
        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
        "-crf", "18", "-r", "24", "-pix_fmt", "yuv420p",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",
        "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "256k",
        "-movflags", "+faststart", str(target),
    ])


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    for source, _ in SOURCES.values():
        if not source.exists():
            raise FileNotFoundError(source)

    conformed = {
        name: conform(name, source, gain)
        for name, (source, gain) in SOURCES.items()
    }
    scene_1 = OUT / "Ep1_scene1_post_picture.mp4"
    scene_2 = OUT / "Ep1_scene2_post_picture.mp4"
    scene_3 = OUT / "Ep1_scene3_post_picture.mp4"
    concat_hard([
        conformed["s1a"], conformed["s1b"], conformed["s1c"], conformed["s1d"]
    ], scene_1)
    dissolve_three([conformed["s2a"], conformed["s2b"], conformed["s2c"]], scene_2, 0.65)
    scene_3.write_bytes(conformed["s3"].read_bytes())

    master = OUT / "Ep1_scenes1-3_full_post_review_v2_storm_tighter_aida.mp4"
    assemble_episode([scene_1, scene_2, scene_3], master, 0.5)
    manifest = {
        "status": "review-only-human-approval-required",
        "scope": "approved picture through Scene 3; Scene 4 has no approved WATCH render",
        "master": str(master),
        "durationSec": round(duration(master), 3),
        "masterSha256": sha256(master),
        "sources": [
            {"name": name, "path": str(source), "sha256": sha256(source), "gainDb": gain,
             "trim": TRIMS.get(name)}
            for name, (source, gain) in SOURCES.items()
        ],
        "policies": {
            "lipSync": "native picture and audio remain paired; no redub or time stretch",
            "scene1Joins": "hard cuts",
            "scene2Joins": "0.65 second dissolves for vision transitions",
            "betweenScenes": "0.5 second dissolves",
            "delivery": "854x480, 24fps, Rec.709, H.264/AAC 48kHz stereo",
            "loudness": "-16 LUFS target, -1.5 dBTP ceiling, LRA 11",
        },
    }
    (OUT / "Ep1_scenes1-3_full_post_review_v2_storm_tighter_aida.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print(master)
    return 0


if __name__ == "__main__":
    sys.exit(main())
