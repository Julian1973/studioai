# Every refusal, and the one action that resolves it

**For approval before I build anything.** Julian, 3 September 2026: "Make every refusal
self-healing… Show me the list of refusals and remedies before you build it."

## What I measured, not guessed

`engine/` raises **1,011** exceptions. That is not what you meet. What you meet is what a button
in the studio can hand back, so I walked the call graph from each of the **30 director actions**
and collected every refusal reachable from it:

- **141 front-line refusals** — the wording a button can actually return to you.
- **34 blocker codes** — the states `cb_state` / `cb_production_preflight` can put a stage into.

Every one is mapped to exactly one remedy: **139 of 141** and **34 of 34**. The two left over
(`department requires a shotId`, `unknown department stage`) are unreachable unless the browser
sends a malformed request — they stay as loud refusals. The full list is the appendix, generated
from the code rather than typed, so you can spot-check any row.

## The rule I want to build to

> A blocked stage never renders a dead button. It renders the remedy — a button whose label is the
> fix, which performs the fix and returns you to exactly where you were. Where the fix needs
> something only you know, it asks for that one thing and nothing else.

Three consequences worth stating, because they change how the studio behaves:

1. **The refusal text stops being the destination.** Today the engine's sentence is the end of the
   road. It becomes the *tooltip* — the button above it is the road.
2. **The engine does not change its mind.** Every refusal stays exactly as strict. I am not
   loosening a single gate; I am giving each one a door.
3. **You are never asked twice.** After the remedy runs, the studio returns to the stage you were
   on, with the action you originally pressed now available.

## The three you lost the day to

**1 · Cast canon incomplete** — `Teacher has no locked identity pack` (2 refusals, 2 blockers)

Today: SEE refuses, the message names the character, and there is no way to act on it from the
desk. The button becomes **“Lock cast: Teacher”**, and asks you exactly one question:

> *Teacher appears in this shot. Is she a character we see, or a scripted presence staged
> off-frame?*
> **[ Attach a reference ]** — pick from the asset library or upload; the studio writes the
> identity pack and re-locks canon. **[ Staged off-frame ]** — records the role as a scripted
> stub, which canon already supports, and the shot proceeds with no reference attached.

You ruled tonight that the Teacher is a one-off, so on this shot you would press the second one,
once, and never see it again.

**2 · Stale animation direction** — `Prepare current Animation direction for S1.SH01 first`
(6 refusals, 9 blockers — this family is the single most common cause of a dead stage)

Today: WATCH refuses because the direction was signed against inputs that have since moved. The
button becomes **“Refresh direction”**: re-prepare that department from the current inputs, adopt
it, and put you back on the WATCH panel with *Compile prompt* live. No input from you. One text
call, pennies. The studio already does exactly this inside “Build opening frame” — this only makes
it a visible, reusable button for all four departments.

**3 · Superseded approval** — `the approved SEE frame is stale against its direct inputs`
(5 refusals, 5 blockers)

Today: the approval is quietly not-current and the stage dead-ends. Two buttons, and which one is
offered depends on a fact the studio can check — whether the artifact's own bytes still match:

- **“Re-confirm”** — the image/track is unchanged, only its inputs moved (a canon re-lock, a
  recast elsewhere). You re-approve the same artifact against the current inputs. Free.
- **“Rebuild”** — the artifact itself must change. Paid, disclosed as usual.

**This one needs your ruling** (see Decisions, below): re-confirming is you approving again, not
the machine keeping a stale approval — but it is the one place where a remedy touches an approval,
so I want you to say it is right before I build it.

## The remedies in full

