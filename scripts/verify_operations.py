"""Exercise production settings on an explicitly supplied EMPTY basis_verify_* PostgreSQL DB.

Creates synthetic data only in that disposable DB. Never uses seed_demo or user DBs.
Requires matching PostgreSQL client binaries on PATH. Reports no row values or secrets.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import timedelta
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

ROOT = Path(__file__).resolve().parents[1]


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def candidate_manifest() -> dict[str, object]:
    paths = (
        subprocess.check_output(
            ["git", "ls-files", "-co", "--exclude-standard", "-z"],
            cwd=ROOT,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        .decode()
        .split("\0")
    )
    files = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in sorted(set(filter(None, paths)))
        if (ROOT / name).is_file()
    }
    return {
        "base_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.PIPE,
            timeout=30,
        ).strip(),
        "files": files,
        "sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
    }


def run(command: list[str], environment: dict[str, str]) -> None:
    subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, check=True, timeout=300)


def snapshot(database_url: str) -> dict[str, object]:
    import psycopg
    from psycopg import sql

    result: dict[str, object] = {}
    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        )
        tables = [row[0] for row in cursor.fetchall()]
        for table in tables:
            cursor.execute(
                sql.SQL(
                    "SELECT row_to_json(t)::text FROM {} t ORDER BY row_to_json(t)::text"
                ).format(sql.Identifier(table))
            )
            rows = [row[0] for row in cursor.fetchall()]
            result[table] = {
                "rows": len(rows),
                "sha256": hashlib.sha256(json.dumps(rows).encode()).hexdigest(),
            }
        # Sequences are part of recovery: equal rows alone don't prove safe future inserts.
        cursor.execute(
            "SELECT sequencename, last_value FROM pg_sequences "
            "WHERE schemaname='public' ORDER BY sequencename"
        )
        result["sequences"] = cursor.fetchall()
    return result


def fixture() -> tuple[list[str], str, dict[str, int]]:
    from django.contrib.auth import get_user_model
    from django.test import Client
    from django.utils import timezone

    from basis.modules.athletes.adapters.models import User as Athlete
    from basis.modules.athletes.adapters.models import UserExerciseRM, WorkoutData
    from basis.modules.billing.adapters.models import BillingAccount
    from basis.modules.catalog.adapters.models import Classification, Exercise
    from basis.modules.training.adapters.models import (
        Block,
        Cycle,
        Goal,
        PlannedSession,
        Session,
        StrengthSet,
        TrainingPlan,
    )

    today = timezone.localdate()
    classification = Classification.objects.create(nombre="Operations Synthetic")
    exercise = Exercise.objects.create(nombre="Operations Squat", classification=classification)
    paths = ["/health/", "/accounts/login/", "/", "/plans/", "/progress/"]
    owners = []
    # Ten accounts, two plan versions, scheduled and completed sessions with measured RM links.
    for index in range(10):
        owner = get_user_model().objects.create_user(
            username=f"operations-{index}@example.test", password=None
        )
        owners.append(owner)
        profile = Athlete.objects.create(
            account=owner,
            nombre=f"Synthetic {index}",
            email=f"operations-{index}@example.test",
            fecha_inicio=today,
            email_verified=True,
        )
        BillingAccount.objects.create(
            owner=owner,
            status="active",
            period_start=timezone.now() - timedelta(days=1),
            period_end=timezone.now() + timedelta(days=30),
        )
        reference = UserExerciseRM.objects.create(
            user=profile, exercise=exercise, peso_maximo_rm=100, fecha_registro=today
        )
        WorkoutData.objects.create(
            user=profile, exercise=exercise, fecha=today, sets=3, reps=5, peso=50
        )
        goal = Goal.objects.create(owner=owner, title="Synthetic strength", sport="strength")
        previous = TrainingPlan.objects.create(
            owner=owner, goal=goal, title="Synthetic v1", start_date=today, end_date=today
        )
        plan = TrainingPlan.objects.create(
            owner=owner,
            goal=goal,
            title="Synthetic v2",
            lineage=previous.lineage,
            version=2,
            previous=previous,
            start_date=today,
            end_date=today,
        )
        parent = None
        for kind in ("macro", "meso", "micro"):
            parent = Cycle.objects.create(
                plan=plan, parent=parent, kind=kind, title=kind, start_date=today, end_date=today
            )
        if parent is None:
            raise RuntimeError("Synthetic cycle missing")
        for number in range(12):
            planned = PlannedSession.objects.create(
                owner=owner, plan=plan, cycle=parent, title=f"Synthetic {number}", date=today
            )
            session = Session.objects.create(
                owner=owner, planned=planned, title="Synthetic completed", status="completed"
            )
            block = Block.objects.create(session=session, sport="strength", title="Synthetic")
            for order in range(1, 4):
                StrengthSet.objects.create(
                    block=block,
                    exercise=exercise,
                    rm_reference=reference,
                    order=order,
                    actual_kg=50,
                    actual_reps=5,
                )
            if index == 0 and number == 0:
                paths.extend([f"/plans/{plan.pk}/", f"/sessions/{session.pk}/", "/export/"])
    client = Client()
    client.force_login(owners[0])
    from django.conf import settings

    cookie = f"{settings.SESSION_COOKIE_NAME}={client.cookies[settings.SESSION_COOKIE_NAME].value}"
    return (
        paths,
        cookie,
        {
            "profiles": Athlete.objects.count(),
            "plans": TrainingPlan.objects.count(),
            "sessions": Session.objects.count(),
            "strength_sets": StrengthSet.objects.count(),
            "measured_rm": UserExerciseRM.objects.count(),
        },
    )


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


class ReferenceServer(ThreadingMixIn, WSGIServer):
    daemon_threads = False

    def process_request_thread(
        self, request: socket.socket | tuple[bytes, socket.socket], client_address: tuple[str, int]
    ) -> None:
        from django.db import connections

        try:
            super().process_request_thread(request, client_address)
        finally:
            # A short-lived reference HTTP thread must release its persistent PG connection.
            connections.close_all()


def load(paths: list[str], cookie: str, requests: int, concurrency: int) -> dict[str, object]:
    from django.core.wsgi import get_wsgi_application

    with make_server(
        "127.0.0.1",
        0,
        get_wsgi_application(),
        server_class=ReferenceServer,
        handler_class=QuietHandler,
    ) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def request(index: int) -> tuple[int, float]:
            path = paths[index % len(paths)]
            started = time.perf_counter()
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            req = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}{path}",
                headers={
                    "Host": "reference.example.test",
                    "X-Forwarded-Proto": "https",
                    "Cookie": cookie,
                },
            )
            with opener.open(req, timeout=30) as response:
                response.read()
                if response.url != req.full_url:
                    raise RuntimeError("Unexpected redirect in representative workload")
                return response.status, (time.perf_counter() - started) * 1000

        started = time.perf_counter()
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
                responses = list(pool.map(request, range(requests)))
        finally:
            server.shutdown()
            thread.join(timeout=10)
        elapsed = time.perf_counter() - started
    latencies = sorted(value for _, value in responses)
    ensure(all(code == 200 for code, _ in responses), "HTTP workload failure")
    return {
        "server": "stdlib threaded WSGI reference, not a production capacity benchmark",
        "requests": requests,
        "concurrency": concurrency,
        "routes": len(paths),
        "http_200": len(responses),
        "seconds": round(elapsed, 3),
        "requests_per_second": round(requests / elapsed, 2),
        "p50_ms": round(latencies[math.ceil(len(latencies) * 0.50) - 1], 2),
        "p95_ms": round(latencies[math.ceil(len(latencies) * 0.95) - 1], 2),
        "max_ms": round(max(latencies), 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--requests", type=int, default=160)
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    if not 16 <= args.requests <= 10000 or not 1 <= args.concurrency <= 32:
        parser.error("Use 16..10000 requests and 1..32 concurrent clients.")
    if not args.report.parent.is_dir() or args.report.exists():
        parser.error("Report requires an existing parent and a new filename.")
    url = os.environ.get("DATABASE_URL", "")
    parsed = urlsplit(url)
    name = parsed.path.removeprefix("/")
    if parsed.scheme not in ("postgres", "postgresql") or not name.startswith("basis_verify_"):
        parser.error("Supply an EMPTY disposable basis_verify_* database via DATABASE_URL.")
    # Don't inherit provider credentials, development bypasses, settings overrides or DEBUG.
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper()
        in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE", "LANG"}
    }
    environment.update(
        DATABASE_URL=url,
        DJANGO_SETTINGS_MODULE="config.settings",
        DJANGO_DEBUG="0",
        DJANGO_SECRET_KEY=secrets.token_urlsafe(64),
        DJANGO_ALLOWED_HOSTS="reference.example.test",
        DJANGO_HEALTH_HOST="reference.example.test",
        PUBLIC_URL="https://reference.example.test",
        CSRF_TRUSTED_ORIGINS="https://reference.example.test",
        TRUST_PROXY="1",
        AI_ENABLED="0",
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        PYTHONDONTWRITEBYTECODE="1",
    )
    report: dict[str, object] = {
        "status": "FAILED",
        "candidate": None,
        "checks": [],
        "production_deployment": "NOT RUN",
    }
    checks: list[dict[str, object]] = []
    report["checks"] = checks
    restore_name = "basis_restore_" + uuid4().hex
    restore_url = urlunsplit(parsed._replace(path="/" + restore_name))
    backup = args.report.with_suffix(".dump")
    stage = "candidate_manifest"
    restore_started = False
    try:
        report["candidate"] = candidate_manifest()
        checks.append({"name": stage, "status": "VERIFIED"})
        stage = "empty_database_guard"
        import django
        import psycopg
        from psycopg import sql

        ensure(snapshot(url) == {"sequences": []}, "Disposable DB must be empty")
        checks.append({"name": stage, "status": "VERIFIED"})
        os.environ.clear()
        os.environ.update(environment)
        sys.path.insert(0, str(ROOT))
        django.setup()
        report["versions"] = {
            "python": sys.version.split()[0],
            "django": django.get_version(),
            "postgresql_client": subprocess.check_output(
                ["pg_dump", "--version"], text=True
            ).strip(),
        }
        with psycopg.connect(url) as connection:
            row = connection.execute("SHOW server_version").fetchone()
            if row is not None:
                report["postgresql_server"] = row[0]
        commands = [
            ("deploy", ["check", "--deploy", "--fail-level", "WARNING"]),
            ("migrate", ["migrate", "--noinput"]),
            ("migration_drift", ["makemigrations", "--check", "--dry-run"]),
            ("static", ["collectstatic", "--noinput"]),
        ]
        for stage, command in commands:
            run([sys.executable, "-B", "manage.py", *command], environment)
            checks.append({"name": stage, "status": "VERIFIED"})
        stage = "synthetic_fixture"
        paths, cookie, counts = fixture()
        report["fixture"] = counts
        checks.append({"name": stage, "status": "VERIFIED"})
        stage = "backup_restore"
        before = snapshot(url)
        started = time.perf_counter()
        run([sys.executable, "-B", "scripts/backup_db.py", "backup", str(backup)], environment)
        report["backup_seconds"] = round(time.perf_counter() - started, 3)
        started = time.perf_counter()
        with psycopg.connect(url) as connection:
            ensure(
                not connection.execute(
                    "SELECT 1 FROM pg_database WHERE datname=%s", (restore_name,)
                ).fetchone(),
                "Generated restore name already exists",
            )
        restore_started = True
        run(
            [
                sys.executable,
                "-B",
                "scripts/backup_db.py",
                "restore-test",
                str(backup),
                "--database",
                restore_name,
            ],
            environment,
        )
        report["restore_seconds"] = round(time.perf_counter() - started, 3)
        ensure(before == snapshot(restore_url), "Restored rows/references/sequences differ")
        checks.append({"name": stage, "status": "VERIFIED"})
        stage = "repeat_migrate_preserves_data"
        restored_environment = {**environment, "DATABASE_URL": restore_url}
        run([sys.executable, "-B", "manage.py", "migrate", "--noinput"], restored_environment)
        ensure(before == snapshot(restore_url), "Migrate changed restored data")
        checks.append({"name": stage, "status": "VERIFIED"})
        stage = "rollback_rehearsal"
        from django.conf import settings
        from django.db import connections

        from basis.modules.training.adapters.models import StrengthSet

        StrengthSet.objects.all().update(actual_kg=55)
        ensure(snapshot(url) != before, "Synthetic failure injection did not change data")
        connections.close_all()
        settings.DATABASES["default"]["NAME"] = restore_name
        connections["default"].settings_dict["NAME"] = restore_name
        ensure(snapshot(restore_url) == before, "Recovery point changed")
        checks.append({"name": stage, "status": "VERIFIED", "scope": "database switchover"})
        stage = "representative_http_load_after_recovery"
        report["load"] = load(paths, cookie, args.requests, args.concurrency)
        # GETs may refresh sessions but cannot mutate historical records.
        after = snapshot(restore_url)
        ensure(
            all(value == after[key] for key, value in before.items() if key != "django_session"),
            "Read workload changed historical data",
        )
        report["snapshot"] = before
        checks.append({"name": stage, "status": "VERIFIED"})
        report["status"] = "VERIFIED"
    except Exception as exc:
        checks.append({"name": stage, "status": "FAILED", "error_type": type(exc).__name__})
    finally:
        # The caller owns source DB/cluster. Only our newly generated restore DB is removed.
        try:
            if restore_started:
                from django.db import connections

                connections.close_all()
                with psycopg.connect(url, autocommit=True) as connection:
                    connection.execute(
                        sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(restore_name))
                    )
            report["restore_cleanup"] = "VERIFIED"
        except Exception as exc:
            report["restore_cleanup"] = type(exc).__name__
            report["status"] = "FAILED"
        try:
            report["candidate_unchanged"] = (
                report["candidate"] is not None and candidate_manifest() == report["candidate"]
            )
        except Exception as exc:
            report["candidate_unchanged"] = False
            checks.append(
                {
                    "name": "final_candidate_manifest",
                    "status": "FAILED",
                    "error_type": type(exc).__name__,
                }
            )
        if not report["candidate_unchanged"]:
            report["status"] = "FAILED"
        with args.report.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, default=str)
    print(json.dumps({"status": report["status"], "stage": stage, "report": str(args.report)}))
    return 0 if report["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    sys.exit(main())
