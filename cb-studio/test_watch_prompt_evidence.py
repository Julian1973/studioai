"""Execute the real WATCH renderer: drafts cannot impersonate generation receipts."""
import json
import re
import subprocess
from pathlib import Path

import pytest


APP = (Path(__file__).parent / 'app.html').read_text()
SOURCE = APP[APP.index('function watchPreparedPrompt('):APP.index('function watchRevisionHistoryHTML(')]


def run_js(assertions):
    harness = r'''
const assert = require('node:assert/strict');
const _esc = text => String(text).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
const shot = {shotId:'S1.SH2',seedancePrompt:'OLD PACKAGE PROSE'};
const led = {workingSeedancePrompt:{text:'OLD OVERRIDE'},departmentWork:{animation:{
  candidate:{output:{providerPrompt:'NEW UNSUBMITTED DIRECTION'}},
  approved:{output:{providerPrompt:'EARLIER DIRECTION'}}}}};
const scope = {episode:'Ep3',scene:'1'};
const data = {episode:'Ep3',scene:'1',shotId:'S1.SH2',artifactType:'animation',selectedCandidateId:'C1',
  assets:[{candidateId:'C1',label:'Candidate C1',promptAttributionExact:true,promptHash:'hash-1'}],
  promptContract:{prompt:'ACTUAL SEALED TEXT',promptHash:'hash-1',batchId:'batch-5',
    attributionExact:true,analysisAppliesToRender:true}};
'''
    result = subprocess.run(['node', '-e', SOURCE + harness + assertions], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr


def test_render_prompt_and_next_direction_remain_distinct():
    run_js('''
const evidence = watchPromptEvidence(shot,led,{},data,scope);
assert.equal(evidence.recorded.text,'ACTUAL SEALED TEXT');
assert.equal(evidence.prepared,'NEW UNSUBMITTED DIRECTION');
assert.match(evidence.recorded.detail,/C1.*batch-5.*hash-1/);
const html=watchPromptEvidenceContent(evidence);
assert.match(html,/Recorded generation prompt/);
assert.match(html,/not a submitted request/);
assert(!html.includes('OLD OVERRIDE')&&!html.includes('OLD PACKAGE PROSE'));
''')


@pytest.mark.parametrize('change', [
    "data.promptContract.attributionExact=false;",
    "data.promptContract.analysisAppliesToRender=false;",
    "data.assets[0].promptAttributionExact=false;",
    "data.assets[0].promptHash='different-prompt';",
    "data.selectedCandidateId='missing';",
    "data.episode='Ep2';",
    "data.scene='2';",
    "data.shotId='S1.SH1';",
    "data.artifactType='keyframe';",
    "data.error='unavailable';",
])
def test_incomplete_or_different_take_binding_cannot_claim_a_sent_prompt(change):
    run_js(change + '''
const evidence=watchPromptEvidence(shot,led,{},data,scope);
assert.equal(evidence.recorded,null);
assert(!watchPromptEvidenceContent(evidence).includes('ACTUAL SEALED TEXT'));
assert.equal(evidence.prepared,'NEW UNSUBMITTED DIRECTION');
''')


def test_pending_edit_does_not_inherit_original_take_prompt():
    run_js('''
const evidence=watchPromptEvidence(shot,led,{edit:{status:'candidate-pending',candidateUrl:'/edit.mp4'}},data,scope);
assert.equal(evidence.recorded,null);
assert.match(evidence.message,/pending edit/);
''')


def test_no_legacy_fallback_without_specialist_or_receipt():
    run_js('''
delete led.departmentWork;
const evidence=watchPromptEvidence(shot,led,{},null,scope);
assert.equal(evidence.prepared,'');
assert.equal(evidence.recorded,null);
assert(!watchPromptEvidenceContent(evidence).includes('OLD'));
''')


def test_multisegment_payload_is_not_replaced_by_one_draft_or_first_segment():
    run_js('''
data.promptContract.prompt='Part 1: ACTUAL\nPart 2: ALSO ACTUAL';
assert.equal(watchPromptEvidence(shot,led,{},data,scope).recorded.text,data.promptContract.prompt);
'''.replace("'Part 1: ACTUAL\nPart 2: ALSO ACTUAL'", json.dumps('Part 1: ACTUAL\nPart 2: ALSO ACTUAL')))


def test_evidence_refresh_updates_panels_without_resetting_video():
    run_js('''
const panels=[{dataset:{watchPromptEvidence:'S1.SH2'},innerHTML:''},
  {dataset:{watchPromptEvidence:'S1.SH1'},innerHTML:'KEEP'}];
let PSTAGE='animation',PSHOT_I=0,SH_EP='Ep3',SH_SC='1';
const pShots=()=>[shot],shTok=x=>x,shLedger=()=>led,shMedia=()=>({});
const plCacheKey=()=> 'scope',SH_PROMPTLAB_CACHE={scope:data};
const document={querySelectorAll:selector=>{assert.equal(selector,'[data-watch-prompt-evidence]');return panels;}};
refreshWatchPromptEvidence('S1.SH2');
assert.match(panels[0].innerHTML,/ACTUAL SEALED TEXT/);
assert.equal(panels[1].innerHTML,'KEEP');
panels[0].innerHTML='UNCHANGED';
refreshWatchPromptEvidence('S1.SH1');
assert.equal(panels[0].innerHTML,'UNCHANGED');
''')


def test_actual_watch_surface_uses_shared_evidence_and_script_parses():
    scene = APP[APP.index('function watchSceneIntentHTML('):APP.index('function shotDialogueWindow(')]
    assert 'watchPromptEvidencePanel(shot,led,media)' in scene
    assert 'Full provider prompt' not in scene
    stage = APP[APP.index('function renderShotStage('):APP.index('const acceptedReview=')]
    assert 'const currentPrompt=watchPreparedPrompt(led);' in stage
    assert 'const currentPrompt=((led.workingSeedancePrompt' not in stage
    assert 'mode==="animation"?null:s.seedancePrompt' in APP
    assert 'watchPromptEvidencePanel(s,led,m)' in APP
    update = APP[APP.index('function plRenderOnly('):APP.index('async function shLoadPromptLab(')]
    assert 'refreshWatchPromptEvidence(tok)' in update
    script = '\n'.join(re.findall(r'<script>(.*?)</script>', APP, re.S))
    result = subprocess.run(['node','--check','-'], input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
