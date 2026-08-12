# Crystal Bears Studio Frontend Capability Audit

Date: 2026-08-12  
Scope: phase 1 frontend consolidation audit only. No app/director merge decisions are implemented here.

## Removed In This Pass

- `cb-studio/fable.html` deleted.
- Reason: superseded by `room.html`, not present in `_APPROVED_FILES`, and not reachable through the Studio launch allowlist.
- Dead reference check: no remaining code references to `fable.html` outside the deleted file.

## Surface Summary

| Surface | Role Today | Static Entry Status |
|---|---|---|
| `cb-studio/app.html` | Legacy broad production console: projects, creative intake, storyboard, department tools, detailed shot pipeline, legacy library views, prompt lab, post/master tools. | Approved exact static file. |
| `cb-studio/director.html` + `director.js` | Current outcome-first Studio: scenes, asset library, SEE/HEAR/WATCH sign-off, prompt/reference inspection, status/comms, rough-cut queue, Studio agent. | Approved exact static file. |
| `cb-studio/room.html` | Conversational room assistant. | Approved exact static file. Not part of this app/director capability matrix. |

## Capability Matrix

| Capability | Status | `app.html` API Routes | `director.html` / `director.js` API Routes | Notes |
|---|---|---|---|---|
| Studio launch and authenticated static entry | PRESENT-IN-BOTH | static `/cb-studio/app.html` | static `/cb-studio/director.html`, `/api/studio-version` | Both are launchable approved files, but Director has stale-build detection. |
| Project list / project creation / project rename | ONLY-IN-APP | `/api/projects`, `/api/project`, `/api/episode`, `/api/episode-rename` | none observed | Director is fixed to Crystal Bears current project. |
| Episode script/story intake run and approval | ONLY-IN-APP | `/api/story-intake-status`, `/api/story-intake-run`, `/api/story-intake-decide`, `/api/write` | none directly; Director can surface `direct-scene` via `/api/director-action` after session state | App owns the broad intake workflow. |
| Canon lock status and canon readiness | ONLY-IN-APP | `/api/canon-lock` | surfaced indirectly by `/api/director-session` | Director does not expose full canon-lock management. |
| Scene roster and scene navigation | PRESENT-IN-BOTH | `/api/scene-roster`, `/api/storyboard` | `/api/scene-roster`, `/api/director-session`, `/api/director-board` | Director gives a simplified scene board and next-decision routing. |
| Storyboard / Story & Direction review | PRESENT-IN-BOTH | `/api/storyboard`, `/api/storyboard-approve`, `/api/creative-run`, `/api/shot-package` | `/api/director-session`, `/api/director-action` (`direct-scene`) | App has broader legacy controls; Director has outcome-first sign-off projection. |
| Department specialist prepare/save/decide | ONLY-IN-APP | `/api/departments`, `/api/department-run`, `/api/department-save`, `/api/department-decide` | none directly | Director consumes prepared state but does not expose full department editor controls. |
| Scene Look generation/upload/library selection | PRESENT-IN-BOTH | `/api/scenelook`, `/api/scenelook-upload`, `/api/loclib`, `/api/houses` | `/api/scenelook-library`, `/api/scenelook-upload`, `/api/scenelook-select-source`, `/api/director-action` (`build-scene-plate`, `select-scene-plate-library`, `select-scene-plate-upload`) | Director now has the production picker path covered by Golden Path. |
| Asset library: characters/scenes/props browse | PRESENT-IN-BOTH | `/api/character`, `/api/loclib`, `/api/houses`, `/api/scene-ref` | `/api/project-asset-library` | App uses several legacy domain libraries; Director uses the central asset registry projection. |
| Asset library: add/edit/delete/upload/copy reference | ONLY-IN-DIRECTOR | limited legacy add endpoints: `/api/character`, `/api/scene-ref` | `/api/asset-library-upload`, `/api/asset-library-update`, `/api/asset-library-delete`, `/api/project-asset-library` | Director has the newer unified Asset Library UI. |
| Shot selection and per-shot pipeline navigation | PRESENT-IN-BOTH | `/api/production-state`, `/api/shot-package`, `/api/shot-run` | `/api/director-session`, `/api/director-action` | App exposes granular stage pages; Director exposes current decision and shot switcher. |
| Keyframe generation, upload, library reuse, approval/refire | PRESENT-IN-BOTH | `/api/shot-keyframe-upload`, `/api/shot-keyframe-library`, `/api/shot-run` | `/api/shot-keyframe-upload`, `/api/shot-keyframe-library`, `/api/director-action` | Director has SEE sign-off plus enlarged keyframe preview. |
| Keyframe identity/structure checks | ONLY-IN-APP | `/api/shot-check-structure`, `/api/shot-readback`, `/api/shot-reassess`, `/api/prompt-lab` | conformance shown through `/api/director-session` inspector when available | App has direct free-check buttons and prompt lab. |
| Voice direction editing and ElevenLabs performance workflow | PRESENT-IN-BOTH | `/api/shot-voice-status`, `/api/shot-voice-save`, `/api/shot-voice-restore`, `/api/shot-voice-restore-take`, `/api/shot-run` | `/api/shot-voice-status`, `/api/shot-voice-save`, `/api/shot-voice-restore`, `/api/shot-voice-select-audition`, `/api/director-action` | Director has HEAR sign-off and audition selection; App has legacy restore-take path. |
| Animation prompt compile, spend approval, render, candidates, accept/refire | PRESENT-IN-BOTH | `/api/shot-run`, `/api/shot-seedance-status`, `/api/shot-seedance-save`, `/api/shot-seedance-restore`, `/api/production-preflight` | `/api/director-session`, `/api/director-action`, `/api/jobs` | Director has WATCH sign-off and visible status/comms. |
| Exact request / prompt inspection and copy | PRESENT-IN-BOTH | prompt/request sheets in app workspace; `/api/shot-references`, `/api/shot-package` | `/api/director-session`, `/api/shot-references` | Director exposes Exact Prompt and Copy button beside WATCH inputs. |
| Reference pack inspection for keyframe and animation | PRESENT-IN-BOTH | `/api/shot-references` | `/api/shot-references` | Both can show references; Director has dedicated modal and inline references. |
| Provider jobs/status polling and stop controls | PRESENT-IN-BOTH | `/api/jobs`, `/api/stop` | `/api/jobs` | App has explicit stop route; Director focuses on current job state. |
| Prompt lab / rating / learning feedback | ONLY-IN-APP | `/api/prompt-lab`, `/api/prompt-lab-rate`, `/api/shot-reassess` | none observed | Not safe to retire app until this is either ported or deliberately removed. |
| Rough cut queue and shot add/remove | ONLY-IN-DIRECTOR | post/master controls through `/api/shot-run` (`stitch`) | `/api/rough-cut-draft` | Director has explicit rough-cut queue UI. |
| Post/master build and final review | PRESENT-IN-BOTH | `/api/shot-run` (`stitch`), department final review routes | `/api/rough-cut-draft`, `/api/director-session`, `/api/director-action` for final states when projected | App remains more explicit for final/post operations. |
| Studio Agent guidance | PRESENT-IN-BOTH | `/api/studio-agent` | `/api/studio-agent` | Director places it in the live workspace. |
| Mobile navigation | ONLY-IN-DIRECTOR | none explicit | Director mobile nav in `director.html` | Covered by Golden Path. |
| Stale build detection / stale-tab blocking | ONLY-IN-DIRECTOR | none observed | `/api/studio-version` | Covered by Golden Path. |

