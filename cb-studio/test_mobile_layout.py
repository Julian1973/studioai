from pathlib import Path


APP = (Path(__file__).parent / "app.html").read_text(encoding="utf-8")


def test_mobile_shell_handles_safe_areas_and_touch_targets():
    assert 'content="width=device-width, initial-scale=1"' in APP
    assert "html,body{max-width:100%;overflow-x:hidden" in APP
    assert "env(safe-area-inset-left)" in APP
    assert "env(safe-area-inset-bottom)" in APP
    assert ".brand{min-width:0;min-height:44px" in APP
    assert ".nav a,.nav button{min-height:44px}" in APP
    assert ".iconbtn{width:44px;height:44px" in APP
    assert "font-size:16px!important;min-height:44px" in APP


def test_generated_libraries_shrink_to_compact_phone_widths():
    assert '.library-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,360px),1fr))' in APP
    assert 'class="library-grid"' in APP
    assert 'class="library-grid wide"' in APP
    assert 'class="mc character-card"' in APP
    assert 'class="mc asset-card"' in APP
    assert 'class="mc character-detail-lead"' in APP
    assert 'grid-template-columns:repeat(auto-fill,minmax(360px,1fr))' not in APP
    assert 'grid-template-columns:repeat(auto-fill,minmax(440px,1fr))' not in APP


def test_dense_forms_and_modals_reflow_on_mobile():
    assert 'class="mobile-grid-2"' in APP
    assert 'class="mobile-split"' in APP
    assert 'class="wizard-character-add"' in APP
    assert 'class="modal-actions"' in APP
    assert ".mobile-grid-2{grid-template-columns:minmax(0,1fr)}" in APP
    assert ".sheet{width:100%;max-height:calc(100dvh" in APP
    assert 'class="table-scroll"' in APP


def test_character_profile_can_store_production_imagery_and_voice():
    assert "Add or update imagery and voice" in APP
    assert 'id="character_voice_id"' in APP
    assert 'id="character_anchor"' in APP
    assert 'id="character_turnaround"' in APP
    assert 'id="character_references"' in APP
    assert "multiple" in APP
    assert "saveCharacterAssets()" in APP
    assert "Review and re-lock canon before production." in APP


def test_story_direction_run_has_visible_live_progress():
    assert "storyIntakeProgressHTML(job)" in APP
    assert 'aria-label="Story and Direction progress"' in APP
    assert 'role="progressbar"' in APP
    assert "Directing story, emotion and comedy" in APP
    assert "dialogue lines" in APP


def test_mobile_navigation_remains_reachable_without_page_overflow():
    assert ".top{position:sticky;top:0;display:grid" in APP
    assert 'class="mobile-menu-toggle"' in APP
    assert 'aria-controls="toplinks"' in APP
    assert ".mobile-menu-toggle{display:none;width:44px;height:44px" in APP
    assert ".toplinks.open{display:grid}" in APP
    assert "function toggleMobileMenu()" in APP
    assert 'button.setAttribute("aria-expanded",String(open))' in APP
    assert 'nav.style.removeProperty("display")' in APP
    assert "display:flex!important" not in APP
    assert "max-height:calc(100dvh - 70px" in APP
    assert ".toplinks{order:3;width:100%;height:46px" not in APP
    assert "-webkit-overflow-scrolling:touch" in APP
    assert "#toast{left:max(12px,env(safe-area-inset-left))!important" in APP
