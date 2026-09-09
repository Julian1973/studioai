# Studio AI: Creative Production Build

## Status and intent

This is the implementation brief for a **software-wide creative-production upgrade**. It describes the target behaviour of Studio AI; it does **not** claim that all functionality is already implemented, qualified, or ready for normal production generation.

The objective is to turn an **approved screenplay** into deliberately staged, convincingly acted, emotionally readable, visually coherent family animation—and to carry the same dramatic intention through images, approved audio, animation, editing, and final review.

**Writing is outside this build.** Production begins from an approved screenplay. Studio must preserve that screenplay and its approved dialogue while improving direction, staging, performance, cinematography, editing, sound, continuity, and delivery evidence.

Exceptional storytelling is the ambition. Actual generated scenes, assembled cuts, and human audience response establish whether a result succeeds.

---

## 1. Four creative outcomes

The build is judged by visible improvement in these four outcomes. Architecture, data models, prompts, tests, and workflow changes exist to serve them; they do not replace them.

### 1.1 Cinematic language and continuity

Studio must create purposeful scene coverage, camera placement, camera movement or deliberate stillness, readable geography, eyelines, screen direction, pacing, and editorial cuts.

A scene should feel directed rather than like a collection of attractive clips, centre-framed keyframes, generic truck-ins, decorative dissolves, or long takes that exist only because a generation unit is long.

### 1.2 Acting and character performance

Studio must create thought-led, character-specific performance for speaking and listening characters: intention, attention, pose, gesture, expression, reaction, timing, physicality, weight, contact, walking, restraint, and purposeful stillness.

Characters must not default to vacant forward stares, neutral standing poses, generic lip-sync, simultaneous mechanical movement, or floating physical action.

### 1.3 Dialogue and vocal performance

Studio must not rewrite, substitute, extend, shorten, or otherwise alter approved screenplay dialogue or approved spoken performance.

Approved dialogue is both a lip-sync source and a performance source. Expression, gaze, body acting, listener reaction, camera treatment, pauses, sound, and cut timing must match the approved words, meaning, rhythm, and delivery.

### 1.4 Physical, visual, and effects continuity

Studio must preserve meaningful cause-based character, prop, effect, environmental, sound, and physical states across relevant shots.

Examples include:

- A launched berry leaves an empty cup.
- A stolen honeycomb piece leaves a visible missing section.
- A stain, berry mark, pollen, wetness, mud, or damage persists until a visible or declared cause removes it.
- A transferred prop changes owner.
- Water, impacts, collisions, smoke, magic, debris, and physical forces produce a readable consequence.
- Characters, props, effects, and locations do not teleport or reset between contiguous shots.

---

## 2. Build on the existing Studio system

Retain and extend the current production architecture wherever possible:

- Shared Director Cards and scene-coverage records.
- Existing screenplay, character canon, prop canon, location, asset, audio, version, lineage, approval, spending, and recovery records.
- Exact dialogue and approved-audio protection.
- SEE, HEAR, WATCH-request, WATCH-result, post, dailies, and finishing workflow.
- Scoped corrections that preserve unaffected approved work.
- Actual-media review and finishing workflow.
- Existing request evidence, reference binding, production, transport, and review infrastructure.

Do **not** create competing department documents, shadow canon, duplicate source-of-truth records, or a new user-managed approval maze.

The Director Card and shared scene/shot records must **reference** authoritative records. They must not copy and then silently stale the approved screenplay, canon, asset, audio, or approval data.

---

## 3. Creative authority model

Studio must operate as a **directing system, not a restriction engine**.

It must protect approved truth while allowing specific creative direction to produce comedy, emotional subtlety, surprise, offscreen sound, purposeful silence, camera holds, expressive action, reactions, and cinematic cuts.

### 3.1 Instruction classes

Every instruction considered by the compiler must be classified internally as one of:

| Class | Meaning | Behaviour |
|---|---|---|
| `hard_truth` | Immutable approved audio, identity/canon, current approved story state, critical continuity, legal/safety, provider validity | Cannot be silently overridden |
| `creative_direction` | Current approved dramatic intention: acting, camera, comedy, emotion, sound, cut, hold, focus, staging, surprise | Highest normal creative authority |
| `contextual_guardrail` | Scene/shot-specific continuity or feasibility protection | Applies only to its declared scope |
| `default_behaviour` | Useful fallback when nothing more specific is directed | Suppress automatically when irrelevant or superseded |
| `historic_residue` | Stale inherited instruction or duplicate | Never emit |
| `provider_syntax` | Required provider formatting or setting | Keep minimal and traceable |

### 3.2 Precedence

Resolve instructions in this order:

