# Network security: containment, not account concealment

## Threat model

Protect personal network addresses and local data from accidental disclosure
by a worker, browser, MCP service, extension or subprocess. Network egress
policy must be enforced outside model prompts. The host, daemon, approved
image, and operator are trust roots. A compromised host/admin, kernel escape,
or an intentionally trusted application revealing data is not covered.
No claim is made about concealing activity from services, evading geographic
or account controls, bypassing bans, or defeating anti-abuse measures.

## M0 implemented

- Default deny; no network-enabled role, no host fallback.
- Local immutable image ID, no pull; explicit local Docker Unix socket;
  temporary empty Docker client config to avoid inherited proxy settings.
- Create with network=none, read-only root, no privileged mode, no added
  caps, nonroot uid/gid, no mounted host files/socket, no exposed port,
  no image healthcheck, bounded CPU/memory/PIDs.
- Inspect host configuration, image identity and created state before start.
  Failure blocks. Start only a registered fixture, inspect exit, clean up.
- Raw daemon errors are not returned as candidate content. This initial
  backend is for trusted bounded fixtures, not arbitrary untrusted programs.
  The captured output ceiling is checked after capture, not streaming; a
  future arbitrary-code backend needs bounded streaming output and stronger
  independent lifecycle/cleanup supervision.
- Current evidence: active interfaces only loopback; route table has no
  non-loopback IPv4/IPv6 route; TCP IPv4/IPv6 and UDP fixture connections
  to reserved documentation addresses fail. This is a point-in-time test
  on one local Docker/image environment. It is not a proof for all platforms
  or network-enabled operation.
- No browser, account, proxy provider or internet target was tested.

## External research / integration decisions

1. Docker none driver — implemented as M0 backend:
   https://docs.docker.com/engine/network/drivers/none/
2. Anthropic Sandbox Runtime — evaluate pin, license, OS isolation, trust
   boundaries and subprocess behavior before enabling as a backend:
   https://github.com/anthropics/sandbox-runtime
3. OpenAI Codex network proxy — reference for trusted proxy combined with
   OS sandbox, default deny and explicit destination policy:
   https://github.com/openai/codex/tree/main/codex-rs/network-proxy
   https://openai.com/index/inside-the-codex-sandbox/
4. gVisor — optional Linux workload isolation evaluation:
   https://gvisor.dev/docs/user_guide/networking/
5. RFC 8828 — WebRTC can disclose additional addresses beyond HTTP traffic:
   https://www.rfc-editor.org/rfc/rfc8828.html
6. MCP security guidance — local binding/authentication and least privilege:
   https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html

No third-party source or installer was executed for this intake. M0 depends
only on the already running local Docker engine. Before enabling a connected
backend, prefer officially authorized, narrow, audited connector operations,
not generic browser or arbitrary URL execution. Treat network-enabled
sandboxing as its own security acceptance, with no production credentials.

## Required acceptance for any future connected backend

All checks in a controlled test environment with synthetic credentials and
an owned test destination; independent observation of actual network behavior.

| Test | Required result |
|---|---|
| Missing / unavailable sandbox or policy | do not launch |
| Unauthorized network destination | denied at actual OS / broker boundary |
| Authorized connection | only approved endpoint, independent receipt |
| Backend/proxy loss before start | no worker/browser startup |
| Backend/proxy loss mid-run | no alternate direct route, job fails closed |
| IPv4/IPv6/DNS/UDP/child process | denied unless explicitly authorized |
| Restored tabs/background browser work | no network before enforcement |
| Arbitrary remote browser/session address | rejected; verified binding required |
| Tool request attempts to change route or permission | blocked |
| MCP server unauthorized request | rejected; local bind or scoped authenticated transport |
| Secret/cookie/IP values in logs | minimized/redacted; no raw secrets |
| Process failure/timeout/restart | no unconfined fallback, independent cleanup |
| Provider/account terms | official API or explicit authorized access; human approval for mutations |

This is a test specification, not an implementation of a connected backend.
Commerce integrations must respect service terms and permitted API use.

## v0.2 connected read boundary

A connected agent can request a registered resource, not an endpoint. The
runtime uses a fixed numeric IP and named TLS server, validates the dedicated
CA and server name, presents the operator-provisioned client certificate, and
rejects invalid resource IDs, unknown response fields, duplicate keys, missing
or oversized bodies, redirects and non-JSON results. The reference server
requires a client certificate and checks its fingerprint against a resource
allowlist. No general-purpose CONNECT or forwarding API is exposed.
The plain loopback transport is deliberately a synthetic test fixture only.

The worker still has no outbound network. The MCP service itself is trusted
host code; only the gateway client is restricted by this code path. The gateway
can see the connection source IP; its own outbound route, handlers and privacy
properties must be independently accepted. No claim is made of anonymous
internet access or host-wide traffic containment. Gateway deployment requires
certificate lifecycle, rate limits, handler deadlines, monitoring, explicit
allowlist and OS-level network controls. The included server is a reference
implementation, not a hardened public service.

### Browser and existing-agent boundary

No browser adapter or remote debugging attachment is registered. Arbitrary
browser URLs, existing browser sessions, shell and unrestricted network tools
are rejected by this service. Before enabling any browser route, a separate
reviewed OS-level containment backend must enforce egress before launch,
including DNS/IPv4/IPv6, child processes and restored tabs. Verify failure and
mid-session loss with synthetic endpoints, not production accounts. The
browser/session bugs reported in the initial screenshot have not been patched
in the existing business application. Do not treat this repository as proof
that a separate live application is protected.

The earlier M0 note about post-capture output ceilings is superseded for the
current bounded Docker worker path: selector-based streaming limits both
stdout and stderr. A create timeout may leave daemon state indeterminate; the
exact cleanup attempt fails closed and managed containers carry a scoped
label for owner inspection. No arbitrary worker code is supported.

## v0.2.0a2 gateway availability and audit remediation

The accept loop never performs TLS handshakes. Bounded concurrent threads
(default 16 global, 4 per source) use a single wall-clock socket budget
(default 3 seconds) from admission through request/response; timeout or
transport failure closes the socket and releases the slot. A silent peer
does not block five valid sequential requests in the fixture. Arbitrary
trusted callbacks and slow logging sinks cannot be cancelled by this
socket timer. Production deployment remains gated on independent budgets,
supervision, retention and perimeter limits.

Audit events contain timestamp, fixed reason, status, certificate fingerprint
if known, and a registered resource name only. Source addresses are used
ephemerally for connection limits and not logged. Unknown resource strings
and raw input are excluded. The local invocation ledger records both allowed
and denied attempts, with metadata-only denial reasons and crash recovery.
