I now have everything confirmed against real code. Here is the implementation-ready redesign spec.

---

# Crystal Bears Studio — Gate Flow Spine: Redesign Spec

Build target: `cb-studio/app.html` (1043 lines) + `cb-studio/serve.py` (655 lines). Plain JS, no router, stdlib HTTP. All line numbers below are verified against the current files.

---

## 1. CURRENT STATE

**The gate flow today.** Sign-off state lives in `cb-gen/locked.json` as `Ep{N} → sceneNumber → {"1","2a","2b","3","4":bool}`. The real sequence is `GATE_SEQ=["1","2a","2b","3","4"]` (serve.py:229, cb_pipeline.py), but the UI presents 4 gates from `GATE_DEF` (app.html:743). Firing POSTs `/api/fire` → `_start` spawns `cb_pipeline.py` as a detached process group, streamed line-by-line into `JOBS[jobId]={status,step,log}` (serve.py:157-189); the browser polls `/api/pipeline` every 3s (`refreshPipe`, app.html:759; timer app.html:1037). STOP kills the process group with SIGKILL at three scopes (`stopFiring`, app.html:810). Sign-off is `approveGate`→`/api/approve`→`cb_pipeline approve` (app.html:795); unlock rule is `fireable=(g==1)||gApproved(g-1)` (app.html:849). All of this **works** and is enforced in three layers (UI disable, HTTP 409 via `_gate_ready` serve.py:232, pipeline-level guard).

**Where it falls short of press→activate→sign-off→next:**

1. **Not the spine.** Pipeline is one tab among nine in `NAV` (app.html:104); `openEpisode` lands on `script` (app.html:464), not the gate flow. The gates are a passive `renderGates` breadcrumb (app.html:207-213) plus a per-scene wall of cards.
2. **No "where am I / what's next."** Signing gate N just flips a grey `🔒 locked` chip to a grey `ready` chip and un-dims a Fire button (app.html:852-853). No highlight, no arrow, no auto-advance, no single surfaced next action. "ready" (`--muted`) and "locked" (`--hint`) are both low-contrast greys.
3. **Gate 2 is split-brain.** The Pipeline tab shows one "Gate 2" card whose Sign-off secretly fires 2a-then-2b (app.html:783,796), but the actual 2a/2b build UI only exists on the **Keyframes** tab (`sceneAnchors`, app.html:633). Pressing "Sign off" on Gate 2 from Pipeline before the foundation exists hits a server refusal instead of guidance.
4. **Confirm/alert friction.** Every fire uses `window.confirm`; `fireSub` even pops a blocking `alert("Building…")` (app.html:686).
5. **Review is blind.** No keyframe QA / Definition-of-Done verdict surfaces anywhere — `cb_qa.check_done_frame` output is only a transient log string (`"Visual QA…"`, serve.py:138). The 7 North-Star beat fields (`want,need,crystalTruth,kidRead,adultRead,theGame,wordlessHeld`) the Director writes (cb_director.py:240-244) are invisible in `card`, `kfCard`, `openShot`, and `renderBeatEditor` — Julian signs off Gate 1 without seeing the beat's soul. (`/api/beat-update` already persists arbitrary keys — serve.py:503-509, no whitelist — so this is purely front-end.)
6. **Server guard hardcodes Ep1** (`_scene_locks`, serve.py:231) — defense-in-depth broken for any other episode.

---

## 2. TARGET UX — the gate-by-gate spine

### 2.1 The spine: a 4-gate journey stepper, episode-wide

Make the **Pipeline page the home of an open episode** and the visual spine. `openEpisode` lands here (not `script`). The page has two zones:

**A. Episode header + horizontal gate stepper (always visible, sticky).**
```
Ep1 · The Adventure Begins                       [■ STOP firing]  (only when a job runs)

 ✓✓ ─────── ● ─────── ▷ ─────── 🔒
 GATE 1     GATE 2     GATE 3     GATE 4
 Director   DP key-    Camera     Post
 plan       frames     clips      mix + stems
 signed     ● running  ready      locked
```
Each gate is a node with a state glyph + connector line. The **active node glows** (brand border + soft pulse); connectors fill brand-colour as gates complete. This is `renderGateRail()`, rendered from an episode-rollup of `PIPE.locked` across all scenes.

