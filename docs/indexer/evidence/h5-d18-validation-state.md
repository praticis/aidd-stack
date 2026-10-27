# H5-D18's validation state: which extension method a C# call reaches

> What ran for H5-D18, what it gave, and what is still open. **H5-D18 is not merged, and its semantic gate is open**
> until the steps of §8 are done. Written on 2026-10-26, on `docs/h5-validation-recovery` at `21f9670`, with the
> change in the working tree, uncommitted.
>
> **Added on 2026-10-27:**
>
> - the independent judgment (§5.3);
> - the inherited edges, traced, and the debt (§6.2);
> - the follow-up candidate (§6.4);
> - the author's decisions of that day (§8).
>
> `$C` is defined in [the inventory](../validation-inventory.md). Every live output names the install's tenants, so it
> stays outside the repository, and snapshots are given by number.

## 1. The finding, and the rule

[PR #27's evidence](pr27-validation-state.md), §10, traced one wrong edge: elsa's `x.GetInput<string>(item)`, in a
lambda without a type, reached `ActivityExtensions.GetInput(string)`, which has no type parameter. Its cause is older
than PR #27: no code checked a call's type arguments.

H5-D18 fixes it by C#'s binding rules. It applies to a call that only the repo's extension methods can serve: one
whose receiver's type is outside the repo, or unknown when the call passes type arguments. It has three parts.

1. **Type arguments.** A call written with type arguments reaches only a method that declares type parameters, its own
   or its extension block's.
2. **A receiver outside the repo.** When the type the receiver's chain ends in is outside the repo, the call reaches no
   extension whose `this` is a type of the repo: no type built outside the repo derives from one of it.
   - The `this` counts as a type of the repo only when C#'s scopes reach one from the extension's own file, with as
     many type parameters as the `this` passes type arguments. smartstore's `AsReadOnly<T>(this ISet<T>)` takes the
     framework's `ISet<T>`; the repo's `Smartstore.Caching.ISet` has no type parameter, and that file does not see it.
   - A type outside the repo met before the chain's end (`_lazy.Value`) says nothing of the receiver, and proves
     nothing. The call still goes only to extensions, as on `main`.
3. **Dropping takes targets away.** Dropping the extensions that parts 1 and 2 prove wrong may change the nearest
   homonym. That never makes a guess more than it was:
   - an extension that may or may not take the receiver keeps the strategy `main` gives it, `-ambiguous` included;
   - an extension whose `this` is the receiver's own type, or takes any value (`object`, an unconstrained type
     parameter), takes the strategy left. It is a new target only when it is the only one left.

The diagnosis measured several forms of this rule on recorded calls; the one implemented was named V13 there.

## 2. The code and its cases

| File | What changed |
|---|---|
| `languages/csharp/type_syntax.py` | `type_arity`: how many type arguments a written type passes |
| `languages/csharp/type_facts.py` | an extension's facts also hold its `this`'s type arguments' count |
| `languages/csharp/type_index.py` | `lookup(..., arity)`: with an arity, only a type of that many type parameters that the file sees counts |
| `languages/csharp/symbols.py` | `external_receiver` also tells whether the chain ends in the type; `extension_fit` (it replaces `is_extension_method`) says whether an extension is compatible, proved incompatible, or unknown |
| `languages/base.py` | the two hooks' defaults |
| `core/resolve.py`, `core/nearest.py` (new) | the choice among homonyms by name moved, unchanged, to `nearest.py`, with part 3 as `pruned`; `resolve.py` went from 301 to 274 lines |
| `tests/test_cs_extension_receivers.py` (new) | 13 cases, and `tests/test_cs_names.py`'s 3 cases of part 1 |

**The cycle.** The 13 new cases ran first against the code with part 1 alone. The 6 cases of parts 2 and 3 failed, and
the 7 that guard what must not change passed.

## 3. The local validation

