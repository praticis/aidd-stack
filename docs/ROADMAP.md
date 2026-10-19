# AIDD Stack — Roteiro de evolução (code graph + skills)

> Documento vivo. Marque `[x]` ao concluir. Atualize a seção **Onde estamos** a cada sessão
> para que qualquer agente/pessoa retome do ponto certo.

## Onde estamos

- **Fases:**
  - a **Fase 0** (fundação) está concluída;
  - a **Fase 1** começou em 2026-10-13 pelo F0.7.3;
  - o **F1.14** (o extrator HTTP medido no corpus público, o H2) fechou em 2026-10-19.
- **Os marcos e o porquê de cada escolha:** `docs/history.md`, um marco por linha, e `docs/decisions.md`.
- **Medir o extrator:**
  - `indexer/scripts/corpus.sh --baseline 2026-10-18-v2-baseline-28`;
  - o hold-out: `--holdout --baseline 2026-10-18-v2-holdout-26`;
  - os números estão em `docs/corpus-report.md`.
- **Em curso:**
  - o PR #5 (`feature/f114-close`: o fechamento do F1.14), validado numa instalação ao vivo e esperando o merge;
  - a fase 0a do H4 (os docs de trabalho reciclados): feita em 2026-10-19 numa branch local, esperando o merge do #5.
- **A ordem até o SCIP (H5-D1):** H4 fase 0a → H5 (refatoração do indexador, `docs/handoffs/H5-indexer-refactor.md`,
  sem mudar comportamento) → hold-out novo, medido uma vez, e o handoff dele (H2-D21) → P2 (o indexador em repo
  próprio) → SCIP (F1.1, F1.2).
- **Handoffs ativos:** H3 (eficiência do dev com IA), H4 (docs públicos e o indexador em repo próprio) e H5.
  Fechados: H1 e H2.
- **Candidatos:**
  - `dispatch` para validators alcançados pelo pipeline do barramento (`SendAsync(cmd)` → `AbstractValidator<cmd>`);
  - re-rodar a Q4 .NET com o despacho.
- **Pendências sem bloqueio:**
  - o `raw_path` de uma chamada por wrapper com base terminada em `/` sai com barra dupla (o path normalizado está
    certo);
  - PAT com acesso à org do tenant;
  - validação em WSL (SO14);
  - lacunas do feedback de code review: Go `who_calls` entre repos, mensageria por tipo de evento.

## Princípios (não negociáveis)

- Camada de conhecimento (grafo + vetores + vault) é **independente do orquestrador**: só MCP + skills. Cline, Roo, Goose, Claude Code ou Aider consomem o mesmo backend.
- Extração **determinística** (SCIP / tree-sitter). LLM só para sumarizar e desambiguar; nunca como parser primário.
- Todo nó/aresta carrega `tenant`, `repo`, `ref` (branch), `commit_sha`, `indexed_at`; arestas macro carregam `confidence` + `evidence`.
- Segredos nunca entram no índice (extrair o *nome* da env var, nunca o valor).
- Cada fase termina com **perguntas douradas** passando (recall medido, não sentido).
- **Forma do código** (decidido em 2026-10-18; o H5 leva o código atual até ela): complexidade ciclomática de **um
  dígito** por função (≤ 9, `ruff C901`) e no máximo **300 linhas por módulo**, contadas no arquivo inteiro. O CI
  relata hoje e passa a bloquear quando o autor decidir. Código novo já nasce dentro das metas.
- **Comentários só com o porquê que o código não diz:** um contrato, um caso de borda, a razão de uma ordem. Sem
  referência a docs nem a itens de planejamento (ROADMAP, `F1.x`, decisões, ADRs, seções de guia), porque os docs
  mudam e o código não deve apontar para eles. Sem nome de projeto: o exemplo descreve a forma do código, e só se
  nomeia o framework ou a biblioteca que define o comportamento.
- **Nenhum nome real de tenant, cliente ou projeto privado** em docs, código, testes ou fixtures. O repositório é
  público. Onde um exemplo for preciso, usa-se um nome neutro (`orders-api`, `PARTNER_API_URL`).

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

