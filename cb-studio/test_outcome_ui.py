import re
from pathlib import Path


APP = (Path(__file__).parent / "app.html").read_text(encoding="utf-8")
SERVER = (Path(__file__).parent / "serve.py").read_text(encoding="utf-8")
RENDER = (Path(__file__).parent.parent / "engine" / "cb_render.py").read_text(encoding="utf-8")
INTAKE = (Path(__file__).parent.parent / "engine" / "cb_intake.py").read_text(encoding="utf-8")
COVERAGE = (Path(__file__).with_name("scene-coverage.js")).read_text(encoding="utf-8")


def test_server_freezes_stable_prewarmed_graph_before_accepting_browser_requests():
    prewarm = SERVER.index("_prewarm_director_session_cache()")
    collect = SERVER.index("gc.collect()", prewarm)
    freeze = SERVER.index('gc.freeze()', collect)
    disable = SERVER.index("gc.disable()", freeze)
    serve = SERVER.index("ThreadingHTTPServer((BIND_HOST, PORT), H)", disable)
    assert prewarm < collect < freeze < disable < serve


def test_primary_dashboard_cards_expose_explicit_actions():
    assert '<article class="projcard"' in APP
    assert '<article class="epcard"' in APP
    assert '<article class="scenecard"' in APP
    assert 'class="projcard" onclick=' not in APP
    assert 'class="epcard" onclick=' not in APP
    assert 'class="scenecard" onclick=' not in APP
    assert 'class="mc" onclick=' not in APP
    assert '<button type="button" class="wtree-shot ' in APP
    assert 'Open archive' in APP
    assert 'Continue production' in APP
    assert 'All caught up' not in APP
    assert 'Continue Production' not in APP


def test_text_direction_cost_policy_is_visible_and_served_from_backend():
    assert 'let RATES=null,OPENAI_POLICY=null;' in APP
    assert 'gpt-5.4-mini' not in APP
    assert 'hard limits $${call} per call / $${daily} per day' in APP
    assert 'textDirectionCostCopy("premium")' in APP
    assert 'textDirectionCostCopy("standard")' in APP
    assert '"openai": cb_llm.cost_policy()' in SERVER


def test_scene_board_is_a_visual_director_queue_not_a_department_matrix():
    assert 'aria-label="Episode production triage"' in APP
    assert 'Your decisions' in APP
    assert 'Needs attention' in APP
    assert 'Working now' in APP
    assert 'Scenes complete' in APP
    assert 'What needs you now · ${_esc(activeName)}' in APP
    assert 'aria-label="Direction, See, Hear, Watch"' in APP
    assert 'Current scene media' in APP
    assert 'Review "+activeName' in APP
    assert 'Resolve "+activeName' in APP
    assert 'Department matrix' not in APP
    assert 'Batch approve' not in APP


def test_scene_board_attention_filter_includes_blocked_and_rejected_scenes():
    assert '(key==="needs-attention"&&["blocked","rejected"].includes(scene.status))' in APP
    assert '["needs-attention","Needs attention"]' in APP


def test_see_and_watch_offer_visible_zero_spend_upload_choices():
    assert "Upload keyframe · no generation cost" in APP
    assert "Upload render · no generation cost" in APP
    assert 'accept="image/png,image/jpeg,image/webp"' in APP
    assert 'accept="video/mp4,video/webm"' in APP
    assert 'function shRenderUpload(tok,input)' in APP
    assert '/api/shot-render-upload' in APP
    assert 'shRun("select-render-upload",tok' in APP


def test_scene_board_exposes_keyframe_upload_for_the_next_eligible_shot():
    assert "function boardKeyframeUploadTarget(scene)" in APP
    assert 'activePhase.id==="see"?boardKeyframeUploadTarget(s):null' in APP
    assert "Upload keyframe<br>" in APP
    assert "${_esc(uploadTarget.shotId)} · no cost" in APP
    assert "onchange=\"boardKeyframeUpload(" in APP
    assert 'shot.sourceType==="opener"&&!ledger.keyframeCandidate' in APP


def test_dialogue_correction_reopens_only_hear_and_watch_without_redriving_story():
    correction = SERVER.index('if self.path == "/api/script-dialogue-correction":')
    synchronize = SERVER.index("synchronize_episode_script_registry(", correction)
    amend = SERVER.index("apply_scoped_dialogue_correction(", correction)
    assert synchronize < amend
    assert '"story-intake:correction", scene' not in SERVER[correction:correction + 5000]
    assert '"providerCalled": False' in SERVER
    assert '"next": "review-hear"' in SERVER
    assert '"voiceDirectionPreparing": True' in SERVER
    assert '["cb_render.py", "department-prepare", scene,' in SERVER
    assert "Words corrected — rebuilding this shot's HEAR direction" in APP
    assert '&st=voice&shot=' in APP
    assert 'location.reload();' not in re.search(
        r"async function shCorrectDialogue\(.*?\n\}", APP, re.DOTALL
    ).group(0)


def test_dialogue_correction_registry_sync_is_verified_before_intake():
    assert "def synchronize_episode_script_registry(" in SERVER
    assert 'actual != expected_script_version_id' in SERVER
    assert 'episode registry synchronization failed for {episode}' in SERVER


def test_hear_exposes_words_and_provider_prompt_as_separate_editable_layers():
    assert "Dialogue · exact script words" in APP
    assert "ElevenLabs prompt · v3" in APP
    assert "Spoken words from the ElevenLabs prompt appear here." in APP
    assert "Spoken words sync to Dialogue above." in APP
    assert "Exact ElevenLabs v3 text" in APP
    assert "Local timing recovery · review this take" in APP
    assert "No provider was called for this recovery" in APP
    assert "The paid path uses only the approved Voice specialist performance above" not in APP
    assert "Save ElevenLabs prompt" in APP
    assert "voicePanelHTML(tok,SH_VOICE_CACHE[tok])" in APP
    assert "await shLoadVoiceWork(tok)" in APP
    assert '"pronunciationOnly": True' in SERVER
    assert "Canon stays Aida · ElevenLabs receives Ada" in APP


def test_hear_prompt_edits_sync_dialogue_and_survive_script_versioning():
    assert "function shElevenLabsSpokenText(value)" in APP
    assert 'replace(/\\[[^\\]]*\\]/g," ")' in APP
    assert "const promptText=voiceDrafts[i]??SH_VOICE_CACHE[tok]?.currentLines?.[i]?.text" in APP
    assert "promptChanged?spokenPrompt:l.exactText" in APP
    assert 'const spoken=shElevenLabsSpokenText(value);' in APP
    assert 'dialogue.value=spoken;shScriptLineDirty(dialogue);' in APP
    assert 'SH_VOICE_DIRTY[tok]=voiceLines.map((line,i)=>(document.getElementById(`vwLine_${tok}_${i}`)||{}).value??line.text)' in APP
    assert "let SH_DIALOGUE_DIRTY={};" in APP
    correction = re.search(r"async function shCorrectDialogue\(.*?\n\}", APP, re.DOTALL).group(0)
    assert "Keep the live prompt draft" in correction
    assert "delete SH_DIALOGUE_DIRTY[tok][draftIndex]" in correction


def test_keyframe_review_decision_rail_exposes_upload_and_library_sources():
    assert "function keyframeDecisionSourceActions(tok)" in APP
    assert "Upload replacement keyframe" in APP
    assert "Choose library image" in APP
    assert "pending?keyframeDecisionSourceActions(tok)" in APP
    assert "keyframeDecisionSourceActions(tok)];" in APP
    assert "function shSelectReplacementKeyframe(cmd,tok,sourcePath)" in APP
    replacement = APP[APP.index("function shSelectReplacementKeyframe("):
                      APP.index("async function shOpenFrameUpload(")]
    assert 'return shRun(cmd,tok,{sourcePath,preserveView:true,progressLabel:sourceLabel})' in replacement
    # The authoritative selection command preserves history atomically; a separate
    # browser reject-then-select sequence can lose the replacement if interrupted.
    assert 'reject-keyframe' not in replacement
    assert 'confirm(' not in replacement
    assert 'if(outcome==="pending")' in APP


def test_every_shared_outcome_and_decision_shell_has_an_action_fallback():
    assert 'onclick="${_attr(action.onclick)}"' in APP
    outcome = re.search(
        r"function outcomePanelHTML\(opts\)\{(.*?)\n\}", APP, re.DOTALL
    )
    assert outcome
    assert "if(!actions.length)" in outcome.group(1)
    assert "actions.map(actionButtonHTML)" in outcome.group(1)

    decision = re.search(
        r"function decisionShell\(title,version,actionsHTML,historyHTML\)\{(.*?)\n\}",
        APP,
        re.DOTALL,
    )
    assert decision
    assert "actions.some" in decision.group(1)
    assert "actionButtonHTML(defaultDecisionAction())" in decision.group(1)
    assert 'if(target===current)return {label:"Open episode outcome"' in APP
    assert 'if(active===current)return {label:"Back to all scenes"' in APP


