# Seedance 2.5 Production Blueprint

Research date: 2026-07-31  
Project: Crystal Bears Studio / 8th Hour Animation Studio  
Decision status: recommended architecture; Seedance 2.5 production activation not approved

## Executive decision

Seedance 2.5 is a strong prospective fit for Crystal Bears because almost every scene is
under 30 seconds. Its advertised scene length, reference capacity and local editing could
reduce visible joins and let comic timing, emotional turns, camera rhythm and sound develop
inside one coherent generation.

It should not replace the Studio's directing, approval, lineage, spend or post-production
system. It should become another renderer behind that system.

The correct decision today is:

1. Keep the current fal Seedance 2.0 route as the production path.
2. Refactor the hard-coded provider/model assumptions behind a capability-driven adapter.
3. Add a scene-length generation contract without removing the existing shot contract.
4. Leave Seedance 2.5 disabled until a real model ID, API schema, price and terms are
   verified for Julian's account.
5. Run a small, explicitly authorised A/B qualification before making 2.5 the default.

This is not caution for its own sake. As of the research date, Dreamina markets Seedance
2.5 features, but fal says 2.5 is announced and not yet live on fal, and BytePlus documents
Seedance 2.0 model IDs rather than a 2.5 production endpoint. There is not yet enough
verified API information to wire a paid production route honestly.

## Current Studio audit

The existing application is not starting from zero. It already contains several controls
that must survive the upgrade:

- `engine/cb_engine.py` has typed shot, dialogue, performance and continuity contracts, but
  fixes every provider shot to 4-8 seconds.
- `engine/cb_render.py` creates controlled candidate sets, requires approved opening frames
  and voices, seals exact provider inputs and maximum cost, and preserves human approval.
- `engine/cb_gen.py` hard-codes fal Seedance 2.0 reference-to-video endpoints and waits with
  blocking `subscribe()` calls.
- `engine/cb_safety.py` and the sealed envelope also hard-code provider, model, endpoint,
  720p resolution and 2.0 assumptions.
- `engine/cb_costs.py` and `engine/billing_profile.json` protect paid generation with
  confirmed model-specific rates, but are not yet a runtime capability/quote system.
- `engine/cb_post.py` transactionally builds and hashes 16:9/9:16 outputs, captions and
  programme audio, but currently normalises audio at 44.1 kHz and does not fully validate
  codec, colour or frame-rate delivery properties.
- `skills/seedance-production-director/SKILL.md` already has the right compact-shooting-script,
  reference-role, performance and continuity discipline. It needs a scene/unit input rather
  than a replacement creative philosophy.

The no-spend test run on 2026-07-31 produced `175 passed, 4 skipped, 10 failed, 2 errors`.
Every observed failure/error was caused by tests expecting the now-archived live `Ep1`
storyboard, beat package or production package in `cb-output`, rather than constructing an
isolated fixture. This is not evidence that the new research document broke runtime code,
but it is a genuine fresh-project defect. The golden path must start from a test-owned
script fixture and leave production state empty before and after the test.

## What is verified, claimed and unknown

### Availability matrix

| Surface | Current evidence | Duration | References | Output | Price | Production conclusion |
|---|---|---:|---:|---|---|---|
| Dreamina Seedance 2.5 UI | Official product pages advertise it; access may vary by account and region | Up to 30s advertised; longer beta modes are also mentioned | Up to 50 multimodal inputs advertised | Native 4K and local editing advertised | Not published as an API rate | Useful for manual evaluation, not proof of an automatable production API |
| fal Seedance 2.5 | fal's current article says announced, not yet released on fal | 30s reported | 50 reported | 4K reported; native audio not confirmed | Unannounced | Do not invent an endpoint or cost |
| BytePlus ModelArk Seedance 2.5 | No verified 2.5 model ID, request schema or price found in current official documentation | Unknown | Unknown | Unknown | Unknown | Capability probe must remain closed |
| fal Seedance 2.0 reference-to-video | Live and already integrated in Crystal Bears Studio | 4-15s family limit; Studio currently constrains shots to 4-8s | Up to 9 images, 3 videos and 3 audio references on the documented family route | Current Studio route is 720p with native audio | Studio uses a confirmed upper bound of about $0.3034/output-second standard and $0.24 fast | Keep as the known fallback and comparison baseline |
| BytePlus ModelArk Seedance 2.0 | Official asynchronous API is documented | 4-15s or automatic within the model rules | 0-9 images, 0-3 videos and 0-3 audio; image or video is required | 480p, 720p, 1080p and 4K vary by model; documented 4K output is 10-bit H.265 | Token based and model specific | Viable alternative adapter only after account-level validation |

