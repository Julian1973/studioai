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

Use **Character states** to upload and review a variant. Bind it to a character and,
when appropriate, an episode and scene numbers. Only approved states matching that
scope can enter a shot. Revisions retain prior files and versions. Adding an unrelated
state does not reset existing shots. Changing a used reference requires the existing
source-update flow for affected unfinished work.

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
`engine/test_studio_production.py` and `cb-studio/test_project_agent_api.py`.

Run `node cb-studio/project_review_browser.mjs` with Playwright available on NODE_PATH.
It starts a temporary project/server and drives the actual UI, HTTP handlers and SQLite
ledger. Providers are synthetic; ffmpeg creates real test media. The test covers the
board, approvals, edit preview/apply, retained voice, visible gaps, review notes, joins,
episode sign-off, downloadable handoff, continuous playback, stable polling and mobile
layout. No production assets, account keys or paid generations are used.

Artistic performance, model account access and final delivery quality require a real
production trial and human viewing. Passing software tests does not establish them.