### Checklist de validação do compose (validado 2026-09-10/11; `install-check.sh` cobre os itens 2–7 a cada upgrade)

Atalho: `~/.aidd/install-check.sh` (copiado pelo `install.sh`) roda os itens 2–7 abaixo e imprime OK/FAIL por check.


- [x] `.env` tem `NEO4J_USER=neo4j` e `NEO4J_PASSWORD=<senha>` (o `install.sh` gera; se o volume já existia com outra senha: `docker compose down -v` e subir de novo — dev only)
- [x] `docker compose up -d --build` sem erro; `docker compose ps` mostra `neo4j` *healthy* e `neo4j-init` como *Exited (0)*
- [x] `docker logs aidd-neo4j-init` sem erro (o cypher-shell é silencioso em sucesso — vazio é bom; erro de sintaxe aparece aqui)
- [x] **Neo4j Browser** em <http://localhost:7474> (login com o `.env`): `SHOW CONSTRAINTS` lista 14 constraints; `SHOW INDEXES` inclui `symbol_fulltext`; `RETURN apoc.version()` responde
- [x] `docker logs aidd-mcp-atlas` mostra o Uvicorn escutando em 0.0.0.0:3000; `curl -s http://localhost:3005/healthz` devolve `{"status":"ok","neo4j":true,...}`
- [x] (debug) `docker compose --profile debug up -d mcp-neo4j` → `curl -s -o /dev/null -w "%{http_code}" http://localhost:3004/mcp/` devolve um status HTTP
- [x] No Claude Code, com `setup/.mcp.json` aplicado: `/mcp` lista `atlas`; pedir "rode `get_neo4j_schema`" retorna vazio (grafo sem dados) sem erro de autenticação
- [x] `install.sh` re-executado sincroniza `~/.aidd/neo4j/` e o `docker-compose.yml` novo
- [x] Docs: `git rm docs/graph-schema.md` (movido para `neo4j/SCHEMA.md`)

---

## Fase 0 — Fundação (PoC ponta a ponta, 2 repos)

Objetivo: provar micro + macro com o mínimo: dois repos (Go + Node) que se falam por gRPC/HTTP, e uma pergunta `who_consumes` respondida a partir do grafo.

- [x] F0.1–F0.2 Neo4j Community no compose (D1) e o esquema em `neo4j/SCHEMA.md`
- [x] F0.3 O indexador `indexer/`: `aidd index`, tree-sitter → nós micro, `MERGE` idempotente, GC de órfãos e
  `IndexRun`. Também: o F0.3.1 (validado no atlas real), o F0.3.2 (idempotência e GC), o F0.3.5 (processo de
  indexação: `atlas.yaml`, `plan`/`bootstrap`/`refresh`, `docs/indexing-process.md`), o F0.3.6 (política de refs por
  repo) e o F0.3.7a (wrapper de host, instalação sem fetch, D12)
- [x] F0.4 O extrator de integrações HTTP (`core/integrations.py` + `languages/<lang>/http.py`). Também:
  - F0.4.1, validado no portfólio;
  - F0.4.2, as fixtures do padrão do autor (.NET: `dotnet-praticis`);
  - F0.4.3, o corpus público, H2a e H2b: `docs/corpus-report.md`, `docs/handoffs/H2-roadmap.md`;
  - F0.4.4, o refactor do ADR-003;
  - F0.4.5, as convenções e o `Violation`.
- [x] F0.5 O linker: `CONSUMES`/`CALLED_FROM` por `path_key` e método, com desempate por hints. Também o F0.5.1
  (validado; `DEPENDS_ON` por manifesto)
- [x] F0.6 O MCP `atlas`, com 11 tools (`indexer/aidd_indexer/mcp/server.py`). Também o F0.6.1, validado no Claude Code
- [x] F0.7 As 5 perguntas douradas respondidas pelo grafo (`docs/golden-questions.md`). Também:
  - F0.7.1–F0.7.2b, `CALLS` pelo tipo do receptor em Go e C#;
  - F0.7.3, interfaces Go e o despacho do mediator.
