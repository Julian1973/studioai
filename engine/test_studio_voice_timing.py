import base64
import hashlib
from types import SimpleNamespace
import pytest

from studio_transport import ProviderTransport
from studio_voice_timing import measured_timing, dialogue_cues
from studio_workspace import StudioError


def payload():
    return {'audio_base64': base64.b64encode(b'audio').decode(), 'voice_segments': [
        {'dialogue_input_index': 0, 'voice_id': 'voice-a', 'start_time_seconds': .2, 'end_time_seconds': 1.1},
        {'dialogue_input_index': 1, 'voice_id': 'voice-b', 'start_time_seconds': 1.8, 'end_time_seconds': 2.5}]}


def test_timestamped_adapter_preserves_actual_performance_and_maps_speakers(monkeypatch, tmp_path):
    transport = ProviderTransport(); calls = []
    def request(connection, key, endpoint, *, body):
        calls.append((endpoint, body))
        return SimpleNamespace(json=payload)
    monkeypatch.setattr(transport, 'request', request)
    monkeypatch.setattr(transport, 'verify_media', lambda *args: 3)
    inputs = [{'voice_id': 'voice-a', 'text': '[curious] Really?'}, {'voice_id': 'voice-b', 'text': '[softly] Yes.'}]
    timing = transport.voice({}, 'fake', 'eleven_v3', inputs, tmp_path/'voice.mp3')
    assert len(calls) == 1 and calls[0][0].endswith('/with-timestamps')
    assert calls[0][1]['inputs'] == inputs
    assert timing['lines'][1]['startSec'] == 1.8
    cues = dialogue_cues(timing, [{'speaker': 'A', 'text': 'Really?'}, {'speaker': 'B', 'text': 'Yes.'}], hashlib.sha256(b'audio').hexdigest())
    assert cues[0] == {'speaker': 'A', 'text': 'Really?', 'startSec': .2, 'endSec': 1.1}
    assert cues[1]['speaker'] == 'B'
    with pytest.raises(StudioError, match='another recording'):
        dialogue_cues(timing, [{'speaker': 'A', 'text': 'Really?'}], 'different')


@pytest.mark.parametrize('field,value', [('voice_id', 'wrong'), ('end_time_seconds', float('nan')), ('end_time_seconds', 31), ('dialogue_input_index', 3)])
def test_invalid_provider_timing_cannot_become_a_sync_contract(field, value):
    data = payload(); data['voice_segments'][0][field] = value
    with pytest.raises(StudioError):
        measured_timing(data, [{'voice_id': 'voice-a'}, {'voice_id': 'voice-b'}], 3, b'audio')
