# AIDD Stack — Roteiro de evolução (code graph + skills)

> Documento vivo. Marque `[x]` ao concluir. Atualize a seção **Onde estamos** a cada sessão
> para que qualquer agente/pessoa retome do ponto certo.

## Onde estamos

- Fase atual: **Fase 0 — Fundação** (em andamento)
- Último marco concluído (2026-09-09): D1 decidido (Neo4j, ADR-001), Neo4j + `neo4j-init` + `mcp-neo4j` no compose (porta 3004, `atlas` no `.mcp.json`), esquema v1 em `neo4j/SCHEMA.md` (inglês)
- Branch de trabalho: `feature/refine-business` (já contém `refine-business` v1 e `scan` com vault por projeto)
- 2026-09-10: compose subiu; credenciais centralizadas no `.env` (`NEO4J_USER`/`NEO4J_PASSWORD`, geradas pelo `install.sh`); compose falha rápido sem senha
- 2026-09-10: `install-check.sh` passou; MCP renomeado para `atlas` (D6)
- 2026-09-10: F0.3 entregue e validado no atlas real com um repo Go do portfólio (`<project-a>`); `AIDD_TENANT` obrigatório em todo o stack (D7)
- 2026-09-11: **checkpoint** — infra + indexador funcionando; pausa para desenhar o *processo* de indexação (bootstrap do portfólio, política de branches, refresh) antes do F0.4. Proposta em `docs/indexing-process.md` (D8–D11 em aberto)
- 2026-09-11: F0.3.5 implementado — `atlas.yaml`, `aidd plan/bootstrap/refresh`, refs via `git archive`, áreas opcionais, etapa "Atlas Bootstrap" no `install.sh` (que agora também builda o profile `tools`). Validado com fixture; **falta rodar numa instalação limpa**
- 2026-09-11: **instalação limpa validada de ponta a ponta** — `install.sh` → infra → `plan` (6 repos, 22 snapshots) → bootstrap em 26 s, 0 falhas. Baseline de resolução por nome: ~40% dos call sites em Go resolvidos (ex.: `<project-b>` 2549/5131) — métrica a bater com SCIP (F1.2)
- 2026-09-11: GC validado com commit real (6 changed, orphans removidos). Indexador agora faz `git fetch --all --prune` sozinho (workspace rw, SSH/.gitconfig montados, `openssh-client` na imagem, ssh-agent encaminhado, PAT via `git-askpass.sh`; `--no-fetch` / `fetch: false`). Pendente F0.3.7: agente SSH persistente entre sessões WSL. `<project-b>@develop` confirmado como resquício → remover `develop` desse repo do atlas (ver F0.3.6)
- 2026-09-11: D12 — instalação sem fetch; trilha "Atualização contínua" (U1–U5) criada
- 2026-09-11: **atualização contínua validada** (U1–U3.1) — agendador **dentro do WSL** (systemd user timer + linger + autostart do distro via Startup `.vbs`), sem task no Windows; `aidd schedule check --fix` valida/repara os pré-requisitos
- 2026-09-11: incidente — um build transitório do indexador não carregou gramáticas e gravou 26 snapshots **vazios como sucesso**. Corrigido: versões pinadas, gramática ausente aborta a execução (rc=4), `aidd selftest` (também no `install-check.sh`), contagem de snapshots sem símbolos. Bônus: classes JS nunca eram extraídas (query errada) — corrigido
- 2026-09-11: **causa-raiz do incidente acima encontrada** no teste de sync: `tree-sitter-language-pack` 1.x não embute gramáticas — baixa um `.so` por linguagem do GitHub Releases no primeiro `get_language()`. Como cada `docker compose run` é um container novo, todo refresh que precisava parsear baixava de novo, e um timeout do GitHub derrubou o refresh agendado (`rc=4`, a proteção funcionou: snapshot não foi gravada). Corrigido: `indexer/Dockerfile` pré-baixa as 6 gramáticas em `/opt/tslp-cache` (`TREE_SITTER_LANGUAGE_PACK_CACHE_DIR`), roda `aidd selftest` no build (build falha se faltar algo) e define `AIDD_GRAMMAR_OFFLINE=1` — em runtime, gramática fora do cache é erro imediato ("rebuild the indexer image"), nunca download. Validado offline no sandbox: 6/6 OK com cache; cache vazio falha em 0,1 s
- 2026-09-11: **F0.6 implementado** — MCP `atlas` v0 (`aidd serve`, mesma imagem do indexador, serviço `mcp-atlas` na porta **3005**, `/healthz`): `atlas_status`, `repo_map`, `find_symbol`, `who_calls`, `symbol_context`, `cypher_readonly` (transação READ + bloqueio de palavras de escrita), tudo escopado por `AIDD_TENANT`, `ref` default = branch padrão do repo, snapshots efêmeras só com `ref` explícito. `mcp-neo4j` bruto foi para o profile `debug`; `.mcp.json` aponta `atlas` → 3005; `install-check.sh` chama `atlas_status` de verdade. Protocolo validado no sandbox (initialize, tools/list, tools/call, healthz, recusa de escrita); `install-check` verde na máquina (atlas_status listou os 6 repos, /healthz ok, 25 002 nós); falta o teste pelo Claude Code (F0.6.1)
- 2026-09-11: `install.sh` em modo upgrade não pergunta mais o tenant — lê `AIDD_TENANT` do `.env` e só oferece trocar ([Y/n])
- 2026-09-11: **F0.6.1 validado no Claude Code** — `atlas_status`, `repo_map <project-a>` (camadas hexagonais, 9 entry points), `find_symbol Handler`, `who_calls` no decoder central de requests (7 chamadores same-module), `symbol_context`, escrita recusada. Achado: fulltext casa prefixo mas não sufixo (`Handler` não trazia `XxxHandler`) → `find_symbol` ganhou complemento por substring no nome
- 2026-09-11: **F0.8 implementado** — `scan` v2: passo 0 chama `atlas_status` → `repo_map` (ref = branch atual se indexada) como verdade estrutural, com fallback explícito ("atlas unavailable" → fluxo antigo); página do vault ganha `## Source` com `<repo>@<ref> <sha>`; seção "From here on" orienta `find_symbol`/`symbol_context`/`who_calls` antes de mexer em código, com a semântica das estratégias de resolução. validado em sessão real (F0.8.1)
- 2026-09-11: **F0.8.1 validado** — (a) `<project-a>` com atlas: `scan` usou `repo_map` + leitura de 5 arquivos representativos, gravou vault + qdrant, produziu a "receita" de endpoint novo em 3 min; (b) `<project-b>` com `mcp-atlas` parado: a skill avisou "não carregados nesta sessão" e mapeou pela árvore (nota: qdrant/obsidian também não estavam carregados nessa sessão — fallback confundido com MCPs do projeto não aprovados; comportamento da skill foi o correto mesmo assim). Skill ganhou instrução explícita para o caso vault/qdrant indisponíveis. Causa do (b) encontrada: `<project-b>/.claude/settings.local.json` tinha `disabledMcpjsonServers` (um "não" na primeira sessão fica gravado e os MCPs do projeto nunca mais carregam, em silêncio) → etapa 5 do `install.sh` agora detecta e avisa `[blocked]` por repo, com a correção (`enableAllProjectMcpServers: true`). **Fase 0: só falta o macro (F0.4, F0.5, F0.7).** Par piloto escolhido pelo grafo: **`<project-a>` (BFF) → `<project-b>` (serviço)** — o BFF tem um adapter outbound dedicado ao serviço (constantes de rota + `PostJSON`); o serviço expõe ~18 rotas via `mux.HandleFunc`
- Próximo passo: F0.4 extrator de candidatos v0 (Go: rotas `mux.HandleFunc("METHOD /path")`, chamadas HTTP de saída com path literal) → F0.5 linker `CALLS_HTTP` `<project-a>`→`<project-b>` → F0.7 perguntas douradas

