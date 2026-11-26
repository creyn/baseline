# 17. Catching changes on the AI services: pinned versions and weekly live evals

Date: 2026-11-24

## Status

Accepted. Extends point 2 of [ADR-0004](0004-serverless-hosting-and-operations.md) (when evals run).

## Context

Live evals run when our code changes: the extractor, its prompt, its contracts or the evals ([ADR-0004](0004-serverless-hosting-and-operations.md)). The AI services can also change without any change on our side:

- **Azure OpenAI** deploys one model version. A deployment's `versionUpgradeOption` decides what happens when Microsoft names a new default version or retires the current one (checked 2026-11-24 in the Azure OpenAI documentation, "Working with models" and "Model retirements"):
  - `OnceNewDefaultVersionAvailable`: upgrades within two weeks after a new default version is named;
  - `OnceCurrentVersionExpired`: upgrades when the current version retires. (Correction 2026-11-26: the first version of this ADR said this is also the behaviour when the option is not set. A deployment created with the Azure CLI got `OnceNewDefaultVersionAvailable`, so the option is always set explicitly. The decision is unchanged.)
  - `NoAutoUpgrade`: never upgrades, and the deployment stops working when the version retires.
  - Notice: at least 60 days before a GA version retires (e-mail to subscription owners and Azure Service Health), and at least two weeks before a new default version.
- **Document Intelligence** `prebuilt-layout` is called with a fixed API version (2024-11-30, through the pinned SDK). Whether the model behind it can still change within that API version is not stated in the documentation (to check).

### Considered options

1. **Evals only when our code changes.** A model upgrade or a service change shows up first as wrong values on review.
2. **Pin versions and rely on Microsoft's notices.** Covers announced upgrades of Azure OpenAI; misses unannounced changes of Document Intelligence, and depends on someone reading the e-mail.
3. **Option 2 plus a weekly scheduled live eval run**, and the model version that answered recorded in every `text` blob and eval report. Catches any change within a week, announced or not, at the cost of one run a week.
4. **A daily run.** Faster detection, seven times the cost, for a service that changes rarely.

All options pass the gates (the evals use fictional documents only). Option 3 is the cheapest one that does not depend on a person noticing an e-mail (K1).

## Decision

We choose option 3.

1. **The Azure OpenAI deployment pins a model version** with `versionUpgradeOption: OnceCurrentVersionExpired`. It does not move to a new default version by itself; at retirement it upgrades instead of stopping. `NoAutoUpgrade` is not used: a stopped deployment would fail every import.
2. **Live evals also run every Monday at 04:00 UTC**, besides pull requests that change the extractor, its contracts or the evals, and runs on demand. A run below the targets of [ADR-0007](0007-extraction-with-document-intelligence-and-an-llm.md) fails the workflow, and GitHub e-mails the owner.
3. **The model version that answered** (the `model` field of the chat completion) is stored in `extraction.model` of every `text` blob and in each eval report, so a change of version is visible next to a change of quality.
4. **Before a retirement**, the owner deploys the new version next to the old one and runs the live evals against it on demand before switching.

## Consequences

- A silent change of a model or of Document Intelligence is found within a week, on fictional documents, before users notice it on review.
- One live run costs about 0.65 USD (starting value: 37 page-forms at 0.01 USD per page, about 5,000 input tokens per page and 200 output tokens per result), so the weekly run adds about 3 USD a month. ADR-0004 estimated about 1 USD for 30 pages, a rougher starting value; the first live run gives the real cost per run, which both ADRs then use. The 10 USD budget alert of ADR-0004 still holds, with less room.
- That the `model` field carries the version (for example a dated name) is to check on the first live run.
