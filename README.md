# Local Agent Runtime

Shared agent backbone extracted from an operating local agent. This is
an installable set of common runtime laws, boot templates, memory adapter
and runtime modules, not a new inference engine.

**Start here:** [Shared backbone guide](docs/SHARED-BACKBONE.md).
Copy the neutral templates under scaffold into each agent's workspace,
keep identity/role/memory private, and use the existing host's cognition
loop. The runtime spine is loaded by the host's boot mechanism. The
previously reviewed execution subsystem is one backend; MCP is optional.

## Install the scaffold

Use your existing agent host and model. Install this repo in a dedicated
Python environment and copy the contents of scaffold/ into a new agent
workspace; adapt the boot file to the host's actual startup mechanism.
Do not replace an existing private identity or memory store.

The cue adapter expects the existing Memory Core Python API
(ConsumerBundle, ConsumerMemory, MemoryProfile). The external project
is https://github.com/tamvi-journal/trajecta-identity-memory. Install a
compatible owner-approved version and bind an existing initialized private
database (0600); no seeds, credentials or default database are supplied.
Run scripts/backbone_smoke.py in that environment for a synthetic
packaging check before using the binding.

## Bounded execution subsystem (reviewed a3 baseline)

Role-neutral, local-first runtime scaffold for local agents, including Hermes.
One shared candidate-audit kernel; owner-selected roles; independent state journals;
OS-enforced offline workers and a narrowly scoped authenticated read gateway.

**0.2.0a4 — shared scaffold export.** The unchanged bounded execution implementation was independently reviewed in a3; the additional boot/memory/policy files have a packaging smoke check. No full-host/browser containment certification.

## Quick start

Python 3.11+ on macOS/Linux, a qualified local Docker Engine (runc and required inspection contract) and a reviewed
local Python image. A separate virtual environment is required because the
legacy import namespace is named runtime.

    uv build --wheel --offline
    uv venv .venv
    uv pip install --no-deps --python .venv/bin/python dist/local_agent_runtime-0.2.0a4-py3-none-any.whl

Copy an example instance config into an owner-controlled directory, replace the
image placeholder with the reviewed immutable local image ID, and set file
permissions to 0600. Do not commit actual configuration, credentials, keys,
private memory, or the state directory.

For the local MCP server:

    .venv/bin/local-agent-mcp --config /absolute/owner/instance.json --state-root /absolute/owner/state

For Hermes, generate a config fragment instead of editing the live agent:

    .venv/bin/local-agent-hermes-config --config /absolute/owner/instance.json --state-root /absolute/owner/state

Merge the generated fragment only into a separately approved agent profile.
This server uses legacy MCP stdio initialize/list/call; the local SDK acceptance
uses MCP Python SDK 1.26.0. It does not expose HTTP, execute arbitrary code, or
inherit the model's claimed identity as authorization.

## Architecture

    owner config (instance, role, tool allowlist)
       -> role-scoped MCP or Python service
       -> role/argument enforcement + shared declaration and candidate gate
       -> registered operation
          -> Docker network=none worker, or
          -> pinned mTLS read gateway with client resource authorization
       -> candidate audit + advisory allocator/monitor
       -> per-instance metadata ledger (including denied attempts)

The Gate validates declarations and candidate evidence, not operating-system capabilities.
The role-bound service enforces its operation registry and argument contracts.
The gateway is a separate trust root. Runtime clients may use only the
operator-configured endpoint and resource names; no arbitrary URLs or direct
origin fallback. Registered handlers are reviewed developer code. The reference
gateway and TLS tests use synthetic resources only. A real provider connector
requires separate authorization and validation.

Worker output is a candidate, not verified truth. No operation in this release
auto-releases or claims independent completion. Existing state, sleep/wake and
memory helpers remain portable; persistent semantic memory/provider migration is
not included in the accepted execution path.

## Boundaries

- Docker enforcement applies to containers launched by this runtime, not the
  whole Hermes process, other MCP servers, host browsers or OS.
- No network-enabled browser, real account, shell or external write is allowed
  by the supplied tool registry. Disable or isolate all other host tools before
  relying on this boundary; a configuration declaration alone is not proof.
- The mTLS gateway transport is not a general VPN or proxy kill switch and
  cannot certify a gateway's upstream egress or service compliance.
- No private identities or history imported. The bundled governance library
  retains its MIT notice. Private scaffold redistribution rights require
  review before public publication.

See docs/ARCHITECTURE.md, docs/NETWORK-SECURITY.md, docs/RELEASE-0.2.0a3.md,
and docs/INDEPENDENT-REVIEW.md.
