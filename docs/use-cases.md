# Use cases, workload and cost

The decisions in [docs/adr](adr/README.md) are made for this workload. Frequencies are assumptions for a family of up to 10 people, to be corrected with real use. Prices are list prices from the Azure Retail Prices API for Sweden Central, read on 2026-11-22.

## Users

The owner and their family, up to 10 people. Each person signs in and sees only their own results. Sharing results between people is not supported ([ADR-0013](adr/0013-identity-users-and-consent.md)).

## Use cases

| # | Use case | Frequency per person | Who waits | Target (p95) | AI on the path |
|---|---|---|---|---|---|
| U1 | Sign in, give or withdraw consent | once, then a session | a person | < 2 s | no |
| U2 | Import a lab result: mask in the browser, upload, check, extract | 2 results a month, 3 pages on average; about 30 old results once at the start | a person while masking, then nobody | masking: measured 6–28 s per page; 202 < 3 s; `PendingReview` < 3 min | DI, LLM |
| U3 | Review and approve the extracted values | once per import | a person | screen opens < 2 s | no |
| U4 | Fix a blocked document and send it again | about 1 in 10 imports | a person | as U2 | no |
| U5 | **Browse results and trends** | **12 sessions a month, about 10 reads each** | a person | **< 1 s when warm** | no |
| U6 | **Ask the agent a question** | **10 questions a month** | a person | first words < 3 s, full answer < 15 s when warm | LLM, tools |
| U7 | Pre-visit summary | once a month | a person | < 30 s | LLM |
| U8 | Delete a document | about once a quarter | nobody, after confirmation | confirmation < 2 s, done < 5 min | no |
| U9 | Reprocess a document after a fix | rarely | nobody | as U2 | DI, LLM |
| U10 | Delete the account (also after withdrawing consent) | once | nobody | done < 1 h | no |
| U11 | Export my data | rarely | a person | < 10 s | no |

**What this means for the architecture:**
1. **Reads dominate.** One import comes with about 60 reads of results and trends and 5 questions to the agent. The most frequent path needs no AI, only SQL with good indexes.
2. **Results are structured data in SQL.** The agent's tools are SQL queries. Vector search is needed only for descriptive text, which is a small share of questions ([ADR-0011](adr/0011-retrieval-without-ai-search.md)).
3. **Import is rare and asynchronous.** Its cost depends on the number of pages, not on how the queues are arranged.
4. **The system is idle most of the day.** Services that scale to zero cost almost nothing, but the first read after idle time waits for a cold start ([ADR-0006](adr/0006-serverless-hosting-on-azure.md)).

Every use case that changes state is drawn as a sequence diagram, with arguments on the arrows, alternative paths and the state after a failure. Import, review, U5 and U6 are drawn in [docs/adr/0007](adr/0007/c-pipeline-without-outbox.svg).

## Cost

### Per use

| Item | Price (USD) | Per unit |
|---|---|---|
| Document Intelligence, layout (S0) | 10 per 1,000 pages | 0.01 per page |
| gpt-5.4 mini, Data Zone | 0.825 per 1M input tokens, 4.95 per 1M output tokens | extraction about 0.021, a question about 0.017, a summary about 0.016 |
| text-embedding-3-small, Data Zone | 0.022 per 1M tokens | negligible |

Assumptions: extraction uses 8k input and 3k output tokens per result, a question 15k and 1k (a few rounds with tools), a summary 10k and 1.5k.

| | 1 person | 10 people |
|---|---|---|
| Per month | about 0.29 USD | about 2.92 USD |
| Once, importing 30 old results per person | about 1.54 USD | about 15.44 USD |

### Fixed

| Service | Option | USD per month | Note |
|---|---|---|---|
| Azure AI Search | Basic | 73.73 | Not used ([ADR-0011](adr/0011-retrieval-without-ai-search.md)). |
| Azure SQL Database | serverless, free offer | 0 | 100,000 vCore seconds and 32 GB per database per month; auto-pause. |
| Container Apps | Consumption, scale to zero | about 0 | Free grant per subscription: 180,000 vCPU seconds, 360,000 GiB seconds, 2M requests. |
| Container images | GitHub Container Registry | 0 | Instead of Azure Container Registry Basic (5.07). |
| Service Bus | Basic | about 0 | 0.05 per 1M operations. |
| Blob Storage | Hot LRS | about 0 | Under 1 GB. |
| Key Vault | Standard | about 0 | One certificate, a few operations. |
| Log Analytics | | 0 | The first 5 GB per month are free. |
| Entra External ID | | 0 | Free up to 50,000 monthly active users. |

**Total for 10 people:** about 3 USD a month, plus about 15 USD once for the old results. With Azure AI Search Basic it would be about 77 USD a month, so that one service would be about 96% of the bill.
