"""Execute the actual browser continuation with fake transport and no providers."""
import json
import subprocess
from pathlib import Path

import pytest


APP = Path(__file__).with_name("app.html").read_text()
PREPARE = APP[APP.index("async function prepareDirectionThen("):
              APP.index("async function openDisclosureModal(")]


@pytest.mark.parametrize("scenario", ["current", "existing", "new", "failed", "navigated"])
def test_fire_preparation_continues_once_and_only_in_its_original_scene(scenario):
    harness = r'''
const assert=require("node:assert/strict");
let SH_JOB=null,SH_SC="1",SH_EP="Ep3",SH_DEPT_CACHE={},SH_LAST_JOB=null;
let SH_POLL_MISSES=0,SH_AFTER_JOB=null,BASE="",events=[];
const document={getElementById:()=>({innerHTML:"",classList:{add(){}}})};
const currentProductionDirection=()=>scenario==="current";
const alert=()=>{throw Error("Unexpected busy hold")};
const directionLabel=x=>x,_esc=x=>x,deptKey=(a,b)=>a+":"+b;
const closeM=()=>{},showToast=()=>{},renderWorkspaceBody=()=>{};
const shRememberJob=()=>{},shPollStart=()=>{},renderJobBanner=()=>{};
const directionPrepFailure=()=>events.push("failure");
const shFetchPkg=async()=>{events.push("refresh");};
const fetch=async(url,options)=>{
  events.push("prepare");
  const body=JSON.parse(options.body);
  assert.equal(body.episode,"Ep3"); assert.equal(body.shotId,"S1.SH1");
  return {ok:true,json:async()=>scenario==="existing"
    ? {ok:true,existing:true,department:{directionReady:true}}
    : {ok:true,jobId:"fixture-job"}};
};
(async()=>{
  await prepareDirectionThen("animation","S1.SH1",async()=>events.push("cost-review"));
  if(SH_AFTER_JOB){
    assert.deepEqual(events,["prepare"]);
    if(scenario==="navigated")SH_SC="2";
    await SH_AFTER_JOB({status:scenario==="failed"?"failed":"done"});
  }
  const expected=scenario==="current"?["cost-review"]:
    scenario==="failed"?["prepare","failure"]:
    scenario==="navigated"?["prepare"]:["prepare","refresh","cost-review"];
  assert.deepEqual(events,expected);
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
    subprocess.run(["node", "-e", "const scenario=" + json.dumps(scenario) + ";\n" +
                    PREPARE + harness], check=True, capture_output=True, text=True)
