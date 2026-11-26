# Shared agent backbone export

This pack is an extraction of an existing Hermes-based agent's operating
scaffold and runtime modules, not a replacement inference engine. The
host owns its original model/turn loop. The agent instance loads the
boot adapter and canonical operating laws, retrieves bounded candidate
memory on each turn, and uses the shared state/monitor/allocator,
verification, sleep/wake and worker contracts.

The scaffold directory contains neutral startup templates and the
original canonical spine and timing/snapshot specs, with personal
identifiers removed. The runtime package retains the portable original
helpers and the independently reviewed bounded execution subsystem.
The original security, worker envelope and evidence helpers are
included as policy/validation helpers, not as unrestricted execution.

Memory recall uses the existing external Memory Core library via its
ConsumerMemory API. The adapter takes an explicitly selected private
database and generic profile, ships no seed records, never initializes
or migrates a database, and retrieves without access telemetry.
The caller owns the instance binding and any memory writes. Private
memory and work state are not part of this repository.

MCP is optional tool transport. Preserve the host's working model and
inference loop. Use boot files at the instance boundary; helper functions
alone are not proof that a host invokes or enforces them at every required
seam.

The four bundled execution extensions (Docker worker, mTLS gateway, MCP
transport and SQLite activity ledger) are opt-in. Follow
[INSTALL.md](INSTALL.md) and [AI installer instructions](../AGENTS.md);
default to all off. The current MCP executable requires its activity
ledger and a configured backend for useful operations. Ask the owner to
resolve dependencies explicitly. The shared laws remain mandatory even
with all extensions declined.

## Security law

The network/data law extends the existing canonical spine. The tested
offline-worker and authenticated read-gateway paths are bounded actual
enforcement. Network-enabled host/browser containment requires a
separately enforced OS or sandbox boundary and acceptance on that
boundary; do not run those paths under a claim of protection until
qualified. This is prevention of accidental exposure, not service
restriction evasion or an anonymity guarantee.

## Distribution

No instance identity files, operator profile, private memory database,
seeds, credentials, transcript, original private Git history, or live
configuration is imported. The bundled governance library retains its
MIT notice. The external Memory Core project is separately licensed.

The Memory Core implementation is maintained separately in the public
trajecta-identity-memory project (https://github.com/tamvi-journal/trajecta-identity-memory).
The local extraction smoke used the existing installed Memory Core API;
compatibility with a different installed version is an integration concern,
not a reason to re-test the original agent.
