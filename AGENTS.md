# AGENTS.md — porta de entrada do aidd-stack

Leia isto primeiro, seja você uma pessoa chegando ao projeto ou a IA dela. Em poucos minutos dá o contexto e diz
onde está o resto. Os docs de trabalho são em português; os docs públicos, em inglês, saem do H4.

## O que é

O aidd-stack é uma stack local para desenvolvimento assistido por IA num portfólio de vários repositórios. Ela
indexa o código de cada repo num **grafo** (Neo4j, database `atlas`). São dois níveis:

- **micro:** arquivos, símbolos, `CALLS` e `IMPORTS`;
- **macro:** as rotas HTTP que um serviço expõe, as chamadas que ele faz e as ligações entre serviços.

As ferramentas do grafo chegam às skills do processo (`scan` → `refine-business` → `refine-tech` → `implement`)
pelo MCP `atlas`. Junto vão um vault Obsidian, vetores no Qdrant e um serviço `knowledge` com o que o projeto
aprendeu.

A extração é **determinística**: tree-sitter hoje, SCIP como enriquecimento depois. LLM nunca é o parser, e por
três razões:

- o grafo tem de ser reprodutível, o mesmo commit dando o mesmo grafo;
- o grafo tem de ser medível, como no corpus;
- o grafo tem de ser barato de manter atualizado a cada push.

O SCIP entra por repo onde a resolução por nome não basta (ADR-002).

## Mapa do repo

| Caminho | O que tem |
|---|---|
| `setup/` | `install.sh` (instala e atualiza em `~/.aidd`), `install-check.sh` (saúde da instalação), o wrapper `aidd`, as skills (`scan`, `refine-business`) e um exemplo de convenção |
| `docker-compose.yml`, `gateway/`, `neo4j/`, `qdrant/`, `obsidian/`, `git/` | a infra: Neo4j com o esquema (`neo4j/SCHEMA.md`), Qdrant, os MCPs e o gateway nginx, tudo só em localhost |
| `indexer/` | o pacote `aidd-indexer`: a CLI `aidd`, o refresher (`aidd daemon`), o MCP `atlas` e o serviço `knowledge` |
| `indexer/aidd_indexer/core/` | o que é comum a todas as linguagens: descoberta, extração, resolução de `CALLS`, o extrator HTTP (`http_*`, `integrations.py`), o linker e a escrita do grafo |
| `indexer/aidd_indexer/languages/<lang>/` | Go, TS/JS, C# e Python: queries tree-sitter, símbolos, resolução e o scanner HTTP de cada uma (ADR-003) |
| `indexer/conventions/` | as convenções de arquitetura como extensões (a de referência é `dotnet-praticis`) |
| `indexer/tests/` | as fixtures por linguagem (`fixtures/*/expected.json`), os gabaritos do corpus (`corpus_expected/`) e os testes |
| `indexer/scripts/` | o corpus público (`http_corpus.py`, `corpus_metrics.py`, `corpus.sh`) e os testes (`test.sh`) |
| `docs/` | o ROADMAP, as decisões, o histórico, o guia do indexador, o relatório do corpus, as perguntas douradas, os ADRs e os handoffs |

## Arquitetura em uma figura

```
 repos do workspace ──(espelho bare, só leitura)──▶ refresher (aidd daemon, a cada 15 min)
                                                        │ tree-sitter por linguagem
                                                        ▼
            discovery → extract (símbolos, imports) → resolve (CALLS) → HTTP (rotas, chamadas)
                                                        │ convenções (papéis, camadas, violações)
                                                        ▼
                                  Neo4j "atlas" ◀── linker (CONSUMES, CALLED_FROM, DEPENDS_ON)
                                        │
                         MCP atlas (:3005, via gateway) ── 11 tools: atlas_status, repo_map, find_symbol,
                                        │                  who_calls, symbol_context, http_map, who_consumes,
                                        ▼                  impact_of, ref_diff, violations, cypher_readonly
                    skills do processo + MCP knowledge (:3006) + vault Obsidian + Qdrant
```

Cada nó e cada aresta carregam `tenant`, `repo`, `ref` e `commit_sha`; as arestas macro carregam `confidence` e
`evidence`. Um snapshot é um (repo, ref), e um snapshot escrito por outro build do indexador fica `outdated` até o
refresh reindexá-lo.

## Princípios

O texto completo está no ROADMAP, em "Princípios".

