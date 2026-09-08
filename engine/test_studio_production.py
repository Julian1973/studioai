"""Provider calls are fake; production transactions and media checks are real."""
import copy
import json
from pathlib import Path
import subprocess
import uuid
import wave

from PIL import Image
import pytest

from studio_workspace import Workspace, StudioError, NativeVault
from studio_production import Production, money
from studio_transport import ProviderTransport


class Vault:
    def __init__(self): self.values = {}
    def put(self, account, secret): self.values[account] = secret
    def get(self, account): return self.values[account]


def shot(index, line):
    return {"id": f"S1.SH{index}", "scene": 1, "startLine": index, "endLine": index,
            "title": "A thought before the answer", "emotion": "Uncertainty becomes trust", "performance": "Listen, hesitate, then answer.",
            "camera": "Eye-level medium reverse", "geography": "Hero stays screen left; door remains behind.",
            "transition": "cut", "duration": 4, "characters": ["Hero"], "location": "", "props": [],
            "dialogue": [{"speaker": "Hero", "text": line.split(': ', 1)[1], "delivery":"neutral"}] if ': ' in line else [],
            "seePrompt": "Hero hesitates by the door.", "watchPrompt": "A quiet hesitation before the smile."}


class FakeTransport(ProviderTransport):
    def __init__(self): self.calls=[]; self.reply=None; self.error=None; self.pending=False
    def direct(self, connection, key, model, system, context, *, planning=False, images=None):
        self.calls.append(("direction",key,context))
        if self.error: raise self.error
        if planning:
            return {"message":"Prepared from your script.","shots":[shot(i,line) for i,line in context['scriptLines']]}
        return copy.deepcopy(self.reply or {"message":"The selected shot keeps its geography.","revisedShot":None})
    def image(self, connection, key, model, prompt, references, output, *, received=None):
        self.calls.append(("image",key,prompt))
        if self.error: raise self.error
        Image.new('RGB',(32,18),'blue').save(output)
    def voice(self, connection, key, model, dialogue, output):
        self.calls.append(("voice",key,dialogue))
        with wave.open(str(output),'wb') as file:
            file.setnchannels(1);file.setsampwidth(2);file.setframerate(8000);file.writeframes(b'\0\0'*8000)
    def video_submit(self, connection, key, model, prompt, images, audio, duration, *, ratio="16:9"):
        self.calls.append(("video",key,prompt))
        if self.error: raise self.error
        return 'provider-task-1'
    def video_poll(self, connection, key, task_id, output, *, progress=None):
        self.calls.append(("poll",key,task_id))
        if progress: progress('provider', 'Provider reports the render is running' if self.pending else 'Provider reports completion; downloading and verifying the render')
        if self.pending: return False
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=32x18:r=5','-t','2','-c:v','libx264','-pix_fmt','yuv420p','-y',str(output)],check=True,capture_output=True)
        return True

    def review_audio(self, connection, key, model, context, audio):
        self.calls.append(('review_audio', key, {'context':context, 'audio':audio}))
        if self.error: raise self.error
        return 'Test audio evidence: the attached soundtrack contains silence. Listen before deciding.'

    def review_frames(self, connection, key, model, context, images):
        self.calls.append(('review_frames', key, {'context':context, 'images':images}))
        if self.error: raise self.error
        return {'summary':'Test review of supplied render frames.', 'findings':[{
            'seconds':.5, 'category':'composition', 'observation':'The supplied test frames are blue.',
            'suggestion':'Review the opening composition.', 'confidence':'high'}],
            'limitations':['Synthetic provider response for workflow testing.']}


