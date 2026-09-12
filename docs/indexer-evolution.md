# Guia de evolução do indexador (`indexer/`)

> Documento de trabalho em PT (como o ROADMAP). Público: quem vai **melhorar a extração** — símbolos,
> chamadas, e principalmente os **candidatos de integração HTTP** (`integrations.py`). Os handoffs
> em `docs/handoffs/` apontam para cá; leia este primeiro.

## 1. O que o indexador é e o que não é

- Transforma repositórios em um grafo (Neo4j, database `atlas`): micro (Repo → Module → File → Symbol,
  `CALLS`, `IMPORTS`) e macro (Service → `HttpEndpoint`, `HttpCall` → futuro `CONSUMES`). Esquema:
  `neo4j/SCHEMA.md`. Ids determinísticos: `aidd_indexer/ids.py`.
- **Determinístico**: tree-sitter + heurísticas. LLM nunca é parser (princípio no ROADMAP). Se um padrão não
  dá para reconhecer estaticamente, a resposta certa é *registrar a limitação*, não chutar.
- Tudo que o indexador grava carrega `tenant/repo/ref/commit_sha/indexed_at` e, no macro, `evidence`
  (`repo:arquivo:linha`) e `confidence`. Nada de valor de segredo; só nome de env var.
- Roda dentro da imagem `aidd-indexer` (Docker), com as gramáticas pré-baixadas
  (`TREE_SITTER_LANGUAGE_PACK_CACHE_DIR=/opt/tslp-cache`, `AIDD_GRAMMAR_OFFLINE=1`). O `refresh`
  agendado reindexa a cada 15 min e **reindexa tudo quando `INDEXER_VERSION` muda**.

## 2. Mapa do código

| Arquivo | Papel |
|---|---|
| `cli.py` | comandos `plan / bootstrap / refresh / index / status / wipe / selftest / serve`; `extract_tree()` é o pipeline por repo |
| `discovery.py` | quais arquivos entram, linguagem por extensão (`LANGUAGE_BY_EXT`), módulos por manifesto (`go.mod`, `package.json`, `*.csproj`, `pyproject.toml`), `PARSEABLE` |
| `extract.py` | `FileExtractor`: parse tree-sitter + queries `.scm` → `SymbolInfo`, `CallInfo`, `ImportInfo`; heurística de `is_entry_point`; `load_language()` com `GRAMMAR_ERRORS` |
| `queries/*.scm` | uma query por linguagem, padrões `def.<kind>`, `call`, `import` — compiladas padrão a padrão (um padrão inválido é pulado com warning, não derruba a linguagem) |
| `resolve.py` | `CALLS` por nome (same-file → same-module → unique-name) e `IMPORTS` → File/Module/Package |
| `integrations.py` | **candidatos HTTP**: rotas expostas (`HttpEndpointInfo`) e chamadas de saída (`HttpCallInfo`) — ver §3 |
| `model.py` | dataclasses de tudo acima + `ExtractionResult` |
| `graph.py` | `GraphWriter.write()`: MERGE idempotente, `EXPOSES{ref}`/`HANDLED_BY{ref}`, GC de órfãos por `commit_sha`, `IndexRun` |
| `planner.py` / `manifest.py` / `gitinfo.py` | `atlas.yaml` → plano de (repo, ref, sha); `git archive` por ref; política de branches |
| `mcp_server.py` | MCP `atlas` (leitura): `atlas_status, repo_map, find_symbol, who_calls, symbol_context, http_map, who_consumes, cypher_readonly` |
| `scripts/http_corpus.py` | corpus público de calibração do extrator HTTP (§5) |

Pipeline de um repo (`cli.extract_tree`): `list_files` → `discover_modules` → `build_files` → para cada
arquivo parseável `FileExtractor.run()` → `extract_http(repo, extractors)` → `Resolver.run()` → `GraphWriter.write()`.

## 3. Como `integrations.py` decide

Dois passes sobre os `FileExtractor`s (que já têm `tree`, `src`, `symbols`, `_enclosing_symbol()`):

