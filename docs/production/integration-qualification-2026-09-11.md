# Production workflow integration — 11 September 2026

The implemented changes make the reviewed shot plan the source of final WATCH
text and preserve its originating evidence through returned-media review. They
also repair WATCH preparation recovery and project HEAR timing handoff. This is
software qualification; it does not certify live model judgement, image identity
recognition, cinematic quality, or a finished episode.

## Changes

- Final WATCH compilation reads typed camera, action, acting, timing and landing
  fields. Historical visual prompt prose cannot override those fields. Prompt
  Director reviews the plan, makes source-bound request-local corrections,
  recompiles, and reviews the exact resulting provider payload.
- Native and project routes preserve measured dialogue occurrences, speaker,
  timing and the existing Audio1 block. Segmented clips keep explicit local
  clocks and the unchanged parent shot/audio records. Unsupported ambiguous
  splits require a real plan change; they are not silently trimmed.
- Reference aliases resolve against registered identities. A real S2 check
  exposed `char:aida` versus `Aida` producing a false no-character instruction;
  the shared resolver now handles those aliases without treating props as cast.
- Immutable requests separate creative truth from execution/audit metadata.
  Returned-media review binds to original references, opening, audio and plan,
  including supplied identity references. Changed or malformed origin evidence
  remains an explicit incident rather than inheriting newer shot data.
- WATCH preparation has durable operations, checkpoints, bounded retries,
  duplicate suppression and visible CLI/browser progress. New authored changes
  and retired cost decisions create linked preparation lifecycles. Uncertain
  submissions cannot replay or inherit an older batch's returned media.
- Existing approved assets, scene packages, model settings, 9.5 score floor and
  producer approval powers are preserved.

## Evidence

The integrated suite passed **613 tests** across 38 selected modules. The optional
MCP protocol module was then run in the existing `.venv-mcp` runtime: **4 passed**.
Total: **617 passing checks**, with the one initial runtime-related collection
skip resolved. External networking and the live Studio port were forbidden in
the test harness. HTTP tests used disposable loopback servers and fake APIs.

The tested paths include native and project production, source/approval
invalidation, exact provider payload sealing, recovery/concurrency, returned
media origin checks, post/export and MCP authorization/idempotency. The existing
end-to-end production test reaches a mocked approved master. No paid calls,
new render, human creative approval or live DaVinci operation is implied.

Read-only compilation of current Ep3 S2.SH1 retained five views over 16 seconds,
the current opening/Aida/pool/Sunny-vision references, and Aida's exact approved
line at 11.8–15.2 seconds. The audio SHA-256 stayed
`d6c576a5b60b71da2ae94e5ae2b472121aeadc09767f2d1b32794d86c9074f25`.
The resulting prompt contains 1,245 words and passed compiler checks. This is
not a semantic Prompt Director approval or a new request ready for paid Fire.

Run evidence is stored in `/private/tmp/studio-integration-20260911/`, including
`qualification/full.xml`, `qualification/mcp.xml`, the S2 compilation record,
the installation manifest and installation receipt.

## Explicit remaining boundary

The Final Show Bible and existing creative playbooks are selected, hashed and
scoped locally. **New source-excerpt forwarding to the OpenAI Director is not
enabled.** Automatic approval review requires the user's specific consent for
those passages and `api.openai.com`. The proposed connection remains an inert
patch pending that consent; existing Director inputs continue unchanged.
See [source selection and pending connection](creative-source-integration-2026-09-11.md).

Recovery currently covers WATCH preparation/retakes and local submission
reconciliation. It does not implement universal runtime code repair, automated
scene-completion incident synthesis or provider retrieval after a dead worker.
See [recovery boundaries](production-recovery-coordinator-implementation-2026-09-11.md)
and [compiler authority](watch-plan-authority-2026-09-11.md).