```text
1. Safety, legal constraints, immutable approved source authority
2. Current approved story facts, identity, essential continuity and audio ownership
3. Specific current creative direction
4. Contextual guardrails
5. Generic defaults
6. Historic/duplicate residue: removed
```

Specific creative direction overrides generic defaults unless it genuinely conflicts with immutable approved audio, identity/canon, safety, explicit physical-continuity conditions, or a provider capability.

### 3.3 Scope

Every relevant instruction must be scoped by as many of these as apply:

- Project, episode, scene, shot, editorial view, or generation block.
- Character and role.
- Visible or offscreen status.
- Speaking, non-speaking, listening, witnessing, or ambient role.
- Time range or dialogue phrase range.
- SEE, HEAR, WATCH, post, review, or provider route.
- Reference role and provider input role.

### 3.4 Replace blanket restrictions

Remove/refactor blanket prompt clauses such as:

```text
All listeners remain still.
All listeners’ mouths remain closed.
All witnesses remain still.
No vocalisation during dialogue.
Nobody moves unless explicitly instructed.
```

Replace them with scoped behaviour:

```text
Visible non-speaking characters must not mouth words assigned to another speaker.

Visible listeners remain attentive and do not perform unrelated distracting action
unless a specific acting or reaction beat directs it.

Offscreen characters receive no visible-mouth, pose, stillness, or listener restriction.

Approved spoken performance remains immutable during generation.

No unapproved generated spoken dialogue may overlap approved spoken performance.

Authorised nonverbal character SFX—laughter, breath, gasp, effort, cry, sigh or
reaction—may occur when the current shared direction defines character, sound type,
time window, dramatic purpose, and provider dependency.

Intentional stillness, a static camera, offscreen sound, silence, a reaction, a cut,
a reframe, an insert, or a long take are valid when the current direction motivates them.
```

### 3.5 Locked, directed, open

Each provider package must distinguish:

```text
LOCKED
Facts that cannot change: approved dialogue, identity, essential geography,
story state, required prop/effect state, safety and provider-validity conditions.

DIRECTED
What the audience must experience: dramatic action, acting beat, camera behaviour,
focus, sound event, comedy/emotional intent, cut/hold, and cause/effect.

OPEN
Permitted creative interpretation: exact micro-expression, subtle gesture, natural
timing texture, small environmental life, non-conflicting secondary detail.
```

`OPEN` must never override `LOCKED` or `DIRECTED`. It exists to prevent unnecessary micromanagement and leave room for artistic life.

---

## 4. Creative team inside Studio

These are defined responsibilities. They do not all require individual model calls. They enrich and resolve into one shared scene plan and one shared set of shot records.

| Role | Responsibility | Required output |
|---|---|---|
| Supervising Director | Own the audience experience; reconcile specialist recommendations | One coherent scene plan and shared shot records |
| Comedy and Emotional Story Review | Examine how approved action creates humour, vulnerability, connection, tension, or release | Specific execution notes tied to existing screenplay beats |
| Storyboard and Editorial Director | Plan visual progression before choosing generation units | Ordered coverage, cut reasons, reaction space, timed rough sequence |
| Production Designer | Preserve show identity and develop scene-specific atmosphere | Scene look, palette, lighting intention, environment references |
| Cinematographer | Decide viewpoint, lens, composition, focus, camera state, movement, and exit | Camera direction for every editorial view |
| Animation Performance Director | Make characters think, listen, move, react, and physically interact distinctly | Playable acting and physical-interaction instructions |
| Voice Director | Interpret exact approved recorded performance into phrase timing, emphasis, pauses, listener response, and animation direction without altering words or audio | Dialogue-performance brief linked to approved audio version and timing |
| Music and Sound Director | Develop sonic continuity, themes, ambience, purposeful silence, and cue ownership | Episode sound plan and scene cue sheets |
| Continuity Supervisor | Protect identity, geography, props, action state, effects, and audiovisual joins | Source-bound opening/closing state and discrepancy reports |
| Editor and Post Supervisor | Judge the assembled scene and finish approved episode | Edit recommendations, finishing candidates, delivery evidence |

The Supervising Director remains accountable. Specialist disagreements return to that role as recommendations. Specialists must not create competing versions of the screenplay or scene story.

---

## 5. Crystal Bears show language

Studio is a general production platform, but Crystal Bears requires a concise **Show Performance and Visual Language Profile** linked to existing approved Crystal Bears canon, references, and approved footage.

This profile is a practical production interpretation of existing authority. It must not duplicate canon, create a competing character bible, or turn moment-specific direction into permanent character law.

### 5.1 Required show-language areas

