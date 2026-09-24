"""SEE adapters using the existing project/native assets, image transport and budget."""
from pathlib import Path
from copy import deepcopy
import json
import math
import os
import subprocess
import sys
import time
import uuid

from studio_see_package import Package, media, checkpoints, panel_prompt, digest


def context(root, scope, server=None):
    from studio_workspace import Workspace
    ws = Workspace(root)
    ctx = ws.context(scope['projectId'], scope['episode'])
    if ctx.get('legacy'):
        from studio_journey_native import read
        import cb_render
        R = server._canonical_cb_render() if server else cb_render
        pkg, board, shot, ledger = read(Path(root), scope)
        look = R.scenelook_status(scope['scene'], scope['episode']) if shot else {}
        if shot and not look.get('current'):
            # A scoped visual amendment may explicitly carry the exact approved
            # scene plate while its historical look-direction signature is stale.
            # Verify bytes and recorded hash before projecting it as current SEE
            # geography; never infer currentness from a filename alone.
            approved = look.get('approved') or {}
            carried = next((item for item in (pkg.get('scopedAmendments') or [])
                            if item.get('shotId') == shot.get('shotId') and
                            'scenelook' in (item.get('preservedStages') or []) and
                            item.get('sceneLookContentHash') == approved.get('hash')), None)
            if carried and approved.get('path') and Path(approved['path']).is_file():
                import cb_render as _render
                if _render._sha256_file(approved['path']) == approved.get('hash'):
                    look = {**look, 'current': True, 'active': approved,
                            'activeSource': 'approved', 'approvedCurrent': True}
        plate = (look.get('active') or look.get('candidate') or look.get('approved') or {}).get('path')
        opening = (ledger.get('keyframeCandidate') or ledger.get('keyframeApproval') or {}).get('path') or ledger.get('keyframePath')
        refs = []
        if shot:
            source = R._with_effective_reference_slots(pkg, shot, 'keyframeReferenceSlots', scope['scene'], scope['episode'])
            manifest = R._provider_attachment_plan(source, 'keyframeReferenceSlots', opening,
                                                   scope['scene'], scope['episode'], R._characters_cfg())
            for ref in manifest:
                item = media(root, ref)
                if item:
                    refs.append(item)
        return dict(shot=shot, plate=plate, opening=opening, refs=refs, legacy=True,
                    componentReviews={
                        'plate': 'pending' if look.get('candidate') else 'approved' if look.get('current') else 'missing',
                        'opening': 'pending' if ledger.get('keyframeCandidate') else 'approved' if (ledger.get('keyframeApproval') or {}).get('approved') else 'missing'},
                    directorApproved=board.get('approvalState') == 'approved',
                    hasAcceptedFilm=ledger.get('status') == 'approved',
                    aspect=pkg.get('aspectRatio') or ctx['project'].get('aspectRatio') or '16:9')
    from studio_production import Production
    P = Production(ws)
    state = P.snapshot(scope['projectId'], scope['episode'])['state']
    shot = next((s for s in state['shots'] if s['id'] == scope['unit']), {})
    refs = P.assets(ctx, shot) if shot else []
    saved = Package(root, scope).read()
    plate = saved.get('plate') or next((r for r in refs if r.get('role') == 'location geography'), None)
    opening = ((P.artifact(shot, 'see') or {}).get('files') or [None])[0]
    return dict(shot=shot, plate=plate, opening=opening, refs=refs, legacy=False,
                directorApproved=bool((shot.get('planDecision') or {}).get('approved')),
                hasAcceptedFilm=(P.artifact(shot, 'watch') or {}).get('status') == 'approved',
                aspect=ctx['project'].get('aspectRatio') or '16:9', ws=ws, production=P, state=state, projectContext=ctx)


