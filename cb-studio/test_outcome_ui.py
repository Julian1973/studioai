import re
from pathlib import Path


APP = (Path(__file__).parent / "app.html").read_text(encoding="utf-8")
SERVER = (Path(__file__).parent / "serve.py").read_text(encoding="utf-8")


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
        "Build a corrected keyframe below",
        "Redesign with Animation Director",
        "Open next unfinished shot",
        "focusShotReview",
        "Continue to Final Master",
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
    assert '>Build Scene World</button>' in APP
    assert '>Continue to First Keyframe</button>' in APP
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


def test_internal_direction_is_not_a_fake_human_approval_gate():
    assert "Direction ready" in APP
    assert "Its proof is the next rendered outcome" in APP
    assert "Approve direction" not in APP
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
    assert 'if(!confirm("PAID BATCH' not in APP
    assert "✓ Accept keyframe" in APP
    assert "Iterate batch" in APP


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
    assert '<details class="focus-evidence"><summary>Exact dialogue and performance notes</summary>' in APP


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
    assert '"Creative direction"' in APP


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
