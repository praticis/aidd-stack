# Perguntas douradas (F0.7)

> Documento vivo em PT. Cada pergunta tem **a ferramenta MCP que responde**, **o Cypher que verifica a
> resposta direto no grafo** e o **resultado obtido no par piloto** — `<project-a>` (BFF) →
> `<project-b>` (serviço de auth) e `<project-c>` (serviço de onboarding), tenant fixo, 6 repos Go.
> Nomes reais nunca entram aqui (repo open-source); o resultado é descrito em forma, não em conteúdo.
>
> Uma pergunta só conta como respondida quando a resposta do MCP e a do Cypher coincidem **e** uma
> amostra foi conferida na fonte (a `evidence` aponta `repo:arquivo:linha`). Regressão: repetir as
> cinco depois de qualquer mudança em `graph.py`, `linker.py` ou `mcp/server.py`.

## Por que estas cinco

Cobrem os três eixos que o atlas existe para responder e que a leitura do repositório sozinha não
dá: **dentro de um repo** (Q2), **entre repos** (Q1, Q3, Q4) e **entre refs** (Q5). Q1–Q3 são as
perguntas do dia a dia da skill `scan` e do `refine-business`; Q4 é a que justifica o grafo
(impacto cruzando repositórios, que nenhum `grep` responde); Q5 é a que o `refresh` contínuo
habilita (a branch está indexada antes do merge).

---

## Q1 — Quem consome esta rota?

**Pergunta:** "Quem chama `POST /v1/password-reset/start` do `<project-b>`, e de onde?"

**MCP:** `who_consumes(path="/v1/password-reset/start", method="POST")` — sem `repo`, porque a
mesma rota pode ser exposta por mais de um serviço (o BFF re-expõe rotas do serviço).

**Cypher:**

```cypher
MATCH (svc:Service {tenant: $t})-[:EXPOSES]->(e:HttpEndpoint {method: 'POST', path_key: '/v1/password-reset/start'})
OPTIONAL MATCH (e)-[cf:CALLED_FROM]->(caller)
RETURN svc.name AS provider, caller.repo AS consumer, caller.qualified_name AS symbol,
       collect(DISTINCT cf.ref) AS refs, cf.evidence AS evidence, cf.confidence AS confidence
ORDER BY provider, consumer;
```

**Esperado:** duas rotas — a do `<project-b>` com um consumidor (`<project-a>`, símbolo do adapter
outbound, `arquivo:linha`, `confidence: exact`, lista de `refs`) e a re-exposta pelo `<project-a>`
sem consumidor (quem chama o BFF é o app, que não está indexado). `possible_consumers` vazio.

**Obtido (2026-09-29):** ✅ exatamente isso. O modelo distinguiu as duas rotas sem ser instruído e
explicou a ausência de consumidor no BFF. Antes do ajuste, `consumers` vinha com uma linha por ref
(13 branches = 13 "consumidores"); agora é uma linha por repo × símbolo com `refs[]`.

---

## Q2 — O que este repositório chama, e para onde vai?

**Pergunta:** "Quais chamadas HTTP de saída o `<project-a>` faz em `main`, e cada uma bate em que
serviço/rota?"

**MCP:** `http_map(repo="<project-a>")` — olhar `outbound_calls[].linked_to`, `outbound_unlinked`.

**Cypher:**

```cypher
MATCH (c:HttpCall {tenant: $t, repo: '<project-a>', ref: 'main'})
OPTIONAL MATCH (target:HttpEndpoint)-[cf:CALLED_FROM {call_id: c.id}]->()
RETURN c.method, c.path, c.target_hint, c.evidence, target.service AS linked_service, target.path AS linked_path, cf.confidence
ORDER BY c.path;
```

**Esperado:** toda chamada com path literal aparece; as que casam com uma rota de outro repo do
workspace têm `linked_to` (`exact`); as externas (antifraude, e-mail, WhatsApp) e as com segmento
literal passado por variável ficam `linked_to: null`.

**Obtido (2026-09-29):** ✅ 5 chamadas em `main`, 5 ligadas ao `<project-b>`, `outbound_unlinked: 0`.
O modelo apontou, pelo `AGENTS.md` do repo, chamadas que não aparecem no mapa (2FA, `users/me`,
saldo/extrato) — a hipótese dele (path dinâmico ou só em branch) está certa nos dois casos e é o
gap de recall registrado para o H1 (`docs/handoffs/H1-reference-apps.md`).

