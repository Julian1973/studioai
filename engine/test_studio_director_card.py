import copy
import json
import pytest
from studio_director_card import card, stage_decisions, CONTRACT
from studio_editing import fields, impact
from test_studio_production import setup, command, approve


def direction():
    return dict(audienceFocus='A decision to trust', cameraPurpose='Read the hesitation', editIn='Cut on attention shift', editOut='Leave after decision', handoff='same moment', intendedState='Door stays closed', soundOwnership='Approved speech unchanged', views=[], acting=[dict(character='Hero', intention='Hide concern', attention='Partner by door', observableBehaviour='Grip relaxes after listening', startingPose='Hand on door', endingPose='Hand relaxed', timing='Listen before answering', listening='Watches partner and weighs answer')])


def test_revision_and_selective_acting_dependencies(setup):
    p,ws,t,_=setup;command(p,'budget',amountUsd=4)
    old=fields(p.snapshot('first','1')['state']['shots'][0]);old['directorCard']=direction()
    new=copy.deepcopy(old);new['directorCard']['acting'][0]['endingPose']='Hand tightens'
    assert card(old)['revision'] != card(new)['revision']
    assert stage_decisions(old,'see') == stage_decisions(new,'see')
    assert 'see' not in impact(old,new)['reset']
    assert 'hear' not in impact(old,new)['reset']
    new['directorCard']['acting'][0]['startingPose']='Hand raised'
    assert 'see' in impact(old,new)['reset']


def test_directed_revision_reaches_provider_and_preserves_origin(setup):
    p,ws,t,_=setup;command(p,'budget',amountUsd=8);approve(p,'see');approve(p,'hear')
    old=p.snapshot('first','1')['state']['shots'][0]
    new=fields(old);new['directorCard']=direction()
    t.reply={'message':'Directed listening and coverage','revisedShot':new}
    command(p,'chat',shotId='S1.SH1',message='Direct the listening and camera')
    proposal=p.snapshot('first','1')['state']['shots'][0]['proposal']
    command(p,'apply_revision',shotId='S1.SH1',proposalId=proposal['id'],prepare=True)
    current=p.snapshot('first','1')['state']['shots'][0]
    assert current['outcomes']['hear']==old['outcomes']['hear']
    image=current['outcomes']['see']
    assert 'Partner by door' in image['prompt']
    assert 'Grip relaxes after listening' not in image['prompt']
    assert image['directorCardRevision']['revision']
    approve(p,'see')
    request=p.snapshot('first','1')['state']['shots'][0]['outcomes']['request']
    assert 'Grip relaxes after listening' in request['prompt']
    assert 'Cut on attention shift' in request['prompt']
    assert CONTRACT


def test_specialist_context_never_truncates_tail_direction():
    import json
    import cb_departments
    value = cb_departments._creative_context({'largeSource': 'x' * 24000, 'finalActingDecision': 'Listen toward the door, then soften'})
    assert 'Listen toward the door, then soften' in value
    assert json.loads(value.strip())['finalActingDecision'] == 'Listen toward the door, then soften'


def test_post_sound_and_watch_sound_have_distinct_dependencies(setup):
    p, _, _, _ = setup; command(p, 'budget', amountUsd=4)
    old = fields(p.snapshot('first', '1')['state']['shots'][0]); old['directorCard'] = direction()
    new = fields(old)
    new['directorCard']['soundCues'] = [dict(kind='music', instruction='Resolve into room tone', timing='last two seconds', destination='post')]
    assert impact(old, new)['reset'] == []
    new['directorCard']['soundCues'][0]['destination'] = 'watch'
    assert impact(old, new)['reset'] == ['request', 'watch']


def test_coverage_cannot_disappear_or_change_during_clip_allocation():
    from studio_director_card import validate_coverage, SceneCoverage
    view = dict(viewId='reaction', audienceNeed='Read the decision', framing='Reverse close-up',
                cameraPurpose='Reveal doubt', cutReason='The listener now understands', continuity='Same door and eyeline',
                productionChoice='new keyframe and clip', entry='cut')
    scenes = [SceneCoverage(scene=1, audienceJourney='The listener doubts the promise', views=[view]).model_dump()]
    shots = [dict(scene=1, directorCard={'views': [view]})]
    validate_coverage(scenes, shots)
    with pytest.raises(ValueError, match='duplicated'):
        validate_coverage(scenes, shots * 2)
    with pytest.raises(ValueError, match='lost'):
        validate_coverage(scenes, [])
    edited = copy.deepcopy(shots); edited[0]['directorCard']['views'][0]['framing'] = 'Wide'
    with pytest.raises(ValueError, match='changed'):
        validate_coverage(scenes, edited)


def test_time_jump_does_not_inherit_previous_pose(setup):
    from studio_shot_remix import build
    p, ws, _, _ = setup; command(p, 'budget', amountUsd=4)
    state = p.snapshot('first', '1')['state']; shot = state['shots'][1]
    shot['directorCard'] = {**direction(), 'storyTime': 'time_jump'}
    assert build(ws.context('first', '1'), state, shot, []) is None