| Area | Working production purpose |
|---|---|
| Character thought | How each bear visibly processes uncertainty, delight, embarrassment, concern, disappointment, curiosity, courage, and affection |
| Listening behaviour | How characters direct attention and respond while another character speaks |
| Body language | Posture, personal space, touch, weight, pace, and movement through the Nook/world |
| Comedy | How sincere intention creates humour; how a character recovers, doubles down, hides, shares a look, or preserves dignity |
| Family relationships | How closeness, distance, interruption, shared attention, comfort, disagreement, and repair are shown physically |
| Emotional restraint | How a gaze shift, lowered hand, held breath, shoulder release, or delayed response can carry feeling |
| Crystal/Nook visual life | How crystal light, particles, foliage, wind, weather, and foreground life support action without competing with faces or performance |
| Rhythm | Comic pauses, quiet emotional holds, visual breathing space, silence, and transition back into play/adventure |
| Camera language | Relationship framing, observed comedy, nature depth, intimate holds, action tracks, and earned long takes |
| Sound language | How ambience, silence, music bridges, nonverbal SFX, and dialogue space support visual rhythm |

### 5.2 Use examples correctly

The profile must use concise working examples tied to approved canon and footage. Examples guide a shot; they do not create permanent gesture laws.

```text
Approved canon indicates Zenny tends toward composed observation and controlled response.

Shot-specific direction:
Zenny starts to offer the object again, notices the other bear has turned away,
lowers it slightly, remains close, and waits rather than forcing the moment.

Reason:
The audience reads disappointment, care, and restraint before dialogue explains it.
```

The director remains free to create appropriate moment-specific acting choices unless they conflict with established identity, story fact, or physical/design constraints.

---

## 6. Episode interpretation

The director reads the complete approved screenplay before dividing it into production units.

Record:

- Central relationship.
- What the principal character wants.
- What changes through approved events.
- What children need to understand.
- What adults may recognise beneath the action.
- Setups and later payoffs.
- Recurring visual and sound ideas.
- Opening and closing emotional states.
- Important physical cause-and-effect chains.

Remove any requirement for exactly seven transformations, a mandatory low point, trauma, lesson, climax, reconciliation, tears, or uplifting ending.

Support the structure actually present in the screenplay, including:

- Play and escalation.
- Misunderstanding.
- Discovery.
- Quiet observation.
- Small relationship change.
- Adventure and consequence.
- Restraint, ambiguity, incomplete recovery, or unresolved feeling.

Studio must never invent story architecture merely to satisfy a template.

---

## 7. Scene direction and editorial planning

### 7.1 Coverage precedes generation planning

Before generating keyframes, Studio produces a **complete scene coverage board**.

A keyframe establishes an opening state; it does not dictate one camera angle or composition for a whole scene.

A render is a production unit; it is not necessarily one uninterrupted cinematic shot.

Story beats, editorial views/shots, and generation clips remain separate.

```text
Approved scene beat
→ acting and audience understanding
→ coverage: setup, action, reaction, reverse, insert, reveal, payoff
→ camera/cut plan
→ production planner chooses generation units
```

The production planner decides whether a planned view:

- Continues within the current generation clip.
- Belongs in a controlled multi-shot generation block.
- Needs a separately prepared opening keyframe and a distinct generation clip.
- Can be solved using existing approved media in post.
- Should be merged or removed because it repeats information or slows the scene.

Provider-duration limits must not determine story rhythm.

### 7.2 Required coverage fields

Every planned editorial view must identify:

| Field | Purpose |
|---|---|
| View ID | Stable identity across planning, generation, review, and editing |
| Source beat | Approved screenplay event being staged |
| Audience need | What the viewer must understand, notice, anticipate, feel, or discover |
| Viewpoint owner | Character or force whose experience controls the camera |
| Visible action | Physical cause and consequence |
| Performance | What a character visibly does to express intention |
| Listener reaction | Relevant response from other characters |
| Camera instruction | Framing, position, lens, focus, movement/hold, composition and exit |
| Planned duration | Time required for the action and reaction to read |
| Cut reason | Why the next view improves understanding, feeling, pace, or relation |
| Opening state | Continuity entering the view |
| Closing state | Continuity leaving the view |
| Production route | Current clip / multi-shot block / new keyframe + clip / post / reuse / remove |

Every planned view must have an audience need plus a story or performance reason.

Static shots, centred framing, symmetry, simultaneous action, long holds, deliberate stares, silence, and long takes remain valid when they are purposeful. Studio flags unexplained defaults, decorative cuts, repeated near-identical coverage, and camera movement without clear audience purpose.

### 7.3 Timed rough sequence

Allow the scene board to play in editorial order using available storyboard/previs images, approved audio, and clearly labelled timing estimates.

The rough sequence must show selected coverage order, cut points, temporary holds, dialogue/audio ownership, and known missing assets. It must never present a text board as a completed animatic or imply missing picture/audio has been reviewed.

