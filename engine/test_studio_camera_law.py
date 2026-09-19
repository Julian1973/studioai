"""Camera height is computed from locked heights and reaches the provider's Camera line."""
import json
from pathlib import Path
import pytest
import studio_camera_law as C

ROOT = Path(__file__).resolve().parent.parent
GRAMMAR = json.loads((ROOT / 'shows/crystal-bears/laws/shot_grammar.json').read_text())
CHARS = json.loads((ROOT / 'shows/crystal-bears/canon/characters.json').read_text())


def _view(view_id, **extra):
    base = dict(viewId=view_id, audienceNeed='Read it.', framing='MS on the table', cameraPurpose='Hold.',
                cutReason='KNOW', continuity='Door behind.', productionChoice='current clip',
                action='She turns and settles.', performance='Listen, then answer.', timing='0-4s', entry='opening')
    base.update(extra)
    return base


def test_bee_is_photographed_from_its_own_eye_line_and_the_world_towers():
    facts = C.derive(_view('V', framing='MCU on Fuzzby at the flower rim', viewpointOwner='Fuzzby',
                           cinematography={'kind': 'cut_in', 'attention': 'character thought'}), GRAMMAR, CHARS)
    assert facts['subject'] == 'Fuzzby' and facts['subjectHeightIn'] == 14
    assert facts['eyeLineIn'] == 11.9 and 'world towers' in facts['cameraHeight']
    assert facts['size'] == 'MCU' and facts['lens'] == 'long'


def test_bear_eye_line_and_scale_low_angle_come_from_data_not_prose():
    default = C.derive(_view('V', framing='WS Sunny and Luna at the table',
                             visibleEntities=['character:Sunny', 'character:Luna'],
                             cinematography={'kind': 'master', 'attention': 'relationship'}), GRAMMAR, CHARS)
    assert default['subject'] == 'Sunny' and default['eyeLineIn'] == 45.0
    assert default['cameraHeight'] == "at the featured character's eye-line"
    scale = C.derive(_view('V', framing='WS Howey fills the doorway', visibleEntities=['character:Howey'],
                           cinematography={'kind': 'reveal', 'attention': 'scale'}), GRAMMAR, CHARS)
    assert scale['subject'] == 'Howey' and scale['cameraHeight'].startswith('low, below')


def test_world_views_get_no_character_height():
    assert C.derive(_view('V', framing='EWS above the canopy', visibleEntities=['sky', 'birds'],
                          cinematography={'kind': 'establishing'}), GRAMMAR, CHARS) is None
    assert C.derive(_view('V', framing='ECU on the cup', visibleEntities=['prop:cup']), GRAMMAR, CHARS) is None


def test_show_without_grammar_derives_nothing():
    assert C.load(show_root='/nonexistent')[0] is None
    assert C.derive(_view('V', viewpointOwner='Sunny'), None, CHARS) is None


def test_request_snapshot_attaches_camera_law_beside_the_shot_not_in_the_card():
    from studio_prompt_director import request_snapshot
    card = {'audienceFocus': 'x', 'views': [_view('S3.V1', viewpointOwner='Sunny', framing='MS on Sunny')]}
    shot = {'shotId': 'S3.SH1', 'durationSec': 4, 'charactersInFrame': ['Sunny'], 'directorCard': card}
    snap = request_snapshot('[Audio]\nNo dialogue.', {'shot': shot}, [], {}, 4)
    assert snap['authorities']['cameraLaw']['S3.V1']['subject'] == 'Sunny'
    assert 'cameraLaw' not in snap['authorities']['shot']['directorCard']  # the card is untouched
    assert snap['authorities']['shot']['directorCard'] == card


def test_compiled_camera_line_carries_inches_and_directed_move():
    from studio_watch_plan import camera_line
    view = _view('V', framing='MCU on Fuzzby', viewpointOwner='Fuzzby',
                 cinematography={'kind': 'cut_in', 'movement': 'the camera drifts down to the petal'})
    law = C.derive(view, GRAMMAR, CHARS)
    line = camera_line(view, 'MCU on Fuzzby', law)
    assert line.startswith('MCU on Fuzzby Movement: the camera drifts down to the petal')
    assert "Fuzzby's eye-line is 11.9 in above the ground" in line and 'long lens for a MCU' in line


def test_character_camera_grammar_from_data_rides_on_the_camera_line():
    from studio_watch_plan import camera_line
    view = _view('V', framing='CU on Zenny', viewpointOwner='Zenny',
                 cinematography={'kind': 'hold', 'lens': '50mm — her stillness needs no drama from the glass',
                                 'movement': 'locked off', 'composition': 'Zenny on the right third, negative space left'})
    law = C.derive(view, GRAMMAR, CHARS)
    assert law['characterGrammar'].startswith('the camera is steadier around Zenny')
    line = camera_line(view, 'CU on Zenny', law)
    assert 'Lens: 50mm — her stillness needs no drama from the glass' in line
    assert 'Movement: locked off' in line and 'Composition: Zenny on the right third' in line
    assert "Zenny's camera: the camera is steadier around Zenny" in line and 'locked off with no movement' in line
    bear = C.derive(_view('V', framing='MS on Sunny', viewpointOwner='Sunny'), GRAMMAR, CHARS)
    assert 'characterGrammar' not in bear  # only characters the show's grammar defines


def test_world_camera_language_and_light_are_stated_once_under_must_preserve():
    from studio_prompt_director import request_snapshot
    from studio_watch_plan import build_plan
    card = {'audienceFocus': 'x', 'views': [
        _view('S3.V1', viewpointOwner='Sunny', framing='MS on Sunny', startState='Sunny at the table.', endState='Sunny turns.'),
        _view('S3.V2', viewpointOwner='Sunny', framing='CU on Sunny', timing='4-8s', entry='cut',
              startState='Sunny mid-turn.', endState='Sunny settles.')]}
    shot = {'shotId': 'S3.SH1', 'durationSec': 8, 'charactersInFrame': ['Sunny'], 'directorCard': card}
    snap = request_snapshot('[Audio]\nNo dialogue.', {'shot': shot}, [], {}, 8)
    world = snap['authorities']['cameraLaw']['_world']
    assert world['cameraLanguage'].startswith('Slightly imperfect and organic')
    plan = build_plan(snap)
    world_lines = [x for x in plan['invariants'] if x.startswith(('Camera language of this world:', 'Light of this world:'))]
    assert len(world_lines) == 2 and 'never mechanical, never cold' in world_lines[0]
    assert 'warm-gold against cool-teal' in world_lines[1] and 'Every light is motivated' in world_lines[1]
    assert not any('Camera language of this world' in v['camera'] for v in plan['views'])  # once, not per view


def test_contract_asks_direct_for_camera_and_light_as_emotional_decisions():
    from studio_director_card import CONTRACT
    assert 'CAMERA AND LIGHT ARE EMOTIONAL DECISIONS, NEVER SPECS' in CONTRACT
    for phrase in ('stated in millimetres', '50 mm honest and still', 'lock the camera', 'never flat, never from nowhere',
                   'locked camera is a choice about stillness, never a default', 'composition in the view'):
        assert phrase in CONTRACT, phrase
