# 13. Application security baseline

Date: 2026-11-23

## Status

Accepted. Point 6 is refined by [ADR-0020](0020-dependency-updates-after-a-waiting-time.md): new versions are proposed monthly, after a waiting time, majors one by one, and never merged automatically.

## Context

The API serves the UI and keeps the session in a cookie ([ADR-0010](0010-identity-users-and-consent.md)). It accepts uploads of page images, sends text to paid AI services and holds health data. The other ADRs decide where data goes. This one decides the controls every endpoint needs, so that each developer does not choose their own.

Threats that the other decisions do not cover:
- **Cross-site request forgery.** Another site makes the browser send a request with our cookie, for example `DELETE /me`. `SameSite=Lax` stops most of these, but not every case.
- **Script injection into the UI.** A script running on our domain could read health data shown on the page.
- **Oversized input.** A small PNG can declare huge dimensions and use gigabytes of memory when decoded. "No page limit" must not mean no limit at all.
- **Runaway cost.** A bug that reprocesses in a loop, or a script that asks the agent questions without end, spends money on Document Intelligence and Azure OpenAI.

### Considered options

1. **Framework defaults only.** ASP.NET has antiforgery and rate limiting, but they are off until configured, and nothing limits image size or daily use.
2. **An explicit baseline for all endpoints**, written here, configured once in the API and tested in CI.

Option 1 leaves each control to each developer. Option 2 costs a little configuration once.

## Decision

We choose option 2.

1. **Antiforgery on every state-changing request.** `POST`, `PUT` and `DELETE` need the ASP.NET antiforgery token, which the UI sends in a header. `SameSite=Lax` stays as a second layer.
2. **Security headers on every response:**
   - Content Security Policy: `default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self' blob:; img-src 'self' blob: data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'`. Tesseract.js needs WebAssembly, hence `wasm-unsafe-eval`. No inline scripts and no third-party origins ([ADR-0002](0002-languages-dotnet-python-and-typescript.md)).
   - `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`.
   - Responses with health data have `Cache-Control: no-store`.
3. **Input limits** (starting values, changed by configuration):
   - one upload at most 50 MB;
   - at most 200 pages in one version (a technical limit; real results have a few pages);
   - each PNG at most 25 megapixels, read from the PNG header before decoding, in the API and again in the checker;
   - a question at most 2,000 characters, a history at most 20 messages.
4. **Daily limits per user**, counted in SQL so that they survive a restart (starting values):
   - 10 imports or reprocessings,
   - 50 questions to the agent,
   - 10 pre-visit summaries.

   Above a limit the API answers 429 with a plain explanation. The counters are deleted with the account ([ADR-0012](0012-deletion-and-retention.md)).
5. **A monthly budget alert** on the subscription ([ADR-0004](0004-serverless-hosting-and-operations.md)).
6. **Dependencies are watched:** Dependabot for all three toolchains and CodeQL in CI ([ADR-0014](0014-development-with-ai-agents.md)).
7. **A CI test checks the baseline:** a state-changing request without the token gets 400, every response has the headers, and oversized input is rejected before it is decoded.

## Consequences

- A forged request from another site cannot delete data or start paid work.
- An injected script cannot load code from another origin or send data to one.
- One bad upload cannot exhaust the memory of the API or the checker.
- The worst case of a runaway bug is bounded: 10 users × 10 imports a day is about 1 USD a day for extraction.
- The limits are guesses. They are logged when hit, and changed in configuration if a real user hits them.
- The counters are one more small table to delete with an account.
