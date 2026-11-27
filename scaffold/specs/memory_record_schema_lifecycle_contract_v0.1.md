# memory_record_schema_lifecycle_contract_v0.1.md

## 0. Purpose and Scope

This document defines the canonical schema and lifecycle contract for future Agent memory records.

It is a docs/spec document only.
It does not implement memory runtime.
It does not grant memory authority.
It does not create autonomous memory behavior.

Memory remains evidence substrate only.
Memory supports continuity and auditability, but memory does not become the spine.

---

## 1. Record Family Overview

Agent memory records are separated into three primary record families.

### 1. EventMemoryRecord

Purpose: record that something happened.

An event is an occurrence record, not an interpretation record.
An event preserves provenance and supports later review, but it does not become belief or axis by itself.

### 2. BeliefMemoryRecord

Purpose: record an inferred pattern from multiple events.

A belief is a synthesis record.
It summarizes a pattern suggested by evidence, and it remains revisable.

### 3. AxisMemoryRecord

Purpose: record an approved canonical operating direction, identity-direction, or return-law.

An axis is a canonical direction record.
It requires explicit approval and audit visibility.

### Core law

```text
event ≠ belief ≠ axis
```

Definitions:
- Event = something happened.
- Belief = inferred pattern from evidence.
- Axis = approved canonical operating direction / return-law.

No record family may silently collapse into another family.

---

## 2. Shared Base Fields

Every durable memory record should share these fields:

- `memory_id`
- `record_type`
- `content`
- `impact`
- `source`
- `confidence`
- `authority_status`
- `lifecycle_status`
- `evidence_handles`
- `relation_handles`
- `created_at`
- `updated_at`
- `last_accessed_at`
- `access_count`
- `created_by`
- `last_reviewed_at`
- `review_status`

### Allowed values

`record_type`:
- `event`
- `belief`
- `axis`

`authority_status`:
- `candidate`
- `canonical`
- `deprecated`
- `invalidated`

`lifecycle_status`:
- `active`
- `inert`
- `blocked`
- `replaced`
- `review_required`

`review_status`:
- `unreviewed`
- `reviewed`
- `approved`
- `rejected`
- `needs_recheck`

### Base-field rules

- `authority_status` and `lifecycle_status` must not be silently changed by retrieval.
- `last_accessed_at` and `access_count` may be updated by retrieval in future implementation.
- `content`, `impact`, `confidence`, `authority_status`, `lifecycle_status`, canonical status, and replacement relation require explicit review/write path.
- `review_status` must reflect review state, not implied confidence.

---

## 3. EventMemoryRecord Schema

Purpose: record something that happened.

### Required fields

- `memory_id`
- `record_type = event`
- `event_kind`
- `content`
- `source`
- `timestamp`
- `evidence_handles`
- `impact`
- `confidence`
- `authority_status`
- `lifecycle_status`
- `relation_handles`

### Allowed `event_kind`

- `user_statement`
- `task_run`
- `file_change`
- `commit`
- `pull_request`
- `verification_result`
- `test_result`
- `system_observation`
- `model_report`
- `correction`
- `boundary_violation`
- `blocker`

### Rules

- Event memory records occurrence, not interpretation.
- One event must not become belief by itself.
- Event must not become axis by itself.
- Event should preserve provenance.
- If source is `user_reported`, mark source clearly.
- Event records may support later synthesis, but they do not settle meaning alone.

### Bad / Good

Bad:
"User said they prefer X, therefore stable preference belief exists."

Good:
"Event: user said X at time T. Possible preference candidate requires more evidence."

---

## 4. BeliefMemoryRecord Schema

Purpose: record an inferred pattern from multiple events.

### Required fields

- `memory_id`
- `record_type = belief`
- `belief_statement`
- `supporting_event_ids`
- `contradicting_event_ids`
- `evidence_handles`
- `confidence`
- `domain`
- `impact`
- `authority_status`
- `lifecycle_status`
- `created_at`
- `last_reviewed_at`
- `revision_history`

### Rules

- Belief requires more than one weak signal unless explicitly approved.
- Contradiction lowers confidence or creates `review_required`.
- Stale beliefs require review before high-stakes use.
- Belief cannot override verification.
- Belief cannot override task evidence.
- Belief cannot become axis without explicit approval.
- Belief must remain revisable.

### Confidence bands

Use meaning labels even if a future implementation also adds numeric confidence.

Allowed labels:
- `low`
- `medium`
- `high`

A future implementation may add numeric confidence, but the meaning band must remain explicit.

### Bad / Good

