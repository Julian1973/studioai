# Golden Path test triage

Baseline recorded at commit `c3e83a1f3046ce5d541203c8f85f943b7c07b022` before
production fixes.

## Baseline results

- Full suite: 118 passed, 2 failed, 10 errors.
- Push gate: failed in the local sandbox because HTTP test fixtures could not
  bind loopback sockets; the browser gate did not qualify.
- No provider or model calls occurred.

## Failure ledger

The initial run exposed 12 failures. These entries are provisional until the
isolated qualification run can bind its test sockets.

| Test | Classification | Current invariant | Disposition |
|---|---|---|---|
| `cb-studio/test_local_auth.py::test_retired_department_mutations_are_gone_from_current_production[run]` | TEST_ENVIRONMENT_FAILURE | HTTP route fixture must start | Re-run with socket permission; classify after exact failure is observable |
| `cb-studio/test_local_auth.py::test_retired_department_mutations_are_gone_from_current_production[save]` | TEST_ENVIRONMENT_FAILURE | HTTP route fixture must start | Re-run with socket permission; classify after exact failure is observable |
| `cb-studio/test_local_auth.py::test_retired_department_mutations_are_gone_from_current_production[decide]` | TEST_ENVIRONMENT_FAILURE | HTTP route fixture must start | Re-run with socket permission; classify after exact failure is observable |
| `cb-studio/test_local_auth.py::test_launch_token_establishes_http_only_session_and_cleans_url` | TEST_ENVIRONMENT_FAILURE | HTTP session security | Re-run with socket permission; classify after exact failure is observable |
| `cb-studio/test_local_auth.py::test_director_entry_and_facade_share_the_authenticated_session` | TEST_ENVIRONMENT_FAILURE | Shared authenticated session | Re-run with socket permission; classify after exact failure is observable |
| `cb-studio/test_local_auth.py::test_host_origin_and_session_are_all_enforced` | TEST_ENVIRONMENT_FAILURE | Host/origin/session enforcement | Re-run with socket permission; classify after exact failure is observable |
| `cb-studio/test_local_auth.py::test_parallel_index_reads_return_complete_json` | TEST_ENVIRONMENT_FAILURE | Concurrent read completeness | Re-run with socket permission; classify after exact failure is observable |
| `cb-studio/test_local_auth.py::test_credits_endpoint_requires_auth_and_routes_one_explicit_fire` | TEST_ENVIRONMENT_FAILURE | Authenticated paid route and one explicit fire | Re-run with socket permission; classify after exact failure is observable |
| `cb-studio/test_local_auth.py::test_retired_paid_routes_fail_without_starting_work[/api/room-chat]` | TEST_ENVIRONMENT_FAILURE | Retired paid routes cannot start work | Re-run with socket permission; classify after exact failure is observable |
| `cb-studio/test_local_auth.py::test_retired_paid_routes_fail_without_starting_work[/api/write]` | TEST_ENVIRONMENT_FAILURE | Retired paid routes cannot start work | Re-run with socket permission; classify after exact failure is observable |
| `cb-studio/test_local_auth.py::test_authenticated_browser_session_survives_server_restart` | TEST_ENVIRONMENT_FAILURE | Session continuity across restart | Re-run with socket permission; classify after exact failure is observable |
| `cb-studio/test_local_auth.py::test_explicit_https_origin_supports_secure_remote_access` | TEST_ENVIRONMENT_FAILURE | Explicit secure origin handling | Re-run with socket permission; classify after exact failure is observable |

This ledger is deliberately not used to remove or weaken tests. Safety,
reservation, duplicate-submission, and provider-identity tests remain required.

## Escalated baseline and no-spend qualification

With loopback permission, the unchanged baseline is `130 passed`.
The producer-facing no-spend matrix then exposed three current Journey blockers:
late-result and fresh-process recovery do not reach the persisted busy state after
the third action, and a known provider failure does not expose the explicit retry
decision. The same path records a WATCH request as blocked when a compiled
reference path cannot be resolved from the worker cwd. No provider or model call
occurred; no tests were deleted.

The required Native-focused legacy set currently reports 58 failures and 120
passes. The failures cluster around retired specialist/relay assumptions,
old candidate-review setup, and old retake/message contracts. They are not
being made green by weakening production safety. The Native release bar stays
closed until each Native money/safety case is either rewritten to the current
DIRECT → SEE → HEAR → WATCH contract or replaced by an equivalent call-counting
proof.
