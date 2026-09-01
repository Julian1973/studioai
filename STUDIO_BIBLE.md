# STUDIOAI — THE STUDIO BIBLE

*How the studio works, for ANY show. Written 2026-09-01 (T60) from the engine parts of the first
project's bible (`projects/crystal-bears/SHOW_BIBLE.md`, which keeps everything that is Crystal Bears).
A show's own bible says how THAT show is made; this page says how the studio makes any show.*

---

## PART 0 — THE GOVERNING LAWS

1. **One studio, one director, one mind per chair — never a committee.** Every chair is one coherent
   practitioner. The Director makes the calls; every other chair executes that vision in its craft.
2. **References are law; text does the motion; the video model does the heavy lifting.** Identity and
   look come entirely from the reference images. Prompt text controls motion, performance, camera and
   audio rules — it never describes a character.
3. **Fix the structure, not the output.** A bad clip is a bad keyframe, prompt or reference. Fix what
   produced it and re-run through the system. No hand-patched output, ever.
4. **Gate discipline.** Each gate is signed off before the next unlocks. Cheap fixes upstream beat
   expensive fixes downstream. Nothing self-advances past a gate.
5. **The voice lives in the render — never in post.** The directed voice track goes IN as `@Audio1`
   and the video model performs to it. Post is a mix, not a rescue.
6. **One studio, any show.** The engine, the studio UI, the chairs and the tools contain no show. A
   show is a PROJECT (`projects/<id>/`) that owns everything about itself. The active project's
   `profile.json` is the only path authority.

---

## PART 1 — THE PIPELINE AT A GLANCE

```
GATE 0 Write → GATE 1 Direct → GATE 1.6 Previz → GATE 2 Look + Keyframe → GATE 3 Voice + Animate → GATE 4 Retake/Edit → GATE 5 Post
                                          (Continuity / Director Review checks EVERY gate)
```

Into the video model at Gate 3 go only: the opening frame (`@图1` — the scene's keyframe, or the
previous take's harvested settle frame), the character references (`@图2`…), the scene plate, and the
directed voice (`@Audio1`). Everything else is the beat's own story, staged by the Director.

---

## PART 2 — THE CHAIRS (studio/chairs/<role>/SKILL.md)

Each chair is generic craft — its role, responsibility, workflow, real-world influence and the
executable runtime contract — and names no show. The active project fills `{project}` and
`{showrunner}` from its profile and may append its own taste (`projects/<id>/chairs/<role>.md`, the
`RUNTIME_TASTE` block). A chair is resolved BY ROLE (`engine/cb_departments.py`), never by project id.

| Chair | Influence (never imitation) | Gate |
|---|---|---|
| Writer — the writers' room | Docter · Stanton · Brumm | 0 |
| Director — the faithful adapter | Docter · Stanton · Lasseter | 1 |
| Cinematographer / DP | Lin · Kalache · Eggleston · Calahan | 2 |
| Voice Director | Romano | 3 |
| Animation Director | the model's own production doctrine (`studio/chairs/animation`) | 3 |
| Composer + Music Supervisor | Giacchino · Newman · Bush | 5 |
| Director Review / Continuity | the script supervisor's discipline | every gate |
| Post Supervisor | Nolting · Rydstrom · Giacchino | 5 |

---

## PART 3 — THE GATE CONTRACTS

Every gate is a HARD LOCK: entry condition → the chair's workflow → deliverable / definition of done
→ sign-off by the showrunner → the next gate unlocks. The lock is enforced three ways — the engine
refuses to fire, the server refuses the request, the UI shows it locked. Continuity checks before
every sign-off. Machine checks (manifests, lints, QA, canon lock, join checks) prove what a machine
can prove; "does it flow, is it funny, would the audience watch it again" is the showrunner's
reserved verdict and no check approximates it.

| Gate · Chair | Locked until | Deliverable / Definition of Done |
|---|---|---|
| **0 · Write** | a seed exists | a locked, dialogue-final screenplay with its `.score.json` sidecar (Gate 1 refuses a script without one) |
| **1 · Direct** | Gate 0 signed | the beat package: every beat one gag arc, every manifest field populated; Director's Eye passes |
| **1.6 · Previz** | Gate 1 signed | the scratch-voice reel watched; dialogue timing judged |
| **2 · Look + Keyframe** | Gate 1.6 signed | the scene plate (checked) and one wide opening keyframe per scene, on-model, continuity-chained |
| **3 · Voice + Animate** | Gate 2 signed | one directed take per beat, voice in the render, clip QA + join check passed, the showrunner's eye |
| **4 · Retake / Edit** | Gate 3 signed | surgical retakes by timecode, one variable per re-fire; the locked cut |
| **5 · Post** | Gate 4 signed | conform on live motion, platform masters, captions, the vertical derivative; the mix the showrunner curates |

---

## PART 4 — WHERE THINGS LIVE

```
engine/                the pipeline (law in code) — no show in it
cb-studio/             the studio UI + local API — no show in it
studio/chairs/         the eight generic chairs (craft)
studio/templates/      the project template a new production is created from
tools/                 baseline, canon sync, link check, media backup
projects/<id>/         ONE FOLDER PER SHOW
  profile.json           the only path authority (id, name, showrunner, capabilities, every path)
  SHOW_BIBLE.md          how THIS show is made
  canon/                 facts: LOCKED_CANON.md, characters, locations, continuity, voice cards,
                         reference slot policy, lock_policy + CANON_LOCK (the approved snapshot)
  laws/                  the show's own rules the engine enforces: style, cast vocabulary,
                         forbidden elements, continuity rules, emission checks (read via project_laws)
  chairs/                the show's taste per chair (+ room.json, the creative room's voice)
  creative/              learning, exemplars, the Design-tab roster
  assets/                turnarounds, plates, references (not in git — backed up)
  episodes/              scripts (the immutable script store), output (packages, evidence,
                         prompt bank, asset registry), media (takes), episodes.json
```

The active project: `STUDIO_PROJECT` env → the studio's last switch (`cb-studio/data/active-project.json`)
→ the one profile marked `"default": true` → the only project. Switching productions in the studio
reloads the engine onto the chosen project.

**Canon is data and is locked.** `canon/lock_policy.json` names the sources; `CANON_LOCK.json` is the
showrunner's approved snapshot of their hashes. Editing a locked source marks canon DRIFTED until the
showrunner re-locks it in the studio. A new show LAW goes in `laws/*.json`, which the lock does not
hash. `python3 tools/sync_canon.py --project <id> --check` must pass before any sign-off.

**Adding a show:** Productions → New production (the wizard) — or
`python3 engine/project_scaffold.py "Name" --premise … --audience … --showrunner …`. Then fill the
canon (the bible, characters with reference images, locations), cast the voices, lock canon, upload
the first script. Nothing in the engine is edited to add a show.

---

## PART 5 — THE SAFETY RULE FOR STRUCTURAL WORK

`python3 tools/t40_baseline.py --check` must print IDENTICAL after any change to the engine's shape:
every stored emission and production package of the first project is byte-identical. The test suite
must keep its pre-existing failures and gain none. `tools/check_links.py` must pass. Structure changes
land one ticket per commit on a branch the showrunner merges.
