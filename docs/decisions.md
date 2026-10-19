# Decisões

> As decisões em vigor que não viraram ADR, com o contexto, a escolha e o porquê. Os ADRs ficam em `docs/adr/`:
> ADR-002 (tree-sitter como base, SCIP como enriquecimento) e ADR-003 (núcleo + módulos por linguagem). As decisões
> **pendentes** estão no ROADMAP ("Decisões pendentes"). Os marcos de quando cada uma foi tomada estão em
> `docs/history.md`, e o texto original fica no git.

## Stack (D1–D17)

| # | Decisão | Porquê |
|---|---|---|
| D1 | Banco do grafo: **Neo4j Community**. A alternativa era Memgraph. | MCP oficial, memória e licença para uso interno. Esquema v1 em `neo4j/SCHEMA.md`. |
| D3 | Refs: `always` do tenant = `[main, master]`. Feature branches entram pela política `active` (≤ 14 dias, ≤ 5 por repo, efêmeras, GC em 30 dias) e por `refs.overrides`. | A organização não usa `develop`, que fica no default do código por compatibilidade (2026-10-03, F0.3.6). |
| D6 | Nome **Atlas**, para o database Neo4j e para o MCP voltado a agentes (`atlas.*` nas skills). `neo4j/` segue como pasta de infra. | Ferramentas de intenção substituem o Cypher bruto (F0.6). |
| D7 | Sem default de tenant: `AIDD_TENANT` vem do `install.sh` (`.env`), é `${AIDD_TENANT:?}` no compose e é obrigatório no indexador. Um `auto` que não deriva tenant é erro. | Um tenant errado mistura grafos de clientes. |
| D8 | Providers: **GitHub primeiro** (F1). O manifesto já aceita N fontes por tenant. | Cada tenant combina providers sem mudar o formato. |
| D9 | Fonte `local` lida por `git archive` das refs; revisto pelo D15: também com espelho, para o workspace ficar só leitura. | Ler sem tocar no checkout do dev. |
| D10 | Política de refs por default: `main`, `master` e `develop` sempre; ativas ≤ 14 dias, ≤ 5 por repo; GC das efêmeras em 30 dias. | Limita o custo de indexação por repo. |
| D11 | Áreas: seção opcional `areas:` no `atlas.yaml` (`Repo.area`, agrupa o `plan`). Nós de domínio e Backstage/Compass ficam para a F2. | Agrupar sem um modelo de domínio prematuro. |
| D12 | Instalação ≠ atualização. O bootstrap indexa as refs locais como clonadas (sem fetch, sem credencial); manter o atlas atualizado é um processo próprio. | A instalação não pode depender de credencial nem de rede. |
| D13 | Refresh automático com PAT somente leitura dedicado, nunca a chave pessoal; intervalo de 15 min. O agendador do D13 e do D14 foi trocado pelo D15. | Credencial de serviço revogável e mínima. |
| D15 | O refresher é um serviço do compose (`aidd daemon`) com espelhos bare em `~/.aidd/mirrors`. O workspace é montado só leitura, e os containers rodam como o usuário do host. Substitui o D14 (systemd no WSL) e o fetch no host do D12. | Funciona igual em macOS, Linux e WSL, e o Docker o reinicia. |
| D16 | Conhecimento é mecanismo da stack, não skill: um serviço MCP (`knowledge`) que todas as etapas consomem. Quem decide o que registrar é o modelo da etapa; quem grava é o serviço. SARIF e Sonar entram por `aidd ingest`. | As skills espelham as etapas e ficam poucas. Hook roda shell e não distingue padrão de ruído. O atlas segue só leitura. |
| D17 | A política do processo fica em `policy.yaml` (cobertura, harness, review, conhecimento), separada do `atlas.yaml`, que diz como ler o código. Tem as mesmas camadas (defaults → tenant → área → repo), e as skills leem a política efetiva por `policy_for`. | `profile` já são os profiles do compose; as skills nunca fazem o merge. |

## H2: corpus público e precisão do extrator HTTP (H2-D1–D21)

