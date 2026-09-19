#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Producer-facing money-safety contract. Runs with NO provider keys in the
# environment and with every non-loopback socket connection refused, so a
# regression that tries to reach a provider fails here instead of spending.
unset OPENAI_API_KEY FAL_KEY FAL_API_KEY ELEVENLABS_API_KEY ELEVEN_API_KEY \
      BYTEPLUS_ACCESS_KEY BYTEPLUS_SECRET_KEY BYTEPLUS_API_KEY DREAMINA_API_KEY \
      GOOGLE_API_KEY GEMINI_API_KEY ANTHROPIC_API_KEY SUNO_API_KEY 2>/dev/null || true
for name in $(env | grep -iE '^[A-Z0-9_]*(API_KEY|SECRET|TOKEN)[A-Z0-9_]*=' | cut -d= -f1); do
  case "$name" in
    GITHUB_TOKEN|GH_TOKEN|CI_JOB_TOKEN) ;;  # CI plumbing, not a provider
    *) unset "$name" ;;
  esac
done

# conftest.py's autouse fixture already refuses every non-loopback socket
# connection for the whole suite; this gate additionally runs with no keys.

PYTHONPATH=engine python3 -m pytest -q -p no:cacheprovider \
  cb-studio/test_local_auth.py::test_budget_approval_does_not_approve_any_media \
  cb-studio/test_local_auth.py::test_credits_endpoint_requires_auth_and_routes_one_explicit_fire \
  cb-studio/test_director_ui.py::test_production_pipeline_uses_the_canonical_creative_path \
  cb-studio/test_director_ui.py::test_watch_shows_new_prepared_prompt_without_authorizing_render \
  cb-studio/test_director_ui.py::test_uncompiled_animation_prompt_explains_the_separate_spend_gate \
  cb-studio/test_watch_prompt_evidence.py \
  cb-studio/test_journey_spend.py \
  "cb-studio/test_journey_acceptance.py::test_actual_duplicate_click_is_one_producer_operation" \
  "cb-studio/test_journey_acceptance.py::test_reload_and_late_known_provider_result_never_resubmit" \
  cb-studio/test_journey_http.py \
  engine/test_watch_frontdoor.py \
  engine/test_studio_seedance_execution.py