def _status(root, scope, ctx):
    status = Package(root, scope).status(ctx['shot'], ctx['plate'], ctx['opening'], ctx['refs'])
    status['componentReviews'] = ctx.get('componentReviews', {})
    status['requiresAudio'] = bool(ctx['shot'].get('dialogueLines') or ctx['shot'].get('dialogue'))
    status['directorApproved'] = ctx['directorApproved']
    status['hasAcceptedFilm'] = ctx['hasAcceptedFilm']
    if status.get('plate'):
        proof_path = (Path(root)/status['plate']['path']).with_suffix('.scene-plate-request.json')
        if proof_path.exists():
            from studio_scene_plate import request_for
            proof = json.loads(proof_path.read_text())
            try:
                current_request = request_for(root, scope, ctx)
                valid = proof.get('requestHash') == current_request['requestHash']
            except (ValueError, OSError) as exc:
                valid = False
                status['issues'].append(str(exc))
            status['scenePlateAuthority'] = {'requestHash':proof.get('requestHash'), 'status':'current' if valid else 'stale'}
            if not valid:
                status['plate']['current'] = False
                status['ready'] = status['approved'] = False
                status['issues'].append('SEE_SCENE_PLATE_AUTHORITY_STALE: the scene plate was generated from superseded authorities.')
                status['binding'] = digest([status['binding'],status['scenePlateAuthority']])
    return status


def current(root, scope, server=None):
    return _status(root, scope, context(root, scope, server))


def enrich(root, scope, snapshot):
    """A read-only projection; existing returned/approved films remain intact."""
    if not snapshot.get('review', {}).get('source'):
        return snapshot
    try:
        status = current(root, scope)
    except (ValueError, RuntimeError, OSError) as exc:
        status = {'ready': False, 'approved': False, 'issues': [str(exc)], 'panels': [], 'binding': None}
    snapshot['review']['seePackage'] = status
    if snapshot['phase'] == 'plan' and status.get('directorApproved'):
        snapshot['phase'] = 'images'
    if snapshot['phase'] == 'audio' and not status['approved']:
        snapshot['phase'] = 'images'
    if snapshot['phase'] == 'images' and not status['ready']:
        snapshot['disclosure']['ready'] = False
    if snapshot['phase'] == 'plan':
        snapshot['disclosure'] = {'limitUsd': 0, 'operations': [], 'maxMediaCalls': 0, 'ready': True,
                                  'basis': 'Approve DIRECT and open SEE. Each image request has its own disclosed cost.'}
    snapshot['binding'] = digest(snapshot['review'])
    return snapshot


def native_references(root, scope, plan):
    from studio_see_package import provider_references
    package = Package(root, scope)
    if not package.read().get('approval'):
        return plan
    status = current(root, scope)
    if not status['approved']:
        return plan  # Read-only previews remain available; dispatch is gated separately.
    plan = deepcopy(plan)
    for key, role in (('plate', 'scene plate'), ('opening', 'opening keyframe')):
        anchor = status.get(key)
        if not anchor:
            raise ValueError('The approved SEE reference package is missing its ' + key + '.')
        existing = next((r for r in plan if r.get('role') == role or
                         key == 'opening' and 'opening' in r.get('role', '')), None)
        item = {**anchor, 'path': str(Path(root)/anchor['path']), 'fileName': Path(anchor['path']).name,
                'role': role, 'usage': 'animation', 'identity': None}
        if existing is not None:
            existing.update(item)
        else:
            plan.append({**item, 'sourceSlot': 'see:'+key})
    for index, item in enumerate(plan):
        item.update(position=index+1, slot='@图'+str(index+1))
    for ref in provider_references(status, len(plan), has_audio=status.get('requiresAudio', True)):
        role = ('storyboard multi-grid plot reference' if 'MULTI_GRID_STORYBOARD' in ref['roles'] else 'storyboard ending visual reference' if 'OPTIONAL_ENDING_VISUAL_REFERENCE' in ref['roles']
                else 'storyboard critical causal reference')
        if ref['atSec'] is not None:
            role += ' at ' + str(ref['atSec']) + 's'
        plan.append({**ref, 'path': str(Path(root)/ref['path']), 'fileName': Path(ref['path']).name,
                     'position': len(plan)+1, 'slot': '@图'+str(len(plan)+1),
                     'sourceSlot': 'storyboard:'+ref['panelId'], 'role': role,
                     'usage': 'animation', 'identity': None})
    return plan