**Gate state vocabulary (one source of truth, `gatePhase(sn,g)`):**

| Phase | Glyph | Colour | Meaning |
|---|---|---|---|
| locked | 🔒 | `--hint` grey, dimmed | previous gate not signed |
| ready | ▷ | `--brand` solid, **bright** | fireable now — primary action lives here |
| running | ● | `--info`, pulsing | job streaming |
| review | ✓ | `--ok` outline | produced on disk / job done, **not yet signed** |
| signed | ✓✓ | `--ok` solid | locked.json signed |
| failed | ✗ | `--danger` | last job failed — retry surfaced |

**B. The active-gate panel — the single focused "do this next" surface.** Below the rail, render ONE expanded panel for the **current gate** of the selected scene (per-scene driver). It contains: the gate's **mind credits**, the **one primary action button**, live progress when running, the **review artifacts inline**, and the **Sign off → unlock next** control. Scenes are a compact selector strip at the top of this panel (`Scene 1 ✓✓ · Scene 2 ● · Scene 3 ▷`) so multi-scene stays one click away but the focus is always a single gate of a single scene.

### 2.2 The single primary action, always surfaced

At any moment the active-gate panel shows exactly one bright primary button driven by `gatePhase`:
- **ready** → `▶ Fire Gate N — {mind-led verb}` (e.g. "Run the Director", "Build the keyframes")
- **running** → `■ Stop` + live step + streaming log (reuse existing markup)
- **review** → `✓ Sign off Gate N →` (bright green) with the review artifacts above it
- **signed** → collapses to `✓✓ signed`, and the panel **auto-advances** to the next gate (see 2.4)
- **failed** → `↻ Retry Gate N` (re-fires) + `Clear` (drops the failed job from view)

No `window.confirm`, no blocking `alert`. Firing flips the panel to running inline; an unobtrusive inline note replaces the alert. (Keep one lightweight confirm only for **destructive** actions: Unsign, and Re-fire over a signed gate.)

### 2.3 What the user SEES at each gate, one scene start-to-finish

**GATE 1 — Director plan** (mind row: *Docter · Lasseter · Lin · Kalache*).
- Ready: panel says "Gate 1 reads the script and breaks the episode into beats." One button `▶ Run the Director`. Fire → running, live step ("Director — beat map…"), streaming log, Stop.
- Review: on done, the **beat list** renders inline as compact rows — each beat shows `beatCode · pillar · Xs`, the **want vs need contradiction** (`want` struck-through-ish above `need` highlighted), the `crystalTruth` with its read enum as a coloured chip (`steady/flicker/dim/brightening/steady-warm-but-changed`), a dual **kid-read / adult-read** two-liner, and a `◈ wordless-held` badge on the single nadir beat. Click a beat → `openShot` (now shows + the editor edits these 7 fields). Below: `✓ Sign off Gate 1 →`.
- Sign off → rail node 1 flips ✓✓, connector 1→2 fills, panel slides to Gate 2.

**GATE 2 — DP keyframes** (mind row: *Eggleston · Jessup · Keane*). **The split is made visible as a 2-step sub-progress inside the one panel** (no more split-brain):
- Step 1 · Foundation (2a): the **scene plate** (16:9) + each character's **locked identity sheet** (turnaround) with a 🔒 immutable badge. Button `▶ Build foundation` (or Upload / Library). On done → `✓ Sign off foundation`.
- Step 2 · Keyframes (2b), dimmed until 2a signed: `▶ Build the keyframes`, live per-beat % bar (reuse `sceneAnchors` log-regex), then the **per-beat keyframe grid** with, on each card, a **QA verdict pill** (`✓ PASS` / `⚠ 2 notes` / `✗ FAIL`) from the new QA endpoint, click-through to the openShot modal showing the assembled prompt + ref count + the QA checklist. On done → `✓ Sign off keyframes →`.
- The rail's Gate 2 node shows a half-fill when 2a is signed but 2b isn't (review of the in-between state). Signing 2b flips node 2 to ✓✓ and advances to Gate 3.

