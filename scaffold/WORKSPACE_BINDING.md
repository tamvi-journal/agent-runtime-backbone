# Workspace binding

The operator selects one workspace, one instance role and its memory store.
Keep instance identity, user material, memory databases, credentials and
working state outside the shared repository. Load the shared laws from
the pinned backbone at startup; roles can narrow but not weaken the security
floor. Host integration must enforce any mandatory security boundary;
the boot adapter is runtime guidance, not an OS sandbox.

Use the host's existing inference and action loop. Do not introduce a
second model runner just to adopt this pack. Use the shared runtime helpers
at the appropriate host seams and the bounded execution subsystem only
where supported.
