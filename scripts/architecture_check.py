"""Enforce static boundaries, including imports under TYPE_CHECKING.

Run from any cwd: python scripts/architecture_check.py. No Django initialization.
"""

from __future__ import annotations

import ast
import configparser
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULES = frozenset(("accounts", "athletes", "catalog", "training", "billing", "coach", "sync"))
LAYERS = frozenset(("domain", "application", "adapters", "public"))
INFRASTRUCTURE_STDLIB = frozenset(
    ("http", "urllib", "socket", "ssl", "subprocess", "sqlite3", "configparser", "os", "sys")
)


def import_targets(tree: ast.AST, module: str, is_package: bool) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    package = module if is_package else module.rpartition(".")[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            name = node.module or ""
            if node.level:
                name = importlib.util.resolve_name("." * node.level + name, package)
            result.extend((node.lineno, name + "." + alias.name) for alias in node.names)
    return result


def violations(source: str, module: str, is_package: bool = False) -> list[str]:
    tree = ast.parse(source)
    parts = module.split(".")
    own = parts[2] if len(parts) > 2 and parts[:2] == ["basis", "modules"] else None
    layer = parts[3] if own and len(parts) > 3 else None
    core = (
        module in ("basis", "basis.modules")
        or parts[:2] == ["basis", "shared"]
        or (own is not None and layer is None)
        or layer in ("domain", "application", "public")
    )
    errors: list[str] = []
    if own is not None and (own not in MODULES or (layer is not None and layer not in LAYERS)):
        errors.append(f"{module}: module must use a declared business area and layer")
    if len(parts) > 1 and parts[1] not in ("shared", "bootstrap", "modules"):
        errors.append(f"{module}: code must live in shared, bootstrap or a business module")
    for line, target in import_targets(tree, module, is_package):
        dest = target.split(".")
        reason: str | None = None
        if dest[0] in ("daily_trainning_app", "training"):
            reason = "legacy runtime imports are forbidden"
        elif core and dest[0] in INFRASTRUCTURE_STDLIB:
            reason = "core imports HTTP, configuration or persistence infrastructure"
        elif core and dest[0] not in sys.stdlib_module_names | {"basis", "__future__"}:
            reason = "core imports infrastructure or a third party"
        elif core and dest[:2] == ["basis", "bootstrap"]:
            reason = "core imports bootstrap"
        elif parts[:2] == ["basis", "shared"] and dest[:2] == ["basis", "modules"]:
            reason = "shared imports a business module"
        elif dest[:2] == ["basis", "modules"]:
            other = dest[2] if len(dest) > 2 else None
            dest_layer = dest[3] if len(dest) > 3 else None
            if own and other != own and (dest_layer != "public" or len(dest) < 4):
                reason = "cross-module access must use public"
            elif core and dest_layer is None:
                reason = "core must import a concrete layer or public contract"
            elif core and dest_layer == "adapters":
                reason = "core imports an adapter"
            elif layer == "domain" and dest_layer in ("application", "public") and other == own:
                reason = "domain imports application/public"
            elif layer == "public" and other == own and dest_layer not in ("domain", "application"):
                reason = "public may only export domain/application contracts"
        if target.endswith(".Any") or target == "typing.Any":
            reason = "explicit Any is forbidden"
        if core and dest[0] in ("importlib", "builtins"):
            reason = "dynamic import helpers are forbidden in core"
        if reason:
            errors.append(f"{module}:{line}: {reason}: {target}")
    if core:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in ("__import__", "eval", "exec"):
                    errors.append(f"{module}:{node.lineno}: dynamic execution is forbidden in core")
    return errors


def inventory_files(text: str) -> set[str]:
    data: object = json.loads(text)
    if not isinstance(data, dict) or not isinstance(data.get("files"), list):
        raise ValueError("Invalid legacy inventory")
    values: object = data["files"]
    assert isinstance(values, list)
    if not all(isinstance(value, str) for value in values):
        raise ValueError("Invalid legacy path")
    return {str(value) for value in values}


def inventory_errors(root: Path) -> list[str]:
    baseline_path = "docs/architecture/legacy-baseline.json"
    pending_path = "docs/architecture/legacy-pending.json"
    baseline = inventory_files((root / baseline_path).read_text(encoding="utf-8"))
    pending = inventory_files((root / pending_path).read_text(encoding="utf-8"))
    errors = [f"Legacy inventory grew: {path}" for path in sorted(pending - baseline)]
    # HEAD is the integration base during local edits; HEAD^ catches growth in CI.
    for ref in ("HEAD", "HEAD^"):
        previous = subprocess.run(
            ["git", "show", f"{ref}:{pending_path}"], cwd=root, capture_output=True, text=True
        )
        if previous.returncode == 0:
            errors.extend(
                f"Legacy inventory reintroduced: {p}"
                for p in sorted(pending - inventory_files(previous.stdout))
            )
        frozen = subprocess.run(
            ["git", "show", f"{ref}:{baseline_path}"], cwd=root, capture_output=True, text=True
        )
        if frozen.returncode == 0 and baseline != inventory_files(frozen.stdout):
            errors.append("Legacy baseline is immutable")
    tracked = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", "*.py"],
        cwd=root,
        text=True,
    ).splitlines()
    strict_entries: set[str] = set()
    for filename in ("mypy-core.ini", "mypy-django.ini"):
        config = configparser.ConfigParser()
        config.read(root / filename)
        strict_entries.update(p.strip() for p in config.get("mypy", "files").split(","))
        for section in config.sections():
            if config.get(section, "follow_imports", fallback="normal") != "silent":
                continue
            if not section.startswith("mypy-"):
                errors.append("Global silent imports are forbidden")
                continue
            for module in section.removeprefix("mypy-").split(","):
                module = module.strip()
                if "*" in module or module.replace(".", "/") + ".py" not in pending:
                    errors.append(
                        f"Silent imports must name an exact pending legacy module: {module}"
                    )
    for path in tracked:
        # A tracked deletion is part of the candidate, not pending legacy code.
        if not (root / path).is_file():
            continue
        strict = any(
            path == entry or path.startswith(entry.rstrip("/") + "/") for entry in strict_entries
        )
        if not strict and path not in pending:
            errors.append(f"Python file outside strict scope and legacy inventory: {path}")
        if strict and path in pending:
            errors.append(f"Strict code cannot be exempted as legacy: {path}")
    return errors



