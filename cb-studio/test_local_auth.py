import http.client
import base64
import hashlib
import importlib.util
import json
import pathlib
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
ENGINE = ROOT / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import cb_lineage
import cb_intake


def _load_server_module(name="cb_studio_serve_auth_test"):
    spec = importlib.util.spec_from_file_location(name, HERE / "serve.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_episode_script_registry_sync_publishes_and_verifies_exact_pointer(monkeypatch):
    module = _load_server_module("cb_studio_registry_sync_test")
    expected = "sha256:" + "c" * 64
    calls = []

    def fake_reindex():
        calls.append("reindex")
        return [{"number": 2, "scriptVersionId": expected}]

    monkeypatch.setattr(module, "reindex_episodes", fake_reindex)
    record = module.synchronize_episode_script_registry("Ep2", expected)

    assert calls == ["reindex"]
    assert record["scriptVersionId"] == expected


def test_episode_script_registry_sync_refuses_unpublished_pointer(monkeypatch):
    module = _load_server_module("cb_studio_registry_sync_refusal_test")
    expected = "sha256:" + "c" * 64
    monkeypatch.setattr(
        module,
        "reindex_episodes",
        lambda: [{"number": 2, "scriptVersionId": "sha256:" + "a" * 64}],
    )

    with pytest.raises(RuntimeError, match="episode registry synchronization failed"):
        module.synchronize_episode_script_registry("Ep2", expected)


def test_render_upload_decoder_accepts_bounded_mp4_and_webm_only():
    module = _load_server_module("cb_studio_render_decode_test")
    mp4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 24
    webm = b"\x1aE\xdf\xa3" + b"\x00" * 24
    assert module.decode_video_upload(base64.b64encode(mp4).decode())[1] == ".mp4"
    assert module.decode_video_upload(base64.b64encode(webm).decode())[1] == ".webm"
    with pytest.raises(ValueError, match="only readable MP4 and WebM"):
        module.decode_video_upload(base64.b64encode(b"not-video").decode())


def test_canonical_engine_module_reloads_changed_source(monkeypatch, tmp_path):
    module = _load_server_module("cb_studio_live_module_test")
    module_name = "studio_live_engine_fixture"
    source = tmp_path / f"{module_name}.py"
    source.write_text("VALUE = 'first'\n")
    monkeypatch.setattr(module, "CBGEN", tmp_path)
    sys.modules.pop(module_name, None)
    try:
        first = module._canonical_engine_module(module_name)
        assert first.VALUE == "first"

        time.sleep(0.01)
        source.write_text("VALUE = 'second-version'\n")
        second = module._canonical_engine_module(module_name)

        assert second is first
        assert second.VALUE == "second-version"
    finally:
        sys.modules.pop(module_name, None)


@pytest.mark.parametrize("planned_cut", [False, True])
def test_relay_opening_frame_is_not_exposed_as_watch_result(monkeypatch, tmp_path, planned_cut):
    module = _load_server_module("cb_studio_relay_media_test")
    media = tmp_path / "media"
    shots = media / "shots"
    shots.mkdir(parents=True)
    (shots / "EpT_S1.SH1_final_frame.png").write_bytes(b"previous-final-frame")
    monkeypatch.setattr(module, "MEDIA", media)
    monkeypatch.setattr(
        module.cb_asset_registry,
        "shot_media_from_registry",
        lambda *args: {"S1.SH2": {"keyframe": "/engine/media/shots/stale-copy.png"}},
    )

    class Renderer:
        @staticmethod
        def timing_slate_status(*_args):
            return {"current": False, "approved": False, "reason": "missing"}

        @staticmethod
        def lineage_status(*_args):
            return {"current": True, "reasonCodes": []}

        @staticmethod
        def post_status(*_args):
            return {"candidate": {"exists": False}, "approved": {"exists": False}}

    monkeypatch.setattr(module, "_canonical_cb_render", lambda: Renderer)
    package = {
        "creativeDirectingStandardVersion": 4,
        "shots": [{"shotId": "S1.SH2", "sourceType": "relay", "sourceShotId": "S1.SH1"}],
        "continuityLedger": [{"shotId": "S1.SH2", "status": "designed"}],
    }

    if planned_cut:
        monkeypatch.setattr(module, "_url_from_abs", lambda path: "/engine/media/shots/" + pathlib.Path(path).name if path and pathlib.Path(path).is_file() else None)
        package["shots"][0].update({"sourceType": "opener", "sourceShotId": None,
            "shotTransition": {"type": "cut", "stateSourceShotId": "S1.SH1"}})
        package["continuityLedger"].append({"shotId": "S1.SH1", "status": "approved",
            "harvestFrame": str(shots / "EpT_S1.SH1_final_frame.png")})
    result = module.shot_media_map(package, "1", "EpT")["shots"]["S1.SH2"]
    if planned_cut:
        assert result["handoffFrame"].endswith("EpT_S1.SH1_final_frame.png")
        assert result["handoffSourceShotId"] == "S1.SH1"
        assert result["openingFrame"] is None
        assert result["finalFrame"] is None
        assert result["clip"] is None
        return

    assert result["openingFrame"].endswith("EpT_S1.SH1_final_frame.png")
    assert result["openingFrameSourceShotId"] == "S1.SH1"
    assert result["keyframe"] == result["openingFrame"]
    assert result["finalFrame"] is None
    assert result["clip"] is None


@pytest.fixture()
def studio(monkeypatch):
    module = _load_server_module()
    monkeypatch.chdir(ROOT)
    server = module.http.server.ThreadingHTTPServer(("127.0.0.1", 0), module.H)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield module, server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def _request(port, method, path, headers=None, body=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    request_headers = {"Host": f"127.0.0.1:{port}", **(headers or {})}
    connection.request(method, path, body=body, headers=request_headers)
    response = connection.getresponse()
    payload = response.read()
    result = response.status, dict(response.getheaders()), payload
    connection.close()
    return result


def test_accept_direction_queues_all_eight_scene_compilers_without_provider_calls(monkeypatch,
                                                                                   tmp_path):
    module = _load_server_module("cb_studio_accept_direction_queue_test")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(cb_intake, "scene_roster", lambda episode: {
        "scenes": [{"sceneNumber": number} for number in range(1, 9)]})
    calls = []
    monkeypatch.setattr(module, "_start", lambda job_id, gate, scene, args: (
        calls.append((gate, scene, args)) or job_id))

    jobs = module._queue_episode_storyboards("Ep2")

    assert len(jobs) == 8
    assert [scene for _gate, scene, _args in calls] == [str(n) for n in range(1, 9)]
    assert all(gate == "creative:scene" for gate, _scene, _args in calls)
    assert all(args == ["cb_creative.py", "scene", scene, "Ep2"]
               for _gate, scene, args in calls)
    assert not any("seedream" in " ".join(args).lower() or
                   "eleven" in " ".join(args).lower() or
                   "seedance" in " ".join(args).lower()
                   for _gate, _scene, args in calls)


def test_episode_retry_skips_completed_scene_direction_packages(monkeypatch, tmp_path):
    module = _load_server_module("cb_studio_retry_missing_scenes_test")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    complete = tmp_path / "cb-output/creative/Ep2_scene2_storyboard.json"
    complete.parent.mkdir(parents=True)
    complete.write_text("{}")
    monkeypatch.setattr(cb_intake, "scene_roster", lambda episode: {
        "scenes": [{"sceneNumber": number} for number in range(1, 4)]})
    calls = []
    monkeypatch.setattr(module, "_start", lambda job_id, gate, scene, args: (
        calls.append(scene) or job_id))

    module._queue_episode_storyboards("Ep2")

    assert calls == ["1", "3"]


def test_episode_retry_rebuilds_and_archives_storyboard_from_stale_script(monkeypatch,
                                                                          tmp_path):
    module = _load_server_module("cb_studio_retry_stale_scene_test")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    stale = tmp_path / "cb-output/creative/Ep2_scene1_storyboard.json"
    stale.parent.mkdir(parents=True)
    stale.write_text(json.dumps({
        "sourceScript": {"scriptVersionId": "sha256:old"},
    }))
    monkeypatch.setattr(module.cb_scripts, "ScriptStore", lambda *_args, **_kwargs: type(
        "Store", (), {"current": lambda self, *_args, **_kwargs: {
            "scriptVersionId": "sha256:new1234567890",
        }})())
    monkeypatch.setattr(cb_intake, "scene_roster", lambda episode: {
        "scenes": [{"sceneNumber": 1}]})
    calls = []
    monkeypatch.setattr(module, "_start", lambda job_id, gate, scene, args: (
        calls.append(scene) or job_id))

    module._queue_episode_storyboards("Ep2")

    assert calls == ["1"]
    archived = (stale.parent / "archive/script-new123456789" /
                "Ep2_scene1_storyboard.json")
    assert archived.exists()
    assert json.loads(archived.read_text())["sourceScript"]["scriptVersionId"] == "sha256:old"


def test_uncached_director_builds_are_serialized_across_different_shots(monkeypatch):
    module = _load_server_module("cb_studio_serve_build_serialization_test")
    active = 0
    max_active = 0
    state_lock = threading.Lock()

    def fake_director_session(scene, episode="Ep1", requested_shot_id=None):
        nonlocal active, max_active
        with state_lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.05)
        with state_lock:
            active -= 1
        return {"scene": scene, "shot": requested_shot_id}

    monkeypatch.setattr(module, "_director_session", fake_director_session)
    module._clear_director_session_cache()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(
            lambda shot: module._cached_director_session("1", "Ep1", shot),
            ("S1.SH1A", "S1.SH1B", "S1.SH1C", "S1.SH2"),
        ))

    assert max_active == 1
    assert [result["shot"] for result in results] == [
        "S1.SH1A", "S1.SH1B", "S1.SH1C", "S1.SH2",
    ]


