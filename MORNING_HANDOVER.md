# Morning handover — 26 July 2026

You asked to wake up and run the new system. It runs. Start the Studio and go.

```bash
python3 cb-studio/serve.py
```

Then open **http://127.0.0.1:8765/cb-studio/app.html** — the "Can't reach the studio
server" dialog is gone (see §3).

---

## 1. What changed while you slept, in one line each

| | |
|---|---|
| **The stage is now built from the direction too** | `prepare_cinematography` was blind to the beat's intent — only the animation chair had it. Both now read the same source. |
| **The Stop no longer blocks approved work** | It was refusing your own approved SH1 keeper. Recalibrated against four real verdicts; 4/4 correct. |
| **The Studio shows the real chairs** | Nine hardcoded labels still said "Animation Director / Camera". Fixed, and bound to the engine by a test. |
| **The studio can reach its own server** | `BASE` was pinned to `localhost` while you browse `127.0.0.1`. Fixed and verified live. |

**317 tests pass. No provider calls were made in any of this work. The production package
is byte-identical (`d212af02bdbfe5797eca4f26f1100441`).**

---

## 2. The thing you said that changed the design

> *"the keyframe gives the stage which allows the performance to deliver and breathe — but
> BOTH those prompts are engineered FROM the director, not the other way around"*

That was a real gap, not a nuance. The animation chair had your intent; the keyframe chair
had none of it. So the stage was being composed without knowing what had to happen on it —
which is exactly how you get a frame that's beautiful and leaves the performance nowhere to
go.

Both chairs now read **one shared reader** (`cb_departments._intent_charge`). One source
deliberately, not two: two would have drifted apart the first time either was edited, which
is precisely how the keyframe chair ended up blind in the first place.

The stage's brief now opens by telling it what a stage is *for*:

> Build a frame that **AFFORDS** it: room to travel in the direction the action travels, the
> object the gag needs actually present and reachable, both characters placed so the moment
> can play, air where the payoff has to land. A frame that is beautiful and leaves the
> performance nowhere to go is a failed frame.

And your other point — *"prompts are always compliant because we build them AFTER the
director has given us the outcomes"* — is now the actual architecture. Compliance is
**produced, not policed**: the writer is charged with your intent before writing, the gate
refuses at authoring time where a miss means the job wasn't done, and at fire time it only
warns (the prompt already carries your approval by then).

---

## 3. Two bugs that would have stopped you this morning

**The Stop was refusing your approved keeper.** Gating every intent field refused
`SH1_KEEPER_EXEMPLAR` — the take *you approved* — on five tempoDesign clauses the keeper
genuinely delivers in its own words ("bounce" for "uncontrolled bounce", "push" for "dolly",
"blink"/"proud" for "stillness before pride"). A false refusal on approved work is the worst
failure this gate can have: it stops the studio.

Calibrated against four prompts with real recorded verdicts:

| prompt | expected | gating everything | gating payoff+felt |
|---|---|---|---|
| SH1 keeper (you approved) | PASS | ✗ **STOP** | ✓ PASS |
| SH2 intent-delivered | PASS | ✓ PASS | ✓ PASS |
| SH2 old-engine (rejected) | STOP | ✓ STOP | ✓ STOP |
| SH2 laboured (rejected) | STOP | ✓ STOP | ✓ STOP |
| | | **3/4** | **4/4** |

So the Stop refuses on `visualPayoff` + `feltIntent` only. `tempoDesign`,
`dramaticIntent`, `emotionMechanic`, `doesItLand` stay in the writer's charge and in every
report as **advisory** — real direction, delivered through pacing a word-match cannot see,
judged by your eye. Nothing was dropped; it was scoped.

