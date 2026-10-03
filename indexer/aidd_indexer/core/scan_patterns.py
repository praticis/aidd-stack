"""What a convention adds to the HTTP scanners (F0.4.5) — a plain data module so `conventions/`
can import it without pulling the scanners (and the language registry) in."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScanPatterns:
    """What a *convention* adds to the HTTP scanners (F0.4.5): route registrars and HTTP client
    methods of the organization's own SDK, which the generic tables cannot know.

    * `registrars`: function name -> HTTP method (`"GET"`), or None when the method is an argument
      or unknown (`ANY`). `srv.Route("GET", "/v1/x", h)` → `{"Route": null}`.
    * `clients`: method name -> HTTP method, or None to read it from the arguments / request object.
    * `client_receivers`: receiver names (last segment, case-insensitive) to treat as HTTP clients,
      so generic verbs on them (`gateway.Do(...)`) count as outbound calls.
    """
    registrars: dict[str, str | None] = field(default_factory=dict)
    clients: dict[str, str | None] = field(default_factory=dict)
    client_receivers: frozenset[str] = frozenset()

    def merge(self, other: "ScanPatterns") -> "ScanPatterns":
        return ScanPatterns({**self.registrars, **other.registrars}, {**self.clients, **other.clients},
                            self.client_receivers | other.client_receivers)

    def is_client(self, receiver: str) -> bool:
        return receiver.lower() in self.client_receivers

    @classmethod
    def from_dict(cls, raw: dict) -> "ScanPatterns":
        def table(d) -> dict[str, str | None]:
            if isinstance(d, list):
                return {str(k): None for k in d}
            return {str(k): (str(v).upper() if v else None) for k, v in (d or {}).items()}
        routes = raw.get("route_patterns") or {}
        clients = raw.get("client_patterns") or {}
        return cls(table(routes.get("registrars")), table(clients.get("methods")),
                   frozenset(str(r).lower() for r in clients.get("receivers") or ()))
