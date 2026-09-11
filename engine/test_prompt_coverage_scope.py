"""Verify production writer/reviewer receive the same unit-boundary instructions."""
import pytest
import cb_departments as D
import studio_prompt_director as P


def test_live_animation_writer_receives_unit_scope_and_audio_rules(monkeypatch):
    captured={}
    class Captured(Exception):pass
    def stop(system,prompt,*args,**kwargs):
        captured.update(system=system,prompt=prompt)
        raise Captured()
    monkeypatch.setattr(D.cb_llm,'structured_with_repair',stop)
    with pytest.raises(Captured):
        D._prepare_animation_once({'shot':{'shotId':'TEST','durationSec':16}},[])
    assert 'current production unit, not a single camera view' in captured['system']
    assert 'last included view' in captured['system']
    assert 'measured Audio1 timing' in captured['system']
    assert 'never truncate camera or performance clauses' in captured['system']


def test_final_reviewer_distinguishes_included_next_view_from_out_of_scope_action():
    assert "A 'next view' action is valid when that view is included" in P.SYSTEM
    assert 'incomplete semantic clauses with exact payload quotes' in P.SYSTEM
    assert 'unavailable pixel evidence' in P.SYSTEM
    assert 'Never edit audio/speech/lip-sync instructions' in P.SYSTEM
