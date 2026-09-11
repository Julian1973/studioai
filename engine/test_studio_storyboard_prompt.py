"""Real compiler checks. No provider, image recognition or creative-quality claim."""
from copy import deepcopy
import pytest
import cb_departments as D
from studio_storyboard_prompt import view_timings, subjects_for_view


def example():
    shot = dict(shotId='S4.SH3', durationSec=8, charactersInFrame=['Mira', 'Oren'],
        dialogueLines=[dict(speaker='Mira', exactText='Here you are.', startSec=2, endSec=3)],
        directorCard=dict(views=[dict(viewId='A', atSec=0, timing='0–4s'),
                                 dict(viewId='B', atSec=4, timing='4–8s')]))
    direction = dict(durationSec=8, generationGoal='A hesitant handoff becomes trust.',
        dramaticBeat='Mira trusts Oren with the cup.',
        audienceBefore='Mira is hesitant.', audienceAfter='Oren accepts the responsibility.',
        creativeTranslation={'interpretation': {}, 'gagClocks': []},
        referenceContract=[
            dict(assetTag='@图1', role='opening_frame', controls='the approved opening'),
            dict(assetTag='@图2', role='character_identity', controls='Oren identity and scale'),
            dict(assetTag='@图3', role='location', controls='the fixed workshop'),
            dict(assetTag='@图4', role='character_identity', controls='Mira identity and scale'),
            dict(assetTag='@Audio1', role='audio', controls='the approved performance')],
        shotPlan=[dict(shotNumber=1, sourceViewId='A', transitionType='opening',
            framingLensAndCamera='Hold a medium two-shot at eye height.',
            causalAction='Mira extends the cup and Oren reaches to accept it.',
            observablePerformance='Mira hesitates, then relaxes her fingers.',
            compositionLightAndMaterials='Warm window light catches the ceramic rim.',
            landingImage='Oren holds the cup; Mira has released it.',
            dialogueLineIndexes=[1], holdAfterDialogue=False),
            dict(shotNumber=2, sourceViewId='B', transitionType='cut',
            framingLensAndCamera='Cut to a close-up of Oren.',
            causalAction='Oren cradles the cup.',
            observablePerformance='Oren looks down with a small smile.',
            compositionLightAndMaterials='The same window lights the near cheek.',
            landingImage='Oren holds the single cup against his chest.')],
        stagePlan=[dict(stageNumber=1, startSec=0, endSec=8,
            initialOrCarriedState='Mira holds a cup.', cause='Mira decides to trust Oren.',
            primaryEvent='Mira hands the cup to Oren.',
            observableEndState='Oren holds the cup.', emotionOrCameraAnalysis='Let trust read.')],
        geography=['Mira stands opposite Oren at the workshop table.'],
        consistencyContract=['Keep the table axis stable.'], surgicalSafeguards=[],
        continuityFinish='Oren holds the cup.', audioContract='Approved dialogue with quiet foley.')
    return shot, direction


def test_actual_compiler_emits_timed_views_and_local_reference_bindings():
    shot, direction = example()
    before = deepcopy((shot, direction))
    prompt = D.compile_animation_provider_prompt(shot, direction)
    assert 'Shot 1: 0–4s\nCamera:' in prompt
    assert 'Shot 2: 4–8s\nCamera:' in prompt
    first, second = prompt.split('Shot 2:', 1)
    assert 'Subjects: Oren from @图2; Mira from @图4.' in first
    assert 'Subjects: Oren from @图2.' in second
    assert 'Setting / light / materials: Warm window light catches the ceramic rim.' in first
    assert 'Setting / light / materials: The same window lights the near cheek.' in second
    assert 'End state: Oren holds the cup; Mira has released it.' in first
    assert prompt.count('{Here you are.}') == 1
    import cb_emission_conformance as emission
    expected_cue = emission.dialogue_placement_line(
        emission.dialogue_cues(shot['dialogueLines'], duration_sec=8)[0], hold_after=False)
    assert expected_cue in prompt
    assert prompt.index('[PURPOSE]') < prompt.index('[TIMED ACTION]')
    assert (shot, direction) == before


def test_current_storyboard_does_not_append_another_telling_of_the_story():
    shot, direction = example()
    shot['watchDirectorFeedbackApproved'] = 'A raw review note kept in the review authorities.'
    prompt = D.compile_animation_provider_prompt(shot, direction)
    assert 'A raw review note' not in prompt
    assert '[Human Review Correction]' not in prompt
    assert '[COVERAGE STAGING]' not in prompt
    assert '[Crystal Energy Law]' not in prompt
    assert prompt.count('Mira extends the cup and Oren reaches to accept it.') == 1


def test_storyboard_reaches_actual_prompt_director_seal_with_audio_unchanged(monkeypatch, tmp_path):
    import cb_llm
    import studio_prompt_director as pd
    from test_studio_prompt_director import review
    shot, direction = example()
    prompt = D.compile_animation_provider_prompt(shot, direction)
    heard = {'path': 'approved-source.wav', 'md5': 'synthetic-waveform-hash'}
    import hashlib
    refs = []
    for i, role in enumerate(('opening keyframe', 'Oren', 'scene plate', 'Mira'), 1):
        path = tmp_path / f'image-{i}.jpeg'
        path.write_bytes(role.encode())
        refs.append(dict(role=role, slot=f'@图{i}', path=str(path), hash=hashlib.sha256(path.read_bytes()).hexdigest()))
    env = {'prompt': prompt, 'references': refs, 'audio': heard, 'durationSec': 8,
           'executionPlan': {'segments': [{'prompt': prompt, 'references': refs,
               'audio': heard, 'durationSec': 8, 'contract': {}}]}}
    seen = []
    def reviewer(system, text, schema, **kwargs):
        import json
        seen.append(json.loads(text))
        return review()
    monkeypatch.setattr(cb_llm, 'structured_with_repair', reviewer)
    pd.review_legacy_envelope(env, shot, direction, archive_folder=tmp_path)
    pd.verify_legacy_envelope(env)
    final = env['executionPlan']['segments'][0]
    assert 'Shot 1: 0–4s' in final['prompt']
    assert 'Camera: Hold a medium two-shot at eye height.' in final['prompt']
    assert 'Mira identity/design only' in final['prompt']
    assert final['audio'] == heard
    assert final['prompt'].count('{Here you are.}') == 1
    assert seen[0]['authorities']['shot'] == shot