def test_audio_timing_conflict_offers_direct_and_hear_choices_without_fire():
    assert 'DIRECT_AUDIO_TIMING_CONFLICT' in APP
    assert 'The spoken line and movement do not line up yet' in APP
    assert "openStageOutcome('storyboard')" in APP and 'Revise in DIRECT' in APP
    assert "openStageOutcome('voice')" in APP and 'Review in HEAR' in APP
    assert "isTimingConflict?'':actionButtonHTML(recovery)" in APP
    import subprocess
    functions = APP[APP.index('function watchOperationProducerCopy(operation)'):APP.index('async function directorContinue()')]
    script = r'''
const assert=require('node:assert/strict');
const _esc=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
const actionButtonHTML=()=>'<button>Generic recovery</button>';
'''+functions+r'''
const error="DIRECT_AUDIO_TIMING_CONFLICT: char:Sunny checkpoint at 20.5s says it follows Sunny's approved line, which ends at 29.5s";
const copy=watchOperationProducerCopy({message:error});
assert.equal(copy.kind,'audio-timing');
assert.match(copy.detail,/29\.5s/);assert.match(copy.detail,/20\.5s/);
const html=watchPreflightFailureHTML(error,{});
assert.match(html,/Revise in DIRECT/);assert.match(html,/Review in HEAR/);
assert.doesNotMatch(html,/Generic recovery/);
assert.match(html,/Technical details/);
'''
    subprocess.run(['node','-e',script],check=True,capture_output=True,text=True)


def test_blocked_rejected_review_and_complete_states_offer_outcomes():
    required_actions = (
        "Resolve Story &amp; Direction handover",
        "Run episode Story &amp; Direction",
        "Open Look Development",
        "Resolve the previous shot",
        "Next: create revision",
        "Redesign with Animation Director",
        "Open Director's Seat",
        "focusShotReview",
        "Lock cut &amp; build master",
        "Approve or reject the final review",
        "Rebuild current post master",
        "Back to all scenes",
    )
    for action in required_actions:
        assert action in APP
    assert 'x.code==="STORY_INTAKE_APPROVAL_REQUIRED"' in APP


def test_empty_and_moved_views_route_somewhere_useful():
    assert 'title:"No houses are locked yet"' in APP
    assert 'label:"Open scenes"' in APP
    assert 'title:"Continue in the production workspace"' in APP
    assert 'if(page=="script")return renderScript();' in APP
    assert 'title:"No scenes match this filter"' in APP
    assert 'label:"Show all scenes"' in APP
    assert "generated scene shot" in APP
    assert "locked location master" in APP
    assert "approved &amp; stored (reusable)" not in APP


def test_episode_continue_prefers_newest_script_when_upstream_changes_stale_packages():
    assert "const byNewestEpisode=" in APP
    assert 'byNewestEpisode(EPISODES).find(e=>e.packageCurrent)' in APP
    assert 'byNewestEpisode(EPISODES).find(e=>e.script)' in APP
    assert 'EPISODES.find(e=>e.script)||EPISODES[0]' not in APP


def test_completed_shots_and_scenes_have_a_clean_next_step():
    assert "function nextSceneActionHTML(kind)" in APP
    assert "function approvedShotNextActionHTML(shots)" in APP
    assert 'return nextSceneActionHTML("scene");' in APP
    assert 'nextSceneActionHTML("scene")' in APP
    assert "Finish scene then continue to Scene" in APP
    assert "Continue to Scene" in APP
    start = APP.index("async function continueToNextProductionShot()")
    end = APP.index("function focusShotReview", start)
    assert 'command:"next-shot-guidance"' in APP[start:end]
    assert "Luna’s next-shot recommendation" in APP[start:end]
    assert 'id="agreeNextShot"' in APP[start:end]
    assert 'id="stayOnShot"' in APP[start:end]
    assert 'openShotOutcome("keyframe",nextIndex);' in APP[start:end]
    assert 'openShotOutcome("animation",nextIndex);' not in APP[start:end]
    assert 'if(guidance.ready===false){openShotOutcome("animation",PSHOT_I);return;}' in APP[start:end]
    route_start = APP.index("function openShotOutcome(stage,index)")
    route_end = APP.index("function continueCurrentShotToWatch", route_start)
    assert 'if(target>PSHOT_I)stage="keyframe";' in APP[route_start:route_end]
    director_start = APP.index("function directorSelectShot(index)")
    director_end = APP.index("function watchProductionOperation", director_start)
    assert "openShotOutcome(stage,index);" in APP[director_start:director_end]


def test_shot_handoff_distinguishes_cut_from_exact_relay():
    assert 'const relay=shot.sourceType==="relay"&&source===shot.sourceShotId;' in APP
    assert 'const exactCarry=!!(relay&&frame&&opening===frame);' in APP
    assert "No new keyframe is generated." in APP
    assert 'const cut=media.handoffType==="cut"||transition.type==="cut";' in APP
    assert 'Hard cut: ${_esc(source)}’s final frame informs continuity only;' in APP
    assert "The script and Director Card stay authoritative." in APP
    assert 'const openingBrief=transition.openingImage||shot.openingPose||shotFocusCopy' in APP
    assert 'visualAnchorPairHTML(anchorMedia,keyframeReviewHTML,handoffReview)' in APP
    assert 'const openingInputsStale=mode==="keyframe"&&/(inputs changed|direction updated)/i.test(decVersion);' in APP
    assert 'const currentOpening=keyframeAnchorOwnsCurrent&&!openingInputsStale;' in APP
    assert 'keyframeCandidate:currentOpening?m.keyframeCandidate:null' in APP
    assert 'keyframeCandidates:currentOpening?m.keyframeCandidates:[]' in APP
    assert 'historicalOpening?"Previously approved image · reference for this opening"' in APP
    assert 'Image available · approval status shown alongside' in APP


def test_stale_story_direction_keeps_carried_scene_work_visible():
    assert "def carried_scene_roster(episode):" in INTAKE
    assert '"carriedScenes": carried_scene_roster(episode)' in INTAKE
    assert "j.carriedScenes||[]" in APP
    assert "const hasCarried=!!e.stalePackage;" in APP
    assert 'const actionLabel=navigable?"Open scenes"' in APP
    assert "Recovered production" in APP
    assert "Earlier scene work is still here" in APP
    assert 'onclick:"openStoryIntakePanel()"' in APP
    assert "stale against the active script" not in APP


def test_explicit_hash_navigation_reloads_the_requested_scene():
    assert 'window.addEventListener("hashchange",async()=>{' in APP
    assert 'const restored=await _restoreFromHash(raw);' in APP
    assert 'if(seq!==HASH_RESTORE_SEQ)return;' in APP


def test_scene_asset_status_only_counts_files_proven_on_disk():
    assert "master_path.is_relative_to(ROOT)" in SERVER
    assert '"master": configured_master if master_exists else None' in SERVER
    assert '"masterMissing": bool(configured_master and not master_exists)' in SERVER


def test_story_intake_remembers_runs_and_names_the_lock_boundary():
    assert "function latestJobFor(kind,scene,episode)" in APP
    assert "Last run details" in APP and "shJobHTML(lastJob)" in APP
    assert 'label:"Accept direction"' in APP
    assert 'title:"Story & Direction accepted"' in APP
    assert "Approved & locked" in APP
    assert "verdict,note,by:REVIEWER" in APP
    assert 'subprocess.Popen([sys.executable, "-u"] + args' in SERVER
    assert "cb_db.interrupt_running_jobs(ROOT, server_key=SERVER_KEY)" in SERVER
    assert "restored_jobs = cb_db.load_jobs(ROOT, server_key=SERVER_KEY)" in SERVER
    assert '!r.ok||!Array.isArray(payload)' in APP
    assert 'title:"Episode state could not load"' in APP
    assert 'return await boot()' in APP


def test_storyboard_leads_with_seedance_units_and_exposes_packing_reasons():
    assert "story beat${beats.length===1" in APP
    assert "production unit${shots.length===1" in APP
    assert "full 30s" in APP
    assert "30-second packing audit" in APP
    assert "providerBoundaryReason" in APP
    assert "short provider split" in APP
    assert "capacity indicator, never a padding target" in APP
    assert 'str(gate or "").startswith("creative") and "seedance" in low' in SERVER
    assert "Story & Direction — packing production units…" in SERVER