- [x] F0.8 A skill `scan` sobre o atlas, com fallback. Também o F0.8.1, validado em 3 cenários

**Saída da fase:** grafo local com 2 repos, `who_consumes` funcionando, `scan` lendo do grafo. **Obtido (2026-10-03):** 8 repos / 28 snapshots do portfólio + par .NET de referência; 130 endpoints, 90 `CONSUMES` exatas, 45 `DEPENDS_ON`; 11 tools no MCP; Q1–Q5 respondidas pelo grafo em Go e .NET sem leitura de código; 40 testes, corpus de 15 repos como regressão.

## Processo de atualização contínua (trilha própria — MUITO importante)

> **2026-10-12 — D15:** a atualização contínua saiu do host. O serviço `refresher` do compose
> (`aidd daemon`) substitui o agendador (U2, U2.1, D14) e o fetch no host (D12/D13 seguem valendo
> no princípio: PAT somente-leitura, chave pessoal fora); U6 deixa de ser necessário. Itens abaixo
> ficam como histórico. Detalhes na trilha **Segurança e operação**.
>
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
- [x] U5 **Fetch in-container**: virou o caminho padrão com o refresher (D15) — espelho por repo, PAT como arquivo via `git-askpass.sh`. Validado com remoto local no e2e; **falta validar contra o GitHub com um PAT real**
- [x] U6 **Portabilidade Linux / macOS** — resolvido pelo D15: nada de agendador nem bash GNU no host (o `aidd` virou cliente fino compatível com bash 3.2). A lista abaixo fica como histórico
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

## Segurança e operação (trilha própria)

> Pré-requisito para adoção em organizações. Revisão de 2026-10-12: o stack nasceu como ferramenta
> local de um dev e expunha mais do que devia (ver "Onde estamos"). Ordem: fechar o que estava exposto,
> tirar estado e credenciais do host, depois governança.

Feito (2026-10-12, validado no e2e isolado em macOS/Docker Desktop):

- [x] SO1 **Exposição**: toda porta publicada em `AIDD_BIND_ADDRESS` (default `127.0.0.1`); os MCPs não publicam nada — o **`mcp-gateway`** (nginx fixado) os serve nas mesmas portas (3001/3002/3003/3005, `.mcp.json` não muda) e devolve 403 quando o `Host` não é localhost/127.0.0.1/[::1] ou quando um navegador manda `Origin` de outro site (DNS rebinding). O `atlas` também valida `Host`/`Origin` sozinho (SDK MCP). `install-check.sh` confere portas e recusas
- [x] SO2 **Credenciais**: Qdrant exige `QDRANT_API_KEY` (gerada pelo `install.sh`), CORS desligado; `mcp-git` sem chave ssh/ssh-agent (operações locais; push/pull no terminal do dev); o PAT do refresher entra como secret em arquivo (`/run/secrets/git-token`), nunca em variável de ambiente
- [x] SO3 **Isolamento de tenant (lógico)**: `cypher_readonly` continua oferecido nos dois modos (default `ATLAS_RAW_CYPHER=on`), mas Cypher livre não fica preso a um tenant — num atlas multi-tenant cujos tenants não podem se ver (vários clientes na mesma máquina), `ATLAS_RAW_CYPHER=off` o retira; Neo4j carrega só `apoc.version`, `apoc.meta.*` e os utilitários puros `apoc.coll/text/map.*` (sem `apoc.load`/`export`/`cypher.*` → sem acesso a arquivo/URL nem Cypher dinâmico); telemetria do Neo4j desligada
- [x] SO4 **Supply chain (parcial)**: imagens e pacotes com versão fixa (neo4j 5.26.30, qdrant v1.19.1, node 24.21.0, python 3.12.15, nginx 1.28.0, `@cyanheads/git-mcp-server@2.15.3`, `mcp-obsidian@0.8.2`, `mcp-proxy@6.7.16`, `mcp-server-qdrant==0.8.1`, `mcp-neo4j-cypher==0.6.0`); o obsidian não baixa mais do npm a cada start
- [x] SO5 **Refresher em container (D15)**: `aidd daemon` no compose (restart unless-stopped, jitter ± 10 %, SIGTERM termina o snapshot em curso, limites de CPU/memória, log rotativo); `refresh` cobre todos os tenants; workspace **só leitura** + espelho bare por repo (`core/mirror.py`): o clone do dev nunca recebe `FETCH_HEAD`, refs ou arquivos de root; containers como `AIDD_UID`/`AIDD_GID`; `aidd` do host vira cliente fino (bash 3.2) — `schedule install|status|check --fix` gerenciam o container e removem agendadores antigos; `install.sh` migra `fetch: false` → `true` nos manifestos gerados
- [x] SO6 **Frescor visível**: `status.json` + healthcheck (`aidd daemon-health`), `RefreshState` por tenant no grafo, `atlas_status.refresh.stale` (> 2 intervalos sem rodar) e a skill `scan` avisa; `install-check` confere a idade por tenant; idade de snapshot corrigida

