"""Explicit ownership and route enforcement; not face recognition qualification."""
from copy import deepcopy
import hashlib
import json
import socket
import pytest
from studio_character_roles import audit, emit, bind_visual_names
from studio_prompt_director import run, verify, review_legacy_envelope, return_review
from test_studio_prompt_director import review


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: pytest.fail('No network permitted'))


def _view(view_id, timing, characters, action):
    """One authored view in the current typed shape: entry, timing, action, and the camera,
    performance and landing every WATCH view is built from."""
    start = float(timing.split('–')[0])
    return dict(
        viewId=view_id, timing=timing, atSec=start,
        entry='opening' if start == 0 else 'cut',
        visibleEntities=[f'character:{name}' for name in characters],
        action=action,
        framing='Medium-wide on the comb, held at bee height',
        cameraPurpose='Keep both bodies readable through the move',
        performance='Wings drive the body; the head leads each change of direction',
        staging=f"{' and '.join(characters)} on the comb",
        startState=f"{' and '.join(characters)} in position as the view opens",
        endState=action,
    )


@pytest.fixture
def source(tmp_path):
    def ref(index, name):
        path = tmp_path / (name + '.jpeg')
        path.write_bytes(name.encode())
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        return dict(slot=f'@图{index}', name=name, role=name,
                    path=str(path), sha256=sha,
                    canonicalIdentity=dict(character=name, path=str(path), hash=sha))
    characters = ['Zenny', 'Fuzzby', 'Keen']
    roles = [dict(character='Zenny', identityTraits={'face': 'small dark nose; long eyelashes'},
                  allowedActions=['stays on her leaf'], exclusiveActions=['meditates on her leaf', 'gives the final wink']),
             dict(character='Fuzzby', identityTraits={'face': 'bulbous tan nose; round spectacles'},
                  allowedActions=['chases Keen'], exclusiveActions=['pursues Keen', 'perches on the comb']),
             dict(character='Keen', allowedActions=['runs upright'])]
    # The unit declares its own duration (26s: views run to 26s, the line ends at 19.56s).
    # A segment is projected onto the source unit's clock, so a shot authority without one
    # cannot be matched against the request duration and is refused before any role check.
    shot = dict(shotId='S1.SH2', durationSec=26, charactersInFrame=characters,
                dialogueLines=[dict(speaker='Fuzzby', exactText='Nice machine.', startSec=18, endSec=19.56)],
                directorCard=dict(characterRoles=roles,
                                  audienceFocus='Read the chase, then land on Zenny\'s wink.', views=[
                    # Authored coverage now accounts for the whole unit, contiguously — the
                    # two named beats keep their exact original timings; the frames between
                    # them are stated rather than left as gaps the contract cannot read.
                    _view('approach', '0–6s', ['Fuzzby', 'Keen'], 'Keen breaks from the comb and Fuzzby lifts after him.'),
                    _view('chase', '6–10s', ['Fuzzby', 'Keen'], 'Fuzzby pursues Keen along the comb.'),
                    _view('settle', '10–23.4s', ['Fuzzby', 'Keen'], 'The chase tires and both of them settle, breath returning.'),
                    _view('ending', '23.4–26s', ['Zenny'], 'Zenny gives the final wink from her leaf.')]))
    return dict(prompt='[Audience Purpose]\nRead the chase.\n[Shot Sequence]\nShot 1: 6–10s\nAction: Fuzzby pursues Keen.\n\nShot 2: 23.4–26s\nAction: Zenny gives the final wink.\n[Audio]\n@Audio1 unchanged. {Nice machine.}',
                authorities=dict(shot=shot, specialist={}), duration=26,
                references=[dict(role='opening keyframe', slot='@图1'), dict(role='previous shot final frame', slot='@图2')] +
                           [ref(i, name) for i, name in enumerate(characters, 3)],
                audio=dict(hash='approved-audio-hash'), settings={})


