"""Verify a disposable BASIS environment. The launcher uses only the standard library."""

import argparse
import contextlib
import hashlib
import importlib
import importlib.metadata
import io
import json
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = "basis_trainning_app.test_settings"
STAGES = ("dependencies", "isolation", "check", "migrate", "makemigrations", "runtime")


class VerificationError(Exception):
    """A verification invariant failed; never include environment values in its message."""


def safe_environment(database):
    """Allow only OS bootstrap variables; never forward application configuration."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in {"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE"}
    }
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": SETTINGS,
            "BASIS_DATABASE_PATH": str(database),
            # Base settings must import in development mode before our safe overrides.
            "DJANGO_DEBUG": "1",
            "DJANGO_SECRET_KEY": secrets.token_urlsafe(48),
            "DJANGO_ALLOWED_HOSTS": "testserver,localhost,127.0.0.1",
            "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
            "AI_ENABLED": "0",
            "BASIS_DEVELOPMENT_ACCESS": "0",
            "TRUST_PROXY": "0",
            "PUBLIC_URL": "http://testserver",
            "TEMP": str(database.parent),
            "TMP": str(database.parent),
            "TMPDIR": str(database.parent),
        }
    )
    return environment


def require_disposable(database):
    """Reject existing databases and paths outside our exclusive scratch directory."""
    cache = ROOT / ".cache"
    database = Path(database)
    if (
        cache.is_symlink()
        or cache.resolve() != ROOT / ".cache"
        or database != database.resolve()
        or database.parent.parent != cache
        or not database.parent.name.startswith("environment-")
        or not database.parent.is_dir()
        or database.name != "verification.sqlite3"
        or database.exists()
    ):
        raise VerificationError("unsafe_database_path")


def dependency_check(report):
    import django

    report["versions"] = {
        "python": ".".join(map(str, sys.version_info[:3])),
        "django": django.get_version(),
        "sqlite": sqlite3.sqlite_version,
    }
    requirements = (ROOT / "requirements.txt").read_bytes()
    report["requirements_sha256"] = hashlib.sha256(requirements).hexdigest()
    mismatches = []
    checked = 0
    for line in requirements.decode("utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if not re.fullmatch(r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.+!-]+", line):
            raise VerificationError("requirements_must_be_pinned")
        name, expected = line.split("==")
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            installed = None
        if installed != expected:
            mismatches.append({"package": name, "expected": expected, "installed": installed})
        checked += 1
    report["dependencies"] = {"checked": checked, "mismatches": mismatches}
    if sys.version_info[:2] != (3, 13) or django.VERSION[:2] != (5, 2) or mismatches:
        raise VerificationError("dependency_mismatch")


def configure_django(database):
    # Run before django.setup(), migrations, checks or any database access.
    require_disposable(database)
    if "DATABASE_URL" in os.environ or os.environ.get("BASIS_DATABASE_PATH") != str(database):
        raise VerificationError("unsafe_environment")
    sys.path.insert(0, str(ROOT))
    module = importlib.import_module(SETTINGS)
    configuration = {key: getattr(module, key) for key in dir(module) if key.isupper()}
    configuration.update(
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(database),
                "CONN_MAX_AGE": 0,
            }
        },
        DATABASE_ROUTERS=[],
        DEBUG=False,
        SECURE_SSL_REDIRECT=False,
        SESSION_COOKIE_SECURE=False,
        CSRF_COOKIE_SECURE=False,
        SECURE_PROXY_SSL_HEADER=None,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        AI_ENABLED=False,
        DEVELOPMENT_ACCESS=False,
        MEDIA_ROOT=str(database.parent / "media"),
        EMAIL_FILE_PATH=str(database.parent / "mail"),
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    )
    import django
    from django.conf import settings
    from django.db import connections

    settings.configure(**configuration)
    django.setup()
    connection = connections["default"]
    if (
        list(connections) != ["default"]
        or connection.vendor != "sqlite"
        or Path(connection.settings_dict["NAME"]) != database
    ):
        raise VerificationError("database_isolation_failed")


def runtime_check(report):
    from django.contrib.auth import SESSION_KEY, get_user_model
    from django.test import Client

    client = Client(enforce_csrf_checks=True)
    health = client.get("/health/")
    login = client.get("/accounts/login/")
    if health.status_code != 200 or health.json() != {"status": "ok"}:
        raise VerificationError("health_failed")
    if login.status_code != 200 or "csrftoken" not in client.cookies:
        raise VerificationError("login_page_failed")
    username = "environment-check@example.test"
    password = secrets.token_urlsafe(32)
    user = get_user_model().objects.create_user(username=username, password=password)
    response = client.post(
        "/accounts/login/",
        {"username": username, "password": password},
        HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
    )
    authenticated = client.session.get(SESSION_KEY) == str(user.pk)
    if response.status_code != 302 or not authenticated:
        raise VerificationError("login_authentication_failed")
    report["runtime"] = {
        "health_get": health.status_code,
        "login_get": login.status_code,
        "login_post": response.status_code,
        "authenticated_session": authenticated,
        "csrf_checks": True,
    }


def worker_main(database):
    """Internal subprocess entry: raw Django output never enters the JSON report."""
    report = {"status": "FAILED", "steps": [{"name": s, "status": "NOT RUN"} for s in STAGES]}
    database = Path(database)
    exit_code = 1
    # Suppress tracebacks, command output, warnings and logs which might contain data.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            for step in report["steps"]:
                start = time.monotonic()
                try:
                    name = step["name"]
                    if name == "dependencies":
                        dependency_check(report)
                    elif name == "isolation":
                        configure_django(database)
                    elif name == "runtime":
                        runtime_check(report)
                    else:
                        from django.core.management import call_command

                        if name == "check":
                            call_command("check", verbosity=0)
                        elif name == "migrate":
                            call_command("migrate", interactive=False, verbosity=0)
                        else:
                            call_command("makemigrations", check=True, dry_run=True, verbosity=0)
                    step["status"] = "VERIFIED"
                except (Exception, SystemExit) as error:
                    step.update(status="FAILED", error_type=type(error).__name__)
                    # Only our own fixed error identifiers are safe to expose.
                    if isinstance(error, VerificationError):
                        step["reason"] = str(error)
                    raise
                finally:
                    step["seconds"] = round(time.monotonic() - start, 3)
            report["status"] = "VERIFIED"
            exit_code = 0
        except (Exception, SystemExit):
            pass
        finally:
            try:
                from django.conf import settings
                from django.db import connections

                if settings.configured:
                    connections.close_all()
            except Exception:
                report["status"] = "FAILED"
                report["error"] = "connection_cleanup_failed"
                exit_code = 1
    print(json.dumps(report))
    raise SystemExit(exit_code)


def run_verification(python, timeout=180):
    """Own and clean only a directory allocated by TemporaryDirectory for this run."""
    report = {
        "schema_version": 1,
        "status": "FAILED",
        "settings_module": SETTINGS,
        "database_engine": "sqlite",
        "database_url_inherited": False,
        "cleanup": "NOT RUN",
        "steps": [],
    }
    exit_code = 2
    scratch = None
    try:
        cache = ROOT / ".cache"
        if cache.is_symlink() or cache.resolve() != ROOT / ".cache":
            raise VerificationError("unsafe_cache_path")
        cache.mkdir(exist_ok=True)
        scratch = tempfile.TemporaryDirectory(prefix="environment-", dir=cache)
        database = Path(scratch.name) / "verification.sqlite3"
        report["temporary_database"] = str(database.relative_to(ROOT))
        require_disposable(database)
        command = [
            str(Path(python).resolve()),
            "-I",
            "-B",
            "-c",
            "import runpy, sys; runpy.run_path(sys.argv[1])['worker_main'](sys.argv[2])",
            str(Path(__file__).resolve()),
            str(database),
        ]
        child = subprocess.run(
            command,
            cwd=ROOT,
            env=safe_environment(database),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
        )
        try:
            result = json.loads(child.stdout)
            if result["status"] not in {"VERIFIED", "FAILED"} or not isinstance(
                result["steps"], list
            ):
                raise ValueError
        except (ValueError, KeyError, TypeError):
            report["error"] = "invalid_worker_report"
        else:
            report.update(result)
            exit_code = 0 if child.returncode == 0 and result["status"] == "VERIFIED" else 1
            if exit_code:
                report["status"] = "FAILED"
    except subprocess.TimeoutExpired:
        report["error"] = "worker_timeout"
        exit_code = 3
    except (OSError, VerificationError) as error:
        report["error"] = str(error) if isinstance(error, VerificationError) else "launcher_failed"
        report["error_type"] = type(error).__name__
    finally:
        if scratch is not None:
            try:
                scratch.cleanup()
                report["cleanup"] = "VERIFIED"
            except OSError:
                report["cleanup"] = "FAILED"
                report["status"] = "FAILED"
                report["error"] = "temporary_cleanup_failed"
                exit_code = 2
    report["exit_code"] = exit_code
    return report, exit_code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python", required=True, type=Path, help="Path to the installed Python 3.13"
    )
    parser.add_argument("--report", type=Path, help="Optional NEW JSON file (never overwritten)")
    parser.add_argument("--timeout", type=int, default=180, help="Worker timeout in seconds")
    args = parser.parse_args(argv)
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    # Reserve an optional report before doing any work; existing files remain untouched.
    try:
        handle = args.report.open("x", encoding="utf-8") if args.report else None
    except OSError:
        print(json.dumps({"status": "FAILED", "error": "report_create_failed", "exit_code": 2}))
        return 2
    try:
        report, code = run_verification(args.python, args.timeout)
        payload = json.dumps(report, indent=2)
        if handle:
            handle.write(payload + "\n")
        print(payload)
        return code
    except OSError:
        print(json.dumps({"status": "FAILED", "error": "report_write_failed", "exit_code": 2}))
        return 2
    finally:
        if handle:
            handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
