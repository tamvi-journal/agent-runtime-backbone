# Routing Decision to Envelope Builder Design v0.1

## 1. Purpose

Define how a MainBrain routing decision may be converted into a WorkerInvocationEnvelope.

```text
Envelope building converts a routing decision into permission shape, not authority transfer.
```

```text
The envelope builder may construct invocation permission, but Preflight Guard still decides whether execution may proceed.
```

Clarifications:
- routing decision chooses whether candidate evidence may be requested
- envelope builder constructs the bounded invocation shape
- Preflight Guard validates the envelope
- Controlled Invocation remains the only worker execution call path
- worker output remains candidate contribution
- envelope building is not worker execution
- envelope building is not verification
- envelope building is not governance
- envelope building is not Gate approval
- envelope building is not memory authority

---

## 2. Relationship to Worker Spine

This design is bound to the landed worker spine from Tasks 034–042:

- Task 034 — Worker Invocation Envelope Canonical
- Task 035 — Worker Invocation Preflight Guard Design
- Task 036 — Preflight Guard Runtime Helper
- Task 038 — Controlled Worker Invocation Path
- Task 040 — MainBrain Worker Routing Design
- Task 041 — MainBrain Worker Routing Runtime Helper
- Task 042 — Routing-to-Controlled-Invocation Smoke Test

Required chain:

```text
MainBrainWorkerRoutingDecision
→ RoutingDecisionToEnvelopeBuilder
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

For envelope building specifically:

- Envelope builder ≠ MainBrain.
- Envelope builder ≠ worker.
- Envelope builder ≠ Preflight Guard.
- Envelope builder ≠ Controlled Invocation.
- Envelope builder ≠ Gate.
- Envelope builder ≠ Verification.
- Envelope builder ≠ Governance.
- Envelope builder ≠ Memory authority.
- Envelope builder cannot approve execution.
- Envelope builder cannot approve side effects.
- Envelope builder cannot claim task completion.
- Envelope builder cannot mutate memory.
- Envelope builder cannot bypass Preflight Guard.
- Envelope builder cannot bypass Controlled Invocation.

---

## 4. Builder Scope v0.1

For v0.1, the builder may support exactly one routing decision:

```text
decision: route_repo_research_worker
selected_worker:
  worker_id: repo_research_worker
  worker_type: read_only_repo_research
```

Supported invocation purpose:

```text
candidate_repo_evidence
```

Forbidden in v0.1:

- building envelopes for unknown workers
- building envelopes for multiple workers
- worker-to-worker routing
- worker self-invocation
- subagent routing
- Hermes delegation
- hermes_subprocess
- open worker registry
- dynamic plugin loading
- arbitrary callable execution
- external network research
- money-touching envelopes
- memory mutation envelopes
- repo mutation envelopes

---

## 5. Builder Input

Define conceptual input:

```yaml
RoutingDecisionToEnvelopeBuilderInput:
  routing_decision:
    task_id:
    decision:
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
  requested_by:
  invocation_id_optional:
  created_at_optional:
```

Rules:

- routing_decision is mandatory
- routing_decision.decision must be `route_repo_research_worker`
- selected_worker must match repo_research_worker / read_only_repo_research
- proposed_input_scope must exist
- paths_allowed must be explicit and non-empty
- requested_by must be explicit
- builder must not infer paths from prose
- builder must not widen paths_allowed
- builder may narrow scope but not expand it
- approval_required must be false
- blocked_reasons must be empty or non-authoritative warnings only
- if routing decision is not route_repo_research_worker → no envelope; return blocked/invalid builder result

---

## 6. Envelope Construction Rules

For Repo Research Worker v0.1, builder must construct:

```yaml
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

Builder must also include:

- invocation_id
- task_id
- requested_by
- invocation_purpose
- input_scope
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
The builder may create the envelope, but it may not mark the envelope as approved.
```

---

## 7. Default Policy Values v0.1

Safe defaults for Repo Research Worker v0.1:

```yaml
allowed_tools:
  - filesystem_read
  - repo_scoped_read
forbidden_tools:
  - shell
  - network
  - browser
  - download
  - package_install
  - git_write
  - memory_write
  - external_write
auto_allowed_actions:
  - read_scoped_files
  - collect_candidate_evidence
approval_required_actions:
  - repo_write_candidate
  - repo_mutation
  - external_read
  - external_write
  - memory_mutation
  - model_provider_change
  - delegated_subagent
  - hermes_subprocess
blocked_actions:
  - money_touching
  - trading
  - withdrawal
  - download_and_execute
  - arbitrary_code_execution
  - worker_self_approval
  - worker_self_invocation
  - bypass_gate
  - bypass_verification
  - bypass_governance
