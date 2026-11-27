# retrieval_discipline_candidate_context_contract_v0.1.md

## 0. Purpose and Scope

This document defines the canonical retrieval discipline contract for Agent.
It specifies how raw retrieval hits become bounded candidate context.

Core line:

```text
Retrieval candidates are evidence candidates, not truth.
```

This spec does not implement memory storage.
This spec does not implement live retrieval.
This spec does not grant retrieval authority.

Retrieval remains below MainBrain, verification, gate, governance, and axis law.
Memory supports the spine; memory does not become the spine.

---

## 1. Retrieval Boundary

Retrieval may:

- surface candidate context
- expose evidence handles
- expose lifecycle status
- expose authority status
- expose contradictions
- support task relevance checks
- support historical comparison

Retrieval may not:

- decide truth
- claim completion
- create memory
- rewrite memory
- promote event to belief
- promote belief to axis
- reactivate deprecated memory
- use invalidated memory as guidance
- override MainBrain
- override verification
- override gate
- override governance

Core rule:

```text
retrieval ≠ truth
```

---

## 2. Retrieval Candidate Shape

Define `RetrievalCandidate` with these fields:

- `candidate_id`
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
- `rank_or_similarity_score`
- `blocked_status`
- `block_reason`
- `retrieval_note`
- `task_relevance`
- `contradiction_status`
- `allowed_use`

### Allowed values

`blocked_status`:
- `allowed`
- `inert`
- `blocked`
- `review_required`

`task_relevance`:
- `relevant`
- `partially_relevant`
- `not_relevant`
- `unknown`

`contradiction_status`:
- `none_known`
- `contradicts_current_context`
- `contradicted_by_newer_record`
- `needs_review`
- `unknown`

`allowed_use`:
- `candidate_context`
- `historical_comparison_only`
- `evidence_reference_only`
- `blocked_do_not_use`
- `review_before_use`

Required retrieval note:

```text
retrieval candidates only; not truth by itself
```

---

## 3. Lifecycle Handling Rules

Rules:

- candidate records may be surfaced as `candidate_context` only
- canonical records may be surfaced only after task relevance check
- deprecated records are inert by default
- invalidated records are blocked by default
- replaced records must point to replacement target if relation exists
- historical comparison requires explicit user/task request
- blocked records must not influence answer synthesis

### Mapping

`authority_status` / `lifecycle_status` → `allowed_use`

- `candidate` / `active` → `candidate_context`
- `canonical` / `active` → `candidate_context` after relevance check
- `deprecated` / `inert` → `historical_comparison_only`
- `invalidated` / `blocked` → `blocked_do_not_use`
- `canonical` / `review_required` → `review_before_use`
- `candidate` / `review_required` → `review_before_use`
- `replaced` / `inert` → `historical_comparison_only` unless replacement is requested

---

## 4. Authority Boundary

Retrieval output must remain below:

- MainBrain
- M2 / verification
- Gate
- Governance
- Axis canonical

Retrieval may support but not decide.

Memory supports the spine; memory does not become the spine.

---

## 5. Candidate Context Packet

Define `RetrievalCandidateContextPacket` with:

- `query`
- `retrieval_timestamp`
- `retrieval_source`
- `candidates`
- `blocked_candidates`
- `contradiction_notes`
- `candidate_summary`
- `retrieval_note`
- `generated_by`
- `review_status`

Rules:

- Packet is a context object, not a truth object.
- Packet cannot claim completion.
- Packet cannot mutate memory.
- Packet must preserve blocked candidates separately.
- Packet summary must not erase lifecycle/authority distinctions.

---

## 6. Contradiction Handling

Rules:

- contradiction does not auto-delete memory
- contradiction creates `review_required` or lowers confidence in future implementation
- newer evidence does not silently invalidate older memory
- invalidation requires explicit write/review path
- contradiction must be surfaced in candidate packet

Bad:

```text
New result conflicts with old memory, so overwrite old memory.
```

Good:

```text
New result contradicts old memory. Mark contradiction_status=needs_review. No mutation occurs in retrieval path.
```

---

## 7. Deprecated / Invalidated Handling

### Deprecated

- inert by default
- may appear only under historical comparison or audit request
- cannot guide active output
- must show `deprecated_by` relation if available

### Invalidated

- blocked by default
- must not guide output
- may be listed only as blocked candidate for audit transparency
- must show `invalidates` / `invalidated_by` relation if available

---

## 8. No Silent Reconsolidation

Retrieval may update only in future implementation:

- `last_accessed_at`
- `access_count`

Retrieval may not update:

- `content`
- `impact`
- `confidence`
- `authority_status`
- `lifecycle_status`
- `canonical status`
- `replacement relation`
- `relation graph`
- `belief statement`
- `axis statement`

