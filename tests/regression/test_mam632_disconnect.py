"""A real loopback TCP reset while a PostgreSQL sync transaction is open."""

import http.client
import json
import socket
import struct
from threading import Event, get_ident
from types import TracebackType
from typing import cast
from unittest.mock import patch
from urllib.parse import urlsplit
from uuid import uuid4

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.servers.basehttp import WSGIRequestHandler
from django.db import connection
from django.test import override_settings, skipUnlessDBFeature

from basis.adapters.django.transactions import DjangoUnitOfWork
from basis.modules.athletes.adapters.models import User as Athlete
from basis.modules.sync.adapters.models import SyncReceipt
from basis.modules.sync.adapters.receipts import DjangoReceiptRepository
from basis.modules.sync.domain.operations import Receipt
from basis.modules.training.adapters.actions import session_snapshot
from basis.modules.training.adapters.models import Session

from .factories import account, session


@skipUnlessDBFeature("has_select_for_update")
@override_settings(DEVELOPMENT_ACCESS=True)
class OfflineTransactionDisconnectTests(StaticLiveServerTestCase):
    host = "127.0.0.1"

    def test_tcp_reset_after_write_before_commit_and_idempotent_retry(self) -> None:
        self.assertEqual(connection.vendor, "postgresql")
        user = account("mam632-tcp-reset")
        item = session(user)
        original_revision = item.revision
        snapshot = session_snapshot(item)
        snapshot["duration_seconds"] = 765
        mutation = str(uuid4())
        body = json.dumps(
            {
                "account": str(Athlete.objects.get(account=user).public_id),
                "mutation_id": mutation,
                "created": 1792377600000,
                "session": snapshot,
            }
        ).encode("utf-8")
        self.client.force_login(user)
        session_cookie = self.client.cookies["sessionid"].value
        csrf = "a" * 32
        cookie = f"sessionid={session_cookie}; csrftoken={csrf}"
        headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
            "Cookie": cookie,
            "X-CSRFToken": csrf,
            "Connection": "close",
        }
        url = urlsplit(self.live_server_url)
        assert url.port is not None
        written = Event()
        release = Event()
        committed = Event()
        order: list[str] = []
        server_threads: list[int] = []
        written_state: list[tuple[bool, bool, int | None]] = []
        server_sockets: list[socket.socket] = []
        save = DjangoReceiptRepository.save
        exit_uow = DjangoUnitOfWork.__exit__
        get_environ = WSGIRequestHandler.get_environ

        def capture_socket(handler: WSGIRequestHandler) -> dict[str, str]:
            server_sockets.append(cast(socket.socket, handler.connection))
            return get_environ(handler)

        def held_save(repository: DjangoReceiptRepository, receipt: Receipt) -> None:
            save(repository, receipt)
            server_threads.append(get_ident())
            written_state.append(
                (
                    connection.in_atomic_block,
                    SyncReceipt.objects.filter(mutation_id=mutation).exists(),
                    Session.objects.get(pk=item.pk).duration_seconds,
                )
            )
            order.append("receipt-written")
            written.set()
            if not release.wait(timeout=15):
                raise TimeoutError("test did not release the open transaction")
            order.append("transaction-released")

        def observed_exit(
            uow: DjangoUnitOfWork,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: TracebackType | None,
        ) -> None:
            exit_uow(uow, exc_type, exc_value, traceback)
            if server_threads and get_ident() == server_threads[0]:
                order.append(
                    "transaction-committed"
                    if uow.committed and exc_type is None
                    else "transaction-rolled-back"
                )
                committed.set()

        with (
            patch.object(DjangoReceiptRepository, "save", held_save),
            patch.object(DjangoUnitOfWork, "__exit__", observed_exit),
            patch.object(WSGIRequestHandler, "get_environ", capture_socket),
        ):
            sock = socket.create_connection(("127.0.0.1", url.port), timeout=10)
            try:
                request = f"POST /api/sync/ HTTP/1.1\r\nHost: 127.0.0.1:{url.port}\r\n"
                request += "".join(f"{key}: {value}\r\n" for key, value in headers.items())
                sock.sendall(request.encode("ascii") + b"\r\n" + body)
                self.assertTrue(written.wait(timeout=15), "server did not reach receipt barrier")
                self.assertEqual(written_state, [(True, True, 765)])
                self.assertEqual(Session.objects.get(pk=item.pk).revision, original_revision)
                self.assertEqual(
                    Session.objects.get(pk=item.pk).duration_seconds, item.duration_seconds
                )
                self.assertFalse(SyncReceipt.objects.filter(mutation_id=mutation).exists())
                order.append("external-read-before-commit")
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("hh", 1, 0))
                sock.close()
                order.append("client-reset")
                self.assertEqual(len(server_sockets), 1)
                server_sockets[0].settimeout(10)
                with self.assertRaises(ConnectionResetError):
                    server_sockets[0].recv(1, socket.MSG_PEEK)
                order.append("server-observed-reset")
            finally:
                sock.close()
                release.set()
            self.assertTrue(committed.wait(timeout=15), "server did not exit transaction")

        self.assertEqual(
            order,
            [
                "receipt-written",
                "external-read-before-commit",
                "client-reset",
                "server-observed-reset",
                "transaction-released",
                "transaction-committed",
            ],
        )
        item.refresh_from_db()
        self.assertEqual(item.duration_seconds, 765)
        self.assertEqual(item.revision, original_revision + 1)
        self.assertEqual(SyncReceipt.objects.filter(mutation_id=mutation).count(), 1)
        retry = http.client.HTTPConnection("127.0.0.1", url.port, timeout=10)
        try:
            retry.request("POST", "/api/sync/", body=body, headers=headers)
            response = retry.getresponse()
            result = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(result["session"]["duration_seconds"], 765)
            self.assertEqual(result["session"]["revision"], original_revision + 1)
            self.assertEqual(
                result["session"], SyncReceipt.objects.get(mutation_id=mutation).result
            )
        finally:
            retry.close()
        item.refresh_from_db()
        self.assertEqual(item.revision, original_revision + 1)
        self.assertEqual(SyncReceipt.objects.filter(mutation_id=mutation).count(), 1)
