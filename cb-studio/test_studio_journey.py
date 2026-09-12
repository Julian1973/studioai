from contextlib import contextmanager
from copy import deepcopy
import pytest
from studio_journey import Journey, DecisionRequired


class Store:
    def __init__(self): self.rows = {}
    @contextmanager
    def lock(self, key): yield
    def read(self, key): return deepcopy(self.rows.get(key))
    def save(self, key, value): self.rows[key] = deepcopy(value)


class Services:
    """Fake transport; actual Journey executes every operation and decision."""
    def __init__(self, silent=False):
        self.phase, self.version = 'prepare', 1
        self.silent, self.calls, self.receipts = silent, [], {}
        self.image, self.audio = 'approved-image-bytes', 'approved-audio-bytes'
        self.material = False
        self.dependency = False
    def snapshot(self, scope):
        return dict(phase='dependency' if self.dependency else self.phase,
                    binding=str(self.version), requiresAudio=not self.silent,
                    review={'image':self.image,'audio':self.audio,'revision':self.version},
                    preserved=['approved image','approved audio'],
                    disclosure={'limitUsd':2,'operations':[self.phase]})
    def execute(self, scope, step, op):
        if step == 'align_timing' and self.material:
            raise DecisionRequired('The action needs more time.', 'Review the proposed timing change.', ['approved image','approved voice'])
        self.calls.append(step)
        assert op['grant']['limitUsd'] == 2
        receipt = {'status':'complete','origin':op['reviewedBinding']}
        if step == 'prepare_plan': self.phase='plan'
        if step == 'review_images': self.phase='images'
        if step == 'review_audio': self.phase='audio'
        if step == 'review_film': self.phase='film'
        if step == 'prepare_next': self.phase='complete'
        if step == 'submit_render':
            receipt['requestHash']='exact-reviewed-and-submitted-request'
        self.receipts[(op['id'],step)] = receipt
        return receipt
    def reconcile(self, scope, step, op):
        return self.receipts.get((op['id'],step),{'status':'pending','message':'Reconciling existing job'})


SCOPE = dict(projectId='test',episode='Ep1',scene='1',unit='S1.SH1')

def click(journey, scope=SCOPE, n=1):
    v=journey.view(scope)
    return journey.accept(scope, dict(commandId='command_'+str(n), action=v['phase'],
                                      binding=v['binding'],expectedRevision=v['revision']), 'Producer')

def finish(journey, scope=SCOPE):
    for _ in range(12):
        journey.tick(scope)
        if not journey.view(scope)['busy']:return
    raise AssertionError('Operation did not terminate')


@pytest.mark.parametrize('scene',['1','2'])
def test_five_actions_for_different_scenes(scene):
    scope={**SCOPE,'scene':scene,'unit':f'S{scene}.SH1'}
    s=Services();j=Journey(Store(),s)
    for n in range(1,6):click(j,scope,n);finish(j,scope)
    assert j.view(scope)['phase']=='complete'
    assert j.view(scope)['normalActionCount']==5
    assert s.calls.count('submit_render')==1
    assert s.calls.index('approve_audio') < s.calls.index('submit_render')


def test_silent_unit_uses_four_actions_and_no_voice_generation():
    s=Services(True);j=Journey(Store(),s)
    for n in range(1,5):click(j,n=n);finish(j)
    assert j.view(SCOPE)['phase']=='complete'
    assert 'create_audio' not in s.calls and 'approve_audio' not in s.calls


def test_stale_review_cannot_approve():
    s=Services();j=Journey(Store(),s);v=j.view(SCOPE);s.version+=1
    with pytest.raises(DecisionRequired):
        j.accept(SCOPE,dict(commandId='command_stale',action='prepare',binding=v['binding'],expectedRevision=0),'Producer')
    assert not s.calls


def test_double_click_and_reload_use_same_operation():
    store=Store();s=Services();j=Journey(store,s)
    a=click(j);b=click(j)
    assert a==b
    j.tick(SCOPE)
    j=Journey(store,s);finish(j)
    assert s.calls.count('prepare_plan')==1
    assert j.view(SCOPE)['normalActionCount']==1


def test_interruption_after_dispatch_reconciles_without_resubmit():
    store=Store();s=Services();j=Journey(store,s);click(j)
    key=next(iter(store.rows));op=store.rows[key]['operation']
    op.update(status='running',pending='prepare_plan')
    s.execute(SCOPE,'prepare_plan',op)
    j=Journey(store,s);finish(j)
    assert s.calls==['prepare_plan']