def test_snapshot_storyboard_approval_promotes_existing_scene_package(monkeypatch, tmp_path):
    module = _load_server_module("cb_studio_serve_snapshot_handover_test")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "OUT", tmp_path / "cb-output")
    creative = module.OUT / "creative"
    creative.mkdir(parents=True)
    signature = {
        "kind": "scene-storyboard-snapshot",
        "schemaVersion": 1,
        "inputs": {"sceneNumber": "3"},
        "algorithm": "sha256",
        "digest": "fixture",
    }
    storyboard_path = creative / "Ep1_scene3_storyboard.json"
    storyboard_path.write_text(json.dumps({
        "episodeId": "Ep1",
        "sceneNumber": "3",
        "approvalState": "generated-pending-human-review",
        "humanNote": "",
        "inputSignature": signature,
    }))
    original_storyboard_sha = cb_lineage.sha256_file(storyboard_path)
    package_inputs = {
        "scriptVersionId": "sha256:" + "a" * 64,
        "beatPackageDigest": "beat-digest",
        "storyboardSha256": original_storyboard_sha,
        "creativeCardHashes": {},
        "canonProfileDigest": None,
    }
    package_path = module.OUT / "Ep1_scene3_production_package.json"
    package_path.write_text(json.dumps({
        "episode": "Ep1",
        "sceneNumber": 3,
        "revision": 1,
        "sourceStoryboard": {
            "path": str(storyboard_path),
            "md5": hashlib.md5(storyboard_path.read_bytes()).hexdigest(),
            "sha256": original_storyboard_sha,
            "inputSignature": signature,
        },
        "inputSignature": cb_lineage.dependency_signature(
            "production-package", package_inputs),
        "validation": {"passed": True},
        "shots": [{"shotId": "3.B1.S1"}, {"shotId": "3.B2.S1"}],
    }))

    result = module._storyboard_approval({
        "episode": "Ep1",
        "scene": "3",
        "target": "scene",
        "verdict": "approved",
        "note": "approved by Julian",
        "by": "Julian",
    })

    assert result["ok"] is True
    assert result["handover"]["reset"] == ["3.B1.S1", "3.B2.S1"]
    assert json.loads(storyboard_path.read_text())["approvalState"] == "approved"
    written = json.loads(package_path.read_text())
    approved_storyboard_bytes = storyboard_path.read_bytes()
    approved_storyboard_sha = cb_lineage.sha256_file(storyboard_path)
    assert written["sourceStoryboard"]["approvalState"] == "approved"
    assert written["sourceStoryboard"]["humanNote"] == "approved by Julian"
    assert written["sourceStoryboard"]["md5"] == hashlib.md5(approved_storyboard_bytes).hexdigest()
    assert written["sourceStoryboard"]["sha256"] == approved_storyboard_sha
    assert written["inputSignature"]["inputs"]["storyboardSha256"] == approved_storyboard_sha
    assert cb_lineage.signature_matches(
        written["inputSignature"],
        "production-package",
        {**package_inputs, "storyboardSha256": approved_storyboard_sha},
    )
    approved_record = json.loads(storyboard_path.read_text())
    approval_log = list(approved_record.get("approvalLog") or [])

    repaired = module._ensure_storyboard_handover({"episode": "Ep1", "scene": "3"})

    assert repaired["ok"] is True
    assert repaired["approvalPreserved"] is True
    assert json.loads(storyboard_path.read_text()).get("approvalLog") == approval_log


