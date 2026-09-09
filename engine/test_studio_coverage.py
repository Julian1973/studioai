"""Direction is authored once; drawings, prompts and post consume the same revision."""
import copy
import json
import subprocess
from pathlib import Path

from studio_coverage import unit_board, scene_boards, panel_brief, staging_instruction
from studio_director_card import CoverageView, validate_coverage, stage_decisions
from studio_editing import fields, impact, revised_scene_coverage
from test_studio_director_card import direction
from test_studio_production import setup, command, approve, shot as fixture_shot


def view():
    return dict(viewId='door-wide', audienceNeed='Understand who can reach the latch',
                framing='Wide diagonal', cameraPurpose='Show the distance before the decision',
                cutReason='Read the release after the latch moves', continuity='Same door and moment',
                productionChoice='controlled multi-shot clip', entry='opening',
                staging='Hero near left, listener behind the closed door',
                action='Hero releases the latch; the door opens',
                performance='Hero listens, loosens the grip, then exhales', timing='0–4s',
                startState='Door closed; paw on latch', endState='Door open; paw relaxed',
                cutTo='Listener recognises the invitation')


def directed():
    d=direction();d['views']=[view()]
    return {**fixture_shot(1,'Hero: Hello.'), 'directorCard':d}


def test_board_has_no_second_authority_and_opening_excludes_future_action():
    shot=directed();before=copy.deepcopy(shot)
    board=unit_board(shot);brief=panel_brief(shot)
    assert board['revision']==brief['boardRevision']
    assert brief['panels'][0]['action']==shot['directorCard']['views'][0]['action']
    assert shot==before
    opening=json.dumps(stage_decisions(shot,'see'))+staging_instruction(shot,opening_only=True)
    assert 'Door closed; paw on latch' in opening
    assert 'Door open; paw relaxed' not in opening
    assert 'Listener recognises' not in opening
    assert 'Door open; paw relaxed' in staging_instruction(shot)


def test_clip_allocation_cannot_rewrite_scene_camera_or_acting():
    from types import SimpleNamespace
    from cb_creative import StoryboardInternalShot, _validate_scene_view_allocation
    from studio_director_card import SceneCoverage
    source=view()
    scene=SceneCoverage(scene=1,audienceJourney='Trust',views=[source])
    packed=StoryboardInternalShot(shotNumber=1,viewId=source['viewId'],transitionType='opening',
        framingAndCamera='Contradictory close-up',purpose='Different purpose',storyAction='Wrong action',
        performanceFocus='Vacant stare',landingImage='Door still closed',cutReason='Random variety')
    _validate_scene_view_allocation(SimpleNamespace(sceneCoverage=[scene]),
        [SimpleNamespace(shotId='S1.SH1',internalShotPlan=[packed])])
    assert packed.framingAndCamera==source['framing']+'. '+source['cameraPurpose']
    assert packed.storyAction==source['action'] and packed.performanceFocus==source['performance']
    assert packed.landingImage==source['endState'] and packed.staging==source['staging']


def test_scene_revision_updates_only_selected_unit_and_preserves_voice():
    old=directed();second=directed();second['id']='S1.SH2'
    second['directorCard']['views'][0]['viewId']='listener-reverse'
    state={'shots':[old,second], 'sceneCoverage':[{'scene':1,'audienceJourney':'Hesitation to trust',
        'views':[old['directorCard']['views'][0],second['directorCard']['views'][0]]}]}
    before=scene_boards(state['shots'],state['sceneCoverage'])[0]
    new=copy.deepcopy(old);new['directorCard']['views'][0]['endState']='Door ajar; paw relaxed'
    updated=revised_scene_coverage(state,old,new)
    after=scene_boards([new,second],updated)[0]
    assert before['revision']!=after['revision']
    assert before['units'][1]==after['units'][1]
    assert 'hear' not in impact(old,new)['reset']
    assert 'see' not in impact(old,new)['reset']
    validate_coverage(updated,[new,second])


