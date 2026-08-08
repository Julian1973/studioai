# DAILIES — the learning lane

One job: render something every day, learn from every render, and never lose a lesson.

This lane exists because the studio has world-class discipline and zero shipped film.
The gates (0–5) remain the law for MASTERS. Dailies is where takes are cheap, ugly is
allowed, and every outcome — good or bad — becomes permanent knowledge. Nothing here
bypasses canon: the same engine, the same references, the same Law 5. What it strips
is ceremony, not standards.

## The three laws of the lane

1. **Something renders every day.** A day with no fire is a day the studio learned
   nothing. Dryruns don't count.
2. **Every failure gets a diagnosis before any refire.** Layer (take / keyframe /
   brief / reference) + failure class. "Try again" is not a diagnosis.
3. **A proven path is law.** When a take is accepted, its recipe is written to the
   playbook. The next similar shot uses the proven recipe VERBATIM — no freelancing,
   no 'improvements' — until a render (not an opinion) dethrones it.

## Quickstart (from the repo root, keys in env)

```
python3 dailies/dailies.py status                    # where are we, retake rate
python3 dailies/dailies.py preflight 1.B1            # free: brain-check the beat
python3 dailies/dailies.py fire 1.B1                 # preflight → real render
python3 dailies/dailies.py verdict 1.B1 good "lands. fuzzby energy right"
python3 dailies/dailies.py verdict 1.B1 retake --layer take --class floaty "wings dead in shot2"
python3 dailies/dailies.py log                       # the learning ledger
```

`fire` refuses to spend if preflight finds a BLOCK — the stupid-output guard runs
BEFORE the money, not after. `verdict good` banks the recipe into `playbook.json`.
`verdict retake` logs the lesson and prints the exact `cb_retake.py` command.

## The two organs

- **preflight.py — the pre-flight brain.** Mechanical checks compiled from the locked
  canon, the studio laws, and the Seedance guides. Not an LLM opinion: regex and
  arithmetic against the engine's own dryrun output. Each check names its source law.
  This is the answer to "things get overlooked" — a checklist cannot forget.
- **playbook.json — the memory.** Proven recipes per shot archetype, failure classes
  with their known fixes, and the route ledger (which model route is proven vs
  candidate). This is the answer to "never finds the best path and sticks to it" —
  the best path is a FILE, not a model's mood.

## Relationship to the gates

Dailies feeds masters. When a scene's takes are consistently landing in dailies (the
retake rate is falling and the playbook is thick), walk the SAME beats through the
gate UI for sign-off — they'll pass fast because the lessons are already banked.
Never master a beat straight from a first take.
