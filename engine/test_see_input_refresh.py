"""Execute the active SEE entry point without network or media generation."""
import ast
from pathlib import Path
from types import SimpleNamespace
import pytest

@pytest.mark.parametrize('stale,repair_ok', [(False,True),(True,True),(True,False)])
def test_changed_plate_refresh_precedes_provider(stale,repair_ok):
    tree=ast.parse((Path(__file__).parent/'cb_safety.py').read_text())
    fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='keyframe_shot')
    events=[]; state={'plate':'new','signed':'old' if stale else 'new'}
    def prepare(*args):
        events.append('prepare')
        if repair_ok: state['signed']=state['plate']
    def verify(*args):
        events.append('verify')
        if state['signed']!=state['plate']: raise ValueError('still stale')
    def provider(*args,**kwargs): events.append('provider');return 'candidate'
    ns={'current_package':lambda *a:(state,None),
        'department_record_status':lambda *a:{'current':state['signed']==state['plate']},
        'prepare_department':prepare,'current_direction_output':verify,
        'original':{'keyframe_shot':provider},
        'm':SimpleNamespace(load_pkg=lambda *a:(state,None),_shot=lambda *a:{},_ledger=lambda *a:{})}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'SEE-entry','exec'),ns)
    if stale and not repair_ok:
        with pytest.raises(ValueError,match='still stale'): ns['keyframe_shot']('3','S3.SH1','Ep3',lambda *a:None)
        assert events==['prepare','verify']
    else:
        assert ns['keyframe_shot']('3','S3.SH1','Ep3',lambda *a:None)=='candidate'
        assert events==(['prepare'] if stale else [])+['verify','provider']

@pytest.mark.parametrize('pending_old_candidate', [False, True])
def test_native_build_reaches_refresh_and_preserves_other_approved_work(monkeypatch,tmp_path,pending_old_candidate):
    import inspect
    import cb_render as R
    from copy import deepcopy
    tree=ast.parse((Path(__file__).parent/'cb_safety.py').read_text())
    fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='keyframe_shot')
    frame=tmp_path/'old.png';frame.write_bytes(b'old plate candidate')
    old={'path':str(frame),'inputSignature':{'plate':'old'},'contentHash':R._sha256_file(frame)}
    ledger={'shotId':'S3.SH1','keyframeApproval':{'approved':True,'path':'existing-approved.png'},
            'voApproval':{'approved':True,'hash':'keep-voice'}}
    if pending_old_candidate: ledger['keyframeCandidate']=old
    other={'shotId':'S3.SH2','keyframeApproval':{'approved':True,'hash':'keep-other'}}
    pkg={'shots':[{'shotId':'S3.SH1','sourceType':'opener'}],
         'validation':{'passed':True},'continuityLedger':[ledger,other]}
    protected=deepcopy((ledger['keyframeApproval'],ledger['voApproval'],other))
    state={'signed':'old'};events=[]
    monkeypatch.setattr(R,'load_pkg',lambda *a:(pkg,tmp_path/'package.json'))
    for name in ['_require_current_lineage','_require_confirmed_billing','_require_current_scenelook']:
        monkeypatch.setattr(R,name,lambda *a:None)
    monkeypatch.setattr(R,'_keyframe_input_signature',lambda *a:{'plate':'new'})
    monkeypatch.setattr(R,'_save',lambda *a:None)
    def prepare(*args):
        assert args[:4]==('3','cinematography','S3.SH1','Ep3')
        state['signed']='new';events.append('refresh')
    def verify(*args): assert state['signed']=='new';events.append('verify')
    def provider(*args,**kwargs): events.append('provider');return 'new candidate'
    ns={'current_package':lambda *a:(pkg,tmp_path/'package.json'),
        'department_record_status':lambda *a:{'current':state['signed']=='new'},
        'prepare_department':prepare,'current_direction_output':verify,
        'original':{'keyframe_shot':provider},'m':R}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'SEE-entry','exec'),ns)
    monkeypatch.setattr(R,'keyframe_shot',ns['keyframe_shot'])
    assert inspect.unwrap(R.build_keyframe)('3','S3.SH1','Ep3',lambda *a:None,compare=False)=='new candidate'
    assert events==['refresh','verify','provider']
    assert (ledger['keyframeApproval'],ledger['voApproval'],other)==protected
    if pending_old_candidate:
        assert ledger['keyframeSuperseded']==[old]
        assert ledger['keyframeCandidate'] is None
