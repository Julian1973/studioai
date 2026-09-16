"""Routes inside the existing authenticated Studio server."""
from studio_journey import Journey, StudioStore, DecisionRequired, scope_key
from pathlib import Path
import threading
import time
import uuid

_ACTIVE=set()
_LOCK=threading.Lock()


def controller(server, scope):
    from studio_workspace import Workspace
    workspace=Workspace(server.ROOT)
    context=workspace.context(scope['projectId'],scope['episode'])
    if context.get('legacy'):
        from studio_journey_native import Native
        adapter=Native(server.ROOT,server)
    else:
        from studio_journey_project import Project
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


def request(server,data):
    scope=data.get('scope') or {}
    action=data.get('command','status')
    request_id=str(data.get('requestId') or ('journey_'+uuid.uuid4().hex[:12]))
    try:
        scope_key(scope)
        J=controller(server,scope)
        if action=='decide':
            J.accept(scope,data,str(data.get('by') or 'Producer'))
            continue_operation(server,scope)
        elif action=='recover':
            J.recover(scope)
            continue_operation(server,scope)
        elif action=='resume':
            continue_operation(server,scope)
        elif action!='status':
            raise ValueError('Use the current production action.')
        return J.view(scope)
    except Exception as exc:
        component=str(scope.get('unit') or scope.get('shot') or 'production journey')
        operation='journey.refresh' if action=='status' else f'journey.{action}'
        return {'ok':False, 'error': {
            'errorCode':'STUDIO_JOURNEY_PROJECTION_ERROR' if action=='status' else 'STUDIO_JOURNEY_ERROR',
            'stage':'journey', 'operation':operation, 'component':component,
            'humanMessage':'Studio could not load the current production review.' if action=='status' else 'Studio could not complete this production step.',
            'technicalMessage':f'{type(exc).__name__}: {exc}',
            'correlationId':request_id, 'requestId':request_id}}
