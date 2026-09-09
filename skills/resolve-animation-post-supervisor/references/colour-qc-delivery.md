# Colour, QC and delivery

## Colour and image repair
Inspect input colour tags, range, transfer interpretation, project colour management and output intent before grading. Prevent double transforms. Use a shared technical transform only for clips with matching interpretation; place individual exposure/white-balance/hue corrections at clip level. Shared scene/location groups carry common look, with one deliberate output transform. Preserve recoverable grade versions and compare approved stills plus moving adjacent shots.

Check canonical fur/eyes/props, highlight and shadow detail, saturation, shot density, flicker, banding and edge instability. Avoid forcing a fundamentally different lighting direction into continuity with colour alone. Test focus/sharpen/deblur tools only if available in the installed edition and callable route. Inspect moving edges and texture stability before applying broadly. Do not advertise software release features as installed capabilities.

## Evidence and disposition
Keep findings in existing episode manifest/report records, keyed to the actual master hash. Each finding should carry: ID; shot/source references; timeline seconds and frames/timebase; category; critical/major/minor severity; observation; inspection mode (sampled stills, continuous motion, listened, measured); proposed/performed repair; before/after evidence; remaining limitation; disposition.

Use dispositions flagged, repaired-awaiting-check, verified, unresolved or unverified. Verified applies to a named check and artifact only. Track reviewed coverage and any skipped ranges. A contact sheet is a sampled visual pass. A timeline probe finds structure, not dramatic or audiovisual quality. Advisory craft scores cannot override critical findings or human judgment. Do not infer children's comprehension from a numeric score or claim audience testing that did not occur.

Use diagnostic passes where the inputs support them: silent picture for action and visual intention; dialogue/performance without score for timing; full mix for the actual experience. Genuine stems are needed to mute music or effects independently. These are questions about clarity, not universal pass/fail tests: an intentionally sound-led joke or dialogue-led revelation may require sound to work. Record the inspection mode and assess readability against this project's audience.

## Behavioural qualification of skill changes
Maintain eight real-production cases in `cb-output/post-skill-qualification/qualification.json`, with project-local evidence links. Do not create or render test footage without the relevant authorization:
1. A continuation with a faulty pickup.
2. A strong outgoing music cue colliding with the next entrance.
3. A flattened mixed-audio repair near protected dialogue/effects.
4. A deliberate hard cut that should be preserved.
5. A technically clean export with a creative continuity defect.
6. Identity drift requiring regeneration rather than a cosmetic mask.
7. A small defect that a trim or bounded Fusion repair can resolve.
8. Existing Seedance score timing that should remain untouched.

For each log: project/episode; starting candidate hash; observed problem or intended contrast; inspection mode; evidence and time range; diagnosis; action or justified non-action; resulting candidate hash; verification method and coverage; human verdict with reviewer/date; proposed lesson and whether it was adopted. For a justified non-action the resulting hash remains the starting hash. Leave unavailable evidence and verdicts null, not passed.

Promotion to production v1.0 requires evidence-backed disposition and explicit human acceptance for all eight cases, including justified non-action cases, with no unresolved critical regression. A failure remains open through retest; do not promote on a numeric average or invent historical human verdicts. A lesson is a proposed scoped change, not permission to rewrite global rules automatically.

Qualification execution follows the eight-case procedure above. Do not add new qualification cases, claim a pass, or promote the skill outside that evidence record.

## Export verification
Render to a new versioned destination after checking disk space, range, fps, resolution, colour tags and audio channels. Record actual rendering method: native Resolve, stream copy/remux or external encode. Verify file exists, opens/decodes, has expected start/end and duration/frame count, and preserves sync. Check repaired scenes, black/frozen/flash frames, credits, effects, colour interpretation and final fade. Inspect unexpected timestamp gaps, but do not confuse packet continuity with clean audible playback.

The release checklist is conjunctive: required technical checks passed; full motion/listening coverage performed by a capable reviewer; critical defects resolved or explicitly accepted with documented limitation; named output spec met; exact version approved by the project's human director. Uninspected domains stay unverified. A successful render or high craft score never grants approval.

## Project-selected review and enhancement

Use the project's agreed review route, output specification and provider. The following Google/vCube procedure applies only when those services are selected; local review and other projects do not inherit that delivery requirement. For the existing legacy finishing desk, preserve the recorded Google receipt requirement.
Register an immutable candidate in the existing post workspace. Verify the copied hash, remote file identity/size and playback before a Google review receipt; upload processing is pending, not playable. Do not loosen sharing permissions without scope. Approval attaches to the exact pre-enhancement file and never starts spending by itself.

Use the existing BytePlus VOD/vCube adapter, account readiness and separately authorized allowance. Do not substitute fal, ModelArk or another service. Never expose credentials. Retain job IDs and reconcile ambiguous submissions before retrying. Provider success means awaiting QC, not delivery.

Check the enhanced result against the signed cut for duration, frame cadence, dropped/repeated/interpolated frames, audio correspondence and lip-sync, character detail, texture shimmer, colour/HDR interpretation and credits. A 3840×2160 file alone is only dimensional upscaling. Publish or deliver only within authorization and report the verified endpoint.