---

## Princípios (não negociáveis)

- Camada de conhecimento (grafo + vetores + vault) é **independente do orquestrador**: só MCP + skills. Cline, Roo, Goose, Claude Code ou Aider consomem o mesmo backend.
- Extração **determinística** (SCIP / tree-sitter). LLM só para sumarizar e desambiguar; nunca como parser primário.
- Todo nó/aresta carrega `tenant`, `repo`, `ref` (branch), `commit_sha`, `indexed_at`; arestas macro carregam `confidence` + `evidence`.
- Segredos nunca entram no índice (extrair o *nome* da env var, nunca o valor).
- Cada fase termina com **perguntas douradas** passando (recall medido, não sentido).

## Stack alvo (open source / baixo custo)

| Camada | Ferramenta | Licença / custo |
|---|---|---|
| Parser universal | tree-sitter | MIT |
| Indexação precisa | SCIP: scip-go, scip-typescript, scip-dotnet, scip-python | Apache-2.0 |
| Graph DB | Neo4j Community (alt.: Memgraph Community) | GPLv3 / BSL — gratuitos |
| Vetores | Qdrant (já no compose) | Apache-2.0 |
| Embeddings | FastEmbed + `jinaai/jina-embeddings-v2-base-code` (alt.: nomic-embed-code via Ollama) | Apache-2.0, local |
| Docs/ADR | Obsidian + MCP (já no compose) | gratuito (uso comercial liberado desde 2025) |
| MCP `atlas` | FastMCP (Python) próprio + mcp-neo4j-cypher | Apache-2.0 |
| LLM local | Ollama (Qwen-Coder / DeepSeek para sumários, classificação) | gratuito |
| LLM frontier | Claude (planejamento, refinamento, review) | **único custo variável** |
| Planejamento | Jira via Atlassian MCP | já disponível |
| Spec | Spec Kit (opcional) | MIT |
| CI (fase 3) | GitHub Actions / GitLab CI com runner self-hosted | gratuito/baixo |