---

## 9. Data Source Discipline

Each candidate must preserve source type:

- `observed_now`
- `read_from_file`
- `user_reported`
- `retrieved_memory_candidate`
- `inferred_from_events`
- `approved_canonical`
- `unknown`

Rules:

- `user_reported` is not verified truth
- `retrieved_memory_candidate` is not truth
- `approved_canonical` still requires task relevance
- `unknown` source requires `review_before_use`

---

## 10. Optional Pure Helper Contract

A future/potential pure helper may transform input candidate dictionaries into bounded candidate context.

Suggested public API:

```python
def build_retrieval_candidate_context(
    query: str,
    raw_candidates: list[dict],
    *,
    retrieval_source: str = "provided_by_caller",
    generated_by: str = "retrieval_candidate_context_helper",
) -> dict:
    ...
```

Allowed behavior:

- classify `allowed_use` based on `authority_status` / `lifecycle_status`
- preserve evidence handles
- preserve relation handles
- add `retrieval_note`
- separate blocked candidates
- mark unknown values explicitly

Forbidden behavior:

- read memory store
- write memory store
- call shell
- query database
- mutate candidate input
- decide truth
- claim completion
- import MainBrain / gate / monitor / verification
- create new worker

The helper must be pure.

---

## 11. Bad / Good Examples

Bad:

```text
Retrieved memory says X, so X is true.
```

Good:

```text
Retrieved candidate suggests X. Authority status: candidate. Lifecycle: active. Allowed use: candidate_context. Needs task relevance check.
```

Bad:

```text
Deprecated anchor appeared, so use it.
```

Good:

```text
Deprecated anchor remains inert. Allowed use: historical_comparison_only.
```

Bad:

```text
Invalidated memory supports current answer.
```

Good:

```text
Invalidated memory is blocked_do_not_use and may only be shown for audit transparency.
```

Bad:

```text
Retrieval found contradiction, so update memory.
```

Good:

```text
Retrieval found contradiction; contradiction_status=needs_review. No mutation occurs.
```

Bad:

```text
Canonical memory automatically decides the answer.
```

Good:

```text
Canonical memory can support context after task relevance check, but MainBrain and verification remain authority.
```

---

## 12. Anti-Drift Checkpoint

```text
CHECKPOINT: RETRIEVAL-DISCIPLINE-CANDIDATE-CONTEXT-v0.1
```

Retrieval returns candidates, not truth.
retrieval ≠ truth.
retrieved memory is evidence, not authority.
Deprecated records are inert by default.
Invalidated records are blocked by default.
Canonical records still require task relevance.
Contradictions create review need, not silent overwrite.
Retrieval cannot create, rewrite, promote, or invalidate memory.
Retrieval cannot claim completion.
Memory supports the spine; memory does not become the spine.

---

## 13. Non-Scope

Do not build:

- live retrieval engine
- vector database
- memory storage
- memory write engine
- autonomous memory cron
- self-updating belief loop
- emotional retrieval weighting
- graph expansion system
- cross-agent shared pool
- worker
- agent
- identity/personhood module
- consciousness detector

---

## 14. Acceptance Criteria

The spec is accepted only if it clearly states:

- retrieval ≠ truth
- retrieval candidates are evidence candidates only
- `RetrievalCandidate` shape exists
- `RetrievalCandidateContextPacket` shape exists
- lifecycle handling rules exist
- deprecated inert / invalidated blocked
- canonical still requires task relevance
- contradiction handling exists
- no silent reconsolidation
- data source discipline exists
- optional helper contract is pure
- no runtime memory store created
- no vector DB created
- no memory writes added
- no worker added
- no authority moved into retrieval

Task-run audit scaffold must include:

- files created/modified
- source files inspected
- section summary
- acceptance criteria
- warnings/blockers
- boundary confirmation

---

## 15. Source Files Inspected

### Source of truth


### Task-run references


---

## 16. Boundary Confirmation

This canonical document:

- Does NOT implement runtime storage
- Does NOT implement live retrieval
- Does NOT grant retrieval authority
- Does NOT modify memory runtime
- Does NOT modify MainBrain, gate, monitor, verification, bridge, external wrapper, `src/`, or workers
- Does NOT add a vector DB, retrieval engine, memory write engine, autonomous memory loop, or federation
- Does NOT stage or commit

Boundary confirmed: docs/spec only.

---

## 17. Warnings / Blockers

- The optional helper is intentionally pure and bounded; it does not replace live retrieval.
- Retrieval discipline remains an evidence boundary, not an authority boundary.
- Any future live retrieval integration must preserve the same candidate-only contract.
