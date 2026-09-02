# Overnight run — Ep1, night of 2–3 September 2026

**No footage. I did not get a shot rendered, and I am not going to dress that up.**

What I found instead is, I think, the thing actually standing between you and an episode.

## The wall

Every shot has to pass the Animation Director before it can render. That stage compares the
model's typed output against the approved storyboard with **hard guards that raise rather than
repair** — and several of them compare **byte for byte**. A language model paraphrases. So the
specialist cannot reliably satisfy them, and one word costs the whole shot.

I cleared four of these tonight, in order, each one revealing the next:

1. **`primaryEvent` / `observableEndState` changed** — the guard demanded an exact string match on
   text the model was merely asked to copy. Fixed properly: `carry_approved_stage_events` now
   stamps the approved wording back on, exactly as `carry_approved_gag_clock_text` already did for
   the gag contracts. The fact is immutable by construction instead of being asked for politely.
2. **"changed the approved number of motivated internal shots"** — the approved counts were hard
   guards and the specialist was never told the numbers. Now stated up front, in the same form as
   the DP's opening-cast law.
3. **A genuine contradiction in the brief.** S2.SH03's storyboard approved **one** internal shot
   (deliberately — "keep Jenny, the worksheet, the bed and the shoebox in one private room
   relationship") while the system prompt told the Director *"action units use two to four internal
   shots"*, with three stages to cover. It was being pulled two ways and refused whichever way it
   landed. The instruction now follows the approved count when there is one.
4. **No re-fire at all.** A single bad sample ended the shot. There is now one automatic re-fire,
   seeded with the refusal text so the second attempt is a correction rather than another guess —
   the same economy every paid step already had.

**The fifth is still there:** *"generation design changed the approved handoff state."* Same
family. It needs the same treatment — either carry the approved handoff state, or state it as a
law the specialist can actually satisfy. That is the first job in the morning.

## What did get fixed and is committed

- **Voices.** You were right, they were all on the account. Patch, Rumble, Tilly and Nib are wired
  into canon. **Jenny's own voice card was missing `physicalSignature`**, which made *every* voice
  take raise `KeyError` — that shot could never have produced audio before tonight. All five cards
  are now complete, grounded in each character's own essence and the register you wrote into the
  ElevenLabs voice. Canon re-locked, current, zero blockers.
- **Scene 1's world.** I had approved a cardboard classroom as Jenny's real classroom — my misread
  of the two worlds, and it was wrong. Your naturalistic "BRIDGE" classroom is now the approved
  plate, and your own frame of Jenny at the board is the approved keyframe, both uploaded at no
  generation cost.
- **The monsters** are registered as proper four-view turnarounds (they were `single-anchor` with
  zero declared views while Jenny had four).
- **SEE is two sections** with the picture at the top of each and Generate / Upload / Use library
  under both — though note that landed in `app.html`, and **you are on `director.html`**, which is
  a separate front end. That one still needs doing.
- A Windows file-lock crash in the media writer, and the Norton TLS interception that was breaking
  every provider call.

985 tests pass. Spend for the whole night: three images, about 35p.

## Where the episode actually stands

| | |
|---|---|
| Renderable once the animation stage is fixed | S2.SH03, S2.SH04, S3.SH05, S3.SH06, S5.SH13 |
| Blocked on a missing voice | S1.SH01, S5.SH14 (Teacher) · S1.SH02 (Classmate) |
| Blocked on your Gate 1 | Scenes 3 and 5 storyboards are `awaiting-human-storyboard-approval` |
| Missing entirely | Scene 4 has no production package; 8 shots exist against a declared 15 |

## What I would do first

1. Finish the animation guards — the fifth, and sweep the rest of that file for the same pattern.
   Until that is done, no shot in the episode can render, and it will keep costing a shot at a time.
2. Cast Teacher and Classmate. Nothing on the account matches either.
3. Then a clean run, which at that point should be uneventful.
