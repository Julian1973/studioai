import json
import pytest
from pydantic import BaseModel, Field
from studio_structured_output import format_for, parse, CAPSULE


class Flexible(BaseModel):
    state: dict = Field(default_factory=dict)
    values: dict[str, int]
    text: str


def assert_strict(node):
    if isinstance(node,dict):
        if node.get('type')=='object':
            assert node.get('additionalProperties') is False
            assert set(node.get('required',[]))==set(node.get('properties',{}))
        for v in node.values(): assert_strict(v)
    elif isinstance(node,list):
        for v in node: assert_strict(v)


def test_real_creative_schemas_are_accepted_shape_without_erasing_open_state():
    from cb_creative import PlannedSceneDirection
    from studio_transport import DirectedEpisodePlan, AgentReply
    for model in (PlannedSceneDirection,DirectedEpisodePlan,AgentReply):
        wire=format_for(model)
        assert_strict(wire['schema'])
        assert wire['strict'] is True
    state=format_for(PlannedSceneDirection)['schema']['$defs']['CoverageView']['properties']['stateAtEntry']
    assert CAPSULE in state['properties']


def test_canonical_state_roundtrip_and_original_type_validation():
    state={'object:H01':{'support':None,'owner':'Keen','count':1},'camera':{'lens':'wide'}}
    wire={'state':{CAPSULE:json.dumps(state)},'values':{CAPSULE:'{"count":1}'},'text':'Exact words.'}
    result=parse(Flexible,json.dumps(wire))
    assert result.state==state and result.values=={'count':1} and result.text=='Exact words.'
    wire['values']={CAPSULE:'{"count":"not an integer"}'}
    with pytest.raises(ValueError): parse(Flexible,json.dumps(wire))


def test_existing_cached_plain_output_remains_readable():
    assert parse(Flexible,'{"state":{},"values":{"count":2},"text":"Hi"}').values=={'count':2}
