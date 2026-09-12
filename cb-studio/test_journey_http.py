"""Actual HTTP decision route + native adapter/worker; synthetic native service fixtures.
Real native compiler/control qualification lives in test_journey_native_controls.py.
No connection to the live Studio or external networks is permitted.
"""
import importlib.util
import os
import subprocess
import wave
import json
from pathlib import Path
import socket
import sys
import types
import pytest

ROOT=Path('/Users/julianjenkins/Desktop/Ai Studio')
sys.path[:0]=[str(Path(__file__).parent),str(ROOT/'engine'),str(ROOT/'cb-studio')]
from test_production_recovery import Http
from studio_journey import Journey, StudioStore, scope_key, digest, DecisionRequired
from studio_journey_native import Native, read
import studio_journey_http as H
import studio_journey_worker as W

@pytest.fixture
def fixture(tmp_path,monkeypatch):
    original_connect=socket.socket.connect
    def local_only(sock,address):
        assert isinstance(address,tuple) and address[0]=='127.0.0.1' and address[1]!=8899,'External/live network forbidden'
        return original_connect(sock,address)
    monkeypatch.setattr(socket.socket,'connect',local_only)
    # Execute the modified REAL server source; keep imports at their normal location.
    module=types.ModuleType('journey_actual_server');module.__file__=str(ROOT/'cb-studio/serve.py')
    monkeypatch.setitem(sys.modules,module.__name__,module)
    exec(compile(Path(__file__).with_name('serve.py').read_text(),module.__file__,'exec'),module.__dict__)
    module.ROOT=tmp_path
    monkeypatch.setattr(module.H,'_authorize',lambda *a,**k:True)
    monkeypatch.setattr(module.H,'_valid_post_origin',lambda *a,**k:True)
    monkeypatch.setattr(module,'_is_stale',lambda:False)
    import cb_episode_budget
    monkeypatch.setattr(cb_episode_budget,'status',lambda ep:{'remainingUsd':10})
    media=tmp_path/'engine/media/shots';media.mkdir(parents=True)
    calls=[]
    import cb_intake
    monkeypatch.setattr(cb_intake,'scene_roster',lambda ep:{'scenes':[]})
    class Render:
        def load(self,sc,ep):
            p=tmp_path/'cb-output'/f'{ep}_scene{sc}_production_package.json';return json.loads(p.read_text()),p
        def save(self,pkg,path):path.write_text(json.dumps(pkg))
        def scenelook_status(self,*a):return {'current':True}
        def shot_reference_manifest(self,*a):return {'keyframe':{'references':[]}, 'animation':{'references':[]}}
        def _keyframe_record_status(self,*a):return {'current':True}
        def _voice_approval_status(self,pkg,shot,*a):return {'current':not shot['dialogueLines'] or bool(pkg['continuityLedger'][0].get('voiceApproval'))}
        def _anchor_for(self,pkg,shot):return pkg['continuityLedger'][0]['keyframeApproval']['path']
        def approve_keyframe(self,sc,unit,ep,**kw):
            p,f=self.load(sc,ep);l=p['continuityLedger'][0];l['keyframeApproval']={**l.pop('keyframeCandidate'),'approved':True};calls.append('approve-image');self.save(p,f)
        def approve_voice(self,sc,unit,ep,**kw):
            p,f=self.load(sc,ep);l=p['continuityLedger'][0];l['voiceApproval']={'approved':True,'path':l['voPath']};calls.append('approve-audio');self.save(p,f)
        def fire_shot(self,sc,unit,ep,**kw):
            p,f=self.load(sc,ep);l=p['continuityLedger'][0];a=l['pendingSpendAuth'];assert kw['spend_token']==a['token'];calls.append(('submit',a['envelope']['prompt']));
            v=media/f'{unit}.mp4';v.write_bytes(b'fixture-video');
            if os.environ.get('BROWSER_DEMO'):
                subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=0x47405f:s=960x540:r=24','-t','1','-c:v','libx264','-pix_fmt','yuv420p','-y',str(v)],check=True)
            l.update(status='candidates-pending',candidatePaths=[str(v)],batch={'envelope':a['envelope'],'envelopeHash':a['envelopeHash']},pendingSpendAuth=None);self.save(p,f)
        def _returned_origin(self,led):return {'originIntegrity':{'verified':bool(led.get('batch',{}).get('envelopeHash'))}}
        def prepare_department(self,*a):calls.append('review-originating-film')
        def approve_shot(self,sc,unit,episode,**kw):
            p,f=self.load(sc,episode);l=p['continuityLedger'][0];end=media/f'{unit}-ending.png';end.write_bytes(b'ending');l.update(status='approved',approvedTake=l['candidatePaths'][0],harvestFrame=str(end));calls.append('approve-film');self.save(p,f)
        def stitch_scene(self,*a):calls.append('assembly')
    R=Render()
    class Director:
        def build_keyframe(self,sc,unit,ep):
            p,f=R.load(sc,ep);image=media/f'{unit}.png';image.write_bytes(b'fixture-image');
            if os.environ.get('BROWSER_DEMO'):
                from PIL import Image,ImageDraw
                canvas=Image.new('RGB',(960,540),'#47405f');ImageDraw.Draw(canvas).text((40,220),'OFFLINE WORKFLOW FIXTURE — NOT A PRODUCTION IMAGE',fill='white');canvas.save(image)
            p['continuityLedger'][0]['keyframeCandidate']={'path':str(image),'conformanceScreening':{'status':'unverified'}};calls.append('image');R.save(p,f)
        def build_voice(self,sc,unit,ep):
            p,f=R.load(sc,ep);audio=media/f'{unit}.wav';audio.write_bytes(b'fixture-audio');cues=media/f'{unit}-cues.json';cues.write_text('{}');p['continuityLedger'][0].update(voPath=str(audio),voTimingPath=str(cues));calls.append('voice');R.save(p,f)
        def prepare_render(self,sc,unit,ep):
            p,f=R.load(sc,ep);env={'prompt':p['shots'][0]['purpose']};calls.append(('review',env['prompt']));p['continuityLedger'][0]['pendingSpendAuth']={'token':'fixture-only','envelope':env,'envelopeHash':digest(env),'disclosure':{'maxBatchCostUsd':.5}};R.save(p,f)
    D=Director();module._canonical_cb_render=lambda:R
    def approve(data):
        p=tmp_path/'cb-output/creative'/f"{data['episode']}_scene{data['scene']}_storyboard.json";b=json.loads(p.read_text());b['approvalState']='approved';b['approvalLog']=[{'by':data['by'],'state':'approved'}];p.write_text(json.dumps(b));calls.append('approve-plan')
    module._storyboard_approval=approve
    def start(job,gate,sc,args):
        key,op_id,step=args[-3:];state=StudioStore(tmp_path).read(key);op=state['operation']
        result=W.perform(tmp_path,state['scope'],step,op,R,D)
        import cb_db
        cb_db.atomic_write_json(tmp_path,tmp_path/'cb-output/state/journeys'/f'{op_id}_{step}.json',{**result,'operationId':op_id,'step':step})
        return job
    module._start=start
    monkeypatch.setattr(H,'controller',lambda server,scope:Journey(StudioStore(tmp_path),Native(tmp_path,module)))
    def drain(server,scope):
        j=H.controller(server,scope)
        for _ in range(25):
            j.tick(scope)
            if not j.view(scope)['busy']:break
    monkeypatch.setattr(H,'continue_operation',drain)
    import cb_post
    monkeypatch.setattr(cb_post,'_dur',lambda p:4)
    def setup(sc=1,silent=False):
        scope={'projectId':'crystal-bears','episode':'Ep3','scene':str(sc),'unit':f'S{sc}.SH1'}
        p=tmp_path/'cb-output'/f'Ep3_scene{sc}_production_package.json';p.parent.mkdir(exist_ok=True)
        shot={'shotId':scope['unit'],'purpose':'A distinct audience beat '+str(sc),'durationSec':4,'dialogueLines':[] if silent else [{'speaker':'Hero','exactText':'Hello.','text':'Hello.'}]}
        p.write_text(json.dumps({'shots':[shot],'continuityLedger':[{'shotId':scope['unit'],'status':'designed'}]}))
        board=tmp_path/'cb-output/creative'/f'Ep3_scene{sc}_storyboard.json';board.parent.mkdir(exist_ok=True)
        prepared={'scene':{'title':'Scene '+str(sc)},'shots':[{**shot,'internalShotPlan':[{'viewId':scope['unit']+'.V1','storyAction':shot['purpose'],'framingAndCamera':'Medium held view'}]}],'approvalState':'candidate'}
        import cb_creative
        monkeypatch.setattr(cb_creative,'run_scene',lambda *a:board.write_text(json.dumps(prepared)))
        return scope,p,board
    return module,setup,calls


