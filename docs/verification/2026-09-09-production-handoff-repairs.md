# Production handoff repair evidence — 9 September 2026

Status: identified software repairs passed regression verification; new animation submissions paused
by Julian. This record does not qualify finished-film quality, a live Resolve finish, or
the whole Studio for broadcast delivery. The post skill's existing eight-case qualification
record remains authoritative and has not been replaced with another rule set.

## Failures and shared repairs

| Observed problem | Shared change and evidence |
| --- | --- |
| Current revision absent from some specialist/reviewer inputs | `cb_creative` carries the active brief through every creative role. Runtime receipts bind actual model, system, context and output hashes. |
| Missing or duplicated camera views during clip allocation | Each authored view retains its ID and camera/acting content. A failed allocation returns once to scene planning with the actual capacity constraint; it cannot silently drop a reverse or ending. Incoming cut semantics are separate from outgoing provider boundaries. |
| Creative decisions routed through the routine validator | Scene creative passes use the configured premium Director route. This run recorded gpt-5.5 for those roles; routine formatting used gpt-5.4-mini. This is execution evidence, not proof of artistic quality. |
| Old intake contained stage directions inside spoken lines | Source refresh proves unchanged ordered script text before rebuilding event boundaries and occurrence IDs. It archives prior records and preserves the locked episode interpretation without claiming a new creative pass. |
| Splitting the shot risked changing approved performances | `cb_voice_reuse` copies exact approved PCM samples into new measured windows. It validates source approval, words, speaker, occurrence, voice authority and output hashes. It neither calls TTS nor claims a new human audition. |
| Handover cards omitted an explicitly registered prop and a cut's prior-state reference | `cb_handover` retains approved, shot-scoped registry prop requirements. `cb_engine` emits separate opening and previous-ending references for a cut. A missing required file stays a requirement rather than disappearing. Scene geography and new camera composition have distinct authority. |
| Replacing an approved image moved its original file | Scene-look and keyframe approval archive copies while preserving the original source path used by previous generations. |
| Correct dialogue following a cut failed R15 | The parser now recognises the numbered view after its cut instruction. Wrong or missing spoken text still fails. WATCH takes physical delivery from the Voice Director's separate physical-action field; the ElevenLabs instruction remains in HEAR. |
| Valid short-shot clocks were labelled `storyline` and rejected | Complete supplied clocks are classified as timestamp pacing, then validated for order, coverage, gaps and overlaps. No times or action are invented or discarded. Partial/invalid clocks still fail. |
| Local validation lost paid response evidence and usage | The same strict OpenAI schema is requested through `responses.create`; local validation happens after receiving the response. Completed output and known cost are retained on failure. Only the exact request digest may be revalidated locally after a repair. Incomplete responses are not accepted or automatically retried. Historic unknown reservations remain unknown. |
| Failed handover could return `alreadyPrepared` | The Studio server now propagates the actual handover failure; it no longer reports a successful preparation with a null handover. |

The response-handling implementation was checked against the installed OpenAI SDK and
[OpenAI Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs).
Its new failure-accounting and recovery cases use fake provider responses; no new paid API
test was initiated after the animation pause.

## Current live evidence

Final regression result: **1,343 passed, 4 skipped, 0 failed**, in 90 seconds.
Python compilation and whitespace checks also passed. The Studio health endpoint
reported `stale: false` and zero server-tracked jobs; no native preparation job remained.

Native Creative Room completed a two-unit plan and its internal review, then native
handover produced production revision 3. S1.SH1 is 12 seconds; S1.SH2 is 26 seconds.
The five exact dialogue occurrences carry the intended approved-sample placements.
Shot one's actual upload resolver reports seven ready assets: opening frame, Zenny,
Fuzzby, Keen, catapult, scene plate and voice track. Shot two additionally requires its
new opening and the selected exact ending of the new shot one; those media do not yet exist.

The original scene plate, S1.SH1 opening and approved 30-second voice file were verified
unchanged by SHA-256. Existing outputs were not replaced with newly approved WATCH media.
The later candidate-continuity operation has negative tests for changed/rejected/wrong-scope
sources; it has not yet been exercised with the paused new render pair.

Detailed logs and source manifests live in
`cb-output/production-runs/Ep3_S1_workflow_refire_v01/`. Read `regression_final.log` for
the final test result; earlier logs include failures that were subsequently addressed.

## Evidence boundaries

The suite includes project-scoped command/approval/budget tests, source and timing
currentness, SEE/HEAR/WATCH request handoffs, camera coverage, reference bindings and
post-package source lineage. These are code and controlled integration tests.

Still unverified by this repair run: execution of the final changed OpenAI request adapter
against the live API; the new image and animation outputs; continuous motion and lip sync;
auditory quality, comedy and emotional success; the new two-shot join; and a complete
Resolve picture/sound/export qualification. No test count, prompt score or model review
should be presented as proof of those outcomes.
