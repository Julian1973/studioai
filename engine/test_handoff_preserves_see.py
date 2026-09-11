from copy import deepcopy
from types import SimpleNamespace
from studio_director_handoff import persist


def test_derived_handoff_preserves_current_see_but_not_stale_or_changed_references():
    for initially_current, changed_references in [(True, False), (False, False), (True, True)]:
        record = {'inputSignature': {'shotContractHash': 'before', 'references': 'same'},
                  'output': {'opening': 'approved composition'}}
        original = deepcopy(record)
        count = 0
        def status(*args):
            nonlocal count
            count += 1
            return {'current': initially_current if count == 1 else False,
                    'record': record,
                    'expectedInputSignature': {'shotContractHash': 'after',
                        'references': 'changed' if changed_references else 'same'}}
        runtime = SimpleNamespace(_department_record_status=status,
            _signature_diff=lambda a,b: [k for k in set(a)|set(b) if a.get(k)!=b.get(k)],
            _sha256_file=lambda _: 'opening-hash', _save=lambda *args: None)
        shot = {'shotId':'X.SH1', 'referenceSlots':{'@img1':'opening frame'}}
        persist(runtime, {'sceneNumber':1,'episode':'E'}, None, shot, {},
                {'directorCard':{'states':'new'},'directorCardSource':{'kind':'derived'}},
                {}, {}, 'opening.png', {'openingObservedStates':{},'observationLimitations':[]})
        if initially_current and not changed_references:
            assert record['inputSignature']['shotContractHash'] == 'after'
            assert record['output'] == original['output']
            assert record['derivedHandoffCarryForward'][0]['beforeInputSignature'] == original['inputSignature']
        else:
            assert record == original