---

## Q3 — Mapa do serviço: quem fala com quem no workspace?

**Pergunta:** "Desenhe as integrações HTTP entre os repositórios deste tenant."

**MCP:** `cypher_readonly` com a consulta abaixo (é a "workspace map" do `SCHEMA.md` §7; ausente num atlas
multi-tenant com `ATLAS_RAW_CYPHER=off`); ou `http_map` por repo e somar. Candidata a ferramenta própria (`workspace_map`) na F1.

**Cypher:**

```cypher
MATCH (a:Service {tenant: $t})-[c:CONSUMES]->(e:HttpEndpoint)<-[:EXPOSES]-(b:Service)
WITH DISTINCT a, b, e, c.confidence AS conf
RETURN a.name AS consumer, b.name AS provider, count(e) AS routes, collect(DISTINCT conf) AS confidence
ORDER BY consumer, provider;
```

Atenção: `CONSUMES` e `EXPOSES` são **por ref** — sem o `DISTINCT` a consulta multiplica linhas por
snapshot (496 linhas para 6 pares na primeira rodada).

**Esperado:** um par por (consumidor, provedor) com o número de rotas; só `exact` depois da regra de
sufixo com corroboração.

**Obtido (2026-09-29):** ✅ `<project-a>` → `<project-b>` (5 rotas) e `<project-a>` → `<project-c>`
(1 rota). O par `<project-c>` → `<project-a>` que aparecia por sufixo era falso positivo e motivou
a regra "sufixo só com hint" (`core/linker.py`).

---

## Q4 — Impacto de mudar um símbolo, cruzando repositórios

**Pergunta:** "Se eu mudar `<símbolo do serviço de auth que valida a política de senha>`, o que é
afetado — dentro do repo e nos outros?"

**MCP:** `impact_of(symbol="<qualified_name>", repo="<project-b>")` → `internal_callers` (com
`hops`), `exposed_through` (rotas cujo handler alcança o símbolo), `consumers` (outros repos:
serviço, rota, símbolo chamador, `arquivo:linha`, `confidence`).

**Cypher:**

```cypher
MATCH (s:Symbol {id: $id})
MATCH p = (h:Symbol)-[:CALLS*1..6]->(s) WHERE h.ref = s.ref AND h.repo = s.repo
WITH s, h, min(length(p)) AS hops
OPTIONAL MATCH (e:HttpEndpoint)-[:HANDLED_BY {ref: s.ref}]->(h)
OPTIONAL MATCH (e)-[cf:CALLED_FROM]->(caller)
RETURN h.qualified_name AS reaches_via, hops, e.method + ' ' + e.path AS route,
       caller.repo AS consumer, caller.qualified_name AS consumer_symbol, cf.evidence
ORDER BY hops, route;
```

**Esperado:** os callers internos até o handler HTTP (`hops` crescente; `via_ambiguous: true` quando
alguma aresta `CALLS` do caminho é `*-ambiguous`), a rota `GET /v1/password-policy` em
`exposed_through`, e `<project-a>` em `consumers` com o adapter outbound e a linha. Se o símbolo não
é alcançado por handler nenhum, `exposed_through` vazio = mudança interna ao serviço.

**Obtido (2026-10-03):** ⚠️ respondida, com um limite importante. A pergunta foi feita no repo do
BFF (`<project-a>`), e o modelo escolheu o adapter outbound (`Client.GetPasswordPolicy`) como alvo.
A parte **entre repos** veio certa do grafo: a rota `GET /v1/password-policy` é exposta pelo
`<project-b>`, consumida só pelo BFF (`exact`, sem `possible_consumers`), e a rota re-exposta pelo BFF
não tem consumidor indexado (app). A parte **dentro do repo** expôs o limite da resolução por nome:
`who_calls` devolveu só os 5 testes do adapter; o uso de produção passa por uma **interface**
(`ports.PasswordPolicyGetter`) e a chamada `getter.GetPasswordPolicy()` tem vários candidatos com o
mesmo nome (método da interface, método concreto, fakes dos testes) em módulos diferentes →
`unique-name` falha → aresta `CALLS` não existe. O modelo reconstruiu a cadeia correta
(handler → use case → porta → adapter) por `find_symbol` + leitura, e disse que o grafo não provava.
Isso é exatamente a métrica que dispara o SCIP (ADR-002, F1.2). Correção barata antes disso:
ao resolver chamadas de código de produção, descartar candidatos definidos em arquivos de teste
(`TEST_FILE`) — remove os fakes da disputa e muitos casos voltam a ser `unique-name` (F0.7.1).

