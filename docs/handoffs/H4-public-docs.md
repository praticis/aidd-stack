# Handoff H4 — Documentação pública: o aidd-stack, o indexador em repo próprio e quatro idiomas

> Cole este arquivo (ou peça para ler `docs/handoffs/H4-public-docs.md`) no início de um chat novo. Antes de qualquer
> coisa, o chat deve ler `docs/ROADMAP.md` ("Onde estamos", "Princípios" e as trilhas), o `README.md` e o
> `indexer/README.md` atuais, os ADRs 002 e 003, `docs/knowledge-contract.md`, `neo4j/SCHEMA.md`, o
> `docker-compose.yml` (serviços), o `setup/install.sh` (etapas) e as skills em `setup/skills/`.
>
> **Estado (2026-10-16):** registrado, não iniciado. Os assets visuais (marca, banner, diagrama de destaque, prévia
> social) são feitos em outro processo; este handoff define onde eles entram e o que os docs pedem a eles. A separação
> do indexador espera o H2b sair da `feature/h2-corpus` (ver "Ordem").

## Contexto em um parágrafo

O `praticis/aidd-stack` é público e o README tem uma linha (o `curl` do instalador). A documentação que existe foi
escrita para quem continua o trabalho, não para quem chega: ROADMAP, handoffs e o guia do indexador em português;
contratos e referência em inglês (`SCHEMA.md`, `knowledge-contract.md`, `corpus-report.md`, `indexer/README.md`).
Duas mudanças pedem documentação de produto: o indexador sai para um repositório próprio, utilizável sem o resto da
stack, e a documentação passa a existir em inglês, português, espanhol e chinês. Este handoff desenha as duas coisas
juntas, porque os docs seguem a fronteira do código: escrever a documentação antes de decidir o que fica em cada repo
seria escrevê-la duas vezes.

## Os nomes que os docs precisam separar

Hoje quem chega encontra cinco coisas sem saber qual é qual:

| Nome | O que é | Onde vive depois do H4 |
|---|---|---|
| a metodologia da Praticis | o processo: `scan` → `refine-business` → `refine-tech` → `implement` → `review`, uma skill por etapa (D16), o conhecimento que as etapas alimentam e consultam, os princípios do ROADMAP. Existem `scan` e `refine-business`; as outras são planejadas (S5–S7) — os docs dizem isso | aidd-stack (explicação) |
| aidd-stack | a suíte que implementa a metodologia num setup pronto: compose (Neo4j, Qdrant, vault Obsidian, gateway, MCPs de git e Obsidian, refresher, `knowledge`), instalador, cliente `aidd`, skills | aidd-stack |
| o indexador (pacote `aidd-indexer`) | o motor do grafo de código: tree-sitter, resolução de chamadas, extrator HTTP, linker, refresher, MCP `atlas` | repo próprio |
| `atlas` | hoje, o nome do database Neo4j e do MCP de leitura (D6) | H4-D6 |
| convenções (`dotnet-praticis`) | extensões que ensinam ao indexador um padrão de arquitetura; a do .NET é o padrão do Praticis SDK | H4-D8 |

A descrição do repo no GitHub cita o Praticis SDK. Os docs dizem qual é a relação (a convenção `dotnet-praticis`
reconhece o padrão do SDK) sem que nada dependa dele para funcionar.

## Objetivo

1. **Fronteira entre os dois repositórios** decidida e executada — código, testes, docs, imagem e histórico —, com o
   aidd-stack consumindo o indexador por versão publicada em vez de `build: ./indexer`.
2. **Arquitetura de informação** dos dois repos: README como porta de entrada e docs organizados pelo tipo de leitura
   (tutorial, guia, referência, explicação).
3. **Idiomas:** inglês como fonte; `pt-BR`, `es` e `zh-CN` como traduções com proveniência, glossário, guia de estilo e
   uma checagem que acusa tradução defasada.
4. **Contrato com o processo de assets:** que imagens os docs usam, em que formato, com que variantes e em que caminho.
5. Arquivos de comunidade (`CONTRIBUTING`, `SECURITY`, `CODE_OF_CONDUCT`, `CHANGELOG`, templates) e metadados do GitHub.
6. **Auditoria antes de publicar:** nomes reais, segredos, números sem fonte, links quebrados.

## O que obter do autor logo no início

