# 1. Record architecture decisions

Date: 2026-11-17

## Status

Accepted

## Context

Baseline is a private tool for organising one's own lab test results. One person builds and maintains it for their own use. The system processes health data, so many decisions are trade-offs around security and privacy. Decisions need to outlive memory: six months from now we must know not only what we chose, but also why, and what we rejected.

### Considered options

1. Decisions in the project README. One place, but the context and alternatives get lost with each edit.
2. MADR (Markdown Any Decision Records). Its minimal variant is just as short: context and problem statement, considered options, decision outcome. Considered options are a required section, which is its strongest point. Status and consequences are optional, and most other sections (decision drivers, pros and cons per option, confirmation) are optional too.
3. Michael Nygard's template: title, status, context, decision, consequences. Short and focused on context. Every section is required, including status and consequences. Alternatives are not a separate section, so they are easy to skip.

## Decision

We use Michael Nygard's template with one extension borrowed from MADR: the "Context" section contains a required "Considered options" subsection.

Both formats would work, and the difference is small. Nygard's template wins because it makes status and consequences mandatory: every decision has to say what it costs, not just what it gains. MADR's best idea, explicit considered options, is added on top, because the rejected alternatives are the most valuable knowledge later on.

Rules:
- One file per decision: `NNNN-short-title.md`, numbered sequentially. Numbers are never reused.
- Statuses: Proposed, Accepted, Rejected, Superseded by ADR-NNNN.
- An accepted ADR is not rewritten. Changing a decision means a new ADR that supersedes the old one.
- ADRs are written in English.

## Consequences

- Each significant decision takes a few minutes of writing.
- When returning to the project after a break, or when someone else reads the code, the reasons behind decisions are visible, not just their outcome.
- The list of ADRs is in [README.md](README.md).
