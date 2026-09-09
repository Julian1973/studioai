"""Verify timing-only reuse without granting approval or calling a provider."""
import hashlib
import tempfile
from pathlib import Path
import cb_audio_timing


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_reviewed_retime(ledger, shot, old_signature, signature, same_request, previous):
    if not same_request or not previous.get('approved'):
        return False
    # Only the dialogue timing hash may differ; canon, voices and rules must match.
    excluded = {'dialogueHash', 'performanceHash'}
    if ({k: v for k, v in old_signature.items() if k not in excluded} !=
            {k: v for k, v in signature.items() if k not in excluded}):
        return False
    try:
        if not previous.get('rawContentHash') or not previous.get('timingContentHash'):
            return False
        if (_hash(ledger['voRawPath']) != previous['rawContentHash'] or
                _hash(ledger['voTimingPath']) != previous['timingContentHash']):
            return False
        with tempfile.TemporaryDirectory(prefix='studio-retime-check-') as folder:
            output = Path(folder) / 'verify.wav'
            cb_audio_timing.render_timed_dialogue_master(
                ledger['voRawPath'], ledger['voTimingPath'],
                shot['dialogueLines'], shot['durationSec'], output)
            return _hash(output) == _hash(ledger['voPath'])
    except (OSError, ValueError, KeyError, RuntimeError):
        return False
