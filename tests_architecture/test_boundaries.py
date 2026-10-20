"""Executable architecture contracts; no Django, database or credentials."""

import configparser
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.architecture_check import final_layout_errors, violations

ROOT = Path(__file__).resolve().parent.parent


class BoundaryTests(unittest.TestCase):
    def test_rejects_framework_legacy_and_provider_in_core(self) -> None:
        for source in (
            "import django",
            "from rest_framework import serializers",
            "from training.models import Session",
            "import httpx",
            "from basis.bootstrap import training",
            "from os import environ",
            "from urllib.request import urlopen",
            "import sqlite3",
        ):
            with self.subTest(source=source):
                self.assertTrue(violations(source, "basis.modules.training.domain.session"))

    def test_type_only_imports_are_checked(self) -> None:
        source = "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n import django\n"
        self.assertTrue(violations(source, "basis.modules.training.application.session"))

    def test_relative_adapter_import_is_rejected(self) -> None:
        self.assertTrue(
            violations("from ..adapters import repository", "basis.modules.training.domain.session")
        )

    def test_cross_module_internals_are_rejected_in_adapters_too(self) -> None:
        for layer in ("domain", "application", "adapters"):
            self.assertTrue(
                violations(
                    f"from basis.modules.billing.{layer} import Access",
                    "basis.modules.training.adapters.repository",
                )
            )

    def test_adapters_cannot_import_retired_runtime(self) -> None:
        for source in ("from training.models import Session", "import daily_trainning_app"):
            self.assertTrue(violations(source, "basis.modules.training.adapters.views"))

    def test_final_layout_rejects_old_namespaces_and_allows_regression_tests(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "config").mkdir()
            for filename in ("__init__.py", "settings.py", "test_settings.py", "urls.py", "asgi.py", "wsgi.py"):
                (root / "config" / filename).write_text("", encoding="utf-8")
            (root / "tests" / "regression").mkdir(parents=True)
            (root / "tests" / "regression" / "test_history.py").write_text("", encoding="utf-8")
            (root / "training").mkdir()
            self.assertFalse(final_layout_errors(root))
            (root / "training" / "models.py").write_text("", encoding="utf-8")
            self.assertEqual(len(final_layout_errors(root)), 1)
            (root / "daily_trainning_app").mkdir()
            (root / "daily_trainning_app" / "__init__.py").write_text("", encoding="utf-8")
            self.assertEqual(len(final_layout_errors(root)), 2)

    def test_views_reject_direct_writes_and_transactions_but_allow_binding(self) -> None:
        module = "basis.modules.training.adapters.views"
        for source in (
            "from .models import Session\nSession.objects.create(title='x')",
            "from .models import Session\nSession.objects.filter(pk=1).update(title='x')",
            "from django.db import transaction",
            "form.save()",
        ):
            with self.subTest(source=source):
                self.assertTrue(violations(source, module))
        self.assertFalse(violations("form.save(commit=False)", module))
        self.assertFalse(violations("from .models import Session\nSession.objects.filter(pk=1)", module))
        self.assertFalse(violations("cases().save_strength(command)", module))

    def test_final_configuration_cannot_be_an_old_named_package(self) -> None:
        self.assertTrue(violations("from basis_trainning_app import settings", "basis.modules.training.adapters.views"))
        with tempfile.TemporaryDirectory() as folder:
            errors = final_layout_errors(Path(folder))
            self.assertEqual(len(errors), 6)
            self.assertTrue(all("config/" in error for error in errors))

    def test_public_contract_import_is_allowed(self) -> None:
        self.assertFalse(
            violations(
                "from basis.modules.billing.public import Access",
                "basis.modules.training.application.session",
            )
        )

    def test_domain_cannot_import_own_application(self) -> None:
        self.assertTrue(
            violations(
                "from ..application import StartSession", "basis.modules.training.domain.session"
            )
        )

    def test_public_contract_cannot_leak_adapter(self) -> None:
        self.assertTrue(
            violations("from .adapters import Repository", "basis.modules.training.public")
        )

    def test_shared_cannot_import_business_module(self) -> None:
        self.assertTrue(
            violations(
                "from basis.modules.training.public import Session", "basis.shared.identifiers"
            )
        )

    def test_any_alias_and_dynamic_execution_are_rejected(self) -> None:
        for source in (
            "from typing import Any as Payload",
            "__import__('django')",
            "import importlib",
            "eval('import django')",
        ):
            self.assertTrue(violations(source, "basis.modules.training.domain.session"))

    def test_application_can_import_domain(self) -> None:
        self.assertFalse(
            violations("from ..domain import Session", "basis.modules.training.application.session")
        )

    def test_code_cannot_bypass_declared_layers(self) -> None:
        self.assertTrue(violations("", "basis.modules.training.models"))
        self.assertTrue(violations("", "basis.providers"))

    def test_bootstrap_can_wire_django_adapters(self) -> None:
        self.assertFalse(violations("import django", "basis.bootstrap", is_package=True))

    def test_all_core_modules_import_without_site_packages_or_settings(self) -> None:
        # -I ignores environment/PYTHONPATH; -S removes site packages, including Django.
        code = """
import importlib, pathlib, sys
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root))
for path in sorted((root / 'basis').rglob('*.py')):
    parts = path.relative_to(root).with_suffix('').parts
    if 'adapters' in parts or 'bootstrap' in parts:
        continue
    module = '.'.join(parts).removesuffix('.__init__')
    importlib.import_module(module)
assert 'django' not in sys.modules
"""
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-c", code, str(ROOT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_core_mypy_has_no_django_plugin_or_missing_import_exemption(self) -> None:
        config = configparser.ConfigParser()
        config.read(ROOT / "mypy-core.ini")
        self.assertFalse(config.has_option("mypy", "plugins"))
        self.assertFalse(config.has_option("mypy", "ignore_missing_imports"))
        self.assertTrue(config.getboolean("mypy", "strict"))
        self.assertTrue(config.getboolean("mypy", "disallow_any_explicit"))
        self.assertTrue(config.getboolean("mypy", "disallow_any_unimported"))

    def test_mypy_rejects_mixed_identifiers_and_any(self) -> None:
        source = """
from typing import Any
from missing_architecture_dependency import Missing
from basis.shared.identifiers import AccountId, AthleteId
def accepts_account(value: AccountId) -> None:
    pass
accepts_account(AthleteId(1))
def explicit(value: Any) -> None:
    pass
def imported(value: Missing) -> None:
    pass
"""
        config = configparser.ConfigParser()
        config.read(ROOT / "mypy-core.ini")
        config.remove_option("mypy", "files")
        with tempfile.TemporaryDirectory() as folder:
            filename = Path(folder) / "mypy.ini"
            with filename.open("w", encoding="utf-8") as handle:
                config.write(handle)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mypy",
                    "--config-file",
                    str(filename),
                    "--no-incremental",
                    "-c",
                    source,
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        for code in ("[arg-type]", "[explicit-any]", "[no-any-unimported]"):
            self.assertIn(code, result.stdout)


if __name__ == "__main__":
    unittest.main()
