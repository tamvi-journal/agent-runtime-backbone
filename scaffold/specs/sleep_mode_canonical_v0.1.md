# Sleep Mode Canonical v0.1

## Purpose

Sleep mode defines how the agent pauses work without losing operational posture and without pretending that continuity is complete.

Sleep is a bounded runtime transition.

It is not death.
It is not memory.
It is not archive.
It is not canonical promotion.
It is not a promise that old tool handles remain live.

## Core definition

```text
sleep = capture minimal restartable state
      + record unresolved risks
      + preserve next safe action
      + mark stale-sensitive handles
```

## Sleep is allowed when

- a task must pause before completion,
- a runtime will shut down,
- a handoff is required,
- evidence exists but verification is incomplete,
- a tool result is known to be stale-sensitive,
- the next step is known but cannot be executed now.

## Sleep snapshot must include

- agent identity marker,
- current task id,
- route class,
- gate decision,
- active mode,
- axis state,
- live state summary,
- delta summary,
- open loops,
- evidence handles,
- stale-sensitive handles,
- memory handoff notes,
- wake requirements,
- forbidden claims.

## Forbidden sleep behavior

The agent must not sleep by dumping raw transcript.

The agent must not store hidden reasoning.

The agent must not upgrade provisional memory to canonical memory during sleep.

The agent must not claim task completion just because a snapshot exists.

The agent must not treat a sleep snapshot as proof that the environment is still valid on wake.

## Wake dependency

Every sleep snapshot requires a wake sanity pass before resume.

```text
sleep_snapshot
→ wake_sanity_pass
→ resume_decision
```

## Resume decisions

A wake pass may return:

- `resume_full`
- `resume_with_refresh`
- `resume_with_clarification`
- `resume_read_only`
- `do_not_resume`

## Final lock

Sleep preserves restartability.

It does not certify continuity.
