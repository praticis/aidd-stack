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

# Every `docker compose run` is a fresh container, so
# without this step each run would download again — and fail (empty snapshots / rc=4). 
# Bake the grammars into the image and forbid downloads at runtime.
ENV TREE_SITTER_LANGUAGE_PACK_CACHE_DIR=/opt/tslp-cache \
    AIDD_GRAMMAR_OFFLINE=1
RUN python -c "import tree_sitter_language_pack as t; t.prefetch(['go','typescript','tsx','javascript','python','csharp']); print('grammars:', t.downloaded_languages())" \
 && rm -rf /opt/tslp-cache/tree-sitter-language-pack/*/bundles \
 && aidd selftest

# Repositories are mounted read-only at /workspace (see docker-compose.yml).
ENV WORKSPACE_PATH=/workspace
ENTRYPOINT ["aidd"]
CMD ["--help"]
