"""Exercise the real finalizer exception boundary without jobs or providers."""
import ast
from contextlib import nullcontext
from pathlib import Path
import pytest

@pytest.mark.parametrize('gate,expected', [('chat:approve:keyframe','finalizing'),
    ('chat:approve:voice','finalizing'),('chat:approve:render','finalizing'),
    ('storyintake','failed')])
def test_next_preparation_error_does_not_revoke_saved_approval(gate,expected):
    tree=ast.parse(Path(__file__).with_name('serve.py').read_text())
    block=next(n for n in ast.walk(tree) if isinstance(n,ast.Try)
        and any(isinstance(x,ast.Expr) and isinstance(x.value,ast.Call)
                and isinstance(x.value.func,ast.Name) and x.value.func.id=='_finalize_automatic_direction'
                for x in n.body))
    job={'status':'finalizing','gate':gate}
    def fail(*a):raise ValueError('WATCH direction needs repair')
    ns={'job':job,'_JOB_LOCK':nullcontext(),'_finalize_automatic_direction':fail}
    exec(compile(ast.Module(body=[block],type_ignores=[]),'completion','exec'),ns)
    assert job['status']==expected
    if expected=='finalizing':
        assert 'error' not in job
        assert 'WATCH direction needs repair' in job['nextPreparationError']
    else:assert 'WATCH direction needs repair' in job['error']
