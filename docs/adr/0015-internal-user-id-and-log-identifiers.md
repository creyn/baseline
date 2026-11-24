# 15. Our own user id, and the identifiers in every log entry

Date: 2026-11-24

## Status

Accepted. Supersedes point 4 of [ADR-0010](0010-identity-users-and-consent.md) (the `User` row keyed by `oid`) and extends point 10 of [ADR-0006](0006-document-lifecycle-and-review.md) (the identifiers in logs and messages).

## Context

ADR-0010 keys the `User` row by the `oid` claim, the person's object id in the External ID tenant. Read literally, `userId` is the `oid`, and it would then appear in every table, every blob path, every message and every log entry.

The `oid` belongs to Entra, not to us:
- it ties all our data to one identity provider; a move to another provider would rewrite every key and blob path;
- it is the key the owner uses to find the person in Entra, so a log entry with it points straight at a real account, even after our data is deleted.

Logs also need to say whose import failed. ADR-0006 puts only `docId` and `verId` in logs, so support needs a database query to find the person, and daily limits ([ADR-0013](0013-application-security-baseline.md)) cannot be read from the logs.

### Considered options

**The user id:**
1. **The `oid` as `userId`.** Nothing to map, but the drawbacks above.
2. **A hash of the `oid`.** Not the `oid` itself, but derived from it: anyone with the `oid` can compute it, and a new provider still means new keys.
3. **Our own UUIDv7**, made by the API when the `User` row is created, with the `oid` in one column of `User` only.

**Identifiers in logs:**
1. **`docId` and `verId` only** (as ADR-0006).
2. **`userId`, `docId` and `verId`, and the W3C trace context.** The trace id joins one user action across the API, the queues and the workers; Application Insights builds the end-to-end view from it.
3. **The same with the `oid`.** Direct for the owner, but it puts the Entra key into every entry.

All options pass the gates. Option 3 for the id and option 2 for logs are better on G5: after an account is deleted, nothing in the logs leads back to the Entra account.

## Decision

User id: option 3. Logs: option 2.

1. **`userId` is a UUIDv7 made by the API** when the `User` row is created with the consent. `User` has `ExternalId` (the `oid`) with a unique index, and the issuer. Every other table, blob path, message and log entry uses `userId`.
2. **The `oid` appears in three places only:** `User.ExternalId`, the deletion marker, and the `AccountDeleted` and `ConsentDeclined` log events, because the owner needs it to remove the account in Entra ([ADR-0012](0012-deletion-and-retention.md)). The `AccountDeleted` and `ConsentDeclined` events log the `oid` and no `userId`.
3. **The session cookie carries `userId`**, not the `oid`. Sign-in reads `User` by `ExternalId` once, then everything uses `userId`.
4. **Every log entry carries `userId`, `docId` and `verId`** where they apply (except the two events in point 2, which carry the `oid` only), and the W3C trace context. Never content (ADR-0006, point 10, [ADR-0012](0012-deletion-and-retention.md), point 8).
5. **Messages carry the trace context in the `Diagnostic-Id` application property**, in the `traceparent` format, as Service Bus tracing does (checked 2026-11-24 in the Service Bus end-to-end tracing documentation; whether the Python SDK sets it by itself is to check). The Service Bus `CorrelationId` property is not used: it is meant for request and reply, which the pipeline does not have. `docId` and `verId` are also set as application properties, so a message in a dead-letter queue can be read without opening its body.
6. **Logging goes to Application Insights through OpenTelemetry** from .NET and Python. No other log service: it would add a vendor, a key and a store that deletion must reach.

## Consequences

- A change of identity provider changes one column, not the keys of every table and blob.
- Logs answer "what happened to this person's import" without a database query, and one trace shows a user action across all services.
- After an account is deleted, its `userId` in the logs points to nothing, and the logs expire after 30 days.
- Sign-in needs one lookup by `ExternalId`. It is indexed and happens once per session.
- **Known gap, not new here:** between the `AccountDeleted` alert and the owner removing the Entra account, the person can sign in and consent again, which makes a new `User` with the same `ExternalId`. If the owner then removes the Entra account, the new user's data is left without anyone who can sign in. It is an open question in [docs/sequences](../sequences/README.md#open-questions).
- The U1 and U10 diagrams already map the `oid` to `userId` through the `User` row; the session cookie in U1 changes from `oid` to `userId`.
