"""Observed evidence, recovery boundaries and isolation for the next workspace pass."""
import copy
import json
import uuid
import wave
from unittest.mock import Mock

from PIL import Image
import pytest

from studio_production import Production
from studio_references import suggestions, resolve
from studio_transport import ProviderTransport
from studio_workspace import StudioError
from test_studio_production import setup, command, approve
from test_studio_review import finish, timeline_command


def configure(p, ws, accounts):
    ws.save_services('first', {**ws.services('first'), 'review': {
        'connectionId': accounts['openai']['id'], 'model': 'test-vision', 'audioModel': 'test-audio', 'estimateUsd': .2}})


def render_candidate(p):
    command(p, 'budget', amountUsd=10)
    for stage in ('see', 'hear', 'request'):
        approve(p, stage)


def review(p, sid='S1.SH1', **extra):
    shot = next(s for s in p.snapshot('first','1')['state']['shots'] if s['id'] == sid)
    return command(p, 'media_review', shotId=sid, reviewId=shot['outcomes']['watch']['id'], **extra)


def test_suggestions_only_use_verified_approved_earlier_same_scene_sources(setup):
    p,ws,t,_=setup;command(p,'budget',amountUsd=10)
    state=p.snapshot('first','1')['state'];context=ws.context('first','1')
    assert not suggestions(p,context,state,state['shots'][1])  # candidate is not approved
    approve(p,'see');state=p.snapshot('first','1')['state']
    choices=suggestions(p,context,state,state['shots'][1])
    assert [r['choice']['role'] for r in choices]==['camera setup','scene geography']
    assert not suggestions(p,context,state,state['shots'][0])  # cannot look forwards
    state['shots'][1]['scene']=2
    assert not suggestions(p,context,state,state['shots'][1])
    state['shots'][1]['scene']=1;state['shots'][1]['cameraSetupId']='a-new-reverse'
    assert all(r['choice']['role']!='camera setup' for r in suggestions(p,context,state,state['shots'][1]))
    ws.project_path('first',choices[0]['path']).write_bytes(b'changed')
    assert not suggestions(p,context,state,state['shots'][1])


def test_reference_choice_is_previewed_then_reaches_real_generation_inputs(setup):
    p,ws,t,_=setup;finish(p)
    before=p.snapshot('first','1')['state'];other=copy.deepcopy(before['shots'][0]);voice=before['shots'][1]['outcomes']['hear']
    choice=p.snapshot('first','1')['review']['inspections']['S1.SH2']['suggestions'][0]['choice']
    command(p,'choose_reference',shotId='S1.SH2',reference=choice)
    shot=p.snapshot('first','1')['state']['shots'][1]
    assert shot['outcomes']==before['shots'][1]['outcomes']
    assert 'hear' in shot['proposal']['impact']['preserved']
    command(p,'apply_revision',shotId=shot['id'],proposalId=shot['proposal']['id'],prepare=True)
    state=p.snapshot('first','1')['state']
    assert state['shots'][0]==other
    assert state['shots'][1]['outcomes']['hear']==voice
    assert any(r.get('sourceShotId')=='S1.SH1' and r['version']==choice['candidateId'] for r in state['shots'][1]['outcomes']['see']['references'])
    assert 'S1.SH1 approved camera setup' in [c[2] for c in t.calls if c[0]=='image'][-1]


def test_stale_or_cross_project_reference_choice_cannot_be_applied(setup):
    p,ws,t,_=setup;finish(p)
    choice=p.snapshot('first','1')['review']['inspections']['S1.SH2']['suggestions'][0]['choice']
    command(p,'choose_reference',shotId='S1.SH2',reference=choice)
    shot=p.snapshot('first','1')['state']['shots'][1]
    with ws.db() as db:
        state=p._load(db,'first','1');state['shots'][0]['outcomes']['see']['id']='replacement';p._save(db,'first','1',state)
    with pytest.raises(StudioError,match='reference changed'):
        command(p,'apply_revision',shotId=shot['id'],proposalId=shot['proposal']['id'])
    assert p.snapshot('first','1')['state']['shots'][1]['outcomes']['watch']['status']=='approved'
    command(p,'budget',pid='second',amountUsd=2)
    with pytest.raises(StudioError):command(p,'choose_reference',pid='second',shotId='S1.SH1',reference=choice)


