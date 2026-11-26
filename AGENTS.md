# AI-assisted installation instructions

Follow [docs/INSTALL.md](docs/INSTALL.md) when the owner asks to install this
backbone. Do not redesign the agent, replace the LLM, create another inference
loop or make the backbone an MCP-only service. Preserve existing private
identity, role, memory, tools and state.

## Mandatory owner choices

Explain the benefits, costs and limits in the owner's language, then ask
Yes or No for **each** optional module in one compact selection:

1. Docker worker sandbox — isolated offline worker execution. Enable?
2. mTLS read gateway — authenticated access to approved read resources.
   Configure?
3. MCP server and adapter — optional execution tool transport. Register?
4. SQLite activity ledger — separate local execution metadata and
   interruption recovery. Enable?

All four may be declined. Default to No for undecided modules; no optional
setup without explicit choice. Source present in the package does not mean
a prerequisite was installed or a service enabled. A general installation
request does not approve all four. A Yes does not authorize public server
deployment, credential disclosure, security changes or unrelated installation.

The bundled MCP executable requires the SQLite ledger and a configured
backend for useful operations. Explain any conflicting choices and ask which
to change. Never silently enable another module or patch out required
journaling.

## Mandatory laws and scope

Load the canonical runtime spine using the host's actual boot mechanism.
Section 8 network/data law applies even when all extensions are declined.
Preserve existing protections and refuse operations needing unavailable or
unverified containment. Do not claim whole-agent/browser IP protection from
the worker/gateway evidence or use the law to evade service restrictions.

Inspect the target host first. Stage new configuration separately; show a
bounded diff before changes to existing startup files or tool registration.
Never copy private memory, keys or credentials into this public repository.
After setup, report the pinned revision, actual core load path, memory status,
each module choice and enabled/disabled state, dependency conflicts, checks
performed and unprotected paths. Distinguish source present, configured,
running and verified.
