from pathlib import Path


HERE = Path(__file__).resolve().parent
HTML = (HERE / "director.html").read_text(encoding="utf-8")
CSS = (HERE / "director.css").read_text(encoding="utf-8")
JS = (HERE / "director.js").read_text(encoding="utf-8")
SERVER = (HERE / "serve.py").read_text(encoding="utf-8")
ROOM = (HERE / "room.html").read_text(encoding="utf-8")
BOARD = (HERE / "board.html").read_text(encoding="utf-8")
ROOM_INSTRUCTION = (HERE / "CODEX_ROOM_INSTRUCTION.md").read_text(encoding="utf-8")
UX_CONTRACT = (HERE / "UX_CONTRACT.md").read_text(encoding="utf-8")
GOLDEN_BROWSER = (HERE / "golden_path_browser.mjs").read_text(encoding="utf-8")
PUSH_GATE = (HERE.parent / "scripts" / "verify_push.sh").read_text(encoding="utf-8")
PRE_PUSH = (HERE.parent / ".githooks" / "pre-push").read_text(encoding="utf-8")


def test_seven_ux_laws_are_the_versioned_interface_contract():
    headings = [line for line in UX_CONTRACT.splitlines() if line.startswith("## ")]
    laws = [line for line in headings if line[3:4].isdigit()]
    assert len(laws) == 7
    for phrase in (
        "One location truth", "One current decision", "Literal production state",
        "Immediate, refresh-free acknowledgement", "human owns every sign-off",
        "Refusals are honest and actionable", "Continuity survives time",
    ):
        assert phrase.lower() in UX_CONTRACT.lower()
    assert "launch -> SEE -> HEAR -> WATCH -> verdict" in UX_CONTRACT


def test_golden_path_browser_is_the_push_gate():
    for evidence in (
        "launch -> SEE -> HEAR -> WATCH -> verdict",
        "Fix voice setup", "mainNavigations", "save-retake-note",
        "accept-keyframe", "accept-voice", "approve-spend", "accept-animation",
    ):
        assert evidence in GOLDEN_BROWSER
    assert "golden_path_browser.mjs" in PUSH_GATE
    assert "test_local_auth.py" in PUSH_GATE
    assert "test_director_ui.py" in PUSH_GATE
    assert "scripts/verify_push.sh" in PRE_PUSH


def test_director_includes_anyfilm_style_pipeline_plus_outcome_views():
    for view in ("pipeline", "episodes", "director", "review"):
        assert f'id="view-{view}"' in HTML
        assert f'data-view="{view}"' in HTML
    for step in ("Upload", "Style", "Analysis", "Characters", "Props", "Locations", "Storyboard", "Footage", "Audio", "Rough Cut"):
        assert step in HTML
    assert "Houses" not in HTML
    assert "Departments" not in HTML
    assert "Scene creation path" not in HTML


def test_frontend_consumes_one_authoritative_director_state_and_action_route():
    assert "/api/director-session?" in JS
    assert 'api("/api/director-action"' in JS
    assert 'credentials: "same-origin"' in JS
    for internal_route in (
        "/api/production-preflight", "/api/production-state", "/api/shot-package",
        "/api/department-run", "/api/shot-run",
    ):
        assert internal_route not in JS
    assert "allowed_action_ids(session)" in SERVER
    assert "That action is no longer current" in SERVER


def test_studio_room_is_allowlisted_and_uses_the_claude_proxy_contract():
    assert '"/cb-studio/room.html"' in SERVER
    assert 'if self.path == "/api/room-chat":' in SERVER
    assert '"model": "claude-opus-5"' in SERVER
    assert '"max_tokens": int(payload.get("max_tokens") or 2048)' in SERVER
    assert '"system": system' in SERVER
    assert "isinstance(system, list)" in SERVER
    assert 'return {"text": text}' in SERVER
    assert "system untouched" in ROOM_INSTRUCTION
    assert "claude-opus-5" in ROOM_INSTRUCTION
    assert '{"text": "..."}' in ROOM_INSTRUCTION
    assert "/api/room-chat" in ROOM
    assert "system: systemBlocks(gate, u)" in ROOM


def test_studio_board_is_allowlisted_and_reads_real_shot_media_urls():
    assert '"/cb-studio/board.html"' in SERVER
    assert "/api/director-session?episode=" in BOARD
    assert "s.keyframeUrl||s.imageUrl||null" in BOARD
    assert "s.clipUrl||s.url||null" in BOARD
    assert 'a.type==="video-set"' in BOARD
    assert "no artifact yet" in BOARD
    assert "def _expose_session_shot_media(session, media):" in SERVER
    assert 'shot.setdefault("keyframeUrl", keyframe_url)' in SERVER
    assert 'shot.setdefault("imageUrl", keyframe_url)' in SERVER
    assert 'shot.setdefault("clipUrl", clip_url)' in SERVER
    assert 'shot.setdefault("acceptedUrl", clip_url)' in SERVER


