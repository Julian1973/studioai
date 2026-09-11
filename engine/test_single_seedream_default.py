import ast
from pathlib import Path
import cb_render as R

def test_all_native_keyframe_entrypoints_default_to_single_candidate():
    for filename,names in [('cb_render.py',{'build_keyframe','keyframe_shot','keyframe_build_status'}),('cb_safety.py',{'keyframe_shot'})]:
        tree=ast.parse(Path(__file__).with_name(filename).read_text())
        found=set()
        for node in ast.walk(tree):
            if isinstance(node,ast.FunctionDef) and node.name in names:
                pairs=dict(zip([a.arg for a in node.args.kwonlyargs],node.args.kw_defaults))
                assert isinstance(pairs['compare'],ast.Constant) and pairs['compare'].value is False
                found.add(node.name)
        assert found==names

def test_displayed_build_cost_and_provider_match_single_default(monkeypatch):
    monkeypatch.setattr(R,'load_pkg',lambda *a:({'shots':[{'shotId':'X'}]},None))
    monkeypatch.setattr(R,'_shot',lambda *a:{'shotId':'X'})
    monkeypatch.setattr(R,'_ledger',lambda *a:{})
    monkeypatch.setattr(R,'_shot_uses_own_keyframe',lambda *a:True)
    monkeypatch.setattr(R,'_expanded_reference_blueprint',lambda *a,**k:[])
    import cb_costs
    monkeypatch.setattr(cb_costs,'estimate_image_cost',lambda **k:.1 if k['provider']=='seedream5pro' else .2)
    status=R.keyframe_build_status('1','X')
    assert status['maxMediaCalls']==status['finishingCallsRequired']==1
    assert status['estimatedMaxUsd']==.1 and status['provider']=='byteplus'
    assert list(status['providerModelId'])==['A']
    comparison=R.keyframe_build_status('1','X',compare=True)
    assert comparison['maxMediaCalls']==2 and comparison['estimatedMaxUsd']==.3
