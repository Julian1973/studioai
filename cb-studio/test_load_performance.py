"""Exercise actual HTTP encoding and concurrent projection loading; no providers."""
import gzip
import io
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from test_local_auth import _load_server_module


@pytest.mark.parametrize('encoding,compressed', [('gzip', True), ('br, gzip;q=0.5', True),
                                                ('gzip;q=0', False), ('', False)])
def test_json_transport_is_lossless_and_respects_encoding(encoding, compressed):
    server = _load_server_module('load_encoding_test')
    headers = {}
    response = SimpleNamespace(headers={'Accept-Encoding': encoding}, wfile=io.BytesIO(),
        send_response=lambda code: None, send_header=lambda k,v: headers.update({k:v}),
        end_headers=lambda: None)
    payload = {'dialogue': 'Exact words — unchanged. ' * 1000, 'evidence': [1,2,3]}
    server.H._json(response, 200, payload)
    wire = response.wfile.getvalue()
    assert (headers.get('Content-Encoding') == 'gzip') is compressed
    assert json.loads(gzip.decompress(wire) if compressed else wire) == payload
    assert int(headers['Content-Length']) == len(wire)
    assert headers['Cache-Control'] == 'no-store'
    if compressed:
        assert len(wire) < len(json.dumps(payload)) / 10


def test_concurrent_page_reads_share_one_state_build(tmp_path, monkeypatch):
    server = _load_server_module('load_singleflight_test')
    package = tmp_path / 'package.json'; package.write_text('{}')
    entered, release = threading.Event(), threading.Event()
    calls = []
    def build(*args):
        calls.append(args); entered.set()
        assert release.wait(5)
        return {'revision': len(calls)}
    monkeypatch.setattr(server, '_shot_pkg_path', lambda *a: package)
    monkeypatch.setattr(server, '_canonical_cb_state', lambda: SimpleNamespace(production_state=build))
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(server._cached_production_state, '1', 'Ep3') for _ in range(4)]
        assert entered.wait(5); release.set()
        assert [f.result() for f in futures] == [{'revision': 1}] * 4
    assert len(calls) == 1
    server._clear_director_session_cache(scene='1', episode='Ep3')
    assert server._cached_production_state('1', 'Ep3') == {'revision': 2}


def test_invalidation_during_build_does_not_republish_old_state(tmp_path, monkeypatch):
    server = _load_server_module('load_epoch_test')
    package = tmp_path / 'package.json'; package.write_text('{}')
    def build(*args):
        server._clear_director_session_cache(scene='1', episode='Ep3')
        return {'revision': 'old'}
    monkeypatch.setattr(server, '_shot_pkg_path', lambda *a: package)
    monkeypatch.setattr(server, '_canonical_cb_state', lambda: SimpleNamespace(production_state=build))
    server._cached_production_state('1', 'Ep3')
    assert ('Ep3', '1') not in server._PRODUCTION_STATE_CACHE
