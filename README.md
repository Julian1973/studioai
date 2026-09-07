# Crystal Bears Animation Studio

You direct the film instead of managing the machinery.

## Start

Use the existing configured Python environment:

```bash
python3 cb-studio/serve.py
```

Open [the production workspace](http://127.0.0.1:8899/cb-studio/app.html). The separate
`director.html` page is an advanced inspector, not the default episode workflow.
For a fresh environment, install `requirements.txt` into a virtual environment first.
Preserve the private engine configuration, billing profile and media when moving the Studio.

## Produce an episode

Upload the script and approve the proposed episode allowance. The Studio prepares story
interpretation, scene plans, department direction and production packages internally.
Review the keyframe (SEE), voice (HEAR), exact animation request (WATCH), then the returned
render. Each is a distinct human decision. Silent shots skip the unnecessary voice decision.
Describe corrections in production chat; approved work elsewhere remains available.
At the end of a scene, review its cut and complete the final-master review.

[The current production contract](THE_DEFINITIVE_PIPELINE.md) defines approval, continuity,
spending and revision behaviour. [The shared craft standard](skills/production-standard.md)
and each marked runtime skill define department output. [Provider evidence](skills/provider-evidence.md)
records the qualified capabilities. Historical documents are not runtime instructions.

## Repository

- `cb-studio/`: current interface, advanced inspector and local API.
- `engine/`: planning, compilation, approvals, generation, budget, learning and post.
- `skills/`: current department contracts and maintained references.
- `shows/crystal-bears/`: immutable script versions, locked canon and creative taste sources.
- `cb-output/`: production packages, jobs, approvals and evidence.
- `tools/`: maintenance and read-only audits.
- `docs/archive/`: superseded documents and inert source copies for recovery.

The unrelated root Node/Replit project and old imported prototype folders are outside this
animation runtime. Do not start the Studio with their `package.json`.
The locked `CRYSTAL_BEARS_STUDIO_BIBLE.md` is retained for canon lineage; its historical
technical gate map is superseded by the current contract and is not supplied to new direction calls.

## Verify

```bash
python3 tools/audit_studio_sources.py --output docs/audits/source-audit.json
python3 -m pytest -q
```

Tests block external providers. Software tests are not evidence of a successful live render.
A production trial requires a script, approved allowance and the applicable media/request approvals.
Configured USD estimates exclude tax and are not an invoice guarantee. Reservations prevent
concurrent workers from committing more estimated spend than the remaining episode allowance.
Unknown submissions retain their reservation; known BytePlus task IDs can be recovered.
