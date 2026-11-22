# 12. One agent with tools and guardrails

Date: 2026-11-22

## Status

Proposed

## Context

The user asks questions about their results and asks for a pre-visit summary. Answers must be correct, cite their source, and never diagnose: the system organises data, the doctor interprets it.

The data is approved results in SQL and approved text fragments with vectors ([ADR-0011](0011-retrieval-without-ai-search.md)). The agent runs in the API ([ADR-0002](0002-split-between-dotnet-and-python.md)), on Microsoft Agent Framework and Microsoft.Extensions.AI, with gpt-5.4 mini in the EU Data Zone.

### Considered options

1. **One agent with tools** that query SQL and search text, with guardrails on the answer.
2. **Several agents** (a router plus specialists for trends, text and summaries). More moving parts and more model calls per question, for a domain small enough for one agent.
3. **One agent, with its tools served by an MCP server** inside the API. Shows the protocol, but adds a layer with no functional gain. The tools return health data, so the MCP endpoint would have to stay internal, carry the user's identity and be tested to be unreachable from outside.

Exposing the user's results to external MCP clients (for example a desktop assistant) was rejected outright: health data would leave our Azure boundary for a model we do not control (G1, G2).

| Criterion (weight) | 1: one agent | 2: several agents | 3: tools via MCP |
|---|---|---|---|
| K1 simple, self-healing (40) | 5 | 3 | 4 |
| K2 cost (20) | 5 | 4 | 4 |
| K4 engineering practice (15) | 4 | 3 | 4 |
| K5 testable in CI (10) | 4 | 3 | 3 |
| K6 time to deliver (10) | 4 | 4 | 4 |
| K7 performance (5) | 4 | 4 | 4 |
| **Result** | **92** | **67** | **78** |

## Decision

We choose option 1.

1. **Tools:**
   - `get_trend(parameter, from, to)`: the series of a parameter with ranges and sources;
   - `list_out_of_range(since)`: results outside their own reference range;
   - `period_summary(from, to)`: the data for a pre-visit summary, with the last value before the period;
   - `search_text(query)`: approved text fragments by meaning.

   Every tool filters by the signed-in user and by `Approved`, and returns the document, version and page hash of every row.
2. **Guardrails on every answer, in code:**
   - every number in the answer must match a value returned by a tool;
   - every claim must cite a source returned by a tool;
   - "in range" and "out of range" come only from the result's own range ([ADR-0016](0016-reference-ranges.md)), never from the model's general knowledge.

   If a check fails, the user gets the raw results table and a suggestion to ask their doctor, instead of the generated text.
3. **The system prompt says the assistant organises and never diagnoses:** "this result is outside the lab's reference range, worth asking your doctor", never "this means X".
4. **The question is checked for personal identifiers before it is sent** ([ADR-0014](0014-personal-data-in-questions.md)).
5. **Chat history lives only in the browser tab.** The browser sends it with each question; the server stores no conversation ([ADR-0019](0019-deletion-and-retention.md)).
6. **Answers are streamed** to the UI.

## Consequences

- One model call loop per question, a few rounds with tools.
- The guardrails make some answers fall back to a table. That is the intended failure mode.
- Evals in CI check that numbers match, sources are cited, and questions such as "am I sick?" never get a diagnosis.
- Several agents can be introduced later if one agent with more tools stops working well, which evals would show.
