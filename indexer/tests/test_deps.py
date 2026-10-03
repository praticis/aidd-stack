"""F0.5.1: manifests → provides/requires per language, and the DEPENDS_ON join rules."""
from __future__ import annotations

from pathlib import Path

from aidd_indexer import languages
from aidd_indexer.core.deps import collect_manifest_deps, normalize
from aidd_indexer.core.discovery import list_files
from aidd_indexer.core.linker import DepRow, ProvideRow, depends_on_rows, link_deps
from aidd_indexer.core.model import RepoInfo

FIXTURES = Path(__file__).parent / "fixtures"


def _repo(name: str) -> RepoInfo:
    root = FIXTURES / name
    return RepoInfo(tenant="t", name=name, ref="main", commit_sha="x", root=str(root))


def test_go_mod_module_and_direct_requires():
    names, deps = languages.by_id("go").manifest_deps("go.mod", (
        "module github.com/org/svc-a\n\ngo 1.22\n\nrequire (\n\tgithub.com/org/shared-kit v1.4.0\n"
        "\tgithub.com/gin-gonic/gin v1.9.1 // indirect\n)\nrequire golang.org/x/text v0.14.0\n"))
    assert names == ["github.com/org/svc-a"]
    assert deps == [("github.com/org/shared-kit", "v1.4.0"), ("golang.org/x/text", "v0.14.0")]


def test_csproj_package_id_and_package_references():
    names, deps = languages.by_id("csharp").manifest_deps("src/A/A.csproj", (
        '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><PackageId>Org.Shared.Contracts</PackageId></PropertyGroup>'
        '<ItemGroup><PackageReference Include="Refit" Version="7.0.0" />'
        '<PackageReference Include="Org.Accrual.Contracts" Version="1.2.3"></PackageReference>'
        '<ProjectReference Include="../B/B.csproj" /></ItemGroup></Project>'))
    assert names == ["Org.Shared.Contracts"]
    assert deps == [("Refit", "7.0.0"), ("Org.Accrual.Contracts", "1.2.3")]
    assert languages.by_id("csharp").manifest_deps("src/Shop.Api/Shop.Api.csproj", "<Project/>") == (["Shop.Api"], [])


def test_package_json_runtime_dependencies_only():
    names, deps = languages.by_id("typescript").manifest_deps("package.json", (
        '{"name":"@org/bff","dependencies":{"@org/contracts":"workspace:*","axios":"^1"},'
        '"devDependencies":{"jest":"29"}}'))
    assert names == ["@org/bff"]
    assert deps == [("@org/contracts", "workspace:*"), ("axios", "^1")]


def test_pyproject_and_requirements():
    py = languages.by_id("python")
    names, deps = py.manifest_deps("pyproject.toml", '[project]\nname="svc_b"\ndependencies=["org-shared>=1.0", "fastapi[all]==0.1; python_version>\'3\'"]\n')
    assert names == ["svc_b"] and deps == [("org-shared", ">=1.0"), ("fastapi", "==0.1")]
    assert py.manifest_deps("requirements.txt", "# c\norg_shared==1.0\n-r base.txt\nhttpx\n")[1] == [("org_shared", "==1.0"), ("httpx", "")]
    assert normalize("pypi", "Org_Shared") == "org-shared"


def test_fixture_pair_declares_the_internal_dependency():
    mix, billing = _repo("go-http-mix"), _repo("go-billing-api")
    provides_b, _ = collect_manifest_deps(billing, list_files(Path(billing.root)))
    _, requires_a = collect_manifest_deps(mix, list_files(Path(mix.root)))
    assert [p.key() for p in provides_b] == ["go:example.com/go-billing-api"]
    assert [(d.key(), d.version) for d in requires_a] == [("go:example.com/go-billing-api", "v0.3.0"),
                                                          ("go:github.com/gorilla/mux", "v1.8.1")]


def test_link_deps_unique_provider_never_self_never_ambiguous():
    provides = [ProvideRow("billing", "go:example.com/billing"), ProvideRow("billing", "nuget:org.billing.contracts"),
                ProvideRow("legacy", "nuget:org.billing.contracts"), ProvideRow("bff", "npm:@org/bff")]
    requires = [DepRow("bff", "main", "s1", "go:example.com/billing", "v1.0.0"),
                DepRow("bff", "main", "s1", "nuget:org.billing.contracts", "2.0"),   # two publishers
                DepRow("bff", "main", "s1", "npm:@org/bff", "1.0"),                  # itself
                DepRow("bff", "main", "s1", "npm:axios", "^1"),                      # external
                DepRow("bff", "dev", "s2", "go:example.com/billing", "v1.1.0")]
    r = link_deps(requires, provides)
    assert [(e.dep.repo, e.provider, e.dep.ref) for e in r.edges] == [("bff", "billing", "main"), ("bff", "billing", "dev")]
    assert r.ambiguous == {"nuget:org.billing.contracts": ["billing", "legacy"]}
    rows = depends_on_rows(r)
    assert rows[0] == {"repo": "bff", "provider": "billing", "ref": "dev", "commit_sha": "s2",
                       "packages": ["example.com/billing"], "versions": ["v1.1.0"], "ecosystems": ["go"]}
