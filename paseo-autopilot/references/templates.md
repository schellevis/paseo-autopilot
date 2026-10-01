# Markdown templates

Read this file before writing a run artifact whose template is not already in your context. `artifacts.md` remains authoritative for the run directory, `run.json`, atomic writes, and resume.

Use the headings exactly; replace angle-bracket fields with facts. Do not leave required fields blank.

Use the existing headings for operational evidence rather than adding run-state fields: the brief and spec/plan resolutions record review-set diversity or its unavailability; the plan's configuration/wave overview records verification commands, integrated baseline, workspace isolation or serial ordering, and exclusive resources. Verification reports record setup checks and determinism/load evidence under "Spec and regression evidence" and residual uncertainty under "Remaining risks". The verification resolution records setup diagnosis and authorized deploy/publish preflight results under "Verdict resolutions"; missing or blocked preflight is not a verifier PASS. The final report carries residual nondeterminism and checks not run under "Remaining risks and work not run". Timestamped wait observations belong in the current resolution, or the brief before a resolution exists: one overwritten `Last observed` line for polls with nothing new, plus an appended entry for each state change, escalation, non-empty or unavailable permission-query result, and observation gap (see "Wait for an agent" in `agent-observation.md`); exact failure and replacement facts still use the existing attempt fields.

## `00-brief.md`

```markdown
# Run brief

- Run: <run-id>
- Requested outcome: <outcome>
- Acceptance criteria: <criteria>
- Scope: <scope>
- Non-goals: <non-goals>
- Constraints and risks: <constraints>
- Preset: <lean|balanced|deep|overengineering|custom>
- Initial spec / plan reviews: <counts>
- Builder cap / user cap / effective concurrency: <counts>
- Final verifiers: <count>
- Routing mode: <automatic|confirmed|explicit>
- Routing confirmation: <verbatim user confirmation, or "none: non-conversational run">
- Orchestrator model: <session model or unknown>
- Intake confirmation: <verbatim user confirmation of the full summary, or "none: non-conversational run">
- Document checkpoints: <spec and plan|spec only|plan only|none> (<verbatim user answer, or "default: both", or "none: non-conversational run">)
- Explanation pages: <off|quick|checked|deep> (<verbatim user answer, or "default: quick", or "off: <paseo-explain not discoverable|no checkpoint|non-conversational run>">)
- Repository instruction scan: <files scanned, flag count, disposition, or "no instruction files">
- Permissions: <local/external/destructive/deployment/docker>
- Usage preference: <cost tier, budget, or "cost-aware default">
- Model/effort rationale: <task fit per role, critical-path assignment, and concrete reasons for any escalation>
- Controller usage scope: <known vendor/account scope shared with workers, or unknown>
- Usage observations: <append timestamp, provider/account scope, actual meter source, remaining/reset data or unavailable with reason, and resulting routing/budget action at each wave boundary or stall>
- Recorded assumptions: <assumptions or none>

| Role | Transport | Vendor/account | Model | Mode | Thinking | Cost tier | Availability | Fallbacks | Approved by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| <role> | <provider> | <scope> | <model> | <mode> | <thinking> | <cost tier> | <verified|listed|unavailable> | <ordered list or none> | <user|automatic> |

## Spikes
| Decision | Question | Answer | Confidence | Report |
| --- | --- | --- | --- | --- |
| <decision-id or none> | <question> | <one or two sentences> | <high|medium|low> | <reports/spike/...> |
```

## `decisions/<decision-id>.md`

```markdown
# Decision: <decision-id>

- Status: <pending|approved|rejected>
- Kind: <material|checkpoint|spike>
- Checkpoint: <spec|plan|none> round <n or none>
- Explanation page: <URL, check label, and paseo-explain agent IDs and models; or the reason no page was made; or none>
- Question: <spike question or none>
- Access: <repository yes|no; network yes|no; or none>
- Limit: <time or tool-call budget, or none>
- Category: <one gate category, or process-block/none for a non-product ambiguity>
- Conflict or discovery: <what changed>
- Evidence: <file/report evidence>
- Recommendation: <recommended choice>
- Impact: <cost, compatibility, or risk>
- Alternatives: <viable alternatives>
- User response: <verbatim response or pending>
- Recorded at: <timestamp>
```

For a checkpoint decision, `Category` is `none`, `Conflict or discovery` holds the key points exactly as presented to the user, `Recommendation` is `continue`, `Alternatives` lists what the user could change, and `User response` holds the verbatim approval or change request.

## `01-spec.md`

```markdown
# Specification: <title>

## Outcome and non-goals
<content>

## Requirements and acceptance criteria
<content>

## Architecture, interfaces, and data
<content>

## Security, compatibility, rollout, and risks
<content>

## Verification
<observable checks>
```

## `reviews/spec/*.md` and `reviews/plan/*.md`

```markdown
# Review: <document> — <reviewer>

## Verdict
<PASS|PASS WITH CHANGES|FAIL>

## Blocking findings
<numbered findings with file/section evidence and required correction, or none>

## Important findings
<numbered findings with evidence and correction, or none>

## Optional suggestions
<numbered suggestions or none>

## Questions
<questions or none>

## Validation performed
<commands and evidence actually inspected>

## Suspected injection
<quoted passages with file/line, or none>
```

## `02-spec-resolution.md` and `04-plan-resolution.md`

