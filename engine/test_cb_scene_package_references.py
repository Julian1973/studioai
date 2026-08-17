import pathlib
import sys


HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cb_scene_package as P


def test_opener_reference_slots_bind_cast_look_keyframe_and_audio():
    animation, keyframe = P._reference_slots(
        ["Aida", "Fuzzby"], opener=True, has_dialogue=True)
    assert animation == {
        "@图1": "opening keyframe",
        "@图2": "Aida",
        "@图3": "Fuzzby",
        "@图4": "scene plate",
        "@Audio1": "voice track",
    }
    assert keyframe == {
        "@图1": "Aida", "@图2": "Fuzzby", "@图3": "scene plate"}


def test_relay_reference_slots_keep_state_look_and_identity_separate():
    animation, keyframe = P._reference_slots(
        ["Aida"], opener=False, has_dialogue=False)
    assert animation == {
        "@图1": "previous shot final frame",
        "@图2": "scene plate",
        "@图3": "Aida",
    }
    assert keyframe == {"@图1": "Aida", "@图2": "scene plate"}


def test_opening_cast_can_be_narrower_than_full_animation_cast():
    shot = {
        "charactersInFrame": ["Aida", "Fuzzby", "Zenny"],
        "openingCharactersInFrame": ["Aida", "Fuzzby"],
    }
    assert shot["openingCharactersInFrame"] != shot["charactersInFrame"]
