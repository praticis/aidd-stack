# Handoff H1 — Apps de referência multi-linguagem do *seu* padrão de desenvolvimento

> Cole este arquivo (ou peça para ler `docs/handoffs/H1-reference-apps.md`) no início de um chat
> novo. Antes de qualquer coisa o chat deve ler `docs/indexer-evolution.md`, `docs/ROADMAP.md`
> (seção "Onde estamos" e F0.4/F0.5), `indexer/aidd_indexer/languages/base.py` e `indexer/aidd_indexer/conventions/`.

## Contexto em um parágrafo

O aidd-stack indexa repositórios num grafo de código (Neo4j `atlas`) e expõe isso às skills via MCP.
O extrator de integrações HTTP (`core/integrations.py` + `languages/<lang>/http.py`, F0.4) reconhece rotas expostas e chamadas de saída
por heurísticas sobre a árvore tree-sitter. Ele foi calibrado num corpus público, mas o alvo real é
**o padrão de arquitetura que o autor definiu para os times** — hexagonal, com um jeito próprio de
registrar rotas, de encapsular clientes HTTP e de nomear camadas — hoje aplicado em Go e replicado em
outras linguagens. Este handoff é sobre garantir que o indexador entende *esse* padrão em todas as
linguagens em que ele existe, com resultado esperado conhecido (ground truth), e usar isso como
suíte de regressão permanente.

## Pré-requisito: o refactor do ADR-003 (F0.4.4) — **feito em 2026-09-17**

O padrão do autor **não** entra em `core/` nem em `languages/`. Ele vira a primeira **convenção**
real, escrita contra o contrato que já existe:

- `indexer/aidd_indexer/conventions/base.py` — `Convention` com `configure(options)`, `layer_of(file,
  module)`, `target_of(http_call, file)`, `is_entry_point(symbol, file)`, `check(ctx) -> [ViolationInfo]`.
- `conventions/declarative.py` — `convention.yaml` (camadas por glob, `targets`, `entry_points`, regras
  `forbid_import` / `endpoints_only_in` / `http_calls_only_in`). Exemplo comentado em
  `setup/conventions/hexagonal.example.yaml`; comece por ele.
- Ativação em `atlas.yaml`: `tenants.<t>.conventions: [{path: .../convention.yaml, repos: ["*"]}]` ou
  `{id: pacote.modulo:Classe}` / entry point `aidd.conventions` para o que exigir Python. Para testar
  sem manifesto: `AIDD_CONVENTIONS=/caminho/convention.yaml aidd index <repo> --dry-run --out x.json`
  (o payload traz `violations` e `layer` em files/modules).
- O que **ainda não existe** e é provavelmente o que o padrão do autor vai pedir primeiro:
  `route_patterns` / `client_patterns` (registradores e clientes HTTP próprios, ex.:
  `registerRoutes`+`setHandlerSecurity`, `PostJSON`) entrando no scanner da linguagem via um hook em
  `core/http_base.BaseScanner` consultado pela convenção ativa. Implementar como hook, com fixture;
  nunca como `if` no scanner.
- Regressão obrigatória a cada mudança: `pytest indexer/tests/` (5 testes) e o corpus público idêntico
  (`scripts/http_corpus.py`). Mudança em `core/` ou `languages/` só se for regra geral da linguagem.

## Objetivo

1. Ter, dentro do repositório (`indexer/tests/fixtures/<lang>-<framework>/`), **uma aplicação mínima
   por linguagem/framework que implemente o padrão do autor de ponta a ponta**: inbound (rotas +
   handlers + middleware de segurança), aplicação (use cases/ports), outbound (cliente HTTP para outro
   serviço do mesmo padrão, com constantes de rota e base URL por env var), erros, testes.
2. Ao lado de cada app, um `expected.json` com o *ground truth*: lista de `(method, path)` expostos com
   o nome do handler, e lista de chamadas de saída `(method, path, target_hint, caller)`.
3. Um teste (`indexer/tests/test_fixtures.py`, pytest) que roda `extract_tree` + `extract_http` em cada
   fixture e compara com o `expected.json` — **precisão e recall 100 %** é o critério, porque o padrão é
   controlado.
4. Onde o extrator genérico falhar por causa do padrão, a correção vai na **convenção** (yaml/hooks);
   só o que é regra geral de linguagem/framework vai em `languages/<lang>/` — sem regredir o corpus
   público (`scripts/http_corpus.py`).
