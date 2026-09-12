"""Existing native operations invoked by one durable five-action worker step."""
from contextlib import contextmanager
from pathlib import Path
import json
import sys
import os
from studio_journey import StudioStore, DecisionRequired, digest, scope_key
from studio_journey_native import read, authority, file_record


def unchanged(root, expected, actual, label):
    if not expected or not actual or expected.get('sha256') != actual.get('sha256'):
        raise DecisionRequired(f'{label} changed after your review.', f'Review the current {label.lower()}.')


@contextmanager
def spending(root, op):
    """Bound EVERY native reservation to this producer action, including model checks.

    Wrap the existing reservation boundary inside this isolated worker. Keep unknown
    charges counted; a failed or interrupted provider request cannot free retry money.
    """
    import cb_episode_budget as budget
    import cb_db
    original = budget.reserve
    path = root/'cb-output/state/journeys'/f'{op["id"]}_spend.json'
    def reserve(episode, amount, operation):
        with cb_db.scene_lease(root, 'journey-cost', op['id'], 'reserve', wait_seconds=1):
            state = cb_db.read_json_document(root,path)[0] if path.exists() else {'charges':[]}
            units = budget._units(amount)
            used = sum(x['units'] for x in state['charges'])
            if units+used > budget._units(op['grant']['limitUsd']):
                raise DecisionRequired('This action would exceed the cost you approved.',
                    'Review an updated cost before continuing.', ['Existing approved media'])
            allowed = op['grant'].get('operations', [])
            kind = ('direction' if str(operation).startswith(('text:', 'vision:', 'review')) else
                    'keyframe' if 'keyframe' in str(operation) else
                    'voice' if 'voice' in str(operation) else 'animation')
            if kind not in allowed:
                raise DecisionRequired('This action would call an undisclosed service.', 'Review its scope and cost first.')
            media_count = sum(x['kind'] != 'direction' for x in state['charges'])
            if kind != 'direction' and media_count >= op['grant'].get('maxMediaCalls',1):
                raise DecisionRequired('This action already used its media request.', 'Review or recover the existing result; another take needs a new decision.')
            # Persist before existing allowance reservation / external submission.
            state['charges'].append({'units':units,'operation':operation,'kind':kind})
            cb_db.atomic_write_json(root,path,state)
            return original(episode,amount,operation)
    budget.reserve = reserve
    try:
        yield
    finally:
        budget.reserve = original


