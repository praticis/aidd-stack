# Handoff H1 — apps de referência do padrão do autor (fechado no essencial)

O objetivo era que o indexador entendesse o padrão de arquitetura que o autor definiu para os times: hexagonal,
com um jeito próprio de registrar rotas, encapsular clientes HTTP e nomear camadas. Isso valeria em todas as
linguagens em que o padrão existe, com fixtures de resultado conhecido como suíte de regressão.

O padrão entra como **convenção** (ADR-003), nunca em `core/` nem em `languages/`.

- **Feito (F0.4.2, 2026-10-12, indexer 0.2.10):** o .NET, com a extensão `dotnet-praticis`
  (`indexer/conventions/dotnet-praticis/`). Ela traz papéis, as arquiteturas `flat`, `split` e `layered`, e as
  fixtures `csharp-praticis-todos`, `-reports` e `-projects`, com camadas, entry points, uma violação proposital,
  `CALLS` e gaps no `expected.json`.
- **As fixtures Go** (`go-http-mix`, `go-wrapped-http`, `go-receiver-types`, ..) já seguem o layout hexagonal do
  autor.
- **Falta:** escrever a convenção Go, TS e Python quando houver um app de referência dessas linguagens. Até lá, é
  item aberto do F0.4.2 no ROADMAP.

O texto original do handoff está em `git show 1d73bb0:docs/handoffs/H1-reference-apps.md`.
