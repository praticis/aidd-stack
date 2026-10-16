# Handoff H3 — Medir o efeito do atlas e do conhecimento no desenvolvimento com IA

> Cole este arquivo (ou peça para ler `docs/handoffs/H3-ai-dev-efficiency.md`) no início de um chat novo. Antes de
> qualquer coisa, o chat deve ler `docs/ROADMAP.md` (trilha de skills e conhecimento), `docs/golden-questions.md`
> (o que o atlas responde e como se confere) e `docs/knowledge-contract.md`. Para a disciplina de medição — gabarito,
> baseline, julgar o diff, categoria do erro —, o modelo é o do H2 (`docs/handoffs/H2-roadmap.md`).
>
> **Estado (2026-10-16):** registrado, não iniciado. Nasceu de uma pergunta durante o H2b: o arcabouço reduz os tokens
> do desenvolvimento orientado por IA, ou o ganho principal está em outro lugar? A resposta dada foi uma estimativa,
> não uma medição; este handoff é para transformá-la em dado.

## Contexto em um parágrafo

A stack dá ao agente fatos sobre o código que ele não precisa redescobrir: o grafo do atlas (símbolos, chamadas,
imports, rotas e chamadas HTTP ligadas entre repos e entre refs, via MCP) e o conhecimento do processo (`policy_for`,
`insights_for`, `record_insight`). O custo de construir isso é alto: indexação, extrator HTTP medido num corpus,
linker, serviço de conhecimento. Ainda não há número que diga quanto ele devolve, nem em quê. Sem esse número, não dá
para priorizar o que falta (mais recall do extrator? respostas MCP mais enxutas? as skills S1–S7?) nem defender o
custo.

## Hipóteses a confirmar ou derrubar

A estimativa de 2026-10-16, sem medição:

1. **Tarefa dentro de um repo:** a economia de tokens é modesta. Um agente com grep já é eficiente ali, e a maior parte
   dos tokens vai para ler o código que vai mudar, raciocinar, escrever e testar — o grafo só encurta a descoberta.
2. **Tarefa entre repos** (mudar um contrato HTTP, achar quem consome uma rota, impacto de uma branch): a diferença é
   grande, e sobretudo em **completude**. Sem o grafo, o agente nem sabe em que repos procurar; um consumidor esquecido
   é uma quebra silenciosa.
3. **O ganho principal é menos retrabalho, não menos leitura:** dependência inventada, consumidor esquecido e erro já
   corrigido antes (que o conhecimento do processo evita) custam uma rodada inteira de review, teste e correção.
4. **Riscos que podem anular o ganho:**
   - grafo desatualizado ou com recall baixo gera confiança indevida — o agente para de procurar;
   - respostas MCP grandes (um `repo_map` inteiro de um repo de 10 mil arquivos) custam mais tokens que um grep bem
     feito.

## Desenho do experimento

**Tarefas.** Cerca de 10 tarefas reais do portfólio, metade dentro de um repo e metade entre repos, cada uma com
resposta conhecida. A forma mais barata de ter gabarito é **reencenar PRs já mergeados**:

- partir do commit anterior ao PR;
- dar ao agente o card ou a descrição original;
- comparar com o que o PR de fato mudou (arquivos, repos, consumidores ajustados, testes).

Incluir de propósito tarefas em que o PR original esqueceu algo que depois quebrou, se houver: são as que testam a
hipótese 2.

**Condições.** As mesmas tarefas em cada uma, com o mesmo modelo, o mesmo prompt ou skill, o mesmo commit de partida
e uma sessão nova por execução:

- **A** — sem atlas e sem conhecimento (leitura, grep, git);
- **B** — com o atlas;
- **C** — com o atlas e o conhecimento do processo (só quando houver insights acumulados na área).

Pelo menos 2 ou 3 repetições por tarefa e condição: a variância do modelo entre execuções pode ser maior que o efeito.

**Métricas, por execução:**

- tokens de entrada, saída e cache. As transcrições do Claude Code (`~/.claude/projects/<projeto>/<sessão>.jsonl`)
  registram o uso por mensagem; um script soma por sessão;
- quanto desses tokens veio de respostas MCP e quanto de leitura de arquivos;
- número de chamadas de ferramenta e tempo de parede;
- **completude** contra o gabarito: arquivos e repos certos, consumidores encontrados;
- **defeitos:** testes quebrados, o que o review apontaria e iterações até ficar verde.

**Análise.** Por tipo de tarefa (local × entre repos), com mediana e dispersão; nada de conclusão com n pequeno sem
dizer o tamanho da amostra. O resultado esperado é um mapa de onde o atlas paga, não um número único.

## Pré-requisitos

- Recall do extrator suficiente nas linguagens das tarefas. O H2 mede isso; ver os números vigentes no
  `docs/handoffs/H2-roadmap.md` antes de escolher as tarefas, e preferir as linguagens já fechadas.
- Os repos do experimento indexados no atlas, nos refs certos, e o linker rodado.
- Para a condição C: insights registrados na área das tarefas; sem eles, C é igual a B.

## Restrições e convenções

- Sem nomes reais de projeto ou tenant nos docs: o relatório descreve tarefas e resultados em forma, não em conteúdo
  (como o `golden-questions.md`). A lista de tarefas e os gabaritos ficam fora do repo público, no espaço do tenant.
- Completude e defeitos julgados por gabarito e testes; quando precisar de julgamento, uma pessoa confere uma amostra.
  LLM não julga o próprio resultado.
- Não otimizar a stack no meio da medição: uma mudança no atlas entre execuções invalida a comparação. Mudanças viram
  uma nova rodada.

## Entregáveis esperados

- Script que soma o uso de tokens por sessão a partir das transcrições, separando MCP de leitura de arquivos.
- Relatório (`docs/ai-dev-efficiency-report.md`, EN, como o `corpus-report.md`): método, tarefas em forma e resultados
  por tipo de tarefa e condição.
- Conclusão acionável: onde o atlas paga, onde não paga e o que mudar. Por exemplo: recortar respostas MCP grandes,
  priorizar recall em certas linguagens ou adiantar ou adiar skills.
- ROADMAP: o item S9 marcado, com o resumo no log.