def _auto_approve_legacy_components(root, scope, status):
    """Close the deterministic legacy corridor from already-approved SEE inputs.

    Legacy shots have no separate storyboard asset when the producer has already
    approved the scene plate and opening keyframe. Record the existing
    "continue without storyboard" choice and package approval; never generate,
    infer image evidence, or replace a human component decision.
    """
    ctx = context(root, scope)
    choice = status.get('storyboardChoice') or {}
    if (not ctx.get('legacy') or choice.get('required') is True or
            ctx.get('componentReviews', {}).get('plate') != 'approved' or
            ctx.get('componentReviews', {}).get('opening') != 'approved' or
            not ctx.get('directorApproved') or status.get('issues')):
        return status
    package = Package(root, scope)
    actor = 'StudioAI (approved SEE components)'
    with package.lock():
        saved = package.read()
        if saved.get('storyboardChoice') is None:
            package.choose_storyboard(False, actor)
        reviewed = current(root, scope)
        if reviewed.get('ready') and not reviewed.get('approved'):
            package.approve(reviewed, reviewed['binding'], actor)
    return current(root, scope)


def gate(root, scope, reviewed=None, *, approved=False):
    status = current(root, scope)
    if approved and not status.get('approved'):
        status = _auto_approve_legacy_components(root, scope, status)
    if not status['ready'] or approved and not status['approved']:
        raise ValueError('WATCH_CONFIGURATION_REQUIRED: ' + ((status.get('issues') or [None])[0] or 'the selected SEE assets do not have a current package approval.'))
    if reviewed and status['binding'] != reviewed.get('binding'):
        raise ValueError('The SEE package changed after review. Review the current selected assets.')
    return status


def approve(root, scope, reviewed, actor):
    package = Package(root, scope)
    with package.lock():
        status = gate(root, scope, reviewed)
        package.approve(status, reviewed['binding'], actor)


def library(root, scope, ctx):
    # Project-scoped library plus this unit's generated/uploaded proof images.
    roots = [Path(root)/'engine/media'] if ctx['legacy'] else [Path(root)/'projects'/scope['projectId']]
    items = {}
    for base in roots:
        if not base.exists():
            continue
        for path in base.rglob('*'):
            if path.is_file() and path.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'):
                relative = path.relative_to(root).as_posix()
                items[relative] = {'path': relative, 'url': '/' + relative, 'name': path.name}
    return sorted(items.values(), key=lambda x: x['path'])


def require_plate_review_resolved(scope, ctx, component):
    if component == 'plate' and ctx['legacy']:
        import cb_render as R
        if R._load_scenelook_rec(scope['scene'], scope['episode']).get('candidate'):
            raise ValueError('A scene plate is awaiting review. Approve or reject it before generating another.')


