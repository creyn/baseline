# 20. Development with AI coding agents: specs first, CI as the build, privacy checks everywhere

Date: 2026-11-22

## Status

Proposed

## Context

The code is written mostly by AI coding agents (Claude Code), reviewed by the owner. Development happens on a small server with 2 GB of memory and no .NET SDK or Docker, so building and testing locally is not practical. The repository is public, and the system handles health data: one real value or name in a commit would be published at once, even on a branch.

### Considered options

**How changes reach `main`:**
1. **Direct pushes to `main`, each approved by the owner.** Simple, but every fix after a failed build needs another approval, and nothing runs before the push.
2. **Branches and pull requests.** Agents push to working branches; CI runs on the pull request; the owner merges when it is green.

**Where tests run:**
1. **Locally, before every push.** Fast feedback, but needs the SDKs and container emulators on a machine that cannot hold them.
2. **In CI only**, on GitHub Actions, with emulators in containers. The pipeline is the build.

**How agents work on a feature:**
1. **Prompt and code.** Fast for small changes; the reasons and the plan are lost.
2. **GitHub Spec Kit.** Strong guidance through fixed phases (constitution, specify, plan, tasks, implement); aimed at building a feature from nothing.
3. **OpenSpec.** Each change is a proposal folder (proposal, design, tasks, spec changes) next to living specs of the current system; made for existing projects; no fixed phase gates. A proposal and its code fit one pull request.

**Giving agents the project's decisions:**
1. **Agents read the files themselves.**
2. **A local MCP server for the project documentation:** ADRs, use cases, criteria and specs as tools ("find the decision about X", "which gates apply to this change"). It runs locally over stdio and touches no health data.

## Decision

Branches and pull requests; tests in CI only; OpenSpec; a local MCP server for documentation.

1. **Agents never push to `main`.** They push to `feat/…` or `fix/…` branches and open a pull request. The owner merges after CI is green.
2. **Before every push the diff is checked for personal data.** [tools/privacy/scan.py](../../tools/privacy/scan.py) runs in three places: a Claude Code hook before an agent commits or pushes (which also blocks `--no-verify`), a Git pre-commit hook, and CI on every pull request and on `main`. A deny list of real names kept outside the repository can be added locally.
3. **CI is the build.** GitHub Actions builds and tests every part, with emulators in containers (Azurite, the Service Bus emulator, SQL Server), runs the evals and the privacy scan, and deploys with azd and Bicep using OIDC, without stored secrets.
4. **Features start as OpenSpec change proposals** in `openspec/changes/`, reviewed in the same pull request as their code. Living specs in `openspec/specs/` describe the current system.
5. **A review subagent** checks every branch before its pull request: privacy, the gates, consistency with the ADRs, failure handling and tests ([.claude/agents/reviewer.md](../../.claude/agents/reviewer.md)).
6. **A local MCP server exposes the project documentation** to coding agents. It reads files from the repository only.
7. **Rules for agents are in [AGENTS.md](../../AGENTS.md)**, which `CLAUDE.md` imports, so other agents follow the same rules.

## Consequences

- Every change is visible as a pull request with its spec, its code and a green build.
- Feedback is slower than local tests: a mistake costs a push and a few minutes of CI. Code an agent believes correct still fails sometimes, and CI catches it.
- Branches of a public repository are public from the moment they are pushed, so the privacy check before the push is the first line of defence and CI is the second.
- The Claude Code hook works only in sessions opened in the repository folder. Agents started elsewhere rely on the check before push and on CI.
- OpenSpec and the MCP server are two more tools to keep up to date.
