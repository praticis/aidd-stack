# HTTP extractor — corpus report v1

Precision and recall of the HTTP integration extractor (`core/integrations.py` + `languages/<lang>/http.py`)
on the public calibration corpus. This is v1 (F0.4.3a, handoff H2a): the 15 repositories the extractor was
calibrated on, pinned to fixed commits and measured against an expected list per repository. H2b (F0.4.3b)
widens the corpus and changes the extractor in the order this report sets. Plan, decisions and status are in
`docs/handoffs/H2-roadmap.md`.

- Measured on 2026-10-14, indexer 0.2.14, commits pinned in `indexer/scripts/http_corpus.py` (`CORPUS`).
- Expected lists: `indexer/tests/corpus_expected/<repo>.json` (format in `indexer/scripts/corpus_metrics.py`).
- The extractor was **not changed** for this report. Every number comes from the baseline run.

## How it was measured

Two independent measures per repository, kept apart because they answer different questions:

1. **Precision from a sample of what was extracted** (`checked`): up to 20 routes per repository, drawn with a
   fixed seed (`--sample 20 --seed 1`, all of them when there are 20 or fewer), plus every outbound call (there
   are only 24 in the whole corpus). Each item was read at its evidence line and judged against what the
   application really serves or requests. This is precision over the whole repository.
2. **Precision and recall against an expected list** (`endpoints` / `calls` with a `scope`): a committed
   OpenAPI spec where one exists (3 repositories), otherwise source files read end to end and every route or call
   in them listed by hand. Only extracted items whose evidence falls inside the scope count. Recall is only
   measured this way: sampling what was extracted can never show a miss.

Rules applied while judging (H2-D5, D12, D13 in the roadmap):

- Matching is by `(method, path_key)` over distinct pairs. Placeholder names do not matter, and ANY matches any method.
- A route or call whose path **lost a prefix the code holds** (a group, a mount, `include_router(prefix=)`, a
  class field interpolated into the URL) is **wrong**. The path is the linker's join key, so a wrong path
  means a wrong link or none. A prefix that comes from config or the environment (`BaseAddress`, `*_URL`)
  belongs to the linker (F0.5) and is not counted against the extractor.
- Outbound calls are only expected when their path is a literal or a template in the code. URLs assembled at
  runtime are out of the measure.
- What the graph receives is what is measured, after `_dedupe`. Collapsing equal routes from different apps of
  one repository is a real defect, not a measurement artefact (category `multi-app-repo`).

Reproduce (see the roadmap for the container command):

```bash
python scripts/http_corpus.py --expected --baseline <runs/baseline> --show 20
```

The run prints every number below, lists the false positives and misses behind them, and ends with the
per-language and per-category tables.

## Results by language

Pooled over the repositories of each language. *P checked* = sampled items judged correct. *P/R expected* =
against the expected lists, within their scopes.

| Language | Kind | P checked | P expected | R expected |
|---|---|---|---|---|
| Go | routes | 60.6 % (60/99) | 17.4 % (4/23) | 6.1 % (4/66) |
| Go | calls | 80.0 % (4/5) | 100 % (4/4) | 36.4 % (4/11) |
| TS/JS | routes | 33.8 % (22/65) | 9.1 % (2/22) | 5.9 % (2/34) |
| TS/JS | calls | 100 % (2/2) | — | — |
| C# | routes | 90.0 % (18/20) | 100 % (18/18) | 48.6 % (18/37) |
| C# | calls | 50.0 % (3/6) | 50.0 % (3/6) | 18.8 % (3/16) |
| Python | routes | 62.7 % (32/51) | 44.1 % (15/34) | 30.6 % (15/49) |
| Python | calls | 63.6 % (7/11) | — | — |

Read with the sample sizes in mind: 235 routes and 24 calls judged by hand, 11 to 66 expected pairs per
language and kind. These figures show where the extractor fails and roughly how much. Small movements between runs
mean nothing.

Two things move these numbers more than the language does:

- **Most wrong routes are wrong only because the prefix was lost.** That accounts for 67 of the 103 wrong
  routes in the sample. Such a route is counted twice: as a false positive with the short path, and as a miss
  with the full one. That is why a repo like `fastapi-template` shows P 0 % and R 0 % although every route
  and handler was found.
- **The corpus is example-heavy.** Framework repositories carry their own test apps and library code (33 wrong
  routes, mostly nest's `integration/`), and example collections repeat the same routes across apps. Product
  repositories will not look like this. H2b adds real services to balance it.

## Results by repository

| Repo | Lang | Routes | Calls | Expected list (scope) | P routes checked | P / R routes expected | P / R calls expected |
|---|---|---|---|---|---|---|---|
| alertmanager | Go | 22 | 0 | OpenAPI `/api/v2` (recall only); notifier calls | 68.2 % (15/22) | — / 0 % (0/9) | — / 0 % (0/7) |
| chi | Go | 25 | 0 | 3 example files | 24.0 % (6/25) | 16.7 % / 4.5 % | — |
| fiber-recipes | Go | 127 | 5 | OpenAPI `swagger/` recipe; sveltekit calls | 100 % (20/20) | 100 % / 50 % | 100 % / 100 % |
| gin-examples | Go | 31 | 0 | 4 examples | 95.0 % (19/20) | 33.3 % / 8.3 % | — |
| gin-realworld | Go | 12 | 0 | the two routers files | 0 % (0/12) | 0 % / 0 % | — |
| gorilla-mux | Go | 0 | 0 | library only, nothing expected | — | — | — |
| express | TS/JS | 31 | 0 | `examples/multi-router/` | 85.0 % (17/20) | — / 0 % (0/5) | — |
| express-realworld | TS/JS | 19 | 0 | the four controllers | 0 % (0/19) | 0 % / 0 % | — |
| fastify | TS/JS | 6 | 1 | `examples/` | 33.3 % (2/6) | 66.7 % / 33.3 % | — |
| nest | TS/JS | 195 | 1 | `sample/01-cats-app`, `sample/24-serve-static` | 15.0 % (3/20) | — / 0 % (0/4) | — |
| eshop | C# | 23 | 6 | OpenAPI Catalog + Ordering, Webhooks by hand; client services | 90.0 % (18/20) | 100 % / 66.7 % | 50 % / 18.8 % |
| clean-arch-dotnet | C# | 0 | 0 | `src/Web/Endpoints/` | — | — / 0 % (0/10) | — |
| fastapi | Python | 84 | 11 | `docs_src/bigger_applications/` | 100 % (20/20) | 100 % / 37.5 % | — |
| fastapi-template | Python | 19 | 0 | `backend/app/api/routes/` | 0 % (0/19) | 0 % / 0 % | — |
| flask | Python | 12 | 0 | tutorial, celery and javascript examples | 100 % (12/12) | 100 % / 66.7 % | — |

The `notes` field of each expected list explains its choices and the misses in prose.

## Gaps by category

*Wrong* = sampled items judged wrong. *Missed* = distinct expected pairs not extracted. Categories are recorded
per item in the expected lists (`category` on a miss, on a wrong `checked` item), so the run recounts them.

### Routes

| Category | Wrong | Missed | What it is | What it would take | Goes to |
|---|---|---|---|---|---|
| `prefix-other-file` | 39 | 41 | Prefix applied in another file: `app.use('/api', router)`, `Router().use('/api', api)`, `app.include_router(r, prefix=settings.API_V1_STR)` | A per-repo **mount graph** after the scan: router variable/module → prefix, with imports to follow modules and constants/settings to resolve the prefix. Recorded `confidence: heuristic` | extractor (H2b) |
| `router-as-param` | 20 | 18 | Routes registered in a function that receives the router/group: `func Register(r *gin.RouterGroup)`, `V1DeprecationRouter.Register(r.WithPrefix("/api/v1"))` | The same mount graph, plus call sites: `Register(v1.Group("/users"))` gives the parameter its prefix | extractor (H2b) |
| `root-route-dropped` | 0 | 35 | `r.Get("/", h)`, `@router.get("/")`, `MapGet("/")`, `router.GET("")`. `path_of` rejects any literal of length ≤ 1, so `"/"` never becomes a route, not even under a prefix | Accept `"/"` and `""` as route patterns (the prefix completes them). Keep rejecting them as outbound calls | extractor (H2b, cheap) |
| `test-app-folder` | 20 | 0 | Framework test apps outside the test patterns: nest `integration/<x>/src`, fastify `integration/server.js`. `TEST_FILE` matches `/integration-tests/`, not `/integration/` | Decide in H2b whether `/integration/` joins `TEST_FILE` (risk: product code named so). Otherwise per-repo excludes in `atlas.yaml` | extractor or config |
| `library-code` | 13 | 0 | The library's own routers: chi `middleware/profiler.go` (mounted wherever the consumer chooses) | Not decidable from the code. Only appears when indexing a framework | limitation |
| `multi-app-repo` | 0 | 11 | Endpoint identity is `svc/<repo>/http/<METHOD> <path_key>`: the same route in two apps of one repo becomes one endpoint carrying the first app's evidence and handler | Endpoint identity per deployable (project/module), not per repo. Monorepos (eShop has five APIs) need it too | model (F1) |
| `route-by-name-convention` | 2 | 10 | Routes derived from names at runtime: CleanArchitecture `MapGroup($"/api/{type.Name}")` + `groupBuilder.MapPost(handler, "pattern")`; MVC conventional routing (`{controller}/{action}`) turning `[HttpGet]` into `GET /` | A convention (`route_patterns`, ADR-003) for the project wrapper. Do not emit `/` for template-less actions on a controller with no `[Route]` | convention + extractor (the FP) |
| `generated-server` | 0 | 9 | go-swagger server mounted with `mux.Handle("/api/v2/", handler)`. The routes exist only in the spec and in generated code | The committed spec as a route source | F2.1 (OpenAPI connector) |
| `route-constraint-syntax` | 0 | 9 | `{name:minlength(1)}`, `{brandId?}`, `{id:int?}`, Flask `<int:id>`, `<any(a, b):js>`. `PATH_LITERAL` rejects `<>()?+`, so the whole route is lost | Accept these characters inside a placeholder and normalize them to `{name}` | extractor (H2b, cheap) |
| `prefix-other-scope` | 6 | 7 | Prefix in an enclosing scope of the same file: chi `r.Route("/articles", func(r) {...})`, fastify `register(fn, { prefix: '/english' })`, a router returned by a local function and mounted | Same mount graph, starting with the same-file cases | extractor (H2b) |
| `no-leading-slash` | 0 | 6 | `apiV1.GET("users")`, `authorized.POST("admin")`, `api.MapGet("{orderId:int}")`. Route literals must start with `/` | Accept a relative pattern when the call is a route registration (registrar + handler-like argument) | extractor (H2b, cheap) |
| `prefix-as-param` | 2 | 0 | Prefix passed as a string parameter: express `app.resource(path, obj)` → `this.get(path + '/:id')` | Mount graph with string parameters. Rare, low priority | extractor (later) |
| `global-prefix` | 0 | 1 | nest `app.setGlobalPrefix('api')` | Part of the mount graph: an app-wide prefix | extractor (H2b) |
| `optional-segment-syntax` | 1 | 0 | Express 5 optional groups `{:query}`, `{.:format}` normalized into broken templates | Drop optional groups to the required form (or emit both) | extractor (cheap) |

Also seen outside any scope: `r.Del(...)` (Prometheus `route`) is not a known verb (`verb-alias`), and
`MapMethods("/check", [HttpMethods.Options])` comes out as ANY because the C# collection expression is not
read.

### Outbound calls

| Category | Wrong | Missed | What it is | What it would take | Goes to |
|---|---|---|---|---|---|
| `url-object-builder` | 0 | 7 | The path is appended to a `net/url` value (`u.Path += "v2/alerts"`, `APIURL.JoinPath("api/v1/chat.postMessage")`) and the call sends `u.String()` later | Follow `.Path +=`, `JoinPath` and `ResolveReference` on a local URL value up to the call | extractor (Go) |
| `client-wrapper` | 0 | 6 | Calls through the project's own client (`_requestProvider.GetAsync(uri)`), with `UriHelper.CombineUri(base, $"{ApiUrlBase}/...")` | `client_patterns` in a convention (ADR-003). `CombineUri`-like helpers as path joins | convention |
| `field-in-interpolation` | 3 | 3 | `$"{remoteServiceBaseUrl}items/{id}"` where the field holds `"api/catalog/"`. The field is treated as a base-URL placeholder and dropped | Resolve class fields/constants inside interpolations as `path_of` already does for locals | extractor (H2b) |
| `test-client-in-source` | 4 | 0 | `TestClient(app).get("/items/foo")` inside test functions of tutorial files, outside test folders | Ignore `TestClient`/`supertest`-style receivers wherever they appear (TS already filters supertest) | extractor (cheap) |
| `query-in-template` | 0 | 2 | `$"{base}items/{id}?api-version=2.0"`: the literal query makes the template rejected before the query is stripped | Strip the query string before validating the literal | extractor (H2b, cheap) |
| `method-default` | 1 | 0 | `fetch(url)` without options comes out as ANY instead of GET | `fetch` with no `method` option = GET | extractor (cheap) |
| `url-from-helper` | 0 | 1 | URL returned by a private helper (`GetAllCatalogItemsUri(...)`) | Follow a same-class static helper's return value. Low priority | extractor (later) |
| `url-transform-call` | 0 | 1 | `.TrimEnd('&', '?')` applied to an interpolation | Let `path_of` see through string transforms on templates | extractor (cheap) |

Calls are thin in this corpus (24 extracted, 27 expected in scope). H2b needs repositories with real
service-to-service clients before any call figure means much.

## Two open decisions, measured

- **Generated clients (H2-D9).** Two in the corpus: the openapi-ts client of `fastapi-template`
  (`frontend/src/client/sdk.gen.ts`, 23 operations) and alertmanager's go-swagger client (`api/v2/client`,
  9 operations). **None of the 32 is extracted.** `.gen.ts` is not in `GENERATED_SUFFIXES`, so the file is
  scanned. It is missed because the call is `(options.client ?? client).post({ url: '/api/v1/login/access-token' })`:
  the receiver is a parenthesized expression and the path is the `url` property of an options object. The
  literal is exact and the edge it gives (frontend → backend) is real, so the recommendation is to extract
  them, as `HttpCall` with `via: generated-client`.