def test_studio_room_verdicts_map_to_current_director_actions_and_rejects_send_notes():
    expected_actions = (
        "accept-keyframe", "iterate-keyframe", "accept-voice", "iterate-voice",
        "accept-animation", "iterate-animation", "reopen-shot",
        "accept-master", "iterate-master",
    )
    for action_id in expected_actions:
        assert action_id in SERVER
    assert "function pipeActions()" in ROOM
    assert "function resolvePipeAction(verdict)" in ROOM
    assert "const want = verdict===\"PASS\"" in ROOM
    assert "await pipeAct(act, v===\"REJECT\" ? text.trim() : undefined)" in ROOM
    assert "body.note = reason" in ROOM
    assert 'if not note:' in SERVER


def test_exact_request_is_separate_and_named_authoritative():
    assert 'id="request-drawer"' in HTML
    assert "Exact provider request" in HTML
    assert "app.session?.inspector?.providerRequest" in JS
    assert "shot.seedancePrompt" not in JS
    assert "keyframePrompt" not in JS


def test_watch_shows_new_prepared_prompt_without_authorizing_render():
    assert ("return session.inspector?.preparedAnimationRequest || "
            "session.inspector?.providerRequest || null;") in JS
    assert '$$("#request-button").disabled' not in JS
    assert '$("#request-button").disabled = !session.inspector?.providerRequest;' in JS


def test_references_are_available_for_keyframe_and_animation_without_clutter():
    assert 'data-reference-stage="keyframe"' in HTML
    assert 'data-reference-stage="animation"' in HTML
    assert "/api/shot-references?" in JS
    assert 'id="reference-dialog"' in HTML
    assert not ('id="reference-dialog" open' in HTML)
    assert "Complete uncropped 360 turnaround" in JS


def test_generated_keyframe_can_be_enlarged_and_zoomed_before_signoff():
    assert 'id="keyframe-preview-dialog"' in HTML
    assert 'id="keyframe-preview-image"' in HTML
    assert 'id="keyframe-zoom-out"' in HTML
    assert 'id="keyframe-zoom-reset"' in HTML
    assert 'id="keyframe-zoom-in"' in HTML
    assert 'aria-label="Enlarge keyframe"' in JS
    assert 'data-keyframe-preview' in JS
    assert "openKeyframePreview(button.dataset.keyframePreview)" in JS
    assert "Math.min(3, Math.max(.5, nextZoom))" in JS
    assert ".relay-keyframe-preview" in CSS
    assert ".keyframe-preview-viewport" in CSS


def test_mobile_navigation_is_always_reachable_and_safe_area_aware():
    assert 'class="mobile-nav"' in HTML
    assert 'data-view="director"><span aria-hidden="true">01</span>Shot' in HTML
    assert "env(safe-area-inset-bottom)" in CSS
    assert "@media (max-width: 720px)" in CSS
    assert ".mobile-nav { position: fixed" in CSS
    assert "hamburger" not in HTML.lower()
    assert "mobile-menu" not in HTML.lower()


def test_visual_system_is_neutral_premium_and_uses_real_media():
    assert "gradient" not in CSS.lower()
    assert "aspect-ratio: 16 / 9" in CSS
    assert "object-fit: contain" in CSS
    assert "border-radius: 6px" in CSS
    assert "/engine/media/" not in HTML
    assert "renderArtifact(session)" in JS


def test_rendering_has_persistent_honest_progress_feedback():
    assert "renderProgress(session)" in JS
    assert "formatRenderElapsed" in JS
    assert "latestMessage" in JS
    assert "does not supply a reliable completion percentage or ETA" in JS
    assert ".render-progress-track" in CSS
    assert "@keyframes render-scan" in CSS
    assert ".media-stage:has(.render-progress)" in CSS
    assert '"Submitting the approved Seedance request..."' in JS
    assert 'const preparingRetry = action.id === "iterate-animation"' in JS
    assert "actionActivityCopy(action, previousSession, preparingRetry)" in JS
    assert "Keyframe build in progress" in JS
    assert "This is the still stage. No Seedance animation render has been submitted." in JS
    assert "No provider spend is occurring yet" in JS
    assert "const previousSession = app.session" in JS
    assert "renderGenerateStatus(session)" in JS
    assert "setLocalActivity(activity)" in JS
    assert "data-activity-elapsed" in JS
    assert 'state: "held"' in JS
    assert "Seedream returned a frame, but QC did not pass it." in JS
    assert "Working..." in JS
    assert ".generate-status" in CSS
    assert ".generate-status.held" in CSS
    assert "render-ready-panel" in JS
    assert "Request prepared" in JS
    assert "Render 480p" in JS
    assert "Sealed request awaiting your approval" in JS
    assert "No video is rendering yet." in JS
    assert "Approve $${cost} & render" in JS
    assert "Request sealed" in JS
    assert ".render-ready-panel" in CSS


