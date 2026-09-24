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
const SH_SEEDANCE_CACHE={'S1.SH2':{currentPrompt:'NEW UNSUBMITTED DIRECTION'}};
const shTok=x=>x;
const led = {shotId:'S1.SH2',workingSeedancePrompt:{text:'OLD OVERRIDE'},departmentWork:{animation:{
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
delete SH_SEEDANCE_CACHE['S1.SH2'];
const evidence=watchPromptEvidence(shot,led,{},null,scope);
assert.equal(evidence.prepared,'');
assert.equal(evidence.recorded,null);
assert(!watchPromptEvidenceContent(evidence).includes('OLD'));
''')


@pytest.mark.parametrize('status', ["{loading:true}", "{error:'DIRECT required',currentPrompt:'STALE'}"])
def test_unavailable_compilation_never_displays_stale_department_prompt(status):
    run_js("SH_SEEDANCE_CACHE['S1.SH2']=" + status + ";assert.equal(watchPreparedPrompt(led),'');")


def test_watch_routes_to_review_and_confirmation_uses_only_sealed_inputs():
    assert "window.StudioJourney && stage==='storyboard'" in APP
    assert 'aria-label="WATCH preflight review"' in APP
    assert "pFocusedStage()===\"animation\"" in APP
    strip = APP[APP.index('function fireReferenceStripHTML('):APP.index('function openTimingReviewModal(')]
    assert 'SH_REFERENCE_CACHE' not in strip
    assert 'watchPreparedPrompt(led)' not in strip
    assert 'executionPlan' in strip
    assert 'aria-label="Sealed Audio1"' in strip
    assert 'Fire candidates' in strip
    intent = APP[APP.index('function watchSceneIntentHTML('):APP.index('function watchProductionSurfaceHTML(')]
    assert 'shot.directorCard' in intent
    assert 'voice.approvedLines' in intent
    assert 'departmentWork' not in intent


def test_advisory_conflict_opens_existing_fire_review_without_repreparing():
    source=APP[APP.index('function watchCraftNotesHTML('):APP.index('function shCompareRender(')]
    script=r'''
const assert=require('node:assert/strict');
const _esc=s=>String(s).replaceAll('<','&lt;').replaceAll('>','&gt;');
const quality={assessment:{critical_issues:['Droop overlaps dialogue.','<unsafe>']}};
let opened=0;
const shLedger=()=>({pendingSpendAuth:{token:'existing',envelope:{executionPlan:{segments:[{promptQuality:quality}]}}}});
const openAnimationConfirmModal=()=>{opened++;};
const showStageWorking=()=>{throw Error('Must not prepare again for creative advice');};
(async()=>{
  await shRender('S3.SH2');
  assert.equal(opened,1);
  const html=watchCraftNotesHTML(quality);
  assert(html.includes('Droop overlaps dialogue.'));
  assert(html.includes('&lt;unsafe&gt;'));
  assert(!html.includes('<unsafe>'));
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
    result=subprocess.run(['node','-e',source+script],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr


def test_watch_operation_uses_latest_state_and_preserves_real_failures():
    source=APP[APP.index('function watchProductionOperation('):APP.index('async function resumeProductionOperation(')]
    script=r'''
const assert=require('node:assert/strict');
const SH_EP='Ep4',SH_SC='3';
const pShots=()=>[{shotId:'S3.SH2'}];
let ledgerStatus='designed';
const shLedger=()=>({status:ledgerStatus});
const op=(createdAt,state,message)=>({shotId:'S3.SH2',episode:'Ep4',scene:'3',createdAt,state,message});
let PJOBS={old:{operation:op(1,'needs-attention','Missing audio')},
 current:{operation:op(2,'needs-attention','WATCH_PROMPT_REVIEW_REQUIRED: unresolved critical conflicts: pacing')}};
assert.equal(watchProductionOperation('S3.SH2'),null);
PJOBS.current.operation.state='reconciling-submission';
assert.equal(watchProductionOperation('S3.SH2'),PJOBS.current.operation);
for(const message of ['SOURCE_DIALOGUE_SEGMENTATION_UNRESOLVED: source payload changed',
 'WATCH_CONFIGURATION_REQUIRED: selected SEE assets do not have a current package approval',
 'WATCH_PROMPT_REVIEW_REQUIRED: prompt evidence changed']){
 PJOBS.current.operation=op(3,'needs-attention',message);
 assert.equal(watchProductionOperation('S3.SH2').message,message);
}
PJOBS.current.operation=op(4,'complete','Returned candidate');
assert.equal(watchProductionOperation('S3.SH2').state,'complete');
 PJOBS.current.operation=op(5,'needs-attention',"REFUSED — S3.SH2 has a candidate batch pending Julian's review");
 assert.equal(watchProductionOperation('S3.SH2'),null);
 ledgerStatus='candidates-pending';
 assert.equal(watchProductionOperation('S3.SH2'),PJOBS.current.operation);
PJOBS.current.operation.state='reconciling-submission';
assert.equal(watchProductionOperation('S3.SH2'),PJOBS.current.operation);
'''
    result=subprocess.run(['node','-e',source+script],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr


def test_confirmation_images_follow_sealed_order_not_reference_cache():
    source = APP[APP.index('function fireReferenceStripHTML('):APP.index('function openAnimationConfirmModal(')]
    script = """
const assert=require('node:assert/strict'),BASE='',MEDIA_V=1;
const _esc=x=>String(x),refSlotLabel=x=>x,fireReferencePathUrl=x=>x;
const SH_REFERENCE_CACHE={stale:{animation:{references:[{url:'/wrong.png'}]}}};
const html=fireReferenceStripHTML('S3.SH1',{envelope:{references:[
 {slot:'@Image1',path:'/opening.png'}, {slot:'@Image2',path:'/sunny.png'}]}});
assert(html.indexOf('/opening.png')<html.indexOf('/sunny.png'));
assert(!html.includes('/wrong.png'));
assert(!fireReferenceStripHTML('S3.SH1',{}).includes('/wrong.png'));
"""
    result=subprocess.run(['node','-e',source+script],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_action_review_compares_current_card_and_compiled_action_with_clean_words():
    source=APP[APP.index('function watchSceneIntentHTML('):APP.index('function watchProductionSurfaceHTML(')]
    script="""
const assert=require('node:assert/strict');
const _esc=x=>String(x),shTok=x=>x,watchPromptEvidencePanel=()=>'',watchProductionRecordHTML=()=>'';
const SH_VOICE_CACHE={S3:{approvedLines:[{speaker:'Sunny',exactText:'Good luck?'}]}};
const html=watchSceneIntentHTML({}, {shotId:'S3',durationSec:18,purpose:'Denial',
 dialogueLines:[{exactText:'STALE stage action'}],directorCard:{views:[
 {viewId:'V1',timing:'0–4s',action:'Lift the cup',cameraPurpose:'Reveal hesitation',performance:'Force a smile'}]}},
 '[TIMED ACTION]\\n0–4s: Lift the cup; force a smile.\\n[REFERENCE AUTHORITY]\\nKeep identity');
assert(html.includes('Lift the cup; force a smile.'));
assert(html.includes('Reveal hesitation'));
assert(html.includes('Good luck?'));
assert(!html.includes('STALE stage action'));
"""
    result=subprocess.run(['node','-e',source+script],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


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
const pShots=()=>[shot],shLedger=()=>led,shMedia=()=>({});
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
