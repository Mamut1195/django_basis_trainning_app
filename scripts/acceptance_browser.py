"""Launch real browser acceptance against a fresh owned loopback SQLite database."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import TextIO
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent


def find_browser(explicit: str | None) -> str | None:
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise ValueError("The explicit browser executable does not exist")
        return str(path.resolve())
    for base in (os.getenv("PROGRAMFILES(X86)"), os.getenv("PROGRAMFILES")):
        if base:
            candidate = Path(base) / "Microsoft/Edge/Application/msedge.exe"
            if candidate.is_file():
                return str(candidate)
    return None


def choose_port(requested: int) -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", requested))
        return int(probe.getsockname()[1])


def child_environment(database: Path, password: str, secret: str) -> dict[str, str]:
    allowed = {
        "SYSTEMROOT",
        "WINDIR",
        "SYSTEMDRIVE",
        "COMSPEC",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "LOCALAPPDATA",
        "APPDATA",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "PATH",
        "PATHEXT",
        "PROCESSOR_ARCHITECTURE",
    }
    result = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    result.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.test_settings",
            "DJANGO_DEBUG": "1",
            "DJANGO_SECRET_KEY": secret,
            "DATABASE_URL": "sqlite:///" + database.as_posix(),
            "BASIS_ACCEPTANCE_DATABASE": str(database),
            "BASIS_E2E_PASSWORD": password,
            "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
            "AI_ENABLED": "0",
            "DEEPSEEK_API_KEY": "",
            "POLAR_ACCESS_TOKEN": "",
            "POLAR_PRODUCT_ID": "",
            "POLAR_WEBHOOK_SECRET": "",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUNBUFFERED": "1",
        }
    )
    return result


def execute(command: list[str], environment: dict[str, str], log: Path, timeout: int = 90) -> None:
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            stdout=stream,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    if result.returncode:
        raise RuntimeError("Acceptance subprocess failed; inspect " + log.name)


def ready(server: subprocess.Popen[str], origin: str) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError("Owned Django server exited before readiness")
        try:
            with urlopen(origin + "/health/", timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, OSError):
            pass
        time.sleep(0.1)
    raise RuntimeError("Owned Django server did not become ready")


def run(output: Path, executable: str | None, requested_port: int) -> int:
    output = output.resolve()
    cache_root = ROOT / ".cache"
    if cache_root.is_symlink() or cache_root.resolve() != cache_root:
        raise ValueError("Acceptance cache must not redirect outside the repository")
    cache = cache_root.resolve()
    if not output.is_relative_to(cache):
        raise ValueError("Acceptance artifacts must stay under the repository .cache directory")
    output.mkdir(parents=True, exist_ok=False)
    database = output / "browser.sqlite3"
    password, secret = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    environment = child_environment(database, password, secret)
    server: subprocess.Popen[str] | None = None
    server_log: TextIO | None = None
    result: dict[str, object] = {
        "status": "FAILED",
        "database": str(database),
        "server_stopped": False,
        "provider_calls": "DISABLED",
        "smtp": "DISABLED",
    }
    try:
        browser = find_browser(executable)
        port = choose_port(requested_port)
        origin = "http://127.0.0.1:" + str(port)
        result["origin"] = origin
        execute(
            [
                sys.executable,
                "manage.py",
                "migrate",
                "--noinput",
                "--verbosity",
                "0",
                "--settings=config.test_settings",
            ],
            environment,
            output / "migrate.log",
        )
        execute(
            [
                sys.executable,
                "-c",
                "import django; django.setup(); from basis.bootstrap.acceptance_fixture import prepare; prepare()",
            ],
            environment,
            output / "fixture.log",
        )
        server_log = (output / "server.log").open("w", encoding="utf-8")
        server = subprocess.Popen(
            [
                sys.executable,
                "manage.py",
                "runserver",
                "127.0.0.1:" + str(port),
                "--noreload",
                "--settings=config.test_settings",
            ],
            cwd=ROOT,
            env=environment,
            stdout=server_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        result["server_pid"] = server.pid
        ready(server, origin)
        command = [
            sys.executable,
            "-m",
            "scripts.browser_smoke",
            "--origin",
            origin,
            "--output",
            str(output),
        ]
        if browser:
            command.extend(("--browser-executable", browser))
        execute(command, environment, output / "browser.log", timeout=150)
        browser_result: object = json.loads(
            (output / "browser-result.json").read_text(encoding="utf-8")
        )
        if not isinstance(browser_result, dict) or browser_result.get("status") != "VERIFIED":
            raise RuntimeError("Real browser did not produce VERIFIED evidence")
        closed: object = json.loads((output / "browser-closed.json").read_text(encoding="utf-8"))
        if not isinstance(closed, dict) or closed.get("browser_closed") is not True:
            raise RuntimeError("Browser cleanup was not confirmed")
        result["browser"] = browser_result
        result["browser_closed"] = True
        result["status"] = "VERIFIED"
    except Exception as error:
        result["error"] = str(error).replace(password, "[REDACTED]").replace(secret, "[REDACTED]")
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
        if server_log is not None:
            server_log.close()
        result["server_stopped"] = server is None or server.poll() is not None
        for log in output.glob("*.log"):
            text = log.read_text(encoding="utf-8", errors="replace")
            log.write_text(
                text.replace(password, "[REDACTED]").replace(secret, "[REDACTED]"), encoding="utf-8"
            )
        (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result["status"],
                "receipt": str(output / "result.json"),
                "server_stopped": result["server_stopped"],
            }
        )
    )
    return 0 if result["status"] == "VERIFIED" and result["server_stopped"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".cache" / "browser-acceptance" / uuid4().hex
    )
    parser.add_argument("--browser-executable")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    return run(Path(args.output), args.browser_executable, int(args.port))


if __name__ == "__main__":
    raise SystemExit(main())