def test_every_director_action_gets_immediate_visible_feedback():
    submit_start = JS.index("async function submitAction")
    submit_end = JS.index("async function openReferences")
    submit_body = JS[submit_start:submit_end]
    assert "const activity = {" in submit_body
    assert "setLocalActivity(activity)" in submit_body
    assert "renderDirector(app.session)" in submit_body
    assert "if (showsGenerateStatus)" not in submit_body
    assert 'status: "rendering"' in submit_body
    assert "holdLocalActivity(action, previousSession, error.message, \"Action refused\")" in submit_body
    assert "holdLocalActivity(action, previousSession, message, \"Action failed\")" in submit_body
    assert 'app.localActivity.state === "held"' in JS
    assert 'const serverJob = session.runningJob' in JS
    assert 'Still working. Live status remains on this shot.' in JS
    assert "async function pollLiveSession()" in JS
    assert "session.status === \"rendering\" ? 1600 : 4500" in JS
    assert "Accepting keyframe" in JS
    assert "Locking this frame as the shot truth" in JS
    assert "No provider generation or spend is occurring" in JS
    assert "Keyframe accepted. HEAR is now active." in JS


def test_director_decisions_survive_expensive_authoritative_checks():
    assert 'async function api(path, options, timeoutMs = path === "/api/director-action" ? 60000 : 15000)' in JS
    assert 'api("/api/director-action", {' in JS
    assert "}, 60000);" in JS
    assert "The Studio is still checking this decision" in JS
    assert 'timedOut.code = path === "/api/director-action" ? "DIRECTOR_ACTION_TIMEOUT"' in JS
    assert 'error.code === "DIRECTOR_ACTION_TIMEOUT"' in JS
    assert "setTimeout(loadSession, 500)" in JS
    assert JS.count("${shot}`, undefined, 60000)") == 2
    assert JS.count("shotId=${encodeURIComponent(session.selectedShotId)}`, undefined, 60000)") == 1
    assert JS.count("shotId=${encodeURIComponent(app.session.selectedShotId)}`, undefined, 60000)") == 1
    action_route = SERVER[SERVER.index('if self.path == "/api/director-action"'):]
    session_check = action_route[:action_route.index('if action in ("open-inspector"')]
    assert "session = _cached_director_session(scene, ep, shot_id)" in session_check
    assert "_clear_director_session_cache(scene=scene, episode=ep)" not in session_check


def test_duplicate_and_background_session_reads_do_not_compete():
    assert "_DIRECTOR_SESSION_BUILD_LOCK = threading.Lock()" in SERVER
    assert "with _DIRECTOR_SESSION_BUILD_LOCK:" in SERVER
    assert "_DIRECTOR_SESSION_CACHE_TTL_SEC = 3600.0" in SERVER
    assert 'document.visibilityState !== "visible"' in JS
    assert "setTimeout(pollLiveSession, 15000)" in JS
    assert 'document.addEventListener("visibilitychange"' in JS
    assert "Reconnecting to Studio state" in JS
    assert "Retrying automatically..." in JS
    assert "app.pollTimer = setTimeout(loadSession, 2000)" in JS


def test_voice_contract_failure_is_contained_in_hear_instead_of_losing_studio():
    assert '"code": "VOICE_PROMPT_CONTRACT"' in SERVER
    assert '"stage": "voice"' in SERVER
    assert '"action": "Correct and prepare current Voice direction."' in SERVER
    assert "except (cb_render.Refused, ValueError) as exc:" in SERVER


def test_success_is_published_only_after_director_cache_refresh():
    finalizing = SERVER.index('job["status"] = "finalizing"')
    clear_cache = SERVER.index("_clear_director_session_cache(scene=job_scene)", finalizing)
    done = SERVER.index('job["status"] = "done"', clear_cache)
    assert finalizing < clear_cache < done
    assert '!["running", "queued", "finalizing"].includes(job.status)' in JS