### 7.4 Mechanics-first previs

When a scene contains a material spatial or physical-risk condition, Studio should create a simple mechanics-first staging board or coarse 3D blockout before polished keyframe generation.

Use this for:

- Long-distance projectiles.
- Routes, chases, or multi-zone movement.
- Catapults, ropes, traps, levers, doors, or other mechanisms.
- Collisions and physical comedy.
- Prop transfers across meaningful space.
- Difficult camera paths.
- Previous geometry failures.

The blockout may use primitive shapes, named zones, action routes, basic camera positions, and start/end state. It is an agent-operated optional production tool, not another task the director must manage. Use it as provider input only where the active provider route actually supports it.

---

## 8. Cinematography upgrade

The existing cinematography skill is a positive creative authority. It must enter the working pipeline—not remain only a research document.

For every meaningful editorial view or controlled multi-shot generation block, record:

| Decision | Required direction |
|---|---|
| Dramatic owner | Who owns the camera and why this is the useful viewpoint |
| Emotional action | Hide, test, invite, reject, protect, confess, release, observe, etc. |
| Camera state | Controlled, observational/reactive, flowing, or deliberately still |
| State-change trigger | Time/action/cause that changes camera behaviour; no unexplained state changes |
| Viewpoint | Height, side, distance, obstruction, camera relationship |
| Lens relationship | Intended spatial effect; numerical lens language when useful, never as a quota |
| Composition | Foreground, subject plane, relationship plane, background; silhouette, negative space, eyelines, depth |
| Movement | Static-by-design or rig metaphor, trigger, path, speed curve, finish |
| Focus | Initial owner, motivated transfer/search/miss/recovery, final focus state |
| Light | How value/colour/illumination connects or separates story layers within continuity |
| Cut-in reason | Why this view begins now |
| Exit frame | Final composition/state that supports the next view or edit |

### 8.1 Camera principles

- Choose point of view before lens or movement.
- Every camera movement, hold, cut, reframing, focus change, or deliberate stillness must have a clear audience purpose.
- Movement may reveal information, follow action, sustain identification, establish atmosphere, maintain a relationship, transfer attention, increase intimacy, create comic timing, express a living environment, or land an emotional consequence.
- Acting drives camera. Block emotional action first; let camera accommodate it.
- Focus is attention, not decoration.
- Preserve world-space geography and relationship, not identical screen composition.
- Use foreground life asymmetrically and sparingly; ambient life must not become a theme-park display.
- Reserve long takes for emotional immersion or escalating cause-and-effect, never merely to show technical ambition.
- Assess long-take complexity through readability, available duration, spatial stability, identity stability, and demonstrated provider capability. Do not impose arbitrary focus-transfer quotas.

No compulsory orbits, lens quotas, focus pulls, camera-state transitions, push-ins, or camera movement. A locked shot can be the strongest direction.

### 8.2 Cinematography handoff

The cinematography block must compile into:

- **SEE keyframe contract:** opening composition, staging, depth, viewpoint, lens relationship, focus owner, light, visual relationship, and visible action readiness.
- **WATCH delivery prompt:** camera state, motivated movement/hold, focus behaviour, planned cut/reframe, performance visibility, and final exit composition.
- **Post review:** whether the audience can read the owner, relationship, focus, movement/hold, and exit.

---

## 9. Performance upgrade

Camera and performance must be planned together.

For each featured character, direct only the phases relevant to the beat:

```text
Intention → attention → impulse → hesitation or decision → action → consequence → recovery
```

This is a vocabulary for readable acting, not a compulsory formula. A valid beat may be restraint, meditation, sleep, quiet listening, a held look, shock, partial reaction, or unresolved emotion.

Direct:

- What the character wants, avoids, protects, hides, or decides.
- What they see, hear, feel, remember, or attend to.
- The thought/change the audience should read.
- The visible behaviour that expresses it: gaze, expression, posture, breath, gesture, weight shift, action, reaction, restraint, or stillness.
- Start pose and end/settle pose.
- Character-specific physical behaviour informed by approved identity/personality, while allowing the director to invent moment-appropriate local gestures.
- Weight, balance, contact, arcs, follow-through, and physical cause-and-effect where relevant.
- Walk quality where walking occurs.
- The thought continuing after a line ends.

### 9.1 Speaking and listening

Speaking characters need:

- Literal meaning of the approved line.
- Objective/subtext.
- Actual delivery/phrase structure from approved audio.
- Attention target.
- Facial/body performance.
- Timing/pauses/emphasis.
- Post-line state.

Listening characters need:

- What they hear or observe.
- What they infer, resist, or decide.
- Attention target.
- A visible response, restraint, or motivated stillness.
- A reason for remaining in frame or for the camera to cut away.

