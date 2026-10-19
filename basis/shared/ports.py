"""Infrastructure contracts available to application use cases."""

from datetime import date, datetime
from types import TracebackType
from typing import Protocol, Self


class Clock(Protocol):
    def today(self) -> date: ...

    def now(self) -> datetime: ...


class UnitOfWork(Protocol):
    """Rollback on error or on exit without commit, including nested use."""

    def __enter__(self) -> Self: ...

    def commit(self) -> None: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
