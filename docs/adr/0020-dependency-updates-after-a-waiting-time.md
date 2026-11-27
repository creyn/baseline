# 20. Dependency updates: proposed after a waiting time, majors one by one, never merged automatically

Date: 2026-11-27

## Status

Accepted. Refines point 6 of [ADR-0013](0013-application-security-baseline.md) ("Dependencies are watched: Dependabot for all three toolchains"). The rest of ADR-0013 stands.

## Context

ADR-0013 point 6 turned Dependabot on, but did not say how. The first configuration (2026-11-27) checked every week and put every pip update into one pull request. Its first run opened two pull requests within minutes:
- one with 13 updates at once, among them major versions (openai 1 to 3, Pillow 11 to 13, reportlab 4 to 5, pypdfium2 4 to 5). The new pypdfium2 removed an attribute the synthetic document generator reads, so CI failed;
- one that moved the extractor's image from Python 3.12 to 3.15. The image did not build: Pillow and pydantic-core had no wheels for 3.15 yet.

Both were closed without merging. A version released yesterday may carry its own bugs, and a major version may change behaviour without a failing test. We want to know about new versions, but take them only after they have settled, and only after a review.

Facts checked in the [Dependabot options reference](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference) on 2026-11-27:
- `cooldown` delays version updates by a number of days after a release. The default is 3 days.
- pip supports separate days for patch, minor and major versions. Docker and GitHub Actions support only `default-days`.
- `cooldown` and the `update-types` of `allow` apply to version updates only, not to security updates.
- A group can be limited to `update-types` (`patch`, `minor`, `major`).
- Whether `ignore` also holds back security updates is not stated there: to check.

### Considered options

1. **No Dependabot.** No noise, but known vulnerabilities in our pins go unnoticed. Breaks ADR-0013 point 6.
2. **Security updates only.** Vulnerabilities are fixed, but the pins age until a forced jump over several major versions.
3. **Version updates after a waiting time, grouped by size, security updates at once.** We hear of new versions every month, after they have settled; majors come one at a time, with a review of their changes.
4. **Every version at once, every week** (the first configuration). The newest code, the most review work, and the highest chance of taking a fresh bug.

Checked against [docs/decision-criteria.md](../decision-criteria.md): no option touches the gates except option 1, which leaves vulnerable code in the image that handles masked health data. Options 3 and 4 cost the same; option 3 asks for less review and takes fewer fresh bugs.

## Decision

We choose option 3.

1. **Monthly checks** for every ecosystem (pip, Docker, GitHub Actions; NuGet and npm join when the .NET API and the UI arrive).
2. **Waiting time after a release** (starting values):
   - pip: 7 days for a patch, 14 for a minor version, 30 for a major version;
   - Docker and GitHub Actions: 14 days (only one value is supported).
3. **Minor and patch updates in one pull request per ecosystem.** Each major version comes in its own pull request. Its release notes are read and the code is fixed in the same pull request before it is merged.
4. **The Python version is held at 3.12** in the extractor's image. A new Python version is its own decision, when the libraries we use publish wheels for it.
5. **Security updates come at once**, without a waiting time.
6. **Nothing is merged automatically.** A Dependabot pull request is a proposal like any other: CI, a review, and a merge by the owner. No workflow approves or merges it.

## Consequences

- A new version reaches us at the earliest after its waiting time, and at the latest about a month later.
- Fewer pull requests: about one per ecosystem a month, plus one per major version.
- A Dependabot pull request that touches the extractor also runs the live evals (about 0.61 USD a run), which is what a dependency change of the extractor should do.
- A fix that arrives as a normal release, not as a security advisory, waits like any other version.
- The waiting times are guesses. If a bug we hit was already fixed in a version we were still waiting for, we shorten them.