- O **nome do repo do indexador** (H4-D6) e, se houver, o nome público da metodologia.
- O **estado do processo de assets**: o que já existe, o que está em produção, quando chega. O manifesto (abaixo)
  começa disso.
- **Revisores por idioma**: pt-BR o autor revisa; es e zh-CN precisam de alguém, ou ficam marcados como tradução por
  máquina.
- O que da **marca Praticis** pode ser reutilizado por terceiros (o código é MIT; a marca, em geral, não).
- Se há documentação pública do **Praticis SDK** para linkar.

## Decisões a tomar no início

As recomendações são o ponto de partida; o chat confirma com o autor antes de executar.

**Documentação e idiomas**

| # | Decisão | Recomendação | Por quê |
|---|---|---|---|
| H4-D1 | Idioma da fonte | Inglês; as outras línguas são traduções dele. Fecha o D5 do ROADMAP. ROADMAP, handoffs e guias de trabalho continuam em português, fora da navegação dos docs públicos e sem tradução | É o padrão do projeto (esquema e ADRs já em inglês) e do open source; traduzir os docs de trabalho custaria mais do que valem para quem chega |
| H4-D2 | Locales | `pt-BR`, `es` (neutro, América Latina), `zh-CN` (simplificado), etiquetas BCP 47 nos nomes de arquivo | `pt` e `zh` sozinhos são ambíguos (pt-PT, zh-TW); fixar agora evita renomear arquivos depois |
| H4-D3 | O que se traduz | Em camadas. **1** (quatro idiomas): READMEs, instalação e primeiros passos, visão geral da metodologia, FAQ. **2** (inglês + pt-BR): guias. **3** (só inglês): referência, contratos, esquema, ADRs, relatório do corpus, CHANGELOG | Referência muda a cada commit e é feita de identificadores: é a tradução que envelhece primeiro. Os guias têm pt-BR porque é a língua do time |
| H4-D4 | Onde os docs vivem | Markdown no próprio GitHub, com a estrutura `docs/<locale>/` pronta para um site estático. O site (GitHub Pages) só quando a navegação pedir — busca, muitas páginas por idioma —, com a ferramenta escolhida nessa hora por critério: i18n por pasta, busca que funcione em chinês, Mermaid, projeto mantido | O GitHub já renderiza Mermaid e `<picture>` claro/escuro; um site é mais infraestrutura e não muda o conteúdo se a estrutura de pastas for a mesma |
| H4-D5 | Como se traduz | Arquivos no repo; tradução assistida por LLM com o glossário e o guia de estilo no contexto; revisão de falante nativo quando houver. Sem Crowdin/Weblate até existirem tradutores externos | Quatro idiomas e poucas páginas por camada; uma plataforma de tradução é processo a mais sem quem a use |

**Fronteira e distribuição**

