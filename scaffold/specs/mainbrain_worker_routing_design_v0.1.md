# MainBrain Worker Routing Design v0.1

## 1. Purpose

Define how MainBrain decides whether to invoke a worker for bounded candidate evidence.

```text
MainBrain may decide to invoke a worker, but may not delegate authority to the worker.
```

```text
Routing decides whether to ask for candidate evidence; it does not decide truth, completion, side effects, or governance.
```

Clarifications:
- MainBrain is the synthesis authority.
- Worker routing is evidence acquisition.
- Worker output remains candidate contribution.
- Routing is not verification.
- Routing is not governance.
- Routing is not Gate.
- Routing is not memory authority.
- Routing is not autonomous agent delegation.

---

## 2. Relationship to Worker Spine

This design is bound to the landed worker spine from Tasks 031–039:

- Task 031 — Worker Architecture Boundary Canonical
- Task 032 — Repo Research Worker Spec
- Task 033 — Safe Agent Profile Canonical
- Task 034 — Worker Invocation Envelope Canonical
- Task 035 — Worker Invocation Preflight Guard Design
- Task 036 — Preflight Guard Runtime Helper
- Task 037 — Repo Research Worker Runtime Prototype
- Task 038 — Controlled Worker Invocation Path
- Task 039 — Controlled Invocation Smoke Test

Required chain:

```text
MainBrain routing decision
→ WorkerInvocationEnvelope
→ Preflight Guard
→ Controlled Invocation
→ Repo Research Worker
→ WorkerOutputPacket candidate-only
→ MainBrain synthesis
```

---

## 3. Non-Authority Law

Repeat and apply:

- Worker ≠ authority.
- Worker output = candidate contribution.
- MainBrain/Agent synthesis remains final synthesis authority.
- Gate controls side effects.
- Verification controls completion.
- Governance controls evidence/review discipline.
- Memory/retrieval remain candidate context only.

For routing specifically:

- Router ≠ MainBrain.
- Router ≠ worker.
- Router ≠ Gate.
- Router ≠ Verification.
- Router ≠ Governance.
- Router ≠ Memory authority.
- Router cannot claim task completion.
- Router cannot approve side effects.
- Router cannot mutate memory.
- Router cannot bypass Preflight Guard.
- Router cannot bypass Controlled Invocation.

---

## 4. Routing Scope v0.1

For v0.1, MainBrain routing may target exactly one worker:

```text
repo_research_worker / read_only_repo_research
```

Allowed route purpose:

```text
candidate_repo_evidence
```

Forbidden in v0.1:

- multiple workers
- worker-to-worker routing
- worker self-invocation
- subagent routing
- Hermes delegation
- hermes_subprocess
- open worker registry
- dynamic plugin loading
- arbitrary callable execution
- external network research
- money-touching routes
- memory mutation routes
- repo mutation routes

---

## 5. When MainBrain May Route to Repo Research Worker

MainBrain may request Repo Research Worker candidate evidence when:

- user/task asks where a file, spec, test, or runtime component is located
- MainBrain needs scoped repo evidence before answering
- MainBrain needs file existence confirmation
- MainBrain needs content snippets from approved paths
- MainBrain needs to inspect canonical/spec/runtime/test files in a bounded scope
- MainBrain needs to verify whether prior task artifacts exist
- MainBrain needs local evidence before proposing the next task
- MainBrain needs a read-only summary of scoped files

MainBrain must not route when:

- the task requires writing files
- the task requires commit/push/PR
- the task requires network/browser/download/package installation
- the task requires subagent/Hermes delegation
- the task requires trading/money-touching
- the task requires memory write/mutation
- the task requires verification completion
- the task requires governance approval
- the task requires side-effect approval

In those cases, routing must produce one of:

- no_worker_needed
- escalation_required
- blocked
- ask_MainBrain_for_different_plan

---

## 6. Routing Decision Outcomes

Define routing outcomes:

```text
no_worker_needed
route_repo_research_worker
needs_approval
blocked
invalid_request
```

Meanings:

### no_worker_needed

MainBrain can answer or proceed without worker evidence.

### route_repo_research_worker

MainBrain should build an envelope for Repo Research Worker.

### needs_approval

The request requires approval or a different gate before any worker invocation.

### blocked

The request asks for forbidden action.

### invalid_request

The request is underspecified or malformed.

---

## 7. Routing Input

Define conceptual input:

```yaml
MainBrainWorkerRoutingInput:
  task_id:
  user_request:
  mainbrain_intent:
  requested_evidence:
  candidate_paths:
  forbidden_paths:
  side_effect_intent:
  network_intent:
  money_touching_intent:
  memory_mutation_intent:
  model_provider_intent:
  runtime_surface_intent:
  current_repo_state_optional:
  prior_context_optional:
```

Rules:

- user_request is not enough by itself.
- mainbrain_intent must be declared.
- requested_evidence must be declared if worker is considered.
- candidate_paths must be explicit before routing to Repo Research Worker.
- ambiguous candidate_paths → invalid_request or no route.
- if evidence scope is too broad, route must be refused or narrowed.

---

## 8. Envelope Construction Requirements

If routing outcome is `route_repo_research_worker`, MainBrain must build an envelope with:

```text
worker_id: repo_research_worker
worker_type: read_only_repo_research
permission_class: read_only
security_profile: repo_read_only_no_network
execution_surface: direct_tool
side_effect_class: repo_read
money_touching: false
external_mutation: false
network_access: false
shell_access: false
```

Envelope must include explicit:

- invocation_id
- task_id
- requested_by
- invocation_purpose
- input_scope
- paths_allowed
- paths_excluded
- max_files
- max_bytes_per_file
- allowed_tools
- forbidden_tools
- auto_allowed_actions
- approval_required_actions
- blocked_actions
- model_provider_policy
- memory_context_policy
- verification_expectation
- governance_expectation
- output_contract
- return_path
- escalation_policy
- abort_conditions
- created_at

```text
MainBrain may build the envelope, but Preflight Guard decides whether the invocation may proceed.
```

---

## 9. Return Handling

When WorkerOutputPacket returns:

MainBrain may:

- read candidate findings
- cite evidence handles
- compare evidence with current context
- detect contradictions
- request Verification/Governance if needed
- synthesize a response or next task plan

MainBrain may not:

- treat worker output as truth
- treat worker output as completion
- treat worker output as verification
- treat worker output as governance approval
- treat worker output as permission for side effects
- silently write memory based on worker output
- promote findings into canonical decisions without review

```text
WorkerOutputPacket returns to MainBrain as evidence, not as authority.
```

---

## 10. Escalation Rules

Routing must escalate instead of invoking worker when:

- side_effect_intent is true
- external_mutation intent is true
- network intent is true
- shell intent is true beyond read-only design
- money_touching intent is true
- memory mutation intent is true
- model/provider change intent is true
- Hermes delegation/subagent intent is true
- worker scope exceeds allowed read-only boundaries
- candidate_paths are missing or unsafe
- request attempts worker self-invocation
- request attempts bypass of Controlled Invocation or Preflight Guard

Escalation target examples:

- Gate
- Verification
- Governance
- owner review
- future risk policy
- future task design

Do not implement escalation runtime in Task 040.

---

## 11. Block Rules

Routing must block if:

- request asks for forbidden runtime/network behavior
- request asks for worker to execute arbitrary code
- request asks for dynamic worker loading
- request asks for unknown worker execution
- request asks for download-and-execute
- request asks for money transfer/withdrawal
- request asks for bypassing Gate/Verification/Governance
- request asks for memory mutation by worker
- request asks for worker to approve itself
- request asks for worker to claim completion
- request asks for worker to route another worker

---

## 12. Routing Output Packet

Define conceptual output:

```yaml
MainBrainWorkerRoutingDecision:
  task_id:
  decision: no_worker_needed | route_repo_research_worker | needs_approval | blocked | invalid_request
  reasons:
  selected_worker:
    worker_id:
    worker_type:
  invocation_purpose:
  proposed_input_scope:
    paths_allowed:
    paths_excluded:
    research_question:
    max_files:
    max_bytes_per_file:
  required_envelope_fields:
  approval_required:
  blocked_reasons:
  limitations:
  next_step:
  generated_at:
```

Rules:

- routing decision is not worker output
- routing decision is not verification
- routing decision is not governance
- routing decision is not Gate approval
- routing decision must not execute anything by itself

---

## 13. Automation Boundary

Task 040 must preserve bounded autonomy.

```text
Automation is allowed only inside pre-approved envelope boundaries.
```

```text
MainBrain routing reduces repeated manual approval for read-only evidence, not for side effects.
```

Routing may become automatic only for:

- repo_read
- read_only
- repo_read_only_no_network
- direct_tool
- explicit paths_allowed
- candidate evidence only

Routing must not become automatic for:

- repo mutation
- external writes
- network research
- subagent delegation
- Hermes subprocess
- memory mutation
- money-touching
- trading
- model/provider changes

---

## 14. Workflow Network vs Runtime Network

```text
Workflow network ≠ runtime network.
```

Rules:

- Approved git workflow actions such as push/PR may use network only when explicitly approved by owner/Gate.
- Runtime worker code/tests must not use network unless a future envelope/security profile explicitly allows it.
- Repo workflow permission does not grant worker/runtime network permission.
- Worker/runtime network permission does not imply git workflow permission.

---

## 15. Anti-Drift Checklist

- Did MainBrain decide whether worker evidence is needed?
- Was routing limited to Repo Research Worker v0.1?
- Was an explicit envelope required?
- Did Preflight Guard remain mandatory?
- Did Controlled Invocation remain the only call path?
- Did worker output remain candidate-only?
- Did routing avoid verification/completion claims?
- Did routing avoid governance approval claims?
- Did routing avoid side-effect approval?
- Did routing avoid memory mutation?
- Did routing avoid subagent/Hermes delegation?
- Did routing avoid network/runtime expansion?
- Did routing avoid money-touching/trading?
- Did routing preserve workflow network vs runtime network distinction?
- Did Task 041 remain not started?

---

## 16. Future Runtime Note

Task 040 is design/spec only.
Runtime implementation is out of scope for Task 040.

Future task candidates:

- Task 041 — MainBrain Worker Routing Runtime Helper v0.1
- Task 042 — Routing-to-Controlled-Invocation Integration Smoke Test
- Task 043 — Spec Draft Worker Design
- Future subagent/Hermes delegation requires separate delegation boundary, security profile, and approval path.
- Future trading/money-touching requires separate trading boundary, risk manager, execution gate, and paper-trading phase.
