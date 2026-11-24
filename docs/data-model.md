# Data model

The tables in Azure SQL, written by the API only ([ADR-0002](adr/0002-languages-dotnet-python-and-typescript.md)). This is the first version: it covers the import path, from the upload to results waiting for review. Each later change adds its tables here (users and consent, fragments, aliases, normalised values, review corrections).

The decisions behind it: identifiers and statuses in [ADR-0006](adr/0006-document-lifecycle-and-review.md), results in [ADR-0007](adr/0007-extraction-with-document-intelligence-and-an-llm.md) and [ADR-0011](adr/0011-lab-parameters-units-and-ranges.md), isolation in [ADR-0010](adr/0010-identity-users-and-consent.md) and [ADR-0015](adr/0015-internal-user-id-and-log-identifiers.md), deletion in [ADR-0012](adr/0012-deletion-and-retention.md). What extraction writes is in the `text` contract ([contracts/](../contracts/README.md)).

## Rules for every table

- **Every table has `UserId`** (`uniqueidentifier`, our own UUIDv7 for the person, never the Entra `oid`; [ADR-0015](adr/0015-internal-user-id-and-log-identifiers.md)) and a Row-Level Security policy on it. Background work sets the user from the message before it touches a table.
- **Keys are UUIDv7** made by the API (`uniqueidentifier`).
- **Times written by the system** are `datetimeoffset` in UTC. Dates read from a document keep the offset of their zone.
- **Hashes** are `binary(32)` (SHA-256).
- **Deletion cascades** from `Document` to everything below it.
- **Text as printed** is `nvarchar`, because results are in Polish. Its lengths are the `maxLength` values in [contracts/text.v1.schema.json](../contracts/text.v1.schema.json), so a valid blob always fits; a longer text fails extraction with `extract_invalid`.

## Document

One original of one user.

| Column | Type | Notes |
|---|---|---|
| `Id` | uniqueidentifier | PK, `docId` |
| `UserId` | uniqueidentifier | |
| `OriginalSha256` | binary(32) | the hash of the original, or of the sorted hashes of several photos |
| `CreatedAt` | datetimeoffset | |

Unique index on (`UserId`, `OriginalSha256`): the same file imported again returns the existing document.

## Version

One masked upload of a document, or a reprocessed copy of one.

| Column | Type | Notes |
|---|---|---|
| `Id` | uniqueidentifier | PK, `verId` |
| `DocumentId` | uniqueidentifier | FK to `Document` |
| `UserId` | uniqueidentifier | |
| `ZipSha256` | binary(32) | the hash of the uploaded ZIP; null for a reprocessed copy |
| `ReprocessOf` | uniqueidentifier, null | the version whose checked ZIP was copied (U9); no foreign key, because a failed source is deleted ([ADR-0016](adr/0016-retry-replaces-a-failed-version.md)) |
| `Status` | varchar(16) | `Uploaded`, `Blocked`, `PendingReview`, `Approved`, `Archived`, `Superseded`, `Failed` |
| `FailReason` | varchar(16), null | `integrity`, `check_error`, `extract_invalid`, `extract_error`, `no_results`, `timeout`. A failed version is deleted when the document gets a new version ([ADR-0016](adr/0016-retry-replaces-a-failed-version.md)) |
| `StatusChangedAt` | datetimeoffset | the sweeper reads it |
| `ResendCount` | tinyint | how many times the sweeper sent the first message again (at most 3) |
| `BlockedRegions` | nvarchar(max), null | JSON: page and rectangle, never text (`Blocked`) |
| `DocumentDates` | nvarchar(max), null | JSON: `documentDates` from the `text` blob (label, text, time, zone, kind) |
| `CreatedAt` | datetimeoffset | |
| `RowVersion` | rowversion | optimistic concurrency on review |

Indexes:
- (`DocumentId`, `ZipSha256`), unique, filtered `WHERE ZipSha256 IS NOT NULL AND Status IN ('Uploaded', 'Blocked', 'PendingReview', 'Approved')` ([ADR-0016](adr/0016-retry-replaces-a-failed-version.md)). A retry of the same upload returns the live version made by the first try; the same ZIP after a failure, or after its version was superseded, makes a new version, and the failed version is deleted. A reprocessed copy has no hash, so it never collides with the version it was copied from.
- (`DocumentId`), unique, filtered `WHERE Status = 'Approved'`: at most one approved version per document.
- (`Status`, `StatusChangedAt`): the sweeper's query.

Status changes are forward-only: `UPDATE … SET Status = @new, StatusChangedAt = SYSUTCDATETIME() WHERE Id = @verId AND Status = @expected`.

## Extraction