## Quando cada coisa fica utilizável (para não se perder)

| Marco | O que você passa a poder fazer | Muda algo nas skills? |
|---|---|---|
| Compose com Neo4j (feito) | Abrir `localhost:7474`; MCP `atlas` responde `get_neo4j_schema` | **Não.** Grafo vazio; `scan` segue igual |
| F0.3–F0.5 indexer + linker v0 | `aidd index <repo>` popula o grafo; validar com Cypher / perguntas douradas | Não |
| F0.6 MCP `atlas` próprio (:3005) | Ferramentas de intenção (`repo_map`, `who_consumes`…) disponíveis no Claude Code | Não, mas habilita o próximo |
| F0.8 `scan` v2 | `scan` consulta o grafo primeiro, com fallback ao fluxo atual | **Sim** — transparente: mesmo gatilho, mais precisa |
| F1.10 / F2.7 `flow`, `impact` | Perguntas micro/macro respondidas com evidência | Novas skills |
| S4/S5 `refine-business`, `refine-tech` | Fluxo de refinamento completo (Jira → contexto → área → spec) | Novas skills; dependem de `impact` |

Regra: o grafo só entra nas skills via MCP `atlas` e **sempre com fallback**. Até o F0.6 ele é infra em preparação — nada a acionar no dia a dia.

### Checklist de validação do compose (fazer agora)

Atalho: `~/.aidd/install-check.sh` (copiado pelo `install.sh`) roda os itens 2–7 abaixo e imprime OK/FAIL por check.


