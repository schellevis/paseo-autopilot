# Paseo Autopilot

Paseo Autopilot is a portable Agent Skills package. From a single
user-facing orchestrator session, it turns a substantial software request
into clarified requirements, an independently reviewed specification, an
independently reviewed implementation plan, integrated work delegated to
Paseo agents, and independent final verification — with all
usage-affecting, scope-changing, and permission-elevating decisions
routed back to the user.

## Supported hosts

The distributable unit is the [`paseo-autopilot/`](paseo-autopilot/) directory,
with `SKILL.md` at its root. It is one provider-neutral package, discovered
identically by:

- Claude Code
- Codex
- OpenCode
- Mistral Vibe

Paseo supplies the cross-provider agent delegation that lets a session
started in any one of these hosts hand work to agents running other
providers.

## Installation

Install by creating an **absent-only** link or copy named `paseo-autopilot`
in the relevant home-relative root(s). Do not overwrite an existing path —
if `paseo-autopilot` already exists at a target root, leave it and warn
instead of replacing it.

- `~/.agents/skills/paseo-autopilot` — Codex, OpenCode, and Mistral Vibe
- `~/.claude/skills/paseo-autopilot` — Claude Code
- `~/.codex/skills/paseo-autopilot` — Codex's product-specific alternative

Project-local equivalents may be used instead when a host documents them.
All roots must point at the same immutable `paseo-autopilot/` package; there
are no provider-specific forks of `SKILL.md`.

The package includes `agents/openai.yaml` as Codex interface metadata. It does
not fork the provider-neutral workflow in `SKILL.md`.

## Basic invocation

```text
Use $paseo-autopilot to develop this request with reviewed specifications,
planning, implementation, and verification.
```

The `$paseo-autopilot` form is the Codex-style explicit invocation. On other
hosts, invoke the installed skill by name using that host's documented skill
syntax, or describe the same substantial autonomous-development need so normal
skill discovery can select it.

## Intake and checkpoints

In a conversational run the orchestrator first asks what must be built and
runs a clarification round. It then queries Paseo for the providers, models,
and profiles available right now and shows one table with a proposed model,
mode, thinking level, and fallback chain per delegated role (spec reviewer,
plan reviewer, builder, verifier, repairer). You confirm the table, edit any
row, or explicitly hand routing to the orchestrator. During the clarification
round you also choose whether you want a checkpoint after the reviewed
specification, after the reviewed plan, both (the default), or neither. At a
checkpoint the orchestrator posts the key points, the review outcome, and the
path of the full document, then waits for "continue" or a change request.
After one final intake confirmation the run proceeds autonomously; you are
asked again only at the checkpoints you chose, for a material decision, or
when an approved fallback chain is exhausted.

An explicit mapping can also be given up front, for example:

```text
Use $paseo-autopilot with preset=custom, builder-cap=3, and this routing:
spec-reviewer=<a strong model from a different family/vendor than the builder>,
plan-reviewer=<a strong critical-reasoning model>,
builder=<a strong coding/tool-use model>,
verifier=<a sufficiently strong independent reasoning model>,
repairer=<a strong coding/tool-use model>.
```

Exact model IDs are always confirmed against runtime Paseo discovery, never
launched from a remembered default. An unavailable choice is reported and
asked again, not silently replaced.

## Untrusted content

Everything agents read (their own reports, the target repository, the web) is
treated as data, never as instruction. Every report is scanned with
`paseo-autopilot/scripts/scan_untrusted.py` before the orchestrator acts on
it, the result is recorded per attempt in `run.json`, and a suspected
injection becomes a security decision for you. The scanner is heuristic; the
diff and the tests remain the evidence.

## Related documents

- Docker consumer contract:
  [`docs/docker-consumer-contract.md`](docs/docker-consumer-contract.md) —
  the immutable GitHub-to-image interface for installing this package into a
  Paseo agent image from a user-authorized repository and ref.

## Validation status

Version 0.1.0 has passed structural package validation, JSON-schema parsing,
and maintainer-side validator unit tests. End-to-end behavioral evaluation of
the autonomous orchestration workflow is ongoing.

## Docker image integration boundary

This repository owns the skill package, references, validator, and Docker
consumer contract. Image implementation lives in a separate consumer
repository and is outside this project's authority. Work here must not edit,
mutate, or otherwise change that repository.

## License

Paseo Autopilot is available under the MIT License. The same license is kept
inside `paseo-autopilot/` so it travels with copied and containerized packages.
