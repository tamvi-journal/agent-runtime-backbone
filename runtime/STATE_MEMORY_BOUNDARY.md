# State Memory Boundary

## Core definition
State memory is operational posture continuity.

It records:
- current task posture
- route class
- gate decision
- verification status
- evidence handles
- open loops
- next hint
- completion claim permission

## State memory is not
- canonical memory
- identity memory
- Obsidian archive
- raw transcript
- memory retrieval
- long-term semantic memory

## Correct layer split

LiveState = now
Baton = next turn
SessionStatusMetadata = durable work-thread snapshot
TaskRun records = structured execution history
State/Task Register Index = read-only operational index
Obsidian = human-readable archive/vault
Agent semantic memory = revisioned evidence and candidate context
Agent canonical documents = reviewed operating references

## Host integration

The source contract references a separate state-memory implementation. Those
historical source paths are not shipped as modules of this package. Use the
host's existing state store, the shared live-state/baton contracts and
sleep/wake helpers. Bind any persistent state to an instance-private location
selected by the owner, not the shared checkout.

## Rule
Reading task records to build a viewer index is allowed.
Reading task records or state-memory files for viewer summaries may be allowed later as read-only.
Cue-driven semantic retrieval is now available through
`runtime/memory_core_adapter/`, but only as bounded candidate context. It does
not become truth authority and remains below MainBrain, monitor, verification,
gate, and governance.

## Authority boundary
State memory can show operational status.
It cannot decide truth.
It cannot promote canonical memory.
It cannot override verification.
It cannot speak final.

## Semantic memory boundary

The external Memory Core records evidence, current revisions, and historical
revisions. the instance supplies its own profile and translates
retrieval hits into the existing candidate-context contract.

Semantic memory may orient MainBrain. It cannot replace state memory, decide
truth, claim completion, or authorize execution.
