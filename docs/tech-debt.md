# Technical debts

A debt is a known defect or gap that does not block a PR, so decided by the author. The `main` branch already has it;
the change that found it neither creates nor worsens it. Each debt is registered with where it was seen, when it is
due, and the case that tells when it is gone.

**The case is the reminder.** A debt's case is a strict xfail in `indexer/tests/`: when the resolver learns the right
answer, the case passes, the strict xfail fails the suite, and the mark has to go. That does not depend on anyone
remembering.

Rules:
- A debt enters with the author's decision and a case. This is the standing process (AGENTS.md, Principles): what a
  judgment finds and does not block is registered here with its strict xfail, never left as a note in a handoff.
- A phase of the [ROADMAP](ROADMAP.md) lists the debts due in it and closes only when they are settled or the author
  moves them.
- A debt closes in the PR that removes its xfail mark; its row here is then marked closed with that PR (its Due reads
  `closed in PR #n`).
- CI checks this table (the `debts` job, `indexer/scripts/debts.py`) against the tests and the ROADMAP: each case named
  here is a case of a `indexer/tests/test_*_debts.py`, in the form `case("id", ...)`, and each case there is named here;
  the ROADMAP's `Debts due here:` (F1.2), `are due in `fix(csharp)` PRs before F1.2` and `due in an H5 step` lists are
  the open debts of those dues; no document names a debt this table lacks.

Seen at: a public corpus repo's file and line, or the decision whose judgment found it when no site was kept. Decided by the author on 2026-10-27: TD-001 to TD-006 with the acceptance of H5-D18
([decisions.md](decisions.md)), and TD-007 to TD-022 by moving here the gaps that H5-D16 and H5-D17 had left in the H5
handoff; TD-023 on 2026-10-28, from the design review of H5-D22, and TD-024 the same day, from the eighth resume run;
TD-025 on 2026-10-29, from the judgment of Python's change of behavior, with H5-D26: unlike the others, that change
creates it, and the author keeps the change's rule. TD-026 on 2026-10-30, from the judgment of where a Python absolute
import is looked for, with H5-D28: `main` has it, that change widens it, and the author keeps the change.
SCIP is a possible remedy for some of them, not a proven one. A due of `fix(csharp)` is a PR of that kind before F1.2,
for a defect whose answer is declared in the repo; F1.2 is for one that needs a type or a model the resolver does not
have. A due in a step of H5 (`H5 step 6`) is for a defect of the code's architecture that the step removes.

