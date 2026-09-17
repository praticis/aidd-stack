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
| `core/discovery.py` | quais arquivos entram; linguagem por extensão via `languages.by_extension()`; módulos por manifesto (declarados em cada `LanguageSupport.manifests`) + `discover_modules()` de cada linguagem (pacotes Go) |
| `core/extract.py` | `FileExtractor`: parse tree-sitter + `queries.scm` → `SymbolInfo`, `CallInfo`, `ImportInfo`; delega a `LanguageSupport` nomes qualificados, visibilidade, docstrings, bindings de import e marcadores de entry point; `load_language()` com `GRAMMAR_ERRORS` |
| `core/resolve.py` | `CALLS` por nome (same-file → same-module → unique-name); `IMPORTS` via `LanguageSupport.resolve_import()` → File/Module/Package; `link_symbols()` por linguagem (receivers Go) |
| `core/integrations.py` | orquestra os **candidatos HTTP**: contexto por diretório → `LanguageSupport.http_scanner` de cada arquivo — ver §3 |
| `core/http_base.py` | `BaseScanner` (as peças reutilizáveis de §3), `PackageContext`, `TEST_FILE`, tabela `OUTBOUND` |
| `core/paths.py` | `normalize_path`, `path_key`, `unquote`, regexes de path — usados pelo extrator, pelo `graph.py` e pelo MCP |
| `core/model.py` | dataclasses de tudo + `ExtractionResult` (inclui `violations`) |
| `core/graph.py` | `GraphWriter.write()`: MERGE idempotente, `EXPOSES{ref}`/`HANDLED_BY{ref}`, `Violation`/`HAS_VIOLATION`, GC de órfãos por `commit_sha`, `IndexRun` |
| `core/planner.py` / `core/manifest.py` / `core/gitinfo.py` | `atlas.yaml` (tenants, sources, refs, areas, **conventions**) → plano de (repo, ref, sha); `git archive` por ref |
| `languages/__init__.py` | registro: `REGISTRY`, `by_id`, `by_extension`, `parseable()`, `grammars()`; `_MODULES` lista as pastas |
| `languages/base.py` | contrato `LanguageSupport` (identidade · descoberta · símbolos · resolução · http) e `ResolveContext` |
| `languages/<lang>/queries.scm` | padrões `def.<kind>`, `call`, `import` — compilados padrão a padrão (um inválido é pulado com warning) |
| `languages/<lang>/symbols.py` | a subclasse de `LanguageSupport` + `LANGUAGES = [...]` (typescript registra `typescript`, `tsx`, `javascript`) |
| `languages/<lang>/http.py` | o scanner HTTP da linguagem (`GoScanner`, `TsScanner`, `CsScanner`, `PyScanner`) e suas tabelas de registradores |
| `conventions/base.py` | contrato `Convention` (`layer_of`, `target_of`, `is_entry_point`, `check`) e `ConventionContext` |
| `conventions/declarative.py` | `convention.yaml` → `Convention` (camadas por glob, alvos, entry points, regras `forbid_import` / `endpoints_only_in` / `http_calls_only_in`) |
| `conventions/__init__.py` | `load(specs, repo)` (arquivo, entry point `aidd.conventions` ou `pacote.modulo:Classe`) e `apply()` |
| `mcp/server.py` | MCP `atlas` (leitura): `atlas_status, repo_map, find_symbol, who_calls, symbol_context, http_map, who_consumes, cypher_readonly` |
| `scripts/http_corpus.py` | corpus público de calibração do extrator HTTP (§5) |
| `tests/` | fixtures HTTP (golden) + `test_conventions.py` (costura das convenções) |

Pipeline de um repo (`cli.extract_tree` → `extract_and_resolve`): `list_files` → `discover_modules` →
`build_files` → para cada arquivo parseável `FileExtractor.run()` → `extract_http(repo, extractors)` →
`Resolver.run()` → `conventions.apply()` (se houver) → `GraphWriter.write()`.

## 3. Como o extrator HTTP decide

Dois passes sobre os `FileExtractor`s (que já têm `tree`, `src`, `symbols`, `_enclosing_symbol()`):

1. **Contexto por diretório** (`PackageContext`): constantes/vars de rota (`const routeX = "/v1/x"`,
   `ORDERS_PATH = '/v1/orders'`) e nomes de env var que parecem base URL (`*_URL`, `*_HOST`, `*_ENDPOINT`).
2. **Scanner por linguagem** (`languages/<lang>/http.py`: `GoScanner`, `TsScanner`, `CsScanner`, `PyScanner`),
   todos herdando de `core/http_base.BaseScanner`, que concentra as peças reutilizáveis:
   - `path_of(node, lenient)`: transforma uma expressão em template de path — literal, constante do
     pacote, **variável local** (`resolve_local`: última atribuição anterior no mesmo escopo),
     concatenação, `Sprintf`/f-string/`$""`/`` `${}` ``, `path.Join`. `lenient=True` (só em contexto de
     cliente HTTP) aceita `items/{id}` e `{base}catalogBrands`.
   - `is_handler_like(node)`: **a regra que separa rota de chamada de saída** — o argumento depois do
     path é função/seletor/identificador (rota) ou dado/string/nil (cliente).
   - `method_from_args`, `resolve_handler` (nome → `Symbol` do mesmo arquivo), `add_endpoint`,
     `add_call` (descarta path sem segmento literal), `_record_group` (prefixos de `Group/MapGroup/APIRouter(prefix=)`).
   - `normalize_path`: `:id`, `{id:int}`, `<int:id>`, `%s`, `${x}`, `[controller]` → `{param}`-style;
     remove base URL, query string, barra final. `path_key` = tudo vira `{param}` (chave de join do linker).