def test_material_timing_change_stops_before_render():
    s=Services();j=Journey(Store(),s)
    for n in range(1,4):click(j,n=n);finish(j)
    s.material=True;click(j,n=4);finish(j)
    assert j.view(SCOPE)['operation']['status']=='needs-decision'
    assert 'submit_render' not in s.calls
    assert s.image=='approved-image-bytes' and s.audio=='approved-audio-bytes'


def test_unapproved_dependency_has_no_primary_action():
    s=Services();s.dependency=True;j=Journey(Store(),s)
    assert j.view(SCOPE)['primary'] is None
    with pytest.raises(DecisionRequired):click(j)


def test_disclosure_change_invalidates_decision():
    s=Services();j=Journey(Store(),s);v=j.view(SCOPE)
    original=s.snapshot
    s.snapshot=lambda scope:{**original(scope),'disclosure':{'limitUsd':3,'operations':['prepare']}}
    with pytest.raises(DecisionRequired):
        j.accept(SCOPE,dict(commandId='command_cost',action='prepare',binding=v['binding'],expectedRevision=0),'Producer')


def test_changed_authoritative_correction_can_resume_without_losing_media():
    s=Services();j=Journey(Store(),s)
    for n in range(1,4):click(j,n=n);finish(j)
    s.material=True;click(j,n=4);finish(j)
    assert j.view(SCOPE)['primary'] is None
    # A reviewed correction updates the actual adapter source, never the old prompt.
    s.version+=1;s.material=False
    assert j.view(SCOPE)['corrected'] is True
    click(j,n=5);finish(j)
    assert j.view(SCOPE)['correctionActionCount']==1
    assert j.view(SCOPE)['normalActionCount']==4
    assert s.calls.count('submit_render')==1
    assert s.image=='approved-image-bytes' and s.audio=='approved-audio-bytes'


def test_unknown_submission_is_not_cured_by_a_source_edit():
    s=Services();j=Journey(Store(),s)
    for n in range(1,4):click(j,n=n);finish(j)
    original=s.execute
    def submit(scope,step,op):
        if step=='submit_render':raise DecisionRequired('Submission acceptance is unknown.','Reconcile that request.')
        return original(scope,step,op)
    s.execute=submit;click(j,n=4);finish(j);s.version+=1
    assert j.view(SCOPE)['primary'] is None


def test_failure_projection_cannot_erase_operation_error():
    s=Services();store=Store();j=Journey(store,s);click(j)
    def fail(*a):
        s.snapshot=lambda *a: (_ for _ in ()).throw(RuntimeError('Status unavailable'))
        raise RuntimeError('Missing input file')
    s.execute=fail;j.tick(SCOPE)
    op=next(iter(store.rows.values()))['operation']
    assert op['decision']['issue']=='Missing input file' and op['status']=='needs-decision'


def test_persistence_failure_before_intent_never_dispatches():
    s=Services();store=Store();j=Journey(store,s);click(j)
    store.save=lambda *a: (_ for _ in ()).throw(OSError('Disk unavailable'))
    with pytest.raises(OSError):j.tick(SCOPE)
    assert s.calls==[]


def test_late_result_recovery_reads_receipt_without_second_execution():
    s=Services();store=Store();j=Journey(store,s);click(j)
    original=s.execute
    def unknown(scope,step,op):
        original(scope,step,op)
        raise DecisionRequired('The acknowledgement was lost.','Check saved operation.')
    s.execute=unknown;j.tick(SCOPE)
    assert j.view(SCOPE)['operation']['status']=='needs-decision'
    j=Journey(store,s);j.recover(SCOPE);finish(j)
    assert j.view(SCOPE)['phase']=='plan' and s.calls==['prepare_plan']


def test_progress_is_readable_while_worker_holds_execution_lease(tmp_path):
    from studio_journey import StudioStore,scope_key
    from concurrent.futures import ThreadPoolExecutor
    store=StudioStore(tmp_path);J=Journey(store,Services());click(J)
    with store.lock(scope_key(SCOPE)):
        with ThreadPoolExecutor(max_workers=1) as pool:
            view=pool.submit(J.view,SCOPE).result(timeout=1)
    assert view['busy'] and not view['primary']
    assert J.adapter.calls==[]