### Officially advertised 2.5 strengths

Dreamina's own pages advertise:

- Up to 30-second standard generations.
- Up to 50 mixed script, image, video, audio, music and style references.
- 4K output.
- Multi-shot camera and audio control.
- Local region editing rather than regenerating the whole result.
- White-model or simplified previews for testing movement and spatial interaction.

These are product claims, not yet a stable third-party API contract. Dreamina's pages are
also internally transitional: one page says 2.5 is live while another describes expected
availability and account/region variation, and an embedded creation surface can still name
2.0 mini. The Studio must therefore discover capabilities from the chosen provider at
runtime instead of encoding marketing copy as truth.

### Unknowns that block production activation

- Exact fal or BytePlus 2.5 model ID and endpoint.
- Request and response schema.
- Which input combinations are accepted.
- Minimum and exact maximum duration per route.
- Reference count by media type, file limits and ordering semantics.
- Whether supplied dialogue audio is preserved, transformed or only used as guidance.
- Native audio behavior, channels, sample rate and language behavior.
- Exact frame rate, codec, bit depth, colour tags and keyframe interval of output.
- Watermark and provenance controls.
- Price, successful-output billing rules and retry charging behavior.
- Job retention and generated-media URL lifetime.
- API availability in Julian's account and region.
- Commercial-use terms for the exact account, plan and delivery territory.

No production code should guess any of these.

## The right production model

### The Studio remains the brain

AI can take a locked script through most of the preparation and execution work, but it
cannot be the authority for story truth or final quality. The working division should be:

**AI prepares and executes**

- Parse the immutable script version.
- Preserve every event and dialogue occurrence.
- Propose scene beats, performance, staging, camera and edit rhythm.
- Build scene audio timing, reference manifests and opening frames.
- Compile the provider instruction.
- Validate mechanical constraints.
- Disclose cost and submit only after authorisation.
- Ingest, hash, probe and organise results.
- Flag likely identity, continuity, speech, artefact and delivery failures.
- Conform approved material and prepare delivery candidates.

**Julian's eye and ear decide**

- Is it funny in an observational family-comedy way?
- Is the emotion legible, honest and earned?
- Does the performance feel alive rather than merely compliant?
- Are character appeal, staging and visual quality at the show's bar?
- Is a candidate approved, repaired, split or rejected?
- Is the final master ready to leave the Studio?

No automated score may approve creative quality or a final master.

### Scene-as-unit, shot-aware

The new primary object should be a `GenerationUnit`, not a provider clip and not blindly an
entire scene. A unit may contain one to three motivated cinematic views and must end in an
explicit continuity state.

A scene may be one 2.5 unit when all of these are true:

- Its natural duration is 30 seconds or shorter within the verified API.
- It is one continuous place and time.
- Its action can be expressed as a clear setup, development and payoff.
- The number of characters, actions, props and camera changes is visually manageable.
- Exact dialogue timing fits the verified audio-reference limits.
- The required final frame can be described and reviewed clearly.

Split a scene at a motivated edit even when it is under 30 seconds when:

- It contains competing actions or more than one major physical gag.
- Several characters must speak and react at once.
- Identity or spatial continuity is already fragile.
- It changes location, time, scale or visual rules.
- A precise insert, reaction or transformation is business-critical.
- Regenerating the whole scene would throw away too much good approved material.

