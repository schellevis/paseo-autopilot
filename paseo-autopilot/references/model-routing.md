# Model routing

Runtime discovery is authoritative. Never launch a remembered model, mode, thinking level, or profile name without confirming that the current Paseo installation exposes it.

## Precedence

Resolve each role in this order:

1. the user's explicit role-to-model mapping, provided the requested choice exists now;
2. a matching configured Paseo profile and its human-authored notes;
3. current discovered capabilities matched to the role;
4. the role requirements below, matched against discovered capabilities.

Use this order to build the proposal table shown in intake step 3 (`workflow.md`). The user's answer sets `config.routing_mode`:

- `confirmed`: the user accepted the proposed table as shown;
- `explicit`: the user replaced one or more cells or supplied a full mapping;
- `automatic`: the user explicitly delegated routing to the orchestrator, or the run is genuinely non-conversational.

In `confirmed` and `explicit` mode every routing row, including its fallback chain, carries `approved_by: user`, and the run may not leave `INTAKE` until all five delegated roles have an approved row. `validate_run.py` enforces this.

If an explicit choice is unavailable, do not silently substitute. Report the discovery result and ask again in a conversational run; an unattended run records the unavailable mapping and uses the already-authorized automatic policy only when the user allowed fallback.

An empty profile list, no matching profile, or a CLI-only host without profile access is not an error; record that fact and continue with current discovered capabilities at precedence 3.

Persist three separate facts for every choice: Paseo transport/provider, underlying model vendor and account/quota scope, and exact actual model ID. OpenCode is a transport/provider, not a model family; routing through it does not by itself provide vendor diversity.

## Role requirements

- **Specification and architecture:** strongest available long-horizon reasoning when public interfaces, data, security, or multiple systems are involved; a capable mid-tier model suffices for narrow, well-scoped changes.
- **Spec/plan review:** strong critical reasoning from a different underlying family/vendor/account scope than the author when possible; a mid-tier model often suffices for routine review of bounded scope.
- **Implementation:** strong coding and tool use matched to repository complexity. Efficient models are suitable for narrow, mechanical, independently verifiable tasks; default to mid-tier and escalate only when the task demands it.
- **Integration and debugging:** strong repository-wide reasoning and reliable tool use; escalate from mid-tier only when the bug is subtle or spans many files.
- **Verification:** strong independent reasoning; avoid reusing the implementation model when a credible diverse option is available. A mid-tier model suffices for deterministic, scoped verification.
- **Research spike:** reliable tool use and source citation, with web access when granted; a capable mid-tier model is usually sufficient because the output is a bounded factual report.

Do not make a general-purpose implementation model the sole author of high-impact architecture while a stronger planning model is available. For high-impact specification, planning, debugging, and verification, select a discovered high-or-higher reasoning/thinking level when the provider exposes one, and record it. A lower-cost model may handle bounded formatting, fixture, or mechanical tasks only when its output has deterministic verification.

## Cost awareness and usage budget

The strongest available model is not the default for every role. Match model cost and reasoning level to task complexity. The intake proposal table includes a cost-tier column (for example `high`, `mid`, `low`) so the user can see the cost implications of each choice before confirming. Default each role to the least expensive model and reasoning level that satisfies the role requirements above; escalate to a higher tier only when the task genuinely needs it or the user explicitly requests maximum capability.

Do not default every role to the highest reasoning level. Specification architecture, complex debugging, and high-impact verification may warrant it; routine reviews, mechanical implementation, formatting, and verification of narrow deterministic output often do not. When discovery exposes a usage meter, quota, or rate limit, record it in the brief and factor it into the fallback chain ordering.

Record the user's usage budget or cost preference in the brief. When the user expresses one, honour it: never launch a model outside the user's stated cost ceiling without explicit approval. When the user declines to specify, apply the default cost-aware selection above.

## Diversity and fallback chains

At intake, propose an ordered fallback chain for every delegated role as part of the step-3 table. Each entry records `(transport provider, underlying vendor/account scope, model, mode, thinking level)`. Order it as follows:

1. a capable model in a distinct underlying vendor/account quota scope;
2. another capable distinct-vendor option;
3. a same-vendor different model only when evidence shows a model-specific failure, or no diverse option exists.

In `confirmed` or `explicit` mode the chain the user approved is the only chain. An automatic replacement must use the approved primary or one of its approved fallbacks; `validate_run.py` rejects an automatic attempt outside that set. When the chain is exhausted, stop, record the evidence, create a pending category-5 decision proposing the next available option, and enter `AWAITING_USER`. A user-authorized attempt (`initiated_by: user`) may use any currently discovered model; its decision record is the authorization.

Do not treat a new transport that reaches the same vendor/account as quota failover. Record when diversity is unavailable. For an explicit quota, rate, context, provider, vendor, or account failure, move to the next entry of the approved chain (in `automatic` mode, the next distinct scope) when possible. For a silent task failure, follow `workflow.md`; do not consume the fallback chain without evidence.

Every replacement is a fresh Paseo agent with a new attempt-specific report and a complete handoff. Preserve valid partial work, record exact failure evidence, use reciprocal replacement links, and respect the two-automatic-replacement limit.

## Permissions are separate from capability

Choose model quality and process permissions independently. A powerful model does not need broad write access to review. Use the most restrictive discovered mode that can read inputs and write its one report without an unattended approval deadlock for reviewers and verifiers. Select a discovered broad local-write mode only for an authorized builder or repairer that actually needs it; no remembered mode name expands task scope.

## Maintenance and controller rollover

Revise the role requirements above when provider capabilities, model quality, or vendor offerings change materially. Run results may recommend changes but must never self-edit this routing guide or override an explicit user mapping. Update the `routing-reviewed` date in `SKILL.md` only after both current Paseo runtime discovery and review of authoritative vendor information.

If the orchestrator approaches its own context or usage limit, persist all state and a handoff decision, stop launching work, and start a fresh controller. The replacement must acquire/take over the lock and perform full resume reconciliation from `artifacts.md`; it does not inherit authority merely from being a new session.