def test_new_clip_opening_keeps_the_directors_planned_cut():
    from types import SimpleNamespace
    from cb_creative import StoryboardInternalShot, _validate_scene_view_allocation
    from studio_director_card import SceneCoverage
    source = {**view(), 'entry': 'cut'}
    scene = SceneCoverage(scene=1, audienceJourney='Read the listener', views=[source])
    packed = StoryboardInternalShot(shotNumber=1, viewId=source['viewId'],
        transitionType='opening', framingAndCamera='Wide', purpose='Read the listener',
        storyAction='Listen', performanceFocus='Read the thought',
        landingImage='Listener settles', cutReason='Changed attention')
    _validate_scene_view_allocation(SimpleNamespace(sceneCoverage=[scene]),
        [SimpleNamespace(shotId='S1.SH2', internalShotPlan=[packed])])
    assert packed.transitionType == 'cut'
    assert packed.framingAndCamera == source['framing'] + '. ' + source['cameraPurpose']


def test_new_camera_opening_does_not_become_a_relay_at_scene_end():
    from types import SimpleNamespace
    from cb_creative import StoryboardInternalShot, _validate_scene_view_allocation
    from studio_director_card import SceneCoverage
    source = {**view(), 'entry':'opening', 'cutReason':'A new angle reads the listener'}
    scene = SceneCoverage(scene=1, audienceJourney='Read the listener', views=[source])
    packed = StoryboardInternalShot(shotNumber=1, viewId=source['viewId'],
        transitionType='opening', framingAndCamera='Wide', purpose='Listen',
        storyAction='Listen', performanceFocus='Recognise', landingImage='Settled', cutReason='Listen')
    shot = SimpleNamespace(shotId='S1.SH2', transitionType='CONTINUOUS',
                           providerBoundaryReason='scene_end', internalShotPlan=[packed])
    _validate_scene_view_allocation(SimpleNamespace(sceneCoverage=[scene]), [shot])
    assert shot.transitionType == 'PLANNED_CUT'
    assert shot.providerBoundaryReason == 'scene_end'


def test_current_revision_reaches_every_role_and_does_not_leak(monkeypatch):
    import cb_creative as c
    monkeypatch.setattr(c, '_canon_text', lambda *a: 'Established canon')
    monkeypatch.setattr(c, '_canonical_exemplars', lambda: '')
    monkeypatch.setattr(c.cb_departments, 'load_runtime_skill', lambda *a: 'Current role contract')
    note = 'Keep the honey grab and drone pursuit; preserve the approved words.'
    token = c._active_direction_brief.set(note)
    try:
        for role in ('EMOTIONAL STORY-TO-SCREEN DIRECTOR', 'DIRECTOR',
                     'CINEMATOGRAPHER', 'VOICE DIRECTOR', 'SHOWRUNNER'):
            system = c._mind(role, [], 'Direct the current scene')
            assert note in system
            assert 'Older treatments and episode summaries are context' in system
    finally:
        c._active_direction_brief.reset(token)
    assert note not in c._mind('DIRECTOR', [], 'Direct another scene')


def test_existing_coverage_remains_valid_without_new_optional_fields():
    shot=directed();oldview={k:v for k,v in view().items() if k not in
        ('staging','action','performance','timing','startState','endState','cutTo')}
    shot['directorCard']['views']=[CoverageView.model_validate(oldview).model_dump()]
    validate_coverage([dict(scene=1,audienceJourney='Trust',views=[oldview])],[shot])


def test_old_see_projection_does_not_add_coverage_to_existing_signatures():
    shot={'shotId':'old','storyIntentApproved':{'intent':'Trust'},
          'storyboardInternalShotPlanApproved':[{'framingAndCamera':'Wide','storyAction':'A later action'}]}
    assert 'openingCoverage' not in stage_decisions(shot,'see')
    shot['storyboardInternalShotPlanApproved'][0]['staging']='Left bank opening'
    assert stage_decisions(shot,'see')['openingCoverage']['staging']=='Left bank opening'


