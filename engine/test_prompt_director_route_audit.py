"""No-network qualification: real project commands, injected reviewer and media transport.
These prove plumbing and refusal behaviour, NOT semantic model detection accuracy.
"""
import copy,json,os,socket
from pathlib import Path
import pytest
from test_studio_production import setup, command, approve
from test_studio_prompt_director import review
from studio_workspace import StudioError

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket,'connect',lambda *a,**k:pytest.fail('Network forbidden in audit'))

def save(name,data):
    folder=os.environ.get('STUDIO_AUDIT_OUTPUT')
    if folder:
        Path(folder).mkdir(parents=True,exist_ok=True)
        (Path(folder)/(name+'.json')).write_text(json.dumps(data,indent=2,default=str))

def prepare(setup,monkeypatch,reply=None):
    p,w,t,_=setup
    original=t.direct
    inputs=[]
    def direct(*args,**kwargs):
        if kwargs.get('schema') and kwargs['schema'].__name__ != 'Assessment':
            inputs.append(copy.deepcopy(args[4]))
            return copy.deepcopy(reply or review())
        return original(*args,**kwargs)
    monkeypatch.setattr(t,'direct',direct)
    command(p,'budget',amountUsd=5)
    approve(p,'see');approve(p,'hear')
    return p,w,t,inputs

def test_ready_command_to_fake_transport_and_return_link(setup,monkeypatch):
    p,w,t,inputs=prepare(setup,monkeypatch)
    before=p.snapshot('first','1')['state']['shots'][0]
    request=before['outcomes']['request']
    assert request['promptDirector']['verdict']=='READY TO FIRE'
    snapshot = request['promptDirectorSnapshot']
    line = snapshot['authorities']['shot']['dialogueLines'][0]
    measured = before['outcomes']['hear']['voiceTiming']['lines'][0]
    assert (line['speaker'], line['exactText'], line['startSec'], line['endSec']) == ('Hero', 'Hello.', measured['startSec'], measured['endSec'])
    assert request['prompt'].count('{Hello.}') == 1
    assert 'Hero: 0.15–0.85s.' in request['prompt']
    assert '[Audio]\n@Audio1 is the approved voice performance. Match its exact words, speaker timing and lip sync. No extra dialogue.' in request['prompt']
    assert 'Measured dialogue ownership' not in request['prompt'] and '"startSec"' not in request['prompt']
    from studio_prompt_director import project_authorities, request_snapshot, verify
    reconstructed = request_snapshot(request['prompt'], project_authorities(p.ws.context('first', '1'), before, request['source']), request['images'], request['audio'], request['duration'], request['binding'])
    verify(reconstructed, request['promptDirector'])
    assert not any(c[0]=='video' for c in t.calls)
    approve(p,'request')
    state=p.snapshot('first','1')['state'];watch=state['shots'][0]['outcomes']['watch']
    assert watch['promptDirector']['payloadHash']==request['promptDirector']['payloadHash']
    assert next(c[2] for c in t.calls if c[0]=='video')==request['prompt']
    assert watch['status']=='candidate'
    from studio_media_review import manifest
    context=p.ws.context('first','1')
    linked=manifest(p,context,state,state['shots'][0])
    assert linked['promptDirector']['payloadHash']==request['promptDirector']['payloadHash']
    save('ready-route',dict(before=inputs[0],request=request,returned=watch,reviewManifest=linked,transport='fake; zero network'))

@pytest.mark.parametrize('case,values',[
 ('attachment',{'attachment':'attached'}),('mechanism',{'condition':'upright'}),
 ('location',{'location':'zone A'}),('effect',{'mark':'clean'})])
def test_obsolete_opening_blocks_command_and_no_task(setup,monkeypatch,case,values):
    p,w,t,_=setup
    original=t.direct
    def direct(*args,**kwargs):
        if kwargs.get('schema') and kwargs['schema'].__name__ != 'Assessment':
            result=review()
            result['lifecycle']=[dict(entity='one-object',view='same moment',at=1,values=[dict(field=k,value=v)],cause='approved state',source='fixture') for k,v in values.items()]
            result['lifecycle'] += [dict(entity='one-object',view='same moment',at=1,values=[dict(field=k,value='incompatible state')],cause='obsolete reference reset',source='fixture') for k in values]
            return result
        return original(*args,**kwargs)
    monkeypatch.setattr(t,'direct',direct)
    command(p,'budget',amountUsd=5);approve(p,'see');approve(p,'hear')
    state=p.snapshot('first','1')['state'];request=state['shots'][0]['outcomes']['request']
    assert request['status']=='blocked'
    with pytest.raises(StudioError):approve(p,'request')
    assert not any(c[0]=='video' for c in t.calls)
    jobs=p.snapshot('first','1')['jobs'];assert not any(j.get('taskId') for j in jobs)
    save(case+'-blocked-route',dict(request=request,jobs=jobs,providerCalls=0,providerJobId=None,qualification='Injected contradictory state report, not pixel detection'))

