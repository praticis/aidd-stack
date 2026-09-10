// ---- Identity: every node has a unique `id` within its label ----------------
CREATE CONSTRAINT repo_id       IF NOT EXISTS FOR (n:Repo)            REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT module_id     IF NOT EXISTS FOR (n:Module)          REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT file_id       IF NOT EXISTS FOR (n:File)            REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT symbol_id     IF NOT EXISTS FOR (n:Symbol)          REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT http_id       IF NOT EXISTS FOR (n:HttpEndpoint)    REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT grpc_svc_id   IF NOT EXISTS FOR (n:GrpcService)     REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT grpc_mth_id   IF NOT EXISTS FOR (n:GrpcMethod)      REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT topic_id      IF NOT EXISTS FOR (n:Topic)           REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT event_id      IF NOT EXISTS FOR (n:EventSchema)     REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT pkg_id        IF NOT EXISTS FOR (n:Package)         REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT table_id      IF NOT EXISTS FOR (n:DbTable)         REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT service_id    IF NOT EXISTS FOR (n:Service)         REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT snapshot_id   IF NOT EXISTS FOR (n:Snapshot)        REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT indexrun_id   IF NOT EXISTS FOR (n:IndexRun)        REQUIRE n.id IS UNIQUE;

// ---- Filters most used by the MCP -------------------------------------------
CREATE INDEX symbol_tenant_repo_ref IF NOT EXISTS FOR (n:Symbol) ON (n.tenant, n.repo, n.ref);
CREATE INDEX file_tenant_repo_ref   IF NOT EXISTS FOR (n:File)   ON (n.tenant, n.repo, n.ref);
CREATE INDEX symbol_name            IF NOT EXISTS FOR (n:Symbol) ON (n.name);
CREATE INDEX symbol_kind            IF NOT EXISTS FOR (n:Symbol) ON (n.kind);
CREATE INDEX file_path              IF NOT EXISTS FOR (n:File)   ON (n.path);
CREATE INDEX http_method_path       IF NOT EXISTS FOR (n:HttpEndpoint) ON (n.method, n.path);
CREATE INDEX topic_name             IF NOT EXISTS FOR (n:Topic)  ON (n.name);
CREATE INDEX snapshot_repo_ref      IF NOT EXISTS FOR (n:Snapshot) ON (n.tenant, n.repo, n.ref);

// ---- Text search (fallback when Qdrant doesn't have the symbol) --------------
CREATE FULLTEXT INDEX symbol_fulltext IF NOT EXISTS
  FOR (n:Symbol) ON EACH [n.name, n.qualified_name, n.signature, n.doc];
