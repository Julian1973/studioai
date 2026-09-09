import cb_voice_retime as V


def test_retime_requires_identical_reviewed_audio_and_approved_source(tmp_path, monkeypatch):
    raw = tmp_path / 'raw'; raw.write_bytes(b'paid performance')
    timing = tmp_path / 'timing'; timing.write_bytes(b'timestamps')
    wav = tmp_path / 'voice'; wav.write_bytes(b'reviewed retime')
    ledger = dict(voRawPath=str(raw), voTimingPath=str(timing), voPath=str(wav))
    previous = dict(approved=True, rawContentHash=V._hash(raw), timingContentHash=V._hash(timing))
    old = dict(dialogueHash='old', voiceIds=['a']); new = dict(dialogueHash='new', voiceIds=['a'])
    monkeypatch.setattr(V.cb_audio_timing, 'render_timed_dialogue_master',
                        lambda raw, timing, lines, duration, out: out.write_bytes(b'reviewed retime'))
    shot = dict(dialogueLines=[], durationSec=30)
    assert V.verify_reviewed_retime(ledger, shot, old, new, True, previous)
    assert not V.verify_reviewed_retime(ledger, shot, old, new, False, previous)
    assert not V.verify_reviewed_retime(ledger, shot, old, dict(new, voiceIds=['b']), True, previous)
    wav.write_bytes(b'different edit')
    assert not V.verify_reviewed_retime(ledger, shot, old, new, True, previous)
    wav.write_bytes(b'reviewed retime'); raw.write_bytes(b'changed source')
    assert not V.verify_reviewed_retime(ledger, shot, old, new, True, previous)
