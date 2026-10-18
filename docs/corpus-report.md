# HTTP extractor — corpus report

Precision and recall of the HTTP integration extractor (`core/integrations.py` + `languages/<lang>/http.py`)
on the public calibration corpus. v1 (F0.4.3a, handoff H2a) measured the 15 repositories the extractor was
calibrated on, pinned to fixed commits and measured against an expected list per repository. The two
"Update" sections record the cheap fixes that followed. **v2** widens the corpus to 39 repositories (42 later),
most of them real applications, and resets the order of H2b (F0.4.3b); its "Update" sections record each step of
H2b, **"Closing H2b"** has where it started, where it ends and where each remaining gap goes, and **"The hold-out
set"** measures, once, 16 repositories the rules never saw. **F1.14**'s sections (ROADMAP) follow: increments 1–5
moved 13 of them to the corpus (55), and the hold-out keeps 3; increment 6 on closes the rest of F1.14. Plan,
decisions and status of H2 are in `docs/handoffs/H2-roadmap.md`.

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

## Update: route chains — H2b item 4 (2026-10-16)

This is H2b item 4, `route-chain`, which H2-D18 put next for Go. It is done for Go and for the express form in
TS/JS.

**What is read now:**

- **Verbs chained on a path builder.** gitea's `m.Combo("/x", mw).Get(h).Put(h)` and express's
  `router.route('/x').get(h).post(h)` give one route per verb, on the builder's path and router. The verb's first
  argument is not a path, so nothing came out before. Hono's `app.route('/x', sub)`, with two arguments, is still a
  mount.
- **gorilla's route builder.** `r.Methods("POST").Path("/x").Handler(h)` and `r.Path("/x").HandlerFunc(h).Methods("GET")`
  are routes. The verbs can come before or after the handler. A `PathPrefix(...).Handler(h)` serves a whole tree,
  so it is a route only when it has a method: mattermost's OAuth metadata endpoint is one, a `FileServer` is not.
- **`http.StripPrefix`.** In `r.PathPrefix("/addsvc").Handler(http.StripPrefix("/addsvc", pkg.NewHTTPHandler()))`,
  the gateway mounts the handler another package returns, under the prefix the strip removes.
- **Served routers.** A router of another file passed to `http.Serve` or `ListenAndServe` is an application too. So
  when go-kit's addsvc serves the handler that the gateway also mounts, its routes stay in both places.

Diff against `2026-10-16-v2-baseline-7`, judged: 4 repositories changed, all with routes added only.

- **gitea (+290):** the 219 `Combo` routes of the API, and 71 in the web UI and the actions artifacts router. The
  web UI routes have the same prefixes as their neighbours. That includes the `router-as-param` defect already
  judged in `web.go`, where a closure passed to a group by value loses the group's path.
- **go-kit-examples (+11):** profilesvc's 9 builder routes, and addsvc's two routes under `/addsvc`.
- **mattermost (+1):** `GET /.well-known/oauth-authorization-server`.
- **express-boilerplate (+3):** `GET`, `PATCH` and `DELETE /:userId`. They lack the `/v1/users` that another file
  mounts, so they are wrong, like the auth routes (`prefix-other-file`, the TS step 2). The chain's
  `router.route('/')` roots wait for that mount. The 5 expected items moved from `route-chain` to
  `prefix-other-file`.

| Repo (routes) | P / R expected before | P / R expected now |
|---|---|---|
| gitea | 99.7 % / 59.1 % | 99.8 % / 99.1 % |
| go-kit-examples | 100 % / 59.3 % | 100 % / 100 % |
| mattermost | 100 % / 99.8 % | 100 % / 100 % |

| Language (routes) | P sampled | P expected | R expected |
|---|---|---|---|
| Go before | 87.7 % (192/219) | 98.7 % | 75.4 % (1153/1530) |
| Go now | 87.7 % (192/219) | 98.9 % | 90.5 % (1384/1530) |

`route-chain` is no longer in the ranking. Go still misses 146 routes; the largest groups are:

- the generated servers of argo-cd and alertmanager (`generated-server`, 115);
- kratos' router types that add `/admin` (`prefix-in-router-type`, 12);
- gitea's `g.MatchPath("GET", "/<ref:*>/status", h)` (`custom-registrar`, 3), plus two patterns that gitea joins to
  the group without a slash.

Go calls are still at 31.6 % recall: go-kit's request encoders, URL objects, and the generated clients of item 7.

HTTP extraction took 88.8 s for the whole corpus (88 s before). The whole run still takes about 11 minutes.

New baseline: `2026-10-16-v2-baseline-8`.

## Update: Go calls and Go generated clients (2026-10-16)

This step covers the call side of Go, the next tier after the routes (H2-D18). It joins item 5 (`url-object-builder`)
with the Go part of item 7 (generated clients).

**What is read now:**

- **The path on a `url.URL`.** The notifiers of alertmanager and the OIDC providers of kratos build the URL as an
  object: `u.Path += "gettoken"`, `u.Path = path.Join(u.Path, "/oauth/userinfo")`, `APIURL.JoinPath("api/v1/x")`. They
  send `u.String()` later. Now `u.String()`, or `u` itself, takes the last path assigned to `u.Path` before that
  point; with nothing assigned, it takes the path of `url.Parse(literal)`. The base URL comes from configuration, so a
  relative `+=` gets its leading slash.
- **go-kit clients.** In `httptransport.NewClient("GET", tgt, encodeX, decodeX)` the method is the first argument.
  The path is the URL's, or, when the URL sets none (`tgt.Path = ""`), whatever the request encoder sets
  (`req.URL.Path = "/profiles/" + id`). The encoder is often in another file: each encoder publishes its path, and
  the call is completed after the scan.
- **Generated clients** (`via: generated-client`):
  - **openapi-generator.** `localVarPath := localBasePath + "/admin/identities/{id}"`, then `strings.Replace(..)` and
    `prepareRequest(ctx, localVarPath, localVarHTTPMethod, ..)`. The verb comes from the variable.
  - **go-swagger.** `&runtime.ClientOperation{Method: "GET", PathPattern: "/alerts"}`. The spec's `basePath` is added
    by the transport at runtime, like a base URL.

**Caught on the first run.** Relaxing the "unknown router" guard, so that `notify.Get(ctx, client, u.String())`
counts as a call, also let through two false calls:

- **huma.** `huma.Get(api, "/books", h)` registers a route; it is not a request. A verb with a path before the last
  argument and a handler at the end is now a route registration.
- **A SQL query in mattermost** (`"SELECT " + strings.Join(cols, ", ") + " FROM Posts"`). The concatenation accepted
  any `"WORD /"` as a net/http 1.22 `"METHOD /path"` pattern; it now requires an HTTP verb. `strings.Join` no longer
  counts as a path join.

Diff against `2026-10-16-v2-baseline-8`, judged: 7 repositories changed, calls only, all added. No route changed.

- **kratos (+126):** the 60 operations of the openapi-generator client, in its two copies (`pkg/httpclient` and
  `pkg/client-go`), match `spec/api.json` exactly. Six OIDC provider calls were added too.
- **alertmanager (+15):** the 9 go-swagger operations, opsgenie's 4 and wechat's 2.
- **go-kit-examples (+11):** profilesvc's 9 calls through its encoders, `/paths` and `/uppercase`.
- **go-feature-flag (+3), argo-cd (+1), mattermost (+2), fiber-recipes (+1):** URLs built on `url.Parse(..)`. That
  covers Maven, PyPI, GitHub, the Azure token exchange and Mattermost's calls to a remote Mattermost
  (`path.Join(u.Path, model.APIURLSuffix, "remotecluster", ...)`).

Expected lists:

- **kratos:** the generated client's 60 operations, taken from the spec it is generated from.
- **alertmanager:** the 9 go-swagger operations. Rocketchat's call is still missed: it posts through a function kept
  in a struct field (`n.postJSONFunc`), now categorised `client-in-field`.
- **go-kit:**
  - the `/uppercase` client was listed as `POST`; it is a `GET`;
  - three calls were added whose path is a parameter of a helper (`copyURL(u, "/sum")` and the gateway's
    `stringsvcFactory(ctx, "GET", "/count")`), as `url-from-helper`.

| Repo (calls) | R expected, baseline-8 → now (same expected lists) | P expected |
|---|---|---|
| kratos | 10.5 % → 96.1 % | 100 % |
| alertmanager | 0 % → 93.8 % | 100 % |
| go-kit-examples | 0 % → 78.6 % | 100 % |

| Language (calls) | P sampled | P expected | R expected |
|---|---|---|---|
| Go before (same expected lists) | 100 % (16/16) | 100 % | 10.9 % (12/110) |
| Go now | 100 % (16/16) | 100 % | 93.6 % (103/110) |

What Go calls still miss (7 calls):

- URLs kept in struct fields (`url-in-field`, kratos, 3);
- paths passed to a helper as a parameter (`url-from-helper`, go-kit, 3);
- rocketchat's function field (`client-in-field`, 1).

HTTP extraction took 91.1 s for the whole corpus (88.8 s before). The whole run still takes about 11 minutes.

New baseline: `2026-10-16-v2-baseline-9`.

## Update: Go generated servers (2026-10-16)

This is the last large gap in Go routes. 115 of the 146 Go routes still missed were served by generated code:
argo-cd's grpc-gateway (106) and alertmanager's go-swagger server (9).

**What is read now:**

- **grpc-gateway.** `*.pb.gw.go` registers each route as `mux.Handle("GET", pattern_AccountService_CanI_0, func(..))`.
  The path exists only in `runtime.MustPattern(runtime.NewPattern(1, []int{2, 0, 2, 1, ..}, []string{"api", "v1", ..},
  ""))`, a small stack program that pushes literals, captures variables (`{name}`, also `{id.value}`), takes the rest
  of the path (`**`) and appends a custom verb (`:sync`). `path_of` decodes it. Three changes support it:
  - `Handle(verb, path, h)` with the verb first is a route; httprouter uses the same form.
  - The handler is named after the gRPC method (`AccountService.CanI`).
  - A package variable built by a call counts as a last resort for a name, so `pattern_X_0` resolves.
  - `normalize_path` keeps a custom verb after a placeholder literal: `{name}:cancel` is no longer `{name}{cancel}`.
- **go-swagger server.** `restapi/operations` registers `o.handlers["GET"]["/alerts"] = ..`. The routes are relative
  to the spec's `basePath`, which only `restapi/embedded_spec.go` holds, inside the embedded JSON. That file publishes
  the `basePath`, and the routes wait for it.

Diff against `2026-10-16-v2-baseline-9`, judged: 2 repositories changed, routes added only.

- **argo-cd (+106):** the whole `/api/v1` of the committed swagger, from `pkg/apiclient/**`. The four extra
  registrations are the same routes registered twice (`...HandlerServer` and `...HandlerClient`).
- **alertmanager (+9):** the whole `/api/v2` spec.

Expected lists:

