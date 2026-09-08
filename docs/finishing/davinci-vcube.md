# Legacy Crystal Bears finishing in AI Studio

This page documents the existing episode-only finishing desk. New projects use their
own production ledger and **Create finishing handoff**, which exports an FCPXML and
`source-manifest.json` containing a project-specific Post Supervisor brief. That brief
carries the script, bible, shot direction, approved SEE/HEAR/request/WATCH IDs and
media hashes, assembly fingerprint and assembly approval state. It does not launch
an editing agent or register a returned Resolve cut. Those project-level execution
and return paths remain to be implemented; do not put another IP in this legacy ledger.

Open `/cb-studio/finishing.html?episode=Ep2` from the scene Final stage's episode review link.
This uses `cb_post_workspace` and its existing verdict ledger. It does not create a second
production pipeline or change shot approvals.

The current pre-enhancement cut is registered with its SHA-256. Google Drive review receipts
bind the link to that same digest and record remote metadata/playback verification. Approval
requires the browser's current digest and a verified matching Drive receipt. A new cut cannot
inherit an old verdict. No approval has been entered by the integration.

The Resolve control reads the live version, project/timeline IDs, frame rate, tracks
and markers through the installed MCP bridge. It compares them with the registered
candidate and distinguishes an ID match, names-only evidence, a mismatch and no binding.
Even an ID match does not prove that the timeline still corresponds to the exported file.
The director brief loads the canonical Studio skill and identifies required rendered-media
inspection. Preparing that brief is not a completed director assessment. Frame-exact MCP
capture must be used for boundary review; clip thumbnails cannot establish frame accuracy.

After subsequent MCP exports complete, run `tools/register_resolve_review.py --help` to register
an immutable review copy. It compares the export frame count with the named active timeline,
retains a Resolve snapshot, and optionally stages a copy in an existing Google Drive folder.
It never marks a sync as verified or signs a cut off. Verify the uploaded file's metadata and
playback before adding its receipt to the manifest. Current review findings remain attached to
their original version; carry forward only findings that still describe the new render.

## vCube transport

The supplied [Lark document](https://bytedance.larkoffice.com/docx/P3SZdNRuboYkgkx8alacq7hznNb)
links to [StartExecution](https://docs.byteplus.com/en/docs/byteplus-vod/reference-startexecution).
The implemented route uses the official BytePlus Python SDK for local-file upload and request
signing. Execution APIs use version 2025-07-01, Johor ap-southeast-1, vod.byteplusapi.com.
GetExecution polls the stored RunId. Profile: Enhance/Moe, aigc, Pro, RepairStrength 0,
4k, 30 fps, 10-bit. No replacement audio generation or audio enhancement is requested.
The returned audio still needs comparison against the signed cut; preservation is not assumed.

Use the existing gitignored `engine/.env` for:

- BYTEPLUS_VOD_ACCESS_KEY (or BYTEPLUS_ACCESSKEY)
- BYTEPLUS_VOD_SECRET_KEY (or BYTEPLUS_SECRETKEY)
- BYTEPLUS_VOD_SPACE_NAME (or VOD_SPACE_NAME)
- BYTEPLUS_VOD_COST_4K_USD_PER_MINUTE (the verified Pro profile rate)
- BYTEPLUS_VOD_COSTS_VERIFIED=true

The existing ModelArk bearer token is for a different authentication contract; it is never
sent to the VOD signing endpoint. No credential values appear in the browser or reports.
As verified on 8 September, these VOD settings are absent locally. The adapter is implemented
and locally tested, but account authentication, entitlement and a paid live execution remain
unverified. No paid job was submitted during implementation.

The human enhancement button records an explicit processing allowance against this job before
upload. Its estimate excludes tax/storage/transfer and does not promise an invoice total.
The job ledger retains Vid, exact request, stable ClientToken and RunId. Ambiguous upload or
submission failure requires reconciliation; automatic retries are disabled. Provider Success
means `provider-complete-awaiting-QC`. Result retrieval, audio comparison, visual inspection
and delivery approval remain required finishing work after a real job returns.

## Post Supervisor skill

`skills/resolve-animation-post-supervisor/SKILL.md` is the canonical post skill, also
discoverable through a link in the local Codex skills folder. `studio_post_contract.py`
loads its runtime guidance for both workflows. The legacy `director-brief` action returns
both Director and Post Supervisor contracts, bound to the candidate hash. Only the
legacy Crystal Bears Ep2 brief includes its dated case study; new project briefs use
the project production standard and carry no historical episode evidence by default.
The review page displays these as an operating brief, not an autonomous editor dispatch
or completed QC. Existing legacy Drive approval and vCube spending checks remain in force.

Verdict input is normalized before approval checks; concurrent verdicts and candidate
registration share a local review lock. Registration refuses an existing version name
so it cannot overwrite that version's findings or receipt. Review notes use the Studio's
existing local draft recovery, scoped to the exact cut hash. Status refresh preserves
the connected video player and playback position.
