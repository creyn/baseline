# Design

## Context

After the second check, a version's pages lie in `clean/{userId}/{docId}/{verId}.zip`, and the checker sends `ExtractRequested` ([ADR-0005](../../../docs/adr/0005-asynchronous-import-pipeline.md)). The extractor reads the pages, calls Document Intelligence and an LLM ([ADR-0007](../../../docs/adr/0007-extraction-with-document-intelligence-and-an-llm.md)), writes `text/{userId}/{docId}/{verId}.json`, and reports `Extracted` or `Failed` to the `status` queue. The API reads `text` and stores the results as `PendingReview` ([ADR-0006](../../../docs/adr/0006-document-lifecycle-and-review.md)).

The checker and the API do not exist yet. This change defines the contracts they will use, builds the extractor, and measures it on the synthetic documents ([evals/synthetic](../../../evals/synthetic/README.md)).

## Goals / Non-Goals

**Goals:**
- Contracts precise enough to build the checker, the extractor and the API's status consumer separately.
- A data model for the import path that the API can implement without guessing.
- An extractor whose numbers can be checked against the page, not trusted from the model.
- Evals that say, for every change of the prompt or the model, whether values and units are still 100% correct.

**Non-Goals:**
- The checker, the API, the UI, and the infrastructure.
- Normalised values, computed flags and the parameter dictionary ([ADR-0011](../../../docs/adr/0011-lab-parameters-units-and-ranges.md)): they run in .NET at approval.
- Tuning the batch size. It starts at 5 pages, as ADR-0007 says.

## Decisions

### Messages

- **One envelope for every message:** `type`, `schemaVersion`, `userId`, `docId`, `verId`, plus the fields of the type. The Service Bus message also sets `subject` to the type and the application properties `docId` and `verId`, so the dead-letter queue can be read without opening the body. The trace context travels in `Diagnostic-Id`, and `CorrelationId` is not used ([ADR-0015](../../../docs/adr/0015-internal-user-id-and-log-identifiers.md)). The body never carries content of the document ([ADR-0005](../../../docs/adr/0005-asynchronous-import-pipeline.md), point 4).
- **`userId` travels in every message**, because blob paths start with it and the API's status consumer runs as that user for Row-Level Security ([ADR-0010](../../../docs/adr/0010-identity-users-and-consent.md)). It is our own UUIDv7, never the Entra `oid` ([ADR-0015](../../../docs/adr/0015-internal-user-id-and-log-identifiers.md)).
- **This change defines three types:**
  - `ExtractRequested` (queue `extract`): the envelope only.
  - `Extracted` (queue `status`): the envelope only. The results are in `text`, the claim check.
  - `Failed` (queue `status`): the envelope plus `reason`. The extractor sends `extract_invalid`, `extract_error` or `no_results`. The schema also allows `integrity` and `check_error`, which the checker will send. `timeout` is never a message: the API's sweeper sets it.
- **Versioning, so that the first version can change:**
  - Schemas are strict: they list every allowed field, so a sender's tests catch a field that should not be there (content of the document, a typo).
  - Required means the sender must provide it, whoever reads it. A field that only a later reader needs is still required; each receiver reads only the fields it knows and ignores the rest.
  - `schemaVersion` is `major.minor`, a string such as `"1.0"`. Adding an optional field raises the minor version; receivers need no change, and the minor version shows in logs which sender wrote the message.
  - Removing a field (optional ones too, since a receiver may use them), renaming it, changing its meaning or adding a required field raises the major version. The schema file carries the major version in its name (`messages.v1.schema.json`); a new major version is a new file next to the old one. For one release, receivers accept both, the same expand-then-contract rule as database migrations ([ADR-0004](../../../docs/adr/0004-serverless-hosting-and-operations.md)).
  - A receiver decides on the major version only. A major version it does not know goes to the dead-letter queue, which raises an alert.
  - Until the first release, nothing has sent a v1 message, so v1 is still a draft and can change without a new major version.
- **Contracts are JSON Schema (draft 2020-12) in `contracts/`.** Every service validates what it sends in its tests. Examples in `contracts/examples/` are valid messages, checked by a test, and used by the services' tests.

### The ZIP manifest, minimal

The extractor needs the order of the pages. The ZIP holds `manifest.json` with `schemaVersion` and `order`, the page hashes in page order, and `pages/{sha256}.png`. The checker change adds the other fields drawn in U2 (`keptRegions`, `originalSha256`); the extractor ignores them.

