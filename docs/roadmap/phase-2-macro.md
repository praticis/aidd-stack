# Phase 2 — Complete macro (contract linker)

> The macro level of the graph: the routes a service exposes, the calls it makes and the links between services, read
> from the code and from what declares them (specs, messaging, infrastructure, databases), each link with its evidence.
> The fields are H10-D2's; the map of the roadmap is `docs/ROADMAP.md`.

- [ ] F2.1 OpenAPI connector: specs → `HttpEndpoint`; routes extracted from the code reconciled with the spec
  (divergence = alert)
  - **Sketch:** missing the spec formats and versions read (OpenAPI, and the `.proto` a Connect service is generated
    from: `docs/corpus-report.md` leaves memos' 93 Connect routes here), what an alert is in an answer, and the
    repositories that measure it; first step: the corpus repositories that commit an OpenAPI spec or a Connect `.proto`,
    each with the routes its spec lists against the ones the extractor finds
  - **Verified by:** anyone
  - **Depends on:** nothing
- [ ] F2.2 Messaging connector: topics/queues in constants, config and env (Kafka, RabbitMQ, SQS/SNS) →
  `PUBLISHES`/`SUBSCRIBES`; event schemas when they exist
  - **Sketch:** missing the first broker and language, and the reference it is measured against, since the corpus lists
    only HTTP; first step: an expected list for the corpus repositories that publish or subscribe through a broker, the
    topics each names, as a literal or by the type of the event it sends, written by hand from the source
  - **Verified by:** anyone
  - **Depends on:** nothing
  - **Not to do:** write a credential that a manifest, a URL or a connection string carries
- [ ] F2.3 Infra connector: `docker-compose`, k8s/Helm, gateway → resolve `ENV_VAR → URL → repo` to link outbound
  HTTP calls to the target repo
  - **Sketch:** missing the first manifests read (compose, Helm, an API gateway's routes), the calls it must link, and
    what a link keeps as its evidence, since a variable's value is read to resolve it and never enters the graph; the
    linker already reads the variable's name as a hint to the provider; first step: the corpus's outbound calls whose
    base URL comes from an environment variable, counted, and how many of them a compose or Helm file in the same
    repository resolves to a host
  - **Verified by:** anyone
  - **Depends on:** nothing
  - **Not to do:** write a variable's value, or a credential that a manifest, a URL or a connection string carries
- [ ] F2.4 Database connector: migrations/ORM → `DbTable`, `READS/WRITES`; tables shared between repos = an implicit
  macro edge
  - **Sketch:** missing the first migration or ORM format, the database a table belongs to, and the evidence an implicit
    edge carries; first step: the corpus repositories with migrations or an ORM, by format, each with the tables it
    declares and the database its configuration names
  - **Verified by:** anyone
  - **Depends on:** nothing
  - **Not to do:** write a credential that a manifest, a URL or a connection string carries
- [ ] F2.5 Confidence and evidence on the macro edges F2.1 to F2.4 add, as `CONSUMES` has them (`exact`, `suffix`, and
  the candidates listed when the linker cannot decide); no level is decided by a model
  - **Sketch:** missing what each level means for an edge that is not an HTTP call, the form of its list of candidates
    in an answer (HTTP's is `who_consumes`'s `possible_consumers`), and whether it is a contract each connector follows
    from its first pull request or a pass over their edges once they exist; first step: the levels and the evidence
    `CONSUMES` writes today, written as the contract a new macro edge follows
  - **Verified by:** anyone
  - **Depends on:** nothing
- [ ] F2.6 `atlas` MCP: `workspace_map(tenant)`, and the cross-repo impact of an endpoint or a topic, as `impact_of`
  gives a symbol's (`repo_map` already gives a repo's dependencies); Go's `who_calls` across repositories
  - **Sketch:** missing the shape of each answer (`who_consumes` already lists an endpoint's consumers); the topic
    target, which needs topics in the graph; and how a call into another repository's Go package reaches that package's
    symbols, since a `CALLS` edge stays inside one snapshot; first step: `workspace_map`, checked against golden
    question Q3's Cypher on the repositories `mcp-it` indexes
  - **Verified by:** anyone
  - **Depends on:** nothing
  - **Not to do:** rename a tool `docs/atlas-interface.md` lists
- [ ] F2.8 Visualization: export of the subgraph as static HTML or as data — human reading of the macro level
  - **Sketch:** missing which subgraph, its size and its format; first step: the rows golden question Q3 reads, for the
    repositories `mcp-it` indexes, written as one static HTML page and as JSON, with their bytes per service and per
    link
  - **Verified by:** anyone
  - **Depends on:** nothing
- [ ] F2.9 Macro golden questions (≥ 15) + `aidd eval` covering micro and macro
  - **Sketch:** missing the pass rule, and how its questions split from F1.12's twenty, since three of the five
    documented questions already cross repositories; first step: the macro questions beyond Q1, Q3 and Q4, each with its
    tool and the Cypher that checks it, as the documented ones have
  - **Verified by:** the author (the golden calls run on his tenants)
  - **Depends on:** F1.12
- [ ] F2.10 Front-end flows: the screens of a front end, the navigation between them, and the HTTP calls each screen
  makes
  - **Sketch:** missing what is extracted (a route table, a component tree), from which frameworks first, and the
    reference it is measured against; first step: an expected list for one front end of the corpus, its screens, the
    navigation between them and the calls each makes, written by hand from the source
  - **Verified by:** anyone
  - **Depends on:** nothing
- [ ] F2.11 gRPC connector: the services a `.proto` declares → `GrpcService`, `GrpcMethod`; the servers that register
  them and the clients that call them → `EXPOSES`, `CALLS_GRPC`
  - **Sketch:** missing the first languages and frameworks read (a server's registration, a client's construction),
    how a client's address finds its server, and whether a Connect route, an HTTP route of the same `.proto`, is also
    a gRPC method; first step: an expected list for the corpus repositories whose `.proto` declares a service, the
    services each serves and the calls to them, written by hand from the source
  - **Verified by:** anyone
  - **Depends on:** nothing

**Phase exit:** a queryable workspace map; cross-repo impact with evidence.
