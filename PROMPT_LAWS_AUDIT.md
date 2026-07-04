# PROMPT LAWS AUDIT — Layer 1 (the invariant skeleton) vs the actual emitter code

Commissioned by CLAUDE.md rule 28 (Julian, 2026-07-04): "a law that lives in a document can be forgotten; a law
that lives in the emitter cannot." This audits each of the twelve Layer-1 laws against the CURRENT code —
`engine/cb_segprompt.py` (the emitter), `engine/cb_beats.py` (the fire path), `engine/cb_scene.py` (relay/harvest/
re-mint), `engine/cb_qa.py` (join/re-mint checks) — and states CODE-ENFORCED vs CONVENTION-ONLY for each, with a
proposal for every gap. **Report only — no code changed by this pass.**

Verdict key: **CODE-ENFORCED** = mechanically guaranteed, cannot be produced wrong by a data/authoring mistake.
**CONVENTION-ONLY** = correct today only because someone (director data, past authoring) wrote it correctly;
nothing in the code would catch a violation. **PARTIAL** = enforced for part of the claim, not all of it.

---

### Law 1 — One beat, one prompt, one gag arc; 15s hard-locked (~13 action + 2 settle)

- **The 15s split: CODE-ENFORCED.** `HANDLE_TOTAL/HANDLE_ACTION/HANDLE_SETTLE` (`cb_segprompt.py:349-351`) are
  fixed constants; `_v3_shots` (`:359-400`) allocates `HANDLE_ACTION` across shots by weight and always adds
  `HANDLE_SETTLE` to the last shot — shot seconds mechanically sum to 15 every time, no data path can produce a
  different total.
