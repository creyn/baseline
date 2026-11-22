# 13. Sign-in, users and consent

Date: 2026-11-22

## Status

Proposed

## Context

Baseline serves a family of up to 10 people. Each person's results are health data. Nobody should have to create a new password, every person must see only their own data (G3), and processing other people's health data needs their explicit consent (GDPR Art. 9).

The UI is a single-page application in TypeScript and React ([ADR-0021](0021-ui-in-typescript-and-react.md)). The API is the only component that reads the database.

### Considered options

**Sign-in:**
1. **Microsoft Entra External ID, with the API as a backend for frontend (BFF).** The API serves the UI, runs the OpenID Connect sign-in, keeps the tokens on the server and gives the browser an HTTP-only session cookie. One domain.
2. **Entra External ID with the UI on Static Web Apps,** tokens in the browser. The UI loads fast even when the API is cold, but tokens are exposed to script in the browser, and two origins need CORS.
3. **Our own accounts and passwords.** No external dependency, but we would store password hashes and build reset and multi-factor flows ourselves.

| Criterion (weight) | 1: BFF | 2: tokens in the browser | 3: own accounts |
|---|---|---|---|
| K1 simple, self-healing (40) | 4 | 3 | 2 |
| K2 cost (20) | 5 | 5 | 5 |
| K4 engineering practice (15) | 4 | 4 | 4 |
| K5 testable in CI (10) | 4 | 3 | 3 |
| K6 time to deliver (10) | 4 | 4 | 4 |
| K7 performance (5) | 4 | 4 | 4 |
| **Result** | **84** | **74** | **66** |

**Sharing between people:**
1. **Each person sees only their own data.**
2. **A person can share their results with another** (a parent and a child). Needs a permission model, and every query and test must handle it.

## Decision

Sign-in: option 1. Sharing: option 1.

1. **Entra External ID** with Google and Microsoft accounts. It is free up to 50,000 monthly active users.
2. **The API is the backend for frontend.** It serves the UI from the same domain, runs the sign-in and sets an HTTP-only, secure, same-site session cookie. Tokens never reach the browser.
3. **The API authenticates to Entra with a certificate kept in Key Vault**, read with the API's managed identity. A managed identity cannot be the credential itself, because the app registration lives in the External ID tenant and the managed identity in the subscription's tenant, and that federation requires one tenant.
4. **A `User` row** is created at first sign-in, keyed by the external identity. Every other table has `userId`.
5. **Isolation is enforced twice:** every query filters by the signed-in user, and Row-Level Security in Azure SQL filters by the user id set on the connection. A test in CI proves that one user cannot read another's documents, results, pages or fragments.
6. **Blob paths start with `userId`** ([ADR-0008](0008-document-lifecycle-and-identifiers.md)). The API checks ownership in SQL before it reads a blob.
7. **Consent:** at first sign-in the person reads what is stored and processed and ticks a checkbox. The consent is stored with its date and the version of the text. Nothing can be imported without it.
8. **Withdrawing consent deletes the account** and all its data ([ADR-0019](0019-deletion-and-retention.md)). The UI says so before the person confirms.
9. **No sharing.** A family member who wants to see someone else's results asks them. Sharing can be added later with its own decision.

## Consequences

- Nobody creates or remembers a password for Baseline.
- The browser never holds an access token, so a script injected into the page cannot steal one.
- The UI is served by the API, so it also waits for the API's cold start ([ADR-0006](0006-serverless-hosting-on-azure.md)). Security of one origin was preferred to a faster first paint.
- Key Vault holds one certificate, which needs renewal before it expires; an expiry alert is required.
- Two layers of user filtering cost a little complexity and protect against the most damaging bug: showing one person's results to another.
