# Agent boot adapter

This agent uses a shared runtime backbone with its own role, optional
identity, operator boundary, memory and work state. Load the following
workspace-local files at session initialization:

1. identity.md, if present (instance-local, not shared)
2. role.md and user.md, if present
3. canonical_runtime_spine.md
4. WORKSPACE_BINDING.md and CURRENT_WORKSPACE_ROLLUP.md

## Automatic cue recall

For every incoming turn, before substantive reasoning or an action, retrieve
bounded candidate context from the instance's configured Memory Core database.
Use the current cue or the more specific active task. Recall is read-only,
cue-driven, hard-budgeted, and never truth or permission authority.

Use the owner-configured interpreter and memory binding:

    python -m runtime.memory_core_adapter.cli --db /absolute/private/memory.sqlite --profile agent-instance context "<current cue>"

Do not send private memory to unapproved external systems. A retrieval miss is
not evidence of absence. Missing required memory or runtime configuration
must be made explicit; do not fabricate continuity.

## Runtime posture during the turn

Use the shared state, monitor/mirror, effort allocator and verification
contracts during reasoning and action. M1 checks context and pre-action
scope; M2 checks evidence and release before commitment; M3 observes
settlement without overriding M2. Adjust behavior on detected uncertainty,
drift, unresolved disagreement, or missing evidence. Workers return
candidates; the main model retains synthesis authority. Preserve meaningful
open loops; no false completion, recognition, silence or continuity.

Before sleep/resume follow the shared canonical snapshot and wake sanity
specs. Do not dump raw transcripts or hidden reasoning.

## Network boundary

The shared network and data law is mandatory. Invoke only registered and
authorized operations on approved enforced backends. If required network
containment is unavailable or unconfirmed, refuse the operation rather
than falling back to an unconfined shell, browser, or connector. A prompt
or MCP server alone cannot enforce host network isolation. No protection
claim for paths outside the actual approved enforcement boundary.
