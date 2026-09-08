# Director workspace

The project workspace has three views over the same production ledger: **Episode
board**, **Shot workspace** and **Review episode**. The agent and buttons use the
same commands. A view or percentage never grants approval.

## Start and direct

Create a project, supply its bible and references, choose its services and save a
script. Approve the episode allowance once. The director prepares the plan and the
first SEE outcome. Review SEE, HEAR, the WATCH request and the returned WATCH in
that order. Silent shots skip HEAR. Approving WATCH prepares the next shot.

The board groups thumbnails by scene. It distinguishes preparing, ready for review,
approved, missing and needs attention. Approved running time uses measured, verified
video; generated footage and planned duration are separate. Remaining estimates use
configured service costs and exclude speculative retakes. These are estimates, not
provider invoice totals.

Select a shot to see its outcomes, dialogue, prompts, reference roles and direction.
The director's shot record carries intention, emotion, camera, geography, opening and
ending state, timed performance beats and identity claims into actual generation
inputs. SEE describes one instant; WATCH carries the performance over time.

## Change a shot

Give direction in chat or choose a character state. A proposed change shows the
changed fields and affected outcomes. **Apply & prepare** uses the proposed direction
and existing allowance to prepare its next outcome. **Keep current version** discards
the proposal. **Undo last direction edit** restores the prior direction and its
recorded outcomes while retaining spending, jobs and generated versions.

Visual changes preserve approved voice. Voice-only changes preserve picture.
Other shots keep their files; incoming and outgoing joins are flagged where relevant.
A proposal is bound to current direction, sources and outcome versions. It cannot
silently overwrite an approval made after the proposal was prepared.

## References and character states

The inspector distinguishes character identity, location geography, prop continuity,
approved character state, previous ending and opening composition. It shows references
actually used by the selected candidate, including hashes/version identifiers, as well
as missing files and changed dependencies.

In **Edit project library**, add named identity traits such as `species = bear` and
`wings = none`. Director claims conflicting with those recorded values are refused
before media generation. This is a structured consistency check; it does not detect
every contradiction in arbitrary prose or prove visual likeness.

**Suggested camera and scene references** lists verified approved openings from earlier
shots in the same episode, scene and location. Matching camera setup names (or exactly
matching camera direction for older records without a setup name) suggest a reusable
view; the first approved opening offers a geography anchor. Each suggestion explains
what it controls. A reverse uses its own setup name. Preview the selection, then apply
it through the normal direction-change preview. The selected candidate ID and file hash
are carried into SEE inputs and retained in the outcome's actual reference strip.
Changed, missing, unapproved, future-shot and cross-project sources cannot be selected.
Character-state matches are never substituted from a nearby scene.
If an earlier reference gets a newer version after this shot's SEE approval, the
inspector warns and preserves the approved downstream outcomes. A new SEE must select
a currently valid reference; an already approved movie does not become an assembly gap.

Use **Character states** to upload and review a variant. Bind it to a character and,
when appropriate, an episode and scene numbers. Only approved states matching that
scope can enter a shot. Revisions retain prior files and versions. Adding an unrelated
state does not reset existing shots. Changing a used reference requires the existing
source-update flow for affected unfinished work.

## Drafts and job progress

Unsent direction and candidate review notes are recovered on this browser, scoped by
project, episode and shot/candidate. New-episode title/script drafts, library/state text
and timeline notes also recover. Each tab retains its draft copy. Restoring a draft
does not submit it or grant approval; successful submission clears the submitted text
while preserving text typed during the request. Different-version drafts are labelled
for review. Files must be selected again and approval checkboxes are never restored.
API-key-looking text is excluded. A storage failure is shown beside the field. These
are local browser drafts, not cloud backup or cross-device sync.

Jobs show persisted, observed processing steps: provider-reported queue/running state,
download/verification, voice conforming, ending-frame extraction and assembly phases.
Assembly shows the number of clips actually prepared and checked. There is no timer
driving a percentage or invented provider completion estimate. Restart recovery uses
the same recorded task and original connection revision.

## Optional actual-media review

In **Project services**, connect **Review** to your own OpenAI connection. Set a vision
model supporting Responses structured output and an audio-input Chat Completions model.
Enter a combined per-review estimate covering both calls. No model or account is selected
implicitly. The optional shot button **Review footage & audio** (or chat command
`review footage`) reserves that estimate from the existing episode allowance.

