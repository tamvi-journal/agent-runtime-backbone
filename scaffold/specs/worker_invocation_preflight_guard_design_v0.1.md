# Worker Invocation Preflight Guard Design v0.1

## 1. Purpose

Define the Worker Invocation Preflight Guard as the validation layer that checks a WorkerInvocationEnvelope before any worker, tool-backed worker, delegated subagent, or Hermes subprocess may run.

```text
Preflight Guard checks the envelope before any worker runs.
```

```text
No envelope, no worker.
Invalid envelope, no worker.
Escalation-required action, no worker until Gate approval.
Blocked action, no worker.
```

Clarifications:
- The guard is not MainBrain.
- The guard is not Gate.
- The guard is not Verification.
- The guard is not Governance.
- The guard does not decide architecture.
- The guard does not approve side effects.
- The guard only validates whether an invocation is allowed to proceed under its envelope.

---

## 2. Relationship to Prior Canonicals

This design is bound to:
- Task 031 — Worker Architecture Boundary Canonical
- Task 033 — Safe Agent Profile Canonical
- Task 034 — Worker Invocation Envelope Canonical

```text
Task 031 defines what a worker is not allowed to become.
Task 033 defines the security profiles that constrain Hermes capability.
Task 034 defines the envelope that carries permission into an invocation.
Task 035 defines the preflight guard that checks the envelope before execution.
```

---

## 3. Non-Authority Law

Repeat and apply:
- Worker ≠ authority.
- Worker output = candidate contribution.
- MainBrain/Agent synthesis remains final authority.
- Gate controls side effects.
- Verification controls completion.
- Governance controls evidence/review discipline.
- Memory/retrieval remain candidate context only.

For Preflight Guard specifically:
- Guard ≠ MainBrain.
- Guard ≠ Gate.
- Guard ≠ Verification.
- Guard ≠ Governance.
- Guard ≠ worker.
- Guard ≠ runtime executor.
- Guard cannot approve what the Gate must approve.
- Guard cannot mark a task complete.
- Guard cannot transform blocked actions into allowed actions.

---

## 4. Guard Input

```yaml
WorkerInvocationPreflightInput:
  invocation_envelope:
  current_repo_state_optional:
  runtime_visibility_optional:
  policy_registry_optional:
  approved_escalations_optional:
```

Rules:
- invocation_envelope is mandatory.
- approved_escalations_optional must be explicit if used.
- Missing envelope means blocked.
- Missing permission/security/execution triple means blocked.

---

## 5. Required Envelope Fields to Validate

The guard must validate presence and coherence of at least:
- invocation_id
- task_id
- requested_by
- worker_id
- worker_type
- invocation_purpose
- input_scope
- permission_class
- security_profile
- execution_surface
- allowed_tools
- forbidden_tools
- auto_allowed_actions
- approval_required_actions
- blocked_actions
- side_effect_class
- money_touching
- external_mutation
- network_access
- shell_access
- model_provider_policy
- memory_context_policy
- verification_expectation
- governance_expectation
- output_contract
- return_path
- escalation_policy
- abort_conditions
- created_at

Rules:
- Missing required field → blocked.
- Unknown permission_class → blocked.
- Unknown security_profile → blocked.
- Unknown execution_surface → blocked.
- Missing input_scope → blocked.
- Missing output_contract → blocked.
- Missing return_path → blocked.
- Missing escalation_policy → blocked.

---

## 6. Permission / Security / Execution Intersection Rule

```text
Allowed execution is the intersection of permission_class, security_profile, and execution_surface.
```

```text
The most restrictive layer wins.
```

Rules:
- A tool available in Hermes is not allowed unless the envelope allows it.
- A tool allowed by permission_class is still blocked if security_profile forbids it.
- A tool allowed by security_profile is still blocked if execution_surface forbids it.
- An action requiring approval cannot run as auto_allowed.
- A blocked action cannot be converted into approval_required by the worker.

---

## 7. Decision Outcomes

```text
allow
needs_approval
block
invalid_envelope
```

Meanings:
- allow: The invocation may proceed inside the declared envelope.
- needs_approval: The invocation requests an action listed under approval_required_actions or otherwise requires Gate approval.
- block: The invocation includes blocked actions, unknown permissions, missing fields, unsafe combinations, or forbidden security conditions.
- invalid_envelope: The envelope is malformed, incomplete, contradictory, or unparseable.

---

## 8. Guard Output Packet

```yaml
WorkerInvocationPreflightResult:
  invocation_id:
  task_id:
  worker_id:
  decision: allow | needs_approval | block | invalid_envelope
  reasons:
  validated_permission_class:
  validated_security_profile:
  validated_execution_surface:
  allowed_tools_effective:
  blocked_tools_effective:
  auto_allowed_actions_effective:
  approval_required_actions_effective:
  blocked_actions_effective:
  escalation_required:
  gate_required:
  side_effect_detected:
  money_touching_detected:
  external_mutation_detected:
  network_detected:
  shell_detected:
  model_provider_visibility_status:
  memory_context_status:
  output_contract_status:
  return_path_status:
  limitations:
  generated_at:
```

Rules:
- Result is evidence for routing, not task completion.
- Result cannot approve side effects.
- Result cannot replace Gate.
- Result cannot replace Verification.
- Result cannot replace Governance.
- Result must be logged or returned to MainBrain before worker execution.

