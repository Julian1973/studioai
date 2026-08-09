# Emission Conformance Matrix

Canonical contract: `AAA_PROMPT_STANDARD.md`, Part 8, `aaa-part-8-v2.1`.
`IMPLEMENTED+TESTED` means a deterministic check and regression test exist. `OPEN`
means the control is missing, advisory-only, or has not yet declared and tested that it
is non-applicable. This table intentionally does not count an LLM instruction as a check.

| # | Mechanical check | Keyframe emission | Render emission | Voice emission |
|---:|---|---|---|---|
| 1 | Ending state present | OPEN — an opening still has no explicit tested non-applicability rule. | IMPLEMENTED+TESTED — stage and shot handoffs are locked by `animation_story_lock_report`. | OPEN — track/line completion is not mapped to the visual end-state law. |
| 2 | Route envelope and time tiling | IMPLEMENTED+TESTED — provider route, reference limits and prompt budget are checked. | IMPLEMENTED+TESTED — stages tile 0 to approved duration and dialogue regions must fit and overlap a stage. | IMPLEMENTED+TESTED — line start and duration are checked against the approved voice contract. |
| 3 | Character budget | IMPLEMENTED+TESTED — Seedream production word budget hard-blocks after plumbing compaction. | IMPLEMENTED+TESTED — duration-specific provider word ceilings hard-block. | OPEN — emitted V3 request text has no provider character-budget check. |
| 4 | Camera grammar conflict | OPEN — no blocking dominant-move-family check. | OPEN — Prompt Lab reports a warning, but Part 8 requires a BLOCK. | OPEN — non-applicability is not mechanically declared. |
| 5 | Brand names | OPEN — no dedicated provider-prompt brand-name blocker. | OPEN — no dedicated provider-prompt brand-name blocker. | OPEN — no dedicated spoken/request brand-name blocker. |
| 6 | Geography block present | IMPLEMENTED+TESTED — Geography must match approved Cinematography verbatim. | IMPLEMENTED+TESTED — Animation geography must match the approved scene ledger and is emitted. | OPEN — non-applicability is not mechanically declared. |
| 7 | Motion vocabulary | OPEN — non-applicability for a still is not mechanically declared. | IMPLEMENTED+TESTED — the versioned character grammar pack is injected and banned verbs block. | OPEN — non-applicability is not mechanically declared. |
| 8 | Numeric holds | OPEN — non-applicability for an opening still is not mechanically declared. | IMPLEMENTED+TESTED — every approved gag clock must emit its numeric `Hold` line. | OPEN — voice pause timing is checked, but it is not the Part 8 gag-hold contract. |
| 9 | Shot-purpose “and” count | OPEN — no advisory split-candidate check. | OPEN — no deterministic purpose-count check. | OPEN — non-applicability is not mechanically declared. |
| 10 | Reference scope | IMPLEMENTED+TESTED — complete turnarounds/Scene Look are individually bound and contract-checked. | IMPLEMENTED+TESTED — Seedance preflight checks attached/cited reference roles and limits. | OPEN — canon voice binding exists, but Part 8 reference-scope applicability is not declared. |
| 11 | Duplicate action sentences | OPEN — no semantic duplicate-action blocker. | OPEN — exact duplicate direction is advisory-only, not the required BLOCK. | OPEN — non-applicability is not mechanically declared. |
| 12 | Transition continuity | OPEN — no A-end/B-open transition check on this path. | OPEN — continuity fields exist, but the complete checklist is not enforced as Part 8 specifies. | OPEN — audio-transition applicability is not mechanically declared. |
| 13 | Style paragraph verbatim | IMPLEMENTED+TESTED — canonical version/text or approved Scene Look authority is checked. | IMPLEMENTED+TESTED — the versioned style paragraph is compiler-owned. | OPEN — non-applicability is not mechanically declared. |
| 14 | Music policy present | OPEN — image generation has no explicit tested non-applicability rule. | IMPLEMENTED+TESTED — the approved audio contract deterministically emits `No music` when required. | OPEN — dialogue request emission does not declare scene-music ownership. |
| 15 | Complete-sentence integrity | IMPLEMENTED+TESTED — compiler-owned compact prose cannot be clipped mid-phrase. | IMPLEMENTED+TESTED — compacted stage prose is boundary-safe and emitted narrative lines are checked. | IMPLEMENTED+TESTED — every performed-text recipe must end as a complete spoken sentence. |
| 16 | Approved physical-staging fidelity | OPEN — the opening still path has not declared what physical staging is permitted at frame one. | IMPLEMENTED+TESTED — approved `physicalStaging.contactAndWeight` is emitted verbatim in its owning stage and audited. | OPEN — body/voice relationship is checked, but physical-staging non-applicability is not declared. |

## Current closure

The three current regressions are closed as classes where they apply:

- Dangling prose: shared implementation and tests on keyframe, render and voice.
- Timecoded multi-stage tiling and audio-line placement: render implementation and tests;
  keyframe/voice route checks remain separately visible above.
- Leaf-loading physics: generalized to every approved comedy beat carrying
  `physicalStaging.contactAndWeight`; the compiler never contains a Fuzzby-specific fix.

OPEN cells are the next hardening backlog. They are not blockers invented by this table;
they are the previously unimplemented parts of the stated AAA contract made visible.
