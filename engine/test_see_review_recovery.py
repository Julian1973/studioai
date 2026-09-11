"""Approval-time SEE translation is review evidence, never a source revision."""
from copy import deepcopy
from types import SimpleNamespace
import ast
from pathlib import Path
import cb_render as R
import studio_director_handoff as H
import studio_keyframe_director as K
import cb_llm


def test_readiness_preparation_does_not_mutate_generation_inputs(monkeypatch,tmp_path):
    shot={'shotId':'X','storyboardInternalShotPlanApproved':[{'viewId':'v'}]}
    ledger={};pkg={'shots':[shot]};before=deepcopy(shot)
    monkeypatch.setattr(R,'load_pkg',lambda *a:(pkg,tmp_path/'package.json'))
    monkeypatch.setattr(R,'_shot',lambda p,*a:p['shots'][0])
    monkeypatch.setattr(R,'_sha256_file',lambda *a:'imagehash')
    monkeypatch.setattr(R,'_save',lambda *a:None)
    def prepare(runtime,*args,package,opening_image,**kwargs):
        assert opening_image=='candidate.png'
        package[0]['shots'][0]['directorCard']={'views':[{'viewId':'v'}]}
        runtime._save(*package)
    monkeypatch.setattr(H,'prepare_native',prepare)
    monkeypatch.setattr(R,'_see_readiness_source',lambda *a:{'references':[]})
    monkeypatch.setattr(K,'require',lambda source,report:None if report else (_ for _ in ()).throw(ValueError('missing')))
    monkeypatch.setattr(K,'assess',lambda *a:{'verdict':'READY'})
    R.review_see_action_readiness(pkg,shot,ledger,'candidate.png','2','Ep3')
    assert shot==before
    assert ledger['seeDirectorHandoff']['shot']['directorCard']['views']
    assert ledger['seeActionReadiness']['verdict']=='READY'


def test_rejection_reason_reaches_active_keyframe_compiler():
    tree=ast.parse((Path(__file__).parent/'cb_safety.py').read_text())
    fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='keyframe_prompt')
    ledger={'keyframeRejections':[{'reason':'Keep the pool clear; move Aida left.'}]}
    ns={'current_direction_output':lambda *a:{},
        'm':SimpleNamespace(_ledger=lambda *a:ledger,_compile_keyframe_integration_prompt=lambda *a:'AUTHORED PROMPT\n\n[LIGHTING]\nCamera direction'),
        'studio_prompt_aliases':SimpleNamespace(protect_honeycomb_aliases=lambda p,s:p)}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'active-compiler','exec'),ns)
    result=ns['keyframe_prompt']({}, {'shotId':'X'})
    assert 'Keep the pool clear; move Aida left.' in result
    assert result.startswith('AUTHORED PROMPT')


def test_retake_preserves_ordered_sections_and_ignores_admin_invalidation():
    tree=ast.parse((Path(__file__).parent/'cb_safety.py').read_text())
    fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='keyframe_prompt')
    base='\n\n'.join(f'[{name}]\nAuthored {name}' for name in R.SEEDREAM_KEYFRAME_PROMPT_SECTIONS)
    ledger={'keyframeRejected':{'reason':'Superseded automatically','category':'stale-inputs'}}
    ns={'current_direction_output':lambda *a:{},
        'm':SimpleNamespace(_ledger=lambda *a:ledger,_compile_keyframe_integration_prompt=lambda *a:base),
        'studio_prompt_aliases':SimpleNamespace(protect_honeycomb_aliases=lambda p,s:p)}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'active-compiler','exec'),ns)
    assert ns['keyframe_prompt']({}, {'shotId':'X'})==base
    ledger['keyframeRejected']={'reason':'Move Sunny left.\nKeep the cups straight.'}
    result=ns['keyframe_prompt']({}, {'shotId':'X'})
    sections=R.cb_departments.prompt_sections(result)
    assert tuple(sections)==R.SEEDREAM_KEYFRAME_PROMPT_SECTIONS
    assert 'Move Sunny left. Keep the cups straight.' in sections['COMPOSITION']


def test_human_image_approval_preserves_blocked_watch_evidence_without_model_call(tmp_path):
    tree=ast.parse((Path(__file__).parent/'cb_render.py').read_text())
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='approve_keyframe')
    image=tmp_path/'uploaded.png';image.write_bytes(b'approved pixels')
    readiness={'verdict':'BLOCKED','summary':'Opening action needs reconciliation'}
    ledger={'keyframeCandidate':{'path':str(image),'source':'uploaded'},
            'seeActionReadiness':deepcopy(readiness)}
    pkg={'shots':[{'shotId':'S3.SH1'}]};saved=[]
    def forbidden(*a,**k):raise AssertionError('Image approval must not run a model')
    ns={'load_pkg':lambda *a:(pkg,tmp_path/'pkg.json'), '_shot':lambda *a:pkg['shots'][0],
        '_ledger':lambda *a:ledger,'Refused':ValueError,'_now':lambda:'now',
        '_save':lambda *a:saved.append(deepcopy(ledger)),
        'review_see_action_readiness':forbidden}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'approve-image','exec'),ns)
    assert ns['approve_keyframe']('3','S3.SH1','Ep3',log=lambda *a:None)==str(image)
    assert ledger['keyframeApproval']['approved'] is True
    assert ledger['keyframeApproval']['path']==str(image)
    assert ledger['keyframeCandidate'] is None
    assert ledger['seeActionReadiness']==readiness and len(saved)==1


def test_watch_submission_still_requires_current_see_action_readiness():
    source=(Path(__file__).parent/'cb_render.py').read_text()
    assert 'require_see_readiness(_see_readiness_source(pkg, shot, led, opening, scene, episode), led.get("seeActionReadiness"))' in source