| | Button | Refusals | Blockers | Asks you for | Cost |
|---|---|---|---|---|---|
| R1 | **Lock cast** | 2 | 2 | reference, or “staged off-frame” | free |
| R2 | **Refresh direction** | 6 | 9 | — | one text call |
| R3 | **Re-confirm / Rebuild** | 5 | 5 | — / — | free / paid |
| R4 | **Replace** | 9 | — | one sentence | as the new step |
| R5 | **Add the note** | 10 | — | one sentence | free |
| R6 | **Choose the candidate** | 3 | — | A or B | free |
| R7 | **Re-seal the request** | 17 | — | — | free until you approve |
| R8 | **Resume / Abandon batch** | 6 | — | — / reason | free |
| R9 | **Reopen the take** | 1 | — | one sentence | free |
| R10 | **Reopen with a redesign** | 3 | — | one sentence | free |
| R11 | **Go to the step that is missing** | 24 | 7 | — | free |
| R12 | **Carry onto the canon lock** | 5 | 3 | — | free |
| R13 | **Promote Story & Direction** | 4 | 3 | — | free |
| R14 | **Split shot** | 2 | — | where to split | free |
| R15 | **Lock the cut** | 2 | — | — | free |
| R16 | **Fix configuration** | 1 | 4 | varies | free |
| R17 | **Reload and retry** | 1 | — | — | free |
| R18 | **Restore the compiled prompt** | 1 | — | — | free |
| R19 | **Bind the reference** | 13 | 1 | pick the asset | free |
| R20 | **Rebuild review media** | 4 | — | — | free |
| R21 | **Fix the storyboard field** | 10 | — | the corrected text | free |
| R22 | **Re-run the scene direction** | 2 | — | optional note | paid text pass |
| R23 | **Retry the provider** | 2 | — | — | as the step |
| | *(re-raise, inherits its wrapped remedy)* | 6 | — | | |
| | *(internal invariant, unreachable)* | 2 | — | | |

**The four biggest wins by volume**, in order: *Go to the step that is missing* (31), *Re-seal the
request* (17), *Refresh direction* (15), *Bind the reference* (14). None of them needs anything
from you.

Two are worth reading twice:

- **R11 “Go to the step that is missing”** is the largest family and the most annoying one in
  practice — the stage refuses because work is owed *somewhere else*, sometimes on a different
  shot (a relay source that is not approved yet). The button will name it and take you there with
  that shot already selected, instead of telling you a fact about another shot.
- **R7 “Re-seal the request”** covers every way a sealed spend request goes stale — you approve
  the cost, something moves, the token voids. One button re-compiles the disclosure at the current
  cost. Nothing is bought until you approve the new one.

## Decisions I need from you

1. **Re-confirm (R3).** Is it right that you can re-approve an unchanged artifact against moved
   inputs, without paying to regenerate it? I believe yes — you are approving, not the machine —
   but it is your law, not mine. If you say no, R3 becomes Rebuild-only and costs money each time
   canon moves.
2. **Refresh direction (R2) adopts automatically.** The refreshed direction is recorded as adopted
   by the Studio, not by you — same as today's keyframe build. Say if you would rather see it and
   press something.
3. **Split shot (R14) is the one real build.** Everything else is plumbing an existing engine
   function to a button. Splitting a 30-second unit into two means re-deriving beat ownership, the
   packing audit and the ledger, then re-promoting. It is a few days, not an afternoon. It covers
   2 refusals. **My recommendation: leave it out of this pass** — when a direction overruns, the
   honest remedy today is *Refresh direction* with fewer timed beats, and I would rather ship the
   other 22 remedies this week than hold them behind this one.

## What I would build, in order

1. **The mechanism** — a remedy is declared next to the refusal that raises it, so a new refusal
   cannot be added without one. The studio renders `session.remedy` as the primary button.
2. **Your three** — Lock cast, Refresh direction, Re-confirm/Rebuild.
3. **The volume families** — R11, R7, R19, R5/R4/R6 (the ones that only need a sentence or a pick).
4. **The rest** — R8, R9, R10, R12, R13, R15, R16, R17, R18, R20, R21, R22, R23.
5. **Deferred** — R14 Split shot, unless you want it now.

Nothing here loosens a gate, and no remedy spends money without the usual disclosure. Say go, or
tell me what to change first.

## Appendix — every front-line refusal, and the remedy it gets

141 refusals reachable at depth 0-1 from the 30 studio actions. `PASS` re-raises inherit
the wrapped refusal's remedy; `XX` cannot be reached unless the browser sends a malformed
request. Generated, not hand-written: `scratchpad/audit/remedies.py`.


### R1 — Lock cast  (2 refusals)

- `cb_canon.py:862` [rebase-canon] — CANON LOCK {}
- `cb_render.py:4180` [run-ai-review, run-final-review, run-quality-review] — animation provider prompt is not production-ready: {}