def test_keyframe_refire_is_one_visible_replacement_job():
    assert 'action.id === "iterate-keyframe"' in JS
    assert "Keyframe refire in progress" in JS
    assert "Seedream is generating the replacement" in JS
    assert '"cb_studio_director.py", "refire-keyframe"' in SERVER
    assert 'f"director:refire-keyframe:{target}"' in SERVER


def test_director_action_area_explains_current_outcome_before_button():
    assert "actionGuidance(session)" in JS
    assert "Creates one keyframe candidate for this shot." in JS
    assert "No animation render is submitted at this stage." in JS
    assert "Review cost, references and prompt before pressing Render." in JS
    assert ".action-guidance" in CSS
    assert "Current Shot" in HTML


def test_current_shot_has_inline_creation_and_animation_inputs():
    assert 'id="shot-inputs"' in HTML
    assert "renderShotInputs(session)" in JS
    assert "loadInlineShotContext(session)" in JS
    assert "currentReferenceStage(session)" in JS
    assert "Scene Plate" in JS
    assert "Character Turnarounds" in JS
    assert "Exact Prompt" in JS
    assert "preparedAnimationRequest" in JS
    assert "WATCH direction ready" in JS
    assert "HEAR is approved. Compile the current provider request" in JS
    assert "Complete HEAR before render preparation or spend." in JS
    assert 'session.inspector?.packageRevision || ""' in JS
    assert 'session.status === "rendering" && stage === relayStage(session)' in JS
    assert '${session.status === "rendering" ? "" : renderGenerateStatus(session)}' in JS
    assert 'if (session.status === "rendering") {\n      return renderProgress(session);\n    }' not in JS
    assert "Complete uncropped turnaround · identity authority" in JS
    assert "final accepted frame becomes the handoff truth for the next shot" in JS
    assert "Create the still frame first" in JS
    assert "Animation uses the signed keyframe" in JS
    assert ".shot-inputs" in CSS
    assert ".shot-prompt-panel pre" in CSS
    assert ".shot-input-ref-grid" in CSS
    assert "watch-conformance-20260810-2" in HTML


def test_client_bundle_has_no_fabricated_clip_fallbacks_or_banned_canon():
    client_bundle = "\n".join((HTML, CSS, JS)).lower()
    banned = (
        "pollen" + " sacks",
        "zenny " + "laughs",
    )
    for phrase in banned:
        assert phrase not in client_bundle
    assert "const storyboardShots" not in JS
    assert "const footageClips" not in JS
    assert "footageClips.map" not in JS
    assert "No clips yet." in JS


def test_watch_shows_authoritative_emission_score_verdict_and_findings():
    assert "renderEmissionConformance(providerRequest)" in JS
    assert "Emission pre-flight" in JS
    assert 'verdict: "BLOCK"' in JS
    assert "report.findings" in JS
    assert ".emission-conformance-score" in CSS
    assert ".emission-conformance-findings" in CSS


def test_visible_prompts_have_copy_controls_and_feedback():
    assert "copyVisiblePrompt(button)" in JS
    assert "bindPromptCopyButtons(host)" in JS
    assert 'data-prompt-copy-panel' in JS
    assert 'data-copy-prompt' in JS
    assert 'aria-label="Copy prompt"' in JS
    assert 'status.textContent = "Copied"' in JS
    assert "navigator.clipboard?.writeText" in JS
    assert 'document.execCommand("copy")' in JS
    assert ".prompt-copy-button" in CSS
    assert ".prompt-copy-status" in CSS


def test_scene_plate_source_buttons_are_valid_and_clickable():
    assert 'data-toggle-scene-plate-library=""' in JS
    assert 'data-fire-scene-plate=""' in JS
    assert 'data-toggle-scene-plate-library>${' not in JS
    assert 'data-fire-scene-plate>Fire Scene Plate' not in JS
    assert 'host.querySelectorAll("[data-toggle-scene-plate-library]")' in JS
    assert 'host.querySelectorAll("[data-fire-scene-plate]")' in JS


def test_voice_review_shows_keyframe_context_and_specific_actions():
    assert "voice-review-stage" in JS
    assert "Approved opening keyframe" in JS
    assert "Approve or refire the dialogue performance only." in JS
    assert 'action.id === "accept-voice" ? "Approve Voice"' in JS
    assert 'action.id === "iterate-voice" ? "Refire Voice"' in JS
    assert 'action.id === "accept-keyframe" ? "Approve Keyframe"' in JS
    assert 'action.id === "accept-animation" ? "Approve Animation"' in JS
    assert ".voice-review-stage" in CSS
    assert ".voice-review-player" in CSS