- [ ] `.env` tem `NEO4J_USER=neo4j` e `NEO4J_PASSWORD=<senha>` (o `install.sh` gera; se o volume já existia com outra senha: `docker compose down -v` e subir de novo — dev only)
- [ ] `docker compose up -d --build` sem erro; `docker compose ps` mostra `neo4j` *healthy* e `neo4j-init` como *Exited (0)*
- [ ] `docker logs aidd-neo4j-init` sem erro (o cypher-shell é silencioso em sucesso — vazio é bom; erro de sintaxe aparece aqui)
- [ ] **Neo4j Browser** em <http://localhost:7474> (login com o `.env`): `SHOW CONSTRAINTS` lista 14 constraints; `SHOW INDEXES` inclui `symbol_fulltext`; `RETURN apoc.version()` responde
- [ ] `docker logs aidd-mcp-atlas` mostra o Uvicorn escutando em 0.0.0.0:3000; `curl -s http://localhost:3005/healthz` devolve `{"status":"ok","neo4j":true,...}`
- [ ] (debug) `docker compose --profile debug up -d mcp-neo4j` → `curl -s -o /dev/null -w "%{http_code}" http://localhost:3004/mcp/` devolve um status HTTP
- [ ] No Claude Code, com `setup/.mcp.json` aplicado: `/mcp` lista `atlas`; pedir "rode `get_neo4j_schema`" retorna vazio (grafo sem dados) sem erro de autenticação
- [ ] `install.sh` re-executado sincroniza `~/.aidd/neo4j/` e o `docker-compose.yml` novo
- [ ] Docs: `git rm docs/graph-schema.md` (movido para `neo4j/SCHEMA.md`)

---

## Fase 0 — Fundação (PoC ponta a ponta, 2 repos)

Objetivo: provar micro + macro com o mínimo: dois repos (Go + Node) que se falam por gRPC/HTTP, e uma pergunta `who_consumes` respondida a partir do grafo.

- [x] F0.1 Escolher graph DB (Neo4j Community vs Memgraph) e adicionar ao `docker-compose.yml` com volume e healthcheck
- [x] F0.2 Escrever `neo4j/SCHEMA.md`: nós (Repo, Module, File, Symbol, HttpEndpoint, GrpcMethod, Topic, InternalPackage, DbTable), arestas, propriedades obrigatórias
- [x] F0.3 Criar `indexer/` (Python): CLI `aidd index <repo>` com tree-sitter → nós micro (Repo, Snapshot, Module, File, Symbol, CONTAINS, IMPORTS, CALLS por nome, Package externo) → `MERGE` idempotente + GC de órfãos + IndexRun; `--dry-run --out` para inspeção
- [x] F0.3.1 Validar no atlas real (2026-09-10: `<project-a>`, 494 símbolos / 636 CALLS / 352 IMPORTS em 5,9 s): `docker compose --profile tools build indexer` → `docker compose run --rm indexer index <repo>` → `aidd status` → no Browser: `MATCH (f:File)-[:CONTAINS]->(s:Symbol) RETURN f.path, s.kind, s.name LIMIT 25` e `MATCH (a)-[c:CALLS]->(b) RETURN a.name, b.name, c.strategy LIMIT 25`
- [x] F0.3.5 **Processo de indexação** (ver `docs/indexing-process.md`): `atlas.yaml` (fontes, seleção, política de refs), fonte `local`, `aidd plan` / `bootstrap` / `refresh`, `--ref` real via `git worktree`, opção "Atlas bootstrap" no `install.sh`; `install.sh` builda também o profile `tools`
- [x] F0.3.2 Idempotência e GC confirmados: `refresh` = 0 changed após bootstrap; após push real, 6 changed, `orphans_deleted` > 0
- [x] F0.3.7a Wrapper de host `~/.aidd/aidd` (fetch com as credenciais do dev, container com `--no-fetch`); instalação indexa **sem fetch** (refs como clonados) — decisão D12
- [ ] F0.3.6 Política de refs por repo: permitir `refs.overrides: {<project>: {always: ["main"]}}` no `atlas.yaml` para casos como `<project>@develop` (branch abandonada); até lá, `aidd wipe <project> --ref develop`
- [ ] F0.4 Extrator de candidatos de integração v0: rotas expostas (Go `mux/gin/chi`, NestJS/Express), `.proto` + stubs, chamadas HTTP de saída com path literal
- [ ] F0.5 Linker v0: match exato de gRPC (`service.method`) e de pacotes internos (manifests) → arestas `CALLS_GRPC`, `DEPENDS_ON`, `CONSUMES`
- [x] F0.6 MCP `atlas` v0 (FastMCP via SDK `mcp`, streamable HTTP *stateless* na porta 3005, `indexer/aidd_indexer/mcp_server.py`, `aidd serve`): `atlas_status`, `repo_map`, `find_symbol` (fulltext `symbol_fulltext`, prefixo automático), `who_calls`, `symbol_context`, `cypher_readonly`. `mcp-neo4j` bruto → profile `debug`. `who_consumes` (macro) entra com o F0.5
  - [ ] F0.6.1 Validar na máquina: `install-check` seção MCP verde, `/mcp` lista `atlas` no Claude Code, `repo_map <project>` e `who_calls` respondem com dados reais
