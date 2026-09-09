import copy
import pytest
from cb_candidate_handoff import resolve, sha


def fixture(tmp_path):
    video=tmp_path/'candidate.mp4';video.write_bytes(b'candidate bytes')
    frame=tmp_path/'frame.png';frame.write_bytes(b'exact last frame')
    shot={'shotId':'S1.SH2','shotTransition':{'type':'cut','stateSourceShotId':'S1.SH1'}}
    record=dict(sourceShotId='S1.SH1',targetShotId='S1.SH2',sourcePath=str(video),sourceHash=sha(video),
        framePath=str(frame),frameHash=sha(frame),batchId='batch',authorization='Refire both as candidates',humanApproval=False)
    pkg={'continuityLedger':[{'shotId':'S1.SH1','status':'candidates-pending','candidatePaths':[str(video)],'batchId':'batch'},
        {'shotId':'S1.SH2','candidateStateSource':record}]}
    return pkg,shot,video,frame


def test_explicit_candidate_continuity_does_not_approve(tmp_path):
    pkg,shot,_,frame=fixture(tmp_path);before=copy.deepcopy(pkg)
    assert resolve(pkg,shot)==str(frame)
    assert pkg==before and pkg['continuityLedger'][0]['status']=='candidates-pending'


@pytest.mark.parametrize('change',['video','frame','batch','rejected','target','authorization'])
def test_candidate_continuity_rejects_changed_or_unauthorised_source(tmp_path,change):
    pkg,shot,video,frame=fixture(tmp_path)
    if change=='video': video.write_bytes(b'other take')
    elif change=='frame': frame.write_bytes(b'other frame')
    elif change=='batch': pkg['continuityLedger'][0]['batchId']='replacement'
    elif change=='rejected': pkg['continuityLedger'][0]['status']='rejected'
    elif change=='target': shot['shotId']='S1.SH3'
    else: pkg['continuityLedger'][1]['candidateStateSource']['authorization']=''
    with pytest.raises(ValueError): resolve(pkg,shot)