The central rule is: duration capacity is not complexity capacity.

### Quality target without copying another property

The creative brief should translate references such as Bluey, Inside Out and Pixar into
production qualities rather than ask a model to imitate protected characters or a house
style:

- Observational humour that grows from character behaviour and family truth.
- A child-readable surface with an additional emotional read for adults.
- Clear wants, needs, reactions and emotional turns.
- Strong silhouette, eyelines, anticipation, contact, weight and readable payoff poses.
- Premium theatrical 3D materials, lighting, composition and camera discipline.
- Restraint: one strong joke or feeling lands better than several compressed events.

Crystal Bears canon, approved designs and its own visual bible remain the actual style
authority.

## The scene generation contract

The provider-neutral contract should be typed and immutable after approval. Provider
adapters compile this contract into the exact schema their model accepts.

```json
{
  "schemaVersion": "scene-generation/v1",
  "unitId": "E101.S03.U01",
  "scriptVersionId": "immutable-version-id",
  "sceneNumber": "3",
  "durationSec": 24,
  "aspectRatio": "16:9",
  "resolutionIntent": "2160p",
  "frameRateIntent": "native-24-or-25",
  "openingState": {
    "referenceId": "opening-frame",
    "description": "approved composition and exact starting state"
  },
  "timeline": [
    {
      "startSec": 0,
      "endSec": 6,
      "shotId": "S03.SH01",
      "purpose": "setup",
      "performance": "one observable action and reaction",
      "camera": "one motivated framing or move"
    },
    {
      "startSec": 6,
      "endSec": 16,
      "shotId": "S03.SH02",
      "purpose": "development",
      "performance": "visible cause and consequence",
      "camera": "intentional cut or continuous reframe"
    },
    {
      "startSec": 16,
      "endSec": 24,
      "shotId": "S03.SH03",
      "purpose": "payoff and emotional landing",
      "performance": "payoff, reaction, then living hold",
      "camera": "composition that delivers the ending"
    }
  ],
  "dialogueOccurrences": [
    {
      "id": "script-occurrence-id",
      "speaker": "canonical-character-id",
      "audioWindow": {"startSec": 7.2, "endSec": 9.8}
    }
  ],
  "referenceManifestId": "immutable-reference-manifest-id",
  "audioGuideId": "immutable-scene-audio-id",
  "closingState": {
    "composition": "exact required final composition",
    "characterState": "pose, gaze, expression and screen position",
    "propState": "all persistent prop and mark states",
    "cameraAndLight": "height, side, lens intent and light direction"
  },
  "prohibited": [
    "only failures materially likely in this scene"
  ]
}
```

Dialogue text remains in the script and audio contracts. It does not enter the visual
provider prompt. This retains the Studio's existing rule that the approved audio carries
the exact spoken words.

## Reference best practice

### One reference, one job

Do not treat an advertised limit of 50 references as a target. Extra or contradictory
references can diffuse attention. A normal scene should start with the smallest sufficient
set, usually:

1. Approved opening frame or previous approved closing frame.
2. Scene Look for environment, palette, materials and established lighting.
3. One approved identity asset per visible principal character.
4. One scale or lineup reference when relative scale is important.
5. A hero prop reference only when the prop matters to the action.
6. A motion or camera reference only when it communicates something text cannot.
7. The exact scene dialogue/performance guide.

Every entry in the manifest needs:

- Stable logical ID and provider slot.
- Single declared role.
- Absolute local source path at submission time.
- SHA-256 digest, dimensions, duration and media type.
- Canon or approval version that authorised it.
- Rights/provenance record.
- Priority and any known conflict with another reference.

The adapter must reject duplicate roles, missing files, changed hashes, unsupported file
types and references beyond the discovered provider limits before spend authorisation.

### Reference priority

When instructions compete, compile the intended hierarchy explicitly:

