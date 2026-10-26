"""Rebuild files of the scratchpad from the session transcript: each Write, then each Edit after it, in order.
   recover.py TRANSCRIPT OUT_DIR NAME...   (NAME is the path under the scratchpad, e.g. val/foto.sh)"""
import json
import sys
from pathlib import Path

transcript, out, names = sys.argv[1], Path(sys.argv[2]), sys.argv[3:]
SP = "/scratchpad/"
state: dict[str, str] = {}
for line in open(transcript, errors="replace"):
    if '"tool_use"' not in line or SP not in line:
        continue
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        continue
    content = (msg.get("message") or {}).get("content")
    for c in content if isinstance(content, list) else []:
        if c.get("type") != "tool_use" or c.get("name") not in ("Write", "Edit"):
            continue
        inp = c.get("input", {})
        path = inp.get("file_path", "")
        if SP not in path:
            continue
        rel = path.split(SP, 1)[1]
        if rel not in names:
            continue
        if c["name"] == "Write":
            state[rel] = inp.get("content", "")
        elif rel in state:
            old, new = inp.get("old_string", ""), inp.get("new_string", "")
            if old in state[rel]:
                state[rel] = state[rel].replace(old, new) if inp.get("replace_all") else state[rel].replace(old, new, 1)
            else:
                print(f"{rel}: an edit did not apply", file=sys.stderr)
for rel, text in state.items():
    p = out / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    print(rel, len(text.splitlines()), "lines")
print("missing:", [n for n in names if n not in state])