@pytest.fixture
def setup(tmp_path):
    root=tmp_path/'studio';root.mkdir()
    (root/'cb-studio/data').mkdir(parents=True)
    projects=[]
    for pid in ('first','second'):
        base=root/'projects'/pid
        (base/'scripts').mkdir(parents=True);(base/'media').mkdir();(base/'assets').mkdir()
        Image.new('RGB',(24,24),'red').save(base/'assets/hero.png')
        meta={"id":pid,"name":pid.title(),"setupVersion":1,"configBase":f'projects/{pid}',"style":pid+' style'}
        projects.append(meta)
        (base/'show_bible.md').write_text(pid+' world only')
        (base/'characters.json').write_text(json.dumps({'Hero':{'anchor':f'projects/{pid}/assets/hero.png','voiceId':'voice123456789012'}}))
        (base/'locations.json').write_text('[]');(base/'props.json').write_text('[]')
        (base/'scripts/part-1.txt').write_text('Hero: Hello.\nHero: Come home.')
        (base/'episodes.json').write_text(json.dumps([{'number':1,'title':'Opening','script':'scripts/part-1.txt'}]))
    (root/'cb-studio/data/projects.json').write_text(json.dumps({'projects':projects}))
    vault=Vault();ws=Workspace(root,private=tmp_path/'private',vault=vault)
    accounts={}
    for provider in ('openai','byteplus','elevenlabs'):
        accounts[provider]=ws.save_connection({'provider':provider,'key':provider+'-test-secret-value'})
    for pid in ('first','second'):
        ws.save_services(pid,{role:{'connectionId':accounts[provider]['id'],'model':model,'estimateUsd':.1} for role,provider,model in [
            ('direction','openai','test-model'),('keyframes','byteplus','test-image'),('voices','elevenlabs','eleven_v3'),('animation','byteplus','dreamina-seedance-2-5-260628')]})
    transport=FakeTransport();production=Production(ws,transport=transport,background=False)
    return production,ws,transport,accounts


def command(p,action,pid='first',ep='1',**extra):
    snapshot=p.snapshot(pid,ep)
    return p.command({'projectId':pid,'episode':ep,'action':action,'commandId':uuid.uuid4().hex,'expectedRevision':snapshot['state']['revision'],**extra})


def approve(p,stage,via_chat=False):
    item=p.snapshot('first','1')['state']['shots'][0]['outcomes'][stage]
    return command(p,'chat' if via_chat else 'approve',shotId='S1.SH1',reviewId=item['id'],message='approve' if via_chat else '')


def test_budget_prepares_directed_shots_and_see_without_approving(setup):
    p,ws,t,_=setup
    command(p,'budget',amountUsd=2)
    state=p.snapshot('first','1')['state']
    assert len(state['shots'])==2
    assert state['shots'][0]['outcomes']['see']['status']=='candidate'
    assert not state['shots'][1]['outcomes']
    assert state['budget']['committed']==200000 and state['budget']['reserved']==0
    prompt=next(c[2] for c in t.calls if c[0]=='image')
    assert 'first world only' in prompt and 'second world only' not in prompt
    assert 'Eye-level medium reverse' in prompt and 'Listen, hesitate' in prompt
    assert p.snapshot('second','1')['state']['shots']==[]


@pytest.mark.parametrize('via_chat',[False,True])
def test_see_hear_request_render_approvals_use_one_pipeline(setup,via_chat):
    p,ws,t,_=setup
    command(p,'budget',amountUsd=5)
    approve(p,'see',via_chat)
    state=p.snapshot('first','1')['state']; assert state['shots'][0]['outcomes']['hear']['status']=='candidate'
    approve(p,'hear',via_chat)
    state=p.snapshot('first','1')['state'];request=state['shots'][0]['outcomes']['request']
    assert request['status']=='candidate' and 'Hero: Hello.' in request['source']
    assert not any(c[0]=='video' for c in t.calls)
    approve(p,'request',via_chat)
    state=p.snapshot('first','1')['state'];render=state['shots'][0]['outcomes']['watch']
    assert render['status']=='candidate'
    assert render['audioAuthority']['source']['hash']==state['shots'][0]['outcomes']['hear']['files'][0]['hash']
    assert ws.project_path('first',render['files'][0]['path']).is_file()
    approve(p,'watch',via_chat)
    state=p.snapshot('first','1')['state']
    assert state['shots'][0]['outcomes']['watch']['status']=='approved'
    assert state['shots'][1]['outcomes']['see']['status']=='candidate'
    assert 'Previous approved ending' in [c[2] for c in t.calls if c[0]=='image'][-1]


def test_stale_approval_and_other_project_candidate_cannot_approve(setup):
    p,ws,t,_=setup
    command(p,'budget',amountUsd=3)
    before=p.snapshot('first','1')['state']
    candidate=before['shots'][0]['outcomes']['see']
    command(p,'status')
    with pytest.raises(StudioError,match='another window'):
        p.command({'projectId':'first','episode':'1','commandId':'stale','action':'approve','expectedRevision':before['revision'],'shotId':'S1.SH1','reviewId':candidate['id']})
    command(p,'budget',pid='second',amountUsd=3)
    with pytest.raises(StudioError,match='current candidate'):
        command(p,'approve',pid='second',shotId='S1.SH1',reviewId=candidate['id'])
    assert len([c for c in t.calls if c[0]=='voice'])==0