- **Independente do orquestrador:** só MCP e skills.
- **Extração determinística:** uma lacuna que pede tipo não declarado à vista vira `needs-resolver` para o F1.2, sem
  heurística.
- **Segredos nunca entram no índice:** só o nome da env var.
- **Cada fase fecha com perguntas douradas passando.**
- **Forma do código:**
  - complexidade ≤ 9 por função (`ruff C901`) e módulos de até 300 linhas;
  - comentários só com o porquê, sem referência a docs ou itens de plano.
- **Nenhum nome real de tenant, cliente ou projeto privado** em docs, código, testes ou fixtures. O repo é público.

## Como instalar, testar e medir

- **Instalar ou atualizar:** `./setup/install.sh` (pergunta pelo terminal), depois `./setup/install-check.sh`, que
  deve terminar em "All checks passed".
- **Testes do indexador:** `indexer/scripts/test.sh`, no container de teste, com o código da árvore montado.
- **Corpus HTTP (a régua do extrator):** `indexer/scripts/corpus.sh --baseline 2026-10-18-v2-baseline-28`.
  - Deve dar `0 repo(s) differ`, ou um diff julgado item a item.
  - O hold-out: `--holdout --baseline 2026-10-18-v2-holdout-26`.
  - Os clones ficam em `~/.cache/aidd-corpus`, e os números em `docs/corpus-report.md`.
- **Uma mudança no extrator segue o ciclo** do guia (`docs/indexer-evolution.md` §5):
  1. caso de fixture que falha sem a regra;
  2. corpus `--baseline`;
  3. julgamento na fonte;
  4. gabaritos (H2-D15);
  5. nova baseline.
- **Antes do merge**, validar também numa instalação ao vivo: dry-run do `main` contra a branch em cada snapshot
  (com `-w` no código montado) e fotos do grafo antes e depois.
- **Perguntas douradas:** `docs/golden-questions.md`, repetidas depois de mudanças no grafo, no linker ou no MCP.

## Onde estamos

- A **Fase 0** (fundação) está concluída.
- O **H2/F1.14** (o extrator HTTP medido num corpus público de 55 repos) fechou em 2026-10-19.
  - Precisão pela lista: 98–100 % em todas as linguagens.
  - Os números estão no relatório do corpus.
- **A ordem até o SCIP:**
  1. H4 fase 0a (esta reciclagem dos docs);
  2. **H5**, a refatoração do indexador sem mudar comportamento (`docs/handoffs/H5-indexer-refactor.md`);
  3. o hold-out novo;
  4. o P2 (o indexador em repo próprio);
  5. o SCIP (F1.1, F1.2).
- O estado do dia está no ROADMAP, em "Onde estamos".

## Onde achar cada coisa

| Pergunta | Onde |
|---|---|
| O que está aberto, em que ordem | `docs/ROADMAP.md` |
| Por que tal escolha | `docs/decisions.md` e `docs/adr/` (ADR-002 tree-sitter × SCIP, ADR-003 módulos por linguagem) |
| O que aconteceu e quando | `docs/history.md`; o texto antigo completo está no git (`git show 1d73bb0:docs/ROADMAP.md`) |
| Como o indexador decide (regras, o ciclo de uma mudança, o mapa do código) | `docs/indexer-evolution.md` |
| Os números do extrator HTTP e o que falta | `docs/corpus-report.md` |
| O modelo do grafo | `neo4j/SCHEMA.md` |
| O processo de indexação (fontes, refs, refresh) | `docs/indexing-process.md` |
| O contrato do vault e do conhecimento | `docs/knowledge-contract.md` |
| Um trabalho em curso | `docs/handoffs/` (ativos: H3, H4, H5; fechados: H1, H2, reduzidos a resumo) |

## Para quem contribui (pessoa ou agente)

- **Commits:** assunto convencional de uma linha que nomeia a capacidade, sem corpo e sem trailer de atribuição;
  assinados.
- **O código novo já nasce nas metas** de forma; o H5 leva o código antigo até elas.
- **Repos do corpus são de terceiros:** nunca rode código deles. Leia e meça pelo container do indexador.
- **Comandos longos** (corpus, refresh) rodam em segundo plano. Não edite o indexador nem os gabaritos durante uma
  rodada do corpus, porque o código está montado nos containers.
- **Português na conversa e nos docs de trabalho;** inglês no código, nos commits, nos PRs, no relatório do corpus e
  nos docs públicos.