def test_shared_code_update_preserves_prepared_look_but_not_changed_inputs(monkeypatch):
    import cb_render as r
    import cb_canon
    monkeypatch.setattr(cb_canon,'require_locked',lambda *a,**kw:{'profileDigests':{'look':'canon'}})
    monkeypatch.setattr(r,'_scene_context',lambda *a,**kw:{'place':'same forest'})
    work={}
    monkeypatch.setattr(r,'_department_container',lambda *a,**kw:(work,None))
    pkg={'sceneNumber':1,'episode':'EpT','shots':[]}
    expected=r._department_record_status(pkg,None,'look','1','EpT')['expectedInputSignature']
    stored=copy.deepcopy(expected);stored['directingContractHash']='older-shared-code'
    work['candidate']={'inputSignature':stored,'output':{'providerPrompt':'Original authored place'}}
    assert r._department_record_status(pkg,None,'look','1','EpT')['current']
    stored['sceneContextHash']='a different forest'
    assert not r._department_record_status(pkg,None,'look','1','EpT')['current']
    stored['sceneContextHash']=expected['sceneContextHash'];stored['skillHashes']={'look':'different skill'}
    assert not r._department_record_status(pkg,None,'look','1','EpT')['current']


def test_authored_staging_flows_from_revision_to_actual_request_and_post(setup):
    p,ws,t,_=setup;command(p,'budget',amountUsd=10)
    old=p.snapshot('first','1')['state']['shots'][0]
    new=fields(old);new['directorCard']=directed()['directorCard']
    t.reply={'message':'Stage the latch and listener','revisedShot':new}
    command(p,'chat',shotId=old['id'],message='Show the staging before the reaction')
    proposal=p.snapshot('first','1')['state']['shots'][0]['proposal']
    command(p,'apply_revision',shotId=old['id'],proposalId=proposal['id'],prepare=True)
    image=[c[2] for c in t.calls if c[0]=='image'][-1]
    assert 'Hero near left' in image and 'Door open; paw relaxed' not in image
    approve(p,'see');approve(p,'hear')
    request=p.snapshot('first','1')['state']['shots'][0]['outcomes']['request']
    assert 'Door open; paw relaxed' in request['prompt']
    assert 'Hero listens, loosens the grip' in request['prompt']
    approve(p,'request');approve(p,'watch')
    snapshot=p.snapshot('first','1')
    shot=snapshot['state']['shots'][0]
    assert shot['outcomes']['watch']['originatingShot']['directorCard']['views'][0]['staging']==view()['staging']
    from studio_post_contract import project_brief
    state=copy.deepcopy(snapshot['state'])
    state['shots'][0]['directorCard']['views'][0]['endState']='A later editorial suggestion'
    timeline=copy.deepcopy(snapshot['review']['timeline']);timeline['clips']=timeline['clips'][:1]
    brief=project_brief(p,ws.context('first','1'),state,timeline)['shots'][0]
    assert brief['coverageBoard']['panels'][0]['endState']=='Door open; paw relaxed'
    assert brief['direction']['directorCard']['views'][0]['endState']=='A later editorial suggestion'
    assert brief['renderedDirectionEvidence']=='recorded at generation'


def test_coverage_renderer_escapes_authored_text_and_does_not_invent_drawings():
    path=Path(__file__).resolve().parents[1]/'cb-studio/scene-coverage.js'
    script='global.window={};'+path.read_text()+''';
    const assert=require('node:assert/strict');
    assert.equal(window.StudioCoverage.html({units:[]}), '');
    const out=window.StudioCoverage.html({units:[{shotId:'S1.SH1',panels:[{number:1,framing:'<script>oops</script>',performance:'Listen & react'}]}]});
    assert(!out.includes('<script>'));
    assert(out.includes('&lt;script&gt;') && out.includes('Listen &amp; react'));
    assert(!out.includes('<img'));
    '''
    subprocess.run(['node','-e',script],check=True,capture_output=True)
