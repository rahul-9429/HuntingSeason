import ast
from pathlib import Path

SERVICES = Path(__file__).resolve().parent.parent / "services"


def imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def test_services_never_import_the_api():
    # A future worker imports services/ alone, so it must not drag in FastAPI routes
    offenders = {
        str(path.relative_to(SERVICES.parent)): sorted(m for m in imported_modules(path) if m.split(".")[0] == "api")
        for path in SERVICES.rglob("*.py")
    }
    assert {path: modules for path, modules in offenders.items() if modules} == {}
