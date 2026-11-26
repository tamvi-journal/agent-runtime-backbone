# Monitor Position Canonical v0.1

## Purpose

This canonical file defines where the agent's monitors sit in the runtime spine.

A monitor is not the actor.
A monitor is not MainBrain.
A monitor is not a worker.
A monitor is not canonical memory.

A monitor observes boundary conditions, flags drift, and can block or downgrade claims when the evidence does not support completion.

## Three monitor positions

### M1 — Preflight Monitor

Position:

```text
request_router
→ M1 Preflight Monitor
→ execution_gate
```

Function:
- classify route risk
- check scope
- detect stale task/context
- prevent unsafe side effects before execution
- confirm required evidence inputs are available

M1 can recommend:
- allow
- sandbox_only
- needs_approval
- deny
- clarify_scope

### M2 — Commit Monitor

Position:

```text
worker / tool result
→ M2 Commit Monitor
→ final synthesis / memory write / completion claim
```

Function:
- compare intended action vs observed outcome
- block unsupported completion claims
- downgrade confidence
- prevent canonical promotion without evidence
- prevent memory mutation without gate permission

M2 is the most important monitor for repo hygiene.

M2 can say:

```text
implemented_but_unverified
partial_completion
completion_claim_blocked
evidence_gap_detected
```

### M3 — Observability Mirror

Position:

```text
final output
→ M3 Observability Mirror
→ task-run record / viewer / audit trace
```

Function:
- expose what happened
- record route/gate/status
- preserve audit handles
- support later review

M3 cannot change the completed action. It records and displays.

## Non-authority rule

Monitors do not decide truth.

They decide whether the current evidence permits a claim, commit, memory write, or resume state.

## Wake interaction

On wake, M1 must run before resume.

M2 must run before claiming that a resumed task is complete.

M3 must record the wake result.

## Failure markers

Monitor failure exists when:
- final answer claims completion without evidence,
- stale tool handles are treated as live,
- restored snapshot is treated as full continuity,
- semantic memory candidate is treated as truth,
- worker output overrides MainBrain,
- canonical promotion skips gate review.

## Final lock

Monitor is a boundary organ.

It protects the agent from fluent false continuity.
