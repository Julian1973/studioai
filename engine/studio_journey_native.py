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
from studio_roots import data_root


def _servable_roots(root):
    source = Path(root).resolve()
    data = data_root(source)
    roots = [(source, "/")]
    for media_root, url_prefix in (
            (data / "engine" / "media", "/engine/media/"),
            (data / "media", "/engine/media/"),
            (data / "cb-seed" / "assets", "/cb-seed/assets/")):
        resolved = media_root.resolve()
        if all(resolved != existing for existing, _ in roots):
            roots.append((resolved, url_prefix))
    return roots


def file_record(root, value):
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    for base, url_prefix in _servable_roots(root):
        try:
            relative = path.relative_to(base)
            break
        except ValueError:
            continue
    else:
        raise ValueError('This production asset is outside the Studio media library.')
    if not path.is_file():
        return None
    return {'path': str(path), 'url': url_prefix + relative.as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def optional_collection(value, field):
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f'STUDIO_JOURNEY_INVALID_COLLECTION: {field} must be a list or null')
    return value


def read(root, scope):
    scope_key(scope)
    # Production records live under the data root; in a single-root deployment that is
    # the studio root itself. Reading them from the release folder returns an empty shot
    # and SEE then refuses with 'complete the timed action in DIRECT' (17 Sep outage class).
    root = Path(root)
    data = data_root(root)
    path = data / 'cb-output' / f"{scope['episode']}_scene{scope['scene']}_production_package.json"
    board_path = data / 'cb-output/creative' / f"{scope['episode']}_scene{scope['scene']}_storyboard.json"
    import cb_db
    pkg = cb_db.read_json_document(root, path)[0] if path.exists() else {}
    board = cb_db.read_json_document(root, board_path)[0] if board_path.exists() else {}
    shot = next((s for s in optional_collection(pkg.get('shots'), 'shots')
                 if s['shotId'] == scope['unit']), {})
    led = next((s for s in optional_collection(pkg.get('continuityLedger'), 'continuityLedger')
                if s['shotId'] == scope['unit']), {})
    return pkg, board, shot, led


def authority(shot):
    # Use the existing source projector, not a second list of creative fields.
    from studio_director_handoff import source
    return source(shot)


def _phase_from_policy(board, policy, shot_state, ledger):
    """Project the single approval policy into the producer journey's next stage."""
    # `packageCurrent` already includes the canonical Storyboard approval/lineage
    # check. Do not re-check a second board projection here; it can be absent or stale
    # even when the server's authoritative package policy is current.
    if not policy.get('packageExists') and not board:
        return 'prepare'
    if not policy.get('packageCurrent'):
        return 'plan'
    if not shot_state:
        return 'images'
    if shot_state.get('kf') == 'waitingPrev':
        return 'dependency'
    if (ledger.get('status') == 'candidates-pending' and
            shot_state.get('animState') in ('candidates-pending', 'stale-batch')):
        return 'film'
    current = shot_state.get('current') or {}
    if ledger.get('status') == 'approved' and current.get('animation'):
        return 'complete'
    if current.get('keyframe'):
        return 'audio'
    return 'images'


