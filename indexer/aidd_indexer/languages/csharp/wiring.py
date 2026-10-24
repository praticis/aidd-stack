"""What a C# repo wires up to run, read off its type facts through the type index: the types that handle a message a
mediator sends, and what the DI container builds for an interface."""

from __future__ import annotations

from ...core.config import is_test_path
from ...core.model import FileInfo
from .type_facts import CsTypes
from .type_index import CsTypeIndex, Declared


def handlers(types: CsTypeIndex, file: FileInfo, message_type: str, handler_bases: frozenset[str]) -> list[str]:
    """The types whose generic base among `handler_bases` takes the message type sent from `file` first."""
    sent = types.lookup(file, message_type)
    out: list[str] = []
    for d in types.declarations():
        for base, targs in d.type.generic_bases if d.type.kind != "interface" else ():
            if base in handler_bases and targs and _same(types, sent, d.file, targs[0], message_type):
                out.append(d.qualified)
    return sorted(set(out))


def di_chain(types: CsTypeIndex, interface: str) -> list[str] | None:
    """What the container builds for an interface (qualified), innermost first: `[UpdateCacheStep,
    CommitActivityStep, CheckTodoStep]` for `AddScoped<I, UpdateCacheStep>(); Decorate<I, CommitActivityStep>();
    Decorate<I, CheckTodoStep>()`. An interface registered in more than one file (environments, tests) has none:
    which one runs cannot be told."""
    if types.chains is None:
        found: dict[str, list[list[str]]] = {}
        for f, facts in types.files():
            if not is_test_path(f.path):
                for qi, chain in _registered(types, f, facts).items():
                    found.setdefault(qi, []).append(chain)
        types.chains = {qi: chains[0] for qi, chains in found.items() if len(chains) == 1 and "" not in chains[0]}
    return types.chains.get(interface)


def _registered(types: CsTypeIndex, f: FileInfo, facts: CsTypes) -> dict[str, list[str]]:
    here: dict[str, list[str]] = {}
    for method, (iface, impl) in facts.registrations:
        qi, qt = types.lookup(f, iface), types.lookup(f, impl)
        if qi is None or qt is None:
            continue
        if method == "Decorate":
            if qi.qualified in here:
                here[qi.qualified].append(qt.qualified)
        elif qi.qualified in here and len(here[qi.qualified]) == 1:
            here[qi.qualified] = [""]                       # registered twice for one interface: no single base
        else:
            here[qi.qualified] = [qt.qualified]
    return here


def _same(types: CsTypeIndex, sent: Declared | None, file: FileInfo, handled_name: str, message_type: str) -> bool:
    """Both in the repo: the same qualified type; both outside (a package's message): the same name."""
    handled = types.lookup(file, handled_name)
    if sent and handled:
        return sent.qualified == handled.qualified
    return not sent and not handled and handled_name == message_type
