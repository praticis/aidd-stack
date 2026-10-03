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

**MCP:** `cypher_readonly` com a consulta abaixo (é a "workspace map" do `SCHEMA.md` §7); ou
`http_map` por repo e somar. Candidata a ferramenta própria (`workspace_map`) na F1.

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

**2ª rodada (2026-10-03, `impact_of`, no repo do `<project-b>`):** ✅ ferramenta usada de ponta a
ponta. Handler: 0 chamadores internos (folha), 1 rota, consumidor cross-repo com símbolo, linha,
`exact` e 14 refs colapsados. Getters do value object: `hops: 1` até o handler. Construtor: 156
chamadores, 2 de produção (`main`/`run`) — a injeção de dependência não vira `CALLS`, e o modelo
explicou. **Ponto cego confirmado:** `Policy.Validate` chamado como `uc.policy.Validate(...)` em dois
use cases, grafo só via o teste — receiver é campo de struct, vários `Validate` no repo, resolução
por nome desistia. **F0.7.1 (indexer 0.2.2):** (a) `impact_of` marca `test` por chamador e separa
`production_caller_count`/`test_caller_count`; (b) código de produção nunca resolve para símbolo de
arquivo de teste; (c) Go: tipo estático do receiver (receiver do método, parâmetro, `x := T{}`,
`x := pkg.New()`, campos de struct seguidos pela cadeia `uc.policy`) → estratégia `receiver-type`.
Fixture `go-receiver-types` cobre os 4 casos + fake de teste; no corpus público os `-ambiguous`
caíram (alertmanager 1002→641, gorilla 1090→793, gin-realworld 88→8) com 10/10 arestas amostradas
corretas, e tudo que não é `CALLS` saiu byte a byte igual. Re-rodar esta pergunta após o `refresh`:
`Validate` deve listar os dois use cases com `hops: 1` e `exposed_through` deve trazer
`POST /v1/password-reset/complete` (consumida pelo BFF). Interfaces (`ports.X`) continuam sem aresta
— aí é SCIP ou convenção.

Observação de processo: um `refresh` passou no meio da sessão e as linhas da `evidence` mudaram
entre duas respostas; o modelo percebeu e avisou. É o comportamento desejado — a resposta carrega
`ref`/`sha`, e a skill manda comparar com o `HEAD` local.

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

## Segunda rodada: par .NET de referência (2026-10-03)

Dois repositórios C# preparados para o teste — `<svc-transaction>` (12 rotas em 4 controllers,
`[Route("api/[controller]")]`, comandos via service bus) e `<svc-accrual>` (2 rotas, 2 consumers
Kafka e **uma** chamada HTTP de saída: `httpClient.GetAsync($"api/accounts/{id}/details")`, base URL em
`TRANSACTION_API_URL`). Indexados no mesmo tenant dos repos Go. A comunicação real entre eles é
majoritariamente por eventos — fora do escopo até a F1 (`Topic`/`PRODUCES`/`CONSUMES_EVENT`).

| Q | Resultado | Observação |
|---|---|---|
| Q1 `who_consumes` | ✅ consumidor único, símbolo, `arquivo:15`, `exact`, `possible_consumers` vazio | o hint não foi necessário; `env_hints` vazio porque a env var está em `Extensions/`, outra pasta (hint de env é por diretório) |
| Q2 `http_map` | ✅ 1 chamada, `linked_to` exato, `outbound_unlinked: 0`; rotas de rollup sem consumidor indexado | o modelo apontou que os `Consumers/` são eventos, não HTTP |
| Q3 mapa | ✅ 3 pares no tenant (BFF→auth 5, BFF→onboarding 1, accrual→transaction 1), todos `exact` | o modelo preferiu `http_map`×8 + Cypher de conferência a uma query só → `workspace_map` como tool (F1) |
| Q4a `impact_of` handler | ⚠️ cross-repo certo; **7 chamadores internos falsos** | resolução por nome em C#: `this._query.FindByIdAsync()` ligado ao próprio handler (same-file) e os `_xRepository.FindByIdAsync` dos command handlers ligados por homonímia |
| Q4b `impact_of` query | ❌ `IAccountQuery.FindByIdAsync` com 6 chamadores falsos e sem o handler; `AccountReadRepository.FindByIdAsync` sem nada | o modelo disse "o grafo não prova a cadeia" e reconstruiu por leitura — correto |