def test_scene_workbench_uses_live_audio_review_state():
    assert 'artifact.type === "audio" && artifact.url' in JS
    assert "workbench-artifact-frame voice" in JS
    assert "workbench-voice-player" in JS
    assert "Voice review active. Approve or refire the dialogue performance only." in JS
    assert "directorActionLabel(accept)" in JS
    assert '"Approve Shot"' not in JS
    assert "workbenchStatusLabel(session, beat)" in JS
    assert "VOICE REVIEW" in JS
    assert "Voice Check" in JS
    assert ".workbench-artifact-frame.voice" in CSS
    assert ".workbench-voice-player" in CSS
    assert ".workbench-status.voice" in CSS
    assert "grid-template-columns: 34px minmax(0, 1fr) auto" not in CSS
    assert 'document.querySelector(".director-outcome")' in JS
    assert "legacyOutcome) legacyOutcome.hidden = true" in JS


def test_pipeline_live_actions_use_specific_director_labels():
    assert "function directorActionLabel(action)" in JS
    assert "${esc(directorActionLabel(acceptAction))}" in JS
    assert "${esc(directorActionLabel(iterateAction))}" in JS
    assert "${esc(directorActionLabel(acceptAction))} &amp; Continue" in JS
    assert "${esc(directorActionLabel(sendAction))}" in JS
    assert "${esc(directorActionLabel(action))}" in JS


def test_shot_inputs_are_phase_specific_not_generic_keyframe_copy():
    assert 'session.phase === "voice"' in JS
    assert "Voice performance" in JS
    assert "Review the approved keyframe context, the current ElevenLabs acting prompt and the generated take." in JS
    assert "directorActionLabel(session.primaryAction)" in JS
    assert "directorActionLabel((session.decisionActions || [])[0])" in JS
    assert "Loading locked references..." in JS
    assert "Reference load failed:" in JS
    assert "References failed" in JS


def test_director_first_scene_workbench_matches_build_brief():
    assert 'id="scene-workbench"' in HTML
    assert "watch-conformance-20260810-2" in HTML


def test_browser_and_server_publish_the_same_studio_build_version():
    assert 'STUDIO_BUILD_VERSION = "watch-conformance-20260810-2"' in SERVER


def test_three_signoff_relay_and_parallel_scene_board_are_present():
    assert "renderSignoffRelay(session)" in JS
    assert '1: "SEE", 2: "HEAR", 3: "WATCH"' in JS
    assert "Back to my next decision" in JS
    assert "/api/director-board" in JS
    assert "Start scene → generate keyframes" in JS
    assert "data-relay-note" in JS
    assert "submitAction(action, note)" in JS
    assert ".relay-grid" in CSS
    assert ".relay-card.locked" in CSS
    assert "sceneOneContract" in JS
    assert "Script" in JS and "Direction" in JS and "Keyframes" in JS and "Generate" in JS and "Review" in JS
    assert "Fuzzby’s Pollination Lesson" in JS
    assert "Pollen Moustache" in JS
    assert "Visible proof" in JS
    assert "Director Check" in JS
    assert "Two clear upper-lip pollen curls" in JS
    assert "Builder Mode · prompt segment and reference roles" in JS
    assert "Generation + Review" in JS
    assert "Approve $${cost} & render" in JS
    assert "Refine Keyframe" in JS
    assert ".workbench-grid" in CSS
    assert ".workbench-gates" in CSS
    assert ".director-check-list" in CSS
    assert ".generation-review-strip" in CSS


def test_scene_workbench_is_active_beat_driven():
    assert "activeBeatId" in JS
    assert "app.activeBeatId = params.get(\"beat\")" in JS
    assert "app.activeBeatId = button.dataset.beat" in JS
    assert "Keyframe Studio — ${beat.title}" in JS
    assert "Shot: ${esc(beat.shot)} • ${esc(beat.range)} • ${esc(beat.priority)} beat" in JS
    assert "beat.promptSegment || requestPromptText(session)" in JS
    assert "beat.reviewNote || beat.visibleProof" in JS
    assert "Generate Chase Keyframe" in JS
    assert "Generate False-Triumph Anchor" in JS
    assert "Generate Moustache Setup Keyframe" in JS
    assert "Generate Moustache Reveal Keyframe" in JS
    assert "Generate Zenny Reaction Keyframe" in JS
    assert "Generate Final Payoff Keyframe" in JS
    assert "Clear bee-height chase lane" in JS
    assert "No moustache exists in setup frame" in JS
    assert "Two clear upper-lip pollen curls" in JS
    assert ".beat-card.selected" in CSS
    assert ".workbench-beat-frame" in CSS
    assert ".keyframe-substates" in CSS


