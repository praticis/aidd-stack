"""dotnet-praticis — the Praticis .NET pattern as an aidd convention (ADR-003, extension layer).

Everything the pattern needs is declarative (`convention.yaml` next to this file: layers, handler
entry points, dependency rules); the class only binds that file to the `aidd.conventions` entry point
so a tenant enables it by id:

```yaml
# atlas.yaml
tenants:
  <tenant>:
    conventions:
      - id: dotnet-praticis
        repos: ["*-api"]          # optional
```
"""

from __future__ import annotations

from pathlib import Path

from aidd_indexer.conventions.declarative import DeclarativeConvention

__version__ = "0.1.0"

CONVENTION_FILE = Path(__file__).with_name("convention.yaml")


class DotnetPraticis(DeclarativeConvention):
    def __init__(self) -> None:
        super().__init__(CONVENTION_FILE)
