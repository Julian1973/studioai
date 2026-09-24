import pytest
from studio_prompt_quality import Assessment, assess, require


def receipt(score=9.6, critical=None):
    value={name:{'score':score,'evidence':'Hold on the reaction.','reason':'Readable motivated pause.'}
           for name in Assessment.model_fields if name not in ('critical_issues','improvements')}
    value.update(critical_issues=critical or [], improvements=['Clarify reaction timing.'])
    return assess({'prompt':'Hold on the reaction.'},lambda *args:value)


def test_exact_prompt_above_floor_passes():
    r=receipt()
    assert require('Hold on the reaction.',r)>9.5


@pytest.mark.parametrize('score',[0,9.4,9.5])
def test_creative_score_is_advisory_and_summary_cannot_change_measured_score(score):
    r=receipt(score)
    assert r['ready']
    assert r['scorePolicy'] == 'advisory'
    # Older sealed receipts may retain a false readiness flag from the old floor.
    r.update(ready=False,score=10,floorExclusive=9.5)
    assert require('Hold on the reaction.',r) == pytest.approx(score)


def test_stale_and_missing_reviews_cannot_submit():
    for text,r in [('Changed.',receipt()),('Hold on the reaction.',None)]:
        with pytest.raises(ValueError):require(text,r)


def test_creative_conflicts_are_preserved_as_advisories_including_old_receipts():
    notes=['Final line begins before the outage lands.',
           'Droop overlaps visible speech articulation.']
    r=receipt(8.4,notes)
    assert r['ready']
    assert r['findingsPolicy']=='advisory'
    assert r['assessment']['critical_issues']==notes
    assert require('Hold on the reaction.',r)==pytest.approx(8.4)
    r.pop('findingsPolicy')
    r['ready']=False
    assert require('Hold on the reaction.',r)==pytest.approx(8.4)
    assert r['assessment']['critical_issues']==notes


def test_review_evidence_must_quote_actual_payload():
    r=receipt()
    r['assessment']['camera_and_edit']['evidence']='Invented quote'
    with pytest.raises(ValueError,match='evidence changed'):
        require('Hold on the reaction.',r)


def test_serialized_quotes_reuse_review_without_changing_scores():
    import json
    prompt = 'Sunny: 0.9–13.466s.\nSunny: 13.466–17.146s.'
    value = receipt(9.2)['assessment']
    for name in Assessment.model_fields:
        if name not in ('critical_issues', 'improvements'):
            value[name]['evidence'] = json.dumps(prompt, ensure_ascii=False)
    result = assess({'prompt': prompt}, lambda *args: value)
    assert result['assessment']['audio_and_timing']['evidence'] == prompt
    assert result['score'] == pytest.approx(9.2)
    assert result['ready']
    assert require(prompt, result) == pytest.approx(9.2)


def test_exact_evidence_recovers_unicode_quote_and_whitespace_serialization():
    from studio_prompt_quality import exact_evidence
    prompt = '  Sunny’s line says “We are safe inside now.”\nHold\ton the reaction.  '
    assert exact_evidence(prompt, '"We are safe inside now."') == \
        '“We are safe inside now.”'
    assert exact_evidence(prompt, 'Hold on the reaction.') == 'Hold\ton the reaction.'
    assert exact_evidence(prompt, 'Sunny chooses to calm down.') is None


@pytest.mark.parametrize(('prompt', 'evidence'), [
    ('Action: Sunny refuses drying and calls for the ladder.',
     '“Sunny refuses drying and calls for the ladder.”'),
    ('Movement: locked hold against Sunny’s motion',
     '“Movement: locked hold against Sunny’s motion”'),
    ('Audio continuity: match articulation to @Audio1.',
     '"match articulation to @Audio1."'),
])
def test_exact_evidence_accepts_balanced_presentation_quotes_only(prompt, evidence):
    from studio_prompt_quality import exact_evidence
    assert exact_evidence(prompt, evidence) in prompt


def test_exact_evidence_does_not_accept_paraphrase_after_removing_quotes():
    from studio_prompt_quality import exact_evidence
    assert exact_evidence('Sunny refuses drying and calls for the ladder.',
                          '“Sunny chooses to get the ladder.”') is None


def test_exact_evidence_recovers_long_verbatim_quote_with_spliced_prefix():
    from studio_prompt_quality import exact_evidence
    prompt = ('Performance: Amie is careful and small, not scolding. '
              'Sunny @图3’s refusal begins in her posture before her words: '
              'shoulders forward, attention already past the towel.')
    evidence = ('Performance: Sunny @图3’s refusal begins in her posture before her words: '
                'shoulders forward, attention already past the towel.')
    recovered = exact_evidence(prompt, evidence)
    assert recovered == 'Sunny @图3’s refusal begins in her posture before her words: shoulders forward, attention already past the towel.'
    assert recovered in prompt


@pytest.mark.parametrize('evidence', ['"Invented quote"', '""', '"hold on the reaction."'])
def test_quote_decoding_never_accepts_empty_invented_or_paraphrased_evidence(evidence):
    value = receipt()['assessment']
    value['story_and_causality']['evidence'] = evidence
    with pytest.raises(ValueError, match='evidence remains invalid after one automatic correction'):
        assess({'prompt': 'Hold on the reaction.'}, lambda *args: value)


def test_invalid_source_quote_is_automatically_repaired_once_without_changing_prompt():
    from copy import deepcopy
    snapshot = {'prompt': 'Hold on the reaction.', 'authorities': {'camera': 'Source-only camera rationale.'}}
    before = deepcopy(snapshot)
    valid = receipt(9.2)['assessment']
    invalid = deepcopy(valid)
    invalid['camera_and_edit']['evidence'] = 'Source-only camera rationale.'
    calls = []
    def reviewer(system, data):
        calls.append(deepcopy(data))
        return deepcopy(invalid if len(calls) == 1 else valid)
    result = assess(snapshot, reviewer)
    assert len(calls) == 2
    assert calls[1]['evidenceRepair']['invalidDimensions'] == ['camera_and_edit']
    assert calls[1]['evidenceRepair']['exactPromptLines'] == ['Hold on the reaction.']
    assert snapshot == before
    assert result['score'] == pytest.approx(9.2)
    assert result['ready']


def test_valid_low_score_never_triggers_score_chasing():
    calls = []
    value = receipt(9.0)['assessment']
    def reviewer(system, data):
        calls.append(data)
        return value
    result = assess({'prompt': 'Hold on the reaction.'}, reviewer)
    assert len(calls) == 1
    assert result['ready']


def test_repeated_invalid_evidence_is_bounded_to_two_reviews():
    value = receipt()['assessment']
    value['camera_and_edit']['evidence'] = 'Source-only rationale.'
    calls = []
    def reviewer(system, data):
        calls.append(data)
        return value
    with pytest.raises(ValueError, match='after one automatic correction'):
        assess({'prompt': 'Hold on the reaction.'}, reviewer)
    assert len(calls) == 2


def test_transport_refuses_unreviewed_generation_before_provider(monkeypatch,tmp_path):
    import cb_render
    monkeypatch.setattr(cb_render.cb_providers,'generate_video',lambda *a,**k:pytest.fail('Provider must not run'),raising=False)
    with pytest.raises(ValueError,match='WATCH_PROMPT_REVIEW_REQUIRED'):
        cb_render._submit_seedance_provider('Hold on the reaction.',[],out=str(tmp_path/'take.mp4'),
            direction_evidence={'segmentIndex':1})