def test_three_signoff_relay_exposes_real_inputs_and_source_choices():
    assert 'scene-workbench ~ .shot-inputs' not in CSS
    assert 'Choose scene plate or keyframe source' in JS
    assert 'renderKeyframeSourcePanel(session)' in JS
    assert 'data-keyframe-upload' in JS
    assert 'data-select-keyframe-library' in JS
    assert 'data-select-scene-plate-asset' in JS
    assert 'if (session.phase === "keyframe")' in JS
    assert 'Promise.all([loadKeyframeLibrary(session), loadSceneAssetLibrary()])' in JS


def test_audio_references_use_waveform_artwork_not_broken_images():
    assert 'function audioWaveformMarkup' in JS
    assert 'audio-reference' in JS
    assert '/\\.(?:wav|mp3|m4a|aac|ogg)' in JS
    assert 'relay-audio-player' in JS
    assert '<audio controls preload="metadata"' in JS
    assert '.audio-waveform' in CSS
    assert '.audio-waveform-mark::before' in CSS


def test_director_hash_is_the_complete_location_truth_including_beat():
    write_hash = JS.split("function writeHash()", 1)[1].split("function setView", 1)[0]
    assert 'params.set("beat", app.activeBeatId)' in write_hash
    assert 'app.explicitBeat = params.has("beat")' in JS
    assert '!app.explicitBeat && app.workbenchState?.activeBeatId' in JS


def test_provider_failure_has_real_error_fix_and_dismiss_actions():
    assert "failure.error" in JS
    assert 'data-retry-failure="${esc(fix.id)}"' in JS
    assert 'data-dismiss-failure="${esc(failure.jobId)}"' in JS
    assert 'host.querySelectorAll("[data-retry-failure]")' in JS


def test_unchanged_live_poll_does_not_rebuild_media_or_reset_playback():
    assert "function directorSessionSignature(session)" in JS
    assert "const changed = directorSessionSignature(session) !== directorSessionSignature(app.session)" in JS
    poll = JS.split("async function pollLiveSession()", 1)[1].split("async function loadSession()", 1)[0]
    assert "if (changed) {" in poll
    assert "renderDirector(session)" in poll


def test_workbench_gate_summary_is_dynamic_and_actionable():
    assert "function workbenchGateState(session)" in JS
    assert "${esc(gateState.activeGate)} active" in JS
    assert "Approve the active beat keyframe before Generate unlocks." in JS
    assert "gates passed" not in JS
    assert ".workbench-gate-summary em" in CSS


def test_workbench_state_is_persisted_for_project_reopen():
    assert "/api/project-workbench-state?project=crystal-bears" in JS
    assert 'api("/api/project-workbench-state"' in JS
    assert "loadProjectWorkbenchState" in JS
    assert "saveProjectWorkbenchState" in JS


def test_audio_performance_uses_live_voice_status_take_url():
    assert 'status.takeUrl' in JS
    assert '/api/shot-voice-status?' in JS
    assert 'await loadVoicePerformance(true)' in JS
    assert 'if (action.id === "build-voice") await loadVoicePerformance(true)' in JS
    assert 'status["takeUrl"] = _url_from_abs(led.get("voPath"))' in SERVER
    assert "COMPLETE HEAR TRACK" in JS
    assert "This is the full shot track you approve or refire" in JS
    assert "DIRECTION AUDITIONS · NOT THE SHOT TRACK" in JS
    assert "Choose direction & build full track" in JS
    assert "activeBeatId: app.activeBeatId" in JS
    assert "beatState" in JS
    assert "app.workbenchState = null" in JS
    assert "/api/project-workbench-state" in SERVER
    assert "WORKBENCH_STATE_FILE" in SERVER
    assert "_save_project_workbench_state" in SERVER
    assert "cb_db.atomic_write_json(ROOT, WORKBENCH_STATE_FILE" in SERVER


def test_director_supports_out_of_order_scene_selection():
    assert "director-scene-strip" in HTML
    assert "renderDirectorSceneStrip(session)" in JS
    assert "data-director-scene" in JS
    assert "Creates the production shots for this scene from the locked script." in JS
    assert "You can do this out of order" in JS
    assert "This scene has not been directed into production shots yet." in JS
    assert ".director-scene-strip" in CSS


