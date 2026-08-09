"""Transactional coordination for mutable production state.

JSON production packages remain reviewable artifacts. SQLite owns the concurrency facts
that JSON cannot safely represent across the Studio's parallel worker processes: scene
leases, spend-token claims, per-candidate claims, and document revisions.
"""
from __future__ import annotations

import contextlib
import datetime
import hashlib
import json
import os
import pathlib
import sqlite3
import tempfile
import threading
import time
import uuid


SCHEMA_VERSION = 6
DEFAULT_LEASE_SECONDS = 90.0
DEFAULT_HEARTBEAT_SECONDS = 15.0


class StateConflict(RuntimeError):
    """A stale process tried to replace a document changed since it was read."""


class SceneBusy(RuntimeError):
    """Another process currently owns the scene's mutation lease."""


class SpendConflict(RuntimeError):
    """A spend authorization or candidate claim is absent, stale, or already used."""


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def state_db_path(root):
    override = os.environ.get("CB_STUDIO_STATE_DB")
    if override:
        return pathlib.Path(override).expanduser().resolve()
    return pathlib.Path(root).resolve() / "cb-output" / "state" / "studio.sqlite3"


def _connect(root):
    path = state_db_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    schema_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if schema_version == SCHEMA_VERSION:
        conn.execute("PRAGMA synchronous = FULL")
        return conn
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = FULL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scene_leases (
            episode TEXT NOT NULL,
            scene TEXT NOT NULL,
            owner TEXT NOT NULL,
            operation TEXT NOT NULL,
            acquired_at REAL NOT NULL,
            heartbeat_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            PRIMARY KEY (episode, scene)
        );

        CREATE TABLE IF NOT EXISTS json_documents (
            path TEXT PRIMARY KEY,
            revision INTEGER NOT NULL,
            digest TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS spend_authorizations (
            token TEXT PRIMARY KEY,
            episode TEXT NOT NULL,
            scene TEXT NOT NULL,
            shot_id TEXT NOT NULL,
            binding_hash TEXT NOT NULL,
            envelope_hash TEXT NOT NULL,
            envelope_json TEXT NOT NULL,
            disclosure_json TEXT NOT NULL,
            candidate_count INTEGER NOT NULL CHECK (candidate_count > 0),
            status TEXT NOT NULL CHECK (
                status IN ('issued', 'claimed', 'completed', 'voided')
            ),
            batch_id TEXT,
            issued_at TEXT NOT NULL,
            claimed_at TEXT,
            completed_at TEXT,
            voided_at TEXT,
            void_reason TEXT
        );

        CREATE INDEX IF NOT EXISTS spend_authorizations_scene
        ON spend_authorizations (episode, scene, shot_id, status);

        CREATE TABLE IF NOT EXISTS spend_candidate_claims (
            token TEXT NOT NULL REFERENCES spend_authorizations(token),
            candidate_index INTEGER NOT NULL CHECK (candidate_index > 0),
            status TEXT NOT NULL CHECK (status IN ('started', 'failed', 'completed')),
            attempts INTEGER NOT NULL DEFAULT 1,
            owner TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            output_path TEXT,
            output_hash TEXT,
            error TEXT,
            PRIMARY KEY (token, candidate_index)
        );

        CREATE TABLE IF NOT EXISTS spend_segment_claims (
            token TEXT NOT NULL REFERENCES spend_authorizations(token),
            candidate_index INTEGER NOT NULL CHECK (candidate_index > 0),
            segment_index INTEGER NOT NULL CHECK (segment_index > 0),
            segment_count INTEGER NOT NULL CHECK (segment_count > 1),
            status TEXT NOT NULL CHECK (status IN ('started', 'failed', 'completed')),
            attempts INTEGER NOT NULL DEFAULT 1,
            owner TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            output_path TEXT,
            output_hash TEXT,
            error TEXT,
            PRIMARY KEY (token, candidate_index, segment_index)
        );

        CREATE TABLE IF NOT EXISTS studio_jobs (
            job_id TEXT PRIMARY KEY,
            server_key TEXT NOT NULL,
            operation_key TEXT NOT NULL,
            gate TEXT NOT NULL,
            scene TEXT NOT NULL,
            args_json TEXT NOT NULL,
            status TEXT NOT NULL CHECK (
                status IN ('running', 'done', 'failed', 'stopped', 'interrupted')
            ),
            step TEXT NOT NULL,
            log TEXT NOT NULL,
            started REAL NOT NULL,
            ended REAL,
            pid INTEGER,
            stopped INTEGER NOT NULL DEFAULT 0 CHECK (stopped IN (0, 1)),
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS studio_jobs_started
        ON studio_jobs (started DESC);

        CREATE INDEX IF NOT EXISTS studio_jobs_operation
        ON studio_jobs (operation_key, status);

        CREATE TABLE IF NOT EXISTS render_ratings (
            rating_id TEXT PRIMARY KEY,
            episode TEXT NOT NULL,
            scene TEXT NOT NULL,
            shot_id TEXT NOT NULL,
            artifact_type TEXT NOT NULL CHECK (artifact_type IN ('keyframe', 'animation')),
            candidate_id TEXT NOT NULL,
            asset_path TEXT NOT NULL,
            asset_hash TEXT NOT NULL,
            prompt_hash TEXT NOT NULL,
            prompt_text TEXT NOT NULL,
            prompt_source TEXT NOT NULL,
            provider TEXT,
            provider_model_id TEXT,
            model_version TEXT,
            overall_read TEXT NOT NULL CHECK (overall_read IN ('miss', 'partial', 'lands')),
            scores_json TEXT NOT NULL,
            note TEXT NOT NULL,
            reviewer TEXT NOT NULL,
            prompt_analysis_json TEXT NOT NULL,
            learning_eligible INTEGER NOT NULL DEFAULT 1 CHECK (learning_eligible IN (0, 1)),
            provenance_grade TEXT NOT NULL DEFAULT 'exact',
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS render_ratings_shot
        ON render_ratings (episode, scene, shot_id, artifact_type, created_at DESC);

        CREATE INDEX IF NOT EXISTS render_ratings_prompt
        ON render_ratings (prompt_hash, artifact_type, created_at DESC);
        """
    )
    studio_job_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(studio_jobs)").fetchall()
    }
    if "server_key" not in studio_job_columns:
        conn.execute(
            "ALTER TABLE studio_jobs ADD COLUMN server_key TEXT NOT NULL DEFAULT 'legacy'"
        )
    rating_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(render_ratings)").fetchall()
    }
    if "learning_eligible" not in rating_columns:
        # Every pre-v5 row passed the old strict exact-prompt/exact-hash gate.
        conn.execute(
            "ALTER TABLE render_ratings ADD COLUMN learning_eligible "
            "INTEGER NOT NULL DEFAULT 1 CHECK (learning_eligible IN (0, 1))"
        )
    if "provenance_grade" not in rating_columns:
        conn.execute(
            "ALTER TABLE render_ratings ADD COLUMN provenance_grade "
            "TEXT NOT NULL DEFAULT 'exact'"
        )
    conn.execute(
        "INSERT INTO schema_meta(key, value) VALUES('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(SCHEMA_VERSION),),
    )
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    return conn


@contextlib.contextmanager
def transaction(root):
    conn = _connect(root)
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def _file_digest(path):
    path = pathlib.Path(path)
    return _sha256_bytes(path.read_bytes()) if path.exists() else None


def read_json_document(root, path):
    """Read JSON and register the exact disk revision returned to the caller."""
    path = pathlib.Path(path).resolve()
    with transaction(root) as conn:
        raw = path.read_bytes()
        digest = _sha256_bytes(raw)
        row = conn.execute(
            "SELECT revision, digest FROM json_documents WHERE path=?", (str(path),)
        ).fetchone()
        revision = int(row["revision"]) if row else 0
        if row and row["digest"] != digest:
            revision += 1
        conn.execute(
            """
            INSERT INTO json_documents(path, revision, digest, updated_at)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                revision=excluded.revision,
                digest=excluded.digest,
                updated_at=excluded.updated_at
            """,
            (str(path), revision, digest, utc_now()),
        )
    return json.loads(raw), digest


def atomic_write_bytes(root, path, raw, expected_digest=None):
    """Atomically replace an artifact if its on-disk revision is still expected."""
    path = pathlib.Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = bytes(raw)
    new_digest = _sha256_bytes(raw)
    with transaction(root) as conn:
        current_digest = _file_digest(path)
        if expected_digest is not None and current_digest != expected_digest:
            raise StateConflict(
                f"CONCURRENT STATE CHANGE - {path.name} changed after this operation read it"
            )

        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
            try:
                dir_fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError:
                pass
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

        row = conn.execute(
            "SELECT revision FROM json_documents WHERE path=?", (str(path),)
        ).fetchone()
        revision = (int(row["revision"]) + 1) if row else 1
        conn.execute(
            """
            INSERT INTO json_documents(path, revision, digest, updated_at)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                revision=excluded.revision,
                digest=excluded.digest,
                updated_at=excluded.updated_at
            """,
            (str(path), revision, new_digest, utc_now()),
        )
    return new_digest


def atomic_write_json(root, path, value, expected_digest=None):
    """Serialize JSON and replace it through the document compare-and-swap boundary."""
    raw = json.dumps(value, indent=1, ensure_ascii=False).encode()
    return atomic_write_bytes(root, path, raw, expected_digest)


def atomic_remove(root, path, expected_digest=None):
    """Remove an artifact only if it is still the exact revision the caller read."""
    path = pathlib.Path(path).resolve()
    with transaction(root) as conn:
        current_digest = _file_digest(path)
        if current_digest is None:
            return False
        if expected_digest is not None and current_digest != expected_digest:
            raise StateConflict(
                f"CONCURRENT STATE CHANGE - {path.name} changed before removal"
            )
        path.unlink()
        try:
            dir_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
        conn.execute("DELETE FROM json_documents WHERE path=?", (str(path),))
    return True


_JOB_STATUSES = {"running", "done", "failed", "stopped", "interrupted"}


def job_operation_key(gate, scene, args):
    """Return the stable identity used to collapse duplicate live job starts."""
    payload = {
        "gate": str(gate or ""),
        "scene": str(scene or ""),
        "args": list(args or []),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def persist_job(root, job):
    """Upsert one Studio job so progress and outcomes survive a server restart."""
    status = str(job.get("status") or "failed")
    if status not in _JOB_STATUSES:
        raise ValueError(f"invalid Studio job status: {status}")
    job_id = str(job["jobId"])
    args = list(job.get("args") or [])
    operation_key = str(
        job.get("operationKey")
        or job_operation_key(job.get("gate"), job.get("scene"), args)
    )
    with transaction(root) as conn:
        conn.execute(
            """
            INSERT INTO studio_jobs(
                job_id, server_key, operation_key, gate, scene, args_json, status, step, log,
                started, ended, pid, stopped, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                server_key=excluded.server_key,
                operation_key=excluded.operation_key,
                gate=excluded.gate,
                scene=excluded.scene,
                args_json=excluded.args_json,
                status=excluded.status,
                step=excluded.step,
                log=excluded.log,
                started=excluded.started,
                ended=excluded.ended,
                pid=excluded.pid,
                stopped=excluded.stopped,
                updated_at=excluded.updated_at
            """,
            (
                job_id, str(job.get("serverKey") or "legacy"), operation_key,
                str(job.get("gate") or ""),
                str(job.get("scene") or ""), json.dumps(args, ensure_ascii=False),
                status, str(job.get("step") or status), str(job.get("log") or ""),
                float(job.get("started") or time.time()),
                float(job["ended"]) if job.get("ended") is not None else None,
                int(job["pid"]) if job.get("pid") is not None else None,
                1 if job.get("stopped") else 0, utc_now(),
            ),
        )
    return job_id


def load_jobs(root, limit=500, server_key=None):
    """Return recent Studio jobs in the same JSON shape consumed by the UI."""
    conn = _connect(root)
    try:
        if server_key is None:
            rows = conn.execute(
                "SELECT * FROM studio_jobs ORDER BY started DESC LIMIT ?", (int(limit),)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM studio_jobs WHERE server_key=? "
                "ORDER BY started DESC LIMIT ?",
                (str(server_key), int(limit)),
            ).fetchall()
    finally:
        conn.close()
    jobs = {}
    for row in rows:
        try:
            args = json.loads(row["args_json"])
        except (TypeError, ValueError):
            args = []
        jobs[row["job_id"]] = {
            "jobId": row["job_id"],
            "serverKey": row["server_key"],
            "operationKey": row["operation_key"],
            "gate": row["gate"],
            "scene": row["scene"],
            "args": args,
            "status": row["status"],
            "step": row["step"],
            "log": row["log"],
            "started": row["started"],
            "ended": row["ended"],
            "pid": row["pid"],
            "stopped": bool(row["stopped"]),
        }
    return jobs


def interrupt_running_jobs(root, message="Studio restarted before this run completed.",
                           server_key=None):
    """Close orphaned in-memory runs honestly when a new server process starts."""
    now = time.time()
    with transaction(root) as conn:
        sql = """
            UPDATE studio_jobs SET
                status='interrupted', step=?, ended=?,
                log=CASE WHEN log='' THEN ? ELSE log || char(10) || ? END,
                updated_at=?
            WHERE status='running'
        """
        params = [str(message), now, str(message), str(message), utc_now()]
        if server_key is not None:
            sql += " AND server_key=?"
            params.append(str(server_key))
        cursor = conn.execute(sql, params)
        return cursor.rowcount


_LEASE_LOCAL = threading.local()


def _held_leases():
    held = getattr(_LEASE_LOCAL, "held", None)
    if held is None:
        held = {}
        _LEASE_LOCAL.held = held
    return held


def _acquire_lease(root, episode, scene, owner, operation, lease_seconds):
    now = time.time()
    with transaction(root) as conn:
        row = conn.execute(
            "SELECT * FROM scene_leases WHERE episode=? AND scene=?",
            (episode, scene),
        ).fetchone()
        if row and float(row["expires_at"]) > now:
            remaining = max(0.0, float(row["expires_at"]) - now)
            raise SceneBusy(
                f"SCENE BUSY - {episode} scene {scene} is running {row['operation']} "
                f"({remaining:.0f}s lease remaining)"
            )
        if row:
            conn.execute(
                "DELETE FROM scene_leases WHERE episode=? AND scene=?",
                (episode, scene),
            )
        conn.execute(
            """
            INSERT INTO scene_leases(
                episode, scene, owner, operation, acquired_at, heartbeat_at, expires_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (episode, scene, owner, operation, now, now, now + lease_seconds),
        )


def _heartbeat(root, episode, scene, owner, lease_seconds, stop, interval):
    while not stop.wait(interval):
        now = time.time()
        try:
            with transaction(root) as conn:
                conn.execute(
                    """
                    UPDATE scene_leases SET heartbeat_at=?, expires_at=?
                    WHERE episode=? AND scene=? AND owner=?
                    """,
                    (now, now + lease_seconds, episode, scene, owner),
                )
        except sqlite3.Error:
            continue


@contextlib.contextmanager
def scene_lease(root, episode, scene, operation, lease_seconds=DEFAULT_LEASE_SECONDS,
                heartbeat_seconds=DEFAULT_HEARTBEAT_SECONDS):
    """Acquire a renewable, process-safe scene mutation lease.

    The lease is re-entrant within one thread so a scene-level action may call shot-level
    helpers without deadlocking itself. A killed process stops heartbeating and can be
    recovered after expiry.
    """
    root = pathlib.Path(root).resolve()
    episode, scene = str(episode), str(scene)
    key = (str(state_db_path(root)), episode, scene)
    held = _held_leases()
    if key in held:
        held[key]["depth"] += 1
        try:
            yield held[key]["owner"]
        finally:
            held[key]["depth"] -= 1
        return

    owner = f"{os.getpid()}:{threading.get_ident()}:{uuid.uuid4().hex}"
    _acquire_lease(root, episode, scene, owner, operation, lease_seconds)
    stop = threading.Event()
    interval = max(0.05, min(float(heartbeat_seconds), float(lease_seconds) / 3.0))
    thread = threading.Thread(
        target=_heartbeat,
        args=(root, episode, scene, owner, lease_seconds, stop, interval),
        daemon=True,
    )
    held[key] = {"owner": owner, "depth": 1}
    thread.start()
    try:
        yield owner
    finally:
        stop.set()
        thread.join(timeout=max(0.2, interval + 0.2))
        try:
            with transaction(root) as conn:
                conn.execute(
                    "DELETE FROM scene_leases WHERE episode=? AND scene=? AND owner=?",
                    (episode, scene, owner),
                )
        finally:
            held.pop(key, None)


def issue_spend_authorization(root, episode, scene, shot_id, auth):
    token = str(auth["token"])
    envelope = auth["envelope"]
    candidate_count = int(envelope["candidateCount"])
    with transaction(root) as conn:
        conn.execute(
            """
            UPDATE spend_authorizations
            SET status='voided', voided_at=?, void_reason='superseded-disclosure'
            WHERE episode=? AND scene=? AND shot_id=? AND status='issued'
            """,
            (utc_now(), str(episode), str(scene), str(shot_id)),
        )
        try:
            conn.execute(
                """
                INSERT INTO spend_authorizations(
                    token, episode, scene, shot_id, binding_hash, envelope_hash,
                    envelope_json, disclosure_json, candidate_count, status, issued_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 'issued', ?)
                """,
                (
                    token, str(episode), str(scene), str(shot_id), auth["bindingHash"],
                    auth["envelopeHash"], json.dumps(envelope, sort_keys=True),
                    json.dumps(auth["disclosure"], sort_keys=True), candidate_count,
                    auth.get("issuedAt") or utc_now(),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise SpendConflict("SPEND TOKEN COLLISION - request a fresh disclosure") from exc
    return token


def claim_spend_authorization(root, token, episode, scene, shot_id, binding_hash,
                              envelope_hash, batch_id):
    with transaction(root) as conn:
        row = conn.execute(
            "SELECT * FROM spend_authorizations WHERE token=?", (str(token),)
        ).fetchone()
        if not row:
            raise SpendConflict("unknown, legacy, or already-used spend token")
        expected = (
            str(episode), str(scene), str(shot_id), str(binding_hash), str(envelope_hash)
        )
        actual = (
            row["episode"], row["scene"], row["shot_id"], row["binding_hash"],
            row["envelope_hash"],
        )
        if actual != expected:
            raise SpendConflict("the spend token is STALE against the current sealed envelope")
        if row["status"] == "completed":
            raise SpendConflict("unknown or already-used spend token")
        if row["status"] == "voided":
            raise SpendConflict("the spend token is VOID; request a new disclosure")
        if row["status"] == "claimed" and row["batch_id"] != str(batch_id):
            raise SpendConflict("the spend token is already claimed by another batch")
        if row["status"] == "issued":
            conn.execute(
                """
                UPDATE spend_authorizations
                SET status='claimed', batch_id=?, claimed_at=?
                WHERE token=? AND status='issued'
                """,
                (str(batch_id), utc_now(), str(token)),
            )
    return str(batch_id)


def claim_candidate(root, token, candidate_index, owner):
    candidate_index = int(candidate_index)
    with transaction(root) as conn:
        auth = conn.execute(
            "SELECT status, candidate_count FROM spend_authorizations WHERE token=?",
            (str(token),),
        ).fetchone()
        if not auth or auth["status"] != "claimed":
            raise SpendConflict("candidate generation has no active claimed spend authorization")
        if not (1 <= candidate_index <= int(auth["candidate_count"])):
            raise SpendConflict("candidate index is outside the authorized spend envelope")
        row = conn.execute(
            """
            SELECT * FROM spend_candidate_claims
            WHERE token=? AND candidate_index=?
            """,
            (str(token), candidate_index),
        ).fetchone()
        if row and row["status"] == "completed":
            return {"action": "completed", **dict(row)}
        if row and row["status"] == "started":
            raise SpendConflict(
                f"candidate {candidate_index} has an unresolved provider attempt; "
                "automatic repayment is blocked"
            )
        now = utc_now()
        if row:
            conn.execute(
                """
                UPDATE spend_candidate_claims
                SET status='started', attempts=attempts+1, owner=?, started_at=?,
                    finished_at=NULL, output_path=NULL, output_hash=NULL, error=NULL
                WHERE token=? AND candidate_index=? AND status='failed'
                """,
                (str(owner), now, str(token), candidate_index),
            )
        else:
            conn.execute(
                """
                INSERT INTO spend_candidate_claims(
                    token, candidate_index, status, attempts, owner, started_at
                ) VALUES(?, ?, 'started', 1, ?, ?)
                """,
                (str(token), candidate_index, str(owner), now),
            )
    return {"action": "generate", "candidate_index": candidate_index}


def fail_candidate(root, token, candidate_index, error):
    with transaction(root) as conn:
        changed = conn.execute(
            """
            UPDATE spend_candidate_claims
            SET status='failed', finished_at=?, error=?
            WHERE token=? AND candidate_index=? AND status='started'
            """,
            (utc_now(), str(error)[:1000], str(token), int(candidate_index)),
        ).rowcount
        if changed != 1:
            raise SpendConflict("candidate failure did not match an active provider claim")


def claim_candidate_segment(root, token, candidate_index, segment_index,
                            segment_count, owner):
    """Claim one paid internal call belonging to one Studio review candidate."""
    candidate_index = int(candidate_index)
    segment_index = int(segment_index)
    segment_count = int(segment_count)
    if segment_count <= 1 or not (1 <= segment_index <= segment_count):
        raise SpendConflict("provider segment index is outside its sealed transport plan")
    with transaction(root) as conn:
        candidate = conn.execute(
            """
            SELECT c.status AS candidate_status, a.status AS authorization_status
            FROM spend_candidate_claims c
            JOIN spend_authorizations a ON a.token=c.token
            WHERE c.token=? AND c.candidate_index=?
            """,
            (str(token), candidate_index),
        ).fetchone()
        if not candidate or candidate["authorization_status"] != "claimed" or \
                candidate["candidate_status"] != "started":
            raise SpendConflict("provider segment has no active candidate claim")
        row = conn.execute(
            """
            SELECT * FROM spend_segment_claims
            WHERE token=? AND candidate_index=? AND segment_index=?
            """,
            (str(token), candidate_index, segment_index),
        ).fetchone()
        if row and int(row["segment_count"]) != segment_count:
            raise SpendConflict("provider segment count changed after authorization")
        if row and row["status"] == "completed":
            return {"action": "completed", **dict(row)}
        if row and row["status"] == "started":
            raise SpendConflict(
                f"candidate {candidate_index} segment {segment_index} has an unresolved "
                "provider attempt; automatic repayment is blocked"
            )
        now = utc_now()
        if row:
            conn.execute(
                """
                UPDATE spend_segment_claims
                SET status='started', attempts=attempts+1, owner=?, started_at=?,
                    finished_at=NULL, output_path=NULL, output_hash=NULL, error=NULL
                WHERE token=? AND candidate_index=? AND segment_index=? AND status='failed'
                """,
                (str(owner), now, str(token), candidate_index, segment_index),
            )
        else:
            conn.execute(
                """
                INSERT INTO spend_segment_claims(
                    token, candidate_index, segment_index, segment_count, status,
                    attempts, owner, started_at
                ) VALUES(?, ?, ?, ?, 'started', 1, ?, ?)
                """,
                (str(token), candidate_index, segment_index, segment_count,
                 str(owner), now),
            )
    return {"action": "generate", "candidate_index": candidate_index,
            "segment_index": segment_index}


def fail_candidate_segment(root, token, candidate_index, segment_index, error):
    with transaction(root) as conn:
        changed = conn.execute(
            """
            UPDATE spend_segment_claims
            SET status='failed', finished_at=?, error=?
            WHERE token=? AND candidate_index=? AND segment_index=? AND status='started'
            """,
            (utc_now(), str(error)[:1000], str(token), int(candidate_index),
             int(segment_index)),
        ).rowcount
        if changed != 1:
            raise SpendConflict("provider segment failure did not match an active claim")


def complete_candidate_segment(root, token, candidate_index, segment_index, output_path):
    output_path = pathlib.Path(output_path).resolve()
    output_hash = _file_digest(output_path)
    if not output_hash:
        raise SpendConflict("provider segment completed without an output artifact")
    with transaction(root) as conn:
        changed = conn.execute(
            """
            UPDATE spend_segment_claims
            SET status='completed', finished_at=?, output_path=?, output_hash=?, error=NULL
            WHERE token=? AND candidate_index=? AND segment_index=? AND status='started'
            """,
            (utc_now(), str(output_path), output_hash, str(token), int(candidate_index),
             int(segment_index)),
        ).rowcount
        if changed != 1:
            raise SpendConflict("provider segment completion did not match an active claim")
    return output_hash


def complete_candidate(root, token, candidate_index, output_path):
    output_path = pathlib.Path(output_path).resolve()
    output_hash = _file_digest(output_path)
    if not output_hash:
        raise SpendConflict("provider candidate completed without an output artifact")
    with transaction(root) as conn:
        segments = conn.execute(
            """
            SELECT status, segment_index, segment_count FROM spend_segment_claims
            WHERE token=? AND candidate_index=? ORDER BY segment_index
            """,
            (str(token), int(candidate_index)),
        ).fetchall()
        if segments:
            expected = int(segments[0]["segment_count"])
            if (len(segments) != expected or
                    [int(row["segment_index"]) for row in segments] !=
                    list(range(1, expected + 1)) or
                    any(row["status"] != "completed" for row in segments)):
                raise SpendConflict(
                    "provider candidate cannot complete until every sealed segment completes"
                )
        changed = conn.execute(
            """
            UPDATE spend_candidate_claims
            SET status='completed', finished_at=?, output_path=?, output_hash=?, error=NULL
            WHERE token=? AND candidate_index=? AND status='started'
            """,
            (utc_now(), str(output_path), output_hash, str(token), int(candidate_index)),
        ).rowcount
        if changed != 1:
            raise SpendConflict("candidate completion did not match an active provider claim")
    return output_hash


def complete_spend_authorization(root, token):
    with transaction(root) as conn:
        auth = conn.execute(
            "SELECT status, candidate_count FROM spend_authorizations WHERE token=?",
            (str(token),),
        ).fetchone()
        if not auth or auth["status"] != "claimed":
            raise SpendConflict("spend authorization is not an active claimed batch")
        completed = conn.execute(
            """
            SELECT COUNT(*) AS n FROM spend_candidate_claims
            WHERE token=? AND status='completed'
            """,
            (str(token),),
        ).fetchone()["n"]
        if int(completed) != int(auth["candidate_count"]):
            raise SpendConflict(
                f"cannot consume spend token: {completed}/{auth['candidate_count']} "
                "candidates are transactionally complete"
            )
        conn.execute(
            """
            UPDATE spend_authorizations SET status='completed', completed_at=?
            WHERE token=? AND status='claimed'
            """,
            (utc_now(), str(token)),
        )


def void_scene_authorizations(root, episode, scene, reason):
    with transaction(root) as conn:
        return conn.execute(
            """
            UPDATE spend_authorizations
            SET status='voided', voided_at=?, void_reason=?
            WHERE episode=? AND scene=? AND status IN ('issued', 'claimed')
            """,
            (utc_now(), str(reason), str(episode), str(scene)),
        ).rowcount


def void_shot_authorizations(root, episode, scene, shot_id, reason):
    """Void unspent envelopes for one shot without disturbing parallel scene work."""
    with transaction(root) as conn:
        return conn.execute(
            """
            UPDATE spend_authorizations
            SET status='voided', voided_at=?, void_reason=?
            WHERE episode=? AND scene=? AND shot_id=? AND status='issued'
            """,
            (utc_now(), str(reason), str(episode), str(scene), str(shot_id)),
        ).rowcount


def spend_authorization(root, token):
    conn = _connect(root)
    try:
        row = conn.execute(
            "SELECT * FROM spend_authorizations WHERE token=?", (str(token),)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


_RENDER_RATING_FIELDS = (
    "ratingId", "episode", "scene", "shotId", "artifactType", "candidateId",
    "assetPath", "assetHash", "promptHash", "promptText", "promptSource",
    "provider", "providerModelId", "modelVersion", "overallRead", "scores",
    "note", "reviewer", "promptAnalysis", "learningEligible", "provenanceGrade",
    "createdAt",
)


def save_render_rating(root, record):
    """Append one immutable prompt/render outcome record."""
    missing = [name for name in _RENDER_RATING_FIELDS
               if name not in record or record[name] is None]
    optional = {"provider", "providerModelId", "modelVersion"}
    missing = [name for name in missing if name not in optional]
    if missing:
        raise ValueError("render rating is missing: " + ", ".join(missing))
    if not isinstance(record["learningEligible"], bool):
        raise ValueError("learningEligible must be a boolean")
    if record["provenanceGrade"] not in {"exact", "prompt-only", "asset-only"}:
        raise ValueError("provenanceGrade must be exact, prompt-only or asset-only")
    with transaction(root) as conn:
        try:
            conn.execute(
                """
                INSERT INTO render_ratings(
                    rating_id, episode, scene, shot_id, artifact_type, candidate_id,
                    asset_path, asset_hash, prompt_hash, prompt_text, prompt_source,
                    provider, provider_model_id, model_version, overall_read, scores_json,
                    note, reviewer, prompt_analysis_json, learning_eligible,
                    provenance_grade, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record["ratingId"]), str(record["episode"]), str(record["scene"]),
                    str(record["shotId"]), str(record["artifactType"]),
                    str(record["candidateId"]), str(record["assetPath"]),
                    str(record["assetHash"]), str(record["promptHash"]),
                    str(record["promptText"]), str(record["promptSource"]),
                    (str(record["provider"]) if record.get("provider") else None),
                    (str(record["providerModelId"]) if record.get("providerModelId") else None),
                    (str(record["modelVersion"]) if record.get("modelVersion") else None),
                    str(record["overallRead"]),
                    json.dumps(record["scores"], sort_keys=True, ensure_ascii=False),
                    str(record.get("note") or ""), str(record["reviewer"]),
                    json.dumps(record["promptAnalysis"], sort_keys=True, ensure_ascii=False),
                    1 if record["learningEligible"] else 0,
                    str(record["provenanceGrade"]),
                    str(record["createdAt"]),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise StateConflict("render rating ID already exists") from exc
    return dict(record)


def list_render_ratings(root, episode=None, scene=None, shot_id=None,
                        artifact_type=None, prompt_hash=None):
    """Read immutable render ratings, newest first, with optional exact filters."""
    filters = []
    values = []
    for column, value in (
        ("episode", episode), ("scene", scene), ("shot_id", shot_id),
        ("artifact_type", artifact_type), ("prompt_hash", prompt_hash),
    ):
        if value is not None:
            filters.append(f"{column}=?")
            values.append(str(value))
    sql = "SELECT * FROM render_ratings"
    if filters:
        sql += " WHERE " + " AND ".join(filters)
    sql += " ORDER BY created_at DESC, rating_id DESC"
    conn = _connect(root)
    try:
        rows = conn.execute(sql, values).fetchall()
    finally:
        conn.close()
    out = []
    for row in rows:
        out.append({
            "ratingId": row["rating_id"],
            "episode": row["episode"],
            "scene": row["scene"],
            "shotId": row["shot_id"],
            "artifactType": row["artifact_type"],
            "candidateId": row["candidate_id"],
            "assetPath": row["asset_path"],
            "assetHash": row["asset_hash"],
            "promptHash": row["prompt_hash"],
            "promptText": row["prompt_text"],
            "promptSource": row["prompt_source"],
            "provider": row["provider"],
            "providerModelId": row["provider_model_id"],
            "modelVersion": row["model_version"],
            "overallRead": row["overall_read"],
            "scores": json.loads(row["scores_json"]),
            "note": row["note"],
            "reviewer": row["reviewer"],
            "promptAnalysis": json.loads(row["prompt_analysis_json"]),
            "learningEligible": bool(row["learning_eligible"]),
            "provenanceGrade": row["provenance_grade"],
            "createdAt": row["created_at"],
        })
    return out
