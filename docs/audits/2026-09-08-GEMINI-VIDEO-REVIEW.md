# Gemini video review integration

The project production workflow can now submit actual shot videos and audio to Gemini, and keep timestamped findings with the exact render. The installed `video-analysis` skill supplies the runtime review contract. This is advisory review, not generation or approval.

## Implemented

- Google Gemini is an optional workspace connection restricted to the review role. Keys use the existing OS credential vault; queued jobs pin a connection revision. No environment-key fallback, connection migration or account switching.
- Project services select the Gemini model, review detail (1, 4 or 8 FPS; default 4) and an estimated allowance per review. One existing episode budget covers the optional review. Token usage is retained when returned; committed amounts remain estimates, not provider invoice totals.
- The same `media_review` command serves chat and buttons. The submitted sources are the current WATCH file including its audio, the supplied previous approved WATCH, approved HEAR, SEE and selected canon references. Source files and hashes are checked before submission and after analysis.
- The official Files API handles uploads; Interactions uses static video processing, structured output, `store=false`, and a 6,000 output-token ceiling. No inference POST retries. Bounded processing waits, completed-status validation and timestamp bounds reject incomplete reports.
- Temporary uploaded files are deleted in `finally`. File IDs and deletion state are saved privately in the job. Failed deletion is visible and can be retried without repeating analysis. A lost upload response is explicitly unconfirmed and cannot be claimed deleted. Interrupted jobs can be closed through existing recovery, then their known uploads cleaned up.
- Current reports and their evidence reach the Resolve export brief. Earlier reports are identified separately. “Add to my direction” creates an editable draft and does not apply a suggestion or change an approval.
- A video review can follow an existing sampled-frame review without destroying it. Matching completed reviews are not submitted again accidentally.
- The skill is versioned at `skills/video-analysis/SKILL.md` and discoverable locally through `~/.codex/skills/video-analysis`. Its standalone mode also supports user-specified videos outside Studio through Google's SDK.

## Scope and limitations

The Studio adapter currently accepts valid shot/voice sources up to 35 seconds and 512 MB each, using the production engine's MP4, WAV and common image formats. These are application limits. The standalone skill documents longer-file preparation and segmentation. Whole-episode Gemini review and agentic video search are not exposed in this Studio adapter.

Submitting a full file does not mean examining every frame. The report discloses its configured sampling rate; short glitches, lip sync and exact edit boundaries need local verification. Artistic success and broadcast readiness still require human review.

This connects the project-based production ledger. Existing legacy Crystal Bears production remains in its own ledger; this change does not migrate it or add a Gemini dispatch path to legacy WATCH endpoints. No production approval, render, source file, API key or live service selection was changed during implementation.

## Verification

- 206 regression tests passed across production, media review, handoffs, project setup, local authentication and director UI. The final targeted Gemini suite passed 16 tests after adding queued-source and silent-video cases.
- Fake Google HTTP tests exercise real synthetic media bytes, structured payloads, cleanup success/failure, unknown submission, processing failure/timeouts, blocked foreign upload destinations, original credential revision, project isolation, source integrity, timestamps and optional-review budgets.
- The browser workflow exercises service switching, conditional audio/video controls, upgrading a sampled review, the saved report, direction from a finding and cleanup recovery, alongside SEE → HEAR → request → WATCH, assembly, draft recovery and mobile navigation.
- Skill validation passed. No production footage was uploaded and no paid inference was run. The live workspace currently has no Gemini review connection, so account/model access and real model review quality remain unverified.

## API references checked during implementation

- https://ai.google.dev/gemini-api/docs/video-understanding
- https://ai.google.dev/gemini-api/docs/files
- https://ai.google.dev/gemini-api/docs/structured-output
- https://ai.google.dev/gemini-api/docs/interactions-overview
- https://ai.google.dev/api/interactions-api
