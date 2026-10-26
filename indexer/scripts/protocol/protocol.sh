#!/usr/bin/env bash
# The regression protocol on the working tree (or the worktree at $AIDD_REPO): the corpus and the hold-out against
# their baselines, then the micro graph against main, on the micro set and any more repos given. The outputs go to
# $AIDD_PROTOCOL_RUNS/LABEL (default ~/.cache/aidd-corpus/protocol), outside the repository.
#   protocol.sh LABEL [REPO...]
set -u
label="$1"; shift
here="$(cd "$(dirname "$0")" && pwd)"
out="${AIDD_PROTOCOL_RUNS:-$HOME/.cache/aidd-corpus/protocol}/$label"
mkdir -p "$out"
repo="${AIDD_REPO:-$(cd "$here/../../.." && pwd)}"      # a worktree, to measure a commit
cd "$repo"
indexer/scripts/corpus.sh --label "$label" --baseline "${AIDD_BASELINE:-2026-10-18-v2-baseline-29}" >"$out/corpus.txt" 2>&1
echo "corpus rc=$? $(grep 'repo(s) differ' "$out/corpus.txt" | tail -1) $(date +%T)"
indexer/scripts/corpus.sh --holdout --label "$label-holdout" --baseline "${AIDD_HOLDOUT_BASELINE:-2026-10-18-v2-holdout-26}" >"$out/holdout.txt" 2>&1
echo "holdout rc=$? $(grep 'repo(s) differ' "$out/holdout.txt" | tail -1) $(date +%T)"
# the micro set, and any more repos after the label; through fresh paths (micro-fresh.sh)
micro="eshop jellyfin btcpayserver umbraco vikunja gitea mattermost grafana dispatch netbox ghost outline"
# shellcheck disable=SC2086
"$here/micro-fresh.sh" "$label" $micro "$@" >"$out/micro.txt" 2>&1
rc=$?
tail -n +1 "$out/micro.txt" | grep -E "identical|differ|failed|not compared|no base run"
echo "micro rc=$rc $(grep -h 'repo(s) differ' "$out/micro.txt" | tail -1) $(date +%T)"
