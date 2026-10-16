# H2 — Roteiro e estado (corpus público + precisão/recall do extrator HTTP)

> Documento vivo do handoff H2. O *briefing* (o que e por quê) está em `H2-public-corpus.md`; aqui fica
> **o plano, as decisões e onde estamos**. Atualize "Onde estamos" e o "Log" ao fim de cada sessão.
> No ROADMAP geral, H2a = F0.4.3a e H2b = F0.4.3b.
>
> **Para retomar num chat novo:** ler este arquivo → `H2-public-corpus.md` → `docs/indexer-evolution.md`
> (§3 regras, §5 medição, §6 checklist) → `core/http_base.py` e `languages/<lang>/http.py` da linguagem
> em foco. Depois, rodar o corpus contra a baseline vigente (ver "Onde estamos").

## Onde estamos

- **Estado:** H2a concluído (2026-10-14). H2b: **item 1 da Fase 4 fechado (2026-10-15, em duas rodadas)** — todas as
  correções baratas do relatório + router com nome de cliente, FP do roteamento convencional e genérico aninhado
  no C#, com fixtures `route-patterns-{go,ts,py,cs}`. Recall de rotas pelos gabaritos: C# 49 → 73 %, Go 6 → 15 %,
  Python 31 → 43 %, TS/JS 6 → 9 %; chamadas C# 19 → 24 %. **Fase 3 fechada (2026-10-15):** corpus v2 com 39 repos
  (24 novos, apps reais), 38 gabaritos, relatório v2. Nos apps reais o recall de rotas despenca fora do C#
  (Go 8,7 %, TS/JS 1,7 %, Python 1,0 %; C# 73 %) e o grafo de montagem aparece em 23 dos 38 repos. **Item 3 da
  Fase 4 fechado (2026-10-15), antes do 2:** os 15 defeitos baratos do v2 + 3 achados no julgamento; nenhuma das
  categorias sobra no ranking. H2-D9 e H2-D10 decididos (itens 6 e 7). **Item 2 em curso:** etapa 1 (dentro do
  arquivo: closures e montagens do mesmo arquivo) feita em 2026-10-15 — chi 14 → 75 % de precisão, fastify,
  Hono e NodeBB sobem; `prefix-other-scope` e `mount-same-scope` saem do ranking. **Reciclagem antes da etapa 2
  (2026-10-15):** escopos, expressões de path, grafo de montagem e tipos de nó saíram do `http_base.py` para
  módulos próprios; corpus idêntico nos 39 repos. Prioridade do portfólio registrada (H2-D18). **Item 6 fechado
  (2026-10-15):** `[Route]` herdado (um nível) e classes de endpoint (FastEndpoints, ApiEndpoints), com o primeiro
  passo entre arquivos (`compose`); rotas C# P 94,6 → 100 %, R 72,9 → 93,1 % nos gabaritos. **Chamadas C# do
  item 5 (2026-10-15):** constante em template como segmentos inteiros e wrappers de cliente do próprio app;
  chamadas C# P 84 → 100 %, R 64 → 97 % (TS/JS R 31,5 → 45 % de carona); extração HTTP do corpus 672 → 98 s.
- **Incremento atual:** H2b — Fase 4, ordem do H2-D18 (ver "Próximo passo").
- **Medir agora:** `http_corpus.py --expected --baseline <baseline> --show 20` (P/R por repo, resumo por
  linguagem e por categoria). Toda mudança no extrator roda contra essa baseline e esses gabaritos.
- **Branch:** `feature/h2-corpus` a partir da `main` (f854509, já com o dispatch mergeado), na pasta
  principal do repo. O H2 é a frente principal desde 2026-10-14.
- **Indexer de referência:** 0.2.14.
- **Baseline vigente:** `~/.cache/aidd-corpus/runs/2026-10-15-v2-baseline-5/` — corpus v2, 39 repos, com as
  chamadas C# do item 5 (a `-4` é a do item 6; a `-3`, a da etapa 1 do grafo de montagem; a `-2`, a dos defeitos baratos do v2; a `2026-10-15-v2-baseline` é
  o v2 com o extrator da Fase 3; a de 2026-10-14 fica como referência do v1).
  Para editar gabaritos sem extrair de novo: `--reuse <baseline>`; para medir mudança no extrator, nunca.
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
- **Próximo passo (H2-D18):** o NSwag do item 7 — o último do .NET (`route-by-name-convention`, 10, fica para a
  convenção do projeto; sobram 2 chamadas C#: `GetFromJsonAsync("User")` de um segmento só e um `UriBuilder`).
  Depois
  o item 2, etapa 2, que é o maior ganho de Go e Python — entre arquivos (`prefix-other-file`: Go 863, Python 230:
  o router exportado por um arquivo e montado em outro, `include_router(users.router)`, `r.Mount("/api/v1",
  apiv1.Routes())`) e helpers que recebem o router (`router-as-param`, Go 102) —, com o `route-chain` do Go (216)
  logo atrás. Cada arquivo deixa um **resumo** (routers que exporta, montagens com o nome importado, rotas por
  router) e um passo depois do scan compõe os resumos — nunca as árvores (F1.13). TS por último (`global-prefix`
  238, `custom-registrar` 353, `prefix-in-client-wrapper`). O corpus tem só 7 repos C# de 39 (144 rotas esperadas,
  contra 1495 de Go): para o .NET pesar o que pesa no portfólio, ampliar a fatia C# com apps reais junto do item 6.

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
| H2-D9 | 2026-10-13 · **decidida 2026-10-15** | Clientes gerados (NSwag, openapi-generator, openapi-fetch, oazapfts): só medir no H2a e decidir com os números. **Decisão: extrair** como `HttpCall` com `via: generated-client`, um reconhecedor por gerador | v2: 371 operações em 4 clientes, 0 extraídas; no immich o SDK gerado é o único caminho do web ao servidor. Cada gerador escreve sempre a mesma forma, então o risco de FP é baixo |
| H2-D10 | 2026-10-13 · **decidida 2026-10-15** | `[Route]` herdado de classe base no ASP.NET: medir a frequência antes de decidir. **Decisão: seguir um nível** de herança — classe base do mesmo repo achada pelo nome; nome ambíguo (duas classes) não herda | v2: 26 de 60 controllers do jellyfin herdam `[Route("[controller]")]` (128 rotas sem prefixo, ações sem template perdidas); custo baixo |
| H2-D11 | 2026-10-13 | Precisão > recall: regra nova que sobe recall e derruba precisão em algum repo não entra | Um FP vira aresta errada no grafo depois do linker |
| H2-D12 | 2026-10-14 | Rota **ou chamada** com path incompleto — prefixo que o código tem (grupo, mount, `include_router`, campo/constante interpolado) e se perdeu — conta como **erro**; prefixo vindo de config/env (`BaseAddress`, `*_URL`) não conta (é do linker) | O path é a chave do linker; path errado vira ligação errada ou nenhuma |
| H2-D13 | 2026-10-14 | Medir **o que o grafo recebe** (depois do `_dedupe`), sem contornar a fusão de rotas iguais entre apps do mesmo repo | A fusão é um defeito real (evidência e handler de outro app), não um artefato da medição — vira a categoria `multi-app-repo` |
| H2-D14 | 2026-10-15 | O H2-D11 julga o erro **que a regra introduz**. Item novo errado só porque herda um defeito já categorizado dos irmãos do mesmo router (prefixo perdido em outro escopo/arquivo) é contado, mas não bloqueia a regra | Nas correções baratas, 6 das 74 rotas novas erraram assim (a regra extraiu exatamente o que está escrito); recusar a regra deixaria de fora 68 corretas e o defeito continua sendo do grafo de montagem, que corrige todas juntas |
| H2-D15 | 2026-10-15 | Gabarito com spec = **spec + rotas conferidas no código**: rota que só existe na spec (sem registro no código) sai; rota real fora da spec, achada ao conferir um item extraído, entra | A spec documenta a API pública, não tudo o que o código serve; sem isso a precisão contra o gabarito pune rotas certas (UI, redirects, health) |
| H2-D16 | 2026-10-15 | Item que precisa de mais de uma correção recebe **uma** categoria: a mais específica além do grafo de montagem (`m.Combo("/x").Get(h)` dentro de closure = `route-chain`; closure + mount em outro arquivo = `prefix-scope-and-file`) | O ranking diz qual regra destrava o quê; o grafo de montagem aparece em quase tudo e esconderia as outras |
| H2-D17 | 2026-10-15 | No resumo por linguagem, item da amostra conta na linguagem **do seu arquivo**, e o gabarito declara `language` por tipo quando difere da do repo (a UI React de um servidor Go). Cada categoria traz o **nº de repos** em que aparece | Repos mistos (backend + UI) misturavam linguagens; um repo grande (netbox, 1256 operações) não pode ranquear uma categoria sozinho |
| H2-D18 | 2026-10-15 | **Prioridade do portfólio:** .NET primeiro, Go e Python em segundo (o Python é FastAPI/Flask, não Django), TS em terceiro. A ordem da Fase 4 passa a pesar a linguagem, não só o tamanho da categoria no corpus; Django + DRF (item 8) segue adiado | O corpus pesa pelo volume dos repos públicos (Go e Python dominam as contagens), não pelo que os projetos reais usam; uma categoria pequena no .NET vale mais que uma grande só em TS |

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
ao menos um monólito grande e um serviço "de empresa". Lista confirmada e fixada em 2026-10-15 (24 repos novos,
39 no total; SHAs em `CORPUS`):

