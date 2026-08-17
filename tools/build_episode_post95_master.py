#!/usr/bin/env python3
"""Build the Scenes 1-3 95% post review master and editable audio stems.

Approved picture, dialogue and native effects remain untouched. Scene-level score
and ambience are assembled continuously, ducked beneath the native soundtrack, and
mastered once across the full programme.
"""

from __future__ import annotations

import hashlib
import argparse
import json
import pathlib
import re
import shutil
import subprocess


ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "cb-output/review/episode_post_pass/Ep1_scenes1-3_full_post_review_v2_storm_tighter_aida.mp4"
ASSETS = ROOT / "engine/media/post95"
OUT = ROOT / "engine/media/post95/Ep1_episode"

SCENES = [
    {
        "name": "scene1",
        "duration": 44.288,
        "music": ASSETS / "Ep1_Scene1_score_post95.mp3",
        "ambience": ASSETS / "Ep1_Scene1_ambience_post95.mp3",
    },
    {
        "name": "scene2",
        "duration": 23.791667,
        "music": ASSETS / "Ep1_Scene2_score_post95.mp3",
        "ambience": ASSETS / "Ep1_Scene2_ambience_post95.mp3",
    },
    {
        "name": "scene3",
        "duration": 102.333333,
        "music": ASSETS / "Ep1_Scene3_score_post95.mp3",
        "ambience": ASSETS / "Ep1_Scene3_ambience_post95.mp3",
    },
]

FADE = 0.5
TARGET_I = -14.0
# Leave codec headroom so the delivered AAC remains at or below -1 dBTP.
TARGET_TP = -1.5
TARGET_LRA = 11.0


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:])
    return result


def duration(path: pathlib.Path) -> float:
    result = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nk=1:nw=1", str(path),
    ])
    return float(result.stdout.strip())


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_scene_stem(kind: str, target: pathlib.Path, programme_duration: float) -> None:
    inputs: list[str] = []
    filters: list[str] = []
    for index, scene in enumerate(SCENES):
        path = scene[kind]
        inputs.extend(["-i", str(path)])
        scene_duration = scene["duration"]
        if kind == "music":
            treatment = ""
            if index == 0:
                treatment += "afade=t=in:st=0:d=1.2,"
            if index == len(SCENES) - 1:
                treatment += f"afade=t=out:st={scene_duration - 1.5:.6f}:d=1.5,"
            filters.append(
                f"[{index}:a]aresample=48000,aformat=channel_layouts=stereo,"
                f"apad=pad_dur={scene_duration:.6f},atrim=0:{scene_duration:.6f},"
                f"{treatment}asetpts=PTS-STARTPTS[{kind}{index}]"
            )
        else:
            filters.append(
                f"[{index}:a]aresample=48000,aformat=channel_layouts=stereo,"
                f"aloop=loop=-1:size=960000,atrim=0:{scene_duration:.6f},"
                f"asetpts=PTS-STARTPTS[{kind}{index}]"
            )
    filters.append(
        f"[{kind}0][{kind}1]acrossfade=d={FADE}:c1=tri:c2=tri[{kind}01]"
    )
    filters.append(
        f"[{kind}01][{kind}2]acrossfade=d={FADE}:c1=tri:c2=tri,"
        f"apad=pad_dur=1,atrim=0:{programme_duration:.6f}[out]"
    )
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        *inputs, "-filter_complex", ";".join(filters), "-map", "[out]",
        "-c:a", "pcm_s24le", "-ar", "48000", "-ac", "2", str(target),
    ])


def base_mix_filter(music_gain: float, ambience_gain: float) -> str:
    return ";".join([
        "[0:a]aresample=48000,aformat=channel_layouts=stereo,asplit=2[native][detector]",
        f"[1:a]volume={music_gain:.6f}[music]",
        f"[2:a]volume={ambience_gain:.6f}[ambience]",
        "[music][ambience]amix=inputs=2:duration=shortest:normalize=0[bed]",
        "[bed][detector]sidechaincompress=threshold=0.025:ratio=10:attack=10:release=500[ducked]",
        "[native][ducked]amix=inputs=2:duration=first:normalize=0,highpass=f=30,"
        "acompressor=threshold=-18dB:ratio=1.5:attack=20:release=250[pre]",
    ])


