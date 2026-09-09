import copy
import json
import struct
import wave
import pytest
from cb_voice_reuse import derive, current_requests, sha


@pytest.fixture
def source(tmp_path):
    audio = tmp_path / 'approved.wav'
    with wave.open(str(audio), 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(1000)
        wav.writeframes(b''.join(struct.pack('<h', i if 1000 <= i < 1400 or 3000 <= i < 3600 else 0)
                                for i in range(5000)))
    placement = tmp_path / 'approved.timing.json'
    placement.write_text(json.dumps({'placements':[
        dict(dialogueOccurrenceId='a', targetStartSec=1, targetEndSec=1.4),
        dict(dialogueOccurrenceId='b', targetStartSec=3, targetEndSec=3.6)]}))
    lines = [dict(dialogueOccurrenceId=oid, sourceEventId=oid, speaker='Hero',
                  exactText=text, startSec=start, endSec=end) for oid, text, start, end in
             [('a','First.',1,1.5),('b','Second.',3,3.7)]]
    shot = dict(shotId='S1.SH1', durationSec=5, dialogueLines=lines)
    ledger = dict(voPath=str(audio), voPlacementPath=str(placement),
        voiceApproval=dict(approved=True, path=str(audio), contentHash=sha(audio),
                           placementContentHash=sha(placement)),
        voGeneratedFrom=[dict(dialogueOccurrenceId=x['dialogueOccurrenceId'], voiceId='voice',
                             text=x['exactText']) for x in lines])
    target = dict(shotId='S1.SH2', durationSec=4, dialogueLines=[{**lines[1], 'startSec':1, 'endSec':1.7}])
    return shot, ledger, target, tmp_path / 'reused.wav'


def test_split_reuses_exact_samples_and_preserves_source_approval(source):
    shot, ledger, target, out = source
    before = copy.deepcopy(ledger); original = sha(ledger['voPath'])
    bundle = derive(shot, ledger, target, out, 'Reuse approved takes in the split')
    with wave.open(str(out), 'rb') as wav:
        data = wav.readframes(wav.getnframes()); assert wav.getnframes() == 4000
    with wave.open(ledger['voPath'], 'rb') as wav: original_data = wav.readframes(wav.getnframes())
    assert data[2000:3200] == original_data[6000:7200]
    assert ledger == before and sha(ledger['voPath']) == original
    assert current_requests(bundle, target) == [ledger['voGeneratedFrom'][1]]
    assert bundle['voicePerformanceReuse']['newHumanAuditionClaimed'] is False


@pytest.mark.parametrize('change', ['words','speaker','source','overrun','unapproved','unauthorised','duplicate'])
def test_reuse_rejects_changed_authority_or_clipped_take(source, change):
    shot, ledger, target, out = source; auth = 'Preserve takes'
    if change == 'words': target['dialogueLines'][0]['exactText'] = 'Different.'
    if change == 'speaker': target['dialogueLines'][0]['speaker'] = 'Other'
    if change == 'source':
        with open(ledger['voPath'], 'ab') as f: f.write(b'changed')
    if change == 'overrun': target['dialogueLines'][0]['endSec'] = 1.3
    if change == 'unapproved': ledger['voiceApproval']['approved'] = False
    if change == 'unauthorised': auth = ''
    if change == 'duplicate': target['dialogueLines'] *= 2
    with pytest.raises(ValueError): derive(shot, ledger, target, out, auth)
    assert not out.exists()


def test_changed_voice_brief_or_timing_stops_using_inherited_request(source):
    shot, ledger, target, out = source
    bundle = derive(shot, ledger, target, out, 'Keep this performance')
    target['voiceDirectorBrief'] = 'Make a new performance'
    assert current_requests(bundle, target) is None
    target.pop('voiceDirectorBrief'); target['dialogueLines'][0]['startSec'] = 2
    assert current_requests(bundle, target) is None