- [ ] F0.7 Rodar nos 2 repos piloto e responder 5 perguntas douradas manualmente escritas em `docs/golden-questions.md`
- [x] F0.8 Atualizar skill `scan`: passo 0 = "se `atlas.repo_map` responder, use o grafo; senão, fluxo atual" (fallback preservado); `## Source` na página do vault; navegação por `find_symbol`/`symbol_context`/`who_calls` antes de implementar
  - [x] F0.8.1 Validado 2026-09-11 em 3 cenários: (a) `<project-a>` com atlas → `repo_map` + vault/qdrant; (b) `<project-b>` com tudo ligado, repo nunca mapeado → `repo_map` (branch feature indexada) + vault/qdrant; (c) `<project-c>` **só com o atlas parado** (qdrant/obsidian conectados) → "atlas fora do ar, li a árvore" + vault/qdrant gravados. Fallback puro confirmado

**Saída da fase:** grafo local com 2 repos, `who_consumes` funcionando, `scan` lendo do grafo.

## Processo de atualização contínua (trilha própria — MUITO importante)

> Separado da instalação (D12). Sem ele o atlas envelhece e as skills respondem sobre um mapa
> desatualizado. **U1–U3 validados em 2026-09-11**: refresh agendado via Task Scheduler (WSL),
> PAT somente-leitura, 14 snapshots do time reindexados sem intervenção, `install-check` verde.

