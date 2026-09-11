"""Prompt-writing/directing-chain regressions from the S1.SH2 incident.

These are deterministic pre-fire checks only: no provider calls and no pixel/audio
recognition claims.
"""
from copy import deepcopy
import socket

import pytest

import studio_seedance_execution as E
import studio_prompt_director as PD
from test_studio_prompt_director import review


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: pytest.fail('Network forbidden'))


def base_snapshot(prompt):
    shot = {
        'shotId': 'S1.SH2A',
        'durationSec':12,
        'purpose': 'Land the honeycomb removal and pursuit clearly.',
        'dialogueLines': [],
        'directorCard': {'views': [
            {'viewId': 'grab', 'timing': '0-6s', 'framing':'Medium view of the support.',
             'action':'Keen removes the honeycomb from the far-tree support.',
             'performance':'Keen commits to the grab.', 'endState':'Keen holds the whole honeycomb.'},
            {'viewId': 'pursuit', 'timing': '6-12s', 'entry':'cut', 'framing':'Track the return route.',
             'action':'Keen returns to the near-bank catapult as Fuzzby pursues him.',
             'performance':'Keen panics; Fuzzby pursues with intent.', 'endState':'Both reach the near bank.'},
        ]},
        'objectLifecycleLocks': {'object:honeycomb.whole': {
            'description': 'original single whole golden honeycomb object',
            'stateIn': 'attached to far-tree support',
            'stateOut': 'removed from the support and carried toward the near-bank catapult',
        }},
    }
    return PD.request_snapshot(prompt, {'shot': shot, 'specialist': {'dramaticBeat': 'Clear cause and effect.'}},
                               [{'slot': '@图1', 'role': 'opening keyframe'}], {}, 12)


def supported_prompt(extra=''):
    return ('[Shot Sequence]\n'
            'Shot 1: 0-6s\nAction: Keen removes the honeycomb from the far-tree support.\n\n'
            'Shot 2: 6-12s\nAction: Keen returns back to the near-bank catapult as Fuzzby pursues him.\n'
            + extra)


def compile_supported(extra='', snapshot_changes=None):
    snap = base_snapshot(supported_prompt(extra))
    if snapshot_changes:
        snapshot_changes(snap)
    prompt, evidence = E.compile_prompt(snap, {'characters': []})
    return {**snap, 'prompt': prompt}, evidence


def test_appended_corrections_require_source_recompile():
    with pytest.raises(ValueError, match='update the approved plan'):
        compile_supported('\n[Human Review Correction]\nChange the outcome.')


def test_world_rules_are_not_silently_deleted():
    def source_rule(snap):
        snap['authorities']['specialist']['consistencyContract']=['Project-authored appearance requirement.']
    final, evidence = compile_supported('\n[Crystal Energy Law]\nStale historical appearance.',source_rule)
    assert 'Project-authored appearance requirement.' in final['prompt']
    assert 'Stale historical appearance.' not in final['prompt']


def test_no_dialogue_shot_does_not_inherit_generic_audio1_authority():
    final, evidence = compile_supported('\n[Audio]\nNo dialogue. No @Audio1 required. Seedance SFX only.')
    assert 'No dialogue. No @Audio1 required. Seedance SFX only.' in final['prompt']
    assert 'Use @Audio1' not in final['prompt']
    assert evidence['audioPolicy'] == 'no-dialogue/no-Audio1'
    _, faults = E.final_check(final, evidence)
    assert faults == []


def test_dialogue_shot_still_preserves_audio1_verbatim():
    def add_audio(snap):
        snap['authorities']['shot']['dialogueLines'] = [dict(speaker='Keen', exactText='Ow!', startSec=1, endSec=2)]
        snap['audio'] = {'path': 'approved.wav', 'hash': 'locked'}
    final, evidence = compile_supported('\n[Audio]\n@Audio1 exact approved performance. Spoken action: Keen says {Ow!}.', add_audio)
    assert '[Audio]\n@Audio1 exact approved performance. Spoken action: Keen says {Ow!}.' in final['prompt']
    changed = deepcopy(final)
    changed['prompt'] = changed['prompt'].replace('exact approved', 'changed approved')
    _, faults = E.final_check(changed, evidence)
    assert 'Protected Audio1 provider text changed during review' in faults


@pytest.mark.parametrize('text', [
    'Fuzzby starts on the honeycomb, then leaves it to pursue Keen.',
    'Camera holds, then cuts to a moving view.',
    'Fuzzby catches himself. Later a new fall happens and he catches himself again.',
    'The opening composition remains for the whole shot by deliberate choice.',
])
def test_phrase_matching_does_not_claim_semantic_failure(text):
    _, errors = E.final_check(base_snapshot(text), {'applied': False})
    assert errors == ['WATCH request has no current typed-plan compiler evidence; legacy prose cannot bypass compilation']
    # The text itself is not a semantic failure; it still needs actual compilation/review.


def test_structured_conflict_blocks_before_semantic_provider(monkeypatch, tmp_path):
    import cb_llm
    monkeypatch.setattr(cb_llm, 'structured_with_repair', lambda *a, **k: pytest.fail('No provider call'))
    snap = base_snapshot(supported_prompt())
    snap['authorities']['shot']['directorCard']['views'][0]['cinematography'] = {
        'cameraState': 'locked', 'movement': 'orbit'}
    env = {'prompt': snap['prompt'], 'durationSec': 12, 'references': snap['references'], 'audio': {},
           'executionPlan': {'segments': [{'prompt': snap['prompt'], 'contract': {}}]}}
    with pytest.raises(ValueError, match='DIRECTION PLAN'):
        PD.review_legacy_envelope(env, snap['authorities']['shot'], {}, archive_folder=tmp_path)
    record = next(tmp_path.glob('*.json')).read_text()
    assert 'locked camera conflicts' in record
    assert '"providerCalled": false' in record


def test_reviewed_payload_is_reverified_unchanged_after_prompt_director(monkeypatch, tmp_path):
    import cb_llm
    calls = []
    def fake_review(system, text, schema, **kwargs):
        calls.append(text)
        return review()
    monkeypatch.setattr(cb_llm, 'structured_with_repair', fake_review)
    snap = base_snapshot(supported_prompt('Keen runs back to the near-bank catapult with the honeycomb.'))
    env = {'prompt': snap['prompt'], 'durationSec': 12, 'references': snap['references'], 'audio': snap['audio'],
           'executionPlan': {'segments': [{'prompt': snap['prompt'], 'contract': {}}]}}
    PD.review_legacy_envelope(env, snap['authorities']['shot'], snap['authorities']['specialist'], archive_folder=tmp_path)
    assert calls
    reviewed = env['executionPlan']['segments'][0]['promptDirectorSnapshot']
    PD.verify_legacy_envelope(env)
    env['executionPlan']['segments'][0]['prompt'] += '\nMutation after review.'
    with pytest.raises(ValueError, match='STALE'):
        PD.verify_legacy_envelope(env)
    assert reviewed['prompt'] != env['executionPlan']['segments'][0]['prompt']
