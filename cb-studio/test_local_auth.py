import http.client
import importlib.util
import pathlib
import threading

import pytest


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent


def _load_server_module():
    spec = importlib.util.spec_from_file_location("cb_studio_serve_auth_test", HERE / "serve.py")
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
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    request_headers = {"Host": f"127.0.0.1:{port}", **(headers or {})}
    connection.request(method, path, body=body, headers=request_headers)
    response = connection.getresponse()
    payload = response.read()
    result = response.status, dict(response.getheaders()), payload
    connection.close()
    return result


def test_launch_token_establishes_http_only_session_and_cleans_url(studio):
    module, port = studio
    status, _, _ = _request(port, "GET", "/cb-studio/app.html")
    assert status == 401

    status, headers, _ = _request(
        port, "GET", f"/cb-studio/app.html?launchToken={module.LAUNCH_TOKEN}")
    assert status == 303
    assert headers["Location"] == "/cb-studio/app.html"
    assert "launchToken" not in headers["Location"]
    assert "HttpOnly" in headers["Set-Cookie"]
    assert "SameSite=Strict" in headers["Set-Cookie"]

    cookie = headers["Set-Cookie"].split(";", 1)[0]
    status, headers, body = _request(
        port, "GET", "/cb-studio/app.html", {"Cookie": cookie})
    assert status == 200
    assert b"Crystal Bears" in body
    assert "Access-Control-Allow-Origin" not in headers
    assert headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]


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


def test_frontend_uses_its_authenticated_origin_and_no_remote_script():
    html = (HERE / "app.html").read_text()
    assert "const BASE=window.location.origin" in html
    assert "cdnjs.cloudflare.com" not in html
    assert '<script src="http' not in html
