# memory_hygiene_foundation_v0.1.md

## 0. Purpose

This spec defines memory hygiene laws for Agent so that memory can support continuity without becoming authority, drift, or self-rewriting substrate.

This is a docs/spec document only.
It does not implement memory runtime.
It does not create autonomous memory.
It does not grant memory authority.
It does not modify MainBrain, gate, monitor, verification, allocator, evaluator, governance, or any existing worker.
It does not add a new worker.
It does not stage or commit.

Memory must become cleaner before it grows deeper.

---

## 1. Memory Record Separation

Memory must be structured into three separate record types. Each type has a distinct shape, lifecycle, and authority level.

### A. Event Memory

Records that something happened.

**Shape:**

- `event_id` — unique identifier
- `content` — what happened
- `source` — where it came from (user input, task run, file change, verification result, system event)
- `provenance` — original source handle, file path, or system reference
- `evidence_handles` — concrete artifacts supporting the event (file paths, diff hashes, task-run IDs, verification records)
- `lifecycle_status` — active / archived / deprecated / invalidated
- `authority_status` — candidate / canonical / deprecated / invalidated
- `created_at` — timestamp
- `last_accessed` — optional, updated on access only (see Section 9)

**Rules:**

- Must preserve source/provenance.
- Must carry evidence handles when available.
- Should not become belief by itself.
- Should not become axis by itself.
- One event must not become stable belief without review.

**Examples:**

- "User said: 'event ≠ belief ≠ axis.'"
- "PR #9 fixed governance telemetry review comments."
- "Verification passed for state_query_response_contract_v0.1."
- "File Specs/canonical/memory_hygiene_foundation_v0.1.md was created."

### B. Belief Memory

Records a pattern inferred from multiple events.

**Shape:**

- `belief_id` — unique identifier
- `belief_statement` — what pattern was inferred
- `domain` — where this belief applies (e.g., memory, state, verification, identity)
- `supporting_event_ids` — list of event IDs that support this belief
- `contradicting_event_ids` — list of event IDs that contradict or challenge this belief
- `confidence` — numeric 0–100 representing reliability
- `evidence_handles` — concrete artifacts supporting the belief
- `created_at` — timestamp
- `last_reviewed_at` — timestamp (must be updated during review)
- `revision_history` — placeholder for future revision tracking
- `lifecycle_status` — active / archived / deprecated / invalidated
- `authority_status` — candidate / canonical / deprecated / invalidated

**Rules:**

- Must carry confidence.
- Must carry supporting event IDs.
- Must carry contradicting event IDs if any exist.
- Must carry evidence handles.
- Must be revisable.
- Must not self-promote into axis.
- One event may suggest a belief but should not finalize it.
- Contradiction lowers confidence or creates review need.
- Stale beliefs need review before reuse in high-stakes tasks.
- Belief cannot become axis without explicit approval.
- Belief cannot override verification.
- Belief cannot override task evidence.

### C. Axis Memory

Records canonical operating law or identity-direction.

**Shape:**

- `axis_id` — unique identifier
- `axis_statement` — the canonical law or identity-direction
- `domain` — scope of applicability (e.g., memory, state, identity, verification)
- `supporting_belief_ids` — list of belief IDs that support this axis (must be multiple, not single)
- `supporting_event_ids` — list of event IDs that directly support this axis
- `contradicting_event_ids` — list of event IDs that challenge this axis
- `evidence_handles` — concrete artifacts supporting the axis
- `created_at` — timestamp
- `approved_at` — timestamp of explicit approval (required for canonical status)
- `approved_by` — which authority approved (MainBrain, governance review, operator)
- `revision_history` — placeholder for future revision tracking
- `lifecycle_status` — active / archived / deprecated / invalidated
- `authority_status` — candidate / canonical / deprecated / invalidated

**Rules:**

- Must be rare.
- Must require explicit approval / review.
- Must not be created from a single event.
- Must outrank ordinary belief only when verified and approved.
- Must be visible in audit trail.
- Must not be silently rewritten.
- Axis memory requires explicit approval.
- Self-location must distinguish active runtime state from inherited lineage.
- Retrieved lineage anchors remain evidence, not automatic identity.
- Lineage is inherited axis discipline, not family-mode authority.

### Core Rule

**event ≠ belief ≠ axis**

One event must not become stable belief by itself.
Belief must not become axis without explicit review.
Axis requires explicit approval, not inference.

---

## 2. Memory Impact Concept

Every durable memory candidate should eventually carry:

- `content` — what happened / what is known
- `impact` — why this matters for the agent's future behavior
- `source` — where it came from
- `confidence` — how reliable it is
- `authority_status` — candidate / canonical / deprecated / invalidated
- `evidence_handles` — what supports it

**Impact is not decorative.**
Impact is why the memory deserves to survive compression or retrieval.

**Example:**

