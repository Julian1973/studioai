"""Scene-specific draft regression. Synthetic audio proves formatting, not production readiness."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket

import pytest
from cb_audio_authority import route_lines
from studio_character_roles import audit
from studio_director_card import ShotDirection
from studio_prompt_director import audio_policy, request_snapshot
from studio_seedance_execution import compile_prompt
from studio_source_segmentation import project

ROOT = Path(__file__).resolve().parent.parent
CANDIDATE = ROOT / 'cb-output/creative/Ep4_scene3_cinematic_revision_candidate.json'


@pytest.fixture
def candidate(monkeypatch):
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: pytest.fail('Network forbidden'))
    if not CANDIDATE.exists():
        pytest.skip('Local Scene 3 development artifact is not part of a clean source checkout')
    return json.loads(CANDIDATE.read_text())


def test_candidate_is_not_an_approval_or_measured_audio(candidate):
    assert candidate['approvalState'] == 'draft'
    assert candidate['mediaApprovalGranted'] is False
    assert candidate['blockingInputs']
    script = (ROOT / candidate['sourceScript']['contentPath']).read_text()
    assert hashlib.sha256(script.encode()).hexdigest() == candidate['sourceScript']['sha256']
    for shot in candidate['shots']:
        assert shot['approvalState'] == 'draft' and shot['timingStatus'] == 'estimated'
        assert not shot['productionReady']
        ShotDirection.model_validate(shot['directorCard'])
        for line in shot['dialogueLines']:
            projection = line['sourceSegmentation']
            assert project(line, script, boundary=projection['evidence']) == projection
        with pytest.raises(ValueError, match='immutable approved Audio1'):
            snapshot = request_snapshot('', {'shot': shot}, [], {}, shot['durationSec'])
            compile_prompt(snapshot, audit(snapshot))


@pytest.mark.parametrize('index', [0, 1])
def test_every_draft_view_reaches_emitter_with_test_only_audio(candidate, index):
    shot = candidate['shots'][index]
    before = deepcopy(shot)
    snapshot = request_snapshot(audio_policy(True), {'shot': shot}, [],
        {'hash': 'OFFLINE-TEST-NOT-APPROVED-AUDIO'}, shot['durationSec'])
    prompt, evidence = compile_prompt(snapshot, audit(snapshot))
    for view in shot['directorCard']['views']:
        assert view['action'] in prompt
        assert view['performance'] in prompt
        for key in ('angle', 'lens', 'movement', 'focus', 'light', 'composition'):
            assert view['cinematography'][key] in prompt
    routed = route_lines(shot['dialogueLines'])
    assert not routed['seedanceSfxCues']
    for line in routed['spokenDialogue']:
        assert '{' + line['exactText'] + '}' in prompt
    assert shot == before


def test_reaction_has_space_and_final_join_is_explicit(candidate):
    second = candidate['shots'][1]
    views = {view['viewId']: view for view in second['directorCard']['views']}
    assert views['S3.v08.oneBeatDroop']['timing'] == '12–14s'
    assert second['dialogueLines'][-1]['startSec'] == 14.8
    assert views['S3.v09.newPlanPivot']['entry'] == 'move'
    assert views['S3.v10.closingSoggyEvidence']['entry'] == 'cut'
