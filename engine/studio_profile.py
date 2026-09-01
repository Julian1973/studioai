#!/usr/bin/env python3
"""COMPATIBILITY SHIM (T44, 2026-09-01) — every name now lives in project_profile.py.

`import studio_profile` keeps working for one release so no caller breaks mid-restructure; new code
imports project_profile directly. Deleted by T61 together with the other compatibility links.
"""
from project_profile import *  # noqa: F401,F403
from project_profile import (  # noqa: F401 — explicit, so tools that scan for names still find them
    SHOW_ID_RE, DEFAULT_CAPABILITIES, ShowProfileError, CanonProfile, EpisodeProfile,
    ShowProfile, LoadedShowProfile, validate_show_id, load_show_profile, capability_report,
    default_project_id, list_project_ids, active_project_setting, set_active_project,
)


def __getattr__(name):
    if name in ("DEFAULT_SHOW_ID", "DEFAULT_PROJECT_ID"):
        return default_project_id()
    raise AttributeError(name)
