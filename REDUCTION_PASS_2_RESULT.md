# StudioAI Controlled Reduction Pass 2

Date: 2026-08-28
Base: `e47a608791fbd8f714ecf58a228a48d6252bd7f3`

## Result

Pass 2 consolidates runtime authority without changing the four-phase Studio workflow,
approval gates, spending controls, provider locks, or approved production media.

- Runtime skill directories: 20 -> 8 (`-12`)
- Tracked files: 507 -> 493 (`-14`, including this result and proof test)
- Physical locked-canon bodies: 12 -> 1 (`-11`)
- Canon compatibility paths: retained as 9 symlinks to the show canon
- Production Python lines: 45,554 -> 45,554 (no runtime logic removed)
- Active production Seedance contracts: 1 (`engine/SEEDANCE_25_PRODUCTION_CONTRACT.md`)
- Active production animation prompt compiler: 1 (`compile_animation_provider_prompt`)
- Legacy comparison transport: retained only as explicit `legacy_compare`; it is not a
  production provider adapter or fallback
- Normative architecture/operating docs retained; superseded `BEFORE_ARCHITECTURE.md` and
  `DISPATCH_001.md` removed, with their history preserved in Git

The staged diff is 135 added lines and 4,788 deleted lines. The large deletion count is
primarily duplicate canon bodies and superseded skill families; tracked symlinks preserve
path compatibility without maintaining separate canon copies.

## Retained authorities

- Story Director: `skills/crystal-bears-director/SKILL.md`
- Screenwriter: `skills/crystal-bears-writer/SKILL.md`
- Cinematic Shot Director and keyframe DP: `skills/crystal-bears-cinematographer/SKILL.md`
- Voice Director: `skills/crystal-bears-voice-director/SKILL.md`
- Seedance Production Director: `skills/seedance-production-director/SKILL.md`
- Editor/Post: `skills/crystal-bears-post/SKILL.md`
- Canon: `shows/crystal-bears/canon/LOCKED_CANON.md`
- Provider policy: `engine/cb_providers.py` and `engine/provider_capabilities.json`

Versioned skill requests are compatibility aliases to the current owner. They cannot load
an alternate v3/v4 runtime contract. Seedance 2.0 remains available only for explicitly
labelled comparison evidence, never through ordinary production model selection.

## Verification

From this worktree, after the reduction changes:

```text
pytest -q
746 passed, 4 skipped in 32.94s
```

No paid provider calls were made. The four skips are existing documented unavailable
historical-media cases. No Episode 1 ledger or media path appears in the Pass 2 diff.
The new reduction tests prove one runtime owner per consolidated responsibility, one
physical canon source, and explicit legacy-comparison labeling.

## Scope boundary

This pass does not alter the default branch, recovery references, ledgers, concurrency,
approved Episode 1 outputs, or provider credentials. It is ready for review only after the
branch is pushed and a fresh clean checkout repeats the test command.
