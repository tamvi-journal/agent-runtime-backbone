# Safe Agent Profile Canonical v0.1

## 1. Purpose

This canonical document defines security profiles for Agent/Hermes workers and subagents.
It clarifies that Hermes exposes capabilities, but Agent architecture decides permission.

Security profile grants less than tool capability, never more.
A worker may possess access at the Hermes layer but still be forbidden at the Agent architecture layer.
Hermes capability is not permission.
Configured tool access is not authority.
Subagent independence is not trust.

---

## 2. Relation to Existing Canonicals

This law is subordinate to Task 031 worker authority law and compatible with Task 032 read-only worker security discipline.
It does not replace worker authority law; it adds security discipline for tool, subagent, and process execution surfaces.

### Task 031 anchors
- Worker ≠ authority.
- Worker output = candidate contribution.
- Gate controls side effects.
- Verification controls completion.
- Governance controls evidence/review discipline.
- Memory/retrieval remain candidate context only.

### Task 032 anchors
- Repo Research Worker uses `repo_read_only_no_network` as default security profile.
- Repo Research Worker is read-only evidence mapper, not repo authority.
- Hermes Delegation Boundary is required for workers using Hermes capability surfaces.

---

## 3. Threat Model

The security model must account for at least these risk surfaces:

- shell execution
- network access
- browser/web content access
- file download
- attachment handling
- package installation
- binary execution
- external API mutation
- secret exposure
- PII exposure
- repo mutation
- subprocess / separate Hermes process
- model/provider switching
- subagent context leakage

A worker can be correct in reasoning but unsafe in execution.
A worker can be read-only by role but unsafe if given network, shell, or browser access without profile discipline.

---

## 4. Security Principles

- Least capability by default.
- Deny by default when scope is ambiguous.
- No network by default.
- No browser by default.
- No downloads by default.
- No package installation by default.
- No binary execution by default.
- No shell execution unless explicitly allowed by profile.
- No side effects without Gate.
- No external API mutation without Gate.
- No memory writes by workers.
- No secret disclosure.
- No PII disclosure beyond approved scope.
- No model/provider change without orchestration approval.
- No silent escalation.
- No execution of untrusted content.
- No download-and-execute in the same task.
- Network access and execution must be separated by a review boundary.
- Downloaded content is untrusted until verified.
- Subagent output is candidate evidence, not trusted execution proof.

---

## 5. Approval Modes

Architectural approval modes:

- `manual`
- `smart`
- `off_or_yolo`

Rules:
- manual is the safest default for risky actions.
- smart may be allowed only when the risk classifier and scope are explicit.
- off_or_yolo is forbidden for Agent workers unless explicitly approved for disposable sandbox experiments.
- Approval mode does not override security profile.
- Security profile does not override Gate.

Approval reduces accidental execution risk; it does not make an action safe.

---

## 6. Execution Surfaces

Execution surface values:

- `direct_tool`
- `delegated_subagent`
- `hermes_subprocess`

### direct_tool
- Preferred for low-risk, bounded repo inspection.
- Must still obey security profile.
- Tool output can support evidence.
- Tool availability is not permission.

### delegated_subagent
- Has separate context and reasoning loop.
- Must report model/provider visibility when available.
- Must report max_iterations when available.
- Must return candidate output only.
- Must not self-approve.
- Must not choose its own model/provider unless orchestration policy permits.
- Must not retain or leak unnecessary context.

### hermes_subprocess
- Highest-risk execution surface.
- Forbidden by default.
- Requires explicit approval and sandbox/worktree boundary.
- Must report command/args if visible.
- Must not be used for read-only worker v0.1 profiles unless explicitly approved.

---

## 7. Canonical Security Profiles

### repo_read_only_no_network

Purpose:
Read repository files and repo metadata without network, browser, download, package execution, or mutation.

Default for:
- Repo Research Worker

Allowed, when explicitly scoped:
- file read
- directory listing
- repo search
- read-only git inspection
- approved read-only shell allowlist

Forbidden:
- network
- browser
- downloads
- package install
- binary execution
- repo mutation
- git write actions
- external API mutation
- memory write
- subagent subprocess unless approved

### draft_only_no_execution

