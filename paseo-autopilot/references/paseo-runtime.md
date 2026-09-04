# Paseo runtime contract

Paseo is the cross-provider transport. Discover its current surface before use; this document defines invariants, not guaranteed provider/model/mode names.

## Capability discovery

Before selecting or launching agents, discover and persist:

1. configured Paseo profiles and human-authored notes;
2. providers/transports and the models each exposes;
3. underlying model vendor and account/quota scope;
4. provider modes, thinking/reasoning levels, and relevant feature support;
5. workspace IDs and canonical roots;
6. agent create, status, activity, logs, stop, and listing facilities;
7. finish-notification support.

Use Paseo tools when available. Otherwise inspect local `paseo --help` and subcommand help before building CLI calls. The current CLI exposes no profile-listing command; in a CLI-only host, record profiles as unavailable and continue at routing precedence 3 (runtime capabilities) rather than blocking or inventing profile notes. Never guess a flag, mode, model ID, or thinking ID. Persist the actual selected transport, vendor/account scope, model, mode, and thinking value in `run.json`.

## Workspace resolution

Resolve session scope before delegation:

- If `PASEO_AGENT_ID` exists and current Paseo inspection confirms agent-scoped inheritance, launch through the agent-scoped operation so child parentage and workspace are inherited. Omit an explicit workspace only in this confirmed case.
- Otherwise run the locally confirmed workspace-list operation (currently `paseo workspace ls --json`) and canonicalize the current repository root and every registered root, including symlink resolution. Match exact root **and isolation kind** (`local` versus worktree). Exactly one workspace must match. Pass its ID explicitly on every top-level launch.
- Zero matches block. Multiple matches block. A name similarity or parent directory is not an exact match. Never omit the workspace and let a top-level call create a surprise workspace.

Record the resolution evidence. For duplicates, present exact-root candidates ordered by most recent agent activity, including workspace ID, root, and isolation; ordering is only presentation, never an automatic tie-break. A user naming one candidate ID is sufficient resolution and is recorded. Show the confirmed remediation commands, currently `paseo workspace ls --json` and `paseo workspace archive <id>` for an obsolete duplicate. A zero match requires the user to create/register a workspace through a confirmed command or UI. In an unattended session write a pending process-block decision (`category: none`), enter `AWAITING_USER`, and launch nothing.

## Launch

Prefer the available Paseo agent-creation tool and request finish notification when supported. Supply the resolved workspace policy, discovered provider/model, thinking level, least-privilege mode, run/role labels, title, and the complete prompt from `handoff-prompts.md`. Atomically record a `planned` attempt with no agent ID before launch; after a successful call returns a real ID, add the matching agent record and mark it running.

For CLI-only operation, first confirm every used option locally. The conceptual shape is:

```bash
paseo run --background \
  --workspace 'resolved-workspace-id-when-top-level' \
  --title 'role: run-id' \
  --provider 'discovered-provider/model' \
  --thinking 'discovered-thinking-id' \
  --mode 'discovered-mode' \
  --label 'paseo-autopilot.run=run-id' \
  --label 'paseo-autopilot.role=role' \
  'self-contained prompt'
```

Omit `--workspace` only for confirmed agent-scoped inheritance. Omit an unsupported optional flag rather than inventing an equivalent. A CLI launch must return a real agent ID before it is recorded as running. The CLI path has the same artifact, budget, label, report, and reconciliation requirements as tool-based launch.

## Asynchronous observation

Do not serialize independent agents by waiting on each launch. Request finish notifications; while agents run, perform useful orchestrator work that cannot collide. If notification is unavailable, poll through confirmed status facilities at bounded intervals of at most 60 seconds.

For each attempt reconcile all three:

- current Paseo status;
- expected unique report path and its contents;
- actual workspace diff and resource state.

Before a new wave and after each wave, perform the label audit through the CLI even in a tool-capable host until the MCP listing surface supports label filtering:

```bash
paseo ls --label 'paseo-autopilot.run=<run-id>' -g -a --json
```

