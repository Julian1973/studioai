#!/usr/bin/env python3
"""Project approved Crystal Bears shots into the post department's input manifest.

This is deliberately read-only with respect to Studio production records.  It copies
approved media into a post workspace and writes a manifest that the post department can
consume without guessing from filenames or accidentally selecting archived candidates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import re
from datetime import datetime, timezone


ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "cb-output"
MEDIA_DIR = ROOT / "engine" / "media"


class ExportError(RuntimeError):
    pass


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path(value: str | None) -> pathlib.Path | None:
    if not value:
        return None
    path = pathlib.Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def _shot_map(package: dict) -> dict[str, dict]:
    return {str(shot.get("shotId")): shot for shot in package.get("shots") or []}


def _approved_shots(episode: str, scene_numbers: list[int]) -> list[dict]:
    result = []
    for scene_number in scene_numbers:
        package_path = PACKAGE_DIR / f"{episode}_scene{scene_number}_production_package.json"
        if not package_path.is_file():
            raise ExportError(f"missing production package: {package_path}")
        package = json.loads(package_path.read_text(encoding="utf-8"))
        shot_details = _shot_map(package)
        for ledger in package.get("continuityLedger") or []:
            shot_id = str(ledger.get("shotId") or "")
            if ledger.get("status") != "approved":
                continue
            take = _path(ledger.get("approvedTake"))
            if not take or not take.is_file():
                raise ExportError(f"approved take is missing for {shot_id}: {take}")
            frame = _path(ledger.get("harvestFrame"))
            if frame and not frame.is_file():
                raise ExportError(f"harvested frame is missing for {shot_id}: {frame}")
            voice_approval = ledger.get("voiceApproval") or {}
            voice = _path(voice_approval.get("path"))
            shot = shot_details.get(shot_id) or {}
            take_hash = sha256(take)
            recorded_hash = (ledger.get('approval') or {}).get('contentHash')
            if recorded_hash and recorded_hash != take_hash:
                raise ExportError(f'approved take changed after approval: {shot_id}')
            item = {
                "sceneNumber": scene_number,
                "shotId": shot_id,
                "status": "approved",
                "approvedTake": str(take),
                "approvedTakeSha256": take_hash,
                "directionContext": shot,
                "directionEvidence": "current authored context at post export; not proof of the historical provider request",
                "approvalReceipt": ledger.get('approval') or {},
                "sourcePackage": str(package_path),
                "sourcePackageSha256": sha256(package_path),
                "harvestFrame": str(frame) if frame else None,
                "harvestFrameSha256": sha256(frame) if frame else None,
                "dialogueLines": shot.get("dialogueLines") or [],
                "approvedVoice": str(voice) if voice else None,
                "approvedVoiceSha256": sha256(voice) if voice and voice.is_file() else None,
                "audioProvenance": ledger.get("audioProvenance") or {},
                "continuityMode": ledger.get("continuityMode") or ledger.get("sourceType"),
            }
            result.append(item)
    result.sort(key=lambda item: (item["sceneNumber"], [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', item["shotId"])]))
    return result


def export_episode(episode: str = "Ep2", output: pathlib.Path | None = None) -> pathlib.Path:
    output = output or MEDIA_DIR / "post95" / f"{episode}_episode"
    scenes = sorted(
        int(path.stem.split("_scene", 1)[1].split("_", 1)[0])
        for path in PACKAGE_DIR.glob(f"{episode}_scene*_production_package.json")
    )
    if not scenes:
        raise ExportError(f"no production packages found for {episode}")
    shots = _approved_shots(episode, scenes)
    if not shots:
        raise ExportError(f"no approved shots found for {episode}")

    renders = output / "renders"
    voices = output / "voice"
    plates = output / "plates"
    for folder in (renders, voices, plates):
        folder.mkdir(parents=True, exist_ok=True)

    manifest_shots = []
    for item in shots:
        shot_id = item["shotId"].replace(".", "_")
        render_target = renders / f"{shot_id}.mp4"
        shutil.copy2(item["approvedTake"], render_target)
        voice_target = None
        if item["approvedVoice"]:
            voice_target = voices / f"{shot_id}.wav"
            shutil.copy2(item["approvedVoice"], voice_target)
        if item["harvestFrame"]:
            shutil.copy2(item["harvestFrame"], plates / f"{shot_id}_final_frame.png")
        manifest_shots.append({
            "id": item["shotId"],
            "scene": item["sceneNumber"],
            "render": f"renders/{render_target.name}",
            "voice": f"voice/{voice_target.name}" if voice_target else None,
            "plate": f"plates/{shot_id}_final_frame.png" if item["harvestFrame"] else None,
            "approvedTakeSha256": item["approvedTakeSha256"],
            "directionContext": item["directionContext"],
            "directionEvidence": item["directionEvidence"],
            "approvalReceipt": item["approvalReceipt"],
            "sourcePackage": item["sourcePackage"],
            "sourcePackageSha256": item["sourcePackageSha256"],
            "dialogueLines": item["dialogueLines"],
            "continuityMode": item["continuityMode"],
        })

    manifest = {
        "schemaVersion": "crystal-bears-post-inputs-v1",
        "episode": episode,
        "title": f"Crystal Bears {episode}",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "Studio approved continuity ledgers",
        "approvalRule": "Only continuityLedger entries with status=approved are exported; pending, rejected and superseded entries are excluded.",
        "format": {"fps": 24, "width": 1920, "height": 1080},
        "audio": {"targetLufs": -14, "truePeakDbtp": -1, "sampleRate": 48000, "channels": 2},
        "scenes": scenes,
        "shots": manifest_shots,
    }
    manifest_path = output / "episode.json"
    temporary = manifest_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(manifest_path)
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", default="Ep2")
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    try:
        path = export_episode(args.episode, args.output)
    except ExportError as error:
        parser.error(str(error))
    print(f"EXPORTED {args.episode}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