Em aberto:

- [ ] SO7 **Isolamento forte entre tenants**: hoje Neo4j, Qdrant e vault são compartilhados (Community não tem RBAC nem vários bancos) e qualquer tool aceita `tenant`. Para quem atende várias organizações na mesma máquina: um stack por tenant (projeto compose com portas próprias) ou, no servidor (F3.4), tenant injetado pelo token
- [ ] SO8 **Autenticação nos MCPs** (token por dev no gateway; hoje a defesa é localhost + Host/Origin) — liga com F3.4; cuidado: o token não pode ir no `.mcp.json` distribuído para dentro dos repos
- [ ] SO9 **Prompt injection e memória envenenada**: código de terceiros, Jira e notas entram no contexto, e o que o agente grava no vault/Qdrant volta como "convention" em toda sessão. Proveniência nas lições (sessão, repo, sha), revisão humana antes de virar convenção, skills tratando esse conteúdo como dado — para a memória, o mecanismo é a trilha **Conhecimento do projeto** (evidência por insight, só humano promove a `accepted`, K5)
- [ ] SO10 **Supply chain completo**: digests (`@sha256`) nas imagens, lock com hashes (Python `--require-hashes`, npm `package-lock`), SBOM + scan (Trivy/Grype) no CI, Renovate para bumps deliberados; dependências do `pyproject.toml` do indexer ainda são faixas
- [ ] SO11 **Backup/restore**: o grafo e os espelhos se refazem; as lições/insights do Qdrant e o vault **não** (`docker compose down -v` apaga as lições). Snapshot do Qdrant agendado + documentar o que é descartável
- [ ] SO12 **Escala com N devs**: N laptops × M repos a cada 15 min batem no rate limit secundário do GitHub; backoff em falha de fetch; servidor central (F3) para organizações maiores. Espelhos dobram o disco dos repos — GC de espelhos de repos que saíram do workspace
- [x] SO13 **Skill indexa sob demanda** (2026-10-12): repo fora do atlas → a `scan` roda `~/.aidd/aidd refresh --tenant <t> --repos <repo> --wait 300` (o mesmo plano do refresher: branch padrão + ativas; espera um refresh em curso; não conta como rodada do refresher nem faz GC; repo ausente/excluído = erro com o motivo) e, para a branch em que vai trabalhar, `aidd index <repo> --ref <branch> --ephemeral`; `allowed-tools` da skill libera só esses dois comandos (nunca `aidd:*`)
- [ ] SO14 **Validar em WSL e Linux nativo** (o e2e foi em macOS): `AIDD_UID`/permissões do workspace (umask 077 deixa o container sem leitura), autostart do Docker; PAT real contra o GitHub (U5)
- [ ] SO15 **Fluxo de dados / threat model** para quem adota: o que sai da máquina (o que o LLM lê; embeddings são locais; telemetria desligada), onde ficam segredos, o que cada container pode tocar. `mcp-neo4j` (perfil debug) segue com Cypher de escrita em `127.0.0.1:3004` — só para depuração

