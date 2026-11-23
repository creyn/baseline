# AGENTS

Instructions for AI coding agents (Claude Code, Codex, Copilot and others) working in this repository. `CLAUDE.md` only imports this file.

## The project

Baseline keeps personal lab results, extracts them into structured data with AI, shows trends and answers questions with citations. It organises data and never diagnoses. Read [README.md](README.md), then the decisions in [docs/adr](docs/adr/README.md) and the use cases in [docs/sequences](docs/sequences/README.md).

## Never

1. **No real personal or health data in the repository.** No real lab results, names, PESEL numbers, addresses, e-mails, screenshots of real documents or their file names, not even masked. Use fictional data ("Jan Testowy", the public example PESEL in [tools/privacy/allowlist.txt](tools/privacy/allowlist.txt)).
2. **No keys, secrets or connection strings.** Services use Managed Identity.
3. **No `--no-verify`.** The privacy scan runs before every commit and push; fix the finding instead.
4. **No direct push to `main`.** Work on a branch (`feat/…`, `fix/…`) and open a pull request. The owner merges after CI is green.

## Gates every change must pass

The gates G1 to G6 are defined once, in [docs/decision-criteria.md](docs/decision-criteria.md#gates). Read them before any change. In short: nothing unmasked reaches AI, EU only, every user sees only their own data, only approved results are read, deletion reaches every store, no secrets.

## How to work

- **Decisions:** every architecture decision is an ADR in `docs/adr` with considered options. Accepted ADRs are never edited, only superseded.
- **Specs first:** a feature starts as an OpenSpec change proposal (`openspec/changes/…`) before code.
- **Diagrams:** generated from `tools/diagrams`. Edit the scripts, never the SVG files.
- **Failure handling:** every message receiver is idempotent (Service Bus Basic has no duplicate detection). Status changes are forward-only (`UPDATE … WHERE status = …`). No database transaction spans an external call.
- **Tests run in CI.** Development happens on a small VPS without .NET or Docker, so the pipeline is the build. Keep tests runnable without Azure (emulators in containers).
- **Review:** before opening a pull request, run the `reviewer` subagent on the branch.
- **Language:** everything in the repository is in English, in plain, short sentences. The only exception is the text the family sees in the UI, including the consent text: it is Polish and lives in the UI's locale files ([ADR-0002](docs/adr/0002-languages-dotnet-python-and-typescript.md)).

## Tools in this repository

| Tool | What it does |
|---|---|
| [tools/privacy/scan.py](tools/privacy/scan.py) | Finds valid PESEL numbers, e-mail addresses, secrets and deny-listed words. Used by the Git hook, the Claude Code hook and CI. It never prints what it found, only where. |
| [.claude/settings.json](.claude/settings.json) | Claude Code hook: runs the scan before an agent commits or pushes, and blocks `--no-verify`. |
| [.githooks/pre-commit](.githooks/pre-commit) | The same scan for people. Enable once per clone: `git config core.hooksPath .githooks`. |
| [.claude/agents/reviewer.md](.claude/agents/reviewer.md) | Review subagent: privacy, gates, ADRs, failure handling, tests. |

Running the tests:

```sh
python3 -m unittest discover -s tools/privacy
node --test 'spikes/**/*.test.mjs'   # the quotes are needed on Node 22
```
