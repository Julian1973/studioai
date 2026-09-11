import json
import subprocess
from pathlib import Path
import pytest

APP = Path(__file__).with_name('app.html').read_text()
FOLLOW = APP[APP.index('async function directorFollowJob('):APP.index('async function sendDirectorMessage(')]

@pytest.mark.parametrize('scenario', ['approved', 'voice-approved', 'failed', 'changed-shot', 'changed-scene', 'request-ready', 'chained'])
def test_chat_continuation_follows_confirmed_job_in_original_scope(scenario):
    harness = r'''
const assert=require('node:assert/strict');
let SH_JOB=null,SH_LAST_JOB=null,SH_POLL_MISSES=0,SH_AFTER_JOB=null;
let SH_EP='Ep3',SH_SC='1',PSHOT_I=0,PJOBS={},page='pipeline';
let DIRECTOR_CHAT_CACHE={},DIRECTOR_CHAT_OPEN_KEY=null,events=[];
const pShots=()=>[{shotId:'S1.SH1'},{shotId:'S1.SH2'}];
const directorChatKey=scope=>scope.stage;
const openDirectorAgent=async scope=>{DIRECTOR_CHAT_OPEN_KEY=scope.stage;events.push(['chat',scope.stage]);};
const directorPollChatJob=()=>{},showToast=()=>{};
const shRememberJob=()=>{},shPollStart=()=>{},renderControl=()=>{};
const openShotOutcome=(stage,index)=>events.push([stage,index]);
const openStageOutcome=stage=>events.push(stage);
const openAnimationConfirmModal=()=>events.push('review-request');
const shLedger=()=>scenario==='request-ready'?{pendingSpendAuth:{token:'test'}}:{};
(async()=>{
  const scope={episode:'Ep3',scene:'1',shotId:'S1.SH1',stage:scenario==='request-ready'?'animation':'keyframe'};
  await directorFollowJob(scope,'key',{jobId:'test',decisionKind:scenario==='request-ready'?null:scenario==='voice-approved'?'voice':'keyframe'});
  if(scenario==='changed-shot')PSHOT_I=1;
  if(scenario==='changed-scene')SH_SC='2';
  if(scenario==='chained')DIRECTOR_CHAT_OPEN_KEY='key';
  await SH_AFTER_JOB({status:scenario==='failed'?'failed':'done',...(scenario==='chained'?{nextOutcomeJobId:'next',nextOutcomeScope:{...scope,stage:'voice'}}:{})});
  if(scenario==='chained')await SH_AFTER_JOB({status:'done'});
  assert.deepEqual(events,scenario==='chained'?[['voice',0],['chat','voice'],['chat','voice']]:scenario==='voice-approved'?[['animation',0]]:scenario==='approved'?[['voice',0]]:scenario==='request-ready'?['review-request']:[]);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    subprocess.run(['node','-e','const scenario='+json.dumps(scenario)+';\n'+FOLLOW+harness], check=True, capture_output=True, text=True)


@pytest.mark.parametrize('status', ['running', 'failed', 'done'])
def test_chat_job_feedback_works_outside_pipeline(status):
    source = APP[APP.index('async function directorPollChatJob('):APP.index('function closeDirectorAgent()', APP.index('async function directorPollChatJob('))]
    harness = r'''
const assert=require('node:assert/strict');
let DIRECTOR_JOB_POLL=null,DIRECTOR_CHAT_OPEN_KEY='episode',DIRECTOR_CHAT_CACHE={episode:{}},renders=0,timers=0;
const BASE='',renderDirectorChatHost=()=>renders++,clearTimeout=()=>{},setTimeout=()=>++timers;
const fetch=async()=>({ok:true,json:async()=>({jobs:{test:{status,step:'Reading script',error:'Cannot parse heading'}}})});
(async()=>{await directorPollChatJob('episode','test');
assert.equal(renders,1);
assert.equal(timers,status==='running'?1:0);
assert.match(DIRECTOR_CHAT_CACHE.episode.jobProgress,status==='failed'?/Production paused: Cannot parse heading/:status==='done'?/completed/:/Reading script/);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    subprocess.run(['node','-e','const status='+json.dumps(status)+';\n'+source+harness],check=True,capture_output=True,text=True)
