"""Account -> lineage anchor -> prescription -> execution, on one DB alias.

SQLite has no row locks. Top-level training transactions reserve its writer before
reading (BEGIN IMMEDIATE); nested transactions retain their caller's isolation.
"""

from uuid import UUID

from django.db import DEFAULT_DB_ALIAS, connections
from django.db.models import Q, QuerySet

from basis.adapters.django.account_locks import lock_account
from basis.adapters.django.transactions import DjangoUnitOfWork
from basis.shared.identifiers import AccountId

from .models import PlannedSession, Session, TrainingPlan


class TrainingUnitOfWork(DjangoUnitOfWork):
    def __enter__(self) -> "TrainingUnitOfWork":
        connection = connections[self.using]
        if connection.vendor == "sqlite" and not connection.in_atomic_block:
            # SQLite initializes transaction_mode while opening the connection.
            # Reserve the writer only after that initialization, otherwise a lazy
            # connection would silently replace IMMEDIATE with its default mode.
            connection.ensure_connection()
        mode = getattr(connection, "transaction_mode", None)
        if connection.vendor == "sqlite" and not connection.in_atomic_block:
            connection.transaction_mode = "IMMEDIATE"  # type: ignore[attr-defined]
        try:
            super().__enter__()
        finally:
            if connection.vendor == "sqlite":
                connection.transaction_mode = mode  # type: ignore[attr-defined]
        return self


def lock_plan(plan: int, alias: str = DEFAULT_DB_ALIAS) -> TrainingPlan:
    query = TrainingPlan.objects.using(alias)
    lineage, owner = query.values_list("lineage", "owner_id").get(pk=plan)
    # Sync/record already hold this lock. Taking it first in every other writer
    # prevents their FK-at-COMMIT from waiting behind a transaction waiting on us.
    lock_account(AccountId(owner), alias)
    # All versions and all writers of this lineage use the same persistent anchor.
    anchor = query.filter(lineage=lineage).order_by("version", "pk").first()
    assert anchor is not None
    query.select_for_update().get(pk=anchor.pk)
    return query.get(pk=plan)


def lock_scheduled(pk: int, alias: str = DEFAULT_DB_ALIAS) -> PlannedSession:
    plan = PlannedSession.objects.using(alias).values_list("plan_id", flat=True).get(pk=pk)
    lock_plan(plan, alias)
    return PlannedSession.objects.using(alias).select_for_update().get(pk=pk)


def lock_execution(pk: UUID, alias: str = DEFAULT_DB_ALIAS) -> None:
    state = Session.objects.using(alias).filter(pk=pk).values_list("owner_id", "planned_id").first()
    if state is not None:
        owner, planned = state
        lock_account(AccountId(owner), alias)
        if planned is not None:
            lock_scheduled(planned, alias)


def intent_executions(row: PlannedSession) -> QuerySet[Session]:
    root = row.origin_id or row.pk
    return Session.objects.using(row._state.db or DEFAULT_DB_ALIAS).filter(
        Q(planned_id=root) | Q(planned__origin_id=root)
    )
