import http.client
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


def _load_server_module(name="cb_studio_serve_auth_test"):
    spec = importlib.util.spec_from_file_location(name, HERE / "serve.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
            "build-keyframe", "build-voice", "prepare-render", "open-inspector",
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
