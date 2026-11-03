"""Exclusive MAM-636 CLI runner: python -m basis.bootstrap.tests.mam636_runner manage test ...

Adapted from wave4-818/run_guarded.py. Guards Python entry points, not an OS firewall.
Never reads .env or a password file. Creates only the named own database on request.
"""

from __future__ import annotations

import os
import runpy
import socket
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

import httpx
import psycopg
from psycopg import sql
from psycopg.abc import AdaptContext
from psycopg.rows import RowFactory

ROOT = Path(__file__).resolve().parents[3]
DATABASE = "basis_wave4_636_fix6"
TEST_DATABASE = "test_" + DATABASE
CONNECT = {"host": "127.0.0.1", "port": "55482", "user": "basis_wave0", "password": ""}
original_connect = socket.socket.connect
original_connect_ex = socket.socket.connect_ex
original_pg = psycopg.connect


def forbidden_http(*args: object, **kwargs: object) -> httpx.Response:
    raise AssertionError("Real HTTP forbidden: MAM636 SIMULATED only")


def guarded_connect(sock: socket.socket, address: object) -> None:
    if not isinstance(address, tuple) or address[:2] != ("127.0.0.1", 55482):
        raise AssertionError("Socket forbidden: only exclusive PostgreSQL endpoint permitted")
    original_connect(sock, address)


def guarded_connect_ex(sock: socket.socket, address: object) -> int:
    if not isinstance(address, tuple) or address[:2] != ("127.0.0.1", 55482):
        raise AssertionError("Socket forbidden: only exclusive PostgreSQL endpoint permitted")
    return original_connect_ex(sock, address)


def guarded_pg(
    conninfo: str = "",
    *,
    autocommit: bool = False,
    prepare_threshold: int | None = 5,
    context: AdaptContext | None = None,
    row_factory: RowFactory[tuple[object, ...]] | None = None,
    cursor_factory: type[psycopg.Cursor[tuple[object, ...]]] | None = None,
    **kwargs: str | int | None,
) -> psycopg.Connection[tuple[object, ...]]:
    params = psycopg.conninfo.conninfo_to_dict(conninfo, **kwargs)
    if (
        params.get("dbname") not in (DATABASE, TEST_DATABASE)
        or params.get("host") != CONNECT["host"]
        or str(params.get("port")) != CONNECT["port"]
        or params.get("user") != CONNECT["user"]
    ):
        raise AssertionError("Non-MAM636 database connection forbidden")
    return original_pg(
        conninfo,
        autocommit=autocommit,
        prepare_threshold=prepare_threshold,
        context=context,
        row_factory=row_factory,
        cursor_factory=cursor_factory,
        **kwargs,
    )


def create_database() -> None:
    try:
        with original_pg(psycopg.conninfo.make_conninfo(dbname=DATABASE, **CONNECT)):
            print("Own database already exists")
    except psycopg.OperationalError as error:
        if "does not exist" not in str(error) and "no existe" not in str(error):
            raise
        # Maintenance connection exclusively for CREATE; no queries of other databases.
        with original_pg(
            psycopg.conninfo.make_conninfo(dbname="postgres", **CONNECT), autocommit=True
        ) as conn:
            conn.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(DATABASE), sql.Identifier(CONNECT["user"])
                )
            )
        print("Created only " + DATABASE)


def verify_guards() -> None:
    def denied(action: object) -> None:
        if not callable(action):
            raise TypeError("Expected callable")
        try:
            action()
        except AssertionError:
            return
        raise AssertionError("Guard did not reject forbidden action")

    with httpx.Client() as client:
        denied(lambda: client.get("https://outside.invalid"))

    # Test the patched async transport entry directly. A Windows event loop creates
    # a loopback self-pipe, which this PostgreSQL-only socket guard correctly rejects.
    denied(
        lambda: httpx.AsyncHTTPTransport().handle_async_request(
            httpx.Request("GET", "https://outside.invalid")
        )
    )
    with socket.socket() as sock:
        denied(lambda: sock.connect(("192.0.2.1", 443)))
        denied(lambda: sock.connect_ex(("192.0.2.1", 443)))
    denied(lambda: psycopg.connect(psycopg.conninfo.make_conninfo(dbname="not_owned", **CONNECT)))
    with psycopg.connect(psycopg.conninfo.make_conninfo(dbname=DATABASE, **CONNECT)) as conn:
        row = conn.execute(
            "SELECT current_database(), current_setting('server_version')"
        ).fetchone()
        assert row is not None and row[0] == DATABASE and str(row[1]).startswith("18.4")
        print(
            "VERIFIED guards sync/async HTTP, connect/connect_ex, exclusive DB; PostgreSQL "
            + str(row[1])
        )


def main() -> None:
    sys.dont_write_bytecode = True
    os.environ.update(
        DJANGO_SETTINGS_MODULE="config.test_settings",
        DJANGO_SECRET_KEY="synthetic-mam636-test-only",
        AI_ENABLED="0",
        DEEPSEEK_API_KEY="",
        POLAR_ACCESS_TOKEN="",
        POLAR_WEBHOOK_SECRET="",
        DATABASE_URL=f"postgresql://basis_wave0@127.0.0.1:55482/{DATABASE}",
        PGPASSWORD="",
        PGPASSFILE=str(ROOT / ".cache/mam636-no-password-file"),
    )
    from django.conf import settings
    from django.db.backends.postgresql.base import DatabaseWrapper

    settings.DATABASES["default"].setdefault("TEST", {})["NAME"] = TEST_DATABASE

    @contextmanager
    def own_nodb_cursor(wrapper: DatabaseWrapper) -> Iterator[object]:
        conn = wrapper.__class__({**wrapper.settings_dict, "NAME": DATABASE}, alias=wrapper.alias)
        try:
            with conn.cursor() as cursor:
                yield cursor
        finally:
            conn.close()

    mode = sys.argv.pop(1)
    with (
        patch.object(httpx.HTTPTransport, "handle_request", forbidden_http),
        patch.object(httpx.AsyncHTTPTransport, "handle_async_request", forbidden_http),
        patch.object(socket.socket, "connect", guarded_connect),
        patch.object(socket.socket, "connect_ex", guarded_connect_ex),
        patch.object(DatabaseWrapper, "_nodb_cursor", own_nodb_cursor),
        patch.object(psycopg, "connect", guarded_pg),
    ):
        if mode == "create-db":
            create_database()
        elif mode == "verify-guards":
            verify_guards()
        elif mode == "manage":
            runpy.run_path(str(ROOT / "manage.py"), run_name="__main__")
        else:
            runpy.run_module(mode, run_name="__main__")


if __name__ == "__main__":
    main()
