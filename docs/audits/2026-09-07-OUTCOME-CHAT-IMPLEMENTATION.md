# Outcome-led production chat

Implemented 7 September 2026 in the canonical AI Studio.

## Producer workflow

1. Upload the script. The Studio proposes an editable, provisional episode allowance without a provider call. Approve it once in production chat.
2. Existing automatic intake and scene direction populate production packages. The outcome worker prepares the internal world reference and the first SEE candidates for each scene.
3. Review SEE. Select a candidate in the interface or say **approve A** / **approve B** in chat. **Approve** accepts the currently selected candidate. The worker then prepares HEAR.
4. Listen and approve the voice. Silent shots proceed to request preparation without fabricated audio or an unnecessary voice approval.
5. Review WATCH's exact per-part animation prompts, references and shot dialogue. **Approve watch request** or **fire** submits the sealed request.
6. Watch the returned candidate. **Approve render** records final acceptance and prepares the next shot. At the end of the scene, review its cut in Director's Seat.

Creative notes continue through the existing scoped Director correction path. **Apply correction** invokes that same reviewed correction from chat. Approved work elsewhere is preserved. Continuity problems still require an explicit resolution; learning observations cannot override script or canon.

## What enforces the workflow

- Deterministic approval commands do not ask a language model to decide whether something was approved. Ambiguous, negative or conditional messages cannot trigger approval.
- Chat carries a fingerprint of the reviewed artifact. The scene worker checks it again under the scene lease. Changed bytes or shot inputs invalidate the old decision.
- Keyframe A/B selection remains explicit. Multi-candidate WATCH comparisons retain their existing candidate selection interface.
- WATCH request approval grants generation only. It never approves the returned film.
- Internal direction and scene-reference preparation are attributed to Studio Director, never to Julian.
- Episode reservations are atomic across processes. Existing spend survives allowance changes and script uploads. Unknown submissions retain their allocation; they are not retried automatically.
- Budget failure before BytePlus POST does not create a phantom submitted task. Known provider tasks can be recovered without another budget charge for submission.
- Worker processes carry the episode identity into text and media cost controls. The scene-reference billing check now names its actual BytePlus image provider.
- Continuations wait for completed jobs and check the original episode, scene and shot before navigating. Errors remain visible in chat.

## Boundaries

The allowance uses configured estimated costs in USD excluding tax. The initial proposal assumes approximately 50 script words per 30-second shot, one WATCH take, SEE A/B, voice and internal direction, with 25% revision allowance. It is editable and is not an invoice quote. Changed plans, extra iterations, provider prices or unusually costly direction can exhaust it. No provider request is authorized merely by uploading a script.

Legacy episodes without an allowance record retain their existing manual production paths. The new budgeted upload workflow creates an allowance record before starting paid preparation.

No paid generation or human media approval was performed to test this implementation. A real Episode 3 production run still requires the script and Julian's allowance approval. Provider output quality and invoice accuracy have not been certified by these software tests.

## Verification

- Complete regression: 1,069 passed, 4 skipped; process exited successfully. Results: `2026-09-07-outcome-chat-tests.txt`.
- New behavioral tests cover parallel budget reservations, unknown submission retention, BytePlus refusal/recovery, text settlement, exact artifact approval, separate request/render decisions, silent shots and navigation races.
- Final chat continuation check: 6 behavioral browser-function tests passed, including refreshing the next outcome after chained jobs.
- JavaScript syntax and Python compilation checked.
- Read-only audit: `2026-09-07-outcome-chat-evidence.json`. All 8 scene lineages are current; the 19 shot asset audit records match the prior integration audit. The audit changed no production packages.
- Live service was verified current with zero running jobs. The accepted Episode 2 production remains present.