| # | Decisão | Recomendação | Por quê |
|---|---|---|---|
| H4-D6 | Nome do repo do indexador | **Do autor.** Fatos: o pacote é `aidd-indexer`, a CLI é `aidd`, o MCP e o database são `atlas`. "Atlas" sozinho colide no GitHub com o `ariga/atlas` (esquema de banco como código) e com o MongoDB Atlas — ruim para busca e para entender. Recomendação: um nome próprio para o repo e o produto, `atlas` mantido como nome do MCP dentro da stack, e nenhuma renomeação de comando no primeiro corte | Um repo que vale sozinho precisa de um nome que faça sentido sem o aidd-stack; renomear CLI, imagem e MCP junto com a separação mistura duas mudanças |
| H4-D7 | Onde fica o `knowledge` | No aidd-stack, como pacote próprio, levando `core/policy.py` e os subcomandos `policy` e `knowledge`. Hoje ele importa do indexador `core.config`, `core.manifest`, `core.policy` e `mcp.server.transport_security`; os que ficam no indexador viram **API pública declarada** do pacote (o que o aidd-stack pode importar), versionada | Vault, insights e política do processo são a metodologia, não indexação de código (D16, D17); o indexador sozinho não precisa deles |
| H4-D8 | Onde fica o `dotnet-praticis` | No primeiro corte, **com o indexador**, documentado como extensão de referência: 5 módulos de teste e as fixtures `csharp-praticis-*` dependem dele, e elas são o teste de ponta a ponta mais completo do mecanismo de convenções (papéis, arquiteturas, `dispatch`, DI). Sai para o aidd-stack, ou para repo próprio, quando o ritmo de versões do Praticis SDK se separar do indexador | Move-se o que tem motivo para mover; tirar a convenção agora obriga a escrever uma convenção de teste genérica antes de qualquer documentação |
| H4-D9 | Histórico | `git filter-repo` levando o histórico dos caminhos do indexador (tabela abaixo) para o repo novo, com varredura de nomes reais e segredos **antes** do primeiro push (`--replace-text` se precisar). No aidd-stack, um commit remove os caminhos; o histórico fica | `blame` e log valem muito no indexador (o porquê de cada regra está nos commits); o aidd-stack já é público, e o repo novo é a chance de não republicar o que não devia estar lá |
| H4-D10 | Distribuição | O indexador publica a imagem no GHCR, multi-arquitetura (amd64 e arm64 — há dev em Mac com Apple Silicon), por tag de versão; o aidd-stack fixa a versão (tag + digest, como pede o SO10). A imagem do `knowledge` passa a ser construída no aidd-stack `FROM` a imagem do indexador. Pacote no PyPI só se alguém pedir uso sem Docker | O stack inteiro roda em containers; uma imagem publicada é o que o `install.sh` precisa para não buildar código de outro repo |
| H4-D11 | Dono do esquema | `neo4j/SCHEMA.md` e `neo4j/init/schema.cypher` vão para o indexador, que é quem escreve o grafo; um comando do indexador aplica o esquema e o serviço `neo4j-init` passa a rodá-lo | O esquema aplicado sempre bate com a versão de quem escreve; o stack não copia arquivo de outro repo |
| H4-D12 | Versões | SemVer nos dois, `CHANGELOG.md` no formato Keep a Changelog, release com tag. O comando de instalação do README aponta para uma release, não para a `main` | Quem instala por `curl \| bash` hoje recebe qualquer commit da `main` |

## Fronteira proposta

| Hoje | Vai para | Nota |
|---|---|---|
| `indexer/aidd_indexer/{cli.py,core/,languages/,conventions/,mcp/}` | indexador | menos `core/policy.py` e os subcomandos `policy`/`knowledge` (H4-D7) |
| `indexer/aidd_indexer/knowledge/`, `core/policy.py`, `indexer/policy.example.yaml`, `tests/test_knowledge.py`, `tests/test_policy.py` | aidd-stack | |
| `indexer/conventions/dotnet-praticis/`, fixtures `csharp-praticis-*` | indexador | H4-D8 |
| demais `indexer/tests/`, `indexer/scripts/`, `indexer/tests/corpus_expected/` | indexador | o corpus e as fixtures são a regressão dele |
| `indexer/Dockerfile` | indexador | estágios `base`/`indexer`; o `knowledge` vira Dockerfile do aidd-stack |
| `indexer/atlas.example.yaml`, `setup/conventions/hexagonal.example.yaml` | indexador | documentam formatos do indexador; o `install.sh` passa a tirá-los da imagem ou da release |
| `neo4j/SCHEMA.md`, `neo4j/init/schema.cypher` | indexador | H4-D11; o `neo4j/Dockerfile` (`mcp-neo4j`, perfil debug) fica |
| `setup/` (`install.sh`, `install-check.sh`, `aidd`, `skills/`), `docker-compose.yml`, `gateway/`, `git/`, `obsidian/`, `qdrant/`, `antigravity/` | aidd-stack | `refresher` e `mcp-atlas` continuam no compose, com a imagem publicada |
| `docs/indexer-evolution.md`, `docs/corpus-report.md`, `docs/golden-questions.md`, `docs/indexing-process.md`, ADR-002, ADR-003, handoffs H1 e H2 | indexador | |
| `docs/knowledge-contract.md`, handoff H3, este handoff | aidd-stack | |
| `docs/ROADMAP.md` | os dois | o indexador leva F0–F2 (menos as skills), F1.13, U* e a parte da segurança que é dele; o aidd-stack fica com skills (S*), conhecimento (K*), o resto da segurança (SO*) e F3 |

O que não existe hoje e o repo do indexador precisa: um caminho **sozinho** — um compose mínimo (Neo4j + indexador +
MCP `atlas`) e o `index --dry-run --out` sem banco —, para o README dele ter um início rápido que não passe pelo
aidd-stack.

