# 10. Sign-in, users and consent

Date: 2026-11-22

## Status

Accepted

## Context

Baseline serves a family of up to 10 people. Each person's results are health data. Nobody should have to create a new password, every person must see only their own data (G3), and processing other people's health data needs their explicit consent (GDPR Art. 9).

The UI is a single-page application in TypeScript and React ([ADR-0002](0002-languages-dotnet-python-and-typescript.md)). The API is the only component that reads the database.

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

1. **Entra External ID** with two sign-in options: a Google account, or an e-mail address with a one-time code for a person without one. Personal Microsoft accounts are not offered; their support in external tenants is unclear in the documentation.
   - **Accounts by invitation only.** Self-service sign-up is disabled in the user flow (`isSignUpAllowed: false`, set through Microsoft Graph). The owner invites each family member by hand in the admin center, without the Microsoft invitation e-mail, and sends them a link with `domain_hint=google`. The first sign-in redeems the invitation and links the Google account.
   - A person who is not invited cannot create an account; Entra answers before the API is reached. It is free up to 50,000 monthly active users.
2. **The API is the backend for frontend.** It serves the UI from the same domain, runs the sign-in and sets an HTTP-only, secure session cookie with `SameSite=Lax`. Tokens never reach the browser.
   - `Lax` sends the cookie when the user arrives by a link or by the redirect back from Entra, and never with requests that other sites make in the background. `Strict` would drop the cookie on the way back from the sign-in.
   - The session lasts 8 hours and is extended by every request.
   - **The cookie keys (ASP.NET Data Protection) are kept in Blob Storage, wrapped by a key in Key Vault.** Every start after sleep is a new container; with keys only in memory, every start would sign everyone out.
3. **The API authenticates to Entra with a certificate kept in Key Vault**, read with the API's managed identity. A managed identity cannot be the credential itself, because the app registration lives in the External ID tenant and the managed identity in the subscription's tenant, and that federation requires one tenant.
4. **A `User` row** is created together with the consent, keyed by the `oid` claim (the person's object id in the External ID tenant). A person who declines leaves nothing stored. Every other table has `userId`.
5. **No e-mail address in our database.** Google passes the e-mail to Entra, and Entra keeps it in the user object in the External ID tenant. The API does not request the e-mail claim and stores only `oid`. A name shown in the UI comes from the session and is not stored.
6. **Isolation is enforced twice:** every query filters by the signed-in user, and Row-Level Security in Azure SQL filters by the user id set on the connection. A test in CI proves that one user cannot read another's documents, results, pages or fragments.
   - **Background work** in the API also runs as a user: the status consumer sets the user id from the message before it touches the database.
   - **The sweeper is the only code that works across users.** It uses a separate database role that may only run a few stored procedures: find versions stuck in `Uploaded`, count a resend or set `Failed (timeout)`, read deletion markers and finish them (delete the rows of a deleted document or account, then the marker), and check whether a version exists. The role cannot read results, fragments or consent. A test in CI proves both limits.
7. **Blob paths start with `userId`** ([ADR-0006](0006-document-lifecycle-and-review.md)). The API checks ownership in SQL before it reads a blob.
8. **Consent:** at first sign-in the person reads what is stored and processed and ticks a checkbox. The consent is stored with its date and the version of the text. Nothing can be imported without it.
9. **Withdrawing consent deletes the account** and all its data ([ADR-0012](0012-deletion-and-retention.md)). The UI says so before the person confirms.
   - **A new version of the consent text** is shown at the next sign-in. The UI says that without consent the account and all its data must be deleted. Declining it, after a confirmation, deletes the account as above.
10. **The owner removes Entra accounts by hand.** When an account is deleted or consent is declined, the API logs an event with the `oid` only, and an alert e-mails the owner, who deletes the user in the admin center and then permanently from "Deleted users". The API has no Microsoft Graph permission.
11. **Entra logs are not exported.** Sign-in logs in the free tier are kept for 7 days and then disappear.
12. **No sharing.** A family member who wants to see someone else's results asks them. Sharing can be added later with its own decision.

## Consequences

- Nobody creates or remembers a password for Baseline.
- The browser never holds an access token, so a script injected into the page cannot steal one.
- The UI is served by the API, so it also waits for the API's cold start ([ADR-0004](0004-serverless-hosting-and-operations.md)). Security of one origin was preferred to a faster first paint.
- Key Vault holds one certificate, which needs renewal before it expires; an expiry alert is required.
- The only personal data outside our database is the e-mail in the External ID tenant and the 7-day sign-in logs. The consent text names both.
- The API holds no permission in Entra. Creating and removing accounts are manual steps for the owner; if the owner forgets, a removed person's e-mail stays in Entra (a soft-deleted user is purged by Entra after 30 days).
- Until the owner removes the account, a person whose data was deleted can still sign in. They see the consent screen again, and a new, empty account is made only if they consent.
- Two layers of user filtering cost a little complexity and protect against the most damaging bug: showing one person's results to another.
