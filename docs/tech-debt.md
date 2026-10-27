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
- A debt closes in the PR that removes its xfail mark; its row here is then marked closed with that PR.

Seen at: public corpus repos only. Decided by the author on 2026-10-27, with the acceptance of H5-D18
([decisions.md](decisions.md)). SCIP is a possible remedy for some of them, not a proven one.

| ID | The debt | Seen at | Due | Case |
|---|---|---|---|---|
| TD-001 | An untyped receiver reaches only the repo's extensions: a call with type arguments on an extension block's receiver, or on a `var` taken from a positional record's property, never reaches the type's own method | elsa `ExpressionEvaluatorExtensions.cs:20`, `DictionaryValueEvaluator.cs:48` (`EvaluateAsync`) | F1.2; the resolver may fix the first earlier | `an-extension-blocks-receiver-reaches-its-types-own-method`, `a-var-from-a-positional-records-property-has-its-type` |
| TD-002 | A type outside the repo has no known members, so an extension on an interface is taken for the type's own method | smartstore `HybridExpando.cs:447`, `:466`, `ExpressionVisitor.cs:279` (`List<T>.AsReadOnly()`) | F1.2, or reference-assembly metadata | `an-outside-types-own-method-is-no-repo-extension` |
| TD-003 | A member reached through a package's type has no type, so an extension on an interface is taken for it. A recorded limit of H5-D16 and H5-D17 | bitwarden `DuoUniversalTokenService.cs:194`, jellyfin `GroupTests.cs:64`, notifo `DefaultUserService.cs:48`, umbraco `DeliveryApiSettingsValidatorTests.cs:97`, elsa `WorkflowTriggerEqualityComparer.cs:45` | F1.2 | `a-member-reached-through-a-package-type-has-its-own-method` |
| TD-004 | The arguments' types are not compared between overloads of one arity. A recorded limit of H5-D16 | clean-arch-dotnet `EndpointRouteBuilderExtensions.cs:24`, rapid-blazor `IAuthorizationServiceExtensions.cs:11`, and jellyfin's site of TD-003 | F1.2 | `the-arguments-types-tell-the-overloads-of-one-arity-apart` |
| TD-005 | A `this` of a predefined type (`this string`) has no name in the type facts, so it is taken for any receiver | umbraco `BackOfficeController.cs:433`, radarr `169_custom_format_scores.cs:75` | a `fix(csharp)` PR before F1.2 | `an-extension-of-a-predefined-type-is-not-taken-for-another-types-method` |
| TD-006 | The count of type arguments is not compared with the method's type parameters | elsa `MassTransitWorkflowDispatcherFeature.cs:26`, `DictionaryExtensions.cs:68` | a `fix(csharp)` PR before F1.2, after a compiler shows how C# 14 counts explicit type arguments on an extension block's method | `a-call-with-two-type-arguments-reaches-only-the-overload-with-two`; the block's case is still to write |