def test_approved_scene_handover_preserves_exact_unchanged_shots(monkeypatch, tmp_path):
    module = _load_server_module("cb_studio_serve_unchanged_handover_test")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "OUT", tmp_path / "cb-output")
    monkeypatch.setattr(
        module, "scene_lineage",
        lambda package, scene, episode="Ep1": {"current": True})
    creative = module.OUT / "creative"
    creative.mkdir(parents=True)
    shots = [
        {"shotId": "S3.SH1", "purpose": "Open the room"},
        {"shotId": "S3.SH2", "purpose": "Reveal Bo"},
    ]
    storyboard_signature = {
        "kind": "scene-storyboard",
        "inputs": {"sceneNumber": "3"},
        "digest": "approved-direction",
    }
    storyboard_path = creative / "Ep1_scene3_storyboard.json"
    storyboard_path.write_text(json.dumps({
        "episodeId": "Ep1",
        "sceneNumber": "3",
        "approvalState": "approved",
        "approvalLog": [{"state": "approved", "by": "Julian"}],
        "inputSignature": storyboard_signature,
        "shots": shots,
    }))
    card_hashes = module._storyboard_creative_card_hashes(
        json.loads(storyboard_path.read_text()))
    old_storyboard_sha = "1" * 64
    package_inputs = {
        "scriptVersionId": "sha256:" + "a" * 64,
        "storyboardSha256": old_storyboard_sha,
        "creativeCardHashes": card_hashes,
    }
    package_path = module.OUT / "Ep1_scene3_production_package.json"
    package_path.write_text(json.dumps({
        "episode": "Ep1",
        "sceneNumber": 3,
        "revision": 4,
        "sourceStoryboard": {
            "path": str(storyboard_path),
            "md5": "stale",
            "sha256": old_storyboard_sha,
            "inputSignature": storyboard_signature,
            "creativeCardHashes": card_hashes,
        },
        "inputSignature": cb_lineage.dependency_signature(
            "production-package", package_inputs),
        "validation": {"passed": True},
        "shots": [{"shotId": shot["shotId"]} for shot in shots],
        "continuityLedger": [{"shotId": "S3.SH1", "keyframeApproval": {"state": "approved"}}],
    }))

    result = module._ensure_storyboard_handover({"episode": "Ep1", "scene": "3"})

    assert result["approvalPreserved"] is True
    assert result["handover"]["carriedForward"] == ["S3.SH1", "S3.SH2"]
    assert result["handover"]["reset"] == []
    written = json.loads(package_path.read_text())
    assert written["continuityLedger"] == [
        {"shotId": "S3.SH1", "keyframeApproval": {"state": "approved"}}]
    assert written["handover"]["resetChangedShots"] == []
    assert written["sourceStoryboard"]["sha256"] == cb_lineage.sha256_file(storyboard_path)
    assert written["inputSignature"]["inputs"]["storyboardSha256"] == cb_lineage.sha256_file(
        storyboard_path)