### R2 — Refresh direction  (6 refusals)

- `cb_render.py:1119` [build-scene-plate] — Prepare current Look Development direction first.
- `cb_render.py:4175` [run-ai-review, run-final-review, run-quality-review] — animation dialogue synthesis contract failed: {}
- `cb_render.py:4643` [build-keyframe] — approved Cinematography direction for {} is missing {}
- `cb_render.py:4657` [build-keyframe] — approved Cinematography cast for {} does not match the shot contract: expected {}, got {}
- `cb_render.py:4664` [build-keyframe] — opening-frame placements for {} do not name each approved in-frame character exactly once
- `cb_render.py:4671` [build-keyframe] — approved Cinematography style for {} does not match the versioned canonical style {}

### R3 — Re-confirm / Rebuild  (5 refusals)

- `cb_render.py:3476` [run-ai-review, run-final-review, run-quality-review] — {}'s Director storyboard is no longer approved
- `cb_render.py:3513` [run-ai-review, run-final-review, run-quality-review] — {}'s scoped Director amendment no longer matches the production shot
- `cb_render.py:3537` [run-ai-review, run-final-review, run-quality-review] — {}'s signed Director shot card is stale
- `cb_render.py:4540` [accept-master, accept-quality, build-keyframe…] — post candidate is stale ({}); rebuild before decision
- `cb_render.py:6477` [accept-keyframe] — {}'s direct input(s) changed since this candidate was generated ({}); a candidate can never be approved a

### R4 — Replace  (9 refusals)

- `cb_render.py:10882` [build-master] — a current post master candidate already awaits review
- `cb_render.py:1113` [build-scene-plate] — scene {} already has a working Scene Look anchor; choose Iterate before generating another
- `cb_render.py:1208` [select-scene-plate-library, select-scene-plate-upload] — scene {} already has a Scene Look candidate awaiting a decision; reject it first, or approve it, before s
- `cb_render.py:2336` [iterate-keyframe] — {} already has a finished keyframe waiting for Accept or Iterate
- `cb_render.py:3996` [run-ai-review, run-final-review, run-quality-review] — {} already has work awaiting a decision
- `cb_render.py:5404` [build-voice] — {}'s voice take is already approved; reject it first (with a reason) before generating another
- `cb_render.py:6116` [build-keyframe] — {} already has a keyframe candidate awaiting a decision; reject it first (with a reason) before generatin
- `cb_render.py:6391` [select-keyframe-library, select-keyframe-upload] — {} already has a keyframe candidate awaiting a decision; choose another (reject it, with a reason) first
- `cb_render.py:9315` [approve-spend, prepare-render] — {} is already approved; reject it first to re-fire

### R5 — Add the note  (10 refusals)

- `cb_render.py:10332` [iterate-animation] — a batch rejection requires a plain-language correction
- `cb_render.py:10334` [iterate-animation] — category must be one of {}
- `cb_render.py:10434` [reopen-shot] — reopening an accepted take requires a plain-language correction
- `cb_render.py:10436` [reopen-shot] — category must be one of {}
- `cb_render.py:4515` [accept-master, accept-quality, build-keyframe…] — department verdict must be approved|rejected
- `cb_render.py:4530` [accept-master, accept-quality, build-keyframe…] — rejection needs a plain-language note
- `cb_render.py:5533` [iterate-voice] — a voice rejection requires a plain-language reason
- `cb_render.py:6559` [abandon-batch] — abandoning a batch requires a plain-language reason
- `cb_render.py:6593` [iterate-keyframe] — a keyframe rejection requires a plain-language reason
- `cb_render.py:7810` [save-retake-note] — WATCH Director feedback cannot be blank

### R6 — Choose the candidate  (3 refusals)

- `cb_render.py:6206` [select-keyframe-candidate] — {} has no pending SEE candidate {}
- `cb_render.py:6460` [accept-keyframe] — {} requires an explicit SEE A/B selection before approval
- `cb_render.py:6463` [accept-keyframe] — {}'s selected SEE candidate does not match the approval target

### R7 — Re-seal the request  (17 refusals)

