# Workflow contract

Read this file during intake and before every phase change. `artifacts.md` is authoritative for persistence and resume; `paseo-runtime.md` is authoritative for agent observation.

## Intake

Inspect repository instructions, status, relevant code, tests, existing plans, and uncommitted work before asking questions. Resolve these fields before any paid delegation:

- outcome and acceptance criteria;
- scope, non-goals, constraints, and known risks;
- preset and optional user concurrency cap;
- automatic routing or an explicit role-to-model mapping;
- worker write permissions and external/destructive/deployment boundaries;
- Docker or other elevated-capability authorization.

Conversational hosts ask one unresolved question at a time. If `superpowers:brainstorming` is available, use it for requirements discovery only; this orchestrator retains budget, routing, artifact, state, and gate ownership.

A genuinely non-conversational run records its assumptions and selects `lean`, automatic routing, least local privilege, and no external, destructive, deployment, or Docker authority. It may not infer permission from silence. Any later material choice enters `AWAITING_USER`.

### Presets

| Preset | Initial spec reviews | Initial plan reviews | Concurrent builder cap | Final verifiers |
| --- | ---: | ---: | ---: | ---: |
| `lean` | 1 | 1 | 2 | 1 |
| `balanced` | 2 | 2 | 4 | 1 |
| `deep` | 3 | 3 | 6 | 2 |
| `custom` | user supplied | user supplied | user supplied | user supplied |

Effective builder concurrency is `min(preset cap, user cap)` when a user cap exists. Custom intake must echo the full projected initial agent count before launch. Counts above cover initial reviews; at most one targeted re-review per source document is automatic. Further review rounds require user approval.

Persist these resolved values in both `00-brief.md` and `run.json.config`: initial spec-review count, initial plan-review count, preset builder cap, nullable user cap, effective concurrency, and final-verifier count. Record planned attempts before creating agents; a planned attempt has no Paseo agent ID yet.

## Lifecycle

Allowed forward transitions are:

```text
INTAKE -> SPEC -> SPEC_REVIEW -> PLAN -> PLAN_REVIEW
PLAN_REVIEW -> BUILD_WAVES -> VERIFY -> COMPLETE
VERIFY -> REPAIR -> VERIFY
any active phase -> RESUME_RECONCILIATION
RESUME_RECONCILIATION -> recorded active phase | AWAITING_USER | COMPLETE
any nonterminal phase -> ABANDONED | CANCELLED
```

Any active phase may enter `AWAITING_USER`. Resume from it through `RESUME_RECONCILIATION`, never by jumping directly. Startup with an incomplete run also enters `RESUME_RECONCILIATION`, then returns to its recorded active phase after reconciliation. `validate_run.py` rejects unknown phases, illegal recorded transitions, and missing prerequisites.

`COMPLETE`, `ABANDONED`, and `CANCELLED` are terminal and excluded from resume discovery. `CANCELLED` records an explicit user stop. `ABANDONED` archives an explicitly acknowledged run that will not resume. Never infer either from inactivity alone.

At every transition: verify required Markdown, validate `run.json`, write the new state to a same-directory temporary file, flush it, atomically rename it over `run.json`, then validate again. Do not advance on errors.

## Specification and plan

The orchestrator writes `01-spec.md` from the accepted brief. It then launches the configured independent spec reviewers concurrently only when each has a unique report path. Wait asynchronously, read every report and the actual files, then record every finding in `02-spec-resolution.md` and `run.json.findings` at classification time as accepted, rejected, deferred, or an explicit no-findings record, with source report, reason, `material: yes|no`, and category/decision ID when material. A pending material decision is represented as `outcome: deferred` while the phase is `AWAITING_USER`. Apply accepted routine corrections. A blocking correction that changes semantics permits one targeted re-review.

Write `03-plan.md` as an executable task DAG. Every task must specify dependencies, owned files, shared mutable paths, exclusive resources, consumed/produced interfaces, acceptance criteria, validation, and a unique attempt-specific report destination. Review and adjudicate it identically in `04-plan-resolution.md`. Do not launch a builder until the relevant spec and plan findings are resolved.

## Material-decision gate

Gate changes in these five categories:

1. requested outcome, scope, or non-goals;
2. public interface, data model, migration, or compatibility;
3. security, privacy, compliance, or irreversible data behavior;
4. visible UX with meaningful alternatives;
5. cost, external service, deployment, destructive action, or newly required elevated capability such as Docker.

A spec/plan conflict uses the applicable category above; it is a gate trigger, not a sixth category. Present conflict, evidence, recommendation, impact, and alternatives compactly. Persist a decision request. Without interactive input, set the decision to pending, transition to `AWAITING_USER`, pause dependent work, and continue only unrelated work already authorized. Never relabel a material change as routine or expand intake permission silently.

## Dependency-safe build waves

Before every wave:

1. capture `git status --short` and the relevant diff as the wave baseline;
2. compare all Paseo agents bearing this run's label with `run.json.agents`; an unexpected agent is a material cost event and blocks launches;
3. confirm the task graph is acyclic and every dependency is in an earlier wave and completed with reports;
4. reject same-wave overlap in owned files, interfaces, shared mutable paths, or exclusive resources;
5. treat manifests, lockfiles, generated outputs, snapshots, formatter scopes, build/cache directories, ports, databases, and test environments as mutable paths or exclusive resources;
6. launch no more than effective concurrency, using complete role handoffs.

When a worker stops, reconcile live status, its unique report, and actual diff. A report alone does not prove completion, and a diff alone does not replace a report. Read both before marking a task complete. Run integration checks and repeat the run-label audit before releasing the next wave. Never reset, overwrite, or misattribute user changes.

## Failure classification and recovery

For idle, stopped, or missing-report attempts, inspect activity and logs:

- Explicit quota, rate-limit, context-limit, provider, vendor, or account-scope evidence is a usage interruption. Persist the exact evidence and trustworthy partial state, stop the old attempt, then launch a fresh agent using the next fallback, preferring a distinct underlying vendor/account scope.
- Without explicit usage evidence, it is a task failure. Allow at most one focused reprompt of the live agent or one fresh same-provider attempt. Do not call it quota failover and never mark missing work complete.

Before either branch, check whether Paseo reports a pending permission request. Respond only when the request is inside the assignment's recorded permissions; a broader request is a capability-escalation gate, not a task or usage failure.

Every replacement gets the failed attempt evidence, durable inputs, current diff, trustworthy partial work, and remaining criteria. Preserve valid partial changes. At most two automatic replacements per assignment are allowed; user-authorized attempts are recorded separately with `initiated_by: user`. If the last allowed replacement is interrupted, record its evidence without a replacement link, create a pending decision, and enter `AWAITING_USER`. A failed attempt always records evidence, including an explicit “no usage signal found” when that is the observed fact.

## Verification and repair

Do not start verification until every builder is stopped or complete and all build reports/diffs have been reconciled. Launch the preset's independent verifier count with unique attempt-specific paths under `reviews/verification/`. Verifiers audit spec compliance, regressions, material-decision coverage, unexpected delegates, and actual tests.

Resolve every verdict in `05-verification-resolution.md`. Any confirmed blocker enters `REPAIR`; a repairer receives only confirmed blockers and may not weaken tests or intended semantics. Re-run independent verification after repair. Stop after two automatic repair rounds and request direction if blockers remain. Only transition to `COMPLETE` after the configured number of verifier reports exist, all tasks are complete, all verdicts and material decisions reconcile, and no decision is pending; write `06-final.md` with evidence, role/provider/model/attempt usage where available, outcomes, decisions, risks, and anything not run.
