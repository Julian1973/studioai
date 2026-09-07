# Provider evidence review · 7 September 2026

## Executable route and research are separate

The active route remains the configured BytePlus ModelArk adapter. Its current contract and
the successful S8.SH2 task are the local operational evidence; this review does not change
models, resolution, pricing, account configuration or reference limits.

The official [ModelArk task API](https://docs.byteplus.com/en/docs/modelark/1520757)
was checked today. Its public rendered page exposed its update date but not the full schema.
That is not sufficient evidence to increase the current adapter's limits.

The official [LAS video service](https://docs.byteplus.com/en/docs/byteplus_las/video_gen_enhanced)
documents Seedance 2.5, editing, extension and combined reference modalities. LAS is a distinct
endpoint/service. Its advertised enhancements must not be silently applied to ModelArk.

The official [ElevenLabs dialogue guide](https://elevenlabs.io/docs/overview/capabilities/text-to-dialogue)
describes per-turn voices and natural-language acting tags. Tags are not a closed universal enum;
their effectiveness needs auditioning in the selected character voice. Retain the Studio's
audio-ownership policy: non-dialogue sound design belongs to its designated sound lane.

The official [timestamped dialogue API](https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert-with-timestamps)
provides segment and alignment data. Use returned timing to place performances rather than
treating estimated duration as measured. Its guidance recommends at most 2,000 input characters
for reliable generation and allows up to ten distinct voice IDs; validate the actual request.

Seedream still-image route settings remain pinned to the existing configured adapter. A fresh
full official Seedream schema was not verified in this review; no new capability is claimed.

## Review on upgrade

1. Fetch official documentation for the exact proposed endpoint and record unknowns.
2. Run the no-network contract/fixture tests, including unsupported-control rejection.
3. Present a bounded comparison quote when a real provider trial is needed.
4. Compare the same approved references, script and audio. Record time, cost and human verdict.
5. Promote a versioned route only after both integration and media acceptance; preserve rollback.

No skill can honestly guarantee it is permanently ahead of the technology. This process makes
new capabilities assessable without disrupting a film already in production.
