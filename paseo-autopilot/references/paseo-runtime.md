# Paseo runtime contract

Paseo is the cross-provider transport. Discover its current surface before use; this document defines invariants, not guaranteed provider/model/mode names.

## Capability discovery

Before selecting or launching agents, discover and persist:

1. configured Paseo profiles and human-authored notes;
2. providers/transports and the models each exposes;
3. underlying model vendor and account/quota scope, per provider entry: one vendor may be reachable through several provider entries, one per signed-in account, and which account an entry reaches is not derivable from its id or its label. For every available entry, obtain its authentication/identity data through the discovered per-provider inspection facility and record the vendor, the account key defined in `artifacts.md`, the evidence that produced the key, the plan or subscription tier, and the account's authentication context. Two entries that resolve to the same account key are one quota scope; record that, so failover does not treat them as independent windows. Where an entry exposes no identity, record the absence and its reason and fall back as `artifacts.md` specifies; never infer an identity and never let an unidentified entry merge silently into another account's scope;
4. provider modes, thinking/reasoning levels, and relevant feature support;
5. workspace IDs and canonical roots;
6. agent create, status, activity, logs, stop, and listing facilities, and, separately, the pending-permission listing and allow/deny facility, which is not part of the agent listing, and the facility that changes a live agent's mode;
7. finish-notification support;
8. for every candidate model, whether the signed-in account or auth scope may actually run it;
9. actual usage-meter operations for the relevant provider/account scopes, their authentication context, and any cost of querying them; record unavailable meters explicitly.

Use Paseo tools when available. Otherwise inspect local `paseo --help` and subcommand help before building CLI calls. The current CLI exposes no profile-listing command; in a CLI-only host, record profiles as unavailable and continue at routing precedence 3 (runtime capabilities) rather than blocking or inventing profile notes. Never guess a flag, mode, model ID, thinking ID, or account identity. Persist the actual selected transport, vendor/account scope, model, mode, and thinking value in `run.json`. On the installation this was last reviewed against, the provider listing and the per-provider diagnostic were separate operations — `paseo provider ls` exposed the entries and `paseo provider diagnostic <provider>` exposed one entry's authentication data, with `list_providers` and `inspect_provider` as the tool-surface equivalents. Treat that as one observation of one installation, not as a permanent command contract: discover the current operations before use.

## Model availability

A model that appears in a provider list, in documentation, or in memory is not proof that this installation and this account may run it. A subscription login, an API key, an organization policy, or a plan tier can each reject a model the transport otherwise advertises, and the rejection arrives at launch time, not at discovery time. Treat availability as a separate fact per `(transport provider, vendor/account scope, model)` and record it in `run.json.routing` as `availability`:

- `verified`: an agent using exactly this triple has actually started under the current credentials, or a confirmed discovery or probe operation reported the model usable for this account;
- `listed`: discovery exposes the model, but nothing has confirmed that this account may run it;
- `unavailable`: the provider explicitly rejected this triple (unknown model, not supported for this account type or plan, not entitled, authentication or authorization failure).

Never record `verified` from memory, from a model list alone, or from a successful launch of a different model on the same transport. Once a triple is `unavailable`, never select it automatically again in this run, for any role, as primary or as fallback; `validate_run.py` rejects an automatic attempt that uses it. Report the exact provider message to the user when a model the user approved turns out to be unavailable.

## Workspace resolution

Resolve session scope before delegation:

- If `PASEO_AGENT_ID` exists and current Paseo inspection confirms agent-scoped inheritance, launch through the agent-scoped operation so child parentage and workspace are inherited. Omit an explicit workspace only in this confirmed case.
- Otherwise run the locally confirmed workspace-list operation (currently `paseo workspace ls --json`) and canonicalize the current repository root and every registered root, including symlink resolution. Match exact root **and isolation kind** (`local` versus worktree). Exactly one workspace must match. Pass its ID explicitly on every top-level launch.
- Zero matches block. Multiple matches block. A name similarity or parent directory is not an exact match. Never omit the workspace and let a top-level call create a surprise workspace.