## Fase 1 — Micro completo (SCIP multi-linguagem + retrieval híbrido)

- [ ] F1.1 Integrar indexadores SCIP (Go, TS, .NET, Python) no `indexer/`; detecção automática de stack por manifest; config por repo (`.aidd/index.yaml`: excludes, conectores)
- [ ] F1.2 Conversor SCIP → grafo (definições, referências resolvidas, IMPLEMENTS/EXTENDS, tipos) + resolvedor para a
  camada HTTP: um gancho no `http_base` (por nome por padrão, SCIP quando a snapshot tem índice) consultado só nos
  pontos de indecisão que o F1.14 registrou como `needs-resolver` — sem índice, o HTTP segue como hoje (ADR-002,
  decisão 3)
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
- [ ] F1.13 **Repos grandes (escala da extração)**: o grafana (24 mil arquivos) é morto por memória a 7,7 GB no Docker
  Desktop (corpus v2, 2026-10-15), porque `extract_tree` guarda a árvore tree-sitter e o texto de **todos** os arquivos
  até o fim — só a extração HTTP precisa delas; o `Resolver` lê dados por arquivo (`namespaces`, `facts`). Primeiro
  medir a memória por fase (discover / extract / http / resolve / escrita) no grafana; depois, em ordem de custo:
  1. soltar a árvore de cada arquivo assim que nada mais a lê — a extração HTTP diretório a diretório (as constantes e
     o scan já são por diretório);
  2. lotes por módulo (pacote Go, `.csproj`, workspace do `package.json`), cada lote gravado no grafo, e as arestas
     entre lotes resolvidas no fim só com a tabela de símbolos — o mesmo recorte que o F1.4 reindexa e que o SCIP
     indexa por projeto (F1.1);
  3. recorte por repo no `atlas.yaml` (subpastas como unidades, excludes) para monorepos em que só uma parte interessa.

  Restrição para quem vier antes: o grafo de montagem do HTTP (H2b) cruza arquivos — deve trabalhar com um resumo por
  arquivo (quem monta o quê, com que prefixo), nunca segurando árvores de outros diretórios. **Pronto quando** o
  grafana indexa sob um teto fixo de memória (ex.: 2 GB) e, num repo médio, a extração em lotes é idêntica à inteira
  (o corpus HTTP com `--baseline` dá o diff). Medir junto o custo do HTTP em repos sem rotas que ele leia (netbox: 49 s
  de 107 s com 0 rotas e 0 chamadas no corpus v2; zulip 17 s de 47 s)
- [x] F1.14 **Extrator HTTP: o que o H2 deixou.** Fechado em 2026-10-18, em 11 incrementos, e no dia seguinte veio o
  12, na validação do PR #5. Cada item terminou com regra com fixture e corpus julgado, ou com limitação registrada no
  guia.
  - **Números finais e destino de cada lacuna:** `docs/corpus-report.md`, "Closing F1.14 and H2".
  - **Regras:** `docs/indexer-evolution.md` §3.
  - **Marcos:** `docs/history.md`.
  - **Mudanças de escopo:**
    - o hold-out novo foi para depois do H5 (H2-D21);
    - o catálogo de frameworks como dado e os limiares do `built_bundle` foram para o H5;
    - o Django ficou fora (o portfólio é FastAPI/Flask);
    - pastas de app de teste com nome de produção ficam para a config por repo do F1.1.
  - **O que pede tipo inferido** é `needs-resolver`, para o F1.2.

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
- [x] S0.1 *(2026-10-12: a `scan` documenta `cards/`, que é onde a `refine-business` grava)* Alinhar layout do vault: `scan` documentava `refine-business/` mas `refine-business` grava em `cards/` — escolher um e corrigir os dois SKILL.md
- [ ] S1 `scan` v2: lê do grafo, fallback ao fluxo atual; salva convenções com `source: graph|llm`
- [ ] S2 `flow`: entry point → narrativa do fluxo micro (F1.10)
- [ ] S3 `impact`: alvo → repos/fluxos afetados (F2.7)
- [ ] S4 `refine-business` v2 — pontos de encaixe do grafo na skill existente (sem mudar o gatilho):
  - Step 2 (cobertura): além de "tem conventions no Qdrant?", checar "está indexado no atlas?" (`atlas.repo_map`) e sugerir `aidd index`
  - Step 4 (projetos afetados): hoje é só busca vetorial nos sumários de convenções; passa a ser híbrido — vetor encontra símbolos/endpoints candidatos → `impact_analysis`/`who_consumes` expande para os repos ligados por contrato. Candidatos ganham `confidence` + `evidence`
  - Step 5 ("o que fazer"): citar o fluxo micro (`trace_flow`) e as arestas macro que justificam a coordenação entre projetos
  - Step 7: nota do card passa a incluir a **área de atuação delimitada** (repos, módulos, símbolos de entrada) — é a entrada do `refine-tech`
