import ast
from pathlib import Path
import cb_render as R
import pytest


@pytest.mark.parametrize('actual_hash,stored_hash,buildable', [
    ('intact', 'intact', False), (None, 'intact', True),
    ('changed', 'intact', True), (None, None, True),
])
def test_build_status_checks_candidate_content_not_only_inputs(monkeypatch, actual_hash, stored_hash, buildable):
    candidate = {'path': 'candidate.png', 'inputSignature': {'input': 'current'},
                 'contentHash': stored_hash}
    monkeypatch.setattr(R, 'load_pkg', lambda *a: ({}, None))
    monkeypatch.setattr(R, '_shot', lambda *a: {})
    monkeypatch.setattr(R, '_ledger', lambda *a: {'keyframeCandidate': candidate})
    monkeypatch.setattr(R, '_shot_uses_own_keyframe', lambda *a: True)
    monkeypatch.setattr(R, '_keyframe_input_signature', lambda *a: {'input': 'current'})
    monkeypatch.setattr(R, '_keyframe_request_preflight', lambda *a, **k: {})
    monkeypatch.setattr(R, '_sha256_file', lambda *a: actual_hash)
    assert R.keyframe_build_status('1', 'X')['buildable'] is buildable
    assert candidate['contentHash'] == stored_hash

def test_all_native_keyframe_entrypoints_default_to_single_candidate():
    for filename,names in [('cb_render.py',{'build_keyframe','keyframe_shot','keyframe_build_status'}),('cb_safety.py',{'keyframe_shot'})]:
        tree=ast.parse(Path(__file__).with_name(filename).read_text())
        found=set()
        for node in ast.walk(tree):
            if isinstance(node,ast.FunctionDef) and node.name in names:
                pairs=dict(zip([a.arg for a in node.args.kwonlyargs],node.args.kw_defaults))
                assert isinstance(pairs['compare'],ast.Constant) and pairs['compare'].value is False
                found.add(node.name)
        assert found==names


@pytest.mark.parametrize('stale_candidate', [False, True])
def test_build_status_cannot_offer_generation_when_request_check_refuses(
        monkeypatch, stale_candidate):
    candidate = {'path': 'old.png', 'inputSignature': {'input': 'old'},
                 'contentHash': 'intact'} if stale_candidate else None
    ledger = {'keyframeCandidate': candidate}
    monkeypatch.setattr(R, 'load_pkg', lambda *a: ({}, None))
    monkeypatch.setattr(R, '_shot', lambda *a: {'shotId': 'X'})
    monkeypatch.setattr(R, '_ledger', lambda *a: ledger)
    monkeypatch.setattr(R, '_shot_uses_own_keyframe', lambda *a: True)
    monkeypatch.setattr(R, '_keyframe_input_signature', lambda *a: {'input': 'current'})
    monkeypatch.setattr(R, '_sha256_file', lambda *a: 'intact')

    def refuse(*args, **kwargs):
        raise R.Refused('REFUSED — keyframe prompt [MUST PRESERVE] differs')

    monkeypatch.setattr(R, '_keyframe_request_preflight', refuse)
    status = R.keyframe_build_status('1', 'X')
    assert status['state'] == 'needs-preparation'
    assert status['buildable'] is False
    assert status['mediaCallsRequired'] == 0
    assert '[MUST PRESERVE]' in status['reason']
    assert ledger['keyframeCandidate'] is candidate


def test_request_preflight_checks_exact_prompt_and_references(monkeypatch):
    shot = {'shotId': 'X'}
    package = {'shots': [shot]}
    for name in ('_require_show_adapter', '_require_current_see_canon',
                 '_require_valid', '_require_current_lineage',
                 '_require_confirmed_billing', '_require_current_scenelook'):
        monkeypatch.setattr(R, name, lambda *args: None)
    monkeypatch.setattr(R, '_direct_keyframe_direction', lambda *args: {})
    monkeypatch.setattr(R.cb_engine_rules, 'playable_stage_report',
                        lambda *args: {'ready': True})
    monkeypatch.setattr(R, '_characters_cfg', lambda: {})
    monkeypatch.setattr(R, '_slot_paths', lambda *args: ['locked-reference.png'])
    monkeypatch.setattr(R, '_resolve_keyframe_prompt', lambda *args: 'exact prompt')
    monkeypatch.setattr(R, '_keyframe_input_signature',
                        lambda *args: {'briefHash': 'exact hash'})

    def check_contract(pkg, candidate_shot, prompt):
        assert pkg is package and candidate_shot is shot
        assert prompt == 'exact prompt'
        raise R.Refused('REFUSED — keyframe prompt [MUST PRESERVE] differs')

    monkeypatch.setattr(R, '_keyframe_prompt_contract', check_contract)
    with pytest.raises(R.Refused, match=r'keyframe prompt \[MUST PRESERVE\]'):
        R._keyframe_request_preflight(package, shot, '1', 'Ep1')

def test_displayed_build_cost_and_provider_match_single_default(monkeypatch):
    monkeypatch.setattr(R,'load_pkg',lambda *a:({'shots':[{'shotId':'X'}]},None))
    monkeypatch.setattr(R,'_shot',lambda *a:{'shotId':'X'})
    monkeypatch.setattr(R,'_ledger',lambda *a:{})
    monkeypatch.setattr(R,'_shot_uses_own_keyframe',lambda *a:True)
    monkeypatch.setattr(R,'_keyframe_request_preflight',lambda *a,**k:{})
    monkeypatch.setattr(R,'_expanded_reference_blueprint',lambda *a,**k:[])
    import cb_costs
    monkeypatch.setattr(cb_costs,'estimate_image_cost',lambda **k:.1 if k['provider']=='seedream5pro' else .2)
    status=R.keyframe_build_status('1','X')
    assert status['maxMediaCalls']==status['finishingCallsRequired']==1
    assert status['estimatedMaxUsd']==.1 and status['provider']=='byteplus'
    assert list(status['providerModelId'])==['A']
    comparison=R.keyframe_build_status('1','X',compare=True)
    assert comparison['maxMediaCalls']==2 and comparison['estimatedMaxUsd']==.3