def test_scene_review_exposes_the_simple_director_journey():
    assert 'aria-label="Scene creation path"' in APP
    assert '{id:"direction",name:"Direction",glyph:"▤",members:["script","storyboard"]}' in APP
    assert '{id:"see",name:"See",glyph:"◧",members:["scenelook","keyframe"]}' in APP
    assert '{id:"hear",name:"Hear",glyph:"♪",members:["voice"]}' in APP
    assert '{id:"watch",name:"Watch",glyph:"►",members:["animation","continuity","final"]}' in APP
    assert APP.index('{id:"keyframe",name:"Keyframe"') < APP.index('{id:"voice",name:"Voice & Timing"')
    assert "function phaseState(phase,stages)" in APP
    assert "function phaseTarget(phase,stages)" in APP
    assert "function openPhaseOutcome(id)" in APP
    assert "openPhaseOutcome('${step.id}')" in APP
    assert 'Continue to SEE →</button>' in APP
    assert 'const PRODUCER_PHASES=PPHASES.filter(phase=>phase.id!=="direction")' in APP
    assert "function continueSceneLookToFirstKeyframe()" in APP
    assert 'Continue to Shot 1 Keyframe →</button>' in APP
    assert 'BASE+"/api/storyboard-handover"' in APP
    assert "SH_STATE&&SH_STATE.packageCurrent===false" in APP
    assert "No approval or provider spend is required" in APP
    assert "Prepare Shot 1 &amp; open Keyframe →" in APP
    assert "Approve the Story & Direction department's storyboard" not in APP
    assert "openDisclosureModal('scenelook'" in APP
    assert "openDisclosureModal('keyframe'" in APP
    assert "s.beatCodes&&s.beatCodes.length" in APP
    assert 'codes[0]+"–"+codes[codes.length-1]' in APP
    assert "Fire Seedance 2.5" in APP
    assert "Run Seedance 2.0 comparison" not in APP
    assert "storyboard-progress-fill" in APP
    assert "storyboard-working" in APP
    assert "stopped on protection" in APP
    assert "Retry unfinished scene directions" in APP


def test_direction_is_automatic_preparation_before_human_media_gates():
    assert 'if(await ensureAutomaticSceneDirection())await pLoadAll();' in APP
    assert 'BASE+"/api/direction-prepare"' in APP
    assert 'Prepared from the active scene script. No producer approval is required here.' in APP
    assert 'Built automatically before SEE, HEAR and WATCH' in APP
    direction_stage = APP[APP.index("function renderStoryboardStage"):
                          APP.index("async function pFireCreative")]
    assert "pStoryboardDecide('approved')" not in direction_stage
    assert 'Continue to SEE →' in direction_stage
    assert 'if self.path == "/api/direction-prepare"' in SERVER
    assert 'def _finalize_automatic_direction(job):' in SERVER
    assert 'humanGates": ["see", "hear", "watch"]' in SERVER
    assert 'directionPreparation": "automatic"' in SERVER
    assert 'old_digest == new_digest' in SERVER


def test_approved_watch_takes_open_the_scene_directors_seat():
    assert "{id:\"continuity\",name:\"Director's Seat\",glyph:\"⇄\"}" in APP
    assert 'onclick="openStageOutcome(\'continuity\')">Open Director\'s Seat</button>' in APP
    assert ">Continue to Director Review</button>" not in APP
    assert "function renderContinuityStage()" in APP
    assert "Scene shot bin" in APP
    assert "WATCH pending" in APP
    assert "directorCutDragStart" in APP and "directorCutDrop" in APP
    assert "directorCutTrim" in APP
    assert "Lock cut &amp; build master" in APP
    assert "/api/rough-cut-draft?episode=" in APP
    assert 'action,sequence:directorCutPayload()' in APP


def test_next_scene_navigation_preserves_scene_progress():
    assert "async function continueToNextScene()" in APP
    assert "openScene(roster[current+1].scene)" in APP


def test_internal_direction_is_not_a_fake_human_approval_gate():
    assert "Direction ready" in APP
    assert "Its proof is the next rendered outcome" in APP
    assert "Approve direction" in APP
    assert "productionInputs" in APP
    assert "approvedInputs" not in APP
    assert '["Creative target",inp.keyframePromptHeadline' in APP
    assert '["Your next decision","Accept or iterate the finished keyframe"]' in APP


def test_provider_blocker_opens_a_real_setup_outcome_instead_of_looping():
    assert "function openConfigurationOutcome()" in APP
    assert "Connect Seedance 2.5" in APP
    assert "Open official BytePlus setup" in APP
    assert "Recheck connection" in APP
    assert "No automatic Seedance 2.0 fallback" in APP
    assert 'configuration=target==="configuration"' in APP
    assert '${configuration?"openConfigurationOutcome()"' in APP


def test_fire_score_labels_are_advisory_not_false_submission_blocks():
    start = APP.index('function openAnimationConfirmModal(')
    body = APP[start:APP.index('function openTimingReviewModal(', start)]
    assert 'Creative target:' in body
    assert 'below target — review direction before Fire' in body
    assert '"PASS — eligible to fire":"BLOCKED"' not in body
    assert 'onclick="_confirmDisclosure()"' in body
    assert 'request integrity and spend checks' in body


def test_fire_prepares_internal_direction_then_returns_to_the_visible_outcome():
    assert "function currentProductionDirection(stage,shotId)" in APP
    assert "async function prepareDirectionThen(stage,shotId,resume)" in APP
    assert "No separate approval is required" in APP
    assert "No media is being generated and no media spend can occur in this step" in APP
    assert 'prepareDirectionThen(directionStage,ctx.shotId,()=>openDisclosureModal(kind,ctx))' in APP
    fire_start = APP.index("async function shRender(shotId,options)")
    fire_body = APP[fire_start:APP.index("function shCompareRender", fire_start)]
    assert 'prepareDirectionThen("animation",shotId,()=>shRender(shotId))' not in fire_body
    assert 'fetch(url,{cache:"no-store"})' in fire_body
    assert "SH_AFTER_JOB" in APP
    assert 'protectedComparison?"Fire one comparison":"Fire candidates"' in APP
    assert "Seedance 2.5 prompt preflight" in APP
    assert "Contract completeness" in APP
    assert "Creative direction" in APP
    assert "Creative target:" in APP
    assert "below target — review direction before Fire" in APP
    assert '"PASS — eligible to fire":"BLOCKED"' not in APP
    assert "No critical failures." in APP
    assert "function fireReferenceStripHTML(shotId,auth)" in APP
    assert "References sent to Seedance" in APP
    assert "Exact upload order locked to this paid request" in APP
    assert '((auth||{}).envelope||{}).references' in APP
    assert '${referenceStrip}' in APP
    assert ".fire-reference-grid{display:grid" in APP
    assert ".fire-reference-grid{grid-template-columns:repeat(2" in APP
    assert 'if(!confirm("PAID BATCH' not in APP
    assert "✓ Approve revision" in APP
    assert "Iterate batch" in APP


def test_hear_keeps_the_audio_outcome_prominent_before_and_after_generation():
    assert "stage-audio-empty" in APP
    assert "No voice take yet" in APP
    assert '${promptCueWarnings} acting ${promptCueWarnings===1?"cue":"cues"} to review' in APP
    assert "Save corrected words" in APP
    assert "data-hear-fire" in APP
    assert "Final review shows exact dialogue, ElevenLabs prompt and cost before Fire." in APP
    assert ">Create voice</button>" in APP
    assert "Final confirmation · generate voice" in APP
    assert "Performance direction ready — audio not generated" in APP
    assert 'openDisclosureModal(\'voice\',{shotId:\'${tok}\'})' in APP
    assert '<audio controls preload="metadata"' in APP


def test_hear_fire_waits_for_see_and_offers_luna_performance_preparation():
    assert "hearFireAllowed=!!shotPolicy.allowedActions?.generateVoice;" in APP
    assert "hearKeyframeNeeded=!!shotPolicy.needsKeyframe&&!hearCurrent.keyframe;" in APP
    assert "else if(hearKeyframeNeeded)" in APP
    assert "else if(!hearSeeHandoffCurrent)" in APP
    assert "Improve acting cues with Luna · optional" in APP
    assert "async function prepareHearPerformance(shotId)" in APP
    assert "Luna is translating the current character intention" in APP
    assert "No audio is generated, and voice Fire remains a separate decision." in APP
    assert "else if(lunaVoicePrepNeeded)" not in APP


def test_see_handoff_offers_storyboard_or_a_clean_continue_to_hear_choice():
    assert "async function continueSeeToHear(shotId)" in APP
    assert 'id="continueHearNoStoryboard">Continue to HEAR' in APP
    assert 'id="addHearStoryboard">Build storyboard first' in APP
    assert "Recommended:</b> continue with the approved opening keyframe." in APP
    assert "PSTAGE='storyboard';renderWorkspaceBody();_syncHash();" in APP
    assert "continueSeeToHear('${_esc(s.shotId)}')" in APP
    assert "<h3>Continue to HEAR</h3>" in APP
    handoff = APP[APP.index("async function continueSeeToHear(shotId)"):APP.index("async function reviewWatchInputs(shotId)")]
    assert handoff.count("await openSceneOutcome(scope.scene,'voice',shotId)") == 2