## Arquitetura dos docs

Os mesmos nomes de arquivo em todos os idiomas (slugs em inglês), para os links mapearem um a um e um gerador de site os
aceitar sem mudança. Os docs de trabalho (ROADMAP, handoffs, ADRs) **não mudam de lugar** no repo em que ficarem: os
caminhos estão citados em todos os handoffs, no histórico e nas skills.

**aidd-stack — README** (cada seção curta, com link para os docs):

1. Seletor de idioma; banner (asset, claro/escuro).
2. O que é, em um parágrafo: a metodologia da Praticis e a suíte que a implementa.
3. O problema que resolve, dito com o que já foi medido (perguntas douradas respondidas pelo grafo, P/R do extrator).
   **Nada de economia de tokens antes do H3.**
4. A metodologia num diagrama: as etapas e o que cada uma lê e escreve.
5. O que vem na caixa: tabela serviço · porta · papel.
6. Início rápido: requisitos (Docker, git, um cliente MCP), instalação, `install-check`, primeiro `scan`.
7. Com que orquestradores funciona, separando o validado (Claude Code) do configurado (Antigravity) e do previsto.
8. Estado: o que é estável e o que é experimental, com link para o ROADMAP.
9. Segurança (só localhost, link para `SECURITY.md`), contribuição, licença, "feito pela Praticis".

**aidd-stack — `docs/<locale>/`:**

```
index.md
getting-started/   install.md · first-project.md (scan) · first-card.md (refine-business)
methodology/       overview.md · stages.md · knowledge.md (ciclo do insight) · principles.md
guides/            tenants-and-sources.md · process-policy.md · continuous-refresh.md · other-orchestrators.md
                   troubleshooting.md (MCP bloqueado, disabledMcpjsonServers…) · upgrade.md · uninstall.md
reference/         components.md · cli.md · configuration.md (.env, policy.yaml) · knowledge-tools.md · vault-contract.md
security/          threat-model.md (fecha o SO15) · hardening.md
faq.md
```

**Indexador — README:** o que extrai (micro e macro, o grafo num diagrama); linguagens e frameworks com a tabela de P/R
do corpus, com data, tamanho do corpus e link para o método — "medido, não sentido" é o argumento do projeto; início
rápido sozinho; as 11 tools do MCP; como estender (linguagem, framework, convenção); quem o usa (aidd-stack).

**Indexador — `docs/<locale>/`:** `concepts/` (modelo do grafo, estratégias de resolução, `confidence`/`evidence`, refs e
snapshots), `getting-started/`, `guides/` (`atlas.yaml`, política de refs, convenções, adicionar linguagem ou framework,
medir com o corpus), `reference/` (esquema, tools do MCP, CLI, `convention.yaml`, `atlas.yaml`) e `explanation/` (ADRs,
relatório do corpus). O `CONTRIBUTING.md` em inglês resume o checklist do guia (§6) e aponta para o
`indexer-evolution.md`, que segue em português enquanto o H2b escrever nele; a tabela de regras (§3) é traduzida no
fechamento do H2 (Fase 5 do `H2-roadmap.md`).

## Idiomas: como funciona

- **Arquivos.** `README.md` (inglês), `README.pt-BR.md`, `README.es.md` e `README.zh-CN.md` na raiz; docs em
  `docs/<locale>/<mesmo caminho>`.
- **Seletor.** Primeira linha de cada página, com os quatro idiomas, gerada por script — nunca à mão.
- **Proveniência.** Cada tradução começa com um comentário, invisível no GitHub:
  `<!-- i18n: source=docs/en/x.md source_sha=<sha> status=machine|reviewed reviewer=<handle> -->`.
- **Defasagem.** Um script (`scripts/i18n_check.py`, no CI) compara o `source_sha` com o último commit que mexeu na
  fonte e lista as traduções defasadas, as páginas da camada 1 que faltam e os links, âncoras e imagens quebrados.
  Página defasada ganha um aviso visível ("esta tradução pode estar desatualizada — ver a versão em inglês"). O CI
  avisa na defasagem e falha no que falta da camada 1 e em link quebrado.
