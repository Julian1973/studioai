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


@pytest.mark.parametrize('changed',[None,'rejected','hash','batch'])
def test_protected_comparison_can_supply_explicit_draft_continuity_without_promotion(tmp_path,changed):
    pkg,shot,video,frame=fixture(tmp_path)
    source,target=pkg['continuityLedger']
    source.update(status='approved',approvedTake='original-approved.mp4',
        comparisonBatch={'batchId':'new-comparison','candidatePaths':[str(video)]},
        comparisonWork={'status':'candidate-pending','candidatePath':str(video),'candidateSha256':sha(video)})
    target['candidateStateSource'].update(sourceKind='protected-comparison',batchId='new-comparison')
    if changed=='rejected':source['comparisonWork']['status']='rejected'
    if changed=='hash':source['comparisonWork']['candidateSha256']='other'
    if changed=='batch':source['comparisonBatch']['batchId']='other'
    before=copy.deepcopy(pkg)
    if changed:
        with pytest.raises(ValueError):resolve(pkg,shot)
    else:assert resolve(pkg,shot)==str(frame)
    assert pkg==before and source['approvedTake']=='original-approved.mp4'
