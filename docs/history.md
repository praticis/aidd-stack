# Histórico

> Os marcos do projeto, um por linha, com a data e o PR em que entraram.
>
> - O texto completo de cada entrada, como era escrito na seção "Onde estamos" do ROADMAP, está em
>   `git show 1d73bb0:docs/ROADMAP.md`.
> - A narrativa de cada incremento do corpus está em `git show 1d73bb0:docs/corpus-report.md`.
>
> As decisões estão em `docs/decisions.md`; o estado atual, no ROADMAP.

## Fase 0: a fundação (PR #1, mergeado em 2026-10-13)

- 2026-09-09: D1, o Neo4j Community (ADR-001); Neo4j e `neo4j-init` no compose; esquema v1 em `neo4j/SCHEMA.md`.
- 2026-09-10: o compose sobe; credenciais centralizadas no `.env`; o `install-check.sh` passa; o MCP vira `atlas`
  (D6).
- 2026-09-10: F0.3, o indexador validado no atlas real com um repo Go do portfólio; `AIDD_TENANT` obrigatório em todo
  o stack (D7).
- 2026-09-11: pausa para desenhar o processo de indexação (`docs/indexing-process.md`, D8–D11). Depois, o F0.3.5:
  `atlas.yaml`, `aidd plan/bootstrap/refresh` e refs por `git archive`.
- 2026-09-11: instalação limpa validada de ponta a ponta: 6 repos e 22 snapshots em 26 s. A baseline de resolução por
  nome fica em ~40 % dos call sites Go, a métrica que o SCIP precisa bater.
- 2026-09-11: o GC validado; o indexador faz o próprio fetch; D12 (instalação ≠ atualização); a atualização
  contínua é validada (U1–U3.1).
- 2026-09-11: incidente: um build sem gramáticas gravou snapshots vazios como sucesso. A causa era o
  `tree-sitter-language-pack` baixando gramáticas em runtime. Correções:
  - versões pinadas;
  - as gramáticas baixadas no build;
  - o `aidd selftest`;
  - o rc=4 quando falta gramática.
- 2026-09-11: F0.6, o MCP `atlas` v0 (`atlas_status`, `repo_map`, `find_symbol`, `who_calls`, `symbol_context`,
  `cypher_readonly`), validado no Claude Code (F0.6.1).
- 2026-09-11: F0.8, a skill `scan` v2 sobre o atlas, com fallback explícito; validada nos dois casos (F0.8.1).
- 2026-09-12: F0.4, o extrator de integrações HTTP v0, com rotas e chamadas de saída em Go, TS, C# e Python e as
  tools `http_map` e `who_consumes` (indexer 0.2.0). Calibrado num corpus público de 15 repos.
- 2026-09-12: o guia `docs/indexer-evolution.md` e os handoffs H1 (apps de referência) e H2 (corpus público).
- 2026-09-14: ADR-002 (tree-sitter como base, SCIP como enriquecimento) e ADR-003 proposto (núcleo + módulos por
  linguagem, convenções como extensões).
- 2026-09-15: a primeira instalação multi-tenant (`AIDD_TENANT=auto`).
- 2026-09-17: F0.4.1, parcial num ambiente .NET multi-tenant; F0.4.4, o refactor do ADR-003 feito, com corpus e
  fixtures idênticos.
- 2026-09-25: F0.5, o linker materializa `CONSUMES`/`CALLED_FROM` por `path_key` e método, com desempate por hints.
- 2026-09-29: F0.5 validado no portfólio; F0.5.1 fechado; F0.7 (CALLS por tipo do receptor) em andamento.
- 2026-10-03: F0.7 fechado e a **Fase 0 concluída**: golden questions respondidas pelo grafo em Go e no par .NET de
  referência.
