"""Rehearse outcome progression without providers or production-state mutations."""
from copy import deepcopy
import cb_production_contracts as C


def test_complete_review_journey_and_scoped_revision():
    row = {'shotId': 'S1.SH1', 'needsKeyframe': True, 'talky': True,
           'current': {}, 'pending': {}, 'allowedActions': {}}
    def code(): return C.shot_next_action(row)['code']
    assert code() == 'prepare-keyframe'
    row['pending']['keyframe'] = True
    row['allowedActions']['approveKeyframe'] = True
    assert code() == 'review-keyframe'
    row['current']['keyframe'] = True
    assert code() == 'prepare-voice'
    row['pending']['voice'] = True
    assert code() == 'review-voice'
    row['current']['voice'] = True
    assert code() == 'prepare-request'
    row['pending']['request'] = True
    assert code() == 'review-request'
    row['pending']['request'] = False
    row['pending']['animation'] = True
    row['allowedActions']['approveAnimation'] = True
    assert code() == 'review-candidate'
    row['acceptedAsset'] = {'accepted': True, 'intact': True}
    assert code() == 'review-cut'
    row['amendment'] = {'active': True, 'changedStage': 'voice'}
    row['current']['voice'] = False
    row['pending'] = {}
    assert code() == 'prepare-voice'
    assert row['current']['keyframe'] is True
    assert row['acceptedAsset']['intact'] is True


def test_silent_shot_goes_directly_to_request_and_projection_is_read_only():
    row = {'shotId': 'silent', 'needsKeyframe': False, 'talky': False, 'current': {}}
    before = deepcopy(row)
    for _ in range(3):
        assert C.shot_next_action(row)['stage'] == 'animation'
    assert row == before


def test_stale_candidate_is_not_presented_as_ready_for_approval():
    row = {'shotId': 's', 'needsKeyframe': True, 'pending': {'keyframe': True},
           'allowedActions': {'approveKeyframe': False}}
    assert C.shot_next_action(row)['state'] == 'needs-attention'


def test_missing_accepted_media_requests_recovery_not_new_paid_generation():
    row = {'shotId': 's', 'acceptedAsset': {'accepted': True, 'intact': False}}
    assert C.shot_next_action(row)['code'] == 'recover-media'


def test_voice_revision_discloses_dependencies_without_rebuilding_see():
    impact = C.revision_impact('voice', 's')
    assert impact['rebuild'] == ['voice performance', 'animation request', 'new render']
    assert 'Existing downstream media is not rewritten' in impact['continuity']
