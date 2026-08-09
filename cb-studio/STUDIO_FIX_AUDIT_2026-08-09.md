# Studio Fix Verification Audit

Date: 2026-08-09

This report applies the verification checklist in `STUDIO_FIX_DOC.md` to the
current Director build. A check is marked PASS only when exercised by the live
browser or the mocked-provider Golden Path. Historical state is not rewritten
to make the report look green.

| # | Verification item | Result | Evidence |
|---|---|---|---|
| 1 | ElevenLabs key replaced; three failed jobs retried and green | **FAIL** | A valid `sk_` credential is configured and later `director:build-voice:S1.SH1A` jobs are green. The two historical `director:prepare-render:S1.SH1A` failures remain failed rather than having been retried successfully. |
| 2 | Stale tab detects a new build and blocks actions | **PASS** | Golden Path opens a second tab, changes the reported build, observes the update banner, and verifies `pointer-events: none` on the workspace and navigation. |
| 3 | Hash controls scene, shot and beat; refresh is identical | **PASS** | Live browser and Golden Path both preserved `scene=1&shot=S1.SH1A&beat=chase`, the same shot, and the same orientation after refresh. |
| 4 | Navigation labels remain visible at every supported width | **PASS** | Golden Path verifies desktop labels and the four mobile navigation labels at 390px. |
| 5 | Image and audio state survive ten polls | **PASS** | Golden Path performs eleven Director-session reads and verifies the same marked audio element, retained playback position, and unchanged image source. |
| 6 | A note survives navigation as a retake diagnosis | **PASS** | Golden Path enters a plain-English note, leaves the field without another production action, and verifies the saved diagnosis in authoritative session state. |
| 7 | Killing a voice job mid-run shows the real error and Retry | **FAIL** | Real provider refusals now show their exact error plus the current Fix/Retry action and Dismiss. The exact user-killed mid-run voice-job case has not been exercised and cannot yet be claimed green. |
| 8 | All progress indicators agree | **PASS** | Golden Path verifies exactly one orientation line and one current sign-off after repeated polling. The live Studio shows `Scene 1 of 10 · Shot 1 · Sign-off 2 of 3` with SEE signed, HEAR current and WATCH locked. |

Additional release evidence:

- Existing authenticated browser session survived a real Studio server restart.
- Golden Path completed launch -> SEE -> HEAR -> WATCH -> verdict without a page refresh.
- Provider refusal showed its real cause and an actionable fix.
- Every push runs the UX contract tests and Golden Path through `.githooks/pre-push`.

Current result: **6 of 8 checklist items pass; 2 remain open.**
