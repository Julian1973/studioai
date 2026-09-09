"""Hash-bound episode finishing handoff, layered on the existing post workspace."""
import json
import math
import pathlib
import subprocess
import sys
import shutil
import tempfile
import fcntl
from contextlib import contextmanager
from datetime import datetime, timezone
import cb_post_workspace as post
import cb_vcube
from studio_post_contract import contracts, POST_SKILL

ROOT = pathlib.Path(__file__).resolve().parents[1]
MCP = pathlib.Path('/Users/julianjenkins/Documents/ChatGPT/Divinvi/davinci-resolve-mcp')

def now():
    return datetime.now(timezone.utc).isoformat()

def job_path(ep):
    return post.STATE_ROOT / f'{ep}_vcube_job.json'

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2)+'\n'); tmp.replace(path)

@contextmanager
def lock(ep):
    post.STATE_ROOT.mkdir(parents=True, exist_ok=True)
    with (post.STATE_ROOT / f'{ep}_finishing.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield

def status(ep):
    w = post.workspace(ep)
    w['upscale'] = cb_vcube.readiness(w.get('durationSec'))
    w['upscale']['cutApproved'] = w.get('status') == 'approved'
    path = job_path(ep)
    job = json.loads(path.read_text()) if path.exists() else None
    w['upscale']['job'] = job if job and job.get('masterSha256') == w.get('masterSha256') else None
    w['upscale']['canStart'] = bool(w.get('finishingWorkflow') and w['upscale']['configured'] and w['upscale']['cutApproved'] and not w['upscale']['job'])
    return w

def current(ep, expected):
    w = post.workspace(ep)
    if not w.get('finishingWorkflow') or not expected or w.get('masterSha256') != expected:
        raise ValueError('The review version changed. Reload and review the current cut.')
    return w

def director_brief(ep, expected):
    w = current(ep, expected)
    return {**contracts(legacy_episode=ep), 'projectId':'crystal-bears', 'ledger':'legacy-post',
        'episode':ep,'masterSha256':expected,
        'postSupervisorSkill':str(POST_SKILL),
        'instruction': 'Assess the actual rendered cut and approved Studio sources. Report timecode, first failed gate, visible/audible evidence and smallest repair. Do not approve media or submit providers. Keep uninspected items pending.',
        'candidate':w['masterUrl'],
        'sourceRecords':w.get('sourceRecords'),
        'sourceEvidence': 'Source records were captured at registration; inspect timeline correspondence.' if w.get('sourceRecords') else 'Historical source records were not registered. Reconcile exact approved footage before editing; current plans alone cannot establish lineage.',
        'knownFindings':w['finishingWorkflow'].get('findings', []),
        'dimensions':['story and reactions','cut in/out frames','identity and scale','geography and motion phase','colour and lighting','dialogue, music and sound','ending and next-shot handoff'],
        'capabilityPolicy':'Verify each operation against the installed edition and bridge before use; no tool capability is asserted by this brief.',
        'approvalOwner':'Julian'}

def resolve_binding(workspace, snapshot):
    """Names are useful orientation, never proof that an export matches a timeline."""
    workflow = workspace['finishingWorkflow']
    saved = workflow.get('resolveSnapshot') or {}
    expected = {'project': workflow.get('resolveProject'), 'timeline': workflow.get('resolveTimeline'),
                'projectId': saved.get('projectId'), 'timelineId': saved.get('timelineId')}
    mismatches = [key for key, value in expected.items() if value and snapshot.get(key) != value]
    if mismatches:
        state, message = 'mismatch', 'Resolve is showing a different project or timeline. Select the registered candidate before editing.'
    elif expected['projectId'] and expected['timelineId']:
        state, message = 'identity-match', 'Registered project and timeline IDs match. Timeline edits and exported-media correspondence still need inspection.'
    elif expected['project'] and expected['timeline']:
        state, message = 'names-only', 'Names match, but this older candidate has no stable Resolve IDs. Verify the source lineage before editing.'
    else:
        state, message = 'unbound', 'No Resolve binding was recorded for this candidate. Current timeline is orientation only.'
    return {'status': state, 'message': message, 'expected': expected, 'masterSha256': workspace['masterSha256']}


def resolve_snapshot(ep=None, expected=None):
    w = current(ep, expected) if ep is not None else None
    code = '''import json
from src.utils.resolve_bridge_client import connect
r=connect(timeout=8,require_enabled=False)
p=r.GetProjectManager().GetCurrentProject()
t=p.GetCurrentTimeline() if p else None
print(json.dumps({'product':r.GetProductName(),'version':r.GetVersionString(),'project':p.GetName() if p else None,'projectId':p.GetUniqueId() if p else None,'timeline':t.GetName() if t else None,'timelineId':t.GetUniqueId() if t else None,'frameRate':t.GetSetting('timelineFrameRate') if t else None,'tracks':{kind:t.GetTrackCount(kind) for kind in ('video','audio','subtitle')} if t else {},'startFrame':t.GetStartFrame() if t else None,'endFrame':t.GetEndFrame() if t else None,'markers':t.GetMarkers() if t else {}}))'''
    try:
        result = subprocess.run([str(MCP/'venv/bin/python'), '-c', code], cwd=MCP, capture_output=True, text=True, timeout=25)
        if result.returncode:
            raise ValueError('bridge failed')
        snapshot = json.loads(result.stdout.strip().splitlines()[-1])
    except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
        raise ValueError('Resolve bridge unavailable. Open Resolve and start its Workspace Scripts bridge.')
    if w is not None:
        current(ep, expected)  # Candidate can change while waiting on the bridge.
        snapshot['binding'] = resolve_binding(w, snapshot)
    return snapshot

def reserve(ep, expected, max_cost):
    with lock(ep):
        w = current(ep, expected)
        if w['status'] != 'approved':
            raise ValueError('Approve this exact final cut before enhancement.')
        ready = cb_vcube.readiness(w['durationSec'])
        if not ready['configured']:
            raise ValueError('vCube setup incomplete: ' + ', '.join(ready['missing']))
        cap = float(max_cost)
        if not math.isfinite(cap) or cap < ready['estimatedUsd']:
            raise ValueError('The displayed enhancement estimate needs a sufficient approved allowance.')
        path = job_path(ep)
        if path.exists():
            old = json.loads(path.read_text())
            if old.get('masterSha256') == expected:
                return old  # Never duplicate an accepted or ambiguous submission.
            if old.get('status') not in ('failed','provider-complete-awaiting-QC'):
                raise ValueError('Reconcile the previous enhancement job before starting another.')
            write(path.with_name(f'{ep}_vcube_{old["masterSha256"][:12]}.json'), old)
        job = {'episode':ep,'masterSha256':expected,'status':'reserved','createdAt':now(),
               'approvedAllowanceUsd':cap,'estimatedUsd':ready['estimatedUsd'],'provider':'BytePlus VOD / vCube'}
        write(path, job)
        return job

def run(ep, expected):
    # Dedicated subprocess tracked by Studio's existing job manager.
    with lock(ep):
        w = current(ep, expected)
        job = json.loads(job_path(ep).read_text())
        if job['masterSha256'] != expected or job['status'] != 'reserved':
            return
        if w['status'] != 'approved':
            job['status']='failed'; job['error']='Cut approval was withdrawn before upload.'; write(job_path(ep),job); return
        try:
            manifest = json.loads(post._manifest_path(ep).read_text())
            source = pathlib.Path(manifest['outputs']['master'])
            if post._sha256(source) != expected:
                raise ValueError('Review file changed before upload.')
            job['status']='uploading'; write(job_path(ep),job)
            with tempfile.TemporaryDirectory(prefix='vcube-sealed-') as folder:
                sealed = pathlib.Path(folder) / 'review.mp4'
                shutil.copyfile(source, sealed)
                if post._sha256(sealed) != expected:
                    raise ValueError('Review file changed while preparing upload.')
                job['vid']=cb_vcube.upload(sealed)
            write(job_path(ep),job)
            if current(ep, expected)['status'] != 'approved':
                job['status']='failed'; job['error']='Cut approval was withdrawn before enhancement.'
                write(job_path(ep),job); return
            body=cb_vcube.payload(job['vid'],expected)
            job['request']=body; job['status']='submitting'; write(job_path(ep),job)
            result=cb_vcube.start(body)
            if not result.get('RunId'):
                raise RuntimeError('No execution ID returned.')
            job['runId']=result['RunId']; job['status']='submitted'
        except Exception:
            # No automatic retries after an ambiguous network response.
            job['status']='needs-reconciliation'
            job['error']='Submission interrupted. Reconcile this stored request before any retry.'
        write(job_path(ep),job)

def poll(ep, expected):
    with lock(ep):
        current(ep, expected)
        job = json.loads(job_path(ep).read_text())
        if job['masterSha256'] != expected or not job.get('runId'):
            raise ValueError('No matching vCube execution ID is available yet.')
        result=cb_vcube.poll(job['runId'])
        job['providerStatus']=result.get('Status')
        job['status']={'Success':'provider-complete-awaiting-QC','Failed':'failed','Terminated':'failed'}.get(result.get('Status'),'processing')
        # Output identifiers are retained for retrieval; success is never final-media approval.
        job['output']=result.get('Output'); job['checkedAt']=now()
        write(job_path(ep),job)
    return status(ep)

if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2])