def perform(root, scope, step, op, R=None, D=None):
    if R is None:
        import cb_render as R
    if D is None:
        import cb_studio_director as D
    sc,ep,unit = scope['scene'],scope['episode'],scope['unit']
    pkg,board,shot,led = read(root,scope)
    review = op['review']
    if step not in ('prepare_plan','prepare_next') and review.get('source') and authority(shot) != review['source']:
        raise DecisionRequired('The approved shot direction changed during this action.',
            'Review the updated direction before continuing.', ['Existing approved images and audio'])
    if step not in ('prepare_plan','prepare_next'):
        for section in ('keyframe','animation'):
            for ref in (review.get('references',{}).get(section) or {}).get('references',[]):
                if ref.get('sha256'):
                    unchanged(root,ref,file_record(root,ref.get('path')),ref.get('role') or 'Reference')
    if step == 'prepare_plan':
        if not board:
            import cb_creative
            import cb_intake
            status = {'canonicalCurrent': True} if pkg else cb_intake.intake_status(ep)
            if not status.get('canonicalCurrent'):
                if not status.get('candidateCurrent'):
                    cb_intake.prepare_intake(ep)
                cb_creative.run_scene(sc,ep,intake_preview=True)
            else:
                cb_creative.run_scene(sc,ep)
        return {'status':'complete','message':'Direction and storyboard ready for your review'}
    if step == 'create_images':
        look = R.scenelook_status(sc,ep)
        if not look.get('current'):
            if look.get('approved') or look.get('candidate'):
                raise DecisionRequired('The scene plate needs a specific source review.', 'Review its changed reference or direction before replacing it.', ['Existing scene plate'])
            R.prepare_department(sc,'look',None,ep)
            R.generate_scenelook_plate(sc,ep)
        if led.get('keyframeCandidate'):
            return {'status':'complete','message':'Current image candidate reused'}
        if (led.get('keyframeApproval') or {}).get('approved'):
            R._anchor_for(pkg,shot)
            return {'status':'complete','message':'Current approved opening reused'}
        D.build_keyframe(sc,unit,ep)
    elif step == 'review_images':
        candidate = led.get('keyframeCandidate') or led.get('keyframeApproval') or {}
        if not file_record(root,candidate.get('path')):
            raise DecisionRequired('The opening image has not returned.', 'Recover the existing image job.')
        # Conformance screening is produced by the normal image path. A missing
        # judgement is UNVERIFIED, never manufactured as an image recognition pass.
        screening = candidate.get('conformanceScreening') or {'status':'unverified'}
        return {'status':'complete','message':'Opening image ready for review','screening':screening}
    elif step == 'approve_images':
        current = led.get('keyframeCandidate') or led.get('keyframeApproval') or {}
        unchanged(root,(review.get('images') or [None])[0],file_record(root,current.get('path')),'Opening image')
        if led.get('keyframeCandidates') and current.get('candidateId'):
            # The producer is approving the exact image displayed in this action.
            # Bind that selection through the existing service before its approval.
            R.select_keyframe_candidate(sc,unit,current['candidateId'],ep)
        look=R.scenelook_status(sc,ep)
        if look.get('candidate'):
            unchanged(root,review.get('plate'),file_record(root,look['candidate'].get('path')),'Scene plate')
            # The image set is one explicit producer decision; no machine approval.
            R.approve_scenelook(sc,ep,reviewed_by=op['actor'])
        current = led.get('keyframeCandidate') or led.get('keyframeApproval') or {}
        unchanged(root,(review.get('images') or [None])[0],file_record(root,current.get('path')),'Opening image')
        if not led.get('keyframeCandidate') and (led.get('keyframeApproval') or {}).get('approved'):
            R._anchor_for(pkg,shot)
        else:
            R.approve_keyframe(sc,unit,ep,reviewed_by=op['actor'])
    elif step == 'create_audio':
        status = R._voice_approval_status(pkg,shot,sc,ep)
        if status.get('current'):
            return {'status':'complete','message':'Approved Audio1 reused without generation'}
        if led.get('voPath') and not (led.get('voiceApproval') or {}).get('approved'):
            return {'status':'complete','message':'Existing voice candidate ready for review'}
        D.build_voice(sc,unit,ep)
    elif step == 'review_audio':
        if not file_record(root,led.get('voPath')) or not led.get('voTimingPath'):
            raise DecisionRequired('The performance or measured cues are missing.', 'Recover the existing voice job.')
        return {'status':'complete','message':'Listen to the performance and review its exact words'}
    elif step == 'approve_audio':
        import cb_audio_authority
        if not cb_audio_authority.spoken_dialogue_lines(shot):
            return {'status':'complete','message':'No voice approval required for this silent unit'}
        unchanged(root,review.get('audio'),file_record(root,led.get('voPath')),'Audio1')
        if not R._voice_approval_status(pkg,shot,sc,ep).get('current'):
            R.approve_voice(sc,unit,ep,reviewed_by=op['actor'])
    elif step == 'align_timing':
        import cb_post
        from studio_delivery_contract import require_aligned_timing
        if led.get('voPath'):
            try:
                require_aligned_timing(shot['durationSec'],audio_duration=cb_post._dur(led['voPath']))
            except ValueError as exc:
                raise DecisionRequired(str(exc),'Review the proposed duration and affected direction before rendering.', ['Approved opening','Approved Audio1']) from exc
    elif step == 'prepare_render':
        D.prepare_render(sc,unit,ep)
        _,_,after,after_led = read(root,scope)
        if authority(after) != authority(shot):
            raise DecisionRequired('Timing preparation changed the approved direction.', 'Review the changed timing before rendering.', ['Approved opening','Approved Audio1'])
        auth = after_led.get('pendingSpendAuth') or {}
        if not auth.get('envelopeHash'):
            raise DecisionRequired('No reviewed animation request was sealed.', 'Resolve the recorded preflight issue.')
        return {'status':'complete','message':'Final request reviewed and sealed',
                'envelopeHash':auth['envelopeHash'], 'cost':auth['disclosure']['maxBatchCostUsd']}
    elif step == 'submit_render':
        auth = led.get('pendingSpendAuth') or {}
        prepared = op['receipts'].get('prepare_render') or {}
        if not auth or auth.get('envelopeHash') != prepared.get('envelopeHash'):
            raise DecisionRequired('The prepared animation request changed.', 'Review its current bindings before Fire.')
        if auth['disclosure']['maxBatchCostUsd'] > op['grant']['limitUsd']:
            raise DecisionRequired('The render exceeds this action’s authorised cost.', 'Review the exact revised cost.')
        # Existing Fire verifies source, files, exact sealed bytes and single-use token.
        R.fire_shot(sc,unit,ep,candidates=1,spend_token=auth['token'])
    elif step == 'review_film':
        origin = R._returned_origin(led)
        if not (origin.get('originIntegrity') or {}).get('verified'):
            raise DecisionRequired('Returned footage could not be linked to its reviewed request.', 'Reconcile the originating request before approval.')
        if not led.get('candidatePaths'):
            raise DecisionRequired('The rendered film has not returned.', 'Recover the existing provider job.')
        R.prepare_department(sc,'review-animation',unit,ep)
        return {'status':'complete','message':'Film and review ready for your decision','origin':origin}
    elif step == 'approve_film':
        actual = file_record(root,(led.get('candidatePaths') or [None])[0])
        unchanged(root,(review.get('videos') or [None])[0],actual,'Rendered film')
        if not (R._returned_origin(led).get('originIntegrity') or {}).get('verified'):
            raise DecisionRequired('The film’s originating request is no longer verified.', 'Reconcile its origin before approval.')
        R.approve_shot(sc,unit,candidate=1,episode=ep,reviewed_by=op['actor'])
    elif step == 'assemble':
        if led.get('status') != 'approved' or not file_record(root,led.get('harvestFrame')):
            raise DecisionRequired('The accepted film’s ending has not been recorded.', 'Recover its existing approval.')
        # cb_post derives its assembly selection from this very approval ledger.
        # Build a scene preview only when all scene clips are accepted.
        if all(l.get('status')=='approved' for l in pkg.get('continuityLedger',[])):
            state=R.post_status(pkg,sc,ep) if hasattr(R,'post_status') else {}
            if not ((state.get('candidate') or {}).get('current') or (state.get('approved') or {}).get('current')):
                R.stitch_scene(sc,ep)
        return {'status':'complete','message':'Accepted take included in the scene assembly selection'}
    elif step == 'prepare_next':
        index=next((i for i,s in enumerate(pkg.get('shots',[])) if s.get('shotId')==unit),-1)
        if 0<=index<len(pkg['shots'])-1:
            from studio_director_handoff import refresh_previous_frame
            _,package_path=R.load_pkg(sc,ep)
            refresh_previous_frame(R,pkg,package_path,pkg['shots'][index+1])
        return {'status':'complete','message':'Ready for the next production unit'}
    else:
        raise ValueError('Unsupported production step')
    return {'status':'complete'}


