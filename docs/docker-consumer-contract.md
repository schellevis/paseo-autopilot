# Paseo Autopilot Docker consumer contract

**Source status:** the repository and ref are user-supplied inputs and may refer
to a private source. Consumer CI must authenticate when required, must not
assume anonymous access, and must never invent a source URL.

This document is the complete interface for the separate agent working in `paseo-agents`. This repository does not edit that sibling.

## Inputs

The image build receives:

- `PASEO_AUTOPILOT_REPOSITORY`: the user-authorized GitHub Git URL;
- `PASEO_AUTOPILOT_REF`: the desired moving branch/tag or an explicit commit;
- optionally an expected commit SHA enforced by release policy.

“Newest” means the single commit to which the supplied ref resolves when the build starts. It does not mean repeatedly checking the ref during a build.

## Immutable source resolution

Consumer CI must:

1. resolve `PASEO_AUTOPILOT_REF` once to a full commit SHA using authenticated Git metadata as appropriate;
2. clone/fetch only from the supplied repository;
3. check out the resolved commit detached;
4. assert `git rev-parse HEAD` exactly equals the resolved SHA;
5. assert the detached checkout is clean (`git status --porcelain` is empty) and retain that SHA as the immutable input for every later build step.

An archive digest captured during this resolution may provide extra provenance, but archive bytes are not proof of Git commit identity and do not replace the detached-checkout assertion. Do not fetch a moving ref again after pinning it.

## Payload validation and installation

The only copied payload is the repository directory `paseo-autopilot/` from that detached clean checkout. Do not copy repository docs, tests, Git metadata, `.paseo-autopilot` run artifacts, `__pycache__/`, or `*.pyc` into the image; fail rather than package a dirty source tree. Confirm that `paseo-autopilot/LICENSE` is present so the license travels with every installed copy.

Before installation:

1. run the actual Agent Skills validator used by this project with its PyYAML dependency. On a host with `uv`, the self-contained form is:

   ```bash
   uv run --with pyyaml python /path/to/skill-creator/scripts/quick_validate.py ./paseo-autopilot
   ```

2. reject any symbolic link in `paseo-autopilot/` whose fully resolved target is outside that package directory;
3. assert exactly one `SKILL.md` exists and it is at `paseo-autopilot/SKILL.md`;
4. assert `paseo-autopilot/LICENSE` exists and is included in the copied payload;
5. reject unfinished scaffold markers.

Install exactly at:

```text
/usr/local/share/paseo-agents/paseo-autopilot
```

The installed tree is root-owned, recursively readable/traversable by the runtime user, and not writable by that user. Record the pinned SHA in an image version manifest and/or OCI label, for example `org.paseo.paseo-autopilot.revision=<sha>`.

The path is image-owned. Exclude it from runtime UID/GID ownership migration and do not put it in Paseo's daemon-managed bundled/orchestration skills directory.

## Absent-only discovery links

At container startup, for the runtime user's home directory, consider these targets:

```text
~/.agents/skills/paseo-autopilot
~/.claude/skills/paseo-autopilot
~/.codex/skills/paseo-autopilot
```

For each target:

- create the parent discovery directory if absent, without changing any existing entry inside it;
- if the target path is entirely absent, create a symbolic link to the immutable installed package;
- if the target is an existing file, directory, working link, or broken link, preserve it unchanged;
- emit a loud startup warning naming every preserved conflicting or broken path and the bundled package it shadows.

Never replace, repair, chown through, or delete an existing target. This absent-only behavior preserves user overrides. A broken override remains preserved but must be visible in logs.

## Runtime smoke checks

Run as the non-root runtime user after link setup:

```bash
test -r /usr/local/share/paseo-agents/paseo-autopilot/SKILL.md
test ! -w /usr/local/share/paseo-agents/paseo-autopilot/SKILL.md
```

For each link newly created by startup, assert that its canonical `SKILL.md` resolves to the installed package's canonical `SKILL.md` and is readable. Existing overrides are not required to resolve to the bundled package, but every conflict must have produced a warning. Smoke-test Claude Code through `~/.claude/skills`, Codex through `~/.agents/skills` and its `~/.codex/skills` alternative, and OpenCode and Mistral Vibe through `~/.agents/skills`.

## Acceptance criteria for the separate image agent

- The build resolves once, pins a full commit, performs detached checkout, and verifies `HEAD`.
- Only `paseo-autopilot/` enters the installed payload.
- The installed payload includes `paseo-autopilot/LICENSE` alongside `SKILL.md`.
- Frontmatter validation, link-containment checks, and the one-entrypoint check pass.
- The immutable package is root-owned, runtime-readable, and runtime-nonwritable.
- The pinned SHA is observable in image metadata or a manifest.
- Startup creates only absent discovery links and loudly preserves conflicts, including dangling links.
- New links resolve to the same readable installed `SKILL.md` under the runtime user.
- Runtime ownership migration and daemon bundle management exclude the installed package.
- Every image build includes this package; source updates take effect only through a newly pinned image build.

## Validation evidence to return

The image agent should report:

- source repository, requested ref, and resolved full SHA;
- detached `git rev-parse HEAD` output;
- Agent Skills validator output;
- escaping-link and package-boundary check output;
- installed license-presence check;
- installed ownership/mode and recorded manifest/label;
- absent-only startup tests for absent, file, directory, working-link, and broken-link targets;
- runtime-user smoke-check output for all created links;
- files changed in `paseo-agents` and any remaining risks.

## Non-goals and authority boundary

This contract does not authorize publishing this repository, changing a GitHub remote, pushing a commit, deploying an image, replacing user skill installations, granting Docker access to agents, or editing this repository from the image integration task. The source repository and ref must be separately authorized for each integration.
