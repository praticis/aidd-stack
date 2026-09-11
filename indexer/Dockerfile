FROM python:3.12-slim

# git: read refs / archive trees of the mounted repositories.
# openssh-client + ca-certificates: `git fetch` over ssh:// and https://
# (without ssh, git fails with "fatal: unable to fork").
RUN apt-get update && apt-get install -y --no-install-recommends git openssh-client ca-certificates \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY aidd_indexer ./aidd_indexer
COPY git-askpass.sh /app/git-askpass.sh
RUN pip install . && chmod +x /app/git-askpass.sh

# Repositories are mounted read-only at /workspace (see docker-compose.yml).
ENV WORKSPACE_PATH=/workspace
ENTRYPOINT ["aidd"]
CMD ["--help"]
