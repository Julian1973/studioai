# Animation Studio Interface Contract

The Seven UX Laws are release criteria. A feature is incomplete when its engine
mutation works but the human cannot understand or continue the outcome in the
same browser session.

## 1. One location truth

The URL hash owns project, scene, shot, beat and view. An explicit location is
never replaced by cached server selection. Refreshing the URL restores the same
workspace.

## 2. One current decision

Every production screen shows one permanent orientation line and one current
decision. The decision always has an outcome: approve, refire, fix, retry, start,
or continue. There are no dead ends.

## 3. Literal production state

Prepared, awaiting approval, submitted, rendering, failed and accepted are
different states. Labels, elapsed activity and spend copy must describe the real
state; only a submitted provider job may say rendering.

## 4. Immediate, refresh-free acknowledgement

Every action acknowledges the click immediately, reports useful progress, and
projects its completed state without a manual reload. A job is not published as
done until indexes and session caches contain its result.

## 5. The human owns every sign-off

Automation may recommend and perform mechanical checks. Only Julian may accept
or reject a keyframe, voice performance, animation, or final master. Candidates
remain candidates until that explicit verdict.

## 6. Refusals are honest and actionable

A refusal shows the real reason in plain English beside a specific fix or retry
action. Retake notes are durable production diagnoses; they are never discarded
silently and never replaced by generic scare copy.

## 7. Continuity survives time

Authentication survives safe server restarts. The selected location, accepted
state, notes and media playback survive refreshes and polling. Polling must not
erase an image, reset audio, duplicate a paid action or revive stale history.

## Golden Path Release Gate

The browser Golden Path is required before a push:

`launch -> SEE -> HEAR -> WATCH -> verdict`

It uses mocked providers and must prove orientation, ordered sign-offs, immediate
feedback, a real refusal with a visible fix action, durable notes, refresh-free
state advancement, and a final human verdict.

The repository hook is enabled with:

`git config core.hooksPath .githooks`

It runs `scripts/verify_push.sh`; a failing browser journey blocks the push.
