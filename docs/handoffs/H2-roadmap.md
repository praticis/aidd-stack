# H2 — Roteiro e estado (corpus público + precisão/recall do extrator HTTP)

> Documento vivo do handoff H2. O *briefing* (o que e por quê) está em `H2-public-corpus.md`; aqui fica
> **o plano, as decisões e onde estamos**. Atualize "Onde estamos" e o "Log" ao fim de cada sessão.
> No ROADMAP geral, H2a = F0.4.3a e H2b = F0.4.3b.
>
> **Para retomar num chat novo:** ler este arquivo → `H2-public-corpus.md` → `docs/indexer-evolution.md`
> (§3 regras, §5 medição, §6 checklist) → `core/http_base.py` e `languages/<lang>/http.py` da linguagem
> em foco. Depois, rodar o corpus contra a baseline vigente (ver "Onde estamos").

## Onde estamos

- **Estado:** Fases 0 e 1 concluídas (2026-10-14) — corpus fixado por SHA, baseline gerada e instrumento
  pronto (`--baseline`, `--expected`, `--sample`, `from-openapi`); extrator intocado.
- **Incremento atual:** H2a — Fase 2 (relatório v1).
- **Branch:** `feature/h2-corpus` a partir da `main` (f854509, já com o dispatch mergeado), na pasta
  principal do repo. O H2 é a frente principal desde 2026-10-14.
- **Indexer de referência:** 0.2.14.
- **Baseline vigente:** `~/.cache/aidd-corpus/runs/2026-10-14-baseline/` (15 JSONs, com `repo` e `sha`),
  gerada a partir da f854509 nos SHAs fixados em `CORPUS`. É idêntica, id a id, à de 2026-10-13 (8069b56).
- **Como rodar** (a imagem `aidd-indexer:local` já traz as gramáticas; o código da árvore entra por
  `PYTHONPATH`, então não precisa rebuild a cada mudança):

  ```bash
  docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONPATH=/src \
    -v "$PWD/indexer":/src:ro -v ~/.cache/aidd-corpus:/corpus \
    --entrypoint python aidd-indexer:local /src/scripts/http_corpus.py \
    --dir /corpus/repos --json /corpus/runs/<data>-<rótulo>
  ```
- **Testes:** `docker run --rm -e PYTHONPATH=/src -v "$PWD/indexer":/src:ro -w /src -e PYTHONDONTWRITEBYTECODE=1
  --entrypoint python aidd-indexer-test:local -m pytest -q -p no:cacheprovider tests`, **sem** `--user`: com o
  usuário do host, 47 testes falham com permissão negada ao escrever no cache de gramáticas (`/opt/tslp-cache`).
- **Próximo passo:** Fase 2 — descobrir quais dos 15 repos têm spec commitada e gerar os gabaritos `openapi`
  com `scripts/corpus_metrics.py from-openapi`.

## Decisões

| # | Data | Decisão | Por quê |
|---|---|---|---|
| H2-D1 | 2026-10-13 | H2 em dois incrementos: **H2a** (instrumento + relatório v1 com os 15 repos atuais, fecha F0.4.3a) e **H2b** (ampliar para ~40 repos + evoluir o extrator, F0.4.3b) | Validar o instrumento num conjunto pequeno antes de ampliar; o ROADMAP já previa o corte |
| H2-D2 | 2026-10-13 | Cada repo do corpus é fixado por **SHA**, não pelo HEAD | Com `--depth 1` no HEAD a baseline muda sozinha e o diff deixa de significar algo |
| H2-D3 | 2026-10-13 | Clones e saídas ficam **fora do repo**, em `~/.cache/aidd-corpus/{repos,runs/<data>-<rótulo>}` | `/tmp` some no reboot; o corpus não é versionado |
| H2-D4 | 2026-10-13 | Gabarito só vem de **spec commitada**, de *routes dump* publicado ou de amostragem manual; **não rodar os apps** para gerar OpenAPI | Rodar o app executa código de terceiros e exige as dependências dele |
| H2-D5 | 2026-10-13 | Métricas separadas para rotas (`HttpEndpoint`) e chamadas (`HttpCall`); o recall de chamadas conta só as que têm path literal/template no código | Os perfis de erro são diferentes; URL montada em runtime não é falha do extrator |
| H2-D6 | 2026-10-13 | A amostragem mede precisão sorteando **do extraído** e recall sorteando **da fonte** (arquivos que registram rotas e fazem chamadas) | Sortear só do extraído nunca mostra um falso negativo |
| H2-D7 | 2026-10-13 | **tRPC fora de escopo** (registrar como limitação) | São procedures, não rotas REST por path |
| H2-D8 | 2026-10-13 | **Java/Kotlin fora**: não são linguagem parseável do indexer | Entra só se o ROADMAP adicionar a linguagem |
| H2-D9 | 2026-10-13 | Clientes gerados (NSwag, openapi-generator, openapi-fetch): **só medir** no H2a; decidir no H2b com os números | Sem dado não há como saber se vale `via: generated-client` |
| H2-D10 | 2026-10-13 | `[Route]` herdado de classe base no ASP.NET: **medir a frequência** antes de decidir se segue herança | Custo alto, frequência desconhecida |
| H2-D11 | 2026-10-13 | Precisão > recall: regra nova que sobe recall e derruba precisão em algum repo não entra | Um FP vira aresta errada no grafo depois do linker |