---

## 9. Auto / Approval / Block Rules

### Auto-Allowed
An action may be auto-allowed only if:
- action is explicitly listed in auto_allowed_actions
- action is not listed in approval_required_actions
- action is not listed in blocked_actions
- requested tool is in allowed_tools
- requested tool is not in forbidden_tools
- permission/security/execution intersection allows it
- side_effect_class permits it
- no money_touching unless approved policy exists
- no external_mutation unless Gate path exists

### Approval-Required
An action must become needs_approval if:
- listed under approval_required_actions
- side_effect_class is anything beyond none or repo_read
- external_mutation is true
- money_touching is true
- network_access is requested beyond the security profile
- shell_access is requested beyond read-only allowlist
- model/provider change is requested
- delegated_subagent is requested where only direct_tool is approved
- hermes_subprocess is requested
- memory mutation is requested
- repo mutation is requested

### Blocked
An invocation must block if:
- missing envelope
- missing required fields
- unknown permission/security/execution values
- requested action appears in blocked_actions
- requested tool appears in forbidden_tools
- download-and-execute appears in the same task
- network access and execution are combined without review boundary
- money_touching is true without explicit risk policy
- withdrawal or fund transfer is requested
- secret exposure risk is detected
- unknown binary execution is requested
- worker attempts to approve itself
- worker attempts to claim completion authority
- worker attempts to bypass Gate/Verification/Governance
- worker attempts to write memory directly

---

## 10. Side Effect Detection

Define side effect classes from Task 034:
- none
- repo_read
- repo_write_candidate
- repo_mutation
- external_read
- external_write
- money_touching
- identity_or_memory_mutation
- blocked

Rules:
- none and repo_read may be auto-allowed only if envelope permits.
- repo_write_candidate requires approved patch/draft envelope.
- repo_mutation requires Gate.
- external_write requires Gate.
- money_touching requires explicit risk policy and execution gate.
- identity_or_memory_mutation requires memory/governance approval path.
- blocked cannot proceed.

---

## 11. Money-Touching Placeholder

Money-touching autonomy is forbidden unless a future risk policy, execution gate, and approved trading envelope exist.

Rules:
- money_touching defaults to false.
- If money_touching is true and no risk policy is present → block.
- Signal ≠ order.
- Order ≠ execution.
- Execution ≠ profit.
- Profit ≠ strategy validity.
- No agent may both generate a trade signal and approve its own execution.
- Withdrawals are blocked by default.
- Leverage/margin are blocked by default until explicitly defined by future policy.

---

## 12. Model / Provider Visibility

Rules:
- If model/provider is visible, report it.
- If not visible, report not_visible_to_runtime.
- Silent model/provider change → block or needs_approval.
- Worker may not choose its own model/provider unless orchestration policy allows it.
- Delegation model/provider changes must be reflected in the preflight result.

---

## 13. Memory / Retrieval Boundary

Bind to existing laws:
- memory is evidence, not authority
- retrieval returns candidates, not truth
- RetrievalCandidateContextPacket is context, not completion
- Worker memory input = candidate context, not authority

Rules:
- Missing memory_context_policy → blocked.
- Memory write request → needs_approval or block depending on policy.
- Direct memory mutation by worker → block.
- Deprecated/invalidated memory cannot be silently reactivated.

---

## 14. Return Path

Required return path:
```text
PreflightResult → MainBrain/Agent routing → worker execution only if allowed
```

After worker execution:
```text
WorkerOutputPacket → MainBrain synthesis → Verification/Governance/Gate as needed
```

Rules:
- Worker output must not bypass MainBrain.
- Worker output must not go directly to Gate as approval.
- Worker output must not claim completion.
- Worker output remains candidate contribution.

---

## 15. Abort Conditions

Define abort conditions:
- invalid envelope
- unknown profile
- unknown permission class
- unknown execution surface
- dirty repo when clean repo is required
- nested/stray repo confusion
- blocked action detected
- forbidden tool detected
- unauthorized shell/network/browser/download/package install
- download-and-execute pattern
- money_touching without risk policy
- missing output contract
- missing return path
- self-approval attempt
- gate bypass attempt
- verification bypass attempt
- governance bypass attempt
- memory write attempt

---

## 16. Anti-Drift Checklist

- Did invocation include an envelope?
- Did the envelope include permission/security/execution triple?
- Did the guard apply the most restrictive layer?
- Did Hermes capability get mistaken for permission?
- Did tool access get mistaken for authority?
- Did delegated_subagent get mistaken for trust?
- Did worker receive only scoped input?
- Did requested tools stay inside allowed_tools?
- Did requested actions avoid blocked_actions?
- Did approval-required actions route to Gate?
- Did side effects route to Gate?
- Did money_touching remain false unless risk policy exists?
- Did output_contract exist?
- Did return_path lead back to MainBrain?
- Did the worker remain candidate-only?
- Did Task 036 remain not started?

---

## 17. Future Runtime Note

Runtime implementation is out of scope for Task 035.

Future task candidates:
- Task 036 — Worker Invocation Preflight Guard Runtime Helper
- Task 037 — Repo Research Worker Runtime Prototype
- Task 038 — Controlled Worker Invocation Path
- Future trading tasks require separate trading boundary, risk manager, execution gate, and paper-trading phase.