A character must not become a vacant figure merely because another character is speaking.

### 9.2 Canon and directorial freedom

Canon protects identity, established personality, physical constraints, design, and story facts.

Canon does not require every new gesture, pose, reaction, or piece of local acting to become a permanent approved trait.

```text
Canon says who the character is.
Direction decides how they behave in this moment.
```

Flag only a gesture/choice that contradicts established identity, a story fact, or a physical/design constraint. A new recurring trait may be proposed for canon only after it proves valuable and receives explicit approval.

---

## 10. Dialogue, music, and sound planning

### 10.1 Dialogue and approved audio

Writing is outside this build. Studio does not rewrite, substitute, extend, shorten, or otherwise alter approved screenplay dialogue or approved spoken performance.

After approval:

- Exact spoken words, voice identity, approved recording, speaker assignment, and measured timing remain protected during generation.
- WATCH receives the actual approved audio asset/version and measured phrase timing, not guessed timing.
- Expression, gaze, body acting, listener reaction, camera treatment, pauses, and cut timing must match the words, meaning, rhythm, and delivery.
- If acting cannot fit approved timing, propose a coherent coverage restructure, duration adjustment, or separately authorised retime/new audio version.
- An authorised retime is a separately recorded operation producing a new version. It must not silently alter the approved source asset.

### 10.2 Sound ownership

Distinguish:

- Approved spoken performance.
- Authorised generated character SFX.
- Physical effects.
- Ambience.
- Music.
- Mixed provider soundtrack versus isolated available stems.

A generated laugh, breath, effort sound, or reaction is an **authorised sound-generation instruction** until a real output exists. Do not create an asset reference before a provider returns an asset. If the sound returns only inside a mixed soundtrack, evidence is that returned render and time range—not an imaginary isolated stem.

Changing sound invalidates WATCH only if the WATCH provider/package actually consumes that sound, sound timing, cue, or music as a generation or performance dependency. Post-only sound changes do not automatically invalidate WATCH.

### 10.3 Episode sound plan

Create an episode-level sound plan before individual clips receive music instructions. Include:

- Recurring character or relationship motifs.
- Environmental identity for each location.
- Intended silence.
- Cue entry/exit points.
- Transitions between scenes.
- Dialogue priority.
- Whether each cue belongs in generation or post.

Every cue must distinguish: planned, authorised instruction, available, generated, reviewed, approved, and delivered state.

---

## 11. Continuity, state, and handoffs

### 11.1 Intended versus observed state

Keep these separate at all times:

```text
Intended state:
What the approved screenplay/director says must be true.

Observed state:
What returned image, video, audio, or assembled cut actually shows/hears.

Decision:
Accept, repair, reject, or explicitly revise the story state.
```

A returned image/video must never silently rewrite canon, intended story state, or the assumed truth for later shots.

### 11.2 Track meaningful state only

Track meaningful audience-visible continuity, not every particle.

- Character world position, facing, eyeline, relevant action phase, held props, marks, wetness, damage.
- Prop owner, location, condition, loaded/empty, held/dropped/launched/open/broken/missing/transferred.
- Effects: pollen, berry juice, water, mud, smoke, magic, food, debris, foam, dust.
- Environment: time, weather, lighting, doors, fires, damage, set changes.
- Physics: gravity, collision, trajectory, contact, impact, rebound, balance, cause/effect.
- Sound state: approved dialogue, authorised SFX instructions, provider-supplied timing dependencies.

### 11.3 Contextual handoffs

Use continuity evidence according to story relationship:

| Relationship | Required continuity evidence |
|---|---|
| Same moment / reverse angle | Relevant approved previous ending for dynamic state; scene plate/layout for fixed geography; canon for identity |
| Continuous motion | Relevant approved preceding footage plus state; preserve video as motion evidence where supported |
| Next beat, same location | Prior state plus only explicit permitted change |
| Time jump | New intended state; previous footage is historical evidence only |
| New location | New approved plate/layout and current character canon |
| Independent scene | Its own state and relevant references |
| Flawed/disputed previous ending | Evidence to investigate, never automatic story authority |

New angles preserve world-space geography, identity, eyelines, action phase, prop/effect state, and story time—not old screen position or identical composition.

---

## 12. Director-to-delivery handoff

Studio must not send generic screenplay notes directly to keyframe or animation generation.

For every planned editorial view or controlled multi-shot generation block, compile a versioned **Shot/Scene Delivery Package** from the shared authoritative records.

```text
Approved screenplay and audio
→ shared Director Card and scene plan
→ coverage board and mechanics previs when needed
→ compiled Delivery Package snapshot
→ SEE Keyframe Contract
→ validated keyframe
→ HEAR bindings/cues
→ WATCH Delivery Contract
→ sealed provider request
→ returned media review
→ post/assembled-cut review
```

