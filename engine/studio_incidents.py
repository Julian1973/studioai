"""Evidence records for workflow defects; recording an incident never changes production."""
import json
import time
import uuid
from studio_workspace import Workspace, StudioError


class Incidents:
    def __init__(self, workspace):
        self.ws = workspace
        with self.ws.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS workflow_incidents (id TEXT PRIMARY KEY, revision INTEGER, data TEXT)')

    def list(self, project_id):
        self.ws.project(project_id)
        with self.ws.db() as db:
            rows = db.execute('SELECT data FROM workflow_incidents ORDER BY rowid DESC').fetchall()
        return {'incidents': [x for row in rows if (x := json.loads(row[0]))['projectId'] == project_id]}

    def save(self, payload):
        from studio_agent_gateway import scrub
        pid = payload.get('projectId')
        self.ws.project(pid)
        incident_id = payload.get('id') or uuid.uuid4().hex
        with self.ws.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT revision,data FROM workflow_incidents WHERE id=?', (incident_id,)).fetchone()
            old = json.loads(row[1]) if row else {}
            if row and (old['projectId'] != pid or row[0] != payload.get('expectedRevision')):
                raise StudioError('Incident changed or belongs to another project.', 'stale')
            record = {**old, **{k: scrub(payload[k]) for k in (
                'projectId', 'episode', 'shotId', 'summary', 'observed', 'expected',
                'requestVersion', 'jobId', 'rootCause', 'affectedComponent', 'fixReference',
                'regressionEvidence', 'workflowEvidence', 'reviewer', 'status') if k in payload}}
            status = record.get('status', 'observed')
            if status not in {'observed', 'reproduced', 'fixed', 'verified'}:
                raise StudioError('Use observed, reproduced, fixed or verified.')
            if not all(record.get(k) for k in ('summary', 'observed', 'expected')):
                raise StudioError('Record the symptom, expected behaviour and observed evidence.')
            if status in {'fixed', 'verified'} and not all(record.get(k) for k in ('rootCause', 'affectedComponent', 'fixReference')):
                raise StudioError('A workaround cannot close an incident: name the root cause, shared component and fix.')
            if status == 'verified' and not all(record.get(k) for k in ('regressionEvidence', 'workflowEvidence', 'reviewer')):
                raise StudioError('Verification needs regression results, workflow evidence and a named reviewer.')
            record.update(id=incident_id, revision=(row[0] + 1 if row else 1), status=status,
                          updatedAt=time.time(), evidenceStatus='recorded-not-independently-certified')
            db.execute('INSERT OR REPLACE INTO workflow_incidents VALUES(?,?,?)',
                       (incident_id, record['revision'], json.dumps(record)))
        return {'incident': record}
