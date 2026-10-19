# H2 — Roteiro e estado (corpus público + precisão/recall do extrator HTTP)

> Documento vivo do handoff H2. O *briefing* (o que e por quê) está em `H2-public-corpus.md`; aqui fica
> **o plano, as decisões e onde estamos**. Atualize "Onde estamos" e o "Log" ao fim de cada sessão.
> No ROADMAP geral, H2a = F0.4.3a e H2b = F0.4.3b.
>
> **Para retomar num chat novo:** ler este arquivo → `H2-public-corpus.md` → `docs/indexer-evolution.md`
> (§3 regras, §5 medição, §6 checklist) → `core/http_base.py` e `languages/<lang>/http.py` da linguagem
> em foco. Depois, rodar o corpus contra a baseline vigente (ver "Onde estamos").

## Onde estamos

- **Resumo final (2026-10-18): o H2 está encerrado.** F0.4.3a, F0.4.3b e o F1.14, que levou ao extrator o que o
  H2b e o hold-out deixaram, estão todos `[x]` no ROADMAP.
  - **Instrumento:**
    - `http_corpus.py` (`--baseline`, `--expected`, `--sample`, `--holdout`, `--reuse`) e o `corpus_metrics.py`;
    - o `corpus.sh`, que roda o corpus em paralelo, um container por repo;
    - os gabaritos em `indexer/tests/corpus_expected/`.
  - **Corpus:** de 15 repos (v1) a 55, 54 deles com gabarito; o hold-out guarda 3 repos (Kavita, go-boilerplate,
    sftpgo).
  - **Números finais** (P / R pelo gabarito, baseline `2026-10-18-v2-baseline-28`):

    | | C# | Go | Python | TS/JS |
    |---|---|---|---|---|
    | Rotas | 100 / 99,3 % | 98,9 / 93,3 % (97,7 % sem os RPCs Connect do memos) | 99,3 / 98,6 % fora do Django | 98,1 / 91,7 % |
    | Chamadas | 100 / 99,0 % | 100 / 93,6 % | — | 98,4 / 99,0 % |

  - **O hold-out de 2026-10-17 mostrou sobreajuste.** Nos 13 repos dele que o F1.14 trabalhou, o recall de rotas
    foi:
    - C#: de 32,2 a 99,8 %;
    - Go: de 0 a 79,3 % (95,7 % sem o Connect);
    - Python: de 83,8 a 100 %;
    - TS/JS: de 74,1 a 99,2 %.

    O de chamadas TS/JS foi de 76,5 a 100 %.
  - **O que sobra tem destino:**
    - Django: fora, até um portfólio pedir;
    - prefixos só conhecidos em runtime: limitação;
    - Connect: F2.1;
    - pastas de app de teste: F1.1;
    - tipo não declarado à vista: `needs-resolver`, para o F1.2.

    A tabela está em `docs/corpus-report.md`, "Closing F1.14 and H2".
  - **O hold-out novo vai para depois do H5 (H2-D21).**
  - **A seguir:**
    1. a fase 0a do H4;
    2. o H5;
    3. o hold-out novo e o handoff dele;
    4. o P2;
    5. o SCIP.

  O histórico abaixo fica como registro.
- **Estado:** H2a concluído (2026-10-14). H2b: **item 1 da Fase 4 fechado (2026-10-15, em duas rodadas)** — todas as
  correções baratas do relatório + router com nome de cliente, FP do roteamento convencional e genérico aninhado
  no C#, com fixtures `route-patterns-{go,ts,py,cs}`. Recall de rotas pelos gabaritos: C# 49 → 73 %, Go 6 → 15 %,
  Python 31 → 43 %, TS/JS 6 → 9 %; chamadas C# 19 → 24 %. **Fase 3 fechada (2026-10-15):** corpus v2 com 39 repos
  (24 novos, apps reais), 38 gabaritos, relatório v2. Nos apps reais o recall de rotas despenca fora do C#
  (Go 8,7 %, TS/JS 1,7 %, Python 1,0 %; C# 73 %) e o grafo de montagem aparece em 23 dos 38 repos. **Item 3 da
  Fase 4 fechado (2026-10-15), antes do 2:** os 15 defeitos baratos do v2 + 3 achados no julgamento; nenhuma das
  categorias sobra no ranking. H2-D9 e H2-D10 decididos (itens 6 e 7). **Item 2 em curso:** etapa 1 (dentro do
  arquivo: closures e montagens do mesmo arquivo) feita em 2026-10-15 — chi 14 → 75 % de precisão, fastify,
  Hono e NodeBB sobem; `prefix-other-scope` e `mount-same-scope` saem do ranking. **Reciclagem antes da etapa 2
  (2026-10-15):** escopos, expressões de path, grafo de montagem e tipos de nó saíram do `http_base.py` para
  módulos próprios; corpus idêntico nos 39 repos. Prioridade do portfólio registrada (H2-D18). **Item 6 fechado
  (2026-10-15):** `[Route]` herdado (um nível) e classes de endpoint (FastEndpoints, ApiEndpoints), com o primeiro
  passo entre arquivos (`compose`); rotas C# P 94,6 → 100 %, R 72,9 → 93,1 % nos gabaritos. **Chamadas C# do
  item 5 (2026-10-15):** constante em template como segmentos inteiros e wrappers de cliente do próprio app;
  chamadas C# P 84 → 100 %, R 64 → 97 % (TS/JS R 31,5 → 45 % de carona); extração HTTP do corpus 672 → 98 s.
  **NSwag do item 7 (2026-10-16), o último do .NET:** clientes NSwag C# (v13 e v14) e TS lidos, 3 apps .NET novos
  no corpus (42 repos), `[controller]`/`[action]` na caixa declarada com o linker sem distinção de caixa para
  ASP.NET, `[area]` e actions herdadas de base abstrata; C# com 10 repos: rotas R 96,9 %, chamadas R 99 %, P 100 %.
  **Etapa 2 do item 2 (2026-10-16), Go e Python:** grafo de montagem entre arquivos — routers com id global
  (variável de módulo/pacote, router devolvido por função, parâmetro router, campo de struct), arestas publicadas por
  arquivo e compostas depois do scan, imports pelo `resolve_import` de cada linguagem, constantes de outro pacote;
  rotas Go P 18,4 → 98,7 %, R 10,6 → 75,4 %; Python fora do Django P 37,7 → 96,1 %, R 19,3 → 93,4 %
  (mattermost R 0,2 → 99,8 %, gitea 0 → 59,1 %, dispatch 0,5 → 98,3 %). **Item 4 (2026-10-16), `route-chain`:**
  verbos encadeados num construtor de path (gitea `m.Combo("/x").Get(h).Put(h)`, express
  `router.route('/x').get(h)`), o builder do gorilla (`r.Methods("POST").Path("/x").Handler(h)`, `PathPrefix` com
  verbo), montagem por `http.StripPrefix` e router servido por `http.Serve` como aplicação; rotas Go P 98,9 %,
  R 75,4 → 90,5 % (gitea R 59,1 → 99,1 %, go-kit 59,3 → 100 %). **Chamadas Go e clientes gerados Go (2026-10-16):**
  path de `url.URL` (`u.Path = ..`/`+=`, `u.String()`), clientes go-kit (verbo no `NewClient`, path no encoder por
  `compose`), openapi-generator e go-swagger (`generated-client`); chamadas Go P 100 %, R 10,9 → 93,6 % nos mesmos
  gabaritos (kratos 10,5 → 96,1 % com as 60 operações do cliente gerado; alertmanager 0 → 93,8 %; go-kit 0 → 78,6 %).
  **Servidores gerados Go (2026-10-16):** grpc-gateway (`mux.Handle("GET", pattern_X, h)`, path decodificado do
  `runtime.NewPattern`) e servidor go-swagger (`o.handlers["GET"]["/x"]` sob o `basePath` do `embedded_spec.go`);
  rotas Go P 99,1 %, R 90,5 → 97,8 % (argo-cd R 3,5 → 96,5 %, alertmanager 0 → 100 %). **flask-restx e decorador
  aplicado à mão (2026-10-16):** `Namespace`/`Api` são routers, `add_namespace` monta, cada método de um `Resource` é
  rota; `router.post("/x")(fn)` é rota de `fn`; rotas Python fora do Django P 96,1 → 99,0 %, R 93,4 → 98,0 % (CTFd
  R 46,9 → 100 %). **TS no H2 (H2-D19), etapa 1 — grafo entre arquivos em TS/JS (2026-10-16):** imports ESM e
  CommonJS, exports e reexportações como arestas, `use` sem path, cadeias no construtor (Hono), genérico no
  construtor, o wrapper de montagem do próprio projeto (`lazyUse` do Ghost) e a aplicação que ninguém monta mantendo a
  raiz; rotas TS/JS P 5,9 → 50,4 %, R 3,7 → 32,9 % (ghost 0 → 100 %, express-realworld 0 → 100 %, hono 67,7 → 93,5 %).
  **Etapa 2 do TS — o Nest (2026-10-16):** `setGlobalPrefix` por pacote, com `exclude` (também lista de outro
  arquivo); argumento de decorator lido pela árvore (array, objeto `path`, constante ou membro de enum de outro
  arquivo); no caminho, o resolvedor de imports TS (`.js` do ESM → `.ts`; aliases a partir do pacote), +9845 arestas
  `IMPORTS` em 4 repos; rotas TS/JS P 50,7 → 93,9 %, R 32,6 → 60,7 % (immich 0,7 → 100 %). **Registrars próprios em
  TS/JS (2026-10-17):** wrapper de rota do projeto (NodeBB `setupApiRoute`/`setupPageRoute`) pelo mesmo mecanismo do
  wrapper de montagem, router de módulo devolvido pela função exportada, parâmetro opcional do Express no fim; rotas
  TS/JS P 94,0 → 95,5 %, R 59,7 → 85,3 % (NodeBB R 8,7 → 73,1 %). **Clientes gerados TS e requisição descrita por
  objeto (2026-10-17):** SDK do oazapfts (immich, 279) e do openapi-ts (fastapi-template, 23), `channel.post({ url })`,
  `axios.request({ url, method })`, `$.ajax(url, {..})`; chamadas TS/JS P 59,5 → 91,4 %, R 12,1 → 87,4 %. **Fase 5
  (2026-10-17):** os últimos defeitos baratos (`Client()` de teste do Django, `urljoin` com path
  absoluto, path de URL validado, restrição do Hono, `Sprintf` com constante de segmento, pastas de teste por nome);
  guia §3 e §5; relatório com "Closing H2b" (do primeiro v2 ao último, nos mesmos gabaritos e 38 repos: rotas
  C# R 55,6 → 93,1 %, Go 9,4 → 98,0 %, Python fora do Django 9,1 → 98,0 %, TS/JS 4,3 → 85,4 %; chamadas C# 48,3 →
  96,6 %, Go 8,2 → 93,6 %, TS/JS 6,1 → 87,4 %) e o destino de cada lacuna; ROADMAP com o **F1.14** (o que o H2
  deixou para o extrator). **Hold-out (2026-10-17, H2-D20):** 16 repos fora do ajuste, gabarito escrito antes de rodar,
  medidos uma vez — recall de rotas C# 48,5 %, Go 19,7 %, Python 83,8 %, TS/JS 74,1 %; chamadas TS/JS 76,5 % (no corpus:
  96,9, 98,0, 98,0 fora do Django e 85,4 %). Sobreajuste nas formas que o corpus não tinha (atributo de rota próprio,
  OData, FastEndpoints atrás de base própria, router de pacote atribuído em outro arquivo, gateway gerado novo) e dois
  defeitos de precisão (prefixo duplicado num grupo Go passado a função); tudo no F1.14. **H2 concluído; F0.4.3b `[x]`.**
