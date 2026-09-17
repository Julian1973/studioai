#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Curated producer-facing safety contract. These tests use fake transports and
# block provider sockets in their fixtures; no provider or model call is valid here.
PYTHONPATH=engine pytest -q \
  cb-studio/test_local_auth.py::test_budget_approval_does_not_approve_any_media \
  cb-studio/test_local_auth.py::test_credits_endpoint_requires_auth_and_routes_one_explicit_fire \
  cb-studio/test_director_ui.py::test_production_pipeline_uses_the_canonical_creative_path \
  cb-studio/test_director_ui.py::test_watch_shows_new_prepared_prompt_without_authorizing_render \
  cb-studio/test_director_ui.py::test_uncompiled_animation_prompt_explains_the_separate_spend_gate \
  cb-studio/test_watch_prompt_evidence.py \
  engine/test_watch_frontdoor.py \
  engine/test_studio_seedance_execution.py
