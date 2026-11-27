# Tasks

## 1. Decision and infrastructure

- [x] 1.1 ADR-0019: Bicep through az, all resources in one group, a smoke test on a test user
- [x] 1.2 `infra/main.bicep`: storage, Service Bus, AI services, monitoring, identities and roles, Container Apps
- [x] 1.3 CI: compile and lint the Bicep

## 2. Image and deployment

- [x] 2.1 Dockerfile of the extractor; CI builds it and starts it
- [x] 2.2 `deploy.yml`: image, Bicep, smoke test
- [x] 2.3 Smoke test with offline tests of its parts

## 3. After merge

- [x] 3.1 The owner decides ADR-0019 (accepted 2026-11-26)
- [x] 3.2 The owner creates the production group, the deploying identity and the `production` environment (2026-11-26; the resource providers registered once on the subscription)
- [x] 3.3 The first deployment; the image package made public; the smoke test passes (2026-11-26)
- [x] 3.4 The evals moved to the new services; `rg-baseline-evals` deleted; resource locks added by hand (2026-11-27; live evals on the new services: values and units 100%, names 97.6%, ranges and flags 100%, 125 of 126 read)
- [x] 3.5 Archive the change
