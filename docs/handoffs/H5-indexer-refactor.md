# Handoff H5 — Refatorar o indexador antes do SCIP

> Cole este arquivo (ou peça para ler `docs/handoffs/H5-indexer-refactor.md`) no início de um chat novo. Antes de
> qualquer coisa, o chat deve ler:
> - `docs/ROADMAP.md`: "Onde estamos", "Princípios", F1.1, F1.2, F1.13 e F1.14;
> - os ADRs 002 e 003;
> - `docs/indexer-evolution.md`: §2 Mapa do código, §5 Como medir e §8 a fronteira com o SCIP;
> - o fim de `docs/corpus-report.md`, a última baseline.
>
> **Estado (2026-10-18):** registrado, não iniciado. As decisões do autor estão em "Decisões tomadas". Nasceu de
> uma revisão pedida no meio do fechamento do F1.14. Depois de 24 commits de regras desde o v2 do corpus, o código
> do extrator ficou com funções de complexidade muito alta, arquivos grandes e duas implementações paralelas de "qual
> é o tipo disto". Isso precisa estar resolvido antes do SCIP (F1.1/F1.2), porque o SCIP entra exatamente nessa
> costura.

## Contexto em um parágrafo

O H2 e o F1.14 levaram o extrator HTTP de quase nada a 99–100 % de precisão e de 89–99 % de recall no corpus de 55
repos. O método foi uma regra por incremento, cada uma com fixture e corpus julgado. O método funcionou. O que ele
não fez foi reorganizar o código entre uma regra e outra. Cada regra entrou onde coube: num `if` a mais no método que
já tratava chamadas, num campo a mais do `PackageContext`, num fato com chave de texto. O resultado mede bem e se lê
mal. O H5 é uma refatoração **sem mudança de comportamento**: o corpus e o hold-out têm de sair idênticos à
baseline de partida, passo a passo. Ela prepara três coisas: o SCIP (um único ponto onde o tipo de uma expressão é
perguntado), a escala (F1.13) e a manutenção (regras como unidades que se testam sozinhas).

## Diagnóstico (medido em 2026-10-18, sobre `713fec8` + o item 2 do F1.14 em andamento)

**Tamanho e complexidade.** São 11.957 linhas não vazias em 54 arquivos e 736 funções. A complexidade ciclomática
conta os desvios (`if`, laços, `and`/`or`, `except`); 10 é o limite usual de uma função fácil de testar.

| Complexidade | Funções | | Tamanho | Funções |
|---|---|---|---|---|
| 1–10 | 545 | | 1–30 linhas | 664 |
| 11–20 | 127 | | 31–60 | 55 |
| 21–40 | 51 | | 61–120 | 15 |
| 41–80 | 11 | | mais de 120 | 2 |
| mais de 80 | 2 | | | |

As piores são estas:

| Função | Complexidade | Linhas |
|---|---|---|
| C# `_controller` | 118 | 118 |
| Go `_call` | 95 | 104 |
| MCP `build_server` | 74 | 610 |
| `_path_of_call` | 69 | 59 |
| `collect_constants` | 66 | 76, aninhamento 7 |
| TS `_read_call` | 62 | 69 |
| `resolve_calls` | 55 | 95 |
| C# `_fast_endpoint` | 51 | 58 |
| C# `_route_attribute` | 50 | 58 |

Os arquivos acima de 600 linhas não vazias:

| Arquivo | Linhas |
|---|---|
| `languages/csharp/http.py` | 1410 |
| `languages/typescript/http.py` | 892 |
| `core/http_expr.py` | 831 |
| `mcp/server.py` | 793 |
| `languages/go/http.py` | 685 |
| `cli.py` | 617 |
| `core/http_base.py` | 609 |

**Responsabilidades misturadas.**

