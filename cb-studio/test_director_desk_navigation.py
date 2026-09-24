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


def test_hear_uses_dedicated_editor_and_canonical_spoken_words():
    assert "['storyboard','keyframe','animation'].includes(stage)" in APP
    assert 'spokenLines=SH_VOICE_CACHE[tok]?.approvedLines||[]' in APP
    assert 'pFocusedStage()==="voice"' in APP
    assert "openHear:()=>openShotOutcome('voice',PSHOT_I)" in APP


def test_unsaved_voice_or_dialogue_edits_block_fire():
    functions = '\n'.join(re.search(r'function '+name+r'\([^)]*\)\{.*?\n\}', APP, re.S).group()
                          for name in ('shVoiceMarkDirty', 'shHearHasUnsavedEdits', 'shHearSyncFire'))
    harness = """
    const assert=require('node:assert/strict');
    const SH_VOICE_DIRTY={},SH_VOICE_CACHE={s:{currentLines:[{text:'[happy] Hello'}]}};
    let scriptDirty=false;const buttons=[{},{}];
    const document={querySelector:()=>scriptDirty?{}:null,querySelectorAll:()=>buttons};
    assert.equal(shHearHasUnsavedEdits('s'),false);
    shVoiceMarkDirty('s',0,'[quiet] Hello');assert(buttons.every(b=>b.disabled));
    shVoiceMarkDirty('s',0,'[happy] Hello');assert(buttons.every(b=>!b.disabled));
    scriptDirty=true;shHearSyncFire('s');assert(buttons.every(b=>b.disabled));
    scriptDirty=false;SH_VOICE_CACHE.s.loading=true;shHearSyncFire('s');assert(buttons.every(b=>b.disabled));
    """
    subprocess.run(['node','-e',functions+harness],check=True,capture_output=True,text=True)
