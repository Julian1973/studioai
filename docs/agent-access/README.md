# StudioAI agent access

StudioAI can be operated through its visible controls, embedded Director chat, or the
MCP bridge. The bridge calls the same authenticated HTTP APIs; it contains no alternate
prompt compiler, generation engine, approval implementation or provider credential store.

## Run locally

Keep `cb-studio/serve.py` running normally on port 8899. Install the separate MCP runtime:

```sh
./tools/install_studio_mcp.sh
```

Open **Projects → Agent access** for the absolute-path client configuration. A local
MCP client launches `.venv-mcp/bin/python engine/studio_mcp.py` over stdio. It authenticates
to the same loopback Studio session as the local UI. No provider keys are in that config.
Installing the bridge does not configure or prove compatibility with a particular client.
Do not publish the Studio's local HTTP port.

The server exposes `studio_read`, `studio_command`, `studio_receipt`, `studio://workflow`,
`studio://commands`, and a production-direction prompt. Read the command resource before
mutating anything. Exact review tokens, revisions and spend tokens are still enforced by
Studio. Review quality scores do not authorise a human verdict or a provider purchase.

The embedded Director already uses these production APIs. Do not replace it with an
agent that edits package JSON or writes generation prompts outside the production path.

## Jobs and reconnection

The Studio owns accepted jobs. The bridge does not wait for a full render and disconnecting
a chat does not terminate a server job. Persist `command_id`: a confirmed response is
returned again without another submission. After an uncertain dispatch the bridge will
not blindly replay it; inspect Studio jobs/current artifacts and the receipt. This is
at-most-once bridge dispatch, not a promise of distributed exactly-once execution.

Production job recovery remains the native worker's responsibility. Generic projects
expose resume/reconcile through `project_command`. Legacy Crystal Bears uses the existing
Studio job runner. Do not restart a worker or create a replacement job to conceal an
uncertain provider submission. A registered job is not a finished or approved outcome.

Bridge receipts live under `~/.local/share/studioai/agent-access/`, outside the served repo.
They store command hashes and scrubbed results, never provider keys. Existing Studio state
is authoritative; the receipts are a dispatch journal, not a second production ledger.

## Remote/cloud clients

Streamable HTTP is implemented as an OAuth protected resource server. Configure an actual
OAuth issuer and HTTPS ingress before running it:

- `STUDIO_MCP_ISSUER`: HTTPS issuer URL.
- `STUDIO_MCP_RESOURCE`: externally reachable HTTPS MCP URL / token audience.
- `STUDIO_MCP_JWKS`: trusted HTTPS signing-key URL.
- Issued JWTs must have valid issuer, audience, signature, expiry, subject and
  `studio:operate` scope. Configure the client registration/consent with that issuer.

```sh
.venv-mcp/bin/python engine/studio_mcp.py --transport streamable-http --port 8900
```

It binds only to loopback. A separately managed HTTPS ingress forwards to port 8900.
SDK middleware enforces authentication and publishes protected-resource metadata;
JWT verification permits RS256/ES256, verifies audience/issuer/expiry and uses trusted JWKS.
No unauthenticated HTTP mode is offered. This is a single trusted workspace deployment:
only users entitled to operate that whole workspace should receive `studio:operate`.
It is not a public multi-tenant hosting service or per-project access-control system.

Cloud-client compatibility must be verified against the deployed HTTPS URL and real
OAuth account. No DNS, public deployment or client login was configured by this change.
Do not claim a ChatGPT/Claude connection based on protocol tests alone.

## Capability boundaries

Project setup projects use the existing project-scoped pipeline and vault. Crystal Bears
uses its existing production ledger and provider setup. The adapter refuses cross-routing
another IP into those legacy endpoints. This change does not migrate legacy credentials.
Project creation, scripts, libraries, service selections, Director actions, SEE/HEAR/WATCH,
review and job retrieval are exposed through existing routes. Exact supported fields are
in `studio://commands` (also available in the Studio Agent access panel).

Crystal Bears post/finishing routes retain their current DaVinci capability checks and
master-hash validation. Other projects currently have their native assembly capability;
this bridge does not silently turn that into a qualified cross-project DaVinci workflow.

## Fault-to-fix evidence

`/api/workflow-incidents` is shared by MCP and Studio. Records preserve observed/expected
behaviour, project/version/job context, root cause, component, change reference and tests.
`fixed` requires a named shared change. `verified` also requires regression evidence,
workflow evidence and reviewer. Evidence is recorded, not automatically certified. A shot
creative revision belongs to that shot; a workflow defect must be fixed in shared code.
No tool executes patches or tests supplied by an external assistant.

Verification:

```sh
python3 -m pytest engine/test_studio_agent_gateway.py cb-studio/test_agent_access_api.py
.venv-mcp/bin/python -m pytest engine/test_studio_mcp_protocol.py
```

Use temporary projects/fake providers for mutation tests. Live connection smoke tests must
stay read-only unless generation or editing was specifically authorised.
