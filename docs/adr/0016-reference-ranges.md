# 16. Reference ranges are stored with each result

Date: 2026-11-22

## Status

Proposed. Carried over unchanged from the earlier set of decisions (2026-11-18).

## Context

A reference range is not one number per parameter.

1. **Every laboratory has its own ranges.** They depend on the method and the analyser. For TSH, for example, one laboratory prints 0.27–4.20 and another 0.40–4.00.
2. **Ranges change over time**, with a new reagent or analyser, and with the patient's age. Lab reports say so explicitly, e.g. "age-specific reference ranges were applied".
3. **Ranges come in many forms:**
   - an interval ("0.27–4.20"),
   - one-sided ("<190", ">30"),
   - descriptive ("negative"),
   - several ranges at once (hormones by cycle phase, age bands),
   - missing.
4. **A flag (H, L) is printed on most reports, but not all.** A flag computed by us could disagree with the printed one.

### Considered options

1. **One global range per parameter**, from a table in code. Simple, but wrong: a result within the range of its laboratory may look out of range against our table, while the doctor reads the range on the report.
2. **The range stored with each result, as printed.** Always matches what the doctor saw. Changes over time and between laboratories show up by themselves. The range moves on the chart, which has to be shown clearly.
3. **A table of ranges per laboratory and period**, built from the documents. Stores fewer duplicates, but needs the laboratory and the validity dates to be recognised, and gains nothing over option 2.
4. **Option 2 plus a personal target set by the user**, e.g. a vitamin D target of 30–50 recommended by their doctor, or LDL below 70. A separate line on the chart, not a laboratory range.

## Decision

We choose option 2 now. Option 4 is in the backlog.

1. **Every result stores its range in two forms:**
   - as text, exactly as printed;
   - parsed: lower bound, upper bound, and kind (interval, "<", ">", descriptive).

   If the range cannot be parsed, e.g. several ranges at once, only the text is kept and no flag is computed from it.
2. **The laboratory's flag wins.**
   - We compute a flag only when the report has none, and mark it as computed.
   - If both exist and disagree, the review screen shows it, because it often means an extraction error.
3. **On the chart, the range is a band that can change at every point.** A change of ranges by the laboratory is visible. Each point is coloured against the range of its own result.
4. **The range is converted together with the value** ([ADR-0015](0015-unit-normalisation.md)).
5. **The agent judges "in range" or "out of range" only against the range of the result itself**, never against the model's general knowledge. This becomes part of the agent guardrails.

## Consequences

- What the user sees always matches the report the doctor saw.
- There is no reference range table to maintain.
- Ranges that cannot be parsed are still shown as text, but they give no computed flag and no band on the chart.
- A disagreement between the printed and the computed flag doubles as a check on extraction.
- A personal target, if added later, is kept apart from laboratory ranges, so the two cannot be confused.
