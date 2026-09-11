"""Candidate approval must survive the SEE anchor layout's duplicate-image hiding."""
import subprocess
from pathlib import Path

APP = (Path(__file__).parent / 'app.html').read_text()


def test_see_candidates_keep_individual_approval_controls_with_anchor():
    source = APP[APP.index('function keyframeRevisionInfo('):APP.index('function shotLandingText(')]
    script = source + r'''
const assert=require('node:assert/strict');
const _esc=String, BASE='', MEDIA_V='test';
const html=keyframeCandidateReviewMedia([
 {candidateId:'A',candidateNumber:1,url:'/a.png',providerLabel:'Seedream'},
 {candidateId:'B',candidateNumber:2,url:'/b.png',providerLabel:'Nano Banana'}
],{}, {shotId:'S2.SH1'},'READY TO REVIEW');
assert.match(html,/class="kf-current kf-candidate-review"/);
assert.match(html,/shRun\('approve-keyframe','S2.SH1',\{candidate:'A'\}\)/);
assert.match(html,/shRun\('approve-keyframe','S2.SH1',\{candidate:'B'\}\)/);
assert.match(html,/Approve Candidate 1/);
assert.match(html,/Approve Candidate 2/);
assert.match(html,/openKeyframeRetake\('S2.SH1','A'\)/);
assert.match(html,/openKeyframeRetake\('S2.SH1','B'\)/);
'''
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert '.see-supporting.has-anchor-keyframe>.kf-current:not(.kf-candidate-review){display:none}' in APP
    assert '.see-supporting.has-anchor-keyframe>.kf-current{display:none}' not in APP


def test_first_approval_click_continues_after_loading_review():
    block=APP[APP.index('async function shRun('):APP.index('  let correction=opts.correction')]
    assert 'await openDirectorAgent(scope);' in block
    assert "return sendDirectorMessage(" in block
    assert "Review is loaded. Check the current version" not in block
    assert "showToast('Recording approval…',true)" in block


def test_retake_requires_reason_and_success_before_normal_preparation():
    block=APP[APP.index('function openKeyframeRetake('):APP.index('function directorStartRejection(')]
    assert "if(!correction)return" in block
    assert "job.status!=='done'" in block
    assert "prepareDirectionThen('cinematography'" in block
    assert "openDisclosureModal('keyframe'" in block
    assert "shRun('build-keyframe'" not in block
