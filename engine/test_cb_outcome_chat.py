import pytest
import cb_outcome_chat as C


@pytest.mark.parametrize('text', ["don't approve", 'is it approved?', 'approve but change Bo', 'fire?', 'approve budget', 'approve episode budget $-1'])
def test_ambiguous_or_negative_language_never_approves(text):
    assert C.intent(text) is None


def test_explicit_budget_and_media_commands():
    assert C.intent('Approve episode budget $25.50') == {'kind': 'budget', 'amount': '25.50'}
    assert C.intent('approve') == {'kind': 'approve'}
    assert C.intent('fire')['targetKind'] == 'request'
    assert C.intent('approve render')['targetKind'] == 'render'
    assert C.intent('approve B')['candidateId'] == 'B'


@pytest.fixture
def package(monkeypatch, tmp_path):
    media = tmp_path / 'frame.png'
    media.write_bytes(b'first frame')
    pkg = {'shots': [{'shotId': 'S1.SH1', 'sourceType': 'opener'}], 'continuityLedger': [
        {'shotId': 'S1.SH1', 'keyframeCandidate': {'path': str(media)}}]}
    monkeypatch.setattr(C.R, 'load_pkg', lambda *a: (pkg, tmp_path / 'pkg.json'))
    return pkg, media


def test_review_is_bound_to_bytes_and_shot_inputs(package, monkeypatch):
    pkg, media = package
    original = C.target('Ep3', '1', 'S1.SH1', 'keyframe')
    media.write_bytes(b'changed frame')
    calls = []
    monkeypatch.setattr(C.R, 'approve_keyframe', lambda *a, **k: calls.append(True))
    with pytest.raises(C.R.Refused, match='changed'):
        C.execute('Ep3', '1', 'S1.SH1', 'keyframe', original['hash'])
    assert not calls
    current = C.target('Ep3', '1', 'S1.SH1', 'keyframe')
    C.execute('Ep3', '1', 'S1.SH1', 'keyframe', current['hash'])
    assert calls == [True]


def test_request_approval_submits_only_sealed_request_not_render_approval(package, monkeypatch):
    pkg, _ = package
    pkg['continuityLedger'][0]['pendingSpendAuth'] = {'token': 'fixture', 'disclosure': {'candidateCount': 1}}
    calls = []
    monkeypatch.setattr(C.R, 'fire_shot', lambda *a, **k: calls.append(k))
    monkeypatch.setattr(C.R, 'approve_shot', lambda *a, **k: pytest.fail('Must review returned render separately'))
    review = C.target('Ep3', '1', 'S1.SH1', 'animation')
    C.execute('Ep3', '1', 'S1.SH1', 'animation', review['hash'])
    assert calls == [{'candidates': 1, 'spend_token': 'fixture'}]


def test_voice_without_dialogue_prepares_request_and_never_invents_voice(package, monkeypatch):
    import cb_studio_director as D
    C.budget.approve('Ep3', 10, 'Julian', 'script')
    calls = []
    monkeypatch.setattr(C.R, 'regen_voice_shot', lambda *a, **k: pytest.fail('Silent shot'))
    monkeypatch.setattr(D, 'prepare_render', lambda *a: calls.append('prepare-watch'))
    assert C.prepare('Ep3', '1', 'S1.SH1', 'voice') == {'requestReady': True}
    assert calls == ['prepare-watch']


def test_keyframe_preparation_routes_unapproved_scene_plate_back_to_see(package, monkeypatch):
    from contextlib import nullcontext
    pkg, _ = package
    pkg['continuityLedger'][0].pop('keyframeCandidate', None)
    C.budget.approve('Ep3', 10, 'Julian', 'script')
    monkeypatch.setattr(C.cb_db, 'scene_lease', lambda *a, **k: nullcontext())
    monkeypatch.setattr(C.R.production_contracts, 'active_shots', lambda value: value['shots'])
    monkeypatch.setattr(C.R, 'scenelook_status', lambda *a, **k: {'current': True, 'approvedCurrent': False})
    monkeypatch.setattr(C.R, 'approve_scenelook', lambda *a, **k: pytest.fail('SEE cannot be auto-approved'))
    monkeypatch.setattr(C.R, 'keyframe_shot', lambda *a, **k: pytest.fail('Opening build must wait for plate approval'))

    with pytest.raises(C.R.Refused, match='SEE_CONFIGURATION_REQUIRED'):
        C.prepare('Ep3', '1', 'S1.SH1', 'keyframe')


def test_render_selection_is_bound_to_reviewed_batch(package, monkeypatch):
    pkg, media = package
    led = pkg['continuityLedger'][0]
    led['candidatePaths'] = [str(media), str(media)]
    led['status'] = 'candidates-pending'
    calls = []
    monkeypatch.setattr(C.R, 'approve_shot', lambda *a, **kw: calls.append(a))
    review = C.target('Ep3', '1', 'S1.SH1', 'animation')
    with pytest.raises(C.R.Refused, match='Select the render'):
        C.execute('Ep3', '1', 'S1.SH1', 'animation', review['hash'])
    with pytest.raises(C.R.Refused, match='not in the reviewed batch'):
        C.execute('Ep3', '1', 'S1.SH1', 'animation', review['hash'], candidate_id='3')
    assert calls == []
    C.execute('Ep3', '1', 'S1.SH1', 'animation', review['hash'], candidate_id='2')
    assert calls[0][2] == 2
