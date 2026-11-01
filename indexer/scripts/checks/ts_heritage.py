"""TS's bases against TypeScript's own checker, over every TS and JS file the indexer extracts from the repos under
/corpus. Each type a heritage clause of a module's class or interface names, in order, must be in the type index the
declaration the checker resolves it to (`ts_heritage.js`, each file read with its `tsconfig.json`'s `baseUrl` and
`paths`): `same`, or `none of the repo's` where neither gives one. Where the index gives `Unknown` and the checker a
declaration of the repo, the reason is counted, and a package's apart: the checker has no package, so the repo's
`tsconfig.json` maps that name to its own file. A global type the repo augments (`declare global { interface Window }`)
is the platform's. `index only` is a declaration the checker does not give, and `different` another one. A declaration
in a function or a namespace, and a name a module declares twice, which TS merges, are counted apart. The compiler
reads and types the files; nothing runs.

    ts_heritage.py [N]    N samples of each kind of difference (default 5)

In the image, with the code at /src, the compiler at $AIDD_TYPESCRIPT and the corpus's repos at /corpus."""
import collections
import json
import os
import subprocess
import sys
from pathlib import Path

from tree_sitter_language_pack import get_parser

from aidd_indexer import languages
from aidd_indexer.core.discovery import build_files, discover_modules, list_files
from aidd_indexer.core.model import RepoInfo
from aidd_indexer.core.types import TypeRef, Unknown
from aidd_indexer.languages.base import ResolveContext
from aidd_indexer.languages.typescript.type_facts import TsTypes
from aidd_indexer.languages.typescript.type_index import OUTSIDE, TsTypeIndex, module_of, qualified

ORACLE = Path(__file__).with_name("ts_heritage.js")
TS = frozenset({"typescript", "tsx", "javascript"})


def index_of(root: Path) -> tuple[TsTypeIndex, dict[str, TsTypes]]:
    """The repo's TS type index, from its TS and JS files' facts alone."""
    repo = RepoInfo(tenant="corpus", name=root.name, ref="main", commit_sha="x", root=str(root))
    rels = list_files(root)
    modules, _ = discover_modules(repo, rels)
    files = [f for f in build_files(repo, rels, modules) if f.language in TS]
    facts = {}
    for f in files:
        lang = languages.by_id(f.language)
        src = (root / f.path).read_bytes()
        tree = get_parser(lang.grammar).parse(src)
        facts[f.id] = lang.file_facts(tree.root_node, src, lang.file_index(tree.root_node, src))
    ctx = ResolveContext(root, {f.path: f for f in files}, {m.path: m for m in modules}, {m.id: m for m in modules},
                         {f.id: f for f in files}, {}, facts=facts)
    return TsTypeIndex(ctx), {f.path: facts[f.id] for f in files}


def oracle(root: Path, rels: list[str]) -> list[dict]:
    out = subprocess.run(["node", "--max-old-space-size=8192", str(ORACLE), "--files", str(root)],
                         input="\n".join(rels), capture_output=True, text=True, check=True,
                         env={**os.environ, "AIDD_TYPESCRIPT": os.environ.get("AIDD_TYPESCRIPT", "typescript")})
    return [json.loads(line) for line in out.stdout.splitlines()]


def kind_of(mine: TypeRef | Unknown, declared: list[str]) -> str:
    repo = [d for d in declared if d not in ("outside", "other") and not d.partition(":")[2].startswith("global.")]
    if isinstance(mine, TypeRef):
        return "same" if qualified(mine) in repo else "different" if repo else "index only"
    if not repo:
        return "none of the repo's"
    return "a package's, which the repo's tsconfig.json maps to its file" if mine == OUTSIDE \
        else f"index unknown: {mine.reason}"


def compare(types: TsTypeIndex, facts: dict[str, TsTypes], rows: list[dict]) -> list[tuple[str, str]]:
    """(kind, sample) for each type a clause of a module's class or interface names."""
    out: list[tuple[str, str]] = []
    declared: dict[tuple[str, str], dict[int, list[dict]]] = collections.defaultdict(dict)
    for r in rows:
        declared[r["file"], r["name"]].setdefault(r["at"], []).append(r)
    for (file, name), at in declared.items():
        if "." in name or not all(r["top"] for rs in at.values() for r in rs):
            out += [("in a function or a namespace", f"{file}:{name}")] * sum(map(len, at.values()))
            continue
        if len(at) > 1:
            out += [("declared twice", f"{file}:{name}")] * sum(map(len, at.values()))
            continue
        out += _clauses(types, facts, file, name, next(iter(at.values())))
    return out


def _clauses(types: TsTypeIndex, facts: dict[str, TsTypes], file: str, name: str,
             rows: list[dict]) -> list[tuple[str, str]]:
    owner = facts[file].owners.get(name) if file in facts else None
    if owner is None:
        return [("no facts", f"{file}:{name}")] * len(rows)
    found = types.bases(TypeRef(module_of(file), name))
    mine = {"extends": found[:len(owner.extends)], "implements": found[len(owner.extends):]}
    theirs = {c: [r for r in rows if r["clause"] == c] for c in mine}
    if any(len(mine[c]) != len(theirs[c]) for c in mine):
        return [("clauses read apart", f"{file}:{name}")] * len(rows)
    return [(kind_of(m, r["declared"]), f"{file}:{name} {r['clause']} index={_text(m)} checker={r['declared']}")
            for c in mine for m, r in zip(mine[c], theirs[c])]


def _text(t: TypeRef | Unknown) -> str:
    return qualified(t) if isinstance(t, TypeRef) else t.reason


def main(argv: list[str]) -> int:
    n = int(argv[0]) if argv else 5
    counts: collections.Counter = collections.Counter()
    samples = collections.defaultdict(list)
    for root in sorted(p for p in Path("/corpus").iterdir() if p.is_dir()):
        types, facts = index_of(root)
        if not facts:
            continue
        for kind, sample in compare(types, facts, oracle(root, sorted(facts))):
            counts[kind] += 1
            if len(samples[kind]) < n:
                samples[kind].append(f"{root.name}/{sample}")
        print(f"{root.name}: {sum(counts.values())} clauses so far", file=sys.stderr, flush=True)
    for key, value in sorted(counts.items()):
        print(f"{key}: {value}")
    for kind, lines in sorted(samples.items()):
        print(f"\n{kind}:\n  " + "\n  ".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