def test_real_media_reaches_review_without_mutating_approvals_or_other_projects(setup):
    p,ws,t,accounts=setup;configure(p,ws,accounts);render_candidate(p)
    before=p.snapshot('first','1')['state'];result=review(p)
    state=p.snapshot('first','1')['state'];report=state['shots'][0]['mediaReviews'][0]
    assert state['shots'][0]['outcomes']==before['shots'][0]['outcomes']
    assert state['shots'][1]==before['shots'][1]
    assert state['budget']['committed']-before['budget']['committed']==200000
    assert state['budget']['reserved']==0
    assert len(report['evidence']['frames'])==10 and len(report['evidence']['audio'])==2
    visual=next(c[2] for c in t.calls if c[0]=='review_frames')
    assert len(visual['images'])==11  # all ten frames of the 5 fps fixture, plus approved SEE
    with Image.open(visual['images'][0][1]) as sample:
        r,g,b=sample.getpixel((0,0));assert b>200 and r<10 and g<10
    audio=next(c[2]['audio'] for c in t.calls if c[0]=='review_audio')
    with wave.open(str(audio[0][1])) as file:assert file.getnframes()>0
    assert p.snapshot('first','1')['review']['inspections']['S1.SH1']['mediaReviews'][0]['current']
    assert not p.snapshot('second','1')['state']['shots']
    with pytest.raises(StudioError,match='already has'):review(p)
    with ws.db() as db:
        job=json.loads(db.execute('SELECT data FROM jobs WHERE id=?',(result['jobId'],)).fetchone()[0])
    assert job['status']=='completed' and job['progress']['phase']=='completed'


def test_review_is_optional_scoped_and_budgeted_before_any_provider_call(setup):
    p,ws,t,accounts=setup;render_candidate(p)
    with pytest.raises(StudioError,match='review connection'):review(p)
    configure(p,ws,accounts)
    with ws.db() as db:
        state=p._load(db,'first','1');state['budget']['allowance']=state['budget']['committed'];p._save(db,'first','1',state)
    with pytest.raises(StudioError) as error:review(p)
    assert error.value.code=='budget_required'
    assert not any(c[0].startswith('review_') for c in t.calls)


def test_review_currentness_tracks_version_and_actual_file_integrity(setup):
    p,ws,t,accounts=setup;configure(p,ws,accounts);render_candidate(p);review(p)
    before=p.snapshot('first','1')['state']['shots'][0]['mediaReviews'][0]
    approve(p,'watch')  # approval alone does not stale a candidate's report
    assert p.snapshot('first','1')['review']['inspections']['S1.SH1']['mediaReviews'][0]['current']
    file=p.snapshot('first','1')['state']['shots'][0]['outcomes']['watch']['files'][0]
    ws.project_path('first',file['path']).write_bytes(b'tampered')
    current=p.snapshot('first','1')
    assert not current['review']['inspections']['S1.SH1']['mediaReviews'][0]['current']
    assert current['state']['shots'][0]['mediaReviews'][0]==before


def test_review_samples_the_incoming_approved_shot(setup):
    p,ws,t,accounts=setup;configure(p,ws,accounts);finish(p);review(p,'S1.SH2')
    report=p.snapshot('first','1')['state']['shots'][1]['mediaReviews'][0]
    assert len(report['evidence']['frames'])==14
    assert len(report['evidence']['joins']) == 1
    assert any('S1.SH1' in f['label'] for f in report['evidence']['frames'])


def test_unknown_review_submission_is_not_retried_and_partial_audio_is_saved(setup):
    p,ws,t,accounts=setup;configure(p,ws,accounts);render_candidate(p)
    original=t.review_frames
    def fail(*args,**kwargs):
        t.error=StudioError('Uncertain visual response','submission_unknown')
        return original(*args,**kwargs)
    t.review_frames=fail
    result=review(p);current=p.snapshot('first','1')
    assert current['jobs'][0]['status']=='failed' and current['jobs'][0]['audioReview']
    assert current['state']['budget']['reserved']==0
    count=len(t.calls)
    with pytest.raises(StudioError,match='closed'):command(p,'resume',jobId=result['jobId'])
    assert len(t.calls)==count
    assert not current['state']['shots'][0].get('mediaReviews')
    t.error=None
    approve(p,'watch')
    assert p.snapshot('first','1')['state']['shots'][1]['outcomes']['see']['status']=='candidate'


def test_interrupted_incomplete_review_can_close_without_blocking_production(setup):
    p,ws,t,accounts=setup;configure(p,ws,accounts);render_candidate(p)
    launch=p.launch;p.launch=lambda job:None
    result=review(p);p.launch=launch
    before=len(t.calls)
    with ws.db() as db:
        job=json.loads(db.execute('SELECT data FROM jobs WHERE id=?',(result['jobId'],)).fetchone()[0]);job.update(status='running',pid=-1,reviewSubmitted=True);p._job(db,job)
    command(p,'resume',jobId=result['jobId'])
    current=p.snapshot('first','1')
    assert current['jobs'][0]['status']=='failed' and current['state']['budget']['reserved']==0
    assert len(t.calls)==before


