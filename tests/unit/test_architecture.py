import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "irobot"
FORBIDDEN = {"app": ("irobot.tools",)}


def _imports(path: Path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


@pytest.mark.parametrize("package", FORBIDDEN)
def test_layer_dependencies(package):
    offenders = [
        f"{path.relative_to(SRC)} -> {name}"
        for path in (SRC / package).rglob("*.py")
        for name in _imports(path)
        if any(name == f or name.startswith(f + ".") for f in FORBIDDEN[package])
    ]
    assert not offenders, offenders