### 12.1 Delivery Package is a compiled snapshot

The Delivery Package is **not** a second source of truth and is not independently editable story/canon/audio authority.

It is an immutable compiled snapshot of what existing authoritative records specified at a particular revision and what was actually submitted.

```text
Authoritative records change
→ new scene/shot revision
→ new Delivery Package compiled
→ old package preserved as historical submission evidence
```

### 12.2 Delivery Package contents

The snapshot must contain:

- Story beat and audience purpose.
- Coverage plan, selected views, cut reasons, production route.
- Cinematography block.
- Performance and dialogue-performance plan.
- Opening intended state, world map, action axis, geography, meaningful distances, physical cause/effect.
- Expected end state/handoff.
- Dialogue/audio bindings and sound ownership/dependencies.
- Relevant references, each with authority and upload-order role.
- Provider settings and constraints.
- Locked/directed/open material.
- Review criteria.
- Immutable revision and dependency fingerprint.

### 12.3 Two distinct compiled prompts

Compile two complete provider-ready prompt packages from the same Delivery Package:

| Package | Purpose |
|---|---|
| SEE Keyframe Contract | Create correct opening visual evidence: viewpoint, lens/composition, geography, visible depth, character placement, opening pose, eye lines, prop/effect state, lighting, and action readiness |
| WATCH Delivery Contract | Execute ordered camera, acting, dialogue interpretation, sound timing, physical action, cuts/reframes/holds, continuity constraints, and expected final state |

The SEE prompt must not attempt to animate the whole scene. The WATCH prompt must not reinterpret the world, reset state, or invent a new camera grammar.

### 12.4 Keyframe suitability

A visually attractive SEE keyframe is not automatically suitable for the planned animation.

Keep separate:

- Visual review/approval.
- Keyframe-contract conformance.
- Animation suitability for the specific planned WATCH action.
- Human approval scope.
- WATCH eligibility.
- Any explicit director override and known risk.

WATCH should not be submitted from a keyframe that fails critical opening-state/geography/action-readiness requirements unless the director explicitly overrides the risk for a limited stated use.

---

## 13. Prompt compilation and request evidence

### 13.1 Prompt order

Provider prompts should lead with:

```text
1. Audience experience and story purpose.
2. Character acting, dialogue delivery, camera, focus and editorial direction.
3. Current world/continuity truth and relevant reference authority.
4. Concise exclusions and provider-specific syntax.
```

Do not produce legalistic blocks of generic negatives before the creative event.

Use negative instructions only for concrete recurring model failures and only within the relevant scope.

### 13.2 Creative Conflict Resolver

Before a request is sealed, the resolver must:

- Classify every instruction.
- Apply character/visibility/time/stage/provider scope.
- Resolve true conflicts by precedence.
- Suppress irrelevant defaults.
- Remove duplicates and historic residue.
- Preserve current specific creative direction where no hard conflict exists.
- Escalate actual hard conflicts with useful human-readable reasons.
- Record decisions in request evidence.

### 13.3 Sealed-request evidence

For each actual provider request, preserve:

- Originating Director Card/Delivery Package revision.
- Creative requirement IDs.
- Exact compiled provider prompt/body.
- References actually attached, their roles, order, source versions and hashes.
- Approved audio asset/version/timing/speaker assignment where applicable.
- Provider, model, endpoint, settings, target duration and job ID.
- Emitted instruction classification, source, scope, authority and resolution.
- Clauses emitted, suppressed, removed as residue, or escalated.
- Locked/directed/open grouping.
- Estimate, authorised cost ceiling, and actual cost status.
- Returned output ID/hash/duration and linked review evidence.

`actual_cost` must never default to `0.00`. Record estimate and authorisation separately. Actual cost is unknown until supported by provider/billing evidence.

A deterministic compilation, deterministic render, analysis review, provider generation, provider edit, and reuse must be labelled accurately. A recompile must not masquerade as a fresh creative pass.

---

## 14. Three creative review passes

Run these inside existing preparation where practical. They are analysis/recommendation passes, not separate user-managed approval gates.

### 14.1 Comedy review

Check:

- What sincere intention creates the joke?
- What does the audience expect?
- What changes expectation?
- Can the physical cause be understood?
- Is there enough time to see the consequence/reaction?
- Does the humour fit the actual character and relationship?

A quiet or emotional scene may correctly contain no joke.

### 14.2 Emotion review

Check:

- What does the character avoid showing?
- What observable choice changes the relationship?
- Can the feeling be noticed before it is explained?
- Does the response fit the character?
- Does the scene allow mixed feeling, restraint, ambiguity, or incomplete recovery?