**F0.7.2 (indexer 0.2.3), motivado pela Q4:** C# ganhou os mesmos hooks que o Go — `file_facts`
(campos, propriedades, parâmetros de construtor primário, `base_list`, `usings`, namespace),
`call_receiver` (`this._x`, `_x`, propriedade, parâmetro, local com tipo explícito ou `new T()`,
`base.`), `resolve_receiver` (tipo por nome simples, desambiguado pelos `usings`; cadeia de membros;
membros herdados de bases do repo) e dois hooks novos no contrato: `supertypes` e
**`implementations`** — interface com **um único implementador** no repo liga também à implementação
(`receiver-type-impl`), que é a forma usual de DI em .NET. Regra de precisão: tipo do receiver
conhecido e sem o método nele, nas bases ou no implementador → **não chuta** por nome (antes virava
3 arestas ambíguas). Resultado no par: `AccountsController.FindByIdAsync → IAccountQuery.FindByIdAsync`
(`receiver-type`) **e** `→ AccountReadRepository.FindByIdAsync` (`receiver-type-impl`); os 6
falsos sumiram; os `_accountRepository.FindByIdAsync` herdados de pacote externo ficam sem aresta
(correto). Corpus: `-ambiguous` clean-arch 93→22, eShop 1004→787; no Go caiu mais um pouco
(alertmanager 641→620) porque receiver tipado como **interface** deixou de cair no fallback por nome —
é o caso que falta (implementador único por conjunto de métodos, F1). 8/8 arestas amostradas no
eShop corretas; símbolos/imports/HTTP byte a byte iguais; fixture `csharp-receiver-types` + 3 testes.

**Q4b re-rodada com 0.2.3:** ✅ `IAccountQuery.FindByIdAsync` → 1 chamador (o handler, `hops: 1`, não
ambíguo), rota e consumidor cross-repo corretos; os 6 falsos sumiram. ⚠️ `AccountReadRepository.FindByIdAsync`
ainda trazia 6 falsos: campos `IAccountReadRepository` (outra interface da mesma classe, cujo
`FindByIdAsync` vem de uma interface-base de pacote externo) caíam no implementador único e batiam
no símbolo da **implementação explícita** `IAccountQuery.FindByIdAsync`. Corrigido no mesmo dia:
`implementation_target(interface, método)` recusa o implementador quando o método nele é
implementação explícita de **outra** interface; `_accounts.FindByIdAsync` fica sem aresta (o método
real vem de pacote externo). Fixture ampliada; corpus inalterado. Esperado agora: a implementação
com **um** chamador interno (o handler).

**Q4b Go re-rodada com 0.2.3 (`impact_of` no método de domínio `password.Policy.Validate`):**
⚠️ `internal_callers` trouxe o caso de uso, mas `exposed_through` e `consumers` vieram vazios — a aresta
handler → `CompletePasswordReset.Execute` não existia no grafo de `main`. O `--dry-run` da mesma
árvore na branch produzia a aresta (`receiver-type`), o que isolou o problema no código do handler
em `main`: o struct do servidor **embute** o de configuração (`type Server struct { Config }`) e o
handler usa o campo promovido (`s.Complete.Execute(...)` em vez de `s.Config.Complete`). A cadeia de
campos de `resolve_receiver` só olhava campos declarados no struct. Corrigido em 0.2.4
(`languages/go/symbols.py`): `file_facts` registra os embeds e a busca de campo desce por eles
(ponteiro ou não, até 4 níveis); de quebra, helpers com retorno múltiplo (`uc, _ := setup(t)`) tipam
o local pelo índice. Fixture `go-receiver-types` ganhou o handler com embedding; corpus Go só
melhorou (alertmanager `-ambiguous` 620→425, `receiver-type` 1379→1905). Esperado após o
`refresh`: `exposed_through` com `POST /v1/password-reset/complete` (e as rotas de criação de
usuário, que também validam senha) e o BFF em `consumers`.

**Q4b Go re-rodada com 0.2.4:** ✅ resposta inteira pelo grafo, sem leitura de código. 58 chamadores
(7 produção, 51 teste); produção sem nenhuma aresta ambígua: caso de uso (1 hop), handler de reset
(2 hops, entry point) e a cadeia de criação de usuário até 4 hops (`createUser`/`createOnboardingUser
→ executeCreateUser → CreateUser.Execute → requiredFieldsPresent → Validate`). `exposed_through`: as 3
rotas (`POST /v1/password-reset/complete`, `POST /v1/users`, `POST /v1/onboarding/users`);
`consumers`: o BFF em `/v1/password-reset/complete` (`exact`, evidência com arquivo:linha, 14 refs).
Resíduo: 29 chamadores de **teste** chegam por `-ambiguous` (locais vindos de helpers/tabelas que a
tipagem Go ainda não cobre) — não afeta produção, amostra para F0.7.3. Observação: "rota sem
consumidor = pública" foi inferência do modelo; o atlas só afirma "nenhum consumidor nos repos
indexados" (vira dado com `Service` externo / `workspace_map`).
