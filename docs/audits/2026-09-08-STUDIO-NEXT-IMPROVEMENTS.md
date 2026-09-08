# Studio workflow improvements — 8 September 2026

Implemented for the project-agnostic workspace. Existing production episodes and
credentials were not migrated, regenerated or edited during this work.

## Delivered

- Approved reference suggestions by scene/location, matching camera setup and scene
  anchor. Choices show their purpose and enter the existing preview/apply/undo path.
  Candidate IDs and hashes reach SEE generation inputs. Stale choices cannot enter a
  new generation. Previously approved downstream footage remains usable when a source
  gets a newer version.
- Local drafts for script/title, shot direction, candidate notes, timeline notes and
  library/state text. Project/episode/shot scope, independent browser writers, reload
  recovery and protection for text edited during submission. Passwords, file inputs
  and approval checkboxes are excluded; storage failures are visible.
- Persisted observed job phases, provider-reported state, checked assembly clip counts,
  and saved download/conform/extraction progress. No elapsed-time completion percentage.
- Optional actual-media review through an explicitly selected project review connection.
  Timestamped render samples, preceding-cut samples, approved references and extracted
  audio are sent to the configured visual/audio models. Reports expose evidence,
  confidence and limitations and are bound to source versions. Findings can be added
  to an unsent direction draft. No automatic approval, prompt change or retake.
- Review estimates use the episode allowance. Incomplete optional reviews preserve
  returned audio evidence, settle submitted estimates conservatively and allow normal
  production to continue. Resume never repeats a review model POST.

## Verified

- Full Python suite: **1,163 passed, 4 skipped**, exit 0.
- Expanded project browser flow: script/shot draft reload, independent tabs, typing
  during submission, explicit directing scope, reference preview/application, media
  report and draft from a finding; existing SEE/HEAR/request/WATCH, edits, joins,
  assembly sign-off, handoff downloads, state uploads, desktop and mobile all passed.
- Legacy browser checks passed, including provider refusal recovery, stale-tab
  protection, scene/shot navigation and stable image/audio playback across polling.
- Live authenticated local server returned HTTP 200 for the app, new draft/review
  modules and workspace provider metadata. Review role was present; health reported
  `stale: false`.
- JavaScript syntax checks and Git whitespace checks passed.

Verification used isolated fixtures, fake providers, real SQLite transactions and
real image/audio/video processing. No paid model request, API-key write, production
render, migration, remote push or broadcast delivery was performed.

## Boundaries

Review must be configured in Project services with a vision model supporting structured
output, an audio-input Chat Completions model and a combined estimate. Real account
permission and artistic usefulness need a production trial. The reviewer samples frames;
it does not continuously watch video or certify frame-accurate lip sync/broadcast quality.
Browser drafts are local convenience storage, not cross-device backup. Ordinary supplied
library references still carry their approval warnings; selected character states and
additional camera/scene references must be approved.

Operational guide: [Director workspace](../DIRECTOR_WORKSPACE.md).