model_provider_policy:
  visibility: not_visible_to_runtime
  change_requested: false
memory_context_policy:
  mode: no_memory_write
  retrieval_context_allowed: false
verification_expectation:
  completion_authority: verification_only
  worker_may_claim_completion: false
governance_expectation:
  governance_authority: governance_only
  worker_may_approve_governance: false
output_contract:
  type: WorkerOutputPacket
  candidate_only: true
return_path:
  target: MainBrain
  mode: candidate_contribution
escalation_policy:
  gate_required_for_side_effects: true
  approval_required_actions_route_to_gate: true
abort_conditions:
  - invalid_envelope
  - blocked_action
  - missing_input_scope
  - unsafe_path
  - network_requested
  - money_touching_requested
  - memory_mutation_requested
```

The spec may refine naming, but must preserve semantics.

---

## 8. Builder Output Packet

Define conceptual output:

```yaml
RoutingDecisionToEnvelopeBuilderResult:
  task_id:
  decision: built_envelope | blocked | invalid_routing_decision
  invocation_id:
  envelope:
  reasons:
  limitations:
  generated_at:
```

Rules:

- built_envelope does not mean execution approved
- envelope is input to Preflight Guard
- blocked means builder refused to construct an unsafe envelope
- invalid_routing_decision means the routing decision is malformed or unsupported
- builder output is not WorkerOutputPacket
- builder output is not verification
- builder output is not governance
- builder output is not Gate approval

---

## 9. Refusal / Block Conditions

Builder must refuse to build envelope when:

- routing decision is not `route_repo_research_worker`
- selected worker is missing
- selected worker is not repo_research_worker / read_only_repo_research
- proposed_input_scope is missing
- paths_allowed is missing or empty
- routing decision includes approval_required true
- routing decision includes blocked_reasons indicating unsafe action
- routing decision asks for side effects
- routing decision asks for network
- routing decision asks for money-touching
- routing decision asks for memory mutation
- routing decision asks for subagent/Hermes delegation
- routing decision asks for hermes_subprocess
- routing decision asks for unknown worker
- routing decision asks for open dispatcher/dynamic plugin
- routing decision attempts worker self-invocation
- routing decision attempts bypass of Preflight Guard or Controlled Invocation

---

## 10. Scope Preservation

```text
The envelope builder may narrow routing scope, but must never expand it.
```

Rules:

- paths_allowed must come from routing decision proposed_input_scope
- builder cannot add new paths
- builder cannot infer paths from user_request
- builder cannot broaden directory scope unless explicitly present in routing decision
- builder must preserve paths_excluded
- builder must preserve max_files / max_bytes_per_file or make them stricter
- builder must not transform vague intent into broad filesystem access

---

## 11. Workflow Network vs Runtime Network

```text
Workflow network ≠ runtime network.
```

Rules:

- envelope builder must not treat approved git workflow network as runtime network permission
- envelope builder must set network_access false for repo_read_only_no_network
- envelope builder must block or refuse runtime network intent
- envelope builder must not add network/browser/download tools

---

## 12. Return Handling

The envelope must route outputs to:

```text
WorkerOutputPacket → MainBrain synthesis
```

Rules:

- return_path target must be MainBrain/Agent-compatible
- return_path must preserve candidate_contribution mode
- worker output must not bypass MainBrain
- worker output must not go directly to Gate as approval
- worker output must not claim completion
- worker output remains candidate contribution

---

## 13. Anti-Drift Checklist

- Did builder only accept route_repo_research_worker?
- Did builder reject unsupported routing decisions?
- Did builder preserve selected_worker?
- Did builder preserve proposed_input_scope?
- Did builder avoid path widening?
- Did builder use read_only / repo_read_only_no_network / direct_tool?
- Did builder set money_touching false?
- Did builder set network_access false?
- Did builder set shell_access false?
- Did builder avoid subagent/Hermes delegation?
- Did builder avoid open dispatcher/dynamic plugin loading?
- Did builder preserve candidate-only output contract?
- Did builder route output back to MainBrain?
- Did builder leave execution decision to Preflight Guard?
- Did builder preserve workflow network vs runtime network distinction?
- Did Task 044 remain not started?

---

## 14. Future Runtime Note

Runtime implementation is out of scope for Task 043.

Future task candidates:

- Task 044 — Routing Decision to Envelope Builder Runtime Helper v0.1
- Task 045 — Routing Decision → Envelope Builder → Controlled Invocation Smoke Test
- Task 046 — Spec Draft Worker Design v0.1
- Future subagent/Hermes delegation requires separate delegation boundary, security profile, and approval path.
- Future trading/money-touching requires separate trading boundary, risk manager, execution gate, and paper-trading phase.
