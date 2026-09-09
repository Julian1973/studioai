import copy
import pytest
import cb_seedance_pipeline as S
from studio_prompt_contract import reference_state_report


def task():
    return {'type':'storyboard_grid','goal':'A pilot notices the empty fuel gauge.',
            'duration_seconds':8,'references':[
                {'tag':'@Image 1','subject':'opening','defines':'opening state','authority':'opening'},
                {'tag':'@Image 2','subject':'board','defines':'coverage only','authority':'coverage'}],
            'assets':{'images':[{'tag':'@Image 1'},{'tag':'@Image 2'}]},'storyboard_tag':'@Image 2',
            'stages':[{'time':'0-8 seconds','purpose':'recognition','initial_state':'Pilot seated; gauge empty.',
                       'event':'Pilot looks at the gauge.','emotion_or_camera':'Hesitates, then looks back; cut to reaction.',
                       'end_state':'Pilot decides to land.'}],
            'audio':'@Audio1 wording is not paraphrased here: preserve punctuation — exactly.',
            'consistency':['Gauge stays empty.','Gauge stays empty.']}


def test_storyboard_keeps_director_timing_acting_opening_and_landing():
    t=task();p=S.SeedancePromptBuilder(t).build()
    for field in ('time','purpose','initial_state','event','emotion_or_camera','end_state'):
        assert t['stages'][0][field] in p
    assert p.index('[Reference Roles]') < p.index('[Opening State]') < p.index('[Shot Plan]') < p.index('[Audio]')
    assert p.count('Pilot seated; gauge empty.')==1
    assert p.count('Gauge stays empty.')==1
    assert t['audio'] in p


def test_declared_conflict_requires_reference_repair_not_more_prompt_negatives():
    t=task();t['references'][1].update(requiredState={'gauge':'empty'},depictedState={'gauge':'full'})
    r=S.SeedancePromptBuilder(t).preflight()
    assert not r['readyForProvider']
    assert r['validation']['referenceState']['conflicts'][0]['depicted']=='full'
    assert r['providerCalled'] is False
    t['references'][1]['depictedState']={'gauge':'empty'}
    assert S.SeedancePromptBuilder(t).preflight()['readyForProvider']


def test_unknown_visual_state_is_not_a_pass_or_a_new_gate():
    t=task();t['references'][1]['requiredState']={'gauge':'empty'}
    r=S.SeedancePromptBuilder(t).preflight()
    assert r['readyForProvider']
    assert r['validation']['referenceState']['unverified']
    assert r['validation']['referenceState']['visualFidelity']=='not-assessed-by-this-check'


def test_alias_duplicates_missing_assets_and_wrong_upload_order_are_detected():
    t=task();t['references'][1]['tag']='@图1'
    assert any('unique' in e for e in S.validate_seedance_task(t)['errors'])
    t=task();t['assets']['images'].pop()
    assert any('absent' in e for e in S.validate_seedance_task(t)['errors'])
    t=task();t['assets']['images'].reverse()
    assert any('provider position' in e for e in S.validate_seedance_task(t)['errors'])


def test_opening_and_continuity_are_distinct_and_approved_prompt_unchanged():
    t=task();t['references'][1]['authority']='opening'
    assert any('one exact opening' in e for e in S.validate_seedance_task(t)['errors'])
    t['references'][1]['authority']='continuity'
    original='Approved old prompt. Keep this exact text.'
    result=S.SeedancePromptBuilder(t).preflight(existing_prompt=original)
    assert result['providerPrompt']==original and result['approvedPromptPreserved']


def test_reference_grammar_does_not_double_negate():
    t=task();t['references'][0]['exclude']='Do not copy later action'
    p=S.SeedancePromptBuilder(t).build()
    assert 'Do not use Do not' not in p
    assert 'Do not copy later action.' in p