| Linguagem | Repos novos (gabarito) | O que testam |
|---|---|---|
| Go | gitea (spec), mattermost (spec em fragmentos), kratos (spec), argo-cd (spec), gotify (spec), go-feature-flag (spec), go-kit-examples (manual) | `Group` com closure, `Combo`, subrouters gorilla em campos, router por tipo (`RouterAdmin`), grpc-gateway, echo, httprouter, go-kit |
| TS/JS | immich (spec), NodeBB (spec multi-arquivo), Ghost, express-boilerplate, fastify-demo, hono-examples, taxonomy (manual) | Nest real com prefixo global, helpers de registro, `lazyUse`, autoload por pasta, Hono, Next.js por arquivo, jQuery no cliente |
| C# | eShopOnWeb, eShopSupport, ardalis/CleanArchitecture, jellyfin, bitwarden/server (manual) | minimal API, controllers com `[Route]` herdado, FastEndpoints, ApiEndpoints, clientes tipados |
| Python | zulip (spec), netbox (spec), dispatch (spec), aiohttp-demos, CTFd (manual) | Django urlconf, DRF routers, `include_router(prefix=)` entre arquivos, aiohttp, flask-restx |

Fora: hashicorp/vault (licença BUSL; o fork openbao não tem spec commitada) e **grafana**, que era
candidato e não roda: a extração do repo inteiro (24 mil arquivos) é morta por memória a 7,7 GB no Docker
Desktop — achado de escala do indexer, registrado no relatório e no ROADMAP como **F1.13** (repos grandes).

