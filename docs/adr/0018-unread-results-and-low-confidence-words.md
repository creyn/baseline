# 18. Results that cannot be read go to review, and words OCR is unsure of are marked

Date: 2026-11-26

## Status

Accepted. Changes point 3 of [ADR-0007](0007-extraction-with-document-intelligence-and-an-llm.md) ("still invalid ends in `Failed (extract_invalid)`") and how its point 6 measures values and units. Extends points 3 and 5 of the review in [ADR-0006](0006-document-lifecycle-and-review.md): the user can also enter a result by hand at an unread place, or dismiss the place.

## Context

The first six live eval runs (2026-11-26, gpt-5.4-mini-2026-03-17, the synthetic documents of `evals/synthetic`) showed two things the extraction rules did not handle:

1. **One result fails a whole document.** The word check rejects a result whose text does not equal the words it names. When a result is still rejected after the one retry, ADR-0007 fails the whole version with `extract_invalid`, so the user gets nothing, not even the results that passed. On layout B, with long names and multi-line ranges between other columns, this happened to a different document in almost every run. One such document moved the values-and-units score by about 5 points, from 98% to 94%.
2. **OCR drops a character with low confidence.** On the scan of one document, Document Intelligence read "µIU/ml" as "IU/ml" with a confidence of 0.43, in every run. "IU/ml" is a valid unit, so code cannot correct it, and the value would be stored with the wrong unit. The model cannot see it either: it reads the words, not the image.

ADR-0006 rejected reviewing only values with low confidence, because models are often confidently wrong. Every value is reviewed. The question here is only what the review shows.

### Considered options

**A result still invalid after the retry:**
1. **Fail the version** (ADR-0007). Simple, but the user loses every result of the document because of one, and has to upload it again for nothing.
2. **Keep the results that passed, and show the one that failed on review** as a place on the page to enter by hand. Nothing is stored that was not verified. The user already reviews every result, so the result is not lost.
3. **Keep the model's text of the failed result**, marked as unverified. Faster for the user, but it shows text the word check refused, which is what the check exists to prevent.
4. **More retries.** Costs more calls, and the failures repeated after the retry in most runs.

**A word OCR is unsure of:**
1. **Nothing.** The review should catch it, but the user has no reason to look closer at that value.
2. **Mark the result for checking on review** when a word of its value or unit has a confidence below a threshold. The evals count such a result as flagged, not wrong.
3. **Send the page image to the model too.** Possibly better reading, but more tokens per page and another path for data; a separate decision if marking is not enough.

All options pass the gates (only fictional documents were used to measure). Scores from 1 to 5 on the criteria of [decision-criteria.md](../decision-criteria.md); K2, K6 and K7 barely differ between the options and are left out:

| A result still invalid | K1 (40) | K4 (15) | K5 (10) |
|---|---|---|---|
| 1. Fail the version | 2: the user loses every result | 3 | 4 |
| 2. Keep the others, unread to review | 5: nothing lost, nothing unverified stored | 5 | 5 |
| 3. Keep the model's text, unverified | 3: an unchecked value can be approved by habit | 3 | 4 |
| 4. More retries | 2: more calls, the same failures | 3 | 4 |

| A word OCR is unsure of | K1 (40) | K4 (15) | K5 (10) |
|---|---|---|---|
| 1. Nothing | 3 | 2 | 4 |
| 2. Mark the result for checking | 5: no cost, one more hint on review | 4 | 5 |
| 3. Send the image too | 3: more tokens and another data path | 4 | 3 |

## Decision

Option 2 for both (decided by the owner on 2026-11-26).

1. **A result still invalid after the retry goes to `unread`** in the `text` blob: its page, a box around the words the model named on that page (or none), and the fields that failed. Never the model's text. The other results of the batch are kept.
2. **The version still fails (`extract_invalid`)** when, after the retry, the problem is not in one result: the model refused, a document date or a fragment is invalid, or a result names a page outside the batch, which leaves no place to show it. When the retry is worse than the first answer (such a problem, or fewer verified results), the first answer is kept.
3. **A version with no verified result** but with unread ones still ends in `Failed (extract_invalid)`: there is nothing to review.
4. **The review shows each unread place** on the page, around the words of the fields that passed, and asks the user to enter the result by hand or to dismiss the place. A version cannot be approved while an unread place is neither entered nor dismissed. ADR-0006 point 5 still holds: at least one result, extracted or entered, must be accepted.
5. **`lowConfidence`** is set by code on a result when a word of its value or its unit has an OCR confidence below `LOW_CONFIDENCE` in [contracts/text_checks.py](../../contracts/text_checks.py), 0.6 as a starting value. The review marks such a result for checking. Every result is still reviewed (ADR-0006).
6. **Evals:** values and units must be 100% right, and names, ranges and flags 95%, over the results the extractor verified and returned. A wrong value or unit marked `lowConfidence` counts as flagged, not wrong. Unread, not returned and flagged results are reported with their counts. So that a run where the model reads little or nothing cannot pass, the run also fails when any document does not end in a `text` blob, and when fewer than 90% of the expected results are read and verified (a starting value).

## Consequences

- One unreadable result no longer costs the user the whole document.
- A model that leaves a few results out is not caught by the value targets; the 90% floor catches a large loss, and the weekly run shows the trend of unread and not returned results.
- The review needs two more things: unread places to fill in, and a mark on low-confidence results. The review change adds them, with what the data model does not hold yet: the state of each unread place (open, entered, dismissed) and the origin of a result entered by hand, whose `Source` is the unread box.
- `text.v1` gets `unread` and `lowConfidence` while v1 is still a draft, so no new major version is needed ([contracts/README.md](../../contracts/README.md)).
- 0.6 is a starting value, set on one case. The live evals report how many results it marks, so it can be tuned.
