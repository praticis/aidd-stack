"""Which of a call's homonyms found by name it reaches when no type tells: the nearest, in the caller's file, then in
its module, then the only one in the repo; none when several are as near outside them. Among the repo's extension
methods, the only ones some calls can reach, the language may prove some cannot take the call: dropping them takes
targets away, and never makes a guess more than it was."""

from __future__ import annotations

from typing import Callable

from .model import FileInfo, SymbolInfo

Picked = list[tuple[SymbolInfo, str]]


def fits(s: SymbolInfo, argc: int | None) -> bool:
    return argc is None or s.arity is None or (s.arity[0] <= argc and (s.arity[1] is None or argc <= s.arity[1]))


def fitting(syms: list[SymbolInfo], argc: int | None) -> list[SymbolInfo]:
    """The symbols a call with `argc` arguments can reach (overloads by arity); unchanged when the count or the
    arities are unknown, or when none fits."""
    return [s for s in syms if fits(s, argc)] or syms if len(syms) > 1 else syms


def nearest(c, cands: list[SymbolInfo], files_by_id: dict[str, FileInfo], module: str | None) -> Picked:
    """The homonyms in the caller's file, else in its `module`, else the only one in the repo, with the strategy that
    found them, `-ambiguous` when there are several."""
    same_file = [s for s in cands if s.file_id == c.file_id]
    if same_file:
        chosen, strat = same_file, "same-file"
    else:
        same_mod = [s for s in cands if files_by_id[s.file_id].module_id == module]
        if same_mod:
            chosen, strat = same_mod, "same-module"
        elif len(cands) == 1:
            chosen, strat = cands, "unique-name"
        else:
            return []
    # `this.x()` / `self.x()` / `s.x()` with a receiver only makes sense for methods
    if c.receiver and c.receiver not in ("this", "self", "cls"):
        chosen = [s for s in chosen if s.kind == "method"] or chosen
    if len(chosen) > 1:
        # homonyms found by name: the argument count trims the guesses, it does not make one of them proven
        strat += "-ambiguous"
        chosen = fitting(chosen, c.arg_count)[:3]
    return [(s, strat) for s in chosen]


def pruned(pick: Callable[[list[SymbolInfo]], Picked], cands: list[SymbolInfo], fit: dict[str, str]) -> Picked:
    """What `pick` reaches among extension methods once those the language proves cannot take the call (`fit`) are
    dropped. One whose fit is unknown keeps what it had beside them, `-ambiguous` included: that they cannot take the
    call says nothing of whether it can. A compatible one takes the strategy left, and is a new target only alone:
    dropping rivals adds no guess."""
    before = pick(cands)
    kept = [s for s in cands if fit[s.id] != "incompatible"]
    if len(kept) == len(cands):
        return before
    had = {s.id: strat for s, strat in before}
    after = pick(kept)
    return [(s, strat if fit[s.id] == "compatible" else had[s.id]) for s, strat in after
            if s.id in had or (fit[s.id] == "compatible" and len(after) == 1)]