Record the resolution evidence. For duplicates, present exact-root candidates ordered by most recent agent activity, including workspace ID, root, and isolation; ordering is only presentation, never an automatic tie-break. A user naming one candidate ID is sufficient resolution and is recorded. Show the confirmed remediation commands, currently `paseo workspace ls --json` and `paseo workspace archive <id>` for an obsolete duplicate. A zero match requires the user to create/register a workspace through a confirmed command or UI. In an unattended session write a pending process-block decision (`category: none`), enter `AWAITING_USER`, and launch nothing.

## Launch

Prefer the available Paseo agent-creation tool and request finish notification when supported. Supply the resolved workspace policy, discovered provider/model, thinking level, the mode selected under "Permission mapping", run/role labels, title, and the complete prompt from `handoff-prompts.md`. Atomically record a `planned` attempt with no agent ID before launch; after a successful call returns a real ID, add the matching agent record and mark it running with `launch_check.status: pending`, which stays pending until "Launch verification" below confirms the agent actually started.

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

Keep each agent launch in its own command block or tool call. Never combine a launch with job control or destructive shell operations such as `kill`, cleanup, or stopping an old attempt. Perform any authorized stop separately and confirm it completed before preparing the replacement; a failed preparation or stop blocks that launch.

Immediately before every launch, including replacements and resume, regenerate the full prompt from current durable artifacts. If a prompt file is used, write it fresh at an attempt-specific path, verify the write succeeded, and read back the exact content before passing it through the locally confirmed launch interface. Check the run/attempt identity, assignment, scope, accepted decisions, and absolute report/output destinations. Never launch from a stale prompt or rely on `/tmp` surviving a long session. A temporary transport file is disposable; the durable artifacts must suffice to regenerate it. Keep prompt data out of shell evaluation through a structured argument or correctly quoted, locally supported file-input mechanism.

## Launch verification

A returned agent ID means the create call was accepted, not that the agent started. Record the attempt as `running` with `launch_check` `{"status": "pending", "evidence": null, "checked_at": null}`, then actively confirm the start before treating the agent as working:

1. Perform the first status and activity check within 60 seconds of the launch call, and never later than the run's next status poll.
2. Confirm the start (`launch_check.status: started` with `checked_at`) only when the agent's status is live or already finished **and** its activity or log shows real work: a first assistant turn, a tool call, or a file access. A live status with an empty transcript is not a confirmed start.
3. Record a startup rejection as `launch_check.status: failed` with the provider's exact message quoted in `evidence` and in the attempt's `failure_evidence`.

Treat any of the following as startup-rejection evidence rather than a silent agent:

- an API or CLI error payload, for example `"type": "error"`, an HTTP 4xx/5xx status, `invalid_request_error`, or a non-zero exit before any tool call;
- a message stating that the model is unknown, unsupported, not available for this account type or plan, or not entitled — for example a provider CLI refusing a model ID because the session is signed in with a subscription account rather than an API key;
- an authentication, authorization, quota, or workspace error returned before any work began;
- a terminal status with no activity, no transcript, and no report.

Never tell the user an agent is launched, running, or working before its start is confirmed. Confirm that every agent of a wave started before settling into the ordinary polling rhythm; an unconfirmed launch at the next poll is investigated immediately, not waited out. Use "Wait for an agent" in `agent-observation.md` to classify observations and "Failure classification and recovery" in `workflow.md` to recover.

## Permission mapping

Discover actual mode semantics; mode names vary by provider. Choose the narrowest mode that can perform the assignment, including its validation commands, without prompting; when the user granted broad local mode, use the broadest discovered local mode for every role below, and when the user chose provider-reviewed mode, use the discovered provider-reviewed mode for every role below whose transport offers one:

