"""Every stop the producer can hit reads as a sentence and a next action, never a code."""
import pytest
from studio_producer_language import translate, stopped_message


@pytest.mark.parametrize('raw, category, button', [
    ('WATCH_CONFIGURATION_REQUIRED: Complete the timed action and visible checkpoint states in DIRECT before building this storyboard.', 'direction', 'Open direction'),
    ('DIRECTOR_REVISION_REQUIRED: WATCH_AUTHORED_TIMED_ACTION_MISSING: unit=S1.SH1; DIRECT must author timed views', 'direction', 'Open direction'),
    ('HEAR_CONFIGURATION_REQUIRED: DIRECT ElevenLabs v3 performance direction is missing for dialogue-1', 'audio', 'Open direction'),
    ('WATCH_REFERENCE_MISSING: reference opening composition file is missing', 'references', 'Open images'),
    ('Approve the current WATCH request before firing its render.', 'request', 'Approve and film'),
    ('REFUSED — SPEND NOT APPROVED for 1.B1.S1', 'money', 'Approve spend'),
    ('openai.RateLimitError: credit_balance_exhausted', 'provider', 'Try again'),
    ('APITimeoutError: Request timed out.', 'provider', 'Try again'),
    ('REFUSED — no current signed scene plate found for Ep1 scene 1 — generate the internal world anchor before the first keyframe', 'images', 'Open scene plate'),
    ('BLOCKED: STALE PACKAGE — Prompt Director evidence does not match this request', 'stale', 'Review update'),
    ("REFUSED — Law 5: 1.B1.S1's approved voice does not match current direction", 'audio', 'Create audio'),
    ('This production asset is outside the Studio media library.', 'setup', 'Contact support'),
])
def test_known_stops_read_as_plain_sentences(raw, category, button):
    p = translate(raw, stage='submit_render')
    assert p['category'] == category and p['button'] == button
    assert p['headline'].endswith('.') and p['nextAction'].endswith('.')
    for jargon in ('WATCH_', 'DIRECTOR_', 'HEAR_', 'BLOCKED:', 'hash', 'payload', 'compil'):
        assert jargon not in p['headline'] and jargon not in p['nextAction']
    assert p['technical'] == raw  # support still gets the exact cause
    assert p['preserved'].startswith('Everything you approved')


def test_unknown_stop_never_says_unknown_to_the_producer():
    p = translate('ZeroDivisionError: division by zero')
    assert p['category'] == 'support'
    assert 'UNKNOWN' not in p['headline'] and 'not classified' not in p['headline']
    assert 'saved your approved work' in p['headline']
    line = stopped_message('ZeroDivisionError: division by zero')
    assert line.startswith('Studio stopped here') and 'Nothing you approved is lost' in line


def test_recovery_projection_classifies_known_stops_instead_of_unknown():
    from studio_recovery_projection import project
    r = project(stage='submit_render', scene_id='1', message='Approve the current WATCH request before firing its render.')
    assert r['classification'] != 'UNKNOWN' and r['errorCode'] != 'UNKNOWN'
    assert r['primaryCause'] == 'The render request needs approving before filming.'
    r = project(stage='prepare_render', scene_id='1', message='ZeroDivisionError: division by zero')
    assert r['classification'] == 'UNKNOWN'  # evidence stays honest; only the producer wording changes


def test_review_card_shows_the_producer_sentence_when_stopped():
    from studio_creative_review import present
    current = {'phase': 'audio', 'review': {'outcomes': {'see': {'status': 'approved'}, 'hear': {'status': 'approved'}}}}
    op = {'status': 'needs-decision', 'pending': 'submit_render',
          'decision': {'issue': 'Approve the current WATCH request before firing its render.',
                       'producer': translate('Approve the current WATCH request before firing its render.')}}
    card = present(current, op)
    assert card['state'] == 'waiting'
    assert card['message'] == 'The render request needs approving before filming. Approve the request to film this shot.'
    assert card['producer']['button'] == 'Approve and film'
    assert 'Production support' not in card['message']
