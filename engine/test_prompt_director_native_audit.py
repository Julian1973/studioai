"""Legacy Studio Fire path qualification with synthetic files and no network."""
import json,socket
import pytest
import cb_render as R, cb_llm
from test_current_production_path import world, isolated_canon, _approve_specialist_inputs, _approve_scene_look, _sign_specialist_inputs
from test_golden_path import _approve_animation_direction
from test_studio_prompt_director import review
from test_prompt_director_route_audit import save

def bind_typed_native_fixture(pkg, monkeypatch):
    """Upgrade synthetic fixture direction before its test approval signatures.

    The old fixture predates typed coverage. Bind its existing single execution
    view explicitly; exercise the real compiler and every production guard.
    """
    from copy import deepcopy
    import test_golden_path as golden
    def adapter(original):
        def make(shot, *args, **kwargs):
            legacy = deepcopy(shot); legacy.pop('directorCard', None)
            result = original(legacy, *args, **kwargs)
            for view, row in zip(shot['directorCard']['views'], result['shotPlan']):
                row['sourceViewId'] = view['viewId']
                row['transitionType'] = view['entry']
            result['providerPrompt'] = R.cb_departments.compile_animation_provider_prompt(shot, result)
            return result
        return make
    monkeypatch.setattr(golden, '_current_animation_fixture', adapter(golden._current_animation_fixture))

@pytest.mark.parametrize('blocked',[True,False])
def test_native_fire_reaches_review_and_obeys_verdict(world,monkeypatch,blocked,tmp_path):
    monkeypatch.setattr(socket.socket,'connect',lambda *a,**k:pytest.fail('Network forbidden'))
    providers,root,path=world
    monkeypatch.setattr(R,'screen_keyframe_conformance',lambda *a,**k:dict(status='pass',reason=None,review=dict(verdict='pass',summary='Synthetic setup, not visually qualified')))
    pkg=json.loads(path.read_text());bind_typed_native_fixture(pkg, monkeypatch);_approve_specialist_inputs(pkg);path.write_text(json.dumps(pkg))
    _approve_scene_look(root,pkg);_sign_specialist_inputs(pkg);path.write_text(json.dumps(pkg))
    sid=pkg['shots'][0]['shotId']
    for shot in pkg['shots']:
        if shot.get('dialogueLines'):
            R.regen_voice_shot('9',shot['shotId'],'EpT',log=lambda *a:None)
            R.approve_voice('9',shot['shotId'],'EpT',reviewed_by='Test',log=lambda *a:None)
    R.keyframe_shot('9',sid,'EpT',log=lambda *a:None)
    R.select_keyframe_candidate('9',sid,'A','EpT',log=lambda *a:None)
    monkeypatch.setattr(cb_llm,'structured_with_repair',lambda *a,**k:dict(verdict='READY',summary='Synthetic SEE',camera='supported',geography='supported',pose='supported',propsEffects='supported',actionFeasibility='supported',findings=[],correctiveAction='none'))
    R.approve_keyframe('9',sid,'EpT',reviewed_by='Test',log=lambda *a:None)
    _approve_animation_direction(sid)
    captured=[]
    def reviewer(system,text,schema,**kwargs):
        if schema.__name__ == 'Assessment':
            return dict(verdict='READY',summary='Synthetic SEE',camera='supported',geography='supported',pose='supported',propsEffects='supported',actionFeasibility='supported',findings=[],correctiveAction='none')
        data=json.loads(text);captured.append(data);result=review()
        if blocked:result['findings']=[dict(category='story/state contradiction',reason='Injected qualification conflict',evidence=(data.get('prompt') or json.dumps(data['authorities'])).splitlines()[0],correction='Resolve authority conflict')]
        return result
    monkeypatch.setattr(cb_llm,'structured_with_repair',reviewer)
    import studio_prompt_director as pd
    import cb_prompt_bank
    monkeypatch.setattr(cb_prompt_bank, 'retake_evidence', lambda context: [
        {'recordId': 'prior-rejected-fixture', 'feedback': 'Duplicate parcel',
         'validation': 'failure-specific-review-required'}])
    real=pd.review_legacy_envelope
    monkeypatch.setattr(pd,'review_legacy_envelope',lambda *a,**k:real(*a,archive_folder=tmp_path/'reviews'))
    with pytest.raises(R.Refused,match='BLOCKED|SPEND NOT APPROVED') as refused:
        R.fire_shot('9',sid,'EpT',candidates=1,log=lambda *a:None)
    assert captured, str(refused.value)
    assert captured[0]['authorities']['outcomeLearning'][0]['recordId'] == 'prior-rejected-fixture'
    assert 'prompt' not in captured[0]  # Source-plan review precedes final payload review.
    if not blocked:
        assert any('prompt' in data for data in captured[1:])
    assert not providers.fire_calls
    current,_=R.load_pkg('9','EpT');ledger=R._ledger(current,sid)
    reports=[json.loads(p.read_text()) for p in (tmp_path/'reviews').glob('*.json')]
    if blocked:assert not ledger.get('pendingSpendAuth')
    else:
        sealed=ledger['pendingSpendAuth']['envelope']['executionPlan']['segments'][0]
        assert sealed['promptDirector']['verdict']=='READY TO FIRE'
        assert sealed['prompt'].startswith('[PURPOSE]')
        assert sealed['prompt'].index('[PURPOSE]') < sealed['prompt'].index('[REFERENCE AUTHORITY]')
    save('native-'+('blocked' if blocked else 'ready'),dict(original=captured[0],reports=reports,providerCalls=0,providerJobId=None,qualification='Real fire_shot and sealing; reviewer findings injected'))


