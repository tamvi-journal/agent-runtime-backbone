# Worker Invocation Envelope Canonical v0.1

## 1. Purpose

Define `WorkerInvocationEnvelope` as the required contract Agent/MainBrain must use before invoking any worker, subagent, direct tool-backed worker, or future process worker.

The purpose is to enable bounded autonomy while preserving authority, security, verification, governance, and memory boundaries.

```text
Invocation is not delegation of authority.
Invocation is scoped evidence collection under MainBrain control.
WorkerInvocationEnvelope enables bounded autonomy, not unchecked automation.
A worker cannot receive more permission from Hermes capability than the envelope explicitly grants.
```

---

## 2. Relationship to Existing Canonical Law

This canonical law builds on Task 031, Task 032, and Task 033.

- Task 031 defines what workers are and are not.
- Task 032 defines the first concrete read-only worker species.
- Task 033 defines safe agent profiles and security constraints.
- Task 034 defines how worker invocation must be wrapped before execution.

```text
No raw worker invocation is allowed.
Every worker call must pass through a WorkerInvocationEnvelope.
```

---

## 3. Non-Authority Law

Apply the following invariants:

- Worker ≠ authority.
- Worker ≠ MainBrain.
- Worker ≠ Gate.
- Worker ≠ Verification.
- Worker ≠ Governance.
- Worker ≠ Memory authority.
- Worker ≠ autonomous self.
- Worker output = candidate contribution.

For invocation specifically:

- Invocation does not transfer authority to the worker.
- Invocation does not grant completion authority.
- Invocation does not grant side-effect authority.
- Invocation does not grant memory authority.
- Invocation does not grant governance approval.
- Invocation does not bypass Gate.

---

## 4. Envelope Required Fields

Every invocation envelope must define these fields:

```yaml
invocation_id:
task_id:
requested_by: MainBrain | Agent | approved_runtime_component
worker_id:
worker_type:
invocation_purpose:
input_scope:
permission_class:
security_profile:
execution_surface:
allowed_tools:
forbidden_tools:
auto_allowed_actions:
approval_required_actions:
blocked_actions:
side_effect_class:
money_touching: false
external_mutation: false
network_access: false
shell_access:
model_provider_policy:
memory_context_policy:
verification_expectation:
governance_expectation:
output_contract:
return_path:
escalation_policy:
abort_conditions:
created_at:
```

Rules:

- `permission_class` is mandatory.
- `security_profile` is mandatory.
- `execution_surface` is mandatory.
- `input_scope` is mandatory.
- `allowed_tools` and `forbidden_tools` must be explicit.
- If any mandatory field is missing, invocation must be blocked.
- Defaults must be restrictive, not permissive.

---

## 5. Permission / Security / Execution Triple

Every invocation must declare three layers:

```yaml
permission_class:
security_profile:
execution_surface:
```

Required rule:

```text
A worker may act only at the intersection of permission_class, security_profile, and execution_surface.
```

Meaning:

- `permission_class` defines what the worker may do architecturally.
- `security_profile` defines what the worker may access safely.
- `execution_surface` defines how the worker is run.

If the layers conflict, the most restrictive rule wins.

```text
Security profile grants less than tool capability, never more.
```

---

## 6. Execution Surfaces

Define execution surfaces from Task 033:

- `direct_tool`
- `delegated_subagent`
- `hermes_subprocess`

### direct_tool

- Preferred for low-risk read-only work.
- Must still be wrapped by an envelope.
- Tool access must be scoped.
- Tool output may support evidence but is not authority.

### delegated_subagent

- Allowed only when envelope explicitly grants it.
- Must report model/provider visibility when available.
- Must report `agent_id` if available.
- Subagent output is candidate artifact, not verified truth.
- Subagent independence is not trust.

### hermes_subprocess

- Highest-risk execution surface.
- Forbidden by default.
- Requires explicit `approval_required_actions` entry.
- Must never be selected silently.

---

## 7. Bounded Autonomy

Automation is allowed only inside pre-approved envelope boundaries.

### auto_allowed_actions

Actions the worker may perform without asking owner again, only because the envelope already allowed them.

Examples for `repo_read_only_no_network`:

- inspect allowed repo paths
- search allowed paths
- read allowed files
- run approved read-only inspection if `shell_access` allowlist is explicitly enabled
- return `WorkerOutputPacket`

### approval_required_actions

Actions that require escalation before execution.

Examples:

