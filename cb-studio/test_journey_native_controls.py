"""Existing native preparation/compiler/Fire/approval services on an isolated saved scene.

Golden-path fixtures supply synthetic canon and provider responses. The older fixture
has a documented lineage bypass, so this test does NOT qualify initial script promotion.
"""
from pathlib import Path
from types import SimpleNamespace
import json,pytest
from test_current_production_path import (_approve_specialist_inputs,_approve_scene_look,_sign_specialist_inputs,_approve_animation_direction,isolated_canon)
from test_golden_path import world,_review_output
import cb_render as R
import cb_studio_director as D
from studio_journey import Journey,StudioStore,scope_key
from studio_journey_native import Native
from studio_journey_worker import perform
_REAL_LAST_FRAME=R.cb_gen.last_frame
_REAL_AUDIO_CONFORM=R.cb_post.replace_guide_dialogue


def test_native_existing_approved_inputs_use_real_compiler_fire_and_approval(world,monkeypatch):
    providers,root,path=world
    monkeypatch.setattr(R,"ROOT",root)
    import studio_prompt_director
    monkeypatch.setattr(studio_prompt_director,"__file__",str(root/"engine/studio_prompt_director.py"))
    bank=R.cb_prompt_bank.bank_prompt
    monkeypatch.setattr(R.cb_prompt_bank,'bank_prompt',lambda **kw:bank(**kw,bank_path=root/'cb-output/prompt-bank/prompt_bank.jsonl'))
    import sys,types
    backup=types.ModuleType('tools.backup_media');backup.backup_one=lambda *a:None
    monkeypatch.setitem(sys.modules,'tools.backup_media',backup)
    pkg=json.loads(path.read_text());_approve_specialist_inputs(pkg);path.write_text(json.dumps(pkg));_approve_scene_look(root,pkg);_sign_specialist_inputs(pkg);path.write_text(json.dumps(pkg))
    # Generate real decodable fixture media at the external provider boundary.
    video_provider=R.cb_gen.generate_video_seedance_ref
    def video(*args,**kw):
        import subprocess
        out=video_provider(*args,**kw)
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=64x36:r=24','-f','lavfi','-i','anullsrc=r=24000:cl=mono','-t','6','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-y',str(out)],check=True,capture_output=True)
        return out
    monkeypatch.setattr(R.cb_gen,'generate_video_seedance_ref',video)
    monkeypatch.setattr(R.cb_gen,'last_frame',_REAL_LAST_FRAME)
    monkeypatch.setattr(R.cb_post,'replace_guide_dialogue',_REAL_AUDIO_CONFORM)
    import cb_llm
    monkeypatch.setattr(cb_llm,'structured',lambda system,text,schema,**kw:schema.model_validate(_review_output('animation')))
    sid=pkg['shots'][0]['shotId']
    R.regen_voice_shot('9',sid,'EpT',log=lambda *a:None);R.approve_voice('9',sid,'EpT',reviewed_by='Fixture Producer',log=lambda *a:None)
    R.keyframe_shot('9',sid,'EpT',log=lambda *a:None);R.select_keyframe_candidate('9',sid,'A','EpT',log=lambda *a:None);R.approve_keyframe('9',sid,'EpT',reviewed_by='Fixture Producer',log=lambda *a:None)
    _approve_animation_direction(sid)
    import cb_episode_budget
    monkeypatch.setattr(cb_episode_budget,'status',lambda *a:{'remainingUsd':10})
    server=SimpleNamespace(_canonical_cb_render=lambda:R)
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
    for _ in range(16):
        J.tick(scope)
        if not J.view(scope)['busy']:break
    v=J.view(scope);assert v['phase']=='complete' and not v['operation'].get('decision'),json.dumps(v['operation'].get('decision'))
    latest,_=R.load_pkg('9','EpT');ledger=R._ledger(latest,sid)
    assert Path(ledger['harvestFrame']).is_file()
    assert v['next']['unit']==latest['shots'][1]['shotId']