def test_tampered_file_cannot_be_approved(setup):
    p,ws,t,_=setup;command(p,'budget',amountUsd=3)
    item=p.snapshot('first','1')['state']['shots'][0]['outcomes']['see']
    ws.project_path('first',item['files'][0]['path']).write_bytes(b'changed')
    with pytest.raises(StudioError,match='changed or is missing'):approve(p,'see')


def test_revision_reaches_prompts_preserves_voice_and_other_shots(setup):
    p,ws,t,_=setup;command(p,'budget',amountUsd=4);approve(p,'see');approve(p,'hear')
    state=p.snapshot('first','1')['state'];old=state['shots'][0];other=copy.deepcopy(state['shots'][1])
    updated={k:copy.deepcopy(old[k]) for k in shot(1,'Hero: Hello.')}
    updated['performance']='Wait, inhale, then answer with a fragile smile.'
    updated['seePrompt']='A fragile smile after hesitation.'
    t.reply={'message':'The reaction now hesitates.','revisedShot':updated}
    command(p,'chat',shotId='S1.SH1',message='Make the reaction more hesitant. Keep the voice and geography.')
    preview=p.snapshot('first','1')['state']['shots'][0]
    assert preview['performance']==old['performance'] and preview['outcomes']==old['outcomes']
    command(p,'apply_revision',shotId='S1.SH1',proposalId=preview['proposal']['id'],prepare=True)
    state=p.snapshot('first','1')['state'];new=state['shots'][0]
    assert new['performance']==updated['performance']
    assert new['outcomes']['hear']==old['outcomes']['hear']
    assert new['outcomes']['see']['id'] != old['outcomes']['see']['id'] and 'request' not in new['outcomes']
    assert {k:v for k,v in state['shots'][1].items() if k!='continuityReview'}==other
    command(p,'continue',shotId='S1.SH1')
    assert updated['performance'] in [c[2] for c in t.calls if c[0]=='image'][-1]


def test_duplicate_command_does_not_duplicate_spend(setup):
    p,ws,t,_=setup
    payload={'projectId':'first','episode':'1','action':'budget','commandId':'same','expectedRevision':0,'amountUsd':2}
    first=p.command(payload);before=len(t.calls);second=p.command(payload)
    assert first==second and len(t.calls)==before


def test_budget_denial_and_missing_service_never_fall_back_to_env(setup,monkeypatch):
    p,ws,t,_=setup;monkeypatch.setenv('OPENAI_API_KEY','global-account-do-not-use')
    ws.save_services('first',{})
    command(p,'budget',amountUsd=2)
    assert not t.calls
    assert 'direction connection' in p.snapshot('first','1')['state']['messages'][-1]['text']
    with pytest.raises(StudioError,match='allowance'):command(p,'prepare',pid='second')
    assert not t.calls


def test_rotation_pins_running_video_to_original_account(setup):
    p,ws,t,accounts=setup;command(p,'budget',amountUsd=3);approve(p,'see');approve(p,'hear')
    t.pending=True;approve(p,'request')
    job=p.snapshot('first','1')['jobs'][0]; assert job['status']=='pending'
    ws.save_connection({'id':accounts['byteplus']['id'],'provider':'byteplus','key':'brand-new-account-key'})
    t.pending=False
    command(p,'resume',jobId=job['id'])
    assert len([c for c in t.calls if c[0]=='video'])==1
    assert [c[1] for c in t.calls if c[0]=='poll']==['byteplus-test-secret-value']*2
    assert p.snapshot('first','1')['jobs'][0]['status']=='completed'


def test_uncertain_submission_blocks_duplicates_until_user_reconciles(setup):
    p,ws,t,_=setup;t.error=StudioError('Check the provider account.','submission_unknown')
    command(p,'budget',amountUsd=3)
    state=p.snapshot('first','1');job=state['jobs'][0]
    assert job['status']=='unknown' and state['state']['budget']['reserved']==100000
    with pytest.raises(StudioError,match='in progress'):command(p,'prepare')
    with pytest.raises(StudioError,match='Check the uncertain'):command(p,'reconcile',jobId=job['id'])
    command(p,'reconcile',jobId=job['id'],providerChecked=True)
    assert p.snapshot('first','1')['state']['budget']['committed']==100000
    t.error=None;command(p,'prepare')
    assert p.snapshot('first','1')['state']['shots']