def test_hear_puts_the_producer_decision_first_and_shows_audio_status_under_shot_buttons():
    assert "function voicePreviewStatusHTML(shot,ledger)" in APP
    assert 'stage==="voice"?voicePreviewStatusHTML(selectedShot,selectedLedger):""' in APP
    start = APP.index(':`${nav}${mode==="voice"?"":producerDirection}')
    end = APP.index('  art.insertAdjacentHTML("beforeend",shotMissingItemsHTML', start)
    hear_surface = APP[start:end]
    assert '`${nav}${mode==="voice"?"":producerDirection}' in hear_surface
    assert 'dec.innerHTML=(mode==="voice"?hearReview:"")+decisionShell' in APP
    assert '.wcol-decision>.hear-review-card' in APP
    assert "The player appears beneath the shot buttons when ElevenLabs returns" not in APP
    assert '<details class="focus-evidence hear-editor" open><summary>Dialogue · exact script words' in APP
    assert '<details class="focus-evidence hear-editor" open aria-label="ElevenLabs v3 performance prompt"><summary>ElevenLabs prompt · v3' in APP


def test_selected_shot_coverage_does_not_show_the_entire_scene_board():
    assert "function legacy(pkg, selectedShotId)" in COVERAGE
    assert "StudioCoverage?.legacy(SH_PKG,s.shotId)" in APP


def test_director_desk_keeps_next_action_and_shots_above_media():
    rail = '<div id="railwrap">${renderStageRail()}</div>'
    next_step = '<div id="director-next-step">${directorNextStepHTML()}</div>'
    shots = '<div id="shotoverview">${sceneShotOverviewHTML()}</div>'
    assert APP.index(rail) < APP.index(next_step) < APP.index(shots)
    assert 'aria-label="Scene and shot navigation"' in APP
    assert 'if(sceneAudio)sceneAudio.innerHTML=""' in APP


def test_current_shot_is_visually_unmistakable_and_accessible():
    assert "box-shadow:0 0 0 4px" in APP
    assert "scene-shot-current" in APP
    assert "Current shot" in APP
    assert 'aria-current="true"' in APP


def test_completed_job_refresh_finishes_before_deferred_outcome_resumes():
    poll = re.search(
        r"async function _shPollTick\(\)\{(.*?)\n\}", APP, re.DOTALL
    )
    assert poll
    body = poll.group(1)
    refresh = 'if(page=="pipeline"&&completedHere)await renderControl();'
    resume = "if(afterJob&&completedHere)await afterJob(j);"
    assert refresh in body
    assert body.index(refresh) < body.index(resume)
    assert 'if(page=="pipeline")renderControl();else renderJobBanner();' not in body


def test_mobile_modal_stacks_above_the_sticky_app_header():
    assert ".modal{position:fixed;inset:0" in APP
    assert "padding:24px;z-index:100}.modal.show" in APP
    assert ".top{position:sticky;top:0;z-index:40" in APP


def test_saved_scene_restore_does_not_load_the_whole_scene_board_first():
    assert "const deferEpisodeRender=pg==='pipeline'&&!!scId;" in APP
    assert "openEpisode(epNum,deferEpisodeRender)" in APP
    episode = re.search(
        r"async function openEpisode\(num,deferRender\)\{(.*?)\n\}", APP, re.DOTALL
    )
    assert episode
    assert "if(!deferRender)render();" in episode.group(1)


def test_missing_legacy_world_asset_never_renders_a_broken_image():
    assert "body=sl.plateUrl" in APP
    assert "The previous world anchor is not available in this workspace" in APP


def test_keyframe_is_one_bounded_build_with_recovery_details_below_it():
    assert 'const buildLabel="Build keyframe"' in APP
    assert "shRun('build-keyframe',ctx.shotId)" in APP
    assert "One generation; no automatic rerolls" in APP
    assert "Keyframe references" in APP
    assert "Acting poses &amp; local checks" in APP
    assert "Use an existing image instead" in APP
    assert "not applicable (scene opener)" not in APP
    assert "Prepare acting poses" not in APP


def test_pipeline_defaults_to_one_calm_outcome_before_production_detail():
    workspace = '<div id="workspace" class="workspace"></div>'
    production_details = '<details class="production-context"><summary>'
    assert workspace in APP and production_details in APP
    assert APP.index(workspace) < APP.index(production_details)
    assert '<details class="production-context" open' not in APP
    assert 'el.classList.add("focus-workspace")' in APP
    assert '<div class="wcol wcol-decision" id="wdecision"></div>' in APP
    assert '<details class="focus-context"><summary>Scene &amp; shot map</summary>' in APP
    assert '<details class="focus-evidence"><summary>Direction &amp; review evidence</summary>' in APP
    assert '<div class="wcol-head">Your decision</div>' in APP
    assert 'return `<div id="director-chat-host">${directorChatHTML()}</div>' in APP


def test_active_production_job_survives_navigation_and_refresh():
    assert 'localStorage.setItem("cb_active_production_job"' in APP
    assert 'localStorage.getItem("cb_active_production_job")' in APP
    assert 'if(SH_JOB)setTimeout(()=>shPollStart(),0)' in APP
    assert 'function shJobBelongsHere()' in APP


def test_see_hear_watch_keep_the_stage_media_visible():
    assert 'keyframe:["SEE","Opening keyframe"]' in APP
    assert 'voice:["HEAR","ElevenLabs v3 voice bed"]' in APP
    assert 'animation:["WATCH","Seedance 2.5 render"]' in APP
    assert 'class="zoom pmedia img"' in APP
    assert 'class="stage-audio"' in APP
    assert 'onloadedmetadata="mediaDurationLoaded(this)"' in APP
    assert '<video controls src="${BASE}${m.clip}?v=${MEDIA_V}"></video>' in APP
    assert '<details class="focus-evidence hear-editor" open><summary>Dialogue · exact script words' in APP
    assert 'aria-label="ElevenLabs v3 performance prompt"' in APP


def test_see_has_an_obvious_full_screen_image_control():
    assert 'function expandCurrentStageImage()' in APP
    assert 'aria-label="View keyframe full screen"' in APP
    assert 'aria-label="View scene image full screen"' in APP
    assert 'onclick="expandCurrentStageImage()"' in APP


def test_populated_stage_is_a_top_level_media_and_decision_desk():
    assert '.focus-workspace.result-first{display:grid;grid-template-columns:minmax(0,1fr) 300px' in APP
    assert '.focus-workspace.result-first .wcol-artefact{grid-column:1;grid-row:1' in APP
    assert '.focus-workspace.result-first .wcol-decision{grid-column:2;grid-row:1' in APP
    assert '@media(max-width:900px){.focus-workspace.result-first{display:flex' in APP
    assert 'workspace.classList.toggle("result-first",true)' in APP


def test_identity_screening_keeps_the_keyframe_visible_for_review():
    assert 'resultFirst=true;keyframeAnchorOwnsCurrent=!!(pending&&m.keyframe)' in APP
    assert 'keyframeRevisionMedia(m.keyframe,led,s,"NEEDS YOUR DECISION")' in APP
    assert 'approveKeyframeAdvisory' in APP
    assert 'Approve current keyframe' in APP
    assert 'approveKeyframeAdvisory' in APP
    assert 'hard canon, reference, lineage and file-integrity checks' in APP.lower()
    assert "directorStartRejection('keyframe'" in APP
    assert 'class="review-warning"' in APP


def test_stale_keyframe_offers_forward_actions_and_neutral_history():
    assert 'pst.kf==="staleInputs"' in APP
    assert "Choose a refreshed opening image" in APP
    assert "Shot direction is updated. Choose how to create this shot’s opening image." in APP
    assert "Generate keyframe" in APP
    assert "Upload image" in APP
    assert "Choose from Library" in APP
    assert '"Earlier version":"rejected"' in APP


def test_human_keyframe_approval_is_the_single_visible_stage_decision():
    safety = (Path(__file__).parent.parent / "engine" / "cb_safety.py").read_text()
    assert 'advisory = record.get("conformanceAdvisoryDecision") or {}' in safety
    assert 'if advisory.get("acceptedBy"):' in safety
    assert "Requiring a second hidden override" in safety


def test_see_makes_revision_lineage_and_current_decision_explicit():
    assert 'function keyframeRevisionInfo' in APP
    assert 'function keyframeRevisionMedia' in APP
    assert 'What changed for this revision' in APP
    assert 'Your requested correction' in APP
    assert 'The large image above is the new result to review.' in APP
    assert 'Approve current keyframe' in APP
    assert 'onclick="openKeyframeRetake(' in APP
    assert 'PREVIOUS · REJECTED' in APP
    assert 'No current keyframe yet.' in APP


def test_current_voice_bed_note_overrides_an_old_rejection_reason():
    assert 'const currentVoiceNote=' in APP
    assert 'const voiceChangeNote=currentVoiceNote||previousVoiceCorrection' in APP
    assert 'const voiceChangeLabel=currentVoiceNote?"Current take":"Your requested correction"' in APP