- **Glossário** (`docs/i18n/glossary.md`): termo × idioma, com a lista do que **não** se traduz — nomes de skill,
  serviço e tool (`scan`, `refine-business`, `atlas`, `knowledge`, `who_consumes`…), termos do grafo (`Snapshot`,
  `HttpEndpoint`, `ref`), `tenant`, MCP. O que se traduz e como (skill, insight, vault) se decide com o revisor de cada
  idioma.
- **Guia de estilo** (`docs/i18n/style.md`): pt-BR com "você" e imperativo nas instruções; es neutro, com "tú"; zh-CN
  com pontuação de largura total na prosa e espaço entre caracteres chineses e palavras latinas ou números.
- **Nunca se traduz:** blocos de código, comandos, chaves de configuração, identificadores, caminhos, saída de
  terminal, nomes de arquivo. Os títulos se traduzem, então as âncoras mudam por idioma: o script as valida com o
  algoritmo de slug do GitHub.
- **Fluxo:** mudança em inglês → o CI acusa as traduções defasadas → um PR por idioma (tradução assistida + revisão) →
  `status: reviewed` quando um nativo revisou. Sem revisor, `status: machine` e uma nota visível de que a tradução é
  assistida por máquina: o leitor sabe o que está lendo.

## Contrato com o processo de assets

O ponto de encontro dos dois processos é um manifesto, `docs/assets/README.md`: cada slot com uso, dimensões, variantes,
caminho e estado (`pendente` / `entregue`). Os docs referenciam os slots por caminho fixo desde o início, e o
`i18n_check.py` falha se uma página publicada aponta para um asset que não existe.

| Slot | Onde aparece | Formato | Variantes | Texto na imagem |
|---|---|---|---|---|
| logo (símbolo) | READMEs, site, favicon | SVG | claro/escuro | não |
| banner / wordmark | topo dos READMEs | SVG (+ PNG) | claro/escuro | só o nome; o slogan vai no Markdown, para ser traduzido |
| prévia social | Settings do GitHub (upload manual, fora do repo) | PNG 1280×640 | uma por repo | inglês |
| diagrama da metodologia (destaque) | README, `methodology/overview` | SVG | claro/escuro; um por idioma se tiver texto | evitar; se tiver, `nome.<locale>.svg` |
| diagramas técnicos (componentes, modelo do grafo, fluxos) | referência e conceitos | **Mermaid no Markdown**, não asset | o GitHub renderiza e acompanha o tema | traduzido com a página |
| capturas e gravações de terminal | primeiros passos | PNG ou SVG de gravação | — | a saída fica em inglês: é o que a ferramenta imprime |

Regras para quem produz: SVG otimizado, com o texto do logo e do wordmark convertido em curvas (imagem no GitHub não
carrega fonte); claro/escuro pelo `<picture>` com `prefers-color-scheme`; até ~200 KB por imagem; o texto alternativo é
escrito nos docs, em cada idioma, nunca embutido. Uma nota em `docs/assets/brand/` e no README diz o que da marca pode
ser reutilizado (decisão do autor; o código continua MIT).

## Arquivos de comunidade e metadados (nos dois repos)

- `CONTRIBUTING.md` (inglês, com versão pt-BR), `CODE_OF_CONDUCT.md` (Contributor Covenant, que tem traduções
  oficiais), `SECURITY.md` (canal: *private vulnerability reporting* do GitHub; o que conta como vulnerabilidade aqui —
  exposição dos MCPs, isolamento de tenant, memória envenenada, SO9), `CHANGELOG.md`, `.github/ISSUE_TEMPLATE/*.yml`,
  `PULL_REQUEST_TEMPLATE.md`, `CODEOWNERS`.
- Issues em inglês de preferência, aceitas nos quatro idiomas (o template diz isso).
- Checklist das configurações que não estão em arquivo: descrição, tópicos, site, prévia social, Discussions,
  *private vulnerability reporting*, releases.

## Auditoria antes de publicar

- **Nomes reais** (a regra de sempre, agora com mais gente lendo). Achados na leitura para este handoff, a conferir com
  o autor: `entry-manager-transaction` no log de 2026-10-12 do ROADMAP e `TERCEL_URL` no `H2-public-corpus.md`. Varrer
  também o histórico que vai para o repo novo (H4-D9).
