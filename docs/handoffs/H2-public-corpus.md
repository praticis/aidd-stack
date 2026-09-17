# Handoff H2 — Ampliar o corpus público e medir precisão/recall do extrator

> Cole este arquivo (ou peça para ler `docs/handoffs/H2-public-corpus.md`) no início de um chat
> novo. Antes de qualquer coisa o chat deve ler `docs/indexer-evolution.md`, `docs/ROADMAP.md`
> (F0.4), `indexer/aidd_indexer/core/http_base.py` e `indexer/aidd_indexer/languages/<lang>/http.py`, e rodar
> `python indexer/scripts/http_corpus.py`
> para ter a baseline em mãos.

## Contexto em um parágrafo

O extrator de integrações HTTP (`core/integrations.py` orquestra; cada linguagem decide em `languages/<lang>/http.py`;
o que é comum está em `core/http_base.BaseScanner`) foi calibrado em 15 repositórios públicos
(Go: chi, gin, fiber, gorilla, alertmanager · TS: nest, express, fastify · C#: eShop, CleanArchitecture ·
Python: fastapi, flask). Isso tirou o viés dos três repos pequenos do time, mas ainda é uma amostra
pequena, sem *ground truth* e com frameworks faltando. Este handoff é sobre transformar o corpus em um
instrumento de medição de verdade: mais repos, mais frameworks, gabarito onde existir (OpenAPI/Swagger,
`routes` dumps, docs), e números de precisão/recall por linguagem que orientem o que melhorar.

## Objetivo

1. **Ampliar o corpus** para ~40 repos, cobrindo por linguagem os frameworks mais usados e ao menos um
   monólito grande e um serviço "de empresa" (não só exemplos):
   - Go: echo, httprouter, gorilla em app real, go-kit, grpc-gateway (rotas via anotações), um serviço
     grande (ex.: `grafana/grafana` API routes, `hashicorp/vault` http/, `argoproj/argo-cd`).
   - TS/JS: NestJS app real (não o repo do framework), Express monólito, Fastify app, Hono, Next.js
     API routes/route handlers (`app/api/**/route.ts` — rota vem do **caminho do arquivo**), tRPC (fora
     de escopo? decidir), axios/got/ky em clientes.
   - C#: ASP.NET com controllers reais (`[Route("api/[controller]")]` resolvido), minimal APIs com
     `MapGroup` aninhado, Refit, `IHttpClientFactory` com `BaseAddress` em `Program.cs`
     (ex.: `dotnet/eShopSupport`, `ardalis/CleanArchitecture`, `dotnet-architecture/eShopOnWeb`,
     `Orleans`? `abp`?).
   - Python: Django (`urls.py` + `path()`/`re_path()` + DRF routers — hoje **não coberto**), Flask app
     grande, FastAPI com `include_router(prefix=)` (prefixo cross-file, hoje não aplicado), aiohttp.
   - Java/Kotlin (Spring `@RequestMapping`) **só se** o ROADMAP confirmar que entra — hoje não é
     linguagem `PARSEABLE`; anotar como decisão.
2. **Gabarito**: para cada repo que publica OpenAPI/Swagger ou lista de rotas, extrair `(method, path)`
   esperados e calcular precisão/recall do extrator (`scripts/http_corpus.py --expected <dir>`); onde
   não houver, amostrar 20 rotas e 20 chamadas por repo e conferir na fonte, registrando FP/FN.
3. **Relatório por linguagem** (`docs/corpus-report.md`, EN): tabela repo × rotas × chamadas × P/R,
   lista dos falsos positivos/negativos por categoria, e o que cada categoria exigiria do extrator.
4. Corrigir o que for regra geral (não convenção de um projeto); registrar o resto como limitação.

## Como medir (sem se enganar)

