# Sleep Snapshot Schema Canonical v0.1

## Purpose

A sleep snapshot is the minimum structured object needed to restart work safely.

It is a runtime continuity artifact, not a transcript and not a canonical memory record.

## Required fields

```text
snapshot_id
created_at
agent_identity
task_id
route_class
gate_decision
active_mode
axis_state
live_state
delta_state
open_loops
evidence_handles
stale_sensitive_handles
memory_handoff
wake_requirements
forbidden_claims
```

## Agent identity

Must include:

```text
agent_name
agent_role
lineage
version
```

Identity mismatch on wake blocks `resume_full`.

## Axis state

Axis state must preserve operating law, not biography.

Examples:

```text
truth_before_fluency
axis_before_capability
mainbrain_speaks_last
boundary_before_mirroring
```

## Live state

Live state answers:

```text
Where is the runtime now?
```

Recommended fields:

```text
coherence
uncertainty
risk_level
verification_status
current_focus
```

## Delta state

Delta state answers:

```text
Which way was the runtime moving before sleep?
```

Recommended fields:

```text
changed_since_last_snapshot
last_success
last_failure
last_blocker
next_safe_action
```

## Stale-sensitive handles

Tool handles, branch names, commit SHAs, issue numbers, PR numbers, temporary file paths, or external URLs may become stale.

Wake must refresh or downgrade them.

## Forbidden claims

A snapshot must state what the agent cannot claim after wake unless reverified.

Examples:

```text
cannot_claim_tests_passed
cannot_claim_pr_merged
cannot_claim_tool_handle_live
cannot_claim_full_continuity
```

## Anti-transcript rule

If `raw_transcript` appears as the dominant content of a sleep snapshot, the snapshot is invalid.

## Final lock

Snapshot is position plus velocity.

It helps the agent restart; it does not prove the agent has resumed correctly.