- 2026-10-03: F0.7.2 (hooks C#: `call_receiver`, `implementations`), `DEPENDS_ON` por manifesto (F0.5.1), F0.3.6
  (política de refs) e F0.4.5 (convenções com `route_patterns`, `Violation` no MCP; indexer 0.2.6).
- 2026-10-03: um bug de GC num reindex do mesmo commit (0.2.7); handler em outro arquivo do pacote; endpoint por
  `path_key` (0.2.8).
- 2026-10-12: convenções mais expressivas (padrão × arquitetura); F0.4.2 .NET com a extensão `dotnet-praticis` e as
  fixtures `csharp-praticis-*` (0.2.10). As fixtures registram os gaps do .NET para o F0.7.3.
- 2026-10-12: segurança e operação: exposição fechada (gateway, portas em localhost) e o refresher em container com
  espelhos (D15).
- 2026-10-12: a `scan` fechada sobre a fundação (0.2.11); o desenho da trilha de conhecimento (D16, D17).

## Conhecimento do projeto (PR #2, mergeado em 2026-10-14)

- 2026-10-13: correções do primeiro uso em code review (0.2.12).
- 2026-10-13: K1 e K1.1 (contrato do vault e `policy.yaml`), K2 (o serviço `knowledge`, `mcp-knowledge` em :3006) e
  K3 (a `scan` escreve o índice pelo contrato), validados na instalação real; a trilha pausa depois do K3.

## O grafo segue o dispatch (PR #3, mergeado em 2026-10-15)

- 2026-10-13: F0.7.3, despacho do mediator e interfaces Go (0.2.13); gaps .NET (3) e (4): métodos da base de um
  pacote, serviços do container e closures.
- 2026-10-14: validados na instalação real; sobrecargas pela contagem de argumentos e registros do DI com a cadeia de
  decorators (0.2.14); terceira rodada da Q4 .NET.
- 2026-10-14: a impressão digital do build entra no snapshot: reindexar deixa de depender de lembrar a versão.

## H2: o corpus público e o extrator medido (PR #4, mergeado em 2026-10-18)

- 2026-10-14: F0.4.3a (H2a): o instrumento do corpus (`http_corpus.py`, `corpus_metrics.py`, gabaritos) e o
  `docs/corpus-report.md` v1 com 15 repos.
- 2026-10-15: H2b: as correções baratas; o corpus v2 com 39 repos de apps reais; os defeitos baratos do v2.
- 2026-10-15/16: o grafo de montagem (dentro do arquivo, depois entre arquivos); as chamadas e os wrappers do C#; o
  NSwag; os servidores e clientes gerados Go; o flask-restx; o grafo entre arquivos em TS/JS; o `setGlobalPrefix` do
  Nest.
- 2026-10-16: fora do H2 e achado nele: chamada genérica com receptor em C#; rotas ASP.NET sem distinção de caixa no
  linker; imports `.js` e aliases no TS. Os handoffs H3 (eficiência do dev com IA) e H4 (docs públicos e indexador em
  repo próprio) são registrados.
- 2026-10-17: os registrars próprios em TS/JS, os clientes gerados TS e a fase 5.
- 2026-10-17: **F0.4.3b fechado:** 42 repos, e um hold-out de 16 que mostrou sobreajuste (H2-D20). O que faltava virou
  o F1.14.
- 2026-10-17/18: F1.14, incrementos 1–5, com as formas que o hold-out mostrou:
  - os defeitos de precisão do Go;
  - os atributos de rota próprios, o OData e o FastEndpoints do .NET;
  - o grpc-gateway e o router de pacote do Go;
  - as subclasses de `APIRouter` do Python;
  - o Koa e a base do cliente no TS.

  13 repos do hold-out viram corpus (55).

## O fechamento do F1.14 (PR #5, `feature/f114-close`)

- 2026-10-18: incrementos 6–8: os grupos do FastEndpoints; o verbo customizado do gRPC; os routers Go por tipo
  declarado e as closures com nome; o prefixo próprio de um grupo global.
- 2026-10-18: incremento 9: um endpoint por app num monorepo (`app` no `HttpEndpoint`, indexer 0.2.15).
- 2026-10-18: incrementos 10–11: os wrappers de cliente do app em Python e em TS/JS; listas de routers em laço;
  `@fastify/autoload`; rotas do Next.js. Os scripts `corpus.sh` (em paralelo) e `test.sh`.
- 2026-10-18: o handoff H5 é registrado (refatoração antes do SCIP, H5-D1–D5).
- 2026-10-18: **F1.14 fechado, e com ele o H2.** O hold-out novo vai para depois do H5 (H2-D21).
- 2026-10-19: incremento 12: a validação do PR numa instalação ao vivo, antes do merge, achou dois defeitos dos
  wrappers TS e eles foram corrigidos. Baseline `2026-10-18-v2-baseline-28`. Quinta rodada das perguntas douradas.
- 2026-10-19: fase 0a do H4: os docs de trabalho reciclados (`AGENTS.md`, `history.md` e `decisions.md`).
