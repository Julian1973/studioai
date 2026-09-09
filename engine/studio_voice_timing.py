"""Measured ElevenLabs turns attached to the exact recording, never estimated."""
import hashlib
import math
from studio_workspace import StudioError


def measured_timing(payload, inputs, duration, audio):
    from cb_audio_timing import _source_ranges, _character_aligned_ranges, AudioTimingError
    segments = payload.get('voice_segments') or []
    try:
        for segment in segments:
            index = segment['dialogue_input_index']
            if type(index) is not int or not 0 <= index < len(inputs) or segment['voice_id'] != inputs[index]['voice_id']:
                raise ValueError()
        ranges = (_character_aligned_ranges(payload, segments, len(inputs)) or
                  _source_ranges(payload, len(inputs)))
        if len(ranges) != len(inputs) or any(not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= duration + .02)
                                            for start, end in ranges):
            raise ValueError()
    except (AudioTimingError, ValueError, KeyError, TypeError):
        raise StudioError('The returned voice timing does not match the submitted speakers or recording. The returned file is preserved; no second generation was submitted.', 'invalid_output') from None
    return {'authority': 'provider timestamps; not an auditory verdict', 'audioSha256': hashlib.sha256(audio).hexdigest(),
            'duration': duration, 'lines': [{'inputIndex': index, 'voiceId': inputs[index]['voice_id'],
                                           'startSec': start, 'endSec': end} for index, (start, end) in enumerate(ranges)]}


def dialogue_cues(timing, dialogue, audio_hash):
    if not timing:
        return []  # Older approved recordings are not assigned imaginary timings.
    if timing.get('audioSha256') != audio_hash or len(timing.get('lines', [])) != len(dialogue):
        raise StudioError('The measured dialogue timing belongs to another recording.', 'timing_mismatch')
    return [{'speaker': line['speaker'], 'text': line['text'], 'startSec': cue['startSec'], 'endSec': cue['endSec']}
            for line, cue in zip(dialogue, timing['lines'])]