- [ ] S5 `refine-tech`: a partir da área delimitada, zoom-in com `flow`/`get_callers`; produz spec técnica (arquivos, contratos, testes, riscos, ADRs); validação humana explícita antes de seguir
- [ ] S6 `implement`: executa a spec no orquestrador escolhido (harness: testes, cobertura, lições → `record_insight`, trilha **Conhecimento do projeto**)
- [ ] S7 `review`: contexto injetado (spec + diff + cobertura + convenções do grafo + insights `accepted`/`enforced` da área) → parecer sênior; PR
- [ ] S8 Definir contrato comum entre skills (frontmatter + formato da nota de saída) para que a saída de uma seja entrada da próxima — a parte do conhecimento (índice do projeto + nota de insight) é o K1
- [ ] S9 (handoff H3) Medir o efeito do atlas e do conhecimento no desenvolvimento com IA — tokens, tempo, completude e defeitos, em tarefas reais dentro de um repo e entre repos, com e sem a stack (`docs/handoffs/H3-ai-dev-efficiency.md`). Depois do H2b, em outro processo

## Conhecimento do projeto (trilha própria)

> Cada projeto tem uma **porta de entrada** no vault (o índice que a `scan` cria) e uma **base de
> conhecimento** que as etapas do processo alimentam e consultam: o que aparece em code review, Sonar,
> ferramentas de segurança, incidentes e decisões vira insight filtrado, para o problema não se repetir
> e para o review já saber o que olhar. Não é uma skill (D16): é um mecanismo da stack que `scan`,
> `refine-business`, `refine-tech` e `implement` usam pelo mesmo contrato. A skill faz a parte que exige
> julgamento (o que vale registrar, com que evidência); a stack faz a determinística (dedup, contagem,
> nota, índice, Qdrant, regras de status).
>
> O que o processo **exige** (cobertura mínima, tentativas do harness, quando pedir ADR, quando um
> insight vira `recurring`) fica no `policy.yaml` (D17), ao lado do `atlas.yaml`: o `atlas.yaml` diz como
> ler o código, o `policy.yaml` diz o que o processo exige. A `scan` descreve o projeto; a política é
> decisão humana e não é descoberta.

Layout no vault:

```
<tenant>/knowledge/
├── <repo>/
│   ├── <repo>.md            índice: seções fixas da scan + bloco de conhecimento gerado
│   └── insights/<slug>.md   um insight por nota (frontmatter)
└── shared/insights/         o que vale para vários repos do tenant
```

Ciclo de um insight:

```
observed ──► recurring ──► accepted ──────────► enforced
(1 vez)      (N vezes)     (humano aprovou:     (virou regra checável:
                            o agente segue)      violations / lint)
        └──────────────► archived (descartado, ou sem ocorrência há muito tempo)
```