Compare every returned ID with `run.json.agents`. If that exact CLI form is unavailable, enumerate the widest available agent list, compare by canonical cwd plus the run's creation window and recorded IDs, and explicitly treat inability to enumerate/inspect labels as blocking—not a silent pass. Unexpected agents indicate possible worker delegation and block further launches.

At every status poll, check for pending permission requests across all run-labelled agents using `paseo permit` or the equivalent MCP facility. A pending permission that falls within the assignment's recorded scope is approved promptly; one that exceeds scope is a capability-escalation gate that enters AWAITING_USER. This prevents agents from silently blocking on permissions while the orchestrator waits.

## Idle, stopped, and failed agents

An idle/stopped status plus no report is ambiguous, not completion and not automatically a usage limit. First inspect pending permission requests through the discovered listing/responding facilities. A pending request is neither usage interruption nor task failure: approve or deny it only within the assignment's recorded permission scope; if it asks for more, persist a capability-escalation decision and enter `AWAITING_USER`. Prefer a discovered mode that can write the single assigned path without prompting when one exists.

If no permission is pending, inspect the agent's activity and logs. Preserve exact relevant evidence in `run.json` and the next handoff.

- Explicit quota, rate, context-window, provider, vendor, or account-scope failure: mark interrupted, stop if still live, and use the cross-vendor/account fallback policy.
- No explicit usage evidence: classify as task failure. Allow only the focused reprompt/fresh same-provider path from `workflow.md`.
- A report with a claimed success but failed status or mismatching diff: investigate and keep the assignment incomplete.
- A silent agent that remains live: do not duplicate it. Reprompt only within the documented task-failure allowance or stop it before a fresh attempt.

A missing report alone never authorizes relaunch. Resume reconciliation uses the same status/activity/log checks.

## Permission mapping

Discover actual mode semantics; mode names vary by provider. Choose the narrowest mode that can perform the assignment:

- Spec/plan reviewers: repository read plus write to one unique report, no source edits.
- Verifiers: repository/test read and write to one report; mutation-producing tests require explicit scoped authorization.
- Spikes: repository read plus write to one report; same rule as reviewers.
- Builders: write only owned paths and report; broad local mode only when no narrower discovered mode suffices and intake authorized it.
- Repairers: same rule as builders, limited to confirmed blocker paths.

Plan mode or any read-only mode is unsuitable for reviewers, verifiers, and spikes because these roles must write a report file. Read-only modes trigger permission prompts (such as ExitPlanMode) that cause the unattended approval deadlock this section prohibits.

Prompt boundaries remain binding even if enforcement is coarse. A discovered broad local-write mode (for example Codex `full-access` or Claude `bypassPermissions`, only after runtime verification) does not authorize delegation, commits, pushes, external effects, destructive commands, or writes outside scope.

When a write-capable role needs a mode, prefer the narrowest discovered mode that can read inputs and write the report without prompting. For example, Claude `acceptEdits` and Codex `auto-review` were observed as write-capable modes that do not trigger permission prompts; these are cited as one data point, not as permanent defaults. Every provider's mode is subject to mandatory runtime discovery and confirmation before use. The orchestrator must never treat a remembered mode name as authoritative without checking the current Paseo installation.

When a task requires broader execution (running commands, network access, destructive actions), the orchestrator performs that work itself rather than granting broader permissions to a reviewer or verifier.

A mounted Docker socket is effectively host-root capability even when the process user is non-root. Use it only when `permissions.docker` was explicitly authorized for the assignment. A Docker need discovered later is a material elevated-capability gate: write the decision artifact, enter `AWAITING_USER`, and do not touch the socket until approved.

## Controller rollover

When the controller approaches a context or provider limit, it persists artifacts and requests/initiates a fresh controller through the explicit handoff contract. The old controller stops launching and releases its lock only after durable transfer state is written. The new controller performs full status and label reconciliation; merely possessing `PASEO_AGENT_ID` does not permit takeover.