Purpose:
Draft specs, docs, summaries, or plans without executing commands or mutating runtime.

Allowed:
- text drafting
- candidate spec writing when task scope allows file creation
- no code execution

Forbidden:
- shell
- network unless specifically approved for research
- downloads
- package install
- binary execution
- tests
- commits/push/PR unless separately approved by workflow task

### patch_candidate_sandboxed

Purpose:
Prepare patch candidates under scoped approval.

Allowed only when task explicitly approves:
- edit scoped files
- produce patch/diff
- run approved local tests
- use isolated worktree/sandbox

Forbidden by default:
- network
- package install
- external API mutation
- uncontrolled shell
- commit/push/PR without separate approval

Rules:
- Cannot self-approve patch.
- Cannot claim completion without verification.
- Must report exact files changed.
- Must report exact test commands/output.

### network_research_no_execution

Purpose:
Permit web/network research without executing downloaded content.

Allowed when explicitly approved:
- web search
- browser/read web pages
- download metadata only if needed
- cite source URLs or handles

Forbidden:
- executing downloaded files
- package installation
- `curl | bash`
- binary execution
- repo mutation
- external API mutation

Rules:
- Network and execution must be separated by review boundary.
- Any downloaded content remains untrusted until verified.

### side_effect_request_only

Purpose:
Allow a worker to prepare a request for side effect without executing it.

Allowed:
- describe proposed side effect
- explain reason
- list risk
- list required approval
- prepare candidate command or action for review

Forbidden:
- executing side effect
- committing
- pushing
- PR creation
- email/calendar/API mutation
- memory write
- spending money
- publishing content

### blocked

Purpose:
Stop unsafe, ambiguous, out-of-scope, or unauthorized work.

Behavior:
- stop
- report reason
- return blocked candidate packet
- do not attempt workaround
- do not escalate silently

---

## 8. Read-Only Shell Allowlist

This allowlist may be used only when explicitly approved by profile and invocation scope.

Allowed examples:
- pwd
- git status --short
- git remote -v
- git branch --show-current
- git log --oneline -n <N>
- git diff --stat
- git diff -- <scoped-file>
- find
- rg
- grep
- ls
- cat
- sed -n

This allowlist is not automatic permission.
It only defines commands that may be allowed by an approved invocation.

---

## 9. Forbidden Actions

Forbidden by default:

- curl
- wget
- curl | bash
- remote script execution
- npm install
- pip install
- package installation
- executing downloaded code
- chmod +x unknown file
- opening/running unknown binary
- git checkout
- git merge
- git commit
- git push
- rm -rf
- writing/editing files outside approved patch scope
- moving/copying files into repo outside approved patch scope
- staging files outside approved commit task
- creating PRs outside approved PR workflow task
- publishing content
- memory writes
- email sending
- calendar editing
- external API mutation
- spend/money action
- secret display
- PII disclosure outside approved scope

Some actions may be allowed in later tasks only under stricter profiles, explicit approval, sandbox/worktree isolation, and Gate.

---

## 10. Download / Attachment / Package Safety

- A worker must never download and execute content in the same task.
- Network access and execution must be separated by a review boundary.
- Downloaded content is untrusted until verified.
- Attachments are untrusted until inspected.
- Binary files are untrusted by default.
- Package manifests must be inspected before installation is considered.
- Hash/signature verification should be required when available.
- Source provenance must be reported when available.
- Execution must occur only in approved sandbox/worktree/container.

---

## 11. Secrets and PII

- Secrets redaction should be enabled if available.
- PII redaction should be enabled if available.
- Workers must not print secrets, API keys, tokens, cookies, private keys, credentials, or `.env` contents.
- Workers must not pass secrets to subagents unless explicitly required and approved.
- Workers must not include sensitive context in delegated subagent prompts unless necessary.
- Secret/PII handling errors must trigger blocked or needs_review.

---

## 12. Model / Provider Delegation Security

- Model/provider selection belongs to Agent orchestration policy or explicit task approval.
- Workers must not silently choose or switch model/provider.
- If model/provider is visible, report it.
- If not visible, report `not_visible_to_runtime`.
- Changing worker model/provider changes evidence quality and must be reported.
- Lower-trust or unknown model/provider should reduce confidence.
- Model switch detection must be reported when visible.
- Subagent outputs from unknown model/provider remain candidate only.

