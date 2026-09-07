# Projects landing and guided setup

7 September 2026. Platform work only; existing Crystal Bears assets, scripts, approvals and renders were not edited.

## Delivered

- Bare Studio launches and the Studio home button open Projects. Explicit episode/shot links still restore their context.
- Projects cards and Add project entry points use project language.
- Eight-step setup: identity and series/film format, look, show bible, characters, locations/scene plates, props, voice/audio and review.
- Character fields include identifying/personality notes, proportions, voice ID/casting notes and a reference image. Locations and props carry their own reference images and notes. The bible supports pasted text or TXT/Markdown import.
- Save and finish later persists the walkthrough, including attached images, in browser IndexedDB on this computer. Resume was verified across reload. No test project was created in the live registry; the preview draft was returned to blank step one.
- Creation stores separate project-local bible, character/location/prop collections, assets, media and episode/script directories. Records remain draft; missing supplied-reference images and bible are disclosed rather than silently approved.
- Newly created projects open their own library and episode/film-sequence script workspace, avoiding legacy Crystal Bears library endpoints. New scripts are stored only in the named project.

## Verified

124 tests passed, including HTTP project creation in temporary directories, duplicate-name project separation, asset/bible isolation, per-project script storage, invalid scope rejection and existing authentication/UI checks. JavaScript syntax passes. Source audit: 159 Python files and 50 documents; no issues.

Live Projects and every walkthrough step were inspected. Save/resume survived reload. Service reports stale=false, running=0. Live registry remains crystal-bears and ep1-v2-archive only. The final Studio home-button navigation change was syntax checked and verified by its direct binding to bootProjects.

## Boundary

This is project onboarding and isolated asset/script storage, not completed multi-IP production execution. New-IP generation is explicitly marked unconnected in the workspace. No paid provider calls were made. Canon approval/editing after setup, automatic folder classification, and generalizing the existing episode/render engine remain separate work; this change does not claim those are complete.
