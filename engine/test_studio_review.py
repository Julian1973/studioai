"""Production-board, editing, assembly and migration tests using real local media."""
import copy
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from test_studio_production import setup, command, approve
from studio_workspace import StudioError
from studio_editing import fields
from studio_migration import Migration
from studio_production import file_hash


def test_returned_review_keeps_original_references_after_new_direction(setup):
    from studio_media_review import manifest
    production, ws, _, _ = setup
    finish(production)
    context = ws.context('first', '1')
    state = production.snapshot('first', '1')['state']
    shot = state['shots'][0]
    before = manifest(production, context, state, shot)
    original = copy.deepcopy(shot['outcomes']['watch']['originatingReviewInputs'])
    identity = next(ref for ref in before['references'] if ref.get('name') == 'Hero')
    assert identity['approvalStatus'] == 'supplied'
    shot['geography'] = 'A later revision on a different bank.'
    shot['outcomes']['see'] = {'status':'candidate', 'id':'new-opening', 'files':[]}
    from PIL import Image
    replacement = ws.project_path('first', 'projects/first/assets/replacement-hero.png')
    Image.new('RGB', (24, 24), 'green').save(replacement)
    context['assets']['characters']['Hero']['anchor'] = 'projects/first/assets/replacement-hero.png'
    after = manifest(production, context, state, shot)
    assert after['references'] == before['references']
    assert all(ref['path'] != context['assets']['characters']['Hero']['anchor'] for ref in after['references'])
    assert after['see'] == before['see']
    assert after['shot'] == before['shot']
    assert after['requestLineage'] == before['requestLineage']
    assert shot['outcomes']['watch']['originatingReviewInputs'] == original


def test_changed_originating_identity_blocks_review_instead_of_using_current_assets(setup):
    from studio_media_review import manifest
    production, ws, _, _ = setup
    finish(production)
    context = ws.context('first', '1')
    state = production.snapshot('first', '1')['state']
    shot = state['shots'][0]
    original = shot['outcomes']['watch']['originatingReviewInputs']
    identity = next(ref for ref in original['references'] if ref.get('name') == 'Hero')
    assert identity['approvalStatus'] == 'supplied'
    ws.project_path('first', identity['path']).write_bytes(b'changed identity reference')
    with pytest.raises(StudioError, match='originating render reference'):
        manifest(production, context, state, shot)


@pytest.mark.parametrize('part', ['identity', 'see', 'hear', 'missing-packet'])
def test_altered_originating_metadata_cannot_substitute_valid_new_media(setup, part):
    from studio_media_review import manifest
    production, ws, _, _ = setup
    command(production, 'budget', amountUsd=20)
    for stage in ('see', 'hear', 'request'):
        approve(production, stage)
    context = ws.context('first', '1')
    state = production.snapshot('first', '1')['state']
    shot = state['shots'][0]
    watch = shot['outcomes']['watch']
    original = watch['originatingReviewInputs']
    if part == 'missing-packet':
        watch.pop('originatingReviewInputs')
    else:
        source = (next(ref for ref in original['references'] if ref.get('name') == 'Hero')
                  if part == 'identity' else original[part]['files'][0])
        # A different valid, same-project file and its correct new hash would pass
        # ordinary file-integrity checks; it must fail the sealed source binding.
        replacement = ws.project_path('first', 'projects/first/assets/new-valid-reference.png')
        from PIL import Image
        Image.new('RGB', (24, 24), 'green').save(replacement)
        source.update(path='projects/first/assets/new-valid-reference.png', hash=file_hash(replacement))
    with pytest.raises(StudioError, match='originating inputs'):
        manifest(production, context, state, shot)