- [x] Selecionar e confirmar a lista; fixar SHAs; gabaritos onde houver spec — e lista à mão nos demais
- [x] Rodar e estender `corpus-report.md` (seção v2)

### Fase 4 — evoluir o extrator (ordem definida pelo ranking do relatório)
Por categoria: fixture → mudança em `languages/<lang>/http.py` (ou `core/http_base.py` se for comum) →
`pytest` → corpus `--baseline` (nenhum repo pode regredir, H2-D11) → tabela §3 do guia → nova baseline.
Um commit por categoria. Ordem do relatório v1, **revista pelo v2 em 2026-10-15** ("What H2b should do, in order
(v2)" no relatório; categorias e contagens lá):
- [x] **1. Correções baratas e gerais**
  - [x] *(2026-10-15)* `root-route-dropped` (raiz só com path completo conhecido: app ou grupo com prefixo),
    `route-constraint-syntax` (placeholder mascarado na validação; `?` opcional antes da query), `no-leading-slash`
    (`relative_on_groups` em Go/C#), `client-named-router` (router do arquivo vence o nome) e o FP do roteamento
    convencional do ASP.NET — fixtures `route-patterns-{go,ts,py,cs}`
  - [x] *(2026-10-15, 2ª rodada)* `optional-segment-syntax`, `query-in-template`, `method-default` (`fetch` = GET), `test-client-in-source`,
    `verb-alias` (`Del`) e `nested-generic-callee` (C# `<List<T>>`, achado no caminho)
- [ ] **2. Grafo de montagem** — no v2 aparece em 23 dos 38 repos com gabarito (200 wrong, 1837 missed).
  - [x] *(2026-10-15)* etapa 1, dentro do arquivo: regiões de closure (`Route`/`Group` com func, `register(fn,
    {prefix})`), montagens do mesmo arquivo (`use`, `route`, `Mount`, `include_router`, `register_blueprint`,
    `basePath`), raiz de sub-router montado, `With`/`Use` — fixtures `route-patterns-*/…/mounts`
  - [x] *(2026-10-15)* reciclagem antes da etapa 2, sem mudar comportamento: `core/http_scope.py` (escopos e
    ligações de nomes), `core/http_expr.py` (expressões de path), `core/http_mounts.py` (o grafo de montagem do
    arquivo, a peça que a etapa 2 compõe entre arquivos), `core/http_nodes.py` (tipos de nó); `http_base.py` fica
    com o scanner e os ganchos por linguagem
  - [ ] etapa 2: entre arquivos e funções (resumo por arquivo), prefixo global

  Ordem original:
  mesmo escopo (`app.use('/api', router)` ao lado das rotas, Hono `route`/`basePath`) → mesmo arquivo (closures
  `r.Route`/`m.Group(..., func)`, `register(fn, {prefix})`) → prefixo global (`setGlobalPrefix`) → entre arquivos
  (imports, constantes/enums, campos de struct, funções-helper chamadas dentro de grupos, `include_router(prefix=)`).
  Passo pós-scan em `integrations.py`, `confidence: heuristic` → bump `INDEXER_VERSION` e `SCHEMA.md` se o nó ganhar campo.
  Entre arquivos, trabalhar com um **resumo por arquivo** (quem monta o quê, com que prefixo), não com as árvores de
  outros diretórios — restrição do F1.13 (repos grandes)
- [x] **3. Defeitos baratos do v2** *(2026-10-15, feito antes do item 2)* — precisão: `variable-other-scope`,
  `call-taken-for-route` (jQuery `$.get(url, cb)`), `mount-as-route`, `route-taken-for-call`, `build-artifact`,
  `non-http-verb`; recall: `const-concat`, `multiline-receiver`, `mime-like-head`, `const-base-url`,
  `method-keyword`/`method-variable`, `verb-alias` (`del`), `default-mux-function`, `group-chain`,
  `aiohttp-router`; achados no julgamento: variável interpolada que lê o próprio valor anterior, `x += e`, e o
  contraexemplo do wrapper genérico (constante de módulo em template fica placeholder). Sobra 1 item
  (`data-taken-for-handler`, gotify)
- [ ] **4. `route-chain`** (gitea `Combo`, builders gorilla, express `router.route()`)
- [ ] **5. Chamadas:** `field-in-interpolation` (TS e C#), `url-object-builder` (todas as linguagens), `request-config-object`
  - [x] *(2026-10-15)* C#: constante interpolada como segmentos inteiros (de path no começo; de uma palavra entre
    barras), nunca num wrapper genérico (variável de nome de path no template); chamada interpolada que já é path
    (`CombineUri`); wrappers de cliente do app (`HttpService.HttpGet(uri)`) por fato + `Pending` + `compose`, com o
    tipo declarado do receiver. Sobra em TS: o `adminUrl` do ghost (`window.location`) e os wrappers do gitea
    (precisam de tipo do receiver em TS)
- [x] **6. C#:** herança de `[Route]` (H2-D10, aceito: um nível) e classes de endpoint (FastEndpoints, ApiEndpoints)
  *(2026-10-15)* — primeiro passo entre arquivos (`facts` + `Pending` → `CsScanner.compose`); constante de classe
  por `Classe.NOME`; `nameof(X)` e variável local em interpolação do C#; `[action]` sem `Async`. Fixtures em
  `route-patterns-cs` (herança entre arquivos, base ambígua, FastEndpoints, ApiEndpoints)
- [ ] **7. Clientes gerados** (H2-D9, aceito): oazapfts (immich), openapi-generator Go/TS (kratos), NSwag e
  openapi-fetch (v1) — `via: generated-client`, fixture por gerador
- [ ] **8. Scanners novos, quando um portfólio pedir:** Django + DRF (maior lacuna isolada: 1420 em 2 repos),
  rotas por arquivo do Next.js, flask-restx
- [ ] **9. `test-app-folder`** (agora em 4 repos): exclusão por repo no `atlas.yaml` é a resposta mais segura
- [x] Decidir H2-D9 e H2-D10 — *(2026-10-15)* as duas recomendações do relatório aceitas (itens 6 e 7)

### Fase 5 — fechamento
- [ ] ROADMAP: F0.4.3b `[x]`; gaps encaminhados (base URL → F0.5 linker; spec como fonte → F2.1; resto → F1 ou limitação)
- [ ] Guia: §3 (regras novas com o sintoma) e §5 (como usar `--expected`/`--baseline`)
- [ ] Dívidas registradas na reciclagem de 2026-10-15 (nenhuma bloqueia a Fase 4):
  - catálogo de frameworks como dado (verbos, nomes de registro, receptores de cliente), extensível pelas
    convenções do projeto — junto dos itens 7/8, quando entrar o primeiro reconhecedor novo
  - os scanners leem `CLIENT_RECEIVER` direto em vez de pedir o cliente às convenções
  - limiares fixos no `built_bundle` (detecção de artefato de build)
  - um conjunto de repos fora do ajuste (*hold-out*), medido só no fechamento, para checar sobreajuste ao corpus
  - na etapa 2, reaproveitar a resolução de imports do `resolve.py` em vez de uma segunda
  - custo do HTTP no netbox: 49 s de 107 s, com 0 rotas e 0 chamadas (zulip 17 s de 47 s) — perfilar junto do F1.13
- [ ] Pendências do item 6, fora do corpus atual (medir quando a fatia .NET crescer):
  - linker: rotas ASP.NET casadas sem distinção de caixa (F0.5) — o extrator mantém `[controller]` em minúsculas
    porque o linker compara exato
  - actions herdadas de controller base abstrato (CRUD genérico) — 0 no corpus
  - FastEndpoints: `RoutePrefix` global e `Group<T>()` — 0 no corpus
  - herança de `[Route]` em mais de um nível (H2-D10 decidiu um)
- [ ] Pendências das chamadas C# (item 5):
  - [x] *(2026-10-16)* **fora do HTTP:** chamada genérica com receiver (`obj.Method<T>(...)`) vira call site; tipo de
    pacote no receiver só alcança extensão do repo (ROADMAP, log de 2026-10-16)
  - `URL_LITERAL` aceita qualquer caractere depois do host (`/x/{param}{param}god_mode=true` passaria)
  - wrappers de cliente em TS (gitea, 16) e Python: o mesmo caminho, com o tipo do receiver de cada linguagem

## Taxonomia de erros

As categorias medidas, com exemplos, o que exigiriam e o destino, estão em `docs/corpus-report.md` ("Gaps by
category" do v1 e do v2); o `--expected` as reconta a cada execução a partir do campo `category` dos gabaritos.
Das categorias previstas no plano, o v2 viu `route-by-file-path`, `django-urlconf`, `inherited-route-attr` e
`generated-client` (medido, não é categoria de gabarito); `lowercase-verb-ambiguous` apareceu como `non-http-verb`
(`Get(key)` de um cache). Seguem fora da métrica:

| Categoria | Exemplo | Destino |
|---|---|---|
| `runtime-url` | URL montada sem literal, link lido da página | fora da métrica (H2-D5) |
| `base-url-in-config` | `BaseAddress = new Uri(...)`, `*_URL`, `globalSettings.X.BaseUrl` | linker F0.5 |

## Números

Tabela do **v1** (2026-10-14), mantida como referência; os números atuais saem do `--expected`, a comparação
v1 → correções baratas está no relatório ("Update: the cheap fixes") e as tabelas do corpus v2 (39 repos, por
linguagem e por repo) estão em "v2: the widened corpus".

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
- **2026-10-15** (2ª rodada) — H2b, Fase 4 item 1 fechado. As cinco correções baratas menores (query fora da validação do
  template, `fetch` = GET, `TestClient` não é chamada de saída, grupo opcional do Express 5, `Del`) e uma achada no
  caminho: genérico aninhado no callee C# (`GetFromJsonAsync<List<T>>`) fazia a chamada sumir — e tinha escondido
  `GET /api/webhooks` também do gabarito do eShop (o grep da listagem tinha o mesmo ponto cego); gabarito corrigido.
  Diff julgado item a item: 4 FPs de `TestClient` a menos, 1 método corrigido, 3 rotas normalizadas, 1 rota nova
  (`DELETE` do alertmanager, sem `/api/v1` como as irmãs) e 10 chamadas novas no eShop (2 certas; as do catálogo
  sem o `api/catalog/` do campo interpolado, como as irmãs) — H2-D14: precisão de chamadas C# no gabarito
  50 → 40 %, recall 19 → 24 %. Amostra: itens que deixaram de ser extraídos saíram; os do mesmo local com path ou
  método corrigido foram atualizados. Nova baseline `2026-10-15-baseline-2`.
- **2026-10-15** — H2b, Fase 3 fechada. 24 repos novos fixados por SHA (39 no total): Go (gitea, mattermost, kratos,
  argo-cd, gotify, go-feature-flag, go-kit-examples), TS/JS (immich, NodeBB, Ghost, express-boilerplate, fastify-demo,
  hono-examples, taxonomy), C# (eShopOnWeb, eShopSupport, ardalis/CleanArchitecture, jellyfin, bitwarden), Python
  (zulip, netbox, dispatch, aiohttp-demos, CTFd). grafana saiu: a extração do repo inteiro é morta por memória a
  7,7 GB no Docker Desktop (achado de escala do indexer). Gabaritos: spec onde há (11 dos novos, 14 no total; mattermost em
  fragmentos, NodeBB multi-arquivo — o `from-openapi` passou a seguir `$ref` externo), lista lida na fonte nos
  demais; amostra de 20 rotas + 20 chamadas julgada na fonte em cada repo. Decisões H2-D15 (spec + rotas conferidas
  no código), H2-D16 (uma categoria por item: a mais específica além do grafo de montagem) e H2-D17 (linguagem por
  arquivo no resumo; nº de repos por categoria). Instrumento: `--reuse`, `language` no gabarito, coluna `repos`.
  Extrator intocado: os 15 do v1 idênticos à baseline anterior; extração do v2 idêntica à usada nos gabaritos.
  Achados: o grafo de montagem em 23 de 38 repos (200 wrong, 1837 missed); defeitos baratos novos (`const-concat`,
  `multiline-receiver`, `variable-other-scope`, `mime-like-head`, jQuery `$.get` como rota, mount como rota);
  H2-D9 com 371 operações em 4 clientes gerados (0 extraídas); H2-D10 com 26 de 60 controllers do jellyfin herdando
  `[Route("[controller]")]` (128 rotas sem prefixo). Correção de datas: o trabalho registrado como 2026-10-16 foi
  feito em 2026-10-15 (2ª rodada); a baseline passou a se chamar `2026-10-15-baseline-2`. Nova baseline
  `2026-10-15-v2-baseline`.
- **2026-10-15** — H2b, Fase 4 item 3 fechado (antes do item 2). Os 15 defeitos baratos do v2, cada um com caso
  nas fixtures `route-patterns-*`: constantes só do módulo/classe e nome procurado da função mais interna para
  fora (parâmetro encerra), constante montada por `+` e com URL absoluta, `$`/`jQuery` como cliente, padrão com
  `/` final no `ServeMux` como montagem, argumento espalhado desembrulhado, bundle de build fora da extração HTTP,
  segmento sem nome não é path, callee sem espaços, MIME só com dois tokens, método de keyword e de variável,
  `del`, mux padrão, prefixo pela cadeia `Group().Use()`, aiohttp. O julgamento do diff achou 3 defeitos das
  próprias regras e os corrigiu no caminho: a chamada do CTFd que lia o próprio valor anterior em template (variável
  local interpolada passou a ser resolvida — constante de módulo não, contraexemplo do alertmanager), `x += e`
  (path e método do mesmo ramo; com base desconhecida só vale o trecho com segmento nomeado — chi `FileServer`).
  Diff contra `2026-10-15-v2-baseline` julgado item a item: rotas −37 +49, chamadas −54 +186; o que errou
  entre os novos só herda defeito já categorizado das irmãs (7 rotas do kratos sem `/admin`, 127 chamadas de
  argo-cd e NodeBB sem o prefixo do wrapper — H2-D14). Gabaritos: 6 chamadas reais que faltavam (gotify,
  kratos), recategorização dos que mudaram de causa, amostras sincronizadas e julgadas de novo. Por linguagem
  (gabarito): chamadas C# P 62 → 84 %, R 48 → 64 %; chamadas Go R 24 → 32 %; chamadas TS/JS R 22 → 31 %; rotas
  Python P 27 → 38 %. Decisões H2-D9 e H2-D10 aceitas (itens 6 e 7 da Fase 4). Item novo no ROADMAP: **F1.13**
  (repos grandes). Nova baseline `2026-10-15-v2-baseline-2`.
- **2026-10-15** — H2b, Fase 4 item 2, etapa 1 (dentro do arquivo). `prefix_for` (região de closure via o gancho
  `region_of` de cada linguagem, senão o grupo), routers identificados por (escopo que liga o nome, nome), arestas de
  montagem do arquivo e `finish()` no fim de cada arquivo (cadeias de montagem; a raiz de sub-router fica pendente
  — `MountedRoot` — e só vira rota se montada). Diff julgado contra `2026-10-15-v2-baseline-2`: chi, fastify, Hono e
  NodeBB certos (ou só sem prefixo de outro arquivo); Ghost ganha o prefixo dos sub-routers do arquivo; gitea
  −440 +970, com as rotas web completas (o router web é montado em `/`) e, na API, 247 de 282 batendo com a spec se
  somado o `/api/v1` que vem de `routers/init.go` — 231 itens do gabarito passam de `prefix-scope-and-file` a
  `prefix-other-file`; a precisão Go contra os gabaritos cai de 21,1 % para 18,4 % só por isso (H2-D14). Achado no
  caminho: `r.With(mw).Get(...)` é registro no próprio `r`. Julgamento do v1 corrigido: chi `router-walk` `PUT /ping`
  estava certo. Nova baseline `2026-10-15-v2-baseline-3`.

- **2026-10-15** — H2b, reciclagem antes da etapa 2 do item 2 (sem mudança de comportamento). O `http_base.py`
  (800 → 392 linhas) foi dividido: `http_scope.py` (`Scopes`: ligação de um nome do escopo mais interno para fora, sem
  entrar em outras funções, com cache de `binding_scope`), `http_expr.py` (`PathExpressions`: `path_of` despachando
  por tipo de nó), `http_mounts.py` (`MountGraph`: arestas, rotas por router, `prefixes` e `apply`) e
  `http_nodes.py` (os tipos de nó comuns). Os scanners passaram a usar `callee_of`/`split_callee` e
  `add_endpoint(..., router=...)`, que acha o prefixo e registra a rota no grafo sozinho. `pytest` 164 passed,
  corpus idêntico a `2026-10-15-v2-baseline-3` nos 39 repos (ids, handlers e callers); a saída do corpus agora
  mostra o tempo do HTTP por repo (`(http Xs)`). Prioridade do portfólio registrada como H2-D18 (.NET > Go/Python >
  TS), com a ordem da Fase 4 proposta em "Próximo passo". Dívidas adiadas na Fase 5. A baseline não muda.
- **2026-10-15** — H2b, Fase 4 item 6 (C#), primeiro sob o H2-D18. Primeiro passo entre arquivos: cada arquivo
  publica fatos (`out.publish`) e deixa rotas `Pending`; `BaseScanner.compose` roda uma vez por linguagem depois do
  scan, sem árvores (F1.13). `[Route]` da classe base, um nível, achada pelo nome (nome ambíguo não herda; ação sem
  template só com o prefixo herdado); FastEndpoints (`Configure()`) e Ardalis.ApiEndpoints. Constante de classe
  também por `Classe.NOME`, nome com dois valores na pasta só vale no próprio arquivo (o ardalis tem um `Route` em
  cada request). No julgamento: `nameof(X)` em interpolação, e as chaves da interpolação do C# (nós nomeados)
  impediam a regra da variável local interpolada. Tentado e revertido: `[controller]` na caixa declarada — o teste
  de ponta a ponta do .NET quebra porque o linker compara exato (pendência F0.5). Diff contra `-3`: só jellyfin
  (−128 +162), ardalis (+19) e eshop-on-web (+1), todos certos; nenhuma chamada muda. Rotas C# nos gabaritos:
  P 94,6 → 100 %, R 72,9 → 93,1 %; jellyfin P/R 33/25 → 100/100 %. Python do portfólio = FastAPI/Flask (H2-D18).
  Nova baseline `2026-10-15-v2-baseline-4`.
- **2026-10-15** — H2b, Fase 4 item 5, parte C# (H2-D18). Constante interpolada vale como segmentos inteiros: a de
  path no começo do template (`$"{remoteServiceBaseUrl}items/{id}"`), a de uma palavra entre barras
  (`` `/${resource}/${id}` ``, guardada à parte para nunca virar path sozinha) — e nunca num wrapper genérico, um
  template com variável de nome de path (a primeira versão fez lixo do `${GHOST_URL}/ghost/api/admin/${endpoint}`
  do ghost, pego no diff). Chamada interpolada que já é path (`CombineUri`, família do `Path.Combine`; base
  desconhecida sai do join). Wrappers de cliente do app: o método que monta o path em volta de um parâmetro publica
  `Classe.Método` (e sob as interfaces); a chamada num receiver de tipo declarado conhecido fica `Pending` e
  `compose` monta o path — primeiro uso do passo entre arquivos para chamadas. Custo: a primeira medida mostrou o
  netbox em 445 s de HTTP; `Scopes` passou a indexar as atribuições uma vez por escopo e o alias do aiohttp só é
  procurado onde existe — saída idêntica, HTTP do corpus 672 → 98 s, execução 23 → 13 min. Diff julgado (8 repos,
  tudo certo): dispatch +273, eshop, eshop-on-web (+6 pelo `HttpService`), eshop-support, mattermost, zulip,
  argo-cd, ghost. Chamadas C#: P 84 → 100 %, R 64 → 97 %; TS/JS: P 44 → 60 %, R 31,5 → 45 %. Achado fora do HTTP:
  `obj.Method<T>()` não é call site no C#. Nova baseline `2026-10-15-v2-baseline-5`.
- **2026-10-16** — Fora do HTTP, achado no item 5: chamada genérica com receiver no C# vira call site, e o resolver
  deixa de chutar homônimo quando o tipo do receiver é de pacote (só extensão do repo que estenda o tipo e caiba nos
  argumentos). Medido no grafo dos 4 repos .NET do corpus: bitwarden −5.684 +12.244 arestas, jellyfin −1.459 +367;
  o que sai é chute, o que entra é `receiver-type` e extensões do repo. Detalhe no log do ROADMAP.