- `cb_render.py:10404` [override-model-limited] — clear or use the existing spend disclosure before overriding
- `cb_render.py:7604` [approve-spend, prepare-render] — the presented token predates the sealed-envelope protocol and is VOID; request a new disclosure.
- `cb_render.py:7608` [approve-spend, prepare-render] — sealed-envelope integrity check failed; request a new disclosure.
- `cb_render.py:7612` [approve-spend, prepare-render] — {} ({}) changed on disk after the disclosure; the token is STALE. Request a new disclosure.
- `cb_render.py:7615` [approve-spend, prepare-render] — the audio asset changed after the disclosure; the token is STALE. Request a new disclosure.
- `cb_render.py:7620` [approve-spend, prepare-render] — the sealed envelope has no provider execution plan
- `cb_render.py:7626` [approve-spend, prepare-render] — segment {} reference {} changed after disclosure
- `cb_render.py:7632` [approve-spend, prepare-render] — the approved timed voice master changed after disclosure
- `cb_render.py:7634` [approve-spend, prepare-render] — segment {} audio changed after disclosure
- `cb_render.py:9297` [approve-spend, prepare-render] — comparison settings differ from the sealed spend envelope
- `cb_render.py:9358` [approve-spend, prepare-render] — {} has an in-flight batch; resuming requires its original spend token (nothing new is authorized)
- `cb_render.py:9364` [approve-spend, prepare-render] — the package changed mid-batch (binding mismatch); the in-flight authorization is void. Request a new disc
- `cb_render.py:9451` [approve-spend, prepare-render] — DRY RUN. No spend token was issued and no state changed.
- `cb_render.py:9464` [approve-spend, prepare-render] — SPEND NOT APPROVED. A single-use spend token has been issued, bound to the sealed envelope above; re-run 
- `cb_render.py:9470` [approve-spend, prepare-render] — unknown or already-used spend token; request a new disclosure
- `cb_render.py:9473` [approve-spend, prepare-render] — the spend token is STALE: the package, references, audio, cost or settings changed after the disclosure. 
- `cb_render.py:9720` [approve-spend, prepare-render] — candidate {} failed during its sealed provider plan ({}). The batch is saved and resumable: re-run with t

### R8 — Resume / Abandon batch  (6 refusals)

- `cb_render.py:10167` [accept-animation] — {} has no candidate batch pending review
- `cb_render.py:10171` [accept-animation] — candidate must be 1..{} for {}
- `cb_render.py:10329` [iterate-animation] — {} has no candidate batch pending review
- `cb_render.py:10406` [override-model-limited] — a candidate batch is currently generating
- `cb_render.py:9379` [approve-spend, prepare-render] — {} has a candidate batch pending Julian's review (approve one candidate or reject the batch first)
- `cb_render.py:9528` [approve-spend, prepare-render] — candidate {}'s transactionally completed artifact is missing or changed; automatic repayment is blocked

### R9 — Reopen the take  (1 refusals)

- `cb_render.py:10444` [reopen-shot] — {} has no accepted animation take to reopen

### R10 — Reopen with a redesign  (3 refusals)

- `cb_render.py:10395` [override-model-limited] — model-limited override requires a written reason
- `cb_render.py:10402` [override-model-limited] — {} is {}, not model-limited
- `cb_render.py:9257` [approve-spend, prepare-render] — {} is MODEL-LIMITED after {} failed candidate batches; the ladder requires human redesign or an alternati

### R11 — Go to the step that is missing  (24 refusals)

