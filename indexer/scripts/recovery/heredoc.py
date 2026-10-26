"""Rebuild scratchpad files that a Bash heredoc wrote (`cat > $S/x <<'EOF' ... EOF`): the last write of each wins.
Lists the later `sed -i` and in-place python edits of each file, which it does not replay.
   heredoc.py TRANSCRIPT OUT_DIR NAME...   (NAME is the path under the scratchpad, e.g. h5/micro-fresh.sh)"""
import json
import re
import sys
from pathlib import Path

transcript, out, names = sys.argv[1], Path(sys.argv[2]), sys.argv[3:]
PREFIX = r'(?:\$S|"\$S|/private/tmp/claude-\d+/[^/\s]+/[^/\s]+/scratchpad)/'
state: dict[str, str] = {}
quoted: dict[str, bool] = {}
later: dict[str, list[str]] = {n: [] for n in names}
for line in open(transcript, errors="replace"):
    if '"tool_use"' not in line or '"Bash"' not in line:
        continue
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        continue
    content = (msg.get("message") or {}).get("content")
    for c in content if isinstance(content, list) else []:
        if not isinstance(c, dict) or c.get("type") != "tool_use" or c.get("name") != "Bash":
            continue
        cmd = c.get("input", {}).get("command", "")
        for n in names:
            if n not in cmd:
                continue
            pat = re.compile(r"(?:cat|tee)\s*>\s*" + PREFIX + re.escape(n) + r'"?\s*<<-?\s*([\'"]?)(\w+)\1[^\n]*\n(.*?)\n\2\n',
                             re.S)
            writes = list(pat.finditer(cmd + "\n"))
            if writes:
                m = writes[-1]
                state[n], quoted[n] = m.group(3) + "\n", bool(m.group(1))
                later[n] = []
            elif n in state and re.search(r"sed -i|python3 -I - [^\n]*" + re.escape(n), cmd) and re.search(
                    r"(sed -i[^\n]*|open\([^)]*\"w\"\))", cmd):
                if re.search(r"sed -i[^\n]*" + re.escape(n), cmd) or re.search(r"python3 -I - [^\n]*" + re.escape(n), cmd):
                    later[n].append(cmd[:300])
for n, text in state.items():
    p = out / n
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    print(f"{n}: {len(text.splitlines())} lines, heredoc {'quoted' if quoted[n] else 'UNQUOTED (expanded by the shell)'};"
          f" {len(later[n])} later in-place edit(s)")
    for e in later[n]:
        print("   ", e.replace("\n", " ")[:200])
for n in names:
    if n not in state:
        print(f"{n}: not found")
