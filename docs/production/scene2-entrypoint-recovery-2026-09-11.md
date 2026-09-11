# Scene 2 entry-point recovery

The user encountered three distinct integration faults on the actual production corridor:

1. A JSON null shot ID became the literal `None` string during scene-world preparation. Preparation/save/decision now preserve scene scope; HTTP route regressions exercise null targets.
2. Cinematography preparation called the WATCH opening-image observation handoff before SEE had created an image. Stage-specific preparation now preserves coverage/continuity work while deferring image observation until WATCH. Tests preserve the WATCH requirement.
3. `build_keyframe`, the button/CLI entry point, referenced an undefined `compare` variable. It now declares and forwards its comparison mode, matching the existing underlying generator default. Tests exercise both modes and their billing prerequisites.

The preceding golden tests exercised the lower-level generator, not this higher-level build entry point. Passing those tests did not establish coverage of the failed button path. New entry-point tests close this specific gap; no general readiness claim follows.

The undefined-name scan additionally identified an unbound render-module name in the Director-session fallback, now explicitly loaded. The guarded opening-cast expression was simplified to its already defined local source. Pyflakes reports no undefined names in the four checked corridor modules after correction.

Validation: 29 golden-path tests passed after the build-mode correction; earlier handoff tests and HTTP null-scope tests cover the other faults. The retry runs as Studio job `shotbuild-keyframe_s2_1789130702_356bb1`, so its result and evidence remain in the Studio, not only in chat. Submission and returned media must be verified separately.

Live recovery completed: the Studio job reports `done`, with Seedream candidate `Ep3_S2.SH1_keyframe_A_79ecc15d.png` and Nano Banana candidate `Ep3_S2.SH1_keyframe_B_c22af5a7.png` returned into the Scene 2 SEE ledger for human selection. No animation was fired and neither generated keyframe was automatically approved. Additional HTTP/auth/loading suite: 45 tests passed.