**GATE 3 — Camera clips** (mind row: *Lasseter · Dohrn · Docter · Brumm · Romano*).
- Ready: `▶ Animate the keyframes`. Running: live step ("Rendering beat … take…"), Stop. Review: the **stitched scene video** (`sceneComplete`, app.html:605) + per-beat clip thumbnails with play. `✓ Sign off clips →`.

**GATE 4 — Post** (mind row: *Murch · Nolting · Myers · Bush · Giacchino*).
- Ready: `▶ Mix & stitch`. Review: the **final mix** video (reuse `renderPost` markup) inline. `✓✓ Sign off — episode complete`. On sign, the rail shows all-green and a celebratory "Episode signed off" state.

### 2.4 Sign-off animates and advances

`approveGate`/`signSub` already return fresh `locked`. After setting `PIPE.locked`, the new flow:
1. animate the just-signed rail node to ✓✓ and **fill the connector** to the next node (CSS transition on width/colour),
2. compute the next unlocked gate, **scroll/slide** the active-gate panel to it, and **pulse its Fire button once** (a `.justUnlocked` class, 1.2s glow),
3. toast `Gate N signed → Gate N+1 unlocked` with a "Fire it" action that fires immediately.

This is the literal "sign it off, the next unlocks, press the button" loop.

---

## 3. CHANGES (prioritized, concrete)

### P0 — the core flow spine (must-have)

**P0-1. Make Pipeline the landing + spine.**
- `openEpisode` (app.html:459-465): change `page="script"` → `page="pipeline"`.
- `NAV` (app.html:104): move `["pipeline","Pipeline","⚙"]` to first, relabel `"Gate flow"`. Keep Script/Storyboard/Keyframes/Animation/Post as the **review tabs** the gates deep-link into.

**P0-2. Add `gatePhase(sn,g)` — single state source.** New function near `gateProduced` (app.html:803). Returns one of `locked|ready|running|review|signed|failed` by combining `gateState(sn)` (app.html:609), `jobFor(sn,g)` (app.html:745), and `gateProduced(sn,g)`. For g==2 it returns a sub-object `{p2a, p2b}` so the rail can render the half state. Centralizes the logic currently smeared across app.html:849-853.

**P0-3. `renderGateRail(scene)` — the sticky stepper.** New function; call it at the top of `renderPipeline` (app.html:819). Markup: a flex row of 4 nodes + 3 connectors, each node `{glyph, GATE n, name, desc, phase-colour}` from `GATE_DEF` (app.html:743) + `gatePhase`. Add CSS: `.gnode`, `.gnode.active{box-shadow + pulse}`, `.gconn` (connector), `.gconn.fill{background:var(--brand)}`, and `@keyframes justUnlocked`. Use existing `--ok/--info/--brand/--hint` vars; add `--danger:#c0392b` if not present.

**P0-4. `renderActiveGate(scene)` — the one focused panel.** New function replacing the per-scene 4-card wall loop in `renderPipeline` (app.html:843-874). For the selected scene + its current gate:
- mind row from `GATE_DEF[g-1][3]`,
- the single primary button per `gatePhase` (see 2.2),
- reuse the **existing live bar + log markup** verbatim (app.html:867-871) for running,
- for review, call a per-gate artifact renderer (P0-6),
- the `✓ Sign off Gate N →` button calling `approveGate`.
Keep a compact `renderSceneStrip()` selector above it (scene chips with their rail-state glyph; click sets a module var `CURSCENE` and re-renders). Default `CURSCENE` = first scene whose top gate isn't signed.

**P0-5. Surface Gate 2's two steps in the panel (kill split-brain).** Inside `renderActiveGate` when g==2, render the **2a then 2b sub-stepper** (lift the ladder logic from `sceneAnchors` app.html:654-679: plate + locked sheets + Build/Sign 2a → Build/Sign 2b with the live % bar). Reuse `fireSub`/`signSub`/`unsignSub` (app.html:682-694) unchanged. The standalone `sceneAnchors` block on the Keyframes tab stays as the deep-dive review surface; the Pipeline panel becomes the driver. This removes the `gate==2` redirect ambiguity by making both halves explicit where Julian presses.

