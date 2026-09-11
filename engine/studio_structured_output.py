"""Strict OpenAI wire schema without deleting extensible production state.

Open maps/Any values travel in an explicit JSON capsule and are decoded before
the original Pydantic model validates them. The stored production schema is unchanged.
"""
from copy import deepcopy
import json

CAPSULE = '__studio_json_value'


def format_for(model):
    from openai.lib._parsing._responses import type_to_text_format_param
    format = deepcopy(type_to_text_format_param(model))

    def visit(node):
        if not isinstance(node, dict):
            return node
        # SDK strict conversion does not support arbitrary maps. Closing those
        # maps would silently lose lifecycle/cinematography values.
        open_map = node.get('type') == 'object' and not node.get('properties') and node.get('additionalProperties') is not False
        any_value = not any(k in node for k in ('type','$ref','anyOf','oneOf','enum','const'))
        if open_map or any_value:
            return {'type':'object', 'properties':{CAPSULE:{'type':'string',
                'description':'JSON-encoded object preserving all authored keys and values.' if open_map else 'JSON-encoded value; preserve its type and contents.'}},
                'required':[CAPSULE], 'additionalProperties':False,
                'description':node.get('description','Extensible production data')}
        out=deepcopy(node)
        if out.get('type')=='object':
            out['additionalProperties']=False
        for key in ('properties','$defs'):
            if key in out:
                out[key]={k:visit(v) for k,v in out[key].items()}
        for key in ('items',):
            if key in out: out[key]=visit(out[key])
        for key in ('anyOf','oneOf','allOf'):
            if key in out: out[key]=[visit(v) for v in out[key]]
        return out

    # Walk the schema, not the format metadata or property-name dictionaries.
    format['schema']=visit(format['schema'])
    return format


def decode(value):
    if isinstance(value,list):
        return [decode(v) for v in value]
    if isinstance(value,dict):
        if set(value)=={CAPSULE}:
            # Do not recursively interpret user keys inside the capsule.
            return json.loads(value[CAPSULE])
        return {k:decode(v) for k,v in value.items()}
    return value


def parse(model, text):
    return model.model_validate(decode(json.loads(text)))
