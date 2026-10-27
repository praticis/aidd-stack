"""The golden questions and one call of every atlas tool, over the live MCP; each answer saved as JSON.

The calls are read from CALLS_JSON, a list of {"label", "tool", "arguments"}. The live install's list names its
tenants and repositories, so it is kept outside the repository; golden-calls.example.json shows the shape.

usage: golden.py CALLS_JSON OUT_DIR [--url URL]"""
import json
import sys
import urllib.request
from pathlib import Path

URL = "http://localhost:3005/mcp"


def call(url: str, name: str, args: dict) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": name, "arguments": args}}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    raw = urllib.request.urlopen(req, timeout=120).read().decode()
    if raw.lstrip().startswith("event:") or "\ndata:" in raw or raw.startswith("data:"):
        raw = next(ln[5:] for ln in raw.splitlines() if ln.startswith("data:"))
    res = json.loads(raw).get("result", {})
    out = {"isError": res.get("isError", False)}
    if "structuredContent" in res:
        out["content"] = res["structuredContent"]
    else:
        texts = [c.get("text", "") for c in res.get("content", [])]
        try:
            out["content"] = [json.loads(t) for t in texts]
        except ValueError:
            out["content"] = texts
    return out


def main(argv: list[str]) -> int:
    url = argv[argv.index("--url") + 1] if "--url" in argv else URL
    calls, out = json.loads(Path(argv[1]).read_text()), Path(argv[2])
    out.mkdir(parents=True, exist_ok=True)
    unreached = 0
    for c in calls:
        label, name = c["label"], c["tool"]
        try:
            r = call(url, name, c.get("arguments", {}))
        except Exception as e:  # noqa: BLE001
            r = {"transport_error": f"{type(e).__name__}: {e}"}
            unreached += 1
        (out / f"{label}.json").write_text(json.dumps(r, indent=1, sort_keys=True, ensure_ascii=False))
        size = len(json.dumps(r))
        print(f"{label:28} {name:16} error={r.get('isError', r.get('transport_error'))} {size} bytes")
    # an answer with isError is a result to compare (the refused write is one); a call that never reached the MCP is not
    return 1 if unreached else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
