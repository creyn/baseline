# 9. One agent with tools and guardrails: questions and pre-visit summaries

Date: 2026-11-23

## Status

Accepted. The part on visits was carried over unchanged from the earlier set of decisions (2026-11-18).

## Context

The agent answers questions and writes pre-visit summaries from approved results. This ADR covers the agent, what a user may type into a question, and what the system stores about the user's care.

### One agent with tools and guardrails

The user asks questions about their results and asks for a pre-visit summary. Answers must be correct, cite their source, and never diagnose: the system organises data, the doctor interprets it.

The data is approved results in SQL and approved text fragments with vectors ([ADR-0008](0008-retrieval-without-ai-search.md)). The agent runs in the API ([ADR-0002](0002-languages-dotnet-python-and-typescript.md)), on Microsoft Agent Framework and Microsoft.Extensions.AI, with gpt-5.4 mini in the EU Data Zone.

#### Considered options

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

### Block personal identifiers in the user's questions

Documents are masked before any AI service sees them ([ADR-0003](0003-masking-in-the-browser-and-a-second-check.md)). The user's own question goes to Azure OpenAI as typed, and Azure OpenAI keeps prompts for abuse monitoring by default. A user might type:
- "I am Jan Testowy, PESEL …, is my cholesterol fine?"
- "Dr Nowak from the clinic at Prosta 5 told me to repeat TSH. What do you think?"

The health content of a question ("is a TSH of 7.6 high?") is the point of the feature and must reach the model. Age and sex ("I am 45") identify nobody on their own and help the answer.

#### Considered options

1. **Do nothing, show a warning.** One moment of inattention puts a PESEL into Azure's logs.
2. **Mask detected data silently before sending.** The question changes meaning without the user knowing, and the answer may confuse them.
3. **Block with an explanation.** The question is checked by deterministic rules for a valid PESEL, numbers of 7 or more digits, an e-mail address and a street address. On a match it is not sent, and the user sees what to remove. Names are not detected.
4. **Option 3 plus name detection** with public lists of first names and surnames. Catches names, but collides with ordinary words (Róża, Zdrowy, Biały) and could only warn, not block.

### Store only lab results, not visits

The pre-visit summary shows changes in the results, out-of-range results and questions for the doctor. A summary "since the last visit" needs to know when the last visit was, and the data model has no visits.

Storing visits raises further questions:
- **What to record:** date, specialty, purpose, doctor, clinic, recommendations.
- **The doctor's name and the clinic** are personal data of other people. Masking ([ADR-0003](0003-masking-in-the-browser-and-a-second-check.md)) removes exactly this kind of data from documents.
- **Notes and purposes are free text.** They reach the model when a summary is generated.

#### Considered options

1. **No visits. The summary covers a period the user chooses.** Nothing beyond lab results is stored. The user picks the period each time.
2. **Visits with date, specialty and a short purpose.** "Since the last visit" works by itself, per specialty, and summaries and questions are kept with the visit. However, it stores free text that needs the checks for personal identifiers (above), and a history of the user's medical appointments.
3. **Option 2 plus the doctor's name and the clinic.** Stores personal data of other people, for little gain: the user knows whom they visited.
4. **Import visits** from a calendar or the national patient portal (IKP). No typing, but integrations and consents. Too much for the first version.

## Decision

### One agent with tools and guardrails

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
   - "in range" and "out of range" come only from the result's own range ([ADR-0011](0011-lab-parameters-units-and-ranges.md)), never from the model's general knowledge.

   If a check fails, the user gets the raw results table and a suggestion to ask their doctor, instead of the generated text.
3. **The system prompt says the assistant organises and never diagnoses:** "this result is outside the lab's reference range, worth asking your doctor", never "this means X".
4. **The question is checked for personal identifiers before it is sent** (see below).
5. **Chat history lives only in the browser tab.** The browser sends it with each question; the server stores no conversation ([ADR-0012](0012-deletion-and-retention.md)). The history is neither signed nor encrypted.
6. **Answers are returned whole, not streamed.** The guardrails check the full answer before the user sees any of it; a stream would show text that may then be withdrawn. The UI shows progress while it waits. The target is a full answer within 15 seconds when warm.
7. **At most 5 tool calls per question.** After that the model must answer with what it has.

### Block personal identifiers in the user's questions

We choose option 3.

1. **The check runs in the browser**, to highlight the problem at once, **and in the API**, because the browser cannot be trusted. Both use the same rules: the PESEL and long-number rules shared with masking, plus patterns for an e-mail address and a street address, with the same tests.
2. **The question is blocked, never changed silently.** It is sent only after the user fixes it.
3. **A permanent hint next to the question field:** "Do not type names, addresses or numbers. Age and sex are fine."
4. **Names are knowingly not detected.** The question is typed on purpose by the user, unlike a document that arrives from outside.
5. **The system prompt contains no personal data of the user.**
6. **Blocked questions are not logged with their content.**

### Store only lab results, not visits

We choose option 1. The system stores lab results and the documents they come from, nothing else about the user's care.

1. **There is no visit entity.**
2. **The pre-visit summary is generated on demand** for a period the user chooses. It also uses the last value of each parameter before that period, to show the change.
3. **The summary is not stored.** The user prints it or saves it as a PDF in the browser. Generating it again gives the same facts, because they come from the stored results, not from the model.

## Consequences

### One agent with tools and guardrails

- One model call loop per question, a few rounds with tools.
- The history comes from the browser, so a user can alter it. That can only change answers about their own data, and every number still has to match a tool result. Each question sends the whole history, so long conversations cost more tokens; keeping the history on the server, with a limit on its length, is a possible later improvement.
- The guardrails make some answers fall back to a table. That is the intended failure mode.
- Evals in CI check that numbers match, sources are cited, and questions such as "am I sick?" never get a diagnosis.
- Several agents can be introduced later if one agent with more tools stops working well, which evals would show.

### Block personal identifiers in the user's questions

- A PESEL, a phone number, an e-mail or an address does not reach the model through a question, unless written in a form the rules do not recognise, such as digits spelled out in words.
- The user is never surprised by a changed question.
- A name typed by the user reaches the model. The hint reduces this; option 4 can be added later as a warning.

### Store only lab results, not visits

- No personal data of doctors or clinics is stored, and no history of the user's appointments.
- There is no free text about visits to check, store or delete.
- The user chooses the period every time. A sensible default (e.g. the last 6 months) keeps this to one click.
- Questions for the doctor are not kept between visits. If needed, the user saves the printed summary.
- Recommendations after a visit (e.g. "repeat TSH in 6 weeks") have no place in the system. Reminders, if they come back, will need their own decision.
