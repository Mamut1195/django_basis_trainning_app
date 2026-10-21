"""Linux regression: real Gunicorn parser, application exception and worker timeout.

All requests use synthetic sentinels over a private inherited loopback socket.
Only safe event counts/statuses leave this process; temporary raw logs are deleted.
"""

from __future__ import annotations

import collections
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FIXTURE = """import time
def application(environ, start_response):
    path = environ["PATH_INFO"]
    if path.startswith("/raise"):
        raise RuntimeError("EXCEPTION_SENTINEL_PRIVATE " + environ["QUERY_STRING"])
    if path.startswith("/timeout"):
        time.sleep(30)
    start_response("200 OK", [("Content-Type", "text/plain"), ("Content-Length", "2")])
    return [b"ok"]
"""


def exchange(port: int, request: bytes) -> int:
    with socket.create_connection(("127.0.0.1", port), timeout=10) as connection:
        connection.settimeout(10)
        connection.sendall(request)
        response = bytearray()
        while chunk := connection.recv(65536):
            response.extend(chunk)
    return int(response.split(b" ", 2)[1])


def main() -> int:
    result: dict[str, object] = {"status": "FAILED", "stage": "start"}
    try:
        if os.name != "posix":
            raise RuntimeError("Linux Gunicorn execution required")
        with tempfile.TemporaryDirectory(prefix="basis-gunicorn-regression-") as directory:
            root = Path(directory)
            (root / "logging_fixture.py").write_text(FIXTURE, encoding="utf-8")
            with socket.socket() as listener, (root / "private.log").open("wb") as output:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
                environment = {**os.environ, "PYTHONPATH": str(root) + os.pathsep + str(ROOT)}
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-B",
                        "-m",
                        "gunicorn",
                        "logging_fixture:application",
                        "--config",
                        str(ROOT / "deploy/gunicorn_config.py"),
                        "--bind",
                        f"fd://{listener.fileno()}",
                        "--workers",
                        "1",
                        "--timeout",
                        "2",
                        "--access-logfile",
                        "-",
                        "--access-logformat",
                        "%(m)s %(s)s %(L)s %(b)s",
                        "--error-logfile",
                        "-",
                    ],
                    cwd=ROOT,
                    env=environment,
                    pass_fds=(listener.fileno(),),
                    stdout=output,
                    stderr=subprocess.STDOUT,
                )
                try:
                    result["uid"] = int(subprocess.check_output(["id", "-u"], text=True).strip())
                    result["stage"] = "normal_request"
                    for _ in range(100):
                        if process.poll() is not None:
                            raise RuntimeError("Gunicorn startup failed")
                        try:
                            status = exchange(
                                port,
                                b"GET /?token=QUERY_SENTINEL_PRIVATE HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n",
                            )
                            break
                        except OSError:
                            time.sleep(0.1)
                    else:
                        raise RuntimeError("Gunicorn not ready")
                    if status != 200:
                        raise RuntimeError("Normal request failed")
                    result["stage"] = "malformed_parser"
                    malformed = exchange(
                        port,
                        b"GET /accounts/reset/PATH_SENTINEL_PRIVATE/?token=QUERY_SENTINEL_PRIVATE\r\n\r\n",
                    )
                    result["stage"] = "application_exception"
                    exception = exchange(
                        port,
                        b"GET /raise/PATH_SENTINEL_PRIVATE/?token=QUERY_SENTINEL_PRIVATE HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n",
                    )
                    result["stage"] = "worker_timeout"
                    timeout = exchange(
                        port,
                        b"GET /timeout/PATH_SENTINEL_PRIVATE/?token=QUERY_SENTINEL_PRIVATE HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n",
                    )
                    result["http"] = {
                        "normal": status,
                        "malformed": malformed,
                        "exception": exception,
                        "timeout": timeout,
                    }
                    if (malformed, exception, timeout) != (400, 500, 500):
                        raise RuntimeError("Unexpected negative response statuses")
                    time.sleep(0.2)
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
            logs = (root / "private.log").read_text(encoding="utf-8")
            result["stage"] = "private_logging"
            if any(
                value in logs
                for value in ("SENTINEL_PRIVATE", "/accounts/reset/", "?token=", "Traceback")
            ):
                raise RuntimeError("Sensitive logging regression")
            events = collections.Counter(re.findall(r"gunicorn event=([a-z_]+)", logs))
            if not all(
                events[event] >= 1
                for event in (
                    "request_rejected",
                    "request_exception",
                    "worker_timeout",
                    "worker_boot",
                )
            ):
                raise RuntimeError("Safe event diagnostics missing")
            if (
                "status=400 exception=InvalidRequestLine" not in logs
                or "status=500 exception=RuntimeError" not in logs
            ):
                raise RuntimeError("Safe class/status diagnostics missing")
            result.update(
                status="VERIFIED", events=dict(events), sentinels_absent=True, cleanup="VERIFIED"
            )
    except Exception as exc:
        result["error_type"] = type(exc).__name__
    print(json.dumps(result))
    return 0 if result["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    sys.exit(main())