1. **Contexto por diretório** (`_PackageContext`): constantes/vars de rota (`const routeX = "/v1/x"`,
   `ORDERS_PATH = '/v1/orders'`) e nomes de env var que parecem base URL (`*_URL`, `*_HOST`, `*_ENDPOINT`).
2. **Scanner por linguagem** (`_GoScanner`, `_TsScanner`, `_CsScanner`, `_PyScanner`), todos herdando de
   `_BaseScanner`, que concentra as peças reutilizáveis:
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

- **Fixture mínima** (a de `docs/handoffs/H1-reference-apps.md` vai virar `indexer/tests/fixtures/`): cada
  padrão suportado aparece uma vez com o resultado esperado. Regressão binária.
- **Corpus público** (`scripts/http_corpus.py`): ordem de grandeza por repo documentada no docstring; um
  desvio grande em qualquer repo é sinal de regressão ou de melhoria — em ambos os casos, olhar o JSON.
- **Amostragem manual**: sortear 10–20 itens por repo e conferir na fonte (`evidence` aponta linha).
  Anotar falsos positivos/negativos na tabela de regras (§3). Precisão importa mais que recall no
  extrator: o linker só liga o que casa; ruído vira aresta errada no grafo.
- Quando existir *ground truth* (apps de referência do H1, ou OpenAPI de um repo do corpus), calcular
  precisão/recall de verdade: `esperado × extraído` por `(method, path_key)`.

## 6. Checklist para mudar o extrator

1. Reproduzir o caso numa fixture pequena antes de mexer na heurística.
2. Mudar `integrations.py`; rodar fixture + corpus; comparar contagens com o docstring do script.
3. Se a **semântica dos nós** mudou (novo campo, novo tipo de nó, path normalizado diferente): bump em
   `INDEXER_VERSION` (`aidd_indexer/__init__.py`) e em `pyproject.toml` → o `refresh` reindexa tudo.
   Novo label/índice → `neo4j/init/schema.cypher` (idempotente; `neo4j-init` reaplica no `up`) e `neo4j/SCHEMA.md`.
4. Se o MCP precisa expor o dado novo → `mcp_server.py` (ferramenta nova ou campo em `http_map`/`repo_map`);
   validar com o teste de protocolo (`build_server(store=Fake)`) — não precisa de Neo4j.
5. Atualizar a tabela de regras (§3), o docstring de `integrations.py` e o ROADMAP ("Onde estamos" + item F0.x).
6. Nunca gravar nomes de projetos/tenant/tickets reais em docs ou código do repo (open-source): usar
   `<project-a>`, `<tenant>`, `<ticket>`.

## 7. Adicionar uma linguagem ou framework

- Linguagem nova: extensão em `discovery.LANGUAGE_BY_EXT` e `PARSEABLE`; gramática em `Dockerfile`
  (`t.prefetch([...])`) e no `selftest`; `queries/<lang>.scm` com `def.*`/`call`/`import`; scanner em
  `integrations.py` (herdar `_BaseScanner`, implementar `run()`), registrado no dict de `extract_http`.
- Framework novo numa linguagem existente: primeiro **veja a árvore** (`get_parser(lang).parse(src)` e
  imprima os `type`s — há um snippet no histórico do H2), depois adicione o padrão ao scanner e uma
  linha na fixture. Preferir reconhecer pela *forma* (verbo + path literal + handler) a por nome de
  biblioteca; o nome entra só como `framework` informativo.

## 8. O que vem depois do extrator (para não invadir)

- **F0.5 linker**: `HttpCall × HttpEndpoint` por `path_key` + método → `CONSUMES` (Service→HttpEndpoint)
  e `CALLED_FROM` (HttpEndpoint→Symbol), com desempate por `target_hint`/`env_hints` e match por sufixo.
- **F0.7 perguntas douradas**: `who_consumes('/v1/<rota>')` respondida pelo grafo no par piloto.
- F1: SCIP para `CALLS` resolvidos, gRPC/proto, mensageria, Qdrant.
