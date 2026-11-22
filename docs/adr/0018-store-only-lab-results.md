# 18. Store only lab results, not visits

Date: 2026-11-22

## Status

Proposed. Carried over unchanged from the earlier set of decisions (2026-11-18).

## Context

The pre-visit summary shows changes in the results, out-of-range results and questions for the doctor. A summary "since the last visit" needs to know when the last visit was, and the data model has no visits.

Storing visits raises further questions:
- **What to record:** date, specialty, purpose, doctor, clinic, recommendations.
- **The doctor's name and the clinic** are personal data of other people. Masking ([ADR-0004](0004-zone-based-masking.md)) removes exactly this kind of data from documents.
- **Notes and purposes are free text.** They reach the model when a summary is generated.

### Considered options

1. **No visits. The summary covers a period the user chooses.** Nothing beyond lab results is stored. The user picks the period each time.
2. **Visits with date, specialty and a short purpose.** "Since the last visit" works by itself, per specialty, and summaries and questions are kept with the visit. However, it stores free text that needs the checks from [ADR-0014](0014-personal-data-in-questions.md), and a history of the user's medical appointments.
3. **Option 2 plus the doctor's name and the clinic.** Stores personal data of other people, for little gain: the user knows whom they visited.
4. **Import visits** from a calendar or the national patient portal (IKP). No typing, but integrations and consents. Too much for the first version.

## Decision

We choose option 1. The system stores lab results and the documents they come from, nothing else about the user's care.

1. **There is no visit entity.**
2. **The pre-visit summary is generated on demand** for a period the user chooses. It also uses the last value of each parameter before that period, to show the change.
3. **The summary is not stored.** The user prints it or saves it as a PDF in the browser. Generating it again gives the same facts, because they come from the stored results, not from the model.

## Consequences

- No personal data of doctors or clinics is stored, and no history of the user's appointments.
- There is no free text about visits to check, store or delete.
- The user chooses the period every time. A sensible default (e.g. the last 6 months) keeps this to one click.
- Questions for the doctor are not kept between visits. If needed, the user saves the printed summary.
- Recommendations after a visit (e.g. "repeat TSH in 6 weeks") have no place in the system. Reminders, if they come back, will need their own decision.
