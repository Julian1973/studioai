# Project production agent

Implemented 8 September 2026. The project agent turns a saved screenplay into shot
records, then prepares SEE, HEAR and WATCH outcomes. Chat and buttons call the same
`POST /api/project-command` dispatcher. Model output cannot approve work, select a
different account, increase the allowance, execute code or create an independent job trail.

## Using the project workspace

1. Create a project with its own bible and character, location and prop references.
2. Open **Connections** on the Projects screen. Save provider keys in the OS credential
   store and use the read-only connection check. No generation is needed for this check.
3. In the project, choose **Project services**. Assign direction, keyframes, voices and
   animation to workspace connections, select models and enter conservative per-request
   estimates from the provider account. Voice casting accepts one `Character = Voice ID`
   per line. A project can connect services incrementally.
4. Paste or import an episode/sequence script (text, Fountain, DOCX, PDF or RTF). Approve its total USD allowance once. Direction
   prepares the shot records and then the first SEE candidate when its service is ready.
5. Review SEE. Approval prepares HEAR, or the WATCH request for a silent shot. HEAR
   approval prepares a request showing its prompt, source text, references, duration,
   account/model revision and estimate. Approving that request submits one render.
6. Review the returned WATCH candidate. Its approval prepares the next shot. Rejection
   retains the candidate and its review note; the agent can revise the selected shot.

Use **Edit project library** to add or revise references and bible text. Files get new
names; prior metadata and bible versions are retained. A source update shows its effect
before continuing. Refreshing sources rebuilds affected unfinished pictures, retaining
unaffected shots, finished renders and approved speech. Screenplay revisions need their
own episode/sequence version because the exact source line coverage and dialogue are
protected. No production records are silently migrated.

The original production desk remains the compatibility path for existing projects that
predate project onboarding. Its current records and approvals are not copied into the new
ledger. Explicit foreign project IDs are refused by legacy shot/director mutation routes.
The new BYOK selections are consumed by the project workspace engine; they do not silently
override legacy environment credentials. Migrating an established project requires a
separate, reviewed adapter for its existing production records.

## Creative handoff and review

`skills/project-production-standard.md` is the runtime creative standard, snapshotted and
hashed into every job. The director receives only the selected project's bible, source
lines, asset descriptions, available reference images and recent human review evidence.
It returns typed shot records with emotion, performance, camera, geography, transition,
exact source coverage, dialogue/delivery cues and matching SEE/WATCH prompts.

The compiler includes these fields and named reference roles in actual generation inputs.
The plan must cover every script line exactly once, in order. Unknown cast/assets and
invented dialogue are rejected before publication to the pipeline. Visual changes retain
approved voice. Voice-delivery changes retain picture and require a new HEAR approval.
Other shots are preserved; subsequent joins in the same scene get a continuity review note.
Review evidence is project-local and can inform later episodes; it never becomes an
automatic artistic veto or another project's canon.

A planned cut gets a new opening composition. The previous approved ending is a state
reference, displayed beside the new SEE candidate. A continuation requires an approved
preceding ending. Final-frame extraction is checked before that image can become a handoff.

WATCH uses HEAR as an audio reference and conforms the exact approved speech into the
review movie. The original provider movie remains available in the retained files. Its
native music/effects are not part of the speech-conformed review track. Lip sync, emotional
delivery and the final sound mix still require media review; software tests cannot qualify
artistic or broadcast quality.

## State, credentials and recovery

- `engine/studio_workspace.py`: strict project paths, library versions, provider metadata,
  service choices and native keyring access. No `.env` fallback for new project work.
- `engine/studio_production.py`: shared commands, typed plans, hashes, budgets, reviews,
  job reservations, media handoff, scoped revisions and automatic next-outcome preparation.
- `engine/studio_transport.py`: explicit-credential OpenAI, ModelArk and ElevenLabs
  adapters. Generation POSTs are never retried automatically. Downloads send no keys;
  HTTPS certificates are checked and connections pin a validated public IP.
- `cb-studio/project-production.js` and `.css`: workspace connection/library/service
  editors, selection-aware chat, review controls, persistent shot selection and job recovery.

Workspace metadata and jobs live in an owner-only SQLite database below
`~/.local/share/studioai/<workspace-digest>/`, outside the served checkout. Keys live only
in a supported native credential store (macOS Keychain, Windows Credential Locker or
Secret Service); an insecure fallback is refused. This is a local workspace design,
not a hosted multi-tenant authentication or secret-management system.

Jobs pin connection ID, credential revision, model, source/standard hashes, inputs and
estimated cost. Replacing a key affects new work; existing tasks retain the original
credential revision for recovery. Disabling a connection prevents new work.

Command IDs deduplicate submissions; optimistic revisions prevent stale approvals.
Reservations and command/state writes use SQLite transactions. Budgets count configured
estimates, including uncertain requests. They are not a guarantee of the provider's
invoice total. Known task IDs and returned image URLs survive restart and can be resumed
without another generation POST. If submission was not confirmed, the agent stops and
asks for account reconciliation; closing that request retains its estimated cost.

## Supported adapters and limits

- OpenAI Responses with strict structured output and no SDK retries, using the project's
  selected model. Planning is bounded to 120 shots, 200,000 serialized context characters,
  and 16,000 output tokens per request; long scripts may need production sequences.
- ModelArk Seedream image endpoint: one 2K candidate, up to ten reference images.
- ElevenLabs v3 text-to-dialogue: exact words and project casting, with bounded delivery cues.
- ModelArk Seedance `dreamina-seedance-2-5-260628`: the existing qualified 480p route,
  4–30 seconds, explicit reference images/audio and asynchronous task recovery.

Model/account access and pricing must be checked for the selected provider region. A
connection check proves read access, not generation permission or artistic performance.
There is no implicit model, account or provider fallback.

The adapters follow [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
[ElevenLabs text-to-dialogue](https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert)
and [ModelArk task queries](https://docs.byteplus.com/en/docs/modelark/1521675).

## Verification

Run `PYTHONPATH=engine:cb-studio python3 -m pytest -q` for the suite. The focused project
tests are `engine/test_studio_production.py` and `cb-studio/test_project_agent_api.py`.
They exercise real transactions, file hashes, scope checks and ffmpeg conform/extraction
with fake providers; external network calls are blocked by the test configuration.
The existing `cb-studio/golden_path_browser.mjs` checks legacy production UI regressions.
Live account authorization, provider generation and human assessment of actual creative
results remain separate from this software verification.
