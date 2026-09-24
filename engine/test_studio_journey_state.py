from studio_journey_native import _phase_from_policy


def test_unapproved_or_stale_package_returns_to_plan():
    board = {'approvalState': 'approved'}
    assert _phase_from_policy(board, {'packageCurrent': False}, {}, {}) == 'plan'
    # Canonical packageCurrent includes storyboard approval. The adapter does not
    # interpret a second board projection.
    assert _phase_from_policy({'approvalState': 'awaiting'},
                              {'packageCurrent': True}, {}, {}) == 'images'


def test_missing_records_open_the_first_required_step():
    assert _phase_from_policy({}, {}, None, {}) == 'prepare'
    assert _phase_from_policy({'approvalState': 'approved'},
                              {'packageCurrent': True}, None, {}) == 'images'


def test_predecessor_dependency_stays_a_dependency():
    shot = {'kf': 'waitingPrev', 'current': {'keyframe': False}}
    assert _phase_from_policy({'approvalState': 'approved'},
                              {'packageCurrent': True}, shot, {}) == 'dependency'


def test_only_current_animation_approval_completes_the_journey():
    board = {'approvalState': 'approved'}
    policy = {'packageCurrent': True}
    shot = {'current': {'keyframe': True, 'animation': False}}
    assert _phase_from_policy(board, policy, shot, {'status': 'approved'}) == 'audio'
    shot['current']['animation'] = True
    assert _phase_from_policy(board, policy, shot, {'status': 'approved'}) == 'complete'


def test_current_candidate_batch_is_reviewed_before_completion():
    board = {'approvalState': 'approved'}
    policy = {'packageCurrent': True}
    shot = {'animState': 'candidates-pending', 'current': {'animationBatch': True}}
    assert _phase_from_policy(board, policy, shot,
                              {'status': 'candidates-pending'}) == 'film'


def test_keyframe_is_the_boundary_between_see_and_hear():
    board = {'approvalState': 'approved'}
    policy = {'packageCurrent': True}
    shot = {'current': {'keyframe': False}}
    assert _phase_from_policy(board, policy, shot, {}) == 'images'
    shot['current']['keyframe'] = True
    assert _phase_from_policy(board, policy, shot, {}) == 'audio'
