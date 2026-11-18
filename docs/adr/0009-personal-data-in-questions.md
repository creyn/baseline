# 9. Block personal identifiers in the user's questions

Date: 2026-11-18

## Status

Accepted

## Context

Documents are masked before any AI service sees them ([ADR-0003](0003-mask-personal-data-before-ai.md), [ADR-0006](0006-zone-based-masking.md)). The user's own question goes to Azure OpenAI as typed. By default, Azure OpenAI stores prompts for abuse monitoring (ADR-0003). Examples of what a user might type:
- "I am Jan Kowalski, PESEL …, is my cholesterol fine?"
- "Dr Nowak from the clinic at Prosta 5 told me to repeat TSH. What do you think?"

Two kinds of content have to be told apart:
- **The health content of the question** ("is a TSH of 7.6 high?") is the point of the feature and has to reach the model. ADR-0003 is about identifiers of people, not about medical content.
- **Age and sex** ("I am 45") do not identify anyone on their own and help the interpretation. They may pass.

### Considered options

1. **Do nothing, show a warning in the UI.** No work, but one moment of inattention puts a PESEL into Azure's logs.
2. **Mask detected data silently before sending.** Convenient, but the question changes meaning without the user knowing ("[REMOVED] told me to…"), and the answer may be confusing.
3. **Block with an explanation.** The question is checked deterministically before sending, for:
   - a PESEL with a valid checksum,
   - numbers with 7 or more digits (phone, order number),
   - an email address,
   - a postcode with a street.

   On a match, the question is not sent and the user sees what to remove, highlighted. Nothing leaks silently, and the user knows what to fix. Names are not detected.
4. **Option 3 plus name detection** with the public lists of first names and surnames from the PESEL register (see ADR-0006). Catches "Jan Kowalski", but collides with ordinary words (Róża, Zdrowy, Biały), and the surname list is very large. It could only warn, not block.

## Decision

We choose option 3.

1. **The check runs in two places:** in the browser, to highlight the problem at once, and in the API, because the browser cannot be trusted. Both use the same rules as the PESEL check in masking, with the same tests.
2. **The question is blocked, not masked silently.** It is sent only after the user fixes it.
3. **A permanent hint next to the question field:** "Do not type names, addresses or numbers. Age and sex are fine."
4. **Names are knowingly not detected.** This is the residual risk of this decision. The question is typed by the user, on purpose, unlike a document that arrives from outside.
5. **The system prompt contains no personal data of the user.** None is stored anywhere (ADR-0006).

## Consequences

- A PESEL, a phone number, an email address or an address never reaches the model through a question, unless the user writes it in a form the rules do not recognise, e.g. digits spelled out in words.
- The user is never surprised by a changed question.
- The rules are shared with masking, so a fix in one place fixes both.
- A name typed by the user reaches the model. The hint reduces this, and option 4 can be added later as a warning.
- Blocked questions are not logged with their content, so the check itself does not store the data it rejected.
