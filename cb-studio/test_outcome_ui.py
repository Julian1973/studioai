import re
from pathlib import Path


APP = (Path(__file__).parent / "app.html").read_text(encoding="utf-8")
SERVER = (Path(__file__).parent / "serve.py").read_text(encoding="utf-8")
RENDER = (Path(__file__).parent.parent / "engine" / "cb_render.py").read_text(encoding="utf-8")
INTAKE = (Path(__file__).parent.parent / "engine" / "cb_intake.py").read_text(encoding="utf-8")


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
    assert 'Direction and SEE preserved; HEAR and WATCH reopened' in APP
    assert '&st=voice&shot=' in APP
    assert 'location.reload();' not in re.search(
        r"async function shCorrectDialogue\(.*?\n\}", APP, re.DOTALL
    ).group(0)


def test_dialogue_correction_registry_sync_is_verified_before_intake():
    assert "def synchronize_episode_script_registry(" in SERVER
    assert 'actual != expected_script_version_id' in SERVER
    assert 'episode registry synchronization failed for {episode}' in SERVER


def test_hear_exposes_words_and_provider_prompt_as_separate_editable_layers():
    assert "1 · Approved spoken words" in APP
    assert "2 · ElevenLabs v3 performance prompt" in APP
    assert "Changing them creates a scoped dialogue revision for this shot" in APP
    assert "Adapt phonetic spelling, pronunciation, cadence, pauses, breath" in APP
    assert "Save ElevenLabs prompt" in APP
    assert "voicePanelHTML(tok,SH_VOICE_CACHE[tok])" in APP
    assert "await shLoadVoiceWork(tok)" in APP


def test_keyframe_review_decision_rail_exposes_upload_and_library_sources():
    assert "function keyframeDecisionSourceActions(tok)" in APP
    assert "Upload replacement keyframe" in APP
    assert "Choose library image" in APP
    assert "pending?keyframeDecisionSourceActions(tok)" in APP
    assert "keyframeDecisionSourceActions(tok)];" in APP
    assert "function shSelectReplacementKeyframe(cmd,tok,sourcePath)" in APP
    assert "Replace the current keyframe revision?" in APP
    assert 'correction:"Replaced by a different keyframe source selected by Julian."' in APP
    assert 'if(job&&job.status==="done")shRun(cmd,tok,{sourcePath,preserveView:true,progressLabel:sourceLabel})' in APP
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
    assert 'return nextSceneActionHTML("shot");' in APP
    assert 'nextSceneActionHTML("scene")' in APP
    assert "Finish scene then continue to Scene" in APP
    assert "Continue to Scene" in APP


def test_stale_story_direction_keeps_carried_scene_work_visible():
    assert "def carried_scene_roster(episode):" in INTAKE
    assert '"carriedScenes": carried_scene_roster(episode)' in INTAKE
    assert "j.carriedScenes||[]" in APP
    assert "Recovered production" in APP
    assert "Earlier scene work is still here" in APP


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
    assert 'subprocess.Popen(["python3", "-u"] + args' in SERVER
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


def test_fire_prepares_internal_direction_then_returns_to_the_visible_outcome():
    assert "function currentProductionDirection(stage,shotId)" in APP
    assert "async function prepareDirectionThen(stage,shotId,resume)" in APP
    assert "No separate approval is required" in APP
    assert "No media is being generated and no media spend can occur in this step" in APP
    assert 'prepareDirectionThen(directionStage,ctx.shotId,()=>openDisclosureModal(kind,ctx))' in APP
    assert 'prepareDirectionThen("animation",shotId,()=>shRender(shotId))' in APP
    assert "SH_AFTER_JOB" in APP
    assert '>Fire candidates</button>' in APP
    assert "Seedance 2.5 prompt preflight" in APP
    assert "Contract completeness" in APP
    assert "Creative direction" in APP
    assert "Firing floor:" in APP
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
    assert "Your performance direction is ready" in APP
    assert "Step 1 of 2: confirm the exact words below. Step 2: review cost and press Fire voice." in APP
    assert "Save corrected words" in APP
    assert "data-hear-fire" in APP
    assert "A provider job starts only after the final Fire voice confirmation." in APP
    assert "Review cost &amp; fire voice" in APP
    assert "Final confirmation · generate voice" in APP
    assert "Performance direction ready — audio not generated" in APP
    assert 'openDisclosureModal(\'voice\',{shotId:\'${tok}\'})' in APP
    assert '<audio controls preload="metadata"' in APP


