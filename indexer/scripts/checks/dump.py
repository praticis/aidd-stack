"""Every C# file's type facts under /corpus, as JSON in field order, one line per file: `repo/path<TAB>json`.
The code is the indexer mounted at /src; the repos are only parsed.   dump.py OUT_FILE

Rebuilt from the transcript of the session that wrote it on 2026-10-22, not recovered as a file."""
import json
import sys
from pathlib import Path

from tree_sitter_language_pack import get_parser

from aidd_indexer import languages


def plain(x):
    if hasattr(x, "_asdict"):
        return {k: plain(v) for k, v in x._asdict().items()}
    if isinstance(x, dict):
        return {k: plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [plain(v) for v in x]
    return x


lang, parser = languages.by_id("csharp"), get_parser("csharp")
n = 0
with open(sys.argv[1], "w") as out:
    for repo in sorted(Path("/corpus").iterdir()):
        for f in sorted(repo.rglob("*.cs")):
            if not f.is_file() or f.is_symlink():
                continue
            src = f.read_bytes()
            facts = lang.file_facts(parser.parse(src).root_node, src)
            out.write(f"{f.relative_to('/corpus')}\t{json.dumps(plain(facts), ensure_ascii=False)}\n")
            n += 1
print(f"{n} files")
