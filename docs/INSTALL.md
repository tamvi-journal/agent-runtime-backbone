# Installation guide

Use your existing agent host, LLM, inference loop, identity, role and memory.
This backbone is an addition to that host, not a replacement agent.

## 1. Inspect and ask before optional installation

Identify the target workspace, host/model, platform, Python version, memory
binding, startup-file mechanism and current security controls. Inspect only
what is needed; never expose credentials or private memory. Preserve
existing working files, state and tools.

Ask the owner the following four questions in their preferred language.
Explain that all four are optional, and that the mandatory shared laws
remain in force regardless of the answers.

| Module | Ask the owner | Default |
|---|---|---|
| Docker sandbox | Do you want isolated offline workers? Requires Docker and a reviewed image; uses extra machine resources. | No |
| mTLS gateway | Do you need authenticated access to approved read resources? Requires gateway administration and certificates. | No |
| MCP server + adapter | Do you want registered execution tools available through MCP? The backbone itself does not require MCP. | No |
| SQLite activity ledger | Do you want a separate local journal of execution attempts, denials and interruptions? This is not semantic memory. | No |

Record explicit Yes/No choices. All No is a valid core-only setup.
Do not select a module automatically based on the role or treat an
unanswered choice as consent. A Yes selects that module only.

### Current dependencies

- All four extensions ship as source in one package. Optional means whether
  prerequisites are installed and the extension is configured, enabled or
  used, not four separately distributed packages.
- The bundled MCP executable always opens its private SQLite ledger. MCP
  cannot be enabled if the ledger is declined. Explain this dependency and
  ask the owner whether to approve the ledger or leave MCP off.
- Useful MCP execution needs a configured Docker or registered read-gateway
  backend. If both are declined, leave MCP off. Do not silently enable a
  backend or patch out required journaling.
- The direct offline CLI uses Docker without MCP or a new ledger. The Python
  AgentService accepts an optional Ledger; an approved host can use it
  directly without MCP. The read gateway also has a direct Python broker.
- SQLite is built into Python. Selecting the ledger means creating and
  using its separate private database, not installing a database server.
  It is not a stand-alone monitor of unrelated host tools. Without MCP,
  an explicit Python integration is needed to use this journal.

## 2. Install the shared core

Use a dedicated Python 3.11+ environment on macOS/Linux. Select an exact
reviewed repository revision. Do not modify global Python or replace an
existing environment. For a host with uv and the cached build backend:

    uv build --wheel --offline
    uv venv .venv
    uv pip install --no-deps --python .venv/bin/python dist/local_agent_runtime-0.2.0a4-py3-none-any.whl

Run from the cloned repository root. If .venv already belongs to another
project, use a different private environment. Missing prerequisites or
required downloads must be explained and approved. The core does not
require Docker, certificates, MCP registration or an activity database.

Stage the files in scaffold/ in an instance-private workspace:

- SOUL.md: boot adapter, adapted to the host's actual startup mechanism.
- canonical_runtime_spine.md: mandatory shared laws.
- WORKSPACE_BINDING.md and CURRENT_WORKSPACE_ROLLUP.md.
- specs/: monitor and sleep/wake contracts.
- role.md.example: example only; the owner defines the instance role.

Preserve existing identity.md, role.md, user.md, SOUL/AGENTS files, memory
and state. For an existing agent, stage a minimal merge of the shared
instructions/laws; show the diff and obtain approval before changing
existing startup configuration. For a new agent, keep its private files
separate. Verify that the host actually loads the laws. Copying files alone
does not prove runtime integration.

### Memory binding

Reuse the instance's compatible Memory Core connection. The supplied
adapter expects ConsumerBundle, ConsumerMemory and MemoryProfile from
the separate project:
https://github.com/tamvi-journal/trajecta-identity-memory.
Use an owner-approved compatible version. The adapter expects an existing
initialized private database with mode 0600; it ships no seeds, initializes
no database and does not migrate one. Do not copy another agent's database.