def test_originating_reference_path_can_relocate_without_changing_its_content(setup):
    from studio_media_review import manifest
    production, ws, _, _ = setup
    command(production, 'budget', amountUsd=20)
    for stage in ('see', 'hear', 'request'):
        approve(production, stage)
    state = production.snapshot('first', '1')['state']
    shot = state['shots'][0]
    source = next(ref for ref in shot['outcomes']['watch']['originatingReviewInputs']['references'] if ref.get('name') == 'Hero')
    old_path = ws.project_path('first', source['path'])
    destination = ws.project_path('first', 'projects/first/assets/relocated-hero.png')
    destination.write_bytes(old_path.read_bytes())
    source['path'] = 'projects/first/assets/relocated-hero.png'
    result = manifest(production, ws.context('first', '1'), state, shot)
    assert result['requestLineage']['status'] == 'origin-verified'
    assert any(ref['path'] == source['path'] and ref['hash'] == source['hash'] for ref in result['references'])


def finish(p):
    command(p, 'budget', amountUsd=20)
    for sid in ('S1.SH1', 'S1.SH2'):
        for stage in ('see', 'hear', 'request', 'watch'):
            shot = next(s for s in p.snapshot('first','1')['state']['shots'] if s['id']==sid)
            command(p,'approve',shotId=sid,reviewId=shot['outcomes'][stage]['id'])


def timeline_command(p, action, **extra):
    fingerprint=p.snapshot('first','1')['review']['timeline']['fingerprint']
    return command(p,action,timelineFingerprint=fingerprint,**extra)


def test_board_counts_approved_seconds_not_planned_or_generated(setup):
    p,ws,t,_=setup
    command(p,'budget',amountUsd=5)
    summary=p.snapshot('first','1')['review']['summary']
    assert summary['shots']==2 and summary['approvedSeconds']==0 and not summary['assemblyReady']
    approve(p,'see');approve(p,'hear');approve(p,'request')
    review=p.snapshot('first','1')['review']
    assert review['summary']['generatedShots']==1 and review['summary']['approvedShots']==0
    assert all(c['gap'] for c in review['timeline']['clips'])
    approve(p,'watch')
    review=p.snapshot('first','1')['review']
    assert review['summary']['approvedSeconds']==2 and review['summary']['approvedShots']==1
    assert review['timeline']['clips'][1]['gap'] and review['timeline']['clips'][1]['start']==2
    assert review['shots'][0]['status']=='approved'


def test_tampered_approved_media_becomes_visible_gap(setup):
    p,ws,t,_=setup;finish(p)
    watch=p.snapshot('first','1')['state']['shots'][0]['outcomes']['watch']
    ws.project_path('first',watch['files'][0]['path']).write_bytes(b'changed')
    view=p.snapshot('first','1')['review']
    assert view['timeline']['clips'][0]['gap'] and view['summary']['approvedShots']==1
    assert any(i['code']=='media_changed' for i in view['inspections']['S1.SH1']['issues'])
    with pytest.raises(StudioError,match='gaps'):timeline_command(p,'export_cut')


def test_preview_discard_apply_undo_preserve_approvals_and_spend(setup):
    p,ws,t,_=setup;finish(p)
    old=p.snapshot('first','1')['state']['shots'][0]
    new=fields(old);new['performance']='A longer breath, then a relieved smile.'
    t.reply={'message':'Let relief arrive slowly.','revisedShot':new}
    command(p,'chat',shotId=old['id'],message='Slow the relief')
    preview=p.snapshot('first','1')['state']['shots'][0]
    assert preview['outcomes']==old['outcomes']
    assert preview['proposal']['impact']['replacesApproved']==['request','see','watch']
    command(p,'discard_revision',shotId=old['id'],proposalId=preview['proposal']['id'])
    assert 'proposal' not in p.snapshot('first','1')['state']['shots'][0]
    command(p,'chat',shotId=old['id'],message='Slow the relief')
    preview=p.snapshot('first','1')['state']['shots'][0]
    command(p,'apply_revision',shotId=old['id'],proposalId=preview['proposal']['id'])
    changed=p.snapshot('first','1')['state']
    assert changed['shots'][0]['outcomes']['hear']==old['outcomes']['hear']
    assert changed['shots'][1]['outcomes']['watch']['status']=='approved'
    assert p.snapshot('first','1')['review']['shots'][1]['status']=='needs_attention'
    budget=copy.deepcopy(changed['budget'])
    command(p,'undo_revision',shotId=old['id'])
    restored=p.snapshot('first','1')['state']
    assert restored['shots'][0]['outcomes']==old['outcomes']
    assert restored['budget']==budget and restored['editAudit'][-1]['action']=='undo'