1. Opening state and continuity.
2. Character identity and relative scale.
3. Script action and exact audio timing.
4. Scene geography and hero props.
5. Camera and performance reference.
6. Surface style detail.

Reference slots must be generated by the adapter. The internal contract should use names
such as `opening-frame` and `dialogue-guide`, not hard-code `@Image1`, `@Audio1` or a
provider-localized slot name throughout the application.

## Prompt best practice

The prompt should be a compact shooting script, not a prose mood board and not a dump of
the show bible.

For each internal shot provide:

- A time range or ordered shot number.
- Shot size, useful lens intent and camera behaviour.
- One primary physical or emotional action.
- Cause, contact, weight and visible consequence.
- Speaker/listener mouth behaviour tied to the approved audio reference.
- Useful foreground, midground and background geography.
- Two to four motivated details of light, depth, atmosphere or material response.
- The composition and living action on which the shot ends.

Across the unit provide:

- Exact opening state.
- Setup, escalation/development and payoff/reaction.
- Only intentional cuts.
- Exact closing continuity state.
- At most a few scene-specific negative constraints.

Avoid:

- Copying dialogue words into the visual prompt.
- Long generic quality adjectives.
- Repeating identity descriptions already supplied as references.
- Several actions in one sentence or shot.
- Conflicting camera moves.
- A universal negative wall.
- Asking the model to invent story, jokes, props or continuity.
- Filling 30 seconds simply because 30 seconds is available.

The existing `seedance-production-director` skill already follows much of this discipline.
Its next version should accept a generation unit and emit a timed multi-shot scene brief
while preserving its current rule that it never spends or self-approves.

## Audio strategy

### Authoritative scene audio

Build one immutable scene audio guide before video generation:

- Exact approved dialogue performances at approved timecodes.
- Silence where no one speaks.
- Optional temporary timing cues for reactions and physical beats.
- 48 kHz, 24-bit WAV as the internal source.
- Stable occurrence IDs in a sidecar timeline.
- Separate dialogue source retained even when the provider returns mixed audio.

The visual prompt refers to the audio asset and speakers without repeating the words. The
model may add performance-compatible ambience, SFX or music only if the verified endpoint
supports this without changing or duplicating dialogue.

### Qualification tests for native audio

Before enabling native audio for 2.5, compare two explicit modes:

**Mode A: integrated generation**

- Supply the exact scene audio guide.
- Allow documented native SFX/music generation.
- Check for changed words, duplicate voices, language drift and destructive processing.

**Mode B: protected dialogue**

- Generate picture with the guide used for timing/performance.
- Preserve the original dialogue master for final post.
- Add or replace SFX/music in post when required.

The preferred mode is whichever retains exact dialogue and yields the best mouth and body
performance. A good picture should be locked before spending on another full video render.
Where possible, test the smallest audio, mix or local-edit correction first.

## Candidate and spend strategy

The current controlled candidate-set model remains correct. Longer generations make spend
and waste larger, so authorisation must become stricter, not looser.

Before a paid request, disclose and seal:

- Provider, exact model ID, endpoint and schema version.
- Exact prompt bytes.
- Duration, resolution, aspect, audio and watermark settings.
- Ordered references and hashes.
- Candidate count.
- Provider price snapshot and billing unit.
- Maximum authorised cost including tax policy if known.
- Request idempotency key and expiry.

Never estimate 2.5 using the 2.0 rate as if it were a fact. Until an official price is
available, the authorisation button remains disabled.

For the current 2.0 standard bound, one 8-second candidate is about $2.43 and a batch of
three is about $7.28. One 15-second batch of three is about $13.65. These are useful
baseline comparisons only; they are not 2.5 forecasts.

### Retry rules

- A network timeout after submission is not permission to submit again.
- Persist the provider request ID before waiting for completion.
- Reconcile status before any retry.
- Use one idempotency key for one sealed request.
- Treat webhook delivery as at-least-once and process it idempotently.
- Separate provider infrastructure retries from creative rerolls.
- A successful but creatively poor result is a charged candidate, not a technical retry.
- After one unchanged reroll, diagnose the repeated defect and change the input or split the
  unit; do not enter an open-ended prompt-patching loop.

