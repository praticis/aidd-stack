# H2 — corpus público e precisão/recall do extrator HTTP (encerrado)

> Handoff **fechado** (F0.4.3a, F0.4.3b e F1.14).
>
> - O plano, as fases, o log diário e as tabelas de cada passo saíram na reciclagem de 2026-10-19 (fase 0a do H4) e
>   ficam no git: `git show 1d73bb0:docs/handoffs/H2-roadmap.md`.
> - As decisões H2-D1…D21 estão em `docs/decisions.md`; os marcos, em `docs/history.md`; os números e o método, em
>   `docs/corpus-report.md`.

## Resumo

- **O H2 está encerrado.** F0.4.3a, F0.4.3b e o F1.14, que levou ao extrator o que o
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

## Como medir hoje

- O corpus: `indexer/scripts/corpus.sh --baseline 2026-10-18-v2-baseline-28`. O hold-out: `--holdout --baseline
  2026-10-18-v2-holdout-26`.
- Os testes: `indexer/scripts/test.sh`.
- O ciclo de uma mudança no extrator está no guia, `docs/indexer-evolution.md` §5.