class Native:
    def __init__(self, root, server):
        self.root, self.server = Path(root), server

    def snapshot(self, scope):
        if scope['projectId'] != 'crystal-bears':
            raise ValueError('The selected project uses its project production service.')
        pkg, board, shot, led = read(self.root, scope)
        R = self.server._canonical_cb_render()
        state_reader = getattr(self.server, '_production_state', None)
        if state_reader:
            policy = state_reader(scope['scene'], scope['episode'])
        else:
            state_module = getattr(self.server, '_canonical_cb_state', None)
            if state_module:
                policy = state_module().production_state(scope['scene'], scope['episode'])
            else:
                import cb_state
                policy = cb_state.production_state(scope['scene'], scope['episode'])
        shot_state = next((row for row in policy.get('shots', [])
                           if row.get('shotId') == scope['unit']), None)
        plate_status = R.scenelook_status(scope['scene'],scope['episode']) if shot else {}
        plate = file_record(self.root,(plate_status.get('active') or plate_status.get('candidate') or plate_status.get('approved') or {}).get('path'))
        see = led.get('keyframeCandidate') or led.get('keyframeApproval') or {}
        image = file_record(self.root, see.get('path') or led.get('keyframePath'))
        plate_review = ('pending' if plate_status.get('candidate') and plate_status.get('candidateCurrent') else
                        'stale' if plate_status.get('candidate') else
                        'approved' if plate_status.get('current') else
                        'stale' if plate_status.get('approved') else 'missing')
        opening_review = ('pending' if led.get('keyframeCandidate') else
                          'approved' if (led.get('keyframeApproval') or {}).get('approved') else 'missing')
        audio = file_record(self.root, led.get('voPath'))
        videos = [file_record(self.root, p) for p in
                  optional_collection(led.get('candidatePaths'), 'candidatePaths')]
        videos = [v for v in videos if v]
        if led.get('status') == 'approved':
            videos = [v for v in [file_record(self.root, led.get('approvedTake'))] if v]
        import cb_audio_authority
        spoken = cb_audio_authority.spoken_dialogue_lines(shot) if shot else []
        if not shot and board:
            spoken = [{'speaker':line['speaker'], 'exactText':line['exactDialogue']}
                      for line in board.get('voicePerformances', [])]
        has_audio = bool(spoken)
        projection_issues = []
        current_state = (shot_state or {}).get('current') or {}
        see_current = bool(image and current_state.get('keyframe'))
        try:
            voice_status = R._voice_approval_status(
                pkg, shot, scope['scene'], scope['episode']) if shot else {}
        except (R.Refused, OSError, ValueError, KeyError) as exc:
            voice_status = {'current': False, 'reason': str(exc)}
            projection_issues.append(str(exc))
        audio_current = not has_audio or bool(current_state.get('voice'))
        # An approved storyboard is the SEE handoff. Keep the existing image
        # review surface visible even when its media is missing or stale so the
        # producer can upload, refire, choose from the library, or review it.
        phase = _phase_from_policy(board, policy, shot_state, led)
        # Keep an existing candidate visible for an explicit human decision, even
        # when its dependency check now marks it stale. Approval remains guarded.
        if led.get('status') == 'candidates-pending' and videos and phase != 'dependency':
            phase = 'film'
        dependency = None
        reference_issue = None
        try:
            references = R.shot_reference_manifest(
                scope['scene'], scope['unit'], scope['episode']) if shot else {}
        except (R.Refused, OSError, ValueError, KeyError) as exc:
            # A read-only journey projection must still show the human-reviewable media.
            # WATCH/preflight keeps the hard reference gate; projection surfaces the issue.
            references = {}
            reference_issue = str(exc)
        for section in ('keyframe','animation'):
            for ref in (references.get(section) or {}).get('references', []):
                asset = file_record(self.root,ref.get('path'))
                if asset: ref.update(sha256=asset['sha256'],url=asset['url'])
        storyboard = [
            {**view, 'storyboardIndex': index + 1}
            for index, view in enumerate(
                [view for scene in optional_collection(board.get('sceneCoverage'), 'sceneCoverage')
                 for view in scene.get('views', [scene])]
                or optional_collection(board.get('shots'), 'storyboard shots')
            )
        ]
        from studio_see_package import Package
        storyboard_choice = Package(self.root, scope).read().get('storyboardChoice')
        storyboard_required = True if storyboard_choice is None else bool(storyboard_choice.get('required'))
        review_images = ([{**image, 'label':'Opening keyframe', 'component':'opening', 'reviewStatus':opening_review}] if image else [])
        if image and led.get('keyframeCandidate') and see.get('inputSignature'):
            from studio_keyframe_selection import can_reuse_prompt_change
            try:
                expected = R._keyframe_record_input_signature(pkg, shot, see, scope['scene'], scope['episode'])
                review_images[0]['reusePromptChange'] = bool(
                    len(led.get('keyframeCandidates') or []) <= 1 and
                    can_reuse_prompt_change(see, expected, image['sha256']))
            except (R.Refused, OSError, ValueError):
                review_images[0]['reusePromptChange'] = False
        review_images += ([{**plate, 'label':'Scene plate', 'component':'plate', 'reviewStatus':plate_review}] if plate else [])
        reference_inputs = []
        for section_name, section in references.items():
            if not isinstance(section, dict):
                continue
            for item in section.get('references') or []:
                reference_inputs.append({**item, 'stage': section_name,
                                         'label': item.get('role') or item.get('fileName') or 'Reference'})
        from studio_coverage import producer_scene_sequence
        review = {'references':references, 'referenceInputs':reference_inputs,
                  'referenceIssue':reference_issue,
                  'sceneSequence':producer_scene_sequence(
                      board.get('sceneDirectionCard'), board.get('approvalState')),
                  'title': shot.get('purpose') or board.get('scene', {}).get('title') or 'Scene direction',
                  'direction': shot.get('openingPose') or board.get('scene', {}).get('purpose') or '',
                  'actionPlan':[{'timing':v.get('timing',''),'action':v.get('action','')} for v in (shot.get('directorCard') or {}).get('views',[])],
                  'script': spoken, 'performancePrompt':'\n'.join(str(l.get('text') or '') for l in optional_collection(led.get('voGeneratedFrom'), 'voGeneratedFrom')), 'plan': [view for scene in optional_collection(board.get('sceneCoverage'), 'sceneCoverage') for view in scene.get('views', [scene])] or optional_collection(board.get('shots'), 'storyboard shots'),
                  'images': review_images, 'storyboard': storyboard, 'storyboardRequired': storyboard_required,
                  'storyboardChoice': storyboard_choice, 'plate':plate, 'audio': audio, 'videos': videos,
                  'source': authority(shot) if shot else {},
                  'seeCurrent': see_current, 'audioCurrent': audio_current,
                  'boardHash': digest(board),
                  'lineage': {k: deepcopy(led.get(k)) for k in ('batchId','watchRetake','watchRetakeHistory')},
                  'audioIssue': voice_status.get('reason'),
                  'issues': projection_issues + ([reference_issue] if reference_issue else []),
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
        active = optional_collection(pkg.get('shots'), 'shots')
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

    def see_package_status(self, scope):
        """Read the deterministic storyboard package outside the decision binding."""
        snapshot = self.snapshot(scope)
        review = snapshot.get('review') or {}
        opening = next((item for item in review.get('images') or [] if item.get('component') == 'opening'), None)
        references = []
        for section in (review.get('references') or {}).values():
            if isinstance(section, dict):
                references.extend(section.get('references') or [])
            elif isinstance(section, list):
                references.extend(section)
        from studio_see_package import Package
        shot = read(self.root, scope)[2]
        return Package(self.root, scope).status(shot, review.get('plate'), opening, references)

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