def test_conversational_director_is_present_on_every_decision_surface():
    assert '<div id="director-chat-host">${directorChatHTML()}</div>' in APP
    assert '✦ Ask Director' in APP
    assert 'producer-director-fold' in APP
    assert 'if(!DIRECTOR_CHAT_OPEN_KEY)openDirectorAgent()' in APP
    assert 'if(!DIRECTOR_CHAT_CACHE[key])openDirectorAgent(scope)' not in APP
    assert 'class="director-chat-backdrop"' in APP
    assert 'role="${docked?"region":"dialog"}"' in APP
    assert '.director-chat.director-chat-docked{position:static' in APP
    assert 'queueMicrotask(mountDirectorDesk)' in APP
    assert 'Apply to next revision and return' in APP
    assert 'What will visibly change' in APP
    assert 'Keep locked' in APP
    assert 'Director is thinking' in APP
    assert '.director-chat{position:fixed' in APP
    assert 'Apply to working prompt · no render' in APP
    assert '[DIRECTOR ITERATION]' in APP
    assert 'Director change applied · no render fired' in APP
    assert 'Applying correction…' in APP
    assert 'Archiving the rejected takes and updating this shot' in APP


def test_director_apply_uses_its_prepared_correction_without_a_second_prompt():
    run_start = APP.index('async function shRun(cmd,shotId,opts)')
    run_end = APP.index('function shOverrideModelLimited', run_start)
    run = APP[run_start:run_end]
    assert 'correction=(correction!=null?correction:' in run
    assert 'document.getElementById("shCat_"+tok)' in APP
    assert 'shRun("reject",tok,{correction,category,preserveView:true' in APP
    assert 'onStartError:error=>directorApplyFailed(key,error)' in APP
    assert 'function directorApplyFailed(key,message)' in APP
    assert 'async function persistAnimationDirectorPrompt(tok,revised)' in APP
    assert 'function directorProductionInstruction(latest)' in APP
    assert 'Visible result required: ' in APP
    assert 'Keep locked: ' in APP
    assert 'correction:productionInstruction' in APP
    assert 'Saving the corrected working prompt' in APP
    assert 'await persistAnimationDirectorPrompt(tok,revised)' in APP
    assert 'await finishAnimationDirectorCorrection(tok,key)' in APP
    assert 'applying:false' in APP


def test_keyframe_director_apply_passes_visible_result_and_locks():
    start = APP.index('function directorApplyCorrection()')
    end = APP.index('\nfunction ', start + 10)
    apply = APP[start:end]
    assert 'if(scope.stage==="keyframe")return shRun("reject-keyframe",tok,{correction:productionInstruction,preserveView:true' in apply
    assert 'Saving the SEE correction' in apply
    assert 'SEE correction saved and current candidate archived. No image generated.' in apply
    assert 'showToast("SEE correction saved · no image generated · updated prompt ready to review",true)' in apply


def test_director_exposes_refire_only_for_the_current_keyframe_review():
    assert 'function directorKeyframeRefireReady(data,scope)' in APP
    assert 'latest.reviewTargetHash===data.reviewTarget.hash' in APP
    assert 'button.textContent="Refire corrected keyframe · 1 image"' in APP
    assert 'The new image returns here for your review; WATCH is not fired.' in APP
    assert 'Update correction for current keyframe' in APP
    assert 'This proposal is for an earlier image. Updating it uses Luna/API credit, not image spend.' in APP


def test_working_prompt_change_invalidates_the_previous_spend_envelope():
    render = (Path(__file__).parent.parent / "engine" / "cb_render.py").read_text(encoding="utf-8")
    save_start = render.index("def save_seedance_working")
    save_end = render.index("def restore_seedance_working", save_start)
    assert 'led["pendingSpendAuth"] = None' in render[save_start:save_end]


def test_approved_watch_has_clear_approve_refire_and_bounded_edit_paths():
    assert "Refire full take" in APP
    assert "Edit part of take" in APP
    assert 'stage:"animation-edit"' in APP
    assert 'stage:"animation-refire"' in APP
    assert "Prepare targeted edit · review cost" in APP
    assert 'shRun("edit",tok,{startSec:Number(latest.editStartSec)' in APP


def test_voice_fire_confirmation_shows_exact_provider_dialogue():
    assert "Exact dialogue being generated" in APP
    assert "Exact dialogue being regenerated" in APP
    assert "These are the provider-facing words and V3 performance tags for this Fire." in APP
    assert "This is exactly the current provider input." in APP
    assert "<b>Script:</b>" in APP
    assert "<b>ElevenLabs:</b>" in APP


def test_filmagent_style_shot_context_is_visible_across_see_hear_watch():
    assert 'function shotContextCardHTML' in APP
    assert 'function shotLandingText' in APP
    assert 'SHOT · ${_esc(shot.shotId)} · ${stage} REVISION ${revision}' in APP
    assert '["Opening",shot.openingPose' in APP
    assert '["Action",shot.purpose' in APP
    assert '["Landing",shotLandingText(shot)]' in APP
    assert 'Canon locked' in APP
    assert 'Seedance 2.5' in APP
    assert 'ElevenLabs v3 · @Audio1' in APP
    assert 'fetch(BASE+"/api/director-chat"' in APP
    assert 'function directorApplyCorrection()' in APP
    assert 'directorStartRejection(\'keyframe\'' in APP
    assert "shRun('reject-voice','${tok}')" in APP
    # WATCH uses the dedicated, batch-bound retake form rather than chat rejection.
    assert 'onclick="openWatchRetake(' in APP
    assert "shRun('retake',tok,{correction,expectedBatchId:batch" in APP
    assert '"Creative direction"' in APP


def test_shot_context_keeps_duration_purpose_and_dialogue_timing_visible():
    assert 'function shotDialogueWindow(shot)' in APP
    assert 'class="shot-glance"' in APP
    assert '<span>Total shot</span>' in APP
    assert '<span>What this shot must do</span>' in APP
    assert '<span>Voice in context</span>' in APP
    assert 'Math.min(...starts).toFixed(1)' in APP
    assert 'Math.max(...ends).toFixed(1)' in APP


def test_hear_visually_separates_elevenlabs_dialogue_from_seedance_sfx():
    assert 'function routeShotAudio(shot)' in APP
    assert 'o{2,}h{2,}m{2,}' in APP
    assert '"meditation mantra chant"' in APP
    assert 'authoredCue:original' in APP
    assert 'Seedance 2.5 SFX · not sent to ElevenLabs' in APP
    assert 'No ElevenLabs track is required for this shot.' in APP
    assert 'Seedance 2.5 SFX only · no ElevenLabs spend' in APP
    assert 'They never enter @Audio1.' in APP


def test_watch_readiness_uses_routed_spoken_dialogue_not_raw_script_events():
    assert 'const talky=routeShotAudio(s).spokenDialogue.length>0;' in APP
    assert 'Only routed spoken dialogue requires an ElevenLabs approval before WATCH.' in APP
    assert 'function continueCurrentShotToWatch()' in APP
    assert 'onclick="continueCurrentShotToWatch()">Continue to Watch' in APP


def test_hear_has_one_forward_action_at_the_top_of_the_page():
    assert APP.index('id="producer-primary-action"') < APP.index('id="railwrap"')
    start = APP.index("function mountHearPrimaryAction(")
    end = APP.index("\nfunction scenePlateSourceActionsHTML", start)
    action = APP[start:end]
    assert 'host.appendChild(primary)' in action
    assert 'Approve voice and continue to WATCH' in action
    assert 'Create corrected voice take' in action
    assert 'Save words for the next voice take' in action
    assert 'Save voice direction for the next take' in action
    assert 'const gateFirst=["SEE keyframe required","Approved opening ready","Refresh the current production check"].includes(version)' in action
    assert 'let primary=gateFirst?actions?.querySelector(".btn:not(:disabled)"):null' in action
    assert 'host.classList.add("hear-forward-action")' in action
    assert 'Review dialogue' in action
    assert 'if(mode===\'voice\'){shHearSyncFire(tok);mountHearPrimaryAction(s,art,dec,decVersion,tok);}' in APP


def test_hear_candidate_shows_approve_or_reject_at_top_and_approval_continues_to_watch():
    start = APP.index('decVersion=`Current voice revision ${voiceRevision} · Awaiting your decision`')
    end = APP.index('if((led.voiceRejections||[]).length)', start)
    decision = APP[start:end]
    assert 'shRun(\'approve-voice\'' in decision
    assert 'openVoiceRetake' in decision
    assert 'Approve to make this take @Audio1 and continue to WATCH.' in decision
    assert 'voice-regen' not in decision

    start = APP.index('function mountHearPrimaryAction(')
    end = APP.index('\nfunction scenePlateSourceActionsHTML', start)
    mount = APP[start:end]
    assert 'if(approve&&reject){' in mount
    assert 'versionText.includes("text changed")' in mount
    assert 'const needsProducerOverride=promptDirty||versionText.includes("text changed")' in mount
    assert 'Approve this take as heard' in mount
    assert 'host.append(approve,reject);return' in mount
    assert 'hear-review-choice' in mount
    assert 'Save changed words or voice direction and create a matching take before approval' in APP


