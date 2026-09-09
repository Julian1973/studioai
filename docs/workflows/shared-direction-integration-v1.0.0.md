# Shared direction integration v1.0.0

9 September 2026. Software integration release; this is not a promotion of the separately qualified post-supervisor skill.

## Production outcomes

The four outcomes remain cinematic language and continuity; character acting; dialogue; and physical, visual and effects continuity. Scene coverage precedes provider clip allocation. Camera changes serve an action, thought, reaction, relationship or reveal. Deliberate stillness and uninterrupted takes remain legitimate choices.

## Connected implementation

| Path | Implementation |
|---|---|
| New projects | New director responses require scene coverage, allocated view IDs, an authored Director Card, a playability decision and actual performed voice text. Missing, duplicated or changed view allocations cannot silently enter production. |
| Existing Crystal Bears workflow | Scene coverage is created before the shot conference and retained in the storyboard. Existing approved cinematography and performance records are projected into the shared card; their authority is retained. Typed cut/move/hold decisions reach the animation compiler without depending on keywords in prose. |
| Chat Director | The selected shot's acting, listener behaviour, emotional/comic intent, planned coverage and recorded dialogue timings reach the conversational Director from the same approved authorities. Camera guidance preserves motivated cuts instead of forcing a single composition. Estimated timings remain explicitly distinct from measured audio. |
| SEE | Opening state, attention, starting pose, camera and references reach the image request. Later acting and ending states are not opening-frame requirements. A declared time jump or independent scene does not inherit the previous pose. |
| HEAR | The voice specialist receives playable intentions and listening context; ElevenLabs receives validated performed text with exact spoken words. New project voice generation uses timestamped dialogue output, checks speaker ownership and binds measured turns to the recording hash. |
| WATCH | Direction, views, meaningful physical state changes, authorised sound cues, exact dialogue timing and ordered references reach the request. New results retain their originating shot, direction revision and execution receipt. Existing submitted envelopes remain immutable. |
| Sound | WATCH sound changes invalidate dependent WATCH work. Post-only cues preserve SEE, HEAR and WATCH. Explicit generated sound is retained in the provider mix, with the approved voice conform available separately; no isolated stem is invented. |
| Revisions | Shot edits update their upstream scene view allocation. Other units retain their views. SEE only changes for relevant opening changes; approved voice survives visual-only revisions. Prior coverage and direction revisions remain available, including undo. |
| Review and post | Reports bind to the exact render and its originating direction. Available neighbouring clips and saved trims produce bounded picture-and-sound hard-cut auditions. Full video review and sampled-frame review describe their actual evidence separately. Post briefs carry direction and source-bound receipts. |
| User interface | SEE → HEAR → WATCH remains the review sequence. A collapsible card shows acting and planned views. The returned HEAR player precedes adjacent approved words and performance prompt. No new human approval stage is introduced. |

The packing audit now matches the existing typed limits of five stages and six views. These are representation limits, not a target or proof that a scene is playable. Emotional keywords no longer block a deliberate cut. Compulsory held endings and the stale instruction to replace Seedance music with an ElevenLabs score were removed. Honest duration still controls whether a unit must be restructured.

## Verification

- Final full repository run: **1,290 passed, 4 conditionally skipped**, zero failures in 88.68 seconds. Command: `python3 -m pytest engine cb-studio -q --disable-warnings --maxfail=3`.
- The four skips concern three unavailable historical revision-6 fixtures and a refusal test whose live storyboard is already approved. Current isolated end-to-end, approval, handover, provider recovery, continuity, voice, post and UI tests passed.
- Real Chrome test: mounted the project desk with an isolated fixture; opened the card; checked acting and coverage text; switched between two shots; confirmed no duplicate/stale card and no JavaScript errors. This was a functional browser check, not a new visual-design certification.
- Python compilation, JavaScript syntax and changed implementation whitespace checks passed.
- Local Studio health and Director session responded successfully after service reload. Approved keyframe, approved voice and current Ep3 scene package hashes were unchanged.
- Live selected-shot context contained approved acting, cinematography, three planned views and five dialogue lines, attached to its direction revision. Health confirmed current code with no active render jobs.
- Tests prevent external provider connections and isolate mutable production state. Synthetic provider responses validate software handoffs, not artistic performance.

ElevenLabs timestamp transport was checked against its [official dialogue-with-timestamps API documentation](https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert-with-timestamps). Returned times are provider evidence, not a claim that a reviewer listened or that a render's mouth movements match.

## Evidence boundary

Coverage, playability, observed media and audience readability remain separate assessments. Human shot approval is separate from adjoining-cut review and delivery readiness. Existing still-frame-only legacy reviews explicitly leave sound, continuous motion and assembled-cut judgment unverified. Full video/audio review requires a configured project review service; post review requires the actual media.

This release does not claim AAA acting, broadcast readiness or a pass of the post supervisor's eight real-film qualification cases. Those claims require inspected finished picture and sound and the human verdicts defined by that existing evidence record. The post-supervisor qualification status has not been promoted.
