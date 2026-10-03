# Processo de indexação do atlas — proposta (em discussão)

> Status: **decidido e implementado para a fonte `local`** (2026-09-11, F0.3.5). Providers remotos e
> scheduler ficam para F1. D9 resolvido sem espelhos: refs são materializados com `git archive`
> a partir das remote-tracking refs do clone do dev. D11 simplificado: `areas` opcional no manifesto.
> Contexto: F0.3 validado (`aidd index <repo>` funciona), mas indexar é hoje um comando manual,
> repo a repo, sobre a branch que estiver checked out. Precisa virar processo.

## 1. Problema

Três perguntas ficaram abertas depois do F0.3:

1. **Como o portfólio inteiro do tenant entra no atlas** na instalação (bootstrap), sem depender
   do que cada dev tem clonado.
2. **Quais branches indexar**: hoje é "a que está checked out"; queremos `main`, `develop` e só as
   branches com movimentação recente — nunca todas.
3. **Como manter atualizado** até existirem triggers de pipeline (Fase 3).

## 2. Princípio: separar *fonte* de *workspace*

O workspace do dev (`WORKSPACE_PATH`) é volátil — branch checked out, arquivos sujos, só os repos
que ele clonou. Não serve como fonte para o atlas do tenant. A proposta é o atlas ter a **sua
própria fonte**: um espelho de repositórios sob controle do aidd.

```
~/.aidd/_docker/mirror/<tenant>/<repo>.git     ← clones bare, atualizados por `aidd sync`
~/.aidd/atlas.yaml                              ← manifesto: fontes, seleção, política de refs
```

Com espelhos, `aidd index <repo> --ref develop` faz `git worktree add` temporário do ref pedido,
indexa e descarta — independente do que o dev tem aberto. O workspace do dev continua servindo para
o caso **efêmero**: indexar a branch do card no `refine-tech`.

## 3. Manifesto `atlas.yaml` (por instalação, seções por tenant)

```yaml
tenants:
  <tenant>:
    sources:
      - type: local            # repos já clonados no workspace do dev (bootstrap rápido, sem rede)
        path: ${WORKSPACE_PATH}/<tenant>
      - type: github           # ou gitlab | azure-devops | bitbucket — cada tenant escolhe o seu
        org: <github-org>
        token_env: GITHUB_TOKEN_<TENANT>   # nome da env var, nunca o valor
        include: ["*"]         # globs sobre o nome do repo
        exclude: ["*-archive", "poc-*"]
        skip_archived: true
    refs:
      always: ["main", "master", "develop"]     # indexa os que existirem
      patterns: ["release/*"]                    # opcional
      active:
        max_age_days: 14       # branches com commit nos últimos N dias…
        max_per_repo: 5        # …limitado a K por repo, marcadas ephemeral: true
        exclude: ["dependabot/*", "renovate/*", "docs/*", "ci/*", "cd/*", "pipeline/*"]
      gc_ephemeral_after_days: 30
      overrides:             # opcional: política por repo (nome exato ou glob; sobrescreve só o que declarar)
        <project>:
          always: ["main"]   # ex.: `develop` abandonada neste repo — sai da política sem mexer no tenant
        "legacy-*":
          always: ["master"]
          active: false      # sem branches ativas para esses
    schedule: "0 */6 * * *"    # refresh automático (aidd sync + index --changed) até a Fase 3
```

Regras: nenhum default implícito de tenant (D7); tokens só por referência a env var; `local` e
remotos podem coexistir (o remoto é a fonte de verdade quando os dois têm o mesmo repo).

## 4. Comandos

| comando | faz |
|---|---|
| `aidd sync [--tenant T]` | lista repos nas fontes (provider API), cria/atualiza espelhos bare (`git fetch --prune`), grava `Repo` com `url`, `default_ref`, `archived`, `last_activity` |
| `aidd plan [--tenant T]` | mostra o que **seria** indexado: repos × refs segundo a política, com motivo (`always`, `active: 3 commits/9d`) — sem tocar no grafo |
| `aidd bootstrap [--tenant T] [--all \| --repos a,b,c]` | `sync` + `index` de tudo que o `plan` listou; idempotente; retomável |
| `aidd index <repo> [--ref R] [--ephemeral]` | já existe; passa a aceitar `--ref` real (worktree do espelho) além do workspace |
| `aidd refresh` | só o que mudou: compara `commit_sha` do espelho com o `Snapshot`; reindexa diferenças; GC de snapshots efêmeros vencidos |
| `aidd status` | já existe; ganha coluna `stale` (espelho à frente do snapshot) |

## 5. Onde entra no `install.sh`

Depois da etapa de infra (compose up) e antes de distribuir o `.mcp.json`:

```
=== 4. Atlas bootstrap ===
  1) Indexar o workspace local agora (repos já clonados)          ← default
  2) Configurar fonte remota (GitHub/GitLab/Azure DevOps) e indexar o portfólio
  3) Pular (rodar `aidd bootstrap` depois)
```

A opção 2 pede provider, org/grupo e o nome da env var do token, grava no `atlas.yaml`, roda
`aidd plan` e pede confirmação ("42 repos × 2,3 refs em média ≈ 97 snapshots — indexar todos ou
escolher?"). O `install.sh` continua sendo também o comando de **upgrade**: re-executá-lo sincroniza
`~/.aidd`, reaplica o schema e reconstrói as imagens (inclusive o profile `tools`).

## 6. Fases

| quando | o que |
|---|---|
| **F0.3.5 (agora)** | `atlas.yaml` + fonte `local` + política de refs + `aidd plan/bootstrap/refresh` + opção no `install.sh` + `--ref` real via worktree |
| F1 | providers remotos (GitHub primeiro; GitLab/Azure DevOps na sequência), espelhos bare, `aidd sync`, scheduler no compose |
| F2 | governança: ler `catalog-info.yaml` (Backstage) / CODEOWNERS → nós `Domain`, `System`, `Team`, aresta `OWNS`; opcionalmente integrar com Backstage ou Atlassian Compass como fonte do catálogo |
| F3 | triggers de pipeline (push em branch protegida → `aidd index`), central substitui o scheduler |

## 7. Decisões

- D8 **Em aberto** — providers em uso por tenant; necessário só na F1.
- D9 **Resolvido** — sem espelhos na fonte `local`: o indexador faz `git fetch --all --prune` (credenciais SSH/.gitconfig montadas como no `mcp-git`) e materializa refs com `git archive <sha>`; a working tree nunca é tocada. Espelhos bare só com providers remotos (F1).
- D10 **Resolvido** — defaults `14 dias / 5 por repo / GC 30 dias`, editáveis no `atlas.yaml`.
- D11 **Simplificado** — `areas:` opcional no manifesto (nome → repos/globs), usado pelo `aidd plan` para agrupar e gravado em `Repo.area`. Nós `Domain`/`System`/`Team` e Backstage/Compass ficam para F2.