def test_playability_and_voice_cast_are_checked_before_provider_spend(setup):
    from studio_workspace import StudioError
    p, ws, _, _ = setup; command(p, 'budget', amountUsd=4)
    shot = fields(p.snapshot('first', '1')['state']['shots'][0])
    shot['directorCard'] = {**direction(), 'playability': dict(minimumDurationSec=31, reasoning='Travel and reply need more time', decision='playable')}
    with pytest.raises(StudioError, match='more time'):
        p.validate_shot(ws.context('first', '1'), shot)
    shot['directorCard'] = None; shot['characters'] = []
    with pytest.raises(StudioError, match='cast'):
        p.validate_shot(ws.context('first', '1'), shot)


def test_voice_specialist_receives_acting_and_tts_receives_performed_words(setup):
    p, ws, t, _ = setup; command(p, 'budget', amountUsd=8); approve(p, 'see'); approve(p, 'hear')
    old = p.snapshot('first', '1')['state']['shots'][0]
    directed = fields(old); directed['directorCard'] = direction()
    t.reply = {'message': 'Listen before answering', 'revisedShot': directed}
    command(p, 'chat', shotId=old['id'], message='Show the hesitation')
    proposal = p.snapshot('first', '1')['state']['shots'][0]['proposal']
    command(p, 'apply_revision', shotId=old['id'], proposalId=proposal['id'])
    revised = fields(p.snapshot('first', '1')['state']['shots'][0])
    revised['dialogue'][0]['performedText'] = '[curious] Hello.'
    t.reply = {'message': 'Question gently', 'revisedShot': revised}
    command(p, 'chat', shotId=old['id'], stage='hear', message='Make the voice curious')
    ctx = [call[2] for call in t.calls if call[0] == 'direction'][-1]
    assert ctx['stageDirection']['acting'][0]['listening'] == direction()['acting'][0]['listening']
    proposal = p.snapshot('first', '1')['state']['shots'][0]['proposal']
    command(p, 'apply_revision', shotId=old['id'], proposalId=proposal['id'], prepare=True)
    approve(p, 'see')
    voice = [call[2] for call in t.calls if call[0] == 'voice'][-1]
    assert voice[0]['text'] == '[curious] Hello.'
    hear = p.snapshot('first', '1')['state']['shots'][0]['outcomes']['hear']
    assert hear['executionReceipt']['voiceDirection']['acting']
    assert hear['directorCardRevision']['sourceBindings']['projectId'] == 'first'


def test_review_never_treats_approval_as_observed_success():
    from studio_director_card import assessment
    report = assessment({'directorCard': direction()}, candidate={'id': 'r1', 'status': 'approved'})
    assert report['humanApproval'] == 'approved'
    assert report['observedResult'] == report['audienceReadability'] == 'unverified'


def test_shot_revision_updates_scene_coverage_without_touching_other_views():
    from studio_editing import revised_scene_coverage
    first = dict(viewId='one', entry='opening', framing='Wide', audienceNeed='See the relationship',
                 cameraPurpose='Show distance', cutReason='Read both characters', continuity='Same room', productionChoice='current clip')
    second = {**first, 'viewId': 'two', 'entry': 'cut', 'framing': 'Reverse'}
    original = dict(id='one', scene=1, directorCard={'views': [first]})
    neighbour = dict(id='two', scene=1, directorCard={'views': [second]})
    state = {'shots': [original, neighbour], 'sceneCoverage': [{'scene': 1, 'audienceJourney': 'Distance becomes trust', 'views': [first, second]}]}
    before = copy.deepcopy(state)
    new = copy.deepcopy(original); new['directorCard']['views'][0]['framing'] = 'Close-up to read doubt'
    changed = revised_scene_coverage(state, original, new)
    assert state == before
    assert changed[0]['views'][0]['framing'] == 'Close-up to read doubt'
    assert changed[0]['views'][1] == second
    new['directorCard']['views'][0]['viewId'] = 'two'
    from studio_workspace import StudioError
    with pytest.raises(StudioError, match='another shot'):
        revised_scene_coverage(state, original, new)


# --- Feature-animation coverage vocabulary (Phase 1, inside cinematography) ---

def _view(view_id, **extra):
    base = dict(viewId=view_id, audienceNeed='Read the moment.', framing='Medium.', cameraPurpose='Hold attention.',
                cutReason='new information', continuity='Door behind.', productionChoice='current clip')
    base.update(extra)
    return base


