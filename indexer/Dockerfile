FROM python:3.12-slim

# git: read HEAD / ref / tracked files of the mounted repositories.
RUN apt-get update && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY aidd_indexer ./aidd_indexer
RUN pip install .

# Repositories are mounted read-only at /workspace (see docker-compose.yml).
ENV WORKSPACE_PATH=/workspace
ENTRYPOINT ["aidd"]
CMD ["--help"]
