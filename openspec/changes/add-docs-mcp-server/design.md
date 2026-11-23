# Design

## Context

The server runs on the developer's machine and in CI. The development server has Python 3.12 and Node 22, but no package should be installed on it without need ([ADR-0014](../../../docs/adr/0014-development-with-ai-agents.md)).

## Goals / Non-Goals

**Goals:** give agents the decisions, gates and use cases in a few calls; never expose anything but documentation; be testable in CI without network.

**Non-Goals:** semantic search, writing documents, serving code or data of the application.

## Decisions

- **Python standard library instead of the official MCP SDK.** The server needs four methods of the protocol (`initialize`, `ping`, `tools/list`, `tools/call`) over stdio, one JSON message per line. The SDK would add a dependency to install locally and in CI for about 100 lines of protocol code. If the server grows (resources, prompts, other transports), moving to the SDK is a contained change.
- **Protocol version negotiation** as the specification requires: the server answers with the client's version when it supports it, otherwise with its newest one (2025-11-25, checked on 2026-11-23).
- **An allow list of files, checked after resolving symbolic links,** so neither `../` nor a link can reach other files.
- **Only files Git does not ignore.** The list of candidates comes from `git ls-files --cached --others --exclude-standard`, so a local `private/` folder is never served, even under `docs/`. Without Git the server serves nothing.
- **One bad message never ends the session.** Invalid JSON, invalid UTF-8, deep nesting and unexpected exceptions give a JSON-RPC error and the loop goes on. A file that is not UTF-8 or is larger than 1 MB is skipped by search and refused by `read_doc`.
- **Errors a model can fix** (unknown ADR number, file not allowed, missing, unknown or mistyped arguments) are tool results with `isError: true`, as the specification asks for input validation errors. An unknown tool and `params` that are not an object are JSON-RPC errors.
- **`.mcp.json` uses a relative path,** because Claude Code starts project servers in the project folder. The server finds the repository from its own location, not from the working directory.

## Risks / Trade-offs

- A hand-written protocol layer may miss a new rule of a later protocol version. The end-to-end test runs a full session over stdio, and the server advertises only the versions it was tested with.
- Search is a plain match of all words on one line. It finds exact terms, not meanings. At the size of this documentation that is enough.