- Rodar o corpus **antes** de mexer e guardar os JSONs (`--json baseline/`); depois de cada mudança,
  comparar contagens e *diffs* de ids (`method path_key evidence`) — regressão em um repo enquanto
  outro melhora é o caso comum.
- Precisão > recall para o extrator: um falso positivo vira aresta errada no grafo depois do linker;
  um falso negativo só deixa uma pergunta sem resposta (e a skill tem fallback).
- Separar as métricas: rotas (`HttpEndpoint`) e chamadas (`HttpCall`) têm perfis de erro diferentes.
  Chamadas de saída são naturalmente incompletas (URL montada em runtime) — medir recall só sobre as
  que têm path literal/template no código.
- Anotar sempre a **categoria** do erro, não só o caso: "prefixo em outro escopo", "router passado por
  parâmetro", "verbo minúsculo em receiver ambíguo", "rota por caminho de arquivo", etc. É a categoria
  que vira regra.

## Evoluções prováveis que o corpus maior vai pedir (para começar já sabendo)

- **Prefixos cross-scope/cross-file**: `r.Route("/admin", func(r chi.Router){...})` (closure),
  `app.include_router(router, prefix="/api/v1")` (outro arquivo), `Handle("/api/v1", subrouter)`,
  `app.use('/users', usersRouter)`. Caminho: um passo de *ligação de prefixos* por repo depois do
  scan (grafo de montagem: variável/módulo do router → prefixo), com `confidence: heuristic`.
- **Rota derivada do caminho do arquivo**: Next.js `app/api/users/[id]/route.ts` → `/api/users/{id}`
  (método = função exportada `GET/POST`), Nuxt/SvelteKit `+server.ts`, Remix. Precisa de um scanner
  por convenção de arquivo, não por chamada.
- **Django**: `urlpatterns = [path("users/<int:id>/", view)]` com `include()` aninhado — outro
  scanner (assignment + list) e prefixos por `include`.
- **`[controller]`/`[action]` no ASP.NET** já são substituídos quando o atributo está na própria
  classe; com `[Route]` herdado de classe base não são. Decidir se vale seguir herança.
- **Clientes gerados** (OpenAPI generator, NSwag, Refit, openapi-fetch): as rotas estão em arquivos
  gerados que hoje podem cair em `GENERATED_SUFFIXES`/excludes — decidir se entram como `HttpCall`
  com `via: generated-client`.
- **Base URL por serviço**: `services.AddHttpClient<CatalogService>(c => c.BaseAddress = new Uri("http://catalog-api"))`
  e `TERCEL_URL` em config — hoje só `env_hints`; o linker (F0.5) é quem usa. Não resolver no extrator
  além de registrar o dado.

## Restrições e convenções

- Sem LLM como parser; sem nomes de projetos/tenant reais nos docs (os repos públicos podem ser
  citados normalmente).
- Clonar com `--depth 1`; não versionar o corpus no repo (só a lista em `scripts/http_corpus.py` e,
  se houver, os gabaritos pequenos em `indexer/tests/corpus_expected/<repo>.json`).
- Mudança de semântica dos nós → bump de `INDEXER_VERSION`; label/índice novo → `schema.cypher` + `SCHEMA.md`.
- Toda regra nova entra na tabela §3 do guia `docs/indexer-evolution.md` com o sintoma que a motivou.

## Entregáveis esperados ao fim do chat

- `scripts/http_corpus.py` com a lista ampliada e suporte a `--expected`/`--baseline` (diff de ids).
- `docs/corpus-report.md` com P/R por repo e linguagem e a lista categorizada de gaps.
- `languages/<lang>/http.py` (e `core/http_base.py` para o que é comum a todas) evoluídos para as categorias
  que são regra geral — nunca heurística de uma organização (isso é convenção, ver ADR-003); fixture do H1
  (se já existir) e corpus sem regressão.
- ROADMAP: F0.4.3 "corpus ampliado + métricas" marcado; gaps direcionados a F0.5 (linker) ou F1.
