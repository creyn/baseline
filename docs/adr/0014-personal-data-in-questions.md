# 14. Block personal identifiers in the user's questions

Date: 2026-11-22

## Status

Proposed

## Context

Documents are masked before any AI service sees them ([ADR-0003](0003-mask-in-the-browser-check-again-on-the-server.md)). The user's own question goes to Azure OpenAI as typed, and Azure OpenAI keeps prompts for abuse monitoring by default. A user might type:
- "I am Jan Testowy, PESEL …, is my cholesterol fine?"
- "Dr Nowak from the clinic at Prosta 5 told me to repeat TSH. What do you think?"

The health content of a question ("is a TSH of 7.6 high?") is the point of the feature and must reach the model. Age and sex ("I am 45") identify nobody on their own and help the answer.

### Considered options

1. **Do nothing, show a warning.** One moment of inattention puts a PESEL into Azure's logs.
2. **Mask detected data silently before sending.** The question changes meaning without the user knowing, and the answer may confuse them.
3. **Block with an explanation.** The question is checked by deterministic rules for a valid PESEL, numbers of 7 or more digits, an e-mail address and a street address. On a match it is not sent, and the user sees what to remove. Names are not detected.
4. **Option 3 plus name detection** with public lists of first names and surnames. Catches names, but collides with ordinary words (Róża, Zdrowy, Biały) and could only warn, not block.

## Decision

We choose option 3.

1. **The check runs in the browser**, to highlight the problem at once, **and in the API**, because the browser cannot be trusted. Both use the same rules as masking, with the same tests.
2. **The question is blocked, never changed silently.** It is sent only after the user fixes it.
3. **A permanent hint next to the question field:** "Do not type names, addresses or numbers. Age and sex are fine."
4. **Names are knowingly not detected.** The question is typed on purpose by the user, unlike a document that arrives from outside.
5. **The system prompt contains no personal data of the user.**
6. **Blocked questions are not logged with their content.**

## Consequences

- A PESEL, a phone number, an e-mail or an address does not reach the model through a question, unless written in a form the rules do not recognise, such as digits spelled out in words.
- The user is never surprised by a changed question.
- A name typed by the user reaches the model. The hint reduces this; option 4 can be added later as a warning.
