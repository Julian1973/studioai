"""Run the local Studio workflow regressions with synthetic provider fixtures.

Usage: python3 tools/check_studio_workflow.py
This qualifies software behavior, not live provider availability or rendered quality.
"""
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
TESTS = (
    'engine/test_cb_audio_timing.py',
    'engine/test_cb_safety_voice_equivalence.py',
    'engine/test_watch_handoff_preparation.py',
    'engine/test_watch_source_integrity.py',
    'engine/test_studio_prompt_quality.py',
    'engine/test_studio_seedance_execution.py',
    'engine/test_cb_render_generation_safety.py',
    'cb-studio/test_watch_prompt_evidence.py',
    'cb-studio/test_journey_native_controls.py',
    'cb-studio/test_production_recovery.py',
    'cb-studio/test_watch_input_acceptance.py',
    'cb-studio/test_approval_completion_boundary.py',
)


if __name__ == '__main__':
    environment = dict(os.environ)
    environment['PYTHONPATH'] = os.pathsep.join(
        [str(ROOT / 'engine'), str(ROOT / 'cb-studio'),
         *filter(None, [environment.get('PYTHONPATH')])])
    raise SystemExit(subprocess.call(
        [sys.executable, '-m', 'pytest', '-q', '--tb=short', *TESTS],
        cwd=ROOT, env=environment))