- `cb_render.py:1014` [select-keyframe-library, select-keyframe-upload] — Scene Look Plate is '{}', not a current signed working anchor for scene {} — prepare direction and genera
- `cb_render.py:10864` [build-master] — scene cut source is unavailable: {}
- `cb_render.py:10877` [build-master] — cannot stitch scene {}: unapproved shots {}
- `cb_render.py:2333` [iterate-keyframe] — {} inherits its opening frame and needs no build
- `cb_render.py:3471` [run-ai-review, run-final-review, run-quality-review] — {} needs a human-approved Director storyboard before new forward-standard department work
- `cb_render.py:3527` [run-ai-review, run-final-review, run-quality-review] — {}'s storyboard predates directing standard v{}
- `cb_render.py:3532` [run-ai-review, run-final-review, run-quality-review] — {} has no signed Director shot card
- `cb_render.py:3539` [run-ai-review, run-final-review, run-quality-review] — {}'s storyboard lacks the signed emotional North Star
- `cb_render.py:3547` [run-ai-review, run-final-review, run-quality-review] — {} lacks forward directing contracts: {}
- `cb_render.py:4017` [run-ai-review, run-final-review, run-quality-review] — no current QC-passed post master exists for scene {} to review ({})
- `cb_render.py:4107` [run-ai-review, run-final-review, run-quality-review] — {}'s approved voice is required before the Animation Director enters
- `cb_render.py:4191` [run-ai-review, run-final-review, run-quality-review] — no actual keyframe media exists for {} to review
- `cb_render.py:4212` [run-ai-review, run-final-review, run-quality-review] — no actual animation media exists for {} to review
- `cb_render.py:4520` [accept-master, accept-quality, build-keyframe…] — {} has no specialist candidate awaiting a decision
- `cb_render.py:5421` [build-voice] — no ElevenLabs voiceId for {} (Law 5: the voice lives in the render; no fallback)
- `cb_render.py:5521` [accept-voice] — {} has no voice track to approve
- `cb_render.py:5538` [iterate-voice] — {} has no voice track to reject
- `cb_render.py:6106` [build-keyframe] — {} is a relay shot; it anchors on its source shot's harvested final frame, never its own keyframe
- `cb_render.py:6419` [select-keyframe-library, select-keyframe-upload] — {} is the scene's first shot; there is no previous final frame to carry forward
- `cb_render.py:6427` [select-keyframe-library, select-keyframe-upload] — {} is not approved+harvested yet; there is no final frame to carry forward
- `cb_render.py:6456` [accept-keyframe] — {} has no keyframe candidate awaiting approval
- `cb_render.py:6720` [approve-spend, prepare-render, run-ai-review…] — {} has no APPROVED keyframe (a generated-but-unapproved candidate is never a valid anchor) — cb_render.py
- `cb_render.py:6727` [approve-spend, prepare-render, run-ai-review…] — {} relays off {}, which is not approved+harvested yet (status: {}) — Julian's eye comes first, always
- `cb_render.py:9323` [approve-spend, prepare-render] — {} has dialogue but {} (Law 5: voice first, no native-voice fallback)

### R12 — Carry onto the canon lock  (5 refusals)

- `cb_intake.py:1216` [rebase-canon] — {} has no approved beat package to rebase
- `cb_intake.py:1220` [rebase-canon] — canon rebase cannot cross an immutable script version
- `cb_intake.py:1223` [rebase-canon] — canon rebase source-event contract is stale: {}
- `cb_intake.py:1227` [rebase-canon] — canon rebase cannot sign changed creative content
- `cb_intake.py:1236` [rebase-canon] — episode vision does not match the unchanged beat package

### R13 — Promote Story & Direction  (4 refusals)

- `cb_render.py:3464` [run-ai-review, run-final-review, run-quality-review] — {}'s scoped Director amendment escapes the studio
- `cb_render.py:3468` [run-ai-review, run-final-review, run-quality-review] — {}'s scoped Director amendment is missing or changed
- `cb_render.py:3490` [run-ai-review, run-final-review, run-quality-review] — {}'s scoped Director amendment is not registered
- `cb_render.py:3522` [run-ai-review, run-final-review, run-quality-review] — {} lacks scoped v4 directing contracts: {}

### R14 — Split shot  (2 refusals)

- `cb_render.py:4112` [run-ai-review, run-final-review, run-quality-review] — {}'s voice-timed performance budget is overloaded: {}
- `cb_render.py:9264` [approve-spend, prepare-render] — {}'s voice-timed performance budget is overloaded: {}

### R15 — Lock the cut  (2 refusals)

- `cb_render.py:10857` [build-master] — the scene cut cannot be locked: {}
- `cb_render.py:10859` [build-master] — lock the current Director's Seat cut before building the master

### R16 — Fix configuration  (1 refusals)

- `cb_render.py:6861` [approve-spend, build-scene-plate, build-voice…] — billing profile for '{}' is UNCONFIRMED (engine/billing_profile.json: planConfirmed/cadenceConfirmed). Pa