1. **O `core/` conhece as linguagens, o que o ADR-003 proíbe.** O ADR-003 diz que o núcleo "nunca consulta o id da
   linguagem". Mesmo assim:
   - `core/http_expr.py:92` faz `go, py = fx.file.language == "go", ..` e abriga regras de linguagem: `_ts_client`,
     `_ts_interceptor`, `_ts_client_class`, `_py_class`, `_go_struct`, `_passthrough`, `_enum_member`, o `url.URL`
     do Go e o `runtime.NewPattern` do grpc-gateway;
   - o `PackageContext` (`core/http_base.py`) tem campos de cada linguagem: `client_bases` (TS), `classes` (Python),
     `struct_fields`, `passthrough` e `verb_lists` (Go).
2. **Dois sistemas de tipos em paralelo.** O resolver micro (`languages/*/symbols.py`, com `file_facts` e
   `ResolveContext.facts`) e os scanners HTTP respondem, cada um à sua maneira, a "qual é o tipo deste valor":
   - Go: `go/symbols.py:_declared_type` e `go/http.py:_value_type`. Os dois leem receptor, parâmetros e
     `x := &T{}`. O item 2 do F1.14 chegou a duplicar também os campos de struct (`PackageContext.struct_fields`); antes
     do commit, passou a ler os `file_facts["structs"]` do resolver, repassados por diretório
     (`PackageContext.file_facts`). É um remendo até o `TypeIndex`;
   - C#: `csharp/symbols.py:_local_type` e `csharp/http.py:_declared_type`;
   - por linguagem, ainda: `router_param_type`, o `_router_class` do Python, o `_client_of` do TS, o `classes_named`
     da `RepoView`, e o `_reaches_fast` e o `_inherited_route` do C#.

   O SCIP vai responder a essa pergunta. Hoje ele teria de entrar em dez lugares.
3. **O conhecimento de framework está espalhado em código.** Verbos, registradores, portadores de prefixo,
   construtores de app e receptores de cliente estão em constantes soltas por scanner (`GO_REGISTRARS`, `GO_MOUNTS`,
   `GO_PREFIXED`, `CS_MAP`, `FE_VERBS`, `TS_ROUTER_VERBS`, `KOA_ROUTERS`, `CLIENT_RECEIVER` ..). O nome do framework
   gravado na rota é decidido dentro do `_call` do Go por heurística de nome de método. O item 7 do F1.14 já pedia
   o catálogo como dado.
