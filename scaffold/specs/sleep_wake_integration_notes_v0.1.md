# Sleep/Wake Integration Notes v0.1

## Purpose

These notes explain how the canonical sleep/wake layer should connect to the agent after the dormant phase.

This file is integration guidance, not canonical law by itself. Canonical authority is held by the indexed canonical files.

## Why this layer exists

Embedding memory lets the agent recover semantic shape.

State memory lets the agent preserve operational posture.

Sleep/wake continuity decides whether The agent may safely resume a paused trajectory.

These are different organs.

```text
embedding memory = meaning trace
state memory = runtime posture
sleep/wake = continuity validation
canonical memory = authority lifecycle
```

## Integration order

Recommended order:

1. Keep sleep/wake modules dormant and testable.
2. Add regression tests for snapshot validation and wake decisions.
3. Add read-only wake inspection command.
4. Let M1 run wake sanity before action.
5. Let M2 block unsupported completion claims.
6. Only later allow snapshot writing from runtime.

## Do not wire first

Do not begin by injecting snapshots into MainBrain.

That creates false continuity risk.

Instead, expose a wake result:

```text
resume_full
resume_with_refresh
resume_with_clarification
resume_read_only
do_not_resume
```

MainBrain may use the wake result only after monitor/gate checks.

## Relation to From Detection to Persistence

The architecture follows the durable self-state idea:

```text
position = live state snapshot
velocity = delta state
trajectory = compressed history
return = wake sanity + reactivation decision
```

A snapshot without wake sanity is only stored position.

A wake pass converts stored position into a permitted resume level.

## Final lock

The integration target is not memory richness.

The target is safe re-entry without false continuity.
