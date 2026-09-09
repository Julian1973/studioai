"""Replacing a selected image must not break earlier generations' source paths."""
import inspect

import cb_render as render
import pytest


@pytest.mark.parametrize('stage', ['scenelook', 'keyframe'])
def test_superseding_approved_reference_preserves_original_path(monkeypatch, tmp_path, stage):
    monkeypatch.setattr(render, 'HERE', tmp_path)
    old = tmp_path / 'media' / 'approved.png'
    old.parent.mkdir()
    old.write_bytes(b'approved immutable image')
    new = old.with_name('candidate.png')
    new.write_bytes(b'new selected image')
    record = {'path': str(old), 'approved': True}
    candidate = {'path': str(new), 'source': 'library'}
    policy = render._production_policy
    if stage == 'scenelook':
        state = {'approved': record, 'candidate': candidate}
        monkeypatch.setattr(render, '_load_scenelook_rec', lambda *args: state)
        monkeypatch.setattr(render, '_save_scenelook_rec', lambda *args: None)
        original = inspect.getclosurevars(policy.approve_scenelook).nonlocals['original']
        original['approve_scenelook']('1', 'EpTest', 'Explicit user selection', lambda _: None)
        assert state['approved']['path'] == str(new)
        history = state['history']
    else:
        ledger = {'keyframeApproval': record, 'keyframeCandidate': candidate}
        monkeypatch.setattr(render, 'load_pkg', lambda *args: ({}, tmp_path / 'package.json'))
        monkeypatch.setattr(render, '_shot', lambda *args: {'shotId': 'S1.SH1'})
        monkeypatch.setattr(render, '_ledger', lambda *args: ledger)
        monkeypatch.setattr(render, '_save', lambda *args: None)
        original = inspect.getclosurevars(policy.approve_keyframe).nonlocals['original']
        original['approve_keyframe']('1', 'S1.SH1', 'EpTest', 'Explicit user selection', lambda _: None)
        assert ledger['keyframeApproval']['path'] == str(new)
        history = ledger['keyframeHistory']
    assert old.read_bytes() == b'approved immutable image'
    assert (tmp_path / history[-1]['archivedFile']).read_bytes() == old.read_bytes()
    assert new.read_bytes() == b'new selected image'
