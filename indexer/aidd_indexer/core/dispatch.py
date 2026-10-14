"""Mediator dispatch — a plain data module, like `scan_patterns`. Public libraries are built into their
language (`LanguageSupport.dispatch`: MediatR in C#); an organization's own bus is declared by its convention.

In a mediator pattern the caller never names the handler: `bus.SendAsync(new CreateTodoCommand(..))`
reaches `CreateTodoCommandHandler.Handle` because that class implements `ICommandHandler<CreateTodoCommand, ..>`,
whatever its name. Name resolution cannot see that link, and guessing it from the generics alone would
link `validator.ValidateAsync(cmd)` to every `AbstractValidator<cmd>` — what makes a call a dispatch is the
library's contract (which method hands the message over, which base receives it), declared like this:

    dispatch:
      - calls: [SendAsync]                           # the bus method that hands over a message
        handlers: [ICommandHandler]                  # generic bases whose first type argument is the message
        method: Handle                               # the handler method the message reaches

`core/resolve.py` then links the call site to `method` of every type whose base list has one of
`handlers` with the static type of the first argument as its first type argument (strategy
`dispatch`; a published event reaches each of its handlers). The language finds both types
(`LanguageSupport.call_argument_type` / `message_handlers`).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DispatchRule:
    calls: frozenset[str]
    handlers: frozenset[str]
    method: str = "Handle"

    @classmethod
    def from_dict(cls, raw: dict, where: str = "dispatch") -> "DispatchRule":
        from .config import ConfigError
        if not isinstance(raw, dict):
            raise ConfigError(f"{where}: each entry is a mapping {{calls, handlers, method}}")
        calls, handlers = raw.get("calls"), raw.get("handlers")
        if not calls or not handlers:
            raise ConfigError(f"{where}: `calls` (bus methods) and `handlers` (generic handler bases) are required")
        unknown = set(raw) - {"calls", "handlers", "method"}
        if unknown:
            raise ConfigError(f"{where}: unknown key(s) {', '.join(sorted(unknown))} (known: calls, handlers, method)")
        as_set = lambda v: frozenset(str(x) for x in (v if isinstance(v, list) else [v]))   # noqa: E731
        return cls(as_set(calls), as_set(handlers), str(raw.get("method") or "Handle"))


def call_names(rules: list[DispatchRule]) -> frozenset[str]:
    """Every bus method name — the extractor records the first argument's type only for these."""
    return frozenset().union(*(r.calls for r in rules)) if rules else frozenset()
