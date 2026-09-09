import hashlib
import json
import pytest
import cb_post_workspace as post
import cb_finishing as finish
import cb_vcube

@pytest.fixture
def candidate(tmp_path, monkeypatch):
    folder=tmp_path/'media/post95/Ep2_episode';folder.mkdir(parents=True)
    master=folder/'review.mp4';master.write_bytes(b'exact review cut')
    sha=post._sha256(master)
    manifest={'masterSha256':sha,'durationSec':120,'outputs':{'master':str(master)},
              'finishingWorkflow':{'drive':{'verified':True,'masterSha256':sha,'url':'https://drive.google.com/file/d/test/view'}}}
    path=folder/'review_manifest.json';path.write_text(json.dumps(manifest))
    monkeypatch.setattr(post,'POST_ROOT',folder.parent)
    monkeypatch.setattr(post,'MEDIA_ROOT',tmp_path/'media')
    monkeypatch.setattr(post,'STATE_ROOT',tmp_path/'state')
    monkeypatch.setattr(cb_vcube,'config',lambda:{'ak':'test','sk':'test','space':'test','rate':'1','costsVerified':True})
    return sha,path,manifest

def test_signoff_rejects_stale_file_and_unverified_google(candidate):
    sha,path,m=candidate
    with pytest.raises(ValueError,match='version changed'): post.record_verdict('Ep2','approved',expected_hash='stale')
    m['finishingWorkflow']['drive']['verified']=False;path.write_text(json.dumps(m))
    with pytest.raises(ValueError,match='Google Drive'): post.record_verdict('Ep2','approved',expected_hash=sha)

def test_upscale_is_locked_until_exact_approval_and_allowance(candidate):
    sha,_,_=candidate
    with pytest.raises(ValueError,match='Approve'): finish.reserve('Ep2',sha,10)
    post.record_verdict('Ep2','approved',expected_hash=sha)
    for cap in [1, float('nan'), float('inf')]:
        with pytest.raises(ValueError,match='allowance'): finish.reserve('Ep2',sha,cap)
    first=finish.reserve('Ep2',sha,2)
    assert first==finish.reserve('Ep2',sha,2)

def test_network_uncertainty_never_resubmits(candidate,monkeypatch):
    sha,_,_=candidate
    post.record_verdict('Ep2','approved',expected_hash=sha);finish.reserve('Ep2',sha,2)
    monkeypatch.setattr(cb_vcube,'upload',lambda path:'verified-vid')
    calls=[]
    def timeout(body): calls.append(body);raise TimeoutError()
    monkeypatch.setattr(cb_vcube,'start',timeout)
    finish.run('Ep2',sha);finish.run('Ep2',sha)
    assert len(calls)==1
    job=json.loads(finish.job_path('Ep2').read_text())
    assert job['status']=='needs-reconciliation' and job['request']['Control']['ClientToken']

def test_changed_candidate_cannot_inherit_approval(candidate):
    sha,path,m=candidate
    post.record_verdict('Ep2','approved',expected_hash=sha)
    master=path.parent/'new.mp4';master.write_bytes(b'new edit')
    m['outputs']['master']=str(master);m['masterSha256']=post._sha256(master);path.write_text(json.dumps(m))
    assert post.workspace('Ep2')['status']=='review-required'
    with pytest.raises(ValueError): finish.reserve('Ep2',sha,2)

def test_request_uses_documented_vcube_and_preserves_cadence(candidate):
    body=cb_vcube.payload('vid',candidate[0]);moe=body['Operation']['Task']['Enhance']['MoeEnhance']
    assert moe=={'Config':'aigc','Target':{'Res':'4k','Fps':30,'BitDepth':10},'VideoStrategy':{'RepairStrength':0,'EnhanceLevel':'Pro'}}
    assert body['Control']['ClientToken']==cb_vcube.payload('vid',candidate[0])['Control']['ClientToken']


