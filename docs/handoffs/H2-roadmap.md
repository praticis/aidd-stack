# H2 — Roteiro e estado (corpus público + precisão/recall do extrator HTTP)

> Documento vivo do handoff H2. O *briefing* (o que e por quê) está em `H2-public-corpus.md`; aqui fica
> **o plano, as decisões e onde estamos**. Atualize "Onde estamos" e o "Log" ao fim de cada sessão.
> No ROADMAP geral, H2a = F0.4.3a e H2b = F0.4.3b.
>
> **Para retomar num chat novo:** ler este arquivo → `H2-public-corpus.md` → `docs/indexer-evolution.md`
> (§3 regras, §5 medição, §6 checklist) → `core/http_base.py` e `languages/<lang>/http.py` da linguagem
> em foco. Depois, rodar o corpus contra a baseline vigente (ver "Onde estamos").

## Onde estamos

- **Estado:** H2a concluído (2026-10-14). **H2b iniciado (2026-10-15)**: as três correções baratas de maior
  efeito (raiz, restrições/conversores, padrão relativo em grupo) + router com nome de cliente + o FP do
  roteamento convencional, com fixtures `route-patterns-{go,ts,py,cs}`. Recall pelos gabaritos: C# 49 → 73 %,
  Go 6 → 15 %, Python 31 → 43 %, TS/JS 6 → 9 %.
- **Incremento atual:** H2b — Fase 4, item 1 (restam as correções baratas menores), depois Fase 3.
- **Medir agora:** `http_corpus.py --expected --baseline <baseline> --show 20` (P/R por repo, resumo por
  linguagem e por categoria). Toda mudança no extrator roda contra essa baseline e esses gabaritos.
- **Branch:** `feature/h2-corpus` a partir da `main` (f854509, já com o dispatch mergeado), na pasta
  principal do repo. O H2 é a frente principal desde 2026-10-14.
- **Indexer de referência:** 0.2.14.
- **Baseline vigente:** `~/.cache/aidd-corpus/runs/2026-10-15-baseline/` — depois das correções baratas
  (a de 2026-10-14 fica como referência do v1).
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
- **Próximo passo:** fechar o item 1 da Fase 4 com as correções baratas menores
  (`query-in-template`, `method-default`, `test-client-in-source`, `optional-segment-syntax`, `verb-alias`) e
  partir para a Fase 3 (ampliar o corpus) antes do grafo de montagem.

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
| H2-D12 | 2026-10-14 | Rota **ou chamada** com path incompleto — prefixo que o código tem (grupo, mount, `include_router`, campo/constante interpolado) e se perdeu — conta como **erro**; prefixo vindo de config/env (`BaseAddress`, `*_URL`) não conta (é do linker) | O path é a chave do linker; path errado vira ligação errada ou nenhuma |
| H2-D13 | 2026-10-14 | Medir **o que o grafo recebe** (depois do `_dedupe`), sem contornar a fusão de rotas iguais entre apps do mesmo repo | A fusão é um defeito real (evidência e handler de outro app), não um artefato da medição — vira a categoria `multi-app-repo` |
| H2-D14 | 2026-10-15 | O H2-D11 julga o erro **que a regra introduz**. Item novo errado só porque herda um defeito já categorizado dos irmãos do mesmo router (prefixo perdido em outro escopo/arquivo) é contado, mas não bloqueia a regra | Nas correções baratas, 6 das 74 rotas novas erraram assim (a regra extraiu exatamente o que está escrito); recusar a regra deixaria de fora 68 corretas e o defeito continua sendo do grafo de montagem, que corrige todas juntas |

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
      `{source, sha, scope, endpoints: [{method, path, category}], calls: [...], checked: {endpoints, calls}, notes}` (formato completo no docstring de `scripts/corpus_metrics.py`)