Bad:
"One user statement creates stable belief."

Good:
"One user statement creates event memory; belief requires more evidence or explicit approval."

---

## 5. AxisMemoryRecord Schema

Purpose: record approved canonical operating law / identity-direction / return-law.

### Required fields

- `memory_id`
- `record_type = axis`
- `axis_statement`
- `source`
- `approval_evidence`
- `approved_by`
- `approval_timestamp`
- `evidence_handles`
- `impact`
- `authority_status = canonical` unless deprecated/invalidated later
- `lifecycle_status`
- `replacement_relation` if any
- `last_reviewed_at`

### Rules

- Axis memory must be rare.
- Axis memory requires explicit approval/review.
- Axis memory must not be created from a single event.
- Axis memory must be visible in audit trail.
- Axis memory may guide behavior only when current and verified.
- Deprecated axis memory is inert by default.
- Invalidated axis memory is blocked by default.
- Axis memory cannot be silently rewritten.

### Boundary note

VHO interpretation cannot auto-promote into axis.
Lineage cannot auto-promote into runtime authority.
Memory cannot create identity law by itself.

### Bad / Good

Bad:
"VHO memory implies identity authority."

Good:
"VHO memory is interpretive context only unless explicitly approved as axis law."

---

## 6. Lifecycle State Machine

This section defines lifecycle transitions and their effective handling.

### Allowed `authority_status` transitions

- `candidate → canonical`
- `canonical → deprecated`
- `canonical → invalidated`
- `candidate → rejected / invalidated`
- `deprecated → historical_reference_only`
- `invalidated → blocked`

### Interpretation rule

`historical_reference_only` is an effective handling state for deprecated records, not a new authority enum in v0.1.
The stored authority values remain:
- `candidate`
- `canonical`
- `deprecated`
- `invalidated`

### Lifecycle handling

Use the simple lifecycle set:
- `active`
- `inert`
- `blocked`
- `replaced`
- `review_required`

### Transition table

| From authority_status | To authority_status | Effective lifecycle_status | Notes |
| --- | --- | --- | --- |
| candidate | canonical | active | Requires explicit approval |
| candidate | invalidated | blocked | Candidate rejected by evidence or review |
| canonical | deprecated | inert | Deprecated memory becomes inert by default |
| canonical | invalidated | blocked | Invalidated memory is blocked by default |
| deprecated | historical_reference_only | inert | Read-only historical handling; not active guidance |
| invalidated | blocked | blocked | Never active by default |

### Rules

- Deprecated memory becomes inert by default.
- Invalidated memory becomes blocked by default.
- Replacement must point to target via relation.
- Old anchor must not reactivate unless explicitly requested for historical comparison.
- Invalidated memory must never be used as active guidance.
- Canonical replacement must be audit-visible.

---

## 7. Relation Contract

Allowed relation types only:

- `supports`
- `contradicts`
- `replaces`
- `deprecated_by`
- `invalidates`
- `derived_from`
- `evidence_for`

### Relation fields

- `relation_type`
- `source_memory_id`
- `target_memory_id`
- `evidence_handle`
- `created_at`
- `created_by`
- `review_status`

### Rules

- Keep relation set minimal.
- No broad association graph.
- No emotional resonance relation.
- No autonomous connection discovery.
- No self-growing belief graph.
- Relations support hygiene only.

---

## 8. Retrieval Contract

Retrieval result must include:

- `query`
- `candidate_ids`
- `rank_or_similarity_score` if available
- `lifecycle_status`
- `authority_status`
- `blocked_status`
- `block_reason`
- `evidence_handles`
- `retrieval_note`

### Required retrieval note

"retrieval candidates only; not truth by itself"

### Rules

- Retrieval cannot decide truth.
- Retrieval cannot claim completion.
- Retrieval cannot create memory.
- Retrieval cannot rewrite memory.
- Retrieval cannot silently promote candidate to belief or axis.
- Invalidated memory blocked by default.
- Deprecated memory inert by default.
- Canonical memory still requires task relevance.

---

## 9. Write / Review Contract

Any future memory write or status change must have:

- `operation_type`
- `target_memory_id`
- `previous_state`
- `new_state`
- `evidence_handles`
- `actor_or_module`
- `approval_status`
- `timestamp`
- `reason`

### Allowed `operation_type`

- `create_event`
- `propose_belief`
- `approve_belief`
- `revise_belief`
- `create_axis`
- `approve_axis`
- `deprecate`
- `invalidate`
- `replace`
- `mark_accessed`

### Rules

