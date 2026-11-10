# The test image: the indexer image plus pytest, and Node with a pinned TypeScript compiler (the reference TS's type cases and
# the scorecard are checked against). Sourced by test.sh and checks/reference.sh, so that one recipe builds it.
#
#   . "$indexer/scripts/lib/test-image.sh"
#   test_image_ensure [--rebuild]     builds the image when it is missing, or was built from another recipe
#
# It sets `base` (the indexer image), `image` (the test image) and `stamp` (a checksum of the recipe).
base="${AIDD_INDEXER_IMAGE:-aidd-indexer:local}"
image="${AIDD_INDEXER_TEST_IMAGE:-aidd-indexer-test:local}"

recipe="FROM node:24.21.0-trixie-slim AS node
RUN npm install -g --no-fund --no-audit typescript@6.0.3
FROM $base
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/typescript /opt/typescript
RUN pip install pytest==9.1.1
WORKDIR /src
ENV PYTHONPATH=/src AIDD_TYPESCRIPT=/opt/typescript
ENTRYPOINT []"
stamp=$(printf %s "$recipe" | cksum | cut -d' ' -f1)

test_image_ensure() {
  local built
  built=$(docker image inspect -f '{{ index .Config.Labels "aidd.recipe" }}' "$image" 2>/dev/null || true)
  if [ "${1:-}" = "--rebuild" ] || [ "$built" != "$stamp" ]; then
    docker image inspect "$base" >/dev/null 2>&1 \
      || { echo "missing image $base: build the stack's indexer image first (docker compose build at the repo root)" >&2; return 2; }
    printf '%s\nLABEL aidd.recipe=%s\n' "$recipe" "$stamp" | docker build -q -t "$image" - >/dev/null
  fi
}