### R17 — Reload and retry  (1 refusals)

- `cb_render.py:258` [abandon-batch, accept-animation, accept-keyframe…] — {}; reload the scene and retry

### R18 — Restore the compiled prompt  (1 refusals)

- `cb_render.py:7701` [approve-spend, prepare-render] — saved WATCH working prompt is stale against the current SEE/HEAR/reference inputs. Restore it or save the

### R19 — Bind the reference  (13 refusals)

- `cb_render.py:1116` [build-scene-plate] — reference_path does not exist: {}
- `cb_render.py:1205` [select-scene-plate-library, select-scene-plate-upload] — unknown Scene Look source {}; must be upload or library
- `cb_render.py:1212` [select-scene-plate-library, select-scene-plate-upload] — no uploaded file found to select
- `cb_render.py:1224` [select-scene-plate-library, select-scene-plate-upload] — the selected library item no longer exists on disk
- `cb_render.py:2869` [approve-spend, prepare-render, run-ai-review…] — the {} reference file is missing
- `cb_render.py:2871` [approve-spend, prepare-render, run-ai-review…] — {} resolves outside this canonical Studio's approved asset libraries ({}); re-select it inside the curren
- `cb_render.py:6375` [select-keyframe-library, select-keyframe-upload] — unknown opening-frame source {}; must be upload, library or previousFinalFrame
- `cb_render.py:6401` [select-keyframe-library, select-keyframe-upload] — no uploaded file found to select
- `cb_render.py:6413` [select-keyframe-library, select-keyframe-upload] — the selected library item no longer exists on disk
- `cb_render.py:6698` [approve-spend, prepare-render, run-ai-review…] — openingFrameOverride for {} is missing
- `cb_render.py:6701` [approve-spend, prepare-render, run-ai-review…] — openingFrameOverride for {} resolves outside the approved Studio media and asset libraries
- `cb_render.py:6936` [approve-spend, prepare-render] — provider reference slot text conflicts with sealed uploads: {}
- `cb_render.py:737` [approve-spend, prepare-render] — required continuity prop authority is missing from the exact provider attachment list: {}. Register the a

### R20 — Rebuild review media  (4 refusals)

- `cb_render.py:3966` [run-ai-review, run-final-review, run-quality-review] — could not extract review frames from {}: {}
- `cb_render.py:3971` [run-ai-review, run-final-review, run-quality-review] — no visible frames could be extracted from {}
- `cb_render.py:961` [build-scene-plate, select-scene-plate-library, select-scene-plate-upload] — the scene look record is unreadable ({}: {}); restore it from media/archive or delete it to start the sce
- `cb_render.py:9835` [approve-spend, prepare-render] — cannot restore approved HEAR audio for {} candidate {}: review media or voice master is missing

### R21 — Fix the storyboard field  (10 refusals)

- `cb_render.py:384` [approve-spend, prepare-render] — {} is a complex multi-character WATCH shot and must have an approved SEE keyframe before fire. Detected c
- `cb_render.py:393` [approve-spend, override-model-limited, prepare-render] — the production package failed design validation; fix the design, never fire past a red validator
- `cb_render.py:4648` [build-keyframe] — approved charactersInFrame for {} contains duplicates
- `cb_render.py:4677` [build-keyframe] — opening frame for {} is not a playable stage: {}
- `cb_render.py:6112` [build-keyframe] — opening frame is not a playable stage: {}
- `cb_render.py:6470` [accept-keyframe] — {}'s generated keyframe cannot be accepted until the objective playable-stage and identity screen passes 
- `cb_render.py:7421` [approve-spend, prepare-render] — {} is not active in the current package
- `cb_render.py:7543` [approve-spend, prepare-render] — fresh validation of the CURRENT package failed with {} error(s) (first: {} at {}). A revised package requ
- `cb_render.py:8130` [approve-spend, prepare-render, run-ai-review…] — engine preflight failed: {}
- `cb_render.py:9329` [approve-spend, prepare-render] — dialogue synthesis preflight failed before spend: {}

### R22 — Re-run the scene direction  (2 refusals)

