import copy
import hashlib
import json
import pytest
from studio_approved_media_projection import watch_shot, reference_records


@pytest.fixture
def media(tmp_path):
    audio=tmp_path/'audio.wav';audio.write_bytes(b'immutable master')
    timing=tmp_path/'timing.json';timing.write_text('{}')
    receipt=tmp_path/'placement.json'
    receipt.write_text(json.dumps({'outputPath':str(audio),'outputSha256':hashlib.sha256(audio.read_bytes()).hexdigest(),
        'dialogueTimingPath':str(timing),'dialogueTimingSha256':hashlib.sha256(timing.read_bytes()).hexdigest(),
        'placements':[{'dialogueOccurrenceId':'line1','targetStartSec':11.8,'targetEndSec':14.44}]}))
    return {'shotId':'S2.SH1','durationSec':16,'dialogueLines':[{'dialogueOccurrenceId':'line1','speaker':'Aida','exactText':'Exact words','startSec':11.8,'endSec':15.2}]}, {'voiceApproval':{'approved':True,'path':str(audio)},'voPlacementPath':str(receipt)}


def test_placement_owns_timing_without_mutating_approval_or_words(media):
    s,l=media;before=copy.deepcopy(media);out=watch_shot(s,l)
    assert out['dialogueLines'][0]['endSec']==14.44
    assert out['dialogueLines'][0]['exactText']=='Exact words'
    assert media==before
    assert watch_shot(out,l)==out


def test_changed_audio_blocks_projection(media):
    s,l=media
    from pathlib import Path
    Path(l['voiceApproval']['path']).write_bytes(b'different')
    with pytest.raises(ValueError,match='placement receipt'):watch_shot(s,l)


def test_completion_state_uses_same_measured_interval(media):
    s,l=media;s['directorCard']={'stateChanges':[{'entityId':'char:aida','atSec':15.2,
        'beforeValues':{'spokenLineStatus':'unspoken'},
        'afterValues':{'spokenLineStatus':'completed: Exact words'}}]}
    out=watch_shot(s,l);event=out['directorCard']['stateChanges'][0]
    assert event['atSec']==14.44 and event['dialogueOccurrenceId']=='line1'
    assert watch_shot(out,l)==out


def test_occurrences_not_guessed_by_text(media):
    s,l=media;s['dialogueLines'][0]['dialogueOccurrenceId']='other'
    with pytest.raises(ValueError,match='no placement'):watch_shot(s,l)


def test_approved_vision_authority_is_content_only(tmp_path):
    image=tmp_path/'vision.png';image.write_bytes(b'approved vision')
    refs=[{'role':'vision:party','path':str(image)}]
    ledger={'visionReferenceBinding':{'role':'vision:party','sourcePath':str(image),
        'sourceSha256':hashlib.sha256(image.read_bytes()).hexdigest(),'approvedBy':'Julian','scope':'vision only'}}
    out=reference_records(refs,ledger)
    assert out[0]['stateScope']['authority']=='vision_content'
    assert out[0]['stateScope']['controlsGeography'] is False
    assert out[0]['stateScope']['physicalPresence'] is False
    assert 'stateScope' not in refs[0]
    image.write_bytes(b'replaced')
    with pytest.raises(ValueError,match='changed'):reference_records(refs,ledger)
