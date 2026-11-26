# Wake Sanity Pass Canonical v0.1

## Purpose

Wake sanity pass prevents false continuity.

A restored snapshot is only a candidate for resumption. It is not proof that the runtime, tools, repo, task, or memory state are still valid.

## Core flow

```text
sleep_snapshot
→ validate_snapshot_shape
→ check_identity
→ check_task_scope
→ check_stale_handles
→ check_governance_state
→ decide_resume_level
```

## Required checks

### 1. Snapshot shape

The snapshot must include all required fields from `sleep_snapshot_schema_v0.1`.

Missing required fields block `resume_full`.

### 2. Identity check

Wake must compare:

- expected agent name
- expected role
- expected lineage
- expected runtime version if applicable

Mismatch returns `do_not_resume` or `resume_with_clarification`.

### 3. Task scope check

Wake must verify that the current user request still matches the slept task.

If task intent changed, resume must downgrade.

### 4. Stale handle check

Any tool handle, branch, commit, PR, issue, temp file, or external reference marked stale-sensitive must be refreshed before full resume.

If refresh is unavailable, resume must downgrade.

### 5. Governance check

Wake must preserve any existing gate restrictions.

A sleep/wake cycle must not erase:

- `needs_approval`
- `sandbox_only`
- `deny`
- incomplete verification
- forbidden claims

## Resume levels

### `resume_full`

Allowed only when:
- identity matches,
- task scope matches,
- no required handle is stale,
- gate state permits continuation,
- verification state is compatible.

### `resume_with_refresh`

Use when:
- identity and scope match,
- but stale-sensitive handles require refresh.

### `resume_with_clarification`

Use when:
- task scope is ambiguous,
- user intent may have changed,
- snapshot is coherent but insufficient.

### `resume_read_only`

Use when:
- state can be inspected,
- but side effects are not permitted.

### `do_not_resume`

Use when:
- identity mismatch is material,
- snapshot is invalid,
- governance state blocks action,
- or the task should be restarted instead of resumed.

## Final lock

Wake does not restore continuity.

Wake tests whether continuity may be safely resumed.