def quote(root, scope, ctx, status, component, panel_id=None):
    if any(issue.startswith('KEEN_TAIL_CONTRADICTION') for issue in status.get('issues', [])):
        raise ValueError(' '.join(status['issues']))
    if component not in ('plate', 'opening', 'storyboard'):
        raise ValueError('Unknown SEE component.')
    if ctx['legacy'] and component == 'opening':
        raise ValueError('Use the existing scene plate/opening generation controls.')
    plate_request = None
    if component == 'plate':
        from studio_scene_plate import request_for
        plate_request = request_for(root, scope, ctx)
        prompts = [{'panelId':'plate', 'prompt':plate_request['prompt']}]
    elif component == 'storyboard':
        if not status['plate'] or not status['plate']['current'] or not status['opening'] or not status['opening']['current'] or status['issues']:
            raise ValueError('Supply the scene plate, opening and explicit DIRECT checkpoint states first. ' + ' '.join(status['issues']))
        panels = [p for p in status['panels'] if not p['reuseOpening'] and (p['status'] != 'current' or panel_id is not None)
                  and (panel_id is None or p['id'] == panel_id)]
        if not panels:
            raise ValueError('All storyboard images are current; no generation is needed.')
        landing = checkpoints(ctx['shot'])['landing']
        prompts = [{'panelId': p['id'], 'inputHash': p['inputHash'], 'prompt': panel_prompt(p, landing)} for p in panels]
    else:
        if component == 'opening' and not status['plate']:
            raise ValueError('Supply the scene plate before creating the opening.')
        shot = ctx['shot']
        prompt = ('Scene plate: world geography, fixed set dressing and lighting only. No transient character action or future events.\n' +
                  json.dumps({'location': shot.get('location'), 'references': ctx['refs'],
                              'style': ctx['projectContext']['project'].get('style')}, ensure_ascii=False)
                  if component == 'plate' else ctx['production']._prompt(ctx['projectContext'], shot, 'see', ctx['refs']))
        prompts = [{'panelId': component, 'prompt': prompt}]
    references = []
    anchors = ([status['plate'], status['opening']] if component == 'storyboard' else [status['plate']] if component == 'opening' else [])
    sources = plate_request['selectedReferences'] if plate_request else anchors + ctx['refs']
    for index, source in enumerate(sources):
        item = media(root, source)
        if item and (plate_request is not None or index < len(anchors) or item['path'] not in [r['path'] for r in references]):
            references.append({**(source if isinstance(source, dict) else {}), **item})
    if component == 'opening':
        references[0].update(name='Scene plate', role='location geography', description='Current approved world geography and lighting')
        prompts[0]['prompt'] = ctx['production']._prompt(ctx['projectContext'], ctx['shot'], 'see', references)
    if len(references) > 10:
        raise ValueError('The image provider supports ten references. Select a smaller authoritative reference set first.')
    if ctx['legacy']:
        import cb_gen, cb_costs
        binding = {'provider': 'BytePlus', 'model': cb_gen.SEEDREAM_MODEL_ID}
        unit = cb_costs.estimate_image_cost(provider='seedream5pro', num_refs=len(references), output_tier='2K')
    else:
        binding = ctx['ws'].binding(scope['projectId'], 'keyframes')
        unit = float(binding.get('unitUsd') or binding.get('estimateUsd') or 0)
    if not math.isfinite(unit) or unit <= 0:
        raise ValueError('Configure a positive image cost estimate before generating.')
    result = {'component': component, 'binding': binding, 'sourceBinding': status['binding'],
              'panelCount': len(status['panels']) if component == 'storyboard' else 1,
              'newImageCount': len(prompts), 'reusedImageCount': len(status['panels'])-len(prompts) if component == 'storyboard' else 0,
              'resolution': '2K', 'aspect': ctx['aspect'], 'estimateUsd': round(unit*len(prompts), 6),
              'hardMaximumUsd': round(unit*len(prompts), 6), 'perPanelEstimateUsd': unit,
              'panelId': panel_id, 'prompts': prompts, 'references': references,
              'textModelCalls': 0, 'automaticRetries': 0, 'separateEndingImages': 0}
    if plate_request:
        result['scenePlateRequest'] = plate_request
    result['quoteHash'] = digest(result)
    return result


def install_component(root, scope, ctx, status, component, images, source):
    package = Package(root, scope)
    from PIL import Image
    expected = ctx['aspect'].split(':')
    ratio = float(expected[0]) / float(expected[1])
    for item in images.values():
        try:
            with Image.open(Path(root)/item['path']) as image:
                width, height = image.size
                if component != 'storyboard' and abs(width/height-ratio) > .025:
                    raise ValueError(f'Scene Plate must match the project {ctx["aspect"]} aspect ratio. Received {width}×{height}.')
                image.verify()
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f'Scene Plate upload failed: unreadable image ({type(exc).__name__}).') from None
    if component == 'storyboard':
        package.install(status, images, source)
    elif component == 'plate' and ctx['legacy']:
        import cb_render as R
        record = R._load_scenelook_rec(scope['scene'], scope['episode'])
        if record.get('candidate'):
            raise ValueError('SEE_PLATE_CANDIDATE_PENDING: A Scene Plate candidate is already awaiting review. Reject or approve it before replacing it.')
        item = next(iter(images.values()))
        record['candidate'] = {'path':str(Path(root)/item['path']), 'hash':item['sha256'],
            'generatedAt':R._now(), 'approvalStatus':'PENDING_HUMAN_REVIEW',
            'scenePlateRequestHash':item.get('scenePlateRequestHash'),
            'inputSignature':R._scenelook_input_signature(scope['scene'], scope['episode'])}
        R._save_scenelook_rec(record, scope['scene'], scope['episode'])
    elif component == 'plate' and not ctx['legacy']:
        record = package.read()
        record['plate'] = media(root, next(iter(images.values())))
        package.save(record)
    elif component == 'opening' and not ctx['legacy']:
        P, ws = ctx['production'], ctx['ws']
        path = ws.project_path(scope['projectId'], next(iter(images.values()))['path'])
        with ws.db() as db:
            db.execute('BEGIN IMMEDIATE')
            state = P._load(db, scope['projectId'], scope['episode'])
            shot = P.selected(state, scope['unit'])
            if digest(shot) != digest(ctx['shot']):
                raise ValueError('The opening changed during selection; review again.')
            item = P.media_result(scope['projectId'], path, 'Producer-supplied opening image')
            item.update(sourceHash=P.source_signature(ctx['projectContext'], shot),
                        executionReceipt={'kind': source, 'providerRequests': []})
            P._replace(shot, 'see', item)
            state['revision'] += 1
            P._save(db, scope['projectId'], scope['episode'], state)
        saved = package.read()
        saved.pop('openingBinding', None)  # Explicit producer selection revalidates this opening.
        package.save(saved)
    else:
        raise ValueError('Use the existing native asset controls for this component.')