def test_studio_agent_is_visible_read_only_and_selection_aware():
    assert 'id="studio-agent-panel"' in HTML
    assert "/api/studio-agent?mode=HELP" in JS
    assert "renderStudioAgent()" in JS
    assert "loadStudioAgent()" in JS
    assert "Read-only" in JS
    assert "No data is changed and no provider is called" in JS
    assert "session.headline || brief.headline" in JS
    assert "phaseLabel(session.phase)" in JS
    assert ".studio-agent-panel" in CSS
    assert ".agent-meta" in CSS


def test_dense_render_advisories_are_visible_before_provider_actions():
    assert 'id="director-advisories"' in HTML
    assert "renderAdvisories(session)" in JS
    assert "session.advisories || []" in JS
    assert "Check the split before rendering" in SERVER or "DENSE_UNIT_REVIEW" in (HERE.parent / "engine" / "cb_studio_director.py").read_text(encoding="utf-8")
    assert ".director-advisory" in CSS


def test_pipeline_footage_displays_reviewable_video_candidates():
    assert "renderPipelineArtifact(step, session)" in JS
    assert 'artifact.type === "video-set"' in JS
    assert 'id="pipeline-candidate-video"' in JS
    assert "data-pipeline-candidate" in JS
    assert ".pipeline-artifact img, .pipeline-artifact video" in CSS


def test_completed_render_candidates_are_visible_before_batch_finishes():
    assert 'job.completedCandidateCount' in JS
    assert 'class="render-completed-candidates"' in JS
    assert "Candidate ${esc(item.n)} complete" in JS
    assert ".render-completed-candidates video" in CSS
    assert 'transportCandidates' in SERVER


def test_watch_relay_shows_every_candidate_and_requires_explicit_selection():
    assert 'class="relay-candidate-grid"' in JS
    assert 'data-relay-candidate="${esc(item.n)}"' in JS
    assert 'app.selectedCandidate = Number(button.dataset.relayCandidate)' in JS
    assert '.relay-candidate.selected' in CSS


def test_hear_relay_distinguishes_ready_from_locked_without_fake_media():
    assert "No voice performance has been created yet." in JS
    assert "Voice is locked until SEE is approved." in JS
    assert "relayStage(session) >= 2" in JS


def test_watch_relay_keeps_superseded_renders_visible_without_approval_controls():
    assert "Previous renders — view only" in JS
    assert "artifact.stale" in JS
    assert 'class="relay-candidate stale"' in JS
    assert ".relay-stale-notice" in CSS


def test_director_entry_is_authenticated_and_static_allowlisted():
    assert '"/cb-studio/director.html"' in SERVER
    assert 'parsed.path not in (' in SERVER
    assert '"/cb-studio/director.html", "/cb-studio/app.html"' in SERVER
    assert '"Location", "/cb-studio/director.html"' in SERVER
    assert "/cb-studio/director.html?launchToken=" in SERVER


def test_paid_actions_receive_an_explicit_confirmation_without_exposing_tokens():
    assert 'id="confirm-dialog"' in HTML
    assert "Maximum provider cost" in JS
    assert 'action.id === "approve-spend"' in JS
    assert "pendingSpendAuth" not in JS
    assert "spendToken" not in JS


def test_production_pipeline_uses_the_canonical_creative_path():
    assert 'id: "upload"' in JS
    assert 'id: "analysis"' in JS
    assert 'id: "characters"' in JS
    assert 'id: "storyboard"' in JS
    assert 'id: "footage"' in JS
    assert 'id: "audio"' in JS
    assert 'id: "rough-cut"' in JS
    assert JS.index('id: "audio"') < JS.index('id: "footage"')
    assert HTML.index('data-pipeline-step="audio"') < HTML.index('data-pipeline-step="footage"')
    assert "renderCanonicalPipelineStep(step)" in JS
    assert 'view: "director"' in JS
    assert '? params.get("view") : "director"' in JS
    assert '? requestedStep : "storyboard"' in JS
    assert "production-board" in JS
    assert "shotPipelineRail(shot)" in JS
    assert "Keyframe" in JS
    assert "Voice" in JS
    assert "Animation" in JS
    assert "Open Current Shot" in JS
    assert "Work This Scene" in JS
    assert ".pipeline-rail {\n  display: none;" in CSS
    assert ".pipeline-shell { grid-template-columns: 118px" not in CSS
    assert ".pipeline-rail { min-height: 0; position: static; display: flex" not in CSS
    assert ".production-board-scenes" in CSS
    assert ".shot-pipeline" in CSS


