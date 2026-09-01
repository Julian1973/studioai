# Crystal Bears — the show's chairs (taste overlays)

T52/T53 (RESTRUCTURE_SPEC_PROJECTS.md, 2026-09-01). The CRAFT of every chair — role, responsibility,
workflow, real-world influence and the executable runtime contract — is the studio's, at
`studio/chairs/<role>/SKILL.md`, and names no show. The files here are THIS show's own doctrine for
each chair: the worked examples, canon citations, cast notes and dated rulings that used to live in
`skills/crystal-bears-<role>/SKILL.md` (moved verbatim; `skills/…` keeps a symlink to each one until
the canon re-lock at T61, because `canon/lock_policy.json` still hashes them as the runtime sources).

How a chair is assembled at run time (`engine/cb_departments.load_runtime_skill`):

1. the studio chair's `RUNTIME_WORKER` contract, with `{project}` → the profile's `name` and
   `{showrunner}` → the profile's `showrunner`;
2. plus, if this show's `<role>.md` carries a block between `<!-- RUNTIME_TASTE_START -->` and
   `<!-- RUNTIME_TASTE_END -->`, that block appended — the ONLY part of these documents a worker
   call ever reads. None of them carries one today, so every assembled contract is byte-identical
   to what shipped before the split. Everything else in these files is for humans.

`room.json` is the creative room's own voice (`project_laws.room_voice`), used by the Director's
chat and the creative room prompts. `animation.md` holds the ensemble-continuity rules that used to
sit inside the animation chair's own reference notes.