Regras aprendidas no corpus (não regredir):

| Sintoma | Regra |
|---|---|
| `auth.Post("/login", h)` lido como chamada de saída | rota se o 2º arg é handler-like **ou** receiver é var de grupo/router |
| decorator `@Get(':id')` contado como chamada | `call_expression` dentro de `decorator` é ignorado |
| `cache.get(key)`, `map.delete(k)` | verbo minúsculo só é HTTP com receiver cliente (`CLIENT_RECEIVER`) |
| `post(ctx, client, "application/json", body)` | MIME/heads em `_NOT_A_PATH_HEAD` não são path |
| ``fetch(`${base}${path}`)`` | path só de placeholders é descartado (`_has_literal_segment`) |
| `var uri = $"{base}items/{id}"; GetFromJsonAsync(uri)` | `resolve_local` + `lenient` |
| `vApi.MapGroup("api/catalog").HasApiVersion(1,0)` | procurar o `MapGroup` **interno** da cadeia |
| supertest `request(app).get('/x')` em `e2e/` | `TEST_FILE` + filtro por `getHttpServer/supertest` |
| `Execute`, `Call`, `Send`, `Do` genéricos | `GENERIC_OUTBOUND` exige receiver cliente |
| C# `GetAsync($"api/x/{id}")` não detectado | `_interpolated` ignora `interpolation_start`/aspas — só texto + `{param}` |
| `new Uri($"api/x", UriKind.Relative)`, `string.Format("api/x/{0}")`, `Routes.X.Replace(..)` | `path_of` desce em `object_creation_expression(Uri)`, `Format`, `Replace/Trim*` |
| `SendAsync(msg)` duplicando `new HttpRequestMessage` | `SendAsync` com variável local que é `HttpRequestMessage` é ignorado |
| Flurl: URL é o *receiver* (`url.AppendPathSegment("x").GetJsonAsync()`) | `_flurl_path` percorre a cadeia antes do verbo; checado **antes** do early-return de args vazios |

Limitações conhecidas (candidatas a evolução — ver handoffs): prefixos definidos em outro escopo ou
arquivo (`r.Route("/admin", func(r){...})`, `include_router(prefix=)`, `Handle("/api/v1", sub)`),
rotas por convenção de nome (`MapGet(GetTodoItems)`), URL montada em runtime sem literal, gRPC/proto,
mensageria. O prefixo que viaja na base URL (`{base}items/{id}` vs `/api/catalog/items/{id}`) é
problema do **linker** (match por sufixo + `target_hint`/`env_hints`), não do extrator.

## 4. Como rodar localmente (sem Neo4j)

```bash
cd indexer && pip install -e .                    # ou dentro da imagem: docker compose run --rm indexer ...
export TREE_SITTER_LANGUAGE_PACK_CACHE_DIR=~/.cache/tslp   # 1ª vez baixa as 6 gramáticas
python -c "import tree_sitter_language_pack as t; t.prefetch(['go','typescript','tsx','javascript','python','csharp'])"
aidd selftest                                     # gramáticas + queries
AIDD_TENANT=t WORKSPACE_PATH=/path aidd index <repo> --dry-run --out /tmp/x.json   # payload completo, sem banco
python scripts/http_corpus.py --json /tmp/corpus-out            # corpus público (clona em /tmp/aidd-corpus)
```

O `--dry-run --out` inclui `endpoints`, `http_calls`, `symbols`, `calls`, `warnings` — é a forma de
inspecionar o que o extrator viu num repo específico.

## 5. Como medir (sem se enganar)

- **Fixtures golden** (`indexer/tests/fixtures/<nome>/` + `expected.json`, rodadas por `pytest tests/`): cada
  padrão suportado aparece uma vez com o resultado esperado; precisão e recall 100 % obrigatórios. Hoje:
  `go-http-mix` (net/http 1.22, gorilla, chi, gin+Group, clientes Go), `ts-express-nest`, `csharp-httpclients`
  (HttpClient em 8 formas, Refit, Flurl, RestSharp, controllers). Regenerar `expected.json` só depois de conferir
  cada linha na fonte — nunca a partir da saída do extrator sem revisão.
- **Corpus público** (`scripts/http_corpus.py`): ordem de grandeza por repo documentada no docstring; um
  desvio grande em qualquer repo é sinal de regressão ou de melhoria — em ambos os casos, olhar o JSON.
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
  bindings de import, `resolve_import`; exportar `LANGUAGES = [instância]` com `id`, `grammar`,
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

## 8. O que vem depois do extrator (para não invadir)

- **F0.5 linker**: `HttpCall × HttpEndpoint` por `path_key` + método → `CONSUMES` (Service→HttpEndpoint)
  e `CALLED_FROM` (HttpEndpoint→Symbol), com desempate por `target_hint`/`env_hints` e match por sufixo.
- **F0.7 perguntas douradas**: `who_consumes('/v1/<rota>')` respondida pelo grafo no par piloto.
- F1: SCIP para `CALLS` resolvidos, gRPC/proto, mensageria, Qdrant.
