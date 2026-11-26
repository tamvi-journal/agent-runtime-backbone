# M0 architecture and migration boundary

## Source intake

- Governance kernel, revision 618960e0523d1cedfbf2a0c00d5e388079acef64:
  copy committed Python package and regression tests; preserve MIT notice.
- Runtime scaffold, revision 5023b966376da654825ba26d1fc95b4c7f054e87:
  extract committed contracts, allocator, advisory monitor/mirror/core, sleep,
  canonical-promotion and local embedding/retrieval helpers; port nine
  regression modules with synthetic names and paths.
- No Git history, user/identity documents, real profiles, private memory,
  secrets, archived chats, social-account adapters, generated task logs,
  generated UI snapshots, or identity-specific Memory Core seeds imported.
  The embedding model namespace is neutralized; it is a deterministic fixture,
  not a production embedding service. Existing vectors are not migrated.
- Legacy worker invocation, state-query identity layer and live posting paths
  are deliberately not copied. They require adapters against the shared gate
  instead of duplicating release/evidence policy.
- The lineage reference repository was inspected, not merged: architecture
  source is a reference canary and contains inconsistent README markers.
- Original runtime completion helper now requires a nonempty observation and
  evidence locator in addition to passed status. That structural check is
  necessary but not independent verification.

## Separation

| Layer | Responsibility |
|---|---|
| Role | task permissions and registered operations; owner config |
| Governance | trusted envelope/preflight, candidate scan and review |
| Runtime | invocation routing, state, monitor/mirror, evidence, continuity |
| Execution | actual OS isolation; no fallback to host |
| Domain adapter | separately reviewed official connectors, scoped credentials |
| Verifier | independent artifact readback and outcome, not worker self-report |

The governance library evaluates declarations, not actual permissions.
The offline backend is the only executable path in M0. Policy and network
controls are trusted-host-owned. A worker cannot set its own authority.

## Roadmap

M0: curated private repository + role profiles + offline fixture + tests.
M1: independent review, packaged install acceptance, authenticated runtime
broker, explicit capability schema, role-specific tool registry, per-instance
state stores and memory provider adapter (not identity data).
M2: evaluate pinned third-party sandbox and authorized network connector
backends in isolated fixtures. Require independent network enforcement and
negative tests before accepting any network-enabled role.
M3: provider/Hermes adapters and scoped API workflows, migration dry runs and
independent release evidence. Keep old source repos and running agents intact
until separately accepted. No real account, browser, or external action is
approved by M0.

## v0.2 local candidate (supersedes M0-only status above)

The M0 sections preserve intake provenance. Current entrypoints:
- runtime/instance.py: owner file validation; instance-bound SQLite metadata
  ledger. The journal is not independent signed evidence, does not persist
  user payloads, and preserves unsettled operations as started.
- runtime/service.py: explicit registered tools and strict argument validation,
  one shared preflight and candidate gate; allocator and post-commit monitor
  are advisory and cannot elevate authorization or verification.
- runtime/mcp_server.py: local process-scoped legacy MCP stdio lifecycle.
  Authorization is an owner-selected process/config binding, not a remote
  authenticated identity; no TCP listener or generic tool invocation.
- runtime/adapters/hermes.py: generates role-filtered MCP configuration,
  never mutates the installed Hermes runtime.
- runtime/offline_executor.py: actual Docker no-network sandbox, bounded
  output, input via stdin, pre-start inspection of immutable image, command,
  security options, resources and container state, exact cleanup attempt.
- runtime/broker.py: exact owner gateway IP and mTLS identity, typed resource
  allowlist, strict response schema, no redirects, retry or direct fallback.
- runtime/adapters/gateway_server.py: reference mTLS read-only server with
  certificate fingerprint to resource authorization and registered callbacks.
  No public-facing deployment or provider integration is included.

For adding a domain, register a new bounded operation and schema in reviewed
runtime code or an owner-controlled adapter; select its availability per role.
Do not give roles raw shell, arbitrary URLs or policy-changing permissions.
The role is not identity; per-agent private identity and memory remain outside
the distribution.

The portable original memory, snapshot and canonical helpers are present but
not all are wired into the active MCP service. Provider-backed reasoning,
durable semantic memory, and actual production agent/browser migration remain
separate acceptance work. Host-wide enforcement requires an independently
enforced environment around the agent itself; adding an MCP server does not
remove other host network paths.

## v0.2.0a2 remediation

The service creates its invocation journal row before validating role/args.
Unknown operations are recorded as a fixed label, never raw input. It binds
the declaration policy to the full owner-configured role. The role and typed
argument checks, sandbox and gateway are the actual authorization/enforcement
boundaries; the shared Gate is a declaration and candidate-evidence check.
The per-instance writer lock prevents recovery while another writer is active.
Interrupted work is marked unknown, not completed. The MCP transport preserves
the request ID when internal processing fails. No automatic replay.
