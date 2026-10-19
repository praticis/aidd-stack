# aidd-stack

A local stack for AI-assisted development across a portfolio of repositories. It indexes each repository into a
code graph (Neo4j, `atlas`) with symbols, calls, imports, the HTTP routes each service exposes, the calls it makes,
and the links between services. The graph reaches the development skills through an MCP server. Extraction is
deterministic (tree-sitter, with SCIP planned), and an LLM never parses code.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/praticis/aidd-stack/refs/heads/main/setup/install.sh | bash
```

Then run `~/.aidd/install-check.sh`.

## Where to start

- [`AGENTS.md`](AGENTS.md): the entry point for a contributor or their AI. It has the repository map, the
  architecture, and how to test and measure. It is in Portuguese for now; the English docs come with the public
  docs work.
- [`docs/ROADMAP.md`](docs/ROADMAP.md): what is open, and in what order.
