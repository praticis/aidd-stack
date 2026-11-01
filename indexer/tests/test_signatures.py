"""A symbol's signature is its declaration up to its body: its first line, cut at the `{` that opens the body, without
the `=>`, `=` or `:` that leads into it, whatever ends the line. A type the declaration ends with keeps its closing
`>`."""

import contextlib
import io

import pytest

FILES = {
    "package.json": '{"name": "app"}\n',
    "app/sig.ts": """export class Store {
  async load(id: string): Promise<Map<string, number>> {
    return new Map();
  }
}
export abstract class Base {
  protected abstract run(): Promise<void>;
}
export function used(widget: HTMLElement): Set<string> {
  return new Set();
}
export const handler = async (): Promise<void> => {
};
export const plain = () => {
};
export const make =
  () => 1;
export interface Paged extends Array<string>
{
  total: number;
}
export type Pair = Map<string, Set<number>>
""",
    "App.csproj": '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
    "Converter.cs": """namespace App;
public class Converter : BaseConverter<int, bool>
{
    public int Count =>
        1;
}
""",
    "Totals.cs": "namespace App;\r\npublic class Totals\r\n{\r\n    public int Sum =>\r\n        1;\r\n}\r\n",
    "go.mod": "module example.com/x\n\ngo 1.22\n",
    "limits/limits.go": "package limits\n\nvar Limit =\n\t10\n",
    "pyproject.toml": '[project]\nname = "app"\n',
    "app/calc.py": "def total(xs: list[int]) -> dict[str, int]:\n    return {}\n",
    "app/ready.py": "def ready() -> bool:\r\n    return True\r\n",
}

CASES = [
    ("a-method-keeps-the-type-it-returns", "app/sig:Store.load",
     "async load(id: string): Promise<Map<string, number>>"),
    ("an-abstract-method-keeps-the-type-it-returns", "app/sig:Base.run", "protected abstract run(): Promise<void>"),
    ("a-function-keeps-the-type-it-returns", "app/sig:used", "function used(widget: HTMLElement): Set<string>"),
    ("an-arrow-function-keeps-its-type-without-its-arrow", "app/sig:handler",
     "const handler = async (): Promise<void>"),
    ("an-arrow-function-drops-its-arrow", "app/sig:plain", "const plain = ()"),
    ("a-declaration-drops-the-equals-sign-its-line-ends-with", "app/sig:make", "const make"),
    ("an-interface-keeps-its-generic-base", "app/sig:Paged", "interface Paged extends Array<string>"),
    ("a-type-alias-keeps-its-type", "app/sig:Pair", "type Pair = Map<string, Set<number>>"),
    ("a-cs-class-keeps-its-generic-base", "App.Converter", "public class Converter : BaseConverter<int, bool>"),
    ("a-cs-property-drops-its-arrow", "App.Converter.Count", "public int Count"),
    ("a-cs-property-drops-its-arrow-before-a-crlf", "App.Totals.Sum", "public int Sum"),
    ("a-go-var-drops-the-equals-sign-its-line-ends-with", "limits.Limit", "var Limit"),
    ("a-python-function-drops-its-colon", "app/calc:total", "def total(xs: list[int]) -> dict[str, int]"),
    ("a-python-function-drops-its-colon-before-a-crlf", "app/ready:ready", "def ready() -> bool"),
]


@pytest.fixture(scope="module")
def signatures(tmp_path_factory):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    root = tmp_path_factory.mktemp("repo")
    for rel, body in FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        res, _ = extract_and_resolve(RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(root)),
                                     convs=[])
    return {s.qualified_name: s.signature for s in res.symbols}


@pytest.mark.parametrize("name, signature", [pytest.param(n, s, id=i) for i, n, s in CASES])
def test_a_signature_is_its_declaration_up_to_its_body(signatures, name, signature):
    assert signatures[name] == signature
