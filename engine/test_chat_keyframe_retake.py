from contextlib import nullcontext
import pytest
import cb_outcome_chat as C

@pytest.mark.parametrize('valid,budget',[(True,True),(False,True),(True,False)])
def test_retake_uses_shared_build_without_approval(monkeypatch,valid,budget):
    calls=[]
    monkeypatch.setattr(C.budget,'status',lambda *a:{'approved':budget})
    monkeypatch.setattr(C.cb_db,'scene_lease',lambda *a:nullcontext())
    monkeypatch.setattr(C,'target',lambda *a:{'hash':'current' if valid else 'changed'})
    monkeypatch.setattr(C.R,'reject_keyframe',lambda *a,**k:calls.append(('reject',a,k)))
    monkeypatch.setattr(C.R,'build_keyframe',lambda *a,**k:calls.append(('build',a,k)))
    monkeypatch.setattr(C.R,'approve_keyframe',lambda *a,**k:pytest.fail('Never auto-approve'))
    if not valid or not budget:
        with pytest.raises(Exception):C.retake_keyframe('Ep3','3','S3.SH1','current','Put cups on table')
        assert calls==[]
    else:
        C.retake_keyframe('Ep3','3','S3.SH1','current','Put cups on table')
        assert [x[0] for x in calls]==['reject','build']
        assert calls[0][1][2]=='Put cups on table'
        assert calls[1][2]=={'compare':False}

def test_explicit_refire_intent_does_not_capture_discussion():
    assert C.intent('apply and refire keyframe')['kind']=='retake-keyframe'
    assert C.intent('Should we refire?') is None