**2ª rodada (2026-10-03):** ✅ o `impact_of` foi usado de ponta a ponta no repo do `<project-b>`. O ponto cego foi um receptor que é campo de struct e resolvia só pelo nome. Ele levou ao F0.7.1, que trouxe três coisas:

- o tipo estático do receptor em Go (`receiver-type`);
- produção nunca resolve para teste;
- o `impact_of` separando os chamadores de produção e de teste.

As interfaces ficaram para o SCIP ou para uma convenção, e o F0.7.3 resolveu a interface com implementador único.

Limite conhecido: `CALLS` é resolvido por nome (same-file → same-module → unique-name); em repos
com muitos homônimos os caminhos `-ambiguous` inflam o raio. É o gatilho do SCIP (ADR-002, F1.2).

---

## Q5 — O que esta branch adiciona à superfície do serviço?

**Pergunta:** "Que rotas, entry points e chamadas de saída a branch `<feature/x>` do `<project-a>`
tem que `main` não tem (e vice-versa)?"

**MCP:** `ref_diff(repo="<project-a>", ref="<feature/x>")` (base = default branch; `base=` para
comparar duas features).

**Cypher:**

```cypher
MATCH (:Service {tenant: $t, name: '<project-a>'})-[x:EXPOSES]->(e:HttpEndpoint)
WITH e.method + ' ' + e.path AS route, collect(DISTINCT x.ref) AS refs
WHERE '<feature/x>' IN refs XOR 'main' IN refs
RETURN route, refs ORDER BY route;
```

**Esperado:** as rotas de onboarding que só existem nas branches de feature aparecem em
`endpoints_added` com handler e `evidence`; `entry_points_added` lista os handlers novos por
`qualified_name`; `http_calls_added` as chamadas novas (por método+path); `*_removed` vazios para
uma branch que só adiciona. `summary` com as contagens.

**Obtido (2026-10-03):** ✅ a ferramenta respondeu e o modelo leu certo — inclusive o caso
inverso ao esperado: a branch indexada estava **atrás** de `main` (14 rotas × 31; `main` tinha
acabado de receber o onboarding, 17 rotas em `endpoints_removed` do ponto de vista da branch), e
localmente a branch já tinha `main` mergeada. O modelo explicou que o `ref_diff` compara os commits
**indexados** (refs remotas) e não o checkout local, e propôs `git diff main...<branch>` para o
código local. Também listou, em `main`, as 4 chamadas para o `<project-c>` com 3 sem `linked_to`
pelo `{param}/{param}` — o gap de recall já registrado. Ajuste feito na ferramenta: `ref_diff` agora
devolve `snapshots` (sha indexado e `indexed_at` de cada ref) e uma `note` sobre refs locais, para
que a defasagem fique explícita na própria resposta em vez de depender da leitura do modelo.

---

## Como usar este documento

- Nova pergunta = novo bloco com os quatro campos (pergunta, MCP, Cypher, esperado) **antes** de
  implementar a ferramenta; o "obtido" vem depois, com data.
- Uma resposta que exigiu `cypher_readonly` é sinal de ferramenta faltando (Q3 hoje).
- Uma resposta certa que o grafo **não prova** (Q4: cadeia reconstruída por leitura porque `CALLS` não
  atravessa interface) é a métrica da F1.2 — anotar quantas vezes acontece antes de decidir pelo SCIP.
- Quando o modelo responde certo mas com ruído (Q1 e os refs), o ajuste é no MCP, não no prompt.
- Cada `[WARN]`/gap anotado aqui tem dono: extrator → tabela de regras em `indexer-evolution.md`
  §3 e handoffs; linker → `core/linker.py` + `tests/test_linker.py`; MCP → `tests/test_mcp_protocol.py`.

---

## Rodadas anteriores

O texto completo de cada rodada está em `git show 1d73bb0:docs/golden-questions.md`.

