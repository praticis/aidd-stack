#!/bin/sh
# GIT_ASKPASS for the indexer: answers git's HTTPS credential prompts from the
# environment, so `git fetch` works with PATs without any credential helper
# or stored secrets. Never prompts a human (GIT_TERMINAL_PROMPT=0 upstream).
#
#   AIDD_GIT_TOKEN                 token used for every host
#   AIDD_GIT_TOKEN_<HOST>          per-host override, HOST upper-cased with '.'/'-' -> '_'
#                                  e.g. AIDD_GIT_TOKEN_GITHUB_COM, AIDD_GIT_TOKEN_DEV_AZURE_COM
#   AIDD_GIT_USERNAME              username sent with the token (default: x-access-token,
#                                  accepted by GitHub, GitLab and Azure DevOps for PATs)
#
# git calls this as: askpass "Username for 'https://github.com': "
#                    askpass "Password for 'https://user@github.com': "
prompt="$1"
host=$(printf '%s' "$prompt" | sed -n "s#.*'https\{0,1\}://\([^/']*\)'.*#\1#p" | sed 's/.*@//')
key=$(printf '%s' "$host" | tr 'a-z.-' 'A-Z__')

case "$prompt" in
  Username*) printf '%s\n' "${AIDD_GIT_USERNAME:-x-access-token}" ;;
  Password*)
    token=$(eval "printf '%s' \"\${AIDD_GIT_TOKEN_${key}:-}\"")
    [ -z "$token" ] && token="${AIDD_GIT_TOKEN:-}"
    if [ -z "$token" ]; then
      echo "aidd: no AIDD_GIT_TOKEN (or AIDD_GIT_TOKEN_${key}) in the environment for ${host}" >&2
      exit 1
    fi
    printf '%s\n' "$token" ;;
  *) exit 1 ;;
esac
