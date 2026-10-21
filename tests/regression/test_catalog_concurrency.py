"""Serialize real database writers before revalidating catalog topology."""

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import OperationalError, close_old_connections, connection, connections, transaction
from django.test import TransactionTestCase, skipUnlessDBFeature
from rest_framework.test import APIClient

from basis.modules.catalog.adapters.models import Classification, Exercise

from .factories import account


@skipUnlessDBFeature("has_select_for_update")
class CatalogConcurrencyTests(TransactionTestCase):
    def setUp(self) -> None:
        self.staff = account("catalog-race-staff")
        self.staff.is_staff = self.staff.is_superuser = True
        self.staff.save(update_fields=["is_staff", "is_superuser"])
        category = Classification.objects.create(nombre="Concurrent catalog")
        self.rows = [
            Exercise.objects.create(nombre=f"Concurrent {index}", classification=category)
            for index in range(3)
        ]

    def writer(self, kind: str, row: Exercise, parent: Exercise) -> Callable[[], int]:
        client = APIClient()
        # Session creation happens before the coordinator holds the table lock,
        # so last_login updates cannot serialize the requests accidentally.
        client.force_login(self.staff)

        def write() -> int:
            if kind == "api":
                return client.patch(
                    f"/api/v1/exercises/{row.pk}/", {"variante_de": parent.pk}
                ).status_code
            if kind == "admin":
                response = client.post(
                    f"/admin/basis_catalog/exercise/{row.pk}/change/",
                    {
                        "nombre": row.nombre,
                        "classification": row.classification_id,
                        "nivel_fatiga": row.nivel_fatiga,
                        "musculos_principales": "[]",
                        "variante_de": parent.pk,
                        "_save": "Guardar",
                    },
                )
                return 200 if response.status_code == 302 else response.status_code
            row.variante_de_id = parent.pk
            try:
                row.save()
            except ValidationError:
                return 400
            return 200

        return write

    def contend(self, operations: list[Callable[[], int]]) -> list[int]:
        token = "catalog-race-" + uuid4().hex

        def worker(index: int) -> int:
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT set_config('application_name', %s, false)", [token])
                    cursor.execute("SET lock_timeout = '8s'")
                    cursor.execute("SET statement_timeout = '12s'")
                return operations[index]()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            with transaction.atomic():
                # Old code validates both candidates then waits on UPDATE;
                # corrected code waits *before* authoritative validation.
                # No barrier is ever awaited after a worker acquires its lock.
                table = connection.ops.quote_name(Exercise._meta.db_table)
                with connection.cursor() as cursor:
                    cursor.execute(f"LOCK TABLE {table} IN SHARE ROW EXCLUSIVE MODE")
                pending = [pool.submit(worker, index) for index in range(len(operations))]
                deadline = time.monotonic() + 6
                waiting = 0
                while time.monotonic() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_stat_clear_snapshot()")
                        cursor.execute(
                            "SELECT count(DISTINCT activity.pid) FROM pg_locks locks "
                            "JOIN pg_stat_activity activity ON activity.pid = locks.pid "
                            "WHERE NOT locks.granted AND locks.relation = %s::regclass "
                            "AND activity.application_name = %s",
                            [Exercise._meta.db_table, token],
                        )
                        result = cursor.fetchone()
                        assert result is not None
                        waiting = result[0]
                    if waiting == len(operations):
                        break
                    time.sleep(0.02)
                self.assertEqual(waiting, len(operations), "Writers never reached DB contention")
            # Releasing the coordinator allows native database serialization.
            return [future.result(timeout=15) for future in pending]

    def assert_acyclic_and_archivable(self) -> None:
        parents = dict(Exercise.objects.values_list("pk", "variante_de_id"))
        for identity in parents:
            visited: set[int] = set()
            current: int | None = identity
            while current is not None:
                self.assertNotIn(current, visited)
                visited.add(current)
                current = parents[current]
        for row in Exercise.objects.all():
            row.archivado = True
            row.save(update_fields=["archivado"])

    def test_opposing_staff_api_patches_revalidate_after_waiting(self) -> None:
        first, second = self.rows[:2]
        results = self.contend(
            [self.writer("api", first, second), self.writer("api", second, first)]
        )
        self.assertCountEqual(results, [200, 400])
        self.assert_acyclic_and_archivable()

    def test_opposing_orm_saves_on_different_rows_cannot_form_a_cycle(self) -> None:
        first, second = self.rows[:2]
        results = self.contend(
            [self.writer("orm", first, second), self.writer("orm", second, first)]
        )
        self.assertCountEqual(results, [200, 400])
        self.assert_acyclic_and_archivable()

    def test_admin_and_orm_share_the_same_topology_guard(self) -> None:
        first, second = self.rows[:2]
        results = self.contend(
            [self.writer("admin", first, second), self.writer("orm", second, first)]
        )
        self.assertCountEqual(results, [200, 400])
        self.assert_acyclic_and_archivable()

    def test_three_concurrent_edges_cannot_close_a_longer_cycle(self) -> None:
        first, second, third = self.rows
        results = self.contend(
            [
                self.writer("api", first, second),
                self.writer("api", second, third),
                self.writer("orm", third, first),
            ]
        )
        self.assertCountEqual(results, [200, 200, 400])
        self.assert_acyclic_and_archivable()

    def test_stale_repeatable_read_snapshot_fails_closed(self) -> None:
        def writer(row: Exercise, parent: Exercise) -> Callable[[], int]:
            def write() -> int:
                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                        current = Exercise.objects.get(pk=row.pk)
                        current.variante_de_id = parent.pk
                        current.save()
                except OperationalError as error:
                    if getattr(error.__cause__, "sqlstate", None) != "40001":
                        raise
                    return 409
                return 200

            return write

        first, second = self.rows[:2]
        self.assertCountEqual(
            self.contend([writer(first, second), writer(second, first)]), [200, 409]
        )
        self.assert_acyclic_and_archivable()
