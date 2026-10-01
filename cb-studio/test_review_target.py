"""Execute the real browser helper to verify polling-safe review identity."""
import pathlib
import shutil
import subprocess

import pytest


def test_refresh_keeps_review_but_new_media_or_candidate_invalidates_it():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required to execute the browser review helper")
    js = pathlib.Path(__file__).with_name("director.js").read_text()
    start = js.index("  function reviewTargetSignature(")
    end = js.index("  async function submitAction(", start)
    helper = js[start:end]
    program = helper + """
      const assert = require('node:assert/strict');
      const session = {episode:'Ep1',scene:'1',selectedShotId:'SH1',phase:'voice',
                       artifact:{url:'/voice-v1.wav'},progress:{complete:1}};
      const refreshed = JSON.parse(JSON.stringify(session));
      refreshed.progress.complete = 2;
      assert.equal(reviewTargetSignature(session, 'A'), reviewTargetSignature(refreshed, 'A'));
      assert.notEqual(reviewTargetSignature(session, 'A'), reviewTargetSignature(refreshed, 'B'));
      refreshed.artifact.url = '/voice-v2.wav';
      assert.notEqual(reviewTargetSignature(session, 'A'), reviewTargetSignature(refreshed, 'A'));
      assert.notEqual(reviewTargetSignature(session, 'A'), reviewTargetSignature(null, 'A'));
    """
    subprocess.run([node, "-e", program], check=True, capture_output=True, text=True)