def test_timing_is_not_invented_from_duration_or_stage_ordinal():
    assert view_timings({'durationSec': 26}, 5) == [None] * 5
    assert view_timings({'durationSec': 26, 'directorCard': {
        'views': [{'viewId': 'V1', 'timing': 'reaction'},
                  {'viewId': 'V2', 'timing': 'handoff'}]}}, 2) == [None, None]


def test_explicit_typed_visual_edit_reaches_source_without_changing_timing_or_audio():
    from studio_director_handoff import synchronise_visual_coverage
    shot, direction = example()
    shot['storyboardInternalShotPlanApproved'] = [dict(viewId=v['viewId'], storyAction='Old action')
        for v in shot['directorCard']['views']]
    shot['directorCard']['views'][1]['visibleEntities'] = ['character:Oren']
    before = deepcopy(shot)
    result = synchronise_visual_coverage(shot, direction, author='Test accepted edit')
    assert result['storyboardInternalShotPlanApproved'][1]['storyAction'] == direction['shotPlan'][1]['causalAction']
    assert result['directorCard']['views'][1]['action'] == direction['shotPlan'][1]['causalAction']
    assert result['directorCard']['views'][1]['visibleEntities'] == ['character:Oren']
    assert result['dialogueLines'] == shot['dialogueLines']
    assert result['durationSec'] == shot['durationSec']
    assert view_timings(result, 2) == view_timings(shot, 2)
    assert shot == before
    direction['shotPlan'].reverse()
    with pytest.raises(ValueError, match='sourceViewId'):
        synchronise_visual_coverage(shot, direction, author='Test stale edit')


@pytest.mark.parametrize('change', ['gap', 'overrun', 'count', 'stale'])
def test_explicit_coverage_cannot_silently_desynchronise(change):
    shot, _ = example()
    if change == 'gap':
        shot['directorCard']['views'][1].update(atSec=5, timing='5–8s')
    elif change == 'overrun':
        shot['directorCard']['views'][1]['timing'] = '4–9s'
    elif change == 'count':
        shot['directorCard']['views'].pop()
    else:
        shot['directorCardSource'] = {'version': 'old', 'sourceHash': 'stale'}
    with pytest.raises(ValueError):
        view_timings(shot, 2)


def test_subject_names_are_not_guessed_or_inserted_in_dialogue():
    view = {'causalAction': 'Anne follows Oren.'}
    assert subjects_for_view([('@图1', 'Ann'), ('@图2', 'Oren')], view) == 'Subjects: Oren from @图2.'
    assert subjects_for_view([('@图4', 'Mira')], view, ['Mira']) == 'Subjects: Mira from @图4.'


def test_previous_clip_cut_is_not_a_cut_away_from_the_current_opening():
    shot, direction = example()
    direction['taskMode'] = 'reference-to-video'
    shot['storyboardInternalShotPlanApproved'] = [
        {'viewId': 'A', 'transitionType': 'cut'}, {'viewId': 'B', 'transitionType': 'cut'}]
    prompt = D.compile_animation_provider_prompt(shot, direction)
    first, second = prompt.split('Shot 2:', 1)
    assert 'Cut to the planned view.' not in first
    assert 'Cut to the planned view.' in second


def test_revised_watch_does_not_reimport_historical_hear_body_blocking():
    shot, _ = example()
    line = shot['dialogueLines'][0]
    line['dialogueOccurrenceId'] = 'line-1'
    shot['voiceDirectorBrief'] = [{'dialogueOccurrenceId': 'line-1',
        'physicalActionRelationship': 'Speak while running.',
        'elevenLabsV3Direction': 'Small and breathless.', 'expectedTiming': '2–3s'}]
    shot['watchDirectorFeedbackApproved'] = 'Stop first, then speak.'
    before = deepcopy(shot)
    current = D._animation_current_context({'shot': shot})
    assert 'physicalActionRelationship' not in current['shot']['voiceDirectorBrief'][0]
    assert current['shot']['voiceDirectorBrief'][0]['elevenLabsV3Direction'] == 'Small and breathless.'
    assert current['shot']['dialogueLines'] == before['dialogueLines']
    assert 'while running' not in D._animation_dialogue_direction(shot, line)
    assert shot == before


@pytest.mark.parametrize('failure', ['swapped', 'missing', 'placeholder'])
def test_correct_count_cannot_hide_misbound_or_empty_coverage(failure):
    shot, direction = example()
    if failure == 'swapped':
        direction['shotPlan'][1]['sourceViewId'] = 'A'
    elif failure == 'missing':
        direction['shotPlan'][1].pop('sourceViewId')
    else:
        direction['shotPlan'][1]['causalAction'] = 'No extra view.'
    with pytest.raises(ValueError, match='sourceViewId|placeholder'):
        D.compile_animation_provider_prompt(shot, direction)