def test_audio_stage_is_the_editable_elevenlabs_performance_desk():
    assert "/api/shot-voice-status?" in JS
    assert 'api("/api/shot-voice-save"' in JS
    assert 'api("/api/shot-voice-restore"' in JS
    assert "Acting &amp; cadence prompt" in JS
    assert "Text + audio tags sent to ElevenLabs" in JS
    assert "directorActionLabel(sendAction)" in JS
    assert 'data-advance-step="footage"' in JS
    assert ".voice-direction-grid" in CSS
    assert '["storyboard", "footage", "rough-cut"]' in JS
    assert 'step.id === "audio" ? "" : `<div class="production-now">' in JS
    assert 'class="voice-take-player"' in JS
    assert 'app.session?.artifact?.type === "audio"' in JS
    assert ".voice-take-player audio" in CSS
    assert "status.error" in JS
    assert "recoveryAction" in JS


def test_project_truth_layer_distinguishes_real_production_states():
    assert 'id="truth-rail"' in HTML
    for label in ("Canon", "Script", "Assets", "Shots", "Spend", "Delivery"):
        assert f'["{label}"' in JS
    for state in ("proven", "built", "proposed", "blocked", "awaiting", "locked"):
        assert f".truth-chip.{state}" in CSS


def test_pipeline_current_step_uses_real_actions_and_blocked_steps_return_to_work():
    assert "pipelineStepState(step, session)" in JS
    assert 'data-live-action=' in JS
    assert "directorActionLabel(acceptAction))} &amp; Continue" in JS
    assert "pendingAdvance" in JS
    assert 'data-jump-current=' in JS
    assert "handleAction(action)" in JS
    assert "Approve the audio performances before generating footage." in JS
    assert "data-open-evidence" in JS
    assert "openEvidence(stepId)" in JS
    assert "data-open-references" in JS
    assert "data-open-request" in JS


def test_workbench_gate_buttons_are_real_navigation_not_dead_controls():
    assert 'data-workbench-gate=' in JS
    assert 'host.querySelectorAll("[data-workbench-gate]")' in JS
    assert 'generate: session.phase === "voice" ? "audio" : "footage"' in JS
    assert 'setView("pipeline")' in JS


def test_workbench_preview_shows_clean_artwork_without_composition_overlay():
    assert 'class="canvas-overlay"' not in JS
    assert ".canvas-overlay" not in CSS


def test_workbench_actions_show_immediate_and_persistent_activity_status():
    assert "${renderGenerateStatus(session)}" in JS
    assert 'button.textContent = action.id === "prepare-render" ? "Compiling prompt..." : "Working..."' in JS
    assert 'button.setAttribute("aria-busy", "true")' in JS


def test_progress_copy_distinguishes_voice_from_keyframe_and_animation():
    assert 'isVoice ? "Voice performance build" : "Opening-frame build"' in JS
    assert 'isVoice ? "ElevenLabs voice build is active"' in JS
    assert "The Studio is creating the dialogue performance." in JS


def test_uncompiled_animation_prompt_explains_the_separate_spend_gate():
    assert "The Seedance prompt has not been compiled yet." in JS
    assert "No video is generated until you separately approve spend." in JS
    assert "This does not generate video. No spend happens until render approval." in JS


def test_sealed_request_takes_display_priority_over_superseded_candidates():
    spend_gate = JS.index('if (session.spendDisclosure && (session.decisionActions || []).some((action) => action.id === "approve-spend"))')
    candidate_gallery = JS.index('if (artifact.type === "video-set" && (artifact.items || []).length)')
    assert spend_gate < candidate_gallery
    assert "Request prepared" in JS
    assert "No new Seedance video exists until you press Render." in JS


def test_every_production_stage_has_persistent_scene_and_shot_navigation():
    assert 'renderProductionNavigator(step)' in JS
    assert '["storyboard", "audio", "footage", "rough-cut"]' in JS
    assert 'data-production-scene=' in JS
    assert 'data-production-shot=' in JS
    assert "app.pipelineStep =" not in JS[JS.index('panel.querySelectorAll("[data-production-scene]")'):JS.index('panel.querySelectorAll("[data-live-action]")')]
    assert ".production-nav-options" in CSS
    assert "overflow-x: auto" in CSS


def test_rough_cut_uses_a_saved_approved_take_bin():
    assert "/api/rough-cut-draft?" in JS
    assert 'api("/api/rough-cut-draft"' in JS
    assert "Approved shot bin" in JS
    assert "Add shot" in JS
    assert 'self.path == "/api/rough-cut-draft"' in SERVER
    assert "rough_cut_projection" in SERVER
