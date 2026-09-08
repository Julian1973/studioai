import copy
import json
import pytest
from test_studio_production import setup, command, approve
from test_studio_review import finish, timeline_command
from studio_workflow import estimate, handoff
from studio_workspace import StudioError


def test_opening_frame_and_motion_are_distinct_but_keep_intent():
    shot={'intent':'comfort','openingState':'left of door','performance':'hesitate then laugh','endingState':'embrace','beatPlan':[{'at':2,'action':'laugh'}]}
    see=handoff(shot,'see',[]);watch=handoff(shot,'watch',[])
    assert 'beatPlan' not in see['direction']
    assert see['performanceContextNotDepicted']['performance']==shot['performance']
    assert watch['direction']['beatPlan']==shot['beatPlan']
    assert see['fingerprint']!=watch['fingerprint']
    assert 'ONE opening instant' in see['instruction']


def test_performance_trace_matches_generated_prompt(setup):
    p,ws,t,_=setup;command(p,'budget',amountUsd=5)
    artifact=p.snapshot('first','1')['state']['shots'][0]['outcomes']['see']
    assert artifact['directionTrace']['fingerprint'] in artifact['prompt']
    assert artifact['directionTrace']['references'][0]['hash']


def test_account_rates_are_forecasts_with_conservative_floor():
    s={'duration':12,'dialogue':[{'text':'a'*1000,'delivery':'neutral'}]*2}
    assert estimate({'estimateUsd':.1,'unitUsd':.2},'watch',s)==2.4
    assert estimate({'estimateUsd':.1,'unitUsd':.2},'hear',s)==.4
    assert estimate({'estimateUsd':3,'unitUsd':.2},'watch',s)==3
    assert estimate(None,'watch',s) is None


def test_account_rate_changes_request_preview_and_reservation(setup):
    p,ws,t,_=setup;services=ws.services('first');services['animation']['unitUsd']=.7;ws.save_services('first',services)
    command(p,'budget',amountUsd=10);approve(p,'see');approve(p,'hear')
    request=p.snapshot('first','1')['state']['shots'][0]['outcomes']['request']
    assert request['estimateUsd']==2.8
    approve(p,'request')
    job=p.snapshot('first','1')['jobs'][0]
    assert job['estimate']==2800000


def test_learning_requires_approved_evidence_and_stays_project_local(setup):
    p,ws,t,_=setup;command(p,'budget',amountUsd=10)
    see=p.snapshot('first','1')['state']['shots'][0]['outcomes']['see']
    with pytest.raises(StudioError):command(p,'save_learning',shotId='S1.SH1',stage='see',candidateId=see['id'],note='Hold a listening reaction.')
    approve(p,'see')
    command(p,'save_learning',shotId='S1.SH1',stage='see',candidateId=see['id'],note='Hold a listening reaction.')
    with ws.db() as db:
        notes=p.review_learning(db,'first',p._load(db,'first','1'))
        other=p.review_learning(db,'second',p._load(db,'second','1'))
    assert any(n.get('authority','').startswith('human-approved') for n in notes)
    assert not other
    record=p.snapshot('first','1')['state']['learning'][0]
    command(p,'retire_learning',learningId=record['id'])
    with ws.db() as db:assert not any(n.get('authority','').startswith('human-approved') for n in p.review_learning(db,'first',p._load(db,'first','1')))


def test_learning_does_not_accept_a_secret(setup):
    p,ws,t,_=setup;command(p,'budget',amountUsd=10);approve(p,'see')
    see=p.snapshot('first','1')['state']['shots'][0]['outcomes']['see']
    with pytest.raises(StudioError):command(p,'save_learning',shotId='S1.SH1',stage='see',candidateId=see['id'],note='sk-'+'x'*30)


def test_chat_revision_uses_exact_preview_and_preserves_voice(setup):
    from studio_editing import fields
    p,ws,t,_=setup;command(p,'budget',amountUsd=10);approve(p,'see');approve(p,'hear')
    before=p.snapshot('first','1')['state']['shots'][0]
    new=fields(before);new['seePrompt']='Opening: uncertain smile.'
    t.reply={'message':'New opening','revisedShot':new}
    command(p,'chat',shotId='S1.SH1',message='Change the opening.')
    proposal=p.snapshot('first','1')['state']['shots'][0]['proposal']
    calls=len(t.calls)
    with pytest.raises(StudioError):command(p,'chat',shotId='S1.SH1',message='apply the change',proposalId='old')
    command(p,'chat',shotId='S1.SH1',message='apply the change',proposalId=proposal['id'])
    after=p.snapshot('first','1')['state']['shots'][0]
    assert after['outcomes']['hear']==before['outcomes']['hear']
    assert after['seePrompt']==new['seePrompt']
    assert len(t.calls)==calls+1  # SEE only, no model interpreting the command.


def returned(p):
    timeline_command(p,'export_cut')
    snapshot=p.snapshot('first','1');timeline=snapshot['review']['timeline']
    watch=snapshot['state']['shots'][0]['outcomes']['watch']
    return dict(path=watch['files'][0]['path'],hash=watch['files'][0]['hash'],handoffId=timeline['handoffId'],resolveProjectId='test-project',resolveTimelineId='test-timeline',inspection='24 fps. Inspected picture and sound from 0–2s.',unresolved='')


def test_returned_edit_is_separate_version_and_human_approved(setup):
    p,ws,t,_=setup;finish(p);data=returned(p)
    before=copy.deepcopy(p.snapshot('first','1')['state']['shots'])
    timeline_command(p,'register_finish',**data)
    c=p.snapshot('first','1')['review']['timeline']['finishedCandidates'][0]
    assert c['status']=='candidate' and c['current']
    assert c['files'][0]['path']!=data['path']
    timeline_command(p,'approve_finish',candidateId=c['id'],hash=c['files'][0]['hash'])
    assert p.snapshot('first','1')['state']['shots']==before
    assert p.snapshot('first','1')['review']['timeline']['finishedCandidates'][0]['status']=='approved'


@pytest.mark.parametrize('field,value',[('hash','wrong'),('handoffId','stale'),('path','projects/second/media/other.mp4')])
def test_return_rejects_wrong_file_or_handoff(setup,field,value):
    p,ws,t,_=setup;finish(p);data=returned(p);data[field]=value
    with pytest.raises(StudioError):timeline_command(p,'register_finish',**data)


def test_unresolved_return_cannot_be_approved(setup):
    p,ws,t,_=setup;finish(p);data=returned(p);data['unresolved']='Uninspected final cut'
    timeline_command(p,'register_finish',**data)
    c=p.snapshot('first','1')['review']['timeline']['finishedCandidates'][0]
    with pytest.raises(StudioError):timeline_command(p,'approve_finish',candidateId=c['id'],hash=c['files'][0]['hash'])
    timeline_command(p,'reject_finish',candidateId=c['id'],hash=c['files'][0]['hash'])


def test_repeat_jobs_do_not_count_other_shots_as_retakes():
    from studio_model_policy import summary
    costs=summary([{'kind':'see','shotId':'A'},{'kind':'see','shotId':'A'},{'kind':'see','shotId':'B'},{'kind':'hear','shotId':'A'}])
    assert costs['generationJobs']==4
    assert costs['repeatGenerationJobs']==1
