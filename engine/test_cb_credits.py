from pathlib import Path
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

import pytest
import cb_credits as c
import cb_credits_compose as compose
import cb_db

REAL_ROOT=c.ROOT

@pytest.fixture
def studio(tmp_path,monkeypatch):
    monkeypatch.setattr(c,'ROOT',tmp_path)
    canon=tmp_path/'shows/crystal-bears/canon';canon.mkdir(parents=True)
    refs=tmp_path/'cb-seed/assets/final_turnarounds';refs.mkdir(parents=True)
    (refs/'CB_Bo_with_satchel.png').write_bytes(b'approved-reference')
    (canon/'characters.json').write_text(json.dumps({'Bo':{'turnaround':'../cb-seed/assets/final_turnarounds/CB_Bo_with_satchel.png'}}))
    fonts=tmp_path/'cb-studio/assets/fonts';fonts.mkdir(parents=True)
    for name in compose.FONT_FILES:
        shutil.copyfile(REAL_ROOT/'cb-studio/assets/fonts'/name,fonts/name)
    import cb_providers,cb_costs
    monkeypatch.setattr(cb_providers,'request_contract',lambda **kw:{'providerModelId':'dreamina-seedance-2-5-260628','costRateKey':'seedance_25_byteplus_480p_per_sec','endpoint':'/api/v3/contents/generations/tasks'})
    monkeypatch.setattr(cb_costs,'load_billing_profile',lambda _:dict(planConfirmed=True,cadenceConfirmed=True))
    return tmp_path

def test_choices_reject_traversal_unknown_reference_and_invalid_colour(studio):
    cfg=c.defaults('Ep2')
    with pytest.raises(ValueError):c.status('../../engine')
    for change in [{'character':'not approved'},{'background':'red; injected'},{'title':''},{'cards':[]}]:
        with pytest.raises(ValueError):c.prepare('Ep2',{**cfg,**change})
    assert not (studio/'cb-output/credits/Ep2/current.json').exists()

def test_preview_is_silent_bound_to_reference_and_official_fonts(studio):
    result=c.prepare('Ep2',{**c.defaults('Ep2'),'title':"Bo's Big Day"})
    state=c._state('Ep2')
    assert result['status']=='prepared'
    assert state['envelope']['generateAudio'] is False
    assert state['envelope']['candidateCount']==1
    assert state['referenceUrl'].endswith('CB_Bo_with_satchel.png')
    assert (studio/result['previewUrl'].lstrip('/')).is_file()
    assert len(state['envelope']['fonts'])==2
    assert cb_db.spend_authorization(studio,state['token'])['status']=='issued'

def test_reference_change_blocks_spend(studio,monkeypatch):
    result=c.prepare('Ep2',c.defaults('Ep2'))
    (studio/'cb-seed/assets/final_turnarounds/CB_Bo_with_satchel.png').write_bytes(b'changed')
    monkeypatch.setattr(c,'_spawn',lambda *a:pytest.fail('Must not start'))
    with pytest.raises(ValueError,match='changed'):c.fire('Ep2',result['token'])

def test_concurrent_duplicate_clicks_start_one_candidate(studio,monkeypatch):
    result=c.prepare('Ep2',c.defaults('Ep2'));calls=[]
    def spawn(ep,state,*args):
        calls.append(state['id']);state['pid']=99999999
    monkeypatch.setattr(c,'_spawn',spawn)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _:c.fire('Ep2',result['token']),range(2)))
    assert len(calls)==1
    assert cb_db.spend_authorization(studio,result['token'])['status']=='claimed'
    with pytest.raises(ValueError):c.prepare('Ep2',c.defaults('Ep2'))

def test_expired_token_and_review_are_bound_to_current_candidate(studio,monkeypatch):
    old=c.prepare('Ep2',c.defaults('Ep2'));new=c.prepare('Ep2',c.defaults('Ep2'))
    with pytest.raises(ValueError):c.fire('Ep2',old['token'])
    with pytest.raises(ValueError):c.verdict('Ep2',new['id'],True)
    c.update('Ep2',status='awaiting_review',videoUrl='/engine/media/test.mp4')
    assert c.verdict('Ep2',new['id'],True)['humanReview']=='accepted'

def test_recovery_never_resubmits(studio,monkeypatch):
    result=c.prepare('Ep2',c.defaults('Ep2'))
    c.update('Ep2',status='interrupted',providerTaskId='existing-job',pid=99999999)
    calls=[]
    monkeypatch.setattr(c,'_spawn',lambda ep,s,resume:calls.append(resume))
    c.resume('Ep2')
    assert calls==[True]

def test_worker_and_compositor_produce_review_without_auto_approval(studio,monkeypatch):
    if not shutil.which('ffmpeg'):pytest.skip('ffmpeg missing')
    plate=studio/'plate.mp4'
    subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=c=red:s=854x480:r=24:d=30',
                    '-c:v','libx264','-preset','ultrafast',str(plate)],check=True)
    prepared=c.prepare('Ep2',{**c.defaults('Ep2'),'title':"Bo's Big Day"})
    monkeypatch.setattr(c,'_spawn',lambda *args:None)
    c.fire('Ep2',prepared['token'])
    import cb_gen
    def fake_generate(prompt,refs,**kwargs):
        assert kwargs['generate_audio'] is False
        assert kwargs['duration']==30
        assert len(refs)==1
        kwargs['progress_callback']({'event':'submitted','taskId':'mock-provider-job'})
        shutil.copyfile(plate,kwargs['out'])
        return kwargs['out']
    monkeypatch.setattr(cb_gen,'generate_video_seedance_ref',fake_generate)
    c.run_worker('Ep2',prepared['id'])
    state=c.status('Ep2')
    assert state['status']=='awaiting_review'
    assert state['humanReview']=='pending'
    assert cb_db.spend_authorization(studio,prepared['token'])['status']=='completed'
    result=studio/state['videoUrl'].lstrip('/')
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type','-of','json',str(result)]))
    assert float(probe['format']['duration'])==30
    assert [s['codec_type'] for s in probe['streams']]==['video']
