# Spec Delta

## Purpose

A local, read-only MCP server that gives coding agents the project documentation: decisions, gates, use cases and specs.

## ADDED Requirements

### Requirement: Only documentation is readable

The server SHALL read only `README.md`, `AGENTS.md`, and `.md` or `.yaml` files under `docs/` and `openspec/`, after resolving symbolic links. It MUST NOT write files or open network connections.

#### Scenario: A path outside the documentation

- **WHEN** a tool is asked for `../outside.md`, `/etc/passwd`, `tools/secret.md` or a link that points outside the repository
- **THEN** it returns a tool error and reads nothing

#### Scenario: Listing files

- **WHEN** an agent calls `list_docs`
- **THEN** only allowed files are listed

#### Scenario: A file Git ignores

- **WHEN** `docs/private/note.md` exists and `private/` is in `.gitignore`
- **THEN** it is neither listed, searched nor read

### Requirement: Decisions, gates and use cases

The server SHALL provide tools that list the ADRs with number, title and status, return one ADR in full, return the gates from `docs/decision-criteria.md`, and return a use case with its workload, target, diagram and decisions.

#### Scenario: Reading an ADR by number

- **WHEN** an agent calls `get_decision` with `number: 6`
- **THEN** it receives the full text of ADR-0006

#### Scenario: An unknown ADR

- **WHEN** an agent asks for an ADR that does not exist
- **THEN** it receives a tool error that names `list_decisions`

#### Scenario: A use case

- **WHEN** an agent calls `get_use_case` with `id: "U3"`
- **THEN** it receives the row of U3 from `docs/use-cases.md` and from `docs/sequences/README.md`

### Requirement: Search

The server SHALL return the lines of the documentation that contain all given words, ignoring case, with the file and line number, at most 50 lines.

#### Scenario: Two words

- **WHEN** an agent searches for `sweeper role`
- **THEN** every returned line contains both words, with its path and line number

### Requirement: Model Context Protocol over stdio

The server MUST speak MCP over stdio: one JSON-RPC message per line on stdout, logs only on stderr. It MUST answer `initialize` with the client's protocol version when it supports it, and with its newest version otherwise.

#### Scenario: A session

- **WHEN** a client sends `initialize`, `notifications/initialized` and `tools/call`
- **THEN** it receives exactly one reply for each request and none for the notification

#### Scenario: A bad message

- **WHEN** a client sends invalid JSON, invalid UTF-8 or `params` that are not an object
- **THEN** it receives a JSON-RPC error and the session goes on
