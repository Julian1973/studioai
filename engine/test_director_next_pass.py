"""Route checks use synthetic reviewer outputs; socket connections forbidden."""
import json,socket
import pytest
import cb_render as R,cb_llm
from test_current_production_path import world,isolated_canon
from test_studio_prompt_director import review
from test_studio_production import setup,command,approve

@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(socket.socket,'connect',lambda *a,**k:pytest.fail('Network forbidden'))

def test_targeted_edit_blocked_before_token_or_transport(world,monkeypatch):
    providers,root,path=world
    pkg=json.loads(path.read_text());shot=pkg['shots'][0];led=R._ledger(pkg,shot['shotId'])
    source=root/'source.mp4';source.write_bytes(b'synthetic')
    led.update(status='approved',approvedTake=str(source));path.write_text(json.dumps(pkg))
    def reject(system,text,schema,**kw):
        data=json.loads(text);assert data['authorities']['editScope']['outsideWindow']=='preserve approved source'
        out=review();out['findings']=[dict(category='story/state contradiction',reason='Edit resets moved object outside scope',evidence=data['prompt'].splitlines()[0],correction='Keep outside-window state')];return out
    monkeypatch.setattr(cb_llm,'structured_with_repair',reject)
    with pytest.raises((R.Refused,ValueError),match='BLOCKED'):
        R.edit_shot('9',shot['shotId'],'Restore the old position.',0,1,'EpT',log=lambda *a:None)
    assert not providers.fire_calls
    records=[json.loads(p.read_text()) for p in (root/'cb-output/state/preflight-attempts').glob('*.json')]
    assert records and records[-1]['mediaProviderCalled'] is False
    current=json.loads(path.read_text());assert not R._ledger(current,shot['shotId']).get('pendingEditSpendAuth')

def test_early_exception_durable_complete(world):
    _,root,_=world
    with pytest.raises(Exception):R.fire_shot('9','missing-shot','EpT')
    report=json.loads(next((root/'cb-output/state/preflight-attempts').glob('*.json')).read_text())
    assert all(k in report for k in ('reason','revision','packageHash','sourceBindings','correctiveAction','mediaProviderCalled','mediaSpendOccurred'))
    assert report['mediaProviderCalled'] is False and report['mediaSpendOccurred'] is False
    assert report['providerCallOccurred'] is False and report['spendOccurred'] is False

def test_unsuitable_see_blocks_project_watch_request(setup,monkeypatch):
    p,w,t,_=setup;original=t.direct
    def direct(*args,**kwargs):
        result=original(*args,**kwargs)
        if kwargs.get('schema') and kwargs['schema'].__name__=='Assessment':
            result.update(verdict='BLOCKED',summary='Launch path is occluded',correctiveAction='Restage the opening camera')
        return result
    monkeypatch.setattr(t,'direct',direct)
    command(p,'budget',amountUsd=5);approve(p,'see');approve(p,'hear')
    snapshot=p.snapshot('first','1')
    assert not any(c[0]=='video' for c in t.calls)
    assert not snapshot['state']['shots'][0]['outcomes'].get('request')
    assert any(j.get('keyframeDirector',{}).get('verdict')=='BLOCKED' for j in snapshot['jobs'])
    assert list((w.root/'cb-output/state/preflight-attempts').glob('*.json'))

def test_origin_is_sealed_batch_not_current_direction():
    envelope={'directorCardRevision':{'revision':3},'executionPlan':{'segments':[{'promptDirector':{'lifecycle':['original expectation']},'promptDirectorSnapshot':{'authorities':{'revision':3}},'references':['original ref']}]}}
    ledger={'batch':{'envelope':envelope,'envelopeHash':'sealed'},'currentDirection':'changed'}
    origin=R._returned_origin(ledger)
    assert origin['segments'][0]['promptDirector']['lifecycle']==['original expectation']
    assert origin['reviewScope']['deliveryEligible'] is False


def test_legacy_returned_review_receives_originating_plan(world,monkeypatch):
    _,root,path=world
    pkg=json.loads(path.read_text());shot=pkg['shots'][0];led=R._ledger(pkg,shot['shotId'])
    media=root/'take.mp4';media.write_bytes(b'synthetic-take');ref=root/'origin.png';ref.write_bytes(b'origin-ref')
    report={'payloadHash':'original','audienceBeat':'surprise','lifecycle':[{'entity':'prop','state':'landed'}]}
    led.update(status='candidates-pending',candidatePaths=[str(media)],batch={'envelopeHash':'sealed','envelope':{'directorCardRevision':{'revision':1},'executionPlan':{'segments':[{'promptDirector':report,'promptDirectorSnapshot':{'revision':1},'references':[{'path':str(ref),'role':'prop','md5':R._file_md5(str(ref))}]}]}}})
    path.write_text(json.dumps(pkg))
    monkeypatch.setattr(R,'_anchor_for',lambda *a:None)
    monkeypatch.setattr(R,'_provider_attachment_plan',lambda *a:[])
    def frames(*a):
        folder=root/'samples';folder.mkdir(exist_ok=True);frame=folder/'sample.png';frame.write_bytes(b'sample');return str(folder),[str(frame)]
    monkeypatch.setattr(R,'_review_frames',frames)
    seen=[]
    monkeypatch.setattr(R.cb_departments,'review_media',lambda stage,context,images,**kw:seen.append(context) or {'summary':'Synthetic observations','verdict':'pass'})
    R.prepare_department('9','review-animation',shot['shotId'],'EpT',log=lambda *a:None)
    assert seen[0]['originatingProduction']['segments'][0]['promptDirector']==report
    assert seen[0]['orderedReviewImages'][-1]['path']==str(ref)
    saved=json.loads(path.read_text());candidate=R._ledger(saved,shot['shotId'])['departmentWork']['review-animation']['candidate']
    assert candidate['originatingProduction']['reviewScope']['audioLipSync'].startswith('unverified')
    assert candidate['originatingProduction']['segments'][0]['sourceSnapshot']=={'revision':1}
