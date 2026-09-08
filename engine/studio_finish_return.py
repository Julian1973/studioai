"""Import and human review of an editor's project-local returned movie.

Does not launch Resolve, infer repairs, replace source shots or publish delivery.
"""
import shutil
import time
import uuid
from studio_workspace import StudioError, digest
from studio_production import file_hash
from studio_workflow import clean_note


def handle(production, context, state, timeline, payload):
    pid=context['project']['id'];assembly=state.setdefault('assembly',{})
    exported=assembly.get('export') or {}
    if exported.get('fingerprint')!=timeline['fingerprint']:
        raise StudioError('Create a finishing handoff for the current assembly first.', 'stale')
    production.assert_artifact(pid, exported)
    candidates=assembly.setdefault('finishedCandidates',[])
    if payload['action']=='register_finish':
        if payload.get('handoffId')!=digest(exported):
            raise StudioError('The finishing handoff changed. Use its current version.', 'stale')
        path=production.ws.project_path(pid,payload.get('path',''))
        if not path.is_file() or path.suffix.lower() not in {'.mp4','.mov','.webm'}:
            raise StudioError('Save the returned MP4, MOV or WebM inside this project and select that file.')
        expected=str(payload.get('hash',''))
        if file_hash(path)!=expected:
            raise StudioError('The returned file differs from the supplied hash.', 'stale')
        evidence={k:clean_note(payload.get(k)) for k in ('resolveProjectId','resolveTimelineId','inspection')}
        unresolved=str(payload.get('unresolved') or '').strip()
        if unresolved:unresolved=clean_note(unresolved)
        duration=production.transport.verify_media(path,'video')
        if any(s.get('dialogue') for s in state['shots']):
            production.transport.verify_media(path,'audio')
        folder=production.ws.project_path(pid,f'projects/{pid}/media/finishing')
        folder.mkdir(parents=True,exist_ok=True)
        target=folder/(uuid.uuid4().hex+path.suffix.lower())
        shutil.copyfile(path,target)
        if file_hash(target)!=expected or file_hash(path)!=expected:
            target.unlink(missing_ok=True)
            raise StudioError('The file changed during import. No candidate was registered.', 'stale')
        candidate={'id':uuid.uuid4().hex,'status':'candidate','files':[production.file_record(pid,target)],
                   'duration':duration,'sourceDuration':timeline['duration'],'fingerprint':timeline['fingerprint'],'handoffId':digest(exported),
                   'evidence':evidence,'unresolved':unresolved,'createdAt':time.time(),
                   'meaning':'Editor-supplied inspection evidence; decoded file verified, artistic quality requires human viewing.'}
        candidates.append(candidate)
        return 'Returned edit imported for viewing. Source shots and their approvals are preserved.'
    candidate=next((c for c in candidates if c['id']==payload.get('candidateId')),None)
    if not candidate or candidate['fingerprint']!=timeline['fingerprint'] or candidate['handoffId']!=digest(exported):
        raise StudioError('Review the returned candidate for this exact handoff.', 'stale')
    production.assert_artifact(pid,candidate)
    if candidate['status']!='candidate' or payload.get('hash')!=candidate['files'][0]['hash']:
        raise StudioError('The candidate changed or was already reviewed.', 'stale')
    if payload['action']=='approve_finish' and candidate['unresolved']:
        raise StudioError('The returned edit has unresolved work. Return a corrected candidate before approval.')
    candidate.update(status='approved' if payload['action']=='approve_finish' else 'rejected',reviewedAt=time.time())
    return 'Returned edit '+candidate['status']+' against its exact file. No publication or delivery was performed.'