- [x] `--expected <dir>`: P/R por `(method, path_key)`, rotas e chamadas separadas (H2-D5)
- [x] Conversor OpenAPI/Swagger → gabarito, com `servers`/`basePath` como prefixo (reaproveitável no F2.1)
- [x] `--sample N --seed S`: amostra reprodutível com `evidence` para conferência na fonte
- [x] Teste unitário da função de métrica (sem rede)
- **Pronto quando:** rodar o corpus contra a baseline dá diff vazio, e um gabarito de brinquedo produz P/R conferido à mão.
  ✅ 2026-10-14: 0 de 15 repos com diferença; gabarito de brinquedo do gin-realworld (escopo `articles/`) deu
  P 2/9 e R 2/3, igual à conta à mão, e a amostra `checked` deu 2/3 com 1 pendente e 1 stale.

### Fase 2 — relatório v1 (15 repos)
- [x] Identificar quais dos 15 têm spec commitada → **3**: eShop (`Catalog.API.json` + `_v2`), alertmanager
  (`api/v2/openapi.yaml`, só recall) e fiber-recipes (`swagger/`). Gabaritos em `indexer/tests/corpus_expected/`.
- [x] Nos demais: 20 rotas + 20 chamadas sorteadas do extraído (precisão) e rotas/chamadas listadas a partir de arquivos sorteados da fonte (recall) (H2-D6)
  - Precisão: `--sample 20 --seed <n>` imprime entradas `checked` prontas para colar no gabarito; preencher `ok`/`category`.
  - Recall: sortear arquivos que registram rotas ou fazem chamadas (grep do framework por linguagem), listar à mão tudo o
    que eles têm e gravar com `scope` = esses arquivos. Se o grep virar rotina, transformar em `--sample-files`.
- [x] Cada erro com **categoria** da taxonomia abaixo (criar categoria nova quando nenhuma servir, e registrar aqui)
- [x] Medir H2-D9 (clientes gerados) e H2-D10 (`[Route]` herdado) — D9: 32 operações em 2 clientes gerados, 0 extraídas
  (recomendação: extrair como `generated-client`); D10: 0 ocorrências no v1, decidir com os repos do H2b
