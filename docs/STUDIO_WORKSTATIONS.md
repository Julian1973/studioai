# Studio workstation release candidate

## Installation

Use a separate checkout of the development release on each workstation. Keep
approved production assets and the current production installation intact.

Current qualification target: Linux, Python 3.12. macOS and Windows acceptance
tests have not been performed. The launcher uses portable Python commands, but
that is not evidence of full platform compatibility.

Prerequisites: Python 3.12 with venv/pip, Node for browser-contract verification,
FFmpeg and FFprobe for picture/sound assembly. The initial installation needs
network access to the Python package index. Model execution uses external APIs;
this is not an offline model appliance and installing it does not supply model licences.

```bash
python3 scripts/studio.py install --verify
python3 scripts/studio.py doctor
python3 scripts/studio.py run
```

Installation creates `.venv-studio` and installs exact versions from
`requirements-studio.lock`. The doctor command prints local readiness, dependency
mismatches and credential presence only. It never tests keys remotely or spends.
The launcher refuses startup when machine dependencies or the selected profile
are missing. It does not certify artistic quality or production approvals.

Provider credentials remain on the workstation in environment variables or the
existing ignored `engine/.env`. Environment variables take precedence. Restrict
credential-file access to the operator. The server listens on loopback and opens
through its authenticated launch URL. Do not expose its port directly to the LAN.

Select an existing profile at launch with `--show <show-id>`. New project adapters
remain blocked until qualified. An installation includes source code; customer
redistribution needs agreed licence terms and third-party notices first.

## Multi-machine boundary

Each workstation is an independent local installation. This release does not
provide shared studio identity, central permissions, distributed job ownership or
safe concurrent writes across a network file share. Do not point several running
instances at one shared production folder or SQLite database.

For a collaborative studio deployment, deliver a central production service,
operator identities, project permissions, shared asset storage and coordinated
workers before claiming multi-user operation. A local workstation build can still
support an internal proof of production with controlled handovers.

## Recovery and updates

Stop the server before backing up production state. Preserve the whole production
workspace, including approved media, scripts, shows, output evidence, billing
profile and SQLite state. Store credentials separately. Existing media backup
tools alone are not a full workstation recovery plan.

Install updates in another directory and verify them first. Do not overwrite the
production folder in place. Rollback means returning to the previous directory
and its matching state snapshot. Schema rollback across different builds has not
been qualified. Confirm a restore on a second machine before commercial delivery.

## Remaining release gates

Candidate verification: installed into a new isolated Python 3.12 environment;
`pip check` found no broken requirements; 755 tests passed and four skipped.
Authenticated startup smoke check: unauthenticated API 401, studio page 200,
authenticated health endpoint 200, Python source request 404. No model API was called.

- Test installation and restore on the studio's actual operating systems.
- Lock distribution hashes and retain required third-party licence notices.
- Complete ownership/provenance and repository confidentiality review.
- Run a vulnerability audit against the release dependency set.
- Qualify live provider access, costs and delivery with authorised generation.
- Demonstrate a complete production and failure/recovery on a second workstation.