def measure_mix(music: pathlib.Path, ambience: pathlib.Path, music_gain: float,
                ambience_gain: float, target_i: float) -> dict[str, float]:
    result = run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(SOURCE),
        "-i", str(music), "-i", str(ambience), "-filter_complex",
        base_mix_filter(music_gain, ambience_gain) +
        f";[pre]loudnorm=I={target_i}:TP={TARGET_TP}:LRA={TARGET_LRA}:"
        "print_format=json[measure]",
        "-map", "[measure]", "-f", "null", "-",
    ])
    matches = re.findall(r"\{\s*\"input_i\".*?\}", result.stderr, re.S)
    if not matches:
        raise RuntimeError("loudness measurement did not return JSON")
    raw = json.loads(matches[-1])
    numeric_keys = {
        "input_i", "input_tp", "input_lra", "input_thresh",
        "output_i", "output_tp", "output_lra", "output_thresh", "target_offset",
    }
    return {key: float(value) for key, value in raw.items() if key in numeric_keys}


def build_master(music: pathlib.Path, ambience: pathlib.Path, target: pathlib.Path,
                 measured: dict[str, float], music_gain: float,
                 ambience_gain: float, target_i: float) -> None:
    normalize = (
        f"[pre]loudnorm=I={target_i}:TP={TARGET_TP}:LRA={TARGET_LRA}:"
        f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
        f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
        f"offset={measured['target_offset']}:linear=true,"
        "alimiter=limit=0.891251:level=false[aout]"
    )
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(SOURCE), "-i", str(music), "-i", str(ambience),
        "-filter_complex", base_mix_filter(music_gain, ambience_gain) + ";" + normalize,
        "-map", "0:v:0", "-map", "[aout]", "-c:v", "copy",
        "-color_primaries", "bt709", "-color_trc", "bt709",
        "-colorspace", "bt709", "-c:a", "aac", "-ar", "48000", "-ac", "2",
        "-b:a", "320k", "-movflags", "+faststart", str(target),
    ])


def extract_audio(source: pathlib.Path, target: pathlib.Path) -> None:
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-map", "0:a:0", "-c:a", "pcm_s24le", "-ar", "48000", "-ac", "2", str(target),
    ])


def stream_hash(path: pathlib.Path) -> str:
    result = run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
        "-map", "0:v:0", "-c:v", "copy", "-f", "hash", "-hash", "sha256", "-",
    ])
    return result.stdout.strip().split("=", 1)[-1].lower()