def request(server, data):
    root, scope = Path(server.ROOT), data.get('scope') or {}
    package = Package(root, scope)
    ctx = context(root, scope, server)
    status = _status(root, scope, ctx)
    command, component = data.get('command', 'status'), data.get('component', 'storyboard')
    if command == 'status':
        return status
    if command == 'library':
        return {'items': library(root, scope, ctx)}
    if command == 'quote':
        if component == 'storyboard' and ctx['legacy'] and any(ctx.get('componentReviews', {}).get(k) != 'approved' for k in ('plate', 'opening')):
            raise ValueError('Approve the scene plate and keyframe before generating the storyboard.')
        if component == 'storyboard' and status.get('storyboardRequired') is False:
            raise ValueError('Choose Use storyboard before preparing storyboard images.')
        return quote(root, scope, ctx, status, component, data.get('panelId'))
    with package.lock():
        from studio_journey import StudioStore, scope_key
        journey = StudioStore(root).read(scope_key(scope)) or {}
        if journey.get('operation', {}).get('status') in ('queued', 'running'):
            raise ValueError('Wait for this unit’s current production action before changing SEE assets.')
        ctx = context(root, scope, server)
        status = _status(root, scope, ctx)
        if data.get('binding') != status['binding']:
            raise ValueError('SEE changed in another window. Refresh before choosing an asset.')
        job = package.read().get('job') or {}
        if command == 'reconcile-job':
            if job.get('pid'):
                try:
                    os.kill(job['pid'], 0)
                except ProcessLookupError:
                    pass
                else:
                    raise ValueError('This SEE worker is still active. Wait for its existing request.')
            if job.get('status') not in ('queued', 'running', 'unknown', 'failed') or data.get('providerChecked') is not True or not str(data.get('note') or '').strip():
                raise ValueError('Check the provider outcome and record the result before resolving this job.')
            record = package.read()
            record['job'].update(status='resolved', reconciliation={'note': str(data['note'])[:2000], 'at': time.time()})
            package.save(record)
            return current(root, scope, server)
        if job.get('status') in ('queued', 'running', 'unknown'):
            raise ValueError('A SEE generation is already active or needs recovery. Do not submit it again.')
        if command == 'continue-without-storyboard':
            if not ctx['legacy'] or any(ctx.get('componentReviews', {}).get(k) != 'approved' for k in ('plate', 'opening')):
                raise ValueError('Approve the scene plate and keyframe first, then continue without a storyboard.')
            if not ctx['directorApproved']:
                raise ValueError('The current scene direction needs approval before continuing to HEAR.')
            actor = str(data.get('by') or '').strip()
            package.choose_storyboard(False, actor)
            reviewed = current(root, scope, server)
            package.approve(reviewed, reviewed['binding'], actor)
            return current(root, scope, server)
        if command == 'review-component':
            if not ctx['legacy'] or component not in ('plate', 'opening'):
                raise ValueError('Choose a scene plate or opening keyframe to review.')
            if ctx.get('componentReviews', {}).get(component) != 'pending':
                raise ValueError('This image is no longer awaiting a decision. Refresh SEE.')
            decision, actor = data.get('decision'), str(data.get('by') or '').strip()
            if decision not in ('approved', 'rejected') or not actor:
                raise ValueError('Choose Approve or Reject and identify the reviewer.')
            if component == 'opening' and decision == 'approved' and ctx['componentReviews'].get('plate') != 'approved':
                raise ValueError('Approve the scene plate before approving the keyframe.')
            reason = str(data.get('reason') or '').strip()
            if decision == 'rejected' and not reason:
                raise ValueError('Tell us what needs to change before rejecting this image.')
            R = server._canonical_cb_render()
            args = [scope['scene']] + ([scope['unit']] if component == 'opening' else [])
            if decision == 'rejected':
                args.append(reason)
            name = ('approve_' if decision == 'approved' else 'reject_') + ('scenelook' if component == 'plate' else 'keyframe')
            extra = ({'reuse_prompt_change': True}
                     if component == 'opening' and decision == 'approved' and data.get('reusePromptChange') is True else {})
            getattr(R, name)(*args, episode=scope['episode'], reviewed_by=actor, log=lambda line: None, **extra)
            saved = package.read()
            saved.pop('approval', None)
            package.save(saved)
            return current(root, scope, server)
        if command == 'choose-storyboard':
            package.choose_storyboard(data.get('required'), str(data.get('by') or 'Producer'))
            return current(root, scope, server)
        if component == 'storyboard' and status.get('storyboardRequired') is False and command != 'approve-existing-film-see':
            raise ValueError('Choose Use storyboard before changing storyboard assets.')
        if not ctx['directorApproved']:
            raise ValueError('Approve DIRECT before preparing the SEE assets.')
        if command == 'approve-existing-film-see':
            if not ctx['hasAcceptedFilm']:
                raise ValueError('Use the current Approve SEE production action for this unit.')
            package.approve(status, data['binding'], str(data.get('by') or 'Producer'))
        elif command == 'compile-grid':
            package.compile_grid(status)
        elif command in ('review-panel', 'approve-storyboard'):
            panel_ids = [p['id'] for p in status['panels']] if command == 'approve-storyboard' else [data.get('panelId')]
            package.review_panels(status, panel_ids, 'approved' if command == 'approve-storyboard' else data.get('decision'),
                                  str(data.get('by') or 'Producer'), data.get('reason', ''))
        elif command == 'select-role':
            package.select(status, data['panelId'], data['role'], data.get('selected') is True)
        elif command in ('upload', 'select-library'):
            images = {}
            allowed = {r['path'] for r in library(root, scope, ctx)} if command == 'select-library' else set()
            for row in data.get('images') or []:
                if command == 'upload':
                    blob, extension = server.decode_image_upload(row['data'])
                    directory = root/('engine/media/see-storyboards' if ctx['legacy'] else 'projects/'+scope['projectId']+'/media/see')
                    directory.mkdir(parents=True, exist_ok=True)
                    path = directory/(uuid.uuid4().hex + extension)
                    path.write_bytes(blob)
                    item = media(root, str(path))
                else:
                    if row['path'] not in allowed:
                        raise ValueError('Choose an image from this project library.')
                    item = media(root, row['path'])
                if row.get('fidelity'):
                    item['fidelity'] = row['fidelity']
                images[row['panelId']] = item
            if not images:
                raise ValueError('Select at least one image.')
            install_component(root, scope, ctx, status, component, images, 'upload' if command == 'upload' else 'library')
        elif command == 'generate':
            if component == 'storyboard' and ctx['legacy'] and any(ctx.get('componentReviews', {}).get(k) != 'approved' for k in ('plate', 'opening')):
                raise ValueError('Approve the scene plate and keyframe before generating the storyboard.')
            require_plate_review_resolved(scope, ctx, component)
            proposal = quote(root, scope, ctx, status, component, data.get('panelId'))
            if proposal['quoteHash'] != data.get('quoteHash'):
                raise ValueError('Review the current provider, image count and cost before generating.')
            record = package.read()
            job = {'id': uuid.uuid4().hex, 'status': 'queued', 'quote': proposal,
                   'scope': scope, 'createdAt': time.time(), 'completed': []}
            record['job'] = job
            package.save(record)  # Persist before dispatch; never auto-replay unknown requests.
            log = root/'cb-output/state/see-packages'/(job['id']+'.log')
            try:
                with log.open('ab') as output:
                    process = subprocess.Popen([sys.executable, str(root/'engine/studio_see_worker.py'),
                                               json.dumps(scope), job['id']], cwd=root/'engine', stdout=output, stderr=output)
                record['job']['pid'] = process.pid
                package.save(record)
            except OSError:
                record['job'].update(status='failed', error='The image worker did not start. No provider request was dispatched.')
                package.save(record)
                raise
        else:
            raise ValueError('Unknown SEE action.')
    return current(root, scope, server)