## API Route Inventory

### `app.html`

Observed direct `/api` calls:

- `/api/canon-lock`
- `/api/character`
- `/api/creative-run`
- `/api/department-decide`
- `/api/department-run`
- `/api/department-save`
- `/api/departments`
- `/api/episode`
- `/api/episode-rename`
- `/api/houses`
- `/api/jobs`
- `/api/loclib`
- `/api/masters`
- `/api/production-preflight`
- `/api/production-state`
- `/api/project`
- `/api/projects`
- `/api/prompt-lab`
- `/api/prompt-lab-rate`
- `/api/rates`
- `/api/scene-ref`
- `/api/scene-roster`
- `/api/scene-shot`
- `/api/scenelook`
- `/api/scenelook-upload`
- `/api/shot-check-structure`
- `/api/shot-keyframe-library`
- `/api/shot-keyframe-upload`
- `/api/shot-package`
- `/api/shot-readback`
- `/api/shot-reassess`
- `/api/shot-references`
- `/api/shot-run`
- `/api/shot-seedance-restore`
- `/api/shot-seedance-save`
- `/api/shot-seedance-status`
- `/api/shot-voice-restore`
- `/api/shot-voice-restore-take`
- `/api/shot-voice-save`
- `/api/shot-voice-status`
- `/api/stop`
- `/api/story-intake-decide`
- `/api/story-intake-run`
- `/api/story-intake-status`
- `/api/storyboard`
- `/api/storyboard-approve`
- `/api/studio-agent`
- `/api/write`

### `director.html` / `director.js`

Observed direct `/api` calls:

- `/api/asset-library-delete`
- `/api/asset-library-update`
- `/api/asset-library-upload`
- `/api/director-action`
- `/api/director-board`
- `/api/director-session`
- `/api/jobs`
- `/api/project-asset-library`
- `/api/project-workbench-state`
- `/api/rough-cut-draft`
- `/api/scene-roster`
- `/api/scenelook-library`
- `/api/scenelook-select-source`
- `/api/scenelook-upload`
- `/api/shot-keyframe-library`
- `/api/shot-keyframe-upload`
- `/api/shot-references`
- `/api/shot-voice-restore`
- `/api/shot-voice-save`
- `/api/shot-voice-select-audition`
- `/api/shot-voice-status`
- `/api/studio-agent`
- `/api/studio-version`

## Retirement Recommendation

Retire `app.html` eventually, but not in phase 1.

Reason: `director.html` is the better surviving surface for Julian's actual production workflow: it has the SEE/HEAR/WATCH relay, clearer sign-off state, the newer Asset Library, stale-build protection, next-decision routing, status/comms, and Golden Path coverage.

What would be lost if `app.html` were deleted today:

- Full project and episode management.
- Story/script intake controls.
- Canon-lock management visibility.
- Department specialist editing/save/decide surfaces.
- Prompt Lab, ratings, reassess/readback controls, and learning-feedback tools.
- Some explicit post/master controls and stop controls.
- Legacy scene/house/location library flows that are not yet proven equivalent in Director.

Therefore phase 2 must not delete `app.html` until each `ONLY-IN-APP` capability is either ported to `director.html`/`room.html`, explicitly retired by product decision, and covered by Golden Path or an equivalent browser gate.

## Phase 2 Rule

No capability may be deleted until it is confirmed present in the surviving surface and the Golden Path covers it.