- **argo-cd:**
  - `pkg/apiclient/` entered the endpoint scope, since the gateway registers the routes there.
  - The hand-written `/auth/login`, `/auth/callback` and `/api/webhook` were added. The last two are registered first
    by another app of the repo (the CLI's local login callback, the applicationset controller), and the route node
    keeps that evidence (`multi-app-repo`).

| Repo (routes) | P / R expected before | P / R expected now |
|---|---|---|
| argo-cd | 66.7 % / 3.5 %¹ | 98.2 % / 96.5 % |
| alertmanager | — / 0 % | 100 % / 100 % |

¹ Before = the run of baseline-9 measured against the new expected list (114 routes).

| Language (routes) | P expected | R expected |
|---|---|---|
| Go before | 98.9 % | 90.5 % (1384/1530) |
| Go now | 99.1 % | 97.8 % (1500/1533) |

What Go routes still miss (33):

- kratos' router types that add `/admin` (`prefix-in-router-type`, 12);
- paths built from a string parameter (`prefix-as-param`, argo-cd and others);
- `multi-app-repo`;
- gitea's `MatchPath` (3).

**Timing.** This run took 111.7 s of HTTP extraction against 91.1 s before, but every repository slowed by 20–25 %,
TS, Python and C# included, and parsing too. Re-running ghost, netbox and gitea right after, with the code before and
after this change, gave the same times (52.9 / 52.8 s, 33.8 / 31.2 s, 62.6 / 61.0 s). The rise was the machine's
load at that moment, not this change.

New baseline: `2026-10-16-v2-baseline-10`.

## Update: flask-restx resources and hand-applied route decorators (2026-10-16)

Python outside Django still missed or got wrong 26 expected routes in two repositories: CTFd's REST API, which is
flask-restx, and one route of dispatch.

**What is read now:**

- **flask-restx** (also `flask_restplus` and `flask_restful`):
  - `Namespace` and `Api` imported from it are routers. A namespace's `path=` is its prefix.
  - An `Api(blueprint)` is mounted on the blueprint or app it is built with, so it takes the blueprint's
    `url_prefix`.
  - `api.add_namespace(ns, "/challenges")` mounts the namespace, also one from another file, through the
    cross-file mount graph.
  - `@ns.route("/<id>")` on a `Resource` class gives one route per HTTP method the class defines, with the handler
    `Class.method`. Before, the class was a single `GET` with neither prefix.
- **A decorator applied by hand.** `register_user = auth_router.post("/register")(register_user)` is the route of
  `register_user`.

Not applied: a namespace's default path (`/<name>`), which holds only when neither `Namespace` nor `add_namespace`
gives one. CTFd always gives it.

Diff against `2026-10-16-v2-baseline-10`, judged: 2 repositories changed.

- **CTFd:**
  - The 40 restx routes that came out as `GET` without a prefix are replaced by 155, one per method, under
    `/api/v1/<namespace>`. An `ast` walk of `CTFd/api` counts the same 155, in 90 classes.
  - Four blueprint routes come back (`GET /teams`, `/users`, `/users/{user_id}` and `/{route}`). A restx route with
    the same normalized id had hidden each of them.
  - Routes with a handler went from 82 of 122 to 241 of 241.
- **dispatch (+1):** `POST /api/v1/{organization}/auth/register`.

Expected lists:

- CTFd's 17 `restx-resource` items and dispatch's `decorator-call` item lose their category.
- The 7 CTFd samples judged wrong (a `GET` without its prefix) were judged again, and all are right now. Among them
  is `TeamPrivateMembers`, which defines only `post` and is now a `POST`.

| Repo (routes) | P / R expected before | P / R expected now |
|---|---|---|
| CTFd | 57.7 % / 46.9 % | 100 % / 100 % |
| dispatch | 98.6 % / 98.3 % | 98.6 % / 98.6 % |

| Language (routes) | P sampled | P expected | R expected |
|---|---|---|---|
| Python before | 91.2 % (83/91) | 96.1 % | 20.3 % (369/1815) |
| Python now | 98.9 % (90/91) | 99.0 % | 21.3 % (387/1815) |
| Python without Django (FastAPI, Flask, aiohttp, CTFd), before → now | | 96.1 % → 99.0 % | 93.4 % → 98.0 % (387/395) |

What Python routes still miss outside Django (8):

- dispatch's Slack plugin routes, which a loop over the registered plugins mounts (`router-from-registry`, 4). The
  registry is filled at run time, so this stays a limitation.
- fastapi's documentation examples, which register the same path in several apps of the repository
  (`multi-app-repo`, 4).

Django's urlconf (1420, netbox and zulip) is still deferred (item 8).

**Timing.** HTTP extraction took 113.8 s, against 111.7 s before. In this run mattermost took 1369 s in all, against
250 s before, with its HTTP part unchanged (30.4 s). The change touches only Python. Run alone right after, with the
same code, mattermost took 249.6 s (29.0 s of HTTP). The spike was the machine, not this change.

New baseline: `2026-10-16-v2-baseline-11`.

## Update: the mount graph across files in TS/JS (2026-10-16)

TS/JS was the language furthest behind: 3.7 % recall of the expected routes. The largest gap was a router whose prefix
lives in another file (`prefix-other-file`: ghost 256, express-realworld 19, express and hono-examples 4 each). The
cross-file mount graph that Go and Python already had now covers TS/JS.

**What is read now:**

- **Imports and exports, ESM and CommonJS.**
  - Imports: `import r from`, `import { a as b }`, `import * as m`, `require('./x')`, `require('./x').y` and
    `const { y } = require('./x')`.
  - A module-level router is known to other files as `var:<file>:<name>`. A router a function returns is
    `ret:<file>:<function>`, and a router passed as a parameter is `param:<file>:<function>:<i>`. A function exported by
    `module.exports =` or `export default` is named `default`.
  - An export under another name (`export default router`, `module.exports = { a: b }`, `exports.x = y`) and a
    re-export (`module.exports = require('./app')`, `export { a } from './x'`) are edges without a prefix, from the
    local name to the exported one.
- **What a mount can mount:** an imported name, `require('./x')` in place, `routes()` (what the function returns) or
  `m.router`. `require('./legacy')(app)` hands the router to the other file's parameter.
- **`use` without a path** mounts with an empty prefix.
- **Chains.** A chain of calls that starts at a router constructor belongs to the name the chain is bound to:
  `export const TodoAPI = new Hono().get(..).post(..)`, or `export default Router().use('/api', api)` (named
  `default`). A generic between the constructor and its call (`new Hono<{ Bindings: Env }>()`) no longer hides it.
- **A project's own mount wrapper.** Ghost mounts its APIs with `app.lazyUse(path, require('./x'))`, a method that
  `shared/express.js` defines as `app.use(mountPath, .. requireFn() ..)`.
  - A method whose parameter is the path of a `use` call is published as a mount wrapper: the position of the path,
    the position of the router, and whether the method calls it.
  - A call of that name on a router stays a candidate, and `compose` makes it a mount when some file defines a wrapper
    of the same shape.
- **Applications.** An application other files can name is published, so a chain that ends at an application nobody
  mounts keeps a sub-router's root.

Diff against `2026-10-16-v2-baseline-11`, judged: 5 repositories changed, all TS/JS; Go, Python and C# are identical.

- **ghost:**
  - The Admin and Content APIs come out under `/ghost/api/admin` and `/ghost/api/content`. The chain is backend →
    `lazyUse(BASE_API_PATH, require('../api'))` → re-export → `lazyUse('/admin/', ..)` → `use(routes())`, with
    `BASE_API_PATH` from `shared/url-utils.ts`.
  - The members, comments, announcement, gift and webmentions apps take `/members`, `/gift` and `/webmentions` the
    same way.
  - The Content API grows from 4 routes to 20. Without the prefix, its routes had the ids of the Admin ones, and the
    dedupe kept only the first.
- **express-realworld:** all 19 routes under `/api`, through the unnamed chains.
- **express:** `examples/multi-router` under `/api/v1` and `/api/v2`, roots included.
- **hono-examples:**
  - The stytch `TodoAPI` comes out under `/api`.
  - The blog's router (`api`, typed with generics) is a router now, not a client.
- **nodebb (+2):** `GET /` and `POST /` of the web installer (`install/web.js`). Its `app = express()` is the
  application, and the routes registered inside `setupRoutes()` keep their root.

Expected lists:

- **ghost:** 13 routes added. The run showed that the regex behind the list had missed two sub-routers that
  `admin/routes.js` mounts on itself (`router.use('/apps', appsRouter)`, `router.use('/members/metafields', ..)`).
- **All four repositories:**
  - `prefix-other-file` and `client-named-router` were removed from the items found.
  - The 42 samples whose path changed were judged again, and all are right.

| Repo (routes) | P / R expected before | P / R expected now |
|---|---|---|
| ghost | 0 % / 0 % | 100 % / 100 % (269) |
| express-realworld | 0 % / 0 % | 100 % / 100 % |
| express (`multi-router`) | — / 0 % | 100 % / 80 % |
| hono-examples | 77.8 % / 67.7 % | 93.5 % / 93.5 % |

| Language (routes) | P sampled | P expected | R expected |
|---|---|---|---|
| TS/JS before | 31.9 % (52/163) | 5.9 % | 3.7 % (38/1028) |
| TS/JS now | 57.7 % (94/163) | 50.4 % | 32.9 % (338/1028) |

The before row is baseline-11 measured against the new lists, which have the 13 ghost routes.

What TS/JS routes still miss (690):

- NodeBB's own registrar (`custom-registrar`, 353);
- Nest's `setGlobalPrefix` (`global-prefix`, 238);
- the controller prefix in an enum of another file (`const-other-file`, 42 in immich);
- the express-boilerplate mount loop over a literal array (`prefix-other-file`, 14);
- the fastify-demo autoload by folder (`prefix-by-folder`, 14);
- a prefix passed as a string parameter (`prefix-as-param`, 13);
- the Next.js file routes (`route-by-file-path`, 9);
- the multi-app repositories and the rest (7).

**Timing.** HTTP extraction took 105.0 s, against 113.8 s before. ghost, the repository the change does the most
for, went from 11.6 s to 12.4 s. In this run bitwarden took 813 s in all, with its HTTP part unchanged (6.9 s). Run
alone right after, with the same code, it took 129.8 s. The run before had the same spike in mattermost. In each full
run, one large repository becomes 4–6 times slower outside HTTP, likely from memory pressure in the Docker VM. It is
not this change.

New baseline: `2026-10-16-v2-baseline-12`.

## Update: Nest's global prefix and controller constants (2026-10-16)

After the cross-file graph, the largest TS/JS gap was Nest's `app.setGlobalPrefix('api')` (`global-prefix`, 238, all
but one in immich). Next came the controller prefix held in an enum of another file (`const-other-file`, 42 in immich).

**What is read now:**

- **`setGlobalPrefix`** applies to the controllers of the package that calls it, the module of the nearest
  `package.json`.
  - The call is published per package. Every Nest route waits for `compose`, which applies the prefix only when the
    package has a single one.
  - `exclude` takes strings, `{ path }` objects and wildcards (`docs/(.*)`, `x/*`, `x/{*splat}`). The list may be
    another file's: immich's `excludePaths`, an exported array of strings.
- **The arguments of a Nest decorator are read from the tree:**
  - a literal;
  - an array, which gives one route per path (`@Get(['ping', 'status'])`);
  - an object's `path` (`@Controller({ path: 'host-array', host: [..] })`);
  - a constant or an enum member, also of another file (`@Controller(RouteKey.Asset)`). String members of a TS enum
    are now constants named `Enum.Member`.
- **A comment between a decorator and its method** no longer hides the handler.
- **Found on the way: the TS import resolver.** Immich imports `src/enum.js` for `server/src/enum.ts`, the ESM
  convention under `moduleResolution: nodenext`, through a `src/*` alias of its own `server/` package.
  - The resolver now tries the `.ts`/`.tsx`/`.mts`/`.cts` source of a `.js`/`.jsx`/`.mjs`/`.cjs` specifier.
  - It tries the aliases (`src/`, `@/`, `~/`, `#`) from the file's package before the repo root.
  - This changes the `IMPORTS` edges of the code graph, not only the HTTP extractor. Measured on four TS
    repositories with the code before and after:

| Repo | resolved file imports before → after | unresolved before → after |
|---|---|---|
| immich | 76 → 3232 | 3244 → 88 |
| nest | 54 → 3540 | 3489 → 3 |
| ghost | 11647 → 14863 | 3817 → 601 |
| fastify-demo | 0 → 26 | 26 → 0 |

  Every one of the 9845 new edges names the file its specifier names (same path, extension and `index` aside). No
  edge was lost or moved to another target.

Diff against `2026-10-16-v2-baseline-12`, judged: 2 repositories changed.

- **immich:**
  - 246 routes take `/api`, and 44 also take the enum's prefix (`/api/assets`, `/api/users`).
  - 3 routes the dedupe had hidden come back.
  - `/.well-known/immich` and `/custom.css` stay out of the prefix, as `excludePaths` says.
- **nest:**
  - `sample/24-serve-static` puts its root under `/api`.
  - The integration apps' controller prefixes given as objects are read. Those routes are still the framework's
    test apps (`test-app-folder`).

Expected lists:

- **immich:** 16 real routes the spec leaves out were added (H2-D15): the 14 `PATCH` aliases marked
  `@ApiExcludeEndpoint()`, and the two excluded from the prefix. Its 20 samples were judged again, and all are right.
- **nest:** its 2 changed samples stay `test-app-folder`.
- **Both:** `global-prefix` and `const-other-file` leave the ranking.

| Repo (routes) | P / R expected before | P / R expected now |
|---|---|---|
| immich | 0.7 % / 0.7 % | 100 % / 100 % (295) |
| nest (`sample/`) | — / 0 % | 100 % / 25 % (the 3 left are `multi-app-repo`) |

| Language (routes) | P sampled | P expected | R expected |
|---|---|---|---|
| TS/JS before | 57.7 % (94/163) | 50.7 % | 32.6 % (340/1044) |
| TS/JS now | 69.9 % (114/163) | 93.9 % | 60.7 % (634/1044) |

The before row is baseline-12 measured against the new lists, which have the 16 immich routes.

What TS/JS routes still miss (410):

- NodeBB's own registrar (`custom-registrar`, 353);
- fastify-demo's autoload by folder (14);
- the express-boilerplate mount loop (14);
- a prefix passed as a parameter (13);
- the Next.js file routes (9);
- the multi-app repositories and the rest (7).

**Timing.** HTTP extraction took 131.1 s, against 105.0 s before. Every repository slowed by 20–35 %, the Go ones
included, which this change does not touch (kratos 3.8 → 4.8 s, gitea 6.3 → 8.5 s). The cause is the machine's load,
as in the run of the Go generated servers.

New baseline: `2026-10-16-v2-baseline-13`.

## Update: the project's own route registrars in TS/JS (2026-10-17)

After the Nest step, NodeBB alone held most of the TS/JS gap (`custom-registrar`, 353). It registers every route
through helpers of its own: `setupApiRoute(router, 'post', '/x', mws, handler)` for the write API and
`setupPageRoute(app, '/x', .., handler)` for each page and its `/api` JSON twin. A helper of this kind is common in
real projects, so the rule is the general one: the same mechanism as Ghost's mount wrapper, for routes.

**What is read now:**

- **A route wrapper** is a named function (method, `helpers.x = function`, declaration, `const x =`) that registers
  on a router parameter (`router.get(name, ..)`, `router[verb](name, ..)`). The path comes from a parameter, also
  inside a template (`` `/api${name}` ``). A rest parameter destructured in the body counts: `(...args) => { const
  [router, verb, name] = args; .. }`.
  - Its shapes are published: the router's position; the verb, or the position of the argument that names it; the
    path's position; the path around it.
  - A call with a path and a router among its arguments is a candidate, with the handler from its last argument and
    where its router leads. `compose` makes it a route, before the mount graph.
  - The registrations in the wrapper's body stay routes as written until `compose` sees the wrapper used. Then they
    are dropped as the templates they are (`GET /api{param}`, a false positive before).
  - A candidate never stops the reading of its call. The run showed k6's `http.del(url, null, params)` in bitwarden
    being taken for one.
  - A call whose path has a part only known at run time makes no route. NodeBB's remountable prefixes
    (`` `/${name}/settings` ``) would give `/{param}/settings`, which links nothing, since the linker compares literal
    segments.
- **A module router returned by the exported function** (`module.exports = function () { ..; return router }`)
  follows `require('./users')()`.
- **Express's optional trailing parameters** (`/reset/:code?`, `/chats/:roomid?/:index?`) give the short forms too.

Diff against `2026-10-16-v2-baseline-13`, judged: only NodeBB changed. Its routes went from 92 to 377:

- the write API under `/api/v3/*`;
- the read API's pages and their `/api` twins;
- the optional short forms.

One route left: the helper's template. The other repositories are identical.

Expected lists (NodeBB):

- The scope grew to the files that register the read API: `index.js`, `user.js` and `activitypub.js`.
- Under H2-D15, 62 real routes that the specs leave out were added: the HTML pages, the ActivityPub routes,
  `/compose`, `POST /email/unsubscribe/{token}`, `POST /api/user/{userslug}/uploadpicture` and the optional short
  forms.
- The spec's `POST /api/email/unsubscribe/{token}` was removed, because the code registers only the GET.
- The misses blocked by a runtime prefix moved from `custom-registrar` to `prefix-as-param` (119): the remountable
  mounts, built by a `reduce` that plugins can change, and `/ping` and `/sping` under `${relativePath}`.

| Repo (routes) | P / R expected before | P / R expected now |
|---|---|---|
| NodeBB | 66.7 % / 8.7 % | 93.9 % / 73.1 % (439) |

| Language (routes) | P sampled | P expected | R expected |
|---|---|---|---|
| TS/JS before | 70.4 % (114/162) | 94.0 % | 59.7 % (660/1105) |
| TS/JS now | 70.4 % (114/162) | 95.5 % | 85.3 % (943/1105) |

The before row is baseline-13 measured against the new lists.

**Timing.** HTTP extraction took 105.2 s, back from the 131.1 s of the loaded Nest run. NodeBB took 3.4 s.

New baseline: `2026-10-16-v2-baseline-14`.

## Update: TS generated clients and requests described by an object (2026-10-17)

Two TS clients in the corpus are generated from the server's OpenAPI spec. Neither was read:

- immich's web app calls its server only through an oazapfts SDK, with 279 operations;
- fastapi-template's frontend uses a `@hey-api/openapi-ts` SDK, with 23.

The second writes each operation as `(options.client ?? client).post({ url: '/api/v1/..', ...options })`. That is the
`request-config-object` form already measured in hand-written code (9 misses in zulip, gotify and NodeBB), so one
general rule covers both.

**What is read now:**

- **A request described by an object.** In a verb method (`get` … `delete`, `del`), or in `request`, `ajax` or
  `axios`, an object whose `url` holds a path is the request, whatever the receiver is called.
  - The verb comes from the method's name, else from the object's own `method` (`type` for jQuery), else GET.
  - Only the object's own keys count. The `security: [{ type: 'http' }]` of openapi-ts is no verb.
  - Examples: zulip's `channel.post({ url: "/json/bots" })`, gotify's `axios.create().request({ url, method })`,
    `$.ajax(url, { type: 'POST' })`.
- **oazapfts.** In a file with its header, `oazapfts.fetchJson`, `fetchText` and `fetchBlob` are `generated-client`
  calls.
  - The path drops its query string (`${QS.query(..)}`) and goes under the client's literal `baseUrl` (`"/api"`).
  - The verb comes from the options, also inside `oazapfts.json(..)` or `multipart(..)`, and is GET when there is none.

Diff against `2026-10-16-v2-baseline-14`, judged: 7 repositories changed, calls only, additions only.

- immich +279 (the SDK, every operation of the spec under `/api`) and fastapi-template +23 (its SDK).
- zulip +124: the web app's `channel.post/get/patch/del({ url })`.
- ctfd +5, NodeBB +6 (`$.ajax`), gotify +2 (`axios.request`).
- mattermost +10, in `e2e-tests/` (test tooling, which the baseline already counts: 21 of its 44 calls).

Expected lists:

- immich and fastapi-template get call lists for the first time: immich the 279 operations of its committed spec
  under `/api` (scope `packages/sdk/`); fastapi-template its 23 routes, which the generated client mirrors (scope
  `frontend/src/client/`, language TS/JS under H2-D17).
- The 9 `request-config-object` misses are found.

| Repo (calls) | P / R expected before | P / R expected now |
|---|---|---|
| immich (SDK) | — / 0 % | 100 % / 100 % (279) |
| fastapi-template (SDK) | — / 0 % | 100 % / 100 % (23) |
| zulip | — / 0 % | 100 % / 100 % (7) |

| Language (calls) | P expected | R expected |
|---|---|---|
| TS/JS before | 59.5 % | 12.1 % (50/413) |
| TS/JS now | 91.4 % | 87.4 % (361/413) |

The before row is baseline-14 measured against the new lists.

What TS/JS calls still miss (52):

- a client wrapper that prepends its own prefix (`prefix-in-client-wrapper`, 34): argo-cd's UI, 25, and NodeBB's
  `api.put('/admin/..')` under `/api/v3`, 9;
- the app's own client wrappers in TS (`client-wrapper`, 15, gitea), which need the receiver's type in TS;
- one each of a field in an interpolation, a URL builder and data taken for a handler.

**Timing.** HTTP extraction took 106.9 s, against 105.2 s before.

New baseline: `2026-10-17-v2-baseline-15`.

## Update: the last cheap fixes (2026-10-17, H2 Phase 5)

The final ranking still showed a few defects that one line of rule fixes. Each now has a fixture with a case and a
counterexample, and each fixture fails without its rule:

- **Django's test client.** `client = Client()` with `from django.test import Client` now counts as a test client,
  like `TestClient(app)`. It was in a development view outside test folders: 9 zulip calls, all judged wrong.
- **`urljoin` onto an absolute path.** `urljoin(f"https://{hostname}", f"/api/v1/../{token}/")` was recorded as
  `/https:/{param}/api/v1/..`. Now an absolute second argument is the path, and a join that starts with a URL keeps
  its host.
- **The path of a URL is checked.** A URL passed validation with anything after the host. Its path must now be a
  route path, as for a literal without a host: `https://host/admin/${token}god_mode=true` is no call. This was
  the open item of the C# calls.
- **Hono's regex constraint.** `/:id{[0-9]+}` is the parameter.
- **Test folders by name.** `TEST_FILE` now also covers `e2e-tests/`, `cypress/`, `playwright/` and `testhelpers/`
  (`e2e/` already counted). `integration/` is left out on purpose, because in real apps it often names production
  code. The test apps of nest and fastify under that name go to the per-repository config of F1.1.
- **A constant formatted into a path.** `fmt.Sprintf("/%s", SchemasPath)` with `SchemasPath = "schemas"` (kratos).
  The test-helper change exposed it: a fake server in `testhelpers/` had held the same endpoint id,
  `GET /{param}`. Now a `%s` or `%v` whose argument the code holds takes its value, under the same rule as an
  interpolation: a whole-segment constant, or a path at the start, and never in a generic wrapper.

Diff against `2026-10-17-v2-baseline-15`, judged item by item:

- zulip: −9 calls (the test client); the zilencer call moves to `GET /api/v1/zulip-services/verify/{param}`, a real
  call to a remote server, judged right.
