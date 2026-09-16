# ADR-003 — Indexador em núcleo compartilhado + módulos por linguagem

**Status:** proposto (executar após F0.4.1, antes de abrir H1/H2) · **Data:** 2026-09-14 · **Fase:** 0

## Contexto

Hoje o indexador (`indexer/aidd_indexer/`, ~3,7 k linhas) mistura duas coisas: o **pipeline**
(descoberta, snapshot, escrita idempotente no grafo, GC, plano de refs, MCP) e o **conhecimento
por linguagem** (queries tree-sitter, regras de nome qualificado, receivers em Go, namespaces em C#,
scanners HTTP por framework). O conhecimento por linguagem está espalhado: `extract.py` tem `if
lang == "csharp"` em vários pontos, `integrations.py` concentra quatro scanners num arquivo de 900
linhas, `discovery.py` conhece extensões e manifestos de todas as linguagens.

Duas frentes vão evoluir esse conhecimento em paralelo (handoffs H1 e H2) e o SCIP entrará por
linguagem (ADR-002). Com o layout atual, cada frente edita os mesmos arquivos grandes; conflitos e
regressões cruzadas são inevitáveis.

## Decisão (proposta)

Separar em **núcleo** e **módulos de linguagem**, com um contrato explícito:

```
aidd_indexer/
├── core/                      # sem nenhum `if language ==`
│   ├── pipeline.py            # extract_tree(): discovery → per-file extract → integrations → resolve
│   ├── model.py  ids.py  paths.py (normalize_path, path_key)
│   ├── discovery.py           # walk + módulos, consultando o registro de linguagens
│   ├── extract.py             # FileExtractor genérico: parse, queries, símbolos, chamadas, imports
│   ├── resolve.py  graph.py  planner.py  manifest.py  gitinfo.py  config.py
│   └── http_base.py           # _BaseScanner: path_of, is_handler_like, resolve_local, add_endpoint/add_call
├── languages/
│   ├── __init__.py            # REGISTRY: language id → LanguageSupport; by_extension(); parseable()
│   ├── base.py                # class LanguageSupport(Protocol)
│   ├── go/        __init__.py  queries.scm  symbols.py  http.py
│   ├── typescript/ (ids: typescript, tsx, javascript)
│   ├── csharp/
│   └── python/
├── mcp/server.py
└── cli.py
```

Contrato `LanguageSupport` (o que um módulo declara):

| Membro | Hoje vive em | Exemplo |
|---|---|---|
| `id`, `aliases`, `extensions` | `discovery.LANGUAGE_BY_EXT` | `csharp`, `.cs` |
| `manifests` | `discovery.MANIFESTS` | `go.mod` → `go-module` |
| `grammar` (nome no language pack) | `extract.load_language` | `csharp` |
| `queries` (arquivo `.scm` ao lado) | `extract.QUERY_DIR` | `languages/go/queries.scm` |
| `qualified_name(chain, name, file)`, `receiver()`, `visibility()`, `namespaces()` | `extract._make_symbol` + ifs | Go: `pkg.Type.Method`; C#: `Namespace.Class.Method` |
| `entry_point_hints` | `extract.ENTRY_POINT_HINTS` / `DECORATOR_ENTRY` | `[HttpGet`, `@Get(` |
| `test_file_patterns` | `integrations.TEST_FILE` | `_test.go`, `Tests.cs` |
| `http_scanner` (classe) | `integrations._GoScanner` etc. | herda `core.http_base.BaseScanner` |
| `generated_suffixes` | `config.GENERATED_SUFFIXES` | `.pb.go`, `.g.cs` |
| `enrichers` (F1.2) | — | `scip-go` → resoluções para `CALLS` |

Regras:

- O núcleo **nunca** consulta o id da linguagem; só o registro. Adicionar linguagem = criar a pasta e
  registrar; nada muda em `core/`.
- Convenções específicas de um tenant (padrão de arquitetura do autor, H1) entram como **camada
  opcional** por linguagem (`languages/<lang>/conventions/<nome>.py`) ligada por `atlas.yaml`
  (`conventions: [hexagonal-v1]`), nunca como heurística global.
- Sem carregamento dinâmico de pacotes externos por enquanto (entry points do Python ficam para
  quando existir demanda real de plugin de terceiros); o registro é estático e legível.

## Convenções como extensões (segunda camada)