def final_layout_errors(root: Path) -> list[str]:
    """ADR-002 final runtime layout; historical tests are not installed apps."""
    errors: list[str] = []
    for path in sorted((root / "daily_trainning_app").rglob("*.py")):
        errors.append(f"Retired daily application source remains: {path.relative_to(root)}")
    for path in sorted((root / "training").rglob("*.py")):
        relative = path.relative_to(root / "training")
        if relative.parts[0] != "tests" and relative.as_posix() != "__init__.py":
            errors.append(f"Retired training runtime source remains: {path.relative_to(root)}")
    for path in sorted((root / "basis_trainning_app").glob("*.py")):
        for line, target in import_targets(ast.parse(path.read_text(encoding="utf-8")),
                                           "basis_trainning_app." + path.stem, False):
            if target.split(".")[0] in ("daily_trainning_app", "training"):
                errors.append(f"Project configuration imports retired runtime: {path.name}:{line}")
    return errors


def main() -> int:
    errors: list[str] = []
    for path in sorted((ROOT / "basis").rglob("*.py")):
        relative = path.relative_to(ROOT).with_suffix("")
        module = ".".join(relative.parts)
        is_package = path.name == "__init__.py"
        if is_package:
            module = module.removesuffix(".__init__")
        errors.extend(violations(path.read_text(encoding="utf-8"), module, is_package))
    errors.extend(inventory_errors(ROOT))
    errors.extend(final_layout_errors(ROOT))
    for error in errors:
        print(error)
    if not errors:
        print(
            "VERIFIED: layer/public boundaries and legacy inventory (including type-only imports)"
        )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