def test_old_proposal_cannot_overwrite_new_approval(setup):
    p,ws,t,_=setup;command(p,'budget',amountUsd=5)
    old=p.snapshot('first','1')['state']['shots'][0]
    new=fields(old);new['camera']='A motivated close reaction.'
    t.reply={'message':'A closer reaction.','revisedShot':new}
    command(p,'chat',shotId=old['id'],message='Move closer')
    preview=p.snapshot('first','1')['state']['shots'][0]['proposal']
    approve(p,'see')
    with pytest.raises(StudioError,match='changed'):command(p,'apply_revision',shotId=old['id'],proposalId=preview['id'])


def save_state(ws, **extra):
    c=ws.context('first')
    image=ws.project_path('first',c['assets']['characters']['Hero']['anchor']).read_bytes()
    return ws.update_library({'projectId':'first','sourceHash':c['sourceHash'],'group':'states','character':'Hero','name':'Soaked',
                              'notes':'Wet fur; unchanged identity.','imageData':'fixture','approve':True,**extra},lambda _: (image,'.png'))['characterState']


def test_character_states_are_scoped_versioned_and_sent_to_generation(setup):
    p,ws,t,_=setup
    state=save_state(ws,episode='1',scenes=[1]);command(p,'budget',amountUsd=5)
    command(p,'bind_states',shotId='S1.SH1',characterStates=[{'character':'Hero','stateId':state['id']}])
    shot=p.snapshot('first','1')['state']['shots'][0]
    assert not shot['characterStates']
    command(p,'apply_revision',shotId=shot['id'],proposalId=shot['proposal']['id'],prepare=True)
    prompt=[c[2] for c in t.calls if c[0]=='image'][-1]
    assert 'Wet fur; unchanged identity.' in prompt and 'approved character state' in prompt
    assert ws.context('second')['characterStates']==[]
    original=ws.project_path('first',state['image']).read_bytes()
    newer=save_state(ws,id=state['id'],name='Soaked',notes='Dripping wet',episode='1',scenes=[1])
    assert newer['version']!=state['version'] and original==ws.project_path('first',state['image']).read_bytes()
    assert p.snapshot('first','1')['sourceChanged']


@pytest.mark.parametrize('change,code',[({'episode':'1','scenes':[2]},'state_scope'),({'approve':False},'state_unapproved')])
def test_wrong_or_unapproved_state_cannot_enter_a_shot(setup,change,code):
    p,ws,t,_=setup;state=save_state(ws,**change);command(p,'budget',amountUsd=5)
    with pytest.raises(StudioError) as error:command(p,'bind_states',shotId='S1.SH1',characterStates=[{'character':'Hero','stateId':state['id']}])
    assert error.value.code==code


def test_identity_conflict_is_refused_before_generation(setup):
    p,ws,t,_=setup
    path=ws.project_path('first','projects/first/characters.json')
    data=json.loads(path.read_text());data['Hero']['identityTraits']={'species':'bear','wings':'none'};path.write_text(json.dumps(data))
    command(p,'budget',amountUsd=4)
    old=p.snapshot('first','1')['state']['shots'][0]
    new=fields(old);new['identityClaims']=[{'character':'Hero','trait':'wings','value':'feathered'}]
    with pytest.raises(StudioError,match='conflicts'):p.validate_shot(ws.context('first','1'),new)
    assert 'wings' in [c[2] for c in t.calls if c[0]=='image'][0]