def test_approved_scene_handover_rebuilds_when_one_shot_changed(monkeypatch, tmp_path):
    module = _load_server_module("cb_studio_serve_changed_handover_test")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "OUT", tmp_path / "cb-output")
    creative = module.OUT / "creative"
    creative.mkdir(parents=True)
    storyboard_path = creative / "Ep1_scene3_storyboard.json"
    storyboard_path.write_text(json.dumps({
        "approvalState": "approved",
        "inputSignature": {"digest": "same-direction"},
        "shots": [{"shotId": "S3.SH1", "purpose": "changed"}],
    }))
    package_path = module.OUT / "Ep1_scene3_production_package.json"
    package_path.write_text(json.dumps({
        "revision": 1,
        "validation": {"passed": True},
        "sourceStoryboard": {
            "inputSignature": {"digest": "same-direction"},
            "creativeCardHashes": {"S3.SH1": "old-card-hash"},
        },
        "shots": [{"shotId": "S3.SH1"}],
    }))
    monkeypatch.setattr(
        module, "_promote_approved_storyboard",
        lambda path, ep, sc, package: {"revision": 2, "reset": ["S3.SH1"]})

    result = module._ensure_storyboard_handover({"episode": "Ep1", "scene": "3"})

    assert result["handover"]["reset"] == ["S3.SH1"]
    assert json.loads(package_path.read_text())["revision"] == 1


