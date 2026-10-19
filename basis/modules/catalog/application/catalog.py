"""Catalog use cases with explicit staff authorization."""

from dataclasses import dataclass, replace
from typing import Callable, Protocol

from basis.shared.identifiers import AccountId, ClassificationId, ExerciseId
from basis.shared.ports import UnitOfWork
from basis.shared.text import normalized_name

from ..domain.catalog import ClassificationData, ExerciseData


class CatalogAuthorization(Protocol):
    def require_write(self, actor: AccountId) -> None: ...


class CatalogRepository(Protocol):
    def classification(self, id: ClassificationId) -> ClassificationData: ...
    def exercise(self, id: ExerciseId) -> ExerciseData: ...
    def save_classification(
        self, data: ClassificationData, id: ClassificationId | None
    ) -> ClassificationId: ...
    def save_exercise(self, data: ExerciseData, id: ExerciseId | None) -> ExerciseId: ...
    def delete_classification(self, id: ClassificationId) -> None: ...
    def delete_exercise(self, id: ExerciseId) -> None: ...


@dataclass(frozen=True)
class SaveClassification:
    actor: AccountId
    data: ClassificationData
    id: ClassificationId | None = None


@dataclass(frozen=True)
class SaveExercise:
    actor: AccountId
    data: ExerciseData
    id: ExerciseId | None = None


@dataclass(frozen=True)
class DeleteClassification:
    actor: AccountId
    id: ClassificationId


@dataclass(frozen=True)
class DeleteExercise:
    actor: AccountId
    id: ExerciseId


class Catalog:
    def __init__(
        self,
        repository: CatalogRepository,
        authorization: CatalogAuthorization,
        uow: Callable[[], UnitOfWork],
    ) -> None:
        self.repository, self.authorization, self.uow = repository, authorization, uow

    def save_classification(self, command: SaveClassification) -> ClassificationId:
        with self.uow() as work:
            self.authorization.require_write(command.actor)
            result = self.repository.save_classification(
                replace(command.data, nombre=normalized_name(command.data.nombre)), command.id
            )
            work.commit()
            return result

    def save_exercise(self, command: SaveExercise) -> ExerciseId:
        with self.uow() as work:
            self.authorization.require_write(command.actor)
            result = self.repository.save_exercise(
                replace(command.data, nombre=normalized_name(command.data.nombre)), command.id
            )
            work.commit()
            return result

    def delete_classification(self, command: DeleteClassification) -> None:
        with self.uow() as work:
            self.authorization.require_write(command.actor)
            self.repository.delete_classification(command.id)
            work.commit()

    def delete_exercise(self, command: DeleteExercise) -> None:
        with self.uow() as work:
            self.authorization.require_write(command.actor)
            self.repository.delete_exercise(command.id)
            work.commit()