- **"One gag arc, never two in one take": CONVENTION-ONLY.** Nothing counts setup/payoff cycles in a beat's
  `cuts[]`. This is SCENE1_DIRECTORS_CUT.md's staging law 3, enforced only as instruction text in `cb_director.py`'s
  system prompt at beat-authoring time — a human or the Director LLM writing two arcs into one beat's `cuts` would
  ship cleanly.
  - *Proposal:* a report-only QA check (LLM-graded, per rule 17's concrete-criteria discipline: "does this beat's
    action text contain TWO distinct complete setup→payoff cycles, or one?") run at Gate-1/authoring time, not
    Gate-3 fire time — narrative-arc counting is a judgment call, not a value to hard-block on, but it should
    surface before a beat is locked, the same way ACTION_STATE_MISMATCH surfaces a keyframe problem before sign-off.

### Law 2 — Opener vs relay, no exceptions, no pre-relay keyframes

- **CODE-ENFORCED.** `cb_scene.relay_source_for()` (`cb_scene.py:192-224`) is the single resolver; every render
  call site uses it and only it: `cb_beats.run` (`:215`), `gate3_dryrun` (`:110`), `render_readiness` (`:162`),
  `fire_next_beat`'s dry-run preview (`:474`). No call site branches on anything else.
- **Minor, non-correctness gap:** nothing PREVENTS a stray Gate-2b keyframe generation for a beat 2+ (e.g. via the
  UI's per-beat "build keyframe" action) even though the relay path would ignore it once a predecessor clip exists.
  Wasted image-gen cost, not a wrong render — `relay_source_for`'s "relay" status doesn't check whether this beat
  also has its own keyframe file; it just doesn't route through it.
  - *Proposal:* low priority. If worth closing, gate the per-beat keyframe-build UI action itself on
    `relay_source_for` returning anything other than `"first"`.

### Law 3 — The five-anchor stack, every relay prompt, each with one declared job

- **The prompt TEXT: CODE-ENFORCED.** `emit_json_v3`/`_v3_environment` (`:698-721`, `:472-507`) unconditionally
  write the @图1 / @Video1 / turnaround / plate / @Audio1 declarations whenever `relay=True` — the wording can't
  be skipped by beat data.
- **The actual upload matching that text: CONVENTION-ONLY — a confirmed, currently-live gap.** `cb_beats.run`
  builds the uploaded image list as
  `imgs = [start] + [a for c in _chars if (a := _anchor(c))]` (`cb_beats.py:295`) — `_anchor()` returns `None`
  and is **silently filtered out** for any character whose turnaround file doesn't exist (`:27-33`). But the
  prompt's reference labels come from `emit_json_v3`'s own loop over the SAME `cast` list
  (`for i, name in enumerate(cast): refs[f"@图{i+2}"] = ...`, `cb_segprompt.py:713-716`) with **no existence
  check at all**. If any one character in `openingCast` is missing its turnaround file, `imgs` gets shorter than
  the label set assumes and every later slot — the scene plate especially — shifts one position left of what the
  prompt text claims it is. This is exactly the class of bug rule 11 (sweep-the-pattern) exists to catch, and nothing
  currently sweeps it.
  - *Proposal:* assert `len(imgs) == len(cast) + 1 (+1 if relay for the plate)` in `cb_beats.run` right before
    `generate_video_seedance_ref` fires, and refuse the render (loud, same style as the Law 5 voice-refusal) if a
    named character has no resolvable anchor — never silently ship a shifted reference stack.
- **@Video1 specifically: PARTIAL, currently coupled but not by a shared invariant.** `relay_status == "relay"` is
  only returned once `harvest_settle_frame` (or an existing re-mint) has confirmed the predecessor's clip exists
  (`cb_scene.py:219-224`), so in practice the clip is present when `cb_beats.run` re-checks
  `os.path.exists(_prev_clip)` moments later (`:314`) to build `vids`. But it's two independent `os.path.exists`
  checks, not one shared fact — if a clip is ever moved/archived between the two checks, or if `relay_source_for`'s
  definition of "ready" ever changes to not require a live clip, the @Video1 declaration would still appear in the
  prompt text with nothing actually uploaded at that slot.
  - *Proposal:* have `relay_source_for` return the resolved clip path alongside the frame path/status, and have
    `cb_beats.run`/`fire_next_beat` consume that same value for `vids` instead of re-deriving and re-checking it.

### Law 4 — @图1 description is a photograph, not a story (no temporal verbs/imperatives)

- **PARTIAL, and knowingly so.** The boilerplate job-declaration ("this image IS the first frame... nothing
  composed fresh...") is CODE-ENFORCED fixed text. The CONTENT clause is `_v3_prev_frame_content` reading the
  predecessor's `endStateStill` field verbatim (`cb_segprompt.py:433-457`) — CLAUDE.md rule 27 already
  explicitly rejected an automatic mechanical transform of `endState` into this static form ("genuine rewriting a
  regex strip could not reproduce reliably or safely"), so this is a **deliberately accepted** convention-only
  gap: it relies on whoever authors `endStateStill` to have already stripped every temporal verb and imperative.
  Nothing currently re-checks that they did.
  - *Proposal:* since a mechanical FIX was already ruled out, add a mechanical DETECTOR instead — a cheap,
    deterministic (no vision call needed) regex/keyword check on `endStateStill` for temporal verbs and
    imperatives ("holds", "ends on", "resumes", "begins to", "straightens into and...") run at beat-authoring
    time / before Gate 3 fires, in the same spirit as rule 17's concrete-criteria QA. It can't fix the prose, but
    it can refuse to ship it un-reviewed — closing exactly the gap that produced rule 27's bug in the first place,
    without re-attempting the rewrite Julian already rejected.

### Law 5 — Anti-hold: frame one IS @图1, then motion moves decisively away, never held/repeated/returned to

- **The instruction: CODE-ENFORCED.** `_RELAY_OPEN_LOCK` (`cb_segprompt.py:353-357`) is fixed text prepended to
  shot 1's own action every time `relay=True`, plus the same anti-hold clause repeated in the @图1 reference
  declaration (`:474-479` / `:700-706`). Two independent, code-guaranteed placements of the same instruction.
- **Whether the render actually complies: NOT CODE-ENFORCED, and can't be** — this is inherently a generation-time
  outcome, not a structural property of the prompt. It IS caught after the fact, advisory-only, by
  `cb_qa.check_join` (`cb_qa.py:103-127`, POSITION/STATE/LIGHT vs the previous settle) — which is exactly why the
  just-completed 1.B2 re-fire's join check (`BROKEN — POSITION: the bees are suddenly much farther away...`) is
  doing its designed job, not a code gap. No proposal beyond what rule 27 already did; this is the correct
  division of labour (code states the law twice; QA catches violations; a human judges the report).

### Law 6 — Audio law: all vocal sound is the V3 performance in @Audio1; prompt never contains the spoken words

- **CODE-ENFORCED, with an actual regex safety net, not just an instruction.** `dlg["line"]` is always the fixed
  string `"the line in @Audio1 during this shot"` (`cb_segprompt.py:729`), never the real words. `_strip_spoken_words`
  (`:178-196`) is run over every free-text field (action, camera, atmosphere, tone) and mechanically removes any
  quoted span, so even an authoring mistake that pastes a line of dialogue into an action field gets stripped
  before it reaches the prompt. This is the strongest-enforced law in the set — no gap found.

### Law 7 — Ambience is scene-property, locked, identical every clip in the scene; never in any other field

- **"Identical every clip": CODE-ENFORCED.** `_v3_ambience(scene)` (`cb_segprompt.py:510-518`) is a pure function
  of the scene dict's own `ambientBed` field — every beat in the same scene gets the byte-identical string, by
  construction.
- **"Never appears inside any other field": CONVENTION-ONLY — a live gap, same class as the bug rule 27 already
  found once (there it was `endState` restating `ambience`; here it's the same risk in a different field pair).**
  `_v3_environment`'s `atmo` clause (`:500-503`) takes the FIRST sentence of the beat's own authored `atmosphere`
  field verbatim, with no check against the scene's `ambientBed` text for overlap/duplication. A director
  authoring `atmosphere` in language that restates the locked ambient bed (an easy mistake — both describe the
  same meadow/breeze) would ship a duplicate with nothing to catch it.
  - *Proposal:* a cheap deterministic check — token-overlap or substring similarity between the beat's `atmosphere`
    first sentence and the scene's `ambientBed` — flagged (not blocked) at authoring time, mirroring how rule 27's
    bug was actually found (by reading a shipped prompt and noticing the restatement).

### Law 8 — Camera law: locked during any vocal beat; motion only in non-speaking action; one primary move per shot

- **The beat-level statement: CODE-ENFORCED.** `_v3_rule` (`cb_segprompt.py:619-636`) appends "Camera holds static
  and locked during any shot with dialogue" whenever any cut in the beat has dialogue — mechanical, can't be
  skipped.
- **Per-shot enforcement against that statement: CONVENTION-ONLY.** Each shot's own `camera` text comes straight
  from the cut's authored `framing` field (`_v3_shots`, `:379`) with no check that a dialogue shot's `framing`
  doesn't itself contain camera-movement language (e.g. "pushes in", "pans") that would contradict the beat-level
  rule line right next to it — two statements in the same prompt that could disagree, same shape as the
  temporal-contradiction bug in Law 4. "One primary camera move per shot" is likewise never counted or verified
  anywhere.
  - *Proposal:* a lightweight keyword check (push/pan/dolly/truck/zoom/orbit/whip, etc.) on any dialogue-bearing
    shot's `framing` text, flagged at authoring time — same pattern as the ambience-overlap check above; and a
    second check counting camera-movement keywords per shot, flagging (not blocking) more than one.

### Law 9 — The living settle: every clip ends at rest, idle life continuing, nothing frozen, nothing new

- **CODE-ENFORCED for presence.** `_v3_settle` (`cb_segprompt.py:402-412`) unconditionally appends a settle block
  to the closing shot — the universal idle-life guarantee (wings/breeze/pollen/held expressions/camera locked)
  fires even before a beat has an authored `endState`, so a settle block can never be silently absent.
- **Whether the ACTUAL render complies ("nothing new happens"): not code-enforceable**, verified only
  after the fact, advisory, by `check_join`'s STATE criterion and `cb_qa.check_clip`'s CLIP_FROZEN/floaty checks.
  Correct division of labour, same as Law 5 — no proposal.

### Law 10 — The six negatives, every prompt, in full (Crystal World Rule + Wing Law included)

- **CODE-ENFORCED for the TEXT.** `_v3_negatives(any_bee)` (`cb_segprompt.py:534-541`) returns a fixed list —
  4 universal + 2 species-swapped, `core[:6]` — always exactly six, always present in both emitters' output.
  Can't be produced with five or seven, can't omit the Crystal World Rule or Wing Law phrasing for a bee cast.
- **Whether the RENDER actually honours them: PARTIAL by deliberate design, not a gap.** Only two of the six have
  a hard QA BLOCK on the clip (`BEE_WITH_CRYSTAL`, in `CLIP_BLOCK_CODES`, `cb_qa.py:216-218`); the others
  (on-screen text, morphing/rescale, flicker, continuity-break) are advisory NOTE-only for a clip frame
  (`CLIP_SAFE_CODES`, `:209-211`, not all mirrored into `CLIP_BLOCK_CODES`). This looks like a deliberate,
  documented anti-false-positive choice (the same rationale ANATOMY_DEFECT gets, `:219-220`), not an oversight —
  flagging for awareness, not proposing a change without Julian confirming that's still the intended balance.

### Law 11 — Character law: identity by reference only; binding handles neutral; personality only in action prose

- **CODE-ENFORCED for the binding handle itself.** `_v3_subjects`/`emit_json_v3`'s ref labels use `_short_role`
  (size + species only, e.g. "the larger bee") — personality adjectives are structurally excluded from that one
  field (`cb_segprompt.py:414-431`, `:713-716`), confirmed by rule 25's fix.
- **Whether the SAME image actually shows the identity referenced: see Law 3's confirmed gap above** — the
  turnaround-filter/label-list mismatch is this law's real exposure, not a separate finding; cross-referenced
  here rather than duplicated.

### Law 12 — Style law and world text: verbatim from show profile/scene data, never retyped or paraphrased

- **CODE-ENFORCED.** `_v3_style()` returns `STYLE_LAW`, loaded once from `laws/style.txt`, returned byte-for-byte
  (`cb_segprompt.py:520-521`). World/location text comes from `scene.get("definingFeature"/"location")` with only
  a mechanical capitalization touch-up, never an LLM paraphrase step (`:489-498`). No gap found — this is the
  cleanest law in the set, by construction (there is no rewriting step to introduce drift).

---

## Summary table

| # | Law | Verdict |
|---|-----|---------|
| 1 | One beat/one arc, 15s split | Duration split CODE-ENFORCED; "one gag arc" CONVENTION-ONLY |
| 2 | Opener vs relay | CODE-ENFORCED (minor stray-keyframe waste only) |
| 3 | Five-anchor stack | Text CODE-ENFORCED; **upload-matches-text is CONVENTION-ONLY — confirmed live gap** |
| 4 | @图1 is a photograph | Boilerplate CODE-ENFORCED; content clause CONVENTION-ONLY (deliberate, per rule 27) |
| 5 | Anti-hold | Instruction CODE-ENFORCED (doubled); compliance verified only by advisory QA (correct split) |
| 6 | Audio law / no spoken words | CODE-ENFORCED with an active regex safety net — strongest law in the set |
| 7 | Ambience scene-property | "Identical every clip" CODE-ENFORCED; **"never restated elsewhere" CONVENTION-ONLY — live gap, same class as a bug already found once** |
| 8 | Camera law | Beat-level statement CODE-ENFORCED; **per-shot compliance CONVENTION-ONLY — live gap** |
| 9 | Living settle | Presence CODE-ENFORCED; render compliance advisory QA only (correct split) |
| 10 | Six negatives | Text CODE-ENFORCED (exactly six, always); render-side enforcement deliberately partial (2/6 hard-blocked) |
| 11 | Character law / neutral handles | Binding handle CODE-ENFORCED; identity-match exposure = Law 3's gap |
| 12 | Style/world text verbatim | CODE-ENFORCED — no gap |

**Net: 12/12 laws are stated in code without exception. Four concrete, currently-live gaps found** (Law 3's
upload/label mismatch, Law 4's un-detected temporal-verb leakage, Law 7's ambience-restatement risk, Law 8's
per-shot camera-movement risk) — each proposed above as either an assertion (fail loud before firing) or a cheap
report-only check (flag before firing), none requiring a re-attempt of the mechanical-rewrite approach Julian
already rejected for Law 4. No code has been changed. Awaiting sign-off on which gaps to close and in what order.