fal recommends asynchronous submit plus polling or webhooks for production. Its webhook
documentation requires signature verification, timestamp checking and idempotent handling,
and notes that failed deliveries can be repeated. The current blocking `subscribe()` path
should therefore be retained only until the provider-job state machine is introduced.

## Ingest and preservation

Provider output is source material, not a final master.

Immediately after successful generation:

1. Download to a temporary local file.
2. Verify HTTP completion and non-zero size.
3. Probe container, streams, duration, dimensions, frame rate, codec, pixel format, audio
   channels/sample rate and colour metadata.
4. Compute SHA-256 before exposing the asset.
5. Save the complete provider response, request ID and timing/cost metadata.
6. Move source and manifest atomically into immutable candidate storage.
7. Create viewing proxies separately; never overwrite the provider source.

This matters because provider jobs and URLs are not an archive. BytePlus explicitly says
its video task IDs are retained for only seven days.

## Quality-control gates

### 1. Mechanical gate

All must pass:

- Readable video stream and expected audio policy.
- Duration within the verified endpoint tolerance.
- Intended aspect ratio and sufficient dimensions.
- No truncated or corrupt media.
- Frame count and frame rate are credible.
- Audio is not clipped, silent by accident or the wrong channel layout.
- No unexpected visible watermark, subtitles, logos or generated text.
- Every requested script occurrence is represented in the timeline.
- Provider response, source file and manifest hashes agree.

### 2. Script and performance gate

- No line is omitted, duplicated, rewritten or assigned to the wrong character.
- No extra speech, vocalisation or language drift.
- Dialogue starts and ends in its approved window.
- Listeners remain listeners when they should not speak.
- The setup, development and payoff all read.
- Physical causes and consequences are visible.
- The emotional turn is visible without explanatory text.

### 3. Visual and continuity gate

Review the Studio's existing ten criteria:

- Character identity.
- Relative scale.
- Starting geography.
- Action readability.
- Physical cause and effect.
- Comic or emotional performance.
- Camera behaviour.
- Dialogue and mouth performance.
- Continuity.
- Final-frame usability.

Also inspect frame-by-frame for morphing, limb/prop errors, texture crawl, eye/gaze errors,
unmotivated background motion, flicker, lighting jumps and compressed edits. Automated
checks may flag these, but the human review remains authoritative.

### 4. Repair decision

Choose the smallest intervention that preserves approved work:

1. Keep the candidate when it succeeds.
2. Trim or re-time only when no approved word/action is damaged.
3. Use verified local editing for a genuinely local defect.
4. Repair or replace audio while locking good picture where sync permits.
5. Reroll unchanged once when failures appear random.
6. Correct opening frame or references for repeated identity/geography failure.
7. Simplify or split for repeated action/timing failure.
8. Use the 2.0 shot route or another approved method when the unit is model-limited.

## Post-production and delivery

### Required scene package

Every approved scene should contain:

- Immutable provider source(s).
- Provider request/response and cost manifest.
- Approved generation-unit contract and reference manifest.
- Conformed 16:9 picture.
- Reviewable 9:16 derivative.
- Authoritative dialogue source and final programme audio.
- SRT and VTT captions tied to immutable dialogue occurrence IDs.
- QC report and human approval record.
- Asset hashes and provenance/rights manifest.

### Mastering policy

The provider output should be normalised only after approval:

- Preserve native frame rate unless the delivery specification requires a controlled
  conform. YouTube recommends uploading at the native frame rate.
- Normalise SDR colour to tagged BT.709/Rec.709 only through a tested colour-managed path.
- Use 48 kHz audio throughout production and delivery.
- Retain a high-quality archive/mezzanine master with 24-bit PCM audio.
- Build the platform MP4 separately using H.264 High Profile, progressive scan, 4:2:0,
  AAC-LC, fast-start metadata and the platform's current bitrate requirement.
