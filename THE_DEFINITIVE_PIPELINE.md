# Current production contract · 16 September 2026

The only current producer workflow is:

**SCRIPT → DIRECT → SEE → HEAR → WATCH → FIRE → REVIEW**

## Authority

- **SCRIPT** owns scene order, story and exact spoken dialogue.
- **DIRECT** is the sole creative directing stage. It owns beats, generation-unit
  boundaries, internal cuts, timed visible action, performance, camera, composition,
  geography, coverage, opening state and landing state. Cinematic Language is vocabulary
  used inside DIRECT; it is not another department or gate.
- **SEE** contains the Scene Plate, this unit's Opening Keyframe and an optional Illustrated
  Storyboard. A storyboard can be skipped explicitly for a simple unit.
- **HEAR** compiles exact spoken dialogue plus DIRECT performance intent and the locked
  character voice into one ElevenLabs v3 request. The returned human-approved media is
  Audio1. Non-spoken action and SFX never enter the voice request.
- **WATCH** deterministically compiles current DIRECT, approved SEE, approved Audio1,
  current references, show-bible binding and provider settings. It validates; it does not
  rewrite, direct, repair or call a creative department.
- **FIRE** submits one immutable, human-authorized sealed request to BytePlus.
- **REVIEW** presents the returned media for human Approve or Retake.

## Generation units and continuity

A scene is a dramatic unit. A story beat is a cause, effect or emotional change. A
generation unit is one Seedance request and may contain multiple authored internal views
and cuts.

New production uses `EDITORIAL_CUT`. Every generation unit has its own approved Opening
Keyframe and ends on a readable beat. The next unit deliberately changes composition while
preserving identity, wardrobe, props, geography, screen direction, weather, lighting,
physical condition and story state.

Story continuity is required. Pixel continuity is not. Current production has no previous
final-frame prerequisite, previous-video `@Video1` attachment, extension source or exact-pose
continuation requirement. Historical handoff and video-extension records remain evidence;
they are not current authority and cannot block or modify current production.

## Human decisions and recovery

The producer approves visible media: Scene Plate, Opening Keyframe, optional Storyboard,
Audio1 and returned animation. Internal preparation never manufactures approval.

WATCH preview and FIRE use the same readiness implementation. Readiness checks current
DIRECT, SEE, Audio1 when required, references, provider settings, active provider work and
exact action integrity. It returns one current actionable blocker and never invents an
automatic creative repair.

The sealed request binds DIRECT action, references, Audio1, provider/model/settings and
request hash. Returned-media approval compares against that sealed production truth.
Unrelated mutable working records cannot make the take stale.

If a provider task ID exists, recover or poll that exact task. If submission outcome is
unknown, stop and reconcile before another attempt. Never duplicate-submit by inference.

Historical specialist, failed-preparation and recovery records remain readable evidence.
They are non-authoritative unless they describe a genuinely active current provider
operation.

## Verification

Run `scripts/verify_push.sh` plus the permanent zero-provider current-path tests. Preserve
approved media and production records during maintenance. Passing software checks qualifies
the route; only human review qualifies the creative result.