def main(root, key, op_id, step):
    import cb_db
    store = StudioStore(root)
    state = store.read(key)
    op = state['operation']
    if scope_key(state['scope']) != key or op['id'] != op_id or op['pending'] != step or step not in op['steps']:
        raise ValueError('This worker is not authorised by the current producer decision.')
    result_path = root/'cb-output/state/journeys'/f'{op_id}_{step}.json'
    if result_path.exists():
        return  # A completed step never replays approvals, retrieval or generation.
    if step == 'submit_render':
        # A restarted worker must not re-enter Fire after an unreceipted attempt.
        # The existing job/provider recovery owns reconciliation of that attempt.
        attempt_path = result_path.with_name(f'{op_id}_{step}_attempt.json')
        with cb_db.scene_lease(root, 'journey-submission', op_id, 'claim', wait_seconds=1):
            if attempt_path.exists():
                return
            cb_db.atomic_write_json(root, attempt_path, {
                'operationId': op_id, 'step': step,
                'envelopeHash': (op.get('receipts', {}).get('prepare_render') or {}).get('envelopeHash'),
                'status': 'acceptance-unknown-until-reconciled',
                'sourceBinding': op.get('binding'),
            })
    os.environ['CB_EPISODE'] = state['scope']['episode']
    try:
        with spending(root,op):
            result = perform(root,state['scope'],step,op)
    except DecisionRequired as exc:
        result = {'status':'complete','decision':exc.detail}
    except Exception as exc:
        result = {'status':'complete','decision':{'issue':str(exc),
            'proposed':'Review the recorded issue and recover this operation before another submission.',
            'preserved':['Existing approved material']}}
    cb_db.atomic_write_json(root,result_path,{**result,'operationId':op_id,'step':step})


if __name__ == '__main__':
    main(Path(__file__).resolve().parent.parent,*sys.argv[1:])
