"""Operational failure paths: no leaked diagnostics, overwrite or false readiness."""

import contextlib
import io
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.db import OperationalError
from django.test import SimpleTestCase, override_settings

from basis.adapters.web.operational_logging import SafeGunicornErrorFilter, SafeHTTPFilter
from scripts import backup_db, healthcheck


@override_settings(
    DATABASES={
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "basis_verify_test",
            "USER": "synthetic",
            "PASSWORD": "do-not-print-this-password",
            "HOST": "127.0.0.1",
            "PORT": "5432",
        }
    }
)
class BackupFailureTests(SimpleTestCase):
    def invoke(self, arguments: list[str]) -> tuple[int, str]:
        output = io.StringIO()
        with (
            patch("sys.argv", ["backup_db.py", *arguments]),
            contextlib.redirect_stderr(output),
            contextlib.redirect_stdout(output),
        ):
            result = backup_db.main()
        return result, output.getvalue()

    def test_failed_dump_removes_partial_and_suppresses_sensitive_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "failed.dump"
            failure = subprocess.CalledProcessError(
                1, ["pg_dump"], stderr=b"do-not-print-this-password private-row-data"
            )
            with patch.object(backup_db, "pg_run", side_effect=failure):
                result, output = self.invoke(["backup", str(target)])
            self.assertEqual(result, 1)
            self.assertNotIn("do-not-print", output)
            self.assertNotIn("private-row", output)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_existing_backup_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "existing.dump"
            target.write_bytes(b"keep-existing")
            with patch.object(backup_db, "pg_run") as command:
                result, _ = self.invoke(["backup", str(target)])
            self.assertEqual(result, 1)
            command.assert_not_called()
            self.assertEqual(target.read_bytes(), b"keep-existing")

    def test_invalid_restore_archive_never_creates_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "invalid.dump"
            target.write_bytes(b"not-a-postgresql-archive")
            with patch.object(
                backup_db, "pg_run", side_effect=subprocess.CalledProcessError(1, ["pg_restore"])
            ) as command:
                result, _ = self.invoke(
                    ["restore-test", str(target), "--database", "basis_restore_test"]
                )
            self.assertEqual(result, 1)
            self.assertEqual(command.call_count, 1)
            self.assertEqual(command.call_args.args[0][:2], ["pg_restore", "--list"])

    def test_restore_rejects_source_database_and_unsafe_names(self) -> None:
        for name in ("basis_verify_test", "production", "basis_restore_unsafe;DROP"):
            with self.subTest(name=name), patch.object(backup_db, "pg_run") as command:
                with self.assertRaises(SystemExit):
                    self.invoke(["restore-test", "unused.dump", "--database", name])
                command.assert_not_called()


class ReadinessTests(SimpleTestCase):
    def test_gunicorn_error_retains_safe_event_and_class_not_exception_values(self) -> None:
        try:
            raise RuntimeError("PRIVATE_EXCEPTION_URL?token=PRIVATE_QUERY")
        except RuntimeError:
            exception = sys.exc_info()
        record = logging.LogRecord(
            "gunicorn.error",
            logging.ERROR,
            "",
            1,
            "Error handling request %s",
            ("/PRIVATE_PATH?token=PRIVATE_QUERY",),
            exception,
        )
        self.assertTrue(SafeGunicornErrorFilter().filter(record))
        self.assertEqual(
            record.getMessage(),
            "gunicorn event=request_exception status=500 exception=RuntimeError",
        )
        self.assertIsNone(record.exc_info)
        self.assertIsNone(record.exc_text)

    def test_unknown_gunicorn_event_never_formats_arguments_or_invents_status(self) -> None:
        record = logging.LogRecord(
            "gunicorn.error",
            logging.CRITICAL,
            "",
            1,
            "unknown PRIVATE_MESSAGE %s",
            ({"token": "PRIVATE_ARGUMENT"},),
            None,
        )
        self.assertTrue(SafeGunicornErrorFilter().filter(record))
        self.assertEqual(
            record.getMessage(), "gunicorn event=server_event status=0 exception=Unavailable"
        )
        self.assertEqual(record.levelno, logging.CRITICAL)

    def test_production_http_filter_removes_tokens_request_and_exception_data(self) -> None:
        record = logging.LogRecord(
            "django.security", logging.ERROR, "", 1, "token=%s", ("secret",), None
        )
        record.status_code = 403
        record.request = "private request body"
        record.exc_text = "private exception details"
        record.stack_info = "private stack"
        self.assertTrue(SafeHTTPFilter().filter(record))
        self.assertEqual(record.getMessage(), "HTTP failure status=403")
        self.assertIsNone(record.exc_text)
        self.assertIsNone(record.stack_info)
        self.assertNotIn("request", record.__dict__)

    def test_health_db_failure_is_503_without_database_details(self) -> None:
        with patch("django.db.connection") as connection:
            connection.cursor.side_effect = OperationalError("private-db-password")
            response = self.client.get("/health/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertNotContains(response, "private-db-password", status_code=503)

    def test_probe_uses_explicit_allowed_host_and_no_proxy(self) -> None:
        with (
            patch.dict("os.environ", {"DJANGO_HEALTH_HOST": "production.example.test"}),
            patch("urllib.request.build_opener") as build,
        ):
            build.return_value.open.return_value.__enter__.return_value.status = 200
            self.assertEqual(healthcheck.main(), 0)
            request = build.return_value.open.call_args.args[0]
            self.assertEqual(request.get_header("Host"), "production.example.test")
            self.assertEqual(request.full_url, "http://127.0.0.1:8000/health/")

    def test_probe_failure_has_no_exception_or_body_output(self) -> None:
        output = io.StringIO()
        with (
            patch("urllib.request.build_opener", side_effect=OSError("private failure")),
            contextlib.redirect_stderr(output),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(healthcheck.main(), 1)
        self.assertEqual(output.getvalue(), "")


class VerifierEnvironmentTests(SimpleTestCase):
    def test_missing_git_writes_failed_json_without_traceback(self) -> None:
        self.check_environment_failure(missing_git=True)

    def test_missing_repository_writes_failed_json_without_traceback(self) -> None:
        self.check_environment_failure(missing_git=False)

    def check_environment_failure(self, *, missing_git: bool) -> None:
        source = Path(__file__).resolve().parents[3] / "scripts/verify_operations.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / "scripts"
            scripts.mkdir()
            shutil.copyfile(source, scripts / source.name)
            report = root / "failure.json"
            environment = {
                key: value
                for key, value in os.environ.items()
                if key.upper()
                in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE"}
            }
            environment.update(
                DATABASE_URL="postgresql://synthetic@127.0.0.1:1/basis_verify_unreachable",
                PYTHONDONTWRITEBYTECODE="1",
                GIT_CEILING_DIRECTORIES=str(root.parent),
            )
            if missing_git:
                environment["PATH"] = str(root / "no-tools")
            result = subprocess.run(
                [sys.executable, "-B", str(scripts / source.name), "--report", str(report)],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("Traceback", result.stdout + result.stderr)
            receipt = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(receipt["status"], "FAILED")
            self.assertEqual(receipt["checks"][0]["name"], "candidate_manifest")
            self.assertEqual(receipt["checks"][0]["status"], "FAILED")
            self.assertIsNone(receipt["candidate"])
            self.assertFalse(receipt["candidate_unchanged"])
