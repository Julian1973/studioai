"""Execute the actual navigation functions with stale technical stages present."""
import re
import subprocess
from pathlib import Path

APP = Path(__file__).with_name('app.html').read_text()


def test_review_tabs_open_human_outcomes_not_internal_departments():
    function = re.search(r'function openPhaseOutcome\(id\)\{.*?\n\}', APP, re.S).group()
    harness = """
    const assert=require('node:assert/strict'),events=[];
    const PSHOT_I=1;
    const pShots=()=>[{shotId:'one'},{shotId:'two'}];
    const openShotOutcome=(stage,index)=>events.push([stage,index]);
    const currentStages=()=>{throw new Error('Must not send reviewer to technical world-building gates')};
    openPhaseOutcome('see');openPhaseOutcome('hear');openPhaseOutcome('watch');
    assert.deepEqual(events,[['keyframe',1],['voice',1],['animation',1]]);
    """
    subprocess.run(['node','-e',function+harness],check=True,capture_output=True,text=True)


def test_explicit_review_stays_visible_when_generation_is_locked():
    function = re.search(r'function pFocusedStage\(\).*?\n', APP).group()
    harness = """
    const assert=require('node:assert/strict');
    const PSTAGES=[{id:'keyframe'},{id:'voice'},{id:'animation'}];
    let PSTAGE='keyframe';const pStatus=()=> 'locked';const pActiveStage=()=> 'continuity';
    assert.equal(pFocusedStage(),'keyframe');
    PSTAGE='voice';assert.equal(pFocusedStage(),'voice');
    """
    subprocess.run(['node','-e',function+harness],check=True,capture_output=True,text=True)
