# Handoff H1 — Apps de referência multi-linguagem do *seu* padrão de desenvolvimento

> Cole este arquivo (ou peça para ler `docs/handoffs/H1-reference-apps.md`) no início de um chat
> novo. Antes de qualquer coisa o chat deve ler `docs/indexer-evolution.md`, `docs/ROADMAP.md`
> (seção "Onde estamos" e F0.4/F0.5) e `indexer/aidd_indexer/integrations.py`.

## Contexto em um parágrafo

O aidd-stack indexa repositórios num grafo de código (Neo4j `atlas`) e expõe isso às skills via MCP.
O extrator de integrações HTTP (`integrations.py`, F0.4) reconhece rotas expostas e chamadas de saída
por heurísticas sobre a árvore tree-sitter. Ele foi calibrado num corpus público, mas o alvo real é
**o padrão de arquitetura que o autor definiu para os times** — hexagonal, com um jeito próprio de
registrar rotas, de encapsular clientes HTTP e de nomear camadas — hoje aplicado em Go e replicado em
outras linguagens. Este handoff é sobre garantir que o indexador entende *esse* padrão em todas as
linguagens em que ele existe, com resultado esperado conhecido (ground truth), e usar isso como
suíte de regressão permanente.

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
4. Onde o extrator falhar, evoluir `integrations.py` (ou `extract.py`/queries) — sem regredir o corpus
   público (`scripts/http_corpus.py`).

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
- `integrations.py` evoluído, corpus público sem regressão, tabela de regras atualizada no guia.
- ROADMAP: item F0.4.2 "fixtures do padrão do autor" marcado, com a lista de gaps que ficaram para o
  F0.5 (linker) e F1 (SCIP/gRPC).