### The `text` blob

One JSON file per version, written once. It holds:

- **`extraction`:** how it was made (the model deployment, `promptVersion`, `dictionaryVersion`, the extractor's version, the time), as ADR-0006 point 11 requires.
- **`pages`:** for each page in the manifest's order, its `sha256` and its words. A word has an id (`p{page}w{n}`), its text, its box and the confidence from Document Intelligence.
- **Boxes are fractions of the page** (`x`, `y`, `w`, `h` between 0 and 1, from the top left). Document Intelligence answers in inches for a PDF; fractions do not depend on the unit or on the size of the PNG the UI shows.
- **`fragments`:** comments and descriptions, never result rows, with their page and box. The API embeds them at approval ([ADR-0008](../../../docs/adr/0008-retrieval-without-ai-search.md)).
- **`documentDates`:** dates that belong to the whole document (registration, collection), never the date of birth.
- **`results`:** one entry per result (see below).

### Every value is tied to words on the page

The model never writes a box. It gets the words with their ids, and for the name, the value, the unit and the range of each result it returns the text **and the ids of the words it read it from**. Code then checks that the text equals those words, after removing spaces and a trailing footnote marker (`*`). A value the model typed but did not read fails the check. When the value and the unit share one word ("18ng/ml"), the value must be the whole number at the start of the word, so the split cannot move. OCR misreads some characters in units ("tys/ul" for "tys/µl", "U/I" for "U/l", "min/ul" for "mln/µl"; seen on the first live run, 2026-11-26). A unit read like that, which can only stand for one unit of a fixed list, is replaced by that unit; the words keep the reading, so the review still shows what OCR read. The check accepts the corrected unit for those words and nothing else. Long names and ranges run over several lines, between other columns, and the model often lists their word ids a little wrong (a mark printed between the lines added, such as an accreditation "A" or a procedure code "V2.4", or a word left out; seen on the live runs, 2026-11-26). When the text does not equal the listed words, code looks for the text on the page in reading order from the first listed word, skipping only such marks inside it, and keeps the words it found if they hold every listed word that is not a mark. The text is never changed, so a name that is not printed, a cut name or one band picked from a range still fails. A range with more than one band must have kind `text` and no bounds, or it fails the check. A failed check tells the model on the retry whether the ids hold more words than the text or fewer, without quoting the page. The check is in [contracts/text_checks.py](../../../contracts/text_checks.py), shared by the extractor and the contract tests.

This is principle 2 of the [README](../../../README.md) applied inside extraction: the model proposes, code verifies against the OCR layer, the user approves. Boxes for highlighting are computed from the word ids.

### A result

`name`, `value` and `unit` as printed; `range` as printed text, with `low` and `high` as printed strings when the range has bounds, and `kind` (`interval`, `lt`, `gt`, `text`, `none`). A range printed with several lines, bands or conditions ("na czczo: <150, nie na czczo: <175", a table of vitamin D bands) is the whole printed text, with `kind` `text` and no bounds: picking one band would be an interpretation, and Baseline does not diagnose (owner, 2026-11-26). Such a result then has no computed flag ([ADR-0011](../../../docs/adr/0011-lab-parameters-units-and-ranges.md)), only the laboratory's; `flagPrinted`, the laboratory's marker as printed ("H", "↑", "*"; not an accreditation mark "A", a procedure code or a footnote "*" on the unit), and `flag`, mapped from it by code with a fixed table (`H` and `↑` to `H`, `L` and `↓` to `L`, anything else to none, so the computed flag of ADR-0011 is not hidden by a guess); `icd9`, `material`, `condition`, `method`, `analyser` (each may be missing); `dates`; `suggestedParameter` (always empty until the dictionary exists); `source` with the page and the word ids of each field.

Values stay text: "<1,0" and "nie wykryto" are valid values. Parsing numbers, converting units and computing flags happen in .NET ([ADR-0011](../../../docs/adr/0011-lab-parameters-units-and-ranges.md)).

### Dates

The model returns each date's label, its text as printed, and the local date and time it reads (`2026-04-10T07:25`, or a date alone). Code, not the model, adds the zone and the offset ([ADR-0007](../../../docs/adr/0007-extraction-with-document-intelligence-and-an-llm.md), point 2): `Europe/Warsaw` by default, the earlier offset in the hour repeated in autumn, midnight and `hasTime: false` for a date without a time. A time in the hour skipped in spring is invalid. The model also gives each date a `kind` from its label: `collected`, `registered`, `received`, `performed`, `released`, `printed` or `other`.

Every result gets `collectedAt`, the date its trend uses, and `collectedHasTime`. Code picks it from the labelled dates in this order of kind: `collected`, `received`, `registered`, `performed`, `released` (never `printed`). Within a kind, the result's own dates win over the document's, and the earliest wins. Without any such date it is null; the review then asks the user for it, and a result cannot be approved without it. The user can correct it on review. The word check also checks that `collectedAt` is the date this rule picks. The date of birth is never on a masked page ([ADR-0003](../../../docs/adr/0003-masking-in-the-browser-and-a-second-check.md)), so extraction does not look for it.

### The extractor

- **Python 3.12**, in `services/extractor/`. The core is a function from pages to the `text` document, with the AI services behind two small interfaces. The service shell around it reads the queue and the blobs.
- **Steps for one message:**
  1. If `text/…/{verId}.json` exists, send `Extracted` and stop. A retry never calls the AI services again.
  2. Read the clean ZIP. If it is gone, the version was deleted or replaced: complete the message and log it. If it never comes back, the sweeper times the version out.
  3. Build one image-only PDF of all pages in memory and call `prebuilt-layout` once.
  4. Send the words to the LLM in batches of 5 pages, with structured output from a pydantic model.
  5. Validate: the schema, the word ids, the dates. An invalid batch gets one retry with the errors. Still invalid: `Failed (extract_invalid)`.
  6. No results in any batch: `Failed (no_results)`.
  7. Write the blob with `If-None-Match: *`. If another run wrote it first, keep theirs.
  8. Send `Extracted` and complete the message.
- **Retries ([ADR-0005](../../../docs/adr/0005-asynchronous-import-pipeline.md), point 6):** the message lock is renewed while the work runs. A transient error (HTTP 429 or 5xx from an AI service, a storage or Service Bus error) abandons the message while `deliveryCount` is below 5; on the fifth try the extractor sends `Failed (extract_error)` and completes it. An invalid answer is not transient and does not wait for five tries. A clean ZIP that breaks its contract, or any other unexpected error, sends `Failed (extract_error)` at once, because retrying would call the AI services again for the same result; the log names only the error type. On the last delivery the extractor checks for the `text` blob first, so a version whose results were saved is reported as `Extracted`.
- **A failure is not stored.** After `no_results` or `extract_invalid` nothing is written, so a redelivery (a crash after sending `Failed`, before completing the message) calls the AI services again. The API ignores the second `Failed`. Accepted: it is rare and costs a few cents.
- **Two runs of the same message at once** both write with `If-None-Match: *`; one wins, both send `Extracted`, and the API's forward-only update ignores the second.
- **Deleted while in progress:** the extractor may write `text` after the deletion. The sweeper removes blobs that have no version row ([ADR-0012](../../../docs/adr/0012-deletion-and-retention.md)).
- **Logs** go to Application Insights through OpenTelemetry. They carry `userId`, `docId`, `verId` and the trace context from `Diagnostic-Id` ([ADR-0015](../../../docs/adr/0015-internal-user-id-and-log-identifiers.md)), page and result counts, tokens and durations. Never words, values or prompts.
- **Identity:** the extractor's managed identity reads `clean`, writes `text`, receives from `extract`, sends to `status`, and calls Document Intelligence and Azure OpenAI. Nothing else. It has no database access ([ADR-0002](../../../docs/adr/0002-languages-dotnet-python-and-typescript.md)).
- **The prompt** lives in a file with a version in its name (`extract.v1`). Changing the prompt means a new file and a new version, so every `text` blob says which prompt made it.

### The data model

The tables are in [docs/data-model.md](../../../docs/data-model.md), one place for the API and the reviewers. It covers documents, versions, extractions and results. A result has its printed name, the confirmed parameter (`ParameterCode`, set by the review) and `CollectedAt` for trends; all labelled dates are kept as JSON, because their number and labels differ between laboratories and nothing queries them. Users, consent, fragments, aliases and normalised values are added there by the changes that need them.

### Evals

- **The truth** comes from `evals/synthetic/describe.py` (`expected_extraction`), the same function the generator uses.
- **Matching:** an extracted result matches an expected one on the same page with the same printed name, after removing spaces and case. Each expected result is matched at most once.
- **Metrics:**
  - values and units exactly right, over all expected results (target 100%, the run fails below it);
  - names, ranges and flags as printed (target 95%, the run fails below it). ADR-0007 sets the 95% on normalised names and ranges; normalisation does not exist yet ([ADR-0011](../../../docs/adr/0011-lab-parameters-units-and-ranges.md), in .NET), so this change measures the printed form, and the normalisation change adds the normalised metric;
  - missing and extra results (counted and reported);
  - material, condition, method and dates (reported, no target yet).
- **Offline run, on every pull request, free:**
  - The layout is built from the description: one line per section title, date, result row and method, every token a word with a box. It is not the rendered page, so the run needs no generator and runs anywhere with the standard library and jsonschema; rendering and OCR are the live run's job.
  - The "LLM" is a fake that answers from the truth, naming the ids the core gave to those words.
  - It tests everything except the models: batching, the word check, dates, validation, the `text` schema and the scoring. The score must be 100%; anything less is a bug in our code.
- **Live run:** real Document Intelligence and gpt-5.4 mini on every form of every synthetic document (text, scan and photo). It runs on pull requests that change `services/extractor/**`, `contracts/**` or `evals/**`, every Monday ([ADR-0017](../../../docs/adr/0017-catching-changes-on-the-ai-services.md)), and on demand. The pages are the generated ones, rendered to PNG at 200 DPI. They are fictional but not masked, so the header with the invented patient is still there. How much masking changes the results (for example a registration date in the header) is to check, once masking runs on the server side and the evals can mask the pages first. The report names the model version that answered. The report is a JSON artifact and a table in the job summary. Evals call the extractor's core function and never touch storage or queues ([ADR-0004](../../../docs/adr/0004-serverless-hosting-and-operations.md)).

### Live evals: what the owner sets up

Live evals need Azure resources that do not exist yet. They cost money and change the subscription, so the owner creates them:

1. Document Intelligence (S0) and Azure OpenAI with a gpt-5.4 mini deployment in the EU Data Zone, in Sweden Central, with a pinned model version and `versionUpgradeOption: OnceCurrentVersionExpired` ([ADR-0017](../../../docs/adr/0017-catching-changes-on-the-ai-services.md)). The option must be set explicitly: a deployment created with `az cognitiveservices account deployment create` got `OnceNewDefaultVersionAvailable` (checked 2026-11-26), so it is set through the management API.
2. An identity for GitHub Actions with a federated credential for the GitHub environment `evals`, and the role "Cognitive Services User" on those two resources only. The credential's subject must be the one GitHub presents: for this repository it carries the owner and repository IDs, `repo:<owner>@<id>/<repo>@<id>:environment:evals`, not `repo:<owner>/<repo>:environment:evals` (checked on the first run, 2026-11-26).
3. Variables (not secrets) that `.github/workflows/evals.yml` reads: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `DOCUMENT_INTELLIGENCE_ENDPOINT`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, and optionally `AZURE_OPENAI_API_VERSION`.
4. A budget alert. [ADR-0004](../../../docs/adr/0004-serverless-hosting-and-operations.md) names 10 USD a month; the subscription bills in EUR, so the alert is set at 10 EUR, close enough for an alert (owner, 2026-11-26).

The Bicep for these resources comes with the infrastructure change. Until the owner creates them, the live run is skipped when the variables are missing.

## Risks / Trade-offs

- **A fake LLM in the offline run proves only our code.** Model quality is measured only by the live run, which needs Azure.
- **Synthetic documents are cleaner than real ones.** The scan and photo forms add noise. Evals on real documents stay a manual step for the owner, outside the repository.
- **A result that spans two batches** can be split or repeated. ADR-0007 says the evals include such documents, so the evals part adds a synthetic document of 7 pages with a result block that continues from page 5 to page 6. No single result row is split across pages, as on real printouts.
- **A continued block loses its dates.** Pages 5 and 6 are in different batches, so the results on page 6 do not see the collection date printed with their block on page 5, and `collectedAt` falls back to the document's registration date. Known limitation: the review shows `collectedAt` and the user corrects it. Passing the last block's dates to the next batch is a later improvement, measured by the same document.
- **The word check can reject a correct answer** when a value is printed in one word with its unit ("18ng/ml"). The check allows a value that is the start of one word, and the unit the rest of it.