def test_keys_are_absent_from_database_context_history_and_responses(setup):
    p,ws,t,_=setup;command(p,'budget',amountUsd=2)
    public=json.dumps([ws.connections(),p.snapshot('first','1')])
    with ws.db() as db: dump='\n'.join(db.iterdump())
    for secret in ws.vault.values.values():
        assert secret not in public and secret not in dump
    with pytest.raises(StudioError,match='Workspace connections'):
        command(p,'chat',message='my key is sk-this_is_a_secret_key_do_not_store')


def test_new_episode_does_not_stale_existing_episode_and_traversal_is_rejected(setup):
    p,ws,t,_=setup;before=ws.context('first','1')['sourceHash']
    episodes=ws.root/'projects/first/episodes.json'
    episodes.write_text(json.dumps(json.loads(episodes.read_text())+[{'number':2,'script':'scripts/part-2.txt'}]))
    assert ws.context('first','1')['sourceHash']==before
    with pytest.raises(StudioError):ws.project_path('first','projects/second/assets/hero.png')
    outside=ws.root/'projects/first/assets/escape.png';outside.symlink_to(ws.root/'projects/second/assets/hero.png')
    with pytest.raises(StudioError):ws.project_path('first','projects/first/assets/escape.png')


def test_invalid_script_coverage_and_cast_are_rejected(setup):
    p,ws,t,_=setup;context=ws.context('first','1')
    invalid=shot(1,'Hero: Hello.');invalid['characters']=['Foreign IP']
    with pytest.raises(StudioError,match='outside'):p.validate_shot(context,invalid)
    with pytest.raises(StudioError,match='whole script'):p.validate_plan(context,{'message':'','shots':[shot(1,'Hero: Hello.')]})
    invalid=shot(1,'Hero: invented line')
    with pytest.raises(StudioError,match='dialogue'):p.validate_shot(context,invalid)


@pytest.mark.parametrize('amount',['NaN','Infinity',-1,0,'not money'])
def test_budget_requires_finite_positive_amount(amount):
    with pytest.raises(StudioError):money(amount)


def test_native_vault_rejects_plaintext_backend(monkeypatch,tmp_path):
    import keyring
    monkeypatch.setattr(keyring,'get_keyring',lambda:object())
    with pytest.raises(StudioError,match='credential storage'):NativeVault(tmp_path).backend()


def test_source_refresh_preserves_voice_and_versions(setup):
    p,ws,t,_=setup;command(p,'budget',amountUsd=4);approve(p,'see');approve(p,'hear')
    before=p.snapshot('first','1')['state']['shots'][0]
    (ws.root/'projects/first/show_bible.md').write_text('A changed visual world')
    snapshot=p.snapshot('first','1');assert snapshot['sourceChanged']
    with pytest.raises(StudioError,match='source changed'):command(p,'chat',shotId='S1.SH1',message='Change the lighting')
    command(p,'refresh_sources',sourceHash=snapshot['sourceHash'])
    after=p.snapshot('first','1')['state']['shots'][0]
    assert 'see' not in after['outcomes']
    assert after['outcomes']['hear']==before['outcomes']['hear']
    assert any(v['id']==before['outcomes']['see']['id'] for v in after['versions'])
    assert not p.snapshot('first','1')['sourceChanged']


def test_voice_delivery_revision_preserves_picture(setup):
    p,ws,t,_=setup;command(p,'budget',amountUsd=4);approve(p,'see');approve(p,'hear')
    old=p.snapshot('first','1')['state']['shots'][0]
    revised={k:copy.deepcopy(old[k]) for k in shot(1,'Hero: Hello.')}
    revised['dialogue'][0]['delivery']='whispering'
    t.reply={'message':'A quieter performance.','revisedShot':revised}
    command(p,'chat',shotId='S1.SH1',message='Whisper the line',stage='hear')
    preview=p.snapshot('first','1')['state']['shots'][0]
    assert preview['outcomes']==old['outcomes']
    command(p,'apply_revision',shotId='S1.SH1',proposalId=preview['proposal']['id'],prepare=True)
    new=p.snapshot('first','1')['state']['shots'][0]
    assert new['outcomes']['see']==old['outcomes']['see']
    assert new['outcomes']['hear']['id']!=old['outcomes']['hear']['id']
    assert new['outcomes']['hear']['status']=='candidate'
    assert [c[2] for c in t.calls if c[0]=='voice'][-1][0]['text']=='[whispering] Hello.'


