# v0.2.0a2 — independent-review remediation, 2026-11-26

The previous review candidate v0.2.0a1 (commit fd4b29f) passed independent
Linux unit, installed-wheel SDK broker and mTLS checks, but the reviewer
identified gateway availability and denial/audit lifecycle gaps. The
independent reviewer could not run Docker on their Linux VM. This release
addresses those findings and reruns the complete suite on the Mac host.

## Remediation

| Finding | Change and regression evidence |
| --- | --- |
| M1 | Bounded threaded gateway; handshake runs in worker thread, not accept loop. Global and per-source concurrent connection limits; single admission-to-response wall-clock socket deadline. Silent peer plus five valid requests, partial HTTP, deadline and capacity recovery tests. |
| M2 | Metadata-only ledger before role and argument validation, blocked reason and correlation ID, including malformed initialized MCP tool calls. Gateway emits structured denial/auth/response events without source IP, raw URL, headers or payload; unregistered resource names omitted. Reference gateway denies dispatch if its configured sink raises. |
| L1 | Post-execution observer failures block release, settle the ledger and retain actual worker-ran status. MCP unexpected errors preserve a valid request ID. Exclusive per-instance writer lease; interrupted rows become settled/unknown at startup, never replayed. Old ledger schema migrates in place. |
| L2 | Docker prestart rejects host namespace overrides, unexpected runtime, unconfined security options/profile, missing selected masked/read-only paths and unbounded swap. Explicit runc/private cgroup and IPC, memory=swap limit. |
| L3 | Acceptance generates JUnit-derived test count and JSON receipt; historical M0 count moved to unit-tests-m0.txt. Two offline wheel builds must have identical SHA256, and an optional expected SHA verifies an externally supplied review target. Mac and Linux test installations compare installed source bytes with the exact wheel; evidence is generated only after all legs pass. |
| L4 | TLS suite executes from the installed wheel, not the repository source. Reference server rejects missing client certificate, wrong CA, expired client/server certificates and unknown principals; existing hostname, redirect and denial cases retained. |
| L5 | Config must be owner-owned regular single-link file with mode 0600. |
| I1 | Policy compiled independently from the owner-selected role, not the current requested operation. The actual role/argument enforcement is explicit; preflight checks declarations and cannot replace OS containment. |
| I2 | Neutral CLI name and installed entry point; current tracked release documentation and review brief neutralized. Copyright notice and historical provenance retained. |

## Reproduce

Python 3.11+ on macOS/Linux, pytest, uv, a running local Docker engine with
the reviewed local Python image, and an installed MCP SDK client (the Mac
acceptance used the existing 1.26.0 client). From the repository root:

    MCP_CLIENT_PYTHON=/absolute/sdk/venv/bin/python sh scripts/acceptance.sh

The script builds twice in offline mode by default. Hatchling and its build
dependencies must already be cached; if not, explicitly allow dependency
resolution with LAR_ALLOW_BUILD_NETWORK=1 (review the build dependency
provenance). No Docker image pulls or real business traffic. For an exact
artifact review, set LAR_EXPECTED_WHEEL_SHA256 to the prior recorded digest;
a different digest fails acceptance.

The script mounts only the built wheel and two acceptance scripts into
a disposable network-none test container, installs the wheel offline, generates
synthetic certificates there, and checks installed bytes. The installed Mac
wheel is tested through the actual SDK and Docker worker. It then writes
evidence/acceptance-0.2.0a2.json and evidence/unit-tests.txt. No audit
fingerprints, socket addresses or request payloads are saved in the receipt.

## Boundaries that remain

The reference gateway is still not a production perimeter. Socket deadlines
do not forcibly terminate arbitrary trusted Python callbacks or a blocked audit
sink; deployed handlers/sinks need their own execution and storage budgets,
rate limiting, supervision and independent upstream network controls.
Source-address concurrency limits are in-memory only; clients behind one NAT
share the limit, and connection exhaustion is still possible. TLS certificate
fingerprints are pseudonymous identifiers with retention/access obligations.
Daemon defaults for user namespaces and seccomp/AppArmor remain trusted, not
attested merely by inspection. The runtime requires the selected runc backend.
The review addresses this exact bounded implementation, not all network
security properties.

No production account, agent config, original repo, browser or remote gateway
changed. Live domain adapters, full agent/browser OS-level egress containment,
durable semantic memory, independent re-review, and private-source publication
rights remain separate gates. Historical release artifacts are preserved; no
Git history rewrite was performed.