def test_completed_audio_sits_between_progress_and_scene_shots():
    rail = '<div id="railwrap">${renderStageRail()}</div>'
    audio = '<div id="sceneaudio">${completedSceneAudioHTML()}</div>'
    shots = '<div id="shotoverview">${sceneShotOverviewHTML()}</div>'
    assert rail in APP and audio in APP and shots in APP
    assert APP.index(rail) < APP.index(audio) < APP.index(shots)
    assert 'class="scene-audio-strip"' in APP
    assert 'if(!media.vo)return ""' in APP
    assert "openStageOutcome('voice')" in APP
    assert "sceneAudio.innerHTML=completedSceneAudioHTML()" in APP


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
    assert "References &amp; checks" in APP
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
    assert 'return `<div class="wcol-head">Your decision</div>' in APP


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
    assert '<details class="focus-evidence" open><summary>1 · Approved spoken words</summary>' in APP
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
    assert 'workspace.classList.toggle("result-first",resultFirst)' in APP


def test_identity_screening_keeps_the_keyframe_visible_for_review():
    assert 'resultFirst=true;keyframeAnchorOwnsCurrent=!!(pending&&m.keyframe)' in APP
    assert 'keyframeRevisionMedia(m.keyframe,led,s,"NEEDS YOUR DECISION")' in APP
    assert 'approveKeyframeAdvisory' in APP
    assert 'Approve revision ${kfInfo.revision}' in APP
    assert 'approveKeyframeAdvisory' in APP
    assert 'hard canon, reference, lineage and file-integrity checks' in APP.lower()
    assert "directorStartRejection('keyframe'" in APP
    assert 'class="review-warning"' in APP


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
    assert 'Approve revision ${kfInfo.revision}' in APP
    assert 'Discuss / change revision ${kfInfo.revision}' in APP
    assert 'PREVIOUS · REJECTED' in APP
    assert 'No current keyframe yet.' in APP


def test_conversational_director_is_present_on_every_decision_surface():
    assert '<div id="director-chat-host">${directorChatHTML()}</div>' in APP
    assert '✦ Ask Director' in APP
    assert 'class="director-chat-backdrop"' in APP
    assert 'role="dialog" aria-modal="true"' in APP
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
    assert 'directorStartRejection(\'voice\'' in APP
    assert 'directorStartRejection(\'animation\'' in APP
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
    assert 'Prompt used by rejected take' in APP
    assert 'Corrected prompt prepared for the next fire' in APP
    assert 'function durableWatchJob(led)' in APP
    assert 'const liveJob=activeWatchJob(shot.shotId),durableJob=durableWatchJob(led);' in APP
    assert 'liveJob&&durableJob?{...liveJob,...durableJob' in APP
    assert 'Provider task ${job.providerTaskId}' in APP


def test_watch_discovers_server_jobs_after_reload_or_cross_tab_fire():
    assert 'id="watchResultState"' in APP
    assert 'id="watchResultMedia"' in APP
    assert 'function updateWatchLiveStatus(job)' in APP
    assert 'function _watchServerPollTick()' in APP
    assert 'await fetchJobsNow();' in APP
    assert 'const serverJob=shot?activeWatchJob(shot):null;' in APP
    assert 'const durableJob=shot?durableWatchJob(shLedger(shot)):null;' in APP
    assert 'const active=serverJob&&durableJob?{...serverJob,...durableJob' in APP
    assert 'SH_WATCH_POLL=setInterval(_watchServerPollTick,2500);' in APP
    assert 'startWatchServerPoll();' in APP
    assert 'function watchLiveProgressHTML(job,compact)' in APP
    assert 'hasResult?`<div class="watch-live-results">${resultHTML}</div>`' in APP
    assert 'watchLiveProgressHTML(job,hasResult)' in APP
    assert 'if(existing){existing.outerHTML=watchLiveProgressHTML' in APP


def test_top_corridor_keeps_completed_current_shot_phases_green():
    assert 'function corridorPhaseState(phase,stages)' in APP
    assert 'if(current.keyframe&&SH_STATE&&SH_STATE.sceneLook&&SH_STATE.sceneLook.current)return "approved";' in APP
    assert 'if(!policy.talky||current.voice)return "approved";' in APP
    assert 'if(current.animation)return "approved";' in APP
    assert 'corridorPhaseState(phase,stages)==="approved"' in APP
    assert '.pstage.done.active{border-color:var(--ok)' in APP