**P0-6. Inline review artifacts per gate** (`gateArtifacts(sn,g)`): g1 → beat list (P0-9); g2 → plate + keyframe grid (`kfCard`, app.html:594) with QA pills (P0-10); g3 → `sceneComplete` (app.html:605) + clip thumbs; g4 → final-mix video (lift from `renderPost`, app.html:736). These render **above** the Sign-off button so review precedes sign-off.

**P0-7. Sign-off → animate + auto-advance.** In `approveGate` (app.html:795) and `signSub` (app.html:688) success branches: after `PIPE.locked=j.locked`, call new `advanceAfterSignoff(sn, signedGate)` that adds `.justUnlocked` to the next node, re-renders `renderPipeline`, scrolls the active panel into view, and toasts "Gate N signed → fire Gate N+1" with a fire action. Replace the bare `render()`/`renderPipeline()` calls there.

**P0-8. Kill blocking modals.** `fireGate` (app.html:782-794): drop `confirm` for the ready→fire path (keep confirm only when re-firing a `signed`/`review` gate). `fireSub` (app.html:686): delete the `alert("Building…")`; the running panel is the feedback. Replace "Error" `alert`s in fire paths with an inline red note in the panel.

**P0-9. North-Star beat fields — wire through (Gate-1 review).** Purely additive; backend already persists them.
- `normBeat` (app.html:110-121): in the `Object.assign`, pass through `want,need,crystalTruth,kidRead,adultRead,theGame,wordlessHeld` (they already survive via spread, but add explicit keys so legacy shot-shaped beats don't break and to document them).
- `openShot` (app.html:912-922, beats branch): add a "North-Star" block — want (muted) → need (bold), `crystalTruth` with the read-enum chip, kid-read / adult-read, theGame, and a `◈ wordless-held` callout when set.
- `editBeat` `EB.f` build (app.html:957-964): add the 7 keys.
- `renderBeatEditor` (app.html:983): add a "North-Star · the beat's soul" fieldset with inputs (read enum as a `<select>`).
- `ebSave` `updates` (app.html:1024): add the 7 keys (+ nested-safe). No serve.py change.
- `card`/`kfCard` (app.html:580/594): add a small `crystalTruth` read-chip + `◈` wordless badge for at-a-glance.

**P0-10. Keyframe QA verdict — surface it (Gate-2 review).** New serve.py GET `/api/qa?scene=&package=&episode=` that shells `cb_qa.check_done_frame` (or the existing scene QA the pipeline already calls) and returns `{beatCode: {verdict:"pass|notes|fail", checks:[{name,ok,msg}]}}`. Model it on `/api/keyframe-prompt` (serve.py:376-390) / `/api/continuity` (serve.py:267). Front-end: `kfCard` (app.html:594) gains a QA pill from a `QA` map fetched after keyframes finish; `openShot` keyframe branch (app.html:921) renders the per-frame checklist beneath the assembled prompt. This makes "the machine is the QA" visible at the exact sign-off point.

**P0-11. Fix the Ep1 server hardcode.** `_scene_locks` (serve.py:230-231): thread an `episode` param through `/api/fire`, `/api/regen`, and `_gate_ready` (serve.py:232) and read `locked_state().get(episode, {})` instead of literal `"Ep1"`. Front-end `fireGate`/`fireSub`/`regenShot` POST `episode:"Ep"+CUR.number`. Restores defense-in-depth for multi-episode.

### P1 — clarity polish

**P1-1. Contrast for ready vs locked.** In the rail and panel, `ready` = solid brand (bright, obviously actionable); `locked` = dimmed grey with 🔒. Currently both grey (app.html:852).
**P1-2. "Why is this locked" hint on the spine.** When a gate is locked, the panel shows "Sign off Gate {n-1} first →" (the hint currently only lives in `sceneAnchors`, app.html:679).
**P1-3. Episode roll-up line** under the rail: "All scenes through Gate 2 · 1 scene at Gate 3 — next: fire Gate 3 on Scene 2." Computed from `gatePhase` across scenes.
**P1-4. Inline failed→retry.** In the panel, `failed` phase shows `↻ Retry` + `Clear` (drop the job id from a client-side hidden set so it stops being "latest"). Currently failed just relabels Fire (app.html:861).
**P1-5. Mind row styling.** Promote `GATE_DEF[g-1][3]` minds from the tiny 8.5px line (app.html:858) to a proper credit row in the active panel ("Built to the minds of: …").

### P2 — nice-to-have

**P2-1. SSE for live step** (replace 3s poll, app.html:1037 / serve.py:266) — stream `job["step"]` so the last pre-completion line isn't missed.
**P2-2. Job persistence** — write `JOBS` to a small json on exit so a server restart keeps log history (serve.py:104).
**P2-3. Stale-job timeout** — heartbeat in `_stream` (serve.py:157) flips `running`→`failed` after N minutes of no output.
**P2-4. Per-beat keyframe sign-off** — mark individual beats good/needs-work before the whole-scene 2b lock (currently all-or-nothing, app.html:688).
**P2-5. `/api/next`** endpoint encapsulating "fire the next unlocked gate" so the order isn't only client-encoded (serve.py).

---

## 4. PRESERVE / RISKS

**Must not break:**
- **The STOP mechanism** — process-group SIGKILL (`stop_job`/`stop_all`, serve.py:195-214) and all three stop scopes (`stopFiring`, app.html:810). Reuse the existing live-bar Stop markup verbatim; do not refactor the kill path.
- **Live job streaming** — `_stream`/`_humanise`/`JOBS` (serve.py:126-189), `refreshPipe` poll + done-diff + toast (app.html:759-772), the 3s timer (app.html:1037). The new rail/panel must read the same `PIPE` state; don't change the job schema (P2-2 only adds a sidecar).
- **Sign-off gating / `locked.json`** — `GATE_SEQ` and the 3-layer guard (UI `fireable` app.html:849; HTTP `_gate_ready` serve.py:232; pipeline guard). New `gatePhase` must produce identical fire-eligibility; the P0-11 episode fix must keep returning 409 for unsigned previous gates.
- **The 2a/2b internal split** — `fireSub`/`signSub`/`unsignSub` and the `gate==2 → 2a-then-2b` routing (app.html:783,796,847). Surfacing the steps (P0-5) must not change which endpoint each press hits.
- **Reference-first / immutable foundation** — the locked turnaround sheets (`charTurnURL`, app.html:620) and the assembled keyframe prompt (`/api/keyframe-prompt`, serve.py:376). The QA work (P0-10) is read-only; never let the QA panel mutate the keyframe.
- **Reversibility** — every Unsign clears downstream (`unapprove`, cb_pipeline). The animated advance (P0-7) must not auto-sign anything; advance only moves focus.

**Risks to watch:**
- **`gateProduced` vs `JOBS` after restart** (app.html:803) — `review` phase must fall back to disk artifacts when the in-memory job is gone, else a restart hides a done gate.
- **North-Star round-trip** — `ebSave` must send the 7 keys with the same nested-merge contract `/api/beat-update` expects (serve.py:503-509); missing keys are fine (merge skips empties) but malformed nesting could clobber — keep them scalar/string.
- **Single-threaded server** — synchronous `/api/qa` (P0-10) and `/api/continuity` block `/api/pipeline` polling (no ThreadingMixIn). Add a `timeout` like `continuity_state` (serve.py:121) and fetch QA only after a keyframe job finishes, never on every poll.
- **Episode param threading** (P0-11) must reach *all* call sites (`fire`, `regen`, both guards) or the guard silently passes again.

---

**Build order:** P0-2 (`gatePhase`) → P0-3/P0-4/P0-5 (rail + active panel + Gate-2 steps) → P0-1 (landing) → P0-7/P0-8 (advance + de-modal) → P0-9 (North-Star) → P0-11 (Ep fix) → P0-6/P0-10 (review artifacts + QA). P0-2 through P0-5 are the load-bearing spine; everything else hangs off `gatePhase`.

Key files: `/Users/julianjenkins/Desktop/8Th Hour/cb-studio/app.html` (gate UI), `/Users/julianjenkins/Desktop/8Th Hour/cb-studio/serve.py` (endpoints + guards), beat fields authored in `/Users/julianjenkins/Desktop/8Th Hour/cb-gen/cb_director.py:240-244`.