from pathlib import Path


HERE = Path(__file__).resolve().parent
HTML = (HERE / "director.html").read_text(encoding="utf-8")
CSS = (HERE / "director.css").read_text(encoding="utf-8")
JS = (HERE / "director.js").read_text(encoding="utf-8")
SERVER = (HERE / "serve.py").read_text(encoding="utf-8")


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
    for internal_route in (
        "/api/production-preflight", "/api/production-state", "/api/shot-package",
        "/api/department-run", "/api/shot-run",
    ):
        assert internal_route not in JS
    assert "allowed_action_ids(session)" in SERVER
    assert "That action is no longer current" in SERVER


def test_exact_request_is_separate_and_named_authoritative():
    assert 'id="request-drawer"' in HTML
    assert "Exact provider request" in HTML
    assert "app.session?.inspector?.providerRequest" in JS
    assert "shot.seedancePrompt" not in JS
    assert "keyframePrompt" not in JS


def test_references_are_available_for_keyframe_and_animation_without_clutter():
    assert 'data-reference-stage="keyframe"' in HTML
    assert 'data-reference-stage="animation"' in HTML
    assert "/api/shot-references?" in JS
    assert 'id="reference-dialog"' in HTML
    assert not ('id="reference-dialog" open' in HTML)
    assert "Complete uncropped 360 turnaround" in JS


def test_mobile_navigation_is_always_reachable_and_safe_area_aware():
    assert 'class="mobile-nav"' in HTML
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


def test_audio_stage_is_the_editable_elevenlabs_performance_desk():
    assert "/api/shot-voice-status?" in JS
    assert 'api("/api/shot-voice-save"' in JS
    assert 'api("/api/shot-voice-restore"' in JS
    assert "Acting &amp; cadence prompt" in JS
    assert "Text + audio tags sent to ElevenLabs" in JS
    assert "Send to ElevenLabs" in JS
    assert 'data-advance-step="footage"' in JS
    assert ".voice-direction-grid" in CSS
    assert '["storyboard", "footage", "rough-cut"]' in JS
    assert 'step.id === "audio" ? "" : `<div class="production-now">' in JS
    assert 'class="voice-take-player"' in JS
    assert 'app.session?.artifact?.type === "audio"' in JS
    assert ".voice-take-player audio" in CSS


def test_project_truth_layer_distinguishes_real_production_states():
    assert 'id="truth-rail"' in HTML
    for label in ("Canon", "Script", "Assets", "Shots", "Spend", "Delivery"):
        assert f'["{label}"' in JS
    for state in ("proven", "built", "proposed", "blocked", "awaiting", "locked"):
        assert f".truth-chip.{state}" in CSS


def test_pipeline_current_step_uses_real_actions_and_blocked_steps_return_to_work():
    assert "pipelineStepState(step, session)" in JS
    assert 'data-live-action=' in JS
    assert "Approve &amp; Continue" in JS
    assert "pendingAdvance" in JS
    assert 'data-jump-current=' in JS
    assert "handleAction(action)" in JS
    assert "Approve the audio performances before generating footage." in JS
    assert "data-open-evidence" in JS
    assert "openEvidence(stepId)" in JS
    assert "data-open-references" in JS
    assert "data-open-request" in JS


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
