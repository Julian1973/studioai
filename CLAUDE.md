# Crystal Bears Studio — operating instructions for Claude Code

Source of truth order: CRYSTAL_BEARS_LOCKED_CANON.md (what the show is) > CRYSTAL_BEARS_STUDIO_BIBLE.md (how it is made) > this file. Where they touch, canon wins.

Every session: read this file, TICKET_PACK_001.md and the current phase of WORLD_CLASS_ROADMAP.md before writing any code. Work tickets in the pack's order of play, one commit per ticket, the commit message naming the ticket. A ticket is done only when its Definition of Done is true AND the Bible agrees — never merely when the code compiles.

Hard rules (never work around these):
1. Gates are hard locks. Never advance past an unsigned gate; never sign past an open BLOCK.
2. Taste lives in prose (the chair skills); law lives in code; canon lives in data. Anything found in the wrong layer moves the day it is found.
3. No output is ever hand patched. A fault routes through a retake with a layer diagnosis (keyframe / brief / reference / take).
4. Law 5: the voice lives in the render. One combined @Audio1, supplied by the Voice Director and lip-synced by Seedance; no native-voice fallback (a beat with dialogue whose V3 track fails REFUSES to render); no post voice swap. cb_post has no swap function by design — do not add one.
5. Never describe a character's appearance in prompt text. Identity comes only from the reference images; names live only in the audio.
6. Canon is edited ONLY at root CRYSTAL_BEARS_LOCKED_CANON.md, then `python3 tools/sync_canon.py`. The skill copies are generated; editing one is drift. `--check` must pass before any sign off.
7. When code becomes sharper than the documents, the documents update in the same commit.
8. Restructure work follows RESTRUCTURE_SPEC_T30.md: one phase per commit, baseline byte-identical prompts proven after each phase.
9. A temporary state (e.g. a pollen moustache) resolves WITHIN the take it started in — it never carries across a take boundary (T2 ruling, 2026-07-02, Julian). There is no continuity-tail/previous-clip-tail chaining mechanism; do not re-add one without a fresh ruling.
10. cb_seedance.py's older validation machinery (the 15 minds, physical-action archetypes, authoring/compact validators) is a KEPT, intentional second validation layer underneath the Director's chair (T3 ruling, 2026-07-02, Julian) — not leftover code. It can legitimately refuse a render; that is by design.

Baseline proof (run before and after any change that touches prompt code):
  cd cb-gen && python3 cb_segprompt.py ../cb-output/Ep1_The_Adventure_Begins_beat_package.json 1.B1
  plus for_beat on the first three Ep1 beats — outputs must be byte identical unless the ticket explicitly changes them.
