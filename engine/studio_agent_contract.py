"""Human-readable command contract served to UI and MCP from one source."""
COMMAND_HELP = '''StudioAI agent command contract v1

Always name projectId. Read projects to find the real ID and setupVersion; never guess.
Use read view production with projectId/episode for setupVersion=1 projects. Crystal Bears
uses scene (projectId/episode/scene), shot and readiness (also shotId). Read view director
returns the current context and next decision. director_session returns valid action IDs;
chat (also stage) returns history and the current reviewTarget. Read connections is masked metadata;
configure keys in the Studio Connections screen, not in a tool or a prompt.

Every write takes operation, arguments, command_id. A command_id is a unique request ID
created once and retained across retries. Read studio_receipt after a disconnect. The
Studio owns all media jobs; disconnecting MCP does not cancel accepted jobs. An HTTP
return/jobId is not an approved or completed render. Use jobs (Crystal Bears) or production
(project-scoped jobs) to retrieve progress and returned artifacts. Runtime/server restart
may require the existing Studio resume/reconciliation operation; do not automatically
submit a new provider job.

For setupVersion=1 projects use project_command arguments:
projectId, episode, action, expectedRevision from production.state.revision, plus fields
for the native action. budget: amountUsd. chat: message. prepare: starts planning.
continue: prepares the next outcome. approve/reject: shotId, reviewId from current
outcome.id; reject also note. request: shotId. resume: jobId. The native command validates
all inputs and source hashes. Creative proposals use chat then apply_revision against the
returned proposal and revision; never overwrite the production ledger directly.

For Crystal Bears:
director_chat: projectId, episode, scene, shotId, stage, message, by. For approvals also
provide the exact reviewTarget returned in Director chat/readiness; only transmit a human
verdict, never your own. Phrases such as prepare voice or prepare request follow the same
chat workflow as the Studio. This can spend within the approved episode allowance.
director_action: same scope plus action from the current Director session; the native
service rechecks it. Do not invent an action.
shot_command: projectId, episode, scene, shotId, cmd. One candidate by default.
fire first without spendToken to prepare the exact cost request; inspect its job/result and
current scene package pendingSpendAuth. Fire with the returned spendToken only when the
user authorised the sealed request. Never regenerate tokens or skip the 9.5 authoring floor.
Other native cmds include build-keyframe, voice-shot, approve-keyframe, reject-keyframe,
approve-voice, reject-voice, approve, reject, harvest, stitch, status. Rejections need correction.
voice_direction: scope plus lines (the current HEAR working lines with user edits).
dialogue_revision: scope plus the native oldExactText/newExactText and speaker fields.
animation_direction: scope plus prompt; prefer Director changes when the story changes,
so upstream decisions propagate. Saving is not firing and may require native reprepare.
script: projectId=crystal-bears, episode, number, title, script (plain text).

Project setup:
create_project: native Studio wizard payload including name/projectType and its supplied
bible/assets. project_episode: projectId, title, script; creates a new episode.
library: projectId, sourceHash and native library edit fields. services: projectId,
services mapping of existing connection IDs/model choices. Never send credentials.

Post:
post: Crystal Bears projectId/episode/action build-assembly, approve or reject. A verdict
requires the exact masterSha256, reviewer and note. finishing: projectId/episode/action
status, resolve, director-brief, upscale or poll; modifications bind masterSha256 and
upscale requires maxCostUsd. Resolve availability is verified by the existing finishing
service, not assumed from MCP registration. Other projects use project_command assemble_cut
for their current assembly capability; cross-project DaVinci finishing is not yet exposed.

Faults:
read incidents with projectId. operation incident records projectId, summary, observed,
expected, episode/shotId/requestVersion/jobId as relevant. Updates require id and
expectedRevision. fixed requires rootCause, affectedComponent, fixReference; verified
also requires regressionEvidence, workflowEvidence and reviewer. These are recorded
claims, not automatic certification. A production agent can record a fault, but cannot
modify application code, invent a test pass or close a defect based only on a workaround.
'''


def access_info(root):
    from pathlib import Path
    root = Path(root).resolve()
    return {'version': 1, 'mode': 'same-studio-api', 'localTransport': 'stdio',
            'config': {'mcpServers': {'studioai': {
                'command': str(root / '.venv-mcp/bin/python'),
                'args': [str(root / 'engine/studio_mcp.py')],
                'env': {'STUDIO_URL': 'http://127.0.0.1:8899'}}}},
            'remote': 'Streamable HTTP requires HTTPS ingress and an explicitly configured OAuth issuer, resource and JWKS URL.',
            'credentials': 'Provider keys remain in Studio Connections; the MCP configuration contains no provider keys.',
            'instructions': COMMAND_HELP}
