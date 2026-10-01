"""Durable human scores for Director review requests, separate from approvals.

Records describe what the human requested against a server-side session snapshot.
They do not assert that asynchronous approval or regeneration succeeded and cannot
promote learning rules or contact a provider.
"""
import hashlib
import json
import uuid

import cb_db


REVIEW_ACTIONS = frozenset({
    "accept-keyframe", "iterate-keyframe", "accept-voice", "iterate-voice",
    "accept-animation", "iterate-animation", "accept-master", "iterate-master",
})


def record(root, *, show_id, session, action, score, reason, reviewer, request_id, candidate=None):
    if action not in REVIEW_ACTIONS:
        raise ValueError("action is not a creative review")
    if type(score) is not int or not 0 <= score <= 10:
        raise ValueError("score must be an integer from 0 to 10")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
        raise ValueError("a review reason of 1 to 2000 characters is required")
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 100:
        raise ValueError("reviewer is required")
    try:
        uuid.UUID(request_id)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("request ID must be a UUID") from exc
    snapshot = json.dumps(session, sort_keys=True, ensure_ascii=False, allow_nan=False)
    values = {
        "requestId": request_id, "showId": show_id,
        "episode": session["episode"], "scene": session["scene"],
        "shotId": session.get("selectedShotId"), "action": action,
        "requestedCandidate": candidate,
        "score": score, "reason": reason.strip(), "reviewer": reviewer.strip(),
        "sessionHash": hashlib.sha256(snapshot.encode()).hexdigest(),
        "sessionSnapshot": session, "status": "review-requested",
        "learningEligible": False,
    }
    payload = json.dumps(values, sort_keys=True, ensure_ascii=False, allow_nan=False)
    with cb_db.transaction(root) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS director_outcomes ("
                     "request_id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL)")
        existing = conn.execute("SELECT payload, created_at FROM director_outcomes WHERE request_id=?",
                                (request_id,)).fetchone()
        if existing:
            if existing["payload"] != payload:
                raise cb_db.StateConflict("review request ID already has different evidence")
            created = existing["created_at"]
        else:
            created = cb_db.utc_now()
            conn.execute("INSERT INTO director_outcomes VALUES (?, ?, ?)",
                         (request_id, payload, created))
    return values | {"createdAt": created}


def history(root, *, show_id, episode, scene, shot_id=None, limit=10):
    """Bounded, project-scoped review summaries; never return stored session snapshots."""
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("history limit must be an integer from 1 to 100")
    filters = ["json_extract(payload, '$.showId')=?",
               "json_extract(payload, '$.episode')=?",
               "json_extract(payload, '$.scene')=?"]
    values = [show_id, episode, scene]
    if shot_id is not None:
        filters.append("json_extract(payload, '$.shotId')=?")
        values.append(shot_id)
    with cb_db.transaction(root) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='director_outcomes'").fetchone():
            return []
        rows = conn.execute(
            "SELECT payload, created_at FROM director_outcomes WHERE " +
            " AND ".join(filters) + " ORDER BY created_at DESC, request_id DESC LIMIT ?",
            (*values, limit)).fetchall()
    allowed = {"requestId", "action", "score", "reason", "reviewer", "shotId",
               "requestedCandidate", "status", "learningEligible", "sessionHash"}
    return [{key: value for key, value in json.loads(row["payload"]).items() if key in allowed}
            | {"createdAt": row["created_at"]} for row in rows]
