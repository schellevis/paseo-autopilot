# Repository guidance

## Purpose

This repository contains `paseo-autopilot`, a portable Agent Skills package for Claude Code, Codex, OpenCode, and Mistral Vibe.

The skill coordinates an autonomous development workflow:

1. One orchestrator clarifies the request and records the intake.
2. The orchestrator writes a specification.
3. Independent cross-provider agents review it in Markdown reports.
4. The orchestrator adjudicates findings and asks the user only about material decisions.
5. The orchestrator writes and reviews an implementation plan.
6. Scope-bound builders execute dependency-safe waves in the shared workspace.
7. Independent verifiers check the integrated result.

Users may choose models and review counts or allow automatic runtime routing. Minimize manual coordination without silently crossing material, permission, security, deployment, destructive-action, or usage-budget boundaries.

## Scope and authority

- Work in this repository only. The Docker image implementation is maintained in a separate consumer repository.
- Use `apply_patch` for deliberate handwritten edits.
- Preserve unrelated work and avoid destructive Git operations.
- Do not publish, change repository visibility, push, rewrite history, deploy, or mutate external systems unless the user explicitly authorizes that action.
- Commit-author metadata has been reviewed by the user and does not need to be changed.
- Do not add real personal data, organization details, workspace names, workspace IDs, agent IDs, account identifiers, or credentials to tracked fixtures or documentation. Use unmistakably fictional values such as `agent-example-1`, `wks_example_1`, and `/workspace/project-a`.

## Public files

- `paseo-autopilot/SKILL.md`: the single provider-neutral skill entry point.
- `paseo-autopilot/agents/openai.yaml`: Codex interface metadata, not a workflow fork.
- `paseo-autopilot/references/workflow.md`: lifecycle, gates, orchestration, and resume behavior.
- `paseo-autopilot/references/artifacts.md`: durable artifact and `run.json` contract.
- `paseo-autopilot/references/model-routing.md`: runtime model selection and failover policy.
- `paseo-autopilot/references/handoff-prompts.md`: self-contained worker/reviewer handoffs.
- `paseo-autopilot/references/paseo-runtime.md`: Paseo MCP and CLI behavior.
- `paseo-autopilot/references/run-state.schema.json`: machine-readable run-state schema.
- `paseo-autopilot/scripts/validate_run.py`: standard-library run-state validator.
- `docs/docker-consumer-contract.md`: contract for a separate Docker-image consumer.
- `LICENSE` and `paseo-autopilot/LICENSE`: repository and distributed-package MIT terms.

## Executable contract

The intended lifecycle is:

```text
INTAKE -> SPEC -> SPEC_REVIEW -> PLAN -> PLAN_REVIEW
       -> BUILD_WAVES -> VERIFY -> COMPLETE
                         |          ^
                         +-> REPAIR-+

any active state -> AWAITING_USER
startup/takeover -> RESUME_RECONCILIATION -> active
any nonterminal state -> ABANDONED | CANCELLED
```

Key invariants:

- `run.json` has one orchestrator writer, atomic updates, and a lock.
- Startup or takeover reconciles artifacts and live agents before new work is launched.
- Tasks form a valid dependency graph; waves respect dependencies, file ownership, shared mutable paths, exclusive resources, and interface collisions.
- Every agent attempt has a unique report path.
- Reviewer and builder handoffs are self-contained.
- Workers may receive broad local permissions but remain scope-bound. They may write only assigned implementation paths and their unique report. They must never write `run.json` or create agents, schedules, terminals, or delegates.
- A material finding remains recorded while awaiting the user's decision.
- `COMPLETE` is invalid until tasks, required reviews, verifiers, findings, decisions, and reports are reconciled.
- Explicit usage/quota evidence triggers failover to a distinct vendor/account scope. Silence or a missing report is a task failure, not quota evidence.
- Model recommendations are runtime-discovered guidance, not permanent model-name truth; update them as providers and model quality change.

## Validation

Run the checks available from the public tree after relevant changes:

```bash
python3 -m json.tool paseo-autopilot/references/run-state.schema.json >/dev/null
python3 paseo-autopilot/scripts/validate_run.py --help >/dev/null
test "$(find paseo-autopilot -name SKILL.md -type f | wc -l)" -eq 1
test -z "$(find paseo-autopilot -type l -print -quit)"
git diff --cached --check
git status --short
```

Also run an installed official Agent Skills validator against `paseo-autopilot/` when available. Discover its supported command and location at runtime; do not embed a host-specific absolute path.

Before release, inspect the complete tracked tree for credentials, personal or operational identifiers, unexpected binaries, cache files, symlinks, and executable modes.

## Docker integration contract

A consumer image build should:

1. Fetch a user-authorized repository and ref, authenticating when required.
2. Resolve and pin the commit SHA once.
3. Use a clean detached checkout.
4. Copy only `paseo-autopilot/` to `/usr/local/share/paseo-agents/paseo-autopilot`.
5. Include the package `LICENSE`.
6. Make the installed package root-owned, readable, and non-writable by runtime users.
7. Create absent-only discovery links in `~/.agents/skills`, `~/.claude/skills`, and `~/.codex/skills`.

Never overwrite a user-managed skill at a discovery root. The consumer repository remains outside this repository's authority.