4. **Os métodos são "tudo-em-um".** `_call` (Go), `_read_call` (TS), `_invocation` e `_controller` (C#) classificam o
   callee e decidem entre rota, montagem, router passado adiante, cliente gerado e chamada de saída, num só fluxo de
   `if`s. Uma regra nova é um `if` a mais nesse fluxo, e a ordem entre elas é implícita.
5. **Os fatos e as pendências são tipados por texto.** São cerca de 35 chaves de fato (`"cs.fe-group"`,
   `"ts.mount-wrapper"`, `"go.encoder"` ..) com valores em tuplas posicionais, desempacotadas longe de onde nasceram
   (`bases, controller, prefixes, area, own, uses, versions = p.key`).
6. **A regra de casar paths existe em mais de um lugar.** O linker compara uma rota ASP.NET sem caixa, e o MCP só
   passou a fazer o mesmo hoje (`98b8368`). O `who_consumes` ainda calcula a chave com uma regex própria
   (`mcp/server.py:608`), e não com `paths.normalize_path` + `path_key`, então um `:id` perguntado não é
   normalizado.
7. **Há um ciclo de import.** `core/http_base` importa `languages/base`, que passa por `languages/__init__`, que
   importa todas as linguagens, que importam `core/http_base`. Importar `aidd_indexer.core.http_base` primeiro
   falha. Só funciona porque a ordem de import usual mascara o ciclo.

**Desempenho.** Perfil da extração inteira do vikunja (2134 arquivos, 51 s sem o profiler):

| Função | Chamadas | Tempo acumulado | Parte do total (93 s, com profiler) |
|---|---|---|---|
| `walk` | 55,6 milhões | 52 s | 56 % |
| `go/symbols.py:_declared_type` (via `call_receiver`) | 63.820 | 32 s | |
| `collect_constants` | | 14 s | |
| `run` do scanner TS | | 15 s | |

- O `walk` é um gerador Python que materializa a lista de filhos de cada nó. Quase metade dele vem do
  `_declared_type`, que percorre a função inteira para cada receptor de chamada: é quadrático por função.
- Cada arquivo é percorrido inteiro de quatro a seis vezes: as queries do extrator, o `file_facts`, o
  `collect_constants`, o `run` do scanner e as sub-varreduras (`function_of`, `_param_values` ..).
- No corpus, o HTTP é 208 s de 1255 s de extração, e o resto é parse, símbolos e resolução. O mattermost leva
  219 s, o bitwarden 128 s, o photoprism 101 s (só 8 s de HTTP).
- A rodada inteira do corpus leva cerca de 21 min em série. Esse é o ciclo de regressão de cada passo, então
  encurtá-lo é parte do objetivo.

**Escala (F1.13).** `extract_http` recebe todos os extratores do repo com as árvores vivas, porque as duas passadas
(constantes, depois scanners) precisam delas. O grafana morre por memória a 7,7 GB. A refatoração não resolve o
F1.13, mas não pode fechar a porta: a segunda passada tem de poder reparsear um arquivo, em vez de exigir a árvore
guardada.

**Testes.**
- O HTTP inteiro passa por um teste parametrizado (`tests/test_fixtures.py`, 16 fixtures). Quando falha, ele diz
  quais rotas faltam, e não qual regra quebrou.
- Não há teste unitário de `core/paths.py`: `normalize_path` tem 19 regex cuja ordem importa. Também não há de
  `http_mounts`, `http_scope` nem `http_expr`.
- O `test_mcp_protocol` usa um store falso e não executa Cypher. Quem prova as queries são as perguntas douradas,
  rodadas à mão.

**O que está bem e deve ficar.**
- O orquestrador `core/integrations.py` é enxuto.
- O grafo de montagem (`core/http_mounts.py`) é pequeno e geral.
- A regra F1.13 vale: um scanner nunca lê a árvore de outro arquivo; o que cruza arquivos vai por fatos e `compose`.
- Os `except Exception` são fronteiras deliberadas, por arquivo e por repo, e estão comentados.
- O ciclo regra → fixture → corpus julgado é o melhor ativo do projeto, e o H5 o usa como rede.

## Objetivo

Ao fim do H5:
- o corpus e o hold-out estão **idênticos** à baseline de partida;
- a extração do corpus inteiro leva **≤ 60 %** do tempo de hoje (meta a confirmar no passo 0);
- valem as metas de forma, decididas pelo autor:
  - **complexidade de um dígito**: nenhuma função acima de 9 (`ruff`, regra `C901`, `max-complexity = 9`), sem
    exceção. Um despachante é uma consulta ao catálogo, não uma cadeia de `if`s;
  - **nenhum módulo com mais de 300 linhas**, contadas no arquivo inteiro como o `wc -l` conta: docstrings e
    comentários incluídos. São cerca de 12 mil linhas de hoje divididas em pacotes por linguagem e por papel;
  - `core/` sem nenhum nome de linguagem nem de framework, verificado por teste;
  - um único serviço de tipos que o resolver micro e os scanners HTTP consultam, e onde o F1.2 pluga o SCIP;
  - regras como unidades: cada uma com nome, pré-condição barata, fixture e teste próprio.

## Arquitetura-alvo

1. **Utilitários de árvore neutros** (`aidd_indexer/tree.py`):
   - `node_text`, `walk` com `TreeCursor` (sem lista de filhos por nó) e um índice por arquivo (`FileIndex`);
   - `languages/base` e `core/` importam daqui, e o ciclo some;
   - o registro de linguagens carrega sob demanda.
2. **`FileIndex`, uma passada por arquivo.** É construído uma vez, logo depois do parse, e compartilhado pelo
   extrator de símbolos, pelo coletor de constantes e pelo scanner. Ele tem:
   - os nós por tipo;
   - as funções por id, com o pai de cada uma;
   - as declarações e atribuições por escopo, que hoje são o `Scopes._assignments` e o `_declared_type`;
   - os identificadores por nome e escopo;
   - as chamadas.

   As varreduras ad hoc (`function_of`, `_idents`, `_param_values`, `walk(scope)`) passam a consultá-lo.
3. **Serviço de tipos** (`TypeIndex`, a costura do SCIP). As perguntas são:
   - `declared_type(valor)`: receptor, parâmetro, `var x T`, literal composto, campo de struct ou classe;
   - `bases(tipo)`, `method(tipo, nome)` e `field(tipo, nome)`;
   - `return_type(função)`, quando declarado.

   A implementação de agora sai dos `file_facts` de cada linguagem, consolidados por repo. O resolver micro
   (`call_receiver`) e os scanners HTTP usam a mesma instância. O que hoje é `needs-resolver` (ADR-002, adendo) vira
   uma chamada a esse serviço que devolve "não sei". No F1.2, uma implementação SCIP responde as mesmas perguntas
   quando houver índice.
4. **Fatos de pacote por linguagem.** O `PackageContext` do `core/` fica com o que é geral: constantes de path,
   pedaços de constante, `env_hints` e funções por nome. Cada linguagem registra o próprio coletor
   (`LanguageSupport.collect_package_facts`) e a própria classe tipada de fatos: os clientes com base do TS, as
   classes de router do Python, o passthrough e as listas de verbos do Go. O código de `_ts_client`, `_py_class`,
   `_go_struct`, `url.URL` e grpc-gateway muda para `languages/<lang>/`.
5. **Regras como reconhecedores.** O `_call`/`_invocation`/`_read_call` de cada linguagem vira um despachante sobre
   uma lista ordenada de reconhecedores. Cada um declara:
   - uma pré-condição barata, como o tipo de nó e o nome do callee num conjunto, para o despachante indexar;
   - `apply(nó) -> bool`.

   A ordem fica explícita na lista. Cada reconhecedor corresponde a uma linha da tabela do guia
   (`indexer-evolution.md` §3), com o seu caso de fixture e o seu teste. O `_controller` do C# se parte do mesmo modo:
   ler atributos, detectar o controller, publicar a herança, FastEndpoints e as actions. Com 300 linhas por módulo,
   cada linguagem vira um pacote (`languages/<lang>/http/`), com um módulo por grupo de reconhecedores (rotas por
   atributo, rotas por chamada, montagens, clientes), mais o `compose` e os fatos.
6. **Catálogo de frameworks como dado, em YAML** (o item 7 do F1.14; H5-D2):
   - um arquivo por linguagem (`languages/<lang>/frameworks.yaml`). Por framework, ele traz o nome gravado na rota,
     os verbos, os registradores, os portadores de prefixo, os construtores de app/router e os receptores de
     cliente;
   - um esquema validado na carga, com teste. Um catálogo inválido falha alto no teste e degrada com aviso na
     indexação, como as convenções;
   - os reconhecedores leem o catálogo. As convenções (F0.4.5), que já são YAML, estendem o mesmo catálogo;
   - os limiares do `built_bundle` viram parâmetros nomeados.
7. **Fatos e pendências tipados.** Cada fato é uma dataclass registrada (por exemplo `FeGroup(name, prefix,
   parent)`), e o `compose` de cada linguagem é uma lista ordenada de passos que consomem fatos tipados. Acabam as
   chaves de texto e as tuplas posicionais.
8. **Uma regra de casar paths.** Um módulo (`core/matching.py`) com `path_key` e a comparação com ou sem caixa por
   framework. O linker, o MCP e o placar do corpus o usam.
9. **MCP dividido.**
   - O `build_server` (610 linhas) se divide em módulos por grupo de ferramentas.
   - O Cypher vira constantes nomeadas num módulo de queries.
   - Um teste de integração roda cada query contra um Neo4j de verdade (container efêmero) com um grafo pequeno
     semeado pela fixture. É a lição do `who_consumes`.
10. **Laço do corpus mais curto.**
    - O paralelismo já existe desde 2026-10-18: `indexer/scripts/corpus.sh` roda um container por repo, os maiores
      primeiro, com teto de memória em cada um, e junta o relatório no fim. Este passo mede o ganho no que cada repo
      gasta, não no relógio: a soma dos tempos por repo que o script registra (1.382 s na `baseline-26`, com 3 em
      paralelo).
    - Os números da docstring são gerados da baseline, em vez de editados à mão a cada incremento.
11. **Comentários só com o que é estritamente pertinente** (H5-D4). Os docs ainda vão ser reorganizados, então o
    código não aponta para eles. As regras:
    - um comentário diz o porquê que o código não diz: um contrato, um caso de borda, a razão de uma ordem. Ele não
      narra o código nem cataloga os casos que motivaram a regra;
    - nenhuma referência a docs nem a itens de planejamento: ROADMAP, `F1.x`, `H2-Dx`, ADR, seções do guia,
      relatório do corpus;
    - nenhum nome de projeto. Um nome privado (tenant, serviço de cliente) nunca aparece, e onde o comentário
      precisa de um exemplo, ele usa um nome neutro (`orders-api`, `PARTNER_API_URL`). Também saem os nomes dos apps
      públicos do corpus, como vikunja e gitea: o exemplo descreve a forma do código (`um grupo passado por campo de
      struct`), e só fica o nome de framework ou biblioteca quando é ele que define o comportamento (gin,
      FastEndpoints, grpc-gateway);
    - as fixtures seguem a mesma regra: o comentário descreve a forma, não o app de origem. Os gabaritos do corpus
      (`tests/corpus_expected/`) seguem com os nomes, porque falam daqueles repos.

## Passos

Cada passo é um commit, ou alguns, com o critério de pronto abaixo **e** o protocolo de regressão. A ordem vai do
mais seguro e mais barato ao mais estrutural. As redes de teste entram antes de mover código.

| # | Passo | Pronto quando |
|---|---|---|
| 0 | Linha de base: congelar `v2-baseline-N` e o hold-out; medir sozinho (sem outra carga) o tempo do corpus e o perfil de 4 repos (mattermost, vikunja, umbraco, ghost); no CI, relatório (sem bloquear) de `ruff C901` com `max-complexity = 9` e de módulos acima de 300 linhas | números registrados no `corpus-report.md` (seção "H5 baseline"), com a contagem de funções e módulos fora das metas |
| 1 | Rede de testes unitários: tabela de casos para `normalize_path`/`mask_placeholders`/`path_key` (cada regex com um caso, e os pares cuja ordem importa), `http_mounts`, `Scopes`, `path_of` | cobre cada regra de `paths.py`; mutar uma regex quebra um teste nomeado |
| 2 | `aidd_indexer/tree.py`: `walk` por `TreeCursor`, `node_text`, fim do ciclo de import, registro sob demanda | `import aidd_indexer.core.http_base` sozinho funciona; perfil do `walk` cai |
| 3 | `FileIndex`: uma passada por arquivo; `_declared_type` (Go), `_local_type` (C#), `Scopes`, `function_of`, `_idents` consultam o índice | sem varredura de escopo por chamada; perfil do vikunja: `walk` < 20 % |
| 4 | Fatos de pacote por linguagem: o código de linguagem sai de `core/http_expr.py` e do `PackageContext`; fatos tipados | um teste prova que `core/` não nomeia linguagem nem framework |
| 5 | `TypeIndex`: um serviço para o resolver micro e o HTTP; `struct_fields`/`_value_type`/`_router_class`/`_client_of`/`classes_named`/`_reaches_fast` passam a consultá-lo | uma única implementação por linguagem de "tipo declarado"; `needs-resolver` é uma resposta do serviço |
| 6 | Reconhecedores + catálogo YAML, **uma linguagem por commit**, do pior ao menor: C# (`_controller`, `_invocation`), Go (`_call`), TS (`_read_call`), Python | nenhuma função > 9 nem módulo > 300 linhas nesses pacotes; cada linha da tabela do guia aponta para um reconhecedor |
| 7 | `compose` tipado por linguagem; `Pending` tipado | nenhuma tupla posicional entre scanner e `compose` |
| 8 | `core/matching.py`; MCP dividido; Cypher testado contra Neo4j efêmero | `who_consumes` usa `normalize_path`; as 11 ferramentas com teste de integração |
| 9 | docstring gerada; o laço do corpus pelo `corpus.sh` | a soma dos tempos por repo em ≤ 60 % da do passo 0 |
| 10 | Revisão geral dos comentários e docstrings (arquitetura, item 11), no código, nos testes e nas fixtures; troca dos nomes de projeto | nenhuma referência a docs nem a nome de projeto no código, verificado por teste; os comentários que ficaram dizem um porquê |
| 11 | Docs: ADR-003 atualizado (ou ADR novo: reconhecedores, catálogo, serviço de tipos); `indexer-evolution.md` §2, §5 e §7 | o guia descreve o código como ele ficou; o relatório de metas no CI mostra zero funções e zero módulos fora (o bloqueio liga quando o autor decidir, H5-D3) |

**Protocolo de regressão (todo passo):**
1. testes verdes;
2. corpus contra a baseline de partida: "0 repo(s) differ";
3. hold-out idêntico;
4. o tempo do passo, medido sozinho, não pior que o anterior, salvo justificativa.

Uma diferença no corpus é um defeito do passo, não um ganho. Se a refatoração revelar um bug real, ele é registrado,
corrigido num commit separado, com caso de fixture, e entra na baseline por decisão explícita.

## Decisões tomadas (2026-10-18, pelo autor)

- **H5-D1, a ordem: tudo antes do SCIP.** Revista no mesmo dia: o autor quis dar ponto final ao H2 antes do H5.
  1. fechar o F1.14 inteiro, na ordem registrada nele: o item 2 (Go), o router reatribuído do item 7, o item 5 (o
     modelo: a mesma rota em dois apps), o item 3 (wrapper de cliente Python, só com fixture), o item 4 (TS/JS,
     inteiro) e o hold-out novo, medido uma vez. O que ele mostrar vira um handoff à parte, sem reabrir o F1.14.
     O código desses itens já nasce nas metas (H5-D3);
  2. a fase 0a do H4 (reciclar os docs de trabalho);
  3. fazer o H5, que absorve a parte de refatoração do item 7 (o catálogo e os limiares do `built_bundle`). A rede
     de regressão é o corpus e o hold-out novo, idênticos a cada passo;
  4. o handoff do que o hold-out novo mostrar, já no formato de reconhecedores; um defeito de precisão que ele
     mostre se corrige antes do H5;
  5. só então o SCIP (F1.1/F1.2).

  O P2 (o indexador em repo próprio) também vem antes do SCIP, depois do H5, para levar o código já limpo. A
  posição exata dele fica a confirmar com o autor.
- **H5-D2, o catálogo é YAML** (arquitetura, item 6), com esquema validado e teste, no mesmo formato em que as
  convenções já são escritas.
- **H5-D3, as metas são complexidade ≤ 9 e módulos ≤ 300 linhas.** Durante o H5, o CI só relata, sem bloquear. A
  intenção é que vire bloqueio; quem liga é o autor, quando o código inteiro cumprir as metas.
- **H5-D4, uma revisão geral dos comentários** (arquitetura, item 11; passo 10): fica só o estritamente pertinente,
  sem referência a docs, porque os docs ainda vão ser reorganizados, e sem nome de projeto. Os nomes privados que
  estavam nos docs (um serviço no log do ROADMAP, uma variável de ambiente no `H2-public-corpus.md`) foram trocados
  em 2026-10-18. O comentário de `core/model.py` que citava um serviço privado também foi trocado no mesmo dia.
- **H5-D5, o escopo inclui o MCP** (passo 8). O `cli.py` fica para quando o P2 mexer nele.

## Armadilhas

- **Identidade de nó do tree-sitter.** `node.child_by_field_name(..)` cria um objeto novo a cada chamada, então
  `a is b` é sempre falso. Compare por `node.id`, que vale dentro de uma árvore. Isso custou uma depuração no
  item 2 do F1.14.
- **A ordem das regex em `normalize_path` é semântica.** Exemplos: o `:x?` opcional antes do corte da query, a
  restrição do Hono antes do `?`. Mova uma regex só com o teste unitário do passo 1 no lugar.
- **Estado por arquivo × por repo.** Os scanners são por arquivo, e o `compose` é por repo. Um índice ou cache que
  sobreviva ao arquivo vaza memória e mistura ids de nó de árvores diferentes.
- **Medir desempenho com o corpus rodando ao lado** distorce o perfil. Meça sozinho, três vezes, e use a mediana.
- **Não edite o código do indexer com uma rodada do corpus em andamento**, porque ela importa os módulos.
- **Refatorar e mudar regra no mesmo commit** apaga a rede: o "0 repos differ" deixa de provar alguma coisa.
- **O prefixo próprio de um grupo global é um fato do router, não da aresta.** Um grupo que outros arquivos nomeiam
  (variável de pacote, router devolvido, parâmetro) publica o próprio prefixo (`go.mount.own`), e o `compose` o põe
  depois do prefixo de cada cadeia que chega ao router. Pendurá-lo nas arestas do arquivo que o define, como era até
  2026-10-18, perdia o prefixo quando a reatribuição (`router = router.WithPrefix("/x")`, `r = r.Group("/x")`) dava
  só uma aresta do router para ele mesmo, e quando outro arquivo montava o router. A fixture
  `route-patterns-go` (`internal/reassigned/`) cobre os dois casos.

## Restrições e convenções

As do H2:
- **Commits:** uma linha convencional, sem corpo e sem `Co-Authored-By`.
- **Idioma:** código, commits e relatório do corpus em inglês; ROADMAP, guia e handoffs em português.
- **Privacidade:** nenhum nome de tenant ou de projeto privado nos docs, no código, nos testes ou nas fixtures.
- **Parser:** LLM nunca é parser.
- **Temporários:** no scratchpad da sessão.
- **Repos do corpus:** não rodar Python dentro dos clones; usar `python -I`, ou o Docker com os mounts do guia.
- **Prioridade do portfólio:** .NET primeiro, depois Go e Python, depois TS. Ela orienta a ordem do passo 6.

## Entregáveis esperados

- O código nos módulos da arquitetura-alvo, com o corpus e o hold-out idênticos à baseline de partida.
- Os testes unitários novos (`paths`, `mounts`, `scopes`, `expr`, um por reconhecedor) e o teste de integração do
  MCP contra Neo4j.
- No CI, o relatório de `ruff C901` (`max-complexity = 9`) e de módulos acima de 300 linhas, zerado, ainda sem
  bloquear (H5-D3).
- No `corpus-report.md`, uma seção "H5" com tempos antes e depois, os perfis e as métricas de forma antes e depois.
- ADR-003 atualizado, ou um ADR novo, e o `indexer-evolution.md` (§2, §5, §7) descrevendo o código novo.
- No ROADMAP: o item do H5 marcado, e o SCIP (F1.1/F1.2) com a costura do `TypeIndex` pronta.