Do not force tears, trauma, reconciliation, or an uplifting conclusion.

### 14.3 Editorial review

Check:

- Does the scene make sense in order?
- Are important actions and reactions visible?
- Is information revealed at the right moment?
- Does every cut have a purpose?
- Does the final thought have room to land?
- Can existing coverage solve the problem before another generation is requested?

Store resolved decisions in the shared scene and shot records.

---

## 15. Editorial revision loop

Creative improvement is iterative. A good plan does not remove the need to watch, diagnose, revise selectively, and watch again.

```text
Approved screenplay
→ scene plan / coverage board
→ SEE / HEAR / WATCH
→ timed board, dailies, or rough cut
→ watch in sequence with actual dialogue and available sound
→ diagnose
→ revise authoritative shared records
→ compile only affected new revision/package
→ targeted generation, targeted repair, post adjustment, or reuse
→ watch again
→ scoped review and approval
```

Editorial notes must become traceable directed changes, not vague requests such as “more energy,” “better acting,” or “make it cinematic.”

Example:

```text
Weak note:
Zenny’s reaction does not land.

Directed revision:
Hold the Zenny close-up 0.45 seconds longer after Fuzzby’s offscreen laugh.
Keep the camera locked. Zenny’s eyes acknowledge the sound, then she closes
them and resumes calm. Preserve approved dialogue and all surrounding picture/audio.
```

Studio must identify whether the change can be achieved in post, through a targeted repair, a new reaction view, a coverage change, or a different cut point—while preserving unaffected approved material.

---

## 16. Review actual results

Keep separate forms of evidence:

| Review | What it can establish |
|---|---|
| Plan review | Intended staging, coverage, timing, performance and state are coherent enough to attempt |
| Media review | Specific visible/audible events occurred in inspected returned material within declared scope |
| Human audience review | Whether the moment feels funny, moving, clear, cinematic, convincing, or otherwise achieves its purpose |

Review adjoining shots and assembled scenes, not only isolated renders.

Every finding must record:

- Exact candidate and inspected time range/frame range.
- Originating revision and sealed provider package.
- Intended result.
- Observed result.
- Inspection method and coverage: full clip, selected samples, audio available/unavailable, neighbouring footage available/unavailable.
- Likely problem.
- Specific proposed correction.
- What must remain unchanged.
- Whether the correction would need another paid generation or can be handled through authorised post/repair/reuse.
- Limitations and unknowns.

Do not award a claim such as “award-winning,” “ready,” or “passed” merely because the prompt is structurally complete.

### 16.1 Keep statuses separate

Keep at minimum:

```text
Review status:
What evidence was inspected and within what scope.

Approval status:
Whether a human approved an asset for a stated purpose.

Delivery eligibility:
Whether it may be used for shot, sequence, episode, or final-master delivery.
```

A clip can be human-approved for shot use while adjoining-cut continuity remains unverified. One green label must not conceal the other.

Use scope-qualified status language such as:

- Not reviewed.
- Advisory.
- Partially verified.
- Verified within shot scope.
- Adjoining cut unverified.
- Human-approved for shot use.
- Pending sequence review.
- Not approved for final master.

---

## 17. User experience

Keep the main workflow familiar:

```text
Approved script → scene direction → SEE → HEAR → WATCH → scene cut → finished episode
```

The director should not need to fill out every Director Card field, choose every handoff type, manage reference hashes, maintain state ledgers, resolve internal rules, or administer seven additional gates.

The agent should derive and prepare the plan, compile specialist work, run internal checks, keep evidence, prepare authorised repair candidates, and surface only meaningful decisions.

Provide three accessible review surfaces:

1. **Scene direction** — audience journey, coverage, camera/performance plan, continuity state.
2. **Scene playback** — timed coverage board, available animatic, or assembled footage; missing assets explicitly shown.
3. **Creative notes** — concise comedy, emotion, camera, dialogue, continuity, sound and review findings.

Example desired interaction:

```text
Julian: “We’re missing Zenny’s reaction.”

Studio: identifies the affected editorial view, explains why the current coverage
misses the reaction, proposes a framing/timing/production-route change, identifies
which downstream outputs are affected, preserves unaffected approvals, and presents
a candidate—not a new administrative workflow.
```

---

## 18. Acceptance criteria

The build is ready for controlled production validation when it demonstrates all of the following:

### Creative outcomes

- A quiet scene can pass without an invented joke, crisis, trauma, lesson, or dramatic transformation.
- A short episode can use fewer than seven transformation movements.
- Purposeful coverage, reverses, inserts, reactions, and long takes are chosen for audience understanding rather than template variety.
- A static camera and intentional stillness can pass when motivated by current cinematography and performance direction.
- Listener acting survives into the animation request.
- Dialogue expression/body performance matches approved words, meaning and delivery—not merely lip-sync.
- Reverse coverage preserves world geography, matched eyelines, action axis and relevant state.
- Meaningful prop/effect/physics states persist or change only by cause.