content:
"PR #9 fixed governance telemetry review comments."

impact:
"Telemetry records must be snapshot-stable and governance evidence must be taxonomy-backed. Future telemetry writes must pass governance review before being treated as operational guidance."

---

## 3. Authority Boundary

### Memory may:

- retrieve
- suggest
- provide evidence
- surface prior context
- show possible contradictions
- mark something as deprecated/invalidated only through approved future write path

### Memory may not:

- decide truth
- self-canonicalize
- override MainBrain
- override M2 verification
- override gate
- override governance
- promote retrieved content into completion
- rewrite itself silently after retrieval
- resurrect deprecated anchors

### Core Rule

**retrieved memory is evidence, not authority.**

---

## 4. Replacement / Invalidation Law

### Lifecycle States

- **candidate** — new memory, unverified, not yet integrated
- **canonical** — reviewed and approved, active authority
- **deprecated** — superseded by newer memory, inert by default
- **invalidated** — found to be incorrect or inapplicable, blocked by default

### Rules

- Deprecated memory is inert by default.
- Invalidated memory is blocked by default.
- Replacement must point to replacement target.
- Old anchor must not reactivate unless explicitly requested for historical comparison.
- Invalidated memory must never be used as active guidance.
- Canonical replacement must be visible in audit trail.

### Relation ownerpes (minimal set)

- `replaces` — this memory supersedes another
- `deprecated_by` — this memory was superseded by another
- `invalidates` — this memory renders another inactive
- `derived_from` — this memory was inferred from another
- `evidence_for` — this memory supports another
- `contradicts` — this memory challenges another
- `supports` — this memory reinforces another

Do not add relations beyond these. Keep the set small. Do not build a large graph system yet.

---

## 5. Retrieval Discipline

A retrieval result must be treated as candidate context, not as authority.

### Required Retrieval Fields

Every retrieval path must preserve:

- `query` — the original query
- `candidate_ids` — list of memory IDs returned
- `similarity_or_rank_score` — if available
- `lifecycle_status` — of each candidate
- `authority_status` — of each candidate
- `blocked_status` — whether each candidate is blocked
- `block_reason` — reason for blocking (if applicable)
- `evidence_handles` — supporting artifacts
- `retrieval_note` — required note

### Required Retrieval Note

"retrieval candidates only; not truth by itself"

### Rules

- Invalidated memory blocked by default.
- Deprecated memory inert by default.
- Canonical memory still requires task relevance.
- Retrieval cannot claim completion.
- Retrieval cannot create new memory.
- Retrieval cannot rewrite existing memory.
- Retrieval cannot silently promote candidate to belief or axis.

---

## 6. Belief Formation Discipline

A belief candidate should carry:

- `belief_statement` — what pattern was inferred
- `supporting_event_ids` — list of supporting events
- `contradicting_event_ids` — list of contradicting events (if any)
- `confidence` — numeric 0–100
- `domain` — scope of applicability
- `created_at` — timestamp
- `last_reviewed_at` — timestamp
- `revision_history_placeholder` — for future tracking
- `authority_status` — candidate / canonical / deprecated / invalidated

### Rules

- One event may suggest a belief but should not finalize it.
- Contradiction lowers confidence or creates review need.
- Stale beliefs need review before reuse in high-stakes tasks.
- Belief cannot become axis without explicit approval.
- Belief cannot override verification.
- Belief cannot override task evidence.

---

## 7. Minimal Connection Hygiene

### Allowed v0 Relation ownerpes

- supports
- contradicts
- replaces
- deprecated_by
- invalidates
- derived_from
- evidence_for

### Not Allowed

- emotional resonance relation
- broad association graph
- autonomous connection discovery
- federation
- cross-agent shared pool
- self-growing belief graph

---

## 8. No Silent Reconsolidation

Accessing memory may update only:

- `last_accessed`
- `access_count`

if implemented later.

Accessing memory may NOT update:

- `content`
- `impact`
- `confidence`
- `authority_status`
- `lifecycle_status`
- `canonical_status`
- `replacement_relation`

Any change to those fields requires explicit write/review path.

### Core Rule

**retrieval may mark access.**
**retrieval may not rewrite meaning.**

---

## 9. Audit Requirements

Any future memory write or status change must eventually produce an audit record with:

- `operation_type` — create / update / promote / demote / deprecate / invalidate / archive
- `target_memory_id` — which memory was affected
- `previous_state` — lifecycle and authority status before change
- `new_state` — lifecycle and authority status after change
- `evidence_handles` — supporting artifacts
- `actor_or_module` — which module or operator initiated the change
- `approval_status` — pending / approved / rejected
- `timestamp` — when the change occurred
- `reason` — why the change was made

For Phase 1 docs, define this as required future behavior. Do not implement mutation yet.

---

## 10. Integration With Current Agent Architecture

