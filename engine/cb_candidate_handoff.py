"""Explicit candidate-to-candidate continuity; never a human render approval."""
import hashlib
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve(package, target):
    ledger = next((x for x in package['continuityLedger'] if x['shotId'] == target['shotId']), {})
    record = ledger.get('candidateStateSource') or {}
    source_id = (target.get('shotTransition') or {}).get('stateSourceShotId')
    source = next((x for x in package['continuityLedger'] if x['shotId'] == source_id), {})
    if not record or not record.get('authorization'):
        raise ValueError('Select and authorise the exact preceding candidate for this draft sequence.')
    if (record.get('sourceShotId') != source_id or record.get('targetShotId') != target['shotId']
            or record.get('batchId') != source.get('batchId')
            or source.get('status') != 'candidates-pending'
            or record.get('sourcePath') not in (source.get('candidatePaths') or [])):
        raise ValueError('The selected continuity candidate is no longer current; select its replacement explicitly.')
    for path_key, hash_key in [('sourcePath', 'sourceHash'), ('framePath', 'frameHash')]:
        path = record.get(path_key)
        if not path or not Path(path).is_file() or sha(path) != record.get(hash_key):
            raise ValueError('The selected continuity candidate or its exact ending changed.')
    return record['framePath']


def select(render, scene, source_id, target_id, candidate, episode, authorization, log=print):
    """Used only for an explicitly requested draft sequence. Both WATCH takes stay candidates."""
    import json
    import subprocess
    import uuid
    if not str(authorization or '').strip():
        raise render.Refused('An explicit draft-sequence authorisation is required.')
    pkg, path = render.load_pkg(scene, episode)
    source, target = render._ledger(pkg, source_id), render._shot(pkg, target_id)
    if (target.get('shotTransition') or {}).get('stateSourceShotId') != source_id:
        raise render.Refused('This is not the preceding source selected by the Director Card.')
    paths = source.get('candidatePaths') or []
    if source.get('status') != 'candidates-pending' or not 1 <= int(candidate) <= len(paths):
        raise render.Refused('Choose an existing current render candidate.')
    video = Path(paths[int(candidate)-1]).resolve()
    before = sha(video)
    probe = json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames',
        '-select_streams','v:0','-show_entries','stream=nb_read_frames','-of','json',str(video)]))
    index = int(probe['streams'][0]['nb_read_frames'])-1
    frame = render.HERE / 'media' / 'shots' / f'{episode}_{source_id}_candidate_ending_{uuid.uuid4().hex[:12]}.png'
    subprocess.run(['ffmpeg','-v','error','-i',str(video),'-vf',f'select=eq(n\\,{index})',
        '-frames:v','1',str(frame)],check=True,capture_output=True)
    if sha(video) != before:
        raise render.Refused('The source candidate changed during extraction.')
    record = dict(sourceShotId=source_id, targetShotId=target_id, sourcePath=str(video),
        sourceHash=before, framePath=str(frame), frameHash=sha(frame), frameIndex=index,
        batchId=source.get('batchId'), authorization=str(authorization), selectedAt=render._now(),
        humanApproval=False, meaning='Candidate continuity for the explicitly requested draft sequence; not final media approval')
    render._ledger(pkg, target_id)['candidateStateSource'] = record
    resolve(pkg, target)
    render._save(pkg, path)
    log(f'CONTINUITY CANDIDATE — {source_id} to {target_id}; exact ending bound, no WATCH approval changed')
    return record