---

## 13. Escalation Rules

A worker must stop and request review when:

- scope is ambiguous
- required tool is forbidden by profile
- shell/network/browser access is needed but not approved
- package installation is requested
- downloaded content needs execution
- repo mutation is needed
- external API mutation is needed
- memory write is requested
- secret/PII risk is detected
- model/provider visibility is unknown and task risk depends on it
- nested/stray repo confusion is detected
- working tree is dirty unexpectedly

Escalation output must include:
- requested capability
- reason
- risk
- proposed safer alternative
- required approval boundary
- whether Gate is required

---

## 14. Security Packet Fields

```yaml
security_profile:
  name:
  approval_mode:
  network:
  browser:
  shell:
  downloads:
  package_install:
  binary_execution:
  repo_mutation:
  external_api_mutation:
  secrets_redaction:
  pii_redaction:
  sandbox_or_worktree:
execution_surface:
  mode:
  tools_used:
  agent_id:
  model_visible:
  provider_visible:
  max_iterations:
  context_boundary:
security_events:
  blocked_items:
  escalation_requests:
  forbidden_tool_requests:
  untrusted_inputs_seen:
  redaction_notes:
```

Rules:
- Missing `security_profile` should block worker execution.
- Missing `execution_surface` should block delegated worker execution.
- Security events must be explicit, not hidden in prose.

---

## 15. Interaction With Gate / Verification / Governance

- Gate controls side effects.
- Security profile controls what the worker may attempt before Gate.
- Verification controls completion.
- Governance controls evidence/review discipline.
- Worker cannot self-approve security exceptions.
- Worker cannot self-verify safety.
- Worker cannot self-merge security exception into authority chain.

Security profile = pre-execution permission boundary.
Gate = side-effect approval boundary.
Verification = completion boundary.
Governance = evidence and review boundary.

---

## 16. Failure Modes

- unauthorized_shell_request
- unauthorized_network_request
- unauthorized_browser_request
- unauthorized_download_request
- unauthorized_package_install_request
- binary_execution_attempt
- download_execute_same_task
- secret_exposure_risk
- pii_exposure_risk
- model_provider_unreported
- execution_surface_unreported
- scope_ambiguous
- dirty_tree_detected
- nested_repo_confusion
- side_effect_attempt
- sandbox_missing
- external_api_mutation_attempt
- memory_write_attempt

Each failure mode must include expected behavior:
- stop
- downgrade confidence
- report blocked_items
- request review
- return candidate packet only
- do not attempt workaround

---

## 17. Anti-Drift Security Checklist

- Did tool capability become permission?
- Did configured access become authority?
- Did a subagent become trusted by default?
- Did execution surface go unreported?
- Did model/provider visibility go unreported?
- Did a worker use network/browser/download without explicit profile approval?
- Did a worker use shell outside approved allowlist?
- Did a worker download and execute content in the same task?
- Did a worker request package install without review?
- Did a worker expose secrets or PII?
- Did a worker mutate repo outside approved scope?
- Did a worker perform side effects without Gate?
- Did a worker self-approve security exception?
- Did a worker hide security events inside prose?
- Did output re-enter MainBrain synthesis as candidate only?

---

## 18. Acceptance Criteria

A valid Safe Agent Profile application must:
- declare `security_profile`
- declare `execution_surface`
- declare `approval_mode`
- declare toolsets allowed/forbidden where applicable
- declare network/browser/shell/download/package/binary settings
- declare sandbox/worktree boundary when execution is allowed
- declare model/provider visibility when delegated
- report security events
- block ambiguous scope
- separate network and execution by review boundary
- preserve Gate for side effects
- preserve Verification for completion
- preserve Governance for evidence/review discipline
- return worker output as candidate only

---

## 19. Future Runtime Note

Runtime enforcement is out of scope for Task 033.

Future task candidates:
- Task 034 — Worker Invocation Envelope Spec v0.1
- Task 035 — Repo Research Worker Runtime Prototype
- Task 036 — Safe Agent Profile Runtime Guard Prototype
