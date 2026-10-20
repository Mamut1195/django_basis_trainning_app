"""Atomic administrative bulk deletion through catalog-specific ports."""

from dataclasses import dataclass
from typing import Callable

from basis.shared.identifiers import AccountId, ClassificationId, ExerciseId
from basis.shared.ports import UnitOfWork

from .catalog import CatalogAuthorization, CatalogRepository


@dataclass(frozen=True)
class DeleteClassifications:
    actor: AccountId
    ids: tuple[ClassificationId, ...]


@dataclass(frozen=True)
class DeleteExercises:
    actor: AccountId
    ids: tuple[ExerciseId, ...]


class CatalogAdministration:
    def __init__(
        self,
        repository: CatalogRepository,
        authorization: CatalogAuthorization,
        uow: Callable[[], UnitOfWork],
    ) -> None:
        self.repository, self.authorization, self.uow = repository, authorization, uow

    def delete_classifications(self, command: DeleteClassifications) -> None:
        with self.uow() as work:
            self.authorization.require_write(command.actor)
            for id in command.ids:
                self.repository.delete_classification(id)
            work.commit()

    def delete_exercises(self, command: DeleteExercises) -> None:
        with self.uow() as work:
            self.authorization.require_write(command.actor)
            for id in command.ids:
                self.repository.delete_exercise(id)
            work.commit()
