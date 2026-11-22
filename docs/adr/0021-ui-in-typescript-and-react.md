# 21. UI in TypeScript and React

Date: 2026-11-22

## Status

Proposed

## Context

The UI does real work, not only display: it renders PDFs, runs OCR, masks pages and checks them before anything is sent ([ADR-0003](0003-mask-in-the-browser-check-again-on-the-server.md)). The [browser sanitiser spike](../../spikes/browser-sanitiser/README.md) does this in JavaScript with PDF.js and Tesseract.js, including the masking rules and their tests.

The UI also shows trends as charts, the review screen with highlighted values, and a streamed chat. It is served by the API from the same domain ([ADR-0013](0013-identity-users-and-consent.md)).

### Considered options

1. **TypeScript and React.** PDF.js and Tesseract.js are JavaScript libraries, so the spike's code moves over directly. Large ecosystem for charts and drag and drop.
2. **Blazor WebAssembly.** One language with the API, but PDF.js and Tesseract.js would be called through JavaScript interop, the masking rules would be rewritten or wrapped, and the download is larger.
3. **Server-rendered pages (Razor) with a little JavaScript.** Little client code, but masking must run in the browser anyway, so the heavy JavaScript stays.

| Criterion (weight) | 1: TypeScript, React | 2: Blazor | 3: Razor + JS |
|---|---|---|---|
| K1 simple, self-healing (40) | 5 | 3 | 3 |
| K2 cost (20) | 5 | 5 | 5 |
| K4 engineering practice (15) | 3 | 4 | 3 |
| K5 testable in CI (10) | 4 | 4 | 3 |
| K6 time to deliver (10) | 5 | 4 | 4 |
| K7 performance (5) | 4 | 3 | 3 |
| **Result** | **91** | **75** | **66** |

## Decision

We choose option 1.

1. **TypeScript, React, built with Vite.** The build output is served by the API as static files.
2. **Masking runs in a Web Worker** with PDF.js and Tesseract.js, so the page stays responsive. The masking rules are a separate TypeScript module with their own tests, shared in spirit with the Python checker: both are tested against the same synthetic documents.
3. **No tokens in the browser.** The UI calls the API with the session cookie only.
4. **The masking libraries and the OCR language data are served from our own domain**, not from a CDN, so masking works offline once loaded and no third party sees the page.

## Consequences

- The spike's rules and tests move over with little change.
- There are two implementations of the masking rules: TypeScript in the browser and Python in the checker. Synthetic documents in CI keep them in step.
- The UI waits for the API's cold start, because the API serves it ([ADR-0006](0006-serverless-hosting-on-azure.md)).
