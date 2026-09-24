from copy import deepcopy
import pytest
from studio_keyframe_selection import can_reuse_prompt_change


@pytest.mark.parametrize('change,hash_value,screen,allowed', [
    ({'briefHash': 'new'}, 'image', 'pass', True),
    ({'briefHash': 'new', 'cardHash': 'changed'}, 'image', 'pass', False),
    ({'briefHash': 'new', 'referenceHashes': {'Sunny': 'changed'}}, 'image', 'pass', False),
    ({'briefHash': 'new'}, 'changed', 'pass', False),
    ({'briefHash': 'new'}, None, 'pass', False),
    ({'briefHash': 'new'}, 'image', 'fail', False),
    ({}, 'image', 'pass', False),
])
def test_reuse_is_only_intact_screened_prompt_only_change(change, hash_value, screen, allowed):
    signature = {'briefHash': 'old', 'cardHash': 'same', 'referenceHashes': {'Sunny': 'same'}}
    candidate = {'source': 'generated', 'inputSignature': signature, 'contentHash': 'image',
                 'conformanceScreening': {'status': screen}}
    before = deepcopy(candidate)
    assert can_reuse_prompt_change(candidate, {**signature, **change}, hash_value) is allowed
    assert candidate == before


def test_explicit_reuse_preserves_generation_record_and_uses_normal_approval(monkeypatch, tmp_path):
    import ast
    from pathlib import Path
    from types import SimpleNamespace
    signature = {'briefHash': 'old', 'cardHash': 'same'}
    candidate = {'source': 'generated', 'path': str(tmp_path / 'image.png'),
                 'inputSignature': signature, 'contentHash': 'image',
                 'conformanceScreening': {'status': 'pass'}}
    ledger = {'keyframeCandidate': candidate}
    saved = []
    def signature_for(pkg, shot, record, *args):
        return ({'briefHash': 'new', 'cardHash': 'same'} if record['source'] == 'generated'
                else {'selectedAssetHash': 'image', 'source': 'library'})
    def approve(*args):
        ledger['keyframeApproval'] = deepcopy(ledger['keyframeCandidate'])
        ledger['keyframeCandidate'] = None
        return 'approved-image'
    module = SimpleNamespace(
        _shot=lambda *a: {}, _ledger=lambda *a: ledger,
        _load_opening_composition_master=lambda *a: None, _characters_cfg=lambda: {},
        _now=lambda: 'now', Refused=ValueError,
        _signature_diff=lambda a, b: [k for k in set(a) | set(b) if a.get(k) != b.get(k)],
        _save=lambda *a: saved.append(deepcopy(ledger)), load_pkg=lambda *a: ({}, 'pkg'))
    tree = ast.parse(Path(__file__).with_name('cb_safety.py').read_text())
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'approve_keyframe')
    ns = dict(m=module, current_package=lambda *a: ({}, 'pkg'),
              keyframe_signature=signature_for, file_sha256=lambda *a: 'image',
              original={'approve_keyframe': approve})
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'approval-policy', 'exec'), ns)
    with pytest.raises(ValueError, match='inputs changed'):
        ns['approve_keyframe']('3', 'S3.SH1')
    assert not saved and candidate['source'] == 'generated'
    assert ns['approve_keyframe']('3', 'S3.SH1', reuse_prompt_change=True) == 'approved-image'
    assert ledger['keyframeHistory'][0]['inputSignature'] == signature
    assert ledger['keyframeHistory'][0]['source'] == 'generated'
    assert ledger['keyframeApproval']['source'] == 'library'
    assert ledger['keyframeApproval']['inputSignature']['selectedAssetHash'] == 'image'
