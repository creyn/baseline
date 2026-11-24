# Data model

The tables in Azure SQL, written by the API only ([ADR-0002](adr/0002-languages-dotnet-python-and-typescript.md)). This is the first version: it covers the import path, from the upload to results waiting for review. Each later change adds its tables here (users and consent, fragments, aliases, normalised values, review corrections).

The decisions behind it: identifiers and statuses in [ADR-0006](adr/0006-document-lifecycle-and-review.md), results in [ADR-0007](adr/0007-extraction-with-document-intelligence-and-an-llm.md) and [ADR-0011](adr/0011-lab-parameters-units-and-ranges.md), isolation in [ADR-0010](adr/0010-identity-users-and-consent.md), deletion in [ADR-0012](adr/0012-deletion-and-retention.md). What extraction writes is in the `text` contract ([contracts/](../contracts/README.md)).

## Rules for every table

- **Every table has `UserId`** (`uniqueidentifier`, the `oid` of the signed-in person) and a Row-Level Security policy on it. Background work sets the user from the message before it touches a table.
- **Keys are UUIDv7** made by the API (`uniqueidentifier`).
- **Times written by the system** are `datetimeoffset` in UTC. Dates read from a document keep the offset of their zone.
- **Hashes** are `binary(32)` (SHA-256).
- **Deletion cascades** from `Document` to everything below it.
- **Text as printed** is `nvarchar`, because results are in Polish. Its lengths are the `maxLength` values in [contracts/text.schema.json](../contracts/text.schema.json), so a valid blob always fits; a longer text fails extraction with `extract_invalid`.

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
| `ReprocessOf` | uniqueidentifier, null | the version whose checked ZIP was copied (U9) |
| `Status` | varchar(16) | `Uploaded`, `Blocked`, `PendingReview`, `Approved`, `Archived`, `Superseded`, `Failed` |
| `FailReason` | varchar(16), null | `integrity`, `check_error`, `extract_invalid`, `extract_error`, `no_results`, `timeout`; kept after `Superseded` |
| `StatusChangedAt` | datetimeoffset | the sweeper reads it |
| `ResendCount` | tinyint | how many times the sweeper sent the first message again (at most 3) |
| `BlockedRegions` | nvarchar(max), null | JSON: page and rectangle, never text (`Blocked`) |
| `CreatedAt` | datetimeoffset | |
| `RowVersion` | rowversion | optimistic concurrency on review |

Indexes:
- (`DocumentId`, `ZipSha256`), unique, filtered `WHERE ZipSha256 IS NOT NULL`, as [ADR-0006](adr/0006-document-lifecycle-and-review.md) sets it. A retry of the same upload returns the version made by the first try. A reprocessed copy has no hash, so it never collides with the version it was copied from. **Open question:** the same ZIP sent again after a failure returns the failed version; see [docs/sequences](sequences/README.md#open-questions). A change of this index needs a new ADR.
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
| `PrintedName` | nvarchar(200) | |
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
| `SuggestedParameter` | varchar(64), null | a code from the dictionary; empty until it exists |
| `PageSha256` | binary(32) | |
| `Source` | nvarchar(max) | JSON: the word ids and boxes of the name, value, unit and range, for highlighting |

The review removes rejected rows and applies corrections at approval (U3). Numbers, normalised values and computed flags are added by the changes for review and normalisation ([ADR-0011](adr/0011-lab-parameters-units-and-ranges.md)). They are derived, so they can be recomputed.

## DocumentDate and LabResultDate

Dates read from a document. `DocumentDate` holds the dates of the whole document (registration, collection) and has `VersionId`, a cascading FK to `Version`. `LabResultDate` holds the dates of one result and has `ResultId`, a cascading FK to `LabResult`. Two tables, because one table with both keys would have two cascade paths from `Version`, which SQL Server refuses. Both have these columns too:

| Column | Type | Notes |
|---|---|---|
| `Id` | uniqueidentifier | PK |
| `UserId` | uniqueidentifier | |
| `Label` | nvarchar(100) | as printed: "Data/godz. pobrania" |
| `Text` | nvarchar(100) | the date as printed |
| `At` | datetimeoffset | with the offset of its zone on that day |
| `TimeZone` | varchar(64) | `Europe/Warsaw` by default |
| `HasTime` | bit | false: the time is midnight and was not printed |

## Life of the rows

- **Create:** the upload inserts `Document` (or finds it) and `Version`. `Extracted` inserts the `Extraction`, `LabResult`, `LabResultDate` and `DocumentDate` rows and sets `PendingReview`, in one transaction, after the API has read the `text` blob.
- **Retry:** `Extracted` delivered twice: the second update changes zero rows, the transaction rolls back, the message is completed.
- **Change:** only the review changes results; only forward-only updates change statuses.
- **Delete:** deleting a document deletes its versions, extraction, results and dates by cascade (one path to each table), then its blobs ([ADR-0012](adr/0012-deletion-and-retention.md)).
