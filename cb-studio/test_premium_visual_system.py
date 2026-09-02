import json
from pathlib import Path


STUDIO = Path(__file__).parent
ROOT = STUDIO.parent
APP = (STUDIO / "app.html").read_text(encoding="utf-8")
SERVER = (STUDIO / "serve.py").read_text(encoding="utf-8")
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
    assert primary["theme"]["accent"].startswith("#")
    assert 'class="projcard-artmedia"' in APP
    assert 'class="epthumb-label"' in APP
    assert 'data-primary="${p.primary?' in APP
    assert 'data-archived="${p.archived?' in APP


def test_premium_system_keeps_visual_rules_explicit():
    assert "PREMIUM STUDIO SYSTEM" in APP
    assert "--bg:#f4f2ef" in APP
    assert "background:#211f23" in APP
    assert "--brand:#745477" in APP
    assert "html *{letter-spacing:0!important}" in APP
    # Flat surfaces: no decorative gradient anywhere. The single exception is the striped
    # progress bar on a live Story & Direction run (2026-09-02) — that stripe is the motion
    # itself, the one signal that the Director is still working, not decoration. Pinned to
    # exactly one use so ornament cannot creep back in behind it.
    assert "radial-gradient(" not in APP
    assert APP.count("linear-gradient(") == 1
    assert APP.count("repeating-linear-gradient(") == 1
    assert "animation:sbstripe" in APP
    assert ":focus-visible" in APP
    assert "@media (prefers-reduced-motion:reduce)" in APP


def test_platform_shell_is_ip_agnostic_and_projects_supply_identity():
    assert "<title>Animation Studio</title>" in APP
    assert '<span class="brand-name">Animation</span>' in APP
    assert "Crystal Bears canon" not in APP
    assert "function projectTheme(project)" in APP
    assert "function applyProjectPresentation(project)" in APP
    assert 'project.name+" · Animation Studio"' in APP
    assert 'style="--brand:${theme.accent};--brandink:${theme.ink};--brandbg:${theme.soft}"' in APP


def test_first_viewport_names_productions_and_keeps_episode_decisions_inside_them():
    assert '<div class="screen-eyebrow">Studio workspace</div>' in APP
    assert '<h1>Productions</h1>' in APP
    assert 'Production library' in APP
    assert 'Props & references' in APP
    assert 'function productionLibraryHTML(active)' in APP
    assert 'opts.kicker||"Next decision"' in APP
    assert "if(pg=='assets'){showAssets();return true;}" in APP
    assert 'if(page=="assets")return renderAssets();' in APP
    assert "if(EXPLICIT_START_HASH){bootProjects();return;}" in APP


def test_project_art_reaches_central_screens_and_new_project_storage():
    assert "function projectScreenHeaderHTML(opts)" in APP
    assert 'class="screenhead-art"' in APP
    assert "CURRENT_PROJECT.episodeCoverImage||CURRENT_PROJECT.coverImage" in APP
    assert "function wizKeyArt(input)" in APP
    assert 'id="wz_accent" type="color"' in APP
    assert "coverImageData" in APP
    assert 'fn = "project_key_art" + ext' in SERVER
    assert 'meta["coverImage"] = cover_image' in SERVER
    assert '"theme": {"accent": accent}' in SERVER
    assert 'fn = "CB_" + safe + "_anchor.png"' not in SERVER


def test_core_cards_stay_compact_and_responsive():
    assert '.projcard{border:1px solid var(--line);border-radius:8px' in APP
    assert '.epcard{border:1px solid var(--line);border-radius:8px' in APP
    assert '.scenecard{border:1px solid var(--line);border-radius:8px' in APP
    assert '@media (max-width:980px)' in APP
    assert '@media (max-width:700px)' in APP