| Check | Result |
|---|---|
| `test.sh` | 628 passed, 26 skipped (they need `mcp-it.sh`'s Neo4j), 1 xfail that was there before; rc 0 |
| `mcp-it.sh` | 56 passed; the throwaway Neo4j, network and volume removed |
| `protocol/shape.sh main` | "0 new or worse over a target". `resolve.py` no longer exceeds 300 lines, and `resolve_calls` went from complexity 25 to 19 |
| `protocol/protocol.sh 2026-10-26-cs-receiver-compat`, with the 11 other C# repos of PR #27's protocol | the corpus against `-29`: 0 repos differ; the hold-out against `-26`: 0; the micro graph: 17 of 23 repos identical, and jellyfin, umbraco, notifo, radarr, smartstore and elsa differ |
| `gates.sh`, run locally: `main`'s run `2026-10-26-audit-main-0725d47` against the branch's | the corpus gates pass; the micro gate fails without a label, and passes with `graph-change` given on the command line. No PR exists, so no label is applied |
| The 6 repos that changed, dry-run again through fresh paths | identical, record by record |

The micro runs are in `$C/micro-fresh/2026-10-26-cs-receiver-compat-180708*`, and the protocol's outputs in
`$C/protocol/2026-10-26-cs-receiver-compat/`.

## 4. The micro graph, against the measure

Before the code, the rule was measured on the 233,429 calls of the 15 C# repos that take this path. A copy of the
code recorded each call's candidates (`$C/diag/receiver-compat-20261026-164139/`). The real dry-runs were then compared
with that measure, record by record, keyed by the caller's file, the line, the callee and the strategy.

| Comparison | Real | Measured | Different |
|---|---|---|---|
| `main` → H5-D18 | −815 / +97 | −815 / +97 | 0 |
| part 1 alone → H5-D18 | −740 / +37 | −740 / +37 | 0 |

- **By repo, from `main`:** smartstore −524 +26, elsa −163 +51, radarr −73, umbraco −52 +19, notifo −2 +1,
  jellyfin −1.
- **Nothing else changed:** no file, symbol, import, endpoint or violation record.
- **39 measured edges have no record under that key, on both sides.** Their caller's id belongs to two files: a
  `partial` class, or twin projects with one namespace. The dry-run ties the id to one file. They do not change.
- The comparer was checked first on a known pair: part 1 alone against `main`, with 0 differences.
- **Part 2 was measured on four repos only:** elsa, radarr, smartstore and umbraco. The other eleven repos' records
  were taken before the copy read a `this`'s scope, so the measure could drop nothing by part 2 there. The real code
  dropped nothing by part 2 there either, so the comparison holds.

## 5. The judgment by case (H5-D14)

### 5.1 The self-review, a proposal

The changes from `main` were read at the source by the agent that wrote the change. How each case was read:

- parts 1 and 2 by target group, the first two sites of each, not as a seeded sample per case and repo;
- part 3's sites one by one;
- the 23 `GetDbContext` calls through their source lines, grouped, and the extension's declaration.

The method does not accept an LLM judging its own result ([semantic judgment](../semantic-judgment-and-regressions.md),
§4.2). So these verdicts are a proposal, not yet the judgment H5-D14 asks for (§8).

| Case | Edges | Verdict |
|---|---|---|
| Part 2: an extension of a repo type, dropped | 665, in 21 `this` families | **right.** The receiver's static type is outside the repo and ends the chain: `IDictionary`, `ILogger`, `IDbConnection`, `IServiceCollection`, Autofac's `ILifetimeScope`, `HttpClient`, MailKit's `SmtpClient`, `ZipArchive`, `IList`, `DirectoryInfo`. With no implicit conversion to the repo's interface, C# cannot bind the extension: the call is the type's own method or an outside extension. Read by target group: 33 groups, the first two sites of each |
| Part 1: a method with no type parameter, dropped | 104, in 20 groups | **right.** The call passes type arguments, as `Builder().Join<Blocklist, Movie>(..)` and `GenerateHash<SHA1>()` do. Read by target group: 20 groups, the first two sites of each |
| Part 3: a compatible extension, no longer ambiguous | 46 | **right, each one.** `AddApi<T>`, `CreateInstance<T>` on an `IServiceProvider`, `AddNotificationAsyncHandler<,>` on an `IServiceCollection`, `ConvertTo<T>(this object?)` |
| Part 3: a compatible extension, a new `unique-name` | 51 | **right, each one.** `GetDbContext<TContext>()` of `extension(IQueryable)`, 23 sites, `TryConvertTo<T>(this object?)` 4, `AddActivity<T>`, `SetCanStartWorkflow` on a `JsonObject`. None of these outside types declares the method |
| Part 3: an unknown extension kept at `main`'s strategy | 5 | its dropped rival's edge goes, which is right. What stays is `main`'s edge, unchanged: 3 right, and the 2 wrong ones of §6.2 |

**The fixed sites,** read in the real dry-runs of `main`, of part 1 alone and of H5-D18:

| Site | `main` | Part 1 alone | H5-D18 |
|---|---|---|---|
| elsa's `x.GetInput<string>(item)`, the original finding, and 10 more | wrong | none | none |
| smartstore's `query.GetDbContext<SmartDbContext>()`, 23 sites | none | `unique-name` | `unique-name` |
| elsa's `value.TryConvertTo<int>(..)`, 4 sites | none | `unique-name` | `unique-name` |
| umbraco's `_serviceProvider.CreateInstance<T>(..)`, 4 sites | `same-module-ambiguous` | `same-module` | `same-module` |
| elsa's `jsonValue.TryGetValue<T>(..)` 20, `builder.RootComponents.Add<T>(..)` 12, `jsRuntime.InvokeAsync<T>(..)` 10, `module.InvokeAsync`, `DidNotReceive().EvaluateAsync<T>(..)` | none | a wrong `unique-name` | none |
| elsa's `handler.InvokeAsync<TResult>(..)`, umbraco's `(..).GenerateHash<SHA1>()` ×2 | `-ambiguous`, the right target among them | resolved | `main`'s, with the dropped rival gone |
| smartstore's `list.AsReadOnly()`, 3 sites | two wrong `-ambiguous` | the same | the same (§6.2) |
| umbraco's `GenerateHash<T>()` on a string 7, as `url.GenerateHash<SHA1>()`; `provider.CreateInstance<T>(..)` in a lambda 1 | none | `unique-name` | none (§6.3) |

**By these verdicts, no edge `main` had right was lost,** so no regression of the change's own kind.

### 5.2 The packet for an independent judgment

It was prepared on 2026-10-26, outside the repository, in
`$C/protocol/2026-10-26-cs-receiver-compat/independent-review/`. It was judged on 2026-10-27 (§5.3).

- **The draw.** A seeded sample (seed `20261026`), drawn per case and repo, round-robin over target groups. It has 114
  items in its first tier, and 189 with its second.
- **What it covers:**
  - parts 1 and 2 dropped;
  - part 3's held targets, and the targets it does not add;
  - the compatible extensions, raised and new;
  - three kinds of unchanged call, as controls;
  - every named site of §6.2 and §6.3.
- **What backs it.** Each item is confirmed in the real dry-runs.
- **The verdicts of §5.1 are sealed in it,** to be compared only after the review.

### 5.3 The independent judgment, 2026-10-27

**Who judged.** An AI agent (Claude Opus 5.5, in Claude Code), started by the author with no memory of the
implementation. **It is not a human review.** The method asks for "a person, or an agent reading the source", never an
LLM judging its own result ([semantic judgment](../semantic-judgment-and-regressions.md), §4.2), and H3 and H4.1 ask a
person to check a sample.

**The author's decision, 2026-10-27:** this judgment is accepted as complementary engineering evidence. It is
recorded as what it is: an AI agent's judgment, not a person's, with nothing compiled or run.

- **The project's criterion is not literally met by it:** H3 and H4.1 ask a person to check a sample.
- **The decision does not say** whether the gate also needs that check (§8).

**How it judged:**

- It read the packet, the 15 corpus clones at their pins, one dry-run file and the method's documents.
- It decided each binding by reading the source and C#'s rules. Nothing was compiled or run.
- It did not read the sealed verdicts, `prior.py` or this record before its verdicts were frozen (SHA-256
  `e1049dad…`). Only then did it run the packet's comparison.
- Its notes, verdicts and comparison stay in the packet's folder, outside the repository.

The sample is not a statistical estimate, and a count below is of the sample only.

| Stratum | Items | `right` | `wrong` | What a `wrong` means there |
|---|---|---|---|---|
| A, part 1 dropped | 36 | 36 | 0 | a right edge lost |
| B, part 2 dropped | 32 | 32 | 0 | a right edge lost |
| D1, compatible, no longer ambiguous | 17 | 17 | 0 | a wrong edge raised |
| D2, compatible, new | 21 | 21 | 0 | a wrong edge added |
| C1, part 3's held targets | 5 | 3 | 2 | `main`'s edge, wrong and untouched: inherited |
| C2, part 3's targets not added | 20 | 14 | 6 | the target is not the method C# binds, so leaving it out is right |
| E1, F1, F2, the unchanged controls | 58 | 45 | 13 | `main`'s edge, wrong and untouched: inherited |
| **total** | **189** | **168** | **21** | none `undecided` |

A K item is counted in the stratum it was measured in.

**What it found:**

- **No wrong item among the changed edges.** The review found 0 of 106 in A, B, D1 and D2. By the packet's criteria,
  nothing there blocks under H5-D14, and no right edge was lost (H5-D17). That does not approve the gate (§8).
- **15 inherited wrong edges,** `main`'s and untouched by H5-D18:
  - the 2 `EvaluateAsync` calls and the 3 `AsReadOnly` calls of §6.2;
  - 10 more in the controls: E1-001, E1-004, E1-005, E1-007, E1-009, E1-011, F1-004, F2-005, F2-012 and F2-013.

  By the review, 13 of the 15 have one shape: an applicable instance member, or a method outside the repo, that the
  resolver cannot see, so a repo extension of the same name takes the call. Whether each is covered by a recorded gap
  is not settled here.
- **What part 3 costs.** Of the 20 C2 targets, 14 are the method C# binds: gains part 3 does not make. They include
  the 7 `GenerateHash<T>()` calls and the lambda's `CreateInstance<T>` of §6.3, and C2-002 (§6.4). The other 6 are
  not, and leaving them out is right.
- **Beyond the verdicts,** inferred from the source and not checked by a compiler:
  - the count of type arguments (§6.4);
  - a C# 14 extension block's type parameters seem to count in an explicit type-argument list (F1-004);
  - one callee id stands for three declarations, in three projects of ardalis-clean-arch (F2-001);
  - D2-002 and D2-004 bind a compiled package of elsa, which the edge names by its declaration in the repo.

**Against the self-review.** The packet's comparison takes the 129 items to which the sealed file gives a word, and
shows one disagreement: C2-002. A check by candidate id, made after the review, shows that 3 of those words are not
the self-review's.

- `prior.py` matched a C2 target to part 1 alone's edges by qualified name, which overloads share.
- Part 1 alone never reached C2-002's target.
- C2-006's and C2-007's targets were part 1 alone's `same-file-ambiguous` edges. They are not among the 44
  `unique-name` edges the self-review judged (§6.1).

So the self-review judged 126 of the 189 items, and the review agrees with it on all 126. The one disagreement is
with a word the self-review never gave. The sealed file is left as it was, and the review's finding on C2-002 stands.

## 6. What H5-D18 corrects, what it inherits, and what stays out

### 6.1 Corrected by H5-D18

These counts come from §5.1's verdicts. The independent judgment drew 106 of these edges, and none of them was wrong
(§5.3). Both judgments wait for the author.

- **769 wrong edges `main` had, gone:** 665 by part 2 and 104 by part 1.
- **97 right edges gained:** 51 new, and 46 no longer ambiguous.
- **What part 1 alone added wrongly, never added:** 44 `unique-name` edges, made when dropping a rival left one guess.
  The independent judgment drew 4 of them, and none is the method C# binds.

### 6.2 Inherited defects: the 15 edges, and the debt

The independent judgment found 15 inherited wrong edges (§5.3). They are `main`'s, and H5-D18 leaves them as they
were, except that it drops one wrong rival at `EvaluateAsync`.

- **Decided:** on 2026-10-27 the author decided that two groups of them are non-blocking debt candidates, associated
  with F1.2 (SCIP): the 2 `EvaluateAsync` edges and the 3 `List<T>.AsReadOnly()` edges.
- **Not classified as non-blocking:** the other 10, by the author's decision of the same day. Seven fall under
  limitations recorded before H5-D18, and three stay unresolved.

**The recorded limitations, word for word, on `origin/main`:**

- **H5-D16,** in `docs/decisions.md` and the H5 handoff: "the arguments' types between overloads of one arity" and "a
  member of a package's type" stay out. The handoff adds "a member of a package's type, whose own type is not known".
- **H5-D17's gap 1,** in the H5 handoff's "What stays out": "Type arguments in the middle of a chain. A member's type
  is kept by its simple name".
- **H5-D17's gap 5,** in the same list: "An extension on an interface is also still taken for any receiver outside
  the repo (H5-D16)".

**How each edge is traced:**

- **The cause** comes from the packet's records: the receiver, the outside type the resolver found, and the `this` of
  the candidate `main` chose.
- **The method C# binds** is the review's reading of the source.
- **A gap counts as documented** only if it is on `origin/main`, the merged record: H5-D16's list of what stays out,
  and H5-D17's thirteen gaps, both in [the H5 handoff](../../handoffs/H5-indexer-refactor.md). A record in this
  document does not count, since it is part of the change under review.

**What the H2-D14 column says.** H2-D14 reads: "A new item wrong only because it inherits an already categorized
defect counts, but does not block the rule."

- These edges are not new. They are outside the diff that H5-D14 judges.
- So the column says only whether H2-D14's condition holds: every cause of the edge categorized on `origin/main`.
- Whether an untouched edge needs that condition at all is the author's decision, as
  [the semantic judgment](../semantic-judgment-and-regressions.md), §4.6, left it.

| Item | Site | What `main` reaches; what C# binds | Cause | Documented on `origin/main` | H2-D14's condition | Non-blocking by |
|---|---|---|---|---|---|---|
| E1-001 | bitwarden `DuoUniversalTokenService.cs:194` | `TryGetValue<T>(this IDistributedCache, ..)`; `IHeaderDictionary`'s own `TryGetValue` | `Request.Headers` is reached through `HttpContext`, a package's type, so the receiver has no type; an extension on an interface is taken for it | H5-D16: a member of a package's type. H5-D17: gap 5 | holds | not classified: covered as listed; H2-D14's condition holding does not decide the gate |
| E1-004 | jellyfin `GroupTests.cs:64` | `GetItemById(this ILibraryManager, string)`; the interface's own `GetItemById(Guid)` | `MockLibraryManager.Object` is reached through `Mock<T>`, so no type; an interface's extension is taken; the arguments' types are not compared | H5-D16: a member of a package's type, and the arguments' types between overloads of one arity. H5-D17: gaps 1 and 5 | holds | not classified: covered as listed; H2-D14's condition holding does not decide the gate |
| E1-005 | notifo `DefaultUserService.cs:48` | `ToAsyncEnumerable(this IFindFluent<,>)`; an outside `ToAsyncEnumerable` on `IEnumerable<T>`, not pinned down by the review | `userManager.Users` is reached through `UserManager<T>`, so no type; an interface's extension is taken | H5-D16: a member of a package's type. H5-D17: gap 5 | holds | not classified: covered as listed; H2-D14's condition holding does not decide the gate |
| E1-007 | umbraco `DeliveryApiSettingsValidatorTests.cs:97` | `Count(this IUmbracoDatabase, Sql)`; LINQ's `Count` | `_loggerMock.Invocations` is reached through `Mock<T>`, so no type; an interface's extension is taken. The outside type is met before the chain's end, so part 2 does not apply (§6.3) | H5-D16: a member of a package's type. H5-D17: gap 5 | holds | not classified: covered as listed; H2-D14's condition holding does not decide the gate |
| E1-009 | elsa `WorkflowTriggerEqualityComparer.cs:45` | `Add(this IDictionary<string, ..>, Type)`; `IList<JsonConverter>`'s own `Add` | `_settings.Converters` is reached through `JsonSerializerOptions`, so no type; an interface's extension is taken | H5-D16: a member of a package's type. H5-D17: gap 5 | holds | not classified: covered as listed; H2-D14's condition holding does not decide the gate |
| E1-011 | umbraco `BackOfficeController.cs:433` | `TrimStart(this string, string)`; `string.TrimStart(char)` | `_securitySettings.Value` is reached through `IOptions<T>`, so no type. A `this string` has no name in the type facts, so it is taken for any receiver | the receiver: H5-D16, a member of a package's type, and H5-D17 gap 1. The `this string`: no gap; `main`'s code documents it as intended (`is_extension_method`: "extending what may be anything — … a predefined type") | partly | unresolved: covered in part |
| F1-004 | elsa `DictionaryExtensions.cs:68` | three `TryGetValue<T>` of one type parameter; the `TryGetValue<T>` of `extension<TKey>(IDictionary<TKey, object>)` | an extension block's receiver has no type; part 1 checks that type parameters exist, not their count | none. Both causes are recorded only in this document (the first record below, and §6.4) | no | unresolved: no gap documented before H5-D18 |
| F2-005 | clean-arch-dotnet `EndpointRouteBuilderExtensions.cs:24` | `MapGet(this IEndpointRouteBuilder, Delegate, string)`, the method itself; ASP.NET's `MapGet(string, Delegate)` | the arguments' types are not compared; the overload C# binds is outside the repo | H5-D16: the arguments' types between overloads of one arity | holds | not classified: covered as listed; H2-D14's condition holding does not decide the gate |
| F2-012 | radarr `169_custom_format_scores.cs:75` | `Reverse(this string)`; `List<T>.Reverse()` | a `this string` has no name, so it is taken for a `List<T>`, whose own method is outside the repo | none as a gap; `main`'s code documents the `this string` reading as intended, as for E1-011 | no | unresolved: no gap documented before H5-D18 |
| F2-013 | rapid-blazor `IAuthorizationServiceExtensions.cs:11` | `AuthorizeAsync(this IAuthorizationService, .., Permissions)`, the method itself; ASP.NET's `AuthorizeAsync(.., string)` | as for F2-005 | H5-D16: the arguments' types between overloads of one arity | holds | not classified: covered as listed; H2-D14's condition holding does not decide the gate |
| K-003, K-005 | elsa `DictionaryValueEvaluator.cs:48`, `ExpressionEvaluatorExtensions.cs:20` | `EvaluateAsync<T>(Input<T>, ..)`; `IExpressionEvaluator.EvaluateAsync<T>(Expression, ..)` | the receiver has no type: a positional record's property, an extension block's receiver | none | no | the author's decision of 2026-10-27 (the first record below) |
| K-009 to K-011 | smartstore `HybridExpando.cs:447`, `:466`, `ExpressionVisitor.cs:279` | `AsReadOnly<T>(this ISet<T>)` and the `IEnumerable<T>` block's `AsReadOnly()`; `List<T>.AsReadOnly()` | an interface's extension is taken for a receiver outside the repo, whose own members are not known | H5-D17: gap 5 | holds | the author's decision of 2026-10-27 (the second record below) |

**So:**

- **Non-blocking by the author's decision:** 5 edges.
- **Covered by recorded limitations, not classified:** 7 edges, E1-001, E1-004, E1-005, E1-007, E1-009, F2-005 and
  F2-013.
  - Each falls under H5-D16 or H5-D17 as the table lists, so H2-D14's condition holds.
  - That H2-D14 could apply does not decide the gate. Its text speaks of a new item, and no decision has applied it
    to these.
- **Unresolved:** 3 edges.
  - E1-011 is covered in part: its receiver, not its `this string`.
  - F1-004 and F2-012 have no gap documented before H5-D18.

Each of the ten waits for the author (§8).

**The two debt records below.** The project has no identifier scheme for debt, so each record is named by its
heading, which stays stable. In each record, "observed" is what the dry-runs hold, and "what C# binds" was read at the
source; nothing was compiled.

#### Debt: an untyped receiver reaches only extensions (`EvaluateAsync`)

- **Observed:** elsa's `evaluator.EvaluateAsync<T>(input.Expression!, ..)` at `ExpressionEvaluatorExtensions.cs:20`,
  and `evaluator.EvaluateAsync<object>(expression, ..)` at `DictionaryValueEvaluator.cs:48`. They are the packet's
  K-002 to K-005.
  - On `main`, each has two `-ambiguous` edges to the repo's `ExpressionEvaluatorExtensions.EvaluateAsync`.
  - H5-D18 drops the non-generic one, by part 1. It keeps `EvaluateAsync<T>(Input<T>, ..)`, which at line 20 is an
    edge to itself.
  - `IExpressionEvaluator.EvaluateAsync<T>` gets no caller edge at either site.
  - C2-010, `_expressionEvaluator.DidNotReceive().EvaluateAsync<object>(..)`, has the same cause, with no edge on
    either side.
- **What C# binds:** the interface's own
  `IExpressionEvaluator.EvaluateAsync<T>(Expression, ExpressionExecutionContext, ExpressionEvaluatorOptions?)`. Member
  lookup finds it before extension lookup starts.
- **The cause, in the resolver:** neither receiver has a type.
  - One is an extension block's receiver parameter.
  - The other is `var evaluator = context.ExpressionEvaluator`, where `ExpressionEvaluator` is a property of a
    positional record.
  - A call with type arguments on a receiver of unknown type reaches only the repo's extensions by name, so the
    interface's method is never a candidate.
  - Both types are declared in the repo, in sight: the information is not outside it.
- **Size:** the named sites. How many other calls share the cause was not measured.
- **Status:** a non-blocking debt candidate, by the author's decision of 2026-10-27, associated with F1.2 (SCIP).
- **Recorded:** here only. It is not among H5-D17's thirteen gaps, so H2-D14, which speaks of a defect already
  categorized, does not cover it. It is non-blocking by the author's decision, not by H2-D14.
- **What a fix needs:** one of two capabilities.
  - A type for those two forms of receiver, and then the receiver's own members before the extensions.
  - Or a compiler-based index of the repo, SCIP (F1.1, F1.2), mapped to the graph's symbols.
- **Proposed phase:** F1.2, as the author associated it. A fix of the resolver that types the two receivers stays the
  alternative, and may come first.
- **SCIP is a plausible remedy, not a proven one.** By ADR-002's account, a compiler's index records the method
  overload resolution chose. Here that would be the interface's method, but no index was made for these sites. It
  would also need these, none of them verified:
  - elsa restores and builds where the indexer runs;
  - the scip-dotnet version in use reads C# 14 extension blocks;
  - F1.2's converter maps SCIP's symbols to the graph's by file and range, since one id can stand for several
    declarations (F2-001);
  - SCIP runs for that snapshot, which is optional per repo (ADR-002).
- **The regression cases**, written first as strict xfails whose reason is what the code gives today:
  - `an-extension-blocks-receiver-reaches-its-types-own-method`: inside `extension(IEvaluator evaluator)`,
    `evaluator.Evaluate<T>(expression)` reaches `IEvaluator.Evaluate<T>(Expression)`, not the block's
    `Evaluate<T>(Input<T>)`;
  - `a-var-from-a-positional-records-property-has-its-type`: with `record Context(IEvaluator Evaluator)`,
    `var evaluator = context.Evaluator;` and then `evaluator.Evaluate<object>(expression)` reach
    `IEvaluator.Evaluate<T>`.
- **Done when:**
  - both cases pass, and no other case changes;
  - the two elsa sites reach `IExpressionEvaluator.EvaluateAsync<T>`, with no edge to the extension;
  - every other micro difference is judged by case at the source (H5-D14), under `graph-change`;
  - the corpus and the hold-out pass their gates.

#### Debt: an outside type's own members lose to the repo's extensions (`List<T>.AsReadOnly()`)

- **Observed:** smartstore's `list.AsReadOnly()` at `HybridExpando.cs:447` and `:466` and at
  `ExpressionVisitor.cs:279`, where `list` is a `List<…>`. They are the packet's K-009 to K-011.
  - `main` and H5-D18 give each call the same two `same-module-ambiguous` edges: to `AsReadOnly<T>(this ISet<T>)`
    (`EnumerableExtensions.cs:31`), and to the `AsReadOnly()` of `extension<T>(IEnumerable<T>? source)` (`:98`).
  - The edges are identical on both sides, and wrong on both. Unchanged does not mean right.
- **What C# binds:** `List<T>.AsReadOnly()`, the BCL's instance method, so no repo edge should exist.
  - `List<T>` does not implement `ISet<T>`.
  - Member lookup finds the instance method before it reaches the `IEnumerable<T>` block's.
- **The cause:** the resolver knows the receiver's type is `List<…>`, outside the repo, but has neither its members nor
  its interfaces.
  - An extension on an interface is taken for any receiver outside the repo (H5-D16; H5-D17's fifth gap).
  - Part 2 drops only an extension whose `this` is a repo type, and both `this` here are the framework's.
- **Size:** the named sites. The independent judgment puts 13 of its 15 inherited wrong edges in a broader shape that
  holds this one: an applicable instance member, or a method outside the repo, that the resolver cannot see (§5.3).
  Examples are `IList.Add` (E1-009), `List.Reverse` (F2-012), `string.TrimStart(char)` (E1-011),
  `IHeaderDictionary.TryGetValue` (E1-001) and LINQ's `Count` (E1-007). How many calls share it in the corpus was not
  measured.
- **Status:** a non-blocking debt candidate, by the author's decision of 2026-10-27, associated with F1.2 (SCIP).
- **Recorded:** H5-D17's fifth gap, so H2-D14's condition, a defect already categorized, holds.
- **What a fix needs:** two things.
  - An outside type's members and interfaces, from a SCIP index or from reference-assembly metadata.
  - A rule that a call resolved to a symbol outside the repo keeps no repo edge found by name.
- **Proposed phase:** F1.2, as the author associated it, with F1.1's indexers. Reading reference-assembly metadata is
  an alternative the plan has no item for.
- **SCIP is a plausible remedy, not a proven one.** It would need the same conditions as the record above, and a
  converter rule, not yet specified, for a call that SCIP resolves to an external symbol.
- **The regression case,** written first as a strict xfail:
  - `an-outside-types-own-method-is-no-repo-extension`: `new List<int>().AsReadOnly()`, beside repo extensions
    `AsReadOnly<T>(this ISet<T>)` and `extension<T>(IEnumerable<T>).AsReadOnly()`, reaches no repo method;
  - it needs the capability above, so it can pass only where that capability runs.
- **Done when:**
  - the case passes where the capability runs;
  - the three smartstore sites lose both edges;
  - where it did not run, the path by name is unchanged, as ADR-002, decision 3, does for HTTP;
  - every other micro difference is judged by case at the source.

### 6.3 Known limitations, and the work they leave

- **A `this` of a predefined type has no name in the type facts.** `this string` reads as nothing, so such an
  extension is never compatible, and dropping its overloads adds no target. umbraco's 7 `GenerateHash<T>()` calls on a
  string, as `url.GenerateHash<SHA1>()`, stay without an edge, as on `main`. The case
  `an-extension-of-a-predefined-type-is-never-known-to-take-a-value` fixes this behavior. Naming predefined types is
  separate work. The independent judgment found all 7 bound to that extension: gains part 3 does not make.
- **A receiver of unknown type is never compatible with an interface's `this`.** umbraco's
  `provider => provider.CreateInstance<T>(..)`, a lambda without a type, stays without an edge, as on `main`. It is the
  gap H5-D16 leaves. The independent judgment found it bound to that extension: a gain not made.
- **Overloads declared on one line share their facts' key.** An extension's facts are found by name and line, so two
  overloads of one name on one line both read the first one's. It was found in a test fixture. How often it occurs in
  the corpus was not measured.
- **A type outside the repo before the chain's end keeps `main`'s reading.** It still matches a `this` of its own name.
  That is right for a nullable value's `.Value`, as in umbraco's `dto.EmailConfirmedDate.Value.EnsureUtc()` (8 sites
  in three repos), and would be wrong for a `this Lazy<T>` on `_lazy.Value`.
- **Part 2's premise:** a type built outside the repo derives from none of its types. A package built against the
  repo's own published assemblies, a plugin, could break it; none was seen in the corpus. A `using` alias is not read
  (H5-D17's eighth gap).
- **A compatible `this` is matched by name without its type arguments.** `IQueryable` for an `IQueryable<T>` is right;
  `Action` for an `Action<T>` would not be.

### 6.4 A follow-up candidate: the count of type arguments (C2-002)

The independent judgment found this at elsa's `MassTransitWorkflowDispatcherFeature.cs:26`. There,
`context.AddMassTransitConsumer<DispatchWorkflowRequestConsumer, ..>()` passes two type arguments to a
`ShellFeatureContext`, a type outside the repo that ends the chain.

- **What H5-D18 gives,** in the real dry-runs:
  - Part 2 drops `main`'s two edges to `ModuleExtensions.AddMassTransitConsumer` (`this IModule`).
  - It keeps `MassTransitConsumerExtensions.AddMassTransitConsumer<TConsumer>`, which has one type parameter, at
    `main`'s `same-module-ambiguous`. `main` had that edge, so it is inherited, not a regression.
  - It does not add `AddMassTransitConsumer<TConsumer, TDefinition>`, which the review judged to be the method C# binds.
    Part 3 adds no target that is not alone.
- **Why.** Part 1 checks that a method declares type parameters, not how many.
  - The count is declared in sight.
  - Comparing it would drop the one-parameter overload, and leave the two-parameter one alone, whose `this` is the
    receiver's type.
- **An open point.** In a C# 14 extension block, the block's type parameters seem to count in an explicit
  type-argument list (F1-004, inferred from the code at its pin, not by a compiler). A count must say which list it
  compares.
- **Status: a separate follow-up.** The author kept it out of H5-D18 on 2026-10-27. It is not implemented, measured
  or validated, and H5-D18's code and cases do not change for it.
- **To validate first: how C# 14 counts explicit type arguments on an extension block's method.** A compiler decides
  it, on synthetic code and never on a corpus repo. Given `extension<TKey>(IDictionary<TKey, object> d)` declaring
  `TryGetValue<T>(..)`:
  - does `d.TryGetValue<TKey, T>(..)` bind it?
  - does `d.TryGetValue<T>(..)` bind it, with `TKey` inferred?

  The count the rule compares follows that answer.
- **Its cases,** written first as strict xfails:
  - `a-call-with-two-type-arguments-reaches-only-the-overload-with-two`: the repo declares `Add<T>(this Ctx)` and
    `Add<T, U>(this Ctx)`, and `ctx.Add<A, B>()`, on a `Ctx` from outside the repo, reaches only `Add<T, U>`;
  - a case for an extension block's method, written from the compiler's answer above.
- **Done when:**
  - the cases pass, and no existing case changes its expectation;
  - C2-002's site reaches `AddMassTransitConsumer<TConsumer, TDefinition>` alone, no longer the overload with one type
    parameter;
  - every micro difference is judged at the source, by case, on a seeded sample per case and repo (H5-D14), under
    `graph-change`;
  - the corpus and the hold-out pass their gates.

## 7. The live validation before the merge (V21, V22, V25), 2026-10-26, and its limits

`pre-merge.sh`, read-only, on the 3 tenants and 10 snapshots, with the copies of `main`'s code and the branch's checked
against git (652 and 654 files). The install's build is `0.2.15+ccc54d86dbc7`, PR #27's, and no snapshot is
`outdated`.

- **The picture:** rc 0, 15 lists. All 15 equal PR #27's after picture, `labels.txt` and `snapshots.txt` included, by
  the digests [its evidence](pr27-validation-state.md) records in §5 and §9. The graph has not changed since.
- **The dry-runs:** both codes gave rc 0 on all 10 snapshots. `main`'s and the branch's are identical in all 12 lists
  of each, record by record.
- **`graph_vs_dry.py`:** the graph holds `main`'s dry-run on every snapshot; "mismatching snapshots: 0".
- **The 27 golden calls, the planned run:** rc 0. 26 gave no error, and `cypher_readonly` refused the write before
  Neo4j. Q1 to Q5 have their expected shapes ([the golden questions](../../golden-questions.md), the twelfth round).
  - The 5 answers that hold time fields are the 5 that PR #27's evidence, §9, names: `atlas_status`, Q5's `ref_diff`
    and three `repo_map`s.
  - PR #27's answers are in `.local/`, which was not read, so they were not compared file by file. The graph and the
    build are the same, so the other 22 are inferred unchanged.

**What it shows.** Two of the snapshots are C#, with 74 and 90 files, and neither holds a call the change reaches. The
check shows the install, not the change, as the eleventh round did. The change was judged on the corpus (§4, §5).

**Two deviations from the procedure:**

- **The calls file.** PR #27's private calls file was not read, by the author's instruction. The 27 calls came from
  the original `golden.py` that the recovery rebuilt (`$C/recover/out/val/`). Its labels are the 27 the documents name,
  but it was not compared with PR #27's file.
- **An unplanned run.** Loading that recovered script to read its calls also ran them, since it has no `__main__`
  guard: the same 27 calls, minutes before the planned run, with the same write refused. The graph did not change. It
  is not a validation round of its own; it only shows the answers are stable. 26 of its answers are byte for byte the
  planned run's, and `atlas_status` differs only in time fields, since a refresher cycle ran in between.

## 8. The acceptance criteria not yet met

**The semantic gate is open, and H5-D18 is not accepted.** What it still needs:

| Criterion | State | Needs |
|---|---|---|
| The judgment by case (H5-D14) | the self-review is a proposal (§5.1). An independent AI agent judged the seeded packet on 2026-10-27 (§5.3): 189 items, and 0 wrong among the 106 changed edges. The author accepted it that day as complementary engineering evidence: not a human review, nothing compiled or run, and not a statistical sample. The criterion of a person checking a sample (H3, H4.1) is not literally met | the author's decision whether the gate also needs that check, or proceeds on this evidence |
| The inherited defects (§6.2) | 15 in the sample, each traced. The 2 `EvaluateAsync` edges and the 3 `List<T>.AsReadOnly()` edges are non-blocking debt candidates for F1.2, by the author's decision of 2026-10-27. The other 10 are not classified as non-blocking: 7 fall under H5-D16 or H5-D17, which does not decide the gate, and E1-011, F1-004 and F2-012 are unresolved | the author's decision on each of the 10. A place in the plan for the two debt records; the project has no identifier scheme for debt |
| The count of type arguments (§6.4) | kept out of H5-D18 by the author's decision of 2026-10-27: a separate follow-up | nothing for this gate; the follow-up has its own cases and validation |
| The documents | they describe the change as in the working tree, uncommitted, which still holds. The recovery's documents now point to `21f9670` where they called it uncommitted (2026-10-27, in the working tree) | H5-D18's mentions updated once its commit and PR exist |
| The commit and its PR | not made; the proposed `fix(csharp)` holds only the code and its cases, from `origin/main` | the author's authorization |
| CI on that PR, with `graph-change` | not run; no label is applied | the PR, and the label after the review |
| The after side: reinstall, the after picture, the golden answers after, `graph_vs_dry.py` before against after | not done | the merge and the author's authorization |
| The limitations of §6.3 | recorded; none adds a wrong item to the measured diff | later work, each with its cases first |

The live validation of §7 shows the install, not the change, so it meets none of these criteria by itself.
