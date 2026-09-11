import ast
import pathlib
import shutil
import uuid
import os
from copy import deepcopy
import pytest

def run_selector(tmp_path, missing=False):
    tree=ast.parse(pathlib.Path(__file__).with_name('cb_render.py').read_text())
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='select_keyframe_source')
    old=tmp_path/'old.png';old.write_bytes(b'old')
    source=tmp_path/'new.png'
    if not missing: source.write_bytes(b'new')
    led={'keyframeCandidate':{'path':str(old)},'keyframeApproval':{'approved':True,'path':'protected'}}
    saved=[]
    def copy(src,*args):
        dest=tmp_path/'candidate.png';shutil.copy2(src,dest);return str(dest)
    ns=dict(os=os,pathlib=pathlib,shutil=shutil,uuid=uuid,HERE=tmp_path,Refused=ValueError,
        load_pkg=lambda *a:({},'pkg'),_shot=lambda *a:{},_ledger=lambda *a:led,
        _require_current_scenelook=lambda *a:None,_immutable_candidate_copy=copy,
        _now=lambda:'now',_save=lambda *a:saved.append(deepcopy(led)))
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'selector','exec'),ns)
    return ns['select_keyframe_source'],source,old,led,saved

def test_upload_replaces_pending_preserving_history_and_approval(tmp_path):
    fn,source,old,led,saved=run_selector(tmp_path)
    fn('3','S3.SH1','upload','EpT',upload_path=str(source),log=lambda *a:None)
    assert pathlib.Path(led['keyframeCandidate']['path']).read_bytes()==b'new'
    assert led['keyframeHistory'][0]['path']==str(old)
    assert old.read_bytes()==b'old'
    assert led['keyframeApproval']=={'approved':True,'path':'protected'}
    assert len(saved)==1

def test_missing_upload_keeps_pending_candidate(tmp_path):
    fn,source,old,led,saved=run_selector(tmp_path,True)
    with pytest.raises(ValueError):fn('3','S3.SH1','upload','EpT',upload_path=str(source))
    assert led['keyframeCandidate']['path']==str(old)
    assert not saved and 'keyframeHistory' not in led


def test_upload_retires_generated_comparison(tmp_path):
    fn,source,old,led,saved=run_selector(tmp_path)
    led['keyframeCandidates']=[{'candidateId':'A','path':'a.png'},{'candidateId':'B','path':'b.png'}]
    led['selectedKeyframeCandidateId']='A'
    fn('3','S3.SH1','upload','EpT',upload_path=str(source),log=lambda *a:None)
    assert 'keyframeCandidates' not in led and 'selectedKeyframeCandidateId' not in led
    assert [x.get('candidateId') for x in led['keyframeHistory']]==[None,'A','B']
    assert led['keyframeApproval']['path']=='protected'


def test_generated_comparison_still_needs_selection():
    from studio_keyframe_selection import retire_comparison
    led={'keyframeCandidates':[{'candidateId':'A'},{'candidateId':'B'}]}
    before=deepcopy(led)
    assert not retire_comparison(led,source='generated',at='now',reviewer='Test')
    assert led==before
