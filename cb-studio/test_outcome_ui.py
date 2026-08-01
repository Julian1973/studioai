import re
from pathlib import Path


APP = (Path(__file__).parent / "app.html").read_text(encoding="utf-8")
SERVER = (Path(__file__).parent / "serve.py").read_text(encoding="utf-8")


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
        "Choose the replacement source",
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