def test_compiler_only_refresh_does_not_regenerate_direction_or_touch_media(world, monkeypatch):
    """Use the actual preparation route; fail if refresh reaches any network call."""
    from copy import deepcopy
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: pytest.fail('Network forbidden'))
    providers, root, path = world
    pkg = json.loads(path.read_text())
    bind_typed_native_fixture(pkg, monkeypatch)
    _approve_specialist_inputs(pkg)
    path.write_text(json.dumps(pkg))
    _approve_scene_look(root, pkg)
    _sign_specialist_inputs(pkg)
    path.write_text(json.dumps(pkg))
    sid = pkg['shots'][0]['shotId']
    monkeypatch.setattr(R, 'screen_keyframe_conformance', lambda *a, **k:
        dict(status='pass', reason=None, review=dict(verdict='pass', summary='Synthetic opening')))
    for shot in pkg['shots']:
        if shot.get('dialogueLines'):
            R.regen_voice_shot('9', shot['shotId'], 'EpT', log=lambda *a: None)
            R.approve_voice('9', shot['shotId'], 'EpT', reviewed_by='Test', log=lambda *a: None)
    R.keyframe_shot('9', sid, 'EpT', log=lambda *a: None)
    R.select_keyframe_candidate('9', sid, 'A', 'EpT', log=lambda *a: None)
    monkeypatch.setattr(cb_llm, 'structured_with_repair', lambda *a, **k:
        dict(verdict='READY', summary='Synthetic SEE', camera='supported', geography='supported',
             pose='supported', propsEffects='supported', actionFeasibility='supported',
             findings=[], correctiveAction='none'))
    R.approve_keyframe('9', sid, 'EpT', reviewed_by='Test', log=lambda *a: None)
    _approve_animation_direction(sid)
    pkg, _ = R.load_pkg('9', 'EpT')
    work, _ = R._department_container(pkg, '9', sid, 'animation', 'EpT')
    original = deepcopy(work.get('candidate') or work.get('approved'))
    # Represent an already prepared source with older derived compiler bytes.
    work['candidate'] = deepcopy(original)
    work['candidate']['output']['providerPrompt'] += '\n\nOld presentation.'
    ledger = R._ledger(pkg, sid)
    ledger['pendingSpendAuth'] = {'token': 'synthetic-stale-request'}
    protected = {k: deepcopy(ledger.get(k)) for k in ('keyframeApproval', 'voiceApproval', 'approvedTake')}
    R._save(pkg, path)
    updated = R.prepare_department('9', 'animation', sid, 'EpT', log=lambda *a: None)
    assert updated['output'] == original['output']
    assert updated['recompileKind'] == 'same signed direction; new derived prompt'
    current, _ = R.load_pkg('9', 'EpT')
    after = R._ledger(current, sid)
    assert after['pendingSpendAuth'] is None
    assert protected == {k: after.get(k) for k in protected}
    assert not providers.fire_calls

    # Agent/editor visual corrections must use the same schema, compiler and
    # guards, without calling the provider or changing media approval records.
    from studio_director_handoff import save_native_animation_direction
    signature = R._department_input_signature(current, 'animation', sid, '9', 'EpT')
    authored = deepcopy(updated['output'])
    authored['providerPrompt'] = 'This uncompiled text must never reach the provider.'
    # The historic fixture predates the generation-design handoff requirement.
    # Supply its actual approved source so the real contract guard stays enabled.
    current_shot = R._shot(current, sid)
    authored['creativeTranslation']['generationDesign']['handoffState'] = current_shot['visualPayoff']
    for field, value, match in [
        ('durationSec', 30, 'duration'),
        ('audioContract', 'A different performance', 'audio contract'),
        ('timeline', [{'channel': 'dialogue', 'performer': 'Unapproved speaker',
                       'event': 'New words', 'startSec': 0, 'endSec': 1}], 'dialogue timeline')]:
        bad = deepcopy(authored); bad[field] = value
        with pytest.raises(ValueError, match=match):
            save_native_animation_direction(R, '9', sid, 'EpT', bad,
                expected_input_signature=signature, author='Fixture editor')
    with pytest.raises(ValueError, match='inputs changed'):
        save_native_animation_direction(R, '9', sid, 'EpT', authored,
            expected_input_signature={'stale': True}, author='Fixture editor')
    edited = save_native_animation_direction(R, '9', sid, 'EpT', authored,
        expected_input_signature=signature, author='Fixture editor')
    assert edited['output']['providerPrompt'] == updated['output']['providerPrompt']
    assert edited['editedBy'] == 'Fixture editor'
    final, _ = R.load_pkg('9', 'EpT')
    final_ledger = R._ledger(final, sid)
    assert protected == {k: final_ledger.get(k) for k in protected}
    assert not providers.fire_calls
