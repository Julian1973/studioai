"""The episode master - five approved scene masters into one delivered episode (2026-09-03).

Before this module existed the studio's "FULL EPISODE ASSEMBLY" band launched
tools/build_episode_post95_master.py, which imported a module that did not exist: no scene
master could ever become an episode. The contract is deliberately small and transactional:

  * every scene with a production package must have a CURRENT, human-approved post master
    (cb_render.post_status(...)["approved"]) - a missing or stale one is refused BY NAME;
  * the scene masters are hard-cut in scene order with cb_post.assemble_picture (each scene
    master already carries its own conformed picture, mix, loudness and captions);
  * the result lands under <media>/post95/<episode>_episode/ with a manifest whose shape is what
    cb_post_workspace.workspace() reads (outputs.master, masterSha256, durationSec, scope,
    shotCount, assets[]) - the human verdict stays in the post workspace, never here.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
import subprocess

import paths as P
import cb_post
import cb_post_workspace
import cb_render

ROOT = pathlib.Path(P.ROOT) if hasattr(P, "ROOT") else pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / P.OUTPUT_REL


class EpisodePostRefused(RuntimeError):
    """A named refusal: which scene is missing its approved master and what to do."""


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _scene_packages(episode):
    rows = []
    for path in sorted(OUT.glob(f"{episode}_scene*_production_package.json")):
        pkg = json.loads(path.read_text(encoding="utf-8"))
        try:
            scene = int(str(pkg.get("sceneNumber") or "").strip())
        except ValueError:
            continue
        rows.append((scene, pkg, path))
    return sorted(rows, key=lambda row: row[0])


def approved_scene_masters(episode="Ep1"):
    """[{scene, path, sha256, manifestPath, durationSec}] for every scene, or a refusal naming the
    first scene whose master is missing or stale."""
    rows = _scene_packages(episode)
    if not rows:
        raise EpisodePostRefused(f"REFUSED — {episode} has no production package for any scene")
    masters = []
    for scene, pkg, _ in rows:
        status = cb_render.post_status(pkg, str(scene), episode)
        approved = status.get("approved") or {}
        manifest = approved.get("manifest") or {}
        master = ((manifest.get("outputs") or {}).get("master16x9") or {}).get("path")
        if not approved.get("exists") or not master:
            raise EpisodePostRefused(
                f"REFUSED — scene {scene} has no approved scene master yet; build and accept its "
                "master in the post stage first")
        if not approved.get("current"):
            raise EpisodePostRefused(
                f"REFUSED — scene {scene}'s approved master is stale ({approved.get('reason')}); "
                "rebuild and re-accept it before the episode master")
        if not pathlib.Path(master).is_file():
            raise EpisodePostRefused(
                f"REFUSED — scene {scene}'s approved master file is missing on disk: {master}")
        masters.append({
            "scene": scene, "path": master, "sha256": _sha256(master),
            "manifestDigest": hashlib.sha256(
                json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            "durationSec": ((manifest.get("outputs") or {}).get("master16x9") or {})
                           .get("media", {}).get("durationSec"),
            "shotCount": manifest.get("shotCount"),
        })
    return masters


def build_episode_assembly(episode="Ep1", reviewed_by=None):
    """Concatenate every approved scene master in scene order into one episode master and
    write the manifest the post workspace reviews. Zero provider spend."""
    masters = approved_scene_masters(episode)
    folder = cb_post_workspace.POST_ROOT / f"{episode}_episode"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    assembly_id = hashlib.sha256(
        "".join(m["sha256"] for m in masters).encode()).hexdigest()[:12]
    out = folder / f"{episode}_master_16x9_{assembly_id}.mp4"
    if not out.exists():
        duration = cb_post.assemble_picture([m["path"] for m in masters], str(out))
        if not duration or not out.exists():
            raise EpisodePostRefused("REFUSED — episode assembly failed (ffmpeg concat); see the job log")
    else:
        duration = cb_post._dur(str(out))
    manifest = {
        "schemaVersion": 1,
        "episode": episode,
        "id": assembly_id,
        "builtAt": stamp,
        "scope": "episode",
        "stage": "post-review-human-signoff-required",
        "sceneCount": len(masters),
        "shotCount": sum(int(m.get("shotCount") or 0) for m in masters),
        "durationSec": duration,
        "inputs": masters,
        "outputs": {"master": str(out), "master16x9": {"path": str(out), "sha256": _sha256(out)}},
        "masterSha256": _sha256(out),
        "assets": [{"label": f"Scene {m['scene']} master", "path": m["path"], "sha256": m["sha256"]}
                   for m in masters],
        "note": ("Hard-cut assembly of the approved scene masters in scene order. Each scene master "
                 "already carries its own mix, loudness and captions; the human final verdict is "
                 "recorded in the post workspace."),
    }
    manifest_path = folder / f"{assembly_id}_manifest.json"
    tmp = manifest_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(manifest_path)
    print(f"EPISODE MASTER — {episode}: {len(masters)} scene masters -> {out} ({duration}s)", flush=True)
    return {"ok": True, "master": str(out), "manifest": str(manifest_path),
            "sceneCount": len(masters), "durationSec": duration}
