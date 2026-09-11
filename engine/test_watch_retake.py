from copy import deepcopy
import pytest
import cb_render as R
import cb_studio_director as D

@pytest.fixture
def retake(monkeypatch):
    ledger={'status':'candidates-pending','batchId':'batch1','candidatePaths':['take'], 'pendingSpendAuth':{'token':'old'},'voPath':'approved.wav','voiceApproval':{'hash':'audio'},'keyframeApproval':{'hash':'image'}}
    pkg={'ledger':ledger};calls=[]
    monkeypatch.setattr(R,'load_pkg',lambda *a:(pkg,'fixture'))
    monkeypatch.setattr(R,'_ledger',lambda *a:ledger)
    monkeypatch.setattr(R,'_save',lambda *a:None)
    monkeypatch.setattr(R,'save_watch_director_feedback',lambda *a,**k:calls.append('feedback'))
    def reject(*a,**kw):
        calls.append('archive');ledger.update(status='designed',candidatePaths=None)
    monkeypatch.setattr(R,'reject_shot',reject)
    monkeypatch.setattr(R,'restore_seedance_working',lambda *a:calls.append('clear-old-prompt'))
    monkeypatch.setattr(R,'prepare_department',lambda scene,stage,*a:calls.append(stage))
    monkeypatch.setattr(R,'recompile_animation_candidate',lambda *a:calls.append('bind-current-opening-and-references'))
    def prepare(*a):
        calls.append('normal-pre-fire');ledger['pendingSpendAuth']={'token':'new'}
    monkeypatch.setattr(D,'prepare_render',prepare)
    return ledger,calls

def test_retake_rebuilds_then_enters_normal_pre_fire_preserving_approved_media(retake):
    ledger,calls=retake;voice=deepcopy(ledger['voiceApproval']);image=deepcopy(ledger['keyframeApproval'])
    D.retake_render('1','S1.SH2','Keep audio; fix object state','Ep3',lambda *a:None,expected_batch_id='batch1')
    assert calls==['feedback','archive','clear-old-prompt','cinematography','animation','bind-current-opening-and-references','normal-pre-fire']
    assert ledger['watchRetake']['status']=='ready'
    assert ledger['voiceApproval']==voice and ledger['keyframeApproval']==image
    assert ledger['pendingSpendAuth']['token']=='new'

def test_failed_retake_keeps_note_and_resumes_without_second_rejection(retake,monkeypatch):
    ledger,calls=retake
    def fail(*a):raise RuntimeError('Missing current reference')
    monkeypatch.setattr(D,'prepare_render',fail)
    with pytest.raises(RuntimeError):D.retake_render('1','S1.SH2','Fix state','Ep3',lambda *a:None,expected_batch_id='batch1')
    assert ledger['watchRetake']['status']=='needs-attention'
    assert ledger['watchRetake']['note']=='Fix state' and ledger['pendingSpendAuth'] is None
    with pytest.raises(RuntimeError):D.retake_render('1','S1.SH2','Fix state','Ep3',lambda *a:None,expected_batch_id='batch1')
    assert calls.count('archive')==1

def test_blank_retake_changes_nothing(retake):
    ledger,calls=retake;before=deepcopy(ledger)
    with pytest.raises(R.Refused):D.retake_render('1','S1.SH2',' ','Ep3')
    assert ledger==before and not calls

def test_stale_batch_cannot_reject_a_new_take(retake):
    ledger,calls=retake;before=deepcopy(ledger)
    with pytest.raises(R.Refused,match='changed'):
        D.retake_render('1','S1.SH2','Change state','Ep3',expected_batch_id='old-batch')
    assert ledger==before and not calls


def test_prompt_director_timeout_retries_preparation_only(retake, monkeypatch):
    ledger, calls = retake
    attempts = []
    def prepare(*a):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError('Director provider error (prompt_director): APITimeoutError: Request timed out')
        ledger['pendingSpendAuth'] = {'token':'new'}
    monkeypatch.setattr(D, 'prepare_render', prepare)
    D.retake_render('1','S1.SH2','Fix vision','Ep3',lambda *a:None,expected_batch_id='batch1')
    assert len(attempts) == 2
    assert calls.count('archive') == 1
    assert ledger['watchRetake']['status'] == 'ready'


def test_uncertain_media_submission_is_never_retried(retake, monkeypatch):
    ledger, calls = retake
    attempts = []
    def prepare(*a):
        attempts.append(1)
        raise RuntimeError('Submission outcome is unknown: request timed out')
    monkeypatch.setattr(D, 'prepare_render', prepare)
    with pytest.raises(RuntimeError):
        D.retake_render('1','S1.SH2','Fix vision','Ep3',lambda *a:None,expected_batch_id='batch1')
    assert len(attempts) == 1
    assert ledger['watchRetake']['status'] == 'needs-attention'