How a version was extracted ([ADR-0006](adr/0006-document-lifecycle-and-review.md), point 11). A version has at most one extraction, so the key is the version's id. Copied from `extraction` in the `text` blob.

| Column | Type | Notes |
|---|---|---|
| `VersionId` | uniqueidentifier | PK, FK to `Version` |
| `UserId` | uniqueidentifier | |
| `Model` | varchar(64) | the model deployment |
| `PromptVersion` | varchar(32) | `extract.v1` |
| `DictionaryVersion` | varchar(32), null | null until the dictionary exists |
| `ExtractorVersion` | varchar(32) | |
| `ExtractedAt` | datetimeoffset | |

## LabResult

One result of one version, as extracted. Written in the same transaction that sets the version to `PendingReview`.

| Column | Type | Notes |
|---|---|---|
| `Id` | uniqueidentifier | PK |
| `VersionId` | uniqueidentifier | FK to `Version` |
| `UserId` | uniqueidentifier | |
| `Ordinal` | int | the order in the `text` blob; unique with `VersionId` |
| `PrintedName` | nvarchar(200) | the name as printed: "Tyreotropina (TSH) III generacji" |
| `ParameterCode` | varchar(64), null | the parameter this result measures (TSH, WBC), from the dictionary ([ADR-0011](adr/0011-lab-parameters-units-and-ranges.md)); set when the user confirms it on review, null before. Trends group by it, or by the printed name until it is mapped (ADR-0011) |
| `Value` | nvarchar(100) | as printed: "18", "<1,0", "nie wykryto" |
| `Unit` | nvarchar(50), null | as printed, without a footnote marker |
| `RangeText` | nvarchar(400), null | as printed |
| `RangeLow` | nvarchar(50), null | as printed |
| `RangeHigh` | nvarchar(50), null | as printed |
| `RangeKind` | varchar(8) | `interval`, `lt`, `gt`, `text`, `none` |
| `LabFlag` | char(1), null | `H` or `L`, mapped by code from `LabFlagPrinted` |
| `LabFlagPrinted` | nvarchar(10), null | the laboratory's marker as printed: "H", "↑", "*" |
| `Icd9` | varchar(10), null | |
| `Material` | nvarchar(100), null | |
| `Condition` | nvarchar(100), null | as printed: "na czczo", "po 2 h" |
| `Method` | nvarchar(400), null | |
| `Analyser` | nvarchar(200), null | |
| `SuggestedParameter` | varchar(64), null | the model's proposal for `ParameterCode`; empty until the dictionary exists |
| `CollectedAt` | datetimeoffset, null | the date the trend uses, `collectedAt` from the `text` blob (the rule is in [the design](../openspec/changes/add-extraction/design.md)); required before approval, corrected on review |
| `CollectedHasTime` | bit | false: a date without a printed time, stored at midnight |
| `Dates` | nvarchar(max) | JSON: the result's own labelled dates from the `text` blob |
| `PageSha256` | binary(32) | |
| `Source` | nvarchar(max) | JSON: the word ids and boxes of the name, value, unit and range, for highlighting |

Trend queries join `Version` and read only `Status = 'Approved'` (G4). Indexes: (`UserId`, `ParameterCode`, `CollectedAt`) for mapped results, and (`UserId`, `PrintedName`, `CollectedAt`) filtered `WHERE ParameterCode IS NULL` for results not mapped yet, which trend by printed name ([ADR-0011](adr/0011-lab-parameters-units-and-ranges.md)). Dates other than `CollectedAt` are JSON, not tables: their number and labels differ between laboratories, nothing queries them, and they are shown as printed.

The review removes rejected rows and applies corrections at approval (U3). Numbers, normalised values and computed flags are added by the changes for review and normalisation ([ADR-0011](adr/0011-lab-parameters-units-and-ranges.md)). They are derived, so they can be recomputed.

## Life of the rows

- **Create:** the upload inserts `Document` (or finds it) and `Version`. `Extracted` inserts the `Extraction` and `LabResult` rows, stores the document dates on the version and sets `PendingReview`, in one transaction, after the API has read the `text` blob.
- **Retry:** `Extracted` delivered twice: the second update changes zero rows, the transaction rolls back, the message is completed.
- **Change:** only the review changes results; only forward-only updates change statuses.
- **Delete:** deleting a document deletes its versions, extractions and results by cascade, then its blobs ([ADR-0012](adr/0012-deletion-and-retention.md)). A new version deletes the document's `Failed` versions, then their blobs ([ADR-0016](adr/0016-retry-replaces-a-failed-version.md)); nothing cascades from that, because `Extraction` and `LabResult` rows are written only with `PendingReview`.
