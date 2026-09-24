"""Offline audio-template and lossless review regressions. No provider calls."""
import socket
import hashlib

import pytest
import cb_render as R
import cb_emission_conformance as C
import studio_prompt_director as PD
import studio_seedance_execution as E
from studio_character_roles import audit
from test_studio_seedance_execution import compact_source


def test_frozen_s1_authority_bytes_require_explicit_version_migration():
    # Independent fingerprint of the submitted Ep4 S1.SH1 authority, not a
    # dynamically generated expectation that could silently follow a rewrite.
    assert C.STANDARD_AUDIO_TEMPLATE_VERSION == 'crystal-bears-s1-audio-v1'
    assert hashlib.sha256(C.STANDARD_DIALOGUE_AUDIO_AUTHORITY.encode()).hexdigest() == (
        '23640f82b6b45fc1d959566b0bd535b077d4d1cba39ab56e7b7cb5a878f4b163')


def test_hand_insert_does_not_invent_visible_lip_sync(compact_source):
    shot = compact_source['authorities']['shot']
    shot['directorCard']['views'][0]['framing'] = 'Close insert of the hand; her mouth stays out of frame.'
    prompt, _ = E.compile_prompt(compact_source, audit(compact_source))
    first = prompt.split('Shot 2:')[0]
    assert 'Preserve offscreen @Audio1 timing' in first
    assert 'Match visible speech articulation' not in first


def test_explicit_object_angle_does_not_inherit_character_eye_height():
    from studio_watch_plan import camera_line
    text = camera_line({'cinematography': {'angle': 'At tabletop height', 'lens': '35 mm'}},
        'Cup insert', {'cameraHeight': 'eye-line', 'subject': 'Sunny', 'eyeLineIn': 45})
    assert 'At tabletop height' in text
    assert '45' not in text


def test_standard_template_reaches_compiled_prompt(compact_source):
    prompt, evidence = E.compile_prompt(compact_source, audit(compact_source))
    assert evidence['audioTemplate']['version'] == C.STANDARD_AUDIO_TEMPLATE_VERSION
    assert C.STANDARD_DIALOGUE_AUDIO_AUTHORITY in prompt
    assert 'instrumental musical underscore' in prompt
    assert 'The exact braced dialogue markers place approved words only' in prompt
    assert 'Do not synthesize, repeat, dub, echo, layer or replace' in prompt
    assert PD.audio_policy(False) == '[Audio]\nNo dialogue.'
    lines = compact_source['authorities']['shot']['dialogueLines']
    result = C.validate_dialogue_synthesis(prompt, lines)
    assert result['ready'], result['errors']
    assert '[Dialogue timing]' in prompt
    assert '[TIMED ACTION]' in prompt
    assert 'Only the active @Audio1 speaker articulates dialogue.' in prompt


def test_fallback_uses_standard_but_never_rewrites_signed_audio():
    lines = [{'speaker': 'Sunny', 'exactText': 'Again.'}]
    old = 'Spoken action: Sunny: {Again.}'
    updated = R._provider_safe_dialogue_prompt(old, lines)
    assert C.STANDARD_DIALOGUE_AUDIO_AUTHORITY in updated
    assert C.validate_dialogue_synthesis(updated, lines)['ready']
    assert R._provider_safe_dialogue_prompt(updated, lines) == updated
    # An already complete reviewed contract keeps its exact signed bytes.
    historical = updated.replace('Never mask speech.', 'Keep the original mix.')
    assert R._provider_safe_dialogue_prompt(historical, lines) == historical


def test_every_spoken_prompt_is_normalized_to_locked_template():
    lines = [{'speaker': 'Sunny', 'exactText': 'Hello.'}]
    assert C.STANDARD_DIALOGUE_AUDIO_AUTHORITY in C.ensure_standard_audio_template(
        'Shot 1: Sunny speaks. {Hello.}', lines)
    legacy = 'Shot 1: Sunny speaks. ' + C.SINGLE_INSTANCE_DIALOGUE_LOCK
    normalized = C.ensure_standard_audio_template(legacy, lines)
    assert C.STANDARD_DIALOGUE_AUDIO_AUTHORITY in normalized
    assert C.SINGLE_INSTANCE_DIALOGUE_LOCK not in normalized


@pytest.mark.parametrize('replacement', [None, {'version': 'obsolete', 'hash': 'wrong'}])
def test_submission_review_detects_missing_or_changed_template_identity(compact_source, replacement):
    prompt, evidence = E.compile_prompt(compact_source, audit(compact_source))
    snapshot = dict(compact_source, prompt=prompt)
    _, errors = E.final_check(snapshot, evidence)
    assert not any('Locked Audio1 template' in error for error in errors)
    evidence['audioTemplate'] = replacement
    _, errors = E.final_check(snapshot, evidence)
    assert 'Locked Audio1 template differs from the reviewed compiler version' in errors


def test_video_edit_uses_same_dialogue_bed_without_expanding_edit_scope():
    shot = {'dialogueLines': [{'speaker': 'Sunny', 'exactText': 'Again.',
                              'startSec': 1, 'endSec': 2}]}
    prompt = R._video_edit_prompt(shot, 'Keep berries visible.', 3, 4, True)
    assert C.STANDARD_DIALOGUE_AUDIO_AUTHORITY in prompt
    assert prompt.count('{Again.}') == 1
    assert 'outside the correction window' in prompt
    assert C.validate_dialogue_synthesis(prompt, shot['dialogueLines'])['ready']
    silent = R._video_edit_prompt({'dialogueLines': []}, 'Keep berries visible.', 3, 4, False)
    assert '@Audio1' not in silent


def test_review_preserves_complete_mix_and_requires_human_verification(tmp_path, monkeypatch):
    monkeypatch.setattr(socket.socket, 'connect', lambda *a: pytest.fail('No network'))
    monkeypatch.setattr(R.cb_audio_authority, 'spoken_dialogue_lines', lambda s: [{}])
    movie = tmp_path / 'take.mp4'
    voice = tmp_path / 'approved.wav'
    # The operation must be byte-preserving, not a transcode or audio overlay.
    movie.write_bytes(b'video + original dialogue + effects + music')
    voice.write_bytes(b'approved dialogue')
    original = movie.read_bytes()
    result = R._restore_approved_voice_for_review(
        {'shotId': 'S3.SH2'}, {'voPath': str(voice)}, movie, 'batch', 1)
    assert movie.read_bytes() == original
    assert result['reviewSha256'] == result['providerGuideSha256']
    assert result['providerFinalMixPreserved'] is True
    assert result['approvedHearRestored'] is False
    assert result['guideDialogueRemoved'] is False
    assert result['dialogueVerified'] is False
    assert result['exactApprovedWaveformPassthrough'] is False


def test_review_still_requires_approved_voice_file(tmp_path, monkeypatch):
    monkeypatch.setattr(R.cb_audio_authority, 'spoken_dialogue_lines', lambda s: [{}])
    with pytest.raises(R.Refused):
        R._restore_approved_voice_for_review({'shotId': 'S3.SH2'},
            {'voPath': str(tmp_path / 'missing.wav')}, tmp_path / 'missing.mp4', 'b', 1)