@pytest.mark.parametrize('bad', [
    'Fuzzby from @图3 pursues Keen.', 'Zenny from @图4 stays on her leaf.',
    'FUZZBY_ID is @图3.', '@图3 = Fuzzby.', '@图4 defines Zenny identity.',
    'Zenny pursues Keen.', 'Zenny @图3 perches on the comb.',
    'Fuzzby meditates on her leaf.', 'Fuzzby gives the final wink.',
])
def test_zenny_fuzzby_role_swap_blocks_before_fire(source, bad, tmp_path, monkeypatch):
    import cb_llm
    source['prompt'] += '\n' + bad
    before_audio = deepcopy(source['audio'])
    monkeypatch.setattr(cb_llm, 'structured_with_repair', lambda *a, **k: pytest.fail('Blocked roles must not spend on review'))
    env = dict(prompt=source['prompt'], durationSec=26, references=source['references'], audio=source['audio'],
               executionPlan={'segments': [dict(prompt=source['prompt'], contract={})]})
    # The refusal now names the role fault itself rather than a bare 'BLOCKED' prefix.
    # Asserting the code is stricter than the old wording, and the report assertions below
    # remain the real safeguard: blocked status, no provider call, no spend, audio untouched.
    with pytest.raises(ValueError, match=r'CHARACTER_(REFERENCE_ROLE|ACTION_OWNER)_MISMATCH'):
        review_legacy_envelope(env, source['authorities']['shot'], {}, archive_folder=tmp_path / 'reports')
    records = [json.loads(p.read_text()) for p in (tmp_path / 'reports').glob('*.json')]
    assert len(records) == 1
    report = records[0]['review']
    assert report['characterRoleIntegrity']['status'] == 'BLOCKED'
    assert report['characterRoleIntegrity']['errors'][0]['expected']
    assert report['characterRoleIntegrity']['errors'][0]['actual']
    assert report['providerCalled'] is False and report['spendOccurred'] is False
    assert report['payloadHash'] and report['correctiveAction']
    assert 'pendingSpendAuth' not in env
    assert env['audio'] == before_audio


def test_putting_a_locked_line_in_another_mouth_blocks_before_fire(source, tmp_path, monkeypatch):
    """Was a role-swap parameter until 20 Sep 2026. Giving Zenny Fuzzby's locked line is
    caught by locked-dialogue ownership before the role audit runs, so it proves a
    different safeguard and asserts it directly: refused, archived, and nothing spent."""
    import cb_llm
    source['prompt'] += '\nZenny says {Nice machine.}'
    before_audio = deepcopy(source['audio'])
    monkeypatch.setattr(cb_llm, 'structured_with_repair',
                        lambda *a, **k: pytest.fail('A blocked prompt must not spend on review'))
    env = dict(prompt=source['prompt'], durationSec=26, references=source['references'],
               audio=source['audio'],
               executionPlan={'segments': [dict(prompt=source['prompt'], contract={})]})
    with pytest.raises(ValueError, match='unmatched or repeated dialogue occurrences'):
        review_legacy_envelope(env, source['authorities']['shot'], {}, archive_folder=tmp_path / 'reports')
    assert 'pendingSpendAuth' not in env
    assert env['audio'] == before_audio


def test_actual_upload_order_drives_inline_names_and_preserves_audio(source):
    before = deepcopy(source)
    matrix = audit(source)
    emitted = emit(source['prompt'], matrix)
    assert 'Action: Fuzzby @图4 pursues Keen @图5.' in emitted
    assert 'Action: Zenny @图3 gives the final wink.' in emitted
    assert emitted.split('[Audio]')[1] == source['prompt'].split('[Audio]')[1]
    assert source == before
    assert bind_visual_names(emitted, matrix) == emitted
    # Remove the previous final frame and rebuild the actual manifest, not a
    # hard-coded Crystal Bears index table.
    del source['references'][1]
    for i, ref in enumerate(source['references'], 1):
        ref['slot'] = f'@图{i}'
    changed = emit(source['prompt'], audit(source))
    assert 'Fuzzby @图3 pursues Keen @图4' in changed


def test_quotes_and_spoken_action_are_verbatim_even_inside_visual_fields(source):
    text = 'Action: Keen reads {Fuzzby}. Zenny holds.\nSpoken action: Fuzzby says {Nice machine.}\n[Audio]\nKeen and Fuzzby @Audio1.'
    result = bind_visual_names(text, audit(source))
    assert '{Fuzzby}' in result and 'Keen @图5 reads' in result
    assert result.split('Spoken action:')[1] == text.split('Spoken action:')[1]


def test_review_added_visual_names_are_bound_before_final_review_and_seal(source):
    inputs = []

    def reviewer(system, value):
        inputs.append(deepcopy(value))
        result = review()
        if len(inputs) == 1:
            result['edits'] = [dict(
                old='Action: Fuzzby @图4 pursues Keen @图5.',
                new='Action: Fuzzby @图4 pursues Keen @图5. Zenny stays on her leaf.',
                source='Approved Zenny role: stays on her leaf.',
                reason='Keep the non-chasing character on her approved leaf.')]
        return result

    final, report = run(source, reviewer)
    assert len(inputs) == 2
    assert 'Zenny @图3 stays on her leaf.' in inputs[1]['prompt']
    assert 'Zenny @图3 stays on her leaf.' in final['prompt']
    from studio_seedance_execution import sections
    assert dict(sections(final['prompt']))['Audio'] == dict(sections(source['prompt']))['Audio']
    verify(final, report)


