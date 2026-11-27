# SECRET_LEAK_GUARD

## Purpose

Agent treats worker output as untrusted. Workers may return candidate evidence, but they may not expose credentials through prompts, snippets, logs, audit packets, commits, or push paths.

## Enforcement Points

1. Worker input scope gate:
   - `.env`, `.env.*`, private key files, credential JSON files, and token JSON files are blocked before worker execution.
   - This is enforced by `runtime.security.worker_io_guard.guard_worker_input_scope` and wired into `runtime.workers.preflight_guard`.

2. Worker output redaction:
   - Secret-like text is redacted before repo research snippets enter worker output.
   - Redaction evidence is surfaced as `secret_redaction`, with no raw secret value.

3. Repo diff guard:
   - `runtime.security.repo_diff_guard.scan_diff_text` returns `block` for staged or candidate diffs that contain secret-like content.
   - Managers should call this before `git add`, `commit`, `push`, PR body creation, or worker patch promotion.

4. Git ignore baseline:
   - Local secret files are ignored by default.
   - `.env.example` remains allowed for placeholders only.

## Canonical Rule

```text
No worker receives or emits raw credentials. If secret-like content appears, redact output and block repository promotion.
```

## Current Secret Classes

- OpenAI API keys
- TrustMRR API keys
- GitHub tokens
- AWS access key IDs
- Bearer tokens
- Database DSNs
- Private key blocks

## Operational Requirement

Any new worker or manager bridge must call the security guard at both boundaries:

```text
manager input -> guard -> worker candidate -> guard -> MainBrain / repo / logs
```

Worker output remains candidate-only even when redaction passes. Redaction is not verification, approval, or completion.
