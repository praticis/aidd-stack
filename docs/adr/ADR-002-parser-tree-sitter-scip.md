# ADR-002 — Parser base do indexador: tree-sitter agora, SCIP como enriquecimento

**Status:** aceito · **Data:** 2026-09-14 · **Fase:** 0 (revisar em F1.2) · **Registra:** o princípio "extração determinística (SCIP / tree-sitter)" do ROADMAP

## Contexto

O indexador precisa transformar dezenas de repositórios (Go, .NET, Node/TS, Python), em várias
branches cada, num grafo micro (símbolos, chamadas, imports) e macro (rotas HTTP expostas, chamadas
de saída), e manter isso atualizado a cada 15 minutos rodando no Docker de cada dev — sem
credenciais de registries privados dentro do container e sem exigir que o repositório compile.

Duas famílias de tecnologia poderiam produzir o micro:

- **tree-sitter**: parser incremental por arquivo, gramáticas para todas as linguagens alvo numa
  única biblioteca (`tree-sitter-language-pack`), sem resolução de tipos. Extrai definições,
  chamadas por nome e imports; a resolução de `CALLS` é heurística (mesmo arquivo → mesmo módulo →
  nome único no repo).
- **SCIP** (Sourcegraph Code Intelligence Protocol): *formato de índice* gerado por um indexador
  por linguagem (`scip-go`, `scip-typescript`, `scip-dotnet`, `scip-python`), cada um um
  compilador/type-checker completo. Dá símbolos globais estáveis e referências resolvidas com
  precisão de compilador.

## Opções consideradas

| | tree-sitter | SCIP |
|---|---|---|
| Pré-requisito | nenhum: parseia qualquer arquivo isolado | o projeto precisa **compilar**: `go mod download`, `npm install`, `dotnet restore` — com acesso e credenciais aos registries |
| Toolchain | 1 lib Python, 6 gramáticas pré-baixadas na imagem | 1 indexador + SDK/runtime por linguagem, na versão de cada repo |
| Tempo por snapshot | segundos (26 snapshots em ~30 s) | minutos (build + análise) |
| Resolução de chamadas | por nome: ~40 % dos call sites em Go resolvidos (baseline medida) | ~100 % do que compila; interfaces, DI e sobrecargas corretas |
| Semântica de framework (rotas, clientes HTTP, tópicos) | não vem de graça — heurísticas sobre a árvore | também não vem: SCIP sabe que `HandleFunc` é `net/http.(*ServeMux).HandleFunc`, não que `"POST /v1/x"` é uma rota |
| Falha parcial | um arquivo com erro de sintaxe não derruba o repo | build quebrado = snapshot sem índice |
| Adequação à atualização contínua | alta | baixa no Docker do dev; viável num servidor/CI com cache de dependências |

## Decisão

1. **tree-sitter é a base universal** do micro e a única fonte do macro. Todo repositório entra no
   grafo no primeiro minuto, compile ou não; a atualização contínua (U1–U3) permanece barata.
2. **SCIP entra na F1.2 como enriquecimento opcional por repositório**, não como substituto: quando
   o indexador SCIP da linguagem conseguir rodar para uma snapshot, as arestas `CALLS` dessa snapshot
   ganham `resolved: true` e os nós `Symbol` ganham `scip_symbol`; quando não conseguir, permanece a
   resolução por nome (`resolved: false`, `strategy`). O esquema já prevê os dois campos
   (`neo4j/SCHEMA.md`, `Symbol.scip_symbol?`, `CALLS.resolved/strategy`).
3. A camada de integrações (`integrations.py`: rotas expostas, chamadas HTTP de saída, futuro gRPC e
   mensageria) é **independente do resolvedor** — heurísticas de framework sobre a árvore, calibradas
   em corpus público, com `evidence` e `confidence` em cada candidato. Ela não é provisória: continua
   por cima do SCIP quando ele existir.
4. LLM não é parser em nenhuma das camadas (princípio do ROADMAP). Onde um padrão não é reconhecível
   estaticamente, a limitação é registrada, não estimada.

## Consequências

- O `who_calls`/`symbol_context` da Fase 0 têm precisão dependente da disciplina do código (nomes
  únicos por módulo). A skill `scan` já informa a `strategy` de cada aresta e trata `unique-name`
  como "provável", não "certo".
- O gatilho para investir em SCIP é uma métrica, não um princípio: quando o `impact` cross-repo
  (F2) for limitado pela taxa de resolução (~40 % hoje em Go), a F1.2 entra com esse número para
  bater. Medir por linguagem antes de escolher por onde começar (Go via `scip-go` é o candidato
  natural: toolchain única, builds rápidos, `go mod download` cacheável).
- Rodar SCIP exigirá o cenário servidor/CI (F3): cache de dependências, credenciais de registries
  via `token_env`, indexadores por linguagem na imagem — e isolamento por repo para que um build
  quebrado não bloqueie a fila.
- A modularização por linguagem do indexador (ADR-003, proposta) deve deixar o ponto de entrada do
  SCIP explícito: um enriquecedor por linguagem que recebe a snapshot já extraída e devolve
  resoluções, sem reescrever o pipeline.