With the dependency available in the dedicated environment, run the
synthetic packaging check:

    .venv/bin/python scripts/backbone_smoke.py

Configure the actual approved interpreter and private memory binding in
the boot instructions. Retrieval is candidate evidence, never truth or
authority. Report a missing or incompatible binding rather than claiming
continuity. No model or cognition migration is needed.

## 3. Enable only selected extensions

### Docker worker sandbox

Requires a qualified local Docker Engine, runc and the required inspection
contract, plus a reviewed immutable local image. Use
examples/analyst.instance.json as a template for registered operations.
Keep actual configuration private (0600); use the reviewed image ID.
Use the existing offline CLI or the selected direct Python/MCP integration.
Do not automatically download images, modify the Docker daemon or grant
new agent access to its socket. The bounded backend isolates registered
offline workers, not arbitrary programs, the whole host or browsers.
If declined, do not configure its worker operations.

### Authenticated mTLS read gateway

Use examples/tls-gateway.instance.json only as a template. Bind an approved
gateway and registered read resources. Keep certificates, keys and
configuration private. The reference server is not a certified public
deployment. Review [network security](NETWORK-SECURITY.md) and the
[release notes](RELEASE-0.2.0a3.md) for the perimeter, certificate,
rate/deadline and supervision requirements before deployment. Do not open
a listener or access real resources merely because this module was selected.

The broker rejects unregistered resources and has no direct-origin fallback.
It is not a general proxy, VPN or whole-host/browser containment. If
declined, do not configure its brokered read operation.

### MCP server and adapter

Only configure if the owner selected MCP, its required ledger and a
registered execution backend. Prepare a private instance config listing
only the selected role operations. The bundled stdio server can be
launched by a compatible host:

    .venv/bin/local-agent-mcp --config /absolute/private/instance.json --state-root /absolute/private/state

For Hermes, generate a config fragment without editing the live agent:

    .venv/bin/local-agent-hermes-config --config /absolute/private/instance.json --state-root /absolute/private/state

Replace placeholder paths with the actual approved absolute paths. The
generator only prints configuration; it does not install it. Review the
fragment and merge it only into the approved target instance. Preserve
other tools; verify actual discovery matches the selected role's tool list.
Do not restart a working agent or alter another profile without approval.
When declined, retain the existing host's integration without registering
the bundled MCP server.

### SQLite activity ledger

The Ledger in runtime/instance.py is instance-scoped, metadata-only and
single-writer. It records invocation status/reason and marks abandoned
invocations unknown at recovery, without replay. It does not record raw
tool inputs, transcripts, IPs or credentials. Keep its state root private
(0700) and database outside source control. It is not independent factual
verification or another semantic memory store.

If selected without MCP, bind it through an approved Python integration;
report if no consumer is configured. Do not create an unused database or
claim to monitor unrelated tools. If declined, omit the new database on
supported paths and preserve existing audit/evidence systems. The bundled
MCP path must remain off if its journal dependency is declined.

## 4. Mandatory network and data law (all installations)

Load section 8 of
[canonical_runtime_spine.md](../scaffold/canonical_runtime_spine.md)
and its boot instructions even if all optional modules are off.

Network access requires owner authorization and an actually qualified
enforcement boundary. Prevent accidental IP/data disclosure. Refuse
operations requiring unavailable or unverified containment. Preserve
existing approved protection; never fall back to an unconfined route.

A prompt, declared policy, optional module or successful connection alone
does not prove actual containment. Verify selected supported boundaries
with authorized synthetic fixtures. The accepted worker/gateway scope
does not cover the whole host/browser. Report unverified paths and do
not use them under a claim of protection. No service-restriction evasion
or account concealment is authorized.

## 5. Installation receipt

Report the exact pinned revision, environment and actual core load path;
the memory binding status; each explicit module choice and its actual
configured/running/verified/disabled/blocked state; dependency conflicts;
security boundaries verified and unverified; any withheld operations;
and exact files/config changed and remaining owner actions. Do not claim
completion merely from copied files or generated configuration.
