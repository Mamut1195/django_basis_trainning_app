"""Shared Django transaction and clock adapters wired by composition roots."""

from datetime import date, datetime
from types import TracebackType
from typing import Self

from django.db import DEFAULT_DB_ALIAS, transaction
from django.utils import timezone


class DjangoUnitOfWork:
    def __init__(self, using: str = DEFAULT_DB_ALIAS) -> None:
        self.using = using
        self.atomic = transaction.atomic(using=using)
        self.committed = False

    def __enter__(self) -> Self:
        self.committed = False
        self.atomic.__enter__()
        return self

    def commit(self) -> None:
        self.committed = True

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if not self.committed:
            transaction.set_rollback(True, using=self.using)
        self.atomic.__exit__(exc_type, exc_value, traceback)


class DjangoClock:
    def today(self) -> date:
        return timezone.localdate()

    def now(self) -> datetime:
        return timezone.now()