- Deliver the highest genuinely generated/finished resolution. Upscaling does not repair
  weak staging, lighting, identity or motion.

YouTube's current recommended upload settings specify MP4, H.264 High Profile, progressive
scan, native frame rate, 4:2:0, AAC-LC or Opus at 48 kHz, BT.709 for SDR and 35-45 Mbps for
standard-frame-rate 4K. Platform specs must be checked again at final delivery.

### Current post gaps to close

The existing post path is a strong transactional base: it builds immutable candidates,
hashes outputs, validates aspect/duration/audio presence, exports SRT/VTT and 24-bit
programme audio, and requires a final human gate. For 2.5 delivery it should also:

- Change internal audio normalisation from 44.1 kHz to 48 kHz.
- Record video codec, pixel format, frame rate, audio sample rate/channels and colour tags in
  deterministic QC.
- Add explicit BT.709 output metadata for SDR masters.
- Add a true archive/mezzanine master instead of treating H.264/AAC as the only master.
- Increase the YouTube delivery audio bitrate from 256 kbps to the current 384 kbps stereo
  recommendation when that is the selected platform profile.
- Make 4K or 1080p an explicit delivery profile rather than inherit mixed provider sizes.
- Review vertical framing shot by shot. The current fixed centre crop is a baseline, not a
  guarantee that action, faces or captions remain safe.
- Verify loudness targets against the actual distributor delivery specification. YouTube
  does not publish a simple universal mastering mandate equivalent to EBU R128; the current
  `-14 LUFS` profile should be treated as a house web target, not described as a YouTube
  delivery law.

For UK/EU broadcast delivery, EBU R128 remains the authoritative starting point at -23 LUFS
programme loudness with the applicable true-peak rules. Netflix, Amazon or broadcaster
delivery must use the current title-specific delivery specification supplied for that job,
not a remembered generic number.

## Rights, safety and provenance

- Only submit scripts, designs, voices, music, performances and references the production
  has the right to use.
- Store licence/source information beside every reference and final asset.
- Never use protected characters or frames from another show as production references.
- Keep API keys server-side and out of browser code, logs, screenshots and manifests.
- Do not automate Dreamina's consumer UI as a substitute for an API. Use an authorised API
  route whose terms permit the workflow.
- Review the exact plan and regional terms before commercial release. Dreamina's terms say
  users retain ownership of inputs/outputs as between the parties when compliant, but also
  grant the service broad rights and do not guarantee uniqueness, faithfulness or freedom
  from third-party claims.
- Preserve required AI provenance or watermarks where contract or law requires them; never
  strip one without confirming the applicable rule.
- Use provider safety identifiers and retain moderation outcomes without storing secrets.

This section is operational guidance, not legal advice. Commercial distribution needs a
production-specific rights review.

## Architecture changes

### 1. Capability-driven provider boundary

Introduce a provider interface with these responsibilities:

```text
capabilities()        -> verified limits and supported fields
validate(request)     -> zero-spend local/provider-schema validation
quote(request)        -> exact current price basis or unavailable
submit(request, key)  -> durable provider request ID
status(request_id)    -> queued/running/succeeded/failed/cancelled
cancel(request_id)    -> best-effort provider cancellation
ingest(request_id)    -> atomic local source plus manifest
```

Capabilities must include provider, model ID, endpoint, schema version, durations,
resolutions, input combinations, per-type reference limits, audio, watermark, output
properties, pricing source and `verifiedAt` timestamp.

Recommended implementation shape:

- `engine/cb_video_providers.py` - interface, registry and capability validation.
- `engine/cb_provider_jobs.py` - durable asynchronous job lifecycle and idempotency.
- `engine/cb_generation_units.py` - typed scene/unit contract and split policy.
- `engine/model_registry.json` - versioned, reviewable model configuration and pricing links.
- Existing `cb_gen.py` - thin media helpers and temporary backward compatibility.

### 2. Dual-granularity production contracts