def test_source_file_and_registry_binding_changes_block(source):
    bad = deepcopy(source)
    bad['references'][2]['path'] = bad['references'][3]['path']
    bad['references'][2]['sha256'] = bad['references'][3]['sha256']
    assert audit(bad)['status'] == 'BLOCKED'
    # Same path, different bytes cannot borrow the sealed identity approval.
    from pathlib import Path
    Path(source['references'][3]['path']).write_bytes(b'new identity')
    assert audit(source)['status'] == 'BLOCKED'


def test_shared_identity_requires_explicit_source_exception(source):
    a, b = source['references'][2:4]
    b.update(path=a['path'], sha256=a['sha256'],
             canonicalIdentity=dict(character='Fuzzby', path=a['path'], hash=a['sha256']))
    assert any(e['code'] == 'CHARACTER_IDENTITY_SOURCE_SHARED' for e in audit(source)['errors'])
    source['authorities']['shot']['directorCard']['sharedIdentityExceptions'] = [
        dict(characters=['character:Zenny', 'character:Fuzzby'], authorisation='synthetic-authorisation-1')]
    assert audit(source)['status'] == 'BLOCKED'  # prose is not execution authority
    source['authorities']['identityAuthorisations'] = [dict(id='synthetic-authorisation-1',
        characters=['character:Zenny', 'character:Fuzzby'], authorisedBy='Test director', shotId='S1.SH2')]
    assert audit(source)['status'] == 'PASS'


def test_structured_dialogue_and_action_owner_cannot_be_transferred(source):
    source['authorities']['specialist']['timeline'] = [dict(channel='dialogue', performer='Zenny', event='Nice machine.', startSec=18)]
    assert any(e['code'] == 'CHARACTER_DIALOGUE_OWNER_MISMATCH' for e in audit(source)['errors'])
    source['authorities']['specialist'].clear()
    event = dict(eventId='chase', viewId='chase', character='Fuzzby', action='pursue')
    source['authorities']['shot']['directorCard']['characterRoleEvents'] = [event]
    source['authorities']['specialist']['characterRoleEvents'] = [{**event, 'character': 'Zenny'}]
    assert any(e['code'] == 'CHARACTER_ACTION_OWNER_MISMATCH' for e in audit(source)['errors'])


def test_role_seal_rechecked_and_inherited_by_returned_review(source):
    final, report = run(source, lambda *a: review())
    assert report['characterRoleIntegrity']['matrixHash']
    verify(final, report)
    returned = return_review(report, {'hash': 'returned-take'}, [], method='sampled frames', ranges=[[6, 10]])
    assert returned['characterRoleIntegrity'] == report['characterRoleIntegrity']
    assert returned['audioLipSync'] == 'unverified'
    from pathlib import Path
    Path(source['references'][3]['path']).write_bytes(b'changed after sealing')
    with pytest.raises(ValueError, match='CHARACTER ROLE'):
        verify(final, report)


def test_role_report_persistence_failure_prevents_sealing(source, tmp_path, monkeypatch):
    import cb_llm, studio_request_evidence
    source['prompt'] += '\nFuzzby from @图3.'
    monkeypatch.setattr(cb_llm, 'structured_with_repair', lambda *a, **k: pytest.fail('No review call'))
    def unavailable(*args):
        raise OSError('disk unavailable')
    monkeypatch.setattr(studio_request_evidence, '_write', unavailable)
    env = dict(prompt=source['prompt'], durationSec=26, references=source['references'], audio=source['audio'],
               executionPlan={'segments': [dict(prompt=source['prompt'], contract={})]})
    with pytest.raises(OSError, match='disk unavailable'):
        review_legacy_envelope(env, source['authorities']['shot'], {}, archive_folder=tmp_path)
    assert not env['executionPlan']['segments'][0].get('promptDirector')


def test_bounded_source_edit_does_not_invent_canonical_image_tags(source, tmp_path):
    video = tmp_path / 'approved.mp4'; video.write_bytes(b'approved synthetic take')
    sha = hashlib.sha256(video.read_bytes()).hexdigest()
    source['authorities']['editScope'] = dict(startSec=1, endSec=2,
        outsideWindow='preserve approved source', audio='immutable', sourceSha256=sha)
    source['references'] = [dict(role='approved source video; preserve outside declared edit window', path=str(video), sha256=sha)]
    matrix = audit(source)
    assert matrix['status'] == 'WARN' and matrix['characters'] == []
    assert matrix['sourcePreservation']['identityReplacementQualified'] is False
    video.write_bytes(b'changed')
    assert audit(source)['status'] == 'BLOCKED'
