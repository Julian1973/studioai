import cb_prompt_bank as B
import cb_learning_context as C


def record(path, outcome='rejected', project='crystal-bears', prompt='one parcel moves'):
    return B.bank_prompt(prompt=prompt, episode='Ep3', scene='1', shot_id='S1.SH2B',
                         outcome=outcome, diagnosis='Two parcels appeared.',
                         metadata={'projectId': project, 'batchId': 'batch-test'},
                         bank_path=path)


def test_next_outcome_links_failure_without_promoting_lesson(tmp_path):
    path = tmp_path / 'bank.jsonl'
    rejected = record(path)
    accepted = record(path, 'approved', prompt='The same parcel leaves empty hands.')
    assert accepted['outcomeLearning']['priorRejectedRecordIds'] == [rejected['recordId']]
    assert accepted['outcomeLearning']['sharedPracticePromoted'] is False
    rows = B.retake_evidence({'episode':'Ep3','scene':'1','shotId':'S1.SH2B'}, path)
    assert rows[0]['laterOutcomes'][0]['recordId'] == accepted['recordId']
    assert rows[0]['validation'] == 'failure-specific-review-required'


def test_failure_reaches_authoring_context_with_exact_prompt_binding(tmp_path, monkeypatch):
    path = tmp_path / 'bank.jsonl'
    rejected = record(path)
    monkeypatch.setattr(B, 'DEFAULT_BANK_PATH', path)
    monkeypatch.setattr(C, 'observations', lambda context: [])
    brief = C.brief({'episode':'Ep3','scene':'1','shotId':'S1.SH2B'})
    assert rejected['promptHash'] in brief
    assert 'Two parcels appeared.' in brief
    assert 'revise the authoritative shot plan before compiling' in brief


def test_outcomes_do_not_cross_project_episode_or_shot(tmp_path):
    path = tmp_path / 'bank.jsonl'
    record(path)
    for change in ({'projectId':'other'}, {'episode':'Ep4'}, {'shotId':'S1.SH1'}):
        context = {'episode':'Ep3','scene':'1','shotId':'S1.SH2B', **change}
        assert B.retake_evidence(context, path) == []