- [x] K1 *(2026-10-13: `docs/knowledge-contract.md`, contrato v1)* **Contrato do vault** (fecha o S8 para o conhecimento): esqueleto do índice — seções fixas da `scan` (inclusive a política efetiva do repo, só leitura: muda-se no `policy.yaml`) + bloco entre `<!-- aidd:knowledge:start -->`/`<!-- aidd:knowledge:end -->`, gerado a partir das notas e nunca editado à mão; formato da nota de insight — frontmatter `topic` (vocabulário controlado: `architecture`, `review`, `quality`, `security`, `incident`, `decision`, `business`; extensível por um registro de tópicos, não texto livre — evita `security`/`segurança`/`sec`), `status`, `severity`, `scope` (`repo`|`shared`), `occurrences`, `first_seen`/`last_seen`, `evidence[]` (PR, arquivo:linha, sha, ferramenta, sessão), `applies_to` (arquivos, roles, símbolos); payload no Qdrant `{project, type: insight, topic, status}`
- [x] K1.1 *(2026-10-13: `core/policy.py`, `aidd policy show|check`, `install.sh` cria a partir de `indexer/policy.example.yaml`, `install-check` valida)* **`policy.yaml`** em `~/.aidd` (D17), com camadas como o `atlas.yaml`: defaults embutidos → tenant → área → repo (`overrides`), cada nível sobrescrevendo só o que declara. Conteúdo inicial: `coverage` (`min`, `new_code_min`), `harness` (`max_attempts`), `review` (`spec_approval`, `adr_when`), `knowledge` (`recurring_after`, `archive_after_days`) — tudo o que seria número fixo no código. Validado com erro claro (como o `ConfigError` do `atlas.yaml`); `install.sh` cria um exemplo comentado; `aidd policy show <repo>` imprime a política efetiva com a origem de cada valor
- [x] K2 *(2026-10-13: `aidd_indexer/knowledge/`, serviço `mcp-knowledge` na porta 3006 do gateway)* **Serviço `knowledge`** no compose (mesma imagem do indexer, atrás do `mcp-gateway`; o único que escreve conhecimento no vault e no Qdrant — o atlas continua só leitura). Três tools:
  - `policy_for(repo)` → a política efetiva, já combinada, com a origem de cada valor (default/tenant/área/repo) — as skills não fazem o merge das camadas
  - `insights_for(repo, files?, roles?, topic?)` → `accepted`/`enforced` como regra, `observed`/`recurring` como contexto (rotulados: dado, não instrução)
  - `record_insight(repo, topic, summary, evidence, applies_to, severity)` → dedup (Qdrant por similaridade + mesmo tópico), incrementa ou cria a nota, `recurring` ao atingir `knowledge.recurring_after` ocorrências (política; default 3), reconstrói o bloco do índice, espelha no Qdrant; nenhuma tool promove para `accepted`
  - `refresh_index(repo)` → reescreve só o bloco `aidd:knowledge` a partir das notas (a `scan` chama ao terminar a página; uma página nova já nasce com o que foi gravado antes)
  - Testes: dedup, reconstrução do índice preservando as seções da `scan`, idempotência
- [x] K3 *(2026-10-13: skill reescrita e validada na instalação real — migração, repetição em outro idioma, página do zero)* `scan` gera o esqueleto do índice e mostra o bloco de conhecimento; a lição de fim de tarefa (hoje `qdrant-store` direto) passa a ser `record_insight`
- [ ] K4 *(com a revisão da `refine-business`)* `refine-business` adota o contrato: consulta incidentes/decisões dos projetos afetados, registra as decisões de negócio do card. `refine-tech` (S5) e `implement` (S6) já nascem com ele: riscos conhecidos da área na spec; `accepted`/`enforced` como checklist antes de codar e antes do PR
- [ ] K5 *(nasce com a `refine-tech`, S5)* **Promoção com humano dentro do processo**: a `refine-tech` mostra os `observed`/`recurring` que tocam a área delimitada ("apareceu 3×, vira regra?") e grava a aprovação (`accepted`, quem e quando); editar o frontmatter no Obsidian vale igual. Fecha a parte de memória do SO9
- [ ] K6 *(nasce com a `implement`, S6)* Fontes dentro da `implement`, onde o motivo de um erro aparece: (1) **reprovação no review** (o parecer sênior que devolve para a execução — o motivo é o insight); (2) **escalada do harness** (`harness.max_attempts` esgotado: o que o modelo não conseguiu corrigir sozinho e por quê); (3) **comentários de review do PR** ao tratar o feedback (`gh`). Em todas, registra só o que não é óbvio
- [ ] K7 *(quando houver scanner no CI dos tenants)* `aidd ingest <arquivo.sarif>` (Semgrep, CodeQL, Trivy, Snyk): agrupa findings por regra × repo, grava `observed` com contagem e evidência — o bruto fica na ferramenta; roda no CI ou pelo refresher. Sonar pela API depois
- [ ] K8 *(depois da Fase 1)* `enforced`: insight verificável no grafo vira regra da convenção e aparece em `violations`; o que não é verificável fica como checklist
- [ ] K9 *(com volume de insights; backup junto do SO11)* Envelhecimento e backup: `last_seen` mais antigo que `knowledge.archive_after_days` sem novas ocorrências perde peso e vai para `archived`; notas e coleção de insights não se refazem a partir do código → entram no backup (SO11)
- [ ] K10 Política dentro do repo (`.aidd/policy.yaml`, lida do espelho na branch padrão): em organizações, a política no `~/.aidd` é de cada dev e dois devs podem trabalhar com thresholds diferentes; no repo ela vale igual para todos e só muda por PR (review humano). Camada acima de `overrides` do repo; depois do K1.1 provado

