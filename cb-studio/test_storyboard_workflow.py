"""Offline qualification of the native storyboard job dispatch boundary."""
import copy
from contextlib import nullcontext
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
import studio_see_service as service
from studio_journey import StudioStore


def test_clean_release_storyboard_dispatch_uses_running_python_and_never_duplicates(tmp_path, monkeypatch):
    scope = {'projectId': 'crystal-bears', 'episode': 'Ep4', 'scene': '3', 'unit': 'S3.SH1'}
    state = {}
    status = {'binding': 'assets-v1', 'storyboardRequired': True}
    quote = {'quoteHash': 'reviewed-v1', 'prompts': [], 'scope': scope}
    calls = []

    class Package:
        def __init__(self, *args): pass
        def read(self): return copy.deepcopy(state)
        def save(self, value): state.clear(); state.update(copy.deepcopy(value))
        def lock(self): return nullcontext()

    monkeypatch.setattr(service, 'Package', Package)
    monkeypatch.setattr(service, 'context', lambda *args: {
        'legacy': True, 'directorApproved': True,
        'componentReviews': {'plate': 'approved', 'opening': 'approved'}})
    monkeypatch.setattr(service, '_status', lambda *args: status)
    monkeypatch.setattr(service, 'quote', lambda *args: quote)
    monkeypatch.setattr(service, 'require_plate_review_resolved', lambda *args: None)
    monkeypatch.setattr(StudioStore, 'read', lambda *args: {})
    monkeypatch.setattr(service.subprocess, 'Popen', lambda args, **kwargs: calls.append((args, kwargs)) or SimpleNamespace(pid=123))
    (tmp_path / 'cb-output/state/see-packages').mkdir(parents=True)
    server = SimpleNamespace(ROOT=tmp_path)
    payload = {'scope': scope, 'component': 'storyboard', 'binding': 'assets-v1', 'quoteHash': 'reviewed-v1'}

    service.request(server, {**payload, 'command': 'quote'})
    assert calls == [] and state == {}
    with pytest.raises(ValueError, match='Review the current provider'):
        service.request(server, {**payload, 'command': 'generate', 'quoteHash': 'old'})
    assert calls == [] and state == {}
    service.request(server, {**payload, 'command': 'generate'})
    assert calls[0][0][0] == sys.executable
    assert state['job']['status'] == 'queued' and state['job']['pid'] == 123
    with pytest.raises(ValueError, match='already active'):
        service.request(server, {**payload, 'command': 'generate'})
    assert len(calls) == 1
