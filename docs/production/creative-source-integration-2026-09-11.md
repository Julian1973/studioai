# Existing creative sources: local selection and pending Director wiring

Implemented locally on 11 September 2026: `engine/studio_creative_context.py` reads the
project's explicit `creative_sources.json`, selects complete named sections, records
source and selected-content SHA-256 hashes, and produces a compact provenance receipt.
It does not invoke any model, generate media, relock canon or grant approval.

The module is currently **not connected to text-provider calls**. Automatic approval
review rejected forwarding newly selected confidential bible/playbook excerpts to the
configured OpenAI Director endpoint. Existing routing is unchanged. The inert proposed
integration diff is `/private/tmp/studio-integration-20260911/pending-director-context.patch`;
it must remain unapplied until the user explicitly authorizes this source payload to the
existing OpenAI text Director/specialist endpoints. No provider-call success is claimed.

## Registered sources and selections

| Source | Selected existing material | Stages |
|---|---|---|
| September final Drive show bible, file `1VygMCPRQLwcW4UyJ1Xw-FMQgNTAwmsUm` | Series Promise; Creative Language; Continuity & Emotional Storytelling; Original Character Imagery | All |
| Existing `canon/LOCKED_CANON.md` | Target audience, look and premise; excludes the historical format entry | All |
| Existing Seedance production director skill | Humour through play/character/recognition (Joe Brumm); visible relationship change (Pete Docter); expressive bodies and environment (Chris Sanders); application within existing authority | All, with visual cinema omitted from HEAR |
| Existing script direction engine reference | Read for audience experience and governing screen idea | Story |
| Same existing reference | Compile stills and animation from the same record | SEE, WATCH |
| Same existing reference | Paper reel review with observed-evidence boundary | Review, Post |
| User-supplied Chris Stover cinematography DOCX | Camera consciousness and performance driving camera | Story, SEE, WATCH, Review |
| Same Stover source | Lens/focus grammar | SEE, WATCH, Review |
| Same Stover source | Motivated, finishable movement | WATCH |
| Same Stover source | Editorial rhythm | Post |
| Existing voice performance canon | Intention toward the listener and thought before the line | HEAR |

Full extracted reference texts remain local in `shows/crystal-bears/creative/sources/`.
The manifest records the Drive source URL/date and original Stover DOCX path/hash.
Selected production passages exclude commercial, licensing, legal, historical-format,
scent-conflict and identity-conflict material. Conflicts are recorded in provenance; no
new source silently supersedes current screenplay, locked canon or approved originals.
Source examples, numerical scores and proposed workflow gates are not production law.

## Scope and evidence

Other projects read only `projects/<project-id>/show_bible.md` or their own explicit
manifest. Cross-project paths, symlink aliases, conflicting project IDs and malformed
selectors fail locally. Long content requires narrower explicit selection rather than
silent truncation. No Crystal Bears fallback is used for a named different project.

The fingerprint includes selected-content hashes and relevant metadata, not full-file
audit hashes. A WATCH-only section edit changes WATCH dependencies while preserving SEE,
even when both selections reside in the same source file. The receipt retains full-file
hashes for provenance. Consumers must compare `fingerprint`, not hash the entire receipt.

Validation: `python3 -m pytest -q engine/test_studio_creative_context.py` — **11 passed**.
`python3 -m py_compile engine/studio_creative_context.py` also passed. These prove local
source selection, content/provenance hashes, stage isolation and project isolation.
They do not prove that a live Director call received or applied the newly selected text;
that integration remains pending the explicit payload/destination authorization above.

## Existing destination evidence

`studio_workspace.PROVIDERS['openai']['base']` is `https://api.openai.com/v1`.
`cb_llm` creates the standard OpenAI SDK client. The live `engine/.env` contains no
`OPENAI_BASE_URL` override and disables Gemini fallback. The recorded legacy Director is
`gpt-5.5` and validator `gpt-5.4-mini`; final SEE/HEAR Director defaults to `gpt-6-astra`
and WATCH Prompt Director defaults to `gpt-5.6-sol`. No model settings or credentials were
changed by this work. Only allowlisted non-secret routing fields were inspected.
