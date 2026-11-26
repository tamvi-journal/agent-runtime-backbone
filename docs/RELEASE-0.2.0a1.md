# v0.2.0a1 — local integration candidate, 2026-11-26

## Accepted local scope

- Common role-neutral source from the pinned governance and runtime repositories.
- Local registered offline operations and read gateway behind the common Gate.
- Instance configuration, isolated metadata ledger, role-specific MCP
  discovery and real SDK transport.
- Immutable Docker fixture, pre-start isolation checks, bounded streams,
  separate monitor/allocator summaries and no automatic verification.
- Pinned mutual-TLS gateway client and reference server with client/resource
  access policy; only synthetic local endpoints used during tests.

## Reproduce

Use Python 3.11+, pytest and uv. Docker must be running with a reviewed
local python:3.11.15-slim-bookworm image (no automatic pulls). Use an installed
MCP 1.26.0 SDK client environment, e.g. an existing Hermes dev environment.
Run from repo root:

    MCP_CLIENT_PYTHON=/absolute/sdk/venv/bin/python sh scripts/acceptance.sh

No real accounts, secrets or third-party gateways are necessary. The TLS
fixture generates test-only certificates inside a disposable read-only
network-none container, not on the host. The source bind mount is developer
test-only and read-only, never a production worker mount.

## Corrections and limits

Host test key creation was blocked by the existing secret-file boundary;
the TLS tests moved into a disposable container without changing host
permissions. Initial isolated package build failed due to uncached hatchling;
the pinned standard build backend was then resolved in an isolated build
environment. The initial SDK test mistakenly resolved the virtualenv Python
symlink to the base interpreter; preserving the venv executable path fixed it.

No production agent profile, original repo, actual commerce browser or gateway
was modified. No external account or provider was tested. The real Hermes
agent configuration was not installed; the actual MCP SDK used by its
environment was used for a subprocess integration test. Full agent process
containment, browser egress, real data adapters, authenticated verifier,
durable semantic memory and independent security review remain separate
release gates. Public distribution requires private-source rights review.