def test_timed_direction_reaches_both_generation_prompts(setup):
    p,ws,t,_=setup;command(p,'budget',amountUsd=10)
    old=p.snapshot('first','1')['state']['shots'][0]
    new=fields(old);new.update(intent='Ask for forgiveness',openingState='Hero looks down, left hand against the door',endingState='Hero meets the listener eyeline',
                             beatPlan=[{'at':0,'action':'Hold the breath','audienceFeeling':'Anticipation'},{'at':2,'action':'Let the smile arrive','audienceFeeling':'Relief'}])
    # Revise the actual shared decisions. Legacy beat prose is not a competing
    # WATCH authoring channel once a typed Director Card exists.
    card = new['directorCard']
    card.update(audienceFocus=new['intent'], handoff=new['endingState'], intendedState=new['endingState'])
    card['acting'][0].update(intention=new['intent'], startingPose=new['openingState'],
                            endingPose=new['endingState'], observableBehaviour='Hold the breath; after the reply, let the smile arrive.')
    card['views'][0].update(startState=new['openingState'], endState=new['endingState'],
                            staging='Hero stands with the left hand against the door.',
                            action='Hold the breath. Deliver the exact approved reply. Let the smile arrive after the reply.',
                            performance='Keep attention on the listener; the held breath releases into a small smile.')
    t.reply={'message':'A clear emotional turn.','revisedShot':new}
    command(p,'chat',shotId=old['id'],message='Build the anticipation')
    proposed=p.snapshot('first','1')['state']['shots'][0]['proposal']
    command(p,'apply_revision',shotId=old['id'],proposalId=proposed['id'],prepare=True)
    approve(p,'see');approve(p,'hear')
    request=p.snapshot('first','1')['state']['shots'][0]['outcomes']['request']
    for prompt in ([c[2] for c in t.calls if c[0]=='image'][-1],request['prompt']):
        assert 'Ask for forgiveness' in prompt and 'Hold the breath' in prompt and 'left hand against the door' in prompt
    assert 'Let the smile arrive' not in [c[2] for c in t.calls if c[0]=='image'][-1]
    assert 'Let the smile arrive' in request['prompt']


def test_timeline_notes_trims_join_signoff_and_export_are_version_bound(setup):
    p,ws,t,_=setup;finish(p)
    budget=copy.deepcopy(p.snapshot('first','1')['state']['budget'])
    timeline_command(p,'timeline_note',seconds=2.5,note='Give this reaction more time.')
    note=p.snapshot('first','1')['review']['timeline']['notes'][0]
    assert note['shotId']=='S1.SH2' and note['sourceSeconds']==.5
    timeline_command(p,'assemble_cut')
    with pytest.raises(StudioError,match='review notes'):timeline_command(p,'review_cut')
    timeline_command(p,'resolve_note',noteId=note['id'])
    timeline_command(p,'assemble_cut')
    timeline_command(p,'review_cut')
    assert p.snapshot('first','1')['review']['summary']['reviewCurrent']
    before=p.snapshot('first','1')['review']['timeline']['fingerprint']
    timeline_command(p,'trim_clip',shotId='S1.SH2',**{'in':.25,'out':1.75})
    assert not p.snapshot('first','1')['review']['summary']['reviewCurrent']
    with pytest.raises(StudioError,match='changed'):command(p,'review_join',shotId='S1.SH2',timelineFingerprint=before)
    timeline_command(p,'review_join',shotId='S1.SH2');timeline_command(p,'assemble_cut');timeline_command(p,'review_cut');timeline_command(p,'export_cut')
    view=p.snapshot('first','1')
    assert view['state']['budget']==budget
    exported=view['review']['timeline']['export']
    assert view['review']['timeline']['preview']['duration']==pytest.approx(3.5,abs=.1)
    xml=ET.parse(ws.project_path('first',exported['files'][0]['path']))
    assert len(xml.findall('.//asset-clip'))==2 and xml.find('.//sequence').get('duration')=='84/24s'
    assert all(a.get('src').startswith('file:///') for a in xml.findall('.//asset'))