- scope expansion
- shell outside allowlist
- network access
- browser access
- download
- package install
- file write
- `git checkout` / `git merge` / `git commit` / `git push`
- subagent spawning if not already allowed
- `hermes_subprocess`
- model/provider change
- side-effect request
- money-touching action

### blocked_actions

Actions that must be blocked without asking.

Examples:

- `curl | bash`
- download and execute in same task
- running unknown binary
- leaking secrets
- disabling redaction
- silent model/provider change
- self-approval
- self-verification
- bypassing Gate
- using invalidated memory as guidance
- claiming completion without verification

---

## 8. Side-Effect Classes

Define `side_effect_class` values:

```text
none
repo_read
repo_write_candidate
repo_mutation
external_read
external_write
money_touching
identity_or_memory_mutation
blocked
```

Rules:

- `side_effect_class: none` or `repo_read` can be auto-allowed only if envelope permits.
- `repo_write_candidate` requires explicit `permission_class` and must not imply commit/push.
- `repo_mutation` requires Gate.
- `external_write` requires Gate.
- `money_touching` requires Risk Manager and Execution Gate in future trading systems.
- `identity_or_memory_mutation` requires memory/governance rules and cannot be done by worker directly.
- `blocked` means stop.

```text
Signal ≠ order.
Order ≠ execution.
Execution ≠ success.
Success ≠ strategy validity.
```

These lines prepare the envelope for future money-touching systems without implementing trading.

---

## 9. Money-Touching Future Compatibility

This section does not implement trading.

```yaml
money_touching: false
requires_risk_manager: false
requires_execution_gate: false
max_loss_limit:
max_position_size:
allowed_assets:
forbidden_assets:
withdrawal_allowed: false
```

Rules:

- All current repo/doc workers must set `money_touching: false`.
- If `money_touching: true` in a future task, invocation must require Risk Manager and Execution Gate.
- No worker can both generate a trade signal and approve its own execution.
- Withdrawal authority must be blocked by default.
- Live trading must not be enabled by this spec.

```text
Trading autonomy is allowed only inside pre-approved risk limits.
```

---

## 10. Model / Provider Visibility Policy

- If model/provider is visible, report it.
- If not visible, report `not_visible_to_runtime`.
- Worker must not guess model/provider.
- Worker must not silently change model/provider.
- Changing model/provider changes evidence quality and must be reported.
- Model/provider selection belongs to orchestration policy or explicit task approval.

```yaml
model_provider_policy:
  model_visible:
  provider_visible:
  model_selection_allowed:
  provider_selection_allowed:
  change_requires_approval:
```

---

## 11. Memory Context Policy

Bind to existing memory/retrieval law:

- event ≠ belief ≠ axis
- retrieval ≠ truth
- memory is evidence, not authority
- retrieval returns candidates, not truth
- Worker memory input = candidate context, not authority

```yaml
memory_context_policy:
  memory_allowed:
  retrieval_packet_allowed:
  raw_memory_access_allowed: false
  memory_write_allowed: false
  deprecated_memory_allowed: false
  invalidated_memory_allowed: false
```

Rules:

- Workers may receive `RetrievalCandidateContextPacket` only if envelope allows.
- Workers may cite candidate context.
- Workers may surface contradictions.
- Workers may not write memory.
- Workers may not treat memory as truth.

---

## 12. Output Contract / Return Path

```yaml
output_contract:
  required_packet_type: WorkerOutputPacket
  candidate_status_required: true
  evidence_handles_required: true
  assumptions_required: true
  limitations_required: true
  verification_needed_required: true

return_path:
  returns_to: MainBrain
  enters_as: candidate_contribution
  synthesis_authority: MainBrain
  verification_authority: Verification
  governance_authority: Governance
  side_effect_authority: Gate
```

Rules:

- Worker output must return to MainBrain.
- Worker output must enter as candidate contribution.
- Worker output cannot be treated as final answer by itself.
- Worker output cannot claim completion.
- Worker output cannot approve itself.

---

## 13. Escalation Policy

```yaml
EscalationRequest:
  requested_action:
  why_needed:
  current_envelope:
  requested_delta:
  risk:
  alternatives:
  rollback_plan:
  expected_output:
  approval_target: Gate | MainBrain | Governance | owner
```

Rules:

- Escalation must be explicit.
- Escalation must state `requested_delta` from current envelope.
- Escalation must include safer alternatives if available.
- Worker must stop until approval if requested action is `approval_required`.
- Blocked actions must not be escalated unless architecture policy changes.