- [x] U1 **Credencial do serviço** (D13): PAT **somente-leitura** em `~/.aidd/secrets/git-token` (600), coletado na etapa 6 do `install.sh`; o wrapper usa via `GIT_ASKPASS` e reescreve remotos ssh→https só no fetch. Sua chave pessoal fica fora do agendador. Validado: `fetch: ok (service)` nos 6 repos. Nota: fine-grained exige aprovação de admin na org — classic (escopo `repo`, expiração curta) serve como ponte; **GitHub App** é o alvo para o servidor (F1)
- [x] U2 **Agendador no host**: `aidd schedule install|status|remove|check [--fix]` — **systemd user timer preferido** (Linux e WSL com `systemd=true`; roda onde Docker e repos vivem, sem janela, `enable-linger`), Task Scheduler oculto (`conhost --headless`) como fallback no WSL sem systemd, cron por último; intervalo em `AIDD_REFRESH_INTERVAL_MINUTES` (.env, default 15); `flock` + `~/.aidd/logs/refresh.log` rotativo. Validado no WSL (`schtasks.exe` a partir do distro)
- [x] U3 **Observabilidade**: `aidd status` com idade e `trigger` (manual/scheduled/bootstrap); `install-check.sh` seção 6 falha se o último refresh > 2× intervalo
- [x] U2.1 Agendador dentro do WSL (D14): `systemd=true` + linger + autostart do distro (`.vbs` no Startup); task do Windows removida automaticamente; `aidd schedule check --fix` valida/repara. Validado em instalação limpa 2026-09-11
- [x] U3.1 Validação ponta a ponta (2026-09-11): instalação limpa → etapa 6 com PAT → task criada → refresh agendado reindexou 14 snapshots (`trigger=scheduled auth=service rc=0`) → `install-check.sh` verde
- [x] U3.2 Re-validação após o fix das gramáticas (2026-09-11 14:29, imagem offline): push em `<project-a>@feature/<ticket>` → timer systemd → `1 of 26 changed` → extract/resolve/write em 1 s (`orphans_deleted: 1`) → `rc=0` → `aidd status` com o SHA novo, `age=1m`, `trigger=scheduled`. **Trilha U1–U3 concluída.**
- [ ] U4 **Gatilho por evento (F3)**: webhook/CI em push de branch protegida → `aidd index <repo> --ref <branch>`; substitui o agendador no servidor central
- [ ] U5 **Fetch in-container para servidor/CI**: `fetch: true` + PAT via `git-askpass.sh` (já implementado, validar quando existir servidor)
- [ ] U6 **Portabilidade Linux / macOS** (só WSL foi validado; tudo que é WSL está atrás de `is_wsl()`)
  - Linux nativo: deve funcionar como está (systemd user timer → cron como fallback). Falta só **validar** em uma máquina (Ubuntu/Fedora com Docker Engine ou Docker Desktop)
  - macOS — ajustes necessários no `setup/aidd` e `install-check.sh` (bash 3.2 e utilitários BSD):
    - [ ] agendador: sem systemd/`loginctl` → hoje cai no `crontab` (funciona, mas pede permissão de Full Disk Access ao cron e não sobrevive bem a sleep); implementar **launchd agent** (`~/Library/LaunchAgents/com.aidd.refresh.plist`, `StartInterval`) como opção preferida no macOS
    - [ ] `flock` não existe no macOS → fallback com `mkdir` lock (ou `shlock`/`lockfile`)
    - [ ] `mapfile` exige bash ≥ 4 (macOS traz 3.2) → trocar por `while read`, ou exigir `brew install bash` e checar `BASH_VERSINFO` no início
    - [ ] `stat -c %s` / `stat -c %a` → `stat -f %z` / `stat -f %Lp` no BSD (helper `fsize()`/`fperm()` detectando `uname`)
    - [ ] `date -d "<ts>" +%s` → `date -j -f ... ` no BSD (helper `to_epoch()`), ou gravar epoch no log além do ISO
    - [ ] `sed -i` sem sufixo no `check --fix` (wsl.conf) é só WSL — ok; padrão `sed -i.bak && rm` já usado no `install.sh`
    - [ ] ssh-agent in-container (U5, só se `fetch: true`): no Docker Desktop macOS o socket é `/run/host-services/ssh-auth.sock`, não `$SSH_AUTH_SOCK`
    - [ ] `install-check.sh` seção 6: `schedule check` deve reconhecer launchd (`launchctl list | grep com.aidd.refresh`)
  - Indexer, compose, Neo4j, Qdrant e MCPs: idênticos nas 3 plataformas (rodam em containers) — sem ajuste

## Fase 1 — Micro completo (SCIP multi-linguagem + retrieval híbrido)

- [ ] F1.1 Integrar indexadores SCIP (Go, TS, .NET, Python) no `indexer/`; detecção automática de stack por manifest; config por repo (`.aidd/index.yaml`: excludes, conectores)
- [ ] F1.2 Conversor SCIP → grafo (definições, referências resolvidas, IMPLEMENTS/EXTENDS, tipos)
- [ ] F1.3 tree-sitter como fallback para linguagens sem SCIP (Vue SFC, SQL, YAML, templates)
- [ ] F1.4 Indexação incremental: `git diff` → pacotes tocados → reindex parcial; remoção de órfãos por snapshot `(repo, ref)`
- [ ] F1.5 Embeddings por **símbolo** (assinatura + docstring + corpo curto) no Qdrant, payload `{node_id, repo, ref, kind}`; trocar modelo para o de código
- [ ] F1.6 Sumários hierárquicos via Ollama (arquivo → módulo → repo) armazenados no grafo e no Qdrant
- [ ] F1.7 MCP `atlas`: `get_callers`, `get_callees`, `trace_flow(entry_point)`, `search(query)` híbrido (vetor → expansão k-hops → rerank)
- [ ] F1.8 Suporte a `ref`: indexar `main` (baseline) e `develop`; nós/arestas com `ref`; consultas com `ref` opcional (default: develop se existir)
- [ ] F1.9 Métricas de git como atributos: `last_touched`, `churn_90d`, `authors` (hotspots e "quem mexe aqui")
- [ ] F1.10 Nova skill `flow`: dado um entry point (endpoint/handler/job), narra o fluxo micro usando `trace_flow` + trechos
- [ ] F1.11 Tabela `index_runs` (repo, ref, sha, duração, contagens, erros) + comando `aidd status`
- [ ] F1.12 Ampliar perguntas douradas para 20; script `aidd eval` que roda todas e reporta recall

