#!/usr/bin/env python3
"""Create a visual first/last-frame audit for approved episode shot boundaries."""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
from datetime import datetime, timezone

from PIL import Image, ImageDraw, ImageFont, ImageStat

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _extract_frame(video: pathlib.Path, output: pathlib.Path, *, last: bool) -> None:
    args = ["ffmpeg", "-y"]
    if last:
        args += ["-sseof", "-0.08"]
    else:
        args += ["-ss", "0"]
    args += ["-i", str(video), "-frames:v", "1", "-q:v", "2", str(output)]
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode or not output.is_file():
        raise RuntimeError(f"could not extract {'last' if last else 'first'} frame from {video}: "
                           f"{result.stderr[-500:]}")


def _difference(left: Image.Image, right: Image.Image) -> float:
    left = left.convert("RGB").resize((320, 180))
    right = right.convert("RGB").resize((320, 180))
    diff = ImageStat.Stat(Image.eval(Image.blend(left, right, 0.5), lambda value: value))
    # Mean RGB delta is more useful here than a perceptual score: it tells the
    # editor how visibly different the two boundary compositions are.
    pixels_left = list(left.getdata())
    pixels_right = list(right.getdata())
    total = sum(abs(a - b) for p, q in zip(pixels_left, pixels_right) for a, b in zip(p, q))
    return total / (len(pixels_left) * 3 * 255)


def _sheet(rows: list[dict], output: pathlib.Path) -> None:
    thumb_w, thumb_h, label_h = 480, 270, 58
    cols = 2
    cell_w, cell_h = thumb_w * 2, thumb_h + label_h
    sheet = Image.new("RGB", (cell_w * cols, cell_h * ((len(rows) + cols - 1) // cols)), "#171717")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 22)
        small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 17)
    except OSError:
        font = small = ImageFont.load_default()
    for index, row in enumerate(rows):
        x = (index % cols) * cell_w
        y = (index // cols) * cell_h
        left = Image.open(row["lastFrame"]).convert("RGB").resize((thumb_w, thumb_h))
        right = Image.open(row["firstFrame"]).convert("RGB").resize((thumb_w, thumb_h))
        sheet.paste(left, (x, y))
        sheet.paste(right, (x + thumb_w, y))
        draw.rectangle((x, y + thumb_h, x + cell_w, y + cell_h), fill="#242424")
        mode = row["recommendation"]
        draw.text((x + 8, y + thumb_h + 5),
                  f"{row['from']} -> {row['to']}   {mode}", fill="white", font=font)
        draw.text((x + 8, y + thumb_h + 32),
                  f"left last frame | right first frame | diff {row['difference']:.3f}",
                  fill="#cfcfcf", font=small)
    sheet.save(output, quality=92)


def _load_shots(input_root: pathlib.Path, episode: str) -> tuple[pathlib.Path, list[dict]]:
    manifest_path = input_root / "episode.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return manifest_path, manifest.get("shots") or []

    # Episode 1 predates the post95 episode manifest. Its approved assembly
    # manifest is still authoritative and points directly at canonical renders.
    legacy = sorted(input_root.glob(f"{episode}_assembly_review*_manifest.json"))
    if not legacy:
        raise RuntimeError(f"post input manifest is missing: {manifest_path}")
    legacy_path = legacy[-1]
    manifest = json.loads(legacy_path.read_text(encoding="utf-8"))
    shots = [
        {"id": item["shotId"], "scene": item["scene"], "render": item["sourcePath"]}
        for item in manifest.get("timeline", [])
    ]
    return legacy_path, shots


def _clip_path(input_root: pathlib.Path, render: str) -> pathlib.Path:
    path = pathlib.Path(render)
    if path.is_absolute() and path.is_file():
        return path
    if path.is_absolute():
        for root in (ROOT / "engine" / "media" / "shots", ROOT / "engine" / "media"):
            candidate = root / path.name
            if candidate.is_file():
                return candidate
    return input_root / path


def audit(episode: str = "Ep2") -> pathlib.Path:
    input_root = ROOT / "engine" / "media" / "post95" / f"{episode}_episode"
    manifest_path, shots = _load_shots(input_root, episode)
    if len(shots) < 2:
        raise RuntimeError("at least two approved shots are required")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = input_root / f"boundary_audit_{stamp}"
    output.mkdir(parents=True, exist_ok=False)
    frames = {}
    for shot in shots:
        video = _clip_path(input_root, shot["render"])
        first = output / f"{shot['id']}_first.jpg"
        last = output / f"{shot['id']}_last.jpg"
        _extract_frame(video, first, last=False)
        _extract_frame(video, last, last=True)
        frames[shot["id"]] = (first, last)

    rows = []
    for previous, current in zip(shots, shots[1:]):
        previous_last = frames[previous["id"]][1]
        current_first = frames[current["id"]][0]
        score = _difference(Image.open(previous_last), Image.open(current_first))
        same_scene = previous["scene"] == current["scene"]
        if score < 0.12:
            recommendation = "MATCH / CUT"
        elif not same_scene and score < 0.28:
            recommendation = "DISSOLVE OK"
        else:
            recommendation = "REVIEW / RE-ANCHOR"
        rows.append({
            "from": previous["id"], "to": current["id"],
            "sameScene": same_scene, "difference": round(score, 6),
            "recommendation": recommendation,
            "lastFrame": str(previous_last), "firstFrame": str(current_first),
        })
    report = {
        "episode": episode,
        "manifest": str(manifest_path),
        "method": "last frame versus next first frame; visual review required",
        "boundaries": rows,
        "summary": {
            "total": len(rows),
            "matchCut": sum(r["recommendation"] == "MATCH / CUT" for r in rows),
            "dissolveOk": sum(r["recommendation"] == "DISSOLVE OK" for r in rows),
            "reviewOrReanchor": sum(r["recommendation"] == "REVIEW / RE-ANCHOR" for r in rows),
        },
    }
    (output / "boundary_audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    _sheet(rows, output / "boundary_review_sheet.jpg")
    print(json.dumps(report, indent=2))
    print(f"REVIEW_SHEET {output / 'boundary_review_sheet.jpg'}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", default="Ep2")
    args = parser.parse_args()
    audit(args.episode)
