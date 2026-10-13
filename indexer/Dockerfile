# Base image pinned to the patch release — bump deliberately (python deps: pyproject.toml).
# Stages: `base` (indexer + atlas MCP), `knowledge` (adds the embedding stack for mcp-knowledge) and
# `indexer` — the default (last) stage, what the refresher and mcp-atlas run: no embedding model in it.
FROM python:3.12.15-slim AS base

# git: read refs / archive trees of the mounted repositories.
# openssh-client + ca-certificates: `git fetch` over ssh:// and https://
# (without ssh, git fails with "fatal: unable to fork").
RUN apt-get update && apt-get install -y --no-install-recommends git openssh-client ca-certificates \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# The containers run as the host user (docker-compose.yml `user:`), which may not own the mounted
# repos as the image sees them: trust every repository for git, for every git process in the
# container (system config — also read by `git fetch <local path>`'s upload-pack).
RUN git config --system --add safe.directory '*'

WORKDIR /app
COPY pyproject.toml README.md ./
COPY aidd_indexer ./aidd_indexer
COPY git-askpass.sh /app/git-askpass.sh
RUN pip install . && chmod +x /app/git-askpass.sh

# Convention extensions (ADR-003): every package under conventions/ registers itself in the
# `aidd.conventions` entry point; atlas.yaml enables one per tenant by id. The build fails if one
# does not install or does not load.
COPY conventions ./conventions
RUN set -e; for d in conventions/*/; do if [ -f "${d}pyproject.toml" ]; then pip install --no-deps "$d"; fi; done \
 && python -c "from importlib.metadata import entry_points; from aidd_indexer.conventions import load_one; ids = sorted(e.name for e in entry_points(group='aidd.conventions')); [load_one({'id': i}) for i in ids]; print('conventions:', ids)"

# tree-sitter-language-pack ships no grammars: it downloads a prebuilt .so per language from
# GitHub Releases on first `get_language()`. Every `docker compose run` is a fresh container, so
# without this step each run would download again — and fail (empty snapshots / rc=4) whenever
# GitHub is slow or unreachable. Bake the grammars into the image and forbid downloads at runtime.
ENV TREE_SITTER_LANGUAGE_PACK_CACHE_DIR=/opt/tslp-cache \
    AIDD_GRAMMAR_OFFLINE=1
# The grammar list comes from the language registry (aidd_indexer/languages) — a new language
# module is prefetched automatically.
RUN python -c "import tree_sitter_language_pack as t, aidd_indexer.languages as L; g = sorted(L.grammars()); t.prefetch(g); print('grammars:', g, '->', t.downloaded_languages())" \
 && rm -rf /opt/tslp-cache/tree-sitter-language-pack/*/bundles \
 && chmod -R a+rX /opt/tslp-cache \
 && aidd selftest \
 && setpriv --reuid=65534 --regid=65534 --clear-groups aidd selftest >/dev/null
# ^ compose runs these containers as the host user (any uid): the grammars must load for it too

# Repositories are mounted read-only at /workspace; git reads and fetches go to the mirrors under
# /var/lib/aidd/mirrors (core/mirror.py, docker-compose.yml).
ENV WORKSPACE_PATH=/workspace
ENTRYPOINT ["aidd"]
CMD ["--help"]

# ── knowledge service (mcp-knowledge) ─────────────────────────────────────────────────────────────
# FastEmbed + the embedding model mcp-qdrant uses, baked in (like the grammars): the service embeds
# insights for the same Qdrant collections the skills search with `qdrant-find`. No download at
# runtime, and the model must load for any uid (compose runs it as the host user).
FROM base AS knowledge
ENV FASTEMBED_CACHE_PATH=/opt/fastembed-cache \
    EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
RUN pip install "/app[knowledge]" \
 && python -c "from aidd_indexer.knowledge.vectors import FastEmbedder; e = FastEmbedder(); print('embedding model:', e.model, e.size)" \
 && chmod -R a+rX /opt/fastembed-cache
ENV HF_HUB_OFFLINE=1
RUN setpriv --reuid=65534 --regid=65534 --clear-groups env HOME=/tmp \
      python -c "from aidd_indexer.knowledge.vectors import FastEmbedder; FastEmbedder()"

# ── default: the indexer (refresher, on-demand runs, mcp-atlas) ───────────────────────────────────
FROM base AS indexer