5. As `rules()` da convenção (direção de dependência, um handler por path, decoder único, sem PII em
   log…) geram nós `Violation`; validar nas fixtures com uma violação proposital cada.

## O que o chat precisa perguntar/obter do autor logo no início

- **A descrição do padrão** (os standards: ele mencionou um submódulo `tools/` com arquivos como
  `http-handler-pattern.md`). Pedir o conteúdo ou um resumo: como se registra rota (ex.: `ServerConfig`
  + interface `Handler` + `registerRoutes` + `setHandlerSecurity`, `mux.HandleFunc("METHOD /path")`),
  como é o cliente outbound (constantes `routeX`, `PostJSON`, base URL em env `*_URL`), nomes de pastas
  (`internal/adapters/inbound/http`, `internal/adapters/outbound/<svc>`, `internal/app/{ports,usecases}`).
- **Em quais linguagens/frameworks o padrão já existe ou vai existir**: Go (net/http 1.22), .NET
  (minimal APIs ou controllers?), Node (Nest? Express? Fastify?), Python (FastAPI?). Priorizar as
  stacks do ROADMAP: Go, .NET, Node.
- **Exemplos reais**: se ele puder colar trechos (registro de rotas, adapter outbound, wiring) de um repo
  de cada linguagem, a fixture nasce fiel. Não copiar código proprietário para o repo open-source —
  reescrever como exemplo genérico (`orders`, `users`, `billing`), sem nomes de projetos/tenant/tickets.

## Como fazer (ordem sugerida)

1. Ler o guia e rodar o extrator no estado atual: `aidd selftest`, depois `python scripts/http_corpus.py`
   para ter a baseline (números no docstring do script).
2. Escrever a primeira fixture em Go seguindo o padrão do autor (é a linguagem onde ele está mais
   maduro); produzir o `expected.json` **à mão, lendo o código**, não a partir da saída do extrator.
3. Escrever `tests/test_fixtures.py` e rodar; corrigir o extrator até 100 %; anotar cada regra nova na
   tabela do guia (§3).
4. Repetir para .NET, Node e Python, sempre reproduzindo a *forma* do padrão (não só "um endpoint
   qualquer"): grupos/prefixos, versionamento de rota (`/v1`), rota autenticada vs pública, handler que
   chama use case que chama adapter outbound → **a cadeia inteira deve aparecer no grafo**
   (`HttpEndpoint -HANDLED_BY-> handler -CALLS-> usecase -CALLS-> adapter -MAKES_HTTP_CALL-> HttpCall`).
   Onde `CALLS` por nome falhar (interfaces, DI), registrar — é insumo do F1 (SCIP).
5. Fechar com um par de fixtures que se falam (app A chama app B) e validar `who_consumes` no MCP com o
   teste de protocolo (sem Neo4j) e, se houver ambiente, num Neo4j real.

## Armadilhas conhecidas

- Não usar LLM para "adivinhar" rota; se um padrão do autor depende de convenção de nome
  (ex.: rota derivada do nome do método), a solução é uma **regra explícita e documentada** para
  aquele padrão, ligada por configuração (`atlas.yaml` poderá ganhar `conventions:` por repo), não uma
  heurística global.
- Arquivos de teste são ignorados por `TEST_FILE`; se o padrão do autor coloca código real em pastas
  chamadas `test*`/`integration`, isso precisa ser revisto.
- Mudança de semântica nos nós → bump de `INDEXER_VERSION` (o `refresh` reindexa tudo sozinho).
- Docs do repo em inglês, ROADMAP e handoffs em PT; nunca nomes reais de projetos.

## Entregáveis esperados ao fim do chat

- `indexer/tests/fixtures/*` (≥ 1 por linguagem) + `expected.json` + `tests/test_fixtures.py` verdes.
- A convenção do padrão do autor (`convention.yaml` + classe `Convention` se precisar) com testes em
  `tests/test_conventions.py`; hooks novos no contrato só quando o YAML não expressar; corpus público
  sem regressão; tabela de regras atualizada no guia.
- ROADMAP: item F0.4.2 "fixtures do padrão do autor" marcado, com a lista de gaps que ficaram para o
  F0.5 (linker) e F1 (SCIP/gRPC).