def test_post_handoff_contains_scoped_direction_and_approved_authorities(setup):
    p,ws,t,_ = setup; finish(p)
    before = p.snapshot('first','1')['state']
    calls = len(t.calls)
    timeline_command(p, 'export_cut')
    snapshot = p.snapshot('first','1')
    exported = snapshot['review']['timeline']['export']
    manifest = json.loads(ws.project_path('first', exported['files'][1]['path']).read_text())
    brief = manifest['postSupervisor']
    assert brief['projectId'] == 'first' and brief['episode'] == '1'
    assert brief['context']['bible'] == 'first world only'
    assert 'second world only' not in json.dumps(manifest)
    assert 'episode2-evidence.md' not in brief['postSupervisorReferences']
    assert not brief['assemblyApproved'] and brief['reviewType'] == 'brief-only'
    assert brief['assemblyFingerprint'] == manifest['fingerprint']
    for bound, original in zip(brief['shots'], before['shots']):
        assert bound['direction'] == fields(original)
        assert not bound['missingAuthorities']
        assert bound['approvedOutcomes']['hear']['files'] == original['outcomes']['hear']['files']
        assert bound['approvedOutcomes']['watch']['id'] == original['outcomes']['watch']['id']
        assert bound['approvedOutcomes']['request']['prompt'] == original['outcomes']['request']['prompt']
    assert snapshot['state']['shots'] == before['shots']
    assert snapshot['state']['budget'] == before['budget'] and len(t.calls) == calls
    assert p.snapshot('second','1')['state']['shots'] == []


def test_post_handoff_rejects_foreign_audio_even_when_video_is_approved(setup):
    from studio_post_contract import project_brief
    p,ws,t,_ = setup; finish(p)
    snapshot = p.snapshot('first','1')
    state = snapshot['state']
    state['shots'][0]['outcomes']['hear']['files'][0]['path'] = 'projects/second/assets/hero.png'
    with pytest.raises(StudioError, match='selected project'):
        project_brief(p, ws.context('first','1'), state, snapshot['review']['timeline'])


def test_post_handoff_rejects_changed_candidate_ids(setup):
    from studio_post_contract import project_brief
    p,ws,t,_ = setup; finish(p)
    snapshot = p.snapshot('first','1')
    snapshot['review']['timeline']['clips'][0]['candidateId'] = 'outdated-render'
    with pytest.raises(StudioError, match='footage changed'):
        project_brief(p, ws.context('first','1'), snapshot['state'], snapshot['review']['timeline'])


def test_existing_render_cannot_be_resubmitted_without_a_review_or_revision(setup):
    p,ws,t,_=setup;command(p,'budget',amountUsd=10);approve(p,'see');approve(p,'hear');approve(p,'request')
    request=p.snapshot('first','1')['state']['shots'][0]['outcomes']['request']
    with pytest.raises(StudioError,match='returned render'):command(p,'watch',shotId='S1.SH1',reviewId=request['id'])
    assert len([c for c in t.calls if c[0]=='video'])==1


def test_voice_scope_preserves_picture_even_if_director_changes_extra_fields(setup):
    p,ws,t,_=setup;command(p,'budget',amountUsd=5);approve(p,'see');approve(p,'hear')
    original=p.snapshot('first','1')['state']['shots'][0]
    revised=fields(original);revised['dialogue'][0]['delivery']='whispering';revised['camera']='An unwanted new camera angle'
    t.reply={'message':'A whisper.','revisedShot':revised}
    command(p,'chat',shotId=original['id'],stage='hear',message='Whisper this line')
    proposal=p.snapshot('first','1')['state']['shots'][0]['proposal']
    assert proposal['impact']['changed']==['dialogue']
    command(p,'apply_revision',shotId=original['id'],proposalId=proposal['id'],prepare=True)
    current=p.snapshot('first','1')['state']['shots'][0]
    assert current['camera']==original['camera'] and current['outcomes']['see']==original['outcomes']['see']


def test_episode_feedback_informs_only_its_own_project(setup):
    p,ws,t,_=setup;finish(p)
    timeline_command(p,'timeline_note',seconds=1,note='Let the listener finish thinking before the cut.')
    with ws.db() as db:
        learning=p.review_learning(db,'first',p._load(db,'first','1'))
        other=p.review_learning(db,'second',p._load(db,'second','1'))
    assert any('listener finish thinking' in r['note'] for r in learning)
    assert not any('listener finish thinking' in r['note'] for r in other)