- **1ª (2026-09-29 e 2026-10-03), tenant Go piloto:**
  - Q1–Q3 e Q5 ✅;
  - Q4 ⚠️, porque a cadeia por interface não estava no grafo. Isso levou ao F0.7.1–F0.7.2b.
- **2ª (2026-10-03), par .NET de referência:**
  - Q1–Q3 ✅;
  - Q4a ⚠️ (7 chamadores internos falsos, pela resolução por nome em C#) e Q4b ❌ (a interface sem o handler). Isso
    levou ao F0.7.2: o tipo do receptor e o implementador único em C#.
- **3ª (2026-10-14, indexer 0.2.14):** a Q4 .NET depois do F0.7.3, com dispatch do mediator, DI e bases de pacote.
  - Q4a: 1 chamador, a rota e o consumidor;
  - Q4b: 5 chamadores e 2 rotas.
- **4ª (2026-10-18, build `0.2.14+8553d8007527`):** Q1, Q2 e Q4 .NET depois do H2, com a rota ASP.NET na caixa do
  código.
  - O que pegou: o `who_consumes` comparava `path_key` com caixa, e foi corrigido em `98b8368`.
  - A lição: todo leitor de uma chave de junção precisa da mesma regra do linker.

## Quinta rodada: a validação do PR #5 numa instalação ao vivo (2026-10-19, build `0.2.15+0377dbb62b98`)

O que mudou desde a quarta rodada: o F1.14 (`feature/f114-close`, PR #5). Ele trouxe:

- um endpoint por app num monorepo, com o `app` no nó e no id (indexer 0.2.15);
- os wrappers de cliente do app em Python e em TS/JS;
- as rotas Go por tipo declarado.

A rodada foi parte de uma validação em duas fases antes do merge:

- **offline:** corpus e hold-out do `main` contra a branch, a cadeia de baselines, os gabaritos e os testes;
- **na instalação:** 3 tenants e 10 snapshots.

As perguntas e uma chamada de cada uma das 11 tools foram gravadas em JSON, pelo HTTP do MCP, antes e depois da
reinstalação. A comparação deixa de fora só os campos de tempo e de build.

| Q | Resultado | Observação |
|---|---|---|
| Q1 `who_consumes`, em minúsculas e na caixa do código | ✅ o mesmo consumidor, `exact` | o endpoint ganha `app: ""` |
| Q2 `http_map` | ✅ igual | o `linked_to` também traz o `app` |
| Q3 mapa | ✅ igual nos 3 tenants | um par, `<svc-accrual>` → `<svc-transaction>`, `exact` |
| Q4a e Q4b `impact_of` | ✅ iguais | — |
| Q5 `ref_diff` (um repo TS, `develop` contra `master`) | ✅ agora com as 7 chamadas que só a `develop` faz, com o verbo certo | antes, 0: os wrappers do cliente do app escondiam as chamadas |

**O que a rodada pegou.** Na primeira reinstalação, o repo TS ganhou 51 chamadas pelos wrappers do app, e 34 estavam
erradas por dois defeitos:

- as opções num local caíam no GET padrão;
- a query entre parênteses virava `{param}`.

A correção é o incremento 12 (`dfbc8d7`), com caso de fixture. Na segunda reinstalação, as 109 chamadas novas (51 e
58 nas duas refs) batem com o dry-run e estão certas. O corpus não tinha essas formas. Só o código real as mostrou.

**O resto do grafo.**

- Fora do HTTP, ficaram idênticos antes e depois: símbolos, `CALLS`, `IMPORTS`, módulos, violações, `DEPENDS_ON`,
  `CONSUMES` e `CALLED_FROM`.
- No monorepo Go de amostra, 3 rotas que 3 serviços com `go.mod` próprio declaram viraram um endpoint por serviço:
  são 8 endpoints, onde antes eram 3.
- O nó órfão da rota antiga, em minúsculas, do par .NET foi removido.

**Lição de operação.** `python -m aidd_indexer.cli` numa imagem com `WORKDIR=/app` roda o código da imagem, e não o
montado por `PYTHONPATH`, porque o diretório de trabalho vem antes no `sys.path`.

- O dry-run de comparação precisa de `-w` apontando para o código montado.
- A versão impressa na primeira linha confirma qual código rodou.
