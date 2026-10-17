# Guia de evolução do indexador (`indexer/`)

> Documento de trabalho em PT (como o ROADMAP). Público: quem vai **melhorar a extração** — símbolos,
> chamadas, e principalmente os **candidatos de integração HTTP** (`core/integrations.py` + `languages/<lang>/http.py`). Os handoffs
> em `docs/handoffs/` apontam para cá; leia este primeiro.

## 1. O que o indexador é e o que não é

- Transforma repositórios em um grafo (Neo4j, database `atlas`): micro (Repo → Module → File → Symbol,
  `CALLS`, `IMPORTS`) e macro (Service → `HttpEndpoint`, `HttpCall` → futuro `CONSUMES`). Esquema:
  `neo4j/SCHEMA.md`. Ids determinísticos: `aidd_indexer/core/ids.py`.
- **Determinístico**: tree-sitter + heurísticas. LLM nunca é parser (princípio no ROADMAP). Se um padrão não
  dá para reconhecer estaticamente, a resposta certa é *registrar a limitação*, não chutar.
- Tudo que o indexador grava carrega `tenant/repo/ref/commit_sha/indexed_at` e, no macro, `evidence`
  (`repo:arquivo:linha`) e `confidence`. Nada de valor de segredo; só nome de env var.
- Roda dentro da imagem `aidd-indexer` (Docker), com as gramáticas pré-baixadas
  (`TREE_SITTER_LANGUAGE_PACK_CACHE_DIR=/opt/tslp-cache`, `AIDD_GRAMMAR_OFFLINE=1`). O `refresh`
  agendado reindexa a cada 15 min e **reindexa tudo quando `INDEXER_VERSION` muda**.

## 2. Mapa do código

Organização por [ADR-003](adr/ADR-003-language-modules.md): **`core/`** (pipeline genérico, nunca
pergunta "qual linguagem?"), **`languages/<lang>/`** (o que é específico de cada linguagem, atrás do
contrato `LanguageSupport`) e **`conventions/`** (regras do *seu* padrão de desenvolvimento, plugáveis).