def test_launch_token_establishes_http_only_session_and_cleans_url(studio):
    module, port = studio
    status, headers, _ = _request(port, "GET", "/cb-studio/app.html")
    assert status == 303
    assert headers["Location"] == "/cb-studio/app.html"
    assert "HttpOnly" in headers["Set-Cookie"]

    status, headers, _ = _request(
        port, "GET", f"/cb-studio/app.html?launchToken={module.LAUNCH_TOKEN}")
    assert status == 303
    assert headers["Location"] == "/cb-studio/app.html"
    assert "launchToken" not in headers["Location"]
    assert "HttpOnly" in headers["Set-Cookie"]
    assert "SameSite=Strict" in headers["Set-Cookie"]
    assert "Max-Age=2592000" in headers["Set-Cookie"]

    cookie = headers["Set-Cookie"].split(";", 1)[0]
    status, headers, body = _request(
        port, "GET", "/cb-studio/app.html", {"Cookie": cookie})
    assert status == 200
    assert b"Animation Studio" in body
    assert "Access-Control-Allow-Origin" not in headers
    assert headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]


def test_authenticated_browser_session_survives_server_restart(monkeypatch, tmp_path):
    secret_path = tmp_path / "studio-session-secret"
    monkeypatch.setenv("CB_STUDIO_SESSION_SECRET_FILE", str(secret_path))
    first = _load_server_module("cb_studio_serve_restart_first")
    server = first.http.server.ThreadingHTTPServer(("127.0.0.1", 0), first.H)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_port
        _, headers, _ = _request(
            port, "GET", f"/cb-studio/director.html?launchToken={first.LAUNCH_TOKEN}")
        cookie = headers["Set-Cookie"].split(";", 1)[0]
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=3)

    second = _load_server_module("cb_studio_serve_restart_second")
    assert second.SESSION_TOKEN == first.SESSION_TOKEN
    assert secret_path.stat().st_mode & 0o777 == 0o600
    restarted = second.http.server.ThreadingHTTPServer(("127.0.0.1", 0), second.H)
    restarted_thread = threading.Thread(target=restarted.serve_forever, daemon=True)
    restarted_thread.start()
    try:
        status, _, body = _request(
            restarted.server_port, "GET", "/api/studio-version", {"Cookie": cookie})
        assert status == 200
        assert json.loads(body)["version"] == second.STUDIO_BUILD_VERSION
    finally:
        restarted.shutdown(); restarted.server_close(); restarted_thread.join(timeout=3)


