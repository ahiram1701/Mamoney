import json
import re
import tomllib
from pathlib import Path

import mamoney

ROOT = Path(__file__).resolve().parents[2]


def _pyproject_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def test_fallback_version_matches_pyproject() -> None:
    # El .exe usa este valor si no encuentra los metadatos; si se desfasa, el actualizador
    # creería que siempre hay una versión nueva.
    source = (ROOT / "backend" / "mamoney" / "__init__.py").read_text(encoding="utf-8")
    fallback = re.search(r'__version__ = "([^"]+)"', source)
    assert fallback and fallback.group(1) == _pyproject_version()


def test_frontend_version_matches_pyproject() -> None:
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    assert package["version"] == _pyproject_version()


def test_runtime_version() -> None:
    assert mamoney.__version__ == _pyproject_version()
