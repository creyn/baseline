# Spec Delta

## Purpose

The messages between the pipeline's services and the `text` blob, written as JSON Schema, so that each service can be built and tested alone.

## ADDED Requirements

### Requirement: Contracts are JSON Schema in the repository

Every message type and every blob format that one service writes and another reads SHALL have a JSON Schema (draft 2020-12) in `contracts/`, and at least one valid example in `contracts/examples/`.

#### Scenario: The examples are valid

- **WHEN** the contract tests run
- **THEN** every example validates against its schema, and every schema has at least one example

#### Scenario: A broken example

- **WHEN** an example lacks a required field
- **THEN** the contract tests fail and name the example and the field

### Requirement: One envelope for every message

Every message body MUST carry `type`, `schemaVersion`, `userId`, `docId` and `verId`, and MUST NOT carry any text, value or image from the document. The sender SHALL set the Service Bus `subject` to `type`, the application properties `docId` and `verId`, and the trace context in `Diagnostic-Id`. `userId` MUST be our own UUIDv7, never the Entra `oid`.

#### Scenario: A message with content

- **WHEN** a message body has a field with a result value or page text
- **THEN** it does not validate against its schema, because the schemas list every allowed field of the envelope and of each type

### Requirement: Messages of the extraction path

The contracts SHALL define `ExtractRequested` (queue `extract`), `Extracted` and `Failed` (queue `status`). `Failed` MUST carry a `reason`: one of `integrity`, `check_error`, `extract_invalid`, `extract_error`, `no_results`.

#### Scenario: An unknown reason

- **WHEN** a `Failed` message has the reason `timeout`
- **THEN** it does not validate, because `timeout` is set by the API's sweeper and is never sent

### Requirement: Versioned contracts

`schemaVersion` SHALL be `major.minor`. A receiver SHALL ignore fields it does not know and SHALL decide on the major version only. Adding an optional field MUST raise the minor version. Removing any field, renaming it, changing its meaning or adding a required field MUST raise the major version, in a new schema file. For one release after a new major version, receivers MUST accept both. A receiver MUST dead-letter a message whose major version it does not support. A reader of a blob with a major version it does not support MUST treat it the same way: the API dead-letters the `Extracted` message that pointed to it, and refuses a manifest with 422 at upload.

#### Scenario: A new optional field

- **WHEN** a sender adds an optional field and sends `schemaVersion` "1.1"
- **THEN** a receiver built for the earlier contract still accepts the message

#### Scenario: An unknown version

- **WHEN** a receiver gets `schemaVersion` "2.0" and supports only major version 1
- **THEN** it sends the message to the dead-letter queue, which raises an alert

### Requirement: The minimal ZIP manifest

A clean ZIP SHALL contain `manifest.json` with `schemaVersion` and `order`, the page hashes in page order, and one `pages/{sha256}.png` per hash.

#### Scenario: Page order

- **WHEN** the extractor reads a ZIP with three pages
- **THEN** it processes them in the order of `order`, not in the order of the files in the ZIP

### Requirement: The text blob

The `text` blob of a version SHALL hold `extraction` (model, prompt version, dictionary version, extractor version, time), `pages` (each page's `sha256` and its words with id, text, box and confidence), `fragments`, `documentDates` and `results`. Boxes MUST be fractions of the page, from the top left. Every date MUST have a `kind`, and every result a `collectedAt` (or null) chosen by code.

#### Scenario: A result points to its words

- **WHEN** a result in the blob names word ids for its value
- **THEN** every id exists on the page the result names

#### Scenario: Values stay as printed

- **WHEN** a laboratory prints "<1,0" or "nie wykryto"
- **THEN** the result's `value` holds exactly that text

#### Scenario: Text that does not fit

- **WHEN** a value is longer than the `LabResult.Value` column
- **THEN** the blob does not validate, because every text field has the `maxLength` of its column in [docs/data-model.md](../../../../../../docs/data-model.md)

#### Scenario: A date with its zone

- **WHEN** a date is printed as "10.04.2026 07:25" by a laboratory in Poland
- **THEN** the blob holds it as `2026-04-10T07:25:00+02:00`, with `timeZone` `Europe/Warsaw` and `hasTime` true