def command(http,scope,command_name='status',**kw):
    status,res=http.request('POST','/api/production-journey',{'scope':scope,'command':command_name,**kw})
    assert status==200,res
    return res

@pytest.mark.parametrize('scene,silent',[(1,False),(2,False),(3,True)])
def test_actual_route_native_steps(fixture,scene,silent):
    server,setup,calls=fixture;scope,p,board=setup(scene,silent)
    with Http(server) as http:
        v=command(http,scope);assert v['primary']=='Prepare Scene'
        clicks=0
        while v['phase']!='complete' and clicks<5:
            v=command(http,scope,'decide',action=v['phase'],binding=v['binding'],expectedRevision=v['revision'],commandId='decision'+str(clicks),by='Test Producer');clicks+=1
            assert not v.get('operation',{}).get('decision'),v
        # Authored scene plan was already prepared (Action 1 reusable).
        assert clicks==(4 if silent else 5)
        assert v['normalActionCount']==clicks and v['phase']=='complete'
    reviewed=[x[1] for x in calls if isinstance(x,tuple) and x[0]=='review']
    submitted=[x[1] for x in calls if isinstance(x,tuple) and x[0]=='submit']
    assert reviewed==submitted and len(submitted)==1
    assert ('voice' in calls)==(not silent)
    assert 'review-originating-film' in calls and 'assembly' in calls


