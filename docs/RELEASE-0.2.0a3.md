# v0.2.0a3 — accepted local transport audit hardening

The previous independently accepted local baseline is v0.2.0a2 at
1ea49e3. The R2 delta at a169988 was subsequently independently reviewed
and accepted; main was fast-forwarded to the audited code. The original
baseline remains available under its local tag.

## R2: bounded transport audit volume

Transport-level connection-limit, TLS/transport failure, deadline and
internal-error diagnostics use a fixed four-reason aggregation budget.
One immediate sample per reason per five-second monotonic window is
followed by a count summary when the window expires (or at server close).
The summary counts additional occurrences, not the already-emitted sample.
A periodic flush is provided by serve_forever via service_actions. A caller
using handle_request manually has no periodic flush guarantee: summaries
can be deferred until a later record for that reason or server_close.
No raw source address, client-controlled key, payload or new unbounded queue
is retained. The window is shared by all gateway workers. This does not sample
HTTP request denials or authorized dispatch/response audit events. The
reference server requires a client certificate before HTTP processing;
a valid certificate is not itself proof of resource authorization. The
request event principal can be null for parse failures, unsupported methods,
and other errors before the handler captures the fingerprint. These HTTP
records are intentionally not aggregated by the transport budget. Deployers
must separately budget authenticated request rates and audit storage.
Transport samples and summaries carry an integer count; ordinary request
records omit count. Consumers should distinguish the event types and may
normalize a missing count to one occurrence, without assuming that every
record has identical schema. A failing transport sink is counted in process-local diagnostics;
this is not a durable audit guarantee.

The reference gateway still calls its configured sink synchronously for
emitted events and trusts registered callbacks. Production use needs
independent deadlines, nonblocking bounded sink handling, storage limits,
monitoring, retention policy and supervision. Aggregation limits diagnostic
volume, not the number of connections accepted or the ability to deny
service.

## R1: deployment gate (not implemented on a host)

The global connection cap is intentionally a cap, not a fairness guarantee.
Multiple untrusted source addresses can exhaust the admission pool. Before
any remote deployment, an independently enforced firewall or controlled
front end must allow only approved client networks, enforce connection/rate
budgets and protect the gateway's listener. Validate the deployed controls
with authorized synthetic clients and test that an unapproved source cannot
reach the gateway. A Python resource allowlist or mTLS alone is insufficient.
Do not expose a reference listener as a production perimeter.

No firewall, external account, live gateway or agent configuration has been
changed. The browser/whole-agent containment gate is unchanged.

## R3/R4: engine and evidence scope

The tested worker engine is Docker Engine using its local Unix socket,
the runc runtime, private cgroup and IPC namespaces, no-network mode and
the explicit inspection contract in runtime/offline_executor.py. The
reviewed Mac environment uses Docker Engine 29.5.3. Other engines and
alternate Docker environments are not automatically supported: Colima,
OrbStack, Podman and rootless/custom profiles may fail closed on the socket,
runtime, namespace or masked/read-only-path checks. Do not weaken those
checks merely to get an alternative engine to start. Independently qualify
an engine and its inspection semantics before adding support.

The independent Linux reviewer of a2 and a3 had no Docker engine. Docker
execution, SDK integration and cleanup evidence for a3 comes from the
Mac author acceptance, not an independent Docker rerun.

## Reproduce

    MCP_CLIENT_PYTHON=/absolute/sdk/venv/bin/python sh scripts/acceptance.sh

The acceptance script generates evidence for the current release version.
The targeted regression exercises a bounded loopback fixture only and
checks that 30 denied connections generate two aggregate/sample records,
with the full count retained and the slot released. Unit tests also
exercise concurrent aggregation and sink failure accounting.

## Independent delta acceptance

The independent reviewer reproduced 229/229 unit tests on Linux, the source
digest and byte-identical wheel from the Mac receipt, and 19/19 TLS tests
against the installed wheel. The immediate transport audit output in the
bounded flood fixture decreased from 29 records on a2 to two on a3 (one
per reason). The reviewer observed successful post-flood recovery and no
retained active connections or source entries. The short flood observation
ended before the summary window expired; the count-conservation assertion
of 30 represented denials in two records comes from the author's explicit
aggregation fixture, not an independent observation of that short run.

R2 is closed for local acceptance. The R1 production admission gate and
R3/R4 engine/evidence qualifications remain. This acceptance is for audited
code a169988; subsequent explanatory documentation does not expand it.