### Direction-to-provider handoff

- Image, voice, animation, and post inherit the same current direction revision.
- A Director Card/Coverage/Cinematography/Performance decision reaches the exact sealed SEE and WATCH provider payload where relevant.
- A deliberately removed required reaction, camera/cut instruction, reference, audio binding, state rule, or end state is detected before submission.
- A generic default cannot suppress a specific approved creative beat when no hard conflict exists.
- A genuine conflict—such as newly generated speech overlapping immutable approved dialogue—is explicitly blocked or escalated with a useful reason.
- A camera correction does not unnecessarily regenerate approved voice.
- Sound cues retain their timing and destination through finishing; WATCH invalidation occurs only when the changed sound is actually a WATCH provider dependency.

### Truthfulness and review

- Image visual approval is distinct from keyframe-contract conformance and animation suitability.
- Uninspected audio, motion, neighbouring footage, sampling gaps, and unsupported billing remain explicitly unverified/unknown.
- Review cannot automatically approve media or initiate spending.
- Estimate, authorised ceiling, and evidenced actual cost remain separate.
- Existing approved episodes remain readable and usable.

### Controlled end-to-end proof

- An assembled test scene demonstrates one current direction revision travelling through scene planning, SEE, HEAR, WATCH, returned-media assessment and final review.
- The test proves a qualifying case only; it must not claim universal Studio reliability.
- Additional qualification cases cover at least: reverse angle, time jump/new location, persistent effect, dialogue plus authorised nonverbal SFX, physical cause/effect, and real adjoining-shot continuity where authentic neighbouring footage exists.

### Creative comparison

Use one approved Crystal Bears scene to compare before and after the upgrade through structured human/director review:

| Question | Evidence |
|---|---|
| Can viewers understand the action without explanation? | First-view audience/director response |
| Do the bears feel distinct? | Acting and listening review |
| Does the reaction arrive when viewers need it? | Rough-cut timing review |
| Does the camera show the right character at the right moment? | Coverage/cinematography comparison |
| Does humour or emotion land in the assembled cut? | Human audience/director viewing notes |
| Does picture performance match approved dialogue delivery? | Audio versus picture review |
| Do geography, props, effects and physical actions remain coherent? | Continuity review |
| How many paid attempts and manual corrections were required? | Generation, repair and cost evidence |

Do not convert these into a false “award-winning” score. The purpose is to demonstrate more readable, alive, cinematic footage with fewer blind rerenders and less manual repair.

---

## 19. Delivery sequence

| Build phase | Build focus | Required proof |
|---|---|---|
| 1. Direction foundation + first scene trial | Creative authority, screenplay boundary, shared-record compilation, basic coverage, first performance/camera handoff | Small approved Crystal Bears scene travels from shared scene direction → SEE/WATCH request → returned media → honest review |
| 2. Camera and performance | Full cinematography block, dialogue-performance interpretation, listening direction, mechanics-first previs option | Compare approved scene before/after for camera purpose, performance readability, reaction timing and continuity |
| 3. Editorial workspace | Timed coverage board, rough-cut playback, cut timing, revision loop, selective impact/reuse | Watch a real scene, revise one coverage/acting issue, regenerate only affected work, review again |
| 4. Sound and finishing | Episode sound plan, cue ownership/dependencies, post handoff | Verify dialogue remains exact; sound cues arrive in intended place; post-only changes do not needlessly invalidate WATCH |
| 5. Production validation | Regression, omission, request-evidence, cross-route and controlled qualification cases | Demonstrate broader reliability across reverse angle, time jump, persistent effect, dialogue-plus-SFX, physical comedy and adjoining cuts |

---

## Defining requirement

> Every department must preserve and strengthen the same dramatic intention, from the approved screenplay through scene direction, coverage, keyframe, voice, animation, sound, edit, and finished scene.

Studio begins with an approved screenplay and protects it. It does not rewrite the story; it makes the story visible, audible, cinematic, emotionally readable, and physically coherent. The Delivery Package is an immutable compiled snapshot of authoritative direction at submission time, not a second source of truth. Every camera move, cut, focus change, hold, sound cue, performance action, and intentional stillness must have an audience purpose. The system must repeatedly watch, diagnose, revise selectively, and watch again until the assembled scene—not the prompt, checklist, or test suite—demonstrates the intended dramatic experience.

The system succeeds when a director can change an intention once, see the appropriate image/audio/animation/post work update, inspect the actual delivered result, and judge the scene without managing hidden machinery or discovering preventable failures through repeated paid renders.
