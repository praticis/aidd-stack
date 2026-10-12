# Convention extensions

Each folder here is a pip-installable package that publishes an aidd convention (ADR-003, extension
layer): the rules of a development pattern that the generic indexer cannot know — layers, entry
points, allowed dependencies, internal HTTP registrars/clients.

```
conventions/<name>/
  pyproject.toml                    # [project.entry-points."aidd.conventions"] <name> = "pkg:Class"
  aidd_conventions_<name>/
    __init__.py                     # class Name(DeclarativeConvention) or a full Convention subclass
    convention.yaml                 # the declarative part (format: aidd_indexer/conventions/declarative.py)
```

- The indexer image installs every package in this folder (`Dockerfile`); the build fails if one does
  not install or does not load.
- A tenant enables one by id in `atlas.yaml` (`conventions: [{id: <name>, repos: [...]}]`), or ad hoc
  with `AIDD_CONVENTIONS=<name>`.
- Tests import them without installing (`tests/conftest.py` puts each folder on `sys.path`); a
  fixture that reproduces the pattern names it in `expected.json` (`"convention": "pkg:Class"`).
- Nothing organization-specific goes into `aidd_indexer/core/` or `aidd_indexer/languages/`.