---

## 14. Abort Conditions

- missing `permission_class`
- missing `security_profile`
- missing `execution_surface`
- missing `input_scope`
- dirty tree when clean tree required
- nested/stray repo confusion
- unauthorized tool request
- unauthorized network request
- unauthorized shell request
- unauthorized model/provider change
- side-effect attempt outside Gate
- memory write attempt
- invalidated memory use
- secret exposure risk
- unknown binary execution request
- download-execute coupling
- money_touching without Risk Manager / Execution Gate

Expected behavior:

- stop
- report `blocked_items`
- return no execution result
- request review if applicable

---

## 15. Example Envelope — Repo Research Worker

```yaml
invocation_id: inv_repo_research_example_001
task_id: example
requested_by: MainBrain
worker_id: repo_research_worker
worker_type: read_only_repo_research
invocation_purpose: map repository evidence for a scoped question
input_scope:
  research_question: "Find canonical files related to worker boundaries."
  paths_allowed:
    - Specs/canonical
    - Specs/workers
    - runtime/task_runs
  paths_excluded:
    - .git
    - node_modules
  max_files: 25
permission_class: read_only
security_profile: repo_read_only_no_network
execution_surface:
  mode: direct_tool
  delegated_subagent_allowed: false
  hermes_subprocess_allowed: false
allowed_tools:
  - filesystem_read
  - repo_search
forbidden_tools:
  - network
  - browser
  - download
  - package_install
  - shell_write
  - git_write
auto_allowed_actions:
  - read_allowed_files
  - search_allowed_paths
  - return_worker_output_packet
approval_required_actions:
  - scope_expansion
  - delegated_subagent
  - shell_access
  - model_provider_change
blocked_actions:
  - download_and_execute
  - memory_write
  - repo_mutation
side_effect_class: repo_read
money_touching: false
external_mutation: false
network_access: false
shell_access:
  enabled: false
model_provider_policy:
  model_visible: not_visible_to_runtime
  provider_visible: not_visible_to_runtime
  model_selection_allowed: false
  provider_selection_allowed: false
  change_requires_approval: true
memory_context_policy:
  retrieval_packet_allowed: true
  raw_memory_access_allowed: false
  memory_write_allowed: false
verification_expectation:
  worker_may_support_verification: true
  worker_may_claim_completion: false
governance_expectation:
  worker_may_self_approve: false
output_contract:
  required_packet_type: WorkerOutputPacket
return_path:
  returns_to: MainBrain
  enters_as: candidate_contribution
escalation_policy:
  required_for_approval_required_actions: true
abort_conditions:
  - missing_scope
  - unauthorized_tool_request
  - side_effect_attempt
created_at: <runtime_generated_timestamp>
```

---

## 16. Anti-Drift Checklist

- Did invocation bypass the envelope?
- Was `permission_class` missing?
- Was `security_profile` missing?
- Was `execution_surface` missing?
- Did the worker receive more capability than the envelope granted?
- Did the worker expand scope silently?
- Did a subagent get spawned without envelope approval?
- Did model/provider change silently?
- Did network/browser/download activate unexpectedly?
- Did shell run outside approved allowlist?
- Did side effect bypass Gate?
- Did worker output claim completion?
- Did worker output bypass MainBrain synthesis?
- Did memory/retrieval become authority?
- Did money_touching appear without Risk Manager / Execution Gate?

---

## 17. Acceptance Criteria

Task 034 spec is acceptable only if:

- WorkerInvocationEnvelope required fields are defined.
- `permission_class` / `security_profile` / `execution_surface` triple is defined.
- Bounded Autonomy section exists.
- `auto_allowed_actions` / `approval_required_actions` / `blocked_actions` are defined.
- `side_effect_class` values are defined.
- model/provider visibility policy is defined.
- memory context policy is defined.
- output contract and return path are defined.
- escalation policy is defined.
- abort conditions are defined.
- repo research example envelope is included.
- money-touching future compatibility exists but does not implement trading.
- no runtime code is added.

---

## 18. Future Runtime Note

Runtime implementation is out of scope for Task 034.

Future task candidates:

- Task 035 — Worker Invocation Preflight Guard Design v0.1
- Task 036 — Repo Research Worker Runtime Prototype
- Task T001 — Trading Agent Boundary Canonical, future only
