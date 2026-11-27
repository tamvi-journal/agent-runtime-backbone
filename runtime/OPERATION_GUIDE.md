# OPERATION_GUIDE

## Local turn flow

1. Read user request.
2. Classify route:
   - `direct_host_chat`
   - `kernel_direct_reasoning`
   - `kernel_capability_path`
   - `clarify_or_reject`
3. If action is needed, run gate.
4. If gate allows/sandboxes/requires approval, execute only within allowed scope.
5. Build `VerificationRecord`.
6. If `verification_status != passed`, forbid completion wording.
7. Build `Baton` / `SessionStatusMetadata` if useful.
8. Final response must state:
   - what was attempted
   - what was actually done
   - what was verified
   - what remains partial/blocked
