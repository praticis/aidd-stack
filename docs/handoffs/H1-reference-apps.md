# Handoff H1 — reference apps of the author's pattern (essentially closed)

The goal was for the indexer to understand the architecture pattern the author defined for the teams: hexagonal,
with its own way of registering routes, wrapping HTTP clients and naming layers. That would hold in every language
the pattern exists in, with fixtures of known result as a regression suite.

The pattern comes in as a **convention** (ADR-003), never in `core/` or `languages/`.

- **Done (F0.4.2, 2026-10-12, indexer 0.2.10):** .NET, with the `dotnet-praticis` extension
  (`indexer/conventions/dotnet-praticis/`). It brings roles, the `flat`, `split` and `layered` architectures, and the
  fixtures `csharp-praticis-todos`, `-reports` and `-projects`, with layers, entry points, a deliberate violation,
  `CALLS` and gaps in `expected.json`.
- **The Go fixtures** (`go-http-mix`, `go-wrapped-http`, `go-receiver-types`, ..) already follow the author's
  hexagonal layout.
- **Missing:** writing the Go, TS and Python convention when there is a reference app in those languages. Until then,
  it is an open item of F0.4.2 in the ROADMAP.

The handoff's original text is in `git show 1d73bb0:docs/handoffs/H1-reference-apps.md` (in Portuguese).
