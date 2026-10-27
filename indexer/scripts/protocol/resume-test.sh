#!/usr/bin/env bash
# The resume test (docs/indexer/resume-test.md) on a pushed commit, headless: a fresh clone outside the workspace (a
# worktree would share the project's memory), a new `claude` session with no MCP servers and read-only tools, the prompt
# of §2, and the report in a file. Written to a folder next to the clone, outside the repository:
#   report.md         the session's report
#   calls.txt         its first line says which memory it loaded; then every tool call, with the failed or refused ones
#                     and those that touched a path outside the clone flagged (criteria 2, 4, 7, 9)
#   transcript.jsonl  the full event stream
#   resume-test.sh COMMIT                the clone stays; delete the folder when done
set -euo pipefail

commit="${1:?usage: resume-test.sh COMMIT}"
repo="$(cd "$(dirname "$0")/../../.." && pwd)"
sha="$(git -C "$repo" rev-parse --short "$commit")"
out="${AIDD_RESUME_RUNS:-$HOME/.cache/aidd-worktrees}/resume-test-$sha-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$out"
git clone --quiet "$(git -C "$repo" remote get-url origin)" "$out/checkout"
git -C "$out/checkout" checkout --quiet --detach "$(git -C "$repo" rev-parse "$commit")" \
  || { echo "$commit is not on the remote: push it first" >&2; exit 2; }

prompt="$(python3 -I -c 'import re, sys
text = open(sys.argv[1]).read()
print(re.search(r"## 2\. The prompt.*?```text\n(.*?)```", text, re.S).group(1))' "$out/checkout/docs/indexer/resume-test.md")"

# read-only by construction: no write tools, and only these commands. A refused call is kept in calls.txt.
allowed="Read,Grep,Glob"
for c in "git status" "git diff" "git log" "git show" "git branch" "git worktree list" "git rev-parse" "git rev-list" \
         "git ls-tree" "git ls-files" "git merge-base" "git stash list" "ls" "wc" "head" "tail" "cat" "grep" "echo" "awk" "sort" "git ls-remote" \
         "docker image inspect" "docker image ls" "gh pr view" "gh pr list" "gh pr checks" "gh run list"; do
  allowed="$allowed,Bash($c:*)"
done

cd "$out/checkout"
printf '%s' "$prompt" | claude -p --output-format stream-json --verbose --no-session-persistence \
  --setting-sources project --strict-mcp-config --permission-mode dontAsk \
  --tools Read Grep Glob Bash --allowedTools "$allowed" >"$out/transcript.jsonl" 2>"$out/stderr.txt" \
  || echo "claude exited with $?; see $out/stderr.txt" >&2

python3 -I - "$out" <<'EOF'
import json, sys
out = sys.argv[1]
checkout = out + "/checkout"
meta, calls, names, report = {}, [], {}, ""
for line in open(out + "/transcript.jsonl"):
    try:
        ev = json.loads(line)
    except ValueError:
        continue
    kind = ev.get("type")
    if kind == "system" and ev.get("subtype") == "init":
        meta = {k: ev.get(k) for k in ("model", "cwd", "mcp_servers", "permissionMode", "memory_paths")}
    elif kind == "assistant":
        for block in ev.get("message", {}).get("content", []):
            if block.get("type") == "tool_use":
                inp = block["input"]
                arg = inp.get("command") or inp.get("file_path") or " in ".join(
                    x for x in (inp.get("pattern"), inp.get("path")) if x)
                names[block["id"]] = len(calls)
                calls.append([block["name"], str(arg), ""])
    elif kind == "user":
        for block in ev.get("message", {}).get("content", []):
            if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("is_error"):
                if block.get("tool_use_id") in names:
                    calls[names[block["tool_use_id"]]][2] = "FAILED OR REFUSED"
    elif kind == "result":
        report = ev.get("result", "")
        meta.update({k: ev.get(k) for k in ("num_turns", "duration_ms", "total_cost_usd", "is_error")})
open(out + "/report.md", "w").write(report + "\n")
with open(out + "/calls.txt", "w") as fh:
    fh.write(json.dumps(meta) + "\n")
    for name, arg, flag in calls:
        paths = arg.replace(" in ", " ").split()
        outside = any(t.startswith(("/", "~")) and not t.startswith(checkout) for t in paths)
        fh.write(f"{name}\t{arg}\t{flag}{' OUTSIDE THE CHECKOUT' if outside else ''}\n")
print(out)
EOF

echo "the run folder holds the clone and the outputs; delete it whole when done: rm -rf $out" >&2
