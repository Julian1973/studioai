"""WATCH preparation migrates legacy direction before pure readiness, never Fire."""
from unittest.mock import Mock
import pytest
import cb_render as R
import cb_studio_director as D
import studio_director_handoff as H
import studio_see_service as S
import cb_recovery


def test_legacy_dot_character_ids_match_current_cast():
    from studio_character_roles import character_id
    assert character_id('char.Sunny') == character_id('Sunny') == character_id('char:Sunny')
    assert character_id('prop.Sunny') != character_id('Sunny')


@pytest.mark.parametrize('images,voice,expected', [(True,True,'ready'),(False,True,'images'),(True,False,'voice')])
def test_handoff_order_and_approved_input_guards(monkeypatch, images, voice, expected):
    shot={'shotId':'S3.SH1','storyboardInternalShotPlanApproved':[{'viewId':'v1'}],
          'dialogueLines':[{'speaker':'Sunny','exactText':'Hello.'}]}
    pkg={'shots':[shot],'continuityLedger':[{'shotId':'S3.SH1'}]}
    calls=[]
    monkeypatch.setattr(R,'load_pkg',lambda *a:(pkg,None))
    monkeypatch.setattr(R,'_require_valid',lambda *a:None)
    monkeypatch.setattr(R,'_require_current_lineage',lambda *a:None)
    monkeypatch.setattr(cb_recovery,'require_no_provider_operation',lambda *a:None)
    monkeypatch.setattr(S,'context',lambda *a:{'componentReviews':{'plate':'approved','opening':'approved' if images else 'pending'}})
    monkeypatch.setattr(R,'_voice_approval_status',lambda *a:{'current':voice})
    monkeypatch.setattr(H,'prepare_native',lambda *a,**k:calls.append('handoff'))
    def readiness(*a):
        calls.append('readiness')
        raise R.Refused('stop before request preparation')
    monkeypatch.setattr(D,'watch_readiness',readiness)
    fire=Mock(side_effect=AssertionError('No provider dispatch'))
    monkeypatch.setattr(R,'fire_shot',fire)
    with pytest.raises(R.Refused):
        D.prepare_render('3','S3.SH1','Ep4')
    assert calls==(['handoff','readiness'] if expected=='ready' else [])
    fire.assert_not_called()