Acima dos módulos de linguagem, uma camada **plugável e versionada** para os padrões de arquitetura
de cada organização — que podem ser proprietários e evoluir em ritmo próprio, portanto **não precisam
viver neste repositório**.

- Um pacote Python (`aidd_conventions_<nome>`, repo próprio ou pasta `conventions/` aqui) registra-se
  no ponto de extensão `aidd.conventions` (entry point) e implementa o contrato `Convention`, todo
  opcional:

| Hook | Devolve | Efeito no grafo / MCP |
|---|---|---|
| `classify_module(path, module)` | `layer` (`inbound-http`, `usecase`, `port`, `outbound:<svc>`, `domain`, `platform`) | `Module.layer`, `Symbol.role`; `repo_map` mostra camadas nomeadas |
| `route_patterns(language)` / `client_patterns(language)` | registradores e clientes HTTP extras (ex.: `registerRoutes`+`setHandlerSecurity`, `PostJSON`) | entram no scanner da linguagem com `confidence: exact` (convenção declarada) |
| `target_of(file, module)` | serviço alvo de um adapter outbound | substitui o `target_hint` heurístico |
| `entry_point(symbol)` | handler / comando / job / consumer | precisão de `is_entry_point` |
| `rules()` | verificações estruturais (direção de dependência, um handler por path, decoder único…) | nós `Violation{rule, severity, evidence}` consultáveis pelo MCP — insumo do `refine-tech` |

- A parte declarativa vai num `convention.yaml` (mapa pasta → camada, nomes de registradores/clientes,
  layout do outbound); só regras e resolvedores exigem Python.
- Ativação por tenant ou por repo no `atlas.yaml`: `conventions: [hexagonal-v1]`. Versões coexistem
  (`hexagonal-v1`, `-v2`) enquanto os repos migram.
- O núcleo nunca importa uma convenção; consulta o registro. Convenção ausente ou com erro degrada
  para o comportamento genérico **com aviso** — nunca derruba a indexação.
- Regra de ouro: nada específico de uma organização entra em `core/` ou `languages/`; se uma
  heurística só faz sentido para um padrão, ela é convenção.

## Migração

Refatoração **mecânica, sem mudança de comportamento**: os números do corpus público
(`scripts/http_corpus.py`) e da fixture são a regressão — devem sair idênticos antes e depois.
`INDEXER_VERSION` não muda (semântica dos nós igual), então não dispara reindexação.

1. Mover `normalize_path`/`path_key` para `core/paths.py`; `_BaseScanner` para `core/http_base.py`.
2. Criar `languages/base.py` + registro; migrar `LANGUAGE_BY_EXT`, `MANIFESTS`, `PARSEABLE`,
   `GENERATED_SUFFIXES`, `TEST_FILE` para os módulos.
3. Uma linguagem por commit: mover `.scm`, extrair os `if lang ==` de `extract.py` para `symbols.py`,
   mover o scanner para `http.py`. Rodar fixture + corpus após cada uma.
4. `extract.py` e `integrations.py` viram fachadas finas sobre o registro (ou somem).
5. Criar o registro `aidd.conventions`, o contrato `Convention` e uma convenção-exemplo mínima
   (`conventions/example/`) que só classifica camadas por pasta — prova a costura sem codificar
   nenhum padrão real. `atlas.yaml` ganha `conventions:` (opcional).
6. Atualizar `docs/indexer-evolution.md` (mapa do código, "adicionar linguagem", "escrever uma
   convenção") e os handoffs.

Ordem: depois do F0.4.1 (validação do extrator genérico no portfólio real — separa bug de refactor)
e **antes** de H1/H2 começarem a editar. O H1 (padrão do autor) passa a ser a primeira convenção
real escrita contra o contrato, não código dentro de `integrations.py`.

## Consequências

- H1 e H2 trabalham em pastas diferentes (`languages/<lang>/`), e o núcleo fica protegido por
  regressão.
- SCIP (ADR-002) tem um lugar natural: `languages/<lang>/enrich.py`.
- Custo: um refactor de algumas horas agora; o risco é baixo porque a regressão é numérica e já
  existe.
- Fica para depois: empacotar linguagens como plugins externos (entry points) e um `LanguageSupport`
  declarativo em YAML — só se aparecer necessidade de terceiros adicionarem linguagens sem tocar no repo.
