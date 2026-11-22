# Decision criteria

Every option in an ADR passes two checks. First the gates: an option that fails one is rejected. Then the weighted criteria: each option gets a score from 1 to 5 per criterion, and its result is the sum of weight × score / 5, on a scale of 0 to 100.

The workload behind these criteria is described in [use-cases.md](use-cases.md).

## Gates

| # | Gate |
|---|---|
| G1 | No unmasked personal data reaches a managed AI service. |
| G2 | Data and AI processing stay in the EU (EU region, Data Zone EU). |
| G3 | Every user sees only their own data, and a test proves it. |
| G4 | Model output is saved at once, as `PendingReview`, so it is not lost. Only the user sets `Approved`. Trends, the agent and summaries read only approved results. Out-of-range flags are computed by code, and every answer cites its source. |
| G5 | Deleting a document or an account reaches every store, and a test proves it. |
| G6 | No keys or passwords in code or configuration (Managed Identity, Entra ID). |

## Weighted criteria

| # | Criterion | Weight | 5 means | 1 means |
|---|---|---|---|---|
| K1 | **Simple, reliable, self-healing** | 40 | Few moving parts. A failure anywhere loses no work and leaves no stuck status; the system recovers by itself. One person understands all of it. | Many services and processes. Failures need manual clean-up; state can be lost. |
| K2 | **Monthly cost**, mostly fixed cost | 20 | About 0 USD when nobody uses it. | A fixed charge of tens of USD, used or not. |
| K4 | **Current engineering practice** | 15 | Uses well-supported, current patterns for AI systems (an agent with tools and guardrails, evals, specs before code, a reason for each language) and keeps them documented. | Ad hoc code with no tests for the AI parts and no recorded reasons. |
| K5 | **Testable in CI** | 10 | Unit and integration tests run automatically in the pipeline without deploying to Azure (emulators in containers). Evals run in CI. | Tests need an Azure environment or manual steps. |
| K6 | **Time to deliver** | 10 | Little code and configuration before the first working import. | A lot of infrastructure before anything works. |
| K7 | **Performance when warm** | 5 | Browsing results under 1 s, an agent answer under 15 s. | Slower than the targets in [use-cases.md](use-cases.md). |

K3 (reliability) was merged into K1; the number is not reused.

**Why these weights:**
- **K1 is the highest** because one person maintains the system in their spare time. Simplicity and self-healing are one goal.
- **K2 is high** because the system is idle most of the day. A fixed charge is paid for nothing.
- **K7 is the lowest** because a long cold start after idle time is accepted ([ADR-0006](adr/0006-serverless-hosting-on-azure.md)).
