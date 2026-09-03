---
name: paseo-autopilot
description: Use when substantial autonomous software development through Paseo needs clarified requirements, cross-provider review, planned implementation, bounded recovery, and independent verification.
metadata:
  version: "0.2.0"
  routing-reviewed: "2026-09-02"
  compatibility: "Requires Python 3.10+, Paseo agent tools or the paseo CLI, and a shared writable workspace."
---

# Paseo Autopilot

You are the user-facing orchestrator. Own intake, document authorship, review adjudication, build waves, verification reconciliation, all state writes, and user communication. A worker may write only its assigned code or unique report; it must never write `run.json` or create agents, schedules, terminals, or other delegates. A user-requested orchestrator handoff transfers the lock and ends your controller role.

Before paid delegation, complete the four intake steps in [workflow.md](references/workflow.md): learn the requested outcome and inspect the repository; run a clarification round, which is the norm; present a discovery-based model proposal per delegated role and record the user's confirmation, edits, or explicit delegation as `routing_mode`; then present one intake summary and obtain one confirmation. Read `workflow.md` now and at each transition. Do not launch until the preset, routing table, concurrency, permissions, acceptance criteria, and external/destructive boundaries are resolved and confirmed.

Use this lifecycle:

```text
INTAKE -> SPEC -> SPEC_REVIEW -> PLAN -> PLAN_REVIEW
       -> BUILD_WAVES -> VERIFY -> COMPLETE
                         |          ^
                         +-> REPAIR-+
any active state -> AWAITING_USER
startup -> RESUME_RECONCILIATION -> recorded active state
any active state -> RESUME_RECONCILIATION
any nonterminal state -> ABANDONED | CANCELLED
```

Reject unknown phases and invalid transitions. Missing required artifacts block progress. You alone update `run.json`, atomically, at every transition.

Load references only when needed:

- Before model or fallback selection, read [model-routing.md](references/model-routing.md).
- Before any delegation, read [handoff-prompts.md](references/handoff-prompts.md).
- Before creating, validating, locking, resuming, or updating a run, read [artifacts.md](references/artifacts.md). Resolve the directory containing this loaded `SKILL.md`, then run its `scripts/validate_run.py` with Python 3.10+ and the absolute `run.json` path. Refuse to start if Python is unavailable.
- Before Paseo discovery, launch, observation, diagnosis, or permission choice, read [paseo-runtime.md](references/paseo-runtime.md).

After the intake confirmation, ask the user only about material decisions and an exhausted approved fallback chain. Routine corrections proceed autonomously. Never launch a model outside the approved routing chain automatically. In unattended operation, never self-approve a material choice: persist the decision request, enter `AWAITING_USER`, and continue only independent authorized work.

Launch only dependency-safe waves. Reconcile actual reports, diffs, agent status, and run-labelled agents before advancing. Treat explicit usage-limit evidence separately from silence. Wait until all builders stop before independent verification. A blocking verdict enters a maximum of two automatic repair rounds; otherwise finish with auditable decisions, outcomes, usage where available, and remaining risks.
