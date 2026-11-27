# Source parity audit — neutral export

Scope: compare the actual boot-bound source checkout's portable mechanisms
with the first public scaffold export, not reimplement or retest a working
agent. Source files were read without changing the source instance. The
work-memory hook and its tests came from the source working tree rather than
its last committed tree; the source configuration referenced that hook for
pre/post LLM calls. This is a source extraction, not proof of a live invocation.

| Source mechanism | Disposition |
|---|---|
| Allocator, canonical promotion, contracts, monitor and retrieval context | Existing portable implementations retained |
| Core gate and verification | Existing portable code retained; verification additionally requires evidence and observed outcome |
| Embedding memory and sleep/wake | Existing implementation retained; instance names neutralized |
| Secret scanning and input/diff guards | All five original files retained byte-for-byte |
| MainBrain demo modules | Restored source state and wake fixtures; not an additional model loop |
| Worker preflight/routing/envelope/evidence/observability | Restored remaining source execution bridge, controlled invocation, local repo research and enable policy |
| State-query response and external wrapper | Restored six-layer response with generic caller-supplied identity |
| External Memory Core | Read-only cue adapter plus source candidate bridge; profile, seeds, migration and instance-specific pilot belong to the consuming host |
| Work Memory and Skill Evolution | Restored source code as private-state libraries; explicit host integration only, no automatic registration or state creation on import |
| Operator UX | Restored task-index generator with explicit local paths; no prior generated dashboards/snapshots |
| Canonical contracts and task templates | Retained portable state, worker, memory and task discipline documents; historical source paths and personal axis references excluded |
| Source task runs, archives, rollout records and operational snapshots | Excluded: instance data, not reusable mechanisms |
| Identity, relationship/axis anchors, approved domain skills and service-specific posting adapters | Excluded: instance-specific identity, operational data or optional application integrations, not required backbone |
| Source-specific migration/pilot tools and historical personal references | Excluded; existing external memory implementation remains the authority |

Source corrections: per-file sensitive path and link checks in directory
research, read-only no-follow regular file reads, redact bounded text before
snippet slicing, no snippets from truncated text; require explicit private
work-memory hook storage; escape viewer task labels and retain evidence-based
completion conditions. These are narrow extraction/security changes, not a
new cognition engine. The repo reader is not a race-proof OS filesystem
sandbox and the secret scan is pattern-limited; use an enforced approved
execution boundary for untrusted work. The hook remains fail-open only for
candidate work memory, never for network security.

Validation: existing package and neutral source regression fixtures passed
536 tests before documentation packaging. The original credential-path
test was adapted to assert no read occurs without creating a credential-like
file (the local tool environment refuses such writes). Three positive worker
smokes observe the actual os.open read primitive; work-memory hook fixture
sets its synthetic database to 0600. No live-agent/browser/account testing.

The source-specific state store references, personal profile seeds and
application-specific integrations are not cloned. This is a portable
mechanism export, not byte-identical replication of all original instance
files. No source databases, account information, credentials, transcripts
or private Git history are distributed.
