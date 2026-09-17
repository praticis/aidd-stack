"""Runtime configuration: environment contract + repo/tenant resolution.

Environment (same names as docker-compose.yml / .env):
  NEO4J_URI        bolt://neo4j:7687
  NEO4J_USERNAME   neo4j
  NEO4J_PASSWORD
  NEO4J_DATABASE   atlas
  WORKSPACE_PATH   /workspace  (root that contains <tenant>/<repo> folders)
  AIDD_TENANT      REQUIRED. Same value setup/install.sh wrote to the skills'
                   `tenant:` frontmatter: `auto` derives the tenant from the
                   path (<WORKSPACE_PATH>/<tenant>/<repo>); anything else is
                   used verbatim. There is deliberately no fallback — a wrong
                   tenant silently splits the graph, so we fail loudly instead.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str
    user: str
    password: str
    database: str

    @classmethod
    def from_env(cls) -> "Neo4jConfig":
        missing = [k for k in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE") if not os.getenv(k)]
        if missing:
            raise ConfigError(f"missing environment variables: {', '.join(missing)}")
        return cls(
            uri=os.environ["NEO4J_URI"],
            user=os.environ["NEO4J_USERNAME"],
            password=os.environ["NEO4J_PASSWORD"],
            database=os.environ["NEO4J_DATABASE"],
        )


DEFAULT_EXCLUDES = {
    ".git", "node_modules", "vendor", "dist", "build", "out", "bin", "obj",
    ".next", ".nuxt", ".venv", "venv", "__pycache__", ".idea", ".vscode",
    "coverage", ".terraform", "target", ".gradle",
}

# Generated code is noise for the graph; extend via .aidd/index.yaml later (F1.1).
GENERATED_SUFFIXES = (".pb.go", "_pb2.py", "_pb2_grpc.py", ".min.js", ".d.ts", ".g.cs", ".Designer.cs")


def workspace_root() -> Path:
    return Path(os.getenv("WORKSPACE_PATH", "/workspace"))


def resolve_repo(arg: str) -> Path:
    """`arg` is either a path or a repo name searched under WORKSPACE_PATH
    (depth 1 = <root>/<repo>, depth 2 = <root>/<tenant>/<repo>)."""
    p = Path(arg)
    if p.is_dir():
        return p.resolve()

    root = workspace_root()
    if p.is_absolute() or arg.startswith(("~", "./", "../")):
        raise ConfigError(f"path '{arg}' does not exist")
    candidates = [c for c in (root / arg,) if c.is_dir()]
    candidates += [c for c in root.glob(f"*/{arg}") if c.is_dir() and c not in candidates]
    candidates = [c for c in candidates if (c / ".git").exists() or any(c.iterdir())]
    if not candidates:
        raise ConfigError(f"repo '{arg}' not found under {root} (tried {root}/{arg} and {root}/*/{arg})")
    if len(candidates) > 1:
        raise ConfigError(f"repo '{arg}' is ambiguous: {', '.join(str(c) for c in candidates)} — pass the full path")
    return candidates[0].resolve()


def resolve_tenant(repo_path: Path, explicit: str | None) -> str:
    """Same rule as the `scan` skill. `--tenant` wins; otherwise AIDD_TENANT is
    required: a fixed value is used verbatim, `auto` derives it from the path."""
    if explicit:
        return explicit
    env = os.getenv("AIDD_TENANT", "").strip()
    if not env:
        raise ConfigError("AIDD_TENANT is not set — it is written to ~/.aidd/.env by setup/install.sh; "
                          "pass --tenant to override for a single run")
    if env != "auto":
        return env
    root = workspace_root().resolve()
    try:
        rel = repo_path.resolve().relative_to(root)
    except ValueError:
        raise ConfigError(f"AIDD_TENANT=auto but {repo_path} is not under WORKSPACE_PATH={root}; "
                          "pass --tenant explicitly")
    if len(rel.parts) < 2:
        raise ConfigError(f"AIDD_TENANT=auto expects <WORKSPACE_PATH>/<tenant>/<repo>, got {root}/{rel} "
                          "(repo sits directly under the workspace root); pass --tenant explicitly")
    return rel.parts[0]
