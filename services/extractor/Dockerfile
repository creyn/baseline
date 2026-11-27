# The extractor's image (ADR-0019). Built from the repository root, because it needs contracts/:
#   docker build -f services/extractor/Dockerfile .
FROM python:3.15-slim

# Links the GitHub package to the repository, so the workflow's token can push new versions.
LABEL org.opencontainers.image.source=https://github.com/creyn/baseline

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CONTRACTS_DIR=/app/contracts
WORKDIR /app/services/extractor

COPY services/extractor/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY contracts/*.json contracts/text_checks.py /app/contracts/
COPY services/extractor/extractor ./extractor

# No root at run time.
RUN useradd --uid 10001 --no-create-home extractor
USER 10001

CMD ["python", "-m", "extractor.main"]