Do not stretch the current `Shot.durationSec` from 8 to 30 and call that a scene. Preserve:

- `Shot` as one cinematic view/performance assignment.
- `GenerationUnit` as one provider request containing ordered shots.
- `Scene` as the script/editorial container containing one or more units.

The current 4-8 second shot rule can remain valid inside a longer unit. A separate verified
provider limit governs total unit duration.

### 3. Durable provider jobs

Replace the final blocking call with a state machine persisted in SQLite:

```text
DISCLOSED -> AUTHORISED -> SUBMITTING -> QUEUED -> RUNNING
          -> SUCCEEDED -> INGESTED -> QC_PENDING -> REVIEW -> APPROVED/REJECTED
          -> FAILED/CANCELLED
```

Submission, spend reservation and provider request ID persistence must be transactional.
Scene/unit locks prevent two browser actions from authorising the same work. Webhook and
poll responses update the same job idempotently.

### 4. Expanded sealed envelope

Retain the existing sealed-envelope strength and add:

- Generation unit and script-version signatures.
- Provider capability snapshot/hash.
- Request schema and provider parameters.
- Full SHA-256 reference/audio manifest.
- `generate_audio`, watermark and safety settings.
- Price source, quote timestamp, currency and billing unit.
- Idempotency key and provider request ID after submission.
- Expected output and retention policy.

### 5. Delivery profiles

Move format and loudness decisions into versioned delivery profiles, for example:

- `review_720p`
- `youtube_2160p_sdr`
- `youtube_vertical_1080x1920`
- `archive_2160p_pcm`
- `broadcast_ebu` only when the actual broadcaster spec is attached

Each profile should define dimensions, frame-rate policy, codec, pixel format, colour,
audio codec/sample rate/bit depth/channels, bitrate or quality policy, captions and
loudness/QC rules.

## Migration and qualification plan

### Phase 0: no-spend architecture work

- Add typed `GenerationUnit`, provider capabilities and model registry.
- Wrap the current fal 2.0 route behind the new interface with byte-for-byte equivalent
  sealed requests.
- Add durable provider jobs, scene/unit locking and idempotency tests.
- Upgrade media probe and delivery profiles.
- Keep all existing 2.0 tests green.

Exit: current production behavior works through the adapter with no provider call in tests.

### Phase 1: 2.5 zero-spend capability gate

Only when a provider publishes 2.5:

- Record exact model ID, endpoint and schema from official documentation.
- Query model availability and price for Julian's account without generating media where
  the provider supports that.
- Validate accepted duration, reference, audio, resolution and watermark fields.
- Attach current terms and regional availability to the model-registry entry.
- Add mocked contract tests from the real schema.

Exit: the provider adapter can validate and quote an exact sealed request. Paid submission
remains disabled.

### Phase 2: explicitly authorised technical smoke test

Use one non-production test unit and one candidate at the lowest useful resolution/duration.
Verify:

- Submission and recovery after client restart.
- Real price against the quote.
- Output duration, resolution, fps, codec, colour, audio and watermark.
- Reference slot ordering and exact start-frame use.
- Cancellation and error behavior where safely testable.
- Immediate ingest and manifest preservation.

Exit: no duplicate charge, complete evidence, predictable provider lifecycle.

### Phase 3: creative A/B qualification

Use three locked, representative Crystal Bears scenes with a fixed maximum budget:

1. A 10-15 second simple performance/reaction scene.
2. An 18-24 second dialogue and emotional-turn scene.
3. A 24-29 second multi-shot physical-comedy scene.

Compare:

- 2.5 scene/unit render.
- Existing 2.0 approved-shot-and-stitch route.
- Split 2.5 units when the full scene is too complex.

Measure approved-result cost and time, not just first-output cost. Score all ten review
criteria, script occurrence accuracy, continuity defects, local-repair usefulness, render
latency and post labour.

Exit: 2.5 must improve the accepted scene, total cost or production time without weakening
script truth, identity, approval lineage or final delivery.