**Saída da fase:** qualquer repo do workspace indexável em 1 comando; `scan` e `flow` respondendo com fatos do grafo.

## Fase 2 — Macro completo (linker de contratos + governança)

- [ ] F2.1 Conector OpenAPI: specs → `HttpEndpoint`; rotas extraídas do código reconciliadas com a spec (divergência = alerta)
- [ ] F2.2 Conector mensageria: tópicos/filas em constantes, config e env (Kafka, RabbitMQ, SQS/SNS) → `PUBLISHES`/`SUBSCRIBES`; schemas de evento quando existirem
- [ ] F2.3 Conector infra: `docker-compose`, k8s/Helm, gateway → resolver `ENV_VAR → URL → repo` para ligar chamadas HTTP de saída ao repo alvo
- [ ] F2.4 Conector banco: migrations/ORM → `DbTable`, `READS/WRITES`; tabelas compartilhadas entre repos = aresta macro implícita
- [ ] F2.5 Confiança nas arestas (`exact | heuristic | llm`) + `evidence`; passada LLM só nos ambíguos; resultado vira nota de revisão no Obsidian (`<tenant>/_links-review.md`)
- [ ] F2.6 MCP `atlas`: `impact_analysis(symbol|endpoint|topic)` transitivo cross-repo, `repo_dependencies(repo)`, `workspace_map(tenant)`
- [ ] F2.7 Nova skill `impact`: dado um alvo, lista repos/fluxos afetados com confiança e evidência
- [ ] F2.8 Visualização: export do subgrafo para Obsidian (canvas/notas com wikilinks) ou HTML estático — leitura humana do macro
- [ ] F2.9 Perguntas douradas macro (≥ 15) + `aidd eval` cobrindo micro e macro

**Saída da fase:** mapa do workspace consultável; impacto cross-repo com evidência.

## Fase 3 — Central e contínuo (alvo final)

- [ ] F3.1 Servidor central (Neo4j + Qdrant + MCPs) com backup; compose "server profile"
- [ ] F3.2 Job de CI por repo: a cada merge em `main`/`develop` → `aidd index` → push para o central (runner self-hosted com cache de SCIP)
- [ ] F3.3 Linker agendado/por evento no central; relatório de novas arestas e divergências
- [ ] F3.4 Auth no MCP por tenant (token por dev/time atrás de reverse proxy); filtro de tenant injetado, nunca confiado ao cliente
- [ ] F3.5 Dashboard de cobertura/frescor: repos indexados, idade do índice, % de arestas macro por confiança
- [ ] F3.6 Retenção: manter N snapshots por `(repo, ref)`; GC de refs mortas
- [ ] F3.7 `install.sh` aponta `.mcp.json` para o central quando configurado; local continua como fallback offline

---

## Trilha paralela — Skills e fluxo de desenvolvimento

Encadeamento alvo (cada skill consome o grafo via MCP e escreve no Obsidian/Qdrant):

```
scan ──► flow / impact ──► refine-business ──► refine-tech ──► implement ──► review
 (fatos)   (micro/macro)     (card + contexto)   (spec técnica)   (harness)    (sênior)
```

