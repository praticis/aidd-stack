#!/usr/bin/env bash
# What main holds, raised: sets the bounds of checks/reference_floors.txt that the measured counts beat (floors_bot.py), and with
# --push carries the change in the one pull request `chore/raise-floors`, rebuilt from main every time.
#
#   indexer/scripts/floors.sh --measured FILE [--sha SHA] [--push] [--branch NAME]
#
#   --measured FILE  the counts the scorecard measured on main (checks/reference.sh --out DIR leaves DIR/measured.txt)
#   --sha SHA        the commit of main they were measured on; it goes in the notes of the bounds raised and in the body
#   --push           commit on the branch, push it and open the pull request, or update it; with nothing to raise, close the one
#                    that is open. Without it nothing leaves the machine: it prints what it would raise and puts the file back
#   --branch NAME    the branch of the pull request (default chore/raise-floors)
#
# Run it at the root of a checkout of main, where `git push` and `gh` are allowed to write (the job of the workflow gives them a
# token whose pull requests start the checks: the one of GITHUB_TOKEN does not). The branch is `git switch -C` from main's commit
# and is pushed over what it was, which is the bot's own earlier raise: a branch that holds a commit of someone else's stops the
# job (2) and nothing is overwritten. Ends as `floors_bot.py raise`: 0, or 1 when main does not hold a bound, or has a count with
# no bound, which is an alarm and not a change; 2 for a wrong input or a git or gh that failed.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
bot="python3 -I $here/floors_bot.py"
name="${FLOORS_GIT_NAME:-floors bot}" email="${FLOORS_GIT_EMAIL:-floors-bot@users.noreply.github.com}"
file="indexer/scripts/checks/reference_floors.txt"
measured="" sha="" push="" branch="chore/raise-floors"
title="chore(scripts): raise the floors the graph holds"

while [ $# -gt 0 ]; do
  case "$1" in
    --measured) measured="$2"; shift 2 ;;
    --sha) sha="$2"; shift 2 ;;
    --push) push=1; shift ;;
    --branch) branch="$2"; shift 2 ;;
    -h|--help) sed -n '2,/^set -/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
[ -n "$measured" ] && [ -f "$measured" ] || { echo "floors: no such file of measured counts: $measured" >&2; exit 2; }
cd "$(git rev-parse --show-toplevel)"
[ -f "$file" ] || { echo "floors: no $file in this checkout" >&2; exit 2; }

before=$(mktemp) body=$(mktemp)
trap 'rm -f "$before" "$body"' EXIT
cp "$file" "$before"
note=()
[ -z "$sha" ] || note=(--note "measured on main at ${sha:0:7}")

rc=0
moved=$($bot raise "$file" "$measured" --write ${note[@]+"${note[@]}"}) || rc=$?
[ "$rc" -le 1 ] || exit 2

if [ -z "$moved" ]; then
  echo "Nothing to raise: no bound is beaten by what main holds."
  if [ -n "$push" ]; then
    open=$(gh pr list --head "$branch" --state open --json number --jq '.[0].number // empty')
    [ -z "$open" ] || gh pr close "$open" --delete-branch --comment "Nothing to raise any more: main holds no count beyond its bound."
  fi
  exit "$rc"
fi

echo "Raises:"
echo "$moved" | sed 's/^/- /'
if [ -z "$push" ]; then
  cp "$before" "$file"
  echo "(nothing was pushed: this is what --push would carry)"
  exit "$rc"
fi

$bot body "$before" "$file" ${sha:+--sha "$sha"} > "$body"
git fetch --quiet origin main
git fetch --quiet origin "$branch" 2>/dev/null || true
lease=$(git rev-parse --quiet --verify "refs/remotes/origin/$branch" || true)
if [ -n "$lease" ]; then
  foreign=$(git log --format='%an' "$lease" --not origin/main | grep -vxF "$name" || true)
  [ -z "$foreign" ] || { echo "floors: $branch holds a commit that is not the bot's ($foreign): close the pull request and delete the branch" >&2; exit 2; }
fi
git switch --quiet -C "$branch"
git add "$file"
git -c "user.name=$name" -c "user.email=$email" commit --quiet -m "$title"
git push --quiet --force-with-lease="$branch:$lease" origin "$branch"
if [ -n "$(gh pr list --head "$branch" --state open --json number --jq '.[0].number // empty')" ]; then
  gh pr edit "$branch" --title "$title" --body-file "$body"
else
  gh pr create --base main --head "$branch" --title "$title" --body-file "$body"
fi
exit "$rc"
