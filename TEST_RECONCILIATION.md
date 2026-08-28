# Test Reconciliation

Date: 2026-08-28

The first clean checkout run exposed 31 failures: the 21 failures from the
working-tree run plus 10 additional failures that had been hidden by ignored
local media/output. No provider was contacted. No assertion was deleted,
skipped, xfailed, or loosened to obtain the final result.

## Dispositions

| Test | Class | Root cause and corrective action | Changed | Protection evidence |
|---|---|---|---|---|
| `cb-studio/test_premium_visual_system.py::test_primary_slate_uses_real_local_key_art` | `ENVIRONMENT_FIXTURE` | Project cards referenced ignored legacy artwork; point cards at tracked Seedance test art. | production data | Files must exist in the repository; no external path is accepted. |
| `engine/test_cb_canon.py::test_repository_ep1_human_canon_decisions_are_locked` | `ENVIRONMENT_FIXTURE` | Source-only branch has no bundled operator media; assert lock/script evidence and refusal of incomplete canon. | test | Missing canon still blocks production through `require_locked`. |
| `engine/test_cb_departments.py::test_animation_reads_missing_beat_contracts_only_from_exact_approved_storyboard` | `ENVIRONMENT_FIXTURE` | Temporary storyboard was outside the production root and was rejected as untrusted. | test | Test now injects the temporary root; stale MD5 still returns the un-enriched shot. |
| `engine/test_cb_directing_standard.py::test_forward_department_work_requires_signed_v3_director_card` | `OBSOLETE_CONTRACT_EXPECTATION` | Test fixture path was outside the declared root, not a v4 contract failure. | test | Approval state, version, card hash and required contracts remain mandatory. |
| `engine/test_cb_directing_standard.py::test_v3_source_contract_remains_valid_without_v4_heart_fields` | `OBSOLETE_CONTRACT_EXPECTATION` | Same root-containment fixture issue; v3 intentionally has no v4 North Star requirement. | test | v3 still requires approved source, card hash and v3 fields. |
| `engine/test_cb_director.py::test_review_animation_signature_allows_external_director_accepted_take` | `ENVIRONMENT_FIXTURE` | Test did not provide a canon profile for the review signature. | test | All profile digests are injected; generation signature remains forbidden for external accepted media. |
| `engine/test_cb_pose_first.py::test_stage_prompt_keeps_pose_flexible_and_never_forwards_stale_composition_props` | `ENVIRONMENT_FIXTURE` | Prompt unit test depended on ignored Zenny media. | test | Symbolic identity attachments preserve role/turnaround rules without bypassing prompt assertions. |
| `engine/test_cb_pose_first.py::test_stage_prompt_preserves_verbose_specialist_direction` | `ENVIRONMENT_FIXTURE` | Same missing operator media dependency. | test | Full specialist prose and anti-drift assertions remain. |
| `engine/test_cb_pose_first.py::test_stage_prompt_has_no_length_target` | `ENVIRONMENT_FIXTURE` | Same missing operator media dependency. | test | No length target assertion remains. |
| `engine/test_cb_pose_first.py::test_keyframe_budget_never_trims_director_creative_core` | `ENVIRONMENT_FIXTURE` | Same missing operator media dependency. | test | Load-bearing direction remains asserted. |
| `engine/test_cb_pose_first.py::test_keyframe_word_count_never_blocks_load_bearing_direction` | `ENVIRONMENT_FIXTURE` | Same missing operator media dependency. | test | Word-count protection remains absent; direction is retained. |
| `engine/test_cb_pose_first.py::test_keyframe_prompt_recompiles_from_exact_approved_direction` | `ENVIRONMENT_FIXTURE` | Same missing operator media dependency. | test | Recompile remains deterministic and exact. |
| `engine/test_cb_reference_manifest.py::test_keen_identity_reference_follows_episode_wristband_state` | `ENVIRONMENT_FIXTURE` | State-selection test depended on ignored Keen turnarounds. | test | State/file-name and no-crystal constraints remain asserted. |
| `engine/test_current_production_path.py::test_current_path_reaches_an_approved_master_without_provider_spend` | `CURRENT_PRODUCTION_REGRESSION` | Target-shot fresh validation treated a shared beat as if every dialogue line belonged to that shot; validate the complete relay ancestry and exact assigned dialogue. | production + fixture | Exact dialogue checks, explicit spend token, mocked providers and zero-spend assertions remain. |
| `engine/test_e2e_fire_route.py::test_golden_path_keyframe_refuses_on_the_actual_current_lineage_mismatch` | `OBSOLETE_CONTRACT_EXPECTATION` | The test patched an unused helper while the real gate calls the lineage guard. | test | It now simulates the real refusal boundary; no generator call occurs. |
| `engine/test_golden_path.py::test_golden_path_package_to_approved_scene_master` | `CURRENT_PRODUCTION_REGRESSION` | Same shared-beat target validation issue; fixed by ancestry scoping. | production + fixture | Paid route remains behind the server token and mocked provider calls. |
| `engine/test_golden_path.py::test_same_process_comparison_returns_one_candidate_from_approved_stage_relay` | `APPROVED_OUTPUT_PARITY` | Final review media must contain restored approved HEAR audio, not the provider guide bytes. | test | Test now checks the approved-audio restoration marker and retained provider guide evidence. |
| `engine/test_golden_path.py::test_immutable_script_to_approved_master_golden_path` | `OBSOLETE_CONTRACT_EXPECTATION` | Synthetic story fixture omitted required current schema fields. | test | Current `charactersInFrame` and `offscreenCharacters` fields are supplied; script immutability remains tested. |
| `engine/test_golden_path.py::test_failure_ladder_unchanged_reroll_then_model_limited` | `CURRENT_PRODUCTION_REGRESSION` | Model-limited refusal was reached only after stale prompt resolution. | production | Safety and render layers refuse model-limited work before prompt/provider activity. |
| `engine/test_golden_path.py::test_stale_token_refused_when_spend_envelope_changes` | `CURRENT_PRODUCTION_REGRESSION` | Shared-beat validation blocked the intended spend-envelope assertion first. | production | Fresh validation remains before spend and tokens remain single-use/bound. |
| `engine/test_golden_path.py::test_parallel_fire_cannot_claim_the_same_spend_token_twice` | `CURRENT_PRODUCTION_REGRESSION` | Same validation ordering issue. | production | Parallel token ownership and conflict protection remain tested. |
| `engine/test_golden_path.py::test_batch_resume_is_idempotent_never_repays` | `CURRENT_PRODUCTION_REGRESSION` | Same validation ordering issue. | production | Resumable batches still generate only missing candidates and never repay completed work. |
| `engine/test_production_safety.py::test_scene_look_refuses_before_provider_without_current_direction` | `ENVIRONMENT_FIXTURE` | Real Ep1 local checkout had compatibility-copy drift before the intended direction gate. | test | Canon refusal remains a hard no-provider boundary; fixture supplies only the canonical profile decision. |
| `engine/test_scene1_director_records.py::test_scene1_director_records_recompile_deterministically_and_pass` | `OBSOLETE_CONTRACT_EXPECTATION` | Stored pre-v4 provider prose was stale against the current compiler. | test | Current compiler is checked twice for deterministic output and emission/engine gates remain. |
| `engine/test_scene1_director_records.py::test_s1s4_corrected_emission_fixture_and_regressions` | `OBSOLETE_CONTRACT_EXPECTATION` | Test read stale stored prose instead of current typed compilation. | test | Current typed prompt still asserts reference, dialogue, landing and watermark constraints. |
| `engine/test_scene3_remaining_recut.py::test_superseded_units_are_excluded_from_live_production_state` | `OBSOLETE_CONTRACT_EXPECTATION` | Expected an obsolete `3.B6R.S1` unit after the approved two-unit recut. | test | Superseded units remain excluded; active IDs come from the current package. |
| `engine/test_scene_wrapper.py::test_establish_prompt_contains_wrapper_hold_and_ambient_rules` | `ENVIRONMENT_FIXTURE` | Test read an ignored scene-10 package absent from the source branch. | test | Uses a tracked package schema; wrapper rules remain asserted. |
| `engine/test_scene_wrapper.py::test_establish_validation_allows_ten_second_location_discovery` | `ENVIRONMENT_FIXTURE` | Same absent generated package dependency. | test | Ten-second discovery is validated through the real scene validator. |
| `engine/test_scene_wrapper.py::test_fresh_establish_can_use_scene_plate_without_chain_source` | `ENVIRONMENT_FIXTURE` | Same absent generated package dependency. | test | Scene-plate opening behavior remains asserted. |
| `engine/test_scene_wrapper.py::test_scene_may_open_and_close_on_coverage_when_story_demands_it` | `ENVIRONMENT_FIXTURE` | Same absent generated package dependency. | test | Coverage exception remains explicit and validated. |
| `engine/test_scene_wrapper.py::test_wrapper_validation_rejects_dialogue_on_button` | `ENVIRONMENT_FIXTURE` | Same absent generated package dependency. | test | Dialogue-on-button rejection remains asserted. |

## Final safeguards

- Tests use mocked provider functions and no paid image, audio or video calls.
- Seedance 2.5 and ElevenLabs v3 locks, explicit Fire authorization, audio
  restoration, dailies advisory behavior, lineage invalidation and STOP behavior
  remain covered by the existing passing suite.
- No approved Episode 1 output was regenerated or rewritten by this
  reconciliation. The integration branch does not commit the ignored local
  media tree; production still refuses when required canon media is absent.
- The four skips are intentional environment/legacy evidence checks and are
  not used to suppress failures. Their reasons are in the test bodies.