def test_post_brief_is_candidate_bound_and_has_no_side_effects(candidate, monkeypatch):
    sha, path, _ = candidate
    before = path.read_bytes()
    def forbidden(*args, **kwargs):
        raise AssertionError('A review brief must not execute external operations')
    monkeypatch.setattr(finish, 'resolve_snapshot', forbidden)
    monkeypatch.setattr(cb_vcube, 'upload', forbidden)
    monkeypatch.setattr(cb_vcube, 'start', forbidden)
    brief = finish.director_brief('Ep2', sha)
    assert brief['masterSha256'] == sha and brief['reviewType'] == 'brief-only'
    assert brief['postSupervisorContract'] and brief['directorContract']
    assert {'sound.md', 'editorial.md', 'colour-qc-delivery.md', 'studio-and-mcp.md'} <= brief['postSupervisorReferences'].keys()
    assert path.read_bytes() == before
    assert post.workspace('Ep2')['status'] != 'approved'
    assert not finish.job_path('Ep2').exists()
    assert brief['sourceRecords'] is None and 'not registered' in brief['sourceEvidence']
    with pytest.raises(ValueError, match='version changed'):
        finish.director_brief('Ep2', 'stale')


def test_registered_source_direction_reaches_post_without_reinterpreting_it(candidate):
    sha,path,manifest=candidate
    manifest['sourceRecords']={'sha256':'source-record-hash','shots':[{'id':'S1.SH1',
        'directionContext':{'storyboardInternalShotPlanApproved':[{'performanceFocus':'Listen before answering'}]},
        'directionEvidence':'Current context, not historical render proof'}]}
    path.write_text(json.dumps(manifest))
    assert finish.director_brief('Ep2',sha)['sourceRecords']==manifest['sourceRecords']


@pytest.mark.parametrize('verdict', ['approved', 'APPROVED', ' Approved '])
def test_signoff_normalization_cannot_bypass_receipt(candidate, verdict):
    sha, path, manifest = candidate
    manifest['finishingWorkflow']['drive']['verified'] = False
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='Google Drive'):
        post.record_verdict('Ep2', verdict, expected_hash=sha)
    assert not post._verdict_path('Ep2').exists()


def test_concurrent_review_decisions_preserve_every_receipt(candidate):
    from concurrent.futures import ThreadPoolExecutor
    sha, _, _ = candidate
    def reject(index):
        post.record_verdict('Ep2', 'rejected', note=f'Repair {index}', expected_hash=sha)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(reject, range(20)))
    history = [json.loads(line) for line in post._verdict_history_path('Ep2').read_text().splitlines()]
    assert {row['note'] for row in history} == {f'Repair {i}' for i in range(20)}
    assert len(history) == 20
    assert post.workspace('Ep2')['verdict'] == history[-1]


def test_history_is_selected_by_legacy_scope_not_episode_number():
    from studio_post_contract import contracts
    assert 'episode2-evidence.md' in contracts(legacy_episode='Ep2')['postSupervisorReferences']
    assert 'episode2-evidence.md' not in contracts(legacy_episode='Ep3')['postSupervisorReferences']
    assert 'episode2-evidence.md' not in contracts()['postSupervisorReferences']
    with pytest.raises(ValueError, match='legacy Crystal Bears'):
        post.require_legacy_project('another-ip')


def test_resolve_binding_does_not_confuse_matching_names_with_identity(candidate):
    sha, _, _ = candidate
    w = {'masterSha256': sha, 'finishingWorkflow': {'resolveProject':'Film', 'resolveTimeline':'Cut'}}
    live = {'project':'Film', 'timeline':'Cut', 'projectId':'p1', 'timelineId':'t1'}
    assert finish.resolve_binding(w, live)['status'] == 'names-only'
    w['finishingWorkflow']['resolveSnapshot'] = {'projectId':'p1', 'timelineId':'t2'}
    assert finish.resolve_binding(w, live)['status'] == 'mismatch'
    w['finishingWorkflow']['resolveSnapshot']['timelineId'] = 't1'
    assert finish.resolve_binding(w, live)['status'] == 'identity-match'
    live['projectId'] = 'other-project'
    assert finish.resolve_binding(w, live)['status'] == 'mismatch'


def test_candidate_changed_while_resolve_is_read_is_refused(candidate, monkeypatch):
    from types import SimpleNamespace
    sha, path, manifest = candidate
    def snapshot(*args, **kwargs):
        master = path.parent / 'newer.mp4'
        master.write_bytes(b'newer candidate')
        manifest['outputs']['master'] = str(master)
        manifest['masterSha256'] = post._sha256(master)
        path.write_text(json.dumps(manifest))
        return SimpleNamespace(returncode=0, stdout='{}')
    monkeypatch.setattr(finish.subprocess, 'run', snapshot)
    with pytest.raises(ValueError, match='version changed'):
        finish.resolve_snapshot('Ep2', sha)