def test_director_entry_and_facade_share_the_authenticated_session(studio):
    module, port = studio
    status, headers, _ = _request(port, "GET", "/cb-studio/director.html")
    assert status == 303
    assert headers["Location"] == "/cb-studio/director.html"
    assert "HttpOnly" in headers["Set-Cookie"]

    status, headers, _ = _request(
        port, "GET", f"/cb-studio/director.html?launchToken={module.LAUNCH_TOKEN}")
    assert status == 303
    assert headers["Location"] == "/cb-studio/director.html"
    cookie = headers["Set-Cookie"].split(";", 1)[0]

    status, _, body = _request(
        port, "GET", "/cb-studio/director.html", {"Cookie": cookie})
    assert status == 200
    assert b'id="view-director"' in body

    status, _, body = _request(
        port, "GET", "/api/director-session?episode=Ep1&scene=1",
        {"Cookie": cookie})
    assert status == 200
    session = json.loads(body)
    assert session["schemaVersion"] == 1
    assert session["selectedShotId"]
    if session["status"] == "rendering":
        assert session["primaryAction"] is None
        assert session["runningJob"]
    elif session["primaryAction"] is None:
        assert session["status"] in {"ready_to_review", "complete"}
        if session["status"] == "ready_to_review":
            assert session["decisionActions"]
    else:
            assert session["primaryAction"]["id"] in {
                "direct-scene", "build-keyframe", "build-voice", "prepare-render", "open-inspector",
                "open-provider-setup", "run-quality-review", "build-master", "run-final-review",
            }

    origin = f"http://127.0.0.1:{port}"
    status, _, body = _request(
        port, "POST", "/api/director-action",
        {"Cookie": cookie, "Content-Type": "application/json", "Origin": origin},
        body=json.dumps({
            "episode": "Ep1", "scene": "1", "shotId": "S1.SH1",
            "action": "invented-action",
        }).encode(),
    )
    assert status == 409
    assert "no longer current" in json.loads(body)["error"]


def test_host_origin_and_session_are_all_enforced(studio):
    module, port = studio
    _, headers, _ = _request(
        port, "GET", f"/cb-studio/app.html?launchToken={module.LAUNCH_TOKEN}")
    cookie = headers["Set-Cookie"].split(";", 1)[0]

    status, _, _ = _request(
        port, "GET", "/api/health", {"Cookie": cookie, "Host": "attacker.example"})
    assert status == 421

    status, _, _ = _request(
        port, "POST", "/api/stop", {"Cookie": cookie, "Content-Type": "application/json"},
        body=b"{}")
    assert status == 403

    status, _, _ = _request(
        port, "POST", "/api/stop",
        {"Cookie": cookie, "Content-Type": "application/json",
         "Origin": "https://attacker.example"}, body=b"{}")
    assert status == 403

    origin = f"http://127.0.0.1:{port}"
    status, _, _ = _request(
        port, "POST", "/api/stop",
        {"Cookie": cookie, "Content-Type": "application/json", "Origin": origin},
        body=b"{}")
    assert status == 200