def final_qc(source: pathlib.Path, master: pathlib.Path, target_i: float) -> dict[str, object]:
    loudness = run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(master), "-map", "0:a:0",
        "-af", f"loudnorm=I={target_i}:TP=-1:LRA={TARGET_LRA}:print_format=json",
        "-f", "null", "-",
    ])
    matches = re.findall(r"\{\s*\"input_i\".*?\}", loudness.stderr, re.S)
    if not matches:
        raise RuntimeError("final loudness QC did not return JSON")
    report = json.loads(matches[-1])
    integrated = float(report["input_i"])
    true_peak = float(report["input_tp"])

    black = run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(master),
        "-vf", "blackdetect=d=0.20:pix_th=0.10", "-an", "-f", "null", "-",
    ])
    black_frames = len(re.findall(r"black_start:", black.stderr))
    run(["ffmpeg", "-v", "error", "-i", str(master), "-f", "null", "-"])
    source_video_hash = stream_hash(source)
    master_video_hash = stream_hash(master)
    picture_locked = source_video_hash == master_video_hash
    passed = (
        abs(integrated - target_i) <= 0.5 and true_peak <= -1.0 and
        black_frames == 0 and picture_locked
    )
    return {
        "passed": passed,
        "integratedLufs": integrated,
        "truePeakDbtp": true_peak,
        "blackFrameEvents": black_frames,
        "decodePassed": True,
        "pictureLocked": picture_locked,
        "sourceVideoSha256": source_video_hash,
        "masterVideoSha256": master_video_hash,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--music-gain", type=float, default=0.18)
    parser.add_argument("--ambience-gain", type=float, default=0.04)
    parser.add_argument("--target-lufs", type=float, default=TARGET_I)
    args = parser.parse_args()
    if not 0.0 <= args.music_gain <= 1.0 or not 0.0 <= args.ambience_gain <= 1.0:
        parser.error("music and ambience gains must be between 0 and 1")
    if not -24.0 <= args.target_lufs <= -9.0:
        parser.error("target LUFS must be between -24 and -9")
    OUT.mkdir(parents=True, exist_ok=True)
    staging = OUT / ".building"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    required = [SOURCE] + [scene[key] for scene in SCENES for key in ("music", "ambience")]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing post input(s): " + ", ".join(missing))

    programme_duration = duration(SOURCE)
    filenames = {
        "native": "Ep1_scenes1-3_native_dialogue_sfx_24bit.wav",
        "picture": "Ep1_scenes1-3_picture_native_audio.mp4",
        "music": "Ep1_scenes1-3_music_post95_24bit.wav",
        "ambience": "Ep1_scenes1-3_ambience_post95_24bit.wav",
        "master": "Ep1_scenes1-3_POST95_review_master.mp4",
        "finalMix": "Ep1_scenes1-3_POST95_final_mix_24bit.wav",
    }
    native = staging / filenames["native"]
    picture_original = staging / filenames["picture"]
    music = staging / filenames["music"]
    ambience = staging / filenames["ambience"]
    master = staging / filenames["master"]
    final_mix = staging / filenames["finalMix"]

    shutil.copy2(SOURCE, picture_original)
    extract_audio(SOURCE, native)
    build_scene_stem("music", music, programme_duration)
    build_scene_stem("ambience", ambience, programme_duration)
    measured = measure_mix(music, ambience, args.music_gain, args.ambience_gain,
                           args.target_lufs)
    build_master(music, ambience, master, measured, args.music_gain,
                 args.ambience_gain, args.target_lufs)
    extract_audio(master, final_mix)
    qc = final_qc(SOURCE, master, args.target_lufs)

    manifest = {
        "status": "95-percent-review-human-signoff-required",
        "scope": "approved Scenes 1-3 picture and native lip-synced dialogue",
        "source": str(SOURCE),
        "sourceSha256": sha256(SOURCE),
        "durationSec": round(duration(master), 3),
        "outputs": {
            "master": str(OUT / filenames["master"]),
            "pictureOriginal": str(OUT / filenames["picture"]),
            "nativeDialogueAndSfxStem": str(OUT / filenames["native"]),
            "musicStem": str(OUT / filenames["music"]),
            "ambienceStem": str(OUT / filenames["ambience"]),
            "finalMixStem": str(OUT / filenames["finalMix"]),
        },
        "mixPolicy": {
            "nativeDialogue": "preserved; never stripped, regenerated, shifted or time-stretched",
            "music": "one generated instrumental cue per scene, crossfaded at scene transitions",
            "ambience": "one subtle continuous bed per scene, crossfaded at scene transitions",
            "ducking": "score and ambience sidechain-duck beneath the native soundtrack",
            "musicLinearGain": args.music_gain,
            "ambienceLinearGain": args.ambience_gain,
            "targetIntegratedLufs": args.target_lufs,
            "targetTruePeakDbtp": TARGET_TP,
            "targetLraLu": TARGET_LRA,
            "remainingFivePercent": "human taste review and any frame-specific SFX nudges",
        },
        "preNormalizationMeasurement": measured,
        "finalQc": qc,
        "assets": [
            {
                "scene": scene["name"],
                "music": str(scene["music"]),
                "musicSha256": sha256(scene["music"]),
                "ambience": str(scene["ambience"]),
                "ambienceSha256": sha256(scene["ambience"]),
            }
            for scene in SCENES
        ],
    }
    manifest["masterSha256"] = sha256(master)
    for filename in filenames.values():
        (staging / filename).replace(OUT / filename)
    manifest_tmp = OUT / ".Ep1_scenes1-3_POST95_manifest.json.tmp"
    manifest_tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest_tmp.replace(OUT / "Ep1_scenes1-3_POST95_manifest.json")
    staging.rmdir()
    print(OUT / filenames["master"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
