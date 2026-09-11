# WATCH production prompt structure 1.0.0

Adopts the producer's Seedance template supplied on 2026-09-11, using current typed direction rather than the example shot. Implemented in `studio_watch_structure.py`, invoked by the native animation compiler and the execution compiler before Prompt Director review/sealing. No media generation or production-package mutation is part of this change.

## Field mapping

- PURPOSE / STORY BEAT: current audience intention and generation goal.
- REFERENCE AUTHORITY: actual ordered upload bindings; opening, identity, set, prop and preceding-frame roles remain distinct.
- OPENING STATE: first authored stage's initial/carried state, otherwise an explicitly supplied textual opening state. No guessing from an image or using the ending as the start.
- TIMED ACTION: complete current views or continuous phases, including the authored camera, visible cast, action, performance, exact spoken-action markers and per-view end states. View timings are retained, never assigned equally or copied from the example. A continuous plan remains continuous.
- CAUSALITY: authored physical cause and effect when supplied.
- GEOGRAPHY / MUST PRESERVE: existing current geography and state-sensitive continuity clauses. State evolves as directed; a reference cannot reset a moved object.
- CONTINUITY OUT: current authored handoff. LANDING and PERFORMANCE remain in their respective views, rather than repeating the sequence globally.
- AUDIO AUTHORITY / AUDIO-FOLEY: existing protected `[Dialogue Authority]`, `[Audio]` and `[AUDIO AND EXCLUSIONS]` blocks remain byte-for-byte unchanged, including their headings. Exact dialogue stays once in its assigned view; measured cue intervals remain bound to Audio1. Explicit Seedance SFX permissions survive. The example's blanket laughter prohibition is not a new studio rule.
- ACTING FREEDOM / DO NOT: existing authored instructions and scoped safeguards remain; the template does not add an unrequested list of prohibitions.
- PROJECT, duration, aspect ratio and source hashes remain request metadata. FINAL VALIDATION remains durable review evidence, not a provider-facing claim of success.

The heading aliases in the structural reviewer and role-binding code recognise the new structure. Existing sealed requests and approved media are not rewritten. Freeform legacy, edit and extension prompts retain their own structures; this is not a claim that every historical route has been migrated.

## Evidence boundary

Offline tests cover actual compiler output, unchanged dialogue/audio/references, reference-local visibility, continuous versus cut coverage, no invented timings, idempotent formatting, preserved authored SFX, and native review/seal behaviour. Semantic reviewer responses in route tests are fixtures. No real image understanding, lip-sync, acting or render-quality qualification is claimed.

The separately observed `test_current_path_reaches_an_approved_master_without_provider_spend` prompt comparison remains outside this change: it compares the submitted request against `_approved_seedance_prompt`, which retrieves specialist output plus scale control, before final request compilation. That distinction requires separate audit; the failing assertion must not be counted as passed.
