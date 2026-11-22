# 1. Record architecture decisions

Date: 2026-11-22

## Status

Proposed

## Context

Baseline keeps the lab results of one family. One person builds and maintains it. It processes health data, so most decisions are trade-offs between privacy, cost and simplicity. Decisions must outlive memory: months later we need to know what we chose, why, and what we rejected.

This set replaces an earlier one (ADR-0001 to ADR-0014 of 2026-11-17 to 2026-11-20). Those decisions were written before the workload, the costs and the import flow were known, and the choice of import flow changed most of them. They remain in the Git history.

### Considered options

1. **Decisions in the README.** One place, but the context and the alternatives are lost with each edit.
2. **MADR.** Considered options are required, which is its best part. Status and consequences are optional.
3. **Michael Nygard's template:** title, status, context, decision, consequences. Every section is required. Alternatives are easy to skip.
4. **Nygard's template, plus required considered options from MADR, plus fixed decision criteria.** Options are compared against the same gates and weighted criteria in every ADR.

## Decision

We choose option 4.

1. **One file per decision:** `NNNN-short-title.md`, numbered in order. Numbers are never reused.
2. **Sections:** Status, Context (with a required "Considered options" subsection), Decision, Consequences.
3. **Options are checked against [docs/decision-criteria.md](../decision-criteria.md):** gates first, then the weighted criteria when the choice is close. The workload and costs behind them are in [docs/use-cases.md](../use-cases.md).
4. **Statuses:** Proposed, Accepted, Rejected, Superseded by ADR-NNNN. An ADR is accepted when the owner merges the pull request that adds it.
5. **An accepted ADR is not rewritten.** A changed decision is a new ADR that supersedes the old one.
6. **ADRs are written in English**, in plain, short sentences.

## Consequences

- Each decision takes some writing, and the comparison of options is explicit.
- The same criteria make decisions comparable and show which trade-off was made.
- The criteria themselves can change. A change of weights is recorded in the criteria file, and old ADRs keep the scores they were made with.