- [x] S0 `scan` v1 com vault por projeto (`<tenant>/knowledge/<repo>/<repo>.md`) e `refine-business` v1 (Jira → candidatos via Qdrant → "o que fazer" por projeto → loop → `<tenant>/cards/<card>.md`)
- [ ] S0.1 Alinhar layout do vault: `scan` documenta `refine-business/` mas `refine-business` grava em `cards/` — escolher um e corrigir os dois SKILL.md
- [ ] S1 `scan` v2: lê do grafo, fallback ao fluxo atual; salva convenções com `source: graph|llm`
- [ ] S2 `flow`: entry point → narrativa do fluxo micro (F1.10)
- [ ] S3 `impact`: alvo → repos/fluxos afetados (F2.7)
- [ ] S4 `refine-business` v2 — pontos de encaixe do grafo na skill existente (sem mudar o gatilho):
  - Step 2 (cobertura): além de "tem conventions no Qdrant?", checar "está indexado no atlas?" (`atlas.repo_map`) e sugerir `aidd index`
  - Step 4 (projetos afetados): hoje é só busca vetorial nos sumários de convenções; passa a ser híbrido — vetor encontra símbolos/endpoints candidatos → `impact_analysis`/`who_consumes` expande para os repos ligados por contrato. Candidatos ganham `confidence` + `evidence`
  - Step 5 ("o que fazer"): citar o fluxo micro (`trace_flow`) e as arestas macro que justificam a coordenação entre projetos
  - Step 7: nota do card passa a incluir a **área de atuação delimitada** (repos, módulos, símbolos de entrada) — é a entrada do `refine-tech`
- [ ] S5 `refine-tech`: a partir da área delimitada, zoom-in com `flow`/`get_callers`; produz spec técnica (arquivos, contratos, testes, riscos, ADRs); validação humana explícita antes de seguir
- [ ] S6 `implement`: executa a spec no orquestrador escolhido (harness: testes, cobertura, lições → Qdrant)
- [ ] S7 `review`: contexto injetado (spec + diff + cobertura + convenções do grafo) → parecer sênior; PR
- [ ] S8 Definir contrato comum entre skills (frontmatter + formato da nota de saída) para que a saída de uma seja entrada da próxima

## Decisões pendentes

- [x] D1 Graph DB → **Neo4j Community** (ADR-001): Neo4j Community vs Memgraph (critério: MCP oficial, memória, licença para uso interno)
- [ ] D2 Orquestrador de execução (Fase S6): Claude Code (já usamos skills nesse formato) vs Cline/Roo Code (VS Code, MCP, modelos locais) vs Goose/Aider (CLI)
- [ ] D3 Estratégia de refs: sempre `main` + `develop`; feature branches sob demanda no `refine-tech`?
- [x] D7 Sem defaults de tenant: `AIDD_TENANT` vem do `install.sh` (`.env`), é `${AIDD_TENANT:?}` no compose e obrigatório no indexador (`auto` que não deriva = erro)
- [x] D6 Nomenclatura → **Atlas**: nome do database Neo4j e do MCP voltado a agentes (`atlas.*` nas skills); `neo4j/` continua sendo a pasta de infra; ferramentas de intenção substituem o Cypher bruto no F0.6
- [x] D14 Agendador dentro do WSL (systemd user timer), não no Windows: o ambiente inteiro vive no distro; Task Scheduler só como fallback sem systemd (e oculto)
- [x] D13 Credencial do refresh automático = PAT somente-leitura dedicado (não a chave pessoal); agendador = Task Scheduler no WSL / systemd em Linux; intervalo 15 min
- [x] D12 Instalação ≠ atualização: o bootstrap indexa os refs locais como clonados (sem fetch, sem credenciais); manter o atlas atualizado é um processo próprio (trilha "Atualização contínua"), rodando no host com as credenciais do dev
- [x] D8 Providers: **GitHub primeiro** (F1); o manifesto já aceita N fontes por tenant, então cada tenant pode combinar providers
- [x] D9 Fonte `local` sem espelhos: `git archive` das remote-tracking refs (read-only); espelhos bare só com providers remotos
- [x] D10 Defaults da política de refs: `main/master/develop` sempre, ativas ≤14 dias, ≤5 por repo, GC efêmeros 30 dias
- [x] D11 Áreas: seção opcional `areas:` no `atlas.yaml` (→ `Repo.area`, agrupa o `plan`); nós de domínio e Backstage/Compass adiados para F2
- [ ] D5 Idioma dos docs: schema e ADR já em inglês (padrão do projeto open source); traduzir `ROADMAP.md` quando estabilizar ou mantê-lo em PT como doc de trabalho interno
- [ ] D4 Modelo local mínimo para tarefas agênticas com tool-calling (avaliar Qwen-Coder ≥ 30B); 7B/14B ficam só para sumários e classificação
