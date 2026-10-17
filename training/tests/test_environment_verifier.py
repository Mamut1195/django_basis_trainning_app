"""Isolation tests runnable without configuring Django or creating its test database."""

import contextlib
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import verify_environment as verifier


class EnvironmentVerifierTests(unittest.TestCase):
    def setUp(self):
        cache = verifier.ROOT / ".cache"
        cache.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="verifier-tests-", dir=cache)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def completed(self, status="VERIFIED", returncode=0):
        return subprocess.CompletedProcess(
            [], returncode, json.dumps({"status": status, "steps": []}), "private stderr"
        )

    def test_environment_allowlist_discards_database_and_service_configuration(self):
        inherited = {
            "DATABASE_URL": "postgresql://private:secret@127.0.0.1:1/never-connect",
            "BASIS_DATABASE_PATH": "db.sqlite3",
            "DJANGO_SETTINGS_MODULE": "production.settings",
            "DJANGO_SECRET_KEY": "private-key",
            "EMAIL_HOST_PASSWORD": "smtp-secret",
            "POLAR_ACCESS_TOKEN": "polar-secret",
            "DEEPSEEK_API_KEY": "model-secret",
            "AI_ENABLED": "1",
            "PYTHONPATH": "foreign-code",
            "SYSTEMROOT": "C:\\Windows",
        }
        with mock.patch.dict(os.environ, inherited, clear=True):
            environment = verifier.safe_environment(self.root / "new.sqlite3")
        self.assertNotIn("DATABASE_URL", environment)
        for name in ("EMAIL_HOST_PASSWORD", "POLAR_ACCESS_TOKEN", "DEEPSEEK_API_KEY", "PYTHONPATH"):
            self.assertNotIn(name, environment)
        self.assertEqual(environment["BASIS_DATABASE_PATH"], str(self.root / "new.sqlite3"))
        self.assertEqual(environment["DJANGO_SETTINGS_MODULE"], verifier.SETTINGS)
        self.assertNotEqual(environment["DJANGO_SECRET_KEY"], "private-key")
        self.assertEqual(environment["AI_ENABLED"], "0")

    def test_existing_and_foreign_database_paths_are_rejected_without_deleting(self):
        cache = self.root / ".cache"
        owned = cache / "environment-owned"
        owned.mkdir(parents=True)
        existing = owned / "verification.sqlite3"
        existing.write_bytes(b"keep existing database")
        foreign = self.root / "foreign" / "verification.sqlite3"
        foreign.parent.mkdir()
        foreign.write_bytes(b"keep foreign database")
        with mock.patch.object(verifier, "ROOT", self.root):
            for database in (existing, foreign, self.root / "db.sqlite3"):
                with self.subTest(path=database), self.assertRaises(verifier.VerificationError):
                    verifier.require_disposable(database)
        self.assertEqual(existing.read_bytes(), b"keep existing database")
        self.assertEqual(foreign.read_bytes(), b"keep foreign database")

    def test_success_and_failure_cleanup_only_the_allocated_directory(self):
        cache = self.root / ".cache"
        neighbour = cache / "someone-elses-work"
        neighbour.mkdir(parents=True)
        sentinel = neighbour / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        outcomes = (
            self.completed(),
            self.completed("FAILED", 1),
            OSError("private credential in OS error"),
            subprocess.TimeoutExpired("private command", 1, output="private output"),
            subprocess.CompletedProcess([], 7, "private invalid output", "private traceback"),
        )
        for outcome, expected_code in zip(outcomes, (0, 1, 2, 3, 2), strict=True):
            with self.subTest(outcome=type(outcome).__name__):
                options = (
                    {"side_effect": outcome}
                    if isinstance(outcome, Exception)
                    else {"return_value": outcome}
                )
                with (
                    mock.patch.object(verifier, "ROOT", self.root),
                    mock.patch.object(verifier.subprocess, "run", **options) as run,
                ):
                    report, code = verifier.run_verification(sys.executable, timeout=1)
                self.assertEqual(code, expected_code)
                self.assertEqual(report["cleanup"], "VERIFIED")
                self.assertFalse((self.root / report["temporary_database"]).parent.exists())
                self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
                self.assertNotIn("private", json.dumps(report))
                self.assertNotIn("DATABASE_URL", run.call_args.kwargs["env"])
                self.assertEqual(run.call_args.args[0][1:3], ["-I", "-B"])

    def test_cleanup_error_is_reported_as_failure(self):
        cache = self.root / ".cache"
        cache.mkdir()
        scratch = tempfile.TemporaryDirectory(prefix="environment-", dir=cache)
        self.addCleanup(scratch.cleanup)
        with (
            mock.patch.object(verifier, "ROOT", self.root),
            mock.patch.object(verifier.subprocess, "run", return_value=self.completed()),
            mock.patch.object(verifier.tempfile, "TemporaryDirectory", return_value=scratch),
            mock.patch.object(scratch, "cleanup", side_effect=PermissionError("secret")),
        ):
            report, code = verifier.run_verification(sys.executable)
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "FAILED")
        self.assertEqual(report["cleanup"], "FAILED")
        self.assertEqual(report["error"], "temporary_cleanup_failed")
        self.assertNotIn("secret", json.dumps(report))

    def test_dependency_pins_accept_windows_utf8_bom_and_reject_mismatch(self):
        (self.root / "requirements.txt").write_text("django==5.2.18\n", encoding="utf-8-sig")
        with mock.patch.object(verifier, "ROOT", self.root):
            report = {}
            verifier.dependency_check(report)
            self.assertEqual(report["dependencies"], {"checked": 1, "mismatches": []})
            with mock.patch.object(verifier.importlib.metadata, "version", return_value="0.0"):
                with self.assertRaisesRegex(verifier.VerificationError, "dependency_mismatch"):
                    verifier.dependency_check({})

    def test_report_refuses_existing_file_before_running(self):
        target = self.root / "existing.sqlite3"
        target.write_bytes(b"unrelated data")
        with mock.patch.object(verifier, "run_verification") as run:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = verifier.main(["--python", sys.executable, "--report", str(target)])
        run.assert_not_called()
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())["error"], "report_create_failed")
        self.assertEqual(target.read_bytes(), b"unrelated data")

    def test_cli_real_sqlite_database_url_is_never_used(self):
        sentinel = self.root / "inherited.sqlite3"
        with contextlib.closing(sqlite3.connect(sentinel)) as connection:
            with connection:
                connection.execute("CREATE TABLE sentinel (value TEXT)")
                connection.execute("INSERT INTO sentinel VALUES ('untouched')")
        before = sentinel.read_bytes()
        report_file = self.root / "report.json"
        env = {
            **os.environ,
            "DATABASE_URL": "sqlite:///" + str(sentinel),
            "BASIS_DATABASE_PATH": str(sentinel),
            "DJANGO_SETTINGS_MODULE": "does_not_exist.production",
            "DJANGO_DEBUG": "0",
            "DJANGO_SECRET_KEY": "private-inherited-secret",
            "POLAR_ACCESS_TOKEN": "private-polar-token",
            "EMAIL_PORT": "invalid-production-setting",
            "AI_ENABLED": "1",
        }
        process = subprocess.run(
            [
                sys.executable,
                "-B",
                str(verifier.ROOT / "scripts" / "verify_environment.py"),
                "--python",
                sys.executable,
                "--report",
                str(report_file),
            ],
            cwd=verifier.ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180,
            check=False,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual(report, json.loads(report_file.read_text(encoding="utf-8")))
        self.assertEqual([step["status"] for step in report["steps"]], ["VERIFIED"] * 6)
        self.assertEqual(report["cleanup"], "VERIFIED")
        self.assertTrue(report["runtime"]["authenticated_session"])
        self.assertTrue(report["runtime"]["csrf_checks"])
        self.assertFalse((verifier.ROOT / report["temporary_database"]).parent.exists())
        self.assertEqual(sentinel.read_bytes(), before)
        self.assertNotIn("private-inherited-secret", process.stdout + process.stderr)
        self.assertNotIn("private-polar-token", process.stdout + process.stderr)


if __name__ == "__main__":
    unittest.main()
