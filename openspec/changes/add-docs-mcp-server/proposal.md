# Proposal

## Why

Coding agents need the project's decisions before they change code: 14 ADRs, the gates, 11 use cases with diagrams, and later the specs. Reading every file at the start of each task is slow and easy to skip. ADR-0014 decides on a local MCP server for the project documentation, which touches no health data.

## What Changes

- A local MCP server in `tools/docs-mcp`, over stdio, with read-only tools: list and read ADRs, read the gates, read a use case with its diagram and decisions, search the documentation, list and read documentation files.
- It reads only `README.md`, `AGENTS.md`, and `.md` or `.yaml` files under `docs/` and `openspec/`.
- `.mcp.json` registers it for Claude Code sessions opened in the repository.
- Tests run in CI.
- `openspec/config.yaml` starts OpenSpec in this repository.

## Capabilities

### New Capabilities

- `docs-mcp-server`

### Modified Capabilities

None.

## Impact

- New files only; no change to the application.
- No new dependency: the server uses the Python standard library.
- No health data and no network: the server reads documentation files of the repository and nothing else.
