# Model routing

Runtime discovery is authoritative. Never launch a remembered model, mode, thinking level, or profile name without confirming that the current Paseo installation exposes it.

## Precedence

Resolve each role in this order:

1. the user's explicit role-to-model mapping, provided the requested choice exists now;
2. a matching configured Paseo profile and its human-authored notes;
3. current discovered capabilities matched to the role;
4. the dated candidates below, only after runtime confirmation.

If an explicit choice is unavailable, do not silently substitute. Report the discovery result and ask for a choice in a conversational run; an unattended run records the unavailable mapping and uses the already-authorized automatic policy only when the user allowed fallback.

An empty profile list, no matching profile, or a CLI-only host without profile access is not an error; record that fact and continue with current discovered capabilities at precedence 3.

Persist three separate facts for every choice: Paseo transport/provider, underlying model vendor and account/quota scope, and exact actual model ID. OpenCode is a transport/provider, not a model family; routing through it does not by itself provide vendor diversity.

## Role requirements

- **Specification and architecture:** strongest available long-horizon reasoning, especially when public interfaces, data, security, or multiple systems are involved.
- **Spec/plan review:** strong critical reasoning from a different underlying family/vendor/account scope than the author when possible.
- **Implementation:** strong coding and tool use matched to repository complexity. Efficient models are suitable only for narrow, mechanical, independently verifiable tasks.
- **Integration and debugging:** strong repository-wide reasoning and reliable tool use.
- **Verification:** strong independent reasoning; avoid reusing the implementation model when a credible diverse option is available.

Do not make a general-purpose implementation model the sole author of high-impact architecture while a stronger planning model is available. For high-impact specification, planning, debugging, and verification, select a discovered high-or-higher reasoning/thinking level when the provider exposes one, and record it.

## Dated candidates — reviewed 2026-09-02

Every exact ID in this section is a candidate marked **verify through runtime discovery**:

- Difficult specs/plans: `codex/gpt-5.6-sol` or the current strongest discovered long-horizon model such as `claude/claude-fable-5-1` — verify through runtime discovery.
- Rigorous diverse review: `claude/claude-fable-5-1` (or the newest discovered Fable 5.x revision) — verify through runtime discovery.
- Broad implementation: `claude/claude-sonnet-5` or `codex/gpt-5.6-terra` — verify through runtime discovery.
- Hard integration/debugging: `codex/gpt-5.6-sol` — verify through runtime discovery.
- Diverse implementation/review: the current Mistral agentic coding model — discover its exact ID; do not invent one.

These are preferences, not availability claims. Record unavailable providers honestly. A lower-cost model may handle bounded formatting, fixture, or mechanical tasks only when its output has deterministic verification.

## Diversity and fallback chains

At intake, build an ordered fallback chain for every delegated role. Each entry records `(transport provider, underlying vendor/account scope, model, mode, thinking level)`. Order it as follows:

1. a capable model in a distinct underlying vendor/account quota scope;
2. another capable distinct-vendor option;
3. a same-vendor different model only when evidence shows a model-specific failure, or no diverse option exists.

Do not treat a new transport that reaches the same vendor/account as quota failover. Record when diversity is unavailable. For an explicit quota, rate, context, provider, vendor, or account failure, move to the next distinct scope when possible. For a silent task failure, follow `workflow.md`; do not consume the cross-vendor failover chain without evidence.

Every replacement is a fresh Paseo agent with a new attempt-specific report and a complete handoff. Preserve valid partial work, record exact failure evidence, use reciprocal replacement links, and respect the two-automatic-replacement limit.

## Permissions are separate from capability

Choose model quality and process permissions independently. A powerful model does not need broad write access to review. Use the most restrictive discovered mode that can read inputs and write its one report without an unattended approval deadlock for reviewers and verifiers. Select a discovered broad local-write mode only for an authorized builder or repairer that actually needs it; no remembered mode name expands task scope.

## Maintenance and controller rollover

Update the `routing-reviewed` date in `SKILL.md` only after both current Paseo runtime discovery and review of authoritative vendor information. Run results may recommend changes but must never self-edit this routing guide or override an explicit user mapping.

If the orchestrator approaches its own context or usage limit, persist all state and a handoff decision, stop launching work, and start a fresh controller. The replacement must acquire/take over the lock and perform full resume reconciliation from `artifacts.md`; it does not inherit authority merely from being a new session.
