# Editorial cut and continuation handoff

Implemented 7 September 2026.

The runtime production standard and installed production-director skill now require a deliberate choice between continuation and a motivated cut, including reverse coverage. The storyboard transition controls handover: PLANNED_CUT gets a shot-owned opening keyframe even when a stale requiresNewKeyframe flag is false. Separate metadata retains the preceding shot as the world/action-state source without making it a pixel anchor.

Both deterministic provider compilers emit the handoff instruction. A cut composes its own opening view while preserving geography, props, action phase, emotional state and matched eyelines. The animation begins on that approved frame; the edit joins the clips. Continuation uses the accepted predecessor landing. Newly prepared shots display the join in the shot strip. Existing approval stages are reused.

## Verification

- Full suite: 1,091 passed, 4 skipped. A final prompt-section heading refinement was then covered by the focused suite: 114 passed, 1 skipped.
- Regression tests cover a declared cut with a contradictory old keyframe flag, retained predecessor state, continuation frame sourcing, and handoff delivery in both real prompt compilers.
- JavaScript syntax passed; repo and installed production-director skills match.
- Source audit: 158 Python files, 50 documents, no issues.
- Live service: stale=false, running=0. All 19 accepted takes and landing-frame hashes remain intact. Production job counts remain unchanged.

No production records were migrated or renders submitted. Tests use isolated fixtures and mocked providers; this verifies software routing and prompt delivery, not a paid reverse-angle render or its visual quality. Existing approved shots retain their prompts until an explicitly scoped revision. Standalone chat advice is still not a production record by itself.

Evidence: accompanying cut-handoff focused/full test logs, source and production audit JSON, and scoped patch against the pre-change backup.