| ID | The debt | Seen at | Due | Case |
|---|---|---|---|---|
| TD-001 | An untyped receiver reaches only the repo's extensions: a call with type arguments on an extension block's receiver, or on a `var` taken from a positional record's property, never reaches the type's own method | elsa `ExpressionEvaluatorExtensions.cs:20`, `DictionaryValueEvaluator.cs:48` (`EvaluateAsync`) | F1.2; the resolver may fix the first earlier | `an-extension-blocks-receiver-reaches-its-types-own-method`, `a-var-from-a-positional-records-property-has-its-type` |
| TD-002 | A type outside the repo has no known members or interfaces, so an extension on an interface is taken for the type's own method, or for a type that does not implement the interface | smartstore `HybridExpando.cs:447`, `:466`, `ExpressionVisitor.cs:279` (`List<T>.AsReadOnly()`); an array's `.Where(..)` reaching `RuleQueryableExtensions.Where` | F1.2, or reference-assembly metadata | `an-outside-types-own-method-is-no-repo-extension`, `an-array-has-no-extension-of-an-interface-it-does-not-implement` |
| TD-003 | A member reached through a package's type has no type, so an extension on an interface is taken for it. A recorded limit of H5-D16 and H5-D17 | bitwarden `DuoUniversalTokenService.cs:194`, jellyfin `GroupTests.cs:64`, notifo `DefaultUserService.cs:48`, umbraco `DeliveryApiSettingsValidatorTests.cs:97`, elsa `WorkflowTriggerEqualityComparer.cs:45` | F1.2 | `a-member-reached-through-a-package-type-has-its-own-method` |
| TD-004 | The arguments' types are not compared between overloads of one arity. A recorded limit of H5-D16 | clean-arch-dotnet `EndpointRouteBuilderExtensions.cs:24`, rapid-blazor `IAuthorizationServiceExtensions.cs:11`, and jellyfin's site of TD-003 | F1.2 | `the-arguments-types-tell-the-overloads-of-one-arity-apart` |
| TD-005 | A `this` of a predefined type (`this string`) has no name in the type facts, so it is taken for any receiver | umbraco `BackOfficeController.cs:433`, radarr `169_custom_format_scores.cs:75` | a `fix(csharp)` PR before F1.2 | `an-extension-of-a-predefined-type-is-not-taken-for-another-types-method` |
| TD-006 | The count of type arguments is not compared with the method's type parameters | elsa `MassTransitWorkflowDispatcherFeature.cs:26`, `DictionaryExtensions.cs:68` | a `fix(csharp)` PR before F1.2, after a compiler shows how C# 14 counts explicit type arguments on an extension block's method | `a-call-with-two-type-arguments-reaches-only-the-overload-with-two`; the block's case is still to write |
| TD-007 | A `foreach` variable, an `out var` and a pattern variable have no type, so their calls go by name (a `foreach` over an array is TD-022) | H5-D16; about 20 sites on the micro set | a `fix(csharp)` PR before F1.2 | `a-foreach-variable-has-the-elements-type`, `an-out-var-has-the-parameters-type`, `a-pattern-variable-has-the-patterns-type` |
| TD-008 | A lambda parameter has no type, so its call goes by name | btcpay `coin => coin.Value.GetValue(..)`, umbraco `(source, target, context) => target.EnableChangeTracking()` | F1.2 | `a-lambda-parameter-has-the-delegates-type` |
| TD-009 | An extension of a type outside the repo is not reached on a type with a base outside it, which may declare the method | notifo `user.Settings.GetOrDefault(..)`, 4 sites | F1.2 | `an-extension-of-an-interface-binds-a-type-with-a-base-outside-the-repo` |
| TD-010 | A field's type keeps no type arguments, so `_sut.Sut.X()` goes by name | H5-D17 | a `fix(csharp)` PR before F1.2 | `a-field-with-type-arguments-passes-them-down-the-chain` |
| TD-011 | A method's own type parameter takes nothing from the call (`Get<Foo>()`); only the DI's `GetRequiredService<T>()` is read | H5-D17 | a `fix(csharp)` PR before F1.2 | `a-methods-own-type-parameter-takes-the-call-type-argument` |
| TD-012 | A type parameter with two constraints (`where T : IA, IB`) declares no type: a value of it has the members of both, which one type cannot say | H5-D17 | F1.2 | `a-type-parameter-with-two-constraints-has-the-members-of-both` |
| TD-013 | A nested type argument keeps its outer name: `Box<Item>` passes `Box` | H5-D17 | a `fix(csharp)` PR before F1.2 | `a-nested-type-argument-keeps-its-own-arguments` |
| TD-014 | Between extensions of one arity, the one whose `this` is the receiver's type is not preferred to one that takes an interface | smartstore `customQuantities.IsNullOrEmpty()` on an `int[]` | a `fix(csharp)` PR before F1.2 | `the-extension-whose-this-is-the-receiver-wins-over-an-interfaces` |
| TD-015 | A capitalized name a base outside the repo may declare is read as this type's own member, with the count of arguments unchecked | eshop `Database.BeginTransactionAsync(IsolationLevel.ReadCommitted)` | F1.2 | `a-database-of-a-base-outside-the-repo-is-no-method-of-this-type` |
| TD-016 | A DI registration counts for the whole repo, not for the project that runs it, so an interface that two projects register has no single implementation | eshop `ChatState`: `_productImages.GetProductImageUrl(..)` | a `fix(csharp)` PR before F1.2 | `a-registration-counts-for-the-project-that-runs-it` |
| TD-017 | A MSBuild `<Using Include>`, a `using static X;` (read as a namespace) and an alias `using A = B.C;` are not read | H5-D17 | a `fix(csharp)` PR before F1.2 | `an-msbuild-using-is-a-global-using`, `a-using-static-brings-the-types-static-methods`, `an-alias-using-names-the-type` |
| TD-018 | A namespace nested in a block one (`namespace A { namespace B { } }`) is named `B`, not `A.B` | H5-D17 | a `fix(csharp)` PR before F1.2 | `a-nested-block-namespace-is-named-with-the-one-around-it` |
| TD-019 | `this.x` finds a field one base up, where a member reads the whole chain | H5-D17 | a `fix(csharp)` PR before F1.2 | `this-field-of-a-base-two-levels-up-has-its-type` |
| TD-020 | Project references are not read: a type of a project the file's project does not reference is still seen, by its namespace | H5-D17 | a `fix(csharp)` PR before F1.2 | `a-namespace-of-an-unreferenced-project-is-not-seen` |
| TD-021 | An extension block's static members (`Type.M()`) are not read; nor are its extension properties, which make no `CALLS` edge and have no case | H5-D17 | a `fix(csharp)` PR before F1.2 | `an-extension-blocks-static-member-is-called-on-the-type` |
| TD-022 | An array's element types nothing: `arr[0].M()` and `foreach (var x in arr)` | H5-D17 | a `fix(csharp)` PR before F1.2 | `an-array-element-has-the-element-type`, `a-foreach-over-an-array-has-the-element-type` |
| TD-023 | The core holds the syntax of each language: 96 node kinds and fields that only one language's grammars have, in 7 modules (`http_nodes.py` 54, `http_expr.py` 23, `extract.py` 8, `http_base.py` 5, `http_scope.py` 3, `http_wrappers.py` 2, `nearest.py` 1). A language's syntax lives in the core and a new language edits it, where each language's module should declare its own and the core read them through a hook | `indexer/aidd_indexer/core/`; the design review of H5-D22 | H5 steps 6 and 12 | `the-core-names-no-syntax-of-one-language` |
| TD-024 | The core holds the vocabulary of frameworks and HTTP client libraries: 50 router types, client libraries, client methods and framework ids, in 3 modules (`http_base.py` 43, `http_expr.py` 4, `matching.py` 3). A new framework edits the core, where each language's catalog of frameworks should hold its names (ADR-006 §4) | `indexer/aidd_indexer/core/`; the eighth resume run | H5 step 6 | `the-core-names-no-framework-or-client-library` |
| TD-025 | The result of a Python call of a function outside the repo is taken for an instance of the function, so a call on it reaches no method of the repo, where the function may return a value of the repo: `get_object_or_404(Token, ..)` gives a `Token`. Which names outside the repo are classes, and what a function returns, is the package's to say (H5-D26) | netbox `account/views.py:420` (`token.get_auth_header_prefix()`), `dcim/api/views.py:224` (`rack.get_elevation_svg(..)`), `core/views.py:515` (`candidate_config.activate()`) | F1.2 | `a-function-outside-the-repo-may-return-a-value-of-the-repo` |
| TD-026 | A call on a Django model's manager, `Model.objects.<method>(..)`, is found by name among the repo's homonyms. The index cannot type `objects`: a base outside the repo may give it, or the repo declares it with a call the index does not read (`as_manager()`), and the model's name itself may be one only a star import binds. The manager has the methods of Django's `QuerySet` and of the queryset or manager the model declares: that is Django's to say, in its recognizer (ADR-006) | netbox `ipam/tests/test_models.py:1281` (`Region.objects.create(..)`), `circuits/tests/test_models.py:313` (`ObjectChange.objects.get(..)`); 15,961 edges by name on such chains on `main`, 29,474 once netbox's absolute imports resolve (H5-D28) | H5 step 6 | `a-django-model-manager-without-one-of-the-repo-serves-no-method-of-it` |