## H2a — instrumento e relatório v1 (F0.4.3a)

### Fase 0 — preparação
- [x] Branch `feature/h2-corpus` a partir da `main`
- [x] Ambiente: `docker compose run --rm indexer ...` ou `pip install -e indexer` + `prefetch` (guia §4); a imagem `aidd-indexer:local` já faz o `selftest` no build
- [x] `CORPUS` com `(slug, sha)` por repo; clone por `git fetch --depth 1 origin <sha>` (H2-D2)
- [x] Default de `--dir` → `~/.cache/aidd-corpus/repos` (H2-D3)
- [x] **Baseline** antes de qualquer mudança no extrator: `--json ~/.cache/aidd-corpus/runs/<data>-baseline/`; anotar em "Onde estamos" e preencher a tabela "Números"

### Fase 1 — instrumento (`indexer/scripts/http_corpus.py`; o extrator não muda nesta fase)
- [x] `--baseline <dir>`: diff de ids `method path_key evidence` por repo (entrou/saiu), rotas e chamadas separadas
- [x] Formato do gabarito em `indexer/tests/corpus_expected/<repo>.json`:
      `{source: openapi|routes-dump|sample, sha, endpoints: [{method, path}], calls: [{method, path}], sampled_fp: [...], notes}`
- [x] `--expected <dir>`: P/R por `(method, path_key)`, rotas e chamadas separadas (H2-D5)
- [x] Conversor OpenAPI/Swagger → gabarito, com `servers`/`basePath` como prefixo (reaproveitável no F2.1)
- [x] `--sample N --seed S`: amostra reprodutível com `evidence` para conferência na fonte
- [x] Teste unitário da função de métrica (sem rede)
- **Pronto quando:** rodar o corpus contra a baseline dá diff vazio, e um gabarito de brinquedo produz P/R conferido à mão.
  ✅ 2026-10-14: 0 de 15 repos com diferença; gabarito de brinquedo do gin-realworld (escopo `articles/`) deu
  P 2/9 e R 2/3, igual à conta à mão, e a amostra `checked` deu 2/3 com 1 pendente e 1 stale.

### Fase 2 — relatório v1 (15 repos)
- [ ] Identificar quais dos 15 têm spec commitada (o ROADMAP fala em 2) → gabarito `source: openapi`
- [ ] Nos demais: 20 rotas + 20 chamadas sorteadas do extraído (precisão) e rotas/chamadas listadas a partir de arquivos sorteados da fonte (recall) (H2-D6)
  - Precisão: `--sample 20 --seed <n>` imprime entradas `checked` prontas para colar no gabarito; preencher `ok`/`category`.
  - Recall: sortear arquivos que registram rotas ou fazem chamadas (grep do framework por linguagem), listar à mão tudo o
    que eles têm e gravar com `scope` = esses arquivos. Se o grep virar rotina, transformar em `--sample-files`.
- [ ] Cada erro com **categoria** da taxonomia abaixo (criar categoria nova quando nenhuma servir, e registrar aqui)
- [ ] Medir H2-D9 (clientes gerados) e H2-D10 (`[Route]` herdado)
- [ ] `docs/corpus-report.md` (EN): tabela repo × rotas × chamadas × P/R por linguagem; gaps por categoria com o que cada uma exigiria do extrator e o destino (extrator / linker F0.5 / OpenAPI F2.1 / limitação)
- [ ] ROADMAP: F0.4.3a `[x]` + entrada em "Onde estamos"; docstring do script com a ordem de grandeza nova
- **Pronto quando:** o relatório existe, cada número é reproduzível pelo script e o ranking de categorias define a ordem do H2b.

