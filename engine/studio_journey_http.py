"""Routes inside the existing authenticated Studio server."""
from studio_journey import Journey, StudioStore, DecisionRequired, scope_key
from pathlib import Path
import threading
import time
import uuid

_ACTIVE=set()
_LOCK=threading.Lock()
CRYSTAL_BEARS_PROJECT_ID = "crystal-bears"
CRYSTAL_BEARS_ACTIVE_ENGINE = "golden-path-native"


def active_engine(scope):
    project = str((scope or {}).get("projectId") or "")
    return CRYSTAL_BEARS_ACTIVE_ENGINE if project == CRYSTAL_BEARS_PROJECT_ID else "project"


def controller(server, scope):
    if active_engine(scope) == CRYSTAL_BEARS_ACTIVE_ENGINE:
        from studio_journey_native import Native
        adapter=Native(server.ROOT,server)
    else:
        from studio_workspace import Workspace
        from studio_journey_project import Project
        workspace=Workspace(server.ROOT)
        adapter=Project(server.ROOT,workspace)
    return Journey(StudioStore(server.ROOT),adapter)


def continue_operation(server,scope):
    key=scope_key(scope)
    with _LOCK:
        if key in _ACTIVE:return
        _ACTIVE.add(key)
    def work():
        try:
            J=controller(server,scope)
            while True:
                J.tick(scope)
                state=J.store.read(key) or {}
                if state.get('operation',{}).get('status') not in ('queued','running'):break
                time.sleep(1)
        finally:
            with _LOCK:_ACTIVE.discard(key)
    threading.Thread(target=work,name='studio-journey-'+key[:8],daemon=True).start()


def image_review(server, data):
    scope = data.get('scope') or {}
    if active_engine(scope) != CRYSTAL_BEARS_ACTIVE_ENGINE:
        raise ValueError('Image review is only available in the Crystal Bears Golden Path.')
    scope_key(scope)
    component = str(data.get('component') or '')
    decision = str(data.get('decision') or '')
    actor = str(data.get('by') or 'Producer').strip()
    if component not in ('opening', 'plate'):
        raise ValueError('Choose an opening keyframe or scene plate.')
    if decision == 'refire':
        return {'ok': True, 'component': component, 'decision': decision,
                'nextStage': 'keyframe' if component == 'opening' else 'scenelook',
                'zeroSpend': True,
                'message': 'Refire controls opened. Review the exact request before any provider submission.'}
    if decision not in ('approved', 'rejected') or not actor:
        raise ValueError('Choose Approve or Reject and identify the reviewer.')
    from studio_see_service import request as see_request
    status = see_request(server, {'scope': scope, 'command': 'status'})
    if data.get('binding') is not None and data['binding'] != status.get('binding'):
        raise ValueError('This image changed after you opened it. Review the current image before approving.')
    result = see_request(server, {'scope': scope, 'command': 'review-component',
                                  'component': component, 'decision': decision,
                                  'reason': str(data.get('reason') or '').strip(), 'by': actor,
                                  'binding': status.get('binding')})
    return {'ok': True, 'component': component, 'decision': decision,
            'zeroSpend': True, 'see': result}


def storyboard_choice(server, data):
    scope = data.get('scope') or {}
    if active_engine(scope) != CRYSTAL_BEARS_ACTIVE_ENGINE:
        raise ValueError('Storyboard choice is only available in the Crystal Bears Golden Path.')
    scope_key(scope)
    required = data.get('required')
    actor = str(data.get('by') or 'Producer').strip()
    if type(required) is not bool or not actor:
        raise ValueError('Choose Use storyboard or Skip storyboard and identify the reviewer.')
    from studio_see_service import request as see_request
    status = see_request(server, {'scope': scope, 'command': 'status'})
    result = see_request(server, {'scope': scope, 'command': 'choose-storyboard',
                                  'required': required, 'by': actor,
                                  'binding': status.get('binding')})
    return {'ok': True, 'required': required, 'zeroSpend': True, 'see': result}