**The CORS bug.** `BASE` was hardcoded to `http://localhost:8765` while you browse
`127.0.0.1:8765` — same server, different origin, so every fetch failed and the UI reported
"Can't reach the studio server" over a page whose data had loaded perfectly. That's the
dialog from your screenshot. Now follows the page's own origin. **Verified live in the
browser**, not from the source: `BASE === location.origin === http://127.0.0.1:8765`, and a
real `/api/health` returns 200.

---

## 4. The chairs, as the Studio now shows them

| Stage | Who holds it | Craft contract loaded |
|---|---|---|
| Look Development | Cinematographer / DP | cinematographer |
| Cinematography | **Director (staging) / DP (execution)** | cinematographer *(hers, kept)* |
| Voice | **Director with the Voice Director** | voice-director |
| Animation | **Director** — Docter's chair, Keane on weight/appeal | director |
| Director Review | **Director with Continuity** | continuity *(kept)* |
| Final & Post | Post Supervisor | post |

A first pass at this set the *skill* to "director" on four rows — which didn't put you in the
room with your specialists, it **deleted them** (the DP's lens/light contract silently
replaced). A test caught it. The label names authority; the craft contract stays with the
expert. Animation is the one genuine transfer.

`engine/test_studio_chair_table.py` now looks each worker title up from
`cb_render._DEPARTMENT_WORKERS` and asserts that exact string appears in `app.html` —
editing either side alone fails the suite.

---

## 5. Your storyboards, audited beat by beat

**Scene 1 — the scene you're running — is ready. All five shots.**

| shot | gated intent | clauses | payoff clauses |
|---|---|---|---|
| S1.SH1 | 2/2 | 12 | 2 |
| S1.SH2 | 2/2 | 13 | 3 |
| S1.SH3 | 2/2 | 6 | 2 |
| S1.SH4 | 2/2 | 5 | 1 |
| S1.SH5 | 2/2 | 4 | 2 |

Fixed along the way: `visualPayoff` clauses were being **silently discarded entirely** on
real shots — S1.SH3 and S1.SH5's payoffs ("swallowed", "smiling", "sigh") weren't in the
demand-verb list, so the payoff was never enforced at all. Payoff clauses always count now.

**Scene 0 (3 shots) has a real gap: no `feltIntent` on any of them.** I did not invent it.
Writing your beat's purpose for you is exactly the drift the Fidelity Law exists to stop.
It's flagged, not filled.

---

## 6. What is NOT done — read before you fire

- **Scene 1's departments are all STALE.** Every shot reports
  `directionCurrent: false` — upstream inputs changed since those directions were approved.
  This is the system working correctly, not a bug: you'll re-prepare and re-approve
  Cinematography → Voice → Animation per shot. Preparation is text-only, no spend.
- **Nothing has been fired.** No keyframe, no clip, no voice take. Every generation is yours
  to authorise in the morning.
- **The chair sweep found ~30 more stale mentions** in docs and comments (`SKILL.md` files,
  `THE_DEFINITIVE_PIPELINE.md`, the Studio Bible). None are live code — they don't affect a
  render. The workflow that was verifying them hit the monthly spend limit partway
  (33 of 51 agents completed) so I stopped delegating and finished by hand. Unfixed, named.
- **Scene 0's missing `feltIntent`** — yours to author.
- **The keyframe canvas-affordance *check*** (does the stage measurably afford the
  performance) is still only a *charge* to the writer, not a verified gate. Tracked.

---

## 7. Proof, not assertion

Everything above was verified by running it, not by reading the code:

- Both chairs receive your real S1.SH2 intent — proven on the real `_shot_context` route
  with the LLM stubbed, zero spend, both showing "the grin-held-too-long… comedy hinge".
- The Stop passes the intent-delivered SH2 prompt and stops the old-engine one with
  **6 missed clauses named in your own words**.
- Retired chair labels present in the served page: **0**.
- `BASE === location.origin`, `/api/health` → 200, measured in the browser.

Commits: `23852ef` (intent engineering + calibration), `17af967` (Studio + CORS + binding
test).
