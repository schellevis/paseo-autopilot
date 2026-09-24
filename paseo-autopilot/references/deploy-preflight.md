# Deploy/publish preflight

Read this file only when the user has authorized a deploy or publish action, before attempting it.

Only when the user has authorized the specific outward action, the orchestrator runs this preflight before attempting deploy or publish. This checklist grants no authority and creates no lifecycle phase. Existing external, deployment, destructive-action, security, and cost gates still apply; read-only inspection does not authorize changing platform settings or widening token scopes.

1. Confirm the authorized destination, visibility, action, artifact/revision, and required permission/capability against the recorded user decision and current platform capability.
2. Verify required authentication, tokens, and least-privilege read/write scopes through safe capability checks; record the result, never token values or credentials. Include required read scopes as well as deploy scopes.
3. Inspect relevant platform settings, such as Pages/CI enablement, workflow permissions, environment restrictions, and build base/target. If a required change is not already authorized, persist the material decision and pause the dependent action before changing it.
4. Confirm release gates have current independent verification evidence for the exact artifact/revision and representative CI concurrency/load, including determinism checks from VERIFY. Unresolved flaky required gates or missing evidence block the attempt; route diagnosis and any delegated repair through the existing workflow before retrying. Do not discover a known untested gate by repeatedly deploying.

Record timestamp, action scope, check results, and blockers in `05-verification-resolution.md`, with authorized action outcomes and residual risks in `06-final.md`. Invalidate and rerun affected checks when the artifact, configuration, permissions, or relevant environment changes. The orchestrator executes the authorized outward action itself; repository fixes required by preflight go to a scope-bound worker and require independent re-verification. Preflight never substitutes for verification or permits bypassing a material decision.
