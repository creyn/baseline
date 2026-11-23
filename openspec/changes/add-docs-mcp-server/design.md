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
- **Errors a model can fix** (unknown ADR number, file not allowed) are tool results with `isError: true`. Unknown tools and invalid arguments are JSON-RPC errors.

## Risks / Trade-offs

- A hand-written protocol layer may miss a new rule of a later protocol version. The end-to-end test runs a full session over stdio, and the server advertises only the versions it was tested with.
- Search is a plain match of all words on one line. It finds exact terms, not meanings. At the size of this documentation that is enough.
