"""Episode artwork comes only from Scene 1 Shot 1's recorded keyframe."""
import json
import hashlib
from studio_workspace import token


def first_shot(shots):
    for sid in ('S1.SH1', 'S1.SH1A'):
        item=next((s for s in shots if (s.get('id') or s.get('shotId'))==sid),None)
        if item:return item
    return None


def covers(workspace, pid, legacy_media):
    project=workspace.project(pid)
    episode_file=(workspace.root/project.get('episodesFile',f'projects/{pid}/episodes.json')).resolve()
    if not episode_file.is_relative_to(workspace.root) or not episode_file.is_file():return {'covers':{}}
    result={}
    for ep in json.loads(episode_file.read_text()):
        number=token(ep['number']);image=None;sid=None
        if project.get('setupVersion')==1:
            from studio_review import verified_file
            with workspace.db() as db:
                row=db.execute('SELECT data FROM production WHERE project=? AND episode=?',(pid,number)).fetchone()
            shot=first_shot(json.loads(row[0]).get('shots',[])) if row else None
            if shot:
                sid=shot['id'];see=shot.get('outcomes',{}).get('see',{});file=(see.get('files') or [None])[0]
                if see.get('status') in {'approved','candidate'} and verified_file(workspace,pid,file):image='/'+file['path']
        else:
            base=project.get('packageBase') or ('cb-output' if project.get('primary') else None)
            path=(workspace.root/base/f'Ep{number}_scene1_production_package.json').resolve() if base else None
            if path and path.is_relative_to(workspace.root) and path.is_file():
                package=json.loads(path.read_text());shot=first_shot(package.get('shots',[]))
                if shot:
                    sid=shot['shotId'];media=legacy_media(package,'1',f'Ep{number}').get('shots',{}).get(sid,{})
                    image=media.get('keyframeApproved') or media.get('keyframeCandidate') or media.get('keyframe')
                    if not image:
                        # A relocated legacy reference is usable only when its saved hash matches.
                        ledger=next((l for l in package.get('continuityLedger',[]) if l.get('shotId')==sid),{})
                        for name in ('keyframeApproval','keyframeCandidate'):
                            record=ledger.get(name) or {};stored=str(record.get('path',''))
                            if '/engine/media/' in stored and record.get('contentHash'):
                                local=(workspace.root/'engine/media'/stored.split('/engine/media/',1)[1]).resolve()
                                if local.is_relative_to(workspace.root/'engine/media') and local.is_file() and hashlib.sha256(local.read_bytes()).hexdigest()==record['contentHash']:
                                    image='/'+local.relative_to(workspace.root).as_posix();break
                    if not image and project.get("primary") and pid == "crystal-bears":
                        # Thumbnail-only fallback to this exact shot's registered keyframe.
                        # This does not restore or grant any production approval.
                        import cb_asset_registry
                        registered=cb_asset_registry.shot_media_from_registry(package,'1',f'Ep{number}',False).get(sid,{})
                        url=registered.get('keyframeApproved') or registered.get('keyframeCandidate') or registered.get('keyframe')
                        local=(workspace.root/str(url or '').lstrip('/')).resolve()
                        if url and local.is_relative_to(workspace.root/'engine/media') and local.is_file():image=url

        result[number]={'url':image,'shotId':sid,'meaning':'Scene 1 Shot 1 keyframe' if image else 'Scene 1 Shot 1 keyframe not available'}
    return {'covers':result}