def test_concurrent_duplicate_budget_commands_reserve_once(setup):
    from concurrent.futures import ThreadPoolExecutor
    p,ws,t,_=setup
    payload={'projectId':'first','episode':'1','action':'budget','commandId':'same-concurrent','expectedRevision':0,'amountUsd':3}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:p.command(payload),range(2)))
    assert results[0]==results[1]
    assert len([c for c in t.calls if c[0]=='direction'])==1
    assert len([c for c in t.calls if c[0]=='image'])==1


def test_project_root_cannot_alias_another_project(setup):
    p,ws,t,_=setup
    (ws.root/'projects/alias').symlink_to(ws.root/'projects/second',target_is_directory=True)
    with pytest.raises(StudioError,match='escapes'):ws.project_path('alias','projects/alias/assets/hero.png')


def test_generation_rejections_are_sanitized_and_never_retried(monkeypatch):
    import studio_transport
    calls=[]
    class Response:
        status_code=401
        text='Authorization: raw-key-value'
    def request(*args,**kwargs):calls.append(kwargs);return Response()
    monkeypatch.setattr(studio_transport.requests,'request',request)
    with pytest.raises(StudioError) as error:
        ProviderTransport().request({'provider':'byteplus'},'raw-key-value','/images/generations',body={})
    assert 'raw-key-value' not in str(error.value)
    assert len(calls)==1 and calls[0]['allow_redirects'] is False


def test_download_refuses_private_hosts_without_http(monkeypatch,tmp_path):
    import studio_transport
    monkeypatch.setattr(studio_transport.socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('127.0.0.1',443))])
    with pytest.raises(StudioError,match='private media'):ProviderTransport.download('https://unsafe.example/file.png',tmp_path/'file.png')


def test_library_edits_are_versioned_and_unrelated_assets_do_not_reset_shots(setup):
    p,ws,t,_=setup;command(p,'budget',amountUsd=4)
    before=p.snapshot('first','1')['state']['shots']
    context=ws.context('first')
    ws.update_library({'projectId':'first','sourceHash':context['sourceHash'],'group':'props','name':'Map','notes':'A folded blue map'},lambda raw:(raw.encode(),'.png'))
    assert not p.snapshot('first','1')['sourceChanged']
    command(p,'status')
    assert p.snapshot('first','1')['state']['shots']==before
    assert ws.context('second')['assets']['props']==[]
    with ws.db() as db:
        history=json.loads(db.execute('SELECT data FROM library_versions WHERE project=?',('first',)).fetchone()[0])
    assert history['content']=='[]'
    with pytest.raises(StudioError,match='library changed'):
        ws.update_library({'projectId':'first','sourceHash':context['sourceHash'],'group':'bible','notes':'stale overwrite'},None)


def test_image_recovery_does_not_submit_again(setup):
    p,ws,t,_=setup
    def interrupted(connection,key,model,prompt,references,output,*,received=None):
        t.calls.append(('image',key,prompt));received('https://media.example/output.png')
        raise StudioError('Download interrupted','download_failed')
    t.image=interrupted
    command(p,'budget',amountUsd=2)
    job=p.snapshot('first','1')['jobs'][0];assert job['status']=='pending'
    t.download=lambda url,path:Image.new('RGB',(32,18),'green').save(path)
    command(p,'resume',jobId=job['id'])
    assert len([c for c in t.calls if c[0]=='image'])==1
    assert p.snapshot('first','1')['state']['shots'][0]['outcomes']['see']['status']=='candidate'


def test_completed_job_poll_is_safe_with_a_stale_page_revision(setup):
    p,ws,t,_=setup;command(p,'budget',amountUsd=3)
    job=p.snapshot('first','1')['jobs'][0]
    calls=len(t.calls)
    result=p.command({'projectId':'first','episode':'1','action':'resume','jobId':job['id'],
                      'commandId':'late-poll','expectedRevision':0})
    assert result['ok'] and len(t.calls)==calls
    assert p.snapshot('first','1')['state']['shots'][0]['outcomes']['see']['status']=='candidate'


def test_credit_errors_are_not_misreported_as_bad_keys():
    from studio_transport import provider_error
    error=provider_error(401,'quota_exceeded')
    assert error.code=='balance_required' and 'allowance or credit' in str(error)
