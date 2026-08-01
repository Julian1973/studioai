import json
from pathlib import Path


STUDIO = Path(__file__).parent
ROOT = STUDIO.parent
APP = (STUDIO / "app.html").read_text(encoding="utf-8")
PROJECTS = json.loads((STUDIO / "data" / "projects.json").read_text(encoding="utf-8"))[
    "projects"
]


def test_primary_slate_uses_real_local_key_art():
    primary = next(project for project in PROJECTS if project.get("primary"))
    archive = next(project for project in PROJECTS if project.get("archived"))

    for project in (primary, archive):
        cover = project["coverImage"]
        assert cover.startswith("/")
        assert (ROOT / cover.lstrip("/")).is_file()

    episode_cover = primary["episodeCoverImage"]
    assert (ROOT / episode_cover.lstrip("/")).is_file()
    assert 'class="projcard-artmedia"' in APP
    assert 'class="epthumb-label"' in APP
    assert 'data-primary="${p.primary?' in APP
    assert 'data-archived="${p.archived?' in APP


def test_premium_system_keeps_visual_rules_explicit():
    assert "PREMIUM STUDIO SYSTEM" in APP
    assert "--bg:#edefec" in APP
    assert "background:#141719" in APP
    assert "html *{letter-spacing:0!important}" in APP
    assert "linear-gradient(" not in APP
    assert ":focus-visible" in APP
    assert "@media (prefers-reduced-motion:reduce)" in APP


def test_first_viewport_names_the_show_and_next_decision():
    assert '<span class="brand-name">Crystal Bears</span>' in APP
    assert '<div class="screen-eyebrow">Studio slate</div>' in APP
    assert '<div class="screen-eyebrow">Episode slate</div>' in APP
    assert 'opts.kicker||"Next decision"' in APP
    assert 'title:"Continue "+primary.name' in APP
    assert "if(EXPLICIT_START_HASH){bootProjects();return;}" in APP


def test_core_cards_stay_compact_and_responsive():
    assert '.projcard{border:1px solid #cfd4d1;border-radius:8px' in APP
    assert '.epcard{border:1px solid #cfd4d1;border-radius:8px' in APP
    assert '.scenecard{border:1px solid #cfd4d1;border-radius:8px' in APP
    assert '@media (max-width:980px)' in APP
    assert '@media (max-width:700px)' in APP
