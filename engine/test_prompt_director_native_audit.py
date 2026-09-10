"""Legacy Studio Fire path qualification with synthetic files and no network."""
import json,socket
import pytest
import cb_render as R, cb_llm
from test_current_production_path import world, isolated_canon, _approve_specialist_inputs, _approve_scene_look, _sign_specialist_inputs
from test_golden_path import _approve_animation_direction
from test_studio_prompt_director import review
from test_prompt_director_route_audit import save

@pytest.mark.parametrize('blocked',[True,False])
def test_native_fire_reaches_review_and_obeys_verdict(world,monkeypatch,blocked,tmp_path):
    monkeypatch.setattr(socket.socket,'connect',lambda *a,**k:pytest.fail('Network forbidden'))
    providers,root,path=world
    monkeypatch.setattr(R,'screen_keyframe_conformance',lambda *a,**k:dict(status='pass',reason=None,review=dict(verdict='pass',summary='Synthetic setup, not visually qualified')))
    pkg=json.loads(path.read_text());_approve_specialist_inputs(pkg);path.write_text(json.dumps(pkg))
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
        data=json.loads(text);captured.append(data);result=review()
        if blocked:result['findings']=[dict(category='story/state contradiction',reason='Injected qualification conflict',evidence=data['prompt'].splitlines()[0],correction='Resolve authority conflict')]
        return result
    monkeypatch.setattr(cb_llm,'structured_with_repair',reviewer)
    import studio_prompt_director as pd
    real=pd.review_legacy_envelope
    monkeypatch.setattr(pd,'review_legacy_envelope',lambda *a,**k:real(*a,archive_folder=tmp_path/'reviews'))
    with pytest.raises(R.Refused,match='BLOCKED|SPEND NOT APPROVED'):
        R.fire_shot('9',sid,'EpT',candidates=1,log=lambda *a:None)
    assert captured
    assert not providers.fire_calls
    current,_=R.load_pkg('9','EpT');ledger=R._ledger(current,sid)
    reports=[json.loads(p.read_text()) for p in (tmp_path/'reviews').glob('*.json')]
    if blocked:assert not ledger.get('pendingSpendAuth')
    else:
        sealed=ledger['pendingSpendAuth']['envelope']['executionPlan']['segments'][0]
        assert sealed['promptDirector']['verdict']=='READY TO FIRE'
        assert sealed['prompt'].startswith('[Audience Purpose]')
        assert sealed['prompt'].index('[Audience Purpose]') < sealed['prompt'].index('[Multimodal Reference Layer]')
    save('native-'+('blocked' if blocked else 'ready'),dict(original=captured[0],reports=reports,providerCalls=0,providerJobId=None,qualification='Real fire_shot and sealing; reviewer findings injected'))
