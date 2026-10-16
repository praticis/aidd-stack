# HTTP extractor — corpus report

Precision and recall of the HTTP integration extractor (`core/integrations.py` + `languages/<lang>/http.py`)
on the public calibration corpus. v1 (F0.4.3a, handoff H2a) measured the 15 repositories the extractor was
calibrated on, pinned to fixed commits and measured against an expected list per repository. The two
"Update" sections record the cheap fixes that followed. **v2** (the last part of this report) widens the corpus
to 39 repositories, most of them real applications, and resets the order of H2b (F0.4.3b). Plan, decisions and
status are in `docs/handoffs/H2-roadmap.md`.

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

## Update: the cheap fixes (2026-10-15)

The first H2b step. It covers the three cheap, high-yield categories, plus two found while doing them. Each
case is reproduced in the fixtures `route-patterns-{go,ts,py,cs}`, together with the counter-examples that must
not become routes.

- **Root routes** (`root-route-dropped`): `"/"` and `""` become a route only when the full path is known. That
  is the case when the receiver is the application itself or a group with a prefix of its own. The root of a
  sub-router is wherever it gets mounted, so it stays out.
- **Constraints and converters** (`route-constraint-syntax`): placeholders are masked before the literal check,
  and an optional `?` is removed before the query is cut. That cut also fixed `{id:int?}` → `{id{int}`.
- **Relative patterns on a group** (`no-leading-slash`): only where the framework joins them (Go groups,
  ASP.NET `MapGroup`).
- **A router named like a client** (new, `client-named-router`): `api := r.Group("/api")` and
  `const api = express.Router()` were rejected because `api` matched the client-name heuristic.
- **Conventional routing** (the `route-by-name-convention` false positive): a template-less action of a
  controller without `[Route]` is no longer recorded as `GET /`.

Every change was judged against the baseline diff:

- **74 routes added.** 68 are correct. The other 6 are wrong for the reason their sibling routes already were:
  the prefix is lost in another scope or file (`/{articleSlug}` inside a chi `r.Route` closure, the four
  router roots of `fastapi-template` without `/api/v1`, a gin group received as a parameter).
- **2 routes removed.** Both were false positives (`AccountController`).

| Language | P expected v1 → now | R expected v1 → now |
|---|---|---|
| Go | 17.4 % → 32.3 % (10/31) | 6.1 % → 15.2 % (10/66) |
| TS/JS | 9.1 % → 13.0 % (3/23) | 5.9 % → 8.8 % (3/34) |
| C# | 100 % → 100 % (27/27) | 48.6 % → 73.0 % (27/37) |
| Python | 44.1 % → 47.7 % (21/44) | 30.6 % → 42.9 % (21/49) |

- eShop routes reach P 100 % / R 100 % on the measured APIs (27/27), and flask reaches 100 % / 100 % (18/18).
- gin-examples goes from P 33 % / R 8 % to P 70 % / R 58 %.
- One repository lost precision against its expected list: chi, 16.7 % → 14.3 %. The cause is a regex route
  inside an `r.Route("/articles", ...)` closure, extracted exactly as written and missing its closure prefix.
- `root-route-dropped`, `route-constraint-syntax` and `no-leading-slash` no longer appear. What they hid is now
  counted where it belongs (`prefix-other-file`, `prefix-other-scope`, `router-as-param`, `multi-app-repo`), plus
  a new `app-not-recognized`: `require('fastify')()` is not recognized as the application, so its root stays out.

The tables above this section are v1 (2026-10-14) and are kept as they were. Run `--expected` for the current
figures.

## Update: the remaining cheap fixes (2026-10-15, second round)

This closes item 1 of the H2b order: the five smaller categories, plus one found on the way. Each case is in
the `route-patterns-*` fixtures, next to its counter-example (`fetch` with a `method` that cannot be read stays
ANY; a real `httpx.get` next to a `TestClient` stays a call).

- `query-in-template`: the template is validated without its query string.
- `method-default`: `fetch(url)` with no `method` key is a GET.
- `test-client-in-source`: names bound to `TestClient(...)` or `app.test_client()` make no outbound calls.
- `optional-segment-syntax`: Express 5 optional groups (`{:q}`, `{.:ext}`) normalize to their parameter.
- `verb-alias`: `Del` is DELETE.
- **New, `nested-generic-callee`:** `GetFromJsonAsync<List<T>>(...)` lost the call entirely, because only the
  innermost type argument was stripped from the callee. It also hid a call from the v1 expected list, which was
  built with a grep that had the same blind spot. `GET /api/webhooks` was added there.

Diff against the 2026-10-15 baseline, every item judged:

- 4 false-positive calls removed (TestClient).
- 1 call method corrected (ANY → GET).
- 3 routes normalized correctly.
- 1 route added: `DELETE /silence/{sid}`. It is right but lacks `/api/v1`, like its siblings (router-as-param).
- 10 eShop calls added. Two are right (`GET /api/webhooks`, plus the method fix above). The catalog calls of
  WebAppComponents and HybridApp have the right path but lack the `api/catalog/` prefix that the client class
  keeps in a field interpolated into the URL. That is `field-in-interpolation`, the defect their already-judged
  siblings have.

This is why the precision of C# calls against the expected list drops from 50 % to 40 % (4/10) while their
recall goes from 18.8 % to 23.5 % (4/17). Under H2-D14 that does not block the rule: the rule now extracts what
is written. `field-in-interpolation` (6 missed) and `url-object-builder` (7) are now the main gaps on calls.
Sampled precision of calls: Go 5/5, Python 7/7.

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

## What H2b should do, in order (v1; revised by v2 below)

1. **Cheap, general fixes**, each with a fixture and a corpus diff. Done on 2026-10-15, in two rounds (see the
   updates above):
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

## v2: the widened corpus (2026-10-15)

H2b, phase 3. 24 repositories were added, 39 in all, chosen to bring what v1 lacked: real applications and
company-style services next to the examples, a large monolith per language, and committed specs where possible.
The extractor did not change for v2. The 15 v1 repositories come out identical (ids and handlers) to the
baseline of the second round of cheap fixes, so every v2 figure is about the new code, not about a new rule. Baseline:
`~/.cache/aidd-corpus/runs/2026-10-15-v2-baseline/`.

| Repo | Lang | What it brings | Expected list |
|---|---|---|---|
| gitea | Go | monolith; chi-style `m.Group("/x", func() {...})` closures, `m.Combo` chains | OpenAPI `/api/v1` (537 operations); browser calls |
| mattermost | Go | large service; gorilla subrouters kept in struct fields | OpenAPI fragments `/api/v4` (608) |
| kratos | Go | identity service; httprouter behind router types (`RouterAdmin`) | OpenAPI + routes verified in code; OIDC provider calls |
| argo-cd | Go | grpc-gateway API plus hand-written net/http | OpenAPI + `server/` routes; five UI service files |
| gotify | Go | gin service with a React UI | OpenAPI + code-only routes; every UI call |
| go-feature-flag | Go | echo relay proxy | swagger + editor API; Python provider, Bitbucket retriever |
| go-kit-examples | Go | go-kit services and clients | every app, by hand |
| immich | TS | NestJS server of a large product | OpenAPI `/api` (279) |
| NodeBB | JS | Express monolith with its own registration helpers | OpenAPI read + write (378, multi-file); two admin files |
| Ghost | JS | Express monolith (`lazyUse`) | the Admin and Content API route files (256) |
| express-boilerplate | JS | routers mounted from a table | the whole API |
| fastify-demo | TS | Fastify official demo, `@fastify/autoload` | the whole app |
| hono-examples | TS | Hono apps | every example app |
| taxonomy | TS | Next.js App Router (`app/api/**/route.ts`) and its UI | the whole app, routes and calls |
| eShopOnWeb | C# | MVC controllers, minimal-API endpoints, Blazor client | the whole solution |
| eShopSupport | C# | minimal APIs and typed HttpClients between services | the whole solution |
| ardalis/CleanArchitecture | C# | FastEndpoints | the template's three apps |
| jellyfin | C# | large controller-based API | three controllers; SchedulesDirect client |
| bitwarden/server | C# | company service, several apps | three controllers; Slack and Teams clients |
| zulip | Python | Django monolith | OpenAPI `/api/v1` (164); three web files |
| netbox | Python | Django REST Framework | OpenAPI (1256) |
| dispatch | Python | FastAPI with `include_router(prefix=)` across files, Vue UI | OpenAPI (207); one UI API module |
| aiohttp-demos | Python | aiohttp apps | every demo |
| CTFd | Python | Flask blueprints and flask-restx | the challenges API and the auth blueprint |