- **Inherited `[Route]` (H2-D10).** Zero occurrences: no C# repository of v1 uses attribute routing with
  `[Route]` at all. Undecided until H2b brings controller-based services (eShopOnWeb and similar).

## What H2b should do, in order

1. **Cheap, general fixes**, each with a fixture and a corpus diff:
   - accept `"/"`/`""` as route patterns (`root-route-dropped`, 35 misses);
   - accept constraint/converter syntax inside placeholders (`route-constraint-syntax`, 9);
   - accept relative patterns on route registrations (`no-leading-slash`, 6);
   - strip the query before validating a call template (`query-in-template`);
   - `fetch` defaults to GET (`method-default`);
   - ignore `TestClient`-style receivers (`test-client-in-source`).
2. **The mount graph** (`prefix-other-file`, `router-as-param`, `prefix-other-scope`, `global-prefix`: 132 wrong
   + missed). Same-file closures and `Group`/`register` options first, then cross-file mounts through imports
   and settings constants. This is the handoff's "prefix linking" step. It changes node semantics, so it
   bumps `INDEXER_VERSION`.
3. **Field and constant resolution in call templates** (`field-in-interpolation`), and `url-object-builder` for Go.
4. Decide `test-app-folder` (`/integration/` in `TEST_FILE` or config) with H2b's product repositories in view.

Outside the extractor: `multi-app-repo` (endpoint identity per deployable) → F1. `generated-server` (spec as a
route source) → F2.1. `route-by-name-convention` and `client-wrapper` → conventions (ADR-003). Base URLs from
config → linker (F0.5).
