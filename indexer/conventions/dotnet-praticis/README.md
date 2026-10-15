# dotnet-praticis

An [aidd convention](../../aidd_indexer/conventions/base.py) for the Praticis .NET pattern: CQRS over an
in-house service bus. Controllers dispatch commands (`ServiceBus.SendAsync(new XCommand(..))` →
`ICommandHandler<XCommand>`), consumers receive broker events already deserialized
(`IEventHandler<ContractEvent>`), a `<Org>.<Svc>.Contracts` project publishes requests, responses and
events as a NuGet package, and outbound HTTP lives in typed clients.

The pattern is the same in every service; the solution layout grows with it:

| Layout | Projects |
|---|---|
| `flat` | `.Api` (Controllers, Consumers, Application, Core, Domain, Infra, Extensions) + `.Contracts` |
| `split` | `.Api` (Controllers, Consumers, Extensions) + `.Core` (Application, Domain, Infra/{Data,Http}, handlers) + `.Contracts` |
| `layered` | `.Api` + `.Application` (Commands, Validators, Queries) + `.Core` (handlers) + `.Domain` + `.Infra` (Data, Http) + `.Contracts` |

What it adds to atlas (all in [`convention.yaml`](aidd_conventions_dotnet_praticis/convention.yaml)):

- **Roles** (`Symbol.role`) — what each type is, by its declaration, wherever it lives: `controller`,
  `command`, `command-handler`, `event`, `event-handler`, `validator`, `query`, `model`, `repository-port`,
  `repository`, `mapping`, `data-context`, `outbound-client`.
- **Layout** — detected from the projects of the same service (`{svc}.Api` + `{svc}.Core` → `split`,
  `{svc}.Api` + `{svc}.Application` → `layered`, otherwise `flat`); force it per repo with
  `options: {architecture: split}`. Layers: `contracts`, `api`, `consumers`, `application`, `core`,
  `domain`, `outbound`, `infra`, `bootstrap`; a file the layout does not place takes its roles' layer.
- **Entry points** — `Handle` of command/event handlers (reached through the bus, not by a call).
- **Dispatch** — the in-house bus: `SendAsync` reaches the `Handle` of the `ICommandHandler<X, ..>` of the
  message's type, `PublishAsync` every `IEventHandler<X>` — CALLS with strategy `dispatch`, so a controller
  reaches its handler in the graph whatever the handler is called (MediatR is built into the C# support).
- **Violations** — contracts import nothing from the service; domain is pure; application does not know
  implementations; controllers dispatch through the bus; consumers do not talk HTTP/storage directly;
  each role lives in its layer (a handler in `.Application` is flagged); routes only in controllers;
  outbound HTTP only in the outbound layer.

## Use

The indexer image installs every package under `indexer/conventions/` at build time. Enable it per
tenant (optionally per repo) in `atlas.yaml`:

```yaml
tenants:
  <tenant>:
    conventions:
      - id: dotnet-praticis
        repos: ["*"]
      # - id: dotnet-praticis            # a repo whose layout detection needs help
      #   repos: ["legacy-api"]
      #   options: {architecture: flat}
```

One-off run without a manifest: `AIDD_CONVENTIONS=dotnet-praticis aidd index <repo> --dry-run --out x.json`
(the log shows the detected layout: `[conv] dotnet-praticis[split]: ...`).
Outside the image: `pip install -e indexer -e indexer/conventions/dotnet-praticis`.

## Tests

Golden fixtures in `indexer/tests/fixtures/`, one per layout: `csharp-praticis-todos` (`flat`, provider),
`csharp-praticis-reports` (`split`, consumer) and `csharp-praticis-projects` (`layered`, consumer). Each
`expected.json` lists the detected layout, every role, every file's layer, the handler entry points, one
deliberate violation, the CALLS chain and the known gaps; `test_linker.py` links both consumers to the
provider's route and `test_deps.py` the `.Contracts` package.
