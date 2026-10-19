# Handoff H2 — ampliar o corpus público e medir precisão/recall do extrator (encerrado)

O briefing pedia quatro coisas:

- levar o corpus de calibração do extrator HTTP (15 repos) a ~40 repos, com frameworks e apps reais;
- um gabarito por repo (spec commitada ou leitura do código);
- precisão e recall por linguagem, com os erros por categoria;
- corrigir o que fosse regra geral.

O texto original está em `git show 1d73bb0:docs/handoffs/H2-public-corpus.md`. O plano e as decisões estão em
`H2-roadmap.md` e `docs/decisions.md`.

**Encerrado (2026-10-18).** Os entregáveis do briefing foram cumpridos, e o F1.14 levou ao extrator o que o H2b e o
hold-out deixaram.

- **Corpus:** 55 repos públicos, 54 deles com gabarito (spec commitada conferida no código, ou lista lida no
  código), fixados por SHA.
- **Hold-out:** 3 repos fora do ajuste. O hold-out novo fica para depois do H5 (H2-D21).
- **Instrumento:** `http_corpus.py`, `corpus_metrics.py` e `corpus.sh`.
- **Números finais** (P / R pelo gabarito):

  | | C# | Go | Python (FastAPI/Flask) | TS/JS |
  |---|---|---|---|---|
  | Rotas | 100 / 99,3 % | 98,9 / 93,3 % | 99,3 / 98,6 % | 98,1 / 91,7 % |
  | Chamadas | 100 / 99,0 % | 100 / 93,6 % | — | 98,4 / 99,0 % |

- **Onde está cada coisa:**
  - o relatório e o destino de cada lacuna: `docs/corpus-report.md` ("Closing F1.14 and H2");
  - o resumo: `H2-roadmap.md`; as decisões: `docs/decisions.md`; os marcos: `docs/history.md`;
  - as regras: `docs/indexer-evolution.md`.