def test_fire_is_acknowledged_in_watch_before_the_first_job_poll():
    assert 'PJOBS[j.jobId]={jobId:j.jobId' in APP
    assert 'Submitting the sealed Seedance 2.5 request' in APP
    assert 'Preparing cost disclosure and sealed spend authorization' in APP
    assert 'renderWorking?"Seedance 2.5 is rendering":"Ready to generate"' in APP
    assert 'Rendering candidate batch…' in APP


def test_watch_routes_a_failed_opening_stage_back_to_see():
    assert 'pst.kf==="stageBlocked"' in APP
    assert 'Return to See and correct the keyframe' in APP
    assert 'Image blocked · audio is ready' in APP
    assert 'Seedance SFX only · no @Audio1 required' in APP
    assert 'Audio is not blocking this shot.' in APP


def test_normal_watch_fire_never_selects_legacy_comparison_transport():
    fire_start = APP.index("function shRender(shotId)")
    fire_end = APP.index("function shApproveSpendFire", fire_start)
    production_fire = APP[fire_start:fire_end]
    assert "comparisonModelId" not in production_fire
    assert "comparisonRunId" not in production_fire
    assert "shRun('fire',shotId,{candidates:SH_CANDS" in production_fire
    assert "let SH_CANDS=2;" in APP


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
    assert 'preserveView:true,progressLabel:"Moving the current revision to History"' in APP


def test_keyframe_screen_keeps_scene_plate_and_opening_frame_distinct():
    assert 'function visualAnchorPairHTML(media)' in APP
    assert 'aria-label="Scene plate and opening keyframe"' in APP
    assert '1 · Scene plate' in APP
    assert 'The world and lighting' in APP
    assert '2 · Opening keyframe' in APP
    assert 'Characters and first composition' in APP
    assert 'mode==="keyframe"?visualAnchorPairHTML(anchorMedia):""' in APP


def test_see_stage_is_visual_first_and_demotes_repeated_context():
    assert 'resultFirst=mode==="keyframe"' in APP
    assert 'overview.innerHTML=stage==="keyframe"?"":sceneShotOverviewHTML()' in APP
    assert 'class="see-focus-title">Opening frame</div>' in APP
    assert '${visualAnchors}<div class="artefact-center see-supporting' in APP
    assert '${referenceHTML}<details class="focus-evidence see-context"><summary>Shot brief &amp; continuity</summary>' in APP
    assert 'workspace.classList.toggle("see-workspace",mode==="keyframe")' in APP


def test_see_scene_plate_can_be_generated_uploaded_or_selected_from_library():
    assert 'function scenePlateSourceActionsHTML(hasPlate,isGenerating)' in APP
    assert 'aria-label="Change Scene Plate source"' in APP
    assert 'onclick="startScenePlateGeneration(${!!hasPlate})"' in APP
    assert 'id="seePlateUpload"' in APP and 'onchange="slUpload(this)"' in APP
    assert 'onclick="slLibrary()">Use library</button>' in APP


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
    assert 'shRun("reject-scenelook",null,{' in APP
    assert 'afterJob:job=>{if(job&&job.status==="done")install();}' in APP
    assert 'The current plate stays protected until you approve its replacement.' in APP


def test_scene_plate_generate_iterates_a_pending_candidate_before_disclosure():
    assert 'function startScenePlateGeneration(regenerate)' in APP
    assert 'SH_SCENELOOK.candidate||SH_SCENELOOK.activeSource==="working"||SH_SCENELOOK.status==="working"' in APP
    assert 'shRun("reject-scenelook",null,{' in APP
    assert 'Moving the current Scene Plate candidate to History' in APP
    assert "openDisclosureModal('scenelook',{regenerate:true})" in APP
    assert 'No generation starts until you review the cost' in APP
    assert 'groups.push(["Your supplied scene plates",uploaded])' in APP


def test_keyframe_references_remain_open_during_live_polling():
    assert 'return `<details class="techdetails" open><summary>References &amp; checks' in APP


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
    assert "work.candidate||work.approved" in direction
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
