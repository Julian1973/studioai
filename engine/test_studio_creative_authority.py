import pytest
from studio_creative_authority import resolve, compile_instructions
from studio_delivery_contract import delivery_snapshot


def instruction(id, kind, value, **scope):
    return dict(id=id, kind=kind, value=value, decisionKey='listener-performance',
                text=value, source='current director', scope=scope)


def test_directed_reaction_beats_default_and_residue_in_own_scope():
    rows = [instruction('default','default_behaviour','Hold still'),
            instruction('reaction','creative_direction','Laugh naturally',stage='watch'),
            instruction('old','historic_residue','Freeze')]
    report = resolve(rows, {'stage':'watch'})
    assert report['ready']
    assert {r['id']: r['resolution'] for r in report['instructions']} == {
        'default':'superseded','reaction':'emitted','old':'removed-residue'}
    assert resolve(rows, {'stage':'see'})['instructions'][1]['resolution'] == 'out-of-scope'


def test_hard_conflict_is_not_silently_suppressed():
    rows = [instruction('audio','hard_truth','Preserve approved spoken performance'),
            instruction('new','creative_direction','Replace approved spoken performance')]
    assert not resolve(rows,{})['ready']
    with pytest.raises(ValueError, match='conflicts with approved'):
        compile_instructions('Original', {'directorCard': {'instructions':rows}}, 'watch')


def test_snapshot_has_unknown_actual_cost_and_no_approval():
    a = delivery_snapshot({'estimatedCost':1.2}, {'acting':'wait'}, 'wait', {'prompt':'wait'})
    b = delivery_snapshot({'estimatedCost':1.2}, {'acting':'move'}, 'move', {'prompt':'move'})
    assert a['cost']['actual'] is None
    assert a['approvalStatus'] == 'not-granted-by-compilation'
    assert a['fingerprint'] != b['fingerprint']
