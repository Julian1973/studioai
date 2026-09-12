"""Five-action adapter for the existing native production package and workers.

No second creative record: views are projections; approval and Fire stay in
cb_render and the existing server storyboard transaction.
"""
from pathlib import Path
from copy import deepcopy
import json
import hashlib
import os
from studio_journey import DecisionRequired, digest, scope_key, StudioStore


def file_record(root, value):
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        relative = path.relative_to(root.resolve())
    except ValueError:
        raise ValueError('This production asset is outside the Studio media library.')
    if not path.is_file():
        return None
    return {'path': str(path), 'url': '/' + relative.as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def read(root, scope):
    scope_key(scope)
    path = root / 'cb-output' / f"{scope['episode']}_scene{scope['scene']}_production_package.json"
    board_path = root / 'cb-output/creative' / f"{scope['episode']}_scene{scope['scene']}_storyboard.json"
    import cb_db
    pkg = cb_db.read_json_document(root, path)[0] if path.exists() else {}
    board = cb_db.read_json_document(root, board_path)[0] if board_path.exists() else {}
    shot = next((s for s in pkg.get('shots', []) if s['shotId'] == scope['unit']), {})
    led = next((s for s in pkg.get('continuityLedger', []) if s['shotId'] == scope['unit']), {})
    return pkg, board, shot, led


def authority(shot):
    # Use the existing source projector, not a second list of creative fields.
    from studio_director_handoff import source
    return source(shot)


class Native:
    def __init__(self, root, server):
        self.root, self.server = Path(root), server

    def snapshot(self, scope):
        if scope['projectId'] != 'crystal-bears':
            raise ValueError('The selected project uses its project production service.')
        pkg, board, shot, led = read(self.root, scope)
        R = self.server._canonical_cb_render()
        plate_status = R.scenelook_status(scope['scene'],scope['episode']) if shot else {}
        plate = file_record(self.root,(plate_status.get('active') or plate_status.get('candidate') or plate_status.get('approved') or {}).get('path'))
        see = led.get('keyframeCandidate') or led.get('keyframeApproval') or {}
        image = file_record(self.root, see.get('path') or led.get('keyframePath'))
        audio = file_record(self.root, led.get('voPath'))
        videos = [file_record(self.root, p) for p in led.get('candidatePaths', [])]
        videos = [v for v in videos if v]
        if led.get('status') == 'approved':
            videos = [v for v in [file_record(self.root, led.get('approvedTake'))] if v]
        import cb_audio_authority
        spoken = cb_audio_authority.spoken_dialogue_lines(shot) if shot else []
        if not shot and board:
            spoken = [{'speaker':line['speaker'], 'exactText':line['exactDialogue']}
                      for line in board.get('voicePerformances', [])]
        has_audio = bool(spoken)
        see_current = bool(image and (led.get('keyframeApproval') or {}).get('approved') and not led.get('keyframeCandidate'))
        if see_current:
            see_current = bool(R._keyframe_record_status(pkg, shot, led['keyframeApproval'], scope['scene'], scope['episode']).get('current'))
        voice_status = R._voice_approval_status(pkg, shot, scope['scene'], scope['episode']) if shot else {}
        audio_current = not has_audio or bool(voice_status.get('current'))
        phase = ('complete' if led.get('status') == 'approved' else
                 'film' if videos and led.get('status') == 'candidates-pending' else
                 'audio' if see_current and (audio or not has_audio) else
                 'images' if image else 'plan' if board else 'prepare')
        if see_current and audio_current and phase != 'film' and phase != 'complete':
            # Already accepted performances are reused, with a single render decision.
            phase = 'audio'
        dependency = None
        source_id = shot.get('sourceShotId')
        if source_id and (shot.get('motionContinuityRequired') or shot.get('sourceType') in ('relay','continuation')):
            prior = next((l for l in pkg.get('continuityLedger', []) if l['shotId'] == source_id), {})
            if not (prior.get('status') == 'approved' and file_record(self.root, prior.get('harvestFrame'))):
                dependency = f'Approve {source_id} and its ending before preparing this opening.'
                phase = 'dependency'
        references = R.shot_reference_manifest(scope['scene'],scope['unit'],scope['episode']) if shot else {}
        for section in ('keyframe','animation'):
            for ref in (references.get(section) or {}).get('references', []):
                asset = file_record(self.root,ref.get('path'))
                if asset: ref.update(sha256=asset['sha256'],url=asset['url'])
        review = {'references':references, 'title': shot.get('purpose') or board.get('scene', {}).get('title') or 'Scene direction',
                  'direction': shot.get('openingPose') or board.get('scene', {}).get('purpose') or '',
                  'actionPlan':[{'timing':v.get('timing',''),'action':v.get('action','')} for v in (shot.get('directorCard') or {}).get('views',[])],
                  'script': spoken, 'performancePrompt':'\n'.join(str(l.get('text') or '') for l in led.get('voGeneratedFrom', [])), 'plan': [view for scene in (board.get('sceneCoverage') or []) for view in scene.get('views', [scene])] or board.get('shots') or [],
                  'images': ([{**image,'label':'Opening keyframe'}] if image else []) + ([{**plate,'label':'Scene plate'}] if plate else []), 'plate':plate, 'audio': audio, 'videos': videos,
                  'source': authority(shot) if shot else {},
                  'seeCurrent': see_current, 'audioCurrent': audio_current,
                  'boardHash': digest(board),
                  'lineage': {k: deepcopy(led.get(k)) for k in ('batchId','watchRetake','watchRetakeHistory')},
                  'audioIssue': voice_status.get('reason'),
                  'evidencePath': str(self.root / 'cb-output' / f"{scope['episode']}_scene{scope['scene']}_production_package.json")}
        import cb_episode_budget
        budget = cb_episode_budget.status(scope['episode'])
        # A finite disclosed ceiling; existing episode reservations remain authoritative.
        # This ceiling covers specialist model checks as well as the media operation.
        limit = budget['remainingUsd'] if phase in ('prepare','plan','images','audio') else 0
        ops = {'prepare':['direction'], 'plan':['direction','keyframe'],
               'images':['direction','voice'] if has_audio else ['direction','animation'],
               'audio':['direction','animation']}.get(phase, [])
        if not has_audio and phase == 'images':
            limit = budget['remainingUsd']
        active = list(pkg.get('shots', []))
        index = next((i for i,s in enumerate(active) if s.get('shotId') == scope['unit']), -1)
        next_scope = {**scope, 'unit':active[index+1]['shotId']} if 0 <= index < len(active)-1 else None
        if next_scope is None and index == len(active)-1 and phase == 'complete':
            import cb_intake
            roster=cb_intake.scene_roster(scope['episode']).get('scenes',[])
            position=next((i for i,s in enumerate(roster) if str(s['sceneNumber'])==str(scope['scene'])),-1)
            if 0<=position<len(roster)-1:
                number=str(roster[position+1]['sceneNumber'])
                next_scope={**scope,'scene':number,'unit':f'S{number}.SH1'}
        return {'phase': phase, 'binding': digest(review), 'requiresAudio': has_audio,
                'review':review, 'disclosure':{'limitUsd':limit, 'operations':ops, 'maxMediaCalls':2 if phase=='plan' and not plate else 1,
                    'basis':'Maximum estimated API charges for this action, within your episode allowance. No automatic paid rerolls.'},
                'preserved':[s for s,b in [('Opening image',see_current),('Audio1',audio_current)] if b],
                'dependency':dependency, 'next':next_scope,
                'concerns': ['Automated checks do not establish cinematic quality. Review the returned media.']}

    def execute(self, scope, step, op):
        if step == 'approve_plan':
            _,board,shot,_ = read(self.root,scope)
            planned=next((item for item in board.get('shots',[]) if item.get('shotId')==scope['unit']),{})
            coverage=planned.get('internalShotPlan') or (planned.get('directorCard') or {}).get('views')
            if not coverage:
                raise DecisionRequired('This scene plan has no camera coverage for the selected shot.',
                    'Prepare the missing directed views before approving images.', ['Existing approved material'])
            if digest(board) != op['review']['boardHash']:
                raise DecisionRequired('The storyboard changed since your review.', 'Review the updated plan.')
            if board.get('intakeCandidateDigest') and not board.get('intakeApprovalOperationId'):
                import cb_intake, cb_db
                draft = cb_intake.preview_intake(scope['episode'])
                if draft['candidateDigest'] != board['intakeCandidateDigest']:
                    raise DecisionRequired('The script direction changed since storyboard preparation.', 'Review the updated plan.')
                approved = cb_intake.decide_intake(scope['episode'], reviewed_by=op['actor'], note='Producer journey '+op['id'])
                # Approval changes authority, not the reviewed creative content.
                board['sourceBeatPackage']['path'] = approved['canonicalPackage']
                board['vision']['approvalState'] = 'approved'
                board['intakeApprovalOperationId'] = op['id']
                path = self.root/'cb-output/creative'/f"{scope['episode']}_scene{scope['scene']}_storyboard.json"
                cb_db.atomic_write_json(self.root,path,board)
            self.server._storyboard_approval({'episode':scope['episode'],'scene':scope['scene'],
                'target':'scene','verdict':'approved','by':op['actor'],'note':'Producer journey '+op['id']})
            return {'status':'complete','message':'Plan approved; preparing images'}
        job_id = 'journey_' + op['id'] + '_' + step
        args = [str(self.root/'engine/studio_journey_worker.py'), scope_key(scope), op['id'], step]
        actual = self.server._start(job_id, 'journey:'+step, scope['scene'], args)
        if actual != job_id:
            raise DecisionRequired('An existing production job already owns this operation.', 'Resume that existing job before continuing.')
        return {'status':'pending','jobId':job_id,'message':'Preparing '+step.replace('_',' ')}

    def reconcile(self, scope, step, op):
        if step == 'approve_plan':
            _,board,_,_ = read(self.root,scope)
            if any(x.get('by') == op['actor'] and x.get('state') == 'approved' and x.get('note') == 'Producer journey '+op['id'] for x in board.get('approvalLog', [])) and board.get('approvalState')=='approved':
                return {'status':'complete'}
            raise DecisionRequired('Plan approval was interrupted.', 'Review the saved plan decision before continuing.')
        job_id = 'journey_'+op['id']+'_'+step
        import cb_db
        jobs = cb_db.load_jobs(self.root)
        job = jobs.get(job_id)
        receipt = self.root/'cb-output/state/journeys'/f'{op["id"]}_{step}.json'
        if receipt.exists():
            result = cb_db.read_json_document(self.root,receipt)[0]
            if result.get('operationId') != op['id'] or result.get('step') != step:
                raise ValueError('The worker receipt belongs to another operation.')
            if result.get('decision') and step=='submit_render':
                _,_,_,ledger=read(self.root,scope)
                expected=(op.get('receipts',{}).get('prepare_render') or {}).get('envelopeHash')
                if (ledger.get('status')=='candidates-pending' and ledger.get('candidatePaths') and expected
                        and (ledger.get('batch') or {}).get('envelopeHash')==expected):
                    return {'status':'complete','message':'Recovered the returned result of the original request'}
            if result.get('decision'):
                raise DecisionRequired(**result['decision'])
            return result
        if job and job.get('status') in ('running','finalizing'):
            return {'status':'pending','jobId':job_id,'message':job.get('step') or 'Working'}
        attempt = receipt.with_name(f'{op["id"]}_{step}_attempt.json')
        if step == 'submit_render' and attempt.exists():
            raise DecisionRequired(
                'RECOVERY REQUIRED — provider acceptance is uncertain for the original render request.',
                'Reconcile the original submission with the provider before another Fire; no replacement was submitted.',
                ['Approved opening image', 'Approved Audio1', 'Original operation and spend lineage'],
                {'jobId': job_id, 'operationId': op['id'], 'evidencePath': str(attempt),
                 'envelopeHash': (op.get('receipts', {}).get('prepare_render') or {}).get('envelopeHash')})
        raise DecisionRequired('This operation stopped before recording its outcome.',
            'Reconcile the existing job; do not submit a replacement.',
            op['review'].get('lineage',{}).keys(), {'jobId':job_id})
