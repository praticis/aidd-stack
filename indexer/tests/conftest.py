"""Convention extensions under indexer/conventions/<name>/ are importable in tests without being
installed (the image installs them; see Dockerfile)."""
import sys
from pathlib import Path

for pkg in sorted((Path(__file__).resolve().parents[1] / "conventions").glob("*/pyproject.toml")):
    sys.path.insert(0, str(pkg.parent))