def test_local_assembly_recovers_without_provider_calls_or_budget_change(setup):
    p,ws,t,_=setup;finish(p)
    old_launch=p.launch;p.launch=lambda job:None
    result=timeline_command(p,'assemble_cut');p.launch=old_launch
    with ws.db() as db:
        row=db.execute('SELECT data FROM jobs WHERE id=?',(result['jobId'],)).fetchone();job=json.loads(row[0]);job.update(status='running',pid=-1);p._job(db,job)
    before=p.snapshot('first','1')['state']['budget'];calls=len(t.calls)
    command(p,'resume',jobId=result['jobId'])
    current=p.snapshot('first','1')
    assert current['review']['timeline']['preview'] and len(t.calls)==calls
    assert current['state']['budget']==before


def legacy(ws, approved_hash=True):
    import subprocess
    root=ws.root/'legacy';(root/'canon').mkdir(parents=True)
    (root/'bible.md').write_text('Legacy world')
    (root/'script.txt').write_text('Hero: Hello.')
    (root/'episodes.json').write_text(json.dumps([{'number':1,'title':'Legacy episode','script':'legacy/script.txt'}]))
    image=ws.project_path('first','projects/first/assets/hero.png');(root/'hero.png').write_bytes(image.read_bytes())
    (root/'canon/characters.json').write_text(json.dumps({'Hero':{'anchor':'legacy/hero.png'}}))
    video=root/'approved.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=32x18:r=5','-t','1','-c:v','libx264','-y',str(video)],check=True,capture_output=True)
    package={'episode':'Ep1','sceneNumber':1,'shots':[{'shotId':'S1.SH1','durationSec':4,'purpose':'A held reaction','charactersInFrame':['Hero']}],
             'continuityLedger':[{'shotId':'S1.SH1','status':'approved','approvedTake':str(video),'approval':{'approved':True,'contentHash':file_hash(video) if approved_hash else 'wrong'}}]}
    (root/'Ep1_scene1_production_package.json').write_text(json.dumps(package))
    registry=ws.root/'cb-studio/data/projects.json';value=json.loads(registry.read_text());value['projects'].append({'id':'old','name':'Old world','configBase':'legacy/canon','showBibleFile':'legacy/bible.md','episodesFile':'legacy/episodes.json','packageBase':'legacy'})
    registry.write_text(json.dumps(value));return video


@pytest.mark.parametrize('matching',[True,False])
def test_migration_preserves_originals_and_only_matching_approval_evidence(setup,matching):
    p,ws,t,_=setup;video=legacy(ws,matching);before=video.read_bytes();m=Migration(ws);report=m.preview('old')
    assert report['episodes'][0]['approvedShots']==int(matching)
    m.apply({'projectId':'old','targetId':'upgraded','fingerprint':report['fingerprint'],'reviewed':True})
    assert video.read_bytes()==before and ws.project('old').get('setupVersion') is None
    snapshot=p.snapshot('upgraded','1');shot=snapshot['state']['shots'][0]
    assert shot['importedArchive'] and snapshot['review']['summary']['approvedShots']==int(matching)
    assert ws.project_path('upgraded',shot['outcomes']['watch']['files'][0]['path']).read_bytes()==before
    with pytest.raises(StudioError,match='archive'):command(p,'chat',pid='upgraded',shotId='S1.SH1',message='Change it')


def test_migration_refuses_changed_source_and_existing_destination(setup):
    p,ws,t,_=setup;legacy(ws);m=Migration(ws);report=m.preview('old')
    (ws.root/'legacy/script.txt').write_text('Changed screenplay')
    with pytest.raises(StudioError,match='current migration'):m.apply({'projectId':'old','targetId':'upgraded','fingerprint':report['fingerprint'],'reviewed':True})
    report=m.preview('old')
    with pytest.raises(StudioError,match='unused'):m.apply({'projectId':'old','targetId':'first','fingerprint':report['fingerprint'],'reviewed':True})