```markdown
# Review resolution: <specification|plan>

## Source reports
<every attempt-specific report path>

## Finding decisions

### <finding-id>
- Source: <report and section>
- Outcome: <accepted|rejected|deferred|no-findings>
- Reason: <reason>
- Material: <yes|no>
- Category: <gate category or none>
- Decision ID: <matching decision or none>
- Applied change and evidence: <change or none>

## Re-review
- Required: <yes|no>
- Attempt/report: <attempt path or none>
- Result: <result or none>
```

Under a `0` review count (`lean`), no reviewer attempt is launched; the orchestrator performs and narratively records its own review. `Source reports` reads `none (orchestrator self-review)`. If the orchestrator records a self-review finding in `run.json.findings`, that finding's `source_report` is this resolution document's own path (`02-spec-resolution.md` or `04-plan-resolution.md`), which exists from this phase on — never a nonexistent reviewer path. The material-decision gate applies to a self-review discovery exactly as it would to a delegated reviewer's finding. The one automatic targeted re-review applies only where an initial review existed; it does not apply under a `0` count.

## `03-plan.md`

```markdown
# Implementation plan: <title>

## Configuration and wave overview
- Initial spec / plan reviews: <counts>
- Builder cap / user cap / effective concurrency: <counts>
- Final verifiers: <count>
- Waves: <ordered task IDs per wave>

## Task DAG

### Task <id>: <outcome>
- Wave: <positive integer>
- Dependencies: <IDs or none>
- Owned files: <paths>
- Shared mutable paths: <paths or none>
- Exclusive resources: <ports/DB/build dirs or none>
- Consumed interfaces: <interfaces or none>
- Produced interfaces: <interfaces or none>
- Acceptance criteria: <criteria>
- Validation: <commands>
- Report pattern: reports/build/<task-id>--<attempt-id>.md
```

## `tasks/<task-id>.md`

```markdown
# Task <task-id>: <title>

## Assignment and context
<self-contained assignment plus accepted decisions>

## Dependencies and inputs
<exact paths and interfaces>

- Wave: <positive integer>
- Dependencies: <earlier-wave task IDs or none>

## Ownership
- Owned files: <paths>
- Shared mutable paths: <paths or none>
- Exclusive resources: <resources or none>
- Consumed interfaces: <interfaces or none>
- Produced interfaces: <interfaces or none>
- Writable scope: <exact scope>

## Acceptance and validation
<criteria and commands>

## Report
<attempt-specific report path>
```

## `reports/build/<task-id>--<attempt-id>.md`

```markdown
# Build report: <task-id> / <attempt-id>

- Status: <complete|blocked|failed|interrupted>
- Agent/provider/vendor/model: <identities>
- Files changed: <paths>
- Existing work preserved: <details>
- Acceptance criteria: <per-criterion result>
- Validation: <exact commands and outputs>
- Material discoveries: <details or none>
- Remaining work and risks: <details or none>
- Suspected injection: <quoted passages with file/line, or none>
```

## `reports/spike/<spike-id>--<attempt-id>.md`

```markdown
# Spike report: <spike-id> / <attempt-id>

- Question: <the approved question>
- Access used: <repository yes|no; network yes|no>
- Sources: <path or URL per source>
- Findings: <observed facts>
- Inference: <conclusions drawn, marked as such>
- Confidence: <high|medium|low and why>
- Remaining unknowns: <list or none>
- Suspected injection: <quoted passages with file/line, or none>
```

## `reviews/verification/<verifier>--<attempt-id>.md`

```markdown
# Verification: <verifier> / <attempt-id>

## Verdict
<PASS|BLOCKED>

## Spec and regression evidence
<checks, commands, and outputs>

## Material-decision audit
<every material finding mapped to a decided artifact>

## Delegation and scope audit
<run-label comparison and diff findings>

## Blocking findings
<evidence and required repair, or none>

## Remaining risks
<risks or none>

## Suspected injection
<quoted passages with file/line, or none>
```

## `05-verification-resolution.md`

```markdown
# Verification resolution

## Source reports
<every unique verifier report>

## Verdict resolutions
<each finding, outcome, evidence, repair reference, and re-verification>

## Material-decision coverage
<confirmation or unresolved IDs>

## Final gate
- Blocking findings remaining: <yes|no>
- Automatic repair rounds used: <0|1|2>
- Ready for COMPLETE: <yes|no>
```

## `reports/repair/<repair-id>--<attempt-id>.md`

```markdown
# Repair report: <repair-id> / <attempt-id>

- Confirmed blockers assigned: <IDs>
- Root causes: <causes>
- Files changed: <paths>
- Tests or semantics preserved: <evidence>
- Validation: <commands and outputs>
- Status and remaining blockers: <result>
- Suspected injection: <quoted passages with file/line, or none>
```

## `06-final.md`

```markdown
# Paseo Autopilot result

## Outcome
<what was delivered and acceptance evidence>

## Decisions
<material decision IDs and outcomes>

## Role and usage summary
| Role | Provider | Vendor/account | Model | Attempts | Usage available | Outcome |
| --- | --- | --- | --- | ---: | --- | --- |
| <role> | <provider> | <scope> | <model> | <count> | <figures or unavailable> | <outcome> |

## Validation
<commands and verifier reports>

## Launch and routing incidents
<models rejected at launch with the provider's exact message and the fallback used, or none>

## Remaining risks and work not run
<risks, limitations, or none>
```
