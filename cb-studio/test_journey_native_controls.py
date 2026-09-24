"""Existing native preparation/compiler/Fire/approval services on an isolated saved scene.

Golden-path fixtures supply synthetic canon and provider responses. The older fixture
has a documented lineage bypass, so this test does NOT qualify initial script promotion.
"""
from pathlib import Path
from types import SimpleNamespace
import json,pytest
import hashlib
from test_current_production_path import (_approve_specialist_inputs,_approve_scene_look,_sign_specialist_inputs,_approve_animation_direction,isolated_canon)
from test_golden_path import world,_review_output,_lock_scene_cut,_approve_director_review
import cb_render as R
import cb_studio_director as D
from studio_journey import Journey,StudioStore,scope_key
from studio_journey_native import Native
from studio_journey_worker import perform
_REAL_LAST_FRAME=R.cb_gen.last_frame
_REAL_AUDIO_CONFORM=R.cb_post.replace_guide_dialogue


@pytest.mark.parametrize('single_shot_scene', [False, True])
def test_native_existing_approved_inputs_use_real_compiler_fire_and_approval(world,monkeypatch,single_shot_scene):
    providers,root,path=world
    monkeypatch.setattr(R,"ROOT",root)
    import studio_prompt_director
    monkeypatch.setattr(studio_prompt_director,"__file__",str(root/"engine/studio_prompt_director.py"))
    bank=R.cb_prompt_bank.bank_prompt
    monkeypatch.setattr(R.cb_prompt_bank,'bank_prompt',lambda **kw:bank(**kw,bank_path=root/'cb-output/prompt-bank/prompt_bank.jsonl'))
    import sys,types
    backup=types.ModuleType('tools.backup_media');backup.backup_one=lambda *a:None
    monkeypatch.setitem(sys.modules,'tools.backup_media',backup)
    # Supply the same trusted show/project/script records the current services read.
    # Do not bypass SEE configuration or scene-plate authority checks.
    show = root/'shows/crystal-bears'
    (show/'profile.json').write_text(json.dumps({
        'showId':'crystal-bears', 'name':'Fixture show', 'animationType':'3D animation',
        'aspectRatio':'16:9', 'engineAdapter':'crystal-bears-v1',
        'canon':{'lockedCanon':'canon/LOCKED_CANON.md', 'characters':'canon/characters.json',
                 'locations':'canon/locations.json', 'continuity':'canon/continuity.json'},
        'laws':{}, 'episodes':{'scripts':'episodes/scripts','output':'output'}}))
    (show/'canon/LOCKED_CANON.md').write_text('A synthetic test meadow with oversized flowers.')
    registry = root/'cb-studio/data/projects.json'
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(json.dumps({'projects':[{'id':'crystal-bears','aspectRatio':'16:9'}]}))
    monkeypatch.setenv('STUDIO_WORKSPACE_PRIVATE', str(root/'private'))
    script = show/'episodes/scripts/fixture.txt'
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text('The character turns, moves, and settles in the test meadow.')
    pkg=json.loads(path.read_text())
    if single_shot_scene:
        pkg['shots'] = pkg['shots'][:1]
        pkg['continuityLedger'] = pkg['continuityLedger'][:1]
    pkg.setdefault('sourceScript', {}).update(contentPath=str(script.relative_to(root)),
                              sha256=hashlib.sha256(script.read_bytes()).hexdigest())
    _approve_specialist_inputs(pkg)
    for shot in pkg['shots']:
        shot['directorCard'].update(cameraPurpose='Keep the causal action readable.',
            editIn='Begin on the approved opening.', editOut='Hold the settled result.',
            handoff='Carry the settled pose.', intendedState='The character has settled.',
            acting=[], soundOwnership='Approved dialogue is the audio authority.')
        from studio_source_segmentation import project as segment_source
        for index, line in enumerate(shot.get('dialogueLines') or [], start=1):
            line.setdefault('dialogueOccurrenceId', f"{shot['shotId']}.dialogue.{index}")
            raw = line['exactText']
            revision = 'sha256:' + hashlib.sha256(raw.encode()).hexdigest()
            line['sourceSegmentation'] = segment_source(line, raw, boundary={
                'occurrenceId': line['dialogueOccurrenceId'],
                'speaker': line['speaker'], 'scriptRevision': revision,
                'authority': 'structural_line_types', 'evidenceId': 'native-flow-fixture',
                'spans': {'spokenText': [0, len(raw)]},
            })
        for view in shot['directorCard']['views']:
            view.update(audienceNeed='Read the cause and result.',
                cameraPurpose='Keep the action visible.', cutReason='One continuous setup.',
                continuity='Keep the test meadow geography.', productionChoice='current clip',
                staging='The character stands in the test meadow.',
                startState='The character is still in the test meadow.')
    path.write_text(json.dumps(pkg));_approve_scene_look(root,pkg);_sign_specialist_inputs(pkg);path.write_text(json.dumps(pkg))
    # Generate real decodable fixture media at the external provider boundary.
    video_provider=R.cb_gen.generate_video_seedance_ref
    def video(*args,**kw):
        import subprocess
        import cb_provider_jobs
        out=video_provider(*args,**kw)
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=64x36:r=24','-f','lavfi','-i','anullsrc=r=24000:cl=mono','-t','6','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-y',str(out)],check=True,capture_output=True)
        contract = R.cb_providers.request_contract(
            fast=kw.get('fast', False), duration=kw['duration'], resolution=kw['resolution'],
            image_count=len(args[1]), audio_count=len(kw.get('audio_urls') or []),
            video_count=len(kw.get('video_urls') or []), model_id=kw['model_id'])
        request_hash = cb_provider_jobs.fingerprint(contract, args[0], args[1],
            kw.get('audio_urls') or [], kw.get('video_urls') or [], int(kw['duration']),
            kw['resolution'], kw.get('generate_audio', True))
        task_id = 'synthetic-' + kw['request_id']
        cb_provider_jobs.save(str(out)+'.'+kw['request_id'], {
            'taskId':task_id, 'state':'downloaded', 'requestHash':request_hash,
            'outputHash':hashlib.sha256(Path(out).read_bytes()).hexdigest()})
        kw['progress_callback']({'event':'downloaded', 'taskId':task_id})
        return out
    monkeypatch.setattr(R.cb_gen,'generate_video_seedance_ref',video)
    monkeypatch.setattr(R.cb_gen,'last_frame',_REAL_LAST_FRAME)
    monkeypatch.setattr(R.cb_post,'replace_guide_dialogue',_REAL_AUDIO_CONFORM)
    import cb_llm
    def review_fixture(system,text,schema,**kw):
        from studio_prompt_quality import Assessment
        if schema is Assessment:
            prompt=json.loads(text)['prompt']
            value={name:{'score':8.5,'evidence':prompt.splitlines()[0],
                         'reason':'Synthetic craft review; not a quality claim.'}
                   for name in Assessment.model_fields if name not in ('critical_issues','improvements')}
            value.update(critical_issues=['Synthetic pacing concern remains advisory.'],improvements=[])
            return schema.model_validate(value)
        return schema.model_validate(_review_output('animation'))
    monkeypatch.setattr(cb_llm,'structured',review_fixture)
    monkeypatch.setattr(cb_llm,'structured_with_repair',review_fixture)
    sid=pkg['shots'][0]['shotId']
    R.regen_voice_shot('9',sid,'EpT',log=lambda *a:None)
    voice_status = R.voice_performance_status('9', sid, 'EpT')
    assert voice_status['takeMatchesCurrent'] is True
    R.approve_voice('9',sid,'EpT',reviewed_by='Fixture Producer',log=lambda *a:None)
    approved_pkg,_=R.load_pkg('9','EpT')
    approved_shot=R._shot(approved_pkg,sid)
    assert R._voice_approval_status(approved_pkg,approved_shot,'9','EpT')['current']
    # Finishing early inside the approved window is valid; revising that window
    # after approval must still require a timing repair.
    approved_shot['dialogueLines'][0]['endSec']+=1
    drift=R._voice_approval_status(approved_pkg,approved_shot,'9','EpT')
    assert not drift['current']
    assert drift['reason']
    R.keyframe_shot('9',sid,'EpT',log=lambda *a:None);R.select_keyframe_candidate('9',sid,'A','EpT',log=lambda *a:None);R.approve_keyframe('9',sid,'EpT',reviewed_by='Fixture Producer',log=lambda *a:None)
    _approve_animation_direction(sid)
    from studio_see_package import Package
    import studio_see_service
    scope=dict(projectId='crystal-bears',episode='EpT',scene='9',unit=sid)
    see = Package(root, scope)
    see.choose_storyboard(False, 'Fixture Producer')
    reviewed = studio_see_service.current(root, scope)
    studio_see_service.approve(root, scope, reviewed, 'Fixture Producer')
    import cb_episode_budget
    monkeypatch.setattr(cb_episode_budget,'status',lambda *a:{'remainingUsd':10})
    import cb_state
    def fixture_production_state(scene, episode):
        state = cb_state.production_state(scene, episode)
        # This legacy fixture intentionally bypasses script-lineage promotion. Isolate
        # the journey test to its already-approved media handoffs while preserving the
        # canonical phase shape and live ledger decisions.
        state['packageCurrent'] = True
        for row in state.get('shots', []):
            if row.get('shotId') != sid:
                continue
            current_pkg, _ = R.load_pkg(scene, episode)
            current_shot = R._shot(current_pkg, sid)
            current_ledger = R._ledger(current_pkg, sid)
            row['current'] = {
                'keyframe': bool((current_ledger.get('keyframeApproval') or {}).get('approved')),
                'voice': bool(R._voice_approval_status(
                    current_pkg, current_shot, scene, episode).get('current')),
                'animation': current_ledger.get('status') == 'approved',
            }
            row['kf'] = 'current' if row['current']['keyframe'] else 'missing'
            row['animState'] = current_ledger.get('status')
        return state
    server=SimpleNamespace(_canonical_cb_render=lambda:R, _production_state=fixture_production_state)
    adapter=Native(root,server)
    # Keep native operations intact; execute worker in-process for isolated module paths.
    def start(job,gate,sc,args):
        key,opid,step=args[-3:];state=StudioStore(root).read(key)
        result=perform(root,state['scope'],step,state['operation'],R,D)
        import cb_db
        cb_db.atomic_write_json(root,root/'cb-output/state/journeys'/f'{opid}_{step}.json',{**result,'operationId':opid,'step':step})
        return job
    server._start=start
    scope=dict(projectId='crystal-bears',episode='EpT',scene='9',unit=sid)
    J=Journey(StudioStore(root),adapter);v=J.view(scope);assert v['phase']=='audio',v
    J.accept(scope,dict(commandId='native-render-1',action=v['phase'],binding=v['binding'],expectedRevision=v['revision']),'Fixture Producer')
    for _ in range(20):
        J.tick(scope)
        if not J.view(scope)['busy']:break
    v=J.view(scope)
    assert not v['operation'].get('decision'),v['operation']
    assert v['phase']=='film'
    latest,_=R.load_pkg('9','EpT');envelope=R._ledger(latest,sid)['batch']['envelope']
    assert providers.fire_calls[-1]['prompt']==envelope['executionPlan']['segments'][0]['prompt']

    J.accept(scope,dict(commandId='native-approve-2',action=v['phase'],binding=v['binding'],expectedRevision=v['revision']),'Fixture Producer')
    cut_reviewed = False
    for _ in range(16):
        J.tick(scope)
        if single_shot_scene and not cut_reviewed:
            current, _ = R.load_pkg('9', 'EpT')
            if R._ledger(current, sid).get('status') == 'approved':
                _approve_director_review('review-animation', sid)
                _lock_scene_cut('9', 'EpT')
                cut_reviewed = True
        if not J.view(scope)['busy']:break
    v=J.view(scope);assert v['phase']=='complete' and not v['operation'].get('decision'),json.dumps(v['operation'].get('decision'))
    latest,_=R.load_pkg('9','EpT');ledger=R._ledger(latest,sid)
    assert Path(ledger['harvestFrame']).is_file()
    if single_shot_scene:
        post = R.post_status(latest, '9', 'EpT')
        assert post['candidate']['current']
        _approve_director_review('review-final')
        final, _ = R.load_pkg('9', 'EpT')
        assert R.post_status(final, '9', 'EpT')['approved']['current']
    else:
        assert v['next']['unit']==latest['shots'][1]['shotId']
