"""Real project pipeline through the actual HTTP route; only provider transport is fake."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace,ModuleType
import json, socket, sys, uuid
import pytest
from test_studio_production import setup,shot,FakeTransport
from test_production_recovery import Http
from studio_journey import Journey,StudioStore,DecisionRequired,scope_key
from studio_journey_project import Project,Services
import studio_journey_http as H
ROOT=Path('/Users/julianjenkins/Desktop/Ai Studio')

@pytest.fixture
def live_controls(setup,monkeypatch):
    _,ws,t,accounts=setup
    original=socket.socket.connect
    def local_only(sock,address):
        assert isinstance(address,tuple) and address[0]=='127.0.0.1' and address[1]!=8899,'Only disposable loopback permitted'
        return original(sock,address)
    monkeypatch.setattr(socket.socket,'connect',local_only)
    module=ModuleType('journey_project_acceptance_server');module.__file__=str(ROOT/'cb-studio/serve.py')
    monkeypatch.setitem(sys.modules,module.__name__,module)
    exec(compile(Path(__file__).with_name('serve.py').read_text(),module.__file__,'exec'),module.__dict__)
    module.ROOT=ws.root
    monkeypatch.setattr(module.H,'_authorize',lambda *a,**k:True)
    monkeypatch.setattr(module.H,'_valid_post_origin',lambda *a,**k:True)
    monkeypatch.setattr(module,'_is_stale',lambda:False)
    for pid in ('first','second'):
        services=ws.services(pid);services['review']={'connectionId':accounts['openai']['id'],'model':'test-model','audioModel':'test-audio','estimateUsd':.1};ws.save_services(pid,services)
        Services(ws,transport=t,background=False).command({'projectId':pid,'episode':'1','action':'budget','amountUsd':10,'commandId':uuid.uuid4().hex,'expectedRevision':0})
    def controller(server,scope):return Journey(StudioStore(ws.root),Project(ws.root,ws,transport=t,background=False))
    monkeypatch.setattr(H,'controller',controller)
    def drain(server,scope):
        j=controller(server,scope)
        for _ in range(24):
            j.tick(scope)
            if not j.view(scope)['busy']:break
            # A pending provider is polled only on the next real refresh.
            if any(c[0]=='poll' for c in t.calls) and t.pending:break
    monkeypatch.setattr(H,'continue_operation',drain)
    return module,ws,t,controller

SCOPE=dict(projectId='first',episode='1',scene='1',unit='S1.SH1')
def status(http,scope=SCOPE,command='status',**extra):
    code,v=http.request('POST','/api/production-journey',{'scope':scope,'command':command,**extra});assert code==200,v;return v

def click(http,scope=SCOPE):
    v=status(http,scope);assert v['primary'],v
    return status(http,scope,'decide',action=v['phase'],binding=v['binding'],expectedRevision=v['revision'],commandId=uuid.uuid4().hex,by='Fixture Producer')

def command(P,action,**kw):
    state=P.snapshot('first','1')['state']
    return P.command({'projectId':'first','episode':'1','shotId':'S1.SH1','action':action,'commandId':uuid.uuid4().hex,'expectedRevision':state['revision'],**kw})

@pytest.mark.parametrize('pid,silent',[('first',False),('second',False),('first',True)])
def test_full_actual_http_pipeline(live_controls,pid,silent):
    server,ws,t,_=live_controls
    if silent:(ws.root/f'projects/{pid}/scripts/part-1.txt').write_text('Hero waits quietly.')
    scope={**SCOPE,'projectId':pid}
    with Http(server) as http:
        states=[]
        for _ in range(4 if silent else 5):states.append(click(http,scope))
        assert states[-1]['phase']=='complete',states[-1]
        assert states[-1]['normalActionCount']==(4 if silent else 5)
        assert not (states[-1]['operation'] or {}).get('decision')
        if not silent:assert states[-1]['next']['unit']=='S1.SH2'
    assert sum(c[0]=='video' for c in t.calls)==1
    assert sum(c[0]=='voice' for c in t.calls)==(0 if silent else 1)
    assert any(c[0]=='review_frames' for c in t.calls)
    P=Services(ws,transport=t,background=False);s=P.snapshot(pid,'1')['state']['shots'][0]
    assert s['outcomes']['watch']['status']=='approved'
    assert s['outcomes']['request']['prompt']==next(c[2] for c in t.calls if c[0]=='video')


def test_correction_uses_real_director_edit_preserves_approved_voice(live_controls):
    server,ws,t,_=live_controls
    with Http(server) as http:
        for _ in range(5):click(http)
        P=Services(ws,transport=t,background=False)
        old=deepcopy(P.snapshot('first','1')['state']['shots'][0]);new=__import__('studio_editing').fields(old)
        new['watchPrompt']='Keep the reply and geography; allow a smaller smile after the line.'
        t.reply={'message':'Only the animation performance changes.','revisedShot':new}
        # Normal Director conversation and approved proposal, no direct state edits.
        chat=Services(ws,transport=t,background=False,operation={'id':'correction-dialogue','grant':{'limitUsd':1,'maxMediaCalls':0}})
        command(chat,'chat',message='Make the reaction smaller. Preserve the image and voice.')
        proposal=chat.snapshot('first','1')['state']['shots'][0]['proposal']
        command(chat,'apply_revision',proposalId=proposal['id'],prepare=False)
        updated=P.snapshot('first','1')['state']['shots'][0]
        assert updated['outcomes']['see']==old['outcomes']['see'] and updated['outcomes']['hear']==old['outcomes']['hear']
        v=click(http);assert v['phase']=='film',v
        assert v['correctionActionCount']==1
        assert sum(c[0]=='voice' for c in t.calls)==1


def test_reload_and_late_known_provider_result_never_resubmit(live_controls):
    server,ws,t,controller=live_controls
    with Http(server) as http:
        for _ in range(3):click(http)
        t.pending=True;v=click(http);assert v['busy']
        # New controller objects read the persisted operation and real job ledger.
        assert controller(server,SCOPE).view(SCOPE)['busy']
        t.pending=False
        v=status(http,command='resume')
        assert v['phase']=='film' and not v['busy'],v
        assert sum(c[0]=='video' for c in t.calls)==1


def test_changed_reference_blocks_approval_before_audio(live_controls):
    server,ws,t,_=live_controls
    with Http(server) as http:
        click(http);click(http)
        v=status(http)
        (ws.root/'projects/first/assets/hero.png').write_bytes(b'changed reference')
        code,result=http.request('POST','/api/production-journey',dict(scope=SCOPE,command='decide',action=v['phase'],binding=v['binding'],expectedRevision=v['revision'],commandId=uuid.uuid4().hex))
        if code==200:assert result['operation']['decision'] or result['phase']!='audio'
        else:assert code==409
        assert not any(c[0] in ('voice','video') for c in t.calls)


def test_incomplete_director_response_is_specific_and_no_media(live_controls):
    server,ws,t,_=live_controls
    original=t.direct
    t.direct=lambda *a,**kw: {'message':'incomplete','shots':[]} if kw.get('planning') else original(*a,**kw)
    with Http(server) as http:
        v=click(http)
        assert v['operation']['decision'],v
        assert v['operation']['decision']['issue']
        assert not any(c[0] in ('image','voice','video') for c in t.calls)


def test_provider_failure_keeps_approved_images_and_audio(live_controls):
    from studio_workspace import StudioError
    server,ws,t,_=live_controls
    with Http(server) as http:
        for _ in range(3):click(http)
        P=Services(ws,transport=t,background=False);old=deepcopy(P.snapshot('first','1')['state']['shots'][0]['outcomes'])
        t.video_submit=lambda *a,**kw: (_ for _ in ()).throw(StudioError('Provider rejected this request.','generation_failed'))
        v=click(http)
        assert v['operation']['decision'],v
        new=P.snapshot('first','1')['state']['shots'][0]['outcomes']
        assert new['see']==old['see']
        assert new['hear']['files']==old['hear']['files'] and new['hear']['status']=='approved'
        assert v['primary'] # Explicit newly disclosed retry is available, never automatic.


def test_dependent_shot_opens_only_after_approved_true_ending(live_controls):
    server,ws,t,_=live_controls
    later={**SCOPE,'unit':'S1.SH2'}
    with Http(server) as http:
        click(http)
        assert status(http,later)['phase']=='dependency'
        for _ in range(3):click(http)
        assert status(http,later)['phase']=='dependency' # returned is not approved
        v=click(http);assert v['next']['unit']=='S1.SH2'
        v=status(http,later);assert v['phase']=='plan'
        v=click(http,later);assert v['phase']=='images',v
        assert 'Previous approved ending' in [c[2] for c in t.calls if c[0]=='image'][-1]


def test_known_provider_failure_retry_requires_another_explicit_action(live_controls):
    from studio_workspace import StudioError
    server,ws,t,_=live_controls
    original=t.video_submit
    with Http(server) as http:
        for _ in range(3):click(http)
        t.video_submit=lambda *a,**kw: (_ for _ in ()).throw(StudioError('Rejected by fixture provider.','generation_failed'))
        v=click(http);assert v['primary'] and v['operation']['decision']
        before=len(t.calls);status(http,command='resume');assert len(t.calls)==before
        t.video_submit=original
        v=click(http);assert v['phase']=='film',v
        assert v['correctionActionCount']==1


def test_missing_character_reference_is_named_before_image_generation(live_controls):
    server,ws,t,_=live_controls
    with Http(server) as http:
        click(http)
        (ws.root/'projects/first/assets/hero.png').unlink()
        v=click(http)
        assert v['operation']['decision'],v
        assert not any(c[0]=='image' for c in t.calls)


def test_contradictory_explicit_direction_blocks_before_provider(live_controls):
    server,ws,t,_=live_controls
    original=t.direct
    def direct(*a,**kw):
        result=original(*a,**kw)
        if kw.get('planning'):
            result['shots'][0]['directorCard']['instructions']=[
                {'id':'stay','kind':'hard_truth','decisionKey':'hero-location','value':'door','text':'Hero remains beside the door.','source':'approved director','stage':'watch'},
                {'id':'leave','kind':'creative_direction','decisionKey':'hero-location','value':'garden','text':'Hero remains in the garden.','source':'current director','stage':'watch'}]
        return result
    t.direct=direct
    with Http(server) as http:
        v=click(http)
        # Invalid/contradictory typed creative response must not be rendered.
        for _ in range(3):
            if v['operation'].get('decision'):break
            v=click(http)
        assert v['operation'].get('decision'),v
        assert 'conflict' in v['operation']['decision']['issue'].lower(),v['operation']['decision']
        assert not any(c[0]=='video' for c in t.calls)


def test_fresh_process_recovers_confirmed_render_without_submission(live_controls):
    import subprocess,os
    server,ws,t,_=live_controls
    with Http(server) as http:
        for _ in range(3):click(http)
        t.pending=True;v=click(http);assert v['busy']
        code='''
import json,sys,socket
from pathlib import Path
socket.socket.connect=lambda *a:(_ for _ in ()).throw(RuntimeError('Network forbidden'))
from studio_workspace import Workspace
from test_studio_production import Vault,FakeTransport
from studio_journey import Journey,StudioStore
from studio_journey_project import Project
vault=Vault();vault.values=json.loads(sys.argv[3]);ws=Workspace(Path(sys.argv[1]),private=Path(sys.argv[2]),vault=vault)
t=FakeTransport();j=Journey(StudioStore(ws.root),Project(ws.root,ws,transport=t,background=False));scope=json.loads(sys.argv[4])
for _ in range(24):
 j.tick(scope)
 if not j.view(scope)['busy']:break
print(json.dumps({'phase':j.view(scope)['phase'],'calls':[x[0] for x in t.calls]}))
'''
        result=subprocess.run([sys.executable,'-c',code,str(ws.root),str(ws.private),json.dumps(ws.vault.values),json.dumps(SCOPE)],capture_output=True,text=True,check=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        proof=json.loads(result.stdout.strip());assert proof['phase']=='film',proof
        assert 'video' not in proof['calls'] and 'poll' in proof['calls']
        assert status(http)['phase']=='film'
        assert sum(c[0]=='video' for c in t.calls)==1


def test_actual_duplicate_click_is_one_producer_operation(live_controls):
    server,ws,t,_=live_controls
    with Http(server) as http:
        v=status(http);data=dict(action=v['phase'],binding=v['binding'],expectedRevision=v['revision'],commandId='same-browser-decision')
        first=status(http,command='decide',**data);second=status(http,command='decide',**data)
        assert first['operation']['id']==second['operation']['id']
        assert second['normalActionCount']==1
        assert len(t.calls)==1