def test_stale_hear_take_keeps_review_choices_visible_but_blocks_wrong_audio():
    start = APP.index('} else if(staleVoiceTake&&!voApproved){')
    end = APP.index('} else if(timingRepairNeeded){', start)
    stale = APP[start:end]
    assert 'data-hear-approval-preview="true" disabled aria-disabled="true"' not in stale
    assert 'shRun(\'approve-voice\',\'${_esc(tok)}\',{producerOverride:true})' in stale
    assert 'approve.dataset.hearProducerOverride="true"' in APP
    assert 'openVoiceRetake' in stale
    assert 'approve this exact take as heard or reject it' in stale
    assert "openDisclosureModal('voice-regen'" in stale


def test_stale_hear_approval_requires_explicit_ack_and_exact_review_target():
    assert 'function openHearOverrideModal(tok)' in APP
    assert 'id="hearOverrideAcknowledged" type="checkbox"' in APP
    assert 'disabled onclick="confirmHearOverride' in APP
    assert 'await shRun("approve-voice",tok,{producerOverride:true,producerOverrideAcknowledged:true})' in APP
    assert "'approve voice as heard'" in APP
    assert 'producerOverrideAcknowledged:decisionOptions.producerOverrideAcknowledged===true' in APP
    assert 'action["kind"] == "approve-voice-override"' in SERVER
    assert 'd.get("producerOverrideAcknowledged") is not True' in SERVER
    assert 'expected.get("hash") != current["hash"]' in SERVER
    assert '"--producer-override"' in SERVER


def test_watch_has_two_screen_progress_and_prompt_revision_history():
    assert 'function watchProductionSurfaceHTML(' in APP
    assert '1 · APPROVED START' in APP
    assert '2 · WATCH RESULT' in APP
    assert 'const openingUrl=media.openingFrame||media.keyframe;' in APP
    assert 'Last frame from ${openingSource}' in APP
    assert 'function watchJobCopy(job)' in APP
    assert 'Polling Seedance API' in APP
    assert 'Submitted to Seedance 2.5' in APP
    assert 'Preparing the sealed Fire request' in APP
    assert 'role="status" aria-live="polite"' in APP
    assert 'function watchRevisionHistoryHTML(' in APP
    assert 'Why it was rejected' in APP
    assert 'Prompt recorded with rejection · attribution not verified here' in APP
    assert 'Working revision · requires review before Fire' in APP
    assert 'function durableWatchJob(led,shotId)' in APP
    assert 'const liveJob=activeWatchJob(shot.shotId),durableJob=durableWatchJob(led,shot.shotId);' in APP
    assert 'liveJob&&durableJob?{...liveJob,...durableJob' in APP
    assert 'Provider task ${job.providerTaskId}' in APP


def test_watch_discovers_server_jobs_after_reload_or_cross_tab_fire():
    assert 'id="watchResultState"' in APP
    assert 'id="watchResultMedia"' in APP
    assert 'function updateWatchLiveStatus(job)' in APP
    assert 'function _watchServerPollTick()' in APP
    assert 'await fetchJobsNow();' in APP
    assert 'const serverJob=shot?activeWatchJob(shot):null;' in APP
    assert 'const durableJob=shot?durableWatchJob(shLedger(shot),shot):null;' in APP
    assert 'const active=serverJob&&durableJob?{...serverJob,...durableJob' in APP
    assert 'SH_WATCH_POLL=setInterval(_watchServerPollTick,2500);' in APP
    assert 'startWatchServerPoll();' in APP
    assert 'function watchLiveProgressHTML(job,compact)' in APP
    assert 'const pendingEdit=media.edit&&media.edit.status==="candidate-pending"&&media.edit.candidateUrl;' in APP
    assert 'hasResult?`<div class="watch-live-results">${reviewResultHTML}</div>`' in APP
    assert 'watchLiveProgressHTML(job,hasResult)' in APP
    assert 'if(existing){existing.outerHTML=watchLiveProgressHTML' in APP


def test_interrupted_watch_batch_is_not_shown_as_still_rendering():
    assert "function interruptedWatchBatch(shotId,led)" in APP
    assert "if(shotId&&interruptedWatchBatch(shotId,led))return null" in APP
    assert "Render interrupted safely" in APP
    assert "Resume missing candidates" in APP
    assert "Interrupted · ready to resume" in APP


def test_producer_sees_director_intent_without_confusing_it_with_approval():
    assert 'function producerDirectionCardHTML(shot)' in APP
    assert 'Director’s intent' in APP
    assert 'Camera &amp; composition' in APP
    assert 'Lighting &amp; palette' in APP
    assert 'Acting &amp; audience read' in APP
    assert 'Judge the actual image, performance and finished take before approving.' in APP
    assert 'const producerDirection=producerDirectionCardHTML(s)' in APP


def test_saved_watch_review_failure_is_not_labelled_ready_or_left_as_raw_error():
    assert "operation.state==='needs-attention'" in APP
    assert 'return "Direction review needed"' in APP
    assert 'function watchOperationProducerCopy(operation)' in APP
    assert 'Review direction in DIRECT' in APP
    assert 'function watchPreflightFailureHTML(message,recovery)' in APP
    assert 'WATCH_PROMPT_REVIEW_REQUIRED' in APP


def test_top_corridor_keeps_completed_current_shot_phases_green():
    assert 'function corridorPhaseState(phase,stages)' in APP
    assert 'if(current.keyframe&&SH_STATE&&SH_STATE.sceneLook&&SH_STATE.sceneLook.current)return "approved";' in APP
    assert 'if(!policy.talky||current.voice)return "approved";' in APP
    assert 'if(current.animation)return "approved";' in APP
    assert 'corridorPhaseState(phase,stages)==="approved"' in APP
    assert '.pstage.done.active{border-color:var(--ok)' in APP


def test_missing_required_keyframe_never_presents_watch_as_ready():
    assert 'if(policy.needsKeyframe&&!current.keyframe)return "ready";' in APP
    assert 'if(phase.id==="see")return policy.pending&&policy.pending.keyframe?"Review keyframe":"Keyframe required";' in APP
    assert 'if(phase.id==="watch")return "Waiting for SEE";' in APP
    assert 'if(policy.needsKeyframe&&!current.keyframe){openShotOutcome("keyframe",PSHOT_I);return;}' in APP
    assert '// WATCH remains inspectable while it waits for SEE.' in APP


def test_fire_is_acknowledged_in_watch_before_the_first_job_poll():
    assert 'PJOBS[j.jobId]={jobId:j.jobId' in APP
    assert 'Submitting the sealed Seedance 2.5 request' in APP
    assert 'Preparing cost disclosure and sealed spend authorization' in APP
    assert 'renderWorking?"Seedance 2.5 is rendering":"Ready to generate"' in APP
    assert 'Rendering candidate batch…' in APP


def test_spend_disclosure_is_a_decision_not_a_failed_job():
    assert 'job["status"] = "done" if (p.returncode == 0 or spend_decision) else "failed"' in SERVER
    assert 'job["step"] = "Cost ready for approval"' in SERVER
    assert 'const disclosure=shIsSpendDecision(j);' in APP
    assert '${disclosure?"WATCH cost review":failureCopy?_esc(failureCopy.title):_esc(String(j.gate))}' in APP
    assert 'This cost-review step did not submit a generation.' in APP
    assert 'This REFUSED run is the designed disclosure step' not in APP


