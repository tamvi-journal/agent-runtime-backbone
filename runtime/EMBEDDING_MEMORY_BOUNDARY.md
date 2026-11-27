# Embedding Memory Boundary

## Core definition

Embedding memory is semantic trace retrieval.

It stores compressed semantic records so Agent can later recover shape by meaning, not exact wording.

It records:
- memory kind
- title
- content
- tags
- strength
- source handles
- lifecycle status
- authority status
- embedding model
- embedding vector
- metadata

## Embedding memory is not

- canonical memory
- state memory
- raw transcript
- hidden reasoning
- final truth
- automatic reactivation authority
- Obsidian archive
- Agent identity

## Correct layer split

LiveState = now
Baton = next turn
SessionStatusMetadata = durable work-thread snapshot
State memory = operational posture continuity
Embedding memory = semantic trace retrieval
TaskRun records = structured execution history
Obsidian = human-readable archive/vault
Agent canonical memory = authority/lifecycle truth

## Rule

Retrieval returns candidates only.

Retrieved candidates may guide MainBrain attention, but they cannot decide truth, bypass verification, or promote themselves into canonical memory.

## Lifecycle behavior

- canonical: may be used as stable reference if authority permits
- provisional: may guide reasoning as candidate only
- deprecated: may be retrieved for history but is inert by default
- invalidated: blocked from active use
- archived: visible for audit/history, not active reactivation

## Authority behavior

- non_authoritative: evidence/candidate only
- candidate: eligible for review
- canonical_reference: stable reference, still subject to scope and verification

## Gate behavior

Reading embedding memory may be allowed in read-only mode.

Writing embedding memory is a persistent memory mutation and must be gated.

Canonical promotion must always require explicit approval.

## Authority boundary

Embedding memory can surface semantic similarity.
It cannot decide truth.
It cannot promote canonical memory.
It cannot override verification.
It cannot speak final.
It cannot silently steer the answer.

## v0.1 implementation boundary

This repo may contain dormant contracts and local in-memory stores.

It must not yet auto-inject retrieved memory into reasoning.
It must not mutate canonical memory.
It must not write Obsidian.
It must not add actor authority.