def test_http_stale_binding_has_no_dispatch(fixture):
    server,setup,calls=fixture;scope,p,board=setup()
    with Http(server) as http:
        v=command(http,scope);b={'scene':{'title':'New plan'},'shots':[{'purpose':'initial'}]};b['shots'][0]['purpose']='A different beat';board.write_text(json.dumps(b))
        code,res=http.request('POST','/api/production-journey',{'scope':scope,'command':'decide','action':'plan','binding':v['binding'],'expectedRevision':v['revision'],'commandId':'stale1234'})
        assert code==409 and 'changed' in res['error']
    assert calls==[]


def test_group_images_validated_before_either_approval(fixture):
    server,setup,calls=fixture;scope,p,board=setup()
    with Http(server) as http:
        v=command(http,scope)
        for n in range(2):v=command(http,scope,'decide',action=v['phase'],binding=v['binding'],expectedRevision=v['revision'],commandId='groupdec'+str(n))
        j=H.controller(server,scope)
        j.accept(scope,dict(commandId='groupstart',action=v['phase'],binding=v['binding'],expectedRevision=v['revision']),'Producer')
        # Simulate a genuine concurrent image overwrite after the reviewed decision.
        image=Path(v['review']['images'][0]['path']);image.write_bytes(b'new image bytes')
        j.tick(scope)
        assert j.view(scope)['operation']['decision']['issue']=='Opening image changed after your review.'
        assert 'approve-image' not in calls and 'voice' not in calls


def test_interrupted_plan_cannot_inherit_older_same_actor_approval(fixture):
    server,setup,calls=fixture;scope,p,board=setup()
    board.write_text(json.dumps({'approvalState':'approved','approvalLog':[{'by':'Producer','state':'approved','note':'earlier decision'}]}))
    with pytest.raises(DecisionRequired,match='interrupted'):
        Native(server.ROOT,server).reconcile(scope,'approve_plan',{'id':'new-operation','actor':'Producer'})


@pytest.mark.parametrize('matching',[True,False])
def test_native_late_return_requires_original_sealed_envelope(fixture,matching):
    server,setup,calls=fixture;scope,path,_=setup()
    pkg=json.loads(path.read_text());ledger=pkg['continuityLedger'][0]
    ledger.update(status='candidates-pending',candidatePaths=['returned.mp4'],batch={'envelopeHash':'original' if matching else 'different'})
    path.write_text(json.dumps(pkg))
    import cb_db
    receipt=server.ROOT/'cb-output/state/journeys/op-recovery_submit_render.json'
    cb_db.atomic_write_json(server.ROOT,receipt,{'operationId':'op-recovery','step':'submit_render','decision':{'issue':'Prior timeout','proposed':'Reconcile original task'}})
    op={'id':'op-recovery','review':{'lineage':{}},'receipts':{'prepare_render':{'envelopeHash':'original'}}}
    if matching:
        assert Native(server.ROOT,server).reconcile(scope,'submit_render',op)['status']=='complete'
    else:
        with pytest.raises(DecisionRequired,match='Prior timeout'):Native(server.ROOT,server).reconcile(scope,'submit_render',op)
    assert calls==[]


def test_missing_native_coverage_blocks_before_plan_approval_or_image(fixture):
    server,setup,calls=fixture;scope,path,board=setup()
    board.write_text(json.dumps({'shots':[{'shotId':scope['unit'],'purpose':'Incomplete direction'}]}))
    prior=json.loads(path.read_text());prior['shots'][0]['directorCard']={'views':[{'viewId':'old-view','action':'Older approved staging'}]};path.write_text(json.dumps(prior))
    adapter=Native(server.ROOT,server);_,b,_,_=read(server.ROOT,scope)
    with pytest.raises(DecisionRequired,match='no camera coverage'):
        adapter.execute(scope,'approve_plan',{'id':'missing-coverage','actor':'Producer','review':{'boardHash':digest(b)}})
    assert calls==[]
    assert not json.loads(board.read_text()).get('approvalState')