- [x] `docs/corpus-report.md` (EN): tabela repo × rotas × chamadas × P/R por linguagem; gaps por categoria com o que cada uma exigiria do extrator e o destino (extrator / linker F0.5 / OpenAPI F2.1 / limitação)
- [x] ROADMAP: F0.4.3a `[x]` + entrada em "Onde estamos"; docstring do script com a ordem de grandeza nova
- **Pronto quando:** o relatório existe, cada número é reproduzível pelo script e o ranking de categorias define a ordem do H2b.
  ✅ 2026-10-14: 235 rotas e 24 chamadas julgadas na fonte; P/R e categorias saem do `--expected`.

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
Um commit por categoria. Ordem definida pelo relatório v1 (wrong + missed no corpus atual):
- [ ] **1. Correções baratas e gerais**
  - [x] *(2026-10-15)* `root-route-dropped` (raiz só com path completo conhecido: app ou grupo com prefixo),
    `route-constraint-syntax` (placeholder mascarado na validação; `?` opcional antes da query), `no-leading-slash`
    (`relative_on_groups` em Go/C#), `client-named-router` (router do arquivo vence o nome) e o FP do roteamento
    convencional do ASP.NET — fixtures `route-patterns-{go,ts,py,cs}`
  - [ ] `optional-segment-syntax`, `query-in-template`, `method-default` (`fetch` = GET), `test-client-in-source`, `verb-alias` (`Del`)
- [ ] **2. Grafo de montagem** (132 wrong + missed): `prefix-other-scope` no mesmo arquivo primeiro (closure
  `r.Route`, `Group`, `register(fn, {prefix})`), depois `prefix-other-file`/`router-as-param`/`global-prefix` entre
  arquivos (imports, constantes/settings, chamadas `Register(v1.Group("/x"))`): passo pós-scan em `integrations.py`,
  `confidence: heuristic` → bump `INDEXER_VERSION` e `SCHEMA.md` se o nó ganhar campo
- [ ] **3. Chamadas:** `field-in-interpolation` (campo/constante da classe dentro de `$"..."`), `url-object-builder` (Go `u.Path +=`, `JoinPath`)
- [ ] **4. H2-D9:** clientes gerados como `HttpCall` `via: generated-client` (openapi-ts: receiver entre parênteses + `url` no objeto de opções)
- [ ] **5. `test-app-folder`:** `/integration/` no `TEST_FILE` ou exclusão por config — decidir com os repos de produto do H2b
- [ ] Django: `urlpatterns` + `path()`/`re_path()` + `include()` (com os repos Python do H2b)
- [ ] Rotas por caminho de arquivo: Next.js `app/**/route.ts` (método = função exportada)
- [ ] Decidir H2-D10 com os repos do H2b

### Fase 5 — fechamento
- [ ] ROADMAP: F0.4.3b `[x]`; gaps encaminhados (base URL → F0.5 linker; spec como fonte → F2.1; resto → F1 ou limitação)
- [ ] Guia: §3 (regras novas com o sintoma) e §5 (como usar `--expected`/`--baseline`)

## Taxonomia de erros

As categorias medidas no v1, com exemplos, o que exigiriam e o destino, estão em `docs/corpus-report.md`
("Gaps by category"); o `--expected` as reconta a cada execução a partir do campo `category` dos gabaritos.
Categorias previstas e ainda não vistas no corpus (aparecerão com os repos do H2b):

| Categoria | Exemplo | Provável destino |
|---|---|---|
| `route-by-file-path` | Next.js `app/api/users/[id]/route.ts` | extrator (scanner por arquivo) |
| `django-urlconf` | `urlpatterns = [path("users/<int:id>/", view)]` | extrator (scanner novo) |
| `inherited-route-attr` | `[Route]` na classe base | H2-D10 |
| `lowercase-verb-ambiguous` | `client.get(key)` que não é HTTP (FP) | extrator (`CLIENT_RECEIVER`) |
| `generated-client` | NSwag/openapi-generator/openapi-ts em arquivo gerado | H2-D9 (medido: 32 operações, 0 extraídas) |
| `runtime-url` | URL montada sem literal | fora da métrica (H2-D5) |
| `base-url-in-config` | `BaseAddress = new Uri(...)`, `*_URL` | linker F0.5 |

## Números

Tabela do **v1** (2026-10-14), mantida como referência; os números atuais saem do `--expected` e a
comparação v1 → correções baratas está no relatório ("Update: the cheap fixes").

Referência 2026-09 = ordem de grandeza do docstring antigo, medida no HEAD de então (SHA desconhecido). Baseline = 2026-10-13 nos
SHAs fixados — a diferença entre as duas mistura mudança dos repos e do extrator, então não serve como regressão.

| Repo | Ling. | Rotas (ref. 2026-09) | Chamadas (ref.) | Rotas (baseline) | Chamadas (baseline) | Gabarito | P rotas (amostra) | R rotas (gabarito) | P chamadas (amostra) | R chamadas (gabarito) |
|---|---|---|---|---|---|---|---|---|---|---|
| chi | Go | 26 | — | 25 | 0 | manual (3 exemplos) | 24 % (6/25) | 4,5 % | — | — |
| gin-examples | Go | 31 | — | 31 | 0 | manual (4 exemplos) | 95 % (19/20) | 8,3 % | — | — |
| gin-realworld | Go | 13 | — | 12 | 0 | manual (routers) | 0 % (0/12) | 0 % | — | — |
| fiber-recipes | Go | 135 | — | 127 | 5 | openapi (swagger/) + manual (calls) | 100 % (20/20) | 50 % (2/4) | 80 % (4/5) | 100 % (4/4) |
| alertmanager | Go | 22 | — | 22 | 0 | openapi (/api/v2) + manual (calls) | 68 % (15/22) | 0 % (0/9) | — | 0 % (0/7) |
| gorilla-mux | Go | 0 (só lib) | — | 0 | 0 | — (só lib) | — | — | — | — |
| express | TS | 33 | — | 31 | 0 | manual (multi-router) | 85 % (17/20) | 0 % (0/5) | — | — |
| express-realworld | TS | — | — | 19 | 0 | manual (controllers) | 0 % (0/19) | 0 % | — | — |
| nest | TS | 124 | — | 195 | 1 | manual (2 samples) | 15 % (3/20) | 0 % (0/4) | 100 % (1/1) | — |
| fastify | TS | 6 | — | 6 | 1 | manual (examples/) | 33 % (2/6) | 33 % | 100 % (1/1) | — |
| eshop | C# | 23 | 6 | 23 | 6 | openapi (Catalog) + manual | 90 % (18/20) | 67 % (18/27) | 50 % (3/6) | 19 % (3/16) |
| clean-arch-dotnet | C# | 0 (convenção) | — | 0 | 0 | manual (Endpoints/) | — | 0 % (0/10) | — | — |
| fastapi | Py | 87 | — | 84 | 11 | manual (bigger_applications) | 100 % (20/20) | 38 % (3/8) | 64 % (7/11) | — |
| fastapi-template | Py | 19 | — | 19 | 0 | manual (api/routes) | 0 % (0/19) | 0 % | — | — |
| flask | Py | 12 | — | 12 | 0 | manual (3 exemplos) | 100 % (12/12) | 67 % (12/18) | — | — |

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
- **2026-10-14** — Fase 2 iniciada. Specs commitadas em 3 dos 15 repos → gabaritos `openapi` (o `from-openapi`
  passou a aceitar várias specs, para a união v1+v2 do eShop). Resultado: eShop Catalog P 100 % R 75 % (os 4 FN são
  restrições de rota que o literal rejeita), fiber-recipes `swagger/` P 100 % R 50 % (as 2 rotas "faltantes" foram
  fundidas com as de outra receita: o id do endpoint é por repo e o `_dedupe` fica com a primeira evidência),
  alertmanager `/api/v2` R 0 % (servidor gerado pelo go-swagger). Decisões H2-D12 e H2-D13.
- **2026-10-14** — Fase 2 concluída, **H2a fechado**. Amostra manual em todos os repos (235 rotas, as 24 chamadas)
  e recall por arquivos lidos inteiros; gabaritos em 14 repos (gorilla-mux é só lib). O instrumento ganhou
  `scope`/`source` por tipo, `category` no item esperado (por que falta) e os resumos por linguagem e por categoria.
  Achados principais: 67 das 103 rotas erradas só perderam o prefixo; `"/"` nunca vira rota (`path_of`); restrições
  de rota derrubam a rota inteira; o id do endpoint por repo funde apps (`multi-app-repo`); clientes gerados não são
  vistos (H2-D9). H2-D12 estendido às chamadas. `docs/corpus-report.md` v1 e F0.4.3a no ROADMAP.
- **2026-10-15** — H2b, Fase 4 item 1 (parte). `route_path` no `BaseScanner` (raiz só com path conhecido — app
  reconhecido por (escopo, nome) —, placeholders mascarados, padrão relativo em grupo onde o framework aceita) e
  `mask_placeholders`/`normalize_path` em `core/paths.py`; router do arquivo vence `CLIENT_RECEIVER`; ação sem
  template em controller sem `[Route]` não vira `GET /`. Diff contra a baseline julgado item a item: 74 rotas
  novas (68 certas; 6 erradas só pelo prefixo perdido dos irmãos) e 2 FPs a menos. Um erro da própria regra
  apareceu e foi corrigido no caminho (padrão relativo em `APIRouter` de callback OpenAPI → `relative_on_groups`
  só em Go/C#). Gabaritos: `category` limpo nos itens encontrados e reclassificado nos que faltam; categorias
  novas `client-named-router` e `app-not-recognized`. Sem bump de `INDEXER_VERSION`: a impressão digital do
  build já reindexa. Nova baseline `2026-10-15-baseline`. H2-D14 confirmado.