## H2b — corpus ampliado e evolução do extrator (F0.4.3b)

### Fase 3 — ampliar para ~40 repos
Critério: dar preferência a repos **com spec commitada** (o gabarito sai de graça), incluindo por linguagem
ao menos um monólito grande e um serviço "de empresa". Candidatos **a confirmar** (spec, tamanho, licença):

| Linguagem | Candidatos | O que testam |
|---|---|---|
| Go | go-gitea/gitea, mattermost/mattermost, grafana/grafana, hashicorp/vault (`http/`), argoproj/argo-cd, um app com echo, um com httprouter, go-kit | `Group` com closure, subrouters gorilla, grpc-gateway (anotações) |
| TS/JS | immich-app/immich (server Nest), app Next.js com `app/api/**/route.ts`, exemplos Hono, monólito Express, app Fastify | Nest real, rota por caminho de arquivo, `app.use('/x', router)` |
| C# | dotnet-architecture/eShopOnWeb, dotnet/eShopSupport, ardalis/CleanArchitecture | `[Route("api/[controller]")]`, `MapGroup` aninhado, `AddHttpClient` + `BaseAddress` |
| Python | zulip/zulip, netbox-community/netbox, app FastAPI com `include_router(prefix=)`, app aiohttp, Flask grande | Django `urls.py` + `include()`, DRF routers, prefixo cross-file |

- [ ] Selecionar e confirmar a lista; fixar SHAs; gabaritos onde houver spec
- [ ] Rodar e estender `corpus-report.md` (seção v2)

### Fase 4 — evoluir o extrator (ordem definida pelo ranking do relatório)
Por categoria: fixture → mudança em `languages/<lang>/http.py` (ou `core/http_base.py` se for comum) →
`pytest` → corpus `--baseline` (nenhum repo pode regredir, H2-D11) → tabela §3 do guia → nova baseline.
Um commit por categoria. Aposta inicial (a confirmar pelos dados):
- [ ] Prefixo cross-scope no **mesmo arquivo** (closure `r.Route("/admin", func...)`, `app.use('/x', router)` local)
- [ ] Ligação de prefixos **cross-file** (`include_router(prefix=)`, `app.use('/x', require(...))`, `Handle("/api", sub)`): passo pós-scan em `integrations.py`, `confidence: heuristic` → bump `INDEXER_VERSION` e `SCHEMA.md` se o nó ganhar campo
- [ ] Django: `urlpatterns` + `path()`/`re_path()` + `include()`
- [ ] Rotas por caminho de arquivo: Next.js `app/**/route.ts` (método = função exportada)
- [ ] Decidir H2-D9 e H2-D10 com os números

### Fase 5 — fechamento
- [ ] ROADMAP: F0.4.3b `[x]`; gaps encaminhados (base URL → F0.5 linker; spec como fonte → F2.1; resto → F1 ou limitação)
- [ ] Guia: §3 (regras novas com o sintoma) e §5 (como usar `--expected`/`--baseline`)

## Taxonomia de erros (semente)

| Categoria | Exemplo | Provável destino |
|---|---|---|
| `prefix-other-scope` | `r.Route("/admin", func(r chi.Router){...})` | extrator (mesmo arquivo) |
| `prefix-other-file` | `app.include_router(r, prefix="/api/v1")`, `app.use('/users', usersRouter)` | extrator (passo de ligação) |
| `router-as-param` | `func register(r chi.Router) { r.Get(...) }` | extrator / limitação |
| `route-by-file-path` | Next.js `app/api/users/[id]/route.ts` | extrator (scanner por arquivo) |
| `route-by-name-convention` | `MapGet(GetTodoItems)`, controllers sem atributo | limitação |
| `django-urlconf` | `urlpatterns = [path("users/<int:id>/", view)]` | extrator (scanner novo) |
| `inherited-route-attr` | `[Route]` na classe base | H2-D10 |
| `lowercase-verb-ambiguous` | `client.get(key)` que não é HTTP (FP) | extrator (`CLIENT_RECEIVER`) |
| `generated-client` | NSwag/openapi-generator em arquivo gerado | H2-D9 |
| `runtime-url` | URL montada sem literal | fora da métrica (H2-D5) |
| `test-app-folder` | `nestjs/nest` `integration/<x>/src/*.controller.ts` (apps de teste fora de `e2e/`) | extrator (`TEST_FILE`?) — decidir na Fase 2 |
| `base-url-in-config` | `BaseAddress = new Uri(...)`, `*_URL` | linker F0.5 |