def storyboard_grid(server, data):
    scope = data.get('scope') or {}
    if active_engine(scope) != CRYSTAL_BEARS_ACTIVE_ENGINE:
        raise ValueError('Storyboard grid is only available in the Crystal Bears Golden Path.')
    actor = str(data.get('by') or 'Producer').strip()
    if not actor:
        raise ValueError('Identify the reviewer before compiling the storyboard grid.')
    from studio_see_service import request as see_request
    status = see_request(server, {'scope': scope, 'command': 'status'})
    result = see_request(server, {'scope': scope, 'command': 'compile-grid',
                                  'binding': status.get('binding'), 'by': actor})
    return {'ok': True, 'zeroSpend': True, 'see': result}


def storyboard_action(server, data):
    scope = data.get('scope') or {}
    if active_engine(scope) != CRYSTAL_BEARS_ACTIVE_ENGINE:
        raise ValueError('Use the selected project storyboard controls.')
    command = data.get('action')
    if command not in ('quote', 'generate', 'upload', 'review-panel'):
        raise ValueError('Choose a current storyboard action.')
    from studio_see_service import request as see_request
    payload = {key: data[key] for key in ('scope', 'binding', 'panelId', 'images',
               'decision', 'reason', 'quoteHash', 'by') if key in data}
    result = see_request(server, {**payload, 'command': command, 'component': 'storyboard'})
    return {'ok': True, 'zeroSpend': command != 'generate',
            'quote' if command == 'quote' else 'see': result}


def enrich_native_view(server, scope, view):
    if active_engine(scope) != CRYSTAL_BEARS_ACTIVE_ENGINE or view.get('phase') in ('prepare', 'plan'):
        return view
    try:
        from studio_journey_native import Native
        view.setdefault('review', {})['seePackage'] = Native(server.ROOT, server).see_package_status(scope)
    except Exception as exc:
        view.setdefault('review', {})['seePackage'] = {
            'ready': False, 'approved': False, 'issues': [str(exc)], 'panels': [], 'providerSheet': {}}
    return view


def request(server,data):
    scope=data.get('scope') or {}
    action=data.get('command','status')
    request_id=str(data.get('requestId') or ('journey_'+uuid.uuid4().hex[:12]))
    try:
        scope_key(scope)
        if action == 'image-review':
            return image_review(server, data)
        if action == 'storyboard-choice':
            return storyboard_choice(server, data)
        if action == 'storyboard-grid':
            return storyboard_grid(server, data)
        if action == 'storyboard-action':
            return storyboard_action(server, data)
        J=controller(server,scope)
        if action=='decide':
            J.accept(scope,data,str(data.get('by') or 'Producer'))
            continue_operation(server,scope)
        elif action=='recover':
            J.recover(scope)
            continue_operation(server,scope)
        elif action=='request-displayed':
            J.displayed(scope, data.get('operationId'), data.get('requestHash'))
            continue_operation(server,scope)
        elif action=='resume':
            continue_operation(server,scope)
        elif action!='status':
            raise ValueError('Use the current production action.')
        return enrich_native_view(server, scope, J.view(scope))
    except Exception as exc:
        import sys, traceback
        trace = traceback.format_exc()
        print(f'STUDIO JOURNEY ERROR [{request_id}] {action}: {type(exc).__name__}: {exc}\n{trace}', file=sys.stderr, flush=True)
        component=str(scope.get('unit') or scope.get('shot') or 'production journey')
        operation='journey.refresh' if action=='status' else f'journey.{action}'
        return {'ok':False, 'error': {
            'trace': trace[-6000:],
            'errorCode':'STUDIO_JOURNEY_PROJECTION_ERROR' if action=='status' else 'STUDIO_JOURNEY_ERROR',
            'stage':'journey', 'operation':operation, 'component':component,
            'humanMessage':'Studio could not load the current production review.' if action=='status' else 'Studio could not complete this production step.',
            'technicalMessage':f'{type(exc).__name__}: {exc}',
            'correlationId':request_id, 'requestId':request_id}}