def test_explicit_https_origin_supports_secure_remote_access(monkeypatch):
    public_origin = "https://studio-test.example"
    monkeypatch.setenv("CB_STUDIO_PUBLIC_ORIGIN", public_origin)
    module = _load_server_module()
    monkeypatch.chdir(ROOT)
    server = module.http.server.ThreadingHTTPServer(("127.0.0.1", 0), module.H)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_port
        remote_headers = {"Host": "studio-test.example"}
        status, _, _ = _request(
            port,
            "GET",
            "/cb-studio/app.html",
            remote_headers,
        )
        assert status == 401

        status, headers, _ = _request(
            port,
            "GET",
            f"/cb-studio/app.html?launchToken={module.LAUNCH_TOKEN}",
            remote_headers,
        )
        assert status == 303
        assert "Secure" in headers["Set-Cookie"]
        cookie = headers["Set-Cookie"].split(";", 1)[0]

        status, _, _ = _request(
            port, "GET", "/api/health", {**remote_headers, "Cookie": cookie})
        assert status == 200

        status, _, _ = _request(
            port,
            "POST",
            "/api/stop",
            {
                **remote_headers,
                "Cookie": cookie,
                "Content-Type": "application/json",
                "Origin": public_origin,
            },
            body=b"{}",
        )
        assert status == 200

        status, _, _ = _request(
            port,
            "POST",
            "/api/stop",
            {
                **remote_headers,
                "Cookie": cookie,
                "Content-Type": "application/json",
                "Origin": "https://attacker.example",
            },
            body=b"{}",
        )
        assert status == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_frontend_uses_its_authenticated_origin_and_no_remote_script():
    html = (HERE / "app.html").read_text()
    assert "const BASE=window.location.origin" in html
    assert "cdnjs.cloudflare.com" not in html
    assert '<script src="http' not in html


def test_parallel_index_reads_return_complete_json(studio):
    module, port = studio
    _, headers, _ = _request(
        port, "GET", f"/cb-studio/app.html?launchToken={module.LAUNCH_TOKEN}")
    cookie = headers["Set-Cookie"].split(";", 1)[0]
    paths = ["/cb-studio/data/episodes.json", "/cb-studio/data/media-index.json"] * 8

    def read(path):
        return _request(port, "GET", path, {"Cookie": cookie})

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(read, paths))

    for status, _, body in results:
        assert status == 200
        assert isinstance(json.loads(body), list)


def test_credits_endpoint_requires_auth_and_routes_one_explicit_fire(studio, monkeypatch):
    from types import SimpleNamespace
    module, port = studio
    calls = []
    credits = SimpleNamespace(
        status=lambda ep: {"ok": True, "episode": ep, "characters": []},
        episode_id=lambda ep: ep,
        prepare=lambda ep, config: {"ok": True, "status": "prepared", "token": "sealed"},
    )
    render = SimpleNamespace(fire_credits=lambda ep, token: calls.append((ep, token)) or {"ok": True, "status": "starting"})
    monkeypatch.setattr(module, "_canonical_engine_module", lambda name: render if name == "cb_render" else credits)
    code, _, _ = _request(port, "GET", "/api/credits?episode=Ep2")
    assert code == 401
    _, headers, _ = _request(port, "GET", "/cb-studio/app.html")
    auth = {"Cookie": headers["Set-Cookie"].split(";", 1)[0], "Origin": f"http://127.0.0.1:{port}", "Content-Type": "application/json"}
    code, _, data = _request(port, "GET", "/api/credits?episode=Ep2", auth)
    assert code == 200 and json.loads(data)["episode"] == "Ep2"
    code, _, data = _request(port, "POST", "/api/credits", auth, json.dumps({"episode": "Ep2", "action": "prepare", "config": {}}))
    assert code == 200 and calls == []
    code, _, _ = _request(port, "POST", "/api/credits", auth, json.dumps({"episode": "Ep2", "action": "fire", "token": "sealed"}))
    assert code == 200 and calls == [("Ep2", "sealed")]


@pytest.mark.parametrize('gate,spoken,next_stage', [
    ('chat:approve:keyframe', True, 'voice'),
    ('chat:approve:keyframe', False, 'animation'),
    ('chat:approve:voice', True, 'animation'),
    ('chat:approve:render', True, 'voice'),
])
def test_chat_approval_prepares_only_next_outcome(monkeypatch, tmp_path, gate, spoken, next_stage):
    module = _load_server_module('outcome_transition_' + next_stage)
    import cb_episode_budget as budget
    import cb_render as render
    budget.approve('Ep3', 10, 'Julian', 'script')
    pkg = {'shots': [{'shotId': 'S1.SH1', 'sourceType': 'opener'},
                     {'shotId': 'S1.SH2', 'sourceType': 'relay'}]}
    monkeypatch.setattr(render, 'load_pkg', lambda *a: (pkg, tmp_path / 'package.json'))
    monkeypatch.setattr(render.cb_audio_authority, 'spoken_dialogue_lines', lambda *a: ['voice'] if spoken else [])
    calls = []
    monkeypatch.setattr(module, '_start', lambda jid, gate, scene, args: calls.append((gate,args)) or 'next')
    job = {'status': 'finalizing', 'gate': gate,
           'args': ['cb_outcome_chat.py','Ep3','1','S1.SH1','keyframe','hash','Julian']}
    module._finalize_automatic_direction(job)
    assert calls[0][0] == 'chat:prepare:' + next_stage
    assert calls[0][1][-1] == next_stage
    assert job['nextOutcomeScope']['shotId'] == ('S1.SH2' if gate.endswith(':render') else 'S1.SH1')
    assert len(calls) == 1


