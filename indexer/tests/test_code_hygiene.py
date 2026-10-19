"""The indexer's code points at no doc or planning item, and names no project: a comment says why the code is so, and an
example describes the shape of the code, naming only the framework or library that defines the behavior."""

import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "aidd_indexer"

DOC_REFERENCE = re.compile(r"\bF\d\.\d+\b|\bH\d-D\d+\b|\bADR-\d+\b|\bROADMAP\b|\bdocs/[\w-]+\.md\b|indexer-evolution|corpus-report")
# the corpus's applications with a name no comment uses as a plain word (`outline`, `ghost` or `memos` would)
PROJECT = re.compile(r"\b(vikunja|gitea|mattermost|photoprism|directus|docmost|open-webui|webui|umbraco|elsa|btcpay\w*|"
                     r"smartstore|radarr|kavita|mealie|immich|nodebb|argo-cd|kratos|alertmanager|gotify|zulip|netbox|ctfd|"
                     r"jellyfin|bitwarden|notifo|eshop\w*|sftpgo|planka)\b", re.IGNORECASE)
# what an MCP server tells the agent is product text, not a comment: it may point at the contract it serves
ALLOWED = {("knowledge/server.py", "docs/knowledge-contract.md")}


def _hits(pattern: re.Pattern) -> list[str]:
    out = []
    for f in sorted(PACKAGE.rglob("*.py")):
        rel = f.relative_to(PACKAGE).as_posix()
        for i, line in enumerate(f.read_text().splitlines(), 1):
            for m in pattern.finditer(line):
                if (rel, m.group(0)) not in ALLOWED:
                    out.append(f"{rel}:{i}: {m.group(0)}")
    return out


def test_no_doc_or_planning_reference():
    assert _hits(DOC_REFERENCE) == []


def test_no_project_name():
    assert _hits(PROJECT) == []
