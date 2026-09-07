from concurrent.futures import ThreadPoolExecutor
import pytest
import cb_episode_budget as B


def test_upload_requires_allowance_and_reapproval_does_not_reset_spending():
    assert not B.require_allowance('Ep3', 'script1')['approved']
    with pytest.raises(B.BudgetRefused):
        B.reserve('Ep3', .1, 'voice')
    B.approve('Ep3', 1, 'Julian', 'script1')
    key = B.reserve('Ep3', .7, 'voice')
    B.finish('Ep3', key, 'committed', .5)
    assert B.approve('Ep3', 1, 'Julian', 'script2')['remainingUsd'] == .5
    assert B.require_allowance('Ep3', 'script3')['remainingUsd'] == .5


def test_parallel_workers_cannot_reserve_over_episode_allowance():
    B.approve('Ep3', 1, 'Julian', 'script')
    def attempt(_):
        try:
            return B.reserve('Ep3', .6, 'render')
        except B.BudgetRefused:
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert len(list(filter(None, pool.map(attempt, range(8))))) == 1
    assert B.status('Ep3')['remainingUsd'] == .4


def test_unknown_submission_retains_allowance_and_refusal_makes_no_call():
    B.approve('Ep3', 1, 'Julian', 'script')
    calls = []
    def lost():
        calls.append(True)
        raise TimeoutError('response lost')
    with B.quote('Ep3', .7, 'render'):
        with pytest.raises(TimeoutError):
            B.call(lost)
        with pytest.raises(B.BudgetRefused):
            B.call(lost)
    assert calls == [True]
    assert B.status('Ep3')['unknownRequests'] == 1
    assert B.status('Ep3')['remainingUsd'] == .3


def test_recovered_provider_task_without_submission_is_not_charged():
    B.approve('Ep3', 1, 'Julian', 'script')
    @B.provider('render', lambda a: .9)
    def recovered(out):
        return 'existing task result'
    assert recovered('Ep3_S1.mp4') == 'existing task result'
    assert B.status('Ep3')['usedAndReservedUsd'] == 0


@pytest.mark.parametrize('amount', ['NaN', 'Infinity', '-1', '0'])
def test_invalid_allowance(amount):
    with pytest.raises(ValueError):
        B.approve('Ep3', amount, 'Julian', 'script')


def test_byteplus_budget_refusal_is_not_unknown_submission(monkeypatch, tmp_path):
    import cb_gen as G
    import cb_provider_jobs as J
    B.require_allowance('Ep3', 'script')
    monkeypatch.setattr(G, 'BYTEPLUS_ARK_KEY', 'fixture-credential')
    monkeypatch.setattr(G, 'MEDIA', tmp_path)
    monkeypatch.setattr(G.requests, 'post', lambda *a, **kw: pytest.fail('Budget refused before POST'))
    contract = {'providerModelId': 'fixture', 'endpoint': '/api/v3/contents/generations/tasks',
                'mode': 'reference-to-video', 'costRateKey': 'fixture'}
    monkeypatch.setattr(G.cb_costs, 'estimate_video_cost', lambda *a: 1)
    for _ in range(2):
        with pytest.raises(B.BudgetRefused):
            G._byteplus_generate_video(contract, 'action', [], [], '480p', 5, 'Ep3_candidate.mp4')
        assert not J.record_path(tmp_path / 'Ep3_candidate.mp4').exists()


def test_text_usage_settles_against_episode_allowance(monkeypatch):
    import cb_llm as L
    from pydantic import BaseModel
    class Result(BaseModel):
        value: str
    B.approve('Ep3', 2, 'Julian', 'script')
    monkeypatch.setenv('CB_PRODUCTION_EPISODE', 'Ep3')
    monkeypatch.setattr(L, '_assert_cost_budget', lambda *a: (.8, None))
    monkeypatch.setattr(L, '_openai_call', lambda *a, **kw: (Result(value='ready'), object()))
    monkeypatch.setattr(L, '_log_openai_usage', lambda *a: .3)
    L.structured('system', 'user', Result, reuse=False, log=lambda *a, **kw: None)
    assert B.status('Ep3')['remainingUsd'] == 1.7


def test_script_upload_proposes_one_allowance_without_granting_spend():
    result = B.require_allowance('Ep3', 'script', 'EXT. FOREST - DAY\nBO\nHello.\n')
    assert result['proposal']['suggestedUsd'] > 0
    assert not result['approved']
    assert result['usedAndReservedUsd'] == 0
    assert 'Provisional' in result['proposal']['assumptions']
    with pytest.raises(B.BudgetRefused):
        B.reserve('Ep3', .1, 'voice')