| Arquivo | Papel |
|---|---|
| `cli.py` | comandos `plan / bootstrap / refresh / index / status / wipe / selftest / serve`; `extract_tree()` é o pipeline por repo; `extract_and_resolve()` aplica as convenções |
| `core/discovery.py` | quais arquivos entram (gerados por sufixo ficam de fora, salvo cliente HTTP gerado — o `.g.cs` do NSwag, pelo cabeçalho); linguagem por extensão via `languages.by_extension()`; módulos por manifesto (declarados em cada `LanguageSupport.manifests`) + `discover_modules()` de cada linguagem (pacotes Go) |
| `core/extract.py` | `FileExtractor`: parse tree-sitter + `queries.scm` → `SymbolInfo`, `CallInfo`, `ImportInfo`; delega a `LanguageSupport` nomes qualificados, visibilidade, docstrings, bindings de import e marcadores de entry point; `load_language()` com `GRAMMAR_ERRORS` |
| `core/resolve.py` | `CALLS`: candidatos pelo nome do callee, **código de produção nunca aponta para símbolo de teste**, depois tipo estático do receiver (`LanguageSupport.resolve_receiver` → método no tipo ou em `supertypes` do repo = `receiver-type`; interface com `implementations` único = `receiver-type-impl` — em Go, pelo conjunto de métodos, sem contar fakes/mocks; em C#, o registro no DI decide quando há mais de um (`AddScoped<I, Impl>()`; cadeia `Decorate<I, D>()`: de fora → o decorator mais externo, de dentro de um decorator → o próximo para dentro); tipo conhecido sem o método = **sem aresta**, salvo quando o tipo tem base fora do repo: aresta para o tipo e seu implementador único com o nome do método = `inherited`/`inherited-impl`; tipo conhecido **de pacote** — e genérica num receiver de tipo desconhecido — só alcança método de extensão do repo que estenda o tipo e caiba nos argumentos, `LanguageSupport.external_receiver`/`is_extension_method`); antes de tudo, despacho de mediator declarado pela convenção (`dispatch:` → `core/dispatch.py`: `bus.SendAsync(new X())` → `Handle` de quem implementa `ICommandHandler<X, ..>` = `dispatch`) → same-file → same-module → unique-name (`-ambiguous` quando sobra mais de um); sobrecargas pela contagem de argumentos (`LanguageSupport.arity`/`call_arg_count`: opcionais e `params`/variádicos alargam a faixa) — com receiver tipado escolhe a sobrecarga (mesma aridade = todas, `-ambiguous`); no casamento por nome só corta palpites, a aresta continua `-ambiguous`; `IMPORTS` via `resolve_import()` → File/Module/Package; `link_symbols()` por linguagem |
| `core/deps.py` | manifestos → `provides`/`requires` por repo (`LanguageSupport.manifest_deps`: go.mod, .csproj, package.json, pyproject/requirements), nomes normalizados por ecossistema; vão para o `Snapshot` e o linker cruza por tenant em `DEPENDS_ON` (Service→Service) — F0.5.1 |
| `core/integrations.py` | orquestra os **candidatos HTTP**: contexto por diretório (e a visão do repo, `RepoView`, ligada a cada um) → `LanguageSupport.http_scanner` de cada arquivo → `compose` de cada linguagem (o que atravessa arquivos) — ver §3 |
| `core/http_base.py` | `BaseScanner`: onde a rota mora (`prefix_for`, `region_of`, `route_path`, `route_chain`, `mount`/`finish`; entre arquivos, `compose` sobre os `facts` que cada arquivo publica e as rotas `Pending`; os routers que outros arquivos nomeiam — `global_of`, por linguagem —, os imports do arquivo — `read_imports` — e as constantes dos pacotes importados — `foreign_const`), rota × cliente (`is_handler_like`), handlers, gravação (`add_endpoint`, `add_call`); `PackageContext`, tabela `OUTBOUND`, `split_callee`/`callee_of`; `convention_call()` aplica os `ScanPatterns` da convenção (`route_patterns`/`client_patterns`, em `core/scan_patterns.py`) antes das tabelas genéricas; handler embrulhado em middleware/opções resolve pelo argumento mais interno que é função do repo |
| `core/http_expr.py` | expressão → path e método (`PathExpressions`, misturado ao `BaseScanner`): `path_of` por tipo de nó (string/template, nome, concatenação, chamada, objeto de request, `new Uri`, `x += e`, o `url.URL` do Go pelo `u.Path`), `method_from_args`; `collect_constants` (constantes do diretório) |
| `core/http_scope.py` | escopos e ligações de nome de um arquivo (`Scopes`): da função mais interna para fora, parâmetro encerra a busca, `x += e`; as atribuições de cada escopo são indexadas uma vez (uma busca não percorre o escopo de novo); `scope_id`, `in_function` |
| `core/http_mounts.py` | grafo de montagem (`MountGraph`, `RouterKey`, `MountedRoot`): no fim do arquivo, `settle` prefixa as rotas pelas montagens do arquivo e devolve o que atravessa arquivos — rotas à espera de um router global (`var:`/`ret:`/`param:`/`field:`) e as arestas de cada router global até outro ou até o topo (`TOP`, ou `APP` quando é a aplicação); `compose` segue essas arestas para cada rota à espera |
| `core/http_view.py` | `RepoView`: o que um scanner sabe do resto do repo — as constantes de cada diretório e para onde um import aponta (arquivo ou diretório de pacote), pelo `resolve_import` de cada linguagem, o mesmo do `IMPORTS` |
| `core/http_nodes.py` | os tipos de nó tree-sitter que o extrator HTTP lê, por categoria (strings, chamadas, nomes, funções, handlers…), e `member` (`x.f` em qualquer linguagem) |
| `core/paths.py` | `normalize_path`, `path_key`, `unquote`, `expand_alternatives` (segmento `{t:teams\|channels}` → um path por palavra), regexes de path — usados pelo extrator, pelo `graph.py` e pelo MCP |
| `core/linker.py` | **F0.5**: `link(calls, endpoints)` puro (exact → suffix → desempate por hint → ambíguo = nada; rotas de `aspnet`/`aspnet-minimal`/`fastendpoints` sem distinção de caixa, como o framework) + `consumes_rows`/`called_from_rows`; `GraphWriter.link_tenant` lê/grava |
| `core/model.py` | dataclasses de tudo + `ExtractionResult` (inclui `violations`) |
| `core/graph.py` | `GraphWriter.write()`: MERGE idempotente, `EXPOSES{ref}`/`HANDLED_BY{ref}`, `Violation`/`HAS_VIOLATION`, GC de órfãos por `commit_sha`, `IndexRun` |
| `core/planner.py` / `core/manifest.py` / `core/gitinfo.py` | `atlas.yaml` (tenants, sources, refs, areas, **conventions**) → plano de (repo, ref, sha); `git archive` por ref |
| `languages/__init__.py` | registro: `REGISTRY`, `by_id`, `by_extension`, `parseable()`, `grammars()`; `_MODULES` lista as pastas |
| `languages/base.py` | contrato `LanguageSupport` (identidade · descoberta · símbolos · resolução · http) e `ResolveContext` |
| `languages/<lang>/queries.scm` | padrões `def.<kind>`, `call`, `import` — compilados padrão a padrão (um inválido é pulado com warning) |
| `languages/<lang>/symbols.py` | a subclasse de `LanguageSupport` + `LANGUAGES = [...]` (typescript registra `typescript`, `tsx`, `javascript`). Go e C# implementam também `file_facts`, `call_receiver` e `resolve_receiver` (Go: receiver do método, parâmetro, `x := T{}`, `x := pkg.New()` inclusive retorno múltiplo, campos de struct e campos promovidos por embedding; C#: campos/propriedades/parâmetros/locais/`base.`, membros herdados) e C# ainda `supertypes` + `implementations` (interface → implementador único) |
| `languages/<lang>/http.py` | o scanner HTTP da linguagem (`GoScanner`, `TsScanner`, `CsScanner`, `PyScanner`) e suas tabelas de registradores |
| `conventions/base.py` | contrato `Convention` (`prepare(ctx)`, `role_of`, `layer_of`, `target_of`, `is_entry_point(symbol, file, owner)`, `check`, `describe`) e `ConventionContext` (`rv.namespace_files`: namespace C# → arquivos que o declaram) |
| `conventions/declarative.py` | `convention.yaml` → `Convention` (**papéis** por forma da declaração — `roles:` com `extends`/`name`/`declares`, inclusive bases do próprio repo → `Symbol.role`; **arquiteturas** — `architectures:` com `layers` por layout e `detect` pelos módulos, `together: ["{svc}.Api", "{svc}.Core"]`, ou forçada por `options.architecture`; camadas por glob, e arquivo que o layout não posiciona herda a camada dos seus papéis; alvos, entry points por assinatura, por tipo dono — `members_of` — ou por papel — `entry_points.roles` —, regras `forbid_import` / `endpoints_only_in` / `http_calls_only_in` / `roles_in`; `using` de namespace conta pela camada dos arquivos que o declaram) |
| `conventions/__init__.py` | `load(specs, repo)` (arquivo, entry point `aidd.conventions` ou `pacote.modulo:Classe`) e `apply()` |
| `../conventions/<nome>/` (em `indexer/`) | extensões de convenção empacotadas (`pyproject` + entry point `aidd.conventions`), instaladas pelo `Dockerfile`; hoje `dotnet-praticis` |
| `mcp/server.py` | MCP `atlas` (leitura): `atlas_status, repo_map, find_symbol, who_calls, symbol_context, http_map, who_consumes, impact_of, ref_diff, violations, cypher_readonly` (este só com tenant fixo, ou `ATLAS_RAW_CYPHER=on`: Cypher livre não fica preso a um tenant); `atlas_status.refresh` diz quando o refresher parou — perguntas douradas em `docs/golden-questions.md` |
| `scripts/http_corpus.py` | corpus público de calibração do extrator HTTP (§5) |
| `tests/` | fixtures golden (HTTP; e, nas que reproduzem um padrão, camadas/entry points/violações/`CALLS`/gaps pela convenção) + `test_conventions.py` (costura das convenções) + `test_linker.py` (regras + pares `go-http-mix` → `go-billing-api` e `csharp-praticis-reports` → `csharp-praticis-todos`) + `test_mcp_protocol.py` (tools do MCP com store fake); `conftest.py` põe as extensões de `indexer/conventions/*` no `sys.path` |

Pipeline de um repo (`cli.extract_tree` → `extract_and_resolve`): `list_files` → `discover_modules` →
`build_files` → para cada arquivo parseável `FileExtractor.run()` → `extract_http(repo, extractors)` →
`Resolver.run()` → `conventions.apply()` (se houver) → `GraphWriter.write()`.

## 3. Como o extrator HTTP decide

Três passes sobre os `FileExtractor`s (que já têm `tree`, `src`, `symbols`, `_enclosing_symbol()`):

1. **Contexto por diretório** (`PackageContext`): constantes de rota **do módulo ou da classe** (`const routeX = "/v1/x"`,
   `ORDERS_PATH = '/v1/orders'`, base URL com path `"https://host/v1"`, e as montadas de outras —
   `RouteItem = RouteCollection + "/{id}"`, resolvidas no primeiro uso por `route_const`) e nomes de env var que
   parecem base URL (`*_URL`, `*_HOST`, `*_ENDPOINT`). Locais de função não entram: são lidas por `Scopes.binding`.
   Constante de classe vale também por `Classe.NOME`; nome com dois valores na pasta é ambíguo (só o do próprio
   arquivo vale).
2. **Scanner por linguagem** (`languages/<lang>/http.py`: `GoScanner`, `TsScanner`, `CsScanner`, `PyScanner`),
   todos herdando de `core/http_base.BaseScanner` (`scan()` = `run()` da linguagem + `finish()`), que concentra as
   peças reutilizáveis — algumas em módulos próprios (`http_expr`, `http_scope`, `http_mounts`):
   - `path_of(node, lenient)`: transforma uma expressão em template de path — literal, **variável**
     (`Scopes.binding`: última atribuição anterior, da função mais interna para fora, sem entrar no corpo de outras
     funções; um parâmetro para a busca — o valor é do chamador), constante do diretório, concatenação,
     `Sprintf`/f-string/`$""`/`` `${}` `` (uma variável local interpolada é resolvida como na concatenação; constante
     do módulo interpolada fica placeholder), `x += e` (o valor anterior mais `e`),
     `path.Join`. `lenient=True` (só em contexto de cliente HTTP) aceita `items/{id}`, `{base}catalogBrands` e
     `base + 'message'`.
   - `is_handler_like(node)`: **a regra que separa rota de chamada de saída** — o argumento depois do
     path é função/seletor/identificador (rota) ou dado/string/nil (cliente).
   - `method_from_args`, `resolve_handler` (nome → `Symbol` do mesmo arquivo), `add_endpoint`,
     `add_call` (descarta path sem segmento literal), `_record_group` (prefixos de `Group/MapGroup/APIRouter(prefix=)`).
   - **Grafo de montagem do arquivo** (H2b, Fase 4 item 2, etapa 1): `prefix_for(receiver, nó)` = prefixo da região
     de closure que envolve o registro (`region_of`, gancho por linguagem: chi/fiber `Route("/x", func(r) {})`,
     chi `Group(func(r) {})`, gitea `m.Group("/x", func() { m.Get(..) })`, fastify `register(fn, {prefix})`) ou
     do grupo. Montagens do arquivo (`app.use('/api', router)`, Hono `route('/x', sub)`, chi `Mount("/x", sub)`
     — inclusive o router que uma função do arquivo devolve —, `include_router(r, prefix=)`,
     `register_blueprint(bp, url_prefix=)`) viram arestas entre routers identificados por (escopo que liga o
     nome, nome); `finish()` prefixa, no fim do arquivo, o que foi registrado em cada router com cada cadeia de
     montagens acima dele. A raiz de um sub-router fica pendente (`MountedRoot`) e só vira rota montada com
     prefixo ou na própria aplicação.
   - **Grafo de montagem entre arquivos** (etapa 2, Go, Python e TS/JS): um router que outro arquivo pode nomear tem
     um id global — variável do módulo/pacote (`var:`), o router que uma função devolve (`ret:`, método por
     `Tipo.Metodo`, closure atribuída a variável pelo nome dela), parâmetro de função (`param:`) ou campo de struct
     (`field:`, Go). A rota num router desses espera a composição; o arquivo publica as arestas dos seus routers
     globais e as montagens de routers de fora — `r.Mount("/api/v1", apiv1.Routes())`,
     `include_router(tag_router)`, `include_router(users.router)`, `app.mount("/x", app=sub)`,
     `app.use('/api', require('./api'))` — e os routers que passa a funções (`users.Register(v1.Group("/users"))`,
     `addActionsRoutes(m)`, `routes(app)`). O router parâmetro de uma região de closure é o router de fora. No TS/JS
     o id é por arquivo (`var:<arquivo>:<nome>`, `ret:<arquivo>:<função>`; o que `export default`/`module.exports =`
     exporta se chama `default`), e export com outro nome ou reexportação é aresta sem prefixo. Imports pelo
     `RepoView` (`resolve_import` da linguagem).
   - `normalize_path`: `:id`, `{id:int}`, `<int:id>`, `%s`, `${x}`, `[controller]` → `{param}`-style;
     remove base URL, query string, barra final. `path_key` = tudo vira `{param}` (chave de join do linker).
3. **Composição entre arquivos** (`BaseScanner.compose`, uma vez por linguagem depois do scan): cada arquivo deixa
   um resumo só de dados — `out.publish(tipo, nome, fato)` e rotas `Pending` (gravadas como o arquivo as escreve,
   com o que falta para completá-las) — e a linguagem as resolve sem reabrir árvores (F1.13). Hoje:
   - C#: o `[Route]` herdado (`cs.class`), as actions de base abstrata (`cs.actions`) e os wrappers de cliente do app;
   - Go, Python e TS/JS: o grafo de montagem entre arquivos (`mount_rule`, com `<regra>.edge` e `<regra>.app`);
   - Go: o path que o encoder de um cliente go-kit põe na request (`go.encoder`) e o `basePath` do servidor
     go-swagger (`go.swagger-base`);
   - TS/JS: os wrappers de rota e de montagem do projeto (`ts.route-wrapper`, `ts.mount-wrapper`, com as chamadas
     candidatas `ts.route.maybe`, `ts.mount.maybe`) e o prefixo global do Nest por pacote (`ts.nest-prefix`, com o
     `exclude` em `ts.string-array`). A ordem do `TsScanner.compose`: rotas de wrapper, montagens por wrapper, grafo
     de montagem, Nest — cada passo produz o que o seguinte compõe.

Regras aprendidas no corpus (não regredir):

| Sintoma | Regra |
|---|---|
| `auth.Post("/login", h)` lido como chamada de saída | rota se o 2º arg é handler-like **ou** receiver é var de grupo/router |
| decorator `@Get(':id')` contado como chamada | `call_expression` dentro de `decorator` é ignorado |
| `cache.get(key)`, `map.delete(k)` | verbo minúsculo só é HTTP com receiver cliente (`CLIENT_RECEIVER`) |
| `post(ctx, client, "application/json", body)` | MIME (`MIME_TYPE`: dois tokens, sem placeholder) e heads em `_NOT_A_PATH_HEAD` não são path — `` `${url}application/${id}` `` é (gotify) |
| ``fetch(`${base}${path}`)``, `cache.Get(root + "/" + v + "/" + strings.Join(xs, ","))` | path sem segmento com nome é descartado (`has_literal_segment` exige letra ou dígito) |
| `var uri = $"{base}items/{id}"; GetFromJsonAsync(uri)` | `resolve_local` + `lenient` |
| `vApi.MapGroup("api/catalog").HasApiVersion(1,0)` | procurar o `MapGroup` **interno** da cadeia |
| supertest `request(app).get('/x')` em `e2e/` | `TEST_FILE` + filtro por `getHttpServer/supertest` |
| `Execute`, `Call`, `Send`, `Do` genéricos | `GENERIC_OUTBOUND` exige receiver cliente |
| C# `GetAsync($"api/x/{id}")` não detectado | `_interpolated` ignora `interpolation_start`/aspas — só texto + `{param}` |
| `new Uri($"api/x", UriKind.Relative)`, `string.Format("api/x/{0}")`, `Routes.X.Replace(..)` | `path_of` desce em `object_creation_expression(Uri)`, `Format`, `Replace/Trim*` |
| `SendAsync(msg)` duplicando `new HttpRequestMessage` | `SendAsync` com variável local que é `HttpRequestMessage` é ignorado |
| Flurl: URL é o *receiver* (`url.AppendPathSegment("x").GetJsonAsync()`) | `_flurl_path` percorre a cadeia antes do verbo; checado **antes** do early-return de args vazios |
| C# `this.X()` / `base.X()` nunca viravam call site | `this`/`base` são tokens anônimos na gramática: padrão próprio em `queries.scm`; `base.X()` com base fora do repo (ou implícita) não cai no fallback por nome (`LanguageSupport.parent_receivers`) — seria auto-aresta do override |
| Assinatura de classe C# com `[Route("api/[controller]")]` gravada como `")]` (e atributos com regex em string) | `strip_attributes` (core/extract.py) pula atributos com colchetes aninhados e literais de string; a convenção lê o cabeçalho da declaração (bases em várias linhas) com a mesma função |
| `r.GET("/", h)`, `@app.route("/")`, `group.MapGet("/")`, `router.GET("", h)` nunca viravam rota (`path_of` rejeita literal de 1 caractere) — 35 rotas faltando no corpus | `route_path` (core/http_base.py): a raiz vira rota **só quando o path completo é conhecido** — o receiver é a própria aplicação (`gin.Default/New`, `echo.New`, `fiber.New`, `http.NewServeMux`, `chi/mux.NewRouter` construído no `main`, `express()`, `fastify()`, `FastAPI()`, `Flask()`, `builder.Build()`; reconhecida por (escopo, nome), já que o `r` de `main` não é o `r` que um helper devolve) ou um grupo com prefixo próprio. Raiz de sub-router (`express.Router()`, `APIRouter()` sem prefixo, grupo recebido por parâmetro, router devolvido por função) fica de fora: o lugar dela é onde for montada |
| `{name:minlength(1)}`, `{brandId?}`, `{id:int?}`, `{slug:[a-z-]+}`, `<int:id>`, `<any(a, b):page>`, `:id?` derrubavam a rota inteira (`PATH_LITERAL` sem `<>()?+`) | `mask_placeholders` (core/paths.py) troca cada placeholder por `{p}` só para validar o literal; `normalize_path` remove o `?` de placeholder opcional **antes** de cortar a query (`{id:int?}` virava `{id{int}`) e aceita conversor Werkzeug com argumentos |
| `v1.GET("users", h)`, `api.MapGet("{orderId:int}", h)` ignorados (padrão sem `/` inicial) | `relative_on_groups` (Go, C#): num grupo conhecido o padrão relativo é juntado ao prefixo, como o framework faz. Python e Express exigem a barra — num `APIRouter` de callbacks OpenAPI `"{$callback_url}/invoices/..."` virava rota |
| `api := r.Group("/api")` / `const api = express.Router()`: todo `api.GET(...)` descartado porque `api` casa com `CLIENT_RECEIVER` | receiver que o arquivo construiu como router/grupo (`router_vars`) é rota, qualquer que seja o nome |
| `[HttpGet]` sem template num controller sem `[Route]` gravado como `GET /` (roteamento convencional `{controller}/{action}`) | ação sem template num controller sem prefixo não tem path próprio: não é gravada |
| `$"{base}items/{id}?api-version=2.0"`, `` `/api/users?active=${x}` `` rejeitados: a query literal falhava na validação do template | `path_of` valida o template **sem a query** (e com os placeholders mascarados); `normalize_path` já a removia depois |
| `fetch(url)` sem opções gravado como `ANY` | `fetch`/`$fetch`/`ofetch` sem a chave `method` é GET; com `method` que não se resolve, continua `ANY` |
| `client.get("/items/foo")` de um `TestClient(app)` em tutorial (fora de pasta de teste) virava chamada de saída | nomes ligados a `TestClient(...)` / `app.test_client()` (atribuição ou `with ... as`) não fazem chamada de saída |
| Express 5 `'/search/{:query}'`, `'/files/:name{.:ext}'` normalizados em `{{query}}`, `{.{ext}}` | grupo opcional com parâmetro (`{:x}`, `{.:x}`, `{/:x}`) vira o parâmetro, antes das demais regras |
| `r.Del("/silence/:sid", h)` (lib `route` da Prometheus) não era verbo | `GO_VERB_ALIASES = {"Del": "DELETE"}` |
| `GetFromJsonAsync<List<T>>(uri)` e todo genérico aninhado: o callee virava `GetFromJsonAsync<List` e a chamada sumia | os argumentos de tipo são removidos até estabilizar |
| `fetch(url)` com `url` parâmetro ganhava o valor do `url` local de **outra** função do diretório (zulip, mattermost; `SendAsync(message)` no jellyfin) | constantes só do módulo/classe; o nome é procurado primeiro nos escopos que o envolvem e um parâmetro encerra a busca |
| `RouteItem = RouteCollection + "/{id}"` gravado como `/{id}` (`first_string` pegava o primeiro literal) | constante montada por `+` vira partes e é resolvida no uso, inclusive com constantes de outro arquivo do diretório (kratos) |
| `ApiUrl + "/schedules"` com `ApiUrl = "https://host/20141201"` perdia o `/20141201` | constante com URL absoluta entra no contexto; o host sai na normalização |
| `` url = `${url}?notify=true` `` / `url = url + "/x"`: o nome à direita é o valor anterior | a atribuição que contém o nome não é a ligação dele; variável local interpolada é resolvida — constante do módulo não: num wrapper genérico (`` `${prefix}/${API_PATH}${path}` ``, alertmanager) faria um path do que é só a base |
| `target += "/" + id; method = "PATCH"` lido como `PATCH /api/v1/pages` (o método do ramo, o path de antes) | `x += e` é o valor anterior mais `e`, então path e método saem das mesmas últimas atribuições; com base desconhecida (`urlStr := c.base(); urlStr += fmt.Sprintf("/repos/%s", ..)`) vale o trecho acrescentado, se tiver segmento com nome — `path += "/"` num parâmetro não é rota (chi `FileServer`) |
| `requests\n  .put('/x')` (TS), `client.\n\tGet(...)` (Go): o receiver não casava | espaços removidos do callee em todas as linguagens |
| `fetch(url, {method: method})`, `request(method="POST", url=...)` gravados como `ANY` | o método vem de chave do objeto resolvida como variável (inclusive `{method}`) e de keyword argument |
| `api.del(...)` (NodeBB, superagent) não era DELETE | `TS_VERB_ALIASES = {"del": "DELETE"}`, com a mesma exigência de receiver cliente dos verbos |
| `$.get(url, cb)` do jQuery virava **rota** (o callback parecia handler) | receiver `$`/`jQuery` é cliente: `get`/`post`/`getJSON` são chamadas de saída, nunca rota |
| `mux.Handle("/booking/v1/", sub)` gravado como rota `ANY /booking/v1` | num `ServeMux` (ou no mux padrão) o padrão com `/` final é uma subárvore: montagem, não rota |
| `http.Handle("/x", h)` no mux padrão ignorado (`http` casa com `CLIENT_RECEIVER`) | `http.Handle`/`http.HandleFunc` são registro de rota |
| `routes.Get("/metrics", append(mid, h)...)` lido como chamada GET | argumento espalhado (`h...`, `...h`) é desembrulhado antes de decidir se é handler |
| `g.Group("/user").Use(mw).POST("", h)` perdia o `/user` | o prefixo atravessa a cadeia `Group`/`Use`/`With` do receiver |
| aiohttp `app.router.add_get('/x', h)`, `add_route('*', '/x', h)` (e `add_route = app.router.add_route`) não eram lidos | registrars do aiohttp em receiver `*.router`; a raiz conta (é o router da aplicação) |
| `r.Route("/articles", func(r chi.Router) { r.Get("/search", h) })`, `m.Group("/user", func() { m.Get("/login", h) })`, `fastify.register(fn, {prefix: '/v1'})`: a rota perdia o prefixo da closure | região de prefixo (`region_of`): o registro no parâmetro da closure (ou, no `Group` do gitea, no mesmo router) leva o prefixo; regiões aninhadas somam |
| `app.use('/api', router)` / Hono `app.route('/book', book)` / chi `r.Mount("/admin", adminRouter())` / `include_router(r, prefix=)` no mesmo arquivo: as rotas do router ficavam sem o prefixo, e a raiz dele era descartada | aresta de montagem + `finish()`; a raiz do sub-router montado vira a rota do prefixo (`GET /admin`) |
| `r.With(paginate).Get("/", h)` dentro de um `Route`: o receiver era a cadeia, não o `r` da closure | cadeia só de `With`/`Use` é registro no próprio router |
| bundle de build commitado (`static/assets/main-OdxfRQdf.js`) repetia rotas e chamadas da fonte | `.js` com nome de hash e linha > 500, ou com linha > 2000 e média > 200 por linha, fica fora da extração HTTP |
| `class DevicesController : BaseJellyfinApiController` sem `[Route]` próprio: rotas sem o `/devices` e ações sem template perdidas (jellyfin: 26 de 60 controllers) | `[Route]` da classe base, **um nível** (H2-D10): cada arquivo publica suas classes com o `[Route]` (`cs.class`), a rota do controller sem prefixo fica `Pending` e `CsScanner.compose` aplica o da base achada pelo nome, com `[controller]` do derivado; nome ambíguo (duas classes não `partial`) não herda; ação sem template só é rota com o prefixo herdado |
| FastEndpoints (`Get("/x")`, `Post(CreateRequest.Route)`, `Verbs(..)` + `Routes(..)` no `Configure()`) e Ardalis.ApiEndpoints (`EndpointBaseAsync.WithRequest<..>` com `[HttpPost("api/x")]`) não eram lidos | classe de endpoint: base `Endpoint<..>`/`EndpointWithoutRequest`/`Ep.*` com `Configure()` → as chamadas sem receiver dele, handler `HandleAsync`/`ExecuteAsync` da classe (`fastendpoints`); base `EndpointBase*` é controller |
| `Post(UpdateProjectRequest.Route)` com um `Route` em cada classe de request da pasta pegava o último coletado | constante de classe também por `Classe.NOME`, procurado antes do nome solto; nome com dois valores na pasta é ambíguo: vale o do arquivo, senão nada |
| `Get($"/{nameof(Project)}s")` gravado como `/{param}s`; e no C# a variável local interpolada (`$"{url}/x"`) nunca era resolvida | `nameof(X)` interpolado é o texto `X` (constante de compilação); as chaves da interpolação do C# são nós nomeados (`interpolation_brace`) e ficam fora da conta |
| `$"{remoteServiceBaseUrl}items/{id}"` com `remoteServiceBaseUrl = "api/catalog/"` (campo), `` `/${resource}/${id}/join` `` com `resource = "cases"`: o prefixo e o segmento que o código guarda viravam placeholder (eshop, dispatch) | constante interpolada vale quando forma **segmentos inteiros**: a de path no começo do template (seguida de `/`, de literal ou do fim), a de uma palavra (`_SEGMENT`, guardada à parte: sozinha não é path) entre barras ou numa ponta. **Não** num wrapper genérico — template com variável de nome de path (`path`, `url`, `endpoint`, `*Url`…): `${prefix}/${API_PATH}${path}` (alertmanager), `${GHOST_URL}/ghost/api/admin/${endpoint}` (ghost); ali a constante é só a base |
| `$"{UriHelper.CombineUri(base, ApiUrlBase)}?{v}"`: chamada interpolada e helper de juntar URL do próprio repo | chamada interpolada que já é path (Combine/Format/Join) vale como segmentos inteiros; `CombineUri`/`CombineUrl`/`UrlCombine` entram na família do `Path.Combine`, e o primeiro operando desconhecido de um join é a base (sai, como em `base + "/x"`) |
| `_httpService.HttpGet<T>("catalog-items")`: o wrapper do próprio app (`HttpService.HttpGet(string uri)` → `GetAsync($"{_apiUrl}{uri}")`) escondia toda chamada da UI (eShopOnWeb) | wrapper de cliente C#: o método cujo path de saída é montado em volta de um parâmetro publica `Classe.Método` (e sob as bases/interfaces da classe) com o índice do parâmetro, o verbo e o texto em volta; a chamada com argumento string num receiver de tipo declarado conhecido (campo, propriedade, parâmetro, local) fica `Pending` e `compose` monta o path. Sobrecargas com formas diferentes = nada |
| `[action]` num método `GetAsync` virava `getasync`; e `/api/todoitems` não era o `/api/TodoItems` que o OpenAPI e os clientes gerados escrevem | sem o sufixo `Async`, como o ASP.NET Core faz por padrão; `[controller]`/`[action]`/`[area]` na caixa declarada (a da classe e do método), e o linker casa rotas ASP.NET sem caixa, como o framework |
| `[Route("[area]/x")]` com `[Area("Admin")]`, `[Route("{area}/{controller}/admin")]` | `[area]` vem do `[Area]` da classe; `{area}`/`{controller}`/`{action}` são parâmetros reservados que o roteador fixa nos valores da action, então valem como os tokens |
| `EmailTemplatesController : ChannelTemplatesController<EmailTemplate, ..>` sem actions próprias: as rotas do CRUD genérico da base abstrata sumiam (notifo, 27) | cada action publica `cs.actions` com o template; o controller concreto com base do repo deixa `Pending` (`cs.inherited-actions`) e `compose` serve as actions da base (achada pelo nome, única) sob o `[Route]` do derivado — as que ele declara vencem; a classe abstrata não emite rota própria |
| Cliente NSwag C# (`ApiClients.g.cs`, `Generated.cs`): nenhuma operação extraída, e o `.g.cs` nem era lido | arquivo com o cabeçalho do NSwag: cada método que monta request vira chamada `generated-client` — path do `// Operation Path: "api/x/{id}"` (v14) ou dos literais de `urlBuilder_.Append(..)` (v13, placeholder entre eles), verbo do `request_.Method = new HttpMethod("GET")`; a descoberta mantém o `.g.cs` do NSwag |
| Cliente NSwag TS: 11 de 102 operações perdidas e as que não são `GET` gravadas como `GET` | `path_of` memoizado por nó, com profundidade 64 (as cadeias `url_ = url_.replace("{x}", ..)` e `url_ += "q=" + ..` passavam de 4); `method_from_args` lê o verbo de uma variável ligada a objeto (`fetch(url_, options_)` com `options_ = {method: "POST"}`) |
| `r.Mount("/api/v1", apiv1.Routes())` (gitea), `include_router(tag_router, prefix="/tags")` com o router importado (dispatch), `api_router.include_router(login.router)` (full-stack-fastapi-template): as rotas do router de outro arquivo ficavam sem o prefixo, e a raiz dele (`@router.get("")`) era descartada | grafo de montagem entre arquivos: router global (`var:`/`ret:`) + aresta publicada pelo arquivo que monta; `compose` segue as arestas até o topo. O import resolve pelo `RepoView` (o `resolve_import` da linguagem: arquivo Python, diretório de pacote Go) |
| `users.UsersRegister(v1.Group("/users"))` (gin-realworld), `addActionsRoutes(m, ...)` chamado dentro de vários grupos (gitea), `register_blueprints(app)`: o router chega como parâmetro | parâmetro router de função = router global `param:<unidade>:<função>:<i>`; a chamada publica a aresta com o prefixo do argumento ali (inclusive `x.Group("/p")` inline). Só argumentos que são routers do arquivo (registram, montam, foram criados como router ou são parâmetros tipados como router) |
| `api.BaseRoutes.Users = api.BaseRoutes.APIRoot.PathPrefix("/users").Subrouter()` em `api.go` e `api.BaseRoutes.Users.Handle("/known", h)` em `user.go` (mattermost, 607 rotas) | router em campo de struct (`field:<pacote>:BaseRoutes.Users`), comum aos arquivos do pacote qualquer que seja o nome da variável |
| `PathPrefix(model.APIURLSuffix)` (mattermost), `prefix=settings.API_V1_STR` (full-stack-fastapi-template), `mux.Handle(common.LoginEndpoint, h)` (argo-cd): a constante mora em outro pacote/módulo | `foreign_const`: `pkg.NOME` com `pkg` import do arquivo → constante do diretório importado; em Python também `NOME` importado por nome |
| `APIURLSuffix = APIURLSuffixV4` (Go) e `API_V1_STR: str = "/api/v1"` no corpo de uma classe (Python) não eram constantes | `const` Go que nomeia outra vira referência; atribuição anotada no corpo de classe Python é coletada |
| `m.Route("/repos/{owner}", func(r chi.Router) { addIssueRoutes(r) })`: o `r` da closure não tinha a montagem do router de fora | o parâmetro router de uma região de closure é o router de fora (`router_key`); o prefixo da região já está no registro |
| `r.Mount("/todos", todosResource{}.Routes())` e `usersResource.Routes` no mesmo pacote (chi) | método identificado por `Tipo.Metodo`; o tipo vem do literal `T{}` na chamada |
| `r := app.Group("/todo").Use(middleware.Auth)` não era grupo | `Use`/`With` no fim da atribuição são do grupo (como já era no receptor encadeado) |
| `/{fingerprint:[a-f0-9]{32}}/mute` virava `{fingerprint}}`; `/{websocket:websocket(?:\/)?}` quebrava no `?` | restrição com chaves aninhadas (um nível) e normalizada antes de cortar a query |
| `/{syncable_type:teams\|channels}/{id}/link`, `.Methods(http.MethodGet, http.MethodHead)` (gorilla) | segmento inteiro com alternativas literais vira um path por palavra (`{x:diff\|patch}` dentro de um segmento continua parâmetro); um registro por verbo de `Methods` |
| `ui := r.Group("/")` numa função que recebe a aplicação: `ui.GET("/")` era descartado como raiz de sub-router | a raiz montada sem prefixo vale quando a cadeia termina na aplicação (`APP`) |
| `m.Combo("/token", mw).Get(h).Delete(h)` (gitea, 219 rotas), `router.route('/:userId').get(h).patch(h)` (express): nenhum verbo virava rota — o 1º argumento do verbo não é path | cadeia de rota (`route_chain`): cada verbo depois do construtor (`Combo` no Go, `route` com um argumento no TS) é uma rota no path dele, no router que recebe o construtor; o `route('/x', sub)` do Hono continua montagem |
| `r.Methods("POST").Path("/profiles/").Handler(h)`, `r.Path("/x").HandlerFunc(h).Methods("GET")` (builder do gorilla, go-kit) e `MainRouter.PathPrefix("/.well-known/x").Handler(h).Methods("GET")` (mattermost) | o `Handler`/`HandlerFunc` no fim de uma cadeia de `Methods`/`Path`/`PathPrefix`/`Name`/`Queries`… é a rota, com os verbos de antes e de depois. `PathPrefix` atende uma subárvore: só é rota com verbo — sem verbo é árvore de arquivos (`FileServer`) ou montagem |
| `r.PathPrefix("/addsvc").Handler(http.StripPrefix("/addsvc", addtransport.NewHTTPHandler(..)))` (gateway do go-kit): as rotas do handler de outro pacote ficavam sem o `/addsvc`; e montá-las tirava as que o próprio serviço atende (`http.Serve(l, handler)`) | `StripPrefix` monta o router de dentro sob o prefixo que ele remove (o `PathPrefix` só filtra); um router de outro arquivo entregue a `http.Serve`/`ListenAndServe` é também uma aplicação (aresta para `APP` sem prefixo), então vale nos dois lugares |
| `u := *n.APIURL; u.Path += "gettoken"; notify.Get(ctx, c, u.String())`, `u.Path = path.Join(u.Path, "/oauth/userinfo")`, `APIURL.JoinPath("api/v1/x").String()` (alertmanager, kratos, mattermost): a chamada levava só `u.String()` | `url.URL` do Go: `u.String()` e o próprio `u` valem o último `u.Path = e` / `u.Path += e` antes dali (o índice de escopos guarda `u.Path` como um nome); sem nada atribuído, o path do `url.Parse(literal)`. Com a base desconhecida, o `+=` relativo ganha a barra (a URL configurada termina em `/`); `u.JoinPath(..)` começa pelo path de `u` |
| go-kit `httptransport.NewClient("GET", tgt, encodeX, decodeX)`, com o path no encoder (`req.URL.Path = "/profiles/" + id`, em outro arquivo do pacote) | o verbo é o 1º argumento; o path, o da URL ou, sem ele (`tgt.Path = ""`), o que o encoder põe no `*http.Request`: cada função que atribui `req.URL.Path` publica `go.encoder`, a chamada fica `Pending` e `GoScanner.compose` completa |
| Cliente openapi-generator Go (`localVarPath := localBasePath + "/admin/identities/{id}"`, `strings.Replace(localVarPath, "{"+"id"+"}", ..)`, `localVarHTTPMethod = http.MethodGet`, `prepareRequest(..)`) e go-swagger (`&runtime.ClientOperation{Method: "GET", PathPattern: "/alerts"}`) | `generated-client`: no arquivo com o cabeçalho do OpenAPI Generator, o `prepareRequest` com o path do 2º argumento e o verbo da variável do 3º (variável ligada a literal ou `http.MethodX` vale como verbo); o literal `runtime.ClientOperation` do go-swagger. O `basePath` da spec vem do transporte em runtime, como uma base URL. `strings.Replace(s, ..)` do Go é o `s` |
| `huma.Get(api, "/books", h)` lido como chamada GET; `"SELECT " + strings.Join(cols, ", ") + " FROM Posts"` como `GET /SELECT ...` (mattermost) | verbo com um path **antes** do último argumento e handler no fim é registro de rota (o `notify.Get(ctx, client, u.String())`, com a URL no fim, é chamada); `"VERBO /x"` só com verbo HTTP; `strings.Join` não junta path |
| Servidor grpc-gateway (`*.pb.gw.go`, argo-cd: 106 rotas da API): `mux.Handle("GET", pattern_AccountService_CanI_0, func(..) {..})` com o path só em `runtime.MustPattern(runtime.NewPattern(1, []int{2, 0, 2, 1, ..}, []string{"api", "v1", ..}, ""))` | `Handle(verbo, path, h)` com o verbo literal primeiro é rota (também o do httprouter); o padrão é decodificado (`grpc_gateway_pattern`: o programa de pilha do gateway — literal, segmento, captura `{x}`, `**`, verbo customizado `:sync`); o handler é o método gRPC (`AccountService.CanI`). Variável de pacote construída por chamada vale como último recurso do `path_of`. `{name}:cancel` não vira `{name}{cancel}` (`:x` depois de `}` não é parâmetro) |
| Servidor go-swagger (alertmanager `api/v2/restapi`): `o.handlers["GET"]["/alerts"] = alert.NewGetAlerts(..)`, com o `basePath` só no JSON embutido (`embedded_spec.go`, no pacote pai) | a atribuição ao mapa de handlers é rota (`go-swagger`), que espera o `basePath` que o `embedded_spec.go` do pacote pai publica (`go.swagger-base`) e `GoScanner.compose` aplica |
| flask-restx (CTFd): `@challenges_namespace.route("/<challenge_id>")` numa classe `Resource` com `def get/patch/delete` saía como um `GET` só, sem o `/api/v1/challenges` de `Api(Blueprint(url_prefix="/api/v1"))` + `add_namespace(ns, "/challenges")` em outro arquivo | `Namespace`/`Api` importados de `flask_restx`/`flask_restful` são routers (o `Api` montado no blueprint ou app com que é construído, levando o `url_prefix`); `add_namespace(ns, path)` é montagem, inclusive de namespace de outro arquivo; o `route` numa classe dá uma rota por método HTTP que ela define (`Classe.metodo`). Não aplicado: o path padrão do namespace (`/<nome>`), que só vale quando o `add_namespace` não dá path |
| `register_user = auth_router.post("/register")(register_user)` (dispatch): o decorador aplicado à mão não era rota | chamada cujo callee é a chamada de um registrar, com um nome como argumento, é a rota desse nome |
| TS/JS: router de outro arquivo sem o prefixo de quem monta (express-realworld `export default router` + `app.use(routes)`; express `app.use('/api/v1', require('./api_v1'))`; ghost `module.exports = function apiRoutes() {..; return router}` + `apiApp.use(routes())`) | o grafo entre arquivos cobre TS/JS: imports ESM (`import r from`, `{ a as b }`, `* as m`) e CommonJS (`require`, `require('x').y`, `const { y } = require`); o router de módulo é `var:<arquivo>:<nome>`, o devolvido por função `ret:`, o parâmetro `param:`; a função exportada por `module.exports =`/`export default` se chama `default`; filho de montagem pode ser nome importado, `require('./x')` no lugar, `routes()` (o que a função devolve) ou `m.router`; `router(app)` de outro arquivo passa o router ao parâmetro. Export com outro nome (`export default router`, `module.exports = { a: b }`, `exports.x = y`) e reexportação (`module.exports = require('./app')`, `export { a } from`) são arestas sem prefixo do nome local para o exportado |
| `app.use(router)` sem path não montava nada; Hono `new Hono<{ Bindings }>()` não era router (genérico entre o nome e o `(`), e o `api` do blog virava cliente; rotas encadeadas no construtor (`export const TodoAPI = new Hono().get(..).post(..)`, `export default Router().use('/api', api)`) ficavam sem dono | `use` sem path monta com prefixo vazio; genérico aceito no construtor; uma cadeia de chamadas que começa num construtor de router pertence ao nome a que a cadeia é ligada (`default` para `export default`/`module.exports =`), e a que começa num router (`app.get(..).post(..)`) a ele |
| Montagem por wrapper do projeto (ghost: `backendApp.lazyUse(BASE_API_PATH, require('../api'))`, 256 rotas) | método definido como `x.nome = function (path, fn) { app.use(path, .. fn() ..) }` (ou método de classe) que passa um parâmetro como path de um `use` é wrapper de montagem (`ts.mount-wrapper`: posição do path, do router e se o chama); a chamada `router.nome(path, filho)` num router fica candidata e o `compose` a torna montagem quando algum arquivo define o wrapper com a mesma forma — o filho é o módulo chamado (`ret:`) quando o wrapper chama o argumento |
| Raiz de sub-router montado sem path numa aplicação de outro arquivo (`app.use(webhooks)` com `webhooks.post('/')`) descartada; rotas de `app = express()` registradas dentro de uma função do mesmo arquivo perdiam a raiz | aplicação que outros arquivos podem nomear é publicada (`<regra>.app`); a cadeia que termina numa aplicação que ninguém monta mantém a raiz |
| Nest: `app.setGlobalPrefix('api', { exclude: excludePaths })` (immich, 238 rotas sem `/api`) | o prefixo vale para os controllers do **pacote** do arquivo que o chama (o módulo do `package.json` mais próximo; fato `ts.nest-prefix`); as rotas Nest esperam o `compose` (`ts.nest`), que só aplica quando o pacote tem um prefixo só; `exclude` com strings, `{ path }` e curingas (`docs/(.*)`, `x/*`, `x/{*splat}`), também numa lista exportada por outro arquivo (`ts.string-array`) |
| `@Controller(RouteKey.Asset)` com `enum RouteKey { Asset = 'assets' }` em outro arquivo saía sem prefixo; `@Controller({ path: 'cats' })` e `@Get(['a', 'b'])` também; o handler sumia quando havia comentário entre o decorator e o método | argumento do decorator Nest lido pela árvore: literal, array (uma rota por path), objeto (`path`), constante ou membro de enum, também de outro arquivo (`foreign_const` procura `Enum.Membro` e aceita uma palavra); membros string de enum TS são constantes `Enum.Membro`; comentário depois do decorator não esconde o método |
| Import TS `'../enum.js'` de um arquivo `enum.ts` (ESM com `moduleResolution: nodenext`) e alias `src/*` de um pacote abaixo da raiz (immich `server/`) não resolviam — no HTTP e nas arestas `IMPORTS` do grafo | o resolvedor tenta o `.ts`/`.tsx`/`.mts`/`.cts` de um especificador `.js`/`.jsx`/`.mjs`/`.cjs`, e os aliases (`src/`, `@/`, `~/`, `#`) a partir do pacote do arquivo antes da raiz do repo |
| Registrar do próprio projeto (NodeBB: `setupApiRoute(router, 'post', '/x', mws, handler)`, `setupPageRoute(app, '/x', .., handler)`, 353 rotas); dentro dele, `` router.get(`/api${name}`, ..) `` virava a rota `GET /api{param}` | função com nome (método, `helpers.x = function`, declaração, `const x =`) que registra num parâmetro router (`router.get(name, ..)`, `router[verb](name, ..)`) com o path vindo de um parâmetro — também dentro de template (`` `/api${name}` ``) — é wrapper de rota (`ts.route-wrapper`: posição do router, verbo fixo ou posição do argumento que o dá, posição do path, o path em volta); parâmetro rest desestruturado (`(...args) => { const [router, verb, name] = args }`) conta; os registros de dentro não são rotas. Chamada com path e router entre os argumentos fica candidata (`ts.route.maybe`, com o handler do último argumento e para onde o router leva); o `compose` a torna rota antes do grafo de montagem. A candidata não interrompe a leitura da chamada (`http.del(url, null, params)` do k6 continua chamada) |
| `module.exports = function () { ..; return router }` com `router` de módulo: as rotas não seguiam a montagem de `require('./users')()` | função que devolve um router de módulo publica a aresta `var:<arquivo>:router` → `ret:<arquivo>:<função>` |
| Express `'/reset/:code?'`, `'/chats/:roomid?/:index?'`: só a forma longa saía | parâmetro opcional no fim gera também a rota sem ele, um por vez (`/chats`, `/chats/{roomid}`, `/chats/{roomid}/{index}`) — no registro direto e nas rotas de wrapper |
| Requisição descrita por objeto (`request-config-object`): zulip `channel.post({ url: "/json/bots" })`, gotify `axios.create().request({ url, method: 'POST' })`, `$.ajax(url, { type })`, o SDK do openapi-ts `(options.client ?? client).post({ url: '/api/v1/..' })` | num método de verbo (`get`…`delete`, `del`) ou em `request`/`ajax`/`axios`, um objeto com `url` que guarda um path é a requisição, qualquer que seja o receptor; verbo do nome do método, senão o `method` (o `type` do jQuery) do próprio objeto, senão GET — só as chaves do próprio objeto (o `security: [{ type: 'http' }]` do openapi-ts não é verbo) |
| Cliente gerado pelo oazapfts (immich `packages/sdk`, 279 operações): `oazapfts.fetchJson<T>(`/activities${QS.query(..)}`, oazapfts.json({ ...opts, method: "POST" }))` não era chamada | em arquivo com o cabeçalho do oazapfts, `oazapfts.fetchJson`/`fetchText`/`fetchBlob` é chamada `generated-client`: path sem a query (`${QS.query(..)}`), sob o `baseUrl` literal do cliente (`defaults.baseUrl = "/api"`); verbo das opções (também dentro de `oazapfts.json/multipart/form(..)`), GET sem |
| `client = Client()` com `from django.test import Client` numa view de desenvolvimento (zulip `email_log.py`, 9 chamadas) virava chamada de saída | o `Client()` de teste do Django (importado de `django.test`) entra na regra do `TestClient`: o que passa por ele exercita o próprio app |
| `urljoin(f"https://{hostname}", f"/api/v1/x/{token}/")` gravado como `/https:/{param}/api/v1/x/{param}` | `urljoin` com path absoluto no 2º argumento é esse path; numa junção que começa por URL, o host fica e o resto se junta ao path dela |
| `` `https://host/admin/${token}god_mode=true` `` aceito como chamada: uma URL passava na validação com qualquer coisa depois do host | `is_url_literal`: o path da URL (placeholders mascarados, sem a query) tem de ser um path de rota, como os literais sem host |
| `public.GET(fmt.Sprintf("/%s", SchemasPath), h)` com `SchemasPath = "schemas"` (kratos) gravado como `GET /{param}` | `%s`/`%v` do `Sprintf` cujo argumento o código guarda vale como numa interpolação (`_substitution`: constante de segmento inteiro, de path no começo, fora de wrapper genérico); os outros verbos ficam parâmetro |
| Hono `'/post/:id{[0-9]+}'` gravado como `/post/{id}{[0-9]+}` | parâmetro com restrição de regex do Hono (`:id{..}`, chaves aninhadas num nível) vira o parâmetro, antes de cortar a query |
| Rotas e chamadas de servidores e helpers de teste fora de pasta `test` (mattermost `e2e-tests/cypress/webhook_serve.js`, kratos `courier/template/testhelpers`, Playwright) | `TEST_FILE` cobre também `e2e-tests/`, `cypress/`, `playwright/` e `testhelpers/`. `integration/` não: em app real é nome de código de produção (integrações), e o do nest e do fastify fica para a config por repo (F1.1) |

Limitações conhecidas no fechamento do H2 (2026-10-17; as que são evolução do extrator estão no ROADMAP, **F1.14**,
com os números do corpus):

- **Sem scanner:** Django urlconf e DRF (`path()`, `rest_path()`, `router.register()`); rotas por arquivo (Next.js
  `app/**/route.ts`, `@fastify/autoload` por pasta); rotas por convenção de nome (`MapGet(GetTodoItems)`).
- **Composição que o grafo ainda não segue:** router guardado num registro e montado em laço
  (`defaultRoutes.forEach(r => router.use(r.path, r.route))`, `for plugin in plugins: include_router(plugin.events)`);
  método de router chamado por um campo de tipo declarado (`api.deprecationRouter.Register(r.WithPrefix("/api/v1"))`);
  closure de registro atribuída e chamada dentro de vários grupos (gitea `addIssuesPullsViewRoutes`); tipo de router
  que acrescenta o prefixo nos próprios métodos (kratos `RouterAdmin`); reexportação por `__init__.py`; versionamento
  de URI do Nest (`enableVersioning` + `version`).
- **Wrapper de cliente fora do C#:** o cliente do próprio app que põe a base no path (argo-cd `requests.get('/x')` →
  `` agent.get(`${apiRoot()}${url}`) ``, NodeBB `api.put(..)` → `/api/v3`, gitea `GET(url)`): no TS e no Python a
  chamada sai sem o prefixo, ou não sai.
- **Limitação, não evolução:** prefixo que só existe em runtime (NodeBB `` `/api/${name}/..` `` montado com nomes de
  plugins) — o linker compara segmentos literais, então `/{param}/x` não liga nada e o extrator não grava; router
  entregue por uma interface (gotify `instance.RegisterWebhook(base, g)` aos plugins); rotas de biblioteca que o
  usuário monta (`middleware.Profiler()` do chi); URL montada em runtime sem literal; gRPC/proto e mensageria
  (F1/F2.2).
- **Fora do extrator:** o prefixo que viaja na base URL (`{base}items/{id}` vs `/api/catalog/items/{id}`) é do
  **linker** (match por sufixo + `target_hint`/`env_hints`); a spec como fonte de rotas, do **F2.1**; a mesma rota em
  dois apps do repo (o id do endpoint é por repo), do modelo (F1.14); pastas de app de teste com nome de produção
  (`integration/` do nest e do fastify), da config por repo (F1.1, `.aidd/index.yaml`).

## 4. Como rodar localmente (sem Neo4j)

```bash
cd indexer && pip install -e .                    # ou dentro da imagem: docker compose run --rm indexer ...
export TREE_SITTER_LANGUAGE_PACK_CACHE_DIR=~/.cache/tslp   # 1ª vez baixa as 6 gramáticas
python -c "import tree_sitter_language_pack as t; t.prefetch(['go','typescript','tsx','javascript','python','csharp'])"
aidd selftest                                     # gramáticas + queries
AIDD_TENANT=t WORKSPACE_PATH=/path aidd index <repo> --dry-run --out /tmp/x.json   # payload completo, sem banco
python scripts/http_corpus.py --json ~/.cache/aidd-corpus/runs/<data>-<rótulo>   # corpus público (clona em ~/.cache/aidd-corpus/repos)
```

O `--dry-run --out` inclui `endpoints`, `http_calls`, `symbols`, `calls`, `warnings` — é a forma de
inspecionar o que o extrator viu num repo específico.

## 5. Como medir (sem se enganar)

- **Fixtures golden** (`indexer/tests/fixtures/<nome>/` + `expected.json`, rodadas por `pytest tests/`): cada
  padrão suportado aparece uma vez com o resultado esperado; precisão e recall 100 % obrigatórios. Hoje:
  `go-http-mix` (net/http 1.22, gorilla, chi, gin+Group, clientes Go), `route-patterns-{go,ts,py,cs}` (uma linha
  por regra da tabela do §3, com o caso e o contraexemplo que não pode virar rota nem chamada; os casos entre arquivos
  ficam em subpastas próprias — `route-patterns-go/{cmd/crossfile,internal}`, `route-patterns-py/app/crossfile`,
  `route-patterns-ts/src/crossfile`, `route-patterns-ts/nest/` com `package.json` próprio), `ts-express-nest`, `csharp-httpclients`
  (HttpClient em 8 formas, Refit, Flurl, RestSharp, controllers) e o par **`csharp-praticis-todos` /
  `csharp-praticis-reports`** (+ `csharp-praticis-projects`) — o padrão .NET do autor em domínio genérico, uma
  fixture por layout (`flat`, `split`, `layered`) (Contracts + controller →
  `ServiceBus.SendAsync(command)` → `ICommandHandler`, validators, consumers `IEventHandler<ContractEvent>`,
  processors em decorator, `HttpClient` tipado em `Infra/Http/Outbound/<Svc>Api`), com a convenção `dotnet-praticis`.
  Fixtures que reproduzem um padrão de desenvolvimento declaram no `expected.json` a convenção (`convention`: yaml
  ao lado da fixture, id ou `module:Class`) e o que ela produz: `architecture` (layout detectado), `roles`, `layers`, `entry_points`, `violations` (uma
  proposital por fixture), `edges` (`CALLS` com estratégia) e `gaps` (ligações que o grafo ainda não vê — xfail até
  aparecerem; quando aparecem, o teste pede para movê-las a `edges`). Regenerar `expected.json` só depois de
  conferir cada linha na fonte — nunca a partir da saída do extrator sem revisão.
- **Corpus público** (`scripts/http_corpus.py`, 42 repos fixados por SHA, 41 com gabarito): `--baseline <execução>`
  lista, por repo, os ids `method path_key evidence` que entraram e saíram — toda mudança no extrator é julgada item a
  item nesse diff; `--expected` dá precisão/recall contra `tests/corpus_expected/<repo>.json` (spec commitada ou lista
  lida na fonte, com `scope`, a `category` de cada falta e a amostra `checked` julgada na fonte; formato no
  docstring de `scripts/corpus_metrics.py`) e fecha com os resumos por linguagem e por categoria (com o número de
  repos em que cada uma aparece); `--reuse <execução>` pontua uma execução salva sem extrair de novo — só para
  editar gabaritos, nunca para medir mudança no extrator. Números e ranking: `docs/corpus-report.md`.
- **O ciclo de uma mudança no extrator** (o do H2b, um commit por categoria):
  1. fixture com o caso e o contraexemplo, e conferir que ela **falha** sem a mudança;
  2. a mudança, e `pytest tests/` inteiro;
  3. o corpus contra a baseline vigente (a última `runs/<data>-v2-baseline-N`, em "Onde estamos" do
     `H2-roadmap.md`):

     ```bash
     docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONPATH=/src -v "$PWD/indexer":/src:ro \
       -v ~/.cache/aidd-corpus:/corpus --entrypoint python aidd-indexer:local /src/scripts/http_corpus.py \
       --dir /corpus/repos --json /corpus/runs/<data>-<rótulo> --baseline /corpus/runs/<baseline> --show 20 --expected
     ```

     Com nomes de repos, roda só esses — para iterar; a medida que vale é a do corpus inteiro. Os nomes vêm antes do
     `--expected`, que aceita um diretório (`... --show 20 nodebb ghost --expected`);
  4. julgar o diff **item a item na fonte**: cada item que sai tem de estar errado antes, e cada um que entra, certo.
     Mudança que a regra não explica é defeito da regra, mesmo com P/R subindo — no H2b, assim apareceram a chamada
     do k6 engolida por uma candidata a wrapper e a precisão do NodeBB caindo de 94 para 80 % com prefixos de runtime.
     Nenhum repo pode regredir (H2-D11);
  5. gabaritos: rota que só existe na spec sai, e rota real fora dela achada ao conferir um item entra (H2-D15); a
     linguagem é declarada por tipo quando difere da do repo (H2-D17); um item `checked` cuja `evidence` mudou de
     linha é reconferido, não copiado; depois de editar, `--reuse` pontua de novo;
  6. docs: linha "sintoma → regra" no §3, seção "Update" no `corpus-report.md`, item e log no `H2-roadmap.md`;
  7. a execução julgada vira a nova baseline (`runs/<data>-v2-baseline-N+1`) e o docstring do script ganha as
     contagens novas.

  Tempo: um repo que sai muito do tempo da baseline é rodado sozinho antes de culpar a mudança — no H2b os picos
  (mattermost 1369 s, bitwarden 813 s) eram da máquina, e sozinhos davam o tempo de sempre.
- **Amostragem manual**: sortear 10–20 itens por repo e conferir na fonte (`evidence` aponta linha).
  Anotar falsos positivos/negativos na tabela de regras (§3). Precisão importa mais que recall no
  extrator: o linker só liga o que casa; ruído vira aresta errada no grafo.
- Quando existir *ground truth* (apps de referência do H1, ou OpenAPI de um repo do corpus), calcular
  precisão/recall de verdade: `esperado × extraído` por `(method, path_key)`.

## 6. Checklist para mudar o extrator

1. Reproduzir o caso numa fixture pequena antes de mexer na heurística.
2. Mudar o scanner da linguagem (`languages/<lang>/http.py`) ou, se for regra comum a todas, `core/http_base.py`;
   rodar fixture + corpus; comparar contagens com o docstring do script.
3. Se a **semântica dos nós** mudou (novo campo, novo tipo de nó, path normalizado diferente): bump em
   `INDEXER_VERSION` (`aidd_indexer/__init__.py`) e em `pyproject.toml` → o `refresh` reindexa tudo.
   Novo label/índice → `neo4j/init/schema.cypher` (idempotente; `neo4j-init` reaplica no `up`) e `neo4j/SCHEMA.md`.
4. Se o MCP precisa expor o dado novo → `mcp/server.py` (ferramenta nova ou campo em `http_map`/`repo_map`);
   validar com o teste de protocolo (`build_server(store=Fake)`) — não precisa de Neo4j.
5. Atualizar a tabela de regras (§3), o docstring do módulo alterado e o ROADMAP ("Onde estamos" + item F0.x).
6. Nunca gravar nomes de projetos/tenant/tickets reais em docs ou código do repo (open-source): usar
   `<project-a>`, `<tenant>`, `<ticket>`.

## 7. Adicionar uma linguagem, um framework ou uma convenção

- **Linguagem nova**: `languages/<lang>/` com `queries.scm` (`def.*`/`call`/`import`), `symbols.py`
  (subclasse de `LanguageSupport` sobrescrevendo só o que difere — nomes qualificados, visibilidade,
  bindings de import, `resolve_import`; opcionalmente `file_facts`/`call_receiver`/`resolve_receiver` para
  resolver chamadas pelo tipo estático do receiver); exportar `LANGUAGES = [instância]` com `id`, `grammar`,
  `extensions`, `query_file`, `stack`, `manifests`) e, se houver HTTP, `http.py` (subclasse de
  `BaseScanner`, `http_scanner=` na instância). Registrar a pasta em `languages/__init__.py:_MODULES`.
  O `Dockerfile` e o `selftest` leem o registro — nada mais a editar. Fixture em `tests/fixtures/`.
- **Framework novo numa linguagem existente**: primeiro **veja a árvore** (`get_parser(lang).parse(src)` e
  imprima os `type`s), depois adicione o padrão ao scanner da linguagem e uma linha na fixture. Preferir
  reconhecer pela *forma* (verbo + path literal + handler) a por nome de biblioteca; o nome entra só
  como `framework` informativo.
- **Convenção** (regras do seu padrão — camadas, dependências permitidas, qual pasta de cliente fala
  com qual serviço): escreva um `convention.yaml` a partir de `setup/conventions/hexagonal.example.yaml`
  e aponte-o em `atlas.yaml` (`tenants.<t>.conventions: [{path: ..., repos: [...]}]`). O que o YAML não
  expressa vira uma classe `Convention` (`aidd_indexer/conventions/base.py`) num pacote seu, publicada
  no entry point `aidd.conventions` ou referenciada como `pacote.modulo:Classe`. Convenção nunca muda a
  extração: anota (`File.layer`, `Module.layer`, `HttpCall.target_hint`, `Symbol.is_entry_point`) e emite
  `Violation`. Regra de ouro: nada específico de uma organização entra em `core/` ou `languages/`.
  **Extensão empacotada** (ADR-003): `indexer/conventions/<nome>/` com `pyproject.toml` que publica uma classe no
  entry point `aidd.conventions`; o `Dockerfile` instala todas e falha o build se alguma não carrega; o tenant
  ativa por id (`conventions: [{id: <nome>}]`, ou `AIDD_CONVENTIONS=<nome>`). Em C# um `using X;` vira `IMPORTS`
  para o **Module** (o `.csproj`); a regra `forbid_import` usa a camada dos arquivos que declaram `X` — se eles
  estão em mais de uma camada, o import não diz nada e não gera violação.
  **Padrão × arquitetura** — duas perguntas diferentes, no mesmo `convention.yaml`: `roles:` diz *o que* cada tipo
  é, pela forma da declaração (bases do SDK/framework, nome, cabeçalho), em qualquer pasta → `Symbol.role`, entry
  points por papel e a camada de arquivos que o layout não posiciona; `architectures:` diz *onde* cada coisa mora
  em cada layout (globs por arquitetura, detectada pelos módulos do repo ou forçada por repo). As regras falam de
  camadas (mesmos nomes em todos os layouts) e `roles_in` cruza os dois: "command handler mora em `core`" vale
  igual num serviço de um projeto ou de cinco. Exemplo: `indexer/conventions/dotnet-praticis/` — 13 papéis,
  3 arquiteturas (`flat`: tudo no `.Api`; `split`: `.Api` + `.Core`; `layered`: `.Api` + `.Application` + `.Core` +
  `.Domain` + `.Infra`), 8 regras; validado nos repos de referência (todos os arquivos dos serviços com camada,
  0 violações, monorepo com biblioteca `*.Shared.Bus.Core` corretamente não confundido com `split`).

## 8. O que vem depois do extrator (para não invadir)

- **F0.5 linker (feito)**: `core/linker.py` — `HttpCall × HttpEndpoint` por `path_key` + método →
  `CONSUMES` (Service→HttpEndpoint) e `CALLED_FROM` (HttpEndpoint→Symbol); `exact` antes de `suffix`,
  desempate por `target_hint`/`env_hints`, ambíguo não grava. Roda por tenant inteiro ao fim de
  `index`/`bootstrap`/`refresh` e em `aidd link`. Se uma chamada não liga, a pergunta é sempre "o que
  falta no extrator ou na convenção (`targets:`)?" — não "o linker deveria chutar?".
- **F0.5.1 `DEPENDS_ON` (feito)**: segunda junção do linker — `Snapshot.requires × Snapshot.provides`
  (pacotes internos declarados nos manifestos) → `Service -[:DEPENDS_ON {ref}]-> Service`, mesma postura
  (nome exato normalizado, nunca a si mesmo, dois publicadores → nenhuma aresta). `repo_map` devolve
  `depends_on`/`depended_by`. É a dependência que o scan HTTP não enxerga (contratos, SDKs internos).
- **F0.7 perguntas douradas**: `who_consumes('/v1/<rota>')` respondida pelo grafo no par piloto.
- F1: SCIP para `CALLS` resolvidos, gRPC/proto, mensageria, Qdrant.