- `cb_creative.py:1430` [direct-scene] — BEAT PASS DROPPED/DUPLICATED/REORDERED source beats — expected {}, got {}
- `cb_creative.py:1481` [direct-scene] — BEAT PARTICIPANT UNKNOWN - {} names {}; the scene's locked cast is {}

### R23 — Retry the provider  (2 refusals)

- `cb_gen.py:427` [build-scene-plate] — SEE/keyframe production is locked to Seedream 5 Pro ({}); model overrides and CB_IMAGE_PROVIDER fallbacks
- `cb_render.py:10906` [build-master] — post build failed: {}

### PASS — (re-raise — inherits the inner remedy)  (6 refusals)

- `cb_render.py:1237` [select-scene-plate-library, select-scene-plate-upload] — {}
- `cb_render.py:9376` [approve-spend, prepare-render] — {}
- `cb_render.py:9462` [approve-spend, prepare-render] — {}
- `cb_render.py:9490` [approve-spend, prepare-render] — {}
- `cb_render.py:9523` [approve-spend, prepare-render] — {}
- `cb_render.py:9740` [approve-spend, prepare-render] — {}

### XX — (no remedy — internal invariant)  (2 refusals)

- `cb_render.py:3178` [accept-master, accept-quality, iterate-master…] — department '{}' requires a shotId
- `cb_render.py:3983` [run-ai-review, run-final-review, run-quality-review] — unknown department stage '{}'

### Blockers the studio surfaces (34)

- `CANON_LOCK_REQUIRED` → **Lock cast**
- `VOICE_ID_MISSING` → **Lock cast**
- `ANIMATION_NOT_APPROVED` → **Go to the step that is missing**
- `DIRECTOR_REVIEW_NOT_CURRENT` → **Go to the step that is missing**
- `KEYFRAME_NOT_APPROVED` → **Go to the step that is missing**
- `RELAY_FRAME_NOT_READY` → **Go to the step that is missing**
- `SCENE_LOOK_NOT_APPROVED` → **Go to the step that is missing**
- `TIMING_SLATE_NOT_CURRENT` → **Go to the step that is missing**
- `VOICE_TAKE_NOT_APPROVED` → **Go to the step that is missing**
- `STALE_PACKAGE` → **Carry onto the canon lock**
- `STALE_PRODUCTION_GRAPH` → **Carry onto the canon lock**
- `STORY_INTAKE_APPROVAL_REQUIRED` → **Carry onto the canon lock**
- `PACKAGE_VALIDATION` → **Promote Story & Direction**
- `PRODUCTION_PACKAGE_MISSING` → **Promote Story & Direction**
- `STORYBOARD_NOT_APPROVED` → **Promote Story & Direction**
- `CONFIG_ELEVENLABS_KEY` → **Fix configuration**
- `CONFIG_FAL_KEY` → **Fix configuration**
- `CONFIG_FFMPEG` → **Fix configuration**
- `SHOW_PROFILE_CONTENT_MISSING` → **Fix configuration**
- `SCENE_LOOK_REFERENCE_REQUIRED` → **Bind the reference**
- `ANIMATION_DIRECTION_NOT_APPROVED` → **Refresh direction**
- `ANIMATION_DIRECTION_NOT_CURRENT` → **Refresh direction**
- `CINEMATOGRAPHY_NOT_APPROVED` → **Refresh direction**
- `CINEMATOGRAPHY_NOT_CURRENT` → **Refresh direction**
- `LOOK_DIRECTION_NOT_APPROVED` → **Refresh direction**
- `LOOK_DIRECTION_NOT_CURRENT` → **Refresh direction**
- `STALE_ANIMATION_DIRECTION` → **Refresh direction**
- `VOICE_DIRECTION_NOT_APPROVED` → **Refresh direction**
- `VOICE_DIRECTION_NOT_CURRENT` → **Refresh direction**
- `ANIMATION_TAKE_NOT_CURRENT` → **Re-confirm / Rebuild**
- `KEYFRAME_NOT_CURRENT` → **Re-confirm / Rebuild**
- `SCENE_LOOK_NOT_CURRENT` → **Re-confirm / Rebuild**
- `SHOT_NOT_READY` → **Re-confirm / Rebuild**
- `VOICE_TAKE_NOT_CURRENT` → **Re-confirm / Rebuild**