- **Incremento atual:** nenhum. O H2b fechou em 2026-10-17; o F1.14, em 2026-10-18 (ver o resumo final acima).
- **Medir agora:** `http_corpus.py --expected --baseline <baseline> --show 20` (P/R por repo, resumo por
  linguagem e por categoria). Toda mudança no extrator roda contra essa baseline e esses gabaritos.
- **Branch:**
  - o H2b fechou na `feature/h2-corpus` (PR #4);
  - o F1.14 fechou na `feature/f114-close`, a partir da `main` depois desse merge.
- **Indexer de referência:** 0.2.15 (era 0.2.14 no fechamento do H2b).
- **Baseline vigente:** `~/.cache/aidd-corpus/runs/2026-10-18-v2-baseline-28/`, com 55 repos, no fechamento do
  F1.14. A do hold-out de 3 repos é a `2026-10-18-v2-holdout-26`.
- **Como rodar:** hoje o corpus roda com `indexer/scripts/corpus.sh` (em paralelo, com `--baseline` e `--holdout`) e
  os testes com `indexer/scripts/test.sh`. Os comandos abaixo são os do H2b.
- **Baselines do H2b:** `~/.cache/aidd-corpus/runs/2026-10-17-v2-baseline-16/`, corpus v2 com 42 repos, no fechamento
  do H2b (a `-15` é a dos clientes gerados TS; a `2026-10-16-v2-baseline-14` é a dos wrappers de rota TS; a `-13`, a do `setGlobalPrefix` do Nest; a `-12`, a do grafo entre arquivos em TS/JS; a `-11`, a do flask-restx; a `-10`, a dos servidores gerados Go; a `-9`, a das chamadas Go e dos clientes gerados Go; a `-8`, a das cadeias de rota do item 4; a `-7`, a da etapa 2 do grafo de montagem; a `-6`, a do NSwag do item 7; a `-5`, a das chamadas C# do item 5; a `-4`, a do item 6; a `-3`, a da etapa 1 do grafo de montagem; a `-2`, a dos defeitos baratos do v2; a `2026-10-15-v2-baseline` é
  o v2 com o extrator da Fase 3; a de 2026-10-14 fica como referência do v1).
  Para editar gabaritos sem extrair de novo: `--reuse <baseline>`; para medir mudança no extrator, nunca.
- **Como rodar** (a imagem `aidd-indexer:local` já traz as gramáticas; o código da árvore entra por
  `PYTHONPATH`, então não precisa rebuild a cada mudança):

  ```bash
  docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONPATH=/src \
    -v "$PWD/indexer":/src:ro -v ~/.cache/aidd-corpus:/corpus \
    --entrypoint python aidd-indexer:local /src/scripts/http_corpus.py \
    --dir /corpus/repos --json /corpus/runs/<data>-<rótulo>
  ```
- **Testes:** `docker run --rm -e PYTHONPATH=/src -v "$PWD/indexer":/src:ro -w /src -e PYTHONDONTWRITEBYTECODE=1
  --entrypoint python aidd-indexer-test:local -m pytest -q -p no:cacheprovider tests`, **sem** `--user`: com o
  usuário do host, 47 testes falham com permissão negada ao escrever no cache de gramáticas (`/opt/tslp-cache`).
- **Próximo passo no fechamento do H2b (2026-10-17, histórico; o F1.14 já o cumpriu):** o .NET está fechado (sobram `route-by-name-convention`, 10, para a convenção do
  projeto; 2 chamadas C#; o roteamento convencional do MVC, que serve páginas). **Go fechado no essencial:** rotas
  P 99,1 % / R 97,8 %, chamadas P 100 % / R 93,6 % (sobram os tipos de router do kratos, `prefix-in-router-type`, 12;
  `prefix-as-param`; `multi-app-repo`; o `MatchPath` do gitea, 3; e 7 chamadas `url-in-field`/`url-from-helper`/
  `client-in-field`). **Python fora do Django fechado no essencial:** rotas P 99,0 % / R 98,0 % (sobram o registro
  de plugins do dispatch, `router-from-registry`, 4, preenchido em runtime — limitação; e `multi-app-repo`, 4, no
  fastapi). **TS fechado no essencial (H2-D19):** rotas P 95,5 % / R 85,3 %, chamadas P 91,4 % / R 87,4 % (sobram
  nas rotas o prefixo montado em runtime, `prefix-as-param`, 119 no NodeBB — limitação; o laço sobre array literal
  do express-boilerplate, 14; o autoload por pasta do fastify-demo, 14; as rotas por arquivo do Next.js, 9; nas
  chamadas, o wrapper de cliente com prefixo próprio, `prefix-in-client-wrapper`, 34, e os wrappers do gitea, 15,
  que pedem o tipo do receiver em TS). **Próximo: o F1.14** (ROADMAP), a decidir com o autor — pelo hold-out, começar
  pelos defeitos de precisão (prefixo duplicado no Go) e pelo .NET (atributo de rota próprio, 760 rotas em 2 repos; OData;
  FastEndpoints atrás de base própria). Os repos do hold-out viram corpus quando forem trabalhados, e o fechamento do
  F1.14 precisa de um hold-out novo.

## Decisões

| # | Data | Decisão | Por quê |
|---|---|---|---|
| H2-D1 | 2026-10-13 | H2 em dois incrementos: **H2a** (instrumento + relatório v1 com os 15 repos atuais, fecha F0.4.3a) e **H2b** (ampliar para ~40 repos + evoluir o extrator, F0.4.3b) | Validar o instrumento num conjunto pequeno antes de ampliar; o ROADMAP já previa o corte |
| H2-D2 | 2026-10-13 | Cada repo do corpus é fixado por **SHA**, não pelo HEAD | Com `--depth 1` no HEAD a baseline muda sozinha e o diff deixa de significar algo |
| H2-D3 | 2026-10-13 | Clones e saídas ficam **fora do repo**, em `~/.cache/aidd-corpus/{repos,runs/<data>-<rótulo>}` | `/tmp` some no reboot; o corpus não é versionado |
| H2-D4 | 2026-10-13 | Gabarito só vem de **spec commitada**, de *routes dump* publicado ou de amostragem manual; **não rodar os apps** para gerar OpenAPI | Rodar o app executa código de terceiros e exige as dependências dele |
| H2-D5 | 2026-10-13 | Métricas separadas para rotas (`HttpEndpoint`) e chamadas (`HttpCall`); o recall de chamadas conta só as que têm path literal/template no código | Os perfis de erro são diferentes; URL montada em runtime não é falha do extrator |
| H2-D6 | 2026-10-13 | A amostragem mede precisão sorteando **do extraído** e recall sorteando **da fonte** (arquivos que registram rotas e fazem chamadas) | Sortear só do extraído nunca mostra um falso negativo |
| H2-D7 | 2026-10-13 | **tRPC fora de escopo** (registrar como limitação) | São procedures, não rotas REST por path |
| H2-D8 | 2026-10-13 | **Java/Kotlin fora**: não são linguagem parseável do indexer | Entra só se o ROADMAP adicionar a linguagem |
| H2-D9 | 2026-10-13 · **decidida 2026-10-15** | Clientes gerados (NSwag, openapi-generator, openapi-fetch, oazapfts): só medir no H2a e decidir com os números. **Decisão: extrair** como `HttpCall` com `via: generated-client`, um reconhecedor por gerador | v2: 371 operações em 4 clientes, 0 extraídas; no immich o SDK gerado é o único caminho do web ao servidor. Cada gerador escreve sempre a mesma forma, então o risco de FP é baixo |
| H2-D10 | 2026-10-13 · **decidida 2026-10-15** | `[Route]` herdado de classe base no ASP.NET: medir a frequência antes de decidir. **Decisão: seguir um nível** de herança — classe base do mesmo repo achada pelo nome; nome ambíguo (duas classes) não herda | v2: 26 de 60 controllers do jellyfin herdam `[Route("[controller]")]` (128 rotas sem prefixo, ações sem template perdidas); custo baixo |
| H2-D11 | 2026-10-13 | Precisão > recall: regra nova que sobe recall e derruba precisão em algum repo não entra | Um FP vira aresta errada no grafo depois do linker |
| H2-D12 | 2026-10-14 | Rota **ou chamada** com path incompleto — prefixo que o código tem (grupo, mount, `include_router`, campo/constante interpolado) e se perdeu — conta como **erro**; prefixo vindo de config/env (`BaseAddress`, `*_URL`) não conta (é do linker) | O path é a chave do linker; path errado vira ligação errada ou nenhuma |
| H2-D13 | 2026-10-14 | Medir **o que o grafo recebe** (depois do `_dedupe`), sem contornar a fusão de rotas iguais entre apps do mesmo repo | A fusão é um defeito real (evidência e handler de outro app), não um artefato da medição — vira a categoria `multi-app-repo` |
| H2-D14 | 2026-10-15 | O H2-D11 julga o erro **que a regra introduz**. Item novo errado só porque herda um defeito já categorizado dos irmãos do mesmo router (prefixo perdido em outro escopo/arquivo) é contado, mas não bloqueia a regra | Nas correções baratas, 6 das 74 rotas novas erraram assim (a regra extraiu exatamente o que está escrito); recusar a regra deixaria de fora 68 corretas e o defeito continua sendo do grafo de montagem, que corrige todas juntas |
| H2-D15 | 2026-10-15 | Gabarito com spec = **spec + rotas conferidas no código**: rota que só existe na spec (sem registro no código) sai; rota real fora da spec, achada ao conferir um item extraído, entra | A spec documenta a API pública, não tudo o que o código serve; sem isso a precisão contra o gabarito pune rotas certas (UI, redirects, health) |
| H2-D16 | 2026-10-15 | Item que precisa de mais de uma correção recebe **uma** categoria: a mais específica além do grafo de montagem (`m.Combo("/x").Get(h)` dentro de closure = `route-chain`; closure + mount em outro arquivo = `prefix-scope-and-file`) | O ranking diz qual regra destrava o quê; o grafo de montagem aparece em quase tudo e esconderia as outras |
| H2-D17 | 2026-10-15 | No resumo por linguagem, item da amostra conta na linguagem **do seu arquivo**, e o gabarito declara `language` por tipo quando difere da do repo (a UI React de um servidor Go). Cada categoria traz o **nº de repos** em que aparece | Repos mistos (backend + UI) misturavam linguagens; um repo grande (netbox, 1256 operações) não pode ranquear uma categoria sozinho |
| H2-D18 | 2026-10-15 | **Prioridade do portfólio:** .NET primeiro, Go e Python em segundo (o Python é FastAPI/Flask, não Django), TS em terceiro. A ordem da Fase 4 passa a pesar a linguagem, não só o tamanho da categoria no corpus; Django + DRF (item 8) segue adiado | O corpus pesa pelo volume dos repos públicos (Go e Python dominam as contagens), não pelo que os projetos reais usam; uma categoria pequena no .NET vale mais que uma grande só em TS |
| H2-D19 | 2026-10-16 | **O TS entra no H2**, depois de .NET, Go e Python fechados no essencial: grafo entre arquivos, `setGlobalPrefix` do Nest e clientes gerados TS, em etapas com corpus e commit cada uma | Recomendação de 2026-10-16, seguida no passo seguinte: reaproveita o grafo de montagem e o `compose` que Go e Python já usam; num incremento próprio, o mesmo contexto teria de ser remontado |
| H2-D20 | 2026-10-17 | **Hold-out do fechamento:** 16 repos que as regras nunca viram, no perfil do portfólio (C#: Umbraco-CMS, Elsa 3, Smartstore, Radarr, Kavita, btcpayserver; Go: photoprism, memos, go-boilerplate, sftpgo, vikunja; Python: mealie, open-webui; TS: directus, outline, docmost — 16), fixados por SHA em `HOLDOUT` (`http_corpus.py --holdout`, gabaritos em `corpus_expected/holdout/`). Gabarito escrito **antes** de rodar o extrator: a spec commitada onde houver, senão uma lista lida no código num escopo fixado antes; precisão por amostra sorteada (20 rotas e 20 chamadas por repo, `--sample 20 --seed 0`) julgada na fonte. Medido **uma vez**, no extrator de `c4ecc34`; nenhuma regra é ajustada por ele no H2 — o que aparecer vai ao F1.14; erro de gabarito achado ao julgar se corrige (H2-D15) | Escolha de 2026-10-17 a partir da lista do autor: fora os repos que já estão no corpus, os frameworks (rotas só em exemplos), os de leitura sabidamente ausente (Django, RPC próprio, Next.js/tRPC, rotas por arquivo, Ruby) e os de escala (odoo); open-webui entra para equilibrar o Python; os 6 da primeira recomendação (Radarr, Kavita, btcpayserver, sftpgo, vikunja, docmost) entram no mesmo dia, a pedido do autor — 5 deles com spec commitada. Medir uma vez e não ajustar é o que mantém o número honesto: um hold-out que orienta regras vira corpus |
| H2-D21 | 2026-10-18 | **O hold-out novo do fechamento do F1.14 vai para depois do H5**, como primeiro passo de um handoff próprio, e o F1.14 fecha sem ele. Na medição roda também o commit de antes do H5; o protocolo segue o H2-D20 (gabarito antes de rodar, amostra semeada julgada na fonte, medido uma vez, nenhuma regra ajustada por ele) | O H5 não muda comportamento (corpus idêntico a cada passo), então o número seria o mesmo antes ou depois; o que ele mostrar se corrige já no código refatorado; e a diferença entre os dois commits é regressão do H5 em código que o corpus não cobre. Custo aceito pelo autor: um defeito de precisão que ninguém viu fica na instalação durante o H5 |

## H2a — instrumento e relatório v1 (F0.4.3a)

### Fase 0 — preparação
- [x] Branch `feature/h2-corpus` a partir da `main`
- [x] Ambiente: `docker compose run --rm indexer ...` ou `pip install -e indexer` + `prefetch` (guia §4); a imagem `aidd-indexer:local` já faz o `selftest` no build
- [x] `CORPUS` com `(slug, sha)` por repo; clone por `git fetch --depth 1 origin <sha>` (H2-D2)
- [x] Default de `--dir` → `~/.cache/aidd-corpus/repos` (H2-D3)
- [x] **Baseline** antes de qualquer mudança no extrator: `--json ~/.cache/aidd-corpus/runs/<data>-baseline/`; anotar em "Onde estamos" e preencher a tabela "Números"

### Fase 1 — instrumento (`indexer/scripts/http_corpus.py`; o extrator não muda nesta fase)
- [x] `--baseline <dir>`: diff de ids `method path_key evidence` por repo (entrou/saiu), rotas e chamadas separadas
- [x] Formato do gabarito em `indexer/tests/corpus_expected/<repo>.json`:
      `{source, sha, scope, endpoints: [{method, path, category}], calls: [...], checked: {endpoints, calls}, notes}` (formato completo no docstring de `scripts/corpus_metrics.py`)
- [x] `--expected <dir>`: P/R por `(method, path_key)`, rotas e chamadas separadas (H2-D5)
- [x] Conversor OpenAPI/Swagger → gabarito, com `servers`/`basePath` como prefixo (reaproveitável no F2.1)
- [x] `--sample N --seed S`: amostra reprodutível com `evidence` para conferência na fonte
- [x] Teste unitário da função de métrica (sem rede)
- **Pronto quando:** rodar o corpus contra a baseline dá diff vazio, e um gabarito de brinquedo produz P/R conferido à mão.
  ✅ 2026-10-14: 0 de 15 repos com diferença; gabarito de brinquedo do gin-realworld (escopo `articles/`) deu
  P 2/9 e R 2/3, igual à conta à mão, e a amostra `checked` deu 2/3 com 1 pendente e 1 stale.

### Fase 2 — relatório v1 (15 repos)
- [x] Identificar quais dos 15 têm spec commitada → **3**: eShop (`Catalog.API.json` + `_v2`), alertmanager
  (`api/v2/openapi.yaml`, só recall) e fiber-recipes (`swagger/`). Gabaritos em `indexer/tests/corpus_expected/`.
- [x] Nos demais: 20 rotas + 20 chamadas sorteadas do extraído (precisão) e rotas/chamadas listadas a partir de arquivos sorteados da fonte (recall) (H2-D6)
  - Precisão: `--sample 20 --seed <n>` imprime entradas `checked` prontas para colar no gabarito; preencher `ok`/`category`.
  - Recall: sortear arquivos que registram rotas ou fazem chamadas (grep do framework por linguagem), listar à mão tudo o
    que eles têm e gravar com `scope` = esses arquivos. Se o grep virar rotina, transformar em `--sample-files`.
- [x] Cada erro com **categoria** da taxonomia abaixo (criar categoria nova quando nenhuma servir, e registrar aqui)
- [x] Medir H2-D9 (clientes gerados) e H2-D10 (`[Route]` herdado) — D9: 32 operações em 2 clientes gerados, 0 extraídas
  (recomendação: extrair como `generated-client`); D10: 0 ocorrências no v1, decidir com os repos do H2b
- [x] `docs/corpus-report.md` (EN): tabela repo × rotas × chamadas × P/R por linguagem; gaps por categoria com o que cada uma exigiria do extrator e o destino (extrator / linker F0.5 / OpenAPI F2.1 / limitação)
- [x] ROADMAP: F0.4.3a `[x]` + entrada em "Onde estamos"; docstring do script com a ordem de grandeza nova
- **Pronto quando:** o relatório existe, cada número é reproduzível pelo script e o ranking de categorias define a ordem do H2b.
  ✅ 2026-10-14: 235 rotas e 24 chamadas julgadas na fonte; P/R e categorias saem do `--expected`.

## H2b — corpus ampliado e evolução do extrator (F0.4.3b)

### Fase 3 — ampliar para ~40 repos
Critério: dar preferência a repos **com spec commitada** (o gabarito sai de graça), incluindo por linguagem
ao menos um monólito grande e um serviço "de empresa". Lista confirmada e fixada em 2026-10-15 (24 repos novos,
39 no total; SHAs em `CORPUS`):

| Linguagem | Repos novos (gabarito) | O que testam |
|---|---|---|
| Go | gitea (spec), mattermost (spec em fragmentos), kratos (spec), argo-cd (spec), gotify (spec), go-feature-flag (spec), go-kit-examples (manual) | `Group` com closure, `Combo`, subrouters gorilla em campos, router por tipo (`RouterAdmin`), grpc-gateway, echo, httprouter, go-kit |
| TS/JS | immich (spec), NodeBB (spec multi-arquivo), Ghost, express-boilerplate, fastify-demo, hono-examples, taxonomy (manual) | Nest real com prefixo global, helpers de registro, `lazyUse`, autoload por pasta, Hono, Next.js por arquivo, jQuery no cliente |
| C# | eShopOnWeb, eShopSupport, ardalis/CleanArchitecture, jellyfin, bitwarden/server (manual) | minimal API, controllers com `[Route]` herdado, FastEndpoints, ApiEndpoints, clientes tipados |
| Python | zulip (spec), netbox (spec), dispatch (spec), aiohttp-demos, CTFd (manual) | Django urlconf, DRF routers, `include_router(prefix=)` entre arquivos, aiohttp, flask-restx |

Fora: hashicorp/vault (licença BUSL; o fork openbao não tem spec commitada) e **grafana**, que era
candidato e não roda: a extração do repo inteiro (24 mil arquivos) é morta por memória a 7,7 GB no Docker
Desktop — achado de escala do indexer, registrado no relatório e no ROADMAP como **F1.13** (repos grandes).

- [x] Selecionar e confirmar a lista; fixar SHAs; gabaritos onde houver spec — e lista à mão nos demais
- [x] Rodar e estender `corpus-report.md` (seção v2)

### Fase 4 — evoluir o extrator (ordem definida pelo ranking do relatório)
Por categoria: fixture → mudança em `languages/<lang>/http.py` (ou `core/http_base.py` se for comum) →
`pytest` → corpus `--baseline` (nenhum repo pode regredir, H2-D11) → tabela §3 do guia → nova baseline.
Um commit por categoria. Ordem do relatório v1, **revista pelo v2 em 2026-10-15** ("What H2b should do, in order
(v2)" no relatório; categorias e contagens lá):
- [x] **1. Correções baratas e gerais**
  - [x] *(2026-10-15)* `root-route-dropped` (raiz só com path completo conhecido: app ou grupo com prefixo),
    `route-constraint-syntax` (placeholder mascarado na validação; `?` opcional antes da query), `no-leading-slash`
    (`relative_on_groups` em Go/C#), `client-named-router` (router do arquivo vence o nome) e o FP do roteamento
    convencional do ASP.NET — fixtures `route-patterns-{go,ts,py,cs}`
  - [x] *(2026-10-15, 2ª rodada)* `optional-segment-syntax`, `query-in-template`, `method-default` (`fetch` = GET), `test-client-in-source`,
    `verb-alias` (`Del`) e `nested-generic-callee` (C# `<List<T>>`, achado no caminho)
- [x] **2. Grafo de montagem** *(fechado em 2026-10-16, com o TS)* — no v2 aparece em 23 dos 38 repos com gabarito (200 wrong, 1837 missed).
  - [x] *(2026-10-15)* etapa 1, dentro do arquivo: regiões de closure (`Route`/`Group` com func, `register(fn,
    {prefix})`), montagens do mesmo arquivo (`use`, `route`, `Mount`, `include_router`, `register_blueprint`,
    `basePath`), raiz de sub-router montado, `With`/`Use` — fixtures `route-patterns-*/…/mounts`
  - [x] *(2026-10-15)* reciclagem antes da etapa 2, sem mudar comportamento: `core/http_scope.py` (escopos e
    ligações de nomes), `core/http_expr.py` (expressões de path), `core/http_mounts.py` (o grafo de montagem do
    arquivo, a peça que a etapa 2 compõe entre arquivos), `core/http_nodes.py` (tipos de nó); `http_base.py` fica
    com o scanner e os ganchos por linguagem
  - [x] *(2026-10-16)* etapa 2, Go e Python: entre arquivos e funções — router com id global (`var:`, `ret:`,
    `param:`, `field:`), arestas publicadas por arquivo e compostas depois do scan (`http_mounts.compose`), imports
    pelo `RepoView` (`resolve_import` de cada linguagem), constantes de outro pacote (`foreign_const`), router
    parâmetro de região de closure = router de fora; achados no caminho: restrição com chaves aninhadas ou `?`,
    alternativas literais num segmento, `Methods` com vários verbos, `Group().Use()`, raiz na aplicação. Fixtures
    `route-patterns-go/{cmd/crossfile,internal}` e `route-patterns-py/app/crossfile`
  - [x] *(2026-10-16)* etapa 2 para TS/JS: imports ESM e CommonJS (`TsScanner.read_imports`), exports e
    reexportações como arestas sem prefixo, filhos de montagem de outro arquivo (`require('./x')`, `routes()`,
    `m.router`), router como argumento de função de outro arquivo, `use` sem path, cadeias no construtor ligadas ao
    nome, wrapper de montagem do projeto (`ts.mount-wrapper` + candidatos `ts.mount.maybe` + `TsScanner.compose`);
    aplicação nomeável publicada (`<regra>.app`). Fixture `route-patterns-ts/src/crossfile`
  - [x] *(2026-10-16)* prefixo global (`setGlobalPrefix` do Nest) — etapa 2 do TS: fato por pacote
    (`ts.nest-prefix`), rotas Nest esperando o `compose` (`ts.nest`), `exclude` com curingas e lista exportada de
    outro arquivo (`ts.string-array`); decorator Nest lido pela árvore e membro de enum TS como constante
    (`Enum.Membro`, `foreign_const` qualificado); resolvedor de imports TS (`.js` → `.ts`, aliases do pacote). Fixture
    `route-patterns-ts/nest/` (pacote próprio) e `src/plain.controller.ts`; teste `test_resolve_ts.py`

  Ordem original:
  mesmo escopo (`app.use('/api', router)` ao lado das rotas, Hono `route`/`basePath`) → mesmo arquivo (closures
  `r.Route`/`m.Group(..., func)`, `register(fn, {prefix})`) → prefixo global (`setGlobalPrefix`) → entre arquivos
  (imports, constantes/enums, campos de struct, funções-helper chamadas dentro de grupos, `include_router(prefix=)`).
  Passo pós-scan em `integrations.py`, `confidence: heuristic` → bump `INDEXER_VERSION` e `SCHEMA.md` se o nó ganhar campo.
  Entre arquivos, trabalhar com um **resumo por arquivo** (quem monta o quê, com que prefixo), não com as árvores de
  outros diretórios — restrição do F1.13 (repos grandes)
- [x] **3. Defeitos baratos do v2** *(2026-10-15, feito antes do item 2)* — precisão: `variable-other-scope`,
  `call-taken-for-route` (jQuery `$.get(url, cb)`), `mount-as-route`, `route-taken-for-call`, `build-artifact`,
  `non-http-verb`; recall: `const-concat`, `multiline-receiver`, `mime-like-head`, `const-base-url`,
  `method-keyword`/`method-variable`, `verb-alias` (`del`), `default-mux-function`, `group-chain`,
  `aiohttp-router`; achados no julgamento: variável interpolada que lê o próprio valor anterior, `x += e`, e o
  contraexemplo do wrapper genérico (constante de módulo em template fica placeholder). Sobra 1 item
  (`data-taken-for-handler`, gotify)
- [x] **4. `route-chain`** (gitea `Combo`, builders gorilla, express `router.route()`) *(2026-10-16)* —
  `BaseScanner.route_chain` (cada verbo depois do construtor é rota no path dele: `Combo` no Go, `route` de um
  argumento no TS); builder do gorilla com `Methods`/`Path`/`PathPrefix` antes ou depois do `Handler` (`PathPrefix`
  só é rota com verbo); no caminho, `http.StripPrefix` monta o router de dentro e um router de outro arquivo
  servido por `http.Serve`/`ListenAndServe` é aplicação (as rotas valem nos dois lugares). Fixtures
  `route-patterns-go/cmd/{combo,chain,addsvc}` e `route-patterns-ts/src/chain.ts`
- [x] **5. Chamadas:** `field-in-interpolation` (TS e C#), `url-object-builder` (todas as linguagens), `request-config-object`
  *(fechado em 2026-10-17; sobram o `adminUrl` do ghost, de `window.location` — limitação — e 2 `url-object-builder`,
  no F1.14)*
  - [x] *(2026-10-17)* `request-config-object` (TS/JS): objeto com `url` num método de verbo ou em
    `request`/`ajax`/`axios` é a requisição, qualquer que seja o receptor; verbo do nome, do `method` ou do `type` do
    próprio objeto, senão GET — zulip `channel.post({ url })`, gotify `axios.request`, `$.ajax(url, {..})`; o mesmo
    caminho lê o SDK do openapi-ts. Fixture `route-patterns-ts/src/clients/config-requests.ts`
  - [x] *(2026-10-16)* Go: `url-object-builder` — `url.URL` pelo `u.Path` (`=`, `+=`, `path.Join(u.Path, ..)`),
    `u.String()`, `u.JoinPath(..)`, `url.Parse(literal)`; `request-encoder` do go-kit (`NewClient(method, tgt, enc,
    dec)`, path do encoder por `go.encoder` + `Pending` + `GoScanner.compose`); no caminho, verbo em variável
    (`localVarHTTPMethod = http.MethodGet`, `&http.Request{Method: ..}`), e os contraexemplos `huma.Get(api, "/x",
    h)` (rota, não chamada) e `"SELECT " + strings.Join(..)` (não é `"MÉTODO /path"`). Fixtures
    `route-patterns-go/internal/{notify,kitclient}`
  - [x] *(2026-10-15)* C#: constante interpolada como segmentos inteiros (de path no começo; de uma palavra entre
    barras), nunca num wrapper genérico (variável de nome de path no template); chamada interpolada que já é path
    (`CombineUri`); wrappers de cliente do app (`HttpService.HttpGet(uri)`) por fato + `Pending` + `compose`, com o
    tipo declarado do receiver. Sobra em TS: o `adminUrl` do ghost (`window.location`) e os wrappers do gitea
    (precisam de tipo do receiver em TS)
- [x] **6. C#:** herança de `[Route]` (H2-D10, aceito: um nível) e classes de endpoint (FastEndpoints, ApiEndpoints)
  *(2026-10-15)* — primeiro passo entre arquivos (`facts` + `Pending` → `CsScanner.compose`); constante de classe
  por `Classe.NOME`; `nameof(X)` e variável local em interpolação do C#; `[action]` sem `Async`. Fixtures em
  `route-patterns-cs` (herança entre arquivos, base ambígua, FastEndpoints, ApiEndpoints)
- [x] **7. Clientes gerados** *(fechado em 2026-10-17)* (H2-D9, aceito): `via: generated-client`, fixture por gerador
  - [x] *(2026-10-16)* NSwag, C# e TS — o corpus não tinha nenhum (os do v1 são openapi-ts e go-swagger; o do
    clean-arch-dotnet é gitignored), então entraram RapidBlazor, azure-saas e notifo. C#: arquivo com o cabeçalho do
    NSwag (o `.g.cs` deixa de ser excluído quando é dele), path do `// Operation Path` (v14) ou dos
    `urlBuilder_.Append` (v13), verbo do `request_.Method`. TS: o template do `fetch` já era lido; `path_of`
    memoizado (profundidade 4 → 64, as cadeias `url_ = url_.replace(..)`/`url_ +=`) e verbo pela variável
    `options_`. No caminho: caixa declarada + linker sem caixa para ASP.NET, `[area]` e `{area}`/`{controller}`/
    `{action}` reservados, actions herdadas de base abstrata. Fixtures em `route-patterns-cs` (v13, v14, área, base
    genérica) e `route-patterns-ts` (cliente NSwag)
  - [x] *(2026-10-16)* Go: openapi-generator (kratos, 60 operações em duas cópias, iguais à `spec/api.json`) e
    go-swagger (alertmanager, 9; o `basePath` fica com o transporte, como base URL). Fixtures
    `route-patterns-go/internal/{genclient,swaggerclient}`
  - [x] *(2026-10-17)* oazapfts (immich, 279: `oazapfts.fetchJson/fetchText/fetchBlob`, path sem `${QS.query(..)}`
    sob o `baseUrl` literal, verbo das opções) e openapi-ts (fastapi-template, 23: `client.post({ url })`, pela
    requisição descrita por objeto). Gabaritos de chamadas novos: immich (as 279 da spec sob `/api`) e
    fastapi-template (as 23 rotas). Fixtures `route-patterns-ts/src/clients/{fetch-client.ts,sdk.gen.ts}`
  - [x] *(2026-10-16)* Go, **servidores** gerados (`generated-server`): grpc-gateway (`runtime.NewPattern`
    decodificado; handler = método gRPC; verbo customizado `:x` literal) e go-swagger (`o.handlers[M][P]` +
    `basePath` publicado pelo `embedded_spec.go`, `go.swagger-base`). Fixtures
    `route-patterns-go/internal/{gateway,swaggerserver}`
- [x] *(2026-10-17)* **Registrars próprios em TS/JS** (`custom-registrar`, 353 no NodeBB; decisão de 2026-10-17:
  tratar no H2, pela recomendação — helper de registro é comum em projetos reais): `ts.route-wrapper` (formas do
  wrapper) + candidatos `ts.route.maybe` + `TsScanner.compose`, registros do corpo do wrapper marcados (`ts.wrapped`)
  e descartados só quando o wrapper é usado; router de módulo devolvido pela função exportada; parâmetro opcional do
  Express no fim. Fixture `route-patterns-ts/src/crossfile/wrappers`
- [x] **8. Scanners novos, quando um portfólio pedir:** Django + DRF (maior lacuna isolada: 1420 em 2 repos),
  rotas por arquivo do Next.js, flask-restx *(2026-10-17: Django e Next.js encaminhados ao F1.14)*
  - [x] *(2026-10-16)* flask-restx (também `flask_restplus`/`flask_restful`), adiantado pelo H2-D18 (o Python do
    portfólio é Flask/FastAPI): `Namespace`/`Api` como routers, `Api(blueprint)` montado no blueprint,
    `add_namespace(ns, path)` como montagem entre arquivos, uma rota por método do `Resource`; no caminho, o
    decorador aplicado à mão (`router.post("/x")(fn)`, dispatch). Fixtures `route-patterns-py/app/{restx,decorcall.py}`
- [x] **9. `test-app-folder`** (agora em 4 repos): exclusão por repo no `atlas.yaml` é a resposta mais segura
  *(2026-10-17: `e2e-tests/`, `cypress/`, `playwright/` e `testhelpers/` entram no `TEST_FILE` — kratos e mattermost;
  `integration/` do nest e do fastify, 20 rotas, fica para a config por repo do F1.1)*
- [x] Decidir H2-D9 e H2-D10 — *(2026-10-15)* as duas recomendações do relatório aceitas (itens 6 e 7)

### Fase 5 — fechamento
- [x] *(2026-10-17)* ROADMAP: F0.4.3b `[x]`; gaps encaminhados — base URL → F0.5 linker; spec
  como fonte → F2.1; evolução do extrator → **F1.14** (novo); pastas de app de teste com nome de produção → F1.1;
  resto → limitação no guia. Tabela "Where each remaining gap goes" em `corpus-report.md`
- [x] *(2026-10-17)* Guia: §3 (composição entre arquivos com o TS, as regras novas com o sintoma, limitações
  agrupadas por destino) e §5 (o ciclo de uma mudança: fixture que falha sem a regra → corpus `--baseline` →
  julgamento item a item → gabaritos com H2-D15/H2-D17 → nova baseline; repos antes do `--expected`; picos de tempo)
- [x] *(2026-10-17)* Últimos defeitos baratos do ranking final, cada um com fixture: `Client()` de teste do Django
  (zulip, 9 chamadas), `urljoin` com path absoluto (zilencer), path de URL validado (`is_url_literal`, a pendência
  do `URL_LITERAL`), restrição de regex do Hono, `Sprintf` com constante de segmento (kratos `/schemas`, exposto
  pela mudança seguinte), `TEST_FILE` com `e2e-tests/`, `cypress/`, `playwright/`, `testhelpers/` (item 9 da Fase 4,
  em parte: `integration/` fica para a config por repo)
- [x] Dívidas registradas na reciclagem de 2026-10-15 (nenhuma bloqueia a Fase 4):
  - [x] *(2026-10-17)* encaminhadas ao **F1.14**: catálogo de frameworks como dado (verbos, nomes de registro,
    receptores de cliente), com os scanners pedindo o cliente às convenções em vez de ler `CLIENT_RECEIVER`; os
    limiares fixos do `built_bundle` (nenhum erro no corpus)
  - [x] *(2026-10-17)* um conjunto de repos fora do ajuste (*hold-out*), medido só no fechamento, para checar
    sobreajuste ao corpus — 16 repos (H2-D20), `http_corpus.py --holdout`, gabaritos em `corpus_expected/holdout/`;
    resultado em `corpus-report.md` ("The hold-out set") e no F1.14
  - [x] *(2026-10-16)* na etapa 2, reaproveitar a resolução de imports do `resolve.py` em vez de uma segunda —
    `RepoView` chama o `resolve_import` de cada linguagem
  - [x] *(2026-10-17)* custo do HTTP no netbox (49 s de 107 s, com 0 rotas e 0 chamadas; zulip 17 s de 47 s) —
    anotado no F1.13, para perfilar junto
- [x] Pendências do item 6, fora do corpus atual:
  - [x] *(2026-10-16)* linker: rotas ASP.NET casadas sem distinção de caixa (F0.5); o extrator passou à caixa
    declarada, a dos clientes gerados
  - [x] *(2026-10-16)* actions herdadas de controller base abstrato (CRUD genérico) — notifo, 27 rotas
  - [x] *(2026-10-17)* FastEndpoints `RoutePrefix` global e `Group<T>()`, herança de `[Route]` em mais de um nível
    (0 no corpus) → F1.14, medir quando a fatia .NET crescer
- [x] Pendências das chamadas C# (item 5):
  - [x] *(2026-10-16)* **fora do HTTP:** chamada genérica com receiver (`obj.Method<T>(...)`) vira call site; tipo de
    pacote no receiver só alcança extensão do repo (ROADMAP, log de 2026-10-16)
  - [x] *(2026-10-17)* `URL_LITERAL` aceitava qualquer caractere depois do host — `is_url_literal` exige um path de
    rota depois dele
  - [x] *(2026-10-17)* wrappers de cliente em TS (gitea, 16; com prefixo, 34) e Python → F1.14

## Taxonomia de erros

As categorias medidas, com exemplos, o que exigiriam e o destino, estão em `docs/corpus-report.md` ("Gaps by
category" do v1 e do v2); o `--expected` as reconta a cada execução a partir do campo `category` dos gabaritos.
Das categorias previstas no plano, o v2 viu `route-by-file-path`, `django-urlconf`, `inherited-route-attr` e
`generated-client` (medido, não é categoria de gabarito); `lowercase-verb-ambiguous` apareceu como `non-http-verb`
(`Get(key)` de um cache). Seguem fora da métrica:

| Categoria | Exemplo | Destino |
|---|---|---|
| `runtime-url` | URL montada sem literal, link lido da página | fora da métrica (H2-D5) |
| `base-url-in-config` | `BaseAddress = new Uri(...)`, `*_URL`, `globalSettings.X.BaseUrl` | linker F0.5 |

## Números

Tabela do **v1** (2026-10-14), mantida como referência; os números atuais saem do `--expected`, a comparação
v1 → correções baratas está no relatório ("Update: the cheap fixes") e as tabelas do corpus v2 (39 repos, por
linguagem e por repo) estão em "v2: the widened corpus".

Referência 2026-09 = ordem de grandeza do docstring antigo, medida no HEAD de então (SHA desconhecido). Baseline = 2026-10-13 nos
SHAs fixados — a diferença entre as duas mistura mudança dos repos e do extrator, então não serve como regressão.

| Repo | Ling. | Rotas (ref. 2026-09) | Chamadas (ref.) | Rotas (baseline) | Chamadas (baseline) | Gabarito | P rotas (amostra) | R rotas (gabarito) | P chamadas (amostra) | R chamadas (gabarito) |
|---|---|---|---|---|---|---|---|---|---|---|
| chi | Go | 26 | — | 25 | 0 | manual (3 exemplos) | 24 % (6/25) | 4,5 % | — | — |
| gin-examples | Go | 31 | — | 31 | 0 | manual (4 exemplos) | 95 % (19/20) | 8,3 % | — | — |
| gin-realworld | Go | 13 | — | 12 | 0 | manual (routers) | 0 % (0/12) | 0 % | — | — |
| fiber-recipes | Go | 135 | — | 127 | 5 | openapi (swagger/) + manual (calls) | 100 % (20/20) | 50 % (2/4) | 80 % (4/5) | 100 % (4/4) |
| alertmanager | Go | 22 | — | 22 | 0 | openapi (/api/v2) + manual (calls) | 68 % (15/22) | 0 % (0/9) | — | 0 % (0/7) |
| gorilla-mux | Go | 0 (só lib) | — | 0 | 0 | — (só lib) | — | — | — | — |
| express | TS | 33 | — | 31 | 0 | manual (multi-router) | 85 % (17/20) | 0 % (0/5) | — | — |
| express-realworld | TS | — | — | 19 | 0 | manual (controllers) | 0 % (0/19) | 0 % | — | — |
| nest | TS | 124 | — | 195 | 1 | manual (2 samples) | 15 % (3/20) | 0 % (0/4) | 100 % (1/1) | — |
| fastify | TS | 6 | — | 6 | 1 | manual (examples/) | 33 % (2/6) | 33 % | 100 % (1/1) | — |
| eshop | C# | 23 | 6 | 23 | 6 | openapi (Catalog) + manual | 90 % (18/20) | 67 % (18/27) | 50 % (3/6) | 19 % (3/16) |
| clean-arch-dotnet | C# | 0 (convenção) | — | 0 | 0 | manual (Endpoints/) | — | 0 % (0/10) | — | — |
| fastapi | Py | 87 | — | 84 | 11 | manual (bigger_applications) | 100 % (20/20) | 38 % (3/8) | 64 % (7/11) | — |
| fastapi-template | Py | 19 | — | 19 | 0 | manual (api/routes) | 0 % (0/19) | 0 % | — | — |
| flask | Py | 12 | — | 12 | 0 | manual (3 exemplos) | 100 % (12/12) | 67 % (12/18) | — | — |

## Log

- **2026-10-13** — Plano aprovado: H2 dividido em H2a/H2b (H2-D1), decisões H2-D2…D11 registradas. Ambiente
  local ainda sem venv nem gramáticas (`aidd_indexer` não importa); o Docker está disponível.
- **2026-10-13** — Fase 0. Worktree `feature/h2-corpus` (a partir da `main`). O split do F0.4.3 no ROADMAP
  entrou na branch de dispatch (`01ef61a`): não mexer nessas linhas do ROADMAP nesta branch até o merge.
  `http_corpus.py`: `CORPUS` por SHA, clone do SHA exato, `--dir` padrão `~/.cache/aidd-corpus/repos`,
  JSON com `repo`/`sha`, docstring com a baseline nova. Achados: (1) no bind mount do Docker Desktop o
  primeiro `git fetch` num repo recém-criado falha com `bad object` e o segundo funciona → o script tenta
  3 vezes; (2) **nest: 157 das 195 rotas vêm de `integration/`** (apps de teste do próprio framework, que
  o filtro de pastas de teste não pega) → categoria candidata `test-app-folder`, avaliar na Fase 2.
- **2026-10-14** — Dispatch mergeado na `main` (f854509, indexer 0.2.14); o H2 virou a frente principal. O
  trabalho saiu do worktree e voltou para a pasta principal (branch recriada a partir da `main` nova, e o
  aviso sobre as linhas do ROADMAP deixou de valer). Baseline regenerada (`2026-10-14-baseline`) e idêntica
  à de 2026-10-13 em método, `path_key`, evidência e `handler_id` nos 15 repos: o dispatch não tocou na
  extração HTTP.
- **2026-10-14** — Fase 1. `scripts/corpus_metrics.py` (novo, funções puras): ids `method path_key evidence`
  e diff entre execuções (removidos, adicionados e `~` para mudança de `handler_id`/`caller_id` no mesmo id);
  P/R por pares distintos `(method, path_key)`, com ANY casando qualquer método e `scope` limitando o extraído;
  precisão manual por `checked`, que acusa itens stale; amostra com seed por repo e tipo; `from-openapi` com o
  prefixo de `basePath`/`servers[0].url` (ou `--prefix`). `http_corpus.py` ganhou `--baseline`, `--expected
  [dir]` (padrão `tests/corpus_expected/`), `--sample/--seed` e `--show`, e avisa quando o SHA do gabarito ou
  da baseline difere do pin. `tests/test_corpus_metrics.py`: 10 testes; a suíte inteira passa (157 ok, 2 skipped).
- **2026-10-14** — Fase 2 iniciada. Specs commitadas em 3 dos 15 repos → gabaritos `openapi` (o `from-openapi`
  passou a aceitar várias specs, para a união v1+v2 do eShop). Resultado: eShop Catalog P 100 % R 75 % (os 4 FN são
  restrições de rota que o literal rejeita), fiber-recipes `swagger/` P 100 % R 50 % (as 2 rotas "faltantes" foram
  fundidas com as de outra receita: o id do endpoint é por repo e o `_dedupe` fica com a primeira evidência),
  alertmanager `/api/v2` R 0 % (servidor gerado pelo go-swagger). Decisões H2-D12 e H2-D13.
- **2026-10-14** — Fase 2 concluída, **H2a fechado**. Amostra manual em todos os repos (235 rotas, as 24 chamadas)
  e recall por arquivos lidos inteiros; gabaritos em 14 repos (gorilla-mux é só lib). O instrumento ganhou
  `scope`/`source` por tipo, `category` no item esperado (por que falta) e os resumos por linguagem e por categoria.
  Achados principais: 67 das 103 rotas erradas só perderam o prefixo; `"/"` nunca vira rota (`path_of`); restrições
  de rota derrubam a rota inteira; o id do endpoint por repo funde apps (`multi-app-repo`); clientes gerados não são
  vistos (H2-D9). H2-D12 estendido às chamadas. `docs/corpus-report.md` v1 e F0.4.3a no ROADMAP.
- **2026-10-15** — H2b, Fase 4 item 1 (parte). `route_path` no `BaseScanner` (raiz só com path conhecido — app
  reconhecido por (escopo, nome) —, placeholders mascarados, padrão relativo em grupo onde o framework aceita) e
  `mask_placeholders`/`normalize_path` em `core/paths.py`; router do arquivo vence `CLIENT_RECEIVER`; ação sem
  template em controller sem `[Route]` não vira `GET /`. Diff contra a baseline julgado item a item: 74 rotas
  novas (68 certas; 6 erradas só pelo prefixo perdido dos irmãos) e 2 FPs a menos. Um erro da própria regra
  apareceu e foi corrigido no caminho (padrão relativo em `APIRouter` de callback OpenAPI → `relative_on_groups`
  só em Go/C#). Gabaritos: `category` limpo nos itens encontrados e reclassificado nos que faltam; categorias
  novas `client-named-router` e `app-not-recognized`. Sem bump de `INDEXER_VERSION`: a impressão digital do
  build já reindexa. Nova baseline `2026-10-15-baseline`. H2-D14 confirmado.
- **2026-10-15** (2ª rodada) — H2b, Fase 4 item 1 fechado. As cinco correções baratas menores (query fora da validação do
  template, `fetch` = GET, `TestClient` não é chamada de saída, grupo opcional do Express 5, `Del`) e uma achada no
  caminho: genérico aninhado no callee C# (`GetFromJsonAsync<List<T>>`) fazia a chamada sumir — e tinha escondido
  `GET /api/webhooks` também do gabarito do eShop (o grep da listagem tinha o mesmo ponto cego); gabarito corrigido.
  Diff julgado item a item: 4 FPs de `TestClient` a menos, 1 método corrigido, 3 rotas normalizadas, 1 rota nova
  (`DELETE` do alertmanager, sem `/api/v1` como as irmãs) e 10 chamadas novas no eShop (2 certas; as do catálogo
  sem o `api/catalog/` do campo interpolado, como as irmãs) — H2-D14: precisão de chamadas C# no gabarito
  50 → 40 %, recall 19 → 24 %. Amostra: itens que deixaram de ser extraídos saíram; os do mesmo local com path ou
  método corrigido foram atualizados. Nova baseline `2026-10-15-baseline-2`.
- **2026-10-15** — H2b, Fase 3 fechada. 24 repos novos fixados por SHA (39 no total): Go (gitea, mattermost, kratos,
  argo-cd, gotify, go-feature-flag, go-kit-examples), TS/JS (immich, NodeBB, Ghost, express-boilerplate, fastify-demo,
  hono-examples, taxonomy), C# (eShopOnWeb, eShopSupport, ardalis/CleanArchitecture, jellyfin, bitwarden), Python
  (zulip, netbox, dispatch, aiohttp-demos, CTFd). grafana saiu: a extração do repo inteiro é morta por memória a
  7,7 GB no Docker Desktop (achado de escala do indexer). Gabaritos: spec onde há (11 dos novos, 14 no total; mattermost em
  fragmentos, NodeBB multi-arquivo — o `from-openapi` passou a seguir `$ref` externo), lista lida na fonte nos
  demais; amostra de 20 rotas + 20 chamadas julgada na fonte em cada repo. Decisões H2-D15 (spec + rotas conferidas
  no código), H2-D16 (uma categoria por item: a mais específica além do grafo de montagem) e H2-D17 (linguagem por
  arquivo no resumo; nº de repos por categoria). Instrumento: `--reuse`, `language` no gabarito, coluna `repos`.
  Extrator intocado: os 15 do v1 idênticos à baseline anterior; extração do v2 idêntica à usada nos gabaritos.
  Achados: o grafo de montagem em 23 de 38 repos (200 wrong, 1837 missed); defeitos baratos novos (`const-concat`,
  `multiline-receiver`, `variable-other-scope`, `mime-like-head`, jQuery `$.get` como rota, mount como rota);
  H2-D9 com 371 operações em 4 clientes gerados (0 extraídas); H2-D10 com 26 de 60 controllers do jellyfin herdando
  `[Route("[controller]")]` (128 rotas sem prefixo). Correção de datas: o trabalho registrado como 2026-10-16 foi
  feito em 2026-10-15 (2ª rodada); a baseline passou a se chamar `2026-10-15-baseline-2`. Nova baseline
  `2026-10-15-v2-baseline`.
- **2026-10-15** — H2b, Fase 4 item 3 fechado (antes do item 2). Os 15 defeitos baratos do v2, cada um com caso
  nas fixtures `route-patterns-*`: constantes só do módulo/classe e nome procurado da função mais interna para
  fora (parâmetro encerra), constante montada por `+` e com URL absoluta, `$`/`jQuery` como cliente, padrão com
  `/` final no `ServeMux` como montagem, argumento espalhado desembrulhado, bundle de build fora da extração HTTP,
  segmento sem nome não é path, callee sem espaços, MIME só com dois tokens, método de keyword e de variável,
  `del`, mux padrão, prefixo pela cadeia `Group().Use()`, aiohttp. O julgamento do diff achou 3 defeitos das
  próprias regras e os corrigiu no caminho: a chamada do CTFd que lia o próprio valor anterior em template (variável
  local interpolada passou a ser resolvida — constante de módulo não, contraexemplo do alertmanager), `x += e`
  (path e método do mesmo ramo; com base desconhecida só vale o trecho com segmento nomeado — chi `FileServer`).
  Diff contra `2026-10-15-v2-baseline` julgado item a item: rotas −37 +49, chamadas −54 +186; o que errou
  entre os novos só herda defeito já categorizado das irmãs (7 rotas do kratos sem `/admin`, 127 chamadas de
  argo-cd e NodeBB sem o prefixo do wrapper — H2-D14). Gabaritos: 6 chamadas reais que faltavam (gotify,
  kratos), recategorização dos que mudaram de causa, amostras sincronizadas e julgadas de novo. Por linguagem
  (gabarito): chamadas C# P 62 → 84 %, R 48 → 64 %; chamadas Go R 24 → 32 %; chamadas TS/JS R 22 → 31 %; rotas
  Python P 27 → 38 %. Decisões H2-D9 e H2-D10 aceitas (itens 6 e 7 da Fase 4). Item novo no ROADMAP: **F1.13**
  (repos grandes). Nova baseline `2026-10-15-v2-baseline-2`.
- **2026-10-15** — H2b, Fase 4 item 2, etapa 1 (dentro do arquivo). `prefix_for` (região de closure via o gancho
  `region_of` de cada linguagem, senão o grupo), routers identificados por (escopo que liga o nome, nome), arestas de
  montagem do arquivo e `finish()` no fim de cada arquivo (cadeias de montagem; a raiz de sub-router fica pendente
  — `MountedRoot` — e só vira rota se montada). Diff julgado contra `2026-10-15-v2-baseline-2`: chi, fastify, Hono e
  NodeBB certos (ou só sem prefixo de outro arquivo); Ghost ganha o prefixo dos sub-routers do arquivo; gitea
  −440 +970, com as rotas web completas (o router web é montado em `/`) e, na API, 247 de 282 batendo com a spec se
  somado o `/api/v1` que vem de `routers/init.go` — 231 itens do gabarito passam de `prefix-scope-and-file` a
  `prefix-other-file`; a precisão Go contra os gabaritos cai de 21,1 % para 18,4 % só por isso (H2-D14). Achado no
  caminho: `r.With(mw).Get(...)` é registro no próprio `r`. Julgamento do v1 corrigido: chi `router-walk` `PUT /ping`
  estava certo. Nova baseline `2026-10-15-v2-baseline-3`.

- **2026-10-15** — H2b, reciclagem antes da etapa 2 do item 2 (sem mudança de comportamento). O `http_base.py`
  (800 → 392 linhas) foi dividido: `http_scope.py` (`Scopes`: ligação de um nome do escopo mais interno para fora, sem
  entrar em outras funções, com cache de `binding_scope`), `http_expr.py` (`PathExpressions`: `path_of` despachando
  por tipo de nó), `http_mounts.py` (`MountGraph`: arestas, rotas por router, `prefixes` e `apply`) e
  `http_nodes.py` (os tipos de nó comuns). Os scanners passaram a usar `callee_of`/`split_callee` e
  `add_endpoint(..., router=...)`, que acha o prefixo e registra a rota no grafo sozinho. `pytest` 164 passed,
  corpus idêntico a `2026-10-15-v2-baseline-3` nos 39 repos (ids, handlers e callers); a saída do corpus agora
  mostra o tempo do HTTP por repo (`(http Xs)`). Prioridade do portfólio registrada como H2-D18 (.NET > Go/Python >
  TS), com a ordem da Fase 4 proposta em "Próximo passo". Dívidas adiadas na Fase 5. A baseline não muda.
- **2026-10-15** — H2b, Fase 4 item 6 (C#), primeiro sob o H2-D18. Primeiro passo entre arquivos: cada arquivo
  publica fatos (`out.publish`) e deixa rotas `Pending`; `BaseScanner.compose` roda uma vez por linguagem depois do
  scan, sem árvores (F1.13). `[Route]` da classe base, um nível, achada pelo nome (nome ambíguo não herda; ação sem
  template só com o prefixo herdado); FastEndpoints (`Configure()`) e Ardalis.ApiEndpoints. Constante de classe
  também por `Classe.NOME`, nome com dois valores na pasta só vale no próprio arquivo (o ardalis tem um `Route` em
  cada request). No julgamento: `nameof(X)` em interpolação, e as chaves da interpolação do C# (nós nomeados)
  impediam a regra da variável local interpolada. Tentado e revertido: `[controller]` na caixa declarada — o teste
  de ponta a ponta do .NET quebra porque o linker compara exato (pendência F0.5). Diff contra `-3`: só jellyfin
  (−128 +162), ardalis (+19) e eshop-on-web (+1), todos certos; nenhuma chamada muda. Rotas C# nos gabaritos:
  P 94,6 → 100 %, R 72,9 → 93,1 %; jellyfin P/R 33/25 → 100/100 %. Python do portfólio = FastAPI/Flask (H2-D18).
  Nova baseline `2026-10-15-v2-baseline-4`.
- **2026-10-15** — H2b, Fase 4 item 5, parte C# (H2-D18). Constante interpolada vale como segmentos inteiros: a de
  path no começo do template (`$"{remoteServiceBaseUrl}items/{id}"`), a de uma palavra entre barras
  (`` `/${resource}/${id}` ``, guardada à parte para nunca virar path sozinha) — e nunca num wrapper genérico, um
  template com variável de nome de path (a primeira versão fez lixo do `${GHOST_URL}/ghost/api/admin/${endpoint}`
  do ghost, pego no diff). Chamada interpolada que já é path (`CombineUri`, família do `Path.Combine`; base
  desconhecida sai do join). Wrappers de cliente do app: o método que monta o path em volta de um parâmetro publica
  `Classe.Método` (e sob as interfaces); a chamada num receiver de tipo declarado conhecido fica `Pending` e
  `compose` monta o path — primeiro uso do passo entre arquivos para chamadas. Custo: a primeira medida mostrou o
  netbox em 445 s de HTTP; `Scopes` passou a indexar as atribuições uma vez por escopo e o alias do aiohttp só é
  procurado onde existe — saída idêntica, HTTP do corpus 672 → 98 s, execução 23 → 13 min. Diff julgado (8 repos,
  tudo certo): dispatch +273, eshop, eshop-on-web (+6 pelo `HttpService`), eshop-support, mattermost, zulip,
  argo-cd, ghost. Chamadas C#: P 84 → 100 %, R 64 → 97 %; TS/JS: P 44 → 60 %, R 31,5 → 45 %. Achado fora do HTTP:
  `obj.Method<T>()` não é call site no C#. Nova baseline `2026-10-15-v2-baseline-5`.
- **2026-10-16** — Fora do HTTP, achado no item 5: chamada genérica com receiver no C# vira call site, e o resolver
  deixa de chutar homônimo quando o tipo do receiver é de pacote (só extensão do repo que estenda o tipo e caiba nos
  argumentos). Medido no grafo dos 4 repos .NET do corpus: bitwarden −5.684 +12.244 arestas, jellyfin −1.459 +367;
  o que sai é chute, o que entra é `receiver-type` e extensões do repo. Detalhe no log do ROADMAP.
- **2026-10-16** — H2b, Fase 4 item 7, parte NSwag (o último do .NET, H2-D18). O corpus não tinha cliente NSwag
  (a nota que dava NSwag no v1 estava errada: os do v1 são openapi-ts e go-swagger, e o do clean-arch-dotnet é
  gitignored); entraram 3 apps .NET fixados por SHA (42 repos): RapidBlazor (v13), azure-saas (v14) e notifo (SDK
  .NET v14 + cliente TS do front). Reconhecedor C# pelo cabeçalho do arquivo (`.g.cs` do NSwag deixa de ser
  excluído na descoberta); no TS, `path_of` memoizado com profundidade 64 e verbo pela variável de opções. Os
  clientes mostraram a caixa que o ASP.NET publica (`/api/TodoItems`): `[controller]`/`[action]` voltam à caixa
  declarada e o linker casa rotas `aspnet`/`aspnet-minimal`/`fastendpoints` sem caixa (F0.5, ROADMAP); `[area]` e os
  parâmetros reservados `{area}`/`{controller}`/`{action}`; actions de base abstrata servidas por cada derivado
  (notifo 75 → 102 de 102). Diff contra `-5`: jellyfin, eShopOnWeb e bitwarden só na caixa (mesmo método,
  evidência e path em minúsculas), nenhuma chamada, nenhum repo TS; gabaritos reescritos na caixa declarada.
  Gabaritos novos pelas operações dos clientes + rotas escondidas por `IgnoreApi` lidas no código (H2-D15): 100/100
  em rotas e chamadas nos três. C# (10 repos): rotas P 100 %, R 93,1 → 96,9 %; chamadas P 100 %, R 96,6 → 99,0 %.
  Nova baseline `2026-10-16-v2-baseline-6`.
- **2026-10-16** — H2b, Fase 4 item 2, etapa 2 (Go e Python, H2-D18). O grafo de montagem atravessa arquivos: um
  router que outro arquivo pode nomear tem id global — variável de módulo/pacote (`var:`), o router que uma função
  devolve (`ret:`, método por `Tipo.Metodo`, closure atribuída pelo nome da variável), parâmetro router de função
  (`param:`) ou campo de struct (`field:`, Go) —; a rota num router desses espera a composição, e cada arquivo
  publica as arestas dos seus routers globais, as montagens de routers de fora e os routers que passa a funções.
  `compose` segue as arestas até o topo; router montado em lugar nenhum mantém as rotas. Imports pelo `RepoView`
  (o `resolve_import` de cada linguagem, a dívida da reciclagem), constantes de outro pacote (`model.APIURLSuffix`,
  `settings.API_V1_STR`). No julgamento: o `r` de `r.Route("/x", func(r chi.Router))` é o router de fora; método
  por tipo (dois `Routes` no pacote do chi); `const` Go que nomeia outra e constante anotada em classe Python;
  `Group().Use()` na atribuição; restrição gorilla com chaves aninhadas ou `?` (antes do corte da query);
  alternativas literais num segmento inteiro e `Methods(GET, HEAD)`; raiz de sub-router montada sem prefixo na
  aplicação. Custo: o HTTP do argo-cd subiu 60 % na primeira versão (chave do router de cada argumento de cada
  chamada) — adiado para o fim do arquivo e filtrado por nome; corpus 82 → 88 s de HTTP. Diff contra `-6` (11
  repos, todos Go/Python; nenhum TS/C#) julgado: certo, exceto `pulls/{index}/.{diffType}` do gitea (o padrão
  `.{diffType}` que o gitea junta ao grupo sem barra). Gabaritos: dispatch sob o `/api/v1` do sub-app e com as 85
  rotas que a spec antiga não tem; mattermost e gitea com as rotas só do código (24 e 11) e `web/oauth.go` no
  escopo do mattermost; categorias novas `router-from-registry`, `decorator-call`, `path-prefix-handler`. Rotas Go
  P 18,4 → 98,7 %, R 10,6 → 75,4 %; Python fora do Django P 37,7 → 96,1 %, R 19,3 → 93,4 %. Nova baseline
  `2026-10-16-v2-baseline-7`.
- **2026-10-16** — Item 4 da Fase 4, `route-chain`. `BaseScanner.route_chain` + `member` (`x.f` nas quatro
  linguagens): gitea `m.Combo(path, mw).Get(h).Put(h)` e express `router.route('/x').get(h)` (o `route('/x', sub)`
  do Hono continua montagem); builder do gorilla (`r.Methods("POST").Path("/x").Handler(h)`,
  `r.Path("/x").HandlerFunc(h).Methods("GET")`; `PathPrefix` com verbo é um endpoint — o OAuth metadata do
  mattermost —, sem verbo é árvore ou montagem). No caminho: `http.StripPrefix` monta o router devolvido por outro
  pacote sob o prefixo removido (gateway do go-kit), e o router de outro arquivo entregue a `http.Serve` publica uma
  aresta para `APP` — senão montar o handler do addsvc no gateway tiraria `/sum` e `/concat` do próprio serviço.
  Diff contra `-7` (4 repos, só adições) julgado: gitea +290 (219 `Combo` da API, 71 da UI e dos artifacts, com o
  mesmo prefixo das vizinhas — inclusive o `router-as-param` já julgado no `web.go`), go-kit +11, mattermost +1,
  express-boilerplate +3 (sem o `/v1/users` de outro arquivo: as 5 esperadas passaram de `route-chain` para
  `prefix-other-file`). `route-chain` sai do ranking. Rotas Go P 98,7 → 98,9 %, R 75,4 → 90,5 % (gitea R 59,1 →
  99,1 %, go-kit 59,3 → 100 %, mattermost 100 %). HTTP do corpus 88 → 88,8 s. Nova baseline
  `2026-10-16-v2-baseline-8`.
- **2026-10-16** — Chamadas Go e clientes gerados Go (itens 5 e 7, fatia Go; H2-D18). `url.URL`: o índice de
  escopos já guardava `u.Path` como nome, então `u.String()`/`u` valem o último `u.Path = e`/`+= e` antes dali
  (`Scopes.binding(ident, name)`), `path.Join(u.Path, ..)` lê o anterior, `u.JoinPath` começa pelo path de `u`,
  `url.Parse(literal)`; com base desconhecida o `+=` relativo ganha a barra. go-kit: `NewClient` (import
  `go-kit/kit/transport/http`), verbo no 1º argumento, path da URL ou do encoder (`go.encoder`, `Pending`,
  `GoScanner.compose`). Gerados: `prepareRequest` em arquivo do OpenAPI Generator e `runtime.ClientOperation` do
  go-swagger; `strings.Replace(s, ..)` é `s`; variável ligada a literal ou `http.MethodX` é verbo. A guarda de
  "router desconhecido" passou a exigir path antes do último argumento (o `notify.Get(ctx, client, u.String())` é
  chamada) — a 1ª rodada mostrou dois FPs que ela escondia: `huma.Get(api, "/books", h)` (rota) e uma query SQL
  do mattermost lida como `"SELECT /..."` (o padrão `"MÉTODO /path"` aceitava qualquer palavra; `strings.Join`
  contava como junção de path) — corrigidos com contraexemplos na fixture. Diff contra `-8` (7 repos, só chamadas,
  só adições) julgado certo: kratos +126 (60 × 2 do cliente gerado, conferidos contra a spec, + 6 OIDC),
  alertmanager +15, go-kit +11, go-feature-flag +3, mattermost +2, argo-cd +1, fiber-recipes +1. Gabaritos:
  kratos com as 60 operações da spec (escopo `pkg/httpclient/`, `pkg/client-go/`), alertmanager com as 9 do
  go-swagger e o rocketchat como `client-in-field`, go-kit com `/uppercase` corrigido para GET e 3 chamadas
  `url-from-helper` que faltavam. Chamadas Go P 100 %, R 10,9 → 93,6 % nos mesmos gabaritos; HTTP do corpus
  88,8 → 91,1 s. Nova baseline `2026-10-16-v2-baseline-9`.
- **2026-10-16** — Servidores gerados Go (`generated-server`, 115 das 146 rotas Go que faltavam). grpc-gateway:
  `Handle(verbo, path, h)` com o verbo primeiro é rota; `path_of` decodifica `runtime.MustPattern(runtime.NewPattern(
  1, ops, pool, verb))` (programa de pilha: literal, segmento, captura, `**`, concatenação, verbo); variável de pacote
  construída por chamada vale como último recurso de um nome; handler = método gRPC (`AccountService.CanI`);
  `{name}:cancel` fica literal no `normalize_path`. go-swagger: `o.handlers["GET"]["/x"] = ..` em `restapi/operations`
  espera o `basePath` que o `embedded_spec.go` do pacote pai publica. Diff contra `-9` (2 repos, só adições) julgado
  certo: argo-cd +106 (a `/api/v1` inteira da swagger), alertmanager +9. Gabaritos: argo-cd com `pkg/apiclient/` no
  escopo e as rotas escritas à mão `/auth/login`, `/auth/callback` e `/api/webhook` (as duas últimas
  `multi-app-repo`: outro app do repo registra antes). Rotas Go P 98,9 → 99,1 %, R 90,5 → 97,8 %. O HTTP do corpus
  subiu para 111,7 s nesta rodada, mas todos os repos (TS, Python e C# inclusive) e o parse subiram 20–25 %:
  rodando ghost, netbox e gitea de novo com o código de antes e de depois, os tempos ficaram iguais — carga da
  máquina, não regressão. Nova baseline `2026-10-16-v2-baseline-10`.
- **2026-10-16** — flask-restx e decorador aplicado à mão (Python fora do Django, H2-D18). `Namespace`/`Api` de
  `flask_restx`/`flask_restplus`/`flask_restful` são routers (`path=` do namespace, `prefix=` do `Api`); o `Api` é
  montado no blueprint ou app com que é construído; `add_namespace(ns, path)` é montagem, também de namespace de
  outro arquivo; `@ns.route` numa classe `Resource` dá uma rota por método HTTP definido (`Classe.metodo`). O
  `register_user = router.post("/register")(register_user)` do dispatch é rota de `register_user`. Diff contra
  `-10` (2 repos) julgado certo: CTFd troca 40 rotas `GET` sem prefixo por 155 sob `/api/v1/<namespace>` (a contagem
  de um `ast` sobre `CTFd/api`: 155 em 90 classes) e 4 rotas de blueprint voltam (uma rota restx de mesmo id as
  escondia); dispatch +1. Gabaritos: categorias `restx-resource` (17) e `decorator-call` (1) removidas, 7 amostras
  do CTFd julgadas de novo (certas). Rotas Python fora do Django P 96,1 → 99,0 %, R 93,4 → 98,0 %. HTTP do corpus
  111,7 → 113,8 s; o mattermost levou 1369 s nesta rodada (HTTP igual), mas sozinho, logo depois e com o
  mesmo código, 249,6 s — máquina, não regressão. Nova baseline `2026-10-16-v2-baseline-11`.
- **2026-10-16** — TS no H2 (H2-D19), etapa 1: grafo de montagem entre arquivos em TS/JS. Imports ESM e CommonJS
  (`require`, `require('x').y`, desestruturação); router de módulo `var:`, devolvido `ret:`, parâmetro `param:`, função
  exportada por `module.exports =`/`export default` chamada `default`; export com outro nome e reexportação viram
  arestas sem prefixo; filho de montagem importado, `require('./x')` no lugar, `routes()` ou `m.router`;
  `require('./legacy')(app)`; `use` sem path; cadeia que começa num construtor pertence ao nome a que é ligada
  (`export const TodoAPI = new Hono().get(..)`, `export default Router().use('/api', api)`); genérico no construtor;
  wrapper de montagem do projeto (`app.lazyUse = function (path, fn) { app.use(path, .. fn() ..) }`: fato
  `ts.mount-wrapper`, chamadas candidatas `ts.mount.maybe`, `TsScanner.compose`); aplicação nomeável publicada
  (`<regra>.app`, `compose` mantém a raiz numa aplicação que ninguém monta — vale para Go e Python também, sem
  diferença no corpus). Diff contra `-11` (5 repos, todos TS) julgado certo: ghost (Admin e Content API sob
  `/ghost/api/*`, members, comments, gift, webmentions; a Content API sobe de 4 para 20 porque o dedupe juntava os ids
  sem prefixo), express-realworld (19 sob `/api`), express (`multi-router`), hono-examples (stytch sob `/api`, o `api`
  do blog é router) e nodebb (+2: a raiz do instalador web). Gabaritos: ghost +13 rotas de dois sub-routers que a
  regex do gabarito não via (`appsRouter`, `metafieldsRouter`); categorias encontradas removidas; 42 amostras julgadas
  de novo (certas). Rotas TS/JS P 5,9 → 50,4 %, R 3,7 → 32,9 %. HTTP do corpus 113,8 → 105,0 s; o bitwarden levou
  813 s nesta rodada e 129,8 s sozinho logo depois — de novo um repo grande lento fora do HTTP numa rodada completa
  (antes o mattermost), provável pressão de memória na VM do Docker. Nova baseline `2026-10-16-v2-baseline-12`.
- **2026-10-16** — TS, etapa 2: o Nest. `app.setGlobalPrefix('api', { exclude })` vale para os controllers do pacote
  (módulo do `package.json` mais próximo) — fato `ts.nest-prefix`, rotas Nest como `Pending` `ts.nest`, aplicado no
  `TsScanner.compose` quando o pacote tem um prefixo só; `exclude` com strings, `{ path }` e curingas, também de uma
  lista exportada por outro arquivo (`ts.string-array`). Argumento de decorator Nest pela árvore: array (uma rota por
  path), objeto (`path`), constante ou membro de enum (`Enum.Membro`, coletado pelo `collect_constants`; o
  `foreign_const` procura o nome qualificado e aceita uma palavra); comentário entre decorator e método não esconde o
  handler. No caminho, fora do HTTP: o resolvedor de imports TS tenta o `.ts` de um especificador `.js` (ESM com
  `nodenext`) e os aliases a partir do pacote do arquivo — +9845 arestas `IMPORTS` em immich, nest, ghost e
  fastify-demo, todas conferidas contra o especificador, nenhuma perdida (ROADMAP, log de 2026-10-16). Diff contra
  `-12` (immich e nest) julgado certo: immich 246 rotas sob `/api` e 44 também com o prefixo do enum, as 2 excluídas
  fora; nest, a raiz do `24-serve-static` sob `/api` e os prefixos-objeto dos apps de teste. Gabaritos: immich +16
  rotas reais fora da spec (H2-D15: 14 `PATCH` com `@ApiExcludeEndpoint()` e as 2 excluídas do prefixo), 20 amostras
  julgadas de novo (certas); `global-prefix` e `const-other-file` saem do ranking. Rotas TS/JS P 50,7 → 93,9 %,
  R 32,6 → 60,7 %. HTTP do corpus 105,0 → 131,1 s, com todos os repos 20–35 % mais lentos, Go inclusive — carga da
  máquina. Nova baseline `2026-10-16-v2-baseline-13`.
- **2026-10-17** — TS, registrars próprios (decisão do usuário: seguir a recomendação para o NodeBB). Wrapper de rota:
  função com nome que registra num parâmetro router com o path vindo de um parâmetro (também em template,
  `` `/api${name}` ``; rest desestruturado `const [router, verb, name] = args`; `router[verb](..)`) publica suas formas
  (`ts.route-wrapper`); chamada com path e router entre os argumentos é candidata (`ts.route.maybe`, com o handler do
  último argumento e para onde o router leva), materializada no `compose` antes do grafo de montagem; os registros do
  corpo ficam como rotas (`ts.wrapped`) até o wrapper ser usado. Achados nas três rodadas: a candidata engolia
  `http.del(url, null, params)` do k6 (bitwarden: agora nunca interrompe a leitura da chamada); `apiRoutes(router,
  name)` e `_mounts.post = (app, name) => ..` sumiam (agora o registro só cai quando o wrapper é usado); e chamada com
  prefixo só conhecido em runtime (`` `/${name}/settings` ``, os mounts remontáveis do NodeBB) gerava `/{param}/..`,
  que o linker não liga (compara segmentos literais) — não vira rota. No caminho: router de módulo devolvido pela
  função exportada (`var:` → `ret:`) e parâmetro opcional do Express no fim (`/reset/:code?` → também `/reset`; a
  fixture `app.ts` passa a esperar as duas formas). Diff contra `-13` (só o NodeBB) julgado certo: 92 → 377 rotas
  (API de escrita sob `/api/v3/*`, páginas e gêmeos `/api`, formas curtas), sai o template `GET /api{param}`.
  Gabarito do NodeBB: escopo com `index.js`, `user.js`, `activitypub.js`; +62 rotas reais fora das specs (H2-D15);
  `POST /api/email/unsubscribe/{token}` só na spec, removida; os bloqueados por prefixo de runtime passam a
  `prefix-as-param` (119). Rotas TS/JS P 94,0 → 95,5 %, R 59,7 → 85,3 % (NodeBB P 66,7 → 93,9 %, R 8,7 → 73,1 %).
  HTTP do corpus 105,2 s. Nova baseline `2026-10-16-v2-baseline-14`.
- **2026-10-17** — Clientes gerados TS e requisição descrita por objeto (item 7 fechado; `request-config-object` do
  item 5). Objeto com `url` que guarda um path, num método de verbo ou em `request`/`ajax`/`axios`, é a requisição
  qualquer que seja o receptor (verbo do nome, senão `method`/`type` do próprio objeto, senão GET); oazapfts em arquivo
  com o cabeçalho do gerador (`generated-client`, path sem a query, sob o `baseUrl` literal). Diff contra `-14` (7 repos,
  só chamadas, só adições) julgado certo: immich +279, fastapi-template +23, zulip +124 (`channel.*({ url })`), ctfd +5,
  NodeBB +6, gotify +2, mattermost +10 (em `e2e-tests/`, que a baseline já conta). Gabaritos: chamadas do immich (279
  da spec sob `/api`, escopo `packages/sdk/`) e do fastapi-template (as 23 rotas, escopo `frontend/src/client/`,
  linguagem TS/JS pelo H2-D17); os 9 `request-config-object` encontrados. Chamadas TS/JS P 59,5 → 91,4 %, R 12,1 →
  87,4 %. HTTP do corpus 106,9 s. Nova baseline `2026-10-17-v2-baseline-15`. O TS fecha no essencial; próximo, a Fase 5.
- 2026-10-17: **Fase 5, menos o *hold-out*.** Últimos defeitos baratos do ranking final, um fixture cada (e cada um
  falhando sem a regra): `Client()` de teste do Django numa view de desenvolvimento (zulip −9 chamadas erradas),
  `urljoin` com path absoluto (zilencer: `GET /api/v1/zulip-services/verify/{param}`), path de URL validado como path
  de rota (`is_url_literal`, a pendência do `URL_LITERAL`), restrição de regex do Hono (`GET /post/{id}`), pastas de
  teste por nome (`e2e-tests/`, `cypress/`, `playwright/`, `testhelpers/`: mattermost −33 rotas e −31 chamadas do e2e,
  kratos −5 rotas e −6 chamadas, fastapi −7 chamadas dos scripts Playwright; nenhuma num gabarito) e, exposto por
  ela, `Sprintf` com constante de segmento (kratos `GET /schemas`, `/schemas/{id}`, na spec). Diff julgado item a
  item em duas rodadas; nenhum repo regride; rotas Go R 97,8 → 98,0 %, chamadas Python P amostrada 69,7 → 100 %.
  HTTP do corpus 105,2 s. Nova baseline `2026-10-17-v2-baseline-16`. Guia §3 (composição com o TS, regras novas,
  limitações por destino) e §5 (o ciclo de uma mudança); relatório com "Closing H2b": do primeiro v2 ao último, nos
  mesmos gabaritos e 38 repos, rotas C# R 55,6 → 93,1 %, Go 9,4 → 98,0 %, Python fora do Django 9,1 → 98,0 %, TS/JS
  4,3 → 85,4 %; chamadas C# 48,3 → 96,6 %, Go 8,2 → 93,6 %, TS/JS 6,1 → 87,4 %; e o destino de cada lacuna.
  ROADMAP: **F1.14** (o que o H2 deixou para o extrator, na ordem do portfólio, com as dívidas da reciclagem), custo
  do HTTP no netbox no F1.13. Falta o *hold-out*; depois, F0.4.3b `[x]`.
- 2026-10-17: **Hold-out e fechamento do H2.** 16 repos fora do ajuste (H2-D20; os 10 da lista do autor filtrada e os 6 da
  primeira recomendação, a pedido), fixados em `HOLDOUT` (`http_corpus.py --holdout`). Gabaritos escritos antes de rodar:
  9 da spec commitada conferida com o código (photoprism e memos corrigidos pela leitura; Umbraco com as 15 rotas que a
  spec esconde), 7 lidos no código num escopo fixado antes; `scope_paths` novo no `corpus_metrics` para spec que cobre um
  subespaço de URL (teste novo). Uma rodada (o Umbraco, 17 mil arquivos, à parte: 112 s, sem estourar a memória), amostra
  semeada de 20 rotas e 20 chamadas por repo julgada na fonte, faltas categorizadas; correções de gabarito pelo H2-D15
  (btcpayserver +42 rotas reais e −10 só da spec, directus +8, Radarr +1). Resultado: recall de rotas C# 48,5 %, Go 19,7 %,
  Python 83,8 %, TS/JS 74,1 %; chamadas TS/JS 76,5 % — contra 96,9 / 98,0 / 98,0 (sem Django) / 85,4 % no corpus. Valem as
  regras onde o app roteia como o corpus (Kavita, sftpgo, open-webui, docmost, btcpayserver inteiros; SDK hey-api do Umbraco
  513/513); caem atributo de rota próprio (760), OData (260), prefixo duplicado num grupo Go passado a função (172, defeito),
  router de pacote atribuído em outro arquivo (165), gateway com verbo em constante e Connect (185), FastEndpoints atrás de
  base própria (94), Koa sem barra (64), subclasse de `APIRouter` (28) e a base do cliente em outro arquivo/alias/campo
  (158 chamadas). Tudo no F1.14. ROADMAP: F0.4.3b `[x]`. **H2 concluído.**
- **2026-10-18** — O F1.14 seguiu nesta branch (incrementos 1–5, no ROADMAP): as formas que o hold-out mostrou em .NET,
  Go, Python e TS/JS. 13 repos do hold-out viraram corpus (55); o hold-out fica com 3 (go-boilerplate, Kavita, sftpgo).
  PR da `feature/h2-corpus`; o fechamento do F1.14 (itens 1–5 e 7, um hold-out novo) segue numa branch nova.
- **2026-10-18** — **F1.14 fechado na `feature/f114-close`, e com ele o H2.**
  - **O que entrou:** os incrementos 6 a 11:
    - os grupos do FastEndpoints e o verbo customizado do gRPC;
    - o Go dos routers por tipo declarado e das closures com nome;
    - o prefixo próprio de um grupo global;
    - um endpoint por app num monorepo;
    - os wrappers de cliente em Python e em TS/JS;
    - as listas de routers montadas em laço;
    - o `@fastify/autoload` e as rotas do Next.js.
  - **Ferramenta:** o corpus roda em paralelo (`corpus.sh`, 461 s contra ~21 min em série).
  - **Baseline final:** `2026-10-18-v2-baseline-28`, depois do incremento 12.
  - **O hold-out novo vai para depois do H5 (H2-D21).**
  - **Docs:**
    - ROADMAP: F0.4.3 e F1.14 `[x]`;
    - relatório: "Closing F1.14 and H2";
    - aqui: o resumo final no topo.
- **2026-10-19** — **F1.14 incremento 12, achado na validação do PR #5 antes do merge.**
  - **O achado:** numa instalação ao vivo, dois defeitos dos wrappers TS do incremento 11:
    - as opções do `fetch` num local caíam no GET padrão;
    - a query entre parênteses virava `{param}` no formato do wrapper.
  - **Corrigido**, com caso de fixture:
    - no app, as chamadas certas passaram de 17 para 51 das 51;
    - no corpus, o mattermost ganha 8 POST e um ANY.
  - **Baseline:** `2026-10-18-v2-baseline-28`.