The reviewer receives up to twelve timestamped frames from the current WATCH file, up
to two preceding approved frames for the incoming cut, the approved SEE opening, up to
five approved library references, and extracted WATCH/approved HEAR soundtracks. Files
are checked against their saved hashes. The audio adapter receives actual WAV data;
its returned listening report is supplied to the separate visual reviewer. A silent
file remains explicitly identified; a missing stream is not claimed as listened to.
The report exposes its sampled-frame images, audio sources, models, observations,
confidence and limitations. Reference omissions are recorded in its evidence.

Reports bind the exact render, relevant direction, references and incoming shot. Old
reports remain visible but are labelled out of date when these change. A source changed
during analysis makes that report historical. **Add to my direction** adds a finding to
your unsent chat draft; it never changes a prompt, creates a retake or approves WATCH.
A completed report for the same inputs is reused rather than charged again. Lost
provider responses are not automatically resubmitted. Failed optional reviews retain
their submitted estimate as committed spending and let production continue. Returned
audio reports survive a later visual failure. Resume attaches a fully received report
after a restart without another model call; an interrupted incomplete review closes
without resubmitting. Check the provider before explicitly requesting another review.

This is sampled visual analysis plus listening, not continuous video understanding or
proof of exact lip sync, emotional impact or broadcast compliance. Review account access
and artistic usefulness still require a real production trial. API input contracts:
[OpenAI audio guide](https://developers.openai.com/api/docs/guides/audio) and
[structured output guide](https://developers.openai.com/api/docs/guides/structured-outputs).

## Review an episode

Approved clips appear in script order. Missing or changed footage remains a visible
gap. Each shot opens directly from the timeline. Notes record episode time, source
time, shot and candidate. Notes inform later direction within the same project.

Once every shot has verified approved footage, opening Review episode automatically
prepares a **continuous local preview**. This spends no provider credits. It uses the
first clip's dimensions and a 24 fps review timeline; it does not enhance source
resolution. The preview allows joins to be judged without browser file-loading gaps.

Assembly trims affect picture and its existing audio together. They do not modify
source renders. Changed trims invalidate assembly approval and rebuild the preview.
Mark flagged joins reviewed and address notes before approving the episode assembly.
Approval binds the current clip identities and timings. It is not broadcast release
or delivery certification.

**Create finishing handoff** writes an FCPXML 1.8 timeline and a source manifest with
file hashes, original paths, timing and notes. The XML references the original approved
media and uses a 24 fps interchange sequence with the first approved clip's dimensions;
no footage is upscaled or replaced.
The review movie can also be downloaded. FCPXML 1.8 uses the asset `src` attribute,
following [Apple's format documentation](https://developer.apple.com/documentation/professional-video-applications/media-rep).
Import into the target finishing application's version still needs a compatibility
check; the Studio does not claim a Resolve import or finishing pass has occurred.

## Established projects

On a supported established project's card, **Upgrade workspace** builds a read-only
report of source files and matching approval evidence. Review the report, choose an
unused workspace ID and create the upgraded copy. Original projects, packages and
media remain available.

The copy includes the bible, character references, named locations/props where the
legacy format supplies them, scripts, source packages and recognized local media.
Historical shots are preserved as read-only archives with their source records and
prior media. A render is counted approved only when its recorded approval hash matches
the copied file. Missing or unverified footage stays a gap. Historical dialogue/source
coverage is not reinterpreted as a newly approved production plan.

New episodes in the upgraded copy use the project agent. Review library gaps and choose
services there. Credentials are not copied or taken from legacy environment files.
The migration does not promise arbitrary legacy layouts are automatically understood;
unsupported layouts receive a specific report before any copy is made.

## Verification

Run the full Python suite with `PYTHONPATH=engine:cb-studio python3 -m pytest -q`.
Focused workflow checks are in `engine/test_studio_review.py`,
`engine/test_studio_production.py`, `engine/test_studio_improvements.py` and
`cb-studio/test_project_agent_api.py`.

Run `node cb-studio/project_review_browser.mjs` with Playwright available on NODE_PATH.
It starts a temporary project/server and drives the actual UI, HTTP handlers and SQLite
ledger. Providers are synthetic; ffmpeg creates real test media. The test covers the
board, approvals, edit preview/apply, retained voice, visible gaps, review notes, joins,
episode sign-off, downloadable handoff, continuous playback, stable polling and mobile
layout. No production assets, account keys or paid generations are used.

Artistic performance, model account access and final delivery quality require a real
production trial and human viewing. Passing software tests does not establish them.