| # | Decisão | Porquê |
|---|---|---|
| H2-D1 | O H2 tem dois incrementos: o H2a (instrumento e relatório v1 com 15 repos) e o H2b (~40 repos e evolução do extrator). | Validar o instrumento num conjunto pequeno antes de ampliar. |
| H2-D2 | Cada repo do corpus é fixado por SHA, não pelo HEAD. | Com o HEAD, a baseline muda sozinha e o diff deixa de significar algo. |
| H2-D3 | Clones e saídas ficam fora do repo, em `~/.cache/aidd-corpus/{repos,runs/<data>-<rótulo>}`. | `/tmp` some no reboot, e o corpus não é versionado. |
| H2-D4 | Gabarito só vem de spec commitada, de dump de rotas publicado ou de leitura do código. Os apps nunca rodam. | Rodar o app executa código de terceiros. |
| H2-D5 | Rotas e chamadas têm métricas separadas. O recall de chamadas conta só as que têm path literal ou template. | Os perfis de erro diferem; URL montada em runtime não é falha do extrator. |
| H2-D6 | A precisão sorteia do extraído; o recall sorteia da fonte. | Sortear só do extraído nunca mostra falso negativo. |
| H2-D7 | tRPC fica fora de escopo. | São procedures, não rotas REST. |
| H2-D8 | Java/Kotlin ficam fora. | Não são linguagem parseável do indexador. |
| H2-D9 | Clientes gerados (NSwag, openapi-generator, oazapfts, ..) são extraídos como `HttpCall` com `via: generated-client`, um reconhecedor por gerador. | No v2 eram 371 operações sem nenhuma extraída. Cada gerador escreve sempre a mesma forma, então o risco de FP é baixo. |
| H2-D10 | `[Route]` herdado no ASP.NET segue a herança; um nome de base ambíguo não herda. Era um nível e passou a quatro no F1.14. | 128 rotas do jellyfin sem prefixo; depois, o Radarr. |
| H2-D11 | **Precisão antes de recall:** regra que sobe o recall e derruba a precisão em algum repo não entra. | Um FP vira aresta errada no grafo depois do linker. |
| H2-D12 | Rota ou chamada com prefixo que o código tem e se perdeu conta como erro. Prefixo de config ou env (`BaseAddress`, `*_URL`) não conta, porque é do linker. | O path é a chave do linker. |
| H2-D13 | Medir o que o grafo recebe (depois do `_dedupe`), sem contornar a fusão de rotas iguais entre apps. | A fusão era um defeito real (`multi-app-repo`, resolvido no F1.14 item 5). |
| H2-D14 | O H2-D11 julga o erro que a regra introduz. Item novo errado só por herdar um defeito já categorizado conta, mas não bloqueia a regra. | Recusar a regra deixaria de fora os itens certos, e o defeito herdado é de outra regra. |
| H2-D15 | Gabarito com spec é a spec mais as rotas conferidas no código: rota que só existe na spec sai, e rota real fora da spec entra. | A spec documenta a API pública, não tudo o que o código serve. |
| H2-D16 | Item que pede mais de uma correção recebe uma categoria só: a mais específica além do grafo de montagem. | O ranking diz qual regra destrava o quê. |
| H2-D17 | O item conta na linguagem do seu arquivo. O gabarito declara `language` por tipo quando difere da do repo, e cada categoria traz o nº de repos. | Repos mistos misturavam linguagens, e um repo grande não ranqueia uma categoria sozinho. |
| H2-D18 | **Prioridade do portfólio:** .NET primeiro, Go e Python (FastAPI/Flask) em segundo, TS em terceiro. Django fica adiado. | O corpus pesa pelo volume dos repos públicos, não pelo que os projetos reais usam. |
| H2-D19 | O TS entra no H2 depois de .NET, Go e Python fechados no essencial, em etapas com corpus e commit cada uma. | Reaproveita o grafo de montagem e o `compose` que Go e Python já usam. |
| H2-D20 | **Hold-out:** repos que as regras nunca viram, no perfil do portfólio. O gabarito é escrito antes de rodar, a amostra é semeada e julgada na fonte, e ele é medido uma vez, sem ajuste. Repo do hold-out que é trabalhado vira corpus. | Um hold-out que orienta regras vira corpus. Os 16 de 2026-10-17 mostraram sobreajuste (C# R 48,5 %, Go 19,7 %). |
| H2-D21 | O hold-out novo do fechamento do F1.14 vai para depois do H5, como primeiro passo de um handoff próprio, medido também no commit de antes do H5. | O H5 não muda comportamento; o que ele mostrar se corrige no código refatorado; a diferença entre os dois commits é regressão do H5. Custo aceito: um defeito de precisão não visto fica na instalação durante o H5. |

## H4: docs públicos e o indexador em repo próprio (H4-D1–D12)

São **propostas**: o H4 confirma com o autor antes de executar. O H4-D6 é do autor.

| # | Proposta | Porquê |
|---|---|---|
| H4-D1 | A fonte dos docs públicos é em inglês, e as outras línguas são traduções; isso fecha o D5. ROADMAP, handoffs e guias de trabalho seguem em português, fora da navegação pública. | É o padrão do open source e do projeto (esquema e ADRs em inglês). |
| H4-D2 | Locales `pt-BR`, `es` (neutro) e `zh-CN`, com etiquetas BCP 47 nos arquivos. | `pt` e `zh` sozinhos são ambíguos. |
| H4-D3 | Tradução em camadas: 1 (READMEs, instalação, visão geral, FAQ) nos quatro idiomas; 2 (guias) em inglês e pt-BR; 3 (referência, contratos, esquema, ADRs, relatório do corpus, CHANGELOG) só em inglês. | A referência muda a cada commit e é a tradução que envelhece primeiro. |
| H4-D4 | Markdown no GitHub com `docs/<locale>/`. O site só quando a navegação pedir. | O GitHub já renderiza Mermaid e `<picture>`. |
| H4-D5 | Tradução assistida por LLM com glossário e guia de estilo, e revisão nativa quando houver. Nada de Crowdin/Weblate por ora. | Poucas páginas por camada, e não há tradutor externo. |
| H4-D6 | O nome do repo do indexador é **do autor**. A sugestão é um nome próprio, com `atlas` mantido como nome do MCP, sem renomear comandos no primeiro corte. | "Atlas" colide com `ariga/atlas` e com o MongoDB Atlas. |
| H4-D7 | O `knowledge` fica no aidd-stack como pacote próprio. O que ele importa do indexador vira API pública declarada e versionada. | Vault, insights e política são a metodologia, não indexação (D16, D17). |
| H4-D8 | O `dotnet-praticis` fica com o indexador no primeiro corte, como extensão de referência. | 5 módulos de teste e as fixtures `csharp-praticis-*` dependem dele. |
| H4-D9 | `git filter-repo` leva o histórico do indexador para o repo novo, com varredura de nomes e segredos antes do primeiro push. | `blame` e log guardam o porquê das regras, e o repo novo é a chance de não republicar o que não devia. |
| H4-D10 | Imagem no GHCR, multi-arquitetura (amd64 e arm64), por tag. O aidd-stack fixa tag e digest. | O `install.sh` não deve buildar código de outro repo. |
| H4-D11 | `SCHEMA.md` e `schema.cypher` vão para o indexador, que aplica o esquema. | O esquema bate sempre com a versão de quem escreve. |
| H4-D12 | SemVer, `CHANGELOG.md` no formato Keep a Changelog, e o README apontando para uma release. | Hoje o `curl \| bash` recebe qualquer commit da `main`. |

## H5: refatoração do indexador antes do SCIP (H5-D1–D5, decididas pelo autor em 2026-10-18)

| # | Decisão | Porquê |
|---|---|---|
| H5-D1 | **A ordem:** fim do F1.14 → fase 0a do H4 → H5 → hold-out novo (H2-D21) → P2 → SCIP (F1.1, F1.2). O H5 absorve o catálogo e os limiares do `built_bundle` (dívidas do item 7 do F1.14). | O SCIP precisa de um lugar só para plugar (um serviço de tipos), e o extrator cresceu em métodos-deus e dois sistemas de tipo paralelos. |
| H5-D2 | O catálogo de frameworks é YAML, com esquema validado e teste. | É o mesmo formato das convenções. |
| H5-D3 | As metas são complexidade ≤ 9 e módulos ≤ 300 linhas. No H5, o CI só relata; quem liga o bloqueio é o autor. | Código que cabe numa leitura; o bloqueio vem quando o código inteiro cumprir. |
| H5-D4 | Revisão geral dos comentários: fica só o pertinente, sem referência a docs e sem nome de projeto. | Os docs vão ser reorganizados, e o código é público. |
| H5-D5 | O MCP entra no escopo; o `cli.py` fica para o P2. | O P2 vai mexer na CLI ao separar o repo. |

## Do processo de trabalho

| Decisão | Porquê |
|---|---|
| **Sem LLM como parser.** A extração é determinística (tree-sitter); uma lacuna que pede o tipo de uma expressão não declarada à vista vira `needs-resolver` e espera o resolvedor do F1.2. | Reprodutível e medível no corpus; a fronteira com o SCIP está no ADR-002. |
| Toda mudança no extrator segue o ciclo: fixture que falha sem a regra → corpus `--baseline` → julgamento item a item na fonte → gabaritos (H2-D15/D17) → nova baseline. | Regressão num repo enquanto outro melhora é o caso comum. |
| Uma mudança no extrator que vai para o `main` passa por uma validação numa instalação ao vivo antes do merge: dry-run do `main` contra a branch em cada snapshot e fotos do grafo antes e depois da reinstalação. | O PR #5 só mostrou dois defeitos dos wrappers TS no código real, que o corpus não tinha (incremento 12). |
| Nenhum nome real de tenant ou de projeto privado em docs, código, testes ou fixtures; repos públicos podem ser citados. | O repo é público. |