## Publicação e documentação (trilha própria)

> O repo é público e o README tem uma linha. Esta trilha dá aos dois repositórios — o aidd-stack e o indexador, que
> sai para um repo próprio — documentação para quem chega, em inglês, português, espanhol e chinês. Decisões, fronteira
> entre os repos e ordem: `docs/handoffs/H4-public-docs.md`.

- [ ] P0 Reciclar os docs de trabalho (H4 passo 0, pedido em 2026-10-18): a verdade atual separada do histórico; um `AGENTS.md` na raiz como porta de entrada para um colaborador e a IA dele; o log do ROADMAP condensado em `docs/history.md`; as decisões destiladas em `docs/decisions.md`; o relatório do corpus só com o método, a baseline vigente e as lacunas; de ~600 KB para no máximo ~150 KB. Fase 0a logo depois do fechamento do F1.14; fase 0b (o guia do extrator) depois do H5
- [ ] P1 Decisões do H4 (H4-D1…D12, nome do repo do indexador, revisores por idioma) e esboço da arquitetura dos docs — pode correr em paralelo ao H2b
- [ ] P2 Indexador em repo próprio: `filter-repo` com histórico auditado, imagem multi-arquitetura no GHCR, `knowledge` e política no aidd-stack, esquema aplicado pelo indexador; regressão = testes, corpus idêntico e instalação limpa do aidd-stack com a imagem publicada. Depois do merge do H2b
- [ ] P3 Conteúdo em inglês dos dois repos (README + `docs/en/`), validado por quem nunca viu o projeto
- [ ] P4 Idiomas: glossário, guia de estilo, `i18n_check.py` no CI; traduções por camada em pt-BR, es e zh-CN
- [ ] P5 Assets visuais (manifesto `docs/assets/README.md`), arquivos de comunidade, configurações do GitHub e primeira release dos dois repos
- [ ] P6 *(opcional)* Site de docs, quando a navegação pedir

## Decisões pendentes

As decididas (D1, D3, D6–D17) estão em `docs/decisions.md`.

- [ ] D2 Orquestrador de execução (Fase S6): Claude Code (já usamos skills nesse formato) vs Cline/Roo Code (VS Code, MCP, modelos locais) vs Goose/Aider (CLI)
- [ ] D5 Idioma dos docs: schema e ADR já em inglês (padrão do projeto open source); traduzir `ROADMAP.md` quando estabilizar ou mantê-lo em PT como doc de trabalho interno — proposta no H4 (H4-D1): inglês como fonte dos docs públicos, traduções em pt-BR, es e zh-CN; ROADMAP e handoffs seguem em PT
- [ ] D4 Modelo local mínimo para tarefas agênticas com tool-calling (avaliar Qwen-Coder ≥ 30B); 7B/14B ficam só para sumários e classificação