- mattermost: −33 routes, the Cypress webhook server, and −31 calls from the e2e helpers. Those calls were counted
  by the baseline (the TS generated clients update says so). They are test code, so they leave, like `e2e/`
  before them. None was in an expected list. 9 of them were in the sample: 7 judged right as HTTP and 2 wrong.
- kratos: −5 routes and −6 calls from `testhelpers/`; `GET /schemas` and `GET /schemas/{id}` come out (both in
  the spec).
- fastapi: −7 calls, the `scripts/playwright` screenshot scripts.
- hono-examples: `GET /post/{id}` right.

No repository regressed against its expected list. Go route recall goes from 97.8 % to 98.0 % (1502/1533), and the
sampled precision of Python calls from 69.7 % to 100 % (17/17). HTTP extraction took 105.2 s.

New baseline: `2026-10-17-v2-baseline-16`.

## Closing H2b (2026-10-17)

H2b set out to widen the corpus and to evolve the extractor on the categories that are general rules. The corpus
went from 15 repositories to 42, 41 with an expected list. The extractor went through Phase 4's items in the order
the v2 ranking set, with one change of order by portfolio priority (H2-D18: .NET first, then Go and Python, then
TS).

### Where it started and where it ends

Same expected lists (today's), same 38 repositories (the three .NET apps added later are left out), the first v2 run
(`2026-10-15-v2-baseline`) against the last (`2026-10-17-v2-baseline-16`):

| Language | Kind | P expected, first → last | R expected, first → last |
|---|---|---|---|
| C# | routes | 72.1 % → 100 % | 55.6 % → 93.1 % (134/144) |
| C# | calls | 62.2 % → 100 % | 48.3 % → 96.6 % (56/58) |
| Go | routes | 20.4 % → 99.1 % | 9.4 % → 98.0 % (1502/1533) |
| Go | calls | 100 % → 100 % | 8.2 % → 93.6 % (103/110) |
| Python | routes | 26.1 % → 99.0 % | 2.0 % → 21.3 % (387/1815) |
| Python | calls | 100 % → 100 % | 66.7 % → 66.7 % (2/3) |
| TS/JS | routes | 7.0 % → 95.6 % | 4.3 % → 85.4 % (944/1105) |
| TS/JS | calls | 44.6 % → 91.4 % | 6.1 % → 87.4 % (361/413) |

Python route recall is held down by Django, which has no scanner: 1420 of the 1815 expected routes are zulip's and
netbox's urlconfs. Without them, Python route recall goes from 9.1 % to 98.0 % (387/395).

Sampled precision covers whole repositories, not only what a spec lists. On all 42 repositories it is:

| Language | Routes | Calls |
|---|---|---|
| C# | 100 % (152/152) | 100 % (100/100) |
| Go | 88.1 % (192/218) | 100 % (16/16) |
| Python | 98.9 % (90/91) | 100 % (17/17) |
| TS/JS | 71.9 % (115/160) | 71.7 % (104/145) |

- Go routes: chi's mountable profiler (library code, 13), alertmanager's v1 routes passed to a method through a
  struct field (7), and four small cases.
- TS/JS routes: the framework's own test apps under `integration/` (nest, fastify; 20), fastify-demo's autoload by
  folder (10), express-boilerplate's routers mounted in a loop (8), and NodeBB's runtime prefixes (5).
- TS/JS calls: a client wrapper that prepends its prefix, in NodeBB, argo-cd's UI and mattermost (37), and Ghost's
  `adminUrl` from `window.location` (4).

### Where each remaining gap goes

| Category | Wrong | Missed | Repos | Goes to |
|---|---|---|---|---|
| `django-urlconf` | 0 | 1420 | 2 | F1.14 (new scanner), when a portfolio asks |
| `prefix-as-param` | 9 | 119 | 3 | limitation: a prefix only known at runtime (NodeBB plugin names); `/{param}/x` links nothing |
| `prefix-in-client-wrapper` | 37 | 34 | 3 | F1.14, TS/JS client wrappers (C#'s path; TS now resolves imports) |
| `client-wrapper` | 0 | 16 | 2 | F1.14, same item |
| `test-app-folder` | 20 | 0 | 2 | F1.1, per-repository excludes (`.aidd/index.yaml`) |
| `multi-app-repo` | 0 | 16 | 7 | F1.14, the model: the endpoint id is per repository |
| `prefix-by-folder` | 10 | 14 | 1 | F1.14, routes by folder (`@fastify/autoload`) |
| `prefix-other-file` | 9 | 14 | 2 | F1.14, routers kept in a list and mounted in a loop (express-boilerplate) |
| `library-code` | 13 | 0 | 1 | limitation: a library's routes, mounted by its users |
| `prefix-in-router-type` | 1 | 12 | 1 | F1.14, a router type that adds its prefix (kratos `RouterAdmin`) |
| `router-as-param` | 10 | 0 | 3 | F1.14 (a method called through a typed struct field, closures called inside groups); gotify's plugin router by interface is a limitation |
| `route-by-name-convention` | 0 | 10 | 1 | convention (F0.4.5 `route_patterns`) |
| `route-by-file-path` | 0 | 9 | 1 | F1.14, Next.js file routes |
| `field-in-interpolation` | 4 | 1 | 2 | limitation: Ghost's `adminUrl` comes from `window.location` |
| the rest (`router-from-registry`, `custom-registrar`, `url-in-field`, `url-from-helper`, `url-object-builder`, and single cases) | 0 | 27 | — | F1.14, when a portfolio shows them |

The categories that leave the extractor keep the destinations v2 gave them. A prefix carried in the base URL goes
to the linker (F0.5, done: suffix match with a hint). A spec as the source of routes goes to F2.1. Generated
servers are in part extracted now (grpc-gateway, go-swagger), and the rest goes to F2.1.

## The hold-out set (2026-10-17)

Every rule above was written against the 42 corpus repositories, so their numbers can flatter the extractor. The
hold-out measures, once, 16 repositories the rules never saw, chosen for the portfolio's profile (H2-D18) from a
list the author gathered, and pinned in `HOLDOUT` (`http_corpus.py --holdout`). The protocol (H2-D20):

- each expected list was written **before** the extractor ran on the repository. Nine come from a committed spec
  checked against the code (Umbraco, Radarr, Kavita, btcpayserver, photoprism, memos, sftpgo, vikunja,
  go-boilerplate); seven were read in the code within a scope fixed first (directus, Elsa, Smartstore, mealie,
  open-webui, outline, docmost);
- precision was judged at the source on a seeded sample of 20 routes and 20 calls per repository (`seed 0`);
- the extractor is the one of `c4ecc34`, and no rule changes because of this result. A list error found while
  judging was corrected (H2-D15): btcpayserver gained 42 real Greenfield routes its fragments leave out and lost 10
  that no code registers, directus gained 8, Radarr 1.

A spec often covers one URL subspace while the same files serve others, such as a web UI or debug pages. For those
repositories the list's precision counts only paths under that subspace. This is a new `scope_paths` field of the
gabarito (`corpus_metrics.py`), and the sample judges the rest.

### Corpus against hold-out

| Language | Kind | Corpus: P sample · P list · R list | Hold-out: P sample · P list · R list |
|---|---|---|---|
| C# | routes | 100 % · 100 % · 96.9 % | 63.3 % (76/120) · 83.8 % · 48.5 % (1053/2170) |
| C# | calls | 100 % · 100 % · 99.0 % | 91.1 % (41/45) · — · — |
| Go | routes | 88.1 % · 99.1 % · 98.0 % | 50.6 % (39/77) · 28.0 % · 19.7 % (128/651) |
| Go | calls | 100 % · 100 % · 93.6 % | 100 % (10/10) · — · — |
| Python | routes | 98.9 % · 99.0 % · 98.0 % (without Django) | 82.5 % (33/40) · 86.3 % · 83.8 % (145/173) |
| Python | calls | 100 % · 100 % · 66.7 % | 100 % (9/9) · — · — |
| TS/JS | routes | 71.9 % · 95.6 % · 85.4 % | 88.3 % (53/60) · 98.3 % · 74.1 % (289/390) |
| TS/JS | calls | 71.7 % · 91.4 % · 87.4 % | 47.0 % (77/164) · 77.8 % · 76.5 % (513/671) |

| Repo | Routes | Calls | P routes sample | P / R routes list | P calls sample | P / R calls list |
|---|---|---|---|---|---|---|
| Umbraco-CMS | 173 | 522 | 0 % (0/20) | 0 % / 0 % (528) | 100 % (20/20) | 100 % / 100 % (513) |
| Radarr | 39 | 2 | 30 % (6/20) | 17.9 % / 2.9 % (239) | 50 % (1/2) | — |
| Kavita | 522 | 306 | 100 % (20/20) | 100 % / 100 % (522) | 0 % (0/20) | — |
| btcpayserver | 636 | 23 | 95 % (19/20) | 100 % / 98.7 % (236) | 85 % (17/20) | — |
| Smartstore | 314 | 5 | 95 % (19/20) | 98.6 % / 52.8 % (551) | 100 % (5/5) | — |
| Elsa 3 | 24 | 239 | 60 % (12/20) | 0 % / 0 % (94) | 100 % (20/20) | — |
| photoprism | 165 | 66 | 0 % (0/20) | 0 % / 0 % (165) | 30 % (6/20) | — |
| vikunja | 202 | 228 | 10 % (2/20) | 0 % / 0 % (172) | 100 % (20/20) | — |
| memos | 8 | 4 | 100 % (8/8) | — / 0 % (185) | 100 % (4/4) | — |
| sftpgo | 285 | 3 | 100 % (20/20) | 100 % / 100 % (119) | 100 % (3/3) | — |
| go-boilerplate | 9 | 0 | 100 % (9/9) | 100 % / 90 % (10) | — | — |
| mealie | 268 | 14 | 65 % (13/20) | 64.1 % / 59.4 % (69) | 92.9 % (13/14) | — |
| open-webui | 595 | 617 | 100 % (20/20) | 100 % / 100 % (104) | 35 % (7/20) | 0 % / 0 % (98) |
| directus | 260 | 78 | 100 % (20/20) | 98.1 % / 87.3 % (292) | 100 % (20/20) | — |
| outline | 26 | 90 | 65 % (13/20) | — / 0 % (64) | 5 % (1/20) | 0 % / 0 % (19) |
| docmost | 149 | 148 | 100 % (20/20) | 100 % / 100 % (34) | 0 % (0/20) | 0 % / 0 % (41) |

### What it says

- **The corpus numbers overfit, and most in the portfolio's first language.** C# route recall falls from 96.9 % to
  48.5 %, and Go's from 98.0 % to 19.7 %. The rules generalize where a repository routes the way the corpus
  did: Kavita, sftpgo, open-webui, docmost and btcpayserver come out whole. They fail where it routes another way
  that is common in real applications:
  - C#: route attributes of the project's own (Umbraco's `[VersionedApiBackOfficeRoute("x")]`, Radarr's
    `[V3ApiController]` and `[RestGetById]`);
  - C#: OData conventions (Smartstore);
  - C#: FastEndpoints behind the project's own base class (Elsa's `ElsaEndpoint<T>`);
  - Go: a router variable assigned from a call in another file (photoprism's `APIv1`);
  - Go: a newer generated-gateway form (memos).
- **Two precision defects** that the corpus never showed:
  - vikunja's `a := e.Group("/api/v1"); registerAPIRoutes(a)` applies the prefix twice;
  - an outbound call in vikunja's Planka migration (`c.get("/api/projects", nil, out)`) is read as a route.
- **What held up:**
  - TS routes: 98.3 % against the lists, with the mount graph and Nest's `setGlobalPrefix` on unseen code;
  - generated clients: Umbraco's hey-api SDK, 513 of 513, through the request described by an object;
  - calls with literal paths in every language.
- **Calls lose the client's base path.** Kavita's `this.baseUrl` from the environment, outline's `ApiClient` with
  `baseUrl` `/api`, docmost's `axios.create({ baseURL: "/api" })` in another file, and open-webui's constants
  imported through SvelteKit's `$lib` alias all drop it: this is `prefix-in-client-wrapper`, already the largest
  call gap in the corpus.

### Gaps by category (hold-out)

| Category | Wrong | Missed | Repos | What it is | Goes to |
|---|---|---|---|---|---|
| `custom-route-attribute` | 33 | 760 | 2 | The project's own route attribute: Umbraco `[VersionedApiBackOfficeRoute("data-type")]` (builds `/umbraco/management/api/v{version}/x`), Radarr `[V3ApiController]`, `[RestGetById]` (`IRouteTemplateProvider`) | F1.14, .NET |
| `odata-convention` | 0 | 260 | 1 | OData actions without a template (`Post`, `Put(key)`, ..) routed by convention under the route component `odata/v1` (Smartstore) | F1.14, .NET |
| `prefix-doubled` (FP) | 16 | 172 | 1 | vikunja: a group with a prefix passed to a function gets the prefix twice (`/api/v1/api/v1/..`) | F1.14, Go, first |
| `prefix-other-file` | 27 | 165 | 2 | photoprism `APIv1 = router.Group(conf.BaseUri(..))` assigned in another file; outline's `mount("/auth", auth)` (koa-mount) | F1.14, Go and TS |
| `endpoint-class-own-base` | 0 | 94 | 1 | Elsa's FastEndpoints endpoints derive from `ElsaEndpoint<T>`, the project's own base; the global `RoutePrefix` (`elsa/api`) is not applied either (`global-prefix`, 5 wrong) | F1.14, .NET |
| `gateway-verb-constant`, `connect-rpc` | 0 | 185 | 1 | memos: `mux.Handle(http.MethodGet, pattern_X, ..)` (the verb as a constant; H2b's rule wants the literal) and connect-go handlers | F1.14, Go (gateway); F2.1 (Connect, from the proto) |
| `prefix-in-client-wrapper`, `const-other-file` | 72 | 158 | 4 | The client's base path held by the code but lost (see above) | F1.14, TS client wrappers |
| `no-leading-slash` | 0 | 64 | 1 | Koa paths without `/` (`router.post("documents.info", ..)`, outline) | F1.14, TS |
| `custom-router-class` | 7 | 28 | 1 | mealie's `UserAPIRouter(prefix=..)`, `AdminAPIRouter`: subclasses of `APIRouter` are not routers | F1.14, Python |
| `search-verb`, `route-constraint-syntax`, `use-as-route`, `router-from-factory`, `optional-param` | 1 | 40 | 3 | directus `router.search(..)`, `/:pk(${UUID_REGEX})`, `router.use('/', handler)`; C# `{id?}` short form (btcpayserver); Radarr `{**path:regex(..)}` | F1.14 |
| `url-from-helper`, `query-in-variable`, `field-in-interpolation` | 18 | 0 | 3 | photoprism `this.getEntityResource() + "/like"`; btcpayserver `$"api/v1/..{queryString}"`; mealie `${this.baseRoute}` | F1.14 |
| `partial-class-route`, `evidence-line`, `call-taken-for-route`, `test-client-in-source` | 4 | 0 | 4 | `[Route]` in another file of a partial class (btcpayserver); a route with the evidence of another line (Elsa's `Program.cs`); vikunja's Planka client; Radarr's test runner in `NzbDrone.Test.Common` | F1.14 |
| `prefix-as-param`, `root-route-dropped` | 4 | 1 | 4 | A prefix from options or a plugin host (Elsa OpenTelemetry, IconKit, vikunja plugins); chi root in a router built by a function | limitation / F1.14 |

The hold-out repositories are now known to the rules that will follow. When F1.14 works on them they become
corpus, and the next closing needs a new hold-out (H2-D20).

## F1.14, increment 1: the hold-out's precision defects and its .NET (2026-10-17)

F1.14 started where the hold-out pointed: the two precision defects first, then .NET, the portfolio's first stack
(H2-D18). Four hold-out repositories were worked on and moved to the corpus (now 46): vikunja, Umbraco, Radarr and
Smartstore. The next closing needs a new hold-out (H2-D20). Every rule below has a fixture case that fails without it.

**Precision.**

- **A group prefix belongs to its scope.** `group_prefix` was keyed by the variable's name across the file. So the
  parameter `a` of `registerAPIRoutes(a *echo.Group)` took the prefix of `a := e.Group("/api/v1")` in another
  function, and the prefix of the call on top. Now the key is (scope, name), the same key as the mount graph.
  Fields and expressions stay file-wide. This fixed 176 vikunja routes: `/api/v1/api/v1/..`, `/api/v2/api/v1/..` and
  `/dav/dav/..`.
- **A Go method that is not exported never registers a route.** `c.get("/api/projects", nil, out)` is vikunja's
  Planka client: a lowercase method belongs to the package, never to a framework. Only exported verbs register
  routes, and vikunja's 4 Planka GETs are calls again.
- **echo joins as written.** `u := a.Group("/user"); u.GET("s", h)` is `/users` in echo (`g.prefix + path`). gin
  and fiber put a slash in between. This was found once vikunja's prefixes were right.

**.NET.**

- **The project's routing attributes.** An attribute class of the repo qualifies when it derives from
  `RouteAttribute` or `Http*Attribute`, implements `IRouteTemplateProvider` or `IActionHttpMethodProvider`, or
  derives from another such attribute. It is published as a recipe: its constructor's parameters with their
  defaults, what it hands its `base(..)`, its `Template` and its `HttpMethods`. Each use, on a controller or an
  action, keeps its arguments, and `compose` fills the recipe. A constant from another project is read by its
  qualified name, and only when the repo gives it one value. Examples: Radarr's `[V3ApiController]` and
  `[RestGetById]`; Umbraco's `[VersionedApiBackOfficeRoute(Constants.UdiEntityType.DataType)]`, two levels over
  `RouteAttribute`.
- **Asp.Versioning.** `v{version:apiVersion}` takes the versions the action (`[MapToApiVersion]`) or the controller
  (`[ApiVersion]`) declares, in the URL's form (`1.0` → `1`). A controller that declares none gets the default
  version: the repo's `DefaultApiVersion`, else 1.0.
- **OData's conventions.** In a controller under `ODataController` or `[ODataRouteComponent]`, `Post` lands on the
  entity set, and `Put`/`Patch`/`Delete`/`Get` with a `key` land on `Set({key})`. An untemplated action the
  conventions do not route is no route: Smartstore's keyless stubs.
- **Inheritance as the framework counts it.** The `[Route]` and the actions of the base classes are taken up to
  four levels, which closes item 1's "more than one level". A class that is not a controller by itself still
  publishes its actions to the classes derived from it (Radarr's `ProviderControllerBase`). `[NonAction]` takes an
  action out there and below (Radarr's `ReleaseControllerBase`). An action is its name plus its parameter count, so
  `[NonAction]` on one overload keeps the other.
- **Templates.** An action with `[Route]` and no verb is ANY, one route per `[Route]`. `[HttpGet("")]` written out
  is the root. A parameter is read with balanced parentheses: `{**path:regex(^(?!(api|feed)/).*)}` → `{path}`, and
  `{action=Index}` is the action. `$"{{{nameof(id)}:guid}}"` is `{id:guid}`: the C# grammar takes it whole as text.
  An attribute counts by its simple name (`[Microsoft.AspNetCore.Mvc.HttpGet]`). A constant of several segments
  without a leading slash (`"security/back-office"`) is kept apart, so that only these recipes read it.
- **The scorer** matches an ASP.NET route without case, as the linker does. Radarr's `[controller]` gives
  `AutoTagging`, and its spec writes `autotagging`.

| Repo | At the hold-out (list · sample) | Now (list · sample) |
|---|---|---|
| vikunja (Go) | P 0% · R 0% · 2/20 | P 100% · R 89.8% · 18/19 |
| Radarr | P 17.9% · R 2.9% · 6/20 | P 100% · R 100% · 20/20 |
| Smartstore | P 98.6% · R 52.8% · 19/20 | P 100% · R 100% · 19/20 |
| Umbraco | P 0% · R 0% · 0/20 | P 0% · R 0% · 0/20; with its token read as `/umbraco`, P 100% · R 99.8% |

The hold-out column is the hold-out run scored against the gabaritos as written then, before the corrections
below.

**What remains in these repositories.**

- **Umbraco.** Every route keeps the template's first segment, the `[umbracoBackOffice]` token. Umbraco's own
  `UmbracoBackofficeToken` convention fills it at startup from `DefaultUmbracoPath` (`route-token-convention`, a
  limitation). Dropping the token would let the linker's suffix match find these routes, but the path would then
  hide a segment the code holds: an open choice.
- **`/umbraco/login`.** An action with no attribute in a controller with `[Route]` (`action-without-attribute`).
- **vikunja's migrators.** Their routes are `"/"+ms.Name()+"/auth"`, a name returned through an interface by the
  value a closure builds (`segment-from-method`). Neither the tree nor SCIP gives it.
- **vikunja's CSV migrator.** Its group goes to a method of a value of declared type (`router-as-param`, item 2).

**Gabarito corrections (H2-D15).**

- **vikunja.** Its spec turned out stale once the routes were visible. `/{username}/avatar` is `/avatar/:username`,
  `PUT /labels/{id}` is `POST /labels/:label`, and `/backgrounds/unsplash/image/..` is `images/..`. The spec's 4 are
  removed and the code's added, along with 15 real routes the spec lacks (bots, sessions, docs, ws, metrics, ..).
- **Smartstore.** 9 controllers declare `Put()`/`Patch()`/`Delete()` without a key, as stubs hidden from the API.
  The 25 `Set({key})` entries I had written for them are removed.

**Diff against `2026-10-17-v2-baseline-17`.** 41 repositories are identical. bitwarden gains `ANY /Error`,
`/error` and `/Home/Error`, `[Route]`-only error pages, judged right. vikunja gains `GET /users` in place of
`/user/s`. No repository regressed against its expected list.

**Totals.** C# route recall over the list is 66.6% (1075/1613), and Umbraco's 528 entries all miss on the token.
Without Umbraco it is 99.1% (1075/1085), at 100% precision. Go is 97.1% (vikunja's limitations come in), Python
without Django and TS/JS are unchanged. HTTP extraction took 148 s.

New baseline: `2026-10-17-v2-baseline-18`.

## F1.14, increment 2: the rest of the hold-out's .NET (2026-10-18)

Elsa and btcpayserver moved from the hold-out to the corpus (48 repositories; the hold-out keeps 10). Each rule below
is the framework's own, read from the tree, and has its fixture (`route-patterns-cs`,
`route-patterns-cs-fastendpoints`).

- **A route token of the project.** A `[x]` in a template that is not one of the framework's (`controller`,
  `action`, `area`, `page`, `handler`) takes the value its convention is registered with. The convention is a class
  of the repo that implements `IApplicationModelConvention` (or the controller and action ones) and rewrites
  `AttributeRouteModel`. Of the two arguments of `Conventions.Add(new T(a, b))`, one is the token's name and the
  other its value, read as the attribute recipes read theirs: a constant of another project by its qualified name, a
  local declared above, `TrimStart` with the characters of a `char[]` field, a constant built from others. Umbraco's
  `[umbracoBackOffice]` is `DefaultUmbracoPath.TrimStart(TildeForwardSlash)`, so `umbraco`. A value from
  configuration, or two registrations with different values, leave the token as written.
- **FastEndpoints behind the project's bases.** A class that overrides `Configure()` under a base of the repo keeps
  its routes pending, and `compose` takes them when the walk up the bases reaches one over FastEndpoints' own. A name
  several classes share (Elsa's `ElsaEndpoint<TRequest>`, `<TRequest, TResponse>`) counts when each of them does.
  `Routes(..)` and `Verbs(..)` are read in either order, the verb also by its qualified name
  (`FastEndpoints.Http.POST`), the path also without a leading slash.
- **FastEndpoints' global `RoutePrefix`.** `config.Endpoints.RoutePrefix = x` goes before every FastEndpoints route
  of the repo when the repo gives it one value: a literal, a constant, or a parameter of the method around it. For a
  parameter, the value is what each call in the file passes, and the declared default where the caller passes its
  own parameter on (Elsa's `MapWorkflowsApi(.., string routePrefix = "elsa/api")`). A value a host passes from
  configuration is not read: the route is the code's default. `RoutePrefixOverride(..)` takes its place.
- **The halves of a `partial` class are one class.** A half without a `[Route]` of its own looks up the class itself
  by name before its bases: btcpay's `UIStoresController.Rates.cs` is under `/stores`, `UIManageController`'s halves
  under `account/{action}`.
- **An action with no routing attribute**, by ASP.NET's own test (`DefaultApplicationModelProvider`): a public
  instance method that is not abstract, generic, `Dispose` or `[NonAction]` is an action at the controller's route,
  with any verb. An `override` takes the attributes of the method it overrides. `[Route(X)]` reads a constant of the
  class: `/umbraco/login`.
- **`[Area]` is inherited.** A controller without its own takes the nearest base's, or the other `partial` half's:
  Smartstore's module controllers under `AdminController`'s `[Area("Admin")]` (20 routes with `[area]` before).
- **The evidence of a minimal API route** is the line `MapGet` is written on. In Elsa's workbench `Program.cs`, an
  `#if` between two `else if` loses the C# grammar, and the receiver of `app.MapGet(..)` took in the 430 lines above:
  the evidence said 364, not 797.

| Repo | Before (list · sample) | Now (list · sample) |
|---|---|---|
| Umbraco (after increment 1) | P 0% · R 0% · 0/20 | P 100% · R 100% · 20/20 |
| Elsa (at the hold-out) | P 0% · R 0% · 12/20 | P 100% · R 100% · 18/20 |
| btcpayserver (at the hold-out) | P 100% · R 98.7% · 19/20 | P 100% · R 98.7% · 20/20 |

Elsa's list had one route, `/package/version` without the prefix. The samples keep their items, each at the path its
line gives now, and the ones that changed were judged again: Umbraco's 20 (19 in the spec, and
`/umbraco/delivery/api/v2/content/items`, real, outside its scope), Elsa's 6 (five under the global prefix, and the
workbench probe at its right line), btcpay's 1.

**What the action rule found elsewhere.** bitwarden `ANY /bitpay`: `BitPayController.GetIdsFromPosData`, a public
helper ASP.NET routes as an action. Smartstore: 7 module actions with only filter attributes (`[LoadSetting]`).
Elsa: Studio's `CultureController.Set`. Umbraco: `ANY /umbraco/management/api/v1/document`, `DocumentUrlController`'s
`[Obsolete]` overload with no routing attribute, which `[ApiExplorerSettings(IgnoreApi = true)]` hides from the spec
only; added to the gabarito (H2-D15). All judged right.

**What remains in these repositories.**

- **A prefix from options or configuration** (`prefix-as-param`). Elsa's OpenTelemetry collector maps under
  `(IsNullOrWhiteSpace(o.HttpEndpointPath) ? "/elsa/otlp/v1" : o.HttpEndpointPath).TrimEnd('/')`; Smartstore's
  IconKit under `MapGroup(options.RoutePrefix)`. The code fixes no value there.
- **btcpay's three `optional-param`**, as at the hold-out.

**Diff against `2026-10-17-v2-baseline-18`.** 43 repositories are identical. Umbraco's 538 routes take `/umbraco`
and gain 2; Smartstore's 20 module routes take their area and gain 7; bitwarden gains 1; Elsa and btcpayserver come
in. The hold-out's other 10 are identical to its last run. No repository regressed against its expected list.

**Totals.** C# route recall over the list is 99.3% (1931/1944) at 100% precision, with Umbraco, Elsa and btcpay in;
the checked sample is 98.8% (249/252). Go, Python and TS/JS are unchanged. HTTP extraction took 160 s.

New baseline: `2026-10-18-v2-baseline-19`.

## F1.14, increment 3: the hold-out's Go (2026-10-18)

memos and photoprism moved from the hold-out to the corpus (50 repositories; the hold-out keeps 8). Each rule below
is Go's or the framework's own, read from the tree, and has its case in `route-patterns-go`, which fails without it.

- **grpc-gateway v2.** v2's generated code registers with `mux.Handle(http.MethodGet, pattern_X, h)`: the verb is
  net/http's constant, where v1 wrote `"GET"`, and it is read as every other verb constant. A capture with literals
  keeps them, with the variable at each wildcard: `{name=memos/*}` is `/api/memos/{name}`, not `/api/{name}`.
- **Go's `=` declares nothing.** A name belongs to the function that declares it: a parameter, `:=`, `var`, `const`,
  or a `range` with `:=`. A function that only assigns a name with `=` assigns the package's. photoprism's
  `APIv1 = router.Group(conf.BaseUri(config.ApiUri), ..)` in `start.go` sets the package variable that `routes.go`
  declares (`var APIv1 *gin.RouterGroup`), not a local of `Start`.
- **A group in a package variable carries its prefix to other files.** Its routes are registered by the functions
  it is handed to (`api.GetAlbums(APIv1)`, 80 files of `internal/api`). The group's own prefix goes on the edge it
  publishes to its parent, not on what is registered on it in that file, so the routes behind each parameter take it
  too. It is a flag of the Go scanner; the other scanners keep the prefix where they had it.
- **A function that returns its parameter is its argument.** When every `return` of a function is one of its
  parameters, or ends with it (`return c.BasePath() + res`), a call to it is the argument it passes: `/api/v1` for
  `conf.BaseUri(config.ApiUri)`. What comes before is the deployment's (`SiteUrl`, `BasePath`), and the route is the
  code's default, as with Elsa's `RoutePrefix`. The function is found in the file's package, through the import of
  `pkg.F`, or for a method by its name when it is unique in the repo.
- **`Match` takes its verbs from a variable.** `router.Match(MethodsPutPost, "/batch/photos/edit", h)` reads the
  `[]string{http.MethodPut, http.MethodPost}` of a package variable in another file, of an imported `pkg.X`, or the
  literal itself. Before, a `Match` whose verbs were not a literal list was `ANY`.

| Repo | Before (list · sample) | Now (list · sample) |
|---|---|---|
| memos (at the hold-out) | P — · R 0% · 8/8 | P 100% · R 49.7% · 20/20 |
| photoprism (at the hold-out) | P 0% · R 0% · 0/20 | P 97.5% · R 97.6% · 19/20 |

memos's list had none of the gateway's 92 routes; the 93 it still misses are the Connect copies of the same RPCs.
photoprism's 161 routes had no `/api/v1`. photoprism's sample keeps its items, each at the path its line gives now
(19 take `/api/v1`). memos's had the 8 net/http routes the extractor found before the gateway was read: it was drawn
again at 20 with the same seed, all gateway routes.

**Gabarito corrections (H2-D15).** memos: the spec's GET and PATCH `/api/instance/{instance}/*` are
`/api/{name=instance/settings/*}` in `instance_service.proto`, `/api/instance/settings/{name}`, which gnostic
renders without the second literal. photoprism: POST `/api/v1/oauth/logout` and `/oauth/userinfo` are routes, because
`OAuthLogout` and `OAuthUserinfo` call `OAuthLogoutPost(router)` and `OAuthUserinfoPost(router)` themselves. gotify:
`HEAD /health`, from `g.Match([]string{"GET", "HEAD"}, "/health", ..)`, is outside its swagger.

**What remains in these repositories.**

- **memos's 93 Connect RPCs** (`connect-rpc`): `POST /memos.api.<Service>/<Method>`, registered by connect-go's
  generated handlers. They stay for F2.1, with the proto as a source.
- **photoprism's `SearchFolders`** (`segment-from-param`, 4 missed and 2 extra): a helper takes the folder's segment
  as a parameter and each caller passes a literal (`originals`, `import`). The routes come out as
  `/api/v1/folders/{param}`.
- **photoprism's `/docs`** (`registrar-in-func-var`, 2 extra): registered only in the debug build. `routes.go`
  calls `registerAPIDocs(APIv1)`, a function variable that a build-tagged `init()` sets to `api.GetDocs`, so the
  routes come out without the prefix.
- **photoprism's web client** (`url-from-helper`): 14 of the 20 calls checked build the URL in a method of the model
  (`$api.post(this.getEntityResource() + "/like")`), which each subclass answers. That is TS's turn.
- **A gRPC custom verb after a literal prints as a parameter.** `normalize_path` reads the `:transcribe` of
  `/api/ai:transcribe` as an Express parameter, `/api/ai{transcribe}` (6 memos routes; `{name}:accept` was already
  spared). Both sides normalize alike, so the pair matches, but the path is wrong. The syntax cannot tell: Express
  and httprouter accept `/user_:name`. The source can: an OpenAPI path and a gateway pattern have no `:` parameters. It is recorded as a debt
  (ROADMAP, F1.14 item 7).

**Diff against `2026-10-18-v2-baseline-19`.** 47 repositories are identical. gotify's two `Match` routes take their
verbs (`ANY /health` is GET and HEAD; `ANY /mcp` is GET, POST and DELETE). memos and photoprism come in. The
hold-out's other 8 are identical to its last run. No repository regressed against its expected list.

**Totals.** Go route precision over the list is 99.1% (1921/1938) and recall 92.9% (1926/2073), with memos's 93
Connect RPCs among the misses; without them, 97.3% (1926/1980). Before this increment it was 99.2% (1668/1681) and
97.1% (1670/1720). The Go checked sample is 89.9% (249/277), from 88.6% (210/237). C# and Python are unchanged; the
TS/JS calls sample is 73.0% (149/204) with photoprism's web client in. HTTP extraction took 178 s: the 48
repositories of before took 167 s against 160 s, the same ~5% in repositories the change does not touch.

New baseline: `2026-10-18-v2-baseline-20`.

## F1.14, increment 4: the hold-out's Python (2026-10-18)

mealie moved from the hold-out to the corpus (51 repositories; the hold-out keeps 7). The rule has its cases in
`route-patterns-py` (`app/crossfile/routers.py` and the four routes modules on it), which fail without it.

- **A router class of the project.** `router = UserAPIRouter(prefix="/recipes")` builds a router when the class's
  bases reach the framework's router (`APIRouter`, `Blueprint`, `Router`) or application (`FastAPI`, `Flask`, ..).
  The class is found in the file's directory, through the import by name (`from ..routers import UserAPIRouter`), or
  through the imported module (`routers.AdminAPIRouter`). A base defined in another file is looked up by its name,
  when it is the only class of that name in the repo. The constant pass records each class's bases and what its
  `__init__` hands `super().__init__` as `prefix` or `url_prefix`; the first `__init__` up the bases decides. A
  literal is the prefix. A parameter is what the call passes for it, by name or position, else its default
  (mealie's `def __init__(self, tags=None, prefix: str = "", **kwargs)` with `super().__init__(prefix=prefix, ..)`).
  Without an `__init__` of its own, or with one that passes `**kwargs` on without naming the prefix, the call reads
  as the base's would.

| Repo | Before (list · sample) | Now (list · sample) |
|---|---|---|
| mealie (at the hold-out) | P 64.1% · R 59.4% · 13/20 | P 100% · R 100% · 20/20 |

87 mealie routes took their router's prefix (`/api/exports` is `/api/recipes/exports`, `/api/about` is
`/api/admin/about` under `AdminAPIRouter(prefix="/admin")`), and none was lost. 18 more come out: the roots
`@router.get("")` of routers whose prefix is now known (`/api/recipes/timeline/events`), and routes of different
files that had collapsed into one endpoint at a shared prefix-less path (`GET /api/{slug}` and
`GET /api/{item_id}`). Each of the 105 was read against its router in the code. The sample keeps its items, each at the path its line
gives now: 3 in the gabarito, 4 outside its scope judged from the code, all right.

**What the rule found elsewhere.** CTFd builds its application as `app = CTFdFlask(__name__)`, a subclass of
`Flask`. Now that it is the application, the root of the `views` blueprint registered on it,
`@views.route("/", defaults={"route": "index"})`, is a whole route: `GET /`, right, outside the gabarito's scope.

**Diff against `2026-10-18-v2-baseline-20`.** 49 repositories are identical. CTFd gains `GET /`, and mealie comes
in. The hold-out's other 7 are identical to its last run. No repository regressed against its expected list.

**Totals.** Python route precision over the list is 99.1% (457/461) and recall 24.2% (456/1884), from 99.0%
(388/392) and 21.3% (387/1815); the recall is low because zulip's and netbox's Django routes have no scanner yet.
The Python checked sample is 99.1% (110/111), from 98.9% (90/91). C#, Go and TS/JS routes are unchanged; the TS/JS
calls sample is 73.7% (157/213) with mealie's web client in. HTTP extraction took 179 s.

New baseline: `2026-10-18-v2-baseline-21`.

## F1.14, increment 5: the hold-out's TS/JS (2026-10-18)

outline, directus, docmost and open-webui moved from the hold-out to the corpus (55 repositories; the hold-out keeps
3: go-boilerplate, Kavita and sftpgo). Each rule below has its case in `route-patterns-ts` (or
`test_resolve_ts.py`), which fails without it.

**Routes.**

- **Koa's relative paths.** In a file that imports `@koa/router` or `koa-router`, a path without its leading slash
  on a router of the file is like a sub-router's root: a route only once a mount gives it a prefix, which Koa puts
  before it as written (`router.use("/", documents.routes())` and `router.post("documents.info", ..)` is
  `/documents.info`). A router mounted nowhere serves nothing at it. `x.routes()` and `x.middleware()` handed to
  `use` are the router itself, and `use(mount("/api", api))`, with `mount` imported from `koa-mount`, is
  `use("/api", api)`.
- **Express's `SEARCH`.** `router.search(path, ..)` on a router of the file is `SEARCH`; on any other receiver it is
  nothing. A router's verb is never a project's mount wrapper: directus's `router.search('/:collection',
  collectionExists, ..)` disappeared as a wrapper candidate once its middleware resolved to another file.
- **A regex after a parameter.** `/:pk(\d+)` and `` `/:pk(${UUID_REGEX})` `` are `/{pk}`: masked and normalized like
  Hono's `:id{..}`, but not after a word, so ASP.NET's `{name:minlength(1)}` keeps its meaning. path-to-regexp 8's
  optional wildcard `{/*path}` is the wildcard (`/mcp/{rest}`, not `/mcp/{/{rest}}`).

**Calls: the client's base.**

- **A module's client with a base.** The constant pass records, per file and name, `X.create({ baseURL })` or
  `X.extend(..)` (axios, ofetch; `prefixUrl` for ky and got), and `new C(..)` of a class of the directory whose base
  is a field: `baseUrl = "/api"`, or the constructor's `this.baseUrl = options.baseUrl || "/api"` (outline's
  ApiClient), where the option the call passes wins over the default. `export default api` names it too. A call on
  that receiver, in the file or through an import, is under the base, joined with a slash as axios joins them:
  docmost's `api.post("/pages/info")` on `axios.create({ baseURL: "/api" })` in `@/lib/api-client` is
  `/api/pages/info`. Only a path: a base URL's host is the linker's.
- **Not when the url is rewritten.** A request interceptor of the client that assigns `config.url` or `baseURL`
  (dispatch: `` config.url = `${currentOrganization}${config.url}` ``) means the base is not all that goes before
  the path. The call stays as written, which the linker's suffix match links to `/api/v1/{organization}/..`.
- **A known client is no router.** `api.post("/comments", data)` was dropped because a variable as the last
  argument looks like a route's handler. On a receiver known as a client it is a request, whatever its name.
- **A constant built as a template is a constant** (`` `${WEBUI_BASE_URL}/api/v1` `` as
  `WEBUI_BASE_URL + "/api/v1"`), and `${X}` imported from another file is read there, as `pkg.X` already was.
  SvelteKit's `$lib` is `src/lib`, its default. A ternary between nothing and a query string
  (`` ${query ? `?${query}` : ''} ``) is the query, not a segment.
- **Found on the way:** `await api.post<T>(..)` parses with the `await` inside the callee, so the receiver read as
  `awaitapi`.

| Repo | Before (at the hold-out; list · sample) | Now (list · sample) |
|---|---|---|
| outline, routes | P — · R 0% · 13/20 | P 100% · R 100% · 20/20 |
| outline, calls | P 0% · R 0% · 1/20 | P 95.0% · R 100% · 19/20 |
| directus, routes | P 98.1% · R 87.3% · 20/20 | P 98.3% · R 99.0% · 20/20 |
| docmost, calls | P 0% · R 0% · 0/20 | P 100% · R 100% · 20/20 |
| open-webui, calls | P 0% · R 0% · 7/20 | P 99.0% · R 100% · 19/20 |

The samples keep their items, each at the path its line gives now, and the changed ones were judged again at the
source: outline's 7 routes take `/auth` or `/oauth` (koa-mount) and 18 calls take `/api`; docmost's 20 calls and 12
of open-webui's 13 take their base.

**Gabarito correction (H2-D15).** docmost: `POST /api/spaces/watched-ids`, from
`api.post<IPagination<string>>("/spaces/watched-ids")` in a file of the scope, which the first reading missed.

**What the rules found elsewhere.** dispatch: 3 calls with a variable last
(`` API.post(`/${resource}/${caseId}/exportTimeline`, data) ``), among them the one its gabarito listed as missed;
its calls are at 100% (16/16), still as written (the interceptor). directus: 17 calls of the app's stores
(`api.patch(`/settings`, updates)`), as written, since its base is `getRootPath()`. outline: 2 more calls of
`client`. All right.

**What remains in these repositories.**

- outline's `this.post("/batch")` inside ApiClient itself, without the base (`prefix-in-client-wrapper`): a class's
  own calls on `this`.
- open-webui's `` /register${searchParams} ``, a query held in a variable and glued to the path
  (`query-in-variable`); and `ANY /auths/mfa/{param}`, a helper that takes the path and the method (a client
  wrapper, F1.14 item 4).
- directus's `/graphql` mounted with `router.use` (`use-as-route`), `POST /auth/login` from a router factory
  (`router-from-factory`) and the SAML/OpenID routes under a provider name from the configuration.
- Koa joins a prefix and a relative path as written, so a non-`/` prefix would give `/apidocuments.info`; the
  extractor reads it with a slash. No repository does that.
- A client class is looked up in the directory of the instance, and the base must be a path.

**Diff against `2026-10-18-v2-baseline-21`.** 50 repositories are identical. dispatch gains 3 calls, and the four
come in. The hold-out's other 3 are identical to its last run. No repository regressed against its expected list.

**Totals.** TS/JS route precision over the list is 96.5% (1331/1379) and recall 89.0% (1331/1495), from 95.6%
(944/987) and 85.4% (944/1105); TS/JS calls are at 96.6% (1034/1070) and 95.3% (1034/1085), from 96.3% (874/908)
and 94.4% (874/926). The checked samples: TS/JS routes 79.5% (175/220), from 71.9% (115/160); calls 79.9%
(231/289), from 73.7% (157/213). open-webui's FastAPI backend (104 routes, 100%) moves Python to 99.3% (561/565) and
28.2% (560/1988). C# and Go are unchanged. The client bases cost about 5% of HTTP time on Ghost (15.1 s against 14.3
s, the same machine).

New baseline: `2026-10-18-v2-baseline-22`.

## F1.14, increment 6: FastEndpoints groups and custom verbs (2026-10-18)

This is the first increment of F1.14's close, on a new branch. It does item 1 and one debt of item 7. No repository
moves, since no hold-out repository was worked on. Each rule has its cases in a fixture, which fail without it.

- **FastEndpoints endpoint groups (item 1).** An endpoint's `Configure()` that calls `Group<Administration>()` puts
  the group's prefix before the routes declared above the call. FastEndpoints throws when there is none, so a route
  declared after it does not take it. The group is a class under `Group`, or under `SubGroup<TParent>`, whose
  constructor calls `Configure("admin", ep => ..)`. Its prefix is a literal or a constant. A sub-group's own prefix
  comes first, then its parent's, as FastEndpoints applies them. The global `RoutePrefix` goes before all of them
  (`/api/admin/billing/invoices`). A group that is not the repo's only class of that name, or whose prefix cannot be
  read, leaves the route as written. The argument of `Get`/`Routes` is always a route, so a literal of one segment
  (`Get("users")`) is now read too. Before, only a path with a slash was. No corpus repository uses groups; the cases
  are in `route-patterns-cs-fastendpoints`.
- **A custom verb after a name is not a parameter (item 7).** `normalize_path` read the `:transcribe` of memos'
  grpc-gateway `/api/ai:transcribe` as an Express parameter (`/api/ai{transcribe}`). Now a `:x` glued to a letter or a
  digit is a custom verb in the style of Google's APIs. After `/`, `-`, `.` or `_` it is still a parameter
  (`/flights/:from-:to`, `/user_:name`). The ROADMAP had planned to decide by the route's origin (OpenAPI and the
  gateway never have a colon parameter). That is not enough: `rebased` normalizes a path again when it joins a prefix,
  and the origin is lost there. In the corpus and the hold-out, the only `:x` glued to a word outside `{..}` and
  `<..>` were these verbs, one in a call and the rest in memos. The optional `:x?` rule now has the same guard. Before,
  it also ate the `?` of a query.

**Diff against `2026-10-18-v2-baseline-22`.** 53 repositories are identical, and so are the hold-out's 3.

- memos: its 6 verb routes keep the verb (`POST /api/attachments:batchDelete`). A seventh comes out:
  `POST /api/attachments:upload` had the key of `attachments:batchDelete` (`/api/attachments{param}`), so the two had
  collapsed into one endpoint. Against the OpenAPI list, the gateway is now 93 of 93 (P 100%), from 92. The 93 Connect
  RPCs stay with F2.1. The gabarito's 7 verb paths, written as the old normalization printed them, were rewritten
  with the verb (H2-D15).
- open-webui: the call to Azure's speech API, `transcriptions:transcribe?api-version=2024-11-15`, was recorded as
  `/speechtotext/transcriptions{transcribeapi}-version=2024-11-15`. It is now `/speechtotext/transcriptions:transcribe`.
  This is right, and outside the gabarito's scope.

**Totals.** Go route precision over the list is 99.1% (1922/1939) and recall 92.9% (1927/2074), from 1921/1938 and
1926/2073. C#, Python and TS/JS are unchanged.

New baseline: `2026-10-18-v2-baseline-23`.

## F1.14, increment 7: Go routers through declared types and named closures (2026-10-18)

This increment does item 2. No repository moves. Each rule has its cases in `route-patterns-go`, which fail without
it.

- **A router method called on a value of declared type.** alertmanager's `api.v1.Register(r.WithPrefix("/api/v1"))`
  now reaches `Register`, so its routes take the prefix. The scanner follows the call when the code declares the
  value's type. That type can come from a receiver or a parameter of a function around the call, or from a local
  assigned a composite literal (vikunja's `csvMigrator := &csv.MigratorWeb{}`). It can also come from a field of a
  struct of the package. The struct may be in any file of the directory, and the scanner reads it from the field types
  the Go symbol pass already collects. A local assigned anything else (`x := NewT()`) has an inferred type. That
  belongs to the resolver (`needs-resolver`) and gets no rule. `WithPrefix` from prometheus/common/route now carries a
  prefix, like `Group`.
- **A named registration closure.** gitea keeps closures under names, such as `addRoutes := func() { m.Get(..) }`. It
  gives a closure as the body of a group on `m`, or calls it inside several groups. Its routes now take each use's
  prefix, once per use. Before, they were recorded once, with no prefix.
- **A prefix known only at runtime is not taken.** alertmanager builds its prefix as
  `router.WithPrefix("/" + strings.Trim(opts.RoutePrefix, "/"))`. Every segment of that prefix is a value read at
  runtime, so it reads as `/{param}`, and the routes now leave it out, as with the option unset. A `/{param}/x` route
  would link to nothing. The first run of this increment found the case, when alertmanager's other routes came out
  under `/{param}`.

**Diff against `2026-10-18-v2-baseline-23`.** 52 repositories are identical, and so are the hold-out's 3.

- alertmanager: its 8 v1 routes now carry `/api/v1` (`GET /api/v1/status`). The judged sample had marked 7 of them
  wrong (`router-as-param`). They are right now, and the sample was updated.
- vikunja: the CSV migrator's 4 routes come out as `/api/v1/migration/csv/..`. The other migrators' 4 come out as
  `/api/v1/migration/{param}/..`, because the name comes from a method called through an interface
  (`segment-from-method`, a limitation). The gabarito's file scope (`pkg/routes/`) left out the migration module where
  these routes are registered, so they could never match. The scope now includes `pkg/modules/migration/`, and the 4
  `{param}` routes count as false positives against the spec's literal names.
- gitea: −79 +192 web routes. 78 registration lines inside named closures were recorded once, without the prefix.
  They now give one route per use:
  - 39 lines are used once;
  - 7 are used three times, for the actions settings of the admin, an org and a user
    (`/-/admin/actions/scoped-workflows/required`);
  - 31 are used four times, for the hooks of the admin, an org, a user and a repo (`/-/admin/hooks/msteams/{id}`);
  - 1 gives eight routes: two verbs on one line, at each of the four uses
    (`/-/admin/actions/runners/{runnerid}`).

  By path, 75 of the added routes are under `/{username}/{reponame}`, 40 under `/user/settings`, 40 under
  `/org/{org}` and 37 under `/-/admin`. Read at the source, they are right. The two judged items that were wrong are
  right now. The gabarito is the API list, so these routes are outside it.

**Totals.** Go route recall over the list is 93.1% (1931/2074), from 92.9% (1927/2074). Precision over the list is
98.9% (1926/1947), from 99.1% (1922/1939). The drop comes from vikunja's widened scope, not from the extractor. The
judged sample is at 93.1% (258/277), from 89.9% (249/277). C#, Python and TS/JS are unchanged.

**Left.** kratos' `RouterAdmin` stays a limitation: its `/admin` is a field that only one of its constructors fills,
at runtime. Telling the two apart needs value flow through a field, which a declared type does not give. A review of
this increment found one more defect, recorded under item 7: a global router reassigned under the same name
(`router = router.WithPrefix("/api/v1")`) loses its prefix when nothing serves or mounts it. No corpus repository has
that shape.

New baseline: `2026-10-18-v2-baseline-24`.

## F1.14, increment 8: a global group's own prefix belongs to the router (2026-10-18)

This increment pays one debt of item 7, which the review of increment 7 found. No repository moves.

In Go, take a group that other files can name: a package variable, a returned router, or a router parameter. Its own
prefix does not go into the routes registered on it in its file. It waits for the composition across files. Until now,
the prefix rode on the edges where the defining file published the group as the child. Two shapes lost it:

- **A router reassigned under its own name.** Examples are `router = router.WithPrefix("/api/v2")`, and
  `r = r.Group("/v3")` on a parameter. The reassignment gives only an edge from the router to itself. A router that no
  file mounts then kept its routes without the prefix: `/healthy` instead of `/api/v2/healthy`.
- **An edge another file publishes when it mounts the router.** That edge never carried the prefix.

Now the group publishes its prefix as the router's own, and `compose` puts it after the prefix of every chain that
reaches the router. The cases are in `route-patterns-go` (`internal/reassigned/`), and they fail without the change.

**Diff against `2026-10-18-v2-baseline-24`.** All 55 repositories are identical, and so are the hold-out's 3. No
repository in either set has either shape. The baseline stays `2026-10-18-v2-baseline-24`.

## F1.14, increment 9: one endpoint per app in a monorepo (2026-10-18)

This increment does item 5, the model. An endpoint's id was `svc/<repo>/http/<METHOD> <path_key>`. The same route in
two apps of one repository became one endpoint, carrying the first app's evidence and handler (`multi-app-repo`).

- **The rule.** Take a route declared in two modules that have a manifest (`go.mod`, `package.json`, a `.csproj`,
  `pyproject.toml`, ..). It is now two endpoints, one per module. The id gains the module's directory
  (`svc/<repo>/app/<dir>/http/..`), and the node gains `app`. A route declared once keeps the repository's id, also
  when it sits in a library that an app references. That way a .NET solution with its controllers in a library project
  does not change. A package a language implies, such as a Go directory, is not a module here. Several design
  choices were measured and dropped:
  - using the nearest module split Go by package;
  - using the module of every route labelled .NET controller libraries as apps.

  The indexer goes to 0.2.15, and the graph drops the endpoint nodes an older indexer wrote. The case is in
  `route-patterns-cs`: `src/Worker` exposes the `GET /health` of `src/Api`. Without the rule the two are one
  endpoint. A call to such a route links to both endpoints, since the service is still the repository.

**Diff against `2026-10-18-v2-baseline-24`.** 42 repositories are identical, and so are the hold-out's 3. Thirteen
only gain endpoints, which are the copies the merge used to hide:

- fiber-recipes: +99, 64 recipes;
- nest: +46, its sample apps;
- bitwarden: +23. Its 14 services each expose `GET /alive` and `GET /now`;
- aiohttp-demos: +10;
- gin-examples: +8;
- ardalis-clean-arch: +5, the template and its sample;
- elsa: +5, the secrets endpoints of a core module and of an extension module;
- chi: +3, `_examples/rest`;
- flask: +2, its examples;
- hono-examples: +2;
- nodebb: +2, the web installer;
- eshop-support: +1, `GET /manual` in the backend and in the staff UI;
- kratos: +1.

Read at the source, each copy is a route its module declares. The kratos copy is `library-code`.
`oryx/prometheusx.SetMuxRoutes(mux)` registers `GET /metrics/prometheus` on whatever mux it gets, and nothing outside
the vendored `oryx` module calls it. Before, it was hidden inside kratos' own `/metrics/prometheus`.

**Totals.** `multi-app-repo` goes from 16 misses in 7 repositories to 8 in 4. Go route recall over the list is 93.3%
(1936/2074), from 93.1%. TS/JS route recall is 89.2% (1334/1495), from 89.0%. Precision over the lists is unchanged
(Go 98.9%, TS/JS 96.5%). C# and Python are unchanged. The gabaritos of chi, fiber-recipes and nest lose the category
on the 8 routes that now match.

**Left.** The other 8 are two apps inside one module: argo-cd's two servers in one `go.mod` (`ANY /api/webhook`,
`ANY /auth/callback`), express' examples and fastapi's single-file tutorials under one manifest, and one gin example.
Telling those apps apart needs the application each route's mounts end at, not the module. That is a limitation,
recorded in the guide.

New baseline: `2026-10-18-v2-baseline-25`.

## F1.14, increment 10: the app's own client wrappers in Python (2026-10-18)

This increment does item 3. No repository moves. The corpus had no known case before. The rule found 47 calls in two
repositories. The cases are in `route-patterns-py` (`app/wrappers/`), and they fail without the rule.

**The rule.** A function or method whose outbound call builds its path around one of its parameters is a client
wrapper. Examples are `_request(self, method, path)` doing `self.client.request(method, path)`, and `legacy_get(path)`
doing `requests.get(BASE + path)`.

- **Verb.** It is the inner call's. If that call takes its verb from a parameter, it is the argument the caller
  passes. If the caller passes none, it is that parameter's default (`method: str = 'POST'`).
- **Calls to the wrapper.** A call that hands a wrapper a literal path is an outbound call, with the wrapper's verb.
  A call that hands it a parameter of its own function makes that function a wrapper too. That way
  `_get(self, path)` doing `self._request("GET", path)` resolves, up to four links.
- **Receiver.** It can be:
  - `self`: the class first, then its bases by name;
  - a local or module variable assigned the constructor of a class of the repo;
  - `self.x` assigned such a constructor in a method of the class.

  A plain name is a function of the module, or one imported from the repo.
- **Precision guards.** A library's client (`httpx.Client()`) is never a wrapper. Two wrappers with one name and
  different shapes give nothing.
- **Shared with C#.** The C# reading of a path built around a parameter moved to `core/http_wrappers.py`, unchanged.
  Both languages use it now, and C# is identical.

**Diff against `2026-10-18-v2-baseline-25`.** 53 repositories are identical, and so are the hold-out's 3. Two
repositories gain calls. Read at the source, all of them are right:

- open-webui, +35 calls:
  - 24 from the Ollama proxy's `send_request(url, method='POST')` and `send_get_request`, to Ollama's own API
    (`POST /api/chat`, `GET /api/tags`, ..);
  - 6 from the MinerU loader's `_request_v1_api('POST', '/v1/uploads')`;
  - 4 from the terminal server's `get_terminal_json(.., '/files/cwd')`;
  - 1 from the OpenAI proxy (`GET /models`).

  Before the default was read, 15 of them came out as `ANY`.
- zulip, +12 calls:
  - 8 to Slack's API, through `get_slack_api_data("https://slack.com/api/users.info", ..)`;
  - 3 to the push bouncer's registration;
  - 1 to a video call provider.

Neither gabarito covers these calls. open-webui's list is its TS client, and zulip's spec is its own API. So precision
and recall over the lists are unchanged.

New baseline: `2026-10-18-v2-baseline-26`.