def test_saved_complete_review_recovers_after_restart_without_repeat_spend(setup):
    p,ws,t,accounts=setup;configure(p,ws,accounts);render_candidate(p)
    complete=p.complete;p.complete=lambda *args:None
    result=review(p);p.complete=complete
    calls=len(t.calls)
    with ws.db() as db:
        job=json.loads(db.execute('SELECT data FROM jobs WHERE id=?',(result['jobId'],)).fetchone()[0]);job['pid']=-1;p._job(db,job)
    assert p.snapshot('first','1')['jobs'][0]['status']=='interrupted'
    command(p,'resume',jobId=result['jobId'])
    assert len(t.calls)==calls
    assert len(p.snapshot('first','1')['state']['shots'][0]['mediaReviews'])==1


def test_assembly_progress_is_observed_and_does_not_increment_approval_revision(setup):
    p,ws,t,_=setup;finish(p)
    before=p.snapshot('first','1')['state']['revision']
    result=timeline_command(p,'assemble_cut')
    assert p.snapshot('first','1')['state']['revision']==before+2  # command and completion; progress is not an edit
    with ws.db() as db:
        job=json.loads(db.execute('SELECT data FROM jobs WHERE id=?',(result['jobId'],)).fetchone()[0])
    events=job['progressEvents']
    assert [v['completed'] for v in events if v['phase']=='normalise']==[0,1,1,2]
    assert all('percent' not in event for event in events)
    assert {'sources','normalise','assemble','verify'} <= {event['phase'] for event in events}


def test_audio_adapter_sends_actual_wav_bytes_and_requests_only_text(setup):
    p,ws,t,_=setup;render_candidate(p)
    source=ws.project_path('first',p.snapshot('first','1')['state']['shots'][0]['outcomes']['hear']['files'][0]['path'])
    response=Mock();response.json.return_value={'choices':[{'finish_reason':'stop','message':{'content':'A quiet pause.'}}]}
    transport=ProviderTransport();transport.request=Mock(return_value=response)
    assert transport.review_audio({'provider':'openai'},'test-key','audio-model',{},[('Approved voice',source)])=='A quiet pause.'
    body=transport.request.call_args.kwargs['body']
    import base64
    part=body['messages'][1]['content'][-1]
    assert base64.b64decode(part['input_audio']['data'])==source.read_bytes()
    assert body['modalities']==['text'] and body['store'] is False


def test_silent_render_is_not_claimed_as_listened_to(setup):
    p,ws,t,accounts=setup;configure(p,ws,accounts)
    ws.project_path('first','projects/first/scripts/part-1.txt').write_text('Hero waits.')
    command(p,'budget',amountUsd=10);approve(p,'see');approve(p,'request');review(p)
    report=p.snapshot('first','1')['state']['shots'][0]['mediaReviews'][0]
    assert not report['evidence']['watchHasAudio'] and not report['evidence']['audio']
    assert not any(c[0]=='review_audio' for c in t.calls)
    assert 'No listening request' in report['audioReview']


def test_source_changed_during_review_is_historical_and_cost_is_settled_once(setup):
    p,ws,t,accounts=setup;configure(p,ws,accounts);render_candidate(p)
    old=t.review_frames
    record=p.snapshot('first','1')['state']['shots'][0]['outcomes']['watch']['files'][0]
    def change(*args,**kwargs):
        result=old(*args,**kwargs);ws.project_path('first',record['path']).write_bytes(b'changed');return result
    t.review_frames=change;before=p.snapshot('first','1')['state']['budget']['committed']
    result=review(p);current=p.snapshot('first','1')
    report=current['review']['inspections']['S1.SH1']['mediaReviews'][0]
    assert not report['current'] and report['sourceIntegrity']=='changed_during_review'
    assert current['state']['budget']['committed']==before+200000 and current['state']['budget']['reserved']==0
    command(p,'resume',jobId=result['jobId'])
    assert p.snapshot('first','1')['state']['budget']==current['state']['budget']


def test_new_reference_version_does_not_block_previously_approved_downstream_media(setup):
    p,ws,t,_=setup;finish(p)
    choice=p.snapshot('first','1')['review']['inspections']['S1.SH2']['suggestions'][0]['choice']
    with ws.db() as db:
        state=p._load(db,'first','1');state['shots'][1]['compositionReference']=choice
        state['shots'][0]['outcomes']['see']['id']='newer-source-version';p._save(db,'first','1',state)
    snapshot=p.snapshot('first','1')
    issues=snapshot['review']['inspections']['S1.SH2']['issues']
    assert any(i['code']=='reference_changed' and i['severity']=='warning' for i in issues)
    assert not any(i['severity']=='blocker' for i in issues)
    assert snapshot['review']['summary']['assemblyReady']
    assert snapshot['state']['shots'][1]['outcomes']['watch']['status']=='approved'
