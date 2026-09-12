"""Regressions for the three fresh-script Ep3 test failures; no provider calls."""
from types import SimpleNamespace as NS
from copy import deepcopy
import pytest
import cb_creative as C
from test_cb_creative import _beat, _card, _performance_contract, _scene, _treatment
import cb_handover as H
from test_cb_handover import _storyboard, _physical_comedy_staging


@pytest.mark.parametrize('carrier_count', [0, 1, 2])
def test_payoff_selection_survives_saved_storyboard_handover(carrier_count):
    storyboard = _storyboard()
    staging = _physical_comedy_staging()
    beat = storyboard['beats'][0]
    beat['comedyContract'].update(mode='BIG', physicalStaging=staging)
    first = storyboard['shots'][0]
    second = deepcopy(first)
    second['shotId'] = 'S1.SH2'
    storyboard['shots'] = [first, second]
    for index, shot in enumerate([second, first]):
        shot['performanceContract']['comedyStaging'] = staging if index < carrier_count else None
    if carrier_count != 1:
        with pytest.raises(H.HandoverRefused, match='unique packed-unit carrier'):
            H._validate_supervision_contracts(storyboard)
        return
    H._validate_supervision_contracts(storyboard)
    assert H._owned_big_comedy_stagings(storyboard, first) == []
    assert H._owned_big_comedy_stagings(storyboard, second) == [
        {'beatCode': beat['beatId'], **staging}]


def test_two_units_can_share_beat_with_one_explicit_comedy_payoff(monkeypatch):
    beat = _beat()
    staging = NS(model_copy=lambda **kwargs: None)
    beat.comedyContract.mode = 'BIG'
    beat.comedyContract.physicalStaging = staging
    shots = [_card('S1.SH1'), _card('S1.SH2')]
    response = C.PerformancePass(
        shots=[C.PerformanceCard(shotId=s.shotId,
            physicalPerformance='Wings settle.', animationTiming='Hold the landing.',
            performanceContract=_performance_contract()) for s in shots],
        comedyCarriers=[C.ComedyCarrier(beatId='1.B1', shotId='S1.SH2')])
    monkeypatch.setattr(C.cb_llm, 'structured_with_repair', lambda *a, **k: response)
    result = C.gate5_performance('Ep1', 1, _treatment('A'),
        C.SceneDirection(scene=_scene(), beats=[beat]), shots)
    assert [s.shotId for s in result] == ['S1.SH1', 'S1.SH2']
    assert all(s.performanceContract.beatOwner == '1.B1' for s in result)


def test_power_bearer_description_reaches_existing_repair_path(monkeypatch):
    beat = _beat()
    beat.powerMoment = NS(bearer='Fuzzby with Zenny joining')
    calls = []
    def respond(system, user, *args, **kwargs):
        calls.append(user)
        if len(calls) == 2:
            raise LookupError('repair reached')
        return NS(beats=[beat])
    monkeypatch.setattr(C.cb_llm, 'structured_with_repair', respond)
    with pytest.raises(LookupError, match='repair reached'):
        C.gate3_beats('Ep1', 1, {}, _treatment('A'), _treatment('A'),
            {'beats': [], 'cast': ['Fuzzby']})
    assert 'powerMoment.bearer' in calls[1]
    assert 'use exactly one participating character' in calls[1]


def test_missing_allocated_view_gets_local_repair_before_upstream(monkeypatch):
    conference = NS(shots=[_card()], model_dump_json=lambda: '{}')
    monkeypatch.setattr(C.cb_llm, 'structured_with_repair', lambda *a, **k: conference)
    calls = []
    def repair(*args, **kwargs):
        calls.append(args)
        raise LookupError('local repair reached')
    monkeypatch.setattr(C.cb_llm, 'repair_call', repair)
    def invalid(*args):
        raise C.CoverageAllocationError(
            'Camera allocation needs the preceding scene viewId for S6.SH1')
    monkeypatch.setattr(C, '_validate_scene_view_allocation', invalid)
    with pytest.raises(LookupError, match='local repair reached'):
        C.gate4_shot_conference('Ep1', 1,
            NS(governingAudienceExperience='Delight'), _treatment('A'),
            C.SceneDirection(scene=_scene(), beats=[_beat()]))
    assert len(calls) == 1


def test_missing_character_truth_requests_one_repair_then_stops(monkeypatch):
    contract = _performance_contract()
    contract.characterTruths = []
    response = C.PerformancePass(shots=[C.PerformanceCard(shotId='S1.SH1',
        physicalPerformance='Wings settle.', animationTiming='Hold.',
        performanceContract=contract)])
    calls=[]
    def respond(*args, **kwargs):
        calls.append(args[1]); return response
    monkeypatch.setattr(C.cb_llm,'structured_with_repair',respond)
    with pytest.raises(RuntimeError,match='MISSING CHARACTER TRUTH'):
        C.gate5_performance('Ep1',1,_treatment('A'),
            C.SceneDirection(scene=_scene(),beats=[_beat()]),[_card()])
    assert len(calls)==2
    assert 'Supply canon-grounded characterTruths' in calls[1]


def test_timing_identity_resolves_only_unique_exact_namespace_omission():
    full = 'dialogue-occurrence:sha256:abc'
    assert C._resolve_timing_occurrence('sha256:abc', [full]) == full
    assert C._resolve_timing_occurrence('sha256:abc', [full, full]) == 'sha256:abc'
    assert C._resolve_timing_occurrence('sha256:ab', [full]) == 'sha256:ab'
    assert C._resolve_timing_occurrence(full, [full]) == full
