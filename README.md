# Agent Runtime Backbone

A shared, role-neutral operating scaffold extracted from an existing local
agent. Keep your existing host, LLM, identity and memory. The backbone
provides common runtime laws, boot templates, state and memory boundaries,
monitor/mirror, effort allocator, verification, sleep/wake and worker
contracts. It is not a replacement inference engine or an MCP-only service.

**Start here:** [Installation guide](docs/INSTALL.md) and
[AI installer instructions](AGENTS.md). See the
[shared backbone guide](docs/SHARED-BACKBONE.md) for the architecture and
[source-parity audit](docs/SOURCE-PARITY.md) for the source extraction boundary.

## Required core and optional modules

The shared laws and scaffold are the required foundation. The following four
extensions are optional. Their source ships in the same Python package, but
they are not automatically configured, registered, started or used. Core
installation requires no Docker, gateway, MCP client or new activity journal.

| Module | What it adds | Trade-off / when to choose |
|---|---|---|
| Docker worker sandbox | OS-enforced isolation for registered offline workers | Requires a qualified Docker Engine and reviewed local image; adds resource overhead. Useful for isolated computation, not ordinary reasoning. Does not isolate the whole host/browser. |
| mTLS read gateway | Authenticated, allowlisted access to registered read resources; no direct-origin fallback | Requires an approved gateway, certificates and maintenance. Not an IP-hiding mechanism or browser network boundary. |
| MCP server + adapter | Optional stdio transport for registered execution operations | Adds a process and host configuration. Use if the existing host needs MCP; the backbone itself does not require it. |
| SQLite activity ledger | Per-instance execution journal, including denied calls and interruption recovery | Adds local metadata storage and management. Not a new semantic memory system or proof of factual completion. |

**AI installers must ask the owner Yes or No for each module before enabling
it.** Default: all off. The owner may decline all four and still use the
core. Explain benefits, costs and dependencies; do not treat silence as
consent.

The current bundled MCP executable requires the SQLite ledger. Useful MCP
execution also needs a configured Docker worker or read-gateway backend.
If selections conflict, explain and ask the owner which choice to change;
never silently enable another module or bypass required journaling. The
direct offline CLI requires Docker but not MCP or a new ledger. Direct
Python service integration can omit the ledger. See the installation guide.

## Mandatory network and data law

[Canonical Runtime Spine, section 8](scaffold/canonical_runtime_spine.md#8-mandatory-network-and-data-boundary)
requires owner-authorized network access, actual enforcement, prevention of
accidental IP/data disclosure and fail-closed operation. The
[boot adapter](scaffold/SOUL.md) requires this law at startup.

This law is **not an optional module**, even with all four extensions off.
Reuse existing approved protection when appropriate. Do not run an operation
requiring containment if that containment is absent, unavailable or
unverified; never fall back to an unconfined route.

The tested enforcement is limited to registered offline Docker workers and
the scoped read-gateway path. It does not certify whole-agent/browser IP
containment. A gateway can observe its client's source IP. A prompt, tool
allowlist, MCP server or successful connection alone is not proof of network
containment. No service-restriction evasion or anonymity guarantee is provided.

## Core installation

Use the existing agent host/model and a dedicated Python 3.11+ environment on
macOS/Linux. Stage the neutral templates under scaffold/ in the agent's
private workspace without replacing its identity, role or memory. The cue
adapter uses the existing ConsumerMemory API from
[Trajecta Identity Memory](https://github.com/tamvi-journal/trajecta-identity-memory).
Bind an owner-approved compatible installation and private database. No
private seeds, credentials or database are supplied. Follow the
[installation guide](docs/INSTALL.md) before making changes.

## Architecture

    existing agent host / existing LLM
        + shared runtime scaffold loaded at instance boundary
          -> state, memory, monitor/mirror, effort and verification contracts
          -> mandatory operating and security laws
          -> existing authorized tools and approved enforcement boundaries
          -> optional execution extensions selected by the owner

The host owns its existing inference and action loop. Shipping helpers alone
does not prove the host invokes them at every required seam. MCP is possible
tool transport, not the backbone. No new cognitive runner or model
replacement is required.

## Acceptance scope

Version 0.2.0a5 is the source-parity candidate; a4 was the initial shared scaffold export. The bounded execution subsystem
was independently reviewed in v0.2.0a3; the added scaffold and read-only Memory
Core adapter received a synthetic packaging smoke check. That is not
certification of the entire agent, host, model, arbitrary network access or
production services.

Worker output is candidate evidence. The Gate validates declarations and
evidence, not OS capabilities. The ledger records invocation state, not
independently verified truth. Extensions never elevate authority.

No private identity, memory database, credentials, original private Git
history or live configuration is distributed. The bundled governance library
retains its MIT notice. Public visibility does not grant a blanket new license
over other upstream material.

See [network security](docs/NETWORK-SECURITY.md),
[bounded execution release notes](docs/RELEASE-0.2.0a3.md) and
[independent review](docs/INDEPENDENT-REVIEW.md).
