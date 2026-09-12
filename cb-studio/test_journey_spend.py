from pathlib import Path
import sys
import pytest
sys.path.insert(0,'/Users/julianjenkins/Desktop/Ai Studio/engine')
from studio_journey_worker import spending
from studio_journey import DecisionRequired
import cb_episode_budget as budget


def op(limit=1,services=None):
    return {'id':'fixture-operation','grant':{'limitUsd':limit,'operations':services or ['direction','animation'],'maxMediaCalls':1}}


def test_total_limit_covers_models_and_render(tmp_path,monkeypatch):
    calls=[];monkeypatch.setattr(budget,'reserve',lambda *a:calls.append(a))
    with spending(tmp_path,op()):
        budget.reserve('Ep1',.4,'text:director')
        with pytest.raises(DecisionRequired):budget.reserve('Ep1',.7,'animation')
    assert len(calls)==1


def test_media_retry_cannot_charge_again_after_restart(tmp_path,monkeypatch):
    calls=[];monkeypatch.setattr(budget,'reserve',lambda *a:calls.append(a))
    with spending(tmp_path,op()):budget.reserve('Ep1',.1,'animation')
    with spending(tmp_path,op()):
        with pytest.raises(DecisionRequired):budget.reserve('Ep1',.1,'animation')
    assert len(calls)==1


def test_scope_excludes_undisclosed_voice(tmp_path,monkeypatch):
    calls=[];monkeypatch.setattr(budget,'reserve',lambda *a:calls.append(a))
    with spending(tmp_path,op()):
        with pytest.raises(DecisionRequired):budget.reserve('Ep1',.1,'voice')
    assert calls==[]


def test_failed_evidence_write_prevents_provider_reservation(tmp_path,monkeypatch):
    import cb_db
    calls=[];monkeypatch.setattr(budget,'reserve',lambda *a:calls.append(a))
    monkeypatch.setattr(cb_db,'atomic_write_json',lambda *a,**k:(_ for _ in ()).throw(OSError('disk full')))
    with spending(tmp_path,op()):
        with pytest.raises(OSError):budget.reserve('Ep1',.1,'animation')
    assert calls==[]