### Phase 4: controlled production rollout

- 2.5 remains opt-in per scene at first.
- 2.0 remains the immediate fallback.
- Store provider choice in each immutable generation-unit approval.
- Review the first five accepted scenes as a calibration batch.
- Promote 2.5 to default only for scene classes where evidence shows it wins.

## Readiness checklist

Seedance 2.5 may be enabled only when every item is true:

- [ ] Official provider endpoint and exact model ID exist.
- [ ] Account and region access are confirmed.
- [ ] Request/response schema is captured in tests.
- [ ] Price and successful-output billing behavior are confirmed.
- [ ] Billing profile and spend ceiling are approved.
- [ ] Terms and production rights have been reviewed.
- [ ] Duration, reference and audio limits are verified.
- [ ] Output codec, fps, colour, audio and watermark behavior are verified.
- [ ] Provider job IDs survive process/browser restart.
- [ ] Submission is idempotent and transactionally spend-reserved.
- [ ] Source output is immediately downloaded, hashed and preserved.
- [ ] Script occurrence and continuity checks work at scene/unit level.
- [ ] Human candidate review and final-master gates cannot be bypassed.
- [ ] 2.0 fallback remains operational.
- [ ] Golden-path test runs from a fresh script to an approved final-master candidate.

## Immediate implementation order

1. Add the provider capability/model registry without changing live behavior.
2. Wrap the existing fal 2.0 call and sealed envelope through it.
3. Add `GenerationUnit` above the existing shot objects.
4. Build one authoritative scene audio guide and reference manifest.
5. Add durable asynchronous provider jobs, idempotency and transactional spend reservation.
6. Upgrade technical ingest/QC and 48 kHz delivery profiles.
7. Add the disabled 2.5 adapter only after an official schema exists.
8. Run the qualification plan with explicit spend authorisation.

## Source register

Primary product and API sources:

- [Dreamina: Seedance 2.5](https://dreamina.capcut.com/seedance/seedance-2-5)
- [Dreamina: Seedance 2.5 vs 2.0](https://dreamina.capcut.com/seedance/seedance-2-5-vs-seedance-2-0)
- [Dreamina: release and availability](https://dreamina.capcut.com/seedance/seedance-2-5-release-date)
- [Dreamina: Seedance 2.5 usage guide](https://dreamina.capcut.com/seedance/how-to-use-seedance-2-5)
- [BytePlus ModelArk: Seedance video-generation tasks](https://docs.byteplus.com/en/docs/modelark/1520757)
- [BytePlus ModelArk pricing](https://docs.byteplus.com/docs/ModelArk/1099320)
- [fal: current Seedance 2.5 status](https://fal.ai/learn/tools/what-is-seedance-2-5)
- [fal: Seedance 2.0 reference-to-video](https://fal.ai/models/bytedance/seedance-2.0/reference-to-video/api)
- [fal: Seedance 2.0 production guide](https://fal.ai/learn/tools/how-to-use-seedance-2-0)
- [fal: asynchronous inference](https://fal.ai/docs/documentation/model-apis/inference/queue)
- [fal: webhook security and retries](https://fal.ai/docs/documentation/model-apis/inference/webhooks)
- [fal: pricing behavior](https://fal.ai/docs/documentation/model-apis/pricing)

Rights and delivery sources:

- [Dreamina Terms of Service](https://dreamina.capcut.com/clause/dreamina-terms-of-service?lang=en&store_region=US)
- [Dreamina User Safety Guide](https://dreamina.capcut.com/clause/dreamina-user-safety-guide)
- [Dreamina Community Guidelines](https://dreamina.capcut.com/clause/dreamina-community-guidelines)
- [YouTube recommended upload encoding settings](https://support.google.com/youtube/answer/1722171)
- [EBU R128 loudness recommendation](https://tech.ebu.ch/docs/r/r128v4_0.pdf)

Provider pages and terms can change. Re-check the model registry and delivery profile
against these sources immediately before activation or distribution.
