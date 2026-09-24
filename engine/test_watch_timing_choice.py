from copy import deepcopy

import pytest

from studio_authored_action import resolve_timing_choice


TEXT = 'Sunny speaks; during or just after the line, another drop hits a lantern behind her.'


def fixture():
    return ({'stateChanges': [{'atSec': 17.4, 'entityId': 'prop.lanterns',
             'cause': 'After the approved spoken line completes, the next drop hits the lantern.'}]},
            {'dialogueLines': [{'endSec': 17.146}]})


def test_timing_alternative_is_resolved_from_existing_evidence_only():
    card, shot = fixture()
    before = deepcopy((card, shot))
    result, trace = resolve_timing_choice(TEXT, card, shot, 14.1, 18)
    assert result == 'Sunny speaks; at 17.4s, after the line ends at 17.146s, another drop hits a lantern behind her.'
    assert trace['sourceText'] == TEXT
    assert trace['checkpoint'] == card['stateChanges'][0]
    assert (card, shot) == before


@pytest.mark.parametrize('change', ['entity', 'cause', 'early', 'multiple', 'no_audio', 'two_lines'])
def test_uncertain_or_contradictory_evidence_never_rewrites_action(change):
    card, shot = fixture()
    event = card['stateChanges'][0]
    if change == 'entity': event['entityId'] = 'prop.cup'
    if change == 'cause': event['cause'] = 'A drop hits while she speaks.'
    if change == 'early': event['atSec'] = 16
    if change == 'multiple': card['stateChanges'].append(deepcopy(event))
    if change == 'no_audio': shot['dialogueLines'] = []
    if change == 'two_lines': shot['dialogueLines'].append({'endSec': 17.8})
    assert resolve_timing_choice(TEXT, card, shot, 14.1, 18) == (TEXT, None)