def test_coverage_vocabulary_is_accepted_and_reaches_the_scene_board():
    from studio_director_card import validate_coverage, SceneCoverage
    from studio_coverage import unit_board, scene_boards
    views = [
        _view('S1.V1', cinematography={'kind': 'world_texture', 'functions': ['establish place', 'create anticipation'], 'attention': 'world'},
              visibleEntities=['sky', 'birds']),
        _view('S1.V2', cinematography={'kind': 'master', 'motivation': 'PLACE', 'cutTiming': 'on'}),
        _view('S1.V3', sourceBeat='cup', cinematography={'kind': 'cut_in', 'actionPhase': 'preparation'}),
        _view('S1.V4', sourceBeat='cup', cinematography={'kind': 'insert', 'actionPhase': 'contact', 'motivation': 'object interaction'}),
        _view('S1.V5', cinematography={'kind': 'reaction', 'motivation': 'REACT', 'cutTiming': 'after'},
              viewpointOwner='Luna', listenerReaction='Delayed realisation.'),
        _view('S1.V6', cinematography={'kind': 'hold', 'attention': 'stillness'}, cutReason='Her thought carries the beat; staying is stronger than any new view.'),
    ]
    scene = SceneCoverage(scene=1, audienceJourney='Arrive through the world, land on the cup.',
                          entrance='through the world: birds, then down to the clearing', mode='warm comedy',
                          function='establish', views=views)
    shot = {'id': 'S1.SH1', 'scene': 1, 'directorCard': {'views': views}}
    validate_coverage([scene], [shot])  # no error
    panels = unit_board(shot)['panels']
    assert [p['kind'] for p in panels] == ['world_texture', 'master', 'cut_in', 'insert', 'reaction', 'hold']
    assert panels[0]['functions'] == ['establish place', 'create anticipation'] and panels[0]['attention'] == 'world'
    assert panels[3]['actionPhase'] == 'contact' and panels[3]['motivation'] == 'SEE'  # alias normalised
    assert panels[4]['cutTiming'] == 'after'
    board = scene_boards([shot], [scene.model_dump()])[0]
    assert board['entrance'].startswith('through the world') and board['mode'] == 'warm comedy' and board['function'] == 'establish'


@pytest.mark.parametrize('bad, message', [
    (dict(cinematography={'kind': 'b-roll'}), 'unknown coverage kind'),
    (dict(cinematography={'motivation': 'because cinematic'}), 'unknown cut motivation'),
    (dict(cinematography={'cutTiming': 'later'}), 'cutTiming must be one of'),
    (dict(cinematography={'kind': 'environment'}), 'at least one function'),
    (dict(cinematography={'kind': 'world_texture', 'functions': ['establish place']}, visibleEntities=['character:Sunny']), 'not a character entity'),
    (dict(cinematography={'kind': 'reaction'}), 'names the listener'),
    (dict(cinematography={'kind': 'hold', 'motivation': 'FEEL'}), 'a hold has no cut motivation'),
    (dict(cinematography={'attention': 'prettiness'}), 'unknown attention priority'),
])
def test_coverage_vocabulary_rejects_ambiguity_not_taste(bad, message):
    from studio_director_card import validate_coverage, SceneCoverage
    views = [_view('S1.V1', **bad)]
    scene = SceneCoverage(scene=1, audienceJourney='x', views=views)
    with pytest.raises(ValueError, match=message):
        validate_coverage([scene], [{'id': 'S1.SH1', 'scene': 1, 'directorCard': {'views': views}}])


def test_a_phase_that_steps_back_is_noted_never_refused():
    """20 Sep 2026, Ep4 scene 3: one beat carried several physical chains (bears react to the
    first drops; the downpour has its consequence; berry cups begin to fill). Stepping back
    is usually the next event, so the order is recorded as a warning; it never stops a scene
    and never goes back to the Director to be flattened into a checker's order."""
    from studio_director_card import validate_coverage, coverage_issues, coverage_warnings, SceneCoverage
    views = [_view('S1.V1', sourceBeat='cup', cinematography={'actionPhase': 'reaction'}),
             _view('S1.V2', sourceBeat='cup', cinematography={'actionPhase': 'consequence'}),
             _view('S1.V3', sourceBeat='cup', cinematography={'actionPhase': 'contact'})]
    scene = SceneCoverage(scene=1, audienceJourney='x', views=views)
    validate_coverage([scene], [{'id': 'S1.SH1', 'scene': 1, 'directorCard': {'views': views}}])
    assert coverage_issues(views[1], views[0]) == []
    assert coverage_warnings(views[1], views[0]) == [
        'action phase steps back: reaction then consequence within the same beat (a new physical chain, or check the order)']
    assert coverage_warnings(views[2], views[1])[0].startswith('action phase steps back: consequence then contact')
    assert coverage_warnings(views[0], None) == []


def test_cards_without_the_vocabulary_keep_their_revision():
    """Phase 1 adds nothing to the hashed card: existing approvals stay current."""
    from studio_director_card import card
    shot = {'id': 'S1.SH1', 'duration': 4, 'directorCard': dict(direction(), views=[_view('S1.V1')])}
    before = card(shot)['revision']
    import copy
    again = copy.deepcopy(shot)
    assert card(again)['revision'] == before
    assert 'kind' not in again['directorCard']['views'][0]


def test_contract_carries_the_feature_animation_craft():
    from studio_director_card import CONTRACT
    for phrase in ('NORTH STAR', 'performance outranks coverage', 'DECISION ORDER', 'AUDIENCE KNOWLEDGE',
                   'HOLD OR CUT, THEN WHY, THEN HOW', 'ACTION CHAINS', 'REACTIONS', 'PHOTOGRAPH THOUGHT',
                   'visual sentence', 'INTERNAL COVERAGE IS THE DEFAULT', 'never the provider', 'better visual decisions'):
        assert phrase in CONTRACT
