# Spec Delta

## Purpose

The extractor turns the masked pages of a checked version into results in the `text` blob, and evals measure how well it does it on the synthetic documents.

## ADDED Requirements

### Requirement: Extraction with the layout and an LLM in batches

The extractor SHALL send all pages of a version to Document Intelligence `prebuilt-layout` in one call, as one image-only PDF built in memory, and SHALL send the words to the LLM in batches of at most 5 pages, using structured output.

#### Scenario: Seven pages

- **WHEN** a version has seven pages
- **THEN** Document Intelligence is called once, and the LLM is called for pages 1–5 and 6–7

### Requirement: Every value is read from the page

For the name, the value, the unit and the range of every result, the LLM MUST return the ids of the words it read them from. The extractor MUST reject a result whose text does not equal those words, after removing spaces and a trailing footnote marker.

#### Scenario: A value the model did not read

- **WHEN** the model returns the value "18" with word ids whose text is "16"
- **THEN** the batch is invalid and is sent once more with the error

#### Scenario: A unit with a footnote marker

- **WHEN** the page prints "ng/ml*" and the model returns the unit "ng/ml"
- **THEN** the check passes

#### Scenario: Still invalid

- **WHEN** a batch is invalid twice
- **THEN** the extractor sends `Failed` with the reason `extract_invalid`

### Requirement: Dates get their zone from code

The extractor SHALL convert each local date and time from the model into a time with an offset, in `Europe/Warsaw` by default, using the offset in force on that day. A date without a time MUST be stored at midnight with `hasTime` false. Code SHALL set each result's `collectedAt` from the labelled dates in this order of kind: `collected`, `received`, `registered`, `performed`, `released`; within a kind the result's own dates before the document's, and the earliest first. Without such a date it SHALL be null.

#### Scenario: Winter time

- **WHEN** a result was collected on "2026-01-15 07:50"
- **THEN** the stored time is `2026-01-15T07:50:00+01:00`

#### Scenario: The hour repeated in autumn

- **WHEN** a printed time falls in the hour repeated when clocks go back
- **THEN** the earlier offset (+02:00) is used

#### Scenario: The date for the trend

- **WHEN** a result has no dates of its own and the document has "Data rejestracji" and "Data/godz. pobrania"
- **THEN** its `collectedAt` is the collection date

#### Scenario: Only a date of performing

- **WHEN** the only dates are "Data wykonania" and "Data wydruku"
- **THEN** `collectedAt` is the date of performing, never the printed date

### Requirement: No results means not a lab result

When every batch is valid and none has a result, the extractor SHALL send `Failed` with the reason `no_results`.

#### Scenario: A page with text but no results

- **WHEN** the pages hold only a letter
- **THEN** the version fails with `no_results`, and no `text` blob is written

### Requirement: Idempotent and retried

The extractor MUST NOT call an AI service for a version whose `text` blob exists. It SHALL write the blob only if it does not exist. A transient error SHALL abandon the message while its delivery count is below 5; on the fifth delivery the extractor SHALL send `Failed` with the reason `extract_error`.

#### Scenario: A message delivered twice

- **WHEN** `ExtractRequested` arrives for a version that already has its `text` blob
- **THEN** the extractor sends `Extracted` without calling Document Intelligence or the LLM

#### Scenario: Two runs at once

- **WHEN** two runs of the same version both try to write the blob
- **THEN** one write succeeds, the other keeps the stored blob, and both send `Extracted`

#### Scenario: The service is down

- **WHEN** Document Intelligence answers 503 on deliveries 1 to 4
- **THEN** each delivery abandons the message, and the fifth sends `Failed` with `extract_error`

#### Scenario: The version was deleted

- **WHEN** the clean ZIP no longer exists
- **THEN** the extractor completes the message without sending a status and logs the version id

### Requirement: Nothing from the document in logs

Logs and telemetry of the extractor MUST carry `userId`, `docId`, `verId` and the trace context, and otherwise only counts, token use and durations, never words, values or prompts.

#### Scenario: An invalid answer

- **WHEN** a batch fails validation
- **THEN** the log names the field and the rule that failed, never the value

### Requirement: Evals on the synthetic documents

Evals SHALL run the extractor's core on every synthetic document and compare the results with the truth from `evals/synthetic/describe.py`. Values and units MUST be 100% correct, and names, ranges and flags as printed at least 95%; below either target the run fails. The evals MUST include a document with a result block that crosses a batch boundary.

#### Scenario: Offline run on a pull request

- **WHEN** a pull request runs CI
- **THEN** evals run with the layout taken from the generated text PDFs and a fake LLM that answers from the truth, and every metric is 100%

#### Scenario: Live run

- **WHEN** a pull request changes the extractor, its contracts or the evals, or it is Monday, and the Azure variables are set
- **THEN** evals run against Document Intelligence and gpt-5.4 mini on every form of every document, and the job summary shows each metric per document and form

#### Scenario: No Azure yet

- **WHEN** the Azure variables are not set
- **THEN** the live run is skipped with a notice, and CI stays green