def test_watch_banner_uses_terminal_outcome_not_old_spend_text():
    import subprocess
    functions = APP[APP.index('function shFailureCopy('):APP.index('function closeM(')]
    program = 'const _esc=s=>String(s); const _attr=s=>String(s);\n' + functions + '''
const audit="SPEND DISCLOSURE — spend token issued; BYTEPLUS SUBMITTING";
const copyErrorButton=text=>`<button data-error-copy="${String(text)}">Copy error</button>`;
for (const status of ["running","finalizing","done","failed"]) {
  const outcome=status==="failed"?"failed":status==="done"?"completed":undefined;
  const html=shJobHTML({status,outcome,log:audit,gate:"shot:fire:S1.SH1"});
  if(html.includes("Ready for your approval"))throw Error(status+" mislabelled as cost review");
}
const cost=shJobHTML({status:"done",outcome:"needs_spend_approval",log:audit});
if(!cost.includes("Ready for your approval"))throw Error("real cost review missing");
const completed=shJobHTML({status:"done",outcome:"completed",log:audit,gate:"shot:build-keyframe:S4.SH2"});
const detailStart=completed.indexOf("<details");
if(!completed.includes("Studio update complete")||detailStart<0)throw Error("completion summary missing");
if(completed.slice(0,detailStart).includes(audit))throw Error("raw success log shown in producer view");
if(!completed.slice(detailStart).includes(audit)||/<details[^>]*open/.test(completed))throw Error("success log not available as collapsed evidence");
const failed=shJobHTML({status:"failed",outcome:"failed",step:"Cost ready for approval",log:audit});
if(failed.includes("Ready for your approval"))throw Error("stale step overrides failure");
'''
    result=subprocess.run(['node','-e',program],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_watch_readiness_repairs_stale_direction_before_fire():
    assert '"recompile-animation",' in SERVER
    assert '"repairAction": "recompile-animation"' in SERVER
    assert '"code": "animation-direction-repair"' in SERVER
    assert 'elif cmd == "recompile-animation":' in RENDER
    assert 'recompile_animation_candidate(pos[0], pos[1], ep(2))' in RENDER
    assert 'if(readiness.repairAction==="recompile-animation"&&!options.repairAttempt)' in APP
    assert 'shRun("recompile-animation",shotId' in APP
    assert 'Rebinding the current approved SEE, HEAR, geography and references locally.' in APP


def test_failed_jobs_show_plain_language_with_collapsed_technical_details():
    assert 'function shFailureCopy(j)' in APP
    assert 'title:"OpenAI direction credits unavailable"' in APP
    assert 'title:"HEAR timing needs attention"' in APP
    assert 'title:"Direction needs refreshing"' in APP
    assert 'title:"Specialist direction needs local repair"' in APP
    assert '>Technical details</summary>' in APP
    assert 'const technical=raw?' in APP


def test_see_asset_choices_are_clear_and_stale_keyframes_are_not_misrepresented():
    assert 'Generate · up to $' in APP
    assert 'Upload · free' in APP
    assert 'Library · free' in APP
    assert 'Shot direction updated · choose a refreshed image' in APP
    assert 'Choose how to create the opening keyframe' in APP
    assert 'sourceChoicesOnCards' in APP
    assert 'Choose Generate, Upload, or Library on the opening-frame card.' in APP


def test_storyboard_is_optional_and_current_director_count_uses_real_shot_plan():
    assert "Optional storyboard · ${count} planned views" in COVERAGE
    assert "const plannedViews=views.length||((shot.storyboardInternalShotPlanApproved||[]).length);" in APP
    assert "This shot · ${plannedViews} view" in APP


def test_see_asset_choices_are_clear_and_stale_keyframes_are_not_misrepresented():
    assert 'Generate · up to $' in APP
    assert 'Upload · free' in APP
    assert 'Library · free' in APP
    assert 'Shot direction updated · choose a refreshed image' in APP
    assert 'Choose how to create the opening keyframe' in APP
    assert 'sourceChoicesOnCards' in APP
    assert 'Choose Generate, Upload, or Library on the opening-frame card.' in APP


def test_watch_routes_a_failed_opening_stage_back_to_see():
    assert 'pst.kf==="stageBlocked"' in APP
    assert 'Return to See and correct the keyframe' in APP
    assert 'Create required SEE keyframe' in APP
    assert 'label:"Open Cinematography",onclick:"openStageOutcome(\'keyframe\')"' not in APP
    assert 'Image blocked · audio is ready' in APP
    assert 'Seedance SFX only · no @Audio1 required' in APP
    assert 'Audio is not blocking this shot.' in APP


def test_normal_watch_fire_never_selects_legacy_comparison_transport():
    fire_start = APP.index("function shRender(shotId,options)")
    fire_end = APP.index("function shApproveSpendFire", fire_start)
    production_fire = APP[fire_start:fire_end]
    assert "comparisonModelId" not in production_fire
    assert "comparisonRunId" not in production_fire
    assert "shRun('fire',shotId,{candidates:SH_CANDS" in production_fire
    assert "let SH_CANDS=1;" in APP


def test_scene_boot_uses_one_authoritative_state_and_preflight_response():
    fetcher = re.search(
        r"async function shFetchPkg\(\)\{(.*?)\n\}", APP, re.DOTALL
    )
    assert fetcher
    body = fetcher.group(1)
    assert 'j&&j.preflight&&!j.preflight.error?j.preflight:null' in body
    assert 'j&&j.productionState&&!j.productionState.error?j.productionState:null' in body
    assert '/api/production-preflight?' not in body
    assert '/api/production-state?' not in body
    assert '/api/studio-agent?' not in body
    assert '"preflight": preflight' in SERVER


def test_reference_and_pose_cards_stack_at_phone_width():
    mobile = re.search(r"@media \(max-width:700px\)\{(.*?)\n\}", APP, re.DOTALL)
    assert mobile
    assert ".refgrid{grid-template-columns:minmax(0,1fr)}" in mobile.group(1)


def test_keyframe_replacement_updates_inline_without_leaving_the_review_surface():
    assert 'SH_PRESERVE_VIEW={scrollY:window.scrollY,page,scene:String(SH_SC||""),stage:PSTAGE,shotId:shotId||null}' in APP
    assert 'shPollStart();if(page=="pipeline"&&!preserveView)renderControl();' in APP
    assert 'The current shot and references stay visible. This panel will update when the result is ready.' in APP
    assert 'window.scrollTo({top:preservedView.scrollY,left:0,behavior:"instant"})' in APP
    assert 'sourcePath,preserveView:true,progressLabel:sourceLabel' in APP
    assert 'return shRun(cmd,tok,{sourcePath,preserveView:true,progressLabel:sourceLabel})' in APP


def test_keyframe_screen_keeps_scene_plate_and_opening_frame_distinct():
    assert 'function visualAnchorPairHTML(media,decisionHTML="",handoffHTML="")' in APP
    anchor = APP[APP.index('function visualAnchorPairHTML('):APP.index('function seeHandoffHTML', APP.index('function visualAnchorPairHTML('))]
    assert anchor.index('class="scene-plate-actions"') < anchor.index('${decisionHTML}')
    assert anchor.index('class="visual-anchor scene-plate-anchor') < anchor.index('${handoffHTML}') < anchor.index('id="seeOpeningKeyframe"')
    assert "handoffHTML?'Scene plate, previous ending and opening keyframe':'Scene plate and opening keyframe'" in APP
    assert '1 · Scene plate' in APP
    assert 'The world and lighting' in APP
    assert "${handoffHTML?'3':'2'} · Opening keyframe" in APP
    assert 'Characters and first composition' in APP
    assert 'mode==="keyframe"?visualAnchorPairHTML(anchorMedia,keyframeReviewHTML,handoffReview):""' in APP
    assert 'Review this image below. Source choices unlock after your decision.' in APP
    assert 'role="group" aria-label="Review opening keyframe"' in APP
    assert 'keyframeActionsInline' in APP
    assert 'sourceChoicesOnCards,keyframeActionsInline' in APP
    disclosure = APP[APP.index('async function openDisclosureModal(kind,ctx)'):APP.index('function ', APP.index('async function openDisclosureModal(kind,ctx)') + 10)]
    assert 'already has a keyframe waiting for review. Choose Accept or Iterate; no new image was generated.' in disclosure


def test_see_stage_is_visual_first_and_demotes_repeated_context():
    assert 'resultFirst=mode==="keyframe"' in APP
    assert 'overview.innerHTML=sceneShotOverviewHTML()' in APP
    assert 'class="see-focus-title">Opening frame</div>' in APP
    assert '${visualAnchors}<div class="artefact-center see-supporting' in APP
    assert 'aria-label="Shot handoff guide"' in APP
    assert 'const openingBrief=transition.openingImage||shot.openingPose||shotFocusCopy' in APP
    assert 'Build a new opening keyframe' in APP
    assert 'Use the exact final frame' in APP
    assert 'Review ${_esc(source)} in WATCH →' in APP
    assert 'Choose Generate, Upload or Library' in APP
    assert 'The script and Director Card stay authoritative.' in APP
    assert '<details class="focus-evidence see-context"><summary>Shot brief &amp; continuity</summary>' in APP
    assert 'workspace.classList.toggle("see-workspace",mode==="keyframe")' in APP


def test_watch_producer_decision_is_moved_above_result_with_guarded_controls():
    assert APP.index('id="producer-primary-action"') < APP.index('id="railwrap"')
    start = APP.index('function mountWatchPrimaryAction(')
    end = APP.index('\nfunction scenePlateSourceActionsHTML', start)
    mount = APP[start:end]
    assert 'host.classList.add("watch-forward-action")' in mount
    assert 'source.querySelectorAll(".dec-actions")' in mount
    assert 'host.appendChild(movable)' in mount
    assert 'nextStep.style.display="none"' in mount
    assert 'mountWatchPrimaryAction(s,controls,decVersion);' in APP
    assert 'approveWatchTake' in APP and 'openWatchRetake' in APP
    assert 'data-watch-review-controls' in APP


def test_see_required_action_is_above_progress_and_preserves_review_controls():
    assert APP.index('id="producer-primary-action"') < APP.index('id="railwrap"')
    mount = APP[APP.index('function mountSeePrimaryAction('):APP.index('function scenePlateSourceActionsHTML', APP.index('function mountSeePrimaryAction('))]
    assert 'host.appendChild(decision)' in mount
    assert 'host.appendChild(sources)' in mount
    assert 'host.appendChild(review)' in mount
    assert 'source-updating' in mount
    assert 'if(mode==="keyframe")mountSeePrimaryAction(s,art,dec,decVersion,seeState);' in APP
    assert 'keyframeReviewHTML=keyframeReviewActionsHTML([approvedShotNextActionHTML(shots)]);' in APP
    assert 'source-updating",!!SH_PRESERVE_VIEW' in APP


def test_see_scene_plate_can_be_generated_uploaded_or_selected_from_library():
    assert 'function scenePlateSourceActionsHTML(hasPlate,isGenerating)' in APP
    assert 'aria-label="Change Scene Plate source"' in APP
    assert 'onclick="startScenePlateGeneration(${!!hasPlate})"' in APP
    assert 'id="seePlateUpload"' in APP and 'onchange="slUpload(this)"' in APP
    assert 'onclick="slLibrary()">Library · free</button>' in APP


def test_scene_plate_generation_stays_inside_the_see_plate_window():
    assert 'progressTarget:"scene-plate"' in APP
    assert 'id="scenePlateProgress"' in APP
    assert '${generating?"Generating":"Updating"} inside this Scene Plate window.' in APP
    assert 'if(isScenePlateJob(j))updateScenePlateLiveStatus(j);' in APP
    assert 'if(isScenePlateJob(j))SH_SCENE_PLATE_PROGRESS=null;' in APP


def test_scene_plate_library_replacement_archives_pending_candidate_first():
    assert 'function slSelectReplacement(cmd,sourcePath,progressLabel)' in APP
    assert "slSelectReplacement('select-scenelook-library',file" in APP
    assert "slSelectReplacement('select-scenelook-upload',j.sourcePath" in APP
    assert 'function reuseCurrentScenePlate()' in APP
    assert "select-scenelook-library',path" in APP
    assert 'shRun("reject-scenelook",null,{' in APP
    assert 'afterJob:job=>{if(job&&job.status==="done")install();}' in APP


def test_keyframe_cost_review_uses_durable_cinematography_direction():
    assert 'const inp=currentProductionDirection("cinematography",ctx.shotId);' in APP
    assert 'const keyframePrompt=inp&&(inp.keyframePrompt||inp.providerPrompt);' in APP
    assert 'inp.keyframePromptHeadline||inp.audienceRead||"A performance-ready opening stage"' in APP
    assert '${_esc(keyframePrompt)}</pre></details>' in APP


def test_keyframe_build_explains_pending_scene_plate_and_rebuilds_stale_direction():
    assert 'if(kind==="keyframe"&&!shSceneLookOk()){showKeyframeScenePlateHold();return;}' in APP
    assert 'The selected image is not current against this scene.' in APP
    assert '>Review Scene Plate</button>' in APP
    assert 'signature.sceneLookHash!==currentPlateHash' in APP
    assert 'SH_SCENELOOK.active&&SH_SCENELOOK.active.hash' in APP
    assert 'record.packageRevision' in APP
    assert 'The current plate stays protected until you approve its replacement.' in APP


def test_keyframe_confirmation_refreshes_and_requires_build_readiness():
    modal = APP.split('async function openDisclosureModal(kind,ctx){', 1)[1]
    keyframe = modal.split('} else if(kind=="keyframe"){', 1)[1].split(
        '} else if(kind=="voice"){', 1)[0]
    assert 'await shLoadReferences(ctx.shotId,true);' in keyframe
    assert 'if(build.buildable!==true)' in keyframe
    assert keyframe.index('if(build.buildable!==true)') < keyframe.index(
        "shRun('build-keyframe',ctx.shotId)")
    assert 'const openingNeedsPreparation=build.state==="needs-preparation";' in APP
    assert 'Upload and Library remain available.' in APP


def test_scene_plate_generate_iterates_a_pending_candidate_before_disclosure():
    assert 'function startScenePlateGeneration(regenerate)' in APP
    assert 'SH_SCENELOOK.candidate||SH_SCENELOOK.activeSource==="working"||SH_SCENELOOK.status==="working"' in APP
    assert 'shRun("reject-scenelook",null,{' in APP
    assert 'Moving the current Scene Plate candidate to History' in APP
    assert "openDisclosureModal('scenelook',{regenerate:true})" in APP
    assert 'No generation starts until you review the cost' in APP
    assert 'groups.push(["Your supplied scene plates",uploaded])' in APP


def test_keyframe_reference_images_stay_visible_below_opening_frame():
    assert 'return `${referencePanel}${checks?' in APP
    assert '${visualAnchors}${referenceHTML}<div class="artefact-center see-supporting' in APP
    assert '<summary>Acting poses &amp; local checks' in APP


def test_completed_job_dismissal_persists_by_job_id():
    assert 'localStorage.setItem("cb_dismissed_job:"+id,"1")' in APP
    assert 'localStorage.getItem("cb_dismissed_job:"+lastJobId)' in APP


def test_keyframe_confirmation_formats_multi_provider_model_ids():
    assert 'Object.entries(build.providerModelId).map(([key,value])=>key+" · "+value).join(" + ")' in APP


def test_stale_voice_take_cannot_be_approved_against_corrected_words():
    assert "takeMatchesCurrent===false" in APP
    assert "Regenerate corrected performance" in APP
    assert "cannot be approved against the corrected words" in APP


def test_fire_uses_durable_department_direction_during_preflight_cache_lag():
    direction_start = APP.index("function currentProductionDirection")
    direction_end = APP.index("function directionLabel", direction_start)
    direction = APP[direction_start:direction_end]
    assert "const led=shotId?shLedger(shotId):null" in direction
    assert "[work.candidate,work.approved].filter(Boolean)" in direction
    assert "animationPrompt:output.providerPrompt" in direction

    modal_start = APP.index("function openAnimationConfirmModal")
    modal_end = APP.index("function openTimingReviewModal", modal_start)
    modal = APP[modal_start:modal_end]
    assert 'currentProductionDirection("animation",shotId)' in modal


def test_working_prompt_keeps_current_animation_candidate_valid():
    signature_start = RENDER.index("def _seedance_working_input_signature")
    signature_end = RENDER.index("def _resolve_seedance_prompt", signature_start)
    signature = RENDER[signature_start:signature_end]
    assert "except Refused:" in signature
    assert 'record = work.get("candidate") or work.get("approved") or {}' in signature

    save_start = RENDER.index("def save_seedance_working")
    save_end = RENDER.index("def restore_seedance_working", save_start)
    save = RENDER[save_start:save_end]
    assert 'direction_record = work.get("candidate") or work.get("approved")' in save
    assert 'direction_record["manualCurrentOverride"] = True' in save

    restore_start = save_end
    restore_end = RENDER.index("def save_watch_director_feedback", restore_start)
    restore = RENDER[restore_start:restore_end]
    assert 'direction_record.pop("manualCurrentOverride", None)' in restore


def test_visible_pipeline_tab_refetches_authoritative_production_state():
    start = APP.index("async function refreshVisibleProductionState")
    refresh = APP[start:APP.index("</script>", start)]
    assert 'document.visibilityState!=="visible"' in refresh
    assert 'page!=="pipeline"' in refresh
    assert "await renderControl()" in refresh
    assert 'document.addEventListener("visibilitychange",refreshVisibleProductionState)' in refresh
    assert 'window.addEventListener("focus",refreshVisibleProductionState)' in refresh


def test_department_endpoint_reuses_current_approved_direction():
    endpoint = SERVER[SERVER.index('if self.path == "/api/department-run"'):]
    endpoint = endpoint[:endpoint.index('if self.path == "/api/director-chat"')]
    assert 'status.get("directionReady")' in endpoint
    assert '"existing": True' in endpoint


def test_scene_queue_uses_recommended_cut_without_hiding_a_real_cut_blocker():
    import subprocess
    function = APP[APP.index('function sceneCardStatus('):APP.index('function badge(')]
    program = function + '''
const stages={scenelook:{state:"blocked"},animation:{state:"approved"},
              continuity:{state:"ready"},final:{state:"locked"}};
if(sceneCardStatus(stages,"continuity")!=="needs-decision")throw Error("accepted cut hidden by draft");
if(sceneCardStatus(stages)!=="blocked")throw Error("draft blocker disappeared");
stages.continuity.state="blocked";
if(sceneCardStatus(stages,"continuity")!=="blocked")throw Error("cut integrity blocker disappeared");
'''
    subprocess.run(['node', '-e', program], check=True, capture_output=True, text=True)