- Spec/plan reviewers: repository read plus write to one unique report, no source edits.
- Verifiers: repository/test read and write to one report; mutation-producing tests require explicit scoped authorization.
- Spikes: repository read plus write to one report; same rule as reviewers.
- Builders: write only owned paths and report; broad local mode when the user granted it, or when no narrower discovered mode performs the assignment without prompting.
- Repairers: same rule as builders, limited to confirmed blocker paths.

A broad local grant given after intake takes effect at once. Record the statement verbatim in `00-brief.md` and set each worker role's routing `mode`, fallbacks included, to the broadest discovered local mode for its transport. Switch every live run agent to that mode through the discovered mode-change facility (currently `paseo agent mode <id> <mode>`, or the tool-surface equivalent) and confirm the change. Then approve its pending requests that are inside assignment scope. A transport without a mode-change facility keeps the agent's current mode until its next launch; never relaunch a live agent solely to change its mode.

Provider-reviewed mode delegates prompt decisions to the provider's own automatic reviewer, for example Claude `auto` (a model classifier) or Codex `auto-review` (a reviewer subagent). Confirm those semantics during discovery, and never treat a mode as provider-reviewed on the strength of its name alone. The reviewer does not change assignment scope: prompt boundaries, the observation checklist, and the verifier's scope audit still apply, and a prompt the reviewer escalates arrives as an ordinary pending permission. An action the reviewer refuses surfaces in the worker's activity or report; when it blocks in-scope work, handle the blocked report through "Failure classification and recovery" in `workflow.md`, and offer the user broad local mode for that role rather than retrying the same mode. A choice of provider-reviewed mode after intake follows the mid-run procedure above with the provider-reviewed mode in place of the broadest local mode.

Plan mode or any read-only mode is unsuitable for reviewers, verifiers, and spikes because these roles must write a report file. Read-only modes trigger permission prompts (such as ExitPlanMode) that cause the unattended approval deadlock this section prohibits.

Prompt boundaries remain binding even if enforcement is coarse. A discovered broad local-write mode (for example Codex `full-access` or Claude `bypassPermissions`, only after runtime verification) does not authorize delegation, commits, pushes, external effects, destructive commands, or writes outside scope.

When a write-capable role needs a mode, prefer the narrowest discovered mode that can read inputs and write the report without prompting. For example, Claude `acceptEdits` and Codex `auto-review` were observed as write-capable modes that do not trigger permission prompts; these are cited as one data point, not as permanent defaults. Every provider's mode is subject to mandatory runtime discovery and confirmation before use. The orchestrator must never treat a remembered mode name as authoritative without checking the current Paseo installation.

When a task requires broader execution (running commands, network access, destructive actions), the orchestrator performs that work itself rather than granting broader permissions to a reviewer or verifier. Under a broad local grant, a verifier runs its assigned local validation commands itself; network, destructive, and outward actions still follow this rule.

This is an execution-permission boundary, not permission for the orchestrator to author target-repository source/test fixes. Delegate those fixes to a scope-bound builder or repairer. Apply the isolation and exclusive-resource rules in "Verification and repair" in `workflow.md` to orchestrator-run checks as well as worker execution; isolated execution does not enlarge a verifier's report-only authored-write scope or authorize an outward action.

A mounted Docker socket is effectively host-root capability even when the process user is non-root. Use it only when `permissions.docker` was explicitly authorized for the assignment. A Docker need discovered later is a material elevated-capability gate: write the decision artifact, enter `AWAITING_USER`, and do not touch the socket until approved.

## Controller rollover

When the controller approaches a context or provider limit, it persists artifacts and requests/initiates a fresh controller through the explicit handoff contract. The old controller stops launching and releases its lock only after durable transfer state is written. The new controller performs full status and label reconciliation; merely possessing `PASEO_AGENT_ID` does not permit takeover.
