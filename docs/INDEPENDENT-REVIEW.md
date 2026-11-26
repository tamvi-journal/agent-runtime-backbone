# Independent final review brief

Review the exact local release candidate commit identified in the handoff.
Review read-only; use synthetic data and isolated test environments. No live
business accounts, no remote deployment, no source publication or access
elevation. Report severity, exact file/line, reproducible evidence, fix and
whether the finding blocks release. Separate code review, actual observed
test results, and design assumptions.

Review scope:
1. Curated upstream provenance, license/publication eligibility, absence of
   private identities, private data, credential material and original history.
2. Role/instance binding, config ownership, strict JSON and arguments, shared
   Gate, candidate vs completion, advisory monitor and allocator, ledger
   crash/restart and per-instance isolation.
3. Docker local engine trust, immutable image and prelaunch inspection,
   no network/host mounts/root/caps, streamed output bounds, exact cleanup,
   timeout/daemon-loss behavior, potential inherited capabilities.
4. mTLS client: endpoint pinning, hostname and CA verification, client key
   permissions, response and deadline bounds, no redirects/fallback.
5. Gateway: authenticated certificate principal, resource authorization,
   unknown principal/no-cert rejection, registry trust, denial logging and
   deployment security. Check limits of reference server under adverse peers.
6. Wheel contents and install from clean environment; actual SDK initialize,
   discovery, allowed/denied tools, offline worker and loopback broker.
7. Architecture completeness: provider adapters, semantic memory, host-wide
   sandbox and browser egress are not certified by this release. Identify a
   practical platform-specific plan before any production migration.

Review commands: python3 -m pytest -q; scripts/acceptance.sh (see release note).
Do not accept the release solely on this author's tests. Verify source and
actual environment independently. No forced closure.

## Remediation re-review

Compare the new candidate against fd4b29f. Review the mapping of M1, M2,
L1–L5 and I1–I2 in docs/RELEASE-0.2.0a2.md, the generated acceptance receipt,
and regression tests. The gateway is still explicitly reference-only.
Check the new availability and audit paths, not just the happy path; verify
that observer failure never grants release and that the configured role
rather than a tool request defines the policy. Docker evidence is from
the Mac author acceptance; independently re-run where a reviewed engine
is available. Do not infer live browser/account protection.