## Números

Referência 2026-09 = ordem de grandeza do docstring antigo, medida no HEAD de então (SHA desconhecido). Baseline = 2026-10-13 nos
SHAs fixados — a diferença entre as duas mistura mudança dos repos e do extrator, então não serve como regressão.

| Repo | Ling. | Rotas (ref. 2026-09) | Chamadas (ref.) | Rotas (baseline) | Chamadas (baseline) | Gabarito | P rotas | R rotas | P chamadas | R chamadas |
|---|---|---|---|---|---|---|---|---|---|---|
| chi | Go | 26 | — | 25 | 0 |  |  |  |  |  |
| gin-examples | Go | 31 | — | 31 | 0 |  |  |  |  |  |
| gin-realworld | Go | 13 | — | 12 | 0 |  |  |  |  |  |
| fiber-recipes | Go | 135 | — | 127 | 5 |  |  |  |  |  |
| alertmanager | Go | 22 | — | 22 | 0 |  |  |  |  |  |
| gorilla-mux | Go | 0 (só lib) | — | 0 | 0 |  |  |  |  |  |
| express | TS | 33 | — | 31 | 0 |  |  |  |  |  |
| express-realworld | TS | — | — | 19 | 0 |  |  |  |  |  |
| nest | TS | 124 | — | 195 | 1 |  |  |  |  |  |
| fastify | TS | 6 | — | 6 | 1 |  |  |  |  |  |
| eshop | C# | 23 | 6 | 23 | 6 |  |  |  |  |  |
| clean-arch-dotnet | C# | 0 (convenção) | — | 0 | 0 |  |  |  |  |  |
| fastapi | Py | 87 | — | 84 | 11 |  |  |  |  |  |
| fastapi-template | Py | 19 | — | 19 | 0 |  |  |  |  |  |
| flask | Py | 12 | — | 12 | 0 |  |  |  |  |  |

## Log

- **2026-10-13** — Plano aprovado: H2 dividido em H2a/H2b (H2-D1), decisões H2-D2…D11 registradas. Ambiente
  local ainda sem venv nem gramáticas (`aidd_indexer` não importa); o Docker está disponível.
- **2026-10-13** — Fase 0. Worktree `feature/h2-corpus` (a partir da `main`). O split do F0.4.3 no ROADMAP
  entrou na branch de dispatch (`01ef61a`): não mexer nessas linhas do ROADMAP nesta branch até o merge.
  `http_corpus.py`: `CORPUS` por SHA, clone do SHA exato, `--dir` padrão `~/.cache/aidd-corpus/repos`,
  JSON com `repo`/`sha`, docstring com a baseline nova. Achados: (1) no bind mount do Docker Desktop o
  primeiro `git fetch` num repo recém-criado falha com `bad object` e o segundo funciona → o script tenta
  3 vezes; (2) **nest: 157 das 195 rotas vêm de `integration/`** (apps de teste do próprio framework, que
  o filtro de pastas de teste não pega) → categoria candidata `test-app-folder`, avaliar na Fase 2.
- **2026-10-14** — Dispatch mergeado na `main` (f854509, indexer 0.2.14); o H2 virou a frente principal. O
  trabalho saiu do worktree e voltou para a pasta principal (branch recriada a partir da `main` nova, e o
  aviso sobre as linhas do ROADMAP deixou de valer). Baseline regenerada (`2026-10-14-baseline`) e idêntica
  à de 2026-10-13 em método, `path_key`, evidência e `handler_id` nos 15 repos: o dispatch não tocou na
  extração HTTP.
- **2026-10-14** — Fase 1. `scripts/corpus_metrics.py` (novo, funções puras): ids `method path_key evidence`
  e diff entre execuções (removidos, adicionados e `~` para mudança de `handler_id`/`caller_id` no mesmo id);
  P/R por pares distintos `(method, path_key)`, com ANY casando qualquer método e `scope` limitando o extraído;
  precisão manual por `checked`, que acusa itens stale; amostra com seed por repo e tipo; `from-openapi` com o
  prefixo de `basePath`/`servers[0].url` (ou `--prefix`). `http_corpus.py` ganhou `--baseline`, `--expected
  [dir]` (padrão `tests/corpus_expected/`), `--sample/--seed` e `--show`, e avisa quando o SHA do gabarito ou
  da baseline difere do pin. `tests/test_corpus_metrics.py`: 10 testes; a suíte inteira passa (157 ok, 2 skipped).