- **Segredos** no histórico inteiro dos dois repos (gitleaks ou trufflehog), antes do primeiro push do repo novo.
- **Números:** todo número dos docs públicos vem de uma fonte reproduzível (relatório do corpus, perguntas douradas),
  com data. Nada de ganho de produtividade ou de tokens até o H3 medir.
- **Referências soltas:** o ADR-001 (Neo4j) é citado no ROADMAP e não existe em `docs/adr/` — escrever ou tirar a
  citação. Os links do aidd-stack para `indexer/...` passam a apontar para o repo novo.

## Ordem

0. **Decisões** H4-D1…D12 e o que obter do autor (seção acima).
1. **Arquitetura dos docs em esboço** — títulos e a pergunta que cada página responde, sem o texto. Pode correr já, em
   paralelo ao H2b, porque não depende de caminhos.
2. **Separação do indexador**, depois do merge da `feature/h2-corpus` (um `filter-repo` com o H2b no meio obriga a
   reaplicar o trabalho dele). Mecânica e sem mudar comportamento, como o ADR-003; regressão = `pytest`, o corpus byte a
   byte igual à baseline vigente e uma **instalação limpa** do aidd-stack com a imagem publicada passando no
   `install-check`. CI do repo novo: testes, build multi-arquitetura, publicação no GHCR por tag. **Pronto quando** os
   dois repos se instalam e testam sozinhos e um aponta para o outro.
3. **Conteúdo em inglês** dos dois repos, aproveitando o que existe: `knowledge-contract.md` → `vault-contract`,
   `SCHEMA.md` → referência, `corpus-report.md` → explicação, `indexer/README.md` dividido entre README e guias, as
   skills → `methodology/stages`. **Pronto quando** alguém que nunca viu o projeto — uma pessoa, ou uma sessão nova de
   agente lendo só os docs — instala e roda o primeiro `scan` sem ajuda.
4. **Infra de idiomas:** glossário, guia de estilo, `i18n_check.py`, workflow do CI.
5. **Traduções:** camada 1 em pt-BR (o autor revisa), depois es e zh-CN; camada 2 em pt-BR.
6. **Assets** conforme forem entregues, arquivos de comunidade, configurações do repo e a primeira release dos dois.
7. *(Opcional)* site, quando a navegação pedir (H4-D4).

## Armadilhas

- Traduzir referência: envelhece no commit seguinte. As camadas (H4-D3) existem por isso.
- A imagem multi-arquitetura baixa as gramáticas do tree-sitter **por arquitetura** no build (é um `.so` por
  linguagem): conferir o `selftest` nas duas.
- A impressão digital do build (`indexer_build`) inclui os pacotes de convenção instalados. Se o `dotnet-praticis` sair
  depois, a conta precisa continuar a enxergá-lo, senão um snapshot deixa de reindexar quando ele muda.
- Sem a API pública declarada (H4-D7), um refactor interno do indexador quebra o `knowledge` no outro repo.
- O `curl | bash` do README é o primeiro comando que um estranho roda: precisa apontar para uma release (H4-D12) e dizer
  o que instala antes de instalar.
- A prévia social é configurada à mão nas Settings; não basta commitar a imagem.

## Restrições e convenções

- Sem nomes reais de projeto ou tenant em docs, código ou histórico publicado.
- Os docs públicos descrevem o que existe e foi validado; o que é plano aparece como plano, com link para o ROADMAP.
- Tom técnico e factual, como os docs atuais: sem promessa nem "mágica".
- Os caminhos dos docs de trabalho não mudam (ROADMAP, handoffs, ADRs).
- Tradução nunca é editada sem atualizar o cabeçalho de proveniência.

## Entregáveis esperados

- Dois repositórios com a fronteira acima executada e o aidd-stack instalando a imagem publicada do indexador.
- READMEs nos quatro idiomas nos dois repos; `docs/<locale>/` com a camada 1 em todos, a 2 em pt-BR e a 3 em inglês.
- Glossário, guia de estilo, `i18n_check.py` e o workflow do CI.
- `docs/assets/README.md` com os slots, e os assets entregues no lugar.
- Arquivos de comunidade, configurações do repo conferidas e a primeira release com `CHANGELOG`.
- O resultado da auditoria no PR: o que foi achado e o que se fez.
- ROADMAP: D5 fechado, itens P1–P6 marcados e o ROADMAP do indexador nascido da divisão.