def test_budget_approval_does_not_approve_any_media(monkeypatch, tmp_path):
    module = _load_server_module('outcome_budget')
    import cb_director_chat as chat
    import cb_outcome_chat as outcomes
    monkeypatch.setattr(chat, 'CHAT_DIR', tmp_path / 'chat')
    monkeypatch.setattr(module.SCRIPT_STORE, 'current', lambda *a, **kw: {'scriptVersionId': 'script'})
    monkeypatch.setattr(cb_intake, 'intake_status', lambda *a: {'canonicalCurrent': False})
    monkeypatch.setattr(outcomes, 'execute', lambda *a: pytest.fail('Budget is not media approval'))
    calls = []
    monkeypatch.setattr(module, '_start', lambda jid, gate, scene, args: calls.append((gate,args)) or 'intake')
    result = module._outcome_chat_command({'message': 'Approve episode budget $50', 'by': 'Julian'}, 'Ep3','1',None,'script')
    assert result['budget']['limitUsd'] == 50
    assert calls == [('storyintake',['cb_intake.py','run','Ep3'])]
    assert result['decisionKind'] is None


@pytest.mark.parametrize('path', ['/api/room-chat', '/api/write'])
def test_retired_paid_routes_fail_without_starting_work(studio, monkeypatch, path):
    module, port = studio
    monkeypatch.setattr(module, '_start', lambda *a, **kw: pytest.fail('Retired route started work'))
    _, headers, _ = _request(port, 'GET', '/cb-studio/app.html')
    cookie = headers['Set-Cookie'].split(';', 1)[0]
    status, _, body = _request(port, 'POST', path, {'Cookie': cookie, 'Content-Type': 'application/json',
        'Origin': f'http://127.0.0.1:{port}'}, '{}')
    assert status == 410
    assert json.loads(body)['zeroSpend'] is True


@pytest.mark.parametrize('code,expected_jobs', [('prepare-keyframe', 1), ('review-request', 0), ('review-candidate', 0), ('recover-media', 0)])
def test_continue_uses_shared_next_step_and_never_substitutes_for_approval(monkeypatch, tmp_path, code, expected_jobs):
    module = _load_server_module('director_desk_continue_' + code)
    import cb_director_chat as chat
    import cb_episode_budget as budget
    monkeypatch.setattr(chat, 'CHAT_DIR', tmp_path / 'chat')
    monkeypatch.setattr(budget, 'status', lambda ep: {'approved': True})
    stage = 'keyframe' if code == 'prepare-keyframe' else 'animation'
    monkeypatch.setattr(module, '_outcome_chat_context', lambda *a: {'nextAction': {'code': code, 'stage': stage, 'label': 'Next'}})
    calls = []
    monkeypatch.setattr(module, '_start', lambda jid, gate, scene, args: calls.append((gate,args)) or 'prepare')
    result = module._outcome_chat_command({'message': 'continue'}, 'Ep3', '1', 'S1.SH1', stage)
    assert len(calls) == expected_jobs
    assert result['navigation'] == stage
    assert result['decisionKind'] is None
    if calls:
        assert calls[0][0] == 'chat:prepare:keyframe'
        assert calls[0][1][1] == 'prepare'
