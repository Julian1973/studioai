"""Every stop the producer can hit reads as a sentence and a next action, never a code."""
import pytest
from studio_producer_language import RULES, _next_stage, translate, stopped_message


@pytest.mark.parametrize('raw, category, button', [
    ('WATCH_CONFIGURATION_REQUIRED: Complete the timed action and visible checkpoint states in DIRECT before building this storyboard.', 'direction', 'Open direction'),
    ('DIRECTOR_REVISION_REQUIRED: WATCH_AUTHORED_TIMED_ACTION_MISSING: unit=S1.SH1; DIRECT must author timed views', 'direction', 'Open direction'),
    ('HEAR_CONFIGURATION_REQUIRED: DIRECT ElevenLabs v3 performance direction is missing for dialogue-1', 'audio', 'Open direction'),
    ('WATCH_REFERENCE_MISSING: reference opening composition file is missing', 'references', 'Open images'),
    ('DIRECT_AUDIO_TIMING_CONFLICT: char:Sunny checkpoint at 20.5s says it follows Sunny\'s approved line, which ends at 29.5s', 'audio', 'Review timing in DIRECT'),
    ('WATCH_CONFIGURATION_REQUIRED: S4.SH3 opening inputs changed; review the saved image against the current prior final frame in SEE', 'images', 'Review opening frame'),
    ('REFUSED — opening frame is not a playable stage: opening geography does not provide visible depth ahead; opening frame does not reserve lead room for travel', 'images', 'Review opening frame'),
    ('REFUSED — keyframe prompt [SUBJECTS] does not contain the approved DIRECT direction in provider-safe wording', 'direction', 'Review in DIRECT'),
    ('Director handoff incomplete: Director handoff needs explicit event completion times.', 'direction', 'Open direction'),
    ('HEAR_CONFIGURATION_REQUIRED: voice leaves 0.10s for the 0.50s landing hold', 'direction', 'Review timing in DIRECT'),
    ('WATCH_REFERENCE_MISSING: reference opening composition file is missing', 'references', 'Open images'),
    ('WATCH_PROMPT_REVIEW_REQUIRED: reviewer evidence is invalid after correction', 'review', 'Review WATCH'),
    ('Approve the current WATCH request before firing its render.', 'request', 'Review WATCH request'),
    ('REFUSED — SPEND NOT APPROVED for 1.B1.S1', 'money', 'Review spend in WATCH'),
    ('openai.RateLimitError: credit_balance_exhausted', 'provider', 'View details'),
    ('APITimeoutError: Request timed out.', 'provider', 'Check existing job'),
    ('REFUSED — no current signed scene plate found for Ep1 scene 1 — generate the internal world anchor before the first keyframe', 'images', 'Open scene plate'),
    ('WATCH_SOURCE_PACKAGE_MISMATCH: storyboard and production package contain different shot rosters', 'request', 'Open WATCH'),
    ('REFUSED — opening-frame approval is stale against its direct inputs', 'images', 'Review opening frame'),
    ('BLOCKED: STALE PACKAGE — Prompt Director evidence does not match this request', 'stale', 'Review update'),
    ("REFUSED — Law 5: 1.B1.S1's approved voice does not match current direction", 'audio', 'Create audio'),
    ('This production asset is outside the Studio media library.', 'setup', 'View file details'),
])
def test_known_stops_read_as_plain_sentences(raw, category, button):
    p = translate(raw, stage='submit_render')
    assert p['category'] == category and p['button'] == button
    assert p['headline'].endswith('.') and p['nextAction'].endswith('.')
    for jargon in ('WATCH_', 'DIRECTOR_', 'HEAR_', 'BLOCKED:', 'hash', 'payload', 'compil'):
        assert jargon not in p['headline'] and jargon not in p['nextAction']
    assert p['technical'] == raw  # support still gets the exact cause
    assert p['preserved'].startswith('Everything you approved')


def test_recovery_points_to_the_stage_and_asset_that_can_fix_it():
    opening = translate('REFUSED — opening-frame approval is stale against its direct inputs', stage='prepare_render')
    assert (opening['targetStage'], opening['component']) == ('see', 'opening')
    plate = translate('REFUSED — no current signed scene plate found', stage='prepare_render')
    assert (plate['targetStage'], plate['component']) == ('see', 'plate')
    direct = translate('HEAR_CONFIGURATION_REQUIRED: performance direction is missing', stage='create_audio')
    assert direct['targetStage'] == 'direct'
    voice = translate('Law 5: approved voice does not match current direction', stage='prepare_render')
    assert voice['targetStage'] == 'hear'
    timing = translate('DIRECT_AUDIO_TIMING_CONFLICT: a checkpoint overlaps the approved line', stage='prepare_render')
    assert timing['targetStage'] == 'direct'
    stale_watch_inputs = translate('WATCH_CONFIGURATION_REQUIRED: opening inputs changed; review in SEE against prior final frame', stage='prepare_render')
    assert (stale_watch_inputs['targetStage'], stale_watch_inputs['component']) == ('see', 'opening')
    hold = translate('HEAR_CONFIGURATION_REQUIRED: voice leaves 0.10s for landing hold', stage='create_audio')
    assert hold['targetStage'] == 'direct'
    review = translate('WATCH_PROMPT_REVIEW_REQUIRED: reviewer evidence is invalid after correction', stage='submit_render')
    assert review['targetStage'] == 'watch'
    render = translate('BLOCKED: STALE PACKAGE', stage='submit_render')
    assert render['targetStage'] == 'watch'


def test_every_refusal_rule_routes_to_a_browser_verified_remedy():
    # test_journey_workflow_browser.mjs opens each stage, opens the evidence drawer,
    # and runs the provider-job recovery action. Keep this set aligned with those
    # exercised UI routes so a new refusal cannot point at an unimplemented remedy.
    tested_routes = {'direct', 'see', 'hear', 'watch', 'recover', 'details'}
    assert RULES
    for pattern, category, _headline, _meaning, action, button in RULES:
        target = _next_stage(category, 'submit_render', action)
        assert target in tested_routes, (pattern, category, action, target)
        assert action.strip().endswith('.') and button.strip()


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
    assert card['message'] == 'The render request needs approving before filming. Review the sealed request and its cost in WATCH. No provider call occurs until you explicitly approve Fire.'
    assert card['producer']['button'] == 'Review WATCH request'
    assert 'Production support' not in card['message']


def test_a_journey_stop_keeps_its_traceback_for_support(monkeypatch, tmp_path):
    """The producer reads one sentence; the saved decision carries the exact origin."""
    import studio_journey_http as H
    class Server: ROOT = tmp_path
    monkeypatch.setattr(H, 'controller', lambda server, scope: (_ for _ in ()).throw(AttributeError("'str' object has no attribute 'get'")))
    out = H.request(Server(), {'scope': {'projectId': 'crystal-bears', 'episode': 'Ep4', 'scene': '2', 'unit': 'S2.SH1'}, 'action': 'resume'})
    assert out['ok'] is False
    assert "'str' object has no attribute 'get'" in out['error']['technicalMessage']
    assert 'Traceback' in out['error']['trace'] and 'AttributeError' in out['error']['trace']
