import hashlib
import json

import cb_post_workspace as post


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_workspace_projects_only_browser_served_media_and_hash_bound_verdict(tmp_path, monkeypatch):
    media = tmp_path / "engine" / "media"
    folder = media / "post95" / "Ep1_episode"
    state = tmp_path / "state"
    folder.mkdir(parents=True)
    master = folder / "master.mp4"
    original = folder / "native.mp4"
    stem = folder / "music.wav"
    for path, content in ((master, b"master"), (original, b"native"), (stem, b"music")):
        path.write_bytes(content)
    (folder / "review_manifest.json").write_text(json.dumps({
        "masterSha256": _hash(master),
        "stage": "assembly-review-human-signoff-required",
        "durationSec": 12.5,
        "outputs": {"master": str(master), "pictureOriginal": str(original), "musicStem": str(stem)},
        "finalQc": {"passed": True, "pictureLocked": True},
    }), encoding="utf-8")
    monkeypatch.setattr(post, "MEDIA_ROOT", media)
    monkeypatch.setattr(post, "POST_ROOT", media / "post95")
    monkeypatch.setattr(post, "STATE_ROOT", state)

    projected = post.workspace("Ep1")
    assert projected["masterUrl"] == "/engine/media/post95/Ep1_episode/master.mp4"
    assert projected["originalUrl"] == "/engine/media/post95/Ep1_episode/native.mp4"
    assert projected["stage"] == "assembly-review-human-signoff-required"
    assert projected["verdict"] is None

    approved = post.record_verdict("Ep1", "approved")
    assert approved["verdict"]["reviewer"] == "Julian"
    assert approved["verdict"]["stage"] == "assembly-review-human-signoff-required"
    history = (state / "Ep1_post_review_history.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(history) == 1
    assert json.loads(history[0])["masterSha256"] == _hash(master)
    master.write_bytes(b"changed")
    try:
        post.workspace("Ep1")
    except post.PostWorkspaceError as error:
        assert "manifest hash" in str(error)
    else:
        raise AssertionError("a changed master must invalidate the workspace")


def test_rejection_requires_a_note(tmp_path, monkeypatch):
    media = tmp_path / "media"
    folder = media / "post95" / "Ep1_episode"
    folder.mkdir(parents=True)
    master = folder / "master.mp4"
    master.write_bytes(b"master")
    (folder / "review_manifest.json").write_text(json.dumps({
        "masterSha256": _hash(master), "outputs": {"master": str(master)}
    }), encoding="utf-8")
    monkeypatch.setattr(post, "MEDIA_ROOT", media)
    monkeypatch.setattr(post, "POST_ROOT", media / "post95")
    monkeypatch.setattr(post, "STATE_ROOT", tmp_path / "state")
    try:
        post.record_verdict("Ep1", "rejected")
    except post.PostWorkspaceError as error:
        assert "notes are required" in str(error)
    else:
        raise AssertionError("a rejection without notes must fail")
