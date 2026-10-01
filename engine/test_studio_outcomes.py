import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import cb_db
import studio_outcomes


def args():
    return dict(show_id="sample", session={"episode": "Ep1", "scene": "1", "selectedShotId": "SH1"},
                action="accept-voice", score=8, reason="The emotion lands", reviewer="Julian",
                request_id=str(uuid.uuid4()), candidate="A")


def test_review_survives_reopen_and_retry_without_duplicates(tmp_path):
    values = args()
    first = studio_outcomes.record(tmp_path, **values)
    assert studio_outcomes.record(tmp_path, **values) == first
    assert first["status"] == "review-requested"
    assert first["learningEligible"] is False
    with cb_db.transaction(tmp_path) as conn:
        assert conn.execute("SELECT count(*) FROM director_outcomes").fetchone()[0] == 1
    with pytest.raises(cb_db.StateConflict):
        studio_outcomes.record(tmp_path, **(values | {"score": 9}))


@pytest.mark.parametrize("change", [{"score": True}, {"score": 10.5}, {"score": 11},
    {"score": -1}, {"reason": " "}, {"request_id": "bad"}, {"action": "approve-spend"}])
def test_invalid_feedback_cannot_be_saved(tmp_path, change):
    with pytest.raises(ValueError):
        studio_outcomes.record(tmp_path, **(args() | change))


def test_parallel_reviews_are_not_lost(tmp_path):
    # Initialise the shared state schema before exercising concurrent review writes.
    with cb_db.transaction(tmp_path):
        pass
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: studio_outcomes.record(tmp_path, **args()), range(12)))
    with cb_db.transaction(tmp_path) as conn:
        assert conn.execute("SELECT count(*) FROM director_outcomes").fetchone()[0] == 12


def test_history_is_scoped_bounded_and_excludes_session_snapshots(tmp_path):
    assert studio_outcomes.history(tmp_path, show_id="sample", episode="Ep1", scene="1") == []
    studio_outcomes.record(tmp_path, **args())
    studio_outcomes.record(tmp_path, **(args() | {"show_id": "other"}))
    rows = studio_outcomes.history(tmp_path, show_id="sample", episode="Ep1", scene="1", shot_id="SH1", limit=1)
    assert len(rows) == 1 and rows[0]["score"] == 8
    assert "sessionSnapshot" not in rows[0]
    assert studio_outcomes.history(tmp_path, show_id="sample", episode="Ep2", scene="1") == []
    assert studio_outcomes.history(tmp_path, show_id="sample", episode="Ep1", scene="1", shot_id="SH2") == []
    with pytest.raises(ValueError):
        studio_outcomes.history(tmp_path, show_id="sample", episode="Ep1", scene="1", limit=True)