- `mark_accessed` may only update `last_accessed_at` / `access_count`.
- `create_axis` / `approve_axis` requires explicit review.
- `deprecate` / `invalidate` requires reason and evidence.
- Replacement requires relation target.
- This is a future contract only; do not implement runtime mutation yet.

---

## 10. Data Source Classification

Every memory record or retrieval claim should preserve source type:

- `observed_now`
- `read_from_file`
- `user_reported`
- `retrieved_memory_candidate`
- `inferred_from_events`
- `approved_canonical`
- `unknown`

### Rules

- `user_reported` is not verified truth by itself.
- `retrieved_memory_candidate` is not truth.
- `inferred_from_events` must remain belief candidate unless approved.
- `approved_canonical` requires audit trail.

---

## 11. Interaction With Current Agent Architecture

Memory remains below:

- MainBrain
- M2 / verification
- Gate
- Governance

Memory may support:

- context
- evidence
- prior task continuity
- contradiction detection
- historical comparison

Memory may not:

- override synthesis
- override verification
- override side-effect permission
- override governance
- override axis
- bypass state-query boundary

Core line:

```text
memory supports the spine; memory does not become the spine.
```

---

## 12. Bad / Good Examples

Bad:
"Retrieved memory says X, so X is true."

Good:
"Retrieved memory suggests X. Authority status: candidate. Evidence handles: [...]. Needs task relevance check."

Bad:
"Old axis anchor appeared, so use it."

Good:
"Old axis anchor is deprecated_by Y and remains inert unless historical comparison is requested."

Bad:
"One user statement creates stable belief."

Good:
"One user statement creates event memory; belief requires more evidence or explicit approval."

Bad:
"Accessing memory updates confidence."

Good:
"Accessing memory may update last_accessed / access_count only. Confidence change requires review."

Bad:
"VHO memory implies identity authority."

Good:
"VHO memory is interpretive context only unless explicitly approved as axis law."

---

## 13. Anti-Drift Checkpoint

```text
CHECKPOINT: MEMORY-RECORD-SCHEMA-LIFECYCLE-v0.1
```

Memory records are separated into event, belief, and axis.
event ≠ belief ≠ axis.
Every durable memory needs content, impact, source, confidence, authority status, lifecycle status, and evidence handles.
Retrieval returns candidates only; retrieval is not truth.
Deprecated records are inert by default.
Invalidated records are blocked by default.
No silent reconsolidation.
Axis memory requires explicit approval and audit visibility.
Memory supports continuity but cannot become authority.
Memory supports the spine; memory does not become the spine.

---

## 14. Non-Scope

Do not build:

- runtime memory storage
- autonomous memory writes
- vector database
- retrieval engine
- graph memory
- self-updating belief loop
- emotional retrieval weighting
- cross-agent memory federation
- worker
- agent
- identity/personhood module
- consciousness detector

---

## 15. Acceptance Criteria

The spec is accepted only if it clearly states:

- EventMemoryRecord schema exists
- BeliefMemoryRecord schema exists
- AxisMemoryRecord schema exists
- shared base fields exist
- lifecycle statuses are defined
- relation contract is minimal
- retrieval contract says retrieval ≠ truth
- write/review contract exists but is not implemented
- no silent reconsolidation
- deprecated inert / invalidated blocked
- data source classification exists
- memory cannot override MainBrain / verification / gate / governance
- VHO cannot promote memory into identity
- lineage is not runtime authority
- no runtime code added
- no worker added
- canonical index updated if appropriate

---

## 16. Source Files Inspected

### Current repo source of truth


### Task-run references


### Additional inspection notes

- Existing canonical index structure and entry style were preserved.
- The memory hygiene spec and axis/state contracts were used as direct source alignment.

---

## 17. Boundary Confirmation

This canonical document:

- Does NOT modify identity.md
- Does NOT modify state_query_response_contract_v0.1.md
- Does NOT modify STATE_MEMORY_BOUNDARY.md
- Does NOT modify canonical_runtime_spine.md
- Does NOT implement runtime code
- Does NOT modify MainBrain, gate, monitor, memory runtime, or execution logic
- Does NOT add a new worker
- Does NOT stage or commit

Boundary confirmed: docs/spec only.

---

## 18. Warnings / Blockers

- This spec defines future contract only; runtime enforcement remains unimplemented.
- No memory runtime code was touched.
- The `deprecated → historical_reference_only` handling is specified as read-only lifecycle behavior, not as a new stored authority enum.
- Any future runtime alignment must preserve the authority boundary: memory remains evidence substrate only.
<!-- normalized-lf: task-029.1-memory-record-schema -->