**grafana** was a candidate (closures, committed spec) and is out: extracting the whole repository (24k files)
is killed for memory at 7.7 GB under Docker Desktop. That is a finding about the indexer, not the corpus: today a
repository is held in memory whole while it is extracted, and a product monorepo of that size would not index on
a developer machine. hashicorp/vault was left out for its license (BUSL); its MPL fork has no committed spec.

### How v2 was measured

Same rules as v1, plus three decisions recorded in the roadmap:

- **H2-D15:** with a spec, the expected list is the spec plus routes verified in the code. A route found while
  checking an extracted item (UI files, redirect twins, health) is added, and a route only the spec has (no
  registration in the code) is removed. Otherwise precision against the list punishes right routes.
- **H2-D16:** an item that needs more than one fix gets one category: the most specific one besides the mount
  graph. Examples: `m.Combo("/x").Get(h)` inside a closure is `route-chain`; a closure route whose router is
  mounted in another file is `prefix-scope-and-file`. The mount graph shows up nearly everywhere and would hide
  the rest.
- **H2-D17:** a sampled item counts for the language of its own file (a Go server's React UI pools as TS/JS),
  and a list can declare `language` per kind. Each category also reports the number of repositories it appears
  in, so that one large repository (netbox, 1256 operations) cannot rank a category alone. With this rule, three
  v1 calls move from Go to TS/JS (fiber-recipes' SvelteKit client).

Tooling added on the way: `from-openapi` follows path items that are `$ref` to other files (NodeBB), and
`--reuse <run>` scores a saved run without extracting it again. It is used only to edit lists, never to measure
an extractor change.

### Results by language (v2, 38 repositories with an expected list)

| Language | Kind | P checked | P expected | R expected |
|---|---|---|---|---|
| Go | routes | 59.6 % (136/228) | 19.2 % (132/686) | 9.0 % (134/1495) |
| Go | calls | 75.0 % (15/20) | 100 % (9/9) | 25.0 % (9/36) |
| TS/JS | routes | 27.8 % (47/169) | 3.1 % (20/640) | 2.0 % (20/1015) |
| TS/JS | calls | 57.6 % (87/151) | 44.6 % (25/56) | 23.1 % (25/108) |
| C# | routes | 90.4 % (85/94) | 94.6 % (105/111) | 72.9 % (105/144) |
| C# | calls | 72.2 % (39/54) | 62.2 % (28/45) | 48.3 % (28/58) |
| Python | routes | 49.5 % (45/91) | 26.8 % (37/138) | 2.1 % (37/1731) |
| Python | calls | 60.6 % (20/33) | 100 % (2/2) | 66.7 % (2/3) |

The 24 new repositories alone, which is what a product portfolio looks like:

| Language | Routes: P checked · R expected | Calls: P checked · R expected |
|---|---|---|
| Go | 58.9 % (76/129) · 8.7 % (124/1429) | 73.7 % (14/19) · 20.0 % (5/25) |
| TS/JS | 23.1 % (24/104) · 1.7 % (17/981) | 55.9 % (81/145) · 23.1 % (25/108) |
| C# | 88.2 % (67/76) · 72.9 % (78/107) | 75.0 % (36/48) · 58.5 % (24/41) |
| Python | 32.5 % (13/40) · 1.0 % (16/1682) | 50.0 % (13/26) · 66.7 % (2/3) |

What this says:

- **Route recall falls apart in real applications, except in C#.** v1's examples registered routes next to their
  prefix. Real apps register them away from it, so the prefix is lost (mount graph), or through structures no
  scanner reads (Django urlconf, project helpers, route chains). Recall against the lists: Go 8.7 %, TS/JS
  1.7 %, Python 1.0 %.
- **C# holds up.** Attribute routes and minimal APIs carry the full path at the registration. bitwarden and
  eShopSupport reach 100 % / 100 %, eShopOnWeb 100 % / 97 %. The C# gaps are specific: `[Route]` inherited from a
  base controller (jellyfin, H2-D10) and endpoint classes (FastEndpoints, ApiEndpoints).
- **Calls do better than routes, and their errors are a lost prefix too.** Sampled precision is 56–75 %. Most
  wrong calls lost a base path the code holds: the API client prepends `/api/v1` (`prefix-in-client-wrapper`,
  3 repositories), or a module constant sits in the template (`field-in-interpolation`, 4 repositories).
- **The browser side brings new false positives.** jQuery `$.get(url, callback)` taken for a route, committed
  minified bundles, and variables resolved from another function.

| Repo | Routes | Calls | P routes checked | P / R routes expected | P calls checked | P / R calls expected |
|---|---|---|---|---|---|---|
| gitea | 533 | 6 | 0 % (0/20) | 0 % / 0 % | 50 % (3/6) | — / 0 % (0/15) |
| mattermost | 446 | 41 | 5 % (1/20) | 0.3 % / 0.2 % | 75 % (15/20) | — |
| kratos | 66 | 6 | 65 % (13/20) | 70.0 % / 54.5 % | 100 % (6/6) | 100 % / 35.7 % |
| argo-cd | 16 | 27 | 68.8 % (11/16) | 42.9 % / 2.7 % | 10 % (2/20) | 0 % / 0 % |
| gotify | 46 | 18 | 95 % (19/20) | 100 % / 92.2 % | 100 % (18/18) | 100 % / 66.7 % |
| go-feature-flag | 18 | 4 | 100 % (18/18) | 100 % / 94.4 % | 50 % (2/4) | 100 % / 66.7 % |
| go-kit-examples | 17 | 0 | 82.4 % (14/17) | 82.4 % / 51.9 % | — | — / 0 % (0/11) |
| immich | 295 | 6 | 0 % (0/20) | 0 % / 0 % | 100 % (6/6) | — |
| NodeBB | 96 | 129 | 45 % (9/20) | 0 % / 0 % | 10 % (2/20) | 0 % / 0 % |
| Ghost | 309 | 29 | 0 % (0/20) | 0 % / 0 % | 80 % (16/20) | — |
| express-boilerplate | 8 | 0 | 0 % (0/8) | 0 % / 0 % | — | — |
| fastify-demo | 10 | 0 | 0 % (0/10) | 0 % / 0 % | — | — |
| hono-examples | 24 | 0 | 75 % (15/20) | 70.8 % / 54.8 % | — | — |
| taxonomy | 0 | 6 | — | — / 0 % (0/9) | 100 % (6/6) | 100 % / 100 % |
| eShopOnWeb | 32 | 0 | 100 % (20/20) | 100 % / 97.0 % | — | — / 0 % (0/6) |
| eShopSupport | 18 | 19 | 100 % (18/18) | 100 % / 100 % | 94.7 % (18/19) | 94.4 % / 94.4 % |
| ardalis/CleanArchitecture | 0 | 0 | — | — / 0 % (0/19) | — | — |
| jellyfin | 388 | 14 | 55 % (11/20) | 33.3 % / 25.0 % | 21.4 % (3/14) | 0 % / 0 % |
| bitwarden | 671 | 27 | 100 % (20/20) | 100 % / 100 % | 100 % (20/20) | 100 % / 87.5 % |
| zulip | 2 | 17 | 0 % (0/2) | — / 0 % (0/164) | 23.5 % (4/17) | — / 0 % (0/7) |
| netbox | 0 | 0 | — | — / 0 % (0/1256) | — | — |
| dispatch | 68 | 67 | 0 % (0/20) | 1.5 % / 0.5 % | 10 % (2/20) | 0 % / 0 % |
| aiohttp-demos | 0 | 2 | — | — / 0 % (0/23) | 100 % (2/2) | 100 % / 50 % |
| CTFd | 129 | 103 | 55 % (11/20) | 57.7 % / 46.9 % | 95 % (19/20) | — |

The `notes` field of each expected list explains its choices and its misses in prose.

### Gaps by category (v2)

*Wrong* = sampled items judged wrong. *Missed* = distinct expected pairs not extracted. *Repos* = repositories
where the category appears. Rows marked FP are precision errors, which come first under H2-D11. Categories
already described in v1 keep their v1 description.

**Routes**

| Category | Wrong | Missed | Repos | What it is | Goes to |
|---|---|---|---|---|---|
| `django-urlconf` | 0 | 1420 | 2 | zulip `rest_path("realm", PATCH=h)` in `urls.py`; netbox DRF `router.register('regions', ViewSet)` + `include()` | new scanner (Django + DRF) |
| `prefix-other-file` | 107 | 1154 | 12 | v1. Now also Ghost `lazyUse(BASE_API_PATH, ...)`, mattermost subrouters in struct fields, dispatch `include_router(prefix=)` | mount graph |
| `custom-registrar` | 0 | 356 | 2 | The project's own helper: NodeBB `setupApiRoute(router, 'post', '/x', mws, h)`, `setupPageRoute`; gitea `g.MatchPath(...)` | convention (`route_patterns.registrars`) |
| `global-prefix` | 18 | 238 | 2 | nest `app.setGlobalPrefix('api')` (immich) | mount graph |
| `prefix-scope-and-file` | 9 | 233 | 1 | gitea: routes inside `m.Group("/x", func() {...})` closures, router mounted at `/api/v1` in another file | mount graph (closures, then the mount) |
| `route-chain` | 0 | 221 | 3 | Path on a builder, verbs chained: gitea `m.Combo("/x").Get(h).Put(h)`, gorilla `r.Methods("POST").Path("/x").Handler(h)`, express `router.route('/x').get(h).post(h)` | extractor |
| `router-as-param` | 23 | 102 | 5 | v1. Now also helper funcs called inside groups (gitea `addProjectRoutes(m, ...)`) and plugin routers | mount graph |
| `generated-server` | 0 | 115 | 2 | v1. Now also grpc-gateway (argo-cd `*.pb.gw.go` under `mux.Handle("/api/", gw)`) | F2.1 (spec as source) |
| `const-other-file` | 2 | 42 | 1 | `@Controller(RouteKey.Asset)`, the enum in another file (immich) | mount graph (constants) |
| `prefix-other-scope` | 15 | 13 | 3 | v1 | mount graph |
| `const-concat` | 5 | 22 | 1 | `RouteItem = RouteCollection + "/{id}"` keeps only `/{id}` (kratos). A defect: a constant built from another constant is not followed | extractor (cheap) |
| `prefix-as-param` | 11 | 15 | 3 | v1. Now also ``router.get(`/api/${name}/config`)`` (NodeBB), `registerDownloadHandlers(mux, base)` (argo-cd) | mount graph (string params) |
| `prefix-by-folder` | 10 | 14 | 1 | `@fastify/autoload`: `routes/api/tasks/index.ts` serves `/api/tasks` | extractor or convention |
| `restx-resource` | 7 | 17 | 1 | flask-restx: `@ns.route("/x")` on a `Resource` whose methods are `def get/post`, `add_namespace(ns, "/challenges")` (CTFd) | extractor (Python) |
| `aiohttp-router` | 0 | 23 | 1 | `app.router.add_get('/x', h)`, `add_route('GET', '/', h)` | extractor (cheap) |
| `test-app-folder` | 23 | 0 | 4 | v1. Now also `pkg/testhelpers` (kratos) and the Cypress webhook server (mattermost) | decide (config or `TEST_FILE`) |
| `endpoint-class` | 0 | 20 | 2 | FastEndpoints `Configure() { Get("/x"); }`; ApiEndpoints `[HttpPost("api/x")]` on a non-Controller class | extractor (C#) |
| `mount-same-scope` | 4 | 16 | 2 | Mount next to the routes: NodeBB `const router = express.Router(); app.use('/api', router)`; Hono `app.route('/book', book)`, `.basePath('/api')` | mount graph, first case |
| `inherited-route-attr` | 9 | 9 | 1 | `[Route("[controller]")]` on the base controller (jellyfin). See H2-D10 below | extractor (C#) |
| `multi-app-repo` | 0 | 14 | 6 | v1 | model (F1) |
| `library-code` | 13 | 0 | 1 | v1 | limitation |
| `prefix-in-router-type` | 1 | 10 | 1 | kratos `RegisterAdminRoutes(admin *httprouterx.RouterAdmin)`: the type prepends `/admin` | convention or mount graph |
| `route-by-name-convention` | 0 | 10 | 1 | v1 | convention |
| `route-by-file-path` | 0 | 9 | 1 | Next.js `app/api/posts/[postId]/route.ts` exporting `GET`/`PATCH` (taxonomy) | new scanner (file convention) |
| `mount-as-route` (FP) | 5 | 0 | 2 | `mux.Handle("/booking/v1/", sub)`, `mux.Handle("/api/", gw)`: a subtree mount becomes `ANY /booking/v1` | extractor (cheap) |
| `call-taken-for-route` (FP) | 4 | 0 | 2 | jQuery `$.get(url, callback)` in browser code (NodeBB, zulip) | extractor (cheap) |
| `build-artifact` (FP) | 2 | 0 | 1 | Committed minified bundles (`themes/*/static/assets/*.js`, CTFd) | extractor or config (cheap) |
| `client-named-router`, `app-not-recognized`, `no-leading-slash`, `route-constraint-syntax` | 1 | 9 | — | v1 categories, new instances: Hono's `api = new Hono()`, `new Hono()` as the app, gin `g.GET("version")` on the engine, Hono `/:id{[0-9]+}` | extractor (cheap) |
| `const-in-format`, `default-mux-function`, `group-chain`, `library-registrar`, `route-in-loop` | 0 | 7 | — | `Sprintf("/%s/{id}", Const)`; `http.Handle("/x", h)`; `g.Group("/user").Use(mw).POST("", h)`; `pprof.Register(e)`; `Handle(m+" "+Route)` in a loop | extractor (cheap) / limitation |

**Outbound calls**

| Category | Wrong | Missed | Repos | What it is | Goes to |
|---|---|---|---|---|---|
| `prefix-in-client-wrapper` | 38 | 21 | 3 | The project's API client prepends a base path the code holds: argo-cd `requests.get('/x')` → `/api/v1/x`, NodeBB `api.put(...)` → `/api/v3/...`, mattermost `${Client4.getBaseRoute()}/...` | convention (`client_patterns` with a base) |
| `field-in-interpolation` | 26 | 23 | 4 | v1, now in TS too: `` API.post(`/${resource}/${id}/join`) `` with `const resource = "cases"` (dispatch), C# `const` in `$"..."` | extractor |
| `client-wrapper` | 0 | 27 | 4 | v1. Verb-named wrappers `GET(url)` (gitea), `HttpService.HttpGet<T>("x")` (eShopOnWeb), `CallHTTPAPI(ctx, url, method)` | convention |
| `const-base-url` | 10 | 9 | 1 | `ApiUrl = "https://host/20141201"`: the base constant holds part of the path, dropped with the host (jellyfin) | extractor (cheap) |
| `url-object-builder` | 3 | 16 | 7 | v1, now in every language: Go `u.Path = path.Join(...)`, `url.JoinPath(base, "x")`; Python `urljoin`, yarl `URL / part`; C# `UriBuilder` | extractor |
| `multiline-receiver` | 0 | 11 | 1 | `requests` on one line and `.put('/x')` on the next: the call is lost (argo-cd). A defect | extractor (cheap) |
| `request-config-object` | 0 | 9 | 3 | URL and method in an options object: `axios.create().request({url, method})`, zulip `channel.post({url: "/json/bots"})`, `$.ajax(url, {...})` | extractor |
| `request-encoder` | 0 | 9 | 1 | go-kit: `NewClient("GET", tgt, enc, dec)` with the path set in `enc` | convention |
| `test-client-in-source` | 9 | 0 | 1 | v1, now Django's test `Client()` driven by a development view (zulip) | extractor (extend the rule) |
| `mime-like-head` | 0 | 8 | 1 | `` axios.delete(`${url}application/${id}`) ``, `'message'`: a first segment named like a MIME type is rejected (gotify) | extractor (cheap) |
| `route-taken-for-call` (FP) | 3 | 0 | 1 | `routes.Get("/metrics", append(mid, h)...)`: a route with a spread handler becomes a call (gitea) | extractor (cheap) |
| `variable-other-scope` (FP) | 3 | 0 | 2 | `fetch(url)` / `SendAsync(message)` where the name is a parameter, resolved to a same-named variable of another function (zulip TS, jellyfin C#). A defect | extractor (cheap) |
| `method-keyword`, `method-variable` | 3 | 0 | 2 | `request(method="POST", url=...)`; `let method = "PATCH"; fetch(url, {method})` → ANY | extractor (cheap) |
| `url-in-field`, `url-in-var`, `url-from-helper`, `verb-alias`, `non-http-verb` (FP), `single-segment-relative` | 2 | 8 | — | URL in a struct field or package var; `api.del()`; a cache `Get(key)`; `GetFromJsonAsync("User")` | extractor |

### The two open decisions, with v2 numbers

- **Generated clients (H2-D9).** 371 operations in four generated clients, none extracted: immich's oazapfts SDK
  (279, ``oazapfts.fetchJson(`/activities${QS.query(...)}`, {...opts})``), kratos' openapi-generator Go client
  (60, `localVarPath := localBasePath + "/self-service/..."`), and v1's two (32). In immich it is the only path
  from the web app to the server. Recommendation unchanged: extract them as `HttpCall` with `via: generated-client`.
- **Inherited `[Route]` (H2-D10).** jellyfin: 26 of 60 controllers declare no `[Route]` and inherit
  `[Route("[controller]")]` from `BaseJellyfinApiController`. Their 128 extracted routes all lack
  `/{Controller}`, and their template-less actions are dropped. eShopOnWeb has a `BaseApiController` with
  `[Route]` that nothing derives from. Recommendation: follow one level of base class for `[Route]` (base classes
  in the same project, found by name), with a fixture of both cases.
- **Decided 2026-10-15:** both recommendations accepted. Generated clients become their own H2b item, and
  `[Route]` inheritance joins the C# item (one level; an ambiguous base name inherits nothing).

### What H2b should do, in order (v2)

1. **The mount graph.** Confirmed as the first item, now by breadth: its categories (`prefix-other-file`,
   `router-as-param`, `prefix-other-scope`, `prefix-scope-and-file`, `global-prefix`, `mount-same-scope`,
   `const-other-file`, `prefix-as-param`, `prefix-in-router-type`, `prefix-by-folder`) appear in 23 of the 38
   repositories with a list: 200 wrong, 1837 missed. Order inside it:
   - same scope: `app.use('/api', router)` next to the routes, Hono `route`/`basePath`;
   - same file: closures `r.Route`/`m.Group(..., func)`;
   - app-wide: `setGlobalPrefix`;
   - across files: imports, constants and enums, struct fields, helper functions called inside groups.
2. **Cheap defects v2 exposed.** Precision first: `variable-other-scope`, `call-taken-for-route`,
   `mount-as-route`, `route-taken-for-call`, `build-artifact`, `non-http-verb`. Then recall: `const-concat`,
   `multiline-receiver`, `mime-like-head`, `const-base-url`, `method-keyword`/`method-variable`, `verb-alias`
   (`del`), `default-mux-function`, `group-chain`, `aiohttp-router`. Each with a fixture and a corpus diff, like
   item 1 of v1.
3. **Route chains** (`route-chain`: gitea `Combo`, gorilla builders, express `route()`).
4. **Calls:** `field-in-interpolation` (constants and fields in templates, TS and C#), `url-object-builder` in
   all languages, `request-config-object`.
5. **C#:** `[Route]` inheritance (if H2-D10 is accepted) and endpoint classes (FastEndpoints, ApiEndpoints).
6. **Scanners for what is not read at all**, each its own piece of work and best done when a portfolio needs it:
   - Django + DRF: the largest single gap, 1420 misses in 2 repositories;
   - Next.js file routes;
   - flask-restx;
   - generated clients (H2-D9).
7. **Decide `test-app-folder`**, now in four repositories (nest, fastify, kratos `pkg/testhelpers`, mattermost
   e2e): per-repo excludes in `atlas.yaml` are the safer answer.

Outside the extractor:

- **Conventions (ADR-003):** `custom-registrar` (NodeBB, gitea), `prefix-in-client-wrapper` and
  `client-wrapper`, `request-encoder`.
- **Elsewhere:** `generated-server` → F2.1. `multi-app-repo` → F1. Memory on large repositories (grafana) → F1.13
  (scale of the extraction: release trees early, batch by module, per-repo scoping), which F1.4's incremental
  indexing builds on.

## Update: the cheap defects of v2 (2026-10-15)

Item 2 of the v2 order, done before the mount graph: the fifteen cheap categories v2 exposed, plus three defects
found while judging the diff. Each case is in the `route-patterns-{go,ts,py,cs}` fixtures, next to the
counter-example that must not change.

Precision:

- `variable-other-scope`: only module- and class-level constants count as constants of the directory. A name is
  looked up in the enclosing functions first, and a parameter ends the search. Before, `fetch(url)` with `url`
  a parameter took the value of a local `url` of another function (zulip, mattermost; jellyfin's
  `SendAsync(message)`).
- `call-taken-for-route`: a `$`/`jQuery` receiver is a client. `$.get`, `$.post` and `$.getJSON` are calls,
  never routes.
- `mount-as-route`: on a `ServeMux` (or the default mux), a `Handle` pattern ending in `/` is a subtree mount,
  not a route.
- `route-taken-for-call`: a spread handler argument (`append(mid, h)...`, `...handlers`) is unwrapped before
  deciding whether it is a handler.
- `build-artifact`: a committed bundle is left out of the HTTP extraction. That means a `.js` file with a hashed
  name and a line over 500 characters, or with a line over 2000 characters and more than 200 per line on
  average.
- `non-http-verb`: a path needs a segment with a letter or digit, so `root + "/" + v + "/" + strings.Join(xs,
  ",")` passed to a cache `Get` is no call.

Recall:

- `const-concat`: a constant built with `+` from other constants resolves on first use, across the files of
  the directory.
- `const-base-url`: a constant holding an absolute URL keeps its path (`/20141201`).
- `multiline-receiver`: whitespace is removed from the callee.
- `mime-like-head`: only a real MIME type (two tokens, no placeholder) is rejected, so `application/{id}` is a
  path. `base + 'message'` reads like the template `${base}message`.
- `method-keyword` and `method-variable`: the method comes from `method="POST"` and from a `method` key whose
  value is a local variable.
- `verb-alias`: `del` is DELETE in TS (`api.del`).
- `default-mux-function`: `http.Handle` and `http.HandleFunc` register routes.
- `group-chain`: the prefix is carried through `Group(...).Use(...)`.
- `aiohttp-router`: `app.router.add_get/add_post/add_route/add_view`, including the bound
  `add_route = app.router.add_route`.

Found on the way:

- **The name on the right is the earlier value.** In `` url = `${url}?notify=true` `` (CTFd) the call was lost
  once locals stopped leaking. A local variable inside a template is now resolved, as in a concatenation. A
  module constant inside a template is not: in alertmanager's generic `` `${pathPrefix}/${API_PATH}${path}` ``
  that would make a path out of a base. Constants inside templates stay with `field-in-interpolation`.
- **`x += e`.** It is the earlier value plus `e`, so path and method come from the same last assignments
  (CTFd: `target += "/" + id; method = "PATCH"` gives `PATCH /api/v1/pages/{id}`, not `PATCH /api/v1/pages`).
  When the base comes from a call, the appended part counts if it has a named segment: argo-cd's
  `urlStr += fmt.Sprintf("/repositories/%s/...")` does, chi's `path += "/"` onto a parameter does not.

Diff against `2026-10-15-v2-baseline`, every item judged:

- **Routes, 37 removed.** All of them are right to go:
  - 8 subtree mounts (alertmanager, argo-cd, go-kit);
  - 10 jQuery calls, which are now calls (CTFd, NodeBB, zulip);
  - 5 routes from CTFd bundles;
  - 13 kratos routes, replaced by their resolved paths;
  - 1 route whose evidence moved to another registration of the same route.
- **Routes, 49 added.**
  - aiohttp-demos: 24, all right (P/R 100 %).
  - gitea: 3, right (a spread handler list).
  - go-kit: 2, right (the default mux).
  - gotify: 1, right (a group chain).
  - argo-cd: 2 default-mux routes, right as written, plus the moved one.
  - kratos: 16. 9 are right. 7 lack `/admin`: the admin router type prepends it, or `AdminPrefix` comes from
    another package. That is the defect their siblings already have (H2-D14).
- **Calls, 54 removed:**
  - 28 from bundles;
  - 7 false positives (a parameter resolved to another function's variable, cache keys);
  - 3 gitea route registrations, now routes;
  - the rest replaced at the same line by a better path or method.
- **Calls, 186 added.**
  - 127 lack the wrapper prefix: argo-cd's 78 calls with the receiver on the line above and NodeBB's 49
    `api.del`. Their paths are as written, and like their already-judged siblings they lack the `/api/v1` or
    `/api/v3` that the project's request wrapper prepends (`prefix-in-client-wrapper`, H2-D14).
  - The other 59 are right as written:
    - gotify: 10;
    - jellyfin: 10, with `/20141201`;
    - CTFd, NodeBB and zulip: 15 `$.get`;
    - the rest: calls to external APIs through URL constants (GitHub, Opsgenie, HIBP, LinkedIn, Lark, two
      `raw.githubusercontent.com` fetches), methods read from variables, and NodeBB's `` `/api/${url}` ``.
  - Four `$.get` calls carry a runtime piece glued to a segment (`/json{param}/billing/...`, `/api{param}`).
    The code builds them that way (`runtime-url`, outside the metric).
  - eShopOnWeb's `ApiBase + "catalog-items"` lacks the `/api/` that comes from configuration, which belongs to
    the linker (H2-D12).

Gabaritos changed with what the judging showed:

- Six real calls were missing from two lists and were added:
  - gotify's `axios\n.delete(...)`, which the listing grep missed for the same reason the extractor did;
  - kratos' LinkedIn `/v2/me` and `/v2/emailAddress`.
- Items still missed for a different reason were re-categorized (`multiline-receiver` and `verb-alias` →
  `prefix-in-client-wrapper`, kratos `const-concat` → `prefix-in-router-type`).
- Sampled items that are no longer extracted left the samples.
- Sampled items extracted differently at the same line were judged again.
- alertmanager's `mux.Handle(prefix+"/api/v1/", ...)` had been judged right in v1, as a catch-all route. It is a
  mount under the v2 reading.

| Language | P expected before → now | R expected before → now | P sampled before → now |
|---|---|---|---|
| Go routes | 19.2 % → 21.1 % | 9.0 % → 9.8 % | 59.6 % → 62.1 % (136/219) |
| Go calls | 100 % → 100 % (12/12) | 23.7 % → 31.6 % | 75.0 % → 93.8 % (15/16) |
| TS/JS routes | 3.1 % → 3.1 % | 2.0 % → 2.0 % | 27.8 % → 28.8 % (47/163) |
| TS/JS calls | 44.6 % → 44.3 % | 22.5 % → 31.5 % | 57.6 % → 57.6 % (83/144) |
| C# calls | 62.2 % → 84.1 % | 48.3 % → 63.8 % | 72.2 % → 92.5 % (49/53) |
| Python routes | 26.8 % → 37.7 % | 2.1 % → 3.5 % | 49.5 % → 49.5 % (45/91) |

C# routes and Python calls did not change. The "before" columns of the expected lists are the old baseline
scored against the final lists, so the six added calls count on both sides. A sampled "before" counts the
sample as it was, including the items that left it.

- None of the fifteen categories is left in the ranking.
- TS/JS call precision against the lists moves by one item. The 78 + 49 new calls of argo-cd and NodeBB are
  scored against lists that hold the prefixed paths.
- Per repository, nothing lost precision except those two, under H2-D14:
  - jellyfin calls: 0 % → 100 %/100 %;
  - kratos routes: P 70 → 82.5 %, R 54.5 → 67.5 %;
  - go-kit routes: P 82 → 100 %;
  - gotify calls: R 60 → 93 %;
  - aiohttp-demos: 0 → 100 %/100 %.
- One item is left from these categories: gotify's `axios.put(url, app)`, recorded as `data-taken-for-handler`.
  A variable named `app` as the second argument looks like a handler; it is one call in one repository.

New baseline: `2026-10-15-v2-baseline-2`.

## Update: the mount graph, step 1 — inside a file (2026-10-15)

The first step of the mount graph covers everything a single file says about where its routes live. Nothing
here holds trees of other files, which is the constraint F1.13 (large repositories) puts on the next steps.

- **Closure regions.** A registration made inside a closure that a router call scopes takes that call's prefix,
  and nested regions add up. The calls are:
  - chi/fiber `r.Route("/x", func(r chi.Router) {...})`;
  - chi `r.Group(func(r) {...})`, which adds no prefix;
  - gitea's `m.Group("/x", func() { m.Get(...) })`, where the closure registers on the same router;
  - fastify `register(fn, { prefix })`.
- **Mounts in the same file.** These record an edge between two routers:
  - express `app.use('/api', router)`;
  - Hono `app.route('/book', book)` and `basePath('/api')`;
  - chi `r.Mount("/admin", sub)`, including a router that a function of the file returns;
  - `include_router(router, prefix=)` and `register_blueprint(bp, url_prefix=)`.

  A router is identified by the scope that binds its name and the name, so a closure's `r` is not the outer
  `r`. At the end of the file, every route registered on a router gets every chain of mounts above it.
  chi's `articleRouter()`, mounted under `/v1`, `/v2` and `/v3`, gives three routes.
- **A sub-router's root** is no longer dropped at once. It becomes the route of its prefix when the file mounts
  the router (`GET /admin`), and is dropped as before when it does not.
- **`r.With(mw).Get(...)`** is a registration on `r`.

Diff against `2026-10-15-v2-baseline-2`, judged:

- chi, fastify, Hono and NodeBB: every changed route is right, or lacks only a prefix from another file
  (chi's `todos` resource mounted in `main.go`).
- Ghost: the admin routes gain `/members/metafields` and `/apps` and still lack the admin API mount, which
  lives in another file.
- gitea: −440 +970. Closures were the whole prefix of its web routes, and that router is mounted at `/`, so
  those routes are now complete. The sampled web routes are right, except two registered in helper closures
  called inside other groups (`router-as-param`).

  In the `/api/v1` scope, 247 of the 282 extracted routes match the spec once `/api/v1` is prepended (16 before
  this step). That prefix comes from `r.Mount("/api/v1", apiv1.Routes())` in `routers/init.go`, so 231 expected
  items move from `prefix-scope-and-file` to `prefix-other-file`. Against the expected list they are still
  wrong: the scope's precision stays at 0 % with 282 routes instead of 129, which is why Go precision against
  the lists drops from 21.1 % to 18.4 % (H2-D14). The remaining 35 come from helpers that receive the router
  (`addProjectRoutes(m)`).
- One v1 judgment was wrong and was corrected: chi `router-walk` `PUT /ping`, a top-level route of the main
  router, had been judged as missing a closure prefix.

| Repository (routes) | P/R expected before | P/R expected now |
|---|---|---|
| chi | 14.3 % / 4.5 % | 75.0 % / 54.5 % |
| fastify | 75.0 % / 50.0 % | 100 % / 83.3 % |
| hono-examples | 70.8 % / 54.8 % | 77.8 % / 67.7 % |
| NodeBB | 0 % / 0 % | 40.0 % / 3.2 % |

| Language (routes) | P sampled before → now | R expected before → now |
|---|---|---|
| Go | 62.1 % → 68.5 % (150/219) | 9.8 % → 10.6 % |
| TS/JS | 28.8 % → 31.9 % (52/163) | 2.0 % → 3.7 % |

- `prefix-other-scope` (13 missed, 15 wrong) and `mount-same-scope` (16, 4) are gone. `prefix-scope-and-file`
  is down to 2 missed.
- What the mount graph still misses is across files or functions:
  - `prefix-other-file`: 1385 missed in 12 repositories;
  - `global-prefix`: 238 (immich's `setGlobalPrefix`);
  - `router-as-param`: 102;
  - `const-other-file`: 42;
  - `prefix-as-param`: 15.

New baseline: `2026-10-15-v2-baseline-3`.


## Update: C# — inherited `[Route]` and endpoint classes (2026-10-15)

H2b item 6, done first because the portfolio is mostly .NET (H2-D18). It needed the first step that crosses
files: each file leaves a summary that is data only, and each language composes the summaries after the whole
repository is scanned. The summary holds the facts the file publishes and the routes waiting on another file.
The mount graph's step 2 will use the same step.

- **Inherited `[Route]`, one level (H2-D10).** A controller with no `[Route]` of its own takes its base class's,
  found by name in the repository, with `[controller]` filled from the derived class. Two classes with the base's
  name (not two `partial` halves of one) give nothing. An action with no template is a route only under the
  inherited prefix.
- **Endpoint classes.**
  - FastEndpoints: a class deriving from `Endpoint<...>`, `EndpointWithoutRequest` or `Ep.*` declares its routes
    in `Configure()` with `Get("/x")`, `Post(CreateRequest.Route)`, or `Verbs(...)` with `Routes(...)`. Its
    handler is the class's `HandleAsync` or `ExecuteAsync`.
  - Ardalis.ApiEndpoints: an `EndpointBase*` class counts as a controller.
- **Class constants by qualified name.** Every request class in an ardalis folder has a `Route`, and the
  directory context used to keep only the last one collected. A class constant is now also known as
  `Class.NAME`. A bare name with two values in the directory resolves only to the file's own definition.
- **Found while judging the diff:**
  - `$"/{nameof(Project)}s"` came out as `/{param}s`. A `nameof(X)` inside an interpolation is the text `X`.
  - C# names the braces of an interpolation as nodes, so a local variable interpolated in C# was never resolved,
    although the rule was meant for every language.
- **`[action]`** drops the `Async` suffix, as ASP.NET Core does by default. The tokens stay lowercased because the
  linker compares paths exactly and clients write them lowercased. Keeping the declared case broke the .NET
  end-to-end link test, so case-insensitive matching for ASP.NET routes is left to the linker (F0.5).

Diff against `2026-10-15-v2-baseline-3`: only the three repositories below changed, and no calls changed.

- **jellyfin (−128 +162):**
  - the 128 routes that lacked `/{controller}` now have it;
  - 34 routes are new: template-less actions, and routes that used to collide in the dedupe (`/{genreName}` with
    other controllers' `/{param}`);
  - `GET /Items/Latest` now carries its real handler (`UserLibraryController`) instead of `ChannelsController`'s,
    which is now `/channels/Items/Latest`.
- **ardalis-clean-arch (+19):** all right.
- **eshop-on-web (+1):** `POST /api/authenticate`, right.

| Repository (routes) | P/R expected before | P/R expected now | P sampled before → now |
|---|---|---|---|
| jellyfin | 33.3 % / 25.0 % | 100 % / 100 % | 55 % → 100 % (20/20) |
| ardalis-clean-arch | — / 0 % | 100 % / 100 % | — |
| eshop-on-web | 100 % / 97.0 % | 100 % / 100 % | 100 % (20/20) |

| Language (routes) | P sampled | P expected | R expected |
|---|---|---|---|
| C# before | 90.4 % (85/94) | 94.6 % | 72.9 % (105/144) |
| C# now | 100 % (94/94) | 100 % | 93.1 % (134/144) |

- `inherited-route-attr` (9 missed, 9 wrong) and `endpoint-class` (20 missed) are gone.
- The 10 C# routes still missed are clean-arch-dotnet's `route-by-name-convention`. That repository maps its
  endpoint groups by reflection, which a convention describes better than the extractor.
- C# calls are unchanged. Next in C#: `client-wrapper` (11 missed) and `field-in-interpolation` (8 missed,
  4 wrong), then NSwag (item 7).

New baseline: `2026-10-15-v2-baseline-4`.

## Update: C# calls — constants in templates and the app's own client wrappers (2026-10-15)

This is the C# part of H2b item 5, done next because of the portfolio priority (H2-D18). The template rule is
general, so it also changes TS/JS calls.

- **Constants in templates.** A constant interpolated into a URL template is read only when it forms whole path
  segments:
  - a constant holding a path, at the start of the template: `$"{remoteServiceBaseUrl}items/{id}"` with the field
    `remoteServiceBaseUrl = "api/catalog/"`, or `$"{ApiUrlBase}/{orderId}"`;
  - a constant holding one word, standing for a whole segment: `` `/${resource}/${id}/join` `` with
    `resource = "cases"`, or `$"collections/{ManualCollectionName}/points/search"`. Word constants are kept apart
    from path constants, so a word alone never becomes a path.

  Neither applies inside a generic wrapper, meaning a template that takes the rest of its path from a variable
  named like one (`path`, `url`, `endpoint`, `*Url`). There the constant is only a base. Two cases show why:
  alertmanager's `${pathPrefix}/${API_PATH}${path}`, and ghost's
  `${GHOST_URL}/ghost/api/admin/${endpoint}${separator}god_mode=true`, which the first version of this rule
  turned into a junk call.
- **Path-valued calls in a template.** A call that already yields a path counts as whole segments, such as eShop's
  `UriHelper.CombineUri(base, ApiUrlBase)`. `CombineUri`, `CombineUrl` and `UrlCombine` join `Path.Combine`'s
  family. An unknown first part of a join is the base and is dropped, as in `base + "/x"`.
- **The app's own client wrappers.** eShopOnWeb's admin UI calls its API only through `HttpService.HttpGet<T>(uri)`,
  which wraps `_httpClient.GetAsync($"{_apiUrl}{uri}")`.
  - A method whose outbound path is built around one of its parameters publishes itself as a wrapper. The fact
    records which parameter is the path, the verb and the text around it, under its class and the class's
    interfaces.
  - A call with a string argument on a receiver whose declared type is known waits for the composition step. The
    receiver can be a field, a property, a parameter or a local.
  - The composition step builds the call's path. This is the first use of the cross-file step for calls.
- **Cost.** The first measurement showed the scanners were slow in general. Two fixes made the whole corpus faster,
  with the output identical to the run before them:
  - name bindings are indexed once per scope instead of walking the scope for each lookup;
  - aiohttp's bound-method alias is only looked for in files that use it.

  HTTP extraction time over the corpus went from 672 s to 98 s (netbox 49 s → 8 s in a normal run), and the whole
  run from about 23 minutes to 13.

Diff against `2026-10-15-v2-baseline-4`, judged: 8 repositories changed, and every changed item is right.

- **dispatch (−53 +273):** each UI `api.js` module's `resource` constant.
- **eshop (−11 +20):** the services' prefix field and the ClientApp's `CombineUri`.
- **eshop-on-web (+6):** the calls through `HttpService`.
- **eshop-support (−1 +1):** the word constant.
- **mattermost (−3 +3):** the Zephyr base URL's `/v2`, and `url.JoinPath(serverURL, "version")`.
- **zulip (−1 +1):** `urljoin(base, "/api/v1/remotes/" + endpoint)`.
- **argo-cd (−1 +1):** `/swagger.json`, whose prefix `path.Dir("/swagger-ui")` is the root.
- **ghost (+1):** an external GeoJSON download.

| Language (calls) | P sampled before → now | P expected before → now | R expected before → now |
|---|---|---|---|
| C# | 92.5 % → 100 % (53/53) | 84.1 % → 100 % | 63.8 % → 96.6 % |
| TS/JS | 57.6 % → 70.1 % (101/144) | 44.3 % → 59.5 % | 31.5 % → 45.0 % |
| Go | 93.8 % → 100 % (16/16) | 100 % | 31.6 % |
| Python | 66.7 % → 69.7 % (23/33) | 100 % | 66.7 % |

- `field-in-interpolation` is down to ghost's admin URL, which starts from `window.location` (4 wrong, 1 missed).
  `client-wrapper` is down to gitea's TS wrappers (16 missed): reading them needs receiver types in TS.
- The 2 C# calls still missed:
  - eshop-on-web's `GetFromJsonAsync("User")`, a single relative segment;
  - a `UriBuilder` in bitwarden (`url-object-builder`).
- **Found on the way, outside the HTTP extractor:** a C# generic method call on a receiver (`obj.Method<T>(...)`) is
  not a call site at all. `queries.scm` only matches bare generic calls, so `CALLS` edges to generic methods are
  missing in .NET repositories.

New baseline: `2026-10-15-v2-baseline-5`.

## Update: NSwag clients and the rest of .NET (2026-10-16)

This is H2b item 7 for .NET, the last .NET item under the portfolio priority (H2-D18). The corpus had no NSwag client:
v1's two generated clients are openapi-ts and go-swagger, and clean-arch-dotnet's NSwag client is gitignored. So
three .NET applications were added, each with a committed NSwag client of its own API:

| Repo | What it brings | Expected list |
|---|---|---|
| RapidBlazor | Blazor WebAssembly app and its API, NSwag v13 client | the client's 17 operations + 1 route hidden from the document |
| azure-saas | two API services with their NSwag v14 clients, an MVC admin area | the 26 operations + the area's attribute-routed controller (8) |
| notifo | notification service; NSwag v14 .NET SDK and the generated TS client of its UI | the SDK's 102 operations + 22 routes hidden from the document |

The expected lists take the operations from the generated clients, which are written from the API's OpenAPI document.
The routes that `[ApiExplorerSettings(IgnoreApi = true)]` hides from the document were read in the code and added
(H2-D15).

- **NSwag C# clients.** The file says it was generated by the "NSwag toolchain" in its header. Each client method:
  - takes its path from the `// Operation Path: "api/x/{id}"` comment (v14), or from the literals it appends with
    `urlBuilder_.Append(...)` (v13), with a placeholder for each value appended between them;
  - takes its verb from `request_.Method = new HttpMethod("GET")`;
  - is recorded with `via: generated-client`.

  File discovery skipped `*.g.cs` as generated code. It now keeps a `.g.cs` whose header names NSwag (RapidBlazor's
  client is `ApiClients.g.cs`).
- **NSwag TypeScript clients.** No new rule: the `fetch` template was already readable. Two defects hid it:
  - each operation builds the URL through a chain, `url_ = url_.replace("{appId}", ...)` and then
    `url_ += "take=" + ...` per query parameter. Expression resolution stopped at depth 4, so 11 of the 102 were
    lost. It is now memoized per node and stops at depth 64;
  - the verb is in a variable, `let options_: RequestInit = { method: "POST", ... }`, passed as `fetch(url_, options_)`.
    The verb is now read through that variable; before, every operation that is not a `GET` came out as `GET`,
    the `fetch` default.
- **Route case.** Item 6 kept `[controller]` and `[action]` lowercased because the linker compared paths exactly. The
  generated clients show what ASP.NET really publishes, `/api/TodoItems`, in the class's case. So the decision is
  reversed:
  - the tokens keep the declared case;
  - the linker matches routes of `aspnet`, `aspnet-minimal` and `fastendpoints` without case, as the framework
    does. Other frameworks still match exactly.
- **`[area]`** is filled from `[Area("..")]`. The reserved parameters `{area}`, `{controller}` and `{action}` in a
  template take the same values, because the router fixes them: azure-saas's `[Route("{area}/{controller}/admin")]`
  is `GET /Admin/Tenants/admin`.
- **Inherited actions.** A controller that declares no actions can serve those of an abstract base. notifo's email,
  messaging and SMS template controllers each serve the 9 actions of `ChannelTemplatesController<T, TDto>` under
  their own `[Route]`. Before this, 75 of notifo's 102 operations had a route; now all 102 do. An action the
  derived class declares itself wins over the base's, and the evidence stays on the base's line.

Diff against `2026-10-15-v2-baseline-5`: three existing repositories changed, all in path case only (same method
and evidence, same path when lowercased). No calls changed, and no TS/JS repository changed.

- jellyfin −162 +162 (`/backup` → `/Backup`);
- eShopOnWeb −25 +25 (`/manage/changepassword` → `/Manage/ChangePassword`);
- bitwarden −4 +4 (`/sso/login` → `/sso/Login`: the prefix is a literal, the action is the token).

Their expected lists were rewritten to the declared case.

| Repo | Routes P / R | Calls P / R | Sampled routes · calls |
|---|---|---|---|
| RapidBlazor | 100 % / 100 % (18) | 100 % / 100 % (17) | 18/18 · 17/17 |
| azure-saas | 100 % / 100 % (34) | 100 % / 100 % (26) | 20/20 · 20/20 |
| notifo | 100 % / 100 % (124) | 100 % / 100 % (102) | 20/20 · 20/20 |

The TS client of notifo is not in the expected calls, because those are counted for C#. It extracts the same 102
operations; 10 of them are in the sample.

| Language (C#) | P sampled | P expected | R expected |
|---|---|---|---|
| routes, before (7 repos) | 100 % (94/94) | 100 % | 93.1 % (134/144) |
| routes, now (10 repos) | 100 % (152/152) | 100 % | 96.9 % (310/320) |
| calls, before (7 repos) | 100 % (53/53) | 100 % | 96.6 % (56/58) |
| calls, now (10 repos) | 100 % (100/100) | 100 % | 99.0 % (201/203) |

What .NET still misses:

- clean-arch-dotnet's 10 routes mapped by reflection (`route-by-name-convention`), better described by the project's
  convention;
- eShopOnWeb's single-segment `GetFromJsonAsync("User")`;
- a `UriBuilder` in bitwarden;
- MVC conventional routing (`MapControllerRoute("{controller=Home}/{action=Index}/{id?}")`), which serves pages
  rather than APIs. It is left out of azure-saas's scope and noted in its expected list.

The run took about 11 minutes, 82 s of it HTTP extraction.

New baseline: `2026-10-16-v2-baseline-6` (42 repositories).

## Update: the mount graph, step 2 — across files (2026-10-16)

This is H2b item 2, step 2, for Go and Python, the portfolio's second tier (H2-D18). TS/JS stays on step 1.

**What crosses files now.** A router that another file can name gets a global id:

- a module-level or package-level variable (`router = APIRouter()` in a `views.py`);
- the router a function returns (gitea's `apiv1.Routes()`, chi's `todosResource{}.Routes()`, named
  `Type.Method`);
- a function's router parameter (`func UsersRegister(router *gin.RouterGroup)`), including a closure assigned to a
  variable (gitea's `addActionsRoutes := func(m *web.Router, ...)`);
- a struct field shared by a package's files (mattermost's `api.BaseRoutes.Users`).

A route registered on such a router waits for the composition step. Each file publishes:

- the mounts of its own global routers;
- every mount of a router from another file: `r.Mount("/api/v1", apiv1.Routes())`,
  `include_router(tag_router, prefix="/tags")`, `include_router(login.router)`, `app.mount("/api/v1", app=api)`;
- every router it passes to a function: `users.UsersRegister(v1.Group("/users"))`, `addActionsRoutes(m, ...)`.

The composition step follows those edges up to a top. A router mounted nowhere keeps its routes as written. Imports
are resolved by the same `resolve_import` that gives the graph its `IMPORTS` edges. A file never reads another
file's tree.

**Found on the way, also general:**

- **Constants from another package or module.** `PathPrefix(model.APIURLSuffix)`, `prefix=settings.API_V1_STR` and
  `mux.Handle(common.LoginEndpoint, h)` now resolve. Two kinds of constant were not collected before: a Go `const`
  that names another, and an annotated constant in a Python class body.
- **Closures.** A closure region's router parameter (chi's `r.Route("/x", func(r chi.Router) {...})`) is the outer
  router, so a mount of the outer router reaches it.
- **Gorilla.**
  - A regex constraint may hold braces (`{fingerprint:[a-f0-9]{32}}`) or a `?` (`{ws:websocket(?:\/)?}`).
  - A whole segment listing literal alternatives (`{syncable_type:teams|channels}`) gives one path per word. Inside a
    segment, as in gitea's `{sha}.{diffType:diff|patch}`, it stays a parameter.
  - `.Methods(GET, HEAD)` gives one route per verb.
- **Groups.** `r := app.Group("/todo").Use(auth)` is the group.
- **A sub-router's root** mounted without a prefix is a route when the chain ends at the application (gotify's UI
  `/`).

Diff against `2026-10-16-v2-baseline-6`, judged: 11 repositories changed, all Go or Python. No TS/JS or C#
repository changed.

- **mattermost (−378 +622):** every API route now has `/api/v4` and its subrouter's path. The two push-proxy calls
  gain `/api/v1`.
- **gitea (−472 +549):** the API routes under `/api/v1` and the package registry under `/api/packages`. The helpers
  that receive the router now get each group's prefix.
- **dispatch (−64 +286):** `/api/v1/{organization}/...` through three files: `views.py`, `api.py`, `main.py`.
- **fastapi-template (−23 +23):** `/api/v1` from `settings.API_V1_STR`.
- **gin-realworld (−12 +19), gin-examples (−4 +5), fiber-recipes (−11 +25):** groups passed to another package's
  functions.
- **chi (−4 +15):** todos/users resources and the versioned article routers.
- **kratos (−3 +14):** the public redirect routes now carry `httprouterx.AdminPrefix`. The admin router's own routes,
  which used to collide with them, now appear; they still lack the `/admin` of the router type
  (`prefix-in-router-type`). Six test-helper calls resolve their path constants.
- **argo-cd (+1):** `/auth/login` from `common.LoginEndpoint`.
- **fastapi (−1 +2):** the sub-application mounted at `/subapi`, and the `admin` router included with `/admin`.
- **gotify (+1):** `GET /`.

Expected lists, with H2-D15 applied (spec plus routes verified in the code):

- **dispatch:** the spec's paths are now under the `/api/v1` where `main.py` mounts the sub-app. The 85 routes the
  older spec lacks were added, and the outdated tag-recommendation operation became the code's two routes. Five
  misses remain:
  - the Slack plugin routes, mounted by a loop over the registered plugins (`router-from-registry`);
  - `auth_router.post("/register")(fn)` (`decorator-call`).
- **mattermost:** 24 routes the spec lacks (channel join requests, property options, the 404 catch-all,
  `web/oauth.go`, now in scope). The one miss left is a gorilla `PathPrefix(...).Handler(h)`
  (`path-prefix-handler`).
- **gitea:** 11 routes the spec lacks. Its 219 remaining misses are `route-chain`.

| Repo (routes) | P / R expected before | P / R expected now | P sampled before → now |
|---|---|---|---|
| mattermost | 0.3 % / 0.2 % | 100 % / 99.8 % | 5 % → 90 % |
| gitea | 0 % / 0 % | 99.7 % / 59.1 % | 45 % → 90 % |
| dispatch | 1.5 % / 0.5 % | 98.6 % / 98.3 % | 0 % → 95 % |
| fastapi-template | 0 % / 0 % | 100 % / 100 % | 0 % → 100 % |
| gin-realworld | 0 % / 0 % | 100 % / 100 % | 0 % → 100 % |
| chi | 75 % / 54.5 % | 100 % / 86.4 % | 44 % → 48 % |
| kratos | 82.5 % / 67.5 % | 84.9 % / 80.5 % | 85 % → 90 % |
| gin-examples | 70 % / 58.3 % | 100 % / 91.7 % | 95 % → 100 % |

| Language (routes) | P sampled | P expected | R expected |
|---|---|---|---|
| Go before | 68.9 % (151/219) | 18.4 % | 10.6 % (158/1495) |
| Go now | 87.7 % (192/219) | 98.7 % | 75.4 % (1153/1530) |
| Python before | 49.5 % (45/91) | 37.7 % | 3.5 % (60/1731) |
| Python now | 91.2 % (83/91) | 96.1 % | 20.3 % (369/1815) |
| Python without Django (FastAPI, Flask, aiohttp, CTFd), before → now | | 37.7 % → 96.1 % | 19.3 % → 93.4 % |

Before and after use different expected lists for dispatch (207 operations relative to the sub-app, then 291 under
`/api/v1`) and for gitea and mattermost (the routes the specs lack).

What Go still misses:

- gitea's `route-chain` (219): `m.Combo("/x").Get(h).Put(h)`, item 4;
- the generated servers of argo-cd and alertmanager (`generated-server`, 115);
- kratos' router types that add `/admin` (`prefix-in-router-type`, 12).

Python outside Django misses CTFd's flask-restx resources (17) and the five dispatch routes above. Django
(`django-urlconf`, 1420) is item 8.

HTTP extraction went from 82 s to 88 s for the whole corpus (mattermost 22 → 23 s). The whole run still takes about
11 minutes.

New baseline: `2026-10-16-v2-baseline-7`.