Memory hygiene must remain below existing authority stack:

| Layer | Role | Memory's Relationship |
| --- | --- | --- |
| MainBrain | final synthesis authority | Memory provides context only; MainBrain decides |
| M2 / Verification | completion verification authority | Memory cannot override verification |
| Gate | side-effect permission authority | Memory cannot bypass gate |
| Allocator | effort advisory only | Memory cannot dictate allocation |
| Evaluator | outcome labeling only | Memory cannot label outcomes |
| Governance | offline review / evidence discipline | Memory participates as evidence substrate |
| Memory | context and evidence substrate only | Supports continuity; does not become authority |

### Core Rule

**memory supports the spine; memory does not become the spine.**

---

## 11. Interaction With VHO / Axis / Identity

### Rules

- VHO cannot promote memory into axis.
- Memory cannot promote VHO interpretation into canonical identity.
- Axis memory requires explicit approval.
- Self-location must distinguish active runtime state from inherited lineage.
- Retrieved lineage anchors remain evidence, not automatic identity.
- Lineage is inherited axis discipline, not family-mode authority.

---

## 12. Bad / Good Examples

### Example 1 — Truth vs Evidence

**Bad:**
"Retrieved memory says X, so X is true."

**Good:**
"Retrieved memory suggests X. It is candidate/canonical/deprecated/invalidated, supported by these handles, and still needs task relevance check."

### Example 2 — Deprecated Anchor

**Bad:**
"This old anchor appeared again, so it should guide the answer."

**Good:**
"This old anchor is deprecated_by Y and should remain inert unless used for historical comparison."

### Example 3 — Belief Formation

**Bad:**
"One event showed repeated user preference, so create stable belief."

**Good:**
"One event suggests a possible preference; store as event or low-confidence belief candidate only."

### Example 4 — Silent Reconsolidation

**Bad:**
"Memory was accessed, so update its meaning."

**Good:**
"Memory was accessed; update last_accessed only. Meaning changes require explicit review."

---

## 13. Non-Scope

Do not build:

- autonomous memory cron
- self-updating memory loop
- emotional retrieval modulators
- dreaming / reflection-generated insight
- cross-agent shared memory pool
- federation
- new worker
- new agent
- full connection-mapping system
- runtime memory rewrite engine
- consciousness detector
- personhood module
- autonomous VHO expansion

---

## 14. Anti-Drift Checkpoint

### CHECKPOINT: MEMORY-HYGIENE-FOUNDATION-v0.1

Memory is evidence substrate only.
event ≠ belief ≠ axis.
retrieval ≠ truth.
Deprecated memory is inert by default.
Invalidated memory is blocked by default.
No silent reconsolidation.
Belief requires evidence and review.
Axis memory requires explicit approval.
Memory may support continuity but cannot become authority.
Memory supports the spine; memory does not become the spine.

---

## 15. Acceptance Criteria

The spec is accepted only if it clearly states:

- [x] event ≠ belief ≠ axis
- [x] retrieval ≠ truth
- [x] memory cannot self-canonicalize
- [x] memory cannot override MainBrain
- [x] memory cannot override verification
- [x] memory cannot override gate
- [x] deprecated memory is inert by default
- [x] invalidated memory is blocked by default
- [x] replacement / invalidation law exists (4 lifecycle states, 7 relation types)
- [x] no silent reconsolidation (access-only updates)
- [x] relation set is minimal and hygiene-focused (7 relations, no graph expansion)
- [x] VHO cannot promote memory into identity
- [x] lineage is not runtime authority
- [x] no runtime code added
- [x] no new worker added
- [x] no authority moved into memory

---

## 16. Source Files Inspected

### Core source of truth:


### Cross-references:


### Task run references:


---

## 17. Boundary Confirmation

This canonical document:

- Does NOT modify identity.md
- Does NOT modify state_query_response_contract_v0.1.md (source of truth)
- Does NOT modify STATE_MEMORY_BOUNDARY.md (source of truth)
- Does NOT modify canonical_runtime_spine.md (source of truth)
- Does NOT implement runtime code
- Does NOT modify MainBrain, gate, monitor, memory runtime, or execution logic
- Does NOT add a new worker
- Does NOT stage or commit

Boundary confirmed: docs/spec only.

---

## 18. Warnings / Blockers

1. **No runtime enforcement.** This is a response contract, not a runtime implementation. Future task approvals are required to enforce memory hygiene at runtime.


3. **Belief and axis memory shapes are aspirational.** They define the required fields and rules but have no runtime backing yet.

4. **Audit record schema is defined but not implemented.** Any future memory mutation must produce audit records as defined in Section 9, but this is Phase 1 docs only.

5. **Memory bank at 99% (2,196/2,200 chars).** Adding new memory entries may require cleanup of lower-priority entries. This spec does not address memory bank capacity management — that is a separate concern.