def test_authority_amendment_refuses_old_request_without_media_mutation(setup,monkeypatch):
    p,w,t,inputs=prepare(setup,monkeypatch)
    state=p.snapshot('first','1')['state'];original=copy.deepcopy(state['shots'][0]);old=original['outcomes']['request']
    with w.db() as db:
        s=p._load(db,'first','1');s['shots'][0]['camera']='Hold on the listener while the prop moves.'
        s['shots'][0]['directorCard']['views'][0]['framing'] = s['shots'][0]['camera']
        p._save(db,'first','1',s)
    approve(p,'request')  # follow-up Fire errors are recorded by the command orchestrator
    assert not any(c[0]=='video' for c in t.calls)
    changed=p.snapshot('first','1')['state']['shots'][0]
    assert changed['outcomes']['see']==original['outcomes']['see']
    assert changed['outcomes']['hear']==original['outcomes']['hear']
    command(p,'request',shotId='S1.SH1')
    new=p.snapshot('first','1')['state']['shots'][0]['outcomes']['request']
    assert 'Hold on the listener while the prop moves.' in new['prompt']
    assert new['promptDirector']['payloadHash']!=old['promptDirector']['payloadHash']
    save('revision-route',dict(old=old,new=new,providerCalls=0,approvedAssetsUnchanged=True,amendment='Real persisted authority mutation; editing UI not exercised'))

@pytest.mark.parametrize('visible',[True,False])
def test_laugh_overlap_and_hold_survive_actual_request_route(setup,monkeypatch,visible):
    p,w,t,_=setup
    from PIL import Image
    base = w.root / 'projects' / 'first'
    Image.new('RGB', (24, 24), 'green').save(base / 'assets' / 'b.png')
    characters = json.loads((base / 'characters.json').read_text())
    characters['B'] = {'anchor': 'projects/first/assets/b.png', 'voiceId': 'voice987654321012'}
    (base / 'characters.json').write_text(json.dumps(characters))
    command(p,'budget',amountUsd=5);approve(p,'see')
    with w.db() as db:
        state=p._load(db,'first','1');s=state['shots'][0]
        s['characters'].append('B')
        s['camera']='Hold on Hero: restraint is the audience beat.'
        s['directorCard']['views'][0]['framing'] = s['camera']
        s['watchPrompt']='B laughs nonverbally from 0.2 to 0.8 seconds during Hero dialogue. B is '+('visible; allow natural laugh-related mouth and body movement.' if visible else 'offscreen; keep the camera on Hero.')+' No new intelligible speech.'
        view = s['directorCard']['views'][0]
        view['performance'] += ' ' + s['watchPrompt']
        view['visibleEntities'] = ['character:Hero'] + (['character:B'] if visible else [])
        s['directorCard']['soundCues'] = [dict(kind='character-sfx', character='B', instruction='B laughs nonverbally. No new intelligible speech.', timing='0.2–0.8s', destination='watch')]
        s['directorCard']['soundOwnership'] = 'Preserve exact Hero speech from HEAR; generate the authored nonverbal B laugh only.'
        p._save(db,'first','1',state)
    approve(p,'hear')
    s=p.snapshot('first','1')['state']['shots'][0];request=s['outcomes']['request']
    assert request['status']=='candidate'
    assert 'B @Image3 laughs nonverbally' in request['prompt']
    assert 'Hold on Hero @Image2' in request['prompt']
    assert 'No new intelligible speech.' in request['prompt']
    assert 'B remains still' not in request['prompt'] and 'B must keep mouth closed' not in request['prompt']
    assert request['audio']
    save('laugh-'+str(visible),dict(request=request,providerCalls=0,limitation='Reviewer injected READY; no pixel or listening qualification; production compiler defaults exercised as present'))

def test_new_speech_conflict_blocks_real_request(setup,monkeypatch):
    p,w,t,_=setup
    original=t.direct
    def direct(*args,**kwargs):
        if kwargs.get('schema') and kwargs['schema'].__name__ != 'Assessment':
            result=review();result['findings']=[dict(category='true audio conflict',reason='New intelligible B speech conflicts with immutable approved dialogue.',evidence='B says an unapproved new line over Hero.',correction='Resolve with director; do not silently rewrite.')];return result
        return original(*args,**kwargs)
    monkeypatch.setattr(t,'direct',direct)
    command(p,'budget',amountUsd=5);approve(p,'see')
    with w.db() as db:
        state=p._load(db,'first','1');state['shots'][0]['directorCard']['views'][0]['action']='B says an unapproved new line over Hero.';p._save(db,'first','1',state)
    approve(p,'hear');request=p.snapshot('first','1')['state']['shots'][0]['outcomes']['request']
    assert request['status']=='blocked'
    with pytest.raises(StudioError):approve(p,'request')
    assert not any(c[0]=='video' for c in t.calls)
    assert 'B says an unapproved new line over Hero.' in request['prompt']
    save('audio-conflict',dict(request=request,providerCalls=0,providerJobId=None))
